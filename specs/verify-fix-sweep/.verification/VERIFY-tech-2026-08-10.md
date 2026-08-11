# Verification Report: verify-fix-sweep (tech)
Date: 2026-08-10
Pipeline Stage: forge-2-tech (complete, v1)
Artifacts Reviewed:
- `specs/verify-fix-sweep/tech-spec.md` (v1, under verification)
- `specs/verify-fix-sweep/PRD.md` (v1, upstream, passed)
- Spot-verified against repo: `scripts/forge-session.py`, `scripts/check-spec-purity.py`, `scripts/validate-traceability.py`, `scripts/validate.sh`, `scripts/build-adapters.py`, `skills/forge-fix/SKILL.md`, `skills/forge-verify/SKILL.md`, `skills/forge-verify/references/findings-template.md`, `skills/forge-verify/references/verification-checklists/{backlog,impl,specs}.md`, `references/shared-conventions.md`, `references/stage-exit-protocol.md`, `tests/test_verification_checklists_split.py`, `tests/test_build_adapters.py`, `tests/test_forge_bootstrap.py`, `tests/test_adapter_host_neutrality.py`, `tests/test_{dev_runtime_smoke,smoke_command,lifecycle_artifact_check}.py`, `AGENTS.md`

Checks Executed: 17 of 17 (9 pass, 8 fail, 0 not-applicable)

Per-check: T01 pass · T02 **fail** · T03 **fail** · T04 **fail** · T05 pass · T06 pass · T07 pass · T08 **fail** · T09 pass · T10 pass · T11 pass · T12 **fail** · T13 pass · T14 pass · T15 **fail** · T16 **fail** · T17 **fail**

## Summary
- Total findings: 10
- Gaps: 5
- Inconsistencies: 2
- Improvements: 2
- Errors: 1

**Blocking (error/gap): 6 — V-001 … V-006.** Verdict: **findings-reported**, routes to forge-fix.

Verification quality note: many of the tech spec's repo claims *do* hold and were checked individually — `forge-session.py` is 7131 lines and has no `return 1` path (0/2 only); `validate-traceability.py` is genuinely 0/1/2; `references/stage-exit-protocol.md:458` really is the "`skills/forge-fix/SKILL.md` Step 6" line; `skills/forge-verify/SKILL.md` lines 33 and 171 really are the two totals sites; the four pinned test literals (`"impl: 23 checks"`/`"impl 23"` ×2 files, `"backlog: 28 checks"`/`"backlog 28"`, `131`) are all exactly where §2 says; `131 + 4 = 135` and `backlog 29 / impl 25 / specs 39` are arithmetically right; `test_forge_bootstrap.py` does carry both `_git()` (L177) and `_set_git_identity()` (L745); `_git_output()` at `forge-session.py:1412` does use `subprocess.run([...], capture_output=True, text=True, timeout=10)`; no test pins a `specs 38` literal. The findings below are what survived that pass.

## Findings

### V-001: §3.2's "dispositions ride Commit 1 atomically" is false — forge-fix stages only the feature directory
- **Severity:** error
- **Location:** tech-spec.md §3.2 (Rationale), reinforced by §3.6 "Step 4 addition" and §6.1
- **Issue:** §3.2 justifies sweeping **pre-commit** with: "run pre-commit, the record and all dispositions ride Commit 1 atomically, with no third commit and no friction with the two-commit provenance protocol." That is factually wrong. `references/shared-conventions.md` § Git Commit Protocol step 1 says, emphatically, **"Stage specific files only: `git add {specsDir}/{feature}/` — never use `git add -A` or `git add .`"**, and `skills/forge-fix/SKILL.md` Step 5 (line 77) repeats it verbatim (`git add {resolvedFeatureDir}/`, or `{specsDir}/{epic}/` for a member). The sweep's entire purpose is finding survivors **outside** the feature directory — the motivating F-5 survivor lived in a *sibling* artifact and in `src/generated/*.ts`, and this feature's own §3.4 keeps prior features' `specs/`, `CHANGELOG.md`, and `STATUS.md` in the corpus. A **fixed** disposition therefore edits a path Commit 1 does not stage. Consequences: (a) the disposition edit is left unstaged; (b) Commit 2's `git rev-parse HEAD` records provenance for a commit that does not contain it; (c) the protocol's stated postcondition "The working tree is clean afterward, so the next stage's dirty-tree check passes" is violated, so the mandatory re-verify (Step 6) and the next stage both start on a dirty tree. The chosen alternative was rejected *on this argument*, so the decision itself rests on the error.
- **Suggested fix:** In §3.2, replace the atomicity sentence with the true staging scope and state how out-of-dir dispositions are committed. Then add to §3.6 a **Step 5 addition** (which §6.1 currently denies exists): after dispositions, forge-fix stages each disposition-edited path **explicitly and enumerated** (`git add <path>` per file recorded in the sweep record) alongside `git add {resolvedFeatureDir}/` — never `git add -A`/`git add .`. Correct §6.1's "no Step-5/6/7 text changes beyond none" accordingly, and add `skills/forge-fix/SKILL.md` Step 5 to the §2 edit description. Add a test to §8 asserting the Step-5 prose enumerates disposition paths. If instead the decision is that out-of-dir survivors are report-only (never fixed in-pass), say so explicitly in §3.6 and reconcile it with REQ-SWEEP-04's "corrected in the same pass" option.
- **References:** `references/shared-conventions.md` § Git Commit Protocol (step 1, step 3); `skills/forge-fix/SKILL.md` lines 77–89; PRD REQ-SWEEP-04, REQ-SWEEP-05
- **Checklist:** CHECK-T02, CHECK-T08, CHECK-T16

