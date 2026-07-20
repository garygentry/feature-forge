# Verification Checklists

Detailed checklists for each verification mode. Execute EVERY check — do not skip.

> **Stack-specific details:** When a stack profile exists at `references/stacks/{stack}.md`, load it alongside this checklist for language-specific check criteria (e.g., what "valid syntax" means, what the type check command is, how module exports work).

## PRD Mode Checklist

### Completeness
- [ ] **CHECK-P01**: All template sections from `references/prd-template.md` are populated
- [ ] **CHECK-P02**: No TBD or TODO placeholders remain in the document
- [ ] **CHECK-P03**: Out-of-scope section exists and is specific (not just "everything else")
- [ ] **CHECK-P04**: Open questions section contains only actionable items (not vague concerns)
- [ ] **CHECK-P05**: Success criteria are measurable and verifiable

### Requirement Quality
- [ ] **CHECK-P06**: Every requirement has a unique ID (REQ-XXX-NN format)
- [ ] **CHECK-P07**: Every requirement has a priority assigned (P0/P1/P2)
- [ ] **CHECK-P08**: Every requirement is testable/verifiable — could you write an acceptance test for it?
- [ ] **CHECK-P09**: No requirements contain technology decisions (specific libraries, frameworks, or implementation choices) unless clearly labeled as constraints with justification
- [ ] **CHECK-P10**: User stories cover all identified actors/personas

### Non-Functional Requirements
- [ ] **CHECK-P11**: Non-functional requirements are quantified where applicable (latency targets, uptime SLAs, throughput minimums)
- [ ] **CHECK-P12**: Security requirements are explicit, not assumed
- [ ] **CHECK-P13**: Constraints section distinguishes mandates (must) from preferences (should/nice-to-have)

### Open-Ended Analysis
- [ ] **CHECK-P14**: Are there implicit requirements that should be made explicit? (e.g., assumptions about authentication, authorization, data retention)
- [ ] **CHECK-P15**: Are there requirement conflicts or tensions? (e.g., performance vs. completeness, simplicity vs. flexibility)

## Tech-Spec Mode Checklist

### Requirement Traceability
- [ ] **CHECK-T01**: Every tech decision traces to at least one PRD requirement (REQ-XXX-NN)
- [ ] **CHECK-T02**: No tech decisions contradict PRD constraints
- [ ] **CHECK-T03**: Every P0 PRD requirement has a corresponding tech decision or is explicitly deferred with rationale

### Integration Analysis
- [ ] **CHECK-T04**: Integration analysis section is complete — all packages identified
- [ ] **CHECK-T05**: Import paths and function signatures are verified against actual source code
- [ ] **CHECK-T06**: For each integration point: shared types/contracts are explicitly named
- [ ] **CHECK-T07**: For each integration point: data flow direction is clear
- [ ] **CHECK-T08**: Changes required to existing packages are specified

### Design Quality
- [ ] **CHECK-T09**: Alternatives considered for major decisions (not just "we chose X")
- [ ] **CHECK-T10**: Error handling strategy is defined (error types, propagation, recovery)
- [ ] **CHECK-T11**: Testing approach is specified (unit, integration, e2e strategy)
- [ ] **CHECK-T12**: Data model aligns with PRD data requirements

### Completeness
- [ ] **CHECK-T13**: Package/module structure is defined with exports map
- [ ] **CHECK-T14**: Configuration approach is specified
- [ ] **CHECK-T15**: Migration/deployment considerations are addressed if applicable

### Open-Ended Analysis
- [ ] **CHECK-T16**: Are there integration points that could cause implementation surprises? (e.g., undocumented behavior, version incompatibilities, missing APIs)
- [ ] **CHECK-T17**: Are there scalability concerns unaddressed by the current design? (e.g., data growth, concurrent users, resource limits)

## Specs Mode Checklist

### Requirement Coverage
- [ ] **CHECK-S01**: Every PRD requirement (REQ-XXX-NN) is referenced by at least one implementation spec
- [ ] **CHECK-S02**: Every P0 (must-have) requirement has detailed implementation guidance, not just a mention
- [ ] **CHECK-S03**: Every P1 requirement is at least acknowledged with an implementation approach
- [ ] **CHECK-S04**: No implementation spec sections exist that don't trace to a PRD requirement or tech-spec decision (orphaned specs indicate scope creep)

