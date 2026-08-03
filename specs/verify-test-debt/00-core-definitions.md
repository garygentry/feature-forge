# 00 — Core Definitions

> Shared contracts for the `verify-test-debt` feature. This feature introduces **no new
> module, no new package, no new dependency, and no new runtime surface** — so this
> document defines the *shared vocabulary* the other seven documents build on: the
> capability clause set, the surface roster, the meta-guard declaration format, the
> structural region model, the two validator contracts, the `UsageError` message shape,
> and the enumerated rosters that several documents cite independently.
>
> Locate every symbol by **name**, never by line number (C-07). Line numbers in this suite
> are as-of-authoring hints and are expected to drift.

## Requirement Coverage

| REQ ID | Requirement | Section |
|---|---|---|
| REQ-GUARD-01 | Canonical capability section is the single source of truth | §3 |
| REQ-GUARD-02 | Every surface carries a paragraph **or** a pointer | §3.3, §4 |
| REQ-GUARD-04 | Enumerated protection set for the prose guard | §5.1 |
| REQ-GUARD-05 | `PROTECTS` / `NON-GOALS` declaration format | §5 |
| REQ-GUARD-06 | Exact-markdown fidelity is a declared non-goal | §5.2 |
| REQ-TRIM-03 | Structural block-scan region model | §6 |
| REQ-FIX-01 | `--version` write-path domain | §7.1 |
| REQ-SEC-01 | `--path` containment | §7.2 |
| REQ-COV-02, REQ-COV-06 | Domains the backfill tests assert against | §7 |
| REQ-BRIT-04 | Exact-stderr roster (5 sites / 11 comparisons) | §9.1 |
| REQ-BRIT-07 | Hash / corrupt-file / gate-selection rosters | §9.2–§9.4 |
| REQ-OBS-01 | Diagnostic-preserving assertion contract | §8.3 |
| REQ-CONC-01 | Single-writer model, no locking | §10.2 |
| REQ-CANON-03 | Narration states intent only | §10.1 |

## 1. Scope and Conventions

Python 3.10+, standard library only. `tests/` may not import any third-party package
except `pytest` — `jsonschema` is absent in CI, so a bare `python3 -m pytest tests` must
run everything in this feature.

Project conventions this feature follows without deviation:

- `Final`, `Literal`, `TypedDict`, and plain dicts at JSON boundaries. **No** Pydantic,
  **no** dataclasses, **no** `jsonschema` at runtime.
- Google-style docstrings with `Args:` / `Returns:` / `Raises:` on every public function.
- `UsageError` for every failure that maps to CLI exit 2 (§8).
- `@pytest.mark.parametrize` for table-driven tests — an established idiom in every file
  this feature touches, so nothing here introduces a new convention.

**No type is added, removed, or retyped.** `.pipeline-state.json` conforms to
`references/pipeline-state-schema.json` exactly as today and needs no migration. The only
contract changes are two **narrowed accepted-input domains** (§7).

## 2. What This Feature Changes — the authoritative inventory

Five workstreams. Every later document owns exactly one:

| Workstream | Document | Requirements | Nature |
|---|---|---|---|
| Prose-guard collapse | `02-canon-and-prose-guard.md` | REQ-GUARD-01..07 | canon edit + test rewrite |
| Machinery trim | `03-machinery-trim.md` | REQ-TRIM-01..07 | test deletion + restructure |
| Production validations | `04-production-validations.md` | REQ-FIX-01, REQ-SEC-01, REQ-FIX-02, REQ-COV-03 | **the only shipped-behavior changes** |
| Coverage backfill | `05-coverage-backfill.md` | REQ-COV-01..07 | new tests |
| Brittleness batch | `06-brittleness-batch.md` | REQ-BRIT-01..07 | assertion loosening + dedup |

`07-testing-strategy.md` owns the gates, the expected counts, and the trial
instrumentation (REQ-TRIAL-\*, REQ-QUAL-\*, REQ-CANON-\*).

## 3. The Capability Rule (REQ-GUARD-01)

### 3.1 Canonical location

The single canonical statement is:

```
references/stage-exit-protocol.md  §  "Host and capability determination"
```

This is a **confirm-and-complete** job — and the *complete* half is real, non-optional
work. Measured against the clause set in §3.2, the canonical section today states:

