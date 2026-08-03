---
title: "Stage Exit Coverage"
---

# Stage Exit Coverage

> This is **maintainer-facing** documentation for the pipeline's own stage-closing
> machinery. If you are looking for how to *use* the pipeline, start with the
> [main README](https://github.com/garygentry/feature-forge#the-pipeline-at-a-glance).

Every forge stage ends by telling you exactly one thing: what to do next. Stage Exit
Coverage makes that closing **deterministic and complete** for every pipeline-advancing
skill — the seven production stages `forge-0-epic` … `forge-6-docs` plus the two branch
skills `forge-verify` and `forge-fix` — by computing the whole exit in a script
(`forge-session.py stage-exit`) instead of having each skill hand-roll a "Next steps:"
list.

Before this feature, the scripted exit contract reached only `forge-0-epic` through
`forge-4-backlog`. The paths most likely to branch or divert were the ones left
uncovered, and each produced a concrete, user-visible failure:

| # | Symptom | Cause |
|---|---------|-------|
| **#172** | A skill prescribed a `stage-exit` command the script then rejected. | The CLI accepted only stages 0–4; `forge-5-loop`/`forge-6-docs` invocations exited 2. |
| **#176** | A verify or fix diversion finished and silently dropped the pipeline thread. | `forge-verify`/`forge-fix` had no complete terminus, so a successful audit lost the production stage it served. |
| **#175** | Epic edit-mode routed a *progressed* member back to `forge-1-prd`. | The exit ignored the member's actual state and always named the first stage. |
| **#163** | A configured in-stage auto-verify vanished without a trace. | If the model dropped the `runInStageVerify` directive, an *owed* verify was indistinguishable from one that was never scheduled. |

Stage Exit Coverage closes all four. Every advancing exit now routes through one script
that decides freshness, gate form, host wording, branch rejoin, loop/docs handoff, and
the next command from live state — and persists auto-verify debt to disk *before* control
can be lost, so a dropped dispatch stays visible.

The change is **behavior-preserving for stages 0–4**. Their user-visible prompts,
verify-gate routing, directives, host translations, and sentinel placement are unchanged,
except where #175 corrects epic edit-mode routing and two ordering fixes apply everywhere
(see [Verify-first ordering](#verify-first-ordering) below).

## Quick Start

A stage skill closes by running the **Scripted Stage Exit** — one stamped block that
shells out to the script and then obeys the directives it prints:

```bash
python3 <plugin-root>/scripts/forge-session.py stage-exit \
  --feature widget-search --stage forge-2-tech \
  --specs-dir ./specs --host claude --verify-capability interactive
```

The script emits a machine-readable **DIRECTIVES** object and, when this call owns the
terminal block, the exact **NEXT-STEPS** text the skill prints verbatim as its last
output — ending in the sentinel line `─ forge: end of stage ─`, with nothing after it.

Stages with a multi-way result pass an `--outcome`; branch skills pass an `--owner` and
the production stage they served:

```bash
# A loop that ran out of iterations resumes the loop, not the next stage:
… stage-exit --feature widget-search --stage forge-5-loop --outcome partial …

# A direct forge-fix that re-verified clean rejoins the stage it served and owns the block:
… stage-exit --feature widget-search --stage forge-fix --owner direct \
             --outcome reverified --served-stage forge-2-tech …
```

Inspect the decision without printing anything by adding `--json`:

```bash
python3 <plugin-root>/scripts/forge-session.py stage-exit \
  --feature widget-search --stage forge-2-tech --host claude \
  --verify-capability manual --json
```

Full flag reference and per-stage matrix are in the [CLI Reference](./cli-reference.md).

## Key Concepts

**Scripted Stage Exit** — the single stamped block every covered skill closes with. It
runs `stage-exit`, obeys the emitted directives in a fixed order, and (for a direct owner)
prints the script-generated NEXT-STEPS block verbatim. It replaces nine bespoke
"Next steps:" prose blocks with one deterministic contract.

**Directives** — the machine-readable object the script emits (`StageExitDirectives`). It
carries everything the old prose asked the model to compute: effective auto-verify, verify
freshness, gate form, host wording, branch rejoin target, loop/docs routing, and the
primary/deferred command pair. A directive is an *instruction to execute*, never a question
to re-derive. See [architecture.md](./architecture.md#the-directive-payload).

**Terminal ownership** — exactly one exit in any chain prints the final
sentinel-terminated block. A direct exit (`terminalOwnedBy: "self"`) prints it; a nested
auto-verify/auto-fix call (`terminalOwnedBy: "outer"`) prints **nothing** terminal and
returns its result to the outer authoring stage. This is what keeps a nested verify from
emitting a competing sentinel inside an outer stage's exit (REQ-EXIT-04).

**Served stage and rejoin** — a `forge-verify` or `forge-fix` diversion has no artifact and
no successor of its own; it routes from the production stage it *served*. That stage is
passed explicitly with `--served-stage`, or inferred from `--verify-mode` when the mapping
is unique, or the call **fails closed** rather than guessing (REQ-ROUTE-03). Every
recovery/defer route carries the served stage forward, so a successful audit never loses
the pipeline thread (#176).

**Verify-first ordering** — while a stage's verification is outstanding and not explicitly
skipped, the *verify* command is the single authoritative primary action; the downstream
production command is demoted to unfenced "after it passes" prose. No path advances past an
unresolved verify without a pass or an explicitly recorded skip (REQ-EXIT-06).

**Auto-verify debt (`auto-verify-pending`)** — when config makes in-stage auto-verify
effective for a stage, the script writes an `auto-verify-pending` marker to pipeline state
**before** it emits the `runInStageVerify` directive. If the dispatch is dropped — model
non-adherence, a crash, compaction — the debt is still on disk, distinct from "never
scheduled," and the navigator catch-up can fire later (#163, REQ-DEBT-01/04).

**Host vs. capability** — two independent inputs. `--host` (`claude` | `pi` | `generic`)
selects command syntax and fresh-session wording *only*. `--verify-capability`
(`interactive` | `manual`) says whether the caller may run an interactive gate and dispatch
a clean-room verifier. A host never implies a capability: a capable Pi session is
`interactive`; a Claude session that may not dispatch is `manual` (REQ-EXIT-07).

**Coverage guard** — an explicit allow-list (`CANONICAL_EXIT_SITES` in
`tests/test_stage_exit_protocol.py`) naming exactly the nine skills and the canon files
that own each terminus. It is an allow-list, not a prefix scan: a new advisory
`forge-something` skill is not silently covered, and a new advancing skill cannot land
without an intentional edit to both the `ExitStage` domain and this table (REQ-GUARD-01/02).

## The Deterministic Core

All logic that must be repeatable — stage/outcome/owner validation, served-stage inference,
verify-state classification, the scheduling boundary for auto-verify debt, gate selection,
host command translation, branch rejoin, and loop/docs live routing — lives in one
stdlib-only function, `stage_exit()` in `scripts/forge-session.py`. Given identical state,
config, host, served stage, and outcome, it produces byte-identical directives and
NEXT-STEPS (REQ-REL-01). Skills never reason about routing; they shell out and obey. See the
[CLI Reference](./cli-reference.md) and [architecture.md](./architecture.md).

## Entry Points

| Entry point | Description |
|-------------|-------------|
| `scripts/forge-session.py` | Host for the feature: the `stage-exit` verb + `stage_exit()`, the `auto-verify-pending` scheduling boundary, `state-verify`'s new status, duplicate-key config warnings, and full-hash write validation. |
| `references/stage-exit-protocol.md` | The single source of truth for the closing contract: the canonical scripted stamp, directive consumption order, host/capability rules, and the owner token. |
| `references/shared-conventions.md` | The `state-*` verb protocol (incl. `state-verify`) and the Verify Capability section every stage consumes. |
| `skills/forge-0-epic/SKILL.md` … `skills/forge-6-docs/SKILL.md`, `skills/forge-verify/SKILL.md`, `skills/forge-fix/SKILL.md` | The nine stamp sites that close through the scripted exit. |
| `references/pipeline-state-schema.json` | Adds `auto-verify-pending` to the `verifyEntry.status` enum; the contract for state the exit reads and writes. |
| `eval/fixtures/compliance/verify-fix-reverify.json` | The compliance fixture that drives verify → fix → re-verify and scores that exactly one terminal sentinel emerges (REQ-EVAL-01/02). |

## Further Reading

- [Architecture](./architecture.md) — the directive payload, verify-first ordering, the scheduling boundary, branch rejoin, loop/docs live routing, and state/provenance integrity.
- [CLI Reference](./cli-reference.md) — every `stage-exit` flag, the per-stage flag matrix, exit codes, and the emitted directive fields.
- [Integration Guide](./guides/integration.md) — stamping the scripted exit in a skill, consuming directives in order, the owner token, extending coverage, and the drift guards.
