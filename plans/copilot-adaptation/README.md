# Copilot Adaptation Implementation Runbook

Status: Active implementation; Phases A and B complete, Phase C at RAUF-203
Last updated: 2026-08-24
Repositories: `feature-forge` and sibling `../rauf`

This directory is the durable handoff surface for adapting both products to GitHub Copilot. Read
this file first in every implementation session. The process is intentionally idempotent: repeating
it identifies the same first unfinished task without regenerating, reverting, or duplicating work.

> **Persistence boundary:** the repository's `.gitignore` excludes new files under `plans/`, but
> files already tracked on this branch remain tracked. Check `git ls-files plans/copilot-adaptation`
> before treating a plan or evidence file as durable: unlisted files persist only in this workspace
> and are absent from fresh clones. Do not change `.gitignore`, force-add plans, or relocate them
> without an explicit owner decision. Tracked implementation, tests, generated artifacts,
> changelog, and repository gates remain the authoritative proof of completed product work.

## Document Authority

1. `unified-copilot-adaptation-plan.md` is the controlling tracker for decisions, task IDs,
   dependencies, phase exits, cross-repository gates, and release order.
2. `copilot-adapter-full-support.md` is detailed feature-forge design evidence and a local progress
   ledger. It does not override the unified tracker.
3. `rauf-copilot-cli-and-harness-remediation.md` is detailed rauf design evidence and a local
   progress ledger. It does not override the unified tracker.
4. Each repository's `AGENTS.md` controls contribution, validation, and release mechanics inside
   that repository.

When documents conflict, use the unified plan for sequencing and the owning repository's
`AGENTS.md` for local execution.

## Current Snapshot

At the end of the 2026-08-24 implementation session:

- **Active coordination phase:** Phases A and B are complete; G0, G1, and G2 are closed. Phase C is
   in progress; `RAUF-201` and `RAUF-202` are complete and `RAUF-203` is next.
- **Implemented but not yet a complete phase:** feature-forge Phase D native plugin foundation.
- **Started in code:** rauf uses the provider-neutral `AgentStreamEvent` internally, retains
   `ClaudeStreamEvent` as an exported compatibility alias, has a buffered Copilot JSONL parser,
   and has a dedicated `CopilotCliProvider` registered under the stable `copilot` id. Copilot-
   owned failure classification now routes through existing runner outcomes without `checkUsage`.
- **Started in code:** rauf now generates a native Copilot operator bundle from its canonical four
   skills and two agents, with provenance, deterministic ordering, stale-file detection, strict
   policy mapping, and a generated mapping/drop report.
- **Not started in code:** rauf operator-boundary runtime enforcement, feature-forge direct-install
   migration, packaged cross-repository harness, and releases.
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

3. Reconcile temporary Copilot probes with the active handoff:

   ```bash
   copilot plugin list
   ```

   While `COP-003` has the current restart handoff, preserve only the explicitly named
   `feature-forge-g1-v1-probe@feature-forge-g1-v1` until its fresh-host evidence is captured. Any
   other feature-forge plugin requires an ownership check before removal. Never uninstall an
   intentional user installation.

4. Locate the active bounded task:
   - Read the phase status table in the unified plan.
   - Select the first `In progress` phase whose entry criteria are satisfied.
   - Within it, select one open task whose dependencies are complete.
   - If a task has progress notes, continue only its remaining acceptance bullets.
   - Do not reopen completed evidence unless the relevant source, generated output, CLI version, or
     schema changed.

5. State one local hypothesis and one falsifying check before editing. Make the smallest edit that
   can satisfy one task or one independently testable subtask. Immediately run its focused check.

6. Never cross a phase exit implicitly. Update the task evidence and phase status only after every
   listed exit criterion passes. A generated file, a passing schema test, and runtime discovery are
   separate forms of proof.

## Active Next Work

The next session should execute these bounded items in order:

1. **Do not repeat the unchanged legacy-root probe.** It ran after a full host restart and failed;
   `operator-actions.md` is now a completed historical runbook.
