# 07 — Testing Strategy

## Requirement Coverage

| REQ ID | Requirement | Section |
|---|---|---|
| REQ-EXIT-01..07 | Nine-stage acceptance, terminal ownership, sentinel, host translation, verify-first ordering, and capability gates | §3, §6 |
| REQ-ROUTE-01..06 | Served-stage inference and every verify/fix terminus | §3.2–§3.4 |
| REQ-PROD-01..06 | Loop, docs, and epic edit-mode route matrices | §3.5–§3.7 |
| REQ-DEBT-01..06 | Durable pending scheduling, transition replacement, read parity, interruption, and legacy compatibility | §4.1–§4.4 |
| REQ-STATE-01..04 | Full-hash writes, legacy hashes, targeted atomic writes, and two-commit provenance | §4.2–§4.5 |
| REQ-CONFIG-01..04 | Recursive warnings, shared consumers, last-key-wins, and arbitrary keys | §5 |
| REQ-GUARD-01..03 | Explicit nine-skill guard and replacement coverage for loop/docs contracts | §6.1 |
| REQ-EVAL-01..03 | Branch compliance scenarios, command-result evidence, negative fixtures, and baseline separation | §7 |
| REQ-CAP-01 | Preserve the loop prerequisite and both body caps | §6.2 |
| REQ-FOLLOW-01/02 | Runner wording and immediate PRD/tech state-note call sites | §6.2 |
| REQ-REL-01..03 | Deterministic output, fail-closed negatives, idempotency, and interrupted debt recovery | §3–§5, §7 |
| REQ-COMPAT-01..03 | Stages 0–4 regression coverage, legacy inputs, null smoke command, and CHECK-I21 semantics | §3.8, §4.4, §8 |
| REQ-PERF-01/02 | Bounded-file/no-network behavior and negligible common paths | §5.4, §8.2 |
| REQ-OBS-01/02 | Structured directive assertions and named human diagnostics | §3–§5, §7 |
| REQ-SEC-01 | Unsafe-name, containment, ambiguity, and epic/member isolation negatives | §3.7, §4.3, §5.3 |
| REQ-A11Y-01 | Interactive labels, descriptions, and recommended default in canon | §6.2 |

## 1. Purpose, Test Stack, and Principles

This is the final numbered specification. It verifies the contracts in
`00-core-definitions.md` through `06-compliance-and-coverage.md`; it does not define another
runtime API. The repository uses Python 3.10+, stdlib `unittest.mock`/pytest
`monkeypatch` where fault injection is appropriate, and pytest tests under `tests/`. There is
no root `pyproject.toml` and no project-wide `pytest-cov` configuration. Do not add a runtime or
dev dependency merely to implement this strategy. Behavioral coverage is measured by complete
enumerated matrices and requirement traceability rather than an invented line-coverage threshold
(REQ-PERF-01, project constraints).

The test layers are:

1. **Pure/in-process unit tests** import hyphenated scripts with
   `importlib.util.spec_from_file_location` and exercise deterministic classifiers, validators,
   renderers, parsers, and fault injection.
2. **CLI integration tests** invoke the real executable using `sys.executable`, capture stdout and
   stderr separately, and assert exit code, durable bytes, and JSON. These are authoritative for
   argparse, output, state writes, and host rendering.
3. **Canon/distribution tests** inspect canonical `skills/` and build fresh temporary adapter trees.
   Generated `adapters/` are never edited to make a test pass.
4. **Offline compliance tests** exercise the real scorer and real `forge-session.py` ground truth,
   but never require a model, API key, Claude CLI, or network.
5. **Repository gates** regenerate adapters, run `bash scripts/validate.sh`, then run the explicit
   ruff command (REQ-EVAL-02, REQ-GUARD-01..03, REQ-COMPAT-02).

Use mocks only to inject an otherwise difficult local failure, such as `os.replace` raising after a
temporary file is flushed. Do not mock `stage_exit`, `cmd_state_verify`, subprocess return codes,
adapter generation, transcript command-result pairs, or the compliance expected payload. When the
contract requires evidence that a user-visible CLI ran, execute the real CLI. A mocked command or a
prose assertion is not evidence (REQ-EVAL-02, REQ-STATE-03, REQ-REL-03).

## 2. Shared Test Helpers and Fixtures

### 2.1 Existing conventions and exact integration signatures

The following source signatures were inspected and are the integration targets tests must call.
From `scripts/forge-session.py`:

```python
def next_stage(state: dict) -> str | None: ...
def verify_state(state: dict) -> tuple[str | None, str]: ...
def pending_verify(state: dict) -> str | None: ...
def build_rows(specs_dir: Path, config: dict | None = None) -> list[FeatureRow]: ...
def _load_config(config_path: Path) -> dict: ...
def _resolve_feature_dir(specs_dir: Path, feature: str, epic: str | None) -> Path: ...
def _host_command(command: str, host: str) -> str: ...
def _next_steps_block(
    next_command: str, host: str, reconcile: dict | None = None
) -> str: ...
def stage_exit(
    feature: str,
    stage: str,
    specs_dir: Path,
    config_path: Path,
    epic: str | None,
    host: str,
    next_feature: str | None,
) -> dict: ...
def _resolve_feature_dir_for_write(
    specs_dir: Path, feature: str, epic: str | None
) -> Path: ...
def _load_state_for_write(
    specs_dir: Path, feature: str, epic: str | None
) -> tuple[Path, dict]: ...
def _commit_state(state_path: Path, state: dict) -> dict: ...
def cmd_state_complete(
    feature: str,
    stage: str,
    version: int,
    based_on: dict[str, int],
    artifacts: list[str],
    commit_hash: str | None,
    specs_dir: Path,
    epic: str | None,
    status: str | None = None,
    preserve_commit_hash: bool = False,
    resumable: bool = False,
) -> dict: ...
```

