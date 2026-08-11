# verify-fix-sweep — Product Requirements Document

## 1. Problem Statement

A fix pass corrects a claim where the finding pointed, but nothing checks whether the
same wrong claim survives anywhere else. In the incident that motivates this feature
(issue #170, a ~39-artifact forge corpus), finding F-5 corrected "universal among the
tracked hyperscalers" at three sites — and the identical sentence survived **verbatim
in a fourth sibling artifact**, passed a subsequent full-corpus review, propagated
into generated output, and would have shipped. It was caught only because a later
session re-derived the count from raw source records. The same closeout also had a
hand-authored work order listing **15 of 16** artifacts; the dropped one would have
been published unreviewed. And the surviving artifact **contradicted itself** — its
own body stated the correct 4-of-7 breakdown two sections below the false claim.

All three are one defect class — *"did the change actually reach every site?"* — and
none is catchable by the existing checks: schema validation passes (well-formed
prose), the mechanical pre-flight passes (paths, registration, status), and human
review passes because a reviewer reads one artifact at a time.

A hard design constraint shapes where the remedy can live: verify-loop-hardening's
R-06 ("Re-verify scope and convergence", `references/stage-exit-protocol.md`) says a
re-verify is **never** a fresh full-checklist sweep — it confirms the prior report's
findings and examines the fix delta. So a corrected-claim sweep cannot ride the
re-verify. It must run **inside the fix pass** (forge-fix Steps 5/6), where the fix
delta is fresh and survivors can still be dispositioned in the same round.

**Who has this problem:** every operator of a multi-artifact forge feature, and every
agent session running a fix pass — a corrected claim that survives elsewhere ships
with the pipeline's blessing.

**Why now:** this is milestone 1 (mechanical) of hardening Track F. Milestone 2
(#171, the semantic sweep) is gated by recorded owner decision on this milestone
having run on at least one real fix pass — its instances are the evidence for where
the mechanical/semantic boundary sits.

## 2. User Stories

- As an **operator closing out a fix pass**, I want every surviving occurrence of a
  corrected claim surfaced before the pass closes, so that a false claim cannot
  outlive the fix that removed it.
- As an **agent running forge-fix**, I want the sweep's hits to be dispositionable in
  the same pass (fix it, or justify why it stands), so that a legitimate quote or
  audit record doesn't burn an extra fix round.
- As an **operator relying on a work order**, I want any enumerated per-item work
  list checked against the actual item set with omissions **named**, so that a
  silently dropped item cannot go unreviewed.
- As a **verifier**, I want an artifact that states the same quantity in two places
  to be flagged when they disagree, so that an internally contradictory artifact
  cannot pass as consistent.
- As a **maintainer of milestone 2 (#171)**, I want milestone 1 validated on a real
  fix pass, so that the semantic sweep's design starts from evidence of what the
  mechanical sweep does and does not catch.

## 3. Functional Requirements

### 3.1 Corrected-Claim Sweep (fix pass)

- REQ-SWEEP-01: After fix steps are applied and before the fix pass closes, a
  mechanical sweep must extract the corrected (removed/replaced) text from the fix
  delta and search the corpus for surviving occurrences of that text.
  - Priority: P0
  - Notes: "Fix delta" is the fix pass's own change set (working tree against the
    pre-fix baseline, or the fix commit's diff — settled in the tech spec). The
    sweep is part of the **fix pass** (forge-fix Steps 5/6), never the re-verify
    (Constraint C-1).
- REQ-SWEEP-02: Detection must be deterministic and model-free: matching is
  normalized (case, whitespace, punctuation) substring/near-match over removed lines
  above a minimum-length threshold, so reflowed-but-identical prose is caught while
  trivially short strings are skipped.
  - Priority: P0
  - Notes: Token-similarity scoring and semantic matching are out of scope
    (milestone 2, #171). The F-5 sibling was verbatim; normalized matching is the
    milestone-1 recall target.
- REQ-SWEEP-03: The sweep corpus is **all git-tracked files repo-wide, including
  generated output**, minus the `.verification/` findings documents.
  - Priority: P0
  - Notes: Findings documents quote the corrected claim by design — they are audit
    records, not survivors. Generated output is explicitly in scope (F-5 reached
    `src/generated/*.ts`).
- REQ-SWEEP-04: Every reported survivor must be **dispositioned before the pass
  closes**: either corrected in the same pass, or explicitly justified with a
  recorded reason (deliberate quote, historical record, false positive). An
  undispositioned survivor blocks closure.
  - Priority: P0
  - Notes: Detection is mechanical; disposition is judgment. A hit is a candidate,
    not automatically a defect.
- REQ-SWEEP-05: Sweep results and every disposition are recorded in the findings
  document (the `## Fix Progress` section or an adjacent sweep record), so the
  sweep's evidence trail lives in the same sanctioned audit record as the fixes.
  - Priority: P0
- REQ-SWEEP-06: Unresolved survivors route through forge-fix's **existing** outcome
  rows — no new `--outcome` values. A survivor awaiting a user decision closes
  `decisions`; an unfixable/unjustifiable survivor closes `failed`; a fully
  dispositioned sweep leaves the pass on its normal path.
  - Priority: P0
- REQ-SWEEP-07: When no git delta is available (not a git repo, or no baseline to
  diff), the sweep is skipped with a **visible notice** recorded in Fix Progress
  ("sweep not run — no git delta") — never silently.
  - Priority: P1

### 3.2 Work-Order Cardinality Assertion

- REQ-CARD-01: The fix pass must assert that the findings document's Fix Execution
  Plan **covers every finding** in the report: each finding maps to at least one
  execution step, and any claimed totals are re-derived from the actual findings
  set. Omissions are reported by **name**, not count.
  - Priority: P0
- REQ-CARD-02: A backlog-mode verification CHECK must assert: when the backlog or an
  artifact it derives from declares an enumerated per-item work list with claimed
  coverage of a set, the list's cardinality is re-derived from the actual item set
  and any missing item is named.
  - Priority: P0
- REQ-CARD-03: An impl-mode verification CHECK must assert the same for
  implementation artifacts: any declared work order / coverage list is checked
  against the actual artifact set it claims to cover, naming omissions (the
  15-of-16 hand-authored work-order case).
  - Priority: P0
- REQ-CARD-04: Cardinality assertions must degrade gracefully: an artifact set with
  no declared work list yields not-applicable, never a hard fail.
  - Priority: P1

### 3.3 Internal-Consistency Check

- REQ-CONS-01: A verification CHECK (verifier judgment, checklist prose) must flag
  an artifact that states the same quantity or claim in more than one place
  inconsistently — front matter vs body, summary block vs prose (the F-5 artifact
  asserted "universal" while its own body stated 4-of-7 two sections below).
  - Priority: P1
  - Notes: Realized as checklist prose executed by the verifier at verify time; no
    mechanical extractor in milestone 1 (see Out of Scope). Severity follows the
    existing severity-floor conventions in forge-verify.

## 4. Non-Functional Requirements

### 4.1 Performance

- REQ-PERF-01: The sweep must be cheap enough to run on every fix pass without
  ceremony: deterministic, no network, no model calls, and completing in seconds at
  this repository's scale (thousands of tracked files).
  - Priority: P0

### 4.2 Observability

- REQ-OBS-01: Every survivor report must name the file and location of the hit and
  the removed text it matched, so disposition requires no re-derivation.
  - Priority: P0

### 4.3 Concurrency

- REQ-CONC-01: Single writer assumed, per the standing owner decision recorded in
  `references/decisions/single-writer-threat-model.md` (#180): the sweep is
  read-only over the corpus and appends only to the findings document; no locking
  is required or wanted. This is the recorded position for CHECK-S27.
  - Priority: P0

## 5. Constraints

- **C-1 (R-06 is untouched).** The corrected-claim sweep lives in the fix pass
  (forge-fix Steps 5/6). "Re-verify scope and convergence"
  (`references/stage-exit-protocol.md`) is not modified: a re-verify remains scoped
  to prior findings + fix delta and never becomes a fresh sweep.
- **C-2 (no model).** All milestone-1 mechanics (sweep, cardinality assertions) are
  deterministic and model-free. The internal-consistency check is verifier judgment
  (checklist prose), consistent with how other CHECKs run.
- **C-3 (tooling).** Any script ships in `scripts/` as Python stdlib-only, matching
  the repository's tooling constraint (AGENTS.md); no new dependencies.
- **C-4 (word/line budgets).** New checklist prose lands in
  `references/`-tier files (e.g. `skills/forge-verify/references/verification-checklists/*.md`) — the
  forge-verify SKILL.md body is at 299/300 lines and gains at most a pointer line.
  forge-fix SKILL.md edits stay within the 300-line body cap.
- **C-5 (canon build discipline).** Canon edits regenerate `adapters/` and pass
  `bash scripts/validate.sh` plus `ruff check scripts/ eval/`. New reference prose
  must remain correct under the #167 host-term translation pass — reword or exempt
  any prose that *mentions* (rather than uses) a host term.
- **C-6 (schema stability).** No new forge-fix outcome values, no pipeline-state
  schema changes, no new config keys.

## 6. Out of Scope

- **Semantic sweeping** (#171 / milestone 2): enumerating claims against a shared
  evidence store and re-testing each; anything requiring a model or similarity
  thresholds. Explicitly gated behind this milestone's real-fix-pass validation.
- **Modifying the re-verify** in any way (R-06 stands).
- **A mechanical numeric-claim extractor** for the internal-consistency check
  (regex-mining "N of M" claims): milestone 1 realizes REQ-CONS-01 as verifier
  judgment only.
- **Non-forge corpora**: the sweep operates where forge-fix operates — a git
  repository holding forge artifacts. No standalone-CLI use case is designed for.
- **Work-order formats outside forge artifacts** (e.g. session handoff documents in
  consumer projects) — the CHECKs cover lists declared in forge-verified artifacts.

## 7. Open Questions

- Exact normalization rules and the minimum-length threshold for REQ-SWEEP-02
  (deferred to the tech spec; requirement is "reflowed prose caught, short trivia
  skipped, deterministic").
- Whether the sweep tool is a new `forge-session.py` verb or a standalone script
  (tech spec; C-3 binds either way).
- Precise fix-delta baseline (working tree vs HEAD, or Commit 1's diff) and its
  interaction with forge-fix's two-commit protocol (tech spec).

## 8. Success Criteria

- A regression-shaped test corpus reproduces F-5: a fix removes a claim from one
  artifact while an identical sentence (and a whitespace-reflowed variant) survives
  in a sibling and in a generated file — the sweep reports both survivors by file
  and location, and reports nothing for the `.verification/` audit copy.
- A work list declaring 15 of 16 items produces an assertion failure that **names**
  the missing 16th item.
- The fix pass cannot close with an undispositioned survivor: outcomes map per
  REQ-SWEEP-06 and the disposition trail is readable in the findings document.
- `bash scripts/validate.sh` and `ruff check scripts/ eval/` green; adapters
  regenerated with no drift.
- **Milestone acceptance (P5.3):** the sweep runs on at least one real fix pass and
  its behavior is reviewed before milestone 2 (#171) begins — per the recorded owner
  decision, #170 is not "done done" until this validation happens.
