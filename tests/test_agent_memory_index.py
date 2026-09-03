"""Guard: every `MEMORY.md` index links a file that exists (#265 F5, #266 P0.1).

An agent-memory `MEMORY.md` is a hand-maintained index: one line per pattern file,
loaded into the verifier's context every run. A link to a file that is not there is not
cosmetic — the agent is told a pattern exists, cannot open it, and has no way to know
whether the pattern was retired or the index is wrong. Exactly that is live today:
`pattern_stale_counts_after_split.md` is indexed and absent.

WHAT THIS GUARD CAN AND CANNOT SEE TODAY
----------------------------------------
`.claude/` is **gitignored** (`.gitignore:15`), so the 21 curated pattern files and their
index are never committed and **CI sees none of them**. This guard therefore does real
work on a contributor's machine and finds nothing in CI — which is why it also asserts,
below, that a root which *does* exist carries an index, and why
`test_a_shipped_pattern_root_must_carry_an_index` exists: the moment #273 (P1.4) ships
these under `references/verifier-patterns/`, this file starts guarding a tracked tree
with no edit needed here.

Stating that plainly rather than letting the file read as coverage it does not yet have
is the point — a guard that silently scans an empty tree is the "guard that skips is a
guard that asserts nothing" shape twice over.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import pytest

REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent

#: Every root that may hold an agent-memory tree, in the order they arrived.
#: `.claude/agent-memory/` is the live-but-gitignored one; `references/verifier-patterns/`
#: is where #273 (P1.4) ships them so they reach an installed bundle.
MEMORY_ROOTS: Final[tuple[Path, ...]] = (
    REPO_ROOT / ".claude" / "agent-memory",
    REPO_ROOT / "references" / "verifier-patterns",
)

#: `[label](target)` — the only link form these indexes use.
LINK_RE: Final[re.Pattern[str]] = re.compile(r"\]\(([^)]+)\)")


def _indexes() -> list[Path]:
    """Every `MEMORY.md` under any known root, at any depth (one per agent)."""
    found: list[Path] = []
    for root in MEMORY_ROOTS:
        if root.is_dir():
            found.extend(sorted(root.rglob("MEMORY.md")))
    return found


def _local_links(index: Path) -> list[str]:
    targets = LINK_RE.findall(index.read_text(encoding="utf-8"))
    return [t for t in targets if not t.startswith(("http://", "https://", "#", "mailto:"))]


@pytest.mark.parametrize("index", _indexes(), ids=lambda p: p.parent.name)
def test_every_memory_index_link_resolves(index: Path) -> None:
    """No index line may point at a file that is not beside it."""
    missing = [t for t in _local_links(index) if not (index.parent / t).exists()]
    assert not missing, (
        f"{index.relative_to(REPO_ROOT)} links files that do not exist: {missing}. "
        "The agent loads this index every run, is told the pattern exists, and cannot "
        "open it — restore the file or drop the line; do not leave the index lying."
    )


@pytest.mark.parametrize("index", _indexes(), ids=lambda p: p.parent.name)
def test_every_pattern_file_is_indexed(index: Path) -> None:
    """The other direction: a pattern nobody indexes is a pattern nobody loads.

    Without this, "fix the dangling link" has a second, silent solution — delete the
    line and orphan the file — which passes the guard above while losing the pattern.
    """
    linked = {t for t in _local_links(index)}
    on_disk = {
        p.name for p in index.parent.glob("*.md") if p.name != "MEMORY.md"
    }
    unindexed = sorted(on_disk - linked)
    assert not unindexed, (
        f"{index.relative_to(REPO_ROOT)} does not index: {unindexed}. A pattern file "
        "that no index line points at never reaches the agent's context."
    )


def test_a_shipped_pattern_root_must_carry_an_index() -> None:
    """A root that exists must have an index — this is what goes live at #273 (P1.4).

    Today `references/verifier-patterns/` does not exist, so this asserts nothing about
    it; the moment P1.4 creates it, an index becomes mandatory with no edit here.
    """
    for root in MEMORY_ROOTS:
        if not root.is_dir():
            continue
        indexes = list(root.rglob("MEMORY.md"))
        patterns = [p for p in root.rglob("*.md") if p.name != "MEMORY.md"]
        if patterns:
            assert indexes, (
                f"{root.relative_to(REPO_ROOT)} holds {len(patterns)} pattern file(s) "
                "and no MEMORY.md — an unindexed tree is never loaded"
            )


def test_the_guard_would_catch_a_dangling_link(tmp_path: Path) -> None:
    """Non-vacuity, and the only assertion here that is guaranteed to run in CI.

    Because `.claude/` is gitignored, every parametrized case above can collect to
    nothing on a clean checkout. This one proves the predicate itself rejects a bad
    index, so the file is never merely decorative.
    """
    index = tmp_path / "MEMORY.md"
    (tmp_path / "present.md").write_text("x", encoding="utf-8")
    index.write_text(
        "- [Here](present.md) — fine\n- [Gone](absent.md) — dangling\n", encoding="utf-8"
    )
    missing = [t for t in _local_links(index) if not (index.parent / t).exists()]
    assert missing == ["absent.md"]
