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
.research-wiki/config.json
```

`.research-wiki/config.json` is the machine-readable path contract:

```json
{
  "schema_version": 1,
  "knowledge_base_path": ".",
  "research_base_path": "Research Base"
}
```

Paths may be absolute or relative to the project. CLI path flags override config for one command. Without a config file, keep backward compatibility by using the project root as Knowledge Base and `<project>/Research Base` as Research Base. `AGENTS.md` remains authoritative for policy, language, frontmatter, and promotion rules; encode custom validator fields and enums in a project schema JSON referenced by `research_base_schema_path` or passed through `--research-base-schema`.

- `sources/`: one page per Zotero item. Source pages summarize and interpret one paper only.
- `concepts/`: construct definitions, mechanisms, theories, variables, institutional context.
- `themes/`: cross-paper literature streams and evolving research narratives.
- `methods/`: identification strategies, empirical designs, data sources, measurements.
- `claims/`: durable propositions, contradictions, boundary conditions, and evidence status.
- `.research-wiki/cache/`: machine-generated Zotero metadata and full text. Do not manually edit.

## Research Base Contract (Opt-In)

`Research Base/` is an optional sibling of the Knowledge Base structure above. It is not created by `init-project`; use it only when the project `AGENTS.md` declares it or the user explicitly requests exploratory research persistence.

```text
Research Base/
  README.md
  index.md
  log.md
  00_Conversation_Notes/
  01_Topic_Exploration/
  02_Method_Prototypes/
  03_Data_Feasibility/
  04_Design_Alternatives/
  90_Archived_or_Rejected/
  _templates/
```

- `README.md` records the boundary among Zotero, Knowledge Base, and Research Base, plus local promotion rules.
- `index.md` links all active and archived notes with a one-line description; `log.md` is append-only.
- Research Base may contain candidate questions, design comparisons, unverified data checks, and prototypes. It must not contain duplicated Zotero records, source notes, PDF/read-state management, or unverified content presented as a settled conclusion.
- A project may override this path, directory layout, language, frontmatter, status rules, and promotion conditions in `AGENTS.md`. The project rule takes precedence.

Default Research Base note frontmatter:

```yaml
type: conversation_note | topic_exploration | method_prototype | data_feasibility | design_alternative
status: exploratory | under_review | promoted | rejected | superseded
evidence_status: unverified | partially_verified | verified
created: YYYY-MM-DD
last_updated: YYYY-MM-DD
kb_promotion: false
related_kb_pages: []
supersedes:
promoted_at:
superseded_by:
decision_reason:
```

Promotion is explicit: verify the underlying evidence, write only the stable reusable conclusion to the relevant Knowledge Base page, cross-link both notes, set the original note to `status: promoted`, record `promoted_at`, and preserve its decision trail. Rejected notes require `decision_reason`; superseded notes require `superseded_by`. All three terminal states remain retained and indexed rather than deleted.

A custom Research Base schema JSON may replace the default `directories`, `note_types`, `statuses`, `evidence_statuses`, and `required_fields` string lists. Omitted schema files use the defaults above.

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

For source pages, use Zotero-backed frontmatter so the Markdown note can be traced back to the reference manager and reused in writing:

```yaml
type: source
status: screened | deep_read_in_progress | deep_read_done | deep_read_skip
zotero_item_key:
zotero_library_id:
zotero_uri:
citation_key:
title:
authors:
year:
venue:
doi:
url:
abstract:
created:
updated:
zotero_modified:
source_fingerprint:
metadata_status: up_to_date | needs_update | needs_review
source_route: openalex | google_scholar | cnki | publisher | ssrn | nber | user | manual | unknown
verification_status: verified | partially_verified | unverified
boss_category: core_literature | related_stream | theory_mechanism | method_data | china_context | excluded_weakfit
boss_screening_reason:
pdf_status: need_pdf | pdf_available | manual_pdf_pending | not_needed | unknown
project_use:
deep_read_priority: high | medium | low | exclude
read_scope:
need_fulltext_read: true | false
deep_read_completed:
read_level: abstract | intro_design_conclusion | fulltext
tags:
project:
```

Source frontmatter rules:

- `zotero_item_key` is the stable Zotero item identifier.
- `citation_key` is the Better BibTeX/Zotero citekey when available; use it for writing citations such as `[@citation_key]`.
- `zotero_uri` should point back to the Zotero item, for example `zotero://select/library/items/ITEMKEY`.
- `created` and `updated` are Markdown note timestamps.
- `zotero_modified` records the Zotero item modification time.
- `source_fingerprint` is computed from Zotero metadata, abstract, notes, and annotations. If it changes, set the separate `metadata_status: needs_update`; do not put metadata freshness into the source-note workflow `status` field.
- `source_route` records where the record was discovered or checked. `verification_status` records metadata/evidence verification and always uses the same three values, including for CNKI. `read_level` records the evidence depth actually read. These dimensions must not be collapsed into one label.
- `source-note` accepts the complete AR screening handoff. `high` and `medium` default to `need_fulltext_read: true`, while `low` and `exclude` default to `false`; an explicit CLI override is allowed except that `exclude` cannot require a deep read.
- Use `refresh-source-note` when Zotero metadata or annotations change. It updates only Zotero-controlled metadata, the fingerprint, metadata status, and annotation/basic-information sections; it preserves `created`, read state, completion date, screening judgment, and manually authored research sections.
- Initial source notes may use only Zotero metadata, abstract, notes, and annotations. Leave unavailable research-design fields blank.
- Source-note read progress is authoritative for avoiding duplicate work. Zotero tags may mirror it, but source frontmatter wins if they conflict.

