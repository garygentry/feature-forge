# 05 — The Post-Run Recovery Procedure

> **The orchestration doc.** This specifies the *content* of the new
> `skills/forge-5-loop/references/recovery-procedure.md` — the named **Post-Run
> Recovery Procedure** that replaces the undefined phrase "stage a post-run retry"
> (REQ-DEC-04). It is the driver that runs after a loop run ends: it enumerates the
> unapplied decisions, consolidates systemic causes, records every operator answer at
> collection, applies them through the runner, proves per item that the affected items
> left `blocked`/`needsHuman`, reconciles a stranded working tree, and selects the
> `resolved` outcome when — and only when — its three-part gate passes.
>
> This document **orchestrates**; it does not own the mechanisms it invokes. The
> decision-record verbs live in `02-decision-record.md`; the apply mechanism and the
> per-item unblock proof live in `04-apply-and-unblock.md`; the clustering + topology
> substrate lives in `06-clustering-and-topology.md`; the shared schema, the
> `LoopOutcome` vocabulary, the module constants, the error model, and the citation
> table all live in `00-core-definitions.md`. Every type and shape referenced here is
> defined there — this doc references, it does not re-derive.
>
> This document ALSO specifies two edits that make the procedure reachable: the new
> `### 1g. Stranded-Work Pre-flight` body sub-step in `skills/forge-5-loop/SKILL.md`
> (REQ-TREE-04), and the two pointer edits in the runner/ralph contracts (REQ-DEC-04).

## Requirement Coverage

| REQ ID | Requirement | Section |
|--------|-------------|---------|
| REQ-DEC-04 | "stage a post-run retry" → a named, referenced procedure that reads the record back | §2 (whole procedure), §6 (pointer edits) |
| REQ-DEC-05 | Enumerating unapplied decisions is a first-class step | §2 step 1, §3 |
| REQ-DEC-06 | Every branch (answered, deferred, cancel-early) records at collection; unapplied re-surface next launch | §2 step 4, §3 |
| REQ-CLU-02 | One consolidated decision per cluster of ≥2, naming every affected item + gated subtree | §2 step 3 |
| REQ-CLU-03 | Consolidated prompts framed by blast radius, not per item | §2 step 3 |
| REQ-CLU-04 | Consolidated answer recorded via the REQ-DEC mechanism, per-item, shared `clusterId` | §2 step 4 |
| REQ-TREE-01 | Detect a dirty tree after the run, before any outcome is selected | §4 sub-step 1 |
| REQ-TREE-02 | Attribute stranded work to items (best-effort, runner-native) and drive to a decision | §4 sub-step 2, sub-step 3 |
| REQ-TREE-03 | Discard requires its own explicit confirmation; never a default | §4 sub-step 3 |
| REQ-TREE-04 | Unreconciled tree surfaced as a launch blocker naming the previous run | §4 sub-step 4, §5 (`### 1g`) |
| REQ-COMPAT-02 | No new prompts on a run that never hit needs-human/blocked and left a clean tree | §2 step 1, §4 sub-step 1 |
| REQ-OBS-01 | Every report surface names its authoritative citation basis | §7 (carried citation table); cited per-step |

Invoked (owned elsewhere, referenced here): REQ-CLU-01 (`06`), REQ-UNB-01..03 /
REQ-REL-02 (`04`), REQ-OUT-01..03 (`00` §5, `03`), REQ-DEC-01..03/07 (`00` §4, `02`),
REQ-SEC-01 (`00` §4.1 — prompts here honor it).

---

## 1. Scope & Dependencies

**This document owns** the prose of `recovery-procedure.md`: the seven-step procedure,
the fresh-session re-entry behavior, the tree-reconciliation section, and the carried
REQ-OBS citation table. It additionally specifies the `### 1g` body sub-step of
`skills/forge-5-loop/SKILL.md` and the two contract pointer edits.

**This document does NOT own** (it invokes them by reference):

