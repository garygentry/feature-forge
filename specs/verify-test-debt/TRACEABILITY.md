# verify-test-debt — Traceability Matrix

> PRD v2 → tech spec v2 → implementation specification suite. Every one of the **46** PRD
> requirements is mapped to the document and section that implements it, and to the section
> that verifies it. Shared contracts and file ownership live in `00-core-definitions.md` and
> `01-architecture-layout.md`.
>
> **Coverage: 46 / 46. No requirement is unimplemented.** Verified programmatically against
> the PRD's own requirement ids, not by hand.

## Requirement → Implementation → Verification

### Prose-guard collapse (R-10, PRD §3.1)

| Requirement | Implementation specification | Verification |
|---|---|---|
| REQ-GUARD-01 | `02-canon-and-prose-guard.md` §2 — canonical section confirm-and-complete; `00-core-definitions.md` §3.1–§3.2 clause set and current-state table | `02` §4.5; `07-testing-strategy.md` §6 |
| REQ-GUARD-02 | `02-canon-and-prose-guard.md` §4.6, §5 — paragraph-or-pointer; `00-core-definitions.md` §3.3, §4.1 roster | `02` §4.6; `07` §6 |
| REQ-GUARD-03 | `02-canon-and-prose-guard.md` §3, §6.3 — `forge-0-epic` pointer in canon; `00-core-definitions.md` §4.2 constant deletion | `02` §9; `01-architecture-layout.md` §9; `07` §6 |
| REQ-GUARD-04 | `02-canon-and-prose-guard.md` §4.1, §4.9, §6 — 4 tests / 4 items under the cap of 5 | `02` §9; `07` §5.2, §6 |
| REQ-GUARD-05 | `02-canon-and-prose-guard.md` §4.2, §4.8; `00-core-definitions.md` §5.1 declaration format | `02` §9; `07` §4.1 |
| REQ-GUARD-06 | `02-canon-and-prose-guard.md` §5.3, §6.2, §9; `00-core-definitions.md` §5.2 load-bearing non-goal | `07` §4.1, §8 |
| REQ-GUARD-07 | `02-canon-and-prose-guard.md` §6.2 — AST layer and its three helpers deleted | `02` §9; `00` §11; `07` §6 |

### Mutation-control and machinery trim (R-11, PRD §3.2)

| Requirement | Implementation specification | Verification |
|---|---|---|
| REQ-TRIM-01 | `03-machinery-trim.md` §2 — 7 classes, one item each, fixed representative | `03` §13; `07` §5.2, §6 |
| REQ-TRIM-02 | `03-machinery-trim.md` §3 — stamp-verbatim preserve list, a hard floor | `03` §13; `07` §5.2, §6 |
| REQ-TRIM-03 | `03-machinery-trim.md` §4; `00-core-definitions.md` §6 region model | `03` §13; `07` §6 |
| REQ-TRIM-04 | `03-machinery-trim.md` §5.1, §5.2, §6 — window constants and tuning test deleted, mutation control added | `03` §13; `07` §6 |
| REQ-TRIM-05 | `03-machinery-trim.md` §5.2, §5.3 — `inspect.getsource` meta-test deleted | `03` §13; `00` §11 |
| REQ-TRIM-06 | `03-machinery-trim.md` §7 — canon-mandate test preserved verbatim | `03` §13; `07` §6 |
| REQ-TRIM-07 | `03-machinery-trim.md` §8 — duplicate source-text assertions removed; `choices=EXIT_STAGES` retained | `03` §13 |

### Coverage backfill and production validations (R-12, PRD §3.3)

