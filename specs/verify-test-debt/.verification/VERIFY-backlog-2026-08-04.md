# Verification Report: verify-test-debt (backlog)

Date: 2026-08-04
Pipeline Stage: forge-4-backlog (complete, v1) — in-stage auto-verify, clean-room, require-clean
Verified Stage Version: 1
Dispatch: 4 parallel `forge-verifier` instances over disjoint CHECK-ID slices (backlog mode, 27 checks)

Artifacts Reviewed:
- `specs/verify-test-debt/backlog.json` (16 items)
- `specs/verify-test-debt/` — `PRD.md`, `tech-spec.md`, `TRACEABILITY.md`, `00-core-definitions.md`, `01-architecture-layout.md`, `02-canon-and-prose-guard.md`, `03-machinery-trim.md`, `04-production-validations.md`, `05-coverage-backfill.md`, `06-brittleness-batch.md`, `07-testing-strategy.md`, `.pipeline-state.json`
- `forge.config.json`, `.rauf/backlog.schema.json`, `AGENTS.md`
- Repo under test: `scripts/validate.sh`, `scripts/build-adapters.py`, `scripts/forge-session.py`, `scripts/check-spec-purity.py`, `eval/run-compliance-eval.py`, `tests/`, `skills/forge-0-epic/SKILL.md`

Checks Executed: **27 of 27** — 23 pass, 2 fail, 2 not-applicable.

| Slice | CHECK-IDs | Result |
|---|---|---|
| schema/enum + freshness + lifecycle | B01–B06, B26, B27 | 6 pass, B26 fail, B27 n/a |
| item scoping & acceptance criteria | B11–B14, B25 | 1 pass, 4 fail-with-advisory |
| dependency / ordering sanity | B15–B19 | 3 pass, B18 fail, B19 fail |
| spec coverage & traceability + completeness | B07–B10, B20–B24 | 7 pass, B20/B21 n/a |

**Independent confirmation.** `rauf-stable backlog validate . --backlog specs/verify-test-debt --specs-dir ./specs --json` → `{"valid": true, "findings": []}`, exit 0. Draft-7 validation against `.rauf/backlog.schema.json` → 0 errors. **Every finding below is something the deterministic validator cannot catch.**

## Not-applicable checks (honest, not manufactured)

- **CHECK-B20 (package scaffold)** — `01-architecture-layout.md` §1: "This feature adds **no** directory, package, module, class, CLI verb, flag, exit code, or JSON payload key." §2's tree is entirely `EDIT`/`REWRITE`/`TRIM`/`REGENERATED`. A scaffold item would be fabricated work.
- **CHECK-B21 (shared types / error hierarchy)** — no new types, no new error hierarchy; `00` §8 records the *existing* exit-2 contract as a constraint to preserve. The two structural analogues that do exist are covered: `_validated_findings_file` signature widening (item 003 AC1–AC2) and the `CANONICAL_EXIT_SITES` export constraint (005 AC7, 006 AC5–AC6, 016 AC7).
- **CHECK-B27 (lifecycle contradiction)** — scanned all 16 items for lifecycle vocabulary. The single hit is "live" in item 001 used as an ordinary verb. Not-applicable per the checklist, never a hard fail.

## Summary

- Total findings: **15**
- Errors: **1**
- Gaps: **2**
- Inconsistencies: **4**
- Improvements: **8**

**Blocking findings: 3** (V-001 error, V-002 gap, V-003 gap). The remaining 12 are advisory.

The three blocking findings share one root cause and one consequence: **`adapters/` is generated from `scripts/` runtime helpers as well as from canon, and the backlog does not know it.** V-001 states the false rule, V-002 is the two items that will red-gate because of it. V-003 is separate — the closeout gate's dependency closure omits three items whose work it reconciles against.

---

## Findings

### V-001: Item 001's notes assert a false exclusivity rule that will actively steer items 002/003 away from regenerating adapters

- **Severity:** error
- **Location:** `specs/verify-test-debt/backlog.json`, item `001`, `notes` (first sentence)
- **Issue:** Item 001's notes read: *"This is the only item that touches `skills/` or `references/`, **so it is the only one that must regenerate adapters.**"* The premise is true; the conclusion is factually wrong. `adapters/` is also generated from six `scripts/` runtime helpers — `scripts/build-adapters.py:314-321`:

  ```python
  RUNTIME_HELPERS: tuple[str, ...] = (
      "forge-root.sh", "forge-init.sh", "epic-manifest.py",
      "forge-session.py", "validate-traceability.py", "forge-bootstrap.py",
  )
  ```

  The emitter copies each from `repo_root / "scripts" / helper` into `adapters/<agent>/scripts/<helper>` on every build (`build-adapters.py:1408-1418`), asserting byte-identity via `_assert_byte_identical`. Confirmed on the live tree: `adapters/{claude,codex,copilot,cursor,gemini}/scripts/forge-session.py` are byte-identical to `scripts/forge-session.py` (279,600 bytes each); the `pi` mirror differs only by the documented `/feature-forge:` → `/skill:` substitution (`build-adapters.py:1650-1662`).

  `scripts/forge-session.py` is the file items 002 and 003 modify. This note is not inert narration — backlog `notes` are read by the autonomous loop as authoritative guidance, and this sentence makes an explicit claim *about other items*. An agent working item 002 that reads it concludes no regeneration is required, then either red-gates on `build-adapters.py --check` with no idea why, or "fixes" the drift by hand-editing `adapters/` — which `01-architecture-layout.md` §6.1 (C-01) forbids. The decision-bearing consequence is what puts this above the severity floor for a notes field.
