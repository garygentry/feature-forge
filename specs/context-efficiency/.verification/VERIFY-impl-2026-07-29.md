# Verification Report: context-efficiency (impl)

Date: 2026-07-29
Pipeline Stage: forge-5-loop complete (20/20 items done) — impl verify before forge-6-docs
Mode: impl (23 checks)
Dispatch: 5 parallel `forge-verifier` instances over disjoint CHECK-ID slices

Artifacts Reviewed:
- `specs/context-efficiency/` — PRD.md, tech-spec.md, 00-core-definitions.md, 01-architecture-layout.md, 02-verify-checklist-split.md, 03-state-verbs.md, 04-effective-config.md, 05-instruction-relocations.md, 06-testing-strategy.md, TRACEABILITY.md, backlog.json, .rauf/progress.md, .verification/BEHAVIOR-PRESERVATION-*.md
- `scripts/` — forge-session.py, epic-manifest.py, check-spec-purity.py, build-adapters.py, validate.sh
- `skills/**` — all 13 SKILL.md bodies and their `references/**`
- `references/` — shared-conventions.md, stage-exit-protocol.md, portable-root.md, pipeline-state-schema.json, forge-config-schema.json
- `tests/**`, `adapters/{claude,codex,copilot,cursor,gemini,pi}/**`, `installer/`
- git range `ca3da53~1..8f160ab` (20 commits)

## Coverage

Executed 23 of 23 checks. Results: 16 pass, 6 fail, 1 not-applicable (advisory).

| Slice | Checks | Result |
|---|---|---|
| 1. Requirement coverage vs specs | I01–I04 | 4 pass |
| 2. Backlog completion + integration | I05–I10 | 3 pass, 3 fail (I05, I07, I08) |
| 3. Testing + static checks | I11, I12, I16, I17 | 3 pass, 1 fail (I17) |
| 4. Code quality + documentation | I13–I15, I18–I20 | 4 pass, 2 fail (I20, and I18 partial) |
| 5. Runnability | I21–I23 | 2 pass, 1 not-applicable (I21) |

### Gates run directly during verification (not taken on report)

- `bash scripts/validate.sh` → **exit 0**, `All checks passed!`
- pytest → **705 passed, 2 skipped** (both skips pre-existing toolchain absences: mypy, cargo-clippy)
- `ruff check scripts/ eval/` → **exit 0**
- `python3 scripts/build-adapters.py --check` → **exit 0** (no drift across all six targets)
- installer `npm ci && npm run build && npm test` → **182/182**
- `adapter-src/pi` verify → **11/11**
- All 8 new subcommands invoked read-only → exit 0; full `state-*` round-trip against a throwaway fixture → exit 0; every documented exit-2 condition reproduced; corrupt state file refused **byte-intact**

## Summary

- Total findings: 18
- Errors: 2 (V-001 introduced by this feature; V-002 pre-existing)
- Gaps: 3
- Inconsistencies: 3
- Improvements: 10

**Only V-001 is a defect this feature introduced.** V-002 and V-011 are pre-existing bugs surfaced incidentally. V-003 is not a code defect but a charter-claim that does not hold under the shipped default, and needs an owner decision. Everything else is documentation reconciliation, preventive guards, or hand-offs to forge-6-docs.

### Corrections to assumptions carried into dispatch

1. **R2 is SCOPED OUT** (`PRD.md:95`, marked `SCOPED OUT (2026-07-28)`). No backlog item implements it; no prelude in the tree is deduped or compacted; `check_prelude_identity` (Rule 5) is green. Any statement that this feature deduped preludes is wrong.
2. **`forge-5-loop` body is 298/300 lines / 4600/5000 words** — measured with `check-spec-purity.py`'s own method (frontmatter-stripped). `forge-0-epic` is 292/300. Raw `wc -l` (304/298) is not what Rule 4 measures.
3. **Live citation count is 140**, not the 134 recorded in `test_reference_citations.py`'s docstring and `progress.md`.

---

## Findings

### V-001: Three cross-references in `agent-selection.md` point at headings that stayed in `runner-contract.md`

- **Severity:** error
- **Location:** `skills/forge-5-loop/references/agent-selection.md:10`, `:91`, `:108`
- **Issue:** Item 015 moved three sections out of `runner-contract.md` into the new gated `agent-selection.md` verbatim, but the moved prose kept intra-document deixis that no longer resolves. `:10` — "parallel to `## Model selection precedence` **above**"; that heading is now `runner-contract.md:12`. `:108` — "see precedence **above**"; same orphaned referent. `:91` — 'see "Root/sandbox env guard" under Step 3b'; that is `## Launch detail (Step 3b — background process)` at `runner-contract.md:66`. This is worse than cosmetic under the capability gate the file exists to serve: when the gate is on, an agent may load `agent-selection.md` **without** `runner-contract.md` in the same turn, so "above" points at text not in its context at all. `tests/test_reference_citations.py` cannot catch it — it validates `references/*.md` **path** citations in skill bodies, not prose heading references inside a reference file. Independently confirmed by two verifier instances (`:10`/`:91` by both, `:108` by one).
- **Suggested fix:** In `skills/forge-5-loop/references/agent-selection.md`:
  - `:10` — `` This section is **parallel** to `## Model selection precedence` above: `` → `` This section is **parallel** to `## Model selection precedence` in `references/runner-contract.md`: ``
  - `:91` — `(see "Root/sandbox env guard" under Step 3b)` → ``(see "Root/sandbox env guard" under `## Launch detail (Step 3b — background process)` in `references/runner-contract.md`)``
  - `:108` — `Override the model (see precedence above)` → ``Override the model (see `## Model selection precedence` in `references/runner-contract.md`)``

  Leave `:28`, `:65`, `:74` alone — those "above" usages are semantic (precedence ordering) or resolve within `agent-selection.md`. Then regenerate adapters and re-run `bash scripts/validate.sh` (the `--check` freshness gate at step 6b is hard-fail). Optionally extend `tests/test_runner_contract_split.py` with an assertion that `agent-selection.md` contains no bare "above"/"below" reference to a heading string that exists only in `runner-contract.md`.
