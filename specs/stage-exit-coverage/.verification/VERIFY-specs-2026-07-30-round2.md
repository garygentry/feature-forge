# Verification Report: stage-exit-coverage (specs) — Round 2

Date: 2026-07-30
Pipeline Stage: forge-3-specs (re-verify after fix commit `8826e56`)
Mode: specs, require-clean
Artifacts Reviewed: `PRD.md`, `tech-spec.md`, `00-core-definitions.md`, `01-architecture-layout.md`,
`02-stage-exit-routing.md`, `03-verification-state.md`, `04-skill-integration.md`,
`05-config-and-distribution.md`, `06-compliance-and-coverage.md`, `07-testing-strategy.md`,
`TRACEABILITY.md`, `.pipeline-state.json`, `.verification/VERIFY-specs-2026-07-30.md`, plus live
source (`scripts/forge-session.py`, `.gitignore`, `references/templates/specs-hygiene/`)

## Summary

- Checks executed: 38 of 38 — 28 pass, 9 fail, 1 not-applicable
- Total findings: 10 (2 gaps, 5 inconsistencies, 3 errors)
- Round-1 findings resolved: 5 of 6 (V-006 not resolved)
- Findings newly introduced by the round-1 fixes: 6 (R2-V-001, R2-V-005, R2-V-007, R2-V-008,
  R2-V-010, and the unresolved-but-now-explicit R2-V-002/003/004/006 chain)

Independent validator run: `python3 scripts/validate-traceability.py
specs/stage-exit-coverage/PRD.md specs/stage-exit-coverage --json` → 54 requirements, 8 spec files,
0 uncovered, 0 orphaned, `valid: true`.

## Round-1 Findings Confirmation

| Round-1 | Status | Evidence |
|---|---|---|
| V-001 (CHECK-S13) | Partially resolved | All 12 types carry adjacent field comments; no declared shape changed (`StageExitDirectives` still 25 fields, `VerifyEntry` 9, `RenderStatus` 8). No comment/field transposition remains. **But two comments state wrong value domains** — R2-V-001. |
| V-002 (CHECK-S14) | **Resolved** | tech-spec §2.1/§3.11 and `01` §2 name `skills/forge-5-loop/references/runner-contract.md` as sole source; the conditional paragraph is gone; no root-level path remains. |
| V-003 (CHECK-S32) | Resolved with defects | All 8 specs carry the section, each immediately before Dependencies; no section number shifted; no cross-document `§N` citation broke. **But three new sections contain factual drift** — R2-V-007, R2-V-008, R2-V-010. |
| V-004 (CHECK-S38) | **Resolved** | Independently verified: 54 rows, ID set identical to the PRD's 54, no duplicates, summary reads 54. |
| V-005 (CHECK-S15/S38) | **Resolved** | All six corrected citations re-checked against actual section headings and content. |
| V-006 (CHECK-S27) | **Not resolved** | §3.5 exists and is wired in, but does not close the lost update it claims to close, overstates its held-region guarantee, and leaves integration with the existing writers unspecified — R2-V-002/003/004. Its §4.3 tests are not executable as written — R2-V-006. |

## Check Results

- **Pass (28):** CHECK-S01, S02, S03, S04, S05, S07, S09, S10, S11, S16, S18, S19, S20, S21, S22,
  S23, S24, S25, S26, S28, S29, S30, S31, S33, S35, S36, S37, S38
- **Fail (9):** CHECK-S06, S08, S12, S13, S14, S15, S27, S32, S34
- **Not applicable (1):** CHECK-S17 — no package exports map; the sibling-import contract
  (`01` §3.4, `05` §5.1) is internally consistent.
- Deviation from round 1: CHECK-S35 scored **pass**, not not-applicable — `07` §2.3 is an explicit
  fixture inventory and §1/§4.3/§5.3 define the mock policy.

## Findings

### R2-V-001: Two new field comments state value domains that do not exist

