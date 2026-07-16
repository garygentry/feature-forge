# Changelog

All notable changes to feature-forge are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **forge-5-loop: `--review` is now the recommended default run mode (rauf only).**
  Step 2d's launch confirmation previously left the `AskUserQuestion` option set
  unprescribed — it handed the model a prose block ("Proceed, or would you like to
  adjust?") and let it improvise the choices, so the rendered options varied
  run-to-run (sometimes "bare + a specific `--review` option", sometimes "bare +
  open-ended add-a-flag"), and the bare no-review command was always the default.
  Step 2d now prescribes a deterministic **"Run mode"** question with a fixed option
  order: **(1) Run with review pass — recommended/default** (appends `--review`),
  **(2) Run without review** (bare command), and **(3, only when the backlog has
  blocked items) Review + retry blocked** (`--review --retry-blocked`).
  `AskUserQuestion`'s built-in "Other" still covers ad-hoc flags (`--model`,
  `--timeout`). The run mode surface is **gated on `loopRunner.name == "rauf"`**
  (`--review` is a rauf-specific flag; the 0.6.0 `minRunnerVersion` floor guarantees
  it is available once the loop clears gate 1c) — non-rauf runners keep the prior
  bare-command confirmation byte-for-byte. Verbatim option labels live in
  `forge-5-loop/references/runner-contract.md` (`## Run mode`). No downstream change:
  Step 4a already reads the `review_completed` event for review runs.

## [0.12.8] — 2026-07-14

Installer republished as `@garygentry/feature-forge@0.2.13` (unchanged installer logic; carries the 0.12.8 plugin pin).

### Added

- **Scripted "adopt into epic" recovery command (#126, epic-backflow Phase 3).**
  Split-brain epics (#125) — a feature forged as a flat standalone when it should be an epic
  member — previously recovered only through manual branch surgery
  (`docs/recovery-detached-epic-member.md`). A new `epic-manifest.py adopt-feature {epic} {feature}`
  subcommand now does the on-disk reconciliation in one command: it relocates
  `specs/{feature}/` → `specs/{epic}/{feature}/`, **merges** the standalone's completed-stage
  history onto the member stub while **preserving** the stub's `epic`/`branch` back-pointers,
  removes the flat dir (no residual), and adds the feature to `epic-manifest.json` if absent. It
  operates on the current tree (bring a cross-branch standalone onto the epic's home branch first)
  and is **re-entrant** — a refused manifest add (e.g. an unknown `--depends-on`) leaves the
  relocation done, and re-running finishes it; ordered relocate-then-manifest so the name maps to
  exactly one dir when `add-feature`'s global-uniqueness re-check runs. After adoption `resolve`
  returns the single nested member, `validate` is clean, and `check-epic-base` reports `action: none`.
  EPIC.md prose is regenerated separately via `forge-0-epic`. Documented in the recovery doc (now
  leads with the scripted path) and the forge-0-epic subcommand reference. Tests + adapters added.

- **impl-verify runnability check: "clean" now means "it runs" (#135, fixes #121).**
  The implementation-mode checklist (`CHECK-I01..I20`) was entirely static reads +
  typecheck/lint + "tests exist" — nothing asserted the assembled application actually
  boots and serves one real request, so a walking skeleton (a bootstrap exported and
  unit-tested but never wired into a runtime entrypoint) passed clean yet answered no
  request. A new **Runnability** section adds two checks: **`CHECK-I21`** executes an
  optional new `smokeCommand` from `forge.config.json` (boots the wired entrypoint and
  drives one happy-path request; pass iff exit 0), and **`CHECK-I22`** is a static
  heuristic — every exported bootstrap/`init*` the specs mark runtime-required must have
  ≥1 **non-test** call site on a runtime path. Both **degrade gracefully**: an unset
  `smokeCommand` or a feature with no runnable surface yields an advisory not-applicable
  finding, never a hard fail, and both fire only at impl-verify completion (post-loop),
  never mid-loop. `smokeCommand` (`string|null`, default `null`, distinct from
  `testCommand` and `loopRunner.runCommand`) is threaded through the config schema,
  `forge-init.sh`, `forge-bootstrap.py`, `forge-2-tech`, and the README config table; the
  `impl` mode total and dimension list in `forge-verify` SKILL.md are bumped (~20 → ~22,
  new runnability dimension). Adapters regenerated.

### Fixed

- **Completion no longer dead-ends — the pipeline hands off to the next unit of work (#124).**
  When a feature reached `complete` (`nextStage` null), both the `forge-6-docs` exit and the
  `/feature-forge:forge` navigator's completion branch just congratulated and stopped, leaving the
  user to remember the next step. Both now hand off: an **epic member** routes back to the epic —
  `render-status`'s next `actionable` member + its `nextCommand` is offered (start it now, honoring
  `autoInvokeNextStage`), or the whole epic's completion is celebrated with the epic-level doc offer;
  a **standalone** completion offers to start a new feature (`forge-1-prd`) and, in the navigator,
  lists other active pipelines from the recency ranker. Coherent with the 0.12.7 detached-epic hint
  (#125): if that split-brain heads-up fired, the recovery path leads. Navigator + forge-6-docs skill
  bodies only; adapters regenerated.

- **Shared references now resolve skill-local on the non-plugin npm-installer Claude layout (#122, #132).**
  Forge skills cite shared bundle-root references (`references/shared-conventions.md`,
  `references/stage-exit-protocol.md`, the stack profiles, …) and their own skill-local
  references with the same bare `references/X` prefix, though the two live in different
  dirs. On the plugin layout the bootstrap prelude resolves the shared refs via
  `${CLAUDE_PLUGIN_ROOT}`; on the **non-plugin** npm-installer Claude layout
  (`~/.claude/skills/feature-forge/`, no `${CLAUDE_PLUGIN_ROOT}`) a bare
  `references/<shared>` prose read did **not** resolve from a skill dir, so the agent
  degraded to manual reconstruction (11/13 skills affected). The adapter build
  (`scripts/build-adapters.py`) now **fans out** every cited bundle-root shared
  reference into that skill's own `references/` at build time, so the bare path
  resolves skill-local on **every** install layout — with **no skill-body changes**.
  The bundle-root `references/` tree is kept (scripts resolve it via `$R`; the plugin
  path still uses it); this only adds skill-local copies. Adapters regenerated.

## [0.12.7] — 2026-07-14

Installer republished as `@garygentry/feature-forge@0.2.12` to carry this to `npx` users.

### Added

- **Split-brain epic guard: refuse to forge an epic member as a detached standalone (#125).**
  `discover-feature` now surfaces `epic`/`isEpicMember` on every candidate, so `forge-1-prd`
  can consult cross-branch discovery **at mint time**: whenever forge-1 is about to create a flat
  standalone — Feature Directory Resolution returns `not-found` (exit 1) **or** `specs dir not found`
  (the exit-2 clean-branch case, e.g. a default branch that predates the epic and has no specs tree
  yet) — and any discovered candidate is a known epic member on another branch, a new **Mint Guard**
  hard-stops with a home-branch pointer instead of silently forging a disjoint, back-pointer-less copy. An explicit `--force-standalone` flag
  (distinct from `--force`, and not implying it) intentionally forks a standalone anyway. As
  defense in depth, a new `forge-session.py check-epic-base` subcommand + **Epic-Member Base
  Guard** block (invoked by `forge-1-prd`..`forge-4-backlog`) refuse to author a nested member
  on a branch that lacks the epic's `epic-manifest.json` (`warn-detached-base`), pointing at the
  member's recorded home branch; `--force` overrides. Both guards self-gate to a no-op for
  standalone features. Docs: the epic branch model — an epic and all its members share one
  `forge/{epic}` branch, inherited by each member's `forge-1-prd` — is now documented positively
  (README Key Concept, a **Branch Inheritance** integration-guide building block, and an
  architecture Robustness note), and `docs/recovery-detached-epic-member.md` covers manual recovery
  of an already-split epic (the scripted "adopt into epic" command is a tracked follow-up, #126).
  Adapters regenerated.

### Fixed

- **Navigator flags a standalone completion that looks like a detached epic member (#125).**
  When a *standalone* feature reaches pipeline completion (`nextStage` null) and its name matches
  a known epic member on another branch, `/feature-forge:forge` now adds a non-blocking heads-up
  that the pipeline may have been forged detached from that epic, pointing at the recovery doc —
  instead of a clean standalone congratulation.

## [0.12.6] — 2026-07-11

Installer republished as `@garygentry/feature-forge@0.2.11` to carry this to `npx` users.

### Added

- **Stage-entry idempotency guard across the authoring stages (#113, O2 — deferred from #92).**
  On entry, `forge-1-prd`..`forge-4-backlog` now detect a re-entered stage instead of blindly
  re-running the interview: a new **Stage-Entry Guard** block in
  `references/shared-conventions.md` (folding in the previously dormant Crash Recovery protocol)
  classifies entry as fresh / interrupted (`status: "in-progress"`) / re-authoring
  (`complete`/`stale`), runs a resume-vs-restart gate (with an on-disk artifact inventory) or a
  "create a new version?" warning, and stamps `status: "in-progress"` + `startedAt` +
  `currentStage=<stage>` at Step 1. The entry stamp is left uncommitted and folds into the
  stage's existing exit commit. This closes the gap where authoring stages never wrote
  `in-progress` at entry, so Crash Recovery could never fire. `--force` bypasses the gate and
  restarts. `forge-0-epic` is unchanged: its manifest-existence dispatch already gates re-entry
  into Edit Mode. No schema change (the `stageEntry` fields already exist); additive and
  backward-compatible. Adapters regenerated.

## [0.12.5] — 2026-07-10

Issue-closeout batch: three fixes/features (#99 loop root-sandbox, #90 scaffold tooling
feedback, #92 state-machine hygiene O1+O3) plus a canonical `STATUS.md`. Installer
republished as `@garygentry/feature-forge@0.2.10` to carry it to `npx` users.

### Added

- **Scaffolded repos now carry a "Tooling feedback" prompt (#90).** Encouraging continuous
  feedback on feature-forge/rauf used to require hand-editing a project's agent-instruction
  files (a near-duplicated block across four files, maintained by hand and prone to drift).
  The prompt is now baked into the scaffold hygiene templates so it lands automatically: the
  project-root `AGENTS.md` / `CLAUDE.md` (forge-bootstrap hygiene templates) get a full
  **Tooling feedback** section — when to flag (any confusing/buggy/missing/surprising forge or
  rauf behavior, papercuts included), where to file (routed to the feature-forge vs. rauf
  issue tracker by which tool the friction is with), how (capture ran/expected/actual/fix-idea
  while fresh, propose a titled issue, file with `gh issue create` on the human's go-ahead, not
  silently), and the autonomous-rauf carve-out (note friction in `progress.md`, don't open
  issues mid-loop). The `specs/` hygiene templates (`references/templates/specs-hygiene/`) get
  a short pointer back to the root section. The blocks are static and forge-bootstrap-owned,
  living outside any rauf-managed region so loop regeneration can't clobber them. Adapters
  regenerated.
- **Structured `deferredDecisions[]` for same-feature decisions postponed to a later stage
  (#92, O3).** A structured alternative to burying a "decide this at the next stage" note in
  the free-text `notes` string, modeled on `epicChangeRequests[]`. New optional
  `deferredDecisions[]` array on `.pipeline-state.json`
  (`references/pipeline-state-schema.json`; additive — legacy states validate unchanged) with
  `question` / `rationale` / `targetStage` / `raisedBy` / `raisedAt` / `status`
  (`open`→`addressed`|`dismissed`). Paired with a new **deferred-decisions rule** in
  `references/stage-exit-protocol.md`: at a stage exit, do not solicit (or unilaterally
  decide) a decision that belongs to a later stage — record it as a `deferredDecisions[]`
  entry for the owning stage to resolve. New `tests/test_pipeline_state_schema.py`; adapters
  regenerated.

### Changed

- **Tightened `currentStage` semantics (#92, O1).** The `currentStage` schema description was
  ambiguous ("the stage currently in progress **or next to start**"). It now has a single
  defined meaning — *where the pipeline IS* (the most recently started stage; `in-progress`
  while authored, then `complete`) — explicitly reconciled with the `stageEntry.status` enum
  and with the **derived** next stage (`next_stage()` computes "what runs next" from
  `stages[].status`, never from `currentStage`). Docstring/comment clarifications in
  `scripts/forge-session.py` make the stored-vs-derived split explicit; no behavior change.
  (O2 — the stage-entry idempotency guard — is deliberately split into follow-up #113: it
  touches all five authoring skills' Step 1 and `forge-0-epic` is at the 300-line body cap.)

### Fixed

- **forge-5-loop no longer circuit-breaks on a hosted remote root environment (#99).** On
  Claude.ai remote (and similar cloud agents) the loop runs as **root**, where rauf's default
  launch `claude -p --dangerously-skip-permissions …` is refused by the Claude CLI unless
  `IS_SANDBOX` is set — so every spawn exited and rauf reported the opaque *"Circuit breaker:
  3 consecutive infra failures — halting"* with no hint of the cause. The Step 3b launch now
  exports `IS_SANDBOX="${IS_SANDBOX:-1}"` **only when the launcher is root**
  (`[ "$(id -u)" = 0 ]`); non-root/local runs are unaffected (no-op), and an explicitly-set
  `IS_SANDBOX` is honored. The loop surfaces a one-line note when it sets the flag, and
  `forge-session.py doctor` now reports the root/sandbox condition as a diagnosable check
  (`rootSandbox` block). Guard added to both launch variants in
  `skills/forge-5-loop/references/runner-contract.md`; adapters regenerated. The durable
  upstream fix (rauf honoring `IS_SANDBOX`/emitting a clear error) is tracked as a rauf-repo
  follow-up.

## [0.12.4] — 2026-07-10

### Added

- **Epic backflow (Phase 1): record and route "the epic decomposition is wrong."** When a
  member stage (`forge-1-prd`/`forge-2-tech`) surfaces that the *epic* itself must change — a
  sibling feature must be added, a frozen boundary between features must move, a feature must
  split, or a dependency edge is wrong — that concern now has a first-class path instead of an
  improvised open question. New optional `epicChangeRequests[]` array on the member
  `.pipeline-state.json` (`references/pipeline-state-schema.json`; additive, no schema-version
  bump) records each request with a `blocksCurrent` flag. `forge-0-epic` edit mode reads pending
  requests on entry (new step E0-read in `references/edit-mode.md`) and offers to apply each
  pre-filled — `add-feature`/`redep` through the existing mutators, `move-boundary`/`split`
  guided-manual in v1 — flipping `status` to `applied` (or `dismissed`) in the same commit.
  `forge-session.py stage-exit` routes the stage exit on `blocksCurrent`: a blocking request
  interposes a reconcile-first next-command (`/feature-forge:forge-0-epic {epic}`) before the
  next stage; only non-blocking requests append a reminder. Every mutation still requires human
  approval. Navigator + `forge-verify` surfacing of open requests is deferred to Phase 2.
- **Epic backflow (Phase 2): surface open epic change requests in the read-only dashboards.**
  `epic-manifest.py render-status` now derives, per member, `openEpicChangeRequests` and
  `blockingEpicChangeRequests` (the `blocksCurrent` subset) from each `.pipeline-state.json` —
  a single deterministic source feeding both surfaces. The `/feature-forge:forge` **Epic
  Dashboard** marks any member with open requests (⚠️ + a `/feature-forge:forge-0-epic {epic}`
  reconcile hint), distinguishing blocking (reconcile-before-specs) from non-blocking
  (finish-then). `forge-verify` epic mode gains a non-fatal **CHECK-E09** that reports each
  member's open requests as a finding, severity keyed to `blocksCurrent` (blocking →
  `inconsistency`, non-blocking → `improvement`) — the pre-emptive surface for the divergence
  class CHECK-E06/E07 otherwise catch only after the fact. The surfaces are strictly read-only;
  only edit mode mutates a request's status. Additive counts (no schema change); adapters
  regenerated.

### Changed

- **Copyable next-stage command on the loop's exit blocks.** The two bespoke
  `forge-5-loop` exits — the step-6 epic-member handoff (standard block) and the all-done
  closing (warm block) — now render their next command inside a fenced code block instead
  of inline code, matching the tap-to-copy parity the authoring stages got in 0.12.3. The
  canonical blocks (`references/stage-exit-protocol.md`) and both stamp sites were updated
  in lock-step; the drift-guard (`tests/test_stage_exit_protocol.py`) covers it. The warm
  block stays host-neutral (no literal `/clear`, since it is copied verbatim into the
  non-Claude adapters). Two `forge-5-loop` Gotchas were merged to keep the SKILL body at
  the 300-line cap. Adapters regenerated.

## [0.12.3] — 2026-07-10

Stage-exit UX polish plus documentation catch-up for the 0.12.x stabilization work.
Installer republished as `@garygentry/feature-forge@0.2.8` to carry it to `npx` users.

### Changed

- **Copyable next-stage command in the stage-exit block.** The scripted "Next steps"
  block (`_next_steps_block` in `scripts/forge-session.py`, used by the authoring stages)
  now renders the next-stage command inside a fenced code block instead of inline code, so
  mobile and remote-control hosts get a native tap-to-copy button. The
  `─ forge: end of stage ─` sentinel remains the absolute-last line, so the stage-exit
  contract is intact. The 5 host adapters were regenerated (`forge-session.py` is bundled
  verbatim); a test asserts the fenced block and the sentinel-still-last invariant.

### Documentation

- **Docs site brought current with 0.12.x behavior.** Documented **branch reconciliation**
  (new subsection in the Stage 5 loop page + a troubleshooting FAQ on imposed
  `claude/<slug>` branches), **cross-branch feature discovery** (the navigator's
  empty-current-branch fallback, in the dashboard page), and the **copyable next-stage
  command** (managing-context page).

Pipeline-stabilization batch: the bootstrap prelude resolves the plugin root exactly on
any Claude layout (chunk 2b), the cross-branch subsystem gains whole-pipeline discovery
and self-healing **branch reconciliation** for hosted/imposed session branches (chunks 5c
+ 6), and the navigator's exit computation is consolidated onto a single resolved
verify-gate with a present-once discipline (chunk 5b). Installer republished as
`@garygentry/feature-forge@0.2.7` to carry it to `npx` users.

### Changed

- **Navigator exit convergence: one resolved verify-gate + present-once discipline
  (chunk 5b).** `rank-features` rows now carry a single `verifyGate` classification
  (`none` / `auto` / `standard`) computed once by the ranker (mirroring `stage-exit`'s
  directive), so the navigator reads the resolved gate instead of re-deriving it from
  `verifyPending` + `autoVerify` in prose. `skills/forge/SKILL.md` §3 now enforces
  **present the gate exactly once and act only on the chosen option — never also narrate
  the not-taken branch** (e.g. never print the "start in a clean session" recommendation
  and *then* auto-invoke the next stage in the same session): the `AskUserQuestion` answer
  is the single decision. New `verifyGate` matrix tests in `tests/test_auto_verify.py`.
  (Deferred: migrating `forge-5-loop`'s bespoke post-loop exit block onto `stage-exit` —
  the loop is at its body-size cap and its exit is loop-specific; tracked as a follow-up.)

### Added

- **Cross-branch resolution: `discover-feature --all` + branch reconciliation (chunks 5c
  + 6).** Two additions to the cross-branch subsystem that hardens the hosted/remote flow:
  - **`discover-feature --all`** enumerates *every* feature's pipeline state across all
    local + remote-tracking branches (grouped by feature), so the navigator's
    empty-dashboard case (fresh clone / default-branch session with state on topic
    branches) surfaces the whole branch-scattered pipeline set instead of concluding
    nothing exists. Wired into `skills/forge/SKILL.md`'s no-features-on-current-branch path.
  - **Branch reconciliation** (`forge-session.py reconcile-branch`) treats the recorded
    `branch` field as a self-healing hint, not gospel. A hosted environment (Claude.ai
    remote, cloud agents) imposes an arbitrary session branch (e.g. `claude/<slug>`) that
    Branch Setup silently records; when the user moves to the intended topic branch the
    stale field made `forge-5-loop` offer to switch *back* to the imposed branch. The
    reconciler classifies deterministically with a **default-branch guardrail**:
    `adopt-current` (on a non-default topic branch where the state resolves → update the
    record to the current branch, visibly, never pushing back), `warn-drift` (on the
    default branch → recommend a topic branch), or `none`. Wired into the `forge-5-loop`
    pre-flight (new **Branch Reconciliation** block in `references/shared-conventions.md`)
    and surfaced in `doctor` (`branchReconcile` classification). New tests:
    `tests/test_reconcile_branch.py`, plus `--all` cases in `tests/test_discover_feature.py`.

### Changed

- **Bootstrap prelude leads with `${CLAUDE_PLUGIN_ROOT:-}` (stabilization chunk 2b).** The
  byte-pinned bootstrap prelude now probes Claude's plugin-root env var as its first
  resolver candidate, giving exact, glob-free root resolution on any current/future Claude
  layout (no version-skew window) — when unset it expands to empty and is harmlessly
  skipped, so path-based resolution is unchanged. Landed as an atomic sweep (the
  `BOOTSTRAP_PRELUDE` constant + all canonical stamp sites + prelude-pinning fixtures, one
  commit, `VR_PRELUDE_DRIFT`-guarded). Spec-purity **rule 3 is hardened**: it now detects
  the `${CLAUDE_PLUGIN_ROOT` prefix (so the `:-}` default form is not an escape hatch) and
  allows the sanctioned use only by stripping the byte-pinned prelude before scanning.
  `forge-agent-adapters-build` translates the hint to `${FEATURE_FORGE_ROOT:-}` for
  non-Claude bundles (which `forge-root.sh` already prefers). Docs updated
  (`references/portable-root.md`, `references/vendor-construct-inventory.md`); new
  resolution tests (hint-wins / stale-hint-skipped) and a rule-3 scoping test.

## [0.12.1] — 2026-07-09

Patch: fixes a self-referential dispatch defect in the verifier that could make
in-stage auto-verify (and any `forge-verifier` dispatch) return a non-answer with no
findings artifact. Installer republished as `@garygentry/feature-forge@0.2.6`.

### Fixed

- **`forge-verifier` no longer self-dispatches.** The `forge-verifier` agent pre-loads
  the `forge-verify` skill, which is written from the *parent orchestrator's* point of
  view ("dispatch the `forge-verifier` subagent via the Agent tool", "Synthesize (parent
  session)"). With no role guard, a dispatched verifier read that as an instruction to
  *itself*, tried to delegate further — it has no Agent tool, so it couldn't — and
  returned a placeholder ("verification is still running…") with **no findings block and
  no artifact on disk**, leaving the tree clean and the stage's auto-verify silently
  empty. Three guards close it: (1) a **role-disambiguation preamble** at the top of
  `skills/forge-verify/SKILL.md` routes a dispatched verifier straight to the checks and
  tells it to SKIP the parent-only sections (now headed *"Subagent Delegation (parent
  orchestrator only)"*); (2) the `agents/forge-verifier.md` system prompt reinforces
  *you ARE the verifier, you never dispatch one*; (3) `references/stage-exit-protocol.md`
  now dispatches the in-stage verify **synchronously** (await the digest inline, never
  background) and treats a non-answer as clean-room-unavailable (verify left **pending**,
  never silently passed). New `tests/test_verifier_role_guard.py` locks the invariants
  (including the verifier's tool allowlist excluding `Agent`/`Task`).

## [0.12.0] — 2026-07-09

This release folds the accumulated post-`0.11.0` work into a single plugin version and
carries it to `npx` users via installer `0.2.5`. The headline is the **pipeline
stabilization** series (#93–#97): the clean-environment failures surfaced by remote
end-to-end testing are root-caused and fixed, and the deterministic computations the
model previously performed in prose at stage exit move into read-only
`forge-session.py` subcommands. Also included: in-stage auto-verify (#93) and the
navigator / rauf-pin work previously carried only by the `0.2.3`/`0.2.4` installer
publishes — `0.12.0` is the first plugin version to include all of it.

### Changed

- **rauf pin advanced to `@garygentry/rauf@0.12.0`.** rauf shipped 0.12.0 (file-driven
  loop supervision — a health/status derivation over `state.json` + `events.ndjson`
  with robust backlog-root resolution and event-altitude filtering in `follow` /
  `log --follow`; `scanBacklogRoots` now skips `artifacts/`; and `author-backlog`
  reset-before-repopulate guidance), so `RAUF_PIN` advances `0.11.0 → 0.12.0` — the
  version a fresh install provisions as the default loop runner. Canonical
  `installHint` (`references/forge-config-schema.json`), regenerated adapters,
  `COMPATIBILITY.md`, installer docs, and the installer pin tests updated.
  `minRunnerVersion` stays `0.6.0` (no compatibility floor change); rauf and
  feature-forge remain independently versioned. The install-time check is a read-only
  `npm view` resolvability probe — existing installs are unaffected. Installer
  published as `@garygentry/feature-forge@0.2.4` to carry the new pin and the
  accumulated Chunk A–G hardening (#80–#87) re-bundled into `adapters/` for
  `npx` users (supersedes the `0.2.3`/`0.11.0` entry).
- **rauf pin advanced to `@garygentry/rauf@0.11.0`.** rauf shipped 0.11.0 (rich live
  event rendering in `follow`/`log --follow`, and a distinct `ITERATIONS_COMPLETE`
  state so an exhausted iteration budget no longer masquerades as a usage limit —
  bounded `--iterations N` runs now exit 0/5 instead of 4), so `RAUF_PIN` advances
  `0.10.1 → 0.11.0` — the version a fresh install provisions as the default loop
  runner. Canonical `installHint` (`references/forge-config-schema.json`), regenerated
  adapters, `COMPATIBILITY.md`, installer docs, and the installer pin tests updated.
  `minRunnerVersion` stays `0.6.0` (no compatibility floor change); rauf and
  feature-forge remain independently versioned. The install-time check is a read-only
  `npm view` resolvability probe — existing installs are unaffected. Installer
  published as `@garygentry/feature-forge@0.2.3` to carry the new pin (supersedes the
  `0.2.2`/`0.10.1` entry).

### Added

- **Pipeline stabilization series (#93–#97)** — the clean-environment reproduction and
  the three fixes it drove:
  - **Clean-env repro runbook, regression anchors, and a `doctor` subcommand** (#94).
    `docs/clean-env-repro.md` gives executable repros of the two clean-environment
    smoking guns (marketplace-cache installs the bootstrap prelude missed; topic-branch
    pipeline state invisible from the default branch); `forge-session.py doctor` is a
    one-shot ground-truth capture (resolved plugin root + version/commit, current vs.
    recorded state branch, recency-ranked feature summary, backlog-path existence).
  - **Marketplace-cache install resolution in root discovery** (#95, root cause A).
    `forge-root.sh` now probes `~/.claude/plugins/cache/<mp>/<plugin>/<version>/`
    (newest-`plugin.json`-first) ahead of the `plugins/*` glob, so a versioned cache
    install always beats the marketplace clone instead of silently running scripts from
    a different commit than the installed skills.
  - **Cross-branch feature discovery + anti-fabrication guard** (#96, root cause B). New
    read-only `forge-session.py discover-feature` scans local heads and remote-tracking
    refs (surfacing unfetched branches with exact fetch/switch commands) so a session on
    the default branch finds a feature whose state lives only on its topic branch; the
    guard forbids narrating pipeline state that resolution/discovery did not establish.
  - **Script-emitted stage exit + skill diet** (#97, root cause C). New read-only
    `forge-session.py stage-exit` emits deterministic DIRECTIVES (effective auto-verify,
    verify gate, freshness, next stage/command) and the exact NEXT-STEPS text terminated
    by a fixed sentinel, replacing ~19-line stamped prose blocks the model had to
    compute by hand in every stage skill.
- **In-stage auto-verify** (#93) — when `autoVerify` is on, the authoring stage now
  dispatches the clean-room `forge-verifier` at stage end (in-session, after the artifact
  commit and before the exit block), chaining `forge-fix` + mandatory re-verify under
  `autoFix`, instead of deferring to the navigator after a `/clear`. Honors the
  verify-before-clear principle and closes the gap where a direct next-stage invocation
  silently skipped a pending verify.
- **Forge navigator predictions and context-window awareness** (#59) — recency-based
  feature prediction, next-stage auto-invoke, and context-window awareness in the forge
  pipeline skills.

### Fixed

- **`forge-5-loop` monitors rauf's native `events.ndjson`** (#61) instead of redirecting
  `--ndjson` into the state dir (rauf self-persists and rotates that file).
- **Inferred context window auto-bumps to 1M** when usage exceeds 200k (#60).

> All of the above ships to `npx @garygentry/feature-forge` users via the re-bundled
> `adapters/` tree carried by the **`0.2.5`** installer publish — which supersedes the
> `0.2.3`/`0.2.4` publishes and is the first installer to carry the pipeline
> stabilization series (#93–#97).

## [0.11.0] — 2026-06-26

This release completes the agent-agnostic remediation: a non-Claude user can now
install **and run** the full feature-forge workflow, with each agent's bundle placed
where that agent actually loads it, while Claude stays the rich, byte-identical default
path. Generated bundles are self-contained; the installer is per-agent honest about
install confidence; and the local gate now matches CI.

### Added

- **Installer second-root placements (manifest v2).** The cross-agent installer now
  writes the two per-agent placements that the single-`destination` model could not
  express: Codex custom agents are mirrored flat into `.codex/agents/*.toml` (where
  Codex loads them) alongside the primary `.agents/skills/feature-forge` bundle, and
  Copilot — which has no skills loader — gets a sentinel-delimited managed block in
  `.github/copilot-instructions.md` pointing at the staged `.github/feature-forge`
  bundle. The managed block is merged idempotently, preserving any existing user
  content; `update` leaves a user-edited block alone unless `--force`, and `uninstall`
  strips only the block (removing the file only if nothing else remains). The install
  manifest is bumped to `schemaVersion: 2` with an additive `placements[]` array; v1
  manifests (no placements) are still read and reconciled on the next update.

- **Host-specific instruction translation for non-Claude targets.** The adapter
  generator now applies a deterministic per-target body transform to NON-Claude skill
  and agent bodies: it strips Claude-only tooling idioms (`AskUserQuestion`, the
  `Agent`/`Task tool` dispatch, `subagent_type=`, `run_in_background`, `` `Monitor` ``)
  and appends a per-target "Host execution notes" overlay (Codex-native for codex,
  neutral elsewhere) so the workflow reads correctly on each host. The Claude emitter is
  unchanged — it emits canon **byte-identical** — the strongest "never disrupt Claude"
  guarantee.

- **Self-contained adapter bundles for true cross-agent installs.** Every
  generated per-agent bundle now ships the neutral `.feature-forge-bundle.json`
  sentinel plus byte-identical copies of every runtime helper a skill can invoke
  (`forge-root.sh`, `forge-init.sh`, `epic-manifest.py`,
  `validate-traceability.py`, `forge-bootstrap.py`). The portable root resolver
  (`scripts/forge-root.sh`) now self-locates on the neutral sentinel (not the
  Claude-only `.claude-plugin/plugin.json`), probes the agent-neutral
  `.agents/skills/feature-forge` roots (project + `$HOME`) alongside the Claude
  paths, and honors a neutral `FEATURE_FORGE_ROOT` override (keeping
  `CLAUDE_PLUGIN_ROOT` as a backwards-compatible Claude fallback). The bootstrap
  prelude was widened to discover the resolver under non-Claude install roots, so
  helper-backed skills run after a `--agent codex` (etc.) install — previously
  the first helper-backed skill could fail even after a successful install. The
  installer's bundle-integrity check now requires these files on every agent.

- **Reliable, state-aware branch setup at pipeline entry.** The new-feature /
  epic branch prompt was previously gated on `gitCommitAfterStage`, soft, and
  blind to the current branch — so features often started on the default branch.
  A centralized **Branch Setup** block (`shared-conventions.md`, invoked by
  `forge-1-prd` and `forge-0-epic`) now gates on a new `branchPerFeature` config
  (default `true`, independent of `gitCommitAfterStage`), detects the current vs.
  default branch, and **strongly recommends (still declinable)** creating
  `{branchPrefix}{label}` (default prefix `forge/`) when on the default branch;
  it skips silently on a topic branch, and epic members inherit the epic branch.
  The chosen branch is recorded in `.pipeline-state.json` (`branch` field), and
  `forge-5-loop` re-checks it in a pre-flight guard before the loop commits
  per item. New config: `branchPerFeature`, `branchPrefix`.

- **Cross-agent installer published to npm** as `@garygentry/feature-forge`
  (independent version line; `0.1.1` adds a package README and validates the
  OIDC trusted-publishing CI path). The one-liner is now
  `npx @garygentry/feature-forge install` — the bare `feature-forge` name on npm
  belongs to an unrelated package. The package now bundles the generated
  `adapters/` at pack time (`prepack`), so it resolves agent bundles when
  installed from npm; Python build artifacts are filtered out. A manual
  `npm-publish.yml` (`workflow_dispatch`) workflow was added.

### Fixed

- **`npx @garygentry/feature-forge` / `npm i -g` silently did nothing on
  Linux/macOS (installer `0.1.4`).** Two compounding bugs in the published bin:
  (1) `dist/cli.js` shipped without a `#!/usr/bin/env node` shebang (ENOEXEC →
  `/bin/sh` fallback → JS syntax error); and (2) the process-entry shim compared
  `import.meta.url` to `process.argv[1]` **without resolving symlinks** — but
  npm/npx install the bin as a symlink, so the comparison never matched and
  `main()` never ran (silent exit 0, no output). Added the shebang and made the
  entry shim resolve the symlink (`realpathSync`) before comparing. Both are
  guarded by new tests (shebang presence + spawn-through-a-symlink). Masked
  until now because CI and the test suite invoke `node dist/cli.js` / `main()`
  directly — never the real symlinked bin — and npm's Windows `.cmd` shims call
  `node` explicitly. (`0.1.3` shipped only the shebang half of this fix.)

### Changed

- **Codex adapter uses current Codex skill/agent shapes.** Codex skills are now
  emitted as `skills/<name>/SKILL.md` (the documented Codex skill directory shape)
  instead of `skills/<name>/<name>.md`, and Codex subagents are emitted as
  standalone `agents/<name>.toml` custom-agent files
  (`name`/`description`/`developer_instructions`) — the current Codex custom-agent
  format — replacing the aggregate `agents/openai.yaml` that Codex does not load.
  Claude-only structural keys (tools/model/maxTurns/effort/memory/skills) are
  drop-recorded in `GENERATION-REPORT.md`, so no Claude model aliases leak into
  Codex config. The Claude adapter is unchanged.

- **Installer per-agent install strategy + honest confidence.** The installer's
  per-agent table now splits detection from placement: `configDirName` (the
  detection probe) is decoupled from `installBaseDir`/`installSubpath` (the install
  location AND the containment root), so each agent installs where it actually loads
  content — codex under `.agents/skills/feature-forge`, copilot under
  `.github/feature-forge`, cursor/gemini unchanged. A widened confidence vocabulary
  (`confirmed`/`verified-current`/`best-known`/`unsupported`, with an optional
  project-scope override) plus a per-target docs URL are surfaced in the run report,
  so users see honestly when an install path is best-known rather than vendor-confirmed.

- **Neutral stack-decisions resolution path.** Project stack overrides now resolve
  `.feature-forge/stack-decisions.md` → `.agents/references/stack-decisions.md` →
  `.claude/references/stack-decisions.md` (legacy alias) → `references/stacks/{stack}.md`
  → `_generic.md`, so non-Claude users get a neutral, documented override location
  while existing Claude paths keep working.

- **Local gate parity + portable root-probe coverage.** `scripts/validate.sh` now
  runs `ruff check scripts/ [eval/]` (hard-fail when ruff is present, warn when
  absent) so the local gate matches CI's Quality Gate. The portable resolver
  `scripts/forge-root.sh` now probes every supported agent's install destination
  under both global and project scope (adding cursor `.cursor/rules`, copilot
  `.github/feature-forge`, and project-scope `.claude`/`.gemini`), closing a
  first-use gap where a helper invoked from a project root could not locate a
  cursor/copilot install.

- **rauf pin advanced to `@garygentry/rauf@0.8.0` (installer `0.1.5`).** rauf
  released 0.8.0 (provider-neutral backlogs + `rauf loop run --no-model`), so
  `RAUF_PIN` advances `0.7.0 → 0.8.0` — the version a fresh install provisions as
  the default loop runner. Canonical `installHint`, regenerated adapters, and
  `COMPATIBILITY.md` updated to the new coordinate. `minRunnerVersion` stays
  `0.6.0` (the agent-surface floor — 0.8.0's `--no-model` doesn't raise it). rauf
  and feature-forge remain independently versioned; the pin is the only coupling.
- **Install docs** (README + `docs/agents/*.md`) restored to the scoped
  `npx @garygentry/feature-forge` one-liner (they had been pointed at a
  from-source path while the package was unpublished).
- **rauf pin reconciled (installer `0.1.2`).** rauf is now published to npm
  (rauf#28), so `RAUF_PIN` advances from the unpublished `rauf@0.6.0` to the
  scoped, published `@garygentry/rauf@0.7.0` (the bare `rauf` name is blocked by
  npm's similarity filter). The install-time resolvability preflight now passes
  by default — the `--skip-rauf` flag remains as an opt-out (e.g. offline
  installs) rather than a workaround for an unpublished pin. The
  `installHint` schema default + regenerated adapters and install docs were
  updated to the scoped coordinate. (`minRunnerVersion` stays `0.6.0` — that is
  the rauf *binary* agent-surface floor, distinct from the npm pin.)

## [0.10.0] — 2026-06-13

### Added

- **CI gates (GitHub Actions, net-new).** `ci.yml` (per-PR blocking deterministic
  gate via the `quality-gate` composite action), `os-matrix.yml` (installer
  `--dry-run` + `uninstall` on Ubuntu/macOS/Windows), and `eval.yml` (advisory
  trigger-accuracy, `workflow_dispatch` + weekly schedule, non-blocking).
- **SKILL.md frontmatter JSON Schema** (`references/skill-frontmatter.schema.json`)
  as the single source of truth for the spec-pure key set; `check-spec-purity.py`
  now loads its allowed/required keys from it.
- **Shell + Python lint gates** — `shellcheck` over `scripts/*.sh` (`.shellcheckrc`)
  and `ruff` over `scripts/*.py` + `eval/*.py` (`ruff.toml`).
- **Trigger-accuracy eval harness** (`eval/run-eval.py` + `eval/fixtures/<skill>.json`).
- **Per-agent setup docs** (`docs/agents/{claude,codex,copilot,cursor,gemini}.md`).
- **MIT `LICENSE`** (previously none).
- **`.gitattributes`** — LF normalization (`* text=auto eol=lf`) + `export-ignore`
  for dev-only trees.

### Changed

- **README rewritten install-first** — Claude marketplace install, universal
  `npx feature-forge install` one-liner, and a per-surface agent table.
- **Version fields reconciled to `0.10.0`** — `marketplace.json` `0.9.0` → `0.10.0`
  (hand-edit) and `adapters/gemini/gemini-extension.json` `0.0.0` → `0.10.0`
  (via the `GEMINI_EXTENSION_VERSION` generator constant). `plugin.json` was
  already `0.10.0`. `installer/package.json` keeps its independent line.
- **Requires rauf ≥ 0.6.0.** Bumped `loopRunner.minRunnerVersion` default
  `0.2.0` → `0.6.0`. 0.6.0 is the floor that ships the **agent-selection
  surface** (`--agent` / `rauf agents`) this release's `loopRunner`
  (`agentArgument` / `agentsProbeCommand`) consumes. It builds on rauf's
  **v0.5.0 grammar + contract flip** — unified exit codes across `status` /
  `loop run`, `loop run --detached` replacing `loop start`, an explicit `review`
  signal, and versioned `events.ndjson` — which 0.6.0 includes. feature-forge
  reads both the unified exit-code / status surface and the agent-selection
  surface, so `forge-5-loop` now gates on 0.6.0 (`rauf version --json`,
  semver-compared) before running.
- **Updated `loopRunner` command defaults to the v0.5.0 rauf surface:**
  `followCommand` `{bin} loop follow …` → `{bin} follow …` (`loop follow` was
  promoted to the top-level `follow` verb in rauf's Phase-1 monitor clean-break),
  and `watchCommand` `{bin} loop watch … --json` → `{bin} status … --json` (the
  `loop watch` verb was removed; stall telemetry — `stuckWarning` — is now read
  from `status --json` / `iteration-status.json`). A project that pins these
  commands in its own `forge.config.json` should update them likewise.

### Requires

- **rauf ≥ 0.6.0.** See `COMPATIBILITY.md`.

## [0.9.0] — 2026-06-09

### Changed

- **The loop runner is now config-driven, not hardcoded.** Added a `loopRunner`
  block to `forge.config.json` (`references/forge-config-schema.json`) with
  templated commands (`{bin}`/`{backlogDir}`/`{specsDir}`/`{iterations}`),
  defaulting to rauf. Every previously hardcoded `rauf …` string in the skills
  now renders from `loopRunner`, so a different ralph-style runner conforming to
  rauf's `SPEC-BACKLOG-TOOL-CONTRACT.md` can be swapped in without editing a
  skill. See `references/ralph-loop-contract.md`.
- **`forge-5-rauf-loop` → `forge-5-loop`** (config-driven). Renders all commands
  from `loopRunner`; enforces `minRunnerVersion` (default rauf **0.2.0**) via
  `rauf version --json` (semver-compared) before running, stopping with the
  CLI-install hint if the runner is missing/too old. The pipeline-state stage key
  and `currentStage` enum migrated to `forge-5-loop`.
- **`forge-4-backlog` is now a thin orchestrator.** It delegates backlog
  *authoring* to the rauf plugin's `author-backlog` skill (single home for the
  granularity / acceptance-criteria / `agentDelegation` craft) and *validation*
  to the runner's `validate` verb — keeping only pipeline concerns (plan review,
  state, commit). Degrades gracefully when the runner isn't installed yet
  (authors, then skips validation with a warning), since it runs before forge-5's
  setup gate.
- Renamed config key `raufIterationMultiplier` → `loopIterationMultiplier`.

### Removed

- `scripts/validate-backlog.py` — the broken Python validator (it exited 0 with
  only a warning on rauf-invalid backlogs). Validation now routes through
  `rauf backlog validate` (exit 0/1/2). `forge-verify` uses the same command.
- `skills/forge-4-backlog/references/backlog-schema.json` and
  `backlog-examples.md` — the schema is owned by rauf (installed copy / `$id`),
  and the examples were migrated into rauf's `author-backlog` skill.

### Requires

- **rauf ≥ 0.2.0** (first release shipping `backlog validate` + backlog
  `schemaVersion`). See `COMPATIBILITY.md`.

## [0.8.0] — 2026-06-09

### Changed

- **Extracted to its own repository.** feature-forge now lives at
  [`garygentry/feature-forge`](https://github.com/garygentry/feature-forge)
  instead of inside the `garygentry/agent-plugins` monorepo. Full commit
  history was preserved via `git subtree split`.
- The repository root **is** the plugin: it carries both the marketplace
  catalog (`.claude-plugin/marketplace.json`, registered with `"source": "."`)
  and the plugin manifest (`.claude-plugin/plugin.json`).
- Added a self-contained `scripts/validate.sh` that validates the flattened
  single-plugin layout (the monorepo previously supplied a marketplace-wide
  validator).

### Install

```
/plugin marketplace add garygentry/feature-forge
/plugin install feature-forge@feature-forge
```

The previous `feature-forge@gwg-plugins` entry in `agent-plugins` remains as a
deprecated stub for one release cycle so existing installs keep working.

### Notes

- This release is a **pure structural move** — no skill behavior changed. The
  pipeline still invokes the `rauf` CLI exactly as in 0.7.0. Config-driven
  loop-runner indirection and delegation to rauf's backlog contract land in a
  later release (tracked in `COMPATIBILITY.md`).

## [0.7.0] and earlier

See git history (`git log`) for changes prior to the repository extraction,
including the `ralph` → `rauf` rename and the stack-agnostic profile system.
