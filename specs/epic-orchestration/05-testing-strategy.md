# 05 — Testing Strategy

> How Epic Orchestration is verified. The deterministic core (`scripts/epic-manifest.py`)
> is covered by a **pytest** suite over fixture epic trees; the prose skills (which are not
> unit-testable) are validated by `forge-verify` epic mode plus a PRD success-criteria
> acceptance walkthrough. This is the always-last `NN-testing-strategy` document.
>
> Stack: **prose plugin + Python 3 helpers** (stdlib only). All Python below is valid
> Python 3.10+ with complete type annotations and follows `references/stacks/python.md`
> conventions (pytest, `conftest.py` fixtures, `tmp_path`, Google-style docstrings).
>
> The CLI under test is specified by 02-manifest-helper-cli.md (parallel-written). Where
> that document is not yet available, this strategy targets the subcommand surface and
> behavior fixed by tech-spec §2.3 / §7 and the foundation docs (00 §4/§7/§8/§9). Subcommand
> names, the `Finding` shape (00 §4), the completion rule (00 §7), the derived sets
> (00 §8), and the exit-code contract (00 §9) are the normative source for the assertions
> here.

## Requirement Coverage

| REQ ID | Requirement | Section |
|--------|-------------|---------|
| REQ-EPIC-05 | Acyclic graph validated → `cycle` finding | 3.3 |
| REQ-DIR-03 | Name→dir resolution (flat/nested/ambiguous/not-found/unsafe) | 3.11 |
| REQ-DIR-04 | Globally unique names → `duplicate-name`/`ambiguous` | 3.4 |
| REQ-STATE-02 | Live status derivation; no cached status | 3.7 |
| REQ-ORCH-01 | Completion rule (§7 branches) | 3.7 |
| REQ-ORCH-03 | actionable / parallel-eligible / rollup | 3.9 |
| REQ-ROBUST-01 | Reconstruction <1s at 20 features | 3.12 |
| REQ-ROBUST-02 | Corrupt manifest → `corrupt-json`, no crash | 3.5 |
| REQ-ROBUST-03 | Atomic writes (temp + replace; interrupt-safe) | 3.8 |
| REQ-SEC-02 | Path-escape / unsafe-name rejection → exit 2 | 3.6 |
| REQ-VERIFY-01 | Skill-prose validation via forge-verify epic mode | 4.1 |
| REQ-COMPAT-01/02/03 | Standalone flows unchanged | 4.2, 5 |

Supporting (validated indirectly): the `dangling-ref` finding (REQ-ROBUST-02) §3.10; the
exit-code contract (00 §9) §3.13; every `FindingCode` in 00 §4 exercised by ≥1 test §6.

---

## 1. Scope & Approach

Two tiers, matching tech-spec §7:

1. **Deterministic core — unit-tested.** `scripts/epic-manifest.py` is pure-ish Python over
   files on disk. Every subcommand and every behavior that must be *repeatably correct*
   (acyclicity, uniqueness, path safety, atomic writes, status derivation, derived sets,
   exit codes) is exercised by pytest over fixture epic trees. This is the bulk of this
   document (§2, §3, §6).
2. **Prose skills — acceptance-checked.** The stage skills (`forge-0-epic`, the context
   injection in `forge-1/2/3`, the loop dependency gate + handoff, the navigator dashboard)
   are markdown prose driving an LLM; they are not unit-testable. They are validated by
   `forge-verify` epic mode (CHECK-E01..E08) and a manual PRD success-criteria walkthrough
   (§4).

**Coverage target (tech-spec §7, stated explicitly):** every helper subcommand
(`resolve`, `validate`, `check-name`, `render-status`, `add-feature`, `remove-feature`,
`reorder`, `set-dep`, `set-status`) and every 00 §7 / tech-spec §3.5 status branch is
exercised by **at least one** fixture/test. Every `FindingCode` in 00 §4 is produced by at
least one test (traceability table in §6).

---

## 2. Framework & Layout

- **Framework:** pytest (the dominant Python convention per `references/stacks/python.md`).
- **Dev dependency only:** pytest is not a plugin *runtime* dependency (01 §2.1); the helper
  itself is stdlib-only. The suite is skipped gracefully when pytest is absent (§5).
- **The helper is invoked as a subprocess in tests**, not imported, for the assertions that
  pin the **exit-code contract** (00 §9) and stdout JSON shape — that is the contract skills
  actually depend on. Pure helper functions (`find_cycle`, `derive_status`, `atomic_write`)
  are *also* imported directly (via `importlib`) for fine-grained unit tests where a
  subprocess would obscure the behavior (atomic-write interruption, in-process graph logic).

### 2.1 Directory layout (mirrors 01 §1.1)

