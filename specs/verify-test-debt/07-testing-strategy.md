# 07 — Testing Strategy

> How this feature is verified, what "done" counts as, and how the trial that runs
> alongside it is instrumented. This feature's *deliverable* is largely test code, so this
> document is not "how we test the feature" in the usual sense — it is the **gate list, the
> count accounting, and the trial measurement** that together decide whether the work
> landed.
>
> Locate every symbol by **name**, never by line number (C-07).

## Requirement Coverage

| REQ ID | Requirement | Section |
|---|---|---|
| REQ-QUAL-01 | Full suite passes; baseline 1840 passed / 2 skipped | §2, §3 |
| REQ-QUAL-02 | `ruff check tests/` ≤19 errors | §3, §4.3 |
| REQ-QUAL-03 | `validate.sh` reports "All checks passed!" | §3 |
| REQ-QUAL-04 | Success targets are countable, never wall-clock | §5, §6 |
| REQ-CANON-01 | Adapter regeneration, `--check` exits 0 | §3 |
| REQ-CANON-02 | `check-spec-purity.py` 0 violations | §3 |
| REQ-CANON-03 | Narration states intent only | §4.4 |
| REQ-OBS-01 | Loosened assertions keep diagnostic value | §4.2 |
| REQ-TRIAL-01 | Zero narration-churn findings | §7.1 |
| REQ-TRIAL-02 | Blocking findings converge | §7.2 |
| REQ-TRIAL-03 | ≤2 rounds per stage is a signal, not a stop | §7.3 |
| REQ-TRIAL-04 | Session Log records four figures per stage-version | §7.4 |
| REQ-TRIAL-05 | forge-2-tech overage filed as a Phase 2 finding | §7.5 |
| REQ-TRIAL-06 | Derived figures recomputed in the same edit | §5.1, §7.6 |

## 1. Framework and Tooling

`pytest`, invoked as `python3 -m pytest tests`. **Stdlib and `pytest` only** — `jsonschema`
is absent in CI, and so is every other third-party package, so a bare
`python3 -m pytest tests` must run everything.

Linting is `ruff`. There is no type checker in the gate list; `typeCheckCommand` in
`forge.config.json` is `ruff check scripts/ eval/`.

**No new test convention is introduced.** `@pytest.mark.parametrize` is the idiom
REQ-BRIT-07 converts hand-rolled loops to, and it is already established suite-wide.

> **Accuracy correction.** `tech-spec.md` §3.14 states parametrize "is an established idiom
> in all three files". It is **not** established in `tests/test_state_verbs.py` — that file
> has **zero** `parametrize` uses and **does not import `pytest` at all** (verified). It is
> established in `test_stage_exit.py`, `test_state_schema_conformance.py`, and
> `test_auto_verify.py`. This changes no conversion; it changes the import list
> (`00-core-definitions.md` §10.5, `06-brittleness-batch.md` §10).

## 2. Measured Baseline

Every figure below was **measured in this session**, not inherited from the tech spec:

| Measurement | Command | Result |
|---|---|---|
| Full suite | `python3 -m pytest tests -q` | **1840 passed, 2 skipped** (1842 collected) |
| Prose guard | `pytest tests/test_capability_determination_prose.py --collect-only` | **43** items |
| Call-sites guard | `pytest tests/test_state_verb_call_sites.py --collect-only` | **10** items |
| Exit-protocol guard | `pytest tests/test_stage_exit_protocol.py --collect-only` | **102** items |

The 102 decomposes as **67** mutation-control items + **18** stamp-verbatim items + **17**
everything else, matching `tech-spec.md` §3.4 and §8.2.

REQ-QUAL-01's stated baseline (1840 / 2) is therefore **confirmed**, not assumed.

## 3. Verification Gates

Run for every fix pass, **in this order**:

| # | Gate | Pass condition | Requirement |
|---|---|---|---|
| 1 | `python3 -m pytest tests -q` | green | REQ-QUAL-01 |
| 2 | `python3 scripts/build-adapters.py` then `--check` | `--check` exits 0 | REQ-CANON-01 |
| 3 | `python3 scripts/check-spec-purity.py` | 0 violations | REQ-CANON-02 |
| 4 | `ruff check scripts/ eval/` | clean | — |
| 5 | `ruff check tests/` | **≤19 errors** | REQ-QUAL-02 |
| 6 | `bash scripts/validate.sh` | "All checks passed!" | REQ-QUAL-03 |

`validate.sh` runs the full pytest suite as one step and both canon gates as hard gates, so
**step 6 subsumes 1–5**; the earlier steps exist for fast local feedback.

> **C-02 caveat.** After any `git checkout`, `merge`, or `pull`, adapter file modes can land
> as 0664 from the ambient umask and fail the mode test. Re-run `build-adapters.py` to
> restore 0644; content is unaffected. **Do not investigate this as a content defect.**

### 3.1 The import gate

A gate the ordinary list does not catch, because both files individually collect fine:

```bash
python3 -c "import sys; sys.path.insert(0, 'tests'); \
  from test_stage_exit_protocol import CANONICAL_EXIT_SITES; \
  assert len(CANONICAL_EXIT_SITES) == 9, len(CANONICAL_EXIT_SITES)"
```

`00-core-definitions.md` §10.4 and `01-architecture-layout.md` §5.3 explain why: the prose
guard imports `CANONICAL_EXIT_SITES` from the exit-protocol guard, and the two files are
edited by **different requirements that do not reference each other** (REQ-GUARD-04 and
REQ-TRIM-01). This is the single most likely breakage in the feature.

## 4. Cross-Cutting Test Rules

### 4.1 Meta-guard norm

Every guard this feature writes or rewrites that protects other tests or prose declares an
**enumerated protection set** and **explicit non-goals** (`00-core-definitions.md` §5).
The declared set and the shipped test set must be **identical** — an undeclared test
invites next round's finding; a declared-but-absent protection is a false claim of
coverage.

A verifier **must not** file guard-incompleteness against a declared non-goal.

### 4.2 Diagnostic preservation (REQ-OBS-01)

Every assertion loosened in `06-brittleness-batch.md` must still fail with a message
identifying **which behavior broke and where**.

**The test:** read the failure output alone, and it names the flag or behavior at fault.
`assert "Error" in stderr` is **not acceptable**. This applies to all 11 runtime
comparisons across the 5 exact-stderr sites (`00-core-definitions.md` §9.1).

### 4.3 The ruff budget is non-increase, not zero

REQ-QUAL-02 is **≤19 errors** on `ruff check tests/`. Fewer is a successful outcome and
becomes the new baseline; more is a regression. **Driving it to zero is explicitly out of
scope.**

This is why the two consequent import removals in `00-core-definitions.md` §11 matter: an
unused `pytest` or `Iterator` import left behind is an `F401` spending the budget for
nothing.

### 4.4 Narration states intent only (REQ-CANON-03)

**A hard rule for every fix pass.** Comments, docstrings, and test narration carry **no
counts, no "measured", no "confirmed", no empirical claims**. Acceptance evidence belongs
in the verification report's Fix Progress section and in commit messages.

This is the habit that generated rounds 5–9 of the prior epic. The counts in this document
are **spec content** and must not be copied into code comments.

Two pre-existing narration defects are corrected as part of files already being
restructured (`03-machinery-trim.md` §5.5): `test_state_verb_call_sites.py`'s module
docstring reads "Both hold today (21 call sites, 0 misses)" while `MIN_CALL_SITES = 34` in
the same file, and `test_the_skip_guard_is_not_vacuous`'s docstring names a mechanism the
trim removes.

## 5. Net Test-Count Effect

