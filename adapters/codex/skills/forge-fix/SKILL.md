---
# GENERATED — DO NOT EDIT. Source: skills/forge-fix/SKILL.md. Regenerate: python3 scripts/build-adapters.py
name: forge-fix
description: Apply fixes from the most recent forge-verify findings document. Use when user runs /feature-forge:forge-fix or asks to apply verification fixes for a forge feature. Do NOT trigger for general code fixes, bug fixes, or repairs outside the forge verification workflow.
---

# forge-fix — Apply Verification Fixes

Apply fixes from the most recent forge-verify findings document, with step-level tracking for crash recovery.

Usually invoked by the user. An **`autoFix` caller** may also dispatch this skill automatically when `autoFix: true` is configured **and** its preconditions hold (the findings document has zero unresolved decision points, the working tree is clean, and a mandatory re-verify passes afterward). Two callers drive that chain: an **authoring stage's in-stage auto-verify** (the primary path — see `references/stage-exit-protocol.md`, the in-stage verify block) and the **`/feature-forge:forge` navigator's catch-up** (§3b). The **fix application** below is identical either way — this skill is not "auto-aware" about *applying* findings; it always applies the selected findings document. What differs is **branch ownership**, and ownership is read from the literal `owner:` token described under Prerequisites, never inferred from how the invocation happened to be phrased.

## Prerequisites

Read and follow `references/shared-conventions.md` for feature name validation, configuration reading, and force mode handling before proceeding.

**Ownership.** Determine branch ownership **at entry**, from the literal `owner: nested` / `owner: direct` token in the prompt that dispatched you. **Absent the token you are `direct`** — a user-typed `/feature-forge:forge-fix` is the only path that carries no dispatcher. Judge the token, never the phrasing of the invocation. Preserve that value unchanged through any re-verify and pass it straight through as `--owner` in Step 7. A **direct** fix stays the terminal owner through its optional re-verify; a **nested** fix invokes nested verify and returns its structured result to the outer stage, printing no terminal block at all. `references/stage-exit-protocol.md` § "Branch ownership: the `owner:` token" owns this rule.

**Turn structure reminder:** Output analysis/context as text, then route ALL questions through the host's question mechanism. Never embed questions in text output — the user will not be prompted and the session will stall. At rung 2/3, follow the Interaction Capability Ladder.

## Step 1: Locate Findings and Establish the Served Stage

1. Read `forge.config.json` for `specsDir` (default: `./specs`)
2. Resolve the feature directory via the **Feature Directory Resolution** block in `references/shared-conventions.md` (a standalone feature resolves to its flat `{specsDir}/{feature}/` path exactly as today; an epic member resolves to its nested path). Then find the most recent `VERIFY-*-*.md` file in `{resolvedFeatureDir}/.verification/`.
3. **Establish the served production stage before any mutation**, in this order:
   - An explicit `--served-stage {stage}` argument on this invocation is authoritative — that is what `forge-verify` and the scripted exit pass when they route here.
   - Otherwise read it from the **selected report's own mode/header**: the `{mode}` in its `VERIFY-{mode}-{YYYY-MM-DD}.md` name together with the mode recorded in the report header, mapped as `epic` → `forge-0-epic`, `prd` → `forge-1-prd`, `tech` → `forge-2-tech`, `specs` → `forge-3-specs`, `backlog` → `forge-4-backlog`, `impl` → `forge-5-loop`.
   - If both are present and disagree, fail closed rather than picking one.
   - Never derive the served stage from conversational context, from `currentStage`, or from whichever feature stage happens to be newest. The report you are applying decides which stage this diversion serves.
4. **An unestablishable served stage is a fail-closed error, not a guess.** If a report exists but its mode is missing, malformed, or ambiguous (for example two same-day reports for different modes, or a header whose mode does not match the filename) and no explicit `--served-stage` was supplied, mutate nothing: list the reports you found and tell the user to re-invoke as `/feature-forge:forge-fix {feature} --served-stage {stage}` or to re-run `/feature-forge:forge-verify {feature} {stage}`. Stop there — with no served stage there is no stage to close against, so do not run Step 7.
5. **No applicable findings → `no-findings`.** If `.verification/` holds no findings document, or none whose steps still apply, the outcome is `no-findings`: mutate nothing and take the served stage from **authoritative pipeline state** — the production stage whose `stages.forge-verify-*` entry is unresolved (`findings-reported`, `findings-applied`, `auto-verify-pending`, or `pending`) — then close through Step 7. If no verification is outstanding either, there is nothing for this pass to serve: tell the user "No verification findings found. Run `/feature-forge:forge-verify {feature}` first." and stop without closing a stage.

