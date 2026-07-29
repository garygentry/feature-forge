# Verification Report: context-efficiency (specs)
Date: 2026-07-29
Pipeline Stage: forge-4-backlog (entry-stamped; this gate ran before spec loading)
Artifacts Reviewed: `PRD.md`, `tech-spec.md`, `TRACEABILITY.md`, `00-core-definitions.md`, `01-architecture-layout.md`, `02-verify-checklist-split.md`, `03-state-verbs.md`, `04-effective-config.md`, `05-instruction-relocations.md`, `06-testing-strategy.md`, plus the live repo surfaces they cite (`skills/`, `references/`, `scripts/`, `hooks/`, `tests/`, `adapters/`)

**Method:** parallel dimensioned fan-out, five `forge-verifier` instances (types/contracts · architecture/layout · cross-reference & traceability · testing strategy · integration). **Executed 38 of 38 checks. Results: 14 pass, 23 fail, 1 not-applicable.** 50 raw findings deduped to 36. The verifiers were deliberately *not* told that R2 had been scoped out — whether the artifacts communicate that on their own was a hypothesis under test. It failed; see V-001.

> **The deterministic traceability validator did not cover this feature.**
> `scripts/validate-traceability.py` uses `REQ_PATTERN = re.compile(r"REQ-[A-Z]+-\d+")`. `[A-Z]+`
> cannot match a digit, so all **17** R-numbered requirements (`REQ-R1-01` … `REQ-R6-03`) are
> invisible to it. It saw 12 of 29 IDs and reported `uncovered_requirements: []` — a false
> all-clear over precisely the requirements carrying this feature's entire functional scope.
> The matrix below was therefore built by hand. **This is a feature-forge tooling defect, not a
> defect in these specs**, and it is filed separately (see "Tooling defect" at the end).

## Summary
- Total findings: 36
- Gaps: 11
- Inconsistencies: 8
- Improvements: 3
- Errors: 14

**Three findings block backlog authoring** (V-001, V-002, V-004) — each would cause the backlog to schedule work that must not be built, or to omit work REQ-R4-04 requires. **Three more would land red on CI on day one** (V-003, V-027, V-030).

## Traceability matrix (29 of 29 PRD requirements, built by hand)

| REQ ID | Pri | Implementing spec → section |
|---|---|---|
| REQ-BEHAV-01 | P0 | `00` §2, §10 · `03` §13, §13.1 · `05` §1.6/§2.4/§3.7 |
| REQ-BEHAV-02 | P0 | `00` §10 · `03` §6.5, §13.2 · `04` §7 · `05` invariants |
| REQ-CTX-01 | — | **deliberately uncovered** — `TRACEABILITY.md` Coverage Notes: it appears only in PRD §6 as the rationale for excluding W1; it is an *epic-orchestration* requirement |
| REQ-DELIV-01 | P0 | `01` §4, §5 — **defective, V-017** |
| REQ-MAINT-01 | P0 | `06` §3–§5 · `01` §6 · `02` §9 · `03` §12 · `04` §9 · `05` §1.6/§2.4/§3.7 |
| REQ-OBS-01 | P0 | `06` §7.1, §7.2 — **stale, V-034** |
| REQ-OBS-02 | P1 | `06` §7.4 — **stale, V-034** |
| REQ-PERF-01 | P0 | `06` §7.5, §7 |
| REQ-PERF-02 | P0 | `06` §7.3 — **vacuous, V-007 / V-008** |
| REQ-PORT-01 | P0 | `00` §9 · `01` §3.1 · `02` §8 · `04` §7 · `05` §2.3/§3.5 · `06` §5 |
| REQ-PORT-02 | P0 | `00` §9 · `02` §8 · `04` §7 · `05` §2.3/§3.6 |
| REQ-PORT-03 | P0 | `00` §9 · `01` §6 · `02` §8 · `06` §6 — **undercounts adapters, V-032** |
| REQ-R1-01 | P0 | `02` §2, §3, §6 |
| REQ-R1-02 | P0 | `02` §3, §5, §7.4 · `00` §7 |
| REQ-R1-03 | P0 | `02` §3, §6 |
| REQ-R1-04 | P0 | `02` §7.3 · `00` §7 · `06` §3.1 |
| REQ-R1-05 | P0 | `02` §2/§2.1, §4, §9 · `00` §7 · `06` §3.1 |
| REQ-R2-01 | P1 | **deliberately not implemented** (PRD §3.2); analysis retained in `05` §1.1/§1.3–§1.5 · `00` §8 |
| REQ-R2-02 | P0 | **deliberately not implemented** (PRD §3.2); `05` §1.2/§1.5/§1.6 · `00` §8 |
| REQ-R3-01 | P1 | `05` §2.1–§2.4 · `06` §3.3 |
| REQ-R4-01 | P0 | `03` §2, §4–§10 · `00` §3, §5 |
| REQ-R4-02 | P0 | `03` §2, §3 |
| REQ-R4-03 | P1 | `03` §3.4, §12 · `00` §4 · `04` §9 · `06` §4 |
| REQ-R4-04 | P0 | `03` §4–§10, §11.2 · `00` §5 · `01` §1 — **incomplete, V-004** |
| REQ-R5-01 | P0 | `04` §2–§4, §7 · `00` §6 |
| REQ-R5-02 | P1 | `04` §3, §4, §5, §8 |
| REQ-R6-01 | P0 | `05` §3.1, §3.2 · `06` §3.6 |
| REQ-R6-02 | P0 | `05` §3.2, §3.3 · `06` §3.6 — **defective, V-018** |
| REQ-R6-03 | P0 | `05` §3.4 · `01` §2.2 · `04` §7 |

No requirement is uncovered. Every failure above is a defect *within* covering material, not an absence of it.

## Findings

### V-001: The R2 scope-out reached 4 of 10 spec documents; the other 6 still schedule R2 work
- **Severity:** inconsistency
- **Location:** `tech-spec.md` §1, §2, §3.2, §3.7, §8; `00-core-definitions.md` §8, §10 (R2 invariant row), Verification checklist; `01-architecture-layout.md` §1, §4, §5; `06-testing-strategy.md` §3.2, §7.5; `02-verify-checklist-split.md`; `03-state-verbs.md`; `04-effective-config.md`
- **Issue:** PRD §3.2 is explicit — *"author no backlog items for them."* The 2026-07-28 scope-out edited `PRD.md`, `TRACEABILITY.md`, `05-instruction-relocations.md`, and `01-architecture-layout.md` §2.2 only. Measured marker coverage across the suite:

  | Document | R2 mentions | scope-out markers |
  |---|---|---|
  | `tech-spec.md` | 12 | **0** |
  | `00-core-definitions.md` | 8 | **0** |
  | `06-testing-strategy.md` | 3 | **0** |
  | `02-verify-checklist-split.md` | 3 | **0** |
  | `03-state-verbs.md` | 1 | **0** |
  | `04-effective-config.md` | 1 | **0** |
  | `01-architecture-layout.md` | 20 | 1 (§2.2 only) |
  | `05-instruction-relocations.md` | 26 | 3 |
  | `PRD.md` | 8 | 2 |
  | `TRACEABILITY.md` | 5 | 1 |

  Concretely, a backlog author reading these documents would schedule R2 work: `tech-spec` §1 says the feature "ships as **six** independently revertible units (R1–R6)", §3.2 is an undecorated R2 decision, §3.7 sequences "R1 + R2 + R3", §8 specifies an R2 test. `06` §3.2 specifies `tests/test_prelude_dedup.py` in full (a test that is red by construction — on-disk prelude counts are forge 5 / forge-0-epic 5 / forge-bootstrap 4 / forge-1-prd 2 and will not change), and §7.5's acceptance table still carries an R2 row. `01` §1 lists `skills/forge-bootstrap/SKILL.md M R2 (4 → 1 + 3)` and `tests/test_prelude_dedup.py N`, §4 keeps a full R2 revert row, §5's diagram keeps R2 in the quick-wins bracket — **while §2.2 of the same document states `forge-bootstrap/SKILL.md` is "untouched by this feature."** A document contradicting itself on the same file is the sharpest form of this defect.

  **This is the hypothesis that failed.** The scope-out was implemented as banners plus struck traceability rows specifically so `forge-verify` would read a deliberate exclusion rather than a coverage gap. Where a banner exists, that worked perfectly — all five verifiers correctly classified REQ-R2-01/02 as deliberately excluded, and none reported a coverage gap. The mechanism is sound; the application was partial.
- **Suggested fix:** Apply the treatment `05` and `TRACEABILITY` already use — retain the analysis, mark it non-shipping. (1) `tech-spec.md` §1: "six" → "five shipping units (R1, R3–R6); R2 is retained for provenance, see PRD §3.2"; add a `> **SCOPED OUT (2026-07-28)**` blockquote at the head of §3.2; drop R2 from §3.7's sequence and §8's test list. (2) `06-testing-strategy.md`: same blockquote at the head of §3.2, replacing the test block with "No `tests/test_prelude_dedup.py` is authored"; strike the R2 row from §7.5. (3) `01-architecture-layout.md`: strike the `R2 (…)` annotations in §1, remove the `skills/forge-bootstrap/SKILL.md` row entirely (§2.2 says it is untouched), strike `tests/test_prelude_dedup.py`; delete §4's R2 revert row; remove R2 from §5's diagram and rewrite the prose as "R1/R3 can land in any order among themselves"; promote §2.2's blockquote to a document-level banner under the title. (4) `00-core-definitions.md`: banner at §8, strike §10's R2 invariant row and the compact-prelude Verification box.
- **References:** `PRD.md` §3.2; `05-instruction-relocations.md` preamble (the template to copy); `01-architecture-layout.md` §2.2
- **Checklist:** CHECK-S04, CHECK-S06, CHECK-S08, CHECK-S16, CHECK-S34, CHECK-S36

### V-002: R4 and R5 call sites are specified in terms of the R2 compact prelude, which will not exist — and the pointer dangles in 5 of 7 target skills
- **Severity:** gap
- **Location:** `04-effective-config.md` §7 ("After (both SKILL bodies)"); `03-state-verbs.md` §11.2 (closing caveat) and §13.1 (worked After block); `00-core-definitions.md` §8
- **Issue:** Every new fenced call the specs insert is written using R2's compact prelude form:
  - `04` §7: *"Resolve `$R` via the plugin-root prelude shown at the top of this skill (**the R2 compact-prelude form**, 00-core-definitions §8), then run: `python3 "$R/scripts/forge-session.py" effective-config …`"*
  - `03` §11.2: *"the **compact-prelude form** the fenced calls use [is] owned by … `05-instruction-relocations.md` (the R2 prelude form)"*

  With R2 dropped, no compact form exists, and `00` §8 still presents it as live canon with no marker. Worse, the "shown at the top of this skill" pointer is factually wrong in almost every target — verified prelude positions against call sites:

  | Skill | Only prelude at | R4/R5 call site | Pointer valid? |
  |---|---|---|---|
  | `forge-5-loop` | L64 | L22–27 (R5) | **No** — prelude is 40 lines below |
  | `forge-4-backlog` | L154 | L32 (R5), L139 (R4) | **No** — both above |
  | `forge-2-tech` | L203 | L189 (R4) | **No** |
  | `forge-3-specs` | L155 | L141 (R4) | **No** |
  | `forge-verify` | L260 | L220 (R4) | **No** |
  | `forge-1-prd` | L31, L142 | L127 (R4) | Yes |
  | `forge-6-docs` | L47 | L173 (R4) | Yes |

  The single worked example in `03` §13.1 uses `forge-1-prd` — the non-representative case. Following it literally produces a dangling forward-reference in five files: exactly the cross-file prelude dependency C-5 and REQ-R2-02 forbid, and the #122-class failure REQ-PORT-02 exists to prevent. The alternative — inlining the full two-line prelude at each site — costs ~4 lines per site (2 prelude + 2 fence) and is budgeted nowhere. With `forge-5-loop` at **298/300** body lines (V-005), one such insertion puts it at 302 and hard-fails `check-spec-purity.py` Rule 4, while `04` §7's own "net **zero** added lines" constraint forbids it.

  Note that under R2's *original* scope this was never obtainable either: `05` §1.1's target table covers only `forge`, `forge-0-epic`, `forge-bootstrap`, `forge-1-prd` — not `forge-5-loop` or `forge-4-backlog`, R5's two consumers — and `05` §1.2 excludes `shared-conventions.md` and `stage-exit-protocol.md`, which carry four of R4's seven touch points.
