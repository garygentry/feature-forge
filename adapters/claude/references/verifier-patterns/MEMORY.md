# Verifier Patterns — Index

Shipped, reviewed verification heuristics for the forge verifier — general craft that
transfers to any project the pipeline runs in. This is the **versioned, reviewed** layer;
it is distinct from the verifier's per-project `memory:` store, which accumulates
repo-specific observations locally. Read this index on start and open the patterns a given
mode makes relevant.

## Claim-checking

- [Spec Literals Are Filesystem Claims](pattern_spec_literals_are_claims.md) — every id, path, constant and signature a spec writes down is an assertion about the repo; verify them mechanically, they survive multiple rounds otherwise
- ["X does not exist" claims](pattern_absence_claims.md) — the one finding shape whose fix DELETES correct content; search the identifier, not the prose word
- ["Extend the existing X" / "X does NOT do Y"](pattern_extend_the_existing.md) — the two tech-spec claim shapes that are wrong often enough to check every time; open the function, not the comment
- [Test-Count Units](pattern_test_count_units.md) — a spec's "N tests" means pytest-COLLECTED, not `def` count; `--collect-only -q` before filing any size-claim error
- [Enum/Count Vocabulary Ripple](pattern_enum_vocabulary_ripple.md) — "one new enum value, rest derives" always under-lists surfaces; grep the OLD value across the whole tree, not the spec's file list

## Guard / mutation verification

- [Proximity-Window Drift Guards](pattern_proximity_window_guards.md) — never trust a "token near call site" guard on baseline-green; delete each token line one at a time and report every miss
- [Guard Substitutions: Measure Detection](pattern_guard_substitution_detection.md) — "structural beats tuned" is a maintainability claim; run the own-mandate mutation census and replay the deleted constant's recorded incident
- [Self-Referential Mutation Controls](pattern_self_referential_control.md) — a control whose mutation span comes from the function under test stays green under the very degradation it bounds; execute every "must FAIL when X degrades" checkbox
- [Vacuous Self-Reading Tests](pattern_vacuous_self_reading_tests.md) — `read(Path(__file__))` + positive substring is vacuous; demand the failing assertion's LINE NUMBER, mutate one property at a time
- [Scratch-Root Probes](pattern_scratch_root_probes.md) — symlinked `tests/` resolves back to the real repo and reads false GREEN; real-copy what you mutate, check `df`, always add an effectiveness control

## Re-verifying an applied fix

- [Post-Fix Re-Verify Shapes](pattern_postfix_reverify.md) — fixes introduce new defects; `ls` any claimed deletion (a gitignored file leaves `git status` clean and the fix believes it worked)
- [Judging Deliberate Deviations](pattern_deviation_judgment.md) — reproduce the fix pass's stated justification first, then attack the deviation on its own terms; prescribed fixes are sometimes worse
- [Mechanical Rewrite Damage](pattern_mechanical_rewrite_damage.md) — a bulk-edit fix pass measures itself with its own regex; re-derive with a looser pattern, scan for column-0 punctuation, word-diff every hunk
- [Carve-Out Sibling Semantics](pattern_carveout_sibling_semantics.md) — when a fix carves ONE form out of a blanket claim, re-probe every sibling that shares the property

## Count / arity drift

- [Stale Counts After a Split](pattern_stale_counts_after_split.md) — splitting a construct N ways leaves "two/three/both" scattered in banners and docstrings; grep the number words after any arity change
- [Sibling Docstring Sweep](pattern_sibling_docstring_sweep.md) — a mirrored guard updates exactly one of N docstrings; grep the *superseded* rationale the amended one disclaims
