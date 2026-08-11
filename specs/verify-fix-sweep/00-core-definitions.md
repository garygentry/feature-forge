# 00 — Core Definitions

> Shared contracts for the `verify-fix-sweep` feature. The feature introduces **one new
> code artifact** (`scripts/fix-sweep.py`, stdlib-only, two subcommands) plus prose edits
> to two skills and three checklist files — so this document defines the *shared
> vocabulary* every other document builds on: the normalization contract, the needle and
> hit models, both JSON payload schemas, the exit-code convention, the findings-document
> parse contract, the sweep-record grammar, the disposition vocabulary, and the
> constants (matching floor, exclusion rules, CHECK IDs) that several documents cite
> independently.
>
> Locate every symbol and prose anchor by **name**, never by line number. Line numbers
> quoted from existing files (tech-spec §2, §3.7) are as-of-authoring hints and are
> expected to drift.

## Requirement Coverage

| REQ ID | Requirement | Section |
|---|---|---|
| REQ-SWEEP-01 | Sweep extracts corrected text from the fix delta | §4 (needle model), §3 (delta definition) |
| REQ-SWEEP-02 | Deterministic, model-free normalized matching with floor | §2 (normalization), §4.3 (floor), §5.3 (matching) |
| REQ-SWEEP-03 | Corpus = tracked+untracked minus audit + drift-gated trees | §5.1–§5.2 |
| REQ-SWEEP-04 | Every survivor dispositioned before close | §8 (disposition vocabulary) |
| REQ-SWEEP-05 | Sweep record lives in the findings document | §7.2 (sweep-record grammar) |
| REQ-SWEEP-06 | Outcome routing through existing rows | §8.2 |
| REQ-SWEEP-07 | Skip is visible, never silent | §6.1 (skip shape), §7.2 (NOT-RUN notice) |
| REQ-CARD-01 | Plan-coverage assertion, omissions named | §6.2, §7.1 |
| REQ-CARD-04 | Graceful degradation to not-applicable | §6.2 (`applicable: false`) |
| REQ-CARD-02 | Backlog-mode cardinality CHECK id/severity | §9 |
| REQ-CARD-03 | Impl-mode cardinality CHECK id/severity | §9 |
| REQ-CONS-01 | Internal-consistency CHECK IDs | §9 |
| REQ-PERF-01 | Cost model bound to single corpus pass | §5.3 (blob model) |
| REQ-OBS-01 | Hits name file, location, matched text | §6.1 (hit model) |
| REQ-CONC-01 | Read-only over corpus; no locking | §1 (conventions) |
| REQ-SEC-01 | Verbatim echo of removed text; no elision | §6.1 (hit model, `excerpt`/`needle`) |

## 1. Scope and Conventions

Python 3.10+, **standard library only** (C-3): `argparse`, `bisect`, `json`, `re`,
`subprocess`, `sys`, `pathlib`, `typing`. No third-party imports; `tests/` may import
`pytest` only. `datetime` is deliberately absent: dates appear only in the sweep
record, which the agent writes (§7.2).

Project conventions this feature follows without deviation (established by
`scripts/validate-traceability.py` and `scripts/check-spec-purity.py`):

- Shebang + module docstring carrying **Usage** and **Exit codes** sections.
- Module-level constants annotated `Final` with `#:` doc comments.
- `TypedDict` for JSON-boundary shapes; **no** dataclasses, **no** Pydantic.
- Google-style docstrings (`Args:` / `Returns:` / `Raises:`) on every public function.
- `def main() -> int` + `sys.exit(main())` entry pattern.
- Git via `subprocess.run(["git", …], capture_output=True, text=True, timeout=…)`.

