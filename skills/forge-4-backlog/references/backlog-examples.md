# Backlog Examples — Gold Standard

These examples demonstrate the quality, detail, and format expected for backlog items. Use them as a reference when generating items.

## Example 1: Foundation / Scaffold Item

```json
{
  "id": "001",
  "type": "chore",
  "priority": 1,
  "title": "Scaffold packages/auth with package.json, tsconfig, and directory skeleton",
  "description": "Create the `packages/auth/` directory with the full package skeleton.\n\n1. Create `packages/auth/package.json` with:\n   - name: `@repo/auth`\n   - Subpath exports: `.`, `./server`, `./client`, `./react`\n   - Dependencies: `hono`, `jose`, `arctic`, `@simplewebauthn/server`, `argon2`\n   - Internal deps: `@repo/config`, `@repo/db`\n   - Dev deps: `vitest`\n\n2. Create `packages/auth/tsconfig.json` extending `../../tsconfig.json` with `jsx: \"react-jsx\"`\n\n3. Create all source directories with empty barrel index.ts files:\n   - `src/index.ts` (re-exports ./shared)\n   - `src/shared/index.ts`\n   - `src/server/index.ts`\n   - `src/client/index.ts`\n   - `src/react/index.ts`\n\n4. Run `bun install` from monorepo root to install dependencies.",
  "acceptanceCriteria": [
    "packages/auth/package.json exists with correct name, exports, and dependencies",
    "packages/auth/tsconfig.json extends root tsconfig",
    "All four barrel index.ts files exist and export empty objects or type-only re-exports",
    "bun install succeeds from monorepo root",
    "bun run typecheck passes for @repo/auth"
  ],
  "status": "pending",
  "completedAt": null,
  "dependsOn": [],
  "notes": "This is the foundation item. Read spec 01-architecture-layout.md completely before implementing. Use the exact exports map from the spec.",
  "estimatedIterations": 1,
  "specReferences": [
    "specs/auth/01-architecture-layout.md"
  ]
}
```

**Why this is good:**
- Self-contained: a fresh agent can implement this without reading other backlog items
- Numbered steps with exact file paths and content
- Acceptance criteria are verifiable commands (`bun run typecheck passes`)
- Single concern: just the scaffold, not the types or logic
- Clear spec reference

## Example 2: Type System Item

```json
{
  "id": "002",
  "type": "feature",
  "priority": 1,
  "title": "Implement shared types, error hierarchy, and constants",
  "description": "Create the complete shared type system for @repo/auth.\n\n1. Create `src/shared/types.ts` with all types from spec 00 section 2:\n   - `SessionToken` interface with `userId`, `sessionId`, `expiresAt`, `roles` fields\n   - `AuthResult` discriminated union: `{ success: true; session: SessionToken }` | `{ success: false; error: AuthError }`\n   - `OAuthProvider` union type: 'google' | 'github' | 'discord'\n   - `Permission` type alias for string\n   - `Role` interface with `name`, `permissions` array\n\n2. Create `src/shared/errors.ts` with error class hierarchy from spec 00 section 3:\n   - `AuthError` base class extending `Error` with `code: string` property\n   - `InvalidCredentialsError` extending `AuthError` (code: 'INVALID_CREDENTIALS')\n   - `SessionExpiredError` extending `AuthError` with `expiredAt: Date` (code: 'SESSION_EXPIRED')\n   - `InsufficientPermissionsError` extending `AuthError` with `required: Permission[]`, `actual: Permission[]`\n   - All classes must have JSDoc on every property\n\n3. Create `src/shared/constants.ts` with:\n   - `SESSION_DURATION_MS = 7 * 24 * 60 * 60 * 1000` (7 days)\n   - `REFRESH_THRESHOLD_MS = 24 * 60 * 60 * 1000` (1 day)\n   - `ALL_OAUTH_PROVIDERS: OAuthProvider[]`\n\n4. Update `src/shared/index.ts` to re-export all types, errors, and constants.",
  "acceptanceCriteria": [
    "src/shared/types.ts exports SessionToken, AuthResult, OAuthProvider, Permission, Role",
    "src/shared/errors.ts exports AuthError, InvalidCredentialsError, SessionExpiredError, InsufficientPermissionsError",
    "All error classes have correct inheritance and typed properties",
    "src/shared/constants.ts exports SESSION_DURATION_MS, REFRESH_THRESHOLD_MS, ALL_OAUTH_PROVIDERS",
    "src/shared/index.ts re-exports everything",
    "bun run typecheck passes for @repo/auth"
  ],
  "status": "pending",
  "completedAt": null,
  "dependsOn": ["001"],
  "notes": "Use EXACT TypeScript from spec 00 — every interface and class is fully specified with JSDoc. Do not simplify or abbreviate.",
  "estimatedIterations": 1,
  "specReferences": [
    "specs/auth/00-core-types-shared.md"
  ]
}
```

**Why this is good:**
- Every type and field is explicitly named — no ambiguity
- Error hierarchy is spelled out with exact class names and properties
- Depends on 001 (scaffold must exist first)
- Notes reinforce "use exact TypeScript from spec"

## Example 3: Integration Item

```json
{
  "id": "008",
  "type": "feature",
  "priority": 3,
  "title": "Wire auth middleware into @starter/app-shell Hono server",
  "description": "Integrate the @repo/auth session middleware with the existing @starter/app-shell Hono application.\n\n1. In `packages/auth/src/server/middleware.ts` (created in item 005), export `createAuthMiddleware(config: AuthConfig): MiddlewareHandler` that:\n   - Reads the session cookie from the request\n   - Validates the JWT using `jose`\n   - Attaches `session: SessionToken | null` to the Hono context via `c.set('session', session)`\n   - Does NOT reject unauthenticated requests (that's the route's job)\n\n2. In `apps/app-shell/src/server.ts`, add the auth middleware:\n   - Import `createAuthMiddleware` from `@repo/auth/server`\n   - Import `AuthConfig` from `@repo/auth`\n   - Add `app.use('*', createAuthMiddleware({ ... }))` before route handlers\n   - Read JWT secret from `@repo/config`\n\n3. Add `@repo/auth` as a dependency in `apps/app-shell/package.json`\n\n4. Run `bun install` from monorepo root.",
  "acceptanceCriteria": [
    "apps/app-shell/package.json includes @repo/auth as a dependency",
    "apps/app-shell/src/server.ts imports and uses createAuthMiddleware",
    "Auth middleware is registered before route handlers",
    "Session is accessible via c.get('session') in route handlers",
    "bun run typecheck passes for both @repo/auth and @starter/app-shell",
    "Existing app-shell tests still pass"
  ],
  "status": "pending",
  "completedAt": null,
  "dependsOn": ["005", "006"],
  "notes": "Read the existing app-shell server.ts to understand the current middleware chain. The auth middleware should slot in AFTER the config middleware but BEFORE route handlers. Check that the Hono context type is extended correctly.",
  "estimatedIterations": 1,
  "specReferences": [
    "specs/auth/04-integration-points.md",
    "specs/auth/03-session-management.md"
  ]
}
```

**Why this is good:**
- Integration items specify BOTH sides of the integration (auth package AND app-shell)
- Exact import paths and function signatures
- Notes call out ordering concerns (middleware chain order)
- Multiple spec references for cross-cutting concerns
- Acceptance criteria verify both packages typecheck
