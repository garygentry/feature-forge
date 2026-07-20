# 01 — Architecture & Layout

> Where the changes live. Because `context-efficiency` adds **no new package**
> (tech-spec §2), this document is not a directory-tree-for-a-new-module — it is
> (a) the exhaustive **file-move manifest** grouped by revert unit, (b) the
> `forge-session.py` module layout showing where the R4/R5 handlers slot in,
> (c) the **citation graph** that makes every moved file ship to all five
> adapters, and (d) the **delivery sequencing and revert boundaries** that make
> R1–R6 independently shippable (REQ-DELIV-01).
>
> Builds on `00-core-definitions.md` (script conventions §3, state shapes §4,
> portability contract §9). Does not restate them.

## Requirement Coverage

| REQ ID | Requirement | Section |
|--------|-------------|---------|
| REQ-DELIV-01 | Each of R1–R6 independently shippable + revertible | §4 (revert boundaries), §5 (sequencing) |
| REQ-PORT-01 | Every new/moved file cited by ≥1 skill body | §3 (citation graph) |
| REQ-PORT-03 | All five adapters regenerate; fixtures refreshed | §3.2 (adapter build), §6 |
| REQ-R2-03..? / REQ-R6-03 | No text pushed back into capped skill bodies | §2.2 (cap ledger) |
| REQ-R4-04 | All state-write sites covered | §1 (touched-files table, R4 rows) |
| REQ-MAINT-01 | Drift-guard coverage per split/moved file | §6 (test surface) |

---

## 1. File-move manifest

No new package. All changes are confined to the canonical surfaces the adapter
build fans out from (`skills/`, `references/`, `scripts/`, `tests/`). Files
grouped by unit; **D**=deleted, **N**=new, **M**=modified.

```
scripts/
  forge-session.py                 M  R4: +7 state verbs, +_write_state, +_now_iso reuse
                                       R5: +effective-config subcommand
                                          (1,866 lines today; argparse + if-dispatch)
references/
  pipeline-state-schema.json       .  R4: UNCHANGED content; remains CI source of truth
  forge-config-schema.json         .  R5: UNCHANGED content; read at runtime for defaults
  process-overview.md              .  R3: read-site relocated (file itself unchanged)
  shared-conventions.md            M  R4: Stage-Entry Guard / Branch Setup / completion
                                          steps switch to state-verb calls (PROSE UNCHANGED)
skills/forge/SKILL.md              M  R2 (5 preludes → 1 full + 4 compact) + R3 (gate read)
skills/forge-0-epic/SKILL.md       M  R2 (5 → 1 + 4); R4 (state verbs)
skills/forge-bootstrap/SKILL.md    M  R2 (4 → 1 + 3)
skills/forge-1-prd/SKILL.md        M  R2 (2 → 1 + 1); R4 (state verbs)
skills/forge-2-tech/SKILL.md       M  R4 (state verbs)
skills/forge-3-specs/SKILL.md      M  R4 (state verbs)
skills/forge-4-backlog/SKILL.md    M  R4 (state verbs); R5 (effective-config consumer)
skills/forge-verify/
  SKILL.md                         M  R1: cite the 6 mode files + findings-template.md;
                                          reconcile Step-3 expected-count table
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
  SKILL.md                         M  R6: 1:1 citation swap (line-neutral, at 300/300 cap)
                                       R5: effective-config consumer
  references/
    runner-contract.md             M  R6: keeps the 6 always-loaded sections
    agent-selection.md             N  R6: NEW — 3 agent-conditional sections
tests/
  test_verification_checklists_split.py  N  R1 drift guard (§6)
  test_state_verbs.py                    N  R4 drift guard (§6)
  test_effective_config.py               N  R5 drift guard (§6)
  test_prelude_dedup.py                  N  R2 drift guard (§6)
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
(`03-state-verbs.md §5`, `04-effective-config.md §4`).

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
├── _now_iso()                       ~  reuse/confirm the existing UTC-ISO helper
├── cmd_state_enter(...)             N  ┐
├── cmd_state_artifact(...)          N  │ R4 handlers — one per verb; each does
├── cmd_state_complete(...)          N  │ resolve→load→mutate→refresh updatedAt→write
├── cmd_state_note(...)              N  │ (may be inlined in the dispatch chain to
├── cmd_state_decision(...)          N  │  match the script's existing style — see
├── cmd_state_ecr(...)               N  │  03-state-verbs.md §3)
├── cmd_state_branch(...)            N  ┘
├── cmd_effective_config(...)        N  R5 handler — schema defaults + deep-merge
├── _print_state(payload) / per-verb N  human-readable printers
└── main()                           M  register 8 subparsers; add 8 dispatch branches
```

The `import os` and `import json` needed by `_write_state` are already present
(the script already uses both). No new stdlib imports beyond what exists.

### 2.2 Skill-body line-cap ledger (C-2, hard constraint)

`check-spec-purity.py` Rule 4 caps skill bodies at **300 lines**. R2 and R6 must
respect current headroom (verified figures from tech-spec):

| Skill | Current lines | Unit(s) touching it | Net line effect |
|-------|--------------|---------------------|-----------------|
| `forge-5-loop/SKILL.md` | **300 / 300** (at cap) | R6, R5 | **0** — R6 is a strict 1:1 citation swap; R5 swaps one read for one call |
| `forge-0-epic/SKILL.md` | 292 / 300 | R2, R4 | **−4** (R2 frees ~4 lines) then R4 swaps in-place |
| `forge-bootstrap/SKILL.md` | (near cap) | R2 | negative (R2 frees lines) |
| `forge-verify/SKILL.md` | 257 / 300 | R1 | small; must NOT inline orchestrator material (that would be +~150, over cap) |
| `forge/SKILL.md` | (headroom) | R2, R3 | negative/neutral |

