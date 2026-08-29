---
# GENERATED — DO NOT EDIT. Source: skills/forge-verify/SKILL.md. Regenerate: python3 scripts/build-adapters.py
name: forge-verify
description: Verify forge pipeline artifacts for completeness, consistency, and quality. Use when user runs /skill:forge-verify or asks to check forge specs, backlog, or implementation for gaps. Do NOT trigger for general code review, quality checks, or verification tasks outside the forge pipeline.
---

# forge-verify — Verification Gate

Analyze feature artifacts for completeness, consistency, and quality. Produce structured, actionable findings designed for a fresh-context agent to apply.

## Which role are you? (read this first)

This skill is loaded in two different roles. Determine yours before proceeding:

- **You ARE the `forge-verifier` subagent** — you were dispatched via the host's subagent mechanism, you have read-only tools (Read, Glob, Grep, Bash) and **no** Agent/host's subagent mechanism, and this skill is pre-loaded in your context. **SKIP "Subagent Delegation (parent orchestrator only)" and "Synthesize" below — those describe how a *parent* dispatches *you*, not work for you to do.** Do **not** dispatch anything, do **not** try to spawn a verifier. Go straight to **Prerequisites → Steps 1–6**, execute the checks yourself, and **return your findings as your response** (the parent writes the document to disk). Dispatching a subagent from here is the classic self-referential loop — never do it.
- **You are the parent orchestrator** — a navigator (`/skill:forge`), a stage skill's in-stage auto-verify, or a direct `/skill:forge-verify` invocation, and you have the host's subagent mechanism. Use "Subagent Delegation" to dispatch the `forge-verifier` subagent, then "Synthesize" to assemble and write the document.

## Subagent Delegation (parent orchestrator only)

This skill is delegated to the `forge-verifier` subagent via the host's subagent mechanism. The verifier subagent has:
- **Read-only tools** (Read, Glob, Grep, Bash) — it cannot accidentally modify specs
- **Persistent memory** — it accumulates knowledge about this project's recurring issues and patterns across sessions
- **The forge-verify skill pre-loaded** — so it has all verification checklists and guidance at startup

### Choose single vs. parallel dispatch

Pick based on how many checks the mode carries (see the per-mode totals in Step 3):

- **Small modes (prd 15, tech 17): single verifier.** Use the host's subagent mechanism once with
  `the forge-verifier custom agent`, passing the feature name and mode. It runs all
  checks and returns findings.
- **Large modes (specs 39, backlog 29, impl 25): parallel dimensioned fan-out.**
  Split the mode's checklist into **dimension groups** and dispatch **one
  `forge-verifier` per group, in parallel — a single message with multiple subagent
  calls** (the `superpowers:dispatching-parallel-agents` pattern). Each instance owns a
  disjoint slice of CHECK-IDs, so it verifies deeper over a narrower scope and they all
  run concurrently. Suggested groups (map to the category clusters in that mode's own
  checklist file):
  - **specs** (`references/verification-checklists/specs.md`): (1) types/contracts,
    (2) architecture/layout, (3) cross-reference & traceability (owns CHECK-S39),
    (4) testing strategy, (5) integration.
  - **backlog** (`references/verification-checklists/backlog.md`): (1) item scoping &
    acceptance criteria, (2) dependency/ordering sanity,
    (3) spec coverage & traceability (owns CHECK-B29), (4) schema/enum correctness.
  - **impl** (`references/verification-checklists/impl.md`): (1) requirement coverage vs specs (owns CHECK-I24/I25),
    (2) integration correctness, (3) testing, (4) code-quality/conventions,
    (5) runnability (owns CHECK-I21/I22 — the smoke command and the non-test-caller heuristic).

  In each parallel instance's prompt, pass: the feature, the mode, the **dimension
  label**, the **exact CHECK-IDs it owns**, and a note that **it is one of several
  parallel instances** — it must verify ONLY its assigned checks and return findings
  for that slice. Tell parallel instances to treat their `MEMORY.md` as **read-only**
  (apply learned patterns, but do NOT write it — concurrent writers would race);
  memory consolidation is left to single-verifier runs.

### Synthesize (parent session)

