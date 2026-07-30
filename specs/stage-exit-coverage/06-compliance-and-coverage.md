# 06 — Compliance and Canonical Exit Coverage

## Requirement Coverage

| REQ ID | Requirement | Section |
|---|---|---|
| REQ-GUARD-01 | Explicitly enumerate every deterministic pipeline exit | §2 |
| REQ-GUARD-02 | Cover nine production/branch skills and intentionally exclude non-advancing skills | §2.1–§2.3 |
| REQ-GUARD-03 | Replace bespoke loop/docs assertions with equivalent positive scripted-contract coverage | §2.4 |
| REQ-EVAL-01 | Independently drive and score verify → fix → re-verify with one terminal sentinel | §3–§5 |
| REQ-EVAL-02 | Score successful rejoin and recovery using ordered command-result evidence | §3.2, §4–§5 |
| REQ-EVAL-03 | Document the linear baseline separately from branch compliance | §6 |
| REQ-EXIT-03 | Require exactly one sentinel and no trailing user-facing content | §2.3, §5.2 |
| REQ-EXIT-04 | Reject a terminal block emitted by a nested verify/fix step | §2.3, §5.2 |
| REQ-REL-01 | Keep fixture expectations and scores deterministic | §3.2, §5.1 |
| REQ-OBS-01 | Preserve auditable routing and command-result criteria in reports | §4–§5 |
| REQ-COMPAT-01 | Retain the existing linear probe as a separate baseline | §3.1, §6 |
| REQ-COMPAT-02 | Preserve direct and nested workflow coverage without changing fixture consumers | §3.1–§3.3 |
| REQ-COMPAT-03 | Keep compliance advisory and `smokeCommand: null` unchanged | §6–§8 |

## 1. Purpose and Scope

This document defines two independent enforcement layers (tech-spec §3.10 and §8.4–§8.5):

1. a fast canonical guard in `tests/test_stage_exit_protocol.py` that names exactly the nine
   pipeline-advancing skills and proves their direct closure surfaces use the single scripted
   contract; and
2. a separate branch compliance fixture/scorer in `eval/run-compliance-eval.py` that measures a
   real verify → fix → re-verify diversion, including successful production rejoin and recovery
   after further findings.

The guard is a correctness gate. The model-driven compliance harness remains advisory, local-only,
and rate-based. Its offline fixture and scorer tests are correctness gates. This document does not
change stage routing itself; those contracts are defined in `00-core-definitions.md` and implemented
before this document per `01-architecture-layout.md`.

## 2. Explicit Nine-Skill Canonical Guard

### 2.1 Coverage data (REQ-GUARD-01, REQ-GUARD-02)

In `tests/test_stage_exit_protocol.py`, replace the inferred authoring-stage sets and the old
terminal allow-list with this explicit immutable table. `ExitStage` is the shared domain from
`00-core-definitions.md`; the test file may use `str` at runtime because `scripts/forge-session.py`
is an executable with a hyphenated filename and is not imported merely to obtain a type alias.

```python
from pathlib import Path
from typing import Final, NamedTuple


class CanonicalExitSite(NamedTuple):
    """One required skill and the exact canon files that own its direct terminus."""

    # Skill id, matching its directory name under `skills/`. Must be one of the
    # nine covered skills; a skill in INTENTIONALLY_EXCLUDED_SKILLS must not appear.
    skill: str
    # Repo-relative canon files that together own this skill's terminal exit —
    # SKILL.md plus any reference file carrying part of the stamp. Non-empty, and
    # paths are canon-only: never an `adapters/` path, which is generated output.
    # A tuple, not a list, so the coverage table stays immutable at import time.
    contract_paths: tuple[str, ...]


CANONICAL_EXIT_SITES: Final[tuple[CanonicalExitSite, ...]] = (
    CanonicalExitSite("forge-0-epic", ("skills/forge-0-epic/SKILL.md",)),
    CanonicalExitSite("forge-1-prd", ("skills/forge-1-prd/SKILL.md",)),
    CanonicalExitSite("forge-2-tech", ("skills/forge-2-tech/SKILL.md",)),
    CanonicalExitSite("forge-3-specs", ("skills/forge-3-specs/SKILL.md",)),
    CanonicalExitSite("forge-4-backlog", ("skills/forge-4-backlog/SKILL.md",)),
    CanonicalExitSite(
        "forge-5-loop",
        (
            "skills/forge-5-loop/SKILL.md",
            "skills/forge-5-loop/references/result-reporting.md",
        ),
    ),
    CanonicalExitSite("forge-6-docs", ("skills/forge-6-docs/SKILL.md",)),
    CanonicalExitSite("forge-verify", ("skills/forge-verify/SKILL.md",)),
    CanonicalExitSite("forge-fix", ("skills/forge-fix/SKILL.md",)),
)

INTENTIONALLY_EXCLUDED_SKILLS: Final[frozenset[str]] = frozenset(
    {
        "forge",
        "forge-guide",
        "forge-init",
        "forge-update",
    }
)
```

