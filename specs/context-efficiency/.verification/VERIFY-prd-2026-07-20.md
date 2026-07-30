# Verification Report: context-efficiency (prd)
Date: 2026-07-20
Pipeline Stage: forge-2-tech (PRD complete; verifying forge-1-prd output)
Artifacts Reviewed:
- specs/context-efficiency/PRD.md (subject)
- specs/context-efficiency/.reference/CHARTER.md (evidence base)
- specs/context-efficiency/.reference/AUDIT.md (evidence base)
- specs/context-efficiency/.reference/RECOMMENDATIONS.md (evidence base)
- specs/context-efficiency/.reference/LOAD-MAP.md (evidence base)
- specs/context-efficiency/.reference/GUARDRAILS.md (evidence base)
- forge-1-prd/references/prd-template.md (structure baseline)

Checks Executed: 15 of 15 (12 pass, 1 not-applicable [CHECK-P12], 2 pass-with-findings). Results: 12 pass, 0 fail, 1 not-applicable, plus 4 findings raised against otherwise-passing checks (all improvement/gap severity — no check hard-failed).

## Summary
- Total findings: 4
- Gaps: 2
- Inconsistencies: 0
- Improvements: 2
- Errors: 0

Overall: this is a strong, evidence-grounded PRD. All six recommendations (R1–R6) and all eight hard guardrails have corresponding requirements or constraints; every interview-settled decision (V1 scope = R1–R6; measure-first success basis; R4/R5 outcome-not-mechanism; dogfood + drift-guard acceptance; independently shippable/revertible delivery) is faithfully reflected. The findings below are refinements, not blockers.

## Findings

### V-001: Drift-guard requirement (REQ-MAINT-01) enumerates R1 but not R6's split or R4/R5's new script surface
- **Severity:** gap
- **Location:** PRD.md §4.4 REQ-MAINT-01; cross-ref §3.6 (R6), §3.4 (R4), §3.5 (R5)
- **Issue:** REQ-MAINT-01 requires the drift-guard discipline be "extended to cover every split/moved file" and then gives R1-specific detail (per-mode checklist CHECK-ID assertion + expected-count table) plus a generic invoke-point-citation clause. GUARDRAILS.md §4 lists drift-guard obligations for R1 and R7 explicitly, but R6 (the `runner-contract.md` → `agent-selection.md` split, §3.6) is itself a "split file" that produces a new citation-gated reference, and R4/R5 introduce new `forge-session.py` code paths whose contract with the schema (REQ-R4-03: schema remains CI source of truth) needs a guard that the helper output stays schema-conformant. The generic "every split/moved file / every new reference file is cited by ≥1 skill" clause technically reaches R6's `agent-selection.md`, but the requirement does not make R6's split or the R4/R5 helper↔schema conformance an explicit drift-guard obligation the way it does for R1. A tech-spec author could reasonably read REQ-MAINT-01 as R1-scoped.
- **Suggested fix:** In REQ-MAINT-01, add R6 and R4/R5 to the enumerated drift-guard obligations: (a) for R6, assert `agent-selection.md` is cited at the Step 2d capability gate and that the always-vs-conditional section split preserves every runner-contract section (mirror the R1 CHECK-ID-count assertion pattern); (b) for R4/R5, assert the `forge-session.py` helper output validates against `pipeline-state-schema.json` / `forge-config-schema.json` in CI, so REQ-R4-03's "schema remains source of truth" is test-enforced, not just asserted. Keep the generic invoke-point clause as the catch-all.
- **References:** GUARDRAILS.md §4 (drift-guard discipline), PRD.md REQ-R4-03, REQ-R6-02, REQ-PORT-01
- **Checklist:** CHECK-P08, CHECK-P14

