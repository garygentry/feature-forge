# 01 — Architecture & Layout

> **WHERE every change lands, and in WHAT ORDER.** `loop-recovery` adds no new
> packages. All forge-side code lands in existing canonical surfaces and fans out to
> `adapters/` via `scripts/build-adapters.py`; exactly one surface lands in the
> separate `rauf` repo. This document owns the full file manifest, the
> `forge-session.py` module layout, the rauf split, the delivery sequencing, and the
> body-cap budget. Type/enum/constant contracts are in `00-core-definitions.md`;
> per-surface detail is in `02`–`07`.

## Requirement Coverage

| REQ ID | Requirement | Section |
|--------|-------------|---------|
| REQ-STATE-01 | Every persistent surface = schema + verb + conformance test | §1 (manifest rows), §2 |
| REQ-COMPAT-01 | Vocabulary/routing change ripples into the directive matrix deliberately | §1 (stage-exit-protocol row + tests), §4 |
| REQ-COMPAT-02 | Clean-tree happy path unchanged but for the Step 2a depth line | §4 (sequencing), §5 (body budget) |
| REQ-DEC-04 | "stage a post-run retry" replaced by a named procedure | §1 (runner-contract/ralph rows) |
| REQ-TOPO-01..03 | Topology reported at three consumers | §1 (forge-4/forge-verify/forge-5 rows) |
| REQ-EVAL-01 | New outcome measured by a compliance probe | §1 (eval rows) |
| all "Constraints" (PRD §5) | Body caps, canon/adapter discipline, ruff, parity | §5 (budget), §6 (build discipline) |

---

## 1. File Manifest

Legend: **NEW** = new file; **EDIT** = modified; **REGEN** = regenerated, never
hand-edited. Every canon edit under the roots that `build-adapters.py` fans out
**requires** an adapter regen in the same change (§6).

### 1.1 Canon — code & schema

| File | Kind | What changes | Owning doc |
|------|------|--------------|-----------|
| `references/forge-decisions-schema.json` | **NEW** | The decision-record schema (`00` §4.1) | `02` |
| `scripts/forge-session.py` | **EDIT** | `decision-record`/`decision-list`/`decision-apply` verbs; `backlog-topology` verb; `compute_topology()`; `cluster_blocked()` helper; `LoopOutcome += "resolved"`; `_LOOP_ROUTE_KIND`/`_LOOP_OUTCOME_TEXT` rows; `stage-exit --cause`; the four new `Final` constants (`00` §6) | `02`,`03`,`06` |
| `tests/_state_schema.py` | **EDIT** | `_DECISIONS_SCHEMA` load + `validate_decisions()` wrapper (~12 lines) mirroring `_STATE_SCHEMA`/`_CONFIG_SCHEMA` (lines 26–31); docstring "Both entry points"→three | `02`,`07` |

### 1.2 Canon — skill bodies & references

| File | Kind | What changes | Owning doc |
|------|------|--------------|-----------|
| `skills/forge-5-loop/SKILL.md` | **EDIT** | Step 7 ladder edit at `:271` (`+= resolved`); **new** `### 1g. Stranded-Work Pre-flight` (~5 body lines, §5 budget); pointer line to the recovery procedure | `03`,`05` |
| `skills/forge-5-loop/references/recovery-procedure.md` | **NEW** | The named **Post-Run Recovery Procedure** + tree reconciliation + the REQ-OBS citation table | `05` |
| `skills/forge-5-loop/references/result-reporting.md` | **EDIT** | Ladder rung defs `+= resolved`; starvation-conditional pending template; starved next-steps note | `03` |
| `skills/forge-5-loop/references/runner-contract.md` | **EDIT** | `:183` "stage a post-run retry" → named pointer to `recovery-procedure.md` (REQ-DEC-04) | `05` |
| `references/ralph-loop-contract.md` | **EDIT** | `:61` "follow-up retry pass" → same named pointer | `05` |
| `references/stage-exit-protocol.md` | **EDIT** | `:50` loop outcome-domain row `+= resolved` (REQ-COMPAT-01 directive matrix) | `03` |
| `skills/forge-4-backlog/SKILL.md` | **EDIT** | Topology-report step in the Step 5/6 slot (REQ-TOPO-01) | `06` |
| `skills/forge-verify/references/verification-checklists/backlog.md` | **EDIT** | **NEW CHECK-B28** (advisory topology check, REQ-TOPO-02) | `06` |
| `skills/forge-verify/SKILL.md` | **EDIT** | **Both** count literals → 28: `:33` "backlog 27" (dimension groups) and `:171` "backlog: 27 checks" (in-line, zero line growth) | `06` |

### 1.3 Canon — docs & eval

