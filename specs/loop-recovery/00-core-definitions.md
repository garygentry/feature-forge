# 00 — Core Definitions

> The shared contracts every other document in this suite builds on. Because
> `loop-recovery` extends the **forge pipeline's own machinery** (the argparse
> verbs in `scripts/forge-session.py`, the `forge-5-loop` skill body and its
> `references/`, plus one new `rauf` CLI subcommand), its "type system" is not a
> new domain model. It is (a) the new **`forge-decisions.json` JSON shape** and
> its R4 surface, (b) the extended **`LoopOutcome` vocabulary** and its route/text
> tables, (c) the **new module-level constants** the recovery, clustering, and
> topology code key off, (d) the **`backlog-topology` verb output shape** all five
> consumers read, and (e) the **error / exit-code and citation contracts** every
> new surface must honor. Every later document references these by section rather
> than re-deriving them.
>
> This document defines **shared contracts only**. It specifies no single surface's
> edits — those live in `02`–`06`. `01-architecture-layout.md` owns the file
> manifest, the `forge-session.py` module layout, and the delivery sequencing.

## Requirement Coverage

| REQ ID | Requirement | Section |
|--------|-------------|---------|
| REQ-DEC-02 | Record captures item/question/answer/decided/applied/actor | §3 (schema), §4.1 |
| REQ-DEC-06 | Deferral + cancel-early recorded shape | §4.1 (semantics), §4.2 |
| REQ-DEC-07 | Append-only; latest-entry-per-item unapplied set | §4.1, §4.3 |
| REQ-STATE-01 | R4 pattern: schema + verb + conformance | §4 (schema is the R4 anchor) |
| REQ-SEC-01 | No secret-shaped fields; actor labels only | §4.1 (field semantics), §7 |
| REQ-OUT-01 | Outcome expresses "decision made and applied" | §5.1 (`resolved`) |
| REQ-OUT-02 | Resolved routes **resume** | §5.2 (route table) |
| REQ-ATTR-04 | Starvation = annotation, not enum value | §5.1 (no new enum), §5.3 |
| REQ-COMPAT-01 | Vocabulary change ripples into directive matrix deliberately | §5.1, §5.2 |
| REQ-CLU-01 | Deterministic clustering substrate | §6.2 (constant), §8.3 (cluster shape) |
| REQ-TOPO-01..03 | Topology metrics + warn triggers | §6.1 (constants), §8 (output shape) |
| REQ-ATTR-01 | `selectable` from authoritative counts | §8 (`selectable` field) |
| REQ-OBS-01 | Every report surface cites its authoritative source | §9 (citation-basis table) |
| REQ-REL-02 | Failed scripted step surfaced verbatim, never claimed succeeded | §7 (error model) |
| REQ-PERF-01 | Topology/cluster linear + bounded | §6 (complexity notes) |

---

## 1. Scope & Non-Goals

**In scope for this document:** the data shapes, enum, constants, and error/citation
contracts shared across the feature. Everything is expressed in the project's actual
idiom — Python **stdlib only** (`argparse`, `json`, `tempfile`, `os`, `re`, `math`,
`typing`), no third-party deps, no `src/` package. New code lands in existing
canonical surfaces and fans out to `adapters/` via `scripts/build-adapters.py`.

