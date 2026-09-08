"""The ``forge_session`` package: the extracted internals of ``forge-session.py``.

``scripts/forge-session.py`` is a thin, hyphen-named CLI shim that inserts its own
directory on ``sys.path`` and re-exports this package's public and private symbols,
so both its path-loading test oracle and its ``__main__`` CLI entry keep working
with zero changes. The 9.8k-line monolith is being split into cohesive modules
here (#279, #265 P4.1). Every module imports the low-level primitives it shares
from :mod:`forge_session._common` and NEVER from the shim (which would be a
circular import). Verb names, flags, exit codes, and JSON shapes are frozen — the
split is a pure move.
"""
