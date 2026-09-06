---
name: noarg
description: A skill with no argument hint and no own references.
allowed-tools:
  - Read
  - Grep
disallowed-tools:
  - Write
disable-model-invocation: true
---

# No Arg

A forge-init analog: no metadata.argument-hint, so the Claude mirror must NOT
invent a top-level argument-hint, and no own references/ dir is copied. It also
carries the Claude-only skill-governance keys (allowed-tools, disallowed-tools,
disable-model-invocation): Claude reconstructs them top-level; every other target
drop-records them (#272).
