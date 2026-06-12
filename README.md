# Research Wiki

Version: `0.0.2`

`research-wiki` is a Codex skill for turning Zotero literature collections into a structured Obsidian research wiki. It creates Zotero-traceable source notes, keeps metadata and reading annotations connected to the original references, and supports project-level synthesis across concepts, themes, methods, and claims. It is designed for literature-intensive accounting and finance research, especially workflows that need both close reading and later manuscript writing.

`research-wiki` 是一个将 Zotero 文献集合整理为 Obsidian 研究知识库的 Codex skill。它可以生成可追溯到 Zotero 条目的 source note，保留文献元数据、引用信息、阅读注释和精读状态，并把单篇文献解读进一步组织到 concepts、themes、methods 和 claims 等跨文献页面中。它适合会计、财务和金融研究中的长期文献积累、精读、选题讨论、研究设计和论文写作准备。

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
