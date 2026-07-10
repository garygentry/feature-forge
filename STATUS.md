# STATUS — feature-forge (living source of truth)

This is the **single canonical status document** for feature-forge. Dated `plans/HANDOFF-*.md`
files are historical snapshots that rot; this file is kept current. When a piece of work lands,
update the relevant section here rather than writing a new dated handoff.

_Last updated: 2026-07-10._

## Current release

| | Version | Source of truth |
|---|---|---|
| Plugin | **0.12.5** | `.claude-plugin/plugin.json` (+ `marketplace.json`, gemini ext — synced) |
| Installer | **0.2.10** | `installer/package.json` (independent version line) |
| npm | **`@garygentry/feature-forge@0.2.10`** (`latest`) | published via `npm-publish.yml` |
| Commit | `chore(release): feature-forge 0.12.5 + installer 0.2.10` | |

CHANGELOG `[Unreleased]` is **empty**; working tree clean.

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

| # | Title (short) | Status / plan |
|---|---|---|
| #113 | Stage-entry idempotency guard across the 5 authoring skills (#92 O2 follow-up) | **Open, not scheduled** — the invasive part of #92 (touches all 5 authoring skills' Step 1; `forge-0-epic` at the 300-line cap → needs a shared helper + reference moves). Split out from #92 so it didn't hold the 0.12.5 release. |

_All of #99, #90, #92 (O1+O3) shipped in 0.12.5. #91 and #69 closed with notes (see below)._

## Deferred / optional (not scheduled)

- **Epic-backflow Phase 3** — automated composite `move-boundary`/`split` mutators. Design in
  `plans/DESIGN-epic-backflow.md`; Phases 1–2 shipped in 0.12.4.
- **forge-5-loop exit → stage-exit migration (Option B)** — the loop's bespoke post-loop exit
  blocks converged onto scripted `stage-exit`. Low value; loop is at its 300-line body cap.
  (The user-facing win — copyable next-command — was already captured via Option A in 0.12.4.)
- **#92 O2 — stage-entry idempotency guard** (issue #113). See Open issues above.
- **Plugin-QA remediation** — findings + remediation on disk (`plans/archive/*-plugin-qa.md`),
  never executed. 1 High + ~16 Med, 7 chunks A–G.
- **Remote e2e retest** — of the latest publish (`plans/remote-retest-checklist.md`). Needs a
  Claude.ai remote / root env; still owner's to run. **Also clears the pending end-to-end
  verification of the #99 root/sandbox fix** (landed with unit-level proof only — a real remote
  root loop run would confirm `IS_SANDBOX` resolves the circuit-break).

## Explicitly won't build

- **Chunk 5a — last-output Stop-hook sentinel guard.** Resolved **DO NOT BUILD** (2026-07-10):
  a local dogfood of 0.12.2 hit 3/3 HELD on every scripted stage-exit — no post-sentinel drift.
  Only re-open if a future **remote** run shows real post-sentinel drift (that would implicate
  the remote harness, not the skill). Context: `HANDOFF-next-session.md`.

## Release mechanics (reference)

No git tags. A release = CHANGELOG heading + 3 synced version fields + independent installer
bump + manual npm dispatch. Full mechanics (gemini via `GEMINI_EXTENSION_VERSION`+regen,
fixture refresh with `command cp -f`, `gh workflow run npm-publish.yml`, `npm@11` provenance
pin): `plans/HANDOFF-stabilization-continuation.md` → "Release mechanics".
