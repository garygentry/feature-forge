# Verification Report: verify-test-debt (impl)
Date: 2026-08-04
Pipeline Stage: forge-5-loop (complete, v1) — `forge-verify-impl` was `auto-verify-pending`

Artifacts Reviewed:
- `specs/verify-test-debt/PRD.md`, `tech-spec.md`, `TRACEABILITY.md`, `backlog.json`
- `specs/verify-test-debt/00-core-definitions.md`, `01-architecture-layout.md`,
  `02-canon-and-prose-guard.md`, `03-machinery-trim.md`, `04-production-validations.md`,
  `05-coverage-backfill.md`, `06-brittleness-batch.md`, `07-testing-strategy.md`
- `scripts/forge-session.py`, `scripts/validate-traceability.py`, `scripts/validate.sh`,
  `scripts/build-adapters.py`, `scripts/check-spec-purity.py`, `eval/run-compliance-eval.py`
- `tests/` (full suite), `adapters/*/scripts/`, `references/`, `README.md`, `CHANGELOG.md`,
  `AGENTS.md`, `forge.config.json`, `ruff.toml`
- Loop commit range `5b3e0a5~1..d1d26c3` (the sixteen `[rauf] NNN:` commits) plus `ff9d634`

Method: five parallel clean-room `forge-verifier` instances over disjoint CHECK-ID slices —
spec coverage + backlog completion (I01–I07), integration (I08–I12), testing (I16–I17),
code quality + documentation (I13–I15, I18–I20), runnability (I21–I23).

**Executed 23 of 23 checks. Results: 16 pass, 4 fail, 3 not-applicable.**

| CHECK | Result | CHECK | Result | CHECK | Result |
|---|---|---|---|---|---|
| I01 | pass | I09 | pass | I17 | pass |
| I02 | n/a | I10 | fail | I18 | fail |
| I03 | pass | I11 | pass | I19 | fail |
| I04 | pass | I12 | pass | I20 | fail |
| I05 | pass | I13 | pass | I21 | n/a |
| I06 | pass | I14 | pass | I22 | pass |
| I07 | pass | I15 | pass | I23 | n/a |
| I08 | pass | I16 | pass | | |

### Objective gate results (measured, not asserted)

| Gate | Result |
|---|---|
| `bash scripts/validate.sh` (`testCommand`) | **exit 0** — `All checks passed!` |
| `python3 -m pytest tests/ -q` | **1797 passed, 2 skipped** — 1799 collected |
| Collection vs `07-testing-strategy.md` §5.4 prediction (1799) | **delta 0** |
| `ruff check scripts/ eval/` (`typeCheckCommand`) | **exit 0** |
| `ruff check tests/` | 19 errors (E501×18, E402×1) — all pre-existing per `git blame`; `07` §3 gate 5 budget is ≤19, and `tests/` is outside `RUFF_TARGETS` by design |
| `scripts/build-adapters.py --check` | **exit 0** — no adapter drift |
| `scripts/check-spec-purity.py` | **PASS — 0 violations** |
| Traceability, all five suites | **rc 0** each; `verify-test-debt`: 46 requirements, 8 spec files |
| Backlog (`rauf-stable status --json`) | 16/16 `done`; 0 pending / in-progress / blocked / needs-human |

Both pytest skips are pre-existing, environment-gated, and out of this feature's scope
(`tests/test_forge_bootstrap.py:919` — `mypy` and `cargo-clippy` absent from the toolchain).
The feature's own conditional skip (REQ-BRIT-01's root-uid guard) did not fire; that item
executed and passed, which is the specified behavior.

Adversarial mutation probes were run against a real-copy scratch tree for the brittleness
and machinery-trim items: all five loosened exact-stderr sites go red under a message
substitution, all eight documented exit-1 evasion spellings are detected, both replaced
scanners are red on real violations and green on the prose shapes that used to
false-positive, and the 67→7 mutation-control collapse preserves its declared floor. No
coverage was silently deleted by any brittleness reduction.

## Summary
- Total findings: 14
- Gaps: 1
- Inconsistencies: 4
- Improvements: 9
- Errors: 0
- Blocking (errors + gaps): **1** — report records `findings-reported`

**The implementation is functionally sound.** Every one of the 16 backlog items marked
`done` has its acceptance criteria genuinely met against the code on disk — verified by
reading the implementation and executing the gates, not by the presence of a commit. All
findings below concern documentation, spec-inventory bookkeeping, and optional hardening.
The single blocking finding (V-001) is a missing user-facing documentation surface for a
CLI flag and config file that ship into six adapter bundles and the npm tarball.

## Findings

### V-001: `--allow-orphan` and `.traceability-allowlist` are undocumented user-facing surfaces
- **Severity:** gap
- **Location:** `README.md` §Validation → `### validate-traceability.py`; `CHANGELOG.md`
  §`## [Unreleased]`; `references/shared-conventions.md` (or the traceability paragraph of
  `references/verification-checklists/specs.md`)
- **Issue:** Commit `ff9d634` added a repeatable `--allow-orphan REQ-ID` CLI flag plus
  auto-discovery of a `<specs-dir>/.traceability-allowlist` config file to
  `scripts/validate-traceability.py`, and regenerated all six `adapters/*/scripts/` copies.
  Neither surface is documented anywhere outside the script's own module docstring and the
  stale `HANDOFF.md`. A `grep` across `README.md`, `CHANGELOG.md`, `docs/`, and
  `references/` returns zero mentions. Three concrete consequences:
  1. `README.md` still prints `python3 scripts/validate-traceability.py <prd-path>
     <specs-dir> [--json]` and says only "reports orphaned references" — now incomplete,
     because some orphans are subtracted. A user who runs `bash scripts/validate.sh` and
     sees `ALLOWED FOREIGN REFERENCES (3):` has no documented place to learn what that
     block means, that a `.traceability-allowlist` file exists, where it must live, or what
     its line format is.
  2. `installer/package.json` `files` is `["dist","adapters"]`, so the changed script lands
     in the npm tarball. Per `AGENTS.md` §"Does this change impact the published build?"
     that makes the missing `## [Unreleased]` CHANGELOG entry a runbook-step-2 omission.
  3. Canon instructs `forge-verify` to include orphaned references as findings, but never
     mentions the escape hatch. A suite that legitimately quotes an antecedent feature's
     ids — exactly this feature's own situation — will have them re-filed as findings round
     after round, because the resolving mechanism exists only in a commit message.
