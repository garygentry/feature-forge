# TypeScript Stack Profile

Stack-specific guidance for TypeScript projects (Node.js/Bun, monorepo or single-package).

## Stack Identity

- **Language**: TypeScript
- **Runtime**: Node.js or Bun (check `package.json` `engines` field and lock files)
- **Package management**: npm, pnpm, yarn, or bun (check for respective lock files)
- **Common monorepo tools**: Turborepo (`turbo.json`), Nx (`nx.json`), Lerna (`lerna.json`)

## Discovery Checklist

When examining a TypeScript project, check for:

- **Runtime**: Bun or Node.js (check `package.json` for which)
- **Package management**: Check for `bun.lockb`, `pnpm-lock.yaml`, `package-lock.json`, or `yarn.lock`
- **Monorepo**: Check for `turbo.json` (Turborepo), `nx.json` (Nx), or `lerna.json` (Lerna)
- **Framework**: Check existing packages for Hono, Express, Fastify, etc.
- **Frontend**: Check for React, Vue, Svelte, etc.
- **Routing**: Check for TanStack Router, React Router, Next.js, etc.
- **Database**: Check for Drizzle, Prisma, TypeORM, etc.
- **Validation**: Check for Zod, Yup, io-ts, etc.
- **UI Components**: Check for shadcn/ui, Radix, MUI, etc.
- **Styling**: Check for Tailwind (v3 or v4), CSS Modules, styled-components, etc.

## Archetype Conventions

### 00-core-definitions.md (TypeScript)

- **Type aliases and union types**: Use `type` declarations for unions, intersections, utility types
- **Core interfaces**: Define with `interface` keyword, JSDoc on every field
- **Error class hierarchy**: Base error class extending `Error` with `code: string` property; domain-specific subclasses with typed properties
- **Constants and enums**: Use `const` declarations and `as const` assertions; prefer string union types over `enum`
- **Utility types**: Generic helpers like `Result<T, E>`, `Optional<T>`, etc.
- **Barrel exports**: Export everything from `src/index.ts`

### 01-architecture-layout.md (TypeScript)

- **Package.json**: `name`, `exports` map (subpath exports like `.`, `./server`, `./client`, `./react`), `dependencies`, `devDependencies`, `scripts`
- **tsconfig.json**: Key compiler options, extends root config
- **Barrel export structure**: What each `index.ts` re-exports
- **Build considerations**: Bundle vs unbundled, ESM vs CJS

### Monorepo conventions

- **Package naming**: `@repo/{name}` for shared packages, `@starter/{name}` for app-specific (adapt to project convention)
- **Internal dependencies**: Reference as `@repo/{package}` in `package.json`
- **Workspace protocol**: `"@repo/config": "workspace:*"` in pnpm, `"@repo/config": "*"` in bun

## Spec Quality Rules

- All TypeScript must be valid syntax — not pseudocode
- Include complete interfaces with generics where applicable
- Use discriminated unions for result types (e.g., `{ success: true; data: T } | { success: false; error: E }`)
- Every interface field must have JSDoc explaining its purpose
- Include explicit import paths in all code examples
- Use `async/await` for asynchronous operations (not raw Promises)

## Verification Specifics

- **Type checking**: `bun run typecheck`, `tsc --noEmit`, or `npx tsc --noEmit`
- **Barrel export validation**: Every `index.ts` re-exports what the spec says
- **Cross-package type checks**: `bun run typecheck` (or equivalent) passes for both the feature package AND packages that depend on it
- **Import path validation**: All import paths resolve correctly per the `exports` map in `package.json`

## Testing

- **Framework**: Vitest (most common in modern TS), Jest, or testing-library
- **Test file location**: Co-located (`*.test.ts` next to source) or in `__tests__/` directories
- **Fixture patterns**: Factory functions, test builders
- **Type testing**: `expectTypeOf` from vitest for type-level assertions

## Common Frameworks

| Category | Options |
|----------|---------|
| Backend | Hono, Express, Fastify, Koa |
| Frontend | React, Vue, Svelte, Solid |
| Routing | TanStack Router, React Router, Next.js App Router |
| Database | Drizzle, Prisma, TypeORM, Kysely |
| Validation | Zod, Valibot, Yup, io-ts |
| UI Components | shadcn/ui, Radix, MUI, Mantine |
| Styling | Tailwind CSS, CSS Modules, styled-components, vanilla-extract |

## Example: Project-Level Override

Create `.claude/references/stack-decisions.md` in your project root:

```markdown
# Stack Decisions

## Runtime & Build
- Bun 1.x for runtime and package management
- Turborepo for monorepo orchestration

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
