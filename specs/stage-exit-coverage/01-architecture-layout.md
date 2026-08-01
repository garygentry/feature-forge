# 01 — Architecture & Layout

> Exhaustive implementation map for expanding deterministic stage exits without adding a
> package, service, dependency, or network path. Shared types and signatures are defined
> in `00-core-definitions.md`; this document pins file ownership, imports, runtime copies,
> integration paths, and delivery ordering.

## Requirement Coverage

| REQ ID | Requirement | Section |
|---|---|---|
| REQ-EXIT-01..07 | Unified scripted exit surface and host/capability split | §2–§4 |
| REQ-ROUTE-01..06 | Branch-skill inputs and deterministic rejoin ownership | §3–§4 |
| REQ-PROD-01..06 | Loop/docs/epic skill integration | §3 |
| REQ-DEBT-01..06 | State/schema/session/manifest integration | §2–§4 |
| REQ-STATE-01..04 | Targeted atomic writers and two-commit provenance | §2, §5 |
| REQ-CONFIG-01..04 | Shared duplicate parser and all config consumers | §2–§4 |
| REQ-GUARD-01..03 | Explicit nine-skill guard | §2, §6 |
| REQ-EVAL-01..03 | Separate branch-path compliance fixture | §2, §6 |
| REQ-CAP-01, REQ-FOLLOW-01/02 | Preserved loop prerequisite and focused canon edits | §3, §5 |
| REQ-COMPAT-01..03 | Existing stage behavior, state/config compatibility, null smoke | §4–§6 |
| REQ-PERF-01/02 | Local bounded reads only | §4 |
| PRD §5 constraints | Adapter shipping, path containment, deterministic layering | §4–§6 |

## 1. Architectural Boundaries

This feature extends the repository's existing **flat script control plane**. The public
runtime entry remains:

```text
python3 <bundle-root>/scripts/forge-session.py <subcommand> ...
```

No Python package manifest, `src/` package, database, service, or third-party runtime
library is introduced — **and no new module**. The flat scripts stay self-contained: each is
copied verbatim into six per-agent adapter bundles, so the repository's standing invariant is
that they share no import module (`tests/test_stage_constants_parity.py`). The duplicate-aware
JSON loader is therefore *mirrored* into its two consumers rather than extracted, following the
same precedent as `PRODUCTION_STAGES` and `AGENT_TARGETS` (§3.4). Exit routing
stays in `forge-session.py` so it can reuse existing feature resolution, state readers,
production-stage ordering, host translation, and argparse error handling without a new
cross-script protocol.

Canonical prose and schemas remain under `skills/`, `agents/`, and `references/`.
Generated files under `adapters/` are outputs only and are regenerated, never edited.

## 2. Complete File Layout

`N` = new, `M` = modified, `G` = regenerated output.