- **Suggested fix:** (1) Add a scope-out banner to `00-core-definitions.md` §8 stating the compact form does not ship. (2) In `04` §7 and `03` §13.1, replace the compact-prelude sentence with an explicit rule: *"the fenced call reuses the file's existing full `BOOTSTRAP_PRELUDE` when one already precedes this call site; otherwise the full two-line prelude is inlined at the call site"* — quoting the canonical two-line text verbatim from `05` §1.1. (3) In `03` §11.2, delete the clause delegating the prelude form to `05`. (4) Change `03` §13.1's worked example from `forge-1-prd` to `forge-2-tech` or `forge-3-specs` so the representative (prelude-below) case is the one shown. (5) Add a per-skill table to `01` §2.2 giving, for each R4/R5 target, whether a prelude already precedes the call site (data above) and the net line cost where it does not, with an explicit check that `forge-5-loop` (2 spare) and `forge-0-epic` (8 spare) stay ≤300.
- **References:** `PRD.md` §3.2, §5 C-5; `05-instruction-relocations.md` §1.1, §1.2; `01-architecture-layout.md` §2.2; `.reference/REMEASURE-0.13.0.md` §Line-cap headroom
- **Checklist:** CHECK-S05, CHECK-S08, CHECK-S14, CHECK-S16, CHECK-S25, CHECK-S26, CHECK-S29

### V-003: `PRODUCTION_STAGES` already exists in `forge-session.py`; the spec's constant redefines it and silently breaks `next_stage()`
- **Severity:** error
- **Location:** `03-state-verbs.md` §3.7 ("Production-stage constant"), consumed by §4.1, §5.1, §6.1 (`choices=PRODUCTION_STAGES`) and §3.6
- **Issue:** §3.7 says *"Add a module constant for the production stage ids the verbs accept (mirrors the existing `EXIT_STAGES` tuple style, L1349)"* and defines a **7-entry** tuple beginning with `"forge-0-epic"` (spec line 328). But `scripts/forge-session.py` **already defines** `PRODUCTION_STAGES` at **L99** with **6** entries and no `forge-0-epic`:
  ```python
  #: The ordered production stages. This is the ONE place stage order lives.
  PRODUCTION_STAGES: Final[tuple[str, ...]] = (
      "forge-1-prd", "forge-2-tech", "forge-3-specs",
      "forge-4-backlog", "forge-5-loop", "forge-6-docs",
  )
  ```
  It is **order-sensitive** and consumed by live logic: `next_stage()` (L245) walks it and returns the first non-`complete` stage; `verify_state` (L317) walks `reversed(...)`; `stage_exit` (L1602–1604) compares `PRODUCTION_STAGES.index(state_next) > PRODUCTION_STAGES.index(stage)`. Implementing §3.7 literally adds a second module-level assignment that wins at import time, so **every standalone feature would have `next_stage()` return `"forge-0-epic"`** — a stage standalone features never record — breaking the navigator's "what runs next" and the scripted stage-exit's successor comparison. That is a runtime behavior change, which REQ-BEHAV-01 forbids. `03` §3.1's "Reused verbatim, not re-implemented" table omits `PRODUCTION_STAGES`, and `01` §2.1's module-layout diagram never lists it, so no document catches the collision.
- **Suggested fix:** In `03` §3.7: (a) replace the new definition with a differently named constant derived from the existing one, and state explicitly that L99 must NOT be redefined:
  ```python
  #: The --stage domain for the R4 state verbs: the six existing PRODUCTION_STAGES
  #: (L99, order-sensitive — do NOT redefine) plus forge-0-epic, which also carries
  #: a stageEntry but is excluded from the next-stage walk.
  STATE_VERB_STAGES: Final[tuple[str, ...]] = ("forge-0-epic", *PRODUCTION_STAGES)
  ```
  (b) change `choices=PRODUCTION_STAGES` → `choices=STATE_VERB_STAGES` in §4.1, §5.1, §6.1 and the §3.6 prose; (c) add `PRODUCTION_STAGES` (L99, 6 entries, order-sensitive) to §3.1's reuse table; (d) rewrite §3.7's WARNING block, which reasons from `EXIT_STAGES` and is now moot; (e) add `STATE_VERB_STAGES` and `_CASCADE_TARGETS` rows to `01` §2.1's diagram.
- **References:** `scripts/forge-session.py` L99–105, L245, L317, L1602–1604, L1349–1355; `00-core-definitions.md` §10; PRD REQ-BEHAV-01
- **Checklist:** CHECK-S09, CHECK-S12

### V-004: The R4 touch-point census omits three-to-four hand-authored state-write sites — REQ-R4-04 forbids a partial extraction
- **Severity:** gap
- **Location:** `03-state-verbs.md` §11.2 (conversion map); `00-core-definitions.md` §5; `01-architecture-layout.md` §1 (manifest), §4; `tech-spec.md` §6.8
- **Issue:** REQ-R4-04 (P0) requires *all* state-write touch points to be covered, and `03` §11.2 states the bar itself: *"No site may keep authoring JSON (a partial extraction is not acceptable, PRD REQ-R4-04)."* `tech-spec` §6.8 enumerates six state-writing skills; `01` §1 lists no R4 row for `forge-5-loop` and does not list `forge-6-docs` at all. Four real hand-authoring sites are left out:
  1. **`skills/forge-5-loop/SKILL.md` L188–189** — *"Before launching, update `.pipeline-state.json`: Set `stages.forge-5-loop.status` to `in-progress`"* (a `state-enter` touch point), and **L258–263** Step 5 — *"Set `stages.forge-5-loop`: `status` = `complete` … `completedAt` … `basedOnVersions` … `artifacts`"* (a `state-complete` touch point).
  2. **`skills/forge-6-docs/SKILL.md` L173–182** — *"Write pipeline state conforming to `references/pipeline-state-schema.json`. 1. Update `.pipeline-state.json`: Set `currentStage` to `complete`; Record `artifacts`; Set `stages.forge-6-docs.basedOnVersions` …"*
  3. **`skills/forge/SKILL.md` L185** — the navigator's `notes` write (a `state-note` touch point). `00` §5 row 4 scopes `notes` to the stage-exit "offer a note" step only, missing this site. `skills/forge/SKILL.md` L53 also carries a "write state conforming to" citation.

  This is not an oversight the verbs paper over: `03` §3.7 already puts `forge-5-loop` and `forge-6-docs` in the stage domain ("included for completeness"), so the verbs will *accept* those stages while no spec instructs any site to *call* them — the exact partial extraction REQ-R4-04 forbids. It also leaves the per-stage schema read that REQ-R4-01 exists to remove in place at three of the eight citing skills.
- **Suggested fix:** Add four rows to `03` §11.2: `forge-5-loop` pre-launch (L188–189) → `state-enter --stage forge-5-loop`; `forge-5-loop` Step 5 (L258–263) → `state-complete --stage forge-5-loop --based-on forge-4-backlog=N`; `forge-6-docs` Step 5 (L173–182) → `state-complete --stage forge-6-docs`; `forge` L185 → `state-note`. Add a note that `forge-5-loop` Step 5's **conditional** status (`complete` iff all backlog items are done, else `in-progress`) is not expressible by `state-complete`'s current contract (`03` §5) — either add an explicit status/partial flag or keep that branch on `state-enter`, and say which. Mirror into `00` §5 (rows 3 and 4), `01` §1 (add `R4 (state verbs)` to the `forge-5-loop` and `forge` rows; add a new `skills/forge-6-docs/SKILL.md M R4` row), `01` §4 (R4 revert row: "6 skill bodies" → 9), and `tech-spec` §6.8. Also decide explicitly whether the navigator's `pipelineStatus` writes (`skills/forge/SKILL.md` L215–228) are in or out of R4 — REQ-R4-04's enumerated list omits `pipelineStatus`, so record it as explicitly out of scope rather than leaving it silent.
- **References:** PRD REQ-R4-01, REQ-R4-04; `skills/forge-5-loop/SKILL.md` L188–189, L258–263; `skills/forge-6-docs/SKILL.md` L173–182; `skills/forge/SKILL.md` L53, L185; `.reference/REMEASURE-0.13.0.md` §R4
- **Checklist:** CHECK-S05, CHECK-S06, CHECK-S22, CHECK-S25

### V-005: The cap ledger is wrong on two rows, two specs disagree on `forge-0-epic`, and the 5,000-word half of the gate is untracked
- **Severity:** error
- **Location:** `01-architecture-layout.md` §2.2 (ledger); `05-instruction-relocations.md` §1.5 and §Dependencies; `tech-spec.md` §3.6, §6.6; `04-effective-config.md` §7
- **Issue:** `check-spec-purity.py` Rule 4 (`check_body_size`, L479–508) measures the body *after* the frontmatter close and enforces **both** `MAX_BODY_LINES = 300` (L89) and `MAX_BODY_WORDS = 5000` (L169). Measured with that exact slice:
  ```
  forge-5-loop     lines=298/300   words=4415/5000
  forge-0-epic     lines=292/300   words=2531/5000
  forge-verify     lines=257/300   words=2502/5000
  forge            lines=227/300   words=3936/5000
  forge-bootstrap  lines=234/300   words=1900/5000
  ```
  Three errors follow. **(a)** `forge-5-loop` is stated as **at** the cap in four places — `tech-spec` §3.6 ("at 300/300"), §6.6, `01` §2.2 ("300 / 300 (at cap)"), `05` §3.4 ("at the 300-line CI cap"). It is at 298/300, i.e. 2 lines of headroom. `.reference/REMEASURE-0.13.0.md` says so explicitly: *"`forge-5-loop` has 2 lines of headroom, **not the 'at the cap' the specs assume**."* That wrong figure drove the "strict 1:1, zero net lines" mandate and `05` §3.4's WARNING about splitting the L165 pointer — a constraint 2 lines less binding than stated. **(b)** `05` §1.5 and §Dependencies state `forge-0-epic` is "298/300"; `01` §2.2 and `tech-spec` §3.2 say 292/300. The Rule-4 measure is **292** — 298 is the raw `wc -l` including the 6-line frontmatter, the wrong metric. Two specs quoting different headroom for the same cap-bound body will read as a genuine disagreement to an implementer sizing an R4 edit. **(c)** No spec tracks the 5,000-word half, so a "line-neutral" R4/R5/R6 edit that swaps a short pointer for a longer verb invocation is unbudgeted on a dimension that also hard-fails CI. **(d)** `01` §2.2's ledger still carries a `forge-bootstrap` "(near cap)" row, which is both wrong (234/300, 66 spare) and moot (§2.2's own correction says that file is untouched).
- **Suggested fix:** Rewrite `01` §2.2's ledger against the figures above, adding a **words** column and a source line: *"Body-line and body-word figures from `.reference/REMEASURE-0.13.0.md` §Line-cap headroom (0.13.0). Rule 4 is a two-part gate — `MAX_BODY_LINES=300` AND `MAX_BODY_WORDS=5000` (`scripts/check-spec-purity.py` L89/L169); every 'line-neutral' claim must also be word-checked."* Delete the `forge-bootstrap` row. Propagate the corrected `forge-5-loop` figure to `tech-spec` §3.6/§6.6, `04` §7, `05` §3.4 (noting the 2-line headroom resolves §3.4's WARNING in favour of splitting the L165 pointer). Change both `05` occurrences of `298/300` for `forge-0-epic` to `292/300 (8 lines spare)`. Add the parenthetical "(body lines, frontmatter excluded — the region Rule 4 measures)" wherever a cap figure appears.
- **References:** `scripts/check-spec-purity.py` L89, L168–169, L479–508; `.reference/REMEASURE-0.13.0.md` §Line-cap headroom
- **Checklist:** CHECK-S06, CHECK-S08, CHECK-S16, CHECK-S25, CHECK-S26, CHECK-S29

### V-006: The loop-body cap test counts frontmatter — red against the unmodified repo
- **Severity:** error
- **Location:** `06-testing-strategy.md` §3.6 (`test_loop_body_within_cap`)
- **Issue:** The test does `BODY = read(LOOP / "SKILL.md")` then asserts `len(BODY.splitlines()) <= 300`. `check-spec-purity.py` counts body lines only (`text.split("\n")[fm.body_start_line:]`, L502, trailing blank stripped). `skills/forge-5-loop/SKILL.md` is **304 raw lines / 298 body lines**, so the assertion **already fails on an unmodified repo** and misreports a 2-line-headroom file as over cap.
- **Suggested fix:** Strip frontmatter before counting, mirroring Rule 4:
  ```python
  def _body_lines(text: str) -> list[str]:
      """Body = everything after the closing `---` (check-spec-purity Rule 4)."""
      lines = text.replace("\r\n", "\n").split("\n")
      assert lines and lines[0].strip() == "---", "no frontmatter block"
      close = next(i for i, l in enumerate(lines[1:], 1) if l.strip() == "---")
      body = lines[close + 1:]
      if body and body[-1] == "":
          body = body[:-1]
      return body

  def test_loop_body_within_cap():
      assert len(_body_lines(BODY)) <= 300, "forge-5-loop SKILL body exceeds 300 lines"
  ```
  Note in §3.6 that the current value is 298/300, citing `.reference/REMEASURE-0.13.0.md`.
