# 01 — Architecture and Layout

> Where every change in this feature lands, who owns it, and in what order it must be made.
> No package is created, no module is added, no dependency is introduced. This document is
> the **file-ownership map and the sequencing contract** for the five workstreams defined
> in `00-core-definitions.md` §2.
>
> Locate every symbol by **name**, never by line number (C-07).

## Requirement Coverage

| REQ ID | Requirement | Section |
|---|---|---|
| REQ-GUARD-01, REQ-GUARD-03 | Canon files edited, and which | §2, §3.1 |
| REQ-TRIM-01..07 | Test files restructured, and which | §3.3 |
| REQ-FIX-01, REQ-SEC-01 | Production files edited, and which | §3.2 |
| REQ-COV-01..07 | Backfill placement across host files | §3.3, §4.2 |
| REQ-CANON-01 | Adapter regeneration in the same commit | §6 |
| REQ-CANON-02 | `check-spec-purity.py` reports 0 violations | §6.2 |
| REQ-QUAL-01..03 | Gate ordering these edits must satisfy | §7 |

## 1. No New Structure

This feature adds **no** directory, package, module, class, CLI verb, flag, exit code, or
JSON payload key.

**Public API surface: unchanged.** The two production validations (§3.2) narrow the
*accepted domain* of two existing flags; they change no success-path output. Every value
accepted before that is still accepted is stored byte-identically.

## 2. Directory Tree — files touched

```
references/
  stage-exit-protocol.md            EDIT (confirm-and-complete) — canon: capability rule
  shared-conventions.md             UNCHANGED — already defers to the above

skills/
  forge-0-epic/SKILL.md             EDIT — + one pointer sentence

scripts/
  forge-session.py                  EDIT — 2 validations, 1 signature widening

eval/
  run-compliance-eval.py            EDIT — + PRELUDE_CRITERIA key-set pin

tests/
  test_capability_determination_prose.py   REWRITE — 43 items → 4
  test_stage_exit_protocol.py              TRIM     — 67 mutation items → 7
  test_state_verb_call_sites.py            RESTRUCTURE — window → structural scan
  test_stage_constants_parity.py           TRIM     — source-text assertions
  test_state_verbs.py                      EDIT     — backfill + brittleness + dedup
  test_auto_verify.py                      EDIT     — backfill + root-uid guard
  test_stage_exit.py                       EDIT     — backfill + narrow ban + dedup
  test_state_schema_conformance.py         EDIT     — key-order → key-set
  test_compliance_eval.py                  EDIT     — + PRELUDE_CRITERIA assertion
  test_forge_root.py                       EDIT     — exact-stderr loosening
  _forge_paths.py                          UNCHANGED — shared canon-path layer
  conftest.py                              UNCHANGED — not used by any file in scope

adapters/{claude,codex,copilot,cursor,gemini,pi}/
                                    REGENERATED — never hand-edited (§6)
```

**Not touched, and deliberately so:** `tests/conftest.py` (its `run_cli` fixture is
hardcoded to `scripts/epic-manifest.py`), `scripts/epic-manifest.py`, every `eval/` fixture
(PRD §6 freezes the compliance eval beyond REQ-COV-03), and
`references/pipeline-state-schema.json`.

## 3. File Ownership

Each file below is owned by exactly one spec document. **Two documents never edit the same
file for the same reason**; where two documents both touch a file, §5 fixes the order.

### 3.1 Canon — `02-canon-and-prose-guard.md`

| File | Change | Requirement |
|---|---|---|
| `references/stage-exit-protocol.md` | Confirm § "Host and capability determination" states all six clauses; complete it if not | REQ-GUARD-01 |
| `skills/forge-0-epic/SKILL.md` | Add one pointer sentence before the `**Close this stage with the Scripted Stage Exit**` sentence in Step C8 | REQ-GUARD-03 |

