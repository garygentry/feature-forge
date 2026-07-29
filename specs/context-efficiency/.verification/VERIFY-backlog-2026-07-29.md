# Verification Report: context-efficiency (backlog)

Date: 2026-07-29
Pipeline Stage: forge-5-loop (pre-launch gate; forge-4-backlog complete at v1, commit `9a29e84`)
Mode: `backlog`

Artifacts Reviewed:
- `specs/context-efficiency/backlog.json` (17 items, ids 001–017, all `pending`)
- `specs/context-efficiency/PRD.md`, `tech-spec.md`, `TRACEABILITY.md`
- `specs/context-efficiency/00-core-definitions.md` … `06-testing-strategy.md`
- `.rauf/backlog.schema.json`, `.rauf/RAUF.md`, `forge.config.json`
- Live target surfaces: `scripts/validate.sh`, `scripts/build-adapters.py`, `scripts/check-spec-purity.py`, `scripts/forge-session.py`, `skills/forge*/SKILL.md`, `references/shared-conventions.md`, `references/stage-exit-protocol.md`, `skills/forge-0-epic/references/edit-mode.md`, `tests/test_build_adapters.py`, `tests/test_adapter_host_neutrality.py`, `tests/test_verifier_role_guard.py`, `.github/workflows/ci.yml`

Method: four parallel `forge-verifier` instances over disjoint CHECK-ID slices — (1) item scoping & acceptance criteria (B11–B14, B25), (2) dependency & ordering sanity (B15–B19, B27), (3) spec coverage & traceability (B07–B10, B20–B24), (4) schema & enum correctness (B01–B06, B26). Findings merged, deduplicated, and renumbered here.

**Checks Executed: 27 of 27. Results: 15 pass, 10 fail, 2 not-applicable.**

Deterministic pre-check: `rauf-stable backlog validate . --backlog specs/context-efficiency --specs-dir ./specs --json` → `{"valid": true, "findings": []}`. The structural layer is clean; every finding below is semantic and beyond what the validator can see.

## Summary

- Total findings: **27** (deduplicated from 35 raw across four dimensions)
- Errors: 3
- Gaps: 13
- Inconsistencies: 6
- Improvements: 5

**Three findings would break the very first loop iteration** (V-001, V-003, V-004) and one more breaks the loop's contract with CI (V-002). **Two P0 requirements have zero acceptance criteria anywhere in the backlog** (V-008 REQ-PERF-01/SC-1, V-009 REQ-BEHAV-01/SC-3).

### Per-check roll-call

| Check | Result | Note |
|---|---|---|
| CHECK-B01 valid JSON | pass | Parses; root keys schema-declared; no `additionalProperties` violation |
| CHECK-B02 required fields | pass | All 17 items carry all 9 fields; no present-but-empty values; all 40 `specReferences` resolve |
| CHECK-B03 unique ids | pass | `001`–`017`, contiguous, zero-padded |
| CHECK-B04 valid types | pass | `{refactor, feature, chore, test}` ⊂ enum; semantically correct per item |
| CHECK-B05 valid priorities | **fail** | Integers in range, but inverted across 4 edges — V-011 |
| CHECK-B06 valid statuses | pass | All `pending` ∈ `{pending, in_progress, done, blocked}` |
| CHECK-B07 specs referenced | pass | All seven numbered specs cited by ≥1 item; no orphans |
| CHECK-B08 P0 coverage | **fail** | V-007, V-008, V-009, V-010, V-017. R2's absence is correctly intentional — not a gap |
| CHECK-B09 spec files exist | pass | All 7 distinct paths stat clean |
| CHECK-B10 valid rel paths | pass | Uniformly `specs/context-efficiency/`-prefixed |
| CHECK-B11 single-iteration scope | **fail** | V-019, V-020 |
| CHECK-B12 fresh-agent detail | **fail** | V-004, V-005, V-006, V-025 |
| CHECK-B13 objective AC | **fail** | V-003, V-014, V-016, V-017, V-018, V-021, V-022, V-024, V-026 |
| CHECK-B14 names files | **fail** | V-005, V-006, V-015, V-021, V-025, V-027 |
| CHECK-B15 valid `dependsOn` | pass | All 24 edges name existing ids |
| CHECK-B16 no cycles | pass | DFS over 17 nodes: DAG |
| CHECK-B17 foundations unblocked | pass | 001, 004, 005 carry `dependsOn: []`; 007→005 is legitimate (both mutate `forge-session.py`, tech-spec §3.7 mandates R5-before-R4) |
| CHECK-B18 interface edges | **fail** | V-010, V-012, V-013, V-023 |
| CHECK-B19 priority vs deps | **fail** | V-011 |
| CHECK-B20 package scaffold | **n/a** | Brownfield. Spec `01` §1: "**No new package.**" No scaffold expected |
| CHECK-B21 shared types/errors | **fail** | Runtime foundation (007) is correct; test-side foundation unowned — V-010 |
| CHECK-B22 subsystem coverage | pass | R1→001-003, R3→004, R5→005-006, R4→007-014, R6→015, guards→016, portability→017 |
| CHECK-B23 integration wiring | pass | Integration-weighted: 002, 006, 011, 012, 013, 017 |
| CHECK-B24 test items | pass | Three dedicated test items plus per-item test ACs |
| CHECK-B25 no oversized items | pass | Descriptions 119–231 words; ≤6 hand-edited files each. 017's bulk is generated output |
| CHECK-B26 generated-artifact freshness | **fail** | V-001, V-002 |
| CHECK-B27 lifecycle conflict | **n/a** | No lifecycle vocabulary in any pairing sense; releases out of scope (tech-spec §3.7, C-7) |

### Deliberately NOT reported

- **R2's absence is correct.** PRD §3.2 marks it "SCOPED OUT", TRACEABILITY.md strikes its rows through with an explicit "expect no backlog items" note, and `backlog.json`'s own `description` says "R2 is SCOPED OUT (PRD §3.2) — author nothing for it". Zero `REQ-R2` references in any item. Consistent across all artifacts.
- **`validate-traceability.py` was not run.** It cannot parse this feature's `REQ-R1-01`-style IDs and emits false "uncovered requirement" noise. Traceability was done by reading PRD.md/TRACEABILITY.md directly and reconciling `03-state-verbs.md` §11.2's 16-row conversion map and `01-architecture-layout.md` §1's file-move manifest against all 17 items.
- **Item 017's `dependsOn` is transitively complete.** One dimension initially flagged it as omitting 001/005/007/008/009/010, but the closure `017 → 002 → 001`, `017 → 006 → 005`, `017 → 011 → 008/009 → 007`, `017 → 012 → 010` reaches every canon-mutating item. Transitive reachability is what ordering requires; no edge needs adding. This claim was dropped from V-001's fix.
- Verified-correct anchors, recorded so they are not re-litigated: `forge-session.py:99` `PRODUCTION_STAGES`, `:177` `_read_state`, `:526` `_load_config`, `:1416` `_resolve_feature_dir`, `epic-manifest.py:315` `atomic_write`, `shared-conventions.md` L217/L230/L243–245/L248/L266–271/L275, `skills/forge/SKILL.md:18`, `forge-5-loop` 298/300 body lines, `forge-0-epic` 292/300 body lines, all 22 `loopRunner` schema fields carrying defaults.

---

## Findings

### V-001: 13 of 17 items mutate canonical surfaces but defer all adapter regeneration to item 017 — every intermediate commit fails the hard `build-adapters.py --check` freshness gate

- **Severity:** gap
- **Location:** `specs/context-efficiency/backlog.json` — `acceptanceCriteria` of items 001, 002, 004, 005, 006, 007, 008, 009, 010, 011, 012, 013, 015; and item 001's `description`
- **Issue:** The freshness gate is real and reachable from the loop's own verification command — confirmed, not hypothesized:
  1. `scripts/validate.sh` **step 6b** provisions `.venv-adapters` and runs `python3 scripts/build-adapters.py --check`, which regenerates to a temp dir and diffs against committed `adapters/`. Its own comment calls it a **HARD gate — NEVER soft-skipped**; non-zero exit increments `ERRORS` → `exit 1`.
  2. `.github/workflows/ci.yml` → `.github/actions/quality-gate/action.yml` step 2 runs `bash scripts/validate.sh` on every `pull_request` and every push to `main`.
  3. **`.rauf/RAUF.md` L10/L14 tells each loop iteration its verification command is `bash scripts/validate.sh`** — the freshness gate sits inside the command a rauf iteration must run before emitting `RAUF_DONE`.

  Baseline verified clean: `.venv-adapters/bin/python3 scripts/build-adapters.py --check` exits 0 at HEAD. So any canon mutation without a regen makes it exit 1.

  Which items break it, verified against `scripts/build-adapters.py` rather than assumed:
  - A skill's **own** `references/` dir is copied **wholesale** (`_emit_bundle`, L1375), not citation-driven (the citation fan-out at L1672 applies only to *bundle-root shared* refs). So **item 001 — described as "purely ADDITIVE … the monolith stays in place so the suite stays green" — still dirties `adapters/`** the moment it creates seven files under `skills/forge-verify/references/`. The item's own premise is wrong for this gate.
  - Item 002 edits `skills/forge-verify/SKILL.md` + `agents/forge-verifier.md` and deletes the monolith, which has six committed copies under `adapters/*/skills/forge-verify/references/`.
  - Items 005, 007, 008, 009, 010 edit `scripts/forge-session.py`, copied verbatim into all six bundles (md5-identical to `adapters/claude/scripts/forge-session.py`).
  - Item 011 edits `references/shared-conventions.md` — **20** committed copies under `adapters/`.
  - Items 004, 006, 012, 013, 015 edit skill bodies and/or `skills/forge-5-loop/references/`.

  No gate named in those 13 items' ACs can catch this: `python3 -m pytest tests` has no real-repo freshness assertion (the two `--check` tests at `tests/test_build_adapters.py` L686–709 run against a `fixture_copy("minimal-canon")` tree, never `REPO_ROOT`); `check-spec-purity.py` excludes `adapters/**` explicitly (L116–126); `ruff` is unrelated and CI-only. `tests/test_verifier_role_guard.py::test_guard_propagates_to_claude_adapter` reads the committed adapter but asserts only four fixed substrings item 002 preserves, and is wrapped in `if CLAUDE_SKILL.exists():` so it degrades to a silent pass.

  Net effect: if the loop obeys RAUF.md and runs `validate.sh`, **item 001 stalls the loop on iteration one** — the agent cannot emit `RAUF_DONE` on a drift it was never told to fix. If it obeys the ACs and runs pytest, all 13 items pass locally and **13 consecutive commits are CI-red**, first green only after item 017.

  This also collides with spec text: `06-testing-strategy.md` §6 opens "**After every moved/split file**, refresh adapter fixtures and re-run the snapshot," and `01-architecture-layout.md` §4 requires each unit to land "as its **own PR/change**, revertible without touching the others" (SC-6). Reverting one unit after a single terminal regeneration leaves `adapters/` carrying that unit's files.
