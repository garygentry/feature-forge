"""Guard test: no leaked Claude-only token or broken grammar in non-Claude adapters.

Chunk B of the plugin-QA remediation. The generator (scripts/build-adapters.py)
degrades Claude-native tool names to host-neutral phrasing when emitting the
codex/copilot/cursor/gemini adapters (see ``_HOST_TERM_REPLACEMENTS`` /
``translate_host_terms``). This test locks that contract for the *committed*
adapter trees: it walks every non-Claude skill **body** and asserts none of the
Claude-only tokens or the double-article grammar bug survive.

Scope (deliberate):
- Non-Claude targets only — ``claude/`` is authored-verbatim by design.
- Skill **bodies** only — ``references/`` subtrees are copied verbatim (a bundled
  reference doc may legitimately quote a literal tool name), so they are excluded.
  Those residual verbatim-reference leaks are documented-by-design (FINDINGS §D2
  Low) and out of scope here.

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
NON_CLAUDE_TARGETS = ("codex", "copilot", "cursor", "gemini")  # 00 §1 minus claude

# Tokens that must NOT appear in a non-Claude skill body. Each is either a literal
# Claude tool name that the host-term pass is supposed to degrade, a Claude-only
# slash command, or the double-article grammar the article-aware pairs kill.
FORBIDDEN_TOKENS: tuple[str, ...] = (
    "the the ",          # double-article (lowercase)
    "The the ",          # double-article (sentence start)
    "`Agent` tool",      # literal Claude subagent tool (backticked)
    "`Skill` tool",      # literal Claude skill-invocation tool (backticked)
    "`Monitor` tool",    # literal Claude monitoring tool (backticked)
    "/clear",            # Claude-only slash command (must degrade to plain prose)
    "AskUserQuestion",   # literal Claude question tool
)


def _non_claude_skill_bodies() -> list[Path]:
    """Every committed non-Claude skill body, excluding ``references/`` subtrees."""
    bodies: list[Path] = []
    for target in NON_CLAUDE_TARGETS:
        skills_dir = ADAPTERS_ROOT / target / "skills"
        if not skills_dir.is_dir():
            continue
        for path in sorted(skills_dir.rglob("*")):
            if path.suffix not in (".md", ".mdc"):
                continue
            if "references" in path.relative_to(skills_dir).parts:
                continue  # verbatim-by-design; out of scope
            bodies.append(path)
    return bodies


def test_skill_bodies_discovered() -> None:
    """Sanity guard: the walk finds bodies so the token assertion can't pass vacuously."""
    bodies = _non_claude_skill_bodies()
    assert len(bodies) >= 4 * 5, (
        "expected at least ~one skill body per non-Claude target; the adapter "
        f"tree looks unbuilt or the glob is wrong (found {len(bodies)})"
    )


@pytest.mark.parametrize("body", _non_claude_skill_bodies(), ids=lambda p: str(p.relative_to(ADAPTERS_ROOT)))
def test_no_leaked_host_token(body: Path) -> None:
    """No non-Claude skill body carries a leaked Claude token or double-article."""
    text = body.read_text(encoding="utf-8")
    leaked = [tok for tok in FORBIDDEN_TOKENS if tok in text]
    assert not leaked, (
        f"{body.relative_to(REPO_ROOT)} leaks host-neutral-degradation token(s) "
        f"{leaked!r}. Fix scripts/build-adapters.py `_HOST_TERM_REPLACEMENTS` and "
        f"rebuild adapters — do not hand-edit adapters/."
    )
