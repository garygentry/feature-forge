"""Shared fixtures for the doctor-check tests (``tests/test_doctor_checks*.py``).

Everything here builds a hermetic project under ``tmp_path`` and runs doctor
in a **scrubbed environment**: ``PATH`` is a single throwaway ``bin/`` holding
symlinks to the few real tools doctor's legacy probes need (``git``, ``bash``
and the coreutils ``forge-root.sh`` calls) plus whatever fakes a test installs
(``fake_runner``, ``fake_gh``). ``HOME`` points at an empty directory so no
real install under ``~/.claude`` (or a real ``gh`` config) can leak into a
result, and every env override doctor reads is cleared.

The fake runner and fake gh are Bash scripts, so no Python needs to be on the
scrubbed PATH; each appends its argv to ``$DOCTOR_PROBE_LOG`` when set, which
is how the allowlist test proves doctor spawned nothing it must not.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HELPER = REPO_ROOT / "scripts" / "forge-session.py"
CONFIG_SCHEMA = REPO_ROOT / "references" / "forge-config-schema.json"

#: External tools the legacy report + forge-root.sh need on a scrubbed PATH.
_REAL_TOOLS = ("git", "bash", "dirname", "ls")

#: The literal a fake ``gh auth token`` prints — must never appear in any output.
FAKE_TOKEN = "ghp_FAKE_TOKEN_MUST_NEVER_APPEAR_IN_DOCTOR_OUTPUT"


def scrubbed_env(tmp_path: Path) -> dict[str, str]:
    """A minimal environment: throwaway ``bin/`` on PATH, empty HOME, overrides cleared."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    for tool in _REAL_TOOLS:
        real = shutil.which(tool)
        if real is None:
            pytest.skip(f"{tool} not available")
        link = bin_dir / tool
        if not link.exists():
            link.symlink_to(real)
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = {
        "PATH": str(bin_dir),
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        # Explicitly cleared: forge-root.sh, doctor and the fakes read these.
        "FEATURE_FORGE_ROOT": "",
        "CLAUDE_PLUGIN_ROOT": "",
        "DOCTOR_PROBE_LOG": str(tmp_path / "probes.log"),
    }
    for passthrough in ("SYSTEMROOT", "TMPDIR", "TEMP", "TMP"):
        if passthrough in os.environ:
            env[passthrough] = os.environ[passthrough]
    return env


def bin_dir(env: dict[str, str]) -> Path:
    """The scrubbed ``bin/`` directory an env from ``scrubbed_env`` points at."""
    return Path(env["PATH"])


def fake_runner(
    env: dict[str, str],
    *,
    name: str = "rauf",
    version: str | object = "0.14.0",
    validate_exit: int = 0,
    validate_stdout: str = "",
    version_exit: int = 0,
    hang_seconds: int = 0,
) -> Path:
    """Install a Bash fake of the loop runner on the scrubbed PATH.

    ``version --json`` prints ``{"version": <version>}`` (``version`` may be any
    JSON-encodable value, e.g. a pre-release string) and exits ``version_exit``;
    ``backlog validate …`` prints ``validate_stdout`` and exits ``validate_exit``;
    ``agents --json`` — the ``agentsProbeCommand`` doctor must never run — and
    any other verb exit 97 loudly. ``hang_seconds`` makes every call sleep first
    (for the timeout test).
    """
    payload = json.dumps({"version": version})
    script = bin_dir(env) / name
    script.write_text(
        "#!/usr/bin/env bash\n"
        'if [ -n "${DOCTOR_PROBE_LOG:-}" ]; then printf \'%s\\n\' "$0 $*" '
        '>> "$DOCTOR_PROBE_LOG"; fi\n'
        f"if [ {hang_seconds} -gt 0 ]; then sleep {hang_seconds}; fi\n"
        'case "$1 $2" in\n'
        f"  \"version --json\") printf '%s\\n' '{payload}'; exit {version_exit};;\n"
        f"  \"backlog validate\") printf '%s' '{validate_stdout}'; exit {validate_exit};;\n"
        '  *) echo "fake runner: forbidden or unknown verb: $*" >&2; exit 97;;\n'
        "esac\n"
    )
    script.chmod(0o755)
    return script


