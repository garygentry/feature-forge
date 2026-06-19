# 03 — Stack Templates

> The per-stack scaffold template **assets** under `skills/forge-bootstrap/references/templates/<stack>/` — their exact file list, complete runnable contents, the four-token substitution, why each baseline is GREEN, monorepo composition, and the CI workflow template.

## Requirement Coverage

| REQ ID | Requirement | Section |
|--------|-------------|---------|
| REQ-STACK-01 | Five stack template directories (ts/python/go/rust/generic) | 1, 2, 3, 4, 5, 6 |
| REQ-STACK-02 | Templates emit a baseline the stack profile's verification commands pass | 2, 3, 4, 5, 6 (each "Why green" + 00 §6 cross-ref) |
| REQ-STACK-03 | Generic baseline is real and zero-dependency | 6 |
| REQ-SCAF-01 | Stack-appropriate runnable structure per member | 2.1, 3.1, 4.1, 5.1, 6.1 |
| REQ-SCAF-02 | Minimal real entrypoint/module per member | 2.2, 3.2, 4.2, 5.2, 6.2 |
| REQ-SCAF-03 | At least one passing test per member | 2.3, 3.3, 4.3, 5.3, 6.3 |
| REQ-SCAF-04 | Stack manifest / build config | 2.2, 3.2, 4.2, 5.2, 6.2 |
| REQ-SCAF-05 | Lint + test resolve to the §6-table commands | 2.4, 3.4, 4.4, 5.4, 6.4 |
| REQ-SCAF-06 | Stack-appropriate `.gitignore` listing the sentinel | 2.5, 3.5, 4.5, 5.5, 6.5 |
| REQ-MONO-01 | One template set composed per member | 8 |
| REQ-MONO-02 | Mixed-language members allowed | 8 |
| REQ-MONO-03 | Aggregate workspace lint + test green | 8 |
| REQ-MONO-04 | CI runs each member's lint + test | 9 |

> Cross-references throughout to `00-core-definitions.md` (the `Stack` enum §2, the per-stack command table §6, token table §6.2, `Member`/`Answers` §5), `02-helper-cli.md` (the `scaffold` / `compose_member` / `write_config` algorithm that *consumes* these assets — this doc specifies only the assets, not that algorithm), and `04-skill-orchestration.md` (the interview that resolves `stack` / `packageManager` / `ci` answers). The directory inventory and 1:1 stack mapping come from `01-architecture-layout.md` §1.1 / §5.

---

## 1. Template Tree Overview (REQ-STACK-01)

Each `Stack` value (`00-core-definitions.md` §2) maps 1:1 to exactly one template directory. The helper resolves the root from `__file__` (`00-core-definitions.md` §1.1), so no env var is needed.

```
skills/forge-bootstrap/references/templates/
  typescript/   package.json, tsconfig.json, src/index.ts, test/smoke.test.ts, .gitignore   (§2)
  python/       pyproject.toml, src/{{PKG}}/__init__.py, src/{{PKG}}/main.py,
                tests/test_smoke.py, .gitignore                                              (§3)
  go/           go.mod, main.go, main_test.go, .gitignore                                    (§4)
  rust/         Cargo.toml, src/lib.rs, src/main.rs, tests/smoke.rs, .gitignore              (§5)
  generic/      run.sh, test.sh, .gitignore                                                  (§6)
  ci/           github-actions.yml                                                            (§9)
  hygiene/      README.md, AGENTS.md, CLAUDE.md                                                (§10)
  licenses/     MIT/LICENSE, Apache-2.0/LICENSE                                                (§10)
```

The five `Stack` directories are composed **per member**; `ci/`, `hygiene/`, and `licenses/` are **repo-level** assets composed once for the whole project (not per member). The files are **editable assets** (`01-architecture-layout.md` §5), not generated. The helper copies them and applies the token substitution of §7. Tokens are shown **in place** below exactly as they appear on disk. Every file content below is real, valid, runnable source in its language — not pseudocode — and is what an implementer commits verbatim.

> **Path tokenization.** Only the **python** template has a token in a *path* segment (`src/{{PKG}}/...`). All other templates carry tokens in file *contents* only. The directory `src/{{PKG}}/` is renamed at compose time by `02-helper-cli.md`'s `compose_member` (this doc does not respecify that rename — it only declares the token).

