# Verification Findings — forge-bootstrap (tech mode)

- **Feature:** forge-bootstrap
- **Mode:** tech
- **Date:** 2026-06-18
- **Artifacts verified:** `PRD.md` (v1), `tech-spec.md` (v1)
- **Checks executed:** 17 of 17 (CHECK-T01..T17) — **11 pass, 6 fail, 0 n/a**
- **Findings:** 6 (2 gap, 1 error, 1 inconsistency, 1 gap, 1 improvement → see below)
- **Dispatch:** single `forge-verifier` (small mode), parent-assembled.

> Intentionally excluded from findings (not defects): carry-forward open
> technical questions **OQ-T1 / OQ-T2 / OQ-T3** (deferred by design), and
> **REQ-PERF-01**'s deliberate non-quantification.

---

## Findings

### V-001 — Completion output / observability has no tech decision (gap)
- **Severity:** gap
- **Location:** `tech-spec.md` — missing coverage; relates to `PRD.md` §3.9 (REQ-OUT-01, REQ-OUT-02) and §4.3 (REQ-OBS-01).
- **What's wrong:** REQ-OUT-01 (P0) requires the success path to print a structured summary — what was created, resolved stack(s), verification result (green/unverified), and the exact next command. REQ-OBS-01 (P1) requires *all* terminal outcomes (success, greenfield refusal, missing toolchain, partial-state detection) to be explicit and actionable. The tech spec describes the helper's JSON/exit-code surface (§5, §7) but never specifies **who renders the human-facing completion summary** or its shape. The summary is a skill-body responsibility (the helper emits JSON), but §3 / §6 never assign it.
- **Suggested fix:** Add a short subsection (e.g. §3.9 "Completion summary & terminal outcomes") stating that the **skill body** renders the human-facing summary from the helper's JSON: on success it prints created artifacts, resolved stack(s), the green/unverified verification verdict, and the literal next command (`forge-1-prd <feature>` / `forge-0-epic <epic>` in Mode A, or the launched stage in Mode B per REQ-OUT-02). Cross-list the four REQ-OBS-01 terminal outcomes and map each to its source (gate refusal → §7 `check`; missing toolchain → §7 `verify`; partial-state → §3.4 sentinel; success → REQ-OUT-01).
- **References:** PRD.md §3.9, §4.3; tech-spec.md §5, §7.
- **Checklist:** CHECK-T01 (requirement coverage), CHECK-T12 (observability).

### V-002 — §6 references a non-existent hook file (error)
- **Severity:** error
- **Location:** `tech-spec.md` §6 Integration Points — row `hooks/session-check.sh`.
- **What's wrong:** The integration table cites `hooks/session-check.sh` as the unaffected hook. No such file exists; the real hook config is `hooks/hooks.json`. §2 already correctly names `hooks/hooks.json` ("No edits needed to … `hooks/hooks.json`"), so §6 is internally inconsistent and factually wrong.
- **Suggested fix:** Change the §6 row target from `hooks/session-check.sh` to `hooks/hooks.json` (or the actual hook script it dispatches, if one is intended). Keep the "unaffected / operates pre-config / exits 0 when no config/specs" note. Verify the path against the repo before finalizing.
- **References:** tech-spec.md §2 (line ~53), §6 (line ~210); repo `hooks/hooks.json`.
- **Checklist:** CHECK-T07 (integration-point accuracy), CHECK-T14 (path/signature verification).

### V-003 — "Source of truth" claim contradicts the profiles' actual content (inconsistency)
- **Severity:** inconsistency
- **Location:** `tech-spec.md` §3.5 and §6 (row `references/stacks/*.md` — "source of truth").
- **What's wrong:** §3.5/§6 assert that `references/stacks/*.md` are the canonical source of truth for verification commands, yet the chosen commands diverge from those profiles: the TypeScript profile endorses **Vitest**, but §3.5 writes `node --test`; and `_generic.md` provides **no concrete command** for §3.5's generic row (`sh -n` / `./test.sh` are invented here, not sourced). Calling the profiles canonical while overriding them is contradictory and will confuse a fresh implementer about which wins.
- **Suggested fix:** Soften the framing: state the stack profiles are the **default/reference** verification commands, and that forge-bootstrap MAY deviate to keep the green baseline minimal-dependency, documenting each deviation. Explicitly note (a) TS uses `node --test` instead of the profile's Vitest to avoid a heavyweight dev-dep (tie to OQ-T2), and (b) the generic commands are bootstrap-defined because `_generic.md` specifies none. Alternatively, reconcile by updating the chosen commands to match the profiles — but the deviation appears intentional, so documenting it is preferred.
- **References:** tech-spec.md §3.5, §3.6, §6, §10 OQ-T2; `references/stacks/typescript.md`, `references/stacks/_generic.md`.
- **Checklist:** CHECK-T05 (internal consistency), CHECK-T08 (source-of-truth alignment).

