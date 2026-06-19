# Verification Findings — forge-bootstrap (specs mode)

- **Feature:** forge-bootstrap
- **Mode:** specs
- **Date:** 2026-06-18
- **Verifier:** forge-verify (5 parallel `forge-verifier` instances, dimensioned fan-out)
- **Artifacts verified:** PRD.md, tech-spec.md, 00-core-definitions.md, 01-architecture-layout.md, 02-helper-cli.md, 03-stack-templates.md, 04-skill-orchestration.md, 05-testing-strategy.md, TRACEABILITY.md

## Summary

- **Findings:** 13 (3 `error`, 1 `gap`, 5 `inconsistency`, 4 `improvement`)
- **Deterministic traceability validator:** 51 requirements, **0 uncovered, 0 orphaned** — corroborated semantically (no requirement merely name-dropped).
- **Checks executed across dimensions:** ~50 (types/contracts 11, architecture/layout 7, cross-ref/traceability 9, testing 14, integration 9).
- **Overall:** The spec suite is strong and internally near-consistent. The load-bearing issues are two factual errors that would actively mislead an implementer (V-001 wrong adapter-regen path; V-002 wrong CI section number) and one dead test assertion (V-003). The rest are tightening fixes. PRD OQ-01..05 and carried-forward OQ-T1/T2/T3 are all substantively resolved.

---

## Findings

### V-001 — `installer/adapters/**` named as the adapter-regeneration / CI-gated target; correct path is top-level `adapters/`
- **Severity:** error
- **Location:** `tech-spec.md` §2 (module tree, line ~51) and §6 (integration table, line ~275); `01-architecture-layout.md` §1.2 (modified-files table, line ~64)
- **What's wrong:** `scripts/build-adapters.py` regenerates the **repo-root `adapters/`** tree (`ADAPTERS_DIRNAME = "adapters"`; atomic-swaps `adapters/`; `--check` drift message "`adapters/` is out of date"). `scripts/validate.sh` runs `build-adapters.py --check` as the hard CI gate against **`adapters/`**, never `installer/adapters/`. `installer/adapters/` is a *separate* npm-packaged copy produced by `installer/scripts/bundle-adapters.mjs` at `prepack` time and is not touched by `build-adapters.py`. Naming `installer/adapters/**` as the regenerated/CI-gated artifact is factually wrong and points the implementer at the wrong tree. (Note: `01-architecture-layout.md` §6.3 already correctly says "committed `adapters/`" — so 01 contradicts itself between §1.2 and §6.3.)
- **Suggested fix:** Replace `installer/adapters/**` → `adapters/**` in tech-spec §2 (line ~51), tech-spec §6 (line ~275), and the 01 §1.2 table row. 01 §1.2 row should read: `| adapters/** | Regenerated via python3 scripts/build-adapters.py (new skill + references/ propagate automatically); hard CI gate via validate.sh build-adapters.py --check over adapters/. |`. This also resolves the 01 §1.2-vs-§6.3 internal inconsistency.
- **References:** `scripts/build-adapters.py`, `scripts/validate.sh` (lines ~159–186), `installer/scripts/bundle-adapters.mjs`; 01 §6.3 (correct phrasing to align to)
- **Checklist:** CHECK-S06, CHECK-S08, CHECK-S14

### V-002 — Broken inter-spec reference: CI workflow cited as "03 §5" but actually lives in 03 §9
- **Severity:** error
- **Location:** `02-helper-cli.md` §4.4 (lines ~508, 515, 532); `01-architecture-layout.md` §1.1 (line ~47) and §5 (line ~174)
- **What's wrong:** Five references send the reader to **"03 §5"** for the CI workflow template / per-member step expansion. In `03-stack-templates.md`, **§5 is the Rust Template**; the CI Workflow Template is **§9** (with member steps in §9.1, single-package in §9.2). Following the pointer lands on the wrong section. **Do not** change `01-architecture-layout.md` line ~44's "03 §5.2" — that correctly references Rust's `src/lib.rs`.
- **Suggested fix:** Replace `03 §5` → `03 §9` (and `03-stack-templates.md §5` → `… §9`) at 02-helper-cli.md lines ~508, 515, 532 and 01-architecture-layout.md lines ~47 and ~174. Leave 01 line ~44 ("03 §5.2") unchanged.
- **References:** `03-stack-templates.md` §9/§9.1/§9.2; `00-core-definitions.md` §6
- **Checklist:** CHECK-S14

