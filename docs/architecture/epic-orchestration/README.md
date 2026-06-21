---
title: "Epic Orchestration"
---

# Epic Orchestration

> New to the pipeline? Start with the [main README's pipeline overview](https://github.com/garygentry/feature-forge#the-pipeline-at-a-glance);
> epics are an optional Stage 0 layered on top of it.

Epic Orchestration lets you group several related forge features into a single
named **epic** with declared dependencies, a shared contract document, and a
prompted thread-of-execution that carries you from one feature to the next.

Some changes are too large or pervasive to be one forge feature. Splitting them
into discrete features works — but without an epic, nothing records the
decomposition, the dependency edges, the shared contracts, or what to do next
when a feature finishes. You end up holding that orchestration in your head
across sessions. An epic puts it on disk: a machine-readable manifest, a
human-readable narrative (`EPIC.md`), and orchestration behavior woven into the
existing pipeline stages.

Epic support is **purely additive**. When no epic is involved, every existing
single-feature flow is byte-for-byte unchanged — same commands, same flat
`{specsDir}/{feature}/` layout, same state files, no migration.

## Quick Start

Create an epic by running the new stage-0 skill and answering the decomposition
interview:

```
/feature-forge:forge-0-epic auth-overhaul
```

This produces an epic subtree:

```
specs/auth-overhaul/
├── epic-manifest.json        # machine-readable source of truth
├── EPIC.md                   # narrative: goal, rationale, contracts
├── config-store/             # one empty member-feature dir per feature…
│   └── .pipeline-state.json  #   …each carrying an `epic` back-pointer
├── token-service/
│   └── .pipeline-state.json
└── …
```

From there, drive each member feature through the normal pipeline. Stages
resolve a bare feature name to its nested directory automatically, so the
commands look exactly like standalone usage:

```
/feature-forge:forge-1-prd config-store     # epic context auto-injected
/feature-forge:forge-2-tech config-store
…
/feature-forge:forge-5-loop config-store    # completing this prompts the handoff
```

Check the whole effort at a glance:

```
/feature-forge:forge auth-overhaul          # epic dashboard
/feature-forge:forge                         # no-arg: epics + standalone features
```

## Key Concepts

**Epic** — a named, self-contained subtree (`{specsDir}/{epic}/`) grouping
related features. Has a lifecycle status (`active | paused | abandoned |
complete`).

**Member feature** — a normal forge feature living at
`{specsDir}/{epic}/{feature}/`. It runs the standard PRD → tech-spec → specs →
backlog → loop → docs pipeline; epic membership only *adds* context injection,
a dependency gate, and a completion handoff.

**Manifest (`epic-manifest.json`)** — the single machine-readable source of
truth for membership, dependency edges (`dependsOn`), per-feature **charters**,
and structured **`exposes` / `consumes`** contracts. `EPIC.md` mirrors the
contracts as prose; on any disagreement, the manifest wins.

**Charter** — a one-paragraph scope statement plus contract obligations,
assigned to each feature at epic-creation time. Full PRDs/specs are authored
*just-in-time* when a feature becomes actionable, so downstream specs build
against real upstream contracts rather than guesses.

**Contracts (`exposes` / `consumes`)** — a lightweight structured format
(`{name, kind, summary}` for exposes; `{from, name, summary}` for consumes)
declaring what each feature provides to dependents and what it relies on from
dependencies. Being structured (not free-form prose) makes contract-drift
checking tractable.

**Complete for orchestration** — a feature is considered done (and unblocks its
dependents) when `forge-5-loop` is `complete` AND implementation verification is
either absent or `passed`/`findings-applied`. Merge/PR status is not tracked in
v1. See [architecture.md](./architecture.md#completion-rule).

**Live status derivation** — the manifest stores **no** cached per-feature
status. Epic status is recomputed from each member's own `.pipeline-state.json`
on every read, so editing a feature's state file is reflected in the dashboard
with no refresh step.

## The Deterministic Core

All logic that must be repeatable and correct — acyclicity validation, corrupt-
manifest detection, atomic writes, global name uniqueness, path containment,
name→directory resolution, and live status derivation — lives in a single
stdlib-only Python helper, `scripts/epic-manifest.py`. Skills never eyeball a
dependency graph for cycles; they shell out to the helper. See the
[CLI Reference](./cli-reference.md).

## Package / Entry Points

| Entry point | Description |
|-------------|-------------|
| `scripts/epic-manifest.py` | Deterministic manifest core — 9 subcommands (resolve, validate, check-name, render-status, and atomic mutators). |
| `skills/forge-0-epic/SKILL.md` | Epic creation + edit stage (decomposition interview / add-remove-reorder). |
| `references/epic-manifest-schema.json` | JSON Schema for `epic-manifest.json`. |
| `references/shared-conventions.md` | **Feature Directory Resolution** and **Epic Context Injection** blocks consumed by every stage skill. |
| `references/pipeline-state-schema.json` | Adds the optional `epic` back-pointer and the `forge-0-epic` / `forge-verify-epic` stage keys. |

## Further Reading

- [Architecture](./architecture.md) — design decisions, data model, data flow, the completion rule.
- [CLI Reference](./cli-reference.md) — every `epic-manifest.py` subcommand, flags, output, and exit codes.
- [Integration Guide](./guides/integration.md) — how epic-awareness threads through each pipeline stage.
