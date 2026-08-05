# Verification Report: verify-test-debt (specs) — RE-VERIFY, round 2
Date: 2026-08-03
Pipeline Stage: forge-3-specs (version 1); `forge-verify-specs` = `findings-applied`
Fix delta confirmed: `d7304389066ec8b56e58f42c95f2094c4a19ede5`
Prior report: `.verification/VERIFY-specs-v1-2026-08-03.md` (11 findings)
Artifacts Reviewed (scoped to the fix delta and the prior findings' acceptance evidence):
`00-core-definitions.md`, `01-architecture-layout.md`, `03-machinery-trim.md`,
`05-coverage-backfill.md`, `07-testing-strategy.md`, `TRACEABILITY.md`, plus the unedited
`02-canon-and-prose-guard.md` §2.4/§2.5 and `06-brittleness-batch.md` §8.3/§10 that the
delta cross-references; live repo: `tests/test_state_verbs.py`,
`tests/test_state_schema_conformance.py`, `tests/test_state_verb_call_sites.py`,
`tests/test_stage_exit_protocol.py`, `tests/test_capability_determination_prose.py`,
`tests/test_stage_exit.py`, `tests/test_auto_verify.py`, `tests/test_compliance_eval.py`,
`references/shared-conventions.md`, `references/stage-exit-protocol.md`,
`scripts/check-spec-purity.py`, `scripts/validate-traceability.py`.

## Scope of this run

This is a **re-verify under `references/stage-exit-protocol.md` § "Re-verify scope and
convergence"**, not a fresh 38-check sweep. Two things were done and nothing else:

1. Each of the prior report's 11 findings was confirmed against **its own acceptance
   evidence** — its "Suggested fix" text and the `## Fix Progress` entry recording what was
   done — re-measured against the live tree rather than taken on trust.
2. The fix delta (`git show d7304389066ec8b56e58f42c95f2094c4a19ede5`, 6 spec files) and
   what those changed lines directly touch were examined for defects the fix itself
   introduced.

**Decisions cited, never re-filed:** V-010 (user decision, option (b) — replace the
unreproducible detection numerals with a qualitative statement; `00` §6.4's declared
boundary and `07` §8's non-goal entry not reopened) and V-004 (recorded refutation +
explicit user decision to skip Step 4). `00` §10.3 / `07` §8 declared non-goals and every
`TRACEABILITY.md` correction row are recorded positions.

## Verification method notes

- Every symbol was located **by name**; no line-number citation was used to find anything.
- `03` §6's mutation control was **executed against live canon**, in the specified form and
  in the pre-fix form, under both `_region_bounds` variants. Four executions, reported in
  full below (§ "Executed: `03` §6's control").
- `07` §5.4 was **re-derived independently** from `00` §9's rosters and §5.1's measured
  inputs, with every measured input re-measured by `pytest --collect-only` or module import.
- The structural block scan was re-run against canon under fence-aware **and** naive heading
  indices, and under fence-block **and** heading-only bounds — four combinations.

## Summary
- Total findings: 1
- Gaps: 0
- Inconsistencies: 0
- Improvements: 1
- Errors: 0
- **Blocking (errors + gaps): 0 — advisory-only. The report records `passed` with this file
  attached; the pipeline advances.**

**Convergence verdict.** No prior finding is unresolved, and the fix delta introduced no
blocking defect. Under the convergence rule the single `improvement` below is recorded and
does **not** flip the outcome. This run does **not** close as `reverify-findings`.

---

## Disposition of the 11 prior findings

| ID | Severity (prior) | Disposition | Evidence |
|---|---|---|---|
| V-001 | error | **RESOLVED** | `len(_VERB_INVOCATIONS)` re-measured = **8**; all seven derived cells corrected and mutually consistent. |
| V-002 | error | **RESOLVED** | Control executed against live canon: PASSES under the adopted bound, GOES GREEN under the heading-only degradation — §13's REQ-TRIM-04 checkbox is now satisfiable. |
| V-003 | inconsistency | **RESOLVED** | Scan executed: 34/34 green under both heading modes; the "2 false failures" claim is gone from `00` §6.3, `03` §4.2, `03` §4.8; §13's REQ-TRIM-03 checkbox is now directly performable and true. |
| V-004 | inconsistency | **IMMUNE (recorded decision)** | Refuted and skipped by explicit user decision. Refutation reasoning re-checked, not the finding. |
| V-005 | inconsistency | **RESOLVED** | `00` §1 and `05` §1.3 rewritten; the three named files re-measured as parametrize users, `test_state_verbs.py` re-measured at 0 uses / 0 `import pytest`. |
| V-006 | inconsistency | **RESOLVED** | `00` §3.1 rewritten; gate location independently confirmed in `references/stage-exit-protocol.md`. |
| V-007 | inconsistency | **RESOLVED** | `03` §11's derived-figure pointer now reads `07` §5.2 and §5.4. |
| V-008 | inconsistency | **RESOLVED** | `01` §9's checkbox now says "seven REQ-COV requirements … (four files in total)". |
| V-009 | inconsistency | **RESOLVED** | `05` §1.1 says "ten named tests across four host files"; `07` §5.4 assumption 1 discharged at 15 collected, verified against `05` §3.2 and §7.2. |
| V-010 | improvement | **IMMUNE (recorded decision)** | Discharged under user option (b); numerals withdrawn, ordering stated qualitatively, `TRACEABILITY` row 11 records the supersession. |
| V-011 | inconsistency | **RESOLVED** | `05` §3.2's WARNING replaced with the directive; the narrowing to §3.2/§7.2 independently confirmed correct. |

### V-001 — RESOLVED

Input re-measured (not read from the fix log):

```
tests/test_state_verbs.py            _VERB_INVOCATIONS  -> 8 keys
tests/test_state_schema_conformance.py VERB_INVOCATIONS -> 8 keys
```

Keys: `state-enter`, `state-artifact`, `state-complete`, `state-branch`, `state-note`,
`state-decision`, `state-ecr`, `state-verify`.

Every dependent cell checked, by name:

| Location | Now reads | Correct? |
|---|---|---|
| `07` §5.1 measured-inputs row | **8** entries, "measured — matches `tech-spec.md` §8.2" | yes |
| `07` §5.3 corrupt-file collected | `3 → **14**` (`1 + 5 + 8`) | yes |
| `07` §5.3 total row | `13 → **55**` | yes (36 + 14 + 5) |
| `07` §5.3 divergence prose | "loops **8** registered verbs" | yes |
| `07` §5.2 `REQ-BRIT-07 dedup` row | 13 items → **55** → **+42** | yes |
| `07` §5.4 arithmetic block | `+42 REQ-BRIT-07 dedup (13 → 55 collected)` | yes |
| `07` §5.4 assumption 2 | 8 entries; corrupt-file expansion **+11**; lands at **1799** | yes (14 − 3 = 11; 7 verb-loop + 4 epic-loop = 11) |
| `07` §10 collection checkbox | "lands near **1799**" | yes |
| `TRACEABILITY.md` row 4 | `_VERB_INVOCATIONS` clause struck, parametrize half retained | yes |

Repo-wide grep across the stage artifacts for `1795`, `1794`, `1781`, `13 → 56`, `20/34`,
`12/34`, `24/34`, `2 false failures`, `seven host files`, `seven tests across` returns hits
**only** in `TRACEABILITY.md` rows 11 and 12, which deliberately quote the superseded
figures as the record of the supersession. `06-brittleness-batch.md` §8.3 states no verb
cardinality of its own — it explicitly delegates the derived function-count figure to `07`
under REQ-TRIAL-06 — so no unedited document carries a stale 9.

### V-002 — RESOLVED (executed, not inspected)

See § "Executed: `03` §6's control" below. Both required executions were run against live
`references/shared-conventions.md`; canon was never written (the probe reads and mutates an
in-memory copy). The added fourth "property" bullet in `03` §6 is present and states the
rule the fix depends on.

### V-003 — RESOLVED

Executed against live canon, all four combinations of {fence-block, heading-only} bound ×
{fence-aware, naive} heading index:

```
canon bound=block    naive_headings=False:  34 sites, 0 missing
canon bound=block    naive_headings=True :  34 sites, 0 missing
canon bound=heading  naive_headings=False:  34 sites, 0 missing
canon bound=heading  naive_headings=True :  34 sites, 0 missing
```

The two `state-complete` sites in § Git Commit Protocol resolve to **identical** bounds
`(323, 352)` — 1-indexed lines 344 and 348. The two bash comments are at 1-indexed **343**
and **347**, i.e. inside the call-bearing block, so `00` §6.3's and `03` §4.2's new
structural rationale ("satisfy neither `index < first` nor `index > last`") is
literally true of the live file. `03` §13's replacement REQ-TRIM-03 checkbox is directly
performable and passes: `_heading_lines(lines, _fence_flags(lines))` returns **no** index
that `_fence_flags` marks `True` (empty set on `shared-conventions.md`).
`_fence_flags` / `_heading_lines` are unchanged in the delta, as Step 3 required.

### V-005 / V-011 — RESOLVED, including the narrowing

Re-measured:

| File | `parametrize` occurrences | top-level `import pytest` |
|---|---|---|
| `test_stage_exit.py` | 70 | yes |
| `test_state_schema_conformance.py` | 8 | yes |
| `test_auto_verify.py` | 6 | yes |
| **`test_state_verbs.py`** | **0** | **no** |

**The fix's narrowing is correct.** `05` carries exactly **two** `@pytest.mark.parametrize`
decorator sites: one in §3.2 ("The test", REQ-COV-02) and one in §7.2 ("The tests",
REQ-COV-06). §6.2 is "What is and is not already covered" (prose); REQ-COV-05's test is in
§6.3 and carries **no** decorator. The original WARNING's "§3.2, §6.2 and §7.2" was itself
a mis-citation; naming §3.2 and §7.2 is the accurate set. The cross-check V-011's fix asked
for also holds: `06` §10's import table carries `tests/test_state_verbs.py | import pytest |
REQ-BRIT-07 (§8.2, §8.3)`, and `05` §1.3 does sequence `05` before `06`, so the new
"the import lands here, not there" sentence is consistent with both documents.

### V-006 — RESOLVED

Independently confirmed against `references/stage-exit-protocol.md`:
`## Host and capability determination` runs to `## Branch ownership: the `owner:` token` and
contains exactly one subsection, `### Clean-room unavailable, or a non-answer`. The Standard
Verify Gate is `### verifyGate: "standard" — the Standard Verify Gate` under the separate
top-level `## Directive contract`. The `host`-is-not-a-proxy rule ("**Do not use
`host == claude` as a capability proxy.**") *is* inside the capability section, so `00`
§3.1's new sentence is accurate in both halves.

`02` §2's scope statement was re-checked and does **not** depend on the gate's location:
§2.4 quotes canon's own sentence ("The full determination rule, the Standard Verify Gate,
and the recovery path live in `references/stage-exit-protocol.md`"), which names the
**file**, not the section — verified verbatim in `shared-conventions.md`. No consequential
edit is owed to `02`.

### V-007, V-008, V-009 — RESOLVED

- `03` §11's derived-figures note now reads "`07-testing-strategy.md` §5.2 and §5.4 derive
  from this table in turn."
- `01` §9's checkbox now reads "The seven REQ-COV requirements each have at least one named
  test, in the host file §4.2 assigns it (four files in total) …".
- `05` §1.1 reads "**ten named tests across four host files**, covering the seven gaps",
  and its own table enumerates exactly ten named tests (2 + 1 + 1 + 1 + 1 + 3 + 1) across
  `test_auto_verify.py`, `test_state_verbs.py`, `test_compliance_eval.py`,
  `test_stage_exit.py`. `05` §11's placement checkboxes agree ("four existing host files").
- `07` §5.4 assumption 1 is discharged rather than left conditional, and the collected
  contribution was verified at source: `05` §3.2's decorator carries `ids=["zero",
  "negative"]` → **2**; `05` §7.2's `_UNSAFE_ARTIFACT_PATHS` is a 5-row tuple used as
  argvalues → **5**; the other eight named functions carry no decorator → **1** each.
  2 + 5 + 8 = **15**, matching §5.2's row and §5.4's arithmetic.

---

## Executed: `03` §6's control against live canon

The §4 helpers (`_fence_flags`, `_heading_lines`, `_call_blocks`, `_region_bounds`,
`_sites_in`, `CallSite`) and §6's `_region_probe_site` / `_without_the_probe_mandate` were
implemented **verbatim from the spec text** in a scratch module, with
`CALL_RE = re.compile(r'forge-session\.py"?\s+(state-[a-z]+)')` taken from
`tests/test_state_verb_call_sites.py`. Canon (`references/shared-conventions.md`) was read
only; the mutation is applied to an in-memory copy.

`03` §13's REQ-TRIM-04 checkboxes require: the control **passes** under the adopted bound,
and **fails** when `_region_bounds`'s lower bound is degraded to the enclosing heading
alone (i.e. Guard 1 goes green — the probe is no longer reported, so the control's
`assert probe_line in after` blows).

**The specified (post-fix) control — strike span computed from document structure:**

| `_region_bounds` variant | probe line | probe `block` | probe `bounds` | strike span | `removed` | reported sites after mutation | control verdict |
|---|---|---|---|---|---|---|---|
| fence-block (adopted) | 386 | (382, 387) | (375, 389) | **(375, 389)** | **1** | `{386}` | **PASSES** — probe reported |
| heading-only (the degradation) | 386 | (382, 387) | (353, 389) | **(375, 389)** — unchanged | **1** | `{}` | **FAILS — probe NOT reported** |

Both §13 criteria are satisfied. The strike span does **not** move when `_region_bounds`
widens, which is exactly what the new property-4 bullet claims.

**The pre-fix control, for contrast — strike span taken from `site.bounds`:**

| `_region_bounds` variant | strike span | `removed` | reported sites after | verdict |
|---|---|---|---|---|
| fence-block (adopted) | (375, 389) | 1 | `{386}` | passes |
| heading-only (the degradation) | **(353, 389)** — widened in lockstep | **2** | `{373, 386}` | **still passes — the old checkbox was unsatisfiable** |

This reproduces the prior round's V-002 diagnosis exactly and confirms the fix is the thing
that changed the outcome, not an artifact of my harness. The `before` baseline is empty
(`{}`) in every run, so the `assert not before` guard in
`test_deleting_a_call_sites_own_epic_mandate_is_reported` holds on current canon.

Canon was byte-identical afterwards (`git status --porcelain references/` clean).

---

## Re-derived: `07` §5.4 closes at 1799

Every input re-measured against the live tree, then the block recomputed by hand.

**Measured inputs (`07` §5.1):**

| Input | Re-measured | Method |
|---|---|---|
| Suite collected today | **1842** | `pytest tests --collect-only -q` |
| `_ACCEPTED_HASHES` | **3** | module import |
| `_REJECTED_HASHES` | **10** | module import |
| `_VERB_INVOCATIONS` | **8** | module import |
| epic corrupt-state loop | **5** shapes | `00` §9.3 / `06` §8.3.2's `_CORRUPT_EPIC_STATES` |
| gate-selection unparametrized | **5** functions | `00` §9.4 (6 sites, 1 already parametrized) |

**Per-file baselines (`07` §5.2 "Before" column):**

```
tests/test_capability_determination_prose.py -> 43 collected
tests/test_state_verb_call_sites.py          -> 10 collected
tests/test_stage_exit_protocol.py            -> 102 collected  (= 67 + 18 + 17)
```

**Dedup family, from `00` §9's rosters (`07` §5.3):**

| Family | Functions | Collected before | Collected after | Derivation |
|---|---|---|---|---|
| 40-hex hash | 5 → 5 | 5 | **36** | 2 loops × `_ACCEPTED_HASHES` (3) + 3 loops × `_REJECTED_HASHES` (10) = 6 + 30 |
| corrupt-file | 3 → 3 | 3 | **14** | 1 (no loop) + 5 (epic shapes) + 8 (`_VERB_INVOCATIONS`) |
| gate selection | 5 → 1 | 5 | **5** | one parametrized function over the 5 unparametrized sites |
| **total** | 13 → 9 | **13** | **55** | delta **+42** |

**The block:**

```
1842  collected today                         (measured)
 −39  prose guard          (43 → 4)
 −60  mutation controls    (67 → 7)
  −1  call-sites guard     (10 → 9)           (−2 deleted §5.2, +1 control §6)
 +15  REQ-COV backfill     (2 + 5 + 8×1)
 +42  REQ-BRIT-07 dedup    (13 → 55)
────
1799  expected
```

1842 − 39 = 1803; − 60 = 1743; − 1 = 1742; + 15 = 1757; + 42 = **1799**. ✔

**Agreement across the four sites that must carry the same numbers:**

| Site | Carries |
|---|---|
| `07` §5.2 | dedup 13 → **55** / **+42**; backfill **15** collected (10 named functions) / **+15** |
| `07` §5.3 | corrupt-file `3 → 14 (1 + 5 + 8)`; total `13 → 55` |
| `07` §5.4 | `+15` / `+42` / total **1799**; assumption 2's `+11` |
| `07` §10 | "Suite collection lands near **1799**" |
| `03` §11 | points at `07` §5.2 and §5.4 (V-007), and its own before-column (67/18/17/10) matches §5.2's |

All consistent. This is the table that failed six times at the tech-spec stage; it closes.

---

## Gates

| Gate | Result |
|---|---|
| `scripts/check-spec-purity.py` | **PASS — 0 violations across canonical surfaces** |
| `scripts/validate-traceability.py PRD.md specs/verify-test-debt/` | 46 requirements, **0 uncovered**, **3 orphaned** — `REQ-DEBT-04`, `REQ-REL-01`, `REQ-STATE-01`, the **pre-existing** baseline recorded in `TRACEABILITY.md` § Coverage Verification as quotations of existing docstrings. Unchanged by the fix delta; **not a finding.** |
| `pytest tests --collect-only` | 1842 collected — the §5.1 baseline is still current. |

---

## Findings

### V-012: `00` §1's parametrize-idiom enumeration omits `test_compliance_eval.py`
- **Severity:** improvement (advisory — does **not** flip the outcome)
- **Location:** `00-core-definitions.md` §1, "Project conventions this feature follows
  without deviation" → the `@pytest.mark.parametrize` bullet (rewritten by the fix delta,
  V-005 Step 5)
- **Issue:** The bullet now reads "the established idiom in `test_stage_exit.py`,
  `test_state_schema_conformance.py`, and `test_auto_verify.py`". That three-file list
  replaced the superseded "every file this feature touches", which is the correct direction —
  but the feature also touches `tests/test_compliance_eval.py` (REQ-COV-03, `05` §4), and
  that file uses `@pytest.mark.parametrize` in 14 places. A reader checking the bullet
  against the tree finds a fourth established user that the list does not name, which
  slightly undercuts the bullet's own "nothing here introduces a new convention"
  justification for that file.
  This is **not** an error and nothing derives from it: the bullet's load-bearing claim —
  that `tests/test_state_verbs.py` is the **exception** and needs `import pytest` added
  with the first decorator — is exactly right and was re-measured (0 uses, no import). No
  count, no test, and no gate reads this sentence.
- **Suggested fix:** In `00` §1, extend the list to "`test_stage_exit.py`,
  `test_state_schema_conformance.py`, `test_auto_verify.py`, and `test_compliance_eval.py`",
  or replace the enumeration with "every file this feature touches **except**
  `tests/test_state_verbs.py`". Keep the bolded `test_state_verbs.py` sentence verbatim.
  `05` §1.3 needs no change — it no longer enumerates.
- **References:** `00-core-definitions.md` §10.5; `05-coverage-backfill.md` §1.3, §4;
  `tests/test_compliance_eval.py`
- **Checklist:** CHECK-S12

---

## New defects introduced by the fix delta

**None.** Every changed hunk was word-diffed and its claim re-checked against the live tree:

- `07` §5.1/§5.2/§5.3/§5.4/§10 — all seven V-001 cells plus the two V-009 cells recomputed
  independently; the block closes at 1799 and no straggler carries an old figure.
- `03` §6 — the new span computation was **executed**, not read; it satisfies both §13
  checkboxes. Its inlined helpers (`_fence_flags`, `_heading_lines`, `_call_blocks`) are all
  in module scope in the same document (§4.2, §4.3), all three are used, and no import is
  added, so no ruff-unused-import risk (`01` §7's gate).
- `03` §6's "region" → "lead-in" rewording in the docstring and the `assert removed` message
  is *more* accurate after the narrowing, not less: the strike span is now the probe's own
  lead-in irrespective of `_region_bounds`.
- `00` §6.2's table lost a column; the remaining two-column table is well-formed and its
  "Green on canon" figures (34/34, 34/34, 33/34) were re-verified by execution.
- `00` §6.4 / §6.5 stay internally consistent: §6.5's tunability argument still explicitly
  disclaims parity ("Detection strength is a **separate axis** and is weaker (§6.4)"), and
  §6.4 no longer states a numeral that §6.2 does not support.
- `TRACEABILITY.md` rows 11 and 12 are correctly scoped to `tech-spec.md` supersessions —
  the upstream artifacts are untouched, as this stage requires.
- Nothing in the delta touches `REQ-DEBT-04`, `REQ-REL-01`, or `REQ-STATE-01`, so the
  orphan baseline is unchanged by it.

---

## Fix Execution Plan

### User Decisions Required

None. This report is **advisory-only** — it contains no `error` and no `gap`, so no fix
round is fenced and no decision is owed. V-012 may be applied opportunistically by whoever
next edits `00` §1; leaving it is also a complete answer.

### Execution Steps

#### Step 1 (optional): Extend `00` §1's parametrize-idiom enumeration
- **Files:** `specs/verify-test-debt/00-core-definitions.md`
- **Addresses:** V-012
- **Checklist:** CHECK-S12
- **Action:** In §1's `@pytest.mark.parametrize` bullet, change the file list to name
  `test_compliance_eval.py` as well (or replace the enumeration with "every file this
  feature touches **except** `tests/test_state_verbs.py`"). Leave the bolded
  `tests/test_state_verbs.py` / `import pytest` sentence byte-identical — it is V-005's
  resolution and is correct.
- **Depends on:** none
- **Rationale:** One sentence, one file, zero derived figures. Deliberately not bundled
  with anything else because nothing else is owed.

---

## Fix Progress

_(No fix pass is required. This section is left empty deliberately — the report is
advisory-only and the stage advances.)_