### V-003 — Dead / self-contradictory assertion in the no-`git add -A` staging test
- **Severity:** error
- **Location:** `05-testing-strategy.md` §3.6, `test_commit_stages_exact_list_not_add_all` (lines ~708–709)
- **What's wrong:** Line ~708 reads `assert "STRAY.txt" in payload["staged"] or True` (a no-op, always passes, comment contradicts the guarantee) immediately followed by `assert "STRAY.txt" not in payload["staged"]`. The two lines are contradictory; this is the flagship REQ-SEC-02 `-A`-guard test and its illustrative code should be exemplary.
- **Suggested fix:** Delete line ~708 entirely; keep only `assert "STRAY.txt" not in payload["staged"]` (plus the existing git `diff --cached` check).
- **References:** PRD REQ-SEC-02; 00 §4 `CommitResult.staged`; 02 §6 step 3
- **Checklist:** CHECK-S (testing edge/failure-mode; verification commands runnable)

### V-004 — `test_verify_toolchain_missing_is_exit_2` does not deterministically exercise the missing-toolchain path
- **Severity:** gap
- **Location:** `05-testing-strategy.md` §3.8, `test_verify_toolchain_missing_is_exit_2` (lines ~779–790)
- **What's wrong:** The body only asserts exit 2 when `shutil.which("cargo") is None`, else `pytest.skip(...)`. On any host/CI image that has `cargo` (or the chosen toolchain) installed, the exit-2 path — the single most safety-critical false-green guard (00 §9; the predicate Mode B gates on) — is **never executed**. The line-~779 comment claims it "empties PATH to force a probe miss," but the code never does so (`monkeypatch` is accepted but unused).
- **Suggested fix:** Make the miss deterministic: use the `env`/PATH control (see V-010) to run `verify` with a probe-stripped `PATH` so the test runs unconditionally; remove the host-dependent `pytest.skip`; fix the comment to match the real mechanism.
- **References:** 00 §9 exit table; 02 §5/§7 (`verify` → exit 2 when `toolchainPresent` false); PRD §8 "Missing toolchain", REQ-MODEB-04; depends on V-010
- **Checklist:** CHECK-S (edge/failure-mode coverage)

### V-005 — `commit()` reads `answers["commitPrefix"]`, but `commitPrefix` is not a field of the `Answers` TypedDict
- **Severity:** inconsistency
- **Location:** `02-helper-cli.md` §6, `commit()` (line ~683: `f"{answers.get('commitPrefix', 'forge')}: bootstrap baseline"`); contradicts `00-core-definitions.md` §5 (`Answers`) and §7 (config field set)
- **What's wrong:** `commitPrefix` lives in `forge.config.json` (00 §7), not in `Answers` (00 §5 defines exactly `projectName, purpose, layout, license, members, modeB, modeBTarget, ci, commitStyle`; 04 §4.1 confirms "body does not invent fields beyond that schema"). So `answers.get("commitPrefix", "forge")` always falls through to `"forge"` and never honors a user-customized prefix. The §6 prose note concedes the call is "illustrative," but the specified code path reads from the wrong source and never says how `commit` obtains the real value. (Low blast radius today since bootstrap always writes `commitPrefix: "forge"`, so default == config — but it's a real contract divergence.) *(Flagged independently by the types and integration verifiers.)*
- **Suggested fix:** Have `commit()` read `commitPrefix` from the just-written `forge.config.json` in `target` (default `"forge"` when absent) and update the §6 snippet; drop the `answers.get(...)` form. Alternatively, if it must come via `Answers`, add `commitPrefix: str` to the `Answers` TypedDict (00 §5) and the 04 §4.1 payload, and use `answers["commitPrefix"]`. Either way, remove `.get()` on a TypedDict.
- **References:** 00 §5, §7; 02 §6; 04 §4.1
- **Checklist:** CHECK-S10, CHECK-S12

### V-006 — `CommandOutcome.member` semantics conflict: `"."` (type docstring) vs `member["name"]` (code)
- **Severity:** inconsistency
- **Location:** `00-core-definitions.md` §4 (`CommandOutcome.member` docstring: `"." for a single package`) vs `02-helper-cli.md` §5 `verify()` (line ~621: `"member": member["name"]`) and §5 prose (line ~546)
- **What's wrong:** The type docstring and §5 prose promise `member == "."` for a single package, but the code emits `member["name"]`, which for a single package equals the **project name** (00 §5), not `"."`. The skill surfaces this field verbatim to the user (04 §7.5), so the mismatch is user-visible and breaks any test asserting `member == "."`.
- **Suggested fix:** Emit `member["path"]` (which is `"."` for a single package, `packages/api` for a monorepo member) in the §5 `verify()` code, and reconcile the 00 §4 docstring to reference `path`. If `name` is truly intended, instead drop the `"."` claim from 00 §4 and §5 prose.
- **References:** 00 §4 (`CommandOutcome`, `VerifyResult`); 02 §5; 04 §7.5
- **Checklist:** CHECK-S10, CHECK-S12, CHECK-S23

