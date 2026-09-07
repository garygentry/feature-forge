# `verify-state` — deterministic upstream-verification classification

`forge-4-backlog`, `forge-5-loop` and `forge-6-docs` each open by reading a served
stage's `stages.forge-verify-*` entry to answer one question — *has the upstream
artifact been verified, and what do I say if not?* Each answered it with its own
hand-rolled branch set: forge-4-backlog a binary verified/not check, forge-5-loop
four cases, forge-6-docs five. `forge-session.py verify-state` derives that answer
from the authoritative on-disk entry instead — one case enum, one message table,
the same "never eyeball the graph" move `select-outcome` makes for the exit outcome
(issue #277, part of the #265 guard-first program).

The verb reads, never writes. It reads the **raw** `forge-verify-{token}` status the
gates key on — it does **not** apply the version-aware freshness `verify_state()`
computes for the navigator's most-recent-stage gate. A `passed` entry classifies
`passed` regardless of the stage version, because that is exactly what the gates read
today; layering re-verify-on-revision onto them would be a behaviour change, not an
additive one.

## Synopsis

```
python3 forge-session.py verify-state \
  --feature F --for-stage S [--specs-dir DIR] [--epic E] [--json]
```

`--for-stage` is one of the five verify-token production stages (`forge-1-prd`,
`forge-2-tech`, `forge-3-specs`, `forge-4-backlog`, `forge-5-loop`) — the stage whose
`forge-verify-{token}` entry is classified. `forge-0-epic` (verification lives in
`.epic-state.json`) and `forge-6-docs` (no verify token) are **out of scope** and
rejected at parse time.

Output — always `{case, verified, stale, message, nextCommand}`:

```json
{
  "case": "findings-applied",
  "verified": false,
  "stale": true,
  "message": "Fixes were applied to auth's forge-4-backlog but nothing re-verified them; re-verification is still outstanding — run /skill:forge-verify auth backlog.",
  "nextCommand": "/skill:forge-verify auth backlog"
}
```

- **`case`** — one `VerifyStateCase`, the union of the cases the three gates spell out.
- **`verified`** — `true` only for `passed`. An explicit `skipped` is resolved but *not*
  verified, so it is `false`.
- **`stale`** — `true` only for `findings-applied`: fixes landed but nothing re-verified
  them, so a re-verify is still owed.
- **`message`** — the single canonical operator sentence for the case.
- **`nextCommand`** — the forge-verify retry for every unresolved case; `null` for
  `passed`, which needs no action.

## The case enum

`VerifyStateCase` is the union of the raw `forge-verify-*` statuses the three gates
key on, plus `never` for the absent / `pending` / unrecognized bucket every gate
folds into "not verified". `tests/test_verify_state.py` pins the enum to the
enumerating gate bodies, both directions, so a gate cannot grow a seventh case or
spell an existing one differently.

| `case` | on-disk status | `verified` | `stale` | meaning |
| --- | --- | :---: | :---: | --- |
| `passed` | `passed` | ✓ | | verification passed — proceed |
| `findings-reported` | `findings-reported` | | | blocking findings live and unresolved |
| `findings-applied` | `findings-applied` | | ✓ | fixes applied, re-verify still owed |
| `auto-verify-pending` | `auto-verify-pending` | | | scheduled automatic verification, owed but unrun |
| `skipped` | `skipped` | | | user explicitly proceeded without verifying |
| `never` | absent / `pending` / unrecognized | | | never verified |

## Classification

The status ordering mirrors `verify_state()` — an explicit `skipped` and recorded
`auto-verify-pending` debt are tested **before** the generic bucket, so neither can
fall through to `never`:

1. `skipped` → **skipped**.
2. `auto-verify-pending` → **auto-verify-pending**. Unusable scheduling metadata
   (missing/malformed `scheduledStageVersion`) warns once (REQ-DEBT-02) but the debt
   stays owed — degrading it to `never` is exactly the conflation that requirement
   forbids.
3. `findings-reported` → **findings-reported**.
4. `findings-applied` → **findings-applied**.
5. `passed` → **passed**.
6. anything else (absent, `pending`, or an out-of-vocabulary status) → **never**. A
   present-but-unrecognized status is flagged once (#148) then treated as unverified,
   the same answer an absent entry gets; a known `pending` (or an absent entry) is
   quiet.

A missing, unreadable, or torn state file never raises — the entry reads as absent
and classifies `never`, the same fail-safe the three gates take.

## Messages

`VERIFY_STATE_MESSAGES` holds one canonical sentence per case; the `auto-verify-pending`
case reuses `AUTO_PENDING_DIAGNOSTIC` — the single normative owed-debt sentence every
read-side emitter already shares — and appends the revision-advance clause when the
recorded schedule predates the current artifact. `{subject}` is the feature (or epic
member), `{stage}` the served production stage, `{command}` the forge-verify retry.
