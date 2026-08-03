# 06 — Brittleness Batch

> Seven mechanical corrections to existing tests: one skip guard, two false-positive
> traps, one over-broad token ban, five exact-stderr equality assertions, one evadable
> regex guard, one key-order pin, and three duplicate-coverage families collapsed by
> `@pytest.mark.parametrize`.
>
> **This document changes no product behavior.** It touches four test files and nothing
> else. Every shipped-behavior change in this feature lives in
> `04-production-validations.md`.
>
> **The rosters this document works from are owned by `00-core-definitions.md` §9.** They
> are cited, never re-derived. Locate every symbol by **name**, never by line number
> (C-07).

## Requirement Coverage

| REQ ID | Requirement | Section |
|---|---|---|
| REQ-BRIT-01 | Root-uid skip guard on the chmod-based test | §2 |
| REQ-BRIT-02 | Token scanners with false-positive traps corrected | §3 (§3.1, §3.2) |
| REQ-BRIT-03 | Whole-source token ban narrowed to its region | §4 |
| REQ-BRIT-04 | Exact-stderr equality → substring/regex on diagnostic content | §5 (§5.2–§5.6) |
| REQ-BRIT-05 | Evadable exit-1 guard widened | §6 |
| REQ-BRIT-06 | Key-**order** pin → key-**set** assertion | §7 |
| REQ-BRIT-07 | Dedup across three families, within-file only | §8 (§8.2, §8.3, §8.4) |
| REQ-OBS-01 | Every loosening still names the behavior at fault | §1.3, and one check per site |
| REQ-CANON-03 | All narration specified here states intent only | §1.4 |

## 1. Scope and Contract

### 1.1 Files touched

Per `01-architecture-layout.md` §3.3, this document owns:

| File | Change | Requirements |
|---|---|---|
| `tests/test_auto_verify.py` | one decorator, one import | REQ-BRIT-01 |
| `tests/test_state_verbs.py` | two scanners, four stderr sites, one guard regex, eight parametrize conversions | REQ-BRIT-02, -04, -05, -07 |
| `tests/test_stage_exit.py` | one narrowed ban, one parametrize conversion | REQ-BRIT-03, REQ-BRIT-07 |
| `tests/test_forge_root.py` | one stderr site | REQ-BRIT-04 |
| `tests/test_state_schema_conformance.py` | one key-set assertion | REQ-BRIT-06 |

No other file is edited. No production source, canon file, or adapter mirror is touched by
this document.

### 1.2 What this document does NOT do

Recorded so a verifier resolves them against a position rather than filing them (C-04):

- **It does not delete a test.** REQ-BRIT-07 converts hand-rolled loops to
  `@pytest.mark.parametrize`; every case that ran before still runs, as its own collected
  item.
- **It does not merge a family across files.** `00-core-definitions.md` §9.5 is binding.
- **It does not touch an already-parameterized site.** `00-core-definitions.md` §9.2, §9.3
  and §9.4 name each one; they are unchanged.
- **It does not loosen an assertion outside the `00` §9.1 roster.** Assertions that are
  already substring-based (for example
  `test_commit_hash_against_a_partial_stage_names_its_actual_status`, which already reads
  `assert "status: 'in-progress'" in result.stderr`) are left exactly as they are.
- **It does not restate net test-count figures.** Collected-item and function-count
  accounting belongs to `07-testing-strategy.md` (§9 below).

### 1.3 The diagnostic contract (REQ-OBS-01)

`00-core-definitions.md` §8.3 is the governing rule, restated here because every section of
this document is measured against it:

> **The test for a loosened assertion:** read the failure output alone, and it names the
> flag or behavior at fault. A bare `assert "Error" in stderr` is **not acceptable**.

Operationally, each loosened assertion in §5 pins **three** things and nothing else:

1. that the failure is a `UsageError`-shaped exit-2 diagnostic (`Error:` prefix, empty
   stdout, state byte-identical — all already asserted at each site and **unchanged**);
2. the **flag or subject** the message must name;
3. the **offending value** or the **reason class**, `!r`-quoted where the production
   message quotes it (`00-core-definitions.md` §8.2).

What is deliberately **not** pinned: connective wording, clause order, punctuation, and the
corrective-action sentence. Those are the incidental parts that generated the churn.

Every section below carries an explicit **REQ-OBS-01 check** stating what a reader learns
from the failure output alone.

### 1.4 Narration rule (REQ-CANON-03)

Every docstring and comment specified in this document states **intent only** — no counts,
no "measured", no "confirmed", no empirical claim. The counts in `00-core-definitions.md`
§9 and in this document are **spec content** and must not be copied into code
(`00-core-definitions.md` §10.1).

Pre-existing narration that is not part of a change specified here is left alone; this rule
governs what this feature writes, not what it reads.

## 2. REQ-BRIT-01 — Root-uid Skip Guard

### 2.1 The site

`tests/test_auto_verify.py::test_an_injected_write_failure_exits_2_with_no_dispatch_directive`
injects a write failure by making the feature directory unwritable:

```python
    (root / "specs" / "widget").chmod(0o555)
    try:
        proc = _stage_exit(root, "--feature", "widget", "--stage", "forge-2-tech")
    finally:
        (root / "specs" / "widget").chmod(0o755)
```

Mode `0o555` does not stop `root` from writing, so `tempfile.mkstemp` succeeds, the write
lands, and the test fails at `assert proc.returncode == 2` — a false failure whose message
describes the product rather than the environment. Every other permission-dependent test in
this suite already guards against it; this one does not.

### 2.2 The change

Add the decorator **verbatim** as the siblings spell it, and add the `os` import it needs.

```python
@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="a read-only directory stays writable as root",
)
def test_an_injected_write_failure_exits_2_with_no_dispatch_directive(
    tmp_path: Path,
) -> None:
    """REQ-DEBT-04: a crash before the write cannot falsely claim the debt landed."""
```

The test body is **unchanged**.

### 2.3 Verbatim match against the siblings — confirmed

Both sibling sites spell the condition identically:

- `tests/test_effective_config.py::test_unreadable_input_preserves_os_error`
- `tests/test_stage_exit.py::test_an_unreadable_member_state_falls_back_to_prd`

```python
@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="mode 000 stays readable as root; the directory row covers OSError there",
)
```

The **condition expression is byte-identical** to the siblings. Only the `reason=` string
differs, because this site's mechanism is a read-only *directory*, not a mode-000 *file*,
and `reason` is what a reader sees in `-rs` output. Copying a reason that names "mode 000"
here would be inaccurate narration.

The `hasattr(os, "geteuid")` half is load-bearing and is not simplified: `os.geteuid` is
absent on Windows, where the bare call would raise `AttributeError` at collection.

### 2.4 Required import

`tests/test_auto_verify.py` does **not** currently import `os` and makes no other use of it.
Add it to the existing stdlib import block, in alphabetical position:

```python
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
```

`pytest` is already imported in that file, so the decorator itself needs nothing further.

### 2.5 Error handling

- **As non-root:** unchanged. The chmod succeeds, the write fails, the assertions run.
- **As root:** the item is *skipped*, reported with its `reason`. It is not silently
  passed, and it is not xfailed.
- **On a platform without `geteuid`:** `hasattr` short-circuits, the item runs, and the
  chmod's platform behavior governs — the same position every sibling takes.
- **The `try/finally` chmod restore is unchanged**, so an assertion failure still leaves
  `tmp_path` deletable.

**REQ-OBS-01 check.** Nothing is loosened here; a genuine regression still fails on
`assert proc.returncode == 2`. A root run now reports a named skip instead of a failure that
misattributes an environment fact to the product.

## 3. REQ-BRIT-02 — False-Positive Traps in `tests/test_state_verbs.py`

Two source scanners in that file fail on legitimate text. Both are corrected in place.

### 3.1 `test_tempfile_is_imported_and_jsonschema_is_not`

**Current:**

```python
def test_tempfile_is_imported_and_jsonschema_is_not():
    source = read(FORGE_SESSION)
    assert re.search(r"^import tempfile$", source, re.M)
    assert "jsonschema" not in source
```

**Both halves are traps.** `"jsonschema" not in source` false-flags any legitimate mention —
most obviously a comment in `scripts/forge-session.py` explaining *why* `jsonschema` is not
used, which is exactly the comment a future maintainer would add. And `r"^import tempfile$"`
pins a spelling: `import tempfile  # atomic writes` and `import os, tempfile` both satisfy
the property and both fail the guard.

**The property actually asserted** is about **import statements**: the atomic write path
needs `tempfile`, and `jsonschema` must not be imported because it is absent in CI
(`00-core-definitions.md` §1).

**Replacement.** Add a module-scope helper beside the other source-scanning helpers, and
rewrite the test:

```python
def _imported_modules(source: str) -> frozenset[str]:
    """Root module names bound by an import statement anywhere in ``source``.

    Scanning the parsed statements rather than the raw text means prose that
    names a module — a comment explaining why it is unused, a docstring, an
    error string — is not mistaken for a dependency on it.

    Args:
        source: Python source text to parse.

    Returns:
        The root name of every module reached by an ``import x`` or
        ``from x import y`` statement, at module scope or inside a function.

    Raises:
        SyntaxError: ``source`` is not parseable Python. The guard fails loudly
            rather than reporting an empty import set.
    """
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return frozenset(names)


def test_tempfile_is_imported_and_jsonschema_is_not():
    """The atomic write path needs `tempfile`; importing `jsonschema` would make
    the script unrunnable where it is absent."""
    imported = _imported_modules(read(FORGE_SESSION))
    assert "tempfile" in imported, (
        f"{FORGE_SESSION.name} does not import tempfile; the atomic write path needs it"
    )
    assert "jsonschema" not in imported, (
        f"{FORGE_SESSION.name} imports jsonschema, which is not available in CI"
    )
```

