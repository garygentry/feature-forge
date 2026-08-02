# Verification Report: stage-exit-coverage (impl, round 8)
Date: 2026-08-01
Pipeline Stage: forge-5-loop (complete, v1)
Mode: impl — served production stage `forge-5-loop`
Method: clean-room require-clean re-verification against the round-7 fix pass (commits `ac6d326` artifacts + `00ae795` provenance; base `db1b8bb`). Every numeric/behavioural claim the fix pass wrote into a comment, docstring or the state file was re-derived with an instrument different from the one the fix pass used (in-process AST probing rather than pytest-on-copies; tokenize-level equivalence rather than diffing). Nothing in the repository was modified.

Artifacts Reviewed:
- `/home/gary/workspace/feature-forge/specs/stage-exit-coverage/.verification/VERIFY-impl-2026-08-01-round7.md` (Findings, Fix Progress, Decision-1 RESOLVED note)
- `git show ac6d326` (10 files: 3 non-adapter + 6 adapter mirrors + 1 report)
- `/home/gary/workspace/feature-forge/tests/test_capability_determination_prose.py`
- `/home/gary/workspace/feature-forge/scripts/forge-session.py`, `/home/gary/workspace/feature-forge/scripts/epic-manifest.py`
- all six `adapters/*/scripts/forge-session.py` mirrors; `skills/forge-{1-prd,2-tech,3-specs,4-backlog,verify,fix}/SKILL.md`
- `/home/gary/workspace/feature-forge/specs/stage-exit-coverage/.pipeline-state.json`, `forge.config.json`

Checks Executed: 23 of 23 (19 pass, 1 fail, 3 not-applicable)

## Summary

- **Total findings: 2** — 1 error, 1 improvement (advisory), 0 gaps, 0 inconsistencies.
- **All five round-7 findings are RESOLVED.** V-001 (helper docstrings), V-003 (fresh bullet) and V-004 (control 3a-ii) are genuinely fixed, each re-derived end-to-end against the code it describes. V-002 landed as decision **(c) record and stop** — the six X-probes are GREEN by decision and recorded. V-005 was advisory only.
- **BUT the standing failure mode recurred for the EIGHTH time — in the recorded-decision comment that resolved V-002.** The comment's load-bearing justification claims *"the ONE property that actually matters — replacing the derived roster with a literal list — is caught by the derivation-`Call` assertion below regardless of binding form."* **This is false.** I bound `ALL_SURFACES` to a hand-kept literal list `[('HANDKEPT','y')]` via a walrus, a `for` target, `with … as`, a `global`-in-function, and a `match`-capture, with the real derivation left intact; in every case the full five-assertion guard stayed **GREEN** while the runtime roster was the literal. The derivation-`Call` assertion catches a literal-list replacement **only** when it is installed via a *counted* binding form (`Assign`/`AnnAssign`/`AugAssign`) — via the very out-of-scope forms the comment enumerates, a literal decoy sails through. This is the exact recorded reassurance used to justify stopping, and it does not hold. → **V-001 (error)**.
- **The six X-probes are confirmed GREEN with roster displaced, and the ten closed shapes confirmed RED**, re-derived in-process. The guard's executable tokens are **byte-identical** to the round-7-measured version (only docstrings/comments changed), so round-7's behavioural measurements transfer and were independently re-confirmed.
- **The out-of-scope comment does NOT claim exhaustiveness**, so a form it omits (`match`-capture) is *not itself* a dishonesty finding — the comment explicitly states "the space of ways to rebind a Python name is not enumerable." I tested the dispatch's hypothesis and it does not rise to a finding on those grounds; `match`-capture instead appears as supporting evidence under V-001.
- **The gate is confirmed, not taken on report**, on a tight but sufficient disk (1.8 GB free, stable across a full validate + full suite): `validate.sh` → `All checks passed!`; **1809 passed / 2 skipped**; 0 fixture bytecode; ruff/spec-purity clean; `build-adapters --check` exit 0; `git status --porcelain` empty.
- **Adapter mirrors, pipeline state, and the report tail are all exactly as specified.**

---

## Measurements

### 1. Gate (re-run independently)