### V-002: No requirement covers the `jsonschema`-absent / `ruff`-CI-only CI hazard for the R4/R5 helper code
- **Severity:** gap
- **Location:** PRD.md §5 C-2 (constraint) — no corresponding functional/NFR requirement
- **Issue:** GUARDRAILS.md §2 records two CI hazards that specifically bite the R4/R5 script-extraction work: `jsonschema` is absent in CI (new helper code must not hard-depend on it) and `ruff check scripts/ eval/` is CI-only (must be run locally before pushing helper changes). The PRD captures both in constraint C-2, which is the correct home for a "must respect" gate — so this is not a mis-placement. The gap is that C-2 bundles these under a general "CI gates" heading without tying the `jsonschema` prohibition to the R4/R5 requirements that create the risk, so a fresh tech-spec author reading §3.4/§3.5 in isolation would not see that "the preferred `forge-session.py` mechanism must not import `jsonschema` at runtime" is a hard acceptance constraint on those requirements. The `check-spec-purity.py` 300-line cap is correctly cross-linked (REQ-R6-03 Notes → Guardrail §2), but the helper-side CI constraints are not similarly cross-linked from R4/R5.
- **Suggested fix:** Add a Notes line to REQ-R4-02 and REQ-R5-02 pointing to C-2 ("the helper mechanism must not hard-depend on `jsonschema` (absent in CI) and must pass `ruff check scripts/ eval/`"), so the constraint is discoverable from the requirement it constrains. No new requirement text needed — just the cross-reference, matching the pattern REQ-R6-03 already uses.
- **References:** GUARDRAILS.md §2, PRD.md C-2, REQ-R4-02, REQ-R5-02
- **Checklist:** CHECK-P13, CHECK-P14

### V-003: Requirement IDs use a recommendation-numbered scheme (REQ-R1-NN) rather than a semantic-category scheme
- **Severity:** improvement
- **Location:** PRD.md §3.1–§3.6 (REQ-R1-* … REQ-R6-*)
- **Issue:** The template's ID convention is `REQ-{CAT}-NN` where CAT is a semantic capability category (e.g. `REQ-ERR-04`, `REQ-SEC-03`). The functional requirements here key off the recommendation number (`REQ-R1-01`, `REQ-R4-02`) rather than a capability noun, while the NFRs correctly use semantic categories (`REQ-PERF`, `REQ-BEHAV`, `REQ-OBS`, `REQ-MAINT`) and the cross-cutting ones use `REQ-DELIV`/`REQ-PORT`. This is internally consistent and every ID is unique and category-prefixed, so CHECK-P06 passes — but the `Rn`-keyed scheme couples the requirement ID to the audit's recommendation numbering, which means if the tech spec re-groups work (e.g. merges R4+R5 into one change), the IDs read as slightly stale. This is a readability/durability nit, not a correctness issue, and is arguably justified here because the recommendations *are* the capability areas for this meta-feature.
- **Suggested fix:** Optional. If durability past the audit's numbering matters, consider aliasing to semantic categories (e.g. `REQ-CHECKLIST-*` for R1, `REQ-PRELUDE-*` for R2, `REQ-STATEWRITE-*` for R4, `REQ-CONFIG-*` for R5, `REQ-RUNNERSPLIT-*` for R6). Otherwise leave as-is and note in the tech spec that `Rn` IDs are stable handles regardless of how the work is later batched. No action required for pipeline correctness.
- **References:** prd-template.md §3 ID convention, PRD.md §3
- **Checklist:** CHECK-P06

