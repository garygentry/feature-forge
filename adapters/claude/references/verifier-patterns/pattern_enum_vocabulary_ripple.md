---
name: pattern-enum-vocabulary-ripple
description: A spec adding one value to a shared enum (or one item to a counted set) always under-lists the ripple surfaces; enumerate them from the repo, never from the spec's file list
metadata:
  type: reference
---

When a tech-spec says "one new enum value, the rest derives automatically", treat the
module-structure file list as a *hypothesis* and re-derive the ripple set yourself. A
single enum addition routinely touches far more than the definition site and one test:

- the `Literal`/type declaration **and** any lookup tables keyed on it;
- **contract/reference docs** that carry a table of the enum's domain — routinely omitted
  from spec file lists;
- the owning skill's **body**, which often carries a *duplicate copy* of the domain. Where
  a test derives the domain from canon and asserts each value's literal appears in the
  skill's exit surface, "pointer-only body edits" is provably false for any enum addition;
- **mirrored copies in the tests** (a second dict of the same enum, plus derivations off
  it);
- shipped **docs** (a rendered table of the domain).

Same shape for **counts**, not just enums: a new checklist entry must update *every* count
string that names the total (a dispatch-table count AND a totals-line count are two
literals), plus any test that asserts those literals.

Two surfaces spec file-lists reliably miss:

- **A new helper script a skill invokes at runtime must be registered wherever the adapter
  build enumerates runtime helpers** — otherwise a generated bundle ships a skill calling a
  script that isn't there, and a test that hard-pins the helper count goes red for whoever
  implements it.
- **A new check section in a large mode's checklist needs a home in the parallel fan-out
  dimension groups.** A spec that says "numeric totals only" leaves the new checks owned by
  no dimension, so a fan-out dispatch silently never executes them.

**Why:** specs repeatedly list only the definition site and one test file, leaving the
verification suite red for whoever implements it.

**How to apply:** in tech mode, for every "new value / new check / new probe", grep the
*old* value across the source, reference, test, eval, and doc trees (excluding generated
mirrors) and diff the hit list against the spec's module-structure section. Every unlisted
hit is a `gap`. Where a test asserts **exact list equality** of a set (e.g. the probes a
dispatcher fans out to), that is another pinned surface the addition must update.
