# Guardrails — Don't-Break Constraints for This Work

> Repo-specific gotchas and hard constraints the pipeline (tech spec, specs,
> backlog acceptance criteria) must encode. Sourced from the audit plus
> accumulated project history.

## 1. Behavior preservation is the prime directive

The system works well under extensive real feature-development use. Every
change in this effort is a **relocation** of instruction text, a **dedup**, or
a **script extraction** — never a rewording of interactive protocol content.
Specifically frozen: AskUserQuestion turn structure, Decision Support
protocol, Branch Setup/Reconciliation prompts, Stage-Entry Guard /
Stage-Completion Re-check classification logic, Git Commit Protocol
(two-commit sequence, never `--amend`), verify gates and stage-exit directive
handling, anti-fabrication guards. If a sentence must change to move, flag it
in review rather than silently adapting it.

## 2. CI gates that local runs don't surface

- **`scripts/check-spec-purity.py`** (Quality Gate workflow) caps skill bodies
  at **300 lines** — pytest does NOT run it. forge-5-loop sits at the cap;
  R6 must not push runner-contract text back into the body. Workaround
  precedent: long unwrapped lines count as one line.
- **`ruff check scripts/ eval/`** is CI-only — run locally before pushing any
  `forge-session.py` change (R4/R5).
- `jsonschema` is absent in CI — don't add a hard dependency on it in new
  helper code paths.

## 3. Adapter build & fan-out (`scripts/build-adapters.py`)

- Step 2b does **citation-driven fan-out**: reference files are discovered by
  scanning skill bodies for cited paths. Any new file (`checklists/*.md`,
  `blocks/*.md`, `agent-selection.md`) must be **cited by path from a skill
  body** or it silently won't ship to non-Claude adapters.
- Skill **bodies** are host-term translated (e.g. `/clear` degraded);
  skill-own **references are copied verbatim** — never put a literal `/clear`
  or Claude-only tool name into a reference file that non-Claude hosts read
  (this is why `result-reporting.md`'s warm block is phrased host-neutrally).
- After moving/splitting files: regenerate adapters (+260-file surface) and
  refresh fixtures. **Gemini fixture gotcha:** build `--root` on a
  minimal-canon scratch dir then `command cp -f` the result — do NOT copy the
  real adapter.

## 4. Drift-guard test discipline

`tests/test_stage_exit_protocol.py` asserts stamped blocks stay in sync with
their source. Extend this pattern, don't weaken it:
- R1: assert each per-mode checklist file contains exactly its expected
  CHECK-IDs and that the skill's expected-count table matches.
- R7: assert every invoke-point sentence in a skill names an existing block
  file, and every block file is cited by at least one skill.

## 5. Prelude history (why R2 is within-file only)

The inline 3-line `R=` resolver with `${CLAUDE_PLUGIN_ROOT:-}` as first hint
was a deliberate reliability fix (PR #101, stabilization chunk 2b) — npm/
non-Claude installs have no `CLAUDE_PLUGIN_ROOT`, and a skill body must
resolve the plugin root without reading any other file. Therefore: dedupe
only **within** a file (first occurrence stays verbatim); never rely on a
cross-file "see shared-conventions for the prelude" pointer in an executable
path. The shared-refs resolution gap (#122/#132) is the cautionary tale for
assuming references resolve on all hosts.

## 6. Dual-role skill hazard (forge-verify)

forge-verify is pre-loaded into the `forge-verifier` subagent AND read by the
parent orchestrator. The v0.12.1 self-dispatch bug (verifier re-dispatching
itself) was fixed with an explicit "which role are you?" guard at the top.
R1's checklist split must keep the role guard intact and keep
orchestrator-facing material (findings template, synthesis, epic state write)
out of the files the subagent is told to read.

## 7. Measure first, optimize second

Baselines in `LOAD-MAP.md` are static file measurements. Before R4
especially, verify from real transcripts (the consumption-data-refresh
dogfood runs are the evidence source) whether the model actually performs the
reads being optimized. Success criteria should be phrased against re-measured
baselines at implementation time, not the audit's snapshot.

## 8. Release mechanics (for the eventual ship)

Standard batch-release flow applies: 3 version-sync fields (gemini via
`GEMINI_EXTENSION_VERSION` + regen), installer version line is independent
(a rauf-pin-style change must also bump `installer/package.json`), npm@11
pinned in the publish workflow for `--provenance`. Not pipeline work, but the
backlog should not include release items — releases are batched manually.
