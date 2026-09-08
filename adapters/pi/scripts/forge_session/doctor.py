"""Doctor: pipeline ground-truth capture and the structured health-check registry.

The ``doctor`` verb (``forge-session.py doctor [--json] [--check ID ...]``) and
its registry of best-effort checks — the CLI's self-verifying smoke command
(CHECK-I21). Extracted from the monolith by #279 P4.1 as a PURE MOVE: the verb,
its ``--check`` IDs, its ``--json`` shape, and CHECK-I21 output are FROZEN.

Every shared primitive it needs (readers, config helpers, git access) is imported
FROM ``forge_session._common`` — never from the hyphen-named shim, which would be a
circular import. Stdlib only, 3.10 baseline, Google-style docstrings.

Path anchors: this module ships at ``<scripts>/forge_session/doctor.py`` while the
CLI shim (``forge-session.py``) and its ``forge-root.sh`` resolver sit one level up
in ``<scripts>/``, and the bundle root is one level above that. The legacy report
resolved those anchors from ``forge-session.py``'s own location, so they are
recomputed here relative to this module to keep doctor's output byte-identical.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Callable, Final, NamedTuple

from forge_session._common import (
    PRODUCTION_STAGES,
    _config_duplicate_keys,
    _counts,
    _default_branch,
    _default_schema_path,
    _git_output,
    _load_config,
    _loop_runner_defaults,
    build_rows,
    invalid_auto_verify_keys,
    load_json_with_duplicates,
)

#: This module lives at ``<scripts>/forge_session/doctor.py``; ``_SCRIPTS_DIR`` is
#: ``<scripts>/`` (where the CLI shim + ``forge-root.sh`` live), ``_SHIM_PATH`` is
#: the CLI entry point an operator remedy shells out to, and ``_BUNDLE_ROOT`` is the
#: install root the plugin resolver compares against. Recomputed from this module's
#: location so every legacy ``Path(__file__)`` anchor keeps its original target.
_SCRIPTS_DIR: Final = Path(__file__).resolve().parent.parent
_SHIM_PATH: Final = _SCRIPTS_DIR / "forge-session.py"
_BUNDLE_ROOT: Final = _SCRIPTS_DIR.parent

#: The runner version that first supports recovery-answer injection — the apply
#: surface doctor reports. Distinct from ``loopRunner.minRunnerVersion`` (the launch
#: floor): this one only DEGRADES the reported surface, never hard-stops.
RECOVERY_MIN_RUNNER_VERSION: Final[str] = "0.14.0"


def _resolve_plugin_root() -> dict:
    """Resolve the plugin root by running the sibling ``forge-root.sh``.

    Uses the resolver that ships next to this script, so the answer reflects
    the install this helper actually belongs to — exactly what a skill's
    bootstrap prelude would find (or fail to find). On success the dict also
    carries the root's ``version`` (from ``.claude-plugin/plugin.json`` or the
    neutral ``.feature-forge-bundle.json``) and, when the root is a git
    checkout, its short ``commit`` — enough to spot version skew between the
    resolved root and the skills a session loaded.
    """
    resolver = _SCRIPTS_DIR / "forge-root.sh"
    if not resolver.is_file():
        return {"resolved": False, "error": f"resolver not found: {resolver}"}
    try:
        proc = subprocess.run(
            ["bash", str(resolver)], capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"resolved": False, "error": str(exc)}
    if proc.returncode != 0:
        return {
            "resolved": False,
            "error": proc.stderr.strip() or f"resolver exited {proc.returncode}",
        }
    root = proc.stdout.strip()
    info: dict = {"resolved": True, "root": root}
    bundle = _bundle_version(Path(root))
    if bundle["version"] is not None:
        info["version"] = bundle["version"]
    if bundle["manifest"] is not None:
        info["manifest"] = bundle["manifest"]
    commit = _git_output(["-C", root, "rev-parse", "--short", "HEAD"])
    if commit:
        info["commit"] = commit
    return info


def _bundle_version(root: Path) -> dict:
    """Read a candidate root's bundle manifest for its declared version.

    Probes ``.claude-plugin/plugin.json`` then the neutral
    ``.feature-forge-bundle.json`` (the same two sentinels ``forge-root.sh``
    accepts) and returns ``{"version", "manifest"}`` — either may be ``None``
    when no manifest exists or it declares no string version.
    """
    for rel in (".claude-plugin/plugin.json", ".feature-forge-bundle.json"):
        manifest = root / rel
        if manifest.is_file():
            version = _load_config(manifest).get("version")
            return {
                "version": version if isinstance(version, str) else None,
                "manifest": rel,
            }
    return {"version": None, "manifest": None}


def _backlog_path(config: dict, name: str, epic: str | None, specs_dir: Path) -> Path:
    """Compose a feature's backlog.json path per the forge-4-backlog rule.

    ``{backlogDir}/{feature}/backlog.json`` when ``backlogDir`` is configured,
    else ``{resolvedFeatureDir}/backlog.json`` (flat or nested under the epic).
    """
    backlog_dir = config.get("backlogDir")
    if isinstance(backlog_dir, str) and backlog_dir:
        return Path(backlog_dir) / name / "backlog.json"
    feature_dir = specs_dir / epic / name if epic else specs_dir / name
    return feature_dir / "backlog.json"


def doctor_report(
    specs_dir: Path,
    config_path: Path,
    *,
    schema_path: Path | None = None,
    only: frozenset[str] | None = None,
) -> dict:
    """Assemble the ground-truth diagnostic payload (always succeeds).

    One snapshot of everything a confused session needs checked: resolved
    plugin root + version/commit, current git branch vs. each feature's
    recorded state branch, the recency-ranked feature summary, and whether
    each feature's composed backlog path exists on disk.

    The eleven legacy keys come first and are unchanged; after them the
    structured ``checks[]`` (one record per ``DOCTOR_CHECKS`` entry, or the
    ``only`` subset), their ``checksSummary`` counts, and the ``remedyClusters``
    grouped by remedy command. A crash anywhere in the check driver degrades
    every requested check to ``na`` — the legacy payload is never lost.

    Args:
        specs_dir: The specs directory to scan.
        config_path: Path to ``forge.config.json``.
        schema_path: Override for the bundled ``forge-config-schema.json``
            (defaults to the sibling ``references/`` copy).
        only: When given, run just these check ids (others are omitted).
    """
    config = _load_config(config_path)
    # --show-current (not rev-parse HEAD) so an unborn branch (fresh repo,
    # no commits yet) still reports its name instead of failing.
    current_branch = _git_output(["branch", "--show-current"])
    default_branch = _default_branch()
    specs_error: str | None = None
    try:
        rows = build_rows(specs_dir, config)
        counts = _counts(specs_dir)
    except (OSError, ValueError, RecursionError) as exc:  # unlistable dir, absurd nesting
        rows, counts = [], {"active": 0, "paused": 0, "abandoned": 0}
        specs_error = _exc_text(exc)
    features = []
    for row in rows:
        backlog = _backlog_path(config, row["name"], row["epic"], specs_dir)
        state_branch = row["branch"]
        mismatch = bool(state_branch and current_branch and state_branch != current_branch)
        # Classify a mismatch: on a topic branch it is adoptable (imposed/session-branch
        # drift, Chunk 6); on the default branch it is real drift-back, only a warning.
        branch_reconcile = None
        if mismatch:
            branch_reconcile = "warn-drift" if current_branch == default_branch else "adopt-current"
        features.append({
            "name": row["name"],
            "epic": row["epic"],
            "currentStage": row["currentStage"],
            "nextStage": row["nextStage"],
            "verifyState": row["verifyState"],
            "stateBranch": state_branch,
            "branchMatchesState": (
                state_branch == current_branch
                if state_branch and current_branch
                else None
            ),
            "branchReconcile": branch_reconcile,
            "backlogPath": str(backlog),
            "backlogExists": backlog.is_file(),
        })
    plugin_root = _resolve_plugin_root()
    report = {
        "pluginRoot": plugin_root,
        "currentBranch": current_branch,
        "specsDir": str(specs_dir),
        "specsDirExists": specs_dir.is_dir(),
        "configPath": str(config_path),
        "configExists": config_path.is_file(),
        "counts": counts,
        "features": features,
        "invalidAutoVerifyKeys": invalid_auto_verify_keys(config),
        "duplicateConfigKeys": _config_duplicate_keys(config_path),
        "rootSandbox": _root_sandbox_status(),
    }
    specs = [spec for spec in DOCTOR_CHECKS if only is None or spec.id in only]
    try:
        ctx = _build_check_context(
            specs_dir,
            config_path,
            schema_path or _default_schema_path(),
            config=config,
            current_branch=current_branch,
            default_branch=default_branch,
            rows=rows,
            features=features,
            plugin_root=plugin_root,
        )
        checks = _run_checks(ctx, specs)
    except Exception as exc:  # INV-3: doctor never crashes
        checks = [
            _check_record(
                spec.id, "na", spec.severity, f"check driver crashed: {_exc_text(exc)}",
            )
            for spec in specs
        ]
    if specs_error is not None:  # only on the failure path: happy-path keys unchanged
        report["specsDirError"] = specs_error
    report["checks"] = checks
    report["checksSummary"] = _checks_summary(checks)
    report["remedyClusters"] = cluster_checks(checks)
    return report


def _root_sandbox_status() -> dict:
    """Report the root/sandbox launch condition for forge-5-loop (issue #99).

    On a hosted remote (e.g. Claude.ai) the loop runs as root, where rauf's
    ``claude --dangerously-skip-permissions`` is refused unless ``IS_SANDBOX``
    is set. forge-5-loop exports ``IS_SANDBOX=${IS_SANDBOX:-1}`` at launch when
    root; this surfaces the same condition as a diagnosable check. ``geteuid``
    is absent on Windows — treat that as non-root.
    """
    geteuid = getattr(os, "geteuid", None)
    is_root = geteuid() == 0 if geteuid is not None else False
    is_sandbox_set = os.environ.get("IS_SANDBOX") not in (None, "")
    return {
        "isRoot": is_root,
        "isSandboxSet": is_sandbox_set,
        # True only when the loop would need to supply the default at launch.
        "loopWillSetSandbox": is_root and not is_sandbox_set,
    }


# --------------------------------------------------------------------------- #
# Doctor checks (roadmap/self-healing-resilience.md §5; catalog: docs/doctor-checks.md)
# --------------------------------------------------------------------------- #
#
# Each check is a pure function ``(ctx) -> dict`` registered in ``DOCTOR_CHECKS``.
# The driver stamps ``id``/``severity``, isolates crashes (a raising check becomes
# ``na`` with the exception in ``detail`` — it never takes doctor down), demotes any
# ``fail`` from a check outside ``FAIL_PROMOTED_CHECK_IDS`` to ``warn`` (INV-1:
# warn-only until the promotion pass) and clusters remedies by command. Doctor
# still always exits 0 (INV-3); remedies are DATA (INV-4) — doctor never runs one.
#
# Subprocess allowlist — the only commands a check may spawn, all read-only:
#   * ``git`` queries and ``bash forge-root.sh`` (already part of the legacy report),
#   * ``{bin} version --json`` (once, memoised on the context),
#   * ``{bin} backlog validate …`` (at most once per distinct backlog dir),
#   * ``gh --version`` and ``gh auth token`` (stdout discarded, never logged).
# Never ``agentsProbeCommand``, ``gh auth status``, ``rauf update --check``, nor any
# ``remedy.command``.

CHECK_STATUSES: Final[tuple[str, ...]] = ("ok", "warn", "fail", "na")
CHECK_SEVERITIES: Final[tuple[str, ...]] = ("blocking", "advisory")
#: Ordered least → most consequential; a merged remedy carries the highest tier.
REMEDY_SAFETY_TIERS: Final[tuple[str, ...]] = (
    "read-only", "local-write", "global-install", "network",
)
#: Check ids allowed to emit ``fail``. Empty until the promotion pass; the driver
#: demotes every other ``fail`` to ``warn`` so no check can block by accident.
FAIL_PROMOTED_CHECK_IDS: Final[frozenset[str]] = frozenset()
#: Check ids whose result is never ``na`` — they hold in every environment.
NO_NA_CHECKS: Final[frozenset[str]] = frozenset({"plugin-root", "gh-available"})
_CHECK_ID_RE: Final = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
#: Wall-clock cap per probe; a stuck runner degrades to ``warn``, never a hang.
_PROBE_TIMEOUT_S: Final[int] = 10
#: Evidence carries at most this many characters of any probe stream.
_PROBE_OUTPUT_CAP: Final[int] = 400

#: The launcher-stamped interaction contract (#244 P3.5, roadmap D2a). A launcher
#: that KNOWS the session it is spawning has no reply channel states it here;
#: feature-forge only ever READS this variable, never sets or exports it. Values
#: are ``INTERACTION_MODES``; anything else is reported as ``unknown`` with the
#: raw value as evidence. Named without ``KEY``/``SECRET``/``TOKEN`` so no host's
#: environment policy strips it before the session sees it (verified on Codex).
INTERACTION_ENV_VAR: Final[str] = "FORGE_INTERACTION"
#: Every adapter id ``scripts/build-adapters.py`` emits; the bundle sentinel's
#: ``agent`` must be one of these to be trusted. Mirrored (not imported — this
#: file is copied verbatim into each bundle) and pinned by a parity test.
_ADAPTER_AGENT_IDS: Final[frozenset[str]] = frozenset(
    {"claude", "codex", "copilot", "cursor", "gemini", "pi"}
)
INTERACTION_MODES: Final[tuple[str, ...]] = ("interactive", "non-interactive")
#: Harness binaries whose argv in process ancestry is a VERIFIED mode signal.
#: Deliberately excludes Codex: its shell tool executes under a long-lived,
#: init-parented ``app-server`` daemon that predates the session, so the nearest
#: ``codex`` ancestor describes the DAEMON's launch mode, not this session's
#: (#261 spike). Inferring from it would confidently report the wrong mode — the
#: one failure the ``unknown``-never-``non-interactive`` rule exists to prevent.
_ANCESTRY_MODE_HARNESSES: Final[frozenset[str]] = frozenset({"claude", "pi"})
#: Harness binaries recognised in ancestry for the HOST axis only. A ``codex``
#: ancestor does identify the host (the daemon is Codex's); only its mode is
#: unreadable. ``cursor-agent`` is the binary; ``cursor`` is the adapter id.
_ANCESTRY_HOSTS: Final[tuple[tuple[str, str], ...]] = (
    ("claude", "claude"), ("pi", "pi"), ("codex", "codex"),
    ("cursor-agent", "cursor"), ("copilot", "copilot"), ("gemini", "gemini"),
)
#: argv flags that put a recognised harness into print/headless mode.
_HEADLESS_FLAGS: Final[frozenset[str]] = frozenset({"-p", "--print"})
#: argv flags that RESTORE a reply channel to an otherwise-headless invocation.
#: Claude's SDK streaming mode (``--print --input-format stream-json``) is
#: bidirectional and its host CAN answer, so ``--print`` alone does not prove
#: "nobody is there". Presence of any of these withdraws the headless claim.
_REPLY_CHANNEL_FLAGS: Final[frozenset[str]] = frozenset(
    {"--input-format", "--permission-prompt-tool"}
)
#: Depth cap on the ancestry walk — a guard, not a tuning knob.
_ANCESTRY_MAX_DEPTH: Final[int] = 16
#: A plausible executable basename. Anything else is redacted to ``?`` before it
#: reaches evidence: a process whose ``argv[0]`` is descriptive text rather than
#: a path (``sshd: gary@pts/6``, kernel threads) can carry a username, and every
#: evidence field lands in ``doctor --json`` output that gets pasted into issues.
_EXEC_NAME_RE: Final = re.compile(r"^[A-Za-z0-9._+-]{1,64}$")
#: Adapter ids that keep their own ``--host`` value; every other id is generic.
_NAMED_HOST_ARGS: Final[frozenset[str]] = frozenset({"claude", "pi"})


def _remedy(description: str, command: str | None, safety: str) -> dict:
    """Build a remedy record — advice as data, in the fixed key order.

    Raises:
        ValueError: ``safety`` is not one of ``REMEDY_SAFETY_TIERS`` (the driver
            turns that into an ``na`` record for the offending check).
    """
    if safety not in REMEDY_SAFETY_TIERS:
        raise ValueError(f"unknown remedy safety tier: {safety!r}")
    return {"description": description, "command": command, "safety": safety}


def _result(
    status: str, detail: str, evidence: dict | None = None, remedy: dict | None = None,
) -> dict:
    """The id-less payload a check returns; the driver stamps id and severity."""
    return {"status": status, "detail": detail, "evidence": evidence, "remedy": remedy}


def _check_record(
    check_id: str,
    status: str,
    severity: str,
    detail: str,
    evidence: dict | None = None,
    remedy: dict | None = None,
) -> dict:
    """Build one validated ``checks[]`` record in the fixed key order.

    Raises:
        ValueError: A field is outside its enum or a remedy is malformed.
    """
    if status not in CHECK_STATUSES:
        raise ValueError(f"unknown check status: {status!r}")
    if severity not in CHECK_SEVERITIES:
        raise ValueError(f"unknown check severity: {severity!r}")
    if remedy is not None:
        if (
            not isinstance(remedy, dict)
            or set(remedy) != {"description", "command", "safety"}
            or not isinstance(remedy["description"], str)
            or not (remedy["command"] is None or isinstance(remedy["command"], str))
        ):
            raise ValueError(f"malformed remedy: {remedy!r}")
        remedy = _remedy(remedy["description"], remedy["command"], remedy["safety"])
    if evidence is not None and not isinstance(evidence, dict):
        raise ValueError("evidence must be an object or null")
    return {
        "id": check_id,
        "status": status,
        "severity": severity,
        "detail": str(detail),
        "evidence": evidence,
        "remedy": remedy,
    }


def _exc_text(exc: BaseException) -> str:
    """One capped line naming an exception, for a ``detail`` field."""
    return _head(f"{type(exc).__name__}: {exc}")


def _head(text: object) -> str:
    """The first ``_PROBE_OUTPUT_CAP`` characters of a probe stream, whitespace-trimmed."""
    text = str(text or "").strip()
    return text if len(text) <= _PROBE_OUTPUT_CAP else text[:_PROBE_OUTPUT_CAP] + "…"


def _run_probe(
    argv: list[str], *, cwd: Path | None = None, discard_stdout: bool = False,
) -> dict:
    """Run one allowlisted read-only probe with a timeout; never raises.

    Returns a dict ``{ok, returncode, stdout, stderr, error, timedOut}``.
    ``discard_stdout`` sends the child's stdout to ``/dev/null`` so it never
    enters this process — used for ``gh auth token``, whose output is a
    credential.
    """
    result: dict = {
        "ok": False, "returncode": None, "stdout": "", "stderr": "",
        "error": None, "timedOut": False,
    }
    try:
        proc = subprocess.run(
            argv,
            stdout=subprocess.DEVNULL if discard_stdout else subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=_PROBE_TIMEOUT_S,
            cwd=str(cwd) if cwd is not None else None,
        )
    except subprocess.TimeoutExpired:
        result["timedOut"] = True
        result["error"] = f"timed out after {_PROBE_TIMEOUT_S}s"
        return result
    except (OSError, ValueError) as exc:
        result["error"] = str(exc)
        return result
    result["ok"] = proc.returncode == 0
    result["returncode"] = proc.returncode
    result["stdout"] = proc.stdout or ""
    result["stderr"] = proc.stderr
    return result


def _render_runner_command(template: str, loop_runner: dict, **tokens: object) -> list[str] | None:
    """Render a ``loopRunner`` command template into argv (``{bin}`` + ``tokens``).

    Every substituted value is ``shlex.quote``d so a path with spaces survives
    the split. Returns ``None`` when the template does not start with ``{bin}``
    (doctor only ever invokes the configured runner binary — a template whose
    first word is anything else is reported as data, never run), when a
    ``{token}`` remains unrendered, or when the result does not split.
    """
    if not template.lstrip().startswith("{bin}"):
        return None
    values: dict[str, object] = {"bin": loop_runner.get("bin") or "", **tokens}
    unrendered = False

    def substitute(match: re.Match) -> str:
        nonlocal unrendered
        key = match.group(1)
        if key not in values:
            unrendered = True
            return match.group(0)
        return shlex.quote(str(values[key]))

    # One pass over the template: a substituted value is opaque and is never
    # re-scanned for a later token (``bin = "run-{backlogDir}"`` stays literal).
    rendered = re.sub(r"\{([A-Za-z][A-Za-z0-9_]*)\}", substitute, template)
    if unrendered:
        return None
    try:
        argv = shlex.split(rendered)
    except ValueError:
        return None
    # argv[0] must be the configured runner binary *exactly*: ``{bin}5.34`` or
    # ``{bin}/../x`` would otherwise swap in a different executable.
    if not argv or argv[0] != str(values["bin"]):
        return None
    return argv


_SEMVER_NUM: Final = r"(0|[1-9]\d*)"  # SemVer 2.0: no leading zeros
_SEMVER_RE: Final = re.compile(rf"^\s*v?{_SEMVER_NUM}\.{_SEMVER_NUM}\.{_SEMVER_NUM}\s*$")
_INSTALLED_BY_RE: Final = re.compile(
    rf"^\s*([A-Za-z0-9._-]+)@v?({_SEMVER_NUM}\.{_SEMVER_NUM}\.{_SEMVER_NUM})\s*$"
)


def _parse_semver(text: object) -> tuple[int, int, int] | None:
    """``"1.2.3"`` (optional ``v``) → ``(1, 2, 3)``; anything else → ``None``.

    A pre-release/build suffix is deliberately ``None``: the check reports it as
    unparseable rather than guessing an ordering.
    """
    if not isinstance(text, str):
        return None
    match = _SEMVER_RE.match(text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def _fmt_semver(version: tuple[int, int, int]) -> str:
    """``(1, 2, 3)`` → ``"1.2.3"``."""
    return ".".join(str(part) for part in version)


def _parse_installed_by(text: object) -> tuple[str, tuple[int, int, int]] | None:
    """``"rauf-manager@0.13.0"`` → ``("rauf-manager", (0, 13, 0))``; else ``None``."""
    if not isinstance(text, str):
        return None
    match = _INSTALLED_BY_RE.match(text)
    if not match:
        return None
    version = _parse_semver(match.group(2))
    return (match.group(1), version) if version else None


def _first_backticked(text: object) -> str | None:
    """The first `` `span` `` in a hint string, or ``None`` — the hint's command."""
    if not isinstance(text, str):
        return None
    match = re.search(r"`([^`]+)`", text)
    return match.group(1).strip() if match else None


_JSON_SCHEMA_TYPES: Final[dict[str, type | tuple[type, ...]]] = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "null": type(None),
}


