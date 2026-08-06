# loop-recovery — Technical Specification

## 1. Overview

loop-recovery makes forge-5-loop's needs-human recovery real: decisions persist to a
scripted, schema-backed record the moment they are collected; a named recovery procedure
applies them through a first-class runner surface and proves, per item, that the affected
items left `blocked`/`needsHuman`; stranded working trees are reconciled as a required
step; a new `resolved` outcome routes the operator to a fenced relaunch; pending items
are attributed truthfully (dependency starvation vs. iteration limit); systemic causes
are consolidated into one blast-radius-framed prompt; and fragile backlog topologies are
reported and warned about before the loop ever runs.

Key architectural decisions (each detailed in §3):

| # | Decision | Choice |
|---|----------|--------|
| D1 | Decision-record location (OQ-2) | `{backlogDir}/{stateDir}/forge-decisions.json` — default `specs/{feature}/.rauf/forge-decisions.json`, gitignored by the existing `**/.rauf/*` rule (#195) |
| D2 | Decision-record surface | New `decision-*` verb family in `scripts/forge-session.py`, full R4 trio (schema + verbs + stdlib conformance test) |
| D3 | Outcome vocabulary (OQ-1) | One new `LoopOutcome` value `resolved` (routes **resume**); starvation is a **cause annotation** on the existing `partial`, not a new enum value |
| D4 | Apply mechanism | New rauf subcommand `rauf backlog answer` — the apply-only twin of `resume --answer` (rauf-side change, pre-authorized by PRD §5) |
| D5 | Recovery prose home | New `skills/forge-5-loop/references/recovery-procedure.md`; body edits are one-line pointers only |
| D6 | Topology warn thresholds (OQ-3) | Fixed constants, no config knob: warn when any single root gates ≥50% of items OR max chain depth ≥50% of item count |
| D7 | Clustering criterion (OQ-4) | Normalized token-set Jaccard ≥ 0.5 with union-find, flat function in `forge-session.py` |
| D8 | Version floor / eval | `minRunnerVersion` stays 0.6.0 — recovery capability-gates on a probed version at apply time; REQ-EVAL-01 lands as a new lightweight compliance-eval probe |

## 2. Module Structure

No new packages. All forge-side code lands in existing canonical surfaces (canon → adapters
fan-out via `scripts/build-adapters.py`; every canon edit regenerates `adapters/`).

**feature-forge repo (canon):**

```
scripts/forge-session.py                 # decision-* verbs, backlog-topology verb,
                                         #   cluster helper, LoopOutcome += "resolved",
                                         #   route/text tables, stage-exit --cause
references/forge-decisions-schema.json   # NEW — decision-record JSON schema
skills/forge-5-loop/SKILL.md             # pointer-only edits (293/300 → ≤300)
skills/forge-5-loop/references/
  recovery-procedure.md                  # NEW — the named Post-Run Recovery Procedure
  result-reporting.md                    # ladder += resolved; starvation-conditional
                                         #   pending template; starved next-steps note
  runner-contract.md                     # :183 "stage a post-run retry" → named pointer
references/ralph-loop-contract.md        # :61 "follow-up retry pass" → named pointer
skills/forge-4-backlog/SKILL.md          # topology report step (Step 5/6 slot)
skills/forge-verify/references/verification-checklists/backlog.md   # CHECK-B28
skills/forge-verify/SKILL.md             # "backlog: 27 checks" → 28 (in-line edit)
eval/run-compliance-eval.py              # NEW probe: loop-outcome
eval/fixtures/compliance/loop-outcome-resolved.json                 # NEW fixture
tests/_state_schema.py                   # += validate_decisions() entry point
tests/test_forge_decisions_schema.py     # NEW — structural schema tests
tests/test_decisions_schema_conformance.py  # NEW — R4 drift guard for decision-*
tests/test_backlog_topology.py           # NEW — topology metrics + warn thresholds
tests/test_decision_clustering.py        # NEW — Jaccard clustering unit tests
tests/test_stage_exit.py                 # mirrored EXIT_OUTCOMES += resolved; routing
adapters/                                # regenerated (never hand-edited)
```

**rauf repo (separate release train):**

```
packages/cli/src/backlog-commands.ts     # NEW subcommand: rauf backlog answer
packages/cli (tests)                     # subcommand unit tests
```

Public API surface added (forge-side, all via `forge-session.py` argparse subcommands):
`decision-record`, `decision-list`, `decision-apply`, `backlog-topology`, plus the
`--cause` option on `stage-exit` (forge-5-loop only).

## 3. Technical Decisions

### 3.1 Decision record: location and R4 surface (REQ-DEC-01..07, REQ-STATE-01, REQ-SEC-01) — D1, D2

The record lives at `{resolvedBacklogDir}/{stateDir}/forge-decisions.json`, where
`stateDir` is `loopRunner.stateDir` (default `.rauf`) from effective config. For a default
feature this resolves to `specs/{feature}/.rauf/forge-decisions.json`, which the existing
deny-by-default ignore block (`**/.rauf/*`, #195) already covers — **zero `.gitignore`
edits**, satisfying REQ-DEC-01's untracked-and-git-ignored durability note (advisory
V-015 discharged by construction). The location is documented runner-agnostically as
"under `loopRunner.stateDir`" per `references/ralph-loop-contract.md`'s state-dir
contract surface; `.rauf` is only the default binding.

The surface follows the R4 pattern exactly (REQ-STATE-01):
- **Schema**: `references/forge-decisions-schema.json` (§4), draft-07 subset compatible
  with `tests/_state_schema.py`'s stdlib validator (`type`, `required`, `properties`,
  `enum`, `items`, `additionalProperties: false`, `$ref` to `#/definitions/*`).
