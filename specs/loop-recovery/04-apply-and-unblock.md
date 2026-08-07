# 04 — Recovery Apply & Unblock

> **The MECHANISM by which a recorded decision becomes a runnable backlog item, and
> the proof that it did.** This document owns the apply side of recovery: which runner
> surfaces can and cannot thread an operator's answer into the next iteration, the one
> new `rauf backlog answer` subcommand that closes that gap, how the forge side
> capability-gates it (never hard-failing on version), the per-item re-read that proves
> the affected items actually left `blocked`/`needsHuman`, and the error model that keeps
> a failed apply from ever being reported as success. The **orchestration** that calls
> these steps in sequence — enumerate → cluster → prompt → record → **apply** → **prove**
> → gate — lives in `05-recovery-procedure.md`; this document is the contract for the
> apply and prove steps it invokes. All shared types, the error/exit contract, and
> `RECOVERY_MIN_RUNNER_VERSION` come from `00-core-definitions.md`; the `decision-apply`
> verb and the unapplied read-back come from `02-decision-record.md`.

## Requirement Coverage

| REQ ID | Requirement | Section |
|--------|-------------|---------|
| REQ-UNB-01 | Recovery unblocks affected items as a required step (runner op, not prose) | §2, §4, §5, §6.4 |
| REQ-UNB-02 | Per-item re-read verifies each affected item left `blocked`/`needsHuman`; aggregate counts are never the test | §6 |
| REQ-UNB-03 | Success only when **every** affected item moved; partial = failed recovery, naming movers and non-movers | §6, §7 |
| REQ-DEC-04 | Named procedure reads the record back and drives apply from it (replaces "stage a post-run retry") | §5.4, §6.4 |
| REQ-DEC-05 | Apply consumes the first-class unapplied read-back (`decision-list --unapplied`) | §5.4, §6.4 |
| REQ-REL-01 | Single-writer apply: one session drives the apply loop; no locking | §1.3, §5.4 |
| REQ-REL-02 | Any failed apply / unavailable-at-version / unparseable read-back surfaced verbatim, never claimed succeeded; failed apply distinguishable from ran-but-nothing-moved | §5.3, §7 |

---

## 1. Scope & Dependencies

### 1.1 What this document owns

The **apply** and **prove** mechanism of the Post-Run Recovery Procedure:

1. The capability-gap analysis that justifies a new runner surface (§2).
2. The alternatives considered as the primary apply path, and why each is rejected (§3).
3. The new `rauf backlog answer` subcommand — the one cross-repo surface (§4).
4. Version gating and the degraded fallback — how the forge side selects a mechanism per
   item without ever hard-failing recovery on runner version (§5).
5. The per-item unblock proof that governs REQ-UNB-02/-03 and feeds the `resolved` gate (§6).
6. The apply-side error model (§7).

### 1.2 What this document does NOT own

- **Orchestration / sequencing** — the order enumerate → cluster → prompt → record →
  apply → prove → gate, the prompts, tree reconciliation, and the `resolved` gate
  evaluation live in `05-recovery-procedure.md`. This document specifies only the apply
  and prove steps that procedure invokes (its steps 5 and 6).
- **The decision record surface** — `decision-record` / `decision-list` / `decision-apply`
  and the `forge-decisions.json` schema are owned by `02-decision-record.md`. This
  document consumes `decision-apply` (the applied-stamp) and `decision-list --unapplied`
  (the set of items to apply for) but does not define them.
- **The `resolved` outcome, routing, and text** — owned by `03` and `00 §5`. This
  document produces the per-item proof result (b) of that gate; it does not select the
  outcome.
- **Topology / clustering** — owned by `06` / `00 §8`.

### 1.3 Dependencies (see the `## Dependencies` section for ordering)

- `00-core-definitions.md §6.2` — `RECOVERY_MIN_RUNNER_VERSION: Final[str] = "0.14.0"`,
  the forge-side capability threshold (NOT `loopRunner.minRunnerVersion`, which stays `0.6.0`).