### V-007 — Rust template file inventory inconsistent across docs (`src/lib.rs`)
- **Severity:** inconsistency
- **Location:** `01-architecture-layout.md` §1.1 (rust tree, includes `src/lib.rs`) vs `tech-spec.md` §2 (rust line, omits it) vs `03-stack-templates.md` §1/§5.1 (omit) and §5.2 (adds `src/lib.rs` as "the load-bearing fourth source file")
- **What's wrong:** The rust template's file set is stated three ways. An implementer reading tech-spec §2 or 03 §1/§5.1 would omit `src/lib.rs`, breaking the rust baseline (the integration test imports `{{PKG}}::greet` from the lib target).
- **Suggested fix:** Make `src/lib.rs` explicit in every rust listing — add it to tech-spec §2's rust line and to 03 §1's tree and §5.1's table so all enumerate exactly: `Cargo.toml, src/lib.rs, src/main.rs, tests/smoke.rs, .gitignore`. Keep the §5.2 note.
- **References:** 01 §1.1; tech-spec §2; 03 §1/§5.1/§5.2
- **Checklist:** CHECK-S06, CHECK-S07, CHECK-S08

### V-008 — TypeScript template lists a non-existent "eslint config" asset
- **Severity:** inconsistency
- **Location:** `01-architecture-layout.md` §1.1 (typescript comment) and `tech-spec.md` §2 (typescript line) vs `03-stack-templates.md` §2.1 (typescript file list)
- **What's wrong:** 01 §1.1 and tech-spec §2 list an "eslint config" in the typescript template, but the authoritative asset doc 03 §2.1 defines exactly `package.json, tsconfig.json, src/index.ts, test/smoke.test.ts, .gitignore` — no eslint config — and the resolved lint command is `npx tsc --noEmit` (00 §6, 03 §2.4), not eslint. The asset is orphaned: no spec defines its contents and no command consumes it; fabricating it risks an extra dev-dep beyond the "typescript + vitest only" guarantee (tech-spec §3.5/OQ-T2).
- **Suggested fix:** Remove "eslint config" from 01 §1.1's typescript comment and tech-spec §2's typescript line so all three docs agree on the 03 §2.1 file set. (If eslint is genuinely wanted, that is a separate decision requiring a 03 asset spec + a 00 §6 lint-command change — do not add silently.)
- **References:** 01 §1.1; tech-spec §2; 03 §2.1/§2.4; 00 §6
- **Checklist:** CHECK-S04, CHECK-S06, CHECK-S08

### V-009 — TRACEABILITY: REQ-SCAF-07 (CI) supporting citation "00 §7" has no CI content
- **Severity:** inconsistency
- **Location:** `TRACEABILITY.md` line ~34 — `REQ-SCAF-07 | Optional CI workflow | 02 §4.4 | 00 §7, 04`
- **What's wrong:** `00-core-definitions.md` §7 is the `forge.config.json` field set + `workspaces[]` extension — nothing about CI. The CI requirement is genuinely specified (primary 02 §4.4 ✓; substantively 03 §9 ✓; interview question 04 §4), so coverage isn't lost, but the §7 support pointer is wrong and the real CI-template home (03 §9) isn't cited for this row.
- **Suggested fix:** Change REQ-SCAF-07's Supporting column from `00 §7, 04` to `03 §9, 04 §4` (keep primary `02 §4.4`).
- **References:** 03 §9/§9.2; 02 §4.4; 04 §4; contrast line ~43 (REQ-MONO-04) which correctly cites 03 §9
- **Checklist:** CHECK-S (TRACEABILITY accuracy)

### V-010 — `run_bootstrap` fixture cannot pass `env`/PATH, blocking deterministic toolchain tests
- **Severity:** improvement
- **Location:** `05-testing-strategy.md` §2.2, `run_bootstrap` fixture (lines ~203–224; `subprocess.run` at ~216–221 passes no `env`)
- **What's wrong:** `_run(*args, cwd=None)` has no `env` parameter and omits `env=` from `subprocess.run`, so a test cannot control the child's `PATH` — exactly what V-004 needs to force a deterministic toolchain miss.
- **Suggested fix:** Extend to `def _run(*args, cwd=None, env=None)` and pass `env=env` (merged over `os.environ` when provided) into `subprocess.run`. Enables V-004's `run_bootstrap("verify", ..., env={**os.environ, "PATH": ""})`.
- **References:** 02 §5 (`verify` toolchain probe); 05 §2.2; enables V-004
- **Checklist:** CHECK-S (05 actionable/complete)