- **Suggested fix:** Append these two criteria to the `acceptanceCriteria` of items 001, 002, 004, 005, 006, 007, 008, 009, 010, 011, 012, 013, 015 — and only those thirteen (003, 014, 016 are tests-only; 017 already owns regeneration):
  ```
  "adapters/ was regenerated in this item's commit: run `python3 -m venv .venv-adapters && .venv-adapters/bin/python3 -m pip install -q -r scripts/requirements-adapters.txt` (create-or-reuse), then `.venv-adapters/bin/python3 scripts/build-adapters.py`, and commit the resulting adapters/ diff alongside the canon change"
  "`.venv-adapters/bin/python3 scripts/build-adapters.py --check` exits 0 (adapters/ matches a fresh generation — validate.sh step 6b, a HARD gate, runs this on every PR)"
  ```
  In item 001, replace `purely ADDITIVE — the monolith stays in place so the suite stays green` with `purely ADDITIVE to canon — the monolith stays in place so the pytest suite stays green; adapters/ still needs regenerating in this commit because a skill's own references/ dir is copied wholesale into all six bundles`.

  Amend item 017's description to frame it as the **final cross-unit reconciliation + fixture refresh** (its steps 2–5 content is correct and should survive verbatim) rather than the first regeneration. Leave its `dependsOn` unchanged — it is transitively complete.

  **Alternative if the above is judged too noisy:** keep regeneration solely in 017 and append to each of the 13 items' `notes`: `"adapters/ is knowingly left stale by this item; build-adapters.py --check (validate.sh step 6b) will fail until item 017 lands. Do NOT emit RAUF_BLOCKED on that failure — verify with python3 -m pytest tests && python3 scripts/check-spec-purity.py instead."` This is strictly worse — 13 red CI runs, and it trains the loop agent to ignore a hard gate.
- **References:** `scripts/validate.sh` step 6b; `.github/actions/quality-gate/action.yml`; `.rauf/RAUF.md` L10/L14; `scripts/build-adapters.py` L49/L1375/L1672; `scripts/check-spec-purity.py` L116–126; `tests/test_build_adapters.py` L686–709; `tests/test_verifier_role_guard.py` L92–103; `06-testing-strategy.md` §6; `01-architecture-layout.md` §4; PRD SC-5/SC-6
- **Checklist:** CHECK-B26, CHECK-B08

### V-002: The backlog's ACs verify with `python3 -m pytest tests`, but `.rauf/RAUF.md` tells each iteration to verify with `bash scripts/validate.sh`