> ### ⚠ THIS TABLE IS DERIVED, NOT AUTHORITATIVE
>
> Every figure is computed from the rosters in `00-core-definitions.md` §9 and the shapes in
> `02`–`06`. **Whenever one of those changes, recompute this table in the same edit**
> (REQ-TRIAL-06).
>
> This is the single most defect-prone location in the feature's documentation. In
> `forge-2-tech`, **six of seventeen findings across three rounds** landed in the
> equivalent table (`tech-spec.md` §8.2) while the rosters those figures derive from were
> correct **every time**. **Edit this table last, never first.**

### 5.1 Measured inputs

| Input | Value | How obtained |
|---|---|---|
| Suite collected today | 1842 | measured (§2) |
| `_ACCEPTED_HASHES` | 3 entries | measured |
| `_REJECTED_HASHES` | 10 entries | measured |
| `_VERB_INVOCATIONS` | **8** entries | measured — matches `tech-spec.md` §8.2 |
| epic corrupt-state loop | 5 shapes | measured |
| gate-selection unparametrized | 5 functions | `00` §9.4 |

### 5.2 Per-file effect

| File / family | Before | After | Delta |
|---|---|---|---|
| `test_capability_determination_prose.py` | 43 items | **4** | **−39** |
| `test_stage_exit_protocol.py` — mutation controls | 67 items | **7** | **−60** |
| `test_stage_exit_protocol.py` — stamp-verbatim | 18 items | **18** | 0 (REQ-TRIM-02) |
| `test_stage_exit_protocol.py` — everything else | 17 items | **17** | 0 |
| `test_state_verb_call_sites.py` | 10 items | **9** | **−1** (−2 deleted, +1 mutation control) |
| REQ-COV backfill | — | **15** collected (10 named functions) | **+15** |
| REQ-BRIT-07 dedup | 13 items | **55** | **+42** |
| `test_validate_traceability.py` (post-verify, §5.5) | — | **5** collected (5 named functions) | **+5** |

### 5.3 The dedup row, computed

Parametrizing **expands** collected items while **reducing** function count. Both views:

| Family | Functions before → after | Collected before → after |
|---|---|---|
| 40-hex hash | 5 → **5** (never merged) | 5 → **36** (2×3 + 3×10) |
| corrupt-file | 3 → **3** (see below) | 3 → **14** (1 + 5 + 8) |
| gate selection | 5 → **1** | 5 → **5** |
| **total** | **13 → 9** | **13 → 55** |

> **Divergence from `tech-spec.md` §3.14, adopted deliberately.** The tech spec's action
> table says corrupt-file is "3 hand-rolled → 1 parametrized". **That is not achievable
> without deleting coverage**, and it is corrected here. The three sites differ in *call
> mechanism*, not input:
> - `test_load_state_for_write_refuses_a_corrupt_state_file_byte_intact` — an **in-process**
>   call to `FS._load_state_for_write` asserting `FS.UsageError`, with **one input and no
>   loop**. There is nothing to parametrize.
> - `test_a_corrupt_or_malformed_epic_state_is_refused_byte_intact` — loops **5**
>   malformation shapes over `.epic-state.json` via `_epic_verify`.
> - `test_every_verb_refuses_a_corrupt_state_file_byte_intact` — loops **8** registered verbs
>   over the feature state via `_run`.
>
> Merging them needs a mechanism-selecting parameter and a branching body — strictly worse
> than three focused tests. **Adopted: parametrize the two loops in place, leave the
> single-case site unchanged → 3 functions.** The 4-site *roster* in `00` §9.3 is unchanged
> and correct; only the tech spec's action cell is superseded.

**Six already-parametrized sites** (4 hash, 1 corrupt, 1 gate) are untouched and appear in
**neither** column.

### 5.4 Expected suite total

```
1842  collected today (measured)
 −39  prose guard          (43 → 4)
 −60  mutation controls    (67 → 7)
  −1  call-sites guard     (10 → 9)
 +15  REQ-COV backfill     (10 named functions, 15 collected)
 +42  REQ-BRIT-07 dedup    (13 → 55 collected)
────
1799  expected at loop completion
  +5  allowlist guard      (§5.5, added after impl verify)
────
1804  expected now
```

