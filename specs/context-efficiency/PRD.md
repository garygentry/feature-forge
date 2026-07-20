# context-efficiency — Product Requirements Document

> Requirements-only. Describes *what* this feature must achieve, not *how* it
> will be built (that is forge-2-tech). Evidence base: the pre-PRD reference set
> in `.reference/` (CHARTER, AUDIT, LOAD-MAP, RECOMMENDATIONS, GUARDRAILS),
> produced by the 2026-07-19 token-efficiency audit at v0.12.9 / b9f0871.

## 1. Problem Statement

Every forge pipeline invocation pays a fixed instruction-token cost before it
touches any feature artifact. A 2026-07-19 top-to-bottom audit found the
architecture fundamentally sound — deterministic compute already lives in
scripts, heavy content is delegated to disposable subagent contexts, the
session hook is near-silent — but **progressive-disclosure granularity is off**
in a handful of places:

- Three reference files load whole when a caller needs only a slice
  (`shared-conventions.md`, `verification-checklists.md`,
  `runner-contract.md`).
- The plugin-root prelude is duplicated ~31 times across runtime-loaded
  surfaces.
- A verbose JSON Schema (`pipeline-state-schema.json`) and a config schema
  (`forge-config-schema.json`) are read per stage for a small slice of their
  actionable content.

A typical stage session carries **~13–19k tokens of instruction overhead
before any artifact**, and because the pipeline deliberately recommends
`/clear` at every stage boundary, that fixed overhead is re-paid per stage —
roughly **100–150k instruction tokens across a full feature run**, of which an
estimated **30–40% is recoverable** at low-to-moderate risk.

**Who has this problem:** every user of the forge pipeline (each stage session
and each verifier/researcher/writer subagent pays the overhead) and the
maintainers who must keep the guidance surfaces within CI limits and reliable
across five host adapters.

**Why now:** the pipeline is mature and in extensive real use; the audit has
already located the recoverable waste and separated it from the deliberate
design wins that must not regress. The window is a clean, measurable
optimization before further feature growth compounds the overhead.

## 2. User Stories

- As a **forge pipeline user**, I want each stage/subagent invocation to load
  only the guidance it actually needs, so that more of the context window is
  available for real artifact work and long runs stay within budget.
- As a **verifier subagent** (and each member of a parallel verify fan-out), I
  want to load only my mode's checklist, so that a multi-instance fan-out does
  not each carry all six modes plus orchestrator-facing material.
- As the **loop stage (forge-5-loop)**, I want the loop-runner defaults and the
  always-needed contract sections without dragging in agent-selection detail
  that only applies when an agent argument is configured.
- As a **pipeline maintainer**, I want each efficiency change to be an
  independently revertible, behavior-preserving relocation/dedup/script-
  extraction, so that a regression reverts one change rather than a batch, and
  no interactive protocol silently changes.
- As a **maintainer of non-Claude adapters** (gemini, codex, cursor, copilot),
  I want every moved or split reference file to remain citation-discoverable
  and regenerate cleanly, so that non-Claude hosts still resolve every guidance
  file they need.
- As the **person accountable for pipeline quality**, I want proof that a full
  dogfooded feature run behaves identically after these changes, so that
  "token savings" never comes at the cost of a changed prompt, gate, or output.

## 3. Functional Requirements

Each recommendation (R1–R6) is a distinct capability area. Per the delivery
decision, **each is an independently shippable, independently revertible unit**
(REQ-DELIV-01). The audit's projected savings are documented in `LOAD-MAP.md`
and are **non-binding goals** — the binding bar is in §8.

### 3.1 Verification-checklist mode split (R1)

- REQ-R1-01: A verifier subagent (or a member of a parallel fan-out) MUST be
  able to load only the checklist for the mode it is running (`prd`, `tech`,
  `specs`, `backlog`, `impl`, or `epic`), rather than all six modes.
  - Priority: P0
- REQ-R1-02: Orchestrator-facing material (the Findings Document Template,
  Example Findings, and Epic Mode State Write Detail) MUST NOT be loaded into
  verifier subagent contexts; it belongs only to the orchestrator role.
  - Priority: P0
