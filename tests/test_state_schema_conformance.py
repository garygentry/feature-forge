"""R4 schema-conformance drift guard (REQ-R4-03).

`references/pipeline-state-schema.json` stays the source of truth for
`.pipeline-state.json` even though R4 removed the per-stage instruction to *read*
it — no skill body loads the schema to author state any more, so nothing but a
test keeps the seven `state-*` verbs honest. This module is that test.

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
    assert len(registered) == 7, f"expected seven state verbs, found {len(registered)}"


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
# 5. The schema itself is unchanged by R4
# --------------------------------------------------------------------------- #

#: sha256 of the VALIDATING CONTRACT of `references/pipeline-state-schema.json` at
#: the pre-feature baseline commit 9a29e846ed510c3b245876a9bf4cc73b8cb60951 ("author
#: backlog v1"), the last commit before any R4 work — i.e. the schema with every
#: `description` key recursively stripped, canonicalized (sorted keys, no
#: whitespace). R4 extracts the WRITES into verbs; it changes no schema, so this
#: digest must never move. A real schema change (a property, type, enum, or required
#: list) belongs to a different feature and updates this constant in the same PR.
#:
#: Why the contract and not the raw bytes: item 020 rewrote the `currentStage`
#: description (only `state-enter` writes that field now, so the enum's `complete`
#: value became unreachable and its prose had to stop claiming otherwise). That is a
#: documentation fix with no effect on what validates — a raw-byte digest could only
#: be re-pinned, which proves nothing, while this digest still proves the contract
#: is untouched. Prose accuracy is asserted separately below.
PRE_R4_SCHEMA_CONTRACT_SHA256 = (
    "52887d60ee504d04b8e78a51ab4d454d7810e75ec11321d191bb4e08092c2936"
)


def _strip_descriptions(node):
    """Recursively drop every `description` key — leaving only what validates."""
    if isinstance(node, dict):
        return {k: _strip_descriptions(v) for k, v in node.items() if k != "description"}
    if isinstance(node, list):
        return [_strip_descriptions(v) for v in node]
    return node


def _schema_contract_digest() -> str:
    contract = _strip_descriptions(json.loads(STATE_SCHEMA.read_text()))
    blob = json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def test_the_state_schema_contract_is_unchanged_since_the_pre_r4_baseline():
    digest = _schema_contract_digest()
    assert digest == PRE_R4_SCHEMA_CONTRACT_SHA256, (
        "the validating contract of references/pipeline-state-schema.json changed — "
        "R4 changes no schema, and item 020's currentStage edit is prose-only "
        f"(pre-R4 {PRE_R4_SCHEMA_CONTRACT_SHA256}, now {digest})"
    )


def test_the_contract_digest_ignores_prose_but_not_structure():
    """Negative control: the digest must be blind to descriptions, not to the schema.

    Without this, a `_strip_descriptions` that stripped too much (or a digest over a
    constant) would satisfy the guard above vacuously.
    """
    schema = json.loads(STATE_SCHEMA.read_text())

    # Rewriting a description does not move the digest.
    prose = json.loads(json.dumps(schema))
    prose["properties"]["currentStage"]["description"] = "totally different prose"
    stripped = json.dumps(
        _strip_descriptions(prose), sort_keys=True, separators=(",", ":")
    ).encode()
    assert hashlib.sha256(stripped).hexdigest() == PRE_R4_SCHEMA_CONTRACT_SHA256

    # Dropping an enum value DOES move it.
    structural = json.loads(json.dumps(schema))
    structural["properties"]["currentStage"]["enum"].remove("complete")
    moved = json.dumps(
        _strip_descriptions(structural), sort_keys=True, separators=(",", ":")
    ).encode()
    assert hashlib.sha256(moved).hexdigest() != PRE_R4_SCHEMA_CONTRACT_SHA256


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