| Requirement | Implementation specification | Verification |
|---|---|---|
| REQ-COV-01 | `05-coverage-backfill.md` §2 — `tests/test_auto_verify.py`, both autoVerify arms | `05` §11; `07` §6 |
| REQ-COV-02 | `05-coverage-backfill.md` §3 — `tests/test_state_verbs.py` | `05` §11; `07` §6 |
| REQ-COV-03 | `04-production-validations.md` §5 (`PRELUDE_CRITERIA`) + `05-coverage-backfill.md` §4 (the two-sided assertion) | `04` §9; `05` §11 |
| REQ-COV-04 | `05-coverage-backfill.md` §5 — byte-level, seeded-marker arm | `05` §11; `07` §6 |
| REQ-COV-05 | `05-coverage-backfill.md` §6 — write/validate distinction preserved | `05` §11; `04` §2.5 |
| REQ-COV-06 | `05-coverage-backfill.md` §7 — five rejection branches, `--path` named | `05` §11; `04` §9 |
| REQ-COV-07 | `05-coverage-backfill.md` §8 — standalone-route degradation only | `05` §11; `04` §4.3 |
| REQ-FIX-01 | `04-production-validations.md` §2 — `_require_positive_int` before the load; `00-core-definitions.md` §7.1, §7.3 | `04` §9; `05` §3; `07` §6 |
| REQ-FIX-02 | `04-production-validations.md` §4 — candidate investigated and disproved; `05-coverage-backfill.md` §9 disposition | `04` §9; `05` §11 |
| REQ-SEC-01 | `04-production-validations.md` §3 — `label` parameter and per-path validation; `00-core-definitions.md` §7.2, §7.3 | `04` §9; `05` §7; `07` §6 |

### Brittleness batch (R-13, PRD §3.4)

| Requirement | Implementation specification | Verification |
|---|---|---|
| REQ-BRIT-01 | `06-brittleness-batch.md` §2 — root-uid skipif, plus the missing `os` import | `06` §11; `07` §6 |
| REQ-BRIT-02 | `06-brittleness-batch.md` §3.1, §3.2 — import-scoped and clause-scoped scanners | `06` §11 |
| REQ-BRIT-03 | `06-brittleness-batch.md` §4 — ban narrowed to `_render_status` | `06` §11 |
| REQ-BRIT-04 | `06-brittleness-batch.md` §5.2–§5.6; roster in `00-core-definitions.md` §9.1 | `06` §11; `07` §4.2, §6 |
| REQ-BRIT-05 | `06-brittleness-batch.md` §6 — widened exit-1 guard; `00-core-definitions.md` §8.1 | `06` §11; `07` §6 |
| REQ-BRIT-06 | `06-brittleness-batch.md` §7 — key-set assertion | `06` §11 |
| REQ-BRIT-07 | `06-brittleness-batch.md` §8.2–§8.4; rosters in `00-core-definitions.md` §9.2–§9.5 | `06` §11; `07` §5.3, §6 |

### Canon and adapter obligations (PRD §3.5)

| Requirement | Implementation specification | Verification |
|---|---|---|
| REQ-CANON-01 | `01-architecture-layout.md` §6.1 — six mirrors, same commit; `02` §8 | `01` §9; `07` §3 |
| REQ-CANON-02 | `01-architecture-layout.md` §6.2 — purity ratchet; `02` §2.3, §3.3, §7.1 | `01` §9; `07` §3 |
| REQ-CANON-03 | `00-core-definitions.md` §10.1; `06-brittleness-batch.md` §1.4, §10; `03-machinery-trim.md` §5.5 | `07` §4.4, §10 |

### Trial instrumentation (PRD §3.6, §3.6.1)

| Requirement | Implementation specification | Verification |
|---|---|---|
| REQ-TRIAL-01 | `07-testing-strategy.md` §7.1 — narration-churn definition and falsifiability caveat | `07` §7.4, §10 |
| REQ-TRIAL-02 | `07-testing-strategy.md` §7.2 — convergence stop with all three counting rules | `07` §7.4, §10 |
| REQ-TRIAL-03 | `07-testing-strategy.md` §7.3 — ≤2 rounds as a signal, not a stop | `07` §7.4 |
| REQ-TRIAL-04 | `07-testing-strategy.md` §7.4 — four figures per stage **and stage version** | `07` §10 |
| REQ-TRIAL-05 | `07-testing-strategy.md` §7.5 — overage filed without reopening the narration axis | `07` §7.6 |
| REQ-TRIAL-06 | `07-testing-strategy.md` §5.1, §7.6 — derived-figure declaration and recompute rule | `07` §5, §10 |