The `.gitignore` in every stack directory lists the sentinel filename `.forge-bootstrap.json` (`00-core-definitions.md` §3, OQ-T3) as belt-and-suspenders so the transient marker can never be committed even if removal-ordering fails (REQ-SCAF-06).

---

## 2. TypeScript Template (`templates/typescript/`)

### 2.1 File list (REQ-SCAF-01)

| Path (template) | Purpose | Tokens |
|-----------------|---------|--------|
| `package.json` | npm/pnpm/yarn manifest; `test` script → `vitest run`; pins only `typescript` + `vitest` | `{{PROJECT_NAME}}`, `{{PURPOSE}}` |
| `tsconfig.json` | compiler config making `tsc --noEmit` pass | — |
| `src/index.ts` | minimal typed entrypoint module | `{{PROJECT_NAME}}` |
| `test/smoke.test.ts` | one passing Vitest test | — |
| `.gitignore` | Node-appropriate ignores + sentinel | — |

### 2.2 Manifest + entrypoint (REQ-SCAF-02, REQ-SCAF-04)

`package.json` — the `test` script is `vitest run` (non-watch, exits on completion), and dev-deps pin **only** `typescript` and `vitest` (tech-spec §3.5 / OQ-T2, matching `references/stacks/typescript.md`). It is package-manager-agnostic across npm/pnpm/yarn — none of these tokens vary by `{{PM}}` because the `test` script is invoked as `<pm> test` (`00-core-definitions.md` §6) which resolves to `vitest run` under every one of the three.

```json
{
  "name": "{{PROJECT_NAME}}",
  "version": "0.0.0",
  "private": true,
  "description": "{{PURPOSE}}",
  "type": "module",
  "scripts": {
    "typecheck": "tsc --noEmit",
    "test": "vitest run"
  },
  "devDependencies": {
    "typescript": "^5.4.0",
    "vitest": "^1.6.0"
  }
}
```

`tsconfig.json` — strict, no emit, ES modules; `noEmit` keeps `npx tsc --noEmit` purely a type check. The `include` covers both `src` and `test` so the smoke test type-checks too.

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "noEmit": true,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "forceConsistentCasingInFileNames": true,
    "types": ["vitest/globals"]
  },
  "include": ["src", "test"]
}
```

`src/index.ts` — a minimal **typed** entrypoint that exports a pure function (so the smoke test can import it) and is safe to run.

```typescript
/** Returns the project's greeting. */
export function greet(name: string = "{{PROJECT_NAME}}"): string {
  return `Hello from ${name}`;
}
```

### 2.3 Smoke test (REQ-SCAF-03)

`test/smoke.test.ts` — imports the entrypoint and asserts the greeting. Uses Vitest globals (enabled via `types` above), so no per-file import of `describe`/`it`/`expect` is required.

```typescript
import { expect, test } from "vitest";
import { greet } from "../src/index.js";

test("greet returns a greeting", () => {
  expect(greet("world")).toBe("Hello from world");
});
```

### 2.4 Resolved commands (REQ-SCAF-05, REQ-STACK-02)

Per `00-core-definitions.md` §6, with `{{PM}}` ∈ {npm, pnpm, yarn} from the interview (`04-skill-orchestration.md`):

- **lint / typeCheckCommand**: `npx tsc --noEmit`
- **testCommand**: `<pm> test` (resolves to `vitest run`)
- **toolchain probe**: `node`, `<pm>`

### 2.5 `.gitignore` (REQ-SCAF-06)

```gitignore
node_modules/
dist/
*.tsbuildinfo
.forge-bootstrap.json
```

### Why the baseline is GREEN

`tsc --noEmit` with this `tsconfig.json` type-checks `src/index.ts` and `test/smoke.test.ts`: both are fully typed, `greet`'s parameter has a default and explicit `string` return, and `vitest/globals` supplies the test runner types — no type error exists. `vitest run` discovers `test/smoke.test.ts`, imports `greet`, and the assertion `greet("world") === "Hello from world"` holds, so the single test passes and Vitest exits 0. Dev-deps pin exactly the two tools the two commands invoke (`typescript`, `vitest`), so a clean install is sufficient for both to pass under npm/pnpm/yarn alike.

---

## 3. Python Template (`templates/python/`)

### 3.1 File list (REQ-SCAF-01)

| Path (template) | Purpose | Tokens |
|-----------------|---------|--------|
| `pyproject.toml` | PEP 621 manifest; mypy + pytest config | `{{PROJECT_NAME}}`, `{{PKG}}`, `{{PURPOSE}}` |
| `src/{{PKG}}/__init__.py` | package marker with `__all__` | `{{PKG}}` (content) |
| `src/{{PKG}}/main.py` | trivial **typed** module | — |
| `tests/test_smoke.py` | one passing pytest | `{{PKG}}` |
| `.gitignore` | Python-appropriate ignores + sentinel | — |

`{{PKG}}` is the sanitized member identifier (`00-core-definitions.md` §6.2 — `Member.name` lower-cased, hyphens → underscores) and appears both as the `src/{{PKG}}/` directory name and in import paths.

### 3.2 Manifest + module (REQ-SCAF-02, REQ-SCAF-04)

`pyproject.toml` — `src/` layout, Python 3.10+, mypy and pytest configured so `mypy .` and `pytest` both work from the repo root. Install path is via the chosen `{{PM}}` ∈ {uv, poetry, pip} (`04-skill-orchestration.md`); the manifest itself is build-backend-agnostic (`setuptools`), which all three install.

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "{{PROJECT_NAME}}"
version = "0.0.0"
description = "{{PURPOSE}}"
requires-python = ">=3.10"
dependencies = []

[project.optional-dependencies]
dev = ["mypy>=1.8", "pytest>=8.0"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.mypy]
files = ["src", "tests"]
strict = true

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

`src/{{PKG}}/__init__.py` — declares the public surface per `references/stacks/python.md` (`__all__` in `__init__.py`).

```python
"""Package root for {{PKG}}."""

