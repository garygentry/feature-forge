"""R4 schema-conformance drift guard (REQ-R4-03).

`references/pipeline-state-schema.json` stays the source of truth for
`.pipeline-state.json` even though R4 removed the per-stage instruction to *read*
it — no skill body loads the schema to author state any more, so nothing but a
test keeps the nine `state-*` verbs honest. This module is that test.

It differs from `tests/test_state_verbs.py` on purpose: that file asserts each
verb's CLI contract (which fields it writes, which flags it rejects); this one
asserts only that whatever a verb writes **conforms to the unchanged schema** —
single calls, realistic multi-verb sequences, and the two first-write edge cases
where the state file is partially populated or absent. The defects found during
spec verification (a lone `{"commitHash": ...}` entry, a first-write state
missing the top-level required fields) are invisible to a single-call test and
only surface once verbs run in a real order.

Stdlib only (`jsonschema` is absent in CI): conformance goes through
`tests/_state_schema.py`, and every subprocess call uses `sys.executable`.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from _forge_paths import REFERENCES, SCRIPTS, read
from _state_schema import validate_state

FORGE_SESSION = SCRIPTS / "forge-session.py"
STATE_SCHEMA = REFERENCES / "pipeline-state-schema.json"
STATE_FILENAME = ".pipeline-state.json"

#: One realistic single invocation per verb (flags beyond `--feature`/`--specs-dir`).
VERB_INVOCATIONS: dict[str, tuple[str, ...]] = {
    "state-enter": ("--stage", "forge-1-prd"),
    "state-artifact": ("--stage", "forge-3-specs", "--path", "00-core-definitions.md"),
    "state-complete": ("--stage", "forge-1-prd", "--version", "1", "--artifact", "PRD.md"),
    "state-branch": ("--branch", "forge/demo"),
    "state-note": ("--note", "Rebaselined tokens at impl time."),
    "state-decision": (
        "--question", "Which cache backend?",
        "--rationale", "Deferred until the tech spec picks a storage layer",
        "--target-stage", "forge-2-tech",
        "--raised-by", "forge-1-prd",
    ),
    "state-ecr": (
        "--kind", "add-feature",
        "--target", "sibling-feature",
        "--rationale", "R7 emerged as a distinct feature",
        "--raised-by", "forge-2-tech",
        "--blocks-current", "false",
    ),
    # `skipped` is the one result that needs no completed artifact behind it, so it
    # is the only invocation that works against a never-written state file.
    "state-verify": ("--stage", "forge-1-prd", "--status", "skipped"),
    "state-skip": ("--stage", "forge-6-docs"),
}


def _feature_dir(tmp_path: Path, name: str = "demo") -> Path:
    """Create an EMPTY feature dir (no state file) under a temp specs tree."""
    feature_dir = tmp_path / "specs" / name
    feature_dir.mkdir(parents=True)
    return feature_dir


def _run(*argv: str) -> subprocess.CompletedProcess[str]:
    """Invoke `forge-session.py` out-of-process on the interpreter running pytest."""
    return subprocess.run(
        [sys.executable, str(FORGE_SESSION), *argv], capture_output=True, text=True
    )


def _verb(specs: Path, verb: str, *extra: str) -> dict:
    """Run one verb against `specs`, assert exit 0, and return the written state."""
    result = _run(verb, "--feature", "demo", *extra, "--specs-dir", str(specs))
    assert result.returncode == 0, f"{verb}: exit {result.returncode}: {result.stderr}"
    return json.loads((specs / "demo" / STATE_FILENAME).read_text(encoding="utf-8"))


def _conforms(state: dict, label: str) -> None:
    """Assert `state` validates against the schema with ZERO findings."""
    findings = validate_state(state)
    assert findings == [], f"{label}: {findings}"


# --------------------------------------------------------------------------- #
# 1. Every verb, in isolation
# --------------------------------------------------------------------------- #


def test_the_guard_covers_every_registered_state_verb():
    """A new verb must not be able to land without joining this guard."""
    registered = set(re.findall(r'add_parser\(\s*"(state-[a-z-]+)"', read(FORGE_SESSION)))
    assert registered == set(VERB_INVOCATIONS), (
        f"registered {sorted(registered)} != covered {sorted(VERB_INVOCATIONS)}"
    )
    assert len(registered) == 9, f"expected nine state verbs, found {len(registered)}"


@pytest.mark.parametrize("verb", sorted(VERB_INVOCATIONS))
def test_each_verb_writes_schema_conformant_state(tmp_path, verb):
    specs = _feature_dir(tmp_path).parent
    _conforms(_verb(specs, verb, *VERB_INVOCATIONS[verb]), verb)


# --------------------------------------------------------------------------- #
# 2. Realistic sequences (the defects single calls cannot see)
# --------------------------------------------------------------------------- #


def test_the_authoring_sequence_conforms_after_every_step(tmp_path):
    """enter -> artifact x2 -> complete -> complete --commit-hash.

    Validated after EVERY step, not just at the end: a partially-populated state
    is exactly where the spec-verification defects lived (a `commitHash`-only
    entry with no `status`, a first write missing the top-level required list).
    """
    specs = _feature_dir(tmp_path).parent
    stage = "forge-3-specs"

    state = _verb(specs, "state-enter", "--stage", stage)
    _conforms(state, "after state-enter")
    assert state["stages"][stage]["status"] == "in-progress"

    state = _verb(specs, "state-artifact", "--stage", stage, "--path", "00-core-definitions.md")
    _conforms(state, "after the first state-artifact")

    state = _verb(specs, "state-artifact", "--stage", stage, "--path", "01-architecture.md")
    _conforms(state, "after the second state-artifact")
    assert state["stages"][stage]["artifacts"] == [
        "00-core-definitions.md",
        "01-architecture.md",
    ]

    state = _verb(
        specs, "state-complete", "--stage", stage, "--version", "1",
        "--based-on", "forge-2-tech=1",
        "--artifact", "00-core-definitions.md", "--artifact", "01-architecture.md",
    )
    _conforms(state, "after state-complete (Commit 1)")
    entry = state["stages"][stage]
    assert entry["status"] == "complete" and entry["commitHash"] is None

    state = _verb(
        specs, "state-complete", "--stage", stage, "--version", "1",
        "--commit-hash", "0123456789abcdef0123456789abcdef01234567",
    )
    _conforms(state, "after the state-complete --commit-hash follow-up")
    entry = state["stages"][stage]
    assert entry["commitHash"] == "0123456789abcdef0123456789abcdef01234567"
    # The Commit-2 follow-up must not strip what Commit 1 recorded — a lone
    # {"commitHash": ...} entry violates stageEntry's required: ["status"].
    assert entry["status"] == "complete"
    assert entry["version"] == 1
    assert entry["artifacts"] == ["00-core-definitions.md", "01-architecture.md"]


def test_a_full_pipeline_sequence_across_verbs_conforms(tmp_path):
    """Every verb in one realistic order, against one accumulating state file."""
    specs = _feature_dir(tmp_path).parent

    _conforms(_verb(specs, "state-branch", "--branch", "forge/demo"), "state-branch")
    _conforms(_verb(specs, "state-enter", "--stage", "forge-1-prd"), "state-enter")
    _conforms(
        _verb(specs, "state-decision", "--question", "Which cache backend?",
              "--raised-by", "forge-1-prd", "--target-stage", "forge-2-tech"),
        "state-decision",
    )
    _conforms(
        _verb(specs, "state-complete", "--stage", "forge-1-prd", "--version", "1",
              "--artifact", "PRD.md"),
        "state-complete (prd)",
    )
    _conforms(_verb(specs, "state-enter", "--stage", "forge-2-tech"), "state-enter (tech)")
    _conforms(
        _verb(specs, "state-ecr", "--kind", "redep", "--target", "sibling-feature",
              "--rationale", "the tech spec moved a boundary",
              "--raised-by", "forge-2-tech", "--blocks-current", "true"),
        "state-ecr",
    )
    _conforms(_verb(specs, "state-note", "--note", "handed off mid-stage"), "state-note")
    state = _verb(
        specs, "state-complete", "--stage", "forge-2-tech", "--version", "1",
        "--based-on", "forge-1-prd=1", "--artifact", "TECH-SPEC.md",
    )
    _conforms(state, "state-complete (tech)")

    assert state["branch"] == "forge/demo"
    assert state["notes"] == "handed off mid-stage"
    assert len(state["deferredDecisions"]) == 1
    assert len(state["epicChangeRequests"]) == 1
    assert state["stages"]["forge-2-tech"]["basedOnVersions"] == {"forge-1-prd": 1}


def test_the_schedule_then_passed_sequence_conforms_after_every_step(tmp_path):
    """complete -> auto-verify-pending -> passed, validated at each step.

    The scheduling marker and the terminal result are two DIFFERENT shapes of the
    same `verifyEntry` — a terminal write deletes the scheduling keys rather than
    nulling them, so only a per-step check catches an entry that kept both.
    """
    specs = _feature_dir(tmp_path).parent
    stage, key = "forge-1-prd", "forge-verify-prd"

    _conforms(
        _verb(specs, "state-complete", "--stage", stage, "--version", "1",
              "--artifact", "PRD.md"),
        "before scheduling",
    )

    state = _verb(specs, "state-verify", "--stage", stage,
                  "--status", "auto-verify-pending")
    _conforms(state, "after the auto-verify schedule")
    entry = state["stages"][key]
    assert entry["status"] == "auto-verify-pending"
    assert entry["scheduledStageVersion"] == 1
    assert entry["commitHash"] is None
    assert "verifiedStageVersion" not in entry

    state = _verb(specs, "state-verify", "--stage", stage, "--status", "passed",
                  "--verified-stage-version", "1")
    _conforms(state, "after the passed result")
    entry = state["stages"][key]
    assert entry["status"] == "passed"
    assert entry["verifiedStageVersion"] == 1
    # Deleted, not nulled: `VerifyEntry` is total=False, so absent means "not
    # scheduled" while present-but-null would be a malformed entry (00 §6).
    assert "scheduledAt" not in entry and "scheduledStageVersion" not in entry


def test_the_schedule_findings_applied_sequence_conforms_after_every_step(tmp_path):
    """complete -> auto-verify-pending -> findings-reported -> findings-applied.

    `findings-applied` is the only status that carries prior state forward (the
    report metadata) while DELETING `verifiedStageVersion` — fixes landed, nothing
    re-verified them, so freshness stays unresolved (03 §3.3).
    """
    specs = _feature_dir(tmp_path).parent
    stage, key = "forge-4-backlog", "forge-verify-backlog"

    _verb(specs, "state-complete", "--stage", stage, "--version", "2",
          "--artifact", "backlog.json")
    _conforms(
        _verb(specs, "state-verify", "--stage", stage,
              "--status", "auto-verify-pending"),
        "after the auto-verify schedule",
    )

    state = _verb(
        specs, "state-verify", "--stage", stage, "--status", "findings-reported",
        "--findings-file", "verify/backlog-findings.md", "--findings-count", "4",
        "--verified-stage-version", "2",
    )
    _conforms(state, "after the findings report")
    entry = state["stages"][key]
    assert entry["findingsFile"] == "verify/backlog-findings.md"
    assert entry["findingsCount"] == 4
    assert entry["verifiedStageVersion"] == 2
    assert "scheduledAt" not in entry

    state = _verb(specs, "state-verify", "--stage", stage,
                  "--status", "findings-applied")
    _conforms(state, "after the fixes were applied")
    entry = state["stages"][key]
    assert entry["status"] == "findings-applied"
    assert entry["findingsFile"] == "verify/backlog-findings.md"
    assert entry["findingsCount"] == 4
    assert "fixedAt" in entry
    assert "verifiedStageVersion" not in entry, "applied must not claim freshness"

    # Only a later passed write restores it.
    state = _verb(specs, "state-verify", "--stage", stage, "--status", "passed",
                  "--verified-stage-version", "2")
    _conforms(state, "after the re-verify passed")
    assert state["stages"][key]["verifiedStageVersion"] == 2


# --------------------------------------------------------------------------- #
# 2b. The two-commit hash boundary (07 §4.5, REQ-STATE-01..04)
# --------------------------------------------------------------------------- #
#
# `commitHash` is deliberately UNCONSTRAINED in the schema (a legacy short hash
# must keep validating), so the 40-hex rule lives only at the writer boundary.
# That makes these the tests standing between "full hashes on new writes" and a
# silent regression: the schema cannot catch it.

#: Accepted on a new write, recorded verbatim — the regex takes either case.
ACCEPTED_HASHES = (
    "0123456789abcdef0123456789abcdef01234567",
    "0123456789ABCDEF0123456789ABCDEF01234567",
    "0123456789AbCdEf0123456789aBcDeF01234567",
)

#: Refused before any mutation. 0/7/39/41 bracket the length boundary; 7 is the
#: legacy-looking abbreviation, which is rejected rather than Git-resolved.
REJECTED_HASHES = ("", "a1b2c3d", "0" * 39, "0" * 41, "z" * 40, "0" * 39 + " ")

FULL_HASH = ACCEPTED_HASHES[0]

#: The two writers that accept `--commit-hash`, with the flags each needs to reach
#: its provenance branch against a feature whose forge-1-prd is complete at v1.
COMMIT_HASH_WRITERS = {
    "state-complete": ("--stage", "forge-1-prd", "--version", "1"),
    "state-verify": ("--stage", "forge-1-prd",),
}


def _prd_complete_and_verified(specs: Path) -> None:
    """forge-1-prd complete at v1 with a passed verify entry — both Commit 1s."""
    _verb(specs, "state-complete", "--stage", "forge-1-prd", "--version", "1",
          "--artifact", "PRD.md")
    _verb(specs, "state-verify", "--stage", "forge-1-prd", "--status", "passed",
          "--verified-stage-version", "1")


@pytest.mark.parametrize("verb", sorted(COMMIT_HASH_WRITERS))
@pytest.mark.parametrize("value", ACCEPTED_HASHES)
def test_a_full_hash_is_recorded_verbatim_and_still_conforms(tmp_path, verb, value):
    specs = _feature_dir(tmp_path).parent
    _prd_complete_and_verified(specs)
    key = "forge-1-prd" if verb == "state-complete" else "forge-verify-prd"

    state = _verb(specs, verb, *COMMIT_HASH_WRITERS[verb], "--commit-hash", value)
    _conforms(state, f"{verb} after the Commit-2 follow-up")
    assert state["stages"][key]["commitHash"] == value, "case was not preserved"


@pytest.mark.parametrize("verb", sorted(COMMIT_HASH_WRITERS))
@pytest.mark.parametrize("value", REJECTED_HASHES)
def test_a_short_or_malformed_hash_exits_2_byte_intact(tmp_path, verb, value):
    """Nothing but the writer boundary rejects these — the schema accepts any string."""
    specs = _feature_dir(tmp_path).parent
    _prd_complete_and_verified(specs)
    state_path = specs / "demo" / STATE_FILENAME
    before = state_path.read_bytes()

    result = _run(verb, "--feature", "demo", *COMMIT_HASH_WRITERS[verb],
                  "--commit-hash", value, "--specs-dir", str(specs))
    assert result.returncode == 2, f"{verb} {value!r}: exit {result.returncode}"
    assert result.stderr.startswith("Error:"), f"{verb} {value!r}: {result.stderr!r}"
    assert state_path.read_bytes() == before, f"{verb} {value!r} mutated state"


def test_commit_1_writes_null_and_commit_2_fills_it_in_for_both_writers(tmp_path):
    """REQ-STATE-04, per step: null after Commit 1, the hash after Commit 2."""
    specs = _feature_dir(tmp_path).parent

    state = _verb(specs, "state-complete", "--stage", "forge-1-prd", "--version", "1",
                  "--artifact", "PRD.md")
    _conforms(state, "stage Commit 1")
    assert state["stages"]["forge-1-prd"]["commitHash"] is None

    state = _verb(specs, "state-verify", "--stage", "forge-1-prd", "--status", "passed",
                  "--verified-stage-version", "1")
    _conforms(state, "verify Commit 1")
    assert state["stages"]["forge-verify-prd"]["commitHash"] is None

    state = _verb(specs, "state-complete", "--stage", "forge-1-prd", "--version", "1",
                  "--commit-hash", FULL_HASH)
    _conforms(state, "stage Commit 2")
    assert state["stages"]["forge-1-prd"]["commitHash"] == FULL_HASH

    state = _verb(specs, "state-verify", "--stage", "forge-1-prd",
                  "--commit-hash", FULL_HASH)
    _conforms(state, "verify Commit 2")
    entry = state["stages"]["forge-verify-prd"]
    assert entry["commitHash"] == FULL_HASH
    # Commit 2 records provenance and nothing else (03 §3.4).
    assert entry["status"] == "passed" and entry["verifiedStageVersion"] == 1


def _epic_root(tmp_path: Path, epic: str = "auth-overhaul") -> Path:
    """An epic root carrying a minimal manifest at revision 1; return the specs dir."""
    specs = tmp_path / "specs"
    (specs / epic).mkdir(parents=True)
    (specs / epic / "epic-manifest.json").write_text(
        json.dumps(
            {
                "schemaVersion": "1",
                "epic": epic,
                "title": "Auth overhaul",
                "revision": 1,
                "features": [{"name": "login", "dependsOn": []}],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return specs


@pytest.mark.parametrize("value", ACCEPTED_HASHES)
def test_epic_commit_2_records_the_hash_in_the_documented_minimal_shape(tmp_path, value):
    """`.epic-state.json` has no schema (03 §1), so its shape is asserted literally."""
    specs = _epic_root(tmp_path / value[:8].lower())
    for argv in (
        ("--status", "passed", "--verified-stage-version", "1"),
        ("--commit-hash", value),
    ):
        result = _run("state-verify", "--feature", "auth-overhaul",
                      "--stage", "forge-0-epic", *argv, "--specs-dir", str(specs))
        assert result.returncode == 0, f"{argv}: {result.stderr}"

    state = json.loads(
        (specs / "auth-overhaul" / ".epic-state.json").read_text(encoding="utf-8")
    )
    assert set(state) == {"epic", "updatedAt", "stages"}, sorted(state)
    assert state["epic"] == "auth-overhaul"
    entry = state["stages"]["forge-verify-epic"]
    assert entry["commitHash"] == value
    assert entry["status"] == "passed" and entry["verifiedStageVersion"] == 1


@pytest.mark.parametrize("value", REJECTED_HASHES)
def test_epic_commit_2_rejects_a_malformed_hash_byte_intact(tmp_path, value):
    specs = _epic_root(tmp_path)
    assert _run("state-verify", "--feature", "auth-overhaul", "--stage", "forge-0-epic",
                "--status", "skipped", "--specs-dir", str(specs)).returncode == 0
    state_path = specs / "auth-overhaul" / ".epic-state.json"
    before = state_path.read_bytes()

    result = _run("state-verify", "--feature", "auth-overhaul", "--stage", "forge-0-epic",
                  "--commit-hash", value, "--specs-dir", str(specs))
    assert result.returncode == 2, f"{value!r}: exit {result.returncode}"
    assert result.stderr.startswith("Error:"), f"{value!r}: {result.stderr!r}"
    assert state_path.read_bytes() == before, f"{value!r} mutated the epic state"


# --------------------------------------------------------------------------- #
# 3. First-write edge cases
# --------------------------------------------------------------------------- #


def test_state_branch_as_the_first_verb_conforms(tmp_path):
    """Branch Setup fires before the Entry Stamp, so this can be the FIRST write.

    Nothing has seeded the top-level required fields at that point (finding V-012).
    """
    specs = _feature_dir(tmp_path).parent
    assert not (specs / "demo" / STATE_FILENAME).exists()

    state = _verb(specs, "state-branch", "--branch", "forge/demo")
    _conforms(state, "state-branch as the first write")
    for required in ("feature", "createdAt", "updatedAt", "currentStage",
                     "pipelineStatus", "stages"):
        assert required in state, f"first write is missing top-level '{required}'"


def test_state_artifact_against_a_never_entered_stage_conforms(tmp_path):
    """Without the `{"status": "pending"}` seed this persists a bare
    `{"artifacts": [...]}`, which violates stageEntry's required: ["status"]."""
    specs = _feature_dir(tmp_path).parent

    state = _verb(specs, "state-artifact", "--stage", "forge-6-docs", "--path", "ARCH.md")
    _conforms(state, "state-artifact on a never-entered stage")
    assert state["stages"]["forge-6-docs"]["status"] == "pending"


