# Verification Report: verify-test-debt (specs)
Date: 2026-08-03
Pipeline Stage: forge-3-specs (version 1)
Artifacts Reviewed: `PRD.md` (v2, upstream), `tech-spec.md` (v2, upstream), `00-core-definitions.md`, `01-architecture-layout.md`, `02-canon-and-prose-guard.md`, `03-machinery-trim.md`, `04-production-validations.md`, `05-coverage-backfill.md`, `06-brittleness-batch.md`, `07-testing-strategy.md`, `TRACEABILITY.md`; live repo: `scripts/forge-session.py`, `scripts/check-spec-purity.py`, `eval/run-compliance-eval.py`, `references/stage-exit-protocol.md`, `references/shared-conventions.md`, `skills/*/SKILL.md`, `tests/**`
Checks Executed: 38 of 38 (27 pass, 8 fail, 3 not-applicable)

Not-applicable: CHECK-S17, CHECK-S26 (no export map / import-path surface — Python test suite, no package boundary introduced), CHECK-S29 (performance-sensitive paths — PRD §4.5 declares runtime characteristics not applicable, and REQ-QUAL-04 forbids a wall-clock target).

Failing checks: CHECK-S06, CHECK-S08, CHECK-S10, CHECK-S12, CHECK-S15, CHECK-S34, CHECK-S36, CHECK-S37.

## Verification method notes

- Every cited symbol was located **by name** (C-07), never by line number.
- Derived figures in `07` §5 were re-derived independently, and the measured inputs were
  re-measured against the live tree (`pytest --collect-only`, module import of the test
  constants).
- The seven mutation controls specified in `03` §2.3 were **executed against live canon**
  (surface read via `_read_contract_surface`, mutation applied, `_assert_exit_contract`
  invoked) to confirm each `match=` pattern trips. All seven pass as written.
- The structural block scan in `03` §4 was executed against canon to confirm the two
  region-bound properties `03` §13 makes verification criteria of.
- Declared non-goals (`00` §10.3, `07` §8) and the ten recorded corrections in
  `TRACEABILITY.md` were treated as recorded positions. No finding is filed against a
  declared non-goal. Correction #4's `_VERB_INVOCATIONS` figure was checked for accuracy
  (permitted: "you may verify that each is accurate") and is the subject of V-001.

## Summary
- Total findings: 11
- Gaps: 0
- Inconsistencies: 8
- Improvements: 1
- Errors: 2

**Stage-blocking (`error`/`gap`): 2.**
**Narration-churn findings (blocking findings whose substance lies in a comment, docstring, or test narration): 0.**
**Advisory findings whose substance lay in narration: 0.**

## What is correct (recorded so a later round does not re-derive it)

These were checked and hold. They are the bulk of the suite.

- **Requirement coverage: 46/46.** `validate-traceability.py` reports 0 uncovered
  requirements and 0 broken cross-references. The three orphaned ids (`REQ-REL-01`,
  `REQ-STATE-01`, `REQ-DEBT-04`) are quotations of existing docstrings, exactly as
  `TRACEABILITY.md` § Coverage Verification states.
- **Mutation-class arithmetic (`03` §2.1, `07` §5.2) is exact.** Live collection:
  `9+9+9+18+9+4+9 = 67` mutation items, `9+9 = 18` stamp-verbatim, 17 other, total 102.
  The two-dimensional classes decompose exactly as claimed (retired-block `9×2`,
  ownership-token `2×2`).
- **All seven specified mutation controls work as written.** Each `match=` pattern was
  executed against a mutated copy of `skills/forge-verify/SKILL.md` and trips the intended
  assertion. `03` §2.2's representative rationale is correct: `forge-verify` carries the
  nested marker once and `forge-fix` twice; the owner tokens are outside the canonical
  stamp, so `match="never inferred"` is reachable.
- **`04-production-validations.md` is accurate throughout.** `_require_positive_int`'s body
  and `_validated_findings_file`'s current two-parameter signature and five branches match
  the quoted source byte-for-byte; the `--resumable --status complete` guard sits exactly
  where §2.4 places the new call; `cmd_state_artifact`'s body matches; `score_prelude`
  returns exactly the four keys in the stated order; `BRANCH_CRITERIA` holds the nine
  listed keys; `_to_result` computes `compliant=all(criteria.values())`; `SAFE_NAME_RE` and
  `_scan_features` match; `_derive_epic` genuinely does not exist; `scripts/forge-session.py`
  has no `return 1` / `sys.exit(1)` path.
- **Roster figures in `00` §9 are correct.** `_ACCEPTED_HASHES` = 3, `_REJECTED_HASHES` = 10,
  5 hand-rolled hash loops in the three named functions, 4 already-parametrized sites in
  `test_state_schema_conformance.py`, the epic corrupt-state loop is 5 shapes, and the
  gate-selection section holds exactly 6.
- **`CANONICAL_EXIT_SITES` is a 9-entry tuple carrying 10 contract paths**, with
  `forge-5-loop` owning two — `00` §4.1's unit correction (TRACEABILITY #7) is accurate.
  `SURFACES_WITHOUT_PROSE` has 3 entries, `MIN_CAPABILITY_SURFACES = 6`, and `CLAUSES`
  carries the six keys `a, b, c1a, c1b, c2, c3`.
- **TRACEABILITY correction #1 is accurate.** None of the c1a/c1b/c2/c3 phrasings appear
  anywhere in `references/stage-exit-protocol.md`; all four live in
  `shared-conventions.md` § "Verify Capability". Clauses **a** and **b** are in the
  canonical section.
- **The call-sites guard baseline matches:** 10 collected items, `MIN_CALL_SITES = 34`,
  `LOOKBEHIND = 12` / `LOOKAHEAD = 3` / `CALL_SPAN = 3`, the `inspect.getsource` meta-test
  and the tuning test both present, `test_the_epic_mandate_itself_is_still_documented`
  present. The module docstring does read "Both hold today (21 call sites, 0 misses)" —
  `07` §4.4 / `03` §5.5 correctly identify it as a pre-existing narration defect.