- **Suggested fix:** Three mechanical edits.
  1. In `README.md`, under `### validate-traceability.py`, replace the fenced usage line
     with:
     ```
     python3 scripts/validate-traceability.py <prd-path> <specs-dir> [--json]
                                              [--allow-orphan REQ-ID ...]
     ```
     and append after the existing "Validates requirement traceability…" paragraph:
     > A suite may legitimately mention a requirement id it does not own — most often when
     > a spec quotes an antecedent feature's test docstrings verbatim. Declare such ids with
     > a repeatable `--allow-orphan REQ-ID`, or list them one per line in
     > `<specs-dir>/.traceability-allowlist` (blank lines and `#` comments ignored), which
     > the validator discovers automatically. Allowed ids are subtracted from the orphan set
     > but printed under `ALLOWED FOREIGN REFERENCES`, never silently dropped; an allowlist
     > entry matching nothing is printed under `STALE ALLOWLIST ENTRIES` (advisory — it does
     > not fail the check). `--json` output gains `allowed_orphans` and
     > `unused_allowlist_entries`.
  2. Add a bullet under `## [Unreleased]` → `### Added` in `CHANGELOG.md` recording the
     flag, the allowlist file and its discovery rule, the two new JSON keys, and the fact
     that the ids live beside the suite rather than in the validator so the script stays
     generic across adapter bundles and consuming repos. While there, also record this
     feature's two shipped `scripts/forge-session.py` behavior narrowings — `state-complete
     --version` now rejects values below 1 on the write path, and `state-artifact --path`
     now enforces feature-directory containment — both of which also reach npm via the
     bundled `adapters/` tree and are likewise unrecorded.
  3. Add a two-sentence pointer to `references/shared-conventions.md` (or the traceability
     paragraph of `references/verification-checklists/specs.md`) stating that a requirement
     id a suite quotes but does not own may be declared in
     `{resolvedFeatureDir}/.traceability-allowlist`, and how allowed and stale entries are
     reported. **Do NOT put this in `skills/forge-verify/SKILL.md`** — its body measures
     300 lines against `check-spec-purity.py`'s `MAX_BODY_LINES = 300`, so any added line
     turns the hard spec-purity gate red. Re-run `python3 scripts/build-adapters.py` after
     any `references/` edit so the six adapter copies stay drift-free.
- **References:** `scripts/validate-traceability.py` lines 8–17, 38–42, 49–66, 77–89,
  145–154, 199–212; `specs/verify-test-debt/.traceability-allowlist`;
  `specs/verify-test-debt/TRACEABILITY.md` §"Coverage Verification"; `AGENTS.md`
  §"Publishing to npm"; `installer/package.json`; `scripts/validate.sh` step 8;
  `specs/verify-test-debt/01-architecture-layout.md` §3.1 (body-size headroom table);
  `scripts/check-spec-purity.py` lines 89–90, 630–643
- **Checklist:** CHECK-I12, CHECK-I18, CHECK-I20

### V-002: the spec inventory does not admit the `validate-traceability.py` change it shipped
- **Severity:** inconsistency
- **Location:** `specs/verify-test-debt/01-architecture-layout.md` §1, §2, §3.2;
  `specs/verify-test-debt/04-production-validations.md` §9 "Cross-cutting"
- **Issue:** Commit `ff9d634` added +74 lines to `scripts/validate-traceability.py` — a
  blocking gate (`validate.sh` step 8) fanned into every adapter bundle and every consuming
  repo — and three spec statements contradict it:
  - `01` §1: *"This feature adds **no** directory, package, module, class, CLI verb, flag,
    exit code, or JSON payload key."* `--allow-orphan` is a new CLI flag; `allowed_orphans`
    and `unused_allowlist_entries` are new JSON payload keys.
  - `01` §2's file tree lists exactly one file under `scripts/` (`forge-session.py`);
    `validate-traceability.py`, `.gitignore`, and
    `specs/verify-test-debt/.traceability-allowlist` appear in the feature's diff but in no
    inventory.
  - `04` §9's cross-cutting checkbox: *"No new exception type, `try`/`except`, CLI verb,
    flag, exit code, or payload key appears in the diff."* — literally false for the
    feature's diff, though true for `forge-session.py` and `run-compliance-eval.py` in
    isolation.

  Nothing is functionally broken (drift guard exit 0, suite green, all five suites rc 0).
  The defect is that the suite's own file-ownership map cannot be used to audit what
  shipped.
- **Suggested fix:** In `01-architecture-layout.md` §2, add to the `scripts/` block:
  `validate-traceability.py    EDIT — --allow-orphan flag, .traceability-allowlist
  auto-discovery, 2 JSON keys (out-of-band gate unblock)`; add `.gitignore` and
  `specs/verify-test-debt/.traceability-allowlist` to the same tree. Add a row to `01` §3.2
  attributing it, or a short "§3.4 Out-of-band gate unblock" subsection stating it is not
  owned by any REQ and was landed to make `validate.sh` green at HEAD. Rescope §1's
  sentence to *"…adds no CLI verb, flag, exit code, or JSON payload key **to
  `scripts/forge-session.py` or `eval/run-compliance-eval.py`**"* and make the same
  qualification in `04` §9's cross-cutting checkbox. **Do not revert the code** — the gate
  depends on it.
- **References:** commit `ff9d634`; `scripts/validate.sh` step 8;
  `specs/verify-test-debt/HANDOFF.md` (describes the change, but is stale and is not a spec
  artifact)
- **Checklist:** CHECK-I10, CHECK-I12

### V-003: the validator's documented exit-code contract is now false in the allowlisted case
- **Severity:** inconsistency
- **Location:** `scripts/validate-traceability.py` lines 19–22 (module docstring "Exit
  codes:" block) and line 222 (the summary line), plus the six generated
  `adapters/{claude,codex,copilot,cursor,gemini,pi}/scripts/validate-traceability.py` copies
- **Issue:** The block still reads `0 = all requirements covered, no orphans` / `1 = gaps or
  orphans found`. After `ff9d634` that is literally wrong: with `raw_orphaned` non-empty and
  every member allowlisted, `has_issues = bool(uncovered or orphaned)` is `False` and the
  script returns `0` **with orphans present**. Verified by running the shipped script
  against this feature: it printed `ALLOWED FOREIGN REFERENCES (3)` for `REQ-DEBT-04`,
  `REQ-REL-01`, `REQ-STATE-01` and exited `0`. The plain-text summary printed on that same
  run — `All requirements covered. No orphaned references.` — is the same overstatement
  rendered at runtime. Prose beside correct code, so it caps at `inconsistency`; but it is
  the documented contract of a CLI that ships into six adapter bundles and the npm tarball,
  and `scripts/validate.sh` branches purely on that exit code.
- **Suggested fix:** In `scripts/validate-traceability.py` **only** (never the `adapters/`
  copies — they are `GENERATED — DO NOT EDIT`), change the docstring block to:
  ```
  Exit codes:
      0 = all requirements covered; no orphans other than allowlisted ones
      1 = uncovered requirements, or orphans that are not allowlisted
      2 = file not found or read error
  ```
  Then change the summary line at the `if not has_issues:` branch from `"All requirements
  covered. No orphaned references."` to `"All requirements covered. No unallowlisted
  orphaned references."`. Regenerate with `python3 scripts/build-adapters.py` and re-run
  `bash scripts/validate.sh` so the drift guard stays green.
- **References:** `scripts/validate-traceability.py` lines 19–22, 164, 213–218, 222;
  `scripts/validate.sh` lines 348–353; `README.md` §"validate-traceability.py" (V-001)
- **Checklist:** CHECK-I14, CHECK-I20

