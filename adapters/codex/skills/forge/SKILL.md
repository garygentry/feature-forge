---
# GENERATED — DO NOT EDIT. Source: skills/forge/SKILL.md. Regenerate: python3 scripts/build-adapters.py
name: forge
description: Feature-forge pipeline navigator and status dashboard. Use when the user references the forge pipeline, asks about forge status or progress, types /feature-forge:forge, or wants to check what stage a feature is at in the forge pipeline. Do NOT use for general feature requests, project status, or tasks unrelated to the forge development pipeline.
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
  - On `not-found` for a never-started feature, ask: "No pipeline exists for '{feature}'. Want to start one? Run `/feature-forge:forge-1-prd {feature}` to begin."
- If resolution succeeds, display the per-feature pipeline status dashboard (see format below) from `{resolvedFeatureDir}/`.

**If no feature name is provided:** list in two tiers.

1. **Epics first.** Identify epic directories as any `{specsDir}/*/` that directly contains an `epic-manifest.json` **and no `.pipeline-state.json` of its own** (an epic root is never itself a feature). For each epic, run:
   ```bash
R="$(bash -c 'for d in "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/epic-manifest.py" render-status "{epic}" --specs-dir "{specsDir}" --json
   ```
   and show one rollup line: `{epic} — {complete}/{total} complete, next: {nextCommand}`.
2. **Standalone features below.** Scan the remaining `{specsDir}/*/` that directly contain a `.pipeline-state.json` **without** an `epic` back-pointer. A nested member's `.pipeline-state.json` is **attributed to its epic (Tier 1), never listed as a standalone feature**.
   - **Rank by recency.** Run the recency ranker so the most-recently-touched active feature is the default — the user rarely has to type a name (especially on mobile after a clear your session / start a fresh session):
     ```bash
R="$(bash -c 'for d in "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-session.py" rank-features --specs-dir "{specsDir}" --json
     ```
     This returns `{active: [...], counts: {...}}` with active features sorted by `updatedAt` **descending** (row 0 is the most recent). Each row carries `currentStage`, `nextStage`, `nextCommand`, `verifyPending`, `verifyCommand`, `verifyStage`, `verifyState` (`fresh`/`stale`/`failing`/`never`/`none`), `autoVerify` (the effective per-stage setting), and `autoFix` (the single source of stage order). A top-level `invalidAutoVerifyKeys` array appears when `forge.config.json` has `autoVerifyStages` keys outside the five verify-capable stages — surface it as a one-line warning. The `active` list excludes nested epic members surfaced in Tier 1 — but the ranker scans them too, so ignore rows whose `epic` is non-null here (they belong to the epic rollup).
   - **Pick the feature:** if exactly one active standalone pipeline exists, show its dashboard. If multiple exist, use the host's question mechanism — **list the most-recently-updated first, labeled `(recommended)`**, each option's description showing its `currentStage` and a relative age ("updated 2h ago"). Always include a free-form escape ("A different feature / something else") so the user is never boxed in. Then render the chosen feature's dashboard.

If no epics and no standalone features exist, say: "No active feature pipelines found. Start one with `/feature-forge:forge-1-prd <feature-name>` or group several with `/feature-forge:forge-0-epic <epic-name>`."

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

After rendering a **per-feature** dashboard for an **active** pipeline (skip this for paused/abandoned pipelines and for the Epic Dashboard), don't stop at a text suggestion — actively offer to start the next stage. This removes the copy-paste-after-clear your session / start a fresh session chore that makes long, multi-stage runs painful (especially on mobile).

**1. Read the next step.** From the `rank-features --json` output (above), find this feature's row and read its `nextStage`, `nextCommand`, `verifyPending`, `verifyCommand`, `verifyStage`, `verifyState`, `autoVerify`, and `autoFix`. If the feature is not in the `active` list (paused/abandoned), or `nextStage` is `null` (every production stage complete), skip the drive prompt — instead congratulate the user and, if `forge-6-docs` has not run, offer it; otherwise note the pipeline is complete. If the payload has a non-empty `invalidAutoVerifyKeys`, print a one-line warning first (e.g. "⚠️ forge.config.json `autoVerifyStages` has unknown keys: … — they are ignored; fix the typo").

