# STATUS — feature-forge (living source of truth)

This is the **single canonical status document** for feature-forge. Dated `plans/HANDOFF-*.md`
files are historical snapshots that rot; this file is kept current. When a piece of work lands,
update the relevant section here rather than writing a new dated handoff.

_Last updated: 2026-07-11._

## Current release

| | Version | Source of truth |
|---|---|---|
| Plugin | **0.12.5** | `.claude-plugin/plugin.json` (+ `marketplace.json`, gemini ext — synced) |
| Installer | **0.2.10** | `installer/package.json` (independent version line) |
| npm | **`@garygentry/feature-forge@0.2.10`** (`latest`) | published via `npm-publish.yml` |
| Commit | `chore(release): feature-forge 0.12.5 + installer 0.2.10` | |

CHANGELOG `[Unreleased]` carries **#113 (stage-entry idempotency guard, O2)** — merged to
`main` (PR #116), **awaiting the next batched release** (no version bump yet). Working tree clean.

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

## Open issues

_None._ The GitHub tracker is empty (`gh issue list --state open` → 0).

_All of #99, #90, #92 (O1+O3) shipped in 0.12.5; #92 O2 (#113) shipped to `main` and sits in
`[Unreleased]` pending release. #91 and #69 closed with notes (see below)._

## Pending release (on `main`, not yet published)

- **#113 — stage-entry idempotency guard (O2, deferred from #92).** `forge-1-prd`..`forge-4-backlog`
  classify re-entry (fresh / interrupted / re-authoring) and gate resume-vs-restart instead of
  blindly re-authoring; entry stamps `status: "in-progress"` + `startedAt` + `currentStage` at
  Step 1. New `## Stage-Entry Guard` block in `references/shared-conventions.md` (supersedes the
  dormant Crash Recovery). `forge-0-epic` unchanged (manifest dispatch already gates re-entry).
  PR #116. No schema change. Adapters regenerated.
- **Plugin-QA close-out (doc-only).** The whole-repo plugin-QA review (audited @`236725f`) is
  **formally closed** — every FINDINGS item D1–D8 + coverage §7 walked item-by-item against `main`
  @ `ff3d7c1` (7 parallel reviewers, one per REMEDIATION chunk A–G), all **CLOSED** with `file:line`
  evidence. The one **High** (forge-verify epic-member resolution) and every Medium/Low landed
  across the 0.12.x line; **no code residual**. Matrix: `plans/archive/CLOSEOUT-plugin-qa.md`;
  FINDINGS + REMEDIATION stamped CLOSED. G5 (advisory linters) → won't build (below). Diff is
  archive stamps + this file only.

## Deferred / optional (not scheduled)

- **Epic-backflow Phase 3** — automated composite `move-boundary`/`split` mutators. Design in
  `plans/DESIGN-epic-backflow.md`; Phases 1–2 shipped in 0.12.4.
- **forge-5-loop exit → stage-exit migration (Option B)** — the loop's bespoke post-loop exit
  blocks converged onto scripted `stage-exit`. Low value; loop is at its 300-line body cap.
  (The user-facing win — copyable next-command — was already captured via Option A in 0.12.4.)
- **Remote e2e retest** — of the latest publish (`plans/remote-retest-checklist.md`). Needs a
  Claude.ai remote / root env; still owner's to run. **Also clears the pending end-to-end
  verification of the #99 root/sandbox fix** (landed with unit-level proof only — a real remote
  root loop run would confirm `IS_SANDBOX` resolves the circuit-break).

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
