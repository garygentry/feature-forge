# eval/

Two advisory harnesses. Both exit 0 on a low score and on a missing prerequisite — the
only non-zero exit is a harness bug. Neither is a correctness gate.

| Harness | Measures | Needs | Runs in CI |
|---|---|---|---|
| `run-eval.py` | **Trigger accuracy** — does a model pick the right skill from the `skills/*/SKILL.md` descriptions? | `ANTHROPIC_API_KEY` | yes (`.github/workflows/eval.yml`) |
| `run-compliance-eval.py` | **Stage-drive compliance** — once a skill *is* driving, does the model honor the contract? | the `claude` CLI on `PATH` | no — local only, by design. Its fixture, transcript parser, and scorers are covered by `tests/test_compliance_eval.py`, which *does* run in CI (offline, no model, no key). |

## Quick invocations

The compliance eval is the **regression oracle for prose changes** (#268 / #265 P0.3).
Every PR that touches `skills/*/SKILL.md` body text or the two shared references
(`references/stage-exit-protocol.md`, `references/shared-conventions.md`) records a
result from one of these before merge (see `AGENTS.md` § Prose-change gate).

```bash
# Fixed-budget probe of one contract, one model, N=5 — ~$14–20, ~10 min.
python3 eval/run-compliance-eval.py --probe stage-exit --n 5 --models claude-opus-5 \
  --json --out eval/last-stage-exit.json

# All four probes, both default models, N=5 — the shape of the recorded baseline.
python3 eval/run-compliance-eval.py --probe all --n 5 --json \
  --out eval/last-all.json

# The narrowest useful probe for a diversion-routing change (verify → fix → re-verify).
python3 eval/run-compliance-eval.py --probe branch-path --n 5 --models claude-opus-5 \
  --json --out eval/last-branch-path.json
```

Absent the `claude` CLI on `PATH`, the harness prints `stage-drive compliance eval: skipped (no driver)`
and exits 0 — the only non-zero exit is a harness bug. The full-cell cost table is at
[§ Why it is not in CI](#why-it-is-not-in-ci); the recorded numbers to compare against are
in [`docs/claude-5/phase-0-compliance-baseline.md`](../docs/claude-5/phase-0-compliance-baseline.md)
(measurements after that landing are appended there per PR).

Also runnable from Actions on demand — `Actions → stage-drive compliance eval (on-demand)
→ Run workflow`, choose branch and probe. Advisory only; the workflow never blocks a PR.

---

## `run-eval.py` — trigger accuracy

```bash
python3 eval/run-eval.py [--json]
```

Scores each `eval/fixtures/<skill>.json`: a `shouldTrigger` prompt is correct when the
expected skill is chosen, a `shouldNotTrigger` prompt is correct when it is not. Judged
by a pinned Haiku model. Prints `skipped (no key)` and exits 0 without a key.

## `run-compliance-eval.py` — stage-drive compliance

```bash
python3 eval/run-compliance-eval.py [--probe stage-exit|r2-prelude|branch-path|all]
                                    [--models A,B] [--n N] [--variants cold,warm]
                                    [--json] [--out FILE]
```

`--variants` selects `stage-exit` variants only. The `branch-path` scenarios are fixed by
`eval/fixtures/compliance/verify-fix-reverify.json` and are always both reported.

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

**Probe 3 — `branch-path`.** Drives a whole verify → fix → re-verify *diversion* and scores
whether the model closed every step through the scripted contract and rejoined the
production stage the diversion served. Two scenarios, reported as separate cells:
`branch-path/successful-rejoin` (re-verify passes, so the final direct exit fences the
production successor) and `branch-path/recovery` (re-verify reports further findings, so the
final direct exit fences the deterministic `forge-fix` recovery command for the *same* served
stage). Eight criteria per run — `ordered_command_results`, `all_commands_succeeded`,
`exactly_one_sentinel`, `nested_steps_emitted_no_sentinel`, `nothing_after_sentinel`,
`next_command_fenced`, `block_verbatim`, `correct_rejoin_or_recovery`.

**A branch run is scored on ordered command *results*, never on prose.** Each expected
`forge-session.py stage-exit` call must appear as a tool request that was *paired with a
seen, non-error, zero-exit tool result*, in the fixture's order, with no unexpected scripted
exit in between. A model that narrates "I ran the exit and it rejoined tech" without a
matching result scores zero on `ordered_command_results` — a *requested* command is not a
*run* command, and a claimed one is not either. Ground truth for `block_verbatim` and
`correct_rejoin_or_recovery` is derived by executing the real CLI against a separate
throwaway repository, so nothing about the expected block is hand-written in the fixture.

### The linear baseline is not evidence for branch compliance

The original `stage-exit/cold` and `stage-exit/warm` cells measure **one authoring stage —
`forge-1-prd` — on the already-scripted linear path**: artifact written, verification already
fresh, one scripted exit, one terminal block. That was the only path scripted when the
baseline was recorded. It says nothing about what a model does when the pipeline *diverges*
into `forge-verify`/`forge-fix` and has to find its way back, which is the failure this
feature exists to close.

So:

- **The linear baseline is not evidence for verify/fix diversion compliance.** A high
  `stage-exit/cold`|`warm` rate does not license a claim that "the pipeline complies".
- **`branch-path/successful-rejoin` and `branch-path/recovery` are separately reported
  cells.** Do not average them into the linear cells, and do not present them as replacements
  for — or as a like-for-like comparison against — the linear numbers. They score a different
  path, a different number of exits, and a different criterion set (eight, not five). A single
  blended "compliance rate" across all four cells is a meaningless number.
- **Historical linear results stand as recorded.** They remain valid measurements of the path
  they measured; nothing here restates or revises them.

The harness itself stays advisory and local-only for every probe. The parts that can be
pinned without a model — the fixture and its strict loader, the transcript request/result
pairing, the ordered evidence matcher, and `score_branch_path` against twelve offline
negative transcripts and two positives — are hard-tested by `tests/test_compliance_eval.py`
in CI, with no live model, no network, and no API key.

### Why it is not in CI

Each run is a real session against a real model. A linear or prelude run is roughly
**$0.70–$1.00 and ~60s**; a `branch-path` run drives four scripted exits instead of one, so
budget at least **$1.00–$1.50 and ~90s** for it (an estimate, not a recorded measurement).

The formula is `models × cells × N`, summed per cell:

| `--probe` | Cells | Runs at 2 models × N=5 | Rough cost |
|---|---|---|---|
| `stage-exit` | `stage-exit/cold`, `stage-exit/warm` | 20 | ~$14–20 |
| `r2-prelude` | `r2-prelude` | 10 | ~$7–10 |
| `branch-path` | `branch-path/successful-rejoin`, `branch-path/recovery` | 20 | ~$20–30 |
| `all` | all five of the above | 50 | ~$41–60, ~60 min |

(Before `branch-path` existed, `--probe all` was three cells — 30 runs, about $22 and 40
minutes. That figure is preserved here only so an older recorded sweep is readable; it is not
the current default.) It also needs the `claude` CLI and interactive-grade credentials, which
a CI runner does not have. Run it locally when changing a stage's exit path, and keep the
JSON (`--out`) as the before/after baseline. Narrow the sweep with `--probe branch-path` when
only the diversion routing changed.

### Reading a result

`compliant` is all-criteria-pass for that run; the per-criterion rates below it say *which*
part of the contract slipped. A run that could not produce a usable transcript is counted
as `unscored`, never as a failure — it would otherwise let a flaky driver masquerade as a
model regression.

**A low model score is not a correctness failure.** Every cell — linear, prelude, and branch
alike — reports a rate over N, and a low rate is evidence about *model behavior under the
current canon wording*, not a bug in the scripts. The scripts' own correctness is asserted by
the pytest suite, not here. With no `claude` CLI on `PATH` the harness prints
`stage-drive compliance eval: skipped (no driver)` and exits 0; the only non-zero exit is a
harness bug.

### What this probe cannot see — and the field capture that covers it

Probe 1 runs fresh headless sessions of 4–16 turns against one authoring stage on the
`verifyGate: none` path. Three conditions are outside it by construction:

- **Real interview-length context.** An actual `forge-1-prd` run accumulates tens of
  thousands of tokens before the exit. The `warm` variant is the closest this harness gets
  and it is not close. If drift is a function of accumulated context, the probe sits below
  the threshold.
- **The interactive gates.** `verifyGate: standard` and in-stage auto-verify are
  `AskUserQuestion` surfaces a headless session cannot answer.
- **The other authoring stages**, and the `forge-5-loop` / `forge-6-docs` scripted exits.
  (The verify/fix diversion is no longer in this list — Probe 3 covers it, in its own cells.)

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
