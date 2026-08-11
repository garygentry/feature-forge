# verify-fix-sweep — Technical Specification

## 1. Overview

Milestone 1 (mechanical) of hardening Track F (#170). Three deliverables, all
deterministic and model-free (C-2):

1. **`scripts/fix-sweep.py`** — a new standalone, Python-stdlib-only script with two
   subcommands: `sweep` (corrected-claim survivor detection over the fix delta) and
   `plan-coverage` (Fix Execution Plan cardinality assertion against the findings set).
2. **forge-fix integration** — the plan-coverage assertion runs in Step 2; the sweep
   runs as the closing sub-steps of Step 4, before Step 5's Commit 1, with every hit
   dispositioned in-pass and recorded in the findings document. **No step
   renumbering** — existing Steps 1–7 keep their numbers, so internal cross-references
   and `references/stage-exit-protocol.md:458` ("forge-fix SKILL.md Step 6") stay valid.
3. **Four new verification CHECKs** — `CHECK-B29` (backlog cardinality), `CHECK-I24`
   (impl cardinality), `CHECK-I25` + `CHECK-S39` (internal consistency), as prose in
   the uncapped checklist reference files, with numeric-only total bumps in
   `skills/forge-verify/SKILL.md` and four pinned tests updated in lockstep.

Key architectural decisions (each detailed in §3): standalone script over a
`forge-session.py` verb; working-tree-vs-HEAD fix delta swept pre-commit; per-line
normalized-substring matching with a 24-normalized-character floor; sweep everything
git-tracked except `.verification/` and drift-gated regenerated trees.

## 2. Module Structure

New and modified files:

```
scripts/fix-sweep.py                                        NEW  stdlib-only CLI, 2 subcommands
tests/test_fix_sweep.py                                     NEW  behavior + prose guards
skills/forge-fix/SKILL.md                                   EDIT Step 2 + Step 4 additions
skills/forge-verify/SKILL.md                                EDIT numeric totals only (lines 33, 171)
skills/forge-verify/references/verification-checklists/backlog.md  EDIT +CHECK-B29
skills/forge-verify/references/verification-checklists/impl.md     EDIT +CHECK-I24, +CHECK-I25
skills/forge-verify/references/verification-checklists/specs.md    EDIT +CHECK-S39
tests/test_dev_runtime_smoke.py                             EDIT pinned total "impl: 23" → 25
tests/test_smoke_command.py                                 EDIT pinned total "impl: 23" → 25
tests/test_lifecycle_artifact_check.py                      EDIT pinned total "backlog: 28" → 29
tests/test_verification_checklists_split.py                 EDIT mode→count table, 131 → 135
adapters/**                                                 REGEN via build-adapters.py (C-5)
```

`fix-sweep.py`'s public surface is its CLI contract (§5) — it exports no Python API.
No `forge.config.json` keys, no pipeline-state schema changes, no new forge-fix
outcome values (C-6).

## 3. Technical Decisions

### 3.1 Standalone script, not a forge-session.py verb (REQ-SWEEP-01, C-3)

**Decision:** ship `scripts/fix-sweep.py` as a standalone stdlib-only script.
**Rationale (evidence-backed):** the sweep wants the standalone-script exit
convention — `0` clean / `1` findings / `2` usage error — already established by
`check-spec-purity.py` and `validate-traceability.py`. `forge-session.py` (7131
lines) uses a strict `0/2`-only convention with no precedent for "findings found",
and the sweep needs none of its state/config machinery.
**Alternative considered:** a `forge-session.py fix-sweep` verb — rejected for the
exit-convention mismatch and mega-file growth.

### 3.2 Fix delta = working tree vs HEAD, swept pre-commit (REQ-SWEEP-01, REQ-SWEEP-05)

**Decision:** the sweep runs after the last fix step is applied and **before** Step
5's Commit 1, while the tree is dirty. The delta is `git diff HEAD` (staged +
unstaged vs HEAD), so the pre-fix baseline is simply `HEAD` — no recorded baseline
hash is needed (none exists in pipeline state).
**Rationale:** REQ-SWEEP-05 requires the sweep record in the findings document; run
pre-commit, the record and all dispositions ride Commit 1 atomically, with no third
commit and no friction with the two-commit provenance protocol. A survivor fixed
during disposition re-enters the same delta naturally.
**Alternative considered:** post-Commit-1 `HEAD~1..HEAD` — cleaner delta definition
but forces an extra commit for the sweep record, rejected.

