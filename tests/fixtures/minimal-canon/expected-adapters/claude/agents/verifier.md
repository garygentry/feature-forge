---
# GENERATED — DO NOT EDIT. Source: agents/verifier.md. Regenerate: python3 scripts/build-adapters.py
name: verifier
description: Verifies artifacts for completeness and consistency.
tools: Read, Glob, Grep, Bash
model: opus
maxTurns: 40
memory: project
skills:
- forge-verify
---

You are a verification sub-agent. The `memory` and `skills` keys appear ONLY
here among the fixture sub-agents, so the per-file drop-with-record test can
prove per-file enumeration rather than a hard-coded list.