**Required import.** Add `import ast` to `tests/test_state_verbs.py`'s stdlib block.

> **This is not the layer REQ-GUARD-07 deletes.** REQ-GUARD-07 removes an AST layer in
> `tests/test_capability_determination_prose.py` that inspected **its own test source**.
> `_imported_modules` parses the **production script under test**, which is the same use
> `ast` already has in `tests/test_stage_exit_protocol.py` and
> `tests/test_stage_constants_parity.py` (`00-core-definitions.md` §11, where `ast` is
> recorded as remaining in both). No self-inspection is introduced.

**Alternative considered and rejected.** A narrowed regex —
`r"^[ \t]*(?:import[ \t]+jsonschema\b|from[ \t]+jsonschema[.\w]*[ \t]+import\b)"` with
`re.M` — needs no new import and does defeat the comment trap, because a comment line begins
with `#`. It is rejected because it is another spelling heuristic: a docstring line
beginning at column 0 with `import jsonschema` still false-flags, and it leaves the
`^import tempfile$` trap on the positive half untouched. `00-core-definitions.md` §5.3
forbids answering an evasion with one more spelling; parsing eliminates the class.

**Error handling.**

- `read(FORGE_SESSION)` raises `OSError` if the script is missing — an error, not a silent
  pass, which is correct: the guard cannot conclude anything about a file it cannot read.
- `ast.parse` raises `SyntaxError` on unparseable source — again loud. A `try/except`
  returning an empty set would make a broken script *pass* the negative half.
- Neither assertion can pass vacuously: an empty import set fails the `tempfile` half.

**REQ-OBS-01 check.** A failure reads `forge-session.py imports jsonschema, which is not
available in CI` or `forge-session.py does not import tempfile; the atomic write path needs
it`. The module and the broken property are both named.

### 3.2 `test_every_canon_mention_of_amend_forbids_it`

**Current:**

```python
            lowered = line.lower()
            assert "never" in lowered or "without" in lowered, (
                f"{path.relative_to(REPO_ROOT)}:{number} mentions --amend without "
                f"forbidding it:\n{line.strip()}"
            )
```

**The trap is bidirectional.** The negation is matched against the **whole line**, so:

- `"Do this without checking, then run --amend."` **passes** — "without" governs
  "checking", not `--amend`. A real provenance route sails through.
- `"--amend is forbidden"` **fails** — the mention *is* forbidden, in the strongest
  possible terms, but not with one of two hardcoded words.

Both directions are defects: the first is a false negative on the property the guard
exists for, the second a false positive on legitimate canon.

**The property actually asserted:** every mention of `--amend` sits inside a clause that
forbids it.

**Replacement.** Two module constants and a helper beside `_canon_text_files`, then the
rewritten test:

```python
#: Clause boundaries for the `--amend` scan: sentence-final punctuation, the
#: parenthesis pair, and a comma introducing a following instruction. A
#: prohibition on one side of a boundary does not govern a mention on the other.
_CLAUSE_BOUNDARY: Final[re.Pattern[str]] = re.compile(r"[;:()!?]|\.(?=\s|$)|,\s+then\b")

#: The wording that counts as forbidding `--amend` within its own clause. Matched
#: case-insensitively and on word boundaries, so canon may phrase the prohibition
#: however it reads best.
_AMEND_PROHIBITION: Final[re.Pattern[str]] = re.compile(
    r"\b(?:never|not|no|without|forbid(?:s|den)?|prohibit(?:s|ed)?"
    r"|disallow(?:s|ed)?|ban(?:s|ned)?|refuse(?:s|d)?)\b",
    re.IGNORECASE,
)


def _amend_clauses(line: str) -> list[str]:
    """Return the clause-sized fragments of ``line`` that mention ``--amend``.

    Args:
        line: One line of canon prose or source text.

    Returns:
        Every fragment containing ``--amend``, delimited by ``_CLAUSE_BOUNDARY``.
        Empty when the line does not mention the flag at all.
    """
    return [part for part in _CLAUSE_BOUNDARY.split(line) if "--amend" in part]


def test_every_canon_mention_of_amend_forbids_it():
    """Prose may name `--amend` only inside a clause that forbids it.

    The two-commit protocol exists precisely because amending rewrites HEAD, so a
    hash captured before the amend points at a commit that is not in the final
    history. A prohibition in a NEIGHBOURING clause does not govern the mention,
    and a mention its own clause forbids is acceptable however it is phrased — so
    the negation is matched against the clause, not the line.
    """
    files = _canon_text_files()
    assert files, "no canon files were scanned"
    seen = 0
    for path in files:
        for number, line in enumerate(read(path).splitlines(), start=1):
            for clause in _amend_clauses(line):
                seen += 1
                assert _AMEND_PROHIBITION.search(clause), (
                    f"{path.relative_to(REPO_ROOT)}:{number} mentions --amend in a "
                    f"clause that does not forbid it:\n{clause.strip()}"
                )
    assert seen, "the prohibition itself disappeared from canon"
```

`_CLAUSE_BOUNDARY` carries **no capturing group**, so `re.split` returns the fragments only.
`.` is a boundary only when followed by whitespace or end of line, so a dotted filename
(`.pipeline-state.json`) does not split a clause.

**Behaviour on the two counterexamples:**

| Line | Fragment containing `--amend` | Result |
|---|---|---|
| `Do this without checking, then run --amend.` | `run --amend` | **fails** — correct |
| `--amend is forbidden` | `--amend is forbidden` | **passes** — correct |

**Behaviour on canon as it stands.** Every existing mention keeps its prohibition inside its
own fragment — the three shapes canon uses are a leading `never` in the same clause
(`**Two-commit provenance — never `--amend`.**`), a parenthetical
(`the protocol's two-commit follow-up (never `--amend`)`), and a semicolon-introduced clause
(`; never use `--amend`/`--no-verify`/`--force`.`). The scan reaches `scripts/`, `skills/`,
`references/` and `agents/` through the unchanged `_canon_text_files`.

**Declared boundary (`00-core-definitions.md` §5.3).** The guard's unit is a
**punctuation-delimited clause**, not a parsed English clause. It does not resolve
prohibitions carried across a boundary by a relative pronoun or a coordinating conjunction
(`` `--amend`, which is forbidden ``). Canon is required to keep a prohibition in the same
clause as the mention it governs — which is also what makes the prohibition readable. This
boundary is declared rather than chased with more punctuation cases, per
`00-core-definitions.md` §5.3.

**Error handling.**

- `assert files` (unchanged) prevents a vacuous pass when the roster resolves empty.
- `assert seen` (unchanged in intent, now counting clauses rather than lines) prevents a
  vacuous pass when the prohibition disappears from canon entirely.
- `read(path)` raises `OSError` on an unreadable canon file — loud, not skipped.
- A line with two `--amend` mentions in different clauses is checked **once per clause**;
  neither can hide behind the other.

**REQ-OBS-01 check.** A failure names the canon file, the line number, and prints the
offending **clause** — a strictly sharper diagnostic than the previous whole-line print.

## 4. REQ-BRIT-03 — Narrow the Whole-Source Token Ban

### 4.1 The site

`tests/test_stage_exit.py::test_docs_never_reimplements_the_epic_dependency_derivation`:

```python
def test_docs_never_reimplements_the_epic_dependency_derivation() -> None:
    """tech-spec §3.5: the router consumes render-status; it does not re-derive."""
    source = HELPER.read_text()
    for forbidden in ("unmet_deps", "parallelEligible", "is_complete_for_orchestration"):
        assert forbidden not in source, forbidden
```

`HELPER` is `scripts/forge-session.py`. The property is a property of **`_render_status`** —
the docs exit consumes `epic-manifest.py render-status` instead of re-deriving the epic
dependency graph. The ban is applied to the **entire file**, so any unrelated future
addition anywhere in the script — a docstring naming `parallelEligible` while describing
what this router deliberately does *not* compute, a comment, an unrelated verb — fails a
guard about a function it has nothing to do with.

**This is the only unsliced token ban in the file.** Every other source-text assertion in
`tests/test_stage_exit.py` already scopes to the region whose property it asserts; the
adjacent test is the template.

### 4.2 The slicing idiom to copy

`test_docs_resolves_the_helper_beside_itself_and_never_a_bare_python3`, immediately above it
in the same file, already establishes it:

```python
    source = HELPER.read_text()
    body = source[source.index("def _render_status(specs_dir"):]
    body = body[: body.index("\n_DOCS_OUTCOME_TEXT")]
    # Executable lines only: the docstring legitimately explains why a bare `python3`
    # is wrong, and a prose mention must not satisfy (or fail) a behavioral guard.
    code = body[body.index('"""', body.index('"""') + 3) + 3:]
```

Three slices: **start** at the `def` line, **stop** at the next module-scope name, **strip**
the docstring. The docstring strip is the half that matters most here — `_render_status`'s
real docstring says *"dependency and completion derivation belong to `epic-manifest.py`;
duplicating them in this file is forbidden"*, and the natural way to sharpen that sentence
is to name the derivations it refuses to reimplement. Under the current whole-source ban,
sharpening the docstring breaks the test.

### 4.3 The change

```python
def test_docs_never_reimplements_the_epic_dependency_derivation() -> None:
    """tech-spec §3.5: the router consumes render-status; it does not re-derive.

    Scoped to `_render_status`'s executable body by the same slicing the sibling
    invocation-contract test uses. The ban is a property of that function, and a
    docstring naming a derivation in order to say it belongs elsewhere is prose,
    not a reimplementation.
    """
    source = HELPER.read_text()
    body = source[source.index("def _render_status(specs_dir"):]
    body = body[: body.index("\n_DOCS_OUTCOME_TEXT")]
    code = body[body.index('"""', body.index('"""') + 3) + 3:]
    for forbidden in ("unmet_deps", "parallelEligible", "is_complete_for_orchestration"):
        assert forbidden not in code, (
            f"_render_status re-derives {forbidden!r}; dependency and completion "
            "derivation belong to epic-manifest.py (tech-spec §3.5)"
        )
```

