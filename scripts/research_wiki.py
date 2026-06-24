#!/usr/bin/env python3
"""Helper for Zotero-backed Obsidian research wiki projects."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = os.environ.get("ZOTERO_LOCAL_API", "http://127.0.0.1:23119")
DEFAULT_VAULT = Path(os.environ.get("RESEARCH_WIKI_VAULT", "/Users/feng/Documents/Obsidian Vault"))
USER_PREFIX = "/api/users/0"
CACHE_DIR = ".research-wiki/cache"
WIKI_DIRS = ("sources", "concepts", "themes", "methods", "claims")
READ_SCOPES = {
    "high": "阅读全文",
    "medium": "阅读 abstract、introduction、research design、conclusion",
    "low": "只读摘要",
    "exclude": "不阅读",
}
READ_LEVELS = {
    "high": "abstract",
    "medium": "abstract",
    "low": "abstract",
    "exclude": "abstract",
}


class ResearchWikiError(RuntimeError):
    pass


def today() -> str:
    return dt.date.today().isoformat()


def now_iso() -> str:
    return dt.datetime.now().astimezone().replace(microsecond=0).isoformat()


def eprint(message: str) -> None:
    print(message, file=sys.stderr)


def slug(value: str, fallback: str = "project") -> str:
    cleaned = re.sub(r"[/:\\]+", " ", value).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or fallback


def creator_name(creator: dict[str, Any]) -> str:
    if creator.get("name"):
        return str(creator["name"])
    first = str(creator.get("firstName") or "").strip()
    last = str(creator.get("lastName") or "").strip()
    return " ".join(part for part in (first, last) if part)


def first_author_slug(creators: list[dict[str, Any]]) -> str:
    if not creators:
        return "unknown"
    name = creator_name(creators[0]) or "unknown"
    last = name.split()[-1]
    return re.sub(r"[^A-Za-z0-9]+", "-", last).strip("-").lower() or "unknown"


def year_from_item(data: dict[str, Any]) -> str:
    date = str(data.get("date") or "")
    match = re.search(r"(18|19|20)\d{2}", date)
    return match.group(0) if match else "n.d"


def short_title_slug(title: str, max_words: int = 6) -> str:
    words = re.findall(r"[A-Za-z0-9]+", title)
    if words:
        return "-".join(words[:max_words]).lower()
    compact = re.sub(r"\s+", "-", title.strip())[:48].strip("-")
    return compact or "untitled"


def source_note_name(item: dict[str, Any]) -> str:
    data = item.get("data", item)
    title = str(data.get("title") or "Untitled")
    creators = data.get("creators") or []
    return f"{year_from_item(data)}-{first_author_slug(creators)}-{short_title_slug(title)}.md"


def request_json(path: str, params: dict[str, Any] | None = None) -> Any:
    query = urllib.parse.urlencode(params or {}, doseq=True)
    url = f"{DEFAULT_BASE_URL}{path}"
    if query:
        url = f"{url}?{query}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Zotero-API-Version": "3",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise ResearchWikiError(f"Zotero API returned HTTP {exc.code} for {path}") from exc
    except urllib.error.URLError as exc:
        raise ResearchWikiError(f"Could not reach Zotero local API at {DEFAULT_BASE_URL}: {exc}") from exc
    if not data:
        return None
    return json.loads(data)


def request_text(path: str, params: dict[str, Any] | None = None) -> str:
    query = urllib.parse.urlencode(params or {}, doseq=True)
    url = f"{DEFAULT_BASE_URL}{path}"
    if query:
        url = f"{url}?{query}"
    request = urllib.request.Request(url, headers={"Accept": "text/plain"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def paged_json(path: str, params: dict[str, Any] | None = None, limit: int = 100) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    start = 0
    base_params = dict(params or {})
    while True:
        page_params = dict(base_params)
        page_params.update({"limit": limit, "start": start})
        page = request_json(path, page_params)
        if not isinstance(page, list):
            raise ResearchWikiError(f"Expected list response for {path}")
        items.extend(page)
        if len(page) < limit:
            break
        start += limit
    return items


def all_collections() -> list[dict[str, Any]]:
    return paged_json(f"{USER_PREFIX}/collections", {"include": "data"})


def find_collection(collections: list[dict[str, Any]], key: str | None, name: str | None) -> dict[str, Any]:
    if key:
        for collection in collections:
            if collection.get("key") == key:
                return collection
        raise ResearchWikiError(f"No Zotero collection found with key {key}")
    if name:
        matches = [c for c in collections if c.get("data", {}).get("name") == name]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise ResearchWikiError(f"No Zotero collection found named {name!r}")
        keys = ", ".join(c["key"] for c in matches)
        raise ResearchWikiError(f"Multiple Zotero collections named {name!r}: {keys}. Use --collection-key.")
    raise ResearchWikiError("Pass --collection-key or --collection-name")


def descendant_collection_keys(collections: list[dict[str, Any]], root_key: str) -> list[str]:
    children_by_parent: dict[str, list[str]] = {}
    for collection in collections:
        parent = collection.get("data", {}).get("parentCollection")
        if parent:
            children_by_parent.setdefault(parent, []).append(str(collection["key"]))
    result: list[str] = []
    stack = [root_key]
    seen: set[str] = set()
    while stack:
        key = stack.pop(0)
        if key in seen:
            continue
        seen.add(key)
        result.append(key)
        stack.extend(children_by_parent.get(key, []))
    return result


def collection_items(collection_key: str) -> list[dict[str, Any]]:
    records = paged_json(f"{USER_PREFIX}/collections/{collection_key}/items", {"include": "data"})
    top_level = []
    for record in records:
        data = record.get("data", {})
        if data.get("itemType") == "attachment" or data.get("parentItem"):
            continue
        top_level.append(record)
    return top_level


def item_children(item_key: str) -> list[dict[str, Any]]:
    return paged_json(f"{USER_PREFIX}/items/{item_key}/children", {"include": "data"})


def child_attachments(item_key: str) -> list[dict[str, Any]]:
    children = item_children(item_key)
    return [child for child in children if child.get("data", {}).get("itemType") == "attachment"]


def child_notes_and_annotations(item_key: str) -> list[dict[str, Any]]:
    children = paged_json(f"{USER_PREFIX}/items/{item_key}/children", {"include": "data"})
    result = [child for child in children if child.get("data", {}).get("itemType") in {"note", "annotation"}]
    for attachment in [child for child in children if child.get("data", {}).get("itemType") == "attachment"]:
        attachment_key = str(attachment.get("key"))
        try:
            attachment_children = item_children(attachment_key)
        except ResearchWikiError:
            attachment_children = []
        result.extend(
            child for child in attachment_children if child.get("data", {}).get("itemType") in {"note", "annotation"}
        )
    return result


def fulltext_for_attachment(attachment_key: str) -> dict[str, Any] | None:
    try:
        data = request_json(f"{USER_PREFIX}/items/{attachment_key}/fulltext")
    except ResearchWikiError:
        return None
    if isinstance(data, dict) and data.get("content"):
        return data
    return None


def item_summary(record: dict[str, Any]) -> dict[str, Any]:
    data = record.get("data", record)
    creators = [creator_name(c) for c in data.get("creators", []) if creator_name(c)]
    return {
        "key": record.get("key") or data.get("key"),
        "itemType": data.get("itemType"),
        "title": data.get("title"),
        "creators": creators,
        "year": year_from_item(data),
        "date": data.get("date"),
        "publicationTitle": data.get("publicationTitle"),
        "DOI": data.get("DOI"),
        "url": data.get("url"),
        "abstractNote": data.get("abstractNote"),
        "tags": [tag.get("tag") for tag in data.get("tags", []) if isinstance(tag, dict)],
        "collections": data.get("collections", []),
        "source_note": source_note_name(record),
    }


def item_by_key(item_key: str) -> dict[str, Any]:
    record = request_json(f"{USER_PREFIX}/items/{urllib.parse.quote(item_key)}", {"include": "data"})
    if not isinstance(record, dict):
        raise ResearchWikiError(f"No Zotero item found with key {item_key}")
    return record


def strip_html(value: str) -> str:
    text = re.sub(r"(?i)<br\s*/?>", "\n", value or "")
    text = re.sub(r"(?i)</p\s*>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def markdown_cell(value: Any) -> str:
    text = strip_html(str(value or ""))
    return text.replace("\n", "<br>").replace("|", "\\|")


def has_frontmatter_field(text: str, field: str) -> bool:
    if not text.startswith("---\n"):
        return False
    end = text.find("\n---\n", 4)
    if end == -1:
        return False
    frontmatter = text[4:end]
    return re.search(rf"(?m)^{re.escape(field)}\s*:", frontmatter) is not None


def yaml_scalar(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return "[" + ", ".join(yaml_scalar(item) for item in value) + "]"
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    if "\n" in text:
        indented = "\n".join("  " + line for line in text.split("\n"))
        return "|\n" + indented
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def citation_key_from_item(data: dict[str, Any]) -> str:
    for key in ("citationKey", "citekey"):
        if data.get(key):
            return str(data[key])
    extra = str(data.get("extra") or "")
    patterns = (
        r"(?im)^\s*Citation Key\s*:\s*(\S+)\s*$",
        r"(?im)^\s*tex\.ids\s*=\s*(\S+)\s*$",
        r"(?im)^\s*bibtex\s*:\s*(\S+)\s*$",
    )
    for pattern in patterns:
        match = re.search(pattern, extra)
        if match:
            return match.group(1).strip()
    return ""


def source_fingerprint(item: dict[str, Any], notes_and_annotations: list[dict[str, Any]]) -> str:
    data = item.get("data", item)
    payload = {
        "item": {
            "key": item.get("key") or data.get("key"),
            "version": item.get("version"),
            "dateModified": data.get("dateModified"),
            "title": data.get("title"),
            "creators": data.get("creators"),
            "date": data.get("date"),
            "publicationTitle": data.get("publicationTitle"),
            "DOI": data.get("DOI"),
            "url": data.get("url"),
            "abstractNote": data.get("abstractNote"),
            "extra": data.get("extra"),
        },
        "notes_and_annotations": [
            {
                "key": child.get("key"),
                "version": child.get("version"),
                "dateModified": child.get("data", {}).get("dateModified"),
                "itemType": child.get("data", {}).get("itemType"),
                "annotationType": child.get("data", {}).get("annotationType"),
                "annotationText": child.get("data", {}).get("annotationText"),
                "annotationComment": child.get("data", {}).get("annotationComment"),
                "note": child.get("data", {}).get("note"),
            }
            for child in notes_and_annotations
        ],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def annotation_rows(notes_and_annotations: list[dict[str, Any]]) -> list[str]:
    rows: list[str] = []
    for child in notes_and_annotations:
        data = child.get("data", {})
        item_type = data.get("itemType")
        if item_type == "annotation":
            tags = ", ".join(tag.get("tag", "") for tag in data.get("tags", []) if isinstance(tag, dict))
            rows.append(
                "| {page} | {atype} | {color} | {text} | {comment} | {tags} |".format(
                    page=markdown_cell(data.get("annotationPageLabel", "")),
                    atype=markdown_cell(data.get("annotationType", "")),
                    color=markdown_cell(data.get("annotationColor", "")),
                    text=markdown_cell(data.get("annotationText", "")),
                    comment=markdown_cell(data.get("annotationComment", "")),
                    tags=markdown_cell(tags),
                )
            )
        elif item_type == "note":
            tags = ", ".join(tag.get("tag", "") for tag in data.get("tags", []) if isinstance(tag, dict))
            rows.append(f"|  | note |  |  | {markdown_cell(data.get('note', ''))} | {markdown_cell(tags)} |")
    return rows or ["| | highlight / note / image | | | | |"]


def render_source_note(
    item: dict[str, Any],
    notes_and_annotations: list[dict[str, Any]],
    project_name: str,
    priority: str,
) -> str:
    data = item.get("data", item)
    item_key = str(item.get("key") or data.get("key") or "")
    creators = [creator_name(c) for c in data.get("creators", []) if creator_name(c)]
    authors = "; ".join(creators)
    title = str(data.get("title") or "")
    year = year_from_item(data)
    venue = str(data.get("publicationTitle") or data.get("conferenceName") or data.get("publisher") or "")
    doi = str(data.get("DOI") or "")
    url = str(data.get("url") or "")
    abstract = str(data.get("abstractNote") or "")
    citation_key = citation_key_from_item(data)
    zotero_uri = f"zotero://select/library/items/{item_key}"
    timestamp = now_iso()
    fingerprint = source_fingerprint(item, notes_and_annotations)
    zotero_modified = str(data.get("dateModified") or "")
    tags = [tag.get("tag") for tag in data.get("tags", []) if isinstance(tag, dict) and tag.get("tag")]
    status = "deep_read_skip" if priority == "exclude" else "screened"
    need_fulltext_read = priority in {"high", "medium"}
    read_level = READ_LEVELS[priority]

    frontmatter = {
        "type": "source",
        "status": status,
        "zotero_item_key": item_key,
        "zotero_library_id": "0",
        "zotero_uri": zotero_uri,
        "citation_key": citation_key,
        "title": title,
        "authors": authors,
        "year": year,
        "venue": venue,
        "doi": doi,
        "url": url,
        "abstract": abstract,
        "created": timestamp,
        "updated": timestamp,
        "zotero_modified": zotero_modified,
        "source_fingerprint": fingerprint,
        "deep_read_priority": priority,
        "read_scope": READ_SCOPES[priority],
        "need_fulltext_read": need_fulltext_read,
        "deep_read_completed": "",
        "read_level": read_level,
        "tags": tags,
        "project": project_name,
    }
    yaml = "---\n" + "\n".join(f"{key}: {yaml_scalar(value)}" for key, value in frontmatter.items()) + "\n---"
    citation = f"[@{citation_key}]" if citation_key else ""
    rows = "\n".join(annotation_rows(notes_and_annotations))
    return f"""{yaml}
