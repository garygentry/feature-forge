# Ranked Recommendations

> Ordered by payoff ÷ risk. R1–R3 are behavior-preserving and independently
> shippable. R4–R6 follow the proven script-extraction pattern. R7 is the only
> structurally risky change and carries a mandatory prototype gate. Each entry
> notes savings, mechanism, and the failure mode to guard against.

## R1 — Split `verification-checklists.md` per mode  · LOW RISK · HIGH PAYOFF

**Change:** `skills/forge-verify/references/verification-checklists.md` →
`checklists/prd.md`, `tech.md`, `specs.md`, `backlog.md`, `impl.md`,
`epic.md`, plus `findings-template.md` (the Findings Document Template,
Example Findings, and Epic Mode State Write Detail sections — these are
**orchestrator-facing** and should not ship to subagents at all).

**Why safe:** dispatch is already parameterized by mode; the subagent prompt
just names a different file. The per-mode "Executed N of M" self-check gets
*more* robust when the file contains only the relevant mode.

**Savings:** each verifier instance drops from ~6k to ~1–2k checklist tokens;
multiplied by parallel fan-out (3–5 instances on specs/backlog/impl modes).
Largest absolute win in the audit.

**Guard against:** (a) the forge-verify skill's mode-dispatch text and the
forge-verifier agent def cite the old path — update all citations so the
adapter build's citation-driven fan-out still discovers every file;
(b) expected-count table in the skill must match the split files; (c) add a
drift-guard test asserting each mode file's CHECK-ID count.

## R2 — Deduplicate the plugin-root prelude within files · LOW RISK

**Change:** in any file with multiple copies of the 3-line `R=` resolver
block (navigator ×5, forge-0-epic ×6, shared-conventions ×6, bootstrap ×4,
forge-1-prd ×2, forge-5-loop ×2), keep the **first** occurrence verbatim as
"the standard prelude", and make subsequent sites a one-liner:
`# (standard prelude from above)` + the `python3 "$R/…"` call. Some call
sites already use this compact form — make it the rule.

**Why safe:** within one file the definition is already in context when later
sites need it. **Do NOT dedupe across files** — the inline prelude is a
deliberate reliability fix (PR #101, `${CLAUDE_PLUGIN_ROOT:-}` first-hint) for
non-Claude hosts; a skill body must remain self-sufficient.

**Savings:** ~110 tok/copy × ~18 removable copies ≈ 2k tokens spread across
the hottest files (~1.2k in a single navigator run).

## R3 — Navigator: make the `process-overview.md` read conditional · TRIVIAL

**Change:** `skills/forge/SKILL.md` Step 1 currently says "For pipeline
architecture details, read `references/process-overview.md`" in the
unconditional setup section. Reword to: read **only if** the user asks how
the pipeline works / architecture questions. Dashboard rendering never needs
it. Saves ~1.7k tokens per navigator invocation.

## R4 — Stop reading `pipeline-state-schema.json` per stage · LOW-MED RISK

Cited by 8 skills ("Write pipeline state conforming to …"); 191 lines of
JSON-Schema whose actionable content (field names, enums, ISO-8601 format)
is far smaller.

**Preferred:** a `forge-session.py` `patch-state` (key-path patcher) /
`write-state` helper — continues the script-extraction pattern that already
worked for stage-exit, removes hand-authored-JSON drift, and makes the schema
a CI-validation artifact only. Touch points are scattered (entry stamp,
incremental `artifacts[]` updates, completion, `notes`, `deferredDecisions[]`,
`epicChangeRequests[]`) — inventory them all in tech spec.

**Cheaper interim:** replace the schema pointer with a compact annotated
example (~⅓ tokens); keep the schema as source of truth for validation.

**Evidence check first:** confirm from dogfood transcripts whether the model
actually opens the schema each stage or already skips it.

## R5 — `forge-session.py effective-config` subcommand · LOW RISK

forge-5-loop and forge-4-backlog read `forge-config-schema.json` (2,068 w)
solely to fill `loopRunner` defaults. A subcommand emitting the resolved,
default-filled `loopRunner` block (and optionally the whole effective config)
replaces a ~2.7k-token schema read with ~50 tokens of JSON in both skills.
Also removes a class of "model mis-merged defaults" bugs.

## R6 — Split `runner-contract.md` rare vs. always sections · LOW-MED RISK

The loop's deferrals are only nominal: launch/monitor/event sections are
needed on every run, but `## Agent selection` (89 lines — only fires when
`loopRunner.agentArgument` is configured) and the optional-flags catalog ride
along. Split into `runner-contract.md` (always) + `agent-selection.md`
(conditional, cited at the Step 2d capability gate). The forge-5-loop body is
at the 300-line cap, so this must not push text back into the body.

## R7 — Restructure `shared-conventions.md` · MODERATE RISK · HIGHEST PAYOFF

**The problem:** ~6k tokens loaded unconditionally by ~10 skills; no consumer
uses more than ~half its 13 blocks (per-consumer matrix in `LOAD-MAP.md`).

**Direction:** thin `conventions-core.md` (~1.5k tok: feature-name rule,
config keys, AskUserQuestion + Decision Support protocol) that keeps the
"read before proceeding" contract, plus `blocks/<name>.md` per named block
(dir-resolution, git-commit, branch-setup, branch-reconciliation,
stage-entry-guard, stage-completion-recheck, epic-context-injection,
epic-member-base-guard, specs-hygiene, force-mode). Skills read a block file
**at the invoke point** — the invoke sentences already exist and are specific
("invoke the **Stage-Entry Guard** block in …"), so this is a path change,
not a new instruction.

**The honest trade-off:** the monolith's reliability comes precisely from one
top-of-skill read guaranteeing every guard's full text is in context before
any can fire. Splitting means a missed mid-flow Read silently weakens a
guard. Mitigations, all required:
1. Keep each guard's **trigger condition** in the skill body / core; only the
   **procedure detail** moves to the block file.
2. Extend drift-guard tests: every invoke-point sentence must name an
   existing block file; every block file must be cited by ≥1 skill.
3. **Prototype gate:** convert ONE low-stakes consumer first (forge-verify or
   the navigator — fewest blocks used), dogfood a full feature run, diff
   behavior, and only then roll out to the authoring stages.
4. Adapter build: blocks must remain citation-discoverable for fan-out;
   regenerate adapters + fixtures.

**Savings:** ~2–4k tokens per stage session × 6–8 sessions per feature — the
largest per-feature total, which is why it's worth the care.

## Watch items (explicitly NOT recommended now)

- **W1 — Epic Context Injection dep-spec volume.** Loading each completed
  direct dep's full PRD + tech-spec is a deliberate product decision
  (REQ-CTX-01 bounds it to direct deps). A "Contracts-sections-only" variant
  would change functionality. Revisit only with transcript evidence that
  dep specs crowd out interview quality on wide epics.
- **W2 — Epic-backflow paragraph duplication** (forge-1-prd ~L102 /
  forge-2-tech ~L97, ~350 w each). Consolidation is token-neutral (trades
  body text for another reference read). Leave unless a body hits the
  300-line cap.

## Sequencing

1. **Measure baseline** from dogfood transcripts (consumption-data-refresh
   runs) — confirm which reads actually happen.
2. Ship R1 + R2 + R3 (quick wins, independently revertible).
3. Ship R5, then R4, then R6 (script-extraction family).
4. R7 prototype on one skill → dogfood → full rollout.
5. Re-measure; compare against the LOAD-MAP baselines.
