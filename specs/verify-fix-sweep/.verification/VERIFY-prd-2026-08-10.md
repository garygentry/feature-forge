# Verification Report: verify-fix-sweep (prd)
Date: 2026-08-10
Pipeline Stage: forge-1-prd (`forge-verify-prd`: `auto-verify-pending`, scheduledStageVersion 1)
Artifacts Reviewed: `specs/verify-fix-sweep/PRD.md` (v1, commit 960b9ab); corroborating repo sources: `skills/forge-1-prd/references/prd-template.md`, `skills/forge-verify/SKILL.md`, `skills/forge-fix/SKILL.md`, `references/stage-exit-protocol.md`, `references/decisions/single-writer-threat-model.md`, `skills/forge-verify/references/verification-checklists/*.md`, `scripts/check-spec-purity.py`, `scripts/validate.sh`, `AGENTS.md`, `specs/CLAUDE.md`, `adapters/gemini/references/stage-exit-protocol.md`
Checks Executed: 15 of 15 (9 pass, 6 fail, 0 not-applicable)

Per-check results: P01 fail, P02 pass, P03 pass, P04 pass, P05 fail, P06 pass, P07 pass, P08 pass, P09 pass, P10 pass, P11 pass, P12 fail, P13 fail, P14 fail, P15 fail.

## Summary
- Total findings: 8
- Gaps: 2
- Inconsistencies: 2
- Improvements: 4
- Errors: 0

Report contains blocking findings (2 gaps) → `findings-reported` / route to `forge-fix`.

## Findings

### V-001: Generated output is in the sweep corpus, but this repo's generated output is host-term *translated* — normalized matching cannot reach it
- **Severity:** gap
- **Location:** PRD.md, §3.1 REQ-SWEEP-02 and REQ-SWEEP-03; §8 bullet 1
- **Issue:** REQ-SWEEP-03 puts generated output explicitly in the corpus ("Generated output is explicitly in scope (F-5 reached `src/generated/*.ts`)"), and REQ-SWEEP-02 fixes milestone-1 recall at normalized (case/whitespace/punctuation) substring/near-match. In *this* repository — the one §8's milestone-acceptance criterion says the sweep must run on — the generated tree is `adapters/`, and the #167 host-term translation pass rewrites tokens inside the copied prose. Measured on `references/stage-exit-protocol.md` vs `adapters/gemini/references/stage-exit-protocol.md`: 9 of 517 lines differ, with substitutions including `` `/clear` `` → "clear your session / start a fresh session", `` `AskUserQuestion` `` → "the host's question mechanism", `${CLAUDE_PLUGIN_ROOT:-}` → `${FEATURE_FORGE_ROOT:-}`, and `--host claude` → `--host generic`. Consequence: if a fix corrects a canon sentence containing any translated token and the adapters are not regenerated, the *wrong* claim survives in five adapter mirrors in a form that differs from the removed canon text by more than case/whitespace/punctuation — so the sweep reports **nothing**, silently. That is precisely the F-5 shape (claim survives in a sibling artifact, reaches generated output, ships) recurring inside the sweep's own blind spot. The PRD's C-5 already acknowledges the translation pass exists, so the two requirements are in tension with a constraint the document itself records. The PRD takes no position on this; §8 bullet 1 tests only verbatim + whitespace-reflowed variants, so acceptance would pass with the hole open.
- **Suggested fix:** Record the position in a `Notes:` line on REQ-SWEEP-03 (and cross-reference from REQ-SWEEP-02). Two acceptable positions, either of which is complete — do not design a matching mechanism here: (a) **Accept the limit:** adapter/translated mirrors are swept, but term-substituted misses are a known milestone-1 recall limit deferred to #171; add a matching sentence to §6 Out of Scope. (b) **Treat mirrors as derived:** the sweep's corpus excludes regenerated trees (`adapters/`), relying on C-5's regenerate-and-commit discipline plus `scripts/validate.sh`'s existing adapter-drift gate ("FAIL: adapters/ is out of date") to propagate the correction; state that the drift gate, not the sweep, is the mirror's guarantee. Whichever is chosen, extend §8 bullet 1 with a third survivor variant that exercises the decision (a translated mirror that must, or must not, be reported).
- **References:** PRD.md §5 C-5; `references/stage-exit-protocol.md` lines 7, 21, 93, 95, 101, 119, 286, 295, 423 vs the same lines in `adapters/gemini/references/stage-exit-protocol.md`; `scripts/validate.sh` (adapter drift gate)
- **Checklist:** CHECK-P14, CHECK-P15