The forbidden-token tuple is **unchanged**. Only the scanned region changes, from
`source` to `code`.

**Alternative considered and rejected.** Extracting the three slices into a shared
`_render_status_code()` helper used by both tests would remove the duplication. It is
rejected because it rewrites `test_docs_resolves_the_helper_beside_itself_and_never_a_bare_python3`,
a passing test that no requirement in this feature names, and `01-architecture-layout.md`
§3.3 scopes this document's edit to the narrowed ban. Duplicating three slice lines is the
smaller cost; if a later feature refactors that region, both tests move together.

### 4.4 Error handling

Each slice can fail, and each failure mode is desirable:

| Operation | Failure | Effect |
|---|---|---|
| `source.index("def _render_status(specs_dir")` | `ValueError` if renamed or its signature changes | test **errors** — it cannot silently scan nothing |
| `body.index("\n_DOCS_OUTCOME_TEXT")` | `ValueError` if that constant is renamed or moved above the function | test **errors** |
| `body.index('"""', ...)` | `ValueError` if the docstring is removed | test **errors** |

`str.index` is used rather than `str.find` precisely for this: `find` returns `-1`, which
would produce a silently truncated or empty region and a guard that passes on nothing. The
guard **fails closed**. This is the same property the adjacent test already relies on.

**REQ-OBS-01 check.** A failure reads `_render_status re-derives 'unmet_deps'; dependency
and completion derivation belong to epic-manifest.py (tech-spec §3.5)` — it names the
function, the token, and the rule. The previous message was the bare token with no
indication of where it was found or why it was banned.

## 5. REQ-BRIT-04 — Exact-Stderr Loosening

### 5.1 The roster and the shared shape

The roster is `00-core-definitions.md` §9.1 — **5 assertion sites / 11 runtime comparisons /
2 files** — reproduced here for navigation only, not re-derived:

| # | File | Test | Comparisons | Section |
|---|---|---|---|---|
| 1 | `test_forge_root.py` | `test_forge_root_fails_actionably` | 1 (vs `FAILURE_MESSAGE`) | §5.2 |
| 2 | `test_state_verbs.py` | `test_commit_hash_against_an_incomplete_stage_exits_2` | 1 | §5.3 |
| 3 | `test_state_verbs.py` | `test_resumable_with_an_explicit_status_complete_exits_2` | 1 | §5.4 |
| 4 | `test_state_verbs.py` | `test_a_malformed_based_on_token_exits_2_naming_the_token` | 3 (loop) | §5.5 |
| 5 | `test_state_verbs.py` | `test_blocks_current_rejects_anything_but_true_or_false` | 5 (loop) | §5.6 |

**Shared shape for sites 2–5.** Each currently reads
`assert result.stderr.strip() == "<the whole message>"`. Each becomes a small ordered set of
independent substring or regex assertions:

```python
    stderr = result.stderr
    assert stderr.startswith("Error:"), stderr          # exit-2 diagnostic shape
    assert "<--flag>" in stderr, stderr                 # which input is at fault
    assert "<reason or offending value>" in stderr, stderr
```

**Substrings are asserted independently, not stitched into one ordered regex.** A regex such
as `r"--commit-hash\b.*forge-2-tech\b.*status: 'pending'"` would re-pin clause **order**,
which is the incidental wording REQ-BRIT-04 exists to release. Independent assertions also
give a sharper failure: the one that fires names the missing element.

**Untouched at every site:** `assert result.returncode == 2`, the empty-stdout assertion
where present, and the byte-identity assertion on the state file. Those are behavioral, not
wording, and REQ-BRIT-04 does not reach them.

### 5.2 Site 1 — `tests/test_forge_root.py::test_forge_root_fails_actionably`

**Current:**

```python
FAILURE_MESSAGE = (
    "feature-forge: cannot locate install root. "
    "Set FEATURE_FORGE_ROOT to the bundle dir, or run from an installed skill dir."
)
...
    assert result.returncode == 1
    assert result.stderr.strip() == FAILURE_MESSAGE
```

`FAILURE_MESSAGE` mirrors one `echo` line in `scripts/forge-root.sh` byte-for-byte,
including the sentence connective and the trailing clause. Rewording the corrective sentence
— which is user-facing prose, the thing most likely to be improved — breaks a test whose
subject is "step 4 fails actionably".

**The diagnostic content:** the tool prefix, the failure, and the environment lever the user
can pull.

**Replacement.** `FAILURE_MESSAGE` is **deleted** — this assertion is its only reader — and
replaced by a marker tuple:

```python
#: What step 4's failure must tell a user: who failed, what failed, and the lever
#: that fixes it. The wording between these is free to improve.
FAILURE_MARKERS: Final[tuple[str, ...]] = (
    "feature-forge:",
    "cannot locate install root",
    "FEATURE_FORGE_ROOT",
)
```

```python
def test_forge_root_fails_actionably(tmp_path):
    """(b) No discoverable root and CLAUDE_PLUGIN_ROOT unset → step 4."""
    lone_dir = tmp_path / "lone" / "scripts"
    lone_dir.mkdir(parents=True)
    lone = lone_dir / "forge-root.sh"
    lone.write_text(RESOLVER.read_text())
    result = _run(
        lone,
        {"HOME": str(tmp_path / "empty-home"), "CLAUDE_PLUGIN_ROOT": ""},
    )
    assert result.returncode == 1
    stderr = result.stderr.strip()
    assert stderr, "step 4 must fail with a diagnostic, not silently"
    for marker in FAILURE_MARKERS:
        assert marker in stderr, (
            f"forge-root.sh step-4 failure dropped {marker!r}: {stderr!r}"
        )
```

`assert stderr` is added deliberately: with equality gone, an empty stderr would otherwise
have to be caught by each marker assertion separately, and "empty" is a distinct defect from
"reworded".

**Deleting `FAILURE_MESSAGE` is part of the change, not a side effect.** A module constant
that duplicates production wording and is read by nothing is exactly what gets re-attached
to an assertion on the next edit.

**Cross-file note.** `"cannot locate install root"` also appears as a *negative* assertion
elsewhere in the same file (`assert "cannot locate install root" not in result.stderr`,
in the success-path test). That assertion is **unchanged**, and after this change the same
substring is the pinned token on both the positive and the negative side — one token, two
directions.

`scripts/build-adapters.py` mentions the message inside a docstring. It is **not** in this
roster and is not touched.

**Error handling.** `_run` returns a `CompletedProcess`; a resolver that exits 0 fails at the
unchanged `assert result.returncode == 1` before any wording is inspected.

**REQ-OBS-01 check.** A failure reads `forge-root.sh step-4 failure dropped
'FEATURE_FORGE_ROOT': 'feature-forge: cannot locate install root.'` — it names the missing
element and prints what was actually emitted.

### 5.3 Site 2 — `test_commit_hash_against_an_incomplete_stage_exits_2`

**Current:**

```python
    assert result.returncode == 2, result.stdout
    assert result.stderr.strip() == (
        "Error: --commit-hash requires forge-2-tech to be complete (status: 'pending'); "
        "run state-complete without --commit-hash first"
    )
    assert state_path.read_bytes() == before, "the rejected follow-up must not write"
```

**The diagnostic content:** the flag (`--commit-hash`), the stage it was aimed at
(`forge-2-tech`), and the status actually found (`'pending'`). The corrective sentence
("run state-complete without --commit-hash first") is helpful prose that no test needs to
freeze.

**Replacement:**

```python
    assert result.returncode == 2, result.stdout
    stderr = result.stderr
    assert stderr.startswith("Error:"), stderr
    assert "--commit-hash" in stderr, stderr
    assert "forge-2-tech" in stderr, stderr
    assert "status: 'pending'" in stderr, stderr
    assert state_path.read_bytes() == before, "the rejected follow-up must not write"
```

**Prior art in the same file.** The sibling
`test_commit_hash_against_a_partial_stage_names_its_actual_status` already reads
`assert "status: 'in-progress'" in result.stderr`. The `status: '<value>'` fragment is
therefore an established pinned token in this file, and this change makes the two siblings
consistent rather than introducing a shape.

**Error handling.** Byte-identity and exit code are unchanged and still run. A message that
names the wrong stage now fails on the `forge-2-tech` assertion specifically, rather than on
an opaque whole-string diff.

**REQ-OBS-01 check.** A failure prints the assertion that fired plus the full stderr, so the
reader learns which of {flag, stage, observed status} the message stopped carrying.

### 5.4 Site 3 — `test_resumable_with_an_explicit_status_complete_exits_2`

**Current:**

```python
    assert result.returncode == 2, result.stdout
    assert result.stderr.strip() == (
        "Error: --resumable implies --status in-progress; do not pass --status complete"
    )
    assert state_path.read_bytes() == before
```

**The diagnostic content:** both flags in the conflict (`--resumable`, `--status`) and the
offending value (`complete`).

**Replacement:**

```python
    assert result.returncode == 2, result.stdout
    stderr = result.stderr
    assert stderr.startswith("Error:"), stderr
    assert "--resumable" in stderr, stderr
    assert re.search(r"--status\s+'?complete'?", stderr), stderr
    assert state_path.read_bytes() == before
```

The one regex at this site is deliberate. A bare `assert "complete" in stderr` would be
satisfied by any message containing the word — including one that named the *wrong* flag —
so the offending value is pinned **adjacent to the flag it was passed to**, which is the
conflict being reported. `'?` tolerates the `!r` quoting form of `00-core-definitions.md`
§8.2 without requiring it, since this particular message currently quotes neither. `re` is
already imported in `tests/test_state_verbs.py`.

