---
name: pattern-postfix-reverify
description: Re-verifying an applied fix pass — the defect shapes fixes reliably introduce, plus what to check when a fix REMOVES scope instead of adding it
metadata:
  type: reference
---

When re-verifying a feature whose findings were just fixed, the findings are rarely "the
fix didn't happen" — they are new defects the fix introduced.

**Why:** the fixer works document-by-document from a fix plan and has no cross-document
budget left to re-check the claims its new prose makes. A round that opens with 6 findings
routinely closes with 10, most of them fix-induced.

**Recurring fix-induced shapes:**

1. *Field-comment fixes invent wrong value domains.* A comment describing the right field
   with the wrong **enum values** survives review — cross-check every documented value
   against the source `Literal`, the argparse `choices`, and any JSON example.
2. *New "Public API / Internal Surface" sections drift from their own citations.* They
   abbreviate a flag list and drop a value, or cite a section for a rule that section does
   not state. Re-read every `§N` such a section cites.
3. *A "new design" fix is the highest-yield target* — and the right outcome is often to
   delete it. See [[pattern-proximity-window-guards]].

**When the fix REMOVES scope (a section deleted, a mechanism withdrawn):**

- The excision itself is usually clean and cheap to prove: grep the removed identifiers
  word-boundary, then script-verify every `<file> §N` citation against actual headings.
- The real defect is in the **replacement requirement**. A withdrawn mechanism gets
  replaced by a one-line requirement, wired into the owning docs — then forgotten in the
  testing spec. A traceability check that only asserts an ID appears in *some* file cannot
  catch this. Diff the requirement families in the testing spec's own coverage table
  against the source, and check whether the acceptance criterion is scoped to "every
  requirement in this document's table".

**Self-narrated round history is unverifiable-by-tooling and drifts.** A fix pass that
adds an "implementation warning" summarizing what prior rounds found writes that history
from memory, not from the reports, and the *count* is usually wrong even when the
operative instruction is right. Diff any such claim against the actual locations of every
prior report. Caps at `inconsistency`.

**A "deleted the file" claim verified by `git status` is worthless when the file is
gitignored.** A gitignored artifact leaves the tree clean before and after, so the fixer
believes a deletion that never happened. For any finding whose remedy is a deletion, `ls`
the literal path — never infer it from a clean tree or the absence of a `D ` line.
`git status --porcelain --ignored <dir>` surfaces the class in one call.

**A retraction orphans the prose that announced the thing being retracted.** Whenever a
fix pass *removes* something a prior pass *added*, grep the removed token across `*.md`
and re-read every hit — the announcement almost always outlives the thing. Grep the
literal token, not the finding's phrasing, and grep the specific file directly rather than
trusting one repo-wide `grep -r … | head`, which can silently truncate the hit.

**A fix that widens a §3 decision leaves the §1 overview summary behind.** The overview's
"key decisions" sentence and the file table are written once at authoring time and are
never in the fix plan's file list. After confirming each fix in its subsection, re-read §1
and §2 and diff them against the new body — cheap, and the single most reliable
fix-induced finding in tech mode. Caps at `inconsistency`.

**Check each fixed section against the decision text, not just the finding.** Where fixes
overshoot is *scope beyond the recorded decision* — a fixed section gains a clause nothing
in the data model or tests backs.

**A suggested fix can prescribe a claim its own remedy doesn't earn.** When a suggested
fix pairs *N concrete items* with a *summary claim over M*, count N against M yourself
before marking resolved — a faithfully-applied fix can land a false exhaustiveness
sentence with the verifier's own authority behind it. Treat the summary sentence, not the
missing item, as the finding.

**A clean re-verify is possible and worth naming as the bar.** The fix passes that come
back clean share one tell: they **re-measured** every literal they wrote (line counts,
word counts, pinned tuple lengths reproduce exactly under the checker's own algorithm) and
they **executed** their own claims before editing (reproduced the defective control
against live canon, then re-ran the replacement) instead of copying the finding's number.
When a fix log reads like that, the re-verify's job is to re-run the same executions
independently, not to hunt. Expect single-artifact modes (prd, tech) to run cleaner than
specs/impl, where cross-document budget exhaustion drives the fix-induced defects — spend
those rounds on filesystem-claim re-measurement instead.

Related: [[pattern-absence-claims]], [[pattern-spec-literals-are-claims]],
[[pattern-mechanical-rewrite-damage]].