## Step 2: Parse Fix Execution Plan

1. Read the "Fix Execution Plan" section of the findings document
2. Identify all execution steps and their dependencies
3. Check for a `## Fix Progress` section at the bottom of the findings document — if present, some steps were already applied in a previous interrupted run
4. **Assert the plan covers every finding** before any fix executes. Exit 1 is that assertion firing, not a tool failure; only exit 2 is a tool failure. Run:

```bash
R="$(bash -c 'for d in "${FEATURE_FORGE_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/fix-sweep.py" plan-coverage "{resolvedFeatureDir}/.verification/{findingsFile}" --json
```

Exit 0 with `"applicable": false` means the document declares no findings set or no plan to assert — proceed silently. Exit 1 → surface the **named** uncovered findings and any `claimed N, actual M` total mismatch, then resolve each one through the host's question mechanism per the **Decision Support** protocol in `references/shared-conventions.md`: either **author a covering execution step** into the Fix Execution Plan and execute it in this pass's Step 4, or **record an explicit justification** against that finding in the findings document. Never resolve a mismatch by editing the claimed total to match — re-derive which finding is missing and name it. Any finding still uncovered when you stop closes with `decisions` in Step 7, no advancement. Exit 2 → surface the `Error:` line verbatim and close with `failed`.

## Step 3: Handle User Decisions

If the "User Decisions Required" section has unresolved items:
1. Present each decision to the user with the context from the findings, using the host's question mechanism for each decision point. Follow the **Decision Support** protocol in `references/shared-conventions.md`: lead with a recommended option and put the trade-off in each option's description. When the findings provide clear evidence, recommend with confidence and cite it. When they don't, still offer a sensible default with the trade-offs, but flag it plainly as a judgment call rather than going neutral — a defaulted recommendation beats an unguided option dump.
2. Wait for answers before proceeding
3. Record decisions in the findings document under the "User Decisions Required" section (mark each as resolved)

If any decision is still unresolved when you stop — the user deferred it, the question mechanism was unavailable, or no answer arrived — do **not** apply the steps that depend on it. Close with `decisions` in Step 7: that is the specific outcome for unanswered decisions, it never advances the pipeline, and its resume action names the unresolved work. A user who explicitly defers the **whole fix pass** is `deferred` instead; an operational failure that is not merely an unanswered decision is `failed` (Step 7).

## Step 4: Execute Fix Steps

For each step in the "Execution Steps" section, in order:

1. **Check if already applied:** If the step appears in the "Fix Progress" section as `[APPLIED]`, skip it
2. **Check dependencies:** If the step depends on another step, verify that step is marked as applied
3. **Apply the fix:** Execute the change described in the step's "Action" field
4. **Verify the change:** Re-read the modified file and check that the change is correct and consistent with the step's rationale
5. **Record progress:** Append to the `## Fix Progress` section at the bottom of the findings document:
   ```
   - Step {N}: [APPLIED] {date} — {short summary of what was done}
   ```
6. If a step fails or produces unexpected results, STOP. Report the issue to the user. Do not continue to dependent steps. Any applied step stays recorded in `## Fix Progress` so a later run resumes rather than repeats, and this run closes with `failed` in Step 7 — no advancement.

**Shipped comments state intent, never measurement (anti-churn).** A fix pass writes **no empirical or quantified claims** into comments, docstrings, or test narration — no "measured", "probed and confirmed", no counts of what was checked, no blanket claims over enumerated cases. Every such claim is a fresh falsifiable surface for the next verify round; a chain of them is exactly how a fix loop stops converging. Shipped prose states what the code intends and what constraint binds it. The evidence — what was probed, how, with what result — belongs in the findings document's `## Fix Progress` entry (and the commit message), which are the sanctioned records for acceptance evidence.

**Closing sub-step — sweep for surviving occurrences of what you just corrected.** After the last plan step is applied and BEFORE Step 5 commits anything, while the working tree is still dirty, sweep this fix's own delta for text you removed that survives elsewhere. Pass no flags beyond `--json` — the exclusions the script applies by default are the correct ones in both a plugin repository and a consumer repository. Exit 1 means survivors were found: that is the sweep working, not a tool failure. Run:

```bash
R="$(bash -c 'for d in "${FEATURE_FORGE_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/fix-sweep.py" sweep --json
```

**Disposition every hit before Step 5.** Each hit names the file, the line, and the removed text it matched, so nothing needs re-deriving. Give every hit exactly one disposition — `FIXED` (you corrected the survivor now, in this pass, so the edit joins this same delta), `JUSTIFIED: {reason}` (it stands by decision: a deliberate quote, a historical or audit record), or `FALSE-POSITIVE: {reason}` (the match is not the corrected claim) — and record the sweep with its dispositions in the `## Fix Progress` section of the findings document, in this shape:

```
- Sweep: {date} — {K} needle(s), {N} survivor(s), {M} disposition(s)
  - {file}:{line} — "{matched removed text}" → FIXED {date}
  - {file}:{line} — "{matched removed text}" → JUSTIFIED: {reason}
  - {file}:{line} — "{matched removed text}" → FALSE-POSITIVE: {reason}
```

Detection is mechanical; disposition is judgment — a hit is a candidate, not automatically a defect. When you cannot classify a hit confidently, route that hit through the host's question mechanism following the same **Decision Support** protocol as Step 3: lead with a recommended disposition and put the trade-off in each option's description. A survivor left awaiting a user decision closes with `decisions` in Step 7; a survivor you can neither fix nor justify closes with `failed`; a fully dispositioned sweep leaves this pass on whatever outcome it otherwise maps to.

**Re-run the sweep once when a disposition edited files.** Those edits joined the same delta, so run the same command again to confirm they introduced no fresh survivors, and append a second `- Sweep:` block for the re-run. A hit already dispositioned `JUSTIFIED` or `FALSE-POSITIVE` — same file, same matched text — legitimately re-appears and needs no second disposition. A re-appearing hit that was dispositioned `FIXED` means the fix did not remove every occurrence: re-disposition it — correct it now, or close with `failed` — never leave it recorded as `FIXED`. One re-run is enough: do not loop. Exit 1 with no JSON payload on stdout is a crash, not survivors — surface the stderr traceback and close with `failed`.

**The sweep is never silent.** When the payload reports `"skipped": true` (exit 0 — no delta was available), append the visible notice `- Sweep: NOT RUN — no git delta ({reason})` under `## Fix Progress`, using the payload's `reason` verbatim, and continue on this pass's normal outcome. A skip is not a failure; exit 2 is — surface its `Error:` line verbatim and close with `failed`.

## Step 5: Record the Fixes Through `state-verify` and Commit

Never hand-author a verify entry, and never write a `verifiedStageVersion` value by hand. Record the fix pass with the `state-verify` verb described in the **Pipeline State Protocol** in `references/shared-conventions.md`, which owns its full flag surface, its status matrix, and the exit-2 failure protocol. `--stage` names the **served production stage** established in Step 1. `findings-applied` deliberately **clears** `verifiedStageVersion` and refuses `--verified-stage-version`: applying fixes is not verifying them, so the served stage's verification stays outstanding until a re-verify passes. Add `--epic "{epic}"` when the feature is an epic member — required, per the Pipeline State Protocol; omitting it for a member is an error and must never fall back to a same-named flat feature.

```bash
R="$(bash -c 'for d in "${FEATURE_FORGE_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-session.py" state-verify \
  --feature "{feature}" --stage "{servedStage}" --status findings-applied \
  --specs-dir "{specsDir}"
```

**Stage every disposition-edited path explicitly.** Commit 1's staging scope is the feature directory only, so a survivor you fixed outside it (Step 4's sweep) would otherwise be left uncommitted. Before committing, run one `git add <path>` per file recorded as `FIXED` in the sweep record — enumerated, one path at a time, never `git add -A` and never `git add .`. Those fixes then ride Commit 1 alongside the findings document that records them, and the tree is left clean for the re-verify and for the next stage's dirty-tree check.

Then follow the Git Commit Protocol in `references/shared-conventions.md`. If `gitCommitAfterStage` is true, stage files (`git add {resolvedFeatureDir}/` — or `{specsDir}/{epic}/` for an epic member so the member-state change commits atomically with the epic subtree) and commit with message `"{commitPrefix}({feature}): apply {mode} verification fixes"`. That is Commit 1, and the write above already recorded `commitHash: null` for it.

**Two-commit provenance — never `--amend`.** Record the provenance of Commit 1 in a second `state-verify` call, passing the **full 40-character** hash — an abbreviation is refused rather than expanded, and this call touches nothing but `commitHash`. Add `--epic "{epic}"` when the feature is an epic member — required, per the Pipeline State Protocol.

```bash
R="$(bash -c 'for d in "${FEATURE_FORGE_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-session.py" state-verify \
  --feature "{feature}" --stage "{servedStage}" \
  --commit-hash "$(git rev-parse HEAD)" --specs-dir "{specsDir}"
```