`CANONICAL_EXIT_SITES` is the authoritative allow-list, not a prefix scan. The test asserts:

- its `skill` tuple equals `EXIT_STAGES` from `00-core-definitions.md`, in the same order;
- it has nine unique skill names and no duplicate path;
- every path exists under `REPO_ROOT` and remains contained by `skills/`;
- every excluded identifier is absent from the covered table; and
- no navigator/setup/bootstrap/advisory skill is added merely because its name begins with
  `forge-`.

The exclusions are documentary and defensive, not an exhaustive list of every helper skill. A new
pipeline-advancing skill requires an intentional edit to both the shared `EXIT_STAGES` domain and
this table; a new advisory skill does not silently become covered.

### 2.2 Canonical stamp extraction and rendering (REQ-GUARD-01, REQ-GUARD-03)

Retain the existing exact source integration from `tests/test_stage_exit_protocol.py`:

```python
def _extract_block(name: str) -> str: ...
def _render(block: str, **slots: str) -> str: ...
```

These functions read `references/stage-exit-protocol.md` and render only build-time slots. Runtime
placeholders such as `{feature}`, `{epic}`, and `{specsDir}` remain literal. Continue using exact
verbatim matching rather than semantically similar prose, because the reference is the sole
canonical directive contract.

Add a local helper for an explicitly listed site's closure surface:

```python
def _read_contract_surface(site: CanonicalExitSite) -> str:
    """Read the explicitly owned canon files for one covered skill.

    Args:
        site: Covered skill and its exact repository-relative canon paths.

    Returns:
        UTF-8 file contents joined in the listed order with one newline separator.

    Raises:
        AssertionError: A path is missing, escapes `skills/`, or is listed twice.
        OSError: A listed canon file cannot be read.
    """
```

Do not recursively scan references. The loop's result templates are included by their exact path so
the guard cannot accidentally pass because unrelated prose elsewhere mentions `stage-exit`.

### 2.3 Contract assertions (REQ-GUARD-01, REQ-GUARD-02, REQ-EXIT-03, REQ-EXIT-04)

For each `CanonicalExitSite`, assert all of the following against its explicit closure surface:

1. The canonical scripted-stage-exit stamp or the equivalent stage-specific invocation generated
   from that stamp is present. The invocation includes
   `python3 "$R/scripts/forge-session.py" stage-exit` and the exact `--stage <skill>` value.
2. Direct `forge-verify` and `forge-fix` invocations include `--owner direct`; their nested/automatic
   instructions include `--owner nested` and explicitly return terminal ownership to the outer
   caller.
3. Every direct closure says the script's `NEXT-STEPS` value is printed verbatim as the absolute
   final output, and names the no-content-after-sentinel rule.
4. No covered closure retains the retired bespoke standard/warm terminal block as an alternative.
   A compatibility explanation may mention the old block, but a second fenced advancing command or
   second terminal-print instruction fails.
5. Each covered direct path contains exactly one terminal-print instruction. Nested branch paths
   contain zero terminal-print instructions and rely on the outer owner.

