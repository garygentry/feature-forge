# Verification Report: stage-exit-coverage (impl, round 7)

Date: 2026-08-01
Pipeline Stage: forge-5-loop (complete, v1)
Mode: impl — served production stage `forge-5-loop`
Method: clean-room re-verification in require-clean mode against the round-6 fix pass (commits `cef9eb0` + `8d111d3`; base `8709348`). Every numeric and factual claim the fix pass wrote into a comment, docstring or spec was re-derived with an instrument different from the one the fix pass used. Nothing in the repository was modified.

Artifacts Reviewed:
- `/home/gary/workspace/feature-forge/specs/stage-exit-coverage/.verification/VERIFY-impl-2026-08-01-round6.md` (Findings, Fix Execution Plan, Decision 1, Fix Progress)
- `git diff 8709348..HEAD` (12 files, +249/−69: 6 adapter mirrors, 6 non-adapter)
- `/home/gary/workspace/feature-forge/tests/test_capability_determination_prose.py`, `/home/gary/workspace/feature-forge/tests/test_state_verb_call_sites.py`
- `/home/gary/workspace/feature-forge/scripts/forge-session.py`, `/home/gary/workspace/feature-forge/scripts/epic-manifest.py`
- `/home/gary/workspace/feature-forge/specs/stage-exit-coverage/{01-architecture-layout.md, 07-testing-strategy.md, backlog.json, .pipeline-state.json}`
- all six `adapters/*/scripts/forge-session.py` mirrors; `/home/gary/workspace/feature-forge/forge.config.json`
- `skills/forge-{1-prd,2-tech,3-specs,4-backlog,verify,fix}/SKILL.md` at HEAD **and at `21f1c34`**

Checks Executed: 23 of 23 (17 pass, 3 fail, 3 not-applicable)

## Summary

- **Total findings: 5** — 1 error, 1 inconsistency, 3 improvements, 0 gaps.
- **Four of round 6's six findings are RESOLVED; two are PARTIAL** (V-002 and V-004). Every verdict was re-derived independently; none is taken from the Fix Progress record.
- **The standing failure mode recurred, in the fix's own new code.** The three helpers added for V-004 carry docstrings making **completeness** claims — `_module_scope_nodes` says its traversal is "**exactly** the set of statements that can replace a module global", `_module_scope_writes` says it finds every write "**in any form**". I disproved both with six probes that displace the roster and leave the suite at **43 passed**. All 1809 tests are green; nothing in the suite can see this.
- **The four probes round-6 V-004 named are genuinely closed**, at exactly the lines the Fix Progress recorded, re-derived with my own harness: N1→`:591`, N2→`:566`, N3→`:566`, N4→`:587`. The six pre-existing probes still red at `:574`/`:574`/`:574`/`:570`/`:566`/`:591`. The `>= MIN_CAPABILITY_SURFACES` floor at `:526` was **never** the source of a red in any of the 16 probes. Displacement was proven for every probe by observing the reversed roster in `SURFACE_IDS`, and the scratch root was proven live by an effectiveness control (mutating `probe/skills/forge-verify/SKILL.md` reds 5 tests).
- **V-001 is fully closed.** Every claim in the rebuilt sentence reproduces, including its history at `21f1c34`, and it does not contradict control 3a-ii. But 3a-ii — the sibling it was written to match — still accounts for only **5 of the 6** surfaces while asserting "all six": the residue of the same defect, in the docstring round 6 used as the reference. → V-004.
- **V-002's two prescribed edits landed and are correct**, but the **`fresh` bullet three lines above them** now contradicts them: it still says `fresh` means "verify is **resolved** AND … matches", and `findings-applied` is in `_VERIFY_RESOLVED`. Sibling `epic_verify_state` says `passed`, precisely. The round-6 acceptance criterion ("neither states a rule the other contradicts") is therefore not met. → V-003.
- **V-003 and V-005 are cleanly closed**, both re-derived from scratch.
- **Mechanical sweeps over all 249 added lines are clean** — 0 TODO/FIXME/XXX/HACK/TBD, 0 column-0 punctuation in added `.py` lines, 0 genuine merged words (all camelCase hits are JSON keys or substrings of `ClassDef`/`AsyncFunctionDef`/`FunctionDef`/`verifiedStageVersion`), 0 de-indented docstring continuations across all three changed Python files.
- **The gate is confirmed, not taken on report**, on a healthy disk (2.3 GB free before, 1.9 GB after): `validate.sh` exit 0 `All checks passed!`, **1809 passed / 2 skipped**, 1811 collected, 0 fixture bytecode, ruff/spec-purity clean, `--check` exit 0, tree clean.
- **Pipeline state is exactly as specified**, including the cleared `verifiedStageVersion`.

---

## Measurements

### 1. Gate (re-run independently)

| Check | Expected | Measured | Result |
|---|---|---|---|
| `df -h /` before gating | ≥ 1 GB | **2.3 GB** free (1.9 GB after) | OK |
| `bash scripts/validate.sh` | exit 0, `All checks passed!` | exit **0**, `All checks passed!` | CONFIRMED |
| Full suite | 1809 passed / 2 skipped | **1809 passed, 2 skipped** in 235.24s | CONFIRMED |
| Collected node count | 1811 | **1811 collected** | CONFIRMED |
| `find tests/fixtures -name '__pycache__' -o -name '*.pyc' \| wc -l` | 0 | **0** (after validate, and again after the full suite) | CONFIRMED |
| `ruff check scripts/ eval/` | clean | exit **0**, `All checks passed!` | CONFIRMED |
| `ruff check tests/` | 19 | **Found 19 errors** | CONFIRMED (unchanged) |
| `ruff check tests/ --select F841,F541` | clean | exit **0** | CONFIRMED |
| `python3 scripts/check-spec-purity.py` | PASS, 0 violations | `spec-purity: PASS — 0 violations across canonical surfaces.` | CONFIRMED |
| `python3 scripts/build-adapters.py --check` | exit 0 | exit **0** | CONFIRMED |
| `git status --porcelain` | empty | **empty** | CONFIRMED (require-clean satisfied) |

### 2. Adapter mirrors (CHECK-I09/I10)

sha-equality of each `adapters/*/scripts/forge-session.py` against canon:

| Adapter | Result |
|---|---|
| claude, codex, copilot, cursor, gemini | **byte-identical to canon** (5/6) |
| pi | differs on **72** +/− lines; `canon.replace("/feature-forge:", "/skill:")` reproduces it **byte-for-byte** (`t == deg` → `True`), zero residual lines |

The six mirrors differ from canon **only** where the documented per-adapter degradation requires.

### 3. Pipeline state — CONFIRMED

| Property | Expected | Measured |
|---|---|---|
| `stages.forge-verify-impl.status` | `findings-applied` | `findings-applied` ✓ |
| `.findingsFile` | round-6 report | `.verification/VERIFY-impl-2026-08-01-round6.md` ✓ |
| `.findingsCount` | 6 | `6` ✓ |
| `.verifiedStageVersion` | **CLEARED** | **absent** ✓ |
| `.verifiedAt` | absent | absent ✓ (replaced by `fixedAt: 2026-08-01T19:53:30Z`) |
| `.commitHash` | full 40-hex of `cef9eb0` (artifact, not provenance) | `cef9eb0501de3951036d8fe4bf70ea9f7f70806a`, length **40**; `git cat-file -t` → `commit`; `git show --oneline` → *"apply impl verification fixes (round 6)"* — the **artifact** commit ✓ |
| Entry key set | exactly 5 keys | `commitHash, findingsCount, findingsFile, fixedAt, status` ✓ |
| Other stage entries | undisturbed | `forge-5-loop` unchanged (`complete`, v1) ✓ |
| `notes` | unchanged | byte-identical to `8709348` ✓ |

### 4. Roster-derivation guard — my own probe battery (V-004)

Harness: **real file copies** of `tests/`, `scripts/`, `skills/`, `references/` into a scratch root (no symlinks — `tests/_forge_paths.py` resolves `REPO_ROOT` through a symlink back to the real repo); `PYTHONDONTWRITEBYTECODE=1`; `-p no:cacheprovider`; `__pycache__` purged between every probe; one fresh copy of the target per probe; hand-kept roster is a **static reversed snapshot** taken before any alias (avoids the recursion the fix pass recorded). Line numbers are de-shifted by the insert width.

**Effectiveness control on the scratch root itself** (this is the control the round-6 hazard note demands): rewriting `probe/skills/forge-verify/SKILL.md`'s `dispatched on the affirmative` → `PRINTED for the user` gives **5 failed, 38 passed**; restoring gives **43 passed**. The scratch canon is genuinely what is read.