| File | Kind | What changes | Owning doc |
|------|------|--------------|-----------|
| `docs/architecture/stage-exit-coverage/cli-reference.md` | **EDIT** | Outcome table `+= resolved` | `03` |
| `docs/architecture/stage-exit-coverage/architecture.md` | **EDIT** | resume/recover split prose covers `resolved` | `03` |
| `eval/run-compliance-eval.py` | **EDIT** | **NEW** `loop-outcome` probe; joins `--probe all`; docstring/usage/argparse three→four | `07` |
| `eval/fixtures/compliance/loop-outcome-resolved.json` | **NEW** | The resolved-route fixture (own required-key set) | `07` |

### 1.4 Tests

| File | Kind | What changes | Owning doc |
|------|------|--------------|-----------|
| `tests/test_forge_decisions_schema.py` | **NEW** | Structural schema assertions | `07` |
| `tests/test_decisions_schema_conformance.py` | **NEW** | R4 drift guard for `decision-*` (clone of `test_state_schema_conformance.py`) | `07` |
| `tests/test_backlog_topology.py` | **NEW** | `compute_topology` metrics + warn thresholds + observed-incident fixture | `07` |
| `tests/test_decision_clustering.py` | **NEW** | Jaccard normalization/boundary/union-find/determinism + vendored one-cause-three-phrasings fixture (V-015) | `07` |
| `tests/test_stage_exit.py` | **EDIT** | Mirrored `EXIT_OUTCOMES["forge-5-loop"] += resolved`; resume-routing case; `--cause` validity matrix (REQ-COMPAT-01) | `03`,`07` |
| `tests/test_stage_exit_protocol.py` | **no code change** | Its canon-derived outcome-domain assertion (`:379-388`) is what **forces** the `SKILL.md:271` ladder edit | `03` |
| `tests/test_lifecycle_artifact_check.py` | **EDIT** | "backlog 27"/"backlog: 27 checks" literals (`:49-52`) → 28 | `06`,`07` |
| `tests/test_compliance_eval.py` | **EDIT** | `--probe all` exact-equality list (`:1953-1954`) `+= run_loop_outcome_probe` | `07` |

### 1.5 rauf repo (separate release train)

| File | Kind | What changes | Owning doc |
|------|------|--------------|-----------|
| `packages/cli/src/backlog-commands.ts` | **EDIT** | **NEW** subcommand `rauf backlog answer <path> <id> "<text>" [--backlog <dir>] [--json]` | `04` |
| `packages/cli` (tests) | **EDIT** | `backlog answer` unit tests (happy path, not-blocked refusal, JSON shape) | `04`,`07` |

### 1.6 Regenerated (never hand-edited)

| Path | Kind |
|------|------|
| `adapters/**` | **REGEN** — `python3 scripts/build-adapters.py` after every canon edit under a fanned-out root |

## 2. `forge-session.py` module layout (where new code sits)

`forge-session.py` is one flat script organized in labeled sections. New code follows the
existing placement conventions — no reorganization:

- **Constants** (top, with the other `Final` module constants): the four new constants
  (`00` §6) next to `LoopOutcome`/`EXIT_OUTCOMES` and the topology neighbors.
- **Route/text tables** (`~:2952`): the `resolved` rows added to `_LOOP_ROUTE_KIND` /
  `_LOOP_OUTCOME_TEXT` in place; `_loop_route()` (`:3117`) needs **no** structural change —
  it already dispatches by `_LOOP_ROUTE_KIND[outcome]`, so a `resume`-kinded `resolved`
  flows through the existing non-handoff branch.
- **Pure helpers** (with `rank-features`/`reconcile-branch` flat-function precedent):
  `compute_topology(items)` and `cluster_blocked(items)` — no class, stdlib only.
- **State-write helpers** (`~:4083-4432`): the `decision-*` verbs reuse the
  **target-agnostic** `_commit_state`/`_write_state` (`00` §10) with the decisions path;
  they do **not** touch `_load_state_for_write` (feature-state-only).
- **Verb functions**: `cmd_decision_record` / `cmd_decision_list` / `cmd_decision_apply` /
  `cmd_backlog_topology`, each returning a dict, following the `cmd_state_note` shape
  (`forge-session.py:4740`).
- **argparse registration + dispatch tail** (`~:5746`, `~:5960`): one `sub.add_parser(...)`
  per verb and one `if args.cmd == "...": _emit(...)` block each, mirroring the existing
  `state-*` registrations exactly.

## 3. rauf split — the one cross-repo surface

Only `rauf backlog answer` lives in rauf (`04`). It is the apply-only twin of
`resume --answer`'s injection block, with **no relaunch**. It ships in the next rauf minor
(assumed **0.14.0**, OTQ-2). The forge side never hard-depends on it:
`RECOVERY_MIN_RUNNER_VERSION` capability-gates it and degrades to `rauf backlog unblock`
below the threshold (`04`). `loopRunner.minRunnerVersion` stays `0.6.0`; the rauf PR can
land **in parallel** with the forge-side DEC/TREE work.

