---
name: pattern-deviation-judgment
description: How to judge a fix pass's deliberate deviation from a prescribed fix — reproduce its stated justification first, then attack the deviation on its own terms
metadata:
  type: reference
---

When a fix pass records a deliberate deviation from a finding's prescribed fix, judge it
on the merits, not on conformance — and in this order.

**Why:** a prescribed fix is sometimes actively worse than what shipped (a prescribed
merged clause that does not catch its own stated mutation). A verifier that graded
deviations as non-compliance would force a regression. Conversely, blanket trust misses
that the *unchanged* half of the same guard still carries the defect.

**How to apply:**

1. **Reproduce the stated justification with your own instrument.** If a justification
   does not reproduce, the deviation is a finding regardless of how reasonable it sounds.
2. **Ask what the finding's argument actually rested on**, not what its code snippet said.
   If the finding argued from an internal inconsistency and the applied half closed exactly
   that inconsistency, the withheld half was cost without benefit.
3. **Then attack the deviation on its own terms.** For an added guard fragment, the
   discriminating questions are: does it occur only inside the scoped region? does the
   *natural* misreading delete it? is the attack that beats it one that beats every
   fragment equally (then it does not distinguish)? A contrived double-negation defeats
   any substring guard and proves nothing.
4. Report a per-deviation **verdict** section, separate from findings, so a reader can see
   the deviation was adjudicated rather than silently accepted.

**A deviation that NARROWS the finding's cited scope is often the finding being
corrected.** When a finding quotes a WARNING naming decorators "in §3.2, §6.2 and §7.2"
and the fix names only two of the three, grep the document: the finding may have inherited
a mis-citation from the very WARNING it was retiring. **Never grade a narrowing against the
finding's section list; grade it against the artifact.** Count the construct the list
claims to enumerate.