**Non-goals** (from PRD §6, tech-spec §10): no locking / concurrent-writer support
(single-writer assumed, REQ-REL-01); no `.gitignore` edits (the record lives under
`**/.rauf/*`, already ignored, #195); no raising of `loopRunner.minRunnerVersion`
(stays `0.6.0`); no retroactive recovery of the verify-test-debt run. `resolved`
gate re-verification server-side is deferred (OTQ-1).

## 2. Prime Facts (the invariants every doc inherits)

1. **Two repos, two release trains.** All forge-side code is in the feature-forge
   repo (canon → adapters). Exactly one surface — `rauf backlog answer` — lands in
   the **separate `rauf` repo** (§`04`). `RECOVERY_MIN_RUNNER_VERSION` (§6.2) is the
   forge-side capability threshold that selects between the new rauf surface and the
   degraded fallback; it is **not** `minRunnerVersion` (which stays `0.6.0`).
2. **R4 pattern is mandatory for every new persistent surface** (REQ-STATE-01):
   a JSON **schema file**, a **scripted verb writer** (never hand-authored JSON), and
   a **schema-conformance test**. The one new persistent surface — `forge-decisions.json`
   — follows it exactly (§4, `02`, `07`).
3. **Exit-code discipline is 0/2 only.** Every new verb raises `UsageError` on any
   failure (unknown dir, unparseable file, failed atomic write, illegal argument
   combination) → exit 2, with an `Error:`-prefixed line on stderr. There is no exit 1
   from a `forge-session.py` verb. Skills surface that line verbatim and stop (§7).
4. **Determinism.** Clustering (§6.2) and topology (§6.1) are pure functions with
   fixed, id-sorted output — no dependence on dict/hash iteration order. This is what
   makes them testable and their reports reproducible.
5. **Every report surface cites authoritative counts** (REQ-OBS-01, §9). A claim the
   counters contradict is a reportable defect.

## 3. The decision-record surface at a glance

The one new persistent artifact is `forge-decisions.json`, an **append-only** log of
needs-human decisions for a backlog. It is written **only** by three new verbs —
`decision-record`, `decision-list`, `decision-apply` (§`02`, `05`) — never by hand.
Its location is `{resolvedBacklogDir}/{stateDir}/forge-decisions.json`
(default `specs/{feature}/.rauf/forge-decisions.json`), where `stateDir` is the
effective-config `loopRunner.stateDir` (default `.rauf`). Being under `**/.rauf/*`
it is git-ignored by construction — it survives session end and context clear
(durable) but is not tracked, not code-reviewed, and never dirties the working tree
that the tree-reconciliation gate (§`05`) inspects (REQ-DEC-01).

The full schema and verb API are in `02-decision-record.md`; the canonical shape is
here so every other doc references one definition.

## 4. `forge-decisions.json` — schema & semantics (REQ-DEC-02/06/07, REQ-STATE-01, REQ-SEC-01)

### 4.1 The schema (draft-07 subset per `tests/_state_schema.py`)

Lands verbatim at `references/forge-decisions-schema.json`. The subset is exactly what
the stdlib validator supports — `type`, `required`, `properties`, `enum`, `items`,
`additionalProperties: false`, and `$ref` to `#/definitions/*` (`tests/_state_schema.py`
module docstring). No `oneOf`, `anyOf`, `pattern`, or `format`.

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

**Field semantics** (authoritative — every doc uses these meanings):

| Field | Meaning | Rules |
|-------|---------|-------|
| `schemaVersion` | Schema version tag | Always `"1"` (enum-locked). Bumping is a breaking change. |
| `feature` | Feature name the backlog belongs to | Stamped on first write; never mutated. |
| `createdAt` / `updatedAt` | File-level timestamps | `_now_iso()` Z-suffixed UTC (§10). `createdAt` set once; `updatedAt` refreshed on every write by `_commit_state`. |
| `decisions[]` | Append-only entry log | New entries appended; existing entries never reordered or deleted. |
| `itemId` | The backlog item the decision answers | A rauf backlog item id (string). |
| `question` | The needs-human question text | For cancel-early/deferral, carries the original needs-human text (§4.2). |
| `answer` | The operator's answer, or `null` | `null` **iff** `deferred: true` (a deferral/cancel has no answer). |
| `deferred` | Whether this entry is a deferral | `true` ⇒ `answer: null`; re-surfaces via `--unapplied` next launch (REQ-DEC-06). |
| `clusterId` | Optional link to a consolidated decision | Present only on entries born from one consolidated (REQ-CLU) answer; shared across the cluster's members (REQ-CLU-04). |
| `decidedAt` | When the operator decided | `_now_iso()`. |
| `recordedBy` | Session/actor label | e.g. `forge-5-loop@claude`. **Never** user identity (REQ-SEC-01). |
| `appliedAt` / `appliedBy` | When/by-what the decision was applied to the runner | `null` until `decision-apply` succeeds; then stamped. Unapplied ⇔ `appliedAt == null`. |

**Security (REQ-SEC-01):** the schema has **no** credential-shaped field. `recordedBy`/
`appliedBy` are actor labels only. The recovery procedure's prompts (`05`) explicitly
instruct never to solicit secrets. The record is treated as repo-visible, non-sensitive
content and is never relied on as a secret store.

### 4.2 Cancel-early & deferral shape (REQ-DEC-06)

There is **no** third entry form. Both "operator cancels the run early" and "operator
defers a consolidated decision" record a **deferral**: `answer: null`, `deferred: true`,
`question` carrying the original needs-human text. The cancellation rationale is
conversational and is **never** written into `answer`. Consequently the
`decision-record` flag surface is exactly two mutually-exclusive forms —
`--answer A` **or** `--deferred` (§`02` §5.1) — and a deferral re-surfaces through
`decision-list --unapplied` on the next launch identically to any other unapplied entry.

### 4.3 Append-only & the unapplied set (REQ-DEC-07, REQ-DEC-05)

- **Append-only:** a later decision for the same `itemId` **appends** a new entry. No
  entry is ever mutated **except** `decision-apply`, which stamps `appliedAt`/`appliedBy`
  on the **latest** entry for an item — and nothing else. Earlier entries' audit fields
  are immutable, preserving the full history.
- **The unapplied set** (REQ-DEC-05, the read-back operation): the *latest entry per
  `itemId`* whose `appliedAt == null`. This naturally includes deferrals (which are never
  applied) and re-raised undecided items. `decision-list --unapplied` returns exactly
  this set. It is a **first-class** operation the recovery procedure enumerates, not a
  side effect.
- **No automatic pruning.** The file persists for the life of the backlog. Items answered
  by one consolidated decision (shared `clusterId`) remain independently re-decidable —
  a later per-item entry supersedes the cluster entry for that item only.

## 5. Loop outcome vocabulary (REQ-OUT-01..03, REQ-ATTR-04, REQ-COMPAT-01)

### 5.1 `LoopOutcome` gains exactly one value

`scripts/forge-session.py:374` today:

```python
LoopOutcome = Literal["complete", "partial", "blocked", "needs-human", "deferred"]
```

becomes:

```python
LoopOutcome = Literal["complete", "partial", "blocked", "needs-human", "deferred", "resolved"]
```

`EXIT_OUTCOMES["forge-5-loop"] = frozenset(get_args(LoopOutcome))` (`:399`) picks the new
value up **automatically** — it is a derived set, the single edit point. `resolved` means:
*a needs-human stop was subsequently resolved — decisions recorded and applied, affected
items verified unblocked per item, tree clean* (REQ-OUT-01). It is distinct from
`needs-human` ("decisions still outstanding").

**Starvation is NOT a new enum value** (REQ-ATTR-04, OQ-1). Dependency starvation is a
**cause annotation** on the existing `partial` outcome (§5.3), because `partial-starved`
and `partial` would route identically (resume) — a distinct value buys only text at the
cost of doubling the enum/routing/test/eval ripple.

### 5.2 Routing & text (the tables `03` edits)

- **Route** (`_LOOP_ROUTE_KIND`, `:2952`): `"resolved": "resume"` (REQ-OUT-02). Its
  NEXT-STEPS block fences `/feature-forge:forge-5-loop {feature}` exactly like
  `partial`/`deferred`, **never** the navigator (which `blocked`/`needs-human` use).
- **Text** (`_LOOP_OUTCOME_TEXT`, `:2964`): new `"resolved"` sentence (its exact prose is
  fixed in `03`): the needs-human stop was resolved (decisions recorded and applied,
  affected items verified unblocked per item, tree clean); relaunch to continue.
- **Non-complete membership:** `resolved` joins the non-complete bucket — no `nextStage`,
  no auto-verify debt, no downstream-readiness claim
  (`test_no_non_complete_loop_outcome_claims_downstream_readiness`).
- **Ladder position:** evaluated **first** — `resolved` → `needs-human` → `blocked` →
  `deferred` → `partial` → `complete` — gated on "the recovery procedure ran this session
  and its gate passed" so a resolved stop never re-triggers the needs-human branch its
  own recovery just cleared. The ladder exists in **two** canonical places, both of which
  change: `skills/forge-5-loop/SKILL.md:271` (the body copy `test_stage_exit_protocol.py:
  379-388` reads) and the rung definitions in `references/result-reporting.md`.

**The `resolved` gate (REQ-OUT-03)** — selected *procedurally* by the recovery procedure
(`05`), only when all three hold: (a) `decision-list --unapplied` is empty for the affected
items; (b) `git status --porcelain` is clean (git-ignored stateDir artifacts are invisible
to it — the clean-tree exclusion holds by construction); (c) the per-item re-read (`04`)
shows every affected item left `blocked`/`needsHuman`. `stage-exit` does **not** re-verify
this server-side (it has no runner access) — enforcement is procedural + eval-measured
+ directive-matrix-tested.

### 5.3 Starvation cause & `--cause`

- `selectable` (REQ-ATTR-01) = pending items whose `dependsOn` are all `done`, from the
  `backlog-topology` verb (§8) over the runner's `listCommand` JSON.
- When `selectable == 0 && pending > 0 && iterationsUsed < iterationsGranted`, the report
  renders **dependency starvation**: blocking roots + each root's gated-subtree size
  (REQ-ATTR-02), not the iteration limit.
- `stage-exit --stage forge-5-loop --outcome partial --cause dependency-starvation` swaps
  the `partial` sentence for a starvation variant naming the unblock path. The flag is
  **rejected (exit 2)** for any other stage/outcome (`03` §5.3). Absent flag = today's text.
- The three canonical "(iteration limit reached)" occurrences become conditional —
  rendered only when `iteration == maxIterations` (limit was binding) **and**
  `selectable > 0` (REQ-ATTR-03).

## 6. New module-level constants (`scripts/forge-session.py`)

All are `Final`, module-level, no config knob (zero-prompt-config direction). Each doc
that uses one references it here.

### 6.1 Topology (REQ-TOPO-01..03, D6)

```python
TOPOLOGY_FANOUT_WARN_RATIO: Final[float] = 0.5   # a single root gating ≥50% of items warns
TOPOLOGY_DEPTH_WARN_RATIO:  Final[float] = 0.5   # max chain depth ≥50% of item count warns
```

`compute_topology(items)` is a pure function, **linear** via memoized DFS over `dependsOn`
edges (cycle-safe: rauf has already rejected cycles; a visited set still guards). The
observed incident (3 roots gating 81%, depth 13/16) trips **both** triggers. (§8 = output.)

### 6.2 Clustering & recovery (REQ-CLU-01, D7; D4/D8)

```python
CLUSTER_JACCARD_THRESHOLD:  Final[float] = 0.5   # token-set Jaccard union-find edge threshold
RECOVERY_MIN_RUNNER_VERSION: Final[str]  = "0.14.0"  # OTQ-2: pin to the real rauf release at impl
```

`CLUSTER_JACCARD_THRESHOLD` is **falsifiable against the incident**: the
one-cause-three-phrasings fixture (`07`, derived from the real verify-test-debt
`blockedReason` strings) must cluster into exactly one candidate; the binding pair clears
0.5 by only ~0.028, so the fixture strings are vendored **verbatim** (carried note V-015).
`RECOVERY_MIN_RUNNER_VERSION` selects the apply mechanism (`04`); it **never** hard-fails
recovery and is **not** `loopRunner.minRunnerVersion` (which stays `0.6.0`).

## 7. Error model (REQ-REL-02, REQ-STATE-01)

Every new `forge-session.py` verb inherits the existing contract:

- Failures raise `UsageError` (`forge-session.py:682` — `class UsageError(Exception): """A
  usage or I/O failure that must exit 2."""`), producing an `Error:`-prefixed line on
  **stderr**, empty stdout, **exit 2**. Cases: unknown backlog dir; unparseable record;
  failed atomic write; unknown item id; `decision-apply` with nothing unapplied for the
  item; the `--cause` flag on any stage/outcome but `forge-5-loop`/`partial`;
  `decision-record` given both `--answer` and `--deferred`, or neither.
- **Recovery procedure (REQ-REL-02):** any non-zero runner exit (`rauf backlog answer`/
  `unblock`), any failed `decision-*` write, and any unparseable read-back is surfaced
  **verbatim** and **stops** the procedure — reported as **failed recovery**, never as
  recorded/succeeded. A **failed apply** (runner errored, or predates the verb) is
  distinguishable from a **ran-but-nothing-moved** failure (REQ-UNB-03): the former stops
  *before* the per-item test; the latter *is* the per-item test failing.
- **Attribution degradation:** unreadable/missing `state.json`/`events.ndjson` degrades
  tree attribution to a single consolidated unattributed decision — detection
  (REQ-TREE-01) **never** aborts on evidence-parse failure.

## 8. `backlog-topology` verb output shape (all five consumers read this)

The `backlog-topology` verb (`06` §5.2) is a **pure function over the runner's item
array** — the caller feeds it the `loopRunner.listCommand` JSON it already obtained
(`rauf backlog list . --backlog {dir} --json`); it **never** reads `backlog.json` off disk
(single-data-source, decision V-007), so every derived claim cites the runner's
authoritative counts. Output JSON (with `--cluster`, `clusters` is appended):

```jsonc
{
  "itemCount": 16,
  "rootCount": 3,
  "roots": [ { "id": "1", "gatedCount": 13, "gatedIds": ["2","3", "..."] } ],
  "maxChainDepth": 13,
  "selectable": 0,                          // REQ-ATTR-01: pending w/ all deps done
  "starvation": {                           // null unless starved
    "starved": true,
    "blockingRoots": [ { "id": "1", "gatedCount": 13 } ]
  },
  "warnings": ["single-root-fanout", "chain-depth"],   // subset of these two tokens
  "clusters": [                             // --cluster only (§6.2, `06` §3.6)
    { "clusterId": "c1", "memberIds": ["4","7"], "memberReasons": ["...","..."],
      "sharedTokens": ["missing","key"], "gatedIds": ["..."], "gatedCount": 13 }
  ]
}
```

- **`roots`**: items with no `dependsOn`. `gatedCount`/`gatedIds` = items transitively
  depending on the root ("gates").
- **`maxChainDepth`**: longest `dependsOn` chain (bounds achievable progress — surfaced at
  forge-5-loop Step 2a, REQ-TOPO-03).
- **`warnings`**: `"single-root-fanout"` when any root's `gatedCount ≥ ceil(0.5·itemCount)`;
  `"chain-depth"` when `maxChainDepth ≥ ceil(0.5·itemCount)`. Advisory only.
- **`clusters`** (`--cluster`): §8.3 shape — one per union-find component of blocked items
  whose pairwise token-set Jaccard ≥ 0.5, emitted sorted by lowest member id.

### 8.3 Cluster entry (feeds REQ-CLU-02/03 blast-radius prompts)

Each cluster carries `memberIds`, `memberReasons`, the `sharedTokens` core, and the
**union** of members' gated subtrees (`gatedIds` + `gatedCount`) for blast-radius framing
("gates 13/16 items"). A `clusterId` is minted deterministically (`c` + lowest member id)
so `decision-record --cluster CID` can tie the consolidated answer's per-item entries
together (REQ-CLU-04).

## 9. Citation-basis contract (REQ-OBS-01)

REQ-OBS-01 binds **every** report surface this feature adds. Each names the authoritative
source it derived its claims from; a claim the source contradicts is a reportable defect.
This table is carried **verbatim** into `recovery-procedure.md` (`05`) and is the master
copy:

| Report surface | Authoritative citation basis |
|---|---|
| Pending / starvation template (`03`) | `backlogSummary` counts + `backlog-topology` output over `listCommand` JSON; iteration counters from `state.json` (`iteration`/`maxIterations`) |
| Failed-recovery report (`04`, `05` step 6) | The per-item `listCommand` re-read — movers/non-movers named from item `status`, never aggregate counts |
| `resolved` outcome text (`03`) | The three gate evaluations: `decision-list --unapplied` (empty), `git status --porcelain` (empty), per-item re-read (all affected left `blocked`) |
| Consolidated blast-radius prompt (`05` step 3) | `backlog-topology --cluster` gated-subtree output (member ids + counts) |
| Tree-reconciliation presentation (`05` §3.5) | `git status --porcelain` paths + `state.json`/`events.ndjson` run evidence, attributions explicitly presented as **candidates** |
| Step 2a depth line (`06`) | The same `backlog-topology` output (`maxChainDepth`) |

## 10. Existing helpers this feature builds on (verified from source)

All line numbers are as of the tech-spec's research pass; treat the **symbol** as
authoritative if a line drifts.

| Symbol | Location | Contract |
|--------|----------|----------|
| `class UsageError(Exception)` | `forge-session.py:682` | any failure → exit 2, `Error:` on stderr |
| `_now_iso()` | `forge-session.py:4083` | Z-suffixed second-precision UTC; used for all timestamps |
| `_write_state(path, state)` | `forge-session.py:4097` | atomic mkstemp→fsync→`os.replace`; `UsageError` on failure. Target-agnostic (works for the decisions path, not only `.pipeline-state.json`). |
| `_commit_state(path, state)` | `forge-session.py:4388` | stamps `updatedAt` = `_now_iso()`, writes atomically, returns the dict for `--json` echo. **Target-agnostic** per its docstring — reused for `forge-decisions.json`. |
| `_emit(payload, json_output, printer)` | `forge-session.py:5514` | the `--json` vs human-print dispatcher every verb ends with |
| `LoopOutcome` / `EXIT_OUTCOMES` | `forge-session.py:374,398` | derived enum — single edit point (§5.1) |
| `_LOOP_ROUTE_KIND` / `_LOOP_OUTCOME_TEXT` / `_loop_route()` | `forge-session.py:2952,2964,3117` | route/text tables + resume/recover dispatcher (§5.2) |
| stdlib validator | `tests/_state_schema.py` (`_check`, `_STATE_SCHEMA`, `_CONFIG_SCHEMA`, `validate_state`) | draft-07 subset; add `_DECISIONS_SCHEMA` + `validate_decisions()` mirroring the two existing loads (§`02`, `07`) |
| R4 guard template | `tests/test_state_schema_conformance.py` | out-of-process `_run()`, `VERB_INVOCATIONS`, registry-completeness regex — cloned for `decision-*` |
| `loopRunner` config | `references/forge-config-schema.json` | `stateDir` (`.rauf`), `versionCommand` (`{bin} version --json`), `listCommand`, `statusJsonCommand`, `installHint`, `minRunnerVersion` (`0.6.0`) |

**Note — the `decision-*` verbs do NOT use `_load_state_for_write`/`_resolve_feature_dir_
for_write`.** Those resolve a *feature* directory for `.pipeline-state.json`. The decision
record lives under a **backlog** directory (`--backlog-dir`), so the verbs resolve their
own path (`{backlog-dir}/{state-dir}/forge-decisions.json`) and reuse only the
target-agnostic `_commit_state`/`_write_state`. Details in `02`.

## Dependencies

None — this is the root document. Every other document in this suite depends on it.

## Verification

- [ ] `references/forge-decisions-schema.json` is byte-for-byte the §4.1 schema and
      validates under `tests/_state_schema.py`'s subset (no unsupported constructs).
- [ ] `LoopOutcome` includes `"resolved"`; `get_args(LoopOutcome)` has 6 members;
      `EXIT_OUTCOMES["forge-5-loop"]` is derived, not hand-listed.
- [ ] The four new constants exist as module-level `Final` with the §6 values.
- [ ] `backlog-topology --json` output matches the §8 shape on the observed-incident
      fixture (both `warnings` tokens present, `starvation.starved == true`).
- [ ] No new persistent surface is hand-authored: `forge-decisions.json` is only ever
      written by `decision-*` verbs (grep proves no direct `json.dump` of a decisions doc
      outside the verbs).
