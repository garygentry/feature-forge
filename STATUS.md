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

CHANGELOG `[Unreleased]` carries the **shared-reference fan-out** (#122/#132, PR #134 — see "In flight");
needs a publish (0.12.8 / installer 0.2.13) to reach npm users, best batched with other pending work.

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

## In flight (open PRs / just-filed)

- **PR #134** — `fix(adapters)`: **build-time fan-out** of cited bundle-root shared references into each
  citing skill's local `references/` (fixes **#122**, closes **#132**). `scripts/build-adapters.py` only,
  **no skill-body changes**; citation-driven + verbatim so the drift guard stays byte-stable; bundle-root
  `references/` kept. `bash scripts/validate.sh` green; adapters regenerated (+260 fanned files). Left in
  `[Unreleased]` (batching — no version bump yet). **Awaiting review/merge.**
- **#135** — scoped fix issue for **#121** (filed from triage): add a **runnability/bootstrap** check to
  impl-verify (new optional `smokeCommand` → `CHECK-I2x`, degrading gracefully to advisory) + a cheap
  static "bootstrap has a non-test caller" heuristic. Design/implement there. Not started.

## Open issues

_GitHub tracker (`gh issue list --state open`)._

- **#121** — `forge-verify-impl` reports "clean" on a walking skeleton that never bootstraps. **TRIAGED**
  2026-07-14 → root cause confirmed (CHECK-I01..I20 is all static reads + typecheck/lint + "tests exist",
  no end-to-end runnability check; the skeleton's unit tests self-bootstrap so `CHECK-I16` misses the
  missing production call site). **High** severity; standalone + epic-member scope; stack-agnostic. Scoped
  fix filed as **#135** (see "In flight"). Triage comment on #121; no code changed.
- **#122 / #132** — shared `references/` don't resolve on non-plugin (npm-installer) Claude installs; fix =
  build-time fan-out. **Fix in flight → PR #134** (see "In flight"). Closes both on merge. (#123 was a dup.)
- **#124** — forge completion dead-ends: no hand-off to the next feature at `forge-6-docs` exit or in
  the navigator. Partially mitigated by the 0.12.7 navigator detached-epic hint (#125 Fix #4), but
  the general hand-off is still open. Not started.
- **#126** — scripted "adopt into epic" recovery command (reconcile a detached standalone into an
  epic member = epic-backflow **Phase 3**, composite manifest+specs mutator). Filed as the #125
  follow-up; 0.12.7 ships the guards + a manual recipe (`docs/recovery-detached-epic-member.md`)
  instead. Not started.

(**#123** closed as a duplicate of #122.)

## Deferred / optional (not scheduled)

- **Epic-backflow Phase 3** — automated composite `move-boundary`/`split` mutators. Design in
  `plans/DESIGN-epic-backflow.md`; Phases 1–2 shipped in 0.12.4.
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
