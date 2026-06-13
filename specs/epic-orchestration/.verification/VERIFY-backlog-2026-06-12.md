# Verification Report: epic-orchestration (backlog)
Date: 2026-06-12
Pipeline Stage: forge-5-loop (forge-4-backlog complete)
Artifacts Reviewed: specs/epic-orchestration/backlog.json (19 items); PRD.md; tech-spec.md; 00–05 implementation specs; 01-architecture-layout.md §1 file inventory; 04-pipeline-integration.md section headers; TRACEABILITY.md. Dispatched as 4 parallel forge-verifier instances (scoping/AC, dependency-ordering, spec-coverage, schema-enum) + the rauf CLI validator.

## Summary
- Total findings: 5
- Gaps: 0
- Inconsistencies: 0
- Improvements: 5
- Errors: 0

**Authoritative cross-check:** `rauf backlog validate . --backlog specs/epic-orchestration --specs-dir specs --json` → exit 0, `{"valid": true, "findings": []}`. Schema, enums, required fields, ID sequencing, dependsOn DAG, and spec-coverage all pass deterministically. No blocking issues — every finding below is a refinement.

## Findings

### V-001: Item 010 bundles all 13 test subsections into one ~2-iteration item
- **Severity:** improvement
- **Location:** backlog.json item `010` (`description`, `estimatedIterations`, `acceptanceCriteria`)
- **Issue:** Item 010 authors `tests/test_epic_manifest.py` covering the entire matrix §3.1–§3.13 (round-trip, schema/cached-status, cyclic + self-dep, dup-name/ambiguous, corrupt-json, path-escape, status-derivation all five branches + live-edit, atomic-write + interrupt-safety, render-status derived sets, dangling-dep, resolve flat/nested/not-found, 20-feature perf, full exit-code table) plus asserting every FindingCode in 00 §4 is produced. It is the largest single unit by surface area and is flagged `estimatedIterations: 2`. A single rauf iteration that must keep the whole suite green risks partial completion. This is over-scoping, not a correctness error — its dependency structure (depends only on 009) is sound.
- **Suggested fix:** Optionally split along a natural seam: 010a "structural/validation tests" (§3.1–§3.6, §3.10, §3.13 exit-code table + FindingCode coverage for corrupt-json/schema/cached-status/dup/dangling/cycle/unsafe/path-escape/not-found/ambiguous) and 010b "status-derivation + render-status + atomic/interrupt + perf" (§3.7–§3.9, §3.11, §3.12). Both `dependsOn: ["009"]`; item 011 then `dependsOn` both. Acceptable to keep whole for a transcribe-from-spec task — this is a user decision, not a mandated change.
- **References:** 05-testing-strategy.md §3.1–§3.13, §6; backlog items 009, 011
- **Checklist:** CHECK-B11, CHECK-B25

### V-002: Item 012 spans both forge-0-epic branches (C1–C8 + E1–E6) in one ~2-iteration item
- **Severity:** improvement
- **Location:** backlog.json item `012` (`description`, `estimatedIterations`)
- **Issue:** Item 012 authors the whole `skills/forge-0-epic/SKILL.md` — creation branch (C1–C8), edit branch (E1–E6), observability/commit (§8), and the error-handling table (§9), at `estimatedIterations: 2`. It is a single new file so it cannot be split by file; the 2-iteration estimate is honest.
- **Suggested fix:** Acceptable to keep as one item. If finer granularity is wanted, split into 012a (frontmatter + Step 0 dispatch + creation branch C1–C8 + EPIC.md/member subdirs) and 012b (edit branch E1–E6 + §8 observability + §9 error table), with 012b `dependsOn: ["012a"]`. User decision.
- **References:** 03-forge-0-epic-stage.md (whole), §6, §8, §9; skills/forge-1-prd/SKILL.md (style reference)
- **Checklist:** CHECK-B11, CHECK-B25

### V-003: Item 011's last acceptance criterion is not a runnable verification command
- **Severity:** improvement
- **Location:** backlog.json item `011` (`acceptanceCriteria[4]`)
- **Issue:** Item 011 edits `scripts/validate.sh`. The convention across all 18 other code-change items is that the LAST acceptance criterion is a runnable verification command. Item 011's last AC is the prose assertion "The new step is the last among the checks; existing steps are unchanged" — checkable by reading but not a command. A runnable check ("bash scripts/validate.sh passes WITH pytest installed…") exists but is `acceptanceCriteria[1]`, not last.
- **Suggested fix:** Reorder so the runnable-command criterion is the final array element, or append a final `"bash scripts/validate.sh passes"` element. Keep the "new step is last / existing steps unchanged" assertion as a non-final criterion.
- **References:** convention established by items 001–010, 012–019; 05-testing-strategy.md §5
- **Checklist:** CHECK-B13

### V-004: Item 008 declares a spurious `dependsOn` on 007 (render-status)
- **Severity:** improvement
- **Location:** backlog.json item `008`, field `dependsOn` (`["006","007"]`) and `notes`
- **Issue:** Item 008's mutator envelope is `assert_safe_name → load_manifest → apply edit → _validate_dict (006) → _bump_and_write → atomic_write`. It uses `_validate_dict` (006) and the 003-scaffolded primitives, but never calls `render_status` or any artifact from item 007. The `notes` claim mutators "re-use _validate_dict(006)+render-status(007)" — render-status is not referenced in the mutator logic. The 007 edge is over-constraining (harmless to correctness since 007 precedes 008 in the chain, but it delays 008's actionability and the note is misleading).
- **Suggested fix:** Change item 008 `dependsOn` to `["006"]`. Update item 008 `notes` to drop "+render-status(007)" — mutators re-use `_validate_dict` from 006 only. (003's `load_manifest`/`atomic_write`/`assert_safe_name` are transitively guaranteed via 006's closure and need not be listed.)
- **References:** item 006 (`_validate_dict`), item 003 (load_manifest/atomic_write/assert_safe_name), item 007 (render_status — unused by 008)
- **Checklist:** CHECK-B18, CHECK-B19

