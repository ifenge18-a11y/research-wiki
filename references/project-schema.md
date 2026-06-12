# Research Wiki Project Schema

Use this schema inside each Obsidian project created by `$research-wiki`.

## Directory Contract

```text
AGENTS.md
index.md
log.md
sources/
concepts/
themes/
methods/
claims/
.research-wiki/cache/
```

- `sources/`: one page per Zotero item. Source pages summarize and interpret one paper only.
- `concepts/`: construct definitions, mechanisms, theories, variables, institutional context.
- `themes/`: cross-paper literature streams and evolving research narratives.
- `methods/`: identification strategies, empirical designs, data sources, measurements.
- `claims/`: durable propositions, contradictions, boundary conditions, and evidence status.
- `.research-wiki/cache/`: machine-generated Zotero metadata and full text. Do not manually edit.

## Page Conventions

Use YAML frontmatter on wiki-authored pages:

```yaml
type: source | concept | theme | method | claim
status: draft | active | needs-review
zotero_key:
created:
updated:
tags:
```

For source pages, include:

```markdown
# Chinese working title / English source title

## Citation
- Zotero item key:
- Authors:
- Year:
- Venue:
- DOI/URL:

## 核心贡献 / Core Contribution

## 研究问题 / Research Question

## 理论机制 / Theory and Mechanism

## 数据与方法 / Data and Method

## 主要发现 / Findings

## 局限与识别风险 / Limits and Identification Risks

## 与本项目的关系 / Relevance to This Project

## 可连接页面 / Links to Wiki Pages
```

For synthesis pages, separate evidence from interpretation:

```markdown
## Synthesis / 综合判断
## Evidence Map / 证据地图
## Tensions / 矛盾与边界
## Open Questions / 待研究问题
## Source Links / 来源链接
```

## Bilingual Style

- Use Chinese for explanation, comparison, and synthesis unless the user asks otherwise.
- Preserve English paper titles, theory names, constructs, methods, dataset names, and variable labels.
- Translate key terms only when helpful, keeping the original on first mention, such as `information asymmetry（信息不对称）`.
- Do not quote long passages. Prefer concise paraphrase with source attribution.

## Index Rules

`index.md` is content-oriented. Keep it short enough for Codex to scan first:

- Group pages by source, concept, theme, method, and claim.
- Each entry should contain an Obsidian link, one-line summary, and source count when useful.
- Update it after every ingest or filed query answer.

## Log Rules

`log.md` is chronological and append-only. Use parseable headings:

```markdown
## [YYYY-MM-DD] ingest | Title or collection
## [YYYY-MM-DD] query | Short question
## [YYYY-MM-DD] lint | Check summary
```

Each entry should name changed pages, missing full-text blockers, and decisions made with the user.

## Ingest Rules

1. Read metadata first, then Zotero indexed full text if available.
2. Create or update the source page.
3. Identify concepts, themes, methods, and claims touched by the source.
4. Update existing synthesis pages before creating new ones when the page already exists.
5. Add cross-links from source to synthesis pages and back from synthesis pages to sources.
6. Update `index.md`.
7. Append `log.md`.

## Lint Rules

Check for:

- Source notes without reciprocal links from synthesis pages.
- Concepts or claims mentioned repeatedly but missing pages.
- Contradictions not represented in `claims/`.
- Missing or stale index entries.
- Missing full text in `.research-wiki/cache/fulltext/`.
- Orphan Markdown pages outside `.research-wiki/`.
