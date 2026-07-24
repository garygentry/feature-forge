---
# GENERATED — DO NOT EDIT. Source: skills/forge-init/SKILL.md. Regenerate: python3 scripts/build-adapters.py
name: forge-init
description: Initialize feature-forge configuration in the current project. Use when user runs /skill:forge-init or asks to set up forge for the first time. Creates forge.config.json with defaults. Do NOT trigger for general project initialization or setup tasks outside the forge pipeline.
---

# Initialize Feature Forge

Run the initialization script to create `forge.config.json` with default settings:

```bash
R="$(bash -c 'for d in "${FEATURE_FORGE_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
bash "$R/scripts/forge-init.sh"
```

After initialization, the config file will contain defaults for:
- `specsDir`: `./specs`
- `docsDir`: `./docs/architecture`
- `backlogDir`: `null` (backlog lives alongside specs)
- `gitCommitAfterStage`: `true`
- `commitPrefix`: `forge`
- `stack`: `null` (detected during `/skill:forge-2-tech`)
- `typeCheckCommand`: `null` (set during `/skill:forge-2-tech`)
- `testCommand`: `null` (set during `/skill:forge-2-tech`)
- `smokeCommand`: `null` (optional end-to-end smoke that boots the wired app and drives one request; set it to enable impl-verify's runnability check `CHECK-I21` — distinct from `testCommand`)
- `autoInvokeNextStage`: `true` (the navigator auto-starts the next stage after you confirm; set `false` to only print the command)
- `contextWindowTokens`: `null` (the navigator infers the context window; set to your model's window, e.g. `1000000` for a 1M-context model, for accurate context-usage advice)
- `contextWarnThreshold`: `0.7` (fraction of the window past which the navigator suggests a clean session)
- `autoVerify`: `false` (set `true` to run `forge-verify` automatically after each authoring stage completes — in-stage, in the same session, before the exit block; it costs an extra clean-room verify per stage, so it trades a little time/tokens for catching errors early)
- `autoVerifyStages`: `{}` (per-stage overrides for `autoVerify`)
- `autoFix`: `false` (set `true` to chain `forge-fix` after an auto-verify finds issues)

If `forge.config.json` already exists, the script will not overwrite it.

## Offer auto-verify

The template writes `autoVerify: false`. After the config is created (and only when the script
actually created it — skip this if it reported the file already exists), offer to turn
auto-verify on, then write the choice back into `forge.config.json`.

If the `AskUserQuestion` tool is available, ask exactly one question:

> **Enable auto-verify?** Verification runs in a clean-room subagent in-stage after each
> authoring stage completes — in the same session, before the exit block, so any fix
> decision keeps its context. It never needs a `/new` and only returns a compact digest.
> **Recommended: on.** (Change later by editing `autoVerify` in `forge.config.json`.)

Options: **Enable (recommended)** / **Leave off**.

- On **Enable**: patch `"autoVerify": false` → `"autoVerify": true` in the generated
  `forge.config.json` in place, preserving formatting and every other key.
- On **Leave off**: leave the config as written (`autoVerify: false`).

If the host lacks a structured question tool but can still prompt the user (e.g. Codex asks in
plain text), use that — ask the one question directly and wait for the reply; it is the same
choice, just rendered differently. Only when the host has **no** way to ask at all (a fully
non-interactive / headless run) do you skip the prompt: leave `autoVerify: false` and print the
one-line note `Set "autoVerify": true in forge.config.json to verify automatically after each stage.`

After initialization, start the pipeline with `/skill:forge-1-prd <feature-name>`.

---

## Host execution notes (Pi)

This Pi bundle preserves Claude's `AskUserQuestion` references because it ships a Pi compatibility extension registering an `AskUserQuestion` tool. On Pi:

- **User input:** use `AskUserQuestion` for genuine user decisions. It supports multiple questions, option descriptions, recommended ordering, multi-select, previews, and free-form Other/custom answers.
- **Skill dispatch:** Pi uses `/skill:<name>` commands. If you cannot invoke a skill directly, print the exact `/skill:<name> ...` command for the user to run.
- **Subagents:** this bundle declares its custom agents (`forge-researcher`, `forge-spec-writer`, `forge-verifier`) as package agents. If a `subagent` tool is registered, dispatch one with `{ agent: "forge-verifier", task: "..." }`, or fan several out concurrently with `{ tasks: [{ agent: "forge-spec-writer", task: "..." }, ...] }`. If no `subagent` tool is available, run that step inline yourself.
- **Background / monitoring:** run long-lived commands in the foreground and report progress as it arrives.
