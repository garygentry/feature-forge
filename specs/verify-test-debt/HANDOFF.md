# verify-test-debt — Loop Handoff

**Written:** 2026-08-04, after the first `forge-5-loop` run.
**Purpose:** let a fresh session drive this feature to completion without reading
the originating conversation. Everything needed is stated here or verifiable from
disk with the commands below.

**Branch:** `forge/verify-test-debt` · **HEAD:** `98c24eb` (`forge(verify-test-debt): forge-5-loop in-progress`)

---

## 1. Where the feature stands

Pipeline state (`specs/verify-test-debt/.pipeline-state.json`): stages 1 through
4 are `complete`, all four verify gates `passed`. `forge-5-loop` is recorded
`in-progress` at v1 — **0 of 16 backlog items are done.**

Backlog (`rauf-stable status . --backlog specs/verify-test-debt --json`):

```json
{"pending": 13, "inProgress": 0, "blocked": 3, "needsHuman": 3, "deferred": 0, "done": 0, "total": 16}
```

## 2. What happened in the first run

Launched `rauf-stable loop run . --backlog specs/verify-test-debt --iterations 24 --review`.
It used **5 of 24 iterations** and stopped with nothing selectable. It did **not**
hit the iteration limit and did **not** circuit-break.

Items `001`, `002`, `004` are the backlog's only roots. All three emitted
`needs_human` for the **same** reason: `bash scripts/validate.sh` was red at HEAD on
three pre-existing traceability orphans (`REQ-DEBT-04`, `REQ-REL-01`,
`REQ-STATE-01`). Each item's own acceptance criteria passed; only the shared final
AC — `validate.sh` reporting `All checks passed!` — failed.

Every remaining item descends from those roots, so the loop had nothing left to run:

```
001 -> 005 -> 006 -> 007 -> 008 -> 009 -> 010 -+
                                               +-> 011 -> 012 -> 013 -> 014 -> 015 -+
002 -> 003 ------------------------------------+                                    +-> 016
004 --------------------------------------------------------------------------------+
```

The `--review` pass never ran.

## 3. The blocking decision — already made and already applied

The operator chose: **add an allowlist to `validate-traceability.py`.** That is
done and verified. The three ids are genuine quotations of test docstrings from the
antecedent `stage-exit-coverage` feature, where they are defined; they are not
requirements of this suite. `TRACEABILITY.md` § Coverage Verification records this.

Changes made (all currently **uncommitted**, see §4):

- `scripts/validate-traceability.py` — added a repeatable `--allow-orphan REQ-ID`
  flag plus auto-discovery of an optional `<specs-dir>/.traceability-allowlist`.
  Allowed ids are subtracted from the orphan set but printed as
  `ALLOWED FOREIGN REFERENCES`; an entry matching nothing is reported as
  `STALE ALLOWLIST ENTRIES`. JSON output gained `allowed_orphans` and
  `unused_allowlist_entries`. The ids are deliberately **not** hardcoded — this file
  ships into every adapter and consuming repo.
- `specs/verify-test-debt/.traceability-allowlist` — the three ids, with a comment
  pointing at `TRACEABILITY.md`.
- `adapters/*/scripts/validate-traceability.py` — regenerated (6 copies) so the
  drift guard stays green.

**Verified:** `bash scripts/validate.sh` exits 0 with `All checks passed!`. The
traceability step reports `ALLOWED FOREIGN REFERENCES (3)` and all five spec suites
pass. The baseline that stopped the loop is fixed.

## 4. What is uncommitted, and why it blocks the next launch

rauf refuses to launch with a dirty tree. The tree is dirty in three ways:

**a) 84 staged files, ~660 insertions — the agents' own work from items 001/002/004.**
Never committed, because each item's final AC failed. Includes
`eval/run-compliance-eval.py`, `scripts/forge-session.py`,
`tests/test_compliance_eval.py`, `tests/test_state_verbs.py`, and the adapter
fan-out. Confirm with `git diff --cached --stat`.