Use stable marker/command literals from `references/stage-exit-protocol.md`, not broad words such as
`Next steps`. Count complete invocation and terminal-print markers so duplicate contracts fail.
The sentinel value itself is shared as `NEXT_STEPS_SENTINEL` in `00-core-definitions.md`; the guard
also asserts that the canonical reference contains its exact value once in the scripted contract.

Errors are assertion failures naming the skill, relative path(s), expected marker, and observed
count. Never rewrite canon from the test and never inspect generated `adapters/` as the source of
truth.

### 2.4 Loop/docs migration equivalence (REQ-GUARD-03)

Replace, rather than delete, the current assertions that `forge-6-docs` is terminal and that
`forge-5-loop` stamps bespoke standard/warm blocks. Positive replacement tests must prove:

- `forge-5-loop`'s explicit SKILL/result-reporting surface covers all outcomes from
  `EXIT_OUTCOMES["forge-5-loop"]` and each terminus invokes scripted `stage-exit`;
- `forge-6-docs` requires `--outcome complete|blocked` and invokes scripted `stage-exit`;
- removing either invocation makes the test fail;
- adding a second scripted terminal instruction makes the test fail; and
- direct verify/fix removals fail identically to production-stage removals.

Negative guard tests should copy a contract surface into a string and remove/duplicate markers;
they must not mutate repository files. This preserves equivalent coverage while retiring obsolete
expectations.

WARNING: The current `tests/test_stage_exit_protocol.py` exports neither
`CanonicalExitSite` nor `CANONICAL_EXIT_SITES`, and currently treats `forge-6-docs` as terminal —
verify and replace those assumptions during implementation.

## 3. Separate Branch Compliance Fixture

### 3.1 Isolation from current fixtures (REQ-EVAL-01, REQ-EVAL-03, REQ-COMPAT-01/02)

Current `eval/fixtures/forge-1-prd.json` and `eval/fixtures/forge-5-loop.json` are trigger-accuracy
fixtures consumed by `eval/run-eval.py::load_fixtures() -> list[dict]`, which uses the non-recursive
pattern `eval/fixtures/*.json`. Do not alter their schema and do not place branch data at that
level.

Create the branch fixture at the exact path:

```text
eval/fixtures/compliance/verify-fix-reverify.json
```

The nested directory deliberately prevents `eval/run-eval.py` from loading a compliance fixture as
a trigger fixture. `eval/run-compliance-eval.py` alone reads this exact file; it does not glob all
JSON. This preserves the existing linear and trigger baselines.

### 3.2 Fixture data shape and scenarios (REQ-EVAL-01, REQ-EVAL-02, REQ-REL-01)

Add these types to `eval/run-compliance-eval.py`. They are eval-internal dictionary boundaries, not
shared domain types and therefore do not redefine `00-core-definitions.md`.