def _schema_violations(node: object, schema: dict, schema_root: dict, path: str) -> list[str]:
    """Structural JSON-Schema check (the draft-07 subset forge's schemas use).

    A port of ``tests/_state_schema.py::_check`` — ``type``, ``required``,
    ``properties``, ``enum``, ``items``, ``additionalProperties``, ``minimum``/
    ``maximum`` and same-file ``$ref`` — so doctor can validate a config with
    the stdlib only. Returns human-readable violations; empty means valid.
    """
    out: list[str] = []
    if "$ref" in schema:
        ref = str(schema["$ref"]).split("/")[-1]
        target = schema_root.get("definitions", {}).get(ref)
        if not isinstance(target, dict):
            return [f"{path}: unresolvable $ref {schema['$ref']!r}"]
        schema = target

    declared = schema.get("type")
    if declared:
        names = [declared] if isinstance(declared, str) else list(declared)
        allowed = tuple(_JSON_SCHEMA_TYPES[n] for n in names if n in _JSON_SCHEMA_TYPES)
        flat: tuple[type, ...] = tuple(
            t for entry in allowed for t in (entry if isinstance(entry, tuple) else (entry,))
        )
        # `bool` is a subclass of `int` in Python; a boolean is not an integer here.
        if flat and (
            not isinstance(node, flat) or (isinstance(node, bool) and bool not in flat)
        ):
            return [f"{path}: expected {declared}, got {type(node).__name__}"]

    if schema.get("enum") is not None and node not in schema["enum"]:
        out.append(f"{path}: {node!r} not in enum {schema['enum']}")

    if isinstance(node, (int, float)) and not isinstance(node, bool):
        if "minimum" in schema and node < schema["minimum"]:
            out.append(f"{path}: {node!r} below minimum {schema['minimum']}")
        if "maximum" in schema and node > schema["maximum"]:
            out.append(f"{path}: {node!r} above maximum {schema['maximum']}")

    if isinstance(node, dict):
        for req in schema.get("required", []):
            if req not in node:
                out.append(f"{path}: missing required '{req}'")
        props = schema.get("properties", {})
        extra = schema.get("additionalProperties")
        for key, value in node.items():
            if key in props:
                out += _schema_violations(value, props[key], schema_root, f"{path}.{key}")
            elif extra is False:
                out.append(f"{path}: unexpected key '{key}'")
            elif isinstance(extra, dict):
                out += _schema_violations(value, extra, schema_root, f"{path}.{key}")

    if isinstance(node, list) and isinstance(schema.get("items"), dict):
        for index, item in enumerate(node):
            out += _schema_violations(item, schema["items"], schema_root, f"{path}[{index}]")

    return out


