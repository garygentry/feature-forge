---
title: "Context Efficiency"
---

# Context Efficiency

> This is **maintainer-facing** documentation for a refactor of the pipeline's own
> instruction surfaces. If you are looking for how to *use* the pipeline, start with the
> [main README](https://github.com/garygentry/feature-forge#the-pipeline-at-a-glance).

Every forge stage session pays a fixed instruction-token cost before it touches a single
feature artifact — the skill body, the shared conventions, whatever reference files the
body points at. Because the pipeline deliberately recommends a fresh session at each stage
boundary, that fixed cost is re-paid per stage. Context Efficiency reclaims the part of it
that was being paid for content the caller never used.

It is a **behavior-preserving optimization**, not a feature. Nothing about how you run the
pipeline changed: same commands, same prompts, same gates, same guards, same outputs. What
changed is *which files get opened*, and who computes the JSON that used to be
hand-authored.

The work shipped as **five independently revertible units**:

| Unit | What it does | Targeted invocation |
|------|--------------|---------------------|
| **R1** | Splits the verification checklists into one file per verify mode, plus an orchestrator-only findings template. | A `forge-verifier` leaf subagent |
| **R3** | Gates the navigator's `process-overview.md` read behind "how does the pipeline work" questions. | A routine dashboard/status render |
| **R4** | Replaces every hand-authored `.pipeline-state.json` edit with seven targeted `forge-session.py` state verbs. | Any stage that writes pipeline state |
| **R5** | Adds `forge-session.py effective-config`, which resolves the `loopRunner` block from schema defaults so no skill reads the config schema for them. | `forge-4-backlog`, `forge-5-loop` |
| **R6** | Splits the loop runner contract into always-loaded and agent-conditional halves. | A loop launch with agent selection off |

A sixth candidate, **R2** (deduplicating the repeated plugin-root prelude *within* a
file), was **scoped out and does not ship** — see [architecture.md](./architecture.md#r2--scoped-out).

## What actually changed for you

Almost nothing, by design. Two things are worth knowing:

**1. There is a new diagnostic.** `effective-config` answers "what `loopRunner`
configuration will the loop actually use?" without you reading the config schema and
merging defaults in your head:

```bash
python3 <plugin-root>/scripts/forge-session.py effective-config \
  --config ./forge.config.json --json
```

Every `loopRunner` field is present in the output — the defaults come from
`references/forge-config-schema.json`, with your `forge.config.json` overrides merged on
top. A missing or corrupt `forge.config.json` resolves to pure defaults and still exits 0;
only an unreadable schema is fatal (exit 2). Full contract in the
[CLI Reference](./cli-reference.md#effective-config).

**2. Pipeline state is written by a script now, not by a model.** Stage skills call
`state-enter`, `state-complete`, and friends instead of editing
`.pipeline-state.json` by hand. You should never notice this except in its consequences:
the version bump, the `updatedAt` refresh, and the downstream staleness cascade are
computed deterministically, and every successful write is atomic and schema-conformant by
construction. If a write refuses, it refuses loudly with exit 2 and leaves the file
byte-intact rather than half-updating it.

## Key Concepts

**Instruction load** — the tokens a session spends on guidance (skill bodies, reference
files, schemas) before it reads any feature artifact. This is the quantity the feature
reduces. It is distinct from *artifact* tokens, which are the real work.

**Progressive disclosure** — the pipeline's existing design principle: a skill body stays
small and points at reference files, which load only when their instruction is reached.
The audit that produced this feature found the principle sound but the *granularity* off
in a handful of places — files that loaded whole when the caller needed a slice.

**Targeted invocation** — the specific call a unit is optimizing. Savings are only
meaningful when attributed to one: R1's is a single verifier leaf, R3's is a routine
dashboard render, R6's is a gate-off loop launch. A unit can be net-negative on one
invocation and net-positive on another, and both figures belong in the ledger.

**Always-paid cost** — instruction text that every invocation loads, including the ones
that do not benefit. Gating a read behind a condition adds a small always-paid clause in
exchange for removing a large conditional load; that trade is the shape of R3 and R6, and
the cost side is counted against the saving rather than omitted.

**State verb** — one of the seven `forge-session.py` subcommands that write
`.pipeline-state.json`. Each covers exactly one touch point (entry stamp, artifact append,
completion, branch, note, deferred decision, epic change request) and nothing else.

**Drift guard** — a stdlib pytest that fails when a split or relocated surface stops
matching its contract: a checklist file losing a check, a reference file losing its
citation, a skill body crossing the line cap. Every unit here shipped with one, because
every unit created a new way for two files to disagree.

## Entry Points

| Entry point | Description |
|-------------|-------------|
| `scripts/forge-session.py` | Host for both new script capabilities — the seven `state-*` verbs (R4) and `effective-config` (R5). |
| `references/pipeline-state-schema.json` | Unchanged as the contract for `.pipeline-state.json`; no longer read per stage, still the CI source of truth. |
| `references/forge-config-schema.json` | Unchanged; read at runtime *by the script* for `loopRunner` defaults, never by a skill. |
| `skills/forge-verify/references/verification-checklists/` | Six per-mode checklist files (R1). A verifier leaf reads exactly one. |
| `skills/forge-verify/references/findings-template.md` | Orchestrator-only findings material (R1) — never loaded into a verifier context. |
| `skills/forge-5-loop/references/runner-contract.md` | The always-loaded half of the loop runner contract (R6). |
| `skills/forge-5-loop/references/agent-selection.md` | The agent-conditional half (R6) — read only when `loopRunner.agentArgument` is set. |
| `references/process-overview.md` | Unchanged; the navigator's read of it is now conditional (R3). |

## Measured Results

Each unit had to show a measured net reduction on its targeted invocation against a
baseline re-measured at implementation time — not against the original audit snapshot,
which had drifted. The method is line/word counts over the canonical surfaces at
~1.3 tokens per word, with read frequency taken from a 188-session transcript corpus.

| Unit | Targeted invocation | Net delta |
|------|--------------------|-----------|
| R1 | one verifier leaf (per mode) | **−4,736 … −5,810 tok** |
| R1 | verify orchestrator's template read | **−5,065 tok** |
| R3 | routine dashboard render | **−1,684 tok** (+40 on an architecture question) |
| R4 | a `forge-6-docs` invocation that would have read the state schema | **−1,363 tok** |
| R5 | `forge-4-backlog` / `forge-5-loop` launch | **−2,579 / −2,587 tok** |
| R6 | gate-off loop launch | **−1,151 tok** (+98 gate-on) |

Two of those numbers come with honest caveats that are easy to lose:

- **R4 and R5 do not save tokens per stage.** The schemas they stop loading were read
  2× and 1× respectively across the whole 188-session corpus — not once per stage. The
  figures above are the static delta on the invocations where the read *does* happen.
  Both units are justified by determinism and drift removal, which hold at any read
  frequency.
- **R6's saving is not the default posture.** The gate condition is a non-empty
  `loopRunner.agentArgument`, and the config schema *defaults* that field to
  `--agent {agent}`. On a default-configured project the gate is on, the conditional file
  opens, and R6's realized instruction-load saving is approximately zero (marginally
  negative). The −1,151 applies only where the field is explicitly blanked. See
  [architecture.md](./architecture.md#r6--runner-contract-split).

## Further Reading

- [Architecture](./architecture.md) — each unit's design, load paths, and trade-offs; what was scoped out and why.
- [CLI Reference](./cli-reference.md) — every new `forge-session.py` subcommand: flags, output, exit codes.
- [Integration Guide](./guides/integration.md) — writing a skill step that calls a state verb, keeping a new reference file discoverable, and which drift guard to extend.
