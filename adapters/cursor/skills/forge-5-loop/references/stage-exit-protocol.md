# Stage Exit Protocol

The single source of truth for how every forge stage closes. **One** scripted contract
covers all **nine** covered direct exits — the seven production stages `forge-0-epic`
through `forge-6-docs`, plus direct `forge-verify` and direct `forge-fix`. It replaces the
old ad-hoc "Next steps:" bullet lists with one fixed, correctly-ordered sequence:
**verify (if missing or stale) → clear your session / start a fresh session → run the next command.**

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
   **not** deferred to the navigator, which runs *after* the session clear with none of the
   authoring context. Clearing first throws that context away.

## How this file is used

Every covered exit closes with the **Scripted Stage Exit**: the single stamped block
below, which runs `forge-session.py stage-exit`, obeys the DIRECTIVES it prints per the
**directive contract** in this file, and — only when this call owns the terminal block —
prints the script-emitted NEXT-STEPS block verbatim as the absolute last output. All the
conditional logic the old prose blocks asked the model to compute (effective auto-verify,
freshness collapse, gate selection, host wording, branch rejoin, loop and docs routing)
now lives in the script, deterministically; only genuinely interactive work (clean-room
subagent dispatch, question-tool gates) remains prose — specified once here, not per
stage.

A drift-guard test (`tests/test_stage_exit_protocol.py`) asserts each stamp site still
contains the canonical block, so an edit here must be mirrored into every stamp site (and
vice-versa).

### The nine covered exits and their stage-specific flags

Every caller passes the same identity and capability flags — `--feature`, `--stage`,
`--specs-dir`, `--host`, `--verify-capability`, plus `--epic "{epic}"` when the feature is
an epic member. Only the flags below are stage-specific; pass no others.

| Caller | `--stage` | Stage-specific typed flags |
|---|---|---|
| `forge-0-epic` | `forge-0-epic` | `--next-feature "{member}"` when a concrete member exists |
| `forge-1-prd` … `forge-4-backlog` | that stage's own id | none beyond identity/capability |
| `forge-5-loop` | `forge-5-loop` | `--outcome` — one of `complete`, `partial`, `blocked`, `needs-human`, `deferred`, `resolved`; optional `--cause dependency-starvation` with `--outcome partial` |
| `forge-6-docs` | `forge-6-docs` | `--outcome` — `complete`, `blocked`, or `skipped` (deliberate docs skip, persisted via `state-skip` before the exit; routes like `complete` with honest wording) |
| direct `forge-verify` | `forge-verify` | `--owner direct`, `--outcome` (`passed`, `findings`, `skipped`, `failed`), and served-stage metadata |
| nested `forge-verify` | `forge-verify` | `--owner nested`, plus the same outcome and served-stage metadata |
| direct/nested `forge-fix` | `forge-fix` | the matching `--owner`, a `FixOutcome` (`no-findings`, `decisions`, `failed`, `applied`, `reverified`, `reverify-findings`, `deferred`), and served-stage metadata |

"Served-stage metadata" means `--served-stage` (the production stage this diversion
served) and/or `--verify-mode` (`epic`, `prd`, `tech`, `specs`, `backlog`, `impl`), which
maps to a served stage when unambiguous. If both are supplied they must agree; if neither
is, the script exits 2 rather than guessing. Conversational context and `currentStage` are
never valid inference sources.

An invalid or missing enum, a conflicting served-stage mapping, or an unresolvable
identity is surfaced as the script's `Error:` line on stderr with exit 2. The skill
surfaces that line and **stops without inventing next steps** — there is no payload and no
sentinel to print.

An exit 2 from `stage-exit` itself is **not** a no-write guarantee: the
`auto-verify-pending` debt marker is persisted at the scheduling boundary *before* the
payload is built, deliberately, so an interrupted exit still leaves the verification
obligation durable on disk. Do not retry on the assumption that nothing landed — the
marker is idempotent and the re-run will read it. (The narrower "nothing was recorded"
guarantee belongs to `state-verify`, whose validation all precedes its single atomic
write.)

### Stamp sites

| Stamp site | Block |
|---|---|
| all nine covered exits (`forge-0-epic` … `forge-6-docs`, direct `forge-verify`, direct `forge-fix`) | the canonical scripted stage-exit stamp |