- **Verb writers**: `decision-record` / `decision-list` / `decision-apply` in
  `forge-session.py` (§5.1), atomic via the `_write_state` mkstemp→fsync→`os.replace`
  pattern (the `_commit_state` helper is target-agnostic and is reused with the
  decisions path), strict 0/2 exit codes, `Error:` line on stderr via `UsageError`.
- **Conformance test**: `tests/test_decisions_schema_conformance.py`, cloning
  `test_state_schema_conformance.py`'s structure including its registry-completeness
  guard — a regex scan for `add_parser("decision-…")` asserting every registered
  `decision-*` verb appears in the test's `VERB_INVOCATIONS`.

Naming note: the family is `decision-*`, **not** `state-decision-*` — a `state-decision`
verb already exists and writes `deferredDecisions[]` into `.pipeline-state.json` (a
different, pipeline-level concept). The distinct prefix keeps the existing `state-`
registry guard untouched and unambiguous.

Records are **append-only** (REQ-DEC-07): a later decision for the same item appends a
new entry; no entry is ever mutated except `decision-apply` stamping `appliedAt`/
`appliedBy` on the latest entry for an item. The REQ-DEC-05 unapplied set is *the latest
entry per item that is not applied* (`appliedAt == null`), which also covers deferred
entries (REQ-DEC-06: deferral records an entry with `answer: null`, `deferred: true`).
No automatic pruning; the file persists for the life of the backlog.

Security (REQ-SEC-01): prompts in the recovery procedure explicitly instruct never to
solicit secrets; the schema has no credential-shaped fields; `recordedBy`/`appliedBy`
capture a session/actor label only (e.g. `forge-5-loop@claude`), never user identity.

### 3.2 Outcome vocabulary: `resolved` + starvation cause (REQ-OUT-01..03, REQ-ATTR-01..04, REQ-COMPAT-01) — D3

One new enum value. `LoopOutcome` (`forge-session.py:374`) becomes:

```python
LoopOutcome = Literal["complete", "partial", "blocked", "needs-human", "deferred", "resolved"]
```

`EXIT_OUTCOMES["forge-5-loop"]` derives automatically. Routing and text:

- `_LOOP_ROUTE_KIND["resolved"] = "resume"` (REQ-OUT-02) — the NEXT-STEPS block fences
  the relaunch command (`/feature-forge:forge-5-loop {feature}`), exactly like
  `partial`/`deferred`, never the navigator.
- `_LOOP_OUTCOME_TEXT["resolved"]` — new prose: the needs-human stop was resolved
  (decisions recorded and applied, affected items verified unblocked per item, tree
  clean); relaunch to continue.
- `resolved` joins the non-complete bucket in `_loop_route()`: no `nextStage`, no
  auto-verify debt, no downstream-readiness claims (mirrors
  `test_no_non_complete_loop_outcome_claims_downstream_readiness`).

