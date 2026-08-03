# verify-test-debt — Product Requirements Document

## 1. Problem Statement

The `stage-exit-coverage` epic took **9 implementation verify/fix rounds** to close.
A five-agent review established that the churn was not caused by product defects: of
12 stage-blocking `error` findings across those 9 rounds, **11 lived in comments or
test narration** and exactly 1 was user-reachable behavior. From round 2 onward,
every blocking finding was introduced by the previous round's fix.

The protocol gaps that let this happen were closed in Phase 2 of the remediation
plan. What remains is the **test debt those rounds left behind** — guards that are
expensive to satisfy and cheap to falsify, plus real coverage holes they crowded out:

- One test file, `tests/test_capability_determination_prose.py` (43 tests, 651 lines),
  absorbed **39% of all fix lines** and appears in **all 9 fix commits**, while
  catching **zero product defects**. It asserts a 6-clause × 6-surface grid of exact
  markdown (including bold markers) and adds an AST layer that inspects its own
  source.
- `tests/test_stage_exit_protocol.py` carries 67 mutation controls where roughly one
  per mutation class would do the same job.
- `tests/test_state_verb_call_sites.py` implements proximity-window matching
  (LOOKBEHIND / LOOKAHEAD / CALL_SPAN) plus a test that asserts *another test's
  failure-message wording* via `inspect.getsource`.
- Seven behaviors on production paths have **no test at all**, including a confirmed
  defect: `state-complete --version 0` writes `"version": 0`, which the read path
  (`_positive_int`, rejects `< 1`) then refuses at exit 2 — poisoning a later verify
  read.

The cost is paid on every future change to this repo: brittle guards convert ordinary
edits into multi-round verify churn, and the untested paths mean genuine regressions
ship unnoticed.

This feature is also the **live trial of Phase 2's anti-churn rules** — it runs
through the forge pipeline specifically to test whether those rules hold under real
work. That dual purpose is a requirement, not a footnote (see §3.6).

**Who has this problem:** maintainers of this repo, and every agent session that runs
the suite or a forge verify round against it.

**Why now:** Phases 1 and 2 are merged to `main`. The protocol is fixed but unproven,
and the debt it created is still in the tree. Both facts are addressed by the same
piece of work.

## 2. User Stories

- As a **repo maintainer**, I want the capability-determination rule stated once in
  canon rather than restated six times in exact markdown, so that editing the rule is
  a one-file change instead of a seven-file grid update.
- As a **repo maintainer**, I want a test failure to tell me a real behavior broke,
  so that I stop spending rounds re-satisfying assertions about prose formatting.
- As an **agent running a forge verify round**, I want guards that declare what they
  do *not* protect, so that I do not file guard-incompleteness findings against
  deliberate non-goals.
- As an **agent running the loop**, I want the seven untested production behaviors
  covered, so that a change to `stage-exit`'s scheduling boundary or the `state-*`
  verbs fails loudly instead of silently.
- As a **maintainer evaluating the remediation**, I want this feature's **narration-churn
  count and blocking-finding convergence sequence** recorded alongside its verify-round
  count, so that I can tell whether Phase 2's rules actually work before committing to
  Phase 4 and a release.
- As a **future contributor**, I want `state-artifact --path` to reject paths that
  escape the feature directory, so that state cannot record a location no forge stage
  could legitimately have written.

## 3. Functional Requirements

### 3.1 Prose-guard collapse (R-10) — **P0**

- **REQ-GUARD-01:** The capability-determination rule MUST exist as a single canonical
  section — `references/stage-exit-protocol.md` § "Host and capability determination"
  (OQ-02) — stating every required clause. That section is the source of truth;
  `references/shared-conventions.md` § "Verify Capability" remains a summary that defers to
  it and MUST NOT be promoted to a second source of truth.
  - Priority: P0
  - Notes: **Corrected in v2.** v1 named `shared-conventions.md` as canonical, which was the
    tentative position while OQ-02 was open. v2 resolved OQ-02 the other way: the
    `stage-exit-protocol.md` section already states every clause plus the Standard Verify
    Gate and the recovery path, both existing pointer surfaces name it by title, and
    `shared-conventions.md` § "Verify Capability" self-identifies as a summary deferring to
    it. See `tech-spec.md` §3.1, including the rejected alternative.
