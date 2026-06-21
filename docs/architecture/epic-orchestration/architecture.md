---
title: "Epic Orchestration — Architecture"
---

# Epic Orchestration — Architecture

This document explains how Epic Orchestration is designed and why. For the
command surface see the [CLI Reference](./cli-reference.md); for how each
pipeline stage was modified see the [Integration Guide](./guides/integration.md).

## Design Goals

1. **Additive, zero-migration.** Existing standalone features keep their flat
   `{specsDir}/{feature}/` layout, commands, and state files unchanged. Epic
   behavior is gated entirely on epic membership.
2. **Deterministic where correctness matters.** Cycle detection, validation,
   atomic writes, name resolution, and status derivation are not things an LLM
   should do by eye. They live in one Python helper.
3. **One source of truth.** The manifest is authoritative for structure and
   contracts; everything else (the `EPIC.md` prose, the dashboard, the injected
   context) is derived from it or from per-feature pipeline state.
4. **Survives sessions.** The full epic state is reconstructable from files on
   disk with no in-memory state, correctly and interactively (<1s) for epics of
   up to 20 features.

## Component Overview

```
                     ┌──────────────────────────────┐
                     │  scripts/epic-manifest.py     │  ← deterministic core
                     │  (Python 3, stdlib only)      │     (Bash-invoked)
                     │                               │
   skills ───Bash──▶ │  resolve / validate /         │
   (forge-0-epic,    │  check-name / render-status / │
    forge-1..6,      │  add/remove/reorder/set-* )   │
    forge-verify,    └───────────────┬───────────────┘
    forge navigator)                 │ reads / atomically writes
                                     ▼
        specs/{epic}/epic-manifest.json   ← single source of truth
        specs/{epic}/EPIC.md              ← mirrored narrative + contracts
        specs/{epic}/{feature}/.pipeline-state.json  ← live status source
                                          (carries `epic` back-pointer)
```

Skills are prose; the helper is code. A skill that needs to resolve a name,
validate a graph, read live status, or mutate the manifest shells out to the
helper and surfaces its output. This mirrors the pre-existing
`scripts/validate-traceability.py` pattern.

## Key Design Decisions

### Deterministic manifest core in Python

Graph acyclicity, schema/dangling-ref validation, name→directory resolution,
global name uniqueness, path containment, live status derivation, and atomic
writes all live in `scripts/epic-manifest.py`. These requirements demand
repeatable correctness and sub-second performance for ≤20 features — an LLM
walking a dependency graph for cycles is non-deterministic and unverifiable.
Acyclicity uses a standard DFS/topological check (`O(V+E)`, trivially <1s).

**Rejected alternative:** prose-only (the skill reasons about cycles inline) —
rejected for non-determinism and the inability to guarantee atomicity or the
<1s target.

### Manifest as source; EPIC.md as generated narrative

Charters and the structured `exposes`/`consumes` arrays live in
`epic-manifest.json`. `EPIC.md` mirrors them as prose plus decomposition
rationale. Contract-drift checking and context injection read structured JSON
rather than parsing markdown — far less brittle. `forge-0-epic` keeps `EPIC.md`
in sync when it writes the manifest.

**Rejected alternative:** `EPIC.md` as source-of-truth with markdown-section
parsing — rejected as brittle for drift-diffing.

### No cached per-feature status

The manifest stores no per-feature `status` field. `render-status` opens each
member's `.pipeline-state.json` on every read and derives status live. The
guarantee this buys: edit a feature's pipeline-state file directly, render the
epic view, and it reflects the change — because there is nothing to refresh.

### Centralized name→directory resolution

A `shared-conventions.md` block instructs every stage skill to obtain the
feature directory via `epic-manifest.py resolve <name>` before any file I/O,
replacing hardcoded `{specsDir}/{feature}/`. This keeps the flat-vs-nested,
uniqueness, and path-containment logic in one place instead of duplicated across
~10 skills.

**Rejected alternative:** prose dual-path globbing per skill — rejected for
duplicating uniqueness/containment logic everywhere.

## Data Model

### `epic-manifest.json`

Schema: `references/epic-manifest-schema.json`.

```jsonc
{
  "schemaVersion": 1,
  "epic": "auth-overhaul",            // kebab-case, matches subtree dir name
  "description": "…",
  "status": "active",                 // active | paused | abandoned | complete
  "narrativeDoc": "EPIC.md",
  "createdAt": "ISO-8601",
  "updatedAt": "ISO-8601",            // bumped by every mutator on each write
  "features": [
    {
      "name": "token-service",        // kebab-case, globally unique
      "charter": "One-paragraph scope statement…",
      "dependsOn": ["config-store"],  // sibling feature names
      "exposes":  [
        { "name": "verifyJwt", "kind": "function|type|endpoint|module|event",
          "summary": "…" }
      ],
      "consumes": [
        { "from": "config-store", "name": "JWT_SECRET", "summary": "…" }
      ]
    }
  ]
}
```

`validate` enforces: unique `epic` and feature names; every `dependsOn` and
every `consumes.from` references a feature present in `features[]` (no dangling
refs); the `dependsOn` graph is acyclic; no name contains a path separator,
`..`, or absolute path. **No per-feature `status` field** — status is always
derived.

### Pipeline-state additions

Additive and optional (preserves zero-migration):

```jsonc
{ "epic": "auth-overhaul" }   // back-pointer; absent for standalone features
```