# {title or item_key}

## 1. 文献基本信息
- 标题：{title}
- 作者：{authors}
- 年度：{year}
- 期刊：{venue}
- DOI：{doi}
- Zotero item key：{item_key}
- Citation key：{citation_key}
- Zotero link：{zotero_uri}
- 写作引用：{citation}
- 摘要：{abstract}

## 2. MD 文件信息
- 创建时间：{timestamp}
- 最后修改时间：{timestamp}
- Zotero 条目修改时间：{zotero_modified}
- Source fingerprint：{fingerprint}
- 当前精读标签：{priority}
- 当前阅读范围：{READ_SCOPES[priority]}
- 当前阅读状态：{status}
- 已完成阅读层级：{read_level}
- 精读完成日期：
- 更新状态：up-to-date

## 3. 初筛判断
- 是否纳入后续研究：
- 项目相关性：
- 文献角色：core_literature / related_stream / theory_mechanism / method_data / china_context / excluded_weakfit
- 精读优先级：{priority}
- 排除或保留理由：

## 4. 具体研究内容
### 4.1 研究问题
- 本文研究什么问题：
- 该问题为何重要：
- 对应的会计/财务研究场景：

### 4.2 研究方法
- 研究设计类型：
- 数据来源：
- 样本范围：
- 样本期间：
- 分析单位：

