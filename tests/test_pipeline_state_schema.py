"""Schema tests for ``references/pipeline-state-schema.json``.

Pins the additive ``deferredDecisions[]`` field (issue #92 / O3): a structured
alternative to the free-text ``notes`` string for same-feature decisions
postponed to a later stage. The array is optional, so legacy states without it
must still validate (additive-change contract, mirroring ``epicChangeRequests``).

The structural tests run everywhere (no third-party dep). The behavioral
``jsonschema`` tests are best-effort — CI installs pytest+ruff but not
jsonschema, so they skip there (mirroring ``test_forge_bootstrap``'s
schema-validation test); they still exercise the schema locally when the dep is
present.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA = REPO_ROOT / "references" / "pipeline-state-schema.json"


def _schema() -> dict:
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Structural pins — dependency-free, always run
# --------------------------------------------------------------------------- #


def test_deferred_decisions_is_optional_additive_array() -> None:
    """deferredDecisions exists as an array property but is NOT required (additive)."""
    schema = _schema()
    props = schema["properties"]
    assert "deferredDecisions" in props
    assert props["deferredDecisions"]["type"] == "array"
    # The additive contract: it must not be forced onto legacy states.
    assert "deferredDecisions" not in schema.get("required", [])


def test_deferred_decision_item_shape() -> None:
    """Each entry pins its required fields, closed keys, and status lifecycle."""
    item = _schema()["properties"]["deferredDecisions"]["items"]
    assert item["additionalProperties"] is False
    assert set(item["required"]) == {"question", "raisedBy", "raisedAt", "status"}
    props = item["properties"]
    assert set(props) >= {
        "question", "rationale", "targetStage", "raisedBy", "raisedAt", "status",
    }
    # Distinct lifecycle from epicChangeRequests (open/applied/dismissed).
    assert props["status"]["enum"] == ["open", "addressed", "dismissed"]


def test_current_stage_description_is_unambiguous() -> None:
    """O1: the currentStage description no longer says 'or next to start'."""
    desc = _schema()["properties"]["currentStage"]["description"]
    assert "or next to start" not in desc
    # It must anchor to the stored-vs-derived distinction.
    assert "next stage is DERIVED" in desc or "DERIVED" in desc


# --------------------------------------------------------------------------- #
# Behavioral checks — best-effort, skip without jsonschema
# --------------------------------------------------------------------------- #


def _validator():
    jsonschema = pytest.importorskip("jsonschema")
    schema = _schema()
    jsonschema.Draft7Validator.check_schema(schema)
    return jsonschema.Draft7Validator(schema)


def _base_state() -> dict:
    return {
        "feature": "widget",
        "createdAt": "2026-07-01T00:00:00Z",
        "updatedAt": "2026-07-01T00:00:00Z",
        "currentStage": "forge-1-prd",
        "pipelineStatus": "active",
        "stages": {"forge-1-prd": {"status": "in-progress"}},
    }


def test_legacy_state_without_deferred_decisions_validates() -> None:
    _validator().validate(_base_state())


def test_valid_deferred_decision_validates() -> None:
    state = _base_state()
    state["deferredDecisions"] = [
        {
            "question": "Which cache backend?",
            "rationale": "Depends on the storage design in tech spec.",
            "targetStage": "forge-2-tech",
            "raisedBy": "forge-1-prd",
            "raisedAt": "2026-07-01T00:00:00Z",
            "status": "open",
        }
    ]
    _validator().validate(state)


def test_deferred_decision_missing_required_field_fails() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    state = _base_state()
    state["deferredDecisions"] = [
        {"raisedBy": "forge-1-prd", "raisedAt": "2026-07-01T00:00:00Z", "status": "open"}
    ]
    with pytest.raises(jsonschema.ValidationError):
        _validator().validate(state)


def test_deferred_decision_unknown_property_fails() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    state = _base_state()
    state["deferredDecisions"] = [
        {
            "question": "Which cache backend?",
            "raisedBy": "forge-1-prd",
            "raisedAt": "2026-07-01T00:00:00Z",
            "status": "open",
            "targetSTAGE": "forge-2-tech",  # wrong casing → unknown key
        }
    ]
    with pytest.raises(jsonschema.ValidationError):
        _validator().validate(state)


def test_deferred_decision_bad_status_enum_fails() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    state = _base_state()
    state["deferredDecisions"] = [
        {
            "question": "Which cache backend?",
            "raisedBy": "forge-1-prd",
            "raisedAt": "2026-07-01T00:00:00Z",
            "status": "applied",  # valid for epicChangeRequests, not here
        }
    ]
    with pytest.raises(jsonschema.ValidationError):
        _validator().validate(state)
