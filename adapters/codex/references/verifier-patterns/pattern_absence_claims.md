---
name: pattern-absence-claims
description: "\"X does not exist\" is the highest-cost finding shape a verifier can get wrong — it induces a fix that DELETES correct content; prove absence with identifier-aware search, never a prose-word grep"
metadata:
  type: reference
---

Before filing any finding whose claim is **"the named thing does not exist"**, prove the
absence with a search that matches the way the thing would actually be spelled in code —
not the way the spec spells it in prose.

**Why:** a false-positive absence claim is uniquely expensive. Every other bad finding
adds noise; this one induces a fix that *removes* correct content, and the loss is
invisible afterwards. The classic miss: a spec quotes a test "the 'exactly the five'
test", the verifier greps the standalone word `five`, finds nothing, and declares the
test absent — but the word lived inside a snake_case identifier
(`test_accepts_exactly_the_five_outcomes`), which a word-boundary grep never sees. The
fix pass believes the finding and deletes the correct sentence.

**How to apply:**

- Grep the token **unanchored and case-folded**, then again split on `_`/`-`/camel
  boundaries: `grep -rin 'five' tests/` before concluding, not `grep -n '\bfive\b'`.
  Prose words routinely live inside identifiers.
- Prefer searching for the **structure** over the phrase: for "a test that enumerates the
  outcomes", grep the symbol the test must consume (the enum/constant name) and read every
  hit. That usually finds it in one call.
- A spec phrase in quotes ("exactly the five") is usually a *paraphrase of an identifier*,
  not a literal string in the file. Convert it to snake_case and search that too.
- If you still cannot find it, say **"I could not locate it; confirm before deleting"**
  and file at `improvement`, never a confident `inconsistency`/`error` whose fix is a
  deletion. Absence findings should carry the search you ran, so the fixer can re-run it.

**Re-verify corollary:** when a prior round's finding said "does not exist" and the fix
removed prose, re-run the absence search yourself first. That is the single highest-yield
check on a re-verify — see [[pattern-postfix-reverify]].