### V-004: `--version`'s help text does not reflect its narrowed domain, and the spec's stated reason for leaving it alone does not apply to that flag
- **Severity:** inconsistency
- **Location:** `scripts/forge-session.py` lines 5710–5711
  (`p_comp.add_argument("--version", type=int, required=True, help="This stage's new
  version (integer)")`); `specs/verify-test-debt/04-production-validations.md` §1.2 (first
  bullet, "No argparse change")
- **Issue:** Two linked problems. (a) Spec §1.2 justifies leaving both flags' `help=`
  strings untouched with *"both already document the feature-dir-relative contract
  (§3.6)"*. That sentence's subjects are `--version` and `--path`, but "feature-dir-relative"
  is meaningless for `--version`, and the table it points at is in **§3.7**, not §3.6 — and
  that table's two rows are `--path` and `--findings-file`, not `--version`. So the decision
  to leave `--version`'s help unchanged rests on a rationale that was never about
  `--version`, and the cross-reference is off by one section. (b) The downstream effect:
  `state-complete --help` still says `(integer)` while the accepted domain is now integers
  ≥ 1, so a user is told `0` is acceptable and only discovers otherwise via exit 2. No test
  pins that help string (`grep "This stage's new version" tests/` → no hits), so amending it
  is cheap — but §9's checklist carries `- [ ] No help= string changed.`, making this a
  deliberate constraint a fresh agent must not silently override. `--path`'s help genuinely
  does state its contract, so no change is warranted there.
- **Suggested fix:** Apply the spec correction unconditionally; route the code change
  through a decision.
  1. **Apply directly:** in `04-production-validations.md` §1.2, replace *"Their `help=`
     strings are unchanged — both already document the feature-dir-relative contract
     (§3.6)."* with *"Their `help=` strings are unchanged. `--path` already states its
     feature-dir-relative contract (§3.7); `--version`'s help is left alone because this
     change narrows an existing flag's domain rather than giving it a new meaning."* — and
     fix the dangling `(§3.6)` citation to `(§3.7)`.
  2. **User decision (D3) before touching code:** either (i) keep `help="This stage's new
     version (integer)"` and leave §9's `No help= string changed.` checkbox intact, or (ii)
     change it to `help="This stage's new version (positive integer)"`, then strike that
     checkbox from §9, run `python3 scripts/build-adapters.py`, and run `bash
     scripts/validate.sh`. Option (ii) alters `--help` output shipped in all six adapter
     bundles and the npm tarball, which is why it is not applied unilaterally.
- **References:** `specs/verify-test-debt/04-production-validations.md` §1.2, §2.4, §2.7,
  §3.7 (lines 482–493), §9 checklist (line 976);
  `specs/verify-test-debt/00-core-definitions.md` §8.2; `scripts/forge-session.py` lines
  5691–5711
- **Checklist:** CHECK-I14, CHECK-I20

### V-005: `HANDOFF.md` still claims 0 of 16 backlog items are done
- **Severity:** inconsistency
- **Location:** `specs/verify-test-debt/HANDOFF.md` (whole file; written 2026-08-04 15:05,
  mid-run)
- **Issue:** The file was written before `forge-5-loop` finished and states that 0 of 16
  backlog items are complete, that three items are blocked on `needs_human`, and that 84
  files are uncommitted. `backlog.json` on disk marks all 16 `done` with `completedAt`
  stamps, the sixteen `[rauf] NNN:` commits are in history through `bcb5cff`, the tree is
  clean, and `rauf-stable status` reports 16/16. A fresh agent or a human opening the
  feature directory reads a document that directly contradicts the delivered state and could
  re-run the loop or conclude the feature is unimplemented. Documentation only — no runtime
  path or CLI output consumes it — so it caps at `inconsistency`.
- **Suggested fix:** Either delete `specs/verify-test-debt/HANDOFF.md`, or replace its
  status sections (§1, §2, §4, §5) with the post-loop reality and add a one-line header
  noting the document is a post-loop record, not an in-flight handoff. If replacing, state:
  all 16 backlog items are `done`; the ordered gate list from `07-testing-strategy.md` §3 is
  green (`pytest tests -q` → 1797 passed / 2 skipped = 1799 collected, matching `07` §5.4's
  prediction exactly; `build-adapters.py --check` exit 0; `check-spec-purity.py` 0
  violations; `ruff check scripts/ eval/` clean; `ruff check tests/` 19 errors at the
  accepted baseline; `bash scripts/validate.sh` "All checks passed!"); and the
  `CANONICAL_EXIT_SITES` import gate resolves with 9 entries. §6's known-process-gaps table
  is still accurate and should be kept.
- **References:** `specs/verify-test-debt/backlog.json`; `git log --oneline` `5b3e0a5`…
  `bcb5cff`; `specs/verify-test-debt/01-architecture-layout.md` §7;
  `specs/verify-test-debt/07-testing-strategy.md` §5.4
- **Checklist:** CHECK-I06

### V-006: the stale-allowlist safeguard is display-only and never reaches the gate's tally
- **Severity:** improvement
- **Location:** `scripts/validate-traceability.py` line 164
  (`has_issues = bool(uncovered or orphaned)`) and lines 208–212 (the `STALE ALLOWLIST
  ENTRIES` printer); `scripts/validate.sh` lines 348–353
- **Issue:** `unused_allowlist` is computed and printed, and surfaces in JSON as
  `unused_allowlist_entries`, but it is excluded from `has_issues` and from the JSON `valid`
  flag. `validate.sh` step 8 branches solely on the exit code, so a stale entry produces
  neither an `ERRORS` nor a `WARNINGS` increment and the gate reports `PASS` — the block
  scrolls past in a passing log. Under `--json` (the mode `forge-verify` itself uses) a
  reader seeing `"valid": true` has no reason to look further. The design intent recorded in
  `ff9d634`'s message — "an entry matching nothing is reported as STALE ALLOWLIST ENTRIES so
  the list cannot outlive the quotation that justified it" — is stronger than the mechanism
  delivers. Not a defect (nothing documented-and-required is absent), hence `improvement`.