**Displacement control:** every probe's hand-kept roster is the six surfaces in **reversed** order, and `SURFACE_IDS` was collected from pytest for each probe. All sixteen probes showed the reversed order (`skills/forge-fix/SKILL.md` first, or sorted order for the `sorted()` probe), so **no probe is a no-op the guard merely appeared to catch**.

Assertion line map at HEAD: `:526` floor · `:566` binding/mutation count · `:570` `AnnAssign` shape · `:574` derivation `Call` · `:587` definition count · `:591` alias writes.

| Probe | Result | De-shifted red line | Fix Progress claimed |
|---|---|---|---|
| C0 unmutated control | **43 passed** | — | 43 passed ✓ |
| P1 hand-kept `ast.List` (roster-preserving) | RED | `:574` derivation `Call` | `:574` ✓ |
| P2 differently-named hand-kept function | RED | `:574` | `:574` ✓ |
| P3 `sorted(_capability_surfaces())` | RED | `:574` | `:574` ✓ |
| P4 `AnnAssign` demoted to `Assign`, still derived | RED | `:570` `AnnAssign` | `:570` ✓ |
| P5 decoy kept + `ALL_SURFACES` re-bound | RED | `:566` count | `:566` ✓ |
| P6 plain alias `_capability_surfaces = _hand_kept` | RED | `:591` alias | `:591` ✓ |
| **N1** annotated alias `_capability_surfaces: Final = _hand_kept` | **RED** | `:591` alias | `:591` ✓ |
| **N2** nested-`if` re-bind of `ALL_SURFACES` | **RED** | `:566` count | `:566` ✓ |
| **N3** in-place `ALL_SURFACES[:] = …` | **RED** | `:566` count | `:566` ✓ |
| **N4** shadowing second `def _capability_surfaces` | **RED** | `:587` definition count | `:587` ✓ |

**The floor at `:526` was never the source of a red in any of the sixteen probes.** Every red was exactly one failure, in `test_the_controls_cover_every_determining_surface`.

**Six NEW blind spots — all GREEN, all with the roster proven displaced:**

| Probe | Binding form | Result | Roster actually used |
|---|---|---|---|
| **X1** | `(ALL_SURFACES := _hand_kept_surfaces)` — walrus at module scope | **GREEN — 43 passed** | hand-kept (reversed) |
| **X2** | `for ALL_SURFACES in [_hand_kept_surfaces]:` — module-level `for` target | **GREEN — 43 passed** | hand-kept |
| **X3** | `def _install_roster(): global ALL_SURFACES; ALL_SURFACES = …` + call | **GREEN — 43 passed** | hand-kept |
| **X4** | `with contextlib.nullcontext(…) as ALL_SURFACES:` | **GREEN — 43 passed** | hand-kept |
| **X5** | `for _capability_surfaces in [_hand_kept]:` — alias via `for` target | **GREEN — 43 passed** | hand-kept |
| **X6** | `(_capability_surfaces := _hand_kept)` — alias via walrus | **GREEN — 43 passed** | hand-kept |

X1/X2/X4/X5/X6 are missed because `_module_scope_writes` handles only `ast.Assign` / `ast.AnnAssign` / `ast.AugAssign` and never `ast.NamedExpr`, `For.target`, `withitem.optional_vars`, comprehension targets, `import … as`, or `except … as`. **X3 is the sharpest**: it defeats `_module_scope_nodes`'s scope-stopping rule, whose docstring justifies that rule with the claim that a function-body binding "rebinds nothing this module reads and would be a false positive" — false in the presence of a `global` declaration.

*(`_store_target_names` is, by contrast, genuinely complete: `Name`/`Attribute`/`Subscript`/`Starred`/`Tuple`/`List` is the entire assignment-target grammar. `bindings[0]` reading a stack-pop order rather than source order is harmless because `len(bindings) == 1` is asserted first.)*

### 5. Module-docstring claims (V-001) — every claim RE-DERIVED AND TRUE

Measured in-process against the live roster, and against `git show 21f1c34:` for the history.

**A. Per-surface c1a fragment at HEAD** — the sentence names the right one for each group:

| Surface | c1a fragment actually matching its capability paragraph |
|---|---|
| `skills/forge-1-prd`, `-2-tech`, `-3-specs`, `-4-backlog` | `reuse the Standard Verify Gate block for consent` |
| `skills/forge-verify` | `presented through the gate` |
| `skills/forge-fix` | `presented through the Step 6 gate` |

**B.** `presented through the gate` occurs in **exactly 1 of 6** capability paragraphs (`forge-verify`, count 1; all five others 0). The amended sentence attributes it to `forge-verify` only. ✓

**C. Merged-list reconstruction:** rebuilding one any-of list from `CLAUSES["c1a"] + CLAUSES["c1b"]` and deleting every c1b phrasing leaves **all six GREEN**, each on its own gate fragment (`forge-1-prd`…`forge-4-backlog` on the gate-block fragment, `forge-verify` on `presented through the gate`, `forge-fix` on `presented through the Step 6 gate`) — exactly the three-way account the sentence now gives. ✓

**D. History at `21f1c34`** (the commit at which c1a and c1b still shared a list): the four authoring stages carry **0** occurrences of `dispatched on the affirmative` in their capability paragraphs, and `presented through the gate` is absent from all four whole files; `forge-verify` carries both `presented through the gate` and `dispatched on the affirmative`; `forge-fix` carries `presented through the Step 6 gate` and `dispatched on the affirmative`. The sentence's history is exact. *(Nuance, deliberately not filed: those four paragraphs do contain the words "…authorizes the dispatch", but that sentence states clause (b) — why a consent-gated session is `interactive` — not the c1b dispatch obligation. "No dispatch phrasing at all" is correct as a claim about the dispatch clause, which is the clause the sentence is about, and it is verbatim the wording round 6 prescribed.)*

**E. End-to-end prose read against control 3a-ii (`:412-421`).** Neither states anything the other contradicts: 3a-ii attributes the surviving match to `presented through the gate` on `forge-verify` and adds "the authoring stages carried no dispatch phrasing at all"; the module docstring says the same and additionally supplies `forge-fix`'s half. **The asymmetry runs the other way now** — 3a-ii accounts for 5 of 6 surfaces while asserting "undetected on all six". → **V-004**.

