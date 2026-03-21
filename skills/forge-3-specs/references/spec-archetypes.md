# Implementation Spec Archetypes

This reference defines the types of implementation spec documents and their internal structure. Use this to plan which documents a feature needs.

## Always Required

### 00-core-types-shared.md
The shared type system for the feature. Every other spec document references types defined here.

**Sections:**
- Type aliases and union types
- Core interfaces (with JSDoc on every field)
- Error class hierarchy (base error, domain-specific errors, each with typed properties)
- Constants and enums
- Utility types (if any)

**Rules:**
- Every type must have JSDoc explaining its purpose
- Error classes must include `code`, `message`, and domain-specific context fields
- Export everything from a barrel `index.ts`

### 01-architecture-layout.md
How the feature is structured in the monorepo.

**Sections:**
- Directory tree (full, not abbreviated)
- Package.json: name, exports map (subpath exports), dependencies, scripts
- tsconfig.json: key compiler options
- Barrel export structure: what each index.ts re-exports
- Build and bundle considerations

**Rules:**
- Exports map must be explicit — list every subpath export
- Dependencies should distinguish runtime vs dev dependencies
- Internal monorepo dependencies must reference exact package names

### NN-testing-strategy.md (always last numbered document)
How to test this feature.

**Sections:**
- Testing framework and tooling (vitest, testing-library, etc.)
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
Use when the feature interacts with existing packages (almost always in a monorepo).

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
- Schema definition (Drizzle, Prisma, or raw SQL — match project conventions)
- Migration steps
- Rollback strategy
- Data seeding / fixtures
- Zero-downtime migration considerations (if applicable)

## Document Quality Checklist

Before finalizing any spec document, verify:

- [ ] Every section references PRD requirement IDs
- [ ] All TypeScript is valid syntax (not pseudocode)
- [ ] All type references resolve to definitions in 00-core-types-shared.md or clearly stated external packages
- [ ] Error scenarios are covered, not just happy paths
- [ ] Cross-references to other spec docs use exact filenames
- [ ] A "Dependencies" section states which other spec docs must be implemented first
- [ ] A "Verification" section describes how to confirm correct implementation