```
tests/
  conftest.py                 # shared fixtures: run_cli(), helper_module(), fixtures_dir()
  test_epic_manifest.py       # the suite (all subsections of §3)
  fixtures/
    valid-epic/               # well-formed 4-feature epic (REQ-EPIC-02/03)
    cyclic-epic/              # dependsOn cycle a→b→a (REQ-EPIC-05)
    dup-name/                 # same feature name flat + nested (REQ-DIR-04)
    path-escape/              # manifest with unsafe name / ".." (REQ-SEC-02)
    corrupt/                  # non-parseable epic-manifest.json (REQ-ROBUST-02)
    status-derivation/        # synthetic .pipeline-state.json trees, one per §7 branch
```

`pytest` is run with `tests/` as rootdir; test files use `test_*` discovery. No
`pyproject.toml`/`[tool.pytest.ini_options]` is required (the suite uses defaults and
`conftest.py`), keeping the prose-plugin repo free of a Python project manifest.

### 2.2 Fixture tree contents

Each fixture is a **read-only template** copied into `tmp_path` before any test that may
mutate or whose behavior depends on absolute paths (`resolve`, `render-status`, all
mutators). Tests that only read (`validate` of a static manifest) may point the helper
directly at the in-repo fixture.

| Fixture | Contains | Exercises |
|---------|----------|-----------|
| `valid-epic/` | `{epic}/epic-manifest.json` (4 features, `config-store ← token-service ← api-gateway`, plus an independent `audit-log`), `EPIC.md`, and one `{feature}/.pipeline-state.json` per feature carrying the `epic` back-pointer. Manifest matches 00 §2.5 shape. | round-trip, render-status, resolution, performance baseline |
| `cyclic-epic/` | manifest where `a.dependsOn=[b]`, `b.dependsOn=[a]` (or a 3-node cycle `token→gateway→token`). | `cycle` finding (REQ-EPIC-05) |
| `dup-name/` | `{specsDir}` containing **two** feature-shaped dirs with the same bare name: one flat `specs/token-service/.pipeline-state.json` and one nested `specs/auth-overhaul/token-service/.pipeline-state.json`. | `duplicate-name` / `ambiguous` (REQ-DIR-04) |
| `path-escape/` | manifest with a feature `name` of `../escape` and a `consumes.from` of `../x`; plus a sibling that would resolve outside `{specsDir}`. | `unsafe-name` / `path-escape` (REQ-SEC-02) |
| `corrupt/` | `epic-manifest.json` containing truncated/garbage bytes (e.g. `{"epic": "x", "featur`). | `corrupt-json`, no crash (REQ-ROBUST-02) |
| `status-derivation/` | one epic with members `a` (incomplete loop), `b` (loop complete, no impl-verify), `c` (loop complete + impl `findings-reported`), `d` (loop complete + impl `findings-applied`), `e` (loop complete + impl `passed`), each as a synthetic `.pipeline-state.json`. `b.dependsOn=[a]`, `c.dependsOn=[d]`, etc., chosen to exercise actionable/blocked sets. | §7 completion branches (REQ-ORCH-01), derived sets (REQ-ORCH-03) |

A `dangling-ref` case (REQ-ROBUST-02) is produced by a tiny inline manifest built in
`tmp_path` (§3.10) rather than a standing fixture, since it is a one-field mutation of
`valid-epic`.

### 2.3 `conftest.py`

```python
"""Shared pytest fixtures for the epic-manifest helper suite."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HELPER = REPO_ROOT / "scripts" / "epic-manifest.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


@dataclass(frozen=True)
class CliResult:
    """Captured result of one helper subprocess invocation.

    Attributes:
        returncode: Process exit code (00 §9 contract: 0/1/2).
        stdout: Decoded standard output.
        stderr: Decoded standard error.
    """

    returncode: int
    stdout: str
    stderr: str

    def json(self) -> Any:
        """Parse stdout as JSON (for --json subcommands)."""
        return json.loads(self.stdout)


@pytest.fixture
def fixtures_dir() -> Path:
    """Absolute path to the read-only fixture templates."""
    return FIXTURES


@pytest.fixture
def fixture_copy(tmp_path: Path) -> "callable[[str], Path]":
    """Return a factory that copies a named fixture tree into tmp_path.

    Returns:
        A function taking a fixture name and returning the copied specs-dir
        root inside tmp_path. Used for any test that mutates state or depends
        on absolute paths.
    """

    def _copy(name: str) -> Path:
        dst = tmp_path / name
        shutil.copytree(FIXTURES / name, dst)
        return dst

    return _copy


@pytest.fixture
def run_cli() -> "callable[..., CliResult]":
    """Return a runner that invokes the helper as a subprocess.

    The subprocess boundary is deliberate: it pins the exit-code and stdout
    JSON contract (00 §9) that skills actually depend on.

    Returns:
        A function `run_cli(*args, cwd=None) -> CliResult`.
    """

    def _run(*args: str, cwd: Path | None = None) -> CliResult:
        proc = subprocess.run(
            [sys.executable, str(HELPER), *args],
            capture_output=True,
            text=True,
            cwd=str(cwd) if cwd else None,
        )
        return CliResult(proc.returncode, proc.stdout, proc.stderr)

    return _run


@pytest.fixture(scope="session")
def helper_module() -> ModuleType:
    """Import epic-manifest.py as a module for in-process unit tests.

    The filename contains a hyphen, so it is loaded via importlib rather than
    a normal import. Used to test pure functions (find_cycle, atomic_write,
    derive_status) directly.
    """
    spec = importlib.util.spec_from_file_location("epic_manifest", HELPER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
```

