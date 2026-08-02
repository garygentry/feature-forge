# Verification Report: stage-exit-coverage (impl — round 9 require-clean re-verify)
Date: 2026-08-02
Pipeline Stage: forge-5-loop (complete, v1) — served production stage `forge-5-loop`
Method: clean-room require-clean re-verification of the round-8 V-001 fix (artifacts `3a98dee` + provenance `15111f9`; parent `8f315cc`). Every behavioural claim in the amended comment was re-derived with an independent in-process AST + `exec` instrument (`_module_scope_writes`/`_module_scope_nodes` extracted from the live file, all five assertions plus the runtime roster value replayed against synthesised decoy sources). Nothing in the repository was modified (memory writes land in a gitignored path).

Artifacts Reviewed:
- `/home/gary/workspace/feature-forge/specs/stage-exit-coverage/.verification/VERIFY-impl-2026-08-01-round8.md` (Findings, Fix Execution Plan, Fix Progress)
- `git show 3a98dee` / `15111f9` (diff, stat)
- `/home/gary/workspace/feature-forge/tests/test_capability_determination_prose.py` (lines 555-625, the guard + amended comment)

Checks Executed: 4 of 4 dispatch checks (gate, V-001 resolution, no-regression/no-new-narrative, Fix-Progress accuracy) — 3 pass, 1 fail (new finding).

## Summary
- Total findings: 1
- Gaps: 0
- Inconsistencies: 0 (the finding below is also internally inconsistent, filed as error)
- Improvements: 0
- Errors: 1

**Verdict: require-clean gate GREEN; round-8 V-001 core RESOLVED; but a NEW `error` of the same false-narrative family survives on the fix's own changed line → NOT clean → another fix pass.**

### Require-clean gate — GREEN (re-run, not taken on report)
| Check | Result |
|---|---|
| `git status --porcelain` | empty |
| `bash scripts/validate.sh` | `All checks passed!` (exit 0) |
| `ruff check tests/` | Found 19 errors (unchanged) |
| `ruff check scripts/ eval/` | clean |
| `python3 scripts/check-spec-purity.py` | PASS — 0 violations |
| `python3 scripts/build-adapters.py --check` | exit 0 |
| Executable-token identity (tokenize, comments+strings stripped) HEAD vs `3a98dee^` | 1666 = 1666, **identical** — comment-only diff, no assertion moved |

### What the fix got right (independently confirmed)
- The false "…caught by the derivation-`Call` assertion below **regardless of binding form**" clause is **gone**. The replacement attribution is now **accurate**, re-derived in-process:
  - count assertion reds any ADDITIONAL counted binding — CONTROL `ALL_SURFACES = […]` → RED via `len(bindings)==2` (a1).
  - derivation-`Call` assertion reds a literal VALUE at the single annotated binding — single `ALL_SURFACES: Final = […]` → only a3 reds (a1/a2 pass).
  - out-of-scope forms NOT caught — walrus / for-target / with…as / global-in-fn / match-capture all leave the full five-assertion guard **GREEN** with runtime `ALL_SURFACES == [('HANDKEPT','y')]`.
- `del` correctly carved out into its own note (UNBINDS → `NameError` at collection before the reads; roster already captured after) — confirmed: a subsequent module read after `del` → `NameError`.
- `match`-capture correctly added to the enumerated forms.
- Round-8 Fix Progress accurately records the del carve-out, the derivation-`Call` re-attribution, and the match-capture addition. Its acceptance matrix, however, re-probed only 5 of the 8 listed forms (see finding).

## Findings

### V-001: The sharpened blanket "Each of THOSE was probed and confirmed to leave the suite green with the roster displaced" is still false for two enumerated forms — comprehension target and `except … as`
- **Severity:** error
- **Location:** `/home/gary/workspace/feature-forge/tests/test_capability_determination_prose.py:576-583` (the changed/added lines of the recorded-decision comment)
- **Issue:** In resolving round-8 V-001, the fix reworded the blanket to *"Each of THOSE was probed and confirmed to leave the suite green with the roster displaced"* over the set {walrus, `For`/`AsyncFor` target, `with … as`, **a comprehension target**, `import … as`, **`except … as`**, `match`-capture, `global`-in-function}. It correctly carved `del` out of that set for a property (unbind → `NameError`, cannot be green-and-displaced). But two members of the set share that exact property and were left in — re-derived with an independent instrument (guard = full five assertions; roster read = a subsequent module-scope `[s[0] for s in ALL_SURFACES]`):

  | Form | guard | subsequent roster read | verdict vs claim |
  |---|---|---|---|
  | `for ALL_SURFACES in …` (target) | GREEN | `['HANDKEPT']` — displaced | claim holds |
  | walrus / `with…as` / `global`-in-fn / `match`-capture | GREEN | displaced (`HANDKEPT`) | claim holds |
  | **comprehension target** `[… for ALL_SURFACES in …]` | GREEN | **`['REAL']` — roster INTACT, NOT displaced** | **claim false** |
  | **`except … as ALL_SURFACES`** | GREEN (AST) | **`NameError`** on read | **claim false** |

  - **Comprehension target:** Python 3 comprehensions have their own scope; the iteration name does not leak to module scope, so it can **never** displace the module roster. It leaves the suite green *with the real roster intact* — the opposite of "displaced."
  - **`except … as`:** Python 3 (PEP 3110) implicitly `del`s the exception target at the end of the handler. It is `del`'s exact semantic twin — placed before the `SURFACE_IDS`/`parametrize` reads it raises `NameError` at collection (not green); it never leaves a "green-and-displaced" decoy. The comment carves `del` out for precisely this reason two lines later, making the comment **internally inconsistent**: it condemns `del` for a property it simultaneously attributes to `del`'s twin.

  The fix's Fix Progress acceptance matrix re-probed only 5 forms (walrus / for / with / global / match) — it did **not** re-probe comprehension target or `except … as`, which is exactly how the residual false claim survived. This is the ninth consecutive round in which a mechanically-correct change (the del carve-out and the derivation-`Call` re-attribution are both right) ships wrapped in a claim the semantics do not support.
