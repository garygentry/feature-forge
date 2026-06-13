# Verification Report: epic-orchestration (impl)
Date: 2026-06-13
Pipeline Stage: complete (final consistency re-verification)
Artifacts Reviewed: scripts/epic-manifest.py; references/{shared-conventions,epic-manifest-schema,pipeline-state-schema}; skills/{forge,forge-0-epic,forge-1-prd,forge-2-tech,forge-3-specs,forge-4-backlog,forge-5-loop,forge-6-docs,forge-verify,forge-fix}/SKILL.md; skills/forge-verify/references/verification-checklists.md; tests/test_epic_manifest.py + tests/fixtures/; specs/epic-orchestration/{PRD,tech-spec,00..05,TRACEABILITY}.md

Method: 4 parallel forge-verifier instances over disjoint dimensions — (1) requirement coverage, (2) integration correctness, (3) testing, (4) code quality/conventions.

## Suite Evidence
- `python3 -m pytest tests/ -q` → **51 passed in 2.73s** (zero failures).
- `bash scripts/validate.sh` → **All checks passed!** (step 7 confirms `py_compile` + the epic-manifest pytest suite are genuinely invoked).
- `python3 -m py_compile scripts/epic-manifest.py` passes; AST confirms **stdlib-only** (argparse, json, os, re, sys, tempfile, datetime, pathlib, typing).

## Summary
- Total findings: 8
- Gaps: 0
- Inconsistencies: 0
- Improvements: 7
- Errors: 1

**Overall:** Every P0/P1 requirement and every tech-spec §3.x decision traces to a concrete implementation (full REQ→impl map confirmed; TRACEABILITY 32/32). The deterministic core — acyclicity, atomic writes, path containment, bounded uniqueness globbing, single-source completion rule, live status derivation — is correct and robust under every fixture exercised. No correctness or security defect was found. All findings are low-severity polish; the single `error` is a latent, currently-harmless fixture bug.

## Findings

### V-001: tech-spec lists `forge.config.json` as a created deliverable, but it was never created
- **Severity:** improvement
- **Location:** tech-spec.md §2.2 (Modified files table, last row) and §2.4; vs. project root (no `forge.config.json`) and scripts/validate.sh:124–139.
- **Issue:** §2.2 lists `forge.config.json (new, this repo)` as a deliverable persisting `stack`/`testCommand`/`typeCheckCommand`, and §2.4 names validate.sh as a consumer that runs those commands. In reality the file does not exist and validate.sh hardcodes `python3 -m py_compile scripts/epic-manifest.py` and `python3 -m pytest …/tests`. The tech-spec marks these fields optional ("absence falls back to built-in defaults") and the pipeline operates correctly on defaults, so runtime behavior is correct by design — this is a spec-deliverable-vs-implementation mismatch, not a functional gap. No REQ-* behavior is unmet.
- **Suggested fix:** Prefer amending tech-spec §2.2/§2.4 to record that the file is intentionally deferred in v1 and the helper commands are hardcoded in validate.sh as the defaults. Alternatively, create `forge.config.json` with the three documented fields and have validate.sh source them with fallback.
- **References:** tech-spec.md §2.2, §2.4; scripts/validate.sh:124–139
- **Checklist:** CHECK-I01, CHECK-I05, CHECK-I11

### V-002: resolve-block exit-1 wording could mislead an agent into parsing JSON from a no-`--json` `resolve` call
- **Severity:** improvement
- **Location:** references/shared-conventions.md, "Feature Directory Resolution" block (exit-1 bullet, ~line 64).
- **Issue:** The canonical `resolve` invocation correctly omits `--json` (the subcommand has no such flag). The exit-1 bullet says "With `--json` this is a `{valid, findings[]}` envelope on stdout; otherwise a plain message." Verified runtime: a no-`--json` `resolve` writes the plain `not-found:`/`ambiguous:` finding to **stderr** with empty stdout. Four downstream render-status consumers (forge-5-loop, forge, forge-6-docs, Epic Context Injection) say "exit 1 → parse `{findings[]}` from stdout" — correct *for them* because they pass `--json`. The risk is purely that the terse resolve wording could be cross-applied to the render-status path.
- **Suggested fix:** Make the no-`--json` stream explicit, mirroring the exit-2 bullet: state that this `resolve` call passes no `--json`, so the finding is a plain line on stderr with empty stdout — surface verbatim, no JSON to parse.
- **References:** scripts/epic-manifest.py resolve dispatch; 02-manifest-helper-cli.md §6.1; skills/forge-5-loop/SKILL.md, skills/forge/SKILL.md
- **Checklist:** CHECK-I08, CHECK-I10

