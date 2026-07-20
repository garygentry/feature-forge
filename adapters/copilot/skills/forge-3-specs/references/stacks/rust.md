# Rust Stack Profile

Stack-specific guidance for Rust projects (stable channel).

## Stack Identity

- **Language**: Rust (stable channel, edition 2021 or later)
- **Build system**: Cargo (`cargo build`, `cargo test`, `cargo run`)
- **Package registry**: crates.io (dependencies declared in `Cargo.toml`)
- **Philosophy**: Zero-cost abstractions, ownership model for memory safety, fearless concurrency

## Discovery Checklist

When examining a Rust project, check for:

- **Project manifest**: `Cargo.toml` (package metadata, dependencies, features, workspace config)
- **Dependency lock**: `Cargo.lock` (exact dependency versions for reproducible builds)
- **Library entry**: `src/lib.rs` (library crate root)
- **Binary entry**: `src/main.rs` (binary crate root), or `src/bin/` for multiple binaries
- **Build script**: `build.rs` (compile-time code generation, native library linking)
- **Cargo config**: `.cargo/config.toml` (target-specific settings, linker config, aliases)
- **Workspace**: `[workspace]` table in root `Cargo.toml` with `members` list
- **Framework**: Check `Cargo.toml` dependencies for actix-web, axum, rocket (web), clap (CLI), tokio (async)
- **Async runtime**: tokio, async-std, smol
- **Serialization**: serde, serde_json, serde_yaml

## Archetype Conventions

### 00-core-definitions.md (Rust)

- **Structs**: Use `struct` types with derive macros (`#[derive(Debug, Clone, Serialize, Deserialize)]`). Document every public field with `///` doc comments.
- **Enums**: Use for sum types / discriminated unions. Each variant documents its purpose. Exhaustive `match` for control flow.
- **Traits**: Define shared behavior contracts. Keep focused (single responsibility). Use associated types for output types, generics for input types.
- **Error types**: `thiserror::Error` for library errors (typed, specific), `anyhow::Error` for application errors (erased, convenient). Define `type Result<T> = std::result::Result<T, MyError>` aliases per module.
- **Type aliases**: Use `type` for complex generic instantiations (e.g., `type DbPool = Pool<Postgres>`)
- **Newtypes**: Single-field tuple structs for type safety (e.g., `struct UserId(Uuid)`)
- **Constants**: `const` for compile-time values, `static` for global state (rarely needed), `lazy_static!` or `std::sync::LazyLock` for runtime-initialized globals

### 01-architecture-layout.md (Rust)

- **Single crate structure**:
  - `src/lib.rs` — library root, declares modules with `mod` statements
  - `src/main.rs` — binary entry point, imports from library crate
  - `src/<module>.rs` or `src/<module>/mod.rs` — submodules
  - `tests/` — integration tests (each file is a separate crate)
  - `examples/` — runnable examples (`cargo run --example name`)
  - `benches/` — benchmarks (`cargo bench`)
- **Cargo workspace** (multi-crate):
  - Root `Cargo.toml` with `[workspace]` and `members = ["crates/*"]`
  - Shared dependencies via `[workspace.dependencies]` with `{ workspace = true }` in member crates
  - Internal crate references as path dependencies
- **Cargo.toml**: `[package]` (name, version, edition), `[dependencies]`, `[dev-dependencies]`, `[build-dependencies]`, `[features]` for conditional compilation
- **Module visibility**: `pub`, `pub(crate)`, `pub(super)` for fine-grained access control. Re-exports via `pub use` in parent modules.

### NN-testing-strategy.md (Rust)

- **Framework**: Built-in `#[test]` attribute (no external framework required)
- **Unit tests**: `#[cfg(test)] mod tests { ... }` at bottom of each source file (white-box, access to private items)
- **Integration tests**: `tests/` directory, each `.rs` file is a separate test crate (black-box, only public API)
- **Test assertions**: `assert!`, `assert_eq!`, `assert_ne!` macros; custom messages as format string arguments
- **Doc tests**: Code blocks in `///` doc comments run as tests with `cargo test`
- **Examples**: `examples/` directory, verified to compile with `cargo test`, runnable with `cargo run --example`
- **Test fixtures**: Builder pattern structs, helper functions in `tests/common/mod.rs`
- **Async tests**: `#[tokio::test]` attribute for async test functions
- **Property testing**: `proptest` or `quickcheck` crates for generative testing
- **Snapshot testing**: `insta` crate for snapshot/approval testing

## Spec Quality Rules

- All Rust code must be valid syntax with complete type annotations — not pseudocode
- Follow Rust idioms:
  - `Result<T, E>` for fallible operations — never panic for expected failures
  - `Option<T>` for nullable/optional values — never use sentinel values
  - Ownership and borrowing: specify whether a function takes ownership (`T`), borrows (`&T`), or mutably borrows (`&mut T`). Note when `Clone` is required.
  - Lifetime annotations when the compiler cannot infer them — document why a lifetime relationship exists
  - Derive macros for common traits (`Debug`, `Clone`, `PartialEq`, `Eq`, `Hash`, `Serialize`, `Deserialize`)
  - `impl` blocks for methods — group inherent methods and trait implementations separately
  - Pattern matching with `match` for control flow over enums and `Result`/`Option`
  - `?` operator for error propagation — avoid manual `match` on `Result` when `?` suffices
