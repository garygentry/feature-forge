# Behavior-preservation run — R4, backlog item 011

**Scope.** `references/shared-conventions.md` (five state-write touch points + the
Pipeline State Protocol header) and `references/stage-exit-protocol.md` (the
deferred-decisions rule). Recorded per `06-testing-strategy.md §9`, which marks the run
**mandatory for R4**.

**Date.** 2026-07-29 · **Branch.** `forge/context-efficiency` · **Baseline.** `git HEAD`
at the time of the run = `8486088` (`[rauf] 014: Add the R4 schema-conformance drift
guard`), i.e. the tree with all seven `state-*` verbs shipped and no call site converted.

**Form.** `§9`'s **reduced substitute for R4**, named explicitly as `§9` requires: *one
authoring stage plus a deliberately failed Commit 1, confirming the `--resumable` revert
path*. It is combined with an exhaustive static surface diff of the two edited files,
because this item edits **only** shared protocol text — it converts no skill body — so a
full `forge-1-prd → forge-6-docs` drive would exercise the same seven surfaces this diff
covers byte-for-byte, at far higher cost.

---

## Comparison basis

The `consumption-data-refresh` dogfood corpus — the same evidence source used for `§7.4`
and re-measured in `.reference/REMEASURE-0.13.0.md` (188 sessions, at
`~/.claude/projects/-home-gary-workspace-consumption-data-refresh/`).

Transcripts naming each surface, confirmed present by grep:

| Surface rendered | Transcript(s) |
|---|---|
| Branch Setup prompt (`Strongly recommended: create …`) | `257af5ca-d171-43c8-9a11-0f14adfbebf7`, `9676ab38-889f-42d0-b131-63516e47a98e`, `b596fd8c-6b5c-4010-8c4b-c452e7af1ef6` |
| Branch Reconciliation adopt note (`recorded branch was …`) | `257af5ca…`, `9676ab38…`, `a8c7a107-ff7e-4574-a27a-be2f578a8de0` |
| Git Commit Protocol Commit 2 (`record stage commit hash`) | `257af5ca…`, `4e09602b-ecd2-4997-99fe-64aa590534c4`, `9676ab38…` |
| NEXT-STEPS sentinel (`─ forge: end of stage ─`) | `257af5ca…`, `726ef9e2-196e-4a74-ad6b-f346a194b822`, `9676ab38…` |
| Stage-Entry Guard *Interrupted* gate (`Resume the in-progress draft`) | `257af5ca…`, `a8c7a107…` |
| Stage-Entry Guard *Re-authoring* warning (`A completed … artifact already exists`) | `257af5ca…`, `a8c7a107…` |

`AskUserQuestion` option sets were extracted from `257af5ca…`, `9676ab38…` and
`a8c7a107…` (14 questions) and confirm the Decision Support convention the corpus ran
under: the recommended option **first**, labelled `(recommended)` — e.g.
`['Approve as-is (recommended)', 'Drop the 004 scaffolding item', …]`,
`['scripts/discover/ sibling + scripts/discover.ts (recommended)', …]`.

---

## The seven §9 surfaces

Method: split both files into `##` sections at the baseline and in the working tree, and
compare each byte-for-byte; then word-diff every changed section.

| # | §9 surface | Owning section | Result |
|---|---|---|---|
| 1 | `AskUserQuestion` option sets, order, `(recommended)` labelling | `User Input Protocol` (shared-conventions) + `Standard block` (stage-exit) | **byte-identical** |
| 2 | Decision Support wording | `User Input Protocol › Decision Support` | **byte-identical** |
| 3 | Branch Setup / Branch Reconciliation prompts | `Branch Setup`, `Branch Reconciliation` | section changed; **every prompt line byte-identical** (below) |
| 4 | Stage-Entry Guard + Stage-Completion Re-check classification | `Stage-Entry Guard`, `Stage-Completion Re-check` | `Stage-Completion Re-check` **byte-identical**; Stage-Entry Guard's classification 1/2/3 **byte-identical** (only the Entry Stamp mechanic changed) |
| 5 | Two-commit Git Commit Protocol incl. L245/L248 | `Git Commit Protocol` | section changed; **every protocol sentence byte-identical** (below) |
| 6 | Verify-gate routing + stage-exit directive handling | stage-exit `Directive contract`, `Standard block`, `Warm-acceptable variant` | `Standard block` + `Warm-acceptable variant` **byte-identical**; `Directive contract` changed **only** in the deferred-decisions sub-block |
| 7 | NEXT-STEPS block and its sentinel | stage-exit `Standard block` / `Warm-acceptable variant` | **byte-identical** |

### Section-level result

```
references/shared-conventions.md            references/stage-exit-protocol.md
  identical  (preamble)                       identical  (preamble)
  identical  Feature Name Requirement         identical  How this file is used
  identical  User Input Protocol              identical  Stamp sites
  identical  Configuration Reading            CHANGED    Directive contract
  identical  Feature Directory Resolution     identical  Standard block
  identical  Specs Directory Hygiene          identical  Warm-acceptable variant
  identical  Epic Context Injection
  identical  Epic-Member Base Guard
  CHANGED    Pipeline State Protocol
  CHANGED    Branch Setup
  CHANGED    Branch Reconciliation
  CHANGED    Git Commit Protocol
  CHANGED    Stage-Entry Guard
  identical  Stage-Completion Re-check
  identical  Force Mode
```

The section **set** is unchanged (no heading added, removed or renamed).

### Every removed line is a state-write mechanic

