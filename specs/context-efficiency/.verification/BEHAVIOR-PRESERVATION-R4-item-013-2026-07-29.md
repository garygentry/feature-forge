# Behavior-preservation run — R4, backlog item 013

**Scope.** The four remaining R4 touch points: `skills/forge-5-loop/SKILL.md`,
`skills/forge-6-docs/SKILL.md`, `skills/forge/SKILL.md` (the navigator),
`skills/forge-verify/SKILL.md` — plus the one prose block this item relocates into
`skills/forge-5-loop/references/runner-contract.md` to stay inside the 300-line body cap.
Recorded per `06-testing-strategy.md §9`, which marks the run **mandatory for R4**.

**Date.** 2026-07-29 · **Branch.** `forge/context-efficiency` · **Baseline.** `git HEAD`
at the time of the run = `032f3dd` (`[rauf] 012: Convert the five authoring skill bodies
to state-verb calls`), i.e. the tree with all seven `state-*` verbs shipped and both the
shared `references/` surfaces (item 011) and the five authoring bodies (item 012)
already converted. This item is R4's **last** conversion, so the baseline is the
complete-but-for-these-four state.

**Form.** `§9`'s **reduced substitute for R4**, named explicitly as `§9` requires: *one
authoring stage plus a deliberately failed Commit 1, confirming the `--resumable` revert
path (status-only: assert `completedAt` is absent and `version` unchanged — a bare
`--status in-progress` would write both)*. It is combined with an exhaustive
section-granular static diff of the five edited files and a live end-to-end exercise of
**every** call site this item introduces.

---

## Comparison basis

The `consumption-data-refresh` dogfood corpus — the same evidence source used for `§7.4`
and re-measured in `.reference/REMEASURE-0.13.0.md` (**188** sessions, at
`~/.claude/projects/-home-gary-workspace-consumption-data-refresh/`). Same corpus as the
item-011 and item-012 records, so the three runs are directly comparable.

Transcripts naming the surfaces **these four bodies** carry, confirmed present by grep:

| Surface rendered | Transcript(s) |
|---|---|
| forge-5-loop launch + `Loop started for …` inform-user block (Step 3c) | `19e50909-c587-46d0-b765-11d20871b3bb`, `9f7238d4-8fa3-4f50-a688-43551cdd5ead` |
| forge-6-docs Step 5 close (`Documentation complete.`) | `19e50909…`, `425c0b38-6556-4aa8-b4bc-cadb1a40985c` |
| forge-verify Decision Support (a/b/c, `Run /feature-forge:forge-fix …`) | `9f7238d4…`, `19e50909…` |
| `AskUserQuestion` option sets with `(recommended)` labelling | `11fe7945-9c68-49f9-97ef-f38da9a76d5a`, `19e50909…`, `257af5ca-d171-43c8-9a11-0f14adfbebf7` |
| NEXT-STEPS sentinel (`─ forge: end of stage ─`) | `257af5ca…`, `726ef9e2-196e-4a74-ad6b-f346a194b822`, `a8c7a107-ff7e-4574-a27a-be2f578a8de0` |
| Stage-Entry Guard *Interrupted* / *Re-authoring* gates | `a8c7a107…`, `257af5ca…` |

`pipelineStatus` appears in **46** of the 188 transcripts and `note:` in **75**, so the
navigator's two write paths (the one converted here and the one deliberately excluded)
are both live surfaces in the corpus, not hypotheticals.

---

## The seven §9 surfaces — all confirmed identical

Method: split every edited file into `##`/`###`/`####` sections at the baseline and in
the worktree, compare byte-for-byte; then read **every** removed line in
`git diff -U0 -- skills/`.

**Section-granular result: 80 of 88 sections byte-identical.**

| File | Identical | Changed sections |
|---|---|---|
| `skills/forge-5-loop/SKILL.md` | 26/29 | `3a. Update Pipeline State`, `3c. Inform User`, `Step 5: Update Pipeline State` |
| `skills/forge-6-docs/SKILL.md` | 18/19 | `Step 5: Update Pipeline State and Commit` |
| `skills/forge/SKILL.md` | 9/11 | `4. Notes Management`, `6. Pipeline Lifecycle Commands` |
| `skills/forge-verify/SKILL.md` | 18/19 | `Step 6: Update Pipeline State` |
| `skills/forge-5-loop/references/runner-contract.md` | 9/10 | `Inform-user output template (Step 3c)` |