- `00-core-definitions.md §7` — the error model (0/2 exit for verbs; recovery-procedure
  verbatim-and-stop for runner failures; failed-apply vs ran-but-nothing-moved distinction).
- `00-core-definitions.md §10` — `loopRunner` config surface (`versionCommand`,
  `listCommand`, `installHint`, `stateDir`, `minRunnerVersion`).
- `02-decision-record.md` — `decision-apply --backlog-dir D --item ID` (the applied stamp,
  §5.4) and `decision-list --backlog-dir D --unapplied --json` (the REQ-DEC-05 read-back,
  the set this document applies for).
- **rauf repo** (separate release train) — the new `rauf backlog answer` subcommand (§4),
  and the existing `rauf backlog unblock` / `rauf backlog list` surfaces (§2, §6).
- **REQ-REL-01 single-writer:** the apply loop runs in one forge session driving one
  backlog. No locking is used or wanted; concurrent multi-session apply is out of scope.

---

## 2. Capability gap analysis — what the existing surfaces can and cannot do

REQ-UNB-01 requires "the runner's unblock operation, **or** an equivalent relaunch flag"
as a required step. The unblock operation already exists and fully satisfies the *unblock*
half. What no existing non-relaunching surface can do is thread the operator's answer into
the next iteration's prompt — and that threading gap is the entire rationale for the one
new surface in §4.

### 2.1 `rauf backlog unblock` — unblocks, but cannot thread an answer

Verified in the rauf source
(`packages/core/src/backlog.ts:436-470`, `unblockItems`):

```ts
// backlog.ts:455-465 (single-item mode)
if (item.status !== "blocked") {
  return err({ code: ErrorCodes.VALIDATION_ERROR,
    message: `Item ${itemId} is not blocked (status: ${item.status})`,
    details: { itemId, currentStatus: item.status } });
}
item.status = "pending";
delete item.blockedReason;   // backlog.ts:463
delete item.needsHuman;      // backlog.ts:464
delete item.deferred;        // backlog.ts:465
```

`rauf backlog unblock <path> [id]`
(CLI handler `packages/cli/src/backlog-commands.ts:945-986`, `handleBacklogUnblock`;
registered `packages/cli/src/commands.ts:327-331`) clears `status` → `pending`,
`blockedReason`, `needsHuman`, and `deferred` for the item, returning
`{ unblockedCount, unblockedIds }`. Its header comment
(`backlog.ts:431-433`) confirms it targets exactly the `RAUF_NEEDS_HUMAN` shape
(`status="blocked" + needsHuman`). This has been available since well below the `0.6.0`
floor, so it **fully satisfies REQ-UNB-01** at every supported runner version.

**What it cannot do:** it never writes `humanAnswer`. There is no code path in
`unblockItems` that sets the answer field, so the operator's answer text is not carried
anywhere the next iteration reads it.

### 2.2 The `humanAnswer` threading gap

The next iteration only sees an operator answer if the item carries a `humanAnswer` field:

```ts
// packages/loop/src/prompt-builder.ts:217-220
if (item.humanAnswer) {
  // …answer is appended into the item's iteration prompt…
${item.humanAnswer}`);
}
```

`humanAnswer` is written **only** by `resume --answer`'s injection block
(`packages/cli/src/resume-commands.ts:295-318`, the `updateItem(...)` at lines 302-307)
and is auto-cleared on completion (`backlog.ts:254-259`, so a reused item id never
re-injects a stale answer). `updateItem` (`backlog.ts:179-183`,
`updateItem(paths, itemId, updates): Result<BacklogItem>`) writes `humanAnswer` via the
`updates.humanAnswer !== undefined` path at `backlog.ts:245`.

**Conclusion:** unblocking and answer-threading are two distinct effects. `unblock`
delivers the first; only `resume --answer` delivers the second, and it always relaunches
(§3.1). The gap — a non-relaunching surface that threads the answer — is what §4 fills.

---

## 3. Alternatives considered & rejected (as the primary apply path)

Per PRD §5 ("SHOULD prefer forge-side / existing runner surfaces"), each existing surface
was evaluated as the primary apply mechanism before spending the pre-authorized rauf change.

### 3.1 `rauf resume --answer <id> "<text>"` — rejected

Performs the exact apply wanted (it is the injection block §4 is modeled on) but **always
relaunches when eligible items remain** (`resume-commands.ts:288-347`: the same lock is
held across injection *and* the relaunch decision; `relaunch` is set when
`detection.nonDone > 0`). Two problems:

1. It conflicts with the fenced-relaunch exit model — `resolved` routes **resume** (`03`,
   `00 §5.2`), where the operator, not the procedure, launches the next run.
2. It makes the REQ-OUT-03 `resolved` gate **unevaluable before launch**: the procedure
   must prove the affected items left `blocked` (§6) *before* selecting an outcome, but
   `resume --answer` would have already relaunched by then.

### 3.2 `rauf backlog unblock` + restating the answer in `notes`/`description` — rejected

Works at today's floor (`rauf backlog edit` writes `notes`), but:

- It **pollutes a permanent field** — `notes`/`description` have no auto-clear analogous
  to `humanAnswer`'s (`backlog.ts:254-259`), so the answer persists into unrelated future
  iterations of a reused id.
- There is no dedicated prompt section for it; the answer is buried in item metadata.

It is kept only as the **shape** of the degraded path (§5.2) — `unblock` per item — **minus
the field pollution**: in the degraded path the answer stays durable in
`forge-decisions.json` (`00 §4`) and is never restated into a backlog field.

### 3.3 `rauf loop run . --retry-blocked` — rejected

Unblocks **all** blocked items indiscriminately at launch, and only *after* an outcome was
already selected. It is a useful operator-facing relaunch convenience, not a per-item,
pre-gate apply step: it cannot target only the affected (answered) items, and it runs on
the wrong side of the outcome decision.

**Decision (D4):** spend the PRD §5 pre-authorization on exactly one new surface — a
non-relaunching, per-item, apply-only twin of `resume --answer`'s injection block — and
degrade to `unblock` below its version threshold.

---

## 4. The new rauf surface — `rauf backlog answer` (TypeScript, rauf repo)

`rauf backlog answer <path> <id> "<text>" [--backlog <dir>] [--json]` — the apply-only twin
of `resume --answer`'s injection block, with **no relaunch**. It lands in
`packages/cli/src/backlog-commands.ts` and registers in the `backlog` subcommand table in
`packages/cli/src/commands.ts:299-332`, modeled exactly on `handleBacklogUnblock`
(`backlog-commands.ts:945-986`).

### 4.1 Registration

Add one entry to the `backlog` command's `subcommands` array
(`packages/cli/src/commands.ts`, alongside the `unblock` entry at `:327-331`):

```ts
{
  name: "answer",
  description: 'Apply a human answer to a blocked item (no relaunch): thread the answer '
    + 'into the next run and re-queue the item to pending',
  usage: 'rauf backlog answer <path> <id> "<text>" [--backlog <dir>] [--json]',
  handler: handleBacklogAnswer,
},
```

### 4.2 Handler

```ts
// packages/cli/src/backlog-commands.ts — new export, modeled on handleBacklogUnblock
// Imports already present in this module: path, ExitCode (commands.js),
// updateItem + readBacklog (@rauf/core backlog), resolveBacklogRoot,
// resolveBacklogPaths, extractStringFlag, outputJson, error, info, success, handleCoreError.

