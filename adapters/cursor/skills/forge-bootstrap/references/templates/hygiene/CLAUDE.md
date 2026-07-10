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

## Tooling feedback (feature-forge / rauf)

I'm driving this project with the feature-forge pipeline and the rauf loop, and I want to keep improving them. When you hit friction with either tool, help me capture it — papercuts included, not just outright bugs.

- **When to flag:** any forge/rauf command, skill, agent, or prompt that is confusing, buggy, missing a capability, forces a workaround, or produces a surprising result.
- **Where to file** — route by which tool the friction is with:
  - feature-forge (pipeline stages, `/feature-forge:*`, forge skills/agents): https://github.com/garygentry/feature-forge/issues
  - rauf (the autonomous loop runner, `rauf` CLI): https://github.com/garygentry/rauf/issues
- **How:** capture it while fresh — *what you ran / what you expected / what actually happened / a fix idea* — then propose a titled issue and file it with `gh issue create` **once I give the go-ahead, not silently.**
- **In an autonomous rauf iteration:** don't open issues mid-loop. Note the friction in `progress.md` for me to triage later.