from {{PKG}}.main import greet

__all__ = ["greet"]
```

`src/{{PKG}}/main.py` — a trivial **fully typed** module that passes `mypy --strict` (Google-style docstring, complete annotations, no untyped defs).

```python
"""Entrypoint module."""


def greet(name: str = "world") -> str:
    """Return a greeting for ``name``.

    Args:
        name: The subject of the greeting.

    Returns:
        A greeting string.
    """
    return f"Hello from {name}"
```

### 3.3 Smoke test (REQ-SCAF-03)

`tests/test_smoke.py` — one passing, typed test (so it satisfies `mypy --strict` over `tests` too).

```python
"""Smoke test for the scaffolded baseline."""

from {{PKG}}.main import greet


def test_greet() -> None:
    """greet returns the expected greeting."""
    assert greet("world") == "Hello from world"
```

### 3.4 Resolved commands (REQ-SCAF-05, REQ-STACK-02)

Per `00-core-definitions.md` §6:

- **lint / typeCheckCommand**: `mypy .`
- **testCommand**: `pytest`
- **toolchain probe**: `python3`, `<pm>`

### 3.5 `.gitignore` (REQ-SCAF-06)

```gitignore
__pycache__/
*.py[cod]
.mypy_cache/
.pytest_cache/
*.egg-info/
.venv/
dist/
build/
.forge-bootstrap.json
```

### Why the baseline is GREEN

`mypy .` (configured via `[tool.mypy] files = ["src", "tests"] strict = true`) type-checks the package and tests: `greet` has a complete signature (`str` param with default, `str` return) and the test's function is annotated `-> None` — `--strict` finds no untyped def and no type error. `pytest` (with `pythonpath = ["src"]`) imports `{{PKG}}.main` and the single assertion holds, so the one test passes and pytest exits 0. The dev extras pin exactly `mypy` and `pytest`, the two tools the two commands invoke, installed via uv/poetry/pip.

---

## 4. Go Template (`templates/go/`)

### 4.1 File list (REQ-SCAF-01)

| Path (template) | Purpose | Tokens |
|-----------------|---------|--------|
| `go.mod` | module definition (Go 1.21+) | `{{PKG}}` |
| `main.go` | `package main` entrypoint | `{{PROJECT_NAME}}` |
| `main_test.go` | one passing test | — |
| `.gitignore` | Go-appropriate ignores + sentinel | — |

Go has **no package-manager question** (`00-core-definitions.md` §2 — absent from `PACKAGE_MANAGERS`), so `{{PM}}` never appears here.

### 4.2 Module + entrypoint (REQ-SCAF-02, REQ-SCAF-04)

`go.mod` — `{{PKG}}` is the module path (the sanitized member identifier; a bare name is a valid module path for a local module).

```go
module {{PKG}}

go 1.21
```

`main.go` — `package main` with both a runnable `main` and a pure `greet` helper the test can exercise; passes `go vet ./...`.

```go
package main

import "fmt"

