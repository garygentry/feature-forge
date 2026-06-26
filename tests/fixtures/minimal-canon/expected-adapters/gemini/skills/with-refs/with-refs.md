---
# GENERATED — DO NOT EDIT. Source: skills/with-refs/SKILL.md. Regenerate: python3 scripts/build-adapters.py
name: with-refs
description: 'Build the thing: do it precisely.'
---

# With Refs

A minimal canonical skill that carries an argument-hint and its own references/
subdir. Used to exercise the Claude argument-hint round-trip, description
byte-fidelity, and per-skill self-containment.

---

## Host execution notes

This skill was authored Claude-first; the body above refers to "the host's question mechanism", "the host's subagent mechanism", and "the host's background-execution mechanism". Use your runtime's equivalent for each — and if your runtime has no such tool:

- **User input:** ask the question directly and wait for the answer before proceeding. Do not skip a required question or assume an answer.
- **Subagents:** if your host cannot dispatch the named custom agent, run that step inline yourself.
- **Background / monitoring:** run long-lived commands in the foreground (or your host's background facility) and report progress as it arrives.
