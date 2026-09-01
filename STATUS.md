# STATUS — feature-forge (living source of truth)

This is the **single canonical status document** for feature-forge. Dated `plans/HANDOFF-*.md`
files are historical snapshots that rot; this file is kept current. When a piece of work lands,
update the relevant section here rather than writing a new dated handoff.

_Last updated: 2026-08-31 (0.19.0 release cut — Pi forge-loop-supervisor extension (#235/#236),
loop-runner floor raise (#234), Pi post-fix verification termination fix (#237/#238), and rauf
pin advance to 0.15.0)._

## Current release

| | Version | Source of truth |
|---|---|---|
| Plugin | **0.19.0** | `.claude-plugin/plugin.json` (+ `marketplace.json`, gemini ext — synced) |
| Installer | **0.3.6** | `installer/package.json` (independent version line) |
| npm | publishing 0.3.6 | |
| Commit | this release commit | |

CHANGELOG `[Unreleased]` is empty.

### rauf coupling

`RAUF_PIN` is **`@garygentry/rauf@0.15.0`** (verified resolving on npm 2026-08-31).
0.15.0 ships Codex provider sandbox/network/approval config plus a batch of loop-runner
fixes (Pi/cursor `E2BIG` prompt delivery, review-pass retry parity, rollback-safety halt,
stale-profile detection, `--retry-blocked` backlog resolution) — none of it a capability
feature-forge's stages depend on, so `minRunnerVersion` **stays at 0.14.0** (the recovery
floor from #234); the pin now sits ahead of the floor, which `COMPATIBILITY.md` documents
as the expected shape (the floor only rises when rauf ships a surface a shipped stage
actually requires). Agents needing a *newer* rauf than the floor are recorded as prose in
`COMPATIBILITY.md`.

Note for future releases: **feature-forge CI never checks that `RAUF_PIN` resolves** — every
`os-matrix.yml` leg runs `--skip-rauf`, and `installer/test/rauf.test.ts` injects a `RegistryQuery`
seam, so no registry call happens anywhere in CI. A pin advanced to an unpublished version merges
green and only breaks real users at install time. Always confirm `npm view @garygentry/rauf version`
before advancing it.

## Shipped recently

- **0.19.0** / installer 0.3.6 (2026-08-31) — Pi `forge-loop-supervisor` extension (#235/#236:
  a first-party Pi extension launches the loop detached and wakes the session only on
  needs-human/blocked/stuck/error/completion, replacing the self-contradictory
  background-and-monitor instructions the generic contract gave Pi); loop-runner launch floor
  raised to rauf `0.14.0` (#234, matching the pin and the recovery-capability floor); Pi
  post-fix verification no longer cycles after a clean round (#237/#238); rauf pin advanced
  to `0.15.0`.
- **0.18.0** / installer 0.3.5 (2026-08-15, PR #233) — rauf pin advance to `0.14.0` (ships
  `backlog answer`) + #230 epic verify/fix branch-exit member-routing fix.
- **0.17.0** / installer 0.3.4 (2026-08-12, PR #229) — fix-sweep script for semantic
  verification fix completeness (#170); zero-prompt loop config (Track E, #153/#164); host-term
  translation of the copied reference closure (#167); several stage-exit/epic-state/notes-baton
  hardening items (Tracks C/D/G).
- **0.16.0** / installer 0.3.3 (2026-08-08, PR #206 — merged, **unpublished**) — Track B
  close-out: **loop-recovery** pipeline feature (#204: autonomous-loop recovery — decision
  records, failure clustering, topology, `resolved` outcome; closed #189–#194 #196) +
  **V-001 smokeCommand docs reconcile** (#205). The 2026-08-08 branch/issue reconciliation
  (13 branches deleted, 6 issues closed, #192 rescoped) preceded this cut.
- **0.15.0** / installer 0.3.2 (2026-08-05) — reconciliation release carrying **three feature
  waves that had accumulated on main unreleased**:
  - **stage-exit-coverage epic + P1 remediation (#184)** — scripted stage exits now cover all
    nine pipeline-advancing skills (`stage-exit` enum widened to loop/docs, `forge-verify`/
    `forge-fix` termini with `--served-stage` rejoin routing, epic edit-mode member routing,
    durable `auto-verify-pending` debt, typed branch outcomes, `state-verify`). Closes the
    gaps behind #163/#172/#175/#176 (issue closeout itself is Track S1).
  - **Anti-churn verify-loop hardening (#185)** — R-05 severity floor, R-06 scoped re-verify +
    decision immunity, R-07 round ledger + second-red escalation, R-08 narrative rule, R-09
    entry-gate doctrine, GATE-P2 `escalation` eval scenario.
  - **verify-test-debt (#198)** — 16-item rauf run paying down verification-test debt
    (capability/mutation guard rewrites, coverage backfill, brittleness batch), the
    `validate-traceability.py` foreign-id allowlist, and two state-verb hardenings
    (`state-complete --version ≥ 1`, `state-artifact --path` containment). Docs stage
    deliberately skipped → #197.
  - Plus the S0 reconcile: retroactive `[0.14.0]` CHANGELOG cut + backfilled #184/#185
    entries, deny-by-default `**/.rauf/*` gitignore (#195), and the AGENTS.md
    release-checklist note.
- **0.14.0** / installer 0.3.1 (2026-07-30, PR #177/#178) — **context-efficiency batch
  (R1–R6)**: verification checklists split per verify mode, navigator's process-overview read
  gated, runner contract split into always-loaded + agent-conditional halves, seven `state-*`
  verbs retiring hand-written `.pipeline-state.json` edits (R4), `effective-config` resolving
  the `loopRunner` block (R5), drift guards over every split surface. (Released without a
  CHANGELOG cut — repaired in 0.15.0.)
- **0.13.0** / installer 0.3.0 — **Pi (`@earendil-works/pi-coding-agent`) as the 6th supported
  agent.** `build-adapters.py` emits `adapters/pi/` as a self-contained Pi package: generated
  skills, package metadata, and a vendored `AskUserQuestion` compatibility extension (a patched
  snapshot of `@juicesharp/rpiv-ask-user-question` 2.1.0, MIT) so the forge interview renders in
  Pi's TUI instead of degrading to prose. forge's custom agents are dispatchable via a
  `pi-subagents` manifest key with frontmatter translated into that schema (so `forge-verifier`'s
  read-only contract is tool-enforced), the installer accepts `-a pi` with scope-correct
  destinations plus an agents `mirror` placement, and `forge-root.sh` discovers Pi installs.
  Real agent-loaded code now lives under `adapter-src/<agent>/` and is verified in CI by its own
  `verify` script. Also advances `RAUF_PIN` to `@garygentry/rauf@0.14.0` — see the coupling note
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

## Hardening pass (Aug 2026)

The active multi-session program: all 28 issues open as of 2026-08-05 were triaged into
tracks (strategy + rationale in the local `plans/PLAN-hardening-2026-08.md`; durable
cross-session state is GitHub issues + the `hardening/*` milestones created in S1 + this
section, updated at every session close).

| Track | Scope | Status |
|---|---|---|
| **S0** — land, reconcile, release 0.15.0 | verify-test-debt PR, CHANGELOG surgery, #195, this refresh, 0.15.0, AGENTS.md process note | **done** (2026-08-05) |
| **S1** — issue closeout + two small fixes | verify-and-close #163 #172 #175 #176 with evidence; rescope #181; record #170/#171 split; fix #183; create milestones | **done** (2026-08-05) |
| **B** — forge-5-loop recovery (pipeline feature `loop-recovery`) | #196 (keystone decision record) #193 #192 #189 #190 #191 #194; release 0.16.0 at close | **done** (2026-08-08: PR #204 merged, 0.16.0 cut via #206; #192 rescoped → Track C wiring fix) |
| **C** — contracts & state-integrity batch (direct PR) | #186 #187 #188 #182 #181-remainder #166 (+ rescoped #192) | **done** (2026-08-09: batch 1 PRs #216–#218 (#192 Step-4c unconditional recovery, #186 Stage Review Gate block, #187 forge-4 return contract); batch 2 PRs #219–#222 (#188 caller-side resumption contract, #181 epic-state schema + conformance, #182 downstream notes reads + overwrite settled, #166 set-charter mutator). All seven issues closed citing their PRs. Unreleased — in `[Unreleased]` for the next cut) |
| **D** — skip-docs (hand-sequenced 4-PR series) | #202 recovery → #197 mechanism → #203+#165 guard/config → #173 re-gate | **done** (2026-08-09: PRs #211–#214 merged, all five issues closed. `state-skip` verb + `docsStageEntry` schema + `docsStage` config + `_SKIP_PROTECTED_PRIOR` demotion guard + `docsStatus`-gated epic-doc offer. Unreleased — in `[Unreleased]` for the next cut) |
| **E** — zero-prompt loop config (direct PR) | #153 #164 (`loopRunner.reviewMode`/`.agentMode`); 0.17.0 with D | **done** (2026-08-10: PR #224 merged — `reviewMode` (`prompt\|always\|never`) gates the Run-mode question, `agentMode` (`prompt\|auto`) gates the agent pick; defaults byte-identical to today; under `auto` the probe/verdict/alias-guard still run; retry-blocked keeps a narrow situational prompt under `always`/`never`; pinned by `tests/test_zero_prompt_loop_config.py`. Both issues closed. Unreleased — in `[Unreleased]` for the 0.17.0 cut) |
| **F** — verify fix-sweeps (pipeline feature) | #170 mechanical milestone, then #171 semantic | **done** (2026-08-12: #170 fix-sweep script via PR #228, #171 semantic sweep via same PR; both shipped in 0.17.0. Both issues closed) |
| **G** — decisions & standalone | #180 single-writer decision; #167 adapter host-term translation (last) | **done** (2026-08-08: #180 decided + recorded via PR #209 — single writer assumed, detection-not-locking, `references/decisions/single-writer-threat-model.md`; unblocks Track C. 2026-08-10: #167 via PR #226 — copied reference markdown is host-term translated per agent in the self-containment pass (Pi `/new`/`/skill:`/`--host pi`, others host-neutral, Claude byte-verbatim; JSON + exempt meta-docs untouched); host-neutrality guard now scans references and covers Pi. Unreleased — in `[Unreleased]` for the next cut) |

Sequencing: S1 next; B before D (both widen `EXIT_OUTCOMES`); E after D (shared schema
surfaces); #167 deliberately last (pure generator churn). Standing constraints for every
session: body caps (forge-verify 299/300, forge-0-epic 297, forge-5-loop 296 — prose goes
to `references/`), adapters regen on every canon edit, schema + verb + conformance test for
any new state surface (the R4 pattern), `bash scripts/validate.sh` green before every commit.

## Open issues

_0 open as of 2026-08-15. All 28 hardening-pass issues closed: Phase 1 (#201/#180),
Phase 2 (#202/#197/#203/#165/#173), Phase 3 / Track C (#192/#186/#187/#188/#181/#182/#166),
Phase 4 / Track E (#153/#164), Phase 5 (#167/#170/#171), plus Tracks S0/S1/B. Post-program
fix #230 also closed (PR #231). Hardening program COMPLETE._

One known non-blocking follow-up, untracked (no issue filed):

- **`installer/tsconfig.json` `include` is `["src"]`**, so the installer's `.ts` tests are never
  type-checked — they only run under Node's native type stripping. A type error in a test file
  passes CI silently.

## Scheduled

Nothing outside the hardening pass. The previously scheduled **forge-5-loop exit →
stage-exit migration (Option B)** — reclassified on 2026-07-29 after its re-open trigger
fired three times (#172 #175 #176) — **shipped as the stage-exit-coverage epic (#184)**,
released in 0.15.0. Original triage context:
`plans/HANDOFF-triage-deferred-composite-and-loop-exit.md`. Still distinct from **chunk 5a**
under "Explicitly won't build" (the Stop-hook sentinel guard), whose own re-open condition —
a remote run showing post-sentinel drift — has **not** fired.

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