- **Suggested fix:** Replace that clause with: *"This is the only item that touches `skills/` or `references/`, but it is **not** the only item that must regenerate adapters — `scripts/forge-session.py` is a `build-adapters.py` runtime helper copied byte-identically into every bundle, so items 002 and 003 must regenerate too."* Keep the rest of the note (the 0664 umask caveat and the `test_capability_determination_prose.py` guidance) verbatim.
- **References:** `scripts/build-adapters.py:310-321, 1404-1418`; `01-architecture-layout.md` §6.1; `AGENTS.md:21` (carries the same narrow framing — "Run this whenever you edit canon (`skills/`, `agents/`, `references/`)" — and should be corrected alongside, though it is outside the backlog artifact)
- **Checklist:** CHECK-B26

### V-002: Items 002 and 003 edit an adapter source but never regenerate `adapters/`, so their own `validate.sh` acceptance criterion cannot pass

- **Severity:** gap
- **Location:** `specs/verify-test-debt/backlog.json`, items `002` (description steps 1–3, acceptanceCriteria) and `003` (description steps 1–4, acceptanceCriteria)
- **Issue:** The configured `testCommand` is `bash scripts/validate.sh`, whose step 6b is a generated-artifact freshness gate: `scripts/build-adapters.py --check` regenerates every bundle into a temp dir and `diff -r`s it against the committed `adapters/` tree (`validate.sh:177`; `build-adapters.py:2106-2153`). `adapters/` is tracked in git (`.gitignore` excludes only `.venv-adapters/`, `adapters.tmp-*/`, `installer/adapters/`), and `python3 scripts/build-adapters.py --check` exits 0 on the current tree — the gate is live and currently green.

  Item 002 modifies `cmd_state_complete`; item 003 modifies `_validated_findings_file` and `cmd_state_artifact` — both in `scripts/forge-session.py`, both therefore staling all six mirrors. Neither item's description nor acceptance criteria mentions `adapters/` or `build-adapters.py` at all, yet both end with:

  > `bash scripts/validate.sh` reports "All checks passed!"

  That criterion is unsatisfiable as written — `validate.sh` will emit `FAIL: adapters/ is out of date — run 'python3 scripts/build-adapters.py' and commit the result`. This is exactly the CHECK-B26 step-2/3 failure mode: an item edits a `--check`-gated artifact's *source* with no regeneration scheduled in its own execute + commit sequence.

  Aggravating: item 001's notes (V-001) and `AGENTS.md:21` both tell the agent regeneration is not needed here. Item 016 does run a full regeneration at feature close, so the feature *closes* consistent — but 002 and 003 are gated individually and land mid-sequence.
- **Suggested fix:** Add a final numbered step to **both** items' descriptions: *"Run `python3 scripts/build-adapters.py` and commit all six mirrors (`adapters/{claude,codex,copilot,cursor,gemini,pi}`) in this same commit. `scripts/forge-session.py` is one of `build-adapters.py`'s `RUNTIME_HELPERS` — copied byte-identically into every bundle — so `scripts/validate.sh`'s `build-adapters.py --check` gate fails on a `scripts/forge-session.py` edit not accompanied by a regeneration. Do NOT hand-edit anything under `adapters/`."* And insert, immediately before each item's existing `bash scripts/validate.sh` criterion: *"`python3 scripts/build-adapters.py --check` exits 0, and all six adapter mirrors are staged in the same commit as the `scripts/forge-session.py` change, with no file under `adapters/` hand-edited."*

  No other item needs this: 004 touches `eval/run-compliance-eval.py`, 005–015 touch only `tests/`, and 016 already regenerates. Item 011 *scans* `scripts/forge-session.py` from a test but does not modify it.
- **References:** `scripts/validate.sh:165-188`; `scripts/build-adapters.py:310-321, 1404-1418, 1650-1662, 2106-2153`; `01-architecture-layout.md` §6.1, §9; `04-production-validations.md` §9; `AGENTS.md:21`; backlog item 016
- **Checklist:** CHECK-B26

### V-003: Item 016, the final gate and suite-count reconciliation, does not depend on items 002, 003, or 004

- **Severity:** gap
- **Location:** `specs/verify-test-debt/backlog.json`, item `016`, `dependsOn: ["015"]`
- **Issue:** Item 016 is the whole-feature closeout, and its acceptance criteria include *"The actual collected suite count is compared against the 1799 expected by `07` §5.4"* and *"Every countable criterion in `07` §6 is confirmed satisfied"*. Its transitive closure is `{001, 005, 006, 007, 008, 009, 010, 011, 012, 013, 014, 015}` — **`002`, `003`, and `004` are absent.**

  Those three contribute 10 of the 15 collected items in the `+15 REQ-COV backfill` term of the 1799 derivation (`07` §5.4 / §5.2 assumption 1: REQ-COV-02 → 2 ids in item 002; REQ-COV-06 → 7 ids in item 003; REQ-COV-03 → 1 id in item 004). 002 and 003 are also the only two production changes in the feature.

  rauf's `selectNextItem` requires only an item's *declared* deps to be `done`, so item 016 becomes eligible the moment 015 completes, regardless of 002/003/004. On the nominal schedule those land early by priority tie-break, so this does not bite on the happy path — but if any is failed, blocked, reset, or hand-deferred, the loop walks 006→015 and then runs 016, which reports `validate.sh` green (the missing work is purely additive) and reconciles the suite count against 1799 while short by up to 10 items, closing the feature on an unfinished tree. Item 016's own criterion *"divergence beyond a handful of items is explained in the commit message"* is precisely the signal that would be misread as expected drift.
