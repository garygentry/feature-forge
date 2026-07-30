# Tech-Spec Verification Checklist

Detailed checklist for the **tech** verification mode, loaded by the `forge-verifier` leaf subagent dispatched for that mode. Execute EVERY check — do not skip.

> **Stack-specific details:** When a stack profile exists at `references/stacks/{stack}.md`, load it alongside this checklist for language-specific check criteria (e.g., what "valid syntax" means, what the type check command is, how module exports work).

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