The scripted stamp fills one build-time slot, `{stage-exit-args}` — the per-stage argument
list from the table above (e.g. `--feature "{feature}" --stage forge-2-tech`; the epic
stage passes `--feature "{epic}" --stage forge-0-epic --next-feature
"{first-actionable-feature}"`; the loop passes `--feature "{feature}" --stage forge-5-loop
--outcome "{LoopOutcome}"`). `{feature}` / `{epic}` / `{specsDir}` /
`{first-actionable-feature}` / `{verify-capability}` remain runtime placeholders the skill
resolves before running the command, exactly as elsewhere.

<!-- BEGIN: scripted-stage-exit-stamp -->
**Close this stage with the Scripted Stage Exit** (contract: `references/stage-exit-protocol.md`; do not improvise a "Next steps" list). Run:

```bash
R="$(bash -c 'for d in "${FEATURE_FORGE_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-session.py" stage-exit {stage-exit-args} --specs-dir "{specsDir}" --host generic --verify-capability "{verify-capability}"
```

Obey the DIRECTIVES it prints, in the consumption order this protocol fixes: surface `invalidAutoVerifyKeys` and every `warnings` entry first; `runInStageVerify: true` → run the in-stage clean-room verify chain now (honoring `autoFixEligible`, and asking through the Standard Verify Gate first when you may not dispatch unsolicited); `verifyGate: "standard"` → present the Standard Verify Gate; `verifyGate: "manual-print"` → print the `verifyCommand` for the user and do **not** dispatch inline. Then, and only when `terminalOwnedBy` is `"self"`, **print the NEXT-STEPS block verbatim as your absolute last output — nothing after its sentinel line.** A `terminalOwnedBy: "outer"` payload carries `nextSteps: null`: return your structured result to the caller and print no terminal block at all.
<!-- END: scripted-stage-exit-stamp -->

The stamp is shown with `--host generic`; the adapter build substitutes `pi`/`generic` per
target, and §"Host and capability determination" below governs the value. The literal is
deliberate — `scripts/build-adapters.py` keys its host translation on the exact canon
value of that flag, and the stamp sites are compared byte-for-byte, so it is the one token
in that line that is not a placeholder.

## Host and capability determination

Before the call, compute the two inputs independently. They are unrelated: **a host never
implies a capability**, and the script takes `--verify-capability` at face value.

**`--host`** describes only the active adapter command surface — `claude`, `pi`, or
`generic`. It selects command syntax (Claude's stage-command prefix vs Pi's `/skill:` vs
host-neutral) and fresh-session wording (Claude's clear command vs Pi's `/new` vs neutral
prose). Nothing else.

**`--verify-capability interactive`** is passed only when **both** of these hold:

- **(a)** a question mechanism equivalent to the host's question mechanism is available, **and**
- **(b)** a clean-room `forge-verifier` subagent can be dispatched.

If either is absent, or capability cannot be established, pass `manual`. **(a) is rung 1 or
rung 2** of the Interaction Capability Ladder (`references/shared-conventions.md`); at
rung 3, (a) is false by definition, so `--verify-capability manual` follows without
further deliberation — the ladder's "verify-capability determination" class states this
rung-3 default once
so it is never re-derived per stage.

**(b) tests PERMISSION, not tool presence.** The question is not "is a subagent-dispatch
tool listed in my tool surface" but "**may I dispatch `forge-verifier` right now**". A
session can carry a standing host instruction against dispatching subagents unless the
user asked. Such instructions are injected by the harness, sit outside both the user's
config and this project's control, can be enabled or disabled per session, and **outrank
this prose**. A model that reads (b) as mere tool presence self-reports `interactive`,
attempts the dispatch, declines its own attempt, and lands in the recovery path below
instead of the correct path. Read (b) as permission and classify up front.

**A consent requirement is `interactive`, not `manual`.** When dispatch is barred only
*unless the user asked*, and a question mechanism **is** available, pass `interactive`. The
Standard Verify Gate's own prompt supplies the missing user request: the user selecting
"Verify {stageNoun} now" **is** the request, so the dispatch that follows that choice is
solicited and permitted. Degrading this case to `manual` prints a copy-paste command and
throws away the in-context digest for no reason. Pass `manual` only when there is **no**
question mechanism **and** **no** permitted dispatch — genuine incapability, never a
consent step.

