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

## Host execution notes (Pi)

This Pi bundle preserves Claude's `AskUserQuestion` references because it ships a Pi compatibility extension registering an `AskUserQuestion` tool. On Pi:

- **User input:** use `AskUserQuestion` for genuine user decisions. It supports multiple questions, option descriptions, recommended ordering, multi-select, previews, and free-form Other/custom answers.
- **Non-interactive (`-p`/`--mode json`):** `AskUserQuestion` is stripped from the tool list, so its absence alone cannot tell you the rung — read that from the Interaction Capability Ladder's `interaction-mode` record. A call attempted anyway fails with `Error: UI not available (running in non-interactive mode)` — never read that as a decline. Take the Interaction Capability Ladder's declared conservative default, state it in your output, and use `no-default: abort — <question> requires a human answer` for an interview question with no sane default (`references/shared-conventions.md`).
- **Skill dispatch:** Pi uses `/skill:<name>` commands. If you cannot invoke a skill directly, print the exact `/skill:<name> ...` command for the user to run. A **forge-invocation-args** compatibility extension wraps the arguments of a `/skill:forge-*` command in a `<feature-forge-invocation>` envelope before Pi expands it, so read the feature name from that envelope's `<arguments>` element (an empty element means none was supplied) rather than from unlabeled trailing text — see `references/shared-conventions.md` § Feature Name Requirement.
- **Subagents:** this bundle declares its custom agents (`forge-researcher`, `forge-spec-writer`, `forge-verifier`) as package agents. If a `subagent` tool is registered, dispatch one with `{ agent: "forge-verifier", task: "..." }`, or fan several out concurrently with `{ tasks: [{ agent: "forge-spec-writer", task: "..." }, ...] }`. If no `subagent` tool is available, run that step inline yourself.
- **Background / monitoring (forge-5-loop):** run the loop through **rauf's Pi package** (`pi install npm:@garygentry/rauf`, rauf >= 0.18.0), whose `rauf-loop-supervisor` extension registers `rauf_loop_launch`, `rauf_loop_status`, `rauf_loop_wait` and `rauf_loop_stop`. Launch with `rauf_loop_launch`; it starts the loop **detached** (it outlives this session), posts a one-line card per completed item, and **wakes this session** on needs-human, blocked, stuck, review failure, loop errors and completion — so end your turn after the launch: do not poll, sleep, tail, run the loop in the foreground or behind `nohup`/`&`, or hand it to a subagent (the extension blocks those calls). Read `rauf_loop_status` before acting on a wake; use `rauf_loop_stop` only to deliberately stop the runner. Full detail: `references/runner-contract.md` Steps 3b/3d. If the `rauf_loop_*` tools are not registered, `forge-session.py doctor` says how to install the package; until then use the `rauf loop wait` recipe there.
