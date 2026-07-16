# Research Wiki

Version: `0.3.0`

`research-wiki` is a Codex skill for turning Zotero literature collections into a structured Obsidian research wiki. It creates Zotero-traceable source notes, keeps metadata and reading annotations connected to the original references, and supports project-level synthesis across concepts, themes, methods, and claims. Version `0.3.0` adds optional Obsidian-native dynamic views and online semantic checks while preserving the portable Markdown indexes and Zotero-independent offline workflow.

`research-wiki` 是一个将 Zotero 文献集合整理为 Obsidian 研究知识库的 Codex skill。它可以生成可追溯到 Zotero 条目的 source note，保留文献元数据、引用信息、阅读注释和精读状态，并把单篇文献解读进一步组织到 concepts、themes、methods 和 claims 等跨文献页面中。`0.3.0` 在保留 Markdown 索引与离线工作流的基础上，新增可选的 Obsidian Bases 动态视图和在线语义检查。

## What's New in v0.3.0

- Added explicitly enabled `knowledge.base` and `research.base` files with project-scoped catalog, reading, metadata, synthesis, exploration, evidence, promotion, and decision views.
- Added `init-obsidian-bases`; `--with-obsidian-bases` is also available on project and Research Base initialization. No Base is created without opt-in, and Research Base is never created as a side effect.
- Added `check-obsidian`, an optional read-only online check for unresolved project wikilinks, graph orphans/dead ends, and broken Base queries.
- Kept `index.md` as the canonical portable index and embedded Bases only as parallel dynamic views.
- Added `project_name` and `obsidian_bases_enabled` to config schema v2. Older configs upgrade on the next write without losing custom keys or paths.
- Added the `project` property to new Research Base templates and warning-only compatibility for legacy Knowledge Base/Research Base notes that lack it.
- Rendered multiline source abstracts as Obsidian `abstract` callouts and added regression coverage against duplicate Zotero-annotation placeholders.
- Documented optional composition with the official `obsidian-markdown`, `obsidian-bases`, and `obsidian-cli` skills.

中文说明：

- 显式启用后可生成 `knowledge.base` 与 `research.base`，分别提供文献、精读、元数据、综合，以及探索、证据、升级和决策视图。
- 新增 `init-obsidian-bases`，并为两类初始化命令增加 `--with-obsidian-bases`；默认不创建 `.base`，也不会顺带创建 Research Base。
- 新增只读的 `check-obsidian`，在线检查项目内未解析链接、图谱孤立/死端页面和 Base 查询错误。
- `index.md` 继续是离线与 Agent 可读的权威索引，Bases 只是并行动态视图。
- 配置升级为 schema v2，增加 `project_name` 与 `obsidian_bases_enabled`；升级时保留旧项目的自定义字段和路径。
- 新模板写入 `project` 属性；旧笔记缺少该属性只警告，不阻断既有项目。
- 多行摘要改用 Obsidian `abstract` callout，并增加回归测试防止待补充清单出现重复行。
- 文档建议组合使用 Obsidian 官方 `obsidian-markdown`、`obsidian-bases` 与 `obsidian-cli` skills，但不设为强制依赖。

## Features

- Build an Obsidian research wiki from a Zotero collection.
- Treat Zotero as the read-only source layer and Obsidian Markdown as the maintained research-note layer.
- Export Zotero metadata and indexed full text into a local project cache.
- Create one source note per Zotero item.
- Preserve Zotero traceability through item keys, Zotero links, citation keys, DOI, URL, modification time, and source fingerprints.
- Generate empirical-accounting source notes with fields for research question, method, sample, variables, main model, mechanism tests, heterogeneity tests, robustness tests, endogeneity tests, findings, innovation, and limitations.
- Support AR-style reading priorities: `high`, `medium`, `low`, and `exclude`.
- Sync Zotero notes and annotations into Markdown source notes for evidence tracking.
- Organize synthesis pages into concepts, themes, methods, and claims.
- Update project index and log files after source-note ingestion.
- Check the wiki for missing source notes, required full text, stale fingerprints, structurally misplaced pages, and ambiguous or stale index entries.
- Maintain an opt-in Research Base for preliminary ideas, data checks, method prototypes, design alternatives, and transparent archive decisions.
- Optionally create project-scoped Obsidian Bases without replacing curated Markdown indexes.
- Optionally validate unresolved links, graph structure, and Base queries through the read-only Obsidian CLI.