```text
scripts/
  forge-session.py                         M  exit router, state-verify, debt, hashes,
                                              duplicate-aware config consumer
  epic-manifest.py                         M  verify vocabulary, manifest revision,
                                              pending/read-side parity
  forge-bootstrap.py                       M  shared duplicate-aware config consumer
  check-spec-purity.py                     M  rule-7 shipped-file corpus and the
                                              CITATION_GRANDFATHERED ceilings
  build-adapters.py                        —  unchanged; listed for orientation only

references/
  stage-exit-protocol.md                   M  sole nine-skill terminal contract
  pipeline-state-schema.json               M  auto-verify-pending + schedule metadata
  epic-manifest-schema.json                M  required revision >= 1
  shared-conventions.md                    M  register state-verify; immediate state-note recipe
  forge-config-schema.json                 M  autoVerify / autoVerifyStages / autoFix keys

skills/
  forge/SKILL.md                           M  auto-pending row rendering + nested-owner dispatch
  forge-0-epic/SKILL.md                    M  scripted creation/edit terminal
  forge-0-epic/references/edit-mode.md     M  live member-state handoff
  forge-1-prd/SKILL.md                     M  capability-aware stage exit + state-note
  forge-2-tech/SKILL.md                    M  capability-aware stage exit + state-note
  forge-3-specs/SKILL.md                   M  capability-aware stage exit
  forge-4-backlog/SKILL.md                 M  capability-aware stage exit
  forge-5-loop/SKILL.md                    M  scripted result terminus; preserve body cap;
                                               auto-verify-pending in the Step 1b gate
  forge-5-loop/references/result-reporting.md
                                            M  typed loop outcomes and terminal ownership
  forge-5-loop/references/runner-contract.md
                                            M  stale --model wording correction (sole source)
  forge-6-docs/SKILL.md                     M  scripted context-aware docs terminus;
                                               auto-verify-pending in the backstop gate
  forge-verify/SKILL.md                     M  direct/nested owner, state-verify, exit
  forge-verify/references/findings-template.md
                                            M  epic-state writes move to state-verify
  forge-fix/SKILL.md                        M  complete outcomes, state-verify, exit

eval/
  run-compliance-eval.py                    M  separate branch-path probe/scorer
  README.md                                 M  linear baseline vs branch result
  fixtures/compliance/verify-fix-reverify.json
                                            N  verify/fix/re-verify command evidence; nested
                                               below run-eval's non-recursive fixtures/*.json
                                               glob so it cannot load as a trigger fixture

tests/
  test_stage_exit.py                        M  nine-stage/outcome/host routing matrix
  test_stage_exit_protocol.py               M  explicit canonical coverage allow-list
  test_auto_verify.py                       M  auto-pending classification/debt
  test_state_verbs.py                       M  state-verify transitions + hashes
  test_state_schema_conformance.py          M  additive schema and legacy reads
  test_stage_constants_parity.py            M  verify vocabulary parity
  test_effective_config.py                  M  recursive duplicate warnings
  test_forge_bootstrap.py                   M  duplicate commitPrefix warning + exit-2 policy
  test_json_loader_parity.py                N  mirrored loader drift guard
  test_compliance_eval.py                   M  branch fixture/scorer validity
  test_build_adapters.py                    M  runtime helper and translated stamps
  test_doctor.py                            M  auto-pending label in doctor output
  test_rank_features.py                     M  auto-pending obligation in rank rows
  test_capability_determination_prose.py    N  the prose-only capability contract:
                                               clauses (a), (b) and (c1a/c1b/c2/c3) over a
                                               roster derived from the exit table
  test_gate_pytest_reachability.py          N  validate.sh's pytest step is reachable, so
                                               a soft skip cannot hide a red suite
  test_state_verb_call_sites.py             M  per-call-site --epic mandate window;
                                               scripted skip persistence
  test_check_spec_purity.py                 M  grandfather list shrink-only + drift warning
  <existing epic manifest tests>            M  revision mutation/freshness matrix

README.md                                   M  documents the autoVerify / autoFix keys

adapters/{claude,codex,copilot,cursor,gemini,pi}/
  scripts/forge-session.py                  G
  scripts/epic-manifest.py                  G
  ...canonical skills/references...         G
```

The canonical runner reference is the skill-local
`skills/forge-5-loop/references/runner-contract.md` — the sole source, and the only
runner-contract file in the repository outside generated `adapters/` output. Edit that file
in place; there is no root-level `references/runner-contract.md` to create or reconcile.

## 3. Module and Canon Ownership

### 3.1 `scripts/forge-session.py`

Keep the existing top-level order:

```text
imports
constants and TypedDicts
feature scan / next-stage / verify classifiers
config and navigator helpers
...
scripted stage exit constants + validation + routing + rendering
loopRunner effective config
...
strict state resolution + atomic state helpers
state-* handlers (including new cmd_state_verify)
argparse registration / dispatch
main guard
```

New code slots:

1. Extend `KNOWN_VERIFY_STATUSES`, `EXIT_STAGES`, stage nouns, mode maps, outcome maps,
   and result types beside current equivalents.
2. Add pure validation/routing helpers immediately before `stage_exit`; avoid one giant
   conditional.
3. Extend `_next_steps_block` in place; preserve `_host_command` as the sole runtime host
   translator.
4. Add `cmd_state_verify` beside other `cmd_state_*` handlers so it reuses strict writer
   machinery.
5. Register flags/subcommand with existing argparse conventions and dispatch under the
   existing `UsageError`/`OSError` exit-2 handler.

