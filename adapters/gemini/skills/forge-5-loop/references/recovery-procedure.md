# forge-5-loop — Post-Run Recovery Procedure

The named procedure that turns a needs-human / blocked loop stop into a resumable backlog
without losing the operator's decision. It runs **after** a loop run ends — entered
**unconditionally** from SKILL Step 4c on every run close, whatever the counts say (the
`needs_human` / `item_blocked` live-event handling in `runner-contract.md` collects
answers early for it, but is **not** the entry condition) — and it runs again as the
**re-entry point** on a fresh session (§3).
Its seven ordered steps: **enumerate → cluster → consolidated prompts →
record-at-collection → apply → prove → gate & exit**.

Notation: `{backlogDir}` is the resolved backlog directory (SKILL Step 2b);
`{stateDir}` is the effective-config `loopRunner.stateDir` (default `.rauf`); `$R` is the
plugin root the SKILL's bootstrap prelude resolves; runner commands are the substituted
`loopRunner.*Command` forms with the SKILL's token substitution (`{bin}` etc.).

## 1. Scope and the failure rule

The procedure orchestrates scripted substrate; it never improvises state. Decisions live
in `{backlogDir}/{stateDir}/forge-decisions.json` — append-only, written **only** by the
`decision-record` / `decision-list` / `decision-apply` verbs of
`scripts/forge-session.py` (schema: `references/forge-decisions-schema.json`), never by
hand. Being under the git-ignored state dir, the record survives session end and context
clear but never dirties the working tree that §4 inspects.

**The failure rule (applies to every step).** Any scripted step that exits non-zero, and
any runner invocation that errors or returns unparseable output, is surfaced **verbatim**
and **STOPS** the procedure with a **failed recovery** report — never reported as
recorded/succeeded. A failed *apply* (step 5) is distinguishable from a
ran-but-nothing-moved *proof* failure (step 6) because the former never reaches step 6
(§6).

## 2. The seven steps

### Step 1 — Enumerate

- **Input:** `{backlogDir}`; the runner's authoritative item list.
- **CLI:**
  ```
  python3 "$R/scripts/forge-session.py" decision-list --backlog-dir {backlogDir} --unapplied --json
  {bin} backlog list . --backlog {backlogDir} --json      # the substituted listCommand
  ```
  The unapplied set is the **latest entry per `itemId` with `appliedAt == null`** —
  deferrals included, applied items excluded.
- **Decision point:** if the unapplied set is **empty** and no item is
  `blocked`/`needsHuman`, there is nothing to decide or apply: **skip steps 2–6 and go
  straight to step 7 — never exit around it.** Step 7's §4 tree reconciliation still
  runs (it is what catches work stranded without any signal), and its `resolved` gate
  does not apply — **an empty affected set never selects `resolved`**; the SKILL Step 7
  ladder falls through to its count-based rungs. Combined with the clean-tree silence
  of §4.1, this keeps a happy-path run free of any new prompt; the only new happy-path
  output is the Step 2a depth line.
- **Output:** the unapplied-decision set (each entry's `itemId`, `question`,
  `answer|null`, `deferred`, `clusterId?`), and the live blocked/needs-human item set.
- **Error:** a `decision-list` exit 2 (unknown dir, unparseable record) stops the
  procedure. A failed `listCommand` read stops it as a failed recovery.

### Step 2 — Cluster

- **Input:** the blocked/needs-human items from step 1, each carrying its
  `blockedReason` (where the runner lands the `RAUF_NEEDS_HUMAN:<reason>` text).
- **CLI:**
  ```
  python3 "$R/scripts/forge-session.py" backlog-topology --items-stdin --cluster --json  < items.json
  ```
  fed the **same** `listCommand` JSON already obtained (single data source — never a
  `backlog.json` path). Returns `clusters[]`: each with `memberIds`, `memberReasons`,
  `sharedTokens`, and the **union** of members' gated subtrees (`gatedIds` +
  `gatedCount`).
- **Decision point:** you **may merge or refine** candidate clusters by judgment —
  under-clustering is the deliberately-chosen failure direction of the scripted helper,
  so its clusters are a floor, not a ceiling. You have no scripted *split* authority.
- **Output:** the final cluster set (scripted candidates ± your merges), each with its
  member ids and blast-radius numbers.
