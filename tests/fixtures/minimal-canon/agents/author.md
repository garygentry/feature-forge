---
name: author
description: Authors one artifact and returns it.
tools: Read, Glob, Grep, Bash, Write
model: opus
maxTurns: 30
---

You are an authoring sub-agent. `Write` appears ONLY here among the fixture
sub-agents, so the Pi emitter's writer branch (acceptanceRole: writer, mapped
write/edit tools, and no read-only completion-guard exemption) has coverage that
the two read-only agents cannot provide.