Exact existing integration signatures read from `scripts/forge-session.py`:

```python
def next_stage(state: dict) -> str | None: ...
def verify_state(state: dict) -> tuple[str | None, str]: ...
def pending_verify(state: dict) -> str | None: ...
def build_rows(specs_dir: Path, config: dict | None = None) -> list[FeatureRow]: ...
def _load_config(config_path: Path) -> dict: ...
def _resolve_feature_dir(specs_dir: Path, feature: str, epic: str | None) -> Path: ...
def _host_command(command: str, host: str) -> str: ...
def _verify_state_for(state: dict, stage: str) -> str: ...
def _resolve_feature_dir_for_write(
    specs_dir: Path, feature: str, epic: str | None
) -> Path: ...
def _load_state_for_write(
    specs_dir: Path, feature: str, epic: str | None
) -> tuple[Path, dict]: ...
def _commit_state(state_path: Path, state: dict) -> dict: ...
```

`stage_exit`, `_next_steps_block`, `cmd_state_complete`, and new `cmd_state_verify`
follow the complete signatures in `00-core-definitions.md`.

### 3.2 `scripts/epic-manifest.py`

This script remains self-contained; do not import `forge-session.py`. Keep its mirrored
constants byte-identical where parity tests require that. Exact existing import paths and
signatures:

```python
# File import/execution path: scripts/epic-manifest.py
KNOWN_VERIFY_STATUSES: Final[frozenset[str]]

def load_manifest(epic_dir: Path) -> dict: ...
def atomic_write(path: Path, data: dict) -> None: ...
def validate(epic_dir: Path, specs_dir: Path) -> list[Finding]: ...
def is_complete_for_orchestration(state: dict) -> bool: ...
def derive_status(feature_dir: Path) -> FeatureStatus: ...
def render_status(epic_dir: Path, specs_dir: Path) -> RenderStatus: ...
def _bump_and_write(
    epic_dir: Path, specs_dir: Path, manifest: dict
) -> list[Finding]: ...
```

Manifest creation writes `revision: 1`. `load_manifest` presents legacy missing revision
as logical revision 1 without requiring an eager migration. Every successful semantic
mutation increments once in `_bump_and_write`; failures and no-ops do not increment.
Do not duplicate revision increments in individual mutators.

### 3.3 Canonical skill layer

Every directly invoked pipeline-advancing skill calls `stage-exit` and prints script
output last. `references/stage-exit-protocol.md` is the single directive contract; skill
bodies contain only stage-specific preparation, typed arguments, gate handling, and the
final invocation.

Ownership rules:

- Authoring stages 0–6 are outer owners.
- Direct `forge-verify`/`forge-fix` pass `--owner direct` and own one terminal block.
- Auto/nested verify/fix pass `--owner nested`; the outer authoring stage remains owner.
- Result-reporting branches provide explicit outcomes rather than hand-written commands.

The loop prerequisite from commit `c174b55` is immutable: before editing
`skills/forge-5-loop/SKILL.md`, confirm Step 2d remains single-sourced in
`skills/forge-5-loop/references/runner-contract.md`. Preserve the ≤300 body-line and
≤5,000 body-word gates after every loop-skill edit.

### 3.4 Config parser ownership

The duplicate-aware loader is **mirrored, not extracted**. `scripts/forge-session.py` and
`scripts/forge-bootstrap.py` each carry their own copy of:

```python
def load_json_with_duplicates(path: Path) -> tuple[object, list[str]]: ...
def warn_duplicate_keys(path: Path, duplicate_keys: list[str]) -> None: ...
```

**Why duplication and not a shared module.** Every flat script is copied verbatim into the six
per-agent adapter bundles, so the repository's standing invariant — stated in
`tests/test_stage_constants_parity.py` — is that these scripts have *no shared import module*.
`epic-manifest.py` already mirrors `PRODUCTION_STAGES` and `KNOWN_VERIFY_STATUSES` from
`forge-session.py` for exactly this reason, and `tests/test_agent_targets_parity.py` exists
because `AGENT_TARGETS` drifted once and silently dropped `adapters/pi/` coverage. The remedy the
repository has twice chosen is a drift guard, not an import. A new `scripts/forge_json.py` would
be the first violation of that invariant, would add a seventh `RUNTIME_HELPERS` entry whose import
must resolve inside every bundle, and would freeze its signature across six shipped bundles — all
to avoid duplicating roughly 25 lines. The trade is not worth it (REQ-COMPAT-02, REQ-PERF-01).