| Check | Expected | Measured | Result |
|---|---|---|---|
| `df -h /` before gating | ≥ 1 GB | **1.8 GB** free (stable after) | OK |
| `bash scripts/validate.sh` | `All checks passed!` | `All checks passed!` | CONFIRMED |
| Full suite (`pytest -q -p no:cacheprovider`) | 1809 passed / 2 skipped | **1809 passed, 2 skipped** in 220.93s | CONFIRMED |
| `find tests/fixtures -name '__pycache__' -o -name '*.pyc' \| wc -l` | 0 | **0** (after validate and after full suite) | CONFIRMED |
| `ruff check scripts/ eval/` | clean | `All checks passed!` | CONFIRMED |
| `ruff check tests/` | 19 | **Found 19 errors** | CONFIRMED (unchanged) |
| `ruff check tests/ --select F841,F541` | clean | `All checks passed!` | CONFIRMED |
| `python3 scripts/check-spec-purity.py` | PASS, 0 violations | `spec-purity: PASS — 0 violations` | CONFIRMED |
| `python3 scripts/build-adapters.py --check` | exit 0 | exit **0** | CONFIRMED |
| `git status --porcelain` | empty | **empty** | CONFIRMED (require-clean satisfied) |

### 2. Guard behaviour is provably unchanged from round-7's measurement

Tokenize-level comparison of `tests/test_capability_determination_prose.py` between `cef9eb0` (the version round-7 probed) and HEAD, with string literals collapsed to a placeholder and comments dropped: **1665 executable tokens each, identical**. The round-7→round-8 fix changed only docstrings and one comment; no assertion or helper body moved. Round-7's independent 16-probe behavioural measurements therefore transfer, and I re-confirmed the salient ones in-process (below).

### 3. Roster-guard probe battery — my own in-process AST instrument (V-002 / new V-001)

I extracted `_module_scope_nodes`, `_store_target_names`, `_module_scope_writes` from the live file and replicated all **five** assertions of `test_the_controls_cover_every_determining_surface` (count == 1, `bindings[0]` is `AnnAssign`, `bindings[0].value` is a `Call` to `_capability_surfaces`, one `_capability_surfaces` def, no alias). This is a different instrument than the fix pass's pytest-on-real-copies, and disk-free.

**Ten closed shapes — RED (guard catches), confirmed:** P1 literal rebind (count=2), P4 `AnnAssign`→`Assign` (RED at the `AnnAssign`-shape assertion), P6/alias (count=2), N3 in-place `[:]` (count=2), N4 shadow `def` (defs=2), aug-assign (count=2).

**Six X-forms — GREEN (guard misses), roster displaced, confirmed:** X1 walrus, X2 module `for` target, X3 `global`-in-function, X4 `with … as`, X5 `for` on derivation name, X6 walrus on derivation name — each keeps `bindings==1` (the untouched `AnnAssign`), `defs==1`, no alias → all five assertions pass.

**The load-bearing claim, DISPROVED (basis of new V-001).** Binding `ALL_SURFACES` to a hand-kept literal `[('HANDKEPT','y')]` via each out-of-scope form, real derivation left intact, then executing to read the runtime value:

| Literal decoy installed via | Full 5-assertion guard | runtime `ALL_SURFACES` |
|---|---|---|
| walrus `(ALL_SURFACES := […])` | **GREEN** | `[('HANDKEPT','y')]` |
| `for ALL_SURFACES in [［…］]` | **GREEN** | `[('HANDKEPT','y')]` |
| `with … as ALL_SURFACES` | **GREEN** | `[('HANDKEPT','y')]` |
| `global ALL_SURFACES` in called fn | **GREEN** | `[('HANDKEPT','y')]` |
| `match […]: case ALL_SURFACES` | **GREEN** | `[('HANDKEPT','y')]` |
| CONTROL: `ALL_SURFACES = […]` (counted `Assign`) | **RED** (count=2) | `[('HANDKEPT','y')]` |

So a hand-kept literal list is caught **only** through a counted binding form, and then by the **count** assertion (bindings=2), not the derivation-`Call` assertion. Through any uncounted form it is not caught at all. The comment's "regardless of binding form" is false, and it even mis-attributes which assertion does the catching.

### 4. Completeness of the out-of-scope comment (dispatch item 2-iii)

The comment lists `NamedExpr`, `For`/`AsyncFor` target, `with … as`, comprehension target, `import … as`, `except … as`, `del`, and `global`-in-function. In-process I confirmed each of the listed forms leaves the guard GREEN. **`match`-capture** (`case ALL_SURFACES`, an `ast.MatchAs`) also leaves the guard GREEN with the roster displaced and is **not** in the list — but the comment explicitly states "the space of ways to rebind a Python name is **not enumerable** by adding node types," so the omission is *not* a dishonesty finding; the comment does not claim to record them all. It is folded into V-001 as further evidence against "regardless of binding form."

