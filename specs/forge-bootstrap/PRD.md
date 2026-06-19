# forge-bootstrap — Product Requirements Document

> Source brief: [`.reference/CHARTER.md`](.reference/CHARTER.md). This PRD captures
> **what** forge-bootstrap must do; technology choices are deferred to the tech spec.

## 1. Problem Statement

The forge pipeline assumes an **existing** codebase. Stage 2 (`forge-2-tech`)
grounds design choices "in real codebase patterns," the stack profile in
`forge.config.json` tailors specs and checks to an established toolchain, and
backlog items carry verification commands that presume something runnable already
exists. Point any of that at an empty directory and there is nothing to grab onto:
no structure, no toolchain, no conventions, no `forge.config.json`, and nothing
for an acceptance-criteria verification command to run.

Today a user must hand-scaffold a baseline before the pipeline is usable.
`forge-bootstrap` fills that **pre-pipeline gap** — and only that gap — taking a
brand-new empty repo to the point where `forge-1-prd <feature>` or
`forge-0-epic <epic>` is the next logical step. It is an unnumbered bootstrap
skill (a sibling of `forge-init` / `forge-fix` / `forge-verify`), not a numbered
pipeline stage, and it is purely additive: existing flows are unchanged.

## 2. User Stories

- As a **developer starting a new project**, I want to scaffold a runnable,
  pipeline-ready repo so I can immediately use forge to build features.
- As a **forge user**, I want bootstrap to create `forge.config.json` and a green
  (lint + test passing) baseline so the first backlog item's verification command
  works out of the box.
- As a **developer with a large initial product idea**, I want to optionally chain
  straight into the pipeline (single feature or epic) right after scaffolding.
- As a **user on a machine missing a toolchain**, I want bootstrap to warn me
  rather than silently produce an unverifiable repo.
- As a **user who points bootstrap at the wrong (non-empty) repo**, I want it to
  refuse without touching my files and tell me what to use instead.
- As a **feature-forge maintainer**, I want bootstrap to be purely additive so all
  existing single-feature and epic flows behave byte-for-byte as before.
- As a **non-Claude agent user** (Codex, etc.), I want bootstrap to work on my host
  like the rest of the pipeline.

## 3. Functional Requirements

### 3.1 Greenfield Gate & Repository Initialization

- **REQ-GATE-01**: Bootstrap MUST refuse to run if the target repo contains
  anything beyond an allowed set of repo-meta files. Allowed: `.git/`, a README
  file, a `LICENSE` file, `.gitignore`, and the forge specs directory. Any source
  file, package manifest, or build/tooling config disqualifies the repo.
  - Priority: P0
- **REQ-GATE-02**: On refusal, the message MUST name the disqualifying path(s) and
  direct the user to the correct alternative (`forge-init`, then `forge-1-prd`).
  - Priority: P0
- **REQ-GATE-03**: If no git repository exists in the target directory, bootstrap
  MUST initialize one before scaffolding.
  - Priority: P0
- **REQ-GATE-04**: The allowed-meta set MUST treat a freshly created remote repo
  (auto-generated README + LICENSE) as eligible to proceed.
  - Priority: P1
- **REQ-GATE-05**: Bootstrap MUST NOT modify or delete any pre-existing file; if it
  cannot proceed without doing so, it refuses (see REQ-GATE-01).
  - Priority: P0

### 3.2 Interview Inputs

- **REQ-INPUT-01**: Collect the project name, defaulting to a value inferred from
  the target directory, with user confirmation.
  - Priority: P0
- **REQ-INPUT-02**: Collect a one-line project purpose (used to seed README and
  config metadata).
  - Priority: P0
- **REQ-INPUT-03**: Collect the language/stack from the built-in profiles
  (TypeScript, Python, Go, Rust, generic). Required — it drives all downstream
  scaffolding.
  - Priority: P0
- **REQ-INPUT-04**: Collect the package manager **only when** the chosen stack has a
  meaningful choice; otherwise skip the question.
  - Priority: P1
- **REQ-INPUT-05**: Collect a license selection (including a "none" option), with
  sensible defaults offered.
  - Priority: P1
