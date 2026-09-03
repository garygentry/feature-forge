# Phase 0 — stage-drive compliance baseline

**Date:** 2026-07-28 · **Harness:** `eval/run-compliance-eval.py` (+ `tests/test_compliance_eval.py`, `eval/README.md`)
**Scope:** Phase 0 of the Claude 5 adaptation program — a per-model baseline for stage-exit
compliance, plus the R2 re-expansion gate. Subject: Opus 5. Reference: Opus 4.8.
**Baselines:** `stage-exit` from sweep 3, `r2-prelude` from sweep 2 (harness unchanged for that path between them)
**Later refresh:** [`baseline-2026-09.md`](baseline-2026-09.md) refreshes the `stage-exit` probe at `main` @ `2734d54` (post-#244 P0–P4, still 20/20). The `r2-prelude`, `branch-path` and `loop-outcome` numbers here stand — nothing has re-baselined them.

> **Why this sits next to `skill-tuning-guide.md` and `skill-review-playbook.md`.** It
> partially overturns them. Those two documents predict a set of Opus 5 failure modes at
> the stage boundary (guide §3.3–3.6, playbook §1.1); §2 below reports that none of them
> occurred in 20 measured runs, and §3 reports the behavior that *did* change. Read the
> guides with this alongside. §-references to "the plan" point at the program roadmap,
> which is an internal working document and deliberately untracked.

---

## 1. The numbers

**Probe 1 — stage-exit compliance.** n=5 per cell, `forge-1-prd` close, `verifyGate: none`.

| variant | Opus 5 | Opus 4.8 |
|---|---|---|
| `cold` (exit step only) | **5/5 (100%)** | **5/5 (100%)** |
| `warm` (full closing work, then exit) | **5/5 (100%)** | **5/5 (100%)** |

Every criterion was 100% in every cell — sentinel present, nothing after it, next-stage
command fenced, NEXT-STEPS block byte-identical to the script's, and `stage-exit`
actually run. 20/20 compliant, zero partial misses.

**Probe 2 — R2 prelude re-expansion.** n=5.

| criterion | Opus 5 | Opus 4.8 |
|---|---|---|
| executed resolver **byte-identical** | 4/5 (80%) | 5/5 (100%) |
| executed resolver **functionally equivalent** | 5/5 (100%) | 5/5 (100%) |

The one non-byte-identical run resolved `$R` correctly and the command ran clean (exit 0).

Cost: $15.42 (probe 1) + $2.91/$2.12 (probe 2) — see §5 for total programme spend.

---

## 2. Does the §1.2 diagnosis hold? **Not at this surface, under these conditions.**

§1.2 predicts the model will (a) summarize the block rather than reproduce it, (b) land
text *after* the sentinel, and (c) "improve" the block instead of copying it. **None of
those occurred once in 20 runs**, on either model, including the `warm` variant built
specifically to create narration pressure (≈16 turns and a git commit before the exit).

That is a real result and the evidence should win over the prior. But be precise about
what it does and does not rule out:

**What it covers.** Fresh headless sessions, 4–16 turns, one authoring stage, the
`verifyGate: none` path, Claude host, the shipped `forge-1-prd` + `stage-exit-protocol`
canon.

**What it does not cover.**

- **The condition that actually produced the reports.** A real `forge-1-prd` run is a
  full structured interview — tens of thousands of tokens of context — before the exit.
  The `warm` variant's ≈16 turns is the closest this harness gets, and it is not close.
  If drift is a function of accumulated context, this probe is below the threshold.
- **The interactive gates.** `verifyGate: standard` and the in-stage auto-verify path
  are `AskUserQuestion` surfaces a headless session cannot answer, so they are excluded
  by construction. B4's "pin every option set" thesis is untested here.
- **The other four authoring stages**, and the `forge-5-loop` bespoke exits.
- **Statistical power.** n=5. A 100% observation has a ~55% lower 95% bound. This rules
  out "fails most of the time"; it does not rule out "fails 1 run in 10".

**Recommendation on B1 (the `Stop`-hook sentinel guard).** Plan §1.3 says the chunk-5a
gate — *"do not build until the re-test shows the last-output invariant drifts under
wording alone"* — is now met, on the strength of the Opus 5 reports. **This baseline does
not corroborate that.** Before building B1, either reproduce the drift under long-session
conditions, or capture a failing real-session transcript. Building a hook to enforce an
invariant that measures 20/20 is the sort of change that looks free and is not: it adds a
`Stop` surface, and it must not be justified by a symptom the instrument cannot find.
This is a "get better evidence" verdict, not a "the reports are wrong" verdict — the
users' experience is data too, and the gap between it and this measurement is itself the
next thing to explain.

---

## 3. The finding that actually reproduced (and it inverts the framing)

Three separate times across the discarded sweeps, Opus 5 scored **0/5 or 1/5 on a cell
where Opus 4.8 scored 5/5** — and every time, the cause was a defect in my fixture, and
Opus 5's behavior was *correct*:

| What Opus 5 did | Why it was right | What Opus 4.8 did |
|---|---|---|
| Refused to close the stage; asked before repairing `.pipeline-state.json` | The state was missing `feature`/`createdAt`/`updatedAt`, required by `pipeline-state-schema.json` | Closed the stage over the invalid file |
| Reported that the named section did not exist | The prompt said "Step 5: Write State & Close"; the real heading is "Step 6: Update Pipeline State and Commit" | Proceeded from the nearest matching content |
| Refused to re-fire the exit on a `complete` stage | **Stage-Completion Re-check** rule 2 (`shared-conventions.md`) — do not re-run a finished exit | Re-fired it |

The third is the sharpest: Opus 5 applied a forge guard that Opus 4.8 walked past, and my
scorer called that non-compliance.

**Implication for W-B.** The reported unreliability may not be "Opus 5 ignores the
contract" but closer to "Opus 5 enforces the contract, including the parts forge's own
artifacts violate." If so, the productive work is not more enforcement (B1) but removing
internal inconsistency — stale prose, headings that moved, states that don't validate,
guards whose preconditions don't quite match their trigger. That is a different backlog
from §2's, and it is worth testing before committing to W-B's shape. Note this also
matches the §1.3 pattern in reverse: the thing that changed is not the model's compliance
but its willingness to proceed over a defect.

One caveat on that third row: the re-check's detect-and-refuse path formally requires a
recorded `commitHash`, and my fixture had `commitHash: null` — so Opus 5 arguably applied
the guard slightly beyond its stated precondition. Whether that is over-application or
sensible caution is a judgement call worth a look when B-series work touches that block.

---

## 4. Should R2 ship? **The probe does not block it; §8.4's own argument still might.**

§8.4's stated risk is a **broken plugin-root resolution at a call site**. That did not
happen: 5/5 Opus 5 runs resolved `$R` correctly and executed cleanly. On the risk as
written, R2 comes back green.

But byte-identity was 4/5, not 5/5 — so the charter's claim that execution stays
"byte-identical to today" is **not** unconditionally true on Opus 5. Two consequences:

1. Any drift guard that asserts byte-identity against an *executed* command (rather than
   against the file) will flag intermittently.
2. The behavior-preservation claim for R2 should be restated as *functionally* preserving,
   with byte-identity as a strong tendency rather than a guarantee.

**My read:** ship R2 if it ships on its merits, not on this probe. The evidence removes
the "it will break resolution" objection but leaves §8.4's risk/reward argument intact —
R2 saves ~2k tokens across 4 files, the smallest payoff of the six, and remains the only
R that converts a verbatim copy into a reconstruct-from-memory operation. Dropping it
still costs nothing (SC-6 makes each R independently shippable). If it does ship, re-run
`--probe r2-prelude` with a larger n first; 4/5 on n=5 is a wide interval.

---

## 5. Harness notes, cost, and what I'd change

**Why the CLI, not the Messages API.** §1.2's mechanic is a conflict between the *host
system prompt* and the skill. A bare API call reproduces neither the host prompt nor skill
loading, so it cannot see the behavior. The driver is `claude -p`, which also means no
`ANTHROPIC_API_KEY` is needed — it authenticates like an interactive session.

**Cost.** ~$58 across three sweeps. Only the last is the baseline; sweeps 1 and 2 measured
my own harness defects and were discarded. Per-run: cold ≈$0.48, warm ≈$1.05, prelude
≈$0.55. A full default sweep is ≈$20 and ≈40 min.

**Not wired into CI**, per the brief — `.github/workflows/eval.yml` is untouched.

**The lesson worth carrying.** Every one of my three defects made a *more careful* model
look non-compliant. A harness whose job is to judge careful behavior will keep doing this
unless the fixture is guarded, so the fixture's validity is now pinned by tests: schema
validation against `pipeline-state-schema.json`, the prompt's section name checked against
the real heading, the `warm` state asserted `in-progress`, and the probe-2 scorer pinned
against the reconnaissance-then-execute pattern.

**If this becomes a regression gate**, three things need to change first: raise n (5 is
too thin to detect a 10% regression), add a long-context variant that approximates a real
interview, and find a way to exercise the `AskUserQuestion` gates — without which the
B4/B5 surfaces stay unmeasured.

---

## 6. Decisions taken on this evidence (owner, 2026-07-28)

1. **The `Stop`-hook sentinel guard is not built.** Its gate required measured drift in the
   last-output invariant; the measurement is 20/20 compliant. It is held pending real-session
   evidence, not cancelled.
2. **A canon consistency sweep leads the follow-on work instead.** §3's finding — Opus 5
   halting on internally inconsistent artifacts where 4.8 proceeds — is the mechanism that
   actually reproduced, so the first move is to find and remove those inconsistencies:
   pipeline states that fail `pipeline-state-schema.json`, prompts naming headings that no
   longer exist, guards whose stated preconditions do not match their trigger. Audit first,
   size the defect count, then decide whether a durable checker earns its keep.
3. **R2 does not ship.** §4 leaves the risk/reward argument standing, and R2 is the only
   context-efficiency item that *adds* a compliance-dependent operation — the wrong
   direction given §3. The `r2-prelude` probe stays in the harness as the gate if it is
   ever revived.
4. **The evidence gap is closed by field capture, not a synthetic long-context probe.**
   See `eval/field-observations.md`.
