# Agent Instructions — {{PROJECT_NAME}}

## Project Purpose

{{PURPOSE}}

## Getting Started

This project was scaffolded by forge-bootstrap. To continue development:

1. Review `forge.config.json` for the project configuration.
2. Run the forge pipeline (forge-1-prd → forge-0-epic → forge-3-specs → forge-4-backlog) to plan and implement features.
3. Use `forge-5-loop` to drive autonomous implementation.

## Conventions

- Follow the patterns established in the existing codebase.
- Keep `forge.config.json` up to date with any changes to stack or commands.

## Specs are pre-implementation

- Documents under `specs/` (PRDs, tech specs, numbered implementation specs) establish the backlog. They are **not** kept in sync with the code as it evolves.
- Do not flag or "fix" divergence between a finalized spec and the implementation — code is the source of truth for behavior.
- It's fine for `specs/` artifacts and `backlog.json` to reference specs for provenance, but implementation artifacts (source code, generated skills/agents, configs, docs) must not reference spec files, which may be archived or deleted after a feature ships.

## Tooling feedback (feature-forge / rauf)

This project is driven by the feature-forge pipeline and the rauf loop. Help improve those tools by capturing friction as you hit it — papercuts included, not just outright bugs.

- **When to flag:** any forge/rauf command, skill, agent, or prompt that is confusing, buggy, missing a capability, forces a workaround, or produces a surprising result.
- **Where to file** — route by which tool the friction is with:
  - feature-forge (pipeline stages, forge skills/agents): https://github.com/garygentry/feature-forge/issues
  - rauf (the autonomous loop runner, `rauf` CLI): https://github.com/garygentry/rauf/issues
- **How:** capture it while fresh — *what you ran / what you expected / what actually happened / a fix idea* — then propose a titled issue and file it with `gh issue create` **on the human's go-ahead, not silently.**
- **In an autonomous rauf iteration:** do **not** open issues mid-loop. Note the friction in `progress.md` for the human to triage later.