// greet returns the project greeting for name.
func greet(name string) string {
	return "Hello from " + name
}

func main() {
	fmt.Println(greet("{{PROJECT_NAME}}"))
}
```

### 4.3 Smoke test (REQ-SCAF-03)

`main_test.go` — table-driven-friendly single case in `package main`, the idiomatic stdlib `testing` pattern (`references/stacks/go.md`).

```go
package main

import "testing"

func TestGreet(t *testing.T) {
	got := greet("world")
	want := "Hello from world"
	if got != want {
		t.Errorf("greet(\"world\") = %q, want %q", got, want)
	}
}
```

### 4.4 Resolved commands (REQ-SCAF-05, REQ-STACK-02)

Per `00-core-definitions.md` §6:

- **lint / typeCheckCommand**: `go vet ./...`
- **testCommand**: `go test ./...`
- **toolchain probe**: `go`

### 4.5 `.gitignore` (REQ-SCAF-06)

```gitignore
/bin/
*.exe
*.test
*.out
.forge-bootstrap.json
```

### Why the baseline is GREEN

`go vet ./...` finds no suspect constructs: `greet` and `main` are well-formed, `fmt` is imported and used, and there are no format-string or unreachable-code issues. `go test ./...` compiles the `main` package with its test file and runs `TestGreet`, where `greet("world")` equals `"Hello from world"`, so the test passes and the command exits 0. No external dependencies means `go.sum` is unnecessary and the module builds offline.

---

## 5. Rust Template (`templates/rust/`)

### 5.1 File list (REQ-SCAF-01)

| Path (template) | Purpose | Tokens |
|-----------------|---------|--------|
| `Cargo.toml` | package manifest (edition 2021) | `{{PROJECT_NAME}}`, `{{PKG}}`, `{{PURPOSE}}` |
| `src/lib.rs` | reusable public function, linkable from the integration test (§5.2) | — |
| `src/main.rs` | binary crate root that calls the library's `pub fn` | `{{PROJECT_NAME}}` |
| `tests/smoke.rs` | integration test exercising the public fn | `{{PKG}}` |
| `.gitignore` | Rust-appropriate ignores + sentinel | — |

Rust has **no package-manager question**, so `{{PM}}` never appears.

> **Why an integration test can call `greet`.** A binary crate's items are not visible to an external `tests/` crate by default. The template makes the binary *also* expose a library target named `{{PKG}}` (via `[[bin]]` + `[lib]` backed by a small `src/lib.rs` below, which `src/main.rs` also calls), so `tests/smoke.rs` imports `{{PKG}}::greet`. This is the smallest valid setup that keeps both `cargo clippy` and `cargo test` (which builds the integration test) green.

### 5.2 Manifest + crate (REQ-SCAF-02, REQ-SCAF-04)

`Cargo.toml` — declares both a library and a binary so the integration test can link the public function. `{{PKG}}` (sanitized, valid crate name: lowercase, underscores) is the crate name.

```toml
[package]
name = "{{PKG}}"
version = "0.0.0"
edition = "2021"
description = "{{PURPOSE}}"

[lib]
name = "{{PKG}}"
path = "src/lib.rs"

[[bin]]
name = "{{PKG}}"
path = "src/main.rs"

[dependencies]
```

`src/lib.rs` — the reusable public function (so both the binary and the integration test can use it).

```rust
//! Library root for the scaffolded baseline.

/// Returns the project greeting for `name`.
#[must_use]
pub fn greet(name: &str) -> String {
    format!("Hello from {name}")
}
```

`src/main.rs` — the binary entrypoint, importing from the library crate.

```rust
use {{PKG}}::greet;

fn main() {
    println!("{}", greet("{{PROJECT_NAME}}"));
}
```

> The §5.1 file list names `Cargo.toml`, `src/main.rs`, `tests/smoke.rs`, `.gitignore`; `src/lib.rs` is the load-bearing fourth source file that makes the public function linkable from the integration test. It is part of the rust template's asset set (an implementer commits all five files: the four listed plus `src/lib.rs`).

### 5.3 Smoke test (REQ-SCAF-03)

`tests/smoke.rs` — integration test (separate crate) calling the public function via the library crate name `{{PKG}}`.

```rust
use {{PKG}}::greet;

