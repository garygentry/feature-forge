# Shared Pipeline Conventions

These conventions apply to every forge pipeline skill. Skills reference this file to avoid duplicating shared logic.

## Feature Name Requirement

Every pipeline skill requires a feature name as the first argument (e.g., `/feature-forge:forge-1-prd auth`).

If no feature name is provided:
1. STOP IMMEDIATELY
2. Do NOT attempt to guess or infer a feature name
3. Ask the user to provide one
4. Do NOT proceed until a feature name is explicitly given
5. The feature name must be a single kebab-case token. If the user provides multiple words (e.g., "user auth flow"), convert to kebab-case: `user-auth-flow`.

## User Input Protocol

### CRITICAL GUARDRAIL: Use AskUserQuestion for All Questions

You MUST use the `AskUserQuestion` tool whenever you need the user's input before proceeding. This includes yes/no confirmations, choices between options, interview questions, and feedback on artifacts. NEVER output questions as inline prose text — the user may not be prompted and the session will stall.

**Required turn structure:** Output your analysis, findings, or context as regular text. Then call `AskUserQuestion` with your questions. Do NOT mix questions into your text output.

**WRONG — questions as inline prose (causes stalling):**
```
I found that the codebase uses React and TanStack Router. Here are my questions:
1. Where should this component live?
2. Should we use server-side rendering?
```

**RIGHT — context as text, questions via tool:**
```
I found that the codebase uses React and TanStack Router.
[then call AskUserQuestion with: "1. Where should this component live? 2. Should we use server-side rendering?"]
```

### Decision Support: Help the User Choose

When an `AskUserQuestion` carries substantive options (a real choice — not a trivial yes/no confirmation), do not just list them. The interview stages have already done codebase research and integration analysis; surfacing that synthesis at the decision moment is the whole point. For every such question:

- **Lead with a recommended option.** Place it first and label it `(recommended)` (matching the `AskUserQuestion` "(Recommended)" convention).
- **Put the trade-off in each option's `description`.** Say why you'd pick it and what you give up versus the alternatives — the cost, not just the benefit.
- **State a one-line rationale** in the text before the question for *why* the recommendation wins.

Two modes, and make clear which one you're in:

- **Evidence-backed** — codebase evidence, an established convention, or a clear technical rationale favors one option. Recommend it with confidence and cite the evidence ("the codebase already uses X, so…").
- **Preference** — no option clearly wins (taste, team workflow, risk appetite). Still offer a sensible **default** and the trade-offs, but say plainly this is a judgment call / the user's preference, so you don't manufacture false confidence.

**The only thing to avoid is false confidence** — recommending as if evidence-backed when it's really preference. Never respond to the absence of a clear winner by going silent: a defaulted recommendation with honest trade-offs always beats a neutral option dump.

For genuinely comparable artifacts (competing module structures, two code snippets, layout variants), use the `AskUserQuestion` `preview` field to show them side-by-side.

The **Branch Setup** block below is the reference pattern: a strong recommendation as the first option, rationale inline, the alternative still available, never a hard-stop.

## Configuration Reading

Read `forge.config.json` from the project root. If it doesn't exist, use defaults.

If `forge.config.json` does not exist and no `.pipeline-state.json` files exist anywhere in `{specsDir}/`, suggest: "No forge.config.json found. Run `/feature-forge:forge-init` to create one with defaults, or I'll use built-in defaults. Want me to continue with defaults?"

