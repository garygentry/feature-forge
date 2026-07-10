# Stage Exit Protocol

The single source of truth for how every forge **authoring** stage closes. It
replaces the old ad-hoc "Next steps:" bullet lists with one fixed, correctly-ordered
sequence: **verify (if missing or stale) → `/clear` → run the next command.**

Two principles this protocol encodes (do not relitigate — they are locked product
decisions):

1. **Clearing is recommended on its own merits at every stage boundary** — a clean
   start for the next stage — *not* as a proxy for a full context window. Window
   fullness only changes *how emphatically* the clear is recommended, never *whether*
   it is.
2. **Verify happens before the clear, never after** — in the authoring session, whether
   manual **or** auto. Verify's clean-room subagent is dispatched from the *current*
   session, so the findings digest and any fix decision land where the context to act on
   them still exists. This holds for auto-verify too: the stage skill dispatches the
   clean-room verify (and any autoFix) at stage end, in-session, before the exit — it is
   **not** deferred to the navigator, which runs *after* the `/clear` with none of the
   authoring context. Clearing first throws that context away.

## How this file is used

The five authoring stages (`forge-0-epic` … `forge-4-backlog`) close with the
**Scripted Stage Exit**: a short stamped block (below) that runs
`forge-session.py stage-exit`, obeys the DIRECTIVES it prints per the **directive
contract** in this file, and prints the script-emitted NEXT-STEPS block verbatim as the
absolute last output. All the conditional logic the old prose blocks asked the model to
compute (effective auto-verify, freshness collapse, gate selection, host wording) now
lives in the script, deterministically; only genuinely interactive work (clean-room
subagent dispatch, `AskUserQuestion` gates) remains prose — specified once here, not
per stage.

The loop (`forge-5-loop`) keeps its bespoke exits: it stamps the **standard block**
(step-6 epic-member handoff) and the **warm variant** (all-done closing) below,
verbatim. `forge-6-docs` is **terminal** — it stamps no exit block.

A drift-guard test (`tests/test_stage_exit_protocol.py`) asserts each stamp site still
contains its block, so an edit here must be mirrored into every stamp site (and
vice-versa).

## Stamp sites

| Stamp site | Block |
|---|---|
| `forge-0-epic` … `forge-4-backlog` | scripted-stage-exit stamp |
| `forge-5-loop` (step-6 epic-member handoff) | standard |
| `forge-5-loop` (all-done closing → docs) | warm |

The scripted stamp fills one build-time slot, `{stage-exit-args}` — the per-stage
argument list (e.g. `--feature "{feature}" --stage forge-2-tech`; the epic stage passes
`--feature "{epic}" --stage forge-0-epic --next-feature "{first-actionable-feature}"`).
`{feature}` / `{epic}` / `{specsDir}` / `{first-actionable-feature}` remain runtime
placeholders the skill resolves before running the command, exactly as elsewhere.

<!-- BEGIN: scripted-stage-exit-stamp -->
**Close this stage with the Scripted Stage Exit** (contract: `references/stage-exit-protocol.md`; do not improvise a "Next steps" list). Run:

```bash
R="$(bash -c 'for d in "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-session.py" stage-exit {stage-exit-args} --specs-dir "{specsDir}" --host claude
```

Obey the DIRECTIVES it prints, in order, per the directive contract: `runInStageVerify: true` → dispatch the in-stage clean-room verify now (honoring `autoFixEligible`); `verifyGate: "standard"` → present the Standard Verify Gate; `verifyGate: "manual-print"` → print the `verifyCommand` for the user; non-empty `invalidAutoVerifyKeys` → print a one-line warning. Then **print the NEXT-STEPS block verbatim as your absolute last output — nothing after its sentinel line.**
<!-- END: scripted-stage-exit-stamp -->

## Directive contract

`stage-exit` emits a DIRECTIVES object and a NEXT-STEPS block. The skill executes the
directives **in this order**; the script has already computed every conditional, so a
directive is an instruction, not a question to re-derive.

### `invalidAutoVerifyKeys` (non-empty)

