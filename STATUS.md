# STATUS — feature-forge (living source of truth)

This is the **single canonical status document** for feature-forge. Dated `plans/HANDOFF-*.md`
files are historical snapshots that rot; this file is kept current. When a piece of work lands,
update the relevant section here rather than writing a new dated handoff.

_Last updated: 2026-07-27 (0.13.0 / installer 0.3.0 published to npm)._

## Current release

| | Version | Source of truth |
|---|---|---|
| Plugin | **0.13.0** | `.claude-plugin/plugin.json` (+ `marketplace.json`, gemini ext — synced) |
| Installer | **0.3.0** | `installer/package.json` (independent version line) |
| npm | **`@garygentry/feature-forge@0.3.0`** (`latest`) | published 2026-07-27 via `npm-publish.yml` (run 30324289460) |
| Commit | `chore(release): v0.13.0 / installer 0.3.0 (Pi support, rauf pin 0.13.0)` | |

CHANGELOG `[Unreleased]` is **empty** — 0.13.0 is the current section.

### rauf coupling

0.13.0 advances `RAUF_PIN` to **`@garygentry/rauf@0.13.0`** (published 2026-07-27), which is the
rauf release that ships the `--agent pi` loop preset. That coupling is load-bearing for this
release: `forge-5-loop` discovers agents by probing `rauf agents --json`, so Pi loop support is
delivered entirely by the runner — an older pinned rauf would never list `pi`. `minRunnerVersion`
deliberately stays at 0.6.0; the Pi-specific requirement is prose in `COMPATIBILITY.md`.

Note for future releases: **feature-forge CI never checks that `RAUF_PIN` resolves** — every
`os-matrix.yml` leg runs `--skip-rauf`, and `installer/test/rauf.test.ts` injects a `RegistryQuery`
seam, so no registry call happens anywhere in CI. A pin advanced to an unpublished version merges
green and only breaks real users at install time. Always confirm `npm view @garygentry/rauf version`
before advancing it.

## Shipped recently

- **0.13.0** / installer 0.3.0 — **Pi (`@earendil-works/pi-coding-agent`) as the 6th supported
  agent.** `build-adapters.py` emits `adapters/pi/` as a self-contained Pi package: generated
  skills, package metadata, and a vendored `AskUserQuestion` compatibility extension (a patched
  snapshot of `@juicesharp/rpiv-ask-user-question` 2.1.0, MIT) so the forge interview renders in
  Pi's TUI instead of degrading to prose. forge's custom agents are dispatchable via a
  `pi-subagents` manifest key with frontmatter translated into that schema (so `forge-verifier`'s
  read-only contract is tool-enforced), the installer accepts `-a pi` with scope-correct
  destinations plus an agents `mirror` placement, and `forge-root.sh` discovers Pi installs.
  Real agent-loaded code now lives under `adapter-src/<agent>/` and is verified in CI by its own
  `verify` script. Also advances `RAUF_PIN` to `@garygentry/rauf@0.13.0` — see the coupling note
  above. A bare `install`/`update` now targets Pi wherever detected; one known issue is documented
  (a *damaged* Claude install alongside a healthy Pi install can resolve to the Pi bundle).
  CI's installer leg moved **Node 20 → 22** in the same release: on Node 20 the installer suite ran
  **0 of its 182 tests** (and couldn't load Pi's SDK at all) while still reporting green. Don't
  lower it back.