**All 22 removed lines** are JSON-authoring mechanics, except the 7-line Step-3c
paragraph, which was **relocated verbatim** (see "Line budget" below). No prompt, guard,
classification, or template sentence was reworded.

1. **`AskUserQuestion` option sets / order / `(recommended)` labelling** — identical.
   Every option set in the four bodies sits in a byte-identical section: forge-5-loop 1b
   (`Verify first (recommended)` · `Continue without verifying`), 1b-epic, 2d Run mode
   (the three-option fixed order), 2d agent selection, 5b, 6.1, 6.3 and the Standard
   Verify Gate's three options; forge-6-docs Step 1 impl-verify warning and Step 4
   review; forge-verify's Decision Support (a)/(b)/(c). The navigator's `abandon`
   confirmation `Offer **Abandon** · **Pause instead** · **Cancel**.` is byte-identical
   — asserted directly, since its enclosing section did change (see 4 below).
2. **Decision Support wording** — identical. `forge-verify` Step 5 is untouched; the
   frozen sentence `Follow the **Decision Support** protocol in
   `references/shared-conventions.md`…` and all three options are byte-for-byte.
3. **Branch Setup / Branch Reconciliation prompts** — identical. Both live in
   `references/shared-conventions.md`, which this item does not edit;
   `forge-5-loop` 1f's pointer to the Branch Reconciliation block is byte-identical.
4. **Stage-Entry Guard + Stage-Completion Re-check classification** — identical. Both
   blocks live in `references/shared-conventions.md` (untouched here). `forge-5-loop`'s
   own pre-launch marker is *not* the Stage-Entry Guard: it is the conversion-map
   pre-launch write, and only its mechanic changed.
