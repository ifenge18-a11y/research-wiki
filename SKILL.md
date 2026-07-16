---
name: research-wiki
description: Build and maintain Obsidian research wikis from Zotero collections using the LLM Wiki pattern, with an optional exploratory Research Base and optional Obsidian Bases/CLI validation. Use when Codex needs to read downloaded Zotero literature, create or update a local Obsidian project knowledge base, ingest papers into bilingual source notes, synthesize concepts/themes/methods/claims, maintain Research Base prototypes, create project-scoped dynamic views, or lint a research wiki for stale metadata, missing links, and missing full text.
metadata:
  version: "0.3.0"
---

# Research Wiki

Use this skill to turn a Zotero collection into a persistent Obsidian research wiki. Treat Zotero as the read-only raw source layer, the Knowledge Base as the maintained and evidence-grounded wiki layer, and the project `AGENTS.md` as the local schema. When explicitly enabled, use a separate Research Base for exploratory research work that is not yet a stable knowledge claim.

## Quick Start

Helper script:

```bash
python3 ~/.codex/skills/research-wiki/scripts/research_wiki.py <command>
```

For Zotero-backed workflows, start with:

```bash
python3 ~/.codex/skills/research-wiki/scripts/research_wiki.py status
python3 ~/.codex/skills/research-wiki/scripts/research_wiki.py collections
```

Research Base-only commands and `init-project` without a collection are Zotero-independent; do not run Zotero preflight for them.

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

4. Read `AGENTS.md` inside the project, then read the exported cache for the target item(s). Treat project-specific source-note schema, read-state rules, and Zotero safety rules as binding. Write or update:
   - `<knowledge_base_path>/sources/<year>-<first-author>-<short-title>.md`
   - relevant pages in `concepts/`, `themes/`, `methods/`, and `claims/`
   - `index.md`
   - `log.md`
5. For a Zotero-backed empirical-accounting source note, use the helper to create the initial source page from Zotero metadata, abstract, notes, and annotations:

```bash
python3 ~/.codex/skills/research-wiki/scripts/research_wiki.py source-note \
  ITEMKEY \
  --project-path "/Users/feng/Documents/Obsidian Vault/ESG CSR" \
  --priority medium \
  --boss-category theory_mechanism \
  --boss-screening-reason "Core mechanism source" \
  --pdf-status manual_pdf_pending \
  --project-use mechanism \
  --source-route google_scholar \
  --verification-status verified \
  --yes
```

`source-note` accepts the complete AR handoff. `high` and `medium` default to `need_fulltext_read: true`; use `--no-need-fulltext-read` only when the planned evidence is already sufficient. To update an existing note, use `refresh-source-note`; it refreshes Zotero-controlled metadata, fingerprint, and annotations while preserving read progress and manually authored research sections. Destructive `--overwrite` is deprecated and requires `--confirm-destructive-overwrite`.

6. Run a health check after meaningful updates:

```bash
python3 ~/.codex/skills/research-wiki/scripts/research_wiki.py check \
  --project-path "/Users/feng/Documents/Obsidian Vault/ESG CSR"
```

## Research Base (Opt-In)

Use Research Base only when the project `AGENTS.md` explicitly declares it or the user explicitly asks to establish, use, save to, or organize it. Do not create it for a normal research discussion, temporary brainstorming, or one-off explanation.

Before the first Research Base write, read the project `AGENTS.md`; if it already exists, also read its `README.md`, `index.md`, `log.md`, and relevant active notes. State the exact Research Base path and get user confirmation. Project rules override the default path, language, frontmatter, status values, and promotion conditions.

Default initialization is explicit and requires `--yes`:

```bash
python3 ~/.codex/skills/research-wiki/scripts/research_wiki.py init-research-base \
  --project-path "/Users/feng/Documents/Obsidian Vault/ESG CSR" \
  --yes
```

The default location is `Research Base/` within the project. Project paths are stored in `.research-wiki/config.json`; CLI path arguments override config for the current command. Pass `--research-base-schema` for a project-level JSON schema when `AGENTS.md` defines custom directories, fields, or enums. The command creates navigation files, the five default work areas, the archive, and reusable templates; `init-project` never creates this folder automatically.

Use Research Base for candidate research questions, conversation summaries, method prototypes, data-feasibility checks, design alternatives, and rejected or superseded paths. Every note must use:

```yaml
project: Project Alpha
type: conversation_note | topic_exploration | method_prototype | data_feasibility | design_alternative
status: exploratory | under_review | promoted | rejected | superseded
evidence_status: unverified | partially_verified | verified
created: YYYY-MM-DD
last_updated: YYYY-MM-DD
tags: []
kb_promotion: false
related_kb_pages: []
supersedes:
promoted_at:
superseded_by:
decision_reason:
```

- Keep Zotero records, attachments, source notes, and reading-state fields out of Research Base. Link existing Knowledge Base pages instead of duplicating them.
- Mark unverified literature facts, data fields, identification assumptions, and expected results clearly. Do not turn prototypes into established conclusions.
- Update Research Base `index.md` and append `log.md` after each creation, rename, archive, status change, or promotion.
- Promote only after the user explicitly asks, unless the project schema explicitly authorizes promotion. Verify the evidence, write only the reusable conclusion to the appropriate Knowledge Base page, cross-link both records, set `promoted_at`, and retain the original note with `status: promoted`.
- Preserve promoted, rejected, and superseded notes. Record `decision_reason` for rejected work and `superseded_by` for replaced work. Move rejected or deferred work to `90_Archived_or_Rejected/` when the project schema requires archival rather than an in-place status change.