### V-005: 01-architecture-layout.md §1.2 modified-files table mis-cites 04 section numbers
- **Severity:** improvement
- **Location:** 01-architecture-layout.md §1.2 (Modified files table, "Spec doc" column) — a SPEC file, not the backlog
- **Issue:** Surfaced while building the spec-coverage map. The §1.2 table cites wrong 04-pipeline-integration.md subsections: forge-4-backlog "§5" (actual §6), forge-5-loop "§6" (actual §7), forge/SKILL.md "§7" (actual §8), forge-6-docs "§8" (actual §10), forge-verify/SKILL.md "§8" (actual §9), verification-checklists.md "§8" (actual §9.5), forge-fix "§5" (actual §11.1). The backlog items themselves (015 §6, 016 §7, 017 §8, 018 §9, 019 §10/§11.1) cite correctly, so coverage/traceability are intact — this is a stale internal cross-reference in the architecture spec only and does not affect backlog correctness.
- **Suggested fix:** Update the §1.2 "Spec doc" column: forge-4-backlog→04 §6; forge-5-loop→04 §7; forge/SKILL.md→04 §8; forge-6-docs→04 §10; forge-verify/SKILL.md→04 §9; verification-checklists.md→04 §9.5; forge-fix→04 §11.1; forge-researcher.md→04 §11.2. Note: this edits a spec already marked verified; the parent may defer it as out-of-scope for a backlog-mode fix.
- **References:** 04-pipeline-integration.md section headers; backlog items 015–019 (cite correctly)
- **Checklist:** CHECK-B-REF-RELEVANT (adjacent traceability)

## Coverage Map (reference, not a finding)
- New files (01 §1.1): epic-manifest-schema.json→001; pipeline-state-schema patch→002; epic-manifest.py→003–008; tests/conftest.py+fixtures→009; test_epic_manifest.py→010; validate.sh wiring→011; forge-0-epic/SKILL.md→012. **All covered.**
- Modified files (01 §1.2): shared-conventions.md→013; pipeline-state-schema.json→002; forge-config-schema.json→correctly NOT a backlog item ("no change required"); forge/SKILL.md→017; forge-1/2/3→014; forge-4→015; forge-5→016; forge-6→019; forge-verify/SKILL.md→018; forge-fix→019; verification-checklists.md→018; forge-researcher.md→014; validate.sh→011. **All covered; no orphaned deliverable; no item invents unbacked work.**

## Fix Execution Plan

### User Decisions Required
- **V-001 (split item 010)** and **V-002 (split item 012)** — both are over-scoping judgment calls on transcribe-from-spec items with honest 2-iteration estimates. Decide per item whether to split or leave whole. Splitting adds dependency-graph re-numbering churn, so do not split without confirmation.
- **V-005** edits an already-verified spec (01-architecture-layout.md), not the backlog. Decide whether to apply now or defer as out-of-scope for a backlog fix pass.

### Execution Steps

Apply in order. Each step is self-contained.

#### Step 1: Remove spurious 007 dependency from item 008 (no decision needed)
- **Files:** specs/epic-orchestration/backlog.json (item 008)
- **Addresses:** V-004
- **Checklist:** CHECK-B18, CHECK-B19
- **Action:** Set item 008 `dependsOn` to `["006"]` (remove `"007"`). In item 008 `notes`, change the phrase "re-use _validate_dict(006)+render-status(007)" to "re-use _validate_dict(006)" (render-status is unused by any mutator). Re-run `rauf backlog validate` to confirm exit 0.
- **Depends on:** none

#### Step 2: Reorder item 011 acceptance criteria (no decision needed)
- **Files:** specs/epic-orchestration/backlog.json (item 011)
- **Addresses:** V-003
- **Checklist:** CHECK-B13
- **Action:** Move the runnable-command criterion ("bash scripts/validate.sh passes WITH pytest installed and actually runs python3 -m pytest tests (PASS line shown)") to be the final element of `acceptanceCriteria`, OR append a new final element `"bash scripts/validate.sh passes"`. Preserve all existing criteria.
- **Depends on:** none

#### Step 3: (conditional) Split item 010
- **Files:** specs/epic-orchestration/backlog.json
- **Addresses:** V-001
- **Action:** Only if the user approves. Split 010 into 010a/010b along the §3.1–§3.6/§3.10/§3.13 vs §3.7–§3.9/§3.11/§3.12 seam; both `dependsOn: ["009"]`; update item 011 to `dependsOn` both new IDs. Renumber subsequent IDs only if necessary; prefer suffixed IDs to avoid mass renumber. Re-run `rauf backlog validate`.
- **Depends on:** user decision

#### Step 4: (conditional) Split item 012
- **Files:** specs/epic-orchestration/backlog.json
- **Addresses:** V-002
- **Action:** Only if the user approves. Split into 012a (creation branch + EPIC.md + member subdirs) and 012b (edit branch + observability + error table); 012b `dependsOn: ["012a"]`. Re-run `rauf backlog validate`.
- **Depends on:** user decision

#### Step 5: (conditional) Correct §1.2 spec-section citations
- **Files:** specs/epic-orchestration/01-architecture-layout.md
- **Addresses:** V-005
- **Action:** Only if the user opts to fix the spec now. In the §1.2 Modified files table, replace the "Spec doc" cells per the mapping in V-005's suggested fix.
- **Depends on:** user decision
- **Rationale:** Edits an already-verified spec; grouped last so the backlog-only fixes (Steps 1–2) can be applied and committed independently.