### 3.3 Matching: per-line needles, normalized-substring, 24-char floor (REQ-SWEEP-02)

**Decision:**
- **Needle extraction:** parse `git diff HEAD --unified=0 --no-color` for removed
  lines (`-` prefix, excluding `---` file headers).
- **Normalization** (applied identically to needles and corpus): `str.lower()`, every
  non-alphanumeric character mapped to a space, whitespace runs collapsed to a single
  space, then stripped. Plain `str.lower()`; no Unicode NFKC folding (determinism over
  cleverness — milestone 2 can revisit).
- **Threshold:** needles shorter than **24 normalized characters** are dropped
  (the motivating F-5 claim normalizes to ~40 chars; list bullets, braces, and "see
  below" fall under the floor).
- **Reflow/move suppression:** a needle is dropped when its normalized text appears
  as a substring of the delta's normalized **added** lines (concatenated per file,
  delta-wide). Text that was merely moved or re-wrapped was not corrected; sweeping
  it would flag every reflow as a survivor.
- **Corpus matching:** each corpus file's content is normalized into one blob with an
  offset→original-line map; each needle is searched as a plain substring (`in` /
  `str.find`). A file reflowed across different line breaks therefore still matches
  (the F-5 whitespace-reflow success criterion).
- **Self-file hits count:** the file a line was removed from is still swept — a
  surviving duplicate two sections below (the F-5 self-contradiction) is a hit.

**Alternatives considered:** word-count floor (≥5 words — generic short phrases clear
it too easily); dual char+word floors (second knob without demonstrated need);
paragraph-joined needles (more complex; per-line halves of a wrapped sentence match
independently anyway, erring toward recall).

### 3.4 Corpus: everything tracked, minus audit + drift-gated trees (REQ-SWEEP-03)

**Decision:** corpus = `git ls-files` output, minus:
- any path containing a `.verification/` segment (findings documents are audit
  records that quote corrected claims by design);
- the default drift-gated exclusion `adapters/` (regeneration, not the sweep, is that
  mirror's guarantee — the #167 translation pass means a translated wrong claim can
  differ from the canon needle by more than normalization bridges, so sweeping it
  gives false confidence while `validate.sh` step 6b already fails until regenerated);
- any additional prefixes passed via repeatable `--exclude <path-prefix>` flags
  (operator escape hatch; no config keys per C-6).