**b) 9 unstaged files** — the §3 allowlist fix (`scripts/validate-traceability.py`
plus 6 regenerated adapter copies), the `state-complete` write to
`.pipeline-state.json`, and rauf's own status edits to `backlog.json`.

**c) 2 untracked files** — `specs/verify-test-debt/.traceability-allowlist` (must be
committed; the validator reads it) and `specs/verify-test-debt/.rauf/progress.md`
(runner runtime state that `.gitignore` misses — see issue #195; ignore it or add
the ignore rule, do not commit it).

## 5. Steps to drive this to completion

Run in order. Do not skip step 3 — fixing the cause does not unblock the items, and
a relaunch without it will select nothing and exit exactly as the first run did.

**1. Reconcile the tree.** Review `git diff --cached --stat`, then commit the agents'
work and the allowlist fix. Add `**/.rauf/progress.md` to `.gitignore` (or leave
`progress.md` untracked and out of the commit). Verify `git status --short` is clean
apart from ignored files.

**2. Re-verify the baseline.** `bash scripts/validate.sh` must print
`All checks passed!` and exit 0. It takes several minutes — run it backgrounded.

**3. Unblock the three items.** `rauf-stable backlog unblock . --backlog specs/verify-test-debt`
(or rely on `--retry-blocked` in step 4). Then **prove** it moved:
`rauf-stable status . --backlog specs/verify-test-debt --json` must show
`blocked: 0, needsHuman: 0`. An unchanged summary means recovery failed — stop and
diagnose rather than launching.

**4. Relaunch.** Iterations: 16 active items x 1.5 = **24**.

```
rauf-stable loop run . --backlog specs/verify-test-debt --iterations 24 --review --retry-blocked
```

Launch backgrounded, then arm a persistent Monitor on
`specs/verify-test-debt/.rauf/events.ndjson` filtering
`item_completed|item_blocked|needs_human|signal_parsed|loop_completed|loop_error|loop_cancelled|llm_stuck_warning`.
Use `tail -F` (follow by name) — the runner rotates that file at the start of each run.

**5. Supervise actively.** Because the backlog is a 13-deep serial chain behind 3
roots, any single item stopping halts everything downstream. On a `needs_human`
signal: surface it immediately, get the decision, apply it, unblock, and resume —
do not end the session with the decision uncollected or uncommitted.

**6. Close the stage.** When `done == 16`, record completion with
`forge-session.py state-complete --feature verify-test-debt --stage forge-5-loop
--version 1 --status complete --based-on "forge-4-backlog=1" --artifact
"specs/verify-test-debt/.rauf/state.json" --specs-dir ./specs`, offer
`/feature-forge:forge-verify verify-test-debt impl`, then run the scripted
`stage-exit` with the outcome selected from the authoritative counts.

## 6. Known process gaps (filed, not yet fixed)

These are why this handoff document is necessary rather than automatic. Expect to
work around them; do not assume the tooling covers them.

| Issue | Gap |
|---|---|
| [#196](https://github.com/garygentry/feature-forge/issues/196) | needs-human answers are collected but never persisted |
| [#189](https://github.com/garygentry/feature-forge/issues/189) | no stage-exit outcome for a decision already made and applied |
| [#190](https://github.com/garygentry/feature-forge/issues/190) | pending items always misreported as "iteration limit reached" |
| [#191](https://github.com/garygentry/feature-forge/issues/191) | no systemic-cause detection across repeated needs-human signals |
| [#192](https://github.com/garygentry/feature-forge/issues/192) | no post-run tree reconciliation |
| [#193](https://github.com/garygentry/feature-forge/issues/193) | resolved items are never unblocked |
| [#194](https://github.com/garygentry/feature-forge/issues/194) | no dependency-topology check on the backlog |
| [#195](https://github.com/garygentry/feature-forge/issues/195) | `.gitignore` misses `**/.rauf/progress.md` |