### V-004 — "Equivalent to forge-init" omits forge-init's actual field set (gap)
- **Severity:** gap
- **Location:** `tech-spec.md` §3.3 (REQ-CFG-02 equivalence).
- **What's wrong:** §3.3 claims the helper "reuses forge-init's exact field set + defaults" but the spec only discusses `stack`/`typeCheckCommand`/`testCommand`/`loopRunner`. forge-init (`scripts/forge-init.sh`) actually writes: `specsDir` (`./specs`), `docsDir` (`./docs/architecture`), `backlogDir` (`null`), `gitCommitAfterStage` (`true`), `commitPrefix` (`forge`), `stack`/`typeCheckCommand`/`testCommand` (`null`), and `loopIterationMultiplier` (`1.5`). The four-plus fields `docsDir`, `backlogDir`, `gitCommitAfterStage`, `commitPrefix`, `loopIterationMultiplier` are never named, so "equivalent" is unverifiable and an implementer could drop them.
- **Suggested fix:** In §3.3, enumerate the full forge-init field set the helper must reproduce: `specsDir`, `docsDir`, `backlogDir`, `gitCommitAfterStage`, `commitPrefix`, `loopIterationMultiplier`, plus the resolved `stack`/`typeCheckCommand`/`testCommand` and the minimal `loopRunner` block. State that bootstrap matches forge-init's defaults byte-for-byte except for the resolved stack/command values and the explicit `loopRunner`. Add this as an assertion in the §8 "Config equivalence" test.
- **References:** tech-spec.md §3.3, §8; PRD.md §3.7 (REQ-CFG-01/02/03); `scripts/forge-init.sh` lines 16–24.
- **Checklist:** CHECK-T01 (requirement coverage), CHECK-T06 (config/contract completeness).

### V-005 — P0 interview inputs only implied via the sentinel shape (gap)
- **Severity:** gap
- **Location:** `tech-spec.md` §3.7, §4 (sentinel `answers`); relates to `PRD.md` §3.1 (REQ-INPUT-01/02/03/06).
- **What's wrong:** REQ-INPUT-01 (project name), -02 (purpose), -03 (stack), and -06 (single vs monorepo) are core interview inputs, but the tech spec only surfaces them implicitly through the sentinel `answers` JSON example (§4) and the §3.7 fallback note. There is no explicit statement of the question set, defaults (e.g. REQ-INPUT-01 infers the name from the directory; REQ-INPUT-02 seeds README), or that the skill body owns them. A fresh implementer cannot derive the questions, ordering, or default-seeding rules from the current spec.
- **Suggested fix:** Add a §3 subsection (or extend §3.7) that lists the interview question set with each question's source REQ-INPUT id, its default/seed rule (name ← directory; purpose → README seed; package-manager asked only when stack has alternatives per REQ-INPUT-04; Mode B feature-vs-epic only in Mode B per REQ-INPUT-07), and a statement that the skill body owns the question set (consistent with §3.7's "question SET is owned by the skill body"). This makes REQ-INPUT-01/02/03/06 explicitly traceable.
- **References:** tech-spec.md §3.7, §4; PRD.md §3.1 (REQ-INPUT-01..08).
- **Checklist:** CHECK-T01 (requirement coverage), CHECK-T03 (input handling).

### V-006 — Range citations hide several requirements; monorepo CI unaddressed (improvement)
- **Severity:** improvement
- **Location:** `tech-spec.md` §2 helper API table (range citations like `REQ-MONO-01..04`, `REQ-SCAF-01..09`), §3.2, §3.8.
- **What's wrong:** Range citations (`REQ-MONO-01..04`, `REQ-MODEB-01..04`) make it impossible to confirm each member is individually covered. In particular **REQ-MONO-04** (when CI is enabled for a monorepo, CI MUST run lint+test for *all* members) has **no concrete generation decision** anywhere in the spec — CI scaffolding is mentioned only as the `ci` answer flag (§4) with no design for what file is emitted or how per-member lint/test is wired. REQ-MONO-02 (mixed-language members) and -03 (per-member entrypoint + test) are asserted in §3.2/§8 but not called out by id. REQ-MODEB-01/02 are covered in §3.8 but buried in a range.
- **Suggested fix:** (1) Add an explicit decision for **REQ-MONO-04**: what CI artifact is scaffolded (e.g. a GitHub Actions workflow under `.github/workflows/`), and that it iterates `workspaces[]` running each member's resolved lint+test — or, if CI generation is deferred, say so explicitly and reconcile with the P-level. (2) Replace range citations in the §2 table with per-id coverage (or add a short traceability note) so REQ-MONO-02/03 and REQ-MODEB-01/02 are individually visible. (3) Add a §8 monorepo-CI test if CI generation is in scope.
- **References:** tech-spec.md §2, §3.2, §3.8, §8; PRD.md §3.6 (REQ-MONO-01..05), §3.8 (REQ-MODEB-01..04).
- **Checklist:** CHECK-T01 (requirement coverage), CHECK-T02 (traceability granularity).