### V-002: REQ-PERF-01 (P0) has no tech decision and no explicit deferral
- **Severity:** gap
- **Location:** tech-spec.md — absent throughout (§3, §4, §8, §10)
- **Issue:** `REQ-PERF-01` is the only PRD requirement id that appears **nowhere** in the tech spec (verified by extracting all `REQ-` ids from both documents: PRD has 16, tech spec cites 14 literally plus REQ-CARD-03 via the `REQ-CARD-02..04` range in §3.7's heading; `REQ-PERF-01` is in neither form). It is P0 and quantified: "completing in seconds at this repository's scale (thousands of tracked files)." The design has a real cost shape the spec never sizes: §3.4 reads and normalizes **every** `git ls-files` entry (1603 files in this repo today) into a per-file blob on **every fix pass**, then searches it once per surviving needle — i.e. O(corpus bytes × needles). Nothing states the expected runtime, nothing bounds needle count, and §8 has no performance assertion.
- **Suggested fix:** Add a `### 3.8 Performance (REQ-PERF-01)` subsection stating the cost model (one pass over the tracked corpus + `str.find` per needle), the measured or estimated wall-clock at this repo's ~1600 tracked files, and the one design consequence worth recording (whole-file read into memory vs streaming; whether needles are searched in a single pass). Add a corresponding line to §8 Testing Approach — at minimum an assertion that the sweep completes within a stated bound on a synthetic corpus, or an explicit statement that timing is measured once at milestone acceptance (§10) rather than asserted in CI. If the position is "no measurement in milestone 1", say that explicitly as a deferral with rationale, per CHECK-T03.
- **References:** PRD §4.1 REQ-PERF-01 (P0); tech-spec §3.4, §8
- **Checklist:** CHECK-T03, CHECK-T17

### V-003: `scripts/fix-sweep.py` is never added to `RUNTIME_HELPERS` — the sweep will not exist in any non-Claude adapter bundle
- **Severity:** gap
- **Location:** tech-spec.md §2 (Module Structure table), §6.6, §6 generally
- **Issue:** §6.1 has forge-fix invoke the new script "through the standard plugin-root prelude (`$R/scripts/fix-sweep.py`)". `scripts/build-adapters.py` copies helper scripts into every adapter bundle from a hardcoded tuple, with the in-file comment "Runtime helper scripts copied BYTE-IDENTICAL into EVERY adapter bundle so a non-Claude install can execute helper-backed skill instructions after install (REQ-GEN-04) … **Editing skill helper calls? Keep this list in sync.**":

  ```python
  RUNTIME_HELPERS: tuple[str, ...] = (
      "forge-root.sh", "forge-init.sh", "epic-manifest.py",
      "forge-session.py", "validate-traceability.py", "forge-bootstrap.py",
  )
  ```

  The precedent is unambiguous: `validate-traceability.py` (invoked from skill prose) is in the tuple; `check-spec-purity.py` (dev tooling only) is not. `fix-sweep.py` is invoked from skill prose, so it belongs in the tuple — but §2 does not list `scripts/build-adapters.py` as EDIT, and §6.6 says only "no changes to validate.sh itself; canon edits require build-adapters.py regeneration". Regeneration alone does **not** add a helper. Left as specified, every codex/copilot/cursor/gemini/pi install runs a forge-fix whose sweep invocation resolves to a nonexistent path (exit 2 → `failed`, per §7). Two further consequences the spec misses: `tests/test_build_adapters.py:1053-1054` hard-pins `assert len(mod.RUNTIME_HELPERS) == 6` (and the dedup twin), so this is a **fifth** pinned test beyond §2's "four pinned tests updated in lockstep"; and `tests/test_build_adapters.py:1062-1069` asserts each bundle's `scripts/` holds *exactly* `RUNTIME_HELPERS`.
- **Suggested fix:** Add `scripts/build-adapters.py` to the §2 table (`EDIT +"fix-sweep.py" in RUNTIME_HELPERS`) and `tests/test_build_adapters.py` (`EDIT RUNTIME_HELPERS count 6 → 7`). Update §2's prose and §6.5 from "four pinned tests" to five. Add a §6 integration point stating that a skill-invoked `scripts/*.py` must be in `RUNTIME_HELPERS` to ship, and note the resulting `adapters/*/scripts/fix-sweep.py` additions in the C-5 regeneration. Add a prose/behavior guard to §8 for the new tuple entry.
- **References:** `scripts/build-adapters.py` lines ~310–322; `tests/test_build_adapters.py` lines 1053–1069; `AGENTS.md` § publish-worthiness ("canon … because regenerating `adapters/` changes what the package ships")
- **Checklist:** CHECK-T04, CHECK-T08, CHECK-T16

### V-004: REQ-CARD-01's "any claimed totals are re-derived from the actual findings set" clause is unimplemented
- **Severity:** gap
- **Location:** tech-spec.md §3.5, §4.2 (`plan-coverage` JSON payload), §8 (plan-coverage tests)
- **Issue:** REQ-CARD-01 (P0) has two conjoined obligations: "each finding maps to at least one execution step, **and any claimed totals are re-derived from the actual findings set**." §3.5 implements only the first. `findings-template.md` line 52 defines a literal claimed total in every report — `## Summary` / `- Total findings: {N}` — and the report header additionally carries `Checks Executed: {N} of {M} ({X} pass, {Y} fail, {Z} not-applicable)`. Neither is parsed: the §4.2 payload is `{applicable, findings, steps, covered, uncovered}` with no claimed-total field and no mismatch signal, and §8's plan-coverage tests exercise only the 16-findings/15-step naming case, the full-coverage case, and the no-plan case. This is exactly the defect class the feature exists to catch — a hand-written total that disagrees with the enumerated set — left uncovered in the feature's own primary artifact.
- **Suggested fix:** Extend §3.5 to state that `plan-coverage` also re-derives `## Summary`'s `Total findings: N` (and, if present, the per-severity counts) from the count of `### V-NNN:` headings under `## Findings`, reporting a mismatch as a named discrepancy (`claimed N, actual M`). Add the fields to the §4.2 payload (e.g. `"claimedTotal": 16, "actualTotal": 16, "totalMismatch": false`) and define whether a mismatch is exit 1 or advisory. Add a §8 unit: a document whose Summary says 16 while `## Findings` holds 15 is reported. If the position is that the Summary total is deliberately out of scope for milestone 1, record that as an explicit deferral in §10 citing REQ-CARD-01.
- **References:** PRD §3.2 REQ-CARD-01 (P0); `skills/forge-verify/references/findings-template.md` lines 46–52, 61, 81–83
- **Checklist:** CHECK-T03, CHECK-T12

### V-005: The four new CHECKs land in checklist sections that no parallel fan-out dimension group owns
- **Severity:** gap
- **Location:** tech-spec.md §3.7, §6.3 ("numeric totals on lines 33 and 171 only"), §2
- **Issue:** All four new checks target **large** modes, and `skills/forge-verify/SKILL.md` routes large modes through a **parallel dimensioned fan-out** in which "Each instance owns a **disjoint slice** of CHECK-IDs" and the parent passes "the **exact CHECK-IDs it owns**." The enumerated groups (lines 40–48) are: specs = types/contracts, architecture/layout, cross-reference & traceability, testing strategy, integration; backlog = item scoping & AC, dependency/ordering, spec coverage & traceability, schema/enum correctness; impl = requirement coverage, integration correctness, testing, code-quality/conventions, runnability (which explicitly "owns CHECK-I21/I22"). These groups are stated to "map to the category clusters in that mode's own checklist file." §3.7 creates **three brand-new clusters** — `### Work-Order Cardinality` in `backlog.md` and `impl.md`, and `### Internal Consistency` in `impl.md` and `specs.md` — that map to **no** listed group. Because §6.3 restricts the SKILL edit to "numeric totals on lines 33 and 171 only", a fan-out dispatch has no dimension that owns CHECK-B29/I24/I25/S39, and the new checks are silently never executed on precisely the modes they were added to. The stated blocker for fixing this is itself wrong — see V-007: the body is at **298/300** lines, not 299, so there are two lines of headroom, and PRD C-4 expressly budgets for "a pointer line".
- **Suggested fix:** Extend §3.7/§6.3 to also amend the dimension-group bullets in `skills/forge-verify/SKILL.md` lines 43–48 within the available headroom — e.g. append "(owns CHECK-B29)" to the backlog `spec coverage & traceability` group, "(owns CHECK-I24/I25)" to the impl `requirement coverage vs specs` group, and "(owns CHECK-S39)" to the specs `cross-reference & traceability` group — with zero net new lines. State the resulting line budget in §3.7 using the corrected 298 figure. Add a §8 prose guard asserting each new CHECK-ID appears in the dispatch-group bullet for its mode. If the alternative is preferred (leave the groups generic and rely on the parent to form clusters from the file), record that as an explicit decision in §3.7 with its risk stated.
- **References:** `skills/forge-verify/SKILL.md` lines 28–55; tech-spec §3.7 "Totals", §6.3
- **Checklist:** CHECK-T04, CHECK-T08, CHECK-T16

### V-006: REQ-SWEEP-03's "drift-gated regenerated trees" class is narrowed to a hardcoded `adapters/` default that ships into consumer repos
- **Severity:** gap
- **Location:** tech-spec.md §3.4, §5 (CLI contract)
- **Issue:** REQ-SWEEP-03 (P0) defines a **class** — "trees regenerated wholesale from canonical sources whose freshness a mechanical drift gate already enforces" — and gives `adapters/` only as this repository's instance. §3.4/§5 collapse the class into an always-on hardcoded default: "Default excludes `.verification/` + `adapters/` **always** apply." But `fix-sweep.py` is invoked by forge-fix, which runs in **consumer** repositories (that is its normal habitat; the PRD's out-of-scope note excludes standalone-CLI use, not consumer projects). In a consumer repo this produces two wrong behaviors: a directory named `adapters/` that is *not* drift-gated is silently dropped from the corpus (false confidence — the exact failure mode §3.4 cites as the reason to exclude), and a consumer's real drift-gated tree cannot be excluded at all, because §3.6/§6.1 fix the forge-fix invocation as a single fenced block, C-6 bars new config keys, and §5 does not say forge-fix ever passes `--exclude`.
- **Suggested fix:** Take a position in §3.4 and record it. Cheapest correct option: make `adapters/` a **conditional** default — excluded only when the repo actually carries the drift gate (e.g. `scripts/build-adapters.py` exists, or `adapters/` contains the generated-file header/`.feature-forge-bundle.json` sentinel) — and keep `.verification/` unconditional. Alternative: keep the hardcoded default but state explicitly in §3.4 that it is feature-forge-specific, accepted for milestone 1, and revisited in §10 alongside the threshold; and say in §3.6 whether forge-fix's invocation surfaces `--exclude` at all. Either way, add a §8 unit covering a repo with a non-gated `adapters/` directory.
- **References:** PRD §3.1 REQ-SWEEP-03 (P0) + its Notes; PRD §6 Out of Scope ("Non-forge corpora"); tech-spec §3.4, §5, C-6
- **Checklist:** CHECK-T03, CHECK-T14, CHECK-T16