def fake_gh(
    env: dict[str, str], *, token_exit: int = 0, version_exit: int = 0,
) -> Path:
    """Install a Bash fake ``gh``: ``--version`` and ``auth token`` only.

    ``auth token`` prints ``FAKE_TOKEN`` (so a leak into evidence is
    detectable) and exits ``token_exit``. ``auth status`` — which doctor must
    never run — and every other verb exit 97 loudly.
    """
    script = bin_dir(env) / "gh"
    script.write_text(
        "#!/usr/bin/env bash\n"
        'if [ -n "${DOCTOR_PROBE_LOG:-}" ]; then printf \'%s\\n\' "$0 $*" '
        '>> "$DOCTOR_PROBE_LOG"; fi\n'
        'case "$1 $2" in\n'
        f"  \"--version \") echo 'gh version 2.93.0 (fake)'; exit {version_exit};;\n"
        f"  \"auth token\") echo '{FAKE_TOKEN}'; exit {token_exit};;\n"
        '  *) echo "fake gh: forbidden or unknown verb: $*" >&2; exit 97;;\n'
        "esac\n"
    )
    script.chmod(0o755)
    return script


def probe_log(env: dict[str, str]) -> list[str]:
    """Every argv line the fakes recorded, in order (empty when nothing ran)."""
    path = Path(env["DOCTOR_PROBE_LOG"])
    if not path.is_file():
        return []
    return [line for line in path.read_text().splitlines() if line]


def pipeline_state(
    done: tuple[str, ...] | list[str] = (),
    *,
    branch: str | None = None,
    in_progress: str | None = None,
    current_stage: str | None = None,
    updated_at: str = "2026-08-01T00:00:00Z",
) -> dict:
    """A minimal ``.pipeline-state.json``: ``done`` stages complete, optional in-progress."""
    stages: dict = {stage: {"status": "complete", "version": 1} for stage in done}
    if in_progress:
        stages[in_progress] = {"status": "in-progress", "version": 1}
    state: dict = {"pipelineStatus": "active", "updatedAt": updated_at, "stages": stages}
    if branch is not None:
        state["branch"] = branch
    if current_stage is not None:
        state["currentStage"] = current_stage
    return state


def write_feature(
    project: Path, name: str, state: dict, *, epic: str | None = None, backlog: bool = False,
) -> Path:
    """Write a feature's state (and optionally an empty ``backlog.json``)."""
    specs = project / "specs"
    feature = specs / epic / name if epic else specs / name
    feature.mkdir(parents=True, exist_ok=True)
    (feature / ".pipeline-state.json").write_text(json.dumps(state))
    if backlog:
        (feature / "backlog.json").write_text(json.dumps({"items": []}))
    return feature


def make_project(
    tmp_path: Path,
    *,
    config: dict | None = None,
    rauf_json: dict | None = None,
    git_branch: str | None = "main",
) -> Path:
    """Create ``tmp_path/project`` with optional config, ``.rauf.json`` and a git repo."""
    project = tmp_path / "project"
    project.mkdir(exist_ok=True)
    (project / "specs").mkdir(exist_ok=True)
    if config is not None:
        (project / "forge.config.json").write_text(json.dumps(config, indent=2))
    if rauf_json is not None:
        (project / ".rauf.json").write_text(json.dumps(rauf_json, indent=2))
    if git_branch is not None:
        # An empty commit so the branch exists as a ref (``_default_branch`` looks
        # for refs/heads/main); ``git_branch`` other than main is then checked out.
        git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=project, check=True)
        subprocess.run(
            [*git, "commit", "-q", "--allow-empty", "-m", "init"], cwd=project, check=True,
        )
        if git_branch != "main":
            subprocess.run(["git", "switch", "-q", "-c", git_branch], cwd=project, check=True)
    return project


def run_doctor(
    project: Path, env: dict[str, str], *extra: str, helper: Path = HELPER,
) -> subprocess.CompletedProcess[str]:
    """Run ``doctor --json`` in ``project`` under ``env``; the caller asserts on it."""
    return subprocess.run(
        [sys.executable, str(helper), "doctor", "--json", *extra],
        capture_output=True, text=True, cwd=str(project), env=env,
    )


def doctor_report(project: Path, env: dict[str, str], *extra: str) -> dict:
    """``run_doctor`` + the always-exit-0 contract + parsed JSON."""
    result = run_doctor(project, env, *extra)
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr, result.stderr
    return json.loads(result.stdout)


def check(report: dict, check_id: str) -> dict:
    """The one ``checks[]`` record with this id."""
    matches = [record for record in report["checks"] if record["id"] == check_id]
    assert len(matches) == 1, f"{check_id}: {len(matches)} records"
    return matches[0]


def warn_ids(report: dict) -> set[str]:
    """The ids of every ``warn`` record."""
    return {record["id"] for record in report["checks"] if record["status"] == "warn"}
