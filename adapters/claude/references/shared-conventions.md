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

**Recommendations:** Only recommend a specific option when codebase evidence, established conventions, or strong technical rationale clearly favors it. If options are equally valid, present them neutrally — let the user decide without bias.

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
- `loopRunner` (optional object — the loop runner to drive; **defaults to rauf** when absent, with every command templated. See `references/forge-config-schema.json` and `references/ralph-loop-contract.md`.)

## Feature Directory Resolution

Before any file I/O against a feature's artifacts, resolve its directory through the deterministic helper rather than hardcoding `{specsDir}/{feature}/`. This makes flat (`{specsDir}/{feature}/`) and nested (`{specsDir}/{epic}/{feature}/`) layouts both resolve from a bare feature name (REQ-DIR-03), with standalone features behaving exactly as today.

```bash
R="$(for d in "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/*/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done)"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
resolvedFeatureDir=$(python3 "$R/scripts/epic-manifest.py" \
  resolve "<feature>" --specs-dir "<specsDir>")
```

- **Exit 0:** stdout is the absolute feature directory. Use it everywhere this skill previously wrote `{specsDir}/{feature}/`.
- **Exit 1:** the helper reports a structured finding (`not-found`, `ambiguous` — see `00-core-definitions.md §4`). Because this `resolve` call passes **no `--json`** (the subcommand has no such flag), the finding is a plain `not-found:`/`ambiguous:` line on **stderr** with empty stdout — there is no findings JSON to parse. **STOP** and surface that stderr line verbatim. (The `{valid, findings[]}`-on-stdout envelope is the `--json` shape used by `render-status`/`validate`, not by `resolve`.)
- **Exit 2:** a usage / safety error (`unsafe-name`, a path-containment escape, missing file). The message is a plain `Error: …` line on **stderr** with empty stdout — there is no findings JSON to parse. **STOP** and surface that stderr line verbatim.

In both failure cases, do not fall back to a guessed path.

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
R="$(for d in "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/*/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done)"
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
R="$(for d in "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/*/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done)"
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

## Git Commit Protocol

When `gitCommitAfterStage` is true, follow this exact order to avoid state inconsistency:

1. **Stage specific files only:** `git add {specsDir}/{feature}/` — never use `git add -A` or `git add .`
2. **Attempt commit:** `git commit -m "{commitPrefix}({feature}): <action>"`
3. **If commit succeeds:** capture the commit hash, then update pipeline state with `status: "complete"` and the `commitHash`
4. **If commit fails:** do NOT update pipeline state to complete. Report the error to the user and leave state as `in-progress` so the stage can be resumed. Common failure causes:
   - **Pre-commit hook failure:** Report the hook output. Never use `--no-verify` to bypass. Help the user fix the underlying issue.
   - **Merge conflicts:** Report conflicting files. Suggest resolution steps appropriate to the conflict.
   - **Nothing to commit:** If all artifacts were already committed, this is fine — proceed with state update but note the absence of a new commit hash.
5. **Never** use `git add -A`, `--no-verify`, or `--force` flags

## Crash Recovery

When a skill detects that `currentStage` matches itself and the stage status is `in-progress`, a previous run was interrupted. Follow this recovery protocol:

1. **Inventory existing artifacts:** List all files on disk in `{specsDir}/{feature}/` that this stage would produce
2. **Compare against state:** Check the `artifacts` array in the pipeline state for this stage — it tracks files written incrementally during the previous run
3. **Present options to user:** "This stage was interrupted. Found {N} artifacts from the previous run: {list}. Would you like to resume from where it left off, or restart the stage from scratch?"
4. **If resume:** Skip artifact generation for files that already exist and appear complete (non-empty, properly structured). Continue from the next unwritten artifact.
5. **If restart:** Proceed normally. The version number will increment.

**Incremental artifact tracking:** When a stage writes multiple files (e.g., forge-3-specs writing a suite of spec documents), update the `artifacts` array in `.pipeline-state.json` after writing each file — not just at stage completion. This ensures crash recovery knows exactly which files were successfully written.

## Force Mode

If the user passes `--force` as an argument, skip prerequisite validation with a warning:

> Force mode: skipping prerequisite checks. Pipeline state tracking may be incomplete. Recommend running `/feature-forge:forge {feature}` after to verify status.

Continue with the stage even if prior stages are not marked complete. Still read any existing artifacts (PRD.md, tech-spec.md, etc.) if they exist on disk — force mode skips the pipeline state check, not the artifact loading.