2. **Continue Phase C at `RAUF-203` only.** Preserve installed child instruction ownership across
   `AGENTS.md`, `CLAUDE.md`, and `.rauf/RAUF.md` without exposing supervisor surfaces to iterations.
3. **Do not begin `RAUF-204`, repository documentation, feature-forge implementation, release, or
   publishing work.** Instruction ownership is the next bounded boundary.
4. In parallel only when independent and G1 is closed, finish feature-forge `FORGE-101`/`FORGE-102`
   residuals, then `FORGE-103` through `FORGE-107` in dependency order.

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
- The unified plan contains a concise evidence note and the source plan status agrees.

Partial work remains unchecked and receives a `Progress:` note naming exactly what remains.

## Session Close Protocol

Before ending any implementation session:

1. Run the narrow check for the last edit and the owning repository gate when available.
2. Run `git diff --check` and inspect `git status --short` in both repositories.
3. Remove temporary fixtures, local plugin registrations, copied package trees, and secrets.
4. Update all three status surfaces:
   - the unified plan's dashboard/task progress/review log;
   - the relevant source plan's phase status and checkboxes;
   - this README's Current Snapshot and Active Next Work if the active boundary changed.
5. Record blockers as a concrete failed criterion with evidence. Do not call a phase complete with an
   unsupported required smoke cell.
6. Do not commit, publish, tag, or dispatch release workflows unless the user explicitly requests
   the repository's owner-gated action.

## Phase Advancement Rule

A phase is bounded by the table in the unified plan. Work stops at its exit boundary. The next phase
may begin only when:

- its entry gate is closed;
- the prior phase's outputs are present and verified;
- no unresolved finding invalidates those outputs; and
- status in this README, the unified plan, and the owning source plan agrees.

If these conditions are not met, continue the current phase or record a blocker. Do not compensate by
starting unrelated downstream work.

## Continuation Prompt

Use this prompt to resume at the next logical milestone in a new session:

```text
Continue the GitHub Copilot adaptation at RAUF-203, using
plans/copilot-adaptation/README.md as the session runbook.

Repository coordinates at handoff:
- feature-forge: `origin/docs/copilot-g2-contract`; this tracked runbook, the unified tracker,
  rauf source plan, and STATUS.md contain the current cross-repository state.
- rauf: `origin/feat/copilot-g2-contract` at commit
  `02f8e67846ccf1ae59443a75c310458d6236ea6d`
  (`feat(adapters): enforce Copilot operator boundaries`).

First read both repositories' AGENTS.md files, then the runbook, unified tracker, rauf source plan,
and evidence/copilot-cli-child-contract-2026-08-23.md. Run the README's idempotent startup checks
and inspect both worktrees before editing. Treat any later changes as user/session work.

Phases A and B are complete. RAUF-101 through RAUF-202 are complete and must not be repeated.
RAUF-201 generated the native four-skill/two-agent Copilot operator bundle. RAUF-202 added
fail-loud tool-alias validation and authenticated Copilot CLI 1.0.80 runtime proof that the backlog
reviewer can read/search/execute but not edit, while the loop driver can invoke and poll rauf JSON
status yet refuses iteration implementation and RAUF signaling. Seven focused tests and the full
pinned-Bun-1.3.10 rauf gate passed 2,188 package tests plus 90 repository-script tests.

Execute RAUF-203 only. Preserve installed child instruction ownership across `AGENTS.md`,
`CLAUDE.md`, and `.rauf/RAUF.md`; prove Copilot loads the child rules and update/uninstall changes
only rauf-owned content without exposing supervisor customizations to the iteration child. Before
editing, state one falsifiable local hypothesis and one focused check, then run that check
immediately after the first substantive edit. Do not begin RAUF-204, feature-forge implementation,
repository documentation, release, publishing, or unrelated plugin registration changes.

At session close, run focused rauf checks and git diff --check in both repositories, inspect both
worktrees, remove disposable fixtures, and update the unified tracker, rauf source plan, evidence
when applicable, and this README handoff with the exact next bounded task.
```