### V-002: PRD takes no security position, while the sweep is specified to echo removed text into a tracked audit document
- **Severity:** gap
- **Location:** PRD.md, §4 Non-Functional Requirements (no Security subsection; template's §4.2)
- **Issue:** `references/prd-template.md` §4 enumerates Performance / Security / Observability / Accessibility / Scalability. This PRD supplies §4.1 Performance, §4.2 Observability, §4.3 Concurrency and silently omits Security, Accessibility and Scalability — the repo convention (precedent: `verify-test-debt` §4.5) is an explicit "Not applicable" plus a reason, not omission. Security is not merely a template hole here: REQ-SWEEP-03 makes the corpus *all* git-tracked files, REQ-OBS-01 requires every survivor report to carry "the removed text it matched", and REQ-SWEEP-05 requires those results be written into the findings document — a **tracked, committed** artifact. So a fix pass whose delta removes sensitive text (a leaked credential, a token, a customer identifier) is specified to copy that text into a new tracked file and into agent output, and to enumerate every other file still holding it. CHECK-P12 requires security to be explicit, not assumed; the PRD is silent, so the tech spec would have to invent a position at the stage where it is least visible.
- **Suggested fix:** Add `### 4.4 Security` with one requirement recording the owner's position — "out of scope, the fix delta's removed text is already in git history and the findings document inherits the repository's existing trust boundary" is a complete answer if that is the position; if not, the minimal alternative is REQ-SEC-01 stating that survivor reports elide match text above a length/entropy bound, or that the sweep is not a secret-scrubbing tool and secret removal must not be routed through it. Also add `### 4.5 Accessibility` / `### 4.6 Scalability` (or renumber) with one-line "Not applicable — {reason}" entries so CHECK-P01 passes against the template.
- **References:** PRD.md §3.1 REQ-SWEEP-03, REQ-SWEEP-05, §4.2 REQ-OBS-01; `skills/forge-1-prd/references/prd-template.md` §4
- **Checklist:** CHECK-P12, CHECK-P01

### V-003: REQ-SWEEP-04's "blocks closure" contradicts REQ-SWEEP-06's outcome routing and the stage-exit invariant
- **Severity:** inconsistency
- **Location:** PRD.md, §3.1 REQ-SWEEP-04 vs REQ-SWEEP-06
- **Issue:** REQ-SWEEP-04 ends "An undispositioned survivor **blocks closure**." REQ-SWEEP-06 says the same condition "closes `decisions`" or "closes `failed`". Under `references/stage-exit-protocol.md` and forge-fix Step 7 ("Invoke the exit **exactly once** … Every path lands on exactly one row; none may be left open"), literally blocking closure is not a permitted state — the pass must close on some row. The intended meaning is evidently "blocks *advancing* closure", but as written a tech-spec author could specify a hang/abort path that violates the exit contract, and REQ-SWEEP-04 is a P0.
- **Suggested fix:** Reword REQ-SWEEP-04's last sentence to "An undispositioned survivor prevents the pass from closing on an advancing outcome — it routes through REQ-SWEEP-06's existing rows (`decisions` / `failed`); the pass always closes exactly once." Add a `Notes:` cross-reference to REQ-SWEEP-06.
- **References:** `skills/forge-fix/SKILL.md` Step 7 outcome table (`decisions`, `failed`, `deferred` rows); `references/stage-exit-protocol.md`
- **Checklist:** CHECK-P15

### V-004: C-4 states the forge-verify SKILL.md body is 299/300 lines; it is 298
- **Severity:** inconsistency
- **Location:** PRD.md, §5 constraint C-4
- **Issue:** C-4 asserts "the forge-verify SKILL.md body is at 299/300 lines and gains at most a pointer line." Measured with the gate's own algorithm (`scripts/check-spec-purity.py`: body = lines after the closing frontmatter fence, trailing split artifact dropped; `MAX_BODY_LINES = 300`), `skills/forge-verify/SKILL.md` body is **298** lines (file total 304, 6 frontmatter lines). The budget claim is off by one and understates headroom, so the derived rule ("at most a pointer line") is tighter than the real cap requires. C-4 also cites only the line cap while its own heading says "word/line budgets" — the same gate enforces `MAX_BODY_WORDS`, against which forge-verify sits at 4447 and forge-fix at 2941. `forge-fix` SKILL.md is 134 body lines, so C-4's second sentence is comfortably true.
- **Suggested fix:** In C-4, replace "at 299/300 lines and gains at most a pointer line" with "at 298/300 body lines (measured by `scripts/check-spec-purity.py`), so it can absorb a pointer line and the per-mode check-count edit"; optionally add "word budgets are not at risk (4447/5000)". Do not restate a number without re-measuring — this constraint is exactly the kind of literal that goes stale.
- **References:** `scripts/check-spec-purity.py` lines 89, 623–629; `skills/forge-verify/SKILL.md`; `skills/forge-fix/SKILL.md`
- **Checklist:** CHECK-P13

### V-005: Three requirements have no success criterion — including both P1 mechanisms most likely to be dropped
- **Severity:** improvement
- **Location:** PRD.md, §8 Success Criteria
- **Issue:** §8's five bullets cover the sweep (bullet 1 → REQ-SWEEP-01/02/03), the cardinality assertion (bullet 2 → REQ-CARD-01/03), closure/outcome routing (bullet 3 → REQ-SWEEP-04/06), the build gates, and milestone acceptance. Nothing in §8 exercises **REQ-CONS-01** (internal-consistency CHECK), **REQ-SWEEP-07** (visible "sweep not run — no git delta" notice), or **REQ-CARD-04** (graceful not-applicable). REQ-CONS-01 is the one requirement realized purely as checklist prose with no mechanical artifact, and REQ-SWEEP-07 is the silent-skip guard — both can be omitted from the implementation without any §8 bullet noticing. For a feature whose entire subject is "did the change reach every site?", an untested requirement set is a self-inflicted instance of the defect class.
- **Suggested fix:** Add three §8 bullets: (1) "The internal-consistency CHECK exists by ID in the checklist file(s) named by REQ-CONS-01 and its ID appears in the per-mode expected total"; (2) "A fix pass run outside a git repository records the `sweep not run — no git delta` notice in `## Fix Progress` and does not close silently"; (3) "An artifact set with no declared work list yields a not-applicable result, not a failure."
- **References:** PRD.md §3.1 REQ-SWEEP-07, §3.2 REQ-CARD-04, §3.3 REQ-CONS-01
- **Checklist:** CHECK-P05, CHECK-P08

### V-006: Success criterion cites "P5.3", a label that resolves nowhere in the tracked repository
- **Severity:** improvement
- **Location:** PRD.md, §8 last bullet ("**Milestone acceptance (P5.3):** …")
- **Issue:** "P5.3" appears exactly once in the entire tracked repository — in this PRD. It is a phase label from the local hardening tracker under `plans/`, which is **gitignored** (`.gitignore`: `plans/`). A fresh agent — the intended reader of a forge artifact — cannot resolve it. The durable anchors that do exist are issue #170 and `STATUS.md` line 154 ("**F** — verify fix-sweeps (pipeline feature) | #170 mechanical milestone, then #171 semantic").
- **Suggested fix:** Replace "(P5.3)" with a resolvable reference: "**Milestone acceptance (issue #170, STATUS.md Track F):**". The rest of the bullet is already self-describing and needs no change.
- **References:** `.gitignore` (`plans/`); `STATUS.md` lines 149, 154, 171
- **Checklist:** CHECK-P05, CHECK-P04

### V-007: REQ-CONS-01 names no verification mode, and adding CHECKs mutates a test-pinned count line
- **Severity:** improvement
- **Location:** PRD.md, §3.3 REQ-CONS-01 (and §5 C-4)
- **Issue:** Its siblings pin their surface — REQ-CARD-02 says "backlog-mode", REQ-CARD-03 says "impl-mode" — but REQ-CONS-01 says only "A verification CHECK". The scope difference is material: one checklist vs all six (`prd` 15, `tech` 17, `specs` 38, `backlog` 28, `impl` 23, `epic` 10 CHECK IDs today). Relatedly, C-4 reasons about forge-verify SKILL.md purely as a line budget, but any new CHECK also forces an edit to the per-mode expected totals sentence at `skills/forge-verify/SKILL.md:171` ("prd: 15 checks, tech: 17 checks, specs: 38 checks, backlog: 28 checks, impl: 23 checks, epic: 10 checks") — and that sentence is **pinned by tests**: `tests/test_dev_runtime_smoke.py:72` and `tests/test_smoke_command.py:82` both assert `"impl: 23 checks" in text`. So REQ-CARD-03 alone (impl 23→24) breaks two tests. §8's `validate.sh` bullet will catch this, so it is not a correctness gap — but recording it prevents a surprise mid-implementation and is exactly the "one new value, the rest derives" under-listing this feature exists to catch.
- **Suggested fix:** (a) Amend REQ-CONS-01 to name its target checklist(s) — e.g. "lands in the `specs` and `impl` checklists" — or state explicitly that mode selection is deferred to the tech spec, and add it to §7 Open Questions. (b) Extend C-4 with: "Each new CHECK also updates the per-mode expected totals in `skills/forge-verify/SKILL.md` and the two tests pinning them (`tests/test_dev_runtime_smoke.py`, `tests/test_smoke_command.py`)."
- **References:** `skills/forge-verify/SKILL.md:171`; `tests/test_dev_runtime_smoke.py:72`; `tests/test_smoke_command.py:82`; PRD.md §3.2 REQ-CARD-02/03
- **Checklist:** CHECK-P14

### V-008: The "audit record" exclusion rationale covers more corpora than `.verification/`
- **Severity:** improvement
- **Location:** PRD.md, §3.1 REQ-SWEEP-03 and its `Notes:`
- **Issue:** REQ-SWEEP-03 excludes `.verification/` because "Findings documents quote the corrected claim by design — they are audit records, not survivors." The same rationale holds for at least two other tracked corpora the sweep will hit on its first real run here: (1) prior features' artifacts under `specs/`, which `specs/CLAUDE.md` declares are "intentionally **not kept in sync**" and explicitly instructs agents not to flag for divergence; and (2) `CHANGELOG.md` / `STATUS.md` entries that narrate a superseded claim. REQ-SWEEP-04 mitigates this — "historical record" is one of its named justifications — so nothing is broken; the cost is disposition churn on every pass, against REQ-PERF-01's "without ceremony" intent.
- **Suggested fix:** Extend REQ-SWEEP-03's `Notes:` with: "Other tracked audit corpora (prior features' `specs/` artifacts, `CHANGELOG.md`, `STATUS.md`) are swept but their hits are expected to disposition as 'historical record' per REQ-SWEEP-04; whether to pre-exclude them by path is a tech-spec decision." Optionally add the corresponding line to §7 Open Questions.
- **References:** `specs/CLAUDE.md` ("Specs are not live contracts" / "Do not flag spec↔code divergence"); PRD.md §3.1 REQ-SWEEP-04, §4.1 REQ-PERF-01
- **Checklist:** CHECK-P14