- Document every public item with `///` doc comments including `# Examples` sections for non-trivial APIs
- Use `#[must_use]` on functions whose return values should not be ignored
- Include complete `use` statements in all code examples

## Verification Specifics

- **Type checking**: `cargo check` (fast compile without codegen — catches all type errors)
- **Linting**: `cargo clippy` (idiomatic Rust lints, catches common mistakes)
- **Testing**: `cargo test` (unit tests, integration tests, doc tests, examples)
- **Documentation**: `cargo doc --no-deps` (ensures documentation compiles, catches broken links)
- **Formatting**: `cargo fmt --check` (ensures code matches `rustfmt` style)
- **Unsafe audit**: `cargo geiger` (if security-sensitive — counts unsafe blocks)

### Runtime Entrypoints & Bootstrap-Wiring Sites

Used by `CHECK-I22` (a runtime-required bootstrap needs a **non-test** caller on one of these) and
`CHECK-I23` (a heavy init wired into a **universal** bootstrap entry should move to a lazier site).

- **Runtime entrypoints (a legitimate non-test call site):** `fn main()` in `main.rs` or a `[[bin]]`
  target, an async runtime entry (`#[tokio::main]`), an HTTP handler registered on an axum/actix/warp
  router, or a worker task spawned from `main` — not a `#[cfg(test)]` module or a `tests/` integration
  file.
- **Universal bootstrap entries (run on every startup — the `CHECK-I23` risk site):** a `lazy_static!`
  / `once_cell::sync::Lazy` static that eagerly constructs heavy clients, a single `bootstrap`/`setup`
  fn `main` calls before serving, or a `#[ctor]`-style pre-`main` initializer. A `Lazy` static is only
  a risk when it is *forced* at startup rather than on first use.
- **Heavy server-only import markers (what makes an init "heavy" for `CHECK-I23`):** DB pools
  (`sqlx::Pool`, `diesel`, `deadpool`, `mongodb`), message/queue clients (`rdkafka`, `lapin`,
  `redis`), telemetry SDKs (`opentelemetry`, `sentry`), or a broad internal service crate. Constructing
  any of these eagerly at a universal entry is the CHECK-I23 pattern — recommend a `OnceCell`/`Lazy`
  forced on **first use** by the handler that needs it, not at process start.

## Testing

- **Framework**: Built-in test harness (`#[test]`, `#[cfg(test)]`)
- **Test command**: `cargo test` for all, `cargo test test_name` for specific, `cargo test --lib` for unit only
- **Unit tests**: `#[cfg(test)] mod tests` at bottom of source files
- **Integration tests**: `tests/` directory, each file is a separate crate
- **Doc tests**: Code in `///` comments, verified by `cargo test --doc`
- **Assertions**: `assert!`, `assert_eq!`, `assert_ne!` with optional format messages
- **Async tests**: `#[tokio::test]` macro for async test functions
- **Snapshot testing**: `insta` crate with `assert_snapshot!` / `assert_debug_snapshot!`
- **Coverage**: `cargo llvm-cov` or `cargo tarpaulin`
- **Benchmarks**: `criterion` crate or built-in `#[bench]` (nightly)

## Common Frameworks

| Category | Options |
|----------|---------|
| Web (async) | axum, actix-web, rocket, warp |
| Serialization | serde, serde_json, serde_yaml, toml |
| Async runtime | tokio, async-std, smol |
| Database | sqlx, diesel, sea-orm |
| Migrations | sqlx-cli, diesel-cli, refinery |
| CLI | clap, argh, structopt (legacy) |
| Observability | tracing, tracing-subscriber, metrics |
| HTTP client | reqwest, hyper, ureq (blocking) |
| Middleware | tower, tower-http, actix middleware |
| Error handling | thiserror (library), anyhow (application), eyre |

## Example: Project-Level Override

Create `.feature-forge/stack-decisions.md` (legacy alias: `.claude/references/stack-decisions.md`) in your project root:

```markdown
# Stack Decisions

## Runtime & Build
- Rust stable (edition 2021)
- Cargo workspace with crates/ directory

## Backend
- axum for HTTP framework
- sqlx with PostgreSQL (compile-time query checking)
- tokio as async runtime

## Serialization & Validation
- serde for serialization/deserialization
- Custom validation via trait implementations

## Testing
- Built-in #[test] with assert macros
- Integration tests in tests/ directory
- insta for snapshot testing

## Conventions
- thiserror for library error types, anyhow in binary
- tracing for structured logging
- cargo clippy must pass with no warnings
- All public APIs documented with /// and examples
```