# --------------------------------------------------------------------------- #
# 4. Corrupt-file refusal — exit 2, bytes untouched
# --------------------------------------------------------------------------- #

CORRUPT = b"{ not json"


@pytest.mark.parametrize("verb", sorted(VERB_INVOCATIONS))
def test_a_corrupt_state_file_exits_2_and_is_left_byte_identical(tmp_path, verb):
    """`_read_state` downgrades corrupt -> {} for the navigator's read-only sweep;
    the write path must NOT inherit that, or a recoverable state file is
    atomically replaced with a near-empty one at exit 0 (finding V-016)."""
    specs = _feature_dir(tmp_path).parent
    state_path = specs / "demo" / STATE_FILENAME
    state_path.write_bytes(CORRUPT)

    result = _run(
        verb, "--feature", "demo", *VERB_INVOCATIONS[verb], "--specs-dir", str(specs)
    )
    assert result.returncode == 2, f"{verb}: exit {result.returncode}: {result.stdout}"
    assert result.stderr.startswith("Error:"), f"{verb}: {result.stderr!r}"
    assert state_path.read_bytes() == CORRUPT, f"{verb} rewrote a corrupt state file"


# --------------------------------------------------------------------------- #
# 5. The schema changed ONLY by this feature's three additive verifyEntry fields
# --------------------------------------------------------------------------- #
#
# Until this feature the guard here was a single sha256 pin over the whole
# validating contract, asserting the schema had not moved at all since the pre-R4
# baseline. That pin can no longer hold: `auto-verify-pending` and the two
# scheduling fields are real, intended, additive schema changes. Re-pinning the
# digest would have replaced a proof with a rubber stamp — the new value proves
# only "whatever is there now is what is there now". So the guard is split:
#
#   * `verifyEntry` — where the change belongs — is compared as a PARSED OBJECT
#     against its pre-feature contract with the three intended additions reversed.
#     Any fourth edit, or a differently-shaped version of one of the three, fails.
#   * everything else is still digest-pinned, over the contract with `verifyEntry`
#     excised. That digest is NOT re-pinned: it is byte-for-byte the value the
#     pre-feature schema produces, so it keeps proving the rest of the schema is
#     untouched.