### V-003: render-status `parallelEligible` is never asserted to be a strict/non-trivial subset of `actionable`
- **Severity:** improvement
- **Location:** tests/test_epic_manifest.py, `test_render_status_derived_sets`.
- **Issue:** The test asserts `parallelEligible ⊆ actionable` but never that the two ever differ (in the fixture both equal `['a','c']`). A regression collapsing `parallelEligible` to simply equal `actionable` would pass undetected.
- **Suggested fix:** Add an arrangement where two actionable features make `parallelEligible` a strict subset of `actionable`, and assert `set(parallelEligible) < set(actionable)` (or pin expected member names).
- **References:** 05-testing-strategy.md §3.9, 00-core-definitions.md §8, tech-spec.md §4.4
- **Checklist:** CHECK-I16, CHECK-I17

### V-004: stale 05 §6 traceability note implies the `schema`-only test is still outstanding
- **Severity:** improvement
- **Location:** specs/epic-orchestration/05-testing-strategy.md §6 note vs. tests `test_validate_missing_required_field_is_schema` / `test_validate_unknown_key_is_schema`.
- **Issue:** The §6 note says a `schema`-only case "should be added as a sibling test during implementation," but it is already implemented and passing. Implementation is ahead of the spec prose; a future reader may re-add it or treat it as an open gap.
- **Suggested fix:** Update §6 to mark the `schema`-only missing-field case as covered, and add the `additionalProperties:false` unknown-key case to the table/prose.
- **References:** 05-testing-strategy.md §3.2/§6; tests/test_epic_manifest.py
- **Checklist:** CHECK-I16

### V-005: doubled `cycle:` prefix in human-readable cycle output
- **Severity:** improvement
- **Location:** scripts/epic-manifest.py, `_validate_dict` cycle-message construction (~line 718) and `_emit_findings` (~line 1186).
- **Issue:** The cycle finding `message` is built as `"cycle: " + " → ".join(cycle)`, while `_emit_findings` prints `f"{code}: {message}"`. Since `code == "cycle"`, human output renders `cycle: cycle: a → b → a` (verified live). No other finding embeds its own code in the message.
- **Suggested fix:** Drop the leading `"cycle: "` from the message (`" → ".join(cycle)`), or use a non-duplicating phrase like `f"dependsOn cycle: {' → '.join(cycle)}"`.
- **References:** `_emit_findings`; all other finding constructors in `_validate_dict`
- **Checklist:** CHECK-I14

### V-006: mutator subcommands do not support the documented `--json` output convention
- **Severity:** improvement
- **Location:** scripts/epic-manifest.py, mutator subparsers (~lines 1306–1341) and `main` exception handler (~line 1356).
- **Issue:** Only `validate`/`render-status` register `--json`. The five mutators (`add-feature`, `remove-feature`, `reorder`, `set-dep`, `set-status`) reject `--json` (argparse error, exit 2). Consequently `_emit_findings(..., getattr(args,"json_output",False))` is always `False` for mutators, so their refusal findings (`duplicate-name`/`dangling-ref`/`cycle`) can never be emitted as JSON — exactly the structured output a skill most wants to parse.
- **Suggested fix:** Add `--json` (`store_true`, `dest="json_output"`) to the five mutator subparsers via a small helper, so refusal findings serialize through the existing JSON branch. (Or, if intentionally human-only, document that explicitly in the module usage block.) **Requires a decision.**
- **References:** `_emit_findings`; `add_specs_dir` helper; validate/render-status subparsers
- **Checklist:** CHECK-I14, CHECK-I20

### V-007: status-derivation fixture uses `"in_progress"`, violating the pipeline-state schema enum (`"in-progress"`)
- **Severity:** error
- **Location:** tests/fixtures/status-derivation/lifecycle/a/.pipeline-state.json (`forge-5-loop.status`).
- **Issue:** Stage status is spelled `"in_progress"` (underscore) but pipeline-state-schema.json's `stageEntry.status` enum is `["pending","in-progress","complete","stale"]` (hyphen). The code happens to behave correctly because it only tests `!= "complete"` and membership in `(None,"pending")`, so the unrecognized value is treated as "started, not complete" — the intended outcome. The bug is **latent**: the fixture is the project's behavioral oracle, and an invalid value could mask a future regression (e.g. if code switches to an allow-list of started states). Currently harmless; no behavioral impact.
- **Suggested fix:** Change `"in_progress"` → `"in-progress"`. Grep other fixtures for the underscore spelling (only this one found).
- **References:** references/pipeline-state-schema.json `definitions.stageEntry.status`; `derive_status`; `is_complete_for_orchestration`
- **Checklist:** CHECK-I14

