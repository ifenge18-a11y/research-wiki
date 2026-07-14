# Research Wiki

Version: `0.2.0`

`research-wiki` is a Codex skill for turning Zotero literature collections into a structured Obsidian research wiki. It creates Zotero-traceable source notes, keeps metadata and reading annotations connected to the original references, and supports project-level synthesis across concepts, themes, methods, and claims. Version `0.2.0` unifies Knowledge Base and Research Base configuration, adds safe source-note refresh, and makes both validators reliable automation gates.

`research-wiki` 是一个将 Zotero 文献集合整理为 Obsidian 研究知识库的 Codex skill。它可以生成可追溯到 Zotero 条目的 source note，保留文献元数据、引用信息、阅读注释和精读状态，并把单篇文献解读进一步组织到 concepts、themes、methods 和 claims 等跨文献页面中。`0.2.0` 统一 Knowledge Base/Research Base 配置，新增安全 source-note 刷新，并使两类检查器都可作为可靠的自动化门禁。

## What's New in v0.2.0

- Added `.research-wiki/config.json` with configurable Knowledge Base and Research Base paths, while preserving the historical project-root layout when config is absent.
- Expanded `source-note` to accept the complete AR handoff and added `refresh-source-note`, which updates Zotero-controlled metadata, fingerprints, and annotations without erasing deep-read state or manual analysis.
- Deprecated one-step destructive overwrite; full replacement now requires both `--overwrite` and `--confirm-destructive-overwrite`.
- Standardized `check` and `check-research-base` output as `valid`, `errors`, and `warnings`; errors return nonzero unless `--report-only` is used.
- Prevented Knowledge Base checks from linting Research Base files, limited missing-full-text warnings to notes that require further reading, and added stale-fingerprint detection.
- Added scalar, inline-list, and multiline-list frontmatter parsing, project-level Research Base schema JSON, unambiguous index-link checks, and promotion/rejection/supersession state requirements.
- Made `init-project` without a collection and every Research Base-only command independent of Zotero availability.

中文说明：

- 新增 `.research-wiki/config.json`，统一 Knowledge Base 与 Research Base 路径；无配置时继续兼容项目根目录布局。
- `source-note` 接收完整 AR 交接字段；新增 `refresh-source-note`，仅刷新 Zotero 控制的元数据、fingerprint 与 annotations，保留精读状态和人工分析。
- 弃用单步破坏性覆盖；完整重建必须同时传入 `--overwrite` 与 `--confirm-destructive-overwrite`。
- 两类检查器统一输出 `valid`、`errors`、`warnings`，错误默认非零退出；`--report-only` 保留兼容模式。
- Knowledge Base 检查排除 Research Base，只在 `need_fulltext_read: true` 时报告缺全文，并检测 stale fingerprint。
- Research Base 支持多种 YAML 列表、项目级 schema、无歧义索引以及 promoted/rejected/superseded 状态字段校验。
- 未绑定 collection 的 `init-project` 与所有 Research Base-only 命令均可在 Zotero 离线时运行。

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
- Check the wiki for missing source notes, required full text, stale fingerprints, orphan pages, and ambiguous or stale index entries.
- Maintain an opt-in Research Base for preliminary ideas, data checks, method prototypes, design alternatives, and transparent archive decisions.

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

The skill does not modify Zotero records, collections, PDFs, attachments, or tags. Zotero remains the reference manager; Obsidian remains the research note layer.