- **REQ-GUARD-02:** Each capability-determination surface MUST either restate the
  paragraph or carry a pointer to the canonical section. No surface may silently
  carry neither.
  - Priority: P0
- **REQ-GUARD-03:** `forge-0-epic`'s missing capability-determination guidance MUST be
  closed **in canon** (as a paragraph or pointer on that surface), not by adding it to
  a test-side exclusion constant. This also closes review finding D7.
  - Priority: P0
  - Notes: The current `SURFACES_WITHOUT_PROSE` test constant encodes the gap as
    permanent; the gap is the defect, and the constant is the symptom.
- **REQ-GUARD-04:** `tests/test_capability_determination_prose.py` MUST contain **at
  most 5 tests**, covering exactly this protection set:
  1. the canonical section states all required clauses;
  2. every surface in the roster has a paragraph or a pointer;
  3. the roster cannot shrink to a vacuous size (non-vacuity floor).
  - Priority: P0
- **REQ-GUARD-05:** The guard MUST declare its **enumerated protection set and its
  explicit non-goals** in the file, per the meta-guard norm established in R-08.
  - Priority: P0
- **REQ-GUARD-06:** Exact-markdown fidelity — clause-fragment matching, bold-marker
  presence, and per-surface formatting equality — is a **declared non-goal**. The
  guard MUST NOT assert it, and a verifier MUST NOT file its absence as a finding.
  - Priority: P0
  - Notes: This is the specific mechanism that produced the churn. Reintroducing it
    rebuilds the problem.
- **REQ-GUARD-07:** The AST self-inspection layer MUST be deleted.
  - Priority: P0

### 3.2 Mutation-control and machinery trim (R-11) — **P1**

- **REQ-TRIM-01:** `tests/test_stage_exit_protocol.py` MUST retain approximately one
  mutation control per mutation class (~7 total, from 67).
  - Priority: P1
- **REQ-TRIM-02:** Every positive stamp-verbatim test in that file MUST be preserved.
  These are legitimate golden-file assertions and are **not** in scope for trimming.
  - Priority: P0
  - Notes: This is a guard on the trim itself — the risk of REQ-TRIM-01 is
    over-deletion.
- **REQ-TRIM-03:** Guard 1 in `tests/test_state_verb_call_sites.py` MUST be replaced by a
  **structural block scan**: each fenced `state-*` call, together with the prose attached to
  it — delimited by markdown headings and neighbouring fence blocks — must carry the
  `--epic` mandate. The proximity-window approach MUST be removed.
  - Priority: P1
  - Notes: **Corrected in v2.** v1 required "each fenced `state-*` call **contains**
    `--epic`", which cannot hold: only **2 of 34** fenced calls literally carry the flag —
    the mandate lives in the prose around each fence, which is precisely why `LOOKBEHIND`
    exists — and the epic-scoped `state-verify` must **never** carry it. The intent
    (eliminate tuned-integer windows) is preserved; the mechanism is corrected. Measured
    rosters and the three region variants are in `tech-spec.md` §3.5.
- **REQ-TRIM-04:** The window-tuning tests bounding LOOKBEHIND, LOOKAHEAD, and
  CALL_SPAN MUST be deleted together with the machinery they constrain.
  - Priority: P1
- **REQ-TRIM-05:** The test asserting another test's failure-message wording via
  `inspect.getsource` MUST be deleted.
  - Priority: P1
- **REQ-TRIM-06:** `test_the_epic_mandate_itself_is_still_documented` MUST be
  preserved — it pins the normative rule in canon rather than a mechanism.
  - Priority: P0
- **REQ-TRIM-07:** Source-text assertions in `tests/test_stage_constants_parity.py`
  that duplicate an existing runtime check MUST be removed.
  - Priority: P1