- **The structural scan is green on canon at 34/34**, and the two decisive region
  properties hold: the Git Commit Protocol's two `state-complete` calls resolve to
  **identical** bounds, and the Stage-Entry Guard's `state-enter` and `state-artifact`
  calls resolve to **separate** regions. `shared-conventions.md` carries exactly one
  `state-artifact` call site, so `03` §6's `_region_probe_site` uniqueness assertion holds.
- **Baseline measurements in `07` §2 are exact:** 1842 collected (1840 passed / 2 skipped),
  43 / 10 / 102 per-file.
- **`04` §5 / `05` §4's two-sided pattern is real:** `SPEC_BRANCH_CRITERIA` and
  `test_the_scorer_returns_exactly_the_nine_specified_criteria` exist as quoted.

---

## Findings

### V-001: `_VERB_INVOCATIONS` has 8 entries, not 9 — the derived suite total is 1794, not 1795
- **Severity:** error
- **Location:** `07-testing-strategy.md` §5.1 (measured-inputs table), §5.2 (per-file effect), §5.3 (the dedup row), §5.4 (expected suite total, and stated assumption 2); `TRACEABILITY.md` § "Corrections Recorded During This Stage" row 4
- **Issue:** The suite records, as a **measured correction to the tech spec**, that
  `_VERB_INVOCATIONS` has 9 entries where "`tech-spec.md` §8.2 assumed 8". Measured against
  the live tree, the dict in `tests/test_state_verbs.py` has **8** keys:
  `state-enter`, `state-artifact`, `state-complete`, `state-branch`, `state-note`,
  `state-decision`, `state-ecr`, `state-verify`. (`tests/test_state_schema_conformance.py`'s
  independent `VERB_INVOCATIONS` also has 8, so no reading of the name yields 9.) The tech
  spec's original 8 was right; the "correction" introduced the error.

  The figure is not cosmetic — it is an input to the derived count table, and the error
  propagates through every dependent cell:

  | Location | Stated | Correct |
  |---|---|---|
  | §5.1 `_VERB_INVOCATIONS` | 9 entries | **8** |
  | §5.3 corrupt-file collected after | 15 (`1 + 5 + 9`) | **14** (`1 + 5 + 8`) |
  | §5.3 dedup total collected | 13 → 56 | 13 → **55** |
  | §5.2 "REQ-BRIT-07 dedup" delta | +43 | **+42** |
  | §5.4 expected suite total | 1795 | **1794** |
  | §5.4 assumption 2 "the corrupt-file expansion is +12, not +7" | +12 | **+11** (and the tech spec's "+7 for the verb loop alone" was arithmetically right) |

  `07` §10's verification checkbox ("Suite collection lands near **1795**") and §5.4's
  "An implementer landing near 1795 is seeing the expected parametrization expansion" are
  the numbers REQ-QUAL-01's full-suite check is read against, so the wrong figure sends an
  implementer looking for a missing test that never existed. This is exactly the
  REQ-TRIAL-06 failure mode the table's own warning banner names, with the added twist that
  the *measured input*, not only the derived cell, is wrong.
- **Suggested fix:** Re-measure and correct in one edit (REQ-TRIAL-06 requires the derived
  cells move with the source):
  1. `07` §5.1: change the `_VERB_INVOCATIONS` row to **8 entries**, and change the "How
     obtained" note to `measured — matches tech-spec.md §8.2`.
  2. `07` §5.3: corrupt-file "Collected before → after" becomes `3 → **14** (1 + 5 + 8)`;
     the `total` row becomes `13 → **55**`.
  3. `07` §5.2: the `REQ-BRIT-07 dedup` row becomes `13 items | **55** | **+42**`.
  4. `07` §5.4: the arithmetic block becomes `+42 REQ-BRIT-07 dedup (13 → 55 collected)` and
     the total becomes **1794**; the sentence "An implementer landing near 1795…" becomes
     1794.
  5. `07` §5.4 assumption 2: rewrite to "`_VERB_INVOCATIONS` has **8** entries.
     `tech-spec.md` §8.2's '+7 more if the corrupt-file dedup is parametrized over all 8
     verb invocations' is correct for the verb loop alone; the epic loop contributes 4 more,
     so the corrupt-file expansion is **+11**. This is why §5.4 lands at 1794 rather than
     the tech spec's ≈1781."
  6. `07` §10: change the "lands near **1795**" checkbox to **1794**.
  7. `TRACEABILITY.md` correction row 4: strike the `_VERB_INVOCATIONS` clause (the parametrize
     /`import pytest` half of that row is accurate and stays). Either delete the clause or
     replace it with "`_VERB_INVOCATIONS` has 8 entries, as `tech-spec.md` §8.2 states —
     re-measured, no correction needed."
- **References:** `tests/test_state_verbs.py` (`_VERB_INVOCATIONS`),
  `tests/test_state_schema_conformance.py` (`VERB_INVOCATIONS`), `00-core-definitions.md`
  §9.3, `06-brittleness-batch.md` §8, `tech-spec.md` §8.2, PRD §3.6.1 (REQ-TRIAL-06)
- **Checklist:** CHECK-S08, CHECK-S37

### V-002: `03` §6's mutation control derives its mutation span from the function it is testing, so it cannot detect region widening — and `03` §13's acceptance criterion for it is unsatisfiable
- **Severity:** error
- **Location:** `03-machinery-trim.md` §6 (`_without_the_probe_mandate`,
  `test_deleting_a_call_sites_own_epic_mandate_is_reported`) and §13 → "REQ-TRIM-04,
  REQ-TRIM-05" checkbox: "That control **fails** when `_region_bounds`'s lower bound is
  degraded to the enclosing heading alone"
- **Issue:** REQ-TRIM-04 requires the deleted width bound (`test_the_window_is_no_wider_than_the_measured_maximum`)
  to be **replaced**, and `03` §6 states the replacement's purpose plainly: "This is the
  bound on the guard's discriminating width. A region that widened until every site is
  covered by an adjacent call's mandate would still pass Guard 1 and the non-vacuity floor,
  and nothing else would fail."

  As specified, it does not do that. `_without_the_probe_mandate` computes its mutation
  span from `site.bounds` — the output of `_region_bounds`, the very function whose
  widening the control exists to catch:

  ```python
  lower, upper = site.bounds
  first, last  = site.block
  for index in range(lower, upper):
      if first <= index <= last or EPIC_FLAG not in mutated[index]:
          continue
      mutated[index] = mutated[index].replace(EPIC_FLAG, "the member flag")
  ```

  Widening the region widens the **strike span in lockstep**, so the control deletes the
  neighbouring call's mandate too and the probe is still reported. I executed the
  specified algorithm against live canon:

  | `_region_bounds` variant | `removed` | Guard 1 reports probe? | Control verdict |
  |---|---|---|---|
  | fence-block (adopted) | 1 | yes (line 386) | passes |
  | **heading-only (the degradation §13 requires it to catch)** | **2** | **yes (lines 373 and 386)** | **passes — the checkbox is false** |

  Two consequences, both blocking:
  1. **`03` §13's verification criterion cannot be satisfied by the specified code.** An
     implementer who writes §6 verbatim and then runs the required degradation check will
     find the control still green, with no way to reconcile the spec against the result.
  2. **REQ-TRIM-04's replacement obligation is not met.** The deleted width bound is
     replaced by a control that is green under precisely the widening it is documented to
     bound, so the trim removes protection with nothing standing in for it — which is the
     over-deletion risk PRD §3.4's success criterion 4 names ("a mutation control replaces
     the deleted width bound").
- **Suggested fix:** Make the strike span **independent of `_region_bounds`**. Compute it
  directly from the fixed structural rule (nearest enclosing heading / previous
  call-bearing block → the probe's own block), so degrading `_region_bounds` widens only
  the *searched* region, not the *mutated* span. Replace `_without_the_probe_mandate`'s
  span computation with:

  ```python
      lines = text.splitlines()
      site = _region_probe_site(text)
      first, last = site.block
      flags = _fence_flags(lines)
      headings = _heading_lines(lines, flags)
      blocks = _call_blocks(lines)
      # The probe's own lead-in, fixed by document structure. Deliberately NOT
      # site.bounds: a span taken from the function under test widens with it, so the
      # control would delete a neighbour's mandate too and never go green.
      lower = max(
          max((index + 1 for index in headings if index < first), default=0),
          max((end + 1 for _, end in blocks if end < first), default=0),
      )
      upper = min(
          min((index for index in headings if index > last), default=len(lines)),
          min((start for start, _ in blocks if start > last), default=len(lines)),
      )
      mutated = list(lines)
      removed = 0
      for index in range(lower, upper):
          if first <= index <= last or EPIC_FLAG not in mutated[index]:
              continue
          mutated[index] = mutated[index].replace(EPIC_FLAG, "the member flag")
          removed += 1
  ```

  Keep the existing `assert removed, ...` guard. Add to §6's "Three properties make this a
  real control" list a fourth: **"The strike span is computed from document structure
  directly, never from `_region_bounds`. A control whose mutation is sized by the function
  under test cannot detect that function widening."**

  I verified this replacement against live canon: under the adopted fence-block bound the
  control passes (`removed=1`, probe reported); under the heading-only degradation the
  control goes green (`removed=1`, probe **not** reported), which is exactly what `03` §13's
  checkbox requires. No other part of §6 — the `before` baseline assertion, the canon
  re-read, `_region_probe_site` — needs to change.
- **References:** `03-machinery-trim.md` §4.4 (`_region_bounds`), §4.7 (the Stage-Entry
  Guard worked example the probe targets), §9; `00-core-definitions.md` §6.2, §6.4; PRD
  REQ-TRIM-04, PRD §8 criterion 4
- **Checklist:** CHECK-S34, CHECK-S37

### V-003: the "2 false failures under a naive heading scan" claim does not reproduce under the adopted fence-block bound
- **Severity:** inconsistency
- **Location:** `00-core-definitions.md` §6.3; `03-machinery-trim.md` §4.2, §4.8 (second row
  of the false-failure table), §13 → REQ-TRIM-03 checkbox ("`_heading_lines` returns no index
  inside a fenced block — verified by the guard being green on
  `references/shared-conventions.md` § Git Commit Protocol, **which is red under a naive
  heading scan**")
- **Issue:** `00` §6.3 states that a naive `^#{1,6} ` scan "misreads bash comments inside
  fences … truncating the region and producing **2 false failures** in
  `shared-conventions.md` § Git Commit Protocol", and makes the fence-aware heading index
  mandatory on that basis.

  Executed against live canon with the adopted **fence-block** bound and a deliberately
  naive (non-fence-aware) heading index, the scan is **34/34 green with zero misses**. The
  reason is structural: `_region_bounds` computes from the *block's* `first`/`last`, and the
  two bash comments (`# Commit 1 — before \`git commit\``, `# Commit 2 — after Commit 1
  lands, so its hash exists`) sit **inside** that block, so they satisfy neither
  `index < first` nor `index > last` and cannot move either bound. Both `state-complete`
  calls keep identical bounds `(323, 352)` under both heading modes.

  The failure mode is real only under a **call-line** bound — the variant `00` §6.2 rejects.
  So the mandate is justified by a symptom the adopted design has already eliminated, and
  `03` §13's REQ-TRIM-03 checkbox instructs the implementer to verify a redness that does not
  occur.

  This is filed as `inconsistency`, not `error`: `_fence_flags` / `_heading_lines` are
  independently correct and should be kept (a call found **outside** any fence bounds itself
  via `_sites_in`'s `(index, index)` fallback, where an in-fence `#` line *can* move a
  bound), and no shipped behavior is wrong. What is wrong is the stated evidence and one
  verification instruction.
- **Suggested fix:**
  1. `00` §6.3: replace the empirical claim with the structural one — "A naive `^#{1,6} `
     scan reads bash comments inside fences as headings. Under the fence-**block** bound
     those comments sit inside the block and cannot move either bound, so canon is green
     today either way; the fence-aware index is required because the bound degrades to the
     call's own line for any `state-*` call found outside a fence (`03` §4.5's
     `(index, index)` fallback), where an in-fence `#` line does truncate the region."
     Remove "producing **2 false failures**".
  2. `03` §4.2: same replacement; drop "produces **2 false failures** on a canon file that
     is correct".
  3. `03` §4.8: change the second row's Symptom cell from "**2 false failures**" to "no
     false failure under the fence-block bound; the region truncates for any unfenced call
     site, which is why the index is fence-aware".
  4. `03` §13 REQ-TRIM-03: replace the checkbox with a directly performable one —
     "`_heading_lines(lines, _fence_flags(lines))` returns no index that `_fence_flags`
     marks `True`, asserted directly against `references/shared-conventions.md`."
- **References:** `references/shared-conventions.md` § Git Commit Protocol;
  `03-machinery-trim.md` §4.3, §4.5
- **Checklist:** CHECK-S37

### V-004: `01` §3.1's body-line measurements are each off by one; `forge-verify` has zero headroom, not one line
- **Severity:** inconsistency
- **Location:** `01-architecture-layout.md` §3.1, "Body-size headroom — measured, not
  inferred" table
- **Issue:** Re-measured through `check-spec-purity.py`'s own `read_frontmatter` +
  `body_start_line` slice (the exact computation `check_body_size` performs):

  | Skill | Spec: body lines | Actual | Spec: headroom | Actual |
  |---|---|---|---|---|
  | `skills/forge-0-epic/SKILL.md` | 295 / 300 | **296** / 300 | +5 lines | **+4 lines** |
  | `skills/forge-verify/SKILL.md` | 299 / 300 | **300** / 300 | +1 line | **0 lines** |

  Word counts (2749, 4365) are exactly right, and `check_body_size` reports 0 violations
  (the test is `n_lines > MAX_BODY_LINES`, so 300 passes). Both conclusions the table
  supports still hold — a one-sentence pointer fits in 4 lines, and `forge-verify` still
  admits no capability prose (more strongly than stated). But the table is labelled
  "measured, not inferred", and a later round that trusts "+1 line" for `forge-verify` would
  add a line and break the gate.
- **Suggested fix:** In `01` §3.1's table set `forge-0-epic` body lines to **296** and
  headroom to **+4 lines**; set `forge-verify` body lines to **300** and headroom to
  **0 lines**. Change the following sentence from "`forge-verify` has **one line** — no
  capability prose may be added there" to "`forge-verify` is **at the cap** — not one line
  of body may be added there."
- **References:** `scripts/check-spec-purity.py` (`MAX_BODY_LINES`, `read_frontmatter`,
  `check_body_size`); PRD C-05; `00-core-definitions.md` §3.1
- **Checklist:** CHECK-S06

### V-005: `00` §1 and `05` §1.3 still carry the superseded "parametrize is an established idiom in every file" claim that `00` §10.5 and `07` §1 correct
- **Severity:** inconsistency
- **Location:** `00-core-definitions.md` §1 ("Project conventions this feature follows
  without deviation" → "`@pytest.mark.parametrize` for table-driven tests — an established
  idiom in **every file this feature touches**, so nothing here introduces a new
  convention"); `05-coverage-backfill.md` §1.3 ("…written with `@pytest.mark.parametrize`
  **from the start** (§7.2), which is an established idiom in all three files")
- **Issue:** Both statements are the tech spec §3.14 claim that `07` §1 and `00` §10.5
  explicitly supersede: `tests/test_state_verbs.py` has **zero** `parametrize` uses and
  **does not import `pytest` at all** (re-verified: `grep -c parametrize` = 0, no
  `import pytest` in the import block). `00` therefore contradicts itself between §1 and
  §10.5, and `05` §1.3 repeats the superseded form while `05` §3.2 flags the same file as
  unconfirmed (see V-011).

  The consequence is concrete: `05` §3.2, §6.2 and §7.2 all specify
  `@pytest.mark.parametrize` decorators in `tests/test_state_verbs.py`, and per `00` §10.5
  omitting `import pytest` there is a **collection-time `NameError`** that presents as the
  whole file vanishing from the run.
- **Suggested fix:**
  1. `00` §1: change the bullet to "`@pytest.mark.parametrize` for table-driven tests — the
     established idiom in `test_stage_exit.py`, `test_state_schema_conformance.py`, and
     `test_auto_verify.py`. **`tests/test_state_verbs.py` uses it nowhere and does not
     import `pytest`; work that adds a decorator there must add the import (§10.5).**"
  2. `05` §1.3: replace "which is an established idiom in all three files" with "…written
     with `@pytest.mark.parametrize` from the start (§7.2). Note that
     `tests/test_state_verbs.py` does not import `pytest` today — `00` §10.5 requires the
     import to be added with the first decorator."
- **References:** `00-core-definitions.md` §10.5; `07-testing-strategy.md` §1;
  `TRACEABILITY.md` correction row 4; `tech-spec.md` §3.14
- **Checklist:** CHECK-S12

### V-006: `00` §3.1 credits the canonical section with carrying the Standard Verify Gate; the gate lives in a different top-level section
- **Severity:** inconsistency
- **Location:** `00-core-definitions.md` §3.1, the sentence following the clause-location
  table: "The section does additionally carry the Standard Verify Gate and the recovery path
  in its `### Clean-room unavailable, or a non-answer` subsection"
- **Issue:** `references/stage-exit-protocol.md` § "Host and capability determination" spans
  from its heading to `## Branch ownership: the \`owner:\` token`, and contains exactly one
  subsection, `### Clean-room unavailable, or a non-answer` — which carries the **recovery
  path** only. The **Standard Verify Gate** is `### verifyGate: "standard"` under the
  separate top-level `## Directive contract` section. The capability section merely refers
  to it ("Interactive gate options keep their explicit labels … (below)").

  The claim is inherited from PRD REQ-GUARD-01's v2 note. OQ-02's resolution is a recorded
  decision and is not being reopened — but the supporting fact stated in the suite's shared
  vocabulary document is wrong, and `02` §2 builds its confirm-and-complete scope on §3.1's
  current-state description.
- **Suggested fix:** In `00` §3.1 replace the sentence with: "The section additionally
  carries the recovery path in its `### Clean-room unavailable, or a non-answer` subsection
  and the `host`-is-not-a-proxy rule. The Standard Verify Gate itself lives in the same file
  under `## Directive contract` → `### verifyGate: \"standard\"`, which the capability
  section references rather than restates." Confirm `02` §2's scope statement does not
  depend on the gate being inside the section (it does not — the six clauses are the scope).
- **References:** `references/stage-exit-protocol.md` §§ "Host and capability determination",
  "Directive contract"; PRD REQ-GUARD-01 note; `02-canon-and-prose-guard.md` §2.2–§2.3
- **Checklist:** CHECK-S15

### V-007: `03` §11 points the derived suite total at `07` §8; the total is in `07` §5.4
- **Severity:** inconsistency
- **Location:** `03-machinery-trim.md` §11, derived-figures note: "`07-testing-strategy.md`
  §8's suite total derives from this table in turn."
- **Issue:** `07` §8 is "What This Feature Does Not Test" (the declared non-goals list). The
  suite total lives in `07` §5.4, and the per-file effect table it feeds is `07` §5.2. A
  reader following the REQ-TRIAL-06 recompute chain from `03` §11 lands on the wrong section
  and finds nothing to recompute — which is the exact propagation failure the note exists to
  prevent.
- **Suggested fix:** Change the sentence to "`07-testing-strategy.md` §5.2 and §5.4 derive
  from this table in turn."
- **References:** `07-testing-strategy.md` §5.2, §5.4, §7.6; `03-machinery-trim.md` §12
- **Checklist:** CHECK-S15

### V-008: `01` §9's checkbox names "seven host files"; §4.2 names four
- **Severity:** inconsistency
- **Location:** `01-architecture-layout.md` §9, sixth checkbox: "The seven REQ-COV tests
  exist in the **seven host files** named in §4.2, each reusing that file's own CLI wrapper."
- **Issue:** `01` §4.2's placement map has seven **rows** but four distinct **files**:
  `tests/test_auto_verify.py` (REQ-COV-01, -04), `tests/test_state_verbs.py` (REQ-COV-02,
  -05, -06), `tests/test_compliance_eval.py` (REQ-COV-03), `tests/test_stage_exit.py`
  (REQ-COV-07). `05` §1.1 and `05` §11 both correctly say "four host files". A verifier
  executing `01` §9 literally will look for three files that do not exist.
- **Suggested fix:** Change the checkbox to "The seven REQ-COV requirements each have at
  least one named test, in the host file §4.2 assigns it (four files in total), each reusing
  that file's own CLI wrapper."
- **References:** `01-architecture-layout.md` §4.2; `05-coverage-backfill.md` §1.1, §11
- **Checklist:** CHECK-S15

### V-009: `05` §1.1 says "seven tests"; its own table names ten, and `07` §5.4 counts ten
- **Severity:** inconsistency
- **Location:** `05-coverage-backfill.md` §1.1, opening sentence: "The backfill is **not one
  file** — it is seven tests across four host files"
- **Issue:** The table immediately below names **ten** test functions (REQ-COV-01 → 2,
  REQ-COV-06 → 3, the remaining five → 1 each). `07` §5.4's stated assumption 1 depends on
  exactly that count: "The backfill contributes 10 collected items — one per named function
  (`05-coverage-backfill.md` covers the seven gaps with ten named tests)". `01` §4.2 has
  seven rows, one per requirement, which is likely where the "seven" came from.

  Because `07` §5.4's `+10` is a derived cell sourced from this document, the mismatched
  prose is a live risk to the count table under REQ-TRIAL-06 — a later edit that "fixes"
  ten to seven would silently move the expected suite total.

  Related sub-point in the same sentence's neighbourhood: `05` §3.2, §7.2's parametrized
  tests will collect **more** than one item each (§3.2 collects 2, §7.2's roster collects 5),
  so the `+10` figure counts **named functions**, not collected items — `07` §5.2's row is
  labelled "10 named functions" but `07` §5.4's arithmetic block adds them to a *collected*
  total. See the suggested fix.
- **Suggested fix:**
  1. `05` §1.1: change "it is seven tests across four host files" to "it is **ten named
     tests across four host files**, covering the seven gaps".
  2. `07` §5.4 assumption 1: the assumption already says "If any backfill test is
     parametrized, this rises; recompute §5.2 and §5.4 together" — `05` §3.2 (2 ids) and
     §7.2 (5 ids) **are** parametrized as specified, so discharge the assumption now rather
     than leaving it conditional: state the collected contribution explicitly
     (`05` §3.2 → 2, §7.2 first test → 5, the other eight named functions → 1 each) and
     carry the resulting number into §5.2's `REQ-COV backfill` row and §5.4's arithmetic.
     Recompute §5.4's total in the same edit as V-001's correction.
- **References:** `05-coverage-backfill.md` §1.1, §3.2, §7.2, §11;
  `07-testing-strategy.md` §5.2, §5.4; `01-architecture-layout.md` §4.2
- **Checklist:** CHECK-S37

### V-010: the detection-strength figures (20/34, 12/34, 24/34) state no reproducible measurement procedure
- **Severity:** improvement
- **Location:** `00-core-definitions.md` §6.2 (variant comparison table) and §6.4;
  `03-machinery-trim.md` §9 ("Detection is measured by removing each site's *own* mandate
  and asking whether the guard still reports that site")
- **Issue:** The **decision** these figures support — accept weaker per-site discrimination
  in exchange for removing every tuned integer — is a declared boundary (`00` §6.4,
  `07` §8) and is **not** being reopened here; detection-strength parity is explicitly not
  claimed and this finding does not ask for it.

  What is not reproducible is the *procedure*. "Removing each site's own mandate" is
  undefined when a region contains more than one mandate, which is the whole subject of the
  measurement. The only mechanical realization of "remove this site's own mandate" the
  suite ships — `03` §6's `_without_the_probe_mandate` — yields a materially different
  census when applied per-site across canon (32/34 for the adopted variant, against the
  stated 20/34), because it strikes every in-region mandate outside the call's own block.
  A reader therefore cannot reproduce, audit, or re-derive the residual after a canon edit,
  and `00` §9's "re-measure, never re-estimate" rule has no procedure to re-measure with.

  This is filed as `improvement`, not a blocker: the adopted design, the rejection of the
  call-line variant, and the recorded residual all stand on the reproducible facts
  (34/34 green; the call-line variant's 1 false failure — both re-verified here).
- **Suggested fix:** Add to `03` §9 a two-sentence statement of the exact procedure the
  figures were produced by — for each of the 34 sites, which lines were struck (own lead-in
  prose only? the whole region outside the block? the call-line-bounded neighbourhood?),
  and whether sites carrying `--epic` inside their own fence (there are 2) count as
  detected, undetected, or excluded. Alternatively, if the procedure cannot be recovered,
  replace the three figures with the qualitative statement they support — "the adopted
  bound discriminates per-site less finely than the call-line bound and more finely than the
  heading-only bound; the residual is not enumerated" — and drop the numerals from `00`
  §6.2's table, keeping its "Green on canon" column (34/34, 34/34, 33/34), which **is**
  reproducible and which I re-verified.
- **References:** `03-machinery-trim.md` §6, §9; `00-core-definitions.md` §6.2, §6.4, §6.5,
  §9; `07-testing-strategy.md` §8
- **Checklist:** CHECK-S36

### V-011: `05` §3.2 ships an unresolved authoring WARNING that `00` §10.5 already answers
- **Severity:** inconsistency
- **Location:** `05-coverage-backfill.md` §3.2, the paragraph after the test body:
  "`pytest` is already imported in `tests/test_state_verbs.py`? **WARNING: Could not confirm
  a top-level `import pytest` in `tests/test_state_verbs.py` — verify it exists (and add it
  if not) before implementing the `@pytest.mark.parametrize` decorators in §3.2, §6.2 and
  §7.2.**"
- **Issue:** This is an unretracted note-to-self left in a shipped specification, phrased as
  an open question. `00` §10.5 already resolves it definitively and in the opposite
  direction — "`tests/test_state_verbs.py` does not import `pytest` and uses no
  `parametrize` today. Verified: zero occurrences of the token in the file. Any work that
  adds a `@pytest.mark.parametrize` there … **must add `import pytest`**" — which I
  re-verified against the tree. Leaving a "could not confirm" in `05` invites the
  implementer to re-derive a fact the suite has already established, and leaves the import
  addition looking conditional when it is mandatory.
- **Suggested fix:** Replace the whole paragraph with a directive: "**`tests/test_state_verbs.py`
  does not import `pytest` today** (`00-core-definitions.md` §10.5). The
  `@pytest.mark.parametrize` decorators in §3.2, §6.2 and §7.2 therefore require
  `import pytest` to be added to that module's import block; omitting it is a
  collection-time `NameError` that presents as the whole file vanishing from the run. Every
  other module-level import these tests need (`json`, `subprocess`, `sys`, `Path`, `FS`,
  `validate_state`) is already present." Cross-check that `06-brittleness-batch.md` §10's
  import list carries the same obligation so the two documents do not both defer it.
- **References:** `00-core-definitions.md` §10.5; `05-coverage-backfill.md` §1.3, §6.2,
  §7.2; `06-brittleness-batch.md` §10; `07-testing-strategy.md` §1
- **Checklist:** CHECK-S10, CHECK-S35

---

## Fix Execution Plan

### User Decisions Required

- **V-010 only.** The fixer must choose between (a) recovering and documenting the exact
  detection-measurement procedure, or (b) replacing the three numerals with the qualitative
  statement and keeping only the reproducible "green on canon" column. Either discharges the
  finding; (b) is cheaper and does not reopen the declared boundary. Every other finding has
  a single determined fix.

  **RESOLVED 2026-08-03 — option (b).** Replace the three numerals with the qualitative
  statement; keep `00` §6.2's "Green on canon" column (34/34, 34/34, 33/34), which is
  reproducible. The declared boundary in `00` §6.4 and `07` §8's non-goal entry are not
  reopened.

- **V-004 — RESOLVED 2026-08-03: the finding is refuted; Step 4 is NOT applied.** Step 4's
  own action requires re-confirming through `check-spec-purity.py`'s slice. Re-measured
  through `read_frontmatter` + `body_start_line` **and** `check_body_size`'s trailing-empty
  drop (`scripts/check-spec-purity.py`, the `if body_lines and body_lines[-1] == ""` guard),
  the live figures are `forge-0-epic` **295** lines / **+5** headroom and `forge-verify`
  **299** / **+1** — exactly what `01` §3.1 already states. V-004's 296 / 300 are the slice
  lengths *before* that drop; both files end in a newline, so `str.split("\n")` yields a
  trailing `""` element that `check_body_size` discards. The matching word counts (2749,
  4365) confirm the same slice with only that difference. Applying Step 4 would write an
  off-by-one into a correct table. `01` §3.1 is left unchanged.

All other fixes can be applied directly.

### Execution Steps

#### Step 1: Correct `_VERB_INVOCATIONS` and every figure derived from it
- **Files:** `specs/verify-test-debt/07-testing-strategy.md`,
  `specs/verify-test-debt/TRACEABILITY.md`
- **Addresses:** V-001
- **Action:** Apply the seven edits enumerated in V-001's suggested fix, **in one edit
  pass** (REQ-TRIAL-06). Before editing, re-confirm the input with
  `python3 -c "import sys; sys.path.insert(0,'tests'); import test_state_verbs as m; print(len(m._VERB_INVOCATIONS))"`
  — it must print `8`. Do not touch `00` §9's rosters; they are correct and are the source
  §5 derives from.
- **Depends on:** none

#### Step 2: Fix the region mutation control and its acceptance criterion
- **Files:** `specs/verify-test-debt/03-machinery-trim.md`
- **Addresses:** V-002
- **Action:** In §6, replace `_without_the_probe_mandate`'s span computation with the
  structure-derived version given in V-002's suggested fix (keeping the `assert removed`
  guard, `_region_probe_site`, and `test_deleting_a_call_sites_own_epic_mandate_is_reported`
  unchanged), and add the fourth "property" bullet stating that the strike span must never
  be taken from `_region_bounds`. Leave §13's REQ-TRIM-04 checkbox as written — the
  corrected control satisfies it.
- **Depends on:** none

#### Step 3: Correct the naive-heading-scan rationale and its verification instruction
- **Files:** `specs/verify-test-debt/00-core-definitions.md`,
  `specs/verify-test-debt/03-machinery-trim.md`
- **Addresses:** V-003
- **Action:** Apply the four edits in V-003's suggested fix (`00` §6.3; `03` §4.2, §4.8
  table row, §13 REQ-TRIM-03 checkbox). **Keep `_fence_flags` and `_heading_lines` exactly
  as specified** — only the justification and the checkbox change.
- **Depends on:** Step 2 (same file, `03`; apply after so the §6 rewrite is settled)

#### Step 4: Correct the measured body-size figures
- **Files:** `specs/verify-test-debt/01-architecture-layout.md`
- **Addresses:** V-004
- **Action:** Set the two body-line cells to 296 and 300 and the headroom cells to "+4
  lines" and "0 lines"; rewrite the following sentence per V-004. Re-confirm first with
  `check-spec-purity.py`'s own `read_frontmatter` + `body_start_line` slice, not with a raw
  file-line count.
- **Depends on:** none

#### Step 5: Retire the superseded parametrize claim and the unresolved WARNING
- **Files:** `specs/verify-test-debt/00-core-definitions.md`,
  `specs/verify-test-debt/05-coverage-backfill.md`
- **Addresses:** V-005, V-011
- **Action:** Rewrite `00` §1's parametrize bullet and `05` §1.3's trailing clause per
  V-005; replace `05` §3.2's WARNING paragraph with the directive form per V-011. Then grep
  the suite for any remaining "established idiom in all three files" / "every file this
  feature touches" phrasing and bring it into line.
- **Depends on:** Step 3 (`00` is edited there too; sequence to avoid overlapping hunks)

#### Step 6: Repair the four cross-references and counts
- **Files:** `specs/verify-test-debt/00-core-definitions.md`,
  `specs/verify-test-debt/01-architecture-layout.md`,
  `specs/verify-test-debt/03-machinery-trim.md`,
  `specs/verify-test-debt/05-coverage-backfill.md`,
  `specs/verify-test-debt/07-testing-strategy.md`
- **Addresses:** V-006, V-007, V-008, V-009
- **Action:** `00` §3.1 — rewrite the Standard-Verify-Gate sentence (V-006). `03` §11 —
  retarget the derived-figure pointer to `07` §5.2/§5.4 (V-007). `01` §9 — rewrite the
  "seven host files" checkbox (V-008). `05` §1.1 — "ten named tests across four host files"
  (V-009), and discharge `07` §5.4's assumption 1 by carrying the parametrized collection
  counts into §5.2 and §5.4.
- **Depends on:** Step 1 (V-009's second half edits the same §5.2/§5.4 cells Step 1
  rewrites — apply Step 1's arithmetic first, then fold the backfill collection counts in,
  and recompute the total once)

#### Step 7: Address the detection-figure reproducibility gap
- **Files:** `specs/verify-test-debt/00-core-definitions.md`,
  `specs/verify-test-debt/03-machinery-trim.md`
- **Addresses:** V-010
- **Action:** Apply whichever option the user selected. Do **not** change the adopted
  variant, the declared boundary in `00` §6.4, or `07` §8's non-goal entry — this step
  edits how the residual is *described*, never whether it is accepted.
- **Depends on:** Step 3 (both files), and the user decision above

#### Step 8: Re-verify the arithmetic end to end
- **Files:** none (verification only)
- **Addresses:** V-001, V-009
- **Action:** After Steps 1 and 6, re-derive `07` §5.4's block from `00` §9's rosters and
  §5.1's measured inputs by hand and confirm it closes. Confirm `07` §5.2, §5.3, §5.4, §10
  and `03` §11 all carry the same numbers. This is the check the equivalent tech-spec table
  failed six times.
- **Depends on:** Steps 1, 6

---

## Fix Progress

- Step 1: [APPLIED] 2026-08-03 — V-001. Re-measured the input before editing:
  `len(_VERB_INVOCATIONS)` is **8** (`state-enter`, `state-artifact`, `state-complete`,
  `state-branch`, `state-note`, `state-decision`, `state-ecr`, `state-verify`);
  `test_state_schema_conformance.VERB_INVOCATIONS` is 8 as well. Corrected `07` §5.1's
  measured-input row (9 → 8, "How obtained" → `measured — matches tech-spec.md §8.2`),
  §5.3's corrupt-file collected cell (15 → **14**, `1 + 5 + 8`) and total row (56 → **55**),
  §5.3's divergence-note prose ("loops 9 registered verbs" → **8**), §5.2's `REQ-BRIT-07
  dedup` row (56 / +43 → **55** / **+42**), §5.4's arithmetic block and total, and §10's
  collection checkbox. `TRACEABILITY.md` correction row 4: the `_VERB_INVOCATIONS` clause is
  struck and replaced with "8 entries, as `tech-spec.md` §8.2 states — re-measured, no
  correction needed"; the parametrize/`import pytest` half of the row is accurate and stays.
  `00` §9's rosters were not touched. (§5.2/§5.4 are revised once more in Step 6 to fold in
  V-009's collected counts; the end-state figures are Step 8's.)

- Step 2: [APPLIED] 2026-08-03 — V-002. Executed the specified algorithm against live canon
  before editing, and the report reproduces exactly. With the span taken from `site.bounds`:
  fence-block bound → `removed=1`, probe reported at line 386, control passes; heading-only
  degradation → `removed=2`, probe **still** reported (sites 373 and 386), control **still
  passes** — so it cannot detect the widening `03` §13 requires it to catch. Replaced
  `_without_the_probe_mandate`'s span computation with the structure-derived version
  (`_fence_flags` / `_heading_lines` / `_call_blocks` inline, never `_region_bounds`), with
  the explanatory comment. Re-executed the replacement: fence-block → `removed=1`, probe
  reported (passes); heading-only → `removed=1`, probe **not** reported (goes green), which
  is what §13's REQ-TRIM-04 checkbox requires. Added the fourth "property" bullet stating
  the strike span must never be sized by the function under test. `assert removed`,
  `_region_probe_site`, `test_deleting_a_call_sites_own_epic_mandate_is_reported`, the
  `before` baseline, and §13's checkbox are unchanged; "region" → "lead-in" in the two
  docstring/message phrases the narrowed span made inaccurate.

- Step 3: [APPLIED] 2026-08-03 — V-003. Executed the scan against live canon under both
  heading modes: **34 sites, 0 misses under each**, and the two § Git Commit Protocol
  `state-complete` calls resolve to identical bounds `(323, 352)` either way — the "2 false
  failures" claim does not reproduce under the adopted fence-block bound. Replaced the
  empirical claim with the structural one in `00` §6.3 and `03` §4.2, rewrote `03` §4.8's
  second table row, and replaced `03` §13's REQ-TRIM-03 checkbox with the directly
  performable form (`_heading_lines(lines, _fence_flags(lines))` returns no fence-flagged
  index). `_fence_flags` and `_heading_lines` are unchanged, as the step requires.

- Step 4: [NOT APPLIED] 2026-08-03 — V-004 refuted by re-measurement; user-confirmed skip.
  The step's own action requires re-confirming through `check-spec-purity.py`'s slice rather
  than a raw line count. Measured through `read_frontmatter` + `body_start_line` **and**
  `check_body_size`'s trailing-empty drop (the `if body_lines and body_lines[-1] == ""`
  guard): `forge-0-epic` = **295** lines / **+5** headroom, `forge-verify` = **299** /
  **+1** — exactly what `01` §3.1 already states. V-004's 296 / 300 are the slice lengths
  *before* that drop; both files end in a newline, so `str.split("\n")` yields a trailing
  `""` the gate discards. Matching word counts (2749, 4365) confirm the same slice with only
  that difference. `01` §3.1 left unchanged; applying the step would have written an
  off-by-one into a correct table.

- Step 5: [APPLIED] 2026-08-03 — V-005, V-011. Re-verified against the tree:
  `tests/test_state_verbs.py` has zero `parametrize` occurrences and no `import pytest` in
  its import block. Rewrote `00` §1's parametrize bullet to name the three files where the
  idiom is established and to carry the `import pytest` obligation, and `05` §1.3's trailing
  clause likewise. Replaced `05` §3.2's unresolved WARNING with the directive form. Swept
  the suite for the superseded phrasings: the only remaining occurrences are in `07` §1 and
  `06` §8.4's *correction notes*, which supersede the claim and are correct as written, and
  in upstream `tech-spec.md`, which this stage does not edit. Two refinements over the
  suggested text: the directive names **§3.2 and §7.2** rather than the finding's "§3.2,
  §6.2 and §7.2" — §6.3 is REQ-COV-05's test section and carries no decorator, and a grep
  confirms only two `@pytest.mark.parametrize` sites in `05`; and it records that the import
  lands in this document, not `06`, because `05` §1.3 sequences `05` first (`06` §10 lists
  the same addition for REQ-BRIT-07).

- Step 6: [APPLIED] 2026-08-03 — V-006, V-007, V-008, V-009. `00` §3.1: the Standard Verify
  Gate sentence now credits the capability section with the recovery path and the
  `host`-is-not-a-proxy rule only, and points the gate itself at `## Directive contract` →
  `### verifyGate: "standard"`; `02` §2's scope statement was checked and does not depend on
  the gate's location (the six clauses are the scope). `03` §11: derived-figure pointer
  retargeted from `07` §8 to `07` §5.2 and §5.4. `01` §9: the "seven host files" checkbox
  now reads "seven REQ-COV requirements … (four files in total)". `05` §1.1: "ten named
  tests across four host files, covering the seven gaps". Discharged `07` §5.4's assumption
  1 rather than leaving it conditional: `05` §3.2 collects 2 ids and `05` §7.2's first test
  collects 5 (the `_UNSAFE_ARTIFACT_PATHS` roster), the other eight functions 1 each, so the
  backfill contributes **15** collected across 10 named functions. Carried that into §5.2's
  row (+15) and §5.4's arithmetic. `05` §11's placement checkbox was checked and is already
  correct.

- Step 7: [APPLIED] 2026-08-03 — V-010, user decision **(b)**. Dropped the "Self-mutation
  detection" column (20/34, 12/34, 24/34) from `00` §6.2, keeping the reproducible "Green on
  canon" column (34/34, 34/34, 33/34), and stated the per-site ordering qualitatively with
  the reason no census is given. Rewrote `00` §6.4 and `03` §9's detection-strength paragraph
  to record the residual without enumerating it, naming why the procedure is not
  recoverable: the only shipped realization (`03` §6's `_without_the_probe_mandate`) strikes
  every in-region mandate outside the call's own block and yields a materially different
  census than a rule striking only the call's own lead-in. Removed the trailing numerals
  from `03` §4.8 and `07` §8's non-goal entry. The adopted variant, `00` §6.4's declared
  boundary, and `07` §8's non-goal itself are unchanged — only how the residual is described.
  Recorded the divergence from upstream as `TRACEABILITY.md` correction rows **11** (the
  withdrawn figures) and **12** (the false-failure claim from Step 3), since both supersede
  statements in `tech-spec.md` §3.5/§8, which this stage does not edit.

- Step 8: [APPLIED] 2026-08-03 — verification only, no file changed by the step itself.
  Re-derived `07` §5.4 independently from `00` §9's rosters and §5.1's measured inputs:
  hash `5 → 36` (2×3 + 3×10), corrupt-file `3 → 14` (1 + 5 + 8), gate `5 → 5`, dedup
  `13 → 55` (**+42**), backfill **15** (2 + 5 + 8×1); `1842 − 39 − 60 − 1 + 15 + 42 =
  **1799**`. The block closes. The pass caught one straggler — §5.4 assumption 2 still ended
  "lands at 1794" — which was corrected to 1799 with the reason (the backfill's parametrized
  ids, per assumption 1) named. §5.2, §5.3, §5.4 and §10 now all carry the same numbers, and
  `03` §11 points at §5.2/§5.4. A repo-wide grep for `1794`, `1795`, `13 → 56`, `20/34`,
  `12/34`, `24/34`, `2 false failures`, `seven host files` and `seven tests across four`
  returns nothing in the stage artifacts; the only hits are the two TRACEABILITY correction
  rows that deliberately quote the superseded figures, and upstream `tech-spec.md`.

**Gates run after the pass.** `check-spec-purity.py`: **PASS**, 0 violations.
`scripts/validate.sh`: 1 error, the **pre-existing** traceability orphan baseline
(`REQ-DEBT-04`, `REQ-REL-01`, `REQ-STATE-01`) that this report's own "What is correct"
section records as quotations of existing docstrings per `TRACEABILITY.md` § Coverage
Verification. `git diff` confirms this pass touches none of those three ids, so the error is
unchanged by it, not introduced by it.
