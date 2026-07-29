# 01 — Architecture & Layout

> **R2 is SCOPED OUT (2026-07-28; PRD §3.2).** This feature ships **five** units — R1,
> R3, R4, R5, R6. No manifest row, revert row, sequencing node, or test below describes
> R2 work any more; author no backlog items for it.

> Where the changes live. Because `context-efficiency` adds **no new package**
> (tech-spec §2), this document is not a directory-tree-for-a-new-module — it is
> (a) the exhaustive **file-move manifest** grouped by revert unit, (b) the
> `forge-session.py` module layout showing where the R4/R5 handlers slot in,
> (c) the **citation graph** that makes every moved file ship to all five
> adapters, and (d) the **delivery sequencing and revert boundaries** that make
> R1, R3, R4, R5 and R6 independently shippable (REQ-DELIV-01).
>
> Builds on `00-core-definitions.md` (script conventions §3, state shapes §4,
> portability contract §9). Does not restate them.

## Requirement Coverage

| REQ ID | Requirement | Section |
|--------|-------------|---------|
| REQ-DELIV-01 | Each of R1, R3–R6 independently shippable + revertible | §4 (revert boundaries), §5 (sequencing) |
| REQ-PORT-01 | Every new/moved file cited by ≥1 skill body | §3 (citation graph) |
| REQ-PORT-03 | All **six** adapter targets regenerate; fixtures refreshed | §3.2 (adapter build), §6 |
| REQ-R6-03 | Split must not push runner-contract text back into the forge-5-loop body | §2.2 (cap ledger) |
| REQ-R4-04 (cap side-constraint) | R4 verb conversions stay within each body's measured headroom | §2.2 (cap ledger) |
| REQ-R4-04 | All state-write sites covered | §1 (touched-files table, R4 rows) |
| REQ-MAINT-01 | Drift-guard coverage per split/moved file | §6 (test surface) |

---

## 1. File-move manifest

No new package. All changes are confined to the canonical surfaces the adapter
build fans out from (`skills/`, `references/`, `scripts/`, `tests/`). Files
grouped by unit; **D**=deleted, **N**=new, **M**=modified.

```
scripts/
  forge-session.py                 M  R4: +7 state verbs, +_write_state, +_now_iso (NEW)
                                       R5: +effective-config subcommand
                                          (1,888 lines at 0.13.0; argparse + if-dispatch)
references/
  pipeline-state-schema.json       .  R4: UNCHANGED content; remains CI source of truth
  forge-config-schema.json         .  R5: UNCHANGED content; read at runtime for defaults
  process-overview.md              .  R3: read-site relocated (file itself unchanged)
  shared-conventions.md            M  R4: Stage-Entry Guard / Branch Setup / completion
                                          steps switch to state-verb calls (PROSE UNCHANGED)
skills/forge/SKILL.md              M  R3 (gate read); R4 (state-note at L185)
                                       NB: pipelineStatus writes (L215–228) are OUT of R4
skills/forge-0-epic/SKILL.md       M  R4 (state verbs) — strictly in-place, 8 lines spare
skills/forge-1-prd/SKILL.md        M  R4 (state verbs)
skills/forge-2-tech/SKILL.md       M  R4 (state verbs)
skills/forge-3-specs/SKILL.md      M  R4 (state verbs)
skills/forge-4-backlog/SKILL.md    M  R4 (state verbs); R5 (effective-config consumer)
skills/forge-6-docs/SKILL.md       M  R4 (state-complete at L173–182)
skills/forge-verify/
  SKILL.md                         M  R1: cite the 6 mode files + findings-template.md;
                                          reconcile Step-3 expected-count table
                                       R4: production stageEntry stamps ONLY
                                          (verifyEntry path unchanged — see 00 §4.2)
  references/
    verification-checklists.md     D  R1: DELETED, replaced by ↓
    verification-checklists/       N  R1: NEW directory
      prd.md                       N     CHECK-P01..P15  (15)
      tech.md                      N     CHECK-T01..T17  (17)
      specs.md                     N     CHECK-S01..S38  (38)
      backlog.md                   N     CHECK-B01..B27  (27)
      impl.md                      N     CHECK-I01..I23  (23, incl. Runnability I21/I22/I23)
      epic.md                      N     CHECK-E01..E10  (10)
    findings-template.md           N  R1: NEW — 3 orchestrator-only sections
agents/forge-verifier.md           M  R1: dispatch prompt names the mode → reads only
                                          verification-checklists/{mode}.md (read-only agent)
skills/forge-5-loop/
  SKILL.md                         M  R6: 1:1 citation swap (line-neutral; 298/300, 2 spare)
                                       R5: effective-config consumer
                                       R4: state-enter (L188–189), state-complete (L258–263)
  references/
    runner-contract.md             M  R6: keeps the 6 always-loaded sections
    agent-selection.md             N  R6: NEW — 3 agent-conditional sections
tests/
  test_verification_checklists_split.py  N  R1 drift guard (§6)
  test_state_verbs.py                    N  R4 drift guard (§6)
  test_effective_config.py               N  R5 drift guard (§6)
  test_process_overview_read.py          N  R3 drift guard (§6)
  test_runner_contract_split.py          N  R6 drift guard (§6)
  (existing guards refreshed for fixtures: test_build_adapters.py snapshot)
```

