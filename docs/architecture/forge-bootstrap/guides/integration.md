# Integration Guide — Forge Bootstrap

How `forge-bootstrap` fits into the pipeline, and how to extend it. For the command
surface see [../cli-reference.md](../cli-reference.md).

## Where bootstrap sits

Bootstrap runs **before** the numbered pipeline, on an empty repo:

```
(empty repo)
   └─ /feature-forge:forge-bootstrap         ← pre-pipeline: structure + toolchain + green baseline + forge.config.json
        └─ /feature-forge:forge-1-prd <feature>   (Stage 1)   ── or ──   /feature-forge:forge-0-epic <epic>  (Stage 0)
             └─ forge-2-tech → forge-3-specs → forge-4-backlog → forge-5-loop → forge-6-docs
```

Its hand-off contract to the pipeline is exactly: a runnable, **green** repo with a
valid `forge.config.json` whose `stack` / `typeCheckCommand` / `testCommand` (or
per-member `workspaces[]`) are the very commands Stage 4's backlog acceptance
criteria will run. Because bootstrap writes a config equivalent to `forge-init`'s
(plus an explicit `loopRunner`), **running `forge-init` afterward is unnecessary**.

It is purely additive: with bootstrap unused, every existing command behaves
byte-for-byte as before.

## Mode B — chaining into the pipeline

Mode B is opt-in (interview Q7; default is Mode A only). After a **verified-green**
baseline **and** a successful commit, the body asks feature-vs-epic (Q8) and
launches the next stage **skill-to-skill** — `forge-1-prd <feature>` or
`forge-0-epic <epic>` — instead of printing the command. The gate is strict: if the
baseline is unverified (toolchain missing) or not-green, Mode B does **not** launch
and does not even ask Q8; it falls back to the Mode A summary with the next command
printed. Mode B only ever launches the *immediate* next stage — subsequent stages
stay normal, user-driven steps. The epic seed (name + decomposition) is proposed
from the project name + purpose and user-confirmed before hand-off.

## Host adaptation (agent-agnostic)

Bootstrap works on any supported host. On a host with `AskUserQuestion` (e.g.
Claude) the interview uses structured input; on a host without it (e.g. Codex) the
body emits the **same** questions as a single numbered text list and waits for one
reply, parsed positionally. The question content/defaults are identical across both
paths. The body resolves its scripts via the portable-root prelude
(content-addressed `forge-root.sh`), never a Claude-only path.

Two `Answers` fields are filled from the runtime rather than asked: `author` (from
`git config user.name`, else the project name) and `host` (`"claude"` on a Claude
host) — the latter makes the helper emit `CLAUDE.md` alongside the always-present
`AGENTS.md`.

> **Running the loop with a non-Claude agent (rauf).** The backlog this pipeline
> produces carries Claude tier aliases (`opus`/`sonnet`) in `item.model`. rauf
> forwards `item.model` to the selected agent, and a non-Claude agent (e.g. codex)
> rejects those aliases — every spawn fails and the loop circuit-breaks. If you run
> `forge-5-loop` under a non-Claude agent, strip/translate `model` first; under the
> default Claude runner the aliases are valid. (Tracked upstream.)

## Adding a stack profile

Stacks are editable assets, so adding one is additive:

1. Create `skills/forge-bootstrap/references/templates/<stack>/` with the file set
   (a manifest, a runnable entrypoint, at least one passing test, a
   `.gitignore` that lists `.forge-bootstrap.json`), using the `{{TOKENS}}`.
2. Add the stack to the `Stack` literal and a `STACK_COMMANDS[<stack>]` row
   (lint template, test template, toolchain-probe binaries) in
   `scripts/forge-bootstrap.py`. If it has a package-manager choice, add a
   `PACKAGE_MANAGERS[<stack>]` entry.
3. Add the option to interview Q3 in `SKILL.md`.
4. Add tests: extend the per-stack emission/command test and (toolchain-gated)
   green-baseline test in `tests/test_forge_bootstrap.py`.
5. Regenerate adapters: `python3 scripts/build-adapters.py` (and commit).

The generic profile is the model for a real, zero-dependency lint + test (`sh -n`
of the scripts + a behavioral `./test.sh`) — use it when there is no language
toolchain to defer to.

## Adding a license

Drop a tokenized `skills/forge-bootstrap/references/templates/licenses/<id>/LICENSE`
(using `{{YEAR}}` / `{{AUTHOR}}` / `{{PROJECT_NAME}}`) and add `<id>` to interview
Q5. `write_hygiene` composes `licenses/<Answers.license>/LICENSE`; an id with no
matching directory is a usage error, so the interview must only offer ids that exist
as assets. `license == "none"` writes no LICENSE.

## Verifying changes

After any change to the helper, templates, or `SKILL.md`:

```bash
python3 -m py_compile scripts/forge-bootstrap.py     # helper compiles
python3 -m pytest tests/test_forge_bootstrap.py -q   # unit + integration tests
bash scripts/validate.sh                             # full gate: spec-purity, adapter drift, py_compile, pytest, traceability
```

`validate.sh` must exit 0. If it reports "adapters/ is out of date", run
`python3 scripts/build-adapters.py` and commit the regenerated `adapters/` tree.
Editing `SKILL.md` or anything under `references/` requires this regeneration; the
spec-purity gate also enforces the `SKILL.md` body stays ≤ 300 lines / ≤ 5000 words.

## Common issues

- **"This repo is not empty" refusal** — bootstrap only scaffolds a brand-new
  project. Use `/feature-forge:forge-init` then `/feature-forge:forge-1-prd`.
- **Verification: UNVERIFIED** — the chosen stack's toolchain isn't installed; the
  baseline was scaffolded but not run. Install the toolchain and re-run `verify`.
  An unverified baseline cannot launch Mode B.
- **Re-run finds a partial scaffold** — bootstrap detected its own
  `.forge-bootstrap.json` sentinel and offers resume / restart / cancel; it never
  refuses its own in-progress work as if it were a foreign project.