**Read-only over the corpus (REQ-CONC-01):** `fix-sweep.py` never writes, locks, or
mutates any repository file. The only writer in this feature is the forge-fix *agent*
appending to the findings document. Single-writer threat model per
`references/decisions/single-writer-threat-model.md` (#180) — cite, do not design
locking (this is the recorded CHECK-S27 position).

**No new config surface (C-6):** no `forge.config.json` keys, no pipeline-state schema
changes, no new forge-fix `--outcome` values.

## 2. Normalization Contract (REQ-SWEEP-02)

One function, applied **identically** to needles and corpus text. Determinism over
cleverness: plain `str.lower()`, no Unicode NFKC folding (milestone 2 may revisit).

```python
def normalize(text: str) -> str:
    """Normalize text for sweep matching.

    Lowercases, maps every non-alphanumeric character to a space, collapses
    whitespace runs to a single space, and strips. Two texts that differ only
    in case, punctuation, or line-wrapping normalize identically — the
    reflowed-prose recall target of REQ-SWEEP-02.

    Args:
        text: Raw text (a diff line or file content).

    Returns:
        The normalized form; possibly the empty string.
    """
```

Reference semantics (the implementation in `02-fix-sweep-script.md` must be
behaviorally identical):

```python
_NON_ALNUM = re.compile(r"[^a-z0-9]+")

def normalize(text: str) -> str:
    return _NON_ALNUM.sub(" ", text.lower()).strip()
```

Note the single regex pass both maps non-alphanumerics to spaces *and* collapses runs
(`+` quantifier); a separate collapse step is unnecessary. "Alphanumeric" here is the
ASCII-and-Unicode set matched by lowercase `str.lower()` output against `[^a-z0-9]` —
i.e. non-ASCII letters normalize to spaces. This is deliberate: the corpus is English
prose and code identifiers; milestone 1 accepts reduced recall on non-ASCII text.

## 3. Fix Delta (REQ-SWEEP-01, tech-spec §3.2)

The **fix delta** is `git diff HEAD --unified=0 --no-color` — staged plus unstaged
changes against `HEAD`, taken **pre-commit** while the fix pass's tree is dirty. The
pre-fix baseline is therefore always the literal string `"HEAD"`; no recorded baseline
hash exists or is needed. Consequences every document inherits:

- The sweep runs as the closing sub-steps of forge-fix **Step 4**, before Step 5's
  Commit 1 (`03-forge-fix-integration.md`).
- Corpus file **content** is read from the **working tree**, so just-corrected sites
  read as corrected, not as survivors (§5.3).
- A survivor fixed during disposition joins the same delta; a re-run of the sweep sees
  its fix's removed lines as new needles (handled by re-run semantics,
  `03-forge-fix-integration.md` §4).

## 4. Needle Model

### 4.1 The `Needle` shape

```python
from typing import TypedDict


class Needle(TypedDict):
    """One removed line surviving extraction filters, in normalized form.

    Keys:
        file: Repo-relative path the line was removed from (diff's a-side path).
        line: 1-based line number in the PRE-fix file (from the @@ hunk header's
            a-side start, plus offset within the hunk's removed run).
        normalized: normalize(original) — the matching key.
        original: The removed line's raw text, verbatim (REQ-OBS-01/REQ-SEC-01:
            echoed without elision; it is already in git history).
    """

    file: str
    line: int
    normalized: str
    original: str
```

### 4.2 Extraction

Needles are the `-`-prefixed lines of the fix delta (excluding `---` file headers),
parsed from `git diff HEAD --unified=0 --no-color`. `--unified=0` makes hunk headers
(`@@ -a,b +c,d @@`) delimit exactly the changed runs, so a-side line numbers are
computable without context-line bookkeeping. Parse contract detail:
`02-fix-sweep-script.md` §4.2.

### 4.3 Filters (applied in order, both counted in `droppedNeedles`)

1. **Length floor:** a needle whose `normalized` is shorter than
   `MIN_NEEDLE_CHARS = 24` characters is dropped (`belowFloor`). The motivating F-5
   claim normalizes to ~40 chars; list bullets, braces, and "see below" fall under the
   floor. The floor is the `--min-chars` CLI default — exposed for tests, not
   advertised in skill prose.
2. **Reflow/move suppression:** a needle whose `normalized` appears as a substring of
   the delta's normalized **added** lines — concatenated per file then joined
   **delta-wide** with a single space between files — is dropped
   (`reflowSuppressed`). Text merely moved or re-wrapped was not corrected; sweeping
   it would flag every reflow as a survivor.

```python
#: Minimum normalized length for a removed line to become a needle (REQ-SWEEP-02).
#: The F-5 claim ("universal among the tracked hyperscalers") normalizes to ~40
#: chars; short structural lines fall under this floor.
MIN_NEEDLE_CHARS: Final[int] = 24
```

Duplicate needles (identical `normalized` from different removed sites) are **kept
distinct** — each carries its own `file`/`line` provenance, and a corpus hit reports
the first extracted needle matching it (deterministic by extraction order; see
`02-fix-sweep-script.md` §4.6).

