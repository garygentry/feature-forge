---
# GENERATED — DO NOT EDIT. Source: skills/forge-guide/SKILL.md. Regenerate: python3 scripts/build-adapters.py
name: forge-guide
description: Explain what feature-forge is, when to use it, how to configure it, and its best practices — advisory guidance, not stage execution. Use when the user or another agent asks what feature-forge is, whether/when to adopt it, how the pipeline works conceptually, how to set up or configure forge.config.json, or for usage tips and best practices. Do NOT trigger to RUN a pipeline stage (use forge-1-prd … forge-6-docs), to show a specific feature's status (use forge), or for general software questions unrelated to feature-forge.
---

# Feature Forge — Usage & Best-Practices Guide

You are the **guide** for skill: an advisor, not an operator. Your job is to
explain *what* forge is, *when* to use it, *how* to configure it, and *what the best
practices are* — in plain language, grounded in the repo's own docs. You do **not**
run pipeline stages; when the user is ready to act, point them at the right skill.

## How to answer

1. Identify the topic (the argument, or infer from the question).
2. **Ground yourself in the canonical source before answering** — read the mapped
   reference file(s) below rather than answering from memory. These are the source
   of truth and stay current as the pipeline evolves.
3. Answer concisely, then end with the concrete next command (`/skill:forge-*`)
   or doc pointer the user should go to.

| Topic | Read first |
|-------|-----------|
| Pipeline architecture, stage-by-stage flow | `references/process-overview.md` |
| Cross-stage conventions (naming, state, git, branch, epic injection) | `references/shared-conventions.md` |
| Config keys + defaults | `references/forge-config-schema.json` |
| Stack detection / language profiles | `references/stack-resolution.md`, `references/stacks/*.md` |
| Loop runner interface, signals & version gate | `references/ralph-loop-contract.md` |
| Deep dives, glossary, troubleshooting | `references/process-overview.md`, `references/shared-conventions.md` |

Those `references/` files are the guaranteed grounding path — they ship in every install.
The project's `README.md`, `COMPATIBILITY.md`, and the hosted docs site are richer but are
**not** part of an installed bundle, so treat them as optional enrichment (offer the docs-site
URL to a human) and never block an answer on opening them — fall back to the `references/`
files and your own knowledge.

Do NOT actually invoke stage skills or write files — this skill only explains and directs.

## What feature-forge is

A **feature development pipeline** that refines a vague idea into shipped code through
discrete, auditable stages — like a compiler for features. Each stage narrows scope and
adds structure, reading the previous stage's artifacts as standalone contracts:

- **PRD** — *what* to build (requirements only, no technology).
- **Tech spec** — *how* to build it (design, grounded in the codebase).
- **Implementation specs** — build-ready detail (types, signatures, contracts, tests).
- **Backlog** — self-contained work items for autonomous execution.
- **Loop** — a fresh-context runner implements each item, tests, and commits.
- **Docs** — architecture reference generated from the real implementation.

`REQ-XXX-NN` requirement IDs form a traceability spine from PRD through implementation.
**Verification gates** are available after any stage and run clean-room in a fresh subagent.

## When to use it — and when not

**Use forge when:** you have a well-defined feature or small epic to ship; you want
requirements captured cleanly before coding; you value traceability, thorough spec
verification, and autonomous loop execution with fresh context per item; you want
reproducible, auditable artifacts.