#[test]
fn greet_returns_greeting() {
    assert_eq!(greet("world"), "Hello from world");
}
```

### 5.4 Resolved commands (REQ-SCAF-05, REQ-STACK-02)

Per `00-core-definitions.md` §6:

- **lint / typeCheckCommand**: `cargo clippy`
- **testCommand**: `cargo test`
- **toolchain probe**: `cargo`

### 5.5 `.gitignore` (REQ-SCAF-06)

```gitignore
/target/
Cargo.lock
.forge-bootstrap.json
```

> `Cargo.lock` is ignored because the baseline is a library+binary scaffold with no dependencies; ignoring it keeps the baseline clean. (An implementer may keep it for a binary-only convention; the no-dependency baseline makes the choice immaterial to green-ness.)

### Why the baseline is GREEN

`cargo clippy` compiles the library, binary, and (in the default profile) finds no lints: `greet` is idiomatic (`&str` in, owned `String` out, `#[must_use]`, `format!`), `main` uses the imported function, and there are no dead-code or style warnings. `cargo test` builds the integration test crate, links `{{PKG}}::greet`, and runs `greet_returns_greeting`, where `greet("world") == "Hello from world"` — the assertion passes and `cargo test` exits 0. No `[dependencies]` means the build is offline and reproducible.

---

## 6. Generic Template (`templates/generic/`)

> The generic baseline assumes **no language toolchain** — only a POSIX shell (REQ-STACK-03). `_generic.md` specifies no concrete verification command, so the commands are **bootstrap-defined** (`00-core-definitions.md` §6.1, tech-spec §3.6).

### 6.1 File list (REQ-SCAF-01)

| Path (template) | Purpose | Tokens |
|-----------------|---------|--------|
| `run.sh` | POSIX entrypoint that prints a greeting | `{{PROJECT_NAME}}` |
| `test.sh` | runs `run.sh` and **asserts** its output | — |
| `.gitignore` | minimal ignores + sentinel | — |

Generic has no package-manager question, so `{{PM}}` never appears.

### 6.2 Entrypoint (REQ-SCAF-02)

`run.sh` — a portable `sh` script (no bashisms) that prints a deterministic greeting. It must be emitted with the executable bit so `./run.sh` is invocable; `02-helper-cli.md`'s `compose_member` sets mode `0755` on `*.sh` artifacts.

```sh
#!/bin/sh
# Entrypoint for the scaffolded baseline.
echo "Hello from {{PROJECT_NAME}}"
```

### 6.3 Behavioral test (REQ-SCAF-03, REQ-STACK-03)

`test.sh` — runs `run.sh`, captures stdout, and **asserts** it matches the expected greeting, exiting non-zero on any mismatch (a real behavioral assertion, not a smoke no-op). Note: `{{PROJECT_NAME}}` is substituted at compose time, so the `expected` string below becomes the concrete project name and matches `run.sh`'s output exactly.

```sh
#!/bin/sh
# Behavioral test: run the entrypoint and assert its output.
set -eu

actual="$(./run.sh)"
expected="Hello from {{PROJECT_NAME}}"

if [ "$actual" != "$expected" ]; then
  printf 'FAIL: expected %s but got %s\n' "$expected" "$actual" >&2
  exit 1
fi

printf 'PASS: run.sh produced the expected greeting\n'
```

### 6.4 Resolved commands (REQ-SCAF-05, REQ-STACK-02, REQ-STACK-03)

Per `00-core-definitions.md` §6 / §6.1:

- **lint / typeCheckCommand**: `sh -n run.sh test.sh` (POSIX syntax check of both scripts)
- **testCommand**: `./test.sh`
- **toolchain probe**: `sh`

### 6.5 `.gitignore` (REQ-SCAF-06)

```gitignore
*.log
.forge-bootstrap.json
```

### Why the baseline is GREEN

`sh -n run.sh test.sh` parses both scripts without executing them; both are valid POSIX shell (no bashisms, balanced `if`/`fi`), so the syntax check exits 0. `./test.sh` runs `./run.sh`, which (after token substitution) prints `Hello from <project>`; the captured `actual` equals the substituted `expected`, the `[ ... != ... ]` branch is not taken, and the script prints `PASS` and exits 0. On any output drift the `if` branch fires and exits 1 — a genuine behavioral assertion. Both commands depend only on `sh`, which the probe confirms, so the baseline is real and green with no language toolchain (REQ-STACK-03).

---

## 7. Token Substitution Mechanics (`00-core-definitions.md` §6.2)

Substitution is **simple string replacement — not a templating engine** (tech-spec §3.5). The four tokens and their replacements (canonical table: `00-core-definitions.md` §6.2):

