# STATUS — feature-forge (living source of truth)

This is the **single canonical status document** for feature-forge. Dated `plans/HANDOFF-*.md`
files are historical snapshots that rot; this file is kept current. When a piece of work lands,
update the relevant section here rather than writing a new dated handoff.

_Last updated: 2026-07-10._

## Current release

| | Version | Source of truth |
|---|---|---|
| Plugin | **0.12.4** | `.claude-plugin/plugin.json` (+ `marketplace.json`, gemini ext — synced) |
| Installer | **0.2.9** | `installer/package.json` (independent version line) |
| npm | **`@garygentry/feature-forge@0.2.9`** (`latest`) | published via `npm-publish.yml` |
| Commit | `c489e5d` — `chore(release): feature-forge 0.12.4 + installer 0.2.9 (#109)` | |

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

## Open issues

| # | Title (short) | Status / plan |
|---|---|---|
| #99 | forge-5-loop circuit-breaks on Claude.ai remote (root env) — rauf's `--dangerously-skip-permissions` refused as root | **Fix planned** — auto-set `IS_SANDBOX=${IS_SANDBOX:-1}` at loop launch when running as root + one-line note + doctor check. Durable rauf-side fix tracked separately (rauf repo). |
| #92 | Stage-boundary state-machine hygiene: currentStage semantics (O1), stage-entry guard (O2), structured cross-stage notes (O3) | **Dedup-audit then implement delta** — much of the mechanism (`stageEntry.status` enum, `next_stage()`) already exists; confirm the real remaining delta before editing. O2 may split to a follow-up PR. |
| #91 | forge-1-prd → forge-2-tech served stale prior-stage context (likely host session-isolation) + latent stage-boundary hygiene | **Close with note** — the in-scope hygiene part (O1/O2/O3) is subsumed by #92; the stale-context root cause is host-level session isolation, out of feature-forge's control. |
| #90 | Emit a "tooling feedback" prompt into scaffolded repos | **Fix planned** — add a static "Tooling feedback" section to forge-bootstrap hygiene templates (outside `rauf:managed` markers). |
| #69 | Context/session management optimization — analysis & future PRD input | **Close with note** — already delivered as `specs/context-management/CANON.md`; point future auto-verify/orchestrator PRDs at it. |

## Deferred / optional (not scheduled)

- **Epic-backflow Phase 3** — automated composite `move-boundary`/`split` mutators. Design in
  `plans/DESIGN-epic-backflow.md`; Phases 1–2 shipped in 0.12.4.
- **forge-5-loop exit → stage-exit migration (Option B)** — the loop's bespoke post-loop exit
  blocks converged onto scripted `stage-exit`. Low value; loop is at its 300-line body cap.
  (The user-facing win — copyable next-command — was already captured via Option A in 0.12.4.)
- **Plugin-QA remediation** — findings + remediation on disk (`plans/archive/*-plugin-qa.md`),
  never executed. 1 High + ~16 Med, 7 chunks A–G.
- **Remote e2e retest** — of the latest publish (`plans/remote-retest-checklist.md`). Needs a
  Claude.ai remote / root env; still owner's to run.

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
