---
name: pattern-sibling-docstring-sweep
description: When a fix mirrors one guard into N places, exactly one of the N docstrings gets updated — grep for the superseded rationale, not the new one
metadata:
  type: reference
---

When a fix pass mirrors a rule into several implementations, it reliably amends **one**
docstring and leaves the siblings stating the superseded rationale. The function the
finding was filed against is not always the one whose docstring got fixed — a mirrored
guard can land in three functions with only the *unnamed* one amended, leaving the target
function still asserting the opposite in two separate sentences.

**Why:** the amended docstring *names* the old rationale in order to disclaim it, which
makes it the perfect grep needle for finding the unamended ones. Behaviour is correct
either way, so no test can see the drift; a reader of the stale docstring draws exactly the
false inference the fix existed to kill.

**How to apply:** after any "mirror the guard into N places" fix —

1. Grep for the *superseded* rationale (the phrase the one amended docstring disclaims),
   not for the new rule. The updated site will not match; the stale ones will.
2. Read the N docstrings **side by side** and check none states a rule another contradicts.
3. The same shape hits number words after an arity change — see
   [[pattern-stale-counts-after-split]] — and false specifics in "measured twice"-style
   claims, where the conclusion is true but the named instrument is wrong on most of the
   surfaces it claims to cover. Verify *which* fragment matched *per surface*, not just that
   the aggregate claim holds.
