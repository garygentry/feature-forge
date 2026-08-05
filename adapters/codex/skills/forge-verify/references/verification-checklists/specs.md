# Specs Verification Checklist

Detailed checklist for the **specs** verification mode, loaded by the `forge-verifier` leaf subagent dispatched for that mode. Execute EVERY check — do not skip.

> **Stack-specific details:** When a stack profile exists at `references/stacks/{stack}.md`, load it alongside this checklist for language-specific check criteria (e.g., what "valid syntax" means, what the type check command is, how module exports work).

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

> **A quoted foreign requirement id is not an orphan.** A suite may legitimately mention a `REQ-` id it does not own — most often when a spec quotes an antecedent feature's test docstrings verbatim. Such ids may be declared, one per line, in `{resolvedFeatureDir}/.traceability-allowlist` (blank lines and `#` comments ignored), or passed as a repeatable `--allow-orphan REQ-ID` to `scripts/validate-traceability.py`. Allowed ids are reported as `ALLOWED FOREIGN REFERENCES` (`allowed_orphans` under `--json`) rather than silently dropped, and an entry matching nothing is reported as `STALE ALLOWLIST ENTRIES` (`unused_allowlist_entries`), which is advisory and does not fail the check. Before filing an orphaned reference as a finding, check whether it is already declared there — a declared id is a recorded decision, not a defect.

