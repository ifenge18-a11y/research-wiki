# Research Wiki

Version: `0.0.2`

`research-wiki` is a Codex skill for building an Obsidian research wiki from Zotero literature. Its writing style is intentionally bilingual: Chinese is used for research thinking and synthesis, while English is preserved for source-facing academic details.

## Bilingual Writing Policy

本 skill 的核心写作原则是“中文组织研究理解，英文保留学术原文信息”。

中文主要用于：

- 解释论文的研究问题、理论机制、研究设计和主要结论。
- 比较多篇文献之间的联系、差异、争议和研究空白。
- 形成面向项目的综合判断，例如对选题、文献综述、变量设计和实证设计的启发。
- 记录研究者自己的理解、疑问、待验证事项和下一步阅读计划。

英文主要用于：

- Paper titles, author names, journal names, DOI, URL, Zotero item keys, and citation keys.
- Theory names, constructs, methods, datasets, variable names, model names, and technical terms.
- Source-note fields that may later be reused in academic writing or citation workflows.
- Exact labels from Zotero metadata, annotations, and empirical tables when preserving the original wording matters.

建议写法：

- 中文句子中保留关键英文术语，例如 `information asymmetry（信息不对称）`、`difference-in-differences`、`audit quality`。
- 不随意翻译变量名、数据库名、模型名和 citation key，避免后续写作时与 Zotero 或原文脱节。
- source note 可以中文解读为主，但标题、期刊、作者、DOI、citation key、变量和模型字段应保持英文原文。
- 跨文献页面可以用中文组织论证，但证据、方法和变量名称应能回溯到英文原文。

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

## Reading Priority

| Priority | Reading Scope | Use Case |
|---|---|---|
| `high` | Full paper | Core literature requiring complete deep reading. |
| `medium` | Abstract, introduction, research design, conclusion | Useful literature where the main design and contribution must be understood. |
| `low` | Abstract only | Screening candidates and background references. |
| `exclude` | No reading | Records kept only for traceability or exclusion reasons. |

## Safety

The skill does not modify Zotero records, collections, PDFs, attachments, or tags. Zotero remains the reference manager; Obsidian remains the research note layer.