- **Error:** a `backlog-topology` exit 2 stops the procedure.

### Step 3 — Consolidated prompts

- **Input:** the final cluster set from step 2.
- **Mechanism:** the host's question mechanism (never inline prose).
  - For any cluster of **two or more** items: emit **exactly one** consolidated question
    that **names every affected item id** and states the **full gated subtree** the
    cluster gates. Frame it by **blast radius** — e.g. *"This one decision gates 13 of
    16 backlog items (items 2, 3, …). Answer it once."* — never one prompt per member.
  - Singleton clusters prompt per item (today's per-item shape).
- **Security:** prompts **MUST NOT solicit secrets**. Ask for the *decision* (which
  path, which policy), never a credential/token/key value. The decision record has no
  credential-shaped field and is treated as repo-visible content.
- **Decision point:** the operator may **answer**, **defer** the decision, or request
  **cancel the run early** — all three branches proceed to step 4 (nothing is acted on
  before it is recorded).
- **Output:** per cluster/item, one of {answer text, deferral, cancel-early}.
- **Citation:** the blast-radius framing is derived from `backlog-topology --cluster`
  gated-subtree output (member ids + counts) — the prompt cites that source; a
  "gates N/M" claim the topology output contradicts is a defect.

### Step 4 — Record at collection

- **Input:** every branch outcome from step 3.
- **CLI (one call per decision, BEFORE anything is applied):**
  ```
  # answered singleton
  python3 "$R/scripts/forge-session.py" decision-record --backlog-dir {backlogDir} \
      --item ID --question "Q" --answer "A"
  # deferred, or cancel-early (both record a deferral: no --answer)
  python3 "$R/scripts/forge-session.py" decision-record --backlog-dir {backlogDir} \
      --item ID --question "Q" --deferred
  # consolidated answer: one entry per affected item, shared clusterId
  python3 "$R/scripts/forge-session.py" decision-record --backlog-dir {backlogDir} \
      --item ID1 --item ID2 --item ID3 --question "Q" --answer "A" --cluster c1
  ```
  (`--actor` defaults to `forge-5-loop@<host>` — a machine label, never user identity.)
- **Decision point:** a decision is recorded on **every** branch — answered, deferred,
  **and** cancel-early — and it is recorded **before** step 5 acts on anything. A
  cancel-early is recorded as a **deferral** (`answer: null`, `deferred: true`,
  `question` carrying the original needs-human text) — there is no third entry form. A
  recorded-but-unapplied entry (`appliedAt == null`) is exactly what step 1 re-surfaces
  on the next launch (§3).
- **Consolidated:** one entry per affected item, all sharing one `clusterId` (minted
  `c` + lowest member id). Items stay **independently re-decidable**: a later per-item
  entry supersedes the cluster entry for that item only.
- **Output:** durable append-only entries in `forge-decisions.json`; the write is
  atomic.
- **Error:** any `decision-record` exit 2 (both/neither of `--answer`/`--deferred`,
  unknown dir, failed atomic write) is surfaced verbatim and stops the procedure. The
  answer is **not** applied if it was not recorded.

### Step 5 — Apply

- **Version probe (once, at the start of this step):** run the substituted
  `loopRunner.versionCommand` (default `{bin} version --json`), parse
  `{ "version": "<semver>" }`, and numerically semver-compare it against
  `RECOVERY_MIN_RUNNER_VERSION` (a `scripts/forge-session.py` module constant, `0.14.0`
  — the capability threshold for `{bin} backlog answer`; **not**
  `loopRunner.minRunnerVersion`, which stays the launch floor). A probe miss
  (missing/old/unparseable version) is **never** a hard failure — it selects the
  degraded path and is reported with `loopRunner.installHint`.
- **Apply per item** (full dispatch table in §5):
  - needs-human item, runner **≥** threshold →
    `{bin} backlog answer . {id} "{answer}" --backlog {backlogDir} --json`
    (the answer text is threaded into the next iteration's prompt).
  - needs-human item, runner **<** threshold → **degraded path:**
    `{bin} backlog unblock . {id} --backlog {backlogDir} --json` — the item is genuinely
    unblocked and the answer stays durable in `forge-decisions.json`, but the recovery
    report **must state explicitly** that the answer was **not** injected into the next
    iteration's prompt, with the `installHint` upgrade hint attached.
  - plain (non-needs-human) blocked item → `{bin} backlog unblock` at **every** runner
    version.
- **Stamp:** after each runner apply **succeeds**, run
  ```
  python3 "$R/scripts/forge-session.py" decision-apply --backlog-dir {backlogDir} --item ID
  ```
  which stamps `appliedAt`/`appliedBy` on the item's latest entry. `decision-apply` is
  called **only after** the runner apply returned success — a stamped record means the
  runner actually accepted the change.
- **Error:** a runner apply that **errors** (non-zero exit — item missing, not
  `blocked`, or any failure) is a **failed apply**: surface it verbatim, do **not** call
  `decision-apply`, stop the procedure, report failed recovery. This is distinct from a
  version-probe miss (which routes to the degraded path, not a failure) and from step
  6's ran-but-nothing-moved failure (§6).

### Step 6 — Prove

- **Input:** the affected item set that step 5 applied.
- **CLI:** re-read per-item state via the substituted `loopRunner.listCommand`
  (`{bin} backlog list . --backlog {backlogDir} --json`) and test **each** affected
  item: `status != "blocked"` — which, per the runner's derivation
  (needs-human ⇔ `status=="blocked" && needsHuman==true`), also removes it from the
  needs-human count, so the single test covers both flags. Aggregate `backlogSummary`
  counts are **never** the test. An affected item **missing** from the re-read counts
  as a non-mover.
- **Decision point:** **all** affected items moved → proceed to step 7. **Any**
  non-mover — including a partial move where some items moved and others did not — is a
  **failed recovery**: report it, **naming the movers and the non-movers** from their
  item `status` fields.
- **Output:** either "all moved → continue" or a failed-recovery report.
- **Citation:** the movers/non-movers are named from the per-item `listCommand` re-read
  (`status` fields), never from aggregate counts — a report that contradicts the
  per-item read is a defect.

### Step 7 — Gate & exit

- **Tree reconciliation first.** Before any outcome is selected, run the **Post-Run
  Tree Reconciliation** section (§4). It runs on every recovery pass — including passes
  with no needs-human items — and is silent on a clean tree.
- **Evaluate the `resolved` gate — all three must hold:**
  1. `decision-list --unapplied` is **empty for the affected items**. The verb returns
     the **global** latest-unapplied-per-item set, so **intersect** that payload's
     entries (each carries `itemId`) with this session's affected-item set and test
     only that intersection for emptiness — an unrelated item's stray deferral must not
     suppress a legitimate `resolved`.
  2. `git status --porcelain` is **clean** (git-ignored `{stateDir}` artifacts are
     invisible to porcelain — the exclusion holds by construction).
  3. the per-item re-read (step 6) shows **every** affected item left
     `blocked`/`needsHuman`.
- **Select the outcome:** on all-three-pass, select `resolved` — the first rung of the
  ladder in `result-reporting.md`, so a resolved stop never re-triggers the needs-human
  branch its own recovery just cleared. **Any one gate failing falls the ladder
  through** to `needs-human` / `blocked` / `deferred` / `partial` / `complete` exactly
  as today. `resolved` routes **resume** — its NEXT-STEPS block fences
  `/feature-forge:forge-5-loop {feature}`, never the navigator.
- **CLI:** the close runs through the Scripted Stage Exit (SKILL Step 7):
  `stage-exit … --outcome resolved …`. `stage-exit` does **not** re-verify the gate
  server-side (it has no runner access) — enforcement is procedural: this step.
- **Citation:** the `resolved` outcome text cites the three gate evaluations
  (`decision-list --unapplied` empty, porcelain empty, per-item re-read all-moved).
  Claiming `resolved` without those preconditions is a reportable defect.

## 3. Fresh-session re-entry

The procedure is the **re-entry point** on a fresh session / next launch — this is what
makes a decision survive session end and context clear.

On a new session, **step 1** enumerates every entry with `appliedAt == null` from a
*previous* session — answered-but-not-yet-applied decisions, deferrals, and cancel-early
deferrals alike. Those entries are re-surfaced:

- An entry that already carries an **answer** (`answer != null`, `deferred == false`,
  `appliedAt == null`) **skips step 3's prompt** for that item — the operator already
  decided; the procedure proceeds straight to step 5 (apply) and step 6 (prove). The
  answer collected last session is applied this session without re-asking.
- A **deferral** (`deferred == true`) re-surfaces through step 3 as an open decision —
  the operator is asked again, and their new answer appends a **new** entry
  (append-only); the deferral's audit fields are never destroyed.

Because entries are durable and untracked, a session boundary, crash, or context clear
between "operator answered" and "answer applied" never costs the decision — step 1 of
the next launch finds it.

## 4. Post-Run Tree Reconciliation

Invoked from step 7 after the run ends and **before** any outcome is selected. It runs
on **every** recovery pass — including passes with no needs-human items, which step 1
routes here directly, and SKILL Step 4c enters the procedure on every run close —
because it is the "tree" half of recovery. Four sub-steps.

### 4.1 Detect

- **CLI:** `git status --porcelain`.
- **Clean tree → SILENT.** Empty output ⇒ no prompt, no output, no operator decision.
  The decision record and all runner state under `{stateDir}` are git-ignored and
  therefore never appear in porcelain output — decision writes never dirty the tree
  this step inspects.
- **Dirty tree → proceed to 4.2.**
- **Error:** a `git status` failure (not a git repo, git error) is surfaced verbatim;
  reconciliation is skipped (there is nothing git-native to reconcile), the rest of the
  procedure continues.

### 4.2 Attribute (best-effort, runner-native)

Best-effort attribution of dirty paths to the backlog item(s) that produced them, from
runner-native evidence — reliable per-item provenance is **not** a prerequisite.

- **Read `{backlogDir}/{stateDir}/state.json`** (the runner's loop state):
  `baseCommitHash` (the HEAD captured at run start — the baseline for
  `git log {baseCommitHash}..HEAD`), `completedItems` / `blockedItems` (item ids that
  finished / blocked), `currentItem` (the item in flight when the run stopped — a
  strong candidate for uncommitted changes), `startedAt` and
  `iteration`/`maxIterations` (run identity + budget).
- **Read `{backlogDir}/{stateDir}/events.ndjson`** — one JSON object per line; parse
  line-by-line (there is **no** runner CLI for events; the file is read directly). The
  per-iteration `item_selected`, `llm_spawned`, and `llm_exited` records — each
  carrying an `itemId` and a `timestamp` — name which items ran during the window and
  in what order.
- **Map dirty paths → candidate items:** the `currentItem` and the most recent
  `item_selected`/`llm_spawned` without a matching clean `llm_exited` are the items "in
  flight when the run died"; `git log {baseCommitHash}..HEAD` names what was already
  committed for which item (the runner commits `[rauf] <id>: <title>`). Present the
  mapping as **CANDIDATES, never asserted**.
- **Degradation (detection never aborts):** if `state.json` or `events.ndjson` is
  missing, unreadable, or unparseable, **degrade** to the fully-unattributed path —
  everything goes into 4.3's single consolidated decision. Detection (4.1) is never
  aborted by an evidence-parse failure.
- **Citation:** the presentation cites `git status --porcelain` paths +
  `{stateDir}/state.json` / `events.ndjson` run evidence, with every attribution
  explicitly labelled a **candidate**.

### 4.3 Decide

- **Mechanism:** the host's question mechanism (never inline prose).
  - **One question per attributed item-group:** for each candidate item-group from 4.2,
    offer **commit-for-that-item** / **stash** / **discard**.
  - **Unattributable changes → ONE consolidated decision:** everything that could not
    be attributed is presented as a single grouped question, not dropped.
- **Discard guard:** **discard is NEVER the default** and requires its **own explicit
  confirmation** — a second, dedicated question via the host's question mechanism confirming the specific paths
  to be discarded before any `git checkout`/`git restore`/`git clean` runs. No path is
  discarded on a single click.
- **Output:** per group, an executed reconciliation (commit / stash / confirmed
  discard) or a deferral the operator can revisit.

### 4.4 Launch blocker

The next launch's `### 1g. Stranded-Work Pre-flight` (SKILL Step 1) STOPS on a dirty
tree when a prior run's `{backlogDir}/{stateDir}/state.json` exists, names that run
(its `startedAt`, `currentItem`, `blockedItems`), and points at this section to
commit / stash / discard the stranded work before relaunch. The runner's own
uncommitted-changes launch refusal remains the backstop for a dirty tree with no
prior-run state.

## 5. Apply-mechanism dispatch (version gate & the degraded path)

| Runner version | Item kind | Apply mechanism | What the report says |
|---|---|---|---|
| `≥ RECOVERY_MIN_RUNNER_VERSION` | needs-human (has an answer) | `{bin} backlog answer . {id} "{answer}" --backlog {backlogDir} --json` | Answer applied and threaded into the next iteration's prompt. |
| `≥ RECOVERY_MIN_RUNNER_VERSION` | plain blocked | `{bin} backlog unblock . {id} --backlog {backlogDir} --json` | Item unblocked. |
| `< RECOVERY_MIN_RUNNER_VERSION` (or probe miss) | needs-human | **DEGRADE:** `{bin} backlog unblock . {id} --backlog {backlogDir} --json` | Item unblocked; **answer was NOT injected into the next prompt** (durable in `forge-decisions.json`); `{installHint}` — upgrade to a runner that ships `backlog answer` to thread it. |
| any version (incl. probe miss) | plain blocked | `{bin} backlog unblock . {id} --backlog {backlogDir} --json` | Item unblocked. |

Key properties:

- **Plain blocked items always use `unblock`, at every version** — they carry no answer
  to thread. The version gate only ever changes the needs-human path.
- **The degraded needs-human path genuinely unblocks** (the runner clears
  `status`/`blockedReason`/`needsHuman`/`deferred`), so recovery works across the whole
  supported runner floor. The only capability lost below the threshold is
  prompt-threading — the answer remains durable in the decision record and re-surfaces
  via `decision-list --unapplied` if re-decided.
- **The report is honest either way:** the degraded path states explicitly that the
  answer was not threaded, with the upgrade hint.

## 6. Failure taxonomy

| Failure | When it occurs | Reaches the step-6 per-item test? | Report |
|---|---|---|---|
| **Failed apply** | `{bin} backlog answer` / `unblock` exits non-zero (corrupt backlog, I/O error, not-blocked/not-found refusal); or the post-apply re-read is unparseable | **No** — stops *before* the test | Verbatim runner error + which item; **failed recovery**; procedure stops; never claimed succeeded |
| **Ran-but-nothing-moved** | Every apply exited 0, but the step-6 per-item test finds a non-mover | **Yes** — *is* the test failing | Movers/non-movers named from `status` fields; **failed recovery** |
| **Version-probe miss** | `versionCommand` missing/unparseable, or version `< RECOVERY_MIN_RUNNER_VERSION` | N/A — selects the degraded path (§5) | Degraded path proceeds; not-threaded caveat + `installHint`; **not** a failed recovery |

Rules: never report recorded/succeeded past a failed step; a failed apply stops before
the per-item test, so a runner that errored is never conflated with a runner that ran
cleanly but moved nothing; `decision-apply` is not called for a failed item — the record
stays unapplied and re-surfaces next launch; a probe miss degrades, it never fails
recovery.

## 7. Report citations (REQ-OBS-01)

Every report surface this procedure produces names the authoritative source it derived
its claims from; a claim that source contradicts is a reportable defect. Each report
surface names the authoritative source it derives its claims from:

| Report surface | Authoritative citation basis |
|---|---|
| Pending / starvation template | `backlogSummary` counts + `backlog-topology` output over `listCommand` JSON; iteration counters from `state.json` (`iteration`/`maxIterations`) |
| Failed-recovery report (§2 step 6) | The per-item `listCommand` re-read — movers/non-movers named from item `status`, never aggregate counts |
| `resolved` outcome text | The three gate evaluations: `decision-list --unapplied` (empty), `git status --porcelain` (empty), per-item re-read (all affected left `blocked`) |
| Consolidated blast-radius prompt (§2 step 3) | `backlog-topology --cluster` gated-subtree output (member ids + counts) |
| Tree-reconciliation presentation (§4) | `git status --porcelain` paths + `state.json`/`events.ndjson` run evidence, attributions explicitly presented as **candidates** |
| Step 2a depth line | The same `backlog-topology` output (`maxChainDepth`) |