---

## 3. Unit Test Matrix

One subsection per concern. Each lists the concrete cases and a representative pytest
function (real Python, not pseudocode). Function bodies assert against the contracts in
00 §4/§7/§8/§9; where 02-manifest-helper-cli.md fixes an exact message or flag, the test
must be reconciled with it during implementation (noted inline).

### 3.1 Valid manifest round-trip (REQ-EPIC-02/03)

Load → validate → mutate → re-validate against `valid-epic`, asserting a clean
`{"valid": true, "findings": []}` and exit 0 at both ends.

```python
def test_valid_manifest_round_trip(run_cli, fixture_copy) -> None:
    """A well-formed epic validates clean, survives a mutation, re-validates clean."""
    specs = fixture_copy("valid-epic")
    epic = "auth-overhaul"

    first = run_cli("validate", epic, "--specs-dir", str(specs), "--json")
    assert first.returncode == 0
    assert first.json() == {"valid": True, "findings": []}

    # Mutate: add a new leaf feature with no deps (atomic write + re-validate).
    # --charter is a required option (02 §7.1); omitting it is a usage error (exit 2).
    added = run_cli(
        "add-feature", epic, "metrics",
        "--charter", "Metrics collection leaf feature.",
        "--specs-dir", str(specs),
    )
    assert added.returncode == 0

    again = run_cli("validate", epic, "--specs-dir", str(specs), "--json")
    assert again.returncode == 0
    assert again.json()["valid"] is True
```

### 3.2 Schema conformance (REQ-EPIC-02, REQ-STATE-02)

- A manifest with a per-feature `status` field must fail with a `cached-status` finding
  (00 §2 invariant 6, 00 §4) — guards against reintroducing cached status (REQ-STATE-02).
- A manifest missing a required top-level field (e.g. `narrativeDoc`) fails with a `schema`
  finding.

```python
def test_per_feature_status_field_rejected(run_cli, fixture_copy) -> None:
    """A Feature illegally carrying a status field fails validation (REQ-STATE-02)."""
    specs = fixture_copy("valid-epic")
    manifest = specs / "auth-overhaul" / "epic-manifest.json"
    data = json.loads(manifest.read_text())
    data["features"][0]["status"] = "complete"   # illegal cached status
    manifest.write_text(json.dumps(data))

    result = run_cli("validate", "auth-overhaul", "--specs-dir", str(specs), "--json")
    assert result.returncode == 1
    codes = {f["code"] for f in result.json()["findings"]}
    assert "cached-status" in codes
```

### 3.3 Cyclic graph rejection (REQ-EPIC-05)

`validate` of `cyclic-epic` → a `cycle` finding and exit 1; the message names the cycle
path (00 §4.2: `cycle: a → b → a`). The in-process `find_cycle` is also unit-tested,
including the degenerate **self-dependency** case (a feature whose `dependsOn` lists its
own name → `["X", "X"]`, formatted `cycle: X → X`; 00 §2.6 invariant 5).

```python
def test_cyclic_graph_rejected(run_cli, fixtures_dir) -> None:
    """A dependsOn cycle yields a 'cycle' finding and exit 1 (REQ-EPIC-05)."""
    result = run_cli(
        "validate", "cyclic-epic", "--specs-dir", str(fixtures_dir / "cyclic-epic"),
        "--json",
    )
    assert result.returncode == 1
    findings = result.json()["findings"]
    assert any(f["code"] == "cycle" for f in findings)
    assert any("→" in f["message"] for f in findings)


def test_find_cycle_pure(helper_module) -> None:
    """find_cycle returns a node path for a cyclic graph, None for a DAG."""
    cyclic = [
        {"name": "a", "dependsOn": ["b"]},
        {"name": "b", "dependsOn": ["a"]},
    ]
    acyclic = [
        {"name": "a", "dependsOn": []},
        {"name": "b", "dependsOn": ["a"]},
    ]
    assert helper_module.find_cycle(cyclic) is not None
    assert helper_module.find_cycle(acyclic) is None


def test_find_cycle_self_dependency(helper_module) -> None:
    """A feature depending on itself is a degenerate cycle (00 §2.6 inv. 5)."""
    self_dep = [{"name": "x", "dependsOn": ["x"]}]
    assert helper_module.find_cycle(self_dep) == ["x", "x"]
```

### 3.4 Duplicate-name detection — flat vs nested (REQ-DIR-04)