- **References:** `scripts/check-spec-purity.py` L89, L502–507; `05-instruction-relocations.md` §3.4
- **Checklist:** CHECK-S37

### V-007: REQ-PERF-02's mandated green/red hook guard targets a file that does not exist — vacuous by construction
- **Severity:** gap
- **Location:** `06-testing-strategy.md` §7.3 (`test_session_hook_common_path_stays_silent`); `TRACEABILITY.md` Coverage Notes (4th bullet)
- **Issue:** The test resolves `hook = SKILLS.parent / "hooks" / "session-start.py"`. **No such file exists** — `hooks/` contains only `hooks.json`, which wires `SessionStart` to `bash ${CLAUDE_PLUGIN_ROOT}/scripts/session-check.sh`. Because the body is wrapped in `if hook.is_file():`, the test is a permanent no-op, and REQ-PERF-02's hook half is satisfied vacuously. REQ-PERF-02 (P0) explicitly demands *"the guard is a green/red test rather than a review judgment."* Even with the right path, the assertion `"print(" not in text or "common" in text.lower()` is tautological for a bash script — satisfiable by any file containing the word "common". `TRACEABILITY.md` flags this as an implementation-time confirmation task rather than as a P0 requirement whose test cannot pass or fail; the real target is now known and should be pinned.
- **Suggested fix:** Replace §7.3's second test with a bidirectional subprocess guard against the real hook:
  ```python
  import subprocess
  HOOK = REPO_ROOT / "scripts" / "session-check.sh"   # wired by hooks/hooks.json

  def test_session_hook_is_silent_on_the_common_path(tmp_path):
      (tmp_path / "forge.config.json").write_text("{}")
      r = subprocess.run(["bash", str(HOOK)], cwd=tmp_path, capture_output=True, text=True)
      assert r.returncode == 0 and r.stdout == "", r.stdout

  def test_session_hook_still_warns_when_config_missing(tmp_path):
      # control: proves the silence above is real, not a broken invocation
      feat = tmp_path / "specs" / "demo"; feat.mkdir(parents=True)
      (feat / ".pipeline-state.json").write_text("{}")
      r = subprocess.run(["bash", str(HOOK)], cwd=tmp_path, capture_output=True, text=True)
      assert r.returncode == 0 and "forge-init" in r.stdout
  ```
  Resolve the path from `hooks/hooks.json` rather than hardcoding it if the spec prefers, but the assertion must be hard (no `is_file()` skip) so the guard can never degrade to a silent pass. Update `TRACEABILITY.md`'s Coverage Note from "confirm the real hook target" to "resolved: guard executes `scripts/session-check.sh`."
- **References:** `hooks/hooks.json`; `scripts/session-check.sh`; `.reference/REMEASURE-0.13.0.md` §Non-regression baselines; PRD §4.1 REQ-PERF-02
- **Checklist:** CHECK-S02, CHECK-S14, CHECK-S36, CHECK-S37

### V-008: The frontmatter budget is ~2× the measured baseline, so the "no increase" guard does not bind
- **Severity:** error
- **Location:** `06-testing-strategy.md` §7.3 (`FRONTMATTER_CHAR_BUDGET = 9000`)
- **Issue:** The constant is `9000` with the comment "`~1.2k tokens across 13 descriptions`". Measured: the 13 `description:` values total **4,688 chars ≈ 1.17k tok** — the constant and its own comment disagree by a factor of two. 9,000 chars is ≈2.2k tokens, so a guard with 92% headroom cannot detect the growth REQ-PERF-02 forbids; it would stay green through a near-doubling.
- **Suggested fix:** Set `FRONTMATTER_CHAR_BUDGET = 4688` and change the comment to `# 13 skill frontmatter descriptions, measured 2026-07-28 @0.13.0 (.reference/REMEASURE-0.13.0.md). REQ-PERF-02 = non-increase, so this is an exact ceiling, not a budget.` Add a note that if a description must legitimately change, the constant is updated in the same PR with the new measurement recorded, so the bump is reviewable.
- **References:** `.reference/REMEASURE-0.13.0.md` §Non-regression baselines; PRD §4.1 REQ-PERF-02, §6 (frontmatter is out of scope, so this should never move)
- **Checklist:** CHECK-S36, CHECK-S37

### V-009: The evidence document and the revival gate for the R2 drop both cite paths that do not exist on this branch
- **Severity:** error
- **Location:** `PRD.md` §3.2 (lines 102 and 113); `05-instruction-relocations.md` preamble (lines 9 and 17)
- **Issue:** Two citations do not resolve:
  1. `docs/claude-5/phase-0-compliance-baseline.md` §4 is named as the sole justification for dropping R2. `docs/claude-5/` on this branch contains only `skill-review-playbook.md` and `skill-tuning-guide.md`.
  2. PRD §3.2 asserts, in the present tense, that "the `r2-prelude` probe **stays in** `eval/run-compliance-eval.py` as the gate if it is ever revived," and `05` instructs "re-run `python3 eval/run-compliance-eval.py --probe r2-prelude`." `eval/` contains only `run-eval.py` and `fixtures/`; only a stale `eval/__pycache__/run-compliance-eval.cpython-310.pyc` remains. `tests/test_compliance_eval.py` is likewise absent.

  **Both files are real** — they live on the unmerged, unpushed branch `test/claude-5-compliance-eval` (`bdc6017` harness, `ab76ace` docs). From this branch, and from `main`, they are unreachable, so the decision's evidence base and its stated revival gate are both dangling for any future reader or fresh agent. This is the spec-side symptom of a known loose end: that branch has no PR.
- **Suggested fix:** Land `test/claude-5-compliance-eval` (it is tooling-only, no CHANGELOG entry) so both paths resolve — this is the fix that makes the citations true rather than merely consistent. Until it lands, add a parenthetical to both citation sites naming the branch: "(currently on branch `test/claude-5-compliance-eval`, commit `ab76ace`; unmerged)". Change PRD §3.2's present-tense "stays in" to reflect the actual state. **User decision required** — see the Fix Execution Plan.
- **References:** `PRD.md` §3.2; `05-instruction-relocations.md` preamble; branch `test/claude-5-compliance-eval`
- **Checklist:** CHECK-S14

### V-010: `_now_iso` provenance, the `tempfile` import, and the `_write_state` body are each specified two ways across `00`/`01`/`03`
- **Severity:** inconsistency
- **Location:** `00-core-definitions.md` §3.3; `01-architecture-layout.md` §2.1 (L109–110, L123–124) and L35; `03-state-verbs.md` §3.1 (reuse table + WARNING), §3.2, §3.3
- **Issue:** Three linked contradictions in the shared machinery every verb depends on:
  1. **`_now_iso` provenance.** `00` §3.3 says the R4 work *"introduces"* it *"(verified: no `_now_iso` exists yet)"*. `01` §2.1 L110 marks it `~ reuse/confirm the existing UTC-ISO helper` and L35 says `+_now_iso reuse`. `03` §3.1's WARNING then quotes `00` as saying *"the module's existing … formatter"* — **that text does not appear in `00` §3.3**, which says the opposite. Verified: `grep -c "_now_iso" scripts/forge-session.py` → **0**, so "introduce" is correct and both `01`'s marker and the `03` misquotation are wrong.
  2. **`import tempfile`.** `03` §3.1's table asserts *"**No new stdlib import is required**"*; `03` §3.3 then decides *"use the `tempfile.mkstemp` + fsync form … and add `import tempfile`."* `01` §2.1 independently states *"No new stdlib imports beyond what exists."* Verified: `forge-session.py` L79–86 imports `argparse, json, os, subprocess, sys, datetime, Path, typing` — `tempfile` is not among them, so one new import IS required under the chosen form.
  3. **`_write_state` body.** `00` §3.3 presents a `state_path.with_suffix(...)` + `write_text` + `os.replace` body (no fsync, fixed temp name) and calls it canonical; `03` §3.3 presents a `tempfile.mkstemp` + fsync body while asserting *"The canonical signature is fixed by `00` §3.3"*. Signatures match, but a fresh agent implementing from `00` alone writes a materially different — and not multi-writer-safe — function.
- **Suggested fix:** Make `03` §3.3 (mkstemp + fsync) canonical and propagate: (a) in `00` §3.3, replace the `with_suffix` block with `03` §3.3's body verbatim and end with "`_write_state` requires adding `import tempfile` to the module import block (L79–86); no other new import is needed"; (b) in `03` §3.1, replace the table's last row with "`tempfile` is the one new stdlib import R4 adds (§3.3)" and delete the "No new stdlib import is required" sentence; (c) delete the misquotation in `03` §3.1's WARNING, restating it as "`00` §3.3 already specifies that R4 *introduces* `_now_iso`; this doc supplies the implementation"; (d) in `01` §2.1, change L110's marker to `N  new — no _now_iso exists today (verified)`, change L35 to `+_now_iso (new)`, change L123–124 to name `import tempfile` as the one new import, and add an `import tempfile  N` row to the tree.
- **References:** `scripts/forge-session.py` L77–86, L168, L177; `scripts/epic-manifest.py` L315–357 (`atomic_write` precedent)
- **Checklist:** CHECK-S06, CHECK-S07, CHECK-S12

### V-011: `01` §2.1 declares an R5 handler and a state printer that no document defines
- **Severity:** inconsistency
- **Location:** `01-architecture-layout.md` §2.1 (module-layout diagram, L118–119)
- **Issue:** `01` §2.1 lists `cmd_effective_config(...)  N  R5 handler` and `_print_state(payload) / per-verb  N`. `04` defines no `cmd_effective_config` — its symbols are `_default_schema_path()`, `_loop_runner_defaults(schema_path)`, `resolve_loop_runner(config_path, schema_path)`, `_print_effective_config(resolved)`, and §6's dispatch calls `resolve_loop_runner(...)` inline. Likewise `03` §11.1 dispatches seven distinct printers (`_print_state_enter` … `_print_state_branch`), not a single `_print_state`. The architecture doc's function inventory is the map a fresh implementer follows, so it names an export that does not exist and mis-names another.
- **Suggested fix:** Replace the `cmd_effective_config` row with the three R5 symbols actually specified (cross-ref `04` §3.2/§3.3/§4); replace the `_print_state` row with the seven `_print_state_*` printers plus `_print_effective_config` and the shared `_emit(payload, json_output, printer)` dispatcher (cross-ref `03` §11.1); and add rows for the shared machinery `03` introduces but `01` omits: `_load_state_for_write`, `_commit_state`, `_stage_entry`, `_parse_based_on`, `_parse_bool`, `STATE_VERB_STAGES`, `_CASCADE_TARGETS`, `_cascade_staleness`.
- **References:** `03-state-verbs.md` §3.4, §3.5, §3.7, §6.2, §9.2, §11.1; `04-effective-config.md` §3.2, §3.3, §4, §5.2, §6
- **Checklist:** CHECK-S10, CHECK-S12

### V-012: The `state-branch` conversion drops a timing qualifier and writes a schema-invalid state file at exit 0
- **Severity:** gap
- **Location:** `03-state-verbs.md` §10, §11.2 (conversion row for `shared-conventions.md` L217); `00-core-definitions.md` §5 (touch point 7)
- **Issue:** `03` §11.2 converts *"Branch Setup 'Record the branch' (L217) → set top-level `branch`"* into an unconditional `state-branch` call. The source prose carries a **timing qualifier the conversion silently drops**: `references/shared-conventions.md` L217 says *"write the resulting branch name … (**create/update it when the state file is first written for this stage**)"*. Branch Setup runs **before** Feature Directory Resolution and **before** the Stage-Entry Guard (`skills/forge-1-prd/SKILL.md` L20–21, L41), and L23 notes that at PRD time a brand-new standalone feature may have **no directory yet**. So at its actual firing point the converted call does one of two wrong things:
  - the feature dir does not exist → `_write_state`'s `tempfile.mkstemp(dir=parent)` raises `FileNotFoundError` → **exit 2 at the very start of forge-1-prd**, where today nothing fails; or
  - the dir exists but no state file does → `_read_state` returns `{}`, and the verb persists `{"branch": …, "updatedAt": …}` — **missing all six schema-required top-level fields** (`feature`, `createdAt`, `updatedAt`, `currentStage`, `stages`, `pipelineStatus`) — at **exit 0**.

  Only `state-enter` seeds those fields (`03` §4.2), and it runs later. `06` §3.5 never exercises this order (`_seed()` always pre-writes a full state), so the drift guard is blind to it.
