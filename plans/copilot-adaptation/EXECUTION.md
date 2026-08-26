# Copilot Adaptation Durable Execution Tracker

Status: Active
Last updated: 2026-08-25
Current cursor: `RAUF-203`
Repositories:

- feature-forge: `docs/copilot-g2-contract` tracking `origin/docs/copilot-g2-contract`
- rauf: `feat/copilot-g2-contract` tracking `origin/feat/copilot-g2-contract`

## Purpose and authority

This is the durable multi-session status ledger for completing GitHub Copilot support across
feature-forge and rauf.

- `unified-copilot-adaptation-plan.md` controls task definitions, decisions, dependencies, gates,
  support claims, and release order.
- This file controls the current cursor, operational state, blockers, repository coordinates, and
  session-to-session receipts.
- `copilot-adapter-full-support.md` and `rauf-copilot-cli-and-harness-remediation.md` are detailed
  design references. Their historical checkboxes are not current-status authority.
- `README.md` is the startup/close runbook.
- Root `STATUS.md` remains feature-forge's repository-level summary; update it at phase exits or
  when the current cursor materially changes, not after every focused test.

If this file conflicts with the unified plan's requirements, the unified plan wins. Reconcile the
conflict before implementation rather than silently choosing one.

## Status vocabulary

- `ACTIVE`: the only current cursor.
- `READY`: dependencies complete; may run after the active task.
- `BLOCKED`: a named dependency, missing evidence, or owner action prevents work.
- `OPEN`: not ready yet.
- `DONE`: acceptance evidence is durable and linked from the task row.
- `OWNER`: requires explicit repository-owner approval; never execute implicitly.

Exactly one row may be `ACTIVE`. A task becomes `DONE` only when its implementation, focused checks,
required broader gate, generated output, and durable evidence are complete. Historical prose or an
uncommitted local probe is insufficient.

## Gates

| Gate | State | Closure |
| --- | --- | --- |
| G0 product contract | DONE | `COP-001`–`COP-002` |
| G1 Copilot host contract | DONE | `COP-003`, DEC-11; self-location plus explicit `FEATURE_FORGE_ROOT`, never required `PLUGIN_ROOT` |
| G2 Copilot CLI child contract | DONE | `COP-004`–`COP-005` |
| G3 clean repository/package gates | OPEN | `RAUF-302` and `FORGE-202` |
| G4 packaged clean install/discovery | OPEN | `INT-001`–`INT-003` |
| G5 integrated parent-harness matrix | OPEN | `INT-004`–`INT-007` |
| G6 live release compatibility | OPEN | `REL-001`–`REL-004` |

## Completed implementation baseline

| Scope | Durable implementation evidence |
| --- | --- |
| Contract freeze | `COP-001`–`COP-005`; tracked host/child evidence under `evidence/` |
| Rauf provider | `RAUF-101`–`RAUF-108`; rauf commits `45603b1` through `5f3710b` |
| Rauf native bundle | `RAUF-201`; rauf commit `db40ed0` |
| Rauf operator boundaries | `RAUF-202`; rauf commit `02f8e67`; exact sanitized recovery receipt in `evidence/rauf-202-operator-boundaries-2026-08-24.md` |
| Rauf operator dependencies/prose | `RAUF-202R`; rauf commit `4668553`; exact runtime receipt in `evidence/rauf-202r-operator-dependencies-2026-08-25.md` |
| Feature-forge native foundation | feature-forge commit `7754a3b`; native skills/agents and legacy-format Copilot plugin manifest; `FORGE-101`/`102` remain partial |

## Open-work ledger

The sequence below is intentionally conservative. Parallel work is allowed only when dependencies
are closed, worktrees/files do not overlap, and each repository has one writer.

