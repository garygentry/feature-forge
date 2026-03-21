---
name: forge-verify
description: "Verify feature artifacts for completeness, consistency, and quality."
argument-hint: "<feature-name> [stage: prd|tech|specs|backlog|impl]"
disable-model-invocation: true
---

# forge-verify — Verification Gate

Analyze feature artifacts for completeness, consistency, and quality. Produce structured, actionable findings designed for a fresh-context agent to apply.

## Subagent Delegation

This skill should be delegated to the `forge-verifier` subagent via the Agent tool. The verifier subagent has:
- **Read-only tools** (Read, Glob, Grep, Bash) — it cannot accidentally modify specs
- **Persistent memory** — it accumulates knowledge about this project's recurring issues and patterns across sessions
- **The forge-verify skill pre-loaded** — so it has all verification checklists and guidance at startup

To delegate: use the Agent tool with `subagent_type="forge-verifier"` and pass the feature name and optional mode in the prompt.

If the `forge-verifier` subagent is not available (not installed, or running in an environment that doesn't support subagents), fall back to running verification inline in the current session.

**Inline execution guidance:** If running inline (not as subagent), process verification checklists one category at a time to manage context pressure. Load only the artifacts needed for each category, verify, summarize findings, then move to the next category.

## Prerequisites

Read and follow `references/shared-conventions.md` for feature name validation, configuration reading, and force mode handling before proceeding.

## Step 1: Read Configuration and Determine Mode

Read `{specsDir}/{feature}/.pipeline-state.json` to understand current pipeline state.

### Mode Selection

If a stage is specified as a second argument (e.g., `/forge-verify auth specs`), use that mode. Otherwise, auto-detect based on pipeline state:

- **prd mode**: If `forge-1-prd` is complete but `forge-verify-prd` is not `passed` or `findings-applied`
- **tech mode**: If `forge-2-tech` is complete but `forge-verify-tech` is not `passed` or `findings-applied`
- **specs mode**: If `forge-3-specs` is complete but `forge-verify-specs` is not `passed` or `findings-applied`
- **backlog mode**: If `forge-4-backlog` is complete but `forge-verify-backlog` is not `passed` or `findings-applied`
- **impl mode**: If user explicitly requests or if implementation code exists for this feature

If ambiguous, ask the user which stage to verify.

## Step 2: Load All Relevant Artifacts

Load into context ALL artifacts for this feature based on mode:

**For prd mode:**
- `{specsDir}/{feature}/PRD.md`

**For tech mode:**
- `{specsDir}/{feature}/PRD.md`
- `{specsDir}/{feature}/tech-spec.md`

**For specs mode:**
- `{specsDir}/{feature}/PRD.md`
- `{specsDir}/{feature}/tech-spec.md`
- `{specsDir}/{feature}/##-*.md` (all implementation specs)

**For backlog mode:**
- All of the above, PLUS
- `{specsDir}/{feature}/backlog.json (or {backlogDir}/backlog.json if configured)`

**For impl mode:**
- All of the above, PLUS
- The actual source code for this feature (read package directory)
- Source code of packages this feature integrates with

## Step 3: Run Verification Checklists

Read `references/verification-checklists.md` for the detailed checklists per mode. Execute every check. Do not skip checks because things "look fine."

Each check in `verification-checklists.md` has a unique ID (CHECK-P01, CHECK-T01, CHECK-S01, CHECK-B01, etc.). As you execute each check, record its ID and result (pass/fail/not-applicable). After completing all checks, report the total: "Executed N of M checks. Results: X pass, Y fail, Z not-applicable." If your count is significantly below the expected total for the mode (prd: ~15 checks, tech: ~15 checks, specs: ~38 checks, backlog: ~25 checks, impl: ~20 checks), you likely skipped checks — go back and complete them.

### Important: Be Specific, Not General

BAD finding: "The error handling could be more thorough."
GOOD finding: "PRD.md REQ-ERR-04 requires rate limit retry behavior, but spec 03-provider-registry.md only handles rate limits by throwing — no retry logic is specified."

Every finding must include:
1. A unique ID (V-001, V-002, etc.)
2. Severity: `gap` (missing requirement coverage), `inconsistency` (contradictory specs), `improvement` (not wrong but could be better), `error` (factually incorrect)
3. Exact location (file + section)
4. What's wrong
5. Suggested fix (specific enough that a fresh agent can apply it)
6. References (which other files/sections are involved)
7. Related checklist item(s) (e.g., CHECK-P01, CHECK-S12)

## Step 4: Write Findings Document

Write findings to `{specsDir}/{feature}/VERIFY-{mode}-{YYYY-MM-DD}.md`:

```markdown
# Verification Report: {feature} ({mode})
Date: {YYYY-MM-DD}
Pipeline Stage: {currentStage}
Artifacts Reviewed: {list of files}

## Summary
- Total findings: {N}
- Gaps: {N}
- Inconsistencies: {N}
- Improvements: {N}
- Errors: {N}

## Findings

### V-001: {Short title}
- **Severity:** gap | inconsistency | improvement | error
- **Location:** {filename}, section {N.N}
- **Issue:** {Detailed description of what's wrong}
- **Suggested fix:** {Specific, actionable fix a fresh agent can apply}
- **References:** {Other files/sections involved}
- **Checklist:** {CHECK-XXX IDs that this finding relates to}

### V-002: ...

## Fix Execution Plan

### User Decisions Required
{List any findings that need user input before fixes can be applied. If none, write "None — all fixes can be applied directly."}

### Execution Steps

Apply these steps in order. Each step is self-contained — a fresh agent can
execute it without prior context beyond this document.

#### Step {N}: {Short title}
- **Files:** {exact file paths to edit}
- **Addresses:** {V-NNN finding IDs}
- **Checklist:** {CHECK-XXX IDs}
- **Action:** {Exact description of what to change — specific enough for a fresh agent}
- **Depends on:** {Step N or "none"}
- **Rationale:** {Why this order, why grouped this way}
```

### Example Findings

Here are complete example findings showing the expected quality:

**Gap example:**
```
### V-003: Missing retry logic for rate-limited API calls
- **Severity:** gap
- **Location:** specs/auth/03-session-management.md, section 3.2 "Token Refresh"
- **Issue:** PRD.md REQ-ERR-04 requires retry behavior when external auth providers rate-limit requests. The spec only handles rate limits by throwing `ProviderRateLimitError` — no retry logic, backoff strategy, or max-retry count is specified.
- **Suggested fix:** Add a "Retry Strategy" subsection to section 3.2 specifying: exponential backoff starting at 500ms, max 3 retries, circuit breaker after 5 consecutive failures. Reference the error type from 00-core-definitions.md.
- **References:** PRD.md REQ-ERR-04, 00-core-definitions.md (ProviderRateLimitError)
```

**Inconsistency example:**
```
### V-007: Conflicting session duration constants
- **Severity:** inconsistency
- **Location:** 00-core-definitions.md section 2.3 vs 03-session-management.md section 1.1
- **Issue:** 00-core-definitions.md defines `SESSION_DURATION_MS = 7 * 24 * 60 * 60 * 1000` (7 days), but 03-session-management.md section 1.1 states "sessions expire after 30 days." These contradict each other.
- **Suggested fix:** Align both documents to the PRD requirement. PRD.md REQ-SEC-03 says "sessions should have a reasonable expiry" without specifying a duration — ask the user which value is intended, then update both documents.
- **References:** PRD.md REQ-SEC-03, 00-core-definitions.md section 2.3, 03-session-management.md section 1.1
```

**Improvement example:**
```
### V-012: Testing strategy lacks fixture factory pattern
- **Severity:** improvement
- **Location:** specs/auth/08-testing-strategy.md, section 3 "Test Fixtures"
- **Issue:** The testing strategy describes test data inline in each test file. For a feature with 15+ test files, this leads to duplicated fixture data. A factory pattern would reduce duplication and make tests more maintainable.
- **Suggested fix:** Add a "Fixture Factories" subsection describing a `createTestSession()`, `createTestUser()` factory pattern in a shared `__fixtures__/` directory, consistent with how @repo/db handles test fixtures.
- **References:** 01-architecture-layout.md (directory structure), packages/db/src/__fixtures__/ (existing pattern)
```

## Step 5: Fix Plan and Next Steps

The Fix Execution Plan (written as part of the findings document in Step 4) is ALWAYS generated regardless of mode. This ensures the findings document is self-contained: diagnosis + action plan in one artifact.

When building the Fix Execution Plan:
1. Group related findings into logical steps (e.g., all type-system fixes together)
2. Order steps to avoid conflicts (fix shared types before documents that reference them)
3. Each step must be specific enough for a fresh agent with zero prior context to execute
4. Flag any findings that require user decisions before fixes can be applied

**If in plan mode:** Also write the Fix Execution Plan to the active plan file so the plan mode workflow is preserved. The user reviews the plan, exits plan mode, and a fresh agent executes the fixes.

**If not in plan mode:** Tell the user:
"Findings and fix plan written to `{findings-file}`.
Next steps:
  - Review the findings and fix plan
  - Run `/forge-fix {feature}` to apply fixes (recommended — works in any session)
  - Or enter plan mode and re-run `/forge-verify {feature}` for plan-mode workflow"

## Step 6: Update Pipeline State

Write pipeline state conforming to `references/pipeline-state-schema.json`.

Update `{specsDir}/{feature}/.pipeline-state.json`:
- Set the relevant verify entry status to `findings-reported`
- Record `findingsFile`, `findingsCount`, `verifiedAt`

Do NOT mark as `findings-applied` — that happens after the fix pass.

## Gotchas

- This skill should be run in plan mode for best results. The plan gives the user a chance to review before committing to changes.
- Verification is most valuable when it finds things that are MISSING, not just things that are present but imperfect. Prioritize gap detection over style preferences.
- Don't verify things that are intentionally left open (check the PRD's "Open Questions" section).
- If you find zero issues, say so honestly. Don't manufacture findings to seem thorough. But zero findings on a complex feature is suspicious — double-check.
- The findings document must be self-contained. A fresh agent reading it should be able to apply every fix without needing conversational context from this session.
- For backlog verification, also run `${CLAUDE_PLUGIN_ROOT}/scripts/validate-backlog.py` if it exists, and include any schema violations as findings.
