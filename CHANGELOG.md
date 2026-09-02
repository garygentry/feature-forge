# Changelog

All notable changes to feature-forge are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **A `forge-0-epic` stage exit no longer hands back the epic dashboard as the sole remaining action (#248).** Two routes did. **(1) A completed epic had no terminus:** with nothing actionable, the exit set `primaryCommand` to `/feature-forge:forge-0-epic {epic}` and fenced it; re-running it landed in edit mode, found nothing to do, and re-emitted the identical pointer, so the operator was prompted to run the same command indefinitely (observed three times in a row on one epic — as the docs→dashboard handoff, after applying the last open change request, and after `set-status complete` plus a passing epic-mode verify). A finished epic now exits **terminally**: `primaryCommand`, `nextCommand`, and `nextStage` are all `null` and the block fences **nothing**, stating what finished and naming the optional follow-ons (start a new feature, re-open the dashboard to inspect state) as inline prose rather than instructions. Terminal means live `render-status` reports nothing actionable **and** either the rollup says every member is complete or the manifest carries `status: "complete"` (the manifest was previously not consulted at all here; on a valid acyclic graph "nothing actionable" already implies a full rollup, so that second route is narrow by construction — what it really reaches is the epic with no members declared yet, where only the operator can say it is finished). A manifest `status: "abandoned"` terminates too, checked *ahead* of the rollup so an abandoned epic whose members happen to be complete is never announced as completed work; `paused` deliberately still routes to the dashboard, because a pause is an intent to resume. **(2) An *actionable* member with no next production stage** — one that finished all six stages but owes verification, so it is not complete for orchestration — also fell back to the dashboard, self-looping on a not-quite-complete epic. It now routes to `render-status`'s own answer for that member: `forge-fix` for an unapplied findings report, `forge-verify` for unrun scheduled debt, per `epic-manifest.py`'s debt rules rather than a re-derivation here (and `forge-1-prd` where that helper answers it for a member whose `PRD.md` is missing from disk — `nextStage` is read back out of the command so the two can never disagree). The terminal answer is applied at one point, and only where the routing had already landed on the epic dashboard, so verify-first ordering, a live findings report, and a *blocking* epic change request all keep precedence (the reconcile command is the *same string* as the dashboard when the exiting feature is the epic, so that guard is explicit). A *non-blocking* request does not displace the terminus — fencing the dashboard for an optional reconcile would reinstate the same loop — and survives as the inline reminder line the block already renders; a `render-status` failure still degrades to the recoverable dashboard route and never claims completion. `references/stage-exit-protocol.md` gains the null-`primaryCommand` contract — print the block as-is, never substitute a command or promote `nextCommand` — `skills/forge-0-epic/references/edit-mode.md`'s no-member branch is updated to match, and `RenderStatus`'s `status` field joins the required set the router validates.

- **The reverse citation guard is derived instead of pinned, so a new shared reference can no longer silently lose its skill-local fan-out (#246).** `scripts/build-adapters.py` ships shared references twice: a whole-tree copy to each bundle root, and a **citation-driven** fan-out of each reference a skill *cites* into that skill's own `skills/<name>/references/`. The fan-out is what makes a bare `references/X` prose read resolve on the non-plugin npm-installer Claude layout (`~/.claude/skills/feature-forge/`, no `${CLAUDE_PLUGIN_ROOT}`), where the bundle-root tree is unreachable from a skill dir (#122/#132). The guard that was supposed to protect it — `tests/test_reference_citations.py`'s reverse direction — iterated a hardcoded 9-entry `NEW_FILES` tuple left over from one past feature, so a reference added today was invisible to it and `bash scripts/validate.sh` stayed green while the file sat at the bundle root unreachable by the path the skill body actually reads. The guard now **derives** its subject: every `references/**/*.md` plus every `skills/*/references/**/*.md` must be cited by some skill body, covered by the `stacks/` whole-tree fan-out rule the builder special-cases, or carried in a new `UNCITED_ALLOWLIST` with a one-line reason (six entries today — the two `templates/specs-hygiene/` files copied through an explicit `"$R/references/..."` path, the `vendor-construct-inventory.md` audit artifact, and the three `forge-bootstrap` hygiene templates read by `scripts/forge-bootstrap.py`). Its subject is the skill **body** — frontmatter stripped, as the builder scans it — so a citation in a `description:` cannot vouch for a file the builder then fans to nobody, and coverage is **owner-aware**, modelling the builder's never-shadow rule (a citation the builder answers from a skill's own `references/` is not coverage for a shared file of the same name, which would reach no skill dir). Supporting guards keep it honest: per-source non-vacuity floors (a combined floor was satisfiable by the skill-own glob alone, leaving the shared glob — the only one fan-out depends on — unguarded), every allowlist entry must name a file that still exists at that owner, state a reason, and still be *necessary*, and the coverage predicate is asserted to reject a never-cited path (the issue's `touch references/never-cited.md` repro, as a pure assertion). This supersedes the `NEW_FILES` guard specified in `specs/context-efficiency/06-testing-strategy.md` §5; the protection that spec describes is preserved and strengthened — a brace-list citation of the six `verification-checklists/` paths passed the old substring match and now leaves all six uncovered.

## [0.19.0] — 2026-08-31

### Added

- **Pi `forge-5-loop` runs the loop without blocking the session: the `forge-loop-supervisor` extension (#235, #236).** The generic loop contract is Claude-shaped — background the process (`run_in_background`), arm a persistent `Monitor` on `events.ndjson`, `PushNotification` on exceptions — and Pi has none of those surfaces, so the generated Pi skill both promised a background monitor it could not provide AND (in `_HOST_NOTES_PI`) told the model to "run long-lived commands in the foreground," a direct self-contradiction (#235). A new first-party Pi extension supplies the real mechanism: `forge_loop_launch` starts the runner **detached** (it runs in rauf's server and outlives the session) and returns immediately, then a rotation-aware, malformed-tolerant NDJSON watcher turns each `item_completed` into one quiet progress line and **wakes the session** — via `pi.sendMessage(..., { triggerTurn: true })`, the `file-trigger.ts` pattern — only on `needs_human` / `item_blocked` / `llm_stuck_warning` / `review_failed` / `loop_error` / cancellation / `loop_completed`. `forge_loop_status` and `forge_loop_stop` complete the launch/attach/status/stop surface; task identity is persisted (session entry + a file mirror beside the runner state) so a restarted session **reattaches without duplicate reporting** (dedup by rauf's per-run event `seq`), and `session_shutdown` tears down watchers only — never the detached runner (#236). The extension lives at `adapter-src/pi/extensions/forge-loop-supervisor/` (typechecked against the pinned pi `0.81.1`, 16 behavioural tests via `adapter-src/pi`'s `npm run verify`) and ships in the bundle alongside `ask-user-question`. `_HOST_NOTES_PI` now names the concrete tools and drops the foreground instruction, and — because the operative Steps 3b–3f (and `runner-contract.md`) still described the Claude-shaped manual "background it + arm a monitor" path — a Pi redirect is injected at Step 3b and at the top of `runner-contract.md` so the model reads the authoritative `forge_loop_launch` instruction first and treats the manual detail as description, not commands (removing the body-vs-overlay contradiction, not just countermanding it). The Pi host-term pass degrades the leaked Claude lifecycle tokens (`PushNotification` / `TaskStop` / `persistent: true`) to the supervisor's surface, and both the published `installer/package.json` and the generated Pi manifest register the new extension. Adversarial review hardening: the tailer decodes UTF-8 through a `StringDecoder` (a multibyte char split across two reads no longer corrupts a field) and, seeded with the last-seen inode, detects a rotation that happened while the session was away so a new run is not swallowed by a stale `seq` cursor; a terminal event tears the watcher down (freeing relaunch, no leaked interval); the durable mirror is written only on surfaced events, not per firehose record; an async spawn failure (bad `bin`) surfaces as an error notification; `forge_loop_stop` refuses to kill a loop it never supervised (no target + nothing supervised is a no-op, not a blind `rauf loop stop`) and both stop and status scope to the supervised backlog via `--backlog`; and a brand-new session (no session entry of its own) rediscovers a still-running loop by scanning the project for the durable mirror, so cross-restart reattach actually works. `tests/test_adapter_host_neutrality.py` gains a contradiction guard (the `forge_loop_launch` redirect precedes the manual prose at Step 3b) and forbids the degraded tokens on Pi; `tests/test_build_adapters.py` asserts both extensions ship whole.

### Changed

- **rauf pin advanced to `@garygentry/rauf@0.15.0`.** rauf 0.15.0 ships Codex provider
  sandbox/network/approval config plus a batch of loop-runner fixes (Pi/cursor `E2BIG`
  prompt-delivery fixes, review-pass retry parity, rollback-safety halt, stale-profile
  detection, `--retry-blocked` backlog resolution) — none of it a capability feature-forge's
  stages depend on, so `minRunnerVersion` stays at `0.14.0`; only the provisioned default pin
  advances.
- **Loop-runner launch floor raised to rauf `0.14.0` (#234).** `loopRunner.minRunnerVersion` defaulted to `0.6.0` (the agent-selection-surface floor) while the same package pins `@garygentry/rauf@0.14.0` and requires 0.14's `backlog answer` for full post-run needs-human recovery (`RECOVERY_MIN_RUNNER_VERSION = "0.14.0"`). The Step 1c gate therefore green-lit rauf `0.13`, giving first-time users a passing compatibility verdict with a runner older than the version the package itself pins — after which needs-human recovery silently degraded to `backlog unblock` (the recorded answer never injected into the next iteration) and large Codex prompts kept the pre-0.14 argv-size (`E2BIG`) failure mode. The floor is now `0.14.0`, so the gate no longer accepts a runner too old for the recovery contract the stage describes; the agent-selection surface (present since 0.6.0) is subsumed by the higher floor. `RECOVERY_MIN_RUNNER_VERSION` now coincides with the floor but stays a conceptually distinct capability threshold (it only degrades recovery; the floor hard-stops the launch). Canonical change in `references/forge-config-schema.json` (the sole runtime-consumed default) with the executable-spec constant, the forge-5-loop gate prose, the ralph-loop contract, the mock-rauf fixture, and the `COMPATIBILITY.md` / `STATUS.md` / `README.md` / `AGENTS-SETUP.md` version references updated to match; adapters regenerated.

### Fixed

- **Pi post-fix verification now terminates on a clean report (#237).** The published npm manifest registers the bundled Forge agents with `pi-subagents`, and `state-verify` accepts and persists an attached zero-finding report for `passed`. Outcome-specific skill guidance and lifecycle regression coverage prevent a completed `findings-applied → passed` round from cycling back through verification.

## [0.18.0] — 2026-08-15

### Changed

- **rauf pin advanced to `@garygentry/rauf@0.14.0`.** The pinned runner now ships `backlog answer` — the operator recovery verb that threads a human's answer into the next loop iteration — which is the rauf half of the `loop-recovery` feature (forge-5-loop's Post-Run Recovery Procedure). `RECOVERY_MIN_RUNNER_VERSION` was already `"0.14.0"` in anticipation; the pin now matches.

### Fixed

- **Epic verify/fix branch exits now resolve the first actionable epic member instead of routing to the epic dashboard (#230).** A `stage-exit` serving `forge-0-epic` with an advancing outcome (e.g. after a successful verify or fix pass) unconditionally fell back to the epic dashboard — ignoring the member routing that standalone exits already performed. The exit now calls `_render_status` to find the first actionable member and routes to that member's live pipeline stage; the dashboard fallback fires only when no member is actionable or the status render fails, preserving the non-fabrication guarantee.

## [0.17.0] — 2026-08-12

### Added

- **A corrected claim can no longer survive elsewhere in the tree: `scripts/fix-sweep.py` sweeps the fix pass (#170).** A fix pass that corrected a false claim in the artifact a finding named left byte-identical copies of it standing in sibling specs, derived docs, and generated files — the finding closed, the claim survived. The new stdlib-only script (Python 3.10+, two subcommands, standalone `0`/`1`/`2` exit convention, no import surface) is wired into `skills/forge-fix/SKILL.md` at three points, with no step renumbering and the Step 6 re-verify gate untouched. **`sweep`** (Step 4, after edits land) extracts every removed line of the working-tree delta as a needle, drops needles under a 24-normalized-character floor and any suppressed by reflow or a pure move, then whitespace/punctuation-normalizes the whole tracked-plus-untracked corpus and reports each surviving copy with its provenance — always excluding `.verification/` records, and excluding `adapters/` when the drift gate is present so a regenerated bundle is never mistaken for an un-swept survivor. Each hit takes one of three dispositions (`FIXED`, `JUSTIFIED:`, `FALSE-POSITIVE:`) recorded in the fix ledger, with exactly one capped re-run, disposition-aware; a repository with no delta records an explicit not-run notice rather than a silent pass, and Step 5 staging is enumerated per path. **`plan-coverage`** (Step 2, before any edit) asserts the cardinality of a hand-authored work list against the findings document it claims to cover, naming every uncovered finding — a plan that silently drops one is caught at entry, not at re-verify. Four verification CHECKs assert the same properties from the other side: **CHECK-B29** and **CHECK-I24** (work-order cardinality — a work list that names fewer items than its source, reported by name as a `gap`), and **CHECK-I25** / **CHECK-S39** (internal consistency — a decision-bearing artifact that contradicts itself, reported as an `inconsistency`/`error`); all four degrade to `not-applicable` rather than hard-failing, and report without repairing. `fix-sweep.py` joins `RUNTIME_HELPERS`, so every adapter bundle ships it.

- **Zero-prompt loop launch: `loopRunner.reviewMode` + `loopRunner.agentMode` (#153, #164).** Two opt-in config keys gate forge-5-loop's two Step 2d `AskUserQuestion`s so a fully-configured loop can launch prompt-free. `reviewMode` (`"prompt"` default | `"always"` | `"never"`) gates the Run-mode question: `"always"` skips it and appends `--review` unconditionally (the rendered command still shows the flag — never hidden), `"never"` skips it and launches the bare command; under either, a **narrower situational retry-blocked question** still surfaces when — and only when — the backlog has blocked items (the review decision itself is fixed by the mode and never re-asked). `agentMode` (`"prompt"` default | `"auto"`) gates the agent question: `"auto"` suppresses only the interactive pick, resolving from `defaultAgent` (or the runner default), while the availability probe, the verdict classification (UNKNOWN hard-reject / UNAVAILABLE proceed-or-choose / probe-failure handling), and the Claude-alias model guard all still run, and the resolved `Agent: {id} (source: …)` line still shows. Defaults reproduce today's prompts byte-identically; `agentMode` is moot when the `agentArgument` capability gate is off (no second gate added). Mode semantics live in the forge-5-loop reference files (`runner-contract.md` / `agent-selection.md`), declared in the config schema and README table, and pinned by `tests/test_zero_prompt_loop_config.py`.

- **`epic-manifest.py set-charter`: edit mode can rewrite a member's charter through a sanctioned mutator (#166).** The charter is the member field most likely to need revision after creation (an ADR lands, a boundary moves, a feature turns out to own more than expected), yet it was the one field with neither a mutator nor a documented direct-edit carve-out — so a charter rewrite had to be inferred from the adjacent contracts rule, bypassing the atomic-write / re-validate / revision-bump guarantees. The new `set-charter {epic} {feature} --charter "…"` subcommand mirrors `set-dep`'s shape exactly (atomic temp-file + `os.replace`, full re-validation with byte-identical refusal, single revision bump via the shared mutator tail, semantic no-op writes nothing) and refuses a blank charter (`empty-charter`) rather than manufacturing a schema-shaped hole. Documented in the edit-mode operation table and the subcommand catalog; the "Contracts have no mutator" carve-out is now explicitly contracts-only, with charter rewrites routed through the mutator and EPIC.md re-synced in E5 like any other mutation (the #126 `adopt-feature` division of labor: the mutator changes the manifest, the agent owns the prose).

- **`.epic-state.json` has a schema: `references/epic-state-schema.json` (#181).** The epic verification state file sat between `pipeline-state-schema.json` and `epic-manifest-schema.json` with neither — its shape was pinned only by literal dict fixtures scattered across the test suite, the exact hand-authored-JSON drift class the R4 `state-*` verbs eliminated for the member file (the heredoc writer itself was already retired; the schema was the missing half). The new schema is minimal and additive — `epic`, `updatedAt`, `stages.forge-verify-epic` — and its `verifyEntry` MIRRORS `pipeline-state-schema.json#/definitions/verifyEntry`: the issue's preferred cross-file `$ref` is unresolvable by the repo's stdlib validator (`tests/_state_schema.py` resolves same-file refs only), so a full-object parity test pins the two definitions equal instead, and a digest pin with the sibling suite's re-pin protocol covers everything outside the mirror. `tests/test_epic_state_schema_conformance.py` proves the `state-verify` epic writer conformant across first-write, schedule→passed, findings lifecycle, and Commit-2 sequences; the literal fixtures in `test_auto_verify.py` / `test_stage_exit.py` / `test_epic_manifest.py` are retired in favor of schema-validated builders (with an explicit `conformant=False` opt-out where a test's point is a torn entry readers must tolerate).

- **The stage review-gate rule has a canonical home (#186).** Which "Review with User" steps block and which merely invite was stated exactly once, in one skill's prose — forge-4-backlog's deliberate non-gate sentence — and contradicted three-to-one by its blocking siblings, so an agent re-deriving the rule from the majority shape treated the non-gate as a gate and stranded the stage at `in-progress` with Step 7 unrun (observed live). `references/shared-conventions.md` gains a **Stage Review Gate** block declaring both shapes once — blocking (forge-1-prd, forge-2-tech, forge-3-specs: iterate until the user confirms) and non-blocking invitation (forge-4-backlog: a statement, then *proceed in the same turn* unless the user asks for changes; stopping on the invitation is a defect, not caution) — plus the rationale for the split (a blocking review guards freshly-interviewed content; the backlog is derived from approved specs, machine-validated, and re-confirmed at forge-5-loop's launch gate). All four authoring stages now point at the block by title, so a future divergence is a visible pointer edit rather than an invisible odd-one-out.

- **`docsStage` config: skip documentation without the per-run prompt (#165).** `forge.config.json` gains `docsStage` (`"prompt"` | `"skip"`, default `"prompt"`, declared in `references/forge-config-schema.json` and the README table). Under `"prompt"` the Documentation Decision Gate asks generate-vs-skip once per run (the #197 behavior); under `"skip"` forge-6-docs records the deliberate skip (`state-skip` → `stage-exit --outcome skipped`) with no question, so teams that document differently are never re-prompted and an epic can reach a fully-complete rollup with docs intentionally skipped. The refuse-to-erase guard is config-independent: docs that already exist are never silently reclassified. An unrecognized value behaves as `"prompt"`.

### Fixed

- **Copied reference files no longer carry Claude-only commands into non-Claude adapters (#167).** The self-containment pass copied the `references/` closure byte-verbatim into every bundle, so while non-Claude SKILL bodies were host-term translated, the reference files a model actually consults (`stage-exit-protocol.md` heaviest — 26 files with a literal `/clear` per bundle) still instructed Pi/codex/copilot/cursor/gemini sessions to run Claude's `/clear`, show `--host claude` in the scripted stage-exit stamp, and (on Pi) name `/feature-forge:` commands. `build-adapters.py` now runs the full per-agent host-term table over copied reference markdown as a distinct post-copy step (2c): Pi gets its real commands (`/new`, `/skill:`, `--host pi`), the other non-Claude targets get the host-neutral degradations (`--host generic`, "the host's question mechanism", and new article-aware `/clear` pairs so "needs a `/clear`" degrades to "needs a session clear" instead of a mid-clause splice), and Claude bundles stay byte-verbatim canon. Prose only — `.json` schemas and every non-`.md` suffix are untouched, and a small exempt set (`templates/` project scaffolding, `vendor-construct-inventory.md`, `portable-root.md` — mention-heavy meta-docs where substitution would falsify content) stays verbatim; canon meta-prose that *mentions* host terms (the stage-exit host-flag notes, the `--host` selection table) was reworded so it stays true under translation. `tests/test_adapter_host_neutrality.py` now scans the bundled references too (previously excluded as verbatim-by-design) and gains Pi coverage with its own token set (`/clear` and `/feature-forge:` forbidden; `AskUserQuestion` legitimate — the bundle ships the compatibility extension), and `tests/test_build_adapters.py` pins the per-agent translation, the JSON/exempt-file no-touch rule, and Claude's byte-verbatim guarantee.

- **The persisted `notes` baton is now read on the far side of the clear (#182).** Four authoring stages offered to write the top-level `notes` field at their exit, but the only reader was the navigator dashboard — so a note persisted for the next stage (the whole point of the field, given the stage-exit `/clear` recommendation) was never seen unless the user happened to re-enter through the navigator. Each downstream stage's Step 1 (forge-2-tech, forge-3-specs, forge-4-backlog, forge-5-loop) now runs a carried-over note check against the state file it already reads: a non-empty `notes` is surfaced verbatim and treated as stage input — never as an override of artifacts or config; conflicts are raised, not silently resolved either way. Overwrite-vs-append is settled as overwrite (documenting the existing `state-note` behavior): the note is a baton with latest-note-wins semantics, stated now at the write sites too (the four "Offer a note" closings tell the author to fold any still-relevant earlier note into the one combined string, matching the Immediate Downstream Note rule) and in the schema's `notes` description alongside its readership.

- **forge-4-backlog's `author-backlog` delegation has an explicit return contract (#187).** forge-4 is the pipeline's only Skill-tool delegation, and Step 4 said nothing about what happens when the sub-skill returns — while `author-backlog`'s own closing posture ("present the validated backlog and stop", correct for direct user invocation) arrived as the freshest instruction in context. In an observed run the agent adopted it, reported the validated result, and stopped, stranding the stage `in-progress` with Step 7 unrun. Step 4 now states the contract: control returns to **this skill at Step 5**; forge-4 owns the stage terminal; the sub-skill's pre-write approval gate is already satisfied by Step 3's approved plan (never re-ask) and its closing validate-and-confirm posture is subsumed by Step 5. Step 5 gains the matching **validation ownership** note — it is authoritative (it carries the missing-runner degradation rules the sub-skill lacks), a sub-skill validate never discharges it, and a clean re-run is cheap and idempotent.

- **Skill-tool delegation has a caller-side contract: the declared resume point (#188).** `references/stage-exit-protocol.md` specified only the callee side of nested invocation — `terminalOwnedBy: "outer"` told a sub-skill to stay quiet and return its result, and nothing told the caller it re-owns the terminal or where it resumes, so the callee's closing posture (the freshest instruction in context) silently ended runs one layer too early with the caller's remaining steps dropped. The protocol gains a **Caller-side resumption** section: on a sub-skill's return the caller re-owns the terminal, the callee's terminal instructions are void for the turn, and every Skill-tool delegation site declares one of two postures at the invocation — **delegate-and-resume** (name the step control returns to; forge-4 Step 4's #187 return contract is the cited worked instance) or **terminal handoff** (the invoked skill owns the terminal from there, declared rather than accidental). The known sites now declare: the navigator's `run` loop replaces "let it run to its natural stopping point" with an explicit return to step 2, its catch-up chain and verify-gate dispatches declare resumption and its `autoInvokeNextStage` advance declares the handoff, and forge-5-loop's Step 5b / 6.1 impl-verify dispatches declare that control resumes in-step. `tests/test_stage_exit_protocol.py` pins the section, bans the undeclared-return phrase from `skills/`, and pins each known site's declared resume point.

- **forge-5-loop's post-run recovery pass runs on every loop close, not only after a live `needs_human` event (#192).** The Post-Run Recovery Procedure — its §4 tree reconciliation included — was reachable only from `runner-contract.md`'s `needs_human` live-event handling, and its own step 1 exited early on "nothing to recover", *before* step 7's §4 call, contradicting §4's "runs on every recovery pass" claim. A run that stranded uncommitted work without emitting `needs_human` (the original report's shape: items failing a shared final acceptance criterion left 84 files staged, guaranteeing the next launch failed a precondition the previous run created) got no post-run reconciliation at all — only the next-launch 1g backstop. forge-5-loop now enters the procedure at a new **Step 4c** on every run close, before Step 5 writes state, so the tree §4 inspects is exactly what the run left; step 1's nothing-to-decide path skips to step 7 (whose §4 still runs) instead of exiting around it; an empty affected set never selects `resolved` (the Step 7 ladder falls through to its count-based rungs); and the `item_blocked` handler points at the pass — a blocked-only run now reaches the plain-blocked unblock offer, which also removes the caveat recorded on #193's close.

- **The epic-level doc offer fires once per epic, on the final docs run (#173).** `forge-6-docs` offered the epic-spanning architecture document whenever `rollup.complete == rollup.total` — but that rollup counts *orchestration* (loop) completeness, so in an epic implemented before any docs were written the offer fired on every member's docs run, starting with the first, when accepting would source the epic doc from a fraction of its inputs. `render-status` member rows now carry `docsStatus` (the recorded `stages["forge-6-docs"].status`, or null), and both offer surfaces gate on it: forge-6-docs offers only when every *other* member's `docsStatus` is `complete` or `skipped` (the current member counts as satisfied by its in-flight run; #197's deliberate skip satisfies by decision, contributing charter/contracts only to the synthesis), and the navigator's completion hand-off offers the epic doc only when every member's docs are settled — pointing at the next docs run otherwise.

- **A verify `skipped` write can no longer demote a resolved verification (#203).** Choosing "Generate docs anyway" / "Continue without re-verifying" at an entry gate unconditionally wrote `skipped` over the existing `forge-verify-*` entry. Over `findings-applied` (or `passed`) that is a strict demotion — both count as complete-for-orchestration (`_VERIFY_ORCH_COMPLETE`), so one prompt answer silently dropped an epic member from the rollup, fabricated `unmetDeps` on every dependent, and routed `nextCommand` at a member with nothing wrong (the observed 5/6 → 1/6 collapse; introducing commit `5febccc`). `state-verify --status skipped` now **fails closed** when the prior status is `passed` or `findings-applied`, naming both statuses and the honest alternatives (re-verify, or `passed` with the report attached to accept residuals); a deferral over a resolved status needs no write at all, because the entry already records that re-verification is outstanding. Every skip-writing surface was reworked to match: forge-6-docs' Impl-Verify Backstop case 3 and forge-5-loop's backlog-verify case 2 now proceed with nothing written, the forge-5-loop Step 5b / forge-4-backlog skip fences and the Standard Verify Gate's "Skip for now" are scoped to absent/unresolved entries, and `skipped` re-writing `skipped` stays an idempotent refresh. The guard applies to epic-target writes identically.

- **A feature can close with documentation deliberately skipped — recorded honestly, never as a false `complete` (#197).** Previously `forge-6-docs` was mandatory in every mechanism that could express "done", so the only way to finish a pipeline without docs was to claim the stage ran (`state-complete` with no `--artifact` — a status misstatement whose only trace was an empty artifacts array). Four surfaces gained the vocabulary together: the schema adds a forge-6-docs-scoped `docsStageEntry` (`skipped` status + `skippedAt`; the shared `stageEntry` enum deliberately does NOT carry `skipped` — a skipped PRD or specs stage is not a representable state); a ninth state verb, `state-skip`, is the only sanctioned writer (it refuses to erase a record of docs that exist, while correcting the artifactless-`complete` workaround is sanctioned as the migration path); next-stage selection treats `complete` and `skipped` both as done (`next_stage()`, the verify reverse walk, and epic-manifest's `_next_production_stage` mirror — so `nextStage: null`/`complete: true` is reached honestly, rank-features and the epic dashboard never re-offer the stage the operator explicitly skipped, and an actionable member's recommendation falls through to its real outstanding work); and `DocsOutcome` gains `skipped`, routed by `stage-exit` exactly like `complete` (standalone navigator completion, live epic member handoff) with wording that says the docs were deliberately skipped, never that they exist. The skill gained a Documentation Decision Gate ahead of source gathering: an explicit generate-or-skip choice, with the skip persisted through the verb before the stage may close.

### Fixed

- **`state-verify --status findings-applied` no longer requires an artifact version it never uses (#202).** Recording a verify result resolved the production stage's `version` for every non-`skipped` status, so a completed stage whose `state-complete` call omitted `--version` (22 of 23 loop stages in the reporting project) exited 2 for *every* status that could move the entry forward — including `findings-applied`, whose entry is built entirely from the prior report plus `fixedAt` and deliberately records no freshness. The lookup now runs only for the statuses that consume the revision (`passed`, `findings-reported`, `auto-verify-pending`); `skipped` and `findings-applied` skip it. This restores the recovery path for state damaged by a demoting skip write (#203) without falsifying `completedAt` via a re-run of `state-complete`. Remedies (b)–(d) from the issue (defaulting a missing version, attaching one without rewriting timestamps, early surfacing) remain open follow-ons.

### Added

- **The single-writer state threat model is a recorded owner decision (#180).** `references/decisions/single-writer-threat-model.md` records what previously lived only in writer docstrings and one feature's requirement: concurrent multi-session mutation of forge state is out of scope (single writer assumed; atomicity protects against interrupted writes, not simultaneous writers), the standing posture is detection-not-locking (opportunistic fail-loud detection is welcome if proposed, a locking mechanism needs its own PRD and would be false comfort alone — git, the two-commit protocol, and adapter regen are equally unsynchronized), and the residual epic-root exposure (a lost `revision` increment on `epic-manifest.json` can classify a stale epic verification as `fresh` when two sessions work different members of one epic) is accepted and documented. `CHECK-S27`'s guidance in `forge-verify` and the specs checklist now cross-link the decision so a verifier answers the check by citation, never by designing a mechanism; the `_write_state`/`atomic_write` docstrings point at the record. This was the requirements-level gate for the Track C state-integrity work (#181/#182).
- **`doctor` reports duplicate `forge.config.json` keys (#201).** A hand-edited config with a repeated key (last value wins) previously surfaced only as a per-invocation stderr warning — repeated on every `forge-session.py` call and absent from the one command whose job is config health. `doctor` now carries the duplicate key names the loader already computes: a `duplicateConfigKeys` list in the `--json` payload (`[]` = checked and clean, empty on a missing/unparseable config since `configExists` owns those findings) and a `! duplicate config keys (last value wins): …` line in the human report, alongside the existing `invalidAutoVerifyKeys` finding. The stderr warning is unchanged.

## [0.16.0] — 2026-08-08

### Added

- **The loop's needs-human dead end is now a recoverable surface: decisions persist, clusters consolidate, topology is measured, and a resolved run resumes (loop-recovery, #204; closes #189, #190, #191, #193, #194, #196).** Previously a needs-human answer lived only in the conversation that collected it — nothing persisted it, nothing applied it, resolved items stayed `blocked`, and every pending item was blamed on "iteration limit reached" whether or not the counters supported that. Five surfaces changed together. **Decisions persist and are applied, provably:** answers land in `{backlogDir}/{stateDir}/forge-decisions.json` (schema: `references/forge-decisions-schema.json`) via three new `forge-session.py` verbs — `decision-record` (append-only, atomic, written the moment `AskUserQuestion` returns and *before* anything acts on the answer, with an early cancel recorded as a deferral), `decision-list --unapplied`, and `decision-apply` (stamped only after the runner apply succeeded). The runner unblock is required, not advisory — `backlog answer` on runners that support it, a documented degraded `backlog unblock` below that floor — and recovery then re-reads each affected item and proves it left `blocked`, with "ran but nothing moved" named a failed recovery. **Systemic causes surface once:** blocked/needs-human items are clustered by reason similarity (token-set Jaccard union-find), and a cluster of two or more emits exactly one consolidated decision naming every member and its blast radius ("this one decision gates 13 of 16 items"), persisted under a shared `clusterId`. **Topology is measured, not guessed:** a new `backlog-topology` verb (`compute_topology`) reports roots, per-root gated counts, max chain depth, and the selectable frontier, with single-root-fanout and chain-depth warnings — consumed advisorily at backlog authoring, as `CHECK-B28` in verify-backlog, and beside the iteration math in the loop's confirmation block. **Attribution is honest:** "iteration limit reached" is rendered only when the limit was actually hit with selectable work remaining; otherwise the report names the blocking roots and the subtree each gates, and `stage-exit` accepts `--cause dependency-starvation` (legal only with `--outcome partial`). **The loop can finish what a human unblocked:** a sixth `resolved` outcome — gated on all decisions applied, a clean tree, and items demonstrably unblocked — routes to relaunching the loop instead of parking at the navigator, per the new Post-Run Recovery Procedure (`skills/forge-5-loop/references/recovery-procedure.md`) with its Stranded-Work Pre-flight, which stops a relaunch over another run's uncommitted work instead of letting it collide. A loop-outcome compliance probe joins the eval suite. (The remaining known gap — the recovery procedure is only entered from the `needs_human` handler, with no unconditional post-run reconciliation hook — is tracked as the rescoped #192.)

### Fixed

- **The `forge-verifier` return contract is explicit, and every dispatcher gates against truncated returns (#183).** Two ~130k-token verifier runs each returned only their opening sentence — the Agent tool hands the parent nothing but the subagent's *final* message, so a run that ends on a status line silently drops its entire digest, and in the observed incident the recovered digest carried two BLOCKER findings that would otherwise have been converted into a pass. Three surfaces changed: `agents/forge-verifier.md` now states that the last message is the only thing the parent receives and that the final response must BE the complete Output Format report (never a summary, opening line, or "the report follows"); `skills/forge-verify` gained a parent-side **Truncated Verifier Returns** gate (new section in `references/findings-template.md`, wired into the Synthesize step) — a return without the report structure (`# Verification Report:` header, `## Findings`, `Checks Executed:`) is a non-answer: resume the agent via `SendMessage` (it replays the digest from its transcript with zero further tool calls) or re-dispatch, and never synthesize, write a findings document, or record a verify result from it; and `forge-5-loop`'s two impl-verify dispatch sites point at the same gate before anything is recorded. Ride-along: `epic-manifest.py`'s module docstring now lists the `adopt-feature` verb it already shipped.

## [0.15.0] — 2026-08-05

### Added

- **Scripted stage exits now cover all nine pipeline-advancing skills (stage-exit-coverage epic, #184).** The scripted exit contract (`forge-session.py stage-exit`) previously reached only `forge-0-epic` … `forge-4-backlog`; the paths most likely to branch or divert were the ones left hand-rolled, and each produced a filed, user-visible failure. The epic closes all four: the CLI's stage enum was widened so `forge-5-loop`/`forge-6-docs` exits are accepted instead of exiting 2 (#172); `forge-verify`/`forge-fix` gained a complete terminus with `--served-stage` routing, so a finished diversion returns the pipeline thread to the production stage it served instead of silently dropping it (#176); epic edit-mode exits resolve the selected member's *actual* recorded stage rather than always naming `forge-1-prd` (#175); and a configured in-stage auto-verify is persisted to disk as durable `auto-verify-pending` debt *before* control can be lost, so a dropped `runInStageVerify` dispatch stays visible instead of vanishing without a trace (#163). Also ships typed branch outcomes, the capability/host split, and the `state-verify` verb (verification results now land in pipeline state through a verb, not a hand edit). The merge includes Phase 1 of the epic's remediation plan: the scheduling boundary no longer overwrites a `findings-reported` entry at the current artifact revision (which silently deleted `findingsFile`/`findingsCount`), torn state files with non-string `status` values no longer crash the dashboard/navigator, the three in-stage dispatch sites carry the literal `owner: nested` token, and `_loop_route` gained live-report parity. Behavior-preserving for stages 0–4 apart from the #175 routing correction and two verify-first ordering fixes. Maintainer docs: `docs/architecture/stage-exit-coverage/`.
- **Anti-churn verify-loop hardening (#185).** Protocol hardening against the fix/re-verify churn that cost the stage-exit epic nine implementation verify rounds (forensic basis: of its 12 stage-blocking `error` findings, 11 lived in comments or test narration, and from round 2 on every blocking error was introduced by the previous round's fix). Five rules: **R-05 severity floor** — `error` requires a behavioral, CLI-output, or decision-bearing consequence; prose-only inaccuracies cap at `inconsistency`; an advisory-only report records `passed` **with the report attached** and never fences a fix round. **R-06 scoped re-verify + decision immunity** — a re-verify confirms the prior report's findings and the fix delta, never a fresh full-checklist sweep, and a finding with a recorded decision is never filed. **R-07 round ledger + escalation** — rounds are counted from round-discriminated findings filenames (`VERIFY-{mode}-{date}-round{N}.md`, no overwrites), and a second consecutive red round presents the digest for explicit disposition (accept residuals / another pass / stop) instead of recommending another fix pass. **R-08 narrative rule** — fix passes write no empirical/quantified claims into shipped comments; meta-guards declare an enumerated protection set with explicit non-goals. **R-09 entry-gate doctrine** — `findings-applied`/`findings-reported` no longer sail through the forge-5-loop/forge-6-docs entry gates silently; each gets its own recommended-action prompt and proceed-anyway persists the deferral. A tabletop replay of the epic's nine rounds under these rules terminates the chain at round ≤ 3, and a new GATE-P2 `escalation` eval scenario scores the digest being surfaced from the skills alone.
- **`validate-traceability.py` gained an allowlist for requirement ids a suite quotes but does not own.** A spec suite that quotes an antecedent feature's test docstrings verbatim inherits that feature's `REQ-` ids, and the validator counted every one as an orphaned reference — a red gate with no correct resolution short of not quoting the source. Declare such ids with a repeatable `--allow-orphan REQ-ID`, or list them one per line in `<specs-dir>/.traceability-allowlist` (blank lines and `#` comments ignored), which the validator discovers automatically. The subtraction is deliberately **not** silent: allowed ids are still printed under `ALLOWED FOREIGN REFERENCES`, an entry matching nothing is printed under `STALE ALLOWLIST ENTRIES` (advisory — it does not fail the check), and `--json` gained `allowed_orphans` and `unused_allowlist_entries` so a programmatic reader can see what was suppressed rather than inferring it from a green result. The ids live beside the suite that quotes them rather than inside the validator, because this script ships into every adapter bundle and every consuming repo, where one project's foreign ids are meaningless.
- **`state-complete --version` rejects values below 1, and `state-artifact --path` enforces feature-directory containment.** Both narrow an existing flag's accepted domain on a shipped write path, and both reach npm through the bundled `adapters/` tree, so they are recorded here rather than left to the pipeline's own specs. `--version 0` previously wrote `"version": 0` into pipeline state; it now exits 2 with `Error: --version must be a positive integer; got 0` before the state file is loaded, so a rejected call leaves the file byte-identical. `--path` now rejects absolute paths, empty values, and any `..` segment that would escape the feature directory, naming `--path` in the diagnostic rather than the `--findings-file` label the shared validator was originally written for.

## [0.14.0] — 2026-07-30

### Added

- **`forge-session.py effective-config` resolves the `loopRunner` block, so no skill reads the config schema for defaults (R5).** `forge-4-backlog` and `forge-5-loop` needed the resolved loop-runner configuration — 22 fields, each with a schema default a project may override — and the instruction was to read the ~2k-word `references/forge-config-schema.json` and merge the defaults inline. That is both expensive on every launch and a live source of "the model mis-merged the defaults" errors. The new subcommand extracts `properties.loopRunner.properties.*.default` from the schema at runtime and merges the project's `loopRunner` block over the top, so the **script** reads the schema and the model never does; because the schema is the input rather than a transcribed table, it stays the single source of truth with nothing to drift. Stdlib-only (`json.load` plus dict access — CI has no `jsonschema`). The exit split is deliberate and is the part worth knowing when diagnosing an environment: a **missing or corrupt `forge.config.json` resolves to pure defaults at exit 0** (what an unconfigured project should get), while an unreadable, unparseable, or `loopRunner`-less schema exits **2** with nothing emitted, because with no defaults to resolve a partial merge would be worse than failing. Command templates are returned literally, placeholders intact. Documented in `docs/clean-env-repro.md` and the docs-site troubleshooting page alongside `doctor`. Measured **−2,579 / −2,587 tok** on the two consumer launches.
- **Seven `state-*` verbs author `.pipeline-state.json`, retiring every hand-written state edit (R4).** Stages used to edit the state file directly, which is why their instructions pointed at a 191-line JSON Schema, and which left rules that only ever existed as prose to be *performed* by a model: bump the version, refresh `updatedAt`, record `basedOnVersions`, set `commitHash` to null for commit 1, and mark downstream stages stale when they were built on an older version. `state-enter`, `state-artifact`, `state-complete`, `state-branch`, `state-note`, `state-decision` and `state-ecr` now cover all seven touch points — one verb per mutation, deliberately not one generic patch command, since a generic patch would leave the model authoring the JSON fragment that is most of the defect surface. Four properties of the shared write path are load-bearing: the writer resolves **fail-closed** (a bare `--feature` matching both a standalone feature and a same-named epic member is refused with exit 2 rather than silently mutating the wrong one at exit 0 — which is why `--epic` is mandatory for members); a **corrupt state file is refused, not overwritten** (the read path's tolerant downgrade-to-`{}` would atomically replace a recoverable file with a near-empty one); a verb **never creates a feature directory**; and the schema-required top-level fields are seeded on every verb, so `state-branch` firing before the entry stamp still produces a valid first write. `state-complete` folds in the version bump, the provenance record, `commitHash: null`, and the **downstream staleness cascade** (`forge-2-tech`…`forge-6-docs`, only where a `complete` stage recorded an older version; `forge-1-prd` is never a target), and its three branches keep the two-commit git protocol intact — `--commit-hash` for commit 2 (guarded on the stage already being complete), `--resumable` for the failed-commit-1 revert (status only: no completion, no version bump, no cascade), and the plain completion otherwise. The surrounding interactive protocol is unchanged: stage-entry classification, the branch prompts and their visible reconciliation note, the "offer a note, don't force one" statement, and the never-`--amend` commit sequence all keep their exact prose — the verb call slots in where "edit the JSON" was, and the entry stamp is still left uncommitted so an interrupted run is still classified as interrupted. `references/pipeline-state-schema.json` is no longer read per stage but remains the CI source of truth: a stdlib drift guard validates every verb's output against it.

### Changed

- **The verification checklists are split one file per verify mode, plus an orchestrator-only findings template (R1).** A single 477-line `verification-checklists.md` carried every mode's checks *and* the orchestrator-facing findings material, so a `forge-verifier` leaf running `prd` mode loaded all six modes plus instructions addressed to the role that dispatched it — and a parallel fan-out paid that per instance. It is now `skills/forge-verify/references/verification-checklists/{prd,tech,specs,backlog,impl,epic}.md` (15 / 17 / 38 / 27 / 23 / 10 checks) plus `references/findings-template.md`. **No check was added, dropped, or renumbered** — the CHECK-IDs were copied across verbatim. A leaf reads exactly one mode file; the orchestrator reads the template when it writes the findings document, so the dual-role separation shipped in 0.12.1 is strengthened rather than reintroduced as a risk. The "executed N of M checks" self-check also got *more* robust: it previously carried approximate totals (it said `tech ~15` against a file holding 17), and each mode file now has an exact count with the skill's expected-count table reconciled to it and drift-guarded. Measured **−4,736…−5,810 tok** per verifier leaf depending on mode, and **−5,065 tok** on the orchestrator's template read.
- **The navigator reads `references/process-overview.md` only when asked how the pipeline works (R3).** It was an unconditional setup step, so a dashboard render — the navigator's most common job, and one needing no pipeline theory — paid for 143 lines every time. The read now sits behind a branch taken for architecture / stage-ordering / "explain forge" questions; routine status rendering does not open it. The file is unchanged and still cited, so it still ships to every adapter. Correctly attributed: the gating clause is **+40 tok always-paid** on every navigator invocation, including the architecture path where the file still loads; a routine render nets **−1,684 tok**.
- **The loop runner contract is split into always-loaded and agent-conditional halves (R6).** `skills/forge-5-loop/references/runner-contract.md` (341 lines) carried three sections that only mean anything when agent selection is enabled — the agent-selection surface, its Claude-only model-alias guard, and the optional-flags catalog. Those moved to a new `references/agent-selection.md` (116 lines), cited **only from inside the Step 2d capability gate**, while `runner-contract.md` (248 lines) keeps what every launch needs: model-selection precedence, run mode, launch detail, monitor arming, event reactions, and the inform-user template. The `forge-5-loop` body edit was a strict citation swap with zero net lines, since that body is at 298/300 lines and CI hard-fails on the cap. **The saving is conditional on a non-default config, and this is easy to misread:** the gate condition is a non-empty effective `loopRunner.agentArgument`, and the config schema *defaults* that field to `--agent {agent}` — so on a default-configured project the gate is **on**, the conditional file **is** opened, and all 116 lines load. The two nested sections are gated for *application*, not for *load*. A gate-off launch nets **−1,151 tok**; a gate-on launch nets **+98**, so R6's realized instruction-load saving on a default-config run is approximately zero and a project only reaches the saving by explicitly blanking the field. The structural win (the conditional material is separable, and the gate is real) stands either way.
- **Drift-guard coverage extended to every split or relocated surface.** Splitting a file creates a new way for two files to disagree, so each unit shipped with a stdlib pytest asserting against the canonical `skills/` surfaces (never generated `adapters/` output): `test_verification_checklists_split.py`, `test_process_overview_read.py`, `test_effective_config.py`, `test_state_verbs.py`, `test_state_schema_conformance.py`, `test_state_verb_call_sites.py`, `test_stage_constants_parity.py`, `test_runner_contract_split.py`, plus two catch-alls — `test_reference_citations.py` (every citation names a real file **and** every reference file is still cited by ≥1 skill body, since the adapter build fans references out *by citation* and a dropped citation silently unships a file while the forward check stays green) and `test_always_loaded_surface.py` (the frontmatter descriptions and the session hook's common-path output are guarded against growth). `scripts/check-spec-purity.py` also gained **Rule 6**, which fails any shell fence that expands `$R` without binding it in-fence — the companion to Rule 5's prelude byte-identity check, closing the other half of that class.
- **Documentation:** `docs/architecture/context-efficiency/` documents the five units, the new subcommands, and the integration rules for anyone editing these surfaces next.

### Notes

- **R2 (within-file plugin-root prelude dedup) was scoped out and does not ship.** Read its absence from the implementation as intended, not as a coverage gap. It was gated on a compliance probe that cleared the stated objection — all five runs resolved the root correctly and executed clean — but byte-identity came back 4/5, so the "byte-identical to today" claim is not unconditionally true. The deciding argument is the risk/reward the probe left standing: R2 was the smallest payoff of the six (~2k tokens across four files) and the only unit that converts a *verbatim copy* into a *reconstruct-from-memory* operation, while the same baseline work found the productive direction to be *removing* compliance-dependent operations. Dropping it cost nothing structurally, because each unit was required to be independently shippable from the start. The `r2-prelude` probe stays in `eval/run-compliance-eval.py` as the gate if the idea is revived — re-run it at a larger sample first, since 4/5 on n=5 is a wide interval.
- **Zero behavioral diff is the bar these changes were held to.** Every unit is a relocation of instruction text or a script extraction, never a rewording of an interactive protocol: the question turn structure, the decision-support framing, the branch prompts, the stage-entry and stage-completion classification, the two-commit git sequence, the verify gates and the anti-fabrication guards all keep their exact prose. Each unit is also independently revertible, so a regression in one reverts one change rather than the batch.
- **How the savings were measured.** Each unit had to show a measured net reduction on its own targeted invocation against a baseline **re-measured at implementation time**, not against the original audit snapshot, which had drifted. Method: line and word counts over the canonical surfaces at ~1.3 tokens per word, with always-paid growth subtracted from the saving rather than omitted. Read frequency came from a 188-session transcript corpus — which is also why **R4 and R5 claim no per-stage saving**: the two schemas they stop loading were read 2× and 1× respectively across that entire corpus, not once per stage, so their figures are the static delta on the invocations where the read does occur. Both units stand on determinism and drift removal, which hold at any read frequency.

## [0.13.0] — 2026-07-27

### Added

- **Pi adapter bundle foundation.** `scripts/build-adapters.py` now emits `adapters/pi/` as a self-contained Pi package: generated skills, package metadata, and an `AskUserQuestion` compatibility extension, so the interactive forge interview runs in Pi's TUI instead of degrading to prose prompts. Pi skill bodies preserve `AskUserQuestion` while translating forge slash commands to `/skill:*` and adding Pi-specific host notes.
- **Pi `AskUserQuestion` extension.** A vendored snapshot of [`@juicesharp/rpiv-ask-user-question`](https://www.npmjs.com/package/@juicesharp/rpiv-ask-user-question) 2.1.0 (MIT), carried under `adapter-src/pi/extensions/ask-user-question/` with a documented four-patch delta — see `adapter-src/pi/UPSTREAM.md`. It renders a tabbed questionnaire (1–4 questions, 2–4 options each) with option descriptions, focused previews, multi-select, per-option notes, terminal-row-aware overflow scrolling, a collapsible overlay, a final Submit review, and an automatically appended free-text row. On RPC/ACP hosts that report a UI but cannot render a custom overlay (the VSCode pendant, Zed, Paseo) it degrades to sequential `select`/`input` dialogs rather than telling the model the user never saw the questions. It ships **inside** the bundle rather than as a dependency because the pipeline's interview stages have no fallback question mechanism on Pi, so a missing `pi install` would be a hard stall rather than a degraded experience; vendoring also puts the tool name under our control, so it registers as Claude's `AskUserQuestion` and canon needs no build-time rename. The extension seeds `FEATURE_FORGE_ROOT` from its own package root so generated forge shell snippets prefer the active Pi adapter over unrelated local Claude installs.
- **forge's custom agents are dispatchable on Pi.** The generated `adapters/pi/package.json` now declares the bundle's `agents/` directory through a top-level `pi-subagents` key, and every Pi skill's host notes name the real dispatch shape (`{ agent, task }`, or `{ tasks: [...] }` for parallel fan-out) instead of asserting that Pi has no subagent construct at all. Previously both halves were broken together: the agent files were emitted but declared to nothing, and the bundle's own prose told the model to give up — so `forge-verify` silently degraded to improvised substitutes rather than running the official gate. The key follows [`pi-subagents`](https://github.com/nicobailon/pi-subagents) 0.35.1's manifest schema and is emitted unconditionally; with no such extension installed it is inert and the host notes keep inline execution as an explicit fallback, so the bundle gains no runtime dependency.
- **The Pi agents' frontmatter is translated into `pi-subagents`' schema, so `forge-verifier`'s read-only contract is tool-enforced, not just prose.** Previously only `{name, description}` mapped and every structural key was drop-recorded, so a dispatched verifier ran with the host's full default tool set — `write`/`edit` included — while its own prompt declared it read-only. `PiEmitter.emit_agent` now maps canon's `tools` onto Pi builtin names (`Read, Glob, Grep, Bash` → `read, find, ls, grep, bash`; spec-writer adds `write, edit`), `maxTurns` → `turnBudget` (as a single-line JSON string, because pi `JSON.parse`s it), `effort` → `thinking`, `memory: project` → `{scope, path}`, and `skills` through. It also derives three Pi-only fields from the tool allowlist: `acceptanceRole` (`writer` iff the agent carries `Write`, else `read-only`), `completionGuard: false` on the read-only agents (they carry `bash`, which pi-subagents treats as mutation-capable, so a correctly no-op verify would otherwise be judged a failed implementation), and `inheritProjectContext: true` (non-builtin agents default `false`, which would blind a forge agent to the target repo's `AGENTS.md`). `model` stays dropped by design (`opus`/`sonnet` are Claude aliases, not Pi model ids; the documented override is `subagents.agentOverrides.<name>.model`). Every mapped shape was confirmed by round-tripping the generated files through pi-subagents 0.35.1's real `loadAgentsFromDir`, not its README — two shapes bite silently otherwise (a `turnBudget` YAML block makes `JSON.parse` throw; a block-sequence `tools`/`skills` is dropped by Pi's line parser, so both emit comma-joined).
- **The npm installer registers the Pi agents too, not just the package install path.** The `-a pi` install copies the bundle under `skills/`, which `pi-subagents` discovery does not scan as a package root — so the manifest key above never reached installer-based setups, only working-tree dev setups listed in Pi's `packages`. The Pi target now carries a `mirror` placement (parallel to Codex's `.codex/agents/`) that copies `agents/*.md` flat into the scope `pi-subagents` scans directly: `~/.pi/agent/agents/` with `--global`, `.pi/agents/` for a project install. Because that second root differs by scope where Codex's does not, `PlacementSpec` gained optional `globalBaseDir`/`projectBaseDir` overrides (mirroring the existing `AgentTarget` split); Codex's scope-invariant placement is unchanged. The scope directories were confirmed read-only against pi-subagents 0.35.1's source (`discoverAgents`), not just its README.
- **Pi install/root-discovery support.** `forge-root.sh` now discovers Pi installs under `PI_CODING_AGENT_DIR`, `~/.pi/agent/skills`, project `.pi/skills` (including ancestor project roots), and Pi package clone/cache layouts while keeping `FEATURE_FORGE_ROOT` as the escape hatch. The npm installer accepts `-a pi` with scope-correct destinations (`~/.pi/agent/skills/feature-forge` globally, `./.pi/skills/feature-forge` for projects), validates the Pi bundle metadata/extension, and advertises Pi package metadata in the real installer `package.json`.

### Changed

- **rauf pin advanced to `@garygentry/rauf@0.13.0`.** That is the rauf release which ships the `--agent pi` loop preset, so it is what makes the Pi pipeline's loop stage actually drive Pi. `forge-5-loop` is agent-agnostic — it probes `rauf agents --json` and offers one option per advertised row — so Pi loop support is delivered entirely by the runner, and a fresh install pinned to an older rauf would complete the Pi pipeline right up to the loop stage and then never list `pi` as an agent. `minRunnerVersion` deliberately stays at **0.6.0**: it is a single floor applied to every agent, and raising it would force an unnecessary rauf upgrade on Claude and Codex users who gain nothing from it. The Pi-specific requirement is recorded as prose in `COMPATIBILITY.md` under "Per-agent runner requirements" instead.
- **The generator can emit a source *tree*, not just a single file.** `adapter_tree()` joins `adapter_source()` in `scripts/build-adapters.py`, walking an `adapter-src/<agent>/<subdir>/` tree in sorted order and emitting it at the same relative path in the bundle. Source layout now mirrors emitted layout exactly, because the Pi extension resolves its own bundle root by walking up from `import.meta.url` — a source tree at a different depth typechecks and tests green in-tree while resolving the wrong root once emitted. Files that cannot carry a line-comment header (`LICENSE`, `locales/*.json`) are emitted verbatim; the existing regen-and-diff drift guard already covers them, and the MIT license text must stay byte-identical for its attribution to hold.
- **Real code that a target agent loads is verified before it ships.** Most of `adapters/` is generated from canon prose; the exception is code a target agent executes at runtime, which now lives under `adapter-src/<agent>/` and is read by the generator at build time. `scripts/validate.sh` iterates `adapter-src/*/` and runs each directory's own `verify` script, so a future agent's source is enrolled in CI just by existing; a directory with no verifier is reported as a visible `SKIP`, never a silent pass. Pi's verifier is `tsc --noEmit` over the whole extension tree plus `node --test`, which drives the real extension through a fake `ExtensionAPI` and a headless TUI: registration and tool name, `FEATURE_FORGE_ROOT` seeding, the questionnaire state machine (tabs, single- and multi-select, preview pane, cancel), the RPC fallback, and the validation guards. Those assert *feature-forge's* contracts rather than restating the vendored package's own suite, so the question the gate answers is "did an upstream refresh change what we depend on".
- **A bare `install` / `update` (no `-a`) now targets Pi too, wherever Pi is detected.** `AGENT_IDS` gained `pi`, and a subcommand run without `-a` installs into every *detected* agent (`installer/src/cli.ts`) — so for an existing user with Pi on the machine, the next routine `feature-forge update` performs a first-time Pi install rather than only refreshing the agents they already had. That is the intended behavior (it is how every other supported agent is picked up), but it writes to a scope the user never explicitly opted into, so it is called out here rather than left to be discovered. Scope Pi out with `-a <agent>`, or preview any run with `--dry-run`.
- The file-wide `# ruff: noqa: E501` on `scripts/build-adapters.py` is removed; the long lines it masked left with the extracted TypeScript, restoring the E501 floor that `ruff.toml` requires for future edits to the generator.

### Fixed

- **The Quality Gate ran on Node 20 and silently tested almost nothing on the installer side; it now runs Node 22.** Two defects shared this root cause. First, `installer/`'s test suite is written in TypeScript and executed by Node's *native* type stripping — `installer/tsconfig.json` sets `include: ["src"]`, so the tests are never compiled — which Node 20 cannot do. `node --test` therefore discovered **zero** files, printed `# tests 0 # fail 0`, and the gate reported `PASS: installer build + node:test suite`. All 182 installer tests had been passing locally and running nowhere in CI. Second, `adapter-src/pi`'s verifier loads `@earendil-works/pi-coding-agent`, whose bundled `undici` calls `webidl.util.markAsUncloneable` — a symbol that does not exist on Node 20 — so every Pi extension test aborted in its `before` hook. The gate now pins Node 22, matching `os-matrix.yml` and `npm-publish.yml`, and the gate's own comment records why the floor exists so it is not lowered again. `adapter-src/pi`'s `test` script also stops passing a `**` pattern to `node --test` (glob support only landed in Node 21; before that the pattern is read as a literal path) in favor of a shell-expanded file list.
- **Pi bundles now recommend Pi's `/new` for a fresh session instead of Claude's `/clear`.** Between stages forge tells the user to start a clean session; on Pi that command is `/new`, not `/clear`. Previously the Pi adapter degraded `/clear` to the same host-neutral phrasing every non-Claude adapter uses ("clear your session / start a fresh session"), which named no real Pi command. The Pi host-term table now maps `/clear` → `/new` (backticks preserved, so it reads as a command) and routes the scripted stage-exit stamp to a new `forge-session.py --host pi` that emits `/new` wording and `/skill:` next-commands (including the structured `nextCommand`/`verifyCommand` directives). The fix is centralized in the two translated surfaces — skill bodies and the stage-exit helper — so it covers every place the user is shown "start a fresh session for the next command"; the self-contained verbatim `references/` copies still carry Claude wording by design (secondary model-facing guidance, not the primary instruction). `/new` was verified as Pi's real command against Pi's own `quickstart.md`/`extensions.md`.
- `installer` now runs `npm run build` before `npm test` (a `pretest` script). The suite imports compiled `dist/`, so a stale build silently tested old code — observed producing both false failures and, worse, false passes.
- Pi adapter generation now translates `/feature-forge:*` command references in Pi skill and role frontmatter descriptions, not just skill bodies, and excludes Python cache byproducts from copied reference trees so installer/package outputs do not ship `__pycache__` or `.pyc` files.
- Pi adapter generation now also rewrites `/feature-forge:*` slash commands inside copied Pi reference files and runtime helper scripts, so helper-generated next-step text can point Pi users at `/skill:*` commands.

### Known issues

- **A damaged Claude install alongside a healthy Pi install can serve Claude the Pi bundle.** `forge-root.sh` resolves the bundle a session should use, and its long-standing rule is that a *complete* install beats a *partial* one: a candidate root that is missing a core asset is remembered as a fallback while probing continues. If a Claude install is partial (mid-reinstall, a half-deleted directory), a Pi install is complete, and nothing identifies the host — no `PI_CODING_AGENT_DIR`, which Pi sets only inside a Pi session — the complete Pi root wins, and the Claude session silently gets Pi wording (`/skill:` commands, `/new` instead of `/clear`) instead of the actionable `install incomplete/degraded at … — reinstall with …` error it used to get. The rule was safe while every bundle was interchangeable, and Pi is the first bundle for which that is no longer true. It is documented rather than fixed because the precondition is an install that is already broken and already needs a reinstall, while every candidate fix either breaks Pi discovery for installer-based setups or pushes same-agent-family tracking into a shell script that ships verbatim in six bundles. **Workaround:** repair the damaged install — `feature-forge update -a claude`, or `npx @garygentry/feature-forge -a claude`. Note that `FEATURE_FORGE_ROOT` does *not* help here: it is a later fallback than the directory probe, so a complete root found during the probe wins before the override is ever consulted.

## [0.12.9] — 2026-07-19

### Added

- **Cross-member shared-state test coupling detection (#144).** In an epic, a member that
  writes or migrates a file a *sibling's* already-shipped tests pin (e.g. a shared corpus a
  benchmark suite reads at v1) silently breaks that sibling the moment it runs — red-gating
  every one of the mutating member's own commits — and nothing in the epic contract checks
  (E04–E09, which cover code symbols, not shared data files) caught it. A new **forge-verify
  epic-mode check `CHECK-E10`** now detects it heuristically: for each member it collects the
  shared paths it writes (from a new optional `mutatesShared[]` manifest hint, or by grepping
  its specs/backlog when the hint is absent) and greps every **completed** sibling's committed
  tests for reads of those paths; a hit is a non-fatal `inconsistency` finding recommending a
  **reconciliation backlog item** scheduled before the first mutating item. The optional
  `mutatesShared` array-of-paths field is added to `epic-manifest-schema.json` (and accepted by
  `epic-manifest.py validate` — schema-legal when present, ignored when absent); it is declarative
  only, **not** a dependency edge. `forge-4-backlog` gains matching authoring guidance so the
  reconciliation item is planned up front rather than discovered mid-loop on a red gate. Degrades
  to a clean no-op when no member declares or greps a shared write. Adapters regenerated.

- **Generated-artifact freshness vs. `testCommand` `--check` gates (#145).** When a project's
  configured `testCommand` gates on staleness of generated artifacts (`<generator> --check`-style
  sub-commands that fail if a checked-in generated file is out of date with its source), a backlog
  item that regenerated *one* gated artifact but omitted a sibling would pass locally yet red-gate
  every commit on the stale-generated check — with no backlog check catching it. New **forge-verify
  backlog-mode check `CHECK-B26`** string-scans `testCommand` for `--check` freshness gates and flags
  (a) a gate whose artifact no item regenerates while some item edits its source, and (b) an item that
  regenerates a proper subset of the artifacts a `--check` set covers — recommending the missing
  generators be added to the item's execute + commit sequence. Advisory / not-applicable when the
  command shape has no parseable `--check` tokens. `forge-4-backlog` (and its rauf `author-backlog`
  delegate) gain matching authoring guidance: enumerate the whole `--check`-gated set up front, not
  just the artifact an item is "about".

- **Dev-runtime smoke guidance + heavy-bootstrap heuristic `CHECK-I23` (#149, follow-up to #121).**
  The impl-verify runnability checks now target the failure modes that a static typecheck and a clean
  prod smoke both hide. `CHECK-I21`'s prose now recommends the configured `smokeCommand` exercise the
  **dev runtime** the developer actually uses (dev server / watch loop / HMR) — where
  module-graph-identity bugs (a "singleton" duplicated across a re-evaluated module graph) and
  watch-loop bugs (an init that never re-fires, or re-fires and leaks on reload) live — and that a
  **fix** be re-verified in the same runtime mode the original bug manifested. A new **`CHECK-I23`**
  (advisory `gap`/`improvement`, **never** a hard fail) flags a runtime-required init wired into a
  **universal framework bootstrap entry** (a Next.js `instrumentation.ts`, an app-server preload, a
  global setup module) that pulls a large **server-only import graph** (DB/ORM clients, queue workers,
  telemetry SDKs), recommending **lazy init** at the first route/handler/worker that needs the graph
  instead of eager wiring on every cold start. Detection is static, driven by a new **Runtime
  Entrypoints & Bootstrap-Wiring Sites** section added to every stack profile
  (`references/stacks/{typescript,python,go,rust,_generic}.md`) — which also retroactively backs the
  stack-profile reference `CHECK-I22` already made. Guidance + heuristic lint only (no runtime-health
  monitor). Impl mode total `~22 → ~23`. Adapters regenerated.

- **Contradictory-lifecycle backlog heuristic `CHECK-B27` + authoring guidance (#150).** A test/e2e
  item whose only path to green is "artifact `X` is *published* / *approved* / *reviewed*", while
  another item pins `X` *draft* and no publish/review item sits between them, forced the autonomous
  loop to **fabricate** the publication or human sign-off (a provenance defect a `--review` pass
  caught). A new **`CHECK-B27`** (advisory, keyword/artifact-name based; **not-applicable** when no
  lifecycle vocabulary is present, never a hard fail) pairs contradictory lifecycle assertions about
  the **same named artifact** and flags an `inconsistency` when the later-state item has no
  human-gated publisher in its `dependsOn` closure, plus an anti-pattern note visible even where the
  heuristic can't fire. Matching authoring guidance lands in `forge-4-backlog` and its rauf
  `author-backlog` delegate: a test item asserting a human-gated state must either `dependsOn` an
  explicit publish/review item or assert the state via a dev-build/fixture path — never be the sole
  driver of a lifecycle transition another item forbids. Forge tracks no artifact-lifecycle model;
  this is guidance + heuristic lint only. Backlog mode total `~26 → ~27`. Adapters regenerated.

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

### Fixed

- **Unknown `forge-verify-*` status no longer silently poisons the epic rollup +
  dependency gates (#148).** An unrecognized status string in a member's
  `.pipeline-state.json` (e.g. the eye-slip `findings-resolved`, conflated with the
  adjacent `findingsResolved` count) was treated as "not complete-for-orchestration"
  with **no diagnostic** — so one typo on one member under-reported the whole epic
  (`rollup 0/6`) and fabricated phantom `unmetDeps` on every dependent, surfacing only
  as a confusing false dependency warning steps downstream. The accepted vocabulary is
  now a single labelled constant `KNOWN_VERIFY_STATUSES` (byte-identical in
  `epic-manifest.py` and `forge-session.py`, sourced from
  `references/pipeline-state-schema.json`), with the orchestration-complete / resolved
  sets documented as strict subsets. `epic-manifest.py render-status` now emits a
  `warnings[]` entry (and a "Warnings:" row in the text dashboard) naming the member,
  stage, and bad value; `forge-session.py`'s freshness classifier prints a one-time
  stderr diagnostic when it reads an out-of-vocabulary status. Treating an unknown
  status as incomplete is unchanged — doing so **silently** was the trap.

- **Authoring stages self-abort a replayed mid-stage continuation instead of overwriting
  a committed artifact (#151).** The Stage-Entry Guard protects only a top-of-skill re-run;
  a pasted/resumed mid-stage instruction ("continue forge-3-specs: write `TRACEABILITY.md`,
  run the stage exit") entered *below* it, and nothing re-checked `stages.<stage>.status`
  before regenerating — followed literally, it would overwrite a committed spec artifact and
  re-fire a completed stage exit. A new **Stage-Completion Re-check** block in
  `references/shared-conventions.md` (sibling to the Stage-Entry Guard) is cited at the head
  of the write/exit step in `forge-1-prd`..`forge-4-backlog`: before writing an artifact or
  running the Scripted Stage Exit, it re-reads the stage entry and, when the stage is already
  `complete`/`stale` with artifacts on disk + a recorded `commitHash` that the current session
  did **not** author, routes to the entry guard's Re-authoring warning (detect-and-refuse)
  rather than regenerating. Distinguisher is provenance — a legitimate exit runs in the session
  that stamped the entry; when unconfirmable, it refuses (a false refuse costs one click, a
  false proceed overwrites committed work). Skill bodies gain one citation line each (all stay
  under the 300-line cap); adapters regenerated.

- **Stale/partial install now fails loudly instead of running degraded (#152).** When a
  skill dir was present but the bundled `scripts/`/shared `references/` were missing (a
  skill-only extraction, or an install predating the shared-reference fan-out), the skill ran
  **degraded with no warning** — hand-improvised state schema, skipped Mint Guard + scripted
  stage-exit. This is not a packaging defect (a fresh install ships everything), so the fix is
  a preflight self-diagnostic in the single verbatim-copied resolver `scripts/forge-root.sh`:
  a new completeness gate verifies a resolved root also carries its core assets
  (`scripts/forge-session.py`, `references/pipeline-state-schema.json`,
  `references/stage-exit-protocol.md`). A sentinel-bearing but asset-incomplete root is now
  reported as `install incomplete/degraded at <dir> (missing <asset>) — reinstall …` with exit
  1, rather than handed back as if whole; a complete root found later in the probe order still
  wins over an earlier partial one. Because **every** skill's bootstrap prelude execs
  `forge-root.sh` at stage start, the guard fires on every **cold** stage entry with no reliance
  on the `/feature-forge:forge` navigator, and with **zero** skill-body changes. README gains a
  "stale or partial install" note pointing at reinstall / `feature-forge update`. Adapters
  regenerated (5 resolver mirrors).

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
