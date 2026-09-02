---
# GENERATED — DO NOT EDIT. Source: skills/with-refs/SKILL.md. Regenerate: python3 scripts/build-adapters.py
name: with-refs
description: 'Build the thing: do it precisely.'
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

## Host execution notes (Codex)

This skill was authored Claude-first; the body above refers to "the host's question mechanism", "the host's subagent mechanism", and "the host's background-execution mechanism". On Codex:

- **User input:** Codex has no structured question tool. Interactive session — ask the question directly and wait for the reply; never assume an answer. Under `codex exec` (non-interactive) — don't wait: take the Interaction Capability Ladder's declared conservative default, state it in your output, and use `no-default: abort — <question> requires a human answer` for an interview question with no sane default (`references/shared-conventions.md`).
- **Subagents:** spawn a Codex subagent using the named custom agent under `.codex/agents/<name>.toml`. Codex spawns a subagent only when explicitly asked; if the custom agent is unavailable, run that step inline yourself.
- **Background / monitoring:** run long-lived runner commands in your shell session and report progress as it arrives — there is no Claude-style background or monitoring tool to arm.