**Body-size headroom — measured, not inferred.** `check-spec-purity.py::check_body_size`
enforces `MAX_BODY_LINES = 300` and `MAX_BODY_WORDS = 5000` against the **body**
(`text.split("\n")[fm.body_start_line:]`, i.e. everything after the closing frontmatter
fence) — **not** the file:

| Skill | File lines | Body lines | Body words | Headroom |
|---|---|---|---|---|
| `skills/forge-0-epic/SKILL.md` | 301 | **295** / 300 | 2749 / 5000 | **+5 lines** |
| `skills/forge-verify/SKILL.md` | 305 | **299** / 300 | 4365 / 5000 | **+1 line** |

Neither file is over the cap, which is why `check-spec-purity.py` reports 0 violations
today. A one-sentence pointer in `forge-0-epic` fits inside its 5 lines of headroom.
`forge-verify` has **one line** — no capability prose may be added there. That is what C-05
actually constrains.

> The pointer-not-paragraph decision does **not** rest on headroom. It rests on shape
> matching (`forge-5-loop` and `forge-6-docs` already use a pointer) and on R-10's goal of
> collapsing restatements rather than adding a seventh. See `02` §3.

### 3.2 Production — `04-production-validations.md`

The **only** document that changes shipped behavior.

| File | Symbol | Change | Requirement |
|---|---|---|---|
| `scripts/forge-session.py` | `cmd_state_complete` | Call `_require_positive_int(version, "--version")` before `_load_state_for_write` | REQ-FIX-01 |
| `scripts/forge-session.py` | `_validated_findings_file` | Add `label: str = "--findings-file"`; substitute `{label}` into all five messages | REQ-SEC-01 |
| `scripts/forge-session.py` | `cmd_state_artifact` | Validate every `--path` after the load, before any mutation | REQ-SEC-01 |
| `eval/run-compliance-eval.py` | module scope | Add `PRELUDE_CRITERIA: Final[tuple[str, ...]]` mirroring `BRANCH_CRITERIA` | REQ-COV-03 |

### 3.3 Tests — three documents, disjoint file sets where possible

| File | Owner | Also touched by |
|---|---|---|
| `test_capability_determination_prose.py` | `02` | — |
| `test_stage_exit_protocol.py` | `03` | — (but see §5, the export constraint) |
| `test_state_verb_call_sites.py` | `03` | — |
| `test_stage_constants_parity.py` | `03` | — |
| `test_compliance_eval.py` | `05` | — |
| `test_forge_root.py` | `06` | — |
| `test_state_verbs.py` | `05` (backfill) | `06` (brittleness + dedup) |
| `test_auto_verify.py` | `05` (backfill) | `06` (root-uid guard) |
| `test_stage_exit.py` | `05` (backfill) | `06` (narrowed ban + dedup) |
| `test_state_schema_conformance.py` | `06` | — |

The three shared files are the merge-risk surface. §5.3 fixes the order.

## 4. Placement Maps

### 4.1 Canon insertion point (REQ-GUARD-03)

`skills/forge-0-epic/SKILL.md`, Step C8 — **immediately before** the sentence beginning
`**Close this stage with the Scripted Stage Exit**`. This is the same structural position
every sibling surface uses, so the edit is positionally as well as textually
shape-matching.

### 4.2 Backfill placement (REQ-COV-01..07)

Each test lands **beside existing coverage of the same subject**, reusing that file's CLI
wrapper (`00` §10.5). This mapping is the audit trail for "each of the seven gaps has a
named test" — the backfill is not visible as a single file, so **this table is the
deliverable a verifier checks against**.

| Req | Behavior | File |
|---|---|---|
| REQ-COV-01 | corrupt state × autoVerify on/off | `tests/test_auto_verify.py` |
| REQ-COV-02 | `--version` domain | `tests/test_state_verbs.py` |
| REQ-COV-03 | prelude criterion key-set pin | `tests/test_compliance_eval.py` |
| REQ-COV-04 | debt-write idempotency (byte-level) | `tests/test_auto_verify.py` |
| REQ-COV-05 | commit-2 ignores conflicting flags | `tests/test_state_verbs.py` |
| REQ-COV-06 | `--path` containment | `tests/test_state_verbs.py` |
| REQ-COV-07 | unsafe epic back-pointer degradation | `tests/test_stage_exit.py` |