| Clause | In the canonical section? | Where it actually lives today |
|---|---|---|
| **a** | **yes** — "**(b) tests PERMISSION, not tool presence.**" | canonical section (meaning stated; the fragment `dispatch, not a listed tool` is shared-conventions' wording) |
| **b** | **yes** — "**A consent requirement is `interactive`, not `manual`.**" | canonical section |
| **c1a** | **no** | `shared-conventions.md` § "Verify Capability" |
| **c1b** | **no** | `shared-conventions.md` § "Verify Capability" |
| **c2** | **no** | `shared-conventions.md` § "Verify Capability" |
| **c3** | **no** | `shared-conventions.md` § "Verify Capability" |

The section does additionally carry the Standard Verify Gate and the recovery path in its
`### Clean-room unavailable, or a non-answer` subsection, and the `host`-is-not-a-proxy
rule.

> **The current arrangement is inverted, and that inversion is the defect REQ-GUARD-01
> closes.** Four of the six obligations are stated *only* in the surface designated as the
> **summary**. `02-canon-and-prose-guard.md` §2.3 specifies the paragraph that adds c1a,
> c1b, c2, and c3 to the canonical section. Until that edit lands,
> `test_the_canonical_rule_states_every_clause` is red — by design.

**No size cap constrains this edit.** `check-spec-purity.py::check_body_size` scans
`_skill_md_files(root)` — `skills/*/SKILL.md` — only, so `references/**` has no body-size
limit. C-05 constrains the *skill* surfaces (`01-architecture-layout.md` §3.1), never this
one.

`references/shared-conventions.md` § "Verify Capability" remains a **summary that defers
to it** and MUST NOT be promoted to a second source of truth. It self-identifies as a
partial excerpt ("the two facts that are most often gotten wrong") and omits the gate and
the recovery path. It may keep restating c1a–c3 after the canon edit — a summary that
repeats the canonical rule is still a summary; what it may not do is remain their **only**
home.

### 3.2 The required clause set

The canonical section must state all of the following. These are the *meanings* the guard
checks for — never their exact wording (§5.2).

| Clause | Obligation |
|---|---|
| **a** | Capability (b) is a **permission** test, not a tool-presence test — "may I dispatch `forge-verifier` right now", not "is a dispatch tool listed". |
| **b** | A consent requirement is `interactive`, not `manual`. `manual` requires **neither** a question mechanism **nor** permitted dispatch. |
| **c1a** | An auto-verify directive under a dispatch bar is routed **through the gate**. |
| **c1b** | The gate's affirmative choice **dispatches** the verifier, rather than printing a command for the user to run later. |
| **c2** | That directive is **never silently skipped**. |
| **c3** | It is **never resolved by advancing past** unresolved verification. |

The current `CLAUSES` mapping in `tests/test_capability_determination_prose.py` encodes
these six keys (`a`, `b`, `c1a`, `c1b`, `c2`, `c3`). The **keys and meanings survive**; the
per-surface exact-fragment tuples that encode bold markers do not (§5.2).

Additionally, the canonical section states that `--host` is **not** a capability proxy —
`host == claude` implies nothing in either direction. This is part of the canonical
section's content but is not a clause the guard enumerates.

### 3.3 Paragraph or pointer

A surface satisfies REQ-GUARD-02 by carrying **either**:

- a **paragraph** — its capability region states the clause set; **or**
- a **pointer** — its capability region references the canonical section **by section
  title** (the literal string `Host and capability determination`).

A pointer is recognised **by section title, not by a URL or a path**, so that moving or
renaming the file cannot leave a stale pointer silently passing.

The two existing pointer surfaces are the shape to match. `skills/forge-5-loop/SKILL.md`
and `skills/forge-6-docs/SKILL.md` both read:

> Determine `{verify-capability}` per the **Host and capability determination** section of
> `references/stage-exit-protocol.md`: `interactive` needs both a question mechanism and
> *permission* to dispatch the clean-room `forge-verifier`, and a session that merely
> needs consent first is still `interactive`.

## 4. The Surface Roster (REQ-GUARD-02, REQ-GUARD-03)

### 4.1 Definition

The roster is **all 9 canonical exit sites, with no exclusions**, derived from
`CANONICAL_EXIT_SITES` in `tests/test_stage_exit_protocol.py`:

```python
class CanonicalExitSite(NamedTuple):
    skill: str                    # skill id, matching its directory under skills/
    contract_paths: tuple[str, ...]  # canon files owning this skill's terminal exit
```

| # | Skill | Capability shape today | Under REQ-GUARD-02 |
|---|---|---|---|
| 1 | `forge-0-epic` | **neither** | **fails** → gains a pointer (`02` §3) |
| 2 | `forge-1-prd` | full paragraph | passes today |
| 3 | `forge-2-tech` | full paragraph | passes today |
| 4 | `forge-3-specs` | full paragraph | passes today |
| 5 | `forge-4-backlog` | full paragraph | passes today |
| 6 | `forge-5-loop` | pointer + one paraphrased fact | **passes today** |
| 7 | `forge-6-docs` | pointer + one paraphrased fact | **passes today** |
| 8 | `forge-verify` | full paragraph | passes today |
| 9 | `forge-fix` | full paragraph | passes today |

**The unit is the SITE, not the file — 9 sites carry 10 contract paths.** `forge-5-loop`
owns two: `skills/forge-5-loop/SKILL.md` and
`skills/forge-5-loop/references/result-reporting.md`. Only the first carries its pointer.

> A site passes when **any one** of its `contract_paths` carries the evidence. A per-file
> rule would falsely fail `forge-5-loop`. Neither the PRD nor the tech spec states this
> unit; it is fixed here and applied in `02-canon-and-prose-guard.md` §4.4.

### 4.2 `SURFACES_WITHOUT_PROSE` is deleted, not shrunk

Under the paragraph-**or**-pointer test, two of the constant's three entries already pass
and the third is closed in canon by one added pointer. The exclusion set is therefore
**empty**, and an empty exclusion constant is still a place to encode a future gap.

Deleting it outright is the strongest available reading of REQ-GUARD-03's "in canon, not a
test-side exclusion constant": nothing is left to encode a gap, stale or otherwise.

**No exemption constant may be reintroduced anywhere in this feature.** `03` §4 applies the
same rule to the `--epic` structural scan. An exemption list recreates precisely the
failure mode being removed.

### 4.3 Non-vacuity floor

`MIN_CAPABILITY_SURFACES: Final[int] = 6` is **replaced by a floor of 9** — the roster is
now all nine sites with no exclusions, so 6 would no longer be a meaningful floor.

## 5. Meta-Guard Declaration Format (REQ-GUARD-05)

Research found **zero prior art** in `tests/` — the norm exists only in canon prose
(`spec-archetypes.md`, `stage-exit-protocol.md` § Re-verify scope, `forge-verify/SKILL.md`).
`tests/test_capability_determination_prose.py` is therefore the **template other guards
will copy**, so the format is deliberately plain and greppable rather than
machine-readable.

### 5.1 The format

A module docstring with a `PROTECTS` section and a `NON-GOALS` section:

```python
"""Guard: the capability-determination rule is stated once in canon.

PROTECTS (the enumerated contract — the whole of it):
  1. The canonical section states every required clause.
  2. Every canonical exit surface carries a paragraph or a pointer.
  3. The roster cannot shrink to a vacuous size.
  4. This guard cannot be skipped or disabled.

NON-GOALS (never a finding against this guard):
  - Exact-markdown fidelity: clause-fragment matching, bold-marker
    presence, per-surface formatting equality.
  - Which of paragraph-or-pointer any given surface chooses.
  - The wording of any surface's restatement.
  - Whether a surface's prose is well written or complete beyond
    the clause set.
"""
```

**A module-level `PROTECTS` / `NON_GOALS` tuple pair is rejected.** It invites a meta-test
asserting the declaration exists — the meta-guard-on-a-meta-guard layering this feature
exists to remove.

**The declared set and the shipped test set must be identical.** An undeclared test is
precisely the shape that invites next round's finding; a declared-but-absent protection is
a false claim of coverage.

### 5.2 The load-bearing non-goal (REQ-GUARD-06)

Exact-markdown fidelity is **the specific mechanism that produced the churn**:
clause-fragment matching, bold-marker presence, and per-surface formatting equality.

The `NON-GOALS` block is what makes a verifier's guard-incompleteness finding on that axis
**inadmissible**, per the decision-immunity rule in
`references/stage-exit-protocol.md` § Re-verify scope.

> Reintroducing clause-fragment or bold-marker matching is a **regression, not a
> hardening**, and must be treated as one by any later round.

### 5.3 The meta-guard norm, generally

Any guard this feature writes or rewrites that protects *other tests or prose* must give an
**enumerated protection set** and **explicit non-goals** — never an open-ended objective
("un-rottable", "regardless of form"). The space of ways to evade a guard is not
enumerable, so an unbounded objective produces an arms race of one-shape-per-round
hardening. **The guard's contract is the declared set.**

## 6. The Structural Region Model (REQ-TRIM-03)

The shared model `03-machinery-trim.md` implements. Defined here because
`07-testing-strategy.md` also asserts against it.

### 6.1 Region bounds

The unit of assertion is a fenced `state-*` call **together with the prose attached to
it**, delimited by markdown structure rather than tuned line counts:

```
lower = max( nearest enclosing heading,
             end of the previous fence BLOCK containing a state-* call )
upper = min( next heading,
             start of the next fence BLOCK containing a state-* call )
```

```
  ## Some Section                    <- heading bound
  ...prose: "Add `--epic` when ..."  <- searched
  ```bash
  python3 ... state-note \
    --feature ... --specs-dir ...    <- the call
  ```
  ...prose...                        <- searched
  ```bash                            <- next call's fence block: upper bound
```

The assertion: `--epic` appears somewhere in the region, for **every** call site.

### 6.2 The bound is the fence BLOCK, not the call line

Two `state-*` calls inside the *same* fence — the Git Commit Protocol's commit-1 and
commit-2 `state-complete` pair — share one region; their `--epic` instruction precedes
both. **Bounding on the previous call line produces a false failure on exactly that pair.**

This is specified rather than left to the implementer because the wrong variant looks
correct and fails on one site out of thirty-four.

| Variant | Green on canon | Self-mutation detection |
|---|---|---|
| heading-bounded only | 34/34 | 12/34 |
| **fence-block-bounded (adopted)** | **34/34** | **20/34** |
| call-line-bounded | 33/34 (false failure) | 24/34 |

### 6.3 Fence-aware heading detection is mandatory

A naive `^#{1,6} ` scan misreads bash comments inside fences (e.g.
`# Commit 1 — before \`git commit\``) as headings, truncating the region and producing **2
false failures** in `shared-conventions.md` § Git Commit Protocol.

