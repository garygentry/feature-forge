# verify-test-debt — Technical Specification

> Locate every symbol by **name**, never by line number (C-07). Line numbers in this
> document are as-of-authoring hints only and are expected to drift.

## 1. Overview

This feature has no new module, no new dependency, and no new runtime surface. It is four
edit workstreams over existing files, plus two narrow production validations:

| Workstream | PRD | Nature |
|---|---|---|
| Prose-guard collapse | R-10 / REQ-GUARD-01..07 | canon edit + test rewrite |
| Machinery trim | R-11 / REQ-TRIM-01..07 | test deletion + restructure |
| Coverage backfill | R-12 / REQ-COV-01..07, REQ-FIX-01, REQ-SEC-01 | new tests + 2 validations |
| Brittleness batch | R-13 / REQ-BRIT-01..07 | assertion loosening + dedup |

Four architectural decisions shape the rest:

1. **Canon lives in `references/stage-exit-protocol.md` § "Host and capability
   determination"** — it already is the source of truth; REQ-GUARD-01 is a
   confirm-and-complete job, not an authoring job (§3.1, resolves OQ-02).
2. **`SURFACES_WITHOUT_PROSE` is deleted outright, not shrunk** — under REQ-GUARD-02's
   paragraph-**or**-pointer test, two of its three entries already pass; one added pointer
   empties the set (§3.2).
3. **REQ-TRIM-03's stated mechanism is unachievable and is replaced by a structural block
   scan** that satisfies its intent — only 2 of 34 fenced calls literally carry `--epic`
   (§3.5).
4. **REQ-FIX-02 surfaced no new defect.** The one candidate was investigated and
   disproved (§3.12).

**Three PRD figures are superseded by verified rosters** in this document (§10.1). They
also appear in PRD §8 Success Criteria and are flagged for amendment; per the recorded
decision, this spec carries the corrected values and the PRD is not re-versioned mid-trial.

## 2. Module Structure

No package is created. Files touched, by role:

```
references/
  stage-exit-protocol.md          canon: capability determination (§3.1)
  shared-conventions.md           unchanged; already defers to the above
skills/
  forge-0-epic/SKILL.md           + one pointer sentence (§3.1)
scripts/
  forge-session.py                + 2 validations (§3.7, §3.8)
eval/
  run-compliance-eval.py          + PRELUDE_CRITERIA key-set pin (§3.13)
tests/                            see §8 for the full per-file plan
adapters/{claude,codex,copilot,cursor,gemini,pi}/
                                  regenerated, never hand-edited (§3.15)
```

**Public API surface: unchanged.** No CLI verb, flag, exit code, or JSON payload key is
added or removed. The two validations narrow the *accepted domain* of two existing flags;
they do not change any success-path output.

## 3. Technical Decisions

### 3.1 Canonical capability section (REQ-GUARD-01, REQ-GUARD-02, REQ-GUARD-03 — resolves OQ-02)

**Decision.** `references/stage-exit-protocol.md` § "Host and capability determination"
is the single canonical section. `references/shared-conventions.md` § "Verify Capability"
remains a summary that points to it.

**Rationale (evidence-backed).** That section already states clause (a), clause (b), the
permission fact, the consent fact, the `host`-is-not-a-proxy rule, and — in its
`### Clean-room unavailable, or a non-answer` subsection — the recovery path. Both existing
pointer surfaces (`forge-5-loop`, `forge-6-docs`) name it *by section title*. Every
restating surface cites it as "full rule" and shared-conventions as "summary". The
codebase already treats it as canonical; this decision ratifies rather than relocates.

**REQ-GUARD-03 — the forge-0-epic gap.** `skills/forge-0-epic/SKILL.md` is the only
stage-closing skill that passes `--verify-capability` with no guidance anywhere in the
file. It receives a **pointer**, not a restatement, matching `forge-5-loop` and
`forge-6-docs` verbatim in shape. Insertion point: immediately before the
`**Close this stage with the Scripted Stage Exit**` sentence in Step C8 — the same
structural position every sibling uses.

The gap is closed **in canon**. `SURFACES_WITHOUT_PROSE` is not edited to accommodate it;
it is deleted (§3.2).

