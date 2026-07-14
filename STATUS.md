# STATUS — feature-forge (living source of truth)

This is the **single canonical status document** for feature-forge. Dated `plans/HANDOFF-*.md`
files are historical snapshots that rot; this file is kept current. When a piece of work lands,
update the relevant section here rather than writing a new dated handoff.

_Last updated: 2026-07-14._

## Current release

| | Version | Source of truth |
|---|---|---|
| Plugin | **0.12.7** | `.claude-plugin/plugin.json` (+ `marketplace.json`, gemini ext — synced) |
| Installer | **0.2.12** | `installer/package.json` (independent version line) |
| npm | **`@garygentry/feature-forge@0.2.12`** (`latest`) | published via `npm-publish.yml` |
| Commit | `chore(release): feature-forge 0.12.7 + installer 0.2.12` (#129) | |

CHANGELOG `[Unreleased]` carries four merged-but-unpublished changes — the **shared-reference fan-out**
(#122/#132, PR #134), the **impl-verify runnability check** (#135/#121, PR #137), the **completion
hand-off** (#124, PR #138), and the **scripted adopt-into-epic** command (#126, PR #139). All need a
publish (**0.12.8 / installer 0.2.13**) to reach npm users — cut one batched release. **Tracker is empty.**

## Shipped recently (0.12.x)

- **0.12.0** (#98) — stabilization chunks 1/2a/3/4 (cache-install root fix, doctor,
  discover-feature + anti-fabrication, scripted stage-exit w/ sentinel) + navigator/rauf-pin.
- **0.12.1** (#100) — fixed `forge-verifier` self-dispatch (read-only leaf must exclude Agent/Task).
- **0.12.2** (#104) — chunk 2b (prelude leads with `${CLAUDE_PLUGIN_ROOT:-}`), 5b (navigator
  exit convergence: one `verifyGate`, present-once), 5c/6 (`discover-feature --all` + branch
  reconciliation for imposed hosted branches).
- **0.12.3** (#105) — copyable next-stage command on stage exits + 0.12.x docs coverage.
- **0.12.4** (#109) — copyable next-command on loop exits (Item 1) + epic-backflow Phase 1
  (record + route epic change requests, #107) and Phase 2 (surface open requests: navigator ⚠️
  + forge-verify CHECK-E09, #108).
- **0.12.5** — issue-closeout batch: #99 (loop root/sandbox `IS_SANDBOX` fix, #111),
  #90 (scaffold "Tooling feedback" prompt, #112), #92 O1+O3 (state-machine hygiene:
  `currentStage` semantics + structured `deferredDecisions[]`, #114). Docs: canonical
  `STATUS.md` (#110).
- **0.12.6** (#118) — #113 (stage-entry idempotency guard O2, deferred from #92):
  `forge-1-prd`..`forge-4-backlog` classify re-entry (fresh / interrupted / re-authoring) and gate
  resume-vs-restart instead of blindly re-authoring; entry stamps `status: "in-progress"` +
  `startedAt` + `currentStage` at Step 1; new `## Stage-Entry Guard` in
  `references/shared-conventions.md`. Also **formally closed the plugin-QA audit** (doc-only #117):
  all FINDINGS D1–D8 verified CLOSED across 0.12.x, no code residual — matrix
  `plans/archive/CLOSEOUT-plugin-qa.md`.
- **0.12.7** (#129) — **split-brain-epic guard** (#125): `forge-1-prd` **Mint Guard** refuses to
  forge a known epic member as a detached standalone (fires on both the exit-1 `not-found` and the
  exit-2 clean-branch `specs dir not found` triggers), with a `--force-standalone` escape;
  `check-epic-base` + **Epic-Member Base Guard** (`forge-1-prd`..`forge-4-backlog`) refuse to author
  a nested member on a branch lacking the epic manifest; navigator flags a standalone completion
  matching an epic member on another branch; `discover-feature` candidates carry `epic`/`isEpicMember`.
  Epic **branch model** documented positively (README/integration/architecture) +
  `docs/recovery-detached-epic-member.md`. Shipped via #127 (guard suite) + #128 (exit-2 trigger fix,
  found by a two-branch dogfood).

## In flight — merged to main, awaiting the 0.12.8 release

Four changes are in CHANGELOG `[Unreleased]` with no version bump yet — cut one batched
**0.12.8 / installer 0.2.13** to publish them all (release mechanics below).

- **PR #134** (#122/#132) — build-time **fan-out** of cited bundle-root shared references into each
  citing skill's local `references/` (`build-adapters.py` only, no skill-body changes; +260 fanned files).
- **PR #137** (#135, fixes #121) — impl-verify **runnability check**: new `### Runnability` checklist
  section with `CHECK-I21` (optional `smokeCommand` smoke) + `CHECK-I22` (static non-test-caller
  heuristic), both degrading gracefully; `smokeCommand` threaded through schema/init/bootstrap/tech/README.
- **PR #138** (#124) — completion **hand-off**: navigator §3b + forge-6-docs exit route an epic member to
  the next actionable member and a standalone to a new-feature offer instead of dead-ending.
- **PR #139** (#126) — scripted **`adopt-feature`** recovery (epic-backflow **Phase 3**):
  `epic-manifest.py adopt-feature {epic} {feature}` relocates a detached standalone into
  `specs/{epic}/{feature}/`, merges state preserving the stub's `epic`/`branch` back-pointers, removes
  the flat dir, manifest-adds if absent. Re-entrant; relocate-then-manifest ordering; recovery doc now
  leads with it. `tests/test_adopt_feature.py` (8 cases).

## Open issues

_GitHub tracker (`gh issue list --state open`) is **empty**._

All of **#121 / #122 / #123 / #124 / #126 / #132 / #135** are closed — #123 was a duplicate of #122;
the rest auto-closed with PRs #134/#137/#138/#139. Next action is purely the batched 0.12.8 publish.

## Deferred / optional (not scheduled)

- **Epic-backflow — automated composite `move-boundary`/`split` mutators.** Design in
  `plans/DESIGN-epic-backflow.md`; Phases 1–2 shipped in 0.12.4. The **`adopt-feature` recovery**
  command (the #126 "Phase 3" split-brain reconciler) shipped in PR #139; these remaining
  composite kinds (moving a frozen contract boundary, splitting a feature) stay guided-manual for now.
- **forge-5-loop exit → stage-exit migration (Option B)** — the loop's bespoke post-loop exit
  blocks converged onto scripted `stage-exit`. Low value; loop is at its 300-line body cap.
  (The user-facing win — copyable next-command — was already captured via Option A in 0.12.4.)
- **Remote e2e retest** — of the latest publish (now `@garygentry/feature-forge@0.2.12`;
  `plans/remote-retest-checklist.md`). Needs a Claude.ai remote / root env; still owner's to run.
  **Also clears the pending end-to-end verification of the #99 root/sandbox fix** (landed with
  unit-level proof only — a real remote root loop run would confirm `IS_SANDBOX` resolves the
  circuit-break). 0.12.7 is a good candidate to retest against since it touches the `forge-1-prd`
  mint path (the split-brain guard was dogfooded locally but not on a remote host).

## Explicitly won't build

- **Chunk 5a — last-output Stop-hook sentinel guard.** Resolved **DO NOT BUILD** (2026-07-10):
  a local dogfood of 0.12.2 hit 3/3 HELD on every scripted stage-exit — no post-sentinel drift.
  Only re-open if a future **remote** run shows real post-sentinel drift (that would implicate
  the remote harness, not the skill). Context: `HANDOFF-next-session.md`.
- **Plugin-QA G5 — extra advisory linters.** Resolved **DO NOT BUILD** (2026-07-11, owner
  discretion): `advisory-lint.yml` already carries non-blocking markdownlint + lychee. Adding
  eslint/prettier/tsc/mypy is advisory-only gold-plating that adds green-keeping surface for no
  correctness gain. Re-open only if style/type/link rot becomes a real problem. Context:
  `plans/archive/CLOSEOUT-plugin-qa.md`.

## Release mechanics (reference)

No git tags. A release = CHANGELOG heading + 3 synced version fields + independent installer
bump + manual npm dispatch. Full mechanics (gemini via `GEMINI_EXTENSION_VERSION`+regen,
fixture refresh with `command cp -f`, `gh workflow run npm-publish.yml`, `npm@11` provenance
pin): `plans/HANDOFF-stabilization-continuation.md` → "Release mechanics".