Print a one-line warning first (e.g. "⚠️ forge.config.json `autoVerifyStages` has
unknown keys: … — they are ignored; fix the typo").

### `runInStageVerify: true` — in-stage auto-verify {stageNoun}

Auto-verify is effective for this stage and verification is outstanding — verify **now,
in this session** (principle #2 applied to auto-verify: the digest and any fix decision
land here, where the authoring context still exists — not deferred to a post-`/clear`
navigator):

1. **Clean-room verify (require-clean).** Dispatch the clean-room `forge-verifier`
   subagent from this session in require-clean mode — the same path the navigator uses
   (`skills/forge-verify/SKILL.md`). Dispatch it **synchronously and await its digest
   inline** — do **not** run it in the background or announce it as "still running";
   the digest and any fix decision must land in this session. It inherits none of this
   session's context, so no `/clear` is needed and only a compact digest returns.
   **Clean-room unavailable** (no `Agent` tool, `forge-verifier` not dispatchable) **or
   a non-answer returned** (the verifier returned a placeholder / "still running" /
   delegation message instead of a findings block): do **not** run inline and do **not**
   silently accept the non-answer as a pass — leave verify **pending** so the navigator
   catch-up fires on a later Claude-host `/feature-forge:forge`, print the
   `verifyCommand` for the user to run, and continue to the NEXT-STEPS block.
2. **Verify passed / no findings** → the fresh verify state is recorded by the
   clean-room run; continue to the NEXT-STEPS block.
3. **Verify found findings** →
   - **`autoFixEligible: true` AND the findings document has zero unresolved decision
     points** → chain `feature-forge:forge-fix` in-session (it owns its own commit +
     step tracking), then run a **mandatory re-verify** in require-clean mode. Continue
     to the NEXT-STEPS block only if the re-verify passes. On any precondition miss, a
     forge-fix early stop, or a red re-verify, fall through to the digest gate below —
     never a silent partial mutation. (`autoFixEligible` already folds in the config
     `autoFix` flag and the clean-tree precondition; a dirty tree or
     `gitCommitAfterStage: false` arrives here as `false`.)
   - **`autoFixEligible: false`, or unresolved decision points** → surface a **compact
     findings digest** as text, then present the gate via `AskUserQuestion`: **Run
     `forge-fix` now** *(recommended — you are in-context and the digest is right
     here)* / **Clear + advance anyway** (leave the findings for later) / **Stop
     here**. Do **not** hard-stop and do **not** silently walk past. Act on the choice,
     then continue to the NEXT-STEPS block.

### `verifyGate: "standard"` — the Standard Verify Gate

Auto-verify is off for this stage and verification is outstanding (`verifyState` is
`never`, `stale`, or `failing`). Verify **now, before clearing**, using
`AskUserQuestion` with exactly these three options — but only when the host has a
question mechanism **and** the clean-room path is available (the `Agent` tool plus a
dispatchable `forge-verifier` subagent); otherwise degrade exactly as `manual-print`
below:

- **Verify {stageNoun} now** *(recommended)* — dispatch the clean-room `forge-verifier`
  subagent from this session in require-clean mode; the digest returns here so any fix
  decision keeps its context. One-time — it does **not** change config.
- **Verify now + enable auto-verify going forward** — verify now **and** patch
  `"autoVerify": true` into `forge.config.json` in place (preserve formatting and every
  other key) so future stages verify automatically, no prompt. This complements the
  `forge-init` opt-in. **Do not auto-commit this config change** — treat it like
  `notes`: a user-facing edit the user commits on their own cadence, never folded into
  a stage's artifact commit.
- **Skip for now** — go straight to the NEXT-STEPS block without verifying. Record this
  stage's verify status as `"skipped"` in pipeline state (mirroring the existing skip
  handling) **only** on an explicit skip — a skip does not go stale.

If verify runs and finds findings, handle them exactly as in the in-stage flow above
(digest + `AskUserQuestion` gate; `autoFixEligible` applies unchanged).

### `verifyGate: "manual-print"`

Verification is outstanding but the host cannot present the gate or dispatch
clean-room. Do **not** run verify inline — print the `verifyCommand` for the user to
run (mirroring `autoInvokeNextStage`), offer the auto-verify enable as plain text only
if a config write is possible, and continue to the NEXT-STEPS block. Verify state stays
outstanding, so the navigator catch-up can fire later.

### `verifyGate: "none"`

Verification is already resolved (fresh or explicitly skipped) or the in-stage run
above covers it. Say so in one line and continue to the NEXT-STEPS block.

### `epicReconcile` (epic backflow — present only when there are open requests)

