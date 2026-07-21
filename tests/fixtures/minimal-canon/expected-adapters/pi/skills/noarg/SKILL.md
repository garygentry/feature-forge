---
# GENERATED — DO NOT EDIT. Source: skills/noarg/SKILL.md. Regenerate: python3 scripts/build-adapters.py
name: noarg
description: A skill with no argument hint and no own references.
---

# No Arg

A forge-init analog: no metadata.argument-hint, so the Claude mirror must NOT
invent a top-level argument-hint, and no own references/ dir is copied.

---

## Host execution notes (Pi)

This Pi bundle preserves Claude's `AskUserQuestion` references because it ships a Pi compatibility extension registering an `AskUserQuestion` tool. On Pi:

- **User input:** use `AskUserQuestion` for genuine user decisions. It supports multiple questions, option descriptions, recommended ordering, multi-select, previews, and free-form Other/custom answers.
- **Skill dispatch:** Pi uses `/skill:<name>` commands. If you cannot invoke a skill directly, print the exact `/skill:<name> ...` command for the user to run.
- **Subagents:** Pi has no Claude-style `Agent` tool; run the work inline or ask the user to start a fresh Pi session with the named role.
- **Background / monitoring:** run long-lived commands in the foreground and report progress as it arrives.
