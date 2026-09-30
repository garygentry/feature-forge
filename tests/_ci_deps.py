"""Optional third-party test deps: skip locally when absent, fail loudly under CI.

A handful of guards need a third-party package (``jsonschema`` to validate against the
shipped JSON schemas, ``yaml`` to import or drive ``build-adapters.py``). A bare
``python3 -m pytest tests`` must still work without them, so locally they ``importorskip``.
``bash scripts/validate.sh`` and the quality gate run the suite in the provisioned
``.venv-test`` (``scripts/requirements-test.txt``), so there they are always present — and
under ``CI`` a missing one means the guard went silently inert, which must be a hard import
error, not a SKIP (#314, #336).
"""

from __future__ import annotations

import importlib
import os
from types import ModuleType

import pytest

_FALSY = frozenset({"", "0", "false", "no", "off"})


def ci_active() -> bool:
    """Whether ``CI`` is truthy; unset, empty, ``0``, ``false``, ``no`` and ``off`` mean local."""
    return os.environ.get("CI", "").strip().lower() not in _FALSY


def require(module: str) -> ModuleType:
    """Import ``module``; under a truthy ``CI`` a missing module raises instead of skipping."""
    if ci_active():
        return importlib.import_module(module)
    return pytest.importorskip(module)