Each copy carries a `#: mirrors ``load_json_with_duplicates`` in <other file>` comment, matching
the existing convention. `forge-session.py` uses its copy inside `_load_config`;
`forge-bootstrap.py` uses its copy at the config read it currently performs as a bare
`json.loads(path.read_text(...))`. Effective config, stage exit, navigator, init/validate, and
other callers inherit warnings from those read paths rather than implementing their own scan.

**Drift guard.** `tests/test_json_loader_parity.py` asserts the two copies stay identical. Unlike
the existing parity tests it cannot use `ast.literal_eval`, because the mirrored unit is a pair of
functions rather than a literal: it extracts each function's source block from both files and
compares them after a uniform `textwrap.dedent` and trailing-whitespace strip. **Exactly one
`#: mirrors …` comment precedes the pair in each file**; the comment is asserted separately and lies
outside the compared region, because the two comments differ by design (each names the other file).
A divergence fails the suite with both bodies in the diff. Like the modules it follows, it may not
grow a skip gate.

## 4. Integration Map and Data Flow

### 4.1 Authoring exit with automatic verification

```text
state-complete Commit 1/Commit 2
  -> outer skill invokes stage-exit(stage, capability)
  -> stage_exit loads duplicate-aware config + stage state
  -> effective auto verify is owed
  -> targeted state-verify writes auto-verify-pending atomically
  -> payload says runInStageVerify=true, debtRecorded=true
  -> outer skill dispatches nested forge-verify(owner=nested)
  -> verify writes terminal result through state-verify
  -> findings optionally dispatch nested forge-fix(owner=nested)
  -> fix writes findings-applied (freshness cleared)
  -> outer requires nested re-verify
  -> only passed/skip permits production successor as primary
  -> outer prints exactly one sentinel-last block
```

The pending write occurs immediately before returning `runInStageVerify: true`. A process
failure after that write leaves durable debt. The clean-tree snapshot used for
`autoFixEligible` is taken before this sanctioned state mutation.

### 4.2 Direct branch rejoin

```text
forge-verify or forge-fix
  -> determine explicit verify mode / findings metadata
  -> serialize served production stage
  -> write result via state-verify
  -> invoke stage-exit(owner=direct, outcome=...)
  -> route to fix, re-verify, recovery, or next production stage
  -> print one terminal block
```

No direct branch skill derives the served stage from prose or `currentStage`.

### 4.3 Epic route

The CLI integration path remains:

```text
scripts/epic-manifest.py render-status <epic> --specs-dir <dir> --json
```

`forge-0-epic --next-feature` first resolves that member state and uses the same
production walk as `next_stage`. Unreadable member state may degrade only to the named
`forge-1-prd` fallback with a warning. Epic-member docs exits consume `render-status`
for actionable/blocked/completed handoff. Epic verification state lives in the epic
root's `.epic-state.json`; it never mutates a member state.

### 4.4 Adapter distribution

Current `scripts/build-adapters.py` defines:

```python
RUNTIME_HELPERS: tuple[str, ...] = (
    "forge-root.sh",
    "forge-init.sh",
    "epic-manifest.py",
    "forge-session.py",
    "validate-traceability.py",
    "forge-bootstrap.py",
)
```

`RUNTIME_HELPERS` is **unchanged** by this feature. Because the loader is mirrored into the two
consuming scripts (§3.4) rather than extracted, no new file is emitted and no import has to
resolve inside a bundle — the set stays at six, and the existing per-target copy assertions cover
it unmodified. Build-time host translation still rewrites canonical skill-body commands; runtime
`_host_command` translates script-generated commands. Both layers require tests.

All data reads are bounded to small config/state/manifest files and local skill artifacts.
No network, repository-history scan, or additional model turn is introduced.

## 5. Implementation Sequencing and Dependencies

Implement in this order:

1. **Definitions and additive schemas** — constants, status fields, manifest revision,
   tests proving legacy reads.
