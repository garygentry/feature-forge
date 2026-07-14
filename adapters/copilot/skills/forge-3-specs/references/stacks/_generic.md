# Generic Stack Profile

Language-neutral guidance for projects without a dedicated stack profile. Use this as a fallback when no matching `references/stacks/{stack}.md` exists.

## Discovery Protocol

Identify the project's stack by checking for these manifest and build files:

| File | Stack |
|------|-------|
| `package.json` | Node.js / Bun (JavaScript/TypeScript) |
| `pyproject.toml`, `setup.py`, `setup.cfg` | Python |
| `go.mod` | Go |
| `Cargo.toml` | Rust |
| `pom.xml`, `build.gradle`, `build.gradle.kts` | Java / Kotlin |
| `*.csproj`, `*.sln` | .NET (C#/F#) |
| `mix.exs` | Elixir |
| `Gemfile` | Ruby |
| `Package.swift` | Swift |

Also check for:
- **Lock files**: Reveal the package manager (`bun.lockb`, `uv.lock`, `poetry.lock`, `go.sum`, `Cargo.lock`, etc.)
- **Workspace/monorepo configs**: `turbo.json`, `nx.json`, `lerna.json`, `pants.toml`, `Cargo workspace`, Go workspace `go.work`
- **CI configuration**: `.github/workflows/`, `Makefile`, `justfile` — often reveals build and test commands

## Archetype Adaptations

### 00-core-definitions.md

The shared type/data contract document. Language-neutral name for what TypeScript calls "core types and interfaces." Contents should include:

- **Data structures**: The primary types, classes, structs, records, or models that define the feature's domain. Use the project's idiomatic type system (dataclasses, structs, interfaces, schemas, etc.)
- **Error/exception hierarchy**: Base error type and domain-specific subtypes with structured properties. Every language has a mechanism for this (exception classes, error types, Result enums, etc.)
- **Constants and enumerations**: Shared values referenced across the feature
- **Public contracts**: Function signatures, protocols, interfaces, or traits that define the feature's API surface

**Documentation rule**: Every type/structure must have documentation comments in the project's convention (JSDoc, docstrings, godoc, rustdoc, etc.)

**Export rule**: Everything must be accessible through the module's entry point following project conventions.

### 01-architecture-layout.md

How the feature is structured in the project:

- **Directory tree**: Full layout (not abbreviated)
- **Project manifest**: Dependencies, entry points, build scripts
- **Build/compiler configuration**: Key options
- **Module export structure**: What each entry point exposes
- **Build and deployment considerations**

### NN-testing-strategy.md

- **Testing framework and tooling**: Match project conventions
- **Unit test approach**: What to test, what to mock/stub
- **Integration test approach**: Cross-module interaction testing
- **Test fixtures and factories**
- **Coverage targets**
- **Test file location conventions**

## Spec Conventions

When writing implementation specs:
- Include complete type definitions and function signatures in the project's language — not pseudocode
- Include documentation comments on every public type and function
- Include error handling for every operation
- Include example usage where it aids clarity
- Cross-reference other spec documents by filename

## Verification Adaptations

Replace stack-specific checks with these generic equivalents:

| Stack-specific check | Generic equivalent |
|---------------------|-------------------|
| "Valid TypeScript syntax" | "Valid syntax in the project's language" |
| "Barrel exports (index.ts)" | "Module exports/entry points follow project conventions" |
| "bun run typecheck passes" | "`{typeCheckCommand}` passes" (from forge.config.json) |
| "bun test passes" | "`{testCommand}` passes" (from forge.config.json) |
| "JSDoc on every field" | "Documentation comments on every field" |
| "tsconfig.json extends root" | "Build configuration follows project conventions" |

## Acceptance Criteria Patterns

Use these placeholder patterns in backlog items. Replace `{typeCheckCommand}`, `{testCommand}`, and `{module}` with values from `forge.config.json` and the project structure:

- `{typeCheckCommand} passes for {module}`
- `{testCommand} passes for {module}`
- `{module}/[entry point] exports [expected symbols]`
- `[dependency manifest] includes [new dependency]`
- `[build command] succeeds`