Two secondary imprecisions in the same comment, noted under V-001: (a) `del ALL_SURFACES` **cannot** "leave the suite green with the roster displaced" — placed before the `SURFACE_IDS`/`parametrize` reads it raises `NameError` at collection (not green), placed after them the roster is already captured (not displaced) — so the blanket "Each was probed and confirmed to leave the suite green with the roster displaced" is false for `del`; (b) `del` "replace[s] the roster" is inaccurate — it unbinds rather than replaces.

### 5. Round-7 V-001 helper docstrings — re-read end-to-end, HONEST

- `_module_scope_nodes` (`:475-486`): now says the traversal "covers every module-level BINDING STATEMENT … deliberately NOT exhaustive: an assignment inside a function that declares `global ALL_SURFACES` … is out of this traversal's reach." Read statement-by-statement against the body (`stack`-based walk stopping at `FunctionDef`/`AsyncFunctionDef`/`ClassDef`): the traversal does reach every module-scope node, and the `global`-in-function exception is correctly named. The false "exactly the set of statements that can replace a module global" and "rebinds nothing this module reads" are gone. No residual false claim.
- `_module_scope_writes` (`:513-517`): now "binding or mutating `name` as an `Assign`, `AnnAssign` or `AugAssign` — including stores reached through a subscript, attribute, star or tuple target. Not every binding form." Matches the body exactly (`isinstance` chain over those three node classes, `_store_target_names` covering the wrapper grammar). The false "in any form" is gone. Honest.

### 6. Round-7 V-003 fresh bullet — re-read against the code path

`verify_state` (`scripts/forge-session.py:875-961`) reaches `return stage, "fresh"` only after: `skipped` returns early (`:925`), `auto-verify-pending` returns early (`:932`), non-resolved statuses branch off (`:933-942`), and **`findings-applied` returns `"stale"` unconditionally (`:943-951`)**. The only status remaining at the version check (`:952-959`) is `passed`. So the amended bullet — *"the entry is `passed` AND its `verifiedStageVersion` matches … `passed` is the ONLY status that reaches `fresh`"* — is exactly what the code does. All seven bullets read top-to-bottom carry no mutual contradiction; `epic_verify_state` (`epic-manifest.py:1066`) names the identical set (`passed`-and-matching → fresh; `findings-applied` → stale unconditionally). RESOLVED.

### 7. Round-7 V-004 control 3a-ii — all six surfaces, re-derived

Amended docstring (`:417-423`) attributes the surviving match to `forge-verify` via `presented through the gate` (1), `forge-fix` via `presented through the Step 6 gate` (1), and the four authoring stages via their gate-block fragment (4) = 6. Independently grepped across the six capability files: `presented through the gate` occurs in **exactly 1 of 6** (`forge-verify` only); `presented through the Step 6 gate` in exactly 1 (`forge-fix` only); 0 in the four authoring stages. No contradiction with the module docstring's clause (c). RESOLVED.

### 8. Adapter mirrors (CHECK-I09/I10)

`build-adapters.py --check` exit 0. Each mirror's ac6d326 change is +4 lines (the `fresh`-bullet rewrite), and the new wording ("ONLY status that reaches") is present in all six. Programmatically: claude/codex/copilot/cursor/gemini are **byte-identical to canon**; `adapters/pi` is reproduced **byte-for-byte** by `canon.replace("/feature-forge:", "/skill:")`. Mirrors differ from canon only where the documented per-adapter degradation requires.

### 9. Pipeline state — CONFIRMED

| Property | Expected | Measured |
|---|---|---|
| `forge-verify-impl.status` | `findings-applied` | `findings-applied` ✓ |
| `.findingsFile` | round-7 report | `.verification/VERIFY-impl-2026-08-01-round7.md` ✓ |
| `.findingsCount` | 5 | `5` ✓ |
| `.verifiedStageVersion` | CLEARED | absent ✓ |
| `.verifiedAt` | absent | absent (`fixedAt: 2026-08-02T00:34:35Z`) ✓ |
| `.commitHash` | full 40-hex of `ac6d326` (artifact, not `00ae795`) | `ac6d326523322e0e5b41db3fc3b1ce4f74149edd`, len 40, artifact commit ✓ |
| Other stage entries | undisturbed | `forge-5-loop` unchanged ✓ |

