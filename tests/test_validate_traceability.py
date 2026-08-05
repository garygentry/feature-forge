"""Guards for the traceability validator's foreign-id allowlist.

`scripts/validate-traceability.py` is a **blocking** gate — `scripts/validate.sh`
step 8 branches on its exit code — and it ships into every adapter bundle and every
consuming repo. Its allowlist path *subtracts ids from the orphan set*, so a defect
here turns a red gate green: the highest-risk shape of untested code in a validator.
A typo in the comment-stripping or a widened match would silently suppress real
orphans everywhere the file lands.

These guards pin the behavior the allowlist is allowed to have:

- A declared id is **reclassified, never dropped** — it leaves `orphaned_references`
  for `allowed_orphans`, and stays visible to any programmatic reader.
- An **undeclared** orphan is still an orphan, and still exits 1.
- An entry matching nothing surfaces as `unused_allowlist_entries`, so a list cannot
  quietly outlive the quotation that justified it. It is advisory: it does not change
  the exit code.
- `--allow-orphan` **merges** with the file rather than replacing it.
- Comments and blank lines are stripped, and nothing else is.

Stdlib only, driving the real CLI out-of-process — the same runtime `validate.sh`
invokes, so the exit codes asserted here are the ones the gate actually branches on.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from _forge_paths import SCRIPTS

VALIDATOR = SCRIPTS / "validate-traceability.py"

#: The filename the validator discovers automatically inside the specs dir.
ALLOWLIST = ".traceability-allowlist"

#: An id this suite defines in its own PRD, so it is covered and never an orphan.
OWNED = "REQ-OWN-01"

#: Ids the spec text mentions without the PRD defining them — the foreign-quotation
#: shape the allowlist exists to describe.
FOREIGN = "REQ-FOREIGN-01"
FOREIGN_OTHER = "REQ-FOREIGN-02"


def _suite(
    tmp_path: Path,
    *,
    spec_reqs: tuple[str, ...],
    allowlist: str | None = None,
) -> tuple[Path, Path]:
    """Build a minimal suite: a PRD defining OWNED, plus one spec file.

    Args:
        tmp_path: Pytest's per-test temporary directory.
        spec_reqs: Requirement ids the spec file references.
        allowlist: Verbatim allowlist file contents, or None to write no file.

    Returns:
        The PRD path and the specs directory, ready to pass to the CLI.
    """
    specs_dir = tmp_path / "specs" / "demo"
    specs_dir.mkdir(parents=True)

    prd = specs_dir / "PRD.md"
    prd.write_text(f"# PRD\n\n- {OWNED}: a requirement this suite owns.\n", encoding="utf-8")
    (specs_dir / "00-core.md").write_text(
        "# Spec\n\n" + "".join(f"Implements {req}.\n" for req in spec_reqs),
        encoding="utf-8",
    )
    if allowlist is not None:
        (specs_dir / ALLOWLIST).write_text(allowlist, encoding="utf-8")
    return prd, specs_dir


def _run(prd: Path, specs_dir: Path, *extra: str) -> tuple[int, dict]:
    """Drive the validator out-of-process and parse its JSON envelope.

    Args:
        prd: Path to the PRD file.
        specs_dir: Path to the specs directory.
        *extra: Additional CLI arguments, e.g. ``--allow-orphan``.

    Returns:
        The process exit code and the decoded ``--json`` payload.
    """
    result = subprocess.run(
        [sys.executable, str(VALIDATOR), str(prd), str(specs_dir), "--json", *extra],
        capture_output=True,
        text=True,
    )
    assert result.stdout, f"no payload on stdout; stderr was {result.stderr!r}"
    return result.returncode, json.loads(result.stdout)


def test_an_allowlisted_id_is_reclassified_not_dropped(tmp_path: Path):
    """A declared foreign id leaves the orphan set but stays reported."""
    prd, specs_dir = _suite(
        tmp_path, spec_reqs=(OWNED, FOREIGN), allowlist=f"{FOREIGN}\n"
    )
    code, payload = _run(prd, specs_dir)

    assert code == 0, payload
    assert payload["orphaned_references"] == [], payload["orphaned_references"]
    assert payload["allowed_orphans"] == [FOREIGN], payload["allowed_orphans"]
    assert payload["valid"] is True
    assert payload["uncovered_requirements"] == []


def test_an_undeclared_orphan_still_fails_the_gate(tmp_path: Path):
    """Without a declaration the same id is an orphan, and the gate goes red."""
    prd, specs_dir = _suite(tmp_path, spec_reqs=(OWNED, FOREIGN))
    code, payload = _run(prd, specs_dir)

    assert code == 1, payload
    assert payload["orphaned_references"] == [FOREIGN], payload["orphaned_references"]
    assert payload["allowed_orphans"] == [], payload["allowed_orphans"]
    assert payload["valid"] is False


def test_an_entry_matching_nothing_is_reported_but_does_not_fail(tmp_path: Path):
    """A stale entry is surfaced so the list cannot outlive its quotation.

    The exit code deliberately does not move: staleness is a documentation-hygiene
    signal, not a merge blocker, and folding it into the gate would turn every
    consuming repo red on an upgrade.
    """
    prd, specs_dir = _suite(tmp_path, spec_reqs=(OWNED,), allowlist="REQ-GONE-01\n")
    code, payload = _run(prd, specs_dir)

    assert code == 0, payload
    assert payload["unused_allowlist_entries"] == ["REQ-GONE-01"]
    assert payload["allowed_orphans"] == []
    assert payload["valid"] is True


def test_the_cli_flag_merges_with_the_allowlist_file(tmp_path: Path):
    """`--allow-orphan` adds to the file's declarations rather than replacing them."""
    prd, specs_dir = _suite(
        tmp_path,
        spec_reqs=(OWNED, FOREIGN, FOREIGN_OTHER),
        allowlist=f"{FOREIGN}\n",
    )
    code, payload = _run(prd, specs_dir, "--allow-orphan", FOREIGN_OTHER)

    assert code == 0, payload
    assert payload["orphaned_references"] == [], payload["orphaned_references"]
    assert payload["allowed_orphans"] == sorted([FOREIGN, FOREIGN_OTHER])
    assert payload["unused_allowlist_entries"] == []


def test_comments_and_blank_lines_are_stripped(tmp_path: Path):
    """Commentary in the allowlist is not mistaken for a declaration.

    A comment line that survived stripping would become an entry matching nothing,
    so the stale-entry list is the sharpest witness that stripping happened.
    """
    prd, specs_dir = _suite(
        tmp_path,
        spec_reqs=(OWNED, FOREIGN),
        allowlist=(
            "# Quoted from the antecedent feature; see TRACEABILITY.md.\n"
            "\n"
            f"{FOREIGN}  # defined there, not here\n"
            "\n"
        ),
    )
    code, payload = _run(prd, specs_dir)

    assert code == 0, payload
    assert payload["allowed_orphans"] == [FOREIGN], payload["allowed_orphans"]
    assert payload["unused_allowlist_entries"] == [], (
        "a comment or blank line was read as a declaration: "
        f"{payload['unused_allowlist_entries']}"
    )
