# Behavior-preservation run — R6, backlog item 015

**Scope.** The `runner-contract.md` always/conditional split: three agent-conditional
sections move out of `skills/forge-5-loop/references/runner-contract.md` into a new
`skills/forge-5-loop/references/agent-selection.md`, and four citation pointers in
`skills/forge-5-loop/SKILL.md` are trimmed or re-pointed. Recorded per
`06-testing-strategy.md §9`, which marks the run **mandatory for R6**.

**Date.** 2026-07-29 · **Branch.** `forge/context-efficiency` · **Baseline.** `git HEAD`
at the time of the run = `c532602` (`[rauf] 006: Switch forge-4-backlog and forge-5-loop
to effective-config`), i.e. the tree with R1, R3, R4 and R5 all landed. R6 is the last
unit, and item 015 is the only item that can check the combined 300-line budget on this
body, so the baseline is the complete-but-for-R6 state.

**Form.** `§9`'s **reduced substitute for R6**, named explicitly as `§9` requires: *one
gate-off and one gate-on loop launch, confirming `agent-selection.md` is read only in the
second*. It is combined with an exhaustive section-granular static diff of both edited
files and a byte-for-byte verification that every moved span is verbatim.

**Honest scope note.** The two "launches" below resolve the gate with the **real**
`effective-config` resolver against two real configs, and then determine the reference-file
read-set by a **citation-reachability trace over the SKILL body** — the same regex the
adapter fan-out uses. They are not two live interactive loop launches; a real launch needs
a populated backlog, an installed runner, and a human at three `AskUserQuestion` prompts.
What is executed is the part the substitute is actually about: *which file does each run
open*. That determination is mechanical and is reproduced verbatim below.

---

## Comparison basis

The `consumption-data-refresh` dogfood corpus — the same evidence source used for `§7.4`
and re-measured in `.reference/REMEASURE-0.13.0.md` (**188** sessions, at
`~/.claude/projects/-home-gary-workspace-consumption-data-refresh/`). Same corpus as the
item-011, item-012 and item-013 records, so all four runs are directly comparable.

Transcripts naming the surfaces **this item's two files** carry, confirmed present by grep
(the same set item 013's record cites for forge-5-loop, since R6 touches the identical
body):

| Surface rendered | Transcript(s) |
|---|---|
| forge-5-loop Step 2d confirmation block + rendered run command | `19e50909-c587-46d0-b765-11d20871b3bb`, `9f7238d4-8fa3-4f50-a688-43551cdd5ead` |
| forge-5-loop launch + `Loop started for …` inform-user block (Step 3c) | `19e50909…`, `9f7238d4…` |
| `AskUserQuestion` option sets with `(recommended)` labelling | `11fe7945-9c68-49f9-97ef-f38da9a76d5a`, `19e50909…`, `257af5ca-d171-43c8-9a11-0f14adfbebf7` |
| NEXT-STEPS sentinel (`─ forge: end of stage ─`) | `257af5ca…`, `726ef9e2-196e-4a74-ad6b-f346a194b822`, `a8c7a107-ff7e-4574-a27a-be2f578a8de0` |
| Stage-Entry Guard *Interrupted* / *Re-authoring* gates | `a8c7a107…`, `257af5ca…` |
| Branch Setup / Reconciliation prompts | `a8c7a107…`, `11fe7945…` |

Every corpus session runs the loop with the agent gate at its **schema default**
(`agentArgument = "--agent {agent}"`, i.e. gate-**on**) — verified below. So the corpus
transcripts are the comparison basis for the gate-on case, and the gate-off case is a
strictly-smaller read-set of the same text.

---

## The reduced substitute — gate-off vs gate-on

### Step 1 — resolve the gate with the real resolver