### V-008: a complete feature can be reported `blocked: true` (cosmetic status artifact)
- **Severity:** improvement
- **Location:** scripts/epic-manifest.py, `render_status` (~lines 906–909) and `_print_status_table` (~line 1198).
- **Issue:** `unmetDeps`/`blocked` are computed for every row regardless of the feature's own completion. In the status-derivation fixture, feature `b` is `status:"complete"` yet `blocked:true` with `unmetDeps:["a"]` (because dep `a` is in-progress). Logically odd for display; does NOT affect `actionable`/`parallelEligible` (both correctly exclude completed features). Purely a presentation wart.
- **Suggested fix:** Gate the blocked/unmetDeps assignment on incompleteness — set `unmetDeps=[]`, `blocked=False` for completed rows; compute real unmet deps only for not-complete rows.
- **References:** `_print_status_table`; `unmet_deps`
- **Checklist:** CHECK-I14

## Fix Execution Plan

### User Decisions Required
- **V-001:** [RESOLVED 2026-06-13] Amend tech-spec to record intentional v1 omission of `forge.config.json`.
- **V-006:** [RESOLVED 2026-06-13] Add `--json` to the five mutator subcommands.

### Execution Steps

#### Step 1: Fix invalid fixture status value
- **Files:** tests/fixtures/status-derivation/lifecycle/a/.pipeline-state.json
- **Addresses:** V-007
- **Checklist:** CHECK-I14
- **Action:** Change `forge-5-loop` `"status": "in_progress"` → `"in-progress"`. Re-run `render-status lifecycle`; confirm feature `a` stays `in-progress`, rollup `3/5`, suite still 51 passed.
- **Depends on:** none

#### Step 2: Code-quality fixes in epic-manifest.py
- **Files:** scripts/epic-manifest.py
- **Addresses:** V-005, V-008 (and V-006 if approved)
- **Checklist:** CHECK-I14, CHECK-I20
- **Action:** (a) V-005 — drop the duplicate `"cycle: "` prefix from the cycle finding message; confirm human output reads `cycle: a → b → a` once. (b) V-008 — in `render_status`, leave `unmetDeps=[]`/`blocked=False` for completed rows; confirm `actionable`/`parallelEligible` unchanged. (c) If V-006 approved — add a `--json` helper and register it on the five mutator subparsers; verify `add-feature <dup> --json` and `set-dep <cycle> --json` emit `{"valid":false,"findings":[...]}` exit 1. Re-run the full suite.
- **Depends on:** none

#### Step 3: Strengthen parallel-eligible assertion
- **Files:** tests/test_epic_manifest.py (and possibly tests/fixtures/status-derivation/)
- **Addresses:** V-003
- **Checklist:** CHECK-I16, CHECK-I17
- **Action:** Add a case where `parallelEligible` is a strict subset of `actionable` and assert `set(parallelEligible) < set(actionable)` (or pin expected names). Re-run suite.
- **Depends on:** none

#### Step 4: Documentation reconciliation
- **Files:** specs/epic-orchestration/tech-spec.md (V-001, per decision), specs/epic-orchestration/05-testing-strategy.md (V-004), references/shared-conventions.md (V-002)
- **Addresses:** V-001, V-002, V-004
- **Checklist:** CHECK-I01, CHECK-I05, CHECK-I08, CHECK-I10, CHECK-I16
- **Action:** V-001 — amend §2.2/§2.4 per decision (or create the config file). V-004 — mark the `schema`-only test covered in §6. V-002 — make the resolve-block exit-1 stderr behavior explicit.
- **Depends on:** none

## Fix Progress
- Step 1: [APPLIED] 2026-06-13 — V-007: fixed `in_progress` → `in-progress` in status-derivation/lifecycle/a fixture.
- Step 2: [APPLIED] 2026-06-13 — V-005 (dropped duplicate `cycle:` prefix), V-008 (complete features no longer reported blocked), V-006 (added `--json` to add-feature/remove-feature/reorder/set-dep/set-status via add_json helper; usage docstring updated). Verified live: dup-name refusal emits JSON, cycle prints single prefix.
- Step 3: [APPLIED] 2026-06-13 — V-003: added incomplete blocked feature `f` (deps [a]) to the fixture; pinned exact actionable/parallelEligible membership and asserted a complete feature is never blocked.
- Step 4: [APPLIED] 2026-06-13 — V-001 (tech-spec §2.2/§2.4 record forge.config.json deferred in v1), V-002 (shared-conventions resolve exit-1 stderr wording), V-004 (05 §6 note marks schema-only tests as implemented).

Result: full suite 51 passed; `validate.sh` → All checks passed!
