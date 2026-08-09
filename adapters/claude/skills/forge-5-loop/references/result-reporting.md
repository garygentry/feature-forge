# forge-5-loop — Result Reports and Loop-Outcome Selection

This file carries two things for `forge-5-loop/SKILL.md`:

1. the verbatim **result-report templates** for **Step 4b** — factual counts only; and
2. the deterministic **`LoopOutcome` ladder** for **Step 7**, which picks the single
   value the scripted stage exit is invoked with.

The reports describe what the run did. They never carry a next command, a retry
command, or a "continue to docs" suggestion: routing is the scripted stage exit's
job, and a loop run emits exactly **one** `stage-exit` invocation and **one**
terminal block.

## Result reports (Step 4b)

Pick **every** branch that applies — a run can be both blocked and needs-human — and
render its report. These are descriptive; none of them ends the turn.

**All items done.**
```
Loop completed for {feature}. All {N} items implemented successfully.
```

**Runner review pass.** A review flag (e.g. rauf's `--review`) makes the runner run
a post-loop review that **auto-creates and implements fix items** rather than handing
findings to the user — distinct from `forge-verify impl` (a clean-context audit that
writes a findings doc). When Step 4a captured a `review_completed` event, add a line
below the counts so the pass's effect is visible and not mistaken for "nothing
happened":
```
Runner review pass: {itemsCreated} fix item(s) created and implemented.
  {summary}
```
Omit this line when no `review_completed` event was emitted (no review flag passed).
The created items are already counted in the totals above.

**Some items need a human:**
```
Loop completed for {feature}.
  Completed:   {done}/{total}
  Needs human: {needsHuman} items (set aside during the run)

These items asked a question the loop couldn't answer:
  - {id}: {title} — {reason}
```

**Some items blocked:**
```
Loop completed for {feature}.
  Completed: {done}/{total}
  Blocked:   {blocked} items

Blocked items:
  - {id}: {title}
  - {id}: {title}

Inspect one with: {bin} backlog show . {id} --backlog {backlogDir}
```

**Some items deferred (runner gave up after retries — "false blocks"):**
```
Loop completed for {feature}.
  Completed: {done}/{total}
  Deferred:  {deferred} items (no signal after retries — likely just need another pass)
```

**Some items still pending** — the parenthetical cause is chosen, never hardcoded:
```
Loop completed for {feature}.
  Completed: {done}/{total}
  Pending:   {pending} items ({cause})
  Blocked:   {blocked} items
```
Render `{cause}` as "iteration limit reached" **only** when `iteration == maxIterations`
AND `selectable > 0` — cite the `iteration`/`maxIterations` counters from
`{loopRunner.stateDir}/state.json` and `selectable` from `backlog-topology --items-stdin
--json` run over the same authoritative item JSON as the counts above. Otherwise —
`selectable == 0` with items still pending while `iteration < maxIterations` — the
iteration limit was NOT the constraint: drop the parenthetical and render this
dependency-starvation report instead, naming each blocking root and its gated-subtree
size from `backlog-topology`'s `starvation.blockingRoots[].{id, gatedCount}` and
`itemCount`, then close the stage with `--cause dependency-starvation` in Step 7:
```
Loop stopped for {feature} with {pending} item(s) still pending, but the iteration
limit was NOT the constraint ({iteration}/{maxIterations} iterations used).
No pending item was selectable — every one is gated behind unblocked roots:
  - {rootId}: {rootTitle} — gates {gatedCount}/{itemCount} items
Unblock these roots (their subtrees free up on the next run), then run the loop again.
```
Both branches cite their authoritative source: the iteration-limit branch the
`state.json` iteration counters, the starvation branch the backlog summary counts plus
the `backlog-topology` output (`selectable`, `blockingRoots`, `gatedCount`,
`itemCount`). A cause any of those counters contradicts — e.g. "iteration limit
reached" while `iteration < maxIterations` — is a reportable defect.

## Selecting the one `LoopOutcome` (Step 7)

After Step 5's `state-complete`, select exactly **one** `LoopOutcome` from Step 4a's
authoritative final counts. Walk this ladder in order and stop at the first match:

1. **`resolved`** — the Post-Run Recovery Procedure
   (`references/recovery-procedure.md`) ran this session with a **non-empty**
   affected-item set and its gate passed: every affected needs-human item has an
   applied decision record, the working tree is clean, and each affected item left
   `blocked`/`needsHuman` per the per-item re-read. This outranks `needs-human` so a
   stop the recovery just cleared is not re-reported as still needing a human. (Step
   4c runs the procedure on every close, so an empty affected set is the common case —
   it never selects `resolved`; fall through.)
2. **`needs-human`** — otherwise, `needsHuman > 0`. This wins even when blocked
   items also exist: a decision only a human can make outranks work that merely
   could not proceed.
3. **`blocked`** — otherwise, genuine `blocked > 0`.
4. **`deferred`** — otherwise, runner-deferred items exist (the "false blocks" the
   runner gave up on after retries).
5. **`partial`** — otherwise, `pending`/`in_progress` items remain because the
   iteration limit was reached.
6. **`complete`** — otherwise, and **only** when every item is `done`.

This is a priority order, not a set. A run reporting both a needs-human and a blocked
count renders both reports above and still exits `needs-human`.

**The runner's process exit code is not the outcome.** A loop runner that exits 0 has
reported only that its process finished; the final backlog state decides. A clean
exit 0 that still leaves pending items is `partial`, never `complete` — and
`complete` is legitimate only when the counts show every item `done`.

**Retrying the non-complete outcomes.** `partial`, `deferred`, and `resolved` fence
the loop resume; `blocked` and `needs-human` fence the navigator. Whichever you land on, the
runner's own retry flags still apply to the next run — e.g. rauf's `--retry-blocked`
picks the set-aside blocked and deferred items back up at Step 2d. Mention that as
plain prose in the report if it helps; never as a second command block.

## Operational failure before the counts are known

If the run cannot produce authoritative counts at all — the status/list command fails,
its output does not parse, the state directory is gone, or the process died in a way
that leaves the backlog unreadable — **do not pick an outcome and do not close the
stage.** There is nothing to select from, and guessing one would record a pipeline
position that never happened.

Instead: say plainly what failed, show the command's own output, and name the
recovery (re-run the status command, or re-run the loop once the runner is healthy).
Emit no `stage-exit` invocation and no terminal block. The stage stays `in-progress`
on disk, which is exactly the state the navigator can resume from.

## Closing the stage

Pass the selected value to the single scripted stage exit in **Step 7** of
`forge-5-loop/SKILL.md` as `--outcome {LoopOutcome}`, and print its NEXT-STEPS block
verbatim as the absolute last output. Append nothing after it — no summary, no retry
line, no docs suggestion. For a completed epic member, the exit consumes the epic's
live status itself, so announce the rollup **before** invoking it and add no
hand-authored handoff of your own afterwards.
