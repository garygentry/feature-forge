# Behavior-preservation run — R4, backlog item 012

**Scope.** The five authoring skill bodies: `skills/forge-0-epic/SKILL.md`,
`skills/forge-1-prd/SKILL.md`, `skills/forge-2-tech/SKILL.md`,
`skills/forge-3-specs/SKILL.md`, `skills/forge-4-backlog/SKILL.md`. Recorded per
`06-testing-strategy.md §9`, which marks the run **mandatory for R4**.

**Date.** 2026-07-29 · **Branch.** `forge/context-efficiency` · **Baseline.** `git HEAD`
at the time of the run = `30cb6b2` (`[rauf] 011: Convert shared-conventions.md's five
state-write touch points …`), i.e. the tree with all seven `state-*` verbs shipped and
only the shared `references/` surfaces converted.

**Form.** `§9`'s **reduced substitute for R4**, named explicitly as `§9` requires: *one
authoring stage plus a deliberately failed Commit 1, confirming the `--resumable` revert
path (status-only: assert `completedAt` is absent and `version` unchanged — a bare
`--status in-progress` would write both)*. It is combined with an exhaustive
section-granular static diff of the five edited bodies, and with a live end-to-end
exercise of **every** call site this item introduces.

---

## Comparison basis

The `consumption-data-refresh` dogfood corpus — the same evidence source used for `§7.4`
and re-measured in `.reference/REMEASURE-0.13.0.md` (**188** sessions, at
`~/.claude/projects/-home-gary-workspace-consumption-data-refresh/`).

Transcripts naming each surface these five bodies carry, confirmed present by grep:

| Surface rendered | Transcript(s) |
|---|---|
| `AskUserQuestion` option sets with `(recommended)` labelling | `11fe7945-9c68-49f9-97ef-f38da9a76d5a`, `19e50909-c587-46d0-b765-11d20871b3bb`, `257af5ca-d171-43c8-9a11-0f14adfbebf7` |
| NEXT-STEPS sentinel (`─ forge: end of stage ─`) | `257af5ca…`, `726ef9e2-196e-4a74-ad6b-f346a194b822`, `a8c7a107-ff7e-4574-a27a-be2f578a8de0` |
| Stage-Entry Guard *Interrupted* gate (`Resume the in-progress draft`) | `a8c7a107…`, `257af5ca…` |
| Stage-Entry Guard *Re-authoring* warning (`A completed … artifact already exists`) | `257af5ca…`, `a8c7a107…` |

Same corpus, same three anchor transcripts as the item-011 record, so the two runs are
directly comparable.

---

## The seven §9 surfaces

Method: split each body into `##`/`###` sections at the baseline and in the working tree
and compare byte-for-byte; then word-diff every changed section, and grep-diff each
frozen-surface marker across both revisions.

**Section census — 73 of 81 sections byte-identical:**

| Body | Sections | Byte-identical | Changed |
|---|---|---|---|
| `forge-0-epic/SKILL.md` | 16 | 15 | `### Step C7 — Create Member Subdirectories + Back-Pointer States` |
| `forge-1-prd/SKILL.md` | 13 | 11 | `### Interview Approach`, `## Step 6: Update Pipeline State and Commit` |
| `forge-2-tech/SKILL.md` | 28 | 26 | `### Interview Approach`, `## Step 7: Update Pipeline State and Commit` |
| `forge-3-specs/SKILL.md` | 14 | 12 | `## Step 3: Plan the Document Suite`, `## Step 7: Update Pipeline State and Commit` |
| `forge-4-backlog/SKILL.md` | 10 | 9 | `## Step 7: Update Pipeline State and Commit` |

No section was added, removed, or renamed in any body.