def _stage_at_or_after(stage: str | None, floor: str) -> bool:
    """True when ``stage`` (a ``nextStage``; ``None`` = complete) is at/after ``floor``."""
    if stage is None:
        return True
    if stage not in PRODUCTION_STAGES:
        return False
    return PRODUCTION_STAGES.index(stage) >= PRODUCTION_STAGES.index(floor)


class _CheckContext:
    """Everything a check may read. Probes are memoised so each runs at most once.

    A plain class (not a dataclass): the test suite imports this file through
    ``importlib`` without registering it in ``sys.modules``, which breaks
    dataclass annotation resolution under ``from __future__ import annotations``.
    """

    def __init__(
        self,
        *,
        cwd: Path,
        specs_dir: Path,
        config_path: Path,
        config_exists: bool,
        config: dict,
        schema_path: Path,
        schema: dict | None,
        schema_error: str | None,
        loop_runner: dict | None,
        loop_runner_defaults: dict | None,
        loop_runner_error: str | None,
        plugin_root: dict,
        current_branch: str | None,
        default_branch: str | None,
        rows: list,
        features: list,
    ) -> None:
        self.cwd = cwd
        self.specs_dir = specs_dir
        self.config_path = config_path
        self.config_exists = config_exists
        self.config = config
        self.schema_path = schema_path
        self.schema = schema
        self.schema_error = schema_error
        self.loop_runner = loop_runner
        self.loop_runner_defaults = loop_runner_defaults
        self.loop_runner_error = loop_runner_error
        self.plugin_root = plugin_root
        self.current_branch = current_branch
        self.default_branch = default_branch
        self.rows = rows
        self.features = features
        self._memo: dict = {}

    def runner_bin(self) -> str:
        """The configured ``loopRunner.bin`` (``""`` when unavailable)."""
        value = (self.loop_runner or {}).get("bin")
        return value if isinstance(value, str) else ""

    def runner_bin_path(self) -> str | None:
        """``shutil.which`` of the runner binary, memoised."""
        if "bin_path" not in self._memo:
            name = self.runner_bin()
            self._memo["bin_path"] = shutil.which(name) if name else None
        return self._memo["bin_path"]

    def runner_version_probe(self) -> dict | None:
        """Run ``versionCommand`` once; ``None`` when it cannot be rendered/run."""
        if "version_probe" not in self._memo:
            probe = None
            if self.loop_runner and self.runner_bin_path():
                template = self.loop_runner.get("versionCommand")
                argv = (
                    _render_runner_command(template, self.loop_runner)
                    if isinstance(template, str) else None
                )
                if argv:
                    probe = _run_probe(argv, cwd=self.cwd)
            self._memo["version_probe"] = probe
        return self._memo["version_probe"]

    def runner_version(self) -> tuple[int, int, int] | None:
        """The live runner's parsed semver from the version probe, or ``None``."""
        probe = self.runner_version_probe()
        if not probe or not probe["ok"]:
            return None
        try:
            payload = json.loads(probe["stdout"])
        except ValueError:
            return None
        return _parse_semver(payload.get("version")) if isinstance(payload, dict) else None

    def precondition_path(self) -> Path | None:
        """``cwd / loopRunner.preconditionFile`` (e.g. ``.rauf.json``), or ``None``."""
        name = (self.loop_runner or {}).get("preconditionFile")
        return self.cwd / name if isinstance(name, str) and name else None

    def precondition(self) -> dict | None:
        """The parsed precondition file: ``None`` when absent, ``{}`` when unreadable."""
        if "precondition" not in self._memo:
            path = self.precondition_path()
            parsed: dict | None = None
            if path is not None and path.is_file():
                try:
                    value, _dupes = load_json_with_duplicates(path)
                except (OSError, ValueError, RecursionError):  # JSON *and* UTF-8 decode errors
                    value = {}
                parsed = value if isinstance(value, dict) else {}
            self._memo["precondition"] = parsed
        return self._memo["precondition"]

    def runner_relevant(self) -> bool:
        """True once any active feature's next stage is forge-4-backlog or later."""
        return any(_stage_at_or_after(row["nextStage"], "forge-4-backlog") for row in self.rows)


def _build_check_context(
    specs_dir: Path,
    config_path: Path,
    schema_path: Path,
    *,
    config: dict,
    current_branch: str | None,
    default_branch: str | None,
    rows: list,
    features: list,
    plugin_root: dict,
) -> _CheckContext:
    """Assemble the shared check context from values the legacy report computed.

    The config schema and the resolved ``loopRunner`` block are loaded here
    with every failure captured as data (``schema_error`` /
    ``loop_runner_error``) — ``_loop_runner_defaults`` raises ``UsageError``
    on a damaged schema, which would otherwise map to exit 2.
    """
    schema: dict | None = None
    schema_error: str | None = None
    try:
        loaded = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        schema_error = _exc_text(exc)
    else:
        if isinstance(loaded, dict):
            schema = loaded
        else:
            schema_error = "schema top level is not an object"
    defaults: dict | None = None
    loop_runner: dict | None = None
    loop_runner_error: str | None = None
    try:
        defaults = dict(_loop_runner_defaults(schema_path))
    except Exception as exc:  # captured as data (INV-3)
        loop_runner_error = _exc_text(exc)
    else:
        # The same flat override resolve_loop_runner applies, without re-reading
        # (and re-warning about) the config the legacy report already loaded.
        loop_runner = dict(defaults)
        user_block = config.get("loopRunner")
        if isinstance(user_block, dict):
            loop_runner.update(user_block)
    return _CheckContext(
        cwd=Path.cwd(),
        specs_dir=specs_dir,
        config_path=config_path,
        config_exists=config_path.is_file(),
        config=config,
        schema_path=schema_path,
        schema=schema,
        schema_error=schema_error,
        loop_runner=loop_runner,
        loop_runner_defaults=defaults,
        loop_runner_error=loop_runner_error,
        plugin_root=plugin_root,
        current_branch=current_branch,
        default_branch=default_branch,
        rows=rows,
        features=features,
    )


