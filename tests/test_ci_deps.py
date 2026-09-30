"""Regression guard for ``tests/_ci_deps.py`` (#336).

CI installs every optional test dep, so a green CI run only ever exercises the successful
import path and cannot tell ``require()`` apart from a plain ``importorskip``. These tests pin
the contract directly: a missing module hard-fails under a truthy ``CI`` and skips otherwise.
"""

from __future__ import annotations

import pytest

from _ci_deps import ci_active, require

MISSING = "forge_ci_deps_probe_module_that_does_not_exist"
TRUTHY = ["true", "1", "yes", "TRUE", " true "]
FALSY = ["", "0", "false", "no", "off", "False", " FALSE "]


@pytest.mark.parametrize("value", TRUTHY)
def test_missing_module_raises_under_truthy_ci(monkeypatch, value):
    monkeypatch.setenv("CI", value)
    assert ci_active()
    with pytest.raises(ImportError):
        require(MISSING)


def test_missing_module_skips_with_ci_unset(monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    assert not ci_active()
    with pytest.raises(pytest.skip.Exception):
        require(MISSING)


@pytest.mark.parametrize("value", FALSY)
def test_missing_module_skips_under_falsy_ci(monkeypatch, value):
    monkeypatch.setenv("CI", value)
    assert not ci_active()
    with pytest.raises(pytest.skip.Exception):
        require(MISSING)


@pytest.mark.parametrize("ci", [None, "true"])
def test_present_module_is_returned(monkeypatch, ci):
    if ci is None:
        monkeypatch.delenv("CI", raising=False)
    else:
        monkeypatch.setenv("CI", ci)
    assert require("json").__name__ == "json"