### 10. Mechanical-damage sweep — CLEAN

Over the added lines of the three non-adapter files + mirrors: **0** TODO/FIXME/XXX/HACK/TBD, **0** column-0 punctuation in added `.py` lines, 0 merged words, 0 de-indented docstring continuations (all added docstring/comment blocks read as clean prose end-to-end). The only `agentId`/`<usage>` token in the round-7 report is at line 484 — Fix-Progress prose *describing* that the stray trailer was stripped; the actual report tail (line 569) ends cleanly with the "Verification discipline honoured" paragraph. No trailer present.

---

## Findings

### V-001: The recorded-decision comment's justification is false — the derivation-`Call` assertion does NOT catch a literal-list roster replacement "regardless of binding form"; a hand-kept literal installed via walrus / `for` / `with … as` / `global` / `match`-capture leaves the full guard GREEN

- **Severity:** error
- **Location:** `/home/gary/workspace/feature-forge/tests/test_capability_determination_prose.py:574-586` (the recorded-decision comment added by ac6d326), specifically the final clause at `:583-586`
- **Issue:** Decision 1 was resolved to **(c) record and stop**, and the recording itself is legitimate: no assertion changed, the six X-forms are out of scope by an explicit decision, and the "not enumerable / needs a hand-planted decoy / no live drift" rationale is sound. But the comment's *closing, load-bearing* sentence states:

  > "…the ONE property that actually matters — replacing the derived roster with a literal list — is caught by the derivation-`Call` assertion below **regardless of binding form**, because a hand-kept list is not a call to `_capability_surfaces`."

  This is false. The derivation-`Call` assertion inspects `bindings[0].value`, where `bindings = _module_scope_writes(tree, "ALL_SURFACES")` counts only `Assign`/`AnnAssign`/`AugAssign`. If a hand-kept literal list is installed through any of the very forms the comment just declared out of scope, `bindings[0]` remains the untouched real `AnnAssign` (whose value *is* the Call), the assertion passes, and the literal is the effective roster. Measured in-process, real derivation left intact:

  | Literal `[('HANDKEPT','y')]` via | full 5-assertion guard | runtime `ALL_SURFACES` |
  |---|---|---|
  | walrus / `for` target / `with … as` / `global`-in-fn / `match`-capture | **GREEN** | `[('HANDKEPT','y')]` |
  | counted `Assign` (control) | RED (count=2) | `[('HANDKEPT','y')]` |

  A literal decoy is caught **only** via a counted binding form, and then by the `len(bindings)==1` **count** assertion — not the derivation-`Call` assertion the comment credits. So both halves of the claim are wrong: the catch is not "regardless of binding form," and it is not the derivation-`Call` assertion that does it in the counted case. `match`-capture (`ast.MatchAs`) is a further green miss not even in the enumerated list; because the comment disclaims exhaustiveness this is not a separate finding, but it is one more form for which "regardless of binding form" fails.

  Two secondary imprecisions in the same comment: (a) the blanket "Each was probed and confirmed to leave the suite green with the roster displaced" is false for `del` — `del ALL_SURFACES` before the `SURFACE_IDS`/`parametrize` reads raises `NameError` at collection (not green), and after them cannot displace the already-captured roster; (b) describing `del` as a form that "replace[s] the roster" is inaccurate (it unbinds).

  This is the eighth consecutive round in which a mechanically-correct change (Decision 1(c), no assertion touched, 1809 tests green) shipped wrapped in a claim the code does not support — and, as in round 7, the false claim is in the very prose written to resolve the previous finding.
- **Suggested fix:** One comment edit in `tests/test_capability_determination_prose.py:583-586`, prose only — no assertion change (Decision 1(c) stands). Replace the false generalisation with what is actually true, e.g.:

  > "…and the ONE property that actually matters — replacing the *derivation* `_capability_surfaces()` at the single annotated binding with a literal list — is caught: the count assertion reds any *additional* counted binding, and the derivation-`Call` assertion reds a literal value at that annotated binding. A literal installed through one of the out-of-scope forms above is NOT caught (it leaves the real derivation as `bindings[0]`); that is the recorded, accepted residue, not a claim of coverage."

  Then, in the sentence "Each was probed and confirmed to leave the suite green with the roster displaced," either drop `del` from that clause or move it to a separate note stating `del` unbinds (and cannot be a green-and-displaced decoy).

  **Acceptance evidence (mandatory, NOT suite-green):** re-run the literal-decoy matrix in §3 above and confirm the amended comment claims only what those forms actually do; read the whole comment end-to-end against the five assertions, naming for each assertion exactly which decoy shapes it reds; confirm no remaining sentence attributes to the derivation-`Call` assertion a catch it does not have.
