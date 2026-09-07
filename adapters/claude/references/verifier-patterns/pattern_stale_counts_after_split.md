---
name: pattern-stale-counts-after-split
description: Splitting a construct N ways leaves the old number words ("two", "three", "both") scattered through banners, docstrings and prose — grep the number words after any arity change
metadata:
  type: reference
---

When a construct is split — one function into three, two checks into five, "both callers"
into "all three" — the code is updated and the **number words describing it are not**. They
survive in module banners, docstrings, comment headers, error messages, and prose that
narrates the old shape. Nothing fails: the count is not executable, so no test observes it,
and the reader is told the wrong arity by a file that otherwise looks authoritative.

**Why it survives review:** a diff shows the new Nth item being *added* and gives no signal
about the sentences elsewhere that quantified the old set. The reviewer checks the new
member is correct — which it is. The stale count sits in a file the diff never touches.

**How to apply.** After any arity change:

1. **Grep the number words, not the identifiers:**
   `\b(one|two|three|four|five|both|either|neither)\b` across the changed construct's own
   file *and* every file that cites it. `both` and `neither` are the highest-yield needles
   — they are only correct at exactly two and break silently at three.
2. **Include the prose surfaces a code grep misses:** module docstrings, comment
   annotations, assertion messages, reference markdown, skill bodies, and changelog entries
   that described the old shape.
3. **Re-read the sentence, do not pattern-match it.** "The two callers" may have become
   "the two callers and the initializer", which is grammatical, cites three things, and
   still says two.
4. A count in an **error message** is worse than one in a docstring: it is read at the
   moment someone is already confused, and it is quoted into issues.

**Sibling shapes:** [[pattern-sibling-docstring-sweep]] (mirroring a rule into N places
amends exactly one docstring) and [[pattern-test-count-units]] (a "N tests" claim means
pytest-collected, not `def` count). All three are the same failure: a number that
describes code, written in prose, with nothing to keep the two in step.