**Error handling.** Unchanged exit-code and byte-identity assertions bracket the wording
assertions. `re.search` returns `None` rather than raising, so a shape change fails as an
assertion, not an error.

**REQ-OBS-01 check.** A failure names `--resumable` or shows that no `--status complete`
pair appears in the message, alongside the full stderr.

### 5.5 Site 4 — `test_a_malformed_based_on_token_exits_2_naming_the_token` (3 comparisons)

**Current:**

```python
def test_a_malformed_based_on_token_exits_2_naming_the_token(tmp_path):
    for token, expected in (
        ("forge-1-prd", "Error: --based-on expects STAGE=N, got: 'forge-1-prd'"),
        ("forge-1-prd=two", "Error: --based-on version must be an integer: 'forge-1-prd=two'"),
        ("forge-1-prd=1.5", "Error: --based-on version must be an integer: 'forge-1-prd=1.5'"),
    ):
        ...
        assert result.stderr.strip() == expected, token
```

Three comparisons, one per iteration. The table's second column is a **whole message**; two
of the three differ only in the token that gets interpolated, so the table restates the same
sentence twice.

**The diagnostic content, per iteration:** the flag (`--based-on`), the **reason class**
(shape versus integer), and the **offending token verbatim** — which the test's own name
already declares is the point ("naming the token").

**Replacement.** The table's second column becomes a reason needle, and each iteration
asserts flag, reason, and `!r`-quoted token:

```python
def test_a_malformed_based_on_token_exits_2_naming_the_token(tmp_path):
    """Every malformed shape is refused before any write, quoting what was passed."""
    for token, reason in (
        ("forge-1-prd", "expects STAGE=N"),
        ("forge-1-prd=two", "version must be an integer"),
        ("forge-1-prd=1.5", "version must be an integer"),
    ):
        _feature_dir(tmp_path / token, "demo")
        result = _run(
            "state-complete", "--feature", "demo", "--stage", "forge-2-tech", "--version", "1",
            "--based-on", token, "--specs-dir", str(tmp_path / token / "specs"),
        )
        assert result.returncode == 2, f"{token}: {result.stdout}"
        stderr = result.stderr
        assert stderr.startswith("Error:"), f"{token}: {stderr!r}"
        assert "--based-on" in stderr, f"{token}: the flag is not named: {stderr!r}"
        assert reason in stderr, f"{token}: expected reason {reason!r} in {stderr!r}"
        assert repr(token) in stderr, (
            f"{token}: the message must quote the offending token: {stderr!r}"
        )
        assert not (
            tmp_path / token / "specs" / "demo" / FS.PIPELINE_STATE_FILENAME
        ).exists(), f"{token}: a parse failure must not write state"
```

**How the loosening applies per iteration.** The loop body is where all three comparisons
live, so one rewrite covers all three; the per-iteration `f"{token}: ..."` message prefix
already present in the file is preserved on every new assertion, so a failure still
identifies **which** of the three inputs broke. `repr(token)` reproduces the production
`!r` quoting of `00-core-definitions.md` §8.2 exactly — `'forge-1-prd=1.5'` — without
pinning the words around it.

**This site is deliberately NOT parametrized.** REQ-BRIT-04 loosens assertions; REQ-BRIT-07
deduplicates three named families (`00-core-definitions.md` §9.2–§9.4), and this loop is in
none of them. Converting it would be an undeclared scope expansion.

**Error handling.** Each iteration builds its own feature directory under
`tmp_path / token`, so a failure in one iteration cannot contaminate the next — unchanged.
The "must not write state" assertion is unchanged.

**REQ-OBS-01 check.** A failure reads e.g. `forge-1-prd=two: the message must quote the
offending token: "Error: --based-on version must be an integer\n"` — the input, the missing
element, and the actual output.

### 5.6 Site 5 — `test_blocks_current_rejects_anything_but_true_or_false` (5 comparisons)

**Current:**

```python
def test_blocks_current_rejects_anything_but_true_or_false(tmp_path):
    _feature_dir(tmp_path)
    for bad in ("yes", "1", "", "True false", "no"):
        result = _run(...)
        assert result.returncode == 2, f"{bad!r}: expected exit 2, got {result.returncode}"
        assert result.stderr.strip() == (
            f"Error: --blocks-current expects true|false, got: {bad!r}"
        ), result.stderr
    assert not (tmp_path / "specs" / "demo" / FS.PIPELINE_STATE_FILENAME).exists()
```

Five comparisons, one per loop value. The expected string is itself an f-string built from
the input, so the assertion is really "the production message is spelled exactly like this
template" — the tightest possible coupling to wording.

**The diagnostic content, per iteration:** the flag (`--blocks-current`), the **accepted
domain** (`true|false`), and the **offending value** `!r`-quoted.

**Replacement:**

```python
def test_blocks_current_rejects_anything_but_true_or_false(tmp_path):
    """Anything outside the boolean domain is refused, naming the domain and the value."""
    _feature_dir(tmp_path)
    for bad in ("yes", "1", "", "True false", "no"):
        result = _run(
            "state-ecr", "--feature", "demo", *_ECR_ARGS, "--blocks-current", bad,
            "--specs-dir", str(tmp_path / "specs"),
        )
        assert result.returncode == 2, f"{bad!r}: expected exit 2, got {result.returncode}"
        stderr = result.stderr
        assert stderr.startswith("Error:"), f"{bad!r}: {stderr!r}"
        assert "--blocks-current" in stderr, f"{bad!r}: the flag is not named: {stderr!r}"
        assert "true|false" in stderr, (
            f"{bad!r}: the accepted domain must be named: {stderr!r}"
        )
        assert repr(bad) in stderr, (
            f"{bad!r}: the offending value must be quoted: {stderr!r}"
        )
    assert not (tmp_path / "specs" / "demo" / FS.PIPELINE_STATE_FILENAME).exists()
```

**How the loosening applies per iteration.** All five comparisons are the one statement in
the loop body, so one rewrite covers all five. `repr(bad)` is what makes the loosening safe
across every value including the empty string (`''`) and the whitespace-bearing
`'True false'` — the same `!r` rendering production uses, so this assertion is *stronger*
than a bare containment check on the raw value, which `""` would satisfy vacuously.

The trailing "no state file was created" assertion is **unchanged** and still runs after the
loop, so a rejection that wrote state still fails.

**Error handling.** A production message that stops quoting the value fails on the `repr`
assertion and names the input that produced it. A message that keeps the value but drops
the domain fails on the `true|false` assertion.

**REQ-OBS-01 check.** A failure reads e.g. `'True false': the accepted domain must be named:
"Error: --blocks-current is invalid\n"` — the input, the missing element, and the output.

## 6. REQ-BRIT-05 — Widen the Evadable Exit-1 Guard

### 6.1 The site and what it protects

`tests/test_state_verbs.py`:

```python
def test_the_script_has_no_exit_1_branch():
    """The contract is 0/2 only — a `return 1` anywhere would break it."""
    source = read(FORGE_SESSION)
    assert not re.search(r"^\s+return 1$", source, re.M)
    assert not re.search(r"sys\.exit\(1\)", source)
```

This guard protects the **0/2-never-1 exit contract** of `00-core-definitions.md` §8.1:
`scripts/forge-session.py` exits 0 or 2, never 1, because callers — `stage-exit` consumers,
`validate.sh`, adapter bundles — distinguish "usage/IO failure" (2) from success (0) and have
no meaning for 1.

Both patterns are **literal-spelling traps**. Every one of these passes the guard today
while breaking the contract:

| Evasion | Defeats |
|---|---|
| `return  1` (two spaces) | `return 1` is spelled with exactly one space |
| `return 1  # fallback` | `$` requires end-of-line immediately after `1` |
| `return(1)` | no parenthesised form |
| `sys.exit( 1 )` | no whitespace inside the call |
| `sys . exit(1)` | no whitespace around the attribute dot |
| `raise SystemExit(1)` | only the `sys.exit` spelling is banned |
| `os._exit(1)` | not covered |
| `exit(1)` (the builtin) | not covered |
| `code = 1; return code` | requires dataflow, not spelling — see §6.3 |

### 6.2 The widened patterns

A labelled table replaces the two ad-hoc regexes, so each spelling has a name the failure
message can use:

```python
#: Every literal spelling of an exit-1 branch. Tolerant of whitespace and of the
#: parenthesised return form, so reflowing a line cannot slip one past the guard.
_EXIT_1_SPELLINGS: Final[tuple[tuple[str, str], ...]] = (
    ("return statement", r"(?m)^[ \t]*return[ \t]*\(?[ \t]*1[ \t]*\)?[ \t]*(?:#.*)?$"),
    ("sys.exit call",    r"\bsys[ \t]*\.[ \t]*exit[ \t]*\([ \t]*1[ \t]*\)"),
    ("SystemExit raise", r"\bSystemExit[ \t]*\([ \t]*1[ \t]*\)"),
    ("os._exit call",    r"\bos[ \t]*\.[ \t]*_exit[ \t]*\([ \t]*1[ \t]*\)"),
    ("builtin exit call", r"(?<![.\w])exit[ \t]*\([ \t]*1[ \t]*\)"),
)


def test_the_script_has_no_exit_1_branch():
    """The CLI contract is exit 0 or 2 — no spelling of exit 1 may reach the source."""
    source = read(FORGE_SESSION)
    for label, pattern in _EXIT_1_SPELLINGS:
        found = re.search(pattern, source)
        assert not found, (
            f"{FORGE_SESSION.name} carries a {label} exit-1 branch "
            f"({found.group(0)!r}); the contract is exit 0 or 2 only"
        )
```