**A dispatch bar routes an auto-verify directive through the gate; it never resolves it.**
When `runInStageVerify: true` arrives and you may not dispatch unsolicited, that directive
is **presented through the Standard Verify Gate** in its consent form — see "Consent
variant on a `none` gate" below — and the clean-room `forge-verifier` is **dispatched on
the affirmative choice**, never merely printed for the user to run later. Such a bar is
**never grounds to skip verification**, and it is never resolved by **advancing to the
production successor** while verification is unresolved.

**Do not use `host == claude` as a capability proxy.** It is not one in either direction:

- a capable Pi session is `--host pi --verify-capability interactive`, and receives the
  same logical gate a capable Claude session does;
- Pi without a dispatchable verifier is `--host pi --verify-capability manual`;
- a Claude session that cannot dispatch keeps the Claude host value with
  `--verify-capability manual`.

Interactive gate options keep their explicit labels, their recommended default, and their
one-line trade-off descriptions (below). The manual path prints the verify command as the
sole fenced primary action and mentions production advancement only as unfenced post-pass
guidance.

### Clean-room unavailable, or a non-answer

If a dispatch advertised as available later returns
`CLEAN_ROOM_UNAVAILABLE: forge-verifier subagent not dispatchable — verify not run.`, or
returns a non-answer (a placeholder, a "still running" note, or a delegation message
instead of a findings block), then **verification failed / did not run**:

- do **not** run the verification inline, and do **not** silently accept the non-answer as
  a pass;
- leave the verification debt **unresolved**, so the navigator catch-up fires later;
- obtain a **fresh** `stage-exit` payload with `--verify-capability manual` and use that
  verify-first output.

**Never reuse an earlier payload that promotes production advancement.** The earlier
payload was computed under a capability claim that has just been disproved; re-printing it
advances the pipeline past verification that never happened.

## Branch ownership: the `owner:` token

`forge-verify` and `forge-fix` are dispatched through a Skill/Agent invocation, not a CLI,
so no `--owner` flag arrives on its own — and ownership is **never** inferred from how the
invocation happened to be phrased.

The dispatching caller states ownership in its invocation prompt using a literal token:

- **`owner: nested`** — used by in-stage auto-verify chains, the navigator's catch-up
  chain, and a nested re-verify. The branch skill returns its structured result to the
  outer caller and prints no terminal block.
- **`owner: direct`** — used when the dispatcher intends the branch skill to own the
  terminal block.

**Absent the token, the skill treats itself as `direct`.** A user-typed
`/feature-forge:forge-verify` or `/feature-forge:forge-fix` is the only path that carries
no dispatcher, so "no token" and "no dispatcher" are the same condition. The skill passes
the resolved value straight through as `--owner direct|nested`.

Getting this wrong is not cosmetic. A nested verify that self-reports `direct` emits a
second sentinel-terminated block **inside** an outer stage's exit, breaking the
exactly-one-terminal-block rule — and the canon guard cannot catch it, because both
wordings legitimately appear in the same file. Judge the token, not the phrasing.

## Caller-side resumption: the declared resume point

The `owner:` token and `terminalOwnedBy` arbitrate who prints — but they specify only
the **callee** side: a nested skill stays quiet and returns its structured result. This
section is the reciprocal, caller-side half of that contract.

**On a sub-skill's return, the caller re-owns the terminal.** Every closing instruction
in the callee's own body — its report-and-stop posture, its "confirm the result" close,
its own next-steps habits — is void for this turn. The caller resumes at its **declared
resume point**, in the same turn, and its remaining steps run to its own terminal.

**Every Skill-tool delegation site declares, at the invocation, what happens on
return.** Suppression without resumption is the failure mode this section closes: the
callee's closing posture is the freshest instruction in context while the caller's next
step is the oldest, so an undeclared return silently ends the run one layer too early —
the caller's remaining steps (validation, state writes, commit, stage exit) dropped,
with no error surfaced. An implicit "let it run to its natural stopping point" is that
bug spelled politely, and it is banned on delegation sites. A site takes one of two
declared postures:

- **Delegate-and-resume** — the callee is a sub-step of the caller: the site names the
  caller's own step that control returns to, and the caller continues there in the same
  turn. The callee never owns the caller's terminal. The worked instance is
  `forge-4-backlog` Step 4's **Return contract** for the `author-backlog` delegation
  (control returns at Step 5; the sub-skill's direct-invocation posture — its approval
  gate and its validate-and-confirm close — is explicitly disapplied on the delegated
  path). New delegation sites follow that pattern rather than re-deriving it.