- **Suggested fix:** Pick one and record the choice (decision D2). **(a) Recommended —
  make the intent honest without changing behavior:** reword the `STALE ALLOWLIST ENTRIES`
  line from `"{req_id}: allowlisted but no longer referenced"` to `"{req_id}: allowlisted
  but no longer referenced — remove it from <specs-dir>/.traceability-allowlist (advisory;
  does not fail this check)"`, and keep the "advisory" clause in the README paragraph added
  by V-001. **(b) Promote it to a gate warning:** in `scripts/validate.sh` step 8, capture
  the validator's stdout, and when it contains `STALE ALLOWLIST ENTRIES` emit `WARN: stale
  traceability allowlist entries in $specs_dir` and `WARNINGS=$((WARNINGS + 1))`, leaving
  PASS/FAIL routing on the exit code untouched. Do **not** fold it into exit 1 without an
  owner decision — that turns a documentation-hygiene signal into a merge blocker. If (b) is
  chosen and implemented as a new `--strict-allowlist` flag, extend V-002's inventory
  amendment to cover it.
- **References:** `scripts/validate-traceability.py` lines 145–154, 164, 175, 208–212;
  `scripts/validate.sh` lines 328–362; `specs/verify-test-debt/.traceability-allowlist`;
  `specs/verify-test-debt/TRACEABILITY.md` §"Coverage Verification"
- **Checklist:** CHECK-I10, CHECK-I14, CHECK-I20

### V-007: the new orphan-suppression path has zero test coverage in a blocking gate that ships to every adapter
- **Severity:** improvement
- **Location:** `scripts/validate-traceability.py` (`read_allowlist_file`, and the
  `allowed_orphans = sorted(raw_orphaned & allowlist)` subtraction in `main`); `tests/`
- **Issue:** `grep -rn "allowlist\|allow_orphan" tests/ --include="*.py"` returns no hit
  against this script. `validate-traceability.py` has **no** test module at all; its only
  appearance under `tests/` is as a byte-copy inside `tests/fixtures/minimal-canon/`, which
  `test_build_adapters.py` compares for drift and never executes. The new code *subtracts
  ids from the orphan set*, i.e. it can turn a red gate green — the highest-risk shape of
  untested code in a validator. A typo in `read_allowlist_file`'s comment-stripping or a
  widened match would silently suppress real orphans in every consuming repo.
- **Suggested fix:** Add `tests/test_validate_traceability.py` with `tmp_path` fixtures
  covering: (a) an id in `.traceability-allowlist` moves from `orphaned_references` to
  `allowed_orphans` and `valid` stays `true`; (b) an id **not** in the allowlist stays in
  `orphaned_references` and the process exits **1**; (c) an allowlist entry matching nothing
  appears in `unused_allowlist_entries`; (d) `--allow-orphan` on the command line merges
  with the file; (e) comment/blank-line stripping in the allowlist file. **Mandatory
  companion edit (REQ-TRIAL-06):** adding N collected items invalidates
  `07-testing-strategy.md` §5.2 and §5.4 — recompute the expected total and the per-file
  table **in the same edit**, or the next verifier files a stale-derived-figure finding. If
  the decision is instead to leave it untested, record that as a declared non-goal in
  `00-core-definitions.md` §10.3 so a later round resolves it against a position rather than
  re-deriving it.
- **References:** `scripts/validate.sh` step 8 (blocking);
  `specs/verify-test-debt/07-testing-strategy.md` §5.4, §7.6
- **Checklist:** CHECK-I12

### V-008: two helpers added by this feature ship without docstrings
- **Severity:** improvement
- **Location:** `tests/test_stage_exit_protocol.py` line 294,
  `def _site(skill: str) -> CanonicalExitSite:` (introduced by `ec4e1e9`, `[rauf] 006`);
  `scripts/validate-traceability.py` line 49,
  `def read_allowlist_file(specs_dir: Path) -> set[str]:` (introduced by `ff9d634`)
- **Issue:** `00-core-definitions.md` line 42 lists, under "Project conventions this feature
  follows without deviation", *"Google-style docstrings with `Args:` / `Returns:` /
  `Raises:` on every public function."* (1) `_site` has no docstring at all and raises
  `AssertionError` on an unknown skill — an undocumented failure mode. Its two module-level
  siblings in that file also lack docstrings, but `git blame` shows those came from
  `9ee7ec1`, i.e. pre-existing; `_site` is this feature's own addition, and every *other*
  helper this feature added carries a full one. (2) `read_allowlist_file` is a **public**
  module-level function in a shipped script with a two-line prose docstring and no `Args:`
  or `Returns:` section — even though the neighbouring new code (`_validated_findings_file`
  in `forge-session.py`) was held to the full format.
- **Suggested fix:** Add to `tests/test_stage_exit_protocol.py` immediately below
  `def _site(skill: str) -> CanonicalExitSite:`:
  ```python
      """Return the canonical exit site for ``skill``.

      Args:
          skill: The skill id, as it appears in ``CANONICAL_EXIT_SITES``.

      Returns:
          The matching site entry.

      Raises:
          AssertionError: ``skill`` is not a covered exit site.
      """
  ```
  And in `scripts/validate-traceability.py`, extend `read_allowlist_file`'s docstring to the
  Google-style shape, keeping the existing body sentence and adding:
  ```
      Args:
          specs_dir: The suite's specs directory, searched for the allowlist file.

      Returns:
          The declared foreign requirement ids; an empty set when the file is
          absent or unreadable.
  ```
  Regenerate adapters after the second edit. Do **not** retrofit `_session_source` or
  `_surface_is_unmutated` under this finding — they are pre-existing and outside this
  feature's delta. Neither docstring may carry a count (REQ-CANON-03).
- **References:** `specs/verify-test-debt/00-core-definitions.md` line 42;
  `scripts/forge-session.py` `_validated_findings_file` (the format exemplar, prescribed
  verbatim in `04-production-validations.md` §3.4); `tests/test_auto_verify.py` `_corrupt`
  (lines 890–902)
- **Checklist:** CHECK-I19

### V-009: the mandated fence-aware heading index has no shipped regression test
- **Severity:** improvement
- **Location:** `tests/test_state_verb_call_sites.py`, `_heading_lines` (lines 130–145) and
  the `(index, index)` fallback in `_sites_in` (lines ~235–275)
- **Issue:** Degrading `_heading_lines` to drop its `flags[index]` consultation — i.e. the
  naive `^#{1,6} ` scan that `03-machinery-trim.md` §4.2 declares must not be used — leaves
  `tests/test_state_verb_call_sites.py` fully green (9 passed) in a scratch copy. The reason
  is structural: canon currently contains **zero** unfenced `state-*` call sites, so
  `_sites_in`'s `(index, index)` fallback — the only path on which an in-fence `#` line can
  truncate a region below its mandate — is never taken, even though canon contains 25
  in-fence lines matching `HEADING_RE`. `03` §13's checkbox is satisfied *at verification
  time* (zero fence-flagged heading indices across all canon files), but no assertion in the
  tree preserves it. This is **not** a declared non-goal: `03` §9's non-goals are the
  residual census, per-site exemptions, and unenumerated evasion shapes — fence-awareness is
  declared mandatory. The omission is a consequence of `03` §11/§13 budgeting the file at
  exactly 9 test functions, leaving no slot.