- **Severity:** error
- **Location:** `00-core-definitions.md` §4 (`StageExitDirectives`)
- **Issue:** Two comments added by the round-1 V-001 fix describe the correct field but the wrong
  values.
  1. `owner: str | None` is commented "Skill id that invoked this exit". It is not a skill id:
     `00` §2 defines `ExitOwner = Literal["direct", "nested"]`, `02` §2.2 registers
     `[--owner {direct,nested}]`, `02` §3.1 step 5 requires `direct`/`nested`, and tech-spec §4.2's
     example shows `"owner": "direct"`.
  2. `verifyCapability: str` is commented `("capable"/"manual")`. `"capable"` is not in the domain:
     `00` §2 defines `VerifyCapability = Literal["interactive", "manual"]` and `02` §2.2 registers
     `[--verify-capability {interactive,manual}]`.
  Both are load-bearing routing fields; an implementation typed against these comments produces a
  payload that fails `02` §3.1 validation. Related nit in the same block: `outcome`'s comment
  enumerates `complete`/`partial`/`blocked`/`needs-human` and omits `deferred`, which IS in
  `EXIT_OUTCOMES["forge-5-loop"]`.
- **Suggested fix:** Rewrite `owner`'s comment to the `direct`/`nested` branch-ownership domain
  (required for verify/fix, rejected on production exits). Change `verifyCapability`'s parenthetical
  to `("interactive"/"manual")`. Append `deferred` to `outcome`'s enumeration, or replace the
  parenthetical with "see `EXIT_OUTCOMES[stage]`".
- **References:** `00-core-definitions.md` §2, §3; `02-stage-exit-routing.md` §2.2, §3.1;
  `tech-spec.md` §3.2, §4.2
- **Checklist:** CHECK-S13, CHECK-S08, CHECK-S12

### R2-V-002: A reclaimed lock does not stop the evicted writer's replace — the lost update survives

