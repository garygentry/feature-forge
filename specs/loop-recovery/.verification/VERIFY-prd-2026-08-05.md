# Verification Report: loop-recovery (prd)
Date: 2026-08-05
Pipeline Stage: forge-1-prd (complete, version 1, commit c27804540cd8216116a84cbe3942ef14ccb89367)
Artifacts Reviewed:
- `specs/loop-recovery/PRD.md`
- `specs/loop-recovery/.pipeline-state.json`
- `skills/forge-1-prd/references/prd-template.md`
- `forge.config.json`, `.gitignore`
- `skills/forge-5-loop/references/runner-contract.md`, `scripts/forge-session.py` (grounding only)
- GitHub issues #196, #193, #192, #189, #190, #191, #194

Executed 15 of 15 checks. Results: 6 pass, 9 fail, 0 not-applicable.

| Check | Result | Note |
|---|---|---|
| CHECK-P01 | pass | All 8 template sections present and populated. §4 renames the template's illustrative NFR subsections to domain-appropriate ones (Reliability, State integrity, Observability, Compatibility) — permitted; the substantive omission is filed under P12. |
| CHECK-P02 | pass | No TBD/TODO/FIXME/placeholder markers. |
| CHECK-P03 | pass | §6 lists five specific exclusions, each with a reason and an owning track/milestone. |
| CHECK-P04 | pass | OQ-1..3 are each a concrete binary/parameter decision routed to the tech spec. |
| CHECK-P05 | fail | V-010 |
| CHECK-P06 | pass | 33 requirement IDs, all unique, all `REQ-{CAT}-NN`. |
| CHECK-P07 | fail | V-007 |
| CHECK-P08 | fail | V-001, V-002, V-003, V-004, V-005 |
| CHECK-P09 | pass | Named internal surfaces (`forge-session.py`, Step 2a, EXIT_OUTCOMES, rauf `backlog unblock`) are this feature's product domain, not premature technology choices; §5 carries the genuine mandates with justification. |
| CHECK-P10 | fail | V-013 |
| CHECK-P11 | fail | V-012 |
| CHECK-P12 | fail | V-006 |
| CHECK-P13 | fail | V-011 |
| CHECK-P14 | fail | V-001, V-005, V-009 |
| CHECK-P15 | fail | V-003, V-008 |

Deliberate deferrals honored, not re-filed: §7 OQ-1 (`partial-starved` vs `cause` field), OQ-2 (decision-record path/name; clustering-assist home), OQ-3 (REQ-TOPO-02 threshold), and REQ-REL-01's explicit single-writer / no-locking position (the standing #180 direction).

## Summary
- Total findings: 13
- Gaps: 8
- Inconsistencies: 1
- Improvements: 4
- Errors: 0

## Findings