### Non-functional (PRD §4)

| Requirement | Implementation specification | Verification |
|---|---|---|
| REQ-QUAL-01 | `07-testing-strategy.md` §2 (baseline **measured**: 1840 passed / 2 skipped), §3 gate 1 | `07` §10 |
| REQ-QUAL-02 | `07-testing-strategy.md` §3 gate 5, §4.3; `00-core-definitions.md` §11 (unused-import removals) | `07` §10 |
| REQ-QUAL-03 | `07-testing-strategy.md` §3 gate 6 | `07` §10 |
| REQ-QUAL-04 | `07-testing-strategy.md` §6 — countable criteria, no runtime threshold | `07` §6 |
| REQ-OBS-01 | `00-core-definitions.md` §8.3; `06-brittleness-batch.md` §1.3 and a per-site check | `07` §4.2 |
| REQ-SEC-01 | *(stated in §3.3 above)* | — |
| REQ-CONC-01 | `00-core-definitions.md` §10.2 — single-writer, no locking may be introduced | `07` §8, §10 |

## Technical-Decision Coverage

| Tech-spec decision | Implemented by |
|---|---|
| §3.1 Canonical section is `stage-exit-protocol.md` § "Host and capability determination" | `00` §3.1; `02` §2 |
| §3.2 `SURFACES_WITHOUT_PROSE` deleted outright, not shrunk | `00` §4.2; `02` §6.3 |
| §3.3 Guard file becomes 4 tests with `PROTECTS`/`NON-GOALS` | `00` §5.1; `02` §4 |
| §3.4 Seven mutation classes, one fixed representative each | `03` §2 |
| §3.5 Structural block scan replaces the proximity window | `00` §6; `03` §4 |
| §3.6 Source-text assertions removed only where a runtime check duplicates them | `03` §8 |
| §3.7 `--version` validated unconditionally before the load | `00` §7.1, §7.3; `04` §2 |
| §3.8 `--path` reuses `_validated_findings_file` via a defaulted `label` | `00` §7.2; `04` §3 |
| §3.9 Corrupt-state read/write asymmetry tested as golden | `05` §2 |
| §3.10 Debt-write idempotency asserted at byte level | `05` §5 |
| §3.11 Commit-2 flag precedence by branch, not rejection | `05` §6 |
| §3.12 REQ-FIX-02 candidate disproved; residual recorded | `04` §4 |
| §3.13 `PRELUDE_CRITERIA` mirrors `BRANCH_CRITERIA`; probe 1 out of scope | `04` §5; `05` §4 |
| §3.14 Brittleness rosters (exact-stderr 5, hash 9, corrupt 4, gate 6) | `00` §9; `06` §5, §8 |
| §3.15 Adapter regeneration and spec purity | `01` §6 |
| §8.1 Backfill placement beside sibling coverage | `01` §4.2; `05` §1 |
| §8.2 Net test-count accounting (derived) | `07` §5 |
| §8.3 Ordered verification gates | `01` §7; `07` §3 |
| §8.4 Declared non-goals | `00` §10.3; `07` §8 |

## Corrections Recorded During This Stage

Findings that supersede a statement in the PRD or tech spec. Each was **verified against
source**, not inferred. They are recorded here so a later round resolves them against a
position rather than re-deriving them (C-04).