- `check-name` for a name that already exists anywhere → exit 1 (duplicate), preventing a
  **new** collision (tech-spec §3.4).
- `resolve` of a name matching two feature-shaped dirs → `ambiguous` finding + exit 1, with
  a message listing both paths (00 §4.2).

```python
def test_check_name_rejects_existing(run_cli, fixture_copy) -> None:
    """check-name rejects a name already present in the tree (REQ-DIR-04)."""
    specs = fixture_copy("dup-name")
    result = run_cli("check-name", "token-service", "--specs-dir", str(specs))
    assert result.returncode == 1


def test_resolve_ambiguous_name(run_cli, fixture_copy) -> None:
    """A name matching a flat and a nested dir resolves as ambiguous (REQ-DIR-04)."""
    specs = fixture_copy("dup-name")
    result = run_cli("resolve", "token-service", "--specs-dir", str(specs), "--json")
    assert result.returncode == 1
    codes = {f["code"] for f in result.json()["findings"]}
    assert "ambiguous" in codes or "duplicate-name" in codes
```

### 3.5 Corrupt-JSON handling (REQ-ROBUST-02)

`validate` of `corrupt/` must emit a `corrupt-json` finding and exit 1 **without** raising
an unhandled exception (no traceback on stderr).

```python
def test_corrupt_manifest_no_crash(run_cli, fixtures_dir) -> None:
    """A non-parseable manifest yields 'corrupt-json' and exit 1, not a crash."""
    result = run_cli(
        "validate", "corrupt", "--specs-dir", str(fixtures_dir / "corrupt"), "--json",
    )
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    codes = {f["code"] for f in result.json()["findings"]}
    assert "corrupt-json" in codes
```

### 3.6 Path-escape / unsafe-name rejection (REQ-SEC-02)

Unsafe names must be rejected **before** filesystem access. Per 00 §9, a name that is
unsafe *as a CLI argument* (separators / `..` / absolute) is a usage/IO error → **exit 2**;
an unsafe name discovered *inside a manifest* during `validate` is a finding → exit 1.
Both forms are tested.

```python
import pytest


@pytest.mark.parametrize("bad", ["../escape", "a/b", "/abs/path", ".."])
def test_resolve_unsafe_name_exit_2(run_cli, fixture_copy, bad: str) -> None:
    """An unsafe name argument is rejected before FS access with exit 2 (REQ-SEC-02)."""
    specs = fixture_copy("valid-epic")
    result = run_cli("resolve", bad, "--specs-dir", str(specs))
    assert result.returncode == 2


def test_path_escape_in_manifest_is_finding(run_cli, fixtures_dir) -> None:
    """An unsafe name inside a manifest yields unsafe-name/path-escape findings."""
    result = run_cli(
        "validate", "path-escape", "--specs-dir", str(fixtures_dir / "path-escape"),
        "--json",
    )
    assert result.returncode == 1
    codes = {f["code"] for f in result.json()["findings"]}
    assert codes & {"unsafe-name", "path-escape"}
```

### 3.7 Status derivation — every §7 branch (REQ-STATE-02, REQ-ORCH-01)

One test per 00 §7 / tech-spec §3.5 branch, driven by the synthetic `.pipeline-state.json`
files in `status-derivation/`. The completion predicate (00 §7) is:

```
forge-5-loop.status == "complete"
  AND (forge-verify-impl absent OR its status in {"passed", "findings-applied"})
```

| Member | loop status | forge-verify-impl | Expected derived status | complete-for-orchestration |
|--------|-------------|-------------------|-------------------------|----------------------------|
| `a` | not complete | — | `in-progress` | no |
| `b` | complete | absent | `complete` | **yes** |
| `c` | complete | `findings-reported` | `in-progress` | **no** |
| `d` | complete | `findings-applied` | `complete` | **yes** |
| `e` | complete | `passed` | `complete` | **yes** |

```python
import pytest


@pytest.mark.parametrize(
    "member, expect_complete",
    [
        ("a", False),   # loop incomplete
        ("b", True),    # loop complete, no impl-verify
        ("c", False),   # loop complete, impl findings-reported (unfixed)
        ("d", True),    # loop complete, impl findings-applied
        ("e", True),    # loop complete, impl passed
    ],
)
def test_derive_status_branches(
    helper_module, fixtures_dir, member: str, expect_complete: bool
) -> None:
    """Each §7 completion branch derives the correct complete-for-orchestration value."""
    feature_dir = fixtures_dir / "status-derivation" / "lifecycle" / member
    status = helper_module.derive_status(feature_dir)
    assert (status == "complete") is expect_complete
```

A live acceptance check for REQ-STATE-02 (edit pipeline-state, re-render, no refresh step):