**An implementer landing near this figure is seeing the expected parametrization expansion,
not an accidental addition.** This is the number REQ-QUAL-01's full-suite check is read
against. The loop closed at **1799**, exactly as predicted; the later `+5` is the
post-verify addition recorded in §5.5 and is the only movement since.

Two stated assumptions, each with its recompute rule:

1. **The backfill contributes 15 collected items across 10 named functions.**
   `05-coverage-backfill.md` covers the seven gaps with ten named tests (REQ-COV-01 → 2,
   REQ-COV-06 → 3, the rest → 1 each). Two of those ten are parametrized as specified, so
   the collected contribution is **not** one per function and the assumption is discharged
   here rather than left conditional: `05` §3.2 collects **2** (`zero`, `negative`), `05`
   §7.2's first test collects **5** (the `_UNSAFE_ARTIFACT_PATHS` roster), and the other
   eight functions collect **1** each — 2 + 5 + 8 = **15**. **If a backfill test gains or
   loses ids, recompute §5.2 and §5.4 together.**
2. **`_VERB_INVOCATIONS` has 8 entries.** `tech-spec.md` §8.2's "± up to +7 more if the
   corrupt-file dedup is parametrized over all 8 verb invocations" is correct for the verb
   loop alone; the epic loop contributes 4 more, so the corrupt-file expansion is **+11**.
   That expansion, together with the backfill's parametrized ids in assumption 1, is why
   §5.4 lands at 1799 rather than the tech spec's ≈1781.

### 5.5 Post-verify addition — `test_validate_traceability.py`

Added by the `forge-fix` pass applying finding V-007 of
`.verification/VERIFY-impl-2026-08-04.md`, after `forge-5-loop` closed. Recorded here
because it is the only change to the suite total since, and because §5.4's arithmetic is
read as a live figure rather than a historical one.

`scripts/validate-traceability.py` gained an `--allow-orphan` flag and
`.traceability-allowlist` discovery (`01-architecture-layout.md` §3.4) with no test
coverage at all. That code *subtracts ids from the orphan set* inside a blocking gate that
ships to every adapter bundle, so a defect there turns a red gate green. The guard pins
five behaviors: a declared id is reclassified rather than dropped; an undeclared orphan
still exits 1; a stale entry is reported but does not move the exit code; `--allow-orphan`
merges with the file; and comments and blank lines are stripped.

It drives the real CLI out-of-process, so the exit codes it asserts are the ones
`validate.sh` step 8 actually branches on. Non-vacuity was established by mutation:
short-circuiting `read_allowlist_file` to return an empty set fails four of the five, and
the survivor is the one that deliberately exercises no allowlist.

## 6. Countable Success Criteria (REQ-QUAL-04)

**No runtime threshold is specified**, because a machine-dependent number cannot be
reproduced by a verifier and would reintroduce unfalsifiable-claim churn. Every target is
countable:

- [ ] `test_capability_determination_prose.py` collects **≤5** items (target: 4), declares
      its protection set and non-goals, and has **no** AST self-inspection layer.
- [ ] All **9** capability surfaces — including `forge-0-epic` — carry a paragraph or a
      pointer, resolved **in canon** rather than a test constant.
- [ ] `SURFACES_WITHOUT_PROSE` does not exist, and **no** exemption constant replaces it
      anywhere in the feature.
- [ ] Mutation controls in `test_stage_exit_protocol.py` collect **7** items, with **all 18**
      stamp-verbatim items intact.
- [ ] `test_state_verb_call_sites.py` satisfies the structural block scan; `LOOKBEHIND`,
      `LOOKAHEAD`, `CALL_SPAN`, their tuning test, and the `inspect.getsource` meta-test are
      gone; the canon-mandate test survives; a mutation control replaces the deleted width
      bound.