- **Suggested fix:** (1) In `03` §3.4, have `_load_state_for_write` seed the required top-level fields on an empty state for **every** verb, not just `state-enter`:
  ```python
  state.setdefault("feature", feature)
  state.setdefault("createdAt", _now_iso())
  state.setdefault("pipelineStatus", "active")
  state.setdefault("stages", {})
  state.setdefault("currentStage", "forge-1-prd")
  ```
  and delete the now-redundant `setdefault` block from §4.2. (2) In `03` §10 and the §11.2 row, preserve the deferral explicitly: state that the `state-branch` call is emitted **after** Feature Directory Resolution and the Entry Stamp, not at the Branch Setup block — or, if it must stay there, require the skill to create `{resolvedFeatureDir}` first and document the exit-2 case in §10.4. (3) Add a `06` §3.5 case: run `state-branch` as the **first** verb against a feature dir with no state file and assert `validate_state(...) == []`.
- **References:** `references/shared-conventions.md` L217; `skills/forge-1-prd/SKILL.md` L20–23, L41; `references/pipeline-state-schema.json` top-level `required`; PRD REQ-BEHAV-01
- **Checklist:** CHECK-S18, CHECK-S21

### V-013: `_stage_entry` can create a `stageEntry` without the schema-required `status`, at exit 0
- **Severity:** gap
- **Location:** `03-state-verbs.md` §3.5 (`_stage_entry`), §5.2, §6.4 (`commit_hash is not None` branch), §6.8, §12
- **Issue:** `_stage_entry` does `stages.setdefault(stage, {})` and returns the empty dict. Two verbs then write into it **without setting `status`**: `cmd_state_artifact` (§5.2) sets only `artifacts`, so on a never-entered stage the persisted entry is `{"artifacts": [...]}`; and `cmd_state_complete` on the Commit-2 branch (§6.4) sets **only** `commitHash` by design, so a `--commit-hash` call against a never-completed stage (a typo'd `--stage`, or Commit 2 after a failed Commit 1) persists `{"commitHash": "abc123"}`. `references/pipeline-state-schema.json` defines `stageEntry` with `"required": ["status"]`, so both write a **schema-invalid** state file and return **exit 0**. §6.8's error table lists no case for "the mutation target does not exist," and `06` §3.5's fixtures always run `state-enter` first, so the guard is blind. `tech-spec.md` §7's claim that "malformed state is a code bug caught by the stdlib drift guard in CI" is therefore not true for these two paths.
- **Suggested fix:** In `03` §3.5, make the bootstrap schema-valid by default — `return stages.setdefault(stage, {"status": "pending"})` — and say so in the docstring. In §6.4, guard the commit-hash branch: if `entry.get("status") != "complete"`, `raise UsageError(f"--commit-hash requires {stage} to be complete (status: {entry.get('status')!r}); run state-complete without --commit-hash first")` → exit 2, and add the row to §6.8's table. Add `06` §3.5 cases: `state-artifact` against a never-entered stage asserts `validate_state(...) == []`; `state-complete --commit-hash` against a never-completed stage asserts `returncode == 2`.
- **References:** `references/pipeline-state-schema.json` `definitions.stageEntry.required`; `06-testing-strategy.md` §3.5; `tech-spec.md` §7
- **Checklist:** CHECK-S18

### V-014: No operator-facing message is specified for the `OSError` path; `_write_state` diverges from the precedent it claims to mirror
- **Severity:** gap
- **Location:** `03-state-verbs.md` §3.3, and the "Unwritable state directory → `OSError`" line in §4.5/§5.5/§6.8/§7.4/§8.4/§9.5/§10.4
- **Issue:** Every `UsageError` in the feature has an exact specified message. The `OSError` path — which is what the **most likely operator error** hits (wrong `--feature`, feature dir not yet created) — has **no specified message anywhere**. `03` §3.3 re-raises the bare `OSError`, so the user sees a raw errno for a *temp* file, e.g. `Error: [Errno 2] No such file or directory: '/…/specs/authh/.pipeline-state.json.k3f8x.tmp'`, naming neither the feature nor the real target. This contradicts §3.3's own claim to *"mirror `epic-manifest.py`'s `atomic_write` (L315)"*: the precedent at L355–357 **wraps** the failure — `raise UsageError(f"atomic write to {path} failed: {exc}")` — and fsyncs the parent dir (L346–354), neither of which §3.3 reproduces. `04` §10 wraps I/O errors descriptively, so the feature is also internally inconsistent.
- **Suggested fix:** In `03` §3.3, change the handler to match the precedent:
  ```python
      except OSError as exc:
          tmp_path.unlink(missing_ok=True)
          raise UsageError(f"atomic write to {state_path} failed: {exc}") from exc
  ```
  Add the parent-dir fsync from `epic-manifest.py` L346–354, or state why it is omitted. In §3.6, specify the message for the missing-feature-dir case and note the feature name in the path is the operator's cue for a typo. Update the seven per-verb "Error cases" sections to read "→ `UsageError` (wrapped `OSError`) → exit 2". Strengthen `06` §3.5's `test_missing_feature_dir_exits_2` to also assert `"atomic write to" in r.stderr`.
- **References:** `scripts/epic-manifest.py` L315–357; `scripts/forge-session.py` L1879–1884; `04-effective-config.md` §10
- **Checklist:** CHECK-S12, CHECK-S20

### V-015: No recovery is described when a state verb fails — and the frozen Git Commit Protocol's own recovery step becomes unexecutable
- **Severity:** gap
- **Location:** `03-state-verbs.md` §6.5, §11.2, §13.2; `00-core-definitions.md` §10 (R4 row)
- **Issue:** R4 introduces a **new runtime failure surface** (a subprocess that can exit 2) at seven protocol touch points, including the Stage-Entry Guard and the Git Commit Protocol, where today the mechanic is a hand-edit that cannot fail with an exit code. No document says what the *skill* does when a verb exits 2 — although the pipeline already has a convention for exactly this (`shared-conventions.md` L160: *"on exit 2, surface the plain `Error:` line from stderr verbatim"*). Two concrete consequences:
  1. **Commit-1 failure recovery is unexecutable.** `shared-conventions.md` L245 — **frozen** per `00` §10 and `03` §13.2 — says *"If Commit 1 fails: do NOT update pipeline state to complete … leave state as `in-progress` so the stage can be resumed."* But `03` §6.5 orders the verb call **before** the commit, and §11.2 forbids any site from hand-authoring JSON. No verb is documented as the revert path. (`state-enter` would restore `in-progress` but also rewrites `startedAt` and `currentStage` — side effects nobody has sanctioned for this use.)
  2. **The "Nothing to commit" branch cannot be honored.** L248 says *"mark the stage `complete`, leave `commitHash` at its **existing value** … and skip Commit 2."* `cmd_state_complete`'s completion branch unconditionally executes `entry["commitHash"] = None`, destroying a prior hash on re-completion, with no flag to preserve it.
- **Suggested fix:** Add `03` §14 "Verb-failure handling at the call site", mirroring the L160 convention: *"If a `state-*` verb exits 2, surface the plain `Error:` line from stderr verbatim, do NOT proceed to the next protocol step, and do NOT hand-author the JSON as a workaround; the stage is resumable because the entry stamp is still on disk."* Then (a) in §6.5, name the sanctioned Commit-1-failure revert path explicitly (either `state-enter` with its `startedAt` side effect documented, or a new `state-complete --status in-progress` escape hatch); (b) add a `--preserve-commit-hash` flag, or specify that the completion branch writes `commitHash: None` only when the key is absent, so L248 is expressible — document it in §6.1/§6.4/§6.8; (c) add both cases to §13.2's must-not-change list and to `06` §3.5.
- **References:** `references/shared-conventions.md` L160, L243–248; PRD REQ-BEHAV-01/02
- **Checklist:** CHECK-S18, CHECK-S21

### V-016: A corrupt-but-present state file is silently overwritten with a near-empty one
- **Severity:** gap
- **Location:** `03-state-verbs.md` §2, §3.4; `00-core-definitions.md` §3.3
- **Issue:** All three documents present the behavior as benign: `00` §3.3 — *"`_read_state` … downgrades a missing/corrupt file to `{}`"*; `03` §3.4 — *"A missing/corrupt state downgrades to `{}` so a verb can create-or-update."* Verified in source: `_read_state` catches `(OSError, json.JSONDecodeError)` and returns `{}`, and its own docstring justifies that for a **read-only** scan (*"the navigator simply treats that feature as not-started"*). That justification does not transfer to a writer. Under R4 the sequence for a corrupt file is: `_read_state` → `{}` → mutate → `_write_state` **atomically replaces the corrupt file** with a minimal one → **exit 0**. The user's `branch`, `stages`, version history, `deferredDecisions[]` and `epicChangeRequests[]` are destroyed with no warning and no non-zero exit. Today's hand-authored mechanic cannot do this — the model reads and edits the JSON itself, so it observes the corruption. R4 therefore introduces a data-loss path that does not exist today.
- **Suggested fix:** In `03` §3.4, distinguish **absent** (legitimately `{}`) from **present-but-unparseable** (fatal). Specify a writer-side load rather than reusing `_read_state`:
  ```python
  if state_path.exists():
      try:
          state = json.loads(state_path.read_text(encoding="utf-8"))
      except json.JSONDecodeError as exc:
          raise UsageError(
              f"{state_path} exists but is not valid JSON ({exc}); refusing to "
              f"overwrite it. Fix or move the file, then re-run."
          ) from exc
      if not isinstance(state, dict):
          raise UsageError(f"{state_path} is not a JSON object; refusing to overwrite it.")
  else:
      state = {}
  ```
  Add the row to §3.6's exit-2 conditions and each verb's "Error cases"; correct the wording in `00` §3.3 and `03` §2. Add a `06` §3.5 case: write `"{ not json"`, run `state-note`, assert `returncode == 2` **and** that the original file bytes are unchanged.
- **References:** `scripts/forge-session.py` L177–187; `06-testing-strategy.md` §3.5
- **Checklist:** CHECK-S18, CHECK-S21

### V-017: The revert-boundary table declares two units file-disjoint that share a file
- **Severity:** error
- **Location:** `01-architecture-layout.md` §4 (R1 and R6 rows)
- **Issue:** REQ-DELIV-01 (P0) and SC-6 rest entirely on this table, and two rows are wrong:
  1. **R6 row** says its shared-file caveat is "none — disjoint." But `01` §1's manifest lists `skills/forge-5-loop/SKILL.md` as carrying both `R6` and `R5: effective-config consumer`, and §2.2's ledger row reads `forge-5-loop | R6, R5`. Both edit the body closest to the cap. Reverting one without a line audit of the other is exactly the failure this table exists to prevent.
  2. **R1 row** gives R1 sole ownership of `skills/forge-verify/SKILL.md` with caveat "none — disjoint." But `03` §11.2 has a conversion row for that file, and `tech-spec` §6.8 lists `forge-verify` among the state-writing skills R4 converts. R1 and R4 both edit it, and `01` §1's manifest omits the R4 annotation (unlike `forge-0-epic`, which correctly carries two).
- **Suggested fix:** (1) R6 row caveat → "shares `forge-5-loop/SKILL.md` with R5 (both 1:1 swaps; combined net line **and word** effect must be re-verified against Rule 4 after each lands)"; add the reciprocal note to the R5 row. (2) R1 row caveat → "shares `skills/forge-verify/SKILL.md` with R4 (R1 edits citations at Steps 2/3/4/6; R4 edits the production-stage state-write step — line-disjoint)". (3) In §1's manifest, append `R4 (state verbs)` to the `skills/forge-verify/SKILL.md` row so it matches `03` §11.2 and `tech-spec` §6.8.
- **References:** `01-architecture-layout.md` §1, §2.2, §4; `03-state-verbs.md` §11.2; `tech-spec.md` §6 items 6 and 8
- **Checklist:** CHECK-S16, CHECK-S38

### V-018: `05` §3.3 and §3.4 contradict each other on where `agent-selection.md` is cited, defeating REQ-R6-02
- **Severity:** inconsistency
- **Location:** `05-instruction-relocations.md` §3.3 ("Load gate (REQ-R6-02)") vs §3.4 (L165 row)
- **Issue:** §3.3 states the requirement is met *because* of citation placement: *"`agent-selection.md` is cited **only at the forge-5-loop capability gate** … Because the citation lives inside that gated block, the file is read only when the gate is on (REQ-R6-02),"* concluding the optional-flags catalog is *"not loaded by default (a gate-off run never opens the file)."* §3.4's table then requires a **second** citation at **L165** — *"**Split the pointer**: keep `runner-contract.md` for model-selection precedence; add/redirect the optional-flags-catalog reference to `references/agent-selection.md`."* Verified against the real file: the capability gate begins at `skills/forge-5-loop/SKILL.md` **L172** (`#### Agent selection (gated on loopRunner.agentArgument)`), so **L165 is outside and above it**. Every gate-off run reads L165 and sees a pointer to `agent-selection.md` — precisely the load §3.3 claims cannot happen. REQ-R6-02 (P0) requires the catalog be "reachable but not loaded by default." §3.4's own fallback ("redirect L165 wholly to the file that holds the majority concern") does not resolve it either: redirecting to `agent-selection.md` makes it worse, and redirecting to `runner-contract.md` leaves the moved catalog unreachable from its only pointer.
- **Suggested fix:** Recommended resolution — keep L165 pointing **only** at `references/runner-contract.md` for model-selection precedence, and move the optional-flags-catalog mention *down into* the gated block (L172–182), where §3.4 already re-points L174 and L180. That satisfies REQ-R6-02 literally. Then correct §3.3 to enumerate all citation sites explicitly, and change §3.4's L165 row to "**Trim the pointer**: drop the optional-flags-catalog clause from L165; the catalog is referenced from inside the gated block." Re-verify the trim is ≤0 net lines. **User decision required** if the owner instead wants the catalog discoverable outside the gate — in which case §3.3 must stop claiming REQ-R6-02 is satisfied by placement and state how it is otherwise met.
- **References:** PRD §3.6 REQ-R6-02; `05` §3.2, §3.3, §3.4; `skills/forge-5-loop/SKILL.md` L165, L172, L174, L180
- **Checklist:** CHECK-S15, CHECK-S16

### V-019: Two sibling-section pointers in `00-core-definitions.md` name the wrong section
- **Severity:** error
- **Location:** `00-core-definitions.md` §5 (closing paragraph) and §7 (Reconciliation note)
- **Issue:** (1) §5 sends the reader to *"`03-state-verbs.md §4`"* for the commit-hash follow-up; `03` §4 is "`state-enter` — Entry Stamp". The material is in **`03` §6.5**, which is also where `TRACEABILITY.md` correctly points REQ-BEHAV-02. (2) §7 sends the reader to *"`02-verify-checklist-split.md §4`"* for the expected-count reconciliation; `02` §4 is "Copy rules (REQ-R1-05)". The material is in **`02` §7.3**, matching `02`'s own coverage table. (For the record, the `tech-spec §6.1`/`§6.9` references in `00` §3 and `01` §3.2 / `04` §7 are **not** defects — `tech-spec` §6 is a numbered list and items 1 and 9 are `forge-session.py` and `build-adapters.py`, which is what those citations mean.)
- **Suggested fix:** `03-state-verbs.md §4` → `03-state-verbs.md §6.5` in §5; `02-verify-checklist-split.md §4` → `02-verify-checklist-split.md §7.3` in §7.
- **References:** `03-state-verbs.md` §6.5; `02-verify-checklist-split.md` §7.3; `TRACEABILITY.md`
- **Checklist:** CHECK-S15

### V-020: `TRACEABILITY.md` ships three unresolved `§...` placeholders, two wrong-document pointers, and a silently renumbered OQ table
- **Severity:** error
- **Location:** `TRACEABILITY.md` — R6 table (REQ-R6-03), Cross-cutting table (REQ-PORT-01/02/03), Constraints table (C-4), NFR table (REQ-BEHAV-02), Open Questions table
- **Issue:** Two defects. **(a) Unfilled and mispointed cells:** `REQ-R6-03` cites `` `04` §... (cap ledger) `` — the cap ledger is `01` §2.2, and `04`'s only REQ-R6-03 mention is §7; `REQ-PORT-01` cites `` `04` §... `` (correct target: `04` §7); `C-4` cites `` `04` §... `` and `04` never mentions C-4 at all (grep: zero hits); `REQ-PORT-02` cites `04` with no section; `REQ-PORT-03` cites `02` with no section; `REQ-BEHAV-02` cites `04` with no section. **(b) OQ renumbering:** PRD §7 defines OQ-1 (schema-read frequency), OQ-2 (script-helper vs annotated-example for R4), OQ-3 (re-measured baselines). `TRACEABILITY.md`'s table lists OQ-1 (matches), OQ-2 = *re-measured baseline counts* (this is PRD OQ-3), OQ-3 and OQ-4 (these are *tech-spec* OQs). So it adopted tech-spec numbering without saying so, and **PRD OQ-2 has no row at all** — even though it is resolved (`tech-spec` §3.4 chose targeted verbs over the fallback). `tech-spec` §10 does this correctly, annotating provenance ("OQ-2 (PRD OQ-3)"); `TRACEABILITY.md` does not.
- **Suggested fix:** Fill all six cells: REQ-R6-03 → `04` §7 (relabel "cap discipline"; the ledger stays credited to `01` §2.2); REQ-PORT-01 → `04` §7; REQ-PORT-02 → `04` §7; REQ-PORT-03 → `02` §8; REQ-BEHAV-02 → `04` §7; C-4 → `04` §1/§3, and add an explicit "C-4" mention to `04` §1 so the constraint is traceable from the target document. In the OQ table, adopt `tech-spec` §10's annotation style (`OQ-1 (PRD OQ-1)`, `OQ-2 (PRD OQ-3)`, `OQ-3 (tech-spec OQ-3)`, `OQ-4 (tech-spec OQ-4)`) and add a row for **PRD OQ-2** — "R4 mechanism: script-helper vs annotated-example" — owner `tech-spec` §3.4, status *resolved: targeted state verbs chosen*.
- **References:** `04-effective-config.md` §7, §9; `02-verify-checklist-split.md` §8; `01-architecture-layout.md` §2.2; `PRD.md` §7; `tech-spec.md` §10
- **Checklist:** CHECK-S15, CHECK-S38

### V-021: Two REQ IDs are cited that do not exist in the PRD — one of them ships into source
- **Severity:** error
- **Location:** `00-core-definitions.md` §3.3 (inside the `_write_state` docstring); `01-architecture-layout.md` Requirement Coverage table, row 4
- **Issue:** (1) `00` §3.3's proposed docstring reads *"…so a crash can never leave a half-written state file (**REQ-ROBUST-03** pattern)."* `REQ-ROBUST-03` does not exist in this PRD and appears nowhere under `specs/`. This is not cosmetic: the string sits inside a Python docstring that `03` §3.3 carries into `scripts/forge-session.py`, so an undefined requirement ID would be baked into shipped source — and `specs/CLAUDE.md` requires shipped implementation artifacts to be self-contained and not lean on `specs/` provenance. (2) `01`'s coverage row reads `| REQ-R2-03..? / REQ-R6-03 | …|`. `REQ-R2-03` does not exist (R2 has only `-01`/`-02`) and the literal `..?` is an unresolved authoring placeholder that shipped. Neither is visible to `validate-traceability.py`. (This is the `REQ-ROBUST-03` orphan the validator *did* catch.)
- **Suggested fix:** (1) Delete `(REQ-ROBUST-03 pattern)` from the docstring — the sentence stands alone; if a cross-reference is wanted, use the concrete precedent already named in the same docstring (`epic-manifest.py`'s `atomic_write`). (2) Replace the coverage row's ID cell with `REQ-R6-03` alone (the R2 half goes with V-001), and add a second row `| REQ-R4-04 (cap side-constraint) | R4 verb conversions stay within each body's measured headroom | §2.2 |`.
- **References:** `PRD.md` §3.2; `03-state-verbs.md` §3.3; `specs/CLAUDE.md`
- **Checklist:** CHECK-S04, CHECK-S14

### V-022: No numbered spec owns the `shared-conventions.md` R4 edits — `03` delegates them to `04`, which never mentions the file
- **Severity:** gap
- **Location:** `01-architecture-layout.md` §1 (the `references/shared-conventions.md M R4` row); `03-state-verbs.md` §11.2 (closing blockquote)
- **Issue:** `03` §11.2 maps four `shared-conventions.md` touch points to verbs (Stage-Entry Guard L266–269, incremental artifacts L275, Branch Setup L217 / Reconciliation L230, Git Commit Protocol L243/L244) and then disclaims ownership: *"The **exact edited lines** … **are owned by `04-effective-config.md` (the shared-conventions edits)**."* `04-effective-config.md` contains **zero** occurrences of "shared-conventions" — it is the R5 subcommand spec. So the single largest R4 surface outside `forge-session.py` — a 295-line always-loaded reference file whose prose is frozen by REQ-BEHAV-02 — has no document specifying its before/after edits. `03` §13.1 supplies a concrete before/after only for `forge-1-prd` Step 6.
- **Suggested fix:** Assign it to `03-state-verbs.md`, which already owns the touch-point map and the frozen-prose invariant. Replace §11.2's misattribution with "the exact edited lines are specified in §13.3 below", and add a new **§13.3 `shared-conventions.md` before/after** giving a verbatim before/after for each touch point at L217, L230, L243/L244, L266–269, L275, in §13.1's format. Update `00` §1's document-ownership list and `01` §1's row to name `03-state-verbs.md §13.3` as the owner. Delete the "(the shared-conventions edits)" attribution to `04` wherever it appears.
- **References:** `tech-spec.md` §6.7; `00-core-definitions.md` §1, §5; `03-state-verbs.md` §11.2, §13.1
- **Checklist:** CHECK-S05

### V-023: The "Public API surface" pointer cites the wrong sections of both owning specs
- **Severity:** error
- **Location:** `01-architecture-layout.md` §1, closing paragraph
- **Issue:** *"Their contracts are the only new 'exports' (`03-state-verbs.md §5`, `04-effective-config.md §4`)."* `03` §5 is "`state-artifact` — incremental artifacts[]", one verb of seven, not the API surface; `04` §4 is "Deep-merge over user config", an internal algorithm step, not the CLI contract. The actual contracts are `03` §2 (overview table) plus §4–§10 (one section per verb), and `04` §2 "CLI Contract" plus §5 "Output". For a plugin, this block *is* the skill-facing API statement, so a reader following either pointer lands on the wrong contract.
- **Suggested fix:** Change to "(`03-state-verbs.md` §2 overview + §4–§10 per-verb contracts; `04-effective-config.md` §2 CLI Contract + §5 Output)". Add a second sentence naming the other half of the skill-facing surface — the reference paths skills are instructed to read — pointing at §3.1: "The other skill-facing contract is the citation set in §3.1: `references/verification-checklists/{mode}.md`, `references/findings-template.md`, `references/agent-selection.md`."
- **References:** `03-state-verbs.md` §2, §4–§10; `04-effective-config.md` §2, §5; `01-architecture-layout.md` §3.1
- **Checklist:** CHECK-S32

### V-024: `forge-session.py` is quoted as 1,866 lines; it is 1,888 on this branch, and two line anchors in `00` are stale
- **Severity:** error
- **Location:** `01-architecture-layout.md` §1 and §2.1; `tech-spec.md` §2 and §6.1; `00-core-definitions.md` §3, §3.1, §3.2
- **Issue:** `wc -l scripts/forge-session.py` → **1,888**. The figure was correct at the specs commit (`git show 36c0a14:scripts/forge-session.py | wc -l` → 1,866) and drifted when `main` @ 0.13.0 was merged into this branch. Most anchors still hold (`UsageError` L168, `_read_state` L177, `_load_config` L526, `_resolve_feature_dir` L1416 — all verified), but two past the drift point are stale: `00` §3.1's `if args.cmd == "stage-exit"` at "L1840" is now **L1862**, and §3.2's top-level handler at "L1857–1862" is now **L1879–1884**.
- **Suggested fix:** Update `1,866` → `1,888 lines (at 0.13.0 / this branch)` in `01` §1 and §2.1 and `tech-spec` §2 and §6.1. Correct `00` §3.1's dispatch anchor to L1862 and §3.2's handler anchor to L1879–1884. Add a one-line note wherever line anchors appear: "anchors verified at 0.13.0; re-grep before editing — they shift with any merge."
- **References:** `scripts/forge-session.py`; `git show 36c0a14:scripts/forge-session.py`; `.reference/REMEASURE-0.13.0.md` header
- **Checklist:** CHECK-S06

### V-025: The tech spec lists `forge-verify` among skills that swap hand-authored JSON for state verbs; `00` §4.2 says R4 adds no verb for verify entries
- **Severity:** inconsistency
- **Location:** `tech-spec.md` §6.8 vs `00-core-definitions.md` §4.2 vs `03-state-verbs.md` §11.2
- **Issue:** `tech-spec` §6.8 lists `forge-verify` among the state-writing skills whose *"'Write pipeline state' step swaps hand-authored JSON for the matching verb(s)."* But `00` §4.2 states *"**R4 does not add a verb for verify entries** — forge-verify/forge-fix keep their existing write path; R4 covers only the production `stageEntry` touch points,"* and `tech-spec` §3.4's own verb table defines no `verifyEntry` verb. So §6.8 promises a swap no verb can perform. `03` §11.2 resolves it correctly (*"production-stage entry/exit stamps it authors (**NOT** the verifyEntry)"*), so the defect is the tech spec's loose wording, which `01` §1's manifest does not disambiguate either.
- **Suggested fix:** In `tech-spec` §6.8, change the entry to `forge-verify (production stageEntry stamps only — the verifyEntry write path is unchanged; R4 adds no verifyEntry verb, see 00-core-definitions.md §4.2)`. Add the same qualifier to `01` §1's `skills/forge-verify/SKILL.md` row (which currently marks it `M R1` only) — this coordinates with V-017's fix to the same row.
- **References:** `00-core-definitions.md` §4.2; `03-state-verbs.md` §11.2; `tech-spec.md` §3.4, §6.8
- **Checklist:** CHECK-S08

### V-026: `tech-spec` §3.6 names two R6 re-point sites; `05` §3.4 correctly identifies three
- **Severity:** inconsistency
- **Location:** `tech-spec.md` §3.6 vs `05-instruction-relocations.md` §3.4
- **Issue:** `tech-spec` §3.6 asserts R6's SKILL edit is "the existing pointers **at lines 165/174**". `skills/forge-5-loop/SKILL.md` cites `runner-contract.md` at L165, L168, L170, L174, L180, L194, L198, L208, L227, L302 — and **L180** (*"Full rationale: `references/runner-contract.md`"*, attached to the Claude-only model-alias guard) points at section 3, which `05` §3.2 moves to `agent-selection.md`. `05` §3.4's table gets this right and covers L165/L168/L170/L174/L180 exhaustively. The impl spec is correct and the tech spec is incomplete — but the tech spec is what a reviewer reads for the R6 decision, and following it verbatim leaves a dangling L180 pointer.
- **Suggested fix:** Update `tech-spec` §3.6 to read "the existing pointers at lines 165 (optional-flags-catalog half), 174 and 180 re-point / split to `references/agent-selection.md`; the pointers at 168, 170 and below are unchanged," and add "see `05-instruction-relocations.md` §3.4 for the verified per-line table."
- **References:** `05-instruction-relocations.md` §3.2, §3.4; `skills/forge-5-loop/SKILL.md` L165, L174, L180
- **Checklist:** CHECK-S15, CHECK-S16

### V-027: R1 breaks three committed test files that no spec enumerates
- **Severity:** gap
- **Location:** `02-verify-checklist-split.md` §1 (in-scope list), §4.4; `06-testing-strategy.md` §2 ("What must stay green")
- **Issue:** R1 deletes `skills/forge-verify/references/verification-checklists.md` (`02` §4.4: *"Deletion is total … not left as a stub"*) and drops the `~` from the Step-2/Step-3 count figures (`02` §7.3). Three existing tests depend on both, and none is named in any spec:
  ```
  tests/test_lifecycle_artifact_check.py:20  CHECKLISTS = …/verification-checklists.md
  tests/test_smoke_command.py:25             CHECKLISTS = … same path
  tests/test_dev_runtime_smoke.py:23         CHECKLISTS = … same path
  ```
  Four `CHECKLISTS.read_text()` calls will raise `FileNotFoundError`, and six assertions pin the exact `~` strings §7.3 mandates removing (`"backlog: ~27 checks"`, `"impl: ~23 checks"`, and their bare-word variants). `06` §2 lists only `test_config_defaults_parity.py`, `test_pipeline_state_schema.py`, `test_stage_exit_protocol.py`, and the `test_build_adapters.py` snapshot as the regression baseline. The R1 unit therefore lands **red on CI's `python3 -m pytest tests`** with nothing in the specs predicting it.
- **Suggested fix:** Add `## 3.1.1 Existing tests R1 must update` to `06-testing-strategy.md` (and item 6 to `02` §1 "In scope"), specifying exactly: (1) `tests/test_lifecycle_artifact_check.py` — repoint `CHECKLISTS` to `…/verification-checklists/backlog.md`; drop the `## Implementation Mode Checklist` split terminator in `test_b27_present_and_advisory` (that heading no longer exists in `backlog.md` — slice to end-of-file); change L49–50 to `"backlog: 27 checks"` / `"backlog 27"`. (2) `tests/test_dev_runtime_smoke.py` — repoint to `…/impl.md`; in `_runnability()` drop the `## Epic Mode Checklist` terminator; change L68–69 to `"impl: 23 checks"` / `"impl 23"`. (3) `tests/test_smoke_command.py` — repoint to `…/impl.md`; change L78–79 the same way. Add all three to `06` §2 with the note that they are "stay green **after a mechanical repoint**," not "stay green unchanged," and must be updated *within the R1 PR* so R1 stays independently revertible (REQ-DELIV-01).
- **References:** `02-verify-checklist-split.md` §1, §4.4, §7.3, §9.5; `06-testing-strategy.md` §2, §3.1; the three test files
- **Checklist:** CHECK-S25

### V-028: The recommended belt-and-suspenders citation form is not matched by the real fan-out regex
- **Severity:** error
- **Location:** `02-verify-checklist-split.md` §8; `06-testing-strategy.md` §5 (`NEW_FILES`)
- **Issue:** `02` §8 recommends the SKILL body "also name at least the six literal paths once — e.g. `` (`references/verification-checklists/{prd,tech,specs,backlog,impl,epic}.md`) ``". The real regex in `scripts/build-adapters.py` L1667–1669 is `r"references/([A-Za-z0-9_][A-Za-z0-9_./{}*-]*)"` — the character class has **no comma**. Verified against that exact pattern:
  ```
  '(`references/verification-checklists/{prd,tech,specs,backlog,impl,epic}.md`)'
    → ['verification-checklists/{prd']      # one bogus capture, zero literal paths
  '`references/verification-checklists/specs.md`'
    → ['verification-checklists/specs.md']  # correct
  ```
  So the recommended form yields **zero** of the six citations. It also defeats `02` §9 assertion 7 and `06` §5's `test_every_new_reference_file_is_cited`. Relatedly, `06` §5 asserts all six literals appear in a skill body, but `02` §7.2 specifies the Step-3 read as the **templated** `references/verification-checklists/{mode}.md` and §8 only *SHOULD*-recommends the literals — so `prd.md` and `tech.md` are not guaranteed, and `06` §5 would be red. (Portability is not actually at risk: `_copytree_verbatim` at L1597–1624 walks `src.rglob("*")` and is called unconditionally at L1392, so the new subdir ships as a skill-local own-ref regardless. But the spec's stated mechanism and its own drift guard are both broken.)
- **Suggested fix:** In `02` §8, promote the clause from SHOULD to **MUST** and replace the brace-list with six separate literal citations in the Step-3 read note. Add an explicit warning that comma-separated brace expansion is **not** matched by `_REFERENCE_CITATION_RE` (`scripts/build-adapters.py` L1667) and must never be used as a citation form. Mirror the six literal paths into `01` §3.1's required-citations table. In `06` §5, add `# Depends on 02 §8: the six mode paths are cited LITERALLY (not as a {mode} template or brace enumeration).`
- **References:** `scripts/build-adapters.py` L1392, L1597–1624, L1667–1669; `02` §7.1, §7.2, §8, §9.7; `00` §9; PRD REQ-PORT-01
- **Checklist:** CHECK-S25, CHECK-S26, CHECK-S37

### V-029: OQ-4 is answerable on disk — citation fan-out does **not** scan agent bodies
- **Severity:** improvement
- **Location:** `tech-spec.md` §10 OQ-4; `00-core-definitions.md` §9; `02-verify-checklist-split.md` §6 (WARNING blockquote)
- **Issue:** Three specs carry OQ-4 as unresolved and defer it to "confirm during R1 implementation." It is resolvable by reading the generator: `_fan_out_shared_references(skill: SkillRecord, …)` (`scripts/build-adapters.py` L1672–1701) scans `skill.body` only, and its sole call site is inside the per-skill loop at L1402; `AGENTS_GLOB` records (L406, L561) are emitted by the per-agent emitters (L946, L1067, L1122) with no fan-out call anywhere. **Fan-out never scans `agents/*.md`.** The specs' mitigation (cite from the SKILL body) is therefore not belt-and-suspenders but strictly required — worth stating as a hard rule rather than a hedge. It also means the path `02` §6 adds to `agents/forge-verifier.md` is prose-only and resolves for the leaf solely because the forge-verify skill dir is its resolution context.
- **Suggested fix:** Mark OQ-4 **RESOLVED — no** in `tech-spec` §10, citing `build-adapters.py` L1402 and L1672–1701. Rewrite `00` §9's OQ-4 bullet from a mitigation to a rule: *"Citation fan-out scans skill bodies **only** — an `agents/*.md` citation never ships a file. Every new reference file MUST be cited from a skill body."* Replace `02` §6's WARNING with a one-line note that the agent-body path is a human-readable pointer with no build effect.
- **References:** `scripts/build-adapters.py` L406, L561, L946, L1067, L1122, L1402, L1672–1701; `00` §9; `02` §6
- **Checklist:** CHECK-S22, CHECK-S26

### V-030: The catch-all citation guard is red on the unmodified repo (2 false positives)
- **Severity:** error
- **Location:** `06-testing-strategy.md` §5 (`test_every_invoke_point_citation_names_an_existing_file`)
- **Issue:** Running the specified `CITE_RE = re.compile(r"references/([A-Za-z0-9_][A-Za-z0-9_./{}*-]*)")` over `skills/*/SKILL.md` today produces two failures, neither caused by this feature:
  1. `skills/forge-5-loop/SKILL.md:165` ends a sentence with "…read `references/runner-contract.md`." — the class includes `.`, so the match captures `runner-contract.md.` (trailing period) and resolves to a missing file.
  2. `skills/forge-2-tech/SKILL.md:61` cites project-level paths `.agents/references/stack-decisions.md` / `.claude/references/stack-decisions.md` — the regex matches the `references/…` tail of a *consumer-project* path that intentionally does not exist in the plugin bundle.

  A guard authored per this spec is red on day one, which is worse than no guard — it gets deleted or `xfail`-ed.
- **Suggested fix:** Replace the regex and document both traps:
  ```python
  # Anchor on a non-path prefix so `.agents/references/…` (project-level, not a
  # bundle ref) is skipped, and stop at `.md` so a sentence-final period is not
  # swallowed into the filename.
  CITE_RE = re.compile(r"(?<![./\w-])references/([A-Za-z0-9_][A-Za-z0-9_./{}*-]*?\.md)\b")
  ```
  Verified: this matches 122 citations across the 13 skill bodies with **zero** misses on the current repo. Add a comment recording that the guard was validated green pre-change, so any future red is a genuine regression.
- **References:** `skills/forge-5-loop/SKILL.md` L165; `skills/forge-2-tech/SKILL.md` L61; `00` §9
- **Checklist:** CHECK-S37

### V-031: No e2e / behavior-preservation procedure for SC-3 — the feature's headline criterion
- **Severity:** gap
- **Location:** `06-testing-strategy.md` (whole document; its Requirement Coverage table omits REQ-BEHAV-01/02 and SC-3)
- **Issue:** The prime directive is *"Zero behavioral diff. A full dogfooded feature run (all authoring stages + verify + loop + docs) MUST exhibit the same prompts, gates, guards, and outputs"* (REQ-BEHAV-01 / SC-3). `TRACEABILITY.md` routes SC-3 to "`00` §10 · `06` §2 (regression baseline)". `00` §10 is a table of per-unit invariants, not a procedure; `06` §2 is a list of four existing pytest files that "must stay green." Neither is an e2e check — every guard in `06` is a static drift assertion over file content, so **nothing in the suite exercises a running pipeline**. The testing-strategy document is the right owner and currently has no e2e tier at all.
- **Suggested fix:** Add `06` §9 "Behavior-preservation run (SC-3, REQ-BEHAV-01/02)" specifying: (1) *when* — once per shipped unit's PR, or once for the batch before release, stated explicitly; (2) *what* — a dogfood run of a small real feature through forge-1-prd → forge-6-docs on a branch, recording the prompt/gate/output surface at each stage; (3) *the comparison basis* — the pre-change transcripts from the `consumption-data-refresh` dogfood corpus (already the evidence source for §7), listing which surfaces must be identical (AskUserQuestion option sets and ordering, Decision Support wording, Branch Setup/Reconciliation prompts, Stage-Entry Guard classification, the two-commit Git protocol, verify gate routing, stage-exit directives); (4) *the record* — where the result is written and who signs off. If a full run is too costly per unit, say so explicitly and name the reduced substitute (R1: one real verifier fan-out; R6: one gate-off and one gate-on loop launch) rather than leaving SC-3 unassigned.
- **References:** PRD §4.2 REQ-BEHAV-01/02, §8 SC-3; `00` §2, §10; `TRACEABILITY.md` SC-3 row
- **Checklist:** CHECK-S34

### V-032: The fixture/portability step covers five adapters; the repo builds six
- **Severity:** gap
- **Location:** `06-testing-strategy.md` §6; `02-verify-checklist-split.md` §8; `PRD.md` §3.7 REQ-PORT-03
- **Issue:** `06` §6 says the snapshot run proves "all five adapters regenerate cleanly", and REQ-PORT-03 and `02` §8 carry the same count. `scripts/build-adapters.py` L49 declares `AGENT_TARGETS = ("claude", "codex", "copilot", "cursor", "gemini", "pi")` — **six** targets; `adapters/` contains a `pi/` tree, and `tests/test_build_adapters.py` has a pi-specific case while its own local `AGENT_TARGETS` constant is still the five-tuple. The Pi adapter landed in 0.13.0, after the PRD's wording was set. A fixture-refresh instruction that under-counts targets risks a moved reference file being verified on five hosts and shipped broken on the sixth — the exact #122/#132 failure class REQ-PORT-01/02 exist to prevent.
- **Suggested fix:** In `06` §6, change to "all six adapter targets (`claude`, `codex`, `copilot`, `cursor`, `gemini`, `pi` — `scripts/build-adapters.py` `AGENT_TARGETS`)", and add: "`pi` resolves references through its own extension (`adapter-src/pi/`); confirm each moved/split reference path appears under `adapters/pi/` after regeneration, not only under the five agent bundles." Note that `tests/test_build_adapters.py`'s local five-tuple should be checked when the moved files land. Apply the same correction to `02` §8 and PRD §3.7 REQ-PORT-03.
- **References:** `scripts/build-adapters.py` L7, L49; `tests/test_build_adapters.py` L38; `adapters/pi/`; `.reference/REMEASURE-0.13.0.md`
- **Checklist:** CHECK-S35

### V-033: No line-cap guard for the other R4-edited bodies, though `forge-0-epic` has only 8 lines of headroom
- **Severity:** gap
- **Location:** `06-testing-strategy.md` §3.6 (cap guard scoped to forge-5-loop only) and §8
- **Issue:** The 300-line body cap is a **CI-only** gate (`check-spec-purity.py`, not run by pytest — C-2). `06` guards it for exactly one skill. But R4 edits state-write citations in **eight** skill bodies (forge-1-prd ×2, forge-2-tech ×2, forge-0-epic, forge-3-specs, forge-4-backlog, forge-6-docs, forge-verify, forge — and three more per V-004), and `.reference/REMEASURE-0.13.0.md` calls this out: *"**`forge-0-epic` has 8 lines of headroom, not 12.** Dropping R2 removed the slack R4 was expected to inherit here. R4 must be strictly in-place in this body."* R1 also edits forge-verify. Nothing in `06` catches an over-cap body outside forge-5-loop until CI rejects the PR.
- **Suggested fix:** Generalize §3.6's cap test into a suite-wide guard using the `_body_lines()` helper from V-006:
  ```python
  def test_every_skill_body_within_cap():
      for skill in sorted(SKILLS.glob("*/SKILL.md")):
          n = len(_body_lines(read(skill)))
          assert n <= 300, f"{skill.parent.name}: {n} body lines (cap 300)"
  ```
  Green today (max is forge-5-loop at 298). Add the word half too (`<= 5000`, per V-005). Add a line to §8: "every skill body edited by any unit is covered by the ≤300-line / ≤5000-word guard, which surfaces the CI-only purity cap in pytest (C-2)."
- **References:** `.reference/REMEASURE-0.13.0.md` §Line-cap headroom; `scripts/check-spec-purity.py` L89, L169; PRD §5 C-2
- **Checklist:** CHECK-S34, CHECK-S36

### V-034: `06` §7 asks for measurements that are already done, and omits the instruction the re-measurement issued to backlog authors
- **Severity:** inconsistency
- **Location:** `06-testing-strategy.md` §7.1, §7.2, §7.4, §7.5
- **Issue:** §7.1 says *"**Before adopting any numeric target, re-measure** … The LOAD-MAP figures have drifted since b9f0871"*; §7.4 says *"Confirm from transcripts how often stages actually performed the per-stage `pipeline-state-schema.json` read (OQ-1)."* Both are **already done**: `.reference/REMEASURE-0.13.0.md` (2026-07-28) declares itself the baseline of record for SC-1, supersedes LOAD-MAP, and answers OQ-1 (2 reads of `pipeline-state-schema.json`, 1 of `forge-config-schema.json`, across 188 dogfood sessions). `06` never cites that file. Worse, REMEASURE carries a directive `06` §7.5 contradicts by silence: *"**Backlog authors: do not write an acceptance criterion asserting a ~1.5k or ~2.7k measured per-stage saving for R4/R5.**"* §7.5's R4/R5 rows ("no schema read", "no config-schema read") invite exactly that framing.
- **Suggested fix:** Rewrite §7.1/§7.2 as "**Baseline of record: `.reference/REMEASURE-0.13.0.md`** (2026-07-28 @0.13.0; method: `wc -l`/`wc -w` at ~1.3 tok/word, cross-checked `chars ÷ 4`)" and reproduce the per-R verdict table (R1 −4.8k…−5.9k, R3 −1.72k, R4 −1.49k, R5 −2.69k, R6 −1.19k) instead of requesting a fresh measurement. Rewrite §7.4 to state the **answer** (the per-stage schema read is not, in practice, per-stage) and carry REMEASURE's instruction verbatim into §7.5: R4/R5 acceptance is the static file-load delta on invocations where the read occurs, plus drift-removal — never a claimed per-stage saving. Mark OQ-1/OQ-3 resolved in `TRACEABILITY.md`'s Open Questions table (coordinates with V-020).
- **References:** `.reference/REMEASURE-0.13.0.md`; PRD §4.3 REQ-OBS-01/02, §7 OQ-1/OQ-3
- **Checklist:** CHECK-S36

### V-035: `test_missing_feature_dir_exits_2` asserts a contract `03` does not specify
- **Severity:** improvement
- **Location:** `06-testing-strategy.md` §3.5 vs `03-state-verbs.md` §3
- **Issue:** The test asserts `state-note --feature nope` exits 2 with empty stdout. `03` §3 specifies the opposite intent: `_load_state_for_write` *"reuses the existing resolver (`_resolve_feature_dir`, L1416) … A missing/corrupt state downgrades to `{}` so a verb can create-or-update"*, and the real `_resolve_feature_dir` is documented "Best-effort feature dir (flat, else unique nested, else flat literal)" — it never errors on a missing feature. The exit 2 arises only incidentally, because `_write_state` calls `tempfile.mkstemp(dir=…)` on a nonexistent directory. If an implementer adds a reasonable `parent.mkdir(parents=True, exist_ok=True)` hardening, the verb silently starts creating state for typo'd feature names and this guard becomes meaningless.
- **Suggested fix:** Pin the contract in `03` §3 first — add an explicit rule: *"the verbs never create a feature directory; a `--feature` whose directory does not exist is an error (exit 2, `Error:` on stderr)"* — and specify where it is raised (a `UsageError` in `_load_state_for_write` when the state dir is not a directory) rather than relying on `mkstemp`. Then strengthen `06` §3.5 to assert the mechanism: `assert r.returncode == 2 and r.stdout == "" and "Error:" in r.stderr`, and rename it `test_unknown_feature_is_a_usage_error`. Coordinates with V-014.
- **References:** `03-state-verbs.md` §3; `scripts/forge-session.py` L1416; `00-core-definitions.md` §3.2
- **Checklist:** CHECK-S37

### V-036: Subprocess helpers hardcode `python3` instead of the suite's `sys.executable`
- **Severity:** improvement
- **Location:** `06-testing-strategy.md` §3.5 (`_run`) and §4.1 (three `subprocess.run` calls)
- **Issue:** All specified subprocess invocations use the literal `"python3"`. The house style in `tests/conftest.py` is `[sys.executable, str(HELPER), *args]`, and 10 existing test modules use `sys.executable` (only `test_build_adapters.py` and `test_forge_bootstrap.py` use `"python3"`, both deliberately exercising a shipped command string). Under a venv or a CI image where `python3` is not the interpreter running pytest, the new guards would test a different interpreter than the suite runs on — an avoidable "green locally, red in CI" source, and this repo has been bitten by that class before (`jsonschema`-absent-in-CI).
- **Suggested fix:** Add a convention bullet to `06` §1: *"Subprocess helper invocations use `sys.executable`, matching `tests/conftest.py`'s `run_cli`; reserve a literal `python3` for tests that assert a shipped command string."* Update `_run` in §3.5 and the three calls in §4.1.
- **References:** `tests/conftest.py`; `tests/test_doctor.py`, `tests/test_discover_feature.py`, `tests/test_reconcile_branch.py`; PRD §5 C-2
- **Checklist:** CHECK-S34, CHECK-S35

## Fix Execution Plan

### User Decisions Required

**All resolved by the owner, 2026-07-29. Treat these as settled inputs — do not re-ask.**

1. **V-009 (R2 provenance citations) → merge the eval branch. DONE.**
   `test/claude-5-compliance-eval` has been merged into `forge/context-efficiency`, so
   `docs/claude-5/phase-0-compliance-baseline.md`, `eval/run-compliance-eval.py`,
   `eval/README.md`, `eval/field-observations.md` and `tests/test_compliance_eval.py` all
   resolve from this branch. **The citations in PRD §3.2 and `05`'s preamble are now
   correct as written — no edit is needed.** The only remaining V-009 work is to confirm
   `docs/claude-5/phase-0-compliance-baseline.md` really does carry a §4 covering the
   `r2-prelude` probe (it does) and to leave both present-tense claims standing. Test
   count moves 462 → **497 passed, 2 skipped**; update that figure anywhere a spec quotes
   it. This work rides to `main` with the feature's PR.

2. **V-018 (R6 load gate) → trim L165; cite only inside the gate.**
   Keep `skills/forge-5-loop/SKILL.md` L165 pointing **only** at
   `references/runner-contract.md` for model-selection precedence, and move the
   optional-flags-catalog mention *down into* the gated block at L172–182 alongside the
   L174/L180 re-points. Rewrite `05` §3.4's L165 row from "**Split the pointer**" to
   "**Trim the pointer**: drop the optional-flags-catalog clause from L165; the catalog is
   referenced from inside the gated block," and correct `05` §3.3 to enumerate all
   citation sites explicitly rather than asserting placement in the abstract. A trim is
   ≤0 net lines, which the 2-line headroom requires.

3. **V-004 (forge-5-loop conditional completion) → add an explicit status flag.**
   Give `state-complete` a `--status {complete,in-progress}` (default `complete`) so the
   loop's conditional is expressible by the verb that owns completion. Specify it in `03`
   §6.1 (argparse), §6.4 (handler), §6.8 (error cases), and add a `06` §3.5 case asserting
   `--status in-progress` leaves a schema-valid entry that is not `complete`. This also
   supplies the sanctioned Commit-1-failure revert path V-015 asks for — use
   `state-complete --status in-progress` there rather than overloading `state-enter`, and
   say so in `03` §6.5 and §14.

4. **V-004 part 2 (`pipelineStatus`) → out of scope, recorded explicitly.**
   REQ-R4-04 enumerates entry stamp, `artifacts[]`, completion, `notes`,
   `deferredDecisions[]`, `epicChangeRequests[]`, and `branch`; `pipelineStatus` is absent,
   so the omission is deliberate. Add an explicit exclusion line to `00` §5 — "the
   navigator's `pipelineStatus` writes (`skills/forge/SKILL.md` L215–228, pause/resume/
   abandon) are **out of R4 scope** per REQ-R4-04's enumerated list; they keep their
   existing write path" — and add the same qualifier to the `skills/forge/SKILL.md` row in
   `01` §1, so V-004's other three conversions there are not read as covering it. Do **not**
   add an eighth verb.