```python
def test_status_reflects_edited_pipeline_state(run_cli, fixture_copy) -> None:
    """Editing a feature's pipeline-state changes render-status with no refresh (REQ-STATE-02)."""
    specs = fixture_copy("status-derivation")
    epic = "lifecycle"
    before = run_cli("render-status", epic, "--specs-dir", str(specs), "--json").json()

    state = specs / epic / "a" / ".pipeline-state.json"
    data = json.loads(state.read_text())
    data["stages"]["forge-5-loop"] = {"status": "complete"}
    state.write_text(json.dumps(data))

    after = run_cli("render-status", epic, "--specs-dir", str(specs), "--json").json()
    assert before != after
    a_after = next(f for f in after["features"] if f["name"] == "a")
    assert a_after["status"] == "complete"
```

### 3.8 Atomic-write behavior (REQ-ROBUST-03)

Two cases:
1. **Mechanism:** a mutation creates a temp file in the *same directory* then `os.replace`s
   it (atomic on POSIX) — assert no stray temp file remains and the result is valid JSON.
2. **Interrupt safety:** if the write is interrupted *before* the replace, the original
   manifest is left intact. Simulated by monkeypatching `os.replace` to raise.

```python
import json
import os

import pytest


def test_atomic_write_replaces_cleanly(helper_module, tmp_path) -> None:
    """atomic_write produces valid JSON and leaves no temp file behind (REQ-ROBUST-03)."""
    target = tmp_path / "epic-manifest.json"
    target.write_text('{"schemaVersion": 1, "old": true}')

    helper_module.atomic_write(target, {"schemaVersion": 1, "new": True})

    assert json.loads(target.read_text()) == {"schemaVersion": 1, "new": True}
    leftovers = [p for p in tmp_path.iterdir() if p != target]
    assert leftovers == []


def test_interrupted_write_leaves_original_intact(
    helper_module, tmp_path, monkeypatch
) -> None:
    """An interrupted write (replace fails) never corrupts the original (REQ-ROBUST-03)."""
    target = tmp_path / "epic-manifest.json"
    original = '{"schemaVersion": 1, "old": true}'
    target.write_text(original)

    def boom(src: str, dst: str) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(KeyboardInterrupt):
        helper_module.atomic_write(target, {"schemaVersion": 1, "new": True})

    assert target.read_text() == original   # untouched
```

### 3.9 render-status correctness (REQ-ORCH-03)

Against `valid-epic` / `status-derivation`, assert the `render-status` output object
(00 §5 / §8, tech-spec §4.4): `actionable`, `parallelEligible`, `rollup`, `nextCommand`,
and per-feature `blocked`/`unmetDeps`.

```python
def test_render_status_derived_sets(run_cli, fixture_copy) -> None:
    """actionable/parallelEligible/rollup are computed over the graph + §7 status."""
    specs = fixture_copy("status-derivation")
    out = run_cli("render-status", "lifecycle", "--specs-dir", str(specs), "--json").json()

    assert set(out["actionable"]).isdisjoint(_complete_names(out))
    # parallel-eligible is a subset of actionable (00 §8)
    assert set(out["parallelEligible"]) <= set(out["actionable"])
    assert out["rollup"]["total"] == len(out["features"])
    assert out["rollup"]["complete"] == len(_complete_names(out))
    if out["actionable"]:
        assert out["nextCommand"].startswith("/feature-forge:")


def _complete_names(out: dict) -> set[str]:
    return {f["name"] for f in out["features"] if f["status"] == "complete"}


def test_blocked_feature_lists_unmet_deps(run_cli, fixture_copy) -> None:
    """A feature with an incomplete dependency is blocked with its unmet deps listed."""
    specs = fixture_copy("status-derivation")
    out = run_cli("render-status", "lifecycle", "--specs-dir", str(specs), "--json").json()
    blocked = [f for f in out["features"] if f["blocked"]]
    assert all(f["unmetDeps"] for f in blocked)
```

### 3.10 Dangling-dependsOn detection (REQ-ROBUST-02)

A `dependsOn` (or `consumes.from`) pointing at a non-member feature → `dangling-ref`
finding + exit 1 (00 §2 invariant 4).

```python
def test_dangling_depends_on(run_cli, fixture_copy) -> None:
    """A dependsOn referencing an unknown feature yields a 'dangling-ref' finding."""
    specs = fixture_copy("valid-epic")
    manifest = specs / "auth-overhaul" / "epic-manifest.json"
    data = json.loads(manifest.read_text())
    data["features"][1]["dependsOn"] = ["config-stor"]   # typo, not a member
    manifest.write_text(json.dumps(data))

    result = run_cli("validate", "auth-overhaul", "--specs-dir", str(specs), "--json")
    assert result.returncode == 1
    codes = {f["code"] for f in result.json()["findings"]}
    assert "dangling-ref" in codes
```

### 3.11 Resolution — flat / nested / ambiguous / not-found / unsafe (REQ-DIR-03)

`resolve` returns the correct absolute directory and exit code for each case. (Ambiguous
and unsafe are also covered in §3.4 / §3.6; here they round out the resolver matrix.)