## Recommended Official Obsidian Skills

For the best Obsidian-native authoring and validation experience, install the official [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) package:

```bash
npx skills add https://github.com/kepano/obsidian-skills
```

The relevant skills are `obsidian-markdown`, `obsidian-bases`, and `obsidian-cli`. They are recommended, not required: all normal `research-wiki` project creation, source-note, Research Base, and offline-check commands continue to work without them. `json-canvas` and `defuddle` are used only when a user explicitly asks for a canvas or web-page extraction. If the skills already appear in the Codex “/” picker, no reinstall or relocation is needed.

The optional CLI check additionally requires Obsidian 1.12 or newer, the `obsidian` command, an open Obsidian app, and the project inside a known vault.

## Optional Dynamic Views and Online Check

Keep `index.md` as canonical navigation, then opt into parallel dynamic views when useful:

```bash
python3 ~/.codex/skills/research-wiki/scripts/research_wiki.py init-obsidian-bases \
  --project-path "/Users/feng/Documents/Obsidian Vault/ESG CSR" \
  --scope all \
  --yes
```

`--scope all` creates `knowledge.base` and creates `research.base` only if Research Base already exists; otherwise the Research Base portion is reported as skipped. Existing `.base` files are preserved so user customization is not overwritten. You can also opt in during initialization with `--with-obsidian-bases`.

Run the portable checks first, then use the online supplement when Obsidian is available:

```bash
python3 ~/.codex/skills/research-wiki/scripts/research_wiki.py check \
  --project-path "/Users/feng/Documents/Obsidian Vault/ESG CSR"
python3 ~/.codex/skills/research-wiki/scripts/research_wiki.py check-research-base \
  --project-path "/Users/feng/Documents/Obsidian Vault/ESG CSR"
python3 ~/.codex/skills/research-wiki/scripts/research_wiki.py check-obsidian \
  --project-path "/Users/feng/Documents/Obsidian Vault/ESG CSR"
```

`check-obsidian` treats unresolved project wikilinks and broken Base queries as errors, and graph orphans/dead ends as warnings. It does not replace either offline validator.

## Research Base

Research Base is deliberately separate from the Zotero-backed Knowledge Base. It is activated only by a project `AGENTS.md` rule or an explicit user request, and its first write still requires an exact-path confirmation. The default path is `Research Base/` inside the project; a project schema may override it.

Each Research Base note records a type, workflow status, evidence status, timestamps, promotion state, Knowledge Base links, and its decision trail. Promoted notes require `promoted_at`, rejected notes require `decision_reason`, and superseded notes require `superseded_by`. Use it for unverified or partially verified work; link to existing source notes rather than recreating them.

```bash
python3 ~/.codex/skills/research-wiki/scripts/research_wiki.py init-research-base \
  --project-path "/Users/feng/Documents/Obsidian Vault/ESG CSR" --yes
python3 ~/.codex/skills/research-wiki/scripts/research_wiki.py check-research-base \
  --project-path "/Users/feng/Documents/Obsidian Vault/ESG CSR"
```

## Reading Priority

| Priority | Reading Scope | Use Case |
|---|---|---|
| `high` | Full paper | Core literature requiring complete deep reading. |
| `medium` | Abstract, introduction, research design, conclusion | Useful literature where the main design and contribution must be understood. |
| `low` | Abstract only | Screening candidates and background references. |
| `exclude` | No reading | Records kept only for traceability or exclusion reasons. |

## Safety

The skill does not modify Zotero records, collections, PDFs, attachments, or tags. Zotero remains the reference manager; Obsidian remains the research note layer. Obsidian CLI integration is read-only, and existing `.base` files are never overwritten.
