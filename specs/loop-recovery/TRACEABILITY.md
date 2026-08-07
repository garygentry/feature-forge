# loop-recovery — Requirement Traceability Matrix

Every functional and non-functional requirement in `PRD.md` maps to at least one
implementation-spec document and section. **Primary** is the document that owns the
requirement's realization; **Supporting** documents cover shared contracts, orchestration,
or test proof. Coverage was validated mechanically: all 37 requirements trace, zero
uncovered.

> These are **pre-implementation** specs. Sections cited are anchors within this spec
> suite, not code locations. See `specs/CLAUDE.md` — specs plan the work and are not kept
> in sync with the code after the backlog ships.

## 3.1 Decision persistence (#196 — keystone)

| REQ ID | Requirement | Primary | Supporting |
|--------|-------------|---------|------------|
| REQ-DEC-01 | Answer persisted at collection, before it is acted on | `02` §2, §3 (`decision-record`) | `00` §3/§4; `05` §2 step 4 (record-at-collection); `07` §2.2 |
| REQ-DEC-02 | Record captures item/question/answer/decided/applied/actor | `02` §3 (entry builder) | `00` §4.1 (field semantics) |
| REQ-DEC-03 | Scripted verb, atomic, never hand-authored | `02` §3, §7 | `00` §2 (R4), §10 (`_commit_state`) |
| REQ-DEC-04 | Named recovery procedure replaces "stage a post-run retry" | `05` §2 (procedure), §6 (pointer edits) | `02` §4 (read-back verb); `01` §1.2 |
| REQ-DEC-05 | Enumerate unapplied decisions (first-class read-back) | `02` §4 (`--unapplied` filter) | `00` §4.3; `05` §2 step 1; `04` §5.4 |
| REQ-DEC-06 | Deferral + cancel-early recorded; re-surfaced next launch | `02` §3.2, §6 | `00` §4.2; `05` §2 step 4, §3 (re-entry) |
| REQ-DEC-07 | Append-only; latest-entry-per-item unapplied set | `02` §5, §6 | `00` §4.3; `07` §2.2 (append-only sequence) |

## 3.2 Post-run tree reconciliation (#192)

| REQ ID | Requirement | Primary | Supporting |
|--------|-------------|---------|------------|
| REQ-TREE-01 | Detect dirty tree before any outcome selected | `05` §4 sub-step 1 | `00` §7 (degradation) |
| REQ-TREE-02 | Attribute stranded work to items; required decision | `05` §4 sub-steps 2–3 | — |
| REQ-TREE-03 | Discard requires explicit confirmation, never default | `05` §4 sub-step 3 | — |
| REQ-TREE-04 | Unreconciled tree = named launch blocker next run | `05` §4 sub-step 4, §5 (`### 1g`) | `01` §5 (body budget) |

## 3.3 Recovery must unblock (#193)

| REQ ID | Requirement | Primary | Supporting |
|--------|-------------|---------|------------|
| REQ-UNB-01 | Applied + gate green → unblock as a required step | `04` §5, §6.4 | `02` §5 (`decision-apply` ordering); `07` §3 |
| REQ-UNB-02 | Per-item re-read proof; counts never the test | `04` §6 | `03` (gate condition c); `07` §3 |
| REQ-UNB-03 | Any item still blocked = failed recovery, named | `04` §6, §7 | `05` §2 step 6; `07` §3 |

## 3.4 An outcome for "decision made and applied" (#189)

| REQ ID | Requirement | Primary | Supporting |
|--------|-------------|---------|------------|
| REQ-OUT-01 | Outcome expresses resolved needs-human stop | `03` §2.1 | `00` §5.1 |
| REQ-OUT-02 | Resolved routes **resume**, not recover | `03` §2.2–2.3 | `00` §5.2 |
| REQ-OUT-03 | Resolved gated on decisions/tree/per-item | `03` §3 (procedural gate) | `04` §6; `05` §2 step 7 |

## 3.5 Truthful pending attribution (#190)