### 3.3 Coverage backfill (R-12) — **P1**

Each of the seven gaps MUST have at least one named test:

- **REQ-COV-01:** Corrupt `.pipeline-state.json` encountered on a production
  `stage-exit`, covering the tolerant-read vs. strict-debt-write asymmetry, with
  auto-verify both **on** and **off**.
  - Priority: P1
- **REQ-COV-02:** The `--version` domain on `state-complete` (see REQ-FIX-01).
  - Priority: P1
- **REQ-COV-03:** The compliance eval's prelude criterion key set MUST be pinned so a
  future criterion cannot be silently dropped, mirroring `BRANCH_CRITERIA`.
  - Priority: P1
  - Notes: **Corrected in v2.** v1 stated that `resolver_line_identical` "is currently
    computed and never checked". It *is* checked — it is one of four keys ANDed into
    `compliant = all(criteria.values())` in `_to_result`. The real gap is narrower: probe 2
    (prelude) and probe 1 (stage-exit) have no pinned key-set constant, unlike probe 3.
    OQ-03 is resolved by this correction.
- **REQ-COV-04:** Auto-verify debt-write idempotency at the same revision, asserted at
  the byte level.
  - Priority: P1
- **REQ-COV-05:** `state-complete`'s commit-2 path ignoring conflicting flags.
  - Priority: P1
- **REQ-COV-06:** `state-artifact --path` containment (see REQ-SEC-01).
  - Priority: P1
- **REQ-COV-07:** Degradation behavior on an unsafe on-disk `epic` back-pointer.
  - Priority: P1

Three behavior changes are in scope, and only these three:

- **REQ-FIX-01:** `state-complete --version` MUST reject values below 1 at the
  **write** path, matching the read path's existing domain.
  - Priority: P1
  - Notes: Confirmed live — `--version 0` currently exits 0 and writes `"version": 0`.
- **REQ-SEC-01:** `state-artifact --path` MUST reject paths that escape the resolved
  feature directory, consistent with the containment validation already applied to
  findings-file paths.
  - Priority: P1
- **REQ-FIX-02:** If a test written for REQ-COV-01..07 uncovers a defect beyond
  REQ-FIX-01 and REQ-SEC-01, the defect MUST be fixed within this feature rather than
  pinned as golden behavior and deferred.
  - Priority: P1
  - Notes: A test that asserts known-wrong behavior invites a blocking finding on the
    next verify round.

### 3.4 Brittleness batch (R-13) — **P2**

- **REQ-BRIT-01:** The chmod-based test in `tests/test_auto_verify.py` MUST carry a
  root-uid skip guard, matching its sibling tests.
  - Priority: P2
- **REQ-BRIT-02:** Token scanners with known false-positive traps in
  `tests/test_state_verbs.py` MUST be corrected so legitimate text does not trip them.
  - Priority: P2
- **REQ-BRIT-03:** Whole-source token bans in `tests/test_stage_exit.py` MUST be
  narrowed to the region whose property they actually assert.
  - Priority: P2
- **REQ-BRIT-04:** Exact-stderr full-equality assertions MUST become substring or regex
  assertions that pin the diagnostic content without pinning incidental wording.
  - Priority: P2
  - Notes: **Corrected in v2.** v1 estimated "~15 sites … spans more than one file". The
    exhaustive roster is **5 assertion sites / 11 runtime comparisons across exactly 2
    files** (`test_forge_root.py` ×1, `test_state_verbs.py` ×4, two of which loop over 3
    and 5 cases). OQ-01 is resolved by this correction; the enumerated roster lives in
    `tech-spec.md` §3.14.
- **REQ-BRIT-05:** The evadable exit-1 guard regex in `tests/test_state_verbs.py` MUST
  be widened so it cannot be trivially bypassed.
  - Priority: P2
- **REQ-BRIT-06:** The key-**order** pin in `tests/test_state_schema_conformance.py`
  MUST become a key-**set** assertion.
  - Priority: P2
