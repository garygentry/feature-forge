# PRD Template and Interview Guide

This reference defines the standard PRD structure and the interview questions to cover for each section.

## PRD Document Structure

```markdown
# {Feature Name} — Product Requirements Document

## 1. Problem Statement
What problem does this feature solve? Who has this problem? Why does it matter now?

## 2. User Stories
As a [role], I want [capability], so that [benefit].
- Include primary actors and secondary actors
- Include admin/operator stories, not just end-user stories

## 3. Functional Requirements

### 3.1 {Capability Area}
- REQ-{CAT}-01: {Requirement description}
  - Priority: P0 (must have) | P1 (should have) | P2 (nice to have)
  - Notes: {Any clarification}

### 3.2 {Another Capability Area}
...

## 4. Non-Functional Requirements

### 4.1 Performance
- REQ-PERF-01: ...

### 4.2 Security
- REQ-SEC-01: ...

### 4.3 Observability
- REQ-OBS-01: ...

### 4.4 Accessibility
- REQ-A11Y-01: ...

### 4.5 Scalability
- REQ-SCALE-01: ...

## 5. Constraints
Technical, organizational, or external constraints that must be respected.
(This is where technology mandates go — e.g., "must integrate with existing @repo/auth package")

## 6. Out of Scope
Explicitly list what this feature will NOT do in this version.

## 7. Open Questions
Unresolved items that need answers before or during implementation.

## 8. Success Criteria
How do we know this feature is done and working correctly?
```

## Interview Question Categories

Cover ALL of these areas during the interview. Don't move on until each is addressed.

### Core Understanding
- What is the feature in one sentence?
- Who are the primary users? Secondary users? Admins/operators?
- What workflow or process does this support?
- What exists today that this replaces or augments?

### Functional Depth
- Walk me through the happy path end to end
- What are the key data entities involved?
- What inputs does the system accept? What are valid/invalid inputs?
- What outputs does the system produce?
- What states can things be in? What transitions are allowed?
- What happens when the user makes a mistake?

### Error and Edge Cases
- What happens when X is unavailable?
- What if two users do Y at the same time?
- What happens with empty inputs? Huge inputs? Malformed inputs?
- What does partial failure look like?
- How should the system recover from crashes mid-operation?

### Integration
- What existing parts of the system does this interact with?
- What data does it need from other features?
- What data does it provide to other features?
- Are there external systems or APIs involved?

### Non-Functional
- What's the expected load? (requests/sec, concurrent users, data volume)
- What are the latency requirements?
- What security considerations exist? (authn, authz, data sensitivity)
- What needs to be logged, monitored, or alerted on?
- Are there accessibility requirements?

### Scope and Priority
- What's the minimum viable version of this?
- What would you cut if you had to ship in half the time?
- What's explicitly NOT part of this feature?
- Are there follow-up features that depend on decisions made here?

### Success
- How do you know this feature is working correctly?
- What would a user complain about if we got it wrong?
- Are there quantitative targets? (latency < Xms, uptime > Y%)