### V-001: "Durable" is undefined against the repo's deny-by-default `.rauf/` ignore, and the answer changes REQ-OUT-03
- **Severity:** gap
- **Location:** PRD.md §3.1 REQ-DEC-01/-02, §3.4 REQ-OUT-03, §7 OQ-2
- **Issue:** REQ-DEC-01 requires the answer be "persisted to a durable, per-backlog decision record", and REQ-DEC-02 requires audit fields (`decidedAt`, applied-when, applied-by-what) whose only purpose is auditability. But the PRD never says whether that record is git-tracked, and in this repo the answer is currently decided by accident: `forge.config.json` sets `backlogDir: null`, so the backlog resolves to `specs/loop-recovery/`, and OQ-2's proposed `{backlogDir}/{stateDir}/forge-decisions.json` therefore lands at `specs/loop-recovery/.rauf/forge-decisions.json` — matched by `.gitignore`'s deny-by-default `**/.rauf/*` rule (shipped as #195, cited in §6). Untracked, the record survives a session end (#196's core need) but not a clean checkout, a worktree switch, or `git clean -xdf`, and never appears in review — so "durable" and the audit fields are only half honored. Tracked (via a `!` negation), every mid-run decision write dirties the working tree, and the runner contract confirms collection happens *while the loop is still running* (`runner-contract.md:180`: "the loop is NOT paused"), so the write lands inside the window REQ-TREE-01 inspects and REQ-OUT-03 gates on "the working tree is clean". Either branch has a requirement-level consequence and the PRD picks neither. OQ-2 defers the file's *location and name*, not what durability and tree-cleanliness mean — a tech spec would have to invent the position.
- **Suggested fix:** Amend REQ-DEC-01 with one clause defining the durability scope — e.g. "durable means it survives session end and context clear; whether the record is committed to git is decided in the tech spec, but the PRD position is {tracked, for auditability | untracked, as run-local state}". Add a matching clause to REQ-OUT-03 stating whether forge's own state writes (the decision record among them) count toward the clean-tree gate, or extend OQ-2 to explicitly carry "and whether the record is git-tracked, given `.gitignore`'s `**/.rauf/*` deny-by-default rule". Do not specify a file layout here — record the position only.
- **References:** `.gitignore` (lines 1-10), `forge.config.json` (`backlogDir: null`), `skills/forge-4-backlog/SKILL.md:25`, `skills/forge-5-loop/references/runner-contract.md:178-184`, issue #196, issue #195
- **Checklist:** CHECK-P08, CHECK-P14

### V-002: REQ-TREE-02 requires per-item attribution of stranded work with no stated source of truth
- **Severity:** gap
- **Location:** PRD.md §3.2 REQ-TREE-02
- **Issue:** "Detected stranded work MUST be attributed to the backlog item(s) that produced it" is a P0 requirement, but nothing in the PRD says where that file→item mapping comes from. Git records no per-item provenance for an uncommitted index, and §5's "Runner scope" constraint enumerates the existing runner surfaces as `rauf backlog unblock`, `--retry-blocked`, and `backlogSummary` — none of which yields file attribution. So the requirement silently implies either a new rauf surface (which §5 permits but prices as "second repo, second release train" plus a `loopRunner.minRunnerVersion` bump) or a best-effort heuristic, and the tech spec has no basis to choose. Related and equally unstated: changes that belong to *no* item — forge's own state writes and runner artifacts — have no defined disposition, yet REQ-TREE-02's three exits (commit per item / stash / discard) all presuppose item ownership.
- **Suggested fix:** Add a Notes line under REQ-TREE-02 recording the attribution basis and its failure mode, e.g. "attribution is best-effort from {named source}; when a change cannot be attributed to an item, the unattributed set is presented as a single decision" — and state explicitly whether obtaining reliable attribution is allowed to require a rauf-side change (§5 already grants that permission conditionally, so the PRD only needs to say whether this requirement is one of the cases that spends it).
- **References:** PRD.md §5 "Runner scope", issue #192 ("attribute staged work to the items that produced it")
- **Checklist:** CHECK-P08, CHECK-P14

### V-003: REQ-UNB-02 and REQ-UNB-03 test different things, and partial unblocking has no defined outcome
- **Severity:** gap
- **Location:** PRD.md §3.3 REQ-UNB-02/-03, §3.4 REQ-OUT-03
- **Issue:** REQ-UNB-02 specifies a **per-item identity** test ("verify the affected items actually left `blocked`/`needsHuman`"). REQ-UNB-03 specifies an **aggregate count** test ("An unchanged blocked/needs-human count after a recovery pass MUST be treated and reported as a failed recovery"). These are not equivalent and diverge in both directions: if item 001 unblocks while item 007 newly blocks, the count is unchanged and REQ-UNB-03 declares a failure that REQ-UNB-02 would pass; conversely a count that moves for an unrelated reason satisfies REQ-UNB-03 while the affected items are still stuck. Separately, the **partial** case — 2 of 3 affected items move — is neither "unchanged" (so not a failed recovery) nor complete, and it directly gates the P0 resolved outcome: REQ-OUT-03 requires "the items have been unblocked with counts moved", which inherits the same ambiguity and adds a third phrasing. A tech spec must invent the semantics for the case that #191's own evidence (three items, one shared cause) makes most likely.
- **Suggested fix:** Make REQ-UNB-02's per-item identity test authoritative and restate REQ-UNB-03 in those terms — e.g. "recovery succeeds only when *every* affected item left `blocked`/`needsHuman`; any affected item still blocked is a failed recovery, reported with the items that did and did not move". Then align REQ-OUT-03's third precondition to the same per-item wording, replacing "with counts moved". Add a Notes line stating the partial case is a failed recovery (not a partial success) if that is the intent.
- **References:** issue #193 ("Treat an unchanged summary as a failed recovery"), issue #189 (outcome gating)
- **Checklist:** CHECK-P08, CHECK-P15

### V-004: REQ-CLU-01's "underlying-reason similarity" has no criterion, and unlike the other thresholds it is not deferred in §7
- **Severity:** gap
- **Location:** PRD.md §3.6 REQ-CLU-01, §7
- **Issue:** REQ-CLU-01 mandates that a "deterministic scripted helper produces candidate clusters (testable)" by clustering items "by underlying-reason similarity" — but nothing states what makes two reasons similar, so the promised acceptance test cannot be written. The PRD's own pattern is to park exactly this kind of undetermined parameter in §7 (OQ-3 defers REQ-TOPO-02's "large fraction" threshold for precisely this reason), and OQ-2 defers only *where the clustering assist lives*, not how it decides. This one falls through both. It matters because REQ-CLU-02's trigger ("any cluster of two or more items") and REQ-CLU-03's blast-radius framing are both downstream of the clustering decision.
- **Suggested fix:** Add **OQ-4** to §7: "the similarity criterion for REQ-CLU-01's candidate clustering — what makes two needs-human reasons the same underlying cause, and how the deterministic helper decides it (→ tech spec)." Optionally add a Notes line under REQ-CLU-01 recording the PRD-level constraint that already exists — the helper must be deterministic and its clusters agent-refinable — so the tech spec knows the bounds without the PRD picking an algorithm.
- **References:** PRD.md §7 OQ-2, OQ-3; issue #191 (three near-identical reasons)
- **Checklist:** CHECK-P08, CHECK-P04