- [ ] Each of the **seven** coverage gaps has at least one **named** test, in the host file
      `01-architecture-layout.md` §4.2 assigns it.
- [ ] `state-complete --version 0` is refused at the **write** path;
      `state-artifact --path` enforces containment naming `--path`.
- [ ] The **seven** brittleness items are addressed against the v2-corrected rosters
      (`00` §9: exact-stderr 5 sites / 11 comparisons; hash 9 sites; corrupt-file 4;
      gate-selection 6).
- [ ] All six gates in §3 pass, plus the import gate in §3.1.

## 7. Trial Instrumentation

This feature is the **live trial of Phase 2's anti-churn rules** (PRD §3.6). That dual
purpose is a requirement, not a footnote.

### 7.1 REQ-TRIAL-01 — narration churn must not recur

A **narration-churn finding** is a stage-blocking (`error`/`gap`) finding whose substance
lies in a comment, docstring, or test narration rather than in behavior or
decision-bearing specification content. **The count across the whole feature MUST be
zero.**

> **Falsifiability, stated plainly.** This count is only meaningful at stages that **author
> code**. A zero at `forge-1-prd`, `forge-2-tech`, or `forge-3-specs` is *consistent with*
> the rule but is **not evidence for it** — those stages author specification prose, not
> narration. **The decisive datapoint is `forge-5-loop`**, where the original epic's churn
> occurred (11 of 12 blocking findings). Do not read this stage's zero as proof the rules
> work.

### 7.2 REQ-TRIAL-02 — blocking findings must converge

Work **STOPS** if **either**:

- **(a)** a narration-churn finding occurs, **or**
- **(b)** **within one stage at one stage version**, a round records **≥1** outstanding
  stage-blocking findings and that count is **≥** that same stage-version's **immediately
  preceding round's**.

Three counting rules, each load-bearing:

1. **The `≥1` qualifier.** A round recording **zero** outstanding blocking findings resolves
   the stage version and can never trip (b). Without it, a clean round following a clean
   round (0 ≥ 0) would trip the stop — the opposite of the intent.
2. **Scope is one stage at one stage version.** Counts are **never** compared across stage
   boundaries and **never** across a version bump. A stage's first round at a given version
   has no predecessor and can never trip (b).
3. **"Outstanding", not "newly filed".** The count is what the round's report records as
   outstanding — newly filed findings **plus** any prior finding it confirms unresolved.

Retro-classification, preserved as the calibration: this feature's `forge-2-tech` v1 cycle
ran **5 → 1 → 0** and **passes** (round 3 resolves); the original `stage-exit-coverage`
impl stage ran **4 → 2 → 3** and still **fails** at round 3 — the behavior the amendment
must preserve.

### 7.3 REQ-TRIAL-03 — rounds are a signal, not a stop

Verify rounds per stage **SHOULD** be ≤2. Exceeding it is a **signal to inspect**, not an
automatic stop: record the overage and its reason, then evaluate against §7.1 and §7.2.

### 7.4 REQ-TRIAL-04 — what the Session Log records

Per stage **and per stage version**, four figures:

| Figure | Why |
|---|---|
| verify-round count | the weakest signal; **alone it is not the result** |
| **narration-churn count** | the trial's actual result |
| **blocking-finding convergence sequence** | the trial's actual result |
| advisory (non-blocking) findings whose substance lay in narration | distinguishes "**the severity floor held**" from "**no narration churn occurred**" |

The advisory series is not optional bookkeeping. C-03 caps narration inaccuracies at
`inconsistency`, so a floor-compliant verifier **cannot** produce a nonzero REQ-TRIAL-01
count by construction. Without the advisory series the trial cannot tell the two apart. The
reports already carry per-severity totals, so this costs nothing to collect.

Recorded to date:

| Stage | Version | Rounds | Narration churn | Convergence |
|---|---|---|---|---|
| `forge-1-prd` | v2 | — | — | — |
| `forge-2-tech` | v1 | 3 | **0** / 17 | 5 → 1 → 0 |
| `forge-2-tech` | v2 | 2 | **0** / 22 | 2 → 0 |
| `forge-3-specs` | v1 | *pending* | *pending* | *pending* |

