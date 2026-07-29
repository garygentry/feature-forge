"""Shared canon-path helpers for the feature-forge drift guards.

Every guard added by the `context-efficiency` feature resolves its targets through
this module rather than re-deriving ``REPO_ROOT`` per test file (spec 06 §1). The
guards assert against **canon** — ``skills/``, ``references/``, ``scripts/`` — and
never against the generated ``adapters/`` tree, which is ``test_build_adapters.py``'s
job (the adapter copies legitimately differ; host-term degradation is expected there).

Stdlib only: `jsonschema` is absent in CI, and so is every other third-party package,
so a bare ``python3 -m pytest tests`` must be enough to run anything importing this.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS = REPO_ROOT / "skills"
REFERENCES = REPO_ROOT / "references"
SCRIPTS = REPO_ROOT / "scripts"


def read(path: Path) -> str:
    """Read a canon file as UTF-8; fail loudly if a spec'd file is missing.

    A missing file is a drift failure in its own right — a guard that silently
    skipped it would read as coverage while asserting nothing.
    """
    assert path.is_file(), f"expected canon file missing: {path}"
    return path.read_text(encoding="utf-8")
