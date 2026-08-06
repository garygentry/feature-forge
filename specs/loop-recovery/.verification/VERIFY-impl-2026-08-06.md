# Verification Report: loop-recovery (impl)

Date: 2026-08-06
Pipeline Stage: forge-5-loop (complete — all 10 backlog items `done`)
Mode: impl
Dispatch: 5 parallel `forge-verifier` instances (dimensioned fan-out), owner `nested`

Artifacts Reviewed: `specs/loop-recovery/{PRD.md, tech-spec.md, 00–07 *.md, TRACEABILITY.md, backlog.json}`; `scripts/forge-session.py` (decision verbs, `cluster_blocked`, `compute_topology`, `_max_chain_depth`, `--cause`, `LoopOutcome`/`resolved` routing, topology/threshold constants); `references/forge-decisions-schema.json`; `skills/forge-5-loop/{SKILL.md, references/recovery-procedure.md, result-reporting.md, runner-contract.md}`; `skills/forge-verify/references/verification-checklists/backlog.md`; `skills/forge-4-backlog/SKILL.md`; `eval/run-compliance-eval.py`, `eval/fixtures/compliance/loop-outcome-resolved.json`; `tests/*`; `forge.config.json`; `AGENTS.md`, project `CLAUDE.md`; cross-repo `/home/gary/workspace/rauf` `packages/cli/src/{backlog-commands.ts, commands.ts, backlog-commands.test.ts}` (item 008).

Checks Executed: **23 of 23** (CHECK-I01–I23). Results: **22 pass, 0 fail, 1 not-applicable** (I23 — no framework universal-bootstrap entry in a stdlib Python CLI).

## Summary
- Total findings: **2**
- Errors: 0
- Gaps: 0
- Inconsistencies: 1
- Improvements: 1

**This report is advisory-only** — it contains no blocking (`error`/`gap`) finding. Per the forge-verify severity/routing rules it records `passed` with the report attached; it fences no forge-fix round. The two advisories remain discoverable here for whoever next touches these artifacts.

### Per-dimension roll-up

| Dimension | Checks | Result | Findings |
|---|---|---|---|
| (1) Requirement coverage vs specs | I01–I07 | 7 pass | none |
| (2) Integration correctness | I08–I12 | 5 pass (`ruff check scripts/ eval/` → all passed) | none |
| (3) Testing | I16–I17 | 2 pass (`bash scripts/validate.sh` exit 0: 1909 passed, 2 skipped) | none |
| (4) Code quality & docs | I13–I15, I18–I20 | 6 pass | V-002 (improvement) |
| (5) Runnability | I21–I23 | 2 pass, I23 n/a (smoke `doctor --json` exit 0) | V-001 (inconsistency) |

Notable positives verified live (not just read):
- **V-012 (carried tech advisory) resolved and robust:** `test_loop_accepts_exactly_the_six_loop_outcomes` (renamed from `_five_`); no `five` literal survives. Parametrized over the derived 6-member `EXIT_OUTCOMES["forge-5-loop"]`, backed by the protocol tripwire that asserts every outcome is documented in the SKILL body. The guard guards.
- **V-015 (carried tech advisory) resolved and robust:** the three incident `blockedReason` strings are vendored verbatim into `test_decision_clustering.py`; the brittle ~0.028 Jaccard margin is pinned structurally (`0.52 < binding < 0.54` and `binding − CLUSTER_JACCARD_THRESHOLD < 0.03`), not just in a comment.
- **Item 007 topology contract** matches across producer (`compute_topology`) and all three consumers (forge-4 report, forge-verify CHECK-B28, forge-5 Step 2a); warning enum literals `single-root-fanout`/`chain-depth` agree; lifecycle count `28` is lockstep (no split-brain).
- **Item 008** rauf `backlog answer` correctly lives in the separate `rauf` repo (separate release train, per 01 §1.5) — verified present, not a gap.

---

## Findings

