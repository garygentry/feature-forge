# Spec Examples — Quality Bar

These examples demonstrate the expected depth and quality for implementation spec sections. Match this level of detail.

> **Note:** The following examples use TypeScript. Adapt the language, idioms, and documentation style to match your project's stack. The STRUCTURE and DEPTH shown here is the quality bar regardless of language. See `references/stacks/{stack}.md` for language-specific conventions.

## Example: Function Specification (from a session management spec)

### 3.2 Token Refresh (REQ-AUTH-05, REQ-SEC-03)

Refresh an expiring session token without requiring re-authentication.

```typescript
/**
 * Refresh a session token if it's within the refresh threshold.
 * Returns a new token with an extended expiry, or null if the session
 * is not eligible for refresh (expired, revoked, or outside threshold).
 *
 * @param currentToken - The JWT string from the session cookie
 * @param options - Refresh configuration
 * @returns New session token string, or null if refresh is not possible
 * @throws {SessionExpiredError} If the token has already expired
 * @throws {TokenValidationError} If the token signature is invalid
 */
export async function refreshSessionToken(
  currentToken: string,
  options: RefreshOptions
): Promise<string | null>;

interface RefreshOptions {
  /** Maximum age of a token eligible for refresh. Default: SESSION_DURATION_MS */
  maxAge?: number;
  /** How close to expiry before refresh is allowed. Default: REFRESH_THRESHOLD_MS */
  refreshThreshold?: number;
  /** Secret key for signing the new token */
  signingKey: CryptoKey;
}
```

**Error Handling:**
- `SessionExpiredError` (code: `SESSION_EXPIRED`): Token's `exp` claim is in the past. Client must re-authenticate.
- `TokenValidationError` (code: `TOKEN_INVALID`): Signature verification failed. Token may have been tampered with. Log a security warning.
- Returns `null` (no error): Token is valid but not yet within the refresh threshold. No action needed.

**Dependencies:**
- Types from `00-core-definitions.md`: `SessionToken`, `SessionExpiredError`, `TokenValidationError`, `RefreshOptions`
- Constants from `00-core-definitions.md`: `SESSION_DURATION_MS`, `REFRESH_THRESHOLD_MS`
- `jose` library for JWT verification and signing

**Verification:**
- [ ] `refreshSessionToken` returns a new token when called with a token within the refresh threshold
- [ ] Returns `null` for a valid token outside the refresh threshold
- [ ] Throws `SessionExpiredError` for an expired token
- [ ] Throws `TokenValidationError` for a token with an invalid signature
- [ ] New token has an expiry of `SESSION_DURATION_MS` from the current time

## Example: Requirement Coverage Header

Every spec document should begin with a requirement coverage section:

```markdown
## Requirement Coverage

| REQ ID | Requirement | Section |
|--------|-------------|---------|
| REQ-AUTH-05 | Token refresh without re-auth | 3.2 |
| REQ-SEC-03 | Session expiry management | 3.1, 3.2 |
| REQ-PERF-02 | Token validation under 10ms | 3.3 |
```

This makes traceability explicit and auditable.
