# 05 — Coverage Backfill

> The seven untested production behaviors named in PRD §3.3 (R-12). This document adds
> **tests only** — it changes no shipped behavior. The two behavior changes its tests
> assert against (`--version` domain, `--path` containment) belong to
> `04-production-validations.md` and must land first (§10).
>
> Locate every symbol by **name**, never by line number (C-07). Line numbers in this suite
> are as-of-authoring hints and are expected to drift.

## Requirement Coverage

| REQ ID | Requirement | Host file | Section |
|---|---|---|---|
| REQ-COV-01 | Corrupt state × autoVerify on/off (tolerant-read vs strict-debt-write asymmetry) | `tests/test_auto_verify.py` | §2 |
| REQ-COV-02 | `--version` domain on `state-complete` | `tests/test_state_verbs.py` | §3 |
| REQ-COV-03 | Prelude criterion key-set pin | `tests/test_compliance_eval.py` | §4 |
| REQ-COV-04 | Debt-write idempotency at the same revision, byte level | `tests/test_auto_verify.py` | §5 |
| REQ-COV-05 | Commit-2 path ignores conflicting flags | `tests/test_state_verbs.py` | §6 |
| REQ-COV-06 | `state-artifact --path` containment | `tests/test_state_verbs.py` | §7 |
| REQ-COV-07 | Unsafe on-disk `epic` back-pointer degradation | `tests/test_stage_exit.py` | §8 |
| REQ-FIX-02 | Disposition: no defect beyond REQ-FIX-01/REQ-SEC-01 | — | §9 |

