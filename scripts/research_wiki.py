#!/usr/bin/env python3
"""Helper for Zotero-backed Obsidian research wiki projects."""

from __future__ import annotations

import argparse
import datetime as dt
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


class ResearchWikiError(RuntimeError):
    pass


def today() -> str:
    return dt.date.today().isoformat()


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


def child_attachments(item_key: str) -> list[dict[str, Any]]:
    children = paged_json(f"{USER_PREFIX}/items/{item_key}/children", {"include": "data"})
    return [child for child in children if child.get("data", {}).get("itemType") == "attachment"]


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
        summary = item_summary(item)
        summary["attachments"] = [
            {
                "key": attachment.get("key"),
                "title": attachment.get("data", {}).get("title"),
                "filename": attachment.get("data", {}).get("filename"),
                "contentType": attachment.get("data", {}).get("contentType"),
            }
            for attachment in attachments
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
    fulltext_by_item = {p.name.split("__", 1)[0] for p in fulltext_files}
    for item_file in item_files:
        key = item_file.stem
        if key not in source_text:
            missing_source_notes.append(key)
        if key not in fulltext_by_item:
            missing_fulltext.append(key)

    result = {
        "project_path": str(project_path),
        "cache_items": len(item_files),
        "fulltext_files": len(fulltext_files),
        "source_notes": len(source_files),
        "missing_source_notes": missing_source_notes,
        "missing_fulltext": missing_fulltext,
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