- **REQ-BRIT-07:** Redundant coverage MUST be deduplicated across three families:
  40-hex hash, corrupt-file refusal, and gate selection. Deduplication is **within-file
  only** — hand-rolled loops become parameterized tests in place; already-parameterized
  sites are untouched, and families are never merged across files.
  - Priority: P2
  - Notes: **Corrected in v2.** v1's "40-hex hash matrices (×5)" counted only the
    `_REJECTED_HASHES` sub-family. The complete roster is **9 sites** across both
    sub-families — 5 hand-rolled loops in `test_state_verbs.py` (2 accepted, 3 rejected)
    plus 4 already-parameterized in `test_state_schema_conformance.py`. Corrupt-file
    (×3 hand-rolled, 4 total) and gate-selection (×6) were re-derived and **confirmed
    correct as stated**. v1's "collapse to a single parameterized case" is superseded:
    the five hash loops exercise three different verbs through different fixtures and two
    domains, so merging them would delete the epic-target coverage. Rosters are enumerated
    in `tech-spec.md` §3.14.

### 3.5 Canon and adapter obligations

- **REQ-CANON-01:** Any change to `skills/` or `references/` MUST be accompanied by
  regeneration of the six adapter mirrors in the same commit, with
  `build-adapters.py --check` exiting 0.
  - Priority: P0
- **REQ-CANON-02:** `check-spec-purity.py` MUST report 0 violations after every
  canon change.
  - Priority: P0
- **REQ-CANON-03:** Comments, docstrings, and test narration written during any fix
  pass MUST state intent only — no empirical or quantified claims ("measured",
  "probed and confirmed", counts). Acceptance evidence belongs in the verification
  report's Fix Progress section and in commit messages.
  - Priority: P0
  - Notes: Carried from R-08. This is the habit that generated rounds 5-9.

### 3.6 Trial instrumentation

> **Amended 2026-08-03 after the forge-2-tech trial (PRD v2).** The original REQ-TRIAL-01
> gated on a **round count** (≤2) as a proxy for churn. forge-2-tech consumed 3 rounds, so
> the original rule fired — but the measurement showed the proxy was wrong: **zero of 17
> findings across three rounds** touched a comment, docstring, or test narration, and
> blocking findings converged monotonically **5 → 1 → 0**. The failure mode Phase 2 targets
> did not occur; a different one did (§3.6.1). The requirements below measure the failure
> mode directly instead of a count that merely correlates with it. The original rule's
> firing is preserved as a finding, not erased — see REQ-TRIAL-05.

- **REQ-TRIAL-01:** **Narration churn MUST NOT recur.** A *narration-churn finding* is a
  stage-blocking (`error`/`gap`) finding whose substance lies in a comment, docstring, or
  test narration rather than in behavior or decision-bearing specification content. The
  count of such findings across the whole feature MUST be **zero**.
  - Priority: P0
  - Notes: This is the defect class that produced rounds 5–9 of the `stage-exit-coverage`
    epic (11 of 12 blocking findings). It is what R-05's severity floor and R-08's
    non-goals norm exist to suppress, so it is what the trial must actually measure.
  - **Falsifiability:** this count is only meaningful at stages that **author code** —
    `forge-5-loop`, and any fix pass touching `tests/` or `scripts/`. A zero at
    `forge-1-prd` or `forge-2-tech` is consistent with the rule but is **not evidence for
    it**, because those stages author specification prose rather than narration. The
    trial's decisive datapoint is `forge-5-loop`.