2. **Mirrored JSON loader + drift guard** — both copies, consumer integration, adapter
   regeneration, warning tests.
3. **Targeted verification writer** — feature and epic result/provenance modes, full-hash
   validation, revision freshness, atomic-failure tests.
4. **Read-side debt parity** — session classifiers, navigator rows, epic rollups/status.
5. **Expanded pure routing/rendering** — stage/outcome validation, owner semantics,
   verify-first commands, host/capability matrices.
6. **Canonical skill adoption** — branch skills, loop, docs, epic edit, stages 1–4,
   follow-up state-note recipes. Regenerate adapters after each coherent canon batch.
7. **Coverage guard and compliance fixture** — enforce the final nine-skill surface and
   real command-result evidence.
8. **Full regeneration and verification** — regenerate once more, run all gates.

The state writer precedes auto-verify scheduling so no directive can promise durable debt
before the writer exists. Routing precedes skill conversion so every converted skill can
be tested against a stable CLI. The explicit guard lands after all nine call sites to
avoid weakening it temporarily.

## 6. Build, Test, and Deployment

There is no deployment process beyond adapter generation and npm bundling of the generated
tree. Runtime and dev dependencies do not change.

Commands:

```bash
python3 scripts/build-adapters.py
bash scripts/validate.sh
ruff check scripts/ eval/
```

`bash scripts/validate.sh` is the single repository verify gate and includes spec purity,
drift, adapter-source verification, tests, ruff, traceability, and version sync.
`smokeCommand` remains `null`; CHECK-I21 is intentionally not-applicable for this repo and
must not be re-raised.

Generated output rules:

- Never hand-edit `adapters/`.
- Every canon/schema/runtime-helper edit that changes generated output ships with a fresh
  `python3 scripts/build-adapters.py` result.
- `python3 scripts/build-adapters.py --check` must report no drift.
- Both mirrored loader copies are asserted byte-identical to canon in all six targets; no new file
  appears under any emitted `scripts/`.

## Public API and Internal Surface

**This document defines no API.** It fixes file placement, module ownership, and
implementation order; every signature it mentions is owned elsewhere and is cited, never
redefined. Consult the owning contract rather than treating a path in §2 as a declaration:

- shared literals, result types, and the `UsageError`/hash contract → `00-core-definitions.md`;
- the `stage-exit` CLI and its routing callables → `02-stage-exit-routing.md`;
- the `state-verify` CLI, the state writers, and the single-writer model →
  `03-verification-state.md`;
- the skill-side stamp and slash-command surface users actually type → `04-skill-integration.md`;
- the mirrored duplicate-aware loader and the adapter distribution surface →
  `05-config-and-distribution.md`;
- coverage guards, fixtures, and scorers → `06-compliance-and-coverage.md`.

The one ownership rule this document does contribute: the flat scripts stay independently
executable and self-contained, so a shared definition is duplicated deliberately rather than
imported across that boundary — **with no exception**. This feature adds none (§3.4), and the
duplication is held in sync by a drift guard, as it already is for `PRODUCTION_STAGES`,
`KNOWN_VERIFY_STATUSES`, and `AGENT_TARGETS`.

## Dependencies

- `00-core-definitions.md` — all shared enums, payloads, writer signatures, and errors.
- Existing `scripts/forge-session.py`, `scripts/epic-manifest.py`, and
  `scripts/build-adapters.py` at the paths/signatures quoted above.
- Existing canonical stage skills and `references/stage-exit-protocol.md`.

## Verification

- [ ] Every path in §2 is accounted for by the implementation diff or explicitly retained.
- [ ] No generated adapter file was edited directly.
- [ ] No new file appears in any emitted `scripts/` directory; `RUNTIME_HELPERS` still has six
      entries, and both mirrored loader copies survive adapter generation byte-identically.
- [ ] All nine direct skills invoke the single scripted exit contract.
- [ ] Nested branch invocations emit no sentinel; outer invocations emit one final sentinel.
- [ ] Every successful epic manifest mutation increments revision exactly once.
- [ ] Loop skill remains within both body caps and retains the completed Step 2d split.
- [ ] Full validation and ruff commands pass with `smokeCommand: null` unchanged.