- **Suggested fix:** Set item 016's `"dependsOn": ["003", "004", "015"]` (003 pulls 002 in transitively). Verified: this does not lengthen the critical path — `depth(003)=2`, `depth(004)=1`, both far below `depth(015)=12`; max chain depth stays **13**.
- **References:** `07-testing-strategy.md` §5.2 (assumption 1: 2 + 5 + 8 = 15 collected across 10 functions), §5.4, §6; `01-architecture-layout.md` §5.2 step 7; `rauf` `packages/core/src/backlog.ts::selectNextItem`
- **Checklist:** CHECK-B18

### V-004: The `06`-workstream items that rewrite `tests/test_state_verbs.py` do not depend on the `05`-backfill items that add to it

- **Severity:** inconsistency
- **Location:** `specs/verify-test-debt/backlog.json`, items `011`–`014` (the `dependsOn` chain rooted at `010`); most acutely item `014`
- **Issue:** `01-architecture-layout.md` §5.4 makes add-before-rewrite a binding merge order and names `test_state_verbs.py` explicitly (`05` backfill first, then `06` brittleness + dedup). Items 002 and 003 are `05`-backfill contributions to that file (`05` §3.2, §7.2) — but neither is in the transitive closure of 011, 012, 013, or 014, all of which rewrite existing tests in that same file. The backlog encodes this rule for the *other* backfill item in the file (`011 ← 010`, with item 010's note citing `01` §5.4 by name) and for the pair `003 ← 002`, so the same stated rationale was applied inconsistently.

  Sharpest instance: item 014's own note says *"item 002 adds the import — confirm it is present before adding decorators, since omitting it is a collection-time `NameError` that presents as the whole file vanishing from the run"* — a hard, named symbol dependency (`import pytest`) the graph does not encode. As with V-003, the default priority/lexicographic tie-break happens to schedule 002 and 003 first, so this is latent rather than live; it becomes real on any blocked/failed/re-run path.
- **Suggested fix:** Set item 011's `"dependsOn": ["003", "010"]`. This puts both 002 and 003 in the closure of 011–015, satisfying `01` §5.4 for `test_state_verbs.py` and guaranteeing `import pytest` exists before item 014 adds `@pytest.mark.parametrize`. Verified: `depth(003)=2 < depth(010)=7`, so max chain depth is unchanged at **13**. Combined with V-003's edge, item 016's closure then covers all 15 other items.
- **References:** `01-architecture-layout.md` §5.4; items 003, 010, 014 notes; `05-coverage-backfill.md` §3.2, §7.2
- **Checklist:** CHECK-B18

### V-005: Priority inversion — item 016 is priority 1 but depends on a priority-3 item

- **Severity:** inconsistency
- **Location:** `specs/verify-test-debt/backlog.json`, item `016` (`priority: 1`, `dependsOn: ["015"]` at `priority: 3`)
- **Issue:** The only priority violation in the graph — every other edge has a dependency at equal or higher priority (`003←002` 2←2, `005←001` 1←1, `006←005` 2←1, the 007–010 run 2←2, `011←010` 3←2, 012–015 3←3). Item 016 is by construction the *last* item (the closeout gate) yet carries the highest priority in the file, the same rank as canon item 001 and guard rewrite 005. `selectNextItem` filters on satisfied deps before sorting by priority, so under rauf this metadata is inert — but it misrepresents the item to every human reader, to `rauf backlog list`, and to any consumer that ranks by priority without consulting the graph.
- **Suggested fix:** Change item 016's `priority` from `1` to `3`, matching its position at the tail of the chain and the 011–015 band it follows. Realized execution order is identical.
- **References:** `rauf` `packages/core/src/backlog.ts::selectNextItem` (priority ascending, tie-break lexicographic id, applied only after dependency filtering)
- **Checklist:** CHECK-B19

### V-006: Item 007's bare section pointers mis-anchor to `00-core-definitions.md`; five resolve to real-but-wrong sections

- **Severity:** inconsistency
- **Location:** `specs/verify-test-debt/backlog.json`, item `007` (description, steps 2–5 and the closing "Order within the file" line); also item `014` (description, "Corrupt-file family (§8.3…)")
- **Issue:** Item 007's description names `03-machinery-trim.md` §4.1 in step 1, then `00-core-definitions.md` §4.2 in the same step. Every subsequent bare `§` in the item — §4.2, §4.3, §4.4, §4.5, §4.6, §5, §5.4, §5.5, §6, §7, and the two in "Order within the file: §4 before §6, §4 before §5.4" — is intended for `03`, but the nearest preceding file token is `00`. Five resolve to a real, *different* section in `00`, so the mis-resolution is silent rather than an obvious dead pointer:

  | Bare ref | Intended (`03`) | Silently resolves to (`00`) |
  |---|---|---|
  | §4.2 | Fence-aware heading index | "`SURFACES_WITHOUT_PROSE` is deleted, not shrunk" |
  | §4.3 | Fenced blocks that hold a call | Non-vacuity floor |
  | §5 | Consequent Deletions (REQ-TRIM-04/-05) | Meta-Guard Declaration Format (REQ-GUARD-05) |
  | §6 | The Replacement Mutation Control | The Structural Region Model (REQ-TRIM-03) |
  | §7 | Preserved Unchanged (REQ-TRIM-06) | Validator Contracts |

  (§4.4, §4.5, §4.6, §5.4, §5.5 do not exist in `00` at all, so those fail loudly.) `§6` is the worst case — `00` §6 is *topically adjacent* to item 007's own subject.

  The same defect appears once in item 014: *"**40-hex hash family** (`06-brittleness-batch.md` §8.2; roster in `00-core-definitions.md` §9.2)"* sets the anchor to `00`, then *"**Corrupt-file family** (§8.3; roster in `00` §9.3)"* — bare `§8.3` is intended as `06` §8.3 but resolves to `00` §8.3, "Diagnostic preservation (REQ-OBS-01)".

  This is the implicit back-reference CHECK-B12 names as a defect: the loop runs each item in a fresh context, and a fresh agent has no conversational anchor to recover the intended file. Advisory rather than blocking because the item's own inline titles quote the `03` section titles verbatim, and 007 AC2/AC6 independently enumerate the deletions and the required replacement mutation control, so a mis-read is caught at acceptance.
- **Suggested fix:** In item 007's description, qualify every bare `§` with `` `03` `` (12 substitutions: §4.2, §4.3, §4.4, §4.5, §4.6, §5, §5.4 ×2, §5.5, §6 ×2, §7, §4 ×2). Do **not** touch item 007's `notes` — its `00` §6.4/§6.2 and `03` §4.8/§4.7 references are already correctly anchored. In item 014, change ``**Corrupt-file family** (§8.3;`` to ``**Corrupt-file family** (`06` §8.3;``. Change no section numbers.
- **References:** `03-machinery-trim.md` §4–§7; `00-core-definitions.md` §4–§7, §8.3; `06-brittleness-batch.md` §8.3
- **Checklist:** CHECK-B12

### V-007: Items 002 and 003 name a test-wrapper set that contradicts the verbatim code in the spec sections they cite

- **Severity:** inconsistency
- **Location:** `specs/verify-test-debt/backlog.json`, item `002` (description step 4) and item `003` (description step 4)
- **Issue:** Both items instruct *"Reuse that file's `_run` / `_feature_dir` / `_state_of` wrappers"* for tests they simultaneously mandate be written per `05-coverage-backfill.md` §3.2 / §7.2. The verbatim test code in those very sections uses a **different** wrapper set: both §3.2 and §7.2 use `_run`, `_seed`, `_state_bytes`. Neither uses `_feature_dir`; neither uses `_state_of`.

  All five helpers exist in `tests/test_state_verbs.py` (`_feature_dir` L44, `_run` L51, `_state_of` L58, `_seed` L653, `_state_bytes` L1708), so an agent following the item's roster literally gets working-but-wrong code: it hand-rolls stage seeding instead of calling `_seed`, and — more consequentially — `_state_of` returns a **parsed dict**, which cannot establish item 003 AC4/AC5's requirement that the state file be left *byte-identical*. That is precisely the semantic-vs-byte distinction item 009 AC4 exists to prevent elsewhere in this backlog.

  Contrast item 009, whose wrapper roster (`_exit_project`/`_stage_exit`/`_exit_ok`/`_tech_state`/`_read_entry`, plus the explicit "do NOT use `_rank`/`_rank_proc`/`_write_state`/`_completed_prd_state`" warning) verified line-by-line correct against `tests/test_auto_verify.py`; and item 010, whose `_exit`/`_project` roster matches `05` §8.3's code. Advisory rather than blocking because both items also point at spec sections containing literal, complete code the agent can copy.
- **Suggested fix:** Item 002 step 4 → *"Reuse that file's own `_run` / `_seed` / `_state_bytes` wrappers, as `05` §3.2's code does."* Item 003 step 4 → *"Reuse that file's `_run` / `_seed` / `_state_bytes` wrappers, as `05` §7.2's code does — the byte-identity assertions in AC 4 and AC 5 require `_state_bytes`, not the dict-returning `_state_of`."* Leave both items' "Do NOT use `tests/conftest.py`'s `run_cli` fixture" sentences unchanged (that warning is correct — `conftest.py`'s `run_cli` is hardcoded to `scripts/epic-manifest.py`). Do not modify items 009 or 010.
- **References:** `05-coverage-backfill.md` §3.2, §7.2; `tests/test_state_verbs.py` L44, L51, L58, L653, L1708; backlog items 003 AC4/AC5, 009 AC4
- **Checklist:** CHECK-B12, CHECK-B13

### V-008: Item 011 bundles four requirements across four files at `estimatedIterations: 1`

- **Severity:** improvement
- **Location:** `specs/verify-test-debt/backlog.json`, item `011` (title, description, `estimatedIterations`)
- **Issue:** Item 011 lands REQ-BRIT-01, -03, -05 and -06 across four files (`tests/test_auto_verify.py`, `tests/test_stage_exit.py`, `tests/test_state_verbs.py`, `tests/test_state_schema_conformance.py`), requires reading ten `06-brittleness-batch.md` sections (§2, §2.2, §2.4, §4, §4.2, §6, §6.2, §6.3, §7, §7.2), and carries an AC (AC3) demanding a two-sided mutation demonstration. It is budgeted at `estimatedIterations: 1` — the same as item 012 (two scanner replacements, one file) and *less* than item 013 (5 sites / 11 comparisons, two files, est 2) and item 014 (one requirement-half, one file, est 2). With `loopIterationMultiplier: 1.5`, a 1-iteration estimate gives this the tightest budget of any multi-file item. Not a scoping error — the four sub-edits are genuinely independent, touch no shared symbol, and `06` §2.2/§6.2/§7.2 each supply verbatim replacement code — but the estimate is out of line with its peers.
- **Suggested fix:** Set item 011's `estimatedIterations` to `2`. Do **not** split the item: `01-architecture-layout.md` §5.2 step 6 and §5.4 treat the brittleness batch as one pass over already-settled files, and splitting multiplies the add-before-rewrite ordering constraints in §5.4.
- **References:** `01-architecture-layout.md` §5.2, §5.4; `06-brittleness-batch.md` §2, §4, §6, §7; `forge.config.json` (`loopIterationMultiplier: 1.5`); items 012, 013, 014 for peer estimates
- **Checklist:** CHECK-B11, CHECK-B25

### V-009: Item 016 AC8's divergence tolerance ("a handful") is not objectively measurable

- **Severity:** improvement
- **Location:** `specs/verify-test-debt/backlog.json`, item `016` acceptance criterion 8
- **Issue:** AC8 reads *"The actual collected suite count is compared against the 1799 expected by `07` §5.4, and any divergence beyond a handful of items is explained in the commit message rather than silently accepted."* "A handful" has no numeric value, so two implementers can reach opposite verdicts on the same count — the one thing CHECK-B13 asks acceptance criteria not to do. The vagueness is inherited from `07-testing-strategy.md` §5.4, which says only "landing near 1799" and states no tolerance. Everything else in the AC is concrete, so this is a wording fix.
- **Suggested fix:** *"The actual collected count from `python3 -m pytest tests -q --collect-only` is recorded and compared against the 1799 expected by `07` §5.4; if it differs by more than ±5 items, the commit message names which roster changed and why. No test is adjusted to hit the number."* If ±5 is to bind the spec too, add the same sentence to `07` §5.4 in the same edit — `00-core-definitions.md` §9's REQ-TRIAL-06 derivation warning requires roster-derived figures to be recomputed together. **Requires a user decision** (see Fix Execution Plan).
- **References:** `07-testing-strategy.md` §5.4; `00-core-definitions.md` §9
- **Checklist:** CHECK-B13

### V-010: Items 002 and 003 modify `scripts/forge-session.py` but no acceptance criterion names the configured `typeCheckCommand`

- **Severity:** improvement
- **Location:** `specs/verify-test-debt/backlog.json`, item `002` (AC6–7) and item `003` (AC7–8)
- **Issue:** Both items edit production Python in `scripts/forge-session.py`. Their lint ACs name only `ruff check tests/` (the 19-error budget) plus `bash scripts/validate.sh`. Item 004, which edits `eval/run-compliance-eval.py`, correctly names the configured `typeCheckCommand` explicitly as its AC5 (`ruff check scripts/ eval/` is clean).

  The `validate.sh` fallback is weaker than it looks: its ruff step (`validate.sh:313-326`) hard-fails only when ruff is on PATH, and otherwise prints `SKIP: ruff not installed` while incrementing WARNINGS, not ERRORS — so `validate.sh` can print "All checks passed!" without ruff ever having run against `scripts/`. The backlog already applies exactly this belt-and-braces reasoning for pytest (which `validate.sh` also soft-skips at L210-218) by pairing every item's `validate.sh` AC with an explicit `python3 -m pytest tests -q`; 002 and 003 just miss the same treatment for the production-lint half.
- **Suggested fix:** Insert into items 002 and 003, immediately before their `python3 -m pytest tests -q` criterion: *"`ruff check scripts/ eval/` is clean"* — matching item 004 AC5 verbatim.
- **References:** `forge.config.json` (`typeCheckCommand`); `scripts/validate.sh:210-218, 306-326`; item 004 AC5
- **Checklist:** CHECK-B13, CHECK-B14

### V-011: Item 016 runs the adapter generator but specifies no files it may modify or commit

- **Severity:** improvement
- **Location:** `specs/verify-test-debt/backlog.json`, item `016` (description step 2, AC2)
- **Issue:** Item 016 is the only item with no create-or-modify file list — appropriate for a verification pass, except that its description step 2 says *"`python3 scripts/build-adapters.py`, then `--check` exits 0"*, i.e. it runs the **generator**, not just the freshness check. If that regeneration produces any diff under `adapters/` (the item's own notes anticipate one case: file modes landing as 0664 after a `git checkout`/`merge`/`pull`), the item gives no instruction on whether to commit it, and AC2 only asserts that `--check` subsequently exits 0. Every other item is explicit about its write surface; item 001, which owns the same regeneration, is explicit that all six mirrors ship "in this same commit".
- **Suggested fix:** Append to item 016's description step 2: *"If `build-adapters.py` produces any diff under `adapters/`, commit all six mirrors (`adapters/{claude,codex,copilot,cursor,gemini,pi}`) together, as item 001 does — a partial regeneration red-gates `validate.sh`. Otherwise this item modifies no file."* Optionally add an AC: *"Either `adapters/` is unchanged by this item, or all six mirrors are committed together."*
- **References:** `01-architecture-layout.md` §6.1; item 001 description step 4 and AC5; `scripts/validate.sh:161-181`
- **Checklist:** CHECK-B14

### V-012: REQ-TRIAL-04's Session Log write has no scheduled executor anywhere

- **Severity:** improvement
- **Location:** `specs/verify-test-debt/backlog.json`, item `016` (description final paragraph; AC12; notes)
- **Issue:** REQ-TRIAL-04 (P1) is a MUST: *"At feature close, the remediation plan's Session Log MUST record, per stage and per stage version,"* four figures. Item 016 correctly makes writing them an **explicit non-goal** (*"do NOT write REQ-TRIAL-04 Session Log figures … they are not observable from inside the loop"*), enforced by AC12. That reasoning is sound. But no other item, and no section of the spec suite, names who *does* write them: `07-testing-strategy.md` §7.4 defines the four figures and carries a "Recorded to date" table with `forge-3-specs | v1 | pending`; `tech-spec.md` (~L1025) says only "Both are recorded in the remediation plan's Session Log" without an owner. `plans/remediation-stage-exit-coverage.md` exists, so the target is real.

  Net effect: a P1 MUST is forbidden inside the loop and unassigned outside it. The likely outcome is that it is never written, and `07` §10's checklist item *"The Session Log records all four REQ-TRIAL-04 figures for every stage and stage version"* fails silently at feature close.
- **Suggested fix:** Append one sentence to item 016's `notes`, after the existing REQ-TRIAL sentence: *"REQ-TRIAL-04's four figures per stage-version are written into `plans/remediation-stage-exit-coverage.md` § Session Log **at feature close, by the operator running the final forge-verify**, sourced from the per-severity totals in `specs/verify-test-debt/.verification/VERIFY-*.md` and the `07` §7.4 table — not by this item and not by any loop iteration."* This transmits the hand-off without weakening AC12 and without adding loop work.
- **References:** `PRD.md` §3.6 REQ-TRIAL-04; `07-testing-strategy.md` §7.4, §10; `tech-spec.md`; `TRACEABILITY.md` row REQ-TRIAL-04; `plans/remediation-stage-exit-coverage.md`
- **Checklist:** CHECK-B08

### V-013: REQ-FIX-02's standing obligation is not carried by any backfill item, and items 009/010 AC6 would forbid the response it mandates

- **Severity:** improvement
- **Location:** `specs/verify-test-debt/backlog.json`, items `009` (AC6) and `010` (AC6)
- **Issue:** `05-coverage-backfill.md` §9 states REQ-FIX-02 is *"**a standing obligation on this document's implementation, not a task**,"* and pins the required sequence when a backfill test surfaces a third defect candidate: *"(1) do not write a test asserting the wrong behavior; (2) raise it against PRD §3.3 REQ-FIX-02; (3) fix it in this feature, or record a position … Silently pinning it is the one disallowed option."*

  No backlog item restates that sequence. Meanwhile items 009 and 010 — the two that write REQ-COV-01/-04/-05/-07 tests, i.e. exactly the tests §9 is about — each carry AC6: *"No production source file is modified by this item."* An agent that hits a genuine REQ-FIX-02 trigger while working item 009 faces a checkable AC forbidding the fix and no instruction pointing to the escalate-don't-pin path; the default failure mode is precisely the disallowed one — pin the wrong behavior as golden — which is the churn this whole feature exists to remove. Mitigating: both items list `05-coverage-backfill.md` in `specReferences`, so §9 is reachable, and item 010 AC4 already carries a narrow instance of the rule.
- **Suggested fix:** (a) Append to items 009 and 010 `notes`: *"REQ-FIX-02 is a standing obligation (`05` §9), not a task. If a test written here surfaces a defect beyond REQ-FIX-01/REQ-SEC-01, do **not** write a test asserting the wrong behavior — stop and raise it against PRD §3.3 REQ-FIX-02, then fix it in this feature or record a position the way `05` §9's two rows are recorded. Silently pinning it is the one disallowed option. The two outcomes in that table are recorded positions and are **not** triggers."* (b) Qualify AC6 in both items to *"No production source file is modified by this item, absent a REQ-FIX-02 trigger raised per `05` §9"* so the AC cannot be read as forbidding the mandated response. Leave items 002, 003, 004 unchanged — their production changes are the two named in PRD §3.3, and REQ-FIX-02 is definitionally about defects *beyond* them.
- **References:** `PRD.md` §3.3 REQ-FIX-02; `05-coverage-backfill.md` §9, §11; `04-production-validations.md` §4, §4.4; `TRACEABILITY.md` row REQ-FIX-02
- **Checklist:** CHECK-B08, CHECK-B22

### V-014: Three items depend on rules stated only in `00-core-definitions.md` but omit it from `specReferences`

- **Severity:** improvement
- **Location:** `specs/verify-test-debt/backlog.json`, items `004`, `008`, `010` (`specReferences`)
- **Issue:** Thirteen of sixteen items list `specs/verify-test-debt/00-core-definitions.md`. Items 004 (`04`, `05`, `07`), 008 (`03`, `01`) and 010 (`05`, `07`, `01`) do not, yet each depends on a normative rule whose only statement is in `00`: all three invoke REQ-CANON-03, defined at `00` §10.1; item 010 AC5 ("neither uses `conftest.py`'s `run_cli`, and no shared wrapper is introduced") is the per-file CLI wrapper rule at `00` §10.5; item 008 AC4 ("no new `F401` appears") tracks the unused-import accounting at `00` §11. The substance is restated inline in each item's AC or notes, so no instruction is actually lost — this is a cross-reference completeness defect, not a coverage defect.
- **Suggested fix:** Add `"specs/verify-test-debt/00-core-definitions.md"` to the `specReferences` array of items 004, 008 and 010, preserving each array's existing ordering convention (workstream spec first, then `00`, then others).
- **References:** `00-core-definitions.md` §10.1, §10.5, §11; `01-architecture-layout.md` §5.1
- **Checklist:** CHECK-B07, CHECK-B10

### V-015: Item 004 is typed `test` but modifies production source, contradicting the `test`-type convention items 009 and 010 establish in this same backlog

- **Severity:** improvement
- **Location:** `specs/verify-test-debt/backlog.json`, item `004`, `type`
- **Issue:** Item 004 (`type: "test"`) adds a module-scope `PRELUDE_CRITERIA: Final[tuple[str, ...]]` constant to `eval/run-compliance-eval.py` in addition to adding a test. Its own notes call this out: *"The production constant and its test are paired because the test cannot be written against a constant that does not exist."* The other two `test`-typed items, 009 and 010, both carry the explicit AC *"No production source file is modified by this item"* — so within this artifact `type: "test"` reads as "test-only, no source change". Item 004 breaks that reading; items 002 and 003, which likewise pair a source change with new tests, are typed `bugfix`. `type` is not load-bearing for rauf's scheduling (which orders by `priority` then `id` subject to `dependsOn`), so this does not block execution — it is a legibility defect for anyone triaging by type or reviewing which items may touch shipped code.
- **Suggested fix:** Either (a) retype item 004 to `chore`, or (b) leave `type: "test"` and append to its notes: *"typed `test` because the test is the deliverable; the paired `PRELUDE_CRITERIA` constant is the minimum production change needed to write it, and is the only `eval/` edit in this feature — items 009 and 010 remain the strictly test-only items."* Option (b) is lower-churn and preserves the item's intent. **Requires a user decision.**
- **References:** items 009, 010 (AC "No production source file is modified"), items 002, 003 (`type: "bugfix"` for source-plus-test work); `.rauf/backlog.schema.json` `type` enum
- **Checklist:** CHECK-B04

---

## Observation (no action recommended)

**Four of the thirteen dependency edges are declared non-substantive, serialising 17 of 20 iterations.** Item 008's note states it is *"Independent of items 006 and 007 in substance (`03` §12) — chained only to keep the trim workstream sequential"*; item 009's states it is *"independent of items 002/003/004 … chained only for sequencing"*. The result is a 13-deep chain carrying 17 of the backlog's 20 estimated iterations, leaving 3 iterations of parallelisable slack across 16 items.

This is a deliberate, defensible trade — deterministic file ordering makes a mid-feature failure explainable, and the shared `ruff check tests/` budget of exactly 19 with no headroom rewards serial landing. Recorded so the choice is visible, **not** as a recommendation to reverse it. If throughput ever becomes a concern, item 008 is the safe edge to cut (its file has a single owner). Do **not** unchain 009/010 from the trim run — they share `test_auto_verify.py` / `test_stage_exit.py` / `test_state_verbs.py` with the `06` items and are load-bearing for `01` §5.4.

---

## Dependency graph (enumerated)

All 13 edges, `dependent ← dependency`:

```
003←002  005←001  006←005  007←006  008←007  009←008  010←009
011←010  012←011  013←012  014←013  015←014  016←015
```

- Roots (no deps): `001`, `002`, `004`. Leaves: `003`, `004`, `016`.
- Every edge points from a higher id to a lower one → strictly decreasing → **acyclic by construction**; DFS colouring confirms zero back-edges.
- **Max chain depth: 13** (`001 → 005 → 006 → 007 → 008 → 009 → 010 → 011 → 012 → 013 → 014 → 015 → 016`). Second chain `002 → 003` (depth 2). Isolated: `004`.
- Critical path carries **17 of 20** total `estimatedIterations`.
- After V-003 + V-004 are applied: max chain depth remains **13**, no cycles, `closure(016)` = all 15 other items.

## Corroborated figures (re-derived against the live tree)

Every quantitative literal the backlog asserts was independently re-derived and is **correct**: suite baseline 1842 collected; `ruff check tests/` exactly 19 errors; per-file collection 43 / 102 / 10 / 147; `CANONICAL_EXIT_SITES` = 9 sites carrying 10 contract paths with `forge-5-loop` the sole two-path site; `skills/forge-0-epic/SKILL.md` body 295/300 lines and 2749/5000 words (item 001's "+5 line budget" is exact); `_ACCEPTED_HASHES` = 3 / `_REJECTED_HASHES` = 10 → 2×3 + 3×10 = 36; epic-malformation loop = 5 shapes; `_VERB_INVOCATIONS` = 8; exactly 6 test defs under `# autoVerify effectiveness × gate selection` and 17 `verifyGate` references in `tests/test_stage_exit.py`; `--version` is `type=int` and item 002 AC2's expected string `--version must be a positive integer; got 0` is byte-correct; `_validated_findings_file`'s signature is `(value: str, target_dir: Path) -> str` as item 003 states. Every named test function exists at the claimed path. `07` §5.4's arithmetic (1842 −39 −60 −1 +15 +42 = 1799) reconciles term-by-term. All ~110 explicit `NN-file.md §X.Y` references resolve to a real heading, and all `specReferences` paths resolve on disk as project-root-relative.

---

## Fix Execution Plan

### User Decisions Required

1. **V-009** proposes **±5** as the concrete divergence tolerance for the 1799 suite-count target. `07-testing-strategy.md` §5.4 deliberately states no tolerance. Confirm ±5, supply a different number, or choose the alternative: drop the tolerance clause and require the actual count to be recorded in the commit message unconditionally. If the tolerance is to bind the spec too, `07` §5.4 must be edited in the same pass (`00` §9 REQ-TRIAL-06 derivation warning).
2. **V-015** — retype item 004 (`test` → `chore`) or annotate its notes. Recommend the annotation: advisory-severity, and retyping churns an item whose deliverable genuinely is a test.

Everything else is mechanical and can be applied directly.

### Step 1 — Correct the adapter-regeneration rule (blocking)

- **Files:** `specs/verify-test-debt/backlog.json`
- **Addresses:** V-001, V-002
- **Action:** (a) In item `001`'s `notes`, replace "so it is the only one that must regenerate adapters" with the corrected clause from V-001; leave the rest of the string byte-identical. (b) For items `002` and `003` each: append the adapter-regeneration step to `description`, and insert the `build-adapters.py --check` criterion into `acceptanceCriteria` immediately **before** the existing `bash scripts/validate.sh` entry (both strings in V-002). Do not add this to any other item.
- **Depends on:** none
- **Note:** `AGENTS.md:21` carries the same narrow framing and should be corrected alongside, but it is outside the backlog artifact — out of scope for a backlog fix pass.

### Step 2 — Close the dependency graph (blocking)

- **Files:** `specs/verify-test-debt/backlog.json`
- **Addresses:** V-003, V-004
- **Action:** Set item `011`'s `dependsOn` to `["003", "010"]` and item `016`'s to `["003", "004", "015"]`. Add one clause to item `011`'s notes recording that `003` is carried for `01` §5.4 add-before-rewrite on `tests/test_state_verbs.py` and for the `import pytest` item 014 needs; and one to item `016`'s notes recording that `003`/`004` are carried because the 1799 reconciliation counts their 10 backfill ids. Touch no other `dependsOn` array. Re-derive the graph afterward and confirm: max depth 13, no cycles, `closure(016)` = all 15 other ids.
- **Depends on:** none

### Step 3 — Correct the closeout item's priority

- **Files:** `specs/verify-test-debt/backlog.json`
- **Addresses:** V-005
- **Action:** Change item `016`'s `priority` from `1` to `3`. No other priority changes.
- **Depends on:** none (apply in the same edit pass as Step 2)

### Step 4 — Qualify the mis-anchored section pointers

- **Files:** `specs/verify-test-debt/backlog.json`
- **Addresses:** V-006
- **Action:** In item `007`'s description, prefix each bare `§` with `` `03` `` (12 substitutions enumerated in V-006). Do not touch item 007's notes. In item `014`'s description, change ``**Corrupt-file family** (§8.3;`` to ``**Corrupt-file family** (`06` §8.3;``. Change no section numbers.
- **Depends on:** none

### Step 5 — Correct the wrapper rosters in items 002 and 003

- **Files:** `specs/verify-test-debt/backlog.json`
- **Addresses:** V-007
- **Action:** Apply the two replacement sentences from V-007 to item `002` step 4 and item `003` step 4. Leave both items' `conftest.py` `run_cli` warnings unchanged. Do not modify items 009 or 010 — their rosters were verified correct.
- **Depends on:** none

### Step 6 — Add the production-lint gate to items 002 and 003

- **Files:** `specs/verify-test-debt/backlog.json`
- **Addresses:** V-010
- **Action:** Insert `` "`ruff check scripts/ eval/` is clean" `` into items `002` and `003` `acceptanceCriteria`, immediately before the existing `python3 -m pytest tests -q` entry. Must match item `004` AC5 exactly.
- **Depends on:** none

### Step 7 — Raise item 011's iteration estimate

- **Files:** `specs/verify-test-debt/backlog.json`
- **Addresses:** V-008
- **Action:** Change item `011`'s `estimatedIterations` from `1` to `2`. Do not split the item.
- **Depends on:** none

### Step 8 — Pin item 016's adapter write surface

- **Files:** `specs/verify-test-debt/backlog.json`
- **Addresses:** V-011
- **Action:** Append the adapter-commit sentence from V-011 to the end of item `016`'s description step 2.
- **Depends on:** Step 1 (so items 001, 002, 003 and 016 tell one consistent adapter story)

### Step 9 — Record the REQ-TRIAL-04 hand-off

- **Files:** `specs/verify-test-debt/backlog.json`
- **Addresses:** V-012
- **Action:** Append the hand-off sentence from V-012 to item `016`'s `notes`. Do **not** modify AC12 or the "Explicit non-goal" paragraph — both are correct as written.
- **Depends on:** none

### Step 10 — Transmit the REQ-FIX-02 standing obligation

- **Files:** `specs/verify-test-debt/backlog.json`
- **Addresses:** V-013
- **Action:** For items `009` and `010`: qualify AC6 and append the standing-obligation note, both per V-013. Leave items 002, 003, 004 unchanged.
- **Depends on:** none

### Step 11 — Add the missing `00-core-definitions.md` references

- **Files:** `specs/verify-test-debt/backlog.json`
- **Addresses:** V-014
- **Action:** Add `specs/verify-test-debt/00-core-definitions.md` to the `specReferences` of items `004`, `008`, `010`, preserving each array's existing ordering convention.
- **Depends on:** none

### Step 12 — Apply the two user decisions

- **Files:** `specs/verify-test-debt/backlog.json`, and (only if the tolerance extends to the spec) `specs/verify-test-debt/07-testing-strategy.md` §5.4
- **Addresses:** V-009, V-015
- **Action:** After the decisions above, rewrite item `016` AC8 with the agreed tolerance, and apply the chosen option for item `004`'s type/notes.
- **Depends on:** User decisions recorded

### Post-fix validation

- **Action:** Re-run `rauf-stable backlog validate . --backlog specs/verify-test-debt --specs-dir ./specs --json` from the project root and confirm `{"valid": true, "findings": []}`, exit 0. Then confirm structural invariants are unchanged where intended: `python3 -c "import json; b=json.load(open('specs/verify-test-debt/backlog.json')); print(len(b['items']), [i['id'] for i in b['items']])"` → 16 items, ids `001`–`016`. Re-derive the dependency graph and confirm max depth 13, no cycles, `closure(016)` covers all 15 other items.
- **Note:** the validator reported clean *before* these fixes too — it does not detect missing (as opposed to invalid) edges, so it is a regression check only, never evidence the findings were addressed.
- **Depends on:** Steps 1–12