### V-005: The "answer collected but the run is cancelled" path and the unblock-failure path have no requirement
- **Severity:** gap
- **Location:** PRD.md §3.1 REQ-DEC-01/-04, §3.3 REQ-UNB-01, §4.1 REQ-REL-02
- **Issue:** Two negative paths are unspecified.
  (a) The runner contract offers the agent *two* branches on `needs_human` (`runner-contract.md:182-184`): "(a) collect the user's answer ... to **stage a post-run retry**, or (b) offer to **cancel the run early** if the answer changes the whole plan". REQ-DEC-04 replaces the undefined phrase in branch (a) and the PRD never mentions branch (b) — yet REQ-DEC-01 requires persistence "the moment it is collected — before it is acted on", which on its face also fires on the cancel branch. Whether a cancelled run leaves a recorded-but-never-applied decision behind (and how REQ-DEC-05's "not yet applied" enumeration should treat it on the next launch) is undefined. The same hole covers an operator who declines or defers the REQ-CLU-02 consolidated decision.
  (b) REQ-REL-02 requires that a failed *decision-record write* be surfaced verbatim and never reported as recorded, but no requirement covers a failed **unblock operation** (REQ-UNB-01) — the runner erroring, or the surface being unavailable at `loopRunner.minRunnerVersion`. Since REQ-UNB-03 defines failure only in terms of counts not moving, an unblock that never ran and an unblock that ran and did nothing are currently indistinguishable.
- **Suggested fix:** Add REQ-DEC-06: "A decision collected on a path that does not proceed to a retry (run cancelled early, operator defers) is still recorded, marked unapplied, and surfaced by the REQ-DEC-05 enumeration on the next launch" — or state the opposite position explicitly. Generalize REQ-REL-02 to cover every scripted step this feature adds ("a failed decision-record write **or a failed unblock operation** MUST be surfaced verbatim and MUST NOT be reported as succeeded"), so REQ-UNB-01's failure is distinguishable from REQ-UNB-03's no-op.
- **References:** `skills/forge-5-loop/references/runner-contract.md:178-184`, PRD.md §5 "Runner scope", issue #196
- **Checklist:** CHECK-P14, CHECK-P08

### V-006: No security or data-handling position for the decision record, which persists operator free text
- **Severity:** gap
- **Location:** PRD.md §4 (no Security subsection)
- **Issue:** §4 covers Reliability, State integrity, Observability, and Compatibility but takes no security or data-sensitivity position, and this feature introduces the pipeline's first surface that persists **operator-authored free text** — REQ-DEC-02 requires storing the question, the answer, and an actor identity ("by what (session / actor)"). The template reserves a Security subsection and CHECK-P12 requires security requirements be explicit rather than assumed. Concretely unanswered: whether answers may contain sensitive content, whether the record is expected to be repo-visible or pushed (see V-001), and what "actor" identity is permitted to capture. This is a one-sentence position, not a design task — but leaving it blank means the tech spec chooses it silently while also choosing the file location.
- **Suggested fix:** Add §4.5 with a single requirement, e.g. "REQ-SEC-01: Decision records hold operator-authored free text and are treated as repo-visible, non-sensitive content; operators must not be prompted for secrets and the record captures no credential material. `appliedBy` identifies the session/actor only, not user identity. Priority: P0." If the position is instead "out of scope", state that explicitly — an explicit non-requirement is a complete answer.
- **References:** `skills/forge-1-prd/references/prd-template.md` §4.2, PRD.md §3.1 REQ-DEC-02, V-001
- **Checklist:** CHECK-P12, CHECK-P01

### V-007: Six non-functional requirements carry no priority
- **Severity:** gap
- **Location:** PRD.md §4.1-§4.4
- **Issue:** The PRD declares 33 requirement IDs but only 27 `Priority:` lines. Every §3 functional requirement has one; **none** of the six §4 requirements does — REQ-REL-01, REQ-REL-02, REQ-STATE-01, REQ-OBS-01, REQ-COMPAT-01, REQ-COMPAT-02. This matters beyond bookkeeping: §3's ordering note gives the backlog an explicit implementation sequence (DEC, TREE, UNB, OUT, ATTR, CLU, TOPO, EVAL) with P0/P1 driving it, and the unprioritized NFRs — including REQ-STATE-01, which constrains every new surface, and REQ-COMPAT-02, which is asserted as Success Criterion 4 — have no place in that ranking. forge-4-backlog will have to guess their weight.
- **Suggested fix:** Add a `- Priority: {P0|P1|P2}` line to each of the six §4 requirements, matching the §3 formatting. Suggested from the PRD's own text: REQ-REL-01 P0 (settled position), REQ-REL-02 P0 (mirrors the `state-*` exit-2 protocol), REQ-STATE-01 P0 (constrains every new surface, #181's lesson), REQ-OBS-01 P0 (generalizes P0 REQ-ATTR-03), REQ-COMPAT-01 P0 (guard integrity), REQ-COMPAT-02 P0 (asserted as SC 4). Confirm rather than assume these.
- **References:** PRD.md §3 ordering note, §8 SC 4
- **Checklist:** CHECK-P07