| REQ ID | Requirement | Primary | Supporting |
|--------|-------------|---------|------------|
| REQ-ATTR-01 | `selectable` from authoritative counts | `06` §3.3, §4 | `03` §5.1; `00` §8 |
| REQ-ATTR-02 | Render dependency starvation, not iteration limit | `03` §5.2 | `06` (blockingRoots) |
| REQ-ATTR-03 | No cause the counters contradict; conditional "(iter limit)" | `03` §6 | `00` §9 (citation) |
| REQ-ATTR-04 | Starvation = annotation, not enum value | `03` §5 | `00` §5.1 (no new enum) |

## 3.6 Systemic-cause consolidation (#191)

| REQ ID | Requirement | Primary | Supporting |
|--------|-------------|---------|------------|
| REQ-CLU-01 | Deterministic clustering substrate, agent-refinable | `06` §2, §2.4 | `00` §6.2; `05` §2 step 2; `07` §7.2 |
| REQ-CLU-02 | One consolidated decision per cluster ≥2 | `05` §2 step 3 | `00` §8.3 (blast radius) |
| REQ-CLU-03 | Consolidated prompts framed by blast radius | `05` §2 step 3 | `06` §4 (gated-subtree output) |
| REQ-CLU-04 | Consolidated answer recorded per item (shared clusterId) | `05` §2 step 4 | `02` §3; `06` §2 (clusterId mint) |

## 3.7 Dependency-topology check (#194)

| REQ ID | Requirement | Primary | Supporting |
|--------|-------------|---------|------------|
| REQ-TOPO-01 | forge-4-backlog reports topology | `06` §3, §5.1 | `01` §1.2 |
| REQ-TOPO-02 | forge-verify advisory topology check (CHECK-B28) | `06` §5.2 | `01` §1.2 (count literals) |
| REQ-TOPO-03 | forge-5-loop Step 2a surfaces max chain depth | `06` §5.3 | `03` §8; `00` §8 |

## 3.8 Eval coverage (the #176 lesson)

| REQ ID | Requirement | Primary | Supporting |
|--------|-------------|---------|------------|
| REQ-EVAL-01 | Compliance eval measures the resolved route | `07` §6 (loop-outcome probe + fixture) | `01` §1.3 |

## 4. Non-Functional Requirements

| REQ ID | Requirement | Primary | Supporting |
|--------|-------------|---------|------------|
| REQ-REL-01 | Single writer; atomic write-then-rename | `04` §1.3, §5.4 | `00` §10; `02` §7 |
| REQ-REL-02 | Failed step surfaced verbatim, never claimed succeeded | `04` §5.3, §7 | `00` §7; `02` §7; `05` (procedure stop) |
| REQ-STATE-01 | R4 pattern for every persistent surface | `02` §2, §8 | `00` §4; `07` §2 |
| REQ-OBS-01 | Every report surface cites authoritative counts | `00` §9 (master table) | `03` §5.2/§6; `05` §7; `04`; `06` |
| REQ-COMPAT-01 | Vocabulary/routing ripple into directive matrix, deliberate | `03` §4, §7 | `01` §1.2; `00` §5; `07` §4.3 |
| REQ-COMPAT-02 | Clean-tree happy path unchanged but for Step 2a depth line | `05` §2 step 1, §4 | `03` §8; `01` §4; `07` §8 (SC-4) |
| REQ-SEC-01 | No secret-shaped fields; actor labels only | `02` §9 | `00` §4.1; `05` §2 step 3 |
| REQ-PERF-01 | Topology/cluster linear + bounded | `06` §6 | `00` §6; `07` §7.1 |

## Foundation documents

`00-core-definitions.md` and `01-architecture-layout.md` are cross-cutting: `00` defines
the schema, enum, constants, output shapes, error model, and the REQ-OBS citation table
every other document builds on; `01` places every change in the file manifest and fixes the
delivery order (DEC → TREE → UNB → OUT → ATTR → CLU → TOPO → EVAL). They appear as
Supporting throughout rather than owning a single requirement.

## Carried forge-2-tech advisories (parked into this suite)

| Advisory | Where addressed |
|----------|-----------------|
| V-012 — rename the outcome-count test when `resolved` lands (else it greens silently) | `07` §4.1 (rename to `..._six_...`) |
| V-015 — vendor the three verify-test-debt `blockedReason` strings verbatim | `07` §7.2 (V-015 fixture, ~0.028 margin) |
