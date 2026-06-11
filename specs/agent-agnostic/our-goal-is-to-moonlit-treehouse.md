# Dual-Agent (Claude Code + Codex) Support for feature-forge + rauf

## Context

`feature-forge` is today a **Claude-only plugin**: its skills, subagents, hooks, and
manifests target Claude Code's plugin spec. The goal is for the plugin's skills and
subagents to be **fully compliant and optimized for Claude Code AND OpenAI Codex**,
with a structure that generalizes to any future agent — and **without losing any
fidelity on Claude** for features other agents lack.

A Codex-authored plan exists at `plans/make-codex-compat.md`. It is *substantially
correct on packaging* but has three material problems this plan corrects:

1. It treats `${CLAUDE_PLUGIN_ROOT}` in hooks as an unknown risk requiring a wrapper.
   **Codex actually sets `CLAUDE_PLUGIN_ROOT`/`CLAUDE_PLUGIN_DATA` "for compatibility
   with existing plugin hooks"** (verified against Codex's official hooks docs), so the
   existing `hooks/hooks.json` needs little-to-no change.
2. It maps `AskUserQuestion → request_user_input` as if equivalent. Codex's
   `request_user_input` is **limited (reportedly Plan-Mode-only)** and Codex lacks
   AskUserQuestion's multi-select and agent "project memory". Naively neutralizing skill
   text would **degrade Claude**. We must preserve Claude fidelity and let other hosts
   degrade gracefully via an explicit capability map — not by rewriting skill bodies.
3. **It explicitly punts on `rauf`.** This is the real blocker: `rauf` (the stage-5 loop
   runner) hardcodes spawning the Claude CLI (`spawnClaude`), reads
   `~/.config/claude-code/credentials.json`, and calls Anthropic's OAuth usage API. So a
   Codex-driven pipeline would still run **Claude** under the hood for the actual coding
   loop. The user has chosen the **full Part B provider refactor** in rauf to fix this.

**Verified facts that shape this plan** (Codex official docs + cross-agent research):

- Codex skills use the **same `SKILL.md` format** (`name` + `description` frontmatter,
  optional `scripts/`, `references/`, `assets/`). A Codex `.codex-plugin/plugin.json`
  with `"skills": "./skills/"` can point at feature-forge's **existing `skills/` dir** —
  no need to move or fork skill bodies.
- Codex hooks use the **same `hooks/hooks.json`** and the **same lifecycle event names**
  (`SessionStart`, etc.), and inject `PLUGIN_ROOT` + the compat `CLAUDE_PLUGIN_ROOT`.
- Codex marketplace = `.agents/plugins/marketplace.json` (repo-scoped) or
  `~/.agents/plugins/marketplace.json` (personal); installable via
  `codex plugin marketplace add owner/repo`.
- Codex subagents = `.codex/agents/*.toml` (`name`, `description`,
  `developer_instructions`, `sandbox_mode`, `model_reasoning_effort`). **No** persistent
  "project memory" field — that Claude feature degrades on Codex.
- `AGENTS.md` is the cross-agent instruction standard; Claude does not read it natively.
- rauf's `SPEC-BACKLOG-TOOL-CONTRACT.md` already documents the Part B `LLMProvider`
  architecture (claude-cli / generic-cli / codex / gemini); it is **specced, not built**.

## Architecture: shared core + thin per-host adapters

The governing principle: **one source of truth for everything shareable; per-host
adapters are purely *additive*, never subtractive.** Adding a new agent = adding an
adapter dir + a column in the capability map, with **zero edits to skill bodies**. This
is what keeps Claude at full fidelity while admitting Codex.

```
feature-forge/
  skills/                      # SHARED core (Claude + Codex both read this dir)
  references/                  # SHARED
  scripts/                     # SHARED (host-neutral bash/python)
  schemas/  config/            # SHARED
  references/host-adaptation.md  # NEW: capability -> per-host mechanism map (the seam)

  .claude-plugin/              # Claude adapter (unchanged: plugin.json, marketplace.json)
  agents/*.md                  # Claude subagents (unchanged, incl. memory: project)
  hooks/hooks.json             # Shared in practice (CLAUDE_PLUGIN_ROOT works on both)

  .codex-plugin/plugin.json    # NEW: Codex manifest -> skills:"./skills/", hooks, agents
  .agents/plugins/marketplace.json  # NEW: Codex marketplace entry
  .codex/agents/*.toml         # NEW: Codex subagent adapters
```

**Why shared `skills/` (not `.agents/skills/`):** feature-forge is already a Claude
plugin that auto-discovers `skills/`; Codex's manifest can target the same path. Moving
to `.agents/skills/` would be churn for zero benefit and would fork the source of truth.

**The capability seam (`references/host-adaptation.md`):** a single doc mapping each
divergent capability to each host's mechanism. Skills keep their current Claude-rich
wording; this doc tells *any* host how to realize it. Initial rows:

| Capability | Claude Code | Codex | Fallback (any agent) |
|---|---|---|---|
| Structured user input | `AskUserQuestion` (multi-select) | `request_user_input` (plan mode) | numbered conversational prompt |
| Subagent delegation | Agent tool, `subagent_type=...` | `.codex/agents/*.toml` subagents (opt-in) | inline execution (already the documented fallback) |
| Plugin-root path | `${CLAUDE_PLUGIN_ROOT}` | `${CLAUDE_PLUGIN_ROOT}` (compat) / `${PLUGIN_ROOT}` | resolve from skill dir |
| Persistent agent memory | `memory: project` | (none) | stateless; re-derive each run |
| Skill invocation | `/feature-forge:forge-1-prd` | `$forge-1-prd` or `/skills` | — |

`shared-conventions.md` and `process-overview.md` get **one** pointer to this map instead
of per-call rewrites — so the ~40 `AskUserQuestion` references in skills stay **verbatim**
(Claude unchanged) and are reinterpreted per host through the map.

## Work breakdown — feature-forge

1. **Codex packaging (additive).**
   - Add `.codex-plugin/plugin.json` (same name/version/description; `"skills":"./skills/"`,
     `"hooks":"./hooks/hooks.json"`, agents pointer, `interface` block for install surface).
   - Add `.agents/plugins/marketplace.json` with the required Codex entry fields
     (`name`, `source` as `{source:"local"/"github", ...}`, `policy.installation`,
     `policy.authentication`, `category`).

2. **Hooks — minimal change.** Keep `hooks/hooks.json` using `${CLAUDE_PLUGIN_ROOT}`
   (works on both). **Verify on Codex** that `session-check.sh` runs after trusting the
   bundled hook; only add a `${PLUGIN_ROOT}` fallback if the live test shows the compat
   var is hook-only and not present.

3. **Plugin-root in skill *bodies*.** `skills/forge-init/SKILL.md` and
   `skills/forge-verify/SKILL.md` invoke `bash ${CLAUDE_PLUGIN_ROOT}/scripts/...`. Unlike
   hooks, these run in the agent's Bash shell. **Verify on Codex whether the var is
   exported there.** If not, change these to a host-neutral resolution (locate the script
   relative to the skill's own directory) — the only skill-body edits required.

4. **Capability map + pointers.**
   - Add `references/host-adaptation.md` (the table above, expanded).
   - In `references/shared-conventions.md` and `references/process-overview.md`, replace
     the Claude-only framing with a short "host adaptation" pointer to the map. Keep all
     existing Claude tool names as the Claude column — **no fidelity loss**.
   - Make subagent delegation explicitly optional + host-dependent in `forge-2-tech` and
     `forge-verify` (the inline fallback already exists; just generalize the prose).

5. **Codex subagent adapters.** Add `.codex/agents/forge-researcher.toml` and
   `forge-verifier.toml` mapping the shared behavior (`sandbox_mode="read-only"`,
   `model_reasoning_effort` ~ medium/high). Source `developer_instructions` from the same
   content as `agents/*.md` to avoid drift (single shared body file referenced by both;
   escalate to a generation step only if drift appears). Document that `memory: project`
   has no Codex equivalent → forge-verify on Codex runs stateless (functional, lower
   cross-run learning).

6. **Consumer-side reference paths.** Update `references/stack-resolution.md` to check
   `.agents/references/stack-decisions.md` first, then `.claude/references/stack-decisions.md`
   (back-compat). This bifurcates *consumer* guidance per host as the user requested.

7. **Provider selection in the loop (ties to rauf below).** `forge-5-loop` should let the
   user pick the loop provider, defaulting to the host it runs on (Claude→`claude-cli`,
   Codex→`codex`). This flows through the existing `loopRunner` command template
   (`references/forge-config-schema.json`) — e.g. a `{provider}` token / `--provider` flag —
   so feature-forge stays runner-agnostic.

8. **Validation + docs.**
   - Expand `scripts/validate.sh`: validate `.codex-plugin/plugin.json`, the Codex
     marketplace JSON, `.codex/agents/*.toml` schema, and hook-command portability — in
     addition to the existing Claude checks.
   - README: split install into Claude (`/plugin marketplace add garygentry/feature-forge`)
     and Codex (`codex plugin marketplace add garygentry/feature-forge`) sections + local-dev
     for both; document the dual-manifest "bifurcated install from one repo" model.
   - Update `CHANGELOG.md` / `COMPATIBILITY.md` (new minor: packaging + invocation expand,
     core pipeline behavior unchanged).

## Work breakdown — rauf (full Part B refactor)

Follow rauf's own `docs/SPEC-BACKLOG-TOOL-CONTRACT.md` Part B. Part A (backlog schema,
`RAUF_DONE/BLOCKED/NEEDS_HUMAN` signal protocol, `.rauf/` layout, CLI verbs) is already
host-neutral and stays as the stable contract feature-forge depends on.

