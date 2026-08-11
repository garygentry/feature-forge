# 05 — Testing Strategy

> How `verify-fix-sweep` is tested: one new test file (`tests/test_fix_sweep.py`)
> covering the script's behavior plus prose guards over the skill/checklist edits, and
> six existing pinned tests updated in lockstep with the checklist-count changes. All
> tests are pytest + stdlib — `jsonschema` is absent in CI, so a bare
> `python3 -m pytest tests` must run everything here.
>
> Shared vocabulary: `00-core-definitions.md`. The functions under test are specified
> in `02-fix-sweep-script.md`; the prose literals pinned here are guaranteed by
> `03-forge-fix-integration.md` §11 and `04-verification-checks.md` §5.3.

## Requirement Coverage

| REQ ID | Requirement | Section |
|---|---|---|
| REQ-SWEEP-01 | Delta extraction tested end-to-end | §2.2, §2.4 |
| REQ-SWEEP-02 | Normalization, floor, reflow suppression units | §2.3, §2.4 |
| REQ-SWEEP-03 | Corpus boundary tests (audit, gated tree, untracked) | §2.2, §2.6 |
| REQ-SWEEP-04 | Disposition vocabulary prose-guarded | §2.11 |
| REQ-SWEEP-05 | Sweep-record / staging prose-guarded | §2.11 |
| REQ-SWEEP-06 | Outcome-table stability prose-guarded | §2.11 |
| REQ-SWEEP-07 | Skip paths produce the skip payload, exit 0 | §2.5, §2.11 (NOT-RUN wording) |
| REQ-CARD-01 | plan-coverage names omissions + total mismatch | §2.7 |
| REQ-CARD-02/03 | CHECK-B29/I24 prose guards + count pins | §2.11, §3 |
| REQ-CARD-04 | not-applicable degradation asserted | §2.7, §2.11 |
| REQ-CONS-01 | CHECK-I25/S39 prose guards + count pins | §2.11, §3 |
| REQ-PERF-01 | Cost-model **shape** pinned; no wall-clock assertion | §2.10, §5 |
| REQ-OBS-01 | Hit payload names file/line/needle/source | §2.2, §2.8 |
| REQ-CONC-01 | Read-only: corpus mtimes unchanged after sweep | §2.9 |
| REQ-SEC-01 | Matched text echoed verbatim, no elision | §2.8 |

## 1. Framework, Conventions, and Fixtures

- **Framework:** pytest, stdlib-only imports (plus `pytest` itself). No new dev
  dependencies (C-3).
- **Scratch-repo pattern** — follow `tests/test_forge_bootstrap.py` exactly: a local
  `_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]` wrapper
  (`subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True)`)
  and `_set_git_identity(repo: Path)` (sets `user.email`/`user.name` locally so
  commits work on CI runners with no global identity), driving repos created under
  `tmp_path`.
- **Loading the hyphenated module:** `fix-sweep.py` is not importable by name. Use
  the `test_forge_bootstrap.py` idiom — a module-scoped fixture that loads it via
  `importlib.util.spec_from_file_location("fix_sweep", REPO_ROOT / "scripts" /
  "fix-sweep.py")`. Unit tests (normalize, parsers, filters) call functions on the
  loaded module; CLI/exit-code tests run it as a subprocess
  (`[sys.executable, str(SCRIPT), …]`, `cwd=scratch_repo`).
- **Table-driven tests** use `@pytest.mark.parametrize` (the established idiom).
- **Test narration states intent, never measurement** (forge-fix Step 4's anti-churn
  rule, inherited repo-wide): docstrings cite the spec section they enforce
  (`"(02 §4.3)"`), not empirical claims.

```python
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "fix-sweep.py"
FORGE_FIX_SKILL = REPO_ROOT / "skills" / "forge-fix" / "SKILL.md"
VERIFY_SKILL = REPO_ROOT / "skills" / "forge-verify" / "SKILL.md"
CHECKLISTS = REPO_ROOT / "skills" / "forge-verify" / "references" / "verification-checklists"
```

### 1.1 The core scratch fixture

```python
@pytest.fixture()
def scratch_repo(tmp_path: Path) -> Path:
    """A git repo with an initial commit — the minimal sweepable baseline.

    Layout after setup: one committed artifact file. Tests then edit the working
    tree (creating the fix delta vs HEAD, per 00 §3) and run the sweep
    pre-commit, exactly as forge-fix Step 4 does.
    """
```

