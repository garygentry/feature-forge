"""Guard: every per-feature I/O skill resolves its feature directory (locks Chunk A).

Chunk A fixed the High defect where `skills/forge-verify/SKILL.md` hardcoded
`{specsDir}/{feature}/` for its I/O and so could not locate an epic MEMBER's
state. The fix routes every per-feature read/write through the **Feature Directory
Resolution** block (yielding `{resolvedFeatureDir}`), mirroring its sibling skills.

This test locks that in mechanically: each production skill that does per-feature
I/O MUST reference both the "Feature Directory Resolution" block and
`{resolvedFeatureDir}`. If someone rips the resolution back out and hardcodes a
flat `{specsDir}/{feature}/` I/O path again, the positive assertion fails.

A blanket "no `{specsDir}/{feature}/` anywhere" grep would false-positive: the
string legitimately appears as *shorthand* prose ("resolves to its flat
`{specsDir}/{feature}/` path exactly as today"), in git commands, and in filename
illustrations. So the guard is positive (the resolution machinery is present),
not a raw substring ban.

Excluded by design:
- `forge-0-epic` — epic-scoped (`{specsDir}/{epic}/…`), not per-feature resolution.
- `references/` subtrees — verbatim bundled docs, not the skill's own I/O contract.

Stdlib-only so it runs under bare `pytest tests` (and thus CI's Quality Gate).
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"

# The production skills that perform per-feature I/O (read/write a per-feature
# artifact or state file) and therefore must resolve the feature directory. Epic
# mode (forge-0-epic) is epic-scoped and intentionally absent.
PER_FEATURE_IO_SKILLS: tuple[str, ...] = (
    "forge-1-prd",
    "forge-2-tech",
    "forge-3-specs",
    "forge-4-backlog",
    "forge-5-loop",
    "forge-6-docs",
    "forge-verify",
    "forge-fix",
)


@pytest.mark.parametrize("skill", PER_FEATURE_IO_SKILLS)
def test_skill_resolves_feature_dir(skill: str) -> None:
    """The skill body routes per-feature I/O through Feature Directory Resolution."""
    body = (SKILLS_DIR / skill / "SKILL.md").read_text(encoding="utf-8")
    assert "Feature Directory Resolution" in body, (
        f"{skill}/SKILL.md must reference the **Feature Directory Resolution** block — "
        "per-feature I/O must resolve the dir, never hardcode {specsDir}/{feature}/ (Chunk A)."
    )
    assert "{resolvedFeatureDir}" in body, (
        f"{skill}/SKILL.md must use {{resolvedFeatureDir}} for per-feature reads/writes "
        "(the resolved path is epic-member-aware; a flat hardcode breaks epic members — Chunk A)."
    )


def test_forge_verify_uses_resolved_dir_not_flat_hardcode() -> None:
    """The Chunk-A defect file specifically: forge-verify must not regress to flat I/O.

    forge-verify is the skill the High finding was filed against. It must carry the
    resolution block and use {resolvedFeatureDir}; a bare {specsDir}/{feature}/ may
    still appear only as shorthand prose, which the resolution reference makes explicit.
    """
    body = (SKILLS_DIR / "forge-verify" / "SKILL.md").read_text(encoding="utf-8")
    assert "Feature Directory Resolution" in body and "{resolvedFeatureDir}" in body