- **References:** `skills/forge-5-loop/references/runner-contract.md:12,66`; backlog item 015 AC1–AC3; `specs/context-efficiency/05-instruction-relocations.md` (R6); pre-split original at `git show ca3da53~1:skills/forge-5-loop/references/runner-contract.md` lines 10, 23, 25
- **Checklist:** CHECK-I08, CHECK-I13, CHECK-I18

### V-002: `Specs Directory Hygiene` second fence uses `$R` with no prelude — `$R` is unset there (PRE-EXISTING)

- **Severity:** error
- **Location:** `references/shared-conventions.md:135-137` (§ Specs Directory Hygiene)
- **Issue:** The Claude-variant fence is `[ -f "<specsDir>/CLAUDE.md" ] || cp "$R/references/templates/specs-hygiene/CLAUDE.md" "<specsDir>/CLAUDE.md"` with no bootstrap prelude. `$R` is assigned inside the *previous* fence (`:127`) and does not survive to a later fence, so this command expands to `cp /references/templates/specs-hygiene/CLAUDE.md …` and fails — the Claude-framed specs-hygiene file is never written. **Pre-existing** (`git blame` → `4e452c7`, 2026-06-19), not introduced by this feature. Reported because it is the only violation of the per-fence prelude convention in the tree, it lives in a file this feature edited, and `check-spec-purity` Rule 5 structurally cannot see it: `check_prelude_identity` verifies that preludes which *exist* are byte-identical; it has no rule for a *missing* one.
- **Suggested fix:** Prepend the canonical two-line prelude to the fence at `references/shared-conventions.md:135`, byte-identical to `:127-128`. Regenerate adapters and refresh fixtures. Separately (higher value than the fix itself): add a Rule-5 companion guard in `scripts/check-spec-purity.py` that fails any fence containing `$R` without an in-fence `R=` assignment — that closes the whole class.
- **References:** `references/shared-conventions.md:126-131` (the correct sibling fence); `scripts/check-spec-purity.py` `check_prelude_identity`; `references/portable-root.md:21-23`
- **Checklist:** CHECK-I13, CHECK-I14

### V-003: R6's `agent-selection.md` gate is true under the shipped default, so the 112 relocated lines still load on every default run

- **Severity:** improvement (charter-claim; owner decision required)
- **Location:** `skills/forge-5-loop/SKILL.md:176` (the capability gate); `references/forge-config-schema.json` → `properties.loopRunner.properties.agentArgument.default`
- **Issue:** The gate reads "Everything below applies **only when** the effective `loopRunner.agentArgument` is present and non-empty," and cites `references/agent-selection.md` (112 lines) inside that gate. The schema default for `agentArgument` is `'--agent {agent}'` — **non-empty**. Verified independently during synthesis:

  ```
  schema default:  agentArgument -> '--agent {agent}'   defaultAgent -> ''
  effective-config on this project resolves agentArgument -> '--agent {agent}'
  ```

  Because `skills/forge-5-loop/SKILL.md:28` resolves the **effective** config (schema defaults merged), the gate is TRUE for every project that does not explicitly blank the field. `05-instruction-relocations.md §3.2` classifies sections {2,3,5} as "CONDITIONAL — `loopRunner.agentArgument` present", and §3.7's drift guard asserts only that the *citation co-occurs with the gate sentinel* — never that the gate is ever false in practice. The split is structurally correct and the invariant is met, but **the instruction-load saving R6 was chartered to deliver does not materialize for the default configuration**: the 112 lines moved file, not load. Sections 3 and 5 are additionally gated behind narrower conditions (non-default agent, non-default flags), so a slice of the win is real; section 2 — the 60-line `## Agent selection` — is not.
- **Suggested fix:** Owner call between two options; do not repair blind.
  - **(a) Record the honest number** *(lower risk, recommended for a behavior-preserving refactor)*: amend `05-instruction-relocations.md §3.1/§3.2` to state that section 2 loads on every default-config run and that R6's measured saving is sections {3,5} only; re-baseline any R6 token claim in `PRD.md`/`tech-spec.md`.
  - **(b) Make the gate bite** *(delivers the charter, changes load behavior)*: narrow `skills/forge-5-loop/SKILL.md:176` to a condition false by default — e.g. gate on `loopRunner.defaultAgent` being non-empty (it **is** `''` by default) or on an explicit user request to choose an agent — and update §3.2's Load-gate column plus the `06-testing-strategy.md` R6 guard's sentinel assertion to match.
- **References:** `specs/context-efficiency/05-instruction-relocations.md §3.1, §3.2 (row 2), §3.7`; `06-testing-strategy.md` (R6 guard); `skills/forge-5-loop/references/agent-selection.md:1-5`
- **Checklist:** CHECK-I23

### V-004: New cross-script constant `_PRODUCTION_STAGES` duplicates `PRODUCTION_STAGES` with no parity guard