### 4.3 主检验
- 主检验模型：
```text

```
- 被解释变量：
- 解释变量：
- 控制变量：
- 固定效应：
- 标准误聚类：
- 主检验结论：

### 4.4 机制检验
- 机制逻辑：
- 机制检验方法：
- 机制检验模型：
```text

```
- 机制变量：
- 机制检验结论：

### 4.5 异质性检验
- 分组或调节变量：
- 检验方法：
- 检验模型：
```text

```
- 异质性结论：

### 4.6 稳健性检验
- 替代变量：
- 替代样本：
- 替代模型：
- 其他稳健性处理：
- 稳健性结论：

### 4.7 内生性检验
- 潜在内生性问题：
- 处理方法：
- 检验模型：
```text

```
- 工具变量 / DID / PSM / Heckman / 其他方法：
- 内生性处理结论：

## 5. 文章评价
### 5.1 主要结论
-

### 5.2 创新点
-

### 5.3 不足与识别风险
-

### 5.4 对本项目的启发
- 可借鉴之处：
- 需要避免之处：
- 可用于文献综述的位置：
- 可用于研究设计的位置：
- 可用于变量设计的位置：

## 6. Zotero 阅读注释
> 从 Zotero annotations / notes 同步或整理。

| Page | Type | Color | Text | Comment | Tags |
|---|---|---|---|---|---|
{rows}

