---
# GENERATED — DO NOT EDIT. Source: skills/forge-verify/SKILL.md. Regenerate: python3 scripts/build-adapters.py
name: forge-verify
description: Verify forge pipeline artifacts for completeness, consistency, and quality. Use when user runs /feature-forge:forge-verify or asks to check forge specs, backlog, or implementation for gaps. Do NOT trigger for general code review, quality checks, or verification tasks outside the forge pipeline.
argument-hint: '<feature-name> [stage: prd|tech|specs|backlog|impl]'
---

# forge-verify — Verification Gate

Analyze feature artifacts for completeness, consistency, and quality. Produce structured, actionable findings designed for a fresh-context agent to apply.

## Subagent Delegation

This skill is delegated to the `forge-verifier` subagent via the Agent tool. The verifier subagent has:
- **Read-only tools** (Read, Glob, Grep, Bash) — it cannot accidentally modify specs
- **Persistent memory** — it accumulates knowledge about this project's recurring issues and patterns across sessions
- **The forge-verify skill pre-loaded** — so it has all verification checklists and guidance at startup

### Choose single vs. parallel dispatch

Pick based on how many checks the mode carries (see the per-mode totals in Step 3):

- **Small modes (prd ~15, tech ~15): single verifier.** Use the Agent tool once with
  `subagent_type="forge-verifier"`, passing the feature name and mode. It runs all
  checks and returns findings.
- **Large modes (specs ~38, backlog ~25, impl ~20): parallel dimensioned fan-out.**
  Split the mode's checklist into **dimension groups** and dispatch **one
  `forge-verifier` per group, in parallel — a single message with multiple Agent
  calls** (the `superpowers:dispatching-parallel-agents` pattern). Each instance owns a
  disjoint slice of CHECK-IDs, so it verifies deeper over a narrower scope and they all
  run concurrently. Suggested groups (map to the category clusters in
  `references/verification-checklists.md`):
  - **specs:** (1) types/contracts, (2) architecture/layout, (3) cross-reference &
    traceability, (4) testing strategy, (5) integration.
  - **backlog:** (1) item scoping & acceptance criteria, (2) dependency/ordering sanity,
    (3) spec coverage & traceability, (4) schema/enum correctness.
  - **impl:** (1) requirement coverage vs specs, (2) integration correctness,
    (3) testing, (4) code-quality/conventions.

  In each parallel instance's prompt, pass: the feature, the mode, the **dimension
  label**, the **exact CHECK-IDs it owns**, and a note that **it is one of several
  parallel instances** — it must verify ONLY its assigned checks and return findings
  for that slice. Tell parallel instances to treat their `MEMORY.md` as **read-only**
  (apply learned patterns, but do NOT write it — concurrent writers would race);
  memory consolidation is left to single-verifier runs.

### Synthesize (parent session)

The verifier(s) are read-only — they return findings as their response; **you** (the
parent) assemble and write the single document to
`{specsDir}/{feature}/.verification/VERIFY-{mode}-{YYYY-MM-DD}.md`. When you fanned out:
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

## Prerequisites

Read and follow `references/shared-conventions.md` for feature name validation, configuration reading, and force mode handling before proceeding.

**Turn structure reminder:** Output analysis/context as text, then route ALL questions through `AskUserQuestion`. Never embed questions in text output — the user will not be prompted and the session will stall.

## Step 1: Read Configuration and Determine Mode

Read `{specsDir}/{feature}/.pipeline-state.json` to understand current pipeline state.

### Mode Selection

If a stage is specified as a second argument (e.g., `/feature-forge:forge-verify auth specs`), use that mode. Otherwise, auto-detect based on pipeline state:

- **epic mode**: Explicit via `/feature-forge:forge-verify {epic} epic`, or auto-detected when the named argument resolves to an **epic directory** — i.e. `{specsDir}/{name}/epic-manifest.json` exists (an epic root holds `epic-manifest.json` but no `.pipeline-state.json` of its own). When the argument is an epic, prefer epic mode over feature-mode resolution.
- **prd mode**: If `forge-1-prd` is complete but `forge-verify-prd` is not `passed` or `findings-applied`
- **tech mode**: If `forge-2-tech` is complete but `forge-verify-tech` is not `passed` or `findings-applied`
- **specs mode**: If `forge-3-specs` is complete but `forge-verify-specs` is not `passed` or `findings-applied`
- **backlog mode**: If `forge-4-backlog` is complete but `forge-verify-backlog` is not `passed` or `findings-applied`
- **impl mode**: If user explicitly requests or if implementation code exists for this feature

If ambiguous, use `AskUserQuestion` to ask which stage to verify.

## Step 2: Load All Relevant Artifacts

Load into context ALL artifacts for this feature based on mode:

**For prd mode:**
- `{specsDir}/{feature}/PRD.md`

**For tech mode:**
- `{specsDir}/{feature}/PRD.md`
- `{specsDir}/{feature}/tech-spec.md`

**For specs mode:**
- `{specsDir}/{feature}/PRD.md`
- `{specsDir}/{feature}/tech-spec.md`
- `{specsDir}/{feature}/##-*.md` (all implementation specs)

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