## 5. Corpus Model (REQ-SWEEP-03)

### 5.1 Path enumeration

```
git ls-files -z --cached --others --exclude-standard
```

(`-z` so paths containing spaces, quotes, or newlines survive intact; no quoting mode
can mangle them.) Tracked files **plus** untracked, non-ignored files — so a surviving claim in a file
the fix pass itself just created is caught, while `.gitignore` keeps build noise out.

### 5.2 Exclusions

```python
#: Path segment excluding findings documents from the corpus — unconditional.
#: Findings documents quote corrected claims by design; they are audit records,
#: not survivors (REQ-SWEEP-03).
VERIFICATION_SEGMENT: Final[str] = ".verification"

#: Drift-gated regenerated tree excluded ONLY when the gate is detectably present:
#: scripts/build-adapters.py exists at the repo root. In a consumer repo without
#: the gate, adapters/ is swept like any other directory (REQ-SWEEP-03 defines a
#: CLASS; adapters/ is this repository's instance).
DRIFT_GATED_PREFIX: Final[str] = "adapters/"
DRIFT_GATE_SENTINEL: Final[str] = "scripts/build-adapters.py"
```

Exclusion rules, in evaluation order per path:

1. Any path containing a `.verification` **segment** (i.e. `".verification" in
   Path(p).parts`) — unconditional, at any depth.