- **Suggested fix:** In `tests/test_state_verb_call_sites.py`, add one test function
  immediately after `test_the_epic_guard_is_not_vacuous` and before the `_REGION_PROBE_VERB`
  constant:
  ```python
  def test_the_heading_index_never_reads_a_fenced_comment_as_a_heading():
      """A `#` line inside a fence is a comment in the fenced language, not a boundary.

      The region's lower bound degrades to the call's own line for an unfenced
      `state-*` call, and there a fenced `#` line would truncate the region below
      the mandate that governs it.
      """
      scanned = 0
      for path in _canon_files():
          lines = read(path).splitlines()
          flags = _fence_flags(lines)
          headings = _heading_lines(lines, flags)
          fenced = [i for i, line in enumerate(lines) if flags[i] and HEADING_RE.match(line)]
          scanned += len(fenced)
          leaked = sorted(set(headings) & set(fenced))
          assert not leaked, (
              f"{path.relative_to(REPO_ROOT).as_posix()}: heading index admitted "
              f"fenced comment line(s) {[i + 1 for i in leaked]}"
          )
      assert scanned, "no fenced `#` line was scanned — this control asserts nothing"
  ```
  The trailing `assert scanned` is the non-vacuity floor. **Mandatory companion edits in the
  same commit (REQ-TRIAL-06):** the file moves from 9 to 10 functions/items and the suite
  total from 1799 to 1800 — update `03-machinery-trim.md` §11 (the
  `test_state_verb_call_sites.py` row) and §13's REQ-TRIM-04 checkbox ("contains **9** test
  functions" → **10**), and `07-testing-strategy.md` §5.2 (per-file table), §5.4 (the
  arithmetic and the 1799 → 1800 total), and §6's bullet naming the call-sites guard. Keep
  the docstring free of counts (REQ-CANON-03), and do not introduce
  `skipif(`/`importorskip(`/`pytest.skip(` into this file — `03` §7's
  `test_this_guard_is_not_skippable` scans this file's own source.
- **References:** `specs/verify-test-debt/03-machinery-trim.md` §4.2, §4.5, §4.8, §9, §11,
  §13; `specs/verify-test-debt/07-testing-strategy.md` §5.2, §5.4, §6;
  `specs/verify-test-debt/00-core-definitions.md` §6.3
- **Checklist:** CHECK-I17

### V-010: item 002's new test reintroduces an exact full-equality stderr comparison
- **Severity:** improvement
- **Location:** `tests/test_state_verbs.py` lines 897–899, inside
  `test_state_complete_rejects_a_non_positive_version_before_mutation`
- **Issue:** The assertion is `assert result.stderr.strip() == (f"Error: --version must be a
  positive integer; got {raw}")` — a full string-equality comparison against CLI stderr.
  Item 013 (REQ-BRIT-04) converted the last five such sites in this repo to substring/regex
  form precisely because a wording change to an error message breaks a test whose subject is
  behavior, not prose. This site is **not** in the `00-core-definitions.md` §9.1 roster, so
  item 013's AC2 and AC5 are both satisfied as written, and the shape is prescribed by
  `05-coverage-backfill.md` §3.2 — a deliberate, spec-sanctioned choice, not a defect.
  Recorded only because the same feature that removes 11 exact-equality comparisons adds a
  twelfth, leaving the repo's exact-stderr count at 1 rather than 0.
- **Suggested fix:** Optional, and only if the repo wants zero exact-stderr comparisons.
  Replace the single assertion with the substring shape used by the four converted sites in
  the same file:
  ```python
  stderr = result.stderr.strip()
  assert stderr.startswith("Error:"), stderr
  assert "--version" in stderr, f"the flag is not named: {stderr!r}"
  assert "positive integer" in stderr, stderr
  assert raw in stderr, f"the rejected value {raw!r} is not named: {stderr!r}"
  ```
  If applied, also update `05-coverage-backfill.md` §3.2's code block in the same edit so
  the spec and the shipped test do not diverge. If not applied, add one sentence to
  `06-brittleness-batch.md` §1.2 recording this site as a deliberate exception to
  REQ-BRIT-04. Either resolution is acceptable; recording the position is what matters.
- **References:** `specs/verify-test-debt/05-coverage-backfill.md` §3.2;
  `specs/verify-test-debt/00-core-definitions.md` §9.1;
  `specs/verify-test-debt/06-brittleness-batch.md` §1.2, §5.1–§5.6; backlog item 013 AC2/AC5
- **Checklist:** CHECK-I05, CHECK-I07

### V-011: item 016 AC11's absolute wording is contradicted by item 004's own spec-prescribed comment
- **Severity:** improvement
- **Location:** `specs/verify-test-debt/backlog.json`, item `016`, `acceptanceCriteria`
  entry 11; the subject is `tests/test_compliance_eval.py` lines 340–342 (the `#:` comment
  above `SPEC_PRELUDE_CRITERIA`, reading `#: The four prelude criteria, spelled out here
  rather than imported.`)
- **Issue:** Item 016 AC11 states absolutely: "No comment, docstring, or test narration in
  the feature's diff carries a count, 'measured', 'confirmed', or any other empirical
  claim" (REQ-CANON-03). The comment above carries the count "four", and it is inside the
  feature's diff. It is not a drift-prone empirical claim — it is a definitional count
  sitting two lines above the four-element literal it describes, and it is prescribed by
  `05-coverage-backfill.md` §4.3, the same document item 004 AC2 binds the test to. Item 004
  AC2 additionally mandates the function name
  `test_the_prelude_scorer_returns_exactly_the_four_specified_criteria`, which also spells
  the count. AC11 as literally worded is therefore unsatisfiable alongside items 004/005's
  own prescribed ACs. A specification-side wording tension with zero runtime consequence.
- **Suggested fix:** Amend the AC, not the test. In `specs/verify-test-debt/backlog.json`,
  item `016`, `acceptanceCriteria` entry 11, replace the absolute wording with a scoped one:
  *"No comment, docstring, or test narration in the feature's diff carries a measurement — a
  suite/site/item count, 'measured', 'confirmed', or any figure that must be recomputed when
  a roster changes. A count that restates an adjacent literal in the same file (e.g. 'the
  four prelude criteria' above a four-element tuple) is definitional, not empirical, and is
  permitted."* Leave `tests/test_compliance_eval.py` lines 340–342 and the test name exactly
  as they are — both are prescribed by `05-coverage-backfill.md` §4.3 and backlog item 004
  AC2, and editing them would break those ACs.
- **References:** `specs/verify-test-debt/backlog.json` item 016 AC11 and item 004 AC2;
  `specs/verify-test-debt/05-coverage-backfill.md` §4.3; `specs/verify-test-debt/PRD.md`
  REQ-CANON-03; `eval/run-compliance-eval.py` lines 1690–1698
- **Checklist:** CHECK-I05, CHECK-I07

### V-012: a stray `backlog.json.bak` sits beside the live backlog
- **Severity:** improvement
- **Location:** `specs/verify-test-debt/backlog.json.bak` (70,621 bytes, mtime identical to
  `backlog.json`)
- **Issue:** A near-identical backup copy of the backlog is present in the resolved feature
  directory. Nothing in `01-architecture-layout.md` §2 or `07-testing-strategy.md` provides
  for it, and it is not an artifact any pipeline stage reads or writes. Its risk is
  confusion, not behavior: a later verifier, a `forge-fix` pass, or a human grepping the
  feature directory for item status can match the stale copy instead of `backlog.json` and
  act on superseded statuses. No gate reads it.
- **Suggested fix:** Delete `specs/verify-test-debt/backlog.json.bak`. First run
  `git ls-files --error-unmatch specs/verify-test-debt/backlog.json.bak` to determine
  whether it is tracked: if tracked, remove it with `git rm` and commit; if untracked,
  delete it from the working tree and add `*.json.bak` to `.gitignore` so a future loop run
  does not leave another one. Do not modify `specs/verify-test-debt/backlog.json` — it is
  the live artifact and is correct (16/16 `done`).
- **References:** `specs/verify-test-debt/backlog.json`;
  `specs/verify-test-debt/01-architecture-layout.md` §2, §9
- **Checklist:** CHECK-I06

### V-013: no `smokeCommand` configured — "clean" does not yet mean "it runs"
- **Severity:** improvement (CHECK-I21 `not-applicable` degradation — advisory, non-blocking)
- **Location:** `forge.config.json`, key `smokeCommand` (currently `null`)
- **Issue:** CHECK-I21 requires executing the configured `smokeCommand` and passing iff exit
  0. `smokeCommand` is `null`, so the check degrades to advisory not-applicable exactly as a
  null `typeCheckCommand` would. No smoke was fabricated, guessed, or run. Consequence:
  every other impl check is a static read, a lint, or a "tests exist" assertion — nothing
  asserts that the assembled CLI boots and completes one happy-path invocation from a cold
  process. That gap is live for this feature specifically: REQ-FIX-01 and REQ-SEC-01 are
  behavior changes on shipped CLI paths whose only in-process proof is `pytest`.
- **Suggested fix:** This is a **user decision** (D1) — do not auto-populate. Ask whether to
  set `smokeCommand` in `forge.config.json`. If yes, the natural candidate for this repo is
  a cold `python3` subprocess driving a real CLI end-to-end (e.g. a read-only
  `python3 scripts/forge-session.py doctor --json`), or reusing `bash scripts/validate.sh`.
  Per CHECK-I21's #149 clause, whatever is chosen must exercise the same runtime mode the
  bugs manifest in — here the cold process, not an in-process import — because REQ-FIX-01's
  original defect (`state-complete --version 0` writing `"version": 0`) is only observable
  as a real process exit code. Record which runtime the smoke exercised in future reports.
  If the user declines, leave `smokeCommand: null`; this advisory stands as the record.
- **References:** `specs/verify-test-debt/PRD.md` §3.3 (REQ-FIX-01, REQ-SEC-01), §4.1
  (REQ-QUAL-03); `specs/verify-test-debt/01-architecture-layout.md` §7; `forge.config.json`
- **Checklist:** CHECK-I21

### V-014: no universal bootstrap entry and no heavy import graph — the eager-init heuristic does not apply
- **Severity:** improvement (CHECK-I23 `not-applicable` degradation — report-only, explicitly
  never a hard fail)
- **Location:** repo-wide; `references/stacks/python.md` §"Runtime Entrypoints &
  Bootstrap-Wiring Sites"
- **Issue:** CHECK-I23 fires only when a runtime-required init is wired into a universal
  startup entry **and** pulls a heavy server-only graph. Neither precondition holds. **No
  universal bootstrap entry:** `find` returns zero first-party `__init__.py` (all hits are
  inside `.venv/`); there is no `pyproject.toml` or `setup.py`, hence no
  `[project.scripts]` console-script target; no web framework is present. `tests/conftest.py`
  exists but bootstraps no production graph — stdlib plus `pytest` only — and is listed
  UNCHANGED and out of scope by `01-architecture-layout.md` §2, §9. **No heavy graph:** a
  grep for every marker the profile names (`sqlalchemy`, `psycopg`, `pymongo`, `redis`,
  `celery`, `rq`, `kafka`, `opentelemetry`, `sentry_sdk`, `fastapi`, `django`, `flask`,
  `lifespan`, `on_event(`) across `scripts/`, `eval/`, `tests/` returns zero matches. All
  nine first-party scripts are `if __name__ == "__main__":` CLIs over stdlib.
- **Suggested fix:** None — report, do not repair. Recorded so a later verifier resolves
  CHECK-I23 against a stated position instead of re-deriving it or inventing a lazy-init
  refactor no requirement asked for. Re-evaluate only if a first-party package
  `__init__.py`, a `pyproject.toml` `[project.scripts]` target, or a long-running server
  process is ever introduced.
- **References:** `references/stacks/python.md`;
  `specs/verify-test-debt/01-architecture-layout.md` §1, §2, §8; `tests/conftest.py`
- **Checklist:** CHECK-I23

## Deliberately not filed

Recorded so a later round resolves these against a stated position rather than re-deriving
them:

- **`PRELUDE_CRITERIA`'s doc-comment** in `eval/run-compliance-eval.py` says "Declared once
  so the scorer, the report, and the tests all name the same set", but `score_prelude` does
  not read it. This is (a) comment-only, capped at `inconsistency` by the severity floor,
  and (b) the **verbatim text the specs prescribe** — `04-production-validations.md` §5.3
  and `05-coverage-backfill.md` §4.2 both quote it as required content, mirroring the
  pre-existing `BRANCH_CRITERIA` comment, and §5.3 explains the deliberate decoupling.
  Filing it would be exactly the narration churn REQ-TRIAL-01 exists to eliminate.
- **`CHECK-I22` on `PRELUDE_CRITERIA`.** Referenced only from
  `tests/test_compliance_eval.py`, but `04` §5.3 marks it a declaration, not a
  runtime-required symbol, so the non-test-caller rule does not apply. The two symbols that
  *are* runtime-required — `_require_positive_int` and `_validated_findings_file(…, label=)`
   — both have confirmed non-test call sites reachable from `main()`.
- **`ruff check tests/` 19 errors.** All pre-existing per `git blame`, and `tests/` is
  outside `RUFF_TARGETS` by design (`ruff.toml` comment, `scripts/validate.sh` line 317).
  `07` §3 gate 5 sets the budget at ≤19; a pre-feature tree reconstructed at `5b3e0a5~1`
  measured the same 19, so the feature is non-increasing.
- **`docs/architecture/verify-test-debt/` absence.** That is `forge-6-docs`'s job; the
  feature is at `forge-5-loop` complete.
- **`adapters/pi/scripts/forge-session.py` divergence from canon** (68 lines) — entirely the
  documented `/feature-forge:` → `/skill:` host-term translation, and it carries both of
  this feature's edits.

## Fix Execution Plan

### User Decisions Required

All four were answered by the user on 2026-08-04, before any step was applied.

- **D1 (V-013) — configure a `smokeCommand`?** **RESOLVED: set it to
  `python3 scripts/forge-session.py doctor --json`.** Verified to exist and be read-only
  before being offered. Runs in a fresh process and exits 0 on a healthy tree, so it catches
  the class `validate.sh` cannot — a CLI that imports fine under pytest but is broken as a
  real entrypoint. Applied in Step 7.
- **D2 (V-006) — stale-allowlist semantics.** **RESOLVED: option (a), report-only wording.**
  The printer line states that staleness is advisory and does not fail the check; zero
  behavior change, no risk to consuming repos. Applied in Step 5.
- **D3 (V-004b) — change `--version`'s `help=` string?** **RESOLVED: option (i), keep it
  as-is.** `04` §9's `No help= string changed.` checkbox stays intact and no code changes.
  The spec-prose correction in V-004 item 1 is still applied unconditionally. Rationale: a
  user passing `0` already gets a clear exit-2 message, so the wart is minor, and changing
  `--help` output shipped to six adapter bundles and the npm tarball is scope creep for a
  test-debt feature. Step 3 therefore applies its spec half only.
- **D4 (V-007, V-009, V-010) — write the optional tests, or record non-goals?**
  **RESOLVED: V-007 only.** V-009 and V-010 are declined and recorded as non-goals in
  `00-core-definitions.md` §10.3, per this section's own instruction that a declined item
  must carry a stated position rather than be left silent. Step 6 therefore writes the
  allowlist tests and recomputes `07` §5.2/§5.4, and does **not** touch
  `test_state_verb_call_sites.py` or the `test_state_verbs.py` assertion. V-008 (docstrings)
  is not decision-gated — it adds no collected items — and is applied regardless.

Steps 1 and 2 need no decision and clear the only blocking finding.

### Execution Steps

Apply in order. Each step is self-contained.

#### Step 1: Document the allowlist surface in README and CHANGELOG
- **Files:** `README.md`, `CHANGELOG.md`
- **Addresses:** V-001 (parts 1 and 2)
- **Checklist:** CHECK-I18, CHECK-I20
- **Action:** Apply V-001's suggested-fix items 1 and 2 verbatim — the amended usage fence
  and new paragraph under `### validate-traceability.py`, and the `## [Unreleased]` →
  `### Added` bullet covering the flag, the allowlist file and its discovery rule, the two
  new JSON keys, and the two `forge-session.py` behavior narrowings.
- **Depends on:** none
- **Rationale:** This is the blocking finding and the only one gating the stage. It touches
  no code and cannot break a gate.

#### Step 2: Add the canon pointer for the allowlist lever, then regenerate adapters
- **Files:** `references/shared-conventions.md` (or
  `references/verification-checklists/specs.md`), then `adapters/**` via
  `python3 scripts/build-adapters.py`
- **Addresses:** V-001 (part 3)
- **Checklist:** CHECK-I12, CHECK-I20
- **Action:** Add the two-sentence pointer from V-001 item 3. **Never** add it to
  `skills/forge-verify/SKILL.md` — its body is at the 300-line `MAX_BODY_LINES` cap and any
  added line turns the spec-purity gate red. Then run `python3 scripts/build-adapters.py`
  followed by `python3 scripts/build-adapters.py --check` to confirm exit 0.
- **Depends on:** none
- **Rationale:** Separated from Step 1 because it is the only part of V-001 that touches a
  generated tree and must be followed by a regeneration.

#### Step 3: Correct the spec inventory and the two prose contracts
- **Files:** `specs/verify-test-debt/01-architecture-layout.md` (§1, §2, §3.2),
  `specs/verify-test-debt/04-production-validations.md` (§1.2, §9),
  `scripts/validate-traceability.py` (docstring lines 19–22 and the summary line at 222),
  and — only under D3 option (ii) — `scripts/forge-session.py` line 5711
- **Addresses:** V-002, V-003, V-004
- **Checklist:** CHECK-I10, CHECK-I12, CHECK-I14, CHECK-I20
- **Action:** Apply V-002's inventory amendment; apply V-004's spec correction (item 1,
  including the `§3.6` → `§3.7` citation fix) unconditionally; apply V-003's docstring and
  summary-line rewording. Edit `scripts/validate-traceability.py` only — never the
  `adapters/` copies, which are `GENERATED — DO NOT EDIT`. Apply the D3 code change only if
  the user chose option (ii), and strike `04` §9's `No help= string changed.` checkbox in
  the same edit if so. Finish with `python3 scripts/build-adapters.py` and
  `bash scripts/validate.sh`.
- **Depends on:** Step 2 (so a single adapter regeneration covers both, if you prefer to
  defer regeneration to here)
- **Rationale:** Grouped because all three are prose-contract corrections to the same
  shipped script and its owning spec documents; ordering them after Step 2 lets one
  `build-adapters.py` run cover every generated-tree change.

#### Step 4: Retire or rewrite the stale handoff, and remove the stray backlog backup
- **Files:** `specs/verify-test-debt/HANDOFF.md`, `specs/verify-test-debt/backlog.json.bak`,
  and `.gitignore` if the backup is untracked
- **Addresses:** V-005, V-012
- **Checklist:** CHECK-I06
- **Action:** Apply V-005 (delete, or rewrite §1/§2/§4/§5 to the post-loop reality and add
  the post-loop-record header; keep §6's known-process-gaps table). Then apply V-012 — check
  `git ls-files --error-unmatch specs/verify-test-debt/backlog.json.bak` first and use
  `git rm` if tracked, otherwise delete and add `*.json.bak` to `.gitignore`. Do not touch
  `backlog.json`.
- **Depends on:** none
- **Rationale:** Both are feature-directory hygiene; grouping them keeps one commit for
  "leave the directory readable to the next agent".

#### Step 5: Settle the stale-allowlist semantics
- **Files:** `scripts/validate-traceability.py` (the `STALE ALLOWLIST ENTRIES` printer), or
  that file plus `scripts/validate.sh` step 8 under option (b)
- **Addresses:** V-006
- **Checklist:** CHECK-I10, CHECK-I14, CHECK-I20
- **Action:** Under D2 option (a), reword the printer line to carry the advisory clause.
  Under option (b), add the `WARNINGS` increment in `validate.sh` step 8 while leaving
  PASS/FAIL routing on the exit code. If option (b) is implemented as a new
  `--strict-allowlist` flag, extend Step 3's inventory amendment to cover it. Regenerate
  adapters and re-run `bash scripts/validate.sh`.
- **Depends on:** Step 3 (shares the file and the inventory amendment), D2
- **Rationale:** Must follow the inventory correction so a newly added flag lands in an
  inventory that already admits the file.

#### Step 6: Optional test backfill and docstrings, with mandatory count recomputation
- **Files:** new `tests/test_validate_traceability.py`;
  `tests/test_state_verb_call_sites.py`; `tests/test_stage_exit_protocol.py` (line 294);
  `tests/test_state_verbs.py` (lines 897–899); `scripts/validate-traceability.py`
  (`read_allowlist_file` docstring); `specs/verify-test-debt/03-machinery-trim.md` §11, §13;
  `specs/verify-test-debt/07-testing-strategy.md` §5.2, §5.4, §6;
  `specs/verify-test-debt/05-coverage-backfill.md` §3.2 or
  `specs/verify-test-debt/06-brittleness-batch.md` §1.2;
  `specs/verify-test-debt/00-core-definitions.md` §10.3
- **Addresses:** V-007, V-008, V-009, V-010
- **Checklist:** CHECK-I12, CHECK-I17, CHECK-I19
- **Action:** For each item D4 approves, apply its suggested fix. **REQ-TRIAL-06 is
  mandatory and unforgiving here:** every added collected item invalidates the derived
  figures, so recompute `07-testing-strategy.md` §5.2's per-file table and §5.4's arithmetic
  and total, and `03-machinery-trim.md` §11/§13 where the call-sites file's function count
  appears — **in the same commit as the test**, never in a follow-up. V-009 alone moves the
  total 1799 → 1800. Keep every new docstring free of counts (REQ-CANON-03), and do not
  introduce `skipif(`/`importorskip(`/`pytest.skip(` into `test_state_verb_call_sites.py`.
  For any item D4 declines, record the non-goal in `00-core-definitions.md` §10.3 instead.
  Finish with `python3 -m pytest tests -q` and `bash scripts/validate.sh`.
- **Depends on:** Steps 3 and 5 (V-007's tests should assert the settled exit-code and
  stale-entry semantics), D4
- **Rationale:** Last because it is the only step that changes the suite's collected count,
  and doing it after the semantics are settled avoids writing tests against a contract that
  is about to change.

#### Step 7: Amend item 016 AC11 and, under D1, set `smokeCommand`
- **Files:** `specs/verify-test-debt/backlog.json` (item 016, AC 11); `forge.config.json`
  (only under D1)
- **Addresses:** V-011, V-013
- **Checklist:** CHECK-I05, CHECK-I07, CHECK-I21
- **Action:** Replace item 016 AC11's absolute wording with V-011's scoped wording. Leave
  `tests/test_compliance_eval.py` and the prescribed test name untouched. Under D1, write
  only the user's chosen `smokeCommand` value into `forge.config.json`, changing no other
  key; if the user declined, make no edit.
- **Depends on:** none
- **Rationale:** Separated because it edits the backlog artifact and the project config —
  neither of which any other step touches — and because V-013 is contingent on a user
  answer that may never come.

## Fix Progress

- Step 1: [APPLIED] 2026-08-04 — README `### validate-traceability.py` usage fence gained `[--allow-orphan REQ-ID ...]` plus a paragraph covering the allowlist file, its line format, the `ALLOWED FOREIGN REFERENCES` / `STALE ALLOWLIST ENTRIES` reporting, the advisory status of staleness, and the two new `--json` keys. CHANGELOG `## [Unreleased]` → `### Added` gained two bullets: the allowlist mechanism (including why the ids live beside the suite rather than in the validator), and the two shipped `forge-session.py` domain narrowings (`--version` ≥ 1, `--path` containment) that also reach npm via `adapters/`.
- Step 2: [APPLIED] 2026-08-04 — added the canon pointer as a block quote under `### Traceability` in `skills/forge-verify/references/verification-checklists/specs.md`, immediately after CHECK-S38 (the check that files orphans). Placed there rather than in `references/shared-conventions.md` because that file loads on every skill invocation while this material is only needed by a verifier in specs mode; `MAX_BODY_LINES` was confirmed to bind skill bodies only, so `references/` carries no cap. `skills/forge-verify/SKILL.md` was left untouched (300/300). `python3 scripts/build-adapters.py` re-run; `--check` exits 0.
- Step 3: [APPLIED] 2026-08-04 — V-002: `01-architecture-layout.md` §1 rescoped to the two files §3.2 owns, §2 tree gained `validate-traceability.py`, `.traceability-allowlist` and `.gitignore`, and a new §3.4 "Out-of-band gate unblock" records the change, why it was necessary (the shared final AC was a green `validate.sh`, so one red gate halted the whole backlog) and why the ids are not hardcoded. `04-production-validations.md` §9's cross-cutting checkbox rescoped to the same two files with a pointer to §3.4. V-004: §1.2's rationale rewritten — `--path` cites §3.7 (the dangling `§3.6` was wrong) and `--version`'s exemption now rests on "narrows an existing flag's domain" rather than a feature-dir-relative claim that never applied to it. V-003: docstring exit-code block and the `if not has_issues` summary line now state the allowlisted case truthfully. Per D3, no `help=` string changed and `04` §9's checkbox stands.
- Step 4: [APPLIED] 2026-08-04 — V-005: `HANDOFF.md` rewritten as a post-loop record with an explicit header saying so; §1 now states 16/16 done with the green gate table, §2 keeps the stall diagnosis and its resolution as history, and the process-gaps table survives (renumbered §3, #195 marked resolved). V-012: `backlog.json.bak` diffed before deletion and confirmed strictly stale (one item `in_progress`/`completedAt: null` where the live file has it `done`) — exactly the confusion risk V-012 describes; removed, and `*.json.bak` added to `.gitignore`.
- Step 5: [APPLIED] 2026-08-04 — V-006 under D2 option (a): the `STALE ALLOWLIST ENTRIES` line now names the file to prune and states "advisory; does not fail this check". Exit-code routing unchanged, so no consuming repo turns red on upgrade.
- Step 6: [APPLIED] 2026-08-04 — V-008: Google-style docstrings added to `_site` (documenting its `AssertionError`) and `read_allowlist_file`; the two pre-existing undocumented siblings left alone as out-of-delta. V-007: new `tests/test_validate_traceability.py`, stdlib-only, driving the real CLI out-of-process so its exit codes are the ones `validate.sh` step 8 branches on. Acceptance evidence — non-vacuity established by mutation, not by inspection: short-circuiting `read_allowlist_file` to `set()` fails 4 of the 5, and the survivor is `test_an_undeclared_orphan_still_fails_the_gate`, which deliberately exercises no allowlist. The mutated file was restored and the restore verified by `git diff` before proceeding. REQ-TRIAL-06 discharged in the same pass: `07` §5.2 gained the new row, §5.4 carries the `1799 → +5 → 1804` arithmetic, and a new §5.5 records the addition. V-009 and V-010 declined per D4 and recorded as positions in `00-core-definitions.md` §10.3, each with the condition that would make it worth revisiting.
- Step 7: [APPLIED] 2026-08-04 — V-011: item 016 AC11 rescoped from "carries a count" to "carries a *measurement*", explicitly permitting a definitional count that restates an adjacent literal; `tests/test_compliance_eval.py` and the prescribed test name left untouched, since both are bound by `05` §4.3 and item 004 AC2. V-013 under D1: `smokeCommand` set to `python3 scripts/forge-session.py doctor --json`, verified to exit 0 before being written; no other config key touched.

### Verification of this fix pass

Adapters were regenerated after the `validate-traceability.py` edits — the first full run
caught the drift (`FAIL: adapters/ is out of date`) and it was fixed before recording.

| Gate | Result |
|---|---|
| `bash scripts/validate.sh` | **exit 0** — `All checks passed!`, 38 gates |
| `python3 -m pytest tests` | **1802 passed, 2 skipped** — 1804 collected |
| Collected vs the recomputed `07` §5.4 figure (1804) | **delta 0** |
| `ruff check scripts/ eval/` | exit 0 |
| `ruff check tests/` | 19 — unchanged; the new test file added none |
| `python3 scripts/build-adapters.py --check` | exit 0 |
| `python3 scripts/forge-session.py doctor --json` (new `smokeCommand`) | **exit 0** |