Read `references/verification-checklists.md` for the detailed checklists per mode. Execute every check. Do not skip checks because things "look fine." That same reference also holds the relocated **Findings Document Template (Step 4)**, the worked **Example Findings (Step 4)**, and the **Epic Mode State Write Detail (Step 6)** sections used later in this skill.

Each check in `verification-checklists.md` has a unique ID (CHECK-P01, CHECK-T01, CHECK-S01, CHECK-B01, etc.). As you execute each check, record its ID and result (pass/fail/not-applicable). After completing all checks, report the total: "Executed N of M checks. Results: X pass, Y fail, Z not-applicable." If your count is significantly below the expected total for the mode (prd: ~15 checks, tech: ~15 checks, specs: ~38 checks, backlog: ~25 checks, impl: ~20 checks, epic: ~8 checks), you likely skipped checks — go back and complete them.

**Epic mode dispatch.** Epic mode is a small (~8-check) checklist, so per the single-vs-parallel rule above, dispatch a **single `forge-verifier`** via the Agent tool, passing the epic name and `mode=epic`. The verifier runs CHECK-E01..E08 from the `## Epic Mode Checklist` in `references/verification-checklists.md` (E01/E02/E03/E08 are delegated to `epic-manifest.py validate`/`check-name`; E04–E07 are verifier judgment) and returns its findings.

### Important: Be Specific, Not General

BAD finding: "The error handling could be more thorough."
GOOD finding: "PRD.md REQ-ERR-04 requires rate limit retry behavior, but spec 03-provider-registry.md only handles rate limits by throwing — no retry logic is specified."

Every finding must include:
1. A unique ID (V-001, V-002, etc.)
2. Severity: `gap` (missing requirement coverage), `inconsistency` (contradictory specs), `improvement` (not wrong but could be better), `error` (factually incorrect)
3. Exact location (file + section)
4. What's wrong
5. Suggested fix (specific enough that a fresh agent can apply it)
6. References (which other files/sections are involved)
7. Related checklist item(s) (e.g., CHECK-P01, CHECK-S12)

## Step 4: Write Findings Document

Ensure the `.verification/` subdirectory exists, then write findings to `{specsDir}/{feature}/.verification/VERIFY-{mode}-{YYYY-MM-DD}.md`.

**For epic mode**, the target is `{specsDir}/{epic}/.verification/VERIFY-epic-{YYYY-MM-DD}.md` (the same format, with `{mode}=epic`).

The full findings-document template (report header, `V-NNN` finding shape, and the
Fix Execution Plan layout) and the worked **Example Findings** (gap / inconsistency /
improvement) live in `references/verification-checklists.md` under the **Findings
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

Then use `AskUserQuestion` to ask: "Would you like to: (a) Review the findings first, (b) Run `/feature-forge:forge-fix {feature}` to apply fixes now, or (c) Enter plan mode and re-run `/feature-forge:forge-verify {feature}` for plan-mode workflow?" Do NOT embed this question in your text output.

## Step 6: Update Pipeline State

Write pipeline state conforming to `references/pipeline-state-schema.json`.

Update `{specsDir}/{feature}/.pipeline-state.json`:
- Set the relevant verify entry status to `findings-reported`
- Record `findingsFile`, `findingsCount`, `verifiedAt`

Do NOT mark as `findings-applied` — that happens after the fix pass.

### Epic mode state (`.epic-state.json`)

Epic mode is **epic-scoped**, not per-feature: record its result into the epic-level
state file `{specsDir}/{epic}/.epic-state.json` — **never** into any member's
`.pipeline-state.json`. Set `stages.forge-verify-epic.status` to `findings-reported`
(or `passed` if zero findings), recording `findingsFile`, `findingsCount`, and
`verifiedAt`. The full `.epic-state.json` schema (minimal shape) and the atomic
temp-file + `os.replace()` **write-mechanism** detail (lazy-create, merge/replace,
fail-intact) — including the worked Python snippet — live in
`references/verification-checklists.md` under the **Epic Mode State Write Detail
(Step 6)** section. Follow it verbatim.

Do NOT mark as `findings-applied` — that happens after the fix pass.

## Gotchas

- This skill should be run in plan mode for best results. The plan gives the user a chance to review before committing to changes.
- Verification is most valuable when it finds things that are MISSING, not just things that are present but imperfect. Prioritize gap detection over style preferences.
- Don't verify things that are intentionally left open (check the PRD's "Open Questions" section).
- If you find zero issues, say so honestly. Don't manufacture findings to seem thorough. But zero findings on a complex feature is suspicious — double-check.
- The findings document must be self-contained. A fresh agent reading it should be able to apply every fix without needing conversational context from this session.
- For backlog verification, also run the loop runner's validate command (resolve `loopRunner` from `forge.config.json`, default rauf: `rauf backlog validate . --backlog {backlogDir} --specs-dir {specsDir}/{feature} --json`). Include any findings it reports (exit 1) as verification findings; if the runner isn't installed yet (command missing), note that backlog validation was skipped rather than failing.
- For specs verification, also run the deterministic traceability validator to supplement agent-driven traceability checks. Include any uncovered requirements or orphaned references as findings:

```bash
R="$(for d in "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/*/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done)"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/validate-traceability.py" {specsDir}/{feature}/PRD.md {specsDir}/{feature}/ --json
```