- **Severity:** gap
- **Location:** `scripts/epic-manifest.py:66-77` (`_PRODUCTION_STAGES`) vs `scripts/forge-session.py:159-166` (`PRODUCTION_STAGES`)
- **Issue:** Item 020 introduced a second copy of the ordered six production stages in `epic-manifest.py`, whose comment states it "mirrors `PRODUCTION_STAGES` in forge-session.py". They are equal today, so CHECK-I10 passes — but nothing enforces it. This repo has an explicit convention that cross-file duplicated constants get a parity guard, adopted precisely because this class already caused a silent failure: `tests/test_agent_targets_parity.py:1-18` documents that `AGENT_TARGETS` drifted (the test copy stayed a five-tuple after `pi` landed), silently dropping `adapters/pi/` coverage — which item 017 AC8 then required a guard for. The same exposure now exists for stage order: a future stage insertion in `forge-session.py` would leave `epic-manifest.py`'s `_next_production_stage` silently skipping it, **regressing exactly the `_next_command` defect item 020 was filed to fix.** `scripts/forge-session.py:211-212` shows a second instance (`KNOWN_VERIFY_STATUSES` — "epic-manifest.py keeps a byte-identical copy"), also unguarded; that one predates this feature (#148) but the fix is the same test module.
- **Suggested fix:** Add `tests/test_stage_constants_parity.py`, modelled on `tests/test_agent_targets_parity.py`: regex-parse the tuple literal out of each source file with `re` + `ast.literal_eval` (do **not** import the modules — both filenames are hyphenated). Import paths from `tests/_forge_paths.py` (`SCRIPTS`, `read`). Assert (a) the `_PRODUCTION_STAGES = (...)` literal in `scripts/epic-manifest.py` equals the `PRODUCTION_STAGES: Final[tuple[str, ...]] = (...)` literal in `scripts/forge-session.py`, and (b) the `KNOWN_VERIFY_STATUSES` frozenset literals in the two files are equal. Add no `skipif`/`importorskip`. Verify red-by-construction by temporarily reordering `_PRODUCTION_STAGES`, then restore.
- **References:** `tests/test_agent_targets_parity.py`; `scripts/epic-manifest.py:55-77,964-990`; `scripts/forge-session.py:159-166,206-213`; `03-state-verbs.md §15.1`
- **Checklist:** CHECK-I10

### V-005: R4's two call-site invariants (§14 failure handling, mandatory `--epic`) have no drift guard