**Alternatives considered.** Making shared-conventions § "Verify Capability" canonical was
rejected: it self-identifies as a partial excerpt ("the two facts that are most often
gotten wrong") and omits the Standard Verify Gate and the recovery path, so promoting it
would require duplicating prose that already lives in stage-exit-protocol.md. Authoring a
third distinct section was rejected as adding a surface while R-10 is collapsing surfaces.

**Constraint check (C-05) — measured, not inferred.** `check-spec-purity.py::check_body_size`
enforces `MAX_BODY_LINES = 300` and `MAX_BODY_WORDS = 5000` against the **body** —
`text.split("\n")[fm.body_start_line:]`, i.e. everything after the closing frontmatter
fence — **not** the file. Measured with that exact rule:

| Skill | File lines | Body lines | Body words | Headroom |
|---|---|---|---|---|
| `skills/forge-0-epic/SKILL.md` | 302 | **295** / 300 | 2749 / 5000 | **+5 lines** |
| `skills/forge-verify/SKILL.md` | 306 | **299** / 300 | 4365 / 5000 | **+1 line** |

Neither file is over the cap, which is why `check-spec-purity.py` reports 0 violations. A
one-sentence pointer in `forge-0-epic` fits within its 5 lines of headroom. `forge-verify`
has one line, so no capability prose may be added there — this is what C-05 actually
constrains.

The pointer-not-paragraph decision does **not** rest on headroom. It stands on the
shape-matching rationale above (`forge-5-loop` / `forge-6-docs` already use a pointer) and
on R-10's goal of collapsing restatements rather than adding a seventh.

### 3.2 Surface roster and constant deletion (REQ-GUARD-02, REQ-GUARD-03)

**Decision.** The roster is **all 9 canonical exit sites**, derived from
`CANONICAL_EXIT_SITES` with **no exclusions**. `SURFACES_WITHOUT_PROSE` is deleted.

**Rationale.** The current constant excludes three surfaces because the current guard
tests for a *paragraph*. REQ-GUARD-02 tests for a paragraph **or a pointer**, and under
that test:

| Surface | Shape | Under REQ-GUARD-02 |
|---|---|---|
| forge-1-prd, forge-2-tech, forge-3-specs, forge-4-backlog, forge-verify, forge-fix | full paragraph | passes today |
| forge-5-loop, forge-6-docs | pointer + one paraphrased fact | **passes today** |
| forge-0-epic | neither | fails → §3.1 adds a pointer |

The exclusion set is therefore empty after one canon edit. Deleting the constant is the
strongest available reading of REQ-GUARD-03's "in canon, not a test-side exclusion
constant": nothing is left to encode a gap, stale or otherwise.

**Detecting "pointer".** A surface satisfies the check if its capability region contains
either the clause set (paragraph) **or** a reference to the canonical section by title. A
pointer is recognised by the section title string, not by a URL or path, so a file move
does not silently pass a stale pointer.

### 3.3 Guard file shape (REQ-GUARD-04, REQ-GUARD-05, REQ-GUARD-06, REQ-GUARD-07)

**Decision.** `tests/test_capability_determination_prose.py` becomes **4 tests / 4
collected items**, down from 13 functions / 43 items — one under the REQ-GUARD-04 cap.

```
1. test_the_canonical_rule_states_every_clause      protection 1
2. test_every_surface_has_a_paragraph_or_pointer    protection 2
3. test_the_guard_is_not_vacuous                    protection 3 (roster >= 9)
4. test_this_guard_is_not_skippable                 self-check
```

Deleted: the 6 parametrized negative-control tests (36 items), the AST self-inspection
test and its three helpers (`_module_scope_nodes`, `_store_target_names`,
`_module_scope_writes`) per REQ-GUARD-07, `test_the_roster_is_derived_not_listed`,
`test_the_delegating_surfaces_still_point_somewhere_real`, and the constants
`SURFACES_WITHOUT_PROSE`, `MIN_CAPABILITY_SURFACES` (replaced by a floor of 9), and the
clause-fragment tuples that encode bold markers.

The self-check is a **fourth declared protection**, not an addition beyond the three
REQ-GUARD-04 enumerates: it protects the guard's *existence* rather than the rule, and
REQ-GUARD-04's cap of 5 accommodates it. Declaring it is what keeps the shipped test set
and the `PROTECTS` block identical — an undeclared test is precisely the shape that invites
next round's finding.

**Why 4 and not 5.** The cap is a ceiling, not a quota. `test_the_roster_is_derived_not_listed`
is dropped because the hand-listing risk it guarded *was* `SURFACES_WITHOUT_PROSE`, which
§3.2 deletes; and it is the test most entangled with the `ast` layer REQ-GUARD-07 removes.
`test_this_guard_is_not_skippable` is retained because every sibling guard in this repo
carries it and its absence would let a `skipif` silently disable the file.

**REQ-GUARD-05 — declaration format.** A module docstring with `PROTECTS` and `NON-GOALS`
sections. Research found **zero prior art** in `tests/`; the norm exists only in canon
prose (`spec-archetypes.md`, `stage-exit-protocol.md` § Re-verify scope,
`forge-verify/SKILL.md`). This file is therefore the template other guards will copy, so
the format is chosen to be plain and greppable rather than machine-readable:

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

A module-level `PROTECTS`/`NON_GOALS` tuple pair was rejected: it invites a meta-test
asserting the declaration exists, which is the meta-guard-on-a-meta-guard layering this
feature removes.

**REQ-GUARD-06 — the declared non-goal is load-bearing.** Exact-markdown fidelity is the
specific mechanism that produced the churn. The `NON-GOALS` block above is what makes a
verifier's guard-incompleteness finding on that axis inadmissible, per the decision-immunity
rule in `references/stage-exit-protocol.md`. Reintroducing clause-fragment or bold-marker
matching rebuilds the problem and must be treated as a regression, not a hardening.

### 3.4 Mutation-control trim (REQ-TRIM-01, REQ-TRIM-02)

**Decision.** Keep all **7 mutation classes**, one collected item each — 67 → 7. Each
surviving control mutates a **single fixed representative exit site**, not all 9.

| Mutation class | Items now | After |
|---|---|---|
| remove the scripted invocation | 9 | 1 |
| duplicate terminal print instruction | 9 | 1 |
| duplicate scripted invocation | 9 | 1 |
| restore a retired bespoke block | 18 | 1 |
| hand-typed sentinel | 9 | 1 |
| drop a branch ownership token | 4 | 1 |
| drop the nested no-terminal-block rule | 9 | 1 |
| **total** | **67** | **7** |

**Rationale.** The per-site contract is identical by construction — that is what
`test_each_covered_skill_satisfies_the_scripted_exit_contract` already proves across all 9
sites. Running each *mutation* against all 9 re-proves site-uniformity 7 more times rather
than testing 7 different things. A fixed representative (rather than a rotating one) keeps
a failure explainable: the same site always exercises the same class.

**REQ-TRIM-02 — the preserve list is a hard floor.** These two tests keep their full
parametrization over all 9 sites and are **out of scope for trimming**:

- `test_each_covered_skill_satisfies_the_scripted_exit_contract` (9 items)
- `test_scripted_stamp_stamped_verbatim` (9 items)

They are golden-file assertions on the rendered stamp, not mutation controls. The risk
REQ-TRIM-01 carries is over-deletion; this list is the guard on the trim itself. Two
further positive tests — `test_the_loop_surface_covers_every_loop_outcome` and
`test_the_docs_surface_covers_both_docs_outcomes` — are not stamp-verbatim but are also
positive assertions and are likewise not trimmed.

### 3.5 Structural `--epic` check (REQ-TRIM-03, REQ-TRIM-04, REQ-TRIM-05, REQ-TRIM-06)

**The requirement's stated mechanism cannot be implemented.** REQ-TRIM-03 specifies
"each fenced `state-*` call contains `--epic`". Measured against current canon:

- **34** fenced `state-*` call sites exist across `skills/*/SKILL.md` and
  `references/shared-conventions.md`.
- **2** literally contain `--epic`.
- **32** do not — the mandate lives in the prose attached to each fence, which is
  precisely why `LOOKBEHIND` exists.
- At least one call (`shared-conventions.md`, the epic-scoped `state-verify` under
  `--stage forge-0-epic`) must **never** carry `--epic`, so the rule could not hold
  universally even after a canon rewrite.

**Decision.** Honor the requirement's intent — *remove the proximity window* — with a
**structural block scan**. The unit of assertion becomes the fenced call together with the
prose attached to it, delimited by **markdown structure** rather than tuned line counts:

```
lower = max( nearest enclosing heading,
             end of the previous fence BLOCK containing a state-* call )
upper = min( next heading,
             start of the next fence BLOCK containing a state-* call )

  ## Some Section                    <- heading bound
  ...prose: "Add `--epic` when ..."  <- searched
  ```bash
  python3 ... state-note \
    --feature ... --specs-dir ...    <- the call
  ```
  ...prose...                        <- searched
  ```bash                            <- next call's fence block: upper bound
assert '--epic' appears somewhere in region, for every call site
```

**The bound is the fence BLOCK, not the call line.** Two `state-*` calls inside the *same*
fence (the Git Commit Protocol's commit-1 and commit-2 `state-complete` pair) share one
region — their `--epic` instruction precedes both. Bounding on the previous *call line*
instead produces a false failure on that pair; bounding on the enclosing fence block does
not. This distinction is specified because the wrong variant looks correct and fails on
exactly one site.

**Measured against current canon:**

| Variant | Green on canon | Self-mutation detection |
|---|---|---|
| heading-bounded only | 34/34 | 12/34 |
| **fence-block-bounded (adopted)** | **34/34** | **20/34** |
| call-line-bounded | 33/34 (false failure) | 24/34 |

Detection is measured by removing each site's *own* `--epic` mandate (its current
`LOOKBEHIND`/`LOOKAHEAD` window) and asking whether the guard still reports that site. The
adopted variant recovers the `state-artifact` case specifically (§ Stage-Entry Guard),
which is the documented regression below.

**Declared boundary — the residual is recorded, not hidden.** At 20/34, fourteen sites
remain detectable only through a neighbouring call's mandate in the same region. This is a
real reduction from the current window's per-site discrimination, accepted in exchange for
removing every tuned integer. It is recorded here so a later round resolves it against a
position rather than re-deriving it.

**The regression this addresses.** `tests/test_state_verb_call_sites.py`'s `LOOKBEHIND`
docstring records that at 20 the lookbehind reached past a block's own mandate into the
preceding block's, so deleting the `state-artifact` mandate left the guard green on the
strength of an unrelated `state-enter` mandate — which is why `LOOKBEHIND` is 12. Both
calls sit under one `## Stage-Entry Guard` heading, so a heading-only region merges them.
The fence-block bound separates them and restores detection on that exact case.

**Verified against current canon: 34/34 pass, zero exemptions.** The epic-scoped
`state-verify` passes naturally because its own prose reads "`--epic` must be absent or
exactly equal to it" — the region contains the token without the call needing it. No
exemption list is introduced, and none may be: an exemption constant here would recreate
the `SURFACES_WITHOUT_PROSE` failure mode §3.2 removes.

**Implementation subtlety — fence-aware heading detection is mandatory.** A naive
`^#{1,6} ` scan misreads bash comments inside fences (e.g. `# Commit 1 — before
\`git commit\``) as headings, which truncates the region and produces 2 false failures in
`shared-conventions.md` § Git Commit Protocol. The heading index MUST toggle on fence
delimiters and ignore any `#` line while inside a fence. This is specified, not left to
the implementer, because the naive version fails in a way that looks like a canon defect.

**Why this is not "a window by another name."** The declared distinction: the bounds are
**document structure** (headings, fence delimiters), which move with the text, versus
**tuned integers** (`LOOKBEHIND = 12`, `LOOKAHEAD = 3`, `CALL_SPAN = 3`), which must be
re-tuned whenever prose is reflowed. The former has nothing to tune, which is what makes
REQ-TRIM-04 deletable.

This claim is about **tunability only**. Detection strength is a separate axis and is
weaker (20/34 vs the window's per-site discrimination) — measured above and recorded as a
declared boundary rather than asserted as parity.

**Consequent deletions:**

- `LOOKBEHIND`, `LOOKAHEAD`, `CALL_SPAN` constants and `_call_sites()`'s window slicing.
- `test_the_window_is_no_wider_than_the_measured_maximum` (REQ-TRIM-04) — its three
  assertions bound constants that no longer exist.
- `test_the_failure_message_describes_the_whole_window` (REQ-TRIM-05) — the
  `inspect.getsource` meta-test asserting another test's failure-message wording.
- `SKIP_STATUS_RE`'s `CALL_SPAN`-based line flattening is replaced by the same structural
  region, so Guard 3 (`test_every_skip_recording_surface_persists_the_skip_through_state_verify`)
  keeps its protection without the flattening window.

**One test is ADDED as a replacement, not a net deletion.** Removing
`test_the_window_is_no_wider_than_the_measured_maximum` removes the only bound on the
guard's discriminating width; a site-count floor cannot detect an over-wide region, and
nothing else fails when the guard stops discriminating — which is how the original hole
shipped. Its structural equivalent is a **mutation control**: delete one known site's own
`--epic` mandate from an in-memory copy of `shared-conventions.md` and assert Guard 1
reports that site. Use the `state-artifact` site (§ Stage-Entry Guard), because that is the
case the recorded regression names. This is one test inside REQ-TRIM-04's budget and is the
only thing that fails if the region silently widens again.

**REQ-TRIM-06 — preserved unchanged.** `test_the_epic_mandate_itself_is_still_documented`
pins the normative rule in `shared-conventions.md` rather than a mechanism, and survives
verbatim. `MIN_CALL_SITES` and `test_the_epic_guard_is_not_vacuous` also survive — the
non-vacuity floor is independent of how regions are computed.

### 3.6 Source-text assertion removal (REQ-TRIM-07)

**Decision.** Remove exactly the source-text assertions in
`tests/test_stage_constants_parity.py` that duplicate a runtime check **in the same test**:

- In `test_the_exit_domains_are_derived_not_hand_listed`: the substring checks
  `"EXIT_STAGES: Final[...] = get_args(ExitStage)" in source` and the per-alias
  `f"frozenset(get_args({alias}))" in source` loop. The two runtime assertions immediately
  above them (`session.EXIT_STAGES == get_args(session.ExitStage)` and the `EXIT_OUTCOMES`
  comparison) already prove the values are `get_args`-derived.

`test_the_cli_stage_choices_are_the_whole_exit_domain`'s `assert "choices=EXIT_STAGES" in
source` is **retained**. It is cited in the PRD, but no runtime check in this file
currently establishes the same fact, so removing it would delete coverage rather than
duplication. REQ-TRIM-07 scopes to assertions that "duplicate an existing runtime check";
this one has no counterpart. Converting it to a runtime `argparse`-choices inspection is
recorded as out of scope (§10.2).

### 3.7 `--version` domain (REQ-FIX-01, REQ-COV-02)

**Confirmed defect.** `p_comp.add_argument("--version", type=int, required=True, ...)` —
`type=int` is the only validator. The value reaches `cmd_state_complete` and is written to
`entry["version"]` and passed to `_cascade_staleness` unchecked. The read path
`_require_positive_int(value, label)` rejects `< 1`, non-`int`, and `bool`. So
`--version 0` writes `"version": 0`, which a later `state-verify` read then refuses at
exit 2 — poisoning the state file at write time and failing at read time.

> The PRD names this validator `_positive_int`. **No such symbol exists**; the real name
> is `_require_positive_int`.

**Decision.** Call `_require_positive_int(version, "--version")` in `cmd_state_complete`
**unconditionally, before `_load_state_for_write`**, mirroring the placement of
`_assert_full_commit_hash`.

**Interaction with REQ-COV-05 — stated explicitly to pre-empt a false finding.** The
commit-2 (`--commit-hash`) and `--resumable` paths do not *write* `--version`, but argparse
**requires** it on every invocation. Validating unconditionally therefore means those paths
now reject `--version 0` too. This is intentional and consistent: "ignored" in REQ-COV-05
means **not written**, not **not validated**. `_assert_full_commit_hash` sets the precedent
by validating before branch dispatch. The REQ-COV-05 test (§3.11) must assert the
write/validate distinction rather than treating any rejection as a contract break.

**Alternative considered.** Validating only inside the write branch would leave
`--version 0` silently accepted on two paths, so a copy-pasted recovery command could
carry an invalid value that later becomes valid-looking. Rejected as a narrower fix that
preserves half the defect.

**Error message** — matching the file's convention exactly:

```
Error: --version must be a positive integer; got 0
```

### 3.8 `--path` containment (REQ-SEC-01, REQ-COV-06)

**Current state.** `cmd_state_artifact(feature, stage, paths, specs_dir, epic)` appends
each `--path` value to `stages.{stage}.artifacts` verbatim — no absolute-path check, no
`..` check, no containment check, no control-character check.

**Decision.** Reuse `_validated_findings_file` per path, **adding a defaulted `label`
parameter**. Its *validation* is already target-agnostic; its *messages* are not — all five
`UsageError` strings hardcode the literal `--findings-file`, and there is no label
parameter. Reuse without that change would make `state-artifact --path ../escape.md` exit 2
naming a flag the user never passed, violating §7's message shape and REQ-OBS-01.

```python
def _validated_findings_file(
    value: str, target_dir: Path, label: str = "--findings-file"
) -> str: ...
```

Replace the hardcoded `--findings-file` in all five messages with `{label}`. The default
preserves every existing message **byte-for-byte**, so the sole existing call site in
`cmd_state_verify` and its tests are unchanged — this is not a behavior change for
`state-verify`.

```python
state_path, state = _load_state_for_write(specs_dir, feature, epic)
target_dir = state_path.parent
for path in paths:
    _validated_findings_file(path, target_dir, label="--path")
```

The validator rejects: empty string, control characters (`ord < 32` or `127`), absolute
paths, a literal `..` segment, and a resolved escape (it calls `.resolve()`, so a symlinked
escape is caught) — **five branch-specific messages, not one generic message**. It returns
the **original unresolved string**, so the stored value is unchanged on the success path —
no migration, no rewrite of existing state.

Validation runs over **all** paths before any mutation, so a rejected path in a repeated
`--path` list leaves the state file byte-identical.

**The PRD's relative/absolute concern does not apply.** Both flags are feature-dir-relative
*by contract* — `--path`'s help reads "Artifact path relative to the feature dir",
`--findings-file`'s reads "relative to and contained by the feature directory". The
adaptation is the defaulted `label` parameter plus the loop; nothing about the containment
semantics changes.

**Naming.** The helper is currently named for its original caller. It gains a second caller
here; renaming it is deliberately **out of scope** (§10.2) — a rename touches every call
site and its tests for no behavioral gain, in a feature with a 2-round verify budget.

### 3.9 Corrupt-state read/write asymmetry (REQ-COV-01)

**Behavior, verified.** `stage_exit`'s routing read uses `_read_state`, which is tolerant:
`except (OSError, json.JSONDecodeError): return {}`. The auto-verify debt write inside
`_schedule_auto_verify_debt` reloads the same file through `_load_state_for_write`, which
is strict and raises `UsageError` on unparseable JSON.

| autoVerify | `_schedule_auto_verify_debt` reached? | Outcome on a corrupt file |
|---|---|---|
| **on** | yes | `UsageError` → **exit 2, no payload printed at all** |
| **off** | no | succeeds normally on `{}`-degraded defaults; file untouched |

**Decision.** Test both arms as **golden**. The asymmetry is defensible: the tolerant read
only *classifies*, the strict write *mutates*, and refusing to overwrite a corrupt state
file is the fail-closed convention every `state-*` verb follows.

**Recorded trade-off.** This blesses an outcome where a corrupt state file makes
`stage-exit` unusable under auto-verify with no payload explaining why. Making the failure
diagnostic was considered and rejected for this feature: it changes `stage_exit`'s output
contract, which is heavily golden-file tested, and the churn risk is unjustifiable against
REQ-TRIAL-01's 2-round budget. Recorded in §10.2 as a candidate for later work, not as a
defect this feature leaves unfixed.

### 3.10 Debt-write idempotency (REQ-COV-04)

**Behavior, verified.** `_schedule_auto_verify_debt` early-returns when the prior entry is
already `auto-verify-pending` at the current revision, **before** calling `_commit_state`.
`scheduledAt`, top-level `updatedAt`, and the file bytes are therefore all untouched — and
`_now_iso()` is never evaluated on that path, so the guarantee holds by construction rather
than by timestamp coincidence.

**Decision.** Assert at the **byte level**: capture `read_bytes()` before and after a
second `stage-exit` at the same revision and assert equality. A field-by-field comparison
would pass even if `updatedAt` were refreshed, which is exactly the regression this pins.

### 3.11 Commit-2 flag precedence (REQ-COV-05)

**Behavior, verified.** When `--commit-hash` is passed, `cmd_state_complete` sets **only**
`entry["commitHash"]`, after asserting the stage is already `complete`. It never reads
`based_on`, `artifacts`, `status`, `resumable`, or `preserve_commit_hash`. "Ignoring" is
implemented by **branch precedence**, not by explicit rejection — the flags are accepted by
argparse and discarded.

**Decision.** Test that a commit-2 call carrying `--based-on`, `--artifact`, and
`--preserve-commit-hash` writes only `commitHash` and leaves `status`, `completedAt`,
`version`, `basedOnVersions`, and `artifacts` byte-identical. Per §3.7, the test must
**not** assert that `--version` is unvalidated on this path — validation and writing are
separate concerns, and conflating them would pin the REQ-FIX-01 defect as golden.

One pre-existing guard runs before branch dispatch and is unaffected:
`--resumable` with `--status complete` raises regardless of `--commit-hash`.

### 3.12 Epic back-pointer degradation (REQ-COV-07) — REQ-FIX-02 disposition

**A candidate defect was investigated and disproved.** The claim under review was that
`row["epic"]` flows unvalidated into `specs_dir / row["epic"] / name`. It does not:
`_scan_features` derives the epic name from the **parent directory enumerated off disk**
(`top.name` from `iterdir()`), not from the state file's `epic` field. The value is a real
directory name by construction and cannot contain a traversal segment. (A function named
`_derive_epic` does not exist in `forge-session.py`.)

**The real surface.** The on-disk `epic` **field** is read and used for routing in
`stage_exit`, and is already guarded:

```python
epic_name = epic or state.get("epic")
route_epic = (
    epic_name if isinstance(epic_name, str) and SAFE_NAME_RE.match(epic_name) else None
)
```

`SAFE_NAME_RE` is `^[a-z0-9]+(?:-[a-z0-9]+)*$`. An unsafe value degrades `route_epic` to
`None` — the standalone route — rather than crashing a stage closing.

**Decision.** REQ-COV-07 is a **coverage test of correct existing behavior**, matching the
requirement's own wording ("degradation behavior"). Assert that an on-disk `epic` failing
`SAFE_NAME_RE` produces the standalone route and a successful exit.

**Residual, deliberately not changed.** The validated `route_epic` drives routing, but the
**unvalidated** `epic_name` is still interpolated into the printed reconcile command
`f"/feature-forge:forge-0-epic {epic_name}"`. This is a display string, and an unsafe name
is rejected by the resolver at exit 2 if the user runs it — it fails closed, just later.
Changing it would touch `stage_exit`'s golden-file-tested payload. The test asserts the
degradation only and does **not** pin the interpolation as golden, so REQ-FIX-02's warning
against pinning questionable behavior is respected. Recorded in §10.2.

**Conclusion: REQ-FIX-02 adds no work.** The behavior changes in this feature remain
exactly the two named in PRD §3.3.

### 3.13 Eval criterion key-set pin (REQ-COV-03 — resolves OQ-03)

**The PRD's premise is superseded.** `resolver_line_identical` is **not** "computed and
never checked". `score_prelude` returns it as one of four keys, and `_to_result` computes
`compliant = all(criteria.values())` — so it is fully load-bearing for a run's compliance
flag. **OQ-03 is resolved: it already asserts equality; no change to its role is needed.**

**The real gap is narrower.** Probe 3 pins its criterion key set:

```python
BRANCH_CRITERIA: Final[tuple[str, ...]] = (...)   # 9 keys
```
with `tests/test_compliance_eval.py` asserting both `tuple(criteria) == SPEC_BRANCH_CRITERIA`
and `ce.BRANCH_CRITERIA == SPEC_BRANCH_CRITERIA` against its own independent copy. Probe 2
(prelude) and probe 1 (stage-exit) have **no equivalent constant**, so a criterion could be
dropped and silently change what "compliant" means.

**Decision.** Add `PRELUDE_CRITERIA: Final[tuple[str, ...]]` mirroring `BRANCH_CRITERIA`,
pinning the four keys `attempted_resolver`, `byte_identical`, `resolver_line_identical`,
`functionally_equivalent`; and a test mirroring the existing two-sided assertion. Probe 1
is **out of scope** — REQ-COV-03 names the prelude criterion only, and PRD §6 freezes the
compliance eval beyond what REQ-COV-03 requires.

### 3.14 Brittleness batch (REQ-BRIT-01..07 — resolves OQ-01)

**REQ-BRIT-01.** `test_an_injected_write_failure_exits_2_with_no_dispatch_directive` in
`tests/test_auto_verify.py` chmods a directory to `0o555` with no root guard. Add the exact
sibling idiom used in `test_effective_config.py` and `test_stage_exit.py`:

```python
@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="a read-only directory stays writable as root",
)
```

**REQ-BRIT-02.** Two scanners in `tests/test_state_verbs.py`:
- `test_tempfile_is_imported_and_jsonschema_is_not` — `"jsonschema" not in source` would
  false-flag a comment explaining why jsonschema is unused. Narrow to import statements.
- `test_every_canon_mention_of_amend_forbids_it` — accepts any line containing "never" or
  "without" anywhere, so `"Do this without checking, then run --amend."` passes while
  `"--amend is forbidden"` fails. Match the negation against the clause governing
  `--amend`, not the whole line.

**REQ-BRIT-03.** `test_docs_never_reimplements_the_epic_dependency_derivation` in
`tests/test_stage_exit.py` scans the entire `forge-session.py` source for three forbidden
tokens. Narrow to the `_render_status` function body — the same slicing idiom the adjacent
`test_docs_resolves_the_helper_beside_itself_and_never_a_bare_python3` already uses. This
is the only unsliced token ban in the file; every other site already scopes.

**REQ-BRIT-04 — roster corrected (resolves OQ-01).** The PRD estimates ~15 sites spanning
more than one file. Exhaustive search found **5 assertion sites across exactly 2 files**,
totalling **11 runtime comparisons**:

| # | File | Test | Comparisons |
|---|---|---|---|
| 1 | `test_forge_root.py` | `test_forge_root_fails_actionably` | 1 (vs `FAILURE_MESSAGE`) |
| 2 | `test_state_verbs.py` | `test_commit_hash_against_an_incomplete_stage_exits_2` | 1 |
| 3 | `test_state_verbs.py` | `test_resumable_with_an_explicit_status_complete_exits_2` | 1 |
| 4 | `test_state_verbs.py` | `test_a_malformed_based_on_token_exits_2_naming_the_token` | 3 (loop) |
| 5 | `test_state_verbs.py` | `test_blocks_current_rejects_anything_but_true_or_false` | 5 (loop) |

Each becomes a substring or regex assertion pinning the **diagnostic content** — the flag
name and the offending value — without the incidental wording around it. Per REQ-OBS-01,
every loosened assertion must still name which behavior broke; a bare
`assert "Error" in stderr` is not acceptable.

**REQ-BRIT-05.** `test_the_script_has_no_exit_1_branch` uses
`re.search(r"^\s+return 1$", source, re.M)` and `re.search(r"sys\.exit\(1\)", source)`.
Both are literal-spelling traps, evadable by `return  1` (two spaces), `code = 1; return
code`, `raise SystemExit(1)`, `os._exit(1)`, `exit(1)`, or `sys.exit( 1 )`. Widen to cover
whitespace variance and the `SystemExit`/`os._exit`/bare-`exit` spellings.

**REQ-BRIT-06.** `tests/test_state_schema_conformance.py`, inside
`test_epic_commit_2_records_the_hash_in_the_documented_minimal_shape`:
`assert list(state) == ["epic", "updatedAt", "stages"]` pins JSON key **insertion order**.
Becomes `assert set(state) == {"epic", "updatedAt", "stages"}`.

**REQ-BRIT-07 — dedup, within-file only.** Parameterize in place; **never merge across
files**. `test_state_verbs.py` asserts CLI behavior and `test_state_schema_conformance.py`
asserts stored-document shape — merging them would delete real coverage, not redundancy.

**The 40-hex hash family is TWO families, totalling 9 sites.** Both the PRD's "×5" and an
earlier draft of this spec's "4" counted one sub-family each. The complete roster:

| Sub-family | `test_state_verbs.py` (hand-rolled loops) | `test_state_schema_conformance.py` (already parametrized) |
|---|---|---|
| `_ACCEPTED_HASHES` — every valid casing accepted | `test_state_complete_accepts_every_40_hex_casing_verbatim`, `test_state_verify_commit_2_accepts_every_40_hex_casing_verbatim` | 2 sites |
| `_REJECTED_HASHES` — short/malformed refused | `test_state_complete_rejects_a_short_or_malformed_hash_before_mutation`, `test_state_verify_commit_2_rejects_a_short_or_malformed_hash_before_mutation`, `test_epic_commit_2_rejects_a_short_or_malformed_hash_before_mutation` | 2 sites |
| **totals** | **5 hand-rolled loops** | **4 parametrized** |

| Family | Action |
|---|---|
| 40-hex hash (**9 sites**) | **5** hand-rolled loops in `test_state_verbs.py` → `parametrize` **in place, one per test**; the 4 in `test_state_schema_conformance.py` are already parametrized — **unchanged** |
| corrupt-file refusal (3 sites) | 3 hand-rolled in `test_state_verbs.py` → 1 parametrized; `test_state_schema_conformance.py`'s own parametrized version — **unchanged** |
| gate selection (**6 sites** — PRD figure confirmed) | 5 unparametrized in `test_stage_exit.py` → 1 parametrized; the 6th is already parametrized over host — **unchanged** |

**Do not merge the five hash loops into one case.** They exercise three different verbs
(`state-complete`, `state-verify` commit-2, epic commit-2) through different fixtures, and
two different domains (accepted vs rejected). Each is parametrized over its own tuple in
place; merging would delete the epic-target coverage.

**Gate-selection unit, pinned (REQ-BRIT-07 leaves it undefined).** A gate-selection site is
a test function under the `# autoVerify effectiveness × gate selection` section header in
`tests/test_stage_exit.py`. That section contains exactly 6:
`test_auto_verify_off_outstanding_verify_gates_standard`,
`test_global_auto_verify_runs_in_stage_and_gates_none`,
`test_per_stage_override_beats_global`, `test_non_boolean_auto_verify_fails_closed`,
`test_invalid_auto_verify_keys_surface`, and the already-parametrized
`test_a_manual_capability_gates_manual_print_on_every_host`. Seventeen tests in that file
*reference* `verifyGate`, but the other eleven assert freshness, routing or epic state and
are **not** in this family — the section header is the boundary, not the token.

`@pytest.mark.parametrize` is an established idiom in all three files, so this introduces
no new convention.

### 3.15 Canon and adapter obligations (REQ-CANON-01, REQ-CANON-02, REQ-CANON-03)

Every edit to `skills/` or `references/` requires `python3 scripts/build-adapters.py` and
committing all six mirrors in the **same commit**; `--check` is a hard gate in
`scripts/validate.sh`. `references/**` is copied verbatim into each bundle, so the §3.1
canon edit propagates mechanically; the `forge-0-epic` skill edit propagates through the
per-skill emitters with host-term translation for non-Claude targets.

`check-spec-purity.py` must report 0 violations. Its seven rules include the body-size cap
(§3.1's open risk), prelude byte-identity, and a self-containment ratchet that bans new
spec-document citations in `scripts/`, `references/`, `skills/`, and `eval/`. **This spec
lives in `specs/`, which is not a shipped surface, so its own citations are unaffected —
but any prose added to canon must not cite this document.**

**REQ-CANON-03 is a hard rule for every fix pass.** Comments, docstrings, and test
narration state **intent only** — no counts, no "measured", no "confirmed", no empirical
claims. Acceptance evidence belongs in the verification report and commit messages. This is
the habit that generated rounds 5–9 of the prior epic. Note that this constrains the
implementation, not this specification: the counts in §3.14 and §10.1 are spec content and
must **not** be copied into code comments.

## 4. Data Model

No persisted structure changes. `.pipeline-state.json` conforms to
`references/pipeline-state-schema.json` exactly as today; no field is added, removed, or
retyped, and no migration is required.

Two **accepted-input domains** narrow:

| Input | Domain before | Domain after |
|---|---|---|
| `state-complete --version` | any `int` | `int >= 1` (matches the read path) |
| `state-artifact --path` | any string | relative, no `..`, no control chars, resolves inside the feature dir |

Both narrow only the rejected set. Every value accepted before that is still accepted is
stored byte-identically, so no existing valid state file is affected.

## 5. API Design

CLI surface is unchanged in shape. Two new rejections, both exit 2 with a plain `Error:`
line on stderr and empty stdout — the established contract for `UsageError`:

```
$ state-complete --feature f --stage forge-2-tech --version 0
Error: --version must be a positive integer; got 0                    # exit 2

$ state-artifact --feature f --stage forge-3-specs --path ../escape.md
Error: --path '../escape.md' contains a '..' segment; it must stay inside the
feature directory (specs/f)                                           # exit 2
```

The `--path` wording is **not re-invented**: it is the existing `_validated_findings_file`
message with `{label}` substituted (§3.8). The helper emits **one of five** branch-specific
messages — empty value, control character, absolute path, `..` segment, resolved escape —
so the example above is one branch, not a single generic template. The `--findings-file`
default keeps every existing message byte-identical.

**Exit-code contract preserved.** The script is 0/2 only — never 1. Both new rejections
raise `UsageError`, which the existing top-level handler maps to exit 2. REQ-BRIT-05's
widened guard protects this property.

## 6. Integration Points

### 6.1 `scripts/forge-session.py` — verified signatures

| Symbol | Signature | Role |
|---|---|---|
| `cmd_state_complete` | `(feature, stage, version, ...) -> dict` | §3.7 validation site |
| `cmd_state_artifact` | `(feature: str, stage: str, paths: list[str], specs_dir: Path, epic: str \| None) -> dict` | §3.8 validation site |
| `_require_positive_int` | `(value: object, label: str) -> int` | reused verbatim by §3.7 |
| `_validated_findings_file` | `(value: str, target_dir: Path, label: str = "--findings-file") -> str` | §3.8 adds the defaulted `label`; the default keeps every existing message byte-identical |
| `_assert_full_commit_hash` | `(commit_hash) -> None` | placement precedent for §3.7 |
| `_load_state_for_write` | `(...) -> tuple[Path, dict]` | strict read; §3.9 |
| `_read_state` | `(state_path: Path) -> dict` | tolerant read; §3.9 |
| `_schedule_auto_verify_debt` | `(specs_dir, feature, epic, stage, verify_key) -> None` | §3.9, §3.10 |
| `_scan_features` | `(specs_dir: Path) -> list[tuple[str, str \| None, dict]]` | §3.12 — epic from `iterdir()` |
| `SAFE_NAME_RE` | `^[a-z0-9]+(?:-[a-z0-9]+)*$` | §3.12 |

Data flow differs between the two validations, because one needs the resolved path and one
does not:

- **`--version`** validates **before** the load — it needs no resolved path, so it mirrors
  `_assert_full_commit_hash`'s pre-load placement.
- **`--path`** validates **after** the load and **before** any mutation, because its
  containment target is `state_path.parent`, which only the load produces.

In both cases nothing is mutated before validation, and `_load_state_for_write` only reads,
so a rejection leaves the state file byte-identical — the fail-closed property both
placements are reaching for.

### 6.2 `eval/run-compliance-eval.py`

`score_prelude` returns the four-key criteria dict consumed by `_to_result`'s
`all(criteria.values())`. `BRANCH_CRITERIA` is the pinning pattern to mirror (§3.13). No
fixture changes — PRD §6 freezes the eval beyond REQ-COV-03.

### 6.3 Cross-test-module import — a constraint on the trim

`tests/test_capability_determination_prose.py` imports `CANONICAL_EXIT_SITES` **from**
`tests/test_stage_exit_protocol.py`. This coupling is load-bearing in both directions:

- §3.3's roster derives from it, so it must keep exporting a 9-site tuple.
- §3.4's trim must not remove or rename it while collapsing that file's mutation controls.

**Verify this import still resolves after both edits.** It is the single most likely
breakage in this feature, because the two files are edited by different requirements
(REQ-GUARD-04 and REQ-TRIM-01) that do not reference each other.

### 6.4 Per-file CLI wrappers

There is **no** shared helper for invoking `forge-session.py`. `tests/conftest.py`'s
`run_cli` fixture is hardcoded to `scripts/epic-manifest.py`. Each forge-session test file
defines its own thin `subprocess.run` wrapper (`_rank`, `_exit`, …) and loads the
hyphenated module via `importlib.util.spec_from_file_location`. **New tests reuse the
wrapper already in their host file** (§8) — this is the practical reason the backfill lands
beside sibling coverage rather than in a new file.

### 6.5 In-progress feature conflicts

Sibling specs exist under `specs/` (`agent-agnostic`, `context-efficiency`,
`context-management`, `epic-orchestration`, `forge-bootstrap`, `stage-exit-coverage`).
`stage-exit-coverage` is this feature's direct antecedent and owns the exit-coverage
contract that §3.4 trims controls for; its artifacts are complete, so no concurrent write
conflict exists. No other in-progress feature touches `tests/` or the capability surfaces.

## 7. Error Handling

One convention, already established, extended to two new sites:

- Every rejected argument raises `UsageError` — "a usage or I/O failure that must exit 2".
- Message shape: `{flag} {reason}; {context or corrective action}`, quoting the offending
  value with `!r`.
- Every public function's docstring carries a `Raises:` section naming `UsageError` and
  `(→ exit 2)`.
- Validation happens **before any mutation** — and before the load where the validator does
  not depend on the resolved path (§6.1). A rejection never leaves a partially written file.

No new exception type is introduced. No `try`/`except` is added around the new validations
— they propagate to the existing top-level handler.

**REQ-OBS-01 applies to every loosened assertion in §3.14.** A substring or regex
replacement must still identify which behavior broke and where. The test for a widened
assertion is: read the failure output alone, and it names the flag or behavior at fault.

## 8. Testing Approach

### 8.1 Backfill placement

Each test lands beside existing coverage of the same subject, reusing that file's CLI
wrapper (§6.4):

| Req | Behavior | File |
|---|---|---|
| REQ-COV-01 | corrupt state × autoVerify on/off | `tests/test_auto_verify.py` |
| REQ-COV-02 | `--version` domain | `tests/test_state_verbs.py` |
| REQ-COV-03 | prelude criterion key-set pin | `tests/test_compliance_eval.py` |
| REQ-COV-04 | debt-write idempotency (byte-level) | `tests/test_auto_verify.py` |
| REQ-COV-05 | commit-2 ignores conflicting flags | `tests/test_state_verbs.py` |
| REQ-COV-06 | `--path` containment | `tests/test_state_verbs.py` |
| REQ-COV-07 | unsafe epic back-pointer degradation | `tests/test_stage_exit.py` |

This mapping is the audit trail for "each of the seven gaps has a named test" — the
backfill is not visible as a single file, so the table is the deliverable a verifier checks
against.

### 8.2 Net test-count effect

| File | Before | After | Delta |
|---|---|---|---|
| `test_capability_determination_prose.py` | 43 items | **4** | −39 |
| `test_stage_exit_protocol.py` — mutation controls | 67 items | **7** | −60 |
| `test_stage_exit_protocol.py` — stamp-verbatim | 18 items | **18** | 0 (REQ-TRIM-02) |
| `test_stage_exit_protocol.py` — everything else | 17 items | **17** | 0 |
| `test_state_verb_call_sites.py` | 10 tests | **9** | −2 deletions, +1 mutation control |
| REQ-COV backfill | — | **+7** named tests | +7 |
| `PRELUDE_CRITERIA` pin (§3.13) | — | **+1** | +1 |
| REQ-BRIT-07 dedup | 13 hand-rolled functions | **3** parametrized functions | ≈0 collected |

The two `test_state_verb_call_sites.py` deletions are named in §3.5:
`test_the_window_is_no_wider_than_the_measured_maximum` and
`test_the_failure_message_describes_the_whole_window`. **No third deletion exists** —
`MIN_CALL_SITES`, `test_the_epic_guard_is_not_vacuous`, the canon-mandate test, both Guard
3 tests and the not-skippable check all survive.

**Units.** The dedup row counts *test functions* (5 hash + 3 corrupt + 5 gate = 13
hand-rolled → 3 parametrized); the 4 already-parametrized sites are untouched and are not
in either column. Parametrizing preserves the individual cases, so the row is
approximately neutral in *collected items* — it reduces function count, not coverage.

**Expected suite total:** 1842 collected today → **≈1750** after
(1842 − 39 − 60 − 1 + 7 + 1), ± the dedup's collected-item delta. This is the number
REQ-QUAL-01's full-suite check compares against.

### 8.3 Verification gates (REQ-QUAL-01..04)

Run for every fix pass, in this order:

1. `python3 -m pytest tests -q` — baseline 1840 passed / 2 skipped; must stay green.
2. `python3 scripts/build-adapters.py` then `--check` exits 0 (REQ-CANON-01).
3. `python3 scripts/check-spec-purity.py` — 0 violations (REQ-CANON-02).
4. `ruff check scripts/ eval/` — clean.
5. `ruff check tests/` — **≤19 errors** (REQ-QUAL-02); fewer becomes the new baseline,
   more is a regression. Driving it to zero is explicitly out of scope.
6. `bash scripts/validate.sh` — "All checks passed!" (REQ-QUAL-03).

`validate.sh` runs the full pytest suite as one step and both canon gates as hard gates, so
step 6 subsumes 1–5; the earlier steps exist for fast local feedback.

**C-02 caveat:** after any `git checkout`/`merge`/`pull`, adapter file modes can land 0664
from the ambient umask and fail the mode test. Re-run `build-adapters.py` to restore 0644;
content is unaffected. Do not investigate this as a content defect.

### 8.4 What this feature does not test

Declared non-goals, so a verifier resolves them against a recorded position rather than
filing them:

- **Concurrency** (REQ-CONC-01). Single-writer is the model; the atomic write protects
  against a torn write, not simultaneous writers. No locking protocol may be introduced.
- **Exact-markdown fidelity** of any capability surface (REQ-GUARD-06, §3.3).
- **Wall-clock runtime.** Targets are countable, never timed (REQ-QUAL-04).
- **Probe-1 criterion pinning** in the compliance eval (§3.13).
- **`ruff check tests/` reaching zero.** The requirement is non-increase.

## 9. Dependencies

**External:** none added. `pytest`, `ruff`, and the stdlib (`json`, `re`, `pathlib`,
`subprocess`, `importlib.util`, `os`) are already in use. The `ast` import is **removed**
from `test_capability_determination_prose.py` (REQ-GUARD-07); it remains in
`test_stage_exit_protocol.py` and `test_stage_constants_parity.py`, where it is used for
`ast.literal_eval` constant extraction, not self-inspection, and is out of scope.

`inspect` is removed from `test_state_verb_call_sites.py` — its only use was the
REQ-TRIM-05 meta-test.

**Internal:** `scripts/forge-session.py`, `eval/run-compliance-eval.py`,
`tests/_forge_paths.py` (`REPO_ROOT`, `SKILLS`, `REFERENCES`, `SCRIPTS`, `read`) — the
shared path layer these guards use, unchanged. `tests/conftest.py` is not used by any file
in scope and is not modified.

**Version constraints:** none. Python 3.10+ as already required.

## 10. Open Technical Questions

### 10.1 Resolved during this spec

- **OQ-01 (exact-stderr roster)** — resolved: **5 sites / 11 comparisons across 2 files**,
  enumerated in §3.14. The PRD's "~15" is superseded.
- **OQ-02 (canonical section)** — resolved: reuse
  `references/stage-exit-protocol.md` § "Host and capability determination"; no new section
  (§3.1).
- **OQ-03 (`resolver_line_identical`)** — resolved: it already asserts equality via
  `all(criteria.values())`. The gap is the missing key-set pin (§3.13).

**PRD figures superseded — flagged for amendment, recorded in pipeline state:**

| PRD | States | Verified |
|---|---|---|
| §3.4 / §8 | ~15 exact-stderr sites | 5 sites / 11 comparisons, 2 files |
| §3.4 / §8 | hash matrices ×5 | **incomplete, not wrong** — ×5 is the `_REJECTED_HASHES` sub-family; the full roster across both sub-families is **9 sites / 5 hand-rolled loops** (§3.14) |
| §3.3 | `resolver_line_identical` computed, never checked | checked via `all(criteria.values())` |

**Confirmed correct and NOT superseded:** REQ-BRIT-07's gate-selection ×6. Re-derived
against the section header in `tests/test_stage_exit.py` (§3.14); the PRD figure is exact.

Per the recorded decision, the PRD is **not** re-versioned mid-trial — a version bump would
cascade `forge-2-tech` to stale and re-trigger PRD verification, spending trial rounds on a
numeric correction. This spec is the authority for these three rosters.

### 10.2 Open, with a recorded position

1. **`_validated_findings_file` naming.** Gains a second, non-findings caller and a
   `label` parameter in §3.8. Not renamed — a rename touches every call site and test for
   no behavioral gain.
2. **`stage_exit`'s unvalidated `epic_name` in the reconcile command string** (§3.12).
   Fails closed downstream. Not changed; not pinned as golden either.
3. **Corrupt-state + auto-verify-ON produces no payload** (§3.9). Tested as golden this
   round; making the failure diagnostic is deferred as an output-contract change.
4. **`test_the_cli_stage_choices_are_the_whole_exit_domain`'s source-text assertion**
   (§3.6). Retained — no runtime counterpart exists, so removal would delete coverage.
   Converting it to an `argparse`-choices inspection is out of scope.
5. **Structural-scan detection residual** (§3.5). 20/34 sites carry per-site
   discrimination; the rest are covered only through a neighbouring mandate. Recorded as a
   declared boundary of the guard, with a mutation control pinning the `state-artifact`
   case.

**Resolved during verification round 1** (was item 1): the body-size cap. `check_body_size`
measures the body after the closing frontmatter fence, so `forge-0-epic` has +5 lines and
`forge-verify` +1 — both under the cap, and `check-spec-purity.py` reports 0 violations.
The measurement is now stated in §3.1 and there is no pre-implementation check outstanding.

### 10.3 Trial instrumentation (REQ-TRIAL-01..03)

REQ-TRIAL-02 is a **hard stop**, not a guideline: if any single stage reaches a third
verify round, work stops, R-05..R-08 reopen, and this feature does not continue through the
pipeline. Pushing through destroys the measurement, which is the point of the trial.

The trial runs the **full** pipeline — PRD → tech spec → specs → backlog → loop → docs
(C-06) — because the rules under trial operate at every stage. Two of those rules bear
directly on how findings against this spec should be read:

- **C-03 (severity floor).** An inaccuracy confined to a comment, docstring, or test
  narration caps at `inconsistency` and does not block a stage. This is what makes
  REQ-CANON-03 enforceable without re-creating the churn: narration drift is corrected,
  not treated as a blocking defect.
- **C-04 (re-verify scope).** A re-verify confirms the prior report's findings; new
  findings below `error` do not block it, and a finding with a recorded decision is never
  re-filed. Every "recorded position" in §10.2 and every declared non-goal in §8.4 exists
  to be cited under this rule.

The per-stage round count is recorded in the remediation plan's Session Log at feature
close (REQ-TRIAL-03). **This stage (`forge-2-tech`) is round 0 at authoring.**
