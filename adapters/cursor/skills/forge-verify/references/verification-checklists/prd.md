# PRD Verification Checklist

Detailed checklist for the **prd** verification mode, loaded by the `forge-verifier` leaf subagent dispatched for that mode. Execute EVERY check — do not skip.

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