### V-007: Both body-line measurements are stale by one, and one contradicts PRD constraint C-4
- **Severity:** inconsistency
- **Location:** tech-spec.md §3.7 ("body is at 299/300 lines") and §3.6 ("`skills/forge-fix/SKILL.md` is at 135/300 body lines")
- **Issue:** Measured with `check-spec-purity.py`'s own `check_body_size` rule (body = everything after the closing frontmatter fence, trailing blank dropped): `skills/forge-verify/SKILL.md` is **298** body lines / 4447 words, and `skills/forge-fix/SKILL.md` is **134** body lines / 2941 words. The tech spec says 299 and 135. The forge-verify figure also directly contradicts its own upstream constraint — PRD C-4 states "the forge-verify SKILL.md body is at 298/300 body lines as measured by `scripts/check-spec-purity.py` (words 4447/5000)", which is exactly right. This is not cosmetic: §3.7 derives the hard rule "no new lines may be added there — all explanatory prose lives in the checklist files" from the 299 figure, and that derived rule is what makes V-005 unfixable as written. True headroom is 2 lines, which is what C-4 budgeted for.
- **Suggested fix:** In §3.7 change "body is at 299/300 lines; no new lines may be added there" to "body is at 298/300 lines (C-4), leaving 2 lines of headroom — explanatory prose still lives in the checklist files, but the dimension-group amendments of V-005 fit within budget." In §3.6 change "135/300 body lines" to "134/300 body lines"; the "~25–35 lines" estimate and the under-cap conclusion are unaffected (134 + 35 = 169).
- **References:** PRD §5 C-4; `scripts/check-spec-purity.py` `check_body_size` (lines 600–640); V-005
- **Checklist:** CHECK-T02