**2. Check the context window.** Run the context-usage helper so you can advise whether to continue here or start the next stage in a fresh session:
```bash
R="$(bash -c 'for d in "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-session.py" context-usage --json
```
- `{"available": true, ...}` → note `pct` (e.g. "context ~68% full") and `overThreshold`. Window/threshold come from `contextWindowTokens` / `contextWarnThreshold` in `forge.config.json` (the helper defaults to a 200k window and 0.7 threshold, and auto-bumps the assumed window to 1M once observed usage exceeds 200k; **on a 1M-context model set `contextWindowTokens: 1000000` so the percentage is accurate below 200k too** — 1M can't be detected from the transcript until usage crosses 200k).
- `{"available": false, ...}` → omit context advice silently (non-Claude host, or a fresh session with no transcript). Never treat this as an error.

**2b. Auto-verify branch (when `verifyPending` is true).** Before offering the advance gate, decide whether verify runs automatically:

- **`autoVerify` is true for the just-completed `verifyStage`** → **skip the verify question entirely** and run verify now, *provided it can run clean-room*. Auto-verify is safe to run unattended only because verify executes in a fresh `forge-verifier` subagent that inherits none of this session's context (so no clear your session / start a fresh session is needed and only a compact digest returns). Guard the clean-room assumption: proceed unattended **only when the `Agent` tool + `forge-verifier` subagent are available**. Invoke `feature-forge:forge-verify` via the `Skill` tool in **require-clean (`auto`) mode** — in that mode forge-verify refuses to run inline and returns a sentinel if the subagent is not dispatchable (see `skills/forge-verify/SKILL.md`). Then:
  - **Sentinel returned (clean-room unavailable)** → do **not** run verify inline. Degrade to the manual gate: fall through to step 3 with the **"Verify `{stage}` first (manual)"** option included, and if `overThreshold`, recommend "clear your session / start a fresh session, then verify in a clean session." Verify state stays outstanding; the stage is never advanced on false assurance.
  - **Verify passed / no findings** → proceed to the normal advance gate (step 3), no verify option.
  - **Verify found findings** →
    - **`autoFix` is true AND preconditions hold** — the findings document has **zero unresolved decision points** and the **working tree is clean** → invoke `feature-forge:forge-fix` via the `Skill` tool, then run a **mandatory re-verify** (require-clean mode). Advance only if the re-verify passes. On **any** precondition miss (decisions required, dirty tree), a forge-fix early stop, or a red re-verify → fall back to the digest + prompt below (never a silent partial mutation).
    - **`autoFix` is false (default), or preconditions failed** → present a **compact findings digest** as text, then the host's question mechanism: *Apply fixes now (forge-fix)* / *Review findings* / *Skip & advance*.
- **`autoVerify` is false/unconfigured** → do not auto-run; use the advance gate in step 3, which gains the folded opt-in verify options ("Verify `{stage}` now" and "Verify `{stage}` now + enable auto-verify going forward").

**3. Offer the next step via the host's question mechanism.** (Reached when auto-verify did not fully resolve the step, or `verifyPending` is false.) Output the dashboard + a one-line context note as text, then ask (per the Decision Support protocol in `references/shared-conventions.md`). This is the same **Stage Exit Protocol** the stage skills stamp (`references/stage-exit-protocol.md`) — a clean session at the boundary is recommended on its own merits, and `overThreshold` only modulates *how emphatically*, never *whether*. Options, in this order:
- **Start `{nextStage}` in a clean session** — **recommended, unconditionally**, at every boundary. A clean session is the right default for the next stage on its own merits, independent of window size. The work survives a clear because all state is on disk: instruct the user to clear your session / start a fresh session, then re-run `/feature-forge:forge {feature}` (or run `{nextCommand}` directly) in the fresh session. Note plainly that you cannot clear your session / start a fresh session for them. **When `overThreshold` is true**, strengthen this wording (the window is also genuinely full) and add mid-stage compaction advice; **when the window is healthy**, still recommend the clean session — `overThreshold` is a *secondary, additive* modifier here, not the clear on/off switch.
- **Continue in this session** — the always-available alternative, reasonable when the window is nearly empty and the user would rather not clear. Not the default.
- **Verify `{stage}` now** — include **only when `verifyPending` is true and `autoVerify` is false**, and the clean-room path is available. **Recommended**, since verify is clean-room and rarely worth skipping. Runs verify now (require-clean mode); **does not** change config.
- **Verify `{stage}` now + enable auto-verify going forward** — same trigger as the option above; runs verify now **and** patches `autoVerify: true` into `forge.config.json` in place (preserve formatting and other keys) so every future stage verifies automatically without prompting. This is the **folded** config-enable — it replaces the old post-hoc "make auto-verify the default?" follow-up. No silent config writes: the config changes **only** when the user picks this option.
- **Verify `{stage}` first (manual)** — include **only when `verifyPending` is true** and the clean-room path is unavailable (the Tier-2 degradation above), or the host lacks the `Skill`/`Agent` tools; selecting it runs `{verifyCommand}` (inline / manual). Offer the "enable auto-verify" choice as text only if a config write is possible.
- **Pick a different stage** — free-form escape to any stage or other action.

**4. Act on the choice.**
- **Clean session** (the default) → give the exact next command and the clear your session / start a fresh session-then-re-run instruction; do not invoke anything (you cannot clear your session / start a fresh session for the user).
- **Continue in this session** → if `autoInvokeNextStage` is true (default) **and** the `Skill` tool is available, invoke the chosen stage **via the `Skill` tool** in this same session (e.g. `skill: "feature-forge:forge-3-specs"`, `args: "{feature}"`) — no retyping, no paste. If `autoInvokeNextStage` is false, or the `Skill` tool is unavailable (a non-Claude host), fall back to printing `{nextCommand}` prominently for the user to run.
- **Verify now / Verify now + enable auto-verify** → invoke `feature-forge:forge-verify` via the `Skill` tool (require-clean mode). For the **enable-auto-verify** variant, additionally patch `autoVerify: true` into `forge.config.json` in place (preserve formatting and other keys) — never a silent write. On a non-Claude host or when degrading to the manual/inline gate, print `{verifyCommand}` instead.
- **Different stage** → honor the free-form request.

**Host fallback.** On a non-Claude host or when the `Skill`/`Agent` tools are unavailable, auto-verify never runs unattended — fall back to printing `{verifyCommand}` exactly as today, mirroring `autoInvokeNextStage`.

This applies whether the feature was named explicitly (`/feature-forge:forge {feature}`) or resolved from the recency default.

### Epic Dashboard

When the named argument is an epic (`{specsDir}/{name}/epic-manifest.json` exists), render the epic dashboard instead of a per-feature one. Run:

```bash
R="$(bash -c 'for d in "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/epic-manifest.py" render-status "{epic}" --specs-dir "{specsDir}" --json
```

and render from its output:

- **Epic header:** name + `status` (active | paused | abandoned | complete).
- **Dependency graph:** each feature with its `dependsOn`, as an arrow list or indented tree (the helper guarantees the graph is acyclic).
- **Per-feature rows:** reuse the **existing status indicators** below (✅/✅⚠️/🔄/⬜/❌/✅🔍/⏭️/⚠️), driven by each feature's derived `stage`/`status`. Mark `blocked` features and list their `unmetDeps`.
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
🔄 token-service    forge-3-specs (in progress)
⬜ api-gateway      blocked — waiting on token-service
✅ audit-log        complete

Actionable now: token-service
Next: /feature-forge:forge-3-specs token-service
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
- `/feature-forge:forge abandon {feature}` — Set `pipelineStatus` to `"abandoned"`. Use the host's question mechanism to confirm first, and state what's reversible: abandoning does not delete artifacts and can be undone with `/feature-forge:forge resume {feature}`, so the cost is low — but if the user really means "stop and discard," point out that `pause` is the better choice when they're only setting it aside. Offer **Abandon** · **Pause instead** · **Cancel**.
- `/feature-forge:forge run [{feature}]` — **Opt-in auto-advance.** Drive the feature through consecutive stages in one session instead of confirming each boundary. This is a convenience wrapper over **3b. Drive to the Next Stage** — same stage order, same context gate — just looped:
  1. Resolve the feature (if omitted, use the recency default from `rank-features`; if multiple are equally plausible, ask once via the host's question mechanism).
  2. **Before each stage,** run `forge-session.py context-usage`. If `overThreshold` is true, **stop** and recommend a clean session (give the exact `{nextCommand}` and the clear your session / start a fresh session-then-re-run instruction) — never auto-clear your session / start a fresh session.
  3. Otherwise invoke the next stage's skill via the `Skill` tool, let it run to its natural stopping point, then re-read state and continue from step 2.
  4. **Stop conditions:** the next stage is an interview/decision point that calls the host's question mechanism (PRD and tech inherently pause for input — let them); `nextStage` is `null` (pipeline complete); context over threshold; or a stage signals it needs human input / is blocked. Always report where the loop stopped and why.
  Per-stage confirmation (3b) remains the default — `run` is only used when the user explicitly asks to "run" / "drive" / "auto-advance" the pipeline. On a non-Claude host where the `Skill` tool is unavailable, fall back to printing the ordered list of commands to run.

**Epic lifecycle.** When the argument names an **epic** (`{specsDir}/{name}/epic-manifest.json` exists), `pause` / `resume` / `abandon` operate on the epic manifest, not a `.pipeline-state.json`:

- Set the manifest's top-level `status` (`paused` / `active` / `abandoned`) via the helper's `set-status` mutator — an atomic write that also bumps `updatedAt`:
  ```bash
R="$(bash -c 'for d in "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/epic-manifest.py" set-status "{epic}" --status paused --specs-dir "{specsDir}"
  ```
  For `complete`, do **not** set the status directly — completion is *derived* from member states (the rollup), so the manifest `status` is a lifecycle flag, never a completion signal.
- **Member feature states are NOT silently mutated.** Pausing/abandoning the epic changes only the manifest `status`. Before doing so, use the host's question mechanism to make the relationship explicit and frame the trade-off: "Pausing the epic does not pause its in-flight member features. {N} members are active. Pause the epic only, or also pause each member?" Recommend **epic only** when members are mid-stage and the user just wants to stop *new* orchestration; recommend **also pause members** when the intent is a hard freeze of all in-flight work. If the user opts to pause members too, update each member's own `pipelineStatus` **individually and visibly** (one explicit action per member), never as a hidden side-effect.
- Commit the change via the Git Commit Protocol, staging `{specsDir}/{epic}/`.

When listing features, show active pipelines by default. Include a count of paused/abandoned: "3 active pipelines (1 paused, 1 abandoned — use `/feature-forge:forge list all` to see them)."

## Gotchas

- Never modify any spec files, backlog files, or pipeline state beyond the `notes`, `updatedAt`, and `pipelineStatus` fields. The navigator is read-only except for notes and lifecycle commands.
- If a user asks to "continue" or "pick up where I left off" without naming a feature, check for active pipelines before asking. Only ask if ambiguous.
- The pipeline state file is the source of truth. Don't infer stage from the existence of files alone — a file might exist from a previous incomplete run.

---

## Host execution notes (Codex)

This skill was authored Claude-first; the body above refers to "the host's question mechanism", "the host's subagent mechanism", and "the host's background-execution mechanism". On Codex:

- **User input:** Codex has no structured question tool — ask the question directly and wait for the user's reply before proceeding. Never skip a required question or assume an answer.
- **Subagents:** spawn a Codex subagent using the named custom agent under `.codex/agents/<name>.toml`. Codex spawns a subagent only when explicitly asked; if the custom agent is unavailable, run that step inline yourself.
- **Background / monitoring:** run long-lived runner commands in your shell session and report progress as it arrives — there is no Claude-style background or monitoring tool to arm.
