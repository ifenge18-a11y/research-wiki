---
name: research-wiki
description: Build and maintain Obsidian research wikis from Zotero collections using the LLM Wiki pattern. Use when Codex needs to read downloaded Zotero literature, create or update a local Obsidian project knowledge base, ingest papers into bilingual source notes, synthesize concepts/themes/methods/claims, update index/log files, or lint a research wiki for stale claims, missing links, and missing full text.
---

# Research Wiki

Use this skill to turn a Zotero collection into a persistent Obsidian research wiki. Treat Zotero as the read-only raw source layer, Obsidian Markdown as the maintained wiki layer, and the project `AGENTS.md` as the local schema.

## Quick Start

Helper script:

```bash
python3 ~/.codex/skills/research-wiki/scripts/research_wiki.py <command>
```

Start every workflow with:

```bash
python3 ~/.codex/skills/research-wiki/scripts/research_wiki.py status
python3 ~/.codex/skills/research-wiki/scripts/research_wiki.py collections
```

Default vault path: `/Users/feng/Documents/Obsidian Vault`. Before writing there, state the exact project path and get user confirmation. The helper also requires `--yes` for write commands.

## Workflow

1. Identify the Zotero collection by name or key. Prefer one collection per Obsidian project; parent collections may be exported recursively.
2. Initialize the project skeleton:

```bash
python3 ~/.codex/skills/research-wiki/scripts/research_wiki.py init-project \
  --project "ESG CSR" \
  --collection-key VMCF3H43 \
  --yes
```

3. Export Zotero metadata and indexed full text into `.research-wiki/cache/`:

```bash
python3 ~/.codex/skills/research-wiki/scripts/research_wiki.py export-collection \
  --collection-key VMCF3H43 \
  --project-path "/Users/feng/Documents/Obsidian Vault/ESG CSR" \
  --yes
```

4. Read `AGENTS.md` inside the project, then read the exported cache for the target item(s). Write or update:
   - `sources/<year>-<first-author>-<short-title>.md`
   - relevant pages in `concepts/`, `themes/`, `methods/`, and `claims/`
   - `index.md`
   - `log.md`
5. For a Zotero-backed empirical-accounting source note, use the helper to create the initial source page from Zotero metadata, abstract, notes, and annotations:

```bash
python3 ~/.codex/skills/research-wiki/scripts/research_wiki.py source-note \
  ITEMKEY \
  --project-path "/Users/feng/Documents/Obsidian Vault/ESG CSR" \
  --priority low \
  --yes
```

6. Run a health check after meaningful updates:

```bash
python3 ~/.codex/skills/research-wiki/scripts/research_wiki.py check \
  --project-path "/Users/feng/Documents/Obsidian Vault/ESG CSR"
```

## Writing Rules

- Write wiki pages in bilingual form: Chinese synthesis first, preserving English titles, constructs, methods, variable names, and quote-adjacent technical terms.
- Use Zotero item keys as stable source identifiers. Distinguish them from BibTeX keys if both appear.
- Preserve Zotero traceability in source pages: `zotero_item_key`, `zotero_uri`, `citation_key`, `zotero_modified`, and `source_fingerprint`.
- Use AR reading priority in source pages: `high` for full text, `medium` for abstract/introduction/research design/conclusion, `low` for abstract-only screening, and `exclude` for no read.
- Keep raw source claims tied to source notes. Put cross-paper synthesis in concept/theme/method/claim pages.
- Update `index.md` whenever adding, renaming, or materially changing wiki pages.
- Append to `log.md` for every ingest, query answer filed back into the wiki, and lint/check pass.
- Prefer one-source-at-a-time ingestion when the user is actively supervising; use batches only when the user asks for bulk processing.
- File useful answers back into the wiki instead of leaving them only in chat when they add durable research value.

## Zotero Safety

- Do not modify Zotero items, collections, PDFs, attachments, or tags.
- Use Zotero local API read routes only. The helper uses `http://127.0.0.1:23119/api/users/0/...`.
- Retrieve full text only for downloaded/indexed attachment content needed for the task.
- If full text is missing, record the blocker in `log.md` and ask whether to inspect, download, or extract the attachment. Do not fabricate the paper content from metadata.

## Resources

- Read `references/project-schema.md` when creating or updating project wiki pages.
- Use `scripts/research_wiki.py` for repeatable Zotero reads, project skeleton creation, cache export, and wiki health checks.