- **Suggested fix:** Prose only; no assertion change (Decision 1(c) stands). Either (a) move `except … as` next to `del` in the UNBINDS note (Python 3 auto-`del`s the exception target → `NameError` before the reads, roster already captured after — not a green-and-displaced decoy), and drop the comprehension target from the "roster displaced" set (Python 3 comprehension scope does not leak, so it leaves the roster **intact**, never displaced); or (b) narrow the blanket to name only the forms that genuinely leave the suite green **with the roster displaced** (walrus, `For`/`AsyncFor` target, `with … as`, `global`-in-function, `match`-capture — the five actually re-probed), and list comprehension-target / `except … as` / `del` / `import … as` under a separate "does not produce a green-and-displaced decoy (scope-local, unbinds, or non-iterable)" note.
  **Acceptance evidence (mandatory, NOT suite-green):** for every form left in the "roster displaced" set, re-probe with a *subsequent module-scope read* of `ALL_SURFACES` (not `ns.get`, which masks unbound-vs-`None`) and confirm the read succeeds AND yields the hand-kept value; for every form moved to the unbind/no-leak note, confirm the read raises `NameError` (unbind) or returns the real roster (no leak).
- **References:** `tests/test_capability_determination_prose.py:580-583` (the `del` carve-out whose logic condemns `except … as`), `:597-625` (the five assertions); round-8 report Fix Progress Step 1 (acceptance matrix covered 5 of 8 listed forms)
- **Checklist:** CHECK-I19, CHECK-I17

## Fix Execution Plan

### User Decisions Required
None — V-001 is a prose correction with no behavioural consequence (Decision 1(c) stands, no assertion touched). This file is not mirrored into the adapter trees, so no adapter regeneration is required.

### Execution Steps
#### Step 1: Correct the "roster displaced" set to exclude scope-local and unbinding forms
- **Files:** `/home/gary/workspace/feature-forge/tests/test_capability_determination_prose.py` (`:576-583`)
- **Addresses:** V-001
- **Action:** Apply V-001's suggested fix (option a or b). Move `except … as` into the `del` UNBINDS note (both auto-`del`/unbind → `NameError` before the reads); remove the comprehension target from the "roster displaced" claim (Python 3 comprehension scope does not leak → roster intact). Change no assertion.
- **Acceptance evidence:** re-probe EVERY form remaining in the "roster displaced" set with a subsequent module read (must yield the hand-kept literal); confirm `except … as` → `NameError` and comprehension target → real roster. `validate.sh` `All checks passed!`; `ruff check tests/` still 19; `check-spec-purity.py` PASS.
- **Depends on:** none.

## Compact digest (re-verify gate decision)
- **Require-clean gate: GREEN** — `git status` empty · `validate.sh` all passed · ruff tests 19 · ruff scripts/eval clean · spec-purity PASS · build-adapters `--check` exit 0 · executable tokens byte-identical to pre-fix (comment-only diff).
- **Round-8 V-001: core RESOLVED** — the "regardless of binding form" false generalisation is gone; count / derivation-`Call` attributions independently re-derived as accurate; `del` correctly carved out; `match`-capture added.
- **NEW V-001 (error): NOT clean.** The fix's own reworded blanket "Each of THOSE was probed and confirmed to leave the suite green with the roster displaced" is still false for **comprehension target** (Python 3 scope does not leak → roster intact, never displaced) and **`except … as`** (Python 3 auto-`del`s the target → `NameError` at collection — `del`'s twin, which the very next sentence carves out). Same false-narrative family, ninth consecutive round; slipped through because the fix's acceptance matrix re-probed only 5 of the 8 listed forms.
- **Recommendation: another fix pass** (single prose edit, no assertion change).

Relevant path: `/home/gary/workspace/feature-forge/tests/test_capability_determination_prose.py:576-583`.
