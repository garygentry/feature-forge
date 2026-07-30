# Behavior-preservation run — BATCH (R1, R3, R5), backlog item 017

**Scope.** The **batch** run `06-testing-strategy.md §9` requires "once for the batch
before release", and the SC-3 evidence for the three units §9 permits to ride it: **R1**
(verification-checklist mode split), **R3** (navigator `process-overview.md` gate) and
**R5** (`effective-config` producer + consumer swap). R4 and R6 carry their own mandatory
per-unit records — `BEHAVIOR-PRESERVATION-R4-item-011/012/013-2026-07-29.md` and
`BEHAVIOR-PRESERVATION-R6-item-015-2026-07-29.md` — and are **re-confirmed** here at the
combined end state rather than re-argued.

**Date.** 2026-07-29 · **Branch.** `forge/context-efficiency`

**Baseline.** `9a29e846ed510c3b245876a9bf4cc73b8cb60951` — *"forge(context-efficiency):
author backlog v1 (17 items, R1/R3/R4/R5/R6)"*, the **pre-feature** commit recorded in
`specs/context-efficiency/.pipeline-state.json` under `stages['forge-4-backlog'].commitHash`.
This is the last tree in which none of R1/R3/R4/R5/R6 had landed, so it is the correct
basis for a *batch* claim (the per-unit records each used their own immediate predecessor).

**Worktree under test.** `b5529ae` (`[rauf] 015: …`) plus item 017's test-only edits —
i.e. every shipped unit landed. `bash scripts/validate.sh` is green on it.

---

## Comparison basis

The `consumption-data-refresh` dogfood corpus — the same evidence source used for `§7.4`
and re-measured in `.reference/REMEASURE-0.13.0.md` (**188** sessions, at
`~/.claude/projects/-home-gary-workspace-consumption-data-refresh/`). Same corpus as the
item-011, item-012, item-013 and item-015 records, so all five runs are directly
comparable.

Transcripts naming each of the seven `§9` surfaces, carried forward from those records and
re-used here unchanged (the batch adds no surface they did not already cover):

| §9 surface | Transcript(s) |
|---|---|
| 1. `AskUserQuestion` option sets / order / `(recommended)` labelling | `11fe7945-9c68-49f9-97ef-f38da9a76d5a`, `19e50909-c587-46d0-b765-11d20871b3bb`, `257af5ca-d171-43c8-9a11-0f14adfbebf7` |
| 2. Decision Support wording | `11fe7945…`, `726ef9e2-196e-4a74-ad6b-f346a194b822` |
| 3. Branch Setup / Branch Reconciliation prompts | `a8c7a107-ff7e-4574-a27a-be2f578a8de0`, `11fe7945…` |
| 4. Stage-Entry Guard + Stage-Completion Re-check classification | `a8c7a107…`, `257af5ca…` |
| 5. Two-commit Git Commit Protocol (incl. the L245/L248 failure branches) | `726ef9e2…`, `a8c7a107…` |
| 6. Verify-gate routing + stage-exit directive handling | `257af5ca…`, `726ef9e2…` |
| 7. NEXT-STEPS block + its sentinel (`─ forge: end of stage ─`) | `257af5ca…`, `726ef9e2…`, `a8c7a107…` |

**Honest scope note.** As in the four per-unit records, what is executed below is
mechanical: byte-level section diffs against the baseline tree, citation-reachability
traces using the adapter fan-out regex, and real subprocess runs of the scripts a stage
invokes. A live end-to-end `forge-1-prd → forge-6-docs` drive would additionally need a
human at ~12 `AskUserQuestion` prompts and a populated backlog. The part the surfaces
actually turn on — *what text is rendered, and which file each path opens* — is determined
here exhaustively rather than sampled, which for an "identical / not identical" claim is
stronger evidence than one sampled run.

---

## Part 1 — the seven surfaces, batch-wide

Method: split every canon file changed since the baseline on `## ` headings, at both
revisions, and compare byte-for-byte. Then read **every** removed line.

```
$ python3 /tmp/secdiff.py     # reproduced in Appendix A
=== TOTAL: 108/139 baseline sections byte-identical ===
```

Per file:

| File | byte-identical | changed sections |
|---|---|---|
| `references/shared-conventions.md` | 10/15 | Pipeline State Protocol; Branch Setup; Branch Reconciliation; Git Commit Protocol; Stage-Entry Guard |
| `references/stage-exit-protocol.md` | 5/6 | Directive contract |
| `agents/forge-verifier.md` | 11/12 | How You Work |
| `skills/forge/SKILL.md` | 2/3 | Behavior |
| `skills/forge-1-prd/SKILL.md` | 7/9 | Step 3 (Interview); Step 6 |
| `skills/forge-2-tech/SKILL.md` | 18/20 | Step 3 (Interview); Step 7 |
| `skills/forge-3-specs/SKILL.md` | 8/10 | Step 3 (Plan); Step 7 |
| `skills/forge-4-backlog/SKILL.md` | 8/10 | Prerequisites; Step 7 |
| `skills/forge-5-loop/SKILL.md` | 6/10 | Resolve the loop runner; Step 2; Step 3; Step 5 |
| `skills/forge-6-docs/SKILL.md` | 12/13 | Step 5 |
| `skills/forge-verify/SKILL.md` | 7/11 | Subagent Delegation; Step 3; Step 4; Step 6 |
| `skills/forge-0-epic/SKILL.md` | 6/7 | Creation Branch |
| `skills/forge-5-loop/references/runner-contract.md` | 5/9 | preamble; Inform-user template (+2 sections relocated to `agent-selection.md`) |

`## User Input Protocol` — the home of surfaces **1** and **2** at the shared level — is
**byte-identical**, as are `## Standard block` and `## Warm-acceptable variant` in
`stage-exit-protocol.md` (the rendered gate text).

### Surface 1 + 2 — `AskUserQuestion` option sets, order, `(recommended)`

Every line in `skills/` and `references/` containing `AskUserQuestion` **or**
`(recommended)`, at both revisions, whitespace-normalized and sorted:

```
$ diff /tmp/auq.base /tmp/auq.head
lines: base=106  head=106
```

**106 lines at both revisions; 103 byte-identical; 3 differ.** Every one of the three
differs *only* outside the prompt text:

1. `forge-1-prd` epic-backflow line — the `epicChangeRequests[]` **JSON-authoring clause**
   became a `state-ecr` invocation (R4/item 012). The prompt sentence inside the same
   line — *"When the change touches a contract/dep edge and the classification is genuinely
   ambiguous, confirm `blocksCurrent` with a single `AskUserQuestion`, defaulting to `true`
   (a false negative silently diverges two members' contracts)."* — and the quoted
   acknowledgement string are **byte-identical**.
2. `forge-2-tech` epic-backflow line — same substitution, same `AskUserQuestion` sentence
   preserved byte-for-byte.
3. `forge-5-loop` `(d-model)` Claude-only model-alias guard — the **only** change is the
   trailing citation, `references/runner-contract.md` → `references/agent-selection.md`
   (R6/item 015). The option set — *"**(1) Strip `model` for this run (recommended)**"* /
   *"**(2) Proceed as-is**"* — its order, and its `(recommended)` label are byte-identical.

Per-file `AskUserQuestion` counts match at every path, with the two split relocations
accounting for themselves exactly:

```
verification-checklists.md  1  →  findings-template.md  1        (R1)
runner-contract.md          4  →  runner-contract.md 3 + agent-selection.md 1   (R6)
```

**Verdict: identical.** No option added, dropped, reordered or relabelled.

### Surface 3 — Branch Setup / Branch Reconciliation prompts

Both sections changed. All removed lines (full set):

```
-**Record the branch.** After this block resolves, write the resulting branch name to the
 feature's `.pipeline-state.json` top-level `branch` field (create/update it when the state
 file is first written for this stage). …
-- **`adopt-current`** — … Write `newBranch` into the state `branch` field with a
 **visible one-line note** ("recorded branch was `{stateBranch}`; work is on
 `{currentBranch}` — updating to match") …
```

Both are **write mechanics**. The `adopt-current` visible one-line note is re-emitted
verbatim in the replacement text, and the timing qualifier (*"create/update it when the
state file is first written for this stage"*) survives — item 011's record verified it is
load-bearing, because Branch Setup runs before the feature directory may exist.

**Verdict: identical prompts.**

### Surface 4 — Stage-Entry Guard + Stage-Completion Re-check classification

`## Stage-Completion Re-check` is **byte-identical**. Within `## Stage-Entry Guard`, the
classification-label line set (`Fresh` / `Resume` / `Interrupted` / `Re-authoring`) differs
in exactly **one** line out of the set:

```
-…update the `stages.{stage}.artifacts` array in `.pipeline-state.json` after writing each file…
+…run `state-artifact --feature {feature} --stage {stage} --path <file>` after writing each file…
```

That is the incremental-artifact-tracking **mechanic**; the sentence's second half
(*"This is what makes the Interrupted inventory above precise…"*) is unchanged, and no
classification rule moved. The Entry Stamp's three removed bullets
(`status` / `startedAt` / `currentStage`) are likewise pure mechanics, now `state-enter`.

**Verdict: identical classification.**

### Surface 5 — the two-commit Git Commit Protocol, incl. L245 / L248

Removed lines are the four numbered protocol steps' **JSON-authoring halves** only. Present
and unchanged in the worktree: the two-commit sequence, the *never `--amend`* rule, the
"hash points at Commit 1, never Commit 2, never an orphaned amend" invariant, and both
failure branches — L245 (*"do NOT update pipeline state to complete … leave state as
`in-progress` so the stage can be resumed"*, now routed through `state-complete …
--resumable`) and L248 (*"leave `commitHash` at its existing value"*, now
`--preserve-commit-hash`).

Item 012's record proved the `--resumable` branch discriminates correctly against a bare
`--status in-progress` on the entered-but-not-completed fixture (A keeps
`{status, startedAt}` only; B gains `completedAt` **and** `version`). Re-confirmed at the
combined end state by `tests/test_state_verbs.py::test_resumable_records_only_the_status`
and the item-014 conformance guard, both green in the batch run below.

**Verdict: identical protocol.**

### Surface 6 — verify-gate routing + stage-exit directive handling

```
$ git show BASE:references/stage-exit-protocol.md | grep '^### ' | md5sum
32420431b18684ad01f5e082bd55fe7d
$ git show HEAD:references/stage-exit-protocol.md | grep '^### ' | md5sum
32420431b18684ad01f5e082bd55fe7d          ← directive heading set: IDENTICAL

$ … | grep 'verifyGate\|runInStageVerify\|autoFixEligible' | md5sum
ed58a21e5d4eb36f536bfa63d64a9606   (both revisions)   ← routing lines: IDENTICAL
```

The only removed lines in the whole file are the four that spelled out the
`deferredDecisions[]` JSON shape (now `state-decision`, R4/item 011). `## Standard block`
and `## Warm-acceptable variant` are byte-identical, and
`tests/test_stage_exit_protocol.py` passes **unchanged**.

**Verdict: identical routing.**

### Surface 7 — the NEXT-STEPS block and its sentinel

```
$ git grep -h "forge: end of stage\|NEXT-STEPS\|NEXT_STEPS" BASE -- skills/ references/ scripts/ | sort | md5sum
11bdcaacb9c073a75de7888c9d772275
$ …same for HEAD…
11bdcaacb9c073a75de7888c9d772275          ← IDENTICAL
```

**Verdict: identical.** Byte-for-byte across canon and `scripts/`.

---

## Part 2 — R1 (verification-checklist mode split)

### The named `§9` reduced substitute

`§9`'s R1 substitute is used and is **named explicitly**: *one real verify fan-out on a
large mode, diffing the findings-document shape*. Executed as a **backlog-mode** pass
(27 checks — one of the three "large" modes) over `specs/context-efficiency/backlog.json`.

**Deviation, stated plainly:** it was run as a **single inline verifier**, not as the
four-way dispatched `forge-verifier` fan-out the skill's Subagent Delegation section
prescribes for large modes. Subagent dispatch is not available to a rauf loop iteration
for this item (item 017 declares no `agentDelegation`). The substitute's object — *does a
leaf that loads only `verification-checklists/backlog.md` still execute the same 27 checks
and produce the same findings-document shape* — is unaffected by verifier count.

### Structural equivalence (exhaustive, not sampled)

```
$ git show BASE:…/verification-checklists.md | sed -n '325,477p' > /tmp/mono.tail
$ tail -n +5 skills/forge-verify/references/findings-template.md > /tmp/ft.body
$ diff /tmp/mono.tail /tmp/ft.body
IDENTICAL (153 lines)
```

The findings-document template — Summary, Findings, Fix Execution Plan, Example Findings,
Epic Mode State Write Detail — is a **byte-for-byte** relocation. The shape *cannot*
differ.

```
$ diff <(monolith @BASE | grep -oE 'CHECK-[A-Z][0-9]+' | sort -u) \
       <(cat verification-checklists/*.md | grep -oE 'CHECK-[A-Z][0-9]+' | sort -u)
IDENTICAL: 130 unique CHECK-IDs, none added / dropped / renumbered
```

### The run

Leaf read-set: `skills/forge-verify/references/verification-checklists/backlog.md` **only**
(97 lines / 1,112 words, vs the 477-line monolith the pre-split leaf loaded).

Deterministic pre-check, exactly as the pre-split report ran it:

```
$ rauf-stable backlog validate . --backlog specs/context-efficiency --specs-dir ./specs --json
{ "valid": true, "findings": [] }
```

**Checks Executed: 27 of 27. Results: 21 pass, 0 fail, 6 not-applicable.**

| Check | Result | Evidence |
|---|---|---|
| B01 valid JSON | pass | `json.loads` clean |
| B02 required fields | pass | 0 items missing any of the 9 required fields |
| B03 unique ids | pass | 17 ids, 17 unique |
| B04 valid types | pass | `chore`, `feature`, `refactor`, `test` |
| B05 valid priorities | pass | `{1, 2}` |
| B06 valid statuses | pass | `{done, in_progress, pending}` |
| B07 every spec doc referenced | pass | all 7 of `00`–`06` cited |
| B08 P0 coverage | pass | 23 P0 reqs; each covered by ≥1 item's ACs (13 are covered behaviorally rather than by ID string — e.g. REQ-R1-05 by item 001's CHECK-ID-count AC, REQ-R1-03 by item 002's dual-role-guard AC; REQ-R2-02 is scoped out per PRD §3.2) |
| B09 no missing spec file | pass | 0 dangling `specReferences` |
| B10 valid relative paths | pass | all resolve from repo root |
| B11 single-iteration scoping | pass | `estimatedIterations` 1–3, all with per-step decomposition |
| B12 fresh-agent detail | pass | every item names files, line ranges and gotchas |
| B13 objectively verifiable ACs | pass | every AC names a command, a file or a count |
| B14 names files to modify | pass | all 17 |
| B15 valid `dependsOn` ids | pass | 0 dangling |
| B16 no cycles | pass | DFS: none |
| B17 foundation items depend-free | pass | item 001 has `dependsOn: []` |
| B18 depend on the creating item | pass | e.g. 008/009/010 → 007; 003 → 002 |
| B19 priority/dependency consistency | pass | 0 inversions |
| B20 package scaffold item | **n/a** | refactor of an existing repo; no new package |
| B21 shared types / error hierarchy | **n/a** | same reason |
| B22 items per subsystem | pass | one contiguous item run per unit R1/R3/R4/R5/R6 |
| B23 integration wiring | pass | items 002/006/011/012/013 are the wiring |
| B24 test items | pass | 003, 014, 016 plus per-item pytest ACs |
| B25 no oversized items | pass | largest is 011 at 3 iterations, 6 enumerated touch points |
| B26 generated-artifact freshness | pass | `testCommand` = `bash scripts/validate.sh`, which gates on `build-adapters.py --check`; **every** canon-mutating item (001/002/004/005/006/007/008/009/010/011/012/013/015/017) carries the regenerate-and-commit AC. This was finding V-001 in the pre-split report and is now closed |
| B27 lifecycle contradiction | **n/a** | no lifecycle vocabulary (`draft`/`published`/`approved`) in any item |

Three further checks report **n/a** by the checklist's own advisory clauses rather than by
judgment (B20, B21, B27 above); B26's heuristic fired and passed.

### Findings-document shape diff

Rendered against `findings-template.md` and compared to the **pre-split**
`.verification/VERIFY-backlog-2026-07-29.md` (added at `ed3ab41`, before item 001's
`ca3da53` — so it is a genuine pre-change artifact produced by the monolith):

| Section | pre-split report | this run |
|---|---|---|
| `# Verification Report: {feature} ({mode})` | ✅ | ✅ |
| Date / Pipeline Stage / Mode / Artifacts Reviewed / Method | ✅ | ✅ |
| `Checks Executed: N of M. Results: X pass, Y fail, Z not-applicable.` | ✅ 27 of 27 | ✅ 27 of 27 |
| `## Summary` (totals, errors, gaps, inconsistencies) | ✅ | ✅ |
| `### Per-check roll-call` | ✅ | ✅ (the table above) |
| `## Findings` / `### V-00N: {title}` | ✅ 27 findings | ✅ 0 findings — nothing to render |
| `## Fix Execution Plan` → `### User Decisions Required`, `### Execution Steps` | ✅ | n/a — no findings |

**Verdict: identical shape.** The only differences are content (0 findings now vs 27 then,
because those 27 were fixed at `ed3ab41` — which is the point of the earlier pass), and the
consequent absence of the Fix Execution Plan, which the template itself makes conditional
on there being findings.

**Note on a known, already-reviewed wording change.** `REQ-BEHAV-02` flagged two R1
adaptations for explicit review rather than silent adoption; both are visible in the
removed-line set for `skills/forge-verify/SKILL.md` and `agents/forge-verifier.md`:

- the verifier's *"How You Work"* file-load line, re-pointed from the monolith to
  `references/verification-checklists/{mode}.md`;
- the expected-count table's `~` hedges dropped and **`tech ~15 → 17`** corrected — the
  file always held 17 checks; the old table was wrong. This *changes what the leaf's
  self-check compares against*, and does so in the direction of correctness (REQ-R1-04).

Both were reviewed and accepted at item 002 and are re-surfaced here so the batch record is
self-contained.

---

## Part 3 — R3 (navigator `process-overview.md` gate)

The line, before and after:

```
BASE  L18: For pipeline architecture details, read `references/process-overview.md`.
HEAD  L20: **Only if the user is asking how the pipeline works** — architecture, stage
           ordering, what a stage does, or "explain forge" — read
           `references/process-overview.md` for the details before answering. For routine
           status/dashboard rendering, do **not** read it.
```

Read-set trace over the frontmatter-stripped navigator body, using the adapter fan-out
regex `(?<![./\w-])references/([A-Za-z0-9_][A-Za-z0-9_./{}*-]*?\.md)\b`:

```
  L 11 references/shared-conventions.md      unconditional
  L 15 references/process-overview.md        GATED (architecture questions only)
  L 19 references/shared-conventions.md      unconditional
  L108 references/stage-exit-protocol.md     unconditional
  L118 references/shared-conventions.md      unconditional
  L118 references/stage-exit-protocol.md     unconditional
  L176 references/shared-conventions.md      unconditional
  L205 references/shared-conventions.md      unconditional
```

Exactly one citation is gated, and it is the R3 target. `references/process-overview.md`
is **byte-identical to baseline** (`git diff` empty), so the architecture-question path
renders the same answer from the same text — R3 changes *when* it is opened, never *what*
it says.

The routine dashboard path was **executed**, not merely traced:

```
$ python3 scripts/forge-session.py rank-features --specs-dir ./specs --json
{ "active": [ { "name": "context-efficiency", "currentStage": "forge-5-loop",
                "branch": "forge/context-efficiency", "nextStage": "forge-5-loop",
                "nextCommand": "/feature-forge:forge-5-loop context-efficiency",
                "verifyPending": false, … } ] }
```

Every field the dashboard renders is produced by the script, not by the gated prose.
`skills/forge-guide/SKILL.md`'s three `process-overview.md` references are **unchanged**
(deliberately out of R3's scope — they were already conditional).

**Verdict: no user-visible surface changed.** On the common path the file is not opened; on
the architecture path it is, and its content is identical.

---

## Part 4 — R5 (`effective-config`)

The producer and both consumers were executed against real configs:

```
$ python3 scripts/forge-session.py effective-config --config ./forge.config.json --json
22 fields;  bin = "rauf-stable"   name = "rauf"        ← this repo's real override wins

$ python3 scripts/forge-session.py effective-config --config /nonexistent/… --json
22 fields;  bin = "rauf"                               ← pure schema defaults, exit 0
```

All 22 `loopRunner` fields resolve; the user override wins for the one field this repo
pins; a missing config degrades to pure defaults at **exit 0** (only an unreadable *schema*
is exit 2). This is the same 22-field block a model previously had to read out of
`references/forge-config-schema.json` and merge by hand — REQ-R5-02's point.

Frozen interactive text in the two consumers: `forge-4-backlog`'s `## Prerequisites` and
`forge-5-loop`'s `## Resolve the loop runner` are the only sections R5 touched, and the
frozen statement *"No loopRunner configured — defaulting to the rauf loop runner."* is
present byte-identical in the worktree (only its line-wrapping changed). `forge-4-backlog`'s
`AskUserQuestion` gates and `forge-5-loop`'s Run-mode surfaces appear in the 103 unchanged
lines of the Surface-1 comparison above.

**Verdict: no user-visible surface changed.** R5 replaces a read-and-merge step with a
deterministic subprocess producing the same values.

---

## Part 5 — R4 and R6 re-confirmed at the combined end state

Not re-argued (each has its own mandatory record), but re-run here so the batch claim holds
for the *combined* tree rather than for five separate intermediate trees:

- `references/pipeline-state-schema.json` is **byte-identical to baseline** — R4 changed no
  schema (`tests/test_state_schema_conformance.py`, sha256 `33a8337a…`).
- All seven `state-*` verbs, and the two realistic multi-verb sequences, produce state that
  validates with **zero findings** against that schema.
- The corrupt-state-file refusal holds: exit 2, file bytes unchanged.
- `agent-selection.md` is cited **only** from below `forge-5-loop`'s capability gate;
  `runner-contract.md`'s six always-loaded sections are intact and the nine-section union
  across the two files is unchanged.
- `skills/forge-5-loop/SKILL.md` body: **298 lines / 4,564 words** — inside Rule 4's
  300/5000 after R4 + R5 + R6 all landed.

### One user-visible display difference, flagged not buried

`state-complete` does not write `currentStage`, so the *"Set `currentStage` to <next
stage>"* bullet was dropped from every converted completion step (spec `03` §13.1's
after-block omits it; no verb can set the field to an arbitrary value). Consequence: a
**finished** pipeline's dashboard now shows `currentStage: forge-6-docs` rather than
`complete`. `next_stage()` derives "what runs next" from `stages[].status` and is
documented as *"intentionally distinct from the stored `currentStage` field"*, so routing is
unaffected; and the schema defines `currentStage` as *"where the pipeline IS: the most
recently started stage"*, which the old bullet already contradicted. It therefore reads as a
correction — but it **is** a display difference, it is not one of the seven `§9` surfaces,
and it is carried forward from the item-012 and item-013 records for owner review rather
than being treated as settled.

---

## Conclusion

Across the batch — R1, R3 and R5 directly, R4 and R6 re-confirmed — **all seven `§9`
surfaces are identical to the baseline**: 108/139 canon sections byte-identical, and every
one of the 31 changed sections differs only in state-write mechanics, citation targets, or
the two REQ-BEHAV-02 adaptations reviewed and accepted at item 002. Of the 106 lines
carrying `AskUserQuestion` or `(recommended)`, 103 are byte-identical and the 3 that differ
preserve their prompt text and option sets verbatim.

`06-testing-strategy.md §9`'s batch requirement is satisfied, and SC-3 is assigned for
every shipped unit:

| Unit | SC-3 record |
|---|---|
| R1 | **this document**, Part 2 (named `§9` reduced substitute: one verify pass on a large mode, findings-document shape diffed) |
| R3 | **this document**, Part 3 |
| R5 | **this document**, Part 4 |
| R4 | `BEHAVIOR-PRESERVATION-R4-item-011/012/013-2026-07-29.md`; re-confirmed Part 5 |
| R6 | `BEHAVIOR-PRESERVATION-R6-item-015-2026-07-29.md`; re-confirmed Part 5 |

---

## Appendix A — reproducing the section diff

```python
BASE = "9a29e846ed510c3b245876a9bf4cc73b8cb60951"
FILES = git diff --name-only $BASE -- skills/ references/ agents/
for f in FILES:
    a, b = git show $BASE:f, read(f)
    split both on lines starting "## "; compare each section byte-for-byte
```

Surface-specific one-liners used above (`zsh`; note `"${rev}:path"` — a bare `$rev:path`
is mangled by the `:r` history modifier):

```
git grep -h "AskUserQuestion\|(recommended)" $REV -- skills/ references/ | sed 's/^[[:space:]]*//' | sort
git show "${REV}:references/stage-exit-protocol.md" | grep '^### ' | md5sum
git grep -h "forge: end of stage\|NEXT-STEPS" $REV -- skills/ references/ scripts/ | sort | md5sum
```