### Tech Spec ↔ Implementation Spec Consistency
- [ ] **CHECK-S05**: Every technology decision in the tech spec is reflected in the implementation specs
- [ ] **CHECK-S06**: Package structure in 01-architecture-layout.md matches what the tech spec describes
- [ ] **CHECK-S07**: Dependencies listed in the tech spec match those in the architecture spec
- [ ] **CHECK-S08**: No implementation spec contradicts a tech-spec decision

### Type System Integrity
- [ ] **CHECK-S09**: All type definitions in 00-core-definitions.md are valid syntax in the project's language (not pseudocode)
- [ ] **CHECK-S10**: All types referenced in other spec docs are defined in 00-core-definitions.md or an explicit external package
- [ ] **CHECK-S11**: Error classes form a consistent hierarchy with no gaps
- [ ] **CHECK-S12**: No duplicate or conflicting type definitions across documents
- [ ] **CHECK-S13**: Every type/interface/struct has documentation comments on every field (JSDoc, docstrings, godoc, etc.)

### Cross-Reference Consistency
- [ ] **CHECK-S14**: All file references between spec documents point to actual files
- [ ] **CHECK-S15**: Section references (e.g., "see section 3.2 of 02-provider-registry.md") point to actual sections
- [ ] **CHECK-S16**: Dependency ordering between spec docs is consistent (no circular dependencies)
- [ ] **CHECK-S17**: Import paths referenced in specs are consistent with the exports map in 01-architecture-layout.md

### Error Handling Coverage
- [ ] **CHECK-S18**: Every operation that can fail has an error type defined
- [ ] **CHECK-S19**: Error propagation is described: where errors are thrown, caught, transformed, and surfaced
- [ ] **CHECK-S20**: User-facing error messages are specified (not just error codes)
- [ ] **CHECK-S21**: Recovery behavior is described for recoverable errors

### Integration Point Completeness
- [ ] **CHECK-S22**: Every package listed in the tech spec's integration section has corresponding detail in the implementation specs
- [ ] **CHECK-S23**: For each integration: the shared types/contracts are explicitly named
- [ ] **CHECK-S24**: For each integration: data flow direction is clear
- [ ] **CHECK-S25**: If integration requires changes to existing packages, those changes are specified
- [ ] **CHECK-S26**: Import paths match actual package export maps

### Edge Cases and Non-Functional
- [ ] **CHECK-S27**: Concurrent access scenarios are addressed if relevant
- [ ] **CHECK-S28**: Empty/null/undefined inputs are handled
- [ ] **CHECK-S29**: Performance-sensitive paths are identified
- [ ] **CHECK-S30**: Security considerations from PRD are reflected in implementation
- [ ] **CHECK-S31**: Observability (logging, metrics, tracing) approach is specified if PRD requires it
- [ ] **CHECK-S32**: Each implementation spec has a clear "public API" section that defines what is exported vs internal

### Testing Strategy
- [ ] **CHECK-S33**: Testing strategy document exists
- [ ] **CHECK-S34**: Test approach covers unit, integration, and e2e as appropriate
- [ ] **CHECK-S35**: Mock/fixture strategy is defined for external dependencies
- [ ] **CHECK-S36**: Coverage targets are stated
- [ ] **CHECK-S37**: Test fixtures and mocks defined in specs align with real interface shapes from 00-core-definitions.md

### Traceability
- [ ] **CHECK-S38**: Build a complete traceability matrix from every REQ-XXX-NN to the spec document and section that implements it. Any REQ ID not found in at least one spec is a gap finding.

## Backlog Mode Checklist

### Schema Compliance
- [ ] **CHECK-B01**: backlog.json is valid JSON
- [ ] **CHECK-B02**: Every item has all required fields: id, type, priority, title, description, acceptanceCriteria, status, dependsOn, specReferences
- [ ] **CHECK-B03**: All `id` values are unique
- [ ] **CHECK-B04**: All `type` values are valid (feature, bugfix, chore, etc.)
- [ ] **CHECK-B05**: All `priority` values are valid numbers
- [ ] **CHECK-B06**: All `status` values are valid (pending, in-progress, complete, etc.)

### Spec Coverage
- [ ] **CHECK-B07**: Every implementation spec document is referenced by at least one backlog item
- [ ] **CHECK-B08**: Every P0 PRD requirement is covered by at least one backlog item's acceptance criteria
- [ ] **CHECK-B09**: No backlog item references a spec file that doesn't exist
- [ ] **CHECK-B10**: specReferences paths are valid relative paths to actual files

