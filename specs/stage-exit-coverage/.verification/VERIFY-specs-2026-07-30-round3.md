# Verification Report: stage-exit-coverage (specs) — Round 3

Date: 2026-07-30
Pipeline Stage: forge-3-specs (re-verify after `e2959c1` mechanical fixes and `302c93f` lock removal / PRD v3)
Mode: specs, require-clean

## Summary

- Checks executed: 38 of 38 — 34 pass, 4 fail, 0 not-applicable
- Total findings: 5 — 1 gap, 1 error, 3 improvements
- **All 10 round-2 findings resolved** (4 by removal of the lock protocol, 6 by the mechanical fixes)
- Round-1 V-006 resolved by recording the position in the PRD rather than specifying a mechanism

Independent validator run: `valid: true`, 55 requirements, 8 spec files, 0 uncovered, 0 orphaned.
Confirmed separately: 55 bolded requirement definitions, 55 unique `REQ-*` tokens, sets identical,
no duplicates, no stray foreign-feature citation (the `epic-orchestration` reference in REQ-REL-04
cites §4.2 by section, never by ID). TRACEABILITY matrix: 55 rows, IDs identical to the PRD.

## Lock-Removal Excision: Clean

Verified mechanically across all 11 documents — word-boundary grep for `lock|lease|locking|lockfile`,
`LOCK_`, `.json.lock`, `_acquire_state_lock`, `_release_state_lock`, "critical section",
"optimistic-version", "mutual exclusion", "contention". The only survivors are the three intentional
*negative* statements (PRD REQ-REL-04, `03` §3.2, TRACEABILITY row 55). `03` now runs §1–§10 with
§3.1–§3.4 then §4 — no §3.5. Zero broken section citations across all 11 documents (script-verified:
heading index per file against every `NN-name.md §N` / `tech-spec.md §N` / `PRD.md §N` citation,
including ranges and comma lists). `.gitignore` appears zero times in the spec set.

## REQ-REL-04 Assessment

Both load-bearing external claims verify verbatim against source: `scripts/forge-session.py:1907`
`_write_state` docstring contains "Concurrent multi-session mutation is out of scope (single writer
assumed, matching epic-manifest.py)", and `specs/epic-orchestration/PRD.md` §4.2 **is** "Robustness"
with REQ-ROBUST-03 stating the atomicity-not-mutual-exclusion position. The requirement is
well-grounded and the position is **defensible**; it should not be reopened in this feature. One
residual exposure recorded as improvement R3-V-003.

## Check Results

- **Pass (34):** S01–S05, S07, S09–S13, S15–S37 except those listed below
- **Fail (4):** CHECK-S06 (R3-V-004), CHECK-S08 (R3-V-002), CHECK-S14 (R3-V-002), CHECK-S38 (R3-V-001, R3-V-005)
- **Not applicable:** none

## Findings

### R3-V-001: REQ-REL-04 had no verification coverage
- **Severity:** gap · **Checklist:** CHECK-S38, CHECK-S36
- **Location:** `07-testing-strategy.md` Requirement Coverage table, §4.3; `TRACEABILITY.md` row 55
- **Issue:** REQ-REL-04 (P0) was wired into the PRD, `03`, and TRACEABILITY, but the string
  `REQ-REL-04` did not occur anywhere in `07-testing-strategy.md`. Because `07` §8.1 scopes its
  acceptance criterion to "every PRD requirement **in this document's table**", a P0 requirement
  carried zero verification obligation. `validate-traceability.py` cannot detect this — it only
  checks that an ID appears in some spec file, and `TRACEABILITY.md` counts as one.

### R3-V-002: The guard's exclusion allow-list named a phantom skill and omitted a real one
- **Severity:** error · **Checklist:** CHECK-S08, CHECK-S14, CHECK-S04
- **Location:** `06-compliance-and-coverage.md` §2.1, `INTENTIONALLY_EXCLUDED_SKILLS`
- **Issue:** The set named `forge-update`, which does not exist anywhere in the repository outside
  that one spec line, and omitted `forge-bootstrap`, which is a real skill that PRD REQ-GUARD-02 and
  tech-spec §3.10 both name by category ("navigator, setup, bootstrap, and advisory"). Predates
  round 1. The §2.1 assertion "every excluded identifier is absent from the covered table" is
  vacuously true for a phantom id.

### R3-V-003: REQ-REL-04's "no threat model established" is falsifiable at the epic root
- **Severity:** improvement · **Checklist:** CHECK-S27
- **Location:** `PRD.md` §4.1 REQ-REL-04; `03-verification-state.md` §3.2
- **Issue:** The single-writer position holds for every in-session scenario — auto-verify chains,
  nested verify → fix → re-verify, and the rauf loop are strictly sequential, and member
  `.pipeline-state.json` files are disjoint. One residual case is worth recording: two sessions on
  *different members of one epic* share `epic-manifest.json` (whose `revision` this feature makes
  load-bearing via a read-modify-write increment in `_bump_and_write`) and `.epic-state.json`. A lost
  increment would not merely drop an edit — it could leave `revision` unchanged after a semantic
  mutation landed, and `03` §5.2 would then classify a stale epic verification as `fresh`. The
  exposure is inherited (epic-orchestration REQ-ROBUST-03 already scoped manifest writes out), but
  this feature widens the shared surface by one file and raises the blast radius from "lost edit" to
  "false freshness". **No mechanism recommended in this feature** — record the candidate and defer.

