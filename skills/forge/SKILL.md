---
name: forge
description: "Feature-forge pipeline navigator and status dashboard. Use when the user references the forge pipeline, asks about forge status or progress, types /feature-forge:forge, or wants to check what stage a feature is at in the forge pipeline. Do NOT use for general feature requests, project status, or tasks unrelated to the forge development pipeline."
metadata:
  argument-hint: "<feature-name> (optional — lists all active features if omitted)"
---

# Feature Forge — Pipeline Navigator

You are the navigator for the feature-forge development pipeline. Your job is to orient the user: show where they are, what's been done, and what's next.

## Behavior

### 1. Read Configuration

Read and follow `references/shared-conventions.md` for configuration reading (feature name validation, config defaults, force mode).

For pipeline architecture details, read `references/process-overview.md`.

### 2. Determine Context

**If a feature name is provided** (e.g., `/feature-forge:forge auth`):
- **First test whether the name is an epic:** if `{specsDir}/{name}/epic-manifest.json` exists, render the **Epic Dashboard** (see format below) and stop — do not treat it as a feature.
- Otherwise, resolve the name via the **Feature Directory Resolution** block in `references/shared-conventions.md` (so a nested epic-member name finds its dashboard too). On a resolution failure (`not-found` / `ambiguous` at exit 1; `unsafe-name` or a path-containment escape at exit 2), surface it verbatim.
  - On `not-found`, first run the cross-branch discovery step from that same Feature Directory Resolution block (`forge-session.py discover-feature` — the state may live on a topic branch or an unfetched remote branch). Candidates → offer switch / fetch+switch per that block (explicit accept + clean tree only), then re-resolve and render the dashboard. Only when discovery also returns nothing, ask: "No pipeline exists for '{feature}' on any branch. Want to start one? Run `/feature-forge:forge-1-prd {feature}` to begin." Never render a dashboard from memory of earlier sessions (anti-fabrication guard).
- If resolution succeeds, display the per-feature pipeline status dashboard (see format below) from `{resolvedFeatureDir}/`.

**If no feature name is provided:** list in two tiers.

1. **Epics first.** Identify epic directories as any `{specsDir}/*/` that directly contains an `epic-manifest.json` **and no `.pipeline-state.json` of its own** (an epic root is never itself a feature). For each epic, run:
   ```bash
R="$(bash -c 'for d in "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/epic-manifest.py" render-status "{epic}" --specs-dir "{specsDir}" --json
   ```
   and show one rollup line: `{epic} — {complete}/{total} complete, next: {nextCommand}`.
2. **Standalone features below.** Scan the remaining `{specsDir}/*/` that directly contain a `.pipeline-state.json` **without** an `epic` back-pointer. A nested member's `.pipeline-state.json` is **attributed to its epic (Tier 1), never listed as a standalone feature**.
   - **Rank by recency.** Run the recency ranker so the most-recently-touched active feature is the default — the user rarely has to type a name (especially on mobile after a `/clear`):
     ```bash
R="$(bash -c 'for d in "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-session.py" rank-features --specs-dir "{specsDir}" --json
     ```
     This returns `{active: [...], counts: {...}}` with active features sorted by `updatedAt` **descending** (row 0 is the most recent). Each row carries `currentStage`, `nextStage`, `nextCommand`, `verifyPending`, `verifyCommand`, `verifyStage`, `verifyState` (`fresh`/`stale`/`failing`/`never`/`none`), `autoVerify` (the effective per-stage setting), `autoFix` (the single source of stage order), and `verifyGate` (`none`/`auto`/`standard` — the single resolved verify-gate, computed once by the ranker; read it rather than re-deriving from `verifyPending`+`autoVerify`). A top-level `invalidAutoVerifyKeys` array appears when `forge.config.json` has `autoVerifyStages` keys outside the five verify-capable stages — surface it as a one-line warning. The `active` list excludes nested epic members surfaced in Tier 1 — but the ranker scans them too, so ignore rows whose `epic` is non-null here (they belong to the epic rollup).
   - **Pick the feature:** if exactly one active standalone pipeline exists, show its dashboard. If multiple exist, use `AskUserQuestion` — **list the most-recently-updated first, labeled `(recommended)`**, each option's description showing its `currentStage` and a relative age ("updated 2h ago"). Always include a free-form escape ("A different feature / something else") so the user is never boxed in. Then render the chosen feature's dashboard.