> Test filenames above are indicative; `06-testing-strategy.md` owns the exact
> assertions. What is binding is that **every split/moved file gets a drift
> guard** (REQ-MAINT-01).

**Public API surface** (what other pipeline code consumes): only the new
`forge-session.py` subcommands (`state-enter`, `state-artifact`,
`state-complete`, `state-note`, `state-decision`, `state-ecr`, `state-branch`,
`effective-config`). Their contracts are the only new "exports"
(`03-state-verbs.md` §2 overview + §4–§10 per-verb contracts;
`04-effective-config.md` §2 CLI Contract + §5 Output). The other half of the
skill-facing contract is the citation set in §3.1: `references/verification-checklists/`
`{prd,tech,specs,backlog,impl,epic}.md` (cited **literally**, one path each — see §3.1),
`references/findings-template.md`, and `references/agent-selection.md`.

## 2. `forge-session.py` module layout (R4 + R5)

### 2.1 Where the new code slots in

The script is organized as: module docstring → constants → small pure helpers →
`main()` with `argparse` subparsers + an `if args.cmd == …` dispatch chain
guarded by `if __name__ == "__main__": sys.exit(main())`. The additions
(00-core-definitions §3):

```
scripts/forge-session.py
├── module docstring                 M  add usage lines for the 8 new subcommands
├── (existing helpers)
│   ├── _read_state (L177)           .  reused by every state verb
│   ├── _load_config (L526)          .  reused by effective-config
│   ├── _resolve_feature_dir (L1416) .  reused by every state verb
│   └── UsageError (L168)            .  raised for bad args → exit 2
├── _write_state(path, state)        N  atomic temp-file + os.replace (§3.3 of doc 00)
├── import tempfile                  N  required by _write_state (§3.3 of doc 03)
├── _now_iso()                       N  NEW — Z-suffixed UTC ISO-8601 helper; no
│                                       equivalent exists today (verified: grep → 0)
├── STATE_VERB_STAGES                N  ('forge-0-epic', *PRODUCTION_STAGES) — do NOT
│                                       redefine PRODUCTION_STAGES (L99, order-sensitive)
├── _CASCADE_TARGETS                 N  downstream staleness cascade map
├── _load_state_for_write(...)       N  ┐ shared machinery (03 §3.4/§3.5/§3.6)
├── _stage_entry(...)                N  │
├── _commit_state(...)               N  │
├── _cascade_staleness(...)          N  │
├── _parse_based_on / _parse_bool    N  ┘
├── cmd_state_enter(...)             N  ┐
├── cmd_state_artifact(...)          N  │ R4 handlers — one per verb; each does
├── cmd_state_complete(...)          N  │ resolve→load→mutate→refresh updatedAt→write
├── cmd_state_note(...)              N  │ (may be inlined in the dispatch chain to
├── cmd_state_decision(...)          N  │  match the script's existing style — see
├── cmd_state_ecr(...)               N  │  03-state-verbs.md §3)
├── cmd_state_branch(...)            N  ┘
├── _default_schema_path()           N  ┐ R5 (04 §3.2/§3.3/§4)
├── _loop_runner_defaults(schema)    N  │ schema defaults
├── resolve_loop_runner(cfg, schema) N  ┘ + deep-merge over user config
├── _print_state_enter/_artifact/    N  seven per-verb printers (03 §11.1)
│   _complete/_note/_decision/
│   _ecr/_branch
├── _print_effective_config(res)     N  R5 printer (04 §5.2)
├── _emit(payload, json_output, fn)  N  shared JSON-vs-human dispatcher
└── main()                           M  register 8 subparsers; add 8 dispatch branches
```

