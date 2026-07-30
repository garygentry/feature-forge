# Verification Report: stage-exit-coverage (specs)
Date: 2026-07-30
Pipeline Stage: forge-4-backlog (verifying forge-3-specs v3)
Basis: PRD v3, tech-spec v3, specs v3 (commit f383837 — verify-capability permission patch)
Artifacts Reviewed: PRD.md, tech-spec.md, TRACEABILITY.md, 00-core-definitions.md,
01-architecture-layout.md, 02-stage-exit-routing.md, 03-verification-state.md,
04-skill-integration.md, 05-config-and-distribution.md, 06-compliance-and-coverage.md,
07-testing-strategy.md; cross-checked against live repo sources under `scripts/`,
`skills/`, `references/`, `tests/`, `eval/`, `adapters/`.

Method: five parallel `forge-verifier` instances over disjoint CHECK-ID slices
(types/contracts, architecture/layout, cross-reference/traceability, testing strategy,
integration). 41 raw findings merged to 33 after dedup; `V-NNN` IDs renumbered across the
merged set and `Checklist:` IDs unioned where slices overlapped.

Deterministic gates run by the orchestrator (both clean, not re-derived by the verifiers):
- `validate-traceability.py` — 55 requirements, 0 uncovered, 0 orphaned, `valid: true`
- `rauf-stable backlog validate` — `valid: true`, 0 findings

Six mechanically-checkable claims were confirmed against the repo before filing:
`CALL_RE`/`LOOKBEHIND=12`/`LOOKAHEAD=8`/`MIN_CALL_SITES=21` in
`tests/test_state_verb_call_sites.py`; `"deferred": next_command` at
`scripts/forge-session.py:1725`; the 66/70-byte minimal-canon stubs; the `§5 stage_exit`
mis-citation at `00-core-definitions.md:584` (`def stage_exit` is at line 134, inside §3);
`adapters/pi/scripts/forge-session.py` differing from canon at byte 23760 while
`forge-bootstrap.py` is identical; and the non-fatal pytest skip at `scripts/validate.sh:218`.

## Summary
- Total findings: 33
- Gaps: 9
- Inconsistencies: 10
- Improvements: 12
- Errors: 2

Per-slice check execution: types 9/9 (4 pass, 5 fail), architecture 10/10 (4 pass, 6 fail),
cross-reference 9/9 (4 pass, 5 fail), testing 5/5 (1 pass, 4 fail), integration 5/5
(1 pass, 4 fail). **Executed 38 of 38 checks. Results: 14 pass, 24 fail, 0 not-applicable.**

---

## Findings

### V-001: `00-core-definitions.md` cites `stage_exit` as a §5 declaration; it is defined in §3
- **Severity:** error
- **Location:** `00-core-definitions.md`, "Public API and Internal Surface", line 584
- **Issue:** The bullet reads "The §5 `stage_exit`, `next_stage`, and §6 `cmd_state_verify` entry points are declared here…". `next_stage` is in §5 ("Rendering and Routing Function Contracts", line 347) and `cmd_state_verify` in §6, but `def stage_exit(` is at line 134, inside §3 ("Request Validation Contract", line 128). §5 contains no `stage_exit` declaration. Every consumer document cites it correctly (`02` §2.2 → "§3", `05` §3.1 → "§3", `07` §2.1 → "§§3, 5, and 6"), so the owning document's own summary is the single wrong pointer — the one a fresh implementer follows first. **Confirmed against the file.**
- **Suggested fix:** Change the clause to: "The §3 `stage_exit`, the §5 `next_stage`, and the §6 `cmd_state_verify` entry points are declared here and implemented by their owning documents."
- **References:** `00-core-definitions.md` §3, §5, §6; `02-stage-exit-routing.md` §2.2; `07-testing-strategy.md` §2.1
- **Checklist:** CHECK-S15

### V-002: `EpicReconcile.deferred` is documented with the wrong semantics — it is a command, not a reason
- **Severity:** error
- **Location:** `00-core-definitions.md` §4, `EpicReconcile.deferred` field comment
- **Issue:** The spec says: "Reconcile explicitly deferred by the user, carrying the reason; None means not deferred. A deferred reconcile never blocks, whatever `required` says." The live field is neither. `scripts/forge-session.py:1725` sets `"deferred": next_command`, and `_next_steps_block` renders it at `:1608-1609` as `After reconciling, continue the pipeline with: {_host_command(reconcile["deferred"], host)}` — a **host-translatable next-stage command string**, present only on a `required: true` (blocking) reconcile. Implemented as written, the key would be repurposed to carry free prose, the blocking-reconcile follow-up line would lose its source, and prose would be passed through `_host_command`. That breaks REQ-COMPAT-01 ("Existing scripted exits for stages 0–4 MUST preserve their user-visible prompts … directives") and contradicts tech-spec §4.2 ("without renaming compatibility fields"). **Confirmed against `scripts/forge-session.py`.**
- **Suggested fix:** Replace the `deferred` comment with: "Canonical (untranslated) production command demoted behind a blocking reconcile — rendered as the unfenced `After reconciling, continue the pipeline with: …` line and passed through `_host_command` at render time. Present only when `required: True`; None/absent otherwise. It is a command, never a user-supplied reason." Add one sentence to `02-stage-exit-routing.md` §5.2 rule 5 giving the precedence between `epicReconcile["deferred"]` and the new `_next_steps_block(deferred_command=...)` parameter (`00` §5), since both feed the same deferred line.
- **References:** `scripts/forge-session.py:1608-1609, :1725`; `references/stage-exit-protocol.md` (`epicReconcile`); `tech-spec.md` §4.2; PRD REQ-COMPAT-01; `00-core-definitions.md` §5
- **Checklist:** CHECK-S08

### V-003: `autoVerifyDebtRecorded: False` with `runInStageVerify: True` is documented as reachable but is specified as impossible
- **Severity:** inconsistency
- **Location:** `00-core-definitions.md` §4 (`autoVerifyDebtRecorded` comment)
- **Issue:** `00` §4 says "False with `runInStageVerify: True` means the debt write failed — the caller must not treat scheduling as done (REQ-DEBT-01/04)", placing an obligation on that combination. `03-verification-state.md` §4.1 says the opposite: "Only after the atomic write succeeds may the result set `autoVerifyDebtRecorded: true` and `runInStageVerify: true`. A write failure raises `UsageError` and no dispatch directive is returned." `04-skill-integration.md` §3.3 step 2 agrees with `03` ("already durable at this point"), making `00` the outlier. A test author reading `00` will write an unconstructible case; a skill author may add a defensive branch that can never run and masks the real fail-closed error.
- **Suggested fix:** Rewrite the comment to: "True whenever `runInStageVerify` is True — `03-verification-state.md` §4.1 persists the `auto-verify-pending` marker before this payload exists, and a failed debt write raises `UsageError` with no payload at all. `runInStageVerify: True` with `autoVerifyDebtRecorded: False` is therefore **unreachable**; the field is carried so tests and downstream tools can assert that invariant rather than infer it. False with `runInStageVerify: False` simply means no debt was owed." Do **not** change `03` §4.1 or `04` §3.3 — fail-closed is what REQ-DEBT-01/REQ-REL-02 require.
- **References:** `03-verification-state.md` §4.1; `04-skill-integration.md` §3.3 step 2; `02-stage-exit-routing.md` §4; PRD REQ-DEBT-01/04, REQ-REL-02/03
- **Checklist:** CHECK-S08, CHECK-S12, CHECK-S19
- *(Merged: architecture V-003 + types V-001)*

### V-004: `stageNoun` is dropped from the directives contract while canon still consumes `{stageNoun}`
- **Severity:** gap
- **Location:** `00-core-definitions.md` §4 `StageExitDirectives`
- **Issue:** The current payload emits `"stageNoun": STAGE_NOUN.get(stage, stage)`, and `references/stage-exit-protocol.md` interpolates it twice (line 79 heading `in-stage auto-verify {stageNoun}`, line 125 gate label `**Verify {stageNoun} now**`). `04-skill-integration.md` §3.2 quotes that exact label as the consent-supplying choice. `StageExitDirectives` — presented as the complete machine-readable directive contract — omits `stageNoun` entirely, though it documents every other pre-existing key. `01-architecture-layout.md` §3.1 step 1 says only "extend … stage nouns"; no spec states that the four new exit stages need `STAGE_NOUN` entries or what they are.
- **Suggested fix:** Add to `StageExitDirectives`, next to `stage`: `stageNoun: str` with the comment "Human-readable noun for this stage's artifact, used by `references/stage-exit-protocol.md`'s `{stageNoun}` slots (gate label and auto-verify heading). Always present; defaults to the stage id when unmapped." In `01-architecture-layout.md` §3.1 step 1, name `STAGE_NOUN` explicitly, require an entry for all nine `EXIT_STAGES`, and fix the four new values (proposed: `forge-5-loop: "implementation"`, `forge-6-docs: "documentation"`, `forge-verify: "verification"`, `forge-fix: "fixes"`).
- **References:** `scripts/forge-session.py` (`stage_exit` directives dict); `references/stage-exit-protocol.md` lines 79, 125; `04-skill-integration.md` §3.2; `tech-spec.md` §4.2; PRD REQ-COMPAT-01
- **Checklist:** CHECK-S05, CHECK-S08

### V-005: Stage-exit JSON is required to carry the pending debt's served stage, but no directive field can hold it
- **Severity:** inconsistency
- **Location:** `03-verification-state.md` §5.3 vs `00-core-definitions.md` §4 `StageExitDirectives.servedStage`
- **Issue:** `03` §5.3 states that for `auto-pending` debt, "JSON output carries the stable `verifyState: "auto-pending"`, served stage, and retry command", applying to "Navigator, stage-exit, doctor/status, and epic dashboard". The navigator side is satisfied — `FeatureRow` already has `verifyStage: str | None` (`scripts/forge-session.py:249`) — but the stage-exit side is not: `StageExitDirectives.servedStage` is defined as branch-only ("None on a production-stage exit, which serves only itself"), and no other key names the stage the debt is owed on. An implementer satisfying §5.3 would invent an undeclared key, which then escapes `06`'s payload-based scoring and `07`'s assertions. This weakens REQ-OBS-01 exactly at the debt case the feature exists for.
- **Suggested fix:** Add to `StageExitDirectives`, adjacent to `verifyState`: `verifyStage: str | None` with the comment "Production stage the outstanding/owed verification belongs to — the value `pending_verify()` returns; mirrors `FeatureRow.verifyStage`. None when nothing is outstanding. Distinct from `servedStage`, which is branch-exit-only." Amend `03` §5.3 to name the keys ("stage-exit JSON carries `verifyState`, `verifyStage`, and `verifyCommand`"), and add a `07` §4.1 assertion that a production-stage exit with `auto-pending` debt reports the owed stage in `directives.verifyStage`.
- **References:** `scripts/forge-session.py:249` (`FeatureRow.verifyStage`); `03-verification-state.md` §5.1/§5.3; PRD REQ-OBS-01, REQ-DEBT-05
- **Checklist:** CHECK-S31