If no epics and no standalone features exist **on the current branch**, do not conclude the pipeline is empty yet — the state may live on topic branches (a fresh clone / default-branch session sees nothing on disk). Run `discover-feature --all` (via the standard prelude: `python3 "$R/scripts/forge-session.py" discover-feature --all --specs-dir "{specsDir}" --json`). If it surfaces features, list them with their branches and offer to switch (explicit accept + clean tree only, per the Feature Directory Resolution block), then render that feature's dashboard. Only when `--all` also returns nothing, say: "No active feature pipelines found. Start one with `/feature-forge:forge-1-prd <feature-name>` or group several with `/feature-forge:forge-0-epic <epic-name>`." Never fabricate a dashboard from memory of earlier sessions.

The feature name must be a single kebab-case token. If the user provides multiple words (e.g., "user auth flow"), convert to kebab-case: `user-auth-flow`.

### 3. Pipeline Status Dashboard

Write pipeline state conforming to `references/pipeline-state-schema.json`.

Display a clear, scannable status for the feature:

```
Feature: {feature}  [active]
Stage: {currentStage} ({status}, started {relative time})

✅ forge-1-prd     → PRD.md (v{n})
⬜ forge-verify     (prd)          ← show only if forge-1-prd is complete
✅ forge-2-tech    → tech-spec.md (v{n}, ⚠️ not yet verified)
⬜ forge-verify     (tech)         ← show only if forge-2-tech is complete
🔄 forge-3-specs   → in progress
⬜ forge-verify     (specs)        ← show only if forge-3-specs is complete
⬜ forge-4-backlog
⬜ forge-verify     (backlog)      ← show only if forge-4-backlog is complete
⬜ forge-5-loop
⬜ forge-6-docs

Next: Continue with /feature-forge:forge-3-specs {feature}
      Or verify tech-spec with /feature-forge:forge-verify {feature}

Notes: "{any persisted notes}"
```

Use these status indicators:
- ✅ = complete
- ✅⚠️ = complete but not yet verified
- 🔄 = in progress
- ⬜ = pending
- ❌ = verification found issues (not yet fixed)
- ✅🔍 = verified and fixes applied
- ⏭️ = verification skipped (user chose to proceed without verifying)
- ⚠️ = stale (built against an older version of an upstream artifact)

### 3b. Drive to the Next Stage

After rendering a **per-feature** dashboard for an **active** pipeline (skip this for paused/abandoned pipelines and for the Epic Dashboard), don't stop at a text suggestion — actively offer to start the next stage. This removes the copy-paste-after-`/clear` chore that makes long, multi-stage runs painful (especially on mobile).

**1. Read the next step.** From the `rank-features --json` output (above), find this feature's row and read its `nextStage`, `nextCommand`, `verifyPending`, `verifyCommand`, `verifyStage`, `verifyState`, `autoVerify`, `autoFix`, and `verifyGate` (the resolved gate: `none` → no verify action; `auto` → the §2b catch-up; `standard` → the §3 gate). If the feature is not in the `active` list (paused/abandoned), or `nextStage` is `null` (every production stage complete), skip the drive prompt — instead congratulate the user and, if `forge-6-docs` has not run, offer it; otherwise the whole pipeline is done, so **route into the Completion hand-off block below instead of dead-ending** (steps 2/2b/3 do not apply — there is no next stage to drive). If the payload has a non-empty `invalidAutoVerifyKeys`, print a one-line warning first (e.g. "⚠️ forge.config.json `autoVerifyStages` has unknown keys: … — they are ignored; fix the typo").