**F. The untouched first half of the same sentence also re-derives.** Merging c2+c3 into one list and inverting `never grounds to skip verification` → `IS grounds to skip verification entirely`: the mutation **bites on exactly 4 surfaces** (the authoring stages) and the merged c2/c3 clause **still matched on all 4**, via `never grounds to fence the production successor`. The parenthetical "(four surfaces)" is exact. *(It is not in tension with control 3b's "five of the six surfaces", which measures whole-guard green in the earlier `"choice 2 omitted"` era, a different experiment.)*

### 6. Read-side classifiers (V-002) — 24 shapes × 4 classifiers, 0 disagreements

Exhaustive matrix over `status` ∈ {`passed`, `findings-reported`, `findings-applied`, `skipped`, `auto-verify-pending`, `pending`, `None`, `findings-resolved`} × `verifiedStageVersion` ∈ {absent, 1 (matching), 2 (non-matching)}.

- `verify_state` vs `_classify_verify_entry` vs `_verify_state_for` vs `epic_verify_state` (revision 1): **0 disagreements across all 24 shapes.**
- `findings-applied` → `stale` at absent / matching / non-matching alike, in all four.
- Direct counterexample against the docstring: `{"status": "findings-applied", "verifiedStageVersion": 1}` with stage `version: 1` → `('forge-1-prd', 'stale')`. `passed` + matching → `fresh`. `skipped` + matching → `skipped`.

Behaviour is correct and the two prescribed edits are accurate. The `fresh` bullet is not. → **V-003**.

### 7. Flattening-window arithmetic (V-005) — CONFIRMED

`_state_verify_call_text`'s amended docstring (`:291-292`): *"Joining `CALL_SPAN` lines starting at the verb's line (so the verb plus up to `CALL_SPAN - 1` continuations)"*. Consumer at **`:302`**: `" ".join(lines[index : index + CALL_SPAN])` — slice width `CALL_SPAN`, starting at the verb line. `CALL_SPAN = 3` (`:89`). The stated count **equals** the slice width. Read end-to-end against the `CALL_SPAN` comment block (`:61-89`): both describe the same **3-line** window, both state the same six four-line sites and the same offset-0-or-1 basis. No number appears twice with two values anywhere in the module.

### 8. `01-architecture-layout.md` §2 (V-003) — COMPLETE

`git diff --name-status e89d8fa~1..HEAD -- . ':(exclude)adapters/' ':(exclude)specs/'` yields **49 paths**. Every one is now accounted for:

- 46 listed explicitly in §2 (including the two new fixture paths at `:121-122`)
- 1 covered by the `<existing epic manifest tests>` placeholder row (`tests/test_epic_manifest.py`)
- 2 attributable to `b3110b1` — `git log e89d8fa~1..HEAD -- .gitignore` and `-- forge.config.json` each return **only** `b3110b1 fix(tests): isolate rank-features from the project's own forge.config.json`

The new row's marker sits at **column 44**, matching every other row in the `tests/` block (measured programmatically across `:99-124`), and the two-line continuation form matches the block's existing style (`:112-114`, `:115-116`, `:117-118`).

### 9. Backlog, docs, config

- `backlog.json`: **32 items, `001`..`032`, `Counter({'done': 32})`**, every item carrying a `completedAt`. No `pending`/`in-progress`.
- `README.md` present and listed in §2; `docs/architecture/` holds three feature dirs; `stage-exit-coverage` absent because `forge-6-docs` has not run — correct for impl-verify.
- `forge.config.json`: `smokeCommand: null`, `typeCheckCommand: "ruff check scripts/ eval/"`, `testCommand: "bash scripts/validate.sh"`.
- `07-testing-strategy.md` §6.2's description of `test_capability_determination_prose.py` (clauses a/b/c split into c1a/c1b/c2/c3, derived roster, per-surface negative controls, structural `ast` guard on the derivation) remains **accurate** after the rewrite.

### 10. Mechanical-damage sweep — CLEAN

Over all **249 added lines** (139 of them `.py`) across the 12-file diff:

- **0** TODO/FIXME/XXX/HACK/TBD markers
- **0** column-0 punctuation characters in added `.py` lines
- **0** genuine merged words — the seven camelCase candidates are JSON keys (`commitHash`, `findingsCount`, `findingsFile`) or substrings of `ClassDef`/`AsyncFunctionDef`/`FunctionDef`/`verifiedStageVersion` (`lassDef`, `syncFunction`, `unctionDef`, `verifiedStage`)
- **0** de-indented docstring continuations (`tokenize` pass over every STRING/COMMENT token in all three changed Python files)
- Exactly one import line added anywhere in the diff (`from collections.abc import Iterator`), correctly placed and used

---

## Findings

### V-001: The three new helper docstrings claim COMPLETENESS the helpers do not have — "exactly the set of statements that can replace a module global" and "in any form" are both false, and I disproved each with a probe that leaves the suite at 43 passed

- **Severity:** error
- **Location:** `/home/gary/workspace/feature-forge/tests/test_capability_determination_prose.py:472-479` (`_module_scope_nodes` docstring) and `:508` (`_module_scope_writes` docstring); supporting narrative at `:552-563` (the comment block)
- **Issue:** Decision 1(a) was applied and the four probes it was chosen to close are genuinely closed (§4 above). But the prose written to justify the generalisation states two completeness properties the code does not have, and a third that is inexact:

  1. **`_module_scope_nodes:472-479`** — *"`ast.walk` alone would also descend into function and class bodies, where a local of the same name rebinds nothing this module reads and would be a false positive. Descending through control flow but stopping at every new scope is **exactly the set of statements that can replace a module global**."*

     Both sentences are false. A statement in a function body **can** replace a module global — that is what `global` is for. Probe **X3**:

     ```python
     def _install_roster():
         global ALL_SURFACES
         ALL_SURFACES = _hand_kept_surfaces
     _install_roster()
     ```

     genuinely displaces the roster (`SURFACE_IDS` observed in the reversed hand-kept order) and the module stays **GREEN — 43 passed**. The docstring's stated rationale for the scope stop is the very thing that lets X3 through.

  2. **`_module_scope_writes:508`** — *"Every module-scope statement that binds or mutates `name`, **in any form**."* It handles `ast.Assign`, `ast.AnnAssign`, `ast.AugAssign` and nothing else. Probes **X1** (`(ALL_SURFACES := _hand_kept_surfaces)`, an `ast.NamedExpr`), **X2** (`for ALL_SURFACES in […]`, a `For.target`) and **X4** (`with … as ALL_SURFACES`, a `withitem.optional_vars`) each bind the module global, each displace the roster, and each leave the module **GREEN — 43 passed**. Also unhandled: comprehension targets, `import … as`, `except … as`, `del`.

  3. Minor, same docstring: *"stopping at **every** new scope"* — `Lambda` and the four comprehension forms are also new scopes and are descended into. No false positive is reachable through them (they admit no `Assign`), so this is wording only.

  The comment block at `:552-563` is, by contrast, **accurate**: it enumerates exactly the forms the code handles (`Assign`, `AnnAssign`, `AugAssign`, plus stores reached through subscript/attribute/star/tuple) without claiming that enumeration is exhaustive. The defect is confined to the two helper docstrings.

  This is the sixth consecutive round in which a mechanically-correct change shipped wrapped in a claim the code does not support, and all **1809** tests were green for it.
- **Suggested fix:** Two docstring edits in `tests/test_capability_determination_prose.py`. Prose only — no assertion change here (the coverage question is V-002, and the wording must be chosen to match whatever V-002's decision is).
  1. `_module_scope_nodes` (`:477-479`): replace *"Descending through control flow but stopping at every new scope is exactly the set of statements that can replace a module global."* with a bounded claim and the named exception, e.g.:

     > `Descending through control flow but stopping at function and class bodies covers every module-level BINDING STATEMENT. It is deliberately not exhaustive: an assignment inside a function that declares` `global ALL_SURFACES` `also replaces the global and is out of this traversal's reach — see the comment in` `test_the_controls_cover_every_determining_surface` `for what that leaves open.`

     Delete or qualify the "rebinds nothing this module reads" clause, which is the false premise.
  2. `_module_scope_writes` (`:508`): change *"in any form"* to name the forms, e.g. `"as an ``Assign``, ``AnnAssign`` or ``AugAssign`` — including stores reached through a subscript, attribute, star or tuple."`
  3. If V-002 is resolved as "record and stop", add one sentence to the `:552-563` comment naming the unhandled forms (`NamedExpr`, `For` target, `with … as`, comprehension target, `import … as`, `except … as`) so the hole is recorded rather than silent.

  **Acceptance evidence (mandatory, and *not* suite-green):** (i) re-run probe X3 and confirm the amended `_module_scope_nodes` docstring does not claim to cover it; (ii) re-run X1/X2/X4 and confirm the amended `_module_scope_writes` docstring does not claim to cover them; (iii) read both amended docstrings **end-to-end as prose against the helper bodies**, line by line, and confirm no sentence asserts a property the body does not have; (iv) confirm the `:552-563` comment and the two docstrings now agree on what is and is not covered.
- **References:** `tests/test_capability_determination_prose.py:481-486` (the `FunctionDef`/`ClassDef` stop), `:498-511` (`_module_scope_writes`'s form list), `:513-522` (`_store_target_names`, which **is** complete for the assignment-target grammar); round-6 V-004 Decision 1(a) and its Fix Progress Step 3
- **Checklist:** CHECK-I19, CHECK-I17

### V-002: The generalised roster guard closes the four shapes it was shown and opens six more — six binding forms displace the roster with the module at 43 passed

- **Severity:** improvement
- **Location:** `tests/test_capability_determination_prose.py:498-522` (`_module_scope_writes`, `_store_target_names`), `:472-489` (`_module_scope_nodes`), consumed at `:565`, `:581-586`, `:591`
- **Issue:** Decision 1(a) succeeded on its own terms — N1/N2/N3/N4 all red at their own assertions' lines, P1–P6 unchanged, the floor never fires, and every probe genuinely displaces the roster (§4). But the generalisation is over three node **classes**, not over the language's binding forms, so six further spellings of the same idea remain green:

  | Probe | Mutation | Missed because |
  |---|---|---|
  | X1 | `(ALL_SURFACES := _hand_kept_surfaces)` | `ast.NamedExpr` not in `_module_scope_writes`' node list |
  | X2 | `for ALL_SURFACES in [_hand_kept_surfaces]:` | `ast.For.target` not inspected |
  | X3 | `global ALL_SURFACES` + assignment inside a called function | `_module_scope_nodes` stops at `FunctionDef` unconditionally |
  | X4 | `with contextlib.nullcontext(…) as ALL_SURFACES:` | `withitem.optional_vars` not inspected |
  | X5 | `for _capability_surfaces in [_hand_kept]:` | same as X2, on the derivation name |
  | X6 | `(_capability_surfaces := _hand_kept)` | same as X1, on the derivation name |

  All six: **43 passed**, roster observed in the reversed hand-kept order. Also unhandled but not probed: comprehension targets, `import … as`, `except … as`, `del`.

  As in round 6 this is `improvement`, not `gap`: every path requires deliberately leaving a decoy behind, there is no live drift, and the suite is green. But this assertion has now been rewritten in **five** consecutive rounds and each rewrite closed exactly the shapes the previous round demonstrated. The evidence that instance-by-instance patching does not terminate is now five rounds deep, and the *generalised* form failed on its first contact with a new spelling.
- **Suggested fix:** Three options — this needs a policy call (see Decision 1 below), not a silent choice.
  - **(a) Close the form class properly.** Replace `_module_scope_writes`' `isinstance` chain with a single pass that collects every `ast.Store`-context `ast.Name` plus `ast.NamedExpr.target`:

    ```python
    def _module_scope_writes(tree: ast.Module, name: str) -> list[ast.AST]:
        """Every module-scope node that binds or mutates `name`, in any binding form."""
        writes: list[ast.AST] = []
        for node in _module_scope_nodes(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                if node.id == name:
                    writes.append(node)
            elif isinstance(node, ast.NamedExpr) and node.target.id == name:
                writes.append(node)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if any((a.asname or a.name.split(".")[0]) == name for a in node.names):
                    writes.append(node)
        return writes
    ```

    A `Store`-context `Name` is the single common denominator of `Assign`, `AnnAssign`, `AugAssign`, `For`, `with … as`, comprehension targets, `except … as` and starred/tuple/subscript/attribute targets, so `_store_target_names` becomes unnecessary. Note the consumers change shape: `bindings[0]` is then an `ast.Name`, so the `AnnAssign`/derivation-`Call` assertions at `:570` and `:574` must reach the binding through `ast.parse`'s parent chain or be re-expressed as a separate "the one `AnnAssign` binding of `ALL_SURFACES` is a call to `_capability_surfaces`" assertion. **This is the expensive option and it changes three assertions.**
  - **(b) Close only the plausible forms.** Add `ast.NamedExpr`, `ast.For`/`ast.AsyncFor` targets and `withitem.optional_vars` to `_module_scope_writes`; leave `global` alone. Cheap; closes X1/X2/X4/X5/X6; leaves X3 open.
  - **(c) Record and stop** — keep the assertions exactly as they are, and add the unhandled-forms sentence from V-001's fix (3) plus a `global`-specific note, converting a silent hole into a recorded decision. This is the device the module already uses for `SURFACES_WITHOUT_PROSE`.

  **Acceptance evidence (mandatory, `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`, `__pycache__` purged, one fresh REAL-FILE copy of `tests/`+`scripts/`+`skills/`+`references/` per probe, reversed-order hand-kept roster, plus a scratch-root effectiveness control):** under (a) all six X probes go RED at the new assertion's own de-shifted line; under (b) X1/X2/X4/X5/X6 go RED and X3 is **re-recorded as still-GREEN in the fix record**; under (c) nothing changes and all six are re-recorded as GREEN-by-decision. In every case P1–P6 and N1–N4 must stay red at `:574`/`:574`/`:574`/`:570`/`:566`/`:591`/`:591`/`:566`/`:566`/`:587` (de-shifted), the floor at `:526` must never be the source of a red, and the unmutated copy must be **43 passed**. Prove displacement for every probe by observing `SURFACE_IDS` in reversed order.
- **References:** `tests/test_capability_determination_prose.py:345` (the guarded assignment), `:346` (`SURFACE_IDS`, which takes the shadowed value), `:526` (the floor), `:552-563` (the comment claiming the shape class is enumerated); round-6 V-004, round-5 V-007, round-4 V-001, round-3 V-007, round-3 V-002
- **Checklist:** CHECK-I17

### V-003: `verify_state`'s `fresh` bullet still defines freshness as "resolved AND matching" — three lines above the `stale` bullet this same fix pass amended to say otherwise

- **Severity:** inconsistency
- **Location:** `/home/gary/workspace/feature-forge/scripts/forge-session.py:880-881` (`fresh` bullet), against `:882-886` (the amended `stale` bullet) and `:905-909` (the amended closing paragraph)
- **Issue:** Round-6 V-002's two prescribed edits landed and are both **correct** — I read them and re-derived the rule they state:

  > `- ``stale``   — … OR the entry is ``findings-applied``, which never classifies ``fresh`` regardless of any version it carries (§4.2 step 4).`
  > `… A ``findings-applied`` entry is treated as ``stale`` UNCONDITIONALLY — applying fixes is not verifying them — …`

  But the **`fresh` bullet three lines above** was not swept and still reads:

  > `- ``fresh``   — verify is resolved AND its ``verifiedStageVersion`` matches the stage's current ``version`` (so no re-verify is needed).`

  `_VERIFY_RESOLVED` (`:263`) is `frozenset({"passed", "findings-applied", "skipped"})`. So a `findings-applied` entry carrying a matching version satisfies the `fresh` bullet's stated condition exactly — and returns `stale`. Measured directly: `verify_state({... "forge-verify-prd": {"status": "findings-applied", "verifiedStageVersion": 1}})` with `forge-1-prd` at `version: 1` → `('forge-1-prd', 'stale')`. The same bullet is also wrong for `skipped` + matching version → `skipped`.

  The sibling this docstring was told to match gets it right by naming the status rather than the category — `epic-manifest.py:1066-1067`: *"``fresh`` — ``passed`` whose ``verifiedStageVersion`` equals the current manifest revision."* So **round-6 V-002's own acceptance criterion — "read the two docstrings side by side and confirm neither states a rule the other contradicts" — is not met**: `verify_state` says resolved-and-matching is fresh, `epic_verify_state` says only `passed`-and-matching is, and the code agrees with `epic_verify_state`.

  Behaviour is correct (24 shapes × 4 classifiers, **0 disagreements**); this is documentation-only. It is the exact recurring shape: one of several sibling statements of the same rule updated, the others left telling the old story, inside the same docstring the finding named.
- **Suggested fix:** One edit in `scripts/forge-session.py`, `verify_state`'s docstring only — no code change, no test change. Replace the `fresh` bullet (`:880-881`) with:

  > `- ``fresh``   — the entry is ``passed`` AND its ``verifiedStageVersion`` matches the stage's current ``version`` (so no re-verify is needed). ``passed`` is the ONLY status that reaches ``fresh``: ``findings-applied`` and ``skipped`` are resolved but never fresh, for the reasons given below.`

  **Acceptance evidence:** after editing, read all seven bullets of `verify_state`'s docstring **top to bottom as prose** and confirm no bullet's stated condition is satisfied by an input another bullet claims; then read it side by side against `epic_verify_state`'s `fresh` and `stale` bullets and confirm the two now name the same status set; then re-run the 24-shape × 4-classifier matrix and confirm it is byte-for-byte unchanged (0 disagreements, `findings-applied` → `stale` at absent/matching/non-matching); `ruff check scripts/ eval/` clean. **Note:** this file is mirrored into all six adapter trees — `python3 scripts/build-adapters.py --check` will exit 1 until the mirrors are regenerated, and the regenerated mirrors must be committed with the fix. This is the premise round 6's Step 6 got wrong.
- **References:** `scripts/forge-session.py:263` (`_VERIFY_RESOLVED`), `:897-901` (the `skipped` bullet, which already carves itself out), `:941-949` (the guard); `scripts/epic-manifest.py:1066-1072` (the sibling that is right); `03-verification-state.md` §5.1; round-6 V-002 Step 2
- **Checklist:** CHECK-I19, CHECK-I14

### V-004: Control 3a-ii's docstring — the reference the module docstring was rewritten to match — accounts for 5 of the 6 surfaces while asserting "all six"

- **Severity:** improvement
- **Location:** `tests/test_capability_determination_prose.py:417-421` (`test_downgrading_the_affirmative_choice_to_a_printed_command_fails_the_guard`, docstring)
- **Issue:** Round-6 V-001 named control 3a-ii as the correct account and required the module docstring be rewritten to "tell the same story". That was done, and done well (§5 above: every claim re-derived, including the history at `21f1c34`). The result is that the **module docstring is now the more complete of the two**, and 3a-ii carries the residue of the defect V-001 was filed about:

  > "While c1a and c1b shared one any-of list this misreading was undetected **on all six surfaces**: rewriting `forge-verify`'s "dispatched on the affirmative choice" to "printed for the user" left the untouched "presented through the gate" matching, and the authoring stages carried no dispatch phrasing at all."

  It asserts six, then explains `forge-verify` (1) and the authoring stages (4) — five. `forge-fix`'s reason (it kept `presented through the Step 6 gate`, a **different** fragment, and round-5's Deviation-1 analysis established that `presented through the gate` is *not* a substring of it) is not stated. A reader who counts is invited to conclude that `presented through the gate` covered `forge-fix` too — which is precisely the wrong inference round-6 V-001 filed against the module docstring.

  Not false, only incomplete, and the guard behaviour is unaffected — hence `improvement`. But this is the third round in a row in which a sibling docstring stating the same fact was left unswept, so closing the pair rather than the instance is what makes the sequence terminate.
- **Suggested fix:** One sentence in `tests/test_capability_determination_prose.py:420-421`. Change:

  > `left the untouched "presented through the gate" matching, and the authoring stages carried no dispatch phrasing at all.`

  to:

  > `left the untouched "presented through the gate" matching on \`forge-verify\`, \`forge-fix\` matching on its own "presented through the Step 6 gate", and the four authoring stages matching on their gate-block fragment — they carried no dispatch phrasing at all, so the mutation was a no-op there.`

  Change nothing else in the module. No test change; `43 passed` before and after.

  **Acceptance evidence:** read the amended 3a-ii docstring and the module docstring's clause (c) **end-to-end, side by side, as prose**, and confirm each of the six surfaces is accounted for in both and that neither contradicts the other; re-confirm `presented through the gate` occurs in exactly 1 of the 6 capability paragraphs.
- **References:** `tests/test_capability_determination_prose.py:34-39` (the module docstring, now correct), `:137-154` (`CLAUSES["c1a"]`/`["c1b"]`); round-6 V-001; round-5 Deviation 1
- **Checklist:** CHECK-I19

### V-005: No `smokeCommand` is configured — advisory re-affirmed (CHECK-I21)

- **Severity:** improvement
- **Location:** `/home/gary/workspace/feature-forge/forge.config.json`, `"smokeCommand": null`
- **Issue:** CHECK-I21 requires an advisory finding whenever `smokeCommand` is `null`. Decision 6 (round 5) resolved to **keep `null`**, and `07-testing-strategy.md` §8.3 records that decision explicitly under REQ-COMPAT-03. Re-assessing this round: **`not-applicable` remains right.** All seven rounds' residual defects have been vacuous guards and false prose, neither of which any booting smoke command can detect — this round's V-001 is a docstring that misdescribes a helper, and V-002 is an `ast` guard with six open spellings; both are invisible to a running process. The "does it actually run" risk continues to be covered at the real boundary by `tests/test_stage_exit.py`, which drives the shipped CLI as a genuine `subprocess.run([sys.executable, HELPER, "stage-exit", …])`.
- **Suggested fix:** None required. Keep `smokeCommand: null` per Decision 6 and §8.3. This entry exists only to satisfy CHECK-I21's mandatory advisory; it is **not** a recommendation to configure one, and it must not be read as a remedy for the recurring false-narrative failures.
- **References:** `specs/stage-exit-coverage/07-testing-strategy.md` §8.3; round-6 V-006, round-5 V-013, Decision 6
- **Checklist:** CHECK-I21

---

## Round-6 finding disposition (each independently re-measured)

| Round-6 finding | Verdict | Independent evidence derived this round |
|---|---|---|
| **V-001** module docstring names a fragment living on 1 of 6 surfaces | **RESOLVED** | The rebuilt sentence names the right c1a fragment for each of the three surface groups — re-derived per surface (`reuse the Standard Verify Gate block for consent` ×4, `presented through the gate` on `forge-verify`, `presented through the Step 6 gate` on `forge-fix`). `presented through the gate` occurs in exactly **1 of 6** capability paragraphs, and the sentence now attributes it to `forge-verify` alone. Merged-list reconstruction with the c1b deletion → **6 of 6 GREEN**, each on its own gate fragment. History at `21f1c34` re-derived from `git show`: the four authoring stages carry **0** occurrences of `dispatched on the affirmative`; `forge-verify` and `forge-fix` carry their respective gate fragments. Read end-to-end against control 3a-ii: no contradiction. The untouched first half ("four surfaces") also re-derives exactly. Residual: 3a-ii itself is now the less complete of the pair → **V-004**. |
| **V-002** `verify_state` docstring gives the superseded rationale | **PARTIAL** | Both prescribed edits landed and both are **correct** — the `stale` bullet now names the `findings-applied` reason and the closing paragraph states it unconditionally, matching `epic_verify_state:1066-1072` read side by side. The 24-shape × 4-classifier matrix is unchanged (**0 disagreements**; `findings-applied` → `stale` at absent/matching/non-matching). But the **`fresh` bullet three lines above** was not swept and still says freshness is "resolved AND matching" — and `findings-applied` ∈ `_VERIFY_RESOLVED`, so it is contradicted by the amended bullet below it and by the code (measured: `findings-applied` + matching version → `stale`). V-002's own acceptance criterion ("neither states a rule the other contradicts") is not met. → **V-003**. |
| **V-003** §2 is not the *Complete* file layout | **RESOLVED** | `git diff --name-status e89d8fa~1..HEAD -- . ':(exclude)adapters/' ':(exclude)specs/'` → **49 paths**; 46 listed explicitly in §2 (including the two new `tests/fixtures/**/epic-manifest.json` entries), 1 covered by the `<existing epic manifest tests>` placeholder, and exactly 2 attributable to `b3110b1` (`git log` on each returns only that commit). The new row's marker sits at **column 44**, matching every other row in the `tests/` block, and uses the block's existing two-line continuation form. `.gitignore` / `forge.config.json` correctly not added. |
| **V-004** four open shadowing paths in the roster guard | **PARTIAL** | Decision 1(a) applied; **all four named probes are genuinely closed** at exactly the recorded lines, re-derived with my own harness on real file copies with a scratch-root effectiveness control: N1 → `:591`, N2 → `:566`, N3 → `:566`, N4 → `:587`. P1–P6 unchanged (`:574`/`:574`/`:574`/`:570`/`:566`/`:591`). The floor at `:526` was **never** the source of a red in any of the 16 probes, and displacement was proven for every probe by the reversed `SURFACE_IDS`. But **six further binding forms are GREEN with the roster displaced** — walrus, module-level `for` target, `global`-in-function, `with … as`, and the `for`/walrus variants on the derivation name → **V-002**; and the helper docstrings written to justify the generalisation claim a completeness the code does not have → **V-001**. |
| **V-005** `_state_verify_call_text` docstring off by one | **RESOLVED** | The amended sentence — "Joining `CALL_SPAN` lines starting at the verb's line (so the verb plus up to `CALL_SPAN - 1` continuations)" — states a count that **equals** the slice width at the consumer (`:302`, `lines[index : index + CALL_SPAN]`, `CALL_SPAN = 3`). Read end-to-end against the `CALL_SPAN` comment block (`:61-89`): both describe the same 3-line window, the same six four-line sites, the same offset-0-or-1 basis. No quantity is stated twice with two values anywhere in the module. |
| **V-006** no `smokeCommand` configured | **RESOLVED as a decision** | Decision 6 kept `null`; `07-testing-strategy.md` §8.3 records it as not-applicable **by design** under REQ-COMPAT-03. Re-affirmed as **V-005** per CHECK-I21's mandatory advisory. |

**One correction to the fix pass's own record, for round 8's benefit:** Fix Progress Step 6 states the disclosed deviation correctly (Step 6's "no canon or adapter surface is touched" premise was wrong; `scripts/forge-session.py` is mirrored, `--check` exited 1, regeneration was run and committed). I independently confirm both halves: `--check` exits **0** at HEAD, five of six mirrors are byte-identical to canon, and the pi mirror is reproduced **byte-for-byte** by `canon.replace("/feature-forge:", "/skill:")`. **The same premise error will recur in V-003's fix** — it edits `scripts/forge-session.py` again — so V-003's step below carries the regeneration requirement explicitly.

---

## Checks Executed

| Check | Result | Note |
|---|---|---|
| CHECK-I01 | pass | §2 is now complete. All 49 paths in `e89d8fa~1..HEAD` (excluding `adapters/`, `specs/`) are listed, placeholder-covered, or attributable to `b3110b1`; the new fixtures row's marker is at column 44 like every sibling. |
| CHECK-I02 | not-applicable | No `package.json` anywhere in the repo; Python + markdown plugin, no exports map. |
| CHECK-I03 | pass | The `forge-session.py` diff is a docstring-only change (11 lines, all inside `verify_state`'s docstring). No `Literal` alias, `Final` constant, `TypedDict` or quoted callable signature from `00-core-definitions.md` was touched. |
| CHECK-I04 | pass | `UsageError` and its handler untouched by this diff. |
| CHECK-I05 | pass | 32/32 backlog items `done` with `completedAt`; both standing traps still hold (`MIN_CALL_SITES = 34` and the 12/3 `--epic` window are intact and green under `validate.sh`). |
| CHECK-I06 | pass | `Counter({'done': 32})`, ids `001`..`032` — no `pending` or `in-progress`. |
| CHECK-I07 | pass | Every round-6 acceptance claim was re-derived from the code/artifacts this round with instruments different from the fix pass's. 4 of 6 fully reproduce; 2 are PARTIAL (V-002, V-004) and are filed. |
| CHECK-I08 | pass | Exactly one import added in the whole diff (`from collections.abc import Iterator`), correctly placed and used. All three changed modules import and run (43 / 10 / CLI standalone). |
| CHECK-I09 | pass | Canon untouched by this round; `build-adapters.py --check` exit 0. |
| CHECK-I10 | pass | 5/6 `adapters/*/scripts/forge-session.py` mirrors byte-identical to canon; `adapters/pi/` differs on 72 lines and is reproduced **byte-for-byte** by the documented `/feature-forge:` → `/skill:` degradation, zero residual lines. |
| CHECK-I11 | pass | `ruff check scripts/ eval/` exit 0. `ruff check tests/` **19 errors**, unchanged. `ruff check tests/ --select F841,F541` clean. |
| CHECK-I12 | pass | `bash scripts/validate.sh` exit 0, `All checks passed!`; full suite **1809 passed, 2 skipped**; **0** `tests/fixtures` bytecode after validate and again after the full suite. |
| CHECK-I13 | pass | **0** TODO/FIXME/XXX/HACK/TBD markers among the 249 added lines. |
| CHECK-I14 | **fail** | V-003. The guards themselves and their inline comments are accurate in all three classifiers, and the four-classifier matrix agrees on all 24 shapes. The failure is `verify_state`'s `fresh` bullet, which states a condition the amended `stale` bullet three lines below it and the code both refute. |
| CHECK-I15 | pass | No new hardcoded value in the diff. `CALL_SPAN = 3` and `MIN_CALL_SITES = 34` untouched; `MIN_CAPABILITY_SURFACES = 6` untouched and never the source of a red across 16 probes. |
| CHECK-I16 | pass | 1811 collected, 1809 passed / 2 skipped; the diff adds and removes no tests (module count 43 before and after, confirmed by the unmutated control). |
| CHECK-I17 | **fail** | V-002 (and contributing to V-001). All four probes Decision 1(a) targeted are genuinely closed at their own de-shifted lines and the six pre-existing ones are unchanged — but six further binding forms displace the roster with the module at 43 passed. |
| CHECK-I18 | pass | `README.md` present and listed in §2; `docs/architecture/` holds three feature dirs; `stage-exit-coverage` absent because `forge-6-docs` has not run — correct for impl-verify. |
| CHECK-I19 | **fail** | V-001, V-003, V-004. Mechanical sweeps over all 249 added lines are **clean** (0 column-0 punctuation, 0 merged words, 0 de-indented docstring continuations, 0 markers); the failures are semantic — two newly-written helper docstrings claiming completeness the helpers lack, one unswept sibling bullet, one incomplete sibling control docstring. |
| CHECK-I20 | pass | V-005 (round 6) is closed: `_state_verify_call_text`'s window arithmetic now equals the slice width at `:302`, and the `CALL_SPAN` comment block and the docstring describe the same 3-line window. |
| CHECK-I21 | not-applicable | `smokeCommand` is `null`. Advisory re-affirmed as V-005; `07-testing-strategy.md` §8.3 records it as not-applicable **by design** under REQ-COMPAT-03. |
| CHECK-I22 | pass | No bootstrap symbol changed this round. `_verify_state_for` remains referenced at `scripts/forge-session.py` in `stage_exit`'s non-epic branch (round-6's mutation evidence stands; the function is untouched by this diff). |
| CHECK-I23 | not-applicable | Python stack, no universal bootstrap entry: no `pyproject.toml`, no framework startup hook, no ASGI/WSGI app object. Unchanged by this round's diff. |

**Executed 23 of 23 checks. Results: 17 pass, 3 fail, 3 not-applicable.**

---

## Fix Execution Plan

### User Decisions Required

**Decision 1 (V-002) — how far to close the roster guard's binding-form coverage.** This assertion has now been rewritten in **five** consecutive rounds. Round 6 chose "generalise the shape class" and the generalisation failed on its first contact with a form outside the three node classes it enumerated. The applier must not pick silently:

- **(a) Close the form class at the right level of abstraction** — collect `ast.Store`-context `ast.Name` nodes plus `ast.NamedExpr` targets plus import aliases, which is the single common denominator of every binding form in the language. Closes all six probes and the class. **Cost:** `bindings[0]` becomes an `ast.Name`, so the `AnnAssign`-shape assertion (`:570`) and the derivation-`Call` assertion (`:574`) must be re-expressed; three assertions change, and the `global` case still needs its own handling or an explicit carve-out.
- **(b) Close the five plausible forms** — add `ast.NamedExpr`, `For`/`AsyncFor` targets and `withitem.optional_vars`; leave `global` recorded but open. Cheap, no assertion re-shaping, closes X1/X2/X4/X5/X6. Leaves X3 and guarantees a sixth rewrite if round 8 probes it.
- **(c) Record and stop** — change no assertion; add a comment naming every unhandled form (`NamedExpr`, `For` target, `with … as`, comprehension target, `import … as`, `except … as`, and `global`-in-function) as out of scope because each requires deliberately leaving a decoy behind. Converts a silent hole into a recorded decision, the device the module already uses for `SURFACES_WITHOUT_PROSE`.

**Recommendation: (c), paired with V-001's Step 1.** This is a change of recommendation from round 6, and the reason is the evidence round 6 produced: (a) was tried, it was executed faithfully and competently, and it still missed six spellings — because the space of ways to rebind a Python name is not enumerable by adding node types, and every round spent enumerating it has ended with the next round finding the next one. Meanwhile the actual defect class this feature keeps shipping is **false prose**, not an under-tight `ast` guard: no probe in five rounds corresponds to real drift, all six of this round's paths need a hand-planted decoy, and the guard's real job — catching someone who replaces the derived roster with a literal list — is already done by the `:574` derivation assertion, which every roster-replacing probe reds on. (c) costs one comment, makes V-001's fix trivially correct, and stops the sequence. If the user prefers a coverage improvement, **(b)** is the better value than (a): it closes five of six for a few lines and no assertion re-shaping.

> **RESOLVED 2026-08-01 — (c), record and stop.** Chosen by the user at the `forge-fix`
> decision gate, matching the recommendation. No assertion changes; a comment enumerates
> every unhandled binding form (`NamedExpr`, `For`/`AsyncFor` target, `with … as`,
> comprehension target, `import … as`, `except … as`, `del`, and `global`-in-a-called-
> function) as deliberately out of scope, on the same rationale the module already uses
> for `SURFACES_WITHOUT_PROSE`: each path requires a hand-planted decoy, none is live
> drift, and the derivation-`Call` assertion at `:574` already reds on any literal-list
> replacement of the roster. Step 1's docstrings are worded to this decision.

**All other findings require no policy call.** V-001, V-003 and V-004 are prose corrections with no behavioural consequence; V-005 is an advisory requiring no action.

### Execution Steps

#### Step 1: Correct the two helper docstrings' completeness claims
- **Files:** `/home/gary/workspace/feature-forge/tests/test_capability_determination_prose.py` (`:472-479`, `:508`)
- **Addresses:** V-001
- **Action:** Apply V-001's suggested fix (1) and (2): replace "*exactly the set of statements that can replace a module global*" and its "rebinds nothing this module reads" premise with a bounded claim naming the `global` exception, and replace "*in any form*" with the explicit form list. Word both to match whatever Decision 1 selects. Change no assertion in this step.
- **Acceptance evidence:** the four items in V-001, ending with an **end-to-end prose re-read of both docstrings against the helper bodies**, statement by statement. No test change expected; `43 passed` before and after.
- **Depends on:** Decision 1 (wording only) — do this first; it is the round's only `error`.

#### Step 2: Resolve the roster guard's binding-form coverage
- **Files:** `/home/gary/workspace/feature-forge/tests/test_capability_determination_prose.py` (`:472-522`, `:552-593`)
- **Addresses:** V-002
- **Action:** Per Decision 1 — (a), (b) or (c) as chosen. Under (c) change no assertion and add only the unhandled-forms comment. Under (a)/(b) apply the code change **and** re-word Step 1's docstrings to match the new coverage exactly.
- **Acceptance evidence (mandatory, `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`, `__pycache__` purged, one fresh **real-file** copy of `tests/`+`scripts/`+`skills/`+`references/` per probe, reversed-order hand-kept roster, plus a scratch-root effectiveness control that mutates `probe/skills/forge-verify/SKILL.md` and confirms a red):** the six X probes must reach the outcome the chosen option promises (RED at the new assertion's own de-shifted line, or re-recorded as GREEN-by-decision **with the probe source in the record**). P1–P6 and N1–N4 must stay red at `:574`/`:574`/`:574`/`:570`/`:566`/`:591` and `:591`/`:566`/`:566`/`:587` (de-shifted). The floor must never be the source of a red. Unmutated copy: **43 passed**. A symlinked `tests/` reads a false GREEN — use real copies.
- **Depends on:** Step 1 (same file), Decision 1

#### Step 3: Sweep `verify_state`'s `fresh` bullet
- **Files:** `/home/gary/workspace/feature-forge/scripts/forge-session.py` (`:880-881`), **plus the six regenerated `adapters/*/scripts/forge-session.py` mirrors**
- **Addresses:** V-003
- **Action:** Apply V-003's suggested fix — name `passed` as the only status reaching `fresh`. Docstring only: do not touch the guard, the ordering, or any return value. **Then run `python3 scripts/build-adapters.py --check`; it WILL exit 1** (this file is mirrored into all six adapter trees — this is exactly the premise round-6 Step 6 got wrong). Regenerate and commit the six mirrors with this pass, then confirm `--check` exits 0.
- **Acceptance evidence:** read all seven bullets of `verify_state`'s docstring top to bottom and confirm no bullet's stated condition is satisfied by an input another bullet claims; read it side by side against `epic_verify_state`'s (`scripts/epic-manifest.py:1066-1072`) and confirm both name the same status set for `fresh` and for `stale`; re-run the 24-shape × 4-classifier matrix and confirm **0 disagreements**, unchanged; `ruff check scripts/ eval/` clean; `check-spec-purity.py` PASS (this file is **not** grandfathered — keep any spec coordinate a bare `§`, which `_SPEC_CITATION_RE` does not match).
- **Depends on:** none

#### Step 4: Complete control 3a-ii's docstring
- **Files:** `/home/gary/workspace/feature-forge/tests/test_capability_determination_prose.py` (`:420-421`)
- **Addresses:** V-004
- **Action:** Apply V-004's one-sentence replacement, naming all three surface groups. Change nothing else.
- **Acceptance evidence:** read the amended 3a-ii docstring and the module docstring's clause (c) end-to-end, side by side, as prose; confirm all six surfaces are accounted for in both and neither contradicts the other; re-confirm `presented through the gate` occurs in exactly 1 of 6 capability paragraphs. `43 passed`.
- **Depends on:** Step 1 (same file)

#### Step 5: Re-gate
- **Action:** **Check `df -h /` for ≥ 1 GB free FIRST** (1.9 GB at the close of this round — round 5 lost a full gate to disk exhaustion, and this is the tightest margin yet; consider pruning before starting). Then `python3 scripts/build-adapters.py --check` — expect **exit 1** before Step 3's regeneration and **exit 0** after. Then `bash scripts/validate.sh` twice back-to-back (both exit 0, both `All checks passed!`), `python3 -m pytest tests -q` (**1809 passed / 2 skipped** if Decision 1 is (b)/(c); if (a) re-shapes assertions, confirm the module is still 43 tests and the total is unchanged by node-ID **set difference**, empty on both sides), `find tests/fixtures -name '__pycache__' -o -name '*.pyc' | wc -l` after each (both 0), `ruff check scripts/ eval/`, `ruff check tests/` (must stay at **19**), `ruff check tests/ --select F841,F541`, `python3 scripts/check-spec-purity.py` (PASS — 0 violations), and `git status --porcelain` (empty).
- **Verification discipline:** every prose edit in this plan must be accepted by **re-reading the passage end-to-end as prose against the artifact it describes**, never by diffing and never by suite-green. **Seven** consecutive rounds have now shipped a mechanically-correct change wrapped in a claim the code does not support, and all 1809 tests were green for every one of them. This round's V-001 is the sharpest instance yet: the false claim is in the docstring of the helper written to fix the previous round's finding.
- **Depends on:** Steps 1–4

---

## Coverage

Every area named in the dispatch was reached:

- ✅ V-001: per-surface c1a re-derivation at HEAD; `presented through the gate` counted per paragraph; merged-list reconstruction (6/6 GREEN); **historical claims re-derived at `21f1c34` via `git show`**; end-to-end prose read against control 3a-ii; the untouched first half's "(four surfaces)" re-measured
- ✅ V-004: **my own** 16-probe battery on **real file copies** (not the fix pass's table), `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`, `__pycache__` purged, one fresh copy per probe; displacement proven for every probe; floor proven never to fire; **scratch-root effectiveness control**; six NEW blind spots found by auditing `_module_scope_nodes` against the full scope list and `_module_scope_writes` against the full binding-form list (`for`, `with … as`, walrus, `global`, `import … as`, `del`, comprehension target, `except … as`)
- ✅ V-002: `verify_state` and `epic_verify_state` docstrings read side by side, bullet by bullet; 24-shape × 4-classifier matrix re-run independently; direct counterexample constructed
- ✅ V-005: stated count vs slice width at the consumer; `CALL_SPAN` comment block and docstring read end-to-end
- ✅ V-003: `git diff --name-status e89d8fa~1..HEAD -- . ':(exclude)adapters/' ':(exclude)specs/'` re-run, all 49 paths accounted for, `b3110b1` attribution re-derived per path, marker column measured programmatically
- ✅ Adapter mirrors: `--check` exit 0; all six diffed against canon; pi reproduced byte-for-byte by the documented degradation
- ✅ Pipeline state: all seven properties, including the cleared `verifiedStageVersion` and the artifact-vs-provenance commit identity
- ✅ Gate: `df` first, `validate.sh`, full suite, collection count, bytecode ×2, ruff ×3, spec-purity, `--check`, `git status`
- ✅ Mechanical sweep: column-0 punctuation, merged words, de-indented docstring continuations, TODO markers, import churn
- ✅ CHECK-I01..I23, all 23 executed

**Methodological note for round 8:** the scratch root used **real file copies** of `tests/`, `scripts/`, `skills/` and `references/` (~8 MB), and its liveness was proven by an effectiveness control that mutates the scratch's own canon and observes 5 reds. The copy was removed after the probes to protect the 1.9 GB margin. A symlinked `tests/` remains fatal — `tests/_forge_paths.py` resolves `REPO_ROOT` through the symlink back to the real repository and every probe reads a false GREEN.

---

## Compact digest

**Findings: 5** — 1 error, 1 inconsistency, 3 improvements, 0 gaps.

| Round-6 finding | Verdict | Evidence |
|---|---|---|
| V-001 module docstring fragment | **RESOLVED** | Per-surface c1a re-derived (4× gate-block, `forge-verify`→`presented through the gate`, `forge-fix`→`presented through the Step 6 gate`); that literal in **1 of 6** paragraphs; merged-list reconstruction **6/6 GREEN**; history at `21f1c34` re-derived (`dispatched on the affirmative` = 0 on all four authoring stages); no contradiction with control 3a-ii |
| V-002 `verify_state` docstring | **PARTIAL** | Both prescribed edits landed and are correct; matrix 24 shapes × 4 classifiers = **0 disagreements**. But the `fresh` bullet at `:880-881` still says "resolved AND matching" and `findings-applied` ∈ `_VERIFY_RESOLVED` — measured `findings-applied` + matching version → `stale`. Sibling `epic_verify_state` says `passed`. → new V-003 |
| V-003 §2 fixtures row | **RESOLVED** | 49 paths in range; 46 listed, 1 placeholder-covered, 2 attributable to `b3110b1` (per-path `git log`); marker at column 44 like every sibling |
| V-004 roster guard, four paths | **PARTIAL** | N1→`:591`, N2→`:566`, N3→`:566`, N4→`:587`; P1–P6 at `:574`/`:574`/`:574`/`:570`/`:566`/`:591`; floor `:526` never fired across 16 probes; all displacements proven. **But six new forms are GREEN**: walrus, module `for` target, `global`-in-function, `with … as`, and `for`/walrus on the derivation name → new V-002 + V-001 |
| V-005 `CALL_SPAN` arithmetic | **RESOLVED** | Stated count == slice width at `:302` (`lines[index : index+CALL_SPAN]`, `CALL_SPAN=3`); comment block `:61-89` and docstring describe the same 3-line window |
| V-006 smokeCommand advisory | **RESOLVED as decision** | Re-affirmed as V-005 per CHECK-I21 |

**New findings:**
- **V-001 (error)** — `_module_scope_nodes`'s docstring claims its traversal is "*exactly the set of statements that can replace a module global*" and that a function-body binding "*rebinds nothing this module reads*"; `_module_scope_writes` claims it finds writes "*in any form*". Probe X3 (`global ALL_SURFACES` inside a called function) and X1/X2/X4 (walrus / `for` target / `with … as`) each displace the roster with the module at **43 passed**. Newly written prose, false against the code it describes — the standing failure mode, in the fix's own helpers.
- **V-002 (improvement)** — six open binding forms in the generalised guard (X1–X6), all with roster displacement proven.
- **V-003 (inconsistency)** — `verify_state`'s `fresh` bullet contradicts the amended `stale` bullet three lines below it and the code; `epic_verify_state` gets it right by naming `passed`.
- **V-004 (improvement)** — control 3a-ii's docstring (the reference V-001 was rewritten to match) accounts for 5 of 6 surfaces while asserting "all six"; `forge-fix`'s reason is unstated.
- **V-005 (improvement)** — CHECK-I21 mandatory `smokeCommand: null` advisory; keep `null` per Decision 6.

**Gate: GREEN, run not taken on report.** `df` 2.3 GB before / 1.9 GB after · `validate.sh` exit 0 `All checks passed!` · **1809 passed, 2 skipped** (1811 collected) · fixture bytecode **0** after validate and after the full suite · `ruff check scripts/ eval/` exit 0 · `ruff check tests/` **19** · `ruff check tests/ --select F841,F541` exit 0 · `check-spec-purity.py` PASS 0 violations · `build-adapters.py --check` exit 0 · **`git status --porcelain` empty** (require-clean satisfied — I wrote nothing to the repository).
---

## Fix Progress

Applied 2026-08-01 by `/feature-forge:forge-fix stage-exit-coverage --served-stage forge-5-loop`
(owner: direct). Decision 1 (V-002) resolved to **(c) record and stop** before any step ran.
The report tail carried a stray subagent harness trailer (`agentId:`/`<usage>`) from the
round-7 write; it was stripped in this pass and is committed corrected here.

- Step 1: [APPLIED] 2026-08-01 — V-001, two helper docstrings in
  `tests/test_capability_determination_prose.py`. `_module_scope_nodes` (`:473-481`) no
  longer claims its traversal is "exactly the set of statements that can replace a module
  global"; it now says it "covers every module-level BINDING STATEMENT", is "deliberately
  NOT exhaustive", and names the `global`-in-a-function exception, pointing at the
  comment for the full out-of-scope list. `_module_scope_writes` (`:508`) replaces "in any
  form" with the explicit form list (`Assign`/`AnnAssign`/`AugAssign` plus
  subscript/attribute/star/tuple stores). Acceptance (not suite-green): probe X3
  (`global ALL_SURFACES` in a called function) and X1/X2/X4 (walrus / `for` target /
  `with … as`) each re-run GREEN with the roster displaced — matching what the amended
  docstrings now say they do NOT cover — and both docstrings were read end-to-end against
  the helper bodies statement by statement, with no remaining sentence asserting a
  property the body lacks. 43 passed before and after.
- Step 2: [APPLIED] 2026-08-01 — V-002 under Decision 1(c). No assertion changed. A
  recorded-decision comment was added ahead of `tree = ast.parse(...)` naming every
  unhandled binding form (`NamedExpr`, `For`/`AsyncFor` target, `with … as`, comprehension
  target, `import … as`, `except … as`, `del`, `global`-in-function) as deliberately out
  of scope, on the `SURFACES_WITHOUT_PROSE` rationale: each needs a hand-planted decoy,
  none is live drift, and the derivation-`Call` assertion catches any literal-list
  replacement regardless of binding form. **Mandatory probe battery** — real file copies
  of `tests/` (symlinks defeat the probe), `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`,
  `__pycache__` purged, one fresh copy per probe, reversed-order hand-kept roster (static
  snapshot, not a call-through), displacement proven by reversed `SURFACE_IDS`:

  | Probe | Expected | Result | De-shifted line |
  |---|---|---|---|
  | P1 literal hand-kept value | RED | RED | derivation `Call` (`:595`) |
  | P2 derived from another fn | RED | RED | derivation `Call` (`:595`) |
  | P3 wrapped in `list()` | RED | RED | derivation `Call` (`:595`) |
  | P4 `AnnAssign` → `Assign` | RED | RED | `AnnAssign` (`:591`) |
  | P5 decoy + re-bind | RED | RED | count (`:587`) |
  | P6 plain alias | RED | RED | alias (`:612`) |
  | N1 annotated alias | RED | RED | alias (`:612`) |
  | N2 nested-`if` re-bind | RED | RED | count (`:587`) |
  | N3 in-place `[:]` slice | RED | RED | count (`:587`) |
  | N4 shadow redef (before binding) | RED | RED | `len(definitions) == 1` (`:608`) |
  | X1 walrus `(ALL_SURFACES := …)` | GREEN by decision | GREEN | roster REVERSED |
  | X2 module `for ALL_SURFACES` | GREEN by decision | GREEN | roster REVERSED |
  | X3 `global ALL_SURFACES` in fn | GREEN by decision | GREEN | roster REVERSED |
  | X4 `with … as ALL_SURFACES` | GREEN by decision | GREEN | roster REVERSED |
  | X5 `for _capability_surfaces` | GREEN by decision | GREEN | roster REVERSED |
  | X6 walrus on derivation name | GREEN by decision | GREEN | roster REVERSED |
  | C0 unmutated control | GREEN | GREEN | 43 passed |

  The floor (`:533`) was **never** the source of a red. The six X-forms are the ones the
  comment now records as out of scope, and each was confirmed to genuinely displace the
  roster (not a no-op) so the record is honest.
- Step 3: [APPLIED] 2026-08-01 — V-003, `scripts/forge-session.py`, `verify_state`'s
  `fresh` bullet (`:880-883`) now names `passed` as the ONLY status reaching `fresh`,
  matching `epic_verify_state` (`scripts/epic-manifest.py:1066-1067`) read side by side.
  Docstring only. All seven bullets read top-to-bottom: no bullet's stated condition is
  satisfied by an input another bullet claims (`findings-applied`+matching version is
  `stale`, not `fresh`; `skipped` carves itself out). 24-shape × classifier matrix re-run
  and unchanged: `fresh` set is exactly `{(passed, matching)}`; `findings-applied` is
  `stale` at absent/matching/non-matching. `ruff check scripts/ eval/` clean;
  `check-spec-purity.py` PASS (the `§4.2 step 4` coordinate is a bare `§`, unmatched by
  `_SPEC_CITATION_RE`). **Adapter regeneration required and done** — this file is mirrored
  into all six trees; `--check` exited 1, `build-adapters.py` was run, the six
  `adapters/*/scripts/forge-session.py` mirrors are committed, `--check` then exited 0.
  (This is the premise round-6 Step 6 got wrong; the round-7 report flagged it in advance.)
- Step 4: [APPLIED] 2026-08-01 — V-004, control 3a-ii's docstring
  (`test_downgrading_the_affirmative_choice_to_a_printed_command_fails_the_guard`,
  `:417-421`) now accounts for all three surface groups — `forge-verify` via
  `presented through the gate`, `forge-fix` via `presented through the Step 6 gate`, the
  four authoring stages via their gate-block fragment — instead of asserting "all six" and
  explaining only five. Read end-to-end against the module docstring's clause (c): each of
  the six surfaces is accounted for in both and neither contradicts the other.
  `presented through the gate` re-confirmed in exactly 1 of 6 capability paragraphs.
  43 passed.
- Step 5: [APPLIED] 2026-08-01 — re-gate on 2.8 GB free. `build-adapters.py --check` exit 1
  before Step 3's regen, exit 0 after. `validate.sh` twice back-to-back (both exit 0, both
  `All checks passed!`, both **1809 passed / 2 skipped**). `find tests/fixtures` bytecode 0
  after each. `ruff check scripts/ eval/` clean, `ruff check tests/` **19**,
  `ruff check tests/ --select F841,F541` clean, `check-spec-purity.py` PASS (0 violations).
  Node-ID **set difference** vs HEAD **empty on both sides** (1811 collected both ways) —
  Decision 1(c) changed no assertion, so no test churn. `git status --porcelain` empty.

**Verification discipline honoured:** every prose edit was accepted by re-reading the
passage end-to-end against the artifact it describes, and every numeric/behavioural claim
was re-derived with an instrument independent of the one that wrote it — never by diffing,
never by suite-green. This round's sharpest case was V-001: false claims in the docstrings
of the very helpers round 6 added, invisible to all 1809 green tests.
