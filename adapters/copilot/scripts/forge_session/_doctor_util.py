"""Pure parsing/validation helpers the doctor registry leans on.

Split out of ``forge_session.doctor`` (#279 P4.1) so the doctor module stays under
the package's per-module size ceiling. These are leaf helpers — SemVer parsing, the
``installed-by`` stamp reader, the stdlib JSON-Schema subset validator, and the
stage-ordering predicate — with no dependency on the check registry, the probe
runner, or any monkeypatched symbol. ``forge_session.doctor`` imports them back and
re-exports them, so ``forge_session.doctor.<helper>`` (and the shim re-export) keep
resolving exactly as before.
"""

from __future__ import annotations

import re
from typing import Final

from forge_session._common import PRODUCTION_STAGES

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


CHECK_STATUSES: Final[tuple[str, ...]] = ("ok", "warn", "fail", "na")
CHECK_SEVERITIES: Final[tuple[str, ...]] = ("blocking", "advisory")
#: Ordered least → most consequential; a merged remedy carries the highest tier.
REMEDY_SAFETY_TIERS: Final[tuple[str, ...]] = (
    "read-only", "local-write", "global-install", "network",
)
#: Evidence carries at most this many characters of any probe stream.
_PROBE_OUTPUT_CAP: Final[int] = 400


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