| # | §9 surface | Result across the five bodies |
|---|---|---|
| 1 | `AskUserQuestion` option sets, order, `(recommended)` labelling | **byte-identical.** 30 `AskUserQuestion` occurrences; the only two lines that differ are the forge-1-prd / forge-2-tech epic-backflow paragraphs, whose `AskUserQuestion` sentence (*"confirm `blocksCurrent` with a single `AskUserQuestion`, defaulting to `true`"*) is byte-identical — only the ECR-recording clause in the same paragraph changed. All 4 `(recommended)` occurrences byte-identical. |
| 2 | Decision Support wording | **byte-identical** in all five bodies (6 occurrences). |
| 3 | Branch Setup / Branch Reconciliation prompts | **not carried by these bodies** — they invoke the shared-conventions blocks, converted and verified in the item-011 record. `forge-0-epic` L95–97 (the `{scope}=epic` invocation) is byte-identical. |
| 4 | Stage-Entry Guard + Stage-Completion Re-check classification | **byte-identical.** 7 Stage-Entry-Guard and 4 Re-check invocation lines unchanged; the single `Stage-Entry Guard` line that differs is forge-3-specs' *Incremental artifact tracking* paragraph, whose changed words are only the artifact-write mechanic. |
| 5 | Two-commit Git Commit Protocol incl. the L245/L248 branches | **byte-identical.** Every stage's item-3 Git-Commit-Protocol sentence — including *"marking `stages.{stage}.status` `complete` with `commitHash: null` in that commit"*, *"never `--amend`"*, and *"If commit fails, leave status as `in-progress`"* — survives unchanged. The one `Git Commit Protocol` line that differs is forge-4-backlog's Step-7 header, where only the *"Write pipeline state conforming to …schema.json"* half was replaced. Live confirmation of both branches below. |
| 6 | Verify-gate routing + stage-exit directive handling | **byte-identical.** All five `DIRECTIVES` paragraphs and all five `stage-exit` fences unchanged. `forge-4-backlog` L148's `forge-verify-backlog` `"skipped"` write is untouched (deliberate `verifyEntry`-class exclusion, `03-state-verbs.md §11.2` ledger (b)). |
| 7 | NEXT-STEPS block and its sentinel | **byte-identical** in all five bodies. |

**Every removed line is a JSON-authoring mechanic.** `git diff -U0` against `30cb6b2`
removes 29 lines across the five bodies: five `Write pipeline state conforming to
references/pipeline-state-schema.json` headers, five `Update/Create … .pipeline-state.json:`
list heads and their 17 field bullets, the forge-3-specs incremental-tracking sentence,
and the two epic-backflow ECR-shape clauses. No prompt, gate, guard classification, or
Decision Support sentence is among them.

---

## Live exercise — every call site this item introduces

Run against a temp fixture with `python3 scripts/forge-session.py`, in the order the
converted bodies emit them:

| Call site | Command | Result |
|---|---|---|
| shared-conventions Entry Stamp | `state-enter --stage forge-1-prd` | `entered forge-1-prd (in-progress)` |
| shared-conventions Branch Setup | `state-branch --branch feature/demo` | `recorded branch` |
| **forge-1-prd Step 6 item 1** | `state-complete --stage forge-1-prd --version 1 --artifact PRD.md` | `status=complete`, `completedAt`, `version=1`, `basedOnVersions={}`, `artifacts=["PRD.md"]`, `commitHash=null` |
| **forge-1-prd Step 6 item 2** | `state-note --note "…"` | `note set (39 chars)` |
| Git Commit Protocol Commit 2 | `state-complete … --commit-hash deadbeef` | `recorded forge-1-prd commitHash` (nothing else touched) |
| **forge-3-specs Step 3** | `state-artifact --stage forge-3-specs --path …` ×2 | `(1 total)` then `(2 total)` |
| **forge-1-prd / forge-2-tech epic backflow** | `state-ecr --epic demo-epic --kind add-feature --raised-by forge-1-prd --blocks-current true` | `epic change request recorded (add-feature → auth-svc, blocksCurrent=true)` |

Both resulting `.pipeline-state.json` files (standalone feature and nested epic member)
validate against `references/pipeline-state-schema.json` with **zero findings** via the
stdlib validator `tests/_state_schema.py` — no `jsonschema`.

## Deliberately failed Commit 1 — the `--resumable` revert path (§9's named substitute)

Fixture: a stage that carries the Entry Stamp and whose Commit-1 completion write did not
land. Two clones of that identical state, one per branch:

```
A (--resumable):          {"status": "in-progress", "startedAt": "2026-07-29T06:24:29Z"}
B (--status in-progress): {"status": "in-progress", "startedAt": "…", "completedAt": "…",
                           "version": 1, "basedOnVersions": {}, "artifacts": [],
                           "commitHash": null}
```

- **A** — `state-complete … --version 1 --resumable` → `left forge-1-prd in-progress
  (resumable — no completion recorded)`. Asserted: `completedAt` **absent**, `version`
  **absent/unchanged**, `artifacts` absent, `commitHash` absent, **no cascade**. This is
  what shared-conventions L245 (*"leave state as `in-progress` so the stage can be
  resumed"*) now routes through.
- **B** — the contrast the AC calls for: a bare `--status in-progress` (forge-5-loop's
  *partial completion*) writes **both** `completedAt` and `version`. Confirms the two
  in-progress callers stay distinguishable, which schema validation cannot catch —
  `stageEntry` declares `status` and `completedAt` as independent optional properties.

L248's `--preserve-commit-hash` branch is unchanged prose in shared-conventions and was
confirmed in the item-011 record.

---

## REQ-BEHAV-02 review flag — one wording/behavior change, not silently adapted

**`currentStage` is no longer advanced at stage completion.** Each converted body
previously carried a `Set currentStage to <next stage>` bullet. `state-complete` does not
write `currentStage`, and `03-state-verbs.md §13.1`'s authoritative before/after for
forge-1-prd Step 6 **omits it** from the after-block; no verb can set it to an arbitrary
value (`state-enter` would also stamp the target stage `in-progress` and rewrite
`startedAt`). So the bullet was dropped in all four converted completion steps, per spec.

Assessed impact — **display-only, and it moves the field toward its documented meaning**:

- `next_stage()` (`scripts/forge-session.py` L320–336) derives "what runs next" from
  `stages[].status`, **never** from `currentStage`; its docstring says so explicitly. All
  routing (`nextStage`, `nextCommand`, the stage-exit successor comparison) is unaffected.
- `currentStage` is documented as *"where the pipeline IS"* (schema O1;
  `shared-conventions.md` Entry Stamp, L301) — which the completion step setting it to the
  **next** stage already contradicted. `render-status` uses it for display only and falls
  back to the derived next stage when absent (L495–498).
- Net observable difference: between stage N's completion and stage N+1's Entry Stamp, the
  dashboard shows `currentStage: forge-N` instead of `forge-N+1`. The `next:` column,
  driven by `next_stage()`, is unchanged.

Flagged here for review rather than silently adapted, per REQ-BEHAV-02.

## Deliberate R4 exclusion confirmed — `forge-0-epic` Step C7

`skills/forge-0-epic/SKILL.md` Step C7 (L224–232) keeps hand-authoring the member stub.
It is the **same site** as the ledger's exclusion 3(i) in `03-state-verbs.md §11.2` — *"the
Member State Example (creation C7) member-subdir stub write"* — whose rationale (*"none of
the seven verbs writes the `epic` back-pointer a brand-new member stub needs"*) names
forge-0-epic's own 8 lines of body headroom, so it plainly covers the instruction in
`SKILL.md` as well as the example in `references/edit-mode.md`. The body now says so in
place (0 added lines). This is **not** the item's cap-driven DEFER clause: the conversion
is impossible, not merely tight, and forge-0-epic's body is unchanged at **292/300 lines**.
Item 013's repo-wide census should name `skills/forge-0-epic/SKILL.md` Step C7 alongside
the `edit-mode.md` site.

---

## Gates

- `python3 -m pytest tests` — **638 passed, 2 skipped**
- `python3 scripts/check-spec-purity.py` — **PASS, 0 violations** (incl. Rule 5 prelude
  byte-identity on all 7 new preludes)
- `.venv-adapters/bin/python3 scripts/build-adapters.py --check` — **exit 0**
- `bash scripts/validate.sh` — **All checks passed!**

**Conclusion.** All seven §9 surfaces are preserved; 73 of 81 sections are byte-identical
and every changed word is a state-authoring mechanic. SC-3 is satisfied for this item's
scope, with the single REQ-BEHAV-02 `currentStage` item flagged above for owner review.
