---
name: pattern-vacuous-self-reading-tests
description: Tests that read their own source file are near-always vacuous unless they assert absence or scope the read; verify by a PROPERTY-PRESERVING mutation and check WHICH line goes red
metadata:
  type: reference
---

A drift-guard test that does `source = read(Path(__file__).resolve())` and then asserts a
**positive** substring is almost always vacuous: the searched literal sits on the assert
line itself, so the whole-file read satisfies it unconditionally.

**Why:** the trap catches even the *fix* for a prior vacuity finding, which often
reproduces the identical defect while its own inline comment claims "this reads for a
DIFFERENT string than the one it writes". The fix pass validates it with a mutation that
changes a second property at the same time — replacing a derived roster with a *shrunken*
hardcoded list goes red, but at a pre-existing floor assertion (`len(...) >= MIN`), not at
the assertion under test. Seeing "red" is taken as proof; a roster-**preserving** hardcode
leaves the test fully green.

**How to apply:**

- Grep every changed test for `read(Path(__file__)` / `inspect.getsource`. For each,
  locate the searched literal's occurrences in the file. Two occurrences (guarded site +
  assert line) = vacuous.
- Never accept "the mutation went red". Demand the **line number** of the failing
  assertion, and design the mutation to change exactly one property.
- Acceptable forms: assert **absence** (write the banned tokens without the syntax that
  makes them live), or scope the read away from the guarding test's own body
  (`inspect.getsource(<the guarded function>)`). The best form for "this expression is
  still derived" is an `ast` parse, which the assertion's own text cannot satisfy.

See [[pattern-postfix-reverify]] and [[pattern-mechanical-rewrite-damage]].
