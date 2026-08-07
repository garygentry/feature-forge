# loop-recovery — Product Requirements Document

## 1. Problem Statement

On 2026-08-04, a fully-hardened forge pipeline ran the `verify-test-debt` backlog
(16 items) and completed **0 of 16** — not because the work was hard, but because
three root items stopped on the same human decision and every recovery affordance
was missing. The operator answered the questions; the answers died with the session
(#196). The blocking cause was fixed and verified green; the items stayed `blocked`
(#193). The failed items stranded 84 files in the index, guaranteeing the next
launch fails its clean-tree precondition (#192). The agent that had collected the
decision, applied the fix, and verified the gate green was still forced to close by
telling the operator to go re-derive state from disk (#189). The final report said
"iteration limit reached" when 19 of 24 granted iterations were unused (#190). The
one shared root cause surfaced as three separate prompts, none stating it gated all
16 items (#191). And the backlog shape that made one defect fatal — 3 roots gating a
13-deep chain — passed both backlog generation and backlog verification without
comment (#194).

Loop recovery today is a no-op wearing a success message. This feature makes it
real: decisions persist, recovery provably unblocks, stranded work is reconciled,
the outcome vocabulary can express "resolved", reports attribute causes truthfully,
systemic causes are consolidated, and fragile topologies are flagged before they run.

**Who has this problem:** the operator answering needs-human prompts; the main
agent driving `forge-5-loop` — which is structurally forced to be a reporter rather
than a driver; and the backlog author at `forge-4-backlog`, whose fragile
topologies pass both authoring and verification without comment (#194).

**Why now:** these seven issues (GitHub milestone `hardening/B-loop-recovery`) were
filed against the *current, hardened* code from a live run. This is the
highest-value track of the August 2026 hardening plan.

**Source issues:** #196 (keystone), #193, #192, #189, #190, #191, #194. Their
bodies are carried into §3 as requirements; the observed-in evidence above is
quoted from them.

## 2. User Stories

- As an **operator**, I want my needs-human answers persisted the moment I give
  them, so that a session end, crash, or context clear never costs me a decision I
  already made.
- As an **operator**, I want a recovery pass to prove the blocked items actually
  became runnable, so that "recovery complete" cannot mean "nothing changed".
- As the **main agent**, I want a required post-run tree reconciliation, so that a
  failed run's stranded work becomes an explicit decision instead of a guaranteed
  precondition failure on the next launch.
- As the **main agent**, I want an outcome that expresses "the human decision was
  made and applied", so that I can close the turn fencing a relaunch instead of
  pointing the operator at a navigator whose text contradicts what just happened.
- As an **operator**, I want pending items attributed to their true cause, so that
  I don't raise the iteration multiplier when the real fix is unblocking three
  roots.
- As an **operator**, I want one consolidated decision per systemic cause, framed
  by blast radius, so that I answer once instead of three times and know it gates
  16/16 items.
- As a **backlog author**, I want topology reported and fragile shapes warned
  about at authoring and verification time, so that a single point of total
  failure is visible before the loop runs.

## 3. Functional Requirements

Ordering note (from the plan and issue dependency edges): REQ-DEC is the keystone
(#196 → #193 → #189; #192 → #189; #194 feeds #190/#191). The backlog should
implement in the order: DEC, TREE, UNB, OUT, ATTR, CLU, TOPO, EVAL.

### 3.1 Decision persistence (#196 — keystone)

- REQ-DEC-01: A needs-human answer collected from the operator MUST be persisted
  to a durable, per-backlog decision record at the moment it is collected — before
  it is acted on. A decision that exists only in conversation memory is a defect.
  - Priority: P0
  - Notes: **Durability scope:** the record is untracked run-local state (the
    standing #195 direction for runner-adjacent artifacts) — durable means it
    survives session end and context clear; it is not expected to survive a fresh
    clone and is not part of code review. Because it is untracked, decision writes
    never dirty the working tree that REQ-TREE-01/REQ-OUT-03 inspect.
- REQ-DEC-02: Each record MUST capture at minimum: the item id, the question, the
  answer, when it was decided, when/whether it was applied, and by what (session /
  actor).
  - Priority: P0
- REQ-DEC-03: The record MUST be written by a scripted verb (the R4 pattern:
  schema file + verb writer + conformance test), atomically, and never
  hand-authored as JSON by the agent. This surface must not become a new #181.
  - Priority: P0
- REQ-DEC-04: The undefined phrase "stage a post-run retry" in the runner contract
  MUST be replaced by a named, referenced procedure that reads the decision record
  back and drives recovery from it.
  - Priority: P0
- REQ-DEC-05: The recovery procedure MUST be able to enumerate which recorded
  decisions are not yet applied (read-back is a first-class operation, not a
  side effect).
  - Priority: P0
- REQ-DEC-06: A decision is recorded at collection on **every** branch — including
  the "cancel the run early" branch and an operator who defers a consolidated
  (REQ-CLU-02) decision. A recorded-but-unapplied decision is marked unapplied and
  MUST be re-surfaced by the REQ-DEC-05 enumeration on the next launch.
  - Priority: P0
- REQ-DEC-07: **Record lifecycle:** an item MAY accumulate more than one decision
  over time (a re-raised needs-human with a new question or revised answer);
  records are append-only — a later decision never destroys an earlier one's audit
  fields — and the REQ-DEC-05 unapplied set is the latest undecided-or-unapplied
  entry per item. The record persists for the life of the backlog and is never
  pruned automatically. Items answered by one consolidated decision (REQ-CLU-04)
  remain independently re-decidable.
  - Priority: P0

### 3.2 Post-run tree reconciliation (#192)

- REQ-TREE-01: After a run ends and before any outcome is selected, the loop stage
  MUST detect a dirty working tree / index left by the run.
  - Priority: P0
- REQ-TREE-02: Detected stranded work MUST be attributed to the backlog item(s)
  that produced it, and driven to an explicit operator decision — commit per item,
  stash, or discard — as a required step, not a remark.
  - Priority: P0
  - Notes: **Attribution basis:** best-effort from runner-native evidence (the
    runner's state/event records of which items ran and when); reliable per-item
    provenance is NOT a prerequisite. A change that cannot be attributed to an
    item is not dropped — the unattributed set is presented as a single
    consolidated decision. §5's rauf-side permission remains available if the
    tech spec finds best-effort insufficient, but this requirement does not
    spend it.
- REQ-TREE-03: Discard MUST require explicit operator confirmation; it is never a
  default or an automatic action.
  - Priority: P0
- REQ-TREE-04: An unreconciled tree MUST be surfaced as a launch blocker for the
  next run (the next launch's precondition failure names the previous run's
  stranded work, not a generic "uncommitted changes").
  - Priority: P0

### 3.3 Recovery must unblock (#193)

- REQ-UNB-01: After a decision is applied and the verification gate is green, the
  recovery procedure MUST unblock the affected items (the runner's unblock
  operation, or an equivalent relaunch flag) as a required step — advisory prose
  is not sufficient.
  - Priority: P0
- REQ-UNB-02: After unblocking, the procedure MUST re-read the authoritative
  backlog summary and verify, **per item**, that each affected item actually left
  `blocked`/`needsHuman`. The per-item identity test is authoritative; aggregate
  counts are never a substitute (a count can be unchanged while items swap
  states, and can move for unrelated reasons).
  - Priority: P0
- REQ-UNB-03: Recovery succeeds only when **every** affected item left
  `blocked`/`needsHuman`. Any affected item still blocked — including a partial
  unblock where some items moved — MUST be treated and reported as a **failed
  recovery**, naming the items that did and did not move. Never report success
  the per-item test contradicts.
  - Priority: P0
  - Notes: Partial is failed, not a distinct state — one test governs
    REQ-UNB-02/-03 and REQ-OUT-03's gate.

### 3.4 An outcome for "decision made and applied" (#189)

- REQ-OUT-01: The loop outcome vocabulary MUST be able to express that a
  needs-human stop was subsequently resolved (decision made and applied), distinct
  from "decisions still outstanding".
  - Priority: P0
- REQ-OUT-02: The resolved outcome MUST route as a **resume** (its next-steps text
  fences the relaunch command), not as a **recover** (navigator hand-off).
  - Priority: P0
- REQ-OUT-03: The resolved outcome MUST be gated on all of: every recorded
  needs-human item has a decision record (REQ-DEC), the working tree is clean
  (REQ-TREE), and every affected item has left `blocked`/`needsHuman` per the
  REQ-UNB-02 per-item test. Claiming it without those preconditions is a defect.
  Untracked runner-state artifacts (the decision record among them, per
  REQ-DEC-01) do not count toward the clean-tree precondition.
  - Priority: P0

### 3.5 Truthful pending attribution (#190)

- REQ-ATTR-01: The result report MUST compute `selectable` = pending items whose
  dependencies are all done, from the authoritative counts.
  - Priority: P0
- REQ-ATTR-02: When `selectable == 0` and iterations remain unused, the report
  MUST render dependency starvation — naming the blocking root items and the size
  of the subtree each gates — and MUST NOT attribute the pending items to the
  iteration limit.
  - Priority: P0
- REQ-ATTR-03: No report surface may attribute a cause that the iteration
  counters contradict. The existing hardcoded "(iteration limit reached)" surfaces
  MUST be conditional on the limit actually having been the binding constraint.
  - Priority: P0
- REQ-ATTR-04: The requirement is truthful attribution; whether it is expressed as
  a distinct outcome variant (e.g. `partial-starved`) or a cause annotation on the
  existing `partial` outcome is a tech-spec decision (see §7).
  - Priority: P0

### 3.6 Systemic-cause consolidation (#191)

- REQ-CLU-01: After a run, needs-human and blocked items MUST be clustered by
  underlying-reason similarity. A deterministic scripted helper produces candidate
  clusters (testable); the agent MAY merge or refine them by judgment before
  presenting — but the scripted assist is the required substrate, not optional.
  - Priority: P1
  - Notes: The PRD constrains only that the helper is deterministic and its
    clusters agent-refinable; the similarity criterion itself is OQ-4.
- REQ-CLU-02: For any cluster of two or more items, the operator MUST be presented
  with **one** consolidated decision naming every affected item and the full
  dependency subtree the cluster gates.
  - Priority: P1
- REQ-CLU-03: Consolidated prompts MUST be framed by blast radius (e.g. "this
  gates 16/16 items"), not per item.
  - Priority: P1
- REQ-CLU-04: A consolidated decision, once answered, is recorded via the
  REQ-DEC mechanism (one record per affected item, or an equivalent that
  preserves per-item read-back).
  - Priority: P1

### 3.7 Dependency-topology check (#194)

- REQ-TOPO-01: Backlog authoring guidance (forge-4-backlog) MUST report the
  backlog's topology: root count, maximum chain depth, and the fan-out (gated
  subtree size) of each root.
  - Priority: P1
- REQ-TOPO-02: Backlog verification MUST include an advisory topology check that
  warns when a single root gates a large fraction of the backlog. Advisory means
  it reports and warns; it does not block.
  - Priority: P1
- REQ-TOPO-03: forge-5-loop's iteration math (Step 2a) MUST surface maximum chain
  depth alongside the computed iteration count, since depth bounds achievable
  progress regardless of iteration budget.
  - Priority: P1

### 3.8 Eval coverage (plan §6.4 — the #176 lesson)

- REQ-EVAL-01: The compliance eval MUST gain a loop-outcome fixture asserting the
  new resolved route (REQ-OUT) emits its sentinel — the new outcome must not ship
  unmeasured.
  - Priority: P0

## 4. Non-Functional Requirements

### 4.1 Reliability & concurrency

- REQ-REL-01: **Single writer assumed.** One forge session reads/writes the
  decision record at a time (the standing #180 position). Atomic write-then-rename
  protects only against an interrupted write, not concurrent writers. Concurrent
  multi-session access is explicitly out of scope; no locking protocol is
  required or wanted.
  - Priority: P0
- REQ-REL-02: A failed scripted recovery step — a decision-record write, or an
  unblock operation that errors or is unavailable at the configured runner
  version — MUST be surfaced verbatim and MUST NOT be reported as
  recorded/succeeded (mirror of the `state-*` verbs' exit-2 protocol). A failed
  unblock is thereby distinguishable from REQ-UNB-03's ran-but-nothing-moved
  failure.
  - Priority: P0

### 4.2 State integrity

- REQ-STATE-01: Every new persistent surface follows the R4 pattern: JSON schema
  file, scripted verb writer, schema-conformance test. No hand-authored JSON, no
  schema-less state files (#181's lesson).
  - Priority: P0

### 4.3 Observability / honesty

- REQ-OBS-01: Every report surface this feature touches must be able to cite the
  authoritative counts it derived its claims from; a claim the counters contradict
  is a reportable defect (this generalizes REQ-ATTR-03).
  - Priority: P0

### 4.4 Compatibility

- REQ-COMPAT-01: Outcome-vocabulary and routing changes ripple into the stage-exit
  directive matrix and its tests deliberately — guard updates are expected and
  in scope, silent guard weakening is not.
  - Priority: P0
- REQ-COMPAT-02: Runs that never hit needs-human/blocked states produce no new
  prompts and no new required *operator decisions*, beyond the Step 2a depth line
  of REQ-TOPO-03. The REQ-TREE-01 detection step runs on every run but is silent
  on a clean tree; REQ-TREE-02's decision fires only when the tree is dirty.
  - Priority: P0

### 4.5 Security

- REQ-SEC-01: Decision records hold operator-authored free text and are treated
  as repo-visible, non-sensitive content (untracked per REQ-DEC-01, but never
  relied on as a secret store): prompts MUST NOT solicit secrets, the record
  captures no credential material, and the applied-by field identifies the
  session/actor only — never user identity beyond that.
  - Priority: P0

### 4.6 Performance

- REQ-PERF-01: Topology computation (root count, max chain depth, per-root
  fan-out) MUST be linear in backlog size and add no perceptible latency to
  Step 2a at realistic backlog sizes (tens of items; the observed corpus is 16).
  No further quantified targets apply — a local single-operator CLI has no
  throughput or uptime dimension.
  - Priority: P2

## 5. Constraints

- **Body caps (MUST):** the 300-line/5000-word body cap is a hard CI gate.
  `forge-5-loop` is at 287/300 after the pre-PRD headroom buy-back;
  `forge-verify` is at 299/300. New prose MUST land in `references/` files
  (checklists, runner-contract, result-reporting) with one-line pointers from
  skill bodies; the topology CHECK MUST NOT land in the forge-verify body.
- **Canon/adapter discipline (MUST):** every canon edit regenerates adapters
  (`python3 scripts/build-adapters.py`); every `scripts/*.py` edit passes
  `ruff check scripts/ eval/`; stage/status constants stay in parity across
  `forge-session.py` and `epic-manifest.py` (parity tests enforce all three).
- **Runner scope (SHOULD prefer forge-side):** prefer existing runner surfaces
  (rauf `backlog unblock`, `--retry-blocked`, `backlogSummary`). rauf-side
  changes ARE permitted when the recovery flow genuinely needs a runner surface
  that does not exist — accepted by the owner with the cost understood (second
  repo, second release train). Any rauf change implies revisiting
  `loopRunner.minRunnerVersion`. REQ-TREE-02 explicitly does not spend this
  permission (best-effort attribution suffices).
- **Pipeline dogfood (MUST):** this feature runs through the forge pipeline
  itself (forge-1-prd → forge-5-loop), so every stage is also a live test of
  the S0/S1 fixes.

## 6. Out of Scope

- **Cutting release 0.16.0** — the track closes with a release, but release
  mechanics are a track-level action outside this feature's success criteria.
- **Locking / concurrent multi-session support** — per REQ-REL-01 and the
  standing #180 direction (Track G records the decision).
- **#195** (`.gitignore` for `.rauf/` artifacts) — already shipped in S0.
- **Semantic fix-sweeps (#170/#171), skip-docs (#197/#165/#173), zero-prompt
  config (#153/#164), contracts batch (#186/#187/#188), adapter host-term
  translation (#167)** — Tracks C–G, tracked by their own milestones.
- **Retroactively recovering the verify-test-debt run** — its backlog was
  completed manually; this feature prevents recurrence, it does not replay
  history.

## 7. Open Questions

- **OQ-1 (→ tech spec):** REQ-ATTR-04 — distinct `partial-starved` outcome value
  vs. a `cause` field on `partial`. Weigh the EXIT_OUTCOMES enum/routing/test
  ripple against the value of distinct next-steps text.
- **OQ-2 (→ tech spec):** exact location and name of the decision record file
  (issue #196 proposes `{backlogDir}/{stateDir}/forge-decisions.json`) and whether
  the clustering assist (REQ-CLU-01) lives in `forge-session.py` or a separate
  helper. (The git-tracking question is settled: untracked run-local, per
  REQ-DEC-01's durability note.)
- **OQ-3 (→ tech spec):** the "large fraction" threshold for REQ-TOPO-02's
  advisory warning (the observed failure was 3 roots gating 81%).
- **OQ-4 (→ tech spec):** the similarity criterion for REQ-CLU-01's candidate
  clustering — what makes two needs-human reasons the same underlying cause, and
  how the deterministic helper decides it.

## 8. Success Criteria

1. All seven issues closeable with evidence: each requirement above traces to a
   shipped, tested surface, and each issue's "Observed in" scenario, replayed
   against a fixture backlog reproducing the observed topology (3 roots, 13-deep
   chain, one shared blocking cause), now produces the required behavior
   (decision persisted; items provably unblocked per item; tree reconciled;
   resolved outcome routed resume; starvation named; one consolidated prompt;
   topology reported).
2. `bash scripts/validate.sh` green, including the new schema-conformance and
   directive-matrix tests; adapters regenerated and deterministic.
3. The compliance eval's new loop-outcome fixture (REQ-EVAL-01) passes.
4. A clean-tree happy-path run (no needs-human, no blocked, nothing stranded)
   produces output equivalent to today's except the Step 2a depth line
   (REQ-COMPAT-02), measured against a captured baseline from a pre-change run.
