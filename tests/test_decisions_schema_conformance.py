"""R4 schema-conformance drift guard for the decision-* verbs (REQ-STATE-01).

`references/forge-decisions-schema.json` is the source of truth for
`forge-decisions.json`, and the three `decision-*` verbs are its only writers/
readers — no skill hand-authors the record, so nothing but a test keeps the
verbs honest against the schema. This module is that test, cloned from
`tests/test_state_schema_conformance.py`: out-of-process invocations against a
temp backlog dir, every on-disk write validated through `validate_decisions()`,
plus the append-only invariants a single-call test cannot see (a later entry
mutating an earlier one, an apply touching more than `appliedAt`/`appliedBy`).

Stdlib only (`jsonschema` is absent in CI): conformance goes through
`tests/_state_schema.py`, and every subprocess call uses `sys.executable`.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from _forge_paths import SCRIPTS, read
from _state_schema import validate_decisions

FORGE_SESSION = SCRIPTS / "forge-session.py"
DECISIONS_RELPATH = Path(".rauf") / "forge-decisions.json"

#: One realistic single invocation per verb (flags beyond `--backlog-dir`).
#: `decision-list` needs a written record first; `decision-apply` needs an
#: unapplied entry — `_verb` seeds both via the SEED record invocation.
VERB_INVOCATIONS: dict[str, tuple[str, ...]] = {
    "decision-record": ("--item", "4", "--question", "Which cache backend?",
                        "--answer", "redis"),
    "decision-list": ("--unapplied",),
    "decision-apply": ("--item", "4",),
}

#: The record invocation that seeds an unapplied entry for the read/apply verbs.
SEED = VERB_INVOCATIONS["decision-record"]


def _backlog_dir(tmp_path: Path, name: str = "demo") -> Path:
    """Create an EMPTY backlog dir (no state dir, no record) under a temp tree."""
    backlog = tmp_path / "specs" / name
    backlog.mkdir(parents=True)
    return backlog


def _run(*argv: str) -> subprocess.CompletedProcess[str]:
    """Invoke `forge-session.py` out-of-process on the interpreter running pytest."""
    return subprocess.run(
        [sys.executable, str(FORGE_SESSION), *argv], capture_output=True, text=True
    )


def _verb(backlog: Path, verb: str, *extra: str) -> dict:
    """Run one verb against `backlog`, assert exit 0, and return the written record.

    `--config` points at an absent file inside the temp tree so the stateDir
    default resolves from the SCHEMA (`.rauf`) via `resolve_loop_runner`,
    hermetically — never from whatever the repo-root `forge.config.json` says.
    """
    config = backlog.parent.parent / "forge.config.json"
    result = _run(verb, "--backlog-dir", str(backlog), *extra, "--config", str(config))
    assert result.returncode == 0, f"{verb}: exit {result.returncode}: {result.stderr}"
    return json.loads((backlog / DECISIONS_RELPATH).read_text(encoding="utf-8"))


def _conforms(record: dict, label: str) -> None:
    """Assert `record` validates against the schema with ZERO findings."""
    findings = validate_decisions(record)
    assert findings == [], f"{label}: {findings}"


# --------------------------------------------------------------------------- #
# 1. Registry completeness + every verb in isolation
# --------------------------------------------------------------------------- #


def test_the_guard_covers_every_registered_decision_verb():
    """A new decision-* verb must not be able to land without joining this guard.

    Keyed to the `decision-` prefix, so `state-decision` (a pipeline-level
    `state-*` verb writing `deferredDecisions[]`, guarded by
    test_state_schema_conformance.py's own scan) is deliberately NOT swept in.
    """
    registered = set(
        re.findall(r'add_parser\(\s*"(decision-[a-z-]+)"', read(FORGE_SESSION))
    )
    assert registered == set(VERB_INVOCATIONS), (
        f"registered {sorted(registered)} != covered {sorted(VERB_INVOCATIONS)}"
    )
    assert len(registered) == 3, f"expected three decision verbs, found {len(registered)}"


@pytest.mark.parametrize("verb", sorted(VERB_INVOCATIONS))
def test_each_verb_leaves_a_schema_conformant_record_on_disk(tmp_path, verb):
    backlog = _backlog_dir(tmp_path)
    if verb != "decision-record":
        _verb(backlog, "decision-record", *SEED)  # list/apply need a record behind them
    _conforms(_verb(backlog, verb, *VERB_INVOCATIONS[verb]), verb)


# --------------------------------------------------------------------------- #
# 2. First-write edge cases
# --------------------------------------------------------------------------- #


def test_the_first_write_seeds_the_full_top_level_stamp(tmp_path):
    """A record against an absent file creates it with all five required fields."""
    backlog = _backlog_dir(tmp_path)
    assert not (backlog / DECISIONS_RELPATH).exists()

    record = _verb(backlog, "decision-record", *SEED)
    _conforms(record, "first write")
    for required in ("schemaVersion", "feature", "createdAt", "updatedAt", "decisions"):
        assert required in record, f"first write is missing top-level '{required}'"
    assert record["schemaVersion"] == "1"
    assert record["feature"] == "demo", "feature must stamp the backlog dir basename"


def test_a_missing_record_lists_empty_at_exit_0(tmp_path):
    """Nothing recorded yet is not a failure — a first launch enumerates cleanly."""
    backlog = _backlog_dir(tmp_path)
    config = str(tmp_path / "forge.config.json")

    result = _run("decision-list", "--backlog-dir", str(backlog), "--unapplied",
                  "--json", "--config", config)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"feature": "demo", "unapplied": [], "count": 0}
    assert not (backlog / DECISIONS_RELPATH).exists(), "decision-list must never write"

    plain = _run("decision-list", "--backlog-dir", str(backlog), "--json",
                 "--config", config)
    assert plain.returncode == 0, plain.stderr
    assert json.loads(plain.stdout) == {"decisions": []}


def test_a_cluster_record_writes_the_shared_cluster_id_per_item(tmp_path):
    """One consolidated decision over two --items shares one clusterId (REQ-CLU-04)."""
    backlog = _backlog_dir(tmp_path)
    record = _verb(
        backlog, "decision-record", "--item", "4", "--item", "7",
        "--question", "Same missing credential?", "--deferred", "--cluster", "c4",
    )
    _conforms(record, "cluster record")
    assert [e["itemId"] for e in record["decisions"]] == ["4", "7"]
    assert all(e["clusterId"] == "c4" for e in record["decisions"])
    assert all(e["answer"] is None and e["deferred"] is True for e in record["decisions"])


# --------------------------------------------------------------------------- #
# 3. The record -> defer -> re-record -> apply sequence (append-only, REQ-DEC-07)
# --------------------------------------------------------------------------- #


def _unapplied(backlog: Path) -> dict:
    """Run `decision-list --unapplied --json` and return the report view."""
    result = _run("decision-list", "--backlog-dir", str(backlog), "--unapplied",
                  "--json", "--config", str(backlog.parent.parent / "forge.config.json"))
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_the_worked_sequence_holds_the_append_only_invariants(tmp_path):
    """02 §6 verbatim: record -> defer -> re-record -> apply, validated per step.

    Asserts the invariants a single call cannot see: entry count only grows,
    earlier entries' audit fields are byte-identical after later writes, apply
    touches only `appliedAt`/`appliedBy` on the LATEST entry, and `--unapplied`
    returns exactly the latest-unapplied-per-item set at each step.
    """
    backlog = _backlog_dir(tmp_path)

    # Step A — answered decision for item 4.
    record = _verb(backlog, "decision-record", "--item", "4",
                   "--question", "Which cache backend?", "--answer", "redis")
    _conforms(record, "after step A")
    entry0 = json.loads(json.dumps(record["decisions"][0]))

    # Step B — deferral for item 7 (answer: null, deferred: true).
    record = _verb(backlog, "decision-record", "--item", "7",
                   "--question", "Missing API key", "--deferred")
    _conforms(record, "after step B")
    assert record["decisions"][0] == entry0, "step B mutated the step-A entry"
    entry1 = json.loads(json.dumps(record["decisions"][1]))
    assert entry1["answer"] is None and entry1["deferred"] is True

    view = _unapplied(backlog)
    assert [e["itemId"] for e in view["unapplied"]] == ["4", "7"]

    # Step C — item 4 re-decided: APPENDS entry2; entry0's audit survives.
    record = _verb(backlog, "decision-record", "--item", "4",
                   "--question", "Which cache backend?", "--answer", "memcached")
    _conforms(record, "after step C")
    assert len(record["decisions"]) == 3, "re-record must append, never overwrite"
    assert record["decisions"][0] == entry0, "re-record mutated the superseded entry"
    assert record["decisions"][1] == entry1

    view = _unapplied(backlog)
    assert [e["itemId"] for e in view["unapplied"]] == ["4", "7"]
    assert view["unapplied"][0]["answer"] == "memcached", "latest entry must win"

    # Step D — apply item 4: stamps ONLY the latest item-4 entry's applied fields.
    before = json.loads(json.dumps(record["decisions"]))
    record = _verb(backlog, "decision-apply", "--item", "4")
    _conforms(record, "after step D")
    assert record["decisions"][:2] == before[:2], "apply touched a non-latest entry"
    applied = record["decisions"][2]
    assert applied["appliedAt"] is not None and applied["appliedBy"] is not None
    untouched = {k: v for k, v in applied.items() if k not in ("appliedAt", "appliedBy")}
    expected = {k: v for k, v in before[2].items() if k not in ("appliedAt", "appliedBy")}
    assert untouched == expected, "apply changed a field beyond appliedAt/appliedBy"

    # Item 4 drops out (latest entry applied); item 7's deferral re-surfaces.
    view = _unapplied(backlog)
    assert [e["itemId"] for e in view["unapplied"]] == ["7"]
    assert view["count"] == 1


def test_unapplied_output_is_sorted_by_item_id(tmp_path):
    backlog = _backlog_dir(tmp_path)
    for item in ("9", "2", "10"):
        _verb(backlog, "decision-record", "--item", item,
              "--question", f"q{item}", "--deferred")
    view = _unapplied(backlog)
    # Lexicographic itemId sort — ids are strings end to end (00 §4.1).
    assert [e["itemId"] for e in view["unapplied"]] == ["10", "2", "9"]


# --------------------------------------------------------------------------- #
# 4. Failure exits — exit 2, Error: on stderr, bytes untouched
# --------------------------------------------------------------------------- #


def _record_path(backlog: Path) -> Path:
    return backlog / DECISIONS_RELPATH


def _assert_refused(result: subprocess.CompletedProcess[str], label: str) -> None:
    assert result.returncode == 2, f"{label}: exit {result.returncode}: {result.stdout}"
    assert result.stderr.startswith("Error:"), f"{label}: {result.stderr!r}"


@pytest.mark.parametrize(
    "extra",
    [
        (),  # neither --answer nor --deferred
        ("--answer", "a", "--deferred"),  # both
    ],
    ids=["neither", "both"],
)
def test_record_refuses_an_illegal_answer_deferred_combo_before_any_write(tmp_path, extra):
    backlog = _backlog_dir(tmp_path)
    result = _run("decision-record", "--backlog-dir", str(backlog),
                  "--item", "4", "--question", "q", *extra,
                  "--config", str(tmp_path / "forge.config.json"))
    _assert_refused(result, f"record {extra!r}")
    assert not _record_path(backlog).exists(), "a refused record must not write"


def test_apply_refuses_an_unknown_item_and_a_double_apply_byte_intact(tmp_path):
    backlog = _backlog_dir(tmp_path)
    config = str(tmp_path / "forge.config.json")
    _verb(backlog, "decision-record", *SEED)

    unknown = _run("decision-apply", "--backlog-dir", str(backlog), "--item", "999",
                   "--config", config)
    _assert_refused(unknown, "apply unknown id")

    assert _run("decision-apply", "--backlog-dir", str(backlog), "--item", "4",
                "--config", config).returncode == 0
    before = _record_path(backlog).read_bytes()
    double = _run("decision-apply", "--backlog-dir", str(backlog), "--item", "4",
                  "--config", config)
    _assert_refused(double, "double apply")
    assert _record_path(backlog).read_bytes() == before, "a refused apply mutated bytes"


CORRUPT = b"{ not json"


@pytest.mark.parametrize("verb", sorted(VERB_INVOCATIONS))
def test_a_corrupt_record_exits_2_and_is_left_byte_identical(tmp_path, verb):
    """No corrupt→{} downgrade anywhere — including the read-only `decision-list`.

    A recovery procedure that silently saw "no unapplied decisions" against a
    corrupt record would falsely claim recovery complete (REQ-REL-02 spirit).
    """
    backlog = _backlog_dir(tmp_path)
    _record_path(backlog).parent.mkdir(parents=True)
    _record_path(backlog).write_bytes(CORRUPT)

    result = _run(verb, "--backlog-dir", str(backlog), *VERB_INVOCATIONS[verb],
                  "--config", str(tmp_path / "forge.config.json"))
    _assert_refused(result, verb)
    assert _record_path(backlog).read_bytes() == CORRUPT, (
        f"{verb} rewrote a corrupt decision record"
    )


def test_a_missing_backlog_dir_is_refused_by_every_verb(tmp_path):
    config = str(tmp_path / "forge.config.json")
    missing = str(tmp_path / "specs" / "nope")
    for verb, extra in sorted(VERB_INVOCATIONS.items()):
        result = _run(verb, "--backlog-dir", missing, *extra, "--config", config)
        _assert_refused(result, verb)


# --------------------------------------------------------------------------- #
# 5. Negative control — the conformance assertions above can go red
# --------------------------------------------------------------------------- #


def test_the_validator_rejects_the_shapes_this_guard_exists_to_catch(tmp_path):
    """Without this, every `== []` above would read as coverage while asserting
    nothing. Hand-built violations of the three load-bearing constraints."""
    backlog = _backlog_dir(tmp_path)
    good = _verb(backlog, "decision-record", *SEED)
    _conforms(good, "control baseline")

    partial_entry = json.loads(json.dumps(good))
    del partial_entry["decisions"][0]["appliedAt"]
    assert validate_decisions(partial_entry), "an entry missing appliedAt validated clean"

    missing_top = {"decisions": []}
    assert validate_decisions(missing_top), (
        "a record missing every top-level required field validated clean"
    )

    extra_field = json.loads(json.dumps(good))
    extra_field["decisions"][0]["surprise"] = "x"
    assert validate_decisions(extra_field), (
        "an entry with an undeclared field validated clean"
    )
