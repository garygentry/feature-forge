---
# GENERATED — DO NOT EDIT. Source: skills/forge-init/SKILL.md. Regenerate: python3 scripts/build-adapters.py
name: forge-init
description: Initialize feature-forge configuration in the current project. Use when user runs /feature-forge:forge-init or asks to set up forge for the first time. Creates forge.config.json with defaults. Do NOT trigger for general project initialization or setup tasks outside the forge pipeline.
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
- `stack`: `null` (detected during `/feature-forge:forge-2-tech`)
- `typeCheckCommand`: `null` (set during `/feature-forge:forge-2-tech`)
- `testCommand`: `null` (set during `/feature-forge:forge-2-tech`)
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

If the host's question mechanism is available, ask exactly one question:

> **Enable auto-verify?** Verification runs in a clean-room subagent in-stage after each
> authoring stage completes — in the same session, before the exit block, so any fix
> decision keeps its context. It never needs a session clear and only returns a compact digest.
> **Recommended: on.** (Change later by editing `autoVerify` in `forge.config.json`.)

Options: **Enable (recommended)** / **Leave off**.

- On **Enable**: patch `"autoVerify": false` → `"autoVerify": true` in the generated
  `forge.config.json` in place, preserving formatting and every other key.
- On **Leave off**: leave the config as written (`autoVerify: false`).

Follow the Interaction Capability Ladder (`references/shared-conventions.md`) for rung 2/3: at
rung 2 (no structured tool, host can still prompt and wait — e.g. Codex), ask the same question
in plain prose and wait for the reply; same choice, different rendering. At rung 3 (genuinely
non-interactive), this question's declared default is the no-write / no-proceed option — skip
the prompt, leave `autoVerify: false`, state the rung-3 default taken, and print the one-line
note `Set "autoVerify": true in forge.config.json to verify automatically after each stage.`

## Preflight the install

Once the config exists, check the tooling this project's pipeline will lean on:

```bash
R="$(bash -c 'for d in "${FEATURE_FORGE_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-session.py" doctor --json \
  --check plugin-root --check root-version-skew --check gh-available
```

Follow `references/preflight-and-self-heal.md` with that result: all `ok`/`na` → say nothing and
move on. Otherwise cluster and report. `gh-available` matters here because the tooling-feedback
step below tells agents to file issues with `gh issue create`; when `gh` is missing or
unauthenticated, say so once — its remedies are `global-install`/`network`, so they are
**advise-only** and nothing is executed. `plugin-root` and `root-version-skew` are reported the
same way; a stale or unresolvable install is worth knowing about before the first stage runs.

## Root hygiene — tooling feedback

Offer the project-root **Tooling feedback** section, per `references/shared-conventions.md`
§ Root Hygiene (Tooling Feedback) — that block owns the protocol text, the copy commands, and the
never-overwrite rule; do not restate them here. It is a `local-write`: one consolidated question
covering the variants the host is offered (`AGENTS.md` always; `CLAUDE.md` only on Claude, from the
build-substituted `--host` — never from tool availability), then run the copy. This is what makes
the `specs/` hygiene files' "see the project-root `AGENTS.md`" pointer resolve.

After initialization, start the pipeline with `/feature-forge:forge-1-prd <feature-name>`.

---

## Host execution notes

This skill was authored Claude-first; the body above refers to "the host's question mechanism", "the host's subagent mechanism", and "the host's background-execution mechanism". Use your runtime's equivalent for each — and if your runtime has no such tool:

- **User input:** ask the question directly and wait for the answer when your runtime can prompt and wait; never assume one. When your runtime is genuinely non-interactive, take the Interaction Capability Ladder's declared conservative default, state it in your output, and use `no-default: abort — <question> requires a human answer` for an interview question with no sane default (`references/shared-conventions.md`).
- **Subagents:** if your host cannot dispatch the named custom agent, run that step inline yourself.
- **Background / monitoring:** run long-lived commands in the foreground (or your host's background facility) and report progress as it arrives.