## 7. 待补充清单
- 缺失的元数据：
- 需要阅读全文确认：
- 需要核对的模型或变量：
- 需要补充的 Zotero 注释：
- 需要连接的 concept/theme/method/claim 页面：
"""


def ensure_project(project_path: Path, collection_key: str | None, collection_name: str | None) -> None:
    project_path.mkdir(parents=True, exist_ok=True)
    for directory in WIKI_DIRS:
        (project_path / directory).mkdir(exist_ok=True)
    (project_path / CACHE_DIR / "items").mkdir(parents=True, exist_ok=True)
    (project_path / CACHE_DIR / "fulltext").mkdir(parents=True, exist_ok=True)
    (project_path / CACHE_DIR / "collections").mkdir(parents=True, exist_ok=True)

    write_if_missing(project_path / "AGENTS.md", project_agents_md(collection_key, collection_name))
    write_if_missing(project_path / "index.md", project_index_md(collection_key, collection_name))
    write_if_missing(project_path / "log.md", project_log_md())


def write_if_missing(path: Path, content: str) -> bool:
    if path.exists():
        return False
    path.write_text(content, encoding="utf-8")
    return True


def project_agents_md(collection_key: str | None, collection_name: str | None) -> str:
    collection_line = collection_name or collection_key or "TBD"
    return f"""# Research Wiki Agent Schema