- **References:** `tests/test_capability_determination_prose.py:513-530` (`_module_scope_writes`, the counted forms), `:587-616` (the five assertions), `:345-346` (the guarded binding and `SURFACE_IDS`); round-7 V-002 Decision 1(c) and its Fix Progress Step 2 (which records the same false "catches … regardless of binding form" claim)
- **Checklist:** CHECK-I19, CHECK-I17

### V-002: No `smokeCommand` is configured — advisory re-affirmed (CHECK-I21)

- **Severity:** improvement
- **Location:** `/home/gary/workspace/feature-forge/forge.config.json`, `"smokeCommand": null`
- **Issue:** CHECK-I21 requires an advisory finding whenever `smokeCommand` is `null`. Decision 6 (round 5) resolved to keep `null`; `07-testing-strategy.md` §8.3 records it as not-applicable by design under REQ-COMPAT-03. Re-assessed this round: **still not-applicable.** Every residual defect across eight rounds has been false prose or a vacuous guard — this round's V-001 is a comment misdescribing which assertion catches what — none of which a booting smoke command can detect. The "does it actually run" boundary remains covered by `tests/test_stage_exit.py` driving the shipped CLI via `subprocess.run([...])`.
- **Suggested fix:** None. Keep `smokeCommand: null` per Decision 6 and §8.3. This entry exists only to satisfy CHECK-I21's mandatory advisory; it is not a remedy for the recurring false-narrative failures.
- **References:** `specs/stage-exit-coverage/07-testing-strategy.md` §8.3; round-7 V-005, Decision 6
- **Checklist:** CHECK-I21

---

## Round-7 finding disposition (each independently re-measured)

| Round-7 finding | Verdict | Independent evidence derived this round |
|---|---|---|
| **V-001** (error) two helper docstrings claim completeness the helpers lack | **RESOLVED** | `_module_scope_nodes` now says "covers every module-level BINDING STATEMENT … deliberately NOT exhaustive," names the `global`-in-function exception, and drops "rebinds nothing this module reads"; read statement-by-statement against the body it is honest. `_module_scope_writes` names its three node classes instead of "in any form." No residual false claim in either docstring. (The new false claim is in the *comment*, not these docstrings → V-001 above.) |
| **V-002** (improvement) six open binding forms | **RESOLVED as decision (c)** | The recorded-decision comment landed; six X-forms confirmed GREEN with roster displaced (in-process, §3), ten closed shapes confirmed RED, floor never a source. Decision (c) — record and stop — is faithfully applied (no assertion changed; executable tokens byte-identical to round-7). **However the comment's justification prose introduced a new false claim → V-001.** |
| **V-003** (inconsistency) `fresh` bullet said "resolved AND matching" | **RESOLVED** | The bullet now names `passed` as the ONLY status reaching `fresh`. Re-derived against the code path (`findings-applied`/`skipped`/`auto-verify-pending` all exit before the version check; only `passed` remains). Matches `epic_verify_state` read side by side. All seven bullets mutually consistent. |
| **V-004** (improvement) control 3a-ii accounted for 5 of 6 surfaces | **RESOLVED** | 3a-ii now attributes the surviving match to `forge-verify` (1) + `forge-fix` (1) + four authoring stages (4) = 6. `presented through the gate` grepped in exactly 1 of 6 files (`forge-verify`); `presented through the Step 6 gate` in exactly 1 (`forge-fix`); no contradiction with the module docstring's clause (c). |
| **V-005** (advisory) `smokeCommand: null` | **RESOLVED as decision** | Kept `null` per Decision 6; re-affirmed as V-002 per CHECK-I21's mandatory advisory. |

---

## Checks Executed