Extract these config values (use defaults if not present):
- `specsDir` (default: `./specs`)
- `docsDir` (default: `./docs/architecture`)
- `backlogDir` (default: null — backlog lives at `{specsDir}/{feature}/backlog.json`; when `backlogDir` is configured, forge-4 composes `{backlogDir}/{feature}/`)
- `gitCommitAfterStage` (default: true)
- `commitPrefix` (default: `forge`)
- `branchPerFeature` (default: true)
- `branchPrefix` (default: `forge/`)
- `loopIterationMultiplier` (default: `1.5`)
- `autoInvokeNextStage` (default: `true` — the `/feature-forge:forge` navigator auto-invokes the next stage via the `Skill` tool after the user confirms; `false` keeps copy-paste behavior. Navigator-only.)
- `contextWindowTokens` (default: `null` — context window used by the navigator's context-usage check; `null` infers from the session model and falls back to 200000. Set to the model's window, e.g. `1000000` on a 1M model. Navigator-only.)
- `contextWarnThreshold` (default: `0.7` — fraction of the window past which the navigator recommends a clean session. Navigator-only.)
- `autoVerify` (default: `false` — when `true`, `forge-verify` runs automatically after a stage completes, no prompt. **In-stage-primary:** the just-completed authoring stage runs it itself, in-session, before the exit block (honoring the verify-before-clear principle). The navigator runs it only as a **catch-up** when verify is still pending (a host that could not dispatch a clean-room subagent, or a stage run before this behavior landed). Either way it runs in a fresh clean-room subagent, so it never needs a `/clear` and costs only a compact digest.)
- `autoVerifyStages` (default: `{}` — per-stage overrides for `autoVerify`, e.g. `{"forge-1-prd": false}`. Effective value = `autoVerifyStages[stage]` if present, else `autoVerify`. Keys are constrained to the five verify-capable stages; a typo is a config error surfaced as `invalidAutoVerifyKeys`. Both the in-stage run and the navigator catch-up read this same effective value.)
- `autoFix` (default: `false` — when `true`, `forge-fix` is chained after an auto-verify that finds issues — by the in-stage run (primary) or the navigator catch-up — but only when auto-verify is on for that stage AND preconditions hold (zero unresolved decisions, clean tree, passing re-verify); otherwise a digest is surfaced and the gate is presented.)
- `loopRunner` (optional object — the loop runner to drive; **defaults to rauf** when absent, with every command templated. See `references/forge-config-schema.json` and `references/ralph-loop-contract.md`.)

## Feature Directory Resolution

Before any file I/O against a feature's artifacts, resolve its directory through the deterministic helper rather than hardcoding `{specsDir}/{feature}/`. This makes flat (`{specsDir}/{feature}/`) and nested (`{specsDir}/{epic}/{feature}/`) layouts both resolve from a bare feature name (REQ-DIR-03), with standalone features behaving exactly as today.

```bash
R="$(bash -c 'for d in "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
resolvedFeatureDir=$(python3 "$R/scripts/epic-manifest.py" \
  resolve "<feature>" --specs-dir "<specsDir>")
```

- **Exit 0:** stdout is the absolute feature directory. Use it everywhere this skill previously wrote `{specsDir}/{feature}/`.
- **Exit 1:** the helper reports a structured finding (`not-found`, `ambiguous` — see `00-core-definitions.md §4`). Because this `resolve` call passes **no `--json`** (the subcommand has no such flag), the finding is a plain `not-found:`/`ambiguous:` line on **stderr** with empty stdout — there is no findings JSON to parse. **STOP** and surface that stderr line verbatim. (The `{valid, findings[]}`-on-stdout envelope is the `--json` shape used by `render-status`/`validate`, not by `resolve`.)
- **Exit 2:** a usage / safety error (`unsafe-name`, a path-containment escape, missing file). The message is a plain `Error: …` line on **stderr** with empty stdout — there is no findings JSON to parse. **STOP** and surface that stderr line verbatim.

In both failure cases, do not fall back to a guessed path.

**On `not-found`, check other branches before stopping.** With `branchPerFeature`, the feature's directory (and its `.pipeline-state.json`) may exist only on its topic branch — invisible from the default branch of a fresh clone. Before concluding the pipeline does not exist, run the read-only cross-branch discovery:

```bash
R="$(bash -c 'for d in "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-session.py" discover-feature "<feature>" --specs-dir "<specsDir>" --json
```

