# Stage Exit Protocol

The single source of truth for how every forge **authoring** stage closes. It
replaces the old ad-hoc "Next steps:" bullet lists with one fixed, correctly-ordered
sequence: **verify (if missing or stale) → `/clear` → run the next command.**

Two principles this block encodes (do not relitigate — they are locked product
decisions):

1. **Clearing is recommended on its own merits at every stage boundary** — a clean
   start for the next stage — *not* as a proxy for a full context window. Window
   fullness only changes *how emphatically* the clear is recommended, never *whether*
   it is.
2. **Verify happens before the clear, never after.** Verify's clean-room subagent is
   dispatched from the *current* session, so the findings digest and any fix decision
   land where the context to act on them still exists. Clearing first throws that
   context away.

## How this file is used

The blocks below are **stamped verbatim** into each stage skill's closing (a runtime
`references/` include would not survive the adapter build, which flattens skills into
`adapters/<agent>/`). A drift-guard test (`tests/test_stage_exit_protocol.py`) asserts
each stamp site still contains its block, so an edit here must be mirrored into every
stamp site (and vice-versa).

Each stamp site fills three slots; everything else is identical across sites:

- `{stage}` — the just-completed stage as a lowercase noun phrase (e.g. `the PRD`,
  `the tech spec`, `the backlog`). Always used mid-sentence, never sentence-initial.
- `{verify-command}` — the verify command for that stage (e.g.
  `` `/feature-forge:forge-verify {feature}` ``).
- `{next-command}` — the command that starts the next stage (e.g.
  `` `/feature-forge:forge-2-tech {feature}` ``).

`{feature}` / `{epic}` and similar remain runtime placeholders that pass through
untouched — they are resolved by the skill at run time, not by this template.

## Stamp sites

| Stamp site | Block | `{stage}` |
|---|---|---|
| `forge-0-epic` (epic → first PRD) | standard | the epic decomposition |
| `forge-1-prd` | standard | the PRD |
| `forge-2-tech` | standard | the tech spec |
| `forge-3-specs` | standard | the implementation specs |
| `forge-4-backlog` | standard | the backlog |
| `forge-5-loop` (step-6 epic-member handoff) | standard | feature `{feature}`'s loop |
| `forge-5-loop` (all-done closing → docs) | warm | — |

`forge-6-docs` is **terminal** — it stamps no exit block. It is the *target* of the
warm variant, not a stamp site.

---

## Standard block

Stamp this at every authoring-stage boundary. It self-adapts: step 1's verify gate
only fires when verification is actually outstanding, so at a boundary where verify
already ran (or was explicitly skipped, or auto-verify is on) it silently collapses to
just the `/clear` → next-command steps.

<!-- BEGIN: standard-exit-block -->
**This stage is done — walk the user through the Stage Exit Protocol** before moving on. The order is fixed, and step 2 is something only the user can do:

1. **Verify {stage} first — if it isn't already verified.** When this stage has no fresh verification on record (`verifyState` is **missing or stale**) **and** `autoVerify` is off for it, verify **now, before clearing**. If verify already ran, is pending under auto-verify, or the stage was explicitly skipped, say so and go straight to step 2. Present the **Standard Verify Gate** using `AskUserQuestion` with exactly these three options — but only when the host has a question mechanism **and** the clean-room path is available (the `Agent` tool plus a dispatchable `forge-verifier` subagent):
   - **Verify {stage} now** *(recommended)* — dispatch the clean-room `forge-verifier` subagent from this session in require-clean mode; the digest returns here so any fix decision keeps its context. One-time — it does **not** change config.
   - **Verify now + enable auto-verify going forward** — verify now **and** patch `"autoVerify": true` into `forge.config.json` in place (preserve formatting and every other key) so future stages verify automatically, no prompt. This complements the `forge-init` opt-in. **Do not auto-commit this config change** — treat it like `notes`: a user-facing edit the user commits on their own cadence, never folded into a stage's artifact commit.
   - **Skip for now** — go straight to `/clear` and the next command without verifying. Record this stage's verify status as `"skipped"` in pipeline state (mirroring the existing skip handling) **only** on an explicit skip — a skip does not go stale.

   **Host / clean-room fallback (not a user-selectable option):** if the question mechanism, the `Agent` tool, or the `forge-verifier` subagent is unavailable, do **not** run clean-room — degrade to printing `{verify-command}` for the user to run inline/manually (mirroring `autoInvokeNextStage`), and offer the auto-verify enable as plain text only if a config write is possible.
2. **Then `/clear`.** Recommended **unconditionally** at this boundary for a clean start — independent of how full the context window is. Every artifact is on disk, so the work survives the clear. **I can't `/clear` for you — you have to run it yourself.**
3. **Then run `{next-command}`** in the fresh session — or re-run `/feature-forge:forge` to let the navigator resume from disk.
<!-- END: standard-exit-block -->

---

## Warm-acceptable variant

Stamp this only at the `forge-5-loop → forge-6-docs` boundary (the all-done result
report). Here clearing is **optional**: the docs stage benefits from the still-warm
context of what the loop actually did, and impl-verify is already offered interactively
by the loop itself, so this block defers rather than re-presenting a gate.

> **Note — no literal `/clear` here.** The warm block lives in `result-reporting.md`, a
> skill-*own* reference that the adapter build copies **verbatim** (unlike skill bodies,
> it is not host-term translated), so a literal `/clear` would reach non-Claude adapters
> undegraded. The warm variant says "clearing is optional" anyway, so it is phrased
> host-neutrally without the token on purpose — do not reintroduce `/clear` here. (The
> standard block *does* use `/clear`; that is fine because every standard stamp site is a
> skill **body**, where `scripts/build-adapters.py` degrades it.)

<!-- BEGIN: warm-exit-block -->
**The loop is complete — this is the one boundary where clearing before the next stage is optional.**

1. **Verify is already offered above.** Impl-verify is offered interactively right after this report (Step 5b for a standalone feature, Step 6.1 for an epic member) — run it there rather than as a second gate. It runs clean-room, so it needs no fresh session.
2. **Clearing is optional here — warm is fine.** `forge-6-docs` benefits from the still-warm context of what the loop actually did, so continuing in this same session is the easy default. A cold start also works — every artifact is on disk — but there is no need to force it.
3. **Then run `{next-command}`** — in this warm session, or a fresh one if you prefer.
<!-- END: warm-exit-block -->