### V-008: REQ-TREE-01's post-run reconciliation contradicts REQ-COMPAT-02's "no new required steps on the happy path"
- **Severity:** inconsistency
- **Location:** PRD.md §3.2 REQ-TREE-01, §4.4 REQ-COMPAT-02, §8 SC 4
- **Issue:** REQ-TREE-01 requires that "**After a run ends** and before any outcome is selected, the loop stage MUST detect a dirty working tree / index" — unconditionally, on every run. REQ-COMPAT-02 states that "Runs that never hit needs-human/blocked states behave exactly as today (no new prompts, no new required steps on the happy path, **beyond the Step 2a depth line** of REQ-TOPO-03)", and SC 4 hardens that into a byte-equivalence claim. The two cannot both hold as written: reconciliation detection is a new required step on every run, and a happy-path run that nonetheless leaves a dirty tree (items done, artifacts uncommitted) now triggers REQ-TREE-02's required operator decision — a new prompt on a path REQ-COMPAT-02 declares unchanged. Issue #192 places the step at "Step 4c ... run before any outcome is selected", confirming the unconditional intent.
- **Suggested fix:** Amend REQ-COMPAT-02's exemption clause to name both new steps and scope the compat guarantee to observable output, e.g. "...no new prompts and no new required *operator decisions*, beyond the Step 2a depth line (REQ-TOPO-03); the REQ-TREE-01 detection step runs on every run but is silent on a clean tree, and REQ-TREE-02's decision fires only when the tree is dirty." Update SC 4's byte-equivalence wording to match (clean-tree happy path only).
- **References:** issue #192 ("Add a Step 4c tree reconciliation, run before any outcome is selected"), PRD.md §8 SC 4
- **Checklist:** CHECK-P15, CHECK-P08