Project source: Zotero collection `{collection_line}`.

## Contract

- Treat Zotero and `.research-wiki/cache/` as raw source layers.
- Treat this Obsidian folder as the maintained wiki layer.
- Do not edit Zotero records, PDFs, or attachments.
- Use Chinese synthesis with preserved English titles, constructs, methods, and variable names.

## Structure

- `sources/`: one note per Zotero item.
- `concepts/`: concepts, constructs, mechanisms, theories, variables.
- `themes/`: literature streams and evolving research narratives.
- `methods/`: data, measurements, empirical designs, identification strategies.
- `claims/`: propositions, contradictions, boundary conditions, evidence status.
- `index.md`: content index updated after every meaningful wiki change.
- `log.md`: append-only chronological record.
- `.research-wiki/cache/`: generated Zotero metadata and full text. Do not manually edit.

## Ingest Checklist

1. Read the item metadata and indexed full text from `.research-wiki/cache/`.
2. Create or update a source page in `sources/`.
3. Link the source to relevant concepts, themes, methods, and claims.
4. Update existing synthesis pages before creating new pages.
5. Update `index.md`.
6. Append `log.md` with changed pages and blockers.

## Source Note Contract

Source pages must preserve Zotero traceability and AR reading priority:

- Keep `zotero_item_key`, `zotero_uri`, and `citation_key` in frontmatter.
- Keep `created`, `updated`, `zotero_modified`, and `source_fingerprint`.
- Use `deep_read_priority`: `high`, `medium`, `low`, or `exclude`.
- Use read-state fields: `status`, `need_fulltext_read`, `read_level`, and `deep_read_completed`.
- Use `high` for full-text deep reading; `medium` for abstract, introduction, research design, and conclusion; `low` for abstract-only screening; `exclude` for records not read.
- Treat `deep_read_priority` as priority, not completion state. Use `status: deep_read_done` and `deep_read_completed: YYYY-MM-DD` only after completing the planned deep read.
- Initial source notes may use only Zotero metadata, abstract, notes, and annotations. Leave unknown research-design fields blank.
"""


def project_index_md(collection_key: str | None, collection_name: str | None) -> str:
    collection_line = collection_name or collection_key or "TBD"
    return f"""# Index

Research wiki for Zotero collection `{collection_line}`.

## Sources

## Concepts

## Themes

## Methods

## Claims
"""


def project_log_md() -> str:
    return f"""# Log

## [{today()}] init | Project skeleton