- **REQ-INPUT-06**: Ask whether to scaffold a single package or a monorepo.
  - Priority: P0
- **REQ-INPUT-07**: In Mode B only, ask whether the first build is a single feature
  or an epic.
  - Priority: P1
- **REQ-INPUT-08**: All questions MUST use host-adapted structured input with the
  documented conversational fallback (agent-agnostic).
  - Priority: P0

### 3.3 Mode A — Scaffold to Pipeline-Ready (default)

- **REQ-SCAF-01**: Produce a directory structure appropriate to the chosen stack
  profile.
  - Priority: P0
- **REQ-SCAF-02**: Produce toolchain configuration: a package/dependency manifest,
  linter, formatter, and test runner for the chosen stack.
  - Priority: P0
- **REQ-SCAF-03**: Produce a minimal **runnable** entrypoint.
  - Priority: P0
- **REQ-SCAF-04**: Produce at least one **passing** test.
  - Priority: P0
- **REQ-SCAF-05**: After scaffolding, the stack's lint command and test command MUST
  both succeed (a "green baseline") whenever the toolchain is available.
  - Priority: P0
- **REQ-SCAF-06**: Produce repo-hygiene files: a stack-appropriate `.gitignore`, a
  README stub seeded with the name and purpose, a `LICENSE` per the user's
  selection, and the host agent-instruction file(s) (`AGENTS.md` / `CLAUDE.md` as
  applicable to the host).
  - Priority: P1
- **REQ-SCAF-09**: When an allowed-meta file (§3.1) already exists — e.g. a README
  or `LICENSE` from a freshly created remote repo — bootstrap MUST NOT overwrite it
  (per REQ-GATE-05). It skips generating that file, seeds the relevant interview
  default from the existing one where sensible (e.g. detecting the existing license),
  and notes the kept file in the completion summary (REQ-OUT-01).
  - Priority: P1
- **REQ-SCAF-07**: Optionally produce a CI workflow that runs lint + test. CI is
  skippable; the specific provider is decided in the tech spec (provider-agnostic
  requirement — see Constraints).
  - Priority: P1
- **REQ-SCAF-08**: On completion, bootstrap MUST leave no untracked or dangling
  scaffold files — every produced file is either committed or staged per the
  run-time commit choice (REQ-LIFE-05); nothing is left untracked.
  - Priority: P0

### 3.4 Stack Profiles

- **REQ-STACK-01**: Support TypeScript, Python, Go, Rust, and a generic fallback —
  parity with the stack profiles the rest of forge advertises.
  - Priority: P0
- **REQ-STACK-02**: The scaffold's verification command(s) MUST match what the
  pipeline's stack profile expects, so downstream acceptance-criteria verification
  commands run against this baseline without adjustment.
  - Priority: P0
- **REQ-STACK-03**: The generic fallback MUST produce a language-neutral structure
  with a real (non-fake) lint/test step that passes, so the baseline is still green.
  - Priority: P1

### 3.5 Monorepo Support

- **REQ-MONO-01**: When monorepo is chosen, interview for the initial member
  packages (count and names) and scaffold a workspace root plus each member.
  - Priority: P1
- **REQ-MONO-02**: Members MAY each use a different stack profile (mixed-language
  workspace).
  - Priority: P1
- **REQ-MONO-03**: Each member gets its own runnable entrypoint and at least one
  passing test; the aggregate workspace lint + test MUST be green.
  - Priority: P1
- **REQ-MONO-04**: When CI is enabled for a monorepo, it MUST run lint + test for all
  members.
  - Priority: P1
- **REQ-MONO-05**: The forge configuration MUST represent the workspace such that the
  pipeline can target an individual member with the correct stack and verification
  command. (Representation mechanism is an Open Question — §7.)
  - Priority: P1

### 3.6 Mode B — Optional Pipeline Hand-off

- **REQ-MODEB-01**: Mode B is opt-in; the default behavior is Mode A only.
  - Priority: P1
