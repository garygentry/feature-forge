# Implementation Spec Archetypes

This reference defines the types of implementation spec documents and their internal structure. Use this to plan which documents a feature needs.

## Always Required

### 00-core-definitions.md
The shared type system and data contracts for the feature. Every other spec document references definitions here.

**Sections:**
- Type aliases, union types, enums, or language-equivalent constructs
- Core types/interfaces/structs with documentation comments on every field
- Error/exception hierarchy (base error, domain-specific errors, each with typed properties)
- Constants and enumerations
- Utility types (if any)

**Rules:**
- Every type must have documentation comments explaining its purpose (JSDoc, docstrings, godoc, etc.)
- Error types must include `code`, `message`, and domain-specific context fields
- Export everything through the module's entry point following project conventions

### 01-architecture-layout.md
How the feature is structured in the project.

**Sections:**
- Directory tree (full, not abbreviated)
- Project manifest: name, exports/entry points, dependencies, build scripts
- Build/compiler configuration: key options
- Module export structure: what each entry point exposes
- Build and deployment considerations

**Rules:**
- Exports/entry points must be explicit — list every public module or subpath
- Dependencies should distinguish runtime vs dev dependencies
- Internal project dependencies must reference exact module/package names

### NN-testing-strategy.md (always last numbered document)
How to test this feature.

**Sections:**
- Testing framework and tooling (match project conventions — e.g., vitest, pytest, go test)
- Unit test approach: what to test, what to mock
- Integration test approach: how to test cross-package interactions
- Test fixtures and factories
- Coverage targets
- Test file location conventions

## Conditionally Required

### ##-{domain-concern}.md (one per major subsystem)
Use when the feature has distinct subsystems that warrant separate specification.

**Examples:** `02-provider-registry.md`, `03-streaming-engine.md`, `04-prompt-templates.md`

**Sections:**
- Purpose and scope (which PRD requirements this covers)
- Public API: exported functions, classes, or components with full signatures
- Internal implementation: key algorithms, data flows, state management
- Configuration: what's configurable, defaults, validation
- Error handling: what can fail, how errors are typed and surfaced
- Dependencies: on types from 00, on other subsystems, on external packages

### ##-integration-points.md
Use when the feature interacts with existing modules or packages.

**Sections:**
- Integration map: which packages, which direction (depends-on vs depended-upon-by)
- For each integration point:
  - Which types/interfaces are shared
  - Data flow description
  - Import paths and barrel exports
  - Any adapter or bridge code needed
- Migration considerations: does integration require changes to existing packages?

### ##-ui-components.md
Use when the feature has a frontend surface.

**Sections:**
- Component tree / hierarchy
- Props interfaces for each component
- State management approach
- Styling approach (consistent with project conventions)
- Responsive behavior
- Accessibility requirements (ARIA, keyboard navigation)

### ##-data-migration.md
Use when the feature involves schema changes or data migration.

**Sections:**
- Schema definition (using project's ORM/migration tool, or raw SQL — match project conventions)
- Migration steps
- Rollback strategy
- Data seeding / fixtures
- Zero-downtime migration considerations (if applicable)

## Document Quality Checklist

Before finalizing any spec document, verify:

- [ ] Every section references PRD requirement IDs
- [ ] All code is valid syntax in the project's language (not pseudocode)
- [ ] All type references resolve to definitions in 00-core-definitions.md or clearly stated external packages
- [ ] Error scenarios are covered, not just happy paths
- [ ] Cross-references to other spec docs use exact filenames
- [ ] A "Dependencies" section states which other spec docs must be implemented first
- [ ] A "Verification" section describes how to confirm correct implementation