### V-006: A single `warning: str` directive cannot carry two concurrent advisories
- **Severity:** improvement
- **Location:** `00-core-definitions.md` §4 (`warning` field)
- **Issue:** `warning` is typed as one string, but the specs define at least three independently triggerable exit-time advisories that can co-occur on one call: the epic-member unreadable-state fallback (`02` §9, `04` §8.2), the legacy/malformed `scheduledStageVersion` metadata warning (`03` §5.1), and the scheduled-vs-current revision mismatch note (`03` §5.3). With one string an implementer must silently drop or concatenate, and `07`'s determinism assertions have no defined ordering to check (REQ-REL-01 requires byte-identical output; REQ-OBS-02 requires each warning to name its affected feature/stage/key).
- **Suggested fix:** Either change the field to `warnings: list[str]` with a stated deterministic order (epic-fallback, then debt-metadata, then revision-mismatch) — mirroring `RenderStatus.warnings` in `04` §2.2, which is already a list — or, if a single string is intentional for compatibility, state the precedence rule explicitly in the `00` §4 comment and cite it from `03` §5.3. **See User Decision D3.**
- **References:** `02-stage-exit-routing.md` §9; `03-verification-state.md` §5.1/§5.3; `04-skill-integration.md` §2.2 (`RenderStatus.warnings`); PRD REQ-OBS-02, REQ-REL-01
- **Checklist:** CHECK-S31