**Gate (REQ-OUT-03).** `resolved` is selected *procedurally* by the Post-Run Recovery
Procedure (§3.4), and only when all three hold: (a) `decision-list --unapplied` is empty
for the affected items, (b) `git status --porcelain` is clean (untracked stateDir
artifacts are gitignored and therefore invisible to porcelain — the clean-tree exclusion
in REQ-OUT-03 holds by construction), (c) the per-item re-read (§3.3) shows every
affected item left `blocked`/`needsHuman`. `stage-exit` does not re-verify the gate
server-side (it has no runner access); enforcement is procedural + eval-measured
(§3.8) + directive-matrix-tested (REQ-COMPAT-01). Recorded as OTQ-1 in §10.

**Ladder position** (`result-reporting.md`): `resolved` is evaluated **before**
`needs-human` — first rung, gated on "the recovery procedure ran this session and its
gate passed". A resolved stop must not re-trigger the needs-human branch its own
recovery just cleared. New ladder: `resolved` → `needs-human` → `blocked` → `deferred`
→ `partial` → `complete`.

**Starvation is an annotation, not an enum value** (REQ-ATTR-04 / OQ-1). Both
`partial-starved` and `partial` would route identically (resume); a distinct value buys
only text at the cost of doubling the enum/routing/test/eval ripple. Instead:

- `selectable` (REQ-ATTR-01) = pending items whose `dependsOn` are all `done`, computed
  by the `backlog-topology` verb (§5.2) from the runner's `listCommand` JSON.
- When `selectable == 0 && pending > 0 && iterationsUsed < iterationsGranted`, the
  report renders dependency starvation: the blocking roots and the gated-subtree size of
  each (REQ-ATTR-02), sourced from the same verb output.
- `stage-exit --stage forge-5-loop --outcome partial` gains an optional
  `--cause dependency-starvation` flag; when present, the `partial` outcome sentence in
  `_LOOP_OUTCOME_TEXT` is replaced by a starvation variant naming the unblock path.
  Absent flag = today's text. The flag is rejected (exit 2) for any other stage/outcome.
- The three canonical "(iteration limit reached)" occurrences
  (`result-reporting.md:67,71`; `SKILL.md:232`) become conditional: the pending template
  renders `({cause})` where cause is "iteration limit reached" **only if**
  `iteration == maxIterations` in the runner's status (the limit was binding) and
  `selectable > 0`; otherwise the starvation line renders (REQ-ATTR-03, REQ-OBS-01 —
  the template cites `backlogSummary` + topology counts it derived the claim from).

### 3.3 Recovery must unblock — apply mechanism (REQ-UNB-01..03, REQ-DEC-04/05, REQ-REL-02) — D4, D8

**New rauf surface** (PRD §5 pre-authorization spent here, deliberately):
`rauf backlog answer <path> <id> "<text>" [--backlog <dir>] [--json]` — the apply-only
twin of `resume --answer`'s injection block (`resume-commands.ts:301-313`):

```ts
updateItem(paths, itemId, {
  humanAnswer: text, status: "pending", needsHuman: false, blockedReason: null,
})
```

with **no relaunch**. Requires the item's current status to be `blocked` (exit non-zero
otherwise; `blocked → pending` is already a legal transition in
`VALID_STATUS_TRANSITIONS`). JSON output: `{ answered: "<id>", status: "pending" }`.
This reuses the existing first-class channel end-to-end: `humanAnswer` is threaded into
the next iteration's prompt as the "Human's Answer" section (`prompt-builder.ts:217`)
and auto-cleared when the item completes (`backlog.ts:254-259`). Ships in the next rauf
minor (assumed **0.14.0** — OTQ-2).

**Version gating (D8).** `loopRunner.minRunnerVersion` stays `0.6.0`. A new forge-side
constant `RECOVERY_MIN_RUNNER_VERSION = "0.14.0"` gates only the apply step: the
recovery procedure probes `versionCommand` (`rauf version --json` → `{version}`) before
applying; a runner below the threshold fails the recovery honestly per REQ-REL-02 —
verbatim error, upgrade hint (`installHint` pin), no claim of success. rauf itself has
no capability-negotiation surface (flat `{version}` only), so the compare is forge-side
semver, mirroring the existing forge-4/forge-5 floor checks.