- Created research wiki skeleton.
"""


def add_source_to_index(project_path: Path, source_path: Path, item: dict[str, Any]) -> None:
    index_path = project_path / "index.md"
    if not index_path.exists():
        write_if_missing(index_path, project_index_md(None, None))
    text = index_path.read_text(encoding="utf-8")
    rel = source_path.relative_to(project_path)
    stem = source_path.stem
    data = item.get("data", item)
    title = str(data.get("title") or stem)
    year = year_from_item(data)
    entry = f"- [[{stem}]] - {year}; {title}; Zotero `{item.get('key') or data.get('key')}`"
    if f"[[{stem}" in text or str(rel) in text:
        return
    marker = "## Sources"
    if marker not in text:
        text = text.rstrip() + f"\n\n{marker}\n"
    lines = text.splitlines()
    insert_at = None
    for index, line in enumerate(lines):
        if line.strip() == marker:
            insert_at = index + 1
            break
    if insert_at is None:
        lines.append(marker)
        insert_at = len(lines)
    lines.insert(insert_at, entry)
    index_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def append_log(project_path: Path, kind: str, title: str, bullets: list[str]) -> None:
    log_path = project_path / "log.md"
    if not log_path.exists():
        write_if_missing(log_path, project_log_md())
    existing = log_path.read_text(encoding="utf-8")
    body = "\n".join(f"- {bullet}" for bullet in bullets)
    entry = f"\n## [{today()}] {kind} | {title}\n\n{body}\n"
    log_path.write_text(existing.rstrip() + "\n" + entry, encoding="utf-8")


def resolve_project_path(args: argparse.Namespace) -> Path:
    if getattr(args, "project_path", None):
        return Path(args.project_path).expanduser().resolve()
    if getattr(args, "project", None):
        vault = Path(getattr(args, "vault", DEFAULT_VAULT)).expanduser()
        return (vault / slug(args.project)).resolve()
    raise ResearchWikiError("Pass --project-path or --project")


def require_yes(args: argparse.Namespace, target: Path) -> None:
    if not getattr(args, "yes", False):
        print(json.dumps({"dry_run": True, "target": str(target), "message": "Re-run with --yes to write."}, ensure_ascii=False, indent=2))
        raise SystemExit(0)


def command_status(args: argparse.Namespace) -> int:
    result: dict[str, Any] = {
        "zotero_base_url": DEFAULT_BASE_URL,
        "vault": str(Path(args.vault).expanduser().resolve()),
        "vault_exists": Path(args.vault).expanduser().exists(),
    }
    try:
        root = request_text("/api/")
        schema = request_json("/api/schema")
        result.update(
            {
                "api_running": True,
                "api_root": root.strip(),
                "schema_version": schema.get("version") if isinstance(schema, dict) else None,
            }
        )
    except Exception as exc:
        result.update({"api_running": False, "api_error": str(exc)})
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["api_running"] else 1


def command_collections(args: argparse.Namespace) -> int:
    collections = all_collections()
    rows = []
    for collection in collections:
        data = collection.get("data", {})
        meta = collection.get("meta", {})
        rows.append(
            {
                "key": collection.get("key"),
                "name": data.get("name"),
                "parent": data.get("parentCollection") or None,
                "num_items": meta.get("numItems"),
                "num_collections": meta.get("numCollections"),
            }
        )
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for row in rows:
            parent = f" parent={row['parent']}" if row["parent"] else ""
            print(f"{row['key']:<10} {row['name']} items={row['num_items']} children={row['num_collections']}{parent}")
    return 0


def command_init_project(args: argparse.Namespace) -> int:
    collections = all_collections()
    collection = None
    if args.collection_key or args.collection_name:
        collection = find_collection(collections, args.collection_key, args.collection_name)
    project_path = resolve_project_path(args)
    require_yes(args, project_path)
    ensure_project(
        project_path,
        collection.get("key") if collection else args.collection_key,
        collection.get("data", {}).get("name") if collection else args.collection_name,
    )
    print(json.dumps({"project_path": str(project_path), "created": True}, ensure_ascii=False, indent=2))
    return 0


def command_export_collection(args: argparse.Namespace) -> int:
    collections = all_collections()
    collection = find_collection(collections, args.collection_key, args.collection_name)
    collection_key = str(collection["key"])
    collection_name = str(collection.get("data", {}).get("name") or collection_key)
    project_path = resolve_project_path(args)
    require_yes(args, project_path)
    ensure_project(project_path, collection_key, collection_name)

    keys = [collection_key]
    if args.recursive:
        keys = descendant_collection_keys(collections, collection_key)

    seen_items: dict[str, dict[str, Any]] = {}
    for key in keys:
        for item in collection_items(key):
            item_key = str(item.get("key"))
            seen_items.setdefault(item_key, item)

    items = list(seen_items.values())
    if args.limit:
        items = items[: args.limit]

    cache = project_path / CACHE_DIR
    manifest = {
        "collection_key": collection_key,
        "collection_name": collection_name,
        "recursive": args.recursive,
        "exported_at": dt.datetime.now().isoformat(timespec="seconds"),
        "item_count": len(items),
        "items": [],
    }

    missing_fulltext: list[str] = []
    for item in items:
        item_key = str(item["key"])
        attachments = child_attachments(item_key)
        notes_and_annotations = child_notes_and_annotations(item_key)
        summary = item_summary(item)
        summary["source_fingerprint"] = source_fingerprint(item, notes_and_annotations)
        summary["attachments"] = [
            {
                "key": attachment.get("key"),
                "title": attachment.get("data", {}).get("title"),
                "filename": attachment.get("data", {}).get("filename"),
                "contentType": attachment.get("data", {}).get("contentType"),
            }
            for attachment in attachments
        ]
        summary["notes_and_annotations"] = [
            {
                "key": child.get("key"),
                "itemType": child.get("data", {}).get("itemType"),
                "annotationType": child.get("data", {}).get("annotationType"),
                "annotationPageLabel": child.get("data", {}).get("annotationPageLabel"),
                "annotationColor": child.get("data", {}).get("annotationColor"),
                "annotationText": child.get("data", {}).get("annotationText"),
                "annotationComment": child.get("data", {}).get("annotationComment"),
                "note": child.get("data", {}).get("note"),
                "tags": child.get("data", {}).get("tags", []),
                "dateModified": child.get("data", {}).get("dateModified"),
            }
            for child in notes_and_annotations
        ]
        (cache / "items" / f"{item_key}.json").write_text(
            json.dumps({"summary": summary, "raw": item}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        fulltext_written = []
        for attachment in attachments:
            attachment_key = str(attachment.get("key"))
            fulltext = fulltext_for_attachment(attachment_key)
            if not fulltext:
                continue
            out = cache / "fulltext" / f"{item_key}__{attachment_key}.txt"
            header = {
                "item_key": item_key,
                "attachment_key": attachment_key,
                "indexedPages": fulltext.get("indexedPages"),
                "totalPages": fulltext.get("totalPages"),
            }
            out.write_text(json.dumps(header, ensure_ascii=False) + "\n\n" + str(fulltext["content"]), encoding="utf-8")
            fulltext_written.append(str(out.relative_to(project_path)))

        if not fulltext_written:
            missing_fulltext.append(item_key)

        manifest["items"].append(
            {
                "key": item_key,
                "title": summary["title"],
                "year": summary["year"],
                "source_note": summary["source_note"],
                "metadata": str((cache / "items" / f"{item_key}.json").relative_to(project_path)),
                "fulltext": fulltext_written,
            }
        )

    manifest_path = cache / "collections" / f"{collection_key}.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "project_path": str(project_path),
                "collection_key": collection_key,
                "collection_name": collection_name,
                "items_exported": len(items),
                "manifest": str(manifest_path),
                "missing_fulltext": missing_fulltext,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def command_source_note(args: argparse.Namespace) -> int:
    project_path = resolve_project_path(args)
    require_yes(args, project_path)
    ensure_project(project_path, None, None)
    item = item_by_key(args.item_key)
    notes_and_annotations = child_notes_and_annotations(args.item_key)
    project_name = args.project_name or project_path.name
    content = render_source_note(item, notes_and_annotations, project_name, args.priority)
    source_path = project_path / "sources" / source_note_name(item)
    if source_path.exists() and not args.overwrite:
        raise ResearchWikiError(f"Source note already exists: {source_path}. Use --overwrite to regenerate.")
    source_path.write_text(content, encoding="utf-8")
    add_source_to_index(project_path, source_path, item)
    append_log(
        project_path,
        "ingest",
        str(item.get("data", {}).get("title") or args.item_key),
        [
            f"Created or updated source note `{source_path.relative_to(project_path)}`.",
            f"Zotero item key: `{args.item_key}`.",
            f"AR read priority: `{args.priority}`.",
        ],
    )
    print(
        json.dumps(
            {
                "project_path": str(project_path),
                "source_note": str(source_path),
                "item_key": args.item_key,
                "priority": args.priority,
                "written": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def markdown_pages(project_path: Path) -> list[Path]:
    return sorted(p for p in project_path.rglob("*.md") if ".research-wiki" not in p.parts)


def command_check(args: argparse.Namespace) -> int:
    project_path = resolve_project_path(args)
    if not project_path.exists():
        raise ResearchWikiError(f"Project path does not exist: {project_path}")
    cache = project_path / CACHE_DIR
    item_files = sorted((cache / "items").glob("*.json")) if (cache / "items").exists() else []
    fulltext_files = sorted((cache / "fulltext").glob("*.txt")) if (cache / "fulltext").exists() else []
    source_files = sorted((project_path / "sources").glob("*.md")) if (project_path / "sources").exists() else []
    pages = markdown_pages(project_path)
    allowed_roots = set(WIKI_DIRS)
    special = {"AGENTS.md", "index.md", "log.md"}
    orphan_locations = []
    for page in pages:
        rel = page.relative_to(project_path)
        if len(rel.parts) == 1 and rel.name in special:
            continue
        if rel.parts[0] not in allowed_roots:
            orphan_locations.append(str(rel))

    index_text = (project_path / "index.md").read_text(encoding="utf-8") if (project_path / "index.md").exists() else ""
    unindexed_pages = []
    for page in pages:
        rel = page.relative_to(project_path)
        if rel.name in special:
            continue
        stem = page.stem
        if f"[[{stem}" not in index_text and str(rel) not in index_text:
            unindexed_pages.append(str(rel))

    source_text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in source_files)
    missing_source_notes = []
    missing_fulltext = []
    missing_read_state = []
    fulltext_by_item = {p.name.split("__", 1)[0] for p in fulltext_files}
    for item_file in item_files:
        key = item_file.stem
        if key not in source_text:
            missing_source_notes.append(key)
        if key not in fulltext_by_item:
            missing_fulltext.append(key)
    for source_file in source_files:
        text = source_file.read_text(encoding="utf-8", errors="replace")
        missing_fields = [
            field
            for field in ("status", "need_fulltext_read", "read_level", "deep_read_completed")
            if not has_frontmatter_field(text, field)
        ]
        if missing_fields:
            missing_read_state.append(
                {"source": str(source_file.relative_to(project_path)), "missing": missing_fields}
            )

    result = {
        "project_path": str(project_path),
        "cache_items": len(item_files),
        "fulltext_files": len(fulltext_files),
        "source_notes": len(source_files),
        "missing_source_notes": missing_source_notes,
        "missing_fulltext": missing_fulltext,
        "missing_read_state": missing_read_state,
        "orphan_locations": orphan_locations,
        "unindexed_pages": unindexed_pages,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Zotero-backed Obsidian research wiki projects.")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="Verify Zotero local API and vault path.")
    status.add_argument("--vault", default=str(DEFAULT_VAULT))
    status.set_defaults(func=command_status)

    collections = sub.add_parser("collections", help="List Zotero collections.")
    collections.add_argument("--json", action="store_true")
    collections.set_defaults(func=command_collections)

    init = sub.add_parser("init-project", help="Create an Obsidian project skeleton.")
    init.add_argument("--project", help="Project folder name under --vault.")
    init.add_argument("--project-path", help="Exact project path to create.")
    init.add_argument("--vault", default=str(DEFAULT_VAULT))
    init.add_argument("--collection-key")
    init.add_argument("--collection-name")
    init.add_argument("--yes", action="store_true", help="Confirm writing project files.")
    init.set_defaults(func=command_init_project)

    export = sub.add_parser("export-collection", help="Export Zotero collection metadata and indexed full text caches.")
    export.add_argument("--collection-key")
    export.add_argument("--collection-name")
    export.add_argument("--project", help="Project folder name under --vault.")
    export.add_argument("--project-path", help="Exact project path.")
    export.add_argument("--vault", default=str(DEFAULT_VAULT))
    export.add_argument("--limit", type=int, help="Limit exported top-level Zotero items.")
    export.add_argument("--recursive", dest="recursive", action="store_true", default=True)
    export.add_argument("--no-recursive", dest="recursive", action="store_false")
    export.add_argument("--yes", action="store_true", help="Confirm writing cache files.")
    export.set_defaults(func=command_export_collection)

    source_note = sub.add_parser("source-note", help="Create one Zotero-backed source note in an existing wiki project.")
    source_note.add_argument("item_key", help="Zotero item key.")
    source_note.add_argument("--project", help="Project folder name under --vault.")
    source_note.add_argument("--project-path", help="Exact project path.")
    source_note.add_argument("--vault", default=str(DEFAULT_VAULT))
    source_note.add_argument("--priority", choices=sorted(READ_SCOPES), default="low")
    source_note.add_argument("--project-name", help="Project label to store in source note frontmatter.")
    source_note.add_argument("--overwrite", action="store_true", help="Overwrite an existing source note.")
    source_note.add_argument("--yes", action="store_true", help="Confirm writing the source note.")
    source_note.set_defaults(func=command_source_note)

    check = sub.add_parser("check", help="Check project cache/wiki consistency.")
    check.add_argument("--project", help="Project folder name under --vault.")
    check.add_argument("--project-path", help="Exact project path.")
    check.add_argument("--vault", default=str(DEFAULT_VAULT))
    check.set_defaults(func=command_check)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ResearchWikiError as exc:
        eprint(f"error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