**The heading index MUST toggle on fence delimiters and ignore any `#` line while inside a
fence.** Specified, not left to the implementer, because the naive version fails in a way
that looks like a canon defect.

### 6.4 Declared boundary — the residual is recorded, not hidden

At 20/34, fourteen sites remain detectable only through a neighbouring call's mandate in
the same region. This is a **real reduction** from the current window's per-site
discrimination, accepted in exchange for removing every tuned integer.

Recorded here so a later round resolves it against a position rather than re-deriving it.
A mutation control pins the `state-artifact` case specifically (`03` §4.4).

### 6.5 Why this is not "a window by another name"

The declared distinction is **tunability only**:

- **Adopted:** bounds are *document structure* (headings, fence delimiters), which move
  with the text. Nothing to tune — which is what makes REQ-TRIM-04 deletable.
- **Replaced:** bounds are *tuned integers* (`LOOKBEHIND = 12`, `LOOKAHEAD = 3`,
  `CALL_SPAN = 3`), which must be re-tuned whenever prose is reflowed.

Detection strength is a **separate axis** and is weaker (§6.4). This claim is not a parity
claim and must not be read as one.

## 7. Validator Contracts

The two narrowed domains. Both narrow only the **rejected** set — every value accepted
before that is still accepted is stored **byte-identically**, so no existing valid state
file is affected and no migration is required.

