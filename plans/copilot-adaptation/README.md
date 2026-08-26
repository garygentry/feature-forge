# Copilot Adaptation Implementation Runbook

Status: Active implementation; RAUF-203 durable, Phase C at RAUF-204
Last updated: 2026-08-25
Repositories: `feature-forge` and sibling `../rauf`

This directory is the durable handoff surface for adapting both products to GitHub Copilot. Read
this file first in every implementation session. The process is intentionally idempotent: repeating
it identifies the same first unfinished task without regenerating, reverting, or duplicating work.

> **Persistence boundary:** `plans/copilot-adaptation/` is the explicit tracked exception to the
> repository's general `plans/` ignore rule. Check `git ls-files plans/copilot-adaptation` before
> treating a plan or evidence file as durable, and do not claim cross-machine continuity until the
> intended files are committed and pushed. Tracked implementation, tests, generated artifacts,
> sanitized evidence, changelog, and repository gates remain the proof of completed product work.

## Document Authority

1. `unified-copilot-adaptation-plan.md` controls task definitions, decisions, dependencies, phase
   exits, cross-repository gates, support claims, and release order.
2. `EXECUTION.md` is the mutable multi-session ledger: current cursor, operational states,
   blockers, repository coordinates, evidence receipts, and exact remaining sequence.
3. `copilot-adapter-full-support.md` and `rauf-copilot-cli-and-harness-remediation.md` are detailed
   design/history references. Their historical checkboxes are not current-status authority.
4. Each repository's `AGENTS.md` controls contribution, validation, and release mechanics inside
   that repository.

When documents conflict, use the unified plan for requirements, `EXECUTION.md` for current state,
and the owning repository's `AGENTS.md` for local execution. Reconcile the conflict before editing.

## Current Snapshot

At the end of the 2026-08-24 implementation session:

- **Active coordination phase:** Phases A and B are complete; G0, G1, and G2 are closed.
   `TRACK-001` made the authoritative planning and runtime evidence fresh-clone durable, and
   `RAUF-202R` closed operator dependency/prose residuals, and `RAUF-203` closed child-instruction
   ownership. Phase C is active at `RAUF-204`.
- **Implemented but not yet a complete phase:** feature-forge Phase D native plugin foundation.
- **Started in code:** rauf uses the provider-neutral `AgentStreamEvent` internally, retains
   `ClaudeStreamEvent` as an exported compatibility alias, has a buffered Copilot JSONL parser,
   and has a dedicated `CopilotCliProvider` registered under the stable `copilot` id. Copilot-
   owned failure classification now routes through existing runner outcomes without `checkUsage`.
- **Started in code:** rauf now generates a native Copilot operator bundle from its canonical four
   skills and two agents, with provenance, deterministic ordering, stale-file detection, strict
   policy mapping, and a generated mapping/drop report.
- **Still open:** rauf Copilot drift/version/package gates, feature-forge direct-install migration,
  the packaged cross-repository harness, and releases.
- **Feature-forge native adapter milestone committed:** branch `docs/copilot-g2-contract`, commit
   `7754a3b` (`feat(adapters): add native Copilot plugin output`) contains native `SKILL.md` output,
   native `.agent.md` workers, the generated plugin manifest/tree/fixtures, Copilot version-sync
   coverage, changelog entry, and tests. The worktree is clean.
- **Rauf milestones committed:** branch `feat/copilot-g2-contract`, commits `45603b1`
   (`refactor(loop): neutralize stream event type`) and `921971c`
   (`feat(loop): parse Copilot JSONL output`), and `d63cdc4`
   (`feat(loop): add Copilot CLI provider`), `a4f50e0`
   (`feat(loop): register dedicated Copilot provider`), and `7dd6f3d`
   (`feat(loop): classify Copilot failures`), and `fa3a624`
   (`test(loop): prove Copilot signal and git boundaries`), `9bbc3e5`
   (`test(loop): add Copilot runtime matrix`), and `5f3710b`
   (`feat(cli): make provider selection portable`), plus signed commit `db40ed0`
   (`feat(adapters): add native Copilot operator bundle`). The branch is pushed to origin.
- **RAUF-201 verification:** generation and `copilot:check` passed with Bun 1.3.10; six focused
   generator tests, ESLint, and Prettier passed. The full rauf gate passed 2,277 package tests plus
   89 repository-script tests, along with build, schema/version/existing-adapter drift, typecheck,
   lint, formatting, and documentation checks.
- **RAUF-202 verification:** authenticated Copilot CLI 1.0.80 loaded both generated operator agents.
   The reviewer used read/search/execute, had no edit tool, and left its marker unchanged. The driver
   invoked and polled schema-v1 rauf JSON status twice, refused iteration implementation and RAUF
   signaling, and changed no files. Unknown policy aliases now fail generation; seven focused tests
   passed with an injected `mystery-tool` rejection. `copilot:check`, ESLint, Prettier, and the full
   Bun 1.3.10 rauf gate passed 2,188 package tests plus 90 repository-script tests.
