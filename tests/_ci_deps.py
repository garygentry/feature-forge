"""Optional third-party test deps: skip locally when absent, fail loudly under CI.

A handful of guards need a third-party package (``jsonschema`` to validate against the
shipped JSON schemas, ``yaml`` to import or drive ``build-adapters.py``). Locally a bare
``python3 -m pytest tests`` must still work without them, so they ``importorskip``. But the
quality gate provisions both for the pytest interpreter (``scripts/requirements-test.txt``,
``scripts/requirements-adapters.txt``), so under ``CI`` a missing one means the guard went
silently inert — that must be a hard import error, not a SKIP (#314, #336).
"""

from __future__ import annotations

import importlib
import os
from types import ModuleType

import pytest


def require(module: str) -> ModuleType:
    """Import ``module``; under ``CI`` a missing module raises instead of skipping."""
    if os.environ.get("CI"):
        return importlib.import_module(module)
    return pytest.importorskip(module)
