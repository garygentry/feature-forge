# feature-forge

End-to-end feature development pipeline: PRD → tech spec → implementation specs → backlog → documentation, with verification gates, pipeline state tracking, and specialized subagents.

## Pipeline Stages

```
/forge-1-prd → /forge-2-tech → /forge-3-specs → /forge-verify → /forge-4-backlog → /forge-verify → [implement] → /forge-5-docs
```

See `references/process-overview.md` for detailed pipeline flow.

## Skills

| Skill | Purpose |
|-------|---------|
| **forge** | Pipeline navigator and status dashboard |
| **forge-1-prd** | Requirements interviewer — creates PRD.md |
| **forge-2-tech** | Tech spec driver — creates tech-spec.md |
| **forge-3-specs** | Implementation spec generator — creates numbered spec suite |
| **forge-4-backlog** | Ralph backlog generator — creates backlog.json |
| **forge-5-docs** | Architecture documentation generator |
| **forge-verify** | Verification gate — produces findings + fix execution plan |

## Agents

| Agent | Purpose | Model |
|-------|---------|-------|
| **forge-researcher** | Codebase exploration for tech-spec planning | Sonnet |
| **forge-verifier** | Read-only artifact verification with persistent memory | Opus |

## Commands

| Command | Description |
|---------|-------------|
| `/forge` | View pipeline status |
| `/forge-init` | Initialize forge.config.json |
| `/forge-1-prd` | Create requirements PRD |
| `/forge-2-tech` | Create technical specification |
| `/forge-3-specs` | Generate implementation specs |
| `/forge-4-backlog` | Generate ralph backlog |
| `/forge-5-docs` | Generate architecture docs |
| `/forge-verify` | Run verification on artifacts |
| `/forge-fix` | Apply fixes from verification report |
| `/forge-status` | Show status for all active features |

## Configuration

Create `forge.config.json` in your project root (or run `/forge-init`):

```json
{
  "specsDir": "./specs",
  "docsDir": "./docs/architecture",
  "backlogDir": null,
  "gitCommitAfterStage": true,
  "commitPrefix": "forge"
}
```

## Quick Start

1. Run `/forge-init` to create configuration
2. Run `/forge-1-prd <feature-name>` to start the pipeline
3. Run `/forge <feature-name>` at any time to check status

Use `--force` on any stage command to skip prerequisite checks.

## Notes

This plugin's reference materials (spec archetypes, backlog examples, stack discovery) are currently optimized for TypeScript monorepo projects. A stack-agnostic rewrite is planned.

## Install

```bash
/plugin install feature-forge@garygentry-agent-plugins --scope project
```