| Input | Domain before | Domain after |
|---|---|---|
| `state-complete --version` | any `int` | `int >= 1` (matches the read path) |
| `state-artifact --path` | any string | relative, no `..`, no control chars, resolves inside the feature dir |

### 7.1 `_require_positive_int` — reused verbatim (REQ-FIX-01)

Exists today in `scripts/forge-session.py`; **unchanged by this feature**.

```python
def _require_positive_int(value: object, label: str) -> int:
    """Return ``value`` as a positive int, or raise ``UsageError``.

    Args:
        value: The candidate revision/version.
        label: The flag or field name to name in the error.

    Returns:
        The validated positive integer.

    Raises:
        UsageError: Not an int, a bool, or below 1 (→ exit 2).
    """
```

Rejects `bool` explicitly (an `int` subclass — `True` would otherwise sail through as
version 1), non-`int`, and `< 1`.

> **Naming correction.** The PRD names this validator `_positive_int`. **No such symbol
> exists**; the real name is `_require_positive_int`. Every document in this suite uses the
> real name.

### 7.2 `_validated_findings_file` — gains a defaulted `label` (REQ-SEC-01)

**Current signature** (`scripts/forge-session.py`):

```python
def _validated_findings_file(value: str, target_dir: Path) -> str: ...
```

