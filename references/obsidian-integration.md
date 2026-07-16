# Optional Obsidian Integration

Use this reference when enabling or validating Obsidian-native features in a `$research-wiki` project. The portable Markdown indexes and offline validators remain authoritative; Obsidian Bases and CLI checks are optional views and diagnostics.

## Capability Boundaries

| Layer | Role | Required? |
|---|---|---|
| `obsidian-markdown` | Properties, wikilinks, embeds, callouts, and Obsidian-readable Markdown | Recommended for all authored notes |
| `obsidian-bases` | Dynamic, project-scoped views over Knowledge Base or Research Base notes | Explicit opt-in only |
| `obsidian-cli` | Online unresolved-link, graph, and Base-query checks against an open vault | Explicit check only |
| `json-canvas` | Canvas or visual-map artifacts | Only when explicitly requested |
| `defuddle` | Web-page extraction | Only when explicitly requested |

Recommend installing the official Obsidian skill pack when these skills are not already discoverable:

```bash
npx skills add https://github.com/kepano/obsidian-skills
```

Do not treat this package as a runtime dependency. Project creation, Research Base creation, source-note generation, `check`, and `check-research-base` must continue to work without Obsidian or Node.js.

## Shared Properties

New Knowledge Base and Research Base notes use valid YAML properties and the configured `.research-wiki/config.json` `project_name`:

```yaml
project: Project Alpha
type: source
status: screened
created: 2026-07-16
updated: 2026-07-16
tags: []
```

Use `last_updated` instead of `updated` for Research Base notes. Existing notes without `project` remain valid but receive a warning because project-scoped Bases cannot display them until the property is added.

## Parallel Index Contract

- Keep `index.md` as the portable, Agent-readable navigation contract and update it after every meaningful change.
- Add `knowledge.base` beside the Knowledge Base `index.md` only after explicit opt-in.
- Add `research.base` beside the Research Base `index.md` only after explicit opt-in and only after Research Base exists.
- Embed the Base in its corresponding index with `![[knowledge.base]]` or `![[research.base]]`.
- Do not create Research Base as a side effect of `init-obsidian-bases --scope all`; report it as skipped when absent.
- Treat generated Bases as safe initial definitions. Do not overwrite an existing `.base`, because users may have customized its views.

`knowledge.base` provides Source Catalog, Reading Queue, Metadata Review, and Synthesis views. `research.base` provides Active Explorations, Evidence Review, Promotion Queue, and Decision Archive views. Both filter on `project_name` plus their permitted `type` values so notes from other projects in the same vault do not leak into the views.

Initialize explicitly:

```bash
python3 ~/.codex/skills/research-wiki/scripts/research_wiki.py init-obsidian-bases \
  --project-path "/path/to/project" \
  --scope knowledge|research|all \
  --yes
```

Use `--with-obsidian-bases` on `init-project` to create only the Knowledge Base view, or on `init-research-base` to create only the Research Base view.

## Online Validation

`check-obsidian` requires the `obsidian` executable, an open Obsidian app, and a project located within a vault reported by `obsidian vaults verbose`. It selects the most specific containing vault, then runs read-only commands:

- `unresolved verbose format=json`: unresolved wikilinks sourced from the project are errors.
- `orphans`: project notes with no incoming links are warnings.
- `deadends`: project notes with no outgoing links are warnings.
- `base:query ... format=json`: each generated view must query successfully and return JSON.

CLI commands can be temporarily unavailable while a vault loads or when a required core feature is disabled. The helper retries once. A missing optional graph capability is reported as a warning; an unavailable CLI, unknown vault, unresolved project link, or broken Base query is an error. Use `--report-only` only when a legacy pipeline requires zero exit status.

This online check supplements the offline validators. Do not rename the offline `orphan_location` structural diagnostic to imply graph analysis: it means a Markdown page is outside the configured Knowledge Base directory contract.
