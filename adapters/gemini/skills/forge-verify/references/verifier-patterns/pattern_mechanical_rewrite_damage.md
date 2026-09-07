---
name: pattern-mechanical-rewrite-damage
description: When a fix pass reports "N mechanical edits", re-derive the count with a wider regex and scan the touched text tokens for column-0 punctuation and collapsed whitespace — the strip script's own pattern is never the audit
metadata:
  type: reference
---

A fix pass that reports a bulk mechanical edit ("192 parentheticals removed, 0 remaining")
is reporting **its own script's** measurement. Two failure modes recur, and neither is
visible to a linter, the test suite, or a drift check, because the damage lands inside
docstrings and comments where the language does not care.

**Why:** a line-by-line strip regex eats the wrong whitespace and produces column-0
docstring corruptions (a bare `.`, `, never by the successor table:`) or word merges
(`from .config.json` → `from.config.json`), while the "0 remaining" is measured with the
finding's own grep — which required a literal space and never saw the surviving backticked
variants. All of it then propagates verbatim into every generated mirror, and the full
gate stays green.

**How to apply:** for any bulk-rewrite step, do three things before believing the count.

1. **Re-run the detection regex in a *looser* form than the fix used** — vary quoting,
   backticks, and separators — and diff the counts against the base commit, not against
   zero.
2. **Tokenize the edited files** (`tokenize` for STRING/COMMENT) and grep those lines for
   `^\s*[.,;:]`, collapsed `\w\.\w`, empty parens, and orphan section signs.
3. **Do a whitespace-normalized *word-level* `difflib` diff** of old vs new and read every
   non-equal opcode. That is what proves "delete the parenthetical, keep the sentence" was
   honored, and it is also the cheapest way to prove a re-wrap (reclaiming lines against a
   line cap) dropped nothing. Trust the word diff, not the fix note.
