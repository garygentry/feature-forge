# Contributing

Short guide. The full build/test contract lives in [`AGENTS.md`](AGENTS.md) — it is read every session by every coding agent that works here, and it is the source of truth for the toolchain, `scripts/validate.sh`, the smoke command, the branching rules, and the prose-change gate.

## Scoping rules (from #265)

Two rules govern how a change is packaged, so a reviewer can read it without having to hold both halves at once:

1. **A PR changes the generator or canon, not both.** `scripts/build-adapters.py` and `adapter-src/` produce the six bundles under `adapters/`; `skills/`, `agents/`, and `references/` are the canon they're built from. A canon edit legitimately touches ~900 generated files; an emitter edit that touches ~900 files is the case to read carefully, and the two changes are much easier to understand separately.
2. **A prose PR touches one skill family.** If the change is body text in a `skills/*/SKILL.md` or in the two shared references (`stage-exit-protocol.md`, `shared-conventions.md`), keep it to one family per PR and paste the compliance-eval result (see below).

The PR template's checkboxes name both rules; the drift diff-stat it asks for is what tells a reviewer whether they're looking at a canon change (~900 files, all in `adapters/`, expected) or an emitter change (~900 files, expected but read carefully).

## Prose-change gate (#268)

Every PR whose diff touches canon prose records a compliance-eval result in its description before merge. The runbook, cost table and recorded baseline live in [`eval/README.md`](eval/README.md) § *Quick invocations*; the full contract lives in `AGENTS.md` § *Prose-change gate*. It is advisory, not a correctness check: the eval reports a rate, and a maintained rate is what the gate is looking for.

Pipeline-mechanical changes (scripts, adapters, tests, docs, workflows) are outside the gate — nothing on that instrument for them to move — and so are frontmatter-only edits, which the weekly trigger-accuracy eval covers instead.

## Before opening a PR

- `bash scripts/validate.sh` green locally. It runs spec-purity, the adapters drift gate, the full pytest suite, `adapter-src/pi` verify, ruff, traceability, and version-sync.
- `python3 scripts/build-adapters.py` (or `--check`) so `adapters/` is in sync with canon. **Never hand-edit `adapters/`** — the drift gate will reject it.
- If the PR is prose, run the narrowest compliance eval probe that covers it, and paste the JSON summary or per-cell rates into the PR description.

## Issue reports

Bug reports use the template in [`.github/ISSUE_TEMPLATE/`](.github/ISSUE_TEMPLATE/), which asks for `python3 scripts/forge-session.py doctor --json` output and the host/adapter in use. Those two pieces are what let a maintainer reproduce the environment before reading the report.

## Where things live

- `AGENTS.md` — the session contract, read every turn by coding agents (and by you before a first PR).
- `scripts/validate.sh` — the local repro of what CI runs.
- `eval/README.md` — the two eval harnesses, their invocations and the recorded baselines.
- `docs/claude-5/` — recorded compliance-eval baselines.
- `.github/workflows/` — CI (`ci.yml`), docs deploy (`docs.yml`), installer matrix (`os-matrix.yml`), advisory evals (`eval.yml`).