- **REQ-TRIAL-02:** **Blocking findings MUST converge.** Work MUST STOP if **either**
  (a) a narration-churn finding occurs (REQ-TRIAL-01 violated), **or** (b) **within one
  stage at one stage version**, a round records **one or more** outstanding stage-blocking
  findings and that count is **greater than or equal to that same stage-version's
  immediately preceding round's** — non-convergence, the real signature of a fix pass
  manufacturing the next round's work.
  - Priority: P0
  - **Counting rules** (each is load-bearing; all three were defects in the first draft of
    this amendment, found by verification):
    1. **`≥1` qualifier.** A round recording **zero** outstanding blocking findings resolves
       the stage version and can never trip (b). Without it, a clean round following a clean
       round (0 ≥ 0) would trip the stop — the opposite of the intent.
    2. **Scope is one stage at one stage version.** Counts are **never** compared across
       stage boundaries, and **never** across a version bump. A stage's first round at a
       given version has no predecessor and can never trip (b). Without this, the first
       blocking round of every later stage would trip against the previous stage's
       terminal zero, and no stage carrying any blocking finding could ever pass.
    3. **"Outstanding", not "newly filed".** The count is what the round's report records as
       outstanding — newly filed findings **plus** any prior finding it confirms unresolved.
       Under a scoped re-verify (C-04) a report legitimately carries both, and the two
       readings select different numbers on real data.
  - Notes: Replaces the fixed three-round stop. Retro-classification against real reports:
    this feature's `forge-2-tech` v1 cycle ran **5 → 1 → 0** and passes (round 3 resolves);
    the original `stage-exit-coverage` impl stage ran **4 → 2 → 3** and still fails at
    round 3, which is the behavior the amendment must preserve.
  - Notes: A round count cannot distinguish "converging on a genuinely intricate artifact"
    from "churning"; the convergence slope can. A stage version resolves when a round
    records zero outstanding blocking findings.
- **REQ-TRIAL-03:** Verify rounds per stage SHOULD be ≤2. Exceeding it is a **signal to
  inspect**, not an automatic stop: record the overage and its reason, then evaluate
  against REQ-TRIAL-01 and REQ-TRIAL-02.
  - Priority: P1
- **REQ-TRIAL-04:** At feature close, the remediation plan's Session Log MUST record, per
  stage **and per stage version**: the verify-round count, the **narration-churn count**,
  the **blocking-finding convergence sequence**, and the count of **advisory**
  (non-blocking) findings whose substance lay in a comment, docstring, or test narration.
  The middle two are the trial's actual result; the round count alone is not.
  - Priority: P1
  - Notes: The advisory-narration count is recorded to distinguish "**the severity floor
    held**" from "**no narration churn occurred**". C-03 caps narration inaccuracies at
    `inconsistency`, so a floor-compliant verifier cannot produce a nonzero REQ-TRIAL-01
    count by construction; without the advisory series the trial cannot tell the two apart.
    The reports already carry per-severity totals, so this costs nothing to collect.
- **REQ-TRIAL-05:** The forge-2-tech overage (3 rounds against the original ≤2) MUST be
  recorded as a Phase 2 finding in its own right — **without** reopening R-05..R-08 on the
  narration-churn axis, which measured clean. The finding to file is §3.6.1.
  - Priority: P0

#### 3.6.1 The failure mode the trial actually found

- **REQ-TRIAL-06:** The recurring defect across both fix rounds was **a derived summary
  figure left stale by a correction made elsewhere in the same artifact** — not narration
  drift. Six of seventeen findings landed in one derived table (`tech-spec.md` §8.2) while
  the rosters those figures derive from were correct every time. Any artifact in this
  feature carrying figures derived from another section MUST declare that derivation and be
  recomputed in the same edit as its source.
  - Priority: P1
  - Notes: R-05..R-08 suppress narration churn but say nothing about derived-figure
    propagation *within* a single artifact. This is the new input for Phase 2's reopening.

## 4. Non-Functional Requirements

### 4.1 Suite quality

- **REQ-QUAL-01:** The full suite MUST pass. Baseline entering this feature is
  1840 passed / 2 skipped.
- **REQ-QUAL-02:** `ruff check tests/` MUST NOT exceed 19 errors. Fewer is a
  successful outcome and becomes the new baseline; more is a regression.