- **Severity:** inconsistency
- **Location:** `backlog.json` (all 17 items' `acceptanceCriteria`) vs `.rauf/RAUF.md` L10/L14 vs `forge.config.json` L9
- **Issue:** Three artifacts disagree about what "verification passes" means, and the disagreement is load-bearing. `bash scripts/validate.sh` is a strict superset: it runs pytest (step 7) **plus** `check-spec-purity` (6a), the `build-adapters.py --check` freshness gate (6b), traceability (8), version-sync (9), installer build+test, `adapter-src/` verify, and ruff (7b). `python3 -m pytest tests` runs none of 6a/6b/8/9. Zero of the 17 items name `validate.sh` in an AC. A loop agent trusting the ACs runs a materially weaker gate than the one RAUF.md instructs and than the one CI enforces — and the delta is exactly V-001, plus `check-spec-purity`, which nine items re-add by hand one at a time precisely because it is missing from the pytest command.

  Confirmed live: `.rauf/RAUF.md` L14 reads `- Test: bash scripts/validate.sh`, while L15–L18 (`Typecheck:`, `Lint:`, `Build:`, `Format:`) are **empty** despite `forge.config.json` declaring `"typeCheckCommand": "ruff check scripts/ eval/"` — the same stale-managed-block symptom.
- **Suggested fix:** Make all three agree; treat `validate.sh` as authoritative since it is what CI runs and therefore the only command that predicts merge success.
  1. Set `forge.config.json` `"testCommand": "bash scripts/validate.sh"`.
  2. Regenerate `.rauf/RAUF.md`'s `<!-- rauf:managed:start -->…<!-- rauf:managed:end -->` block via rauf's own update path so L14–L18 and L31 populate — **do not hand-edit**, it is generated.
  3. Append `"bash scripts/validate.sh passes"` as the final acceptance criterion of all 17 items. Keep the existing pytest / `check-spec-purity` criteria as fast inner-loop signals, but the `validate.sh` line is what gates `RAUF_DONE`.
- **References:** `scripts/validate.sh` steps 6a/6b/7/7b/8/9; V-001
- **Checklist:** CHECK-B26, CHECK-B02

### V-003: Item 001 acceptance criterion 2 is arithmetically false — `grep -oE` counts occurrences, and impl/epic contain 28/13 occurrences of 23/10 unique IDs

- **Severity:** error
- **Location:** `backlog.json` item `001`, `acceptanceCriteria[1]`
- **Issue:** The AC reads *"grep -oE 'CHECK-[A-Z][0-9]+' over the six mode files yields exactly: prd 15, tech 17, specs 38, backlog 27, impl 23, epic 10 (130 total)"*. `grep -oE` emits one line **per occurrence**, not per unique ID. Measured on the actual source spans: prd 15/15, tech 17/17, specs 38/38, backlog 27/27, but **impl = 28 occurrences / 23 unique** (`CHECK-I01`×2, `CHECK-I11`×2, `CHECK-I21`×3, `CHECK-I22`×2 — the Runnability prose cross-references them, e.g. L249 "Weaker than `CHECK-I21`") and **epic = 13 occurrences / 10 unique** (`CHECK-E06`×2, `CHECK-E07`×3). Total occurrences 138, not 130. A zero-context agent performing a faithful byte-for-byte extraction sees this AC go red and "fixes" it the only way available — deleting the in-prose cross-references — directly violating the same item's "Do NOT reword… a single check" rule.
- **Suggested fix:** Rewrite to count unique IDs: *"`grep -oE 'CHECK-[A-Z][0-9]+' <file> | sort -u | wc -l` yields exactly: prd 15, tech 17, specs 38, backlog 27, impl 23, epic 10 (130 unique IDs). Raw occurrence counts are higher for impl (28) and epic (13) because CHECK-I22/I23 and CHECK-E09/E10 cross-reference sibling IDs in their prose — those cross-references must be preserved verbatim."*
- **References:** `skills/forge-verify/references/verification-checklists.md` L249–250, L302, L319–320; item `003` AC 1 (correctly says "contiguity")
- **Checklist:** CHECK-B13

### V-004: Item 001's last span ends at L478, one line past the end of a 477-line file

- **Severity:** error
- **Location:** `backlog.json` item `001`, `description` span list and `agentDelegation.subtasks[2]`
- **Issue:** The item's own prose says the source is "477 lines" (correct — `wc -l` = 477), yet the final span reads `L325–478`. Every other span is inclusive and contiguous (7–31, 32–60, 61–118, 119–209, 210–251, 252–324), so it should be `L325–477`. The wrong bound is repeated in `agentDelegation.subtasks[2]`, so the sub-agent doing the work sees only the wrong figure.
- **Suggested fix:** Change `L325–478` → `L325–477` in both `description` and `agentDelegation.subtasks[2]`. All other boundaries verified correct against the live file (L7, L32, L61, L119, L210, L252, L325 section starts).
- **References:** `skills/forge-verify/references/verification-checklists.md` (477 lines)
- **Checklist:** CHECK-B12

### V-005: Item 013 cites the wrong line range for the navigator's `pipelineStatus` writes — L205–207, not L215–228

- **Severity:** error
- **Location:** `backlog.json` item `013`, `description` (navigator bullet) and `acceptanceCriteria[2]`
- **Issue:** The item says *"Do NOT convert the `pipelineStatus` writes at ~L215–228 (pause/resume/abandon)"*. Verified against `skills/forge/SKILL.md`: the feature-level pause/resume/abandon `pipelineStatus` writes are at **L205, L206, L207**. L213–230 is the **Epic lifecycle** block, which mutates the *epic manifest* via `epic-manifest.py set-status` — not `.pipeline-state.json` at all (the only `pipelineStatus` token in that range is L224, a prose caution). Consequences: (a) the agent treats L205–207 — the writes that must be preserved — as in-scope for conversion, converting exactly what the owner decision excluded; (b) AC 3 is unverifiable at the location it names.
- **Suggested fix:** Replace `~L215–228` with `~L205–207` in the description and `acceptanceCriteria[2]`, adding: *"(the three `/feature-forge:forge pause|resume|abandon {feature}` bullets that set `pipelineStatus`). The epic-lifecycle block at ~L213–230 mutates the epic manifest via `epic-manifest.py set-status`, not `.pipeline-state.json`, and is out of scope for a different reason."*
- **References:** `skills/forge/SKILL.md` L205–207, L213–230
- **Checklist:** CHECK-B12, CHECK-B13, CHECK-B14

### V-006: Item 001's extraction span map silently drops source lines 1–6, losing the "Execute EVERY check" directive and the stack-profile load instruction

- **Severity:** gap
- **Location:** `backlog.json` item `001`, `description` (span list) and `acceptanceCriteria`
- **Issue:** The span map covers L7–478 only. Lines 1–6 are assigned to **no** destination file. Verified contents: the `# Verification Checklists` title, the sentence `Detailed checklists for each verification mode. Execute EVERY check — do not skip.`, and the blockquote `> **Stack-specific details:** When a stack profile exists at references/stacks/{stack}.md, load it alongside this checklist…`. After item 002 deletes the monolith, the "Execute EVERY check" directive and the stack-profile instruction disappear for **prd, tech, specs and backlog** modes (impl and epic survive by accident, re-citing `references/stacks/{stack}.md` inline inside CHECK-I22/CHECK-E10). This is a behavioral change in a feature whose prime directive is zero behavioral diff (C-1, REQ-BEHAV-01/02). No AC detects it — AC 3 covers only CHECK-IDs, AC 4 only the three orchestrator-only headings.
- **Suggested fix:** Add an eighth instruction to item 001's description: *"Each of the six mode files must carry, immediately under its `# ` title, the two shared directives from source L3 and L5 — the `Execute EVERY check — do not skip.` sentence and the `> **Stack-specific details:** …references/stacks/{stack}.md…` blockquote, copied verbatim."* Add the matching AC, and add the same assertion as a 6th assertion in item 003's guard (`tests/test_verification_checklists_split.py`).
- **References:** `skills/forge-verify/references/verification-checklists.md` L1–6; items `001`, `003`; PRD REQ-BEHAV-01/02
- **Checklist:** CHECK-B12, CHECK-B13, CHECK-B14

### V-007: REQ-R4-04's `references/stage-exit-protocol.md` touch point is scheduled by zero backlog items

- **Severity:** gap
- **Location:** `backlog.json` — no item; omission visible at items 010, 011, 013
- **Issue:** Spec `03-state-verbs.md` §11.2 ("Touch-point conversion map — every hand-authored write retired") is a 16-row table. Fifteen rows are claimed by items 011, 012, 013. **Row 5 is claimed by nobody:**
  > `references/stage-exit-protocol.md` — deferred-decisions rule (L184–192) | append `deferredDecisions[]` item | `state-decision --feature … --question … --raised-by …`

  `grep -c "stage-exit-protocol" specs/context-efficiency/backlog.json` returns **0**. The live text at `references/stage-exit-protocol.md` L184–188 still instructs the direct edit verbatim: "record it structurally as a `deferredDecisions[]` entry on this feature's `.pipeline-state.json` … **same direct-edit path as `notes` / `epicChangeRequests[]`**". Item 010 builds `state-decision`, but nothing calls it from this site. REQ-R4-04 is P0 and absolute: "a partial extraction that leaves some sites hand-authoring JSON is not acceptable". The file is also missing from `01-architecture-layout.md` §1's manifest, so the omission is consistent across specs rather than a one-off typo.
- **Suggested fix:** Extend item **011** (it already owns the shared `references/` surface). Retitle to "Convert shared-conventions.md's five state-write touch points **and the stage-exit deferred-decisions rule** to verb calls"; add `"010"` to `dependsOn`; append conversion bullet 6:
  > `references/stage-exit-protocol.md`, deferred-decisions rule (~L184–192) → `state-decision --feature {feature} --question … --raised-by {stage} --specs-dir …`. Delete only the "same direct-edit path as `notes` / `epicChangeRequests[]`" mechanic clause and the field-by-field JSON recipe; the surrounding rule prose is FROZEN by REQ-BEHAV-02 and must survive byte-identical. Precede the fenced call with the full two-line `BOOTSTRAP_PRELUDE`.

  Add two ACs: (a) the rule invokes `state-decision` and no site in `references/` instructs hand-editing `.pipeline-state.json`; (b) `tests/test_stage_exit_protocol.py` passes unchanged. Bump `estimatedIterations` 2 → 3.
- **References:** `03-state-verbs.md` §11.2 row 5, §8; `00-core-definitions.md` §275; PRD §3.4 REQ-R4-04; `01-architecture-layout.md` §1
- **Checklist:** CHECK-B08

### V-008: No item covers spec `06` §7.5 per-R measurement — P0 REQ-PERF-01 / SC-1 has zero acceptance criteria

- **Severity:** gap
- **Location:** `backlog.json` — absent from all 17 items
- **Issue:** REQ-PERF-01 is **P0**: "Each shipped recommendation MUST produce a measured net reduction in instruction tokens on its targeted invocation, measured against a freshly re-measured baseline at implementation time." SC-1 makes it a done-criterion. Spec `06` §7.5 operationalizes it as a per-unit table. **No item's description or acceptance criteria requires any measurement to be taken or recorded.** The only measurement-adjacent text is item 005's *note* ("Do NOT claim a per-stage token saving for R5…") — a prohibition, not a deliverable, and notes are non-binding to the loop runner. As authored, all 17 items can complete with SC-1 unevidenced.
- **Suggested fix:** Add one AC to the **last item of each unit** — 002 (R1), 004 (R3), 006 (R5), 013 (R4), 015 (R6):
  > The unit's measured net instruction-token delta on its targeted invocation (spec `06` §7.5 row for this unit) is recorded in the commit message, computed by the §7.2 method (`wc -l`/`wc -w` over the canonical surface at ~1.3 tok/word) against the baseline of record `.reference/REMEASURE-0.13.0.md`

  For 006 (R5) and 013 (R4) the AC MUST additionally carry §7.4's constraint verbatim: *"record the static file-load delta plus the drift-removal / deterministic-resolution benefit; do NOT assert a ~1.5k (R4) or ~2.7k (R5) per-stage saving — the 188-session corpus shows the read was 2×/1×, not per-stage."* Add no numeric threshold: SC-1's bar is "measured net reduction, correctly attributed"; SC-2 is explicitly directional-not-a-gate.
- **References:** PRD §4.1 REQ-PERF-01, §8 SC-1/SC-2; `06-testing-strategy.md` §7.1/§7.2/§7.4/§7.5
- **Checklist:** CHECK-B08

### V-009: No item covers spec `06` §9's behavior-preservation run — P0 REQ-BEHAV-01 / SC-3 has zero acceptance criteria

- **Severity:** gap
- **Location:** `backlog.json` — absent from all 17 items; nearest text is item 011's `notes`
- **Issue:** REQ-BEHAV-01 is **P0** and SC-3 is called "the feature's headline criterion" by the spec itself. Spec `06` §9 exists precisely because every other guard is static: *"Every guard above is a **static** drift assertion over file content. Nothing in the suite exercises a *running* pipeline — yet SC-3 is the feature's headline criterion… This section owns that gap."* §9 specifies when (once per shipped unit's PR for R4 and R6; once for the batch), what (drive a small feature through `forge-1-prd` → `forge-6-docs`), the comparison basis (the `consumption-data-refresh` corpus, with seven surfaces that must be identical), named reduced substitutes per unit, and a recording requirement ("A run with no recorded comparison basis does not satisfy SC-3").

  The backlog schedules none of it. Item 011's note says "Behavior-preservation review (spec 06 §9) applies to this item's PR" — but it is a note not an AC, it lands only on 011 (not 012/013/015), and items 011/012 carry only *static* prose-diff ACs, exactly what §9 says is insufficient.
- **Suggested fix:** Add an AC to item **013** (R4's last conversion item) and item **015** (R6):
  > A behavior-preservation run per spec `06` §9 is recorded under `specs/context-efficiency/.verification/`, naming the `consumption-data-refresh` comparison transcripts used, and confirms the seven §9 surfaces are identical (AskUserQuestion option sets/order/"(recommended)" labelling; Decision Support wording; Branch Setup/Reconciliation prompts; Stage-Entry Guard + Stage-Completion Re-check classification; the two-commit Git Commit Protocol including the L245/L248 failure branches; verify-gate routing + stage-exit directive handling; the NEXT-STEPS block and its sentinel). The §9 **reduced substitute** is acceptable and must be named explicitly if used — R4: one authoring stage plus a deliberately failed Commit 1 confirming the `--status in-progress` revert path; R6: one gate-off and one gate-on loop launch confirming `agent-selection.md` is read only in the second.

  Promote item 011's note to a matching AC scoped to its own PR. Leave R1/R3/R5 riding the batch run (§9 permits this), but record that in item 017's notes so the batch run is not silently dropped.
- **References:** PRD §4.2 REQ-BEHAV-01/02, §8 SC-3; `06-testing-strategy.md` §9, §2; `00-core-definitions.md` §10
- **Checklist:** CHECK-B08

### V-010: The shared test-helper modules `tests/_state_schema.py` and `tests/_forge_paths.py` are unowned by any item

- **Severity:** gap
- **Location:** `backlog.json` items `005` and `016`; consumed by 008, 009, 010, 014
- **Issue:** Spec `06` specifies two **new shared test helpers**, neither of which exists in `tests/` today (verified: no `_*.py` modules) and neither named anywhere in the backlog:
  1. **`tests/_state_schema.py`** (§4, given as a complete ~60-line code block) exporting `validate_state(state) -> list[str]` and `validate_effective_config(loop_runner) -> list[str]` — the hand-rolled, `jsonschema`-free structural validator supporting the draft-07 subset both schemas use (`type`, `required`, `properties`, `enum`, `items`, `additionalProperties: false`, `$ref` to `#/definitions/*`). Item **005**'s *title* promises "the stdlib schema validator", but its description enumerates only four `forge-session.py` symbols and its ACs only say output "validates against the schema using the stdlib validator" — the module path, its two function names, and its coverage are never committed to. Items **008, 009, 010, 014** then consume it, with 014 saying "Using the stdlib validator **from item 005**". A shared foundation four items depend on but no item's ACs deliver is the classic under-specified-foundation failure: an agent implementing 005 alone will reasonably inline the validator inside `test_effective_config.py`, leaving 008/010/014 with nothing importable.
  2. **`tests/_forge_paths.py`** (§1, also a code block) exporting `REPO_ROOT`, `SKILLS`, `REFERENCES`, `SCRIPTS`, `read()`. Item **016** mentions a `_body_lines()` helper but never this module, while spec `06` §7.3's own guard snippet opens `from _forge_paths import SKILLS, read`.

  Consistently, `01-architecture-layout.md` §1's manifest lists five new `tests/test_*.py` files but neither helper.
- **Suggested fix:** **Item 005** — append to description: *"5. Create `tests/_state_schema.py` exactly as specified in spec `06` §4: `validate_state(state)` and `validate_effective_config(loop_runner)`, both returning a list of human-readable violations (empty == valid), supporting the draft-07 subset both schemas use. Stdlib only — mirror `epic-manifest.py`'s `_schema_findings()` precedent. It is a SHARED module; items 008/009/010/014 import it — do not inline it into a single test file."* Add AC: *"`tests/_state_schema.py` exists exporting `validate_state` and `validate_effective_config`, imports nothing outside the stdlib, and is imported (not duplicated) by `tests/test_effective_config.py`."*

  **Item 016** — add to description: *"Create `tests/_forge_paths.py` (spec `06` §1) exporting `REPO_ROOT`, `SKILLS`, `REFERENCES`, `SCRIPTS` and `read(path)`, and use it from both new guards."* Add AC: *"`tests/_forge_paths.py` exists and both new test modules import their canon paths from it rather than re-deriving `REPO_ROOT`."*

  Cross-reference the validator in items 008, 009, 010, 014 by exact module path so "the stdlib validator from item 005" resolves to a named file.
- **References:** `06-testing-strategy.md` §1, §4, §7.3; `03-state-verbs.md` §12; `01-architecture-layout.md` §1
- **Checklist:** CHECK-B21, CHECK-B17, CHECK-B18, CHECK-B08

### V-011: Four dependency edges invert priority, scrambling the declared R1+R3 → R5 → R4 → R6 sequence

- **Severity:** inconsistency
- **Location:** `backlog.json` — `priority` of items 004, 006, 010; edges 012→010, 015→006, 017→004, 017→006
- **Issue:** Four edges place a dependency at *lower* priority than its dependent (priority 1 = highest, per rauf `docs/SCHEMAS.md` L36): 012 (p1)→010 (p2); 015 (p1)→006 (p2); 017 (p1)→004 (p2); 017 (p1)→006 (p2). All other 20 edges are correctly ordered.

  This is not cosmetic. rauf's `selectNextItem()` (`docs/SPEC-CORE.md` L218) returns "the highest-priority pending item whose dependencies are all done", ties broken by lowest id — priority-first, **not** file order. Simulating that selector against the backlog as written yields:

  `001 002 005 007 008 009 011 013 003 004 006 015 010 012 017 014 016`

  So **004 (R3) executes 10th, mid-R4**, not as a quick win alongside R1; **015 (R6) executes 12th, before 010 and 012, which are R4 items** — R4 is split across the R6 change; and **006 (R5's consumer half) executes 11th, after five R4 items**. That contradicts `backlog.json`'s own `description` ("Sequencing: R1+R3 → R5 → R4 → R6") and tech-spec §3.7, and degrades REQ-DELIV-01/SC-6's "each unit lands as its own revertible change" — you cannot revert R6 without straddling two R4 items that landed after it.

  Secondary, same root: item 004's P2 rank contradicts the leverage it claims. Its description states R3 is "a single-line relocation worth ~1.72k tokens per navigator invocation", it has `dependsOn: []`, `estimatedIterations: 1`, and its notes say "Independent of every other item" — the cheapest, least-risky, highest-per-invocation-saving change in the feature. Meanwhile item 005 is P1 despite its own notes disclaiming its token benefit ("the realized saving is well below the ~2.7k static projection"). The defensible reading is that 005 is P1 for *dependency depth*, not token value — but that reasoning is nowhere recorded.
- **Suggested fix:** Set `"priority": 1` on items **004**, **006** and **010**. Verified: this removes all four inversions and produces `001 002 004 005 006 007 008 009 010 011 012 013 015 017 003 014 016` — R1 → R3 → R5 → R4 → R6 → adapters → guards, matching tech-spec §3.7. Do **not** instead demote 012/015/017: 017 is the ship-blocking adapter regeneration (REQ-PORT-03/SC-5) and 012 is mandatory under REQ-R4-04. Leave 003, 014, 016 at P2 — test-only leaves that block nothing (but see V-023, which may raise 014).

  Verify with:
  ```
  python3 -c "
  import json
  b=json.load(open('specs/context-efficiency/backlog.json'))
  p={i['id']:i['priority'] for i in b['items']}
  bad=[(d,i['id']) for i in b['items'] for d in i['dependsOn'] if p[d]>p[i['id']]]
  print('inversions:', bad or 'none')"
  ```
  which must print `inversions: none`.
- **References:** tech-spec §3.7; `backlog.json` `description`; rauf `docs/SPEC-CORE.md` L218, `docs/SCHEMAS.md` L36
- **Checklist:** CHECK-B19, CHECK-B05

### V-012: Item 012 must depend on 006 — 006 inserts a prelude into `forge-4-backlog/SKILL.md` that invalidates 012's "inline the prelude" instruction

- **Severity:** inconsistency
- **Location:** `backlog.json` item 012 `dependsOn`, `description` (forge-4-backlog bullet), `agentDelegation.subtasks[1]`
- **Issue:** Items 006 and 012 both edit `skills/forge-4-backlog/SKILL.md` with **no edge between them**, so their order is decided only by priority/tie-break. Verified against the live file: the loopRunner-defaults read is at **L32**, the completion state write at **L139**, and the file's only bootstrap prelude at **L154**. Item 006 inlines a full two-line `BOOTSTRAP_PRELUDE` at ~L32. Once that lands, a prelude *precedes* item 012's call site at ~L139 — but 012's description says "Call site ~L139 above the prelude (L154) → inline", and subtask 2 instructs "Both call sites sit ABOVE their file's only prelude, so inline the full two-line BOOTSTRAP_PRELUDE verbatim at each". That contradicts 012's own `acceptanceCriteria[1]` ("reusing an existing prelude when one precedes the call site, otherwise inlining"). A fresh agent following the description inlines a redundant second prelude, spending scarce body lines and diverging from the pattern 012 applies to forge-1-prd.
- **Suggested fix:** Set item 012 `dependsOn` to `["006","008","009","010"]`; replace the forge-4-backlog bullet with: *"`skills/forge-4-backlog/SKILL.md` — completion → `state-complete --based-on …`. Item 006 has already inlined a prelude near the top of this file (~L32), so this call site can **reuse** it; do not inline a second prelude. Re-derive line numbers rather than trusting ~L139."* Make the same correction in `agentDelegation.subtasks[1]`, which must then instruct inlining for `forge-2-tech` only.
- **References:** `skills/forge-4-backlog/SKILL.md` L32/L139/L154; items 006, 012
- **Checklist:** CHECK-B18, CHECK-B19

### V-013: Items 006 and 013 contend for `forge-5-loop`'s 2-line budget with no ordering edge, and only 006 has a sanctioned deferral

- **Severity:** gap
- **Location:** `backlog.json` items 006 and 013 (`dependsOn`), item 006 `description` (deferral clause), item 013 `acceptanceCriteria[4]`
- **Issue:** Three items edit `skills/forge-5-loop/SKILL.md` against a measured **2 spare body lines** (298/300): 006 (R5 consumer, call site above the L64 prelude → must inline a full prelude), 013 (R4 conversion, sites at ~L188/~L258, below the L64 prelude → reuses it), 015 (R6). Item 015 correctly pins itself last via `dependsOn: ["006","013"]`, but **006 and 013 have no edge between them**. Under the backlog as written 013 runs 8th and 006 11th; under V-011's priority fix that **flips** to 006 5th and 013 12th.

  The flip matters because the deferral escape hatch lives only in 006 ("If the forge-5-loop edit cannot be brought to a net change that keeps the body ≤300 lines … DEFER that one consumer"). Item 013 has no such valve — REQ-R4-04 forbids a partial extraction, and its AC 5 hard-requires "body is ≤300 lines and ≤5000 words after this item". If 006 runs first and its agent judges the inlined prelude "just fits", the mandatory 013 can then overflow with no sanctioned recovery, blocking the loop and requiring human intervention. Ordering 013 first makes 006's conditional deferral evaluable against real post-R4 numbers, which is what the clause was written for.
- **Suggested fix:** Add `"013"` to item 006's `dependsOn` → `["005","013"]`, and append to its notes: *"Ordered after 013 deliberately: R4's forge-5-loop conversion is mandatory (REQ-R4-04) and has no deferral clause, while this item's forge-5-loop consumer does. Measure the body after 013 has landed, then fit-or-defer."* Verified acyclic (006→013→{008,009}→007→005; 015 and 017 still resolve) and introduces no new inversion once 006 is priority 1 per V-011.
- **References:** `skills/forge-5-loop/SKILL.md` L25, L64, L188, L258; items 006, 013, 015; REQ-R4-04
- **Checklist:** CHECK-B18, CHECK-B19

### V-014: Item 009 leaves `--status in-progress` semantics undefined for `completedAt`, `version` and the staleness cascade

- **Severity:** gap
- **Location:** `backlog.json` item `009`, `description` branch 2 and `acceptanceCriteria[3]`
- **Issue:** Branch 2 is specified as *"set `status` (from `--status`, default `complete`), `completedAt`, `version`, `basedOnVersions`, `artifacts`, and `commitHash = None` … Then apply the staleness cascade"* — with no carve-out for `--status in-progress`. Per item 011 AC 4, `--status in-progress` is the conversion target for `references/shared-conventions.md` **L245** ("If Commit 1 fails: do NOT update pipeline state to complete… leave state as `in-progress` so the stage can be resumed"). As specified, that failure path would stamp a `completedAt` on a stage that never completed, bump `version`, reset `commitHash` to `null`, and fire the downstream staleness cascade — four mutations the frozen prose forbids.

  AC 4 (*"`--status in-progress` records in-progress instead of complete, and the entry still validates"*) cannot detect any of this: `references/pipeline-state-schema.json` `$defs.stageEntry` has no conditional between `status` and `completedAt` (both independent optional properties), so the malformed entry validates cleanly.
- **Suggested fix:** Append to branch 2: *"When `--status in-progress` is passed, do NOT write `completedAt`, do NOT bump `version`, do NOT reset `commitHash`, and SKIP the staleness cascade — this branch serves the Commit-1-failure recovery at shared-conventions L245, whose contract is 'leave state as in-progress so the stage can be resumed'."* Replace AC 4 with: *"`--status in-progress` records `status: \"in-progress\"` and leaves `completedAt` absent/null, `version` unchanged, `commitHash` unchanged, and fires no staleness cascade — asserted by a dedicated test, not by schema validation alone (the schema permits `completedAt` on an in-progress entry, so validation cannot catch this)."* Propagate the decision to `03-state-verbs.md` so backlog and spec agree.
- **References:** `references/shared-conventions.md` L245; `references/pipeline-state-schema.json` `$defs.stageEntry`; items 011, 014
- **Checklist:** CHECK-B13

### V-015: Items 008, 009 and 010 never name the file they modify

- **Severity:** gap
- **Location:** `backlog.json` items `008`, `009`, `010`, `description`
- **Issue:** All three add subcommands to `scripts/forge-session.py`, but none of their descriptions contains that path. Item 008 names only `tests/test_state_verbs.py`; item 009 names **no file path at all**; item 010 names only `references/pipeline-state-schema.json` and `tests/test_state_verbs.py`. The path is discoverable only by reading item 007 (a different item, whose description a fresh loop session does not load) or by opening `03-state-verbs.md`. Every other implementation item names its target file in the first two sentences. Item 009 is the worst case: the most complex verb in the feature, opening "The most complex R4 verb" with no file anchor.
- **Suggested fix:** Prefix each description with the target file, matching item 007's style. 008: *"Add four verbs to `scripts/forge-session.py` (tests in `tests/test_state_verbs.py`)…"*. 009: *"Add the `state-complete` verb to `scripts/forge-session.py` (tests in `tests/test_state_verbs.py`) — the most complex R4 verb…"*. 010: *"Add two verbs to `scripts/forge-session.py` (tests in `tests/test_state_verbs.py`)…"*.
- **References:** item `007` description (correct pattern); `scripts/forge-session.py`
- **Checklist:** CHECK-B14

### V-016: Item 002's acceptance criterion 2 is written in the exact brace-enumeration form its own description forbids

- **Severity:** inconsistency
- **Location:** `backlog.json` item `002`, `description` step 1 vs `acceptanceCriteria[1]` and `[2]`
- **Issue:** The description says, in caps: *"NEVER use a brace enumeration like `{prd,tech,specs}.md` — the fan-out regex character class has no comma, so it captures one bogus token and yields zero usable paths."* AC 2 then states the required end state as *"skills/forge-verify/SKILL.md contains all six literal paths `references/verification-checklists/{prd,tech,specs,backlog,impl,epic}.md`"* — the forbidden form verbatim. AC 3 contradicts AC 2 again by requiring no comma-separated brace form in any skill body. An agent optimizing for "make AC 2 literally true" writes the one string that breaks adapter citation fan-out — precisely the failure this item exists to prevent.
- **Suggested fix:** Rewrite AC 2 without brace shorthand: *"`skills/forge-verify/SKILL.md` contains six separate literal citations — `references/verification-checklists/prd.md`, `references/verification-checklists/tech.md`, `references/verification-checklists/specs.md`, `references/verification-checklists/backlog.md`, `references/verification-checklists/impl.md`, `references/verification-checklists/epic.md` — each appearing as a standalone path, plus `references/findings-template.md`."*
- **References:** item `016` AC 2/3; `scripts/build-adapters.py` citation fan-out
- **Checklist:** CHECK-B13

### V-017: Item 013's acceptance criterion 6 is internally contradictory, omits the schema-**read** assertion, and collides with a file no item converts

- **Severity:** inconsistency
- **Location:** `backlog.json` item `013`, `acceptanceCriteria[3]` vs `[5]`; `skills/forge-0-epic/references/edit-mode.md` L253–265
- **Issue:** Three defects converge on one criterion.

  **(a) Self-contradiction.** AC 4 requires *"forge-verify's production stageEntry stamps invoke state verbs **while its verifyEntry write path is unchanged**"* — i.e. `skills/forge-verify/SKILL.md` Step 6 keeps hand-writing verify entries. AC 6 then requires *"grep across skills/ finds no remaining instruction to hand-author .pipeline-state.json **except the navigator's pipelineStatus block**"*. Both cannot hold: forge-verify Step 6 is a second deliberately-retained exception. An agent making AC 6 literally true converts the path AC 4 forbids touching. AC 6 also gives no grep pattern and hinges on the unverifiable phrase "instruction to hand-author".

  **(b) Missing the read.** REQ-R4-01 (P0) is about the *read*, not the write: stages "MUST no longer need to **read** the full `pipeline-state-schema.json` (191 lines) on each invocation". Item **012** covers this correctly ("…or reading `pipeline-state-schema.json` to author state"). Item 013 does not — nothing asserts the schema-read instruction is gone. Of the eight skill bodies citing `pipeline-state-schema.json` today, **three fall to item 013** (`forge-6-docs`, `forge-verify`, `forge`). Item 013's own notes say exactly this — "three of the eight skills citing `pipeline-state-schema.json` would keep the per-stage read R4 exists to remove" — but the reasoning never reached an AC, so an implementer satisfying the literal ACs leaves all three reads in place at green.

  **(c) Unsatisfiable collision.** `skills/forge-0-epic/references/edit-mode.md` is under `skills/` and contains a "**Member State Example (creation C7)**" with a hand-authorable JSON block seeding `epic`, `currentStage` and `stages["forge-0-epic"]`. No item touches it: item 012's forge-0-epic subtask names only `SKILL.md`, and `01-architecture-layout.md` §1's manifest omits it. So AC 6 as written is unsatisfiable — the grep hits this site with no guidance. (The seven verbs cannot fully replace it anyway: none writes the `epic` back-pointer on a brand-new member stub.)
- **Suggested fix:** Replace AC 6 with a single combined criterion:
  > `grep -rn 'pipeline-state-schema.json' skills/` returns no instruction to read the schema in order to author state, and `grep -rn '\.pipeline-state\.json' skills/` returns hand-authoring instructions in exactly three places, all deliberate exclusions: (a) `skills/forge/SKILL.md` L205–207 (`pipelineStatus` pause/resume/abandon), (b) `skills/forge-verify/SKILL.md` Step 6 (the `verifyEntry` write path, for which R4 adds no verb), and (c) `skills/forge-0-epic/references/edit-mode.md`'s Member State Example (C7 member-subdir creation, which writes the `epic` back-pointer no verb owns). Citations that merely document field shapes may remain.

  Record exclusion (c) in item 012's notes and in `03-state-verbs.md` §11.2's "Explicitly out of scope" callout so the REQ-R4-04 census stays honest. If instead the owner rules `edit-mode.md` **in** scope, add it to item 012's third `agentDelegation` subtask and description with a matching AC, and drop (c) from the list above.
- **References:** PRD §3.4 REQ-R4-01; `skills/forge-verify/SKILL.md` Step 6; `skills/forge/SKILL.md` L205–207; `skills/forge-0-epic/references/edit-mode.md` L253–265; `03-state-verbs.md` §11.2 rows 6, 12–16; item 012 AC 1 (the correct pattern)
- **Checklist:** CHECK-B13, CHECK-B08

### V-018: Item 016's "118 citations on the unmodified repo" acceptance criteria are guaranteed false at the moment item 016 runs

- **Severity:** inconsistency
- **Location:** `backlog.json` item `016`, `acceptanceCriteria[0]` and `[1]`
- **Issue:** AC 1 requires *"`tests/test_reference_citations.py` passes on the unmodified repo before any other change (verify by running it at HEAD~ if needed)"*; AC 2 pins *"resolves 118 citations with zero misses"*. The figure is correct **today** — reproduced: the specified regex over `skills/*/SKILL.md` yields exactly 118 literal citations plus 4 template citations (`stacks/{stack}.md`×3, `stacks/*.md`×1).

  But 016's dependency closure is `{001,002,004,005,006,007,008,009,013,015}` — about a dozen items land first: item 002 removes the 5 existing `references/verification-checklists.md` citations and adds 7 new ones; item 015 adds `references/agent-selection.md` citations; item 004 rewords the `process-overview.md` citation. So (a) "the unmodified repo" no longer exists, (b) `HEAD~` is ~12 commits short of the intended pre-feature baseline, and (c) 118 is stale for the post-R1/R3/R6 tree (~122). A fresh agent has two bad options: hardcode 118 and ship a red test, or edit the AC. The regex-validation *intent* is sound and important — 016's notes record that the originally-specified regex was red on day one — only the ordering-derived phrasing is wrong.
- **Suggested fix:** Replace AC 1 with: *"The citation regex is validated against the **pre-feature baseline commit** — the hash recorded in `specs/context-efficiency/.pipeline-state.json` under `stages['forge-4-backlog'].commitHash`, not `HEAD~` — where it must resolve 118 citations with zero misses; it must then also pass on the current tree."* Replace AC 2 with: *"On the current tree the guard resolves **every** literal `references/…md` citation in every `skills/*/SKILL.md` with zero unresolved. Do not assert a fixed total; items 002, 004 and 015 change it. The guard does not flag project-level `.agents/references/…` or `.claude/references/…` paths (forge-2-tech L61) and does not swallow a sentence-final period (forge-5-loop L165) — assert both with a fixture string."* Move "118 on the unmodified repo" into `notes` as regex provenance. Consider adding `"012"` to 016's `dependsOn` so the body-cap guard's "green (max is forge-5-loop)" claim is guaranteed rather than incidentally true via tie-break.
- **References:** items `002`, `004`, `012`, `015`; `skills/forge-2-tech/SKILL.md` L61; `skills/forge-5-loop/SKILL.md` L165
- **Checklist:** CHECK-B13, CHECK-B18, CHECK-B19

### V-019: Item 012 bundles forge-0-epic's hard 8-line cap with four unconstrained edits and defines no behavior if the cap is exceeded

- **Severity:** gap
- **Location:** `backlog.json` item `012`, `description` and `acceptanceCriteria[2]`
- **Issue:** Item 012 converts five skill bodies. Four are unconstrained; the fifth, `skills/forge-0-epic/SKILL.md`, has a measured **8 lines of headroom** (292/300 body lines — verified: raw `wc -l` 298 minus 6 frontmatter lines), and the item's own notes say *"Dropping R2 removed the ~4 lines R4 was originally expected to inherit here, so there is no slack to spend."* If the conversion does not fit, AC 3 fails and the **entire five-body item** is blocked — including the four edits that already succeeded — with no defined recovery.

  The directly analogous risk in item 006 (forge-5-loop's 2-line headroom) *is* handled: 006 spells out an explicit DEFER branch, an AC for recording the deferral, and the REQ-DELIV-01 rationale. Item 012 has no equivalent, so an agent facing an over-cap forge-0-epic will either emit `RAUF_BLOCKED` on a mostly-complete item or start deleting unrelated lines to make room.
- **Suggested fix:** Add to item 012's description, mirroring item 006: *"`skills/forge-0-epic/SKILL.md` has 8 body lines of headroom. Measure the frontmatter-stripped body before and after. If the conversion cannot be made line-neutral-or-negative there, DEFER that one body: apply the other four conversions, leave forge-0-epic hand-authoring its state, state the deferral and the measured line/word figures in the commit message, and do not delete unrelated lines to make room."* Add AC: *"If the forge-0-epic conversion was deferred, that decision and its measured figures are stated in the commit message and noted in `progress.md`."*

  **Alternative if the owner prefers hard coverage:** split forge-0-epic into its own item `012b` depending on `012`, so the risky edit cannot block the four safe ones.
- **References:** item `006` (the DEFER pattern to copy); `skills/forge-0-epic/SKILL.md` (298 raw / 292 body lines); `scripts/check-spec-purity.py` Rule 4
- **Checklist:** CHECK-B11, CHECK-B25

### V-020: Item 006's DEFER branch can complete the item with R5's forge-5-loop consumer unconverted and nothing scheduled to finish it

- **Severity:** gap
- **Location:** `backlog.json` item `006`, `description` (DEFER paragraph) and `acceptanceCriteria[4]`
- **Issue:** Item 006 may legitimately exit "done" having converted only one of its two consumers, with the deferral recorded solely in a **commit message**. Nothing picks the work back up: no later item mentions the forge-5-loop `effective-config` consumer, and item 015 (the last item touching that body) asserts only the ≤300-line cap, not the R5 conversion. Item 015 in fact *frees* room in that body (trims L165, moves ~90 lines out to `agent-selection.md`), so the deferral is very likely recoverable — but nothing is scheduled to retry it and no AC reports the residual. The result is a silent partial delivery of R5's consumer half whose only trace is one line of git history.
- **Suggested fix:** Add an AC to item **015** (which lands after 006 has freed line budget in the same body): *"If item 006 deferred the forge-5-loop `effective-config` consumer edit, retry it here now that R6 has freed body lines; if it still does not fit, restate the deferral with measured figures in the commit message and append it to `progress.md` as an open residual."* Also amend item 006 AC 5 to require the deferral be appended to `progress.md`, not only the commit message, so the loop's accumulated-learnings file carries it forward.
- **References:** items `006`, `015`; PRD REQ-DELIV-01; `skills/forge-5-loop/SKILL.md` (304 raw / 298 body lines)
- **Checklist:** CHECK-B11, CHECK-B13

### V-021: Item 017 step 4 is a conditional judgment call with no acceptance criterion — the stale five-tuple in `tests/test_build_adapters.py` will likely be left as-is

- **Severity:** gap
- **Location:** `backlog.json` item `017`, `description` step 4; `acceptanceCriteria` (no coverage)
- **Issue:** Step 4 reads *"Check `tests/test_build_adapters.py`'s own local `AGENT_TARGETS` constant (L38), which is still a five-tuple, and update it if the moved files require it."* Verified: `tests/test_build_adapters.py:38` is `AGENT_TARGETS = ("claude", "codex", "copilot", "cursor", "gemini")  # 00 §1`, while `scripts/build-adapters.py:49` is the six-tuple including `"pi"`. "If the moved files require it" is an unresolved judgment with no decision procedure and **no acceptance criterion at all**. Meanwhile AC 2 requires the new files be "present under every regenerated adapter bundle, including `adapters/pi/`" — which a five-tuple test constant will never assert. An agent takes the path of least resistance, skips step 4, and leaves the pi target unguarded — exactly the #122/#132 failure class this item's notes cite.
- **Suggested fix:** Make step 4 unconditional: *"Update `tests/test_build_adapters.py` L38 `AGENT_TARGETS` from the five-tuple to the six-tuple `(\"claude\", \"codex\", \"copilot\", \"cursor\", \"gemini\", \"pi\")`, matching `scripts/build-adapters.py` L49. Run the file's tests and fix any per-target assertion that assumed five targets."* Add AC: *"`tests/test_build_adapters.py`'s local `AGENT_TARGETS` is the six-tuple matching `scripts/build-adapters.py` `AGENT_TARGETS`, and a test asserts the two constants are equal so they cannot drift again."*
- **References:** `tests/test_build_adapters.py` L38; `scripts/build-adapters.py` L49; PRD REQ-PORT-03 / SC-5
- **Checklist:** CHECK-B13, CHECK-B14

### V-022: Item 017's "no Claude-only tool name" acceptance criterion is unenumerated and subjective, despite an authoritative token list already existing in the repo

- **Severity:** gap
- **Location:** `backlog.json` item `017`, `description` step 5 and `acceptanceCriteria[4]`
- **Issue:** AC 5 reads *"No moved reference file contains a literal `/clear` or a Claude-only tool name."* "A Claude-only tool name" is enumerated nowhere, so two agents check two different sets and neither can be reviewed. The repo already owns the canonical list: `tests/test_adapter_host_neutrality.py` defines `FORBIDDEN_TOKENS: tuple[str, ...] = ("`Agent` tool", "`Skill` tool", "`Monitor` tool", "/clear", "AskUserQuestion", …)` and applies it at L76. The AC neither cites nor runs it, replacing an existing deterministic gate with a manual eyeball pass.
- **Suggested fix:** Replace step 5 and AC 5 with a command-backed criterion: *"`python3 -m pytest tests/test_adapter_host_neutrality.py` passes — it applies the canonical `FORBIDDEN_TOKENS` tuple to every non-Claude host bundle. Additionally confirm the newly-created files — the six mode checklists, `findings-template.md`, `agent-selection.md` — are inside that test's scanned set; if its file globs do not reach them, extend the globs in this item."*
- **References:** `tests/test_adapter_host_neutrality.py` L34–43, L76; PRD REQ-PORT-02
- **Checklist:** CHECK-B13

### V-023: The R4 schema-conformance guard (014) is scheduled after every conversion it exists to protect, and its `dependsOn` names the wrong items

- **Severity:** improvement
- **Location:** `backlog.json` item `014`, `dependsOn` (`["011","012","013"]`) and `priority` (2)
- **Issue:** Item 014 tests the **verbs** — every AC targets `state-*` output, the multi-verb sequence, first-write edge cases, corrupt-file refusal, schema byte-identity. None exercise items 011/012/013. Yet its `dependsOn` names exactly those three, so under rauf's selector the guard lands 16th, after ~10 skill bodies and `references/shared-conventions.md` have already been rewritten to call the verbs. Item 014's own notes argue against this: "the defects found during spec verification (a lone `{'commitHash': …}` entry, a first-write state missing required fields) only appear when verbs run in a realistic order against partially-populated state." If that sequence test lands *after* the conversions, discovering such a defect means re-opening three completed refactor items. Placing it immediately after 010 costs nothing — its real dependencies are already satisfied there — and converts it from a retrospective audit into a gate.
- **Suggested fix:** Set item 014 `dependsOn` to `["008","009","010"]` and `priority` to `1`. If the guard should also **gate** the conversions (recommended, and the reason this is worth doing), add `"014"` to the `dependsOn` of items **011**, **012** and **013**. Verified acyclic with zero inversions; combined with V-011/V-012/V-013 it yields `001 002 003 004 005 007 008 009 010 014 011 013 006 012 015 017 016`.
- **References:** item `014` (acceptanceCriteria, notes); items 011, 012, 013
- **Checklist:** CHECK-B18, CHECK-B19

### V-024: Item 016's 4688-char frontmatter ceiling does not state how it is measured, and the two plausible methods differ by 26 chars

- **Severity:** improvement
- **Location:** `backlog.json` item `016`, `description` §4 and `acceptanceCriteria[4]`
- **Issue:** The AC calls 4688 an *"exact ceiling"* with *"a comment citing the measurement source"*, but never defines the measurement. Both readings were reproduced across the 13 `skills/*/SKILL.md` files: summing the raw text after `description: ` (all 13 values double-quoted) gives **4688**; stripping the surrounding quotes gives **4662**. Since REQ-PERF-02 is a non-increase requirement enforced by an exact ceiling, choosing the stripped method silently grants 26 characters of undetectable growth — the very thing the guard exists to prevent. A zero-context agent has no way to pick correctly.
- **Suggested fix:** Amend description §4 and the AC to: *"Sum, over all 13 `skills/*/SKILL.md`, the length of the raw text following `description: ` on the frontmatter line **including its surrounding double quotes**; the total must be ≤ 4688 (measured at 0.13.0; the quote-stripped total is 4662 — do not use it, it grants 26 chars of undetected slack)."*
- **References:** `skills/*/SKILL.md` frontmatter (13 files); PRD REQ-PERF-02
- **Checklist:** CHECK-B13

### V-025: Item 017 never gives the adapter build command

- **Severity:** improvement
- **Location:** `backlog.json` item `017`, `description` step 1 and `acceptanceCriteria[0]`
- **Issue:** Step 1 says *"Run the adapter build and regenerate `adapters/` for all six targets"* and AC 1 says *"All six adapter targets regenerate cleanly with no build errors"* — but no invocation is given. Every other command-bearing item quotes its command verbatim (e.g. item 005 AC 1 quotes the full `forge-session.py effective-config …` line). Compounding this, `tests/test_build_adapters.py` L41–50 shows the generator needs a YAML dependency and prefers a gitignored `.venv-adapters/bin/python3` when present — an agent invoking bare `python3 scripts/build-adapters.py` may hit an import error and misdiagnose it as a build failure.
- **Suggested fix:** Quote the exact invocation in step 1, including the interpreter rule: *"Run `python3 scripts/build-adapters.py` for all six targets. If the generator's YAML dependency is missing under the default interpreter, use the gitignored `.venv-adapters/bin/python3` (the same preference `tests/test_build_adapters.py::_generator_interpreter()` encodes)."* Mirror the exact command into AC 1 so "regenerates cleanly" is checkable. Coordinate with V-001, which adds the same venv provisioning to 13 other items.
- **References:** `scripts/build-adapters.py`; `tests/test_build_adapters.py` L41–50
- **Checklist:** CHECK-B12, CHECK-B14

### V-026: Two acceptance criteria are satisfied by transient manual experiments that leave no reviewable evidence

- **Severity:** improvement
- **Location:** `backlog.json` item `003` `acceptanceCriteria[1]`; item `016` `acceptanceCriteria[0]`
- **Issue:** Item 003 AC 2: *"The guard fails if a CHECK-ID is removed from any mode file (verify by temporarily deleting one, confirming red, then restoring)."* Item 016 AC 1: *"…verify by running it at HEAD~ if needed."* Both describe a mutation experiment performed and then undone. Nothing durable results, so neither the loop runner, CI, nor a human reviewer can confirm it happened — and an agent under pressure to emit `RAUF_DONE` can assert it truthlessly at zero cost. The intent (mutation-testing a drift guard, per item 003's own note "a drift guard that cannot go red is worse than none") is right; the evidence discipline is missing.
- **Suggested fix:** Require durable evidence. Item 003 AC 2: *"Mutation-test the guard and record the result in the commit message, quoting the assertion text that failed and the mode file mutated (e.g. `removed CHECK-S38 from specs.md → test_specs_checklist_contiguous failed: expected 38 contiguous IDs, found 37`), then restore the file."* Apply the same pattern to item 016 AC 1 — coordinate with V-018, which rewrites that same string.
- **References:** items `003`, `016`; `tests/test_stage_exit_protocol.py` (the discipline model item 003 cites)
- **Checklist:** CHECK-B13

### V-027: Item 016 creates two test files but does not say which of its four guards belongs in which

- **Severity:** improvement
- **Location:** `backlog.json` item `016`, `description`
- **Issue:** The description says *"Create `tests/test_reference_citations.py` and `tests/test_always_loaded_surface.py`"*, then enumerates four guards (1 citation, 2 reverse-citation, 3 body cap, 4 always-loaded surface) with no mapping. Guard 3 belongs to neither filename obviously. The ACs reference guards by function without naming a file, so the set is satisfiable regardless of placement — but items 003 and 015 add sibling guards, and an arbitrary split makes the suite's layout unpredictable for anyone extending it.
- **Suggested fix:** State the mapping: *"`tests/test_reference_citations.py` holds guards 1 and 2 (forward citation resolution, reverse citation coverage). `tests/test_always_loaded_surface.py` holds guards 3 and 4 (SKILL.md body caps, the 13-description frontmatter budget, and the two `session-check.sh` hook tests)."*
- **References:** item `016`; `tests/` layout
- **Checklist:** CHECK-B14

---

## Fix Execution Plan

### User Decisions — ALL RESOLVED 2026-07-29 (owner: Gary Gentry)

**No decisions remain open. Every step below is executable as written.** The six gates were resolved interactively at the forge-5-loop pre-launch verify; each took the recommended option.

1. **V-001 — adapter-regeneration strategy → PER-ITEM REGENERATION.** Each of the 13 canon-mutating items regenerates `adapters/` in its own commit and asserts `build-adapters.py --check` exits 0. Do **not** use the defer-to-017 alternative; it is superseded and must not be applied. Rationale: with D2 resolved to `validate.sh`, the freshness gate runs inside every iteration, so per-item regeneration is mandatory rather than merely tidy — deferring would fail item 001 on iteration one with no recovery. Apply Step 2 option (a).
2. **V-002 — canonical verification command → `bash scripts/validate.sh`.** Set it as `testCommand` in `forge.config.json`, regenerate `.rauf/RAUF.md`'s managed block via rauf's own update path (never hand-edit), and append `"bash scripts/validate.sh passes"` as the final AC of all 17 items. Existing pytest / `check-spec-purity` criteria stay as fast inner-loop signals.
3. **V-017(c) — `skills/forge-0-epic/references/edit-mode.md` → DELIBERATELY EXCLUDED.** Its C7 Member State Example writes the `epic` back-pointer on a fresh member stub, and no state verb owns that field. Record it as the third named exclusion in item 013's rewritten AC 6, in item 012's `notes`, and in `03-state-verbs.md` §11.2's "Explicitly out of scope" callout so the REQ-R4-04 census stays honest. Do **not** convert the file.
4. **V-019 — item 012 shape → DEFER BRANCH (no `012b` split).** Backlog stays at 17 items. Add the item-006-style DEFER branch and the deferral-recording AC to item 012; if forge-0-epic cannot be made line-neutral-or-negative, apply the other four conversions, leave it hand-authoring state, and record the deferral with measured line/word figures in the commit message **and** `progress.md`.
5. **V-023 — verb-conformance guard → GATES THE CONVERSIONS.** Set item 014 `dependsOn` to `["008","009","010"]` and `priority: 1`, **and** add `"014"` to the `dependsOn` of items 011, 012 and 013.
6. **V-014 — `--status in-progress` → SUPPRESS THE COMPLETION FIELDS.** When `--status in-progress` is passed: do not write `completedAt`, do not bump `version`, do not reset `commitHash`, and skip the staleness cascade. Assert it with a dedicated test, not schema validation (the schema permits `completedAt` on an in-progress entry). Propagate the same semantics into `specs/context-efficiency/03-state-verbs.md` so spec and backlog agree.

**Resulting expected execution order** once every step lands: `001 002 003 004 005 007 008 009 010 014 011 013 006 012 015 017 016`.

### Execution Steps

#### Step 1: Reconcile the verification command across config, RAUF.md, and the backlog
- **Files:** `forge.config.json`, `.rauf/RAUF.md`, `specs/context-efficiency/backlog.json`
- **Addresses:** V-002
- **Checklist:** CHECK-B26, CHECK-B02
- **Action:** Pending Decision 2. If adopting validate.sh: set `"testCommand": "bash scripts/validate.sh"`; regenerate `.rauf/RAUF.md`'s `<!-- rauf:managed:start -->…<!-- rauf:managed:end -->` block via rauf's own update path (do **not** hand-edit — L14–L18 and L31 are generated and currently stale/empty); append `"bash scripts/validate.sh passes"` as the last acceptance criterion of all 17 items. Leave every existing AC in place.
- **Depends on:** Decision 2

#### Step 2: Add adapter-regeneration and `--check` criteria to the 13 canon-mutating items
- **Files:** `specs/context-efficiency/backlog.json`
- **Addresses:** V-001
- **Checklist:** CHECK-B26
- **Action:** Pending Decision 1. If option (a): append the two criteria quoted verbatim in V-001 to the `acceptanceCriteria` of items **001, 002, 004, 005, 006, 007, 008, 009, 010, 011, 012, 013, 015** — and only those thirteen. Correct item 001's "stays green" clause per V-001. Amend item 017's description to the final-reconciliation framing; leave its `dependsOn` unchanged (transitively complete). If option (c): append the quoted `notes` sentence to those same 13 items instead.
- **Depends on:** Step 1 (both edit the same 13 `acceptanceCriteria` arrays — apply in one pass to avoid conflicting rewrites)

#### Step 3: Fix item 001's extraction contract (spans, counts, dropped preamble)
- **Files:** `specs/context-efficiency/backlog.json`
- **Addresses:** V-003, V-004, V-006
- **Checklist:** CHECK-B12, CHECK-B13, CHECK-B14
- **Action:** In item `001`: change `L325–478` → `L325–477` in both `description` and `agentDelegation.subtasks[2]`; add the instruction that each of the six mode files must reproduce source L3 and the L5 stack-profile blockquote verbatim under its `# ` title, plus a matching AC; replace `acceptanceCriteria[1]` with the `sort -u` unique-ID form noting the 28/13 raw occurrence counts. Add the preamble assertion as a 6th assertion in item `003`'s guard list.
- **Depends on:** none — **highest urgency: item 001 is the first item the loop executes and all three defects surface in iteration 1**

#### Step 4: Correct the ordering graph
- **Files:** `specs/context-efficiency/backlog.json`
- **Addresses:** V-011, V-012, V-013, V-023
- **Checklist:** CHECK-B05, CHECK-B18, CHECK-B19
- **Action:** Set `"priority": 1` on items **004**, **006**, **010**. Set item **012** `dependsOn` to `["006","008","009","010"]`; item **006** `dependsOn` to `["005","013"]` (Decision 4 may alter this); item **014** `dependsOn` to `["008","009","010"]` with `priority: 1`, and if Decision 5 is yes add `"014"` to 011/012/013's `dependsOn`. Append the rationale sentences from V-012/V-013/V-023 to the corresponding `notes`. Then run the inversion one-liner from V-011 and confirm `inversions: none`.
- **Depends on:** Decisions 4, 5

#### Step 5: Fix item 012's forge-4-backlog prelude instruction
- **Files:** `specs/context-efficiency/backlog.json`
- **Addresses:** V-012
- **Checklist:** CHECK-B18
- **Action:** Replace the forge-4-backlog bullet in item 012's `description` and the corresponding clause in `agentDelegation.subtasks[1]` so that call site **reuses** the prelude item 006 inlines near L32 instead of inlining a second one; subtask 2 must then instruct inlining for `forge-2-tech` only.
- **Depends on:** Step 4

#### Step 6: Schedule the missing REQ-R4-04 touch point
- **Files:** `specs/context-efficiency/backlog.json`
- **Addresses:** V-007
- **Checklist:** CHECK-B08
- **Action:** In item `011`: retitle per V-007; add `"010"` to `dependsOn`; append conversion bullet 6 for `references/stage-exit-protocol.md` L184–192 → `state-decision` (full text in V-007, including the FROZEN-prose constraint and the `BOOTSTRAP_PRELUDE` requirement); append the two ACs; add the provenance note citing `03-state-verbs.md` §11.2 row 5. Bump `estimatedIterations` 2 → 3.
- **Depends on:** Step 4 (both touch item 011's edges)

#### Step 7: Close the two P0 evidence gaps
- **Files:** `specs/context-efficiency/backlog.json`
- **Addresses:** V-008, V-009
- **Checklist:** CHECK-B08
- **Action:** Add the V-008 measurement AC to items `002`, `004`, `006`, `013`, `015` — with §7.4's "do NOT assert a per-stage token figure" constraint verbatim in the `006` and `013` variants. Add the V-009 behavior-preservation AC to items `013` and `015`; promote item `011`'s spec-§9 note to a matching AC scoped to its own PR; add a note to item `017` recording that R1/R3/R5 ride the batch §9 run.
- **Depends on:** none

#### Step 8: Give the shared test helpers an owner
- **Files:** `specs/context-efficiency/backlog.json`
- **Addresses:** V-010
- **Checklist:** CHECK-B21, CHECK-B17, CHECK-B18
- **Action:** Add `tests/_state_schema.py` (with `validate_state` / `validate_effective_config`, per spec `06` §4) as a description bullet plus one AC on item `005`. Add `tests/_forge_paths.py` (per spec `06` §1) plus one AC on item `016`. Cross-reference the validator by exact module path in items `008`, `009`, `010`, `014`.
- **Depends on:** none

#### Step 9: Pin `--status in-progress` semantics
- **Files:** `specs/context-efficiency/backlog.json`, then `specs/context-efficiency/03-state-verbs.md`
- **Addresses:** V-014
- **Checklist:** CHECK-B13
- **Action:** Add the no-`completedAt` / no-version-bump / no-`commitHash`-reset / no-cascade carve-out to item 009's branch 2, and replace `acceptanceCriteria[3]` with the explicit field-level assertion noting schema validation cannot catch this. Propagate to `03-state-verbs.md`.
- **Depends on:** Decision 6

#### Step 10: Name the target file in the three state-verb items
- **Files:** `specs/context-efficiency/backlog.json`
- **Addresses:** V-015
- **Checklist:** CHECK-B14
- **Action:** Prefix items `008`, `009`, `010` descriptions with `scripts/forge-session.py` (and `tests/test_state_verbs.py`), matching item 007's opening style.
- **Depends on:** none

#### Step 11: Fix the two self-contradicting citation criteria
- **Files:** `specs/context-efficiency/backlog.json`
- **Addresses:** V-016, V-017
- **Checklist:** CHECK-B13, CHECK-B08
- **Action:** Rewrite item `002` `acceptanceCriteria[1]` to list six separate literal paths with no brace shorthand. Replace item `013` `acceptanceCriteria[5]` with the combined three-exclusion criterion from V-017 (applying Decision 3), and correct `acceptanceCriteria[2]` + the navigator bullet to `~L205–207` per V-005. Record the `edit-mode.md` exclusion in item 012's notes and `03-state-verbs.md` §11.2's out-of-scope callout.
- **Depends on:** Decision 3

#### Step 12: Resolve the two cap-risk scoping gaps
- **Files:** `specs/context-efficiency/backlog.json`
- **Addresses:** V-019, V-020
- **Checklist:** CHECK-B11, CHECK-B13, CHECK-B25
- **Action:** Apply Decision 4 to item `012` (DEFER branch + deferral-recording AC, or split out `012b`). Add the retry-the-deferred-consumer AC to item `015`, and amend item `006` `acceptanceCriteria[4]` to require the deferral also be appended to `progress.md`.
- **Depends on:** Decision 4, Step 4

#### Step 13: Close item 017's verification holes
- **Files:** `specs/context-efficiency/backlog.json`
- **Addresses:** V-021, V-022, V-025
- **Checklist:** CHECK-B12, CHECK-B13, CHECK-B14
- **Action:** Make step 4 unconditional (update `tests/test_build_adapters.py` L38 to the six-tuple) with a matching AC asserting equality with `scripts/build-adapters.py` L49; replace the "Claude-only tool name" criterion with `pytest tests/test_adapter_host_neutrality.py` plus a glob-coverage check for the new files; quote the exact build invocation and `.venv-adapters` fallback in step 1 and AC 1.
- **Depends on:** Step 2 (both edit item 017)

#### Step 14: De-hardcode item 016's counts and pin its measurements
- **Files:** `specs/context-efficiency/backlog.json`
- **Addresses:** V-018, V-024, V-026, V-027
- **Checklist:** CHECK-B13, CHECK-B14
- **Action:** Replace item 016 `acceptanceCriteria[0..1]` with the baseline-commit + count-free invariant form (V-018), also folding in V-026's durable-evidence requirement for the same string; move "118 on the unmodified repo" into `notes`; amend `description` §4 and `acceptanceCriteria[4]` to define 4688 as the raw quote-**inclusive** sum over 13 files (V-024); state the guard→file mapping (V-027). Separately rewrite item `003` `acceptanceCriteria[1]` per V-026.
- **Depends on:** none

#### Step 15: Re-validate
- **Files:** `specs/context-efficiency/backlog.json` (read-only verification)
- **Addresses:** all
- **Action:** Run `rauf-stable backlog validate . --backlog specs/context-efficiency --specs-dir ./specs --json` → must stay `{"valid": true, "findings": []}`. Confirm: 17 unique ids `001`–`017`; `type` ⊂ `{bug,bugfix,refactor,feature,chore,test}`; every `status` ∈ `{pending,in_progress,done,blocked}`; the inversion one-liner prints `inversions: none`; the graph is still acyclic (Step 6 adds `011 → 010`; verify no cycle with `010 → 007 → 005`). Then re-simulate rauf's dependency-aware priority selection and confirm 001–003 precede 004, 005 precedes 007, 008–010 precede 011/012/013, 013 precedes 006, 006 and 013 precede 015, and 017 is the last non-test item. Expected order with every recommendation applied: `001 002 003 004 005 007 008 009 010 014 011 013 006 012 015 017 016`. Do **not** run `validate-traceability.py` — it cannot parse `REQ-R1-01`-style IDs and emits false noise.
- **Depends on:** Steps 1–14

---

## Fix Progress

All 15 steps applied 2026-07-29 in a single pass, with all six owner decisions resolved beforehand (see "User Decisions — ALL RESOLVED" above).

- Step 1: [APPLIED] 2026-07-29 — V-002. `forge.config.json` `testCommand` → `bash scripts/validate.sh`; `"bash scripts/validate.sh passes"` appended as the final acceptance criterion of all 17 items. **Sub-step dropped as unnecessary:** the plan called for regenerating `.rauf/RAUF.md`'s managed block on the belief it was stale/empty. It is not — `.rauf.json`'s profile already carries `test`/`verify` = `bash scripts/validate.sh`, so the block accurately reflects rauf's profile; the empty Typecheck/Lint/Build lines are `null`-by-design (and `validate.sh` step 7b runs ruff regardless). `rauf update --check` reports only tool-version lag (installed by 0.6.0, current 0.13.0), which is unrelated to these findings and deliberately left alone rather than folded into a verification-fix commit.
- Step 2: [APPLIED] 2026-07-29 — V-001. Two criteria (regenerate `adapters/` in-commit; `build-adapters.py --check` exits 0) appended to the 13 canon-mutating items 001/002/004/005/006/007/008/009/010/011/012/013/015. Item 001's "purely ADDITIVE … suite stays green" premise corrected to note that a skill's own `references/` dir is copied wholesale into all six bundles. Item 017 reframed as the final cross-unit reconciliation sweep. Item 017's `dependsOn` left unchanged — verified transitively complete.
- Step 3: [APPLIED] 2026-07-29 — V-003/V-004/V-006. Item 001 span `L325–478` → `L325–477` in both `description` and `agentDelegation.subtasks[2]`; AC 2 rewritten to `sort -u` unique-ID counting with the 28/13 raw-occurrence caveat; the source L1–6 preamble directives (`Execute EVERY check — do not skip.` + the stack-profile blockquote) added to the extraction contract and to item 003's guard as assertion 6.
- Step 4: [APPLIED] 2026-07-29 — V-011/V-012/V-013/V-023. `priority` 2→1 on items 004, 006, 010, 014. `dependsOn`: 014 → `[008,009,010]`; 006 → `[005,013]`; 011 → `[008,009,010,014]`; 012 → `[006,008,009,010,014]`; 013 → `[002,008,009,014]`. Rationale appended to each item's `notes`. Zero inversions, zero cycles verified.
- Step 5: [APPLIED] 2026-07-29 — V-012. Item 012's forge-4-backlog bullet and `agentDelegation.subtasks[1]` now reuse the prelude item 006 inlines at ~L32 instead of inlining a second one; subtask 2 instructs inlining for `forge-2-tech` only.
- Step 6: [APPLIED] 2026-07-29 — V-007. Item 011 retitled; conversion bullet 6 added for `references/stage-exit-protocol.md`'s deferred-decisions rule → `state-decision`, with the FROZEN-prose constraint and the `test_stage_exit_protocol.py`-stays-green requirement; two ACs added; `estimatedIterations` 2→3.
- Step 7: [APPLIED] 2026-07-29 — V-008/V-009. Per-unit token-measurement AC added to items 002, 004, 006, 013, 015 (with §7.4's no-per-stage-claim caveat on 006 and 013). Behavior-preservation-run AC added to items 013 and 015 with their named §9 reduced substitutes; item 011's §9 note promoted to a scoped AC; item 017's `notes` record that R1/R3/R5 ride the batch run.
- Step 8: [APPLIED] 2026-07-29 — V-010. Item 005 now creates `tests/_state_schema.py` as a named shared module (bullet 5 + AC); item 016 now creates `tests/_forge_paths.py` (description + AC); items 008/009/010/014 cross-reference the validator by exact module path.
- Step 9: [APPLIED] 2026-07-29 — V-014. Item 009's `--status in-progress` carve-out documented; AC 4 replaced with the field-level assertion noting schema validation cannot catch it. Propagated to `03-state-verbs.md`: the reference implementation gained an `elif status == "in-progress"` branch recording only `status`, and the §6.5 L245 bullet now spells out the four suppressed mutations.
- Step 10: [APPLIED] 2026-07-29 — V-015. Items 008, 009, 010 descriptions now name `scripts/forge-session.py` and `tests/test_state_verbs.py` up front.
- Step 11: [APPLIED] 2026-07-29 — V-005/V-016/V-017. Item 002 AC 2 rewritten as six standalone literal citations (no brace enumeration). Item 013's navigator range corrected `~L215–228` → `~L205–207` in both description and AC 3, with the epic-lifecycle disambiguator; AC 6 replaced with the combined schema-read + three-exclusion criterion. `03-state-verbs.md` §11.2's out-of-scope callout expanded from one site to three (navigator `pipelineStatus` at the corrected L205–207, forge-verify `verifyEntry`, forge-0-epic `edit-mode.md` C7).
- Step 12: [APPLIED] 2026-07-29 — V-019/V-020. Item 012 gained the item-006-style DEFER branch for forge-0-epic (Decision 4: no `012b` split). Item 006 AC 5 now requires the deferral in `progress.md` as well as the commit message; item 015 gained the retry-the-deferred-consumer AC.
- Step 13: [APPLIED] 2026-07-29 — V-021/V-022/V-025. Item 017 step 4 made unconditional (six-tuple `AGENT_TARGETS`); step 5 and AC 5 replaced with `pytest tests/test_adapter_host_neutrality.py` plus a glob-coverage check; step 1 now quotes the exact `.venv-adapters` build invocation.
- Step 14: [APPLIED] 2026-07-29 — V-018/V-024/V-026/V-027. Item 016 AC 1 re-anchored to the pre-feature baseline commit `9a29e846ed510c3b245876a9bf4cc73b8cb60951`; AC 2 made count-free; the 4688 ceiling pinned to the quote-inclusive method (4662 explicitly rejected); `_forge_paths.py` ownership and the guard→file mapping stated. Item 003 AC 2 now requires durable mutation-test evidence in the commit message.
- Step 15: [APPLIED] 2026-07-29 — Re-validation. `rauf backlog validate` → `{"valid": true, "findings": []}`. 17 unique ids, types ⊂ enum, all statuses `pending`, zero dangling deps, zero cycles, zero priority inversions. Full `bash scripts/validate.sh` → **All checks passed!**

### Additional fix applied beyond the plan as written

- **Item 003 raised to `priority: 1`.** Simulating rauf's selector after Step 4 showed the documented priority fix had an unintended consequence: with 004/006/010/014 raised to 1, item 003 became the only priority-2 member of the R1 unit and sorted to execution position **16** — roughly 13 items after the R1 work it guards. That breaks R1's contiguity as a revertible unit (REQ-DELIV-01/SC-6) and leaves the checklist split unguarded for most of the run. The "no inversions" invariant held; unit contiguity did not. Raising 003 to priority 1 restores `001 002 003 …` and makes the realized order match this document's predicted order exactly.
- **Item 013 gained a `dependsOn` edge on `002`.** Both items edit `skills/forge-verify/SKILL.md` (002 re-points its citations, 013 converts its Step 6 stamps) with no edge between them. The ordering happened to be safe under both the old and new priorities, but nothing in the graph guaranteed it. Recorded in item 013's `notes`.

**Realized execution order (verified by simulating rauf's dependency-aware priority selection):**

`001 002 003 004 005 007 008 009 010 014 011 013 006 012 015 017 016`

### Residual follow-up (not a finding, not blocking)

`rauf update --check` reports the project's rauf artifacts were installed by `rauf-manager@0.6.0` while the current tool is `0.13.0`. Content is correct and in sync, so this is tool-version lag only. Running `rauf update .` would refresh `RAUF.md` to the 0.13.0 template — worth doing deliberately, on its own commit, not folded into a verification-fix pass.

---

## Re-verify (round 2) and second fix pass — 2026-07-29

A clean-room re-verify was run after the first fix pass (three parallel `forge-verifier` instances over disjoint slices: item-level ACs; dependency graph + adapter/verification strategy; P0 coverage + spec propagation). It returned **27 raw findings, ~20 distinct**. Several were **regressions introduced by the first fix pass** — recorded here plainly, because that is the point of the gate.

### Regressions the first pass introduced (all now fixed)

- **Item 017's host-neutrality AC (found independently by two slices).** The V-022 fix told the agent to confirm the new reference files sit inside `tests/test_adapter_host_neutrality.py`'s globs and to "extend the globs" otherwise. That test *deliberately* skips any path with `references` in its parts (module docstring: bundled reference docs are copied verbatim and may legitimately quote a tool name), and `NON_CLAUDE_TARGETS` excludes `adapters/pi/` because the pi host implements `AskUserQuestion`. Widening either scope goes red immediately on ~25 committed by-design files per target, and `findings-template.md` / `agent-selection.md` inherit an `AskUserQuestion` token from their source spans — so the only way to green was rewording frozen text. **Unsatisfiable AC. Replaced** with a census-equality criterion (the move introduces no *new* token) plus an explicit "do NOT widen either scope".
- **Item 012's "reuse the prelude" instruction.** It contradicted `01-architecture-layout.md` §2.2.1 (which mandates inline ×2 at `forge-4-backlog`, 141 spare lines) and coupled R4's item 012 to R5's item 006 text, breaking REQ-DELIV-01/SC-6 revertibility. The deeper defect it propagated is **pre-existing, not introduced**: `$R` is set inside a fenced block and does not survive to a later fence, yet the specs marked `forge-1-prd` and `forge-6-docs` "reuse — 0". Canon pairs preludes to `$R`-uses **1:1 across every surface, zero exceptions**. **Adopted always-inline** (owner decision) across items 012/013 and both spec documents.
- **The `--status in-progress` carve-out.** Made blanket, but the flag has two opposite callers: `forge-5-loop`'s *partial completion* (§11.2 row 14 — a real completion-with-artifacts that must keep `completedAt`/`version`/`basedOnVersions`/`artifacts`; item 013 passes `--based-on` on that call) and the *failed-Commit-1 revert*. The blanket branch silently discarded those flags. **Split behind a new `--resumable` flag** (owner decision): only `--resumable` records status-only.
- **`tests/_forge_paths.py` owner.** Assigned to item 016, which executes **17th of 17**, while spec 06's code blocks import it from items running 3rd, 4th, 5th, 7th, 10th and 15th — every one would hit `ModuleNotFoundError`. **Moved to item 003** (its first consumer), with `003` added to items 004/005/016's `dependsOn`.
- **Dead baseline path.** `.reference/REMEASURE-0.13.0.md` does not resolve from the repo root; the first pass propagated that shorthand from a note into 5 binding ACs. **Corrected to `specs/context-efficiency/.reference/…` in all 6 occurrences.**
- **Two ACs the first pass never added.** V-021 (the six-tuple `AGENT_TARGETS` assertion) and V-025 (a command-bearing AC 1) had their descriptions updated but not their criteria. **Both added.**

### Findings the re-verify surfaced that predated the fix pass

- **Item 013's census AC was still unsatisfiable**, for a new reason: it ran a repo-wide grep at a point where item 012's five authoring bodies were still unconverted. **Re-scoped**; the repo-wide census now lives on R4's genuinely-last conversion.
- **Two more hand-authoring sites exist** that no verb can convert: `skills/forge-fix/SKILL.md` Step 5 (`verifyEntry` class, same as the already-sanctioned `forge-verify` Step 6) and `skills/forge-0-epic/references/edit-mode.md`'s ECR `open`→`applied` flip (mutates an existing array item; `state-ecr` only appends). **Documented as exclusions** (owner decision), taking the ledger from three sites to **five**.
- **Item 012 had no §9 behavior-preservation AC** despite being R4's largest PR (five authoring bodies carrying three of §9's seven surfaces). **Added.**
- **The batch §9 run was note-only, not a binding AC** — the same defect the original V-009 rejected. **Added as an AC on item 017.**
- **Declared sequencing no longer matched reality.** `backlog.json`'s `description` and tech-spec §3.7 still asserted `R1+R3 → R5 → R4 → R6`. **Both amended** to record the deliberate R5 split.

### Ordering correction discovered during this pass

Removing item 012's coupling to 006 changed the realized order so that **012 now runs before 013**, making 013 — not 012 — R4's last conversion. The repo-wide census and the R4 token-measurement AC had just been placed on 012 on the opposite assumption. Both were **relocated to 013**, and `013 → 012` was added to `dependsOn` so the ordering is pinned by the graph rather than by a priority tie-break.

### Deliberately not fixed (owner scoped this pass to blocking + correctness)

- Item 001's cross-reference enumeration names `CHECK-I21/I22` where the duplicated ids are actually `I01`×2, `I11`×2, `I21`×3, `I22`×2. The operative counts (28/13/130) are correct and the AC is achievable; only the parenthetical is imprecise.
- Item 001's title / preamble / shared-directives ordering is unspecified, so three parallel sub-agents may lay the six files out inconsistently.
- Item 015 AC 6 misattributes *why* `agent-selection.md` reaches the bundles (it ships via the wholesale `references/` copy, not via citation fan-out). The citation is still required, by REQ-PORT-01 and item 016's reverse guard.

### Realized execution order after the second fix pass

`001 002 003 004 005 007 008 009 010 014 011 012 013 006 015 017 016`

Zero priority inversions, zero cycles, zero dangling deps, no deadlock. `rauf backlog validate` → `{"valid": true, "findings": []}`. Full `bash scripts/validate.sh` → **All checks passed!** (including the `build-adapters.py --check` drift gate).