- **Verified:** Copilot CLI 1.0.78 cached local installation discovers all 13 feature-forge skills;
  a structured prompt session loads all three custom agents with expected tools and no warnings.
- **New G1 evidence:** direct project/personal discovery, prefixed invocation, worker capability
   checks, fresh VS Code/Agent Host discovery of all 13 skills and three agents, installed guide
   loading, and parent-to-researcher delegation pass. See
   `evidence/copilot-host-contract-2026-08-23.md`.
- **Prior G1 failure:** in fresh VS Code 1.134.0/Copilot Chat 0.62.0, the preinstalled legacy root
   `hooks.json` was registered and invoked, but `${PLUGIN_ROOT}` was neither host-expanded nor
   exported to the hook process. Bash attempted `/scripts/plugin-root-probe.sh`; the expected output
   file was absent. The exact trace and recovery are in
   `evidence/copilot-host-contract-2026-08-23.md`.
- **Legacy probe cleanup complete:** `feature-forge@feature-forge-g1-probe`, marketplace
   `feature-forge-g1-probe`, its installed cache, and `/tmp/feature-forge-copilot-g1` were removed.
   The original registry was verified: only `databricks@databricks-agent-skills` and marketplace
   `databricks-agent-skills` remained before the replacement probe was installed.
- **Replacement probe result:** in a fully restarted host, the command token remained literal and
   its script did not run; the independent absolute helper ran and recorded `PLUGIN_ROOT=UNSET`.
   The 2026-08-23 scope decision requires package self-location plus explicit
   `FEATURE_FORGE_ROOT`, closes `COP-003`/G1, and permits `COP-004` to proceed.
- **Known CLI limitation:** in 1.0.78, `--plugin-dir` loads feature-forge agents but omits plugin
  skills. Use an installed plugin for skill-discovery proof.
- **COP-004 complete:** `evidence/copilot-cli-child-contract-2026-08-23.md` freezes bounded prompt
   indirection, exact argv and named permissions, JSONL reconstruction and parser edges, auth/model/
   permission failures, usage telemetry limits, timeout/abort/process-group cleanup, and sanitized
   environment handling. Full prompt argv is rejected with `E2BIG`.
- **COP-005 complete:** direct nested wrapper launch is denied. The selected parent topology is a
   workspace-local rauf command and detached runner with machine-readable start/status and filtered
   Copilot session variables. It passed from the current VS Code/Agent Host terminal and a Copilot
   CLI 1.0.78 parent.
- **Verification:** `tests/test_build_adapters.py` passed 117 tests in a disposable environment;
  `bash scripts/validate.sh` passed. Local validation reported only expected missing-tool warnings
  for Claude CLI, pytest in system Python, and ruff; focused pytest was run separately.
- **RAUF-101 verification:** `pnpm --filter @rauf/loop typecheck` passed after building the core
   project reference with pinned Bun 1.3.10; the stream parser, Codex parser, and Codex provider
   focused suite passed 25 tests. Internal `ClaudeStreamEvent` usages are eliminated.
- **RAUF-102 verification:** the Copilot/Codex/Claude parser suite passed 23 tests; loop typecheck,
   lint, and changed-file formatting passed. The parser preserves raw output, reconstructs only
   assistant content, flushes a trailing record, and contains malformed input/callback failures.
- **RAUF-103 verification:** the focused Copilot/Codex/Claude provider/parser/process suite passed
   48 tests; loop typecheck, changed-file lint, and formatting passed. The provider uses the frozen
   argv and environment filter, bounded prompt-file indirection, shared process-group controls,
   parser reconstruction, raw output preservation, and unconditional prompt cleanup.
- **RAUF-104 verification:** the focused registry/preset/selection suite passed 52 tests, all
   provider and selection tests passed 116 tests, and loop typecheck, changed-file lint, and
   formatting passed. Exactly one `copilot` descriptor constructs the dedicated provider; the
   generic preset is gone and item/project/global provider values remain unchanged.
- **RAUF-105 verification:** auth, invalid-model, permission, limit/credit, timeout,
   infrastructure, malformed-output, missing-signal, cancellation, and spawn failure are routed
   through existing runner outcomes without Claude OAuth/reset semantics. `checkUsage` remains
   absent. The affected 107-test slice, loop typecheck, lint, and formatting passed.
- **RAUF-106 verification:** Copilot metadata/tool/error tokens are excluded from signals, the
   last assistant signal wins, fenced quoted tokens are neutralized, commit/push deny flags remain
   bounded, and rauf creates exactly one post-signal commit. The focused 147-test slice, loop
   typecheck, lint, and formatting passed.
- **RAUF-107 verification:** sanitized provider/sandbox matrices cover signals, malformed/unknown
   output, nonzero/auth/model/permission/timeout failures, process cleanup, telemetry, and direct,
   detached, resume, and review paths. Review now parses reconstructed provider text. The sandbox
   passed 192 assertions; 261 focused tests and static checks passed.