**Required signature:**

```python
def _validated_findings_file(
    value: str, target_dir: Path, label: str = "--findings-file"
) -> str: ...
```

Its *validation* is already target-agnostic. Its *messages* are not — all five `UsageError`
strings hardcode the literal `--findings-file`, and there is no label parameter. Reuse
without this change would make `state-artifact --path ../escape.md` exit 2 **naming a flag
the user never passed**, violating §8's message shape and REQ-OBS-01.

The `--findings-file` **default preserves every existing message byte-for-byte**, so the
sole existing call site in `cmd_state_verify` and all of its tests are unchanged. This is
**not** a behavior change for `state-verify`.

The validator's five rejection branches, each with its own message (§8.2):

| Branch | Condition |
|---|---|
| empty | `not value` |
| control character | any `ord(ch) < 32` or `ord(ch) == 127` |
| absolute | `Path(value).is_absolute()` |
| `..` segment | `".." in Path(value).parts` |
| resolved escape | `(target_dir / candidate).resolve()` is `target_dir.resolve()` or not under it |

It calls `.resolve()`, so a **symlinked** escape is caught. It returns the **original
unresolved string**, so the stored value is unchanged on the success path — no migration,
no rewrite of existing state.

**The PRD's relative/absolute concern does not apply.** Both flags are feature-dir-relative
*by contract*: `--path`'s help reads "Artifact path relative to the feature dir",
`--findings-file`'s reads "relative to and contained by the feature directory". Nothing
about the containment semantics changes.

**Naming is deliberately out of scope.** The helper keeps its name despite gaining a
second, non-findings caller. A rename touches every call site and its tests for no
behavioral gain (`04` §6).

### 7.3 Validation placement

Data flow differs between the two validations, because one needs the resolved path and one
does not:

| Validation | Placement | Why |
|---|---|---|
| `--version` | **before** `_load_state_for_write` | needs no resolved path; mirrors `_assert_full_commit_hash`'s pre-load placement |
| `--path` | **after** the load, **before** any mutation | its containment target is `state_path.parent`, which only the load produces |

In both cases **nothing is mutated before validation**, and `_load_state_for_write` only
reads — so a rejection leaves the state file **byte-identical**. That fail-closed property
is what both placements are reaching for, and it is what the REQ-COV-02 and REQ-COV-06
tests assert.

For `--path`, validation runs over **all** paths before any mutation, so a rejected path in
a repeated `--path` list leaves the state file byte-identical.

## 8. Error Contract

### 8.1 Exit codes

`scripts/forge-session.py` is **0 / 2 only — never 1**. Both new rejections raise
`UsageError`, which the existing top-level handler maps to exit 2. Stdout is empty; the
message is a plain `Error:` line on stderr.

No new exception type is introduced. No `try`/`except` is added around the new validations
— they propagate to the existing top-level handler.

REQ-BRIT-05's widened guard (`06` §6) is what protects the never-1 property.

### 8.2 Message shape

```
{flag} {reason}; {context or corrective action}
```

with the offending value quoted using `!r`. Every public function's docstring carries a
`Raises:` section naming `UsageError` and `(→ exit 2)`.

The two new rejections:

```
$ state-complete --feature f --stage forge-2-tech --version 0
Error: --version must be a positive integer; got 0                    # exit 2

$ state-artifact --feature f --stage forge-3-specs --path ../escape.md
Error: --path '../escape.md' contains a '..' segment; it must stay inside the
feature directory (specs/f)                                           # exit 2
```

The `--path` wording is **not re-invented** — it is the existing message with `{label}`
substituted. The helper emits **one of five** branch-specific messages (§7.2), so the
example above is one branch, **not** a single generic template.

### 8.3 Diagnostic preservation (REQ-OBS-01)

Every assertion loosened in `06-brittleness-batch.md` MUST still fail with a message
identifying **which behavior broke and where**.

**The test for a loosened assertion:** read the failure output alone, and it names the flag
or behavior at fault. A bare `assert "Error" in stderr` is **not acceptable**.

## 9. Enumerated Rosters

These four rosters are cited independently by `06-brittleness-batch.md` and
`07-testing-strategy.md`. They are **verified counts**, not estimates, and they supersede
the figures in PRD v1 (PRD v2 has adopted them).

> **Derivation warning (REQ-TRIAL-06).** Any figure in another document derived from these
> rosters MUST be recomputed **in the same edit** that changes a roster here.

### 9.1 Exact-stderr sites — 5 sites / 11 comparisons / 2 files (REQ-BRIT-04)

| # | File | Test | Comparisons |
|---|---|---|---|
| 1 | `test_forge_root.py` | `test_forge_root_fails_actionably` | 1 (vs `FAILURE_MESSAGE`) |
| 2 | `test_state_verbs.py` | `test_commit_hash_against_an_incomplete_stage_exits_2` | 1 |
| 3 | `test_state_verbs.py` | `test_resumable_with_an_explicit_status_complete_exits_2` | 1 |
| 4 | `test_state_verbs.py` | `test_a_malformed_based_on_token_exits_2_naming_the_token` | 3 (loop) |
| 5 | `test_state_verbs.py` | `test_blocks_current_rejects_anything_but_true_or_false` | 5 (loop) |

PRD v1's "~15 sites spanning more than one file" was an estimate; the exhaustive roster is
the table above. **OQ-01 is resolved by it.**

### 9.2 40-hex hash family — TWO sub-families, 9 sites total (REQ-BRIT-07)

Both PRD v1's "×5" and an earlier tech-spec draft's "4" counted **one sub-family each**.

| Sub-family | `test_state_verbs.py` (hand-rolled loops) | `test_state_schema_conformance.py` (already parametrized) |
|---|---|---|
| `_ACCEPTED_HASHES` — every valid casing accepted | `test_state_complete_accepts_every_40_hex_casing_verbatim`, `test_state_verify_commit_2_accepts_every_40_hex_casing_verbatim` | 2 sites |
| `_REJECTED_HASHES` — short/malformed refused | `test_state_complete_rejects_a_short_or_malformed_hash_before_mutation`, `test_state_verify_commit_2_rejects_a_short_or_malformed_hash_before_mutation`, `test_epic_commit_2_rejects_a_short_or_malformed_hash_before_mutation` | 2 sites |
| **totals** | **5 hand-rolled loops** | **4 parametrized** |

**The five hash loops must NOT be merged into one case.** They exercise three different
verbs (`state-complete`, `state-verify` commit-2, epic commit-2) through different
fixtures, across two different domains (accepted vs rejected). Merging would **delete the
epic-target coverage**. Each is parametrized over its own tuple **in place**.

### 9.3 Corrupt-file refusal family — 4 sites (REQ-BRIT-07)

Three hand-rolled in `test_state_verbs.py`:

- `test_load_state_for_write_refuses_a_corrupt_state_file_byte_intact`
- `test_a_corrupt_or_malformed_epic_state_is_refused_byte_intact`
- `test_every_verb_refuses_a_corrupt_state_file_byte_intact`

Plus `test_state_schema_conformance.py`'s already-parametrized
`test_a_corrupt_state_file_exits_2_and_is_left_byte_identical` — **unchanged**.

**Family boundary, pinned.** `test_load_state_for_write_refuses_a_non_object_state_file` is
**out** of this family — it asserts the *non-object* refusal message, not corrupt-JSON
refusal. The three named tests above are the whole hand-rolled set.

### 9.4 Gate-selection family — 6 sites (REQ-BRIT-07)

