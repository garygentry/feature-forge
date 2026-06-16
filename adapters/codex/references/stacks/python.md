# Python Stack Profile

Stack-specific guidance for Python projects (3.10+).

## Stack Identity

- **Language**: Python 3.10+ (required for modern type hint syntax: `X | Y` unions, `match` statements)
- **Package management**: pip, uv, poetry, pdm, or pipenv (check for respective lock/config files)
- **Type checking**: mypy, pyright, or pytype
- **Linting**: ruff, flake8, pylint

## Discovery Checklist

When examining a Python project, check for:

- **Project manifest**: `pyproject.toml` (modern), `setup.py`/`setup.cfg` (legacy), `requirements.txt` (minimal)
- **Package manager**: `uv.lock` (uv), `poetry.lock` (poetry), `pdm.lock` (pdm), `Pipfile.lock` (pipenv)
- **Monorepo**: `pants.toml` (Pants), `BUILD` files (Bazel), `nx.json` with Python plugins, or plain workspace structure
- **Framework**: FastAPI, Django, Flask, Starlette, Litestar
- **Database**: SQLAlchemy, Django ORM, Tortoise ORM, SQLModel
- **Validation**: Pydantic, attrs, marshmallow
- **Testing**: pytest (dominant), unittest
- **Type checking**: `mypy.ini`, `pyrightconfig.json`, or `[tool.mypy]` / `[tool.pyright]` in `pyproject.toml`

## Archetype Conventions

### 00-core-definitions.md (Python)

- **Data structures**: Use `dataclasses` for simple data containers, Pydantic `BaseModel` for validated/serializable models. Use `TypedDict` for dict-shaped data.
- **Type aliases**: Use `type` statements (3.12+) or `TypeAlias` annotation
- **Union types**: Use `X | Y` syntax (3.10+)
- **Protocols**: Use `typing.Protocol` for structural subtyping (Python's equivalent of interfaces)
- **Error/exception hierarchy**: Base exception class inheriting from `Exception` (or a more specific built-in); domain-specific subclasses with typed attributes
- **Constants and enumerations**: Use `enum.Enum`, `enum.StrEnum`, or module-level constants with `Final` annotation
- **Module exports**: Define `__all__` in `__init__.py` for explicit public API

### 01-architecture-layout.md (Python)

- **Project layout**: `src/` layout (recommended) or flat layout
- **pyproject.toml**: `[project]` table with `name`, `dependencies`, `optional-dependencies`, `[project.scripts]` for CLI entry points
- **Tool configuration**: `[tool.pytest.ini_options]`, `[tool.mypy]`, `[tool.ruff]` sections in `pyproject.toml`
- **Module entry points**: `__init__.py` files with explicit `__all__` lists for re-exports
- **Namespace packages**: When applicable, `py.typed` marker for PEP 561 compliance

### Monorepo conventions (if applicable)

- **Workspace structure**: `packages/` or `libs/` directories with individual `pyproject.toml` per package
- **Internal dependencies**: Path dependencies in `pyproject.toml` or editable installs
- **Build coordination**: Pants, Bazel, or Makefile-based orchestration

## Spec Quality Rules

- All Python code must be valid syntax with complete type annotations — not pseudocode
- Use Google-style or NumPy-style docstrings consistently (match project convention)
- Include `Args`, `Returns`, `Raises` sections in docstrings for every public function
- Use `Protocol` classes to define interfaces/contracts
- Include explicit import statements in all code examples
- Use `async def` for asynchronous operations where applicable

### Example: Well-Specified Function

```python
class SessionExpiredError(AuthError):
    """Raised when a session token has expired.

    Attributes:
        expired_at: When the session expired.
    """

    def __init__(self, expired_at: datetime) -> None:
        self.expired_at = expired_at
        super().__init__(
            code="SESSION_EXPIRED",
            message=f"Session expired at {expired_at.isoformat()}",
        )


async def refresh_session_token(
    current_token: str,
    *,
    max_age: timedelta = SESSION_DURATION,
    refresh_threshold: timedelta = REFRESH_THRESHOLD,
    signing_key: bytes,
) -> str | None:
    """Refresh a session token if it's within the refresh threshold.

    Returns a new token with an extended expiry, or None if the session
    is not eligible for refresh (valid but outside threshold).

    Args:
        current_token: The JWT string from the session cookie.
        max_age: Maximum age of a token eligible for refresh.
        refresh_threshold: How close to expiry before refresh is allowed.
        signing_key: Secret key for signing the new token.

    Returns:
        New session token string, or None if refresh is not possible.

    Raises:
        SessionExpiredError: If the token has already expired.
        TokenValidationError: If the token signature is invalid.
    """
    ...
```

## Verification Specifics

- **Type checking**: `mypy .`, `mypy src/`, `pyright`, or `pyright src/`
- **Linting**: `ruff check .` or `flake8`
- **Formatting**: `ruff format --check .` or `black --check .`
- **Import validation**: `mypy` with `--strict` or `--disallow-untyped-defs` catches missing type annotations
- **Module export validation**: `__all__` lists in `__init__.py` match spec's public API

## Testing

- **Framework**: pytest (with `conftest.py` for fixtures)
- **Fixtures**: Define in `conftest.py` at appropriate scope (session, module, function)
- **Mocking**: `unittest.mock.patch`, `monkeypatch` fixture, or `pytest-mock`
- **Coverage**: `pytest-cov` with `--cov=src/` flag
- **Test file location**: `tests/` directory mirroring `src/` structure, or co-located `test_*.py` files
- **Async testing**: `pytest-asyncio` for async function tests
- **Type testing**: Runtime checks with `isinstance()`, static checks with `reveal_type()`

## Common Frameworks

| Category | Options |
|----------|---------|
| Web (async) | FastAPI, Starlette, Litestar |
| Web (sync) | Django, Flask |
| Database ORM | SQLAlchemy, Django ORM, SQLModel, Tortoise ORM |
| Migrations | Alembic (SQLAlchemy), Django migrations |
| Validation | Pydantic, attrs, marshmallow |
| Task queues | Celery, Dramatiq, Huey, ARQ |
| CLI | Click, Typer, argparse |
| HTTP client | httpx, aiohttp, requests |

## Example: Project-Level Override

Create `.claude/references/stack-decisions.md` in your project root:

```markdown
# Stack Decisions

## Runtime & Build
- Python 3.12 with uv for package management
- src/ layout with pyproject.toml

## Backend
- FastAPI for HTTP framework
- SQLAlchemy 2.0 with PostgreSQL (async)
- Pydantic v2 for validation and serialization

## Testing
- pytest with pytest-asyncio
- Factory Boy for test fixtures
- Coverage target: 90%

## Conventions
- Google-style docstrings
- ruff for linting and formatting
- mypy with --strict for type checking
- __all__ exports in every __init__.py
```