```
$ echo '{"loopRunner":{"agentArgument":""}}'                > /tmp/r6-gate-off/forge.config.json
$ echo '{"loopRunner":{"agentArgument":"--agent {agent}"}}' > /tmp/r6-gate-on/forge.config.json
$ python3 scripts/forge-session.py effective-config --config /tmp/r6-gate-off/forge.config.json --json
  agentArgument=''                 name='rauf'  defaultAgent=''
$ python3 scripts/forge-session.py effective-config --config /tmp/r6-gate-on/forge.config.json  --json
  agentArgument='--agent {agent}'  name='rauf'  defaultAgent=''
```

Schema default for `loopRunner.agentArgument` is `"--agent {agent}"`, so **gate-on is the
default posture** and gate-off requires an explicit empty override. Both resolve exactly as
the Step 2d capability sentence expects (*"present and non-empty"* → on).

### Step 2 — the read-set each run opens

Citation-reachability trace over the frontmatter-stripped body, using the fan-out regex
`(?<![./\w-])references/([A-Za-z0-9_][A-Za-z0-9_./{}*-]*?\.md)\b`. The gated block is
body lines **168–179** (`#### Agent selection (gated on \`loopRunner.agentArgument\`)`
through the next `## ` heading).

```
OUTSIDE the gated block — read on EVERY run (gate-off AND gate-on):
  ralph-loop-contract.md    [10]
  shared-conventions.md     [39, 43, 73, 113]
  runner-contract.md        [161, 164, 166, 192, 196, 196, 200, 219, 296]
  result-reporting.md       [239, 246]
  stage-exit-protocol.md    [273]

INSIDE the gated block — read ONLY when agentArgument is present:
  agent-selection.md        [170, 176, 177]
```

**`references/agent-selection.md` occurs zero times outside the gated block and three times
inside it.** That is the substitute's assertion, satisfied literally:

- **Gate-off launch** — reads `runner-contract.md` (248 L / 2,050 w). Never opens
  `agent-selection.md`; the body gives it no reachable pointer above the gate.
- **Gate-on launch** — reads `runner-contract.md` **and** `agent-selection.md`
  (112 L / 961 w), whose union is the nine original sections, so the gate-on run sees
  exactly the text it saw before the split.

The one non-body cross-reference — `runner-contract.md`'s own preamble — names
`agent-selection.md` but states inline that it is *"read **only** when the Step 2d
`loopRunner.agentArgument` capability gate is on"*, so it does not function as an
unconditional read instruction on the gate-off path.

### Step 3 — the moved text is verbatim

```
$ diff <(sed -n '8,96p'  agent-selection.md) <(git show HEAD:…/runner-contract.md | sed -n '23,111p')   → identical
$ diff <(sed -n '97,112p' agent-selection.md) <(git show HEAD:…/runner-contract.md | sed -n '153,168p') → identical
$ diff <(sed -n '1,22p'   runner-contract.md) <(git show HEAD:… | sed -n '1,22p')                       → identical (pre-preamble-edit)
$ diff <(sed -n '23,63p'  runner-contract.md) <(git show HEAD:… | sed -n '112,152p')                    → identical
$ diff <(sed -n '64,246p' runner-contract.md) <(git show HEAD:… | sed -n '169,351p')                    → identical
```

The L152→L169 seam flagged in spec 05 §3.2 was checked: `## Run mode`'s last bullet is
immediately followed by `## Launch detail`'s heading, with no orphaned prose.

---

## The seven §9 surfaces — all confirmed identical

Method: split both edited files into `##`/`###`/`####` sections at the baseline and in the
worktree, compare byte-for-byte; then read **every** removed line in `git diff -U0`.

**Section-granular result:**

| File | Identical | Changed | Moved out |
|---|---|---|---|
| `skills/forge-5-loop/SKILL.md` | 27/29 | `### 2d. Confirm with User`, `#### Agent selection (gated on …)` | — |
| `…/references/runner-contract.md` | 6/10 | `(preamble)` | the three conditional sections (→ `agent-selection.md`) |

**Every removed line in the SKILL body — all four are citation pointers:**

1. `provider default) and the full optional-flags catalog, read references/runner-contract.md.`
   → re-added as `provider default), read references/runner-contract.md.` (the §3.4 trim).