**The unblock proof (REQ-UNB-02/03).** After every apply, the procedure re-reads
per-item state via `listCommand` (`rauf backlog list . --backlog {dir} --json`) and
tests **each** affected item: `status != "blocked"` (which, per rauf's derivation,
also removes it from `needsHuman` — that count is defined as
`status=="blocked" && needsHuman==true`). Aggregate `backlogSummary` counts are never
the test. Any affected item still `blocked` — including a partial move — is a **failed
recovery**, reported naming movers and non-movers. `rauf backlog unblock` remains the
surface for plain (non-needs-human) blocked items: same per-item proof applies.

REQ-REL-02 mirror of the `state-*` exit-2 protocol: any failed `decision-*` write, any
`backlog answer`/`unblock` non-zero exit, and any unparseable read-back is surfaced
verbatim and stops the procedure; a failed apply is distinguishable from
ran-but-nothing-moved because the former never reaches the per-item test.

### 3.4 The named recovery procedure (REQ-DEC-04..06, REQ-CLU-01..04) — D5

New reference: `skills/forge-5-loop/references/recovery-procedure.md` — the **Post-Run
Recovery Procedure**. Contents (authored at forge-3-specs granularity, summarized here):

1. **Enumerate** — `decision-list --unapplied` (REQ-DEC-05); if empty and nothing is
   blocked, exit (nothing to recover).
2. **Cluster** — run the clustering assist (§3.6) over blocked/needs-human items; agent
   may merge/refine candidate clusters by judgment (REQ-CLU-01).
