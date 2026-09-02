---
# GENERATED — DO NOT EDIT. Source: skills/noarg/SKILL.md. Regenerate: python3 scripts/build-adapters.py
name: noarg
description: A skill with no argument hint and no own references.
---

# No Arg

A forge-init analog: no metadata.argument-hint, so the Claude mirror must NOT
invent a top-level argument-hint, and no own references/ dir is copied.

---

## Host execution notes (Codex)

This skill was authored Claude-first; the body above refers to "the host's question mechanism", "the host's subagent mechanism", and "the host's background-execution mechanism". On Codex:

- **User input:** Codex has no structured question tool. Which rung you are on is **not** observable from inside the session — a `codex exec` run looks exactly like an interactive one — so read it from the Interaction Capability Ladder's `interaction-mode` record instead of judging it. Interactive session — ask the question directly and wait for the reply; never assume an answer. Non-interactive — don't wait: take the Interaction Capability Ladder's declared conservative default, state it in your output, and use `no-default: abort — <question> requires a human answer` for an interview question with no sane default (`references/shared-conventions.md`).
- **Subagents:** spawn a Codex subagent using the named custom agent under `.codex/agents/<name>.toml`. Codex spawns a subagent only when explicitly asked; if the custom agent is unavailable, run that step inline yourself.
- **Background / monitoring:** run long-lived runner commands in your shell session and report progress as it arrives — there is no Claude-style background or monitoring tool to arm.