### V-011 — `forge.config.json` field ordering diverges between docs; "≡ forge-init" equivalence basis unstated
- **Severity:** improvement
- **Location:** `02-helper-cli.md` §4.3 (`write_config` dict literal) vs `00-core-definitions.md` §7 (field table) vs `scripts/forge-init.sh`
- **What's wrong:** 00 §7's table lists `loopIterationMultiplier` before `stack`, while §4.3's literal (matching forge-init.sh) places it after `testCommand`. Neither doc states whether key *order* matters for the REQ-CFG-02 equivalence claim, while §7.1 elsewhere asserts "byte-for-byte back-compatible" — a latent ambiguity.
- **Suggested fix:** State in 00 §7 / 02 §4.3 that REQ-CFG-02 equivalence is **semantic (key/value set), not byte-order**, with `loopRunner` appended last — or pin emitted key order to forge-init.sh exactly and align the §7 table to it. Recommend the semantic-equivalence note.
- **References:** `scripts/forge-init.sh`; 00 §7/§7.1; 02 §4.3
- **Checklist:** CHECK-S05, CHECK-S08

### V-012 — `workspaces[]` uses closed `additionalProperties: false` and drops `packageManager` without a documented rationale
- **Severity:** improvement
- **Location:** `00-core-definitions.md` §7.1 (workspaces[] schema) and `01-architecture-layout.md` §4; vs `references/forge-config-schema.json` (top-level is open)
- **What's wrong:** The new `workspaces[]` item schema is stricter than the surrounding open top-level schema, and intentionally omits `packageManager` (which `Member` carries). The drop is correct (commands already bake in `{pm}`), but it's undocumented, so a future contributor may re-add `packageManager` and trip `additionalProperties: false`.
- **Suggested fix:** Add a one-line note in 00 §7.1: `workspaces[]` deliberately uses `additionalProperties: false` (closed shape) and intentionally omits `packageManager` because per-member `typeCheckCommand`/`testCommand` are already fully resolved.
- **References:** `references/forge-config-schema.json`; 00 §5/§7.1; 01 §4
- **Checklist:** CHECK-S08, CHECK-S12

### V-013 — `compose_member` template-root resolution relies on an undocumented repo-layout invariant
- **Severity:** improvement
- **Location:** `02-helper-cli.md` §4.2 (`compose_member`, `Path(__file__).resolve().parent.parent / "skills" / "forge-bootstrap" / "references" / "templates" / ...`) vs `01-architecture-layout.md` §1.1/§3
- **What's wrong:** The `parent.parent` + 4-segment join is correct only because the helper lives at `scripts/forge-bootstrap.py` and templates at `skills/forge-bootstrap/references/templates/`. Both facts are in 01 §1.1, but §4.2 hard-codes the path without citing that invariant; a relocation would break silently.
- **Suggested fix:** Add a one-line note in 02 §4.2 (and the 01 §3 skeleton): "template root = `<repo-root>/skills/forge-bootstrap/references/templates/`, where `<repo-root>` is `Path(__file__).resolve().parent.parent` because the helper lives at `scripts/forge-bootstrap.py` (01 §1.1)."
- **References:** 02 §4.2; 01 §1.1/§3; 00 §1.1
- **Checklist:** CHECK-S06, CHECK-S17

---

## Fix Execution Plan

A fresh agent can execute these steps with zero prior context. **No user decisions are required** — every fix is a mechanical doc/code correction with a single clear target. Steps are ordered to fix authoritative/shared content first.

### Step 1 — Correct the adapter-regeneration path (`installer/adapters/**` → `adapters/**`)
- **Addresses:** V-001
- **Files:** `tech-spec.md` (§2 line ~51, §6 line ~275), `01-architecture-layout.md` (§1.2 table row, line ~64)
- **Action:** Replace `installer/adapters/**` with `adapters/**` in all three locations. Align the 01 §1.2 row wording to 01 §6.3 (which already says "committed `adapters/`"). This also closes the 01 §1.2-vs-§6.3 internal contradiction.

### Step 2 — Fix the CI inter-spec section number (`03 §5` → `03 §9`)
- **Addresses:** V-002
- **Files:** `02-helper-cli.md` (§4.4 lines ~508, 515, 532), `01-architecture-layout.md` (lines ~47, ~174)
- **Action:** Replace `03 §5` / `03-stack-templates.md §5` with `03 §9`. **Do not** touch `01` line ~44 ("03 §5.2" — correct).