### V-004: REQ-PERF-02's "MUST NOT increase" bound is testable but names no measurement basis, unlike REQ-PERF-01/REQ-OBS-01
- **Severity:** improvement
- **Location:** PRD.md §4.1 REQ-PERF-02
- **Issue:** REQ-PERF-01 and REQ-OBS-01 carefully anchor their targets to a "freshly re-measured baseline at implementation time" with a recorded, reproducible measurement method (the measure-first decision). REQ-PERF-02 states the always-loaded surface (13 frontmatter descriptions, ~1.2k tokens) and the silent `SessionStart` hook MUST NOT increase — a good non-regression guard — but it cites the audit's static ~1.2k figure rather than tying to the same re-measured baseline, and it does not say *how* "did not increase" is verified (a byte/word count assertion, a test, or manual review). Given REQ-OBS-01 mandates recording the measurement method for the reduction targets, the non-increase guard should ride the same method so before/after is reproducible for both directions.
- **Suggested fix:** Reword REQ-PERF-02 to anchor to the same re-measured baseline and method as REQ-PERF-01/REQ-OBS-01 (e.g. "measured by the same method recorded under REQ-OBS-01"), and optionally point at a concrete check (frontmatter description char-count assertion; confirmation the hook's common-path output stays empty). This makes the guard a green/red test rather than a review judgment.
- **References:** PRD.md REQ-PERF-01, REQ-OBS-01, §8 SC-1; LOAD-MAP.md "Always loaded" table
- **Checklist:** CHECK-P05, CHECK-P08, CHECK-P11

## Check-by-check record

| Check | Result | Note |
|---|---|---|
| CHECK-P01 | pass | §1–§8 all present and populated per prd-template.md |
| CHECK-P02 | pass | No TBD/TODO; OQ-1..3 are tracked open questions, not placeholders |
| CHECK-P03 | pass | §6 lists R7, W1, W2, interactive behavior, frontmatter, hook, adapter behavior, release work — specific |
| CHECK-P04 | pass | OQ-1/2/3 each actionable with a named resolution path (dogfood evidence / tech spec) |
| CHECK-P05 | pass (see V-004) | SC-1/4/5/6 measurable; SC-2 explicitly non-gating (intentional per measure-first) |
| CHECK-P06 | pass (see V-003) | All IDs unique + category-prefixed; scheme is Rn-keyed for functional, semantic for NFR |
| CHECK-P07 | pass | Every REQ carries Priority P0/P1 |
| CHECK-P08 | pass | Requirements testable; REQ-R2-01 softness offset by "without changing execution behavior" |
| CHECK-P09 | pass | REQ-R4-02/REQ-R5-02 name forge-session.py but are explicitly preference-not-mandate with outcome as the requirement (C-4); the "labeled constraint with justification" escape clause is satisfied |
| CHECK-P10 | pass | Six personas cover every actor in the evidence base (pipeline user, verifier subagent, loop stage, maintainer, non-Claude-adapter maintainer, quality owner) |
| CHECK-P11 | pass | NFRs intentionally deferred to re-measured baselines (measure-first, REQ-OBS-01) — a defensible non-quantification, not a gap |
| CHECK-P12 | not-applicable | No security surface; host-neutrality (REQ-PORT-02) is the nearest analog and is explicit |
| CHECK-P13 | pass | C-4 explicitly labeled "preference, not mandate"; C-1/2/3/5/6/7 are MUSTs |
| CHECK-P14 | pass (raised V-001, V-002) | Two implicit obligations surfaced (R6/R4/R5 drift guards; helper CI constraints) |
| CHECK-P15 | pass | Core tension (token reduction vs zero-behavior-diff) is explicitly acknowledged and resolved via C-1 prime-directive + REQ-BEHAV-01/02 + flag-in-review discipline; no unresolved conflict |

## Coverage matrix (evidence base → PRD)

| Evidence item | PRD coverage | OK? |
|---|---|---|
| R1 checklist split | §3.1 REQ-R1-01..05 | yes |
| R2 prelude dedup | §3.2 REQ-R2-01..02 | yes |
| R3 conditional process-overview | §3.3 REQ-R3-01 | yes |
| R4 state-schema read | §3.4 REQ-R4-01..04 | yes |
| R5 effective-config | §3.5 REQ-R5-01..02 | yes |
| R6 runner-contract split | §3.6 REQ-R6-01..03 | yes |
| Guardrail §1 behavior preservation | C-1, REQ-BEHAV-01/02 | yes |
| Guardrail §2 CI gates (300-line cap / ruff / jsonschema) | C-2 (300-cap cross-linked at REQ-R6-03; jsonschema/ruff not cross-linked — V-002) | partial |
| Guardrail §3 adapter fan-out / host-neutral / gemini fixture | C-3, REQ-PORT-01/02/03 | yes |
| Guardrail §4 drift-guard discipline | REQ-MAINT-01 (R1 explicit; R6/R4/R5 under-specified — V-001) | partial |
| Guardrail §5 prelude within-file | C-5, REQ-R2-02 | yes |
| Guardrail §6 dual-role verifier guard | REQ-R1-03 | yes |
| Guardrail §7 measure first | C-6, REQ-OBS-01/02, SC-1/2 | yes |
| Guardrail §8 release mechanics | C-7 (backlog excludes release items) | yes |
| Interview: V1=R1–R6, R7/W1/W2 out | §6 Out of Scope | yes |
| Interview: measure-first % basis | SC-1 (per-rec, gating) + SC-2 (~30–35% aggregate, directional) | yes |
| Interview: R4/R5 outcome not mechanism | REQ-R4-02, REQ-R5-02, C-4 | yes |
| Interview: dogfood + drift-guard acceptance | SC-3, SC-4, REQ-BEHAV-01, REQ-MAINT-01 | yes |
| Interview: independently shippable/revertible | REQ-DELIV-01, SC-6 | yes |

## Fix Execution Plan

### User Decisions Required
- **V-003** (ID scheme) is optional and stylistic — decide whether recommendation-numbered IDs are acceptable as stable handles (recommended: leave as-is) before spending effort renaming. All other fixes are direct cross-reference/wording additions with no design decision.

### Execution Steps

Apply in order. Each step is self-contained.

#### Step 1: Tie the R4/R5 helper CI constraints to their requirements
- **Files:** specs/context-efficiency/PRD.md (§3.4 REQ-R4-02, §3.5 REQ-R5-02)
- **Addresses:** V-002
- **Checklist:** CHECK-P13, CHECK-P14
- **Action:** Add a Notes line to REQ-R4-02 and REQ-R5-02: "The helper mechanism MUST NOT hard-depend on `jsonschema` (absent in CI) and MUST pass `ruff check scripts/ eval/` (CI-only — run locally); see C-2." Do not move the constraint out of C-2 — this is a cross-reference only, mirroring REQ-R6-03's existing "Guardrail §2" note.
- **Depends on:** none
- **Rationale:** Makes the helper-side CI gate discoverable from the requirement that creates the risk, without duplicating the constraint.

#### Step 2: Extend REQ-MAINT-01 drift-guard scope to R6 and R4/R5
- **Files:** specs/context-efficiency/PRD.md (§4.4 REQ-MAINT-01)
- **Addresses:** V-001
- **Checklist:** CHECK-P08, CHECK-P14
- **Action:** After the R1-specific clause, add: (a) R6 — a drift guard asserting `agent-selection.md` is cited at the forge-5-loop capability gate and that the runner-contract always/conditional split preserves every original section; (b) R4/R5 — a drift guard asserting the `forge-session.py` helper output validates against `pipeline-state-schema.json` / `forge-config-schema.json` in CI (enforcing REQ-R4-03's "schema remains source of truth"). Retain the generic invoke-point-citation clause as the catch-all.
- **Depends on:** none
- **Rationale:** Closes the "only R1 is explicitly guarded" reading; keeps parity with GUARDRAILS.md §4 which the PRD otherwise mirrors.

#### Step 3: Anchor REQ-PERF-02 to the measure-first baseline/method
- **Files:** specs/context-efficiency/PRD.md (§4.1 REQ-PERF-02)
- **Addresses:** V-004
- **Checklist:** CHECK-P05, CHECK-P08, CHECK-P11
- **Action:** Reword REQ-PERF-02 to verify the non-increase "by the same method recorded under REQ-OBS-01," and (optionally) name a concrete check — a frontmatter description char-count assertion and confirmation the `SessionStart` common-path output stays empty.
- **Depends on:** none
- **Rationale:** Makes the non-regression guard a reproducible green/red test consistent with REQ-PERF-01/REQ-OBS-01, rather than a review judgment against a static audit figure.

#### Step 4 (optional): Reconsider requirement ID scheme
- **Files:** specs/context-efficiency/PRD.md (§3)
- **Addresses:** V-003
- **Checklist:** CHECK-P06
- **Action:** Only if the user opts in (see User Decisions Required): alias `REQ-Rn-*` functional IDs to semantic-category IDs. Otherwise add a one-line note that `Rn` IDs are stable handles independent of later work batching.
- **Depends on:** User decision
- **Rationale:** Purely stylistic/durability; not required for pipeline correctness.