```python
from typing import Literal, TypedDict

BranchScenarioName = Literal["successful-rejoin", "recovery"]
EvidenceStage = Literal[
    "verify-findings",
    "fix-applied",
    "reverify-passed",
    "reverify-recovery",
    "terminal-exit",
]


class ExpectedCommand(TypedDict):
    """One ordered command that must have a successful tool result.

    Total. Ordering is positional: an ExpectedCommand's index in
    `BranchScenario.expectedCommands` IS its required order, which is why matching
    is ordered-subsequence rather than set membership (§4.2).
    """

    # Which branch step this command belongs to (verify, fix, re-verify). Groups
    # evidence so a scorer can attribute a miss to a step, not just to the run.
    stage: EvidenceStage
    # Substrings that must ALL appear in one command string — an AND, not an OR,
    # and substring matching rather than equality so incidental flag ordering and
    # absolute paths do not make the fixture brittle. Non-empty; an empty list
    # would match every command and silently pass.
    contains: list[str]


class BranchScenario(TypedDict):
    """One deterministic branch-path compliance scenario.

    Total. The three outcome fields are the fixture's INPUTS — the branch results
    being simulated — while `expected*` are the ground truth being scored. The
    narrow Literals are deliberate: this fixture exercises the findings→fix→
    re-verify path only, and a widened value belongs in a new scenario rather than
    a loosened type.
    """

    # Stable scenario id, used in scorer output and to select a single scenario.
    name: BranchScenarioName
    # Initial verify result being simulated. Always "findings" — a passing initial
    # verify produces no fix step and so exercises no branch path.
    initialVerifyOutcome: Literal["findings"]
    # Fix result being simulated. Always "applied": a fix that applies nothing has
    # no rejoin to verify.
    fixOutcome: Literal["applied"]
    # Re-verify result being simulated. This is the branch: "passed" rejoins the
    # served production stage, while "findings"/"failed" must keep verification
    # authoritative instead of advancing.
    reverifyOutcome: Literal["passed", "findings", "failed"]
    # The single command that MUST be primary at the terminus for this outcome —
    # the assertion that catches a dropped pipeline thread (#176).
    expectedPrimaryCommand: str
    # Ordered commands that must each appear with a successful tool result.
    expectedCommands: list[ExpectedCommand]


class BranchFixture(TypedDict):
    """Versioned offline input for the branch compliance probe.

    Total. Deliberately isolated from the existing linear fixtures (§3.1): this
    file is loaded only by the branch probe, so a change here cannot move the
    linear baseline.
    """

    # Fixture schema version. Literal[1] — a shape change bumps this rather than
    # mutating v1 in place, so an older probe fails loudly instead of
    # misinterpreting new fields.
    schemaVersion: Literal[1]
    # Synthetic feature name built into the scratch repo. Never a real repo feature.
    feature: str
    # Production stage the simulated verify/fix diversion serves and rejoins.
    servedStage: Literal["forge-1-prd"]
    # Verify mode paired with `servedStage`; must agree with it under
    # VERIFY_MODE_TO_STAGE, and the fixture validator checks that agreement.
    verifyMode: Literal["prd"]
    # The scenarios to run. Exactly two in the shipped fixture (successful rejoin
    # and unresolved re-verify); non-empty, and names must be unique.
    scenarios: list[BranchScenario]
```

The JSON has exactly two scenarios:

- **`successful-rejoin`:** verify reports findings, fix records applied changes, re-verify passes,
  and the final outer/direct exit fences `/feature-forge:forge-2-tech <feature>`.
- **`recovery`:** verify reports findings, fix records applied changes, re-verify reports findings
  (the fixture may use failure only in a negative test), and the final direct recovery terminus
  fences the deterministic `forge-fix` recovery command for the same served stage.

Each `expectedCommands` list orders the real `forge-session.py stage-exit` calls and includes tokens
for exact stage, outcome, owner, and served-stage/mode arguments. Intermediate verify/fix calls use
`--owner nested`; the final call is the sole terminal owner. The fixture never accepts a prose
claim as a substitute for a command.

Implement strict loading:

```python
def load_branch_fixture(path: Path) -> BranchFixture:
    """Load and validate the branch compliance fixture.

    Args:
        path: Exact JSON fixture path.

    Returns:
        A validated version-1 fixture with scenarios in file order.

    Raises:
        OSError: The fixture cannot be read.
        json.JSONDecodeError: The fixture is malformed JSON.
        RuntimeError: Its version, keys, literals, scenario cardinality, ordering,
            command tokens, or safe feature identity violate this specification.
    """
```

Validation requires one occurrence of each scenario name, the order `successful-rejoin` then
`recovery`, non-empty token lists, no duplicate command stage within a scenario, and the same safe
feature/served-stage throughout. Unknown keys fail rather than being silently ignored, keeping
baseline inputs reviewable.

### 3.3 Fixture construction and ground truth (REQ-EVAL-01, REQ-EVAL-02)

Reuse the current exact integrations from `eval/run-compliance-eval.py`:

```python
def run_session(cwd: Path, prompt: str, model: str) -> dict: ...
def expected_stage_exit(root: Path) -> dict: ...
def _git_init(root: Path) -> None: ...
```

Add branch-specific entry points:

```python
def build_branch_fixture(root: Path, fixture: BranchFixture) -> None:
    """Build a schema-valid throwaway repository before branch diversion.

    Raises:
        OSError: Fixture files cannot be created.
        RuntimeError: Fixture values are invalid or the repository cannot initialize.
    """


def branch_prompt(fixture: BranchFixture, scenario: BranchScenario) -> str:
    """Return the user turn that drives one complete branch scenario."""


def expected_branch_exit(
    root: Path,
    fixture: BranchFixture,
    scenario: BranchScenario,
) -> dict:
    """Run the real final `stage-exit` command and return scorer ground truth.

    Raises:
        RuntimeError: The command exits non-zero or emits invalid JSON.
    """
```

Build a fresh temporary repository per model/run/scenario. As with the current cold/warm probe,
state must satisfy `references/pipeline-state-schema.json`; state transitions caused by one run
must never leak into another. Expected terminal output comes from the real
`scripts/forge-session.py stage-exit` after the scenario's state transition, not from hand-written
fixture prose. `StageExitPayload` and `StageExitDirectives` are defined in
`00-core-definitions.md`.

## 4. Ordered Command-Result Evidence

### 4.1 Transcript normalization (REQ-EVAL-02, REQ-OBS-01)

The current `parse_transcript(stdout: str) -> dict` in `eval/run-compliance-eval.py` captures only
Bash command strings and final text. Extend its returned dictionary additively; preserve
`bash_commands` for the linear and R2 scorers.

```python
class CommandEvidence(TypedDict):
    """A Bash request paired with its actual host tool result.

    Total. The whole point of this type is that a REQUESTED command is not a RUN
    command: scoring on requests alone would credit a command the host rejected or
    that failed. `resultSeen` plus `isError` is what makes the evidence real.
    """

    # 0-based position among Bash requests in the transcript. Establishes the
    # ordering that ordered-subsequence matching consumes.
    requestIndex: int
    # Host tool-use id linking request to result. The join key — never positional,
    # since results can interleave.
    toolUseId: str
    # Verbatim requested command string, unnormalized.
    command: str
    # Whether a matching tool RESULT was found. False means the command was
    # requested but never observed to complete — a request without evidence, which
    # never scores as executed.
    resultSeen: bool
    # Parsed exit status, or None when the host did not report one (including every
    # `resultSeen: False` case). None is unknown, never success.
    exitCode: int | None
    # Host-reported error flag. True fails the evidence even with exitCode 0, since
    # the host may error out before the command's own status is meaningful.
    isError: bool
    # Trailing slice of result output, bounded for diagnostics. Never matched
    # against — it is for reading a failure, not for scoring.
    resultTail: str


class ParsedTranscript(TypedDict, total=False):
    """Normalized fields shared by compliance scorers.

    `total=False` because a malformed or truncated transcript yields a partial
    parse: `ok: False` plus `note`, with the content fields absent. A scorer must
    check `ok` before reading anything else — a missing `bash_commands` means "not
    parsed", never "no commands were run".
    """

    # Whether the transcript parsed. False means every content field below may be
    # absent and the run must not be scored as a compliance failure.
    ok: bool
    # The assistant's final user-facing message — where the terminal NEXT-STEPS
    # block and its sentinel must appear.
    final_text: str
    # All assistant messages in order, for asserting no content follows the
    # sentinel and no competing terminal block was emitted.
    assistant_texts: list[str]
    # Every requested Bash command, in order. Requests only — pair with
    # `command_evidence` for what actually ran.
    bash_commands: list[str]
    # Requests joined to results; the evidence scoring consumes.
    command_evidence: list[CommandEvidence]
    # Run cost in USD, None when the host did not report it. Advisory telemetry —
    # never a scoring criterion.
    cost_usd: float | None
    # Assistant turn count, None when unreported. Advisory.
    turns: int | None
    # Wall-clock duration in ms, None when unreported. Advisory.
    duration_ms: int | None
    # Human-readable parse diagnostic. Present on `ok: False`; may also carry a
    # non-fatal advisory on a successful parse.
    note: str


def parse_transcript(stdout: str) -> ParsedTranscript:
    """Pair ordered Bash tool requests with results and retain all assistant text.

    Raises:
        No exception for malformed stream lines or missing result events; those are
        returned as `ok=False` with an actionable `note`.
    """
```

