---
name: with-refs
description: "Build the thing: do it precisely."
metadata:
  argument-hint: "[target]"
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
