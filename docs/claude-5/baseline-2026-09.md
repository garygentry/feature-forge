# Compliance baseline — 2026-09-03

**Date:** 2026-09-03 · **Harness:** `eval/run-compliance-eval.py` (unchanged since the 2026-07-28 baseline; `tests/test_compliance_eval.py` covers the offline pieces in CI)
**Scope:** the refresh #265 P0.3 (#268) asks for — a current reference for the prose-change gate the same phase declares in `AGENTS.md`. Subject: Claude Opus 5. Reference: Claude Opus 4.8.
**Baseline JSON:** [`eval/baselines/stage-exit-2026-09-03.json`](../../eval/baselines/stage-exit-2026-09-03.json) — the full per-run record, including tails and `cost_usd` per run.
**Canon at:** `main` @ `2734d54` (post-#244 P0–P4, post-P0.1, post-P0.2).

## 1. The numbers

**Probe 1 — stage-exit compliance.** n=5 per cell, `forge-1-prd` close, `verifyGate: none`.

| variant | Opus 5 | Opus 4.8 |
|---|---|---|
| `cold` (exit step only) | **5/5 (100%)** | **5/5 (100%)** |
| `warm` (full closing work, then exit) | **5/5 (100%)** | **5/5 (100%)** |

Every criterion 100% in every cell — sentinel present, nothing after it, next-stage command fenced, NEXT-STEPS block byte-identical to the script's, `stage-exit` actually run. **20/20 compliant, zero partial misses**, matching the 2026-07-28 result on the same probe.

Cost: **$19.41** total ($1.16 avg / cold-opus-5, $0.83 / cold-opus-4-8, $1.20 / warm-opus-5, $1.24 / warm-opus-4-8).

## 2. What this measures — and what it does not

Probe 1 drives one authoring stage (`forge-1-prd`) on the already-scripted linear path in a fresh headless session, and scores the last assistant output. It is the **regression oracle for prose changes that touch a scripted stage exit**: the sentinel contract, the fenced next command, and the byte-verbatim NEXT-STEPS block. #244 P0–P4 landed a substantial amount of prose across the shared references (`## Interaction Capability Ladder`, `## Root Hygiene`, the `--doctor` mode on `forge-guide`, the preflight & self-heal procedure and its wiring into `forge-5-loop`'s 1c/1d). None of it moved these numbers.

This refresh **deliberately omits** three probes the 2026-07-28 baseline recorded:

- **`r2-prelude`** — the R2 re-expansion gate for the context-efficiency plugin-root prelude reduction. Its subject prose has not been edited since the July record; nothing to re-baseline against, and the earlier numbers stand.
- **`branch-path/{successful-rejoin,recovery}`** — the verify/fix diversion. Not touched by #244 either, and the harness's own README emphasises that its cost/duration is the highest of the four probes (~$20–30). Left as an explicit gap so the next PR that changes the diversion routing (or the `forge-verify` / `forge-fix` prose) records it, rather than pretending this baseline covers it.
- **`loop-outcome`** — the `forge-5-loop` post-recovery `resolved` route. #244 P4 added the `--doctor` pointer inside the 1c/1d STOP text; the pointer is prose, not exit shape, so it does not move this probe by construction. Same reasoning as `r2-prelude`. *(Since recorded — see §6: #340 changed the loop-outcome exit shape and ran it.)*

If a later phase changes the diversion routing or the loop-outcome exit shape, run the narrowest probe that covers it and append a section here — the harness writes the same JSON shape and the same cell schema, so this document extends by row rather than rewrite.

## 3. What changed between 2026-07-28 and today

At the level this probe measures: **nothing.** The July baseline was 20/20 on the same cells with the same criteria at 100%; today's is the same. That is the outcome an intact regression oracle produces after a program the size of #244, and it is why the gate #268 declares in `AGENTS.md` compares against a *rate*, not a diff — a re-run at 20/20 means the numbers held under everything P0–P4 added to canon, which is exactly the claim it needs to make.

## 4. Running it yourself

```bash
python3 eval/run-compliance-eval.py --probe stage-exit --n 5 --json --out eval/last.json
```

Runbook, full cost table, and the per-probe cell definitions live in [`eval/README.md`](../../eval/README.md) § *Quick invocations*. Also runnable from Actions on demand — **Actions → trigger-accuracy-eval → Run workflow → probe = stage-exit** — which uploads the resulting `compliance-eval-<probe>-<run>.json` as an artifact. The workflow is advisory and never blocks a PR.

## 5. How to read it against `phase-0-compliance-baseline.md`

Keep both. The July document is the historical record — its numbers stand and are not restated here — and it also carries the R2 prelude numbers this refresh does not touch. This one is the current reference the `AGENTS.md` prose-change gate points at; when a later phase records a new probe cell here or in a later `baseline-YYYY-MM.md`, the newest recorded cell wins for that probe and the older one stays valid for the ones it still uniquely covers.

## 6. Later runs (appended)

Rows appended per §2, newest last. Same harness, same cell schema, same criteria; subject Opus 5, reference Opus 4.8. These were run as the `AGENTS.md` prose-change gate on the PR named, and the numbers below are the ones reported in that PR's body; the per-run JSON was not committed.

**Probe 4 — loop-outcome** (`resolved-resume`), n=5 per cell. This is the **formal loop-outcome baseline**; the 2026-09-03 refresh omitted it (§2). Criteria: exactly one sentinel, nothing after it, resume command fenced.

| date | PR · canon at | Opus 5 | Opus 4.8 | criteria | cost |
|---|---|---|---|---|---|
| 2026-09-30 | #340 · `861c9af0` | **5/5 (100%)** | **5/5 (100%)** | all 100% | $10.01 |
| 2026-09-30 | #340 · `e015c878` (after the round-1 `forge-5-loop` SKILL.md changes) | **5/5 (100%)** | **5/5 (100%)** | all 100% | $9.82 |

**Probe 1 — stage-exit**, n=5 per cell, same cells as §1.

| date | PR | `cold` Opus 5 | `cold` Opus 4.8 | `warm` Opus 5 | `warm` Opus 4.8 | criteria | cost |
|---|---|---|---|---|---|---|---|
| 2026-09-03 | this refresh (§1) | **5/5** | **5/5** | **5/5** | **5/5** | all 100% | $19.41 |
| 2026-09-29 | #338 (`forge-init` preflight prose) | **5/5** | **5/5** | **5/5** | **5/5** | all 100% | $26.35 |

The #338 run is a canon-regression check, not a measurement of `forge-init`'s new text: no probe loads `forge-init`, so `stage-exit` was run as the general prose-change oracle. Stage-exit held at 20/20 again.
