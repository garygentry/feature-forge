# Verification Report: epic-orchestration (impl)
Date: 2026-06-12
Pipeline Stage: forge-6-docs (post forge-5-loop implementation verification)
Artifacts Reviewed:
- scripts/epic-manifest.py
- references/epic-manifest-schema.json, references/pipeline-state-schema.json
- scripts/validate.sh
- references/shared-conventions.md
- skills/forge-0-epic, forge-1-prd, forge-2-tech, forge-3-specs, forge-4-backlog, forge-5-loop, forge-6-docs, forge (navigator), forge-verify, forge-fix
- agents/forge-researcher.md
- tests/test_epic_manifest.py, tests/conftest.py, tests/fixtures/**
- specs/epic-orchestration/{PRD.md, 00-05 specs, TRACEABILITY.md, backlog.json}

Verification method: 4 parallel forge-verifier instances across disjoint dimensions
(requirement coverage, integration correctness, testing, code-quality/conventions).
Test suite executed: `python3 -m pytest tests/ -q` → **50 passed in 2.40s**.

## Summary
- Total findings: 10
- Gaps: 3
- Inconsistencies: 4
- Improvements: 3
- Errors: 0

Overall: implementation is sound and complete. All 21 backlog items implemented in
their named files; all helper tests green; no backward-compat (REQ-COMPAT) regressions
found. Findings are hardening gaps and wiring inconsistencies among the grafted skills —
none are blockers for proceeding to docs.

## Findings

### V-001: Hand-rolled schema checker does not enforce `additionalProperties:false`
- **Severity:** gap
- **Location:** scripts/epic-manifest.py, `_schema_findings` (~lines 539-612) vs references/epic-manifest-schema.json (`additionalProperties:false` at top level, `feature`, `contract`/`exposes`, `consumedContract`/`consumes`)
- **Issue:** The JSON Schema sets `additionalProperties:false` at every object level, but the hand-rolled stdlib checker only validates *required* keys, types, enums, consts, and the explicit `features[].status` guard — it never rejects *unknown* keys. Verified empirically: a manifest whose feature carries `"bogusKey":"x"`, or a typo like `"dependson"` instead of `"dependsOn"` (which would also silently drop the dependency), returns `{"valid":true,"findings":[]}`, exit 0. This is precisely the REQ-ROBUST-02 scenario ("a corrupted or hand-edited manifest must fail validation with actionable errors"). The spec prose (02 §6.2) narrowly scopes the checker and does not mention unknown-key rejection, so the code matches the prose but is weaker than the schema file it claims to check "over" — a spec-internal inconsistency realized in the implementation.
- **Suggested fix:** In `_schema_findings`, after the required-key checks, add per-object unknown-key checks against the allowed key sets (`_TOP_REQUIRED`; `_FEATURE_REQUIRED` excluding the specially-handled `status`; `_CONTRACT_REQUIRED`; `_CONSUMED_REQUIRED`), emitting a `schema` finding per stray key. Reconcile the spec: update 02 §6.2 prose to state the checker rejects unknown keys (mirroring `additionalProperties:false`). Add a pytest feeding an unknown key, asserting a `schema` finding + exit 1. (Alternative: relax the schema files to `additionalProperties:true` and document forward-compat tolerance — but enforcing is recommended, matching REQ-ROBUST-02.)
- **References:** REQ-ROBUST-02 (PRD §4.2); 00-core-definitions.md §2.6; 02-manifest-helper-cli.md §6.2; references/epic-manifest-schema.json; tests/test_epic_manifest.py §3.2
- **Checklist:** CHECK-I04, CHECK-I05, CHECK-I12
- **Found by:** requirement-coverage + code-quality verifiers (independently)

### V-002: forge-verify backlog-mode load uses the un-composed backlog path
- **Severity:** inconsistency
- **Location:** skills/forge-verify/SKILL.md line 116
- **Issue:** Spec 04-pipeline-integration.md §6.2 states forge-5-loop's backlog-file check and forge-verify's backlog-mode load must use the same composed path: `{backlogDir}/{feature}/backlog.json` when `backlogDir` is configured, else `{resolvedFeatureDir}/backlog.json`. forge-4-backlog writes to and forge-5-loop reads from `{backlogDir}/{feature}/backlog.json`, but forge-verify line 116 still reads `{specsDir}/{feature}/backlog.json (or {backlogDir}/backlog.json if configured)` — the old, un-composed path. With a configured `backlogDir`, forge-verify reads a missing/wrong file; for a nested epic member with default `backlogDir`, the literal `{specsDir}/{feature}/backlog.json` is also wrong (should be `{resolvedFeatureDir}/backlog.json`).
- **Suggested fix:** Change line 116 to `{resolvedFeatureDir}/backlog.json (or {backlogDir}/{feature}/backlog.json if backlogDir is configured)`, and ensure forge-verify resolves `{resolvedFeatureDir}` via the Feature Directory Resolution block in its load step (matching forge-4/forge-5).
- **References:** 04-pipeline-integration.md §6.2; skills/forge-4-backlog/SKILL.md:25-27; skills/forge-5-loop/SKILL.md:111,132
- **Checklist:** CHECK-I08, CHECK-I09, CHECK-I10
- **Found by:** integration verifier

### V-003: forge-4-backlog passes the bare `{backlogDir}` downstream, not the per-feature composed path
- **Severity:** inconsistency
- **Location:** skills/forge-4-backlog/SKILL.md lines 73-75 (author-backlog invocation) and 96-100 (validate command)
- **Issue:** The backlog-dir rule (lines 23-27) requires that when `backlogDir` is configured the backlog live at `{backlogDir}/{feature}/` to avoid collisions across a multi-feature epic (REQ-COMPAT-03). But the downstream use-sites reuse the bare `{backlogDir}`: line 73 writes `{backlogDir}/backlog.json`, line 100 runs `validate --backlog {backlogDir}`. Unlike forge-5-loop (which re-states the composition at every use-site), forge-4 never re-states that `{backlogDir}` here means the composed value. A fresh agent could write/validate the colliding bare `{backlogDir}/backlog.json` the rule warns against.
- **Suggested fix:** Add one sentence to the Prerequisites rule: "Throughout the rest of this skill, `{backlogDir}` denotes the composed `{backlogDir}/{feature}` directory when a `backlogDir` is configured, else `{resolvedFeatureDir}`." (Optionally also make `/{feature}` explicit at lines 73 and 100.)
- **References:** skills/forge-4-backlog/SKILL.md:23-27 vs 73-75, 96-100; skills/forge-5-loop/SKILL.md:111,132; 04-pipeline-integration.md §6.2
- **Checklist:** CHECK-I08, CHECK-I10
- **Found by:** integration verifier

### V-004: Grafted skills tell agents to "parse findings" on helper failure, but exit-2 UsageError emits plain stderr (no JSON)
- **Severity:** gap
- **Location:** references/shared-conventions.md (Feature Directory Resolution + Epic Context Injection blocks, ~lines 54-94); skills/forge-5-loop/SKILL.md:59-73; skills/forge/SKILL.md:114; skills/forge-6-docs/SKILL.md:39-45
- **Issue:** epic-manifest.py distinguishes two failure classes: `FindingsError` → exit 1 with structured `{valid, findings[]}` JSON; `UsageError` → exit **2** with a plain `Error: <msg>` on stderr and empty stdout (verified live: `render-status … --json` on a non-epic exits 2, stdout empty). Several grafts instruct the agent to "surface its findings"/"parse the findings" on "exit ≥ 1". On an exit-2 UsageError there is no findings JSON to parse — an agent following "parse findings" literally finds nothing and could misreport.
- **Suggested fix:** In the shared-conventions blocks (single source) and the render-status call sites, split the contract: "exit 1 → parse the `{findings[]}` JSON from stdout and surface each; exit 2 → surface the plain `Error:` line from stderr verbatim and STOP." Point the three consumers (forge-5, forge-6, navigator) at this split.
- **References:** scripts/epic-manifest.py UsageError/exit mapping; 00-core-definitions.md §4
- **Checklist:** CHECK-I08, CHECK-I10
- **Found by:** integration verifier

### V-005: `path-escape` FindingCode is never produced — traceability claim false, code untested
- **Severity:** gap
- **Location:** scripts/epic-manifest.py (`_validate_dict`; `contained_path`); 05-testing-strategy.md §6 traceability table & §3.6; tests/test_epic_manifest.py `test_validate_path_escape_in_manifest_is_finding`
- **Issue:** The `FindingCode` union declares `"path-escape"` and 05 §6 asserts "every FindingCode is produced by a helper subcommand and asserted by this suite," listing `path-escape` as produced by `validate`. But no code path constructs a `path-escape` Finding: `_validate_dict` emits `unsafe-name` for bad names and `dangling-ref` for an escaping `consumes.from`, while `contained_path` raises a `UsageError` (exit 2), not a Finding. The test masks this with an OR assertion (`codes & {"unsafe-name","path-escape"}`) satisfied by the `unsafe-name` half. Net: `path-escape` has zero coverage and is likely dead, contradicting the spec's coverage invariant.
- **Suggested fix:** Pick the intended contract and align code + spec + test. Either (a) remove `path-escape` from the FindingCode union and from 05 §6 / 00 §4 (containment escapes already surface as exit-2 UsageErrors with coverage), or (b) make `_validate_dict` emit a `path-escape` Finding for escaping `consumes.from`/resolved dirs and tighten the test to assert it specifically. Option (a) is smaller and matches current behavior.
- **References:** 00-core-definitions.md §4; tech-spec §6; tests/fixtures/path-escape/
- **Checklist:** CHECK-I14
- **Found by:** testing verifier

### V-006: `path-escape` test uses an OR assertion that cannot distinguish the two codes
- **Severity:** inconsistency
- **Location:** tests/test_epic_manifest.py, `test_validate_path_escape_in_manifest_is_finding`
- **Issue:** The fixture deliberately carries two defects — an unsafe name (`../escape`) and an escaping `consumes.from` (`../x`). The test asserts only `codes & {"unsafe-name","path-escape"}`, passing if *either* appears. It cannot detect that `path-escape` is never emitted (V-005), and never verifies the escaping-consumes half.
- **Suggested fix:** After resolving V-005, split into two explicit assertions: `assert "unsafe-name" in codes` and (per the V-005 decision) `assert "path-escape" in codes` or `assert "dangling-ref" in codes`. Avoid the set-intersection OR.
- **References:** V-005; 05-testing-strategy.md §3.6
- **Checklist:** CHECK-I15
- **Found by:** testing verifier

### V-007: Blocked-deps render-status test is looser than the documented fixture graph
- **Severity:** improvement
- **Location:** tests/test_epic_manifest.py `test_render_status_blocked_lists_unmet_deps` (~line 444); tests/fixtures/status-derivation/lifecycle/
- **Issue:** The test asserts only that *some* feature is blocked and that all blocked features have non-empty `unmetDeps` — never *which* feature or *which* dep. A future fixture edit removing `b`'s dependency would still pass if any other blocked feature existed.
- **Suggested fix:** Pin the expectation: `b_row = next(f for f in out["features"] if f["name"]=="b"); assert b_row["blocked"] and "a" in b_row["unmetDeps"]`.
- **References:** 05-testing-strategy.md §2.2, §3.7
- **Checklist:** CHECK-I13, CHECK-I15
- **Found by:** testing verifier

### V-008: `createdAt`/`updatedAt` accepted without date-time format validation
- **Severity:** improvement
- **Location:** scripts/epic-manifest.py, `_schema_findings` (~lines 559-561)
- **Issue:** The schema declares `"format":"date-time"` for `createdAt`/`updatedAt`, but the checker only asserts they are strings. `"yesterday"` passes. Minor — mutators always write correct ISO-8601 via `datetime.now(timezone.utc).isoformat()` — but a hand-edited manifest divergence.
- **Suggested fix:** Either add a lightweight `datetime.fromisoformat()` check emitting a `schema` finding on failure, or explicitly note in 02 §6.2 that date-time `format` is advisory (draft-07 format assertions are non-enforcing by default). Either is acceptable.
- **References:** references/epic-manifest-schema.json; 02 §6.2
- **Checklist:** CHECK-I12
- **Found by:** code-quality verifier

### V-009: Stale "stubs" docstring left in `_dispatch` after implementation
- **Severity:** inconsistency
- **Location:** scripts/epic-manifest.py, `_dispatch` docstring (~lines 1191-1196)
- **Issue:** The docstring still reads "Subcommand handlers are stubs at this stage (backlog items 004-008 fill them in)…". All handlers are now fully implemented — leftover scaffolding text now factually wrong.
- **Suggested fix:** Replace with an accurate description, e.g. "Route a parsed command to its handler, translating return/raise into a process exit code. Read-only commands print to stdout; mutators return findings the caller raises as FindingsError; unknown commands raise UsageError (exit 2)."
- **References:** 02 §9
- **Checklist:** CHECK-I15
- **Found by:** code-quality verifier

### V-010: `find_cycle` self-loop degenerate case under-documented at the code site
- **Severity:** improvement
- **Location:** scripts/epic-manifest.py, `find_cycle` (~lines 326-366)
- **Issue:** Not a correctness bug — self-dependency correctly yields `["X","X"]` and ordinary cycles reconstruct correctly (verified). The implementation docstring abbreviates the spec's careful self-loop explanation (02 §4), so the degenerate branch is less obvious to a future reader.
- **Suggested fix:** Optional. Port the spec's self-dependency paragraph (02 §4) into the `find_cycle` implementation docstring. Low priority; behavior already correct and tested.
- **References:** 02 §4
- **Checklist:** CHECK-I15, CHECK-I16
- **Found by:** code-quality verifier

> Note: one additional candidate finding (validate `--json` failure path allegedly not
> emitting JSON) was raised and then **refuted on re-trace** by the code-quality verifier
> — `_emit_findings` correctly produces the `{"valid":false,"findings":[...]}` envelope on
> the failure path. It is intentionally excluded.

## Fix Execution Plan

### User Decisions Required
- **V-001 direction:** RESOLVED 2026-06-12 → **Enforce** unknown-key rejection in the
  checker (matches the stricter schema + REQ-ROBUST-02).
- **V-005 direction:** RESOLVED 2026-06-12 → **Remove** the `path-escape` FindingCode
  (matches current exit-2 behavior; containment escapes surface as exit-2 UsageErrors).
- All other findings (V-002, V-003, V-004, V-006–V-010) are mechanical and need no decision.

### Execution Steps

#### Step 1: Enforce `additionalProperties:false` in the hand-rolled checker (if decision = enforce)
- **Files:** scripts/epic-manifest.py, tests/test_epic_manifest.py, specs/epic-orchestration/02-manifest-helper-cli.md
- **Addresses:** V-001
- **Checklist:** CHECK-I04, CHECK-I05, CHECK-I12
- **Action:** Add per-object unknown-key checks in `_schema_findings` against `_TOP_REQUIRED` / `_FEATURE_REQUIRED` (skip `status`) / `_CONTRACT_REQUIRED` / `_CONSUMED_REQUIRED`, emitting a `schema` finding per stray key. Add a pytest feeding an unknown key (assert exit 1 + `schema` finding). Update 02 §6.2 prose to state unknown-key rejection.
- **Depends on:** User decision (V-001).

#### Step 2: Resolve the `path-escape` FindingCode contract (if decision = remove)
- **Files:** scripts/epic-manifest.py, specs/epic-orchestration/00-core-definitions.md (§4), specs/epic-orchestration/05-testing-strategy.md (§6, §3.6)
- **Addresses:** V-005
- **Checklist:** CHECK-I14
- **Action:** Delete `"path-escape"` from the FindingCode union and from the 00 §4 taxonomy + 05 §6 table, with a note that containment escapes surface as exit-2 UsageErrors. (Or, if implementing: emit a `path-escape` Finding in `_validate_dict` for escaping `consumes.from`/resolved dirs and document it.)
- **Depends on:** User decision (V-005).

#### Step 3: Tighten the path-escape test assertions
- **Files:** tests/test_epic_manifest.py
- **Addresses:** V-006
- **Checklist:** CHECK-I15
- **Action:** Replace the `codes & {"unsafe-name","path-escape"}` OR with two explicit `in codes` assertions (unsafe name + the consumes outcome chosen in Step 2).
- **Depends on:** Step 2.

#### Step 4: Fix the grafted-skill backlog path + composed-dir wiring
- **Files:** skills/forge-verify/SKILL.md, skills/forge-4-backlog/SKILL.md
- **Addresses:** V-002, V-003
- **Checklist:** CHECK-I08, CHECK-I09, CHECK-I10
- **Action:** forge-verify line 116 → `{resolvedFeatureDir}/backlog.json (or {backlogDir}/{feature}/backlog.json if backlogDir is configured)`, resolving `{resolvedFeatureDir}` via the Feature Directory Resolution block. forge-4-backlog Prerequisites rule → add the "`{backlogDir}` denotes the composed `{backlogDir}/{feature}`" sentence.
- **Depends on:** none.

#### Step 5: Clarify exit-1 vs exit-2 helper-failure handling
- **Files:** references/shared-conventions.md (primary), with pointer notes in skills/forge-5-loop/SKILL.md, skills/forge-6-docs/SKILL.md, skills/forge/SKILL.md
- **Addresses:** V-004
- **Checklist:** CHECK-I08, CHECK-I10
- **Action:** In the Feature Directory Resolution + Epic Context Injection blocks, replace blanket "exit ≥ 1 → surface findings" wording with: "exit 1 → parse `{findings[]}` and surface each; exit 2 → surface the plain `Error:` line from stderr verbatim and STOP." Point the three consumers at this split.
- **Depends on:** none.

#### Step 6: Mechanical doc/test cleanups
- **Files:** scripts/epic-manifest.py, tests/test_epic_manifest.py, specs/epic-orchestration/02-manifest-helper-cli.md
- **Addresses:** V-007, V-008, V-009, V-010
- **Checklist:** CHECK-I12, CHECK-I13, CHECK-I15, CHECK-I16
- **Action:** Replace the stale `_dispatch` "stubs" docstring (V-009); pin the blocked-deps test to feature `b` + dep `a` (V-007); add ISO-8601 validation for `createdAt`/`updatedAt` or note it advisory (V-008); port the self-loop paragraph into `find_cycle`'s docstring (V-010).
- **Depends on:** none.

## Fix Progress
- Step 1: [APPLIED] 2026-06-12 — V-001: enforce unknown-key rejection in `_schema_findings` (top/feature/contract/consumed levels) + ISO-8601 date-time check; added `test_validate_unknown_key_is_schema`; updated 02 §6.2 prose. (Decision: Enforce.)
- Step 2: [APPLIED] 2026-06-12 — V-005: removed `path-escape` FindingCode from union + 00 §4 taxonomy/prose + 05 §6 table; updated `contained_path` docstring (escapes are exit-2 UsageErrors). (Decision: Remove.)
- Step 3: [APPLIED] 2026-06-12 — V-006: tightened path-escape test to assert `unsafe-name` AND `dangling-ref` explicitly (verified fixture produces both).
- Step 4: [APPLIED] 2026-06-12 — V-002: forge-verify backlog path → composed `{resolvedFeatureDir}`/`{backlogDir}/{feature}`. V-003: forge-4-backlog introduced `{resolvedBacklogDir}` alias, used at author + validate sites.
- Step 5: [APPLIED] 2026-06-12 — V-004: split exit-1 (parse findings JSON) vs exit-2 (plain stderr) handling in shared-conventions resolution + injection blocks; pointed forge-5-loop, forge-6-docs, navigator at the split; dropped removed `path-escape` from 04 §6.2.
- Step 6: [APPLIED] 2026-06-12 — V-009 stale `_dispatch` docstring fixed; V-007 blocked-deps test pinned to feature `b` dep `a`; V-008 ISO-8601 validation (folded into Step 1); V-010 self-loop comment added to `find_cycle`.
- Verification: `bash scripts/validate.sh` → All checks passed; `python3 -m pytest tests/ -q` → 51 passed.