- **0.12.9** / installer 0.2.14 (#161) — epic/backlog verification batch: cross-member shared-state
  test coupling detection `CHECK-E10` (#144), generated-artifact freshness vs. `testCommand`
  `--check` gates (#145), dev-runtime smoke guidance + heavy-bootstrap heuristic `CHECK-I23`
  (#149), contradictory-lifecycle backlog heuristic `CHECK-B27` (#150), `--review` as
  forge-5-loop's recommended default run mode (rauf only), unknown `forge-verify-*` status no
  longer silently poisoning the epic rollup, authoring stages self-aborting a replayed mid-stage
  continuation, and stale/partial installs failing loudly instead of running degraded (#152).

## Shipped earlier (0.12.x)

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

_The snapshot below is as of 2026-07-14 and is **stale** — the tracker is no longer empty. Twelve
issues were filed between 2026-07-19 and 2026-07-29, mostly surfaced by dogfooding the
context-efficiency pipeline; see `plans/ROADMAP-post-context-efficiency.md` for the current
review. Four of them (#172 / #175 / #176 / #163) are the stage-exit-coverage cluster that
reclassified the item under "Scheduled" above._

All of **#121 / #122 / #123 / #124 / #126 / #132 / #135** are closed — #123 was a duplicate of #122;
the rest auto-closed with PRs #134/#137/#138/#139. The 0.13.0 / installer 0.3.0 publish is done;
no release work is outstanding.

Two known non-blocking follow-ups, untracked (no issue filed):

- **rauf's `release:prepare` doesn't regenerate `adapters/pi/package.json`.** Until it does, every
  future rauf release PR red-CIs on `pnpm pi:check` and needs a manual regen. Lives in the rauf
  repo, not here, but it gates the next `RAUF_PIN` advance.
- **`installer/tsconfig.json` `include` is `["src"]`**, so the installer's `.ts` tests are never
  type-checked — they only run under Node's native type stripping. A type error in a test file
  passes CI silently.

## Scheduled

- **forge-5-loop exit → stage-exit migration (Option B) — RECLASSIFIED, now scheduled.** This was
  triaged on 2026-07-14 as **do not build unless drift appears**, with a named re-open trigger:
  "(a) the bespoke loop exit drifts from the scripted one and causes a real user-hit
  inconsistency, or (b) a stage-exit semantics change makes two paths demonstrably costly."
  **That trigger has since fired three times**, all filed after the triage:
  - **#172** — `stage-exit` rejects `forge-6-docs`, so the skill's own text prescribes a command
    the script refuses. Four consecutive runs in one epic hand-rolled the state write, producing a
    real short-vs-full `commitHash` inconsistency and a 500-line diff from JSON round-tripping.
    This is (a) — a user-hit inconsistency caused by a hand-rolled exit.
  - **#175** — the state-aware next-stage override is gated on `stage in PRODUCTION_STAGES`, which
    excludes `forge-0-epic`, so edit-mode re-entry routes the user back to `forge-1-prd` on a
    member whose backlog is already complete.
  - **#176** — the general form: exit determinism was hardened along the linear spine where
    compliance was already easy, and left to model discretion exactly where the pipeline branches.
    `forge-verify` and `forge-fix` have **no exit block at all**.

  The 2026-07-14 finding of "no drift" was accurate **at the time** — it checked the loop exit
  against `stage-exit-protocol.md` and found them single-sourced. What it did not check, and what
  #176 reframes as the real defect, is exit **coverage**: `stage-exit --stage` accepts only
  `forge-0-epic … forge-4-backlog`, so every skill outside that enum either hand-rolls its exit or
  has none. The migration is therefore no longer "code-path convergence with no user-visible
  benefit" — it is the fix for four filed issues.

  Two things also made it cheaper than it was. `state-complete` (R4, 0.14.0) now owns the state
  write and the staleness cascade, so widening `stage-exit` is mostly a next-stage-resolution
  problem rather than a state-authoring one. And the 300-line body cap objection has a known
  buy-back (V-012: relocate the Step 2d "Run mode" paragraph into `runner-contract.md`, ~10 lines).

  Scheduled as **Phase 1** of the post-context-efficiency roadmap, sized to run through the forge
  pipeline itself. Original triage context:
  `plans/HANDOFF-triage-deferred-composite-and-loop-exit.md`. Still distinct from **chunk 5a**
  under "Explicitly won't build" (that is the Stop-hook sentinel guard, not code-path convergence),
  whose own re-open condition — a remote run showing post-sentinel drift — has **not** fired.

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