**Why each pattern is shaped as it is:**

- **`return statement`** — `^[ \t]*` replaces `^\s+`, which under `re.M` also matched a bare
  newline and, more importantly, *required* at least one whitespace character (a
  module-scope `return 1` was invisible to it). `[ \t]*\(?...\)?` admits `return(1)` and
  `return ( 1 )`. `(?:#.*)?$` admits a trailing comment. `[ \t]*$` after the digit is what
  keeps `return 10` and `return 1000` from matching.
- **`sys.exit call`** — whitespace is admitted around the dot and inside the parentheses.
- **`SystemExit raise`** — matches `raise SystemExit(1)` and any other construction of it.
- **`os._exit call`** — the hard-exit path that bypasses the top-level handler entirely.
- **`builtin exit call`** — `(?<![.\w])` is what keeps this row from double-matching
  `sys.exit(1)` (preceded by `.`) and `os._exit(1)` (preceded by `_`), so each spelling is
  reported under its own label.

### 6.3 Declared boundary — the dataflow evasion

`code = 1; return code` is **not** detectable by a source-text guard: it requires following
a value through an assignment. It is recorded here as a **declared non-goal** of this guard
rather than chased, per `00-core-definitions.md` §5.3 — the space of ways to compute a `1`
is not enumerable, and an unbounded objective produces one-shape-per-round hardening, which
is the failure mode this feature exists to remove.

What actually protects that case is **behavioral**: `scripts/forge-session.py` raises
`UsageError` for every failure and the top-level handler maps it to exit 2
(`00-core-definitions.md` §8.1), and the suite asserts `returncode == 2` at every rejection
site — including all eleven comparisons in §5 and every case in §8. A dataflow-laundered
`1` would fail those, not this guard. **This guard's declared unit is the literal spelling.**

**A second scope expansion is also rejected:** widening the digit to `[13-9]\d*` so the guard
banned every non-{0,2} literal. It is a genuine hardening, but REQ-BRIT-05's stated scope is
widening the existing exit-**1** guard, and the test's name declares that subject. Recorded
so a later round resolves it against a position rather than filing it (C-04).

### 6.4 Error handling

- `read(FORGE_SESSION)` raises `OSError` if the script is missing — the guard cannot pass
  vacuously on an unreadable file.
- `re.search` returns `None` rather than raising; `found` is only dereferenced inside the
  assertion message, which is evaluated only when `found` is truthy.
- Each spelling is asserted separately, so the **first** offending spelling is reported by
  name rather than as an anonymous boolean.

**REQ-OBS-01 check.** The previous guard failed as a bare `assert not re.search(...)` with no
message at all — the reader saw only which of two lines fired. The replacement reads
`forge-session.py carries a SystemExit raise exit-1 branch ('SystemExit(1)'); the contract
is exit 0 or 2 only`: the spelling, the matched text, and the contract. **The loosening
here is a strict diagnostic improvement**, not merely a preservation.

## 7. REQ-BRIT-06 — Key-Order Pin → Key-Set Assertion

### 7.1 The site

`tests/test_state_schema_conformance.py`, inside the already-parametrized
`test_epic_commit_2_records_the_hash_in_the_documented_minimal_shape`:

```python
    state = json.loads(
        (specs / "auth-overhaul" / ".epic-state.json").read_text(encoding="utf-8")
    )
    assert list(state) == ["epic", "updatedAt", "stages"]
    assert state["epic"] == "auth-overhaul"
```

`list(state)` is the **JSON insertion order** — an artifact of the order in which
`forge-session.py` happens to populate the dict before serializing. The documented contract
(`.epic-state.json` has no schema, `00-core-definitions.md` §9 context) is about which keys
exist, not the order `json.dumps` emitted them in. Reordering two adjacent assignments in an
unrelated refactor breaks this test with no behavior change.

This is the **only** key-order pin in the file.

### 7.2 The change

```python
    assert set(state) == {"epic", "updatedAt", "stages"}, sorted(state)
```

The `sorted(state)` message is added so the failure names the actual key set in a stable
order rather than relying on the set literal's repr ordering.

The assertion stays **two-sided** — `==` on a set, not `<=` or a series of `in` checks — so
an *extra* top-level key is still a failure. Only the ordering constraint is released.

Everything around it is unchanged: `state["epic"] == "auth-overhaul"`, the entry lookup,
the `commitHash`, `status` and `verifiedStageVersion` assertions, and the `@pytest.mark.parametrize("value", ACCEPTED_HASHES)`
decorator (which is an already-parametrized hash site per `00-core-definitions.md` §9.2 and
is **not** touched by §8).

### 7.3 Error handling

- `json.loads` raises `JSONDecodeError` if commit 2 wrote unparseable output — an error, and
  the correct one.
- `read_text` raises `FileNotFoundError` if the epic state file was never created — again
  correct, and distinct from "wrong keys".
- A missing key and an extra key both fail the same assertion; `sorted(state)` distinguishes
  them at a glance.

**REQ-OBS-01 check.** A failure reads
`assert {'epic', 'stages'} == {'epic', 'stages', 'updatedAt'}` with the message
`['epic', 'stages']` — it names the missing or surplus key. The previous form failed with a
list diff in which a pure reordering was indistinguishable from a dropped key.

## 8. REQ-BRIT-07 — Deduplication, Within-File Only

### 8.1 The rules this section obeys

From `00-core-definitions.md` §9.5, binding and not restated as opinion:

1. **Hand-rolled loops become parameterized tests in place.**
2. **Already-parameterized sites are untouched.**
3. **Families are never merged across files.** `tests/test_state_verbs.py` asserts **CLI
   behavior**; `tests/test_state_schema_conformance.py` asserts **stored-document shape**.
   Merging them would delete real coverage, not redundancy.

A fourth rule follows from §9.2 and is equally binding: **the five hash loops are not merged
with each other**, because they exercise three different verbs through different fixtures
across two domains, and merging would delete the epic-target coverage.

**Sequencing.** Per `01-architecture-layout.md` §5.4, `05-coverage-backfill.md` adds its
tests to `test_state_verbs.py`, `test_auto_verify.py` and `test_stage_exit.py` **before**
this document rewrites them, so the dedup pass sees the final set of functions and cannot
leave a newly added test outside a family it belongs to. Any REQ-COV test that lands inside
one of these three families joins its parametrize table; §11 makes that a verification item.

**Shared conversion idiom.** Established prior art in this repo —
`tests/test_epic_manifest.py` uses exactly this form:

```python
@pytest.mark.parametrize(
    "label,argv", _INCREMENTING_MUTATIONS, ids=[m[0] for m in _INCREMENTING_MUTATIONS]
)
```

Every conversion below uses it: the existing `(label, value)` tuple constant becomes the
argvalues, the label stays a parameter so it can appear in assertion messages, and `ids=`
derives the node-id suffix from the label. Two consequences apply everywhere:

- **`tmp_path` is per-item.** pytest gives each parametrized item its own `tmp_path`, so the
  hand-rolled per-iteration sub-directories (`tmp_path / f"complete-{label}"`,
  `tmp_path / f"bad-{label}"`, `tmp_path / verb`) are dropped. Isolation is stronger, not
  weaker: it now also spans failures, where a loop stopped at the first one.
- **A failing case no longer hides its successors.** Under a loop, the first failure aborted
  the remaining iterations; under parametrize each case is collected and reported
  independently.

### 8.2 40-hex hash — 9 sites, two sub-families (`00-core-definitions.md` §9.2)

**Roster (cited, not re-derived).** 5 hand-rolled loops in `tests/test_state_verbs.py`
(2 accepted, 3 rejected) + 4 already-parameterized in
`tests/test_state_schema_conformance.py`.

**The 4 in `tests/test_state_schema_conformance.py` are UNCHANGED**
(`test_a_full_hash_is_recorded_verbatim_and_still_conforms`,
`test_a_short_or_malformed_hash_exits_2_byte_intact`,
`test_epic_commit_2_records_the_hash_in_the_documented_minimal_shape`,
`test_epic_commit_2_rejects_a_malformed_hash_byte_intact`). Rule 2 and rule 3.

**The 5 in `tests/test_state_verbs.py` become 5 parametrized functions — one per test.** The
existing `_ACCEPTED_HASHES` and `_REJECTED_HASHES` constants are the argvalues and are
**not** edited.

#### 8.2.1 `test_state_complete_accepts_every_40_hex_casing_verbatim`

```python
@pytest.mark.parametrize(
    "label,value", _ACCEPTED_HASHES, ids=[case[0] for case in _ACCEPTED_HASHES]
)
def test_state_complete_accepts_every_40_hex_casing_verbatim(tmp_path, label, value):
    """REQ-STATE-01: 40 hex characters, in any case, recorded exactly as supplied."""
    _seed(tmp_path, {"forge-1-prd": {"status": "complete", "version": 1}})
    result = _run(
        "state-complete", "--feature", "demo", "--stage", "forge-1-prd",
        "--version", "1", "--commit-hash", value,
        "--specs-dir", str(tmp_path / "specs"),
    )
    assert result.returncode == 0, f"{label}: {result.stderr}"
    recorded = _state_of(tmp_path)["stages"]["forge-1-prd"]["commitHash"]
    assert recorded == value, f"{label}: case was not preserved ({recorded!r})"
```

#### 8.2.2 `test_state_complete_rejects_a_short_or_malformed_hash_before_mutation`

