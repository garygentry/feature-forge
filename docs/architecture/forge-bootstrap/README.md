# Forge Bootstrap

> New to the pipeline? Start with the [main README's pipeline overview](../../../README.md#the-pipeline-at-a-glance);
> bootstrap is an optional **pre-pipeline** step that runs before Stage 1.

`forge-bootstrap` takes a brand-new **empty** repository to a pipeline-ready,
green baseline — a stack-appropriate structure, a configured toolchain, a
passing lint + test, and a valid `forge.config.json` — then optionally chains
straight into the pipeline. After it runs, `/feature-forge:forge-1-prd <feature>`
(or `/feature-forge:forge-0-epic <epic>`) works with no extra setup.

The rest of the pipeline assumes an **existing** codebase: Stage 2 grounds
design in real code, the stack profile tailors specs and checks, and backlog
acceptance-criteria commands presume something runnable already exists. Point any
of that at an empty directory and there is nothing to grab onto. `forge-bootstrap`
fills that pre-pipeline gap — and only that gap. It is an **unnumbered** skill (a
sibling of `forge-init` / `forge-verify` / `forge-fix`), not a numbered stage.

Bootstrap is **purely additive**: every existing single-feature and epic flow is
unchanged. The one shared-file edit is an additive optional `workspaces[]` array
in `references/forge-config-schema.json`; every pre-existing `forge.config.json`
still validates.

## Quick Start

Run the skill against an empty repo (defaults to the current directory):

```
/feature-forge:forge-bootstrap
```

It runs a short interview (name, purpose, stack, package manager, license,
single-vs-monorepo, commit style, optional Mode B), scaffolds the baseline,
verifies it green, and commits a single baseline commit. Example result for a
Python project:

```
Bootstrap complete — pipeline-ready baseline.
  Stack:        python (uv)
  Created:      pyproject.toml, src/acme_svc/__init__.py, src/acme_svc/main.py,
                tests/test_smoke.py, .gitignore, README.md, LICENSE, AGENTS.md,
                forge.config.json
  Verification: green  (mypy . ✓   pytest ✓)
  Commit:       baseline committed (a1b2c3d)
  Next step:    /feature-forge:forge-1-prd <feature>
```

## Key Concepts

- **Greenfield gate.** Bootstrap refuses to run on a non-empty repo. Only
  repo-meta is allowed through: `.git/`, a README, a LICENSE, `.gitignore`, and
  the specs directory. Any source file, manifest, or build config disqualifies
  the repo — and the gate is read-only, so it never touches your files. (A
  non-empty repo is `forge-init`'s job, not bootstrap's.)
- **Green baseline.** The scaffold's resolved lint + test commands must both pass
  on a machine with the toolchain present. The same commands are written into
  `forge.config.json`, so the pipeline's first backlog item verifies against this
  baseline with no adjustment.
- **Stack profiles.** Five built-in profiles — `typescript`, `python`, `go`,
  `rust`, `generic` — each an editable template directory. The generic profile is
  a real, zero-dependency POSIX lint + test, so even a language-neutral project is
  genuinely green.
- **Monorepo.** A workspace of members (mixed-language allowed), represented in
  config by the additive `workspaces[]` array so the pipeline can target an
  individual member with the right stack and commands.
- **Resume sentinel.** A transient `.forge-bootstrap.json` records the in-progress
  scaffold so a re-run can resume / restart / cancel. It is removed before the
  commit stages files, so it never enters git history.
- **Hybrid split.** Conversation and decisions live in the prose skill body
  (`SKILL.md`); all deterministic mechanics live in a stdlib-only Python helper
  (`scripts/forge-bootstrap.py`). See [architecture.md](./architecture.md).

## The helper at a glance

`scripts/forge-bootstrap.py` exposes five subcommands the skill body drives over
their JSON + exit codes:

| Subcommand | Purpose |
|-----------|---------|
| `check` | Greenfield gate + resume-marker detection (read-only) |
| `scaffold` | Emit the baseline: templates, hygiene files, `forge.config.json`, optional CI |
| `verify` | Probe the toolchain, run resolved lint + test per member |
| `commit` | Stage the exact written file list, single baseline commit (or stage-only) |
| `status` | Inspect the resume sentinel |

Full signatures, flags, JSON shapes, and exit codes: [cli-reference.md](./cli-reference.md).

## Configuration produced

Bootstrap writes a `forge.config.json` equivalent to what `forge-init` would
write (same field set + defaults), plus an explicit `loopRunner` block (defaulting
to rauf). After bootstrap, running `forge-init` is unnecessary. For a monorepo the
three top-level scalars (`stack`/`typeCheckCommand`/`testCommand`) are `null` and
`workspaces[]` carries the per-member resolution.

## When to use

- Starting a **brand-new, empty** project you intend to build with forge.
- You want a runnable green baseline + valid config in one step, optionally
  chaining straight into Stage 1 / Stage 0.

## When NOT to use

- The repo already has source/manifests/build config → use `/feature-forge:forge-init`,
  then `/feature-forge:forge-1-prd`. (Bootstrap will refuse and tell you this.)
- You only need to (re)write `forge.config.json` on an existing project → that is
  `forge-init`.
- You want to import or migrate an existing codebase, provision deployment/secrets,
  or run pipeline stages unattended — all out of scope.

## Further Reading

- [Architecture](./architecture.md) — the hybrid split, the lifecycle flow, the sentinel, templates, and design decisions
- [CLI Reference](./cli-reference.md) — `scripts/forge-bootstrap.py` subcommands, flags, JSON, exit codes
- [Integration Guide](./guides/integration.md) — where bootstrap sits in the pipeline, adding a stack/license, host adaptation, Mode B
