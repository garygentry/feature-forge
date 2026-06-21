# Feature Forge Docs Site — Rebuild Assessment

> Phase-1 end-user assessment + the target information architecture for the
> ground-up docs rebuild. Written against the actual skill/reference files
> (the skills are the source of truth), not prior summaries.

## 1. What the product is

**Feature Forge** is a plugin that turns a fuzzy feature idea into shipped,
verified code through a fixed, resumable **pipeline of stages**, each a separate
skill you invoke as a slash command. State persists between stages in
`.pipeline-state.json`, so the pipeline is resumable across sessions.

The canonical flow (from `references/process-overview.md`):

```
[forge-0-epic]  →  forge-1-prd  →  forge-2-tech  →  forge-3-specs
                       (verify gate available after each stage)
                →  forge-4-backlog  →  forge-5-loop  →  forge-6-docs
```

The six core stages:

| Stage | Command | Produces |
| ----- | ------- | -------- |
| 1 — PRD | `/feature-forge:forge-1-prd <feature>` | `PRD.md` (requirements, REQ-IDs) |
| 2 — Tech Spec | `/feature-forge:forge-2-tech <feature>` | `tech-spec.md` |
| 3 — Impl Specs | `/feature-forge:forge-3-specs <feature>` | `00-…NN-*.md` + `TRACEABILITY.md` |
| 4 — Backlog | `/feature-forge:forge-4-backlog <feature>` | `backlog.json` |
| 5 — Loop | `/feature-forge:forge-5-loop <feature>` | implemented, committed code |
| 6 — Docs | `/feature-forge:forge-6-docs <feature>` | `docs/architecture/<feature>/` |

Surrounding the core stages:

- **`forge-init`** — one-time, writes `forge.config.json` defaults into an
  existing project. Use on a repo that already has code.
- **`forge-bootstrap`** — scaffolds a *brand-new empty* repo to a green baseline
  (toolchain, passing lint/test, `forge.config.json`), optionally chaining into
  the pipeline (Mode B). Use on an empty repo. This is the bootstrap-vs-init fork.
- **`forge` (navigator/dashboard)** — read-only status across the pipeline /
  epics; tells you the next command.
- **`forge-verify` / `forge-fix`** — the quality gate. `forge-verify` analyzes a
  stage's artifacts and writes a findings doc; `forge-fix` applies the fixes.
  Available after every stage.
- **`forge-0-epic`** — Stage 0, optional. Decomposes a large change into member
  features with dependencies + `exposes`/`consumes` contracts
  (`epic-manifest.json` + `EPIC.md`).

**Where rauf fits:** Stage 5 (`forge-5-loop`) runs an autonomous coding loop
against `backlog.json`. The runner is **configured, not hardcoded** (the
`loopRunner` block in `forge.config.json`) and defaults to **rauf**. rauf spawns
a *fresh-context* coding agent per backlog item, runs the project's verification
command, and commits per item. Users need to know how to **run / watch / stop**
the loop and read its `RAUF_DONE` / `RAUF_BLOCKED` / `RAUF_NEEDS_HUMAN` signals —
internals live in the rauf repo.

## 2. The current site's gaps (verified against the live site)

The existing site has exactly **2 native pages** (`index.mdx` splash,
`guides/setup.mdx` starter stub) plus **14 symlinked maintainer docs** (5
per-agent install pages, and the deep `forge-bootstrap` + `epic-orchestration`
architecture/CLI docs). Confirmed gaps:

- **No real getting-started.** `guides/setup.mdx` is the scaffold's placeholder
  ("edit `docs.manifest.json`"), not a user guide.
- **No pipeline overview.** Nothing explains the 6 stages as a usage flow.
- **`forge-init` undocumented.** No page; no bootstrap-vs-init decision aid.
- **Stages 1–6 undocumented as usage.** No per-stage "command / inputs / outputs
  / what you approve / next" pages.
- **No glossary / key concepts.** PRD, REQ-IDs, tech spec, specs, backlog,
  acceptance criteria, verification gate, fresh-context loop, epic, charter,
  contracts are never defined.
- **No worked example.** Nothing walks one feature end to end.
- **No troubleshooting / FAQ.** Stage failures, "repo not empty" refusal,
  reading pipeline state, installed-bundle self-location note — all absent.
- **Agent pages are install-only** and duplicate each other; they sit at top
  prominence rather than in a reference section.
- **Deep architecture docs are top-level**, competing with (absent) end-user
  content for attention.

What already works and is preserved: the manifest-driven single-source-of-truth
model, the symlink mechanism (`setup-docs.sh`), the drift guard
(`check-docs.mjs`), env-driven `SITE`/`BASE_PATH` for GitHub Pages at
`/feature-forge/`, and the light/dark diagram render pipeline.

## 3. Target information architecture

Sidebar groups are independent of page slugs (the drift guard checks slug
membership + order, not group labels). The deep symlinked docs keep their
existing slugs (to avoid changing relative-link depth) and are demoted into a
**Reference** group at the end.