## Fix Execution Plan

### User Decisions Required
1. **V-001 — translated generated mirrors.** ✅ RESOLVED 2026-08-10 (owner): **(b) exclude drift-gated regenerated trees** — regeneration + the `validate.sh` adapter-drift gate, not the sweep, is the mirror's guarantee; generated output *without* such a gate stays in scope.
2. **V-002 — security position.** ✅ RESOLVED 2026-08-10 (owner): **(a) out of scope, stated as REQ-SEC-01** — removed text is already in git history; the findings document inherits the repository's trust boundary; the sweep is not a secret-scrubbing tool (secret removal routes through history rewrite).
3. **V-007(a) — REQ-CONS-01 mode.** ✅ RESOLVED 2026-08-10 (owner): **specs + impl** checklists host the internal-consistency CHECK.

All other findings (V-003, V-004, V-005, V-006, V-007(b), V-008) can be applied directly with no decision.

### Execution Steps

#### Step 1: Add the missing §4 subsections and the security position
- **Files:** `specs/verify-fix-sweep/PRD.md`
- **Addresses:** V-002
- **Action:** After §4.3 Concurrency, add `### 4.4 Security` carrying the decision from User Decision 2 (as REQ-SEC-01 with a `Priority:` line if an affirmative requirement was chosen; as a one-line "Not applicable — {reason}" if position (a) was chosen). Add `### 4.5 Accessibility` and `### 4.6 Scalability`, each a single "Not applicable — {reason}" line, so §4 matches `skills/forge-1-prd/references/prd-template.md`.
- **Depends on:** User Decision 2

