# forge-bootstrap — Charter

> Pre-PRD brief. Input to `forge-1-prd forge-bootstrap`. Describes *what*
> forge-bootstrap is and the scope it owns — deliberately light on *how*, which
> the pipeline (PRD → tech → specs) will decide.

## One-liner

`forge-bootstrap` stands up a brand-new, empty repo to the point where
`forge-1-prd <feature>` or `forge-0-epic <epic>` is the next logical step.

## Problem

The forge pipeline assumes an **existing** codebase. Stage 2 (`forge-2-tech`)
explicitly grounds every design choice "in real codebase patterns"; the stack
profile in `forge.config.json` tailors specs, checks, and acceptance criteria to
an established toolchain; backlog items carry a verification command that
presumes something runnable already exists.

Point any of that at an empty directory and there is nothing to grab onto: no
structure, no toolchain, no conventions, no `forge.config.json`, nothing for an
acceptance-criteria verification command to run. Today you hand-scaffold or
improvise a baseline before the pipeline is usable. `forge-bootstrap` fills that
**pre-pipeline gap** — and only that gap.

## Scope

### In scope — Mode A (default): scaffold to pipeline-ready

From an empty (or near-empty) repo, produce a runnable project baseline plus
forge configuration so the pipeline can run against it:

- **Project identity** — name, one-line purpose, target language/stack.
- **Structure + toolchain** — directory layout and config for the chosen stack
  profile: package manager, linter, formatter, test runner.
- **A minimal runnable skeleton** — a "hello world" entrypoint and at least one
  **passing** test, so a backlog item's verification command has something real
  to execute from item #1.
- **CI stub** — a lint + test workflow.
- **Repo hygiene** — `.gitignore`, `LICENSE`, a `README` stub, and the
  agent-instruction file(s) the host expects (`AGENTS.md` / `CLAUDE.md`).
- **Forge config** — run / subsume `forge-init` to write `forge.config.json`
  with the resolved stack profile and `loopRunner` block.
- **Clean committed baseline** — leave the repo green and committed.

### In scope — Mode B (on request): scaffold, then first MVP

Everything in A, then **hand off into the normal pipeline** to produce a first
working MVP (PRD → … → run the loop once on the core product). Mode B does not
reimplement any pipeline stage — it is "A, then drive the existing stages." It is
opt-in, never the default.

### Out of scope / non-goals

- **Does not overlap or replace** `forge-1-prd`, `forge-2-tech`,
  `forge-3-specs`, `forge-4-backlog`, or `forge-5-loop`. It authors no product
  requirements, design, specs, or backlog of its own.
- **Not a numbered pipeline stage.** No `REQ-XXX-NN` traceability spine. It is an
  unnumbered pre-pipeline bootstrap, a sibling of `forge-init` / `forge-fix` /
  `forge-verify`.
- **Invents no product features** beyond the trivial runnable skeleton needed to
  make the toolchain and verification path real.

## Relationship to existing commands

- **`forge-init`** writes `forge.config.json` into an *existing* repo.
  `forge-bootstrap` stands up the *whole* repo and calls / subsumes `forge-init`
  as one step. After bootstrap, forge-init has effectively already run.
- **Hand-off** — the terminal state is "ready for the pipeline." The skill should
  end by telling the user the next step is `forge-1-prd <feature>` (or
  `forge-0-epic <epic>` for a large change).
- **Additive** — when `forge-bootstrap` is not used, every existing forge-*
  command behaves byte-for-byte as it does today.

## Interaction model

A short interview, one question at a time (host-adapted `AskUserQuestion` with
the documented conversational fallback): project name + purpose, language/stack
(offer the existing built-in profiles — TypeScript, Python, Go, Rust, generic),
package manager, license, CI yes/no, and Mode-B (MVP-now) yes/no.

**Stack-aware:** reuse the same stack profiles the rest of the pipeline keys off,
so the scaffold's toolchain and the verification command the pipeline later
generates agree by construction.

**Agent-agnostic:** works on any supported host (Claude, Codex, …) like the rest
of the pipeline.

## Success criteria

- Empty repo → after `forge-bootstrap`: structure, toolchain, **passing** lint +
  test, `forge.config.json`, and a clean committed baseline all present.
- Running `forge-1-prd <feature>` immediately afterward works with no extra setup
  (config present, stack resolved, a verification command that runs).
- Zero behavior change to any existing forge-* command when bootstrap is unused.

## Open questions (for `forge-1-prd` to resolve)

- Does it run `git init` itself, or assume the repo already exists?
- How much skeleton is "right" per stack — a passing test only, or also a
  runnable entrypoint?
- Behavior on a **non-empty** repo: refuse, detect-and-bail, or offer to proceed?
- Commit granularity: a single bootstrap commit vs. staged commits. (Note: the
  CLAUDE.md "loop runner owns the commit" rule applies to *loop iterations*;
  bootstrap is an interactive setup step, so it may commit directly.)
- Reuse `forge-init`'s config writer directly vs. share a common helper.
