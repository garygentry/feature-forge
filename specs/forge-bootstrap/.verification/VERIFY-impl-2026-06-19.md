# Verification Findings — forge-bootstrap (impl mode)

- **Feature:** forge-bootstrap
- **Mode:** impl
- **Date:** 2026-06-19
- **Verifier:** forge-verify (4 parallel `forge-verifier` instances, dimensioned fan-out)
- **Artifacts verified:** scripts/forge-bootstrap.py, skills/forge-bootstrap/SKILL.md, skills/forge-bootstrap/references/templates/**, references/forge-config-schema.json, scripts/validate.sh, tests/test_forge_bootstrap.py — against PRD.md, tech-spec.md, 00–05 specs, TRACEABILITY.md

## Summary

- **Findings:** 9 (2 `error`, 3 `gap`, 1 `inconsistency`, 3 `improvement`)
- **Build/test health:** `bash scripts/validate.sh` exits 0; `pytest` 52 passed / 2 skipped (skips are genuine toolchain-absence guards: mypy + cargo-clippy); `py_compile` clean; `build-adapters.py --check` clean; helper is stdlib-only.
- **Requirement coverage:** strong — every PRD requirement family traces to implementing code. The two `error` findings are real but localized (a schema type bug and a wrong SKILL.md command); none undermines the core scaffolder.
- **Review item 016 confirmed genuinely fixed:** the generic green-baseline is real — `compose_member` applies `0o755` to `.sh`/shebang files at scaffold time (forge-bootstrap.py:485-489, 520-522), and the integration/green tests do **not** chmod before verify. The on-disk template mode bit (`rw-`) is irrelevant. Not re-masked.

---

## Findings

### V-001 — forge-config-schema.json rejects the helper's (and forge-init's, and the repo's own) config: four nullable fields typed as non-nullable `string`
- **Severity:** error
- **Location:** `references/forge-config-schema.json` — `backlogDir` (~L17-20), `stack` (~L31-34), `typeCheckCommand` (~L35-38), `testCommand` (~L39-42)
- **What's wrong:** These four properties are declared `"type": "string"`, but `write_config` (forge-bootstrap.py:534-545) and `forge-init.sh` (L18-23) both emit them as `null` by default. Validating real configs against the schema (jsonschema Draft7) fails: single-package helper output → 1 error (`backlogDir`); monorepo → 4 errors; **the repo's own committed `forge.config.json` → 4 errors**. So "existing configs still pass" is violated by the schema itself. `null` is the correct documented default; the schema is too strict. (The nested `workspaces[].typeCheckCommand/testCommand` already correctly use `["string","null"]`.)
- **Suggested fix:** Change the four top-level fields' type from `"string"` to `["string", "null"]`, matching the existing nested convention. Leave descriptions unchanged.
- **References:** forge-bootstrap.py:534-545; scripts/forge-init.sh:18-23; references/forge-config-schema.json (nested fields done right); the repo's own forge.config.json
- **Checklist:** CHECK-I10, CHECK-I14

### V-002 — SKILL.md `commit` invocation omits the required `--answers` flag (documented command fails at argparse)
- **Severity:** error
- **Location:** `skills/forge-bootstrap/SKILL.md` Step 6 bash block (~L166)
- **What's wrong:** The block is `python3 "$R/scripts/forge-bootstrap.py" commit "<target-dir>" --json`, but the helper's `commit` subparser declares `--answers` as `required=True` (forge-bootstrap.py:959) and `commit()` reads `answers["commitStyle"]` (L815). As written, argparse exits 2 ("the following arguments are required: --answers") before any commit logic. The sibling scaffold (L132) and verify (L140) blocks correctly pass `--answers`; commit is the lone inconsistent one.
- **Suggested fix:** Update the Step-6 block to `... commit "<target-dir>" --json --answers '<Answers JSON>' [--stage-only]`, matching scaffold/verify. (Alternatively make `--answers` optional for `commit` and default `commitStyle` to "commit" — but the spec treats commitStyle as part of Answers, so fixing the command is preferred.)
- **References:** forge-bootstrap.py:813-833, :959; SKILL.md L132 & L140; 04-skill-orchestration.md §7.6
- **Checklist:** CHECK-I14

### V-003 — No toolchain-independent per-stack structure/config test; typescript & rust scaffolds are unverified when their toolchain is absent
- **Severity:** gap
- **Location:** `tests/test_forge_bootstrap.py` — absence; expected per 05 §3.2
- **What's wrong:** Spec 05 §3.2 mandates a per-stack file-set smoke test (parametrized over all five stacks) plus a config-command test, both "toolchain-independent ... therefore always run." In the implemented suite, **typescript and rust scaffolds are exercised only inside `test_integration_green_baseline_per_stack`**, which is `shutil.which`-gated. On a host without node/npm (typescript) or cargo-clippy (rust — currently SKIPPED on this very host), there is **zero** assertion that those scaffolds emit the correct file set or that `forge.config.json` carries the right `stack`/`typeCheckCommand`/`testCommand`. REQ-STACK-01/02 are therefore unverified for ts/rust when the toolchain is absent. (generic/python/go have toolchain-independent command assertions via the top-level/monorepo tests; ts/rust do not.)
- **Suggested fix:** Add a `@pytest.mark.parametrize("stack", [all five])` test that scaffolds a single-package project and asserts (a) the expected template file set exists and (b) the emitted `forge.config.json` carries `stack`/`typeCheckCommand`/`testCommand` per 00 §6 (e.g. typescript → `npx tsc --noEmit`; rust → `cargo clippy`/`cargo test`). Assert only emitted files/JSON — **no** toolchain guard, so it always runs.
- **References:** 05 §3.2; 00 §6; forge-bootstrap.py:216-223 (constant-only assertion that doesn't exercise emission)
- **Checklist:** CHECK-I16, CHECK-I17 (REQ-STACK-01/02 traceability)

### V-004 — Test suite never validates emitted config against the schema (dead `SCHEMA` constant masks V-001)
- **Severity:** gap
- **Location:** `tests/test_forge_bootstrap.py:29` (`SCHEMA = REPO_ROOT / "references" / "forge-config-schema.json"`)
- **What's wrong:** The module defines a `SCHEMA` constant but never uses it — there is no `jsonschema.validate(...)` anywhere. So the 52-green suite passes even though every emitted config violates the schema (V-001). A schema-conformance test would have caught V-001 at authoring time.
- **Suggested fix:** Add a test (guarded with `pytest.importorskip("jsonschema")`) that validates both single-package and monorepo `write_config` output against `SCHEMA` and asserts zero errors. Land it with the V-001 schema fix so it goes green. If jsonschema isn't an acceptable test dep, remove the dead constant or hand-roll a null-acceptance check.
- **References:** V-001; tests/test_forge_bootstrap.py:29
- **Checklist:** CHECK-I16, CHECK-I17

### V-005 — REQ-SCAF-09 license detect-and-seed half is unimplemented: SKILL.md Q5 never reads a pre-existing LICENSE to seed the default
- **Severity:** gap
- **Location:** `skills/forge-bootstrap/SKILL.md` Step 3 interview table, Q5 (~L107); `CheckResult` (forge-bootstrap.py:164-183, 389-440)
- **What's wrong:** REQ-SCAF-09 requires seeding the interview default from an existing meta file, "e.g. detecting the existing license." 02-helper-cli.md scopes this detection to the skill. But SKILL.md Q5 only says the pre-existing LICENSE "is kept" — it gives no instruction/mechanism to read the existing LICENSE and pre-select the matching Q5 default, and `CheckResult` surfaces no license hint. The no-overwrite half of REQ-SCAF-09 is fully implemented; the detect-and-seed half is not.
- **Suggested fix:** Add a Q5 step in SKILL.md: when `check` reports a pre-existing LICENSE, read its first lines to identify the SPDX id and offer it as the pre-selected default. Optionally have `check`/`status` surface a `preexistingLicense` hint so the seed is deterministic.
- **References:** PRD REQ-SCAF-09; 02-helper-cli.md §4.5/§3; 04-skill-orchestration.md Q5 seed rule
- **Checklist:** CHECK-I (REQ-SCAF coverage)

### V-006 — "the helper cleans" on Restart contradicts the implemented helper (no clean/restart subcommand) and spec 05
- **Severity:** inconsistency
- **Location:** `skills/forge-bootstrap/SKILL.md:91`; mirrored in `04-skill-orchestration.md:322-325`
- **What's wrong:** Both say a Restart choice is handled by "the helper cleans." But the helper exposes exactly five subcommands (check/scaffold/verify/commit/status; forge-bootstrap.py:939-969) with **no** clean/restart/discard path. Spec 05-testing-strategy.md:767 states the opposite (correctly for the implementation): "Restart (clean) is a skill-orchestration decision (delete the partial tree + sentinel, then a fresh `scaffold`)." As written, a Restart choice has no helper subcommand to dispatch.
- **Suggested fix:** Reconcile to match the implementation + spec 05: change SKILL.md:91 to "Restart — discard the partial (delete the recorded `artifactsWritten[]` tree + the sentinel), then run the interview and `scaffold` fresh," and update 04 §7.2 to say restart cleanup is skill-orchestration, not "the helper cleans."
- **References:** forge-bootstrap.py:939-969; 05-testing-strategy.md:767-770; 04-skill-orchestration.md:322-325
- **Checklist:** CHECK-I14

### V-007 — `test_subcommand_bodies_are_stubs` is a tautology (empty `pass`)
- **Severity:** improvement
- **Location:** `tests/test_forge_bootstrap.py:279-281`
- **What's wrong:** The body is `pass` with a docstring "All subcommands are now implemented — this test is a no-op placeholder." It asserts nothing yet counts toward the 52 passes, slightly inflating apparent coverage. Leftover from the foundation phase (item 002).
- **Suggested fix:** Delete it (real coverage now comes from the per-subcommand tests), or convert to `pytest.skip`/`xfail` so it isn't counted as a passing assertion.
- **References:** —
- **Checklist:** CHECK-I (tests assert behavior, not tautologies)

### V-008 — Unused `shutil` import in the helper (dead code)
- **Severity:** improvement
- **Location:** `scripts/forge-bootstrap.py:29` (`import shutil`)
- **What's wrong:** No `shutil.` reference exists in the file (the toolchain probe uses `command -v` via subprocess). epic-manifest.py, the structural model, carries no unused import.
- **Suggested fix:** Remove the `import shutil` line (re-add at point of use if a future template copy needs it).
- **References:** scripts/epic-manifest.py (import block); 01-architecture-layout.md L85
- **Checklist:** CHECK-I13

### V-009 — Generated CI workflow emits no toolchain-setup steps (spec-sanctioned; informational)
- **Severity:** improvement
- **Location:** `skills/forge-bootstrap/references/templates/ci/github-actions.yml`; `_compose_ci_workflow` (forge-bootstrap.py:621-651)
- **What's wrong:** The workflow runs the resolved per-member lint/test commands but installs no language toolchain (`setup-node`, `setup-python`, etc.), so the emitted CI is green-by-design only where the toolchain pre-exists on the runner. This is **explicitly sanctioned** by 03-stack-templates.md:613 ("Toolchain setup is out of scope … An implementer MAY include a minimal setup-* step"), so it conforms — flagged only because it can surprise users.
- **Suggested fix:** Optional: add per-stack `setup-*` steps to the CI composition, or a comment in the generated `ci.yml` noting toolchain setup must be added. No change required for spec compliance.
- **References:** PRD REQ-MONO-04/REQ-SCAF-07; 03-stack-templates.md:613
- **Checklist:** CHECK-I (REQ-MONO/SCAF coverage)

---

## Fix Execution Plan

A fresh agent can execute these with zero prior context. **No user decisions required** for V-001..V-008. V-009 is optional/informational.

### Step 1 — Fix the config schema to accept documented null defaults (V-001)
- **File:** `references/forge-config-schema.json`
- **Action:** Change `backlogDir`, `stack`, `typeCheckCommand`, `testCommand` from `"type": "string"` to `"type": ["string", "null"]`. This unblocks the helper's output, forge-init's output, and the repo's own `forge.config.json`.

### Step 2 — Fix the SKILL.md `commit` command and the Restart prose (V-002, V-006)
- **Files:** `skills/forge-bootstrap/SKILL.md`, `specs/forge-bootstrap/04-skill-orchestration.md`
- **Action:** (a) Step-6 block → `... commit "<target-dir>" --json --answers '<Answers JSON>' [--stage-only]`. (b) Reword the Restart line (SKILL.md:91 + 04 §7.2) so restart cleanup is a skill-orchestration step (delete the `artifactsWritten[]` tree + sentinel, then fresh `scaffold`), not "the helper cleans."

### Step 3 — Strengthen the test suite (V-003, V-004, V-007)
- **File:** `tests/test_forge_bootstrap.py`
- **Action:** (a) Add a toolchain-independent `@parametrize` test over all five stacks asserting the emitted file set + `forge.config.json` `stack`/`typeCheckCommand`/`testCommand` per 00 §6 (closes the ts/rust gap). (b) Add a schema-conformance test (`importorskip("jsonschema")`) validating single-package + monorepo output against `SCHEMA`, asserting zero errors (do after Step 1 so it's green). (c) Delete the tautological `test_subcommand_bodies_are_stubs`.

### Step 4 — Implement the license detect-and-seed half of REQ-SCAF-09 (V-005)
- **Files:** `skills/forge-bootstrap/SKILL.md` (Q5), optionally `scripts/forge-bootstrap.py` (`check`/`status` `preexistingLicense` hint) + `00-core-definitions.md` (CheckResult field)
- **Action:** Have Q5 pre-select the detected license when a LICENSE pre-exists. Minimal: instruct the agent to read the existing LICENSE header and seed the default. Deterministic: add a `preexistingLicense` field to `CheckResult` and have the body use it.

### Step 5 — Cleanup (V-008) and optional CI hardening (V-009)
- **Files:** `scripts/forge-bootstrap.py` (remove unused `import shutil`); optionally the CI template/`_compose_ci_workflow` for V-009.
- **Action:** Delete the dead `shutil` import. Optionally add per-stack `setup-*` steps or an explanatory comment to the generated CI (V-009, not required).

---

## Fix Progress

- Step 1: [APPLIED] 2026-06-19 — V-001: forge-config-schema.json backlogDir/stack/typeCheckCommand/testCommand → ["string","null"]; repo's own forge.config.json now validates (0 errors).
- Step 2: [APPLIED] 2026-06-19 — V-002: SKILL.md Step-6 commit block now passes --answers '<Answers JSON>' [--stage-only]. V-006: SKILL.md:91 + 04 §7.2 reworded — Restart cleanup is a skill-orchestration step (helper has no clean subcommand).
- Step 3: [APPLIED] 2026-06-19 — V-003: added toolchain-independent test_scaffold_emits_stack_file_set_and_commands parametrized over all 5 stacks (file set + stack/typeCheckCommand/testCommand). V-004: added test_emitted_config_validates_against_schema (jsonschema, single+monorepo). V-007: removed tautological test_subcommand_bodies_are_stubs.
- Step 4: [APPLIED] 2026-06-19 — V-005: SKILL.md Q5 now detects/pre-selects license from a pre-existing LICENSE (reads header) and seeds Answers.author (git user.name) + Answers.host (claude on Claude hosts).
- Step 5: [APPLIED] 2026-06-19 — V-008: removed unused `import shutil` from scripts/forge-bootstrap.py. V-009: left as-is (spec-sanctioned, informational).
- Adapters regenerated (python3 scripts/build-adapters.py) after the references/SKILL edits.

Verification: py_compile OK; pytest 57 passed/2 skipped; SKILL.md body 234 lines/1876 words (within budget); bash scripts/validate.sh exit 0 (all checks passed).