| # | Superseded statement | Verified position | Recorded in |
|---|---|---|---|
| 1 | `00-core-definitions.md` draft: the canonical section "already states every clause" | Only clauses **a** and **b** are there. **c1a, c1b, c2, c3 live only in `shared-conventions.md` § "Verify Capability"** — the designated *summary*. That inversion is the defect REQ-GUARD-01 closes, making the "complete" half real, non-optional work. | `00` §3.1; `02` §2.2–§2.3 |
| 2 | PRD §1: "Seven behaviors on production paths have **no test at all**" | Inaccurate for REQ-COV-04 — `test_repeated_stage_exit_at_the_same_revision_is_byte_idempotent` already exists in `tests/test_auto_verify.py` and does byte-level idempotency incl. an explicit `updatedAt` check. The uncovered arm is a **seeded** `auto-verify-pending` marker. | `05` §5.2–§5.3 |
| 3 | tech-spec §3.14: corrupt-file "3 hand-rolled → **1** parametrized" | Not achievable without deleting coverage — the three sites differ in **call mechanism** (one in-process with no loop; two loops over different subprocess wrappers). Adopted: **3 functions**. | `06` §8.3; `07` §5.3 |
| 4 | tech-spec §3.14: parametrize "is an established idiom in all three files" | `tests/test_state_verbs.py` has **zero** parametrize uses and **no `pytest` import**. Measured. (`_VERB_INVOCATIONS` has 8 entries, as `tech-spec.md` §8.2 states — re-measured, no correction needed.) | `00` §10.5; `07` §1, §5.1 |
| 5 | PRD §3.3 REQ-FIX-01 note: the validator is `_positive_int` | **No such symbol.** The real name is `_require_positive_int`. | `00` §7.1; `04` §2.2 |
| 6 | tech-spec §3.1 / `01` §4.1: the pointer position is "the same structural position every sibling uses" | True of the six **restating** surfaces; the two **pointer** surfaces place theirs *after* the fenced call. Harmless — position is never asserted (REQ-GUARD-06). | `02` §3.3 |
| 7 | Roster unit unstated in both PRD and tech spec | 9 sites carry **10** contract paths (`forge-5-loop` owns two). A site passes when **any one** path carries the evidence; a per-file rule would falsely fail it. | `00` §4.1; `02` §4.4 |
| 8 | C-05 read as constraining the `references/` edit | `check_body_size` scans `skills/*/SKILL.md` only — `references/**` has **no** size cap. C-05 constrains the skill surfaces. | `00` §3.1; `02` §2.3 |
| 9 | PRD §3.4 REQ-BRIT-03: "token ban**s**" (plural) in `test_stage_exit.py` | Exactly **one** unsliced ban exists, as tech-spec §3.14 states in the singular. | `06` §4 |
| 10 | tech-spec §3.5: Guard 3 bound to "the **same** structural region" | Binding Guard 3 to the whole region would let prose satisfy a guard whose subject is a shipped fence. Bound instead to the region's **inner** bound (the call's own fence block) — same computation, no tuned integer. | `03` §5.4 |
| 11 | tech-spec §3.5 / §8: the self-mutation detection figures **20/34**, 12/34, 24/34 | **Withdrawn, not re-derived.** "Remove each site's own mandate" has no single mechanical meaning where a region carries more than one mandate, so the figures state no reproducible procedure. The suite keeps only the reproducible column (green on canon: 34/34, 34/34, 33/34) and states the per-site ordering qualitatively. The **decision** the figures supported — accept weaker discrimination to remove every tuned integer — is unchanged and stays a declared boundary. | `00` §6.2, §6.4; `03` §9; `07` §8 |
| 12 | tech-spec §3.5 / `00` §6.3 draft: a naive heading scan produces "**2 false failures**" in § Git Commit Protocol | Does not reproduce under the **adopted fence-block bound**: the two bash comments sit inside the call-bearing block, so they satisfy neither `index < first` nor `index > last` and cannot move a bound. Both `state-complete` calls keep identical bounds under either heading mode and canon is 34/34 green either way. The failure mode is real only under the **rejected call-line** variant. The fence-aware index is retained on the structural ground that the bound degrades to the call's own line for any unfenced call site. | `00` §6.3; `03` §4.2, §4.8, §13 |

## Coverage Verification

```
PRD requirements ....................... 46
Covered by the spec suite .............. 46
Uncovered .............................. 0
Broken document cross-references ....... 0
Requirement ids invented by the suite .. 0
```

Foreign requirement ids appearing in the suite (`REQ-REL-01`, `REQ-STATE-01`,
`REQ-DEBT-04`) are **quotations of existing test docstrings** from the antecedent
`stage-exit-coverage` feature, not new ids.
