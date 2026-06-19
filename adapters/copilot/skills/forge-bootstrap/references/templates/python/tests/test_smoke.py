"""Smoke test for the scaffolded baseline."""

from {{PKG}}.main import greet


def test_greet() -> None:
    """greet returns the expected greeting."""
    assert greet("world") == "Hello from world"