- **REQ-MODEB-02**: In Mode B, after a successful green baseline, bootstrap asks
  feature-vs-epic (REQ-INPUT-07) and auto-launches the corresponding stage
  (`forge-1-prd` or `forge-0-epic`).
  - Priority: P1
- **REQ-MODEB-03**: Subsequent pipeline stages remain normal, user-driven steps;
  Mode B MUST NOT run stages unattended.
  - Priority: P1
- **REQ-MODEB-04**: Mode B MUST NOT launch the next stage if the baseline is not
  verified green, unless the user explicitly overrides.
  - Priority: P1

### 3.7 forge-init Integration & Configuration

- **REQ-CFG-01**: Bootstrap MUST produce a valid `forge.config.json` containing the
  resolved stack profile and a `loopRunner` block (defaulting to rauf).
  - Priority: P0
- **REQ-CFG-02**: The configuration produced MUST be equivalent to what `forge-init`
  would write — bootstrap subsumes/reuses `forge-init`'s config behavior rather than
  diverging from it.
  - Priority: P0
- **REQ-CFG-03**: After bootstrap completes, running `forge-init` MUST be
  unnecessary (a valid config is already present).
  - Priority: P0

### 3.8 Lifecycle: Resume, Toolchain, Commit

- **REQ-LIFE-01**: Bootstrap MUST record an in-progress marker so a re-run can
  recognize its own incomplete scaffold.
  - Priority: P0
- **REQ-LIFE-02**: On re-run over its own partial scaffold, bootstrap MUST offer
  resume / clean-restart / cancel, and MUST NOT misfire the greenfield refusal
  (REQ-GATE-01) against its own in-progress artifacts.
  - Priority: P0
- **REQ-LIFE-03**: Before relying on lint/test, bootstrap MUST detect whether the
  chosen stack's toolchain is installed; if missing, warn and ask whether to
  scaffold anyway (unverified) or abort.
  - Priority: P0
- **REQ-LIFE-04**: If scaffolded without verification (toolchain missing), the
  completion output MUST clearly mark the baseline as unverified.
  - Priority: P1
- **REQ-LIFE-05**: The commit style MUST be chosen at run time: a single baseline
  commit, or leave the scaffold staged with no commit.
  - Priority: P0
- **REQ-LIFE-06**: When committing, bootstrap MUST use a single baseline commit
  containing the whole scaffold plus `forge.config.json`.
  - Priority: P1

### 3.9 Completion Output

- **REQ-OUT-01**: On success, print a summary of what was created, the resolved
  stack(s), the verification result (green or unverified), and the exact next
  command (`forge-1-prd <feature>` or `forge-0-epic <epic>`).
  - Priority: P0
- **REQ-OUT-02**: In Mode B, bootstrap launches the next stage instead of printing
  its command.
  - Priority: P1

## 4. Non-Functional Requirements

### 4.1 Performance
- **REQ-PERF-01**: No numeric performance target applies. Bootstrap's own work
  (interview, file generation, config write) is negligible; runtime is dominated by
  the external stack toolchain's single lint/test verification pass, whose duration
  is the toolchain's responsibility, not bootstrap's. This non-quantification is
  deliberate for a one-shot interactive setup tool.
  - Priority: P2

### 4.2 Security / Safety
- **REQ-SEC-01**: Bootstrap MUST never modify or delete pre-existing user files; the
  greenfield gate (§3.1) enforces this.
  - Priority: P0
- **REQ-SEC-02**: Git initialization and commits MUST follow the shared Git Commit
  Protocol — use the project's git identity, stage specific paths, and never use
  `git add -A`, `--force`, or `--no-verify`.
  - Priority: P1

### 4.3 Observability
- **REQ-OBS-01**: All terminal outcomes — success, greenfield refusal, missing
  toolchain, and partial-state detection — MUST be explicit and actionable in the
  output (the success path is satisfied by REQ-OUT-01).
  - Priority: P1

### 4.4 Accessibility
- Not applicable: forge-bootstrap is an agent/CLI tool with no graphical interface.
  User interaction inherits the host's accessibility characteristics.