### V-009: Record lifecycle is unspecified — re-decision on the same item, and retention across runs
- **Severity:** gap
- **Location:** PRD.md §3.1 REQ-DEC-02/-05, §3.6 REQ-CLU-04
- **Issue:** #196 proposes a record "**keyed by item id**", and the PRD carries that shape into REQ-DEC-02 (one record capturing item id, question, answer, decided/applied timestamps). Two lifecycle cases follow directly and have no requirement:
  (1) **Re-decision** — an item that goes needs-human a second time with a different question or a revised answer. Under per-item keying the second write either overwrites the first (destroying the audit trail that REQ-DEC-02's timestamp fields exist to provide) or the record must hold a sequence. REQ-DEC-05's "enumerate which recorded decisions are **not yet applied**" becomes ambiguous the moment an item has two.
  (2) **Retention** — the record is "per-backlog", but nothing says when it is pruned, archived, or reset. A record that accumulates across relaunches makes REQ-DEC-05's unapplied-set grow monotonically with stale entries; one that is reset per run loses exactly the cross-session durability REQ-DEC-01 exists to provide.
  REQ-CLU-04 compounds this by requiring "one record per affected item, or an equivalent that preserves per-item read-back" — several items sharing one answer — without saying whether those are independently re-decidable.
- **Suggested fix:** Add REQ-DEC-06 (or extend REQ-DEC-02) with the two positions: whether an item may hold more than one decision over time and what REQ-DEC-05 enumerates when it does (e.g. "records are append-only; the unapplied set is the latest undecided-or-unapplied entry per item"), and the record's lifetime (e.g. "the record persists for the life of the backlog and is never pruned automatically"). Record the position only — the on-disk shape belongs to OQ-2.
- **References:** issue #196 (`{itemId, question, answer, decidedAt, appliedAt, appliedBy}`), PRD.md §7 OQ-2
- **Checklist:** CHECK-P14, CHECK-P08

### V-010: Success Criterion 1's "replayed" has no stated vehicle and sits in tension with §6
- **Severity:** improvement
- **Location:** PRD.md §8 SC 1, §6
- **Issue:** SC 1 requires that "each issue's 'Observed in' scenario, **replayed**, now produces the required behavior". All seven Observed-in scenarios are the single `verify-test-debt` run of 2026-08-04, and §6 declares "Retroactively recovering the verify-test-debt run" out of scope, noting its backlog "was completed manually". So the literal artifact the criterion names cannot be re-run, and SC 1 names no substitute — no fixture backlog, no eval case, no synthetic topology. As written, SC 1 is the only success criterion that cannot be mechanically evaluated (SC 2, 3, and 4 all name a command or a comparison). This is not wrong, just under-specified: it costs one clause.
- **Suggested fix:** Name the replay vehicle in SC 1, e.g. "...replayed **against a fixture backlog reproducing that topology (3 roots, 13-deep chain, one shared blocking cause)**, now produces the required behavior". This also gives REQ-TOPO-01/-02 and REQ-ATTR-02 a concrete test substrate and dovetails with REQ-EVAL-01's fixture. Optionally add a parallel clause to SC 4 naming how byte-equivalence is measured (captured baseline output from a pre-change run).
- **References:** PRD.md §6 (final bullet), §3.8 REQ-EVAL-01, issue #194 (topology), issue #190 (dependency graph)
- **Checklist:** CHECK-P05

### V-011: §5 constraints do not distinguish mandates from preferences
- **Severity:** improvement
- **Location:** PRD.md §5
- **Issue:** CHECK-P13 asks that constraints separate must from should. §5's four bullets mix registers without marking them. "Runner scope" does it well and explicitly ("**prefer** existing runner surfaces ... rauf-side changes **ARE permitted** when..."). The other three are written in the indicative and their force must be inferred: "Body caps" states current line counts as facts ("`forge-verify` is at 299/300") and then asserts placement ("New prose lands in `references/` files", "The topology CHECK goes in a checklist file, **never** the forge-verify body") — the "never" reads as a hard mandate while the surrounding sentences read as description. "Canon/adapter discipline" lists three toolchain obligations as statements of fact. "Pipeline dogfood" is ambiguous between a mandate and an observation. A fresh agent at forge-2-tech has to guess which of these it may trade off.
- **Suggested fix:** Prefix each §5 bullet's operative clause with MUST or SHOULD. Suggested reading from the text itself: Body caps — MUST (300-line cap is hard; the topology CHECK MUST NOT land in the forge-verify body); Canon/adapter discipline — MUST (all three, enforced by parity tests); Runner scope — SHOULD prefer existing surfaces, with rauf changes permitted under the stated cost; Pipeline dogfood — MUST (the feature runs through the pipeline itself).
- **References:** PRD.md §5, `skills/forge-1-prd/references/prd-template.md` §5
- **Checklist:** CHECK-P13

### V-012: No non-functional requirement is quantified, including the one this feature adds to every run
- **Severity:** improvement
- **Location:** PRD.md §4, §3.7 REQ-TOPO-03
- **Issue:** CHECK-P11 asks that NFRs be quantified where applicable. §4 contains no number of any kind. Most of this is legitimately not applicable — a local CLI pipeline has no throughput or uptime target — but one case is genuinely quantifiable and lands on the happy path: REQ-TOPO-03 requires maximum chain depth be computed and surfaced at Step 2a on **every** run, which is a graph traversal over the whole backlog, and REQ-TOPO-01 adds root count and per-root fan-out at authoring time. REQ-COMPAT-02 promises behavioral equivalence on the happy path but says nothing about cost, so there is no bound on backlog size at which the new per-run computation becomes noticeable, and no acceptance target for it.
- **Suggested fix:** Add one bounded NFR, e.g. "REQ-PERF-01: Topology computation (root count, max chain depth, per-root fan-out) is linear in backlog size and adds no perceptible latency to Step 2a for backlogs up to {N} items; backlogs are expected to be well under {N}. Priority: P2." If the position is that cost is immaterial at realistic backlog sizes, state that instead — an explicit "not a concern at this scale" is a complete answer and closes the check.
- **References:** PRD.md §4.4 REQ-COMPAT-02, §3.7 REQ-TOPO-01/-03
- **Checklist:** CHECK-P11

### V-013: §2 introduces a third actor that §1 does not name
- **Severity:** improvement
- **Location:** PRD.md §1 ("Who has this problem"), §2
- **Issue:** §1 identifies exactly two affected parties: "the operator answering needs-human prompts, and the main agent driving `forge-5-loop`". §2's final story is written for a **backlog author** ("I want topology reported and fragile shapes warned about at authoring and verification time"), an actor §1 never introduces — even though §1's closing paragraph does describe the #194 problem. The story set itself is complete (four operator stories, two main-agent stories, one backlog-author story, covering all seven source issues), so this is a one-line inconsistency in the problem statement rather than missing coverage.
- **Suggested fix:** Extend §1's "Who has this problem" sentence to name the third actor, e.g. "...and the backlog author at `forge-4-backlog`, whose fragile topologies pass both authoring and verification without comment (#194)."
- **References:** PRD.md §2 (final bullet), §3.7, issue #194
- **Checklist:** CHECK-P10

## Fix Execution Plan

### User Decisions Required
Five findings record a **position** the PRD does not currently hold. A fresh agent should not invent these — surface each to the user as a short either/or and write the chosen answer. Do not design mechanisms for any of them.

1. **V-001** — RESOLVED (2026-08-05): untracked run-local state. Durable = survives session end and context clear; not expected to survive a fresh clone; keeps the #195 direction and never dirties the clean-tree gates.
2. **V-002** — RESOLVED (2026-08-05): best-effort attribution from runner-native evidence with an unattributed-set fallback presented as one consolidated decision; the §5 rauf permission is not spent by REQ-TREE-02.
3. **V-003** — RESOLVED (2026-08-05): per-item test authoritative; partial unblock is a failed recovery, reported with the items that did and did not move.
4. **V-005** — RESOLVED (2026-08-05): always recorded — the cancel/defer branches persist the decision, marked unapplied, re-surfaced by REQ-DEC-05 on the next launch.
5. **V-006** — RESOLVED (2026-08-05): non-sensitive position stated as REQ-SEC-01 (no secrets solicited, no credential material, actor field is session/actor only).
6. **V-007 priorities** — RESOLVED (2026-08-05): all six §4 NFRs confirmed P0 (REQ-PERF-01, added by V-012's fix, is P2).

All other steps were mechanical and applied directly.

### Execution Steps

#### Step 1: Add missing priorities to §4
- **Files:** `specs/loop-recovery/PRD.md`
- **Addresses:** V-007
- **Action:** Add a `  - Priority: {P}` line under each of REQ-REL-01, REQ-REL-02, REQ-STATE-01, REQ-OBS-01, REQ-COMPAT-01, REQ-COMPAT-02, matching §3's two-space-indent formatting. Use the values proposed in V-007 (all P0) unless the user directs otherwise. Verify afterward that the `Priority:` line count equals the unique `REQ-` ID count (33).
- **Depends on:** none

#### Step 2: Resolve the REQ-UNB / REQ-OUT test semantics
- **Files:** `specs/loop-recovery/PRD.md` (§3.3, §3.4)
- **Addresses:** V-003
- **Action:** Restate REQ-UNB-03 in REQ-UNB-02's per-item identity terms and replace REQ-OUT-03's "with counts moved" with the same wording, so one test governs all three requirements. Record the user's partial-unblock decision (User Decision 3) as a Notes line under REQ-UNB-03.
- **Depends on:** User Decision 3

#### Step 3: Close the REQ-TREE / REQ-COMPAT contradiction
- **Files:** `specs/loop-recovery/PRD.md` (§4.4, §8)
- **Addresses:** V-008
- **Action:** Amend REQ-COMPAT-02's exemption clause per V-008's suggested wording — detection runs always and is silent on a clean tree; the operator decision fires only on a dirty tree — and scope SC 4's byte-equivalence claim to the clean-tree happy path.
- **Depends on:** none

#### Step 4: Record the decision-record positions (durability, lifecycle, security, cancel path)
- **Files:** `specs/loop-recovery/PRD.md` (§3.1, §3.4, §4, §7)
- **Addresses:** V-001, V-005, V-006, V-009
- **Action:** Apply the user's answers to Decisions 1, 4, and 5. Specifically: add the durability clause to REQ-DEC-01 and the corresponding clean-tree clause to REQ-OUT-03 (V-001); add REQ-DEC-06 covering the cancel/decline path (V-005) and the re-decision + retention lifecycle (V-009), or fold both into REQ-DEC-02/-05 as Notes; generalize REQ-REL-02 to cover a failed unblock operation (V-005b); add §4.5 with REQ-SEC-01 (V-006). Extend §7 OQ-2 to carry the git-tracking question alongside the file location. Do not specify a file layout, schema, or algorithm anywhere in this step.
- **Depends on:** User Decisions 1, 4, 5; Step 1 (so the new requirements are written with priorities from the outset)

#### Step 5: Record the attribution basis for REQ-TREE-02
- **Files:** `specs/loop-recovery/PRD.md` (§3.2, and §5 "Runner scope" if the user permits a rauf change)
- **Addresses:** V-002
- **Action:** Add a Notes line under REQ-TREE-02 naming the attribution source and the unattributable-changes fallback per User Decision 2. If a rauf-side surface is sanctioned, note it in §5's "Runner scope" bullet as an accepted instance of the permission that bullet already grants.
- **Depends on:** User Decision 2

#### Step 6: Add OQ-4 for the clustering similarity criterion
- **Files:** `specs/loop-recovery/PRD.md` (§7, §3.6)
- **Addresses:** V-004
- **Action:** Append OQ-4 to §7 using V-004's wording, deferring the REQ-CLU-01 similarity criterion to the tech spec. Do not choose an algorithm or threshold in the PRD.
- **Depends on:** none

#### Step 7: Editorial pass — actors, constraints, success criteria, performance
- **Files:** `specs/loop-recovery/PRD.md` (§1, §2, §4, §5, §8)
- **Addresses:** V-010, V-011, V-012, V-013
- **Action:** (a) Add the backlog-author actor to §1's "Who has this problem" sentence. (b) Prefix each §5 bullet's operative clause with MUST/SHOULD per V-011's suggested reading. (c) Name the fixture-backlog replay vehicle in SC 1 and the baseline-capture method in SC 4. (d) Add REQ-PERF-01 (P2) bounding topology-computation cost, or an explicit "not a concern at realistic backlog sizes" position.
- **Depends on:** Step 3 (SC 4 is touched by both — apply Step 3's scoping first, then this step's measurement clause)

## Fix Progress
- Step 1: [APPLIED] 2026-08-05 — priorities added to all six §4 NFRs (all P0 per resolved V-007).
- Step 2: [APPLIED] 2026-08-05 — REQ-UNB-02/-03 restated on the per-item identity test; partial = failed recovery (Notes line); REQ-OUT-03's third precondition aligned to the same wording.
- Step 3: [APPLIED] 2026-08-05 — REQ-COMPAT-02 exemption clause rewritten (detection always runs, silent on clean tree; decision fires only on dirty tree); SC 4 scoped to the clean-tree happy path.
- Step 4: [APPLIED] 2026-08-05 — REQ-DEC-01 durability note (untracked run-local); REQ-OUT-03 clean-tree clause excluding untracked runner-state artifacts; REQ-DEC-06 (cancel/defer path) and REQ-DEC-07 (append-only re-decision + retention) added; REQ-REL-02 generalized to failed unblock operations; §4.5 REQ-SEC-01 added; OQ-2 annotated with the settled tracking position.
- Step 5: [APPLIED] 2026-08-05 — REQ-TREE-02 Notes line: best-effort runner-native attribution, unattributed-set fallback, §5 permission not spent.
- Step 6: [APPLIED] 2026-08-05 — OQ-4 (clustering similarity criterion) added to §7; REQ-CLU-01 Notes line bounding the deferral.
- Step 7: [APPLIED] 2026-08-05 — backlog-author actor added to §1; §5 bullets marked MUST/SHOULD; SC 1 names the fixture-backlog replay vehicle; SC 4 names the captured-baseline measurement; §4.6 REQ-PERF-01 (P2) added.