`git diff -U0` over both files removes exactly 16 lines. All 16 are JSON-authoring
mechanics; **no** prompt, gate, guard, classification or output line is among them:

1. `Write pipeline state conforming to …schema… Always update updatedAt…` (protocol header)
2. `**Record the branch.** … write the resulting branch name to … .pipeline-state.json …`
3. `- **adopt-current** — … Write newBranch into the state branch field …`
4. Git Commit Protocol steps 2, 3, 4 and the *Nothing to commit* bullet (all re-emitted, see below)
5. The Entry Stamp lead-in + its three field bullets
6. `**Incremental artifact tracking:** … update the stages.{stage}.artifacts array …`
7. The deferred-decisions mechanic clause + its four-line field-by-field JSON recipe

Surviving untouched in the changed sections: the Branch Setup `AskUserQuestion`
blockquote and its two options, the `warn-drift` and `none`/`not-resolved` bullets, the
adopt note's exact wording and its *never silently / never push the user back* rules, the
Stage-Entry Guard's Fresh/Interrupted/Re-authoring classification and both of its
`AskUserQuestion` prompts, Force Mode, and *"This write is **left uncommitted**: it is
staged and committed as part of this stage's existing exit commit"*.

### Surface 5 in detail — the frozen Git Commit Protocol

Word-diff of the four re-emitted lines. Only the bracketed mechanic swaps; every other
word is carried across:

- **Step 1** (`git add {specsDir}/{feature}/` — never `-A`/`.`) — untouched.
- **Step 2** — `In .pipeline-state.json, set` → `Run state-complete … (which sets`. The
  rest (`then git commit -m "{commitPrefix}({feature}): <action>"`, *"This is the stage's
  **artifact commit**; its hash is the provenance hash callers rely on"*) is identical.
- **Step 3** — `Write it into this stage's commitHash in .pipeline-state.json` → `by
  running state-complete … --commit-hash $(git rev-parse HEAD), which writes it into this
  stage's commitHash and touches nothing else`. The `git add … && git commit -m
  "{commitPrefix}({feature}): record stage commit hash"` line, the *never at Commit 2 /
  never at an orphaned amend* sentence and the clean-tree sentence are identical.
- **Step 4 (L245)** — the original sentences (*"do NOT update pipeline state to complete.
  Report the error to the user and leave state as `in-progress` so the stage can be
  resumed."* and *"Common failure causes:"*) survive **byte-identical**; the invocation
  is **added** after them, naming `state-complete --feature {feature} --stage {stage}
  --version N --resumable`, with the note that `--version` is required by argparse but is
  not written under `--resumable`. The *Pre-commit hook failure* and *Merge conflicts*
  sub-bullets are untouched.
- **L248 (*Nothing to commit*)** — original sentences survive byte-identical; one
  sentence added naming `--preserve-commit-hash`.
- **Step 5** (`**Never** use git add -A, --amend, --no-verify, or --force flags`) and the
  `**Why two commits.**` rationale paragraph (which carries the never-`--amend`
  reasoning) — untouched.

---

## Executable run — R4 reduced substitute

Every invocation now written into the two files was executed against a throwaway
`specs/` tree; all five verbs ran clean.

```
state-branch  (first write, before any other verb)  -> recorded branch for demo: forge/demo
state-enter   (Entry Stamp)                         -> entered forge-1-prd (in-progress) for demo
state-artifact(incremental)                         -> tracked forge-1-prd artifact(s): PRD.md (1 total)
state-decision(stage-exit deferred decisions)       -> deferred decision recorded (raisedBy forge-1-prd → forge-2-tech)
state-complete(Commit 1)                            -> completed forge-1-prd v1 (commitHash: null)
state-complete --commit-hash (Commit 2)             -> recorded forge-1-prd commitHash: …
state-complete --preserve-commit-hash (L248)        -> completed forge-1-prd v2 (commitHash: <preserved>)
```

### Deliberately failed Commit 1 → the L245 `--resumable` revert

A real git repo, a real `pre-commit` hook returning exit 1, a real rejected `git commit`:

```
Commit 1 FAILED as intended            (pre-commit: deliberately rejecting)
state-complete … --version 2 --resumable
  fields the call changed: ['status']
```

Isolated on a stage that had completed at v1 with a recorded `commitHash`, against the
control §9 names:

```
                 version   completedAt        commitHash
  pre               1      2026-…             'abc123'
  --resumable       1      unchanged          'abc123'      <- changed only: status
  bare --status     2      restamped          None          <- changed: version, completedAt, commitHash
```

**Confirms the frozen L245 contract:** `--resumable` records only `status`, leaving the
stage resumable — `completedAt` is not stamped, `version` does not move, `commitHash` is
not reset, and no staleness cascade fires. A bare `--status in-progress` (forge-5-loop's
*partial completion*, a different caller) writes all three, which is exactly why the two
must not be conflated.

---

## Verdict

**SC-3 satisfied for this item.** All seven `§9` surfaces are identical: four sections
carrying them are byte-identical, and in the five changed sections every removed line is
a JSON-authoring mechanic with no prompt, gate, guard, classification or output line
touched. The L245/L248 failure branches remain executable through `--resumable` and
`--preserve-commit-hash`, demonstrated end-to-end against a genuinely failed Commit 1.

Gates at time of writing: `python3 -m pytest tests` 638 passed / 2 skipped
(`tests/test_stage_exit_protocol.py` green **unchanged**), `python3
scripts/check-spec-purity.py` PASS (0 violations, incl. Rule 5 prelude byte-identity on
all five new fenced calls), `bash scripts/validate.sh` PASS.