The target expanded `stage_exit`, `_next_steps_block`, and new `cmd_state_verify` signatures are
owned by `00-core-definitions.md` §§3, 5, and 6. Tests must switch to those exact signatures after
implementation rather than wrapping a second API.

> WARNING: Could not locate `cmd_state_verify` export in `scripts/forge-session.py` — verify before implementing.

> WARNING: Could not locate the expanded nine-stage `stage_exit` export or the target
> `_next_steps_block(primary_command, host, reconcile, deferred_command, outcome_text)` signature
> in `scripts/forge-session.py` — the source still exposes the stages-0–4 baseline.

From `scripts/epic-manifest.py`:

```python
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

From `eval/run-compliance-eval.py`:

```python
def run_session(cwd: Path, prompt: str, model: str) -> dict: ...
def parse_transcript(stdout: str) -> dict: ...
def _git_init(root: Path) -> None: ...
def expected_stage_exit(root: Path) -> dict: ...
def _in_fenced_block(text: str, needle: str) -> bool: ...
def _probe_report(
    probe: str, model: str, variant: str, results: list[RunResult]
) -> ProbeReport: ...
```

`_to_result` is also present in `eval/run-compliance-eval.py` with a multiline signature and must be
extended in place as specified by `06-compliance-and-coverage.md` §3–§5, which own the branch
fixture types, the evidence normalization and matching, and the scorer API respectively. The branch
fixture/helper signatures are new and are fully specified there.

> WARNING: Could not locate branch exports `load_branch_fixture`, `build_branch_fixture`,
> `branch_prompt`, `expected_branch_exit`, `ordered_command_evidence`, `score_branch_path`, or
> `run_branch_probe` in `eval/run-compliance-eval.py` — verify before implementing.

From `scripts/build-adapters.py`:

```python
def run_self_containment_pass(
    bundle_root: Path,
    repo_root: Path,
    skills: tuple[SkillRecord, ...],
) -> None: ...
def build_tree(root: Path, dest: Path) -> tuple[EmitResult, ...]: ...
```

### 2.2 Reusable real-CLI fixture

Keep epic-manifest's existing `tests/conftest.py::CliResult` and `run_cli` fixture unchanged.
Forge-session tests may add this distinctly named fixture to `tests/conftest.py` only if replacing
the duplicated local `_run` helpers is worthwhile; otherwise place it in the local test module.
The signature and implementation must remain valid Python:

```python
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pytest


@dataclass(frozen=True)
class SessionCliResult:
    """Captured result from the real forge-session executable.

    Frozen so a test cannot mutate captured output and assert against its own
    edit. All three fields are always populated — streams are captured, never
    inherited — so an empty string means the process wrote nothing, never that
    capture was skipped.
    """

    # Process exit status. 0 success; 2 is the project's fail-closed UsageError
    # code, which the error-path tests assert specifically rather than accepting
    # any non-zero value.
    returncode: int
    # Captured stdout, decoded text. Machine-readable under `--json` and parsed by
    # `json()`; warnings never appear here, which is what keeps `--json` parseable.
    stdout: str
    # Captured stderr, decoded text. Carries `Error: ...` lines and every warning,
    # including the lock-contention diagnostic. Asserting on stderr content is how
    # the tests verify diagnostics are actionable rather than bare.
    stderr: str

    def json(self) -> Any:
        """Decode JSON stdout.

        Returns:
            The decoded JSON value.

        Raises:
            json.JSONDecodeError: Standard output is not valid JSON.
        """
        return json.loads(self.stdout)


@pytest.fixture
def run_session_cli() -> Callable[..., SessionCliResult]:
    """Return a subprocess runner for `scripts/forge-session.py`.

    Returns:
        A callable accepting CLI strings plus optional `cwd` and returning captured
        output from the interpreter running pytest.
    """
    helper = Path(__file__).resolve().parent.parent / "scripts" / "forge-session.py"

    def _run(*args: str, cwd: Path | None = None) -> SessionCliResult:
        process = subprocess.run(
            [sys.executable, str(helper), *args],
            cwd=str(cwd) if cwd is not None else None,
            capture_output=True,
            text=True,
            check=False,
        )
        return SessionCliResult(process.returncode, process.stdout, process.stderr)

    return _run