**Unit, pinned** (REQ-BRIT-07 leaves it undefined): a gate-selection site is a test
function under the `# autoVerify effectiveness × gate selection` section header in
`tests/test_stage_exit.py`. **The section header is the boundary, not the token.**

That section contains exactly six:

1. `test_auto_verify_off_outstanding_verify_gates_standard`
2. `test_global_auto_verify_runs_in_stage_and_gates_none`
3. `test_per_stage_override_beats_global`
4. `test_non_boolean_auto_verify_fails_closed`
5. `test_invalid_auto_verify_keys_surface`
6. `test_a_manual_capability_gates_manual_print_on_every_host` — **already parametrized**,
   unchanged

Seventeen tests in that file *reference* `verifyGate`; the other eleven assert freshness,
routing, or epic state and are **not** in this family.

### 9.5 Dedup rule — within-file only

Hand-rolled loops become parameterized tests **in place**. Already-parameterized sites are
**untouched**. **Families are never merged across files**: `test_state_verbs.py` asserts
CLI behavior and `test_state_schema_conformance.py` asserts stored-document shape —
merging them would delete real coverage, not redundancy.

## 10. Cross-Document Invariants

### 10.1 Narration states intent only (REQ-CANON-03)

**A hard rule for every fix pass in this feature.** Comments, docstrings, and test
narration state **intent only** — no counts, no "measured", no "probed and confirmed", no
empirical claims. Acceptance evidence belongs in the verification report's Fix Progress
section and in commit messages.

This is the habit that generated rounds 5–9 of the prior epic.

> **This constrains the implementation, not this specification.** The counts in §9 are spec
> content and must **not** be copied into code comments.

### 10.2 Concurrency is out of scope (REQ-CONC-01)

Concurrent writers to `.pipeline-state.json` are **out of scope**. A single forge session
writes at a time; the atomic write protects only against an interrupted or torn write, not
against simultaneous writers.

**No locking protocol is required, and none may be introduced by this feature.** Stated
explicitly so a generic concurrency check (`CHECK-S27`) resolves against a recorded
position — an unstated position has previously induced a full locking protocol that no
requirement asked for.

### 10.3 Declared non-goals

Recorded so a verifier resolves them against a position rather than filing them (C-04):

- **Concurrency and locking** (§10.2).
- **Exact-markdown fidelity** of any capability surface (§5.2).
- **Wall-clock runtime.** Targets are countable, never timed (REQ-QUAL-04).
- **Probe-1 criterion pinning** in the compliance eval (`04` §5).
- **`ruff check tests/` reaching zero.** The requirement is non-increase (≤19).
- **Detection-strength parity** for the structural scan (§6.4).

### 10.4 The cross-test-module import

`tests/test_capability_determination_prose.py` imports `CANONICAL_EXIT_SITES` **from**
`tests/test_stage_exit_protocol.py`:

```python
from test_stage_exit_protocol import CANONICAL_EXIT_SITES
```

This coupling is load-bearing in both directions:

- `02`'s roster derives from it, so it must keep exporting a **9-site tuple**.
- `03`'s trim must **not remove or rename it** while collapsing that file's mutation
  controls.

> **This is the single most likely breakage in the feature**, because the two files are
> edited by different requirements (REQ-GUARD-04 and REQ-TRIM-01) that do not reference
> each other. `01-architecture-layout.md` §5 makes it an explicit sequencing constraint.

### 10.5 No shared CLI wrapper exists

There is **no** shared helper for invoking `forge-session.py`. `tests/conftest.py`'s
`run_cli` fixture is hardcoded to `scripts/epic-manifest.py` and is **not used by any file
in scope**.

Each forge-session test file defines its own thin `subprocess.run` wrapper and loads the
hyphenated module via `importlib.util.spec_from_file_location`:

| File | Wrapper | Module loader |
|---|---|---|
| `test_state_verbs.py` | `_run`, `_feature_dir`, `_state_of` | `_load_forge_session()` |
| `test_auto_verify.py` | `_rank`, `_rank_proc`, `_write_state` | `_load_module()` |
| `test_stage_exit.py` | `_exit`, `_project`, `_epic_project` | `_load_session()` |
| `test_state_schema_conformance.py` | `_run`, `_verb`, `_feature_dir`, `_conforms` | — |
| `test_compliance_eval.py` | `_build`, `_transcript` | `_load_module()` |