| Order | ID | Repo | State | Depends on | Remaining acceptance / exit proof |
| ---: | --- | --- | --- | --- | --- |
| 1 | `TRACK-001` | feature-forge/shared | DONE | — | Authoritative plans/evidence are tracked on the adaptation branch; exact sanitized `RAUF-202` recovery evidence, cleanup, cursor reconciliation, and fresh-clone readability are verified in the 2026-08-25 receipt below. |
| 2 | `RAUF-202R` | rauf | DONE | `TRACK-001`, `RAUF-202` | Commit `4668553` composes each required canonical skill into its Copilot operator agent with fail-loud dependency validation, host-neutral delegation wording, regenerated Codex/Copilot/Pi outputs, plugin-only topology, green runtime probes/drift/full gate, and exact evidence. |
| 3 | `RAUF-203` | rauf | ACTIVE | `RAUF-202R` | Preserve child instruction ownership. Standalone Copilot must load rauf's host-neutral `AGENTS.md`; the actual iteration provider must retain `--no-custom-instructions` and receive `.rauf/RAUF.md` through the prompt only. Define managed/user ownership for `.rauf/RAUF.md`; preserve user content through install/update/repeated-update/uninstall; isolate Claude and supervisor instructions; prove feature-forge/rauf sentinel coexistence. |
| 4 | `RAUF-204` | rauf | OPEN | `RAUF-203` | Add `copilot:check` to `pnpm gate`; lock plugin/product versions; verify repository, compiled binary, and npm/binary package contents; retain deterministic stale-file checks. |
| 5 | `FORGE-101` | feature-forge | READY | `TRACK-001` | Finish distribution-aware invocation/reference translation. Accurately classify the current manifest as legacy Copilot format, or migrate and runtime-prove actual Agent Plugins 1.0 schema/layout; do not claim 1.0 from the current seven-field manifest. |
| 6 | `FORGE-102` | feature-forge | OPEN | `FORGE-101` | Implement/test the verifier's `forge-verify` dependency; remove unsupported persistent-memory promises; retain durable researcher/verifier edit denial and writer edit success evidence; prove named dispatch patterns. |
| 7 | `FORGE-103` | feature-forge | OPEN | `FORGE-101` | Resolve runtime assets by self-location and explicit `FEATURE_FORGE_ROOT` across plugin/project/personal/subdirectory layouts; test complete/degraded roots, spaces, metacharacters, and existing hosts. Do not depend on `PLUGIN_ROOT`. |
| 8 | `FORGE-104` | feature-forge | OPEN | `FORGE-101` | Add recursive skill and agent mirror placements with containment, dry-run parity, copy/symlink behavior, manifest ownership, exact uninstall, and conservative explicit Copilot detection. |
| 9 | `FORGE-105` | feature-forge | OPEN | `FORGE-102`, `FORGE-103`, `FORGE-104` | Implement and runtime-prove fresh project/personal installs with one complete runtime bundle per scope; only then mark confidence `verified-current`. |
| 10 | `FORGE-106` | feature-forge | OPEN | `FORGE-105` | Implement apply/verify/remove/write-last legacy migration; preserve modified managed blocks as `skip-modified`; remove only manifest-owned orphans; prove repeat update and exact uninstall. |
| 11 | `FORGE-107` | feature-forge | OPEN | `FORGE-101`–`FORGE-106` | Add schema/resource/drop/migration/drift/version/tarball gates and clean-source checks; run the full feature-forge gate. |
| 12 | `RAUF-301` | rauf | OPEN | `RAUF-204` | Correct provider/preset/telemetry/architecture/install/plugin/role/failure docs and add `[Unreleased]` release notes based only on tested behavior. |
| 13 | `FORGE-201` | feature-forge | OPEN | `FORGE-107` | Replace legacy no-skills-loader docs; document plugin-first/direct installs, invocation names, roots, migration conflicts, diagnostics, and uninstall; update `[Unreleased]`. |
| 14 | `RAUF-302` | rauf | OPEN | `RAUF-301` | From clean state run `pnpm gate`, sandbox, compiled provider listing/mock loop, and binary/npm content preflight. |
| 15 | `FORGE-202` | feature-forge | OPEN | `FORGE-201` | Regenerate, run `bash scripts/validate.sh`, installer prepack and `npm pack --dry-run`, verify Copilot contents, remove `installer/adapters/`, and rerun the clean gate. Closes G3 with `RAUF-302`. |
| 16 | `INT-001` | shared external fixture | OPEN | G3 | Build a repeatable clean fixture outside both repos with pre-existing user instructions/agents and one named owner. |
| 17 | `INT-002` | shared | OPEN | `INT-001` | Test exact packed candidates through plugin and direct install/update/migration/conflict/uninstall lifecycles with no user loss or orphaned owned files. |
| 18 | `INT-003` | shared | OPEN | `INT-002` | In CLI, VS Code, and Agent Host prove native discovery and all feature-forge/rauf capability boundaries. Closes G4. |
| 19 | `INT-004` | shared | OPEN | G4 | Run packaged integrated success: feature-forge backlog, detached Copilot rauf loop, stable JSON polling, child edit/verify/signal, rauf-owned state and commit. |
| 20 | `INT-005` | shared | OPEN | `INT-004` | Run needs-human, answer injection, resume with identical provider/model policy, and eventual completion without interactive hangs. |
| 21 | `INT-006` | shared | OPEN | `INT-004` | Exercise model/auth/path/commit/push/timeout/cancel/malformed-stream cleanup and prove recoverability, containment, no false signal, and no secret leakage. |
| 22 | `INT-007` | shared | OPEN | `INT-004`–`INT-006` | Repeat required success/resume flows from Copilot CLI, VS Code, and Agent Host using the approved detached boundary. Closes G5. |
| 23 | `REL-001` | rauf | OWNER | G5 | With explicit approval, merge/release rauf through its owner-gated process and verify live Copilot artifacts. |
| 24 | `REL-002` | feature-forge | OPEN | `REL-001` | Advance `RAUF_PIN`, install hint, docs/tests, compatibility, generated adapters, version, and changelog through a green PR. |
| 25 | `REL-003` | shared | OPEN | `REL-002` | Repeat packaged G4 plus success/resume tests against the live rauf coordinate. |
| 26 | `REL-004` | feature-forge | OWNER | `REL-003` | With explicit approval, merge/release feature-forge manually and verify npm version/dist-tag/content/install. Closes G6. |