Files that fail UTF-8 decoding are skipped silently (binaries). **No pre-exclusion of
historical corpora** (prior features' `specs/`, `CHANGELOG.md`, `STATUS.md`): the F-5
sibling survivor lived in a spec artifact, so recall wins; hits there disposition
cheaply as "historical record" per REQ-SWEEP-04.

### 3.5 plan-coverage as a second subcommand (REQ-CARD-01, C-2)

**Decision:** `fix-sweep.py plan-coverage <findings-doc>` deterministically asserts
Fix Execution Plan coverage: every `V-NNN` id found as a `### V-NNN:` heading under
`## Findings` must appear in at least one `#### Step {N}` entry's `**Addresses:**`
field under `### Execution Steps`. Omissions are reported **by name** (the V-NNN ids),
never as a count delta. Sharing the script keeps the findings-doc parsing in one
place; forge-fix invokes it at Step 2 so an incomplete plan is caught before any fix
executes.
**Alternatives considered:** separate script (duplicate parsing); agent-judgment
prose (violates C-2 — the 15-of-16 incident was an agent miscount).

### 3.6 forge-fix integration without renumbering (REQ-SWEEP-01, REQ-SWEEP-04..07, REQ-CARD-01)

**Decision:** no new step heading; Steps 1–7 keep their numbers.
- **Step 2 addition:** after parsing the plan, run `plan-coverage`. Exit 1 → surface
  the named uncovered findings and resolve through the host's question mechanism:
  either author a covering execution step into the plan (and execute it this pass) or
  record an explicit justification against the finding. Unresolved → the pass closes
  `decisions` (existing row). Exit 0 with `"applicable": false` → proceed silently.
- **Step 4 addition (closing sub-steps):** after the last plan step is applied, run
  `sweep`. Every hit is dispositioned before Step 5: **fixed** (edit made now — it
  joins the same delta and Commit 1), **justified** (deliberate quote / historical
  record, reason recorded), or **false positive** (reason recorded). The sweep record
  (§4.3) is appended under `## Fix Progress`. When the script reports
  `"skipped": true`, the visible notice `- Sweep: NOT RUN — no git delta ({reason})`
  is appended instead — never silent (REQ-SWEEP-07). If any disposition edited files,
  re-run the sweep once to confirm the edits introduced no fresh survivors
  (previously dispositioned hits need no re-disposition — match them by
  file + needle).
- **Outcome routing (REQ-SWEEP-06):** existing rows only. Survivor awaiting a user
  decision → `decisions`; unfixable/unjustifiable survivor or a sweep tool failure
  (exit 2) → `failed`; fully dispositioned → the pass continues on its normal path.
  The pass still closes exactly once through Step 7.

`skills/forge-fix/SKILL.md` is at 135/300 body lines; these additions (~25–35 lines
including one fenced invocation block with the standard plugin-root prelude) stay
comfortably under the cap (C-4).

### 3.7 Verification CHECKs (REQ-CARD-02..04, REQ-CONS-01)

**Decision:** four new checklist entries, next-in-sequence ids (the contiguity test
`test_verification_checklists_split.py` requires exactly this), written in the
established heuristic-with-degradation style and **host-neutral wording** (these
files carry zero host terms and are not translation-exempt — C-5):

- **CHECK-B29** (backlog.md, new `### Work-Order Cardinality` section at end of
  file): when the backlog or an artifact it derives from declares an enumerated
  per-item work list claiming coverage of a set, re-derive the cardinality from the
  actual item set and **name** any missing item. Not-applicable when no such list is
  declared (REQ-CARD-04) — never a hard fail. Severity of a true omission: `gap`
  (blocking — an unreviewed item is missing coverage).
- **CHECK-I24** (impl.md, new `### Work-Order Cardinality` section): same assertion
  over implementation artifacts — any declared work order / coverage list checked
  against the actual artifact set it claims to cover, omissions named (the 15-of-16
  case). Same degradation and severity.
- **CHECK-I25** (impl.md) and **CHECK-S39** (specs.md, both under a new
  `### Internal Consistency` section): flag an artifact stating the same quantity or
  claim in more than one place inconsistently (front matter vs body, summary vs
  prose — the F-5 artifact asserted "universal" while its own body stated 4-of-7).
  Verifier judgment, checklist prose only — no mechanical extractor (out of scope,
  milestone 2). Severity follows the existing floor: defaults to `inconsistency`
  (advisory); escalates to `error` only when the contradiction is decision-bearing
  per the severity conventions already in forge-verify SKILL.md.

**Totals:** `skills/forge-verify/SKILL.md` lines 33 and 171 get numeric-only edits —
`backlog 28→29`, `impl 23→25`, `specs 38→39` (body is at 299/300 lines; no new lines
may be added there — all explanatory prose lives in the checklist files).

## 4. Data Model

### 4.1 `sweep` JSON payload (stdout with `--json`)

```json
{
  "skipped": false,
  "reason": null,
  "baseline": "HEAD",
  "needles": [{"file": "specs/x/PRD.md", "line": 12, "normalized": "…", "original": "…"}],
  "droppedNeedles": {"belowFloor": 3, "reflowSuppressed": 1},
  "excludes": [".verification/", "adapters/"],
  "filesScanned": 1234,
  "hits": [
    {
      "file": "src/generated/foo.ts",
      "line": 88,
      "needle": "universal among the tracked hyperscalers",
      "excerpt": "<original text of the matched region>",
      "sourceFile": "specs/x/PRD.md",
      "sourceLine": 12
    }
  ]
}
```

Skip shape (REQ-SWEEP-07): `{"skipped": true, "reason": "not-a-git-repo" | "no-head",
"hits": []}` with **exit 0** — absence of a delta is not a finding. Every hit names
file, line, and the matched removed text verbatim (REQ-OBS-01, REQ-SEC-01 — no
elision; removed text is already in git history).

### 4.2 `plan-coverage` JSON payload

```json
{
  "applicable": true,
  "findings": ["V-001", "V-002", "V-003"],
  "steps": 2,
  "covered": ["V-001", "V-002"],
  "uncovered": ["V-003"]
}
```

`applicable: false` (exit 0) when the document has no `## Findings` section or no
`## Fix Execution Plan` (REQ-CARD-04 analog at the fix-pass level).

### 4.3 Sweep record in the findings document (REQ-SWEEP-05)

Appended under `## Fix Progress`, forge-fix-owned convention (same section as the
`[APPLIED]` lines):

```
- Sweep: {date} — {K} needle(s), {N} survivor(s), {M} disposition(s)
  - {file}:{line} — "{matched removed text}" → FIXED {date}
  - {file}:{line} — "{matched removed text}" → JUSTIFIED: {reason}
  - {file}:{line} — "{matched removed text}" → FALSE-POSITIVE: {reason}
```

or, when skipped: `- Sweep: NOT RUN — no git delta ({reason})`. The disposition
lines are the evidence trail REQ-SWEEP-04 requires; the agent writes them, the
script never mutates any file (REQ-CONC-01: read-only over the corpus).

## 5. API Design

CLI contract (`python3 scripts/fix-sweep.py …`):

```
fix-sweep.py sweep [--repo-root DIR] [--exclude PREFIX]... [--min-chars N] [--json]
fix-sweep.py plan-coverage FINDINGS_DOC [--json]
```

- `sweep` exit codes: `0` no survivors (or skipped — payload says which), `1` one or
  more survivors reported, `2` usage/environment error (e.g. git invocation failure
  in a repo that exists). Default excludes `.verification/` + `adapters/` always
  apply; `--exclude` adds more. `--min-chars` defaults to 24 (exposed for tests, not
  advertised in skill prose — the skill always uses the default).
- `plan-coverage` exit codes: `0` fully covered or not-applicable, `1` uncovered
  findings named, `2` usage error (missing/unreadable document).
- Human-readable default output mirrors the JSON content one line per hit
  (`{file}:{line}: survivor of "{needle}" (removed at {sourceFile}:{sourceLine})`),
  matching the `check-spec-purity.py` reporting style.
- Git invocations follow the repo pattern: `subprocess.run(["git", …],
  capture_output=True, text=True, timeout=<bounded>)`, cwd = repo root; a failed
  `rev-parse --git-dir` or `rev-parse HEAD` routes to the skip shape, any other git
  failure is exit 2.

## 6. Integration Points

1. **`skills/forge-fix/SKILL.md`** — Step 2 (plan-coverage) and Step 4 (sweep +
   dispositions) additions per §3.6, invoking the script through the standard
   plugin-root prelude (`$R/scripts/fix-sweep.py`). Existing `--outcome` rows are
   reused verbatim: `decisions`, `failed` (REQ-SWEEP-06); no Step-5/6/7 text changes
   beyond none — the two-commit protocol, re-verify gate (R-06/C-1), and stage-exit
   call are untouched.
2. **Findings document format** (`skills/forge-verify/references/findings-template.md`)
   — read-only dependency: `plan-coverage` parses `### V-NNN:` headings and
   `**Addresses:**` fields exactly as the template defines them. The template itself
   is not modified; the sweep record extends the forge-fix-owned `## Fix Progress`
   section, which the template does not define.
3. **`skills/forge-verify/SKILL.md`** — numeric totals on lines 33 and 171 only.
   `test_verification_checklists_split.py` dynamically cross-checks these against the
   checklist files, so drift fails CI.
4. **Checklist files** — new entries per §3.7; contiguity and mode-leak tests bind id
   assignment.
5. **Pinned tests** — four files updated in the same change (see §2 table); the
   mode→count table in `test_verification_checklists_split.py` moves to
   `backlog 29 / impl 25 / specs 39`, total `135`.
6. **`scripts/validate.sh` / build** — no changes to validate.sh itself; canon edits
   require `build-adapters.py` regeneration (step 6b drift gate) and the new checklist
   prose must pass `tests/test_adapter_host_neutrality.py`'s zero-host-term
   expectation (write host-neutral from the start, per C-5).
7. **`forge-session.py`** — deliberately untouched. WARNING-level note: the sweep
   does not reuse `_git_output()` (it lives in forge-session.py and is not
   importable without loading the 7k-line module); `fix-sweep.py` carries its own
   ~10-line bounded-subprocess git helper following the same conventions.

## 7. Error Handling

- **Not a git repo / no HEAD** → `sweep` exits 0 with the skip payload; forge-fix
  records the visible NOT-RUN notice (REQ-SWEEP-07). Never silent, never a crash.
- **Git subprocess failure inside a valid repo** (timeout, non-zero on `diff`/
  `ls-files`) → exit 2 with a plain `Error: …` line on stderr; forge-fix surfaces it
  verbatim and closes `failed` (an operational failure, not a skip).
- **Undecodable corpus files** → skipped, counted in `filesScanned` denominator
  reporting only if trivially available; never fatal.
- **Malformed findings document** in `plan-coverage` (no recognizable sections) →
  `applicable: false`, exit 0; an unreadable path → exit 2.
- **Disposition failures** route through forge-fix's existing rows: unresolved
  decision → `decisions`; unfixable → `failed`. The stage still exits exactly once.

## 8. Testing Approach

`tests/test_fix_sweep.py`, pytest + stdlib, following the `test_forge_bootstrap.py`
scratch-repo pattern (`tmp_path` + local `_git()` wrapper + `_set_git_identity()`):

- **F-5 regression fixture** (PRD Success Criteria): scratch repo where a fix removes
  a claim from one artifact while (a) a verbatim sibling copy, (b) a
  whitespace-reflowed variant, and (c) a copy in an un-gated generated file survive;
  plus copies in `.verification/` and in an excluded drift-gated tree. Assert: hits
  for (a), (b), (c) with correct file/line; **no** hits for the audit copy or the
  excluded tree; exit 1.
- **Threshold + normalization units:** needle below 24 normalized chars skipped;
  punctuation/case/whitespace variants match; reflow/move suppression (removed line
  reappearing among added lines yields no needle).
- **Skip path:** non-repo directory and fresh `git init` (no HEAD) both produce the
  skip payload, exit 0 (REQ-SWEEP-07).
- **plan-coverage:** a 16-findings/15-step document names exactly the missing
  finding id (exit 1); full coverage exits 0; a document with no plan section is
  `applicable: false` (REQ-CARD-04 analog).
- **Prose guards** (pattern of `test_lifecycle_artifact_check.py`): CHECK-B29/I24/
  I25/S39 present in their checklist files with their degradation clauses
  ("not-applicable", named-omission wording); forge-fix SKILL.md contains the sweep
  invocation and the NOT-RUN notice wording.
- **Existing pinned tests** updated as enumerated in §2/§6.5 — they, plus the
  dynamic totals cross-check, are the regression net for the count edits.

Full gate: `bash scripts/validate.sh` + `ruff check scripts/ eval/` green, adapters
regenerated with no drift (C-5).

## 9. Dependencies

- **External:** none. Python 3 stdlib only (`argparse`, `subprocess`, `json`, `re`,
  `pathlib`, `datetime`) — C-3. Git available on PATH (its absence is the skip path,
  not an install requirement).
- **Internal:** forge-fix and forge-verify skill prose (integration surfaces, §6);
  findings-template.md section shapes (read-only parse contract); the plugin-root
  prelude for script location. No dependency on `forge-session.py`.
- **Version constraints:** none new; matches the repo's existing "python3 +
  stdlib" floor.

## 10. Open Technical Questions

None blocking. Two deferred-by-design notes:

- **Milestone-2 boundary evidence:** the first real fix pass run with the sweep
  (milestone acceptance, #170) should archive its JSON payload — the
  `droppedNeedles` counts and disposition mix are the evidence base for where the
  mechanical/semantic boundary sits (#171).
- **Threshold revisit:** 24 normalized chars is the milestone-1 default; if the real
  fix pass shows floor-adjacent false negatives, the `--min-chars` knob permits
  evidence-based adjustment without a schema or config change.