```

State-mutating fixtures must use `tmp_path`; committed fixture templates remain read-only and are
copied before mutation. Capture `Path.read_bytes()` before every expected writer failure and assert
byte equality afterward. Do not normalize state through `json.dumps` before an atomicity assertion,
because semantic equality would miss an unintended rewrite (REQ-STATE-03, REQ-REL-02).

### 2.3 Fixture inventory

Use or add fixtures at these exact locations (REQ-DEBT-06, REQ-EVAL-01/02):

- `tests/fixtures/valid-epic/auth-overhaul/epic-manifest.json`: canonical new-format manifest with
  `revision: 1`.
- `tests/fixtures/status-derivation/lifecycle/epic-manifest.json`: live dashboard/debt cases with an
  explicit revision.
- a local copied manifest with `revision` removed: legacy compatibility; do not make every committed
  epic fixture legacy.
- local `tmp_path` feature states: transition and routing matrices; avoid a combinatorial tree of
  nearly identical committed JSON.
- `tests/fixtures/minimal-canon/scripts/forge_json.py` plus each
  `tests/fixtures/minimal-canon/expected-adapters/<agent>/scripts/forge_json.py`: generator snapshot
  inputs/outputs.
- `eval/fixtures/compliance/verify-fix-reverify.json`: the only committed branch compliance fixture;
  it is below a nested directory so `eval/run-eval.py`'s `fixtures/*.json` trigger glob cannot load
  it.

## 3. Stage Exit Unit and CLI Matrix

All rows in this section live in `tests/test_stage_exit.py` unless the canon assertion belongs in
`tests/test_stage_exit_protocol.py`. Parameterize by named `ids=` so a failure identifies its stage,
outcome, host, capability, and state (REQ-REL-01, REQ-OBS-01).

### 3.1 Stage acceptance, outcome validation, and terminal ownership

The acceptance matrix is exhaustive, not sampled (REQ-EXIT-01..04, REQ-REL-02):

| Stage | Accepted outcome(s) | Owner | Terminal expectation |
|---|---|---|---|
| `forge-0-epic`..`forge-4-backlog` | none; supplied outcome rejected | owner flag rejected | one final sentinel |
| `forge-5-loop` | `complete`, `partial`, `blocked`, `needs-human`, `deferred` | owner flag rejected | one final sentinel |
| `forge-6-docs` | `complete`, `blocked` | owner flag rejected | one final sentinel |
| `forge-verify` | `passed`, `findings`, `skipped`, `failed` | `direct` and `nested` | direct one; nested zero |
| `forge-fix` | `no-findings`, `decisions`, `failed`, `applied`, `reverified`, `reverify-findings`, `deferred` | `direct` and `nested` | direct one; nested zero |

For every outcome-bearing stage, test missing outcome, one outcome belonging to each other stage,
and an arbitrary unknown value. Test unknown stage, production owner, branch missing owner, and
unknown owner. Success JSON must match `StageExitPayload` from `00-core-definitions.md` §4. Direct
`nextSteps` contains the sentinel exactly once and its last line is the sentinel; default human
stdout also ends there. Nested payloads set `terminalOwnedBy == "outer"`, `nextSteps is None`, and
`sentinel is None`. Invalid requests exit 2, begin stderr with `Error:`, emit no success JSON, and
contain no sentinel (REQ-EXIT-03/04, REQ-OBS-02).

### 3.2 Served-stage and mode matrix

For both branch stages and both owners, cover (REQ-ROUTE-01..03, REQ-SEC-01):

- explicit `--served-stage` for every production stage `forge-0-epic` through `forge-6-docs`;
- mode-only mappings `epic→forge-0-epic`, `prd→forge-1-prd`, `tech→forge-2-tech`,
  `specs→forge-3-specs`, `backlog→forge-4-backlog`, `impl→forge-5-loop`;
- every matching explicit-stage/mode pair;
- at least every same-index-neighbor conflict plus an explicit `forge-6-docs` + mode conflict;
- neither field, invalid stage, invalid mode, unsafe feature, ambiguous same-named feature, and
  explicit wrong epic.

The positive assertion is the resolved `directives.servedStage`; the negative assertion includes
both actionable flag names and byte-identical candidate files. Add skill-side integration cases
showing verify obtains mode only from explicit/authoritative state and fix obtains it only from the
selected findings metadata; missing or ambiguous metadata must stop rather than use
`currentStage` or prose (REQ-ROUTE-02/03).

### 3.3 Verify/fix routes

Parameterize every branch outcome from `00-core-definitions.md` §2 and assert exact primary stage,
command, carried feature/served-stage, terminal owner, and whether advancement is forbidden
(REQ-ROUTE-04..06):

- verify: `passed→live successor`, `findings→fix`, `skipped→live successor`,
  `failed→verify recovery`;
- fix: `applied→verify`, `reverified→live successor`, `reverify-findings→fix`,
  `no-findings→verify while owed/live successor only when resolved`, and
  `decisions|failed|deferred→fix or navigator recovery without production advancement`.

Add complete path tests for findings → applied → passed and findings → applied → findings. After
`findings-applied`, execute a fresh stage-exit before re-verification and prove the production
successor is not primary. A nested chain emits no sentinel at any intermediate step; a final direct
or outer call emits exactly one (REQ-EXIT-04, REQ-STATE-04).

### 3.4 Verification priority, capabilities, hosts, and rendering

Cross the following values (pairwise only where the route is irrelevant, exhaustive where gate
selection changes) (REQ-EXIT-05..07, REQ-COMPAT-01):

| Verify state | Auto verify | Capability | Expected primary/gate |
|---|---:|---|---|
| `fresh`, `skipped` | either | either | production / `none` |
| `never`, `stale`, `failing`, `auto-pending` | true and owed | either | nested verify directive; production deferred |
| outstanding | false | `interactive` | `standard`; no advancing block before pass/skip |
| outstanding | false | `manual` | fenced verify / `manual-print`; production inline and conditional |

Run capability cases under all three hosts. Specifically pin capable Pi as `standard`, manual
Claude as `manual-print`, and manual Pi/generic as verify-first. Assert host only translates
commands/session wording: Claude `/clear` + `/feature-forge:`, Pi `/new` + `/skill:`, generic
host-neutral wording. In unresolved cases exactly `primaryCommand` is fenced; `deferredCommand`
never appears in a fence. Explicit skip must be persisted before the production command becomes
primary. Unknown capability exits 2 instead of silently becoming manual (REQ-EXIT-06/07,
REQ-REL-02).

Exercise blocking and non-blocking epic reconciliation together with outstanding verification.
Verification must remain primary; a blocking reconcile becomes deferred ahead of the ordinary
production successor. Repeated requests over byte-identical inputs must produce byte-identical
payloads except when the first call intentionally schedules new debt; after scheduling, repeated
same-revision calls must be byte-identical (REQ-REL-01).

### 3.5 Loop outcomes

For `forge-5-loop`, assert every exact route (REQ-PROD-01/02):

| Outcome | Expected primary | Forbidden |
|---|---|---|
| `complete` | verify-first impl route, then live docs/epic handoff | docs before pass/skip |
| `partial`, `deferred` | loop resume | docs readiness |
| `blocked`, `needs-human` | navigator recovery | docs readiness |

In canonical result-reporting tests, drive count combinations that select each outcome. Add
priority collisions (`needsHuman + blocked`, `blocked + deferred`, `deferred + pending`) and assert
one selected outcome in the order specified by `04-skill-integration.md` §6.1. A runner exit 0 with
pending backlog items is `partial`, not `complete`; absent authoritative counts emits no fabricated
success terminus (REQ-REL-02).

### 3.6 Documentation routes

For `forge-6-docs`, execute the real local `scripts/epic-manifest.py render-status ... --json`
integration (REQ-PROD-03/04):

- standalone complete and blocked;
- epic member with an actionable next member;
- no actionable member because dependencies block remaining work;
- all members complete;
- docs blocked inside an epic;
- render-status nonzero, malformed JSON, missing `nextCommand`/rollup field, and invalid graph.

Positive cases assert exact live member or dashboard command. Standalone complete fences the
navigator and mentions new-feature guidance only as secondary text. Failure cases exit 2 with no
sentinel and no guessed member. Do not mock `render-status`; construct real manifest/member state.
A narrowly injected `subprocess.run` failure may test the exceptional wrapper only after real
success/nonzero integration cases exist (REQ-PERF-01, REQ-REL-02).

### 3.7 Epic edit live routing and safety

Create an epic with one selected member at each live production position: fresh PRD, PRD complete,
tech complete, specs complete, backlog complete, loop complete, and all stages complete. Invoke the
real stage-exit and assert `next_stage` parity and exact command (REQ-PROD-05). Cover creation/no
state as the unchanged PRD route.

Negative/tolerant cases are missing state, corrupt JSON, non-object JSON, unreadable file, unsafe
member, flat/nested collision, two-epic ambiguity, wrong epic back-pointer, and contained member
whose progress is otherwise unresolvable. Unsafe/escaping identities exit 2; only a safe but
unreadable/unresolvable selected member receives the named PRD fallback warning. Assert no later
stage is fabricated and no candidate file changes (REQ-PROD-06, REQ-SEC-01).

### 3.8 Stages 0–4 compatibility targets

Retain existing tests and snapshots for stages 0–4, changing expectations only for the named
product corrections: epic edit live position, verification-primary ordering, and capability-aware
gate selection. Pin state-derived skipping, tolerant corrupt/missing read fallback, auto-fix clean
snapshot, epic reconcile precedence, JSON keys, human `DIRECTIVES:` prefix, host wording, and
sentinel position. A review must reject broad snapshot re-recording without an assertion explaining
one of those intentional changes (REQ-COMPAT-01/02, REQ-GUARD-03).

## 4. Verification State, Revision, Schema, and Provenance

### 4.1 Debt scheduling and read parity

Extend `tests/test_auto_verify.py` and `tests/test_stage_exit.py` with
`auto-verify-pending` cases for every verify-capable production token plus epic mode
(REQ-DEBT-01..05):

- stage-exit writes pending before returning `runInStageVerify: true` and reports
  `autoVerifyDebtRecorded: true` only after the write;
- same current revision is byte-idempotent, including `scheduledAt` and top-level `updatedAt`;
- a newer revision creates one new schedule;
- a fresh terminal or explicit skip does not reschedule;
- injected post-write dispatch interruption/non-adherence leaves the marker readable;
- injected write failure returns exit 2 and never emits the dispatch directive;
- `verify_state`, `_verify_state_for`, `pending_verify`, `build_rows`, rank-features/status,
  stage-exit, and epic `render-status` all classify it as `auto-pending`, pending, and retryable;
- old/missing scheduling revision remains `auto-pending` with a warning rather than `never`.

Do not mock the classifier or state writer. Inject the scheduling-to-dispatch gap by executing
stage-exit and deliberately performing no later verify call; then reopen the persisted file in a
separate CLI process (REQ-DEBT-04, REQ-REL-03).

### 4.2 `state-verify` transition matrix

Add `state-verify` to `tests/test_state_verbs.py` registration and dispatch guards and to
`tests/test_state_schema_conformance.py::VERB_INVOCATIONS`. Update assertions that currently pin
exactly seven verbs to expect eight. Test feature and epic targets for every legal row in
`03-verification-state.md` §3.3 (REQ-DEBT-03, REQ-STATE-03):

- pending schedule;
- passed with current version;
- findings reported with non-empty file and non-negative count;
- findings applied only after findings and with equal metadata;
- skipped;
- commit-2 after each applicable existing entry.

Validate schema conformance after every transition in realistic sequences:
`schedule→passed→commit-2`, `schedule→findings→commit-2→applied→passed→commit-2`, and
`schedule→skipped`. Assert terminal results remove scheduling fields; `findings-applied` removes
`verifiedStageVersion`; only a later passed write restores freshness. Assert unrelated entries and
unknown top-level fields survive (REQ-DEBT-03, REQ-OBS-01).

For every status, generate contradictory metadata: stale/zero/boolean version, missing artifact
version, negative count, empty findings path, findings metadata on passed/skipped/pending, supplied
version on applied, applied without a prior report, neither mode, and mixed result/hash mode. Every
case exits 2 and preserves bytes (REQ-REL-02).

### 4.3 Target isolation and atomic failures

Reuse the existing flat/nested collision fixture and add epic-root cases (REQ-STATE-03,
REQ-SEC-01):

- explicit member writes only that member state;
- ambiguous bare feature changes neither candidate;
- epic result and commit-2 write only `{specsDir}/{epic}/.epic-state.json`;
- epic writes never create/change a member `.pipeline-state.json`;
- mismatched `--feature`/`--epic`, manifest identity, missing manifest, corrupt epic state,
  non-object `stages`, unsafe name, and path escape fail before mutation.

Use `monkeypatch` only for `tempfile.mkstemp`, `os.fsync`, and `os.replace` spies/failures. Assert
successful call order and failed replacement cleanup as the existing `_write_state` tests do. The
original file must remain byte-identical and no sibling temporary debris may remain (REQ-STATE-03).

**Lost-update serialization.** The lock protocol of `03-verification-state.md` §3.5 exists to stop
two successful writers from discarding each other's unrelated updates, so prove that directly rather
than only asserting the lock file appears (REQ-STATE-03, REQ-REL-02):

- *Feature writers.* Two concurrent `state-verify` calls against the same `.pipeline-state.json`
  mutate **different** stage entries. Both must exit 0 and both mutations must be present in the
  final document. Run them as real concurrent processes (`subprocess` via the §2.2 real-CLI fixture)
  rather than threads, since the lock is cross-process by construction. Assert the negative control
  too: with acquisition stubbed to a no-op, the same test fails — proving the test observes the lock
  and not incidental timing.
- *Epic writers.* The same pairing against one `.epic-state.json`: an epic verify transition
  concurrent with an unrelated epic-state update, both surviving.
- *Interleaving is forced, not hoped for.* Wrap the load step with a `monkeypatch` barrier that makes
  writer A pause after its load until writer B has attempted acquisition. Without the lock this is a
  deterministic lost update; with it, B blocks until A replaces, then re-reads A's result.

**Lock lifecycle.** Cover acquisition, reclamation, and release as specified (REQ-REL-02, REQ-OBS-02):

- a live lock is **not** stolen — a second writer against a lock younger than `LOCK_STALE_S` blocks
  and then succeeds once the holder releases, and the holder's own release still finds its token;
- an abandoned lock recovers — a lock file aged past `LOCK_STALE_S` (set its mtime; do not sleep) is
  reclaimed and the write succeeds, with the double-check exercised by mutating the lock's `token`
  between the two reads so reclamation aborts and the writer resumes polling;
- an unreadable lock (truncated/non-JSON metadata) is reclaimable under the same age rule and its
  diagnostics report the holder as unreadable rather than inventing `pid`/`host` fields;
- acquisition timeout exits 2 with a message naming the state file, the holder's `pid`/`host`/`verb`,
  the lock age, and the recovery action — and leaves the target byte-identical;
- token-checked release: a writer whose lock was reclaimed mid-write does **not** unlink the new
  holder's lock, warns on stderr, and still reports its own completed write as success;
- a release failure does not mask an in-flight write error — the original exception propagates;
- no `.lock` file survives a successful write, and `*.json.lock` is matched by the specs-hygiene
  `.gitignore` so a lock can never be staged.

Keep `LOCK_TIMEOUT_S`, `LOCK_POLL_S`, `LOCK_STALE_S`, and `LOCK_STEAL_ATTEMPTS` injectable (module
constants patched per test) so the suite exercises real timeout and staleness paths without a
10-second or 300-second wall-clock cost. Assert the shipped defaults separately as plain constants.

**Writer coverage.** These lock tests parameterize over all eight `state-*` verbs, not `state-verify`
alone: §3.5 governs every writer, and a verb that skips acquisition reintroduces the lost update for
every other verb sharing the file.

### 4.4 Epic revision and legacy fixtures

Extend `tests/test_epic_manifest.py` and the fixture inventory in §2.3 (REQ-DEBT-05/06,
REQ-COMPAT-02):

1. new manifest creation starts at revision 1;
2. committed current-format fixtures validate with revision 1;
3. removing revision from a copied fixture loads logically as 1 without rewriting bytes;
4. its first semantic mutation writes revision 2;
5. every mutator (`add-feature`, `remove-feature`, `reorder`, `set-dep`, `set-status`, and edit-mode
   mutation paths present in source) increments exactly once;
6. validation failure, I/O failure, and semantic no-op preserve revision and bytes;
7. a manifest edit makes a prior epic pass stale and a prior pending marker visibly owed;
8. scheduling/pass metadata uses manifest revision, never a member stage version.

Keep one explicit legacy no-revision test rather than leaving all fixtures legacy. Update any schema
contract digest in `tests/test_state_schema_conformance.py` deliberately: the current
`PRE_R4_SCHEMA_CONTRACT_SHA256` pins an unchanged pre-R4 contract and will correctly fail after the
additive verify schema change. Replace it with a feature-specific baseline/structural assertion
that proves only the intended enum and scheduling fields changed; do not blindly re-pin a digest
without comparing the parsed schema (REQ-DEBT-06).

### 4.5 Hash and two-commit provenance

In `tests/test_state_verbs.py` and `tests/test_state_schema_conformance.py`, parameterize both
`state-complete` and feature/epic `state-verify` commit-2 boundaries (REQ-STATE-01..04):

- exactly 40 lower-, upper-, and mixed-case hex succeeds;
- lengths 0, 7 (legacy-looking), 39, and 41, plus non-hex and whitespace, fail before mutation;
- missing selected entry and mixed result/hash metadata fail;
- successful commit-2 changes only `commitHash` and `updatedAt`;
- Commit 1 contains `commitHash: null`, and Commit 2 records the supplied Commit-1 hash;
- a loaded legacy short hash passes read-side schema/classifier/navigator paths and is not migrated;
- source/canonical skill guards contain no `git commit --amend` provenance path.

Do not require a schema regex for legacy `commitHash`; new-write validation belongs at the writer
boundary (REQ-STATE-02).

### 4.6 Schema and constant parity

Update `tests/_state_schema.py` only as needed to understand the additive fields while remaining
stdlib-only. `tests/test_state_schema_conformance.py` must validate every intermediate writer
state, not only sequence endpoints. `tests/test_stage_constants_parity.py` must expect the exact six
statuses from `00-core-definitions.md`, extract both script constants, and compare them to
`references/pipeline-state-schema.json` rather than maintain an unconnected third vocabulary
(REQ-DEBT-02/05). Keep this guard unskippable.

## 5. Configuration Diagnostics Matrix

### 5.1 Pure loader matrix

Add focused tests for real `scripts/forge_json.py::load_json_with_duplicates` and
`warn_duplicate_keys` in `tests/test_effective_config.py` or a new
`tests/test_forge_json.py`; do not reproduce the hook in test code (REQ-CONFIG-01/03/04):

| Input | Parsed value | Duplicate list/warning |
|---|---|---|
| no duplicate | unchanged | none |
| same key twice at root | final value | one occurrence |
| same key three times | final value | two occurrences |
| nested object | final nested value | nested key |
| object inside array | final nested value | nested key |
| same key once in separate objects | unchanged | none |
| nested duplicate plus root duplicate | final values | decoder-hook order |
| arbitrary Unicode/control-character key | final value | safely JSON-quoted key |
| scalar/array root | stdlib value | duplicates still found inside nested objects |
| malformed/unreadable | exception | `JSONDecodeError`/`OSError` preserved |

Assert the exact warning line from `05-config-and-distribution.md` §2.2, stderr-only output, one
line per repeated occurrence, and deterministic ordering. Add a negative control proving the test
fails if first-key-wins or duplicate deduplication is substituted (REQ-REL-01).

### 5.2 Session and bootstrap CLI matrix

Execute real CLIs (REQ-CONFIG-01..03):

- `effective-config --json`, stage-exit, rank-features/doctor or another `_load_config` consumer:
  top-level and nested duplicates warn, stdout remains valid JSON, exit remains 0, and the last
  value drives behavior;
- no-duplicate config produces no warning and preserves current output;
- malformed/missing/non-object config retains each existing session fallback;
- real `forge-bootstrap.py commit` with duplicate `commitPrefix` warns, succeeds, and uses the last
  prefix;
- malformed/unreadable/non-object bootstrap config remains an actionable exit-2 error with no false
  success JSON.

Inspect the source to ensure specified project-config reads use the shared helper. Do not demand
that state, schema, transcript, or arbitrary answers JSON use it; that would widen scope
(REQ-CONFIG-02/04).

### 5.3 Safety and error output

Duplicate warnings never become `UsageError`, never alter files, never print complete config, and
never contaminate stdout. Capture config bytes before and after each warning-only command.
A stderr write failure may be injected with `monkeypatch` to assert `OSError` remains distinct, but
normal warning evidence must use the real function/CLI (REQ-CONFIG-03, REQ-OBS-02).

### 5.4 Performance/common path

A deterministic unit test may count loader calls/file opens for one consumer to ensure duplicate
detection does not add a second config read. Source assertions reject subprocess, Git, network, or
repository traversal in `forge_json.py`. Do not add wall-clock microbenchmarks; they are flaky and
unnecessary for the bounded `O(n + p)` algorithm. The no-duplicate functional result must equal the
pre-feature result and emit no extra bytes (REQ-PERF-01/02).

## 6. Canonical Skills and Adapter Integration

### 6.1 Explicit exit guard

Implement the `CanonicalExitSite` and `CANONICAL_EXIT_SITES` contracts from
`06-compliance-and-coverage.md` in `tests/test_stage_exit_protocol.py` (REQ-GUARD-01..03). The table
must equal the nine shared `EXIT_STAGES`, in order, with unique explicit paths. It must not use a
prefix glob to infer pipeline skills. Assert navigator/setup/bootstrap/advisory exclusions.

For every site, verify exactly one direct scripted invocation/terminal-print contract, exact stage,
applicable outcome flags, direct branch owner, nested owner/no-terminal wording, and sentinel-last
instruction. Negative tests operate on copied strings: remove one invocation, duplicate one
terminal marker, restore a bespoke standard/warm block, or add a nested sentinel and prove the
guard fails. Replace the current tests asserting bespoke loop blocks and terminal docs; do not
merely delete them (REQ-GUARD-03).

### 6.2 Skill semantics, caps, and follow-ups

Add/retain canon tests for (REQ-CAP-01, REQ-FOLLOW-01/02, REQ-A11Y-01):

- all loop outcome words and the deterministic priority rules appear at the exact owned result
  surface;
- `skills/forge-5-loop/SKILL.md` retains its Step 2d pointer to
  `skills/forge-5-loop/references/runner-contract.md`, does not duplicate run-mode detail, and stays
  at or below 300 body lines and 5,000 body words using the existing frontmatter-aware helpers in
  `tests/test_runner_contract_split.py`/`tests/test_always_loaded_surface.py`;
- the live skill-local runner reference no longer calls `--model` an “optional flag below,” while
  the agent-selection reference remains conditional;
- PRD and tech parking-lot instructions call the real `state-note` immediately and include the
  `--epic` member form; call-site tests should execute both standalone and member commands against
  temporary state to prove correct targeting;
- Standard Verify Gate prose has explicit labels, descriptions, and a recommended default; capable
  Pi is not excluded by host-name wording;
- no canon path authors whole state JSON or appends text after the terminal sentinel.

### 6.3 Adapter generation and host outputs

Extend `tests/test_build_adapters.py` and minimal-canon snapshots (REQ-EXIT-05/07,
REQ-COMPAT-02):

- `forge_json.py` exists beside both consumers for all six `AGENT_TARGETS`, mode `0644`, without a
  generated header, and byte-equal to source (including Pi);
- emitted consumer import smoke does not raise `ModuleNotFoundError`;
- all nine stamp sites ship in generated adapters;
- Claude output retains `/feature-forge:` and `/clear`; Pi output uses `/skill:` and `/new`;
  generic adapter canon remains vendor-neutral;
- build-time translations and runtime `_host_command` output agree, but capability language does
  not classify every Pi session as interactive;
- two builds are byte-identical, orphan purge works, and `--check` detects a missing/stale helper.

Run the real generator against copied minimal canon; do not mock `build_tree` or manually create the
expected generated helper. The YAML-dependent module may retain its existing visible skip when no
provisioned interpreter can import pinned YAML, but `bash scripts/validate.sh` provisions that
interpreter and makes adapter drift a hard gate (REQ-REL-01).

## 7. Compliance Fixture and Scorer Tests

### 7.1 Fixture validity and isolation

Implement `eval/fixtures/compliance/verify-fix-reverify.json` exactly as specified by
`06-compliance-and-coverage.md` §3 (REQ-EVAL-01..03). In `tests/test_compliance_eval.py`, load it
through the real `load_branch_fixture` and assert schema version, exact scenario order, safe
feature, served-stage/mode consistency, and non-empty ordered command tokens. Assert
`eval/run-eval.py::load_fixtures()` does not discover the nested file.

For each scenario, build a fresh repository, validate state with the existing stdlib validator,
and derive expected terminal ground truth by executing the real final `forge-session.py
stage-exit`. Never hard-code `nextSteps` in the test fixture and never share mutated state between
scenarios (REQ-REL-01).

Loader negatives must include malformed JSON, unknown/missing keys, wrong schema version, missing or
duplicate scenario, wrong order, unsafe feature, wrong served stage/mode, empty token list,
duplicate evidence stage, and inconsistent feature/context. Preserve `OSError` and
`json.JSONDecodeError`; use `RuntimeError` for fixture invariants (REQ-REL-02).

### 7.2 Transcript evidence and scorer matrix

Extend current transcript tests with actual assistant `tool_use` IDs and matching `tool_result`
events. Cover delayed-but-matching results, reconnaissance between expected calls, malformed stream
noise, missing final result, duplicate tool ID, result before request, duplicate result, explicit
zero exit, explicit nonzero exit, and error-without-exit-code (REQ-EVAL-02, REQ-OBS-01).

Positive offline fixtures for both `successful-rejoin` and `recovery` must satisfy every exact
criterion in `06-compliance-and-coverage.md` §5.2. The required negative matrix is:

1. missing tool result;
2. nonzero/error result;
3. reordered fix and re-verify;
4. duplicate stage-exit request;
5. duplicate terminal sentinel;
6. sentinel emitted during nested verify/fix;
7. correct sentinel followed by prose;
8. prose-only claim with no Bash evidence;
9. verbatim-looking block without the real terminal command;
10. wrong feature or served stage;
11. recovery incorrectly advancing to production;
12. successful commands but wrong fenced primary command.

Each negative test asserts its targeted criterion is false and, where relevant, that unrelated
criteria remain true. This prevents a single blanket `all(...) is False` assertion from masking
scorer defects. Command matching requires real `forge-session.py stage-exit` tokens, strict branch
order, paired seen result, exit code 0, and `isError is False`; a prose result tail never proves
success (REQ-EVAL-02).

### 7.3 Advisory live harness behavior

Retain current behavior: missing Claude driver returns a visible skipped report at exit 0; a model
miss is a scored noncompliant `RunResult`, not a harness process failure; fixture/scorer defects are
nonzero. Add `branch-path` to `--probe` help and `all`, and report successful-rejoin/recovery as
separate variants. `eval/README.md` must distinguish the original already-scripted
`forge-1-prd` linear baseline from branch compliance and must not average the cells together
(REQ-EVAL-03, REQ-COMPAT-01).

CI/offline tests must not invoke a live model, network, or API. The optional live probe is advisory
and is not part of `bash scripts/validate.sh`; the fixture loader, ground truth, parser, evidence
matcher, and scorer are hard-tested offline (REQ-EVAL-01/02).

## 8. Coverage Targets, Commands, and `smokeCommand`

### 8.1 Requirement coverage targets

Acceptance requires (REQ-GUARD-01..03, REQ-REL-02):

- **100% stage/outcome domain coverage:** all nine stages and all 18 stage-specific outcomes
  (5 loop + 2 docs + 4 verify + 7 fix), plus missing/foreign/unknown outcomes.
- **100% branch terminus coverage:** every verify and fix outcome direct and nested.
- **100% mode mapping coverage:** all six modes, all seven explicit production stages, matching,
  conflicting, and absent metadata.
- **100% verify state coverage:** every shared persisted status and every shared read label,
  including old/mismatched revisions.
- **100% writer transition coverage:** every legal `state-verify` transition and every forbidden
  metadata/mode family for both feature and epic targets.
- **100% host/capability behavior coverage:** Claude, Pi, generic crossed with interactive/manual
  where behavior differs.
- **100% canonical exit-site coverage:** exactly the explicit nine-site allow-list.
- **100% compliance criterion coverage:** each branch scorer criterion has one positive and at least
  one targeted negative test.
- **Every PRD requirement in this document's table** is represented by at least one named test or a
  repository gate. No numeric line threshold is imposed because the repo does not configure
  pytest-cov; adding an unenforced percentage would be false evidence.

### 8.2 Commands

During implementation, run focused groups first:

```text
python3 -m pytest tests/test_stage_exit.py tests/test_auto_verify.py -q
python3 -m pytest tests/test_state_verbs.py tests/test_state_schema_conformance.py tests/test_stage_constants_parity.py tests/test_epic_manifest.py -q
python3 -m pytest tests/test_effective_config.py tests/test_forge_bootstrap.py -q
python3 -m pytest tests/test_stage_exit_protocol.py tests/test_build_adapters.py tests/test_compliance_eval.py -q
```

Final verification, in order:

```text
python3 scripts/build-adapters.py
bash scripts/validate.sh
ruff check scripts/ eval/
```

`bash scripts/validate.sh` is the single full gate: it runs purity, adapter drift, pytest,
installer and adapter-source verification, ruff when available, traceability, and version sync.
The explicit ruff command remains required locally even though validation also runs it when
installed (project constraint). No live compliance model run is required for correctness
(REQ-EVAL-02, REQ-COMPAT-02).

### 8.3 Null smoke command and CHECK-I21

`forge.config.json` intentionally retains:

```json
"smokeCommand": null
```

`tests/test_smoke_command.py` must continue proving the schema accepts string-or-null, the init
template emits null, and the impl checklist labels CHECK-I21 not-applicable when no smoke command is
configured. This repository has no long-running server or wired application entrypoint that
`bash scripts/validate.sh` leaves untested; the configured `testCommand` is the strict superset.
Therefore CHECK-I21 is **not-applicable by design**, not skipped, missing, or a recommendation to
invent a smoke command. Do not fabricate a command or change `smokeCommand` as part of this feature
(REQ-COMPAT-03).

## 9. Error-Testing Rules

Every CLI negative asserts all applicable properties (REQ-REL-02, REQ-OBS-02):

- documented nonzero code (`2` for usage/I/O; manifest validation may retain its existing `1`);
- stdout is empty when a success payload would be unsafe;
- stderr begins with `Error:` or the operation's documented warning/finding format;
- message names feature/epic, stage/key/outcome, and a recovery flag/command where applicable;
- no sentinel or advancing fenced command is emitted;
- all candidate state/config/manifest files are byte-identical;
- no temporary debris remains.

Never assert only that “an exception occurred.” In-process unit tests assert the shared
`UsageError` type and meaningful message fragment; CLI tests assert its process mapping. Built-in
`OSError` and `json.JSONDecodeError` remain distinct at the duplicate loader and fixture-loader
boundaries. Tests must reject traceback leakage for expected user errors (REQ-CONFIG-03,
REQ-STATE-03).

## Public API and Internal Surface

**This document defines no production API.** It specifies tests, and tests are consumers: every
signature reproduced in §2.1 was read from existing source to pin what the suite may rely on,
and is owned by the document that specifies it — routing by `02-stage-exit-routing.md`, state
and locking by `03-verification-state.md`, the duplicate-aware loader and build helpers by
`05-config-and-distribution.md`, guards and fixtures by `06-compliance-and-coverage.md`.

- **User-facing:** none.
- **Test-only surface this document does own:** the reusable real-CLI fixture of §2.2 —
  `run_session_cli()` and its `SessionCliResult` result type — plus the fixture inventory of
  §2.3. These exist so tests exercise the shipped CLI as a subprocess rather than
  re-implementing argument parsing, which is what makes the §4.3 cross-process lock tests
  meaningful.
- **Private to the suite:** `_in_fenced_block` and `_probe_report`, and any per-module
  `monkeypatch` seams. §9 constrains where patching is legitimate at all: only
  `tempfile.mkstemp`, `os.fsync`, `os.replace`, and the injectable lock constants — never the
  logic under test.
- **A private helper reproduced in §2.1 is not thereby promoted.** Importing `_commit_state`
  or `_next_steps_block` in a test does not make it public; it stays renameable, and a test
  that pins its *name* rather than its *behavior* is the fragile kind §1 warns against.

## Dependencies

Implement before this strategy can pass:

- `00-core-definitions.md` — shared literals, payloads, verify entry, sentinel, writer signatures,
  and `UsageError`.
- `01-architecture-layout.md` — file ownership, runtime copy path, and implementation sequence.
- `02-stage-exit-routing.md` — expanded routing/rendering API and complete outcome tables.
- `03-verification-state.md` — state writer, debt, revision, schema, and provenance behavior.
- `04-skill-integration.md` — canonical direct/nested ownership and stage-specific call sites.
- `05-config-and-distribution.md` — duplicate-aware parser and adapter helper distribution.
- `06-compliance-and-coverage.md` — explicit guard and branch fixture/scorer contracts.

No external runtime dependency is added. Tests depend on pytest and the repository's existing
pinned generator YAML environment. Optional `jsonschema` tests may remain visibly skipped, but the
stdlib state validator must provide unconditional schema coverage.

## Verification

An implementation matches this specification only when all are true:

- [ ] Every matrix row in §§3–7 has a named test at the specified location.
- [ ] Real CLI subprocesses, not mocks or prose, establish stage-exit, writer, config-consumer, and
  compliance command evidence.
- [ ] All writer failures prove byte-level non-mutation and safe target isolation.
- [ ] Current and legacy epic/state fixtures separately prove additive compatibility.
- [ ] The nine-skill canon guard fails on removal, duplication, bespoke fallback, or nested terminal
  leakage.
- [ ] Adapter tests prove helper co-distribution and host translation for all six targets.
- [ ] Both compliance scenarios pass all criteria; every negative fixture fails its intended one.
- [ ] `eval/README.md` reports linear and branch baselines separately.
- [ ] `python3 scripts/build-adapters.py` completes and generated files are not hand-edited.
- [ ] `bash scripts/validate.sh` passes with no drift or traceability gap.
- [ ] `ruff check scripts/ eval/` passes.
- [ ] `smokeCommand` remains null and CHECK-I21 is recorded as not-applicable by design.
