---
name: pattern-extend-the-existing
description: "…the existing X is extended" and "X does NOT do Y" are the two tech-spec claim shapes that are wrong often enough to check every time; open the function, not the comment
metadata:
  type: reference
---

Two claim shapes in tech-specs that are wrong often enough to check every time:

1. **"the existing <check/step> is extended (one-line pointer)"** — verify the check
   actually exists *on the side the spec proposes to edit*. A recurring miss: a spec claims
   a skill has "an existing pre-flight dirty-tree check", when what exists is another
   process's own launch refusal, merely *narrated* by the skill. The skill cannot rewrite a
   message another process emits, so the requirement needs a NEW step and real body lines —
   not a pointer. Grep the skill's own step list (`### N. …`) before accepting the claim.

2. **"<existing command> does NOT do Y"** — a negative capability claim used to justify
   building a replacement. Open the implementation. A negative claim ("the subcommand does
   NOT clear the flag", used to justify a whole new subcommand + version floor) is exactly
   the kind nobody re-checks — and the function may already do Y in *both* its branches and
   say so in its header comment.

**Why:** both shapes shrink the apparent cost of a change, so they slip past review — and
both land in the *decision* rationale, not just prose, so they are `error`-severity, not
cosmetic.

**How to apply:** for shape 1, list the skill's actual steps; for shape 2, read the
function body AND the sibling "all items" branch (the single-item branch alone is not the
contract). Cross-check against any "prefer existing surfaces" list in the PRD — an
unevaluated named surface is part of the same finding. Related:
[[pattern-spec-literals-are-claims]].
