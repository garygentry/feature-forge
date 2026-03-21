# Stack Discovery Checklist (Plugin Default)

This file contains default stack context for the feature-forge plugin. Projects can override this by placing a `stack-decisions.md` in `.claude/references/` at the project root.

## Note to Agent

This is a TEMPLATE with common modern TypeScript stack decisions. It represents reasonable defaults but MUST be overridden by project-level configuration if present. Always check `.claude/references/stack-decisions.md` first.

If no project-level override exists, use this as general guidance but ALWAYS verify against the actual project's package.json and codebase to confirm which technologies are actually in use.

## Purpose

This is a default discovery guide for understanding a project's technology stack. It is NOT a set of decisions — it helps you discover what's already in place. Projects should create `.claude/references/stack-decisions.md` with their actual stack decisions, which takes precedence over this checklist.

## Common Modern TypeScript Stack

- **Runtime**: Bun or Node.js (check package.json for which)
- **Package Management**: Check for bun.lockb, pnpm-lock.yaml, package-lock.json, or yarn.lock
- **Monorepo**: Check for turbo.json (Turborepo), nx.json (Nx), or lerna.json (Lerna)
- **Framework**: Check existing packages for Hono, Express, Fastify, etc.
- **Frontend**: Check for React, Vue, Svelte, etc.
- **Routing**: Check for TanStack Router, React Router, Next.js, etc.
- **Database**: Check for Drizzle, Prisma, TypeORM, etc.
- **Validation**: Check for Zod, Yup, io-ts, etc.
- **UI Components**: Check for shadcn/ui, Radix, MUI, etc.
- **Styling**: Check for Tailwind (v3 or v4), CSS Modules, styled-components, etc.

## How to Create a Project-Level Override

Create `.claude/references/stack-decisions.md` in your project root with your specific stack:

```markdown
# Stack Decisions

## Runtime & Build
- Bun 1.x for runtime and package management
- Turborepo for monorepo orchestration
- pnpm for package management

## Backend
- Hono for HTTP framework
- Drizzle ORM with PostgreSQL
- Zod for runtime validation

## Frontend
- React 19 with TanStack Router (SPA-first)
- shadcn/ui component library
- Tailwind CSS v4 with oklch color theming

## Conventions
- Barrel exports from index.ts in every package
- Package naming: @repo/{name} for shared, @starter/{name} for app-specific
- Vitest for testing
```