export async function handleBacklogAnswer(ctx: CommandContext): Promise<number> {
  const targetPath = ctx.args[0];
  const itemId = ctx.args[1];
  const text = ctx.args[2];
  if (!targetPath || !itemId || text === undefined) {
    error("Missing required arguments: <path> <id> <text>");
    info('Usage: rauf backlog answer <path> <id> "<text>" [--backlog <dir>] [--json]');
    return ExitCode.USAGE;
  }

  const resolved = path.resolve(targetPath);
  const backlogFlag = extractStringFlag(ctx.flags, "backlog");
  const backlogRootResult = resolveBacklogRoot(resolved, backlogFlag ?? undefined);
  if (!backlogRootResult.ok) {
    error(backlogRootResult.error.message);
    return ExitCode.USAGE;
  }
  const pathsResult = resolveBacklogPaths(resolved, backlogRootResult.value);
  if (!pathsResult.ok) {
    error(pathsResult.error.message);
    return ExitCode.ERROR;
  }
  const paths = pathsResult.value;

  // Refuse unless the item is currently `blocked` — mirrors unblockItems'
  // not-blocked guard (backlog.ts:455-460) so `answer` and `unblock` reject
  // identically. Reading first also yields a precise "not found" vs "not blocked".
  const backlogResult = readBacklog(paths);
  if (!backlogResult.ok) return handleCoreError(backlogResult.error, ctx, resolved);
  const item = backlogResult.value.items.find((i) => i.id === itemId);
  if (!item) {
    error(`Item not found: ${itemId}`);
    return ExitCode.USAGE;
  }
  if (item.status !== "blocked") {
    error(`Item ${itemId} is not blocked (status: ${item.status})`);
    return ExitCode.USAGE;
  }

  // Apply-only twin of resume-commands.ts:302-307 — NO relaunch.
  const result = updateItem(paths, itemId, {
    humanAnswer: text,
    status: "pending",
    needsHuman: false,
    blockedReason: null,
  });
  if (!result.ok) return handleCoreError(result.error, ctx, resolved);

  if (ctx.globalFlags.json) {
    outputJson({ answered: itemId, status: "pending" });
    return ExitCode.SUCCESS;
  }
  success(`Answered ${itemId} — re-queued to pending with the answer threaded.`);
  return ExitCode.SUCCESS;
}
```

### 4.3 Contract

- **Effect:** `updateItem(paths, id, { humanAnswer, status: "pending", needsHuman: false,
  blockedReason: null })` — identical to `resume --answer`'s injection
  (`resume-commands.ts:302-307`), so the next iteration threads the answer via
  `prompt-builder.ts:217`. The `blocked → pending` transition is legal
  (`VALID_STATUS_TRANSITIONS.blocked = ["pending"]`, `packages/core/src/schemas.ts:379`;
  asserted `schemas.test.ts:1072`), so `updateItem`'s transition guard
  (`backlog.ts:202-214`) passes.
- **Precondition:** the item's current status MUST be `blocked`. Not-found → `USAGE` (2);
  not-blocked → `USAGE` (2) with `Item <id> is not blocked (status: <status>)` (mirrors
  `backlog.ts:455-460`). Any `USAGE`/`ERROR` exit is a **failed apply** for that item (§7).
- **No relaunch:** unlike `resume --answer` there is no `detectResumeState` /
  relaunch branch — the command returns after the write.
- **JSON output:** `{ "answered": "<id>", "status": "pending" }` (via `outputJson`,
  `packages/cli/src/formatter.ts:113`). Exit codes per `ExitCode`
  (`commands.ts:91-99`): `SUCCESS: 0`, `USAGE: 2`, `ERROR: 1`.
- **Ships:** the next rauf minor — assumed **0.14.0** (OTQ-2); pin
  `RECOVERY_MIN_RUNNER_VERSION` to the real release number at implementation time.
- **Tests** (rauf repo, see `07-testing-strategy.md`): happy path (JSON shape +
  `humanAnswer`/`status` written), not-blocked refusal (exit 2 + message), not-found
  refusal (exit 2), and a subcommand-registration assertion alongside the existing
  `backlog-commands.test.ts:1095` `expect(names).toContain("unblock")`.

---

## 5. Version gating & the degraded path (D8, decision V-001)

Recovery MUST work across the whole `≥ 0.6.0` floor and MUST NOT hard-fail on runner
version. The forge side selects the apply mechanism per item by probing the runner version
against `RECOVERY_MIN_RUNNER_VERSION` — a **new forge-side constant**, distinct from
`loopRunner.minRunnerVersion` (which stays `0.6.0`).

### 5.1 The probe (recovery-procedure prose, agent-orchestrated)

rauf has **no capability-negotiation surface**, so the compare is forge-side semver,
mirroring the existing agent-driven floor checks (`forge-5-loop` gate 1c at
`skills/forge-5-loop/SKILL.md:80-94`; `forge-4-backlog` at `SKILL.md:126-128`). The
recovery procedure (`05`) performs the probe **once** at the start of the apply step; no
new scripted `forge-session.py` verb is introduced (the compare reuses the gate-1c
precedent). The concrete algorithm the procedure executes:

```python
# Reference algorithm (executed by the recovery procedure, mirroring gate 1c).
# Input: `reported` = the `version` string from `rauf version --json`
#        (loopRunner.versionCommand); THRESHOLD = RECOVERY_MIN_RUNNER_VERSION ("0.14.0").
# Output: which apply mechanism to use for a needs-human item this session.