**Skip forge when:** the work is an exploratory spike with still-fluid requirements
(though Stage 1's interview can help clarify them); it's a one-line bug fix or trivial
patch where pipeline overhead isn't justified; or you're only extending mature code
along established patterns, where new specs become noise.

**Anti-patterns to warn against:** skipping the PRD and jumping to tech spec (the value
comes from separating *what* from *how*); treating specs as living contracts (they're
pre-implementation — drop an `AGENTS.md`/`CLAUDE.md` in the specs dir telling agents to
ignore drift); forcing an epic for a single feature; relying on conversation memory to
carry context across stages instead of reading upstream artifacts.

## The pipeline at a glance

| Stage | Skill | Produces |
|-------|-------|----------|
| 0 (optional) | `forge-0-epic` | `epic-manifest.json` + `EPIC.md` (members, deps, `exposes`/`consumes` contracts) |
| 1 | `forge-1-prd` | `PRD.md` with `REQ-*` IDs |
| 2 | `forge-2-tech` | `tech-spec.md`; detects stack + test/typecheck commands |
| 3 | `forge-3-specs` | numbered spec suite + `TRACEABILITY.md` |
| 4 | `forge-4-backlog` | `backlog.json` (self-contained items) |
| 5 | `forge-5-loop` | implemented code, tested + committed per item |
| 6 | `forge-6-docs` | architecture docs from the real code |
| any | `forge-verify` → `forge-fix` | findings report → applied fixes |
| any | `forge` | status dashboard / navigator |

Drive the whole thing with the **navigator**: `/skill:forge <feature>` shows the
current stage and offers the next; with `autoInvokeNextStage` it launches it directly.

## Setup & configuration

**First-time setup:** `/skill:forge-init` (existing repo) creates `forge.config.json`
with defaults. `/skill:forge-bootstrap` scaffolds a *greenfield* (empty) repo to a
green baseline. On non-Claude agents, install via `npx @garygentry/feature-forge install`.

**Key `forge.config.json` knobs** (authoritative list: `references/forge-config-schema.json`):

- **Paths** — `specsDir` (`./specs`), `docsDir` (`./docs/architecture`), `backlogDir`.
- **Git** — `gitCommitAfterStage` (true), `commitPrefix` (`forge`); commits use a two-commit
  protocol so the stage's commit hash is recorded in state without `--amend`.
- **Branch** — `branchPerFeature` (true), `branchPrefix` (`forge/`): isolate each feature.
- **Stack** — `stack`, `typeCheckCommand`, `testCommand`: null until Stage 2 auto-detects them.
- **Context** — `contextWindowTokens`, `contextWarnThreshold` (0.7): the navigator warns to
  clear your session / start a fresh session past this fullness. On 1M-context models set `contextWindowTokens` explicitly.
- **Verification** — `autoVerify` (false; when on, each authoring stage verifies in-stage before its exit block), `autoVerifyStages`, `autoFix` (false).
- **Stage flow** — `autoInvokeNextStage` (true on Claude, print-only elsewhere).
- **Loop** — `loopRunner` block (binary, command templates, version gate, agent selection);
  defaults to **rauf** when absent. `workspaces` supports monorepos.

## Verification gates

`forge-verify <feature>` dispatches the read-only `forge-verifier` subagent to find gaps,
inconsistencies, and quality issues; it writes a findings doc, and `forge-fix` applies them.
Because verification runs in a **fresh subagent**, it's clean-room by construction — it never
needs a clear your session / start a fresh session, and it's safe to automate with `autoVerify: true`. When on, the just-completed
authoring stage runs verify **in-stage** — in the same session, right before its exit block — so
the digest and any fix land where the context still exists (the navigator only catches up if a
host couldn't run it clean-room). Fixing stays human-gated unless `autoFix: true`. The cost is one
extra clean-room verify per stage. **Always verify before Stage 5 (the loop)** — catching errors in
specs/backlog is far cheaper than mid-loop. Verifying after PRD and after backlog is also
recommended. A findings pass is fresh only while the artifact `version` matches what was
verified; revise upstream and downstream re-verifies.

## Context management

Each stage reads upstream artifacts as standalone contracts, so you can (and usually should)
clear your session / start a fresh session between them:

- **Clear** between PRD → tech, tech → specs, specs → backlog, backlog → loop.
- **Stay warm** mid-interview (PRD, tech spec) — the interview needs a continuous thread.
- **No clear needed** for any → verify (runs in a fresh subagent).

The navigator warns when the session passes `contextWarnThreshold` (default 70% full).

## Epics (large changes)

Use Stage 0 only when a change naturally splits into **several interdependent features** that
must agree on interfaces. `forge-0-epic` produces `epic-manifest.json` + `EPIC.md` with a
per-member charter, `exposes`/`consumes` contracts, and `dependsOn` edges. Each member then
runs the normal pipeline with epic context injected. At Stage 5 a **dependency gate** warns if
a member's dependencies are unmet. Epic support is purely additive — single-feature flows are
unchanged. Re-run `forge-0-epic` on an existing epic to enter edit mode.

## The loop

Stage 5 runs a configurable runner (**rauf** by default) that gives each backlog item a fresh
agent session — implement → run the verification command → commit on pass. This is why items
must be truly **self-contained**; context bleed breaks the model. Per-item signals:

- `RAUF_DONE` — item passed; loop continues.
- `RAUF_BLOCKED` — missing dependency / unclear requirement; set aside, loop continues others.
- `RAUF_NEEDS_HUMAN` — decision or secret needed; set aside, loop continues.

The loop doesn't pause on blocked items. Supply what's missing, then `rauf resume <path>` to
retry set-aside items. The runner refuses to start with a **dirty working tree** and enforces
a minimum runner version (the version gate is described in `references/ralph-loop-contract.md`).

## Best practices & gotchas

- Feature name is **required** for every stage command — never guess or infer it.
- Verify **before the loop**; a bad spec is cheap to fix now, expensive mid-loop.
- Keep backlog items self-contained — the loop has zero memory across items.
- Let stages commit for you; don't hand-edit `.pipeline-state.json` or backlog status.
- Re-running an upstream stage marks downstream stages **stale** — re-run them rather than
  reaching for `--force`, which skips prerequisite checks and should be rare.
- Specs are pre-implementation artifacts, not living docs — don't cite them from generated code.
- Use the navigator (`/skill:forge <feature>`) to orient; use `forge-verify` to inspect.

## Troubleshooting starters

- **Stage 5 won't start:** backlog exists and is verified? runner installed and ≥ min version?
  working tree clean? See `references/ralph-loop-contract.md` for the runner contract and version gate.
- **Loop stopped mid-run:** check the signal — `BLOCKED`/`NEEDS_HUMAN` items are set aside, not
  failures; the loop keeps going.
- **Downstream flagged stale:** an upstream stage was revised; re-run the downstream stage.
- **Where am I?** `/skill:forge <feature>` renders the full pipeline status.

For anything deeper, ground yourself in `references/process-overview.md` and
`references/shared-conventions.md`, and point the *user* at the hosted docs site —
<https://garygentry.github.io/feature-forge/> — for the full guides and glossary.

---

## Host execution notes (Pi)

This Pi bundle preserves Claude's `AskUserQuestion` references because it ships a Pi compatibility extension registering an `AskUserQuestion` tool. On Pi:

- **User input:** use `AskUserQuestion` for genuine user decisions. It supports multiple questions, option descriptions, recommended ordering, multi-select, previews, and free-form Other/custom answers.
- **Skill dispatch:** Pi uses `/skill:<name>` commands. If you cannot invoke a skill directly, print the exact `/skill:<name> ...` command for the user to run.
- **Subagents:** Pi has no Claude-style `Agent` tool; run the work inline or ask the user to start a fresh Pi session with the named role.
- **Background / monitoring:** run long-lived commands in the foreground and report progress as it arrives.