1. **Introduce `LLMProvider` interface + registry.** `execute(prompt, opts) -> {stdout,
   exitCode, signal}`. Refactor `packages/loop/src/runner.ts` (the two `spawnClaude` call
   sites, ~lines 543 & 876) to call `provider.execute(...)`. Generalize log lines
   (`"Claude exited"` → `provider.displayName`) and the `llm_spawned/llm_exited` event
   `provider` field.

2. **Extract the claude-cli provider.** Move `packages/loop/src/claude-process.ts`,
   `readClaudeOAuthToken` (`packages/core/src/config.ts` ~104–172), and the
   Anthropic-OAuth `packages/loop/src/usage-checker.ts` into a `providers/claude-cli/`
   adapter. Anthropic-specific usage checks become claude-cli-only.

3. **Add generic-cli provider.** Configurable `{binary, args, env}`, prompt via stdin,
   final-line signal parsing (reuse `signal-parser.ts`, already agnostic).

4. **Add codex provider.** Spawn Codex non-interactively (verify exact `codex exec`
   invocation + the unattended-approval/sandbox flag analogous to claude's
   `--dangerously-skip-permissions`), capture stdout, parse the same final-line signal.
   No Anthropic usage check (skip or provider-specific).

5. **Provider config + selection.** Add provider selection to rauf config / `.rauf.json`
   and a `--provider` run flag; default `claude-cli` for back-compat. Wire this to the
   `{provider}` token feature-forge renders.

6. **Cosmetic generalization.** Rename `artifacts/variants/backlog-json/CLAUDE_*.{md,tmpl}`
   → `AGENT_*`; generalize Claude/Task-tool wording in `RAUF.md.tmpl` and
   `prompt-builder.ts` (gate Task-tool guidance on provider capability). Generalize the
   `agentDelegation`/"Task tool" note in the backlog schema.

**feature-forge ↔ rauf boundary is unchanged in shape:** the `loopRunner` template
already abstracts the runner; the only new surface is passing the chosen provider through.

## Critical files

- feature-forge: `.codex-plugin/plugin.json` (new), `.agents/plugins/marketplace.json`
  (new), `.codex/agents/*.toml` (new), `references/host-adaptation.md` (new),
  `references/shared-conventions.md`, `references/process-overview.md`,
  `references/stack-resolution.md`, `skills/forge-init/SKILL.md`,
  `skills/forge-verify/SKILL.md`, `skills/forge-5-loop/SKILL.md`,
  `references/forge-config-schema.json`, `scripts/validate.sh`, `README.md`.
- rauf: `packages/loop/src/runner.ts`, `packages/loop/src/claude-process.ts`,
  `packages/core/src/config.ts`, `packages/loop/src/usage-checker.ts`,
  `packages/loop/src/prompt-builder.ts`, new `packages/loop/src/providers/*`,
  `artifacts/variants/backlog-json/*`, `schemas/backlog.schema.json`,
  `docs/SPEC-BACKLOG-TOOL-CONTRACT.md` (mark Part B implemented).

## Open items to confirm during implementation (Codex available)

- Whether `${CLAUDE_PLUGIN_ROOT}` is present in the Codex **skill Bash** environment
  (decides items 2–3 above).
- Exact Codex non-interactive invocation + unattended flag for the rauf codex provider.
- Codex marketplace entry required-field exact shapes (`policy.*`, `source`).
- Whether Codex honors the shared `SessionStart` hook and `session-check.sh` as-is.

## Verification

**feature-forge — Claude (regression):** install from marketplace; confirm skills,
subagents, and `SessionStart` hook load; run `forge-init` then `forge-1-prd` →
`forge-2-tech` in a scratch repo; confirm `AskUserQuestion`, subagent dispatch, and
`memory: project` behavior are **unchanged**.

**feature-forge — Codex (new):** `codex plugin marketplace add garygentry/feature-forge`;
confirm it appears in `/plugins`, skills in `/skills`, `$forge-1-prd` invokes; confirm the
session hook is offered and `session-check.sh` runs when trusted; run the researcher/
verifier Codex agents and confirm read-only behavior; run `forge-init` and confirm
`forge.config.json` is created.

**rauf — providers:** unit/integration tests for `claude-cli` (parity with current),
`generic-cli`, and `codex` providers (mock + one live run each); confirm signal parsing,
timeout/kill, and event emission are provider-agnostic; confirm `--provider claude-cli`
reproduces today's behavior byte-for-byte (back-compat gate).

**Cross-host end-to-end:** from a single scratch project, drive forge stages through at
least `forge-2-tech` on **both** hosts and confirm shared artifacts (`forge.config.json`,
specs, pipeline state, backlog.json) are host-neutral. Then run stage-5 `forge-5-loop`
once with `--provider codex` (driven from Codex) and once with `claude-cli` (driven from
Claude); confirm each runs the loop on the **intended** agent and reaches `RAUF_DONE`.
