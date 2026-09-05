---
# GENERATED — DO NOT EDIT. Source: skills/forge-init/SKILL.md. Regenerate: python3 scripts/build-adapters.py
name: forge-init
description: Initialize feature-forge configuration in the current project. Use when user runs /feature-forge:forge-init or asks to set up forge for the first time. Creates forge.config.json with defaults. Do NOT trigger for general project initialization or setup tasks outside the forge pipeline.
---

# Initialize Feature Forge

Run the initialization script to create `forge.config.json` with default settings:

```bash
R="$(bash -c 'for d in "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
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

If the `AskUserQuestion` is available, ask exactly one question:

> **Enable auto-verify?** Verification runs in a clean-room subagent in-stage after each
> authoring stage completes — in the same session, before the exit block, so any fix
> decision keeps its context. It never needs a `/clear` and only returns a compact digest.
> **Recommended: on.** (Change later by editing `autoVerify` in `forge.config.json`.)

Options: **Enable (recommended)** / **Leave off**.

- On **Enable**: patch `"autoVerify": false` → `"autoVerify": true` in the generated
  `forge.config.json` in place, preserving formatting and every other key.
- On **Leave off**: leave the config as written (`autoVerify: false`).

This is the run's **first question**, so determine your rung before asking it, per the
Interaction Capability Ladder (`references/shared-conventions.md`) — **read** the rung from
`doctor`'s `interaction-mode` record as that section directs; never judge it from your own tool
surface, which cannot see whether anyone is there to answer:

```bash
R="$(bash -c 'for d in "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-session.py" doctor --json --check interaction-mode
```

At rung 1 or 2, ask (structured tool, or the same choice in plain prose — then wait for the
reply). At rung 3 this question's declared default is the no-write / no-proceed option — skip the
prompt, leave `autoVerify: false`, state the rung-3 default taken, and print the one-line note
`Set "autoVerify": true in forge.config.json to verify automatically after each stage.` — then
**continue with the steps below**; declining this edit never ends the skill. The same rung governs
every remaining step: never emit a question a rung-3 run cannot answer.

## Preflight the install

Once the config exists, check the tooling this project's pipeline will lean on:

```bash
R="$(bash -c 'for d in "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-session.py" doctor --json \
  --check root-version-skew --check gh-available
```

Follow `references/preflight-and-self-heal.md` with that result: all `ok`/`na` → say nothing and
move on. Otherwise cluster and report. **Neither check is a stop for `forge-init`** — report and
continue; a `warn` here never aborts initialization (the procedure returns statuses; the caller
owns its own gate). `gh-available` matters because the tooling-feedback step below tells agents
to file issues with `gh issue create`; when `gh` is missing or unauthenticated, say so once — its
remedies are `global-install`/`network`, so they are **advise-only** and nothing is executed. It
is **one informational line, never a prompt**: `gh` is optional (every stage degrades to manual
steps without it), and this check cannot return `na`, so a machine without `gh` must not be
interrogated about it on every init.
`root-version-skew` is reported the same way: a second install shadowing this one is worth
knowing about before the first stage runs.

(`plugin-root` is deliberately **not** in that list. The prelude above already exits 1 when the
resolver fails, so by the time `doctor` runs the check can only be `ok` — narrowing to checks
that cannot fire would be theatre.)

## Root hygiene — tooling feedback

Offer the project-root **Tooling feedback** section, per `references/shared-conventions.md`
§ Root Hygiene (Tooling Feedback) — that block owns the protocol text, the copy commands, the
three-case analysis, and the never-overwrite rule; do not restate them here. In short: decide
which variants are **missing** first, ask once as a `local-write` only for those, and stay silent
about a file that already carries the section. `AGENTS.md` always; `CLAUDE.md` only on Claude,
read from the bundle's own `agent` field — never from tool availability. **At rung 3 this step
writes nothing and says so** (that block's declared default). This is what makes the `specs/`
hygiene files' "see the project-root `AGENTS.md`" pointer resolve.

After initialization, start the pipeline with `/feature-forge:forge-1-prd <feature-name>`.