- REQ-R1-03: The dual-role separation in forge-verify (the "which role are
  you?" guard, v0.12.1) MUST remain intact; the mode split must not reintroduce
  self-dispatch or leak orchestrator material to the subagent.
  - Priority: P0
  - Notes: Guardrail §6.
- REQ-R1-04: The per-mode "executed N of M checks" self-check MUST remain
  correct against the reduced, mode-scoped file (it should become more robust,
  not weaker).
  - Priority: P0
- REQ-R1-05: Every mode's set of CHECK-IDs MUST be preserved exactly across the
  split — no check added, dropped, or renumbered.
  - Priority: P0

### 3.2 Within-file plugin-root prelude dedup (R2)

- REQ-R2-01: Within any single runtime-loaded file that currently repeats the
  3-line `R=` plugin-root resolver block, the first occurrence MUST remain
  verbatim and subsequent occurrences MUST be reduced to a compact reference
  form, without changing execution behavior at any call site.
  - Priority: P1
- REQ-R2-02: Dedup MUST be within-file only. No executable path may depend on a
  cross-file "see another file for the prelude" pointer; each skill body must
  remain able to resolve the plugin root without reading any other file.
  - Priority: P0
  - Notes: The inline first-hint prelude (`${CLAUDE_PLUGIN_ROOT:-}`) is a
    deliberate reliability fix (PR #101) for non-Claude installs — Guardrail §5.

### 3.3 Conditional process-overview read (R3)

- REQ-R3-01: The navigator (`forge` skill) MUST read
  `references/process-overview.md` only when the user asks how the pipeline
  works / architecture questions — not as an unconditional setup step. Routine
  dashboard/status rendering MUST NOT load it.
  - Priority: P1

### 3.4 Eliminate the per-stage state-schema read (R4)

- REQ-R4-01: Stages that write `.pipeline-state.json` MUST no longer need to
  read the full `pipeline-state-schema.json` (191 lines of JSON Schema) on each
  invocation to author correct state.
  - Priority: P0
- REQ-R4-02: The preferred mechanism is a script-extraction (a
  `forge-session.py` state patch/write helper) because it additionally removes
  hand-authored-JSON drift; a compact annotated example is the documented
  fallback. The requirement is the *outcome* in REQ-R4-01 — the specific
  mechanism is finalized in the tech spec.
  - Priority: P0
  - Notes: This is a constraint on preference, not a mandate; see §5.
- REQ-R4-03: The schema file MUST remain the source of truth for CI/validation
  even after it is no longer read per stage.
  - Priority: P1
- REQ-R4-04: All state-write touch points MUST be covered (entry stamp,
  incremental `artifacts[]` updates, completion, `notes`, `deferredDecisions[]`,
  `epicChangeRequests[]`, branch field) — a partial extraction that leaves some
  sites hand-authoring JSON is not acceptable.
  - Priority: P0

### 3.5 Resolved loop-runner config subcommand (R5)

- REQ-R5-01: forge-5-loop and forge-4-backlog MUST be able to obtain the
  resolved, default-filled `loopRunner` configuration without reading the full
  `forge-config-schema.json` (~2k words) solely for defaults.
  - Priority: P0
- REQ-R5-02: The resolved-config capability MUST eliminate the class of
  "model mis-merged the defaults" errors by making default resolution
  deterministic.
  - Priority: P1
  - Notes: Preferred mechanism is a `forge-session.py effective-config`
    subcommand (§5); outcome is the requirement.

### 3.6 Runner-contract split: always vs. conditional (R6)

- REQ-R6-01: forge-5-loop MUST load the always-needed runner-contract sections
  (model-selection precedence, run mode, launch, monitor arming, event
  reactions, inform-user template) on every run.
  - Priority: P0
- REQ-R6-02: The agent-selection material MUST load only when
  `loopRunner.agentArgument` is configured; the optional-flags catalog MUST be
  reachable but not loaded by default.
  - Priority: P0
- REQ-R6-03: The split MUST NOT push runner-contract text back into the
  forge-5-loop skill body (it is at the 300-line CI cap).
  - Priority: P0
  - Notes: Guardrail §2.

### 3.7 Cross-cutting delivery & portability

- REQ-DELIV-01: Each of R1–R6 MUST be independently shippable and independently
  revertible (its own change/PR), following the audit's sequencing (R1+R2+R3
  quick wins → R5 → R4 → R6).
  - Priority: P0
- REQ-PORT-01: Every new or moved reference file MUST be discoverable by the
  adapter build's citation-driven fan-out — i.e. cited by path from at least
  one skill body — so it ships to all non-Claude adapters.
  - Priority: P0
- REQ-PORT-02: Reference files read by non-Claude hosts MUST NOT contain
  Claude-only tokens (e.g. a literal `/clear` or Claude-only tool names); moved
  content must stay host-neutral.
  - Priority: P0
  - Notes: The shared-refs resolution gap (#122/#132) is the cautionary tale.
- REQ-PORT-03: All five adapters (claude, gemini, codex, cursor, copilot) MUST
  regenerate cleanly and fixtures MUST be refreshed for any moved/split path.
  - Priority: P0

## 4. Non-Functional Requirements

### 4.1 Performance (token load)

- REQ-PERF-01: Each shipped recommendation MUST produce a measured net
  reduction in instruction tokens on its targeted invocation, measured against
  a **freshly re-measured baseline** at implementation time (not the audit's
  static snapshot).
  - Priority: P0
- REQ-PERF-02: The changes MUST NOT increase the always-loaded surface (the 13
  frontmatter descriptions, ~1.2k tokens) or the common-case `SessionStart`
  hook output (silent today).
  - Priority: P0

### 4.2 Behavior preservation (correctness)

- REQ-BEHAV-01: Zero behavioral diff. A full dogfooded feature run (all
  authoring stages + verify + loop + docs) MUST exhibit the same prompts,
  gates, guards, and outputs as before the changes.
  - Priority: P0
- REQ-BEHAV-02: All frozen interactive protocols MUST be preserved verbatim in
  behavior: AskUserQuestion turn structure, Decision Support protocol, Branch
  Setup/Reconciliation prompts, Stage-Entry Guard and Stage-Completion Re-check
  classification, the Git Commit two-commit sequence (never `--amend`), verify
  gates, stage-exit directive handling, and anti-fabrication guards. If a
  sentence must change wording to move, that MUST be flagged in review rather
  than silently adapted.
  - Priority: P0

### 4.3 Observability / measurability

- REQ-OBS-01: Baselines MUST be re-measured from real dogfood transcripts
  before adopting any numeric success target; the measurement method used MUST
  be recorded so before/after comparisons are reproducible.
  - Priority: P0
  - Notes: Guardrail §7; consumption-data-refresh dogfood runs are the evidence
    source.
- REQ-OBS-02: For R4 specifically, whether the model actually performs the
  per-stage schema read MUST be confirmed from transcripts, and the realized
  savings claim scaled to the observed read frequency. (This affects the
  *reported savings*, not whether R4 ships — the script-extraction is justified
  by its drift-removal benefit regardless.)
  - Priority: P1

### 4.4 Maintainability (drift resistance)

- REQ-MAINT-01: The drift-guard test discipline
  (`tests/test_stage_exit_protocol.py`-style) MUST be extended to cover every
  split/moved file — not weakened. Specifically: each per-mode checklist file
  asserts its expected CHECK-IDs and the skill's expected-count table matches;
  every invoke-point citation names an existing file and every new reference
  file is cited by ≥1 skill.
  - Priority: P0

## 5. Constraints

Technical and organizational constraints that must be respected (from
`GUARDRAILS.md` and project history):

- **C-1 Behavior preservation is the prime directive.** Every change is a
  relocation of instruction text, a dedup, or a script extraction — never a
  rewording of interactive protocol content.
- **C-2 CI gates not surfaced by local pytest:** `check-spec-purity.py` caps
  skill bodies at 300 lines (forge-5-loop is at the cap); `ruff check
  scripts/ eval/` is CI-only (run locally before pushing helper changes);
  `jsonschema` is absent in CI — new helper code paths must not hard-depend on
  it.
- **C-3 Adapter build:** reference files are discovered via citation-driven
  fan-out; skill bodies are host-term translated but skill-own references are
  copied verbatim. New/moved files must be citation-discoverable and
  host-neutral. Gemini fixture refresh uses the minimal-canon scratch-build +
  `command cp -f` procedure, not a copy of the real adapter.
- **C-4 Preferred mechanisms (preference, not mandate):** R4 → a
  `forge-session.py` state patch/write helper (annotated-example fallback);
  R5 → a `forge-session.py effective-config` subcommand. The PRD requires the
  outcomes (§3.4/§3.5); the tech spec finalizes the mechanism.
- **C-5 Prelude dedup is within-file only** (C-1/Guardrail §5) — no cross-file
  prelude pointer in any executable path.
- **C-6 Measure first.** Numeric targets are set against re-measured baselines
  at implementation time, not the audit snapshot.
- **C-7 Releases are batched manually.** The backlog MUST NOT contain release
  items; standard batch-release mechanics (version-sync fields, independent
  installer line, npm@11 provenance pin) are handled outside the pipeline.

## 6. Out of Scope

Explicitly NOT part of this feature (V1):

- **R7 — restructuring `shared-conventions.md`** into a thin core plus
  per-block files. It is the highest-payoff but only structurally-risky item
  and carries a mandatory prototype gate; it is deferred to its own follow-up
  feature.
- **W1 — trimming Epic Context Injection dep-spec loading.** A deliberate
  product decision (REQ-CTX-01 bounds it to direct deps); would change
  behavior. Revisit only with transcript evidence.
- **W2 — consolidating the duplicated epic-backflow paragraph** in forge-1-prd
  / forge-2-tech. Roughly token-neutral; leave unless a body hits the 300-line
  cap.
- Any change to **interactive behavior** — AskUserQuestion protocols, Decision
  Support, guards, verify gates, stage-exit routing. Content may move; it must
  not change.
- **Frontmatter descriptions** (already minimal, ~1.2k tokens for all 13
  skills — the only always-loaded surface).
- The **`SessionStart` hook** (already silent on the common path).
- **Non-Claude adapter behavior changes** beyond mechanical regeneration.
- **Release work items** (see C-7).

## 7. Open Questions

- OQ-1: What is the actual per-stage read frequency of
  `pipeline-state-schema.json` in real transcripts (informs the *reported* R4
  savings, per REQ-OBS-02)? Resolve at implementation time from
  consumption-data-refresh dogfood evidence.
- OQ-2: For R4, does the re-measured evidence favor the script-helper or the
  annotated-example fallback on cost/robustness grounds? Decided in the tech
  spec against re-measured baselines.
- OQ-3: What are the re-measured baseline token counts per invocation at
  implementation time (the audit's LOAD-MAP figures will have drifted since
  b9f0871)?

## 8. Success Criteria

The feature is done and working correctly when:

- **SC-1 (per-recommendation reduction):** Each shipped recommendation
  (R1–R6) demonstrates a measured net instruction-token reduction on its
  targeted invocation versus a freshly re-measured baseline. The LOAD-MAP
  projections are non-binding goals; the binding bar is "measured net
  reduction, correctly attributed."
- **SC-2 (directional aggregate):** The full-feature instruction-token load
  trends toward the audit's ~30–35%-per-feature reduction goal. This is a
  directional goal, **not** a pass/fail gate.
- **SC-3 (zero behavioral diff):** A full dogfooded feature run (all stages +
  verify + loop + docs) exhibits the same prompts, gates, guards, and outputs
  as before (REQ-BEHAV-01/02).
- **SC-4 (tests green + drift coverage):** All existing tests pass, and new
  drift-guard coverage exists for every split/moved file (REQ-MAINT-01).
- **SC-5 (clean portability):** All five adapters regenerate cleanly, fixtures
  are refreshed, and non-Claude hosts resolve every moved/split reference file
  (REQ-PORT-01/02/03).
- **SC-6 (independently revertible):** Each of R1–R6 landed as its own
  revertible unit, so a regression in one does not force reverting the others
  (REQ-DELIV-01).