- **Candidates found** (`candidates` and/or `remoteCandidates` non-empty): summarize them as text (branch, recorded stage, whether the state's own `branch` field matches), then use `AskUserQuestion`: **Switch to `{branch}` (recommended)** — run the candidate's `switchCommand` · **Fetch + switch** — for a `needsFetch` remote candidate, run its `fetchCommand` then `switchCommand` (note its contents were matched by name only, not inspected) · **Treat `{feature}` as new on this branch** · **Stop**. A checkout is a mutation inside an otherwise read-only flow: perform it ONLY on the user's explicit accept AND with a clean working tree (`git status --porcelain` prints nothing) — never auto-switch, never with uncommitted changes. After a successful switch, re-run this Feature Directory Resolution block from the top.
- **Nothing found** (both lists empty): the pipeline genuinely does not exist anywhere discoverable — STOP and surface the original `not-found` stderr line verbatim (or, where the caller offers to start a new pipeline, offer that).

**Anti-fabrication guard.** Never describe pipeline state that resolution or discovery did not return: if both come back empty, the pipeline does not exist — say exactly that, and never reconstruct stages, backlogs, or history from conversational memory.

**Resolution algorithm (summary; full spec in `02-manifest-helper-cli.md §4`):**
1. Reject the name if unsafe (path separator, `..`, absolute, or failing `SAFE_NAME_RE`) — before any filesystem access.
2. If `{specsDir}/{name}/.pipeline-state.json` exists → return that flat path.
3. Else if exactly one `{specsDir}/*/{name}/.pipeline-state.json` exists → return that nested path.
4. More than one match anywhere → `ambiguous` error listing all matching paths (uniqueness violation, REQ-DIR-04).
5. Zero matches → `not-found` error.

A directory counts as a **feature** only if it directly contains a `.pipeline-state.json` (the *feature-shaped-dir bound*, `00-core-definitions.md §6`). Non-feature subtrees (`.verification/`, `tests/`, fixture dirs, and the epic root itself — which holds `epic-manifest.json` but no `.pipeline-state.json`) are therefore never matched as features.

**Compatibility:** for a standalone feature the resolver returns its flat path with no epic logic engaged (REQ-COMPAT-01/02) — standalone-feature behavior is unchanged. A pre-existing latent name collision is reported for manual cleanup by the navigator / forge-verify epic mode (CHECK-E08), not by aborting an unrelated command whose name resolves to exactly one dir (tech-spec §3.4).

## Specs Directory Hygiene

Whenever a stage creates the specs tree for the first time (the first PRD or epic written under `{specsDir}/`), ensure a spec-directory agent-instruction file exists at the **specsDir root**. This tells coding agents in the project that the specs here are pre-implementation artifacts — not live contracts to enforce against the code. It is **idempotent: never overwrite an existing file** (the project may have edited it).

Run this after creating the feature/epic directory, before the stage's git commit:

```bash
R="$(bash -c 'for d in "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
mkdir -p "<specsDir>"
[ -f "<specsDir>/AGENTS.md" ] || cp "$R/references/templates/specs-hygiene/AGENTS.md" "<specsDir>/AGENTS.md"
```

If the host is Claude (the `AskUserQuestion` tool is available), also ensure the Claude-framed variant:

```bash
[ -f "<specsDir>/CLAUDE.md" ] || cp "$R/references/templates/specs-hygiene/CLAUDE.md" "<specsDir>/CLAUDE.md"
```

Stage any file this writes (`{specsDir}/AGENTS.md`, and `{specsDir}/CLAUDE.md` when written) as part of the stage's existing git commit.

## Epic Context Injection

After resolving the feature directory, check the feature's `.pipeline-state.json` for an `epic` back-pointer. **If absent, skip this block entirely** (standalone feature — REQ-COMPAT-01; standalone-feature behavior is unchanged). **If present**, load exactly the following context, and nothing transitive (REQ-CTX-01):

1. **`{specsDir}/{epic}/EPIC.md`** — the epic narrative, including the per-feature Contracts sections.
2. **This feature's `charter`** — read from `{specsDir}/{epic}/epic-manifest.json` (the `features[]` entry whose `name` matches), together with its `exposes` and `consumes` arrays. These are the feature's **contract obligations** (REQ-CTX-02): what it must expose to dependents and what it consumes from dependencies.
3. **Direct completed dependencies only** — for each `name` in this feature's `dependsOn`, resolve that sibling's directory and, **only if it is complete-for-orchestration** (`00-core-definitions.md §7`), load its `PRD.md` and `tech-spec.md`.

**Do NOT load** transitive (indirect) dependencies' specs. Indirect contracts reach this feature only through the *direct* deps' Contracts sections in `EPIC.md`. This bounds context size and keeps the injected set deterministic (REQ-CTX-01).

To obtain the manifest contracts and the live completion status of each dependency in one deterministic call, run `render-status` and read the per-feature `status` and the `consumes`/`exposes` arrays rather than re-deriving them:

```bash
R="$(bash -c 'for d in "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/epic-manifest.py" \
  render-status "<epic>" --specs-dir "<specsDir>" --json
```

If `render-status` fails, proceed with **only** EPIC.md + charter (a corrupt manifest must not silently inject stale dep specs — REQ-ROBUST-02): on **exit 1**, parse the `{findings[]}` JSON from stdout and surface each; on **exit 2**, surface the plain `Error:` line from stderr verbatim. Do not attempt to parse findings JSON on an exit-2 failure (stdout is empty).

## Pipeline State Protocol

Write pipeline state conforming to `references/pipeline-state-schema.json`. Always update `updatedAt` when modifying pipeline state.

### Staleness Detection (Read-Time)

When loading upstream artifacts as prerequisites, check `basedOnVersions` in the pipeline state for this stage. If any upstream stage's current version is newer than the version recorded in `basedOnVersions`, warn the user before proceeding:

> "This stage was built against {upstream} v{old}, but {upstream} is now at v{new}. The current artifacts may be outdated. Consider re-running this stage, or use --force to proceed with potentially stale inputs."

Frame the choice with its cost: re-running re-derives this stage from the current upstream (safest, but discards any hand-edits to this stage's artifacts); proceeding stale is faster but risks baking outdated assumptions into everything downstream. Recommend re-running unless the user knows the upstream change doesn't affect this stage.

## Branch Setup

Invoke this block at the **very start** of a pipeline entry point — `forge-1-prd` (standalone feature) and `forge-0-epic` (epic) — **before** any directory resolution or interview, so the rest of the run lands on the intended branch. `{label}` is the feature name (forge-1-prd) or epic name (forge-0-epic); `{scope}` is `feature` or `epic` correspondingly.

**Gate.** Run this block only when the project uses git (a `.git` directory resolves) **and** `branchPerFeature` is true. It is **independent of `gitCommitAfterStage`** — branch isolation matters whether or not forge auto-commits. If `branchPerFeature` is false, skip silently.

**Epic-member inheritance.** In `forge-1-prd`, if the feature has an `epic` back-pointer (an `epic` field resolves via Epic Context Injection, or the directory is nested under an epic), the epic already established the branch in `forge-0-epic`. Skip the prompt — inherit the current branch.

**Detection, then a branch-aware prompt:**

1. Read the current branch: `git rev-parse --abbrev-ref HEAD`.
2. Determine the default branch: `git symbolic-ref --quiet refs/remotes/origin/HEAD` (strip to the last path segment); if that fails, fall back to `main`, else `master` — whichever the repo has.
3. **If the current branch is NOT the default branch** (the user is already on a topic/`{branchPrefix}*` branch) → record it (see below) and proceed silently. Do not prompt.
4. **If the current branch IS the default branch** → use `AskUserQuestion` with a **strong recommendation** (still optional):

   > "You're on `{defaultBranch}`. Strongly recommended: create `{branchPrefix}{label}` so this {scope}'s work stays isolated and reviewable as one branch. Create it?"
   > Options: **Create `{branchPrefix}{label}` (recommended)** · **Stay on `{defaultBranch}`**

   - **Create** → `git switch -c {branchPrefix}{label}` (or `git checkout -b` if `switch` is unavailable). If the branch already exists, `git switch {branchPrefix}{label}`.
   - **Stay** → proceed on the default branch; note that subsequent commits (and any `forge-5-loop` run) will land directly on `{defaultBranch}`.

**Record the branch.** After this block resolves, write the resulting branch name to the feature's `.pipeline-state.json` top-level `branch` field (create/update it when the state file is first written for this stage). Downstream stages and `forge-5-loop` read it to detect drift back onto the default branch.

## Branch Reconciliation

The recorded `branch` is a **self-healing hint, not gospel.** A hosted environment (Claude.ai remote, cloud agents) can impose an arbitrary session branch (e.g. `claude/<slug>`) that Branch Setup silently records; the user may then move the work to the intended topic branch, leaving the recorded field stale. Every branch-aware mechanism (the `forge-5-loop` guard, `discover-feature`) keys off that field, so a stale value actively misleads — the loop would offer to switch you *back* to the imposed branch. Invoke this block from `forge-5-loop`'s pre-flight (and any stage that acts on the recorded branch) to reconcile deterministically. Skip if not a git repo or `branchPerFeature` is false.

```bash
R="$(bash -c 'for d in "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-session.py" reconcile-branch --feature "{feature}" --specs-dir "{specsDir}" --json
```

Act on the emitted `action` (source of truth is where the state actually resolves, not the recorded field):
- **`adopt-current`** — you are on a non-default topic branch where the state resolves, and the recorded `branch` differs (a stale/imposed value). Write `newBranch` into the state `branch` field with a **visible one-line note** ("recorded branch was `{stateBranch}`; work is on `{currentBranch}` — updating to match") — never silently, and **never push the user back** to the recorded branch (offer that only as a plain alternative).
- **`warn-drift`** — you are on the **default** branch and the state records a topic branch. Via `AskUserQuestion`, strongly recommend creating/switching to `{branchPrefix}{feature}` (then record it), still allowing **proceed on the default branch**. Never hard-stop.
- **`none`** / **`not-resolved`** — nothing to do; proceed.

If the helper is unavailable (non-Claude host without the resolver), fall back to the manual check: current branch differs from recorded → adopt the current branch unless it is the default, in which case recommend creating `{branchPrefix}{feature}`.

## Git Commit Protocol

When `gitCommitAfterStage` is true, follow this exact order to avoid state inconsistency.

**Why two commits.** The stage's `.pipeline-state.json` is itself part of the staged commit, but the stage's `commitHash` cannot be known until *after* that commit is made. Recording it *inside* the same commit is a chicken-and-egg with no single-commit solution. Resolve it with a **deterministic two-commit sequence**, and **never** with `git commit --amend`: amending rewrites HEAD, so a hash captured before the amend points at an orphaned commit that is not in the final history (the exact defect this protocol exists to prevent).

1. **Stage specific files only:** `git add {specsDir}/{feature}/` — never use `git add -A` or `git add .`
2. **Commit 1 — artifacts + state, hash not yet known:** In `.pipeline-state.json`, set this stage's `status: "complete"` and `commitHash: null`, then `git commit -m "{commitPrefix}({feature}): <action>"`. This is the stage's **artifact commit**; its hash is the provenance hash callers rely on.
3. **If Commit 1 succeeds — Commit 2 records the hash:** Capture the hash of Commit 1 (`git rev-parse HEAD`). Write it into this stage's `commitHash` in `.pipeline-state.json`, then commit only that one-line change: `git add {specsDir}/{feature}/.pipeline-state.json && git commit -m "{commitPrefix}({feature}): record stage commit hash"`. The stored `commitHash` now points at the artifact commit (Commit 1) — never at Commit 2, and never at an orphaned amend. The working tree is clean afterward, so the next stage's dirty-tree check passes.
4. **If Commit 1 fails:** do NOT update pipeline state to complete. Report the error to the user and leave state as `in-progress` so the stage can be resumed. Common failure causes:
   - **Pre-commit hook failure:** Report the hook output. Never use `--no-verify` to bypass. Help the user fix the underlying issue.
   - **Merge conflicts:** Report conflicting files. Suggest resolution steps appropriate to the conflict.
   - **Nothing to commit:** If all artifacts were already committed, this is fine — mark the stage `complete`, leave `commitHash` at its existing value (or `null` if there was never an artifact commit), and skip Commit 2. There is no new artifact commit to record.
5. **Never** use `git add -A`, `--amend`, `--no-verify`, or `--force` flags

## Stage-Entry Guard

Invoke this block at the **start of an authoring stage** (`forge-1-prd`..`forge-4-backlog`), **after** Feature Directory Resolution and **before** any interview or (re-)authoring. It prevents a re-entered stage — an injected skill body or a re-invoked `Skill` — from blindly re-running the interview over an in-progress or already-complete draft. `{stage}` is the invoking skill's id (e.g. `forge-2-tech`).

**Read, then classify** this stage's entry in `{resolvedFeatureDir}/.pipeline-state.json` (`stages.{stage}.status`):

1. **Fresh** — no state file yet, or `stages.{stage}` is absent/`pending`. First run of this stage. Proceed to the **Entry Stamp** below, then author normally. No prompt.

2. **Interrupted** (`status: "in-progress"`) — a previous run of THIS stage was interrupted before it committed (the exit commit is what flips it to `complete`, so `in-progress` on entry always means a crash/abandon). Do **not** silently re-author. Instead:
   - **Inventory on-disk artifacts:** list the files this stage produces that already exist in `{resolvedFeatureDir}/` (e.g. `PRD.md`; `tech-spec.md`; the `##-*.md` suite + `TRACEABILITY.md`; `backlog.json`), and cross-check against the `stages.{stage}.artifacts` array (written incrementally during the previous run).
   - **Gate via `AskUserQuestion`** (Decision Support protocol): present the inventory as text, then ask "This {stage} run was interrupted — {N} artifact(s) from the previous run are on disk: {list}. Resume the in-progress draft, or start a new version from scratch?" Options: **Resume (recommended)** — continue from the first artifact not yet written/complete, reusing the existing files; do **not** re-stamp or bump the version. · **Start a new version** — treat it as a fresh authoring pass (proceed to the Entry Stamp; the version increments at exit).
   - Skip artifact regeneration for files that already exist and are complete (non-empty, properly structured); continue from the next unwritten artifact.

3. **Re-authoring** (`status: "complete"` or `"stale"`) — a finished draft exists. Warn via `AskUserQuestion` before overwriting: "A completed {stage} artifact already exists for '{feature}' (v{n}{, marked stale}). Continuing will create a new version. Proceed?" On confirm, proceed to the Entry Stamp and author a new version (the version increments at exit, per that stage's Update-Pipeline-State step).

**Entry Stamp** (fresh, restart, and re-author paths — NOT the resume path). Before authoring, write to `{resolvedFeatureDir}/.pipeline-state.json` and update `updatedAt`:
- `stages.{stage}.status` → `"in-progress"`
- `stages.{stage}.startedAt` → current ISO-8601 UTC timestamp
- top-level `currentStage` → `"{stage}"` (where the pipeline IS, per O1)

This write is **left uncommitted**: it is staged and committed as part of this stage's existing exit commit (Git Commit Protocol), so no extra commit is needed at entry. If the run is interrupted after the stamp but before the exit commit, the marker survives on disk (uncommitted) and the next entry classifies as **Interrupted** — which is exactly the intent.

**Force Mode.** When `--force` is passed, skip the interactive gate: do not prompt for resume-vs-restart or the re-author warning. Treat entry as a fresh restart — apply the Entry Stamp and author. (`--force` already skips prerequisite checks; here it likewise bypasses the self-stage gate. Existing on-disk artifacts are still loaded per Force Mode.)

**Incremental artifact tracking:** When a stage writes multiple files (e.g. forge-3-specs writing a suite of spec documents), update the `stages.{stage}.artifacts` array in `.pipeline-state.json` after writing each file — not just at stage completion. This is what makes the Interrupted inventory above precise about which files were successfully written.

## Force Mode

If the user passes `--force` as an argument, skip prerequisite validation with a warning:

> Force mode: skipping prerequisite checks. Pipeline state tracking may be incomplete — this stage may build on prior stages that were never completed or verified, so its output can be silently wrong. Recommend running `/feature-forge:forge {feature}` after to verify status.

Continue with the stage even if prior stages are not marked complete. Still read any existing artifacts (PRD.md, tech-spec.md, etc.) if they exist on disk — force mode skips the pipeline state check, not the artifact loading.