#: The `verifyEntry` validating contract (descriptions stripped) immediately before
#: this feature. Reversing the intended additions must land exactly here.
PRE_STAGE_EXIT_VERIFY_ENTRY_CONTRACT = {
    "type": "object",
    "required": ["status"],
    "properties": {
        "status": {
            "type": "string",
            "enum": ["pending", "passed", "findings-reported", "findings-applied", "skipped"],
        },
        "findingsFile": {"type": ["string", "null"]},
        "findingsCount": {"type": ["integer", "null"]},
        "verifiedAt": {"type": ["string", "null"], "format": "date-time"},
        "fixedAt": {"type": ["string", "null"], "format": "date-time"},
        "commitHash": {"type": ["string", "null"]},
        "verifiedStageVersion": {"type": ["integer", "null"]},
    },
}

#: The one new status value. Durable auto-verify debt: scheduled, never run.
INTENDED_STATUS_ADDITION = "auto-verify-pending"

#: The two new scheduling properties, as they must validate (descriptions stripped).
INTENDED_SCHEDULING_PROPERTIES = {
    "scheduledAt": {"type": ["string", "null"], "format": "date-time"},
    "scheduledStageVersion": {"type": ["integer", "null"], "minimum": 1},
}

#: sha256 of the validating contract of `references/pipeline-state-schema.json` with
#: `definitions.verifyEntry` REMOVED — descriptions recursively stripped, then
#: canonicalized (sorted keys, no whitespace). Unchanged from the pre-feature schema:
#: this feature touches `verifyEntry` and nothing else. A move here means a property,
#: type, enum, or required list changed somewhere this feature has no business
#: changing, and belongs to a different feature that updates this constant in the
#: same PR.
#:
#: Why the contract and not the raw bytes: item 020 rewrote the `currentStage`
#: description (only `state-enter` writes that field now, so the enum's `complete`
#: value became unreachable and its prose had to stop claiming otherwise). That is a
#: documentation fix with no effect on what validates — a raw-byte digest could only
#: be re-pinned, which proves nothing, while this digest still proves the contract
#: is untouched. Prose accuracy is asserted separately below.
#:
#: Re-pinned by #197 (the docs-skip vocabulary): `definitions.docsStageEntry` was
#: added (stageEntry + `skipped` status + `skippedAt`) and `stages.forge-6-docs`
#: re-pointed at it. That is the whole intended delta; the structural comparison in
#: `test_docs_stage_entry_is_stage_entry_plus_the_skip_vocabulary` (in
#: tests/test_state_verbs.py) pins it exactly, so this digest only ever moves again
#: for a change some feature owns.
SCHEMA_CONTRACT_OUTSIDE_VERIFY_ENTRY_SHA256 = (
    "a9b4e426085b7bd4adcbb99007f5bbf1cc646ebed9654532b4245ed4f77ea85a"
)


