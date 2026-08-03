# Verification Report: stage-exit-coverage (impl, round 6)

Date: 2026-08-01
Pipeline Stage: forge-5-loop (complete, v1)
Mode: impl — served production stage `forge-5-loop`
Method: clean-room re-verification in require-clean mode against the round-5 fix pass
(commits `e4ab92a` + `160c6dd`; base `a5a4cd5`; `git diff a5a4cd5..HEAD` = 124 files,
108 adapter mirrors + 16 non-adapter). Every numeric and factual claim the fix pass wrote
into a comment, docstring or spec was **re-derived with an instrument different from the
one the fix pass used**. Nothing in the repository was modified except this report.

Artifacts Reviewed:
- `specs/stage-exit-coverage/.verification/VERIFY-impl-2026-08-01-round5.md` (Findings, Fix Execution Plan, Decisions, Fix Progress, the disclosed deviation)
- `specs/stage-exit-coverage/.pipeline-state.json` (at `a5a4cd5` and HEAD)
- `git diff a5a4cd5..160c6dd` (124 files, +613/−262: 108 adapter mirrors, 16 non-adapter) and `git diff e89d8fa~1..160c6dd` (the feature's full range)

> **Diff tip note, so these numbers stay reproducible:** every measurement below was taken
> against `160c6dd`, the tip of the round-5 fix pass. A partial draft of *this* report was
> committed as `334d30b` mid-run, so `a5a4cd5..HEAD` now reports 125 files. Substitute
> `160c6dd` for `HEAD` when reproducing any diff figure in this document.
- `tests/test_capability_determination_prose.py`, `tests/test_state_verb_call_sites.py`, `tests/test_check_spec_purity.py`, `tests/test_auto_verify.py`, `tests/test_stage_exit.py`, `tests/test_gate_pytest_reachability.py`, `tests/_forge_paths.py`
- `scripts/forge-session.py`, `scripts/epic-manifest.py`, `scripts/check-spec-purity.py`, `scripts/validate.sh`, `scripts/build-adapters.py`
- `references/shared-conventions.md`; `skills/forge-{1-prd,2-tech,3-specs,4-backlog,verify,fix}/SKILL.md`
- `specs/stage-exit-coverage/{01-architecture-layout.md, 03-verification-state.md, 07-testing-strategy.md, backlog.json}`
- all 72 `adapters/**/shared-conventions.md` mirrors
- `forge.config.json`

Checks Executed: 23 of 23 (17 pass, 4 fail, 2 not-applicable)

## Summary

- **Total findings: 6** — 1 error, 1 inconsistency, 4 improvements, 0 gaps.
- **Eleven of the thirteen round-5 findings are RESOLVED; two are PARTIAL** (V-002 and
  V-003). Every verdict was re-derived independently — none is taken from the Fix Progress.
- **The two round-5 `error`s are the two PARTIALs.** V-001 (`CALL_SPAN`) is fully closed:
  my own canon walker reproduces every number the new comment states, including the six
  four-line sites by file and line and the searched-flag offsets. V-002 is **half** closed:
  the docstring now describes a mutation that genuinely reds at `clause (c1b)` on all six,
  but it names a fragment that lives on **1 of 6** surfaces while claiming it matched "on
  all six", so Step 1's own acceptance ("tell the same story as control 3a-ii") is not met.
- **The recurring failure mode recurred again, and again only in prose.** All three new
  `error`/`inconsistency`-class defects are false or off-by-one claims in newly written
  documentation: the docstring fragment (V-001), `verify_state`'s docstring still giving the
  rationale its sibling docstring was amended to disclaim (V-002), and the flattening
  window's arithmetic (V-005). Mechanical sweeps over all **808** added lines are **clean**
  — 0 column-0 punctuation, 0 merged words, 0 de-indented docstring continuations, 0 TODO
  markers — and **all 1809 tests are green**. Nothing in the suite can see any of them.
- **The highest-risk item is sound.** The `findings-applied` classifier change agrees across
  **all four** classifiers on **all 24** status×version shapes; the regression test genuinely
  fails against pre-fix code on all three of its assertions; and `_verify_state_for` is
  demonstrably on the runtime path — mutating it reds **82** CLI-subprocess tests, first at
  `tests/test_stage_exit.py:134`, exactly as claimed.
- **The disclosed deviation is SOUND**, reproduced: V-007's literal snippet would have
  turned the `AnnAssign`-demotion probe GREEN, so keeping the annotation requirement as an
  extra assertion is strictly stronger and leaves no path open that the snippet closed.
- **But the guard has four *other* open shadowing paths**, one of them an asymmetry created
  by this round's own edit — the same block handles `AnnAssign` **and** `Assign` for
  `ALL_SURFACES` and only `Assign` for `_capability_surfaces`, so adding a type annotation
  to the alias reopens the path round 5 just closed. All four were proven to genuinely
  displace the roster, not to be no-ops.
- **Round 5's own CHECK-I10 claim was wrong and the fix pass's correction is right:**
  **60/72** mirrors are byte-identical to canon, and all 12 that differ are the `adapters/pi/`
  tree, reproduced byte-for-byte by the documented `/feature-forge:` → `/skill:` degradation.
- **The gate is confirmed, not taken on report**, on a healthy disk (2.6 GB free before,
  2.3 GB after): `--check` exit 0, `validate.sh` green twice back-to-back, **1809 passed /
  2 skipped**, 0 fixture bytecode after each, ruff/spec-purity clean, tree clean. The **+1**
  delta was re-derived by node-ID **set difference** (1810 → 1811), added set exactly the one
  new test, **removed set empty**.
- **Pipeline state is exactly as specified**, and the `state-note` rewrite lost nothing.

---

## Measurements

### 1. Gate (re-run independently, not taken on report)

| Check | Claimed by fix pass | Measured this round | Result |
|---|---|---|---|
| `df -h /` before gating | 3.2 GB free | **2.6 GB free** (2.3 GB after both runs) — above the ~1 GB the suite needs | OK |
| `python3 scripts/build-adapters.py --check` | exit 0 | exit **0** | CONFIRMED |
| `bash scripts/validate.sh` run 1 | exit 0, `All checks passed!` | `All checks passed!` | CONFIRMED |
| `bash scripts/validate.sh` run 2 (genuinely back-to-back) | exit 0, `All checks passed!` | `All checks passed!` | CONFIRMED |
| `find tests/fixtures -name '__pycache__' -o -name '*.pyc' \| wc -l` after each | 0 | **0** after run 1, **0** after run 2 | CONFIRMED |
| Collected test count at HEAD | 1811 | **1811 collected** | CONFIRMED |

(Remaining gate items — ruff, spec-purity, `git status`, node-ID set difference — recorded below as they complete.)

### 2. Pipeline state — CONFIRMED

Re-derived directly from `specs/stage-exit-coverage/.pipeline-state.json` and
`git diff a5a4cd5..HEAD` on that file.

| Property | Expected | Measured |
|---|---|---|
| `stages.forge-verify-impl.status` | `findings-applied` | `findings-applied` ✓ |
| `.findingsFile` | round-5 report | `.verification/VERIFY-impl-2026-08-01-round5.md` ✓ |
| `.findingsCount` | 13 | `13` ✓ |
| `.commitHash` | full 40-hex of `e4ab92a` | `e4ab92a34656612612abe029f31669302e503cc3`; `git rev-parse e4ab92a` agrees; length 40 ✓ |
| `.verifiedStageVersion` | **absent** | absent ✓ |
| `.verifiedAt` | absent | absent ✓ (replaced by `fixedAt: 2026-08-01T15:08:25Z`) |
| Other stage entries | undisturbed | `forge-verify-impl` is the **only** changed stage entry ✓ |
| Other top-level keys | undisturbed | only `updatedAt` and `notes` changed ✓ |

**`notes` (rewritten through `state-note`, which overwrites) — nothing lost.**
Old length 1156 → new 1230. Character-level comparison of the two strings shows the
**only** difference is the opening clause: `(30 items, 001-030)` →
`(32 items, 001-032; 031-032 appended by forge-5-loop as fix items after backlog
verification)`. Everything from `. Both verify gates are findings-applied…` through the
closing `NOTE: stageNoun already exists in the live directives dict -- retain it, do not
re-add it.` is byte-identical, including both STANDING INVARIANTS and both TWO TRAPS
clauses.

### 3. `CALL_SPAN` comment — every claim RE-DERIVED AND TRUE (V-001 RESOLVED)

Independent walker (my own, counting the verb line plus each `\`-continued
continuation over `skills/*/SKILL.md` + `references/shared-conventions.md`):

```
total call sites: 34                       (== MIN_CALL_SITES = 34)          ✓
span histogram:   {1: 4, 2: 11, 3: 13, 4: 6}                                 ✓
max span:         4                                                          ✓
```

The six four-line sites named in the comment reproduce **exactly**, file and line:

| Site written into the comment | Measured span | 4th line (truncated by the flattener) |
|---|---|---|
| `skills/forge-1-prd/SKILL.md:116` `state-ecr` | 4 | `--specs-dir "{specsDir}"` |
| `skills/forge-2-tech/SKILL.md:110` `state-ecr` | 4 | `--specs-dir "{specsDir}"` |
| `skills/forge-3-specs/SKILL.md:160` `state-complete` | 4 | `--artifact "<file>" --artifact TRACEABILITY.md --specs-dir …` |
| `skills/forge-4-backlog/SKILL.md:158` `state-complete` | 4 | `--artifact backlog.json --specs-dir "{specsDir}"` |
| `skills/forge-6-docs/SKILL.md:197` `state-complete` | 4 | `--artifact "<doc file>" --specs-dir "{specsDir}"` |
| `skills/forge-verify/SKILL.md:233` `state-verify` | 4 | `--verified-stage-version {version} --specs-dir "{specsDir}"` |

The **real measured basis** the comment now states also reproduces: every `--status
skipped` that `SKIP_STATUS_RE` searches for sits at offset **0 or 1** from its verb line —
`skills/forge-5-loop/SKILL.md:263` → **0**; `skills/forge-4-backlog/SKILL.md:172` → **1**;
`skills/forge-6-docs/SKILL.md:53` → **1**. No searched flag anywhere in canon sits at
offset ≥ 2.

The two untouched measurements in the same block still reproduce: max lookbehind distance
actually relied on is **10**, and exactly two sites are not covered by lookbehind
(`forge-1-prd:116`, `forge-2-tech:110`), both carrying `--epic` at distance **1** below.

**Round-5 V-001 is RESOLVED.** Decision 1(b) was applied faithfully and the module now
gives one number for the quantity.

### 4. Roster-derivation guard — all six claimed probes CONFIRMED at the claimed lines

Run in a scratch root built from **symlinks** to the repo (no copies — the round-5
disk-exhaustion hazard), with `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`, and
`__pycache__` purged between every probe. Reported line numbers are de-shifted by the
line count each mutation inserts.

| Probe | Raw red line | Insert shift | De-shifted | Claimed | Verdict |
|---|---|---|---|---|---|
| P0 unmutated baseline | — | — | — | 43 passed | **43 passed** ✓ |
| P1 roster-PRESERVING hand-kept `ast.List` | 527 | +7 | **520** | :520 | ✓ |
| P2 differently-named hand-kept function | 531 | +11 | **520** | :520 | ✓ |
| P3 `sorted(_capability_surfaces())` | 520 | 0 | **520** | :520 | ✓ |
| P4 `AnnAssign` demoted to `Assign`, still derived | 516 | 0 | **516** | :516 | ✓ |
| P5 decoy kept + `ALL_SURFACES` re-bound | 520 | +8 | **512** | :512 | ✓ |
| P6 `_capability_surfaces = _hand_kept_surfaces` alias | 544 | +12 | **532** | :532 | ✓ |

Every probe produced **exactly one** failure, all in
`test_the_controls_cover_every_determining_surface`, and **the floor at :470 was never
the source of the red** in any of the six. The line map the fix pass recorded
(:512 binding-count · :516 AnnAssign-shape · :520 derivation `Call` · :527 FunctionDef
alias · :532 re-bind alias) is exact against the file at HEAD.

**The disclosed deviation is SOUND.** V-007's literal snippet accepted a plain
`ast.Assign` as the single binding; I reproduced that P4 (`ALL_SURFACES =
_capability_surfaces()`, still derived) would then have satisfied `len(bindings) == 1`
and the `ast.Call` check and gone **GREEN**, contradicting V-007's own acceptance
criterion. Keeping the annotated-assignment requirement as a separate assertion at :516
is strictly stronger than the prescribed snippet and leaves no path open that the snippet
closed. Declining the literal snippet was correct.

**The :527 FunctionDef assertion is not dead code.** Renaming `def _capability_surfaces`
to `_capability_surfaces_impl` and rebinding the name via an *annotated* assignment reds
at :527 (raw 530, shift +3), so all five assertions are individually reachable.

### 5. Module-docstring claims — the forward claims hold, one specific is still false

Measured in-process against the live six-surface roster at HEAD.

**A. Dispatch→print semantic downgrade — RED at `clause (c1b)` on all six. CONFIRMED.**

| Surface | Result |
|---|---|
| `skills/forge-1-prd/SKILL.md` | RED at `clause (c1b)` |
| `skills/forge-2-tech/SKILL.md` | RED at `clause (c1b)` |
| `skills/forge-3-specs/SKILL.md` | RED at `clause (c1b)` |
| `skills/forge-4-backlog/SKILL.md` | RED at `clause (c1b)` |
| `skills/forge-verify/SKILL.md` | RED at `clause (c1b)` |
| `skills/forge-fix/SKILL.md` | RED at `clause (c1b)` |
| `references/shared-conventions.md` § Verify Capability | RED at `clause (c1b)` |

**B. Option relabel stays GREEN. CONFIRMED**, and the docstring's new gloss is accurate:
`*Verify now*` occurs **0 times** in `forge-verify` and `forge-fix` (the mutation is a
no-op there) and once in each of the four authoring stages, where it is applied and the
guard stays green.

**C. The historical claim's *conclusion* is true but the *fragment it names* is wrong on
five of six surfaces.** Reconstructing the merged clause (c1a's three fragments + c1b's
one in a single any-of list) and deleting the dispatch phrasing leaves all six GREEN — so
"merging is not enough" is genuinely demonstrated. But the fragment that survives to keep
each surface matching is **not** `presented through the gate` except on `forge-verify`:

| Surface | Surviving c1 fragment after the c1b deletion |
|---|---|
| `skills/forge-1-prd/SKILL.md` | `reuse the Standard Verify Gate block for consent` |
| `skills/forge-2-tech/SKILL.md` | `reuse the Standard Verify Gate block for consent` |
| `skills/forge-3-specs/SKILL.md` | `reuse the Standard Verify Gate block for consent` |
| `skills/forge-4-backlog/SKILL.md` | `reuse the Standard Verify Gate block for consent` |
| `skills/forge-verify/SKILL.md` | **`presented through the gate`** |
| `skills/forge-fix/SKILL.md` | `presented through the Step 6 gate` |

The literal string `presented through the gate` is present in **1 of 6** capability
paragraphs. It is also absent from `forge-1-prd` at `21f1c34` (the commit at which c1a and
c1b still shared a list), so the sentence is false as history too. See **V-001** below.

### 6. Read-side classifier (V-004) — three-way + epic label agreement CONFIRMED

Exhaustive matrix over `status` ∈ {`passed`, `findings-reported`, `findings-applied`,
`skipped`, `auto-verify-pending`, `pending`, `None`, `findings-resolved`} ×
`verifiedStageVersion` ∈ {absent, 1 (matching), 2 (non-matching)} = 24 shapes.

- `forge-session.verify_state` vs `forge-session._classify_verify_entry` vs
  `forge-session._verify_state_for`: **0 disagreements across all 24 shapes.**
- `epic-manifest.epic_verify_state` (revision = 1) vs `_classify_verify_entry`:
  **0 disagreements across all 24 shapes.**
- `findings-applied` returns `stale` at **absent / matching / non-matching** version in all
  four classifiers. §5.1 identical-labels and §5.2 manifest parity hold.

**The regression test genuinely fails against pre-fix code.** Loading
`git show a5a4cd5:scripts/forge-session.py` and feeding it the exact state
`tests/test_auto_verify.py::test_legacy_findings_applied_carrying_a_version_still_reads_stale`
builds:

```
PRE-FIX  verify_state       -> ('forge-1-prd', 'fresh')     POST-FIX -> ('forge-1-prd', 'stale')
PRE-FIX  pending_verify     -> None                          POST-FIX -> 'forge-1-prd'
PRE-FIX  _verify_state_for  -> 'fresh'                       POST-FIX -> 'stale'
```

All three of the test's assertions fail pre-fix. It constructs the entry **directly**
(`{"status": "findings-applied", "verifiedStageVersion": 1}`), never through
`_write_verify_entry`, so it is a genuine read-side assertion and not a disguised
writer-behaviour test.

**Live behaviour change is correct and bounded.** `forge-bootstrap` and
`epic-orchestration` in this repo sit at `findings-applied` and now read `stale`, which is
the spec'd intent (§4.2 step 4) and the behaviour Decision 2(a) chose. This feature's own
two legacy entries (`forge-verify-specs` v4, `forge-verify-backlog` v3) were left in place
per Decision 3 and are neutralised by the guard.

### 7. V-012 — `_verify_state_for` is genuinely on the runtime path. CONFIRMED

**Orphan sweep (independent instrument).** AST sweep over the executable corpus
(12 files: `scripts/*.py`, `eval/*.py`, `references/loop-agent-selection.py`, plus the
bootstrap templates; `adapters/`, `tests/`, `.venv*` excluded), collecting every
`ast.Name` / `ast.Attribute` / string constant across the corpus and diffing against the
300 top-level function definitions:

- **`_verify_state_for` is referenced** — it is NOT in the orphan set. Its live call site
  is `scripts/forge-session.py:3547`, in `stage_exit`'s non-epic branch.

*(Honest divergence from the fix pass's record: my 12-file corpus reports 6 residual
orphans — `render_launch`, `needs_precheck`, `advertised_set`, `classify` in
`references/loop-agent-selection.py` (a spec-mirrored reference implementation whose API
surface is deliberately exported for the loop skill and its tests) and `adapter_source` in
`scripts/build-adapters.py` (referenced only from a docstring at `:1543`), plus `greet` in
the bootstrap template. The fix pass's "returns NONE over 10 files" used a narrower corpus.
None of these belongs to `stage-exit-coverage` — `build-adapters.py` is marked `—`
unchanged in `01-architecture-layout.md` §2 — so this does not change the verdict, but the
fix pass's "NONE" is corpus-dependent, not absolute.)*

**Mutation (CLI-subprocess, not `test_auto_verify.py`).** In a **real-file** scratch copy
(a symlinked `tests/` silently resolves `Path(__file__).resolve()` back to the real repo
and runs the unmutated script — my first attempt did exactly that and read a false GREEN),
`_verify_state_for`'s body was prefixed with `return "fresh"`:

| Run | Result |
|---|---|
| Unmutated baseline, `tests/test_stage_exit.py` | **507 passed** |
| `_verify_state_for` → constant `"fresh"` | **82 failed, 425 passed** |

The first red is at **`tests/test_stage_exit.py:134`** — `assert d["verifyState"] ==
"never"` inside `test_auto_verify_off_outstanding_verify_gates_standard` — exactly the line
the fix pass recorded. `_exit()` (`tests/test_stage_exit.py:63-71`) runs
`subprocess.run([sys.executable, str(HELPER), "stage-exit", "--json", …])`, so this is a
genuine CLI-subprocess boundary. Further reds at `:143`, `:158`, `:186`, `:209`, `:242`,
`:250`, including the whole `test_verify_freshness_matrix` parametrization. The helper is
unambiguously on the shipped path.

**Declining the signature change was correct.** V-012 floated an optional epic-context
parameter. `tests/test_auto_verify.py::test_read_side_signatures_are_unchanged` pins the
exact signature and `03-verification-state.md` §5.1 says the read-side functions keep their
labels "without changing their signatures". The applier's alternative — route the *non-epic*
branch through the helper and let the epic branch keep its direct `_classify_verify_entry`
call with the manifest revision — achieves the call-path fix without touching four spec
quotations. **The guard does have a real single home:** both branches funnel into
`_classify_verify_entry`, and the 24-shape matrix above shows the epic branch and the
helper produce identical labels. Sound.

### 8. Canon prose (V-006) and adapters — CONFIRMED, and round 5's mirror claim was wrong

- `dispatched on the affirmative` **and** `reuse the Standard Verify Gate block for consent`
  both survive verbatim **inside the same blank-line-delimited paragraph** on all four
  authoring stages and in `references/shared-conventions.md`. All five carry one identical
  wording; the circular "on which … on the affirmative choice", the comma series that made
  "the latter" reach past two clauses, and the `rather than` / `never merely` split are all
  gone.
- `c1a` and `c1b` match **in-paragraph** on all six determining surfaces (§5 above).
- The dispatch→print downgrade reds at **`clause (c1b)` on all six** plus the
  `shared-conventions.md` § Verify Capability section (§5A above).
- `python3 scripts/build-adapters.py --check` → exit **0**.
- **72/72** `adapters/**/shared-conventions.md` mirrors carry the amended sentence
  **exactly once**.

**The 60/72-vs-72/72 question: the fix pass is RIGHT and round 5's CHECK-I10 was wrong.**
Measured by sha256 over all 72 mirrors against canon: **60/72 byte-identical**. The 12 that
differ are **the entire `adapters/pi/` tree**, and for **all twelve** the difference is
explained *entirely* by the documented host-term degradation — applying
`canon.replace("/feature-forge:", "/skill:")` reproduces each pi mirror **byte-for-byte**,
with zero residual lines. Round 5's "72/72 mirrors byte-identical to canon" was
unachievable by construction and was already false before this pass touched anything. The
fix pass's correction is confirmed.

### 9. `01-architecture-layout.md` §2 — the seven rows are correct; §2 is still not complete

Re-derived by diffing the feature's full commit range `e89d8fa~1..HEAD` (49 files,
excluding `adapters/` and `specs/`) against §2's listed paths.

**All seven added rows are present with the correct marker**, verified against `git diff
--name-status`:

| Row added | Marker written | `git` status in range | Correct? |
|---|---|---|---|
| `scripts/check-spec-purity.py` | `M` | `M` | ✓ |
| `references/forge-config-schema.json` | `M` | `M` | ✓ |
| `tests/test_capability_determination_prose.py` | `N` | `A` | ✓ |
| `tests/test_gate_pytest_reachability.py` | `N` | `A` | ✓ |
| `tests/test_state_verb_call_sites.py` | `M` | `M` | ✓ |
| `tests/test_check_spec_purity.py` | `M` | `M` | ✓ |
| `README.md` | `M` | `M` | ✓ |

`.gitignore` and `forge.config.json` were correctly **not** added — both are touched only by
the out-of-band commit `b3110b1`, confirmed by `git log -- <path>`.

**But two changed files remain unlisted**, and unlike `.gitignore`/`forge.config.json` they
*are* this feature's own work:

| File | Commit | In §2? |
|---|---|---|
| `tests/fixtures/status-derivation/lifecycle/epic-manifest.json` | `cbcfbf4 [rauf] 002:` (a loop item of this feature) | **no** |
| `tests/fixtures/valid-epic/auth-overhaul/epic-manifest.json` | `cbcfbf4 [rauf] 002:` | **no** |

See **V-003** below. Minor, and arguably shorthanded by the `<existing epic manifest tests>`
placeholder row, but §2 declares itself the *Complete* File Layout and lists an unchanged
file "for orientation only", so the bar it sets for itself is completeness.

### 10. `07-testing-strategy.md` — both new module descriptions are ACCURATE

Checked by reading each module's assertions, not the finding's summary.

- **`tests/test_capability_determination_prose.py`** — §6.2 bullet. Claims: clauses (a),
  (b), (c) split into four sub-clauses (c1a gate, c1b dispatch, c2 no-skip, c3 no-advance);
  roster **derived** from `test_stage_exit_protocol.CANONICAL_EXIT_SITES`; a per-surface
  negative control for each clause; a structural `ast` guard on the derivation. Verified:
  `CLAUSES` has exactly the keys `a, b, c1a, c1b, c2, c3`; `_capability_surfaces()` iterates
  `CANONICAL_EXIT_SITES`; six controls (1, 2, 3a-i, 3a-ii, 3b, 3c) each parametrized over
  all six surfaces = 36 of the module's 43 tests; the `ast` guard is
  `test_the_controls_cover_every_determining_surface`. **Accurate.**
- **`tests/test_gate_pytest_reachability.py`** — §8.2. Claims: pins pytest importable via
  the same `find_spec` resolution `validate.sh` gates on, so the PASS branch is reachable
  rather than assumed; and that the SKIP branch stays textually distinguishable and
  increments the gate's `WARNINGS` counter. Verified against the module: it asserts
  `importlib.util.find_spec("pytest") is not None`; asserts `"PASS: epic-manifest pytest
  suite"` and `"SKIP: pytest not installed"` are both present in `scripts/validate.sh`; and
  asserts `WARNINGS=$((WARNINGS + 1))` appears within 400 chars after the SKIP line.
  **Accurate** — this is the description the fix pass says it corrected on reading the
  module, and the correction landed on the right side.

### 11. Remaining gate items

| Check | Claimed | Measured | Result |
|---|---|---|---|
| `ruff check scripts/ eval/` | clean | exit **0**, `All checks passed!` | CONFIRMED |
| `ruff check tests/` | 19 | **19 errors** | CONFIRMED (unchanged) |
| `ruff check tests/ --select F841,F541` | clean | exit **0**, `All checks passed!` | CONFIRMED |
| `python3 scripts/check-spec-purity.py` | PASS — 0 violations | exit **0**, `spec-purity: PASS — 0 violations across canonical surfaces.` | CONFIRMED |
| `git status --porcelain` | empty | only `?? …/VERIFY-impl-2026-08-01-round6.md` (this report) | CONFIRMED |
| Suite delta re-derived by **node-ID set difference** | +1, removed set empty | **+1** (1810 → 1811); added set = exactly `tests/test_auto_verify.py::test_legacy_findings_applied_carrying_a_version_still_reads_stale`; **removed set EMPTY** | CONFIRMED |

The node-ID baseline was built **without `git archive`** (`.gitattributes` marks `tests/`,
`specs/`, `eval/` `export-ignore`, so an archive baseline collects zero tests) and **without
`git worktree`** (a worktree writes `.git/worktrees` metadata and would need a mutating
`git worktree remove` to clean up, which this read-only pass may not run). Instead: a real
copy of `tests/` with the four files `git diff --name-only a5a4cd5..HEAD -- tests/` reports
as changed restored from `git show a5a4cd5:<path>`, canon and `scripts/` symlinked to HEAD.
Since the only collection-affecting inputs are the test modules themselves and the six-entry
capability roster (unchanged at 6 across the range), this is an exact baseline for the
test-node delta.

### 12. Backlog (CHECK-I05/I06/I07)

`specs/stage-exit-coverage/backlog.json`: **32 items, ids `001`..`032`,
`Counter({'done': 32})`**, every item carrying a `completedAt`. No `pending` /
`in-progress`. Consistent with the corrected `notes` string (§2 above).

### 13. Full suite and mechanical-damage sweep

- **Full suite at HEAD: `1809 passed, 2 skipped` in 248.79s.** Matches the fix pass's claim
  exactly.
- Mechanical sweeps over all **808 added lines** across the 124-file diff: **0**
  TODO/FIXME/XXX/HACK/TBD markers; **0** column-0 punctuation characters in added `.py`
  lines; **0** genuine merged words (the camelCase candidates are all JSON keys —
  `autoVerify`, `commitHash`, `findingsCount`, `verifyGate`, `verifyState` — plus
  substring artefacts of `NameError`/`AskUserQuestion`); **0** de-indented docstring
  continuations in the four changed non-adapter Python files (a `tokenize` pass over every
  STRING/COMMENT token). **No import line was added, removed or reordered anywhere in the
  diff.**

As in round 5, the mechanical layer is clean and the residual defects are **semantic** —
prose claims that are false against the artifacts they describe.

---

## Findings

### V-001: The module docstring's rebuilt "measured twice" sentence names a fragment that lives on 1 of 6 surfaces while claiming it matched "on all six"

- **Severity:** error
- **Location:** `tests/test_capability_determination_prose.py:30-36` (module docstring, clause (c))
- **Issue:** Round-5 V-002 named **two** independent problems with this sentence: (1) *false as history* — the described mutation could not have been "measured … on all six" because on two surfaces it changes nothing, and the sentence collapsed **two different mutations on two different surfaces** into one; (2) *false as present tense* — the mutation was still green after the split.

  **Problem (2) is fully fixed and independently confirmed.** The sentence now describes the *dispatch-clause* rewrite, and I measured that rewrite going **RED at `clause (c1b)` on all six surfaces** plus the `references/shared-conventions.md` § Verify Capability section. That is a real, biting measurement.

  **Problem (1) survives, with a new wrong specific.** The rewritten sentence reads:

  > "…and while c1a and c1b shared a list, rewriting the *dispatch clause* — `forge-verify`'s "dispatched on the affirmative choice" into "printed for the user" — left **the untouched "presented through the gate" matching on all six**."

  The literal string `presented through the gate` occurs in **1 of the 6** capability paragraphs:

  | Surface | c1a fragment that actually keeps it matching |
  |---|---|
  | `skills/forge-1-prd/SKILL.md` | `reuse the Standard Verify Gate block for consent` |
  | `skills/forge-2-tech/SKILL.md` | `reuse the Standard Verify Gate block for consent` |
  | `skills/forge-3-specs/SKILL.md` | `reuse the Standard Verify Gate block for consent` |
  | `skills/forge-4-backlog/SKILL.md` | `reuse the Standard Verify Gate block for consent` |
  | `skills/forge-verify/SKILL.md` | **`presented through the gate`** |
  | `skills/forge-fix/SKILL.md` | `presented through the Step 6 gate` |

  Round-5's own Deviation-1 analysis established that the three c1a fragments **partition the six surfaces disjointly** and that `presented through the Step 6 gate` is *not* a superstring of `presented through the gate`. So no reading makes the named fragment the thing that "matched on all six". It is also false as history: `presented through the gate` occurs **0 times** in `skills/forge-1-prd/SKILL.md` at `21f1c34`, the commit at which c1a and c1b still shared a list.

  The underlying *conclusion* is true — I reconstructed the merged any-of list, deleted the dispatch phrasing, and all six stayed **GREEN** — so the sentence supports a correct claim with an incorrect measurement, which is the shape round 5 flagged.

  **Step 1's stated acceptance was "read the docstring against control 3a-ii's and confirm the two tell the same story". They do not.** Control 3a-ii's docstring (`:412-417`) is careful and correct, and I verified **both** of its halves: it attributes the surviving match to `presented through the gate` on `forge-verify` *only*, and adds separately that "the authoring stages carried no dispatch phrasing at all" (confirmed: 0 occurrences of `dispatched on the affirmative` in `skills/forge-1-prd/SKILL.md` at `21f1c34`, 1 at `5b375f7`). The module docstring dropped the second half and attached "on all six" to the first.
- **Suggested fix:** Replace the trailing clause so the module docstring states both halves, exactly as control 3a-ii does. Change:

  > `left the untouched "presented through the gate" matching on all six.`

  to:

  > `left the merged clause matching on all six: "presented through the gate" was untouched on \`forge-verify\`, \`forge-fix\` kept "presented through the Step 6 gate", and the four authoring stages carried no dispatch phrasing at all — each surface satisfied the merged list on its own gate fragment.`

  Do not change any fragment in `CLAUSES`. No test change is expected; this is prose.

  **Acceptance evidence (mandatory, and *not* suite-green):** (i) re-derive per surface which c1a fragment matches its capability paragraph and confirm the sentence names the right one for each; (ii) re-confirm `presented through the gate` occurs in exactly one of the six paragraphs; (iii) re-run the merged-list reconstruction and confirm all six stay GREEN; (iv) re-read the amended docstring **against control 3a-ii's, end-to-end as prose**, and confirm neither says anything the other contradicts.
- **References:** `tests/test_capability_determination_prose.py:404-426` (control 3a-ii, the correct account), `:133-149` (`CLAUSES["c1a"]`/`["c1b"]`); round-5 V-002 and its Step 1; round-5 Deviation 1 (the disjoint partition of the three c1a fragments)
- **Checklist:** CHECK-I19

### V-002: `verify_state`'s docstring still attributes `findings-applied` → `stale` to the missing key — the exact rationale this same fix pass disclaimed in the sibling docstring it *did* update

- **Severity:** inconsistency
- **Location:** `scripts/forge-session.py:882-884` (the `stale` bullet) and `:904-907` (the closing paragraph of `verify_state`'s docstring)
- **Issue:** The fix pass added an unconditional `findings-applied → stale` guard in three places and correctly amended **`scripts/epic-manifest.py`**'s `epic_verify_state` docstring to say so explicitly:

  > "``findings-applied`` is classified here **UNCONDITIONALLY, not merely because the writer deletes ``verifiedStageVersion``**: applying fixes is not verifying them, and legacy state loaded without migration (REQ-DEBT-06) may still carry the key."

  `verify_state`'s docstring — the function round-5 V-004 was filed against, in the file the guard was added to — was **not** swept and still states only the superseded rationale, twice:

  - `stale` bullet: "verify was resolved once, but the stage version has since moved (artifact revised) **OR the entry predates the freshness ledger (no `verifiedStageVersion`)**."
  - closing paragraph: "**Absent `verifiedStageVersion`** on a `passed`/`findings-applied` entry (legacy state) is deliberately treated as `stale` — verify rather than skip."

  Both enumerate the reasons an entry lands in `stale` and neither includes the new, now-dominant one. Worse, the closing sentence conditions the `findings-applied` case on the key being **absent**, which invites precisely the inference V-004 existed to kill: that a `findings-applied` entry *carrying* a matching version reads `fresh`. It no longer does — I confirmed `stale` at absent / matching / non-matching version in all four classifiers.

  Behaviour is correct (24-shape matrix, 0 disagreements); this is documentation-only. But it is the round's recurring shape: one of two sibling docstrings making the same claim was updated and the other was left stating the old story, in the file the finding named.
- **Suggested fix:** Two edits in `scripts/forge-session.py`, `verify_state`'s docstring only — no code change, no test change.
  1. Extend the `stale` bullet: after "…(artifact revised) OR the entry predates the freshness ledger (no `verifiedStageVersion`)", add "**, OR the entry is `findings-applied`, which never classifies `fresh` regardless of any version it carries (§4.2 step 4)**".
  2. Replace the closing sentence with wording that matches `epic_verify_state`'s: "A `findings-applied` entry is treated as `stale` **unconditionally** — applying fixes is not verifying them — and an absent `verifiedStageVersion` on a `passed` entry (legacy state) is likewise `stale`: verify rather than skip."

  **Acceptance evidence:** after editing, read `verify_state`'s docstring and `epic_verify_state`'s docstring side by side and confirm neither states a rule the other contradicts; re-run the 24-shape label matrix and confirm it is unchanged.
- **References:** `scripts/epic-manifest.py:1066-1073` (the docstring that *was* amended); `scripts/forge-session.py:938-946` (the guard); `03-verification-state.md` §5.1 (the new seventh rule); round-5 V-004 Step 7
- **Checklist:** CHECK-I19, CHECK-I14

### V-003: `01-architecture-layout.md` §2 is still not the *Complete* File Layout — two fixture files this feature modified remain unlisted

- **Severity:** improvement
- **Location:** `specs/stage-exit-coverage/01-architecture-layout.md` §2, `tests/` block
- **Issue:** All seven rows the fix pass added are correct, present, and carry the right marker (verified against `git diff --name-status e89d8fa~1..HEAD`; see §9 above). `.gitignore` and `forge.config.json` were correctly excluded as out-of-band (`b3110b1`).

  Two files remain, and unlike those two they **are** this feature's own work — both changed by `cbcfbf4 [rauf] 002: Add canonical epic manifest revision with exactly-once increment`, a loop commit of this backlog:

  - `tests/fixtures/status-derivation/lifecycle/epic-manifest.json` (`M`)
  - `tests/fixtures/valid-epic/auth-overhaul/epic-manifest.json` (`M`)

  §2 has no `tests/fixtures/` block at all. The `<existing epic manifest tests>  M` placeholder row arguably shorthands the *tests*, but these are fixture data, and §2 sets its own bar by listing `scripts/build-adapters.py` with a `—` marker "unchanged; listed for orientation only".

  Low impact — nothing reads §2 programmatically — but this is the third consecutive round in which §2 has been declared restored and remained incomplete, so the pattern is worth closing rather than re-deriving each round.
- **Suggested fix:** Add one row to the `tests/` block:

  ```
  fixtures/{status-derivation/lifecycle,valid-epic/auth-overhaul}/epic-manifest.json
                                            M  canonical `revision` added (item 002)
  ```

  matching the block's existing marker column. Do **not** add `.gitignore` or `forge.config.json`.

  **Acceptance evidence:** re-run `git diff --name-status e89d8fa~1..HEAD -- . ':(exclude)adapters/' ':(exclude)specs/'` and confirm every path is either listed in §2 or attributable to `b3110b1`.
- **References:** commit `cbcfbf4`; round-5 V-003 and its Step 10
- **Checklist:** CHECK-I01

### V-004: The rebuilt roster-derivation guard has four open shadowing paths — one of them an asymmetry introduced by this round's own edit

- **Severity:** improvement
- **Location:** `tests/test_capability_determination_prose.py:495-540` (`test_the_controls_cover_every_determining_surface`)
- **Issue:** **The two paths round-5 V-007 named are genuinely closed** — P5 (decoy + re-bind) now reds at `:512` and P6 (`_capability_surfaces = _hand_kept_surfaces`) at `:532`, both previously GREEN. Round 4 asked whether the `ast` form has blind spots of its own; four more remain, all measured GREEN with `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider` and `__pycache__` purged between runs, and **all four proven to genuinely displace the derived roster** (each hand-kept list holds the same six surfaces in *reversed* order — identical content, so every clause control and the ≥6 floor still pass — and `SURFACE_IDS` was observed in the reversed order in every case, confirming the shadow took effect rather than the mutation being a no-op):

  | Probe | Result | Roster actually used |
  |---|---|---|
  | `_capability_surfaces: Final = _hand_kept_surfaces` (**annotated** alias) | **GREEN — 43 passed** | hand-kept |
  | `if True:` `ALL_SURFACES = [...]` (binding one level below `tree.body`) | **GREEN — 43 passed** | hand-kept |
  | `ALL_SURFACES[:] = [...]` (in-place slice; **no** re-binding at all) | **GREEN — 43 passed** | hand-kept |
  | second `def _capability_surfaces(...)` shadowing redefinition | **GREEN — 43 passed** | hand-kept |

  The first is the sharpest, because it is an **asymmetry inside one edit**. The same assertion block deliberately counts *both* `ast.AnnAssign` and `ast.Assign` bindings of `ALL_SURFACES` (`:496-511`) — the fix pass clearly knew an annotated assignment is a distinct binding node — yet the `_capability_surfaces` alias check twelve lines later (`:532-540`) scans for `ast.Assign` **only**. Adding a type annotation to the exact alias P6 closes reopens it.

  The other three are contrived (each needs a decoy left behind), there is no live drift, and the suite is green — hence `improvement`, not `gap`. But this assertion has now been rewritten in four consecutive rounds, so closing the shape class rather than the named instance is the only way the sequence terminates.

  Two things I confirmed are **not** wrong: the floor at `:470` was never the source of the red in any of the ten probes, and the `:527` FunctionDef assertion is genuinely reachable (renaming the def and rebinding the name via an annotated assignment reds there), so no assertion in the block is dead code.
- **Suggested fix:** Generalise the two checks rather than adding four more special cases.
  1. Make the alias check symmetric with the roster check — accept `ast.AnnAssign` as a re-binding too:

     ```python
     assert not [
         node
         for node in tree.body
         if (isinstance(node, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == "_capability_surfaces"
                     for t in node.targets))
         or (isinstance(node, ast.AnnAssign)
             and isinstance(node.target, ast.Name)
             and node.target.id == "_capability_surfaces")
     ], "_capability_surfaces is re-bound at module level — the derivation name is aliased"
     ```
  2. Pin the function to exactly one definition, closing the shadowing-redefinition path:

     ```python
     defs = [n for n in tree.body
             if isinstance(n, ast.FunctionDef) and n.name == "_capability_surfaces"]
     assert len(defs) == 1, (
         f"_capability_surfaces is defined {len(defs)} times at module level — a later "
         "redefinition shadows the derivation while leaving this check green"
     )
     ```
  3. Walk `ast.walk(tree)` rather than `tree.body` when counting `ALL_SURFACES` bindings, and additionally reject any `ast.Subscript`/`ast.Attribute` store target named `ALL_SURFACES` (the `ALL_SURFACES[:] = …` in-place path). One combined comprehension over `ast.walk` covers both the nested-`if` and the slice-assignment probes.

  Extend the existing comment with one sentence: the check must be over *every* binding form and *every* nesting level, because each previous round closed the one shape it was shown and the next shape was found immediately.

  **Acceptance evidence (mandatory, with `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`, `__pycache__` purged between runs, one fresh copy per probe):** all four probes above must go RED **at the new assertion's own de-shifted line number** — not at the floor (`:470`), not at the existing derivation `Call` assertion. The six probes P1–P6 must stay red at their current lines (`:520` ×3, `:516`, `:512`, `:532`). Unmutated copy: 43 passed. Use the reversed-order hand-kept roster so that a probe which *fails to displace* the roster is distinguishable from one the guard genuinely catches.
- **References:** `tests/test_capability_determination_prose.py:341` (the guarded assignment), `:342` (`SURFACE_IDS`, which takes the shadowed value), `:470` (the floor that must not be the source of the red), `:527` (the FunctionDef check); round-5 V-007, round-4 V-001, round-3 V-007, round-3 V-002
- **Checklist:** CHECK-I17

### V-005: `_state_verify_call_text`'s corrected docstring is off by one against the code it describes

- **Severity:** improvement
- **Location:** `tests/test_state_verb_call_sites.py:288-294` (`_state_verify_call_text`'s docstring), against `:301`
- **Issue:** Round-5 V-001 required correcting this docstring from "a `\`-continued line **pair**" so the module states **one** number for the flattening window. The replacement reads:

  > "Joining the verb's line **with up to `CALL_SPAN` lines** lets a single `--status skipped` search see it."

  The code is `" ".join(lines[index : index + CALL_SPAN])` — `CALL_SPAN` lines **in total, including the verb line**, i.e. the verb line plus up to `CALL_SPAN - 1` continuations. Read literally the docstring describes a 4-line window where the code takes 3.

  Everything else in the corrected docstring is exact and I re-derived it: "six run to four lines" ✓, "every flag this function is searched for … sits at offset 0 or 1" ✓ (measured 0, 1, 1 at the three skip-recording surfaces). Only the arithmetic phrasing slipped — which matters here specifically because the whole point of round-5 V-001 was that the module must give **one** number for this quantity, and a reader who computes `CALL_SPAN + 1 = 4` will believe the window reaches canon's longest call, the exact belief the `CALL_SPAN` comment was rewritten to destroy.
- **Suggested fix:** Change "Joining the verb's line with up to `CALL_SPAN` lines" to "Joining `CALL_SPAN` lines starting at the verb's line (so the verb plus up to `CALL_SPAN - 1` continuations)". No code change, no test change.

  **Acceptance evidence:** read the amended sentence against `:301` and confirm the count it states equals the slice width; re-read the `CALL_SPAN` comment block and this docstring end-to-end and confirm both describe the same 3-line window.
- **References:** `tests/test_state_verb_call_sites.py:61-89` (the `CALL_SPAN` comment, which is correct), `:301` (the consumer); round-5 V-001 Step 4
- **Checklist:** CHECK-I19, CHECK-I20

### V-006: No `smokeCommand` is configured — advisory re-affirmed (CHECK-I21)

- **Severity:** improvement
- **Location:** `forge.config.json:11`, `"smokeCommand": null`
- **Issue:** CHECK-I21 requires an advisory finding whenever `smokeCommand` is `null`. Decision 6 resolved to **keep `null`**, and `07-testing-strategy.md` §8.3 records that decision explicitly and correctly ("CHECK-I21 is **not-applicable by design**, not skipped, missing, or a recommendation to invent a smoke command … Do not fabricate a command or change `smokeCommand` as part of this feature (REQ-COMPAT-03)"). Re-assessing this round: **`not-applicable` remains right**, and the round-5 narrowing still holds — all six rounds' defects have been vacuous guards and false prose, which no booting smoke command can detect. The "does it actually run" risk is covered at the real boundary: this round drove the shipped CLI as a genuine subprocess **507 times** through `tests/test_stage_exit.py` at HEAD, all green.
- **Suggested fix:** None required. Keep `smokeCommand: null` per Decision 6 and §8.3. This entry exists only to satisfy CHECK-I21's mandatory advisory; it is **not** a recommendation to configure one, and it must not be read as a remedy for the recurring false-narrative failures.
- **References:** `specs/stage-exit-coverage/07-testing-strategy.md` §8.3; `tests/test_smoke_command.py`; round-5 V-013 and Decision 6
- **Checklist:** CHECK-I21

---

## Round-5 finding disposition (each independently re-measured)

| Round-5 finding | Verdict | Independent evidence derived this round |
|---|---|---|
| **V-001** `CALL_SPAN`'s stated measurement is false | **RESOLVED** | My own canon walker reproduces every number now written into the comment: 34 sites (= `MIN_CALL_SITES`), histogram `{1:4, 2:11, 3:13, 4:6}`, max span **4** at exactly the six named file:line sites, and max searched-flag offset **1** (`forge-5-loop:263`→0, `forge-4-backlog:172`→1, `forge-6-docs:53`→1). Decision 1(b) applied faithfully; the untouched 10-above / 1-below measurements also still reproduce. Residual off-by-one in the consumer's docstring → V-005. |
| **V-002** docstring credits the split with catching a green mutation | **PARTIAL** | The mutation identity is corrected and the forward claim is TRUE — the dispatch→print downgrade reds at `clause (c1b)` on all six plus `shared-conventions.md`; the option relabel stays GREEN and the docstring's gloss (`*Verify now*` 0 times in `forge-verify`/`forge-fix`) is accurate. But the "collapsed measurement" half of V-002's issue survives: the named fragment lives on 1 of 6 surfaces. Step 1's own acceptance ("same story as control 3a-ii") is not met. → **V-001**. |
| **V-003** §2 omits every file the fix passes added | **PARTIAL** | All seven rows present with correct markers, verified against `git diff --name-status` over `e89d8fa~1..HEAD`; `.gitignore`/`forge.config.json` correctly excluded (`b3110b1`). Two `tests/fixtures/**/epic-manifest.json` files from this feature's own commit `cbcfbf4` remain unlisted. → **V-003**. |
| **V-004** `findings-applied` reads `fresh` on the read side | **RESOLVED** | 24-shape × 4-classifier matrix: `verify_state`, `_classify_verify_entry`, `_verify_state_for` and `epic_verify_state` **all agree on every shape**, and `findings-applied` → `stale` at absent / matching / non-matching version in all four. §5.1 identical labels and §5.2 manifest parity hold. The regression test **genuinely fails pre-fix** (`('forge-1-prd','fresh')`, `pending_verify` → `None`, `_verify_state_for` → `'fresh'` against `git show a5a4cd5:`), constructs the entry directly, and is not a writer-behaviour assertion. Live change bounded to `forge-bootstrap` / `epic-orchestration` / this feature's two legacy entries, all correct. Residual docstring drift → **V-002**. |
| **V-005** four-way split narrated as "halves" in nine places | **RESOLVED** | `grep -n "half\|halves"` over `tests/test_capability_determination_prose.py` returns **nothing**. `tests/test_state_verb_call_sites.py:197` ("both halves of the window") correctly left alone — genuinely two-sided. Remaining `two`/`three` hits all refer to other quantities (two numbered steps, three delegating skills, two removed fragments). |
| **V-006** circular canon sentence + `shared-conventions.md` divergences | **RESOLVED** | One wording on all five canon surfaces; `dispatched on the affirmative` and `reuse the Standard Verify Gate block for consent` both survive verbatim **inside the same blank-line paragraph** on every one; `c1a`/`c1b` match in-paragraph on all six; dispatch→print reds at `clause (c1b)` on all six; `--check` exit 0; **72/72** mirrors carry the amended sentence exactly once. |
| **V-007** two shadowing blind spots in the `ast` guard | **RESOLVED (for the two named)** | P5 → RED `:512`, P6 → RED `:532`, both previously GREEN. The disclosed deviation is **SOUND**: V-007's literal snippet would have turned P4 GREEN, contradicting its own acceptance criterion; keeping `:516` as an extra assertion is strictly stronger and closes nothing the snippet closed. Four *other* shadowing paths remain open → **V-004**. |
| **V-008** affirmative-choice label pinned nowhere | **RESOLVED (option a)** | The docstring now records the deliberate non-pin with its reason, and **the reason is true**: `*Verify now*` occurs 0 times in `forge-verify` and `forge-fix`, so no label fragment could be a uniform `CLAUSES` entry; the relabel is GREEN on all four authoring stages and a no-op on the other two. `CLAUSES["c1b"]` untouched, as required. |
| **V-009** drift warning attributed to pytest internals | **RESOLVED** | Measured, path recorded: with `"eval/README.md",  # 1` inflated to `# 9999` on a real-file scratch copy, the warnings-summary location line reads `…/tests/test_check_spec_purity.py:462: UserWarning: CITATI…` and echoes the `warnings.warn(` source line — **not** `_pytest/python.py`. Test still passes (`33 passed, 1 skipped, 1 warning`); unmutated copy emits **0** warnings. `:462` is the `warnings.warn(` line. |
| **V-010** unqualified `V-002` beside a round-qualified ID | **RESOLVED** | `:483` reads `round-3 V-002`, `:484` `round-4 V-001`, and `:119` `(round-3 V-001)`. All finding IDs in the module are now round-qualified; no bare `V-00N` remains. |
| **V-011** note gives a backlog count two short | **RESOLVED** | `backlog.json` holds **32** items, ids `001`..`032`, `Counter({'done': 32})`. The note was rewritten through `state-note` (1156 → 1230 chars) and character comparison shows the **only** difference is the opening clause — both STANDING INVARIANTS, both TWO TRAPS and the closing `stageNoun` sentence are byte-identical. |
| **V-012** `_verify_state_for` has no non-test caller | **RESOLVED** | AST orphan sweep over the executable corpus: `_verify_state_for` is **referenced**, live call at `scripts/forge-session.py:3547`. Mutating its body to a constant `"fresh"` reds **82** tests in `tests/test_stage_exit.py` (baseline 507 passed), first at **`tests/test_stage_exit.py:134`**, through the genuine `subprocess.run([sys.executable, HELPER, "stage-exit", "--json", …])` boundary at `:63-71`. Declining the signature change was **correct** (pinned by `test_read_side_signatures_are_unchanged` and by §5.1's "without changing their signatures"), and the guard does have a real single home — both branches funnel into `_classify_verify_entry`, which the 24-shape matrix shows agreeing with the epic branch. |
| **V-013** no `smokeCommand` configured | **RESOLVED as a decision** | Decision 6 kept `null`; `07-testing-strategy.md` §8.3 records it as not-applicable **by design** with REQ-COMPAT-03 behind it. Re-affirmed as **V-006**, per CHECK-I21's mandatory advisory. |

**One correction to the fix pass's own record, for round 7's benefit:** the round-5 Fix
Progress (Step 7) names the epic reader `_epic_verify_state`. No such symbol exists —
`grep -rn "_epic_verify_state" scripts/ tests/` returns nothing. The function is
**`epic_verify_state`** (public, `scripts/epic-manifest.py:1050`), and it is the function
that was correctly amended. This is a naming slip in the record only; the shipped change is
right. Not filed as a finding — the round-5 report is a committed historical artifact — but
recorded here so it is not chased as a phantom.

---

## Checks Executed

| Check | Result | Note |
|---|---|---|
| CHECK-I01 | **fail** | V-003. All seven rows added by the fix pass are present with correct markers, verified against `git diff --name-status e89d8fa~1..HEAD`; two `tests/fixtures/**/epic-manifest.json` files from commit `cbcfbf4` remain unlisted in a section titled *Complete* File Layout. |
| CHECK-I02 | not-applicable | No `package.json` anywhere in the repo; Python + markdown plugin, no exports map. |
| CHECK-I03 | pass | The `forge-session.py` diff is exactly the two guard insertions plus the `stage_exit` routing block. No `Literal` alias, `Final` constant, `TypedDict` or quoted callable signature from `00-core-definitions.md` was touched; **zero import lines added, removed or reordered** anywhere in the 124-file diff. |
| CHECK-I04 | pass | `UsageError` unchanged; its handler still prints `Error: {exc}` to stderr and returns 2. Untouched by this diff. |
| CHECK-I05 | pass | 32/32 backlog items `done` with `completedAt`; the two standing traps still hold (item 024's guard derives `EXIT_STAGES` by regex + literal-eval; every `state-verify` fence keeps `--epic` inside the 12/3 window — re-derived: max above-distance relied on is 10, the two lookahead-covered sites carry it at distance 1). The round-5 V-004 read-side gap is closed and independently confirmed. |
| CHECK-I06 | pass | `Counter({'done': 32})` — no `pending` or `in-progress`. |
| CHECK-I07 | pass | Every round-5 acceptance claim was re-derived from the code/artifacts this round, by instruments different from the fix pass's. 11 of 13 fully reproduce; 2 are PARTIAL (V-002, V-003) and are filed. |
| CHECK-I08 | pass | Zero import changes in the diff. All four changed test modules import and run (43 / 34 / 84 / 10 respectively); `check-spec-purity.py` executes standalone, exit 0. |
| CHECK-I09 | pass | V-006's canon amendment is uniform across all five surfaces, both load-bearing fragments intact and in-paragraph; `build-adapters.py --check` exit 0; 72/72 mirrors carry the sentence exactly once. |
| CHECK-I10 | pass | **Round 5's own CHECK-I10 claim was wrong and the fix pass's correction is right.** 60/72 `shared-conventions.md` mirrors are byte-identical to canon; the 12 that differ are the entire `adapters/pi/` tree and **all twelve** are reproduced byte-for-byte by `canon.replace("/feature-forge:", "/skill:")` — zero residual lines. The meaningful invariant (amended sentence exactly once) holds 72/72. |
| CHECK-I11 | pass | `ruff check scripts/ eval/` exit 0. `ruff check tests/` **19 errors**, unchanged. `ruff check tests/ --select F841,F541` clean. |
| CHECK-I12 | pass | `bash scripts/validate.sh` exit 0 twice genuinely back-to-back on a healthy disk (2.6 GB free before, 2.3 GB after), `All checks passed!` both times, **0** `tests/fixtures` bytecode after each. Full suite `1809 passed, 2 skipped`. |
| CHECK-I13 | pass | **0** TODO/FIXME/XXX/HACK/TBD markers among the 808 added lines. |
| CHECK-I14 | **fail** | V-002. The `CITATION_GRANDFATHERED` drift warning is now correctly attributed (measured: `tests/test_check_spec_purity.py:462`, not `_pytest/python.py`), and the new guard comments in all three classifiers are accurate. The failure is `verify_state`'s docstring, which still gives the superseded rationale for a rule its own function now enforces unconditionally. |
| CHECK-I15 | pass | The one behavioural constant, `CALL_SPAN = 3`, is now backed by a measurement I reproduced exactly. `MIN_CALL_SITES = 34` re-derived. No new hardcoded value in the diff. |
| CHECK-I16 | pass | **+1** re-derived by test-node-ID **set difference** (1810 → 1811), added set exactly `test_legacy_findings_applied_carrying_a_version_still_reads_stale`, **removed set EMPTY**. Baseline built without `git archive` (export-ignore) and without `git worktree` (would write `.git`). |
| CHECK-I17 | **fail** | V-004. All six claimed roster-guard probes reproduce at exactly the claimed de-shifted lines, the floor never fires, and the disclosed deviation is SOUND — but four further shadowing paths are GREEN, one of them an asymmetry created by this round's own edit. Also confirmed: the `:527` FunctionDef assertion is reachable (not dead code). |
| CHECK-I18 | pass | `README.md` present and now listed in §2; `docs/architecture/` holds three feature dirs. `stage-exit-coverage` absent because `forge-6-docs` has not run — correct for impl-verify. |
| CHECK-I19 | **fail** | V-001, V-002, V-005. Mechanical sweeps **clean** (0 column-0 punctuation, 0 merged words, 0 de-indented docstring continuations across all changed Python files); the failures are semantic — three newly-written or newly-corrected prose passages that are false or off-by-one against the artifacts they describe. |
| CHECK-I20 | **fail** | V-005. The `CALL_SPAN` comment's documented basis is now fully true and independently re-derived; `03-verification-state.md` §5.1's new seventh rule matches the shipped classifiers exactly. The failure is the consumer docstring's window arithmetic. |
| CHECK-I21 | not-applicable | `smokeCommand` is `null`. Advisory re-affirmed as V-006; `07-testing-strategy.md` §8.3 records it as not-applicable **by design** under REQ-COMPAT-03. The shipped CLI was driven as a genuine subprocess 507 times this round, all green. |
| CHECK-I22 | pass | V-012 closed and independently confirmed: `_verify_state_for` is out of the orphan set, has a live call at `scripts/forge-session.py:3547`, and mutating it reds 82 CLI-subprocess tests first at `tests/test_stage_exit.py:134`. (Residual orphans in my 12-file corpus — `references/loop-agent-selection.py`'s exported API and `build-adapters.py:adapter_source` — are outside this feature; `build-adapters.py` is marked `—` unchanged in §2.) |
| CHECK-I23 | not-applicable | Python stack, no universal bootstrap entry: no `pyproject.toml`, no framework startup hook, no ASGI/WSGI app object. Unchanged by this round's diff. |

**Executed 23 of 23 checks. Results: 17 pass, 4 fail, 2 not-applicable.**

---

## Fix Execution Plan

### User Decisions Required

**Decision 1 (V-004) — how far to generalise the roster-derivation guard.** This assertion
has been rewritten in four consecutive rounds, and each rewrite closed exactly the shapes
the previous round demonstrated. The applier should not pick silently:

- **(a) Generalise the shape class** (the suggested fix): make the alias check accept
  `AnnAssign`, pin the `FunctionDef` count to exactly 1, and walk `ast.walk(tree)` rather
  than `tree.body` so nested and in-place bindings are caught. Closes all four probes and,
  more importantly, the *class*. Cost: the assertion grows again, and `ast.walk` will also
  see bindings inside function bodies, so the comprehension needs a module-level-scope
  filter or it will produce false positives.
- **(b) Close only the asymmetry** — add `AnnAssign` to the alias check and nothing else.
  One line of the four probes closed; cheapest; leaves the nested/in-place/redefinition
  paths open and guarantees a fifth rewrite if round 7 probes them.
- **(c) Record and stop.** Add a comment stating that module-level shadowing beyond a single
  re-binding is out of scope, because every remaining path requires deliberately leaving a
  decoy behind. Converts a silent hole into a recorded decision, the device the module
  already uses for `SURFACES_WITHOUT_PROSE`.

**Recommendation: (a)**, with the scope filter. Four rounds of instance-by-instance
patching is the evidence that (b) does not terminate, and (c) understates the risk given
that the *annotated-alias* variant is one keystroke from the path round 5 just closed.

> **RESOLVED 2026-08-01 — (a), generalise the shape class.** Chosen by the user at the
> `forge-fix` decision gate, matching the recommendation. Applied in Step 3 with the
> module-level-scope filter implemented as `_module_scope_nodes`, which descends through
> control flow but stops at every new scope (`FunctionDef`/`AsyncFunctionDef`/`ClassDef`)
> — so the nested-`if` binding is caught while a function-local of the same name is not
> a false positive. All four probes plus the six pre-existing ones are RED; see the Fix
> Progress record below for the per-probe de-shifted lines.

**All other findings require no policy call.** V-001, V-002, V-003 and V-005 are prose
corrections with no behavioural consequence; V-006 is an advisory that requires no action.

### Execution Steps

#### Step 1: Correct the module docstring's "measured twice" sentence
- **Files:** `tests/test_capability_determination_prose.py` (`:30-36`)
- **Addresses:** V-001
- **Action:** Replace the trailing clause `left the untouched "presented through the gate" matching on all six.` with the two-part account in V-001's suggested fix, naming the surviving c1a fragment for each group of surfaces. Do not touch any `CLAUSES` entry.
- **Acceptance evidence:** the four items listed in V-001, ending with an **end-to-end prose re-read** of the module docstring against control 3a-ii's (`:404-426`). No test change expected; `43 passed` before and after.
- **Depends on:** none — do this first; it is the round's only `error`.

#### Step 2: Sweep `verify_state`'s docstring to match its sibling
- **Files:** `scripts/forge-session.py` (`:882-884`, `:904-907`)
- **Addresses:** V-002
- **Action:** Apply both edits from V-002's suggested fix. Docstring only — do not touch the guard, the ordering, or any return value.
- **Acceptance evidence:** read `verify_state`'s and `epic_verify_state`'s docstrings side by side and confirm they state the same rule; re-run the 24-shape × 4-classifier label matrix and confirm it is byte-for-byte unchanged; `ruff check scripts/ eval/` clean.
- **Depends on:** none

#### Step 3: Close the roster-derivation guard's remaining shadowing paths
- **Files:** `tests/test_capability_determination_prose.py` (`:495-540`, and the comment at `:474-494`)
- **Addresses:** V-004
- **Action:** Per Decision 1. Under **(a)**: apply all three changes in V-004's suggested fix, adding a module-level-scope filter so `ast.walk` does not flag bindings inside function bodies. Under **(b)**: add the `AnnAssign` branch to the alias check only. Under **(c)**: add the recorded-decision comment and change no assertion. Extend the comment either way with one sentence naming why the check is written over binding *forms* rather than one node.
- **Acceptance evidence (mandatory, `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`, `__pycache__` purged between runs, one fresh copy per probe):** under (a), all four probes in V-004's table go RED at the new assertion's own de-shifted line; under (b), the annotated-alias probe goes RED and the other three are re-recorded as still-GREEN in the fix record. In every case the six probes P1–P6 must stay red at `:520`/`:520`/`:520`/`:516`/`:512`/`:532` (de-shifted) and the floor at `:470` must never be the source of a red. Unmutated copy: 43 passed. Use the **reversed-order** hand-kept roster so an ineffective mutation is distinguishable from a caught one.
- **Depends on:** Step 1 (same file), Decision 1

#### Step 4: Fix the flattening-window arithmetic in `_state_verify_call_text`
- **Files:** `tests/test_state_verb_call_sites.py` (`:288-294`)
- **Addresses:** V-005
- **Action:** Apply V-005's one-sentence replacement. Change nothing else in the module — the `CALL_SPAN` comment block is correct and was fully re-derived this round.
- **Acceptance evidence:** the stated count equals the slice width at `:301`; re-read the `CALL_SPAN` comment and this docstring end-to-end and confirm both describe the same 3-line window; `10 passed` in that module.
- **Depends on:** none

#### Step 5: Complete `01-architecture-layout.md` §2
- **Files:** `specs/stage-exit-coverage/01-architecture-layout.md` (§2, `tests/` block)
- **Addresses:** V-003
- **Action:** Add the fixtures row from V-003's suggested fix, matching the `tests/` block's existing marker column (col 44). Do **not** add `.gitignore` or `forge.config.json`.
- **Acceptance evidence:** re-run `git diff --name-status e89d8fa~1..HEAD -- . ':(exclude)adapters/' ':(exclude)specs/'` and confirm every path is either listed in §2 or attributable to `b3110b1`.
- **Depends on:** none

#### Step 6: Re-gate
- **Action:** No canon or adapter surface is touched by Steps 1–5, so `build-adapters.py` regeneration is **not** required — but run `python3 scripts/build-adapters.py --check` anyway to confirm exit 0. Then **check `df -h /` for ≥1 GB free** (round 5 lost a full gate to disk exhaustion; the disk was at 2.3 GB after this round's runs), then `bash scripts/validate.sh` **twice back-to-back** (both exit 0, both `All checks passed!`, both **1809 passed / 2 skipped** — Steps 1–5 add and remove no tests, so a node-ID set difference against HEAD must be **empty on both sides**), then `find tests/fixtures -name '__pycache__' -o -name '*.pyc' | wc -l` after each (both 0), then `ruff check scripts/ eval/`, `ruff check tests/` (must stay at **19**), `ruff check tests/ --select F841,F541`, `python3 scripts/check-spec-purity.py` (PASS — 0 violations; note Step 2 edits `scripts/forge-session.py`, which is **not** grandfathered, so any `0N §` citation in the new docstring text will red-gate — keep it self-contained), and `git status --porcelain` (empty).
- **Verification discipline:** every prose edit in this plan must be accepted by **re-reading the passage end-to-end as prose against the artifact it describes**, never by diffing and never by suite-green. Six consecutive rounds have now shipped a mechanically-correct change wrapped in a false narrative, and all 1809 tests were green for every one of them.
- **Depends on:** Steps 1–5

---

## Coverage

Every area named in the dispatch was reached. Specifically:

- ✅ `CALL_SPAN` re-measurement (histogram, six four-line sites, `--status skipped` offsets) — independent walker
- ✅ Module-docstring claims (dispatch-clause rewrite red on all six; option relabel green; same-story-as-3a-ii check)
- ✅ Seven `01-architecture-layout.md` §2 rows + marker correctness, against the feature's full commit range
- ✅ Two `07-testing-strategy.md` module descriptions, read against the modules' assertions
- ✅ Six roster-guard mutation probes with de-shifted line numbers, plus five new blind-spot probes and an effectiveness proof for each
- ✅ V-004 code change: 24-shape × 4-classifier label matrix; pre-fix failure of the regression test; live behaviour bounded
- ✅ V-012: AST orphan sweep + CLI-subprocess mutation with line number
- ✅ V-006 canon prose + all 72 adapter mirrors + the 60/72-vs-72/72 question
- ✅ Pipeline state and the full `notes` string
- ✅ Gate: `df` first, `build-adapters --check`, `validate.sh` ×2, bytecode counts ×2, ruff ×3, spec-purity, `git status`, full-suite totals, node-ID set-difference delta
- ✅ CHECK-I01..I23, all 23 executed

**Two deliberate methodological substitutions**, both disclosed above: the node-ID baseline
was built by restoring the four changed test files from `git show a5a4cd5:` into a real-file
scratch root rather than via `git worktree` (a worktree writes `.git/worktrees` metadata and
would require a mutating `git worktree remove` that a read-only pass may not run), and all
mutation probes used symlinked or real-copy scratch roots rather than `cp -al` of the 592 MB
repo. Both are noted where they occur so a future round can reproduce or challenge them.

**A measurement hazard worth carrying forward:** a scratch root whose `tests/` are
**symlinks** silently defeats mutation probes. `tests/_forge_paths.py` computes
`REPO_ROOT = Path(__file__).resolve().parent.parent`, and `resolve()` follows the symlink
back to the real repository — so the subprocess under test runs the **unmutated** script and
the probe reads a false GREEN. My first `_verify_state_for` mutation reported `507 passed`
for exactly this reason before the real-file copy reported `82 failed`. Any future probe
that mutates something under `scripts/` must use **real file copies** of `tests/`.


---

## Fix Progress

Applied 2026-08-01 by `/feature-forge:forge-fix stage-exit-coverage --served-stage forge-5-loop`
(owner: direct). Decision 1 resolved to **(a)** before any step ran.

- Step 1: [APPLIED] 2026-08-01 — `tests/test_capability_determination_prose.py` module
  docstring, clause (c): the trailing "left the untouched `presented through the gate`
  matching on all six" replaced with the two-part account naming the surviving c1a
  fragment per surface group. Acceptance re-derived independently, not taken from the
  report: (i) per-surface c1a match is `reuse the Standard Verify Gate block for consent`
  on the four authoring stages, `presented through the gate` on `forge-verify`,
  `presented through the Step 6 gate` on `forge-fix`; (ii) the literal
  `presented through the gate` occurs in exactly **1 of 6** capability paragraphs;
  (iii) the merged c1a+c1b list after the dispatch-clause rewrite stays **GREEN on 6 of 6**,
  each on its own gate fragment; (iv) the history the sentence asserts was re-measured at
  `21f1c34` — `forge-1-prd` carried **0** occurrences of `dispatched on the affirmative`
  and matched via its gate fragment, `forge-verify` held `presented through the gate`,
  `forge-fix` held `presented through the Step 6 gate` — and the amended docstring was
  read end-to-end against control 3a-ii (`:404-426`): neither states anything the other
  contradicts, mine adding the `forge-fix` half 3a-ii leaves implicit. 43 passed.
- Step 2: [APPLIED] 2026-08-01 — `scripts/forge-session.py`, `verify_state` docstring only.
  The `stale` bullet now names the `findings-applied` reason, and the closing paragraph
  states the rule unconditionally, matching `epic_verify_state`'s amended docstring
  (`scripts/epic-manifest.py:1066-1073`) read side by side. No code, guard, ordering or
  return value touched. The 24-shape x classifier matrix was re-run and is unchanged:
  `findings-applied` -> `stale` at absent / matching / non-matching version alike;
  `passed` -> `fresh` only at a matching version. `ruff check scripts/ eval/` clean.
- Step 3: [APPLIED] 2026-08-01 — Decision 1 **(a)**. `test_the_controls_cover_every_determining_surface`
  now asserts over binding FORMS and SCOPES rather than named instances: new helpers
  `_module_scope_nodes` (control-flow descent, stops at every new scope),
  `_store_target_names` (recovers the global through subscript/attribute/star/tuple) and
  `_module_scope_writes` (`Assign`/`AnnAssign`/`AugAssign`); the alias check is now
  symmetric with the roster check, and `_capability_surfaces` is pinned to exactly one
  definition. The comment records why the check is written over forms rather than one node.
  **Mandatory probe battery** — real file copies of `tests/` (symlinks defeat the probe
  per the report's measurement hazard), `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`,
  `__pycache__` purged, one fresh copy per probe, reversed-order hand-kept roster:

  | Probe | Result | De-shifted line |
  |---|---|---|
  | P1 literal hand-kept value | RED | derivation `Call` (`:574`) |
  | P2 derived from another function | RED | derivation `Call` (`:574`) |
  | P3 wrapped in `list()` | RED | derivation `Call` (`:574`) |
  | P4 `AnnAssign` demoted to `Assign` | RED | `AnnAssign` (`:570`) |
  | P5 decoy + re-bind | RED | count (`:566`) |
  | P6 plain alias | RED | alias (`:591`) |
  | N1 **annotated** alias | RED | alias (`:591`) |
  | N2 nested-`if` re-bind | RED | count (`:566`) |
  | N3 in-place `ALL_SURFACES[:] =` | RED | count (`:566`) |
  | N4 shadowing redefinition (before the binding) | RED | `len(definitions) == 1` (`:587`) |
  | C0 unmutated control | GREEN | — 43 passed |

  The floor (`:526`) was **never** the source of a red. Roster displacement was proven for
  every probe: `SURFACE_IDS` was observed in the reversed hand-kept order in all ten, so
  no probe is a no-op the guard merely appeared to catch. One harness correction is worth
  recording: a hand-kept stub that *calls* the derivation recurses infinitely once the
  alias probes rebind the name, so P6/N1 first errored at import rather than at the
  assertion; the roster must be a static snapshot taken before the alias. Likewise N4 must
  place the second `def` **before** the `ALL_SURFACES` binding or the roster is not
  actually displaced.
- Step 4: [APPLIED] 2026-08-01 — `tests/test_state_verb_call_sites.py`, `_state_verify_call_text`
  docstring: "Joining `CALL_SPAN` lines starting at the verb's line (so the verb plus up to
  `CALL_SPAN - 1` continuations)". `CALL_SPAN = 3` and the consumer slices
  `lines[index : index + CALL_SPAN]` — width 3, which is what the sentence now states. Read
  end-to-end against the `CALL_SPAN` comment block (`:45-89`): both describe the same
  3-line window. Nothing else in the module touched. 10 passed.
- Step 5: [APPLIED] 2026-08-01 — `01-architecture-layout.md` §2, one row added to the
  `tests/` block for `fixtures/{status-derivation/lifecycle,valid-epic/auth-overhaul}/epic-manifest.json`
  at the block's existing marker column. `.gitignore` and `forge.config.json` deliberately
  not added. Acceptance re-run: `git diff --name-status e89d8fa~1..HEAD -- . ':(exclude)adapters/' ':(exclude)specs/'`
  yields 49 paths, every one now listed in §2, covered by the `<existing epic manifest tests>`
  placeholder row (`tests/test_epic_manifest.py`), or attributable to `b3110b1`
  (`.gitignore`, `forge.config.json`).
- Step 6: [APPLIED] 2026-08-01 — re-gate, on 2.8 GB free. **Deviation from the plan, disclosed:**
  Step 6 asserted "no canon or adapter surface is touched by Steps 1–5, so `build-adapters.py`
  regeneration is **not** required". That premise is **wrong** — Step 2 edits
  `scripts/forge-session.py`, which is mirrored into all six adapter trees, and
  `--check` exited **1** naming all six mirrors. Regeneration was run and the six
  `adapters/*/scripts/forge-session.py` mirrors are committed with this pass; `--check`
  then exited 0. Remaining gate, all green: `validate.sh` twice back-to-back (both exit 0,
  both `All checks passed!`, both **1809 passed / 2 skipped**), `find tests/fixtures`
  bytecode **0** after each, `ruff check scripts/ eval/` clean, `ruff check tests/` still
  **19**, `ruff check tests/ --select F841,F541` clean, `check-spec-purity.py` PASS
  (0 violations — the `§4.2 step 4` coordinate in the new docstring is a bare `§`, which
  `_SPEC_CITATION_RE` deliberately does not match). Node-ID **set difference** against HEAD
  is **empty on both sides** (1811 collected both ways), confirming Steps 1–5 add and
  remove no tests.

**Verification discipline honoured:** every prose edit above was accepted by re-reading the
passage end-to-end against the artifact it describes, and every numeric claim was
re-derived with an instrument independent of the one that wrote it — never by diffing and
never by suite-green.