| Token | Replaced with | Source |
|-------|---------------|--------|
| `{{PROJECT_NAME}}` | `Answers.projectName` | `00` §5 |
| `{{PKG}}` | the member's sanitized package identifier | `00` §5 / §6.2 |
| `{{PM}}` | the member's `packageManager` (where applicable) | `00` §5 |
| `{{PURPOSE}}` | `Answers.purpose` | `00` §5 |
| `{{AUTHOR}}` | `Answers.author` (hygiene/license assets only, §10) | `00` §5 / §6.2 |
| `{{YEAR}}` | current UTC year, helper-computed (hygiene/license assets only, §10) | `00` §6.2 |
| `{{LICENSE}}` | `Answers.license` (hygiene README only, §10) | `00` §5 / §6.2 |

Rules (this doc specifies the *contract* the assets rely on; `02-helper-cli.md` §4 owns the implementing code):

1. **Literal, global replacement.** Every occurrence of a token's exact literal `{{TOKEN}}` is replaced with its value, in both file **contents** and **path** segments. No conditionals, loops, or expressions exist in the templates.
2. **`{{PKG}}` sanitization.** `{{PKG}}` is `Member.name` lower-cased with non-alphanumeric runs collapsed to a single `_` (e.g. `My-API` → `my_api`). This is the only token that must also be a valid identifier in Python (package dir + import), Go (module path), and Rust (crate name). The sanitization is defined in `00-core-definitions.md` §6.2 and applied by `02-helper-cli.md`.
3. **`{{PM}}` scope.** `{{PM}}` appears in **no** template file content above — `<pm>` lives only in the *resolved command strings* (`<pm> test`), not in the assets. It is listed for completeness; a future template that embeds the package manager (e.g. a lockfile-aware CI hint) would use it.
4. **Determinism.** Given identical `Answers`, substitution is byte-for-byte deterministic — the per-stack pytest cases (`tests/test_forge_bootstrap.py`, `05`) assert exact composed output.
5. **No escaping needed.** Tokens never appear inside string literals that legitimately contain `{{...}}`; the templates are authored so that the only `{{...}}` sequences are the four tokens.

Example (python member, `projectName="acme-svc"`, `Member.name="acme-svc"` → `{{PKG}}` = `acme_svc`, `purpose="Billing service"`): `src/{{PKG}}/main.py` is written to `src/acme_svc/main.py`, and `pyproject.toml`'s `name = "{{PROJECT_NAME}}"` becomes `name = "acme-svc"`, `description = "Billing service"`.

---

## 8. Monorepo Composition (REQ-MONO-01/02/03)

A monorepo (`Answers.layout == "monorepo"`, `00-core-definitions.md` §5) has **one `Member` per package**; the helper composes **one full template set per member** into that member's `path` (REQ-MONO-01). A single-package project is the degenerate case: one implicit `Member` with `path == "."` composed at the repo root (`00-core-definitions.md` §5 note). This doc specifies what the per-member composition *produces*; the loop that drives it lives in `02-helper-cli.md` §4 (`scaffold` → `compose_member` per member).

### 8.1 Per-member composition

For each `Member m`:

1. Select `templates/<m.stack>/` (REQ-MONO-02 — `m.stack` is independent per member, so members may be **mixed-language**: e.g. `packages/api` python + `packages/web` typescript + `crates/engine` rust).
2. Copy every file in that directory into `<target>/<m.path>/`, applying §7 substitution with `m`'s identifiers (`{{PKG}}` = sanitized `m.name`; `{{PM}}` = `m.packageManager`).
3. Each member's `.gitignore`, manifest, entrypoint, and smoke test land **scoped to its own directory**, so members are self-contained and independently runnable (REQ-SCAF-01/02/03 per member).

> **Token scoping is per member.** `{{PROJECT_NAME}}` is the *project* name (`Answers.projectName`) and is identical across members; `{{PKG}}` / `{{PM}}` are the *member's* values. So two members of different stacks each get a correct, self-consistent scaffold.

### 8.2 Aggregate green-ness (REQ-MONO-03)

Each member's resolved lint + test (the §6-table commands for `m.stack`) are recorded in `workspaces[].typeCheckCommand` / `testCommand` (`00-core-definitions.md` §7.1). The workspace is "green" iff **every** member's lint and test pass. Because each per-member scaffold is individually green (§§2–6 "Why green"), and the scaffolds are directory-isolated (no shared manifest, no cross-member import in the baseline), composing N members yields N independently-green packages — their conjunction is green (REQ-MONO-03). `verify` runs each member's commands in `<m.path>` and reports one `CommandOutcome` per member per phase (`00-core-definitions.md` §4); `green` is the AND over all of them.