def _strip_descriptions(node):
    """Recursively drop every `description` key — leaving only what validates."""
    if isinstance(node, dict):
        return {k: _strip_descriptions(v) for k, v in node.items() if k != "description"}
    if isinstance(node, list):
        return [_strip_descriptions(v) for v in node]
    return node


def _canonical_digest(contract) -> str:
    blob = json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def _schema_contract() -> dict:
    return _strip_descriptions(json.loads(STATE_SCHEMA.read_text()))


def _digest_outside_verify_entry(contract: dict) -> str:
    """Digest the contract with `definitions.verifyEntry` excised."""
    rest = json.loads(json.dumps(contract))
    assert "verifyEntry" in rest["definitions"], "definitions.verifyEntry disappeared"
    rest["definitions"].pop("verifyEntry")
    return _canonical_digest(rest)


def _verify_entry_without_intended_additions(contract: dict) -> dict:
    """Return `verifyEntry` with this feature's three additions reversed.

    Fails loudly (rather than silently no-op'ing) if an addition is missing, so a
    dropped field cannot make the reversal accidentally succeed.
    """
    entry = json.loads(json.dumps(contract["definitions"]["verifyEntry"]))
    enum = entry["properties"]["status"]["enum"]
    assert INTENDED_STATUS_ADDITION in enum, (
        f"{INTENDED_STATUS_ADDITION!r} missing from the verifyEntry status enum: {enum}"
    )
    enum.remove(INTENDED_STATUS_ADDITION)
    for name in INTENDED_SCHEDULING_PROPERTIES:
        assert name in entry["properties"], f"{name} missing from verifyEntry.properties"
        entry["properties"].pop(name)
    return entry


