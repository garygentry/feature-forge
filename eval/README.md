# eval/

Two advisory harnesses. Both exit 0 on a low score and on a missing prerequisite — the
only non-zero exit is a harness bug. Neither is a correctness gate.

| Harness | Measures | Needs | Runs in CI |
|---|---|---|---|
| `run-eval.py` | **Trigger accuracy** — does a model pick the right skill from the `skills/*/SKILL.md` descriptions? | `ANTHROPIC_API_KEY` | yes (`.github/workflows/eval.yml`) |
| `run-compliance-eval.py` | **Stage-drive compliance** — once a skill *is* driving, does the model honor the contract? | the `claude` CLI on `PATH` | no — local only, by design |

## `run-eval.py` — trigger accuracy

```bash
python3 eval/run-eval.py [--json]
```

Scores each `eval/fixtures/<skill>.json`: a `shouldTrigger` prompt is correct when the
expected skill is chosen, a `shouldNotTrigger` prompt is correct when it is not. Judged
by a pinned Haiku model. Prints `skipped (no key)` and exits 0 without a key.

## `run-compliance-eval.py` — stage-drive compliance

```bash
python3 eval/run-compliance-eval.py [--probe stage-exit|r2-prelude|all]
                                    [--models A,B] [--n N] [--variants cold,warm]
                                    [--json] [--out FILE]
```

Reports a **rate over N runs per model**, not pass/fail — the failure mode it exists to
measure is intermittent, so a single run says nothing. Default models are the Claude 5
adaptation program's subject and its known-good reference (`claude-opus-5`,
`claude-opus-4-8`).

**Probe 1 — `stage-exit`.** Builds a throwaway repo parked at the `forge-1-prd` close
(verify recorded fresh, so `verifyGate` is `none` and no `AskUserQuestion` gate is in
play), drives the real stage-closing instructions in a fresh headless session, and scores
the last assistant output against `references/stage-exit-protocol.md`: sentinel present,
nothing after it, next-stage command inside a fence, block byte-identical to the script's,
and `forge-session.py stage-exit` actually run (checked against the tool transcript, not
inferred from the prose). Two variants — `cold` hands over only the closing step; `warm`
makes the model do the stage's real closing work first, so there is something to summarize
when it arrives at the exit.

**Probe 2 — `r2-prelude`.** Applies the R2 transform from
`specs/context-efficiency/05-instruction-relocations.md` §1.5 to a real skill body — first
plugin-root prelude kept byte-verbatim, later call sites reduced to the compact form — then
asks the model to execute a later call site and checks whether the command it *runs*
reconstructs the resolver byte-identically. A drifted-but-working resolver is reported
separately from a broken one.

### Why it is not in CI

Each run is a real session against a real model: roughly **$0.70–$1.00 and ~60s**, so the
default sweep (2 models × 3 cells × 5 runs) is about **$22 and 40 minutes**. It also needs
the `claude` CLI and interactive-grade credentials, which a CI runner does not have. Run it
locally when changing a stage's exit path, and keep the JSON (`--out`) as the before/after
baseline.

### Reading a result

`compliant` is all-criteria-pass for that run; the per-criterion rates below it say *which*
part of the contract slipped. A run that could not produce a usable transcript is counted
as `unscored`, never as a failure — it would otherwise let a flaky driver masquerade as a
model regression.

### What this probe cannot see — and the field capture that covers it

Probe 1 runs fresh headless sessions of 4–16 turns against one authoring stage on the
`verifyGate: none` path. Three conditions are outside it by construction:

- **Real interview-length context.** An actual `forge-1-prd` run accumulates tens of
  thousands of tokens before the exit. The `warm` variant is the closest this harness gets
  and it is not close. If drift is a function of accumulated context, the probe sits below
  the threshold.
- **The interactive gates.** `verifyGate: standard` and in-stage auto-verify are
  `AskUserQuestion` surfaces a headless session cannot answer.
- **The other authoring stages** and the `forge-5-loop` bespoke exits.

Rather than approximate these synthetically, record them from real runs — every pipeline
stage you drive is a free observation at exactly the context length the probe cannot reach.

**Procedure.** At each stage exit, append one row to `eval/field-observations.md`:

| Field | Value |
|---|---|
| date · model · stage | e.g. `2026-07-28 · opus-5 · forge-4-backlog` |
| approx. context at exit | from `forge-session.py context-usage`, or the session indicator |
| sentinel was last output | yes / no |
| anything after the sentinel | none, or quote it |
| NEXT-STEPS block verbatim | yes / no — if no, quote the diff |
| `stage-exit` actually run | yes / no |

A `no` in any of the last four rows is the evidence the probe cannot produce. Two or three
of them reopen the case for a `Stop`-hook sentinel guard (chunk 5a / B1) on the right kind
of evidence; a clean run of stages is two independent instruments agreeing.
