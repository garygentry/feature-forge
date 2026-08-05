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

**Who has this problem:** the operator answering needs-human prompts, and the main
agent driving `forge-5-loop` — which is structurally forced to be a reporter rather
than a driver.

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

### 3.2 Post-run tree reconciliation (#192)

- REQ-TREE-01: After a run ends and before any outcome is selected, the loop stage
  MUST detect a dirty working tree / index left by the run.
  - Priority: P0
- REQ-TREE-02: Detected stranded work MUST be attributed to the backlog item(s)
  that produced it, and driven to an explicit operator decision — commit per item,
  stash, or discard — as a required step, not a remark.
  - Priority: P0
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
  backlog summary and verify the affected items actually left
  `blocked`/`needsHuman`.
  - Priority: P0
- REQ-UNB-03: An unchanged blocked/needs-human count after a recovery pass MUST be
  treated and reported as a **failed recovery** — never as success.
  - Priority: P0

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
  (REQ-TREE), and the items have been unblocked with counts moved (REQ-UNB).
  Claiming it without those preconditions is a defect.
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
- REQ-REL-02: A failed decision-record write MUST be surfaced verbatim and MUST
  NOT be reported as recorded (mirror of the `state-*` verbs' exit-2 protocol).

### 4.2 State integrity

- REQ-STATE-01: Every new persistent surface follows the R4 pattern: JSON schema
  file, scripted verb writer, schema-conformance test. No hand-authored JSON, no
  schema-less state files (#181's lesson).

### 4.3 Observability / honesty

- REQ-OBS-01: Every report surface this feature touches must be able to cite the
  authoritative counts it derived its claims from; a claim the counters contradict
  is a reportable defect (this generalizes REQ-ATTR-03).

### 4.4 Compatibility

- REQ-COMPAT-01: Outcome-vocabulary and routing changes ripple into the stage-exit
  directive matrix and its tests deliberately — guard updates are expected and
  in scope, silent guard weakening is not.
- REQ-COMPAT-02: Runs that never hit needs-human/blocked states behave exactly as
  today (no new prompts, no new required steps on the happy path, beyond the
  Step 2a depth line of REQ-TOPO-03).

## 5. Constraints

- **Body caps:** `forge-5-loop` body is at 287/300 lines after the pre-PRD
  headroom buy-back; `forge-verify` is at 299/300. New prose lands in
  `references/` files (checklists, runner-contract, result-reporting) with
  one-line pointers from skill bodies. The topology CHECK goes in a checklist
  file, never the forge-verify body.
- **Canon/adapter discipline:** every canon edit regenerates adapters
  (`python3 scripts/build-adapters.py`); every `scripts/*.py` edit passes
  `ruff check scripts/ eval/`; stage/status constants stay in parity across
  `forge-session.py` and `epic-manifest.py` (parity tests enforce).
- **Runner scope:** prefer existing runner surfaces (rauf `backlog unblock`,
  `--retry-blocked`, `backlogSummary`). rauf-side changes ARE permitted when the
  recovery flow genuinely needs a runner surface that does not exist — accepted
  by the owner with the cost understood (second repo, second release train). Any
  rauf change implies revisiting `loopRunner.minRunnerVersion`.
- **Pipeline dogfood:** this feature runs through the forge pipeline itself
  (forge-1-prd → forge-5-loop), so every stage is also a live test of the S0/S1
  fixes.

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
  helper.
- **OQ-3 (→ tech spec):** the "large fraction" threshold for REQ-TOPO-02's
  advisory warning (the observed failure was 3 roots gating 81%).

## 8. Success Criteria

1. All seven issues closeable with evidence: each requirement above traces to a
   shipped, tested surface, and each issue's "Observed in" scenario, replayed,
   now produces the required behavior (decision persisted; items provably
   unblocked; tree reconciled; resolved outcome routed resume; starvation named;
   one consolidated prompt; topology reported).
2. `bash scripts/validate.sh` green, including the new schema-conformance and
   directive-matrix tests; adapters regenerated and deterministic.
3. The compliance eval's new loop-outcome fixture (REQ-EVAL-01) passes.
4. A happy-path run (no needs-human, no blocked) is byte-equivalent to today's
   behavior except the Step 2a depth line (REQ-COMPAT-02).
