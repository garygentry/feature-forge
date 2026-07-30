# Verify Findings Template (orchestrator-only)

Loaded by the **parent orchestrator** role of `forge-verify` at Step 4 (write the findings document) and Step 6 (epic-mode state write). The `forge-verifier` leaf subagent MUST NOT load this file — it holds only orchestrator-facing material (see `SKILL.md` → "Which role are you?").

## Findings Document Template (Step 4)

Write findings to `{specsDir}/{feature}/.verification/VERIFY-{mode}-{YYYY-MM-DD}.md`
(for epic mode, `{specsDir}/{epic}/.verification/VERIFY-epic-{YYYY-MM-DD}.md` — same
format, with `{mode}=epic`). Ensure the `.verification/` subdirectory exists first.

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

## Example Findings (Step 4)

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
- **Suggested fix:** Align both documents to the PRD requirement. PRD.md REQ-SEC-03 says "sessions should have a reasonable expiry" without specifying a duration — use `AskUserQuestion` to ask the user which value is intended, then update both documents.
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

## Epic Mode State Write Detail (Step 6)

Epic mode is **epic-scoped**, not per-feature: record its result into the epic-level
state file `{specsDir}/{epic}/.epic-state.json` — **never** into any member's
`.pipeline-state.json`. This file holds only epic-scoped stage entries (currently just
`forge-verify-epic`) and carries **no cached per-feature member status** (so it does not
violate REQ-STATE-02; per-feature status is always derived live from each member's
`.pipeline-state.json`).

Set `stages.forge-verify-epic.status` to `findings-reported` (or `passed` if zero
findings), recording `findingsFile`, `findingsCount`, and `verifiedAt`. The minimal
shape:

```jsonc
{
  "epic": "auth-overhaul",              // matches the manifest `epic`
  "stages": {
    "forge-verify-epic": {
      "status": "findings-reported",     // "findings-reported" | "passed" | "findings-applied"
      "findingsFile": ".verification/VERIFY-epic-2026-06-12.md",
      "findingsCount": 3,
      "verifiedAt": "2026-06-12T00:00:00Z"
    }
  }
}
```

**Write mechanism.** `epic-manifest.py` exposes no subcommand that writes this file, so
the skill writes it **directly**, using an atomic temp-file + `os.replace()` pattern
(mirroring `02-manifest-helper-cli.md §3.3`): serialize the merged state to a sibling
temp file in `{specsDir}/{epic}/`, flush, then `os.replace()` it into place. Create the
file **lazily on first write** (a missing file is simply created; an existing file is
read, its `stages.forge-verify-epic` entry merged/replaced, and rewritten). On any I/O
failure, **report the error and leave any prior `.epic-state.json` intact** (never a
partial write). For example:

```bash
python3 - "$SPECS_DIR/$EPIC" <<'PY'
import json, os, sys, tempfile
from pathlib import Path
epic_dir = Path(sys.argv[1])
path = epic_dir / ".epic-state.json"
state = {}
if path.exists():
    state = json.loads(path.read_text())
state.setdefault("epic", epic_dir.name)
state.setdefault("stages", {})
state["stages"]["forge-verify-epic"] = {
    "status": "findings-reported",   # or "passed" when findingsCount == 0
    "findingsFile": ".verification/VERIFY-epic-2026-06-12.md",
    "findingsCount": 3,
    "verifiedAt": "2026-06-12T00:00:00Z",
}
fd, tmp = tempfile.mkstemp(dir=str(epic_dir), prefix=".epic-state.", suffix=".tmp")
try:
    with os.fdopen(fd, "w") as f:
        json.dump(state, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
except OSError as e:
    try:
        os.unlink(tmp)
    except OSError:
        pass
    print(f"failed to write .epic-state.json: {e}", file=sys.stderr)
    raise
PY
```