## 2. `tests/test_fix_sweep.py` — Behavior and Guards

Organized in the order below; each subsection is a commented section of the file.

### 2.1 Module foundation

Module loads via importlib; the 00-anchored constants exist with canonical values
(`MIN_NEEDLE_CHARS == 24`, `VERIFICATION_SEGMENT == ".verification"`,
`DRIFT_GATED_PREFIX == "adapters/"`, `DRIFT_GATE_SENTINEL ==
"scripts/build-adapters.py"`); `UsageError` is defined and maps to exit 2.

### 2.2 F-5 regression fixture (PRD Success Criteria — the headline test)

One scratch repo reproducing the motivating incident end-to-end:

- Committed baseline: `specs/x/PRD.md` containing the claim sentence
  (“universal among the tracked hyperscalers…”, ≥ 24 normalized chars); a **verbatim
  sibling copy** in `specs/other/PRD.md`; a **whitespace-reflowed variant** (same
  words, different line breaks, different wrapping) in `docs/summary.md`; a copy in an
  **un-gated generated file** `src/generated/foo.ts`; a copy in
  `specs/x/.verification/VERIFY-impl-2026-01-01.md` (audit record); a copy in
  `adapters/claude/skills/x.md` **plus** the drift-gate sentinel file
  `scripts/build-adapters.py` (any content).
- The "fix": remove/replace the claim in `specs/x/PRD.md` only (working tree edit, no
  commit).
- Run `sweep --json`. Assert:
  - exit **1**;
  - hits for the sibling (`specs/other/PRD.md`), the reflowed variant
    (`docs/summary.md` — proves blob matching spans line breaks), and the generated
    file (`src/generated/foo.ts`), each with correct `file`, 1-based `line`,
    `needle` (original removed text verbatim), `sourceFile`, `sourceLine`;
  - **no** hit for the `.verification/` copy (unconditional exclude) and **no** hit
    for the `adapters/` copy (gate detected);
  - `hits` sorted by `(file, line)`; `baseline == "HEAD"`; `skipped is False`.
- **Self-file variant:** a second copy of the claim two sections below in
  `specs/x/PRD.md` itself (left unedited) is reported — the F-5 self-contradiction
  hit.

### 2.3 Normalization and threshold units (REQ-SWEEP-02)

Parametrized over `normalize()` (00 §2 reference semantics): case, punctuation, and
whitespace variants of one sentence normalize identically; distinct sentences do not
collide; non-alphanumerics map to single spaces with runs collapsed; result stripped.
Floor: a removed line normalizing to 23 chars yields no needle (`belowFloor` counted);
24 chars yields one. `--min-chars` overrides the floor (test-only knob).

### 2.4 Needle extraction and reflow/move suppression (REQ-SWEEP-01/02)

- Hunk-header arithmetic: removed lines report correct pre-fix a-side line numbers
  (multi-hunk file, `--unified=0`).
- `---` file headers are never needles; added-only diffs yield zero needles.
- **Reflow suppression:** a removed line whose normalized text reappears within the
  delta's normalized added lines (same file, and cross-file within the delta) yields
  no needle, counted in `reflowSuppressed` — a pure re-wrap sweep finds nothing.
- Duplicate removed lines produce distinct needles with their own provenance.

### 2.5 Skip paths (REQ-SWEEP-07)

- A non-repo directory → skip payload `{"skipped": true, "reason": "not-a-git-repo"}`,
  exit **0**.
- A fresh `git init` with no commit (unborn HEAD) → `reason: "no-head"`, exit **0**.
- Both payloads carry empty `needles`/`hits`, `baseline: null` (00 §6.1 skip shape).

### 2.6 Corpus boundaries (REQ-SWEEP-03)

- An **untracked, non-ignored** file carrying the claim is reported (`ls-files
  --others` inclusion); a `.gitignore`d file is not.
- A repo whose `adapters/` has **no** `scripts/build-adapters.py` → `adapters/` **is**
  swept (conditional default); with the sentinel present → excluded, and `excludes`
  in the payload records what was applied.
- `--exclude docs/` drops `docs/` hits; prefix match is repo-relative.
- A non-UTF-8 binary file is skipped silently, not counted in `filesScanned`, never
  fatal.

### 2.7 `plan-coverage` (REQ-CARD-01, REQ-CARD-04)

Fixture documents written inline (findings-template shapes, 00 §7.1):

- A 16-findings / 15-step document → exit **1**, `uncovered == ["V-016"]` — the
  missing id **named**, never a count delta (the 15-of-16 incident).