def test_verify_entry_changed_only_by_the_intended_additive_fields():
    """Reverse the three intended edits and the pre-feature object must come back."""
    reduced = _verify_entry_without_intended_additions(_schema_contract())
    assert reduced == PRE_STAGE_EXIT_VERIFY_ENTRY_CONTRACT, (
        "references/pipeline-state-schema.json's verifyEntry changed by more than the "
        "auto-verify-pending status and the two scheduling fields"
    )


def test_the_intended_verify_entry_additions_have_the_specified_shape():
    """The additions are nullable, correctly typed, and bounded as specified."""
    entry = _schema_contract()["definitions"]["verifyEntry"]
    assert INTENDED_STATUS_ADDITION in entry["properties"]["status"]["enum"]
    for name, expected in INTENDED_SCHEDULING_PROPERTIES.items():
        assert entry["properties"][name] == expected, f"{name}: {entry['properties'][name]}"


def test_verify_entry_stays_open_and_leaves_legacy_commit_hashes_loadable():
    """Two things this feature must NOT do (REQ-DEBT-06, REQ-STATE-02).

    `additionalProperties: false` would reject state files a later writer enriches;
    a length or hex pattern on `commitHash` would reject the short hashes legacy
    state already carries, which must keep loading unmigrated.
    """
    entry = _schema_contract()["definitions"]["verifyEntry"]
    assert "additionalProperties" not in entry
    commit_hash = entry["properties"]["commitHash"]
    for banned in ("pattern", "minLength", "maxLength", "format", "enum"):
        assert banned not in commit_hash, f"commitHash gained a {banned} constraint"