Everything else is mechanical.

### Execution Steps

#### Step 1: Propagate the R2 scope-out to the six unmarked documents
- **Files:** `tech-spec.md`, `00-core-definitions.md`, `01-architecture-layout.md`, `06-testing-strategy.md`, `02-verify-checklist-split.md`, `03-state-verbs.md`, `04-effective-config.md`
- **Addresses:** V-001, and the `01` half of V-021
- **Checklist:** CHECK-S04, CHECK-S06, CHECK-S08, CHECK-S16, CHECK-S34, CHECK-S36
- **Action:** Apply V-001's four sub-fixes, using `05-instruction-relocations.md`'s preamble blockquote as the template. While in `01`, fix the Requirement Coverage row per V-021(2).
- **Depends on:** none
- **Rationale:** Must land first — Steps 2 and 3 rewrite call sites and ledgers that these markers explain, and a backlog authored before this step would schedule R2 work.

#### Step 2: De-couple R4/R5 call sites from the R2 compact prelude
- **Files:** `04-effective-config.md` §7, `03-state-verbs.md` §11.2 and §13.1, `00-core-definitions.md` §8, `01-architecture-layout.md` §2.2
- **Addresses:** V-002
- **Checklist:** CHECK-S05, CHECK-S08, CHECK-S14, CHECK-S16, CHECK-S25, CHECK-S26
- **Action:** Apply V-002's five sub-fixes: banner on `00` §8; substitute the full two-line `BOOTSTRAP_PRELUDE` (verbatim from `05` §1.1) into both After blocks with the reuse-or-inline rule; delete the delegation clause from `03` §11.2; change `03` §13.1's worked example to a prelude-below skill; add the per-skill prelude-position and line-cost table to `01` §2.2.
- **Depends on:** Step 1

