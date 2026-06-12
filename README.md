# Research Wiki

`research-wiki` 是一个用于把 Zotero 文献集合整理为 Obsidian 研究知识库的 Codex skill。它把 Zotero 视为只读的原始文献层，把 Obsidian Markdown 视为可持续维护的研究笔记层，适合长期积累文献解读、概念、主题、方法和研究主张。

## 中英文书写原则

本 skill 默认采用双语研究写作方式：

- 中文用于解释、比较、综合判断和项目化理解，方便后续选题、文献综述和研究设计。
- 英文保留论文标题、作者、期刊、理论名称、constructs、methods、变量名、数据集名称和引用相关字段。
- source note 中的文献基本信息、Zotero item key、citation key、DOI、URL 和变量/模型名称应尽量保持英文原文。
- 跨文献综合页面可以用中文组织逻辑，但关键术语首次出现时建议保留英文，例如 `information asymmetry（信息不对称）`。
- 不直接翻译或改写可用于引用的英文专有名词，避免后续写作时与 Zotero 引文和原文表述脱节。

## What It Does

- Builds an Obsidian research wiki from a Zotero collection.
- Exports Zotero metadata and indexed full text into a local project cache.
- Creates one source note per Zotero item.
- Preserves Zotero traceability through item keys, Zotero links, citation keys, DOI, URL, modification time, and source fingerprints.
- Supports AR-style reading priorities: `high`, `medium`, `low`, and `exclude`.
- Generates Zotero-backed empirical-accounting source notes with fields for research question, design, sample, variables, main model, mechanism tests, heterogeneity tests, robustness tests, endogeneity tests, findings, innovation, and limitations.
- Syncs Zotero notes and annotations into Markdown source notes for evidence tracking.
- Organizes synthesis pages into concepts, themes, methods, and claims.
- Updates project index and log files after source-note ingestion.
- Checks the wiki for missing source notes, missing full text, orphan pages, and stale index entries.

## Typical Workflow

1. Check Zotero and the local vault.
2. Create a project wiki for one Zotero collection.
3. Export collection metadata and indexed full text into the project cache.
4. Generate or update source notes from Zotero items.
5. Add cross-paper synthesis in concept, theme, method, and claim pages.
6. Run the project check before continuing major wiki work.

## Reading Priority

| Priority | Reading Scope | Use Case |
|---|---|---|
| `high` | Full paper | Core literature requiring complete deep reading. |
| `medium` | Abstract, introduction, research design, conclusion | Useful literature where the main design and contribution must be understood. |
| `low` | Abstract only | Screening candidates and background references. |
| `exclude` | No reading | Records kept only for traceability or exclusion reasons. |

## Safety

The skill does not modify Zotero records, collections, PDFs, attachments, or tags. Zotero remains the reference manager; Obsidian remains the research note layer.

