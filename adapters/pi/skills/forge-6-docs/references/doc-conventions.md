# Documentation Conventions

Standards and patterns for feature architecture documentation.

## General Rules

- Write in present tense ("The auth module validates..." not "The auth module will validate...")
- Use second person for guides ("You can configure..." not "One can configure...")
- Include code examples for every exported function, class, or component
- Code examples must be runnable — no pseudocode, no incomplete snippets
- Use the project's primary language for all code examples

## Heading Structure

- H1: Feature name (only in README.md)
- H2: Major sections
- H3: Subsections
- Don't go deeper than H4

## Code Examples

The following examples use TypeScript. Adapt language and import syntax to your project's stack. The principle — always include imports, show complete runnable examples — applies to all languages.

Always include import statements:
```typescript
// Good
import { createAuthMiddleware } from '@repo/auth/server';

const middleware = createAuthMiddleware({ secret: process.env.JWT_SECRET });

// Bad — missing import, unclear where this comes from
const middleware = createAuthMiddleware({ secret: process.env.JWT_SECRET });
```

### Complete Quick Start Example

Here's a complete "Quick Start" section showing the expected quality:

```markdown
## Quick Start

Install the auth package:

```bash
bun add @repo/auth
```

Add the auth middleware to your Hono server:

```typescript
import { createAuthMiddleware } from '@repo/auth/server';
import { getConfig } from '@repo/config';

const config = getConfig();

app.use('*', createAuthMiddleware({
  secret: config.auth.jwtSecret,
  cookieName: 'session',
}));
```

Access the session in any route handler:

```typescript
app.get('/api/me', (c) => {
  const session = c.get('session');
  if (!session) return c.json({ error: 'Not authenticated' }, 401);
  return c.json({ userId: session.userId, roles: session.roles });
});
```

For full configuration options, see [API Reference](./api-reference.md).
For setting up OAuth providers, see [Integration Guide](./guides/integration.md).
```

## API Reference Format

For each exported item:

```markdown
### `functionName(params): ReturnType`

Brief description of what this does.

**Parameters:**
- `param1` (`Type`) — Description
- `param2` (`Type`, optional) — Description. Defaults to `defaultValue`.

**Returns:** `ReturnType` — Description

**Throws:** `ErrorType` — When condition

**Example:**
\`\`\`typescript
import { functionName } from '@repo/feature';

const result = functionName({ param1: 'value' });
\`\`\`
```

## Diagrams

If the feature has complex data flow or component relationships, include a Mermaid diagram:

```markdown
\`\`\`mermaid
graph LR
  A[Request] --> B[Auth Middleware]
  B --> C{Valid Session?}
  C -->|Yes| D[Route Handler]
  C -->|No| E[401 Response]
\`\`\`
```

## Cross-References

When referencing other packages or features:
- Link to their docs if they exist: `[Configuration package](../config/README.md)`
- Use the package name in backticks: `@repo/config`
- Don't duplicate their documentation — link to it

## File Naming

- All lowercase with hyphens: `api-reference.md`, `getting-started.md`
- Guides go in a `guides/` subdirectory
- ADRs go in a `decisions/` subdirectory with format `adr-NNN-short-title.md`
