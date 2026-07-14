# Research Wiki

Version: `0.1.0`

`research-wiki` is a Codex skill for turning Zotero literature collections into a structured Obsidian research wiki. It creates Zotero-traceable source notes, keeps metadata and reading annotations connected to the original references, and supports project-level synthesis across concepts, themes, methods, and claims. Version `0.1.0` also adds an opt-in Research Base for exploratory work that should not yet become a Knowledge Base conclusion.

`research-wiki` 是一个将 Zotero 文献集合整理为 Obsidian 研究知识库的 Codex skill。它可以生成可追溯到 Zotero 条目的 source note，保留文献元数据、引用信息、阅读注释和精读状态，并把单篇文献解读进一步组织到 concepts、themes、methods 和 claims 等跨文献页面中。`0.1.0` 还新增可选的 Research Base，用于尚不能写入 Knowledge Base 的探索性研究工作。

## What's New in v0.1.0

- Added an explicit `init-research-base` command that creates a separate Research Base only after `--yes`; normal project initialization remains Knowledge Base-only.
- Added `check-research-base` with JSON diagnostics and a failing exit code for structure, metadata, navigation, source-note duplication, and incomplete-promotion problems.
- Added default templates for conversation notes, topic exploration, method prototypes, data feasibility, and design alternatives.
- Defined strict boundaries: Zotero owns references and attachments; Knowledge Base owns traceable and verified research knowledge; Research Base owns evidence-labelled exploratory work and retained decision history.
- Required explicit promotion or project authorization before content moves from Research Base to Knowledge Base.

中文说明：

- 新增显式的 `init-research-base` 命令；只有在 `--yes` 确认后创建独立 Research Base，常规项目初始化不会自动创建它。
- 新增 `check-research-base`，以 JSON 返回目录、元数据、导航、source note 重复及升级记录问题，并在发现问题时失败退出。
- 新增讨论记录、选题探索、方法原型、数据可行性和设计备选五类模板。
- 明确边界：Zotero 管理题录与附件；Knowledge Base 管理可追溯、已核验知识；Research Base 管理带证据标签的探索性工作和决策轨迹。
- Research Base 内容只有在用户明确要求或项目规则授权后才可升级到 Knowledge Base。

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
- Check the wiki for missing source notes, missing full text, orphan pages, and stale index entries.
- Maintain an opt-in Research Base for preliminary ideas, data checks, method prototypes, design alternatives, and transparent archive decisions.

## Research Base

Research Base is deliberately separate from the Zotero-backed Knowledge Base. It is activated only by a project `AGENTS.md` rule or an explicit user request, and its first write still requires an exact-path confirmation. The default path is `Research Base/` inside the project; a project schema may override it.

Each Research Base note records a type, workflow status, evidence status, timestamps, promotion state, Knowledge Base links, and any superseded note. Use it for unverified or partially verified work; link to existing source notes rather than recreating them. Promotion requires verification plus explicit authorization, cross-links, index/log updates, and retention of the original exploration record.

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

The skill does not modify Zotero records, collections, PDFs, attachments, or tags. Zotero remains the reference manager; Obsidian remains the research note layer.