def _semver_ge(reported: str, threshold: str) -> bool:
    """Numeric major.minor.patch compare — never a string compare.

    Returns True iff `reported` >= `threshold`. A `v` prefix or a non-semver
    reported string is treated as a probe MISS (return False → degraded path);
    it is NEVER a hard failure of recovery (unlike gate 1c, which stops the run).
    """
    def parse(s: str) -> tuple[int, int, int] | None:
        s = s.lstrip("v")
        parts = s.split(".")[:3]
        try:
            nums = [int(p) for p in parts]
        except ValueError:
            return None
        nums += [0] * (3 - len(nums))
        return (nums[0], nums[1], nums[2])
    r, t = parse(reported), parse(threshold)
    return r is not None and t is not None and r >= t
```

The probe uses `loopRunner.versionCommand` (default `rauf version --json`) and parses
`{ "version": "<semver>" }` — always the `--json` form (plain `rauf version` prints a
`v`-prefixed human string). **Crucially, a probe miss is not a hard gate failure** (the
key difference from gate 1c): a missing/old/unparseable version does not stop recovery —
it selects the degraded path (§5.2) and is reported with the `installHint` upgrade hint.

### 5.2 Dispatch — mechanism per (version, item kind)

| Runner version | Item kind | Apply mechanism | What the report says |
|---|---|---|---|
| `≥ RECOVERY_MIN_RUNNER_VERSION` | needs-human (`blocked ∧ needsHuman`, has an answer) | `rauf backlog answer <path> <id> "<answer>" --backlog <dir> --json` | Answer applied and threaded into the next iteration's prompt. |
| `≥ RECOVERY_MIN_RUNNER_VERSION` | plain blocked (no needs-human answer) | `rauf backlog unblock <path> <id> --json` | Item unblocked. |
| `< RECOVERY_MIN_RUNNER_VERSION` (or probe miss) | needs-human | **DEGRADE:** `rauf backlog unblock <path> <id> --json` | Item unblocked; **answer was NOT injected into the next prompt** (durable in `forge-decisions.json`); `{installHint}` — upgrade to a runner that ships `backlog answer` to thread it. |
| any version (incl. probe miss) | plain blocked | `rauf backlog unblock <path> <id> --json` | Item unblocked. |

Key properties:

- **Plain blocked items always use `unblock`, at every version** — they carry no answer to
  thread, so there is nothing `answer` would add. The version gate only ever changes the
  needs-human path.
- **The degraded needs-human path genuinely unblocks** (`unblock` clears
  `status`/`blockedReason`/`needsHuman`/`deferred`, §2.1), so REQ-UNB-01..03 are
  **satisfiable across the whole `≥ 0.6.0` floor**. The only capability lost below the
  threshold is prompt-threading — the answer remains durable in the decision record
  (`00 §4`) and re-surfaces via `decision-list --unapplied` if re-decided.
- **The report is honest either way** (REQ-OBS-01, REQ-REL-02): the degraded path states
  explicitly that the answer was not threaded, with the upgrade hint.

### 5.3 A runner that *errors* vs a runner that *predates* the verb

These are different failures and are reported differently (REQ-REL-02):

- **Predates the verb** (version `< RECOVERY_MIN_RUNNER_VERSION`, or a probe miss): a
  *known, expected* condition → the degraded path (§5.2). Recovery proceeds; the report
  carries the not-threaded caveat + `installHint`. This is **not** a failed recovery.
- **Errors** (a non-zero exit from `rauf backlog answer` *or* `rauf backlog unblock` at any
  version — e.g. a corrupt backlog, an I/O failure, or a not-blocked/not-found refusal):
  a **failed apply** for that item → §7. The verbatim error surfaces, the procedure stops,
  and recovery is reported failed. Never claimed succeeded.

### 5.4 Apply ordering (REQ-DEC-04/05, REQ-UNB-01)

The apply step consumes the REQ-DEC-05 read-back and stamps the record **after** the runner
apply succeeds, so the audit trail never records an apply that did not happen:

1. `decision-list --backlog-dir D --unapplied --json` (`02 §5.4`) yields the set of items to
   apply for (latest unapplied entry per item, `00 §4.3`).
2. For each such item, run the dispatched mechanism (§5.2) — `answer` or `unblock`.
3. **Only if** that runner invocation exits 0, run
   `decision-apply --backlog-dir D --item ID` (`02 §5.4`), which stamps `appliedAt`/
   `appliedBy` on the latest entry for that item.
4. If the runner invocation exits non-zero, **do not** call `decision-apply` for that item
   — surface the error and stop (§7). The record stays unapplied and re-surfaces on the
   next launch (REQ-DEC-06).

This replaces the undefined "stage a post-run retry" phrase (REQ-DEC-04): the record is
read back (step 1) and drives apply (steps 2-3) from a named, referenced procedure (`05`).

---

## 6. The per-item unblock proof (REQ-UNB-02, REQ-UNB-03)

After **every** apply (whether via `answer` or `unblock`, at any version), the procedure
proves — per item — that the affected items actually left `blocked`/`needsHuman`. This test
is authoritative for REQ-UNB-02, REQ-UNB-03, and the `resolved` gate's precondition (c)
(`00 §5.2`).

### 6.1 Re-read via `listCommand` (never the aggregate summary)

Re-read authoritative per-item state with `loopRunner.listCommand`
(default `rauf backlog list . --backlog {dir} --json`), which returns a `BacklogItem[]`
each carrying `status`, `needsHuman`, `blockedReason`, `humanAnswer`, `dependsOn`. The
aggregate `backlogSummary` from `rauf status . --json` is **NEVER** the test (REQ-UNB-02):
a count can be unchanged while items swap states, and can move for unrelated reasons.

### 6.2 The per-item test

```python
# Reference algorithm — the per-item proof (executed by the recovery procedure).
# `affected_ids`: the items this session applied for (§5.4 step 1, in-flight set).
# `items`: the BacklogItem[] from the post-apply listCommand re-read (§6.1).