| Check | Result | Note |
|---|---|---|
| CHECK-I01 | pass | `01-architecture-layout.md` untouched by ac6d326; round-7 confirmed §2 complete. |
| CHECK-I02 | not-applicable | No `package.json` anywhere; Python + markdown plugin. |
| CHECK-I03 | pass | `forge-session.py` change is docstring-only (`verify_state`); no `Literal`/`Final`/`TypedDict`/quoted signature from `00-core-definitions.md` touched. |
| CHECK-I04 | pass | `UsageError` and handler untouched. |
| CHECK-I05 | pass | 32/32 backlog items done; standing traps intact under a green `validate.sh`. |
| CHECK-I06 | pass | ids `001`..`032`, all `done`. |
| CHECK-I07 | pass | All five round-7 acceptance claims re-derived independently and reproduce (all RESOLVED). |
| CHECK-I08 | pass | No import added this round; all three changed modules import and run. |
| CHECK-I09 | pass | `build-adapters.py --check` exit 0. |
| CHECK-I10 | pass | 5/6 mirrors byte-identical to canon; `adapters/pi` reproduced byte-for-byte by the `/feature-forge:`→`/skill:` degradation; each mirror +4 lines (fresh-bullet). |
| CHECK-I11 | pass | `ruff check scripts/ eval/` clean; `ruff check tests/` **19** (unchanged); `F841,F541` clean. |
| CHECK-I12 | pass | `validate.sh` `All checks passed!`; **1809 passed / 2 skipped**; 0 fixture bytecode after validate and after full suite. |
| CHECK-I13 | pass | 0 TODO/FIXME/XXX/HACK/TBD in added lines. |
| CHECK-I14 | pass | `verify_state` `fresh` bullet now correct; four-classifier `fresh`/`stale` sets agree (`passed`-and-matching fresh; `findings-applied` stale unconditionally). Round-7 V-003 resolved. |
| CHECK-I15 | pass | No hardcoded value changed; `MIN_CAPABILITY_SURFACES`/`CALL_SPAN`/`MIN_CALL_SITES` untouched. |
| CHECK-I16 | pass | 1809 passed / 2 skipped; Decision 1(c) changed no assertion, so no test churn (executable tokens byte-identical). |
| CHECK-I17 | pass | The guard itself behaves as designed and the (c) decision to leave the extra forms open is legitimate; the defect is prose, not effectiveness (→ CHECK-I19). |
| CHECK-I18 | pass | `README.md` present; `docs/architecture/` unchanged; `stage-exit-coverage` docs absent because `forge-6-docs` has not run — correct for impl-verify. |
| CHECK-I19 | **fail** | **V-001.** Mechanical sweeps are clean; the failure is semantic — the recorded-decision comment's justification claims the derivation-`Call` assertion catches a literal-list replacement "regardless of binding form," which a literal decoy via walrus/`for`/`with`/`global`/`match` leaves GREEN. |
| CHECK-I20 | pass | Round-7 V-005 closed; `_state_verify_call_text` window arithmetic untouched. |
| CHECK-I21 | not-applicable | `smokeCommand` is `null`; advisory re-affirmed as V-002; §8.3 records not-applicable by design. |
| CHECK-I22 | pass | No bootstrap symbol changed; `_verify_state_for` still referenced in `stage_exit`'s non-epic branch. |
| CHECK-I23 | not-applicable | Python stack, no universal bootstrap entry (no `pyproject.toml`, no framework startup hook). |

**Executed 23 of 23 checks. Results: 19 pass, 1 fail, 3 not-applicable.**

---

## Fix Execution Plan

### User Decisions Required

**None.** V-001 is a prose correction with no behavioural consequence — Decision 1(c) stands (no assertion changes); only the comment's false justification clause is rewritten to state what the assertions actually catch. V-002 is an advisory requiring no action. Note that V-001's fix edits `tests/test_capability_determination_prose.py` only (a comment) — this file is **not** mirrored into the adapter trees, so no adapter regeneration is required for it.

### Execution Steps

#### Step 1: Correct the recorded-decision comment's false justification
- **Files:** `/home/gary/workspace/feature-forge/tests/test_capability_determination_prose.py` (`:574-586`)
- **Addresses:** V-001
- **Action:** Apply V-001's suggested fix. Replace the "caught … regardless of binding form" clause with an accurate statement: the count assertion reds an *additional counted* binding, the derivation-`Call` assertion reds a literal *value at the annotated binding*, and a literal installed through an out-of-scope form is NOT caught (it leaves the real derivation as `bindings[0]`) — the recorded, accepted residue. Fix the `del` clause ("leave the suite green with the roster displaced" and "replace the roster" are both wrong for `del`). Change no assertion.
- **Acceptance evidence:** re-run the literal-decoy matrix (walrus/`for`/`with`/`global`/`match` → GREEN with runtime roster = literal; counted `Assign` → RED via count), and read the amended comment end-to-end against the five assertions, naming per assertion which decoy shapes it reds. `1809 passed / 2 skipped` before and after; `check-spec-purity.py` PASS; `ruff check tests/` still 19.
- **Depends on:** none. This is the round's only `error`.