### V-001: Effective `smokeCommand` contradicts the repo's documented null-by-design convention
- **Severity:** inconsistency (advisory — the configured command runs and passes at exit 0)
- **Location:** `forge.config.json` (`"smokeCommand": "python3 scripts/forge-session.py doctor --json"`) vs `AGENTS.md` §"Verification conventions" and the project `CLAUDE.md` "Repo conventions" note.
- **What's wrong:** The effective config **sets** a `smokeCommand`, but two authoritative in-repo sources state it is **null by design** (owner decision 2026-07-29, V-013 of the context-efficiency impl verify) and that CHECK-I21 is `not-applicable` on this repo — CLAUDE.md even says "do not recommend configuring one." The three sources disagree on which is authoritative. Behavioral consequence: every future impl-verify of this repo now **runs** a smoke where the documented convention says it should skip — a gate-behavior contradiction, not merely stale prose. CHECK-I21 itself passed cleanly (`doctor --json` → exit 0, valid health JSON with `pluginRoot.resolved=true`, 6 active features), so this is advisory, not blocking.
- **Suggested fix (owner decision required — do NOT auto-resolve):** Either **(a)** if the `smokeCommand` was intentionally adopted (revisiting the 2026-07-29 decision — `doctor --json` is a legitimate, non-fabricated health smoke), edit `AGENTS.md` §"Verification conventions" + the project `CLAUDE.md` note to say CHECK-I21 now executes `python3 scripts/forge-session.py doctor --json` (exit-0 = pass) here, removing the null-by-design / not-applicable / "do not configure one" language; **or (b)** if the config value is an accidental dogfood-run artifact, revert `forge.config.json` to `"smokeCommand": null`. Do not partially apply — config and both docs must end in agreement.
- **References:** `forge.config.json`; `AGENTS.md` §"Verification conventions"; project `CLAUDE.md` "Repo conventions"; context-efficiency impl-verify V-013.
- **Checklist:** CHECK-I21

### V-002: `recovery-procedure.md` §7 uses bare `(03)/(04)/(06)` spec back-references a bundle reader cannot resolve
- **Severity:** improvement (advisory)
- **Location:** `skills/forge-5-loop/references/recovery-procedure.md`, §7 "Report citations (REQ-OBS-01)" — the "This table is carried from the feature's master citation-basis contract" sentence and the "Report surface" column tags `(03)`, `(04)`, `(06)`.
- **What's wrong:** Unlike the rest of feature-forge's shipped canon, which cites spec files by full name (e.g. `references/loop-agent-selection.py` writes `04-availability-precheck.md`), this table uses bare parenthesized numbers with no legend. A reader of the forge-5-loop bundle — where `03-outcome-and-attribution.md`, `04-apply-and-unblock.md`, `06-clustering-and-topology.md` do not ship — cannot tell what `(03)` points at. The "carried from the feature's master citation-basis contract" sentence is pure spec-provenance framing and mildly contradicts the self-containment rule this same feature added at `SKILL.md:302`. Clarity/self-containment only — the substantive content (which authoritative source each report surface cites) is correct and worth keeping.
- **Suggested fix:** Drop the three bare `(03)`/`(04)`/`(06)` tags from the "Report surface" column (the surfaces are already named in prose), and reword the intro sentence to something self-contained (e.g. "Every report surface names the authoritative source it derives its claims from:"). Keep the "Authoritative citation basis" column and the `REQ-OBS-01` heading tag (REQ-id tags match established repo convention). If canon is edited, regenerate adapters (`python3 scripts/build-adapters.py`) and run `bash scripts/validate.sh` so the `adapters/*/.../recovery-procedure.md` copies stay in sync (the drift guard will otherwise block).
- **References:** `SKILL.md:302` (self-containment rule); `references/loop-agent-selection.py` (full-filename citation style); `specs/AGENTS.md` "Read freely; reference deliberately".
- **Checklist:** CHECK-I18, CHECK-I20

> **Spec-citation convention — checked, explicitly NOT a finding.** The new code docstrings cite REQ-ids (`REQ-TOPO-01`, etc.) and `decision V-007`. This is a pervasive pre-existing in-repo convention (`git show main:scripts/forge-session.py` already carries 72 such citations), and feature-forge is self-hosted: the "implementation artifacts must not cite specs" rule the loop emits is for **external** target repos, not this project's own internal traceability. Flagging these would be a false positive.

---

## Fix Execution Plan

Both findings are **advisory**; neither blocks the pipeline. No fix pass is required to advance to forge-6-docs. The steps below are optional cleanups.

### User Decisions Required
- **V-001:** Owner must decide whether the repo's `smokeCommand` is intentionally set (`doctor --json`) or should return to `null`. This reverses the documented 2026-07-29 owner decision (V-013), so it is not a mechanical fix.

### Execution Steps (optional)

#### Step 1: Reconcile `smokeCommand` config with documented convention (V-001)
- **Files:** `forge.config.json`, `AGENTS.md`, project `CLAUDE.md`
- **Action:** After the owner decision — either (a) keep the config value and update both docs to describe CHECK-I21 running `doctor --json` here (removing null-by-design language), or (b) set `smokeCommand` back to `null` and leave the docs. Do not partially apply — config and both docs must agree.
- **Depends on:** owner decision above.

#### Step 2: Self-contain `recovery-procedure.md` §7 citation table (V-002)
- **Files:** `skills/forge-5-loop/references/recovery-procedure.md` (+ regenerate adapters)
- **Action:** Remove the `(03)/(04)/(06)` suffixes from the "Report surface" cells and reword the intro sentence to a self-contained lead-in. Keep the "Authoritative citation basis" column and `REQ-OBS-01` heading. Run `python3 scripts/build-adapters.py` then `bash scripts/validate.sh`.
- **Depends on:** none.
