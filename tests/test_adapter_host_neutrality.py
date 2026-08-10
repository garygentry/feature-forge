"""Guard test: no leaked Claude-only token or broken grammar in non-Claude adapters.

Chunk B of the plugin-QA remediation, extended by #167. The generator
(scripts/build-adapters.py) degrades Claude-native tool names to host-neutral
phrasing when emitting the codex/copilot/cursor/gemini adapters (see
``_HOST_TERM_REPLACEMENTS`` / ``translate_host_terms``), and — since #167 — runs
the same per-agent pass over the copied ``references/`` closure
(``_translate_reference_host_terms``). This test locks that contract for the
*committed* adapter trees: it walks every non-Claude skill **body** AND every
bundled **reference** markdown file and asserts none of the Claude-only tokens or
the double-article grammar bug survive.

Scope (deliberate):
- Non-Claude targets only — ``claude/`` is authored-verbatim by design (its
  references stay byte-identical to canon; tests/test_build_adapters.py pins that).
- Pi is scanned with its OWN token set: the Pi bundle ships an ``AskUserQuestion``
  compatibility extension, so that token is legitimate there — but Claude's
  ``/clear`` and ``/feature-forge:`` must have degraded to Pi's real ``/new`` /
  ``/skill:`` commands everywhere, references included.
- The #167 translation-exempt reference files (``templates/`` scaffolding,
  ``vendor-construct-inventory.md``, ``portable-root.md``) are scanned WITHOUT
  exemption: they carry zero forbidden tokens today, so an edit that introduces
  one surfaces here as an explicit decision instead of silent drift.

Stdlib-only (no yaml, no generator subprocess) so it runs under bare
``pytest tests`` regardless of the ``.venv-adapters`` provisioning state. It reads
the committed output rather than regenerating, so a hand-edit that reintroduces a
token is caught too, not only a generator regression.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ADAPTERS_ROOT = REPO_ROOT / "adapters"
NON_CLAUDE_TARGETS = ("codex", "copilot", "cursor", "gemini")  # 00 §1 minus claude & pi

# Tokens that must NOT appear in a non-Claude, non-Pi skill body or bundled
# reference. Each is either a literal Claude tool name that the host-term pass is
# supposed to degrade, a Claude-only slash command, or the double-article grammar
# the article-aware pairs kill.
FORBIDDEN_TOKENS: tuple[str, ...] = (
    "the the ",          # double-article (lowercase)
    "The the ",          # double-article (sentence start)
    "`Agent` tool",      # literal Claude subagent tool (backticked)
    "`Skill` tool",      # literal Claude skill-invocation tool (backticked)
    "`Monitor` tool",    # literal Claude monitoring tool (backticked)
    "/clear",            # Claude-only slash command (must degrade to plain prose)
    "AskUserQuestion",   # literal Claude question tool
)

# Pi keeps `AskUserQuestion` (the bundle ships a compatibility extension) and the
# generic tool degradations, but Claude's slash commands must have become Pi's
# real commands (`/new`, `/skill:`) — in bodies AND in the reference closure.
PI_FORBIDDEN_TOKENS: tuple[str, ...] = (
    "the the ",
    "The the ",
    "/clear",            # Pi's fresh-session command is /new
    "/feature-forge:",   # Pi's skill-invocation prefix is /skill:
)


def _scan_paths(target: str) -> list[Path]:
    """Every committed skill body AND reference markdown of one adapter target.

    Walks ``skills/`` (bodies + skill-local ``references/``, both in scope since
    #167) and the bundle-root ``references/`` closure.
    """
    paths: list[Path] = []
    for subdir in ("skills", "references"):
        tree = ADAPTERS_ROOT / target / subdir
        if not tree.is_dir():
            continue
        for path in sorted(tree.rglob("*")):
            if path.suffix in (".md", ".mdc"):
                paths.append(path)
    return paths


def _cases() -> list[tuple[Path, tuple[str, ...]]]:
    cases = [(p, FORBIDDEN_TOKENS) for t in NON_CLAUDE_TARGETS for p in _scan_paths(t)]
    cases += [(p, PI_FORBIDDEN_TOKENS) for p in _scan_paths("pi")]
    return cases


def test_scan_surface_discovered() -> None:
    """Sanity guard: the walk finds files so the token assertion can't pass vacuously."""
    for target in (*NON_CLAUDE_TARGETS, "pi"):
        paths = _scan_paths(target)
        bodies = [p for p in paths if "references" not in p.parts]
        refs = [p for p in paths if "references" in p.parts]
        assert len(bodies) >= 5, (
            f"{target}: expected at least ~one skill body per skill; the adapter "
            f"tree looks unbuilt or the glob is wrong (found {len(bodies)})"
        )
        assert len(refs) >= 10, (
            f"{target}: expected the bundled reference closure in scope (#167); "
            f"found only {len(refs)} reference markdown files"
        )


@pytest.mark.parametrize(
    ("path", "forbidden"),
    _cases(),
    ids=lambda v: str(v.relative_to(ADAPTERS_ROOT)) if isinstance(v, Path) else "",
)
def test_no_leaked_host_token(path: Path, forbidden: tuple[str, ...]) -> None:
    """No non-Claude body or bundled reference carries a leaked Claude token."""
    text = path.read_text(encoding="utf-8")
    leaked = [tok for tok in forbidden if tok in text]
    assert not leaked, (
        f"{path.relative_to(REPO_ROOT)} leaks host-neutral-degradation token(s) "
        f"{leaked!r}. Fix scripts/build-adapters.py `_HOST_TERM_REPLACEMENTS` / "
        f"`_translate_reference_host_terms` and rebuild adapters — do not "
        f"hand-edit adapters/."
    )