### V-007: The twelve `Literal` aliases in `00` §2 duplicate the runtime constants with no derivation and no parity guard
- **Severity:** improvement
- **Location:** `00-core-definitions.md` §2 (Identifiers, Enums, and Constants)
- **Issue:** §2 declares `ProductionStage`, `ExitStage`, `VerifyMode`, `ExitOwner`, `VerifyCapability`, `VerifyStateLabel`, `VerifyStatus`, `VerifyGate`, `LoopOutcome`, `DocsOutcome`, `VerifyOutcome`, `FixOutcome`, then hand-writes the same domains a second time as `EXIT_STAGES` (repeats `ExitStage`'s nine names), `EXIT_OUTCOMES` (repeats the four outcome aliases verbatim), and `VERIFY_MODE_TO_STAGE` (keys repeat `VerifyMode`, values repeat `ProductionStage`). Only the constants are load-bearing at runtime — every consumer types its parameters as `str`. The project's type-check command is `ruff check scripts/ eval/`, a linter that does not verify `Literal` conformance, so a one-sided edit is completely silent. This repo has been bitten twice and now guards it: `tests/test_stage_constants_parity.py` ("the ONE place stage order lives") and `tests/test_agent_targets_parity.py` ("drifted once already and silently dropped `adapters/pi/` coverage"). Nothing in `06`/`07` asserts alias-vs-constant agreement.
- **Suggested fix:** Derive the constants from the aliases so the domain is written once — add `get_args` to the `typing` import and set `EXIT_STAGES: Final[tuple[str, ...]] = get_args(ExitStage)` and each `EXIT_OUTCOMES` value to `frozenset(get_args(<Alias>))`; add "`VERIFY_MODE_TO_STAGE`'s keys MUST equal `set(get_args(VerifyMode))` and its values MUST be a subset of `get_args(ProductionStage)`." If derivation is rejected (to keep the literal tuples greppable), instead add an explicit parity assertion to `tests/test_stage_constants_parity.py` covering all four alias/constant pairs and say so in `00` §2 — but do not leave the duplication unguarded, since ruff cannot catch it. *Recommended: derive.*
- **References:** `00-core-definitions.md` §2, §3; `02-stage-exit-routing.md` §2.2; `01-architecture-layout.md` §3.4; `tests/test_stage_constants_parity.py`, `tests/test_agent_targets_parity.py`; `forge.config.json`
- **Checklist:** CHECK-S10, CHECK-S12

### V-008: `cmd_state_verify` — the feature's one new state verb — is the only new callable whose parameters are undocumented
- **Severity:** improvement
- **Location:** `00-core-definitions.md` §6 (writer signature); repeated in `03-verification-state.md` §3.1
- **Issue:** `00` §1 states the project convention is Google-style docstrings, and every other contract honours it: `stage_exit` documents all twelve parameters plus Returns and Raises; every `TypedDict` field in §4/§6 carries a per-field comment; `02` §3.2's `resolve_served_stage` has full Args/Returns/Raises. `cmd_state_verify` — nine parameters, two mutually exclusive modes, the only new `state-*` verb — carries a one-line summary plus `Raises:`, with no `Args:` or `Returns:`. Its parameter semantics (which fields are required/forbidden per status; that `commit_hash` is mode-selecting; that `feature` names the *epic* when `stage == "forge-0-epic"`) exist only in `03` §3.2/§3.3 prose.
- **Suggested fix:** Extend the docstring with `Args:` for all nine parameters — for `feature`, "the feature name, or the **epic** name when `stage == 'forge-0-epic'` (`03` §3.2 step 2)"; for `status`, "result mode; mutually exclusive with `commit_hash`; see the `03` §3.3 matrix for which metadata each status requires and forbids"; for `commit_hash`, "commit-2 mode; full 40-hex only, validated by `FULL_GIT_HASH_RE.fullmatch`" — plus a `Returns:` line describing the emitted JSON result. Keep `Raises:` unchanged. Mirror the summary line in `03` §3.1.
- **References:** `00-core-definitions.md` §1, §3, §6, §7; `03-verification-state.md` §3.1–§3.3; `scripts/forge-session.py` (`cmd_state_complete` docstring convention)
- **Checklist:** CHECK-S13

### V-009: The `render-status` subprocess pins neither path resolution, interpreter, nor timeout — though "timeout" is a required failure mode
- **Severity:** gap
- **Location:** `02-stage-exit-routing.md` §8 (Docs Live-State Routing) and §10 (Error Handling table)
- **Issue:** §8 requires "Manifest command nonzero, malformed JSON, missing required fields, **timeout**, or invalid graph is an actionable exit-2 routing failure", but no spec states how that timeout arises: no `timeout=` argument, no bound, no mapping from `subprocess.TimeoutExpired` to `UsageError`. `grep -n timeout specs/stage-exit-coverage/*.md` returns only this line and an unrelated eval line in `06` §7. `07` §3 (line ~377) lists the render-status failure cases and omits timeout too, so nothing would catch its absence. Separately, `<bundle-root>` in the fenced command is a placeholder the specs never resolve — `forge-session.py` is copied verbatim into six adapter bundles and runs from arbitrary cwd, so the router must locate its sibling at runtime, and the specs say neither how nor whether to invoke `python3` or `sys.executable`. Implemented as a bare `subprocess.run(...)`, a `forge-6-docs` close for an epic member can block indefinitely with no sentinel and no error, leaving §8's REQ-PERF-01 claim unenforced. The repo already has the convention: every `subprocess.run` in `scripts/forge-session.py` passes `timeout=10` (`:746` git, `:772` the `forge-root.sh` resolver), and `_resolve_plugin_root` (`:767`) uses `Path(__file__).resolve().parent / …`.
- **Suggested fix:** In `02` §8, after the fenced command add: "The router resolves the helper as `Path(__file__).resolve().parent / \"epic-manifest.py\"` — the sibling shipped in the same bundle, matching `_resolve_plugin_root`'s existing convention — invokes it with `sys.executable`, and bounds it with `subprocess.run(..., capture_output=True, text=True, timeout=10, check=False)`. A missing sibling, non-zero exit, `subprocess.TimeoutExpired`, `OSError`, or unparseable stdout is converted to `UsageError` and reported like any other manifest-command failure — naming the epic and the recovery command, emitting no sentinel and never a guessed member route." Add a §10 row: "| Epic docs status | subprocess timeout (10s) or spawn failure | exit 2 naming the epic and `/feature-forge:forge-0-epic EPIC`; no guessed member, no sentinel |". Add the timeout case to `07` §3's render-status failure list (injectable via a sleeping stub or by monkeypatching `subprocess.run` to raise `TimeoutExpired`).
- **References:** `02-stage-exit-routing.md` §8, §10; `01-architecture-layout.md` §4.3; `tech-spec.md` §3.5, §6.1 item 2; `scripts/forge-session.py:745-746, :767, :771-772`; `scripts/build-adapters.py::RUNTIME_HELPERS`; `07-testing-strategy.md` §3; PRD REQ-PROD-03/04, REQ-REL-02, REQ-PERF-01
- **Checklist:** CHECK-S18, CHECK-S21, CHECK-S22, CHECK-S26, CHECK-S29
- *(Merged: architecture V-010 + integration V-006 + types V-003)*

### V-010: The consent-required auto-verify path is told to present the Standard Verify Gate on a payload whose `verifyGate` is `none`
- **Severity:** inconsistency
- **Location:** `02-stage-exit-routing.md` §4 (final paragraph) and §5.1; `04-skill-integration.md` §3.3 step 2
- **Issue:** `02` §4's table sets, for "auto-verify effective and outstanding", `Gate: none; runInStageVerify: true`. `02` §4's closing paragraph and `04` §3.3 step 2 then direct that caller to "route the auto path through the `standard` gate — ask, then dispatch on the affirmative". But `02` §5.1 conditions the gate's content on the emitted value: "For `verifyGate == "standard"`, `references/stage-exit-protocol.md` MUST present three explicitly labeled choices …". So the skill is told to render a gate the payload did not select, and no spec says which block or labels it uses. Worse, choice 2 — "**Verify now + enable auto-verify going forward**" — is a no-op in this path, because auto-verify is already effective; presenting it violates the spirit of REQ-A11Y-01 (explicit labels with real trade-offs). tech-spec §3.3 does not describe this path at all, so the skill-side behavior has no tech-spec anchor. This is the routing half of the same clause-(b) contract patched in f383837.
- **Suggested fix:** Keep the emitted `verifyGate: none` (changing it to `standard` would alter directive values for existing stages 0–4 and collide with REQ-COMPAT-01) and close the prose hole. Add to `02` §5.1, after the three-choice list: "When `runInStageVerify: true` and the caller may not dispatch unsolicited (`04-skill-integration.md` §3.3 step 2), the caller reuses this same gate block for consent even though `verifyGate` is `none`, **omitting choice 2** (auto-verify is already effective) and presenting only *Verify now (recommended)* and *Skip for now*; a skip must be persisted as `skipped` before any advancing block." Mirror one sentence into `04` §3.3 step 2 and add the two-choice consent variant to tech-spec §3.3 so the decision is anchored.
- **References:** `tech-spec.md` §3.3; `references/stage-exit-protocol.md` (gate block, line 125); PRD REQ-EXIT-06/07, REQ-A11Y-01, REQ-DEBT-04
- **Checklist:** CHECK-S08

### V-011: Two user-facing diagnostics that tests must assert have no specified message text
- **Severity:** improvement
- **Location:** `02-stage-exit-routing.md` §9 ("emit a named warning directive"); `00-core-definitions.md` §4 (`invalidAutoVerifyKeys`, `warning`)
- **Issue:** This feature specifies exact strings for its other diagnostics — `02` §3.2, `03` §5.3, `05` §2.2 (`Warning: duplicate JSON key "<key>" in <path>; using the last value.`). Two get only a label: the epic-member PRD fallback is described five times as "a named warning" (`02` §9 and its Verification list, `04` §8.2 and §9, tech-spec §193/§486) with no template, and `invalidAutoVerifyKeys` is only "Keys in `autoVerifyStages` that name no verify-capable stage" with no rendered wording, though `04` §3.3 step 1 requires skills to "surface `invalidAutoVerifyKeys` and `warning` before terminal output". `07` §3 (line ~395) requires asserting that "unreadable/unresolvable selected member receives the named PRD fallback warning", so the test author must invent the string the test pins. REQ-OBS-02 requires such warnings to name the affected feature/stage/key **and the recovery action** — unstated wording can silently miss that.
- **Suggested fix:** Add exact templates, following the `05` §2.2 precedent. In `02` §9: "The warning directive text is exactly: `Warning: {member}: pipeline state could not be resolved under epic {epic} ({reason}); routing to forge-1-prd. Run /feature-forge:forge {member} to inspect its state.` where `{reason}` is one of `missing`, `unreadable`, `malformed`, or `not a member of this epic`." For `invalidAutoVerifyKeys` (in `00` §4 or `02` §10): "Each key renders as `Warning: autoVerifyStages key \"{key}\" names no verify-capable stage; it is ignored. Valid keys are forge-1-prd, forge-2-tech, forge-3-specs, forge-4-backlog, forge-5-loop.` Keys are rendered in sorted order (`02` §10 determinism rule)." Have `07` §3 assert those literals rather than a paraphrase.
- **References:** `02-stage-exit-routing.md` §9, §10; `04-skill-integration.md` §3.3, §8.2, §9; `03-verification-state.md` §5.3 and `05-config-and-distribution.md` §2.2 (precedents); `07-testing-strategy.md` §3; PRD REQ-OBS-02, REQ-PROD-06
- **Checklist:** CHECK-S20

### V-012: `02-stage-exit-routing.md` calls `cmd_state_verify` but does not declare `03-verification-state.md` as a dependency
- **Severity:** improvement
- **Location:** `02-stage-exit-routing.md` "Dependencies"; `04-skill-integration.md` "Dependencies"
- **Issue:** `02`'s Dependencies lists only `00-core-definitions.md` and `01-architecture-layout.md`, yet `02` §4 consumes the `auto-pending` label and `02`'s Public API states "`cmd_state_verify` belongs to `03-verification-state.md`; §4's scheduling boundary calls it". `03` §9 asserts the ordering from the other side, so the constraint exists but is declared only once and in the wrong direction for anyone reading `02` first. Separately, `04`'s Dependencies names two prerequisites descriptively ("The state/debt implementation spec that provides `state-verify`") instead of by filename, unlike every other dependency list in the suite. Neither blocks implementation — `01` §5 sequences correctly and there is no cycle — but both weaken the machine-checkable dependency graph.
- **Suggested fix:** Add to `02`'s "Implement these specifications first": "`03-verification-state.md` — the `state-verify` writer and the `auto-verify-pending` label §4's scheduling boundary consumes and §4 treats as outstanding." In `04`'s Dependencies, replace the two descriptive bullets with `03-verification-state.md` and `02-stage-exit-routing.md` by name, keeping the ordering rationale.
- **References:** `03-verification-state.md` §9; `01-architecture-layout.md` §5; `02-stage-exit-routing.md` §4 and Public API
- **Checklist:** CHECK-S14, CHECK-S16

### V-013: REQ-DEBT-05's "downstream pre-flight checks" consumer has no implementation site
- **Severity:** gap
- **Location:** `03-verification-state.md` §5 (all of §5.1–§5.3); `04-skill-integration.md` §6 and §7.2
- **Issue:** REQ-DEBT-05 (P0) enumerates four consumers that must recognize `auto-verify-pending` and "MUST NOT classify it as ordinary `never` or as a successful terminal state": navigator, stage-exit, status rendering, **and downstream pre-flight checks**. `TRACEABILITY.md` maps the whole requirement to `03` §5, but §5.1 covers only `verify_state`/`pending_verify`/`_verify_state_for`/`build_rows`, §5.2 covers `epic-manifest.py`, and §5.3's diagnostic sentence names "Navigator, stage-exit, doctor/status, and epic dashboard text" — the pre-flight class is dropped. tech-spec §3.7 *does* list "downstream pre-flight text" as a consumer, so this is coverage lost between tech-spec and specs. Two real call sites exist and neither is specified: `skills/forge-6-docs/SKILL.md` line 40 branches on an explicit enumeration — warn if `stages.forge-verify-impl` is absent or `"skipped"`, proceed silently if `findings-applied|findings-reported|passed` — so `auto-verify-pending` matches *neither* branch and its handling is undefined (the likely reading silently proceeds, treating owed debt as resolved); and `skills/forge-5-loop/SKILL.md` §1b line 55 warns "Backlog hasn't been verified yet" for anything outside `{passed, findings-applied}`, reporting owed-and-dropped auto-verify as never-scheduled — the exact conflation REQ-DEBT-02 forbids.
- **Suggested fix:** (1) Add `03` §5.4 "Downstream pre-flight parity (REQ-DEBT-05)": any canon gate reading a `stages.forge-verify-*` entry must treat `auto-verify-pending` as an explicit third case — outstanding, not resolved, not `never` — using the §5.3 diagnostic wording naming the served stage and retry command. (2) Extend `04` §7.2 to require `skills/forge-6-docs/SKILL.md` Step 1's backstop enumeration to add `auto-verify-pending` to the warn branch with debt-specific wording (keeping "generate anyway" persisting `skipped`), and add a subsection under `04` §6 requiring the same for `skills/forge-5-loop/SKILL.md` Step 1b. (3) Add both call sites to the `01` §2 annotations for those skills. (4) Add matching rows to `07` §4.1's consumer list and §6.2's canon assertions. (5) Update the REQ-DEBT-05 cell in `TRACEABILITY.md`.
- **References:** PRD §3.4 REQ-DEBT-05 and §8 success criterion 3; tech-spec §3.7 bullet 4; `skills/forge-6-docs/SKILL.md:40`; `skills/forge-5-loop/SKILL.md:55`
- **Checklist:** CHECK-S01, CHECK-S02, CHECK-S38

### V-014: `--findings-file` is a new path-valued state input with no containment validation
- **Severity:** improvement
- **Location:** `03-verification-state.md` §3.3 (result-mode matrix, `findings-reported` row) and §7.1
- **Issue:** `00` §6 defines `findingsFile` as "Path to the findings document, **relative to the feature directory**", but `03` §3.3 only requires it to be "non-empty", and §7.1's fail-closed list covers unsafe *names*, epic mismatch, and path escape for the **target** resolution — not for this stored value. REQ-SEC-01 requires that "all feature/stage resolution and state writes … retain existing path-safety … and fail-closed containment behavior"; an absolute path or one containing `..` would be accepted and persisted, and later consumers (`forge-fix` selecting the report, `04` §5.1) follow it.
- **Suggested fix:** Change the `findings-reported` required-input cell to "non-empty `findings_file` that is **relative** and contained by the resolved feature/epic directory — reject absolute paths, `..` segments, and NUL/control characters before mutation", add the corresponding bullet to §7.1's covered-failures list, and add a rejection case to `07` §4.2's transition matrix.
- **References:** `00-core-definitions.md` §6 (`findingsFile`); `04-skill-integration.md` §5.1; PRD REQ-SEC-01, REQ-REL-02
- **Checklist:** CHECK-S30

### V-015: `references/shared-conventions.md` is marked modified in both layouts, but no spec says what changes in it
- **Severity:** gap
- **Location:** `01-architecture-layout.md` §2 (`references/shared-conventions.md  M  immediate state-note recipes`) and `tech-spec.md` §2.1 (`shared-conventions.md  # immediate state-note recipe follow-up`)
- **Issue:** Found independently by three of the five verifier slices. `references/shared-conventions.md` is the only file in either layout with no owning implementation-spec section — the string `shared-conventions` appears in **no** implementation spec (`00`–`07`); grep returns only those two layout lines. The one specified `state-note` change (`04` §4.2) targets `skills/forge-1-prd/SKILL.md` and `skills/forge-2-tech/SKILL.md` only. The real file confirms the omission is substantive: its § Pipeline State Protocol (line 188, "Pipeline state is written by the `state-*` verbs … never by hand") enumerates recipes for `state-branch`, `state-complete`, `state-enter`, `state-artifact` and contains **no** occurrence of `state-note` or `state-verify` — so this feature's new verb and new immediate-note recipe would live nowhere in the shared protocol every skill reads, while `03`'s Public API declares `state-verify` "the eighth `state-*` verb". A fresh implementer following `01` §2 has an M-marked file with no instruction; one following `04` §4.2 never opens it. This also interacts with V-018: `tests/test_state_verb_call_sites.py::test_the_epic_mandate_itself_is_still_documented` treats that file as the normative home of the `--epic` mandate the new verb must obey.
- **Suggested fix:** Preferred — add `04-skill-integration.md` §4.3 (or extend §4.2) specifying two edits to `references/shared-conventions.md`: (a) register `state-verify` in the § Pipeline State Protocol verb inventory, with the `--epic` member requirement sentence that already applies to every `state-*` verb (line 190) and the exit-2 failure protocol; (b) add the immediate parking-lot `state-note` recipe as a named block the PRD/tech skills point at by reference instead of inlining. Keep both layout rows and update their annotation to "register state-verify; immediate state-note recipe". Alternative — delete the row from `01` §2 and the line from tech-spec §2.1, and record in `04` §4.2 that the recipe is deliberately inlined per-skill. **See User Decision D1.**
- **References:** `references/shared-conventions.md` lines 188–192; `03-verification-state.md` Public API; `04-skill-integration.md` §4.2; `tech-spec.md` §2.1, §3.11; `TRACEABILITY.md` line 51; PRD REQ-FOLLOW-02, REQ-STATE-03
- **Checklist:** CHECK-S01, CHECK-S04, CHECK-S05, CHECK-S06, CHECK-S22, CHECK-S25, CHECK-S38
- *(Merged: cross-reference V-004 + architecture V-005 + integration V-004)*

### V-016: `skills/forge-verify/references/findings-template.md` still hand-authors `.epic-state.json`, and no spec or layout converts it
- **Severity:** gap
- **Location:** `tech-spec.md` §2.1 and `01-architecture-layout.md` §2 (file layouts) — omission; `03-verification-state.md` §1 warning; `04-skill-integration.md` §5
- **Issue:** `03` §1's warning tells the implementer only that this file documents `.epic-state.json` and "must stay additive". The live file (§"Epic Mode State Write Detail (Step 6)", lines 89–157) contains a **heredoc Python snippet** that hand-writes `.epic-state.json` with `tempfile.mkstemp` + `os.replace`, setting only `status`, `findingsFile`, `findingsCount`, `verifiedAt` — and `skills/forge-verify/SKILL.md` Step 6 says "Follow it verbatim." This feature makes `state-verify --stage forge-0-epic` the sanctioned epic writer (`03` §3.2 case 2, §5.2) and declares that "nothing hand-authors these documents" (`03` Public API). Leaving it as-is means: (a) REQ-STATE-03 ("MUST NOT require model-authored JSON") is violated on the one epic path; (b) the hand-written entry carries no `verifiedStageVersion` and no top-level `updatedAt`, so under `03` §5.2 every epic verification classifies as **`stale`** — a silent functional regression; (c) canon self-contradicts (SKILL.md says `state-verify`, its reference says hand-write). The file is in neither layout, so it would never be opened during implementation, and `06` §2.1's guard inspects only the nine `contract_paths`, which do not include it.
- **Suggested fix:** Add `skills/forge-verify/references/findings-template.md   M   epic-state writes move to state-verify` to the `skills/` block of both `tech-spec.md` §2.1 and `01-architecture-layout.md` §2, and to `04` §1's scope list. Add `04-skill-integration.md` §5.4 specifying the replacement: delete the "Write mechanism" paragraph and the `python3 - <<'PY'` snippet and substitute the sanctioned call —
  ```bash
  python3 "$R/scripts/forge-session.py" state-verify \
    --feature "{epic}" --stage forge-0-epic \
    --status "{passed|findings-reported}" \
    --findings-file "{path}" --findings-count {n} \
    --verified-stage-version {manifest revision} --specs-dir "{specsDir}"
  ```
  — keeping the minimal-shape JSON example but updating it to the `03` §2.1 shape (including `updatedAt` and the scheduling keys). Add a `07` §6.2 assertion that no `.epic-state.json` write recipe or `os.replace` snippet survives under `skills/`. **See User Decision D2.**
- **References:** `skills/forge-verify/references/findings-template.md` lines 89–157; `skills/forge-verify/SKILL.md` (Epic mode state section); `03-verification-state.md` §2.1/§3.2/§5.2/Public API; PRD REQ-STATE-03, REQ-DEBT-05
- **Checklist:** CHECK-S05, CHECK-S06, CHECK-S08, CHECK-S22, CHECK-S25
- *(Merged: architecture V-004 + integration V-005 part 3)*

### V-017: Canon prose that this feature falsifies is left in place — the R4 exclusion note and `forge-fix`'s "fresh in the ledger" claims
- **Severity:** inconsistency
- **Location:** `04-skill-integration.md` §5.2 (verify termini) and §5.3 (fix termini) — instructions absent; affects `skills/forge-verify/SKILL.md` lines 228–241 and `skills/forge-fix/SKILL.md` lines 62–86
- **Issue:** `04` §5.2 says results are written "through `state-verify`" and §5.3 says "`findings-applied` no longer claims freshness: the targeted writer clears `verifiedStageVersion`". Two live canon passages state the opposite and are named by no spec:
  1. `skills/forge-verify/SKILL.md` line 228: *"**Deliberate R4 exclusion.** This step writes a verify entry … and **no `state-*` verb writes verify entries** … So this one step stays hand-authored."* Once `state-verify` exists this is false, and it actively instructs a model to hand-author verify state — the precise behavior REQ-STATE-03/REQ-DEBT-01 exist to remove.
  2. `skills/forge-fix/SKILL.md` line 69 instructs "Record `verifiedStageVersion` = the current `version`…", and lines 79 and 86 assert the stage "reads **fresh** in the navigator's ledger" and "stays `findings-applied` (fresh in the ledger)". Under the new writer, `findings-applied` **clears** `verifiedStageVersion` and is deliberately not fresh — the passages invert the new contract, and line 86's "Skip for now" option is the case `04` §5.3 reclassifies as `deferred`, not `reverified`.
  `04` §5.3 does say "Replace the current open-ended Step 6" for `forge-fix`, but that names only Step 6 — not Step 5's write, not the two freshness claims, and nothing at all for `forge-verify`'s Step 6.
- **Suggested fix:** In `04` §5.2 add: "Replace `skills/forge-verify/SKILL.md` Step 6's hand-authored state write with the `state-verify` call of §5.1, and **delete the 'Deliberate R4 exclusion' blockquote (lines 228–231)** — `state-verify` is now the verb that writes verify entries; replace it with a pointer to the Pipeline State Protocol." In §5.3 add: "Replace `skills/forge-fix/SKILL.md` Step 5's `verifiedStageVersion` instruction with the `state-verify --status findings-applied` call (which clears that field), and rewrite the Step 6 gate text at lines 79 and 86: `findings-applied` is **not** fresh, a skipped re-verify is `deferred`, and the ledger stays outstanding until a passing re-verify."
- **References:** `04-skill-integration.md` §5.1–§5.3; `03-verification-state.md` §3.1, §4; `tech-spec.md` §3.7, §6.2; PRD REQ-STATE-03, REQ-DEBT-01/03; `skills/forge-verify/SKILL.md` lines 228–253; `skills/forge-fix/SKILL.md` lines 62–86
- **Checklist:** CHECK-S22, CHECK-S25

### V-018: The new `state-verify` skill call sites carry no `--epic` instruction, which will fail the existing call-site guard
- **Severity:** gap
- **Location:** `04-skill-integration.md` §5.1–§5.3 (no `state-verify` fence, no `--epic`), and §3.1's flags table rows for direct/nested `forge-verify` and `forge-fix`
- **Issue:** `references/shared-conventions.md` § Pipeline State Protocol mandates: "**Epic members MUST pass `--epic`.** … append it to **every** `state-*` call in this file and in every skill body." `tests/test_state_verb_call_sites.py` enforces that mechanically — **confirmed against the file**: `CALL_RE = re.compile(r'forge-session\.py"?\s+(state-[a-z]+)')` (line 36) matches `state-verify`, and every match must have the `--epic` instruction within `LOOKBEHIND = 12` / `LOOKAHEAD = 8` lines (lines 50–51), with `MIN_CALL_SITES = 21` (line 41). This feature adds `state-verify` call sites to `skills/forge-verify/SKILL.md` and `skills/forge-fix/SKILL.md` (tech-spec §6.2), but `04` §5 never provides the bash fence and the string `--epic` does not appear anywhere in §5. `03` documents `[--epic EPIC]` in the CLI grammar only (§3.1) and provides no skill-side recipe. Two consequences: (a) a member feature's verify/fix result write resolves the bare feature name and exits 2 on ambiguity (REQ-SEC-01); (b) `bash scripts/validate.sh` fails on `test_every_state_verb_call_site_carries_the_epic_instruction` the moment the new sites land. No spec in the suite names `tests/test_state_verb_call_sites.py`.
- **Suggested fix:** In `04` §5.1 add the canonical fence with the member instruction adjacent to it (inside the 12/8-line window), mirroring §4.2's proven shape:
  ```bash
  python3 "$R/scripts/forge-session.py" state-verify \
    --feature "{feature}" --stage "{servedStage}" \
    --status "{status}" --specs-dir "{specsDir}"
  ```
  followed by: "Add `--epic \"{epic}\"` when the feature is an epic member — required, per the Pipeline State Protocol in `references/shared-conventions.md`. Omission is an error and must not fall back to a same-named flat feature. (`--stage forge-0-epic` is the exception: `--feature` names the epic and `--epic` must be absent or equal to it — `03-verification-state.md` §3.1.)" Add `--epic` for members to the §3.1 flags-table rows for direct/nested `forge-verify` and `forge-fix`. In `07` §6.2, add a bullet naming `tests/test_state_verb_call_sites.py` and asserting the new sites satisfy its `--epic` proximity guard and the `MIN_CALL_SITES` floor.
- **References:** `references/shared-conventions.md` lines 188–192; `tests/test_state_verb_call_sites.py:36, :41, :50-51`; `03-verification-state.md` §3.1; `04-skill-integration.md` §3.1, §4.2, §5.1–§5.3; tech-spec §6.2; PRD REQ-SEC-01
- **Checklist:** CHECK-S22, CHECK-S25

### V-019: The navigator skill is an integration consumer in the tech spec but is owned by no implementation spec
- **Severity:** gap
- **Location:** `01-architecture-layout.md` §2 (file layout) and `04-skill-integration.md` §1 (scope list) — omission; driven by tech-spec §6.2 bullets 2 and 5
- **Issue:** tech-spec §6.2 names two navigator obligations: "Stage authoring and navigator auto-verify paths call branch skills with `--owner nested`" and "Navigator/status rendering consumes the new `auto-pending` label." PRD REQ-DEBT-05 (P0) further requires the navigator to "recognize and clearly report `auto-verify-pending`". The string `skills/forge/SKILL.md` appears in **zero** implementation specs. `03` §5.1 covers only the script side (`build_rows` sets `verifyState="auto-pending"`), but the navigator dashboard is rendered by the model from `rank-features --json` per `skills/forge/SKILL.md`, which today: (a) documents a **closed** enum at line 44 — "`verifyState` (`fresh`/`stale`/`failing`/`never`/`none`)" — that becomes factually wrong once `auto-pending` is emitted; (b) explains at line 111 that `verifyPending` is true only "because the producing stage could not dispatch a clean-room subagent … or ran before this behavior landed", which stops being the complete list once durable debt exists; (c) dispatches `feature-forge:forge-verify`/`forge-fix` at lines 113–118 and 132 — the exact "navigator auto-verify paths" that must carry nested ownership; and (d) has a status legend (lines 60–80) with no marker for owed automatic verification. `06` §2.1 mentions the navigator only to *exclude* it from the exit-contract guard, a different concern. Because the file is absent from `01` §2, its adapter regeneration is also unaccounted for.
- **Suggested fix:** Add `skills/forge/SKILL.md   M   auto-pending row rendering + nested-owner dispatch wording` to the `skills/` block of `01` §2, and add `04-skill-integration.md` §4.3 "Navigator read-side and nested dispatch (REQ-DEBT-05, REQ-EXIT-04)" specifying: (1) extend the documented `verifyState` list at line 44 to include `auto-pending`; (2) add `auto-pending` handling to step 1 (line 90) and step 2b (line 111) — an `auto-pending` row means verification is *owed and recorded*, so the catch-up branch fires and it must never be read as "never verified"; (3) add the dashboard legend marker and the one-line obligation text from `03` §5.3; (4) state that when the navigator invokes `forge-verify`/`forge-fix` in its catch-up chain it is a **nested** caller, so those skills pass `--owner nested` and print no terminal block (see V-020). Add `skills/forge/SKILL.md` to the adapter-regeneration batch in `04` §10.
- **References:** tech-spec §6.2; PRD REQ-DEBT-05; `03-verification-state.md` §5.1, §5.3; `06-compliance-and-coverage.md` §2.1; `skills/forge/SKILL.md` lines 44, 60–80, 90, 111–119, 132
- **Checklist:** CHECK-S22, CHECK-S25

### V-020: The outer-caller → branch-skill signal that determines `--owner direct|nested` is never named
- **Severity:** gap
- **Location:** `04-skill-integration.md` §5.1 (last paragraph) and §3.3 step 2
- **Issue:** `04` §3.1 states "Branch ownership is never inferred from whether a user or another skill happened to phrase the invocation: the invoking path carries `--owner direct|nested`", and §5.1 states "Both skills determine `direct|nested` at entry and preserve it through re-verify." Neither says **what input carries that**. The script-side contract is fully pinned (`00` §3 `owner` param, `02` §3.1 step 5, §3.3), but the caller-side half is unspecified: an authoring stage acting on `runInStageVerify`, and the navigator at its catch-up, both dispatch `forge-verify` via a Skill/Agent invocation — not a CLI flag — so there is no specified carrier for "you are nested". The nearest existing precedent in canon is inference (`skills/forge-fix/SKILL.md` line 81: "Skip this gate when an `autoFix` caller invoked you as part of a chain"), which §3.1 explicitly forbids. Misclassification is not cosmetic: a nested verify that self-reports `direct` emits a second sentinel-terminated block inside an outer stage's exit, violating REQ-EXIT-03/04 (exactly one terminal block), and the `06` guard cannot catch it because both wordings are present in the same file.
- **Suggested fix:** In `04` §5.1 add a paragraph naming the carrier explicitly: "The dispatching caller states ownership in its invocation prompt using the literal token `owner: nested` (auto-verify chains, navigator catch-up, and nested re-verify) or `owner: direct` (user-typed `/feature-forge:forge-verify|forge-fix`). Absent the token the skill treats itself as `direct`, because a user-typed invocation is the only path that carries no dispatcher." Add the matching instruction to the outer side in §3.3 step 2, and to the navigator in the new §4.3 (V-019). Add a `06` guard row asserting the token appears at every nested-dispatch site.
- **References:** `04-skill-integration.md` §3.1, §3.3 step 2, §5.1; `00-core-definitions.md` §3 (`owner`), §4 (`terminalOwnedBy`); `02-stage-exit-routing.md` §3.1 step 5, §3.3; tech-spec §6.2; `skills/forge-fix/SKILL.md` line 81
- **Checklist:** CHECK-S23, CHECK-S24

### V-021: REQ-FOLLOW-01 is name-dropped only — no implementation spec says what to correct
- **Severity:** gap
- **Location:** `04-skill-integration.md` §6.3; `TRACEABILITY.md` line 50; `01-architecture-layout.md` §2
- **Issue:** `TRACEABILITY.md` maps `REQ-FOLLOW-01 | 04-skill-integration.md §6.3 — correct runner wording, retain conditional load`. §6.3 is titled "Body-cap and prerequisite constraint (REQ-CAP-01)", says nothing about the runner wording, and its own Requirement Coverage row lists that section against **REQ-CAP-01 only** — `REQ-FOLLOW-01` does not appear anywhere in `04-skill-integration.md`. Repo-wide, "optional flag" appears in `PRD.md` §3.8, tech-spec §3.11 and `07` §6.2 (the *test*), and in no numbered implementation spec. The sole implementation-side trace is a seven-word annotation in the `01` §2 file table (`runner-contract.md M stale --model wording correction (sole source)`). So the requirement passes the string-matching validator via a trace row pointing at a section that does not implement it, and an implementer working from `04` §6.3 will not make the edit; only the `07` §6.2 assertion — which the same implementer authors — would catch it.
- **Suggested fix:** Add a subsection to `04` §6.3 (or a new §6.4 "Runner-contract wording follow-up (REQ-FOLLOW-01)") specifying: (a) the file is `skills/forge-5-loop/references/runner-contract.md`, the sole runner-contract source per `01` §2; (b) the stale phrase describes `--model` as an "optional flag below", which is false after the catalog split — replace it with a pointer to `## Optional flags catalog (Step 2d, rauf)` in `references/agent-selection.md`; (c) the agent-selection reference must remain conditionally loaded (do not make it always-loaded, do not inline its content). Add `REQ-FOLLOW-01` to `04`'s Requirement Coverage table against that section; the existing `TRACEABILITY.md` row then becomes accurate.
- **References:** `PRD.md` §3.8 REQ-FOLLOW-01; tech-spec §3.11; `07-testing-strategy.md` §6.2 bullet 3; `01-architecture-layout.md` §2 lines 76–77
- **Checklist:** CHECK-S01, CHECK-S03, CHECK-S05, CHECK-S38
- *(Merged: cross-reference V-001 + architecture V-006)*

### V-022: Three `TRACEABILITY.md` section citations disagree with the target specs' own coverage tables
- **Severity:** inconsistency
- **Location:** `TRACEABILITY.md` lines 12, 13, 15, 42
- **Issue:** The matrix is the entry point a fix or implementation agent uses to find a requirement's contract, and three rows point at sections that do not contain it:
  1. `REQ-EXIT-03 | 02 §4, §6 — one sentinel-last direct exit` and `REQ-EXIT-04 | 02 §4 — outer/nested ownership`. `02` §4 is "Verify-First Primary Routing" and states no sentinel or ownership rule; terminal ownership is §3.3 and the sentinel-last rendering rule is §5.2 item 6. `02`'s own coverage table (line 8) correctly says "§3, §6". REQ-EXIT-04's cell cites §4 *alone*, so the matrix points at zero of the sections that implement it.
  2. `REQ-EXIT-06 | 02 §5–§6 — verify-first primary command`. The verify-first primary rule is §4 (literally so titled); `02`'s own table says "§4, §5".
  3. `REQ-CONFIG-04 | 05 §2.1, §5.1 — arbitrary recursive keys`. `05` §5.1 is "Generator integration" (`RUNTIME_HELPERS`, `run_self_containment_pass`) and has nothing to do with recursive key detection; the recursion contract is §2.1 plus the §3.3 compatibility matrix. `05`'s own coverage table repeats the same `§5.1` typo, so both documents need the edit.
- **Suggested fix:** In `TRACEABILITY.md`: set REQ-EXIT-03 to "`02-stage-exit-routing.md` §3, §5–§6"; REQ-EXIT-04 to "`02-stage-exit-routing.md` §3.3, §6"; REQ-EXIT-06 to "`02-stage-exit-routing.md` §4–§5"; REQ-CONFIG-04 to "`05-config-and-distribution.md` §2.1, §3.3". In `05-config-and-distribution.md`'s Requirement Coverage table, change the REQ-CONFIG-04 row's `§5.1` to `§3.3`.
- **References:** `02-stage-exit-routing.md` coverage table lines 8, 10, and §3.3, §4, §5.2; `05-config-and-distribution.md` coverage table line 10, §2.1, §3.3, §5.1
- **Checklist:** CHECK-S15, CHECK-S38

### V-023: `_load_config` is specified as never failing, yet calls `warn_duplicate_keys`, which is specified to raise `OSError`
- **Severity:** inconsistency
- **Location:** `05-config-and-distribution.md` §3.1 (the replacement `_load_config` body) vs §2.1/§2.2; mirrored in `00-core-definitions.md` §8
- **Issue:** The specified body places `warn_duplicate_keys(config_path, duplicate_keys)` **outside** the `try/except (OSError, json.JSONDecodeError)`, while the same document documents `warn_duplicate_keys` as raising `OSError: The process cannot write to stderr` (§2.1) and states "An actual stderr I/O failure is an `OSError`" (§2.2). Two paragraphs later §3.1 asserts "`_load_config` preserves its established missing, unreadable, malformed, scalar-root, and array-root behavior: return `{}` rather than fail." Those cannot both hold: on a closed/broken stderr (e.g. `rank-features --json | head`), a `BrokenPipeError` from the warning would escape a read path that is total today, and `03` §3.1 confirms `OSError` is mapped by `main()` to exit 2 — so a purely diagnostic write failure would turn a successful navigator/doctor/stage-exit command into a fail-closed exit 2. `07` §5.3 mandates exactly this test ("A stderr write failure may be injected with `monkeypatch` to assert `OSError` remains distinct") without saying what the consumer must then do, so the test author has no specified expected result. The bootstrap consumer (§3.2) has the same shape, but there exit-2-on-`OSError` is already its policy, so only the session consumer is contradictory.
- **Suggested fix:** Pick one policy and state it in §3.1 next to the code block. Recommended (preserves the documented total contract):
  ```python
  def _load_config(config_path: Path) -> dict:
      """Read config into a dict, warning on duplicates and tolerating bad input."""
      try:
          value, duplicate_keys = load_json_with_duplicates(config_path)
      except (OSError, json.JSONDecodeError):
          return {}
      try:
          warn_duplicate_keys(config_path, duplicate_keys)
      except OSError:
          pass  # a diagnostic write failure must not break a total read path
      return value if isinstance(value, dict) else {}
  ```
  Add to §3.3's compatibility matrix a row "Valid object, duplicates, stderr unwritable → session: parsed value returned, exit unchanged; bootstrap: existing `OSError`/exit-2 policy", and amend `07` §5.3 to assert that split. If propagate is chosen instead, delete the "return `{}` rather than fail" guarantee from §3.1 and say explicitly that a diagnostic write failure is the one way `_load_config` can raise. **See User Decision D4.**
- **References:** `00-core-definitions.md` §8; `05-config-and-distribution.md` §2.1, §2.2, §3.2, §3.3, §4; `07-testing-strategy.md` §5.3; `scripts/forge-session.py:614`; PRD REQ-CONFIG-01/03, REQ-COMPAT-02
- **Checklist:** CHECK-S11, CHECK-S18, CHECK-S19

### V-024: `05` §5.2 cites the adapter snapshot fixtures by a repo-relative path that does not exist
- **Severity:** improvement
- **Location:** `05-config-and-distribution.md` §5.2
- **Issue:** The sentence "Update the committed `expected-adapters/<agent>/scripts/` snapshots for the two changed consumers" names a path that does not exist at the repository root; the real path is `tests/fixtures/minimal-canon/expected-adapters/<agent>/scripts/` (confirmed present, carrying `forge-session.py` and `forge-bootstrap.py` for all six targets). `07` §2.3 cites the full correct path, so the suite is internally inconsistent and a fresh agent reading only `05` will search a path that does not resolve. Not blocking — the fixture is discoverable from `07` or from `tests/test_build_adapters.py`.
- **Suggested fix:** Replace `expected-adapters/<agent>/scripts/` with `tests/fixtures/minimal-canon/expected-adapters/<agent>/scripts/`, matching `07` §2.3.
- **References:** `05-config-and-distribution.md` §5.2, §8.2; `07-testing-strategy.md` §2.3; `tests/fixtures/minimal-canon/expected-adapters/`
- **Checklist:** CHECK-S26

### V-025: `score_branch_path` raises `KeyError` while `06` §7 states harness-invariant failures raise `RuntimeError`
- **Severity:** inconsistency
- **Location:** `06-compliance-and-coverage.md` §5.1 (`score_branch_path` docstring) vs §7 (Error Handling)
- **Issue:** §5.1 declares "Raises: `KeyError`: `expected_payload` is not a valid shared `StageExitPayload`." §7 declares the module's hierarchy: "Fixture/schema/harness invariant failures raise `RuntimeError`; filesystem and JSON exceptions retain `OSError` and `json.JSONDecodeError`", and lists "impossible expected payload" among the harness defects. A malformed `expected_payload` is exactly that defect, so the one new scorer entry point is specified to violate the hierarchy the same document establishes — and a bare `KeyError` escaping through `_to_result`/`run_branch_probe` is indistinguishable from an ordinary dict-access bug.
- **Suggested fix:** Change the docstring to: "Raises: `RuntimeError`: `expected_payload` is missing a required `StageExitPayload` key (`directives`, `nextSteps`, or `sentinel`) or its `directives.primaryCommand` — a harness defect, per §7, not a model miss." State that the implementation validates those keys explicitly before indexing rather than letting a raw `KeyError` escape.
- **References:** `06-compliance-and-coverage.md` §5.1, §5.2, §7; `00-core-definitions.md` §4; `eval/run-compliance-eval.py:731` (`_to_result`)
- **Checklist:** CHECK-S11

### V-026: The coverage guard must compare against `EXIT_STAGES`, but no spec says how a test obtains it from a hyphenated script
- **Severity:** improvement
- **Location:** `06-compliance-and-coverage.md` §2.1 (assertion list); `07-testing-strategy.md` §6.1
- **Issue:** `06` §2.1 requires that `CANONICAL_EXIT_SITES`' `skill` tuple "equals `EXIT_STAGES` from `00-core-definitions.md`, in the same order", and `07` §6.1 repeats it. `EXIT_STAGES` lives in `scripts/forge-session.py`, whose hyphenated filename makes it non-importable by name — and `06` §2.1's own preamble pushes the reader away from importing. `tests/test_stage_exit_protocol.py` today imports nothing from that script, and the repo has two incompatible precedents: drift-guard modules extract literals by regex + `ast.literal_eval` and explicitly forbid importing (`tests/test_stage_constants_parity.py`, echoed by `07` §5.1's "no import of the hyphenated scripts"), while behavioral tests import via `importlib.util.spec_from_file_location` (`tests/test_auto_verify.py:22`, `tests/test_doctor.py:24`). With neither named, the path of least resistance is to hardcode the nine names in the test — producing precisely the second hand-maintained allow-list that REQ-GUARD-01 and `04` §10 exist to prevent, and making the assertion vacuous.
- **Suggested fix:** Add one sentence to `06` §2.1 and mirror it in `07` §6.1: "The guard obtains `EXIT_STAGES` from `scripts/forge-session.py` by the drift-guard convention — regex-locate the assignment and `ast.literal_eval` it, exactly as `tests/test_stage_constants_parity.py` does — or, if the module is needed anyway, via `importlib.util.spec_from_file_location` as `tests/test_auto_verify.py` does. It MUST NOT re-list the nine names in the test file; a hardcoded copy is the second allow-list REQ-GUARD-01 forbids, and the assertion would then be vacuous." *Prefer the regex + `ast.literal_eval` form, consistent with `07` §5.1's stated no-import rule for drift guards.*
- **References:** `06-compliance-and-coverage.md` §2.1; `07-testing-strategy.md` §1, §5.1, §6.1; `04-skill-integration.md` §10; `tests/test_stage_constants_parity.py`, `tests/test_auto_verify.py:21-26`; `01-architecture-layout.md` §3.2
- **Checklist:** CHECK-S10, CHECK-S17
- *(Merged: cross-reference V-008 + types V-006)*

### V-027: §2.3 asserts the mirrored loader is inside an already-snapshotted fixture — the fixture scripts are 66-byte stubs
- **Severity:** error
- **Location:** `07-testing-strategy.md` §2.3 (fixture inventory, `minimal-canon` bullet); consumed by §6.3 bullet 2
- **Issue:** §2.3 states: "`tests/fixtures/minimal-canon/scripts/` plus each `…/expected-adapters/<agent>/scripts/`: generator snapshot inputs/outputs for the two changed consumers. **No new fixture file** — the mirrored loader lives inside scripts already snapshotted." The last clause is factually wrong. **Confirmed:** `tests/fixtures/minimal-canon/scripts/forge-session.py` is 66 bytes (`# fixture stub helper (forge-session)\nprint("forge-session stub")`) and `forge-bootstrap.py` is 70 bytes. No `load_json_with_duplicates`/`warn_duplicate_keys` body can ever appear in `expected-adapters/<agent>/scripts/`, so the minimal-canon snapshot equality test (`tests/test_build_adapters.py:139-142`, `hash_tree(adapters) == hash_tree(expected-adapters)`) proves helper *copying, naming, and mode* but proves **nothing** about the loader travelling byte-equal into the six bundles. An implementer following §6.3 bullet 2 through minimal-canon will write a test that passes vacuously — the exact silent-drift hole `tests/test_json_loader_parity.py` exists to close, reopened at the distribution boundary.
- **Suggested fix:** In §2.3, replace the parenthetical with: "`tests/fixtures/minimal-canon/scripts/` and each `expected-adapters/<agent>/scripts/` hold **stub** helpers (66–70 bytes); they snapshot helper *presence, filename set, and mode* only. **No new fixture file** is needed, and loader byte-equality is therefore **not** provable from minimal-canon. Assert loader co-distribution against the real repo helpers instead — the committed `adapters/<agent>/scripts/{forge-session,forge-bootstrap}.py` (guarded by the existing `skipif(not ADAPTERS.is_dir())` convention in `tests/test_build_adapters.py`) and/or `build-adapters.py --check`." Update §6.3 bullet 2 to point at that surface rather than at minimal-canon.
- **References:** `07-testing-strategy.md` §6.3; `tests/fixtures/minimal-canon/scripts/`; `tests/test_build_adapters.py:139-142`; `05-config-and-distribution.md` §5.1–§5.2
- **Checklist:** CHECK-S35, CHECK-S37

### V-028: "byte-equal to canon (including Pi)" is false for `forge-session.py` as a whole file
- **Severity:** inconsistency
- **Location:** `07-testing-strategy.md` §6.3, bullet 2
- **Issue:** The spec says "both emitted consumers carry the mirrored loader byte-equal to canon (**including Pi**), mode `0644`, without a generated header." **Confirmed:** `cmp adapters/pi/scripts/forge-session.py scripts/forge-session.py` reports a difference at byte 23760, line 503, because `build-adapters.py` runs the `/feature-forge:` → `/skill:` substitution pass over the Pi copy after the verbatim helper copy loop; `adapters/pi/scripts/forge-bootstrap.py` and every Claude/Codex/Copilot/Cursor/Gemini copy *are* byte-identical. The loader *block* is byte-equal everywhere (it contains no slash-command literals), but the sentence as written invites a whole-file assertion for Pi that will fail, and contradicts the generator's own documented Pi divergence contract (REQ-GEN-05).
- **Suggested fix:** Scope the assertion to the extracted function block: "…carry the mirrored `load_json_with_duplicates`/`warn_duplicate_keys` **function bodies** byte-equal to canon for all six targets. Whole-file byte equality holds for `forge-bootstrap.py` on every target and for `forge-session.py` on every target **except Pi**, whose copy legitimately differs by the `/feature-forge:` → `/skill:` substitution (REQ-GEN-05); assert the Pi copy differs *only* by that substitution, reusing the generator's existing invariant."
- **References:** `scripts/build-adapters.py:1408-1418`; `adapters/pi/scripts/forge-session.py`; `05-config-and-distribution.md` §5.2; V-027
- **Checklist:** CHECK-S37

### V-029: No test pins the patched capability-detection semantics (permission-not-presence, consent-is-`interactive`, auto-path-through-`standard`)
- **Severity:** gap
- **Location:** `07-testing-strategy.md` §6.2 and §3.4
- **Issue:** Found independently by two verifier slices. Commit f383837 patched `04-skill-integration.md` §3.2 to state that clause (b) is a **permission** test rather than a tool-presence test, and that a session barring *unsolicited* dispatch while offering a question tool is `interactive`, not `manual`; `04` §3.3 step 2 adds that an auto-verify directive under such a bar routes through the `standard` gate. `02` §4/§5.1 restates both, and `00` §3/§4 carry it in the docstring and field comment. **None of it is verified.** The words `unsolicited`, `consent`, `permission` and `permitted` occur zero times in `07-testing-strategy.md`. It is not testable through `stage_exit` — capability arrives as the `--verify-capability` *input*, so §3.4's matrix (which only crosses given capability values) cannot cover it; it is skill/canon prose, and `07`'s canon inventories do not reach it (§6.2's six bullets cover loop outcome words, the runner-contract pointer, `--model` wording, `state-note` call sites, gate labels, and no-post-sentinel authoring; §6.1 delegates to `06` §2.3, whose five assertions are invocation/stage/owner/terminal-print/sentinel only). §6.2's nearest bullet asserts only that "capable Pi is not excluded by host-name wording", which a spec using the *old* presence reading would also satisfy. So the single contract in this feature that has already been misread once, is prose-only, and degrades silently (a model self-reporting `manual` just prints a copy-paste command and no one notices) ships with zero coverage — while §8.1 claims "100% host/capability behavior coverage".
- **Suggested fix:** Add a §6.2 canon bullet asserting, against `skills/` (never `adapters/`): the capability-determination prose in every direct/outer skill's exit closure states clause (b) as **permitted dispatch, not listed tool**; states that a consent-gated dispatch with a question tool available is `interactive` (with `manual` reserved for *no question tool and no permitted dispatch*); and states that an auto-verify directive under a no-unsolicited-dispatch bar is presented through the Standard Verify Gate and dispatched on the affirmative — never skipped, never resolved by advancing to the production successor. Specify copied-string negatives that must fail the guard: rewrite the clause to tool-presence wording, downgrade the consent case to `manual`, delete the auto-path-through-gate sentence. Add to §3.4 the companion row: with auto-verify effective and outstanding and a caller under a no-unsolicited-dispatch bar *with* a question tool, the caller passes `--verify-capability interactive`, the payload keeps `runInStageVerify: true`, the skill presents the gate before dispatching, and no rendered block promotes the production successor under any gate response. Reference both from the REQ-EXIT-07 row of `07`'s Requirement Coverage table.
- **References:** `04-skill-integration.md` §3.2, §3.3 step 2; `02-stage-exit-routing.md` §4 (final paragraph), §5.1; `00-core-definitions.md` §3, §4; `06-compliance-and-coverage.md` §2.3; PRD §3.1 REQ-EXIT-07
- **Checklist:** CHECK-S02, CHECK-S34, CHECK-S36, CHECK-S38
- *(Merged: testing V-003 + cross-reference V-003)*

### V-030: No test row for the `CLEAN_ROOM_UNAVAILABLE` re-exit contract
- **Severity:** improvement
- **Location:** `07-testing-strategy.md` §3.4 and §6.2
- **Issue:** `04` §3.2 closes with a specific failure contract: when clean-room dispatch advertised as available returns `CLEAN_ROOM_UNAVAILABLE` or a non-answer, treat verification as failed/not run, leave debt unresolved, obtain a **fresh** stage-exit payload with `manual` capability, and "never reuse an earlier payload that promotes production advancement (REQ-REL-02)". `07` has no row for it. The nearest coverage is §7.2 negative 11 ("recovery incorrectly advancing to production"), but per `06` §3.2 the branch fixture's `recovery` scenario is driven by `reverifyOutcome: findings|failed` — an unresolved re-verify, not a dispatch-capability failure — so it does not exercise the stale-payload-reuse mode. §3.3's chain tests likewise re-exit after *state transitions*, not after a dispatch failure.
- **Suggested fix:** Add to §3.4: "Cover the advertised-then-unavailable dispatch path: after a payload with `verifyGate == standard` and `runInStageVerify: true`, simulate `CLEAN_ROOM_UNAVAILABLE`/non-answer and assert (a) the persisted `auto-verify-pending` debt is still readable and unresolved, (b) a fresh `stage-exit --verify-capability manual` yields a verify-first payload whose `primaryCommand` is the verify command, and (c) the earlier payload's `deferredCommand`/`nextCommand` never becomes primary." Add the matching canon assertion to the §6.2 bullet from V-029.
- **References:** `04-skill-integration.md` §3.2 (final paragraph); `06-compliance-and-coverage.md` §3.2; `07-testing-strategy.md` §7.2 negative 11
- **Checklist:** CHECK-S34

### V-031: §8.1's "100% verify state coverage" is not backed by any matrix row for the `none` read label or the legacy `pending` status
- **Severity:** improvement
- **Location:** `07-testing-strategy.md` §8.1 (bullet 4) vs §3.4 table and §4.1/§4.2
- **Issue:** §8.1 claims "**100% verify state coverage:** every shared persisted status and every shared read label". The shared vocabularies in `00` §2 are `VerifyStateLabel` = 7 labels (`fresh`, `stale`, `failing`, `never`, `auto-pending`, `skipped`, `none`) and `VerifyStatus` = 6 statuses (including plain `pending`, documented in `00` §6 as "existing generic/manual pending state"). Two members have no row: **`none`** — reachable and behaviorally meaningful, since `VERIFY_TOKEN_BY_STAGE` (`scripts/forge-session.py:198-204`) has no entry for `forge-6-docs` and `_verify_state_for` returns `"none"` for a tokenless stage (`:1482-1484`, source comment "forge-6-docs has no verify step"), while §3.4's table covers only `fresh`/`skipped`, `never`/`stale`/`failing`/`auto-pending`, and "outstanding", and §3.6 exercises docs routing without pinning `verifyState`/`verifyGate`; and **plain `pending`** — `03` §3.3's writer matrix has no row for it and no read-side row in §4.1/§4.2 classifies a legacy `pending` entry.
- **Suggested fix:** Add a §3.4 row: "| `none` (tokenless stage, e.g. `forge-6-docs`) | either | either | production / `none`; no verify command promoted |", and a §4.1 read-parity bullet: "a legacy plain `pending` entry classifies consistently across `verify_state`, `_verify_state_for`, `pending_verify`, `build_rows`, and epic `render-status`, and is never silently upgraded to `auto-pending` or downgraded to `never`." Alternatively narrow §8.1's claim to the labels/statuses actually enumerated.
- **References:** `00-core-definitions.md` §2, §6; `scripts/forge-session.py:198-204, :1456-1490`; `03-verification-state.md` §3.3
- **Checklist:** CHECK-S36

### V-032: "single full gate" overstates `scripts/validate.sh` — its pytest step is non-fatal when pytest is absent
- **Severity:** improvement
- **Location:** `07-testing-strategy.md` §8.2 and the Verification checklist item for `bash scripts/validate.sh`; §1 layer 5
- **Issue:** §8.2 says "`bash scripts/validate.sh` is the single full gate: it runs purity, adapter drift, pytest, installer and adapter-source verification, ruff when available, traceability, and version sync." The step list is accurate, but the pytest step is conditional and explicitly non-fatal — **confirmed** at `scripts/validate.sh:218`: `echo "SKIP: pytest not installed; skipping epic-manifest test suite (non-fatal)"`. Traceability and version-sync degrade to warnings on a missing tree/script as well (`:356-361`, `:379-380`). §8.2 already carves out the ruff soft-skip but not the pytest one — so on an interpreter without pytest, the acceptance evidence for this entire strategy can go green while zero tests ran. That is precisely the "false evidence" §8.1 refuses elsewhere.
- **Suggested fix:** In §8.2, after the gate sentence add: "Its pytest step is **conditional and non-fatal** (`scripts/validate.sh:210-219` prints `SKIP: pytest not installed` and continues), so acceptance requires the run to show `PASS: epic-manifest pytest suite` — a `SKIP` there is not a pass. Run `python3 -m pytest tests -q` explicitly alongside the gate on any interpreter where that line is not `PASS`." Mirror the wording in the Verification checklist item.
- **References:** `scripts/validate.sh:206-219, :356-361, :379-380`; `07-testing-strategy.md` §1 layer 5, §8.1
- **Checklist:** CHECK-S34, CHECK-S36

### V-033: §4.4's "replace the digest" guidance discards a working drift guard and ignores its negative control
- **Severity:** improvement
- **Location:** `07-testing-strategy.md` §4.4, final paragraph
- **Issue:** The instruction is "Replace it with a feature-specific baseline/structural assertion that proves only the intended enum and scheduling fields changed; do not blindly re-pin a digest without comparing the parsed schema." The diagnosis is right (the digest strips only `description` keys, so adding `auto-verify-pending` and the scheduling properties will move it), but the remedy is stronger than needed and conflicts with the guard's own documented convention: `tests/test_state_schema_conformance.py:255-268` says "A real schema change (a property, type, enum, or required list) belongs to a different feature and updates this constant in the same PR." Removing the digest permanently loses the tripwire for future *unintended* schema edits. The spec also does not mention the paired negative control `test_the_contract_digest_ignores_prose_but_not_structure` (`:299+`), which an implementer told to "replace" the digest may delete along with it.
- **Suggested fix:** Reword to: "Re-pin `PRE_R4_SCHEMA_CONTRACT_SHA256` to a new post-feature baseline **in the same PR** (renaming it accordingly), and **add** a structural assertion that diffs the parsed pre/post contract and proves the only changes are the `verifyEntry.status` enum gaining `auto-verify-pending` and the additive `scheduledAt`/`scheduledStageVersion` properties. Keep `test_the_contract_digest_ignores_prose_but_not_structure` intact — it is the negative control that makes the digest meaningful. Do not re-pin without the structural diff, and do not delete the digest guard."
- **References:** `tests/test_state_schema_conformance.py:255-300`; `00-core-definitions.md` §6; `03-verification-state.md` §2.1
- **Checklist:** CHECK-S35

---

## Fix Execution Plan

### User Decisions Required

**D1 (V-015) — where the `state-verify` registration and immediate `state-note` recipe live.**
*Recommended: specify the edits.* Add `04-skill-integration.md` §4.3 defining both edits to
`references/shared-conventions.md` (register `state-verify` in the Pipeline State Protocol
verb inventory; add the named `state-note` recipe the PRD/tech skills reference), and keep
both layout rows. Alternative: delete the row from `01` §2 and the line from tech-spec §2.1
and record the deliberate per-skill inlining. Specifying wins because
`tests/test_state_verb_call_sites.py::test_the_epic_mandate_itself_is_still_documented`
treats that file as the normative home of the `--epic` mandate the new verb must obey
(V-018).

**D2 (V-016) — is converting `skills/forge-verify/references/findings-template.md`'s
epic-state write recipe to `state-verify` in scope for this feature?**
*Recommended: yes.* Leaving it makes every epic verification classify `stale` under `03`
§5.2 and keeps a model-authored JSON write that REQ-STATE-03 forbids. If deferred, the
deferral must be recorded in PRD §6 (Out of Scope) and `03` §5.2 must state that epic
freshness is unreachable until then.

**D3 (V-006) — `warning: str` versus `warnings: list[str]`.**
*Recommended: list,* for symmetry with `RenderStatus.warnings` (`04` §2.2), with the
deterministic order epic-fallback → debt-metadata → revision-mismatch. Alternative: keep
the single string and state an explicit precedence rule in the `00` §4 comment.

**D4 (V-023) — `_load_config` stderr-write-failure policy.**
*Recommended: swallow* (`try/except OSError: pass` around `warn_duplicate_keys`), which
preserves today's total read path for `rank-features`/`doctor`/`stage-exit` when stdout is
piped and stderr closes. Alternative: propagate as `OSError` → exit 2, in which case the
"return `{}` rather than fail" guarantee must be deleted from §3.1. Bootstrap's exit-2
policy is unaffected either way.

Two further choices carry a stated default and do **not** block: V-007 (derive the `00` §2
constants via `get_args` — recommended — versus adding a parity test) and V-026 (obtain
`EXIT_STAGES` via regex + `ast.literal_eval` per the drift-guard convention — recommended,
consistent with `07` §5.1's no-import rule — versus `importlib`).

All other findings are spec-text edits that can be applied directly. **No source, adapter,
or backlog changes are implied by this findings set.**

### Execution Steps

#### Step 1: Correct the shared type/contract documentation in `00-core-definitions.md`
- **Files:** `specs/stage-exit-coverage/00-core-definitions.md`
- **Addresses:** V-001, V-002, V-003, V-004, V-005, V-006, V-007, V-008
- **Checklist:** CHECK-S05, S08, S10, S12, S13, S15, S19, S31
- **Action:** In the "Public API and Internal Surface" bullet at line 584, change "The §5 `stage_exit`, `next_stage`" to "The §3 `stage_exit`, the §5 `next_stage`" (V-001). In §4: rewrite the `EpicReconcile.deferred` comment to describe a canonical deferred **command** present only when `required: True` (V-002); rewrite the `autoVerifyDebtRecorded` comment to state the `True`/`False` combination is unreachable, citing `03` §4.1 (V-003); add `stageNoun: str` next to `stage` with its `{stageNoun}`-slot comment (V-004); add `verifyStage: str | None` next to `verifyState`, explicitly distinguished from branch-only `servedStage` (V-005); apply the D3 decision to `warning` (V-006). In §2, apply the V-007 decision (recommended: add `get_args` to the `typing` import and derive `EXIT_STAGES` and the four `EXIT_OUTCOMES` values from their aliases, plus the `VERIFY_MODE_TO_STAGE` parity sentence). In §6, extend the `cmd_state_verify` docstring with `Args:` for all nine parameters and a `Returns:` line (V-008). Do not alter §3's validation order or §7–§8.
- **Depends on:** none (D3 answer needed for the `warning` edit)

#### Step 2: Close the routing gaps in `02-stage-exit-routing.md`
- **Files:** `specs/stage-exit-coverage/02-stage-exit-routing.md`, `tech-spec.md`, `04-skill-integration.md`
- **Addresses:** V-002 (composition rule), V-009, V-010, V-011, V-012
- **Checklist:** CHECK-S08, S14, S16, S18, S20, S21, S22, S26, S29
- **Action:** §5.2 rule 5 — add the one-sentence precedence rule between `epicReconcile["deferred"]` and `_next_steps_block(deferred_command=…)` (V-002). §8 — add the sibling-path resolution (`Path(__file__).resolve().parent / "epic-manifest.py"`), `sys.executable`, and `subprocess.run(..., capture_output=True, text=True, timeout=10, check=False)` with the `TimeoutExpired`/`OSError` → `UsageError` mapping; add the matching row to the §10 error table (V-009). §5.1 — add the consent-variant paragraph (reuse the gate block with `verifyGate: none`, omit choice 2, two labeled choices, skip persisted as `skipped`), mirror one sentence into `04` §3.3 step 2, and add the variant to tech-spec §3.3 so the decision is anchored (V-010). §9 and §10 — add the exact epic-member fallback warning template and the `invalidAutoVerifyKeys` rendering rule in sorted order (V-011). Dependencies section — add `03-verification-state.md` with its one-line rationale, and replace `04`'s two descriptive dependency bullets with filenames (V-012).
- **Depends on:** Step 1

#### Step 3: Specify the downstream pre-flight consumers and the `--findings-file` guard in `03-verification-state.md`
- **Files:** `specs/stage-exit-coverage/03-verification-state.md`, `04-skill-integration.md`, `01-architecture-layout.md`
- **Addresses:** V-013, V-014, V-005 (§5.3 wording)
- **Checklist:** CHECK-S01, S02, S30, S31, S38
- **Action:** Add §5.4 "Downstream pre-flight parity (REQ-DEBT-05)" stating that any canon gate reading a `stages.forge-verify-*` entry treats `auto-verify-pending` as an explicit third case — outstanding, not resolved, not `never` — using the §5.3 diagnostic wording. Amend §5.3 to name the stage-exit JSON keys `verifyState`/`verifyStage`/`verifyCommand` (V-005). In §3.3 and §7.1, add relative-and-contained validation for `--findings-file` (V-014). Extend `04` §7.2 to require `skills/forge-6-docs/SKILL.md` Step 1's enumeration to add `auto-verify-pending` to the warn branch, and add a subsection under `04` §6 requiring the same for `skills/forge-5-loop/SKILL.md` Step 1b; annotate both skills in `01` §2 (V-013).
- **Depends on:** Step 1

#### Step 4: Give the unowned canon files owning specs
- **Files:** `specs/stage-exit-coverage/04-skill-integration.md`, `01-architecture-layout.md`, `tech-spec.md`
- **Addresses:** V-015, V-016, V-017, V-018, V-019, V-020, V-021
- **Checklist:** CHECK-S01, S03, S04, S05, S06, S08, S22, S23, S24, S25, S38
- **Action:** Apply D1 to `references/shared-conventions.md` (recommended: new `04` §4.3 specifying the `state-verify` registration and the named `state-note` recipe; keep both layout rows and update their annotation) (V-015). Apply D2 to `skills/forge-verify/references/findings-template.md` (recommended: add it to both layouts and to `04` §1's scope list, and add `04` §5.4 replacing the heredoc `os.replace` snippet with the `state-verify --stage forge-0-epic` invocation) (V-016). Add to `04` §5.2 the instruction to delete the "Deliberate R4 exclusion" blockquote and replace `forge-verify` Step 6's hand-authored write; add to §5.3 the instruction to replace `forge-fix` Step 5's `verifiedStageVersion` write and rewrite the lines 79/86 freshness claims (V-017). Add the `state-verify` bash fence to `04` §5.1 with the `--epic` member sentence adjacent to it, and add `--epic` to the §3.1 flags-table rows (V-018). Add `skills/forge/SKILL.md` to `01` §2 and add `04` §4.3's navigator subsection covering the `verifyState` enum, step 1/2b handling, the legend marker, and nested-caller dispatch (V-019). Add the `owner: nested`/`owner: direct` token paragraph to `04` §5.1 and the matching instruction to §3.3 step 2 and the navigator subsection (V-020). Add the REQ-FOLLOW-01 subsection to `04` §6.3/§6.4 with the runner-contract edit, plus its Requirement Coverage row (V-021).
- **Depends on:** Steps 1–3 (D1 and D2 answers needed)

#### Step 5: Fix the config and eval specs
- **Files:** `specs/stage-exit-coverage/05-config-and-distribution.md`, `06-compliance-and-coverage.md`
- **Addresses:** V-022 (05 half), V-023, V-024, V-025, V-026
- **Checklist:** CHECK-S10, S11, S15, S17, S18, S19, S26, S38
- **Action:** `05` — apply D4 to §3.1's `_load_config` body and add the stderr-unwritable row to §3.3's compatibility matrix (V-023); replace `expected-adapters/<agent>/scripts/` with `tests/fixtures/minimal-canon/expected-adapters/<agent>/scripts/` in §5.2 (V-024); change the REQ-CONFIG-04 coverage row's `§5.1` to `§3.3` (V-022). `06` — change `score_branch_path`'s `Raises:` from `KeyError` to `RuntimeError` and require explicit key validation before indexing (V-025); add the `EXIT_STAGES` access sentence and the no-hardcoded-list prohibition to §2.1 (V-026).
- **Depends on:** none (D4 answer needed)

#### Step 6: Propagate every new assertion into `07-testing-strategy.md`
- **Files:** `specs/stage-exit-coverage/07-testing-strategy.md`
- **Addresses:** V-027, V-028, V-029, V-030, V-031, V-032, V-033, plus the test-side halves of V-009, V-011, V-013, V-014, V-016, V-018, V-023, V-026
- **Checklist:** CHECK-S34, S35, S36, S37
- **Action:** §2.3 — correct the minimal-canon stub description and retarget loader-distribution evidence to the committed `adapters/` helpers (V-027); §6.3 bullet 2 — scope byte-equality to the extracted function bodies and carve out the Pi substitution (V-028). §6.2 — add the capability-semantics canon bullet with its copied-string negatives (V-029); add the `tests/test_state_verb_call_sites.py` bullet (V-018); add the "no `.epic-state.json` write recipe or `os.replace` snippet under `skills/`" assertion (V-016); mirror the `EXIT_STAGES` access sentence into §6.1 (V-026). §3.4 — add the consent-barred auto-verify row (V-029), the `CLEAN_ROOM_UNAVAILABLE` row (V-030), and the `none`-verify-state row (V-031). §3 — add the render-status timeout case and replace "the named PRD fallback warning" with an assertion on the exact template (V-009, V-011). §4.1 — add the legacy-`pending` read-parity bullet (V-031), the pre-flight consumer rows (V-013), and the `directives.verifyStage` assertion (V-005); §4.2 — add the `--findings-file` rejection case (V-014). §4.4 — reword to re-pin-plus-structural-diff and preserve the negative control (V-033). §5.3 — record the D4 expectation split (V-023). §8.2 and the Verification checklist — add the non-fatal-pytest qualifier (V-032). Update the Requirement Coverage rows for REQ-EXIT-07 and REQ-DEBT-05.
- **Depends on:** Steps 1–5

#### Step 7: Refresh traceability and re-run the deterministic gates
- **Files:** `specs/stage-exit-coverage/TRACEABILITY.md`, then all of `specs/stage-exit-coverage/`
- **Addresses:** V-022, plus the new section anchors created in Steps 2–6
- **Checklist:** CHECK-S15, CHECK-S38
- **Action:** In `TRACEABILITY.md` set REQ-EXIT-03 → "`02` §3, §5–§6"; REQ-EXIT-04 → "`02` §3.3, §6"; REQ-EXIT-06 → "`02` §4–§5"; REQ-CONFIG-04 → "`05` §2.1, §3.3" (V-022). Add the new anchors: `03` §5.4 and `04` §6/§7.2 to the REQ-DEBT-05 row; `04` §5.4 to the REQ-STATE-03 row; the amended `04` §6.3/§6.4 to REQ-FOLLOW-01; `04` §4.3 to REQ-FOLLOW-02 and REQ-DEBT-05. Then re-run both gates and confirm they stay clean:
  ```bash
  R="$HOME/.claude/skills/feature-forge"
  python3 "$R/scripts/validate-traceability.py" \
    specs/stage-exit-coverage/PRD.md specs/stage-exit-coverage/ --json   # 55 REQs, 0 uncovered, 0 orphaned
  rauf-stable backlog validate . --backlog specs/stage-exit-coverage \
    --specs-dir specs/stage-exit-coverage --json                        # valid: true
  ```
  Also re-parse every ```python block in the edited specs with `ast.parse` to confirm the `get_args` and `try/except` edits still compile.
- **Depends on:** Steps 1–6

#### Step 8: Re-check the backlog against the amended specs
- **Files:** `specs/stage-exit-coverage/backlog.json` (read-only in this step)
- **Addresses:** downstream consistency of Steps 1–7
- **Checklist:** CHECK-S38
- **Action:** Steps 1–6 add new obligations that the 29-item backlog was authored before: the `stageNoun`/`verifyStage` directive fields (V-004, V-005), the `subprocess` timeout (V-009), the consent-gate variant (V-010), the pre-flight consumers in `forge-6-docs`/`forge-5-loop` (V-013), the `shared-conventions.md` and `findings-template.md` edits (V-015, V-016), the falsified-canon deletions (V-017), the `--epic` fences (V-018), the navigator skill (V-019), the ownership token (V-020), and the REQ-FOLLOW-01 edit (V-021). After the spec fixes land, re-run `/feature-forge:forge-verify stage-exit-coverage backlog` and add or amend items for any obligation with no covering item. Do **not** amend the backlog before the spec fixes are applied — the amended specs are the ground truth it must trace to.
- **Depends on:** Step 7