class _CheckSpec(NamedTuple):
    """One registry entry: a stable id, its severity, and the check function."""

    id: str
    severity: str
    run: Callable[[_CheckContext], dict]


def _make_spec(check_id: str, severity: str, run: Callable[[_CheckContext], dict]) -> _CheckSpec:
    """Validate and build a ``_CheckSpec`` (ids are kebab-case; severity enumerated)."""
    if not _CHECK_ID_RE.match(check_id):
        raise ValueError(f"invalid check id: {check_id!r}")
    if severity not in CHECK_SEVERITIES:
        raise ValueError(f"invalid severity for {check_id}: {severity!r}")
    return _CheckSpec(check_id, severity, run)


def _per_feature_remedy(rows: list[dict]) -> dict | None:
    """Top-level remedy for a per-feature check from its ``features[]`` rows.

    The rows' remedy when every affected row agrees (typically one affected
    feature), else a "per-feature" pointer carrying the most conservative tier
    so a consumer never runs one feature's command for another.
    """
    remedies = [row["remedy"] for row in rows if row.get("remedy")]
    if not remedies:
        return None
    if len({json.dumps(r, sort_keys=True) for r in remedies}) == 1:
        return dict(remedies[0])
    tier = max(remedies, key=lambda r: REMEDY_SAFETY_TIERS.index(r["safety"]))["safety"]
    return _remedy("per-feature — see evidence.features[].remedy", None, tier)


def _feature_label(feat: dict) -> str:
    """``name`` or ``name [epic]`` for detail strings."""
    return feat["name"] + (f" [{feat['epic']}]" if feat.get("epic") else "")


def _check_plugin_root(ctx: _CheckContext) -> dict:
    """The sibling ``forge-root.sh`` resolves an install root (never ``na``)."""
    root = ctx.plugin_root
    evidence = dict(root)
    if root.get("resolved"):
        version = root.get("version")
        suffix = f" (version {version})" if version else " (no version manifest)"
        return _result("ok", f"resolved {root.get('root')}{suffix}", evidence)
    return _result(
        "warn",
        f"plugin root unresolved: {root.get('error', 'unknown')}",
        evidence,
        _remedy(
            "Reinstall feature-forge for this host (setup guide: "
            "https://raw.githubusercontent.com/garygentry/feature-forge/main/AGENTS-SETUP.md) "
            "or set FEATURE_FORGE_ROOT to the bundle directory",
            None,
            "global-install",
        ),
    )


def _runner_unavailable(ctx: _CheckContext) -> dict | None:
    """The shared ``na`` result when the resolved ``loopRunner`` block is missing."""
    if ctx.loop_runner is None:
        return _result(
            "na", f"loopRunner config unavailable: {ctx.loop_runner_error}",
            {"schemaPath": str(ctx.schema_path), "error": ctx.loop_runner_error},
        )
    return None


_NETWORK_FETCH_RE: Final = re.compile(
    r"\b(npx|npm|pnpm|yarn|pip|pipx|cargo|brew|apt(-get)?|curl|wget)\b|https?://"
)


def _install_remedy(ctx: _CheckContext) -> dict:
    """The schema's ``installHint`` as a remedy (command = its first backticked span).

    Tier is the most conservative that applies: ``network`` when the hint
    fetches from a registry or URL (the default ``npx …`` hint does), else
    ``global-install``.
    """
    hint = (ctx.loop_runner or {}).get("installHint")
    description = hint if isinstance(hint, str) and hint else "Install the loop runner"
    tier = "network" if _NETWORK_FETCH_RE.search(description) else "global-install"
    return _remedy(description, _first_backticked(hint), tier)


def _check_runner_binary(ctx: _CheckContext) -> dict:
    """``loopRunner.bin`` resolves on PATH.

    A customised ``bin`` that is missing while the schema default *is* on PATH
    points at the config, not the install: that remedy is a config edit
    (``local-write``), never the install hint (G4).
    """
    if (na := _runner_unavailable(ctx)) is not None:
        return na
    name = ctx.runner_bin()
    default_bin = (ctx.loop_runner_defaults or {}).get("bin")
    customized = name != default_bin
    path = ctx.runner_bin_path()
    default_path = (
        shutil.which(default_bin) if customized and isinstance(default_bin, str) else None
    )
    evidence = {
        "bin": name,
        "path": path,
        "defaultBin": default_bin,
        "customized": customized,
        "defaultOnPath": default_path,
        "pathEntries": len([p for p in os.environ.get("PATH", "").split(os.pathsep) if p]),
    }
    if path:
        return _result("ok", f"'{name}' found at {path}", evidence)
    if not name:
        return _result(
            "warn", "loopRunner.bin is empty — no runner binary to look for", evidence,
            _remedy("Set loopRunner.bin in forge.config.json to the runner binary", None,
                    "local-write"),
        )
    if customized and default_path:
        return _result(
            "warn",
            f"configured runner '{name}' is not on PATH, but the default '{default_bin}' is "
            f"({default_path})",
            evidence,
            _remedy(
                f"Set loopRunner.bin back to '{default_bin}' in forge.config.json, or install "
                f"'{name}' on PATH",
                None,
                "local-write",
            ),
        )
    if customized:
        return _result(
            "warn", f"configured runner '{name}' is not on PATH", evidence,
            _remedy(
                f"Install '{name}' on PATH, or point loopRunner.bin at a binary that is",
                None, "global-install",
            ),
        )
    return _result("warn", f"runner '{name}' is not installed (not on PATH)", evidence,
                   _install_remedy(ctx))


def _check_runner_version(ctx: _CheckContext) -> dict:
    """The live runner's ``version --json`` meets ``minRunnerVersion``."""
    if (na := _runner_unavailable(ctx)) is not None:
        return na
    if not ctx.runner_bin_path():
        return _result("na", "runner binary not on PATH (see runner-binary)",
                       {"bin": ctx.runner_bin()})
    required_text = ctx.loop_runner.get("minRunnerVersion")
    template = ctx.loop_runner.get("versionCommand")
    argv = _render_runner_command(template, ctx.loop_runner) if isinstance(template, str) else None
    evidence: dict = {
        "bin": ctx.runner_bin(),
        "command": shlex.join(argv) if argv else template,
        "required": required_text,
        "reported": None,
        "exitCode": None,
        "timedOut": False,
        "stdoutHead": "",
        "stderrHead": "",
        "recoveryApplySurface": RECOVERY_MIN_RUNNER_VERSION,
    }
    if argv is None:
        return _result("na", f"versionCommand cannot be rendered: {template!r}", evidence)
    probe = ctx.runner_version_probe()
    if probe is None:
        return _result("na", "version probe did not run", evidence)
    evidence.update(
        exitCode=probe["returncode"], timedOut=probe["timedOut"],
        stdoutHead=_head(probe["stdout"]), stderrHead=_head(probe["stderr"] or probe["error"]),
    )
    if not probe["ok"]:
        why = probe["error"] or f"exit {probe['returncode']}"
        return _result(
            "warn", f"'{evidence['command']}' failed ({why})", evidence,
            _remedy("Reinstall the loop runner so its version command runs", None,
                    "global-install"),
        )
    try:
        payload = json.loads(probe["stdout"])
    except ValueError:
        payload = None
    reported_text = payload.get("version") if isinstance(payload, dict) else None
    evidence["reported"] = reported_text
    reported = _parse_semver(reported_text)
    if reported is None:
        return _result(
            "warn",
            f"could not parse a semver from '{evidence['command']}' output "
            f"(version={reported_text!r})",
            evidence,
            _install_remedy(ctx),
        )
    required = _parse_semver(required_text)
    if required is None:
        return _result(
            "warn", f"minRunnerVersion {required_text!r} is not a plain semver", evidence,
            _remedy("Fix loopRunner.minRunnerVersion in forge.config.json (X.Y.Z)", None,
                    "local-write"),
        )
    if reported < required:
        return _result(
            "warn",
            f"runner {_fmt_semver(reported)} is below minRunnerVersion {_fmt_semver(required)}",
            evidence,
            _install_remedy(ctx),
        )
    return _result(
        "ok", f"runner {_fmt_semver(reported)} >= minRunnerVersion {_fmt_semver(required)}",
        evidence,
    )


def _check_runner_wired(ctx: _CheckContext) -> dict:
    """``loopRunner.preconditionFile`` exists once a feature needs the runner."""
    if (na := _runner_unavailable(ctx)) is not None:
        return na
    path = ctx.precondition_path()
    relevant = ctx.runner_relevant()
    evidence = {
        "preconditionFile": str(path) if path else None,
        "exists": bool(path and path.is_file()),
        "runnerRelevant": relevant,
    }
    if path is None:
        return _result("na", "loopRunner.preconditionFile unset", evidence)
    if path.is_file():
        return _result("ok", f"{path.name} present", evidence)
    if not relevant:
        return _result(
            "na", f"{path.name} absent, but no feature has reached forge-4-backlog yet", evidence,
        )
    hint = ctx.loop_runner.get("setupHint")
    return _result(
        "warn", f"{path.name} absent — the runner is not wired into this project", evidence,
        _remedy(
            hint if isinstance(hint, str) and hint else "Wire the loop runner into the project",
            shlex.join([ctx.runner_bin(), "install", "."]),
            "local-write",
        ),
    )


def _check_runner_legacy_layout(ctx: _CheckContext) -> dict:
    """No legacy Ralph artefacts (``.ralph.json`` / ``.ralph/``) beside a rauf project."""
    if (na := _runner_unavailable(ctx)) is not None:
        return na
    runner_name = ctx.loop_runner.get("name")
    if runner_name != "rauf":
        return _result("na", f"runner is {runner_name!r}, not rauf — no legacy layout to detect",
                       {"runnerName": runner_name})
    ralph_json = ctx.cwd / ".ralph.json"
    ralph_dir = ctx.cwd / ".ralph"
    evidence = {
        "runnerName": runner_name,
        "ralphJson": ralph_json.is_file(),
        "ralphDir": ralph_dir.is_dir(),
        "runnerOnPath": ctx.runner_bin_path(),
    }
    found = [name for name, present in (("`.ralph.json`", evidence["ralphJson"]),
                                        ("`.ralph/`", evidence["ralphDir"])) if present]
    if not found:
        return _result("ok", "no legacy Ralph layout", evidence)
    return _result(
        "warn", "legacy Ralph layout present: " + ", ".join(found), evidence,
        _remedy(
            "Migrate the legacy Ralph layout to rauf's per-project artifacts",
            shlex.join([ctx.runner_bin(), "migrate", "."]),
            "local-write",
        ),
    )