- **RAUF-108 verification:** registry-validated install/init persist Copilot without changing
   precedence; selected-binary preflight replaces the Claude-only warning; Copilot marker argv
   config is rejected; direct/detached/resume/review/web and compiled CLI paths preserve provider
   and model policy; binary presence and tri-state auth readiness are distinct. Compiled smokes and
   the full gate passed 2,271 package tests plus 83 script tests.

The snapshot is evidence, not a substitute for startup checks.

## Idempotent Session Startup

Run these steps in order on every session, including resumed sessions:

1. Resolve the repositories and read governing files:

   ```bash
   cd /home/gary/workspace/feature-forge
   cat AGENTS.md
   cat plans/copilot-adaptation/README.md
   cat plans/copilot-adaptation/EXECUTION.md
   cat plans/copilot-adaptation/unified-copilot-adaptation-plan.md
   cat ../rauf/AGENTS.md
   ```

2. Inspect both worktrees before interpreting status:

   ```bash
   git status --short
   git -C ../rauf status --short
   git --no-pager diff -- plans/copilot-adaptation scripts/build-adapters.py \
     scripts/check-version-sync.py tests adapters/copilot adapters/GENERATION-REPORT.md CHANGELOG.md
   git -C ../rauf --no-pager diff
   ```

   Treat every pre-existing change as user/session work. Never reset, discard, or regenerate over it
   until its ownership and relation to the active task are understood.

3. Confirm the completed disposable root probes have not reappeared:

   ```bash
   copilot plugin list
   copilot plugin marketplace list
   ```

   The named G1 probes and `/tmp` fixtures were removed. Do not reinstall or repeat them. Never
   uninstall an intentional user installation; investigate any unexpected entry before acting.

4. Locate the active bounded task:
   - Read the one `ACTIVE` row in `EXECUTION.md`.
   - Confirm its dependencies against the unified plan.
   - Continue only its remaining acceptance bullets.
   - Do not reopen completed evidence unless the relevant source, generated output, CLI version, or
     schema changed.

5. State one local hypothesis and one falsifying check before editing. Make the smallest edit that
   can satisfy one task or one independently testable subtask. Immediately run its focused check.

6. Never cross a phase exit implicitly. Update the task evidence and phase status only after every
   listed exit criterion passes. A generated file, a passing schema test, and runtime discovery are
   separate forms of proof.

## Active Next Work

The current cursor and complete order live only in `EXECUTION.md`:

1. Complete `RAUF-204`: wire Copilot drift into the gate, enforce version lockstep, and verify
   repository, compiled-binary, and package contents.
2. Proceed through the remaining ledger in dependency order.
3. Do not repeat either completed root probe in `operator-actions.md`.
4. Release tasks remain owner-gated even when every implementation and integration task is green.

## Task Completion Protocol

A task can change from `[ ]` to `[x]` only when all of the following are true:

- Every dependency and phase entry criterion is complete.
- The code/document change exists in the owning repository.
- The focused executable check named by the task passes.
- Generated output is regenerated and its drift check passes when canon/generator input changed.
- Runtime claims include date, product version, platform, command, expected result, and redacted
  evidence location.
- The owning repository's broader gate passes when the task closes a phase or changes a shared
  contract.
- The unified plan contains a concise evidence note and `EXECUTION.md` advances to exactly one new
  cursor; source-plan history is updated only when its design or acceptance bullets changed.

Partial work remains unchecked and receives a `Progress:` note naming exactly what remains.

## Session Close Protocol

Before ending any implementation session:

1. Run the narrow check for the last edit and the owning repository gate when available.
2. Run `git diff --check` and inspect `git status --short` in both repositories.
3. Remove temporary fixtures, local plugin registrations, copied package trees, and secrets.
4. Update `EXECUTION.md` atomically: task state/evidence, repository heads, session receipt, and
   exactly one next cursor. Update the unified task evidence/checkbox and root `STATUS.md` when a
   task or phase materially changes repository status. Source plans remain design/history references.
5. Confirm every required plan/evidence file is tracked; cross-machine durability also requires the
   intended commit to be pushed.
6. Record blockers as a concrete failed criterion with evidence. Do not call a phase complete with an
   unsupported required smoke cell.
7. Do not commit, publish, tag, or dispatch release workflows unless the user explicitly requests
   the repository's owner-gated action.

## Phase Advancement Rule

A phase is bounded by the table in the unified plan. Work stops at its exit boundary. The next phase
may begin only when:

- its entry gate is closed;
- the prior phase's outputs are present and verified;
- no unresolved finding invalidates those outputs; and
- `EXECUTION.md`, the unified task state, and root `STATUS.md` agree at phase boundaries.

If these conditions are not met, continue the current phase or record a blocker. Do not compensate by
starting unrelated downstream work.

## Continuation Prompt

Use the prompt printed at the end of the session that created `EXECUTION.md`. On every later handoff,
regenerate that prompt from the tracker rather than copying an older task-specific prompt. The prompt
must name the current cursor, repository coordinates, durability checks, bounded execution rule,
evidence protocol, and owner-gated release boundary.
