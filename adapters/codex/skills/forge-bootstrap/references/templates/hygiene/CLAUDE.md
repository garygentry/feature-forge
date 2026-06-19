# Claude Instructions — {{PROJECT_NAME}}

## Project Purpose

{{PURPOSE}}

## Getting Started

This project was scaffolded by forge-bootstrap. To continue development:

1. Review `forge.config.json` for the project configuration.
2. Run the forge pipeline (forge-1-prd → forge-0-epic → forge-3-specs → forge-4-backlog) to plan and implement features.
3. Use `forge-5-loop` to drive autonomous implementation.

## Working with Claude

- Use `/feature-forge:forge` to enter the forge pipeline for new features.
- The `forge.config.json` at the project root defines the stack, commands, and pipeline settings.
- Follow the patterns established in the existing codebase.

## Specs are pre-implementation

- Documents under `specs/` (PRDs, tech specs, numbered implementation specs) establish the backlog. They are **not** kept in sync with the code as it evolves.
- Don't flag or "fix" divergence between a finalized spec and the implementation — code is the source of truth for behavior.
- It's fine for `specs/` artifacts and `backlog.json` to reference specs for provenance, but implementation artifacts (source code, generated skills/agents, configs, docs) must not reference spec files, which may be archived or deleted after a feature ships.