def _check_runner_artifacts_stale(ctx: _CheckContext) -> dict:
    """The precondition file's ``installedBy`` version matches the live runner."""
    if (na := _runner_unavailable(ctx)) is not None:
        return na
    precondition = ctx.precondition()
    path = ctx.precondition_path()
    if precondition is None:
        return _result("na", "precondition file absent (see runner-wired)",
                       {"preconditionFile": str(path) if path else None})
    live = ctx.runner_version()
    installed_by = precondition.get("installedBy")
    parsed = _parse_installed_by(installed_by)
    evidence = {
        "preconditionFile": str(path),
        "installedBy": installed_by if isinstance(installed_by, str) else None,
        "installedVersion": _fmt_semver(parsed[1]) if parsed else None,
        "liveVersion": _fmt_semver(live) if live else None,
    }
    if live is None:
        return _result("na", "live runner version unknown (see runner-version)", evidence)
    if parsed is None:
        return _result(
            "warn", f"{path.name} has no parseable installedBy ({installed_by!r})", evidence,
            _remedy(
                "Refresh the runner's per-project artifacts",
                shlex.join([ctx.runner_bin(), "update", "."]),
                "local-write",
            ),
        )
    if parsed[1] < live:
        return _result(
            "warn",
            f"{path.name} was written by {installed_by}; the live runner is "
            f"{_fmt_semver(live)}",
            evidence,
            _remedy(
                "Refresh the runner's per-project artifacts",
                shlex.join([ctx.runner_bin(), "update", "."]),
                "local-write",
            ),
        )
    if parsed[1] > live:
        return _result(
            "warn",
            f"{path.name} was written by {installed_by}, newer than the live runner "
            f"{_fmt_semver(live)}",
            evidence,
            _install_remedy(ctx),
        )
    return _result("ok", f"{path.name} matches the live runner ({_fmt_semver(live)})", evidence)


def _check_runner_profile_drift(ctx: _CheckContext) -> dict:
    """``testCommand`` agrees with the runner profile's test/verify command.

    Divergence may be deliberate (the profile can run a broader gate), so this
    is advisory with no remedy — evidence shows both sides.
    """
    if (na := _runner_unavailable(ctx)) is not None:
        return na
    test_command = ctx.config.get("testCommand")
    if not isinstance(test_command, str) or not test_command.strip():
        return _result("na", "testCommand unset (see config-completeness)",
                       {"testCommand": None})
    precondition = ctx.precondition()
    path = ctx.precondition_path()
    if precondition is None:
        return _result("na", "precondition file absent (see runner-wired)",
                       {"testCommand": test_command})
    profile = precondition.get("profile")
    if not isinstance(profile, dict):
        return _result("na", f"{path.name} declares no profile", {"testCommand": test_command})
    commands = profile.get("commands")
    profile_test = commands.get("test") if isinstance(commands, dict) else None
    profile_verify = profile.get("verify")
    if not isinstance(profile_test, str):
        profile_test = None
    if not isinstance(profile_verify, str):
        profile_verify = None
    norm = " ".join(test_command.split())
    matches = [
        label for label, value in (("commands.test", profile_test), ("verify", profile_verify))
        if value is not None and " ".join(value.split()) == norm
    ]
    evidence = {
        "testCommand": test_command,
        "profileTest": profile_test,
        "profileVerify": profile_verify,
        "matches": matches,
    }
    if profile_test is None and profile_verify is None:
        return _result("na", f"{path.name} profile declares no test or verify command", evidence)
    if matches:
        return _result("ok", f"testCommand matches profile {' and '.join(matches)}", evidence)
    return _result(
        "warn",
        f"testCommand {test_command!r} matches neither profile.commands.test "
        f"{profile_test!r} nor profile.verify {profile_verify!r} — divergence may be deliberate",
        evidence,
    )


def _check_config_schema(ctx: _CheckContext) -> dict:
    """``forge.config.json`` parses and conforms to the bundled schema."""
    if not ctx.config_exists:
        return _result(
            "na", "forge.config.json absent — schema defaults apply",
            {"configPath": str(ctx.config_path)},
        )
    evidence: dict = {
        "configPath": str(ctx.config_path),
        "schemaPath": str(ctx.schema_path),
        "schemaError": ctx.schema_error,
        "parseError": None,
        "duplicateKeys": [],
        "invalidAutoVerifyKeys": [],
        "violations": [],
        "unknownKeys": [],
    }
    fix = _remedy("Fix forge.config.json so it parses as a JSON object", None, "local-write")
    try:
        value, duplicates = load_json_with_duplicates(ctx.config_path)
    except (OSError, ValueError, RecursionError) as exc:  # JSON *and* UTF-8 decode errors
        evidence["parseError"] = _exc_text(exc)
        return _result(
            "warn", f"forge.config.json unreadable or invalid JSON: {evidence['parseError']}",
            evidence, fix,
        )
    if not isinstance(value, dict):
        evidence["parseError"] = f"top level is {type(value).__name__}, expected object"
        return _result("warn", f"forge.config.json: {evidence['parseError']}", evidence, fix)
    evidence["duplicateKeys"] = list(duplicates)
    evidence["invalidAutoVerifyKeys"] = invalid_auto_verify_keys(value)
    findings: list[str] = []
    if duplicates:
        findings.append("duplicate keys (last value wins): " + ", ".join(duplicates))
    if evidence["invalidAutoVerifyKeys"]:
        findings.append(
            "invalid autoVerifyStages keys (ignored): "
            + ", ".join(evidence["invalidAutoVerifyKeys"])
        )
    if ctx.schema is None:
        return _result(
            "warn",
            f"config schema unreadable ({ctx.schema_error}); structural validation skipped",
            evidence,
            _remedy(
                "Reinstall or update feature-forge — the bundled forge-config-schema.json "
                "is missing or damaged",
                None,
                "global-install",
            ),
        )
    try:
        evidence["violations"] = _schema_violations(value, ctx.schema, ctx.schema, "$")
    except Exception as exc:  # a malformed schema node (e.g. ``"type": 5``)
        evidence["schemaError"] = f"schema malformed: {_exc_text(exc)}"
        return _result(
            "warn",
            f"config schema malformed ({_exc_text(exc)}); structural validation skipped",
            evidence,
            _remedy(
                "Reinstall or update feature-forge — the bundled forge-config-schema.json "
                "is damaged",
                None,
                "global-install",
            ),
        )
    props = ctx.schema.get("properties")
    known = set(props) if isinstance(props, dict) else set()
    evidence["unknownKeys"] = sorted(key for key in value if key not in known)
    findings += evidence["violations"]
    if findings:
        return _result(
            "warn",
            f"forge.config.json has {len(findings)} finding(s): {findings[0]}",
            evidence,
            _remedy(f"Fix forge.config.json: {findings[0]}", None, "local-write"),
        )
    detail = "forge.config.json conforms to the schema"
    if evidence["unknownKeys"]:
        detail += "; unknown top-level key(s) ignored: " + ", ".join(evidence["unknownKeys"])
    return _result("ok", detail, evidence)


def _check_root_version_skew(ctx: _CheckContext) -> dict:
    """The resolved root, this script's own bundle and any env override agree.

    Two roots agree when they are the same real path, or both declare a
    version and the versions match. A root without a version manifest at a
    different path cannot be proven equal and counts as skew.
    """
    if not ctx.plugin_root.get("resolved"):
        return _result("na", "plugin root unresolved (see plugin-root)", {"resolved": False})
    own_root = _BUNDLE_ROOT
    resolved_root = Path(str(ctx.plugin_root.get("root")))
    env_var = next(
        (name for name in ("FEATURE_FORGE_ROOT", "CLAUDE_PLUGIN_ROOT") if os.environ.get(name)),
        None,
    )
    roots = {
        "own": (own_root, _bundle_version(own_root)["version"]),
        "resolved": (resolved_root, ctx.plugin_root.get("version")),
    }
    if env_var:
        env_root = Path(os.environ[env_var])
        roots["env"] = (env_root, _bundle_version(env_root)["version"])

    def real(path: Path) -> str:
        try:
            return str(path.resolve())
        except OSError:
            return str(path)

    def agree(a: tuple[Path, str | None], b: tuple[Path, str | None]) -> bool:
        if real(a[0]) == real(b[0]):
            return True
        return a[1] is not None and b[1] is not None and a[1] == b[1]

    labels = list(roots)
    disagreements = [
        f"{x} ({roots[x][1] or 'no version'} at {roots[x][0]}) vs "
        f"{y} ({roots[y][1] or 'no version'} at {roots[y][0]})"
        for i, x in enumerate(labels) for y in labels[i + 1:]
        if not agree(roots[x], roots[y])
    ]
    evidence = {
        "ownRoot": str(own_root),
        "ownVersion": roots["own"][1],
        "resolvedRoot": str(resolved_root),
        "resolvedVersion": roots["resolved"][1],
        "envVar": env_var,
        "envRoot": str(roots["env"][0]) if "env" in roots else None,
        "envVersion": roots["env"][1] if "env" in roots else None,
        "agree": not disagreements,
    }
    if not disagreements:
        return _result(
            "ok",
            f"one install in play ({roots['resolved'][1] or 'unversioned'} at {resolved_root})",
            evidence,
        )
    return _result(
        "warn", "install roots disagree: " + "; ".join(disagreements), evidence,
        _remedy(
            "Reinstall or update feature-forge so a single bundle is loaded (setup guide: "
            "https://raw.githubusercontent.com/garygentry/feature-forge/main/AGENTS-SETUP.md), "
            "or unset the stale root override",
            None,
            "global-install",
        ),
    )


#: Config keys forge-2-tech records, in the order forge-2-tech writes them;
#: ``smokeCommand`` is optional everywhere (evidence-only when absent).
_CONFIG_KEYS_BY_STAGE: Final[tuple[tuple[str, str], ...]] = (
    ("stack", "forge-3-specs"),
    ("typeCheckCommand", "forge-4-backlog"),
    ("testCommand", "forge-4-backlog"),
)


