"""Epic-state schema-conformance drift guard (#181).

`references/epic-state-schema.json` is the schema for `{specsDir}/{epic}/.epic-state.json`
— the epic counterpart of `pipeline-state-schema.json`, previously the one state file
with no schema at all (its shape was pinned only by literal dict fixtures scattered
across the test suite). Its sole sanctioned writer is `forge-session.py state-verify`
for epic targets (`--stage forge-0-epic`, resolved through `_load_epic_state_for_write`),
so — exactly like `tests/test_state_schema_conformance.py` for the member file — nothing
but a test keeps that writer honest against the schema. This module is that test.

Two structural guards ride along:

* **verifyEntry parity.** The stdlib validator (`tests/_state_schema.py`) resolves
  same-file ``#/definitions/*`` refs only, so the epic schema MIRRORS
  ``pipeline-state-schema.json#/definitions/verifyEntry`` instead of cross-file
  referencing it (the issue's preferred ``$ref`` form). The parity test is what makes
  the mirror safe: the two definitions are compared as full parsed objects, so any
  drift — structural or prose — fails loudly and is fixed in both files together.
* **A digest pin over the rest.** The epic schema outside ``definitions.verifyEntry``
  is digest-pinned like its sibling. Re-pin protocol: a change there belongs to a
  feature that owns it — update ``EPIC_SCHEMA_CONTRACT_OUTSIDE_VERIFY_ENTRY_SHA256``
  in the same PR as the intended schema change, and say in that PR what moved.

Stdlib only (`jsonschema` is absent in CI): conformance goes through
`tests/_state_schema.py`, and every subprocess call uses `sys.executable`.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from _forge_paths import REFERENCES, SCRIPTS
from _state_schema import validate_epic_state

FORGE_SESSION = SCRIPTS / "forge-session.py"
EPIC_SCHEMA = REFERENCES / "epic-state-schema.json"
STATE_SCHEMA = REFERENCES / "pipeline-state-schema.json"
EPIC = "auth-overhaul"
EPIC_STATE_FILENAME = ".epic-state.json"
FULL_HASH = "0123456789abcdef0123456789abcdef01234567"


def _epic_root(tmp_path: Path, revision: int = 1) -> Path:
    """An epic root carrying a minimal manifest; return the specs dir."""
    specs = tmp_path / "specs"
    (specs / EPIC).mkdir(parents=True)
    (specs / EPIC / "epic-manifest.json").write_text(
        json.dumps(
            {
                "schemaVersion": "1",
                "epic": EPIC,
                "title": "Auth overhaul",
                "revision": revision,
                "features": [{"name": "login", "dependsOn": []}],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return specs


def _run(*argv: str) -> subprocess.CompletedProcess[str]:
    """Invoke `forge-session.py` out-of-process on the interpreter running pytest."""
    return subprocess.run(
        [sys.executable, str(FORGE_SESSION), *argv], capture_output=True, text=True
    )


def _verify(specs: Path, *extra: str) -> dict:
    """Run one epic-target `state-verify`, assert exit 0, return the written state."""
    result = _run(
        "state-verify", "--feature", EPIC, "--stage", "forge-0-epic",
        *extra, "--specs-dir", str(specs),
    )
    assert result.returncode == 0, f"state-verify {extra}: {result.stderr}"
    return json.loads((specs / EPIC / EPIC_STATE_FILENAME).read_text(encoding="utf-8"))


def _conforms(state: dict, label: str) -> None:
    """Assert `state` validates against the epic-state schema with ZERO findings."""
    findings = validate_epic_state(state)
    assert findings == [], f"{label}: {findings}"


# --------------------------------------------------------------------------- #
# 1. Writer conformance — single writes and realistic sequences
# --------------------------------------------------------------------------- #


def test_skipped_as_the_first_write_conforms(tmp_path):
    """`skipped` needs no completed artifact behind it, so it can be the FIRST write."""
    specs = _epic_root(tmp_path)
    assert not (specs / EPIC / EPIC_STATE_FILENAME).exists()

    state = _verify(specs, "--status", "skipped")
    _conforms(state, "skipped as the first write")
    assert state["epic"] == EPIC
    assert "updatedAt" in state
    assert state["stages"]["forge-verify-epic"]["status"] == "skipped"


def test_the_schedule_then_passed_sequence_conforms_after_every_step(tmp_path):
    """auto-verify-pending -> passed, validated at each step.

    The scheduling marker and the terminal result are two different shapes of the
    same `verifyEntry`; a terminal write deletes the scheduling keys rather than
    nulling them, so only a per-step check catches an entry that kept both.
    """
    specs = _epic_root(tmp_path, revision=3)

    state = _verify(specs, "--status", "auto-verify-pending")
    _conforms(state, "after the auto-verify schedule")
    entry = state["stages"]["forge-verify-epic"]
    assert entry["status"] == "auto-verify-pending"
    # The epic's artifact revision is the MANIFEST revision, never a member version.
    assert entry["scheduledStageVersion"] == 3

    state = _verify(specs, "--status", "passed", "--verified-stage-version", "3")
    _conforms(state, "after the passed result")
    entry = state["stages"]["forge-verify-epic"]
    assert entry["status"] == "passed"
    assert entry["verifiedStageVersion"] == 3
    assert "scheduledAt" not in entry and "scheduledStageVersion" not in entry


def test_the_findings_lifecycle_conforms_after_every_step(tmp_path):
    """findings-reported -> findings-applied -> passed, validated at each step."""
    specs = _epic_root(tmp_path, revision=2)

    state = _verify(
        specs, "--status", "findings-reported",
        "--findings-file", ".verification/VERIFY-epic-2026-08-09.md",
        "--findings-count", "3", "--verified-stage-version", "2",
    )
    _conforms(state, "after the findings report")
    entry = state["stages"]["forge-verify-epic"]
    assert entry["findingsCount"] == 3

    state = _verify(specs, "--status", "findings-applied")
    _conforms(state, "after the fixes were applied")
    entry = state["stages"]["forge-verify-epic"]
    assert entry["status"] == "findings-applied"
    assert "verifiedStageVersion" not in entry, "applied must not claim freshness"

    state = _verify(specs, "--status", "passed", "--verified-stage-version", "2")
    _conforms(state, "after the re-verify passed")
    assert state["stages"]["forge-verify-epic"]["verifiedStageVersion"] == 2


def test_the_commit_hash_follow_up_conforms(tmp_path):
    """The Commit-2 provenance write keeps the file schema-conformant."""
    specs = _epic_root(tmp_path)
    _verify(specs, "--status", "passed", "--verified-stage-version", "1")

    state = _verify(specs, "--commit-hash", FULL_HASH)
    _conforms(state, "after the commit-hash follow-up")
    entry = state["stages"]["forge-verify-epic"]
    assert entry["commitHash"] == FULL_HASH
    assert entry["status"] == "passed"


# --------------------------------------------------------------------------- #
# 2. verifyEntry parity — the mirror cannot drift from pipeline-state-schema
# --------------------------------------------------------------------------- #


def _definition(schema_path: Path) -> dict:
    return json.loads(schema_path.read_text(encoding="utf-8"))["definitions"]["verifyEntry"]


def test_the_epic_verify_entry_mirrors_the_pipeline_state_definition():
    """The two `verifyEntry` definitions are IDENTICAL, prose included.

    The issue asked for `$ref: pipeline-state-schema.json#/definitions/verifyEntry`;
    the repo's stdlib validator resolves same-file refs only, so the definition is
    mirrored instead and THIS test is the alignment the `$ref` would have provided.
    The epic copy may carry one extra top-level `description` (the mirror note);
    everything else — properties, enums, types, per-property prose — must be equal.
    """
    epic_entry = {k: v for k, v in _definition(EPIC_SCHEMA).items() if k != "description"}
    assert epic_entry == _definition(STATE_SCHEMA), (
        "references/epic-state-schema.json#/definitions/verifyEntry has drifted from "
        "pipeline-state-schema.json#/definitions/verifyEntry — the two are a mirror "
        "pair; apply the change to both files in the same commit"
    )


def test_the_mirror_note_names_both_the_reason_and_the_guard():
    """The duplication is documented at the definition, not left to look accidental."""
    description = _definition(EPIC_SCHEMA).get("description", "")
    assert "pipeline-state-schema.json#/definitions/verifyEntry" in description
    assert "test_epic_state_schema_conformance" in description


# --------------------------------------------------------------------------- #
# 3. The digest pin over everything outside verifyEntry
# --------------------------------------------------------------------------- #

#: sha256 of the validating contract of `references/epic-state-schema.json` with
#: `definitions.verifyEntry` REMOVED — descriptions recursively stripped, then
#: canonicalized (sorted keys, no whitespace), matching the sibling pin in
#: tests/test_state_schema_conformance.py. `verifyEntry` is excluded because the
#: parity test above already pins it (to the pipeline schema, where changes to it
#: are themselves guarded). Re-pin protocol: only a feature that OWNS a structural
#: change to the epic-state shape updates this constant, in the same PR as the
#: schema edit, naming the intended delta.
EPIC_SCHEMA_CONTRACT_OUTSIDE_VERIFY_ENTRY_SHA256 = (
    "84ab13e19471581121c63016bfdab5e5a876161a6edd09b0b0cb8854d589830d"
)


def _strip_descriptions(node):
    """Recursively drop every `description` key — leaving only what validates."""
    if isinstance(node, dict):
        return {k: _strip_descriptions(v) for k, v in node.items() if k != "description"}
    if isinstance(node, list):
        return [_strip_descriptions(v) for v in node]
    return node


def _digest_outside_verify_entry() -> str:
    contract = _strip_descriptions(json.loads(EPIC_SCHEMA.read_text(encoding="utf-8")))
    assert "verifyEntry" in contract["definitions"], "definitions.verifyEntry disappeared"
    contract["definitions"].pop("verifyEntry")
    blob = json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def test_the_epic_schema_outside_verify_entry_is_digest_pinned():
    digest = _digest_outside_verify_entry()
    assert digest == EPIC_SCHEMA_CONTRACT_OUTSIDE_VERIFY_ENTRY_SHA256, (
        "the validating contract of references/epic-state-schema.json changed outside "
        "definitions.verifyEntry — if intended, re-pin per this constant's protocol "
        f"(expected {EPIC_SCHEMA_CONTRACT_OUTSIDE_VERIFY_ENTRY_SHA256}, now {digest})"
    )


# --------------------------------------------------------------------------- #
# 4. Corrupt-file refusal — exit 2, bytes untouched
# --------------------------------------------------------------------------- #


def test_a_corrupt_epic_state_file_exits_2_and_is_left_byte_identical(tmp_path):
    specs = _epic_root(tmp_path)
    state_path = specs / EPIC / EPIC_STATE_FILENAME
    state_path.write_bytes(b"{ not json")

    result = _run("state-verify", "--feature", EPIC, "--stage", "forge-0-epic",
                  "--status", "skipped", "--specs-dir", str(specs))
    assert result.returncode == 2, f"exit {result.returncode}: {result.stdout}"
    assert result.stderr.startswith("Error:"), result.stderr
    assert state_path.read_bytes() == b"{ not json", "a corrupt epic state was rewritten"


# --------------------------------------------------------------------------- #
# 5. Negative control — the conformance assertions above can go red
# --------------------------------------------------------------------------- #


def test_the_validator_rejects_the_shapes_this_guard_exists_to_catch(tmp_path):
    """A drift guard that cannot fail reads as coverage without being it."""
    specs = _epic_root(tmp_path)
    good = _verify(specs, "--status", "skipped")
    _conforms(good, "control baseline")

    missing_identity = json.loads(json.dumps(good))
    del missing_identity["epic"]
    assert validate_epic_state(missing_identity), "a state with no epic identity validated clean"

    status_less = json.loads(json.dumps(good))
    status_less["stages"]["forge-verify-epic"] = {"commitHash": "abc123"}
    assert validate_epic_state(status_less), "a status-less verify entry validated clean"

    bad_status = json.loads(json.dumps(good))
    bad_status["stages"]["forge-verify-epic"]["status"] = "almost-verified"
    assert validate_epic_state(bad_status), "an out-of-enum status validated clean"

    bool_version = json.loads(json.dumps(good))
    bool_version["stages"]["forge-verify-epic"] |= {
        "status": "auto-verify-pending", "scheduledStageVersion": True,
    }
    assert validate_epic_state(bool_version), "a boolean scheduledStageVersion validated clean"


def test_parity_would_catch_a_drifted_mirror():
    """Negative control for the parity guard: a one-key drift fails the comparison."""
    drifted = json.loads(json.dumps(_definition(EPIC_SCHEMA)))
    drifted.pop("description", None)
    drifted["properties"]["surprise"] = {"type": "string"}
    assert drifted != _definition(STATE_SCHEMA)