---

## Fix Execution Plan

A fresh agent can apply these in order; later steps depend on earlier wording.

**Step 1 — Correct the factual error (V-002).**
In `tech-spec.md` §6, change the `hooks/session-check.sh` row to `hooks/hooks.json` (verify the path in the repo first). No dependencies; do this first.

**Step 2 — Complete config equivalence (V-004).**
In §3.3, enumerate the full forge-init field set (`specsDir`, `docsDir`, `backlogDir`, `gitCommitAfterStage`, `commitPrefix`, `loopIterationMultiplier`, + resolved stack/commands + minimal `loopRunner`). Mirror the new assertion into the §8 "Config equivalence" bullet.

**Step 3 — Reconcile the stack-profile source-of-truth claim (V-003).**
In §3.5/§6, reframe `references/stacks/*.md` as default/reference (not absolute canonical) and document the TS (`node --test` vs Vitest, link OQ-T2) and generic (bootstrap-defined, `_generic.md` has none) deviations.

**Step 4 — Make interview inputs explicit (V-005).**
Add a §3 subsection listing the interview question set mapped to REQ-INPUT-01..08 with default/seed rules and skill-body ownership.

**Step 5 — Add completion-output / observability decision (V-001).**
Add §3.9 "Completion summary & terminal outcomes": skill renders the success summary from helper JSON (REQ-OUT-01), Mode B launches instead (REQ-OUT-02), and map the four REQ-OBS-01 terminal outcomes to their sources.

**Step 6 — Tighten monorepo/Mode-B traceability and decide REQ-MONO-04 (V-006).**
Add an explicit REQ-MONO-04 CI-generation decision (or an explicit deferral with rationale), replace range citations in §2 with per-id coverage, and add a §8 monorepo-CI test if CI generation is in scope.

**User decisions required before applying:**
- **V-006 / REQ-MONO-04:** Is monorepo CI generation in-scope for this feature, or deferred? — **RESOLVED 2026-06-18: IN SCOPE.** Add an explicit CI-generation decision (scaffold a `.github/workflows` artifact iterating `workspaces[]` for per-member lint+test) plus a §8 monorepo-CI test.
- **V-003:** Confirm the intentional TS `node --test` deviation from the Vitest profile is desired (vs. matching the profile). — **RESOLVED 2026-06-18: MATCH THE PROFILE.** Change §3.5 TS `testCommand` to Vitest per `references/stacks/typescript.md`; update §9 dependency note and OQ-T2 accordingly; generic commands remain bootstrap-defined (`_generic.md` specifies none).

## Fix Progress

- Step 1 (V-002): [APPLIED] 2026-06-18 — §6 hook row corrected `hooks/session-check.sh` → `hooks/hooks.json`.
- Step 2 (V-004): [APPLIED] 2026-06-18 — §3.3 now enumerates forge-init's full field set + defaults table; §8 config-equivalence assertion expanded.
- Step 3 (V-003): [APPLIED] 2026-06-18 — per decision, TS testCommand changed to Vitest (`vitest run`) matching the profile; §9 dep note + OQ-T2 updated; generic noted bootstrap-defined.
- Step 4 (V-005): [APPLIED] 2026-06-18 — new §3.9 interview question set mapping REQ-INPUT-01..08 with default/seed rules and skill-body ownership.
- Step 5 (V-001): [APPLIED] 2026-06-18 — new §3.10 completion summary + terminal-outcomes table (REQ-OUT-01/02, REQ-OBS-01).
- Step 6 (V-006): [APPLIED] 2026-06-18 — REQ-MONO-04 in scope: new §3.11 monorepo CI generation, ci/ template added to §2, per-id MONO citation, §8 monorepo-CI + REQ-MONO-03 tests.