def prove_unblocked(affected_ids: list[str], items: list[dict]) -> dict:
    """Return movers and non-movers from a per-item identity test.

    An item is proven unblocked iff its post-apply status != "blocked". Because
    rauf derives the needs-human count as (status=="blocked" && needsHuman==true),
    leaving `blocked` also removes the item from needsHuman — the single test
    covers both flags (00 §5.2). An affected item MISSING from the re-read (e.g.
    deleted) counts as a non-mover: it was not proven to leave `blocked`.
    """
    by_id = {i["id"]: i for i in items}
    movers, non_movers = [], []
    for item_id in affected_ids:
        item = by_id.get(item_id)
        if item is not None and item.get("status") != "blocked":
            movers.append(item_id)
        else:
            non_movers.append(item_id)
    return {"movers": movers, "non_movers": non_movers,
            "all_moved": len(non_movers) == 0}
```

`status != "blocked"` is the whole test: leaving `blocked` also removes the item from the
needs-human count (defined as `status=="blocked" && needsHuman==true`, `00 §5.2`), so one
test governs both flags.

### 6.3 Partial is failed (REQ-UNB-03)

Recovery **succeeds only when `all_moved` is true** — every affected item left `blocked`.
Any non-mover — **including a partial move where some items moved and others did not** — is
a **failed recovery**, not a distinct state. The failed-recovery report names both sets
from item `status` fields (never aggregate counts, per the `00 §9` citation-basis table):

- **Moved:** the ids in `movers`, with their new `status`.
- **Not moved:** the ids in `non_movers`, each with its current `status`/`blockedReason`
  (or "missing from re-read").

On any non-mover, the procedure does **not** select `resolved`; the ladder falls through to
`needs-human`/`blocked` as today (`05`, `00 §5.2`).

### 6.4 Feeding the `resolved` gate

The `all_moved` result is precondition (c) of the `resolved` gate (`00 §5.2`, REQ-OUT-03).
The gate additionally requires (a) `decision-list --unapplied` empty for the affected items
and (b) `git status --porcelain` clean — both owned by `05`. This document supplies only (c).

---

## 7. Error model (REQ-REL-02)

Mirrors the `state-*` exit-2 protocol (`00 §7`). The apply side has two failure classes and
they are reported differently — this distinction is a first-class requirement (REQ-REL-02:
"a failed unblock is thereby distinguishable from REQ-UNB-03's ran-but-nothing-moved
failure").

| Failure | When it occurs | Reaches the §6 per-item test? | Report |
|---|---|---|---|
| **Failed apply** | `rauf backlog answer` / `rauf backlog unblock` exits non-zero (corrupt backlog, I/O error, not-blocked/not-found refusal); or the post-apply re-read is unparseable | **No** — stops *before* the test | Verbatim runner error (or the parse error) + which item; **failed recovery**; procedure stops; never claimed succeeded |
| **Ran-but-nothing-moved** | Every apply exited 0, but the §6 per-item test finds a non-mover | **Yes** — *is* the test failing | Movers/non-movers named from `status` fields (§6.3); **failed recovery** |
| **Version-probe miss** | `versionCommand` missing/unparseable, or version `< RECOVERY_MIN_RUNNER_VERSION` | N/A — selects the degraded path (§5.2) | Degraded path proceeds; not-threaded caveat + `installHint`; **not** a failed recovery |

Rules:

1. **Never report recorded/succeeded past a failed step.** A non-zero runner exit or an
   unparseable read-back is surfaced **verbatim**, the procedure **stops**, and recovery is
   reported **failed**.
2. **A failed apply stops before the per-item test.** So a runner that errored is never
   conflated with a runner that ran cleanly but moved nothing — the former is attributed to
   the failed runner invocation; the latter to the specific non-mover items.
3. **`decision-apply` is not called for a failed item** (§5.4 step 4) — the record stays
   unapplied and re-surfaces next launch (REQ-DEC-06).
4. **A version-probe miss is reported, not fatal** — it degrades and attaches the upgrade
   hint; recovery still runs across the `≥ 0.6.0` floor.
5. **`rauf backlog answer` on a missing / not-blocked item** exits non-zero (§4.3) → treated
   as a **failed apply for that item** (row 1), never silently skipped.

---

## Decision Table (consolidated) — (runner version, item kind) → mechanism → report

| Runner version | Item kind | Mechanism | Report line | Failed-recovery? |
|---|---|---|---|---|
| `≥ 0.14.0` | needs-human | `rauf backlog answer` | Answer applied + threaded into next prompt | Only if runner errors or item doesn't move |
| `≥ 0.14.0` | plain blocked | `rauf backlog unblock` | Item unblocked | Only if runner errors or item doesn't move |
| `< 0.14.0` / probe miss | needs-human | `rauf backlog unblock` (degraded) | Unblocked; **answer NOT threaded** (durable in record); `{installHint}` | Only if runner errors or item doesn't move |
| any / probe miss | plain blocked | `rauf backlog unblock` | Item unblocked | Only if runner errors or item doesn't move |
| — | any (runner exits non-zero) | (stops) | Verbatim error; **failed recovery** | Yes (failed apply) |
| — | any (ran, item still `blocked`) | (proven) | Movers/non-movers named; **failed recovery** | Yes (ran-but-nothing-moved) |

(`0.14.0` = `RECOVERY_MIN_RUNNER_VERSION`, pinned at impl per OTQ-2.)

---

## Dependencies

Must be implemented / available first:

- `00-core-definitions.md` — `RECOVERY_MIN_RUNNER_VERSION` (§6.2), the error model (§7),
  the `loopRunner` config surface (§10). **Root dependency.**
- `02-decision-record.md` — `decision-apply` (the applied stamp, §5.4 step 3) and
  `decision-list --unapplied` (the read-back this document applies for, §5.4 step 1).
  DEC is the keystone and lands first (`01 §4`).
- **rauf `backlog answer`** (rauf repo, §4) — for the `≥ 0.14.0` path. The forge side
  builds and passes **with or without** it present: below the threshold it degrades to
  `unblock` (§5.2). The rauf PR lands in parallel with DEC/TREE (`01 §3`, tech-spec §9).

Consumed by:

- `05-recovery-procedure.md` — invokes this document's apply (step 5) and prove (step 6)
  steps in sequence; supplies gate preconditions (a) and (b) that this document's prove
  result (c) completes.
- `03` — the `resolved` outcome selection, gated on this document's per-item proof.
- `07-testing-strategy.md` — the rauf `backlog answer` unit tests (happy path, not-blocked
  refusal, JSON shape) and the stubbed-CLI forge-side tests exercising both the `answer`
  and degraded `unblock` dispatch and the per-item proof.

---

## Verification

An implementation matches this document when:

- [ ] `rauf backlog answer <path> <id> "<text>"` writes `humanAnswer`, sets `status:
      "pending"`, clears `needsHuman`/`blockedReason`, and **does not relaunch**; its JSON
      output is exactly `{ "answered": "<id>", "status": "pending" }`.
- [ ] `rauf backlog answer` on a **not-blocked** item exits non-zero with
      `Item <id> is not blocked (status: <status>)`; on a **missing** item exits non-zero
      with a not-found message. Both are treated by the procedure as a failed apply.
- [ ] The forge side selects `answer` at `≥ RECOVERY_MIN_RUNNER_VERSION` and **degrades to
      `unblock`** below it (and on a probe miss) **without hard-failing recovery** — a
      stubbed old-runner CLI still completes recovery, reporting the answer was not
      threaded and attaching `installHint`.
- [ ] The **degraded path works at `0.6.0`**: a stubbed `rauf version --json` reporting
      `0.6.0` drives needs-human items through `unblock`, the items leave `blocked`, and
      the report states the answer was not injected into the next prompt.
- [ ] Plain blocked items use `unblock` at **every** version (no version-dependent behavior
      on the non-needs-human path).
- [ ] The unblock proof re-reads via `listCommand` and tests **each** affected item's
      `status != "blocked"` — never the aggregate `backlogSummary`. A test that passes on
      an unchanged count while an item stayed `blocked` is a defect.
- [ ] **Partial moves are caught:** a fixture where item A moved and item B stayed `blocked`
      produces a **failed recovery** naming A as moved and B as not moved; `resolved` is
      **not** selected.
- [ ] **Failed apply vs ran-but-nothing-moved are distinguished:** a stubbed runner that
      exits non-zero stops **before** the per-item test and reports the verbatim error; a
      stubbed runner that exits 0 but leaves an item `blocked` reaches the per-item test and
      reports movers/non-movers. Neither is ever reported as succeeded.
- [ ] `decision-apply` is invoked for an item **only after** its runner apply exited 0; a
      failed apply leaves the record unapplied (re-surfaces via `decision-list --unapplied`).
- [ ] `bash scripts/validate.sh` is green; the rauf repo's `backlog answer` unit tests and
      the subcommand-registration assertion pass.