```python
@pytest.mark.parametrize(
    "label,value", _REJECTED_HASHES, ids=[case[0] for case in _REJECTED_HASHES]
)
def test_state_complete_rejects_a_short_or_malformed_hash_before_mutation(
    tmp_path, label, value
):
    """Every non-40-hex shape fails, and the state file is left byte-identical.

    The check runs before `_load_state_for_write`, so the stage-not-complete guard
    is never even consulted for a malformed value.
    """
    _seed(tmp_path, {"forge-1-prd": {"status": "complete", "version": 1}})
    state_path = tmp_path / "specs" / "demo" / FS.PIPELINE_STATE_FILENAME
    before = state_path.read_bytes()
    result = _run(
        "state-complete", "--feature", "demo", "--stage", "forge-1-prd",
        "--version", "1", "--commit-hash", value,
        "--specs-dir", str(tmp_path / "specs"),
    )
    assert result.returncode == 2, f"{label}: exit {result.returncode}"
    assert result.stderr.startswith("Error:"), f"{label}: {result.stderr!r}"
    assert "40-character" in result.stderr, f"{label}: {result.stderr!r}"
    assert not result.stdout.strip(), f"{label} produced stdout"
    assert state_path.read_bytes() == before, f"{label} mutated state"
```

The docstring's spec-document citation (`03 §6.1`) is dropped because it points at a
different feature's spec suite; the sentence it introduced is kept as intent. Every
assertion is carried over unchanged — note in particular that `"40-character" in
result.stderr` was **already** a substring assertion and is therefore untouched by
REQ-BRIT-04 (§1.2).

#### 8.2.3 `test_state_verify_commit_2_accepts_every_40_hex_casing_verbatim`

```python
@pytest.mark.parametrize(
    "label,value", _ACCEPTED_HASHES, ids=[case[0] for case in _ACCEPTED_HASHES]
)
def test_state_verify_commit_2_accepts_every_40_hex_casing_verbatim(
    tmp_path, label, value
):
    """Commit 2 on a verify entry records the supplied casing verbatim."""
    specs = _verify_fixture(tmp_path)
    _reported(specs)
    assert _verify(
        specs, "--stage", "forge-1-prd", "--commit-hash", value
    ).returncode == 0, label
    assert _entry(specs)["commitHash"] == value, f"{label}: case was not preserved"
```

#### 8.2.4 `test_state_verify_commit_2_rejects_a_short_or_malformed_hash_before_mutation`

```python
@pytest.mark.parametrize(
    "label,value", _REJECTED_HASHES, ids=[case[0] for case in _REJECTED_HASHES]
)
def test_state_verify_commit_2_rejects_a_short_or_malformed_hash_before_mutation(
    tmp_path, label, value
):
    """A malformed hash is refused before the verify entry is touched."""
    specs = _verify_fixture(tmp_path)
    _reported(specs)
    before = _state_bytes(specs)
    result = _verify(specs, "--stage", "forge-1-prd", "--commit-hash", value)
    assert result.returncode == 2, f"{label}: exit {result.returncode}"
    assert result.stderr.startswith("Error:"), f"{label}: {result.stderr!r}"
    assert "40-character" in result.stderr, f"{label}: {result.stderr!r}"
    assert not result.stdout.strip(), f"{label} produced stdout"
    assert _state_bytes(specs) == before, f"{label} mutated state"
```

#### 8.2.5 `test_epic_commit_2_rejects_a_short_or_malformed_hash_before_mutation`

**This is the site rule 4 exists to protect.** Its target is `.epic-state.json` through
`_epic_fixture` / `_epic_verify`, not a feature state file; merging it into either of the
two above would delete the epic-target coverage outright.

```python
@pytest.mark.parametrize(
    "label,value", _REJECTED_HASHES, ids=[case[0] for case in _REJECTED_HASHES]
)
def test_epic_commit_2_rejects_a_short_or_malformed_hash_before_mutation(
    tmp_path, label, value
):
    """The epic target refuses a malformed hash and leaves its state file intact."""
    specs = _epic_fixture(tmp_path, revision=1)
    assert _epic_verify(specs, "--status", "skipped").returncode == 0
    state_path = specs / "auth-overhaul" / FS.EPIC_STATE_FILENAME
    before = state_path.read_bytes()
    result = _epic_verify(specs, "--commit-hash", value)
    assert result.returncode == 2, f"{label}: exit {result.returncode}"
    assert "40-character" in result.stderr, f"{label}: {result.stderr!r}"
    assert state_path.read_bytes() == before, f"{label} mutated the epic state"
```

**Error handling across all five.** The fixture builders (`_seed`, `_verify_fixture`,
`_epic_fixture`) assert their own success, so a broken fixture fails as a fixture, not as a
hash-domain failure. `_state_of` and `_entry` re-validate the whole state file against the
schema on every read, so a rejection that corrupted an unrelated field fails there.

**REQ-OBS-01 check.** Each failure carries the node id (`...[legacy-7]`, `...[mixed]`) and
the `f"{label}: ..."` prefix, so the reader learns which hash shape broke which verb —
strictly more than the loop, which reported only the label of the first failure.

### 8.3 Corrupt-file refusal — 4 sites (`00-core-definitions.md` §9.3)

**Roster (cited, not re-derived).** Three hand-rolled in `tests/test_state_verbs.py`:

- `test_load_state_for_write_refuses_a_corrupt_state_file_byte_intact`
- `test_a_corrupt_or_malformed_epic_state_is_refused_byte_intact`
- `test_every_verb_refuses_a_corrupt_state_file_byte_intact`

Plus `tests/test_state_schema_conformance.py`'s already-parameterized
`test_a_corrupt_state_file_exits_2_and_is_left_byte_identical` — **UNCHANGED** (rules 2 and
3).

**Family boundary, pinned (`00-core-definitions.md` §9.3).**
`test_load_state_for_write_refuses_a_non_object_state_file` is **OUT** of this family: it
asserts the *non-object* refusal message (`"not a JSON object"`), not corrupt-JSON refusal.
It is not touched.

> **Divergence from `tech-spec.md` §3.14, recorded rather than silently applied.** That
> section's action table says the three hand-rolled sites become "1 parametrized". The three
> are **not** three spellings of one loop — they differ in *call mechanism*, not in input:
>
> | Site | Mechanism | Target | Varies over |
> |---|---|---|---|
> | `test_load_state_for_write_refuses_a_corrupt_state_file_byte_intact` | **in-process** call to `FS._load_state_for_write`, asserts `FS.UsageError` | feature state | nothing — one input, no loop |
> | `test_a_corrupt_or_malformed_epic_state_is_refused_byte_intact` | CLI via `_epic_verify` | **epic** state | 5 malformation shapes |
> | `test_every_verb_refuses_a_corrupt_state_file_byte_intact` | CLI via `_run` | feature state | **every** registered verb |
>
> Collapsing them into one function requires a parameter that selects a *call mechanism* and
> a test body that branches on it — machinery of exactly the kind R-11 deletes elsewhere in
> this feature — and it would drop either the exception-type assertion, the epic target, or
> the per-verb sweep. That is the "merging deletes real coverage, not redundancy" rule of
> `00-core-definitions.md` §9.5 applied within a single file.
>
> **Adopted:** parameterize in place. The two hand-rolled **loops** become parametrized
> functions; the single-case site has no loop to convert and is left as it is. **The roster
> count is unchanged at 4 sites** — only the tech spec's action cell is at issue.
> `07-testing-strategy.md` owns the derived function-count figure and must recompute it in
> the same edit (REQ-TRIAL-06).

#### 8.3.1 `test_load_state_for_write_refuses_a_corrupt_state_file_byte_intact` — unchanged

One input, no loop, nothing to parameterize. Left byte-for-byte as it stands.

#### 8.3.2 `test_a_corrupt_or_malformed_epic_state_is_refused_byte_intact`

The inline 5-row tuple is lifted to a labelled module constant beside `_epic_fixture` and
becomes the argvalues:

```python
#: Epic-state contents that must be refused, with the diagnostic each one owes.
#: Labels are the parametrize ids, so a failure names the shape it came from.
_CORRUPT_EPIC_STATES: Final[tuple[tuple[str, str, str], ...]] = (
    ("not-json", "{ not json", "not valid JSON"),
    ("json-array", "[]", "not a JSON object"),
    ("stages-array", '{"epic": "auth-overhaul", "stages": []}', "non-object 'stages'"),
    ("stages-string", '{"epic": "auth-overhaul", "stages": "nope"}', "non-object 'stages'"),
    ("wrong-epic", '{"epic": "some-other-epic"}', "records epic"),
)


@pytest.mark.parametrize(
    "label,content,needle",
    _CORRUPT_EPIC_STATES,
    ids=[case[0] for case in _CORRUPT_EPIC_STATES],
)
def test_a_corrupt_or_malformed_epic_state_is_refused_byte_intact(
    tmp_path, label, content, needle
):
    """An unreadable epic state is refused and left exactly as found."""
    specs = _epic_fixture(tmp_path, revision=1)
    state_path = specs / "auth-overhaul" / FS.EPIC_STATE_FILENAME
    state_path.write_text(content, encoding="utf-8")
    before = state_path.read_bytes()
    result = _epic_verify(specs, "--status", "skipped")
    assert result.returncode == 2, f"{label}: exit {result.returncode}"
    assert needle in result.stderr, f"{label}: {result.stderr!r}"
    assert state_path.read_bytes() == before, f"{label}: mutated on a refusal"
```

Each item now builds a **fresh** `_epic_fixture`, where the loop reused one fixture and
overwrote the state file between iterations. That removes a hidden ordering dependency: a
row could previously pass only because a prior row had already left the epic state in a
particular condition.

#### 8.3.3 `test_every_verb_refuses_a_corrupt_state_file_byte_intact`

