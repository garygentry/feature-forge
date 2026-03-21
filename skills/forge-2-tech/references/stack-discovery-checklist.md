# Stack Discovery Checklist (Plugin Default)

This file contains a default stack discovery protocol for the feature-forge plugin. Projects can override this by placing a `stack-decisions.md` in `.claude/references/` at the project root.

## Note to Agent

This is a DISCOVERY PROTOCOL — it helps you identify what stack the project uses. It is NOT a set of decisions. Always check `.claude/references/stack-decisions.md` first — if present, it takes precedence.

After discovering the stack, check if `references/stacks/{stack}.md` exists in the plugin for stack-specific guidance. See `references/stack-resolution.md` for the full resolution protocol.

## Purpose

This is a default discovery guide for understanding a project's technology stack. Projects should create `.claude/references/stack-decisions.md` with their actual stack decisions, which takes precedence over this checklist.

## Stack Discovery Protocol

### 1. Identify the Primary Language and Runtime

Check for project manifests:
- `package.json` → Node.js / Bun (JavaScript/TypeScript)
- `pyproject.toml`, `setup.py`, `setup.cfg` → Python
- `go.mod` → Go
- `Cargo.toml` → Rust
- `pom.xml`, `build.gradle`, `build.gradle.kts` → Java / Kotlin
- `*.csproj`, `*.sln` → .NET (C#/F#)
- `mix.exs` → Elixir
- `Gemfile` → Ruby
- `Package.swift` → Swift

### 2. Identify the Package Manager

Check for lock files:
- `bun.lockb` → Bun
- `pnpm-lock.yaml` → pnpm
- `package-lock.json` → npm
- `yarn.lock` → Yarn
- `uv.lock` → uv
- `poetry.lock` → Poetry
- `go.sum` → Go modules
- `Cargo.lock` → Cargo

### 3. Identify Project Structure

Check for monorepo/workspace configurations:
- `turbo.json` → Turborepo
- `nx.json` → Nx
- `lerna.json` → Lerna
- `pnpm-workspace.yaml` → pnpm workspaces
- `pants.toml` → Pants (Python/Go/Java)
- `go.work` → Go workspaces
- `Cargo.toml` with `[workspace]` → Cargo workspaces

If none found, this is likely a single-project repository.

### 4. Identify Frameworks and Libraries

Examine the dependency manifest for:
- **Web frameworks**: Hono, Express, Fastify, FastAPI, Django, Flask, Gin, Actix, Spring Boot, etc.
- **Frontend**: React, Vue, Svelte, Solid, etc.
- **Database/ORM**: Drizzle, Prisma, SQLAlchemy, GORM, Diesel, etc.
- **Validation**: Zod, Pydantic, etc.
- **Testing**: Vitest, pytest, go test, etc.

### 5. Identify Build and Type Checking

- Check for CI config (`.github/workflows/`, `Makefile`, `justfile`) to find build, test, and type check commands
- Check `package.json` scripts, `pyproject.toml` `[tool.*]` sections, or `Makefile` targets

## How to Create a Project-Level Override

Create `.claude/references/stack-decisions.md` in your project root with your specific stack decisions. See `references/stacks/typescript.md` or `references/stacks/python.md` for stack-specific examples of what to include.

```markdown
# Stack Decisions

## Runtime & Build
- [Language and version]
- [Package manager]
- [Build tool / monorepo orchestration if applicable]

## Backend
- [Web framework]
- [Database / ORM]
- [Validation library]

## Frontend (if applicable)
- [UI framework]
- [Component library]
- [Styling approach]

## Conventions
- [Testing framework and approach]
- [Type checking / linting command]
- [Module organization patterns]
```