Validate the default structure without contacting Zotero:

```bash
python3 ~/.codex/skills/research-wiki/scripts/research_wiki.py check-research-base \
  --project-path "/Users/feng/Documents/Obsidian Vault/ESG CSR"
```

Both checks return `valid`, `errors`, and `warnings`; errors exit nonzero. Use `--report-only` only for legacy reporting pipelines that require a zero exit status.

## Obsidian-Native Integration (Optional)

Use Obsidian Flavored Markdown for both Knowledge Base and Research Base notes. When the official Obsidian skills are discoverable, follow `$obsidian-markdown` for properties, wikilinks, embeds, and callouts; follow `$obsidian-bases` only when the user or project enables dynamic views; use `$obsidian-cli` only for an explicit online check. Keep all normal initialization and offline validators functional without those skills, the Obsidian app, or the CLI.

Recommend the official Obsidian skill pack to users who do not have it:

```bash
npx skills add https://github.com/kepano/obsidian-skills
```

This is a recommended enhancement, not a hard dependency. `obsidian-markdown`, `obsidian-bases`, and `obsidian-cli` are the relevant components; do not invoke `json-canvas` or `defuddle` unless the user explicitly requests a canvas or web-content extraction.

Keep `index.md` as the portable, Agent-readable canonical index. Create parallel project-scoped Bases only after explicit opt-in:

```bash
python3 ~/.codex/skills/research-wiki/scripts/research_wiki.py init-obsidian-bases \
  --project-path "/Users/feng/Documents/Obsidian Vault/ESG CSR" \
  --scope all \
  --yes
```

Alternatively pass `--with-obsidian-bases` to `init-project` or `init-research-base`. The helper creates `knowledge.base` and/or `research.base`, embeds them in the corresponding `index.md`, and sets `obsidian_bases_enabled: true`. It never creates Research Base as a side effect of Base initialization.

Run online semantic validation only when Obsidian is open and the CLI is available:

```bash
python3 ~/.codex/skills/research-wiki/scripts/research_wiki.py check-obsidian \
  --project-path "/Users/feng/Documents/Obsidian Vault/ESG CSR"
```

This supplements `check` and `check-research-base` with unresolved-wikilink errors, graph-orphan/dead-end warnings, and Base-query validation. Read `references/obsidian-integration.md` before enabling or changing this layer.

## Writing Rules

- Write wiki pages in bilingual form: Chinese synthesis first, preserving English titles, constructs, methods, variable names, and quote-adjacent technical terms.
- Use valid Obsidian properties on newly authored pages. Keep `project`, `type`, `status`, `created`, the appropriate update field, and `tags`; use the configured `project_name` so optional Bases remain project-scoped. Missing `project` on legacy notes is a warning, not a migration-blocking error.
- Use Zotero item keys as stable source identifiers. Distinguish them from BibTeX keys if both appear.
- Preserve Zotero traceability in source pages: `zotero_item_key`, `zotero_uri`, `citation_key`, `zotero_modified`, and `source_fingerprint`.
- Preserve source-note read progress in frontmatter. Use `status`, `deep_read_priority`, `need_fulltext_read`, `read_level`, and `deep_read_completed` unless the project `AGENTS.md` defines a different schema. Keep `source_route`, `verification_status`, and actual `read_level` as separate dimensions.
- Treat source-note frontmatter as the authority for read progress. Zotero tags are secondary; if they conflict, prefer the source note and record a Zotero sync follow-up.
- Use AR reading priority in source pages: `high` for full-text deep-read priority, `medium` for abstract/introduction/research design/conclusion priority, `low` for abstract-only screening, and `exclude` for no read. Priority is not completion state.
- Keep raw source claims tied to source notes. Put cross-paper synthesis in concept/theme/method/claim pages.
- Update `index.md` whenever adding, renaming, or materially changing wiki pages.
- Append to `log.md` for every ingest, query answer filed back into the wiki, and lint/check pass.
- Prefer one-source-at-a-time ingestion when the user is actively supervising; use batches only when the user asks for bulk processing.
- File useful answers back into the wiki instead of leaving them only in chat when they add durable research value.

Default read-state frontmatter:

```yaml
status: screened | deep_read_in_progress | deep_read_done | deep_read_skip
deep_read_priority: high | medium | low | exclude
need_fulltext_read: true | false
deep_read_completed:
read_level: abstract | intro_design_conclusion | fulltext
```

Use `status: screened` and `read_level: abstract` for initial source notes created from metadata, abstracts, notes, and annotations. After a full deep read, set `status: deep_read_done`, `need_fulltext_read: false`, `read_level: fulltext`, and `deep_read_completed: YYYY-MM-DD`. Do not repeat deep reads for `deep_read_done` notes unless the user asks for a reread or update.

## Zotero Safety

- Do not modify Zotero items, collections, PDFs, attachments, or tags.
- Use Zotero local API read routes only. The helper uses `http://127.0.0.1:23119/api/users/0/...`.
- Retrieve full text only for downloaded/indexed attachment content needed for the task.
- If full text is missing, record the blocker in `log.md` and ask whether to inspect, download, or extract the attachment. Do not fabricate the paper content from metadata.

## Resources

- Read `references/project-schema.md` when creating or updating project wiki pages.
- Read `references/obsidian-integration.md` before enabling, validating, or changing optional Obsidian Bases/CLI behavior.
- Use `scripts/research_wiki.py` for repeatable Zotero reads, project skeleton creation, Research Base initialization, cache export, and health checks.