```python
@pytest.mark.parametrize("verb", sorted(_VERB_INVOCATIONS))
def test_every_verb_refuses_a_corrupt_state_file_byte_intact(tmp_path, verb):
    """No verb may overwrite a state file it could not parse."""
    state_path = _feature_dir(tmp_path) / FS.PIPELINE_STATE_FILENAME
    state_path.write_bytes(b"{ not json")
    result = _run(
        verb, "--feature", "demo", *_VERB_INVOCATIONS[verb],
        "--specs-dir", str(tmp_path / "specs"),
    )
    assert result.returncode == 2, f"{verb}: {result.stdout}{result.stderr}"
    assert "refusing to overwrite it" in result.stderr, verb
    assert state_path.read_bytes() == b"{ not json", f"{verb} touched a corrupt file"
```

`sorted(_VERB_INVOCATIONS)` is used as argvalues so the ids are the verb names and the
collection order is deterministic; the body reads the extra args from the dict. This mirrors
`tests/test_state_schema_conformance.py`'s already-parameterized sites, which use
`@pytest.mark.parametrize("verb", sorted(VERB_INVOCATIONS))` — the two files converge on one
idiom without their assertions being merged.

**Error handling.** `_feature_dir` raises if the directory already exists, which cannot
happen under a per-item `tmp_path`. A verb that exits 0 fails on the return-code assertion
before the byte check, so "wrote something" and "wrote the wrong thing" stay distinguishable.

**REQ-OBS-01 check.** Failures read `state-branch: 0` / `state-branch touched a corrupt file`
with the verb in the node id — the loop reported the same information only for the first
failing verb.

### 8.4 Gate selection — 6 sites (`00-core-definitions.md` §9.4)

**Unit, pinned (cited, not re-derived).** A gate-selection site is a test function under the
`# autoVerify effectiveness × gate selection` section header in `tests/test_stage_exit.py`.
**The section header is the boundary, not the `verifyGate` token** — seventeen tests in that
file reference `verifyGate`; the other eleven assert freshness, routing, or epic state and
are **not** in this family.

> **The section header comment MUST be preserved verbatim.** It is the family's definition.
> Deleting or reflowing it makes the boundary unrecoverable for the next round.

**Site 6, `test_a_manual_capability_gates_manual_print_on_every_host`, is already
parameterized over host and is UNCHANGED** (rule 2). It stays under the same header.

**Sites 1–5 become one parametrized function.** Unlike the corrupt-file family (§8.3), these
five are five spellings of a single mechanism: build a project with a config, run
`stage-exit` for `forge-2-tech`, and assert directives. They differ only in the config, the
extra flags, and **which** directives are load-bearing.

```python
#: Each row: an id, the forge.config.json payload, the extra CLI flags the row
#: needs, and the directives it pins. Rows state only their own load-bearing
#: directives; a key a row does not name is not asserted for that row.
_GATE_SELECTION_ROWS: Final[tuple[tuple[str, dict, tuple[str, ...], dict], ...]] = (
    (
        "auto-verify-off-outstanding-gates-standard",
        {},
        ("--verify-capability", "interactive"),
        {
            "autoVerifyEffective": False,
            "runInStageVerify": False,
            "verifyState": "never",
            "verifyGate": "standard",
            "verifyCommand": "/feature-forge:forge-verify widget",
        },
    ),
    (
        "global-auto-verify-runs-in-stage-and-gates-none",
        {"autoVerify": True},
        (),
        {"autoVerifyEffective": True, "runInStageVerify": True, "verifyGate": "none"},
    ),
    (
        "per-stage-override-beats-global",
        {"autoVerify": True, "autoVerifyStages": {"forge-2-tech": False}},
        ("--verify-capability", "interactive"),
        {
            "autoVerifyEffective": False,
            "runInStageVerify": False,
            "verifyGate": "standard",
        },
    ),
    (
        "non-boolean-auto-verify-fails-closed",
        {"autoVerify": "true"},          # a string, not a bool
        (),
        {"autoVerifyEffective": False},
    ),
    (
        "invalid-auto-verify-keys-surface",
        {"autoVerifyStages": {"forge-1-prod": True}},
        (),
        {"invalidAutoVerifyKeys": ["forge-1-prod"]},
    ),
)


@pytest.mark.parametrize(
    "config,extra,expected",
    [row[1:] for row in _GATE_SELECTION_ROWS],
    ids=[row[0] for row in _GATE_SELECTION_ROWS],
)
def test_auto_verify_effectiveness_selects_the_gate(
    tmp_path: Path,
    config: dict,
    extra: tuple[str, ...],
    expected: dict,
) -> None:
    """Effective autoVerify and the verify capability together select the gate.

    The gate follows `--verify-capability`, not `--host`, which is why the rows
    expecting `standard` pass the flag explicitly: the CLI default is `manual`.
    """
    root = _project(tmp_path, config=config)
    directives = _exit(
        root, "--feature", "widget", "--stage", "forge-2-tech", *extra
    )["directives"]
    missing = sorted(key for key in expected if key not in directives)
    assert not missing, f"stage-exit emitted no {missing} directive(s)"
    assert {key: directives[key] for key in expected} == expected
```

**Every assertion of all five originals is preserved.** Row 1 keeps all five of its
directive assertions including `verifyCommand`; row 5 keeps its `invalidAutoVerifyKeys` list
comparison. No row asserts a directive its original did not.

**`state=None` is dropped from row 1's project build** because it is `_project`'s default —
`_project` writes no state file when `state is None`. The fixture is identical.

**The `missing` check** exists so that a *renamed or removed* directive key fails as a named
assertion rather than as a bare `KeyError` inside a dict comprehension. That distinction is
REQ-OBS-01: "no `verifyGate` directive" and "the wrong `verifyGate` value" are different
defects and must read differently.

**Narration.** The originals carry `# INTENTIONAL CHANGE (item 011, ...)` comments recording
why the gate stopped following `--host`. The rule they encode is kept in the new docstring
as intent; the historical marker is not restated per REQ-CANON-03 (`00-core-definitions.md`
§10.1).

**Error handling.** `_exit` already asserts `proc.returncode == 0` and surfaces stderr, so a
`stage-exit` that fails outright fails inside the helper with the CLI's own diagnostic. A
malformed `forge.config.json` cannot arise — `_project` serializes the row's dict.

**REQ-OBS-01 check.** A failure reads
`test_auto_verify_effectiveness_selects_the_gate[per-stage-override-beats-global]` with a
dict diff naming the exact directive key and both values — the scenario, the directive, and
the divergence. Under the five separate functions the scenario came from the function name
and the directive from the line that fired; both survive.

## 9. The `parametrize` Idiom Introduces No New Convention

`@pytest.mark.parametrize` is the established table-driven idiom of this suite
(`00-core-definitions.md` §1) and is already used by two of the three files this section
converts:

| File | `@pytest.mark.parametrize` today | This document |
|---|---|---|
| `tests/test_stage_exit.py` | used extensively | §8.4 adds one |
| `tests/test_state_schema_conformance.py` | used, including the untouched sites of §8.2/§8.3 | none added |
| `tests/test_state_verbs.py` | **not yet used; the file does not import `pytest`** | §8.2, §8.3 add seven |

> **Accuracy correction, recorded rather than assumed.** `tech-spec.md` §3.14 and
> `00-core-definitions.md` §1 describe the idiom as "established in all three files". It is
> established **suite-wide** and in two of the three; `tests/test_state_verbs.py` uses no
> `pytest` API at all today, so this document must add `import pytest` to it (§10). The
> convention is not new to the project, only to that file. Nothing about the conversions
> changes — the correction is recorded so a verifier resolves it against a position (C-04)
> rather than filing the missing import as a defect.

**Effect on collected items.** Parameterizing **expands** the number of collected items while
reducing the number of test functions: each loop iteration becomes its own item with its own
id, fixture instance, and failure report. **The net-count accounting — functions before and
after, and collected items before and after — belongs to `07-testing-strategy.md`, which
owns the expected-count gates.** No figure is restated here; §8.3's divergence note flags the
one input that document must recompute (REQ-TRIAL-06).

## 10. Imports and Module Constants Introduced

Everything this document adds, in one table, so the diff is auditable:

| File | Addition | For |
|---|---|---|
| `tests/test_auto_verify.py` | `import os` | REQ-BRIT-01 (§2.4) |
| `tests/test_state_verbs.py` | `import ast` | REQ-BRIT-02 (§3.1) |
| `tests/test_state_verbs.py` | `import pytest` | REQ-BRIT-07 (§8.2, §8.3) |
| `tests/test_state_verbs.py` | `from typing import Final` | the constants below |
| `tests/test_state_verbs.py` | `_imported_modules` helper | §3.1 |
| `tests/test_state_verbs.py` | `_CLAUSE_BOUNDARY`, `_AMEND_PROHIBITION`, `_amend_clauses` | §3.2 |
| `tests/test_state_verbs.py` | `_EXIT_1_SPELLINGS` | §6.2 |
| `tests/test_state_verbs.py` | `_CORRUPT_EPIC_STATES` | §8.3.2 |
| `tests/test_forge_root.py` | `FAILURE_MARKERS` (replaces `FAILURE_MESSAGE`) | §5.2 |
| `tests/test_forge_root.py` | `from typing import Final` | `FAILURE_MARKERS` |
| `tests/test_stage_exit.py` | `_GATE_SELECTION_ROWS` | §8.4 |

**Nothing is removed except `FAILURE_MESSAGE`** (§5.2), whose sole reader is the assertion
that replaces it. No existing constant, helper, fixture, or import is deleted or renamed.

**On `Final`.** `00-core-definitions.md` §1 and `references/stacks/python.md` both make
`Final` the convention for module constants, and `tests/test_capability_determination_prose.py`
already applies it in `tests/`. New constants specified here carry it. **Existing
unannotated constants in these files are not retrofitted** — that would be an undeclared
edit outside every REQ-BRIT-\* id, and `Final` on a new constant is not a style change to
the file, it is the project convention applied to new code.