Use AR reading priority:

| Priority | Read scope | Source note behavior |
|---|---|---|
| `high` | 阅读全文 | 完整补充研究问题、理论机制、模型、变量、所有检验、结论、创新与不足 |
| `medium` | 阅读 abstract、introduction、research design、conclusion | 补充核心问题、设计、模型框架、主要结论；细节不足处标空 |
| `low` | 只读摘要 | 只生成基本信息、摘要、初筛判断和项目相关性 |
| `exclude` | 不阅读 | 仅保留 Zotero 对应关系和排除原因 |

Use read-state fields separately from priority:

| Field | Meaning |
|---|---|
| `status: screened` | 已完成元数据、摘要或初筛层面的处理，尚未完成全文精读 |
| `status: deep_read_in_progress` | 正在精读全文或核心章节 |
| `status: deep_read_done` | 已完成规定精读，后续批处理默认跳过 |
| `status: deep_read_skip` | 明确不再精读，正文或日志应记录原因 |
| `need_fulltext_read` | 是否仍需要后续全文或核心章节阅读 |
| `read_level` | 实际已完成的阅读层级，不等同于 priority |
| `deep_read_completed` | 只有完成精读后填写 `YYYY-MM-DD` |

For empirical-accounting source pages, include:

```markdown
# Chinese working title / English source title

## 1. 文献基本信息
- 标题：
- 作者：
- 年度：
- 期刊：
- DOI：
- Zotero item key：
- Citation key：
- Zotero link：
- 写作引用：
- 摘要：

## 2. MD 文件信息
- 创建时间：
- 最后修改时间：
- Zotero 条目修改时间：
- Source fingerprint：
- 当前精读标签：high / medium / low / exclude
- 当前阅读范围：
- 当前阅读状态：screened / deep_read_in_progress / deep_read_done / deep_read_skip
- 已完成阅读层级：abstract / intro_design_conclusion / fulltext
- 精读完成日期：
- 更新状态：up-to-date / needs-update / needs-review（对应 `metadata_status`，不对应 source `status`）

## 3. 初筛判断
- 是否纳入后续研究：
- 项目相关性：
- 文献角色：core_literature / related_stream / theory_mechanism / method_data / china_context / excluded_weakfit
- 精读优先级：
- 排除或保留理由：

## 4. 具体研究内容
### 4.1 研究问题
- 本文研究什么问题：
- 该问题为何重要：
- 对应的会计/财务研究场景：

### 4.2 研究方法
- 研究设计类型：
- 数据来源：
- 样本范围：
- 样本期间：
- 分析单位：

### 4.3 主检验
- 主检验模型：
- 被解释变量：
- 解释变量：
- 控制变量：
- 固定效应：
- 标准误聚类：
- 主检验结论：

### 4.4 机制检验
- 机制逻辑：
- 机制检验方法：
- 机制检验模型：
- 机制变量：
- 机制检验结论：

### 4.5 异质性检验
- 分组或调节变量：
- 检验方法：
- 检验模型：
- 异质性结论：

### 4.6 稳健性检验
- 替代变量：
- 替代样本：
- 替代模型：
- 其他稳健性处理：
- 稳健性结论：

### 4.7 内生性检验
- 潜在内生性问题：
- 处理方法：
- 检验模型：
- 工具变量 / DID / PSM / Heckman / 其他方法：
- 内生性处理结论：

## 5. 文章评价
### 5.1 主要结论

### 5.2 创新点

### 5.3 不足与识别风险

### 5.4 对本项目的启发
- 可借鉴之处：
- 需要避免之处：
- 可用于文献综述的位置：
- 可用于研究设计的位置：
- 可用于变量设计的位置：

## 6. Zotero 阅读注释
| Page | Type | Color | Text | Comment | Tags |
|---|---|---|---|---|---|

## 7. 待补充清单
- 缺失的元数据：
- 需要阅读全文确认：
- 需要核对的模型或变量：
- 需要补充的 Zotero 注释：
- 需要连接的 concept/theme/method/claim 页面：
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
- Update it after every ingest or filed query answer. Use path-qualified links such as `[[sources/2025-lovelace-test]]`; basename-only links are accepted only when the basename is unique across the Knowledge Base.

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
2. Create or update the source page using the Zotero-backed source note schema.
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
- Missing full text in `.research-wiki/cache/fulltext/` only when the corresponding source note has `need_fulltext_read: true`.
- Stale source fingerprints compared with `.research-wiki/cache/items/*.json`.
- Source notes missing read-state frontmatter fields: `status`, `need_fulltext_read`, `read_level`, or `deep_read_completed`.
- Orphan Markdown pages outside the configured Knowledge Base contract. Exclude the configured Research Base from Knowledge Base linting.
- Return machine-readable `valid`, `errors`, and `warnings`; errors exit nonzero unless `--report-only` is explicitly requested.