def _check_config_completeness(ctx: _CheckContext) -> dict:
    """The keys forge-2-tech records exist once a feature is far enough along.

    A feature whose next stage is forge-3-specs needs ``stack``; from
    forge-4-backlog on (or complete) it also needs ``typeCheckCommand`` and
    ``testCommand``. Features that have not reached forge-3-specs are skipped.
    """
    def present(key: str) -> bool:
        value = ctx.config.get(key)
        return isinstance(value, str) and bool(value.strip())

    rows = []
    for feat in ctx.features:
        required = [
            key for key, floor in _CONFIG_KEYS_BY_STAGE
            if _stage_at_or_after(feat["nextStage"], floor)
        ]
        if not required:
            continue
        missing = [key for key in required if not present(key)]
        rows.append({
            "name": feat["name"],
            "epic": feat["epic"],
            "nextStage": feat["nextStage"],
            "required": list(required),
            "missing": missing,
            "remedy": _remedy(
                "Record the missing keys in forge.config.json (forge-2-tech Step 3 writes "
                "stack/typeCheckCommand/testCommand): " + ", ".join(missing),
                None,
                "local-write",
            ) if missing else None,
        })
    optional_missing = [key for key in ("smokeCommand",) if not present(key)]
    evidence = {
        "configExists": ctx.config_exists,
        "features": rows,
        "missing": [
            key for key, _floor in _CONFIG_KEYS_BY_STAGE
            if any(key in row["missing"] for row in rows)
        ],
        "optionalMissing": optional_missing,
    }
    if not rows:
        return _result("na", "no active feature has reached forge-3-specs", evidence)
    affected = [row for row in rows if row["missing"]]
    if not affected:
        detail = f"required config present for {len(rows)} feature(s)"
        if optional_missing:
            detail += "; optional " + ", ".join(optional_missing) + " unset"
        return _result("ok", detail, evidence)
    return _result(
        "warn",
        f"{len(affected)} feature(s) missing required config: "
        + ", ".join(evidence["missing"]),
        evidence,
        _per_feature_remedy(rows),
    )


def _check_backlog_valid(ctx: _CheckContext) -> dict:
    """Each backlog the loop is about to consume passes ``{bin} backlog validate``.

    Scoped to features whose next stage is forge-5-loop (a validated-and-done
    loop's backlog is history), at most one probe per distinct backlog dir.
    """
    if (na := _runner_unavailable(ctx)) is not None:
        return na
    if not ctx.runner_bin_path():
        return _result("na", "runner binary not on PATH (see runner-binary)",
                       {"bin": ctx.runner_bin()})
    template = ctx.loop_runner.get("validateCommand")
    if not isinstance(template, str) or not template.strip():
        return _result("na", "loopRunner.validateCommand unset", {"command": template})
    eligible = [
        feat for feat in ctx.features
        if feat["nextStage"] == "forge-5-loop" and feat["backlogExists"]
    ]
    evidence: dict = {"command": template, "features": []}
    if not eligible:
        return _result(
            "na", "no active feature is about to run forge-5-loop with a backlog on disk",
            evidence,
        )
    probes: dict[str, dict] = {}
    rows = []
    for feat in eligible:
        backlog_dir = str(Path(feat["backlogPath"]).parent)
        if backlog_dir not in probes:
            argv = _render_runner_command(
                template, ctx.loop_runner, backlogDir=backlog_dir, specsDir=str(ctx.specs_dir),
            )
            probes[backlog_dir] = (
                _run_probe(argv, cwd=ctx.cwd) if argv
                else {"ok": False, "returncode": None, "stdout": "", "stderr": "",
                      "error": "validateCommand cannot be rendered", "timedOut": False}
            )
        probe = probes[backlog_dir]
        findings: list = []
        findings_parsed = False
        if probe["returncode"] == 1:
            try:
                payload = json.loads(probe["stdout"])
            except ValueError:
                payload = None
            raw = payload.get("findings") if isinstance(payload, dict) else payload
            if isinstance(raw, list):
                findings = raw
                findings_parsed = True
        rows.append({
            "name": feat["name"],
            "epic": feat["epic"],
            "backlogDir": backlog_dir,
            "exitCode": probe["returncode"],
            "valid": probe["ok"],
            "timedOut": probe["timedOut"],
            "error": probe["error"],
            "findingsCount": len(findings),
            "findingsParsed": findings_parsed,
            "findings": [_head(json.dumps(f, ensure_ascii=False)) for f in findings[:5]],
            "stderrHead": _head(probe["stderr"]),
            "remedy": None,
        })
    evidence["features"] = rows
    bad = [row for row in rows if not row["valid"]]
    if not bad:
        return _result("ok", f"{len(rows)} backlog(s) validate", evidence)
    parts = []
    for row in bad:
        if row["exitCode"] == 1 and row["findingsParsed"]:
            parts.append(f"{_feature_label(row)} ({row['findingsCount']} finding(s))")
        elif row["exitCode"] == 1:
            parts.append(
                f"{_feature_label(row)} (exit 1 but the validator output is not findings JSON"
                + (f": {row['stderrHead']}" if row["stderrHead"] else "")
                + ")"
            )
        else:
            why = row["error"] or f"exit {row['exitCode']}"
            parts.append(f"{_feature_label(row)} (validator {why})")
    return _result(
        "warn",
        f"{len(bad)} backlog(s) fail validation: " + "; ".join(parts)
        + " — fix the findings or re-run /skill:forge-4-backlog <feature>",
        evidence,
    )


def _check_gh_available(ctx: _CheckContext) -> dict:
    """GitHub CLI on PATH with credentials (``gh auth token``; never ``auth status``)."""
    path = shutil.which("gh")
    evidence: dict = {
        "path": path,
        "version": None,
        "authenticated": False,
        "tokenFromEnv": any(os.environ.get(name) for name in ("GH_TOKEN", "GITHUB_TOKEN")),
    }
    install = _remedy(
        "Install the GitHub CLI (https://cli.github.com) — needed only for PR/issue "
        "automation; every stage degrades to manual steps without it",
        None,
        "global-install",
    )
    if path is None:
        return _result("warn", "GitHub CLI (gh) not on PATH", evidence, install)
    version = _run_probe([path, "--version"])
    if not version["ok"]:
        evidence["versionError"] = version["error"] or _head(version["stderr"])
        return _result(
            "warn", f"gh present at {path} but `gh --version` failed", evidence,
            _remedy("Reinstall the GitHub CLI", None, "global-install"),
        )
    evidence["version"] = _head(version["stdout"].splitlines()[0] if version["stdout"] else "")
    # stdout is a credential: discarded before it can reach evidence.
    token = _run_probe([path, "auth", "token"], discard_stdout=True)
    if not token["ok"]:
        return _result(
            "warn", f"gh present ({evidence['version']}) but has no credentials", evidence,
            _remedy("Authenticate the GitHub CLI", "gh auth login", "network"),
        )
    evidence["authenticated"] = True
    return _result("ok", f"gh present and authenticated ({evidence['version']})", evidence)


def _check_backlog_present(ctx: _CheckContext) -> dict:
    """Every feature past forge-4-backlog has its composed ``backlog.json`` on disk."""
    eligible = [f for f in ctx.features if _stage_at_or_after(f["nextStage"], "forge-5-loop")]
    if not eligible:
        return _result(
            "na", "no active feature has completed forge-4-backlog",
            {"features": [], "skipped": len(ctx.features)},
        )
    rows = [
        {
            "name": feat["name"],
            "epic": feat["epic"],
            "nextStage": feat["nextStage"],
            "backlogPath": feat["backlogPath"],
            "exists": feat["backlogExists"],
            # The fix is a slash command, not a shell command: remedy stays null.
            "remedy": None,
        }
        for feat in eligible
    ]
    missing = [row for row in rows if not row["exists"]]
    evidence = {"features": rows, "skipped": len(ctx.features) - len(eligible)}
    if not missing:
        return _result("ok", f"{len(rows)} backlog(s) present", evidence)
    names = ", ".join(_feature_label(row) for row in missing)
    return _result(
        "warn",
        f"backlog missing for {len(missing)} feature(s): {names} — re-run "
        "/skill:forge-4-backlog <feature> to regenerate it",
        evidence,
    )


def _check_branch_state(ctx: _CheckContext) -> dict:
    """The current branch matches each pending feature's recorded state branch.

    Complete features are skipped: their branch is history, not a place the
    next stage will run. Reuses the legacy ``branchReconcile`` classification
    (``adopt-current`` on a topic branch, ``warn-drift`` on the default branch).
    """
    base = {"currentBranch": ctx.current_branch, "defaultBranch": ctx.default_branch}
    if ctx.current_branch is None:
        return _result("na", "not a git repository (no current branch)", base)
    pending = [f for f in ctx.features if f["nextStage"] is not None]
    skipped = len(ctx.features) - len(pending)
    if not pending:
        return _result(
            "na", "no active feature has a pending stage",
            {**base, "features": [], "skippedComplete": skipped},
        )
    script = str(_SHIM_PATH)
    rows = []
    for feat in pending:
        reconcile = feat.get("branchReconcile")
        remedy = None
        if reconcile == "adopt-current":
            argv = [
                "python3", script, "state-branch", "--feature", feat["name"],
                "--branch", ctx.current_branch, "--specs-dir", str(ctx.specs_dir),
            ]
            if feat["epic"]:
                argv += ["--epic", feat["epic"]]
            remedy = _remedy(
                f"Record the current branch '{ctx.current_branch}' in the feature's state "
                f"(recorded: '{feat['stateBranch']}')",
                shlex.join(argv),
                "local-write",
            )
        elif reconcile == "warn-drift":
            remedy = _remedy(
                f"Switch to the feature's recorded branch before running {feat['nextStage']} "
                "(create it with `git switch -c` if it no longer exists)",
                shlex.join(["git", "switch", feat["stateBranch"]]),
                "local-write",
            )
        rows.append({
            "name": feat["name"],
            "epic": feat["epic"],
            "nextStage": feat["nextStage"],
            "stateBranch": feat["stateBranch"],
            "reconcile": reconcile,
            "remedy": remedy,
        })
    evidence = {**base, "features": rows, "skippedComplete": skipped}
    drifted = [row for row in rows if row["reconcile"]]
    if not drifted:
        return _result(
            "ok", f"{len(rows)} pending feature(s) consistent with branch '{ctx.current_branch}'",
            evidence,
        )
    parts = [
        f"{_feature_label(row)} ({row['reconcile']}: on '{ctx.current_branch}', "
        f"state records '{row['stateBranch']}')"
        for row in drifted
    ]
    return _result(
        "warn",
        f"{len(drifted)} feature(s) with branch drift: " + "; ".join(parts),
        evidence,
        _per_feature_remedy(rows),
    )