Pair an assistant `tool_use` block by its non-empty `id` with the later `tool_result` block whose
`tool_use_id` matches. Preserve request order even when results arrive later. A successful Claude
Bash tool result normalizes to `exitCode == 0` and `isError is False`; an error result uses its
reported non-zero exit code where present, otherwise `exitCode is None` and `isError is True`.
Unpaired requests set `resultSeen=False`, `exitCode=None`, and fail the branch scorer. Duplicate tool
IDs, a result preceding its request, or two results for one request make the transcript unusable
(`ok=False`) rather than guessing.

`resultTail` is capped to the last 500 characters for auditability and bounded reports; scoring must
not infer success from its prose. `assistant_texts` contains every assistant text block in event
order plus the result event's final result only if it was not already present. This permits sentinel
counting across the full path, not merely the final answer.

WARNING: The current `eval/run-compliance-eval.py::parse_transcript` does not expose tool result
pairing, exit status, or all assistant text — verify the live Claude stream event shape while
implementing.

### 4.2 Evidence matching (REQ-EVAL-02, REQ-REL-01)

```python
def ordered_command_evidence(
    transcript: ParsedTranscript,
    expected: list[ExpectedCommand],
) -> tuple[bool, list[CommandEvidence]]:
    """Match expected real commands to successful results in strict order.

    Args:
        transcript: Normalized session transcript.
        expected: Scenario commands and required literal tokens in expected order.

    Returns:
        `(True, matches)` only when each expectation matches exactly one later Bash
        request with a seen, non-error, zero exit result. Otherwise `(False, matches)`
        contains the successful prefix for diagnostics.
    """
```

Matching is a subsequence over `command_evidence`, but each expected entry must match exactly one
request and no stage-exit request may occur between matched entries out of fixture order. Every
`contains` value is a literal token, not a regex. A command qualifies as a real exit only when it
contains both `forge-session.py` and `stage-exit`. Reconnaissance commands may appear between exit
commands and are ignored. A missing result, non-zero/error result, reordered exit, duplicate exit,
or hand-authored prose returns `False`.

## 5. Branch Scorer and Negative Fixtures

### 5.1 Scorer API (REQ-EVAL-01, REQ-EVAL-02, REQ-OBS-01)

Retain current `RunResult`, `ProbeReport`, `Report`, `_to_result(...)`, and `_probe_report(...)`
dataclasses/signatures. Add:

```python
def score_branch_path(
    transcript: ParsedTranscript,
    expected_payload: dict,
    scenario: BranchScenario,
) -> dict[str, bool]:
    """Score one full branch path against command evidence and terminal output.

    Args:
        transcript: Normalized tool and assistant transcript.
        expected_payload: Real final `StageExitPayload` ground truth.
        scenario: Ordered fixture expectations.

    Returns:
        Every named criterion; compliance requires all values to be true.

    Raises:
        KeyError: `expected_payload` is not a valid shared `StageExitPayload`.
    """


def run_branch_probe(models: list[str], n: int) -> list[ProbeReport]:
    """Run both branch scenarios in fresh repositories for every model/run."""
```

Register `branch-path` as a distinct `--probe` choice and include it under `all`. Report variants
are `successful-rejoin` and `recovery`; do not merge their rates into `stage-exit/cold` or
`stage-exit/warm`.

### 5.2 Required criteria (REQ-EVAL-01, REQ-EVAL-02, REQ-EXIT-03/04)

`score_branch_path` returns these exact keys:

```python
{
    "ordered_command_results": bool,
    "all_commands_succeeded": bool,
    "exactly_one_sentinel": bool,
    "nested_steps_emitted_no_sentinel": bool,
    "nothing_after_sentinel": bool,
    "next_command_fenced": bool,
    "block_verbatim": bool,
    "correct_rejoin_or_recovery": bool,
}
```

Semantics:

- `ordered_command_results`: §4.2 matched the complete expected sequence.
- `all_commands_succeeded`: every matched command has `resultSeen`, `exitCode == 0`, and
  `isError is False`.
- `exactly_one_sentinel`: all `assistant_texts` together contain exactly one occurrence of
  `NEXT_STEPS_SENTINEL` from `00-core-definitions.md`.