- **Severity:** gap
- **Location:** `03-verification-state.md` §3.5 ("Stale recovery", "Release"); §7.1 ("Contention
  diagnostics")
- **Issue:** §3.5 opens by stating the protocol exists because two writers can each replace
  successfully, the later silently discarding the earlier. The specified protocol does not prevent
  that in the reclamation case. Sequence: writer A acquires at T0 and loads; A stalls (SIGSTOP,
  swap, NFS hang) past `LOCK_STALE_S`; writer B double-checks the token, reclaims, acquires, loads
  A's un-replaced document, mutates, replaces at T1; A resumes at T2 > T1 and performs **its own**
  `os.replace` from the T0 snapshot, discarding B's update. Nothing tells A to re-check ownership
  before replacing. §3.5 Release and §7.1 explicitly bless this: "A lock that could not be released
  because its token no longer matches is a stderr warning on an otherwise successful write, never a
  failure: the write itself already landed." **A lease without fencing is not mutual exclusion** —
  the 300 s bound lowers the probability, but the stated guarantee is unconditional.
  Secondary race: release is a read-token-then-`os.unlink` pair with no atomicity, so a lock
  reclaimed in that window is unlinked by the departing writer — the outcome the token check exists
  to prevent.
- **Suggested fix:** Add a fencing step to §3.5 **Held region**: immediately before `os.replace`
  (after fsync of the temp file), re-read the lock and require it to exist and still carry this
  acquisition's `token`. On mismatch or absence, abandon the write — unlink the temp, leave the
  target byte-identical, raise `UsageError` naming the state file and instructing a retry. Correct
  §3.5 Release and §7.1 so a token mismatch means the write was **abandoned**, not "already landed".
  For the release race, note that fencing makes an erroneous unlink harmless because the new holder
  re-fences before its own replace.
- **References:** `tech-spec.md` §7.3 (same unconditional claim, same correction); `PRD.md`
  REQ-STATE-03, REQ-REL-02; `07-testing-strategy.md` §4.3 (its "token-checked release" bullet
  currently asserts the buggy behavior)
- **Checklist:** CHECK-S27

### R2-V-003: §3.5's held-region guarantee is overstated — the epic manifest revision is outside lock scope

- **Severity:** inconsistency
- **Location:** `03-verification-state.md` §3.5 ("Scope", "Held region")
- **Issue:** Held region asserts every input the mutation derives from the document "or its sibling
  manifest — the production stage's `version`, the epic manifest `revision`, the prior verify entry"
  is read inside the lock. But Scope limits the protocol to `.pipeline-state.json` and
  `.epic-state.json`; `epic-manifest.json` is not covered, and its writer (`_bump_and_write` →
  `atomic_write` in `scripts/epic-manifest.py`) takes no lock — nor can it easily, since `01` §3.2
  forbids `epic-manifest.py` from importing `forge-session.py`. Holding `.epic-state.json.lock`
  therefore does not prevent a concurrent manifest mutation from bumping `revision` between read and
  replace. Per `03` §3.3/§5.2 an epic entry can record `verifiedStageVersion == R` for a manifest
  already at `R+1` — a verification that reads fresh but is stale. Separately `_bump_and_write` is
  itself an unsynchronized read-compare-write, so two concurrent manifest mutations can lose an
  increment.
- **Suggested fix:** Either (a) narrow the claim — restrict Held region to inputs in the locked
  document, and add a paragraph stating the manifest revision is read outside any lock, that a
  concurrent manifest mutation can stale a just-written epic result, and that §5.2's read-side
  freshness comparison is the compensating control; or (b) extend Scope to `epic-manifest.json` with
  its own sibling lock, duplicating the helpers in `epic-manifest.py` under the `01` §3.2
  self-containment rule — which also invalidates §3.5's "at most one state-file lock is held at a
  time" ordering rule. Mirror the choice in tech-spec §7.3.
- **References:** `03-verification-state.md` §2.2, §3.3, §5.2; `01-architecture-layout.md` §3.2;
  `tech-spec.md` §7.3
- **Checklist:** CHECK-S27, CHECK-S25

### R2-V-004: §3.5 governs all eight `state-*` verbs but specifies an acquisition point for only one

- **Severity:** gap
- **Location:** `03-verification-state.md` §3.2, §3.5 ("Scope"), §8; `00-core-definitions.md` §7
- **Issue:** §3.5 Scope and tech-spec §7.3 both state the protocol applies to all eight verbs
  (verified: those are exactly the seven existing subparsers in `scripts/forge-session.py` plus the
  new one). Only `state-verify` is given an acquisition point. Three unspecified integration
  problems:
  1. §3.2 says acquire "before the load in step 1 or 2" — but step 1 *is*
     `_load_state_for_write(specs_dir, feature, epic)`, which resolves and loads in one call.
     Locking before it requires calling `_resolve_feature_dir_for_write` separately and composing
     the path; no document says so, and `00` §7 / `03` §8 quote `_load_state_for_write` as an
     unchanged existing signature.
  2. Every other verb enters through the same `_load_state_for_write` / `_commit_state` pair, and no
     section assigns them acquisition — yet `07` §4.3 ("Writer coverage") requires the lock tests to
     parameterize over all eight. The test demands behavior no section specifies.
  3. `_write_state`'s live docstring says "Concurrent multi-session mutation is out of scope (single
     writer assumed, matching epic-manifest.py)". The protocol invalidates that documented contract
     and no spec says to update it.
  Related: `03`'s new API section names `_acquire_state_lock(state_path)` /
  `_release_state_lock(handle)` and a "handle" type that §3.5 never defines.
- **Suggested fix:** Add a §3.5 subsection "Integration with the existing writers": declare
  `_acquire_state_lock(state_path: Path) -> StateLock` and `_release_state_lock(lock: StateLock) ->
  None` with the handle's contents (path + token); pin one call order for all eight verbs
  (recommended: `_resolve_feature_dir_for_write` → `_acquire_state_lock` → `_load_state_for_write` →
  validate/mutate → `_commit_state` → fence → replace → `_release_state_lock` in `finally`); and
  state that `_write_state`'s "single writer assumed" docstring is replaced by a pointer to §3.5.
  Reword §3.2 to match. Add the seven existing verbs to `01` §3.1's "New code slots".
- **References:** `07-testing-strategy.md` §4.3; `03-verification-state.md` §8;
  `00-core-definitions.md` §7; live `scripts/forge-session.py`
- **Checklist:** CHECK-S27, CHECK-S25, CHECK-S23

### R2-V-005: The lock protocol names a `.gitignore` that does not exist

