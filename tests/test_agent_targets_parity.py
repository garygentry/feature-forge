"""Drift guard: the generator's AGENT_TARGETS and the test module's copy stay equal.

`scripts/build-adapters.py` declares the six adapter targets (`AGENT_TARGETS`, 00 §1);
`tests/test_build_adapters.py` keeps a local copy it parametrizes its per-target tests
over. Those two constants drifted once already — the test copy stayed a five-tuple after
the `pi` target landed in 0.13.0, so every per-target assertion silently stopped covering
`adapters/pi/`, which is exactly the host the #122/#132 failure class breaks on.

Why this lives in its own module (item 017):

- **YAML-free.** It parses the `AGENT_TARGETS = (...)` literal out of both files with a
  regex instead of importing the generator, which has a hyphenated module name and
  imports `yaml` at module scope.
- **Unskippable.** `tests/test_build_adapters.py` carries a module-level
  `pytest.mark.skipif` that skips the whole file when no available interpreter can
  import `yaml`. A drift guard placed there would silently no-op in exactly the
  environment (bare `python3 -m pytest tests`) where it is most needed. Nothing in this
  module may grow a `skipif` or an `importorskip`.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from _forge_paths import REPO_ROOT, SCRIPTS, read

GENERATOR = SCRIPTS / "build-adapters.py"
TEST_MODULE = Path(__file__).resolve().parent / "test_build_adapters.py"

# The six v1 target agents. Order is FIXED (alphabetical) and is the emit/report
# iteration order (REQ-DET-01) — never sort at runtime, never reorder.
EXPECTED_TARGETS = ("claude", "codex", "copilot", "cursor", "gemini", "pi")

# `AGENT_TARGETS` optionally carries a type annotation in the generator
# (`AGENT_TARGETS: tuple[str, ...] = (...)`) and none in the test module.
_ASSIGNMENT_RE = re.compile(
    r"^AGENT_TARGETS(?:\s*:[^=\n]+)?\s*=\s*(\([^)]*\))",
    re.MULTILINE,
)


def _parse_agent_targets(path: Path) -> tuple[str, ...]:
    """Return the `AGENT_TARGETS` tuple literal declared at module scope in ``path``.

    Regex-extracts the literal and evaluates it with `ast.literal_eval`, so the file is
    never imported — the generator imports `yaml` at module scope and its hyphenated
    name is not importable by `import` anyway.
    """
    matches = _ASSIGNMENT_RE.findall(read(path))
    rel = path.relative_to(REPO_ROOT).as_posix()
    assert matches, f"{rel}: no module-scope `AGENT_TARGETS = (...)` assignment found"
    assert len(matches) == 1, f"{rel}: AGENT_TARGETS assigned {len(matches)}x — which wins?"
    value = ast.literal_eval(matches[0])
    assert isinstance(value, tuple), f"{rel}: AGENT_TARGETS is not a tuple literal"
    return value


def test_generator_declares_the_six_targets():
    """The generator's AGENT_TARGETS is the six-tuple, in the fixed emit order."""
    assert _parse_agent_targets(GENERATOR) == EXPECTED_TARGETS


def test_test_module_declares_the_six_targets():
    """The test module's local copy is the six-tuple — a five-tuple cannot cover pi."""
    assert _parse_agent_targets(TEST_MODULE) == EXPECTED_TARGETS


def test_the_two_constants_are_equal():
    """The two declarations agree, so a new target cannot land untested (item 017)."""
    assert _parse_agent_targets(TEST_MODULE) == _parse_agent_targets(GENERATOR)


def test_this_guard_is_not_skippable():
    """No skip gate may be introduced here — that is the whole point of the module.

    `tests/test_build_adapters.py` skips wholesale without the YAML dep; if this guard
    ever moves behind a `skipif`/`importorskip` it stops running in CI while still
    reading as coverage.
    """
    source = read(Path(__file__).resolve())
    for banned in ("skipif", "importorskip", "pytest.skip"):
        # Only the prose above may mention them; no call may be made.
        assert f"{banned}(" not in source, f"{banned} gate introduced in the drift guard"