- `## Summary` claiming `Total findings: 16` over 15 headings → exit **1**,
  `claimedTotal == 16`, `actualTotal == 15`, `totalMismatch is True`, human line
  `claimed 16, actual 15`.
- Full coverage + consistent totals → exit **0**.
- No `## Findings` or no `## Fix Execution Plan` → `applicable: false`, exit **0**
  (REQ-CARD-04 analog).
- No Summary total line → `claimedTotal is None`, `totalMismatch is False`.
- A `### V-NNN:` heading inside a **fenced code block** is not counted (the template
  ships fenced examples — 02's parser skips fences).
- Unreadable path → exit **2**, `Error:` on stderr, empty stdout.

### 2.8 CLI, payloads, and output formats

- `--json` emits exactly one JSON object on stdout matching the 00 §6 TypedDict keys
  (camelCase); human mode emits the fixed hit-line format
  `{file}:{line}: survivor of "{needle}" (removed at {sourceFile}:{sourceLine})`
  (02 pins this — `03-forge-fix-integration.md` reads it).
- Matched text is echoed **verbatim** — a needle containing quotes/markup arrives
  unelided in `needle` and `excerpt` (REQ-SEC-01/REQ-OBS-01).
- Unknown flags / missing findings doc → exit **2** with `Error:` stderr line.

### 2.9 Determinism and read-only behavior

- Two consecutive runs over the same tree produce byte-identical `--json` output
  (ordering is total, 02 §4.6).
- **Read-only (REQ-CONC-01):** corpus file mtimes/contents are unchanged after a
  sweep; the script wrote nothing (the only writer in this feature is the forge-fix
  agent).

### 2.10 Cost-model shape (REQ-PERF-01 — no wall-clock)

Monkeypatch the module's `run_git` to a counting wrapper: one full `sweep` performs a
**bounded number of git invocations** (the 02 §7 roster: `rev-parse` probes + `diff` +
`ls-files`; assert count ≤ 5) — **no git call per corpus file**. Each corpus file is
opened at most once (count via monkeypatched `Path.read_text`/open seam per 02's
structure). Wall-clock is never asserted (tech-spec §3.8: flaky on shared runners;
observed instead at milestone acceptance, tech-spec §10).

### 2.11 Prose guards (pattern: `tests/test_lifecycle_artifact_check.py`)

**Meta-guard contract (spec-archetypes norm).** The protection set is the
**enumerated literals below** — nothing else. Non-goals, recorded here as decisions:
exact-markdown fidelity of surrounding prose, wording beyond the literals, and
guarding against every conceivable rewording. The verifier judges completeness
against this declared set only.

Guards over `skills/forge-fix/SKILL.md` (literals guaranteed by
`03-forge-fix-integration.md` §11):

- contains `scripts/fix-sweep.py`, `sweep`, and `--json` inside a bash fence, and
  `plan-coverage` invoked as `$R/scripts/fix-sweep.py`;
- contains the literal `- Sweep: NOT RUN — no git delta ({reason})` (em dash and
  `{reason}` placeholder exact — REQ-SWEEP-07's visibility guarantee);
- contains all three disposition tokens `FIXED`, `JUSTIFIED:`, `FALSE-POSITIVE:`
  (REQ-SWEEP-04);
- contains the enumerated-staging prose: `git add <path>` present, with `git add -A`
  and `git add .` appearing only in a prohibitive clause (REQ-SWEEP-05);
- contains **no** `--exclude` and **no** `--min-chars` (operator escape hatches stay
  out of skill prose);
- Step 7's outcome table still holds exactly the seven existing `--outcome` values
  (C-6) and headings `## Step 1:` … `## Step 7:` survive (C-1, no renumbering).

Guards over the checklist files and `skills/forge-verify/SKILL.md` (literals
guaranteed by `04-verification-checks.md` §5.3):

- each of `**CHECK-B29**` (backlog.md, under `### Work-Order Cardinality`),
  `**CHECK-I24**` + `**CHECK-I25**` (impl.md), `**CHECK-S39**` (specs.md, under
  `### Internal Consistency`) is present with its degradation clause
  (`not-applicable`; `never a hard fail` for B29/I24) and severity literal
  (`` `gap` `` for B29/I24; `` `inconsistency` ``/`` `error` `` + `decision-bearing`
  for I25/S39), plus `Report, do not repair` and the `(#170)` citation;
- each new CHECK id appears in its owning dimension-group bullet in
  `VERIFY_SKILL` (`(owns CHECK-B29)`, `(owns CHECK-I24/I25)`, `(owns CHECK-S39)`) —
  reachability, 04 §4.3;
- `build-adapters.py`'s `RUNTIME_HELPERS` contains `"fix-sweep.py"` (distribution,
  01 §5.1).

**No I25↔S39 cross-reference:** `test_no_cross_mode_leakage` (regex
`CHECK-{letter}\d\d` over each whole mode file) forbids the near-duplicate entries
from citing each other; the relationship lives in `04-verification-checks.md` only.
Do not "helpfully" add the cross-reference.

## 3. Existing Pinned Tests — Lockstep Edits (six files)

All in the same change as the canon edits; each is a literal substitution, no
structural rewrite. The dynamic cross-check
(`test_skill_expected_count_table_matches_the_files`) then re-verifies SKILL totals
against the files, so a missed edit fails CI twice.

| File | Edit |
|---|---|
| `tests/test_verification_checklists_split.py` | `EXPECTED` rows: `"specs": ("S", 38)` → `39`, `"backlog": ("B", 28)` → `29`, `"impl": ("I", 23)` → `25`; inventory total `131` → `135` (both the assertion and its comment, in `test_split_preserves_the_full_check_inventory`) |
| `tests/test_dev_runtime_smoke.py` | `"impl: 23 checks"` → `"impl: 25 checks"`, `"impl 23"` → `"impl 25"`; **refresh the stale comment** claiming `### Runnability` is impl.md's last section (it no longer is — end-of-file placement per 04 §5.2; the membership assertions themselves stay green) |
| `tests/test_smoke_command.py` | same two literal bumps + same comment refresh |
| `tests/test_lifecycle_artifact_check.py` | `"backlog: 28 checks"` → `"backlog: 29 checks"`, `"backlog 28"` → `"backlog 29"` |
| `tests/test_build_adapters.py` | `len(mod.RUNTIME_HELPERS) == 6` → `7` (both the `len` and the `len(set(...))` de-dup assertion) |
| `tests/test_adapter_host_neutrality.py` | **no edit expected** — new checklist prose is written host-neutral from the start (C-5); listed here so its failure is recognized as a prose defect in 04's text, not a test to update |

## 4. Coverage Targets

- `scripts/fix-sweep.py`: every public function of 02's structure exercised;
  every exit-code row of 00 §6.3 hit at least once per subcommand; both filters'
  counters observed non-zero in at least one test.
- Prose guards: every literal in §2.11's enumerated set asserted.
- No coverage-percentage gate is added — the repo pins behavior, not percentages.

## 5. Deliberately Untested (recorded non-goals)

- **Wall-clock** (REQ-PERF-01): shape only (§2.10); timing observed at milestone
  acceptance on the first real fix pass (tech-spec §10), where the JSON payload is
  archived as milestone-2 boundary evidence.
- **Agent behavior** (disposition judgment, AskUserQuestion flows): forge-fix Step 4
  conduct is prose-guarded (§2.11), not simulated.
- **The verifier CHECKs' judgment quality** (C-2): they are checklist prose; only
  their presence, degradation clauses, reachability tags, and counts are guarded.

## 6. Full Gate (definition of done)

```
python3 -m pytest tests                 # includes test_fix_sweep.py + 5 updated pins
bash scripts/validate.sh                # incl. adapter drift (step 6b) after regen
ruff check scripts/ eval/               # CI-only gate — run locally
python3 scripts/check-spec-purity.py    # forge-fix ≤300 body lines; forge-verify at 298
```

## 7. Dependencies

- `00-core-definitions.md` (contracts), `02-fix-sweep-script.md` (functions under
  test), `03-forge-fix-integration.md` §11 and `04-verification-checks.md` §5.3
  (guaranteed prose literals). Implement the script before its behavior tests; prose
  guards land with their canon edits.

## 8. Verification

- [ ] `python3 -m pytest tests/test_fix_sweep.py` green on a machine with git and no
      global git identity (fixture sets its own).
- [ ] The F-5 fixture asserts all five PRD Success-Criteria outcomes (two survivors +
      generated-file hit reported; audit copy and gated tree silent).
- [ ] Removing any single canon edit (a CHECK entry, an ownership tag, the NOT-RUN
      line) fails at least one guard in §2.11.
- [ ] All six §3 edits applied; `python3 -m pytest tests` green end-to-end.
