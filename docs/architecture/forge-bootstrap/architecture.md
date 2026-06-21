---
title: "Forge Bootstrap — Architecture"
---

# Forge Bootstrap — Architecture

How `forge-bootstrap` is built and why. For the command surface see
[cli-reference.md](./cli-reference.md); for usage see the [README](https://github.com/garygentry/feature-forge/blob/main/docs/architecture/forge-bootstrap/README.md).

## The hybrid split (skill + helper)

Bootstrap is split into two halves with a hard boundary:

- **`skills/forge-bootstrap/SKILL.md`** — the prose skill body. Owns *conversation
  and decisions only*: the interview question set, the conversational fallback for
  non-`AskUserQuestion` hosts, the Mode A / Mode B flow, the completion summary,
  and the four terminal-outcome branches. It drives control flow off the helper's
  exit codes + JSON and never inlines file generation, template contents, the
  config field set, or the greenfield allow-list.
- **`scripts/forge-bootstrap.py`** — a stdlib-only Python helper (structured like
  `scripts/epic-manifest.py`: module docstring + exit-code contract, constants,
  TypedDict structures, flat functions over a small I/O layer, an `argparse`
  `main()`). Owns *all deterministic mechanics*: the gate, git init, template
  composition, config write, the sentinel, toolchain probing, lint/test, and the
  commit.

**Why split this way.** `SKILL.md` is under a hard `validate.sh` spec-purity gate
(body ≤ 300 lines and ≤ 5000 words, enforced by `scripts/check-spec-purity.py`).
Keeping the body lean is a *correctness* requirement, not style — a body over
budget fails CI. Pushing every mechanic into the helper keeps the body inside the
budget and makes the deterministic behavior unit-testable in Python
(`tests/test_forge_bootstrap.py`) instead of trapped in prose.

## The lifecycle flow

The skill body runs Mode A as a fixed sequence of helper subcommands, branching on
their exit codes (`0` ok, `1` actionable findings, `2` usage/IO **or** verify
toolchain-missing):

```
1. check    → greenfield gate + recovery detection
     ├─ eligible:false        → greenfield refusal (name disqualifying[]; point to
     │                          forge-init + forge-1-prd; touch nothing) — STOP
     └─ resumeMarker != null  → resume / restart / cancel
2. interview (skill body)  → assemble the Answers payload
3. scaffold → git init if absent; compose each member's templates; emit hygiene
              files (README/LICENSE/AGENTS.md/CLAUDE.md); write forge.config.json;
              optional CI; record every written path in the sentinel
4. verify   → probe toolchain; run resolved lint + test per member
     ├─ toolchainPresent:false (exit 2) → scaffold-anyway-unverified vs abort
     ├─ green:false (exit 1)            → surface failing commands; fix/abort
     └─ green:true (exit 0)             → proceed
5. commit   → remove sentinel; stage the exact written list; single baseline commit
              (or stage-only); return CommitResult
6. completion summary  /  Mode B hand-off
```

The body never re-derives the gate or re-runs lint/test itself — the helper's
structured results are authoritative.

### The four terminal outcomes

Every run ends in exactly one explicit, actionable outcome (REQ-OBS-01):

| Outcome | Source | Body action |
|---------|--------|-------------|
| **Success** | `commit` exit 0 + `green` (or unverified-but-proceeded) | completion summary, or Mode B launch |
| **Greenfield refusal** | `check` `eligible:false` + `disqualifying[]` | name the paths; point to `forge-init` + `forge-1-prd`; touch nothing |
| **Missing toolchain** | `verify` `toolchainPresent:false` (exit 2) | scaffold-anyway-unverified vs abort; mark **unverified** |
| **Partial-state** | `check` `resumeMarker != null` | resume / restart / cancel |

## The resume sentinel

`.forge-bootstrap.json` is a transient marker written **first**, before any
scaffold file, so a crash at any later point leaves a recoverable partial scaffold.
It mirrors the resolved `Answers` (for re-use on resume) and carries a running
`artifactsWritten[]` list — the **idempotency key**: every write goes through one
no-overwrite primitive (`_write_artifact`) that skips a path already recorded,
making a resumed `scaffold` idempotent. A pre-existing allowed-meta file
(README/LICENSE) is kept, never overwritten, and not recorded.

Ordering is load-bearing in `commit`: the sentinel is **removed before** `git add`,
so it can never enter history. A per-stack `.gitignore` lists it as belt-and-
suspenders. **Restart** cleanup (discard a partial) is a skill-orchestration step —
the helper exposes no clean subcommand; the body deletes the recorded tree +
sentinel and re-runs `scaffold`.

## Templates and token substitution

Editable assets live under `skills/forge-bootstrap/references/templates/`:

- **Five per-stack directories** (`typescript/`, `python/`, `go/`, `rust/`,
  `generic/`) composed per member.
- **Repo-level assets** composed once: `ci/github-actions.yml`, `hygiene/`
  (`README.md`, `AGENTS.md`, `CLAUDE.md`), and `licenses/` (`MIT/`, `Apache-2.0/`).

`compose_member` resolves the template root from `__file__`
(`<repo-root>/skills/forge-bootstrap/references/templates/<stack>`, since the helper
lives at `scripts/forge-bootstrap.py`) and copies each file with **simple string
substitution** — not a templating engine. Tokens: `{{PROJECT_NAME}}`, `{{PKG}}`
(sanitized package id), `{{PM}}`, `{{PURPOSE}}`, plus `{{AUTHOR}}`/`{{YEAR}}`/
`{{LICENSE}}` in the hygiene/license assets. `{{YEAR}}` is the only token not
sourced from `Answers` — the helper computes it from the current UTC year. `.sh`
and shebang files are written executable (`0o755`) so the generic baseline is
genuinely green as scaffolded.

## Per-stack commands (single source of truth)

`STACK_COMMANDS` in the helper is the one table shared by `write_config` (what goes
into config) and `verify` (what actually runs), so config and the run always agree:

| Stack | lint (`typeCheckCommand`) | test (`testCommand`) | probe |
|-------|---------------------------|----------------------|-------|
| typescript | `npx tsc --noEmit` | `{pm} test` → `vitest run` | `node`, `{pm}` |
| python | `mypy .` | `pytest` | `python3`, `{pm}` |
| go | `go vet ./...` | `go test ./...` | `go` |
| rust | `cargo clippy` | `cargo test` | `cargo` |
| generic | `sh -n run.sh test.sh` | `./test.sh` | `sh` |

## Configuration & the additive `workspaces[]` extension

`write_config` reproduces `forge-init`'s exact field set + defaults (equivalence is
semantic — the key/value set, not byte order) and appends an explicit minimal
`loopRunner` block. The only schema change bootstrap relies on is an **additive,
optional** `workspaces[]` array in `references/forge-config-schema.json`: a
single-package project omits it; a monorepo populates it and nulls the three
top-level scalars. The top-level config object is open, so every pre-existing
config still validates. (The `workspaces[]` item schema is closed and intentionally
omits `packageManager` — the per-member commands are already fully resolved.)