Nothing outside `REQ-COV-01..07` (plus REQ-FIX-02's disposition) is in this document's
scope. `REQ-FIX-01` and `REQ-SEC-01` are **specified** in `04-production-validations.md`;
this document only **tests** them.

---

## 1. The Placement Map

### 1.1 The map

This table is the audit trail a verifier checks against. The backfill is **not one file** —
it is **ten named tests across four host files**, covering the seven gaps, so the map is the
deliverable that makes "each of the seven gaps has a named test" (REQ-QUAL-04) checkable.

| Req | Behavior | Host file | Named test(s) |
|---|---|---|---|
| REQ-COV-01 | corrupt state × autoVerify on/off | `tests/test_auto_verify.py` | `test_a_corrupt_state_file_exits_2_with_no_payload_when_auto_verify_is_on`, `test_a_corrupt_state_file_closes_the_stage_normally_when_auto_verify_is_off` |
| REQ-COV-02 | `--version` domain | `tests/test_state_verbs.py` | `test_state_complete_rejects_a_non_positive_version_before_mutation` |
| REQ-COV-03 | prelude criterion key-set pin | `tests/test_compliance_eval.py` | `test_the_prelude_scorer_returns_exactly_the_four_specified_criteria` |
| REQ-COV-04 | debt-write idempotency (byte level) | `tests/test_auto_verify.py` | `test_a_pending_marker_at_the_current_revision_is_left_byte_identical` (plus the existing `test_repeated_stage_exit_at_the_same_revision_is_byte_idempotent`, §5.2) |
| REQ-COV-05 | commit-2 ignores conflicting flags | `tests/test_state_verbs.py` | `test_commit_2_ignores_based_on_artifact_and_preserve_commit_hash` |
| REQ-COV-06 | `--path` containment | `tests/test_state_verbs.py` | `test_state_artifact_rejects_an_unsafe_path_before_mutation`, `test_state_artifact_rejects_a_path_that_escapes_through_a_symlink`, `test_state_artifact_rejects_the_whole_batch_when_one_repeated_path_is_unsafe` |
| REQ-COV-07 | unsafe epic back-pointer degradation | `tests/test_stage_exit.py` | `test_an_unsafe_epic_back_pointer_degrades_to_the_standalone_route` |

This map is identical to `01-architecture-layout.md` §4.2 and `tech-spec.md` §8.1. If it
changes here, recompute both in the same edit (REQ-TRIAL-06).

### 1.2 Why each test lands where it does

Each test lands **beside existing coverage of the same subject** and **reuses that file's
own CLI wrapper**, because there is **no shared wrapper** (`00-core-definitions.md` §10.5).
`tests/conftest.py`'s `run_cli` fixture is hardcoded to `scripts/epic-manifest.py` and is
**not used by any file in scope** — it MUST NOT be used here, and no new shared helper may
be introduced.

The wrappers each new test reuses, verified in the host files:

| Host file | Module loader | Wrappers this document reuses |
|---|---|---|
| `tests/test_auto_verify.py` | `_load_module()` → `fs` | `_exit_project`, `_stage_exit`, `_exit_ok`, `_tech_state`, `_read_entry` |
| `tests/test_state_verbs.py` | `_load_forge_session()` → `FS` | `_run`, `_feature_dir`, `_seed`, `_state_of`, `_state_bytes`, `_FULL_HASH` |
| `tests/test_stage_exit.py` | `_load_session()` | `_project`, `_exit`, `_docs` |
| `tests/test_compliance_eval.py` | `_load_module()` → `ce` | `SPEC_BRANCH_CRITERIA` (as the shape to mirror) |

> **Wrapper-name correction, recorded.** The dispatch brief for this document named
> `_rank`, `_rank_proc`, `_write_state`, `_load_module`, and `_completed_prd_state` as the
> `tests/test_auto_verify.py` wrappers to reuse. Those exist, but they drive
> `rank-features` and the pure classifier helpers — **not** `stage-exit`. REQ-COV-01 and
> REQ-COV-04 are `stage-exit` behaviors, so they reuse that file's `stage-exit` wrappers
> instead: `_exit_project`, `_stage_exit`, `_exit_ok`, `_tech_state`, `_read_entry`, all
> defined under the `# Item 012 — the 03 §4.1 stage-exit scheduling boundary` section
> header of the same file. This is still "reuse the host file's own wrapper"; it is the
> correct wrapper within that file.
>
> Likewise, `tests/test_stage_exit.py`'s `_state_with_verify` and `_epic_project` are not
> used by §8: `_state_with_verify` seeds a *verify entry*, and `_epic_project` builds an
> epic-scoped fixture. REQ-COV-07's subject is a **member/standalone** state file carrying
> an unsafe `epic` back-pointer, which `_project(..., state=...)` expresses directly.

### 1.3 Sequencing

Per `01-architecture-layout.md` §5.4, this document's tests are **added before**
`06-brittleness-batch.md` rewrites existing tests in the three shared files
(`test_state_verbs.py`, `test_auto_verify.py`, `test_stage_exit.py`). Adding before
rewriting means `06`'s dedup pass sees the final set of functions and cannot leave a newly
added test outside a family it belongs to.

**Consequence for this document:** none of the tests below may be written as a hand-rolled
loop that `06` would then have to convert. Where a test covers several inputs it is written
with `@pytest.mark.parametrize` **from the start** (§7.2). Note that
`tests/test_state_verbs.py` does not import `pytest` today — `00-core-definitions.md` §10.5
requires the import to be added with the first decorator.

### 1.4 Narration rule (REQ-CANON-03)

Every docstring and comment specified below states **intent only**. No counts, no
"measured", no "confirmed", no empirical claims. The counts and verified behaviors in this
specification are spec content and MUST NOT be copied into the code.

---

## 2. REQ-COV-01 — Corrupt State × autoVerify On/Off

**Host file:** `tests/test_auto_verify.py`. **Wrappers:** `_exit_project`, `_stage_exit`,
`_tech_state`.

### 2.1 The verified current behavior

Two readers touch the same `.pipeline-state.json` during one `stage-exit`, and they
disagree about corruption on purpose.

**The tolerant read** — `stage_exit` classifies routing from it
(`scripts/forge-session.py`, in `stage_exit`: `state = _read_state(feature_dir /
PIPELINE_STATE_FILENAME)`):

```python
def _read_state(state_path: Path) -> dict:
    """Read a `.pipeline-state.json`, tolerating missing/corrupt files."""
    try:
        parsed = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}
```

**The strict read** — `_schedule_auto_verify_debt` reloads the same file through
`_load_verify_target` → `_load_state_for_write`, which refuses:

```python
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise UsageError(
                f"{state_path} exists but is not valid JSON ({exc}); refusing to "
                f"overwrite it. Fix or move the file, then re-run."
            ) from exc
```

The asymmetry is reached only when the debt write is reached, and that is gated on the
effective auto-verify:

```python
    auto_verify_debt_recorded = False
    if run_in_stage and verify_key is not None:
        _schedule_auto_verify_debt(specs_dir, feature, epic, route_stage, verify_key)
        auto_verify_debt_recorded = True
```

**The routing chain that makes the ON arm reach the write.** A corrupt file degrades to
`{}`. For a token-bearing stage, `_verify_state_for({}, "forge-2-tech")` returns the
label for an absent entry — `never`, not `none`; `none` is returned only for a **tokenless**
stage (`forge-6-docs`). So `resolved` is `False`, and with `autoVerify: true`,
`run_in_stage` is `True` and the debt write is reached.

| autoVerify | `_schedule_auto_verify_debt` reached? | Outcome on a corrupt file |
|---|---|---|
| **on** | yes | `UsageError` → **exit 2, no payload printed at all** |
| **off** | no | succeeds normally on `{}`-degraded defaults; file untouched |

Both arms are pinned as **golden** (`tech-spec.md` §3.9).

### 2.2 The recorded trade-off — read this before filing a finding

Testing the ON arm as golden **blesses an outcome where a corrupt state file makes
`stage-exit` unusable under auto-verify, with no payload explaining why.** That is stated
here deliberately.

The asymmetry is defensible on its own terms: the tolerant read only *classifies*, the
strict write *mutates*, and refusing to overwrite a corrupt state file is the fail-closed
convention every `state-*` verb already follows.

**Making the failure diagnostic was considered and REJECTED for this feature.** A
diagnostic failure changes `stage_exit`'s output contract, which is heavily golden-file
tested, and the churn risk is unjustifiable against REQ-TRIAL-02's convergence requirement
and REQ-TRIAL-03's ≤2-round guideline.

> This is **a candidate for later work, recorded with a position** — see `tech-spec.md`
> §10.2 item 3 and `00-core-definitions.md` §10.3. It is **not** a defect this feature
> leaves unfixed, and under C-04 it must not be re-filed as one.

### 2.3 The tests

Both arms are named tests. They land under the existing
`# Item 012 — the 03 §4.1 stage-exit scheduling boundary` section of
`tests/test_auto_verify.py`, beside `test_an_injected_write_failure_exits_2_with_no_dispatch_directive`,
which is the sibling that already pins "write failure → exit 2, no payload".

```python
def _corrupt(root: Path, feature: str = "widget") -> Path:
    """Overwrite a feature's state file with bytes that are not JSON.

    Args:
        root: The project root produced by ``_exit_project``.
        feature: The feature whose state file is corrupted.

    Returns:
        The path to the corrupted state file.
    """
    state_path = root / "specs" / feature / ".pipeline-state.json"
    state_path.write_text("{not json at all", encoding="utf-8")
    return state_path


def test_a_corrupt_state_file_exits_2_with_no_payload_when_auto_verify_is_on(
    tmp_path: Path,
) -> None:
    """REQ-COV-01: the debt write is strict where the routing read is tolerant.

    Routing classifies through the tolerant reader, so the exit reaches the
    scheduling boundary; the boundary reloads through the strict writer, which
    refuses to overwrite an unparseable file. The refusal is the whole payload:
    stdout carries nothing at all, and the file is left as it was found.
    """
    root = _exit_project(tmp_path, state=_tech_state())
    state_path = _corrupt(root)
    before = state_path.read_bytes()

    proc = _stage_exit(root, "--feature", "widget", "--stage", "forge-2-tech")

    assert proc.returncode == 2, proc.stdout
    assert not proc.stdout.strip(), "a refused exit must print no payload"
    assert "not valid JSON" in proc.stderr
    assert "refusing to overwrite" in proc.stderr
    assert state_path.read_bytes() == before


def test_a_corrupt_state_file_closes_the_stage_normally_when_auto_verify_is_off(
    tmp_path: Path,
) -> None:
    """REQ-COV-01: with auto-verify off the strict reload is never reached.

    Nothing is owed, so nothing is written, so the strict reader never runs and
    the corrupt file only degrades the routing snapshot to its defaults. The
    stage still closes, and the file is still left as it was found.
    """
    root = _exit_project(tmp_path, config={}, state=_tech_state())
    state_path = _corrupt(root)
    before = state_path.read_bytes()

    payload = _exit_ok(root, "--feature", "widget", "--stage", "forge-2-tech")

    directives = payload["directives"]
    assert directives["runInStageVerify"] is False
    assert directives["autoVerifyDebtRecorded"] is False
    assert state_path.read_bytes() == before
```

### 2.4 What a failure would mean

- **ON arm fails with exit 0 and a payload** — the strict reload has been replaced by a
  tolerant one, and a corrupt-but-recoverable state file is being atomically overwritten
  with a near-empty one at exit 0. This is the exact failure `_load_state_for_write`'s
  docstring exists to prevent.
- **ON arm fails with a payload on stdout alongside exit 2** — `runInStageVerify: True`
  with `autoVerifyDebtRecorded: False` has become reachable, which the scheduling-boundary
  contract states is unreachable.
- **OFF arm fails with exit 2** — the debt write has escaped its `run_in_stage` gate and now
  runs on every exit, meaning any corrupt file blocks every stage closing rather than only
  auto-verifying ones.

### 2.5 Error handling

Both arms are error-path tests. The ON arm asserts the `UsageError` → exit-2 contract of
`00-core-definitions.md` §8.1: exit 2, empty stdout, a plain `Error:` line on stderr. It
asserts on **diagnostic substrings** (`"not valid JSON"`, `"refusing to overwrite"`), not
on full stderr equality, satisfying REQ-OBS-01 (`00` §8.3) while staying clear of the
exact-stderr sites `06-brittleness-batch.md` is loosening.

---

## 3. REQ-COV-02 — The `--version` Domain on `state-complete`

**Host file:** `tests/test_state_verbs.py`. **Wrappers:** `_seed`, `_run`, `FS`.

**This test asserts a behavior that does not exist yet.** It tests **REQ-FIX-01**, which is
specified in `04-production-validations.md` §2 and must land first (§10).

### 3.1 The behavior under test

`04-production-validations.md` §2 requires `cmd_state_complete` to call
`_require_positive_int(version, "--version")` **unconditionally, before**
`_load_state_for_write`, mirroring `_assert_full_commit_hash`'s pre-load placement. The
validator already exists in `scripts/forge-session.py` and is reused verbatim
(`00-core-definitions.md` §7.1):

```python
def _require_positive_int(value: object, label: str) -> int:
    ...
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise UsageError(f"{label} must be a positive integer; got {value!r}")
    return value
```

Because validation runs **before** the load and nothing is mutated before it, a rejection
leaves the state file **byte-identical** (`00` §7.3).

The message, per `00` §8.2:

```
Error: --version must be a positive integer; got 0
```

### 3.2 The test

Lands in the `# state-complete` section of `tests/test_state_verbs.py`, beside
`test_state_complete_rejects_a_short_or_malformed_hash_before_mutation` — the sibling that
pins the other pre-load rejection.

```python
@pytest.mark.parametrize("raw", ["0", "-1"], ids=["zero", "negative"])
def test_state_complete_rejects_a_non_positive_version_before_mutation(
    tmp_path: Path, raw: str
) -> None:
    """REQ-COV-02 / REQ-FIX-01: the write domain matches the read domain.

    The read path already refuses a version below 1, so accepting one at the
    write path records a value that a later read must reject — poisoning the
    file at write time and failing at read time. The check runs before the state
    file is loaded, so a rejection leaves it byte-identical.
    """
    root = tmp_path / f"version-{raw}"
    _seed(root, {"forge-1-prd": {"status": "complete", "version": 1}})
    state_path = root / "specs" / "demo" / FS.PIPELINE_STATE_FILENAME
    before = state_path.read_bytes()

    result = _run(
        "state-complete", "--feature", "demo", "--stage", "forge-1-prd",
        "--version", raw, "--artifact", "PRD.md",
        "--specs-dir", str(root / "specs"),
    )

    assert result.returncode == 2, result.stdout
    assert result.stderr.strip() == (
        f"Error: --version must be a positive integer; got {raw}"
    )
    assert not result.stdout.strip(), "a refused write must print nothing"
    assert state_path.read_bytes() == before, "the rejected write must not mutate state"
```

**`tests/test_state_verbs.py` does not import `pytest` today** (`00-core-definitions.md`
§10.5). The `@pytest.mark.parametrize` decorators this document specifies for that file —
§3.2 above and §7.2's unsafe-path roster — therefore require `import pytest` to be added to
that module's import block; omitting it is a collection-time `NameError` that presents as
the whole file vanishing from the run. Because §1.3 sequences this document **before**
`06-brittleness-batch.md`, the import lands here, not there: `06` §10 lists the same
addition for REQ-BRIT-07, and whichever change lands first adds it once. Every other
module-level import these tests need (`json`, `subprocess`, `sys`, `Path`, `FS`,
`validate_state`) is already present.

### 3.3 Why the exact message, and why byte-identity

- **Exact message.** The dispatch contract for this test is "assert exit 2, the exact
  message, and that the state file is left byte-identical". `--version` is a **new**
  rejection, not one of the five exact-stderr sites `06-brittleness-batch.md` loosens
  (`00` §9.1), so pinning it exactly introduces no brittleness debt of the kind R-13
  removes: there is one message, one branch, and no incidental wording around it.
- **Byte-identity, not field comparison.** The point of pre-load placement is that
  *nothing* is touched — including `updatedAt`, which `_commit_state` refreshes on every
  successful write. A field-by-field comparison of the stage entry would pass even if the
  file had been rewritten with a refreshed `updatedAt`.

### 3.4 What a failure would mean

- **Exit 0** — REQ-FIX-01 has regressed or was never landed; `"version": 0` is again
  reachable on disk, and the next `state-verify` read of that file exits 2 with no
  indication of where the bad value came from.
- **Exit 2 but the bytes changed** — validation has moved *after* the load or *inside* the
  write branch, breaking the fail-closed property `00` §7.3 requires of both new
  validations.
- **Exit 2 with a different message** — the validator is no longer `_require_positive_int`,
  or is being called with a label other than `"--version"`, which would name a flag the
  user did not pass (the REQ-OBS-01 failure `00` §7.2 describes for `--path`).

### 3.5 Explicit non-assertion

This test does **not** assert anything about `--version` on the commit-2 or `--resumable`
paths. Those paths do not *write* the version, but argparse requires the flag on every
invocation, so validating unconditionally means they now reject `--version 0` too — which
is intentional (`04-production-validations.md` §2, `tech-spec.md` §3.7). §6.4 states the
matching non-assertion from the other side.

---

## 4. REQ-COV-03 — The Prelude Criterion Key-Set Pin

**Host file:** `tests/test_compliance_eval.py`. **Wrapper:** the module-level `ce` produced
by that file's `_load_module()`.

### 4.1 The verified current behavior

`score_prelude` in `eval/run-compliance-eval.py` returns exactly four keys:

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

All four are load-bearing: `_to_result` computes `compliant = all(criteria.values())`, so
every key ANDs into the run's compliance flag.

> **PRD v1's premise was superseded and PRD v2 adopted the correction.**
> `resolver_line_identical` is **not** "computed and never checked" — it is checked. The
> real gap is narrower: probe 3 (branch) pins its criterion key set with
> `BRANCH_CRITERIA`; probe 2 (prelude) has **no equivalent constant**, so a criterion could
> be dropped and silently change what "compliant" means. OQ-03 is resolved by this
> (`tech-spec.md` §3.13, PRD §7).

**Probe 1 (stage-exit) is explicitly out of scope** — REQ-COV-03 names the prelude
criterion only, and PRD §6 freezes the compliance eval beyond what REQ-COV-03 requires
(`00-core-definitions.md` §10.3).

### 4.2 The production-side constant

`04-production-validations.md` §5 owns the `eval/run-compliance-eval.py` edit: add

```python
#: The exact criteria `score_prelude` reports. Declared once so the scorer, the report,
#: and the tests all name the same set — a criterion silently added or dropped would
#: change what "compliant" means without changing any assertion.
PRELUDE_CRITERIA: Final[tuple[str, ...]] = (
    "attempted_resolver",
    "byte_identical",
    "resolver_line_identical",
    "functionally_equivalent",
)
```

mirroring the existing `BRANCH_CRITERIA` declaration in the same module. This document owns
only the test.

### 4.3 The test — the two-sided assertion, mirrored

The shape to mirror already exists in `tests/test_compliance_eval.py`:

```python
def test_the_scorer_returns_exactly_the_nine_specified_criteria(
    branch_fixture: dict, branch_truth: dict[str, dict]
) -> None:
    criteria = _score_run(branch_fixture, branch_truth, "successful-rejoin")
    assert tuple(criteria) == SPEC_BRANCH_CRITERIA
    assert ce.BRANCH_CRITERIA == SPEC_BRANCH_CRITERIA
```

with `SPEC_BRANCH_CRITERIA` declared in the test file as a **second, independent copy**.
That independence is the entire mechanism: **a test that imports the constant it pins
asserts nothing.** Comparing `ce.PRELUDE_CRITERIA` against itself is vacuous; comparing it
against a copy the test file owns is what makes a silently added or dropped criterion fail.

The new test lands beside the existing prelude-scorer tests
(`test_prelude_scorer_accepts_a_byte_identical_command` and its siblings):

```python
#: The four prelude criteria, spelled out here rather than imported. Comparing the module
#: constant against itself would be vacuous; this is the second, independent copy that
#: makes a silently added or dropped criterion fail.
SPEC_PRELUDE_CRITERIA = (
    "attempted_resolver",
    "byte_identical",
    "resolver_line_identical",
    "functionally_equivalent",
)


def test_the_prelude_scorer_returns_exactly_the_four_specified_criteria() -> None:
    """REQ-COV-03: pin probe 2's criterion key set the way probe 3's is pinned.

    Every key ANDs into the run's compliance flag, so dropping one silently
    widens what counts as compliant. Both sides are asserted: the scorer's live
    output and the module constant, each against this file's own copy.
    """
    command = f'{ce.BOOTSTRAP_PRELUDE}\npython3 "$R/scripts/forge-session.py" doctor --json'
    criteria = ce.score_prelude({"bash_commands": [command]})

    assert tuple(criteria) == SPEC_PRELUDE_CRITERIA
    assert ce.PRELUDE_CRITERIA == SPEC_PRELUDE_CRITERIA
```

The transcript shape `{"bash_commands": [...]}` is the one every existing prelude-scorer
test in that file uses; `score_prelude` reads only that key.

### 4.4 What a failure would mean

- **`tuple(criteria) != SPEC_PRELUDE_CRITERIA`** — `score_prelude`'s returned dict has
  gained, lost, renamed, or reordered a key. Any of those changes what
  `all(criteria.values())` means for every recorded run.
- **`ce.PRELUDE_CRITERIA != SPEC_PRELUDE_CRITERIA`** — the module constant and the scorer
  have drifted apart, which is exactly the drift the constant exists to make visible.

Both sides are required. Asserting only the first lets the constant rot; asserting only the
second lets the scorer rot.

### 4.5 Error handling

No error path. `score_prelude` is a pure function over a dict and raises nothing; a missing
`bash_commands` key defaults to `[]` inside the scorer. No fixture is touched — PRD §6
freezes `eval/` fixtures beyond this pin (`01-architecture-layout.md` §2).

---

## 5. REQ-COV-04 — Debt-Write Idempotency, at the Byte Level

**Host file:** `tests/test_auto_verify.py`. **Wrappers:** `_exit_project`, `_exit_ok`,
`_tech_state`, `_read_entry`.

### 5.1 The verified current behavior

`_schedule_auto_verify_debt` early-returns when the prior entry is already
`auto-verify-pending` at the current revision:

```python
    prior = _verify_entry(state, verify_key)
    if (
        prior.get("status") == "auto-verify-pending"
        and _scheduled_stage_version(prior) == current
    ):
        return
    state.setdefault("stages", {})[verify_key] = _verify_result_entry(
        "auto-verify-pending", prior, current, None, None, _now_iso()
    )
    _commit_state(state_path, state)
```

Three facts follow from the position of that `return`, and all three are load-bearing:

1. It returns **before `_commit_state`**, so nothing is written — `scheduledAt`, top-level
   `updatedAt`, and the file bytes are all untouched.
2. It returns **before `_now_iso()` is evaluated** — `_now_iso()` is an argument to
   `_verify_result_entry` on the line *after* the return, so on the early-return path it is
   never called at all.
3. The guarantee therefore holds **by construction, not by timestamp coincidence.** A test
   that merely observed two identical timestamps could be passing because the two runs
   happened inside the same clock second.

### 5.2 What already exists, and what is missing

`tests/test_auto_verify.py` already contains a named byte-level test for the **repeat-exit**
arm:

```python
def test_repeated_stage_exit_at_the_same_revision_is_byte_idempotent(
    tmp_path: Path,
) -> None:
    """REQ-REL-01: no `_commit_state`, so `scheduledAt` AND `updatedAt` hold still."""
    root = _exit_project(tmp_path, state=_tech_state())
    state_file = root / "specs" / "widget" / ".pipeline-state.json"

    _exit_ok(root, "--feature", "widget", "--stage", "forge-2-tech")
    first = state_file.read_bytes()
    for _ in range(2):
        _exit_ok(root, "--feature", "widget", "--stage", "forge-2-tech")
        assert state_file.read_bytes() == first
    ...
```

> **Finding, recorded rather than duplicated.** PRD §1 describes REQ-COV-01..07 as
> "seven behaviors on production paths with **no test at all**". For REQ-COV-04 that is not
> accurate against the current tree: the repeat-exit arm is already covered by the named
> test above, in exactly the host file `01-architecture-layout.md` §4.2 assigns to
> REQ-COV-04. **REQ-COV-04's "at least one named test" obligation is therefore already
> met by an existing function.**
>
> **Duplicating it is forbidden**, not merely unnecessary: a second copy of the same
> assertion is precisely the redundancy REQ-BRIT-07 exists to remove, and adding it in the
> same feature that removes it elsewhere would be self-contradictory.

**The arm that is genuinely uncovered** is the seeded-marker one. Every existing test
reaches the early-return by *writing* the marker first, in an earlier `stage-exit` of the
same test. None seeds an `auto-verify-pending` marker **at the current revision** on disk
and then runs a single exit against it:

- `test_a_pending_marker_for_an_older_revision_is_superseded` seeds a pending marker at an
  **older** revision — the supersede path, not the early-return path.
- `test_a_resolved_entry_prevents_rescheduling` seeds `passed`/`skipped` entries — the
  `resolved` gate upstream of the write, not the early return inside it.

That is the delta §5.3 adds.

### 5.3 The test

```python
def test_a_pending_marker_at_the_current_revision_is_left_byte_identical(
    tmp_path: Path,
) -> None:
    """REQ-COV-04: an already-owed debt at this revision is re-owed without a write.

    The scheduler returns before it commits and before it stamps a time, so a
    marker that already names the current revision survives the exit exactly as
    it sits on disk. Seeded rather than written by an earlier exit, so the
    early-return branch is the only thing that can make this pass.
    """
    root = _exit_project(tmp_path, state=_tech_state(
        {"status": "auto-verify-pending",
         "scheduledAt": "2020-01-01T00:00:00Z",
         "scheduledStageVersion": 2,
         "commitHash": None}
    ))
    state_file = root / "specs" / "widget" / ".pipeline-state.json"
    before = state_file.read_bytes()

    directives = _exit_ok(
        root, "--feature", "widget", "--stage", "forge-2-tech"
    )["directives"]

    assert directives["runInStageVerify"] is True
    assert directives["autoVerifyDebtRecorded"] is True
    assert state_file.read_bytes() == before, "the early return must not write"
    assert _read_entry(root)["scheduledAt"] == "2020-01-01T00:00:00Z"
```

`_tech_state()` seeds `forge-2-tech` complete at `version=2`, so
`scheduledStageVersion: 2` is the **current** revision and the early return is the branch
taken. The distinctive seeded `scheduledAt` makes the failure legible even before the byte
comparison is read (REQ-OBS-01).

### 5.4 Why byte level, stated explicitly

**A field-by-field comparison of the verify entry would pass even if `updatedAt` were
refreshed** — `updatedAt` is a *top-level* key stamped by `_commit_state`, not part of the
entry. Refreshing it is exactly the regression this test pins: a maintainer who moves the
early return below `_commit_state`, or replaces it with a "write the same values again"
no-op, produces a file whose every *entry* field is identical and whose top-level
`updatedAt` has moved. Only `read_bytes()` before and after catches that.

`autoVerifyDebtRecorded: True` is asserted alongside because the directive describes the
**obligation being on disk**, not a write having occurred. A repeat exit truthfully reports
`True` while writing nothing — that pairing is the contract, and asserting it here keeps a
future "fix" from making the directive lie in the other direction.

### 5.5 What a failure would mean

- **Bytes differ** — the early return has been removed, moved below `_commit_state`, or
  defeated by a change to `_scheduled_stage_version`'s comparison. Every idle stage-exit now
  rewrites the state file, and `updatedAt` no longer means "state was touched".
- **`scheduledAt` moved** — the same regression, reported in the form a reader will
  recognize first.
- **`autoVerifyDebtRecorded is False`** — the directive has been re-derived from "did we
  write?" rather than "is the debt on disk?", which would make a repeat exit claim no debt
  is owed while a pending marker sits in the file.

---

## 6. REQ-COV-05 — Commit-2 Ignores Conflicting Flags

**Host file:** `tests/test_state_verbs.py`. **Wrappers:** `_seed`, `_run`, `_state_of`,
`_FULL_HASH`, `FS`.

### 6.1 The verified current behavior

When `--commit-hash` is passed, `cmd_state_complete` takes branch 1 and sets **only**
`entry["commitHash"]`, after asserting the stage is already complete:

```python
    if commit_hash is not None:
        # Commit-2 follow-up: record the real hash, leave everything else intact.
        actual = entry.get("status")
        if actual != _DONE_STATUS:
            raise UsageError(
                f"--commit-hash requires {stage} to be complete (status: {actual!r}); "
                "run state-complete without --commit-hash first"
            )
        entry["commitHash"] = commit_hash
    elif resumable:
        ...
```

It never reads `based_on`, `artifacts`, `status`, `resumable`, or `preserve_commit_hash`.

> **"Ignoring" is implemented by BRANCH PRECEDENCE, not by explicit rejection.** argparse
> accepts every one of those flags on a commit-2 invocation and the branch simply discards
> them. There is no validation error, no warning, and no `UsageError` — a test that expects
> a rejection is testing a contract that does not exist.

**One pre-existing guard runs before branch dispatch and is unaffected**, so it is stated
here to keep it from being read as a counterexample:

```python
    if resumable and status == "complete":
        raise UsageError(
            "--resumable implies --status in-progress; do not pass --status complete"
        )
```

This fires **regardless of `--commit-hash`**, because it sits above the branch. It is
already covered by `test_resumable_with_an_explicit_status_complete_exits_2`; §6.2 does not
re-assert it and does not pass `--resumable`.

### 6.2 What is and is not already covered

`test_commit_hash_follow_up_touches_only_commit_hash` already asserts that a **plain**
commit-2 call disturbs nothing else. It does **not** pass any conflicting flag, so it
cannot detect a branch reordering that lets `--based-on` or `--artifact` through. That is
the gap REQ-COV-05 names, and §6.3 is the test that closes it.

### 6.3 The test

Lands immediately after `test_commit_hash_follow_up_touches_only_commit_hash`, its
positive-control sibling.

```python
def test_commit_2_ignores_based_on_artifact_and_preserve_commit_hash(tmp_path: Path) -> None:
    """REQ-COV-05: the commit-2 branch records the hash and discards the rest.

    Ignoring is branch precedence, not rejection: argparse accepts these flags
    and the branch never reads them. Everything the completion write owns must
    survive the follow-up unchanged, so the surrounding entry is compared as a
    whole rather than field by field.
    """
    _seed(
        tmp_path,
        {
            "forge-1-prd": {
                "status": "complete",
                "completedAt": "2026-01-01T00:00:00Z",
                "version": 2,
                "basedOnVersions": {},
                "artifacts": ["PRD.md"],
                "commitHash": None,
            }
        },
    )
    before = _state_of(tmp_path)["stages"]["forge-1-prd"]

    result = _run(
        "state-complete", "--feature", "demo", "--stage", "forge-1-prd",
        "--version", "2", "--commit-hash", _FULL_HASH,
        "--based-on", "forge-2-tech=9",
        "--artifact", "SHOULD-NOT-BE-RECORDED.md",
        "--preserve-commit-hash",
        "--specs-dir", str(tmp_path / "specs"),
    )
    assert result.returncode == 0, result.stderr

    after = _state_of(tmp_path)["stages"]["forge-1-prd"]
    assert after["commitHash"] == _FULL_HASH
    # Every other field is exactly what the completion write left behind.
    assert {k: v for k, v in after.items() if k != "commitHash"} == {
        k: v for k, v in before.items() if k != "commitHash"
    }
    assert after["basedOnVersions"] == {}, "--based-on must not reach the commit-2 branch"
    assert after["artifacts"] == ["PRD.md"], "--artifact must not reach the commit-2 branch"
    assert after["status"] == "complete"
    assert after["completedAt"] == "2026-01-01T00:00:00Z"
    assert after["version"] == 2
```

`--status` is deliberately **not** passed. Passing `--status complete` would be a no-op
against an already-complete entry and would prove nothing about branch precedence; passing
`--status in-progress` would test the same discard through a flag whose only other consumer
is branch 3. The three flags passed are the three that write *distinct, observable* values
on branch 3 — which is what makes their absence from the result meaningful.

### 6.4 CRITICAL — the assertion this test MUST NOT make

**This test must NOT assert that `--version` is unvalidated on the commit-2 path.**

`--version` is required by argparse on every `state-complete` invocation, including
commit-2, where it is accepted and discarded. It would be trivial — and wrong — to extend
this test with `--version 0` and assert exit 0 as further evidence of "ignoring".

Doing so would **pin the REQ-FIX-01 defect as golden**, in the same feature that fixes it,
and the two tests would then contradict each other (§3 asserts `--version 0` exits 2).

**Validation and writing are separate concerns.** "Ignored" in REQ-COV-05 means **not
written**. It does not mean **not validated**. `_assert_full_commit_hash` sets the
precedent by validating before branch dispatch; `04-production-validations.md` §2 places
`_require_positive_int` in the same pre-dispatch position, so after REQ-FIX-01 lands, a
commit-2 call carrying `--version 0` exits 2 — and that is correct, intended behavior, not
a REQ-COV-05 contract break.

See `04-production-validations.md` §3 and `tech-spec.md` §3.7 ("Interaction with
REQ-COV-05 — stated explicitly to pre-empt a false finding").

### 6.5 What a failure would mean

- **`basedOnVersions` or `artifacts` changed** — branch precedence has been reordered or
  the branches merged, so a copy-pasted commit-2 command now silently rewrites provenance
  that the completion write established.
- **`completedAt` or `version` changed** — the commit-2 path has started re-running the
  completion write, which would re-stamp a completion time for work that completed earlier
  and re-fire the staleness cascade.
- **Exit 2** — either a rejection has been added where the contract is discard-by-precedence
  (a behavior change outside PRD §6's three permitted ones), or the pre-dispatch
  `--resumable`/`--status` guard has widened to flags it does not own.

### 6.6 Error handling

This is a success-path test: exit 0, a state write, and a schema-valid result — `_state_of`
asserts schema conformance on every read, so a branch that wrote a malformed entry fails
here even before the field comparisons run.

---

## 7. REQ-COV-06 — `state-artifact --path` Containment

**Host file:** `tests/test_state_verbs.py`. **Wrappers:** `_seed`, `_run`, `_state_bytes`,
`FS`.

**This test asserts a behavior that does not exist yet.** It tests **REQ-SEC-01**,
specified in `04-production-validations.md` §4, which must land first (§10).

### 7.1 The behavior under test

`cmd_state_artifact` currently appends every `--path` value verbatim:

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

`04-production-validations.md` §4 requires `_validated_findings_file` to gain a defaulted
`label` parameter (`00-core-definitions.md` §7.2) and `cmd_state_artifact` to validate
**every** path **after** the load and **before any mutation**:

```python
state_path, state = _load_state_for_write(specs_dir, feature, epic)
target_dir = state_path.parent
for path in paths:
    _validated_findings_file(path, target_dir, label="--path")
```

**Five branch-specific rejections, not one generic message** (`00` §7.2):

| Branch | Condition | Message fragment |
|---|---|---|
| empty | `not value` | `must not be empty` |
| control character | any `ord(ch) < 32` or `== 127` | `contains a control character` |
| absolute | `Path(value).is_absolute()` | `is absolute` |
| `..` segment | `".." in Path(value).parts` | `contains a '..' segment` |
| resolved escape | `.resolve()` lands on or outside `target_dir` | `escapes the feature directory` |

`.resolve()` is what catches a **symlinked** escape, which no textual check would.

Because validation runs over **all** paths before any mutation, a rejected path in a
repeated `--path` list leaves the file byte-identical.

### 7.2 The tests

Three named tests, landing beside the `--findings-file` containment tests
(`test_state_verify_rejects_an_unsafe_findings_file_before_mutation` and its symlink
sibling) — the same validator, the same property, the other caller.

The unsafe roster mirrors the file's existing `_UNSAFE_FINDINGS_FILES` constant, including
its recorded reason for omitting a NUL byte.

```python
#: `--path` values that must be refused before any mutation (REQ-SEC-01), one per
#: rejection branch. A NUL byte is absent for the same reason it is absent from the
#: findings-file roster: subprocess cannot put one in argv at all.
_UNSAFE_ARTIFACT_PATHS = (
    ("empty", ""),
    ("control-char", "specs/bell\x07.md"),
    ("absolute", "/etc/passwd"),
    ("dotdot", "../../escape.md"),
    ("dotdot-embedded", "verify/../../escape.md"),
)


@pytest.mark.parametrize(
    "label,bad", _UNSAFE_ARTIFACT_PATHS, ids=[row[0] for row in _UNSAFE_ARTIFACT_PATHS]
)
def test_state_artifact_rejects_an_unsafe_path_before_mutation(
    tmp_path: Path, label: str, bad: str
) -> None:
    """REQ-COV-06 / REQ-SEC-01: a recorded path must stay inside the feature dir.

    State must not record a location no forge stage could legitimately have
    written. The refusal names the flag the caller actually passed, and it runs
    before any mutation, so the file is left exactly as it was found.
    """
    root = tmp_path / f"artifact-{label}"
    _seed(root, {"forge-3-specs": {"status": "in-progress"}})
    specs = root / "specs"
    before = _state_bytes(specs)

    result = _run(
        "state-artifact", "--feature", "demo", "--stage", "forge-3-specs",
        "--path", bad, "--specs-dir", str(specs),
    )

    assert result.returncode == 2, f"{bad!r} was accepted"
    assert result.stderr.startswith("Error:"), f"{bad!r}: {result.stderr!r}"
    assert "--path" in result.stderr, f"{bad!r}: {result.stderr!r}"
    assert "--findings-file" not in result.stderr, (
        f"{bad!r}: the refusal must name the flag the caller passed"
    )
    assert not result.stdout.strip(), f"{bad!r} produced stdout"
    assert _state_bytes(specs) == before, f"{bad!r} mutated state"


def test_state_artifact_rejects_a_path_that_escapes_through_a_symlink(
    tmp_path: Path,
) -> None:
    """REQ-COV-06: the containment check resolves, so a link cannot walk out.

    No textual inspection of the value would catch this one — the path has no
    `..` segment and is not absolute; only resolution reveals the escape.
    """
    _seed(tmp_path, {"forge-3-specs": {"status": "in-progress"}})
    specs = tmp_path / "specs"
    outside = tmp_path / "outside"
    outside.mkdir()
    (specs / "demo" / "elsewhere").symlink_to(outside, target_is_directory=True)
    before = _state_bytes(specs)

    result = _run(
        "state-artifact", "--feature", "demo", "--stage", "forge-3-specs",
        "--path", "elsewhere/leaked.md", "--specs-dir", str(specs),
    )

    assert result.returncode == 2, result.stdout
    assert "--path" in result.stderr
    assert "escapes the feature directory" in result.stderr
    assert _state_bytes(specs) == before


def test_state_artifact_rejects_the_whole_batch_when_one_repeated_path_is_unsafe(
    tmp_path: Path,
) -> None:
    """REQ-COV-06: validation covers every `--path` before any of them is appended.

    `--path` is repeatable, so a batch that validates as it appends would leave
    the safe prefix recorded and the file rewritten. Nothing may land.
    """
    _seed(tmp_path, {"forge-3-specs": {"status": "in-progress"}})
    specs = tmp_path / "specs"
    before = _state_bytes(specs)

    result = _run(
        "state-artifact", "--feature", "demo", "--stage", "forge-3-specs",
        "--path", "00-core-definitions.md",
        "--path", "../escape.md",
        "--path", "01-architecture-layout.md",
        "--specs-dir", str(specs),
    )

    assert result.returncode == 2, result.stdout
    assert "--path" in result.stderr
    assert "'../escape.md'" in result.stderr, "the refusal must quote the offending value"
    assert _state_bytes(specs) == before, "no path in a rejected batch may be recorded"
```

### 7.3 The two assertions that carry REQ-COV-06's weight

1. **The message names `--path`, not `--findings-file`.** This is asserted positively *and*
   negatively. Reusing `_validated_findings_file` without the `label` parameter would make
   `state-artifact --path ../escape.md` exit 2 naming a flag the user never passed —
   violating `00-core-definitions.md` §8.2's message shape and REQ-OBS-01. The negative
   assertion is what actually detects a missed `{label}` substitution in one of the five
   messages, since four of them would still contain the substring `--path`… only if
   substituted. Both directions are needed.
2. **The state file is byte-identical after every rejection**, including the repeated-`--path`
   case. Validation is placed after the load but before any mutation
   (`00` §7.3); `_load_state_for_write` only reads, so a rejection cannot leave a partially
   written file.

### 7.4 What a failure would mean

- **Exit 0 on any roster row** — REQ-SEC-01 has regressed or was never landed, and state can
  again record a location outside the feature directory for a downstream consumer to
  resolve.
- **Exit 2 but the message names `--findings-file`** — the `label` argument was not passed
  at the `cmd_state_artifact` call site, or a message was left with the literal hardcoded.
- **Exit 2 but the bytes changed on the batch case** — validation has been moved inside the
  append loop, so a rejected batch now records its safe prefix.
- **The symlink case passes while the `..` cases fail** — `.resolve()` has been dropped in
  favour of a textual check, which is a containment bypass rather than a stylistic change.

### 7.5 What these tests must NOT assert

They must not assert anything about `--findings-file`'s messages. The defaulted
`label = "--findings-file"` preserves every existing message **byte-for-byte**, so
`cmd_state_verify` and all of its tests are unchanged (`00` §7.2). Re-asserting them here
would duplicate `test_state_verify_rejects_an_unsafe_findings_file_before_mutation` for no
added protection.

---

## 8. REQ-COV-07 — Unsafe Epic Back-Pointer Degradation

**Host file:** `tests/test_stage_exit.py`. **Wrappers:** `_project`, `_exit`, `_docs`.

### 8.1 This is a coverage test of CORRECT existing behavior

REQ-COV-07's own wording is "**degradation behavior** on an unsafe on-disk `epic`
back-pointer" — it asks for coverage, not a fix. `tech-spec.md` §3.12 records the
investigation:

> **A candidate defect was investigated and disproved.** The claim under review was that
> `row["epic"]` flows unvalidated into `specs_dir / row["epic"] / name`. It does not:
> `_scan_features` derives the epic name from the **parent directory enumerated off disk**
> (`top.name` from `iterdir()`), not from the state file's `epic` field.

Confirmed in `scripts/forge-session.py`:

```python
    for top in sorted(p for p in specs_dir.iterdir() if p.is_dir()):
        ...
            if nested_state.is_file():
                out.append((child.name, top.name, _read_state(nested_state)))
```

The epic name is a real directory name by construction and cannot carry a traversal
segment. (A function named `_derive_epic` does **not** exist in `forge-session.py`.)

### 8.2 The real surface, and the guard that already protects it

The on-disk `epic` **field** is read for routing in `stage_exit` and is already
name-checked:

```python
    epic_name = epic or state.get("epic")
    route_epic = (
        epic_name if isinstance(epic_name, str) and SAFE_NAME_RE.match(epic_name) else None
    )
```

with

```python
SAFE_NAME_RE: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
```

`route_epic` is what reaches `_loop_route` and `_docs_route`. An unsafe value degrades it to
`None` — the **standalone** route — rather than crashing a stage closing.

### 8.3 The test

Lands in the documentation-routing section of `tests/test_stage_exit.py`, beside
`test_docs_routes_on_the_state_epic_back_pointer_without_an_explicit_flag`, which is the
positive control for the same back-pointer read.

```python
def test_an_unsafe_epic_back_pointer_degrades_to_the_standalone_route(
    tmp_path: Path,
) -> None:
    """REQ-COV-07: an unusable on-disk epic name routes standalone, not fatally.

    The back-pointer is untrusted on-disk data, so it is name-checked before it
    can steer routing. A value that fails the check leaves no epic to route
    against, and the exit falls back to the standalone terminus rather than
    failing a stage closing on data the user did not type.
    """
    root = _project(
        tmp_path,
        config={},
        state={
            "pipelineStatus": "active",
            "epic": "../evil",
            "stages": {"forge-5-loop": {"status": "complete", "version": 1}},
        },
    )

    payload = _docs(root, "widget", "complete")

    # `_exit` already asserts exit 0: the closing succeeds.
    directives = payload["directives"]
    assert "<new-feature>" in payload["nextSteps"], "the standalone terminus was not taken"
    assert "../evil" not in directives["primaryCommand"]
    assert payload["nextSteps"].rstrip("\n").endswith(SENTINEL)
```

`_docs` is `tests/test_stage_exit.py`'s own wrapper
(`_exit(cwd, "--feature", feature, "--stage", "forge-6-docs", "--outcome", outcome, ...)`),
and `_exit` asserts `returncode == 0` internally — so a successful exit is asserted by
construction, which is half of what REQ-COV-07 asks for.

`"<new-feature>"` is the standalone documentation terminus's marker: the epic-scoped route
names a concrete next member, while the standalone route prompts for a new feature. The
existing standalone tests in the same file use exactly this token as the discriminator.

### 8.4 What this test must NOT assert — the residual, deliberately unpinned

**The test asserts the degradation ONLY.** It must not pin the reconcile-command
interpolation as golden.

`tech-spec.md` §3.12 records the residual: the *validated* `route_epic` drives routing, but
the *unvalidated* `epic_name` is still interpolated into the printed reconcile command
`f"/feature-forge:forge-0-epic {epic_name}"`. That is a display string; an unsafe name is
rejected by the resolver at exit 2 if the user runs it — it fails closed, just later.
Changing it would touch `stage_exit`'s golden-file-tested payload, so it is **not changed**
and **not pinned as golden either** (`tech-spec.md` §10.2 item 2).

**The test is constructed so it cannot reach that string.** The seeded state carries no
`epicChangeRequests`, so `open_requests` is empty, `epic_reconcile` stays `None`, and
`reconcile_command` is never built:

```python
    if open_requests and epic_name:
        reconcile_command = f"/feature-forge:forge-0-epic {epic_name}"
```

Do not add an open change request to this fixture. Doing so would drag the unpinned
interpolation into a golden assertion and violate REQ-FIX-02's warning against pinning
questionable behavior (§9).

The assertion `"../evil" not in directives["primaryCommand"]` is scoped to the **primary
route** for exactly this reason — it pins that routing did not use the unsafe value,
without asserting anything about how any display string would render it.

### 8.5 What a failure would mean

- **Exit 2** — the name check has been removed or converted to a hard failure, so untrusted
  on-disk data can now fail a stage closing. This is the crash `route_epic`'s guard exists to
  prevent.
- **An epic-scoped route was taken** — `SAFE_NAME_RE` is no longer applied to the
  back-pointer, and an unsafe name is reaching a path resolver.
- **`../evil` appears in `primaryCommand`** — the unvalidated `epic_name` has been
  substituted for `route_epic` in routing, which is the substitution the guard prevents.

### 8.6 Error handling

There is no error path here — the point is that there **isn't** one. `stage_exit`'s posture
on untrusted on-disk data is "never crash a stage closing"; the degradation is the handling.
Fail-closed identity checks on **caller-supplied** values (`--epic`, `--next-feature`) are a
separate contract, already covered by `test_unsafe_epic_and_next_feature_are_rejected_too`
and `test_an_unsafe_member_name_exits_2_rather_than_falling_back`. This test must not be
read as contradicting them: an argument the user typed is rejected; a field found on disk
degrades.

---

## 9. REQ-FIX-02 — If a Backfill Test Uncovers a Defect

**REQ-FIX-02 is a standing obligation on this document's implementation, not a task.**

If any test written for REQ-COV-01..07 uncovers a defect **beyond** REQ-FIX-01 and
REQ-SEC-01, that defect MUST be **fixed within this feature** rather than pinned as golden
behavior and deferred.

**The reason is procedural, and it is the whole point:** a test that asserts known-wrong
behavior invites a blocking finding on the next verify round. Pinning a defect converts a
one-time fix into recurring churn, which is the failure mode this entire feature exists to
remove.

**Current disposition: REQ-FIX-02 adds no work.** The one investigated candidate — the
claim that an unvalidated `epic` field reaches a path resolver — was **disproved**
(§8.1, `04-production-validations.md` §5, `tech-spec.md` §3.12). The behavior changes in
this feature remain exactly the two named in PRD §3.3.

**Two outcomes recorded in this document are NOT REQ-FIX-02 triggers**, and must not be
re-filed as such under C-04:

| Recorded outcome | Why it is not a REQ-FIX-02 trigger |
|---|---|
| Corrupt state + auto-verify ON yields no payload (§2.2) | Defensible fail-closed behavior with a recorded position; the diagnostic version is a deferred **output-contract change**, not a defect left unfixed (`tech-spec.md` §10.2 item 3) |
| Unvalidated `epic_name` in the reconcile display string (§8.4) | Fails closed downstream at the resolver; **not changed and not pinned as golden** (`tech-spec.md` §10.2 item 2) |

If implementation surfaces a **third** candidate, the required sequence is: (1) do not
write a test asserting the wrong behavior; (2) raise it against PRD §3.3 REQ-FIX-02;
(3) fix it in this feature, or record a position for it the way the two rows above are
recorded. Silently pinning it is the one disallowed option.

---

## 10. Dependencies

### 10.1 Spec documents that must be read first

| Document | For |
|---|---|
| `00-core-definitions.md` | §7 validator contracts (`_require_positive_int`, `_validated_findings_file` + `label`, placement); §8 error contract (exit 2, message shape, REQ-OBS-01); §10.5 the per-file CLI wrapper rule |
| `01-architecture-layout.md` | §3.3 file ownership; §4.2 the placement map; §5.2 step 5 and §5.4 merge order |
| `04-production-validations.md` | §2 (REQ-FIX-01), §3 (the REQ-COV-05 non-assertion), §4 (REQ-SEC-01), §5 (`PRELUDE_CRITERIA` and the disproved candidate) |
| `06-brittleness-batch.md` | Runs **after** this document in all three shared files (`01` §5.4) |

### 10.2 The cross-document requirement pair — implementation ordering

**This is the one hard ordering constraint in this document.**

| This test | Cannot pass until | Specified in |
|---|---|---|
| §3 `test_state_complete_rejects_a_non_positive_version_before_mutation` | **REQ-FIX-01** has landed | `04-production-validations.md` §2 |
| §7 all three `state-artifact --path` tests | **REQ-SEC-01** has landed | `04-production-validations.md` §4 |
| §4 `test_the_prelude_scorer_returns_exactly_the_four_specified_criteria` | **`PRELUDE_CRITERIA`** has been added to `eval/run-compliance-eval.py` | `04-production-validations.md` §5 |

`01-architecture-layout.md` §5.2 puts the production validations at **step 2** and this
backfill at **step 5** for exactly this reason: landing the validations first means these
tests are written against **real behavior** rather than intended behavior.

§2 (REQ-COV-01), §5 (REQ-COV-04), §6 (REQ-COV-05) and §8 (REQ-COV-07) assert **existing**
behavior and have no production dependency — they can be written and will pass against the
tree as it stands today.

### 10.3 Code dependencies

**Production symbols these tests exercise** (all in `scripts/forge-session.py` unless
noted; located by name per C-07):

| Symbol | Signature | Used by |
|---|---|---|
| `_read_state` | `(state_path: Path) -> dict` | §2 (tolerant arm) |
| `_load_state_for_write` | `(specs_dir: Path, feature: str, epic: str \| None) -> tuple[Path, dict]` | §2 (strict arm), §7 |
| `_schedule_auto_verify_debt` | `(specs_dir: Path, feature: str, epic: str \| None, stage: str, verify_key: str) -> None` | §2, §5 |
| `_load_verify_target` | `(specs_dir: Path, feature: str, epic: str \| None, is_epic_target: bool) -> tuple[Path, dict, int \| None]` | §2 (the strict reload's route) |
| `stage_exit` | `(feature, stage, specs_dir, config_path, epic, host, next_feature, served_stage=None, verify_mode=None, outcome=None, owner=None, verify_capability="manual") -> StageExitPayload` | §2, §5, §8 |
| `cmd_state_complete` | `(feature, stage, version, based_on, artifacts, commit_hash, specs_dir, epic, status=None, preserve_commit_hash=False, resumable=False) -> dict` | §3, §6 |
| `cmd_state_artifact` | `(feature: str, stage: str, paths: list[str], specs_dir: Path, epic: str \| None) -> dict` | §7 |
| `_require_positive_int` | `(value: object, label: str) -> int` | §3 (via REQ-FIX-01) |
| `_validated_findings_file` | `(value: str, target_dir: Path, label: str = "--findings-file") -> str` | §7 (via REQ-SEC-01) |
| `SAFE_NAME_RE` | `re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")` | §8 |
| `score_prelude` (`eval/run-compliance-eval.py`) | `(transcript: dict) -> dict[str, bool]` | §4 |
| `PRELUDE_CRITERIA` (`eval/run-compliance-eval.py`) | `Final[tuple[str, ...]]` — **added by `04` §5** | §4 |

**External packages:** none added. Stdlib (`json`, `subprocess`, `sys`, `pathlib`) plus
`pytest`, all already in use in every host file. **`jsonschema` must not be introduced** —
it is absent in CI, and `tests/_state_schema.py` (via `_state_of`) is the schema check
these files already use.

**Forbidden dependency:** `tests/conftest.py`'s `run_cli` fixture. It is hardcoded to
`scripts/epic-manifest.py`, is used by no file in scope, and `01-architecture-layout.md` §2
marks `conftest.py` UNCHANGED.

---

## 11. Verification

An implementation matches this document when every box below is checked.

**Placement (the audit trail):**

- [ ] All seven REQ-COV ids have at least one named test, in the host file §1.1 assigns.
- [ ] Every new test reuses its host file's **own** CLI wrapper; no new shared helper was
      introduced and `tests/conftest.py` is absent from the diff.
- [ ] No new test file was created — the backfill lands entirely in the four existing host
      files.

**Per-requirement:**

- [ ] **REQ-COV-01** — `test_a_corrupt_state_file_exits_2_with_no_payload_when_auto_verify_is_on`
      asserts exit 2, **empty stdout**, and a byte-identical state file;
      `test_a_corrupt_state_file_closes_the_stage_normally_when_auto_verify_is_off` asserts
      exit 0, `autoVerifyDebtRecorded is False`, and a byte-identical state file.
- [ ] **REQ-COV-02** — `test_state_complete_rejects_a_non_positive_version_before_mutation`
      asserts exit 2, the exact message `Error: --version must be a positive integer; got 0`
      (and its `-1` counterpart), and a byte-identical state file.
- [ ] **REQ-COV-03** — `test_the_prelude_scorer_returns_exactly_the_four_specified_criteria`
      asserts **both** `tuple(criteria) == SPEC_PRELUDE_CRITERIA` and
      `ce.PRELUDE_CRITERIA == SPEC_PRELUDE_CRITERIA`, against a copy of the four keys
      declared **in the test file** and **not imported** from `ce`.
- [ ] **REQ-COV-04** — `test_a_pending_marker_at_the_current_revision_is_left_byte_identical`
      compares `read_bytes()` before and after; the existing
      `test_repeated_stage_exit_at_the_same_revision_is_byte_idempotent` still exists and was
      not duplicated.
- [ ] **REQ-COV-05** — `test_commit_2_ignores_based_on_artifact_and_preserve_commit_hash`
      passes `--based-on`, `--artifact` and `--preserve-commit-hash`, asserts only
      `commitHash` changed, and **contains no `--version 0` assertion**.
- [ ] **REQ-COV-06** — all five rejection branches are covered plus the symlinked escape and
      the repeated-`--path` batch; every rejection asserts `--path` **is** in stderr,
      `--findings-file` is **not**, and the state file is byte-identical.
- [ ] **REQ-COV-07** — `test_an_unsafe_epic_back_pointer_degrades_to_the_standalone_route`
      asserts a successful exit and the standalone route, and the fixture carries **no**
      `epicChangeRequests`, so the reconcile-command interpolation is never rendered.

**Cross-cutting:**

- [ ] REQ-CANON-03: no docstring or comment added by this document carries a count, a
      "measured"/"confirmed" claim, or any other empirical assertion.
- [ ] No test added here asserts known-wrong behavior (REQ-FIX-02, §9).
- [ ] No behavior change appears in `scripts/forge-session.py` or `eval/` **from this
      document** — every production edit these tests depend on belongs to
      `04-production-validations.md`.
- [ ] These tests were added **before** `06-brittleness-batch.md`'s rewrites in the three
      shared files (`01` §5.4); no test added here is a hand-rolled loop that `06` would
      then have to parametrize.
- [ ] `python3 -m pytest tests -q` is green; `ruff check tests/` is at or below 19 errors.
