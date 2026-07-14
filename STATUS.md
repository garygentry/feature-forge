# STATUS — feature-forge (living source of truth)

This is the **single canonical status document** for feature-forge. Dated `plans/HANDOFF-*.md`
files are historical snapshots that rot; this file is kept current. When a piece of work lands,
update the relevant section here rather than writing a new dated handoff.

_Last updated: 2026-07-14 (0.12.8 / installer 0.2.13 published)._

## Current release

| | Version | Source of truth |
|---|---|---|
| Plugin | **0.12.8** | `.claude-plugin/plugin.json` (+ `marketplace.json`, gemini ext — synced) |
| Installer | **0.2.13** | `installer/package.json` (independent version line) |
| npm | **`@garygentry/feature-forge@0.2.13`** (`latest`) | published via `npm-publish.yml` |
| Commit | `chore(release): feature-forge 0.12.8 + installer 0.2.13` (#141) | |

CHANGELOG `[Unreleased]` is **empty**. **Tracker is empty, no open PRs.** Nothing is queued for a
next release; deferred/optional items are listed below.

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
- **0.12.8** (#141) — batched four-change publish:
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
    the flat dir, manifest-adds if absent. Re-entrant; relocate-then-manifest ordering.

## Open issues

_GitHub tracker (`gh issue list --state open`) is **empty**._

All of **#121 / #122 / #123 / #124 / #126 / #132 / #135** are closed — #123 was a duplicate of #122;
the rest auto-closed with PRs #134/#137/#138/#139. Next action is purely the batched 0.12.8 publish.

## Deferred / optional (not scheduled)

- **Epic-backflow — automated composite `move-boundary`/`split` mutators.** Design in
  `plans/DESIGN-epic-backflow.md`; Phases 1–2 shipped in 0.12.4. The **`adopt-feature` recovery**
  command (the #126 "Phase 3" split-brain reconciler) shipped in PR #139; these remaining
  composite kinds (moving a frozen contract boundary, splitting a feature) stay guided-manual for now.
  _Triaged 2026-07-14: no triggering evidence, remains deferred (trigger: guided-manual
  `move-boundary`/`split` proven clunky in real epic use, **or** the owner plans an epic needing it).
  Checked all real epics — `consumption-data-refresh/{data-views,data-refresh}`,
  `consumption/{data-enhancement,data-views,data-refresh}`, `rauf/agent-agnostic` — none has recorded
  a single `changeRequest`, so guided-manual has not been exercised at all._
- **Remote e2e retest** — of the latest publish (now `@garygentry/feature-forge@0.2.13`;
  `plans/remote-retest-checklist.md`). Needs a Claude.ai remote / root env; still owner's to run.
  **Also clears the pending end-to-end verification of the #99 root/sandbox fix** (landed with
  unit-level proof only — a real remote root loop run would confirm `IS_SANDBOX` resolves the
  circuit-break). 0.12.8 is a good candidate to retest against since it exercises the #124 completion
  hand-off and the #126 `adopt-feature` recovery on a real host (plus the still-unretested split-brain
  guard on the `forge-1-prd` mint path).

## Explicitly won't build

- **forge-5-loop exit → stage-exit migration (Option B).** Resolved **DO NOT BUILD unless drift
  appears** (2026-07-14, owner-confirmed). Converging the loop's bespoke post-loop exit onto
  scripted `stage-exit` buys code-path convergence, not user-visible behavior — the copyable
  next-command win already shipped via Option A in 0.12.4. Triage found **no drift**: the loop's
  exit is single-sourced against `references/stage-exit-protocol.md`, which owns both the standard
  block and the warm variant (the `forge-5-loop → forge-6-docs` boundary is the one place clearing
  is optional; scripted stage-exit models *cold* boundaries, so a migration would have to *extend*
  it, not just reuse it). No open/closed issue reports a loop-exit inconsistency. Loop is also at
  its 300-line body cap. Re-open only if (a) the bespoke loop exit drifts from the scripted one and
  causes a real user-hit inconsistency, or (b) a stage-exit semantics change makes two paths
  demonstrably costly. Context: `plans/HANDOFF-triage-deferred-composite-and-loop-exit.md`. Distinct
  from **chunk 5a** below (that is the Stop-hook sentinel guard, not code-path convergence).
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