The `currentStage` enum and `stages` keys gain `forge-0-epic` and
`forge-verify-epic`. On any manifest-vs-back-pointer conflict, **the manifest
wins**; `forge-verify` epic mode (CHECK-E07) flags the inconsistency.

### `render-status` output

```jsonc
{
  "epic": "auth-overhaul", "status": "active",
  "features": [
    { "name": "config-store", "stage": "forge-1-prd", "status": "not-started",
      "blocked": false, "unmetDeps": [] },
    { "name": "token-service", "stage": "forge-1-prd", "status": "not-started",
      "blocked": true, "unmetDeps": ["config-store"] }
  ],
  "actionable": ["config-store", "audit-log"],
  "parallelEligible": ["config-store", "audit-log"],
  "rollup": { "complete": 0, "total": 4 },
  "nextCommand": "/feature-forge:forge-1-prd config-store"
}
```

## The Completion Rule

A single rule defines when a feature is **complete for orchestration**,
implemented once in `render-status` and reused by both the dependency gate and
the handoff:

```
stages.forge-5-loop.status == "complete"
  AND (forge-verify-impl is absent OR its status ∈ {"passed", "findings-applied"})
```

A feature whose `forge-verify-impl` is `findings-reported` (findings raised but
not yet fixed) is **not** complete and does **not** unblock dependents. At
handoff, the just-finished feature's implementation verification is offered as a
recommended-but-skippable step before unblocking dependents.

### Derived dependency sets

`render-status` computes, from the `dependsOn` graph:

- **actionable** — features whose every `dependsOn` is complete and that are not
  themselves complete.
- **parallelEligible** — actionable features that do not (transitively) depend
  on each other. Surfaced for *future* parallel execution; v1 execution is
  **serial** (the user picks one when several are unblocked). There is no
  separate `parallelGroup` field — the graph already expresses eligibility.

## Data Flow: Resolution

Every stage skill resolves a bare name before touching files:

1. Reject unsafe names (path separator, `..`, absolute, or failing the
   safe-name pattern) — **before any filesystem access**.
2. If `{specsDir}/{name}/.pipeline-state.json` exists → return that flat path.
3. Else if exactly one `{specsDir}/*/{name}/.pipeline-state.json` exists →
   return that nested path.
4. More than one match → `ambiguous` error listing all matching paths.
5. Zero matches → `not-found` error.

A directory counts as a **feature** only if it directly contains a
`.pipeline-state.json` (the *feature-shaped-dir bound*). Non-feature subtrees
(`.verification/`, `tests/`, fixture dirs, and the epic root itself — which
holds `epic-manifest.json` but no `.pipeline-state.json`) are never matched as
features. Standalone features resolve to their flat path with no epic logic
engaged.

### Pre-existing collisions vs. introduced collisions

An existing specs tree might already contain two features sharing a bare name —
a state that predates epic support. The resolver distinguishes *introducing* a
collision from *encountering* one:

- `check-name` (run by `forge-0-epic` before creating a member) hard-rejects any
  name that already exists anywhere, so no **new** collision is ever introduced.
- `resolve` (run by every stage) reports ambiguity **only** when a name matches
  more than one feature-shaped dir; a name matching exactly one dir always
  resolves cleanly.
- A latent pre-existing duplicate is surfaced non-fatally by `forge-verify` epic
  mode (CHECK-E08) and the navigator for manual cleanup — rather than aborting
  unrelated standalone commands.

## Robustness

- **Atomic writes.** Every mutation writes a temp file in the same directory
  then `os.replace` (atomic on POSIX). An interrupted write never leaves a
  partial manifest. Concurrent multi-session mutation is out of scope (single
  active writer assumed).
- **Corrupt / hand-edited manifest.** `validate` reports specific actionable
  findings (`cycle: a → b → a`, `duplicate feature name 'x' (also at …)`,
  `unknown dependsOn 'y' in feature 'x'`, `unsafe name '../z'`) rather than
  crashing. Skills present them and refuse to mutate until resolved.
- **Path containment.** The helper canonicalizes and asserts every resolved path
  stays within `{specsDir}` before reading/writing; violations are exit-2
  errors. All artifacts are trusted local developer files — the concern is safe
  handling of corrupt input, not adversarial defense.
- **Observability.** Every mutator bumps the manifest's `updatedAt` as part of
  the same atomic write. v1 keeps only the last-write timestamp — the git
  history of `epic-manifest.json` already provides a per-commit audit trail
  (each mutation is committed via the git-commit-after-stage protocol), so a
  separate in-manifest log would be redundant.

## When to Use Epics — and When Not To

**Use an epic when:**
- A change is too large or pervasive for one feature and naturally splits into
  ≥2 discrete features with real dependencies and shared contracts.
- You want forge to carry the thread of execution across sessions (what's done,
  what's next, what's blocked).

**Do NOT use an epic when:**
- The work is a single cohesive feature. A standalone feature has zero epic
  overhead — don't wrap one feature in an epic.
- Features would need **item-level** cross-dependencies (a backlog item in B
  depending on an item in A). That signals they should be one feature; epic
  dependencies are feature-granular only.
- You need parallel/worktree execution, autonomous chaining, nested epics, or a
  feature in multiple epics — all out of scope for v1.

## Scope Boundaries (v1)

Out of scope: cross-backlog item-level dependencies; autonomous (unconfirmed)
chaining between features; parallel execution of unblocked features;
merge/PR-status as a completion criterion; nested epics; a feature belonging to
multiple epics; migration tooling to move a standalone feature into an epic
(manual move + manifest edit is acceptable).
