---
name: pattern-spec-literals-are-claims
description: Every module id, file path, constant and signature written into a spec is a checkable claim about the repo — verify them mechanically, they survive multiple verify rounds otherwise
metadata:
  type: reference
---

Treat every literal a spec writes down as an assertion about the current repository and
check it against the filesystem, not against the spec's own prose.

**Why:** specs quote "exact existing signatures" and author code constants (allow-lists,
fixture inventories, helper additions) inline. These read as authoritative and reviewers
pattern-match them as correct, so a phantom id or a dropped member survives round after
round untouched. The failure is silent: nothing executes a spec's prose.

**How to apply** (cheap, mechanical, do it every round):

- Module/skill ids in a spec constant → list the real directory and diff the sets both
  directions. Missing-from-spec and absent-from-repo are different bugs; report both.
- Quoted "exact current signature" blocks → `grep -n -A12 'def <name>' <file>` for each.
  When these are usually accurate in a repo, a mismatch is high-signal.
- Cited file paths (fixtures, tests, references, data) → loop them through `[ -e "$p" ]`.
  Fast, and it catches placeholder paths a fix pass left behind.
- Cross-document `<file> §N` citations → script it: build a heading index per file, regex
  the citations, report misses. Never eyeball, especially after a section was deleted or
  renumbered.
- Requirement-id tokens in a coverage table → diff the families against the source doc.
  Range citations (`REQ-EXIT-01..07`) and pseudo-rows are where phantom and dropped IDs
  hide.
- Prose claims about existing behavior ("the field is a single string", "the file is 302
  lines") → verify. When they are usually correct, the occasional wrong one gets waved
  through — which is exactly why to check.
- **A spec's *correction* of an upstream figure is itself an unverified claim — re-derive
  it, do not credit it.** A supersession arrives framed as research ("exhaustive search
  found N"), and that framing buys it a pass. Re-derive each superseding number from the
  files; the correct ones cost seconds and a wrong one is blocking.
- **Cited *line ranges* into another file drift as a set, not as a number.** "Amend the
  bullets (lines 43–48)" plus an enumeration of three constructs is two claims; the range
  is usually copied verbatim from the finding that proposed it, so a wrong range
  propagates report → spec → implementer. `grep -n` the first token of each named
  construct and confirm the span contains all of them.
- **Line-count claims: know what the checker counts.** A body-size gate that measures
  lines *after* frontmatter disagrees with a raw `wc -l` by the frontmatter block. When a
  spec's size claim and a passing gate disagree, go read the checker's measurement
  function before believing either.
