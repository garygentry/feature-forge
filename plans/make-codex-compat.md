# Dual Claude Code + Codex Package Support

## Summary

Convert `feature-forge` from a Claude-only plugin repo into a shared core package with host-specific adapters. Keep `skills/`, `references/`, and most `scripts/` as the single source of truth. Add Codex metadata and small compatibility shims where Claude Code and Codex differ: plugin manifests, marketplaces, hooks, subagents, command wording, and host-specific path variables.

## Key Changes

- Add Codex plugin metadata without removing Claude metadata:
  - Keep `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`.
  - Add `.codex-plugin/plugin.json` with the same name/version/description and `skills: "./skills/"`.
  - Add a Codex marketplace entry, preferably `.agents/plugins/marketplace.json`, pointing at the repo/plugin path using Codex's `source: { source: "local", path: ... }` shape.

- Make skill instructions host-neutral:
  - Replace Claude-only command examples like `/feature-forge:forge-1-prd` with dual examples: Claude slash form and Codex skill form (`$forge-1-prd` or `/skills` selection).
  - Replace `AskUserQuestion` wording with a neutral "use the host's user-input mechanism"; in Codex this maps to `request_user_input`, while Claude keeps `AskUserQuestion`.
  - Replace `.claude/references/stack-decisions.md` with a neutral project override path policy. Recommended minimum-duplication default: support both `.claude/references/stack-decisions.md` and `.agents/references/stack-decisions.md`, with `.agents/...` preferred for new cross-agent projects and `.claude/...` retained for compatibility.
  - Update README, stack references, and skill text that currently assumes Claude Code only.

- Fix host-specific script and hook assumptions:
  - `skills/forge-init/SKILL.md` currently runs `bash ${CLAUDE_PLUGIN_ROOT}/scripts/forge-init.sh`; replace with host-neutral guidance that resolves the plugin root from the active skill/plugin location.
  - `hooks/hooks.json` currently uses `${CLAUDE_PLUGIN_ROOT}`. Keep it for Claude, but add a Codex-compatible hook definition that uses a stable path strategy supported by Codex plugin-bundled hooks. Validate whether Codex injects a plugin-root variable before implementation; if not, prefer a small wrapper script or manifest-supported relative hook path.
  - Keep `scripts/session-check.sh` and `scripts/forge-init.sh` shared.

- Add Codex custom-agent adapters:
  - Keep Claude agents in `agents/*.md`.
  - Add Codex agents under `.codex/agents/*.toml` or package-equivalent plugin support if available.
  - Map `forge-researcher` to a Codex custom agent with `sandbox_mode = "read-only"` and `model_reasoning_effort = "medium"`.
  - Map `forge-verifier` to a Codex custom agent with read-only behavior, higher reasoning, and instructions copied from the shared verifier agent content.
  - Update skills to say subagents are optional and host-dependent. Codex should only spawn subagents when the user explicitly permits/delegates, per current Codex behavior.

- Update validation and deployment:
  - Expand `scripts/validate.sh` into a dual-platform validator:
    - Validate Claude manifest and marketplace.
    - Validate Codex `.codex-plugin/plugin.json`.
    - Validate Codex marketplace JSON if present.
    - Validate shared skill frontmatter.
    - Validate Claude agent frontmatter and Codex agent TOML schema separately.
    - Check hook command portability for each host.
  - Update README install docs with separate sections:
    - Claude Code: existing `/plugin marketplace add garygentry/feature-forge` and `/plugin install ...`.
    - Codex CLI/app: `codex plugin marketplace add garygentry/feature-forge` or local `.agents/plugins/marketplace.json`, then install via `/plugins`.
    - Local development: Claude symlink under `~/.claude/skills/feature-forge`; Codex local marketplace or `~/.codex/plugins/feature-forge` with `~/.agents/plugins/marketplace.json`.
  - Update `CHANGELOG.md` and `COMPATIBILITY.md` for a new minor release because packaging and invocation compatibility expand but core pipeline behavior remains compatible.

## Test Plan

- Run existing `bash scripts/validate.sh` after it is expanded.
- In Claude Code:
  - Register/install from marketplace.
  - Confirm skills, agents, and `SessionStart` hook load.
  - Run `forge-init` in a scratch repo and confirm `forge.config.json` is created.
- In Codex:
  - Add the local marketplace and restart Codex.
  - Confirm plugin appears in `/plugins`, skills appear in `/skills`, and installed skills can be invoked.
  - Confirm Codex hook review shows the bundled session hook and that trusting it allows `session-check.sh` to run.
  - Spawn or explicitly request the Codex researcher/verifier agents in a scratch repo and confirm read-only behavior.
- Cross-host smoke test:
  - Run forge stages through at least `forge-2-tech` with the same scratch project.
  - Confirm shared artifacts (`forge.config.json`, specs, pipeline state) remain host-neutral and usable from both Claude Code and Codex.

## Assumptions

- The shared core should remain repo-root based: `skills/`, `references/`, `scripts/`, and config schemas should not be duplicated per host.
- Claude Code support must remain fully backward compatible for current users.
- Codex support should use official Codex plugin packaging: `.codex-plugin/plugin.json`, Codex marketplace metadata, Codex skills, Codex hooks, and Codex custom agents.
- Before implementation, re-check the live Codex manual for exact plugin-bundled hook path semantics and whether plugin manifests can bundle custom agents directly; if not, ship Codex agents through documented `.codex/agents/*.toml` setup instructions.