#### Step 3: Correct every cap figure and the revert boundaries
- **Files:** `01-architecture-layout.md` §1/§2.2/§4, `tech-spec.md` §3.2/§3.6/§6.6, `04-effective-config.md` §7, `05-instruction-relocations.md` §1.5/§3.4/§Dependencies
- **Addresses:** V-005, V-017, V-024, V-025, V-026
- **Checklist:** CHECK-S06, CHECK-S07, CHECK-S08, CHECK-S16, CHECK-S25, CHECK-S26, CHECK-S29, CHECK-S38
- **Action:** Rewrite `01` §2.2's ledger per V-005 (measured lines **and** words, source line, drop `forge-bootstrap`); propagate 298/300 and 292/300 everywhere; fix the two revert-boundary caveats and the `forge-verify` manifest row per V-017 and V-025; update the `1,866` → `1,888` figures and the two stale `00` anchors per V-024; correct `tech-spec` §3.6's re-point site list per V-026.
- **Depends on:** Step 1 (which removes the R2 rows from `01` §4/§5)

#### Step 4: Complete the R4 touch-point census and assign the `shared-conventions.md` owner
- **Files:** `03-state-verbs.md` §11.2 and new §13.3, `00-core-definitions.md` §1/§5, `01-architecture-layout.md` §1/§4, `tech-spec.md` §6.8
- **Addresses:** V-004, V-022
- **Checklist:** CHECK-S05, CHECK-S06, CHECK-S22, CHECK-S25
- **Action:** Add the four conversion rows per V-004 (plus the conditional-completion note, per the user's decision); mirror into `00` §5, `01` §1/§4, `tech-spec` §6.8. Write the new `03` §13.3 with verbatim before/after for all five `shared-conventions.md` touch points, and delete the `04` misattribution per V-022.
- **Depends on:** Steps 1–3; user decision on the conditional-completion mechanism

#### Step 5: Fix the `forge-session.py` contract defects
- **Files:** `03-state-verbs.md` §3.1–§3.7, §6.1/§6.4/§6.5/§6.8, §10, new §14; `00-core-definitions.md` §3.3; `01-architecture-layout.md` §2.1
- **Addresses:** V-003, V-010, V-011, V-012, V-013, V-014, V-015, V-016
- **Checklist:** CHECK-S09, CHECK-S10, CHECK-S12, CHECK-S18, CHECK-S20, CHECK-S21
- **Action:** Rename the colliding constant to `STATE_VERB_STAGES` and update all `choices=` sites (V-003); make `03` §3.3 canonical for `_write_state` and reconcile `_now_iso` / `import tempfile` across `00`/`01`/`03` (V-010); correct `01` §2.1's symbol inventory (V-011); seed required top-level fields in `_load_state_for_write` and fix the `state-branch` ordering (V-012); bootstrap `{"status": "pending"}` and guard the commit-hash branch (V-013); wrap `OSError` in a descriptive `UsageError` (V-014); add §14 verb-failure handling plus the commit-hash-preservation flag (V-015); refuse to overwrite a corrupt state file (V-016).
- **Depends on:** Step 4 (§11.2 rows must be final before §13.3/§14 reference them)
- **Rationale:** Grouped because all eight touch the same shared machinery in `03` §3 and its `00`/`01` mirrors; splitting them would mean editing the same twenty lines five times.

#### Step 6: Repair the testing strategy
- **Files:** `06-testing-strategy.md` §1, §2, new §3.1.1, §3.5, §3.6, §4.1, §5, §6, §7.1–§7.5, §8, new §9; `02-verify-checklist-split.md` §1/§8; `PRD.md` §3.7
- **Addresses:** V-006, V-007, V-008, V-027, V-028, V-030, V-031, V-032, V-033, V-034, V-035, V-036
- **Checklist:** CHECK-S02, CHECK-S14, CHECK-S25, CHECK-S26, CHECK-S34, CHECK-S35, CHECK-S36, CHECK-S37
- **Action:** Add `_body_lines()` and fix the cap test (V-006); generalize it suite-wide with the word half (V-033); replace the hook guard with the real `session-check.sh` subprocess pair (V-007); set `FRONTMATTER_CHAR_BUDGET = 4688` (V-008); add §3.1.1 enumerating the three R1-broken tests and their exact repoints (V-027); fix the citation regex (V-030) and the literal-citation dependency in `02` §8 (V-028); add the §9 behavior-preservation procedure (V-031); correct five→six adapters in `06` §6, `02` §8 and REQ-PORT-03 (V-032); rewrite §7 against REMEASURE and carry its backlog-author instruction into §7.5 (V-034); pin the unknown-feature contract (V-035); switch to `sys.executable` (V-036).
- **Depends on:** Steps 1 and 5 (V-035's assertion follows the V-014/V-016 contract; §7.5's R4/R5 rows follow Step 5's final verb set)

#### Step 7: Fix cross-references, the traceability matrix, and the R6 gate
- **Files:** `00-core-definitions.md` §3.3/§5/§7/§9, `TRACEABILITY.md`, `02-verify-checklist-split.md` §6, `tech-spec.md` §10, `05-instruction-relocations.md` §3.3/§3.4
- **Addresses:** V-018, V-019, V-020, V-021(1), V-029
- **Checklist:** CHECK-S04, CHECK-S14, CHECK-S15, CHECK-S22, CHECK-S26, CHECK-S38
- **Action:** Correct the two section pointers (V-019); delete `(REQ-ROBUST-03 pattern)` from the docstring (V-021); fill `TRACEABILITY.md`'s six cells and re-annotate the OQ table with PRD OQ-2 restored (V-020); mark OQ-4 resolved and promote `00` §9's mitigation to a hard rule (V-029); make `05` §3.3 and §3.4 state the same citation-placement rule per the user's decision (V-018).
- **Depends on:** Steps 1–6 — the matrix must record final section numbers, so this runs last.

#### Step 8: Re-verify
- **Files:** none (verification only)
- **Addresses:** all
- **Action:** Re-run `/feature-forge:forge-verify context-efficiency specs`, plus `python3 -m pytest tests`, `ruff check scripts/ eval/`, and `python3 scripts/check-spec-purity.py`. Confirm the R2 scope-out marker count is non-zero in every document that mentions R2, and that no spec still quotes `300/300` for `forge-5-loop`.
- **Depends on:** Step 7

---

## Tooling defect (filed separately from these findings)

`scripts/validate-traceability.py` L23: `REQ_PATTERN = re.compile(r"REQ-[A-Z]+-\d+")` silently ignores any requirement whose category segment contains a digit — `REQ-R1-01` through `REQ-R6-03`, 17 of this PRD's 29 IDs. It reported `uncovered_requirements: []` while having examined only 12. Any forge feature using numbered category IDs gets a false all-clear from the gate that exists to prevent exactly that. Suggested fix: `r"REQ-[A-Z][A-Z0-9]*-\d+"`, plus a warning when the matched count is implausibly low relative to `REQ-`-prefixed occurrences in the file. This belongs in the feature-forge issue tracker, not in this feature's backlog.

---

## Fix Progress

- Step 1: [APPLIED] 2026-07-29 — R2 scope-out propagated to all six unmarked documents (`tech-spec` banner + §3.2/§3.7/§7/§8, `00` §8 banner + §10 row + Verification box + coverage row, `01` title banner + manifest + §4/§5, `06` §3.2 replaced by a scope-out note, `02`/`03`/`04` residual mentions). Marker coverage verified non-zero in every document that mentions R2 (was 0 in six).
- Step 2: [APPLIED] 2026-07-29 — R4/R5 call sites de-coupled from the R2 compact prelude: `00` §8 banner states the compact form is unused; `04` §7 and `03` §13.1 now carry the full two-line `BOOTSTRAP_PRELUDE` verbatim with a reuse-or-inline rule; `03` §11.2's misattribution to `04` deleted; `03` §13.1's worked example annotated as the prelude-above minority case; new `01` §2.2.1 tabulates prelude position and line cost per target skill.
- Step 3: [APPLIED] 2026-07-29 — cap ledger rewritten from measured figures (lines **and** words, Rule 4 is a two-part gate); `forge-5-loop` 300/300→298/300 and `forge-0-epic` 298/300→292/300 propagated to `tech-spec` §3.2/§3.6/§6.6, `04` §7, `05` §1.5/§3.4/§Dependencies, `TRACEABILITY`; `forge-bootstrap` row dropped; revert-boundary caveats corrected for R1/R3/R4/R6; `1,866`→`1,888` and the two stale `00` anchors (L1862, L1879–1884) fixed; `tech-spec` §3.6 re-point sites 165/174 → 165/174/180.
- Step 4: [APPLIED] 2026-07-29 — R4 census completed: four conversion rows added to `03` §11.2 (`forge-5-loop` pre-launch + Step 5, `forge-6-docs` Step 5, navigator `state-note`), mirrored into `00` §5, `01` §1/§4, `tech-spec` §6.8; `pipelineStatus` and `verifyEntry` recorded as explicit exclusions; new `03` §13.3 gives verbatim before/after for all five `shared-conventions.md` touch points (ownership moved off `04`, which never mentioned the file).
- Step 5: [APPLIED] 2026-07-29 — `forge-session.py` contract defects fixed: `PRODUCTION_STAGES` collision resolved via a derived `STATE_VERB_STAGES` with a do-not-redefine warning citing L99/L245/L317/L1602; `_now_iso`/`tempfile`/`_write_state` reconciled across `00`/`01`/`03` (mkstemp+fsync canonical, `import tempfile` acknowledged); `01` §2.1 symbol inventory corrected; `_load_state_for_write` now seeds the six required top-level fields, refuses a corrupt state file, and errors on an unknown feature dir; `_stage_entry` bootstraps `{"status": "pending"}`; `--commit-hash` guarded; `OSError` wrapped in a descriptive `UsageError`; `--status` and `--preserve-commit-hash` added per the owner decision; new `03` §14 specifies verb-failure handling at the call site.
- Step 6: [APPLIED] 2026-07-29 — testing strategy repaired: `_body_lines()` helper + suite-wide line/word cap guard; REQ-PERF-02 hook guard now executes the real `scripts/session-check.sh` with a control case (no `is_file()` skip); `FRONTMATTER_CHAR_BUDGET` 9000→4688; new §3.0 enumerating the three R1-broken tests with exact repoints; citation regex fixed and **empirically re-verified** (118 resolvable citations, 0 misses; the old pattern produced 3 false positives on the unmodified repo); §7 rewritten against `.reference/REMEASURE-0.13.0.md` with OQ-1/OQ-3 marked resolved and the do-not-claim-per-stage-savings instruction carried into §7.5; new §9 behavior-preservation procedure for SC-3; five→six adapter targets; `sys.executable` convention.
- Step 7: [APPLIED] 2026-07-29 — cross-references and matrix: `00` §5/§7 section pointers corrected (→ `03` §6.5, `02` §7.3); `REQ-ROBUST-03` removed from the shipped docstring; `REQ-R2-03..?` row replaced; `TRACEABILITY` six unfilled cells filled and the OQ table re-annotated with PRD provenance and PRD OQ-2 restored; OQ-4 marked **RESOLVED — no** in `00` §9, `02` §6 and `tech-spec` §10 with the L1402/L1672–1701 evidence; `05` §3.3/§3.4 reconciled on the trim-not-split resolution; `02` §8 brace-enumeration warning promoted to MUST.

**Note on Step 6:** an intermediate edit to `06-testing-strategy.md` §7 truncated the
document tail (§7.5 onward). Detected immediately by a heading re-scan, restored from
`git show HEAD:` and re-applied correctly. Final file carries §1–§9 + Dependencies +
Verification; `wc -l` 635 → 767.

**Gates after all steps:** `python3 -m pytest tests` → **497 passed, 2 skipped** ·
`ruff check scripts/ eval/` → clean · `python3 scripts/check-spec-purity.py` → PASS.