3. **Consolidated prompts** — one `AskUserQuestion` per cluster of ≥2, naming every
   affected item and the full gated subtree, framed by blast radius ("gates 13/16
   items") from topology output (REQ-CLU-02/03). Singleton clusters prompt per item.
4. **Record at collection** — `decision-record` immediately on every branch: answered,
   deferred, and cancel-early all write entries before anything acts on them
   (REQ-DEC-01/06). Consolidated answers write one entry per affected item sharing a
   `clusterId` (REQ-CLU-04); items stay independently re-decidable (REQ-DEC-07).
5. **Apply** — version-gate probe, then `rauf backlog answer` per needs-human item /
   `rauf backlog unblock` per plain blocked item; `decision-apply` stamps each record
   only after its runner apply succeeded (REQ-UNB-01).
6. **Prove** — the per-item re-read test (§3.3). All moved → proceed; any non-mover →
   failed recovery report.
7. **Gate & exit** — evaluate the `resolved` gate (§3.2); on pass, Step 7 selects
   `resolved`; otherwise the ladder falls through to `needs-human`/`blocked` as today.

Pointer edits (REQ-DEC-04): `runner-contract.md:183` replaces "stage a post-run retry"
with "record the answer via `decision-record` **now**, then run the Post-Run Recovery
Procedure (`references/recovery-procedure.md`) after the run ends";
`ralph-loop-contract.md:61`'s "resolution is a follow-up retry pass" gains the same
named pointer. The live-event path (React-to-events) thus records decisions at the
moment of collection even mid-run, before recovery ever starts.

The procedure is also the re-entry point on a **fresh session/next launch**: unapplied
decisions from a previous session are enumerated by step 1 and re-surfaced (REQ-DEC-06)
— this is what makes a decision survive session end.

### 3.5 Post-run tree reconciliation (REQ-TREE-01..04, REQ-COMPAT-02)

A required section of `recovery-procedure.md`, invoked after the run ends and before
Step 7 selects any outcome (also invoked when recovery runs without needs-human items —
it is the tree half of "recovery"):

1. **Detect** — `git status --porcelain`. Empty → silent, no prompt (REQ-COMPAT-02).
   The decision record and all runner state are gitignored and never appear here
   (REQ-DEC-01 note).
2. **Attribute (best-effort, runner-native)** — read `{stateDir}/state.json`
   (`baseCommitHash`, `completedItems`, `blockedItems`, `currentItem`) and
   `{stateDir}/events.ndjson` (per-iteration `item_selected`/`llm_spawned`/`llm_exited`
   `itemId` + timestamps) to name which items ran during the window. Attribution maps
   dirty paths to candidate items by run evidence (items in flight when the run died,
   `git log {baseCommitHash}..HEAD` for what was already committed); it is presented as
   candidates, never asserted. No rauf change is spent here (REQ-TREE-02 note); parse
   failures degrade to the unattributed path, never abort detection.
3. **Decide** — one `AskUserQuestion` per attributed item-group: commit for that item /
   stash / discard; everything unattributable is presented as **one** consolidated
   decision. Discard is never a default and requires its own explicit confirmation
   (REQ-TREE-03).
4. **Launch blocker** — forge-5-loop's existing pre-flight dirty-tree check is extended
   (one-line pointer in the body; prose in `recovery-procedure.md`): when the tree is
   dirty **and** `{stateDir}/state.json` exists from a previous run, the precondition
   failure names that run (`startedAt`, in-flight item ids) and routes to the
   reconciliation section instead of the generic "uncommitted changes" message
   (REQ-TREE-04).

### 3.6 Systemic-cause clustering (REQ-CLU-01, REQ-PERF-01) — D7

Flat function in `forge-session.py` (per the `rank-features`/`reconcile-branch`
precedent), exposed for the procedure via the `backlog-topology` verb's `--cluster`
output section (§5.2):

- **Input**: items with `status == "blocked"` (needs-human and plain), each with
  `blockedReason` (where rauf lands the `RAUF_NEEDS_HUMAN:<reason>` question text).
- **Normalize**: lowercase; split on non-alphanumeric; drop pure-number tokens and
  item-id-shaped tokens (`^\d+$`, `^[a-z]*\d+$`); the token *set* (not bag).
- **Cluster**: union-find over pairs with Jaccard(setA, setB) ≥ 0.5 (constant
  `CLUSTER_JACCARD_THRESHOLD = 0.5`). Deterministic: items processed in id order,
  clusters emitted sorted by lowest member id; ties never depend on hash order.
- **Output per cluster**: member ids, member reasons, the shared token core, and the
  union of the members' gated subtrees (ids + count) for blast-radius framing.

O(k²) pairwise over blocked items only (k ≪ n; observed corpus 16 total) plus the
linear topology pass — comfortably within REQ-PERF-01. The helper is the *substrate*;
the agent may merge clusters it judges to share a cause (under-clustering is recoverable
by judgment; the scripted floor is what's testable).

### 3.7 Topology computation and its three consumers (REQ-TOPO-01..03, REQ-PERF-01) — D6

One pure function `compute_topology(items)` in `forge-session.py`, linear via memoized
DFS over `dependsOn` edges (cycle-safe: rauf validation has already rejected cycles;
the function still guards with a visited set):

- **Metrics**: `rootCount`; per-root `gatedCount` (+ ids) where "gates" = items
  transitively depending on the root; `maxChainDepth`; `itemCount`; and the
  status-aware `selectable` count (§3.2).
- **Warn triggers** (advisory, fixed constants `TOPOLOGY_FANOUT_WARN_RATIO = 0.5`,
  `TOPOLOGY_DEPTH_WARN_RATIO = 0.5`): any single root's `gatedCount ≥ 50%` of
  `itemCount`, or `maxChainDepth ≥ 50%` of `itemCount`. The observed incident (roots
  gating 81%, depth 13/16) trips both. No config knob (zero-prompt-config direction).

Consumers:
1. **forge-4-backlog** (REQ-TOPO-01): a topology-report step in the Step 5/6 slot
   (~100 lines of body headroom) — always reports the metrics after validation
   succeeds; renders the warning when a trigger fires.
2. **forge-verify** (REQ-TOPO-02): new **CHECK-B28** in
   `references/verification-checklists/backlog.md`, modeled on CHECK-B26/B27's
   advisory-heuristic template: severity `improvement` (never `error`/`gap`, never
   blocking), `not-applicable` when no trigger fires or the graph is trivial. Body edit
   = the expected-count bump "backlog: 27 checks" → "28" (in-line character change,
   zero line growth against the 298/300 body).
3. **forge-5-loop Step 2a** (REQ-TOPO-03): one added line — surface `maxChainDepth`
   beside the computed iteration count ("depth bounds achievable progress regardless of
   iteration budget"). This line renders on every run and is the only new happy-path
   output (REQ-COMPAT-02).

### 3.8 Eval coverage (REQ-EVAL-01) — D8

New lightweight probe `loop-outcome` in `eval/run-compliance-eval.py` plus fixture
`eval/fixtures/compliance/loop-outcome-resolved.json` (schemaVersion-2 shape mirroring
the existing compliance fixtures): drive a forge-5-loop close with `--outcome resolved`
and score (a) exactly one sentinel (`─ forge: end of stage ─`), (b) nothing after it,
(c) the primary command is the fenced relaunch `/feature-forge:forge-5-loop {feature}`.
The branch-path probe is left untouched — its verify/fix/re-verify shape stays
hardwired; generalizing it is out of scope for a sentinel-presence requirement.

## 4. Data Model

`references/forge-decisions-schema.json` (draft-07 subset per `_state_schema.py`):

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "forge-decisions",
  "type": "object",
  "additionalProperties": false,
  "required": ["schemaVersion", "feature", "createdAt", "updatedAt", "decisions"],
  "properties": {
    "schemaVersion": { "type": "string", "enum": ["1"] },
    "feature":       { "type": "string" },
    "createdAt":     { "type": "string" },
    "updatedAt":     { "type": "string" },
    "decisions":     { "type": "array", "items": { "$ref": "#/definitions/decision" } }
  },
  "definitions": {
    "decision": {
      "type": "object",
      "additionalProperties": false,
      "required": ["itemId", "question", "answer", "deferred", "decidedAt",
                   "recordedBy", "appliedAt", "appliedBy"],
      "properties": {
        "itemId":     { "type": "string" },
        "question":   { "type": "string" },
        "answer":     { "type": ["string", "null"] },
        "deferred":   { "type": "boolean" },
        "clusterId":  { "type": "string" },
        "decidedAt":  { "type": "string" },
        "recordedBy": { "type": "string" },
        "appliedAt":  { "type": ["string", "null"] },
        "appliedBy":  { "type": ["string", "null"] }
      }
    }
  }
}
```

Semantics (REQ-DEC-02/06/07): `answer: null` + `deferred: true` records a deferral;
`appliedAt: null` marks unapplied; `clusterId` (optional) links entries born from one
consolidated decision; timestamps are `_now_iso()` Z-suffixed UTC; `recordedBy`/
`appliedBy` are session/actor labels only (REQ-SEC-01). Append-only: `decision-apply`
touches only the latest entry for an item, and only its `appliedAt`/`appliedBy` fields.

Storage: single JSON file, atomic write-then-rename, single-writer assumption
(REQ-REL-01 — no locking, by standing #180 direction). Concurrent sessions are out of
scope; an interrupted write can never corrupt (temp-file + `os.replace`).

## 5. API Design

### 5.1 `decision-*` verbs (forge-session.py)

All: `--backlog-dir <path>` (the resolved backlog dir, e.g. `specs/loop-recovery`),
optional `--state-dir <name>` (default: effective-config `loopRunner.stateDir`, `.rauf`),
`--json`, exit 0/2, `Error:` on stderr.

```
decision-record --backlog-dir D --item ID [--item ID …] --question Q
                (--answer A | --deferred) [--cluster CID] [--actor LABEL]
    # appends one entry per --item; creates the file (and feature stamp) on first write
decision-list   --backlog-dir D [--unapplied] --json
    # full record, or the REQ-DEC-05 set: latest-entry-per-item where appliedAt==null
decision-apply  --backlog-dir D --item ID [--actor LABEL]
    # stamps appliedAt/appliedBy on the latest entry for ID; exit 2 if none unapplied
```

### 5.2 `backlog-topology` verb (forge-session.py)

```
backlog-topology --backlog-file <path/to/backlog.json> [--cluster] --json
```

Output: `{ itemCount, rootCount, roots: [{id, gatedCount, gatedIds}], maxChainDepth,
selectable, starvation: {starved, blockingRoots: [{id, gatedCount}]} | null,
warnings: ["single-root-fanout", "chain-depth"]…, clusters: […] }` — `clusters` only
with `--cluster` (§3.6 shape). Reads the backlog file directly (statuses included), so
one call serves forge-4-backlog, CHECK-B28 (read-only for the verifier), forge-5-loop
Step 2a, the starvation report, and the consolidated-prompt blast radius.

### 5.3 `stage-exit` extension

`--cause dependency-starvation` — valid only with `--stage forge-5-loop
--outcome partial`; any other combination exits 2 before output. Swaps the partial
outcome sentence for the starvation variant (§3.2).

### 5.4 rauf: `backlog answer`

`rauf backlog answer <path> <id> "<text>" [--backlog <dir>] [--json]` — §3.3. Exit 0 on
success; non-zero with a message when the item is missing or not `blocked`.

## 6. Integration Points

Existing surfaces this feature **depends on** (all verified from source):

| Surface | Location | Contract used |
|---|---|---|
| `_write_state`/`_commit_state` | `forge-session.py:4097,4388` | atomic write; `_commit_state` is target-agnostic (stamps `updatedAt`, writes any document) |
| `UsageError`/exit-2 protocol | `forge-session.py:682`, `main()` tail | 0/2 only; `Error:` prefix via `_ErrorPrefixParser` |
| `_now_iso()` | `forge-session.py:4083` | Z-suffixed UTC timestamps |
| `LoopOutcome`/`EXIT_OUTCOMES` | `forge-session.py:374,398` | derived enum — single edit point |
| `_LOOP_ROUTE_KIND`/`_LOOP_OUTCOME_TEXT`/`_loop_route()` | `forge-session.py:2952,2964,3117` | route/text tables + resume/recover dispatcher |
| stdlib validator | `tests/_state_schema.py` | `_check()` is schema-generic; add `validate_decisions()` (two-line entry point) |
| R4 guard template | `tests/test_state_schema_conformance.py` | out-of-process `_run()`, `VERB_INVOCATIONS`, registry-completeness regex |
| gitignore rule | `.gitignore` (`**/.rauf/*`, #195) | covers the decision record with no edit |
| `loopRunner` config | `references/forge-config-schema.json` | `stateDir` (default `.rauf`), `versionCommand`, `listCommand`, `statusJsonCommand`, `installHint`, `minRunnerVersion` (stays 0.6.0) |
| rauf `updateItem` | `packages/core/src/backlog.ts:245` | `humanAnswer` set path + `blocked→pending` transition legality |
| rauf `humanAnswer` threading | `packages/loop/src/prompt-builder.ts:217`; auto-clear `backlog.ts:254-259` | answer reaches the iteration prompt; cleared on completion |
| rauf per-item read-back | `rauf backlog list . --json` (`BacklogItem[]`: `status`, `needsHuman`, `blockedReason`, `humanAnswer`, `dependsOn`) | the REQ-UNB-02 per-item test |
| rauf aggregate counts | `rauf status . --json` → `backlogSummary` (`needsHuman` = blocked ∧ needsHuman) | report counts only — never the unblock proof |
| rauf run evidence | `{stateDir}/state.json` (`baseCommitHash`, `completedItems`, …), `{stateDir}/events.ndjson` (`item_selected`/`llm_spawned`/`llm_exited` w/ `itemId`) | best-effort tree attribution; no `rauf events` CLI exists — files parsed directly |
| rauf unblock | `rauf backlog unblock <path> [id]` → `{unblockedCount, unblockedIds}` | plain-blocked path; does NOT clear `needsHuman` — needs-human items go through `backlog answer` |

Surfaces that will **consume** this feature: forge-4-backlog (topology report),
forge-verify (CHECK-B28), forge-5-loop (Step 2a depth, recovery procedure, resolved
outcome), the compliance eval (loop-outcome probe), and forge-3-specs/forge-4-backlog of
*this* pipeline (dogfood constraint).

Patterns that must be followed: canon→adapter regen on every touched canon file
(`build-adapters.py`, checked by `validate.sh` step 6b); ruff over `scripts/`+`eval/`
(validate.sh step 7b + CI Quality Gate; local step skippable); stage/status parity —
the new decision vocabulary stays local to `forge-session.py` (no `epic-manifest.py`
duplicate), so `test_stage_constants_parity.py` needs **no changes** unless review
finds otherwise; adapter regen determinism (fixed `AGENT_TARGETS` order).

Conflicts checked: no other in-progress feature dir exists under `specs/` with
overlapping surfaces (`verify-test-debt` backlog was completed manually and is closed).
The `state-decision` name collision is designed around (§3.1). WARNING-level checks:
none of the expected exports failed to resolve; every integration point above was
located in source during research.

## 7. Error Handling

- **Forge verbs**: `UsageError` → exit 2 with `Error:` on stderr; skills surface the
  line verbatim, stop the surrounding protocol, never hand-author JSON (mirrors the
  Pipeline State Protocol). Unknown backlog dir, unparseable record, failed atomic
  write, unknown item id, `decision-apply` with nothing unapplied — all exit 2.
- **Recovery procedure** (REQ-REL-02): every runner invocation's non-zero exit or
  unparseable output is surfaced verbatim; the procedure stops and reports **failed
  recovery**; it never reports recorded/succeeded past a failed step. A version-probe
  miss (< `RECOVERY_MIN_RUNNER_VERSION`) is reported with the upgrade hint. Failed
  apply ≠ ran-but-nothing-moved: the former stops before the per-item test, the latter
  is the per-item test failing (REQ-UNB-03) — both are failed recoveries, differently
  attributed.
- **Attribution degradation**: unreadable/missing `state.json`/`events.ndjson` degrades
  tree attribution to the single consolidated unattributed decision — detection
  (REQ-TREE-01) never aborts on evidence-parse failure.
- **rauf `backlog answer`**: item missing / not `blocked` → non-zero + message; the
  procedure treats it as a failed apply for that item.

## 8. Testing Approach

Stdlib-only pytest (CI has no third-party deps; `jsonschema` behavioral tests use
`importorskip` as today). New/updated:

- `tests/test_forge_decisions_schema.py` — structural schema assertions
  (`additionalProperties: false`, required sets, enum values), mirroring
  `test_pipeline_state_schema.py`.
- `tests/test_decisions_schema_conformance.py` — R4 drift guard: every `decision-*`
  verb invoked out-of-process against a temp backlog dir; output file validated via
  `validate_decisions()`; registry-completeness scan; multi-verb sequences (record →
  defer → re-record → apply) asserting append-only audit invariants (REQ-DEC-07) and
  the `--unapplied` set across them; first-write edge cases.
- `tests/test_backlog_topology.py` — importlib-loaded `compute_topology`: line/diamond/
  parallel graph fixtures; the **observed incident fixture** (3 roots, 13-deep chain,
  16 items) asserting both warn triggers fire and `selectable`/starvation output names
  the roots (feeds SC-1's replay).
- `tests/test_decision_clustering.py` — normalization cases, Jaccard boundary (0.5),
  union-find transitivity, deterministic ordering, one-cause-three-phrasings fixture.
- `tests/test_stage_exit.py` — mirrored `EXIT_OUTCOMES` gains `resolved`; the
  "exactly the five" test renamed and re-parametrized to six; `resolved` asserted into
  the resume-routing test and the non-complete no-downstream bucket (incl. no
  auto-verify debt); `--cause` validity matrix (accepted on loop/partial, exit 2
  elsewhere) (REQ-COMPAT-01 — deliberate guard updates, no silent weakening).
- Eval: `loop-outcome` probe + fixture (REQ-EVAL-01); run via the existing advisory
  harness.
- rauf repo: `backlog answer` unit tests (happy path, not-blocked refusal, JSON shape)
  alongside the existing backlog-command tests.
- SC-4 baseline: capture a pre-change clean-tree happy-path run transcript before
  merging; assert post-change equivalence modulo the Step 2a depth line.

Verification commands: `bash scripts/validate.sh` (full gate: spec purity, adapter
drift, pytest, ruff, traceability) + `python3 scripts/forge-session.py doctor --json`
(smoke).

## 9. Dependencies

- **Forge-side**: Python stdlib only (argparse, json, tempfile, os, re, math). No new
  third-party deps. Adapter regen requires the existing pinned
  `scripts/requirements-adapters.txt` venv (unchanged).
- **rauf**: one new CLI subcommand shipping in the next rauf minor (assumed 0.14.0);
  `@garygentry/rauf` npm release + the feature-forge `installHint`/installer pin bump
  ride the normal release trains. `RECOVERY_MIN_RUNNER_VERSION` documents the
  capability threshold; `loopRunner.minRunnerVersion` is **not** raised.
- **Internal ordering** (PRD §3 note): DEC (schema+verbs) → TREE → UNB (needs rauf
  0.14.0 available locally for e2e; unit tests stub the CLI) → OUT → ATTR → CLU →
  TOPO → EVAL. The rauf PR can land in parallel with DEC/TREE.

## 10. Open Technical Questions

- **OTQ-1**: Should `stage-exit --outcome resolved` eventually verify the REQ-OUT-03
  gate server-side (e.g. accept `--evidence` counts it echoes into the payload for
  auditability)? Deferred: procedural + eval + directive-matrix enforcement now;
  revisit if the compliance eval observes gate-skipping in practice.
- **OTQ-2**: The exact rauf version carrying `backlog answer` (assumed 0.14.0). Pin
  `RECOVERY_MIN_RUNNER_VERSION` to the real release number at implementation time.
- **OTQ-3**: Whether forge-4-backlog's topology warning should also suggest concrete
  restructurings (e.g. "split root X's subtree") or only report. Current position:
  report + warn only; suggestions are agent judgment, not scripted output.