On exit 2 **nothing was recorded**: surface the `Error:` line verbatim together with the named feature (and epic), do not claim the fixes were persisted, and close with `failed` in Step 7 — the verify entry is unchanged, so no success block may be printed. A failed validation or a failed commit is `failed` for the same reason.

## Step 6: Re-verify Gate

Fixes are applied and recorded as `findings-applied`. That status makes **no** claim of freshness: the writer clears `verifiedStageVersion`, so the served stage's verification stays **outstanding** in the navigator's ledger, and only a re-verify that passes resolves it. Because a re-verify is the one thing that confirms the fixes actually resolved the findings, on a **direct** invocation **prompt** for it rather than leaving it as a passive suggestion — this is the same **Standard Verify Gate** the stage skills stamp (`references/stage-exit-protocol.md`).

**A nested owner presents no gate.** Return your structured result (served stage, outcome `applied`, findings file, steps applied) to the outer caller — it performs the mandatory re-verify itself — and print no terminal block of your own. This follows from the `owner:` token read at entry; it is never decided by how the invocation was phrased.

On a **direct** invocation, present the gate with the host's question mechanism using these three options — but only when your verify capability is `interactive` (Step 7):
- **Re-verify {feature} now** *(recommended)* — dispatch the clean-room `forge-verifier` subagent from this session in require-clean mode to confirm every finding is resolved. The dispatch is **scoped** per "Re-verify scope and convergence" in `references/stage-exit-protocol.md`: it confirms the prior report's findings against their acceptance evidence and examines this fix's delta — never a fresh full-checklist sweep — a finding with a recorded decision is never re-filed, and only an unresolved prior finding or a new blocking defect the fix introduced may block. The digest returns here so any remaining issue keeps its context. One-time — it does **not** change config. A clean-or-advisory-only result closes as `reverified`; unresolved prior findings or new blocking defects close as `reverify-findings` for the same served stage. **Escalation:** if that would be the second consecutive `reverify-findings` for this served stage (count the round-discriminated reports in `.verification/`), follow "Escalation (the round ledger)" in `references/stage-exit-protocol.md` before closing — present the digest and offer explicit acceptance of the residual findings; do not recommend another fix pass.
- **Re-verify now + enable auto-verify going forward** — re-verify now **and** patch `"autoVerify": true` into `forge.config.json` in place (preserve formatting and every other key) so future stages verify automatically, no prompt. This complements the `forge-init` opt-in. **Do not auto-commit this config change** — treat it like `notes`: a user-facing edit the user commits on their own cadence, never folded into a stage's artifact commit. Its outcome mapping is identical to the option above.
- **Skip for now** — an explicit deferral of the re-verify. It closes as **`deferred`**, never `reverified`: the fixes are recorded but nothing has confirmed them, and the served stage's verification stays outstanding until a re-verify passes, so the pipeline does not advance on this pass. Run `/feature-forge:forge {feature}` when you want pipeline status.

**Manual capability is not a skip, and not a deferral.** When your capability is `manual` (Step 7 — no question mechanism **and** no permitted dispatch), do not run clean-room and do not fabricate a choice nobody made: close with `applied`, and the script prints `/feature-forge:forge-verify {feature} --served-stage {servedStage}` as the primary action for the user to run. Offer the auto-verify enable as plain text only if a config write is possible.

**A re-verify that cannot run is an operational failure.** If the user chose to re-verify and the dispatch is refused, returns the `CLEAN_ROOM_UNAVAILABLE` sentinel, or returns no answer, the fixes remain recorded but nothing was confirmed: close with `failed`. Never report `reverified` on an unrun verify, and never treat an unavailable tool as an explicit user skip.

## Step 7: Close the Stage

**Ownership.** Pass the `owner: nested` / `owner: direct` value read at entry (absent the token: `direct`) straight through as `--owner`. As a **direct** owner you print the script's NEXT-STEPS block verbatim as your absolute final output, with nothing after its sentinel line. As a **nested** owner the payload carries `terminalOwnedBy: "outer"` and `nextSteps: null`: return your structured result to the caller and print no terminal block at all.

**Served stage.** Pass the stage established in Step 1 as `--served-stage`, so every branch command carries the diversion's thread forward. Never re-derive it here.

**Capability.** Determine `--verify-capability` before running the exit (full rule: `references/stage-exit-protocol.md`; summary: **Verify Capability** in `references/shared-conventions.md`). Pass `interactive` only when a question mechanism equivalent to the host's question mechanism is available **and** a clean-room `forge-verifier` may actually be dispatched right now; otherwise pass `manual`. Dispatch capability means **permitted** dispatch, not a listed tool — the test is "may I dispatch `forge-verifier` right now", not "is a dispatch tool in my tool surface". A session that bars *unsolicited* dispatch while offering a question mechanism is therefore **`interactive`, not `manual`**: the gate's affirmative choice is the user request that authorizes the dispatch. An auto-verify or re-verify directive under a no-unsolicited-dispatch bar is presented through the Step 6 gate and dispatched on the affirmative choice — never skipped, and never resolved by closing with an outcome that advances the pipeline.