## 4. Delivery sequencing (PRD §3 dependency order)

Implement in the order the PRD/issue edges fix — **DEC → TREE → UNB → OUT → ATTR → CLU →
TOPO → EVAL** — because REQ-DEC is the keystone (#196 → #193 → #189; #192 → #189; #194
feeds #190/#191):

1. **DEC** (`02`) — schema + `decision-*` verbs + conformance. Foundation for everything.
2. **TREE** (`05` §3.5) — tree reconciliation section + the `1g` body pre-flight.
3. **UNB** (`04`) — apply mechanism; needs rauf 0.14.0 available locally for e2e (unit
   tests stub the CLI). The rauf PR lands in parallel with DEC/TREE.
4. **OUT** (`03`) — `resolved` enum + routing/text + ladder; the directive-matrix ripple
   (`test_stage_exit_protocol.py`) forces the `SKILL.md:271` body edit.
5. **ATTR** (`03`) — `selectable` + starvation cause + conditional "(iteration limit)".
6. **CLU** (`06`) — clustering helper + `--cluster` output; the recovery procedure's
   consolidated prompts consume it.
7. **TOPO** (`06`) — `compute_topology` + the three consumers + CHECK-B28.
8. **EVAL** (`07`) — the `loop-outcome` probe + fixture; the new outcome must not ship
   unmeasured (REQ-EVAL-01, the #176 lesson).

Cross-cutting: **canon→adapter regen** runs after *every* canon edit; the full
`bash scripts/validate.sh` gate is the merge bar at each step.

## 5. Body-cap budget (PRD §5 — hard CI gate)

`check-spec-purity.py` rule 4 caps skill **bodies** at 300 lines / 5000 words. Current
measures and this feature's budget:

| Skill body | Now (rule-4 measure) | Change | Result |
|------------|----------------------|--------|--------|
| `skills/forge-5-loop/SKILL.md` | 287/300 | Step 7 ladder edit (in-line, ~0 net) + new `### 1g` (~5 lines) + 1 pointer line | ≈293/300 — within cap |
| `skills/forge-verify/SKILL.md` | 298/300 | Both count literals `27`→`28` **in-line, zero line growth** | 298/300 — unchanged |
| `skills/forge-4-backlog/SKILL.md` | ~ (has ~100-line headroom) | Topology-report step in Step 5/6 slot | within cap |

**All other new prose lands in `references/`** (recovery-procedure, result-reporting,
runner-contract, backlog checklist) with one-line pointers from bodies. The topology
CHECK **must not** land in the forge-verify body — it lives in
`verification-checklists/backlog.md` as CHECK-B28. (PRD §5's "299/300" for forge-verify is
the same file by `wc -l`-style counting; 298 is the rule-4 measure — both mean "essentially
at the cap", so zero-line-growth in-line edits only.)

## 6. Build & parity discipline (PRD §5, tech-spec §6)

- **canon→adapter regen (MUST):** every touched canon file triggers
  `python3 scripts/build-adapters.py`; `validate.sh` step 6b fails on adapter drift.
  Regen is deterministic (fixed `AGENT_TARGETS` order) — commit the regenerated
  `adapters/**` in the same change, never hand-edit them.
- **ruff (MUST):** every `scripts/*.py` and `eval/*.py` edit passes
  `ruff check scripts/ eval/` (validate.sh step 7b + CI Quality Gate; the local step is
  skippable but CI is not).
- **stage/status parity:** the new decision vocabulary stays **local to
  `forge-session.py`** — no `epic-manifest.py` duplicate — so
  `test_stage_constants_parity.py` needs **no** change unless review finds otherwise.
- **spec purity + traceability:** `validate.sh` runs `check-spec-purity.py` (body caps,
  §5) and the traceability check; both are merge bars.

## Dependencies

- `00-core-definitions.md` — the schema, enum, constants, and shapes this manifest places.

## Verification

- [ ] Every **NEW**/**EDIT** row in §1 is realized; `git status` after the change shows
      exactly this set plus regenerated `adapters/**` — no stray edits.
- [ ] `bash scripts/validate.sh` is green: spec purity (bodies within §5 caps), adapter
      **non**-drift, pytest, ruff, traceability.
- [ ] `python3 scripts/forge-session.py doctor --json` (smoke) exits 0.
- [ ] The two forge-verify count literals and their `test_lifecycle_artifact_check.py`
      assertions all read `28` (no split-brain `27`/`28`).
- [ ] The rauf `backlog answer` PR is a self-contained rauf-repo change; the forge side
      builds and passes with **or** without it present (degraded path, `04`).