- **REQ-QUAL-03:** `bash scripts/validate.sh` MUST report "All checks passed!".
- **REQ-QUAL-04:** Success targets are **countable**, not wall-clock: prose-guard file
  ≤5 tests; mutation controls ~7; every positive stamp-verbatim test retained; each of
  the seven coverage gaps has a named test. No runtime threshold is specified, because
  a machine-dependent number cannot be reproduced by a verifier and would reintroduce
  unfalsifiable-claim churn.

### 4.2 Security

- **REQ-SEC-01** (stated in §3.3): path containment on `state-artifact --path`.
- No other security surface is introduced. This feature adds no authentication,
  authorization, network, or untrusted-input handling.

### 4.3 Observability

- **REQ-OBS-01:** Every assertion that replaces an exact-equality check MUST still
  fail with a message identifying which behavior broke and where. Loosening an
  assertion MUST NOT degrade its diagnostic value.

### 4.4 Concurrency

- **REQ-CONC-01:** Concurrent writers to `.pipeline-state.json` are **out of scope**.
  A single forge session writes at a time; the atomic write protects only against an
  interrupted or torn write, not against simultaneous writers. No locking protocol is
  required, and none may be introduced by this feature.
  - Notes: Stated explicitly so that a generic concurrency check (`CHECK-S27`)
    resolves against a recorded position. An unstated position has previously induced
    a full locking protocol that no requirement asked for.

### 4.5 Accessibility and scalability

- Not applicable. This feature has no user interface and no runtime load
  characteristics — it changes test code, canonical prose, and two CLI validation
  paths.

## 5. Constraints

- **C-01:** Canon lives in `skills/` and `references/`; the six adapter mirrors are
  generated, never hand-edited. `python3 scripts/build-adapters.py` regenerates them.
- **C-02:** After any `git checkout`, `merge`, or `pull`, adapter file modes can land
  as 0664 from the ambient umask and fail the mode test. Re-running
  `build-adapters.py` restores 0644; content is unaffected.
- **C-03:** `forge-verify`'s severity floor (R-05) applies: inaccuracies confined to
  comments, docstrings, or test narration cap at `inconsistency` and do not block.
- **C-04:** Re-verify is scoped (R-06): a re-verify confirms the prior report's
  findings; new findings below `error` do not block it; a finding with a recorded
  decision is never re-filed.
- **C-05:** `forge-verify` is at its 300-line cap. Rules that would grow it belong in
  `references/stage-exit-protocol.md` with a same-line pointer from the skill.
- **C-06:** This feature runs the **full** pipeline — PRD → tech spec → specs →
  backlog → loop → docs — because the rules under trial operate at every stage.
- **C-07:** Line numbers cited in the remediation plan are as of baseline commit
  `6337e13` and have drifted. Locate by symbol name or quoted text, never by line
  number.

## 6. Out of Scope

- Phase 4 items R-14 through R-17: findings D3, D4, C4, C5, C6, C7, F3, the remaining
  F4 eval fixture case, and the D8 nits.
- The version bump, CHANGELOG entry, and release checklist (R-17).
- Any product behavior change beyond the three named in §3.3 (REQ-FIX-01,
  REQ-SEC-01, and whatever REQ-FIX-02 surfaces).
- Driving `ruff check tests/` to zero. The requirement is non-increase.
- Changes to `eval/` fixtures beyond the prelude criterion key-set pin required by
  REQ-COV-03. The compliance eval was stabilized in GATE-P2 and is otherwise frozen.
  (**Corrected in v2:** v1 also admitted "the `resolver_line_identical` assertion", which
  v2 establishes already exists — nothing changes about its role.)
- Test files outside those named in T1-T4, except where REQ-BRIT-04's enumerated
  exact-stderr sites legitimately span additional files.
- Concurrency and locking (REQ-CONC-01).
- Re-litigating the review findings. The remediation plan's findings register is the
  surviving record.

## 7. Open Questions

**All three are RESOLVED as of v2** (during `forge-2-tech`; rosters and rationale in
`tech-spec.md` §10.1).