> **Boundary (OQ-T1).** Bootstrap *writes* the `workspaces[]` representation;
> making downstream stages *resolve* a member's stack from it is a deferred
> follow-up beyond this feature.

## Key design decisions

- **Hybrid helper + skill** — keeps `SKILL.md` within the spec-purity budget and
  makes mechanics testable. (The alternative, inlining mechanics in prose, fails CI.)
- **Editable templates, not generated code** — stacks are assets a maintainer can
  read and edit; adding a stack/license is additive (drop a directory + a Q option).
- **Bundled, tokenized license texts** (MIT, Apache-2.0) — offline and stdlib-only,
  like `cargo new` / `npm init`; no network fetch.
- **`AGENTS.md` always, `CLAUDE.md` only on a Claude host** — the portable agent
  file is universal; the Claude-specific one is gated on `Answers.host`.
- **Transient root sentinel** for crash-safe resume, removed before staging so it
  never lands in history.

## Build, test & CI wiring

- `scripts/validate.sh` runs `py_compile` on `forge-bootstrap.py` (alongside
  `epic-manifest.py`) and the whole `tests/` pytest sweep (which auto-discovers
  `test_forge_bootstrap.py`).
- Adding the skill means regenerating the per-agent bundles with
  `python3 scripts/build-adapters.py` (a hard `--check` CI gate over the repo-root
  `adapters/` tree); the generator discovers the new skill + its `references/` by
  glob — no generator code change.
- `SKILL.md` is gated by `check-spec-purity.py` (≤ 300 lines / ≤ 5000 words).