## 5. Dependency Graph and Build Sequence

### 5.1 Document dependencies

```
00-core-definitions.md   (shared vocabulary — no dependencies)
        │
01-architecture-layout.md (this file — depends on 00)
        │
        ├── 02-canon-and-prose-guard.md      depends on 00 §3, §4, §5
        ├── 03-machinery-trim.md             depends on 00 §4.2, §6
        ├── 04-production-validations.md     depends on 00 §7, §8
        ├── 05-coverage-backfill.md          depends on 00 §7, §10.5; 04 (for 02/06)
        └── 06-brittleness-batch.md          depends on 00 §8.3, §9
                │
        07-testing-strategy.md   depends on ALL of the above
```

`05` and `04` are the one **cross-document requirement pair**: REQ-COV-02 tests REQ-FIX-01,
and REQ-COV-06 tests REQ-SEC-01. The validation must exist before its test passes.

### 5.2 Implementation order

Ordered by dependency, not by document number:

1. **Canon first** (`02` §2–§3). `references/stage-exit-protocol.md` confirm-and-complete,
   then the `forge-0-epic` pointer. Regenerate adapters (§6).
2. **Production validations** (`04`). Independent of every test change; landing them first
   means the REQ-COV-02 and REQ-COV-06 tests are written against real behavior rather than
   intended behavior.
3. **Prose guard rewrite** (`02` §4–§6). Depends on step 1 — the guard asserts the canon
   that step 1 produces.
4. **Machinery trim** (`03`). Independent of steps 1–3 **except** for the export
   constraint in §5.3.
5. **Coverage backfill** (`05`). Depends on step 2.
6. **Brittleness batch** (`06`). Last among the edits — it touches three files that steps
   4–5 also touch, and loosening an assertion is easiest to verify against a settled file.
7. **Gates** (`07` §3). Run the full ordered gate list.

### 5.3 The export constraint — the single most likely breakage

`tests/test_capability_determination_prose.py` imports `CANONICAL_EXIT_SITES` from
`tests/test_stage_exit_protocol.py` (`00` §10.4).

- Step 3 (`02`) derives its 9-surface roster from that tuple.
- Step 4 (`03`) collapses 67 mutation controls **in the file that exports it**.

These are different requirements (REQ-GUARD-04 and REQ-TRIM-01) that do not reference each
other, which is exactly how this kind of break ships.

**Hard constraints:**

- `CANONICAL_EXIT_SITES` MUST keep its name, its module scope, and its **9-entry** tuple.
- `CanonicalExitSite` MUST keep its `skill` and `contract_paths` fields.
- `_SITE_IDS` and `_BRANCH_SITES` may be trimmed in use but not deleted while any surviving
  `parametrize` reads them.
- After steps 3 **and** 4, `from test_stage_exit_protocol import CANONICAL_EXIT_SITES` must
  still resolve and still yield 9 entries. `07` §4 makes this an explicit gate.

### 5.4 Files with two owners — merge order

| File | First | Then |
|---|---|---|
| `test_state_verbs.py` | `05` backfill (adds tests) | `06` brittleness + dedup (rewrites existing) |
| `test_auto_verify.py` | `05` backfill (adds tests) | `06` root-uid guard (one decorator) |
| `test_stage_exit.py` | `05` backfill (adds tests) | `06` narrowed ban + gate dedup (rewrites existing) |

Adding before rewriting means the dedup pass in `06` sees the final set of functions and
cannot leave a newly added test outside a family it belongs to.

## 6. Canon and Adapter Obligations (REQ-CANON-01, REQ-CANON-02)

### 6.1 Adapter regeneration

**Every** edit to `skills/` or `references/` requires:

```bash
python3 scripts/build-adapters.py
```