#### Step 2: Record the generated-mirror position on the sweep corpus
- **Files:** `specs/verify-fix-sweep/PRD.md`
- **Addresses:** V-001, V-008
- **Action:** Rewrite REQ-SWEEP-03's `Notes:` block to (a) state the chosen position from User Decision 1 on regenerated/host-term-translated trees, naming `adapters/` and citing C-5 and the `validate.sh` adapter-drift gate; and (b) append the historical-corpora sentence from V-008. Add a one-line cross-reference from REQ-SWEEP-02's `Notes:` to the recall boundary now recorded on REQ-SWEEP-03. If position (a) was chosen, add the matching "translated mirrors" bullet to §6 Out of Scope.
- **Depends on:** User Decision 1

#### Step 3: Reconcile the closure wording
- **Files:** `specs/verify-fix-sweep/PRD.md`
- **Addresses:** V-003
- **Action:** Replace REQ-SWEEP-04's final sentence "An undispositioned survivor blocks closure." with "An undispositioned survivor prevents the pass from closing on an advancing outcome — it routes through REQ-SWEEP-06's existing rows (`decisions` / `failed`); the pass always closes exactly once (`references/stage-exit-protocol.md`)."
- **Depends on:** none

#### Step 4: Correct C-4's budget figures and its edit surface
- **Files:** `specs/verify-fix-sweep/PRD.md`
- **Addresses:** V-004, V-007(b)
- **Action:** In §5 C-4, change "the forge-verify SKILL.md body is at 299/300 lines and gains at most a pointer line" to "the forge-verify SKILL.md body is at 298/300 body lines as measured by `scripts/check-spec-purity.py` (words 4447/5000), and gains a pointer line plus the per-mode check-count edit". Append the sentence: "Each new CHECK also updates the per-mode expected totals at `skills/forge-verify/SKILL.md:171` and the two tests pinning them (`tests/test_dev_runtime_smoke.py`, `tests/test_smoke_command.py`)." Re-measure both numbers before writing them; do not copy them from this report if the file has changed since 2026-08-10.
- **Depends on:** none