- **Severity:** inconsistency
- **Location:** `03-verification-state.md` §3.5 ("Lock file"); `07-testing-strategy.md` §4.3;
  `01-architecture-layout.md` §2; `tech-spec.md` §2.1
- **Issue:** §3.5 states "the specs-hygiene `.gitignore` gains `*.json.lock`" and `07` §4.3 asserts
  the same. Verified against the repository: `references/templates/specs-hygiene/` contains only
  `AGENTS.md` and `CLAUDE.md` — there is no `.gitignore` there or anywhere matching that
  description, and the root `.gitignore` has no `*.json.lock` entry. **This is the same defect class
  as the resolved round-1 V-002: a plausible-sounding path that does not resolve.** Neither `01` §2
  (whose Verification item is "Every path in §2 is accounted for by the implementation diff") nor
  tech-spec §2.1 lists `.gitignore` as modified, so a required file change has no owner. Not
  cosmetic: lock files land beside `.pipeline-state.json` inside the tracked `specs/` tree, and an
  untracked leftover lock dirties the working tree that `00` §4 `cleanTree`/`autoFixEligible` depend
  on and that the two-commit protocol stages against.
- **Suggested fix:** Replace "the specs-hygiene `.gitignore`" with "the repository-root
  `.gitignore`" in `03` §3.5 and `07` §4.3. If installed projects must also ignore locks, specify a
  new `references/templates/specs-hygiene/.gitignore` and name the skill/bootstrap step that copies
  it. Add `.gitignore  M  ignore transient *.json.lock state locks` to `01` §2 and tech-spec §2.1.
- **References:** live `.gitignore`; `references/templates/specs-hygiene/`;
  `00-core-definitions.md` §4; `03-verification-state.md` §6.3
- **Checklist:** CHECK-S14, CHECK-S06

### R2-V-006: The §4.3 lock tests cannot be executed as specified