**Outcome.** Invoke the exit **exactly once**, with the `--outcome` this run maps to. Every path lands on exactly one row; none may be left open:

| This run's result | `--outcome` | Authoritative action |
|---|---|---|
| No applicable findings document or steps (Step 1.5) | `no-findings` | Re-verify while verification is still owed; otherwise the live production successor |
| User decisions remain unresolved (Step 3) | `decisions` | Resume `forge-fix` naming the unresolved decisions; no advancement |
| A fix step, a validation, a commit, or a state write failed (Steps 4–6) | `failed` | Fix/navigator recovery; no advancement |
| Fixes persisted and re-verify has not been run (nested, or manual capability) | `applied` | Re-run `forge-verify` for the same served stage — re-verification is mandatory |
| A mandatory re-verify passed | `reverified` | The live production successor |
| A mandatory re-verify reported an unresolved prior finding or a new blocking defect (a clean-or-advisory-only result is `reverified`) | `reverify-findings` | `forge-fix` for the same served stage |
| The user explicitly deferred the fix pass or the re-verify (Steps 3, 6) | `deferred` | Deterministic `forge-fix`/navigator resume stating the findings remain unresolved; no advancement |

A cancellation, an unavailable tool, or a non-answer is `deferred` **only** when it was an explicit user choice and `failed` when it was an operational failure — an unavailable tool is never an explicit user skip, and neither ever becomes `reverified`. `applied` is not `reverified`: `findings-applied` cleared the freshness the writer deliberately dropped, so only `reverified` after a passing verify permits advancement.

**Round-ledger escalation binds this row on every capability.** Before closing `reverify-findings` that is the SECOND consecutive for this served stage (count the round-discriminated reports in `.verification/`), present the escalation dispositions per "Escalation (the round ledger)" in `references/stage-exit-protocol.md` — through the question mechanism when `interactive`, or printed as text (digest + the three dispositions, "Accept the residual findings" first) BEFORE the terminal block when `manual`. Never recommend another fix pass at this point.

Add `--epic "{epic}"` when the feature is an epic member. Pass no other flags.

**Close this stage with the Scripted Stage Exit** (contract: `references/stage-exit-protocol.md`; do not improvise a "Next steps" list). Run:

```bash
R="$(bash -c 'for d in "${FEATURE_FORGE_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-session.py" stage-exit --feature "{feature}" --stage forge-fix --owner "{owner}" --outcome "{FixOutcome}" --served-stage "{servedStage}" --specs-dir "{specsDir}" --host generic --verify-capability "{verify-capability}"
```

Obey the DIRECTIVES it prints, in the consumption order this protocol fixes: surface `invalidAutoVerifyKeys` and every `warnings` entry first; `runInStageVerify: true` → run the in-stage clean-room verify chain now (honoring `autoFixEligible`, and asking through the Standard Verify Gate first when you may not dispatch unsolicited); `verifyGate: "standard"` → present the Standard Verify Gate; `verifyGate: "manual-print"` → print the `verifyCommand` for the user and do **not** dispatch inline. Then, and only when `terminalOwnedBy` is `"self"`, **print the NEXT-STEPS block verbatim as your absolute last output — nothing after its sentinel line.** A `terminalOwnedBy: "outer"` payload carries `nextSteps: null`: return your structured result to the caller and print no terminal block at all.

---

## Host execution notes (Codex)

This skill was authored Claude-first; the body above refers to "the host's question mechanism", "the host's subagent mechanism", and "the host's background-execution mechanism". On Codex:

- **User input:** Codex has no structured question tool. Interactive session — ask the question directly and wait for the reply; never assume an answer. Under `codex exec` (non-interactive) — don't wait: take the Interaction Capability Ladder's declared conservative default, state it in your output, and use `no-default: abort — <question> requires a human answer` for an interview question with no sane default (`references/shared-conventions.md`).
- **Subagents:** spawn a Codex subagent using the named custom agent under `.codex/agents/<name>.toml`. Codex spawns a subagent only when explicitly asked; if the custom agent is unavailable, run that step inline yourself.
- **Background / monitoring:** run long-lived runner commands in your shell session and report progress as it arrives — there is no Claude-style background or monitoring tool to arm.