> The baseline does **not** wire internal cross-member dependencies (those are a feature concern for the pipeline to add later, OQ-T1). The aggregate-green guarantee rests only on per-member isolation, which the directory-scoped composition provides.

---

## 9. CI Workflow Template (`templates/ci/github-actions.yml`, REQ-MONO-04)

Emitted **only** when the `ci` interview answer is true (`Answers.ci`, `00-core-definitions.md` §5; resolved by `04-skill-orchestration.md`). When emitted, the composed result is written to `<target>/.github/workflows/ci.yml` (tech-spec §3.11). When `ci` is false, no workflow file is written.

This template differs from the per-stack assets: it is **not** plain token substitution — the helper *generates per-member steps* from the resolved answers (tech-spec §3.11). The template is the stable scaffold (triggers, job, checkout); `02-helper-cli.md` `write_config`/CI emission injects one lint step + one test step **per member**, each running in that member's `path` with that member's resolved commands (`workspaces[]`, §8.2). The asset itself is the skeleton below; the `# <<MEMBER_STEPS>>` marker is the single injection point the helper replaces with the generated step block.

```yaml
name: ci
on:
  push:
    branches: ["**"]
  pull_request:

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      # <<MEMBER_STEPS>>
```

### 9.1 Generated member steps

For each member, the helper appends two steps (lint then test), each pinned to the member's directory via `working-directory` and using that member's `00 §6` commands. Example for a two-member monorepo (`packages/api` python, `packages/web` typescript/npm):

```yaml
      - name: api — lint
        working-directory: packages/api
        run: mypy .
      - name: api — test
        working-directory: packages/api
        run: pytest
      - name: web — lint
        working-directory: packages/web
        run: npx tsc --noEmit
      - name: web — test
        working-directory: packages/web
        run: npm test
```

Every member appears, so CI exercises **each** member's lint + test (REQ-MONO-04).

### 9.2 Single-package case

