# 04 — Production Validations

> **This is the only document in the suite where shipped behavior changes.** Every other
> document edits tests or canon prose. This one edits `scripts/forge-session.py` and
> `eval/run-compliance-eval.py`.
>
> Three edits to `scripts/forge-session.py` (one validation call, one signature widening,
> one validation loop) and one module-level constant in `eval/run-compliance-eval.py`. No
> new CLI verb, flag, exit code, exception type, or JSON payload key. The two validations
> narrow the **accepted domain** of two existing flags and change **no** success-path
> output.
>
> Shared vocabulary lives in `00-core-definitions.md` — §7 (validator contracts and
> placement) and §8 (error contract). This document does not redefine them; it specifies
> the exact edits that realise them. File ownership is fixed by
> `01-architecture-layout.md` §3.2, and the implementation order by its §5.2 step 2.
>
> Locate every symbol by **name**, never by line number (C-07).

## Requirement Coverage

| REQ ID | Requirement | Section |
|---|---|---|
| REQ-FIX-01 | `state-complete --version` rejects values below 1 at the **write** path | §2 |
| REQ-SEC-01 | `state-artifact --path` rejects paths escaping the resolved feature dir | §3 |
| REQ-FIX-02 | Any defect surfaced by the backfill is fixed, not pinned as golden | §4 |
| REQ-COV-03 | The compliance eval's prelude criterion key set is pinned | §5 |

**Interactions stated here, tested elsewhere.** REQ-COV-02, REQ-COV-05, REQ-COV-06, and
REQ-COV-07 are owned by `05-coverage-backfill.md`. This document states the behavioral
positions those tests must assert against (§2.5, §3.7, §4.3, §5.4). **It specifies no
test.**

## 1. Scope

### 1.1 What this document changes

| File | Symbol | Change | Requirement |
|---|---|---|---|
| `scripts/forge-session.py` | `cmd_state_complete` | Call `_require_positive_int(version, "--version")` before `_load_state_for_write` | REQ-FIX-01 |
| `scripts/forge-session.py` | `_validated_findings_file` | Add `label: str = "--findings-file"`; substitute `{label}` into all five messages | REQ-SEC-01 |
| `scripts/forge-session.py` | `cmd_state_artifact` | Validate every `--path` after the load, before any mutation | REQ-SEC-01 |
| `eval/run-compliance-eval.py` | module scope | Add `PRELUDE_CRITERIA: Final[tuple[str, ...]]` mirroring `BRANCH_CRITERIA` | REQ-COV-03 |

### 1.2 What this document does not change

- **No argparse change.** `--version` keeps `type=int, required=True`; `--path` keeps
  `required=True, action="append", dest="paths"`. Their `help=` strings are unchanged.
  `--path` already states its feature-dir-relative contract (§3.7); `--version`'s help is
  left alone because this change narrows an existing flag's domain rather than giving it a
  new meaning.
- **No new exception type, no `try`/`except`.** Both rejections raise the existing
  `UsageError` and propagate to the existing top-level handler
  (`00-core-definitions.md` §8.1).
- **No schema change and no migration.** `.pipeline-state.json` conforms to
  `references/pipeline-state-schema.json` exactly as today (§7).
- **No `eval/` fixture change.** PRD §6 freezes the compliance eval beyond REQ-COV-03
  (§5.3).
- **No rename of `_validated_findings_file`** (§3.8).

## 2. REQ-FIX-01 — the `--version` write-path domain

### 2.1 The confirmed defect

The argparse declaration in `scripts/forge-session.py` (`state-complete` subparser,
located by the parser variable `p_comp`):

```python
p_comp.add_argument("--version", type=int, required=True,
                    help="This stage's new version (integer)")
```

`type=int` is the **only** validator on this flag. It rejects a non-integer spelling and
nothing else — `0` and every negative integer parse cleanly. The parsed value flows
straight into `cmd_state_complete`, and on the completion branch reaches two places
unchecked:

```python
entry["version"] = version
...
cascaded = _cascade_staleness(state, stage, version)
```

So `state-complete --version 0` exits **0** and writes `"version": 0` into
`stages.{stage}.version`.

The **read** path already refuses that value. `_current_artifact_version` ends with:

```python
return _require_positive_int(version, f"{stage}.version")
```

and `_require_positive_int` rejects `bool`, non-`int`, and `< 1`. A later `state-verify`
against that stage therefore exits 2 on a value this script itself wrote.

**The defect is the asymmetry:** the write path accepts a value the read path refuses, so
state is poisoned at write time and the failure surfaces later, at a different verb, with a
message naming `{stage}.version` rather than the flag that caused it.

### 2.2 Naming correction (carried from `00-core-definitions.md` §7.1)