- **Severity:** gap
- **Location:** no guard file in `tests/`; the invariants live at `references/shared-conventions.md:188` and `:190`
- **Issue:** R4 converted seven hand-edited state writes into subprocess calls, creating a new runtime failure surface. `03-state-verbs.md §14` mandates call-site behavior ("surface the plain `Error:` line from stderr **verbatim**, do **not** proceed to the next step, and do **not** hand-author the JSON as a workaround"), and `shared-conventions.md:188` mandates `--epic "{epic}"` on **every** `state-*` call "in this file and in every skill body". Both hold today — all **21** call sites across the 13 skill bodies plus `shared-conventions.md` carry the `--epic` instruction (0 misses) — but **nothing asserts either one**. Every other R1/R3/R4/R6 boundary received a dedicated drift guard (REQ-MAINT-01's premise; `00-core-definitions.md §10` claims "the drift guards in `06-testing-strategy.md` enforce these mechanically"); these two are the exception. Losing the `--epic` prose is a hard exit-2 break that manifests **only** in epic mode — the least-exercised path, so it would ship undetected. Losing the §14 text means an agent hand-authors JSON around a failed verb, re-introducing exactly the drift REQ-R4-02 exists to remove. Modest severity: the collision case now fails closed (exit 2, byte-intact), so residual risk is a loud break, not silent damage.
- **Suggested fix:** Add `tests/test_state_verb_call_sites.py` (stdlib only, asserting against `skills/` + `references/`):
  1. `test_every_state_verb_call_site_carries_the_epic_instruction` — regex `forge-session\.py"?\s+(state-[a-z]+)` over `skills/*/SKILL.md` + `references/shared-conventions.md`; for each hit assert `--epic` appears in the surrounding section. Pin a non-vacuity floor (`assert n_call_sites >= 21`) so a regex that stops matching cannot pass silently — the technique `test_reference_citations.py::test_the_forward_guard_is_not_vacuous` already uses.
  2. `test_the_verb_failure_protocol_is_still_documented` — assert `references/shared-conventions.md` still carries the three §14 clauses, and that the three operator-facing message prefixes in the §14 table (`no feature directory at`, `refusing to overwrite it`, `atomic write to`) each still appear verbatim in `scripts/forge-session.py`, so the doc table and the script cannot drift apart.
- **References:** `03-state-verbs.md §14, §3.6`; `00-core-definitions.md §10`; `06-testing-strategy.md §8`; `references/shared-conventions.md:188,:190`; `tests/test_state_verbs.py:328-430`
- **Checklist:** CHECK-I17

### V-006: `effective-config` is undocumented outside the script and the specs

- **Severity:** gap (hand-off to forge-6-docs)
- **Location:** `README.md`, `docs/`, `docs-site/src/content/docs/**` (no occurrence); implemented at `scripts/forge-session.py:2726` (argparse) / `:2935` (dispatch)
- **Issue:** R5 adds a user-runnable `forge-session.py effective-config` subcommand, documented only in the module docstring (`:18`, `:90-96`) and `04-effective-config.md`. **Specs are pre-implementation inputs that get archived** — once archived, the only durable record is `--help`. The project's own convention documents user-runnable `forge-session.py` subcommands in `docs/`: `doctor` (`docs/clean-env-repro.md:9,104`, `docs-site/.../pipeline/stage-5-loop.mdx:97`), `discover-feature` (`docs/clean-env-repro.md:96`), `check-epic-base` (`docs/architecture/epic-orchestration/guides/integration.md:74`). `effective-config` is diagnosable-by-user in the same way ("what loopRunner config will the loop actually use?"). Mitigating: forge-6-docs has not run yet, so this is properly a hand-off, not a defect in the loop's output. `CHANGELOG.md` `## [Unreleased]` is also still empty for this entire 20-item refactor.
- **Suggested fix:** During forge-6-docs: (a) add `effective-config` to the diagnostics surface (e.g. `docs-site/src/content/docs/reference/troubleshooting.mdx` and/or `docs/clean-env-repro.md`, alongside the existing `doctor` bullet), showing `python3 <plugin-root>/scripts/forge-session.py effective-config --config ./forge.config.json --json` and stating that it resolves every `loopRunner` field from `references/forge-config-schema.json` defaults merged with project overrides, exits 0 on a missing/corrupt `forge.config.json` (pure defaults) and 2 only when the bundled schema is unreadable; (b) add a `### Added` entry under `## [Unreleased]` in `CHANGELOG.md` covering R1/R3/R4/R5/R6, explicitly noting R2 was scoped out.
- **References:** `04-effective-config.md §2, §10`; `scripts/forge-session.py:18,90-96,1791-1886`; `skills/forge-4-backlog/SKILL.md:37`, `skills/forge-5-loop/SKILL.md:28`
- **Checklist:** CHECK-I20, CHECK-I18

### V-007: Seven items' evidence ACs demand a commit-message location the loop cannot write to

- **Severity:** inconsistency
- **Location:** `specs/context-efficiency/backlog.json` — item 002 AC9, 003 AC2, 004 AC7, 006 AC5+AC8, 013 AC14, 015 AC9+AC11, 016 AC1 (all say "recorded in the commit message")
- **Issue:** Every commit in `ca3da53..8f160ab` has a single-line subject `[rauf] NNN: <title>` and an **empty body** — the loop runner owns the commit and the iteration agent is forbidden from committing (`CLAUDE.md` → "the iteration agent never commits or stages"). So no item could satisfy these ACs as written. Item 003 AC2 is emphatic ("*A transient experiment with no recorded evidence does not satisfy this criterion*"). Read literally, these seven items are marked `done` with unmet ACs. **The substance is fully present, just relocated**: `specs/context-efficiency/.rauf/progress.md` carries every required datum — R1 delta (`:26`), item 003 mutation evidence with quoted assertion texts (`:72-95`), R3 delta (`:119`), R5 delta + measured figures (`:744,:769`), R4/item-013 delta (`:691`), R6 delta + item-006 retry disposition (`:832,:838`), item 016's baseline table (`:1009-1034`). The relocation was conscious — `progress.md:74-76` and `:1011-1012` both state it.
- **Suggested fix:** Do **not** rewrite git history. Record the convention so ACs and artifacts agree. In `06-testing-strategy.md §7.2`, append: *"**Evidence location under a loop run.** The loop runner owns the commit message (`[rauf] NNN: <title>`, no body), so an iteration agent cannot write to it. Any AC phrased 'recorded in the commit message' is satisfied by a per-item section in `{resolvedFeatureDir}/.rauf/progress.md` naming the item id. This applies to items 002/003/004/006/013/015/016, whose evidence lives at progress.md lines 26, 72, 119, 744+769, 691, 832+838, and 1009 respectively."* For future backlogs, change the AC template from "recorded in the commit message" to "recorded in `progress.md` under a heading naming the item id (and in the commit message if the authoring agent owns the commit)".
- **References:** `specs/context-efficiency/.rauf/progress.md:74-76,1009-1034`; `CLAUDE.md` "Autonomous Loop (Rauf)" → Completing rule 10; `git log ca3da53..8f160ab`
- **Checklist:** CHECK-I05, CHECK-I07

### V-008: Write-path feature resolver diverges from the mandated "reuse `_resolve_feature_dir`" contract

- **Severity:** inconsistency
- **Location:** `scripts/forge-session.py:1946-1999` (`_resolve_feature_dir_for_write`) and `:2033`; vs `00-core-definitions.md:168-169`, `03-state-verbs.md:114` and `:252`, `01-architecture-layout.md:117,119`
- **Issue:** The specs state a hard reuse contract: `00-core-definitions.md:168-169` — "`PIPELINE_STATE_FILENAME` and `_resolve_feature_dir` already exist and MUST be reused, not re-implemented"; `03-state-verbs.md:114` lists `_resolve_feature_dir` in the "**Reused verbatim, not re-implemented**" table; §3.4 (`:252`) shows `_load_state_for_write` opening with it. The shipped implementation does **not** call it on the write path — commit `7fd2fb5` (item 018) introduced an independent fail-closed resolver that globs `{specsDir}/*/{feature}` and raises `UsageError` on a multi-candidate match. Relatedly, `01-architecture-layout.md:117` claims `_read_state (L177)` is "reused by every state verb" — the implementation deliberately does *not* reuse it (correctly, per `00 §3.3` and `03 §3.4`), so that row is stale in the opposite direction. **The code is the sounder artifact**: the divergence closes a real exit-0 cross-feature state-corruption hole, and is covered by tests added in the same commit.
- **Suggested fix:** No code change. (1) In `03-state-verbs.md`, replace the `_resolve_feature_dir` row of the §3.1 reuse table (`:114`) with a row for `_resolve_feature_dir_for_write` marked **new (item 018)**, noting it fail-closes on ambiguity rather than delegating to the reader's tolerant resolver; update the §3.4 code block at `:252` to call it, carrying the shipped docstring's rationale verbatim from `scripts/forge-session.py:1949-1965`. (2) In `00-core-definitions.md:168-169`, change to "`PIPELINE_STATE_FILENAME` already exists and MUST be reused; the **write** path uses its own fail-closed resolver (`03-state-verbs.md §3.1`) because the reader's `_resolve_feature_dir` is deliberately tolerant of ambiguity, which is unsafe for a writer." (3) In `01-architecture-layout.md §2.1`, correct `:117` and `:119`, and add `_resolve_feature_dir_for_write(...)  N` between `_write_state` and `_load_state_for_write`.
- **References:** commit `7fd2fb5`; `03-state-verbs.md §3.1/§3.4`; `00-core-definitions.md §3.3`; `01-architecture-layout.md §2.1`
- **Checklist:** CHECK-I03

### V-009: `pipeline-state-schema.json` was edited, but `00 §4` and the `01 §1` manifest still declare it UNCHANGED

- **Severity:** inconsistency
- **Location:** `references/pipeline-state-schema.json` (`currentStage.description`); vs `01-architecture-layout.md:44` and `00-core-definitions.md:193`
- **Issue:** `01-architecture-layout.md:44` marks the file `.` (no change) with the note "R4: **UNCHANGED content**", and `00-core-definitions.md:193` states it "is **unchanged**" as the basis of REQ-R4-03. Commit `8f160ab` (item 020) **did** modify it: the `currentStage` description was rewritten to reclassify `"complete"` as a legacy, never-written enum value. The change is **prose-only** — no enum member, type, or required key changed, and `tests/test_state_schema_conformance.py` pins a description-stripped structural digest unchanged from the pre-R4 baseline, so REQ-R4-03's substance holds. Properly adjudicated in `03-state-verbs.md §15.2`, but a reader of `00 §4` or the `01 §1` manifest alone would conclude the file was never touched, and the `.` marker is factually wrong for CHECK-I01 purposes.
  **Related trade worth surfacing:** item 014 AC5's guard ("a test asserts `pipeline-state-schema.json` is unchanged by R4") was re-based from a raw-byte digest to a description-stripped structural digest. Per §15.2 this is intentional and arguably stronger (a raw-byte pin could only have been re-pinned, proving nothing), but the side effect is that schema **prose** is now unguarded.
- **Suggested fix:** No code change. (a) `01-architecture-layout.md:44` — change the status marker `.` → `M`, note "R4: structurally UNCHANGED (CI source of truth); `currentStage.description` prose amended by item 020 — see `03-state-verbs.md §15.2`". (b) `00-core-definitions.md:193` — "is **unchanged**" → "is **structurally unchanged** (one `description` string amended by item 020; a description-stripped digest is pinned by `tests/test_state_schema_conformance.py`)". (c) Add the same one-line pointer under `00 §4`'s closing paragraph.
- **References:** commit `8f160ab`; `03-state-verbs.md §15.1-§15.3`; `tests/test_state_schema_conformance.py`
- **Checklist:** CHECK-I01, CHECK-I03

### V-010: Conditional `state-note` call is bundled into the same bash fence as the unconditional `state-complete`, gated only by prose

- **Severity:** improvement
- **Location:** `skills/forge-1-prd/SKILL.md:146-155`; identically `forge-2-tech/SKILL.md:207-215`, `forge-3-specs/SKILL.md:157-166`, `forge-4-backlog/SKILL.md:155-164`
- **Issue:** Each of the four stage skills emits one ```` ```bash ```` fence containing the prelude, then `state-complete …`, then `state-note --note "<what the user volunteered>"`. The gate is prose **above** the fence only; there is no inline marker inside it (verified: no `#` comment in any of the four fences). An agent that executes the fence as a unit — which is exactly what a fenced, prelude-carrying, copy-runnable block invites — persists the literal placeholder string `<what the user volunteered>` into the feature's top-level `notes`. That write succeeds at exit 0 (`state-note` accepts any string and never validates content), so nothing surfaces the corruption; it shows up later in the navigator dashboard's "Notes:" line and in forge-5-loop's context. Low probability given the prose, but the failure is silent and persistent.
- **Suggested fix:** In each of the four skills, insert an inline shell comment immediately above the `state-note` invocation **inside** the fence: `# ONLY run the next call if the user volunteered a note in item 2 — otherwise stop here.` Do **not** split into a second fence (that would duplicate the prelude for no gain, against `references/portable-root.md:21-23`). Apply at `forge-1-prd:151`, `forge-2-tech:213`, `forge-3-specs:164`, `forge-4-backlog:162`, then regenerate adapters and confirm `--check` exits 0.
- **References:** `03-state-verbs.md §7`; `references/portable-root.md:21-23`; `00-core-definitions.md §10`
- **Checklist:** CHECK-I22

### V-011: Navigator directs an unconditional 191-line schema read from the display-only dashboard section (PRE-EXISTING)

- **Severity:** improvement
- **Location:** `skills/forge/SKILL.md:53`, under `### 3. Pipeline Status Dashboard`
- **Issue:** Line 53 reads "Write pipeline state conforming to `references/pipeline-state-schema.json`." It sits immediately above "Display a clear, scannable status for the feature:" — a section that **only renders** and performs no write. The navigator body is the universal startup entry: every `/feature-forge:forge` invocation loads it, and the dashboard is its default path. So the instruction pulls a 191-line JSON schema into context on the plugin's most-travelled route for a step with nothing to write. The write it legitimately serves is the `pipelineStatus` path in `### 6. Pipeline Lifecycle Commands` (~L208) — the sanctioned R4 exclusion, which already carries its "Deliberate R4 exclusion" note at ~L210 but no schema pointer. Now also reads inconsistently against `references/shared-conventions.md:186` ("no stage needs to read the schema in order to author state"). **Pre-existing** (identical line at `ca3da53^:skills/forge/SKILL.md:53`), but squarely in this feature's charter and it survived the R4 sweep untouched.
- **Suggested fix:** Delete line 53 from `### 3. Pipeline Status Dashboard` and fold the pointer into the existing R4-exclusion note in `### 6` (~L210): "When authoring one of these `pipelineStatus` writes, conform to `references/pipeline-state-schema.json` — this is the one navigator path that still reads it." Keep the literal citation string intact so `build-adapters.py`'s shared-reference fan-out still resolves it. Regenerate adapters, then `--check` for exit 0.
- **References:** `00-core-definitions.md §5`; `references/shared-conventions.md:186`; `skills/forge/SKILL.md:208-212`
- **Checklist:** CHECK-I22, CHECK-I23

### V-012: `forge-5-loop` skill body at 298/300 lines — 2 lines of headroom

- **Severity:** improvement
- **Location:** `skills/forge-5-loop/SKILL.md`; cap at `scripts/check-spec-purity.py:89-90` (`MAX_BODY_LINES = 300`, `MAX_BODY_WORDS = 5000`)
- **Issue:** Measured with the script's own method (frontmatter-stripped, trailing-blank-trimmed): `forge-5-loop` **298/300 lines, 4600/5000 words**; `forge-0-epic` **292/300**. Both pass, but 2 lines of headroom means the *next* edit to `forge-5-loop` — including forge-6-docs touch-ups, or the V-001 fix if it ever adds a line here — hard-fails CI with no warning. Item 013 already spent its contingency budget on this file (it relocated Step 3c prose into `runner-contract.md` to afford two state-verb fences), so the cheap relocation has been used once.
- **Suggested fix:** Not required for this feature to pass. Before the next edit to `skills/forge-5-loop/SKILL.md`, relocate one more prose block into `references/runner-contract.md` to restore ≥10 lines of headroom — best candidate is the Step 2d "Run mode" paragraph at `:170`, whose verbatim option labels already live in `runner-contract.md` under `## Run mode (Step 2d, rauf)`; replace with a one-line pointer in the shape of the Step 3c pointer at `:206`. Keep the citation intact so the citation-driven fan-out still ships the file.
- **References:** `scripts/check-spec-purity.py:89-90,479-508`; `skills/forge-5-loop/SKILL.md:206`; `skills/forge-5-loop/references/runner-contract.md:25,:197`
- **Checklist:** CHECK-I13, CHECK-I15

### V-013: No `smokeCommand` configured — "clean" cannot mean "it runs"

- **Severity:** improvement (advisory / not-applicable per checklist)
- **Location:** `forge.config.json`, `"smokeCommand": null`
- **Issue:** CHECK-I21 is the only check that proves the assembled product *runs*; with `smokeCommand: null` it degrades to advisory and every future impl-verify on this repo inherits the gap. This repo's runtime is an agent executing bash fences from `skills/**/SKILL.md` that invoke `scripts/*.py` — a genuinely smokeable surface, as demonstrated during this verify (all 8 new verbs driven to exit 0 in one pass). Without a configured command that proof must be re-improvised by hand each time.
- **Suggested fix:** Owner decision — do **not** auto-populate. Candidate: a small `scripts/smoke.sh` running `forge-session.py --help`, `effective-config --json`, and a full `state-*` round-trip against a throwaway temp specs tree, asserting exit 0 and schema-conformant output. If declined, record the decision so future verifiers stop re-raising it.
- **References:** `references/verification-checklists/impl.md` CHECK-I21; `03-state-verbs.md §12`; `06-testing-strategy.md §4`
- **Checklist:** CHECK-I21

### V-014: Three undocumented (backward-compatible) supersets over the specified verb CLI contracts

- **Severity:** improvement
- **Location:** `scripts/forge-session.py:2752` (`--path`), `:2775` + `:2273`/`:2332-2335` (`--status` default and the `--resumable --status complete` guard), `:2550-2553` (`_print_state_artifact`); vs `03-state-verbs.md:512, :521-522, :561, :621-626, :747`
- **Issue:** The shipped CLI is a strict superset of the specified one in three places, none recorded in the spec: (1) `state-artifact --path` is **repeatable** (`action="append", dest="paths"`) where §5.1 declares a single value; single-`--path` behaviour is identical and no call site passes more than one. (2) `--status` default is `None`, not `"complete"` (`status or _DONE_STATUS` at `:2353`) — semantically identical, but the sentinel enables a **new** guard the spec does not mention: `--resumable --status complete` raises `UsageError`, an exit-2 condition absent from §6.8. (3) `state-artifact`'s human printer prints `artifact(s): {comma-joined} ({N} total)` rather than §5.3's single-path form.
- **Suggested fix:** No code change — the supersets are safe and better. Update `03-state-verbs.md`: (a) §5.1 `:512` → `action="append", dest="paths"` with metavar/help, retype the §5.2 handler to `paths: list[str]`, update the §5.3 sample printer at `:561`; (b) §6.1 `:621` → `default=None` with a note that `None` means "flag absent" and the handler falls back to `"complete"`, retype §6.4 `:747` to `status: str | None = None`, and add to §6.8: "`--resumable` combined with `--status complete` → `UsageError` (contradictory flags)".
- **References:** commits `c4f0531` (008), `d6a549d` (009); `tests/test_state_verbs.py`
- **Checklist:** CHECK-I03

### V-015: Spec §6.3's `_cascade_staleness` listing omits the bool guard the implementation carries

- **Severity:** improvement (minor)
- **Location:** `03-state-verbs.md:722` vs `scripts/forge-session.py:2258`
- **Issue:** §6.3 presents `_cascade_staleness` as a verbatim code block, and item 019 AC4 asks that it match the implementation. The `_CASCADE_TARGETS` block does match after 019; the function body no longer does by one condition. Spec reads `if isinstance(recorded, int) and recorded < new_version:`; shipped code reads `if isinstance(recorded, int) and not isinstance(recorded, bool) and recorded < new_version:` (JSON `true` would otherwise be treated as version 1). Divergence is pre-existing to 019, harmless behaviorally, but a reader treating §6.3 as the contract would re-implement a subtly weaker guard.
- **Suggested fix:** In `03-state-verbs.md §6.3`, change `:722` to include `and not isinstance(recorded, bool)`, and add one prose clause: "the `bool` exclusion keeps a JSON `true` from being read as version 1." No code change.
- **References:** `scripts/forge-session.py:2225-2261`; item 019 AC4
- **Checklist:** CHECK-I05

### V-016: Two test docstrings cite feature-specific spec/state artifacts that get archived

- **Severity:** improvement
- **Location:** `tests/test_reference_citations.py:13-19` (module docstring); `tests/test_always_loaded_surface.py:47` (comment)
- **Issue:** `test_reference_citations.py` sources its baseline commit hash from "`specs/context-efficiency/.pipeline-state.json` under `stages['forge-4-backlog'].commitHash`", and `test_always_loaded_surface.py:47` cites "`specs/context-efficiency/.reference/REMEASURE-0.13.0.md` §Non-regression". Both are permanent test files pointing at per-feature artifacts that get archived once the feature ships, after which the provenance note cannot be resolved. The shipped surface (`skills/`, `scripts/`, `agents/`, `references/`, `adapters/`) is **clean** of such citations — only these two tests carry them, and both are provenance notes rather than executable dependencies, so nothing breaks at runtime.
- **Suggested fix:** Make each note self-contained. In `test_reference_citations.py`, replace the pointer-to-state-file phrasing with the literal hash already inline (`9a29e846ed510c3b245876a9bf4cc73b8cb60951`) and drop the "the hash recorded in `specs/…`" clause. In `test_always_loaded_surface.py:47`, inline the measured 0.13.0 non-regression number and cite the CHANGELOG 0.13.0 entry (or the commit) instead of the `.reference/` path.
- **References:** `references/templates/specs-hygiene/AGENTS.md` (the "specs are pre-implementation artifacts" convention)
- **Checklist:** CHECK-I13, CHECK-I19

### V-017: `test_reference_citations.py`'s pinned provenance count (134) is stale — the tree now resolves 140

- **Severity:** improvement
- **Location:** `tests/test_reference_citations.py:13-19` (module docstring, "Regex provenance")
- **Issue:** The docstring states the pattern "resolves **134** with zero misses" against the post-R1..R6 tree. Re-running the module's own `_citations()` logic over the current tree yields **140** literal citations, 0 unresolved — the count moved again after that comment was written (items 015/016). The total is deliberately not pinned in code (`MIN_EXPECTED_CITATIONS = 100` is a floor), so this is **not** a test failure and not a correctness defect — but the docstring is the guard's stated non-vacuity provenance, and an annotation that no longer reproduces weakens the "verified, zero misses" claim a maintainer would rely on before touching the regex.
- **Suggested fix:** Update the figure from `134` to `140` and note the tree it was measured on (post-item-016, 2026-07-29). Do **not** convert it into an assertion — `MIN_EXPECTED_CITATIONS` is the correct instrument.
- **References:** `06-testing-strategy.md §5`
- **Checklist:** CHECK-I16

### V-018: validate.sh's traceability PASS covers only 12 of this feature's 29 requirements

- **Severity:** improvement
- **Location:** `scripts/validate.sh` step 8 output vs `specs/context-efficiency/PRD.md`
- **Issue:** validate.sh reports `PRD: …/context-efficiency/PRD.md (12 requirements) … All requirements covered.` The PRD declares **29** unique REQ IDs. The 17 invisible ones are exactly the R-unit families — `REQ-R1-01..05`, `REQ-R2-01/02`, `REQ-R3-01`, `REQ-R4-01..04`, `REQ-R5-01/02`, `REQ-R6-01..03` — the feature's entire core content. Root cause is the **pre-existing, separately-tracked** `scripts/validate-traceability.py` bug (`REQ-[A-Z]+-\d+` cannot match the digit in `R1`), explicitly not this feature's defect. What *is* worth recording: this feature's traceability claims silently depend on it. `TRACEABILITY.md:13-17,42,56` and `06-testing-strategy.md`'s Requirement Coverage table both assert coverage rows for `REQ-R1-01..05`, `REQ-R4-03`, `REQ-R6-01/02` — and no automated gate has ever checked a single one. The green traceability line is materially weaker than it reads **for this feature specifically**.
- **Suggested fix:** No code change required in this feature. Add a one-line note to `TRACEABILITY.md` stating that rows with numbered category segments (`REQ-R*-NN`) are **not** machine-verified by `validate-traceability.py` and were confirmed by review only, cross-referencing the upstream validator bug. If the owner wants it closed properly, the upstream fix is widening the pattern to `REQ-[A-Z][A-Z0-9]*-\d+` — but that belongs to the validator's own issue, and would change reported requirement counts for `epic-orchestration` and `forge-bootstrap` too.
- **References:** `PRD.md` (29 REQ IDs); `TRACEABILITY.md:13-17,42,56`; `scripts/validate.sh` step 8
- **Checklist:** CHECK-I16

---

## Fix Execution Plan

### User Decisions Required

1. **V-003 (R6 gate)** — choose (a) record the honest saving in the specs, or (b) narrow the gate so it is false by default. Option (b) changes which instructions load on a default run and touches the R6 invariant and its drift guard; it must not be applied without the owner's word.
2. **V-002 (pre-existing missing prelude)** — fix in this pass (touches `references/shared-conventions.md` + all six adapter bundles + fixtures), or file as a separate issue. The companion `check-spec-purity` rule that closes the class is arguably the higher-value half.
3. **V-007 (evidence-location ACs)** — record the `progress.md` convention as sanctioned (recommended; the substance already exists and is durable), versus re-opening seven items to satisfy a location that cannot be written. No history rewrite is proposed either way.
4. **V-013 (smokeCommand)** — configure one, or record "no smoke command by design" so it stops being re-raised.
5. **V-018 (traceability)** — record the exposure in `TRACEABILITY.md` only (recommended; keeps scope clean), or also fix the upstream validator pattern.
6. **Spec-reconciliation class (V-008, V-009, V-014, V-015)** — `specs/CLAUDE.md` states specs are not kept in sync with code post-ship. If that rule stands, all four are legitimately WON'T-FIX with no loss of correctness; the code is the better artifact in every case. Confirm before spending a fix pass on them.

### Execution Steps

#### Step 1: Repair the R6 dangling cross-references
- **Files:** `skills/forge-5-loop/references/agent-selection.md` (`:10`, `:91`, `:108`)
- **Addresses:** V-001
- **Action:** Apply the three verbatim string replacements in V-001. Do not touch `:28`, `:65`, `:74`.
- **Depends on:** none

#### Step 2: Mark the conditional `state-note` call inside its fence
- **Files:** `skills/forge-1-prd/SKILL.md:151`, `skills/forge-2-tech/SKILL.md:213`, `skills/forge-3-specs/SKILL.md:164`, `skills/forge-4-backlog/SKILL.md:162`
- **Addresses:** V-010
- **Action:** Insert `# ONLY run the next call if the user volunteered a note in item 2 — otherwise stop here.` immediately before the `state-note` line, inside the existing fence. Add nothing else; do not split the fence or duplicate the prelude.
- **Depends on:** none

#### Step 3: Relocate the navigator's schema pointer off the dashboard path
- **Files:** `skills/forge/SKILL.md` (delete `:53`; extend the R4-exclusion note at ~`:210`)
- **Addresses:** V-011
- **Action:** Per V-011's suggested fix. Keep the literal citation string `references/pipeline-state-schema.json` intact so the shared-reference fan-out still resolves it.
- **Depends on:** none

#### Step 4: (conditional on decision 2) Add the missing prelude to the CLAUDE.md hygiene fence
- **Files:** `references/shared-conventions.md:135`
- **Addresses:** V-002
- **Action:** Insert the canonical two-line bootstrap prelude as the first two lines inside the fence, copied byte-identically from `:127-128`. Optionally add the `check-spec-purity` companion rule that fails any fence using `$R` without an in-fence `R=` assignment.
- **Depends on:** owner decision

#### Step 5: Regenerate adapters and re-run the gate
- **Files:** `adapters/**`, `tests/fixtures/**`
- **Addresses:** propagation for V-001, V-002, V-010, V-011
- **Action:** Run `python3 scripts/build-adapters.py`, then `python3 scripts/build-adapters.py --check` (must exit 0), then `bash scripts/validate.sh` (step 6b is hard-fail) and `ruff check scripts/ eval/`. Confirm all six bundles carry the corrected files.
- **Depends on:** Steps 1–4

#### Step 6: Add the two missing drift guards
- **Files:** new `tests/test_stage_constants_parity.py`; new `tests/test_state_verb_call_sites.py`
- **Addresses:** V-004, V-005
- **Action:** Create both modules exactly as specified in V-004 and V-005 — stdlib only, imports from `tests/_forge_paths.py`, non-vacuity floors, **no** `skipif`/`importorskip`/`is_file()` gates (`test_always_loaded_surface.py::test_the_hook_guards_cannot_degrade_to_a_skip` documents why that construct is banned in this feature's guards). Verify each is red-by-construction by temporarily introducing the violation it targets, then restore and confirm `git diff --stat` is empty.
- **Depends on:** none

#### Step 7: Correct the two test provenance notes
- **Files:** `tests/test_reference_citations.py` (docstring `:13-19`), `tests/test_always_loaded_surface.py:47`
- **Addresses:** V-016, V-017
- **Action:** Update the citation count `134` → `140` with its measurement date; drop the pointer-to-state-file clause in favour of the literal hash; inline the REMEASURE figure and cite the CHANGELOG/commit instead of the `.reference/` path. Comment-only edits; no assertion changes.
- **Depends on:** none

#### Step 8: (conditional on decisions 1, 3, 5, 6) Spec and record-keeping reconciliation
- **Files:** `06-testing-strategy.md §7.2` (V-007), `TRACEABILITY.md` (V-018), `05-instruction-relocations.md §3.1/§3.2` + R6 token claims (V-003 option a), `03-state-verbs.md §3.1/§3.4/§5/§6/§6.3` (V-008, V-014, V-015), `00-core-definitions.md:168-169,:193` + `01-architecture-layout.md:44,:117,:119` (V-008, V-009)
- **Addresses:** V-003, V-007, V-008, V-009, V-014, V-015, V-018
- **Action:** Apply per each finding's suggested fix, gated on the owner's answers. Spec-only; no adapter regeneration (specs are outside the canonical surface).
- **Depends on:** owner decisions

#### Step 9: Hand off documentation coverage to forge-6-docs
- **Files:** `docs-site/src/content/docs/reference/troubleshooting.mdx` and/or `docs/clean-env-repro.md`; `CHANGELOG.md`
- **Addresses:** V-006
- **Action:** Document `forge-session.py effective-config` alongside the existing `doctor` diagnostic (command line, what it resolves, its 0/2 exit contract), and add the `## [Unreleased]` entry covering R1/R3/R4/R5/R6, noting R2 was scoped out.
- **Depends on:** belongs to the forge-6-docs stage, not this fix pass

#### Step 10: (conditional on decision 4) Configure a smokeCommand
- **Files:** `forge.config.json`, optionally new `scripts/smoke.sh`
- **Addresses:** V-013
- **Action:** If opted in, author the agreed smoke script and set `smokeCommand`; confirm exit 0 from a clean checkout. If declined, record the decision where future verifiers will see it.
- **Depends on:** owner decision

#### Step 11: Buy back line-cap headroom (optional, before the next forge-5-loop edit)
- **Files:** `skills/forge-5-loop/SKILL.md`, `skills/forge-5-loop/references/runner-contract.md`
- **Addresses:** V-012
- **Action:** Relocate the Step 2d "Run mode" paragraph at `:170` into `runner-contract.md` under the existing `## Run mode (Step 2d, rauf)` heading, replacing it with a one-line pointer. Re-measure to confirm ≥10 lines of headroom. Regenerate adapters.
- **Depends on:** Step 5 (to avoid two adapter regenerations)
