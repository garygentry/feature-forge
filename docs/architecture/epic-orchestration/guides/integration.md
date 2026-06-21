---
title: "Integration Guide — Epic-Awareness Across the Pipeline"
---

# Integration Guide — Epic-Awareness Across the Pipeline

Epic Orchestration is woven into the existing forge pipeline as **conditional,
membership-gated** behavior. The thread through every stage is the same: resolve
the feature directory centrally, and *if* the feature has an `epic` back-pointer,
add epic behavior — otherwise do exactly what was done before.

This guide walks each touchpoint. The two shared building blocks live in
`references/shared-conventions.md`.

## Shared Building Blocks

### Feature Directory Resolution

Every stage skill obtains the feature directory by calling
`epic-manifest.py resolve <name>` instead of hardcoding `{specsDir}/{feature}/`.
The returned directory (`{resolvedFeatureDir}`) is used everywhere the skill
previously wrote the flat path. Standalone features resolve to their flat path
unchanged; nested epic members resolve to `{specsDir}/{epic}/{feature}/`. On an
ambiguous/missing/unsafe name the skill stops and surfaces the helper's finding
verbatim — it never falls back to a guessed path.

### Epic Context Injection

After resolving, the skill checks the feature's `.pipeline-state.json` for an
`epic` back-pointer.

- **Absent** → skip entirely (standalone behavior unchanged).
- **Present** → load exactly, and nothing transitive:
  1. `{specsDir}/{epic}/EPIC.md` — narrative + per-feature Contracts sections.
  2. This feature's **charter** + its `exposes`/`consumes` from the manifest
     (its contract obligations).
  3. **Direct** completed dependencies only — for each `name` in `dependsOn`,
     load that sibling's `PRD.md` and `tech-spec.md` *only if it is complete for
     orchestration*.

Transitive (indirect) dependencies are surfaced only through the direct deps'
Contracts sections in `EPIC.md`, never by loading their specs. This bounds
context size and keeps the injected set deterministic. The skill obtains the
contracts and live completion status of each dependency in one call via
`render-status`.

## Stage-by-Stage

### `forge-0-epic` — creation & edit (new stage)

`skills/forge-0-epic/SKILL.md` handles both modes in one skill:

- **Creation** (no manifest yet): an AskUserQuestion-driven decomposition
  interview produces the manifest + `EPIC.md` + one **charter** per feature
  (short scope + contract obligations only — no full PRDs). Member
  subdirectories are created empty, each with a `.pipeline-state.json` carrying
  the `epic` back-pointer, so the navigator and resolver can see them.
- **Edit** (manifest exists): add / remove / reorder features and change deps via
  the helper's atomic mutators, each re-validated for acyclicity, with a warning
  when a change affects in-flight or completed features.

After creation and after each edit, the git-commit-after-stage protocol commits
`{specsDir}/{epic}/` (manifest + `EPIC.md` + member state) atomically.

### `forge-1-prd` / `forge-2-tech` / `forge-3-specs` — context injection

All three resolve the directory centrally and inject epic context (above) before
authoring:

- **forge-1-prd:** inject before the interview.
- **forge-2-tech:** inject after reading the PRD; add epic paths to the
  `forge-researcher` dispatch; widen the cross-feature glob to also match
  depth-2 (`{specsDir}/*/*/tech-spec.md`).
- **forge-3-specs:** inject after reading PRD + tech-spec; thread the relevant
  `EPIC.md` sections and direct-dep tech-specs into each `forge-spec-writer`
  prompt; widen the spec glob to depth-2.

**Glob scoping:** the widened depth-2 globs are constrained to feature-shaped
directories (those containing a sibling `.pipeline-state.json`), so they never
match non-feature subtrees that happen to hold matching filenames (e.g.
`tests/fixtures/.../tech-spec.md`, a numbered file under `.verification/`).

### `forge-4-backlog` — backlog path composition