| Mechanism | Owning doc | What this procedure calls |
|-----------|-----------|---------------------------|
| `decision-record` / `decision-list` / `decision-apply` verbs + schema | `02` (`00` §3–§4) | steps 1, 4, 5 |
| Apply mechanism (`rauf backlog answer`, degraded `unblock`, version probe) + the per-item unblock proof | `04` (tech-spec §3.3) | steps 5, 6 |
| `backlog-topology --cluster` + `compute_topology` + `cluster_blocked` | `06` (`00` §6, §8) | steps 2, 3, §4 |
| `LoopOutcome` `resolved` + route/text + ladder + the gate | `00` §5, `03` | step 7 |
| Error / exit-code model, citation-basis master table | `00` §7, §9 | throughout, §7 |
| Testing of the procedure's replay | `07-testing-strategy.md` | Verification |

The procedure is a **skill reference** consumed by the `forge-5-loop` agent — it is
authored in prose that instructs the agent, not as executable Python. Its scripted
substrate (the verbs, the topology/cluster functions, the apply CLIs) is what the other
docs specify; this doc specifies the *sequence, decision points, and reporting
obligations* that wire them together.

## 2. The Post-Run Recovery Procedure (REQ-DEC-04)

Seven ordered steps. The procedure runs **after** a loop run ends (invoked from the
`needs_human` / `item_blocked` live-event handling and from Step 7's close path), and it
runs again as the **re-entry point** on a fresh session (§3). Throughout, `D` is the
resolved backlog dir (e.g. `specs/loop-recovery` or `{backlogDir}/{feature}`, per
`forge-5-loop` Step 1e/2b composition), and `{stateDir}` is effective-config
`loopRunner.stateDir` (default `.rauf`).

Any scripted step that exits non-zero, or any runner invocation that errors or returns
unparseable output, is surfaced **verbatim** and **stops** the procedure with a **failed
recovery** report — never reported as recorded/succeeded (`00` §7, REQ-REL-02). A failed
*apply* (step 5) is distinguishable from a ran-but-nothing-moved *proof* failure (step 6)
because the former never reaches step 6.

### Step 1 — Enumerate (REQ-DEC-05)

- **Input:** the backlog dir `D`; the runner's authoritative item list.
- **CLI:**
  ```bash
  python3 "$R/scripts/forge-session.py" decision-list --backlog-dir D --unapplied --json
  ```
  (verb + flag shape defined in `02` §5.1 / `00` §4.3 — the "unapplied set" is the latest
  entry per `itemId` with `appliedAt == null`.) Also read the current blocked/needs-human
  set from the runner: `rauf backlog list . --backlog D --json` (`loopRunner.listCommand`).
- **Decision point (REQ-COMPAT-02):** if `decision-list --unapplied` returns an **empty**
  set **and** no item is `blocked`/`needsHuman`, **exit the procedure — nothing to
  recover.** Combined with the clean-tree silence of §4 sub-step 1, this is what keeps a
  happy-path run free of any new prompt (REQ-COMPAT-02): the only new happy-path output is
  the Step 2a depth line owned by `06`.
- **Output:** the unapplied-decision set (each entry's `itemId`, `question`, `answer|null`,
  `deferred`, `clusterId?`), and the live blocked/needs-human item set.
- **Error:** a `decision-list` exit 2 (unknown dir, unparseable record) stops the
  procedure per `00` §7. A failed `listCommand` read stops it as a failed recovery.

### Step 2 — Cluster (REQ-CLU-01 — substrate owned by `06`)

- **Input:** the blocked/needs-human items from step 1, each carrying its `blockedReason`
  (where rauf lands the `RAUF_NEEDS_HUMAN:<reason>` text — `00` §6.2 input note).
- **CLI:**
  ```bash
  python3 "$R/scripts/forge-session.py" backlog-topology --items-stdin --cluster --json  < items.json
  ```
  fed the same `listCommand` JSON already obtained (single-data-source, `00` §8). Returns
  the `clusters[]` shape (`00` §8.3): each with `memberIds`, `memberReasons`,
  `sharedTokens`, and the **union** of members' gated subtrees (`gatedIds` + `gatedCount`).
- **Decision point:** the agent **may merge or refine** candidate clusters by judgment
  (REQ-CLU-01) — under-clustering is the deliberately-chosen failure direction the scripted
  helper leaves to agent merge authority (`06`, tech-spec §3.6). The agent has no scripted
  *split* authority; the helper's clusters are the floor, not a ceiling.
- **Output:** the final cluster set (scripted candidates ± agent merges), each with its
  member ids and blast-radius numbers.
- **Error:** a `backlog-topology` exit 2 stops the procedure (`00` §7).

### Step 3 — Consolidated prompts (REQ-CLU-02, REQ-CLU-03, REQ-SEC-01)

- **Input:** the final cluster set from step 2.
- **Mechanism:** the host's `AskUserQuestion` surface (never inline prose).
  - For any cluster of **two or more** items: emit **exactly one** consolidated question
    (REQ-CLU-02) that **names every affected item id** and states the **full gated
    subtree** the cluster gates.
  - Frame it by **blast radius** (REQ-CLU-03): e.g. *"This one decision gates 13 of 16
    backlog items (items 2,3,…). Answer it once."* — never one prompt per member.
  - Singleton clusters prompt per item (today's per-item shape).
- **Security (REQ-SEC-01):** prompts **MUST NOT** solicit secrets. Ask for the *decision*
  (which path, which policy), never a credential/token/key value. The decision record
  (`00` §4.1) has no credential-shaped field and is treated as repo-visible content.
- **Decision point:** the operator may **answer**, **defer** the consolidated decision, or
  request **cancel the run early** — all three branches proceed to step 4 (nothing is
  acted on before it is recorded).
- **Output:** per cluster/item, one of {answer text, deferral, cancel-early}.
- **Citation (REQ-OBS-01):** the blast-radius framing is derived from
  `backlog-topology --cluster` gated-subtree output (member ids + counts) — the prompt
  cites that source; a "gates N/M" claim the topology output contradicts is a defect.

### Step 4 — Record at collection (REQ-DEC-06, REQ-CLU-04)

- **Input:** every branch outcome from step 3.
- **CLI (one call per decision, BEFORE anything is applied):**
  ```bash
  # answered singleton
  python3 "$R/scripts/forge-session.py" decision-record --backlog-dir D \
      --item ID --question "Q" --answer "A" --actor forge-5-loop@claude
  # deferred, or cancel-early (both record a deferral: no --answer)
  python3 "$R/scripts/forge-session.py" decision-record --backlog-dir D \
      --item ID --question "Q" --deferred --actor forge-5-loop@claude
  # consolidated answer: one entry per affected item, shared clusterId (REQ-CLU-04)
  python3 "$R/scripts/forge-session.py" decision-record --backlog-dir D \
      --item ID1 --item ID2 --item ID3 --question "Q" --answer "A" \
      --cluster c1 --actor forge-5-loop@claude
  ```
  Verb/flag surface + append-only semantics defined in `02` §5.1 / `00` §4.
- **Decision point (REQ-DEC-06):** a decision is recorded on **every** branch — answered,
  deferred, **and** cancel-early — and it is recorded **before** step 5 acts on anything. A
  cancel-early is recorded as a **deferral** (`answer: null`, `deferred: true`, `question`
  carrying the original needs-human text; `00` §4.2) — there is no third entry form. A
  recorded-but-unapplied entry (`appliedAt == null`) is exactly what step 1 re-surfaces on
  the next launch (REQ-DEC-06 → §3).
- **Consolidated (REQ-CLU-04):** one entry per affected item, all sharing one `clusterId`
  (minted `c` + lowest member id, `00` §8.3). Items stay **independently re-decidable**
  (REQ-DEC-07): a later per-item entry supersedes the cluster entry for that item only.
- **Output:** durable entries in `forge-decisions.json`; the write is atomic
  (`_commit_state`, `00` §10).
- **Error:** any `decision-record` exit 2 (both/neither of `--answer`/`--deferred`, unknown
  dir, failed atomic write) is surfaced verbatim and stops the procedure (`00` §7). The
  answer is **not** applied if it was not recorded.

### Step 5 — Apply (mechanism owned by `04`)

This step **invokes** the apply mechanism specified in `04-apply-and-unblock.md`; it does
not re-specify it. The sequence:

- **Version probe:** run `versionCommand` (`rauf version --json` → `{version}`) and compare
  forge-side semver against `RECOVERY_MIN_RUNNER_VERSION` (`00` §6.2, default `"0.14.0"`).
- **Apply per item:**
  - needs-human item, runner **≥** threshold → `rauf backlog answer <path> <id> "<text>"
    [--backlog D] [--json]` (the answer text is threaded into the next iteration's prompt).
  - needs-human item, runner **<** threshold → **degraded path:** `rauf backlog unblock
    <path> <id>` — the item is genuinely unblocked and the answer stays durable in
    `forge-decisions.json`, but the recovery report **must state explicitly** that the
    answer was **not** injected into the next iteration's prompt, with the `installHint`
    upgrade hint attached (`04`, tech-spec §3.3).
  - plain (non-needs-human) blocked item → `rauf backlog unblock <path> <id>` at **every**
    runner version.
- **Stamp:** after each runner apply **succeeds**, run
  ```bash
  python3 "$R/scripts/forge-session.py" decision-apply --backlog-dir D --item ID \
      --actor forge-5-loop@claude
  ```
  which stamps `appliedAt`/`appliedBy` on the item's latest entry (`02` §5.1). `decision-apply`
  is called **only after** the runner apply returned success (REQ-UNB-01) — a stamped record
  means the runner actually accepted the change.
- **Error (REQ-REL-02):** a runner apply that **errors** (non-zero exit — item missing, not
  `blocked`, or any failure) is a **failed apply**: surface it verbatim, do **not** call
  `decision-apply`, stop the procedure, report failed recovery. This is distinct from a
  version-probe miss (which routes to the degraded path, not a failure) and from step 6's
  ran-but-nothing-moved failure.

### Step 6 — Prove (REQ-UNB-02/03 — test owned by `04`)

- **Input:** the affected item set that step 5 applied.
- **CLI:** re-read per-item state via `loopRunner.listCommand`
  (`rauf backlog list . --backlog D --json`) and test **each** affected item:
  `status != "blocked"` (which, per rauf's derivation, also removes it from `needsHuman` —
  `needsHuman == status=="blocked" && needsHuman==true`). Aggregate `backlogSummary` counts
  are **never** the test (`04`, `00` §9).
- **Decision point:** **all** affected items moved → proceed to step 7. **Any** non-mover —
  including a partial move where some items moved and others did not — is a **failed
  recovery** (REQ-UNB-03): report it, **naming the movers and the non-movers** from their
  item `status` fields.
- **Output:** either "all moved → continue" or a failed-recovery report.
- **Citation (REQ-OBS-01):** the movers/non-movers are named from the per-item `listCommand`
  re-read (`status` fields), never from aggregate counts — a report that contradicts the
  per-item read is a defect.

### Step 7 — Gate & exit (REQ-OUT-03 — vocabulary owned by `00` §5 / `03`)

- **Tree reconciliation first.** Before any outcome is selected, run the **Post-Run Tree
  Reconciliation** section (§4). It runs on every recovery pass — including passes with no
  needs-human items — and is silent on a clean tree.
- **Evaluate the `resolved` gate** (`00` §5.2, REQ-OUT-03) — all three must hold:
  1. `decision-list --unapplied` is **empty** for the affected items (step 1/4).
  2. `git status --porcelain` is **clean** (git-ignored `{stateDir}` artifacts are invisible
     to porcelain — the exclusion holds by construction, `00` §4).
  3. the per-item re-read (step 6) shows **every** affected item left `blocked`/`needsHuman`.
- **Select the outcome:** on all-three-pass, Step 7 selects `resolved` (the first ladder
  rung, `00` §5.2 — a resolved stop must not re-trigger the needs-human branch its own
  recovery just cleared). Otherwise the ladder **falls through** to `needs-human` / `blocked`
  / `deferred` / `partial` / `complete` exactly as today. `resolved` routes **resume** — its
  NEXT-STEPS block fences `/feature-forge:forge-5-loop {feature}` (`00` §5.2, `03`), never the
  navigator.
- **CLI:** the close runs through the existing Scripted Stage Exit
  (`forge-5-loop` Step 7): `stage-exit … --outcome resolved …`. `stage-exit` does **not**
  re-verify the gate server-side (it has no runner access) — enforcement is procedural (this
  step) + eval-measured (`07`) + directive-matrix-tested (`03`, REQ-COMPAT-01).
- **Citation (REQ-OBS-01):** the `resolved` outcome text cites the three gate evaluations
  (`decision-list --unapplied` empty, porcelain empty, per-item re-read all-moved). Claiming
  `resolved` without those preconditions is a reportable defect.

## 3. Fresh-session re-entry (REQ-DEC-06)

The procedure is the **re-entry point** on a fresh session / next launch — this is what
makes a decision survive session end and context clear.

On a new session, **step 1** (`decision-list --unapplied`) enumerates every entry with
`appliedAt == null` from a *previous* session — answered-but-not-yet-applied decisions,
deferrals, and cancel-early deferrals alike (`00` §4.3). Those entries are **re-surfaced**:

- An entry that already carries an **answer** (`answer != null`, `deferred == false`,
  `appliedAt == null`) skips step 3's prompt for that item — the operator already decided;
  the procedure proceeds straight to step 5 (apply) and step 6 (prove). This is the #196
  fix: the answer collected last session is applied this session without re-asking.
- A **deferral** (`deferred == true`) re-surfaces through step 3 as an open decision — the
  operator is asked again, and their new answer appends a **new** entry (append-only,
  REQ-DEC-07); the deferral's audit fields are never destroyed.

Because entries are durable and untracked (`00` §3), a session boundary, crash, or context
clear between "operator answered" and "answer applied" never costs the decision — step 1 of
the next launch finds it. This is the concrete meaning of REQ-DEC-06's "MUST be re-surfaced
by the REQ-DEC-05 enumeration on the next launch".

## 4. Post-Run Tree Reconciliation (REQ-TREE-01..04, REQ-COMPAT-02)

A **required section** of `recovery-procedure.md`, invoked from Step 7 after the run ends
and **before** any outcome is selected. It runs on **every** recovery pass — including
passes with no needs-human items — because it is the "tree" half of recovery. Four
sub-steps.

### 4.1 Detect (REQ-TREE-01, REQ-COMPAT-02)

- **CLI:** `git status --porcelain`.
- **Clean tree → SILENT.** Empty output ⇒ no prompt, no output, no operator decision
  (REQ-COMPAT-02). The decision record and all runner state under `{stateDir}` are
  git-ignored (`**/.rauf/*`, #195) and therefore **never appear** in porcelain output
  (REQ-DEC-01 note) — decision writes never dirty the tree this step inspects.
- **Dirty tree → proceed to 4.2.**
- **Error:** a `git status` failure (not a git repo, git error) is surfaced verbatim;
  reconciliation is skipped (there is nothing git-native to reconcile), the rest of the
  procedure continues.

### 4.2 Attribute (best-effort, runner-native) (REQ-TREE-02)

Best-effort attribution of dirty paths to the backlog item(s) that produced them, from
**runner-native evidence** — reliable per-item provenance is **not** a prerequisite
(REQ-TREE-02 note), and **no rauf change is spent here** (best-effort suffices).

- **Read `{stateDir}/state.json`** (rauf `LoopState`, `packages/core/src/schemas.ts:189`):
  - `baseCommitHash` (`:216`, nullable) — the HEAD captured at run start; the baseline for
    `git log {baseCommitHash}..HEAD`.
  - `completedItems` (`:198`), `blockedItems` (`:199`) — item ids that finished / blocked.
  - `currentItem` (`:194`, nullable) — the item in flight when the run stopped (a strong
    candidate for uncommitted changes).
  - `startedAt` (`:196`), `iteration`/`maxIterations` (`:191`/`:192`) — run identity + budget.
- **Read `{stateDir}/events.ndjson`** (one JSON object per line — parse with stdlib
  `json.loads` per line; rauf event schemas `packages/core/src/schemas.ts`): the per-iteration
  `item_selected` (`:478`, `itemId`+`title`+`priority`), `llm_spawned` (`:485`, `itemId`), and
  `llm_exited` (`:493`, `itemId`+`exitCode`+`durationMs`) records — each carrying `itemId` and
  a base `timestamp` (`:459`) — name which items ran during the window and in what order. There
  is **no `rauf events` CLI**; the file is parsed directly (tech-spec §6). Forge does not parse
  these files today (it parses only its own `.pipeline-state.json`) — this is new procedure-side
  reading, stdlib-only.
- **Map dirty paths → candidate items:** by run evidence — the `currentItem` and the most
  recent `item_selected`/`llm_spawned` without a matching clean `llm_exited` are the items
  "in flight when the run died"; `git log {baseCommitHash}..HEAD` names what was already
  committed for which item (rauf commits `[rauf] <id>:`). Present the mapping as
  **CANDIDATES, never asserted** (REQ-TREE-02 note, `00` §9).
- **Degradation (REQ-TREE-01 never aborts):** if `state.json` or `events.ndjson` is
  missing/unreadable/unparseable, **degrade** to the fully-unattributed path (everything goes
  into 4.3's single consolidated decision). Detection (4.1) is **never** aborted by an
  evidence-parse failure (`00` §7).
- **Citation (REQ-OBS-01):** the presentation cites `git status --porcelain` paths +
  `{stateDir}/state.json` / `events.ndjson` run evidence, with every attribution explicitly
  labelled a **candidate** (`00` §9, tree-reconciliation row).

### 4.3 Decide (REQ-TREE-02, REQ-TREE-03)

- **Mechanism:** `AskUserQuestion` (never inline prose).
  - **One question per attributed item-group:** for each candidate item-group from 4.2,
    offer **commit-for-that-item** / **stash** / **discard**.
  - **Unattributable changes → ONE consolidated decision** (REQ-TREE-02): everything that
    could not be attributed is presented as a single grouped question, not dropped.
- **Discard guard (REQ-TREE-03):** **discard is NEVER the default** and requires its **own
  explicit confirmation** — a second, dedicated `AskUserQuestion` confirming the specific
  paths to be discarded before any `git checkout`/`git restore`/`git clean` runs. No path is
  discarded on a single click.
- **Output:** per group, an executed reconciliation (commit / stash / confirmed discard) or a
  deferral the operator can revisit.

### 4.4 Launch blocker (REQ-TREE-04)

forge-5-loop has **no** existing forge-side dirty-tree pre-flight today — the only gate is
rauf's own launch refusal, *"Refusing to run the loop with uncommitted changes… pass
`--force`"* (`skills/forge-5-loop/references/runner-contract.md:73-79`), whose message forge
**cannot** rewrite. REQ-TREE-04 therefore lands as a **new body sub-step** in
`skills/forge-5-loop/SKILL.md` — `### 1g. Stranded-Work Pre-flight` — placed **after** `### 1f.
Branch Pre-flight` (`SKILL.md:114`) and **before** `## Step 2` (`SKILL.md:118`). Its exact
text is §5. rauf's own refusal remains the backstop for the non-recovery case (a dirty tree
with no prior-run state).

## 5. The `### 1g` body sub-step — verbatim text (REQ-TREE-04)

Insert the following between `### 1f. Branch Pre-flight` and `## Step 2: Construct the Loop
Command` in `skills/forge-5-loop/SKILL.md`. It is host-neutral, compact (~5 real body lines
against the 287/300 → ≈293/300 budget, `01` §5), and names the previous run so the next
launch's precondition failure is specific, not a generic "uncommitted changes":

```markdown
### 1g. Stranded-Work Pre-flight (if using git)

Run `git status --porcelain`. If it reports changes **and** `{backlogDir}/{loopRunner.stateDir}/state.json` exists from a previous run, **STOP**: name that run (its `startedAt`, `currentItem`, and `blockedItems` from `state.json`) and point the user at the **Post-Run Tree Reconciliation** section of `references/recovery-procedure.md` to commit / stash / discard the stranded work before relaunch — never auto-pass `--force`. If the tree is dirty with **no** prior-run `state.json`, keep today's behavior (surface it; let the user commit/stash or pass `--force`). A clean tree is silent. rauf's own launch refusal remains the backstop.
```

**Trigger table** (the sub-step's decision matrix):

| `git status --porcelain` | prior-run `state.json`? | Behavior |
|--------------------------|-------------------------|----------|
| empty | any | Silent — proceed to Step 2 (REQ-COMPAT-02) |
| dirty | **yes** | **STOP**, name the run, point at §4 reconciliation (REQ-TREE-04) |
| dirty | no | Today's behavior — surface it, user commits/stashes/`--force`; never auto-`--force` |

## 6. Pointer edits (REQ-DEC-04)

The undefined phrase "stage a post-run retry" is replaced by a **named, referenced
procedure** in the two contract surfaces that use it. Both edits are prose-only (no line-count
concern); the recovery-procedure.md path names the file by its canonical repo path.

### 6.1 `skills/forge-5-loop/references/runner-contract.md:183`

Within the `needs_human` bullet (the `AskUserQuestion` branch):

- **BEFORE:** *"…collect the user's answer via `AskUserQuestion` to **stage a post-run
  retry**, or (b) offer to **cancel the run early**…"*
- **AFTER:** *"…collect the user's answer via `AskUserQuestion` and **record it via
  `decision-record` now**, then run the **Post-Run Recovery Procedure**
  (`references/recovery-procedure.md`) after the run ends, or (b) offer to **cancel the run
  early** (also recorded via `decision-record` — a deferral)…"*

### 6.2 `references/ralph-loop-contract.md:61`

Within the "runner does not pause for human input" blockquote:

- **BEFORE:** *"…it cannot inject an answer and resume the set-aside item mid-run —
  resolution is a follow-up retry pass."*
- **AFTER:** *"…it cannot inject an answer and resume the set-aside item mid-run —
  resolution is the **Post-Run Recovery Procedure**
  (`skills/forge-5-loop/references/recovery-procedure.md`): record the answer via
  `decision-record` at the moment of collection, then drive recovery from the record after
  the run ends."*

**Live-event note:** because the pointer records at collection, the React-to-events path
(the `needs_human` handler) writes the decision the moment the operator answers — **even
mid-run**, before recovery ever starts (tech-spec §3.4). The record, not conversation
memory, is the durable substrate the post-run procedure reads back (REQ-DEC-05).

## 7. Carried citation table (REQ-OBS-01)

REQ-OBS-01 binds **every** report surface this procedure produces. The following table is
carried **verbatim** from `00-core-definitions.md` §9 (the master copy) into
`recovery-procedure.md`'s prose — every report surface names the authoritative source it
derived its claims from; a claim that source contradicts is a reportable defect.

| Report surface | Authoritative citation basis |
|---|---|
| Pending / starvation template (`03`) | `backlogSummary` counts + `backlog-topology` output over `listCommand` JSON; iteration counters from `state.json` (`iteration`/`maxIterations`) |
| Failed-recovery report (`04`, §2 step 6) | The per-item `listCommand` re-read — movers/non-movers named from item `status`, never aggregate counts |
| `resolved` outcome text (`03`) | The three gate evaluations: `decision-list --unapplied` (empty), `git status --porcelain` (empty), per-item re-read (all affected left `blocked`) |
| Consolidated blast-radius prompt (§2 step 3) | `backlog-topology --cluster` gated-subtree output (member ids + counts) |
| Tree-reconciliation presentation (§4) | `git status --porcelain` paths + `state.json`/`events.ndjson` run evidence, attributions explicitly presented as **candidates** |
| Step 2a depth line (`06`) | The same `backlog-topology` output (`maxChainDepth`) |

## Dependencies

Implement these first (delivery order per `01` §4 — DEC → TREE → UNB → OUT → …):

- `00-core-definitions.md` — the decision schema, `LoopOutcome`/`resolved`, the four module
  constants (`RECOVERY_MIN_RUNNER_VERSION`, `CLUSTER_JACCARD_THRESHOLD`, the two topology
  ratios), the error model, and the master citation table this doc carries.
- `02-decision-record.md` — `decision-record`/`decision-list`/`decision-apply` verbs (steps
  1, 4, 5) and the append-only / unapplied-set semantics (§3).
- `04-apply-and-unblock.md` — the version probe, `rauf backlog answer` / degraded
  `rauf backlog unblock` apply mechanism (step 5), and the per-item unblock proof (step 6).
- `06-clustering-and-topology.md` — `compute_topology` + `cluster_blocked` + the
  `backlog-topology --cluster` output shape (steps 2, 3, §4 blast-radius framing).
- `03` — the `resolved` route/text/ladder + directive-matrix ripple that step 7 selects into.
- `07-testing-strategy.md` — the observed-incident replay that exercises this procedure
  end-to-end (SC-1).

## Verification

An implementation of `recovery-procedure.md` + the `### 1g` sub-step + the pointer edits
matches this spec when:

- [ ] `recovery-procedure.md` documents all seven steps in order, each naming its exact CLI,
      its decision point, its output, and its error behavior (§2).
- [ ] **Clean-tree silence (REQ-COMPAT-02):** a run with an empty `decision-list --unapplied`,
      no blocked/needs-human items, and a clean `git status --porcelain` produces **no** new
      prompt and **no** new operator decision — only `06`'s Step 2a depth line differs from a
      pre-change baseline (SC-4).
- [ ] **Every branch records (REQ-DEC-06):** answered, deferred, and cancel-early each write a
      `decision-record` entry **before** step 5 acts; cancel-early records a deferral
      (`answer: null`, `deferred: true`), not a distinct form.
- [ ] **Consolidated prompt (REQ-CLU-02/03/04):** a cluster of ≥2 produces exactly one
      `AskUserQuestion` naming every member id and the gated-subtree size ("gates N/M"), and
      its answer records one entry per member sharing a `clusterId`; members stay independently
      re-decidable.
- [ ] **Fresh-session re-entry (REQ-DEC-06):** an unapplied answered entry from a prior session
      is applied on the next launch **without** re-prompting; an unapplied deferral re-surfaces
      as an open decision.
- [ ] **Discard needs its own confirmation (REQ-TREE-03):** no dirty path is discarded without a
      second, dedicated confirmation prompt; discard is never a default option.
- [ ] **Attribution degrades, never aborts (REQ-TREE-01/02):** a missing/unparseable
      `state.json`/`events.ndjson` still detects the dirty tree and routes all changes into the
      single consolidated unattributed decision.
- [ ] **`### 1g` stops only with prior-run state (REQ-TREE-04):** a dirty tree **with**
      `{stateDir}/state.json` STOPS and names that run (`startedAt`/`currentItem`/`blockedItems`);
      a dirty tree **without** prior-run state keeps today's surface-and-continue behavior; a
      clean tree is silent. The `### 1g` heading sits between `1f` and `## Step 2` and stays
      within the body-cap budget (`01` §5).
- [ ] **`resolved` gate is all-three (REQ-OUT-03):** step 7 selects `resolved` **only** when
      `decision-list --unapplied` is empty, `git status --porcelain` is clean, **and** the
      per-item re-read shows every affected item left `blocked`/`needsHuman`; any one failing
      falls the ladder through to `needs-human`/`blocked`.
- [ ] **Failed-recovery honesty (REQ-REL-02, REQ-UNB-03):** a runner apply error stops before
      step 6 (failed apply); a ran-but-a-non-mover is a step-6 failed recovery naming movers and
      non-movers — neither is ever reported as `resolved`.
- [ ] **Pointer edits (REQ-DEC-04):** `runner-contract.md:183` and `ralph-loop-contract.md:61` no
      longer contain "stage a post-run retry" / "follow-up retry pass" as undefined phrases; both
      name the Post-Run Recovery Procedure and `decision-record` at collection.
- [ ] **Citation table carried verbatim (REQ-OBS-01):** the §7 table in `recovery-procedure.md`
      is byte-identical to `00` §9, and every report surface's prose names its listed source.