### 4.5 Portability (Agent-Agnostic)
- **REQ-PORT-01**: Bootstrap MUST work on any supported host (Claude, Codex, …)
  using host-adapted input with a conversational fallback.
  - Priority: P0
- **REQ-PORT-02**: Bootstrap MUST resolve its own scripts/resources via the shared
  portable-root pattern, with no reliance on a mechanism that breaks on non-Claude
  hosts.
  - Priority: P0

## 5. Constraints

These are mandated by existing infrastructure or organizational decisions:

- **Packaging**: Must ship as an **unnumbered** forge skill (sibling of
  `forge-init` / `forge-fix` / `forge-verify`), not a numbered pipeline stage; it
  has no `REQ-XXX-NN` traceability spine of its own within the pipeline.
- **Reuse existing forge machinery**: the built-in stack profiles, the
  `forge.config.json` schema, the `loopRunner` block, and `forge-init`'s config
  behavior must be reused, not reimplemented divergently.
- **Shared conventions**: must follow `references/shared-conventions.md` — the
  structured-input protocol, the Git Commit Protocol, and the portable-root pattern.
- **Default loop runner**: `forge.config.json` defaults its `loopRunner` to rauf.
- **CI provider**: GitHub Actions is the likely CI target but is **not mandated** —
  the requirement is "a CI workflow that runs lint + test"; the provider is an
  implementation choice (constraint, not requirement).

## 6. Out of Scope

This version of forge-bootstrap will NOT:

- Operate on a **non-empty** repo / import or migrate an existing project (refused
  per §3.1).
- Run pipeline stages **unattended** (Mode B only auto-launches the next stage).
- Generate `.env` / secrets-management scaffolding (considered and deferred).
- Provision deployment, hosting, or cloud infrastructure.
- Configure more than one CI provider, or non-CI automation.
- Update or migrate the `forge.config.json` of an **existing** repo (that remains
  `forge-init`'s job).

## 7. Open Questions

Items to resolve in the tech spec / during implementation:

- **OQ-01**: How does `forge.config.json` represent a **mixed-language monorepo** so
  the pipeline can target a member with the correct stack profile and verification
  command? (Per-member stack mapping vs. per-member config vs. an extension to the
  config schema — REQ-MONO-05.)
- **OQ-02**: Exact matching rules for the allowed-meta-file set (filename globs,
  case sensitivity, README/LICENSE extension variants) — REQ-GATE-01/04.
- **OQ-03**: Storage location and format of the in-progress resume marker, and how
  "resume" reconstructs prior interview answers — REQ-LIFE-01/02.
- **OQ-04**: Whether the generic profile can guarantee a real, passing lint/test
  step without a language toolchain, and what that step is — REQ-STACK-03.
- **OQ-05**: For the Mode B epic path, how the epic name and initial decomposition
  are seeded when handing to `forge-0-epic` — REQ-MODEB-02.

## 8. Success Criteria

- **Empty repo → pipeline-ready (Mode A)**: after `forge-bootstrap`, the repo has a
  stack-appropriate structure, a configured toolchain, **passing** lint + test, a
  valid `forge.config.json`, and a clean committed (or intentionally staged)
  baseline. Running `forge-1-prd <feature>` immediately afterward works with no
  extra setup.
- **Non-empty repo**: bootstrap refuses, names the disqualifying path(s), points to
  `forge-init` + `forge-1-prd`, and touches **no** files.
- **Interrupted run**: a re-run detects bootstrap's own partial scaffold and offers
  resume / restart / cancel — it never corrupts the repo and never refuses its own
  work as if it were a foreign project.
- **Monorepo**: a workspace with the requested members is scaffolded, each member is
  green, and the pipeline can target an individual member.
- **Mode B**: after a verified green baseline, the chosen next stage
  (`forge-1-prd` or `forge-0-epic`) launches automatically.
- **Missing toolchain**: bootstrap warns and lets the user choose to scaffold
  (clearly marked unverified) or abort — it never silently claims a green baseline
  it could not verify.
- **Additivity**: with bootstrap unused, every existing forge-* command behaves
  exactly as before.