and committing **all six mirrors in the same commit**. `build-adapters.py --check` exiting
0 is a hard gate inside `scripts/validate.sh`.

Propagation is mechanical:

- `references/**` is copied **verbatim** into each bundle, so the §3.1
  `stage-exit-protocol.md` edit propagates without transformation.
- The `forge-0-epic` skill edit propagates through the per-skill emitters, with host-term
  translation for the non-Claude targets.

The six mirrors: `adapters/claude`, `adapters/codex`, `adapters/copilot`,
`adapters/cursor`, `adapters/gemini`, `adapters/pi`. **Never hand-edited** (C-01).

> **C-02 caveat.** After any `git checkout`, `merge`, or `pull`, adapter file modes can
> land as 0664 from the ambient umask and fail the mode test. Re-running
> `build-adapters.py` restores 0644; content is unaffected. **Do not investigate this as a
> content defect.**

### 6.2 Spec purity

`python3 scripts/check-spec-purity.py` must report **0 violations** after every canon
change. Its seven rules include the body-size cap (§3.1, measured), prelude byte-identity,
and a **self-containment ratchet** that bans new spec-document citations in `scripts/`,
`references/`, `skills/`, and `eval/`.

> This spec suite lives in `specs/`, which is **not a shipped surface**, so its own
> citations are unaffected — **but any prose added to canon must not cite this document.**
> The `forge-0-epic` pointer names `references/stage-exit-protocol.md` and nothing in
> `specs/`.

## 7. Verification Gates

The ordered gate list `07-testing-strategy.md` §3 owns. Reproduced here because §5.2's
sequencing refers to it:

1. `python3 -m pytest tests -q` — must stay green.
2. `python3 scripts/build-adapters.py` then `--check` exits 0 (REQ-CANON-01).
3. `python3 scripts/check-spec-purity.py` — 0 violations (REQ-CANON-02).
4. `ruff check scripts/ eval/` — clean.
5. `ruff check tests/` — **≤19 errors** (REQ-QUAL-02).
6. `bash scripts/validate.sh` — "All checks passed!" (REQ-QUAL-03).

`validate.sh` runs the full pytest suite as one step and both canon gates as hard gates, so
**step 6 subsumes 1–5**; the earlier steps exist for fast local feedback.

## 8. Dependencies

**Spec documents that must be read first:** `00-core-definitions.md`.

**External packages:** none added, none removed. See `00` §11 for the two removed *imports*
(`ast` from the prose guard, `inspect` from the call-sites guard).

**In-progress feature conflicts:** sibling specs exist under `specs/` (`agent-agnostic`,
`context-efficiency`, `context-management`, `epic-orchestration`, `forge-bootstrap`,
`stage-exit-coverage`). `stage-exit-coverage` is this feature's direct antecedent and owns
the exit-coverage contract that `03` trims controls for; **its artifacts are complete**, so
no concurrent write conflict exists. No other in-progress feature touches `tests/` or the
capability surfaces.

## 9. Verification

- [ ] Every file in §2 marked EDIT/REWRITE/TRIM/RESTRUCTURE appears in the diff; every file
      marked UNCHANGED does not.
- [ ] `adapters/` changes appear in the **same commit** as every `skills/` or `references/`
      change; `build-adapters.py --check` exits 0.
- [ ] No file under `adapters/` was hand-edited (its diff is reproducible by re-running
      `build-adapters.py`).
- [ ] `check-spec-purity.py` reports 0 violations, and no canon prose cites any document in
      `specs/`.
- [ ] `from test_stage_exit_protocol import CANONICAL_EXIT_SITES` resolves after all edits
      and yields **9** entries.
- [ ] The seven REQ-COV tests exist in the seven host files named in §4.2, each reusing that
      file's own CLI wrapper.
- [ ] `tests/conftest.py`, `scripts/epic-manifest.py`, and every `eval/` fixture are absent
      from the diff.
- [ ] No new directory, module, class, CLI verb, flag, exit code, or payload key appears in
      the diff.
