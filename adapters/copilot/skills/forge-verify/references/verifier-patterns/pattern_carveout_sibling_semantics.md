---
name: pattern-carveout-sibling-semantics
description: When a fix carves ONE enumerated form out of a blanket claim for a semantic property, every sibling form sharing that property must be re-checked
metadata:
  type: reference
---

When a fix pass carves ONE member out of an enumerated "these forms all do X" list because
that member actually does something else, EVERY other member of the list is a suspect for
the same defect.

**Why:** a blanket claim ("each of these binding forms was probed and confirmed to leave
the roster displaced") gets sharpened by carving out the one member that unbinds instead —
but sibling forms sharing the same semantics stay wrongly inside the set. A concrete
Python example: a set of "these all displace the module-scope roster" left in both
`except … as NAME` (Python 3 / PEP 3110 implicitly `del`s the exception target at end of
block → NameError on a later read — `del`'s exact twin) and a comprehension target (Python
3 comprehensions have their own scope; the loop variable does NOT leak to module scope → the
roster is left INTACT, never displaced). The sharpened blanket was still false for two of
the listed forms.

**How to apply:** the moment a fix carves out member M for property P, run the SAME probe
over every remaining member. For roster/binding decoys specifically: `except…as` unbinds
like `del`; list/set/dict-comprehension targets don't leak in py3 (probe with a subsequent
module-scope READ, not just a namespace `.get`, which masks unbound-vs-None); `import…as`
binds a module/non-iterable unless a `from … import x as` names the right type. Also
cross-check the fix's acceptance matrix: if it re-probed only K of N listed forms, the
un-probed forms are exactly where the residue hides.

When a carve-out is applied as an explicit **partition** of the forms by their semantics
(displaced decoys / scope-local no-leak / unbinds-or-non-iterable), that partition is the
confirmed-correct shape — if a future round touches it, preserve the partition rather than
re-collapsing to a blanket. Related: [[pattern-sibling-docstring-sweep]],
[[pattern-postfix-reverify]].