### Step 3 — Reconcile file inventories and orphan assets (Rust `src/lib.rs`, TypeScript eslint)
- **Addresses:** V-007, V-008
- **Files:** `tech-spec.md` §2, `01-architecture-layout.md` §1.1, `03-stack-templates.md` §1/§5.1
- **Action:** (a) Add `src/lib.rs` to every rust file listing so all read `Cargo.toml, src/lib.rs, src/main.rs, tests/smoke.rs, .gitignore`. (b) Remove "eslint config" from the typescript template in 01 §1.1 and tech-spec §2 (match 03 §2.1's five-file set).

### Step 4 — Fix the `commitPrefix` source and `CommandOutcome.member` contract
- **Addresses:** V-005, V-006
- **Files:** `00-core-definitions.md` §4/§5, `02-helper-cli.md` §5/§6
- **Action:** (a) Make `commit()` read `commitPrefix` from the written `forge.config.json` (default `"forge"`), removing the `answers.get("commitPrefix", ...)` form. (b) Change the §5 `verify()` emit from `member["name"]` to `member["path"]` and align the 00 §4 docstring to `path` ("." for single package).

### Step 5 — Fix the testing strategy (fixture env, deterministic toolchain test, dead assertion)
- **Addresses:** V-003, V-004, V-010
- **Files:** `05-testing-strategy.md` §2.2, §3.6, §3.8
- **Action:** (a) §3.6: delete the dead `assert "STRAY.txt" in payload["staged"] or True` line. (b) §2.2: add `env=None` to `run_bootstrap._run` and forward it (merged over `os.environ`) to `subprocess.run`. (c) §3.8: rewrite `test_verify_toolchain_missing_is_exit_2` to force a probe miss via the new `env` PATH control, run unconditionally, drop the `pytest.skip`, fix the comment. (Do (b) before (c).)

### Step 6 — Documentation-tightening notes (TRACEABILITY citation, config order, schema rationale, template-root invariant)
- **Addresses:** V-009, V-011, V-012, V-013
- **Files:** `TRACEABILITY.md` (line ~34), `00-core-definitions.md` (§7/§7.1), `02-helper-cli.md` (§4.2/§4.3), `01-architecture-layout.md` (§3)
- **Action:** (a) V-009: REQ-SCAF-07 Supporting `00 §7, 04` → `03 §9, 04 §4`. (b) V-011: add a "REQ-CFG-02 equivalence is semantic, not byte-order; `loopRunner` appended last" note. (c) V-012: add the `workspaces[]` closed-shape / `packageManager`-omission rationale note. (d) V-013: add the `compose_member` template-root invariant note.

---

## Fix Progress

- Step 1: [APPLIED] 2026-06-18 — V-001: `installer/adapters/**` → `adapters/**` in tech-spec §2/§6 and 01 §1.2 (CI gate now reads build-adapters.py --check over adapters/).
- Step 2: [APPLIED] 2026-06-18 — V-002: CI workflow refs `03 §5` → `03 §9` in 02 §4.4 (×4) and 01 §1.1/§5; left 01 "03 §5.2" (Rust lib) unchanged.
- Step 3: [APPLIED] 2026-06-18 — V-007: added `src/lib.rs` to rust listings (tech-spec §2, 03 §1 tree, 03 §5.1 table) + fixed contradictory "lib.rs-free" note; V-008: removed orphan "eslint config" from typescript listings (tech-spec §2, 01 §1.1).
- Step 4: [APPLIED] 2026-06-18 — V-005: `commit()` now reads `commitPrefix` from forge.config.json (not Answers), updated docstring + note; V-006: `verify()` emits `member["path"]`, 00 §4 docstring + 02 §5 prose aligned to path.
- Step 5: [APPLIED] 2026-06-18 — V-003: deleted dead `or True` assertion in §3.6; V-010: added `env` param to `run_bootstrap` fixture (+ `import os`); V-004: rewrote `test_verify_toolchain_missing_is_exit_2` to force PATH="" deterministically, removed host-dependent skip.
- Step 6: [APPLIED] 2026-06-18 — V-009: TRACEABILITY REQ-SCAF-07 supporting `00 §7, 04` → `03 §9, 04 §4`; V-011: semantic-equivalence note in 00 §7; V-012: workspaces[] closed-shape/packageManager-omission note in 00 §7.1; V-013: compose_member template-root invariant note in 02 §4.2 + 01 §3 skeleton.