Emitted only when the exiting member carries `open` `epicChangeRequests` (recorded by
`forge-1-prd`/`forge-2-tech` when the epic *decomposition* itself must change — see
`references/pipeline-state-schema.json`). Absent on the common path and for standalone
features. The script has already folded the routing into the NEXT-STEPS block, so this
directive is informational — you do **not** re-derive the wording:

- `required: true` (at least one `blocksCurrent: true` request) — the NEXT-STEPS block's
  fenced **primary** command is the epic reconcile command
  (`/feature-forge:forge-0-epic {epic}`), and the normal next stage is demoted to a
  follow-up line ("After reconciling, continue with …"). This is *reconcile-before-specs*:
  proceeding would author artifacts against a decomposition that is about to change. It is
  strongest when exiting `forge-2-tech` (next is `forge-3-specs`, the point of no cheap
  return).
- `reminder: true` (only `blocksCurrent: false` requests) — normal next-stage routing is
  unchanged; the block appends a non-blocking reminder line ("You also flagged N epic
  change(s) to reconcile when convenient …"). This is *finish-then-edit*.

Either way the added lines are host-neutral (no literal `/clear`) and sit **above** the
sentinel; just print the NEXT-STEPS block verbatim as always.

### The NEXT-STEPS block (always last)

Print the script's NEXT-STEPS block **verbatim as your absolute last output**. Nothing
follows its final sentinel line (`─ forge: end of stage ─`) — no caveats, no summary,
no sign-off. The block already carries the `/clear` recommendation (host-aware wording
via `--host`) and the exact next command, so trailing prose can only push the user's
next action out of view.

---

## Standard block

Stamped at the loop's step-6 epic-member handoff (finishing feature A → starting
feature B's PRD). It self-adapts: step 1's verify gate only fires when verification is
actually outstanding, so at a boundary where verify already ran (or was explicitly
skipped, or auto-verify is on) it silently collapses to just the `/clear` →
next-command steps.

Slots: `{stage}` (a lowercase noun phrase), `{verify-command}`, `{next-command}`.

<!-- BEGIN: standard-exit-block -->
**This stage is done — walk the user through the Stage Exit Protocol** before moving on. The order is fixed, and step 2 is something only the user can do:

1. **Verify {stage} first — if it isn't already verified.** If verify already ran in this session — via the in-stage auto-verify on the authoring stages, or the interactive impl-verify offered above on the loop — or is already fresh on record, or the stage was explicitly skipped, say so and go straight to step 2. Only when `autoVerify` is off for this stage **and** verify is **missing or stale** do you present the **Standard Verify Gate**: verify **now, before clearing**, using `AskUserQuestion` with exactly these three options — but only when the host has a question mechanism **and** the clean-room path is available (the `Agent` tool plus a dispatchable `forge-verifier` subagent):
   - **Verify {stage} now** *(recommended)* — dispatch the clean-room `forge-verifier` subagent from this session in require-clean mode; the digest returns here so any fix decision keeps its context. One-time — it does **not** change config.
   - **Verify now + enable auto-verify going forward** — verify now **and** patch `"autoVerify": true` into `forge.config.json` in place (preserve formatting and every other key) so future stages verify automatically, no prompt. This complements the `forge-init` opt-in. **Do not auto-commit this config change** — treat it like `notes`: a user-facing edit the user commits on their own cadence, never folded into a stage's artifact commit.
   - **Skip for now** — go straight to `/clear` and the next command without verifying. Record this stage's verify status as `"skipped"` in pipeline state (mirroring the existing skip handling) **only** on an explicit skip — a skip does not go stale.

   **Host / clean-room fallback (not a user-selectable option):** if the question mechanism, the `Agent` tool, or the `forge-verifier` subagent is unavailable, do **not** run clean-room — degrade to printing `{verify-command}` for the user to run inline/manually (mirroring `autoInvokeNextStage`), and offer the auto-verify enable as plain text only if a config write is possible.
2. **Then `/clear`.** Recommended **unconditionally** at this boundary for a clean start — independent of how full the context window is. Every artifact is on disk, so the work survives the clear. **I can't `/clear` for you — you have to run it yourself.**
3. **Then run the next command** in the fresh session — or re-run `/feature-forge:forge` to let the navigator resume from disk:

   ```
   {next-command}
   ```
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
3. **Then run the next command** — in this warm session, or a fresh one if you prefer:

   ```
   {next-command}
   ```
<!-- END: warm-exit-block -->
