---
name: pattern-test-count-units
description: A spec's "N tests" claim means pytest-COLLECTED tests, not def count — always --collect-only before calling it wrong
metadata:
  type: reference
---

When an artifact claims a test-file size ("43 tests, 651 lines", "67 mutation
controls"), resolve the unit with `pytest <file> --collect-only -q` before filing an
accuracy finding. Parameterization makes `grep -c "def test_"` wildly lower than the
collected count — a single `@pytest.mark.parametrize` function can collect dozens.

**Why:** grep count and collected count are different units, and a spec that is exactly
right in the collected unit looks wrong under a naive `def` grep. Filing that is a pure
false positive, and it burns a fix round on churn the artifact never needed.

**How to apply:** If a spec states a baseline in one unit and a *target* in the other
("43 tests" → "at most 5 tests"), that unit ambiguity is itself the finding — file it as
an `improvement` asking for the counting unit to be named, not as a factual `error`.
See [[pattern-spec-literals-are-claims]].