- **Terminal handoff** — the caller's job ends at the invocation and the invoked skill
  owns the terminal from there on (e.g. the navigator's `autoInvokeNextStage`
  "continue in this session" advance into the next production stage). Declaring the
  handoff is what keeps it distinct from an accidental drop.

Scope: this contract governs **Skill-tool delegation within one session**. The
truncated-verifier-return guard (forge-verify's `findings-template.md`, "Truncated
Verifier Returns") is a different mechanism — it polices what an **Agent-dispatched
subagent's** return payload must contain, not where a caller resumes. A dispatch site
can be subject to both; satisfy each on its own terms.

## Directive consumption order

`stage-exit` emits a DIRECTIVES object and (for a direct owner) a NEXT-STEPS block. The
skill executes the directives **in this order**; the script has already computed every
conditional, so a directive is an instruction, not a question to re-derive.

1. **Surface `invalidAutoVerifyKeys` and `warnings` first**, before any terminal output.
   `warnings` is a **list**, not a single string, rendered in the fixed order the script
   emits (epic-member state fallback, then debt-metadata, then revision mismatch); more
   than one entry can appear on a single call, so print every entry rather than the first.
   An empty list means checked-and-clean, which is not the same as the key being absent.
2. **`runInStageVerify: true`** → execute the nested verify → fix → re-verify chain
   synchronously (see below). This is the **one** directive that asks for an *unsolicited*
   dispatch — auto-verify is authorized by config, not by a live user request — so it is
   exactly where a standing no-unsolicited-dispatch instruction bites. When dispatch
   requires consent and a question mechanism is available, do **not** dispatch silently,
   do **not** treat the bar as a reason to skip verification, and do **not** advance:
   present the Standard Verify Gate first (in its consent form) and dispatch on the
   affirmative choice, then continue the chain unchanged.
3. **`verifyGate == "standard"`** → present the Standard Verify Gate. A pass, a findings
   result, or an explicit skip must be **persisted** and the routing recomputed before any
   block is printed. A "stop here" choice emits no advancing block.
4. **`verifyGate == "manual-print"`** → do **not** dispatch inline; print `verifyCommand`
   for the user and use the script's verify-first block as-is.
5. **Print `nextSteps` byte-for-byte, and only when `terminalOwnedBy == "self"`.**

## Directive contract

### `invalidAutoVerifyKeys` (non-empty)

Each key names a `forge.config.json` `autoVerifyStages` entry that matches no
verify-capable stage — a config typo. The script already prints one warning line per key,
in sorted order; surface them and continue. They never fail the exit.

### `warnings` (a list)

Non-fatal advisories, each naming both the affected feature/stage/key **and** the recovery
action. Print every entry, in the emitted order, above the terminal block. Do not
reformat, merge, or summarize them, and never dump the state file they were derived from.

### `runInStageVerify: true` — in-stage auto-verify {stageNoun}

Auto-verify is effective for this stage and verification is outstanding — verify **now,
in this session** (principle #2 applied to auto-verify: the digest and any fix decision
land here, where the authoring context still exists — not deferred to a post-clear
navigator). The `auto-verify-pending` debt is already durable on disk at this point, so a
declined or deferred gate leaves recorded debt rather than a silent pass.

1. **Clean-room verify (require-clean).** Dispatch the clean-room `forge-verifier`
   subagent from this session in require-clean mode with the `owner: nested` token — the
   same path the navigator uses (`skills/forge-verify/SKILL.md`). Dispatch it
   **synchronously and await its digest inline** — do **not** run it in the background or
   announce it as "still running"; the digest and any fix decision must land in this
   session. It inherits none of this session's context, so no session clear is needed and only
   a compact digest returns.
   **If you may not dispatch unsolicited**, present the consent form of the Standard
   Verify Gate first and dispatch on the affirmative choice — see "Consent variant on a
   `none` gate" below. **Clean-room unavailable or a non-answer returned**: follow
   "Clean-room unavailable, or a non-answer" above — leave verify pending, print the
   `verifyCommand`, and continue to the NEXT-STEPS block.
2. **Verify passed / no findings** → the fresh verify state is recorded by the
   clean-room run; continue to the NEXT-STEPS block.
3. **Verify found findings** →
   - **`autoFixEligible: true` AND the findings document has zero unresolved decision
     points** → chain `feature-forge:forge-fix` in-session with the `owner: nested` token
     (it owns its own commit + step tracking), then run a **mandatory re-verify** in
     require-clean mode. Continue to the NEXT-STEPS block only if the re-verify passes. On
     any precondition miss, a forge-fix early stop, or a red re-verify, fall through to the
     digest gate below — never a silent partial mutation. (`autoFixEligible` already folds
     in the config `autoFix` flag and the clean-tree precondition; a dirty tree or
     `gitCommitAfterStage: false` arrives here as `false`.)
   - **`autoFixEligible: false`, or unresolved decision points** → surface a **compact
     findings digest** as text, then present the gate: **Run `forge-fix` now**
     *(recommended — you are in-context and the digest is right here)* / **Clear + advance
     anyway** (leave the findings for later) / **Stop here**. Do **not** hard-stop and do
     **not** silently walk past. Act on the choice, then continue to the NEXT-STEPS block.

Every nested call in this chain prints no terminal block of its own. This stage is the
sole terminal owner, and it prints exactly one block after the chain settles.

### `verifyGate: "standard"` — the Standard Verify Gate

Auto-verify is off for this stage and verification is outstanding (`verifyState` is
`never`, `stale`, `failing`, or `auto-pending`), and the caller declared
`--verify-capability interactive`. Verify **now, before clearing**, using the host's
question mechanism with exactly these **three** labeled choices — the recommended default
first:

- **Verify {stageNoun} now** *(recommended)* — dispatch the clean-room `forge-verifier`
  subagent from this session in require-clean mode with the `owner: nested` token; the
  digest returns here so any fix decision keeps its context. One-time — it does **not**
  change config.
- **Verify now + enable auto-verify going forward** — verify now **and** patch
  `"autoVerify": true` into `forge.config.json` in place (preserve formatting and every
  other key) so future stages verify automatically, no prompt. This complements the
  `forge-init` opt-in. **Do not auto-commit this config change** — treat it like
  `notes`: a user-facing edit the user commits on their own cadence, never folded into
  a stage's artifact commit.
- **Skip for now** — go straight to the NEXT-STEPS block without verifying. Record this
  stage's verify status as `skipped` in pipeline state (via `state-verify`, never by hand)
  **only** on an explicit skip — a skip does not go stale. Exception: if the existing
  entry records `passed` or `findings-applied` (a resolved result whose freshness has
  merely lapsed), write **nothing** — `state-verify` refuses to demote a resolved status
  to `skipped` (#203), and the recorded result stands on its own; the user's decline is
  honored by simply not re-verifying.

**Advancement is allowed only after a pass, or after an explicit skip has been
persisted.** Choosing to stop, or losing the interaction, produces no advancing terminal
block. If verify runs and finds findings, handle them exactly as in the in-stage flow
above (digest + gate; `autoFixEligible` applies unchanged).

#### Consent variant on a `none` gate

When `runInStageVerify: true` and you may not dispatch unsolicited, the emitted
`verifyGate` **stays `none`** — changing it to `standard` would alter directive values for
the existing stages 0–4. Reuse this same gate block for consent, with **choice 2 omitted**:
auto-verify is already effective on this path, so "enable auto-verify going forward" is a
no-op, and offering a label with no trade-off behind it is not an accessible choice. The
consent form is therefore exactly **two** choices:

1. **Verify {stageNoun} now** *(recommended)* — dispatch the clean-room verifier now; this
   choice **is** the user request that authorizes the dispatch.
2. **Skip for now** — persisted as an explicit `skipped` before any advancing block.

This is the **only** case in which the rendered gate and the emitted `verifyGate` value
differ, and it exists because the gate here supplies *consent* rather than selecting
*policy*.

### `verifyGate: "manual-print"`

Verification is outstanding and the caller declared `--verify-capability manual`. Do
**not** run verify inline — print the `verifyCommand` for the user to run (mirroring
`autoInvokeNextStage`), offer the auto-verify enable as plain text only if a config write
is possible, and continue to the NEXT-STEPS block. Verify state stays outstanding, so the
navigator catch-up can fire later. The script has already made the verify command the sole
fenced primary action and demoted production advancement to unfenced prose.

### `verifyGate: "none"`

Verification is already resolved (fresh or explicitly skipped), the stage carries no
verification token at all, or the in-stage run above covers it. Say so in one line and
continue to the NEXT-STEPS block.

### `epicReconcile` (epic backflow — present only when there are open requests)

Emitted only when the exiting member carries `open` `epicChangeRequests` (recorded by
`forge-1-prd`/`forge-2-tech` when the epic *decomposition* itself must change — see
`references/pipeline-state-schema.json`). Absent on the common path and for standalone
features. The script has already folded the routing into the NEXT-STEPS block, so this
directive is informational — you do **not** re-derive the wording:

- `required: true` (at least one `blocksCurrent: true` request) — the reconcile command
  (`/feature-forge:forge-0-epic {epic}`) is promoted ahead of the ordinary production
  successor, and that successor is demoted to a follow-up line ("After reconciling,
  continue the pipeline with …"). This is *reconcile-before-specs*: proceeding would author
  artifacts against a decomposition that is about to change. It is strongest when exiting
  `forge-2-tech` (next is `forge-3-specs`, the point of no cheap return). When
  verification is also outstanding, verification stays primary and the reconcile becomes
  the **first** deferred action, ahead of the ordinary successor.
- `reminder: true` (only `blocksCurrent: false` requests) — normal next-stage routing is
  unchanged; the block appends a non-blocking reminder line ("You also flagged N epic
  change(s) to reconcile when convenient …"). This is *finish-then-edit*.

Either way the added lines are host-neutral (they name no fresh-session command) and sit
**above** the sentinel; just print the NEXT-STEPS block verbatim as always.

### Deferred decisions — do not solicit next-stage decisions at this exit

Each stage owns its own decisions. At a stage exit, do **not** pull a *later* stage's
decision forward — do not ask the user (or decide unilaterally) something that properly
belongs to the next stage's interview (e.g. at `forge-1-prd` exit, don't settle the
concrete cache backend that `forge-2-tech` will design). Soliciting it here guesses ahead
of the stage that owns the context, and the answer has nowhere durable to live.

Instead, when you notice a decision that belongs downstream, **record it structurally** as
a `deferredDecisions[]` entry on this feature's `.pipeline-state.json` by running
`state-decision` (`--rationale` and `--target-stage` are optional; the verb stamps
`raisedAt` and `status: "open"` for you). Add `--epic "{epic}"` when this feature is an
epic member — required, per the Pipeline State Protocol in `references/shared-conventions.md`:

```bash
R="$(bash -c 'for d in "${FEATURE_FORGE_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-session.py" state-decision \
  --feature "{feature}" --question "<phrased for the target stage>" \
  --rationale "<why it belongs downstream>" --target-stage "<owning stage>" \
  --raised-by "{stage}" --specs-dir "{specsDir}"
```

This keeps the exit focused on *this* stage's next-step routing while carrying the open
question forward for the owning stage to resolve (it flips `status` to `addressed` when it
does). Prefer a `deferredDecisions[]` entry over stuffing the same thing into the free-text
`notes` string. This is a recording affordance, not a gate: never block the exit on it.

### The NEXT-STEPS block, and the sentinel-last rule

**A direct payload** (`terminalOwnedBy: "self"`) carries exactly **one** occurrence of the
sentinel `─ forge: end of stage ─`, as the **final line** of `nextSteps`. Print that block
**verbatim as your absolute last output**. Nothing follows the sentinel — no summary, no
sign-off, no warning, no command result, no acceptance text, no caveat. The block already
carries the fresh-session recommendation (host-aware wording via `--host`) and the exact
next command — or, at the one terminal state below, the statement that there is none — so
trailing prose can only push the user's next action out of view.

**A finished epic ends the pipeline, and its block fences nothing.** When
`primaryCommand` is `null` (`nextCommand` and `nextStage` are `null` too), the epic is
complete — every member done, or the manifest set to `status: "complete"` — and there is no
next command at all. Print the block exactly as you would any other; do **not** substitute a
command, promote `nextCommand`, or append your own "you could now run…" list. The block's own
prose already names the optional follow-ons (start a new feature, re-open the dashboard to
inspect state) as inline offers rather than instructions. Re-fencing the epic dashboard here
is the specific defect this state exists to prevent: running it lands back on this same exit.

**A nested payload** (`terminalOwnedBy: "outer"`) carries `nextSteps: null` and
`sentinel: null`. It prints **no terminal block at all** — not even an empty one. Return
your structured result to the outer caller; that caller re-runs `stage-exit` after the
nested state transitions so its single final block reflects the terminal result.

---

## Re-verify scope and convergence

A **re-verify** is any verification run whose served stage's verify entry is
`findings-applied` — a fix pass preceded it, and its job is to CONFIRM that pass, not to
re-open the artifact. These rules bind the dispatched `forge-verifier`, the skill that
synthesizes its digest (`skills/forge-verify/SKILL.md`), and the fix pass that requests
the re-verify (`skills/forge-fix/SKILL.md` Step 6):

- **Scope.** Confirm each finding of the prior report against that finding's own
  acceptance evidence, and examine the fix's delta (the changed lines and what they
  directly touch) for new blocking defects. A re-verify is NOT a fresh full-checklist
  sweep: the full sweep already ran when the report was minted, and re-sweeping mints
  arbitrary new findings against text the fix just wrote — the divergence loop this
  section exists to prevent.
- **Convergence.** Only an unresolved finding from the prior report, or a new
  **blocking** finding (`error` with behavioral, CLI-output, or decision-bearing
  consequence, or `gap`) introduced by the fix delta itself, may make a re-verify close
  as `reverify-findings`. Every other new observation — advisory-severity anywhere, or
  anything outside the fix delta — is recorded in the report at most and never flips
  the outcome.
- **Decision immunity.** A finding whose subject carries a recorded decision — a
  `state-decision` entry, a recorded-decision comment in the artifact, or a declared
  non-goal — is never filed, in a re-verify or a fresh sweep. Cite the decision
  instead. Re-filing a decided question costs a round and reverses nothing.
  In particular, a **meta-guard** (a test protecting other tests or prose) is judged
  against its DECLARED protection set: guard-incompleteness against a declared
  non-goal is never a finding — the space of what a guard does not cover is
  unbounded, and enumerating it one round at a time is an arms race, not
  verification (authoring norm: the testing-strategy archetype in
  `skills/forge-3-specs/references/spec-archetypes.md`).
- **Escalation (the round ledger).** Rounds are counted from the served stage's
  findings documents (`VERIFY-{mode}-{date}.md`, then `-round{N}` — the filename rule
  in `skills/forge-verify/SKILL.md` Step 4), so the ledger is reconstructable from the
  `.verification/` directory alone. On the SECOND consecutive `reverify-findings`
  close for the same served stage, the loop has stopped converging: do NOT recommend
  another fix pass. Present the compact findings digest and ask for explicit
  disposition with exactly these options —
  **Accept the residual findings and advance** *(recommended)*: record the acceptance
  as a `state-decision` naming each accepted finding, then write the stage's verify
  result as `passed` with the report attached (`--findings-file`/`--findings-count`);
  the accepted findings become recorded decisions that decision immunity keeps from
  ever being re-filed. **Run another fix pass**: available, never recommended at this
  point. **Stop here**. The user may still choose to fix — the protocol just stops
  steering into the loop it cannot show is converging. Under `manual` capability
  (no question mechanism), print the digest and the three dispositions as text
  BEFORE the terminal block — the user answers on their own cadence; the terminal
  block still closes the stage mechanically.

---

## Retired blocks

The two bespoke terminal blocks this protocol used to carry — the **standard block** and
the **warm-acceptable variant**, the latter stamped only at the
`forge-5-loop → forge-6-docs` boundary — are **gone**. They were the last hand-written
advancing contract, and their final two stamp sites (`skills/forge-5-loop/SKILL.md`'s
step-6 epic handoff and `skills/forge-5-loop/references/result-reporting.md`'s all-done
report) now stamp the canonical scripted stamp instead.

Nothing may reintroduce them. A hand-written "walk the user through the Stage Exit
Protocol" block, a warm "clearing is optional" block, or any other bespoke next-command
list on a covered surface is a routing fork: the script already decides freshness, gate
form, host wording, and the next command from live state, and a second block can only
disagree with it. The canonical scripted stamp above is the **only** advancing contract
for all nine covered exits.