`os` and `json` are already imported (L81 / L80). `_write_state` uses the
`tempfile.mkstemp` + fsync form selected in `03-state-verbs.md §3.3`, which requires
adding **`import tempfile`** to the L79–86 import block — the only new stdlib import
in this feature. Line anchors verified at 0.13.0; re-grep before editing, they shift
with any merge.

### 2.2 Skill-body line-cap ledger (C-2, hard constraint)

`check-spec-purity.py` **Rule 4 is a two-part gate**: `MAX_BODY_LINES = 300` **and**
`MAX_BODY_WORDS = 5000` (`scripts/check-spec-purity.py` L89 / L169). Both hard-fail CI,
and pytest does not run either — so a "line-neutral" edit must also be **word**-checked.
Body = the region after the frontmatter close; a raw `wc -l` overcounts by the
frontmatter length and is the wrong metric.

Body figures measured 2026-07-28 @0.13.0 (`.reference/REMEASURE-0.13.0.md`
§Line-cap headroom):

| Skill | Body lines | Body words | Unit(s) touching it | Net line effect |
|-------|-----------|-----------|---------------------|-----------------|
| `forge-5-loop/SKILL.md` | **298 / 300 (2 spare)** | 4,415 / 5,000 | R6, R5, R4 | must be **≤ +2 combined** — R6 is a strict 1:1 swap, R5 swaps one read for one call, R4 converts two write blocks |
| `forge-0-epic/SKILL.md` | **292 / 300 (8 spare)** | 2,531 / 5,000 | R4 | **0** — strictly in-place; any net addition needs a line audit first |
| `forge-verify/SKILL.md` | 257 / 300 (43 spare) | 2,502 / 5,000 | R1, R4 | small; must NOT inline orchestrator material (+~150 → over cap) |
| `forge/SKILL.md` | 227 / 300 (73 spare) | 3,936 / 5,000 | R3, R4 | neutral/negative |
| `forge-4-backlog/SKILL.md` | 159 / 300 (141 spare) | 2,225 / 5,000 | R4, R5 | neutral |
| `forge-6-docs/SKILL.md` | 186 / 300 (114 spare) | 1,722 / 5,000 | R4 | neutral |

`forge-bootstrap/SKILL.md` is **untouched** by this feature (R2 was its only unit) and is
no longer tracked here.

**Consequence:** R1's orchestrator material goes to `findings-template.md` (not inlined);
R6's `runner-contract.md` text is NOT pushed back into the loop body. No edit may push a
body over 300 lines or 5,000 words.

#### 2.2.1 Prelude position per R4/R5 call site (REQ-PORT-02, C-5)

R2 is scoped out, so **no compact prelude form exists**. Every new fenced call site
either reuses a full `BOOTSTRAP_PRELUDE` that already precedes it in the same body, or
inlines the full two-line prelude (~4 lines with the fence). Measured positions:

| Skill | Existing full prelude at | R4/R5 call site | Prelude precedes? | Line cost |
|---|---|---|---|---|
| `forge-5-loop` | L64 | L22–27 (R5) | **No** — below | inline needed; **budget against 2 spare** |
| `forge-4-backlog` | L154 | L32 (R5), L139 (R4) | **No** — below | inline ×2 (141 spare) |
| `forge-2-tech` | L203 | L189 (R4) | **No** — below | inline (91 spare) |
| `forge-3-specs` | L155 | L141 (R4) | **No** — below | inline (138 spare) |
| `forge-verify` | L260 | L220 (R4) | **No** — below | inline (43 spare) |
| `forge-1-prd` | L31, L142 | L127 (R4) | Yes | reuse — 0 |
| `forge-6-docs` | L47 | L173 (R4) | Yes | reuse — 0 |