def _check_sandbox_root(ctx: _CheckContext) -> dict:
    """Root without ``IS_SANDBOX`` — the forge-5-loop launch condition (#99)."""
    if getattr(os, "geteuid", None) is None:
        return _result(
            "na", "os.geteuid unavailable on this platform — root/sandbox gate not applicable",
            {"platform": sys.platform},
        )
    status = _root_sandbox_status()
    if status["loopWillSetSandbox"]:
        return _result(
            "warn",
            "running as root without IS_SANDBOX — forge-5-loop will export IS_SANDBOX=1 at "
            "launch so the runner's --dangerously-skip-permissions is not refused",
            status,
            _remedy(
                "Export IS_SANDBOX=1 in the launching shell (forge-5-loop supplies it "
                "automatically)",
                "export IS_SANDBOX=1",
                "read-only",
            ),
        )
    detail = (
        "running as root; IS_SANDBOX already set" if status["isRoot"] else "not running as root"
    )
    return _result("ok", detail, status)


def _process_ancestry(
    start_pid: int, *, proc_root: Path = Path("/proc"), max_depth: int = _ANCESTRY_MAX_DEPTH,
) -> list[dict]:
    """Walk ``/proc`` from ``start_pid`` upward; never raises, never blocks.

    Returns one entry per readable ancestor, nearest first:
    ``{"pid", "name", "flags"}`` where ``name`` is the basename of ``argv[0]``
    and ``flags`` are the ``_HEADLESS_FLAGS`` present in that argv.

    **Only** those two fields are extracted, and ``name`` is redacted to ``?``
    unless it looks like an executable basename (``_EXEC_NAME_RE``). Raw argv is
    never returned: a parent's command line can carry credentials or a username,
    and every field here reaches ``doctor --json`` output that gets pasted into
    issues and PRs.
    """
    chain: list[dict] = []
    pid = start_pid
    seen: set[int] = set()
    for _ in range(max_depth):
        if pid <= 0 or pid in seen:
            break
        seen.add(pid)
        try:
            # `stat` first: it carries the ppid, so a frame whose `cmdline` is
            # unreadable (hidepid, a uid boundary, a pid that just exited) costs
            # us its NAME but not the rest of the walk.
            stat = (proc_root / str(pid) / "stat").read_text(encoding="utf-8", errors="replace")
            ppid = int(stat.rsplit(") ", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            break
        try:
            raw = (proc_root / str(pid) / "cmdline").read_bytes()
            argv = [part for part in raw.decode("utf-8", "replace").split("\0") if part]
        except OSError:
            argv = []
        if argv:
            # Basename only a real path: `sshd: gary@pts/6` would otherwise
            # basename to `6`, which is both meaningless and a hint at a real user.
            argv0 = argv[0]
            name = (
                PurePosixPath(argv0).name.lstrip("-")
                if not (set(argv0) & {" ", ":", "\t"}) else "?"
            )
            chain.append({
                "pid": pid,
                "name": name if _EXEC_NAME_RE.match(name) else "?",
                "flags": sorted(set(argv[1:]) & _HEADLESS_FLAGS),
                "replyFlags": sorted(set(argv[1:]) & _REPLY_CHANNEL_FLAGS),
                # False when the process exposes no arguments at all — either it
                # genuinely had none, or it overwrote its argv (see _classify_ancestry).
                "hasArgs": len(argv) > 1,
            })
        if pid == 1:
            break
        pid = ppid
    return chain


def _classify_ancestry(chain: list[dict]) -> dict:
    """Derive ``{mode, host, harness}`` from an ancestry chain. Pure.

    The **nearest** recognised harness ancestor decides both axes, so a nested
    session is read as itself rather than as whatever launched its launcher.

    Asymmetric by design. Claiming ``non-interactive`` makes a skill take silent
    defaults, so it is claimed only from a verified harness carrying an explicit
    headless flag. Claiming ``interactive`` only risks a question nobody answers
    — today's behavior — so it is claimed from a verified harness that exposes
    arguments and carries no headless flag. Everything else is ``None``
    (reported as ``unknown``), never a guess either way.

    A harness exposing **no arguments at all** yields no mode. Measured: Pi
    overwrites its own argv with its process title, so ``/proc/<pid>/cmdline``
    for a ``pi -p --mode json`` session reads exactly ``pi`` with the flags
    erased. Without this rule that session is read as *interactive* — a
    confidently wrong claim in the dangerous direction. The rule is written
    against the argv, not against Pi, so it covers any harness that sets a
    process title, and Pi starts detecting again for free if it ever stops.
    """
    for entry in chain:
        host = next((hid for name, hid in _ANCESTRY_HOSTS if entry["name"] == name), None)
        if host is None:
            continue
        if entry["name"] not in _ANCESTRY_MODE_HARNESSES or not entry["hasArgs"]:
            return {"mode": None, "host": host, "harness": entry["name"]}
        if entry["flags"] and entry["replyFlags"]:
            # Headless-looking but a reply channel is wired back in — refuse both
            # claims rather than pick the wrong one.
            return {"mode": None, "host": host, "harness": entry["name"]}
        mode = "non-interactive" if entry["flags"] else "interactive"
        return {"mode": mode, "host": host, "harness": entry["name"]}
    return {"mode": None, "host": None, "harness": None}


def _bundle_agent(root: Path) -> str | None:
    """The adapter id this script was installed as, from its bundle sentinel.

    ``scripts/forge-session.py`` is copied byte-identically into every
    ``adapters/<agent>/scripts/``, so the sentinel beside it names the host
    exactly — the one host fact that is neither guessed nor inferred. Absent at
    the mainline repo root (a dogfood checkout is not a bundle), which is why
    ``_check_interaction_mode`` falls back to ancestry rather than failing.
    """
    try:
        manifest = root / ".feature-forge-bundle.json"
        if not manifest.is_file():
            return None
        agent = _load_config(manifest).get("agent")
    except (OSError, ValueError, RecursionError):
        return None
    return agent if isinstance(agent, str) and agent in _ADAPTER_AGENT_IDS else None


def _check_interaction_mode(ctx: _CheckContext) -> dict:
    """Report the session's interaction mode and host as DATA a skill reads.

    Closes the gap #261 measured: a model has no observable signal for "this
    invocation has no reply channel", so off-Claude headless runs self-assess
    rung 2, emit a prose question and stall — including every rauf loop
    iteration, which runs non-interactively by construction.

    The split this check is built on: a model CAN observe rung 1 vs rung 2 (does
    it have a structured question tool) and CANNOT observe rung 2 vs rung 3 (is
    there a reply channel). This supplies exactly the half the model cannot see,
    and never the half it can — so it informs the ladder without becoming the
    host-implies-capability proxy INV-5 forbids.

    Precedence: the launcher's explicit stamp, then verified process ancestry,
    then ``unknown``. ``unknown`` means "self-assess as today" and is reported
    as ``na``; it is NEVER reported as non-interactive, because guessing
    headless would make an interactive session silently skip its questions and
    take no-write defaults — a silent behavior change traded for a visible
    stall, which is worse than the bug.

    Spawns nothing: the whole check is one env read plus ``/proc`` reads.
    """
    raw = os.environ.get(INTERACTION_ENV_VAR)
    stamp = raw.strip().lower() if isinstance(raw, str) else ""
    chain = _process_ancestry(os.getppid())
    inferred = _classify_ancestry(chain)
    bundle_agent = _bundle_agent(_BUNDLE_ROOT)

    mode, source = (stamp, "env-stamp") if stamp in INTERACTION_MODES else (None, None)
    # A POSITIVE contradiction between the two signals resolves to neither. The
    # stamp normally wins (it is stated, not inferred), but when ancestry has a
    # confident opposite reading the honest answer is that we do not know — and
    # `unknown` (self-assess, ask) is the only resolution that cannot silently
    # skip a question in a session someone is actually watching. Ancestry that
    # merely fails to read a mode is not a contradiction and does not trigger this.
    conflict = (
        source == "env-stamp"
        and inferred["mode"] is not None
        and inferred["mode"] != mode
    )
    if conflict:
        mode, source = None, None
    if mode is None and not conflict and inferred["mode"] is not None:
        mode, source = inferred["mode"], "ancestry"
    host = bundle_agent or inferred["host"]
    host_arg = None if host is None else (host if host in _NAMED_HOST_ARGS else "generic")

    evidence: dict = {
        "mode": mode or "unknown",
        "modeSource": source,
        "rung": 3 if mode == "non-interactive" else None,
        "host": host,
        "hostArg": host_arg,
        "hostSource": "bundle" if bundle_agent else ("ancestry" if host else None),
        "envVar": INTERACTION_ENV_VAR,
        "envStamp": _head(raw) if raw else None,
        "harness": inferred["harness"],
        # Basenames and headless flags only — never a parent's raw argv (§ _process_ancestry).
        "ancestry": chain,
    }
    if raw and stamp not in INTERACTION_MODES:
        evidence["envStampError"] = (
            f"{INTERACTION_ENV_VAR} is not one of {', '.join(INTERACTION_MODES)}"
        )
    if conflict:
        evidence["conflict"] = (
            f"{INTERACTION_ENV_VAR}={stamp} but {inferred['harness']} ancestry "
            f"looks {inferred['mode']} — neither is trusted"
        )

    where = f"host {host or 'unknown'}"
    if conflict:
        return _result(
            "warn",
            f"interaction signals contradict ({where}): {evidence['conflict']}; "
            "treating the mode as unknown — skills self-assess the rung",
            evidence,
            _remedy(
                f"Unset {INTERACTION_ENV_VAR} in this shell if it was exported by hand, or "
                f"correct the launcher that sets it — a stale stamp claiming 'non-interactive' "
                f"in an attended session would make skills skip their questions silently",
                None,
                "read-only",
            ),
        )
    if mode is None:
        return _result(
            "na",
            f"interaction mode undetermined ({where}) — skills self-assess the rung as before",
            evidence,
            _remedy(
                f"Have the launcher state the mode: set {INTERACTION_ENV_VAR} to "
                f"'non-interactive' when spawning a session with no reply channel, or "
                f"'interactive' otherwise. Never guessed from the host (INV-5)",
                None,
                "read-only",
            ),
        )
    if mode == "non-interactive":
        return _result(
            "ok",
            f"non-interactive session ({where}, via {source}) — rung 3: declared defaults apply",
            evidence,
        )
    return _result("ok", f"interactive session ({where}, via {source})", evidence)


#: The check registry — registry order is output order (docs/doctor-checks.md).
DOCTOR_CHECKS: Final[tuple[_CheckSpec, ...]] = (
    _make_spec("plugin-root", "blocking", _check_plugin_root),
    _make_spec("root-version-skew", "advisory", _check_root_version_skew),
    _make_spec("runner-binary", "blocking", _check_runner_binary),
    _make_spec("runner-version", "blocking", _check_runner_version),
    _make_spec("runner-wired", "blocking", _check_runner_wired),
    _make_spec("runner-legacy-layout", "blocking", _check_runner_legacy_layout),
    _make_spec("runner-artifacts-stale", "advisory", _check_runner_artifacts_stale),
    _make_spec("runner-profile-drift", "advisory", _check_runner_profile_drift),
    _make_spec("config-completeness", "advisory", _check_config_completeness),
    _make_spec("config-schema", "advisory", _check_config_schema),
    _make_spec("backlog-present", "blocking", _check_backlog_present),
    _make_spec("backlog-valid", "blocking", _check_backlog_valid),
    _make_spec("branch-state", "advisory", _check_branch_state),
    _make_spec("gh-available", "advisory", _check_gh_available),
    _make_spec("sandbox-root", "advisory", _check_sandbox_root),
    _make_spec("interaction-mode", "advisory", _check_interaction_mode),
)

#: The ids, in registry order, for ``--check`` choices and the catalog parity test.
DOCTOR_CHECK_IDS: Final[tuple[str, ...]] = tuple(spec.id for spec in DOCTOR_CHECKS)


def _run_checks(ctx: _CheckContext, specs: list[_CheckSpec] | tuple[_CheckSpec, ...]) -> list[dict]:
    """Run each spec with crash isolation and return the validated records.

    A check that raises — or returns something ``_check_record`` rejects, or
    something ``json.dumps`` cannot serialise — becomes an ``na`` record whose
    ``detail`` names the exception. A ``fail`` from a check outside
    ``FAIL_PROMOTED_CHECK_IDS`` is demoted to ``warn`` with
    ``evidence.demotedFromFail`` set, so INV-1 holds structurally.
    """
    records: list[dict] = []
    for spec in specs:
        try:
            raw = spec.run(ctx)
            if not isinstance(raw, dict):
                raise TypeError(f"check returned {type(raw).__name__}, expected dict")
            status = raw.get("status")
            evidence = raw.get("evidence")
            if status == "fail" and spec.id not in FAIL_PROMOTED_CHECK_IDS:
                status = "warn"
                evidence = {**(evidence or {}), "demotedFromFail": True}
            record = _check_record(
                spec.id, status, spec.severity, raw.get("detail", ""), evidence, raw.get("remedy"),
            )
            json.dumps(record)
        except Exception as exc:  # crash isolation (INV-3)
            record = _check_record(
                spec.id, "na", spec.severity, f"check crashed: {_exc_text(exc)}",
            )
        records.append(record)
    return records


def _checks_summary(checks: list[dict]) -> dict:
    """Count ``checks[]`` by status, always emitting every status key."""
    summary = {status: 0 for status in CHECK_STATUSES}
    for record in checks:
        summary[record["status"]] += 1
    return summary


def cluster_checks(checks: list[dict]) -> list[dict]:
    """Group ``checks[]`` with a runnable remedy by identical ``remedy.command``.

    Returns ``[{command, safety, checkIds[], description}, …]`` in first-seen
    order. Records whose remedy is null, or whose remedy has no command
    (description-only advice), are not clustered — they are report-only.
    Identical commands merge; the cluster's ``safety`` is the most conservative
    tier among its members and its ``description`` the first member's.
    """
    clusters: dict[str, dict] = {}
    for record in checks:
        remedy = record.get("remedy")
        if not isinstance(remedy, dict) or not remedy.get("command"):
            continue
        command = remedy["command"]
        entry = clusters.get(command)
        if entry is None:
            clusters[command] = {
                "command": command,
                "safety": remedy["safety"],
                "checkIds": [record["id"]],
                "description": remedy["description"],
            }
            continue
        entry["checkIds"].append(record["id"])
        if REMEDY_SAFETY_TIERS.index(remedy["safety"]) > REMEDY_SAFETY_TIERS.index(entry["safety"]):
            entry["safety"] = remedy["safety"]
    return list(clusters.values())


_CHECK_MARKERS: Final[dict[str, str]] = {"ok": "ok", "warn": "!", "fail": "X", "na": "na"}


def _print_checks(report: dict, *, verbose: bool = False) -> None:
    """Print the ``checks[]`` block: a one-line summary, then one line per finding.

    ``warn``/``fail`` records always print (with their remedy on the next
    line); ``ok``/``na`` records only with ``verbose``.
    """
    summary = report.get("checksSummary") or {}
    print(
        "checks: " + ", ".join(f"{summary.get(s, 0)} {s}" for s in CHECK_STATUSES)
    )
    for record in report.get("checks") or []:
        if record["status"] in ("ok", "na") and not verbose:
            continue
        marker = _CHECK_MARKERS.get(record["status"], "?")
        print(f"  {marker:>2} {record['id']}: {record['detail']}")
        remedy = record.get("remedy")
        if remedy:
            print(
                f"      remedy [{remedy['safety']}]: "
                + (remedy["command"] or remedy["description"])
            )


def _print_doctor(report: dict, *, verbose: bool = False) -> None:
    """Print the human-readable doctor report (legacy lines, then the checks block)."""
    root = report["pluginRoot"]
    if root.get("resolved"):
        detail = " ".join(
            f"{key}={root[key]}" for key in ("version", "commit") if key in root
        )
        print(f"plugin root: {root['root']}" + (f"  ({detail})" if detail else ""))
    else:
        print(f"plugin root: UNRESOLVED — {root.get('error', 'unknown')}")
    print(f"current branch: {report['currentBranch'] or '(not a git repo)'}")
    specs_error = report.get("specsDirError")
    print(
        f"specs dir: {report['specsDir']}"
        + ("" if report["specsDirExists"] else "  (MISSING)")
        + (f"  (UNREADABLE — {specs_error}; features not scanned)" if specs_error else "")
    )
    print(
        f"config: {report['configPath']}"
        + ("" if report["configExists"] else "  (MISSING)")
    )
    counts = report["counts"]
    print(
        f"features: {counts['active']} active "
        f"(paused: {counts['paused']}, abandoned: {counts['abandoned']})"
    )
    for feat in report["features"]:
        label = feat["name"] + (f" [{feat['epic']}]" if feat["epic"] else "")
        branch = feat["stateBranch"] or "?"
        if feat["branchMatchesState"] is False:
            if feat.get("branchReconcile") == "adopt-current":
                branch += " (MISMATCH — reconcile: adopt current branch)"
            elif feat.get("branchReconcile") == "warn-drift":
                branch += " (MISMATCH — on default branch; create a topic branch)"
            else:
                branch += " (MISMATCH vs current)"
        backlog = "exists" if feat["backlogExists"] else "MISSING"
        print(
            f"  - {label}: stage={feat['currentStage']} "
            f"verify={feat['verifyState']} branch={branch} "
            f"backlog={backlog} ({feat['backlogPath']})"
        )
    invalid = report.get("invalidAutoVerifyKeys") or []
    if invalid:
        print("  ! invalid autoVerifyStages keys (ignored): " + ", ".join(invalid))
    duplicates = report.get("duplicateConfigKeys") or []
    if duplicates:
        print(
            "  ! duplicate config keys (last value wins): " + ", ".join(duplicates)
        )
    rs = report.get("rootSandbox") or {}
    if rs.get("isRoot"):
        if rs.get("isSandboxSet"):
            print("root/sandbox: running as root; IS_SANDBOX already set — loop launch OK")
        else:
            print(
                "root/sandbox: running as root; IS_SANDBOX not set — forge-5-loop will "
                "export IS_SANDBOX=1 at launch so rauf's "
                "--dangerously-skip-permissions is not refused"
            )
    if "checks" in report:
        _print_checks(report, verbose=verbose)


__all__ = [
    "_resolve_plugin_root",
    "_bundle_version",
    "_backlog_path",
    "doctor_report",
    "_root_sandbox_status",
    "CHECK_STATUSES",
    "CHECK_SEVERITIES",
    "REMEDY_SAFETY_TIERS",
    "FAIL_PROMOTED_CHECK_IDS",
    "NO_NA_CHECKS",
    "_CHECK_ID_RE",
    "_PROBE_TIMEOUT_S",
    "_PROBE_OUTPUT_CAP",
    "INTERACTION_ENV_VAR",
    "_ADAPTER_AGENT_IDS",
    "INTERACTION_MODES",
    "_ANCESTRY_MODE_HARNESSES",
    "_ANCESTRY_HOSTS",
    "_HEADLESS_FLAGS",
    "_REPLY_CHANNEL_FLAGS",
    "_ANCESTRY_MAX_DEPTH",
    "_EXEC_NAME_RE",
    "_NAMED_HOST_ARGS",
    "_remedy",
    "_result",
    "_check_record",
    "_exc_text",
    "_head",
    "_run_probe",
    "_render_runner_command",
    "_SEMVER_NUM",
    "_SEMVER_RE",
    "_INSTALLED_BY_RE",
    "_parse_semver",
    "_fmt_semver",
    "_parse_installed_by",
    "_first_backticked",
    "_JSON_SCHEMA_TYPES",
    "_schema_violations",
    "_stage_at_or_after",
    "_CheckContext",
    "_build_check_context",
    "_CheckSpec",
    "_make_spec",
    "_per_feature_remedy",
    "_feature_label",
    "_check_plugin_root",
    "_runner_unavailable",
    "_NETWORK_FETCH_RE",
    "_install_remedy",
    "_check_runner_binary",
    "_check_runner_version",
    "_check_runner_wired",
    "_check_runner_legacy_layout",
    "_check_runner_artifacts_stale",
    "_check_runner_profile_drift",
    "_check_config_schema",
    "_check_root_version_skew",
    "_CONFIG_KEYS_BY_STAGE",
    "_check_config_completeness",
    "_check_backlog_valid",
    "_check_gh_available",
    "_check_backlog_present",
    "_check_branch_state",
    "_check_sandbox_root",
    "_process_ancestry",
    "_classify_ancestry",
    "_bundle_agent",
    "_check_interaction_mode",
    "DOCTOR_CHECKS",
    "DOCTOR_CHECK_IDS",
    "_run_checks",
    "_checks_summary",
    "cluster_checks",
    "_CHECK_MARKERS",
    "_print_checks",
    "_print_doctor",
    "RECOVERY_MIN_RUNNER_VERSION",
]