```python
def test_resolve_flat(run_cli, fixture_copy) -> None:
    """A flat standalone feature resolves to its flat path, exit 0 (REQ-DIR-03)."""
    specs = fixture_copy("dup-name")   # contains a flat token-service AND nested one
    # Use an unambiguous flat-only name present in the fixture:
    result = run_cli("resolve", "flat-only", "--specs-dir", str(specs))
    assert result.returncode == 0
    assert result.stdout.strip().endswith("/flat-only")


def test_resolve_nested(run_cli, fixture_copy) -> None:
    """A nested epic member resolves to its nested path, exit 0 (REQ-DIR-03)."""
    specs = fixture_copy("valid-epic")
    result = run_cli("resolve", "token-service", "--specs-dir", str(specs))
    assert result.returncode == 0
    assert "/auth-overhaul/token-service" in result.stdout.strip()


def test_resolve_not_found(run_cli, fixture_copy) -> None:
    """An unknown name yields a 'not-found' finding and exit 1 (REQ-DIR-03)."""
    specs = fixture_copy("valid-epic")
    result = run_cli("resolve", "nonexistent", "--specs-dir", str(specs), "--json")
    assert result.returncode == 1
    codes = {f["code"] for f in result.json()["findings"]}
    assert "not-found" in codes
```

> The `flat-only` and an unambiguous nested member must be present in the `dup-name` /
> `valid-epic` fixtures (§2.2). Add `flat-only` to `dup-name` when authoring the fixture.

### 3.12 Performance sanity — 20 features <1s (REQ-ROBUST-01)

A generated 20-feature epic (chain + a few branches) must `validate` and `render-status`
in well under 1s. Generated into `tmp_path` rather than committed.

```python
import json
import time


def _make_20_feature_epic(specs: "Path") -> str:
    """Build a 20-feature acyclic epic on disk; return the epic name."""
    epic = "big-epic"
    epic_dir = specs / epic
    features = []
    for i in range(20):
        name = f"feat-{i:02d}"
        (epic_dir / name).mkdir(parents=True, exist_ok=True)
        (epic_dir / name / ".pipeline-state.json").write_text(
            json.dumps({"epic": epic, "currentStage": "forge-1-prd", "stages": {}})
        )
        features.append(
            {
                "name": name,
                "charter": "x",
                "dependsOn": [f"feat-{i - 1:02d}"] if i else [],
                "exposes": [],
                "consumes": [],
            }
        )
    (epic_dir / "epic-manifest.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "epic": epic,
                "description": "x",
                "status": "active",
                "narrativeDoc": "EPIC.md",
                "createdAt": "2026-06-12T00:00:00Z",
                "updatedAt": "2026-06-12T00:00:00Z",
                "features": features,
            }
        )
    )
    (epic_dir / "EPIC.md").write_text("# big-epic\n")
    return epic


def test_20_feature_validate_render_under_1s(run_cli, tmp_path) -> None:
    """validate + render-status on a 20-feature epic completes under 1s (REQ-ROBUST-01)."""
    specs = tmp_path / "specs"
    epic = _make_20_feature_epic(specs)

    start = time.perf_counter()
    v = run_cli("validate", epic, "--specs-dir", str(specs), "--json")
    r = run_cli("render-status", epic, "--specs-dir", str(specs), "--json")
    elapsed = time.perf_counter() - start

    assert v.returncode == 0 and r.returncode == 0
    assert elapsed < 1.0
```

> The threshold counts two full subprocess launches; the helper's own work is `O(V+E)` and
> negligible (tech-spec §3.1). If interpreter-startup jitter on slow CI risks flakiness,
> raise to `< 1.5` and additionally assert the in-process `render_status()` call (no
> subprocess) is `< 0.1s`.

### 3.13 Exit-code contract — 0 / 1 / 2 per subcommand (00 §9)

A table-driven test pins the exit code for each subcommand in each outcome class. This is
the contract skills gate on.

```python
import pytest


@pytest.mark.parametrize(
    "argv, expected",
    [
        (["validate", "auth-overhaul"], 0),                 # valid → 0
        (["validate", "cyclic-epic"], 1),                   # findings → 1
        (["validate", "no-such-epic"], 2),                  # missing manifest / IO → 2
        (["check-name", "brand-new-name"], 0),              # unique → 0
        (["check-name", "token-service"], 1),               # duplicate → 1
        (["resolve", "token-service"], 0),                  # resolved → 0
        (["resolve", "../escape"], 2),                      # unsafe arg → 2
        (["resolve", "nonexistent"], 1),                    # not-found → 1
    ],
)
def test_exit_code_contract(run_cli, request, argv, expected) -> None:
    """Each subcommand follows the 0/1/2 exit-code contract (00 §9)."""
    # specs-dir is selected per-case in the real suite; see note below.
    ...
```

