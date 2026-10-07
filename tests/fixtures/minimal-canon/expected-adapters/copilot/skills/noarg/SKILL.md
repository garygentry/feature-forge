---
# GENERATED — DO NOT EDIT. Source: skills/noarg/SKILL.md. Regenerate: python3 scripts/build-adapters.py
name: noarg
description: A skill with no argument hint and no own references.
---

# No Arg

A forge-init analog: no metadata.argument-hint, so the Claude mirror must NOT
invent a top-level argument-hint, and no own references/ dir is copied. It also
carries the Claude-only skill-governance keys (allowed-tools, disallowed-tools,
disable-model-invocation): Claude reconstructs them top-level; every other target
drop-records them (#272).

---

## Host execution notes (GitHub Copilot)

This bundle uses distribution-neutral invocation notation because Copilot assigns different slash-command names to plugin and direct installations:

- **Invocation notation:** `invoke-skill: <name> [arguments]` in the body and references is an instruction, not a literal command to paste. Preserve the named skill and its arguments.
- **Plugin install:** invoke `/feature-forge:<name> [arguments]`.
- **Direct project/personal install:** invoke `/<name> [arguments]`.
- **No universal slash name:** use the form matching the skill's discovery source. If the source is uncertain, use Copilot's skill-invocation mechanism or ask the user instead of guessing.
- **User input:** Copilot has no structured question tool in this bundle — ask the question directly and wait for the answer when the session can prompt and wait; never assume one. Read whether it can from the Interaction Capability Ladder's `interaction-mode` record rather than judging it. When the session is genuinely non-interactive, take the Interaction Capability Ladder's declared conservative default, state it in your output, and use `no-default: abort — <question> requires a human answer` for an interview question with no sane default (`references/shared-conventions.md`).
- **Subagents:** dispatch the named custom agent with Copilot's subagent mechanism. If it is unavailable, run that step inline only when the skill permits inline execution.
- **Background / monitoring (forge-5-loop):** launch the loop detached and supervise it with the `rauf loop wait` loop exactly as the forge-5-loop skill's runner contract (Steps 3b/3d) says for this host. Never run the loop in the foreground, and don't end your turn while it runs unless Copilot wakes you when a background command finishes. Other long-lived commands: run them in the foreground (or Copilot's background facility) and report progress as it arrives.
- **Bundle root:** the `$R` bootstrap in each shell block resolves `FEATURE_FORGE_ROOT` first, then the nearest project `.github/feature-forge`, then the plugin install (`~/.copilot/installed-plugins/*/feature-forge`), then `~/.copilot/feature-forge`. Run the blocks as written; set `FEATURE_FORGE_ROOT` only to pin a specific bundle.