#### Step 5: Pin REQ-CONS-01's surface
- **Files:** `specs/verify-fix-sweep/PRD.md`
- **Addresses:** V-007(a)
- **Action:** Either amend REQ-CONS-01 to name the target checklist mode(s) in the same style as REQ-CARD-02/03, or add a §7 Open Questions bullet: "Which verification mode(s) host the internal-consistency CHECK of REQ-CONS-01 (tech spec) — one checklist or several; each adds a CHECK ID and a count-line edit."
- **Depends on:** User Decision 3

#### Step 6: Close the success-criteria gaps
- **Files:** `specs/verify-fix-sweep/PRD.md`
- **Addresses:** V-005, V-006, and the §8 half of V-001
- **Action:** In §8, (1) add the three bullets from V-005 covering REQ-CONS-01, REQ-SWEEP-07 and REQ-CARD-04; (2) extend bullet 1 with the translated-mirror variant implied by User Decision 1 (reported, or deliberately not reported); (3) replace "(P5.3)" in the last bullet with "(issue #170, STATUS.md Track F)".
- **Depends on:** Step 2 (bullet 1 must match the position recorded there), Step 5

## Fix Progress
- Step 1: [APPLIED] 2026-08-10 — Added §4.4 Security (REQ-SEC-01, out-of-scope position per Decision 2), §4.5 Accessibility and §4.6 Scalability ("Not applicable" + reason). (V-002)
- Step 2: [APPLIED] 2026-08-10 — REQ-SWEEP-03 rewritten: drift-gated regenerated trees excluded per Decision 1 (adapters/ named, C-5 + validate.sh drift gate cited; un-gated generated output stays in scope); historical-corpora sentence appended (V-008); REQ-SWEEP-02 Notes cross-references the recall boundary. (V-001, V-008)
- Step 3: [APPLIED] 2026-08-10 — REQ-SWEEP-04 closure wording reconciled with the close-exactly-once exit contract; cross-reference to REQ-SWEEP-06 added. (V-003)
- Step 4: [APPLIED] 2026-08-10 — C-4 re-measured and corrected (298/300 body lines, 4447/5000 words via check-spec-purity.py's algorithm); per-mode check-count totals + pinning tests sentence appended. (V-004, V-007b)
- Step 5: [APPLIED] 2026-08-10 — REQ-CONS-01 pinned to the specs and impl checklists per Decision 3. (V-007a)
- Step 6: [APPLIED] 2026-08-10 — §8: three new bullets (REQ-CONS-01 by-ID presence, REQ-SWEEP-07 no-git notice, REQ-CARD-04 not-applicable); bullet 1 extended with the drift-gated-mirror deliberately-not-reported variant; "(P5.3)" replaced with "(issue #170, STATUS.md Track F)". (V-005, V-006, V-001 §8)
