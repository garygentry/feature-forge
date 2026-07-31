"""Drift guard: the two mirrored duplicate-aware JSON loader copies stay identical.

`scripts/forge-session.py` and `scripts/forge-bootstrap.py` each carry their own copy of
``load_json_with_duplicates`` / ``warn_duplicate_keys``. They are **mirrored, not
extracted** (`01-architecture-layout.md` §3.4): every flat script is copied verbatim into
the six per-agent adapter bundles, so the repository's standing invariant is that these
scripts share no import module. A `scripts/forge_json.py` would be the first violation,
would add a seventh `RUNTIME_HELPERS` entry, and would freeze its signature across six
shipped bundles — all to avoid duplicating ~25 lines. The remedy this repository has twice
chosen (`PRODUCTION_STAGES`, `KNOWN_VERIFY_STATUSES`, `AGENT_TARGETS`) is a drift guard.

Why this differs from the sibling guards (`tests/test_stage_constants_parity.py`,
`tests/test_agent_targets_parity.py`):

- **No `ast.literal_eval`.** The mirrored unit is a *pair of functions*, not a literal, so
  the block is extracted by indentation and compared as source text.
- **The `#: mirrors …` comment lies outside the compared region.** The two comments differ
  by design (each names the other file), so comparison starts at the `def` line and the
  comment is asserted separately — the convention that signals duplication must not be
  silently dropped.
- **Unskippable.** Like the modules it follows, nothing here may grow a skip gate: a guard
  that no-ops in a bare ``python3 -m pytest tests`` run reads as coverage while asserting
  nothing.
"""

from __future__ import annotations

import re
import textwrap
from pathlib import Path

from _forge_paths import REPO_ROOT, SCRIPTS, read

SESSION = SCRIPTS / "forge-session.py"
BOOTSTRAP = SCRIPTS / "forge-bootstrap.py"

#: The mirrored pair, in the order both files declare them.
MIRRORED_FUNCTIONS = ("load_json_with_duplicates", "warn_duplicate_keys")

#: Exactly one of these precedes the pair in each file, naming the *other* file.
MIRROR_COMMENT_BY_FILE = {
    SESSION: (
        "#: mirrors ``load_json_with_duplicates``/``warn_duplicate_keys`` "
        "in scripts/forge-bootstrap.py"
    ),
    BOOTSTRAP: (
        "#: mirrors ``load_json_with_duplicates``/``warn_duplicate_keys`` "
        "in scripts/forge-session.py"
    ),
}


def _rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _extract_function(path: Path, name: str) -> str:
    """Return the module-scope source block of ``name`` in ``path``.

    Locates ``def <name>`` and takes through the end of its body by indentation, so the
    nested ``object_from_pairs`` closure comes along intact. The whole block is dedented
    **as a unit** — never per line, which would flatten the nesting and mask a real
    divergence — then trailing whitespace is stripped.
    """
    lines = read(path).splitlines()
    starts = [
        index
        for index, line in enumerate(lines)
        if re.match(rf"^(\s*)def {re.escape(name)}\(", line)
    ]
    assert starts, f"{_rel(path)}: no `def {name}(` found — mirrored copy missing"
    assert len(starts) == 1, (
        f"{_rel(path)}: `def {name}(` declared {len(starts)}x — which copy is canonical?"
    )
    start = starts[0]
    indent = len(lines[start]) - len(lines[start].lstrip())
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if not line.strip():
            continue
        if len(line) - len(line.lstrip()) <= indent:
            end = index
            break
    block = "\n".join(lines[start:end])
    return textwrap.dedent(block).rstrip()


def _extract_pair(path: Path) -> str:
    """Return both mirrored function blocks from ``path``, joined in declaration order."""
    return "\n\n\n".join(_extract_function(path, name) for name in MIRRORED_FUNCTIONS)


def test_extraction_finds_both_functions_in_both_files():
    """Both copies exist before anything is compared — an empty diff is not a pass."""
    for path in (SESSION, BOOTSTRAP):
        for name in MIRRORED_FUNCTIONS:
            block = _extract_function(path, name)
            assert block.startswith(f"def {name}("), (
                f"{_rel(path)}: extracted block for {name} does not start at its def line"
            )
            assert len(block.splitlines()) > 1, (
                f"{_rel(path)}: {name} in {_rel(path)} extracted as a stub, not a body"
            )


def test_the_two_copies_are_identical():
    """The mirrored pair is byte-identical from the `def` line onward in both files."""
    session = _extract_pair(SESSION)
    bootstrap = _extract_pair(BOOTSTRAP)
    assert session == bootstrap, (
        "mirrored JSON loader drifted between the two flat scripts\n\n"
        f"--- {_rel(SESSION)} ---\n{session}\n\n"
        f"--- {_rel(BOOTSTRAP)} ---\n{bootstrap}\n"
    )


def test_each_file_carries_exactly_one_mirrors_comment():
    """Exactly one `#: mirrors …` comment precedes the pair, naming the other file.

    Asserted separately from the body comparison because the two comments differ by
    design; the convention that signals duplication must not be silently dropped.
    """
    for path, expected in MIRROR_COMMENT_BY_FILE.items():
        source = read(path)
        occurrences = source.count(expected)
        assert occurrences == 1, (
            f"{_rel(path)}: expected exactly one `{expected}`, found {occurrences}"
        )
        marker = f"{expected}\ndef {MIRRORED_FUNCTIONS[0]}("
        assert marker in source, (
            f"{_rel(path)}: the `#: mirrors …` comment does not immediately precede "
            f"`def {MIRRORED_FUNCTIONS[0]}(`"
        )
        # A second, stale mirror comment anywhere in the file is drift in its own right.
        assert source.count("#: mirrors ``load_json_with_duplicates``") == 1, (
            f"{_rel(path)}: more than one mirrored-loader comment present"
        )


def test_neither_copy_references_a_host_script_symbol():
    """Error translation stays in the caller — a shared body cannot name `UsageError`.

    A copy that reached for its host script's symbols could not stay byte-identical to
    the other (`05-config-and-distribution.md` §4).
    """
    for path in (SESSION, BOOTSTRAP):
        pair = _extract_pair(path)
        for banned in ("UsageError", "_emit", "SENTINEL_FILENAME", "run("):
            assert banned not in pair, (
                f"{_rel(path)}: mirrored loader references host symbol {banned!r}"
            )


def test_no_shared_json_module_was_extracted():
    """`scripts/forge_json.py` must not exist — the mirror IS the design (01 §3.4)."""
    assert not (SCRIPTS / "forge_json.py").exists(), (
        "scripts/forge_json.py breaks the no-shared-import-module invariant; the "
        "mirrored copies plus this drift guard are the chosen design (01 §3.4)"
    )


def test_this_guard_is_not_skippable():
    """No skip gate may be introduced here — that is the whole point of the module."""
    source = read(Path(__file__).resolve())
    for banned in ("skipif", "importorskip", "pytest.skip"):
        # Only the prose above may mention them; no call may be made.
        assert f"{banned}(" not in source, f"{banned} gate introduced in the drift guard"
