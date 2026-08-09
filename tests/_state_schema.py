"""Hand-rolled stdlib JSON-Schema validator shared by the R4/R5 drift guards.

`jsonschema` is absent in CI (and in this repo's dev environment), so the guards
that prove `forge-session.py`'s state verbs, `effective-config`, and decision verbs
stay schema-conformant validate structurally instead — mirroring `epic-manifest.py`'s
`_schema_findings()` precedent. That keeps the schemas the single source of truth
in CI rather than only in prose.

The validator is deliberately minimal: it is a **drift guard**, not a general
JSON-Schema engine. It supports exactly the draft-07 subset the four schemas
(pipeline-state, epic-state, forge-config, forge-decisions) use — `type`,
`required`, `properties`, `enum`, `items`, `additionalProperties: false`, and
`$ref` to `#/definitions/*` (same-file only — which is why epic-state MIRRORS
pipeline-state's `verifyEntry` instead of cross-file-referencing it; the parity
guard in tests/test_epic_state_schema_conformance.py keeps the copies equal).
If a future schema construct appears (e.g. `oneOf`), extend `_check` rather than
reaching for `jsonschema`.

All entry points return a list of human-readable violations; an empty list
means valid, so `assert validate_state(s) == [], validate_state(s)` reports *what*
drifted.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_STATE_SCHEMA = json.loads(
    (REPO_ROOT / "references" / "pipeline-state-schema.json").read_text(encoding="utf-8")
)
_CONFIG_SCHEMA = json.loads(
    (REPO_ROOT / "references" / "forge-config-schema.json").read_text(encoding="utf-8")
)
_DECISIONS_SCHEMA = json.loads(
    (REPO_ROOT / "references" / "forge-decisions-schema.json").read_text(encoding="utf-8")
)
_EPIC_STATE_SCHEMA = json.loads(
    (REPO_ROOT / "references" / "epic-state-schema.json").read_text(encoding="utf-8")
)

_JSON_TYPES: dict[str, type | tuple[type, ...]] = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "null": type(None),
}


def _check(node: object, schema: dict, schema_root: dict, path: str) -> list[str]:
    """Return a list of schema violations for ``node`` (empty == valid).

    Args:
        node: The instance value to validate.
        schema: The (sub)schema to validate it against.
        schema_root: The root schema, for resolving ``#/definitions/*`` refs.
        path: A dotted JSON path used in violation messages.

    Returns:
        Human-readable violation strings; empty when ``node`` conforms.
    """
    out: list[str] = []
    if "$ref" in schema:
        ref = schema["$ref"].split("/")[-1]
        schema = schema_root["definitions"][ref]

    declared = schema.get("type")
    if declared:
        names = [declared] if isinstance(declared, str) else list(declared)
        allowed = tuple(_JSON_TYPES[name] for name in names if name in _JSON_TYPES)
        flat: tuple[type, ...] = tuple(
            t for entry in allowed for t in (entry if isinstance(entry, tuple) else (entry,))
        )
        # `bool` is a subclass of `int` in Python; a boolean is not an integer here.
        if flat and (
            not isinstance(node, flat)
            or (isinstance(node, bool) and bool not in flat)
        ):
            return [f"{path}: expected {declared}, got {type(node).__name__}"]

    if schema.get("enum") is not None and node not in schema["enum"]:
        out.append(f"{path}: {node!r} not in enum {schema['enum']}")

    if isinstance(node, dict):
        for req in schema.get("required", []):
            if req not in node:
                out.append(f"{path}: missing required '{req}'")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in node:
                if key not in props:
                    out.append(f"{path}: unexpected key '{key}'")
        for key, value in node.items():
            if key in props:
                out += _check(value, props[key], schema_root, f"{path}.{key}")

    if isinstance(node, list) and "items" in schema:
        for index, item in enumerate(node):
            out += _check(item, schema["items"], schema_root, f"{path}[{index}]")

    return out


def validate_state(state: dict) -> list[str]:
    """Validate a pipeline-state object against `references/pipeline-state-schema.json`.

    Args:
        state: A `.pipeline-state.json` object.

    Returns:
        Human-readable violation strings; empty when the state conforms.
    """
    return _check(state, _STATE_SCHEMA, _STATE_SCHEMA, "$")


def validate_effective_config(loop_runner: dict) -> list[str]:
    """Validate a resolved loopRunner block against `references/forge-config-schema.json`.

    Args:
        loop_runner: The resolved block emitted by `forge-session.py effective-config`.

    Returns:
        Human-readable violation strings; empty when the block conforms.
    """
    return _check(
        loop_runner,
        _CONFIG_SCHEMA["properties"]["loopRunner"],
        _CONFIG_SCHEMA,
        "$.loopRunner",
    )


def validate_epic_state(state: dict) -> list[str]:
    """Validate an epic-state object against `references/epic-state-schema.json`.

    Args:
        state: A `.epic-state.json` object.

    Returns:
        Human-readable violation strings; empty when the state conforms.
    """
    return _check(state, _EPIC_STATE_SCHEMA, _EPIC_STATE_SCHEMA, "$")


def validate_decisions(record: dict) -> list[str]:
    """Validate a forge-decisions object against references/forge-decisions-schema.json.

    Args:
        record: An on-disk ``forge-decisions.json`` document.

    Returns:
        Human-readable violation strings; empty when the record conforms.
    """
    return _check(record, _DECISIONS_SCHEMA, _DECISIONS_SCHEMA, "$")