**Detached-epic hint (completion of a *standalone* feature, Issue #125).** When `nextStage` is `null` for a feature whose row has no `epic` (a standalone completion), run `discover-feature "{feature}" --json` (via the standard prelude) *before* congratulating. If any candidate has `isEpicMember: true` on another branch, add an **additive, non-blocking** hint — it does not change the completion, only flags a likely split-brain: "⚠️ Heads-up: `{feature}` matches a member of epic `{epic}` on branch `{stateBranch}`. This standalone pipeline may have been forged detached from that epic. To reconcile, see `docs/recovery-detached-epic-member.md` (or continue — this is only a heads-up)." Skip the hint for epic-member rows (their `epic` is non-null) and when discovery surfaces no epic-member candidate.

**Completion hand-off (fires when `nextStage` is `null` AND `forge-6-docs` has run — the pipeline is fully complete, Issue #124).** Do not dead-end on "pipeline is complete" — after congratulating, point the user at the next unit of work. This is a **terminal branch**: the drive steps (2/2b/3) do not run.

- **Epic member** (this feature's `rank-features` row has a non-null `epic`, i.e. its `.pipeline-state.json` carries an `epic` back-pointer): run `epic-manifest.py render-status "{epic}" --specs-dir "{specsDir}" --json` (standard prelude; you likely already have this from the Tier-1 epic rollup — reuse it rather than re-running). Then:
  - If `actionable` is non-empty, offer the next member via `AskUserQuestion`: *"Epic '{epic}' has {total−complete} feature(s) left — next up: **{actionable[0].name}** (`{actionable[0].nextCommand}`). Start it now?"* On accept, drive it exactly like a normal next stage (honor `autoInvokeNextStage` + `Skill`-tool availability per step 3's Continue-in-this-session rule; else print `{nextCommand}`). List any remaining `actionable` members as also-available.
  - If `actionable` is empty but the epic is **not** fully complete (members blocked on unmet `dependsOn`), say so and point at the blockers rather than offering a start.
  - If the epic is **fully complete** (`rollup.complete == rollup.total`, `total > 0`), congratulate on the whole epic and offer the epic-level architecture doc (`/feature-forge:forge-6-docs` already surfaces this — mention it) and/or that the epic can be marked complete (`/feature-forge:forge {epic}` renders the finished dashboard).
- **Standalone** (row's `epic` is null): offer to start a fresh feature — *"Start a new feature: `/feature-forge:forge-1-prd <feature-name>` (or group several with `/feature-forge:forge-0-epic <epic-name>`)."* Then, from the `rank-features` `active` list, surface any **other** active pipelines (exclude this just-completed one) as a one-line list with their `nextCommand`s so the user can jump straight back into in-flight work. If the **detached-epic hint above fired** for this feature, lead with that recovery path (`docs/recovery-detached-epic-member.md`) — the split-brain reconcile is the more likely next action than starting something new.

**2. Check the context window.** Run the context-usage helper so you can advise whether to continue here or start the next stage in a fresh session:
```bash
R="$(bash -c 'for d in "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-session.py" context-usage --json
```
- `{"available": true, ...}` → note `pct` (e.g. "context ~68% full") and `overThreshold`. Window/threshold come from `contextWindowTokens` / `contextWarnThreshold` in `forge.config.json` (the helper defaults to a 200k window and 0.7 threshold, and auto-bumps the assumed window to 1M once observed usage exceeds 200k; **on a 1M-context model set `contextWindowTokens: 1000000` so the percentage is accurate below 200k too** — 1M can't be detected from the transcript until usage crosses 200k).
- `{"available": false, ...}` → omit context advice silently (non-Claude host, or a fresh session with no transcript). Never treat this as an error.

**2b. Auto-verify catch-up (when `verifyPending` is true).** Under this behavior the just-completed authoring stage runs auto-verify **in-stage** (`references/stage-exit-protocol.md`, in-stage verify block), which clears `verifyPending` — so on the normal path this branch does **nothing**. It fires only as a **catch-up**: `verifyPending` is still true because the producing stage could not dispatch a clean-room subagent (non-Claude host), or ran before this behavior landed. When it does fire, decide whether verify runs automatically (identical logic to the in-stage run, so a stage that already verified is never double-verified):

- **`autoVerify` is true for the just-completed `verifyStage`** → **skip the verify question entirely** and run verify now, *provided it can run clean-room*. Auto-verify is safe to run unattended only because verify executes in a fresh `forge-verifier` subagent that inherits none of this session's context (so no `/clear` is needed and only a compact digest returns). Guard the clean-room assumption: proceed unattended **only when the `Agent` tool + `forge-verifier` subagent are available**. Invoke `feature-forge:forge-verify` via the `Skill` tool in **require-clean (`auto`) mode** — in that mode forge-verify refuses to run inline and returns a sentinel if the subagent is not dispatchable (see `skills/forge-verify/SKILL.md`). Then:
  - **Sentinel returned (clean-room unavailable)** → do **not** run verify inline. Degrade to the manual gate: fall through to step 3 with the **"Verify `{stage}` first (manual)"** option included, and if `overThreshold`, recommend "/clear, then verify in a clean session." Verify state stays outstanding; the stage is never advanced on false assurance.
  - **Verify passed / no findings** → proceed to the normal advance gate (step 3), no verify option.
  - **Verify found findings** →
    - **`autoFix` is true AND preconditions hold** — the findings document has **zero unresolved decision points** and the **working tree is clean** → invoke `feature-forge:forge-fix` via the `Skill` tool, then run a **mandatory re-verify** (require-clean mode). Advance only if the re-verify passes. On **any** precondition miss (decisions required, dirty tree), a forge-fix early stop, or a red re-verify → fall back to the digest + prompt below (never a silent partial mutation).
    - **`autoFix` is false (default), or preconditions failed** → present a **compact findings digest** as text, then `AskUserQuestion`: *Apply fixes now (forge-fix)* / *Review findings* / *Skip & advance*.
- **`autoVerify` is false/unconfigured** → do not auto-run; use the advance gate in step 3, which gains the folded opt-in verify options ("Verify `{stage}` now" and "Verify `{stage}` now + enable auto-verify going forward").

**3. Offer the next step via `AskUserQuestion`.** (Reached when auto-verify did not fully resolve the step, or `verifyPending` is false.) Output the dashboard + a one-line context note as text, then ask (per the Decision Support protocol in `references/shared-conventions.md`). **Present this gate exactly once and act only on the option the user chooses — never also narrate the not-taken branch.** Concretely: do not print the "start in a clean session" recommendation as prose and *then* auto-invoke the next stage in the same session (or the reverse) — the `AskUserQuestion` answer is the single decision, and only the chosen path's action follows. This is the same **Stage Exit Protocol** the stage skills stamp (`references/stage-exit-protocol.md`) — a clean session at the boundary is recommended on its own merits, and `overThreshold` only modulates *how emphatically*, never *whether*. Options, in this order:
- **Start `{nextStage}` in a clean session** — **recommended, unconditionally**, at every boundary. A clean session is the right default for the next stage on its own merits, independent of window size. The work survives a clear because all state is on disk: instruct the user to `/clear`, then re-run `/feature-forge:forge {feature}` (or run `{nextCommand}` directly) in the fresh session. Note plainly that you cannot `/clear` for them. **When `overThreshold` is true**, strengthen this wording (the window is also genuinely full) and add mid-stage compaction advice; **when the window is healthy**, still recommend the clean session — `overThreshold` is a *secondary, additive* modifier here, not the clear on/off switch.
- **Continue in this session** — the always-available alternative, reasonable when the window is nearly empty and the user would rather not clear. Not the default.
- **Verify `{stage}` now** — include **only when `verifyPending` is true and `autoVerify` is false**, and the clean-room path is available. **Recommended**, since verify is clean-room and rarely worth skipping. Runs verify now (require-clean mode); **does not** change config.
- **Verify `{stage}` now + enable auto-verify going forward** — same trigger as the option above; runs verify now **and** patches `autoVerify: true` into `forge.config.json` in place (preserve formatting and other keys) so every future stage verifies automatically without prompting. This is the **folded** config-enable — it replaces the old post-hoc "make auto-verify the default?" follow-up. No silent config writes: the config changes **only** when the user picks this option.
- **Verify `{stage}` first (manual)** — include **only when `verifyPending` is true** and the clean-room path is unavailable (the Tier-2 degradation above), or the host lacks the `Skill`/`Agent` tools; selecting it runs `{verifyCommand}` (inline / manual). Offer the "enable auto-verify" choice as text only if a config write is possible.
- **Pick a different stage** — free-form escape to any stage or other action.

**4. Act on the choice.**
- **Clean session** (the default) → give the exact next command and the `/clear`-then-re-run instruction; do not invoke anything (you cannot `/clear` for the user).
- **Continue in this session** → if `autoInvokeNextStage` is true (default) **and** the `Skill` tool is available, invoke the chosen stage **via the `Skill` tool** in this same session (e.g. `skill: "feature-forge:forge-3-specs"`, `args: "{feature}"`) — no retyping, no paste. If `autoInvokeNextStage` is false, or the `Skill` tool is unavailable (a non-Claude host), fall back to printing `{nextCommand}` prominently for the user to run.
- **Verify now / Verify now + enable auto-verify** → invoke `feature-forge:forge-verify` via the `Skill` tool (require-clean mode). For the **enable-auto-verify** variant, additionally patch `autoVerify: true` into `forge.config.json` in place (preserve formatting and other keys) — never a silent write. On a non-Claude host or when degrading to the manual/inline gate, print `{verifyCommand}` instead.
- **Different stage** → honor the free-form request.

**Host fallback.** On a non-Claude host or when the `Skill`/`Agent` tools are unavailable, auto-verify never runs unattended — fall back to printing `{verifyCommand}` exactly as today, mirroring `autoInvokeNextStage`.

This applies whether the feature was named explicitly (`/feature-forge:forge {feature}`) or resolved from the recency default.

### Epic Dashboard

When the named argument is an epic (`{specsDir}/{name}/epic-manifest.json` exists), render the epic dashboard instead of a per-feature one. Run:

```bash
R="$(bash -c 'for d in "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/epic-manifest.py" render-status "{epic}" --specs-dir "{specsDir}" --json
```

and render from its output:

- **Epic header:** name + `status` (active | paused | abandoned | complete).
- **Dependency graph:** each feature with its `dependsOn`, as an arrow list or indented tree (the helper guarantees the graph is acyclic).
- **Per-feature rows:** reuse the **existing status indicators** below (✅/✅⚠️/🔄/⬜/❌/✅🔍/⏭️/⚠️), driven by each feature's derived `stage`/`status`. Mark `blocked` features and list their `unmetDeps`.
- **Pending epic changes:** for any feature with `openEpicChangeRequests > 0`, append a ⚠️ marker and a hint: *"N pending epic change(s) — run `/feature-forge:forge-0-epic {epic}` to reconcile."* If `blockingEpicChangeRequests > 0`, use a stronger marker (⚠️ **blocking**) and word it *"reconcile the epic **before** writing specs"* — this mirrors the pause-now vs finish-then split that stage-exit already routes on. Take these counts **only** from `render-status --json` (`features[].openEpicChangeRequests` / `.blockingEpicChangeRequests`); do not read member `.pipeline-state.json` directly for them.
- **Actionable vs blocked:** list the `actionable` set and the recommended `nextCommand`.
- **Rollup:** `{complete}/{total} features complete`.

Example:

```
Epic: auth-overhaul  [active]   —   2/4 features complete

Dependency graph:
  config-store      (no deps)
  token-service     → config-store
  api-gateway       → token-service
  audit-log         (no deps)

✅ config-store     complete
🔄 token-service    forge-3-specs (in progress) — ⚠️ 1 pending epic change
⬜ api-gateway      blocked — waiting on token-service
✅ audit-log        complete

Actionable now: token-service
Next: /feature-forge:forge-3-specs token-service
⚠️ Pending epic changes: token-service (1). Run /feature-forge:forge-0-epic auth-overhaul to reconcile.
```

All of this is reconstructed **purely from disk** — the manifest plus each member's `.pipeline-state.json`, with no in-memory state — so a fresh session renders the same dashboard. If `render-status` fails, do not render a partial dashboard; surface per the exit-1/exit-2 split in the **Feature Directory Resolution** block of `references/shared-conventions.md` (exit 1 → parse `{findings[]}` from stdout; exit 2 → surface the plain `Error:` stderr line verbatim).

### 4. Notes Management

If the user says something like "note: switching to jose for JWT" or "remember: we decided X", update the `notes` field in `.pipeline-state.json`. This helps preserve context across session clears.

### 5. Available Commands Reference

When showing the dashboard, include a compact reference:

```
Commands:
  /feature-forge:forge-1-prd <feature>      Create requirements document
  /feature-forge:forge-2-tech <feature>     Create technical spec
  /feature-forge:forge-3-specs <feature>    Create implementation specs
  /feature-forge:forge-4-backlog <feature>  Generate rauf backlog
  /feature-forge:forge-5-loop <feature>  Run rauf autonomous loop
  /feature-forge:forge-6-docs <feature>     Generate architecture docs
  /feature-forge:forge-verify <feature>     Run verification on current stage
```

### 6. Pipeline Lifecycle Commands

Support these sub-commands for pipeline lifecycle management:
- `/feature-forge:forge pause {feature}` — Set `pipelineStatus` to `"paused"`. Do NOT modify `currentStage` or any stage statuses. The pipeline freezes exactly as-is. Show a confirmation.
- `/feature-forge:forge resume {feature}` — Set `pipelineStatus` back to `"active"`. Calculate how long the feature was paused (from `updatedAt` to now). If paused for more than 24 hours, show a hint: "This feature was paused for {duration}. Session context may have been lost — consider re-running `/feature-forge:forge-{currentStage} {feature}` to rebuild context."
- `/feature-forge:forge abandon {feature}` — Set `pipelineStatus` to `"abandoned"`. Use `AskUserQuestion` to confirm first, and state what's reversible: abandoning does not delete artifacts and can be undone with `/feature-forge:forge resume {feature}`, so the cost is low — but if the user really means "stop and discard," point out that `pause` is the better choice when they're only setting it aside. Offer **Abandon** · **Pause instead** · **Cancel**.
- `/feature-forge:forge run [{feature}]` — **Opt-in auto-advance.** Drive the feature through consecutive stages in one session instead of confirming each boundary. This is a convenience wrapper over **3b. Drive to the Next Stage** — same stage order, same context gate — just looped:
  1. Resolve the feature (if omitted, use the recency default from `rank-features`; if multiple are equally plausible, ask once via `AskUserQuestion`).
  2. **Before each stage,** run `forge-session.py context-usage`. If `overThreshold` is true, **stop** and recommend a clean session (give the exact `{nextCommand}` and the `/clear`-then-re-run instruction) — never auto-`/clear`.
  3. Otherwise invoke the next stage's skill via the `Skill` tool, let it run to its natural stopping point, then re-read state and continue from step 2.
  4. **Stop conditions:** the next stage is an interview/decision point that calls `AskUserQuestion` (PRD and tech inherently pause for input — let them); `nextStage` is `null` (pipeline complete); context over threshold; or a stage signals it needs human input / is blocked. Always report where the loop stopped and why.
  Per-stage confirmation (3b) remains the default — `run` is only used when the user explicitly asks to "run" / "drive" / "auto-advance" the pipeline. On a non-Claude host where the `Skill` tool is unavailable, fall back to printing the ordered list of commands to run.

**Epic lifecycle.** When the argument names an **epic** (`{specsDir}/{name}/epic-manifest.json` exists), `pause` / `resume` / `abandon` operate on the epic manifest, not a `.pipeline-state.json`:

- Set the manifest's top-level `status` (`paused` / `active` / `abandoned`) via the helper's `set-status` mutator — an atomic write that also bumps `updatedAt`:
  ```bash
R="$(bash -c 'for d in "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/epic-manifest.py" set-status "{epic}" --status paused --specs-dir "{specsDir}"
  ```
  For `complete`, do **not** set the status directly — completion is *derived* from member states (the rollup), so the manifest `status` is a lifecycle flag, never a completion signal.
- **Member feature states are NOT silently mutated.** Pausing/abandoning the epic changes only the manifest `status`. Before doing so, use `AskUserQuestion` to make the relationship explicit and frame the trade-off: "Pausing the epic does not pause its in-flight member features. {N} members are active. Pause the epic only, or also pause each member?" Recommend **epic only** when members are mid-stage and the user just wants to stop *new* orchestration; recommend **also pause members** when the intent is a hard freeze of all in-flight work. If the user opts to pause members too, update each member's own `pipelineStatus` **individually and visibly** (one explicit action per member), never as a hidden side-effect.
- Commit the change via the Git Commit Protocol, staging `{specsDir}/{epic}/`.

When listing features, show active pipelines by default. Include a count of paused/abandoned: "3 active pipelines (1 paused, 1 abandoned — use `/feature-forge:forge list all` to see them)."

## Gotchas

- Never modify any spec files, backlog files, or pipeline state beyond the `notes`, `updatedAt`, and `pipelineStatus` fields. The navigator is read-only except for notes and lifecycle commands.
- If a user asks to "continue" or "pick up where I left off" without naming a feature, check for active pipelines before asking. Only ask if ambiguous.
- The pipeline state file is the source of truth. Don't infer stage from the existence of files alone — a file might exist from a previous incomplete run.