> The PRD (§1, REQ-FIX-01's note) names this validator **`_positive_int`**. **No such
> symbol exists** in `scripts/forge-session.py`. The real name is
> **`_require_positive_int`**. Every document in this suite, and the implementation, uses
> the real name.

### 2.3 The validator — reused verbatim, unchanged

`_require_positive_int` is **not modified by this feature**. Its verified signature and body
as they exist today:

```python
def _require_positive_int(value: object, label: str) -> int:
    """Return ``value`` as a positive int, or raise ``UsageError``.

    ``bool`` is rejected explicitly: it is an ``int`` subclass, so ``True`` would
    otherwise sail through as version 1 and record a freshness ledger entry for an
    artifact revision that never existed.

    Args:
        value: The candidate revision/version.
        label: The flag or field name to name in the error.

    Returns:
        The validated positive integer.

    Raises:
        UsageError: Not an int, a bool, or below 1 (→ exit 2).
    """
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise UsageError(f"{label} must be a positive integer; got {value!r}")
    return value
```

REQ-FIX-01 is satisfied by **calling** it, not by changing it. See
`00-core-definitions.md` §7.1.

### 2.4 Decision — call it unconditionally, before the load

**Decision (tech-spec §3.7).** Call `_require_positive_int(version, "--version")` inside
`cmd_state_complete`, **unconditionally** and **before `_load_state_for_write`**, mirroring
the placement precedent set by `_assert_full_commit_hash`.

**Exact placement:** immediately after the existing `--resumable --status complete`
contradiction guard and immediately before the `if commit_hash is not None:` block that
calls `_assert_full_commit_hash`.

Two properties fix that position:

1. **Before the load.** `--version` needs no resolved path, so it belongs in the same
   pre-load band as `_assert_full_commit_hash` (`00-core-definitions.md` §7.3). Nothing is
   read for mutation and nothing is written, so a rejection leaves the state file
   byte-identical.
2. **After the contradiction guard.** The `--resumable --status complete` guard keeps its
   current message precedence, so an invocation that is invalid on both axes still reports
   the contradiction. Moving the version check ahead of it would silently change the
   message for that combination.

The function body after the edit — only the two marked lines are new:

```python
    if resumable and status == "complete":
        raise UsageError(
            "--resumable implies --status in-progress; do not pass --status complete"
        )
    # The write path must not accept a version the read path refuses; checked before
    # the state file is loaded for mutation, so a rejection touches nothing.   # NEW
    _require_positive_int(version, "--version")                                # NEW
    if commit_hash is not None:
        # Branch 1's first act: full 40-hex only, validated BEFORE the
        # state file is loaded for mutation and long before _commit_state. Legacy
        # short hashes already recorded in state keep loading unmigrated.
        _assert_full_commit_hash(commit_hash)
    state_path, state = _load_state_for_write(specs_dir, feature, epic)
```

**Return value discarded deliberately.** `_require_positive_int` returns the validated
integer, but `version` is already an `int` from argparse's `type=int`, and rebinding it
would imply a normalisation that does not occur. The call is used for its `Raises`
behavior only.

**Docstring change.** `cmd_state_complete`'s `Raises:` section gains the new rejection,
stated as intent only (REQ-CANON-03):

```python
    Raises:
        UsageError: Contradictory ``--resumable --status complete``, a
            ``--version`` below 1, a short or non-hex ``--commit-hash``, a
            ``--commit-hash`` follow-up against a stage that is not complete, an
            unknown feature directory, an unparseable state file, or a failed
            atomic write (→ exit 2).
```

No other line of the existing docstring changes.

### 2.5 Interaction with REQ-COV-05 — stated to pre-empt a false finding

`cmd_state_complete` has three branches in precedence order: commit-2 (`--commit-hash`),
`--resumable`, and the completion write. **Only the completion branch writes
`entry["version"]`.** The other two do not read `version` at all.

But argparse declares `--version` as `required=True` on **every** `state-complete`
invocation, so a commit-2 or `--resumable` call must still supply one. Validating
unconditionally therefore means:

> `state-complete --commit-hash <40-hex> --version 0` now exits 2, where it previously
> exited 0.

**This is intentional.** The distinction that resolves it:

| Concern | Commit-2 / `--resumable` | Completion write |
|---|---|---|
| Is `--version` **written**? | **No** — branch precedence discards it | Yes → `entry["version"]` |
| Is `--version` **validated**? | **Yes** (after this change) | Yes |

"Ignored" in REQ-COV-05 means **not written**, not **not validated**. The precedent is
already in the file: `_assert_full_commit_hash` runs before branch dispatch, so a malformed
`--commit-hash` is refused regardless of which branch would have consumed it.

> **Position for `05-coverage-backfill.md`.** The REQ-COV-05 test MUST assert the
> **write/validate distinction** — that a commit-2 call writes only `commitHash` and leaves
> `status`, `completedAt`, `version`, `basedOnVersions`, and `artifacts` byte-identical. It
> MUST NOT assert that `--version 0` is *accepted* on the commit-2 path, and MUST NOT treat
> the rejection as a contract break. Asserting acceptance would pin the REQ-FIX-01 defect as
> golden, which is exactly what REQ-FIX-02 forbids.

One pre-existing guard is unaffected and keeps running before branch dispatch:
`--resumable` with `--status complete` raises regardless of `--commit-hash`.

### 2.6 Rejected alternative — validate inside the write branch only

Placing the call inside the `else:` completion branch was considered and **rejected**.

It would leave `--version 0` accepted on the commit-2 and `--resumable` paths at exit 0, so
a copy-pasted recovery command could carry an invalid value that looks valid because the
CLI accepted it once. That is a **narrower fix that preserves half the defect**: the
poisoned-write hole closes, the "the CLI told me this was fine" hole does not. Rejected on
that basis (tech-spec §3.7).

### 2.7 Error message — exact

`_require_positive_int` formats with `{value!r}`. For `--version 0` the argparse-parsed
value is the integer `0`, whose `repr` is `0`, so the rendered line is:

```
Error: --version must be a positive integer; got 0
```

Neighbouring values, for the same reason:

| Invocation | stderr |
|---|---|
| `--version 0` | `Error: --version must be a positive integer; got 0` |
| `--version -1` | `Error: --version must be a positive integer; got -1` |
| `--version 1` | *(accepted — no change)* |
| `--version abc` | argparse's own `invalid int value` error, **exit 2, unchanged** |

The last row is not this feature's message: `type=int` rejects it before
`cmd_state_complete` is reached. It is listed so a verifier does not read its different
wording as a defect.

## 3. REQ-SEC-01 — `--path` containment on `state-artifact`

### 3.1 Current state — no validation at all

Verified signature and body of `cmd_state_artifact` today:

```python
def cmd_state_artifact(
    feature: str, stage: str, paths: list[str], specs_dir: Path, epic: str | None
) -> dict:
    ...
    state_path, state = _load_state_for_write(specs_dir, feature, epic)
    entry = _stage_entry(state, stage)
    artifacts = entry.setdefault("artifacts", [])
    for path in paths:
        if path not in artifacts:
            artifacts.append(path)
    return _commit_state(state_path, state)
```

Each `--path` value is appended **verbatim**. There is:

- no absolute-path check,
- no `..`-segment check,
- no containment check against the feature directory,
- no control-character check.

So `state-artifact --path ../../etc/passwd` records a location no forge stage could
legitimately have written, at exit 0, and every downstream consumer that follows a stored
artifact path follows it verbatim.

### 3.2 Decision — reuse `_validated_findings_file` with a defaulted `label`

**Verified current signature:**

```python
def _validated_findings_file(value: str, target_dir: Path) -> str: ...
```

**Required signature (tech-spec §3.8, `00-core-definitions.md` §7.2):**

```python
def _validated_findings_file(
    value: str, target_dir: Path, label: str = "--findings-file"
) -> str: ...
```

The helper's **validation** is already target-agnostic — it takes the directory to contain
against as a parameter. Its **messages** are not: all five `UsageError` strings hardcode the
literal `--findings-file`, and there is no label parameter.

Reuse without the label would make `state-artifact --path ../escape.md` exit 2 **naming a
flag the user never passed**, violating the message shape in `00-core-definitions.md` §8.2
and REQ-OBS-01's requirement that a diagnostic identify which behavior broke.

### 3.3 The five messages, with `{label}` substituted

Each of the five `raise UsageError(...)` sites replaces the hardcoded `--findings-file`
with the `label` parameter. **No other token in any message changes** — not the punctuation,
not the `!r` quoting, not the `(feature directory ({target_dir}))` parenthetical, not the
implicit-concatenation line breaks.

| # | Branch | Condition | Message template |
|---|---|---|---|
| 1 | empty | `not value` | `{label} must not be empty` |
| 2 | control character | any `ord(ch) < 32` or `ord(ch) == 127` | `{label} contains a control character ({bad!r}); expected a plain relative path` |
| 3 | absolute | `Path(value).is_absolute()` | `{label} {value!r} is absolute; it must be relative to the feature directory ({target_dir})` |
| 4 | `..` segment | `".." in Path(value).parts` | `{label} {value!r} contains a '..' segment; it must stay inside the feature directory ({target_dir})` |
| 5 | resolved escape | `resolved == root or root not in resolved.parents` | `{label} {value!r} escapes the feature directory ({target_dir}); refusing to record it` |

**Byte-for-byte default preservation.** With `label` defaulting to `"--findings-file"`,
every message above renders **exactly** the string it renders today. Concretely, message 3
today is:

```python
        raise UsageError(
            f"--findings-file {value!r} is absolute; it must be relative to the "
            f"feature directory ({target_dir})"
        )
```

and after the edit:

```python
        raise UsageError(
            f"{label} {value!r} is absolute; it must be relative to the "
            f"feature directory ({target_dir})"
        )
```

For the default `label` the two produce identical bytes. Therefore:

- `cmd_state_verify`'s call site is **unchanged** — it stays
  `_validated_findings_file(findings_file, target_dir)`, the sole existing caller, passing
  two positional arguments and relying on the default.
- Every existing `--findings-file` test is **unchanged**, including any exact-stderr
  assertion.
- **This is not a behavior change for `state-verify`.** It is a signature widening whose
  observable output is identical.

### 3.4 The full edited helper

```python
def _validated_findings_file(
    value: str, target_dir: Path, label: str = "--findings-file"
) -> str:
    """Return ``value`` if it is a safe relative path inside ``target_dir``.

    ``findingsFile`` is defined as relative to the
    feature directory, and downstream consumers (forge-fix selecting the report)
    follow the stored value verbatim. So it gets the same fail-closed containment
    treatment as the write target itself (REQ-SEC-01): an absolute path, a ``..``
    segment, a NUL/control character, or a symlinked escape is rejected BEFORE any
    mutation rather than persisted for a later reader to resolve.

    The same containment contract governs every stored path a caller asserts is
    inside the feature directory, so the flag being validated is a parameter: the
    diagnostic must name the flag the user actually passed.

    Args:
        value: The candidate path, as supplied on the command line.
        target_dir: The resolved feature (or epic) directory it must sit inside.
        label: The flag to name in the error.

    Returns:
        The value unchanged, once validated.

    Raises:
        UsageError: Empty, absolute, ``..``-bearing, control-character-bearing, or
            escaping the target directory (→ exit 2).
    """
    if not value:
        raise UsageError(f"{label} must not be empty")
    bad = next((ch for ch in value if ord(ch) < 32 or ord(ch) == 127), None)
    if bad is not None:
        raise UsageError(
            f"{label} contains a control character ({bad!r}); "
            f"expected a plain relative path"
        )
    candidate = Path(value)
    if candidate.is_absolute():
        raise UsageError(
            f"{label} {value!r} is absolute; it must be relative to the "
            f"feature directory ({target_dir})"
        )
    if ".." in candidate.parts:
        raise UsageError(
            f"{label} {value!r} contains a '..' segment; it must stay inside "
            f"the feature directory ({target_dir})"
        )
    root = target_dir.resolve()
    resolved = (target_dir / candidate).resolve()
    if resolved == root or root not in resolved.parents:
        raise UsageError(
            f"{label} {value!r} escapes the feature directory ({target_dir}); "
            f"refusing to record it"
        )
    return value
```

The only differences from the current source are: the third parameter, the `Args:` entry for
it, one added intent-only docstring paragraph, and `--findings-file` → `{label}` in five
places. The control flow, the branch conditions, the `.resolve()` call, and the return value
are untouched.

### 3.5 The `cmd_state_artifact` call site — exact

```python
    state_path, state = _load_state_for_write(specs_dir, feature, epic)
    target_dir = state_path.parent
    for path in paths:
        _validated_findings_file(path, target_dir, label="--path")
    entry = _stage_entry(state, stage)
    artifacts = entry.setdefault("artifacts", [])
    for path in paths:
        if path not in artifacts:
            artifacts.append(path)
    return _commit_state(state_path, state)
```

`label` is passed **as a keyword**, so the call reads as a labelled validation rather than a
third positional whose meaning must be looked up.

**Placement rationale (`00-core-definitions.md` §7.3).** Unlike `--version`, this validation
runs **after** the load, because its containment target is `state_path.parent` — a value only
`_load_state_for_write` produces. `_load_state_for_write` **only reads**; it does not write,
and it raises rather than repairing a corrupt file. So the fail-closed property still holds:
nothing is mutated before validation.

**Docstring change.** `cmd_state_artifact`'s `Raises:` gains the new rejection:

```python
    Raises:
        UsageError: A ``--path`` that is empty, absolute, ``..``-bearing,
            control-character-bearing, or escaping the feature directory; an
            unknown feature directory, an unparseable state file, or a failed
            atomic write (→ exit 2).
```

### 3.6 Properties this placement guarantees

1. **All paths are validated before any path is appended.** The validation loop is a
   separate, complete pass ahead of the append loop. `--path` is `action="append"`, so a
   single invocation may carry several values; a rejected value anywhere in the list means
   **no** value is appended and the state file is left **byte-identical**. Interleaving
   validation into the append loop would leave earlier paths staged in the in-memory dict —
   never committed, since `_commit_state` is not reached, but the separation is specified so
   the safe variant is not left to inference.
2. **The stored value is unchanged on the success path.** `_validated_findings_file` returns
   the **original unresolved string**, and the call site **discards the return value** — the
   append loop still appends `path`, not a resolved or normalised form. Therefore **no
   migration, no rewrite of existing state, and no change to any success-path output.**
3. **A symlinked escape is caught.** The helper calls `.resolve()` on both the target
   directory and the candidate, so a path that is textually innocent but resolves outside
   the feature directory through a symlink is rejected by branch 5.
4. **Five branch-specific messages, not one generic message.** Each rejection names *which*
   containment rule was broken. A single "invalid path" message would satisfy the letter of
   REQ-SEC-01 and fail REQ-OBS-01.
5. **De-duplication semantics are untouched.** The idempotent "already-tracked path is a
   no-op" behavior and the `updatedAt` refresh on the all-duplicates branch are unchanged.

### 3.7 The relative/absolute concern does not apply

Both flags are feature-dir-relative **by contract**, as their own `help=` strings state
(verified in the argparse setup):

| Flag | `help=` string |
|---|---|
| `--path` | `Artifact path relative to the feature dir (repeatable)` |
| `--findings-file` | `Findings document, relative to and contained by the feature directory (required by findings-reported)` |

Neither help string changes. The adaptation is the defaulted `label` parameter plus the
validation loop; **nothing about the containment semantics changes**, and no flag acquires a
new meaning.

> **Position for `05-coverage-backfill.md`.** The REQ-COV-06 test asserts (a) at least one
> rejecting branch exits 2 naming `--path` and **not** `--findings-file`, (b) the state file
> is byte-identical after a rejection, including when the rejected value is one of several
> repeated `--path` values, and (c) a legitimate relative path is still stored verbatim.

### 3.8 Naming — deliberately out of scope

`_validated_findings_file` keeps its name despite gaining a second, non-findings caller.

A rename touches every call site and every test that names it, for **no behavioral gain**.
Recorded as an **open position with a decision** (tech-spec §10.2 item 1,
`00-core-definitions.md` §7.2) so a later round resolves it against this position under C-04
rather than filing it as a finding.

## 4. REQ-FIX-02 — disposition: a candidate defect was investigated and DISPROVED

REQ-FIX-02 requires that a defect surfaced by the REQ-COV-01..07 work be **fixed**, not
pinned as golden. One candidate was raised and investigated. **It is not a defect.**

### 4.1 The claim, and why it does not hold

**The claim.** `row["epic"]` — the state file's `epic` field — flows unvalidated into a path
join of the form `specs_dir / row["epic"] / name`, so a traversal segment in an on-disk
state file could steer a read outside the specs tree.

**It does not.** The epic name in every scan row is derived from the **parent directory
enumerated off disk**, not from any state file's `epic` field. Verified in `_scan_features`:

```python
def _scan_features(specs_dir: Path) -> list[tuple[str, str | None, dict]]:
    ...
    for top in sorted(p for p in specs_dir.iterdir() if p.is_dir()):
        flat_state = top / PIPELINE_STATE_FILENAME
        if flat_state.is_file():
            out.append((top.name, None, _read_state(flat_state)))
        # Descend one level for nested epic members (skip the epic root itself).
        for child in sorted(p for p in top.iterdir() if p.is_dir()):
            nested_state = child / PIPELINE_STATE_FILENAME
            if nested_state.is_file():
                out.append((child.name, top.name, _read_state(nested_state)))
    return out
```

The epic slot of each tuple is `top.name` — the `.name` of a `Path` yielded by
`specs_dir.iterdir()`. It is a **real directory name by construction**: a single path
component that exists on disk, which cannot be `..`, cannot contain a separator, and cannot
carry a traversal segment. The state file's own `epic` field is never consulted here; it
travels only inside the third tuple element, the state dict.

> A function named `_derive_epic` **does not exist** in `scripts/forge-session.py`. If a
> later round searches for it, that is why.

### 4.2 The real surface — already guarded

The on-disk `epic` **field** *is* read, in `stage_exit`, and used for routing. It is already
name-checked:

```python
    epic_name = epic or state.get("epic")
    # The epic a documentation or completed-loop exit routes against:
    # the explicit `--epic`, else the state's back-pointer. A back-pointer is
    # untrusted on-disk data, so it is name-checked here rather than reaching the
    # helper's argv (REQ-SEC-01); an unusable value degrades to the standalone route
    # rather than crashing a stage closing. `--epic` itself was already validated in
    # step 1.
    route_epic = (
        epic_name if isinstance(epic_name, str) and SAFE_NAME_RE.match(epic_name) else None
    )
```

with

```python
SAFE_NAME_RE: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
```

An unsafe value — a non-string, or any string failing that kebab-case pattern — degrades
`route_epic` to `None`, which is the **standalone route**. A stage closing does not crash;
it routes as if the feature had no owning epic.

**This is correct existing behavior, and it is what REQ-COV-07 covers as a test** (owned by
`05-coverage-backfill.md`).

### 4.3 The residual — recorded, deliberately not changed

`route_epic` is the validated value that drives routing. The **unvalidated** `epic_name` is
still interpolated into the printed reconcile command:

```python
    if open_requests and epic_name:
        reconcile_command = f"/feature-forge:forge-0-epic {epic_name}"
```

**Position: not changed by this feature.** The reasoning:

- It is a **display string**. It is placed into the payload's `epicReconcile.command` and
  rendered for the user to read; it is never joined into a path and never passed as argv by
  this script.
- It **fails closed, just later**. If the user runs the printed command, the epic resolver
  rejects an unsafe name at exit 2. The failure mode is a confusing suggestion, not an
  unsafe operation.
- Changing it would touch `stage_exit`'s payload, which is **heavily golden-file tested**.
  The churn risk is unjustifiable against REQ-TRIAL-02's convergence requirement and
  REQ-TRIAL-03's ≤2-round guideline, for no change in reachable behavior.

Recorded as an **open position with a decision** (tech-spec §10.2 item 2) so a later round
resolves it under C-04.

> **Position for `05-coverage-backfill.md`.** The REQ-COV-07 test asserts the
> **degradation only** — that an on-disk `epic` failing `SAFE_NAME_RE` produces the
> standalone route and a successful exit. It **MUST NOT** pin the reconcile-command
> interpolation as golden. Pinning it would freeze behavior this document has explicitly
> declined to endorse, which is precisely what REQ-FIX-02's note warns against.

### 4.4 Conclusion

**REQ-FIX-02 adds no implementation work.** The candidate was disproved (§4.1), the real
surface is already guarded (§4.2), and the one residual is recorded with a decision rather
than pinned as golden (§4.3).

**The behavior changes in this feature remain exactly the two named in PRD §3.3:**
REQ-FIX-01 (§2) and REQ-SEC-01 (§3). If the backfill work in `05-coverage-backfill.md`
surfaces a genuinely new defect, REQ-FIX-02 reopens and this section is amended — it is not
a closed door, it is a recorded null result.

## 5. REQ-COV-03 — the eval prelude criterion key-set pin

### 5.1 The corrected premise (resolves OQ-03)

PRD v1 stated that `resolver_line_identical` "is currently computed and never checked".
**That premise was wrong, and PRD v2 corrects it.** Verified in
`eval/run-compliance-eval.py`:

```python
def score_prelude(transcript: dict) -> dict[str, bool]:
    """Score the command the model actually ran against the byte-pinned prelude."""
    ...
    return {
        "attempted_resolver": attempted,
        "byte_identical": byte_identical,
        "resolver_line_identical": resolver_line_identical,
        "functionally_equivalent": functional,
    }
```

and in `_to_result`, which consumes every scorer's output:

```python
    criteria = scorer(transcript)
    ...
    return RunResult(
        ...
        compliant=all(criteria.values()),
        criteria=criteria,
        ...
    )
```

`resolver_line_identical` is one of four keys ANDed into `compliant`. It is **fully
load-bearing** for a prelude run's compliance flag. **OQ-03 is resolved: it already asserts
equality, and nothing about its role changes.**

### 5.2 The real gap — narrower

Probe 3 (branch path) pins its criterion key set at module scope in
`eval/run-compliance-eval.py`:

```python
#: The exact criteria `score_branch_path` reports. Declared once so the scorer,
#: the report, and the tests all name the same set — a criterion silently added or dropped
#: would change what "compliant" means without changing any assertion.
BRANCH_CRITERIA: Final[tuple[str, ...]] = (
    "ordered_command_results",
    "all_commands_succeeded",
    "exactly_one_sentinel",
    "nested_steps_emitted_no_sentinel",
    "nothing_after_sentinel",
    "next_command_fenced",
    "block_verbatim",
    "correct_rejoin_or_recovery",
    "escalation_digest_presented",
)
```

and `tests/test_compliance_eval.py` holds its own **independent second copy**,
`SPEC_BRANCH_CRITERIA`, asserted **two-sidedly**:

```python
def test_the_scorer_returns_exactly_the_nine_specified_criteria(
    branch_fixture: dict, branch_truth: dict[str, dict]
) -> None:
    criteria = _score_run(branch_fixture, branch_truth, "successful-rejoin")
    assert tuple(criteria) == SPEC_BRANCH_CRITERIA
    assert ce.BRANCH_CRITERIA == SPEC_BRANCH_CRITERIA
```

The first assertion pins the scorer's **runtime output**; the second pins the module's
**declared constant**. Comparing the module constant against itself would be vacuous — the
independent copy is what makes a silently added or dropped criterion fail.

**Probe 2 (prelude) has no equivalent constant.** A criterion could be added to or dropped
from `score_prelude`'s returned dict and nothing would fail, while `all(criteria.values())`
would silently mean something different.

### 5.3 Decision

Add a module-scope constant to `eval/run-compliance-eval.py`, mirroring `BRANCH_CRITERIA` in
shape, placement style, and comment style, declared adjacent to `score_prelude`:

```python
#: The exact criteria `score_prelude` reports. Declared once so the scorer, the
#: report, and the tests all name the same set — a criterion silently added or dropped
#: would change what "compliant" means without changing any assertion.
PRELUDE_CRITERIA: Final[tuple[str, ...]] = (
    "attempted_resolver",
    "byte_identical",
    "resolver_line_identical",
    "functionally_equivalent",
)
```

The tuple order is the **key insertion order of `score_prelude`'s returned dict**, so a
`tuple(criteria) == PRELUDE_CRITERIA` comparison is meaningful rather than order-insensitive
by accident.

`Final` is already imported in that module (`BRANCH_CRITERIA` and `EXIT_COMMAND_TOKENS` both
use it), so this adds **no import**.

**`score_prelude` itself is not modified.** The constant is a declaration; making the scorer
build its dict from the tuple would couple the two in a way that lets one drift silently
past the other, which is the opposite of the pin's purpose — the same reason
`score_branch_path` does not build its dict from `BRANCH_CRITERIA`.

### 5.4 Scope boundaries

**Probe 1 (stage-exit, `score_stage_exit`) is OUT OF SCOPE.** REQ-COV-03 names the
**prelude** criterion key set only, and PRD §6 freezes the compliance eval beyond what
REQ-COV-03 requires. Adding a `STAGE_EXIT_CRITERIA` constant would be a scope expansion into
a frozen surface. Recorded as a declared non-goal in `00-core-definitions.md` §10.3 so a
verifier resolves it against a position under C-04 rather than filing it.

**NO fixture changes.** Nothing under `eval/` other than the one constant in
`run-compliance-eval.py` is touched. `01-architecture-layout.md` §2 lists every `eval/`
fixture as not-touched, and §9 makes their absence from the diff a verification item.

**No scorer behavior changes.** `score_prelude` returns the same four keys with the same
values; `_to_result` computes the same `compliant` flag. This edit is unobservable to any
eval run.

> **Position for `05-coverage-backfill.md`.** The REQ-COV-03 test lands in
> `tests/test_compliance_eval.py` and mirrors the **two-sided** pattern above against its own
> independent copy of the four keys — one assertion against `tuple(criteria)` from a real
> `score_prelude` call, one against `ce.PRELUDE_CRITERIA`. A one-sided assertion, or one that
> imports the constant instead of copying it, is vacuous.

## 6. Error Handling and API

### 6.1 Exit-code contract — preserved

`scripts/forge-session.py` is **0 / 2 only — never 1** (`00-core-definitions.md` §8.1).
Both new rejections raise the existing `UsageError`:

```python
class UsageError(Exception):
    """A usage or I/O failure that must exit 2."""
```

and reach the existing top-level handler unchanged:

```python
    except UsageError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
```

Therefore:

- **No new exception type** is introduced.
- **No `try`/`except`** is added around either validation — they propagate.
- **Stdout is empty** on both rejections; the message is a single plain `Error:` line on
  stderr.
- The never-1 property is protected by REQ-BRIT-05's widened guard
  (`06-brittleness-batch.md`).

### 6.2 Message shape

The established shape (`00-core-definitions.md` §8.2):

```
{flag} {reason}; {context or corrective action}
```

with the offending value quoted using `!r`. Both new rejections conform without inventing
wording: §2's message is `_require_positive_int`'s existing template with `label`
`"--version"`, and §3's are `_validated_findings_file`'s five existing templates with
`label` `"--path"`.

### 6.3 The two CLI transcripts

```
$ python3 scripts/forge-session.py state-complete \
    --feature f --stage forge-2-tech --version 0 --specs-dir ./specs
Error: --version must be a positive integer; got 0
$ echo $?
2
```

```
$ python3 scripts/forge-session.py state-artifact \
    --feature f --stage forge-3-specs --path ../escape.md --specs-dir ./specs
Error: --path '../escape.md' contains a '..' segment; it must stay inside the feature directory (specs/f)
$ echo $?
2
```

In both cases stdout is empty and `specs/f/.pipeline-state.json` is byte-identical to its
pre-invocation contents.

The second transcript shows **branch 4 of five**. The other four branches render:

| Invocation fragment | stderr |
|---|---|
| `--path ""` | `Error: --path must not be empty` |
| `--path $'a\tb.md'` | `Error: --path contains a control character ('\t'); expected a plain relative path` |
| `--path /etc/passwd` | `Error: --path '/etc/passwd' is absolute; it must be relative to the feature directory (specs/f)` |
| `--path link-out/x.md` (symlink escaping) | `Error: --path 'link-out/x.md' escapes the feature directory (specs/f); refusing to record it` |

`({target_dir})` renders the `state_path.parent` produced by `_load_state_for_write` — the
resolved feature directory as constructed from `--specs-dir`, `--feature`, and `--epic`.

### 6.4 Failure modes summary

| Operation | Failure | Handling | Exit | State file |
|---|---|---|---|---|
| `state-complete` | `--version < 1` (or a non-`int`/`bool` in-process) | `UsageError` from `_require_positive_int`, **before** the load | 2 | untouched — not even read for mutation |
| `state-complete` | contradictory `--resumable --status complete` | existing `UsageError`, **before** the version check | 2 | untouched |
| `state-artifact` | any `--path` failing any of the five branches | `UsageError` from `_validated_findings_file`, **after** the load, **before** any append | 2 | byte-identical — the load only reads |
| `state-artifact` | corrupt/absent-dir/non-object state | existing `UsageError` from `_load_state_for_write`, before the path loop | 2 | byte-intact |
| `state-verify` | `--findings-file` failing any branch | unchanged — same five messages, byte-identical | 2 | byte-identical |
| `score_prelude` | — | none; §5's constant is a declaration and raises nothing | — | — |

## 7. Data Model — the narrowed accepted domains

**No persisted structure changes.** `.pipeline-state.json` conforms to
`references/pipeline-state-schema.json` exactly as today. **No field is added, removed, or
retyped. No migration is required.**

Two **accepted-input domains** narrow (`00-core-definitions.md` §7):

| Input | Domain before | Domain after | Enforced by |
|---|---|---|---|
| `state-complete --version` | any `int` (argparse `type=int`) | `int >= 1` — matches the read path's existing domain | `_require_positive_int` (§2.4) |
| `state-artifact --path` | any string | relative, no `..` segment, no control characters, resolves strictly inside the feature dir | `_validated_findings_file` (§3.5) |

### 7.1 Both narrow only the REJECTED set

This is the property that makes the change safe and migration-free:

- **Every value accepted before that is still accepted is stored byte-identically.**
  `--version` is written as the same integer; `--path` is appended as the **original
  unresolved string** the validator returns (§3.6 property 2).
- **No existing valid state file is affected.** Nothing re-reads, re-validates, or rewrites
  stored values. A state file already containing `"version": 0` from before this change
  keeps loading through `_read_state` and `_load_state_for_write` unmigrated — the read-path
  rejection it already triggers at `_current_artifact_version` is pre-existing behavior, not
  something this change introduces or worsens.
- **No migration, no schema version bump, no backfill script.**

### 7.2 What is newly rejected

| Value | Before | After |
|---|---|---|
| `--version 1` and above | accepted, written | accepted, written — **unchanged** |
| `--version 0`, `--version -5` | **accepted, written** | **rejected, exit 2** |
| `--version 0` on the commit-2 / `--resumable` paths | accepted, discarded | **rejected, exit 2** (§2.5 — intentional) |
| `--path docs/report.md` | accepted, appended | accepted, appended — **unchanged** |
| `--path ../escape.md`, `--path /abs/x`, `--path ""`, control chars, symlink escape | **accepted, appended** | **rejected, exit 2** |
| `--findings-file <anything>` | — | **unchanged in every branch** |

## 8. Dependencies

### 8.1 Spec documents that must be read first

| Document | For |
|---|---|
| `00-core-definitions.md` | §7 validator contracts and placement table; §8 error contract, exit codes, message shape, REQ-OBS-01; §7.1's `_positive_int` naming correction; §10.3 declared non-goals |
| `01-architecture-layout.md` | §3.2 this document's file ownership; §5.2 step 2 (this lands **before** every test change); §7 gate list |

### 8.2 Documents that depend on this one

`05-coverage-backfill.md` — REQ-COV-02 tests REQ-FIX-01, REQ-COV-06 tests REQ-SEC-01, and
REQ-COV-03's test asserts against §5's constant. **The validations must land before those
tests are written**, so they are written against real behavior rather than intended
behavior (`01-architecture-layout.md` §5.2 step 2). REQ-COV-05 and REQ-COV-07 depend on the
positions recorded in §2.5 and §4.3.

### 8.3 Code dependencies — all pre-existing

| Symbol | File | Signature / value as verified today | Role here |
|---|---|---|---|
| `_require_positive_int` | `scripts/forge-session.py` | `(value: object, label: str) -> int` | called by §2.4; **unchanged** |
| `_validated_findings_file` | `scripts/forge-session.py` | `(value: str, target_dir: Path) -> str` | **gains** `label: str = "--findings-file"` (§3.2) |
| `_assert_full_commit_hash` | `scripts/forge-session.py` | `(commit_hash: object) -> None` | placement precedent for §2.4 |
| `_load_state_for_write` | `scripts/forge-session.py` | `(specs_dir: Path, feature: str, epic: str \| None) -> tuple[Path, dict]` | read-only strict load; produces `target_dir` for §3.5 |
| `_read_state` | `scripts/forge-session.py` | `(state_path: Path) -> dict` | tolerant read; unchanged, cited in §4.1 |
| `_commit_state` | `scripts/forge-session.py` | `(state_path: Path, state: dict) -> dict` | the only writer; never reached on a rejection |
| `_cascade_staleness` | `scripts/forge-session.py` | `(state: dict, completed_stage: str, new_version: int) -> list[str]` | downstream consumer of `version` (§2.1); unchanged |
| `_scan_features` | `scripts/forge-session.py` | `(specs_dir: Path) -> list[tuple[str, str \| None, dict]]` | §4.1 — epic name from `iterdir()` |
| `SAFE_NAME_RE` | `scripts/forge-session.py` | `re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")` | §4.2 |
| `UsageError` | `scripts/forge-session.py` | `class UsageError(Exception)` | both rejections |
| `cmd_state_verify` | `scripts/forge-session.py` | sole existing caller of `_validated_findings_file` | §3.3 — call site unchanged |
| `score_prelude` | `eval/run-compliance-eval.py` | `(transcript: dict) -> dict[str, bool]` | §5 — unchanged |
| `_to_result` | `eval/run-compliance-eval.py` | computes `compliant=all(criteria.values())` | §5.1 |
| `BRANCH_CRITERIA` | `eval/run-compliance-eval.py` | `Final[tuple[str, ...]]`, nine keys | §5.2 — the pattern to mirror |

**External packages: none added.** `Final` and `Path` are already imported in their
respective modules. Python 3.10+ as already required.

## 9. Verification

Confirm an implementation matches this document:

**REQ-FIX-01 (§2)**

- [ ] `cmd_state_complete` calls `_require_positive_int(version, "--version")`
      **unconditionally**, after the `--resumable --status complete` guard and **before**
      `_load_state_for_write`.
- [ ] `_require_positive_int`'s own body and signature are **unmodified**.
- [ ] `state-complete --version 0` exits 2 with exactly
      `Error: --version must be a positive integer; got 0` on stderr, empty stdout.
- [ ] The state file is **byte-identical** after that rejection.
- [ ] `state-complete --version 1` still succeeds and still writes `"version": 1`.
- [ ] `state-complete --commit-hash <40-hex> --version 0` exits 2 (§2.5, intentional).
- [ ] `state-complete --resumable --status complete --version 1` still reports the
      contradiction message, not a version message.
- [ ] `cmd_state_complete`'s docstring `Raises:` names the `--version` rejection; no other
      docstring line changed.

**REQ-SEC-01 (§3)**

- [ ] `_validated_findings_file` has the three-parameter signature with
      `label: str = "--findings-file"`.
- [ ] All five `UsageError` messages use `{label}`; **no other token** in any of the five
      changed.
- [ ] Every existing `--findings-file` message is **byte-identical** — the `state-verify`
      tests pass unmodified, and `cmd_state_verify`'s call site is untouched.
- [ ] `cmd_state_artifact` computes `target_dir = state_path.parent` and validates **every**
      path in a **separate loop before** the append loop, passing `label="--path"`.
- [ ] `state-artifact --path ../escape.md` exits 2 naming **`--path`**, never
      `--findings-file`.
- [ ] A rejected path among several repeated `--path` values leaves the state file
      **byte-identical** — no earlier path is recorded.
- [ ] A legitimate relative path is stored **verbatim** (unresolved, unnormalised).
- [ ] All five rejection branches are reachable through `--path` and each emits its own
      branch-specific message.
- [ ] `_validated_findings_file` is **not renamed** (§3.8).

**REQ-FIX-02 (§4)**

- [ ] `_scan_features` is **unmodified** — its epic name still comes from `top.name`.
- [ ] `stage_exit`'s `route_epic` guard and `SAFE_NAME_RE` are **unmodified**.
- [ ] The `f"/feature-forge:forge-0-epic {epic_name}"` interpolation is **unmodified**, and
      no test in the suite pins it as golden.
- [ ] The diff contains **exactly two** shipped-behavior changes to `scripts/forge-session.py`
      — no third.

**REQ-COV-03 (§5)**

- [ ] `PRELUDE_CRITERIA: Final[tuple[str, ...]]` exists at module scope in
      `eval/run-compliance-eval.py` with the four keys in `score_prelude`'s dict-insertion
      order.
- [ ] `score_prelude` is **unmodified** and does not build its dict from the constant.
- [ ] No `STAGE_EXIT_CRITERIA` (probe-1) constant is added.
- [ ] **No file under `eval/` other than `run-compliance-eval.py` appears in the diff.**

**Cross-cutting**

- [ ] `scripts/forge-session.py` still has **no** `return 1` / `sys.exit(1)` path; both new
      rejections reach the existing `except UsageError` handler.
- [ ] No new exception type, `try`/`except`, CLI verb, flag, exit code, or payload key
      appears in the diff **for `scripts/forge-session.py` or `eval/run-compliance-eval.py`**
      — the two files this document owns. `scripts/validate-traceability.py` is outside that
      ownership and does add a flag and two payload keys; see
      `01-architecture-layout.md` §3.4.
- [ ] No `help=` string changed.
- [ ] `.pipeline-state.json`'s schema is unchanged and no migration code exists.
- [ ] `ruff check scripts/ eval/` is clean.
- [ ] No comment or docstring added by this document's edits carries a count, a
      "measured"/"confirmed" claim, or any other empirical assertion (REQ-CANON-03).