### Task Quality
- [ ] **CHECK-B11**: Each item is scoped to be completable in a single rauf loop iteration
- [ ] **CHECK-B12**: Descriptions are detailed enough for a fresh agent with no prior context
- [ ] **CHECK-B13**: Acceptance criteria are objectively verifiable (not subjective like "works well")
- [ ] **CHECK-B14**: Each item specifies what files to create or modify

### Dependency Ordering
- [ ] **CHECK-B15**: `dependsOn` references are valid item IDs
- [ ] **CHECK-B16**: No circular dependencies exist
- [ ] **CHECK-B17**: Foundation items (types, scaffold) have no dependencies
- [ ] **CHECK-B18**: Items that depend on types/interfaces reference the item that creates them
- [ ] **CHECK-B19**: Priority ordering is consistent with dependency ordering (dependencies should have equal or higher priority)

### Completeness
- [ ] **CHECK-B20**: There is an item for the initial package scaffold
- [ ] **CHECK-B21**: There is an item for shared types and error hierarchy
- [ ] **CHECK-B22**: There are items for each major subsystem
- [ ] **CHECK-B23**: There are items for integration wiring (not just isolated subsystems)
- [ ] **CHECK-B24**: There are items for tests (or testing is included in each feature item's acceptance criteria)
- [ ] **CHECK-B25**: No large items that try to do too many things (should be broken down)

### Generated-Artifact Freshness
- [ ] **CHECK-B26**: **Generated-artifact freshness vs. `testCommand` `--check` gates** (#145). When a
  project's configured `testCommand` (forge.config.json) gates on **staleness of generated artifacts**
  — sub-commands of the shape `<generator> --check` / `--verify` / `:check` that fail if a checked-in
  generated file is out of date with its source — every backlog item that regenerates *one* gated
  artifact must regenerate (and commit) **all** the sibling artifacts those same `--check` gates
  depend on, or the item will pass locally yet red-gate on the stale-generated check. Verify
  heuristically:
  1. **Enumerate the gates.** String-scan `testCommand` for `--check`-style freshness sub-commands and
     collect the generator/artifact each one guards (e.g. `build-benchmarks --check` guards
     `partner-program-benchmarks`). If the command shape is unrecognized (no parseable `--check`
     tokens), this check is **advisory / not-applicable** — never a hard fail.
  2. **A gate with no regenerator.** If a `--check` gate guards an artifact that **no** backlog item
     regenerates, and some item edits that artifact's *source*, flag a `gap`: the source change will
     trip the freshness gate with nothing scheduled to refresh the output.
  3. **Partial regeneration.** If an item regenerates a proper subset of the artifacts gated by the
     `--check` set it touches (e.g. runs `build-partner-programs` + `build-analysis` but the gate also
     covers `build-benchmarks`), flag an `inconsistency` naming the missing generator(s) and
     recommending they be added to that item's execute + commit sequence. Same posture as the authoring
     guidance in `forge-4-backlog` / rauf `author-backlog`: enumerate the whole `--check`-gated set, not
     just the artifact the item is "about".

### Artifact Lifecycle Consistency
- [ ] **CHECK-B27**: **No test item forcing a lifecycle transition another item forbids** (#150).
  *Advisory heuristic — keyword/artifact-name based; **not-applicable** when no lifecycle vocabulary is
  present, **never** a hard fail.* A **lifecycle state** (draft / published / released / approved /
  reviewed / signed-off / gated) is a downstream-project concept forge does not itself track — but a
  backlog can still encode a **contradiction** about one named artifact: item A pins artifact `X` as
  *draft* / *unpublished* / *unreviewed* while item B asserts (in its acceptance criteria or a test it
  adds) that `X` is *published* / *released* / *approved*, with **no** publishing/review item for `X`
  anywhere in B's dependency closure. That leaves a **test/e2e item as the only thing forcing the
  transition** — and since the autonomous loop can neither publish a package nor stand in for a human
  reviewer, asked to make such a test green it **fabricates** the publication or sign-off (a provenance
  defect a `--review` pass has caught in the wild). Verify heuristically:
  1. **Find lifecycle assertions.** Scan item titles/descriptions/`acceptanceCriteria` for a named
     artifact paired with a lifecycle-state keyword — earlier states (`draft` / `unpublished` /
     `pending review` / `unreleased`) vs later states (`published` / `released` / `approved` / `live` /
     `signed-off` / `gated`). If **no** item carries such vocabulary, this check is **not-applicable**.
  2. **Pair by artifact name.** Group assertions that reference the **same named artifact**. A pair
     where one item requires the *earlier* state and another asserts the *later* state is a candidate.
  3. **Check the dependency closure.** If the later-state item has **no** publish / review / human-gated
     item for that artifact in its transitive `dependsOn`, flag an `inconsistency`: name the artifact,
     both items, and recommend either (a) adding a `dependsOn` on an explicit human-gated publish/review
     item that legitimately produces the state, or (b) re-asserting the state via a dev-build / fixture
     path — never letting a test item be the sole driver of the transition (mirrors the authoring
     guidance in `forge-4-backlog` / rauf `author-backlog`). **Report, do not repair.**

  > **Anti-pattern (visible even where the heuristic can't fire):** a test/e2e item whose pass condition
  > is "artifact `X` is published / approved / reviewed" while the backlog contains no human-gated
  > publish or review item producing that state. The autonomous loop cannot publish or sign off on
  > behalf of a human; asked to make such a test green it will **fabricate** the published/reviewed
  > provenance. Any item asserting a human-gated lifecycle state must trace — via `dependsOn` — to the
  > item that legitimately produces it, or assert the state through a dev-build / fixture path instead.

## Implementation Mode Checklist

### Spec Compliance
- [ ] **CHECK-I01**: Every file listed in 01-architecture-layout.md exists
- [ ] **CHECK-I02**: Package.json exports map matches what the spec describes
- [ ] **CHECK-I03**: Every type in 00-core-definitions.md is implemented
- [ ] **CHECK-I04**: Every error class is implemented with correct properties

### Backlog Completion
- [ ] **CHECK-I05**: Every backlog item marked "complete" has its acceptance criteria met
- [ ] **CHECK-I06**: No backlog items are still "pending" or "in-progress"
- [ ] **CHECK-I07**: Acceptance criteria can be verified by reading the code

### Integration
- [ ] **CHECK-I08**: Import paths work (no broken imports)
- [ ] **CHECK-I09**: Module exports/entry points re-export everything the spec says they should
- [ ] **CHECK-I10**: Types shared with other packages are compatible
- [ ] **CHECK-I11**: Type checking / linting passes for the module (`{typeCheckCommand}` from forge.config.json succeeds)
- [ ] **CHECK-I12**: Type checking / linting passes for modules that depend on this one

### Code Quality
- [ ] **CHECK-I13**: No placeholder or TODO comments that should have been resolved
- [ ] **CHECK-I14**: Error handling matches what the specs describe
- [ ] **CHECK-I15**: No hardcoded values that should be configurable
- [ ] **CHECK-I16**: Tests exist and pass
- [ ] **CHECK-I17**: No obvious missing test cases for documented edge cases

### Documentation
- [ ] **CHECK-I18**: Package has a README or the docs directory has been populated
- [ ] **CHECK-I19**: Exported functions/classes have documentation comments (JSDoc, docstrings, godoc, etc.)
- [ ] **CHECK-I20**: Configuration options are documented

### Runnability

> **When these fire:** only at impl-verify **completion** (impl mode runs post-loop), never mid-loop — an early skeleton that only compiles is not punished. **Both degrade gracefully:** a feature with no runnable surface (a pure library with no bootstrap contract) or no configured `smokeCommand` yields an **advisory not-applicable** finding, never a hard fail — the same way a null `{typeCheckCommand}` is handled. These exist because `CHECK-I01..I20` are all static reads + typecheck/lint + "tests exist"; nothing here asserts the assembled application actually **runs**. A bootstrap that is exported and unit-tested (each test calls it manually) but never wired into a runtime entrypoint passes every other check yet serves no real request (#121).

- [ ] **CHECK-I21**: **End-to-end smoke passes.** If `smokeCommand` from forge.config.json is set, execute it — it boots the wired entrypoint and drives one happy-path request end-to-end; **pass iff exit 0**. A non-zero exit is an `error` finding (the assembled app does not run — quote the command's failing output). If `smokeCommand` is `null`, this is **advisory**: emit a `not-applicable` finding recommending the user configure a `smokeCommand` so "clean" means "it runs" (never fabricate or guess a command — run only the user-configured one, exactly as `CHECK-I11` runs only a configured `{typeCheckCommand}`).
  - **Prefer the dev runtime the developer actually uses (#149).** Recommend the configured `smokeCommand` boot the app in its **development** mode — the dev server / watch loop / HMR runtime — not only a clean production build. The failure modes that a static typecheck and a prod smoke both miss live in the dev runtime: **module-graph-identity** bugs (a "singleton" duplicated across a re-evaluated module graph, so the initialized instance and the one the request path reads are different objects) and **watch-loop** bugs (an init that fires once but never re-fires on hot reload, or fires on every reload and leaks). A prod build evaluates the graph once and hides both. When the project is served in dev during development, the `smokeCommand` should exercise that same runtime.
  - **For a fix, re-verify in the mode the bug manifested.** When impl-verify runs after a **fix** (not a greenfield build), re-run the smoke in the **same runtime mode where the original bug appeared** — a bug reproduced in dev/watch mode is not proven fixed by a green prod-mode smoke, and vice versa. Note the mode in the finding so "smoke passed" is unambiguous about *which* runtime was exercised.
- [ ] **CHECK-I22**: **Runtime-required bootstrap has a non-test caller.** Every exported bootstrap / `init*` / singleton-populator the specs mark as **required for runtime** must have ≥1 **non-test** call site on a runtime path — an entrypoint such as `main` / `instrumentation` / a route / a layout / a worker, NOT only test files. Statically grep for each such symbol's references (use the stack profile `references/stacks/{stack}.md` **Runtime Entrypoints & Bootstrap-Wiring Sites** list for what counts as a runtime entrypoint in this language). A symbol that is exported and covered by tests but referenced **only** from test files is a `gap` — the #121 walking-skeleton (bootstrap wired to nothing). Degrades naturally: a feature whose specs mark no bootstrap symbol as runtime-required is `not-applicable`. Weaker than `CHECK-I21` (it proves a call site exists, not that the boot succeeds), so it complements rather than replaces the smoke.
- [ ] **CHECK-I23**: **Heavy bootstrap wired into a universal startup entry — recommend lazy init** (#149). *Advisory heuristic — a `gap`/`improvement` at most, **never** a hard fail.* When a runtime-required `init`/bootstrap/singleton-populator is wired into a **framework bootstrap entry that runs on every startup** (a Next.js `instrumentation.ts`, an app-server preload/`register` hook, a global setup module) **and** that init pulls in a **large server-only import graph** (DB clients, ORMs, queue/background workers, telemetry exporters, the whole service layer), recommend moving to **lazy initialization at the entry that already loads that graph** — the first route / handler / worker that needs it — rather than eager wiring at the universal entry. Eager wiring drags the heavy graph into every cold start, and in dev into every module re-evaluation (the watch-loop cost `CHECK-I21` also targets). **Detect statically:** from the stack profile's **Runtime Entrypoints & Bootstrap-Wiring Sites** list, identify this stack's universal bootstrap entries; grep those files for imports of the feature's runtime-required bootstrap symbols (`CHECK-I22`) and for the server-only heavy-import markers the profile names. A match → an `improvement`/`gap` finding naming the entry, the heavy graph it pulls, and the lazier call site to move initialization to. Degrades to `not-applicable` when the stack has no universal bootstrap entry, when no heavy init is wired there, or when the profile lists no bootstrap-wiring sites — **report, do not repair.**

## Epic Mode Checklist

Run `epic-manifest.py validate "{epic}" --specs-dir "{specsDir}" --json` once; map its
findings to E01/E02/E03/E08. Then perform the judgment checks E04–E07, E09, and E10 by
reading the manifest, EPIC.md, completed members' specs, and (for E10) sibling members'
committed tests.

```bash
R="$(bash -c 'for d in "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/epic-manifest.py" validate "{epic}" --specs-dir "{specsDir}" --json
```

### Manifest Integrity (helper-delegated)
- [ ] **CHECK-E01**: `epic-manifest.json` conforms to `epic-manifest-schema.json`
  (delegated: `validate` reports `schema` / `corrupt-json` findings).
- [ ] **CHECK-E02**: the `dependsOn` graph is **acyclic** (delegated: `validate` reports
  `cycle`).
- [ ] **CHECK-E03**: no dangling `dependsOn` / `consumes.from` — every reference names a
  feature in `features[]` (delegated: `validate` reports `dangling-ref`).
- [ ] **CHECK-E08**: **global name uniqueness** across the specs tree — no feature name
  resolves to more than one feature-shaped dir (delegated: `validate` / `check-name`
  report `duplicate-name` / `ambiguous`). Surfaced non-fatally for manual cleanup.

### Charter & Contract Coverage (verifier judgment)
- [ ] **CHECK-E04**: **charter coverage** — every feature has a non-empty `charter`
  stating scope **and** contract obligations (REQ-EPIC-04).
- [ ] **CHECK-E05**: each feature has a meaningful `exposes`/`consumes` declaration — flag
  a feature with empty contracts that the narrative implies should have them
  (REQ-EPIC-03). (Empty is *schema-legal* but suspicious for a feature other features
  depend on.)
- [ ] **CHECK-E06**: **EPIC.md ⇆ manifest contract drift, for completed features only** —
  the contracts in `EPIC.md` match the manifest `exposes`/`consumes`, and a completed
  feature's specs actually deliver what it `exposes`. Drift between EPIC.md prose and the
  manifest, or between the manifest and the built spec, is a finding (REQ-VERIFY-01).
- [ ] **CHECK-E07**: **back-pointer ⇆ manifest consistency** — every member's
  `.pipeline-state.json` `epic` value names this epic, and every `features[]` entry has a
  matching member directory. On conflict the **manifest wins** (REQ-STATE-01); report, do
  not auto-repair.
- [ ] **CHECK-E09**: **open epic change requests** — any member whose `.pipeline-state.json`
  carries `epicChangeRequests[]` entries with `status: "open"` is surfaced as a **non-fatal**
  finding (one per open request). Severity keys off `blocksCurrent`: a **blocking** request →
  `inconsistency` (the epic decomposition and an in-flight member disagree; specs written now
  would build on a soon-invalid premise), a **non-blocking** request → `improvement` (a
  peer/downstream change to reconcile when convenient). Name the request's `kind`, `target`,
  and `rationale`, and point at `/feature-forge:forge-0-epic {epic}` to reconcile. **Report, do
  not repair** (same posture as CHECK-E07). Which members have open requests comes from the
  same `render-status --json` counts the navigator uses (`features[].openEpicChangeRequests` /
  `.blockingEpicChangeRequests`); the per-request `kind`/`target`/`rationale` detail is read
  from the member `.pipeline-state.json` already loaded in Step 2. This is the pre-emptive
  surface for the divergence class CHECK-E06/E07 otherwise catch only after the fact.
- [ ] **CHECK-E10**: **cross-member shared-state test coupling** (#144). A member that writes or
  migrates a file a *sibling's* committed tests already pin will break the sibling's suite the
  moment it runs — blocking every one of its own commits from a green test gate — yet nothing in
  E04–E09 catches it (contracts cover code symbols, not shared data files). Detect it heuristically,
  per member `M`:
  1. **Collect `M`'s mutated paths.** Take `M`'s `mutatesShared[]` from the manifest if present
     (the authored precision hint). If absent or empty, fall back to grepping `M`'s specs
     (change-maps / "files this writes") and backlog item `execute` steps for project-root-relative
     paths it creates, writes, or migrates (data corpora, generated fixtures, migration outputs —
     not `M`'s own source modules or its own tests).
  2. **Grep sibling tests for reads of those paths.** For every *other* member `S` that is already
     **`complete`** (derived status — its regression suite is live and gating), grep `S`'s committed
     **test** files/globs for a read/import/load of any path in step 1. Use the stack profile
     (`references/stacks/{stack}.md`) for what a test glob looks like in this language.
  3. **Emit the finding.** A hit → a non-fatal `inconsistency` finding: name `M`, the shared path,
     the sibling `S` and the specific test, and **recommend a reconciliation backlog item** on `M`
     (regenerate/re-pin `S`'s fixture, or update `S`'s test to the new shape) scheduled *before*
     `M`'s first mutating item — so the coupling is planned, not discovered mid-loop on a red gate.
     **Report, do not repair** (same posture as CHECK-E07/E09). Degrades to a clean no-op when no
     member declares or greps a shared write, or when no completed sibling reads it — never a
     spurious hard-fail.

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
