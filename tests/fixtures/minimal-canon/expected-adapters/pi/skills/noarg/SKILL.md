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
- **Non-interactive (`-p`/`--mode json`):** `AskUserQuestion` is stripped from the tool list, so its absence alone cannot tell you the rung — read that from the Interaction Capability Ladder's `interaction-mode` record. A call attempted anyway fails with `Error: UI not available (running in non-interactive mode)` — never read that as a decline. Take the Interaction Capability Ladder's declared conservative default, state it in your output, and use `no-default: abort — <question> requires a human answer` for an interview question with no sane default (`references/shared-conventions.md`).
- **Skill dispatch:** Pi uses `/skill:<name>` commands. If you cannot invoke a skill directly, print the exact `/skill:<name> ...` command for the user to run.
- **Subagents:** this bundle declares its custom agents (`forge-researcher`, `forge-spec-writer`, `forge-verifier`) as package agents. If a `subagent` tool is registered, dispatch one with `{ agent: "forge-verifier", task: "..." }`, or fan several out concurrently with `{ tasks: [{ agent: "forge-spec-writer", task: "..." }, ...] }`. If no `subagent` tool is available, run that step inline yourself.
- **Background / monitoring (forge-5-loop):** Pi has no built-in background bash, persistent monitor, or push-notification, so do **not** run the loop runner in the foreground and do **not** try to arm one. This bundle registers a **forge-loop-supervisor** extension that IS the "background-execution mechanism" and "monitoring mechanism" Steps 3b–3f refer to. Concretely:
  - **Launch (Step 3b):** call **`forge_loop_launch`** with the backlog dir (and `review` / `agent` / `iterations` as resolved from config). It starts the loop **detached** — it runs in rauf's server and outlives this session — and returns immediately; you do not build or redirect a command yourself.
  - **Supervise (Steps 3d–3f):** the extension then watches the runner's `events.ndjson` for you. It reports each completed item as one quiet line and **wakes this session automatically** on needs-human, blocked, stuck, review-failed, error, and completion — so do **not** arm a monitor, set a continuous tail, send a notification, poll, or foreground-sleep, and do not treat any manual stop as the terminal signal. When completion wakes you, go straight to Step 4 and read the authoritative counts with the status/list command. Use **`forge_loop_status`** to check progress on demand.
  - **Stop / session end:** **`forge_loop_stop`** deliberately stops the runner; use it only when the user wants the loop to actually stop. Ending the Pi session does **not** stop the loop (it is detached), and the next session **reattaches automatically** without re-reporting what you already saw.