- `nested_steps_emitted_no_sentinel`: no assistant text before the final terminal block contains the
  sentinel. This specifically rejects nested verify/fix ownership leaks.
- `nothing_after_sentinel`: the final non-whitespace content of `final_text` is exactly the
  sentinel; suffix checks alone are insufficient if an earlier duplicate exists.
- `next_command_fenced`: the expected payload's `primaryCommand` occurs in a real fenced block,
  using existing `_in_fenced_block(text: str, needle: str) -> bool`.
- `block_verbatim`: the expected payload's `nextSteps` occurs byte-for-byte in `final_text`.
- `correct_rejoin_or_recovery`: the successful scenario's primary command is the production
  successor; the recovery scenario's primary command equals its fixture recovery command and keeps
  the same feature/served-stage context.

### 5.3 Offline negative fixtures (REQ-EVAL-02)

In `tests/test_compliance_eval.py`, create pure transcript dictionaries (no live CLI/network) for:

1. missing tool result;
2. non-zero/error tool result;
3. reordered fix and re-verify calls;
4. duplicate terminal sentinel;
5. sentinel printed by a nested call;
6. correct sentinel followed by trailing prose;
7. prose-only claims with no Bash evidence;
8. verbatim-looking terminal block without the real final stage-exit command;
9. successful branch commands with the wrong feature or served stage; and
10. recovery output that incorrectly advances to production.

Each fixture asserts the specifically relevant criterion is false. Add positive offline tests for
both scenarios proving all criteria true. Also test JSON loader rejection for unknown version,
missing scenario, duplicate scenario, unsafe feature, empty command tokens, and wrong scenario
order. Existing stage-exit and R2 scorer tests remain unchanged except for additive transcript
fields.

## 6. Linear Baseline Documentation (REQ-EVAL-03, REQ-COMPAT-01/03)

Update `eval/README.md` without rewriting historical results. It must state verbatim in substance:

- the original `stage-exit/cold` and `stage-exit/warm` `forge-1-prd` baseline measures only the
  already-scripted linear authoring path;
- it is not evidence for verify/fix diversion compliance;
- `branch-path/successful-rejoin` and `branch-path/recovery` are separately reported cells and must
  not be averaged into or compared as replacements for the linear baseline;
- branch runs require actual ordered command results, not prose; and
- the live harness remains advisory/local-only, while `tests/test_compliance_eval.py` validates the
  fixture and scorer in CI.

Update the cost formula/table to include the two new cells when `--probe all` is used. Preserve the
current absent-driver behavior (prints skipped, returns 0), model pins, rate-over-N interpretation,
and statement that a low model score is not a correctness failure.

## 7. Error Handling

All guard failures use pytest assertions with exact skill/path context. Fixture/schema/harness
invariant failures raise `RuntimeError`; filesystem and JSON exceptions retain `OSError` and
`json.JSONDecodeError`. A live driver timeout/non-zero exit remains unscored data through
`run_session`, not an exception. A model compliance miss is a scored `RunResult` with
`compliant=False`, never a non-zero process exit.

The CLI returns non-zero only for harness defects such as an invalid static fixture, duplicate tool
IDs, impossible expected payload, or prelude/constant drift. Missing `claude` remains a successful
skip. Do not catch programming errors and relabel them as model misses.

## Public API and Internal Surface

Everything this document defines is **maintainer- and CI-facing**. None of it ships to a
project that installs feature-forge, and no skill, adapter, or end user calls into it.

- **User-facing:** none. `eval/run-compliance-eval.py` has a CLI, but its audience is
  maintainers running the compliance evaluation, not forge users; it is never invoked by a
  pipeline stage.
- **Test-only, importable by `tests/`:** `CanonicalExitSite` and `CANONICAL_EXIT_SITES`
  (§2.1), `INTENTIONALLY_EXCLUDED_SKILLS` (§2.1), and the contract assertions of §2.3. The
  coverage data is the guard's ground truth: adding a pipeline skill without adding its row
  is the exact failure §2 exists to catch.