### 7.5 REQ-TRIAL-05 — the overage is filed, not erased

The `forge-2-tech` 3-round overage against the original ≤2 rule is recorded as a Phase 2
finding **in its own right**, **without** reopening R-05..R-08 on the narration-churn axis
— that axis measured clean. The finding to file is §7.6.

### 7.6 REQ-TRIAL-06 — the failure mode the trial actually found

The recurring defect across both fix rounds was **a derived summary figure left stale by a
correction made elsewhere in the same artifact** — *not* narration drift. Six of seventeen
findings landed in one derived table while the rosters those figures derive from were
correct every time.

**Any artifact in this feature carrying figures derived from another section MUST declare
that derivation and be recomputed in the same edit as its source.** In this suite that
means:

| Derived location | Derives from | Rule |
|---|---|---|
| §5 of this document | `00` §9 rosters; shapes in `02`–`06` | recompute in the same edit |
| `00` §9 rosters | the real test files | re-measure, never re-estimate |
| PRD §8 Success Criteria | PRD §3.4, §3.6 | recompute in the same edit |
| `tech-spec.md` §8.2 | tech-spec §3.3/§3.4/§3.5/§3.14 | recompute in the same edit |

R-05..R-08 suppress narration churn but say **nothing** about derived-figure propagation
*within* a single artifact. This is the new input for Phase 2's reopening.

## 8. What This Feature Does Not Test

Declared non-goals, so a verifier resolves them against a recorded position under C-04
rather than filing them:

- **Concurrency and locking** (REQ-CONC-01). Single-writer is the model; the atomic write
  protects against a torn write, not simultaneous writers. **No locking protocol may be
  introduced.**
- **Exact-markdown fidelity** of any capability surface (REQ-GUARD-06) — the mechanism that
  produced the churn. Reintroducing it is a **regression, not a hardening**.
- **Wall-clock runtime.** Targets are countable, never timed (REQ-QUAL-04).
- **Probe-1 criterion pinning** in the compliance eval (`04` §5). REQ-COV-03 names the
  prelude criterion only.
- **`ruff check tests/` reaching zero.** The requirement is non-increase.
- **Detection-strength parity** for the structural scan. It is **weaker**, and recorded as a
  declared boundary (`00` §6.4), not asserted as parity. The residual is deliberately not
  enumerated (`03` §9).
- **`stage_exit`'s reconcile-command interpolation** — REQ-COV-07 asserts the degradation
  only and does **not** pin the interpolation as golden (`04` §5).

## 9. Dependencies

All of `00-core-definitions.md`, `01-architecture-layout.md`, and `02`–`06`. This document
consumes their shapes and rosters; it defines none of its own.

Gate execution requires `pytest`, `ruff`, `python3`, and `bash`. No new dependency.

## 10. Verification

- [ ] All six gates in §3 pass, in order, on a clean tree.
- [ ] The import gate in §3.1 passes after **both** `02` and `03` have landed.
- [ ] Suite collection lands near **1799** (§5.4); a large divergence means a roster changed
      without §5 being recomputed.
- [ ] `ruff check tests/` reports **≤19** errors, and no `F401` from a removed-usage import.
- [ ] Every countable criterion in §6 is satisfied.
- [ ] No comment, docstring, or test narration in the diff carries a count, "measured",
      "confirmed", or any empirical claim (§4.4).
- [ ] The two pre-existing narration defects named in §4.4 are corrected.
- [ ] No locking primitive, lockfile, or advisory-lock call appears anywhere in the diff.
- [ ] The Session Log records all four REQ-TRIAL-04 figures for every stage **and stage
      version**, including this one.
- [ ] Every derived figure in §5 was recomputed in the same edit as any roster it depends on
      (§7.6).