5. **Two-commit Git Commit Protocol incl. the L245/L248 failure branches** — identical.
   The protocol itself is in `shared-conventions.md` (untouched). `forge-6-docs` Step 5
   item 2 — which names the artifact commit, the two-commit follow-up, `never --amend`,
   and `If commit fails, leave status as in-progress` — is byte-identical, asserted
   directly because its enclosing section changed. `forge-5-loop`'s `Then commit this
   state write before launching (mandatory).` and `**No git commit is needed**` are
   likewise byte-identical.
6. **Verify-gate routing + stage-exit directive handling** — identical. `forge-5-loop`
   Steps 5b and 6 (including `record stages.forge-verify-impl.status as "skipped"` and
   the Standard Verify Gate) are byte-identical; `references/stage-exit-protocol.md` is
   untouched; `tests/test_stage_exit_protocol.py` passes unchanged.
7. **The NEXT-STEPS block and its sentinel** — identical. Owned by
   `references/stage-exit-protocol.md` and `forge-session.py stage-exit`, neither edited.

### One REQ-BEHAV-02 flag, raised not silently adapted

Both converted completion steps dropped a `currentStage` advancement bullet:
`forge-5-loop` Step 5 item 2 (`→ "forge-6-docs"`) and `forge-6-docs` Step 5 item 1
(`→ complete`). `state-complete` does **not** write `currentStage`, and spec 03 §13.1's
authoritative after-block omits it — this is the **same** flag item 012 raised for the
five authoring bodies, applied consistently here rather than resolved differently.

Impact is display-only and arguably a correction. `next_stage()` derives "what runs
next" from `stages[].status` and its docstring calls itself *"intentionally distinct
from the stored `currentStage` field"*; `build_rows` uses `currentStage` for display
with a `(nxt or "complete")` fallback. The one visible consequence is that a finished
pipeline's dashboard now shows `currentStage: forge-6-docs` (the last stage started)
instead of `complete`, which matches the schema's own definition of the field —
*"where the pipeline IS: the most recently started stage"*. **Flagged for owner review.**

---

## The reduced substitute, executed

Fixture: `/tmp/r4i13/specs/{demo,rev}/`, driven with the real script.

**(a) Every call site this item introduces, run end-to-end:**

| Call site | Command | Result |
|---|---|---|
| forge-5-loop 3a pre-launch marker | `state-enter --stage forge-5-loop` | `entered forge-5-loop (in-progress) for demo` |
| forge-5-loop Step 5, partial | `state-complete --stage forge-5-loop --version 1 --status in-progress --based-on forge-4-backlog=2 --artifact …` | `partially completed (in-progress) forge-5-loop v1` |
| forge-5-loop Step 5, complete | same with `--status complete` | `completed forge-5-loop v1 (commitHash: null)` |
| forge-6-docs Step 5 | `state-complete --stage forge-6-docs --version 1 --based-on ×3 --artifact …` | `completed forge-6-docs v1 (commitHash: null)` |
| navigator Notes Management | `state-note --note "switching to jose for JWT"` | `note set for demo (25 chars)` |

Every resulting `.pipeline-state.json` validates against
`references/pipeline-state-schema.json` with **zero findings** via `tests/_state_schema.py`
(stdlib validator, no `jsonschema`).

The partial-completion call confirms the distinction item 009 built `--status` for: with
`--status in-progress` the entry still carries `completedAt`, `version: 1`,
`basedOnVersions: {"forge-4-backlog": 2}` and `artifacts` — only `status` differs from
the complete branch. So forge-5-loop's `--based-on forge-4-backlog=N` is **not** silently
discarded on a partial run.

**(b) The deliberately failed Commit 1 (`--resumable`), with its control.**

Per item 012's finding, the discriminating fixture is **entered-but-not-completed** —
clone that one state twice and run the two forms against identical input:

| Branch | Command | Resulting `stages["forge-6-docs"]` |
|---|---|---|
| **A — failed Commit 1** | `state-complete --stage forge-6-docs --version 2 --resumable` | `{status: "in-progress", startedAt: …}` |
| **B — control** | `state-complete --stage forge-6-docs --version 2 --status in-progress` | `{status, startedAt, completedAt, version: 2, basedOnVersions: {}, artifacts: [], commitHash: null}` |

Asserted on A: **`completedAt` absent** and **`version` unchanged** (still absent — the
stage had never completed). B writes **both**, proving the assertion discriminates and
that `--resumable` is genuinely distinct from a bare `--status in-progress`. This is the
`shared-conventions.md` L245 contract — *"leave state as in-progress so the stage can be
resumed"* — still executable now that no site may hand-author JSON.

---

## Line budget — the sanctioned relocation (owner decision 2026-07-29)

`skills/forge-5-loop/SKILL.md` had **2** spare body lines (298/300 measured,
frontmatter stripped). The two conversions cost **+4** lines (each fenced call carries
its own inlined two-line `BOOTSTRAP_PRELUDE`; there is no compact form, R2 being scoped
out). R4 is **not** deferrable (REQ-R4-04), so per this item's own instruction the lines
were recovered by **relocating an existing prose block verbatim** into
`skills/forge-5-loop/references/runner-contract.md` — the file item 015 already
restructures, and which `forge-5-loop` reads on every run.

Relocated: the 7-line Step-3c paragraph (`Tell the user the run has started …`). It
moves **verbatim**, as a blockquote under the existing `## Inform-user output template
(Step 3c)` section — the natural home, since the paragraph already deferred its
template there. The body keeps a one-line citation of
`references/runner-contract.md`, so adapter citation fan-out still ships the file.

| File (body, frontmatter stripped) | Before | After | Δ lines | Δ words |
|---|---|---|---|---|
| `skills/forge-5-loop/SKILL.md` | 298 L / 4,415 w | **296 L / 4,478 w** | **−2** | +63 |
| `skills/forge-5-loop/references/runner-contract.md` | 335 L / 2,820 w | 345 L / 2,899 w | +10 | +79 |
| `skills/forge-6-docs/SKILL.md` | 186 L / 1,722 w | 192 L / 1,823 w | +6 | +101 |
| `skills/forge/SKILL.md` | 227 L / 3,967 w | 235 L / 4,083 w | +8 | +116 |
| `skills/forge-verify/SKILL.md` | 259 L / 2,528 w | 267 L / 2,611 w | +8 | +83 |

`forge-5-loop` lands at **296/300 lines** and **4,478/5,000 words** — under both caps,
with 4 lines of headroom left for items 006 and 015. No prelude was dropped, no cap was
raised, no unrelated line was deleted.

---

## Gates

- `python3 -m pytest tests` — **638 passed, 2 skipped**
- `python3 scripts/check-spec-purity.py` — **PASS, 0 violations** (Rule 5 prelude
  byte-identity green on all 3 new preludes)
- Per-fence prelude audit of the four bodies — **12/12** fences containing
  `$R/scripts/` open with the full two-line prelude *inside that same fence*
- `references/pipeline-state-schema.json` — **unchanged** (191 L / 1,149 w, byte-identical)