### R3-V-004: tech-spec §2.1 omitted `scripts/forge-bootstrap.py`
- **Severity:** improvement · **Checklist:** CHECK-S06, CHECK-S07
- **Location:** `tech-spec.md` §2.1 `scripts/` block
- **Issue:** The same document requires modifying it in §3.9, §6.2, and §6.4. `01` §2 lists it
  correctly, so no implementer is misled — the two file maps simply disagreed by one row.

### R3-V-005: `01`'s coverage table cited a `REQ-PORT` family that does not exist in this PRD
- **Severity:** improvement · **Checklist:** CHECK-S38
- **Location:** `01-architecture-layout.md` Requirement Coverage table, final row
- **Issue:** `REQ-PORT` is a real family in `context-efficiency` and `forge-bootstrap`, but not here;
  the row was shorthand for PRD §5 *Constraints*. Malformed enough that a fresh agent would grep for
  `REQ-PORT-01` and find nothing.

## Round-2 Findings: Disposition

| ID | Status |
|---|---|
| R2-V-001 wrong field value domains | Resolved |
| R2-V-002 reclaimed lock / lost update | Resolved by removal |
| R2-V-003 held-region overstated | Resolved by removal |
| R2-V-004 lock governs 8 verbs, one acquisition point | Resolved by removal |
| R2-V-005 nonexistent `.gitignore` path | Resolved |
| R2-V-006 §4.3 lock tests unexecutable | Resolved by removal |
| R2-V-007 `02` API drops `pi` from `--host` | Resolved |
| R2-V-008 mock policy attributed to §9 | Resolved |
| R2-V-009 duplicate allow-lists | Resolved |
| R2-V-010 branch fixture path | Resolved |

## Observations (not findings)

- **Raised to the human, outside specs scope:** this feature's `.pipeline-state.json` had `notes` as
  an array of `{at, note}` objects, but `references/pipeline-state-schema.json` declares
  `notes: {"type": "string"}` and `cmd_state_note` assigns a bare string. The **spec set is correct**;
  the state file was hand-authored. Fixed during this round — see Fix Progress.
- Verified correct despite looking suspicious: `_VERIFY_RESOLVED` includes `findings-applied` while
  `00` §6 says it "remains unresolved". Consistent — `verify_state()` lets a resolved entry fall
  through to the freshness comparison, and with `verifiedStageVersion` deleted it returns `stale`.
- Verified: `skills/forge-5-loop/SKILL.md` is 302 lines / 4,512 words (body 296 / 4,446) — both under
  the ≤300 / ≤5,000 caps `04` §6.3 claims.
- All 54 fenced Python blocks parse. All 29 externally cited paths exist. All quoted "exact existing
  signatures" match current source.
- REQ-CAP-01's bare `references/runner-contract.md` path not re-reported, per the round-2 judgment —
  agreed, since `01` §2 and `04` §6.3 both pin the skill-local path as sole source.

## Fix Progress

- Step 1: [APPLIED] 2026-07-30 — R3-V-001. `07` coverage table row is now `REQ-REL-01..04` naming the
  preserved single-writer model; §4.3's heading cites `REQ-REL-04`; a new "Single-writer model
  preserved" block asserts the writers acquire no lock, lease, or version guard, that the atomic
  sequence is exactly temp → fsync → `os.replace` with no extra sibling file and no retry/backoff,
  and that a future change adding mutual exclusion must amend REQ-REL-04 first. `TRACEABILITY.md`
  row 55 left as-is — its §4.3 citation is now correct.
- Step 2: [APPLIED] 2026-07-30 — R3-V-002. `INTENTIONALLY_EXCLUDED_SKILLS` is now
  `{forge, forge-bootstrap, forge-guide, forge-init}`; the prose names which REQ-GUARD-02 category
  each covers; and a new assertion requires every excluded id to resolve to an existing
  `skills/<id>/SKILL.md` so the set cannot rot into phantom entries again.
- Step 3: [APPLIED] 2026-07-30 — R3-V-004. `forge-bootstrap.py` added to tech-spec §2.1's `scripts/`
  block; the two layout maps now agree.
- Step 4: [APPLIED] 2026-07-30 — R3-V-005. Final `01` coverage row is now `| PRD §5 constraints |`,
  inventing no REQ id. (`REQ-PORT` remains legitimate in `context-efficiency` and `forge-bootstrap`,
  which define it; it was phantom only here.)
- Step 5: [APPLIED] 2026-07-30 — R3-V-003. PRD REQ-REL-04 and `03` §3.2 now name the deferred
  candidate explicitly: concurrent sessions on two members of one epic, the shared
  `epic-manifest.json` `revision` increment, and the false-freshness consequence via §5.2. Applied
  rather than deferred for decision because it records a position without introducing a mechanism —
  the same discipline REQ-REL-04 itself installs. No section, mechanism, or test changed.
- Step 6: [APPLIED] 2026-07-30 — Re-validated. `valid: true`, 55 requirements, 8 spec files, 0
  uncovered, 0 orphaned; matrix 55 rows; ID sets identical. `REQ-REL-04` now occurs 3× in `07`;
  `forge-update` occurs 0× repo-wide; `REQ-PORT` occurs 0× in this feature. `ruff` and
  `bash scripts/validate.sh` both green with `forge.config.json` at HEAD.
- Extra: [APPLIED] 2026-07-30 — Fixed the hand-authored schema violation the verifier flagged:
  `.pipeline-state.json` `notes` converted from an array of objects to the schema's single string.
  `tests/test_pipeline_state_schema.py` passes.
