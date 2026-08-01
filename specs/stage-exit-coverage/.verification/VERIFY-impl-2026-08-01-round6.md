# Verification Report: stage-exit-coverage (impl, round 6)

Date: 2026-08-01
Pipeline Stage: forge-5-loop (complete, v1)
Mode: impl — served production stage `forge-5-loop`
Method: clean-room re-verification in require-clean mode against the round-5 fix pass
(commits `e4ab92a` + `160c6dd`; base `a5a4cd5`; `git diff a5a4cd5..HEAD` = 124 files,
108 adapter mirrors + 16 non-adapter). Every numeric and factual claim the fix pass wrote
into a comment, docstring or spec was **re-derived with an instrument different from the
one the fix pass used**. Nothing in the repository was modified except this report.

> **STATUS: IN PROGRESS — written incrementally.** Sections are appended as each area
> completes. Areas not yet reached are listed explicitly under "Coverage" at the end.

---

## Measurements completed so far

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