> In the implemented suite this is split per fixture (each row needs the matching
> `--specs-dir`); the table above documents the **intended** code for every
> (subcommand, outcome) pair. Mutator subcommands (`add-feature`/`remove-feature`/`reorder`/
> `set-dep`/`set-status`) additionally assert: exit 0 on a clean mutation, exit 1 when the
> mutation would introduce a cycle or dangling ref (refused, original manifest intact —
> reuses the §3.8 interrupt-safety guarantee), exit 2 on unsafe name / IO error.

---

## 4. Skill-Prose Validation (not unit-testable)

The stage skills are prose; they are validated by the two mechanisms below. Both are
manual/acceptance gates, not pytest.

### 4.1 forge-verify epic mode (REQ-VERIFY-01)

Run `forge-verify` in **epic** mode against a real (or fixture) epic. It executes
CHECK-E01..E08 (tech-spec §5.5, verification-checklists.md):

| Check | Asserts | Delegates to |
|-------|---------|--------------|
| CHECK-E01 | Manifest conforms to `epic-manifest-schema.json` | `epic-manifest.py validate` |
| CHECK-E02 | Dependency graph acyclic | `validate` |
| CHECK-E03 | No dangling `dependsOn` | `validate` |
| CHECK-E04 | Charter coverage (every feature has a charter + obligations) | verifier judgment |
| CHECK-E05 | Non-empty `exposes`/`consumes` per feature | verifier judgment |
| CHECK-E06 | EPIC.md prose ↔ manifest contract drift (completed features) | verifier judgment |
| CHECK-E07 | `epic` back-pointer ↔ manifest membership consistency | verifier judgment |
| CHECK-E08 | Global name uniqueness audit (non-fatal) | `validate` / `check-name` |

Because E01/E02/E03/E08 delegate to the helper, the pytest suite (§3) already gives those
checks deterministic coverage; epic mode wires them into the verification report. E04–E07
are verifier judgment and have no unit test — they are the reason epic mode exists.

### 4.2 PRD success-criteria walkthrough (acceptance checklist)

A manual end-to-end pass mapping each PRD §8 success criterion to an observable outcome.
Run once per release of this feature; checklist:

- [ ] **Decompose** a large change via `forge-0-epic` into **≥2** features with
      dependencies; assert `epic-manifest.json` + `EPIC.md` are created, `validate` is
      clean, and the creation is committed (PRD §8.1; REQ-EPIC-01/02/03).
- [ ] **Context injection:** run stages 1–3 on a member feature whose direct dependency is
      complete; confirm EPIC.md, the feature's charter, and the completed upstream
      PRD/tech-spec are loaded into context (PRD §8.2; REQ-CTX-01/02).
- [ ] **Blocked-loop gate:** attempt `forge-5-loop` on a feature with an incomplete
      dependency; confirm the dependency warning lists the unmet deps and a confirmation
      gate is required to proceed (PRD §8.3; REQ-ORCH-04).
- [ ] **Completion handoff:** complete a member feature; confirm the prompted handoff
      announces completion, offers the recommended-but-skippable impl-verify, and
      identifies the correct next actionable feature(s) per the graph (PRD §8.4;
      REQ-ORCH-01/02/03).
- [ ] **Fresh-session dashboard:** in a brand-new session (no in-memory state), render the
      epic dashboard and confirm it reconstructs per-feature stage, blocked/actionable
      status, and the next recommended command purely from disk (PRD §8.5; REQ-VIS-01,
      REQ-ROBUST-01).
- [ ] **Standalone unchanged:** in a project with **no** epics, run a standalone feature
      through stages 1–6 and confirm byte-for-byte identical behavior (PRD §8.6;
      REQ-COMPAT-01/02/03) — see §4.3.

### 4.3 Standalone-regression guard (REQ-COMPAT-01/02/03)

The strongest compatibility guarantee is that `bash scripts/validate.sh` continues to pass
unchanged (existing checks untouched, §5) and that `resolve` of a pre-existing flat feature
returns its flat path with no epic logic engaged (covered deterministically by
`test_resolve_flat`, §3.11). No migration of existing `.pipeline-state.json` files is
required (REQ-COMPAT-02) — the resolver and §3.7 tests use both fielded and field-absent
state files.

---

## 5. validate.sh Wiring

Append a new numbered step to `scripts/validate.sh`, **after step 6 (script permissions)
and before the final summary block** (current lines 119–130). It must:

- run `python3 -m py_compile scripts/epic-manifest.py` (the `typeCheckCommand` default,
  tech-spec §2.4) — a hard check; failure increments `ERRORS`;
- run the pytest suite **only if pytest is available** (`python3 -m pytest` importable);
  when pytest is absent, print a non-fatal skip line and do **not** increment `ERRORS`, so
  the existing structure checks still pass on machines without pytest (01 §6);
- mirror the existing `PASS:` / `FAIL:` / `ERRORS=$((ERRORS + 1))` style and the leading
  blank-line + section-echo pattern used by steps 4–6.

Exact bash to insert:

```bash
# 7. Compile-check and test the epic-manifest helper
echo ""
echo "Checking epic-manifest helper..."
HELPER="$REPO_ROOT/scripts/epic-manifest.py"
if [ -f "$HELPER" ]; then
  if python3 -m py_compile "$HELPER" 2>/dev/null; then
    echo "PASS: scripts/epic-manifest.py compiles"
  else
    echo "FAIL: scripts/epic-manifest.py failed py_compile"
    ERRORS=$((ERRORS + 1))
  fi

  if python3 -c "import pytest" 2>/dev/null; then
    if python3 -m pytest "$REPO_ROOT/tests" -q; then
      echo "PASS: epic-manifest pytest suite"
    else
      echo "FAIL: epic-manifest pytest suite"
      ERRORS=$((ERRORS + 1))
    fi
  else
    echo "SKIP: pytest not installed; skipping epic-manifest test suite (non-fatal)"
    WARNINGS=$((WARNINGS + 1))
  fi
else
  echo "SKIP: scripts/epic-manifest.py not present yet (non-fatal)"
  WARNINGS=$((WARNINGS + 1))
fi
```

- `WARNINGS` is already declared (line 14) and surfaced in the success summary
  (lines 123–125), so the skip lines are reported without failing the run.
- The `[ -f "$HELPER" ]` guard keeps `validate.sh` green in the window before the helper is
  authored (the suite is built incrementally). Once the helper ships, the file always
  exists, so the compile check is effectively mandatory.
- The step is intentionally **last** among the checks so a helper/test failure does not mask
  the structural checks above it.

---

## Dependencies

- **00-core-definitions.md** — the `Finding` taxonomy (§4, every `FindingCode` exercised),
  the completion rule (§7, each branch tested), the derived sets (§8), and the exit-code
  contract (§9) are the assertion targets for the entire suite.
- **01-architecture-layout.md** — the `tests/` + `fixtures/` layout (§1.1), the helper's
  function inventory imported in-process (§3: `find_cycle`, `atomic_write`, `derive_status`,
  `render_status`), and the `validate.sh` wiring slot (§6).
- **02-manifest-helper-cli.md** — the subcommand signatures, exact flag names, output JSON
  shapes, and finding messages under test. Where 02 fixes an exact string/flag that differs
  from an illustrative assertion here, **02 wins** and the test is reconciled at
  implementation time. (If 02 is unavailable, tech-spec §2.3 / §7 is the fallback source.)

## Verification

- [ ] `python3 -m pytest tests/ -q` is green: every subsection of §3 passes.
- [ ] Coverage of every subcommand confirmed: `resolve`, `validate`, `check-name`,
      `render-status`, and each mutator (`add-feature`/`remove-feature`/`reorder`/`set-dep`/
      `set-status`) is exercised by ≥1 test (§3.13 mutator note + §3.1/§3.4/§3.9/§3.11).
- [ ] Every 00 §7 / tech-spec §3.5 status branch (loop incomplete; complete + no
      impl-verify; complete + `findings-reported`; complete + `findings-applied`; complete +
      `passed`) is exercised (§3.7).
- [ ] Every `FindingCode` in 00 §4 is produced by ≥1 test (§6 traceability table).
- [ ] `bash scripts/validate.sh` passes with pytest installed (runs the suite) **and**
      without pytest installed (skips the suite non-fatally; existing checks still PASS).
- [ ] `python3 -m py_compile scripts/epic-manifest.py` exits 0 (run by validate.sh step 7).

---

## 6. FindingCode → Test Traceability (00 §4)

Confirms 00-core-definitions.md §4 invariant: every `FindingCode` is producible by a
helper subcommand and is asserted by this suite.

| FindingCode | Produced by | Test |
|-------------|-------------|------|
| `corrupt-json` | `validate` of `corrupt/` | §3.5 `test_corrupt_manifest_no_crash` |
| `schema` / `cached-status` | `validate` with illegal field | §3.2 `test_per_feature_status_field_rejected` |
| `duplicate-name` | `check-name` / `resolve` in `dup-name/` | §3.4 |
| `dangling-ref` | `validate` with bad `dependsOn` | §3.10 `test_dangling_depends_on` |
| `cycle` | `validate` of `cyclic-epic/` | §3.3 `test_cyclic_graph_rejected` |
| `unsafe-name` | `resolve` of unsafe arg; `validate` of `path-escape/` | §3.6 |
| `path-escape` | `validate` of `path-escape/` | §3.6 `test_path_escape_in_manifest_is_finding` |
| `not-found` | `resolve` of unknown name | §3.11 `test_resolve_not_found` |
| `ambiguous` | `resolve` in `dup-name/` | §3.4 `test_resolve_ambiguous_name` |

> `schema` and `cached-status` share §3.2 because a per-feature `status` field is the
> canonical schema violation guarding REQ-STATE-02; an additional `schema`-only case
> (missing required top-level field) is listed in §3.2 prose and should be added as a
> sibling test during implementation.