- **Eval-only, importable by `eval/`:** the fixture types `ExpectedCommand`, `BranchScenario`,
  and `BranchFixture` (§3.2); `load_branch_fixture`, `build_branch_fixture`, `branch_prompt`,
  and `expected_branch_exit` (§3.2–§3.3); the evidence types `CommandEvidence` and
  `ParsedTranscript` with `parse_transcript` and `ordered_command_evidence` (§4); and
  `score_branch_path` with `run_branch_probe` (§5).
- **Private helpers:** `_extract_block`, `_render`, `_read_contract_surface` (§2.2), and
  `_git_init` (§3.3).
- **Consumed, not owned:** `expected_stage_exit` and `run_session` are existing eval helpers;
  §3.3 reuses them and the branch path must not fork a second copy (REQ-EVAL-03).
- **Fixture files are data, not API:** `eval/fixtures/<branch-fixture>.json` conforms to the
  §3.2 shape and is validated by `load_branch_fixture`; it carries no stability guarantee
  beyond that schema.

## 8. Dependencies

Implementation order:

1. `00-core-definitions.md` — `ExitStage`, `EXIT_STAGES`, `EXIT_OUTCOMES`,
   `NEXT_STEPS_SENTINEL`, `StageExitPayload`, and terminal ownership semantics.
2. `01-architecture-layout.md` — exact canon/eval/test ownership and sequencing.
3. The stage routing, state transition, and canonical skill specs that implement all nine direct
   exits; this guard must land after their call sites exist.
4. Existing source integrations:
   - `tests/test_stage_exit_protocol.py::_extract_block(name: str) -> str`
   - `tests/test_stage_exit_protocol.py::_render(block: str, **slots: str) -> str`
   - `eval/run-compliance-eval.py::run_session(cwd: Path, prompt: str, model: str) -> dict`
   - `eval/run-compliance-eval.py::parse_transcript(stdout: str) -> dict`
   - `eval/run-compliance-eval.py::expected_stage_exit(root: Path) -> dict`
   - `eval/run-compliance-eval.py::_in_fenced_block(text: str, needle: str) -> bool`
   - `eval/run-compliance-eval.py::_to_result(probe: str, model: str, variant: str, index: int, transcript: dict, scorer: Callable[[dict], dict[str, bool]]) -> RunResult`
   - `eval/run-compliance-eval.py::_probe_report(probe: str, model: str, variant: str, results: list[RunResult]) -> ProbeReport`

No runtime or dev dependency is added. Python 3.10+ stdlib, pytest, and the existing optional
`jsonschema` test skip remain sufficient.

## 9. Verification

- [ ] `CANONICAL_EXIT_SITES` equals the nine shared `EXIT_STAGES`, in order and without duplicates.
- [ ] Removing any one covered invocation or terminal-print contract fails
  `tests/test_stage_exit_protocol.py`.
- [ ] Loop and docs have positive scripted-contract tests; no obsolete terminal/bespoke assertion
  is merely deleted.
- [ ] Direct verify/fix require direct ownership; nested branch instructions emit no terminal block.
- [ ] `eval/fixtures/compliance/verify-fix-reverify.json` is not loaded by trigger eval globbing.
- [ ] Both branch scenarios build fresh schema-valid state and derive final output from the real CLI.
- [ ] Tool requests pair to results by ID and preserve request order.
- [ ] Missing, failed, reordered, duplicate, nested-sentinel, trailing-content, and prose-only
  negative fixtures fail the intended criterion.
- [ ] Successful rejoin and recovery positive fixtures pass every criterion.
- [ ] Exactly one sentinel occurs across all assistant output and the final sentinel has no trailing
  content.
- [ ] `eval/README.md` labels the linear and branch results separately.
- [ ] `python3 -m pytest tests/test_stage_exit_protocol.py tests/test_compliance_eval.py` passes.
- [ ] `python3 scripts/build-adapters.py` and `bash scripts/validate.sh` pass after all canon changes.
- [ ] `ruff check scripts/ eval/` passes.
- [ ] `smokeCommand` remains `null`; CHECK-I21 remains intentionally not-applicable.