- **Start Here**
  - `/` (splash) — *What is Feature Forge?* hero + pipeline diagram
  - `start-here/install` — Claude Code marketplace + cross-agent npx installer
  - `start-here/quick-start` — zero → first shipped feature
  - `start-here/concepts` — Key Concepts & Glossary
- **Using the Pipeline**
  - `pipeline/overview` — the 6 stages + where init/bootstrap/epics fit (diagram)
  - `pipeline/init` — `forge-init` and choosing bootstrap-vs-init
  - `pipeline/stage-1-prd` … `pipeline/stage-6-docs`
  - `pipeline/verify-and-fix` — the gate, findings, applying fixes
  - `pipeline/dashboard` — tracking progress with the `forge` navigator
- **Worked Example**
  - `example/walkthrough` — one small feature through every stage
- **Advanced**
  - `advanced/epics` — Stage 0 epics (when/why, decompose, run, dashboard)
  - `advanced/bootstrapping` — empty-repo Mode B chaining
  - `advanced/config` — `forge.config.json` reference
  - `advanced/cross-agent` — Claude/Codex/Copilot/Cursor/Gemini notes (consolidated)
- **Reference / Architecture** (demoted maintainer material)
  - `reference/troubleshooting` — failures, refusals, reading state, FAQ
  - `forge-bootstrap/overview|architecture|cli-reference|guides/integration` *(symlink)*
  - `epic-orchestration/overview|architecture|cli-reference|guides/integration` *(symlink)*

## 4. Content inventory

| Page (slug) | Source | Purpose |
| ----------- | ------ | ------- |
| `/` (`index.mdx`) | native | Splash: what FF is, pipeline diagram, entry cards |
| `start-here/install` | native | Install on Claude Code + other agents; install rauf |
| `start-here/quick-start` | native | End-to-end first feature in ~8 commands |
| `start-here/concepts` | native | Glossary + key concepts |
| `pipeline/overview` | native | 6-stage map; init/bootstrap/epic placement; diagram |
| `pipeline/init` | native | `forge-init`; bootstrap-vs-init decision aid |
| `pipeline/stage-1-prd` | native | PRD stage: command/inputs/outputs/review/next |
| `pipeline/stage-2-tech` | native | Tech-spec stage |
| `pipeline/stage-3-specs` | native | Implementation specs stage |
| `pipeline/stage-4-backlog` | native | Backlog stage |
| `pipeline/stage-5-loop` | native | Loop stage + rauf run/follow/stop + signals + diagram |
| `pipeline/stage-6-docs` | native | Docs stage |
| `pipeline/verify-and-fix` | native | Verify gate + forge-fix |
| `pipeline/dashboard` | native | `forge` navigator / status |
| `example/walkthrough` | native | Worked example with artifact snippets |
| `advanced/epics` | native | Stage 0 epics usage |
| `advanced/bootstrapping` | native | `forge-bootstrap` Mode A/B |
| `advanced/config` | native | `forge.config.json` full reference |
| `advanced/cross-agent` | native | Cross-agent usage notes (folds 5 stubs) |
| `reference/troubleshooting` | native | Troubleshooting / FAQ |
| `forge-bootstrap/overview` | symlink → `docs/architecture/forge-bootstrap/README.md` | Maintainer overview |
| `forge-bootstrap/architecture` | symlink | Maintainer architecture |
| `forge-bootstrap/cli-reference` | symlink | CLI reference |
| `forge-bootstrap/guides/integration` | symlink | Integration guide |
| `epic-orchestration/overview` | symlink → `docs/architecture/epic-orchestration/README.md` | Maintainer overview |
| `epic-orchestration/architecture` | symlink | Maintainer architecture |
| `epic-orchestration/cli-reference` | symlink | CLI reference |
| `epic-orchestration/guides/integration` | symlink | Integration guide |

**Dropped from the sidebar:** the 5 per-agent install pages (`agents/claude` …
`agents/gemini`) and the `guides/setup` stub. The per-agent repo docs
(`docs/agents/*.md`) remain in the repo and are linked from `advanced/cross-agent`;
their install content is consolidated there and in `start-here/install`.

**Diagrams (light + dark, via the committed `src/diagrams/*.json` build step):**

- `pipeline.{light,dark}.svg` — the end-to-end stage flow (landing + overview).
- `rauf-loop.{light,dark}.svg` — the Stage-5 fresh-context loop.

## 5. Verification plan

1. `cd docs-site && ./setup-docs.sh && node check-docs.mjs` — symlinks valid,
   manifest↔sidebar parity, no broken internal links, frontmatter present.
2. `cd docs-site && npm install && npm run build` — Astro build green with the
   GitHub Pages base path; diagrams render to light/dark SVGs.
3. Nav spot-check: Start Here → Quick Start → Stages 1–6 → Worked Example with no
   dead ends or placeholders.
4. Every documented command/config key cross-checked against the skill/reference
   files.
5. `bash scripts/validate.sh` to confirm the rebuild didn't break the repo gate.

---

*Final IA and results are reflected in `docs.manifest.json`, the native pages
under `src/content/docs/`, and the rebuild summary delivered with this change.*