**New tests reuse the wrapper already in their host file.** This is the practical reason
the backfill lands beside sibling coverage rather than in a new file (`05` §2).

**`test_auto_verify.py` has two wrapper families — use the right one.** `_rank`,
`_rank_proc`, `_write_state`, and `_completed_prd_state` drive `rank-features` and the pure
classifiers; **they cannot invoke `stage-exit`.** The `stage-exit` wrappers, under that
file's `# Item 012 — the 03 §4.1 stage-exit scheduling boundary` header, are
`_exit_project`, `_stage_exit`, `_exit_ok`, `_tech_state`, and `_read_entry`. REQ-COV-01
and REQ-COV-04 need the second family.

**`tests/test_state_verbs.py` does not import `pytest` and uses no `parametrize` today.**
Verified: zero occurrences of the token in the file. Any work that adds a
`@pytest.mark.parametrize` there — REQ-BRIT-07's five hash loops and three corrupt-file
tests (`06`), and any parametrized backfill test (`05`) — **must add `import pytest`** to
that module. Omitting it is a collection-time `NameError`, not a test failure, so it
presents as the whole file vanishing from the run.

Canon-path resolution goes through `tests/_forge_paths.py` (`REPO_ROOT`, `SKILLS`,
`REFERENCES`, `SCRIPTS`, `read`) — unchanged by this feature. Guards assert against
**canon** (`skills/`, `references/`, `scripts/`) and **never** against the generated
`adapters/` tree.

## 11. Dependencies

**External:** none added. `pytest`, `ruff`, and the stdlib (`json`, `re`, `pathlib`,
`subprocess`, `importlib.util`, `os`, `ast`, `inspect`) are already in use.

Two imports are **removed**:

| Import | From | Because |
|---|---|---|
| `ast` | `test_capability_determination_prose.py` | REQ-GUARD-07 deletes the self-inspection layer |
| `inspect` | `test_state_verb_call_sites.py` | its only use was the REQ-TRIM-05 meta-test |
| `pytest` | `test_capability_determination_prose.py` | the 4-test shape has no `parametrize` and no `pytest.raises`, so it becomes unused |
| `collections.abc.Iterator` | `test_capability_determination_prose.py` | only used by the deleted AST helpers |

The last two are **consequent removals, not new scope**: leaving an unused import is a ruff
`F401` counting against REQ-QUAL-02's ≤19 budget.

`ast` **remains** in `test_stage_exit_protocol.py` and `test_stage_constants_parity.py`,
where it is used for `ast.literal_eval` constant extraction — not self-inspection — and is
out of scope.

**Internal:** `scripts/forge-session.py`, `eval/run-compliance-eval.py`,
`tests/_forge_paths.py`. Python 3.10+ as already required. No version constraint changes.

## 12. Verification

- [ ] `references/stage-exit-protocol.md` § "Host and capability determination" states all
      six clauses in §3.2, and is the only canonical statement.
- [ ] `references/shared-conventions.md` § "Verify Capability" still self-identifies as a
      summary and is not promoted.
- [ ] All 9 roster surfaces in §4.1 carry a paragraph or a title-bearing pointer.
- [ ] `SURFACES_WITHOUT_PROSE` and `MIN_CAPABILITY_SURFACES` no longer exist; no exemption
      constant replaces them anywhere in the feature.
- [ ] The prose guard's module docstring carries `PROTECTS` and `NON-GOALS` sections whose
      protection list is **identical** to the shipped test set.
- [ ] `_validated_findings_file` has the three-parameter signature; every existing
      `--findings-file` message is byte-identical.
- [ ] `state-complete --version 0` exits 2 with the §8.2 message and leaves state
      byte-identical.
- [ ] `state-artifact --path ../escape.md` exits 2 naming `--path`, not `--findings-file`.
- [ ] `from test_stage_exit_protocol import CANONICAL_EXIT_SITES` still resolves after both
      files are edited, and the tuple still has 9 entries.
- [ ] No locking primitive, lockfile, or advisory-lock call appears anywhere in the diff.
- [ ] No comment, docstring, or test narration in the diff carries a count or an empirical
      claim.