`forge-5-loop` is the binding case: it takes R4 **and** R5 **and** R6 against 2 spare
lines. If the R5 consumer swap cannot be made net ≤0 there, defer that one edit behind an
explicit line audit rather than forcing it (REQ-DELIV-01 makes R5 independently
shippable, so deferring one consumer does not block the unit).

## 3. Citation graph & portability (REQ-PORT-01)

Every new/moved reference file must be cited by path from ≥1 **skill body** so
`build-adapters.py` fan-out ships it (00-core-definitions §9).

### 3.1 Required citations (the load-bearing preconditions)

| New/moved file | Cited from (skill body) | Load gate |
|---|---|---|
| `verification-checklists/prd.md` … `epic.md` (×6) | `skills/forge-verify/SKILL.md` (Step 2 mode dispatch + Step 3) — each of the six cited as a **separate literal path**, never as a `{mode}` template or `{prd,tech,…}` brace list (see §3.1.1) | leaf reads only its `{mode}.md` |
| `findings-template.md` | `skills/forge-verify/SKILL.md` (Steps 4/6) | orchestrator-only |
| `agent-selection.md` | `skills/forge-5-loop/SKILL.md` L174 and L180 — both **inside** the capability gate that opens at L172 | only when `loopRunner.agentArgument` set; L165 (above the gate) cites `runner-contract.md` only |
| `process-overview.md` (unchanged file, moved read-site) | `skills/forge/SKILL.md` (conditional branch) | only on "how does the pipeline work" |

#### 3.1.1 Citation form is load-bearing

Fan-out's regex is `references/([A-Za-z0-9_][A-Za-z0-9_./{}*-]*)`
(`scripts/build-adapters.py` L1667–1669). The character class has **no comma**, so a
brace enumeration like `` `references/verification-checklists/{prd,tech,specs}.md` ``
captures the single bogus token `verification-checklists/{prd` and yields **zero** real
paths. Never use it as a citation form. Cite each of the six mode files as its own
literal `references/verification-checklists/<mode>.md`.

**Fan-out scans skill bodies only.** `_fan_out_shared_references()` takes a
`SkillRecord` and reads `skill.body`; its sole call site is the per-skill loop at
L1402, and the agent emitters (L946/L1067/L1122) never call it. A citation in
`agents/*.md` therefore ships nothing — it is a human-readable pointer only. Citing
from a skill body is **required**, not belt-and-suspenders (OQ-4, resolved).

The six mode files and `findings-template.md` are **skill-local own-refs**
(`skills/forge-verify/references/...`) so they copy verbatim under the per-skill
own-refs step; `agent-selection.md` is likewise a loop-skill own-ref. Citing
them from the body is what gives fan-out a discoverable path (00-core-definitions §9).

### 3.2 Adapter build — no code change (tech-spec §6.9)

`build-adapters.py` needs **no change**: its citation fan-out + own-refs copy +
`RUNTIME_HELPERS` (which already includes `forge-session.py`) carry the new
subcommands and files automatically — *provided* every new reference file is
cited by path from a skill body (§3.1). `check-spec-purity.py` also needs no
change; it is a **constraint** (Rule 4's line *and* word caps; Rule 5 prelude
byte-identity, which every new call site satisfies by using the full prelude verbatim).

## 4. Revert boundaries (REQ-DELIV-01, SC-6)

Each unit lands as its **own PR/change**, revertible without touching the
others. The boundaries are file-disjoint except where noted:

| Unit | Owns (revert = touch only these) | Shared-file caveat |
|------|----------------------------------|--------------------|
| R1 | `forge-verify/SKILL.md`, `verification-checklists/*`, `findings-template.md`, `agents/forge-verifier.md`, R1 test, **the three existing tests that pin the pre-split file** (`test_lifecycle_artifact_check.py`, `test_smoke_command.py`, `test_dev_runtime_smoke.py` — see `06` §3.1.1) | shares `skills/forge-verify/SKILL.md` with R4 (R1 edits citations at Steps 2/3/4/6; R4 edits the production-stage state-write step — line-disjoint) |
| R3 | `forge/SKILL.md` read-site branch, R3 test | shares `forge/SKILL.md` with R4 (read-site branch vs the `state-note` call at L185 — line-disjoint) |
| R4 | `forge-session.py` (verbs), `shared-conventions.md`, state-write steps in **9** skill bodies, R4 test | shares `forge-session.py` with R5 (additive, disjoint functions); ships **after** R5; shares `forge-5-loop/SKILL.md` with R5+R6 and `forge-verify/SKILL.md` with R1 — all line-disjoint, but re-verify the cap after each lands |
| R5 | `forge-session.py` (effective-config), consumer lines in `forge-5-loop`/`forge-4-backlog`, R5 test | shares `forge-session.py` with R4 (additive); ships **before** R4 |
| R6 | `forge-5-loop/SKILL.md` citation swap, `runner-contract.md`, `agent-selection.md`, R6 test | shares `forge-5-loop/SKILL.md` with R5 **and** R4 (all 1:1 swaps; the combined net line **and word** effect must be re-verified against Rule 4 after each lands — only 2 lines spare) |

Because R4 and R5 both add functions to `forge-session.py`, a revert of one must
not delete the other's functions — they are additive and independently named, so
`git revert` of one PR leaves the other's subcommands intact.

## 5. Delivery sequencing (tech-spec §3.7)

The audit's sequence, refined in the interview:

```
R1  ┐
R3  ┘─  Quick wins (pure relocation, low risk, file-disjoint)
        │
R5  ─────  Lower-risk script add; establishes the "new forge-session subcommand
        │  + stdlib schema drift-guard" pattern
        │
R4  ─────  Largest surface (7 verbs + cascade + ~13 touch-point conversions +
        │  shared-conventions edits); reuses the R5 pattern at scale
        │
R6  ─────  Runner-contract split (cap-bound 1:1 swap)
```

R5 precedes R4 deliberately: it is smaller and exercises the schema-drift-guard
pattern R4 then reuses. R1 and R3 can land in any order among themselves (fully
disjoint). **No release items** appear in this feature's backlog (C-7); batching
is handled outside the pipeline.

## 6. Test surface (REQ-MAINT-01, SC-4)

Stdlib-only pytest under `tests/`, extending the `test_stage_exit_protocol.py`
discipline (`REPO_ROOT`-relative paths; assert against `skills/` canon, never
`adapters/`). One drift guard per unit plus the catch-all; full assertions in
`06-testing-strategy.md`. Portability: all **six** adapter targets (`claude`, `codex`,
`copilot`, `cursor`, `gemini`, `pi`) regenerate, and the `test_build_adapters.py`
snapshot passes after the gemini-fixture minimal-canon scratch-build + `command cp -f`
refresh;
`test_config_defaults_parity.py`, `test_pipeline_state_schema.py`,
`test_stage_exit_protocol.py` stay green.

## Dependencies

- `00-core-definitions.md` (script conventions, state shapes, portability
  contract).

## Verification

- [ ] Every file in §1's manifest exists (N), is removed (D), or is the only
      diff surface for its unit (M) after that unit's PR.
- [ ] Each new reference file in §3.1 appears as a literal `references/...`
      citation in the named skill body (`grep` check).
- [ ] `forge-5-loop/SKILL.md` body is ≤300 **lines** and ≤5,000 **words** after R4,
      R5 and R6 (measure the region check-spec-purity Rule 4 measures — strip
      frontmatter; a raw `wc -l` overcounts).
- [ ] `forge-0-epic/SKILL.md` body is ≤300 lines after R4 (8 lines spare).
- [ ] No spec anywhere still quotes `300/300` for `forge-5-loop`, or `298/300` for
      `forge-0-epic`.
- [ ] `git revert` of the R5 PR leaves R4's verbs compiling, and vice versa
      (additive-function boundary).
- [ ] The delivery order in §5 matches the backlog's dependency edges
      (`04-*` / backlog stage).