**Gate impact (`01-architecture-layout.md` §7).** Every import added is used, so
`ruff check tests/` cannot gain an unused-import error from this document; REQ-QUAL-02's
non-increase requirement is met by construction, not by inspection.

## 11. Declared Non-Goals

Recorded so a verifier resolves them against a position rather than filing them (C-04):

- **English clause parsing** for the `--amend` scan. The unit is a punctuation-delimited
  clause (§3.2).
- **Dataflow-laundered exit codes** (`code = 1; return code`) in the exit-1 guard. The unit
  is the literal spelling; behavior is what protects the contract (§6.3).
- **Exit codes other than 1** in that guard. The test's subject is exit 1 (§6.3).
- **Dynamic imports** (`importlib.import_module("jsonschema")`) in the dependency scan. The
  unit is an import statement (§3.1).
- **Merging the corrupt-file family into one function** (§8.3), or **merging any family
  across files** (`00-core-definitions.md` §9.5).
- **Refactoring the adjacent `_render_status` slicing into a shared helper** (§4.3).
- **Retrofitting `Final` onto pre-existing constants** in the touched files (§10).
- **Any change to an already-parameterized site** named in `00-core-definitions.md` §9.2,
  §9.3 or §9.4.

## Dependencies

**Spec documents that must be read first:**

- `00-core-definitions.md` — §8.1 (the 0/2-never-1 exit contract this document's §6 guards),
  §8.2 (the `{flag} {reason}; {context}` message shape and `!r` quoting that §5's
  substrings are drawn from), §8.3 (the REQ-OBS-01 diagnostic-preservation contract),
  §9.1–§9.5 (**the four rosters and the within-file dedup rule — this document works from
  them and does not re-derive them**), §10.1 (REQ-CANON-03), §10.5 (the per-file CLI
  wrappers every conversion reuses), §11 (the `ast` position).
- `01-architecture-layout.md` — §3.3 (this document's file ownership), §5.2 step 6 (this is
  the **last** edit workstream), §5.4 (**this document runs AFTER `05-coverage-backfill.md`
  on `test_state_verbs.py`, `test_auto_verify.py` and `test_stage_exit.py`**), §7 (the gate
  list).

**Implementation order this document depends on:**

1. `05-coverage-backfill.md` must have landed its tests in the three shared files first
   (`01-architecture-layout.md` §5.4). Rewriting an existing test before a new sibling
   arrives risks leaving that sibling outside the family it belongs to.
2. Nothing in this document depends on `02-canon-and-prose-guard.md`,
   `03-machinery-trim.md`, or `04-production-validations.md`. It touches none of their
   files and asserts none of their behavior. It may land before or after any of them.
3. `07-testing-strategy.md` depends on **this** document: it owns the count gates and must
   recompute the corrupt-file function figure against §8.3's recorded divergence
   (REQ-TRIAL-06).

**External packages:** none added, none removed. `pytest` and the stdlib (`ast`, `os`, `re`,
`typing.Final`) only. `tests/` may still be run by a bare `python3 -m pytest tests`
(`00-core-definitions.md` §1).

**Production source:** untouched. `scripts/forge-session.py`, `scripts/forge-root.sh`,
`eval/`, `skills/`, `references/` and `adapters/` are all absent from this document's diff.

## Verification

**REQ-BRIT-01**

- [ ] `test_an_injected_write_failure_exits_2_with_no_dispatch_directive` carries the
      `skipif` decorator, and its condition expression is **byte-identical** to the two
      siblings in `tests/test_effective_config.py` and `tests/test_stage_exit.py`.
- [ ] `tests/test_auto_verify.py` imports `os`, and the test body is otherwise unchanged.
- [ ] Run as root, the item reports as a **skip** with its reason; run as non-root, it runs
      and passes.

**REQ-BRIT-02**

- [ ] `test_tempfile_is_imported_and_jsonschema_is_not` scans parsed import statements; the
      raw-text `"jsonschema" not in source` and the `^import tempfile$` regex are both gone.
- [ ] Appending `# jsonschema is deliberately not used here` to `scripts/forge-session.py`
      leaves the test **green**; adding `import jsonschema` turns it **red** with a message
      naming the module.
- [ ] `test_every_canon_mention_of_amend_forbids_it` matches the negation against
      `_amend_clauses(line)`, not the whole line.
- [ ] A canon line reading `Do this without checking, then run --amend.` turns it **red**;
      a line reading `--amend is forbidden` leaves it **green**.
- [ ] The test is green against canon as it stands, and both vacuity assertions
      (`assert files`, `assert seen`) survive.

**REQ-BRIT-03**

- [ ] `test_docs_never_reimplements_the_epic_dependency_derivation` scans `code`, sliced by
      the same three-step idiom as
      `test_docs_resolves_the_helper_beside_itself_and_never_a_bare_python3`.
- [ ] The forbidden-token tuple is unchanged.
- [ ] Adding `parallelEligible` to `_render_status`'s **docstring** leaves it green; adding
      it to `_render_status`'s **body** turns it red with a message naming the function.
- [ ] Renaming `_render_status` makes the test **error** on `ValueError`, not pass.
- [ ] No other unsliced whole-source token ban remains in `tests/test_stage_exit.py`.

**REQ-BRIT-04**

- [ ] All five sites in `00-core-definitions.md` §9.1 are converted; **no sixth site** is
      touched, and assertions that were already substring-based are unchanged.
- [ ] No `assert result.stderr.strip() == ` remains at any of the five.
- [ ] Every one of the eleven comparisons still names the flag or subject **and** the
      offending value or reason class.
- [ ] **No loosened assertion is satisfied by a bare `Error:` prefix alone**
      (`00-core-definitions.md` §8.3). Spot-check: replacing a production message with
      `"Error: bad input"` turns every one of the five red.
- [ ] `FAILURE_MESSAGE` no longer exists in `tests/test_forge_root.py`, and the negative
      assertion `"cannot locate install root" not in result.stderr` elsewhere in that file
      is unchanged.
- [ ] Exit-code, empty-stdout and byte-identity assertions at all five sites are unchanged.

**REQ-BRIT-05**

- [ ] `_EXIT_1_SPELLINGS` covers the return statement, `sys.exit`, `SystemExit`, `os._exit`
      and the builtin `exit`.
- [ ] Each of `return  1`, `return 1  # x`, `return(1)`, `sys.exit( 1 )`, `sys . exit(1)`,
      `raise SystemExit(1)`, `os._exit(1)` and `exit(1)`, inserted into a scratch copy of
      the source string, turns the test **red** — each under its own label.
- [ ] `return 10` and `return 100` do **not** match.
- [ ] `sys.exit(1)` is reported under `sys.exit call` only, not also under
      `builtin exit call`.
- [ ] The failure message names the spelling and prints the matched text.
- [ ] The guard is green against `scripts/forge-session.py` as it stands.

**REQ-BRIT-06**

- [ ] `assert set(state) == {"epic", "updatedAt", "stages"}` replaces the `list(state)`
      comparison, and the assertion is still two-sided.
- [ ] Reordering the writes in `forge-session.py`'s epic-state serialization leaves it
      green; dropping or adding a top-level key turns it red naming the key.
- [ ] The enclosing `@pytest.mark.parametrize("value", ACCEPTED_HASHES)` and every other
      assertion in that test are unchanged.
- [ ] No other key-order pin exists in `tests/test_state_schema_conformance.py`.

**REQ-BRIT-07**

- [ ] **Hash — 9 sites.** The five in `tests/test_state_verbs.py` are five separate
      parametrized functions; **none is merged with another**; the epic-target site
      (`test_epic_commit_2_rejects_a_short_or_malformed_hash_before_mutation`) still drives
      `.epic-state.json` through `_epic_verify`.
- [ ] The four in `tests/test_state_schema_conformance.py` are byte-identical to before.
- [ ] `_ACCEPTED_HASHES` and `_REJECTED_HASHES` are unedited, and every value in both still
      runs as its own collected item at every site that used them.
- [ ] **Corrupt-file — 4 sites.** The two hand-rolled *loops* are parametrized;
      `test_load_state_for_write_refuses_a_corrupt_state_file_byte_intact` is unchanged; the
      `test_state_schema_conformance.py` site is unchanged.
- [ ] `test_load_state_for_write_refuses_a_non_object_state_file` is **not** in the diff
      (family boundary, `00-core-definitions.md` §9.3).
- [ ] **Gate selection — 6 sites.** The `# autoVerify effectiveness × gate selection`
      section header is present and **verbatim**; the five unparametrized tests are one
      parametrized function under it; `test_a_manual_capability_gates_manual_print_on_every_host`
      is unchanged and still under the same header.
- [ ] Every directive assertion of the five originals appears in
      `_GATE_SELECTION_ROWS`, including row 1's `verifyCommand` and row 5's
      `invalidAutoVerifyKeys`.
- [ ] **No family is merged across files**; `tests/test_state_verbs.py` still asserts CLI
      behavior and `tests/test_state_schema_conformance.py` still asserts stored-document
      shape.
- [ ] Every REQ-COV test added by `05-coverage-backfill.md` that falls inside one of the
      three families joined its parametrize table rather than being left beside it.

**Cross-cutting**

- [ ] **REQ-OBS-01:** for every loosened assertion in §3, §5, §6, §7 and §8, the failure
      output read **alone** names the flag or behavior at fault. No assertion in the diff
      reads `assert "Error" in stderr` and nothing more.
- [ ] **REQ-CANON-03:** no comment, docstring or test narration added by this document
      carries a count, a "measured", or any empirical claim.
- [ ] `python3 -m pytest tests -q` is green; `ruff check tests/` has not increased above the
      REQ-QUAL-02 ceiling; `bash scripts/validate.sh` reports "All checks passed!".
- [ ] `scripts/`, `references/`, `skills/`, `eval/` and `adapters/` are **absent** from this
      document's diff.
