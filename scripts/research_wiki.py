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
CONFIG_FILE = ".research-wiki/config.json"
WIKI_DIRS = ("sources", "concepts", "themes", "methods", "claims")
RESEARCH_BASE_DEFAULT_DIR = "Research Base"
RESEARCH_BASE_DIRS = (
    "00_Conversation_Notes",
    "01_Topic_Exploration",
    "02_Method_Prototypes",
    "03_Data_Feasibility",
    "04_Design_Alternatives",
    "90_Archived_or_Rejected",
    "_templates",
)
RESEARCH_BASE_NOTE_TYPES = {
    "conversation_note",
    "topic_exploration",
    "method_prototype",
    "data_feasibility",
    "design_alternative",
}
RESEARCH_BASE_STATUSES = {"exploratory", "under_review", "promoted", "rejected", "superseded"}
RESEARCH_BASE_EVIDENCE_STATUSES = {"unverified", "partially_verified", "verified"}
RESEARCH_BASE_REQUIRED_FIELDS = (
    "type",
    "status",
    "evidence_status",
    "created",
    "last_updated",
    "kb_promotion",
    "related_kb_pages",
    "supersedes",
)
DEFAULT_PROJECT_CONFIG = {
    "schema_version": 1,
    "knowledge_base_path": ".",
    "research_base_path": RESEARCH_BASE_DEFAULT_DIR,
}
DEFAULT_RESEARCH_BASE_SCHEMA = {
    "directories": list(RESEARCH_BASE_DIRS),
    "note_types": sorted(RESEARCH_BASE_NOTE_TYPES),
    "statuses": sorted(RESEARCH_BASE_STATUSES),
    "evidence_statuses": sorted(RESEARCH_BASE_EVIDENCE_STATUSES),
    "required_fields": list(RESEARCH_BASE_REQUIRED_FIELDS),
}
BOSS_CATEGORIES = {
    "core_literature",
    "related_stream",
    "theory_mechanism",
    "method_data",
    "china_context",
    "excluded_weakfit",
}
PDF_STATUSES = {"need_pdf", "pdf_available", "manual_pdf_pending", "not_needed", "unknown"}
VERIFICATION_STATUSES = {"verified", "partially_verified", "unverified"}
SOURCE_ROUTES = {"openalex", "google_scholar", "cnki", "publisher", "ssrn", "nber", "user", "manual", "unknown"}
READ_LEVEL_VALUES = {"abstract", "intro_design_conclusion", "fulltext"}
METADATA_STATUSES = {"up_to_date", "needs_update", "needs_review"}
SOURCE_STATUSES = {"screened", "deep_read_in_progress", "deep_read_done", "deep_read_skip"}
READ_SCOPES = {
    "high": "阅读全文",
    "medium": "阅读 abstract、introduction、research design、conclusion",
    "low": "只读摘要",
    "exclude": "不阅读",
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
    boss_category: str = "",
    boss_screening_reason: str = "",
    pdf_status: str = "unknown",
    project_use: str = "",
    need_fulltext_read: bool | None = None,
    read_level: str = "abstract",
    deep_read_completed: str = "",
    source_route: str = "unknown",
    verification_status: str = "unverified",
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
    if need_fulltext_read is None:
        need_fulltext_read = priority in {"high", "medium"}
    status = "deep_read_skip" if priority == "exclude" else "screened"
    if read_level == "fulltext" and deep_read_completed:
        status = "deep_read_done"
        need_fulltext_read = False

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
        "metadata_status": "up_to_date",
        "source_route": source_route,
        "verification_status": verification_status,
        "boss_category": boss_category,
        "boss_screening_reason": boss_screening_reason,
        "pdf_status": pdf_status,
        "project_use": project_use,
        "deep_read_priority": priority,
        "read_scope": READ_SCOPES[priority],
        "need_fulltext_read": need_fulltext_read,
        "deep_read_completed": deep_read_completed,
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
- 精读完成日期：{deep_read_completed}
- 更新状态：up-to-date

## 3. 初筛判断
- 是否纳入后续研究：{'否' if priority == 'exclude' else ''}
- 项目相关性：{project_use}
- 文献角色：{boss_category}
- 精读优先级：{priority}
- 排除或保留理由：{boss_screening_reason}

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


ZOTERO_CONTROLLED_SOURCE_FIELDS = {
    "zotero_library_id",
    "zotero_uri",
    "citation_key",
    "title",
    "authors",
    "year",
    "venue",
    "doi",
    "url",
    "abstract",
    "updated",
    "zotero_modified",
    "source_fingerprint",
    "metadata_status",
    "tags",
}


def replace_frontmatter_fields(text: str, updates: dict[str, Any]) -> str:
    if not text.startswith("---\n"):
        raise ResearchWikiError("Existing source note has no valid YAML frontmatter.")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise ResearchWikiError("Existing source note has no valid YAML frontmatter.")
    lines = text[4:end].splitlines()
    output: list[str] = []
    used: set[str] = set()
    index = 0
    while index < len(lines):
        match = re.match(r"^([^\s#][^:]*):", lines[index])
        if not match:
            output.append(lines[index])
            index += 1
            continue
        key = match.group(1).strip()
        next_index = index + 1
        while next_index < len(lines) and (not lines[next_index].strip() or lines[next_index].startswith((" ", "\t"))):
            next_index += 1
        if key in updates:
            output.extend(f"{key}: {yaml_scalar(updates[key])}".splitlines())
            used.add(key)
        else:
            output.extend(lines[index:next_index])
        index = next_index
    for key, value in updates.items():
        if key not in used:
            output.extend(f"{key}: {yaml_scalar(value)}".splitlines())
    return "---\n" + "\n".join(output) + text[end:]


def markdown_section(text: str, heading: str) -> str:
    start = text.find(heading)
    if start == -1:
        return ""
    following = re.search(r"(?m)^## \d+\. ", text[start + len(heading) :])
    end = start + len(heading) + following.start() if following else len(text)
    return text[start:end].rstrip() + "\n\n"


def replace_markdown_section(text: str, heading: str, replacement: str) -> str:
    start = text.find(heading)
    if start == -1 or not replacement:
        return text
    following = re.search(r"(?m)^## \d+\. ", text[start + len(heading) :])
    end = start + len(heading) + following.start() if following else len(text)
    return text[:start] + replacement + text[end:]


def refresh_source_note_content(existing: str, fresh: str) -> str:
    fresh_frontmatter = parse_frontmatter(fresh)
    if fresh_frontmatter is None:
        raise ResearchWikiError("Generated source note has no valid YAML frontmatter.")
    updates = {key: fresh_frontmatter.get(key, "") for key in ZOTERO_CONTROLLED_SOURCE_FIELDS}
    updated = replace_frontmatter_fields(existing, updates)
    for heading in ("## 1. 文献基本信息", "## 6. Zotero 阅读注释"):
        updated = replace_markdown_section(updated, heading, markdown_section(fresh, heading))
    fresh_metadata = markdown_section(fresh, "## 2. MD 文件信息")
    for label in ("最后修改时间", "Zotero 条目修改时间", "Source fingerprint", "更新状态"):
        match = re.search(rf"(?m)^- {re.escape(label)}：.*$", fresh_metadata)
        if match:
            updated = re.sub(rf"(?m)^- {re.escape(label)}：.*$", match.group(0), updated, count=1)
    return updated


def find_source_note(knowledge_base_path: Path, item_key: str) -> Path | None:
    source_dir = knowledge_base_path / "sources"
    for path in sorted(source_dir.glob("*.md")) if source_dir.exists() else []:
        frontmatter = parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        if frontmatter and normalized_frontmatter_value(frontmatter.get("zotero_item_key")) == item_key:
            return path
    return None


def research_base_templates() -> dict[str, str]:
    common = """---
type: {note_type}
status: exploratory
evidence_status: unverified
created: {date}
last_updated: {date}
kb_promotion: false
related_kb_pages: []
supersedes:
promoted_at:
superseded_by:
decision_reason:
---
"""
    date = today()
    return {
        "conversation-note.md": common.format(note_type="conversation_note", date=date)
        + """# Conversation Note\n\n## 问题与背景\n\n## 工作设想\n\n## 待核验事项\n\n## 下一步\n""",
        "topic-exploration.md": common.format(note_type="topic_exploration", date=date)
        + """# Topic Exploration\n\n## 候选研究问题\n\n## 预期贡献与主要风险\n\n## 竞争解释与待核验文献\n\n## 下一步\n""",
        "method-prototype.md": common.format(note_type="method_prototype", date=date)
        + """# Method Prototype\n\n## 原型目标\n\n## 候选变量、模型或识别思路\n\n## 未核验假设与验证计划\n\n## 相关 Knowledge Base 页面\n""",
        "data-feasibility.md": common.format(note_type="data_feasibility", date=date)
        + """# Data Feasibility\n\n## 候选数据与分析单位\n\n## 字段、映射与样本可得性\n\n## 未核验限制\n\n## 下一步\n""",
        "design-alternative.md": common.format(note_type="design_alternative", date=date)
        + """# Design Alternative\n\n## 设计选项\n\n## 取舍与替代解释\n\n## 识别风险与待核验事项\n\n## 决策记录\n""",
    }


def research_base_readme(project_path: Path, research_base_path: Path) -> str:
    return f"""# Research Base

This folder stores exploratory research work for `{project_path.name}`. It is not a parallel literature library.

## Boundaries

- **Zotero** remains authoritative for bibliographic records, PDFs, attachments, annotations, collections, and tags.
- **Knowledge Base** stores traceable source notes, verified concepts, mature methods, and reusable claims.
- **Research Base** stores candidate questions, method prototypes, data-feasibility checks, design alternatives, discussion notes, and rejected paths that are not yet established conclusions.

## Operating Rules

- Every note must keep the required frontmatter, especially `status` and `evidence_status`.
- Link to Knowledge Base pages instead of duplicating source notes or Zotero read-state metadata.
- Update `index.md` and append `log.md` after creating, renaming, archiving, or promoting a note.
- Promotion requires explicit user instruction or project-`AGENTS.md` authorization. Verify the underlying evidence first, write only the reusable conclusion to the Knowledge Base, then keep this note with `status: promoted`, `kb_promotion: true`, `promoted_at`, and the target links.
- Preserve rejected, superseded, and promoted notes so that research decisions remain traceable. Set `decision_reason` for rejected work and `superseded_by` for replaced work.

Default location: `{research_base_path}`. Project `AGENTS.md` overrides this default when it declares a different path, schema, language, or promotion rule.
"""


def research_base_index_md() -> str:
    return """# Research Base Index

Exploratory material only. Evidence labels in each note determine whether it can be promoted.

## Conversation Notes

## Topic Exploration

## Method Prototypes

## Data Feasibility

## Design Alternatives

## Archived or Rejected
"""


def research_base_log_md() -> str:
    return f"""# Research Base Log

## [{today()}] init | Research Base

- Created the opt-in Research Base structure and templates.
"""


def project_config_path(project_path: Path) -> Path:
    return project_path / CONFIG_FILE


def load_project_config(project_path: Path) -> dict[str, Any]:
    config = dict(DEFAULT_PROJECT_CONFIG)
    path = project_config_path(project_path)
    if not path.exists():
        return config
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResearchWikiError(f"Invalid project config {path}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise ResearchWikiError(f"Project config must contain a JSON object: {path}")
    config.update(loaded)
    for key in ("knowledge_base_path", "research_base_path"):
        if not isinstance(config.get(key), str) or not str(config[key]).strip():
            raise ResearchWikiError(f"Project config field {key!r} must be a non-empty string.")
    return config


def ensure_project_config(project_path: Path, updates: dict[str, Any] | None = None) -> None:
    path = project_config_path(project_path)
    if path.exists():
        return
    config = dict(DEFAULT_PROJECT_CONFIG)
    if updates:
        config.update({key: value for key, value in updates.items() if value is not None})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def configured_path(project_path: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = project_path / path
    return path.resolve()


def resolve_knowledge_base_path(args: argparse.Namespace, project_path: Path | None = None) -> tuple[Path, Path]:
    project_path = project_path or resolve_project_path(args)
    override = getattr(args, "knowledge_base_path", None)
    value = override or str(load_project_config(project_path)["knowledge_base_path"])
    return project_path, configured_path(project_path, value)


def resolve_research_base_path(args: argparse.Namespace) -> tuple[Path, Path]:
    project_path = resolve_project_path(args)
    override = getattr(args, "research_base_path", None)
    value = override or str(load_project_config(project_path)["research_base_path"])
    return project_path, configured_path(project_path, value)


def load_research_base_schema(args: argparse.Namespace, project_path: Path) -> dict[str, list[str]]:
    merged: dict[str, Any] = {key: list(value) for key, value in DEFAULT_RESEARCH_BASE_SCHEMA.items()}
    config = load_project_config(project_path)
    schema_value = getattr(args, "research_base_schema", None) or config.get("research_base_schema_path")
    if schema_value:
        schema_path = configured_path(project_path, str(schema_value))
        try:
            custom = json.loads(schema_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ResearchWikiError(f"Invalid Research Base schema {schema_path}: {exc}") from exc
        if not isinstance(custom, dict):
            raise ResearchWikiError(f"Research Base schema must contain a JSON object: {schema_path}")
        merged.update(custom)
    for key in DEFAULT_RESEARCH_BASE_SCHEMA:
        value = merged.get(key)
        if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
            raise ResearchWikiError(f"Research Base schema field {key!r} must be a non-empty string list.")
    return {key: list(merged[key]) for key in DEFAULT_RESEARCH_BASE_SCHEMA}


def ensure_research_base(
    project_path: Path,
    research_base_path: Path,
    schema: dict[str, list[str]],
) -> None:
    research_base_path.mkdir(parents=True, exist_ok=True)
    for directory in schema["directories"]:
        (research_base_path / directory).mkdir(exist_ok=True)
    write_if_missing(research_base_path / "README.md", research_base_readme(project_path, research_base_path))
    write_if_missing(research_base_path / "index.md", research_base_index_md())
    write_if_missing(research_base_path / "log.md", research_base_log_md())
    if "_templates" in schema["directories"]:
        for filename, content in research_base_templates().items():
            write_if_missing(research_base_path / "_templates" / filename, content)


def parse_yaml_value(raw: str, block_lines: list[str] | None = None) -> Any:
    value = raw.strip()
    if block_lines is not None:
        if value in {"|", ">"}:
            separator = "\n" if value == "|" else " "
            return separator.join(line.strip() for line in block_lines).strip()
        return [parse_yaml_value(line) for line in block_lines]
    if not value or value in {"null", "Null", "NULL", "~"}:
        return ""
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if value.startswith("[") and value.endswith("]"):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_yaml_value(part.strip()) for part in inner.split(",")]
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        if value[0] == '"':
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass
        return value[1:-1]
    return value


def parse_frontmatter(text: str) -> dict[str, Any] | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    result: dict[str, Any] = {}
    lines = text[4:end].splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        match = re.match(r"^([^\s#][^:]*):(?:\s*(.*))?$", line)
        if not match:
            index += 1
            continue
        key = match.group(1).strip()
        raw = (match.group(2) or "").strip()
        index += 1
        indented: list[str] = []
        while index < len(lines) and (not lines[index].strip() or lines[index].startswith((" ", "\t"))):
            child = lines[index]
            if child.strip():
                indented.append(child.strip())
            index += 1
        if raw in {"|", ">"}:
            result[key] = parse_yaml_value(raw, indented)
        elif not raw and indented and all(line.startswith("- ") for line in indented):
            result[key] = parse_yaml_value(raw, [line[2:].strip() for line in indented])
        else:
            result[key] = parse_yaml_value(raw)
    return result


def normalized_frontmatter_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip()


def nonempty_list_value(value: Any) -> bool:
    if isinstance(value, list):
        return any(normalized_frontmatter_value(item) for item in value)
    return bool(normalized_frontmatter_value(value))


def wikilink_targets(text: str) -> set[str]:
    return {match.strip() for match in re.findall(r"\[\[([^\]|#]+)", text)}


def research_base_note_paths(research_base_path: Path) -> list[Path]:
    return sorted(
        path
        for path in research_base_path.rglob("*.md")
        if "_templates" not in path.relative_to(research_base_path).parts
        and path not in {research_base_path / "README.md", research_base_path / "index.md", research_base_path / "log.md"}
    )


def research_base_check_result(
    project_path: Path,
    research_base_path: Path,
    schema: dict[str, list[str]],
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    def error(code: str, message: str, path: Path | None = None) -> None:
        entry = {"code": code, "message": message}
        if path:
            entry["path"] = str(path.relative_to(research_base_path))
        errors.append(entry)

    if not research_base_path.exists():
        error("missing_research_base", "Research Base directory does not exist.")
        return {
            "project_path": str(project_path),
            "research_base_path": str(research_base_path),
            "valid": False,
            "note_count": 0,
            "errors": errors,
            "warnings": warnings,
            "findings": errors,
        }

    for name in ("README.md", "index.md", "log.md"):
        if not (research_base_path / name).is_file():
            error("missing_navigation_file", f"Missing required file: {name}.")
    for directory in schema["directories"]:
        if not (research_base_path / directory).is_dir():
            error("missing_directory", f"Missing required directory: {directory}.")

    index_path = research_base_path / "index.md"
    index_text = index_path.read_text(encoding="utf-8", errors="replace") if index_path.exists() else ""
    index_targets = wikilink_targets(index_text)
    notes = research_base_note_paths(research_base_path)
    stem_counts: dict[str, int] = {}
    for note_path in notes:
        stem_counts[note_path.stem] = stem_counts.get(note_path.stem, 0) + 1
    for note_path in notes:
        rel = note_path.relative_to(research_base_path)
        text = note_path.read_text(encoding="utf-8", errors="replace")
        frontmatter = parse_frontmatter(text)
        if frontmatter is None:
            error("missing_frontmatter", "Note has no valid YAML frontmatter.", note_path)
            continue

        missing_fields = [field for field in schema["required_fields"] if field not in frontmatter]
        if missing_fields:
            error("missing_required_fields", f"Missing required fields: {', '.join(missing_fields)}.", note_path)

        note_type = normalized_frontmatter_value(frontmatter.get("type"))
        status = normalized_frontmatter_value(frontmatter.get("status"))
        evidence_status = normalized_frontmatter_value(frontmatter.get("evidence_status"))
        if note_type not in set(schema["note_types"]):
            error("invalid_type", f"Unsupported Research Base type: {note_type or '<empty>'}.", note_path)
        if status not in set(schema["statuses"]):
            error("invalid_status", f"Unsupported status: {status or '<empty>'}.", note_path)
        if evidence_status not in set(schema["evidence_statuses"]):
            error("invalid_evidence_status", f"Unsupported evidence_status: {evidence_status or '<empty>'}.", note_path)

        if note_type == "source" or any(
            field in frontmatter for field in ("zotero_item_key", "zotero_uri", "citation_key", "source_fingerprint")
        ):
            error("duplicate_source_note", "Research Base must link to, not duplicate, Zotero or Knowledge Base source notes.", note_path)

        promoted = status == "promoted"
        kb_promotion = normalized_frontmatter_value(frontmatter.get("kb_promotion")) == "true"
        related_pages = nonempty_list_value(frontmatter.get("related_kb_pages"))
        if promoted and evidence_status != "verified":
            error("promotion_without_verified_evidence", "Promoted note must have evidence_status: verified.", note_path)
        if promoted and not kb_promotion:
            error("promotion_flag_missing", "Promoted note must set kb_promotion: true.", note_path)
        if promoted and not related_pages:
            error("promotion_link_missing", "Promoted note must link to its Knowledge Base destination.", note_path)
        if promoted and not normalized_frontmatter_value(frontmatter.get("promoted_at")):
            error("promotion_date_missing", "Promoted note must set promoted_at.", note_path)
        if kb_promotion and not promoted:
            error("promotion_status_mismatch", "kb_promotion: true requires status: promoted.", note_path)
        if status == "superseded" and not normalized_frontmatter_value(frontmatter.get("superseded_by")):
            error("superseded_link_missing", "Superseded note must set superseded_by.", note_path)
        if status == "rejected" and not normalized_frontmatter_value(frontmatter.get("decision_reason")):
            error("decision_reason_missing", "Rejected note must record decision_reason.", note_path)

        note_link = rel.with_suffix("").as_posix()
        exact_linked = note_link in index_targets
        unique_stem_linked = stem_counts[note_path.stem] == 1 and note_path.stem in index_targets
        if not exact_linked and not unique_stem_linked:
            error("unindexed_note", "Note is not linked from Research Base index.md with an unambiguous path.", note_path)

    return {
        "project_path": str(project_path),
        "research_base_path": str(research_base_path),
        "valid": not errors,
        "note_count": len(notes),
        "errors": errors,
        "warnings": warnings,
        "findings": errors,
    }


def ensure_project(
    project_path: Path,
    knowledge_base_path: Path,
    collection_key: str | None,
    collection_name: str | None,
    config_updates: dict[str, Any] | None = None,
) -> None:
    project_path.mkdir(parents=True, exist_ok=True)
    ensure_project_config(project_path, config_updates)
    knowledge_base_path.mkdir(parents=True, exist_ok=True)
    for directory in WIKI_DIRS:
        (knowledge_base_path / directory).mkdir(exist_ok=True)
    (project_path / CACHE_DIR / "items").mkdir(parents=True, exist_ok=True)
    (project_path / CACHE_DIR / "fulltext").mkdir(parents=True, exist_ok=True)
    (project_path / CACHE_DIR / "collections").mkdir(parents=True, exist_ok=True)

    write_if_missing(project_path / "AGENTS.md", project_agents_md(collection_key, collection_name))
    write_if_missing(knowledge_base_path / "index.md", project_index_md(collection_key, collection_name))
    write_if_missing(knowledge_base_path / "log.md", project_log_md())


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
- Use `.research-wiki/config.json` for machine-readable Knowledge Base and Research Base paths. CLI overrides apply only to the current command.

## Structure

- `sources/`: one note per Zotero item.
- `concepts/`: concepts, constructs, mechanisms, theories, variables.
- `themes/`: literature streams and evolving research narratives.
- `methods/`: data, measurements, empirical designs, identification strategies.
- `claims/`: propositions, contradictions, boundary conditions, evidence status.
- `index.md`: content index updated after every meaningful wiki change.
- `log.md`: append-only chronological record.
- `.research-wiki/cache/`: generated Zotero metadata and full text. Do not manually edit.

## Research Base (Opt-In Only)

- Create or use `Research Base/` only when this project explicitly enables it or the user asks to preserve exploratory research work.
- Keep candidate topics, method prototypes, data feasibility checks, design alternatives, and rejected paths in Research Base with explicit evidence labels.
- Do not put Zotero-backed source notes or source-note read-state fields in Research Base. Link to Knowledge Base pages instead.
- Before the first Research Base write, state its exact path and get user confirmation. Project rules may override the default path, language, schema, and promotion conditions.
- Promote content to this wiki only with explicit user instruction or project authorization after verification. Keep the Research Base decision trail and update both indexes and logs.

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
- Keep `metadata_status` separate from workflow `status`; use `refresh-source-note` for Zotero metadata or annotation changes.
- Keep `source_route`, `verification_status`, and `read_level` as separate provenance, verification, and evidence-depth dimensions.
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


def add_source_to_index(knowledge_base_path: Path, source_path: Path, item: dict[str, Any]) -> None:
    index_path = knowledge_base_path / "index.md"
    if not index_path.exists():
        write_if_missing(index_path, project_index_md(None, None))
    text = index_path.read_text(encoding="utf-8")
    rel = source_path.relative_to(knowledge_base_path)
    stem = source_path.stem
    data = item.get("data", item)
    title = str(data.get("title") or stem)
    year = year_from_item(data)
    link = rel.with_suffix("").as_posix()
    entry = f"- [[{link}]] - {year}; {title}; Zotero `{item.get('key') or data.get('key')}`"
    if link in wikilink_targets(text):
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


def append_log(knowledge_base_path: Path, kind: str, title: str, bullets: list[str]) -> None:
    log_path = knowledge_base_path / "log.md"
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
    project_path = resolve_project_path(args)
    require_yes(args, project_path)
    collection = None
    if args.collection_key or args.collection_name:
        collections = all_collections()
        collection = find_collection(collections, args.collection_key, args.collection_name)
    existing_config = load_project_config(project_path)
    knowledge_value = args.knowledge_base_path or existing_config["knowledge_base_path"]
    research_base_value = args.research_base_path or existing_config["research_base_path"]
    knowledge_base_path = configured_path(project_path, str(knowledge_value))
    ensure_project(
        project_path,
        knowledge_base_path,
        collection.get("key") if collection else args.collection_key,
        collection.get("data", {}).get("name") if collection else args.collection_name,
        {
            "knowledge_base_path": knowledge_value,
            "research_base_path": research_base_value,
        },
    )
    print(
        json.dumps(
            {"project_path": str(project_path), "knowledge_base_path": str(knowledge_base_path), "created": True},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def command_init_research_base(args: argparse.Namespace) -> int:
    project_path, research_base_path = resolve_research_base_path(args)
    require_yes(args, research_base_path)
    ensure_project_config(project_path, {"research_base_path": args.research_base_path})
    schema = load_research_base_schema(args, project_path)
    ensure_research_base(project_path, research_base_path, schema)
    print(
        json.dumps(
            {
                "project_path": str(project_path),
                "research_base_path": str(research_base_path),
                "created": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def command_export_collection(args: argparse.Namespace) -> int:
    collections = all_collections()
    collection = find_collection(collections, args.collection_key, args.collection_name)
    collection_key = str(collection["key"])
    collection_name = str(collection.get("data", {}).get("name") or collection_key)
    project_path, knowledge_base_path = resolve_knowledge_base_path(args)
    require_yes(args, project_path)
    ensure_project(project_path, knowledge_base_path, collection_key, collection_name)

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
    project_path, knowledge_base_path = resolve_knowledge_base_path(args)
    require_yes(args, project_path)
    if args.deep_read_completed and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.deep_read_completed):
        raise ResearchWikiError("--deep-read-completed must use YYYY-MM-DD.")
    if args.deep_read_completed and args.read_level != "fulltext":
        raise ResearchWikiError("--deep-read-completed requires --read-level fulltext.")
    if args.priority == "exclude" and (args.need_fulltext_read or args.deep_read_completed):
        raise ResearchWikiError("exclude records cannot require full-text reading or carry a deep-read completion date.")
    ensure_project(project_path, knowledge_base_path, None, None)
    item = item_by_key(args.item_key)
    notes_and_annotations = child_notes_and_annotations(args.item_key)
    project_name = args.project_name or project_path.name
    content = render_source_note(
        item,
        notes_and_annotations,
        project_name,
        args.priority,
        boss_category=args.boss_category or "",
        boss_screening_reason=args.boss_screening_reason or "",
        pdf_status=args.pdf_status,
        project_use=args.project_use or "",
        need_fulltext_read=args.need_fulltext_read,
        read_level=args.read_level,
        deep_read_completed=args.deep_read_completed or "",
        source_route=args.source_route,
        verification_status=args.verification_status,
    )
    source_path = knowledge_base_path / "sources" / source_note_name(item)
    if source_path.exists() and not args.overwrite:
        raise ResearchWikiError(f"Source note already exists: {source_path}. Use refresh-source-note for safe metadata updates.")
    if source_path.exists() and args.overwrite and not args.confirm_destructive_overwrite:
        raise ResearchWikiError(
            "--overwrite is deprecated because it replaces manual research content. "
            "Use refresh-source-note, or add --confirm-destructive-overwrite for an intentional full replacement."
        )
    source_path.write_text(content, encoding="utf-8")
    add_source_to_index(knowledge_base_path, source_path, item)
    append_log(
        knowledge_base_path,
        "ingest",
        str(item.get("data", {}).get("title") or args.item_key),
        [
            f"Created source note `{source_path.relative_to(knowledge_base_path)}`.",
            f"Zotero item key: `{args.item_key}`.",
            f"AR read priority: `{args.priority}`.",
        ],
    )
    print(
        json.dumps(
            {
                "project_path": str(project_path),
                "knowledge_base_path": str(knowledge_base_path),
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


def command_refresh_source_note(args: argparse.Namespace) -> int:
    project_path, knowledge_base_path = resolve_knowledge_base_path(args)
    require_yes(args, project_path)
    source_path = find_source_note(knowledge_base_path, args.item_key)
    if source_path is None:
        raise ResearchWikiError(f"No source note with zotero_item_key {args.item_key} under {knowledge_base_path / 'sources'}.")
    item = item_by_key(args.item_key)
    notes_and_annotations = child_notes_and_annotations(args.item_key)
    existing = source_path.read_text(encoding="utf-8", errors="replace")
    frontmatter = parse_frontmatter(existing) or {}
    priority = normalized_frontmatter_value(frontmatter.get("deep_read_priority")) or "low"
    if priority not in READ_SCOPES:
        raise ResearchWikiError(f"Existing source note has unsupported deep_read_priority: {priority}.")
    fresh = render_source_note(
        item,
        notes_and_annotations,
        normalized_frontmatter_value(frontmatter.get("project")) or project_path.name,
        priority,
    )
    refreshed = refresh_source_note_content(existing, fresh)
    source_path.write_text(refreshed, encoding="utf-8")
    append_log(
        knowledge_base_path,
        "refresh",
        str(item.get("data", {}).get("title") or args.item_key),
        [
            f"Refreshed Zotero-controlled metadata and annotations in `{source_path.relative_to(knowledge_base_path)}`.",
            "Preserved read state and manually authored research sections.",
        ],
    )
    print(
        json.dumps(
            {
                "project_path": str(project_path),
                "knowledge_base_path": str(knowledge_base_path),
                "source_note": str(source_path),
                "item_key": args.item_key,
                "refreshed": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def markdown_pages(knowledge_base_path: Path, excluded_roots: list[Path] | None = None) -> list[Path]:
    excluded = [path.resolve() for path in (excluded_roots or [])]
    return sorted(
        path
        for path in knowledge_base_path.rglob("*.md")
        if ".research-wiki" not in path.relative_to(knowledge_base_path).parts
        and not any(path_is_within(path.resolve(), root) for root in excluded)
    )


def command_check(args: argparse.Namespace) -> int:
    project_path, knowledge_base_path = resolve_knowledge_base_path(args)
    if not project_path.exists():
        raise ResearchWikiError(f"Project path does not exist: {project_path}")
    if not knowledge_base_path.exists():
        raise ResearchWikiError(f"Knowledge Base path does not exist: {knowledge_base_path}")
    config = load_project_config(project_path)
    research_base_value = args.research_base_path or str(config["research_base_path"])
    research_base_path = configured_path(project_path, research_base_value)
    cache = project_path / CACHE_DIR
    item_files = sorted((cache / "items").glob("*.json")) if (cache / "items").exists() else []
    fulltext_files = sorted((cache / "fulltext").glob("*.txt")) if (cache / "fulltext").exists() else []
    source_files = sorted((knowledge_base_path / "sources").rglob("*.md")) if (knowledge_base_path / "sources").exists() else []
    pages = markdown_pages(knowledge_base_path, [research_base_path])
    allowed_roots = set(WIKI_DIRS)
    special = {"AGENTS.md", "README.md", "index.md", "log.md"}
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    def add_error(code: str, message: str, path: str | None = None, **details: Any) -> None:
        entry: dict[str, Any] = {"code": code, "message": message}
        if path:
            entry["path"] = path
        entry.update(details)
        errors.append(entry)

    def add_warning(code: str, message: str, path: str | None = None, **details: Any) -> None:
        entry: dict[str, Any] = {"code": code, "message": message}
        if path:
            entry["path"] = path
        entry.update(details)
        warnings.append(entry)

    for page in pages:
        rel = page.relative_to(knowledge_base_path)
        if len(rel.parts) == 1 and rel.name in special:
            continue
        if rel.parts[0] not in allowed_roots:
            add_error("orphan_location", "Markdown page is outside the Knowledge Base directory contract.", str(rel))

    index_path = knowledge_base_path / "index.md"
    index_text = index_path.read_text(encoding="utf-8") if index_path.exists() else ""
    index_targets = wikilink_targets(index_text)
    stem_counts: dict[str, int] = {}
    indexable_pages: list[Path] = []
    for page in pages:
        rel = page.relative_to(knowledge_base_path)
        if len(rel.parts) == 1 and rel.name in special:
            continue
        indexable_pages.append(page)
        stem_counts[page.stem] = stem_counts.get(page.stem, 0) + 1
    for page in indexable_pages:
        rel = page.relative_to(knowledge_base_path)
        stem = page.stem
        relative_link = rel.with_suffix("").as_posix()
        exact_linked = relative_link in index_targets
        unique_stem_linked = stem_counts[stem] == 1 and stem in index_targets
        if not exact_linked and not unique_stem_linked:
            add_error("unindexed_page", "Page is not linked from index.md with an unambiguous path.", str(rel))

    source_by_key: dict[str, tuple[Path, dict[str, Any]]] = {}
    for source_file in source_files:
        rel = str(source_file.relative_to(knowledge_base_path))
        text = source_file.read_text(encoding="utf-8", errors="replace")
        frontmatter = parse_frontmatter(text)
        if frontmatter is None:
            add_error("missing_frontmatter", "Source note has no valid YAML frontmatter.", rel)
            continue
        missing_fields = [
            field
            for field in (
                "zotero_item_key",
                "status",
                "deep_read_priority",
                "need_fulltext_read",
                "read_level",
                "deep_read_completed",
            )
            if field not in frontmatter
        ]
        if missing_fields:
            add_error("missing_read_state", "Source note is missing required trace/read-state fields.", rel, missing=missing_fields)
        missing_dimensions = [field for field in ("source_route", "verification_status", "metadata_status") if field not in frontmatter]
        if missing_dimensions:
            add_warning(
                "missing_source_dimensions",
                "Legacy source note is missing provenance, verification, or metadata-freshness fields.",
                rel,
                missing=missing_dimensions,
            )
        priority = normalized_frontmatter_value(frontmatter.get("deep_read_priority"))
        if priority and priority not in READ_SCOPES:
            add_error("invalid_deep_read_priority", f"Unsupported deep_read_priority: {priority}.", rel)
        status = normalized_frontmatter_value(frontmatter.get("status"))
        if status and status not in SOURCE_STATUSES:
            add_error("invalid_source_status", f"Unsupported source status: {status}.", rel)
        read_level = normalized_frontmatter_value(frontmatter.get("read_level"))
        if read_level and read_level not in READ_LEVEL_VALUES:
            add_error("invalid_read_level", f"Unsupported read_level: {read_level}.", rel)
        source_route = normalized_frontmatter_value(frontmatter.get("source_route"))
        if source_route and source_route not in SOURCE_ROUTES:
            add_error("invalid_source_route", f"Unsupported source_route: {source_route}.", rel)
        verification_status = normalized_frontmatter_value(frontmatter.get("verification_status"))
        if verification_status and verification_status not in VERIFICATION_STATUSES:
            add_error("invalid_verification_status", f"Unsupported verification_status: {verification_status}.", rel)
        boss_category = normalized_frontmatter_value(frontmatter.get("boss_category"))
        if boss_category and boss_category not in BOSS_CATEGORIES:
            add_error("invalid_boss_category", f"Unsupported boss_category: {boss_category}.", rel)
        pdf_status = normalized_frontmatter_value(frontmatter.get("pdf_status"))
        if pdf_status and pdf_status not in PDF_STATUSES:
            add_error("invalid_pdf_status", f"Unsupported pdf_status: {pdf_status}.", rel)
        metadata_status = normalized_frontmatter_value(frontmatter.get("metadata_status"))
        if metadata_status and metadata_status not in METADATA_STATUSES:
            add_error("invalid_metadata_status", f"Unsupported metadata_status: {metadata_status}.", rel)
        need_fulltext = normalized_frontmatter_value(frontmatter.get("need_fulltext_read")) == "true"
        completed = normalized_frontmatter_value(frontmatter.get("deep_read_completed"))
        if status == "deep_read_done" and (need_fulltext or read_level != "fulltext" or not completed):
            add_error(
                "inconsistent_deep_read_done",
                "deep_read_done requires need_fulltext_read: false, read_level: fulltext, and a completion date.",
                rel,
            )
        if status == "deep_read_skip" and need_fulltext:
            add_error("inconsistent_deep_read_skip", "deep_read_skip cannot require full-text reading.", rel)
        item_key = normalized_frontmatter_value(frontmatter.get("zotero_item_key"))
        if item_key:
            if item_key in source_by_key:
                add_error("duplicate_source_key", f"Multiple source notes use Zotero item key {item_key}.", rel)
            else:
                source_by_key[item_key] = (source_file, frontmatter)

    fulltext_by_item = {p.name.split("__", 1)[0] for p in fulltext_files}
    for item_file in item_files:
        key = item_file.stem
        if key not in source_by_key:
            add_error("missing_source_note", f"Cached Zotero item {key} has no source note.", item_key=key)
            continue
        source_file, frontmatter = source_by_key[key]
        rel = str(source_file.relative_to(knowledge_base_path))
        if normalized_frontmatter_value(frontmatter.get("need_fulltext_read")) == "true" and key not in fulltext_by_item:
            add_warning("missing_required_fulltext", "Source note requires further reading but no indexed full text is cached.", rel, item_key=key)
        try:
            cached = json.loads(item_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            add_error("invalid_cache_item", f"Could not read cached Zotero item: {exc}", str(item_file.relative_to(project_path)))
            continue
        cache_fingerprint = normalized_frontmatter_value(cached.get("summary", {}).get("source_fingerprint"))
        note_fingerprint = normalized_frontmatter_value(frontmatter.get("source_fingerprint"))
        if cache_fingerprint and note_fingerprint and cache_fingerprint != note_fingerprint:
            add_warning("stale_source_fingerprint", "Zotero metadata or annotations changed; refresh the source note.", rel, item_key=key)

    result = {
        "project_path": str(project_path),
        "knowledge_base_path": str(knowledge_base_path),
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "stats": {
            "cache_items": len(item_files),
            "fulltext_files": len(fulltext_files),
            "source_notes": len(source_files),
            "wiki_pages": len(pages),
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] or args.report_only else 1


def command_check_research_base(args: argparse.Namespace) -> int:
    project_path, research_base_path = resolve_research_base_path(args)
    schema = load_research_base_schema(args, project_path)
    result = research_base_check_result(project_path, research_base_path, schema)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] or args.report_only else 1


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
    init.add_argument(
        "--knowledge-base-path",
        help="Knowledge Base path, absolute or relative to the project; defaults to the project root.",
    )
    init.add_argument(
        "--research-base-path",
        help="Record a Research Base path in config without creating it.",
    )
    init.add_argument("--yes", action="store_true", help="Confirm writing project files.")
    init.set_defaults(func=command_init_project)

    init_research_base = sub.add_parser(
        "init-research-base",
        help="Create the opt-in Research Base structure for exploratory project work.",
    )
    init_research_base.add_argument("--project", help="Project folder name under --vault.")
    init_research_base.add_argument("--project-path", help="Exact project path.")
    init_research_base.add_argument("--vault", default=str(DEFAULT_VAULT))
    init_research_base.add_argument(
        "--research-base-path",
        help="Research Base path, absolute or relative to the project; defaults to the configured Research Base path.",
    )
    init_research_base.add_argument(
        "--research-base-schema",
        help="Project-level Research Base schema JSON, absolute or relative to the project.",
    )
    init_research_base.add_argument("--yes", action="store_true", help="Confirm writing Research Base files.")
    init_research_base.set_defaults(func=command_init_research_base)

    export = sub.add_parser("export-collection", help="Export Zotero collection metadata and indexed full text caches.")
    export.add_argument("--collection-key")
    export.add_argument("--collection-name")
    export.add_argument("--project", help="Project folder name under --vault.")
    export.add_argument("--project-path", help="Exact project path.")
    export.add_argument("--vault", default=str(DEFAULT_VAULT))
    export.add_argument("--knowledge-base-path", help="Override the configured Knowledge Base path for this command.")
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
    source_note.add_argument("--knowledge-base-path", help="Override the configured Knowledge Base path for this command.")
    source_note.add_argument(
        "--priority",
        "--deep-read-priority",
        dest="priority",
        choices=sorted(READ_SCOPES),
        default="low",
    )
    source_note.add_argument("--project-name", help="Project label to store in source note frontmatter.")
    source_note.add_argument("--boss-category", choices=sorted(BOSS_CATEGORIES))
    source_note.add_argument("--boss-screening-reason")
    source_note.add_argument("--pdf-status", choices=sorted(PDF_STATUSES), default="unknown")
    source_note.add_argument("--project-use")
    fulltext_group = source_note.add_mutually_exclusive_group()
    fulltext_group.add_argument("--need-fulltext-read", dest="need_fulltext_read", action="store_true")
    fulltext_group.add_argument("--no-need-fulltext-read", dest="need_fulltext_read", action="store_false")
    source_note.set_defaults(need_fulltext_read=None)
    source_note.add_argument("--read-level", choices=sorted(READ_LEVEL_VALUES), default="abstract")
    source_note.add_argument("--deep-read-completed")
    source_note.add_argument("--source-route", choices=sorted(SOURCE_ROUTES), default="unknown")
    source_note.add_argument("--verification-status", choices=sorted(VERIFICATION_STATUSES), default="unverified")
    source_note.add_argument("--overwrite", action="store_true", help="Deprecated destructive overwrite; prefer refresh-source-note.")
    source_note.add_argument(
        "--confirm-destructive-overwrite",
        action="store_true",
        help="Second confirmation required with --overwrite to replace the entire source note.",
    )
    source_note.add_argument("--yes", action="store_true", help="Confirm writing the source note.")
    source_note.set_defaults(func=command_source_note)

    refresh_source_note = sub.add_parser(
        "refresh-source-note",
        help="Safely refresh Zotero-controlled metadata, fingerprint, and annotations while preserving research content.",
    )
    refresh_source_note.add_argument("item_key", help="Zotero item key already present in source-note frontmatter.")
    refresh_source_note.add_argument("--project", help="Project folder name under --vault.")
    refresh_source_note.add_argument("--project-path", help="Exact project path.")
    refresh_source_note.add_argument("--vault", default=str(DEFAULT_VAULT))
    refresh_source_note.add_argument("--knowledge-base-path", help="Override the configured Knowledge Base path for this command.")
    refresh_source_note.add_argument("--yes", action="store_true", help="Confirm refreshing the source note.")
    refresh_source_note.set_defaults(func=command_refresh_source_note)

    check = sub.add_parser("check", help="Check project cache/wiki consistency.")
    check.add_argument("--project", help="Project folder name under --vault.")
    check.add_argument("--project-path", help="Exact project path.")
    check.add_argument("--vault", default=str(DEFAULT_VAULT))
    check.add_argument("--knowledge-base-path", help="Override the configured Knowledge Base path for this command.")
    check.add_argument("--research-base-path", help="Override the configured Research Base exclusion path for this command.")
    check.add_argument("--report-only", action="store_true", help="Always exit successfully while retaining diagnostics.")
    check.set_defaults(func=command_check)

    check_research_base = sub.add_parser(
        "check-research-base",
        help="Validate Research Base structure, note metadata, navigation, and promotion boundaries.",
    )
    check_research_base.add_argument("--project", help="Project folder name under --vault.")
    check_research_base.add_argument("--project-path", help="Exact project path.")
    check_research_base.add_argument("--vault", default=str(DEFAULT_VAULT))
    check_research_base.add_argument(
        "--research-base-path",
        help="Research Base path, absolute or relative to the project; defaults to the configured Research Base path.",
    )
    check_research_base.add_argument(
        "--research-base-schema",
        help="Project-level Research Base schema JSON, absolute or relative to the project.",
    )
    check_research_base.add_argument("--report-only", action="store_true", help="Always exit successfully while retaining diagnostics.")
    check_research_base.set_defaults(func=command_check_research_base)
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