- **OQ-01 — RESOLVED.** The exact-stderr roster is **5 sites / 11 comparisons across 2
  files**, not ~15. See REQ-BRIT-04's v2 note.
- **OQ-02 — RESOLVED.** The canonical section is the **existing**
  `references/stage-exit-protocol.md` § "Host and capability determination" — no new
  section. `shared-conventions.md` § "Verify Capability" already self-identifies as a
  summary deferring to it, and both existing pointer surfaces name it by title.
- **OQ-03 — RESOLVED.** `resolver_line_identical` already asserts equality via
  `all(criteria.values())`; nothing changes about its role. The gap is the missing key-set
  pin. See REQ-COV-03's v2 note.

## 8. Success Criteria

> **These criteria restate figures DERIVED from §3.4 and §3.6.** When a roster or a trial
> figure changes there, recompute this section **in the same edit** (REQ-TRIAL-06).

The feature is done when all of the following hold:

1. `tests/test_capability_determination_prose.py` contains ≤5 tests, declares its
   protection set and non-goals, and has no AST self-inspection layer.
2. All capability-determination surfaces — including `forge-0-epic` — carry a
   paragraph or a pointer, resolved in canon rather than a test constant.
3. Mutation controls in `tests/test_stage_exit_protocol.py` are reduced to ~7 with
   every positive stamp-verbatim test intact.
4. `tests/test_state_verb_call_sites.py` satisfies REQ-TRIM-03's structural block scan; the
   window machinery (`LOOKBEHIND`, `LOOKAHEAD`, `CALL_SPAN`), its tuning tests, and the
   `inspect.getsource` meta-test are gone; the canon-mandate test survives; a mutation
   control replaces the deleted width bound.
5. Each of the seven T3 gaps has a named test; `state-complete --version 0` is
   refused at the write path; `state-artifact --path` enforces containment.
6. The seven brittleness items in §3.4 are addressed, using the v2-corrected rosters
   (exact-stderr 5 sites; hash 9 sites across two sub-families; corrupt-file 4;
   gate-selection 6).
7. Full suite green; `validate.sh` passes; `build-adapters.py --check` exits 0;
   `check-spec-purity.py` reports 0 violations; `ruff check scripts/ eval/` clean;
   `ruff check tests/` ≤19 errors.
8. **Zero narration-churn findings** across the whole feature (REQ-TRIAL-01), and
   blocking findings **converged** at every stage that took more than one round
   (REQ-TRIAL-02) — or work stopped on a violation of either, with a Phase 2 finding
   filed, which is a **valid and informative** outcome of this trial, not a failure of
   this feature. Any stage exceeding 2 rounds is recorded with its reason (REQ-TRIAL-03),
   alongside the narration-churn count and convergence sequence (REQ-TRIAL-04).
   - **Status at `forge-2-tech` close:** v1 — narration-churn **0/17**, convergence
     **5 → 1 → 0**, rounds **3** (over the ≤2 guideline, recorded per REQ-TRIAL-05).
     v2 — narration-churn **0/22**, convergence **2 → 0**, rounds **2**. The v2 amendment
     cycle is a **new stage version** and therefore started a fresh sequence (REQ-TRIAL-02
     counting rule 2).
   - **Criterion PROVISIONALLY met.** REQ-TRIAL-01's narration-churn count cannot fail at a
     stage that authors no comments, docstrings, or test narration — forge-1-prd and
     forge-2-tech author specification prose, so every zero above is structurally guaranteed
     rather than evidence. The decisive datapoint is **forge-5-loop**, where the original
     epic's churn occurred (11 of 12 blocking findings, all in the impl stage). Do not read
     these zeros as proof the rules work.

**What a user would complain about if we got this wrong:** that we deleted guards and
lost real protection (addressed by REQ-TRIM-02, REQ-TRIM-06, REQ-GUARD-04's
enumerated set, and the REQ-COV-* backfill running in the same feature), or that the
trim itself triggered another 9-round churn (addressed by REQ-GUARD-05/06 and
REQ-CANON-03, and measured by REQ-TRIAL-01).