2. The **Capability gate** sentence — re-added byte-identical except
   `## Agent selection` of `references/runner-contract.md` → `…of references/agent-selection.md`.
3. The **(d-model)** bullet — re-added byte-identical except
   `Full rationale: references/runner-contract.md` → `…references/agent-selection.md`.
4. The **(e)** bullet — re-added byte-identical plus a trailing clause naming
   `## Optional flags catalog (Step 2d, rauf)` in `references/agent-selection.md`.

No other line in either file was removed. Surface-by-surface:

| # | §9 surface | Verdict |
|---|---|---|
| 1 | `AskUserQuestion` option sets / order / `(recommended)` | **Identical.** Run-mode options 1/2/3 and their exact order live in `## Run mode (Step 2d, rauf)`, which **stays** in `runner-contract.md` (always-loaded). The gated agent question (b)/(d)/(d-model) option sets are byte-identical; only the pointer at the end of their bullets changed. |
| 2 | Decision Support wording | **Identical.** Not carried by either file; `git diff` touches no Decision Support prose. |
| 3 | Branch Setup / Reconciliation prompts | **Identical.** Owned by `references/shared-conventions.md`, untouched by this item (`git status` shows no change). |
| 4 | Stage-Entry Guard + Stage-Completion Re-check classification | **Identical.** Owned by `shared-conventions.md`; forge-5-loop's Step 1a/3a text is unchanged. |
| 5 | Two-commit Git Commit Protocol incl. L245/L248 branches | **Identical.** Owned by `shared-conventions.md`; forge-5-loop's Step 3a commit paragraph is byte-identical (not in the changed-section list). |
| 6 | Verify-gate routing + stage-exit directive handling | **Identical.** Step 5b and Step 6.6's Standard Verify Gate are byte-identical; `tests/test_stage_exit_protocol.py` passes unchanged. |
| 7 | NEXT-STEPS block and its sentinel | **Identical.** Step 6.6's fenced next-command block is untouched. |

---

## Flagged for owner review (REQ-BEHAV-02) — not silently adapted

**The optional-flags catalog is no longer reachable on a gate-off run.** Section 5
documents `--agent`, `--review`, `--model`, `--timeout` and `--retry-blocked`; spec 05
§3.2 classifies it CONDITIONAL and moves it to `agent-selection.md`, so a gate-off launch
that previously could open the catalog via the L165 pointer no longer can. This is the
specified design (§3.3 calls it *"reachable but not loaded by default"*), and the practical
loss is small — `--review`/`--retry-blocked` are fully specified in the kept
`## Run mode` section, and `--model`/`--timeout` are named inline in the body's Run-mode
paragraph — but it is the one place where a gate-off run's *available* text shrinks rather
than merely relocating. Recorded here rather than adapted around.

Same class as, and consistent with, the `currentStage` flags raised in the item-012 and
item-013 records.

---

## Gates

- `python3 -m pytest tests` — **646 passed / 2 skipped** (the new
  `tests/test_runner_contract_split.py` adds 8).
- `python3 scripts/check-spec-purity.py` — **PASS** (Rule 4: body 298/300 lines,
  4,564/5,000 words).
- `.venv-adapters/bin/python3 scripts/build-adapters.py --check` — **exit 0**;
  `agent-selection.md` present under all **six** bundles including `adapters/pi/`.
- `bash scripts/validate.sh` — **PASS**.

**Guard mutation-tested** (both restored with `command cp -f`, re-verified green):

1. Added `references/agent-selection.md` to the pointer above the gate →
   `test_agent_selection_is_cited_only_below_the_capability_gate` red:
   *"references/agent-selection.md is cited above the capability gate at body line(s)
   [161] — a gate-off run would load it, defeating REQ-R6-02"*.
2. Truncated `## Optional flags catalog` off `agent-selection.md` → two red:
   `test_agent_selection_holds_exactly_the_three_conditional_sections` and
   `test_the_union_of_both_files_is_the_original_nine_sections`
   (*"the split dropped, renamed or duplicated a section…"*).