2. Paths under `adapters/` — **only** when `{repo_root}/scripts/build-adapters.py`
   exists. Rationale (recorded, cite don't re-derive): regeneration, not the sweep, is
   the mirror's guarantee; the #167 host-term translation pass means a translated wrong
   claim differs from the canon needle by more than normalization bridges, so sweeping
   the tree gives false confidence while `validate.sh` step 6b already fails the build
   until it is regenerated.
3. Paths starting with any operator-supplied `--exclude <path-prefix>` (repeatable) —
   the consumer-repo escape hatch for their own drift-gated trees. Prefix match is
   against the repo-relative POSIX path string; an empty or whitespace-only prefix
   is rejected (exit 2), never applied.

**No pre-exclusion of historical corpora** (prior features' `specs/`, `CHANGELOG.md`,
`STATUS.md`): the F-5 sibling survivor lived in a spec artifact, so recall wins; hits
there disposition cheaply as "historical record" (§8).

Files that fail UTF-8 decoding are skipped silently (binaries), never fatal.

### 5.3 Normalized-blob matching (REQ-SWEEP-02, REQ-PERF-01)

Each surviving corpus file is read **whole from the working tree** (§3) and normalized
once into a **blob + offset map**:

```python
class NormalizedFile(TypedDict):
    """A corpus file prepared for substring matching.

    Keys:
        path: Repo-relative POSIX path.
        blob: normalize() applied to the full file content — one string, so a
            match spanning the file's original line breaks still lands (the F-5
            whitespace-reflow success criterion).
        line_starts: For each character offset in `blob`, enough structure to map
            a match offset back to the 1-based line number in the ORIGINAL file.
            Concretely: a sorted list of (blob_offset, original_line) pairs; the
            match's line is the last pair whose blob_offset <= match offset
            (bisect). Construction detail: 02-fix-sweep-script.md §4.5.
    """

    path: str
    blob: str
    line_starts: list[tuple[int, int]]
```

Matching is plain substring search: `blob.find(needle["normalized"])` per needle per
file. Cost model (REQ-PERF-01, pinned by shape in `05-testing-strategy.md`, never by
wall-clock): **one** read+normalize pass over the corpus, then O(corpus bytes ×
surviving needles) `str.find` calls, single process, no network, no model calls.

**Self-file hits count:** the file a needle was removed from is still swept — a
surviving duplicate two sections below (the F-5 self-contradiction) is a hit. The
just-corrected site itself does not match because content is read post-fix (§3).

## 6. Payload Schemas

Both subcommands emit human-readable lines by default and a single JSON object on
stdout with `--json`. JSON keys are camelCase (matching the forge convention for JSON
payloads, e.g. `stage-exit`'s `runInStageVerify`).

### 6.1 `sweep` payload

```python
class SweepHit(TypedDict):
    """One surviving occurrence of corrected text (REQ-OBS-01).

    Keys:
        file: Repo-relative path of the surviving occurrence.
        line: 1-based line in the CURRENT working-tree file where the match
            begins (mapped through NormalizedFile.line_starts).
        needle: The matched needle's ORIGINAL removed text, verbatim
            (REQ-SEC-01: no elision — it is already in git history).
        excerpt: The original text of the matched region in the corpus file
            (the line(s) overlapping the match span), verbatim.
        sourceFile: Needle provenance — file the text was removed from.
        sourceLine: Needle provenance — pre-fix line number of the removal.
    """

    file: str
    line: int
    needle: str
    excerpt: str
    sourceFile: str
    sourceLine: int


class DroppedNeedles(TypedDict):
    """Filter counters for the milestone-2 evidence archive (tech-spec §10).

    Keys:
        belowFloor: Count of raw needles dropped because normalize(original) was
            shorter than MIN_NEEDLE_CHARS (§4.3 filter 1). A needle counted here
            is never tested for reflow.
        reflowSuppressed: Count of raw needles dropped because their normalized
            text appears in the delta's normalized added text (§4.3 filter 2).

    Invariant: belowFloor + reflowSuppressed + len(needles) equals the raw
    removed-line count extracted from the delta.
    """

    belowFloor: int
    reflowSuppressed: int


class SweepReport(TypedDict):
    """Top-level `sweep --json` payload.

    Keys:
        skipped: True iff no delta was available (REQ-SWEEP-07).
        reason: None when not skipped; "not-a-git-repo" | "no-head" when skipped.
        baseline: Always "HEAD" when the sweep ran; None when skipped.
        needles: Surviving needles after filters (§4.3).
        droppedNeedles: Filter counters.
        excludes: The exclusion prefixes/segments actually applied this run —
            [".verification/"] always; plus "adapters/" when gated (§5.2); plus
            any --exclude values, in the order applied.
        filesScanned: Count of corpus files read and matched (decode-skipped
            files are not counted).
        hits: All survivors, ordered by (file, line) for determinism.
    """

    skipped: bool
    reason: str | None
    baseline: str | None
    needles: list[Needle]
    droppedNeedles: DroppedNeedles
    excludes: list[str]
    filesScanned: int
    hits: list[SweepHit]
```

**Skip shape (REQ-SWEEP-07):** `{"skipped": true, "reason": "not-a-git-repo" |
"no-head", "baseline": null, "needles": [], "droppedNeedles": {"belowFloor": 0,
"reflowSuppressed": 0}, "excludes": [], "filesScanned": 0, "hits": []}` with
**exit 0** — absence of a delta is not a finding. The forge-fix agent converts this
payload into the visible NOT-RUN notice (§7.2); the script itself never writes it.

### 6.2 `plan-coverage` payload

```python
class PlanCoverageReport(TypedDict):
    """Top-level `plan-coverage --json` payload (REQ-CARD-01, REQ-CARD-04).

    Keys:
        applicable: False when the document has no `## Findings` section or no
            `## Fix Execution Plan` section — exit 0, nothing asserted
            (REQ-CARD-04 analog at the fix-pass level).
        findings: Every V-NNN id found as a `### V-NNN:` heading under
            `## Findings`, in document order.
        steps: Count of `#### Step {N}:` entries under `### Execution Steps`.
        covered: Findings ids appearing in >=1 step's `**Addresses:**` field.
        uncovered: Findings ids appearing in NO step's Addresses field —
            omissions BY NAME, never a count delta.
        claimedTotal: The N parsed from `## Summary`'s `Total findings: {N}`
            line; None when no such line exists.
        actualTotal: len(findings) — re-derived, never trusted from prose.
        totalMismatch: True iff claimedTotal is not None and differs from
            actualTotal. False whenever claimedTotal is None.
    """

    applicable: bool
    findings: list[str]
    steps: int
    covered: list[str]
    uncovered: list[str]
    claimedTotal: int | None
    actualTotal: int
    totalMismatch: bool
```

Exit 1 iff `uncovered` is non-empty **or** `totalMismatch` is true; the human-readable
report prints each uncovered id by name and any mismatch as `claimed N, actual M`.

### 6.3 Exit-code convention (both subcommands)

The standalone-script convention established by `check-spec-purity.py` and
`validate-traceability.py` — the reason this is not a `forge-session.py` verb
(tech-spec §3.1):

| Exit | `sweep` | `plan-coverage` |
|---|---|---|
| 0 | No survivors, **or** skipped (payload's `skipped` says which) | Fully covered and totals consistent, **or** `applicable: false` |
| 1 | One or more survivors reported | Uncovered findings named and/or claimed-total mismatch |
| 2 | Usage/environment error (git failure inside a valid repo, bad flag) | Usage error (missing/unreadable document) |

Exit-2 messages are a plain `Error: …` line on **stderr** with empty stdout — the
`epic-manifest.py resolve` convention; callers surface the line verbatim.

## 7. Findings-Document Contract

### 7.1 Read contract (parsed by `plan-coverage`; owned by `findings-template.md`)

`skills/forge-verify/references/findings-template.md` is a **read-only dependency** —
this feature does not modify it. The shapes parsed, exactly as the template defines
them:

| Anchor | Shape | Regex (authoritative in 02) |
|---|---|---|
| Findings section | `## Findings` heading | `^## Findings\s*$` |
| Finding heading | `### V-NNN: {title}` | `^### (V-\d{3}):` |
| Plan section | `## Fix Execution Plan` | `^## Fix Execution Plan\s*$` |
| Steps section | `### Execution Steps` | `^### Execution Steps\s*$` |
| Step heading | `#### Step {N}: {title}` | `^#### Step \d+:` |
| Addresses field | `- **Addresses:** {V-NNN ids}` | `^\s*-\s*\*\*Addresses:\*\*` then `V-\d{3}` findall |
| Summary total | `- Total findings: {N}` under `## Summary` | `Total findings:\s*(\d+)` |

A document lacking `## Findings` **or** `## Fix Execution Plan` is
`applicable: false` (§6.2). Section scoping is by heading level: a `### V-NNN:`
heading counts only between `## Findings` and the next `##` heading; `**Addresses:**`
fields count only after `### Execution Steps` within `## Fix Execution Plan`.

### 7.2 Write contract (sweep record; authored by the forge-fix **agent**, never the script)

Appended under `## Fix Progress` — the forge-fix-owned section the template does not
define — in the same section as the `[APPLIED]` step lines (REQ-SWEEP-05):

```
- Sweep: {date} — {K} needle(s), {N} survivor(s), {M} disposition(s)
  - {file}:{line} — "{matched removed text}" → FIXED {date}
  - {file}:{line} — "{matched removed text}" → JUSTIFIED: {reason}
  - {file}:{line} — "{matched removed text}" → FALSE-POSITIVE: {reason}
```

(`{date}` is ISO `YYYY-MM-DD`.)

Or, when the payload is the skip shape (REQ-SWEEP-07):

```
- Sweep: NOT RUN — no git delta ({reason})
```

where `{reason}` is the payload's `reason` value verbatim. Grammar rules:

- `{K}`/`{N}`/`{M}` come from the payload (`len(needles)`, `len(hits)`) and the
  disposition lines written; `M == N` when the pass closes on an advancing outcome
  (every survivor dispositioned, REQ-SWEEP-04).
- One disposition line per hit, `→` followed by exactly one of the three uppercase
  disposition tokens (§8.1).
- A re-run after disposition edits appends a **second** `- Sweep:` block; previously
  dispositioned hits are matched by `(file, needle)` and not re-dispositioned
  (`03-forge-fix-integration.md` §4).

## 8. Disposition Vocabulary (REQ-SWEEP-04, REQ-SWEEP-06)

### 8.1 The three dispositions

Detection is mechanical; disposition is judgment — a hit is a candidate, not
automatically a defect. Every hit must carry exactly one:

| Token | Meaning | Effect |
|---|---|---|
| `FIXED` | The survivor was corrected now, in this pass | The edit joins the working-tree delta and rides Commit 1; its path is staged **enumerated** (`03-forge-fix-integration.md` §5) |
| `JUSTIFIED: {reason}` | Deliberate quote / historical record; stands by decision | Recorded reason is the audit trail; no edit |
| `FALSE-POSITIVE: {reason}` | Normalized match is not actually the corrected claim | Recorded reason; no edit; candidate evidence for the milestone-2 boundary (tech-spec §10) |

### 8.2 Outcome routing — existing rows only (C-6)

No new `--outcome` values. The mapping onto forge-fix Step 7's existing table:

| Sweep situation | forge-fix `--outcome` |
|---|---|
| Every hit dispositioned | (unchanged — whatever the pass otherwise closes: `reverified`, `applied`, …) |
| A survivor awaits a user decision | `decisions` |
| A survivor is unfixable/unjustifiable, or the sweep tool exits 2 | `failed` |
| Sweep skipped (no delta) with notice recorded | (unchanged — the notice is the whole obligation) |

An undispositioned survivor therefore prevents every **advancing** close; the pass
still closes exactly once through Step 7 (`references/stage-exit-protocol.md`).

## 9. Verification CHECK Constants (REQ-CARD-02/03/04, REQ-CONS-01)

Four new checklist entries, **next-in-sequence** ids (the contiguity test in
`tests/test_verification_checklists_split.py` requires exactly this; current maxima
confirmed against the live tree: B28, I23, S38):

| CHECK ID | File | Section (new) | Covers | Severity of a true hit |
|---|---|---|---|---|
| `CHECK-B29` | `verification-checklists/backlog.md` | `### Work-Order Cardinality` | REQ-CARD-02 | `gap` (blocking) |
| `CHECK-I24` | `verification-checklists/impl.md` | `### Work-Order Cardinality` | REQ-CARD-03 | `gap` (blocking) |
| `CHECK-I25` | `verification-checklists/impl.md` | `### Internal Consistency` | REQ-CONS-01 | `inconsistency` (advisory); `error` only when decision-bearing |
| `CHECK-S39` | `verification-checklists/specs.md` | `### Internal Consistency` | REQ-CONS-01 | `inconsistency` (advisory); `error` only when decision-bearing |

All four degrade to **not-applicable** when their trigger structure is absent
(REQ-CARD-04) — never a hard fail. All four are **verifier judgment** (checklist
prose, C-2): no mechanical extractor ships in milestone 1. Wording must be
**host-neutral** (C-5): the checklist files carry zero host terms and are not
translation-exempt. Full prose: `04-verification-checks.md`.

Per-mode expected totals move in lockstep: `backlog 28→29`, `impl 23→25`,
`specs 38→39`, checklist inventory `131→135`. Every pinned site is enumerated in
`01-architecture-layout.md` §4 and `05-testing-strategy.md`.

## 10. Error Model

`fix-sweep.py` defines one exception type; everything else routes through exit codes:

```python
class UsageError(Exception):
    """A caller/environment error that maps to exit 2.

    Raised for: an unreadable findings document, a git invocation that fails
    inside a valid repository (timeout, non-zero exit on diff/ls-files), a
    repository with no working tree (a bare repo: `rev-parse --git-dir`
    succeeds while `rev-parse --show-toplevel` fails), or invalid flag
    combinations. The message is printed as `Error: {msg}` on stderr; stdout
    stays empty (exit-2 convention, §6.3).
    """
```

Classification rules (tech-spec §7):

- `git rev-parse --git-dir` fails → **skip shape** (`reason: "not-a-git-repo"`), exit 0.
- `git rev-parse --show-toplevel` fails in a valid repo (bare repository, no working
  tree) → `UsageError`, exit 2.
- `git rev-parse HEAD` fails in a valid repo (unborn branch) → **skip shape**
  (`reason: "no-head"`), exit 0.
- Any *other* git failure (diff/ls-files non-zero, timeout) → `UsageError`, exit 2 —
  an operational failure, not a skip; forge-fix closes `failed`.
- Undecodable corpus file → silently skipped, excluded from `filesScanned`.
- Corpus file unreadable, vanished, or a directory entry (`OSError`) → silently
  skipped, excluded from `filesScanned`.
- Malformed findings document (no recognizable sections) → `applicable: false`,
  exit 0; unreadable path → `UsageError`, exit 2.

## 11. Dependencies

None — this is the suite's root document. External read-only contracts it binds to:

- `git` on PATH (its absence is the skip path, not an install requirement).
- `skills/forge-verify/references/findings-template.md` section shapes (§7.1).
- `references/decisions/single-writer-threat-model.md` (REQ-CONC-01 position).

## 12. Verification

- [ ] `normalize()` reference semantics: case/punctuation/whitespace variants of the
      same sentence produce identical output; distinct sentences do not collide.
- [ ] All four TypedDict payload shapes match the JSON examples in tech-spec §4
      key-for-key (camelCase at the JSON boundary).
- [ ] Exit-code table matches tech-spec §5 exactly (0/1/2 per subcommand).
- [ ] The four CHECK ids are next-in-sequence against the live checklist files.
- [ ] The sweep-record grammar round-trips: a record written per §7.2 is parseable by
      the re-run matcher (`(file, needle)` identity) in `03-forge-fix-integration.md`.
