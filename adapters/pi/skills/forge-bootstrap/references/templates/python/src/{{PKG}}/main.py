"""Entrypoint module."""


def greet(name: str = "world") -> str:
    """Return a greeting for ``name``.

    Args:
        name: The subject of the greeting.

    Returns:
        A greeting string.
    """
    return f"Hello from {name}"
