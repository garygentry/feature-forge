"""Schema tests for ``references/forge-decisions-schema.json``.

Pins the decision-record schema (loop-recovery, REQ-STATE-01): the durable
per-backlog ``forge-decisions.json`` that ``decision-record``/``decision-list``/
``decision-apply`` write against. These are structural pins only — no verbs, no
runner (the R4 conformance half lives in ``test_decisions_schema_conformance.py``).

The schema must stay inside the draft-07 subset ``tests/_state_schema.py``
supports, so a guard asserts no ``oneOf``/``anyOf``/``pattern``/``format``
appears anywhere — otherwise ``validate_decisions()`` would silently pass an
unvalidated construct.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA = REPO_ROOT / "references" / "forge-decisions-schema.json"

UNSUPPORTED_CONSTRUCTS = {"oneOf", "anyOf", "pattern", "format"}


def _schema() -> dict:
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


def test_top_level_shape() -> None:
    """Closed object; required set exact; schemaVersion enum-locked to "1"."""
    schema = _schema()
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "schemaVersion", "feature", "createdAt", "updatedAt", "decisions",
    }
    assert schema["properties"]["schemaVersion"]["enum"] == ["1"]


def test_decisions_array_refs_decision_definition() -> None:
    decisions = _schema()["properties"]["decisions"]
    assert decisions["type"] == "array"
    assert decisions["items"] == {"$ref": "#/definitions/decision"}


def test_decision_definition_shape() -> None:
    """Closed entry; the 8 required fields; clusterId optional."""
    decision = _schema()["definitions"]["decision"]
    assert decision["additionalProperties"] is False
    assert set(decision["required"]) == {
        "itemId", "question", "answer", "deferred",
        "decidedAt", "recordedBy", "appliedAt", "appliedBy",
    }
    props = decision["properties"]
    # clusterId is additive: present in properties, never forced onto entries.
    assert "clusterId" in props
    assert "clusterId" not in decision["required"]
    assert props["clusterId"]["type"] == "string"


def test_nullable_unions_and_deferred_flag() -> None:
    """answer/appliedAt/appliedBy are string-or-null; deferred is boolean."""
    props = _schema()["definitions"]["decision"]["properties"]
    for field in ("answer", "appliedAt", "appliedBy"):
        assert props[field]["type"] == ["string", "null"], field
    assert props["deferred"]["type"] == "boolean"


def _walk_keys(node: object) -> set[str]:
    """Collect every dict key appearing anywhere in the schema tree."""
    keys: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            keys.add(key)
            keys |= _walk_keys(value)
    elif isinstance(node, list):
        for item in node:
            keys |= _walk_keys(item)
    return keys


def test_schema_uses_only_the_supported_draft07_subset() -> None:
    """No oneOf/anyOf/pattern/format anywhere — _check() can validate it all."""
    used = _walk_keys(_schema())
    offending = used & UNSUPPORTED_CONSTRUCTS
    assert not offending, f"unsupported draft-07 constructs in schema: {sorted(offending)}"