---

## Coverage

Every area named in the dispatch was reached:

- ✅ V-001 (round-7): both helper docstrings read end-to-end against the helper bodies; `global` exception verified; "covers every module-level binding statement" verified against the traversal.
- ✅ V-002 (round-7): own in-process AST probe battery (different instrument than the fix pass's pytest-on-copies); ten closed shapes RED, six X-forms GREEN with displacement; **dispatch item 2-iv tested and DISPROVED** (literal-list decoy via out-of-scope forms stays GREEN); completeness item 2-iii tested (`match`-capture found, but comment disclaims exhaustiveness so not a standalone finding); item 2-i floor never a source.
- ✅ V-003 (round-7): all seven `verify_state` bullets read top-to-bottom; re-derived against the code path; compared side by side with `epic_verify_state`.
- ✅ V-004 (round-7): 3a-ii and module clause (c) read side by side; `presented through the gate` counted per file (exactly 1 of 6); `forge-fix` fragment verified.
- ✅ Adapter mirrors: `--check` exit 0; five byte-identical to canon, pi reproduced by the documented degradation; fresh-bullet present in all six.
- ✅ Pipeline state: status/findingsFile/findingsCount/cleared version/commitHash (artifact `ac6d326`, not provenance `00ae795`).
- ✅ Report tail clean (no `agentId`/`<usage>` trailer; the one hit is descriptive prose).
- ✅ Gate: `df` first, `validate.sh`, full suite, fixture bytecode ×2, ruff ×3, spec-purity, `--check`, `git status`.
- ✅ Mechanical sweep: column-0 punctuation, merged words, de-indented continuations, TODO markers.
- ✅ CHECK-I01..I23, all 23 executed.

---

## Compact digest

**Findings: 2** — 1 error, 1 improvement (advisory), 0 gaps, 0 inconsistencies.

**Round-7 disposition:**
- **V-001** (helper docstrings) — **RESOLVED**. Both docstrings now bounded and honest; the `global` exception is correctly named; "in any form" replaced by the three node classes.
- **V-002** (six open binding forms) — **RESOLVED as decision (c)**. Six X-forms recorded and confirmed GREEN-by-decision; no assertion changed (executable tokens byte-identical). *But the recording's justification prose introduced a new false claim → new V-001.*
- **V-003** (`fresh` bullet) — **RESOLVED**. `passed` is now named as the only status reaching `fresh`; re-derived against the code path and against `epic_verify_state`.
- **V-004** (control 3a-ii) — **RESOLVED**. All six surfaces accounted for; `presented through the gate` in exactly 1 of 6 files.
- **V-005** (smokeCommand advisory) — **RESOLVED as decision**; re-affirmed as V-002.

**NEW findings:**
- **V-001 (error)** — the recorded-decision comment (`:583-586`) claims the derivation-`Call` assertion catches a literal-list roster replacement "regardless of binding form." Disproved: a hand-kept literal `[('HANDKEPT','y')]` installed via walrus / `for` target / `with … as` / `global`-in-function / `match`-capture leaves the full five-assertion guard GREEN with the runtime roster equal to the literal; a literal is caught only via a *counted* form, and then by the count assertion, not the derivation-`Call` one. Also the blanket "Each … leave the suite green with the roster displaced" is false for `del`. The eighth consecutive round of a mechanically-correct change wrapped in a false narrative, in the prose written to resolve the prior round's finding.
- **V-002 (improvement)** — CHECK-I21 mandatory `smokeCommand: null` advisory; keep `null` per Decision 6.

**Gate: GREEN, run not taken on report.** `df` 1.8 GB (stable) · `validate.sh` `All checks passed!` · **1809 passed, 2 skipped** · fixture bytecode 0 (×2) · `ruff scripts/ eval/` clean · `ruff tests/` 19 · `ruff tests/ --select F841,F541` clean · `check-spec-purity.py` PASS 0 violations · `build-adapters.py --check` exit 0 · `git status --porcelain` empty (require-clean satisfied — nothing written to the repository).