Resolves the directory centrally. With `backlogDir` **unset** (default), the
backlog lives at `{resolvedFeatureDir}/backlog.json` — unchanged for flat and
nested features. With `backlogDir` **configured**, forge-4 composes a per-feature
subpath `{backlogDir}/{feature}/` so each epic member's backlog stays
independent (a bare shared `backlogDir` would collide across members). The loop
runner (rauf) itself is unchanged.

### `forge-5-loop` — dependency gate + handoff

Two epic-only additions bracket the existing loop:

- **Dependency gate** (new Step 1b-epic, before the runner version gate): if the
  feature is an epic member, read the manifest, compute unmet deps via the
  completion rule, and if any are unmet, `AskUserQuestion`-warn with the list
  and require explicit confirmation to proceed. No back-pointer → gate skips.
- **Handoff** (new Step 6, after pipeline state is written `complete`): run
  `render-status`, announce completion, offer to run `forge-verify` impl on the
  just-finished feature (recommended, skippable), then present the actionable
  next feature(s) via `AskUserQuestion` — offering to author the chosen one's
  PRD if absent. Selection is **serial** when several are unblocked; there is no
  autonomous chaining. The completion write and any `updatedAt` bump are
  committed via the git-commit-after-stage protocol.

### `forge-6-docs` — epic-level doc offer

After the per-feature completeness check, if the feature is an epic member and
**all** members are complete, offer to synthesize an epic-level architecture
document at `{docsDir}/{epic}/` in addition to per-feature docs, sourced from
`EPIC.md`, the per-feature docs, and the manifest contracts. Per-feature
behavior is unchanged. (For a standalone feature — like `epic-orchestration`
itself — this offer never fires.)

### `forge` navigator — dashboard & discovery

- **Named-epic argument** → epic dashboard rendered from `render-status` (graph,
  per-feature stage/status, blocked vs actionable, next command).
- **No-arg discovery** → 2-tier listing: epics (with a `complete/total` rollup)
  above standalone features. Epic directories are recognized by the presence of
  `epic-manifest.json`; their nested `.pipeline-state.json` files are attributed
  to the epic, not listed as standalone.
- **Lifecycle verbs** (`pause` / `resume` / `abandon`) extend to epics. Pausing
  or abandoning an epic does **not** silently mutate member features' own states
  — the relationship is surfaced explicitly.

### `forge-verify` — epic mode

A new `epic` mode loads the manifest + `EPIC.md` + each member
`.pipeline-state.json`, runs CHECK-E01..E08 via a single `forge-verifier`, writes
`{specsDir}/{epic}/.verification/VERIFY-epic-{date}.md`, and records
`stages.forge-verify-epic`. Checks: valid manifest schema (E01), acyclic graph
(E02), no dangling `dependsOn` (E03), charter coverage (E04), non-empty
exposes/consumes per feature (E05), `EPIC.md`-vs-manifest contract drift for
completed features (E06), back-pointer ↔ manifest consistency (E07), global name
uniqueness (E08). E01/E02/E03/E08 delegate to `epic-manifest.py validate`;
E04/E05/E06/E07 are verifier judgment.

### `forge-fix`

Resolves the directory centrally; otherwise unchanged.

## The Loop Runner (rauf) Is Untouched

Backlogs remain per-feature and independent; dependencies are resolved only at
feature granularity, *before* the loop launches. No rauf change, no
backlog-schema change. This is what keeps epic support purely additive at the
execution layer.

## End-to-End Walkthrough

```
/feature-forge:forge-0-epic auth-overhaul
   → interview → manifest + EPIC.md + charters + empty member dirs (committed)

/feature-forge:forge-1-prd config-store      # no deps → actionable immediately
/feature-forge:forge-2-tech config-store     # epic context injected each stage
…
/feature-forge:forge-5-loop config-store
   → completion handoff: offers impl-verify, identifies `token-service`
     as newly actionable, offers to author its PRD

/feature-forge:forge token-service           # blocked earlier, now actionable
   → forge-5-loop token-service shows NO dependency warning (config-store done)

/feature-forge:forge                          # dashboard: 2/4 complete, next command

# Meanwhile, a standalone feature elsewhere in specs/ behaves exactly as before —
# no epic context, no gate, no handoff.
```
