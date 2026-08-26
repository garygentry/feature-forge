---
# GENERATED — DO NOT EDIT. Source: skills/with-refs/SKILL.md. Regenerate: python3 scripts/build-adapters.py
name: with-refs
description: 'Build the thing: do it precisely.'
argument-hint: '[target]'
---

# With Refs

A minimal canonical skill that carries an argument-hint and its own references/
subdir. Used to exercise the Claude argument-hint round-trip, description
byte-fidelity, and per-skill self-containment.

It cites its OWN `references/detail.md` (skill-local — already resolves, must NOT
be re-fanned), a bundle-root SHARED `references/shared-conventions.md` (fanned
skill-local by #132), and the dynamic `references/stacks/{stack}.md` profile
(the whole `references/stacks/` tree is fanned skill-local). A citation of a
project-level `references/stack-decisions.md` resolves to neither and is left alone.

---

## Host execution notes (GitHub Copilot)

This bundle uses distribution-neutral invocation notation because Copilot assigns different slash-command names to plugin and direct installations:

- **Invocation notation:** `invoke-skill: <name> [arguments]` in the body and references is an instruction, not a literal command to paste. Preserve the named skill and its arguments.
- **Plugin install:** invoke `/feature-forge:<name> [arguments]`.
- **Direct project/personal install:** invoke `/<name> [arguments]`.
- **No universal slash name:** use the form matching the skill's discovery source. If the source is uncertain, use Copilot's skill-invocation mechanism or ask the user instead of guessing.
- **User input:** Copilot has no structured question tool in this bundle — ask the question directly and wait for the answer before proceeding.
- **Subagents:** dispatch the named custom agent with Copilot's subagent mechanism. If it is unavailable, run that step inline only when the skill permits inline execution.
- **Background / monitoring:** run long-lived commands in the foreground (or Copilot's background facility) and report progress as it arrives.
