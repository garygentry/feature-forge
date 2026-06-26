# Stack Resolution Protocol

How feature-forge resolves stack-specific guidance for a project.

## Resolution Order (highest priority first)

1. **Project-level override** (first existing path wins). These hold the team's explicit technology decisions and take absolute precedence:
   1. `.feature-forge/stack-decisions.md` — the preferred, host-neutral location (it belongs to this tool, not to any one agent).
   2. `.agents/references/stack-decisions.md` — for projects that centralize cross-agent config under `.agents/`.
   3. `.claude/references/stack-decisions.md` — **legacy alias**, still honored for backward compatibility. If only this file exists, use it and suggest copying it to `.feature-forge/stack-decisions.md`.

2. **Detected stack profile**: `references/stacks/{stack}.md` in this plugin, where `{stack}` matches the `stack` field in `forge.config.json`. Provides language-specific conventions for spec writing, verification, and examples.

3. **Generic fallback**: `references/stacks/_generic.md` in this plugin. Language-neutral guidance that works for any stack. Used when no stack is detected or no matching profile exists.

## How Stack Detection Works

Stack detection happens during **forge-2-tech** (the technical specification stage), which is the natural point where technology decisions are made.

1. The agent examines the project's root manifest and build files
2. Identifies the primary language, build tool, package manager, and framework
3. Asks the user to confirm: "I detected this as a {stack} project. Correct?"
4. Persists the stack identity in `forge.config.json` via the `stack`, `typeCheckCommand`, and `testCommand` fields
5. All downstream stages (forge-3-specs, forge-4-backlog, forge-verify, forge-6-docs) read the `stack` field and load the matching profile

## forge.config.json Fields

```json
{
  "stack": "typescript",
  "typeCheckCommand": "bun run typecheck",
  "testCommand": "bun test"
}
```

- `stack` — Identifier matching a profile filename in `references/stacks/` (e.g., "typescript", "python", "go")
- `typeCheckCommand` — Used in acceptance criteria and verification checks. Null if the stack has no type checker.
- `testCommand` — Used in acceptance criteria and verification checks.

## Available Profiles

| Profile | File | Covers |
|---------|------|--------|
| TypeScript | `references/stacks/typescript.md` | Node.js/Bun, npm/pnpm/bun, monorepo patterns, TS-specific spec conventions |
| Python | `references/stacks/python.md` | Python 3.10+, pip/uv/poetry, pytest, type hints, Pydantic/dataclasses |
| Generic | `references/stacks/_generic.md` | Any stack — language-neutral guidance using placeholders |

## When No Stack Is Configured

If `forge.config.json` has no `stack` field and forge-2-tech hasn't run yet (e.g., when using `--force`), skills should:

1. Attempt basic detection from project files (look for manifest files)
2. Use `_generic.md` as fallback
3. Note in the pipeline state that stack detection was skipped