### V-008: The PRD's "forge-fix Steps 5/6" placement is silently superseded by Steps 2/4 without acknowledgement
- **Severity:** inconsistency
- **Location:** tech-spec.md §1 item 2, §3.2, §3.6 vs PRD §1, §3.1 REQ-SWEEP-01 Notes, §5 C-1
- **Issue:** The PRD names the sweep's home three times as **"forge-fix Steps 5/6"** — in §1 ("It must run **inside the fix pass** (forge-fix Steps 5/6)"), in REQ-SWEEP-01's Notes ("The sweep is part of the **fix pass** (forge-fix Steps 5/6)"), and in constraint C-1 ("The corrected-claim sweep lives in the fix pass (forge-fix Steps 5/6)"). The tech spec places `plan-coverage` in **Step 2** and the sweep in **Step 4**, before Step 5's Commit 1, and never notes that it is departing from the PRD's stated steps. C-1's *normative* content — R-06 untouched, not the re-verify — is honored, and §3.2 gives a good reason for the placement, so this is a documentation deviation rather than a design defect. But a fix agent or a later reader diffing the two documents cannot tell whether the deviation was deliberate.
- **Suggested fix:** Add one sentence to §3.6 (or §3.2's Rationale): "This supersedes the PRD's parenthetical 'forge-fix Steps 5/6' — C-1's binding content is that the sweep lives in the fix pass and never in the re-verify (R-06 untouched), which Steps 2 and 4 satisfy; the pre-Commit-1 placement is chosen for the reason in §3.2." No PRD edit is required.
- **References:** PRD §1, §3.1 REQ-SWEEP-01 Notes, §5 C-1; tech-spec §1, §3.2, §3.6
- **Checklist:** CHECK-T01, CHECK-T02

### V-009: No CHANGELOG `[Unreleased]` entry or publish-worthiness note in the deployment surface
- **Severity:** improvement
- **Location:** tech-spec.md §2 (Module Structure table), §6.6
- **Issue:** `AGENTS.md` § Publish runbook records a standing rule, explicitly marked as learned from a past process gap: "**Every feature PR adds its own CHANGELOG entry** under `## [Unreleased]`, in the PR itself — never deferred to 'the release'." The same section also classifies this change as **publish-worthy**, because it edits canon (`skills/`, `references/`) and therefore changes what the npm package ships. Neither `CHANGELOG.md` nor the publish-worthiness classification appears in the tech spec's file table or its integration points, so an implementer following §2 literally will land a canon change with no changelog line.
- **Suggested fix:** Add `CHANGELOG.md  EDIT  [Unreleased] entry (AGENTS.md publish rule)` to the §2 table, and one sentence to §6.6: "This change is publish-worthy per AGENTS.md (canon edit → adapters regeneration changes the shipped package); the `[Unreleased]` entry lands in the same PR, and the version bump/publish is owner-gated and out of scope for this spec."
- **References:** `AGENTS.md` lines ~178–212; tech-spec §2, §6.6, C-5
- **Checklist:** CHECK-T15

### V-010: Corpus content source (working tree vs HEAD) is unstated, and `git ls-files` misses files the fix itself creates
- **Severity:** improvement
- **Location:** tech-spec.md §3.4 (Corpus), §3.3 (Corpus matching)
- **Issue:** §3.4 defines the corpus as "`git ls-files` output" — a **path** list — but never says which **content** is read. Because §3.2 runs the sweep pre-commit while the tree is dirty, the only coherent reading is the working-tree content, and §3.3's "self-file hits count" only makes sense that way; but the spec never says so, and an implementer could plausibly read blobs from HEAD, which would make every corrected site itself report as a survivor. Second, `git ls-files` (without `--others --exclude-standard`) lists only **tracked** paths. A fix pass that *creates* a new file — a new spec, a new checklist section split into a new file — leaves it untracked, so a surviving copy of the corrected claim inside a file the fix itself just wrote is outside the corpus. That is a plausible milestone-1 miss worth recording either way.
- **Suggested fix:** In §3.4, state explicitly: "file **paths** come from `git ls-files`; file **content** is read from the working tree (the sweep runs pre-commit, §3.2), so corrected sites read as corrected." Then take a one-line position on untracked files — either include them (`git ls-files --cached --others --exclude-standard`) or record that new untracked files are out of scope for milestone 1 and revisit in §10. Add a §8 unit pinning whichever is chosen.
- **References:** tech-spec §3.2, §3.3, §3.4; PRD REQ-SWEEP-03
- **Checklist:** CHECK-T16

## Fix Execution Plan

### User Decisions Required

> All four decisions RESOLVED 2026-08-10 (user chose the recommended option in each):
> 1 → (a) enumerated `git add <path>` per disposition-edited file; 2 → (a) `adapters/`
> exclusion conditional on drift-gate detection (`scripts/build-adapters.py` present);
> 3 → Summary `Total findings: N` re-derived, mismatch = exit 1; 4 → untracked
> non-ignored files included via `git ls-files --cached --others --exclude-standard`.

1. **V-001 disposition-commit strategy.** Either (a) forge-fix Step 5 gains an explicit enumerated `git add <path>` for every disposition-edited file outside `{resolvedFeatureDir}` (recommended — preserves REQ-SWEEP-04's "corrected in the same pass" option and keeps the tree clean for the re-verify), or (b) out-of-feature-dir survivors become report-only and route to `decisions`. (a) requires amending §6.1's "no Step-5/6/7 text changes"; (b) narrows REQ-SWEEP-04.
2. **V-006 consumer-repo default excludes.** Either (a) make the `adapters/` default **conditional** on the drift gate actually being present (recommended — the class REQ-SWEEP-03 defines, correct in both repo shapes), or (b) keep the hardcoded default and record it in §3.4 as a knowingly feature-forge-specific milestone-1 simplification with the false-exclusion risk stated.
3. **V-004 scope of "claimed totals".** Whether `plan-coverage` re-derives only `## Summary`'s `Total findings: N` (recommended, minimal) or also the report header's `Checks Executed: N of M (X pass, Y fail, Z n/a)` arithmetic; and whether a mismatch is exit 1 or advisory.
4. **V-010 untracked files.** Include untracked, non-ignored files in the corpus, or record them as a milestone-1 non-goal.

### Execution Steps

#### Step 1: Correct the two stale body-line measurements
- **Files:** `specs/verify-fix-sweep/tech-spec.md`
- **Addresses:** V-007
- **Action:** In §3.7, change "(body is at 299/300 lines; no new lines may be added there — all explanatory prose lives in the checklist files)" to "(body is at 298/300 lines per C-4, leaving 2 lines of headroom; explanatory prose still lives in the checklist files, but the dimension-group amendments in §6.3 fit within budget)". In §3.6, change "`skills/forge-fix/SKILL.md` is at 135/300 body lines" to "134/300 body lines". Leave the "~25–35 lines" estimate and the under-cap conclusions unchanged.
- **Depends on:** none

#### Step 2: Fix the §3.2 atomicity rationale and specify the disposition-commit scope
- **Files:** `specs/verify-fix-sweep/tech-spec.md`
- **Addresses:** V-001
- **Action:** In §3.2, delete the clause "the record and all dispositions ride Commit 1 atomically" and replace with the true scope: the sweep **record** lives in the findings document inside `{resolvedFeatureDir}` and does ride Commit 1, but forge-fix Step 5 stages `git add {resolvedFeatureDir}/` only (`references/shared-conventions.md` § Git Commit Protocol step 1, `skills/forge-fix/SKILL.md` line 77), so a **fixed** disposition outside the feature directory is not staged by that command. Then implement the user's decision: for (a), add a "**Step 5 addition**" bullet to §3.6 requiring forge-fix to `git add` each disposition-edited path explicitly and enumerated (never `git add -A`/`git add .`), amend §6.1 to say Step 5 text **is** changed (drop "no Step-5/6/7 text changes beyond none"), and add `skills/forge-fix/SKILL.md Step 5` to the §2 table's edit description; for (b), state in §3.6 that out-of-dir survivors are never fixed in-pass and route to `decisions`, and reconcile that with REQ-SWEEP-04 in a note. Add the matching prose guard to §8.
- **Depends on:** User Decision 1

#### Step 3: Add `build-adapters.py` and the fifth pinned test to the ripple set
- **Files:** `specs/verify-fix-sweep/tech-spec.md`
- **Addresses:** V-003
- **Action:** Add two rows to the §2 table: `scripts/build-adapters.py  EDIT  +"fix-sweep.py" in RUNTIME_HELPERS` and `tests/test_build_adapters.py  EDIT  RUNTIME_HELPERS count 6 → 7`. Change §2's prose and §6.5 from "four pinned tests updated in lockstep" to "five pinned tests". Add a new numbered item to §6: "**`scripts/build-adapters.py`** — a `scripts/*.py` invoked from skill prose as `$R/scripts/<x>.py` must be listed in `RUNTIME_HELPERS` or it is absent from every non-Claude adapter bundle (precedent: `validate-traceability.py` is listed, `check-spec-purity.py` is not); `tests/test_build_adapters.py` hard-pins the tuple length and asserts each bundle's `scripts/` equals it exactly." Note the resulting `adapters/*/scripts/fix-sweep.py` additions under C-5, and add a §8 guard for the new entry.
- **Depends on:** none

#### Step 4: Give the four new CHECKs an owning fan-out dimension
- **Files:** `specs/verify-fix-sweep/tech-spec.md`
- **Addresses:** V-005
- **Action:** Extend §3.7's "Totals" paragraph and §6.3 beyond numeric-only: also amend the dimension-group bullets at `skills/forge-verify/SKILL.md` lines 43–48, within the 2-line headroom established in Step 1 and with zero net new lines — append "(owns CHECK-B29)" to the backlog `spec coverage & traceability` group, "(owns CHECK-I24/I25)" to the impl `requirement coverage vs specs` group, and "(owns CHECK-S39)" to the specs `cross-reference & traceability` group. State the rationale in one sentence: large modes dispatch a *disjoint slice* of CHECK-IDs, so a cluster owned by no group is never executed. Add a §8 prose guard asserting each new CHECK-ID appears in its mode's dispatch-group bullet.
- **Depends on:** Step 1 (the corrected 298/300 figure is what makes this fix admissible)

#### Step 5: Implement REQ-CARD-01's claimed-totals clause
- **Files:** `specs/verify-fix-sweep/tech-spec.md`
- **Addresses:** V-004
- **Action:** Per User Decision 3, extend §3.5 to state that `plan-coverage` re-derives the findings document's claimed total(s) from the count of `### V-NNN:` headings under `## Findings`, reporting a mismatch as `claimed N, actual M`. Add the fields to the §4.2 payload (e.g. `"claimedTotal"`, `"actualTotal"`, `"totalMismatch"`) and state the exit-code treatment. Add a §8 plan-coverage unit: a document whose `## Summary` says `Total findings: 16` while `## Findings` holds 15 `### V-NNN:` headings is reported. Cite `skills/forge-verify/references/findings-template.md` line 52 as the parse target in §6.2.
- **Depends on:** User Decision 3

#### Step 6: Resolve the drift-gated-tree exclusion for consumer repositories
- **Files:** `specs/verify-fix-sweep/tech-spec.md`
- **Addresses:** V-006
- **Action:** Per User Decision 2, either (a) rewrite §3.4's second bullet and §5's "Default excludes … always apply" so `adapters/` is excluded **conditionally** on a detectable drift gate (state the detector: `scripts/build-adapters.py` present, or the generated-file header / `.feature-forge-bundle.json` sentinel inside `adapters/`), keeping `.verification/` unconditional; or (b) add an explicit sentence to §3.4 recording the hardcoded default as a knowingly feature-forge-specific milestone-1 simplification, naming the consumer-repo false-exclusion risk, and adding it to §10's deferred notes. Either way, state in §3.6 whether forge-fix's fenced invocation surfaces `--exclude`, and add a §8 unit covering a repo with a non-gated `adapters/` directory.
- **Depends on:** User Decision 2

#### Step 7: Address REQ-PERF-01
- **Files:** `specs/verify-fix-sweep/tech-spec.md`
- **Addresses:** V-002
- **Action:** Add `### 3.8 Performance (REQ-PERF-01)` stating the cost model (one read+normalize pass over the tracked corpus, then `str.find` per surviving needle — O(corpus bytes × needles)), the expected wall-clock at this repository's ~1600 tracked files, and the memory posture (whole-file blob vs streaming). Add one line to §8: either a bounded-time assertion on a synthetic corpus, or an explicit statement that timing is observed once at milestone acceptance (§10) rather than asserted in CI. Cite `REQ-PERF-01` literally so `scripts/validate-traceability.py` and CHECK-S38 see it downstream.
- **Depends on:** none

#### Step 8: Record the PRD step-placement deviation
- **Files:** `specs/verify-fix-sweep/tech-spec.md`
- **Addresses:** V-008
- **Action:** Add one sentence at the end of §3.6's opening (or to §3.2's Rationale): "This supersedes the PRD's parenthetical 'forge-fix Steps 5/6' (PRD §1, REQ-SWEEP-01 Notes, C-1) — C-1's binding content is that the sweep lives in the fix pass and never in the re-verify (R-06 untouched), which Steps 2 and 4 satisfy; the pre-Commit-1 placement is chosen for the reason in §3.2." Do not edit the PRD.
- **Depends on:** none

#### Step 9: Add the CHANGELOG obligation and publish-worthiness note
- **Files:** `specs/verify-fix-sweep/tech-spec.md`
- **Addresses:** V-009
- **Action:** Add `CHANGELOG.md  EDIT  [Unreleased] entry` to the §2 table and one sentence to §6.6: "This change is publish-worthy per AGENTS.md (a canon edit regenerates `adapters/` and so changes what the npm package ships); the `[Unreleased]` CHANGELOG entry lands in the same PR per the standing rule, and the version bump/publish itself is owner-gated and out of scope here."
- **Depends on:** none

#### Step 10: Pin the corpus content source and the untracked-file position
- **Files:** `specs/verify-fix-sweep/tech-spec.md`
- **Addresses:** V-010
- **Action:** In §3.4, add: "file **paths** come from `git ls-files`; file **content** is read from the **working tree** (the sweep runs pre-commit, §3.2), so the sites the fix just corrected read as corrected rather than as survivors." Then apply User Decision 4 — either widen to `git ls-files --cached --others --exclude-standard` (and say so in §3.4 and §5), or record untracked files created by the fix as an explicit milestone-1 non-goal in §10. Add the corresponding §8 unit.
- **Depends on:** User Decision 4

#### Step 11: Re-run the gates
- **Files:** none (verification only)
- **Addresses:** all
- **Action:** Confirm `REQ-PERF-01` now appears literally in the tech spec and that all 16 PRD REQ ids are cited literally (no reliance on `REQ-CARD-02..04` range notation) so `scripts/validate-traceability.py` and CHECK-S38 both resolve them downstream. (Full traceability binds at forge-3-specs; this is the tech-stage spot check.)
- **Depends on:** Steps 1–10

## Fix Progress

- Step 1: [APPLIED] 2026-08-10 — §3.7 corrected to 298/300 (per C-4) with 2-line headroom noted; §3.6 corrected to 134/300 (V-007)
- Step 2: [APPLIED] 2026-08-10 — §3.2 rationale rewritten to state the true `git add {resolvedFeatureDir}/` staging scope; §3.6 gained the Step 5 enumerated disposition-staging bullet; §6.1 updated to name the Step 5 edit; §2 table row updated; §8 prose guard added (V-001, Decision 1a)
- Step 3: [APPLIED] 2026-08-10 — §2 gained build-adapters.py + test_build_adapters.py rows; "four pinned tests" → five (§1, §6.5); new §6.7 RUNTIME_HELPERS integration point; §8 guard added (V-003)
- Step 4: [APPLIED] 2026-08-10 — §3.7/§6.3 extended: dimension-group ownership tags on SKILL.md lines 43–48 with zero net new lines, rationale stated; §8 prose guard added (V-005)
- Step 5: [APPLIED] 2026-08-10 — §3.5 claimed-totals re-derivation (mismatch = exit 1); §4.2 payload gained claimedTotal/actualTotal/totalMismatch; §5 exit codes updated; §6.2 cites template line 52; §8 mismatch unit added (V-004, Decision 3)
- Step 6: [APPLIED] 2026-08-10 — §3.4 rewritten: `.verification/` unconditional, `adapters/` conditional on drift-gate detection (`scripts/build-adapters.py` present); §5 updated; §3.6 states the fenced invocation passes no `--exclude`; §8 non-gated-adapters unit added (V-006, Decision 2a)
- Step 7: [APPLIED] 2026-08-10 — new §3.8 Performance (REQ-PERF-01): cost model, expected wall-clock, memory posture, milestone-acceptance observation in lieu of CI timing; §8 line added (V-002)
- Step 8: [APPLIED] 2026-08-10 — §3.6 opening records the deliberate supersession of the PRD's "forge-fix Steps 5/6" parenthetical, C-1 binding content honored (V-008)
- Step 9: [APPLIED] 2026-08-10 — §2 CHANGELOG row + §6.6 publish-worthiness sentence (V-009)
- Step 10: [APPLIED] 2026-08-10 — §3.3/§3.4 state working-tree content source; corpus widened to `git ls-files --cached --others --exclude-standard`; §5 updated; §8 untracked-file unit added (V-010, Decision 4)
- Step 11: [APPLIED] 2026-08-10 — verified all 16 PRD REQ ids cited literally in tech-spec.md (grep per id ≥ 1; REQ-CARD range notation removed from §3.7 heading)