For `layout == "single"` (one implicit member at `.`), the helper emits the top-level `typeCheckCommand` + `testCommand` (the project's resolved commands, `00-core-definitions.md` §7) as two steps with no `working-directory` (tech-spec §3.11):

```yaml
      - name: lint
        run: <resolved typeCheckCommand>
      - name: test
        run: <resolved testCommand>
```

> **Toolchain setup is out of scope for the baseline.** The generated workflow runs the resolved lint/test commands directly; it does **not** emit language-toolchain setup steps (`actions/setup-node`, etc.). The baseline guarantees the *commands* are correct and green on a machine with the toolchain present (REQ-STACK-02); adding setup actions is a project-evolution concern, consistent with bootstrap never installing toolchains (tech-spec §9). An implementer MAY include a minimal `setup-*` step per stack if desired, but it is not required for REQ-MONO-04, which is about *which commands run per member*.

---

## 10. Repo-Hygiene & License Templates (REQ-SCAF-06, REQ-INPUT-05)

REQ-SCAF-06 requires four hygiene artifacts: the per-stack `.gitignore` (shipped in every stack dir, §§2–6), a **README stub** seeded with name + purpose, a **LICENSE** per the user's selection, and the **host agent-instruction file(s)**. The latter three are **repo-level** assets composed once by `write_hygiene` (`02-helper-cli.md` §4.5), not per member. Each is written through `_write_artifact`, so a pre-existing allowed-meta README/LICENSE is **kept, never overwritten** (REQ-SCAF-09).

### 10.1 `hygiene/` directory

| Path (template) | Purpose | Tokens | Emission rule |
|-----------------|---------|--------|---------------|
| `hygiene/README.md` | Project README seeded with name, purpose, and the chosen license | `{{PROJECT_NAME}}`, `{{PURPOSE}}`, `{{LICENSE}}` | always (kept if one exists) |
| `hygiene/AGENTS.md` | Portable agent-instruction file (read by Codex and other hosts; the canonical agent file) | `{{PROJECT_NAME}}`, `{{PURPOSE}}` | **always** |
| `hygiene/CLAUDE.md` | Claude-specific agent-instruction file | `{{PROJECT_NAME}}`, `{{PURPOSE}}` | **only when `Answers.host == "claude"`** (`02` §4.5) |

`README.md` is a minimal stub: an H1 of `{{PROJECT_NAME}}`, a one-line `{{PURPOSE}}`, a short "License" line naming `{{LICENSE}}` (omitted/"unlicensed" when license is `none`), and a one-line "scaffolded by forge-bootstrap" note. `AGENTS.md`/`CLAUDE.md` are short stubs pointing the agent at the project's purpose and the forge pipeline as the next step — they intentionally carry no stack-specific content (the stack is already discoverable from `forge.config.json`).

### 10.2 `licenses/` directory (REQ-INPUT-05)

Bundled, tokenized license texts — offline and stdlib-only (no network fetch). The interview (`04` §4 Q5) offers **only** licenses that exist here, plus `none`:

| Path (template) | License | Tokens |
|-----------------|---------|--------|
| `licenses/MIT/LICENSE` | MIT (full canonical text) | `{{YEAR}}`, `{{AUTHOR}}` |
| `licenses/Apache-2.0/LICENSE` | Apache License 2.0 (full canonical text) | `{{YEAR}}`, `{{AUTHOR}}` (in the appendix copyright line) |

`write_hygiene` composes `licenses/<Answers.license>/LICENSE` → `LICENSE` at the repo root, substituting `{{YEAR}}` (current UTC year) and `{{AUTHOR}}` (`Answers.author`, seeded from git `user.name` or the project name). When `Answers.license == "none"` no LICENSE is written. An `Answers.license` value with no matching `licenses/<id>/` directory is a `UsageError` (exit 2) — the body must only offer licenses present here, so adding a license to the interview means adding its `licenses/<id>/LICENSE` asset.

> **Why bundle, not fetch.** The helper is stdlib-only and offline-friendly (tech-spec §9); bundling the canonical MIT/Apache-2.0 texts as editable assets mirrors how `cargo new` / `npm init` ship license text, and keeps scaffolding deterministic with no network dependency. Adding more licenses is purely additive (drop a new `licenses/<id>/LICENSE` and list it in Q5).

---

## Dependencies

Must be implemented / read first:

- **`00-core-definitions.md`** — the `Stack` enum (§2), `PACKAGE_MANAGERS` (§2), the per-stack command table (§6), the generic-baseline definition (§6.1), the token table (§6.2), `Member` / `Answers` (§5), and the sentinel filename (§3) all consumed here.
- **`01-architecture-layout.md`** — the template-directory inventory (§1.1) and public-surface mapping (§5) this doc fills in.

Consumed by (depend on this doc):

- **`02-helper-cli.md`** — `scaffold` / `compose_member` / `write_config` and the CI emission consume these assets and the §7 substitution contract; that doc owns the *algorithm*, this doc owns the *assets*.
- **`04-skill-orchestration.md`** — the interview resolves `stack` / `packageManager` / `ci` / `layout`, which select and parameterize these templates.
- **`05` (`tests/test_forge_bootstrap.py`)** — per-stack smoke tests assert the composed output and that each baseline's resolved commands are green.

## Verification

- [ ] Each of the five `templates/<stack>/` directories exists with exactly the §N.1 file list (plus `src/lib.rs` for rust, §5.2), matching `01-architecture-layout.md` §1.1 (REQ-STACK-01).
- [ ] For each stack, composing the template with sample `Answers` and running the §N.4 resolved commands (from `00-core-definitions.md` §6) exits 0 for **both** lint and test on a machine with the toolchain present (REQ-STACK-02, REQ-SCAF-05). Generic is green with only `sh` present (REQ-STACK-03).
- [ ] Every stack's `.gitignore` lists `.forge-bootstrap.json` (REQ-SCAF-06).
- [ ] Token substitution is literal global string replacement in contents and path segments; `{{PKG}}` is sanitized to a valid Python/Go/Rust identifier (§7); composed output is byte-for-byte deterministic for fixed `Answers`.
- [ ] A mixed-language monorepo (≥2 members, different stacks) composes one isolated, individually-green template set per member; `verify`'s `green` is the AND over all members (REQ-MONO-01/02/03).
- [ ] With `ci:true` + monorepo, the composed `.github/workflows/ci.yml` contains a lint **and** test step for **every** member, each scoped to the member's `path` with its resolved commands (REQ-MONO-04). With `ci:true` + single, it runs the top-level `typeCheckCommand` + `testCommand`. With `ci:false`, no workflow is written.