**Consequence:** R1's orchestrator material goes to `findings-template.md` (not
inlined); R6's `runner-contract.md` text is NOT pushed back into the loop body;
R2's compact form is a net reduction. No edit may push a body over 300.

## 3. Citation graph & portability (REQ-PORT-01)

Every new/moved reference file must be cited by path from ≥1 **skill body** so
`build-adapters.py` fan-out ships it (00-core-definitions §9).

### 3.1 Required citations (the load-bearing preconditions)

| New/moved file | Cited from (skill body) | Load gate |
|---|---|---|
| `verification-checklists/prd.md` … `epic.md` (×6) | `skills/forge-verify/SKILL.md` (Step 2 mode dispatch + Step 3) | leaf reads only its `{mode}.md` |
| `findings-template.md` | `skills/forge-verify/SKILL.md` (Steps 4/6) | orchestrator-only |
| `agent-selection.md` | `skills/forge-5-loop/SKILL.md` (~L174 capability gate) | only when `loopRunner.agentArgument` set |
| `process-overview.md` (unchanged file, moved read-site) | `skills/forge/SKILL.md` (conditional branch) | only on "how does the pipeline work" |

The six mode files and `findings-template.md` are **skill-local own-refs**
(`skills/forge-verify/references/...`) so they copy verbatim under the per-skill
own-refs step; `agent-selection.md` is likewise a loop-skill own-ref. Citing
them from the body additionally gives fan-out a discoverable path (belt and
suspenders, per the OQ-4 mitigation in 00-core-definitions §9).

### 3.2 Adapter build — no code change (tech-spec §6.9)

`build-adapters.py` needs **no change**: its citation fan-out + own-refs copy +
`RUNTIME_HELPERS` (which already includes `forge-session.py`) carry the new
subcommands and files automatically — *provided* every new reference file is
cited by path from a skill body (§3.1). `check-spec-purity.py` also needs no
change; it is a **constraint** (Rule 4 line cap, Rule 5 prelude byte-identity).

## 4. Revert boundaries (REQ-DELIV-01, SC-6)

Each unit lands as its **own PR/change**, revertible without touching the
others. The boundaries are file-disjoint except where noted:

| Unit | Owns (revert = touch only these) | Shared-file caveat |
|------|----------------------------------|--------------------|
| R1 | `forge-verify/SKILL.md`, `verification-checklists/*`, `findings-template.md`, `agents/forge-verifier.md`, R1 test | none — disjoint |
| R2 | prelude lines in `forge`, `forge-0-epic`, `forge-bootstrap`, `forge-1-prd` skill bodies, R2 test | shares `forge-0-epic`/`forge-1-prd`/`forge` bodies with R3/R4 — but edits are line-disjoint (prelude blocks vs state-write steps vs read-site) |
| R3 | `forge/SKILL.md` read-site branch, R3 test | shares `forge/SKILL.md` with R2 (disjoint lines) |
| R4 | `forge-session.py` (verbs), `shared-conventions.md`, state-write steps in 6 skill bodies, R4 test | shares `forge-session.py` with R5 (additive, disjoint functions); ships **after** R5 |
| R5 | `forge-session.py` (effective-config), consumer lines in `forge-5-loop`/`forge-4-backlog`, R5 test | shares `forge-session.py` with R4 (additive); ships **before** R4 |
| R6 | `forge-5-loop/SKILL.md` citation swap, `runner-contract.md`, `agent-selection.md`, R6 test | none — disjoint |

Because R4 and R5 both add functions to `forge-session.py`, a revert of one must
not delete the other's functions — they are additive and independently named, so
`git revert` of one PR leaves the other's subcommands intact.

## 5. Delivery sequencing (tech-spec §3.7)

The audit's sequence, refined in the interview:

```
R1  ┐
R2  ├─  Quick wins (pure relocation/dedup, low risk, file-disjoint)
R3  ┘
        │
R5  ─────  Lower-risk script add; establishes the "new forge-session subcommand
        │  + stdlib schema drift-guard" pattern
        │
R4  ─────  Largest surface (7 verbs + cascade + ~9 touch-point conversions +
        │  shared-conventions edits); reuses the R5 pattern at scale
        │
R6  ─────  Runner-contract split (cap-bound 1:1 swap)
```

R5 precedes R4 deliberately: it is smaller and exercises the schema-drift-guard
pattern R4 then reuses. R1/R2/R3 can land in any order among themselves (fully
disjoint). **No release items** appear in this feature's backlog (C-7); batching
is handled outside the pipeline.

## 6. Test surface (REQ-MAINT-01, SC-4)

Stdlib-only pytest under `tests/`, extending the `test_stage_exit_protocol.py`
discipline (`REPO_ROOT`-relative paths; assert against `skills/` canon, never
`adapters/`). One drift guard per unit plus the catch-all; full assertions in
`06-testing-strategy.md`. Portability: `test_build_adapters.py` snapshot passes
after the gemini-fixture minimal-canon scratch-build + `command cp -f` refresh;
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
- [ ] `forge-5-loop/SKILL.md` is ≤300 lines after R5 and R6 (`wc -l` on the
      body region check-spec-purity measures).
- [ ] `git revert` of the R5 PR leaves R4's verbs compiling, and vice versa
      (additive-function boundary).
- [ ] The delivery order in §5 matches the backlog's dependency edges
      (`04-*` / backlog stage).
