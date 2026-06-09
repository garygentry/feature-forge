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
- `backlogDir` (default: null — backlog lives at `{specsDir}/{feature}/backlog.json`)
- `gitCommitAfterStage` (default: true)
- `commitPrefix` (default: `forge`)
- `loopIterationMultiplier` (default: `1.5`)
- `loopRunner` (optional object — the loop runner to drive; **defaults to rauf** when absent, with every command templated. See `references/forge-config-schema.json` and `references/ralph-loop-contract.md`.)

## Pipeline State Protocol

Write pipeline state conforming to `references/pipeline-state-schema.json`. Always update `updatedAt` when modifying pipeline state.

### Staleness Detection (Read-Time)

When loading upstream artifacts as prerequisites, check `basedOnVersions` in the pipeline state for this stage. If any upstream stage's current version is newer than the version recorded in `basedOnVersions`, warn the user before proceeding:

> "This stage was built against {upstream} v{old}, but {upstream} is now at v{new}. The current artifacts may be outdated. Consider re-running this stage, or use --force to proceed with potentially stale inputs."

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
