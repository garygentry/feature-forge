# `select-outcome` — deterministic exit-outcome selection

`forge-verify` and `forge-fix` each close a run by choosing exactly one
`stage-exit --outcome`. That choice used to be model judgment over conversational
state. `forge-session.py select-outcome` derives it from the authoritative on-disk
record instead — the same "never eyeball the graph" move `rank-features` makes when
it derives `verifyGate` for the navigator (issue #276, part of the #265 guard-first
program).

The verb reads, never writes. It is called at the exit step, **after** the run's
result has already been persisted by `state-verify` and the findings document has
been written, so the disk state it reads is the run's own settled record.

## Synopsis

```
python3 forge-session.py select-outcome \
  --feature F --served-stage S --skill verify|fix \
  [--op-failure] [--user-deferred] [--decisions-open] \
  [--specs-dir DIR] [--epic E] [--json]
```

`--served-stage` is one of the five verify-token production stages
(`forge-1-prd`, `forge-2-tech`, `forge-3-specs`, `forge-4-backlog`, `forge-5-loop`).
`forge-0-epic` (epic-scoped verification lives in `.epic-state.json`) and
`forge-6-docs` (no verify token) are **out of scope** and rejected.

Output — always `{outcome, reason, evidence: [...]}`:

```json
{
  "outcome": "reverify-findings",
  "reason": "fixes were applied and a re-verify reopened blocking findings for the served stage",
  "evidence": [
    "forge-verify-tech status = findings-reported",
    "latest report .verification/VERIFY-tech-2026-09-07-round2.md (round 2): 2 blocking = 1 error + 1 gap, 3 total finding(s)",
    "round reports on disk: 2",
    "fix progress: 1 step(s) applied; sweep 1 fixed / 0 justified / 0 false-positive"
  ]
}
```

## Outcome vocabularies

The verb chooses from exactly the branch skills' `--outcome` domains — the
`VerifyOutcome` and `FixOutcome` aliases in `forge-session.py`. It re-lists neither:
`tests/test_select_outcome.py` pins those aliases to the **Outcome.** tables in
`skills/forge-verify/SKILL.md` and `skills/forge-fix/SKILL.md`, so the tables and the
enum can never drift.

- **verify** — `passed` · `findings` · `skipped` · `failed`
- **fix** — `no-findings` · `decisions` · `failed` · `applied` · `reverified` ·
  `reverify-findings` · `deferred`

## Inputs read from disk

- The served stage's `stages.forge-verify-{token}` entry in `.pipeline-state.json` —
  its `status` is the authoritative signal, written mechanically by `state-verify`.
- The latest `.verification/VERIFY-{mode}-*.md` report (round-aware: `-round{N}` beats
  the un-suffixed base file, and the newest day's newest round is "latest"). Blocking
  counts come from the `## Findings` severities (`error`/`gap`), never from the human
  `## Summary` line.
- Each report's `## Fix Progress` section — its `[APPLIED]` steps and the sweep
  dispositions (`FIXED`/`JUSTIFIED`/`FALSE-POSITIVE`). A report carrying `[APPLIED]`
  steps is the disk record that a fix pass ran (`fix-applied`).

## Derivation

### verify

1. `--op-failure` → **failed**.
2. entry `skipped` → **skipped**.
3. entry `findings-reported` → **findings**.
4. entry `passed` → **passed** (a clean report, an advisory-only report, or accepted
   residual findings — all three are recorded `passed`).
5. otherwise (no terminal result recorded) → **fail closed** (exit 2).

### fix

1. `--op-failure` → **failed**.
2. `--user-deferred` → **deferred**.
3. `--decisions-open` → **decisions**.
4. no report for the mode → **no-findings**.
5. entry `findings-applied` → **applied** (a re-verify is still owed).
6. entry `passed` → **reverified**. A forge-fix pass reaches a `passed` served stage
   only by re-verifying it: forge-fix Step 1.5 resolves its served stage to an
   *unresolved* verify entry (`findings-reported`, `findings-applied`, or a pending
   debt), never an already-resolved `passed`, so a `passed` entry at a fix exit is the
   mandatory re-verify's own passing result. (`fix-applied` is not consulted here — it
   reads every round on disk and so cannot tell this pass's fixes from an earlier
   cycle's.)
7. entry `findings-reported` + a fix ran → **reverify-findings** (a re-verify reopened
   findings); entry `findings-reported` + no fix ran → **fail closed** (exit 2).
8. any other resolved/absent entry with no fix → **no-findings**.

Two cases the issue calls out because a model tends to mis-eyeball them, and the verb
gets right by keying on the entry status rather than the presence of findings text:

- **A sweep whose survivors are all `FALSE-POSITIVE`.** Disposition is not a defect —
  the entry is still `findings-applied`, so the outcome is **applied**, never `failed`.
- **A re-verify red on a scoped subset.** The round-2 report reopens blocking findings
  and the entry returns to `findings-reported`, so the outcome is **reverify-findings**.

## Runtime signals

Three outcomes cannot be read off disk, because the fact that distinguishes each is
inherently runtime:

- **failed** — an operational failure (a dispatch, step, validation, commit, or state
  write) leaves *no* state write, so disk shows the prior state.
- **deferred** — an explicit user deferral of the fix or re-verify is byte-identical on
  disk to a nested/manual `applied` (both leave the entry at `findings-applied`).
- **decisions** — unresolved user decisions live in the free-prose "User Decisions
  Required" section, which has no machine format.

The caller asserts these with `--op-failure` / `--user-deferred` / `--decisions-open`
(the latter two are `fix`-only). Everything else is pure disk derivation. When the disk
record names no terminal outcome and no signal was supplied, the verb **fails closed**
with `Error:` on stderr and exit 2 — it never guesses.