- **Severity:** inconsistency
- **Location:** `07-testing-strategy.md` §4.3 ("Lost-update serialization", "Lock lifecycle")
- **Issue:** The tests mandate real cross-process concurrency — "Run them as real concurrent
  processes (`subprocess` via the §2.2 real-CLI fixture) rather than threads, since the lock is
  cross-process by construction" — and then mandate in-process patching of those same processes:
  the negative control ("with acquisition stubbed to a no-op"), the forced interleaving ("Wrap the
  load step with a `monkeypatch` barrier"), and the tunables ("module constants patched per test")
  while the timeout case asserts "exits 2", i.e. a subprocess. `pytest.monkeypatch` does not reach
  into a `subprocess.run` child, so none of the three is achievable. The claimed negative control —
  the one thing proving the test observes the lock rather than incidental timing — is
  unimplementable as written. The bullets also violate this document's own policy: §4.3 says use
  `monkeypatch` "only for `tempfile.mkstemp`, `os.fsync`, and `os.replace`", §1 says mocks only
  inject an otherwise difficult local failure, and the new API section ends "never the logic under
  test" — stubbing lock acquisition to a no-op is patching the logic under test.
- **Suggested fix:** Specify a child-process injection seam in `03` §3.5 and consume it here — e.g.
  env vars read once at import: `FORGE_TEST_LOCK_TIMEOUT_S`, `FORGE_TEST_LOCK_POLL_S`,
  `FORGE_TEST_LOCK_STALE_S`, `FORGE_TEST_LOCK_STEAL_ATTEMPTS`, `FORGE_TEST_LOCK_DISABLE=1` (negative
  control), `FORGE_TEST_LOCK_BARRIER=<path>` (post-load pause) — test-only, undocumented for users,
  defaulting to the shipped constants. Extend `07` §2.2's `_run` to accept `env`, and rewrite §4.3
  to pass them instead of `monkeypatch`. Add the seams to the §4.3 and API-section allow-lists.
  Alternatively drop to in-process `threading` tests plus timing-only subprocess tests, stating
  explicitly which property each layer proves.
- **References:** `07-testing-strategy.md` §1, §2.2, §5.3, "Public API and Internal Surface";
  `03-verification-state.md` §3.5, §7.1
- **Checklist:** CHECK-S34, CHECK-S27, CHECK-S35

### R2-V-007: The new `02` API section drops `pi` from the `--host` domain

- **Severity:** error
- **Location:** `02-stage-exit-routing.md`, "Public API and Internal Surface"
- **Issue:** The bullet renders `[--host claude|generic]`. The actual domain, pinned three times in
  this feature, is `{claude,pi,generic}` (`02` §2.2 line 129, tech-spec §5.1, `00` §3). Dropping
  `pi` from the summary a reader may skim is materially wrong for a feature whose headline
  correction (REQ-EXIT-07) is that capable **Pi** sessions receive the interactive gate; `02` §5.1
  and §5.2 both turn on Pi being first-class.
- **Suggested fix:** `[--host claude|pi|generic]`. Consider replacing the partial flag list with a
  pointer to §2.2 so the summary cannot drift again.
- **References:** `02-stage-exit-routing.md` §2.2, §5.1, §5.2; `tech-spec.md` §5.1;
  `00-core-definitions.md` §3
- **Checklist:** CHECK-S32, CHECK-S08

### R2-V-008: The new `07` API section attributes the mock policy to a section that does not contain it

- **Severity:** error
- **Location:** `07-testing-strategy.md`, "Public API and Internal Surface"
- **Issue:** The bullet states "§9 constrains where patching is legitimate at all". Section 9
  ("Error-Testing Rules") says nothing about patching or mocks — it covers exit codes, stderr
  prefixes, byte-identical files, and traceback leakage. The policy lives in §1 and §4.3. The stated
  allow-list is also incomplete: §3.6 permits a narrowly injected `subprocess.run` failure and §5.3
  permits injecting a stderr write failure. **Same defect class as the resolved round-1 V-005** — a
  citation pointing at an adjacent section that does not carry the claim.
- **Suggested fix:** Cite §1 and §4.3, and extend the list to include the §3.6 and §5.3 exceptions.
- **References:** `07-testing-strategy.md` §1, §3.6, §4.3, §5.3, §9
- **Checklist:** CHECK-S15, CHECK-S32

### R2-V-009: Two competing authoritative allow-lists for the same test module

- **Severity:** inconsistency
- **Location:** `04-skill-integration.md` §10 and its API section; `06-compliance-and-coverage.md`
  §2.1 and its API section
- **Issue:** `04` §10 declares `COVERED_SKILLS` in `tests/test_stage_exit_protocol.py` and `04`'s
  new API section elevates it to "the one importable value this document contributes". `06` §2.1
  declares `CANONICAL_EXIT_SITES` in the **same file**, and `06`'s new API section calls it "the
  guard's ground truth". Both carry the same nine names in the same order, so there is no value
  conflict today — but two hand-maintained allow-lists in one module, each documented as
  authoritative, is precisely the drift failure REQ-GUARD-01 exists to prevent. The round-1 fix did
  not create the duplication but made both claims explicit and mutually exclusive.
- **Suggested fix:** Make `CANONICAL_EXIT_SITES` the single declaration. In `04` §10 replace the
  literal with `COVERED_SKILLS = tuple(site.skill for site in CANONICAL_EXIT_SITES)` and a
  cross-reference; update `04`'s API section to say the allow-list is owned by `06` §2.1.
- **References:** `00-core-definitions.md` §2 (`EXIT_STAGES`); `06` §2.1 assertions; `07` §6.1
- **Checklist:** CHECK-S12, CHECK-S32

### R2-V-010: The branch-fixture path is pinned in one place and left as a placeholder in two others

- **Severity:** inconsistency
- **Location:** `06-compliance-and-coverage.md` API section; `01-architecture-layout.md` §2 (eval
  block)
- **Issue:** `06` §3.1 pins the fixture at `eval/fixtures/compliance/verify-fix-reverify.json` and
  explains the nested directory "deliberately prevents `eval/run-eval.py` from loading a compliance
  fixture as a trigger fixture", because `load_fixtures()` uses the non-recursive glob
  `eval/fixtures/*.json`. `07` §2.3/§7.1 use the exact path. But `06`'s new API section reverts to
  `eval/fixtures/<branch-fixture>.json`, and `01` §2 lists `eval/fixtures/<branch-fixture>.json` — a
  path **at the glob level §3.1 forbids**. An implementer following the architecture map would break
  the isolation `06` §3.1 and `07` §7.1 both test for.
- **Suggested fix:** In `01` §2 use `fixtures/compliance/verify-fix-reverify.json` with the nesting
  rationale; in `06`'s API section use the exact path. Optionally add it to tech-spec §2.1's eval
  block, which omits the fixture entirely.
- **References:** `06` §3.1; `07` §2.3, §7.1; `tech-spec.md` §2.1, §8.5
- **Checklist:** CHECK-S06, CHECK-S14

## Deliberate Exclusion — Assessment

`PRD.md` line 163 (REQ-CAP-01, bare `references/runner-contract.md`): **the call is agreed.** The
cascade cost (forge-1-prd → v3, restaling tech-spec and all eight specs) is disproportionate to a
wording clarification, and the residual ambiguity is closed downstream — `01` §2 now states
affirmatively that "there is no root-level `references/runner-contract.md` to create or reconcile".
Fold it into the next PRD revision rather than tracking it as an open finding. Note that R2-V-005 is
the *same defect class* reappearing in newly authored text, so the underlying habit (bare or
plausible-but-unverified reference paths) is worth a convention note rather than another one-off fix.

## Fix Execution Plan

### User Decisions Required

1. **R2-V-002 — fencing strategy.** (a) Re-check lock ownership immediately before `os.replace` and
   abort on loss *(recommended: smallest change, makes the stated guarantee true, keeps stale
   reclamation)*; (b) remove stale reclamation and require manual `.lock` removal (simplest, but
   reintroduces the permanent wedge reclamation was added to avoid); (c) raise `LOCK_STALE_S` (does
   not close the hole — not recommended). Steps below assume (a).
2. **R2-V-003 — manifest scope.** (a) Narrow the held-region claim and document §5.2's read-side
   comparison as the compensating control *(recommended: no second lock, no `epic-manifest.py`
   duplication, ordering rule unchanged)*; (b) extend the protocol to `epic-manifest.json`. Steps
   below assume (a).
3. **R2-V-006 — test seam.** (a) Documented test-only env-var seams *(recommended: keeps the
   cross-process tests, which is what makes them meaningful)*; (b) in-process threading plus
   timing-only subprocess tests. Steps below assume (a).
4. **R2-V-009 — which constant survives.** Recommended: `CANONICAL_EXIT_SITES` (it carries the
   contract paths the guard actually reads). Steps below assume that.

### Execution Steps

#### Step 1: Close the lock-protocol correctness gaps
- **Files:** `03-verification-state.md`, `tech-spec.md`
- **Addresses:** R2-V-002, R2-V-003 · **Checklist:** CHECK-S27
- **Action:** Add the fencing requirement to §3.5 Held region (re-read lock after fsync, before
  `os.replace`; on token mismatch or absence unlink the temp, leave the target byte-identical, raise
  `UsageError` instructing a retry). Rewrite §3.5 Release and §7.1's last sentence so a token
  mismatch describes an **abandoned** write. Remove "or its sibling manifest" and "the epic manifest
  `revision`" from the protected-inputs list; add a paragraph stating the revision is read outside
  any lock and that §5.2's freshness comparison is the compensating control. Mirror both in
  tech-spec §7.3.
- **Depends on:** none

#### Step 2: Specify how the existing writers acquire the lock
- **Files:** `03-verification-state.md`, `01-architecture-layout.md`
- **Addresses:** R2-V-004 · **Checklist:** CHECK-S27, CHECK-S25
- **Action:** Add §3.5 subsection "Integration with the existing writers" — declare
  `_acquire_state_lock`/`_release_state_lock` and the `StateLock` handle, pin the call order for all
  eight verbs, and state that `_write_state`'s "single writer assumed" docstring is replaced by a
  pointer to §3.5. Reword §3.2's "before the load in step 1 or 2" to match. Add the seven existing
  verbs to `01` §3.1's "New code slots".
- **Depends on:** Step 1

#### Step 3: Fix the `.gitignore` reference and record the file change
- **Files:** `03-verification-state.md`, `07-testing-strategy.md`, `01-architecture-layout.md`,
  `tech-spec.md`
- **Addresses:** R2-V-005 · **Checklist:** CHECK-S14, CHECK-S06
- **Action:** "specs-hygiene `.gitignore`" → "repository-root `.gitignore`" in `03` §3.5 and `07`
  §4.3. Add `.gitignore  M  ignore transient *.json.lock state locks` to `01` §2 and tech-spec §2.1.
  If installed projects must ignore locks too, specify the new template file and its copier.
- **Depends on:** none

#### Step 4: Make the lock tests executable and self-consistent
- **Files:** `07-testing-strategy.md`, `03-verification-state.md`
- **Addresses:** R2-V-006 · **Checklist:** CHECK-S34, CHECK-S27
- **Action:** Add the test-only env-var seams to `03` §3.5 (read once at import, defaulting to the
  shipped constants, not a user knob). Extend `07` §2.2's `_run` to accept `env`. Rewrite §4.3's
  negative-control, forced-interleaving, and injectable-constant bullets to pass env vars instead of
  `monkeypatch`; add the seams to the allow-lists. Update the "token-checked release" bullet to
  assert Step 1's behavior (evicted writer abandons its write, exits 2, target byte-identical).
- **Depends on:** Steps 1, 2

#### Step 5: Correct the field-comment value domains
- **Files:** `00-core-definitions.md`
- **Addresses:** R2-V-001 · **Checklist:** CHECK-S13, CHECK-S08
- **Action:** Rewrite `owner`'s comment to the `direct`/`nested` domain; change
  `verifyCapability`'s parenthetical to `("interactive"/"manual")`; add `deferred` to `outcome`'s
  enumeration. Change no declared field, type, or ordering.
- **Depends on:** none

#### Step 6: Correct the new API sections
- **Files:** `02-stage-exit-routing.md`, `07-testing-strategy.md`, `06-compliance-and-coverage.md`,
  `01-architecture-layout.md`
- **Addresses:** R2-V-007, R2-V-008, R2-V-010 · **Checklist:** CHECK-S32, CHECK-S15, CHECK-S06,
  CHECK-S14
- **Action:** `02`: `[--host claude|generic]` → `[--host claude|pi|generic]`. `07`: re-attribute the
  patching allow-list from §9 to §1/§4.3 and add the §3.6/§5.3 exceptions. `06`:
  `eval/fixtures/<branch-fixture>.json` → `eval/fixtures/compliance/verify-fix-reverify.json`.
  `01` §2: same path plus the nesting rationale.
- **Depends on:** none

#### Step 7: Collapse the duplicate exit allow-list
- **Files:** `04-skill-integration.md`, `06-compliance-and-coverage.md`
- **Addresses:** R2-V-009 · **Checklist:** CHECK-S12, CHECK-S32
- **Action:** In `04` §10 replace the `COVERED_SKILLS` literal with the derivation from
  `CANONICAL_EXIT_SITES` plus a cross-reference; update `04`'s API section accordingly. Leave `06`
  §2.1 unchanged.
- **Depends on:** none

#### Step 8: Re-run traceability and confirm no citation drifted
- **Files:** `TRACEABILITY.md` (verify only)
- **Addresses:** regression guard · **Checklist:** CHECK-S15, CHECK-S38
- **Action:** Re-run `validate-traceability.py` and confirm 54 / 8 / 0 / 0. Confirm Steps 1–7 added
  or renumbered no numbered section; if §3.5 gained a numbered subsection, re-check every `03`
  citation in `TRACEABILITY.md` and `07` §4.
- **Depends on:** Steps 1–7

## Verifier Notes

- Claims independently re-checked against live source before this report was accepted: the
  `ExitOwner` and `VerifyCapability` literal domains, `EXIT_OUTCOMES["forge-5-loop"]`, the contents
  of `references/templates/specs-hygiene/`, the root `.gitignore`, `02` §2.2's `--host` domain, and
  the absence of any patching policy in `07` §9. All six held.