## Clarified contracts discovered during review

1. The current feature-forge `adapters/copilot/plugin.json` is accepted by Copilot but has no Agent
   Plugins 1.0 `$schema`; it must be called the legacy Copilot plugin format until `FORGE-101`
   deliberately migrates and proves a 1.0 layout.
2. `CopilotCliProvider` intentionally uses `--no-custom-instructions`. `RAUF-203` must not remove
   this isolation. Standalone `AGENTS.md` discovery and iteration-child prompt injection are two
   separate acceptance tests.
3. `.rauf/RAUF.md` currently mixes rauf-owned and user-owned content without a complete update/
   uninstall boundary. `RAUF-203` must define and migrate that boundary before claiming ownership
   safety.
4. The current rauf operator bundle still has agent-to-skill and host-neutral delegation residuals;
   `RAUF-202R` owns them instead of silently treating `RAUF-202` or packaging as complete.
5. `FORGE-106` follows fresh-layout proof (`FORGE-105`) because migration must verify the new layout
   before deleting any legacy-owned content.

## Evidence receipt required for runtime claims

Store sanitized receipts under `plans/copilot-adaptation/evidence/`. Every receipt must include:

- task ID and date;
- repository commit or exact dirty-tree diff identity;
- OS, architecture, WSL/native status, and product versions;
- exact command and sanitized prompt/fixture;
- expected result and actual result;
- relevant file hashes or before/after assertions;
- cleanup performed and registry/worktree state afterward;
- secrets explicitly excluded.

A summary in this tracker links to the receipt; it does not replace it.

## Session protocol

### Start

1. Read both repositories' `AGENTS.md` files.
2. Read this tracker, `README.md`, and the active task definition in the unified/source plan.
3. Run in both repositories:

   ```bash
   git status --short --branch
   git diff --check
   git diff --cached --name-only
   git fetch --all --prune
   ```

4. Confirm branch names and inspect divergence from the tracked remote. Never discard pre-existing
   changes.
5. Confirm every file linked by the active task is tracked with `git ls-files`; otherwise keep
   `TRACK-001` active.
6. State one falsifiable hypothesis and one focused check before editing.

### Work

- Complete one bounded task at a time in ledger order.
- Run the narrow check immediately after the first substantive edit.
- Keep one writer per repository/worktree.
- Update generated output only through its generator.
- Do not infer runtime behavior from schemas, file presence, or another harness.
- Do not begin a dependent task when an exit criterion is red or unsupported.

### Close

1. Run focused checks, the owning repository gate when the task/phase requires it, and
   `git diff --check` in both repositories.
2. Remove disposable fixtures, copied package trees, temporary plugins, and secrets.
3. Add/update the exact evidence receipt.
4. Update this row's state/evidence, the next cursor, unified task checkbox/evidence, and root
   `STATUS.md` when the phase or material repository summary changed.
5. Verify required plan/evidence files are tracked and intended branch changes are committed and
   pushed before claiming fresh-clone durability.
6. Record blockers precisely. Never mark a task done from narrative progress alone.
7. Never publish, tag, dispatch a release, or merge without the explicit owner action required by
   repository policy.

## Session receipts

| Date | Cursor | Result | Repository heads | Evidence / next cursor |
| --- | --- | --- | --- | --- |
| 2026-08-24 | `TRACK-001` | Tracker created after complete seven-file plan audit; newly added source/evidence files are present locally but still require Git tracking and a pushed commit for fresh-clone durability. | feature-forge `4cbd7e7`; rauf `02f8e67` | Continue `TRACK-001`, then `RAUF-202R`. |
| 2026-08-25 | `TRACK-001` | Recovered the missing runtime contract through minimal disposable Copilot CLI 1.0.80 probes against rauf `02f8e67`; recorded exact prompts, argv, hashes, schema-v1 status JSON, tool denial, cleanup, and clean worktree/registry state. Reconciled stale cursor and legacy-versus-1.0 claims; the planning milestone was committed/pushed and read from a fresh clone. | feature-forge `bed40ca`; rauf `02f8e67` | `TRACK-001` done; continue `RAUF-202R`. |
| 2026-08-25 | `RAUF-202R` | Added fail-loud required-skill composition for both Copilot operator agents, replaced portable `Task tool` wording, regenerated Codex/Copilot/Pi outputs, retained D7 plugin-only topology, and runtime-proved composed reviewer/driver rules on Copilot CLI 1.0.80. Full clean-home gate passed 2,188 package tests plus 91 script tests; exact receipt and cleanup are durable. | feature-forge tracker milestone on `docs/copilot-g2-contract`; rauf `4668553` | `RAUF-202R` done; continue `RAUF-203`. |
