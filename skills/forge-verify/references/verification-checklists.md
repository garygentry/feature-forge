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

## Epic Mode Checklist

Run `epic-manifest.py validate "{epic}" --specs-dir "{specsDir}" --json` once; map its
findings to E01/E02/E03/E08. Then perform the judgment checks E04–E07 by reading the
manifest, EPIC.md, and completed members' specs.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/epic-manifest.py" validate "{epic}" --specs-dir "{specsDir}" --json
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