#: Constraints that would reject a loaded legacy short hash (REQ-STATE-02).
BANNED_COMMIT_HASH_KEYWORDS = ("pattern", "minLength", "maxLength", "format", "enum")


def _commit_hash_nodes(node, trail=()):
    """Yield every `(path, subschema)` declaring a `commitHash` property."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "commitHash" and isinstance(value, dict):
                yield ".".join((*trail, key)), value
            yield from _commit_hash_nodes(value, (*trail, str(key)))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _commit_hash_nodes(value, (*trail, str(index)))


def test_no_reference_schema_constrains_commit_hash_anywhere():
    """The 40-hex rule is a WRITE boundary, never a schema (03 §6.2).

    A pattern or length here would reject the short hashes legacy state already
    carries — the exact migration REQ-STATE-02 forbids. Every schema is walked,
    not just `verifyEntry`, so `stageEntry` cannot pick one up unnoticed.
    """
    checked = 0
    for schema_path in sorted(REFERENCES.glob("*-schema.json")):
        schema = json.loads(read(schema_path))
        for path, node in _commit_hash_nodes(schema):
            checked += 1
            for banned in BANNED_COMMIT_HASH_KEYWORDS:
                assert banned not in node, (
                    f"{schema_path.name}:{path} gained a {banned} constraint on "
                    f"commitHash; loaded legacy short hashes must keep validating"
                )
    assert checked >= 2, (
        f"expected at least the stageEntry and verifyEntry commitHash nodes, "
        f"found {checked}"
    )


def test_the_rest_of_the_state_schema_contract_is_unchanged():
    digest = _digest_outside_verify_entry(_schema_contract())
    assert digest == SCHEMA_CONTRACT_OUTSIDE_VERIFY_ENTRY_SHA256, (
        "the validating contract of references/pipeline-state-schema.json changed "
        "OUTSIDE definitions.verifyEntry — this feature's schema change is confined "
        f"to verifyEntry (expected {SCHEMA_CONTRACT_OUTSIDE_VERIFY_ENTRY_SHA256}, "
        f"now {digest})"
    )


def test_the_contract_comparison_ignores_prose_but_not_structure():
    """Negative control: the guards above must be blind to prose, not to the schema.

    Without this, a `_strip_descriptions` that stripped too much (or a comparison
    against a constant) would satisfy them vacuously.
    """
    schema = json.loads(STATE_SCHEMA.read_text())

    # Rewriting a description moves neither the digest nor the verifyEntry object.
    prose = json.loads(json.dumps(schema))
    prose["properties"]["currentStage"]["description"] = "totally different prose"
    prose["definitions"]["verifyEntry"]["properties"]["scheduledAt"]["description"] = "x"
    prose_contract = _strip_descriptions(prose)
    assert _digest_outside_verify_entry(prose_contract) == (
        SCHEMA_CONTRACT_OUTSIDE_VERIFY_ENTRY_SHA256
    )
    assert _verify_entry_without_intended_additions(prose_contract) == (
        PRE_STAGE_EXIT_VERIFY_ENTRY_CONTRACT
    )

    # Dropping an enum value outside verifyEntry DOES move the digest.
    structural = json.loads(json.dumps(schema))
    structural["properties"]["currentStage"]["enum"].remove("complete")
    assert _digest_outside_verify_entry(_strip_descriptions(structural)) != (
        SCHEMA_CONTRACT_OUTSIDE_VERIFY_ENTRY_SHA256
    )

    # An unintended FOURTH edit inside verifyEntry DOES fail the object comparison.
    extra = json.loads(json.dumps(schema))
    extra["definitions"]["verifyEntry"]["properties"]["surprise"] = {"type": "string"}
    assert _verify_entry_without_intended_additions(_strip_descriptions(extra)) != (
        PRE_STAGE_EXIT_VERIFY_ENTRY_CONTRACT
    )


def test_a_legacy_verify_entry_still_validates_against_the_updated_schema():
    """REQ-DEBT-06: pre-feature state files load unmigrated.

    The additive change must not strand state written before it — including the
    short `commitHash` values and the absent `verifiedStageVersion` legacy entries
    carry, and including a `stageEntry` with no `version`.
    """
    legacy = {
        "feature": "demo",
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-02T00:00:00Z",
        "currentStage": "forge-2-tech",
        "pipelineStatus": "active",
        "stages": {
            "forge-1-prd": {
                "status": "complete",
                "version": 1,
                "artifacts": ["PRD.md"],
                "commitHash": "a1b2c3d",
            },
            "forge-verify-prd": {
                "status": "passed",
                "findingsFile": None,
                "findingsCount": 0,
                "verifiedAt": "2026-01-02T00:00:00Z",
                "commitHash": "9f8e7d6",
            },
            "forge-2-tech": {"status": "in-progress"},
        },
    }
    _conforms(legacy, "legacy pre-feature state")


def test_the_new_scheduling_fields_validate_when_present():
    """The forward-compatible half: an auto-verify-pending entry conforms too."""
    scheduled = {
        "feature": "demo",
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-07-30T00:00:00Z",
        "currentStage": "forge-1-prd",
        "pipelineStatus": "active",
        "stages": {
            "forge-verify-prd": {
                "status": "auto-verify-pending",
                "scheduledAt": "2026-07-30T00:00:00Z",
                "scheduledStageVersion": 3,
                "commitHash": None,
            }
        },
    }
    _conforms(scheduled, "auto-verify-pending state")


def test_complete_is_retained_in_the_enum_for_backward_compatibility():
    """No writer produces `complete`, but pre-0.14 state files still carry it.

    Item 020 accepted that `currentStage` no longer advances on completion (it is
    "where the pipeline IS", per the schema's own definition, and only `state-enter`
    writes it). Removing the now-unreachable value would invalidate state files
    written before that change, so it stays — as a legacy value.
    """
    schema = json.loads(STATE_SCHEMA.read_text())
    assert "complete" in schema["properties"]["currentStage"]["enum"]


def test_the_currentstage_description_does_not_claim_complete_is_written():
    """The prose must not imply a stage skill still writes `complete` (item 020).

    The pre-item-020 text said "`complete` here means the whole pipeline is done",
    which read as a value some stage produces. Nothing writes it, and a consumer
    that believed the old sentence would test `currentStage == "complete"` and never
    see a finished pipeline.
    """
    description = json.loads(STATE_SCHEMA.read_text())[
        "properties"]["currentStage"]["description"]
    assert "`complete` here means the whole pipeline is done" not in description
    assert "LEGACY" in description, (
        "the currentStage description must mark `complete` as a legacy, "
        "never-written value"
    )
    assert "next_stage()" in description, (
        "the description must point consumers at the derived completeness signal"
    )


# --------------------------------------------------------------------------- #
# 6. Negative control — the conformance assertions above can go red
# --------------------------------------------------------------------------- #


def test_the_validator_rejects_the_shapes_this_guard_exists_to_catch(tmp_path):
    """A drift guard that cannot fail reads as coverage without being it.

    These are the two real spec-verification defects, hand-built: a stage entry
    with only a `commitHash`, and a first write missing the top-level required
    fields. Both MUST produce findings, or every `== []` above is vacuous.
    """
    specs = _feature_dir(tmp_path).parent
    good = _verb(specs, "state-enter", "--stage", "forge-1-prd")
    _conforms(good, "control baseline")

    commit_hash_only = json.loads(json.dumps(good))
    commit_hash_only["stages"]["forge-1-prd"] = {"commitHash": "abc123"}
    assert validate_state(commit_hash_only), "a status-less stage entry validated clean"

    missing_required = {"stages": {}}
    assert validate_state(missing_required), "a state missing every required field validated clean"

    bad_status = json.loads(json.dumps(good))
    bad_status["stages"]["forge-1-prd"]["status"] = "almost-done"
    assert validate_state(bad_status), "an out-of-enum stage status validated clean"