The verifier(s) are read-only — they return findings as their response. **Gate every return first** through "Truncated Verifier Returns" in `references/findings-template.md`: a return without the report structure is a dropped digest (issue #183) — resume the agent via `SendMessage` (or re-dispatch), and never synthesize, write a document, or record a verify result from a truncated return. Then **you** (the parent) assemble and write the single document to
`{resolvedFeatureDir}/.verification/VERIFY-{mode}-{YYYY-MM-DD}.md`. When you fanned out:
1. Concatenate all instances' findings and **renumber `V-NNN` IDs uniquely** across the
   merged set.
2. **Dedup** overlaps — when two instances flag the same file+location+issue (e.g. a
   cross-reference and a type-contract verifier both catch one mismatch), keep one,
   union their `Checklist:` IDs.
3. Build the **single Fix Execution Plan** over the merged findings (Step 5). The output
   document format is unchanged, so `forge-fix` consumes it identically.

### Adversarial confirmation (opt-in "deep verify")

When the user asks for a deep/thorough verify, add a confirmation pass before writing:
for each `error`- and `gap`-severity finding, dispatch a short skeptic `forge-verifier`
prompted to **refute** it ("here is a claimed finding; prove it wrong; default to
REFUTED if you cannot confirm it from the artifacts"). Drop findings the skeptic refutes
with confidence — this cuts false positives before they reach the user. Lower-severity
findings (`improvement`, `inconsistency`) skip this pass.

### Fallback

If the `forge-verifier` subagent is not available (not installed, or an environment
without subagents), fall back to running verification inline in the current session.

**Inline execution guidance:** If running inline (not as subagent), process verification checklists one category at a time to manage context pressure. Load only the artifacts needed for each category, verify, summarize findings, then move to the next category.

### Require-clean (`auto`) mode — unattended auto-verify

When the navigator auto-invokes this skill (its `autoVerify` path), it passes a
**require-clean** signal (e.g. args include `--require-clean`, or the invocation is
described as auto-verify). In this mode the clean-room guarantee is load-bearing: the
whole reason auto-verify is safe to run without a `/new` is that the `forge-verifier`
subagent inherits none of the dispatching session's context. Running inline would break
that — it would consume the dispatching session's context and invalidate the no-clear
justification.

So in require-clean mode, **do NOT fall back to inline execution**. If the host's subagent mechanism
or `forge-verifier` subagent is not dispatchable, return a **sentinel** instead of doing
any work:

> `CLEAN_ROOM_UNAVAILABLE: forge-verifier subagent not dispatchable — verify not run.`

Do not analyze artifacts, do not write a findings document, and do not touch pipeline
state. This is an **operational failure, not a user skip** — close through Step 7 with `--outcome failed`; as a nested owner that call writes no state and prints no terminal block, so the sentinel is your structured result. The navigator detects this sentinel and degrades to its manual verify gate (Tier
2/3), so verify state stays outstanding and the stage is never marked verified on false
assurance. **Manual / interactive invocation** (the normal `/skill:forge-verify`
path, no require-clean signal) keeps the inline fallback above unchanged.

## Prerequisites

Read and follow `references/shared-conventions.md` for feature name validation, configuration reading, and force mode handling before proceeding.

Resolve the feature directory via the **Feature Directory Resolution** block in `references/shared-conventions.md` (so a standalone feature resolves to its flat `{specsDir}/{feature}/` path exactly as today, and an epic member resolves to its nested `{specsDir}/{epic}/{feature}/` path). Use the resulting `{resolvedFeatureDir}` everywhere this skill reads or writes a per-feature artifact or state file — the `{specsDir}/{feature}/…` forms below are shorthand for the resolved path, not a literal flat layout. This does not apply to **epic mode**, whose paths are epic-scoped (`{specsDir}/{epic}/…`) by design.

Determine branch ownership **at entry**, from the literal `owner: nested` / `owner: direct` token in the dispatching prompt (absent the token you are `direct`), and preserve that value unchanged through any re-verify — see Step 7, which passes it through as `--owner`.

**Turn structure reminder:** Output analysis/context as text, then route ALL questions through `AskUserQuestion`. Never embed questions in text output — the user will not be prompted and the session will stall.

## Step 1: Read Configuration and Determine Mode

Read `{resolvedFeatureDir}/.pipeline-state.json` to understand current pipeline state.

### Mode Selection

An explicit `--served-stage <production-stage>` argument on this invocation is authoritative — it is what the scripted exit and forge-fix pass when they route back here (the fix rejoin fences `/skill:forge-verify {feature} --served-stage {stage}`). Map it to the mode directly (`forge-0-epic`→epic, `forge-1-prd`→prd, `forge-2-tech`→tech, `forge-3-specs`→specs, `forge-4-backlog`→backlog, `forge-5-loop`→impl) and skip auto-detection.

Otherwise, if a stage is specified as a second argument (e.g., `/skill:forge-verify auth specs`), use that mode. Otherwise, auto-detect based on pipeline state:

- **epic mode**: Explicit via `/skill:forge-verify {epic} epic`, or auto-detected when the named argument resolves to an **epic directory** — i.e. `{specsDir}/{name}/epic-manifest.json` exists (an epic root holds `epic-manifest.json` but no `.pipeline-state.json` of its own). When the argument is an epic, prefer epic mode over feature-mode resolution.
- **prd mode**: If `forge-1-prd` is complete but `forge-verify-prd` is not `passed` or `findings-applied`
- **tech mode**: If `forge-2-tech` is complete but `forge-verify-tech` is not `passed` or `findings-applied`
- **specs mode**: If `forge-3-specs` is complete but `forge-verify-specs` is not `passed` or `findings-applied`
- **backlog mode**: If `forge-4-backlog` is complete but `forge-verify-backlog` is not `passed` or `findings-applied`
- **impl mode**: If user explicitly requests or if implementation code exists for this feature

If ambiguous, use `AskUserQuestion` to ask which stage to verify — **before any write**. Serialize the resolved mode as `--verify-mode` at Step 7: that mode, never conversational context and never `currentStage`, determines the served production stage.

## Step 2: Load All Relevant Artifacts

Load into context ALL artifacts for this feature based on mode:

**For prd mode:**
- `{resolvedFeatureDir}/PRD.md`

**For tech mode:**
- `{resolvedFeatureDir}/PRD.md`
- `{resolvedFeatureDir}/tech-spec.md`

**For specs mode:**
- `{resolvedFeatureDir}/PRD.md`
- `{resolvedFeatureDir}/tech-spec.md`
- `{resolvedFeatureDir}/##-*.md` (all implementation specs)

**For backlog mode:**
- All of the above, PLUS
- `{resolvedFeatureDir}/backlog.json` (or `{backlogDir}/{feature}/backlog.json` if `backlogDir` is configured) — resolve `{resolvedFeatureDir}` via the **Feature Directory Resolution** block in `references/shared-conventions.md`, using the same composed path as forge-4-backlog and forge-5-loop (04 §6.2)

**For impl mode:**
- All of the above, PLUS
- The actual source code for this feature (read package directory)
- Source code of packages this feature integrates with

**For epic mode:**
- `{specsDir}/{epic}/epic-manifest.json`
- `{specsDir}/{epic}/EPIC.md`
- each member feature's `.pipeline-state.json` (for the `epic` back-pointer + derived status)
- each **completed** member's `PRD.md` + `tech-spec.md` (for contract-drift checking, CHECK-E06)

## Step 3: Run Verification Checklists

Read `references/verification-checklists/{mode}.md` for the detailed checklist for the mode being verified — one of `references/verification-checklists/prd.md`, `references/verification-checklists/tech.md`, `references/verification-checklists/specs.md`, `references/verification-checklists/backlog.md`, `references/verification-checklists/impl.md`, `references/verification-checklists/epic.md`. Read only that mode's file. Execute every check. Do not skip checks because things "look fine." **Exception — a re-verify is scoped, not a fresh sweep:** when the served stage's verify entry is `findings-applied`, follow "Re-verify scope and convergence" in `references/stage-exit-protocol.md` — confirm the prior report's findings against their acceptance evidence and examine the fix's own delta; only an unresolved prior finding or a new blocking defect the fix itself introduced may block, every other observation is advisory, and a finding with a recorded decision is never re-filed. The orchestrator-only **Findings Document Template (Step 4)**, worked **Example Findings (Step 4)**, and **Epic Mode State Write Detail (Step 6)** sections live in `references/findings-template.md`, read later by the parent role at Steps 4/6.

Each check in that mode checklist has a unique ID (CHECK-P01, CHECK-T01, CHECK-S01, CHECK-B01, etc.). As you execute each check, record its ID and result (pass/fail/not-applicable). After completing all checks, report the total: "Executed N of M checks. Results: X pass, Y fail, Z not-applicable." If your count is significantly below the expected total for the mode (prd: 15 checks, tech: 17 checks, specs: 39 checks, backlog: 29 checks, impl: 25 checks, epic: 10 checks), you likely skipped checks — go back and complete them.

**Epic mode dispatch.** Epic mode is a small (10-check) checklist, so per the single-vs-parallel rule above, dispatch a **single `forge-verifier`** via the host's subagent mechanism, passing the epic name and `mode=epic`. The verifier runs CHECK-E01..E10 from the `## Epic Mode Checklist` in `references/verification-checklists/epic.md` (E01/E02/E03/E08 are delegated to `epic-manifest.py validate`/`check-name`; E04–E07, E09, and E10 are verifier judgment) and returns its findings.

### Important: Be Specific, Not General

BAD finding: "The error handling could be more thorough."
GOOD finding: "PRD.md REQ-ERR-04 requires rate limit retry behavior, but spec 03-provider-registry.md only handles rate limits by throwing — no retry logic is specified."

Every finding must include:
1. A unique ID (V-001, V-002, etc.)
2. Severity: `gap` (missing requirement coverage), `inconsistency` (contradictory specs), `improvement` (not wrong but could be better), `error` (factually incorrect **with a behavioral, CLI-output, or decision-bearing consequence**)

   **Severity floor (anti-churn).** An inaccuracy confined to comments, docstrings, or test narration — prose no runtime path executes and no decision consumes — caps at `inconsistency`, never `error`. It is worth recording, but a wrong sentence beside correct code does not block a stage the way wrong behavior does. **Routing consequence:** `error` and `gap` are the two **blocking** severities; `inconsistency` and `improvement` are **advisory**. A report with at least one blocking finding records `findings-reported` and routes to forge-fix. A report whose findings are all advisory records `passed` **with the report still attached** (Step 6) and the pipeline advances — an advisory-only report never fences a fix round. A **meta-guard** (a test protecting other tests or prose) is judged against its declared protection set: guard-incompleteness against a declared non-goal is never a finding (`references/stage-exit-protocol.md` § Re-verify scope).

   **A checklist item with no PRD position behind it is a PRD gap, not a design to invent.** Several checks are deliberately conditional — `CHECK-S27` ("Concurrent access scenarios are addressed **if relevant**") is the clearest, and the same shape appears for performance, observability, and security checks that defer to the PRD. When such a check fires and the PRD takes **no position** on the concern, the finding is that the *requirements* are silent. Report it as an `improvement` (or a `gap` against the PRD, in `prd` mode) whose suggested fix is to **record the position** — including "out of scope, single writer assumed", which is a complete answer. Do **not** specify a mechanism to satisfy the check: a verifier that answers an open requirements question by designing a protocol converts a one-sentence PRD amendment into a foundational change that no requirement asked for, at the stage where it is least visible. Precedent both ways: `epic-orchestration` V-008 raised `CHECK-S27` against a PRD that *had* scoped concurrency out and correctly cost one sentence at `improvement`; `stage-exit-coverage` V-006 raised the same check against a silent PRD, was filed as a `gap`, and induced a full locking protocol that was later removed. For **forge state writes** specifically, the standing owner decision is recorded in `references/decisions/single-writer-threat-model.md` (issue #180): single writer assumed, detection-not-locking — answer `CHECK-S27` by citing it (or the per-feature requirement restating it), never by designing a mechanism.

   Relatedly, **do not let `improvement` fall out of use.** A report containing only `gap`/`error`/`inconsistency` usually means observations that should have been `improvement` were promoted into must-fix findings. If a finding would not block implementation, it is an `improvement` — say so.
3. Exact location (file + section)
4. What's wrong
5. Suggested fix (specific enough that a fresh agent can apply it)
6. References (which other files/sections are involved)
7. Related checklist item(s) (e.g., CHECK-P01, CHECK-S12)

## Step 4: Write Findings Document

Ensure the `.verification/` subdirectory exists, then write findings to `{resolvedFeatureDir}/.verification/VERIFY-{mode}-{YYYY-MM-DD}.md`. **Never overwrite an existing report:** if that name already exists (an earlier round the same day), write `VERIFY-{mode}-{YYYY-MM-DD}-round{N}.md` with the smallest `N ≥ 2` not yet on disk — each round's report and Fix Progress is an audit record later rounds and the round ledger (`references/stage-exit-protocol.md` § Escalation) read.

**For epic mode**, the target is `{specsDir}/{epic}/.verification/VERIFY-epic-{YYYY-MM-DD}.md` (the same format and the same no-overwrite round rule, with `{mode}=epic`).

The full findings-document template (report header, `V-NNN` finding shape, and the
Fix Execution Plan layout) and the worked **Example Findings** (gap / inconsistency /
improvement) live in `references/findings-template.md` under the **Findings
Document Template (Step 4)** and **Example Findings (Step 4)** sections — follow that
template verbatim when writing the document.

## Step 5: Fix Plan and Next Steps

The Fix Execution Plan (written as part of the findings document in Step 4) is ALWAYS generated regardless of mode. This ensures the findings document is self-contained: diagnosis + action plan in one artifact.

When building the Fix Execution Plan:
1. Group related findings into logical steps (e.g., all type-system fixes together)
2. Order steps to avoid conflicts (fix shared types before documents that reference them)
3. Each step must be specific enough for a fresh agent with zero prior context to execute
4. Flag any findings that require user decisions before fixes can be applied

**If in plan mode:** Also write the Fix Execution Plan to the active plan file so the plan mode workflow is preserved. The user reviews the plan, exits plan mode, and a fresh agent executes the fixes.

**If not in plan mode:** Output the following as text:
"Findings and fix plan written to `{findings-file}`."

**Advisory-only reports skip the question.** When the report contains no blocking finding (`error`/`gap`), there is nothing to route to forge-fix: do not present the fix options below — state that the report is advisory-only, record `passed` with the report attached (Step 6), and continue; the advisories stay discoverable in the findings document for whoever next touches the artifact. Otherwise (at least one blocking finding), use `AskUserQuestion` to ask how to proceed — **unless this report closes the SECOND consecutive `reverify-findings` for this served stage** (count the round-discriminated reports in `.verification/`), in which case follow "Escalation (the round ledger)" in `references/stage-exit-protocol.md` instead: present the digest and recommend explicit acceptance of the residual findings, never another fix pass. Otherwise follow the **Decision Support** protocol in `references/shared-conventions.md`: recommend a path based on the findings and give each option a one-line trade-off. Let the severity and volume of findings drive the recommendation — e.g. recommend (b) **Apply fixes now** when findings are clear-cut and mechanical; recommend (a) **Review first** when findings involve design judgment or you flagged low-confidence items; recommend (c) **plan-mode workflow** when the fixes are large or interdependent enough to warrant a reviewed plan. Present:
- **(a) Review the findings first** — read `{findings-file}` and decide per-finding; safest, but you act on nothing until you return.
- **(b) Run `/skill:forge-fix {feature} --served-stage {servedStage}` now** — applies the fix plan immediately; fastest, best when findings are unambiguous.
- **(c) Enter plan mode and re-run `/skill:forge-verify {feature}`** — produces a reviewable plan before any edits; best for large or risky fix sets.

Do NOT embed this question in your text output.

## Step 6: Record the Result Through `state-verify`

Never hand-author a verify entry. Every `stages.forge-verify-*` transition is written by the `state-verify` verb described in the **Pipeline State Protocol** in `references/shared-conventions.md`, which owns its full flag surface, its status matrix, and the exit-2 failure protocol. Pick the command variant below by outcome. Write `findings-reported` when the report lists at least one **blocking** finding (`error`/`gap`). Write `passed` when it lists none: a **clean** report (zero findings — every check ran and nothing surfaced) attaches with `--findings-count 0`, and an **advisory-only** report (`inconsistency`/`improvement` findings only) attaches with `--findings-count` ≥ 1; either way pass `--findings-file` alongside `--status passed` so the report — Step 4 always writes one — stays attached and discoverable without blocking the stage. Attaching the clean report is what lets a **fix pass's re-verify converge**: it records `passed` and the stage advances, instead of stranding at `findings-applied` and re-serving verification (a zero-finding report is valid audit evidence, not a contradiction). A bare `passed` with neither flag is still accepted for compatibility. (One exception routes blocking findings to `passed`: residual findings the user explicitly accepted at the round-ledger escalation — recorded first as a `state-decision`, then `passed` with the report attached, per "Escalation" in `references/stage-exit-protocol.md`.) Never write `findings-applied` here — that belongs to the fix pass. `--stage` names the **served production stage** (Step 1's mode, mapped through the served-stage mapping in Step 7), `--findings-file` is the report path **relative to** the feature directory (the Step 4 filename, round discriminator included), and `--verified-stage-version` is that production stage entry's current `version`, so a later revision of the artifact makes this verification read stale and re-fires. Add `--epic "{epic}"` when the feature is an epic member — required, per the Pipeline State Protocol; omitting it for a member is an error and must never fall back to a same-named flat feature.

```bash
R="$(bash -c 'for d in "${FEATURE_FORGE_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
# CLEAN (no findings): --status passed --findings-count 0. ADVISORY-only ({n}≥1, no error/gap):
# --status passed --findings-count {n}. BLOCKING ({n}≥1 error/gap): --status findings-reported --findings-count {n}.
python3 "$R/scripts/forge-session.py" state-verify \
  --feature "{feature}" --stage "{servedStage}" --status "{passed|findings-reported}" \
  --findings-file "{relative findings path}" --findings-count {n} \
  --verified-stage-version {version} --specs-dir "{specsDir}"
```

**Two-commit provenance — never `--amend`.** The write above records `commitHash: null`. Commit 1 records the findings document and the state together (Git Commit Protocol, `references/shared-conventions.md`). Then record the provenance of that commit in Commit 2, passing the **full 40-character** hash of Commit 1 — an abbreviation is refused rather than expanded, and this call touches nothing but `commitHash`. Add `--epic "{epic}"` when the feature is an epic member — required, per the Pipeline State Protocol.

```bash
R="$(bash -c 'for d in "${FEATURE_FORGE_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-session.py" state-verify \
  --feature "{feature}" --stage "{servedStage}" \
  --commit-hash "$(git rev-parse HEAD)" --specs-dir "{specsDir}"
```

On exit 2 **nothing was recorded**: surface the `Error:` line verbatim together with the named feature (and epic), do not claim the result was persisted, and close the stage with `--outcome failed` in Step 7 — the verify entry is unchanged, so no success block may be printed.

### Epic mode state (`.epic-state.json`)

Epic mode is **epic-scoped**, not per-feature: `--stage forge-0-epic` writes `{specsDir}/{epic}/.epic-state.json` and **never** any member's `.pipeline-state.json`. It is the one exception to the member rule — `--feature` names the **epic**, and `--epic` must be absent or exactly equal to it — and its `--verified-stage-version` is the epic manifest's `revision`, never a member's stage version. The exact call and the minimal written shape live in `references/findings-template.md` under the **Epic Mode State Write Detail (Step 6)** section. Follow it verbatim.

## Step 7: Close the Stage

**Ownership.** Read branch ownership from the literal `owner: nested` / `owner: direct` token in the prompt that dispatched you. **Absent the token you are `direct`** — a user-typed `/skill:forge-verify` is the only path that carries no dispatcher. Never infer ownership from how the invocation happened to be phrased; judge the token, not the wording. Pass the resolved value straight through as `--owner`, and preserve it through any re-verify. As a **nested** owner you return your structured result (mode, served stage, outcome, findings file, findings count) to the caller and print **no terminal block at all** — the outer authoring stage is the sole terminal owner. As a **direct** owner you print the script's NEXT-STEPS block verbatim as your absolute final output, with nothing after its sentinel line. `references/stage-exit-protocol.md` § "Branch ownership: the `owner:` token" owns this rule.

**Served stage.** Pass `--verify-mode` carrying Step 1's explicit or auto-detected mode (`epic`, `prd`, `tech`, `specs`, `backlog`, `impl`); the script maps it to the served production stage. When the caller already owns a stage and states it, additionally pass that value as `--served-stage` — if the two disagree the script fails closed rather than guessing. Derive the served stage **only** from that mode argument or from authoritative pipeline state: conversational context and `currentStage` are never valid inference sources.

**Capability.** Pass `--verify-capability interactive` only when **both** a question mechanism equivalent to `AskUserQuestion` is available **and** a clean-room `forge-verifier` may actually be dispatched right now. Clause (b) tests **permitted dispatch, not a listed tool**: a session that may dispatch only when the user asked, but does have a question mechanism, is `interactive` — the gate's affirmative choice supplies the request. Reserve `manual` for **no** question mechanism **and** **no** permitted dispatch. An auto-verify directive under a no-unsolicited-dispatch bar is presented through the gate and dispatched on the affirmative choice — never skipped, and never resolved by advancing to the production successor.

**Outcome.** Invoke the exit **exactly once**, with the `--outcome` this run's result maps to:

| This run's result | `--outcome` |
|---|---|
| Zero findings — the artifacts are clean | `passed` |
| Advisory-only report (no `error`/`gap`) — recorded `passed` with the report attached | `passed` |
| A report with at least one blocking finding (`error`/`gap`) was written | `findings` |
| The user explicitly chose to defer pipeline action **and** that skip was persisted via `state-verify --status skipped` | `skipped` |
| A dispatch, a check, or a state write failed and needs intervention | `failed` |

Merely **presenting** blocking findings is `findings`, not `skipped` — all three Step 5 options are `findings`, including (a) "review the findings first", which defers *your* next action rather than the pipeline's. `skipped` is available only for an explicit user deferral of **pipeline action** whose skip has already been persisted. A `CLEAN_ROOM_UNAVAILABLE` sentinel or a non-answer from an advertised dispatch is an operational failure, not a user skip: it is `failed`. A state-write failure is `failed`, and no success block may be printed after one.

Add `--epic "{epic}"` when the feature is an epic member, and `--served-stage "{servedStage}"` when the caller supplied one. Pass no other flags.

**Close this stage with the Scripted Stage Exit** (contract: `references/stage-exit-protocol.md`; do not improvise a "Next steps" list). Run:

```bash
R="$(bash -c 'for d in "${FEATURE_FORGE_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-session.py" stage-exit --feature "{feature}" --stage forge-verify --owner "{owner}" --outcome "{VerifyOutcome}" --verify-mode "{mode}" --specs-dir "{specsDir}" --host pi --verify-capability "{verify-capability}"
```

Obey the DIRECTIVES it prints, in the consumption order this protocol fixes: surface `invalidAutoVerifyKeys` and every `warnings` entry first; `runInStageVerify: true` → run the in-stage clean-room verify chain now (honoring `autoFixEligible`, and asking through the Standard Verify Gate first when you may not dispatch unsolicited); `verifyGate: "standard"` → present the Standard Verify Gate; `verifyGate: "manual-print"` → print the `verifyCommand` for the user and do **not** dispatch inline. Then, and only when `terminalOwnedBy` is `"self"`, **print the NEXT-STEPS block verbatim as your absolute last output — nothing after its sentinel line.** A `terminalOwnedBy: "outer"` payload carries `nextSteps: null`: return your structured result to the caller and print no terminal block at all.

## Gotchas

- This skill should be run in plan mode for best results. The plan gives the user a chance to review before committing to changes.
- Verification is most valuable when it finds things that are MISSING, not just things that are present but imperfect. Prioritize gap detection over style preferences.
- Don't verify things that are intentionally left open (check the PRD's "Open Questions" section).
- If you find zero issues, say so honestly. Don't manufacture findings to seem thorough. But zero findings on a complex feature is suspicious — double-check.
- The findings document must be self-contained. A fresh agent reading it should be able to apply every fix without needing conversational context from this session.
- For backlog verification, also run the loop runner's validate command (resolve `loopRunner` from `forge.config.json`, default rauf: `rauf backlog validate . --backlog {backlogDir} --specs-dir {resolvedFeatureDir} --json`). Include any findings it reports (exit 1) as verification findings; if the runner isn't installed yet (command missing), note that backlog validation was skipped rather than failing.
- For specs verification, also run the deterministic traceability validator to supplement agent-driven traceability checks. Include any uncovered requirements or orphaned references as findings:

```bash
R="$(bash -c 'for d in "${FEATURE_FORGE_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/validate-traceability.py" {resolvedFeatureDir}/PRD.md {resolvedFeatureDir}/ --json
```

---

## Host execution notes (Pi)

This Pi bundle preserves Claude's `AskUserQuestion` references because it ships a Pi compatibility extension registering an `AskUserQuestion` tool. On Pi:

- **User input:** use `AskUserQuestion` for genuine user decisions. It supports multiple questions, option descriptions, recommended ordering, multi-select, previews, and free-form Other/custom answers.
- **Skill dispatch:** Pi uses `/skill:<name>` commands. If you cannot invoke a skill directly, print the exact `/skill:<name> ...` command for the user to run.
- **Subagents:** this bundle declares its custom agents (`forge-researcher`, `forge-spec-writer`, `forge-verifier`) as package agents. If a `subagent` tool is registered, dispatch one with `{ agent: "forge-verifier", task: "..." }`, or fan several out concurrently with `{ tasks: [{ agent: "forge-spec-writer", task: "..." }, ...] }`. If no `subagent` tool is available, run that step inline yourself.
- **Background / monitoring:** run long-lived commands in the foreground and report progress as it arrives.
