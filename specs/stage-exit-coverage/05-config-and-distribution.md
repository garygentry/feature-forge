# 05 — Configuration Diagnostics & Runtime Distribution

## Requirement Coverage

| REQ ID | Requirement | Section |
|---|---|---|
| REQ-CONFIG-01 | Visible warning names every duplicated object key | §2.2, §4 |
| REQ-CONFIG-02 | Effective config, stage exit, bootstrap, and other config consumers share one read path | §3 |
| REQ-CONFIG-03 | Duplicate keys remain warning-only and last-key-wins | §2.1, §3, §6.1 |
| REQ-CONFIG-04 | Detection applies recursively to every JSON object and key name | §2.1, §5.1 |
| REQ-REL-01 | Duplicate diagnostics and generated helper output are deterministic | §2, §5, §6.2 |
| REQ-COMPAT-02 | Existing projects require no config migration | §3.3, §6.1 |
| REQ-PERF-01 | Diagnostics add no network, history scan, or model turn | §6.3 |
| REQ-PERF-02 | The no-duplicate path remains operationally negligible | §2.3, §6.3 |
| REQ-OBS-02 | Human warnings identify the source, key, and compatibility action | §2.2, §4 |

## 1. Purpose and Scope

This document specifies the domain implementation and existing-module integrations for
recursive duplicate-key diagnostics in `forge.config.json`, plus the distribution consequences
for the two adapter-copied consumers that now carry the mirrored loader. It implements the shared contracts already defined
in `00-core-definitions.md` §8 and the file ownership/layout in
`01-architecture-layout.md` §§2–4; it does not redefine their shared types, stage-exit payloads,
or `UsageError` hierarchy.

The implementation adds **no source module**. It replaces only
project-config JSON reads in the existing consumers. It does **not** replace pipeline-state,
schema, sentinel, transcript, findings, or arbitrary CLI-payload parsing (tech-spec §§2.1,
3.9). Duplicate keys do not invalidate a project in this release: the final value remains the
effective value, exactly as with the current `json.loads` calls (REQ-CONFIG-03,
REQ-COMPAT-02).

## 2. Duplicate-Aware JSON Domain

### 2.1 Loader algorithm (REQ-CONFIG-03/04, REQ-REL-01)

Mirror the following pair of functions into **both** `scripts/forge-session.py` and
`scripts/forge-bootstrap.py`, with the exact public APIs declared in
`00-core-definitions.md` §8. Do **not** create a shared module: `01-architecture-layout.md`
§3.4 records why (the flat scripts are copied verbatim into six bundles and share no import
module by standing repository invariant), and `tests/test_json_loader_parity.py` holds the two
copies in sync. Each copy is preceded by a `#: mirrors ``load_json_with_duplicates`` in
<other file>` comment, matching the existing convention. The complete implementation contract is:

```python
#: mirrors ``load_json_with_duplicates``/``warn_duplicate_keys`` in scripts/forge-bootstrap.py
def load_json_with_duplicates(path: Path) -> tuple[object, list[str]]:
    """Load JSON with last-key-wins values and ordered duplicate key names.

    Args:
        path: UTF-8 JSON file to read.

    Returns:
        The parsed JSON value and duplicate key names in deterministic decoder-hook
        order. A repeated occurrence is appended whenever its key was already seen
        in that same object. Objects at every nesting depth use the hook.

    Raises:
        OSError: The path cannot be read as UTF-8 text.
        json.JSONDecodeError: The file is not valid JSON.
    """
    duplicate_keys: list[str] = []

    def object_from_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                duplicate_keys.append(key)
            result[key] = value
        return result

    text = path.read_text(encoding="utf-8")
    value = json.loads(text, object_pairs_hook=object_from_pairs)
    return value, duplicate_keys


def warn_duplicate_keys(path: Path, duplicate_keys: list[str]) -> None:
    """Write one deterministic warning for each reported duplicate occurrence.

    Args:
        path: Source file whose duplicate key was accepted.
        duplicate_keys: Ordered names returned by `load_json_with_duplicates`.

    Raises:
        OSError: The process cannot write to stderr.
    """
    for key in duplicate_keys:
        rendered_key = json.dumps(key, ensure_ascii=False)
        print(
            f"Warning: duplicate JSON key {rendered_key} in {path}; "
            "using the last value.",
            file=sys.stderr,
        )
```

The mirrored region is exactly the comment plus these two `def` blocks — no module docstring, no
`from __future__` line, and no imports: both scripts already import `json`, `sys`, and `Path`, and
`from __future__ import annotations` must precede all other statements, so copying one in would be
a `SyntaxError`. **Exactly one `#: mirrors …` comment precedes the pair in each file**, and the two
comments differ by design (each names the other file), which is why the drift guard compares only
from the `def` line onward and asserts the comment separately (`07-testing-strategy.md` §5.1).

`json.loads(..., object_pairs_hook=...)` invokes `object_from_pairs` for every object,
including objects inside arrays. Membership is local to each newly constructed `result`, so
the same key in two different objects is not a collision, while a repeated key within either
object is reported. Assignment is deliberately performed after detection on every pair; the
last assignment wins. Arrays, scalar roots, number handling, insertion ordering of surviving
dictionary entries, and all other stdlib JSON behavior remain unchanged (REQ-CONFIG-03/04).

The returned order is the deterministic order in which the stdlib decoder completes object
hooks; nested objects can therefore report before their containing object. Consumers must not
sort or deduplicate the list. This preserves evidence when a key appears three or more times
and avoids an unordered set in user-visible output (REQ-REL-01; tech-spec §3.9).

### 2.2 Warning contract (REQ-CONFIG-01, REQ-OBS-02)

The warning text is exact:

```text
Warning: duplicate JSON key "<key>" in <path>; using the last value.
```

`json.dumps` renders the key safely and visibly, including quotes, control characters, and
non-ASCII text. `<path>` is the same `Path` supplied by the caller. The warning identifies the
source and key and states the compatibility action. Each list entry produces one line; an empty
list produces no output. The function writes only to `sys.stderr` and returns `None`.

Warnings must never be printed to stdout, embedded in a JSON result, or converted into a
`UsageError`. A successfully parsed duplicate-bearing configuration retains the consumer's
normal exit code and result. An actual stderr I/O failure is an `OSError`; it is not
misclassified as malformed JSON (REQ-CONFIG-01/03).

Example:

```python
from pathlib import Path


config_path = Path("forge.config.json")
value, duplicates = load_json_with_duplicates(config_path)
warn_duplicate_keys(config_path, duplicates)
assert isinstance(value, dict)
```

Given `{"autoVerify": false, "autoVerify": true}`, `value["autoVerify"]` is `True`, stdout
is untouched, and stderr contains one warning naming `autoVerify` (REQ-CONFIG-01/03).

### 2.3 Complexity (REQ-PERF-01/02)

For a file with `n` characters and `p` object pairs, the loader is `O(n + p)` time. It holds
the input text, parsed value, and at most one duplicate-name entry per repeated occurrence:
`O(n + p)` memory. The no-duplicate path adds one dictionary membership check per object pair
and keeps an empty list. It performs one local file read and no filesystem traversal, subprocess,
Git command, network request, model turn, or schema load.

## 3. Shared Consumer Adoption

### 3.1 `scripts/forge-session.py` integration (REQ-CONFIG-01..04)

The exact existing source signatures, found in `scripts/forge-session.py`, are:

```python
def _load_config(config_path: Path) -> dict: ...
def _config_value(config_path: Path, key: str): ...
def build_rows(specs_dir: Path, config: dict | None = None) -> list[FeatureRow]: ...
def stage_exit(
    feature: str,
    stage: str,
    specs_dir: Path,
    config_path: Path,
    epic: str | None,
    host: str,
    next_feature: str | None,
) -> dict: ...
def resolve_loop_runner(config_path: Path, schema_path: Path) -> dict[str, object]: ...
```

`stage_exit` is extended separately to the signature in `00-core-definitions.md` §3. This
configuration change does not introduce another stage-exit API.

Place the mirrored loader pair (§2.1) at module scope in `scripts/forge-session.py`, immediately
above `_load_config`, preceded by its `#: mirrors …` comment. No new import is required — `json`,
`sys`, and `Path` are already imported there.

Replace `_load_config` internally, retaining its exact import path and signature:

```python
def _load_config(config_path: Path) -> dict:
    """Read config into a dict, warning on duplicates and tolerating bad input."""
    try:
        value, duplicate_keys = load_json_with_duplicates(config_path)
    except (OSError, json.JSONDecodeError):
        return {}
    warn_duplicate_keys(config_path, duplicate_keys)
    return value if isinstance(value, dict) else {}
```

This single adoption point automatically covers the current consumers found in source:

- `_config_value`, and therefore `context-usage` configuration;
- `doctor_report` and navigator/backlog diagnostics;
- `reconcile-branch` and `check-epic-base` config snapshots;
- `stage_exit`, including `autoVerify`, `autoVerifyStages`, and `autoFix`;
- `resolve_loop_runner` / `effective-config`;
- the `rank-features` command's config-fed `build_rows` call.

No caller implements a second duplicate hook or formatter. A command that intentionally invokes
`_load_config` more than once may emit the warning once per actual read; there is no process-global
cache or hidden suppression state. `_load_config` preserves its established missing, unreadable,
malformed, scalar-root, and array-root behavior: return `{}` rather than fail. Consequently
`effective-config` still resolves malformed/missing project config to schema defaults at exit 0,
and stage closure retains its existing config fallback (REQ-CONFIG-03, REQ-COMPAT-02).

`_loop_runner_defaults` continues to parse the trusted bundled schema directly. State readers,
Git-object readers, transcript JSON-lines parsing, and CLI JSON parsing continue using their
current `json.loads` policies; they are not forge config consumers (tech-spec §3.9).

### 3.2 `scripts/forge-bootstrap.py` integration (REQ-CONFIG-01..03)

The only real `forge.config.json` read in `scripts/forge-bootstrap.py` is the commit-prefix read.
The exact existing integration signature found in source is:

```python
def commit(target: Path, answers: Answers, stage_only: bool) -> CommitResult: ...
```

Place the mirrored loader pair (§2.1) at module scope in `scripts/forge-bootstrap.py`, immediately
above `commit(...)`, preceded by its `#: mirrors …` comment. No new import is required — `json`,
`sys`, and `Path` are already imported there.

Within `commit`, replace only the direct `json.loads((target /
"forge.config.json").read_text(...))` block:

```python
    config_path = target / "forge.config.json"
    try:
        config_value, duplicate_keys = load_json_with_duplicates(config_path)
    except (OSError, json.JSONDecodeError) as exc:
        raise UsageError(f"cannot read forge.config.json: {exc}") from exc
    warn_duplicate_keys(config_path, duplicate_keys)
    if not isinstance(config_value, dict):
        raise UsageError("cannot read forge.config.json: root must be a JSON object")
    prefix = config_value.get("commitPrefix") or "forge"
```

A duplicate `commitPrefix` therefore warns and the final prefix determines the commit message.
Malformed/unreadable config still raises the shared `UsageError` and maps to CLI exit 2. An
object-root check makes the operation's existing object precondition explicit rather than
allowing an untyped `.get` failure. `write_config(...)` remains a deterministic writer and does
not need duplicate detection; freshly serialized dictionaries cannot contain duplicate keys.
Sentinel JSON and `--answers` JSON are separate protocols and retain their current parsers.

### 3.3 Compatibility matrix (REQ-CONFIG-03, REQ-COMPAT-02)

| Input | `forge-session.py` policy | `forge-bootstrap.py commit` policy |
|---|---|---|
| Missing/unreadable | Existing `{}` fallback | Existing actionable `UsageError`, exit 2 |
| Malformed JSON | Existing `{}` fallback | Existing actionable `UsageError`, exit 2 |
| Non-object root | `{}` fallback | `UsageError`, exit 2; commit requires an object |
| Valid object, no duplicates | Existing value; no warning | Existing value; no warning |
| Valid object, duplicates | Last value wins; warning(s), normal exit | Last value wins; warning(s), normal exit |

No migration, rewrite, normalization, or strict duplicate rejection is introduced. In
particular, duplicate `autoVerify`, arbitrary top-level keys, nested `loopRunner` keys, nested
`autoVerifyStages` keys, and objects nested inside arrays all use the same algorithm
(REQ-CONFIG-02..04).

## 4. stdout, stderr, and CLI Error Contract

For every successful config consumer (REQ-CONFIG-01/03, REQ-OBS-02):

1. Structured `--json` output remains the sole content on stdout and must still parse with
   `json.loads(result.stdout)`.
2. Human-mode output remains on stdout in its existing format.
3. Duplicate warnings are newline-terminated stderr lines in loader order.
4. Duplicate warnings do not change exit 0 to exit 1 or 2.
5. No warning dumps, rewrites, or reserializes the full config.

Malformed/missing handling remains consumer-owned: `load_json_with_duplicates` raises built-in
`OSError` or `json.JSONDecodeError`; session `_load_config` degrades them to `{}`, while bootstrap
wraps them in the shared `UsageError` from its existing module and emits its normal `Error:` line
at exit 2. Neither mirrored copy may reference `UsageError` or any other consumer-specific symbol. Error
translation stays in the caller. This is not merely hierarchy hygiene (`00-core-definitions.md`
§7): a copy that referenced its host script's symbols could not stay byte-identical to the other,
and `tests/test_json_loader_parity.py` would fail.

Example subprocess expectations:

```python
result = subprocess.run(
    [
        sys.executable,
        str(SCRIPTS / "forge-session.py"),
        "effective-config",
        "--config",
        str(config_path),
        "--json",
    ],
    capture_output=True,
    text=True,
)
assert result.returncode == 0
json.loads(result.stdout)
assert 'duplicate JSON key "bin"' in result.stderr
```

## 5. Runtime-Helper Distribution

### 5.1 Generator integration (tech-spec §§2.2, 3.9; REQ-REL-01)

The exact existing APIs and constant found in `scripts/build-adapters.py` are:

```python
RUNTIME_HELPERS: tuple[str, ...] = (
    "forge-root.sh",
    "forge-init.sh",
    "epic-manifest.py",
    "forge-session.py",
    "validate-traceability.py",
    "forge-bootstrap.py",
)

def run_self_containment_pass(
    bundle_root: Path,
    repo_root: Path,
    skills: tuple[SkillRecord, ...],
) -> None: ...

def build_tree(root: Path, dest: Path) -> tuple[EmitResult, ...]: ...
```

`RUNTIME_HELPERS` is **unchanged** — the mirrored loader lives inside the two scripts already in
that set, so no entry is added and no copy loop or emitter special case is needed. `build_tree` calls `run_self_containment_pass` once for each
of the existing targets (`claude`, `codex`, `copilot`, `cursor`, `gemini`, and `pi`); that pass
copies every runtime helper from `<repo>/scripts/<name>` to
`<bundle>/scripts/<name>`.

The existing pass remains authoritative:

- assert the destination is contained by `bundle_root` before copying;
- use `shutil.copyfile`, with no generated provenance header and no `copystat`;
- set Python helper mode to `0644`;
- assert source/copy byte identity before host-specific support translation;
- for Pi, permit only the existing `/feature-forge:` to `/skill:` substitution and verify the
  transformed helper against that expected text.

The mirrored loader contains no host command string, so it survives adapter generation unchanged
inside both consumers, including Pi. **No import has to resolve at runtime**, which is the point:
a bundle cannot fail on a missing or mislocated sibling module, because there is no sibling module
(REQ-CONFIG-02, REQ-COMPAT-02; `01-architecture-layout.md` §3.4).

### 5.2 Generated-output rules (tech-spec §2.2; project generation constraint)

Never hand-edit either generated consumer under `adapters/*/scripts/`. Implement in
`scripts/`, update generator fixtures, and run:

```text
python3 scripts/build-adapters.py
```

The generated copies intentionally have no `GENERATED — DO NOT EDIT` header because runtime
helpers use the byte-copy path, not frontmatter/canon emitters. Provenance is enforced by the
runtime-helper list, copy assertions, deterministic generation, and drift guard. The source
helper plus all generated adapter copies must land in the same implementation change.

Update the committed `expected-adapters/<agent>/scripts/` snapshots for the two changed
consumers. No new fixture file is added. These are test fixtures, not an
alternative production source. A full regenerate atomically replaces the adapter tree, so no
adapter target may retain a stale consumer.

### 5.3 Distribution failures

A missing source helper causes the generator's existing file-copy failure and aborts generation;
it must not silently omit the helper. Containment or byte-divergence failures remain generator
defects (`AssertionError` or the existing Pi `SystemExit`) and prevent atomic publication.
`CanonError` handling and staging-tree cleanup remain unchanged. The mirrored loader cannot fail to
resolve at runtime because it is in-file; the corresponding staleness risk is a bundle whose consumer
copy diverged from canon, which the byte-identity assertion in §8.2 and
`tests/test_json_loader_parity.py` cover. Consumers must not fall back to a direct `json.loads`.

## 6. Determinism, Compatibility, and Performance

### 6.1 Last-key-wins compatibility (REQ-CONFIG-03, REQ-COMPAT-02)

For every object, the implementation reproduces stdlib's existing final-value semantics.
Configuration is read-only: no warning path writes the file, changes key order, inserts defaults,
or performs schema coercion. Unknown keys survive in the parsed dictionary as today. Existing
single-key projects produce identical effective values and no added output. Existing duplicate
projects gain stderr diagnostics only and continue without migration.

### 6.2 Determinism (REQ-REL-01)

Given identical UTF-8 bytes and the same displayed `Path`, parsing returns equal values and equal
ordered duplicate lists, and warning bytes are identical. No timestamp, absolute-path resolution,
locale-dependent sorting, randomization, or environment lookup is introduced. Adapter generation
continues using the existing deterministic target order and atomic whole-tree publication.

### 6.3 Operational bounds (REQ-PERF-01/02)

The implementation reads each config only where the consumer already read it. It must not add a
repository scan, Git history lookup, subprocess, network call, dependency, cache daemon, or model
turn. Python 3.10+ stdlib remains the only runtime requirement. Repeated reads by an existing
command retain existing I/O shape; this feature does not add a new read solely to diagnose keys.
The small `forge.config.json` files make the hook and duplicate list negligible relative to CLI
startup and existing stage-exit processing.

## Public API and Internal Surface

- **Repository-importable module:** none. `load_json_with_duplicates(path) -> tuple[object,
  list[str]]` and `warn_duplicate_keys(path, duplicate_keys) -> None` (§2.1–§2.2) are **mirrored
  private helpers**, one copy per consuming script, not a shared import surface. No **production** code
  outside its own script may call a copy, and no adapter bundle exposes them as a module; `tests/`
  may load either script via `importlib.util.spec_from_file_location` to exercise a copy directly
  (`07-testing-strategy.md` §5.1). This preserves
  the self-contained-scripts rule (`01-architecture-layout.md` §3.4) rather than excepting it;
  `tests/test_json_loader_parity.py` is what keeps the copies honest.
- **User-facing CLI behavior (no new command):** the duplicate-key warning contract of §2.2 and
  the stdout/stderr split of §4. Warnings go to stderr so `--json` stdout stays machine-
  parseable; that separation is the contract, not an implementation detail.
- **Private helpers:** `_load_config` and `_config_value` in each consuming script (§3.1–§3.2).
  They stay private and per-script; only the duplicate-aware loader is shared.
- **Build-time / maintainer-only:** `RUNTIME_HELPERS`, `run_self_containment_pass(...)`, and
  `build_tree(root, dest)` in `scripts/build-adapters.py` (§5). These run at adapter generation
  time and are never present in, or callable from, an installed bundle. `commit(...)` in
  `forge-bootstrap.py` is likewise internal to bootstrap.
- **Generated output is not an API:** everything under `adapters/` is regenerated wholesale
  (§5.2). Editing a generated file is not an extension point — it is drift the adapter gate
  fails on.
- **Test/eval-only:** none.

## 7. Dependencies

The following specifications must be implemented first:

- `00-core-definitions.md` — authoritative duplicate-loader APIs, warning contract ownership,
  built-in error behavior, and shared `UsageError` policy.
- `01-architecture-layout.md` — source/emitted paths, mirrored-copy placement, consumer ownership, and
  implementation sequence.

Existing source integrations required by this document:

- `scripts/forge-session.py` at the exact signatures in §3.1;
- `scripts/forge-bootstrap.py::commit(target: Path, answers: Answers, stage_only: bool) -> CommitResult`;
- `scripts/build-adapters.py::run_self_containment_pass(...)` and `build_tree(...)` in §5.1;
- the six current `adapters/<agent>/scripts/` layouts inspected in the repository.

No external runtime dependency, package export, or service is added.

## 8. Verification

### 8.1 Domain and consumer tests (REQ-CONFIG-01..04, REQ-COMPAT-02)

Update `tests/test_effective_config.py` and bootstrap coverage in
`tests/test_forge_bootstrap.py` to prove:

- a top-level duplicate warns and the last value is effective;
- nested duplicates in `loopRunner`, `autoVerifyStages`, an arbitrary object, and an object inside
  an array are detected (not only `autoVerify`);
- three occurrences preserve the final value and produce one warning for each repeated
  occurrence;
- identical key names in distinct non-duplicated objects do not warn;
- malformed/missing session config retains defaults and its current exit 0 policy;
- no-duplicate input leaves stderr empty and output unchanged;
- `--json` stdout remains independently parseable while warnings appear only on stderr;
- bootstrap commit with duplicate `commitPrefix` uses the last prefix, warns, and succeeds;
- bootstrap malformed/unreadable config still exits 2 with `Error:` and no false JSON stdout.

Tests should execute the real CLI subprocesses where stdout/stderr and exit behavior matter.
Pure recursive parser cases may load either consumer script directly via
`importlib.util.spec_from_file_location`, as the existing tests do (both filenames are hyphenated,
so neither is importable by name); they must call the real in-file functions rather than reproduce
the hook in test code.

### 8.2 Distribution tests (tech-spec §8.4; REQ-REL-01)

Update `tests/test_build_adapters.py` and the minimal-canon snapshots to verify:

- `RUNTIME_HELPERS` still has exactly six entries and no new file appears under `scripts/` for any
  of the six `AGENT_TARGETS`;
- each emitted helper is mode `0644` and has no generated header;
- each emitted helper's bytes equal the fixture source (including Pi, because the helper has no
  slash-command prefix);
- both emitted consumers carry the mirrored loader byte-identically to canon;
- each emitted consumer still executes and its in-file loader is reachable (no import resolution
  is involved);
- two builds remain tree-identical, a full regenerate purges orphans, and `--check` detects a
  missing/stale generated helper.

### 8.3 Repository gates

Run in this order after implementation:

```text
python3 scripts/build-adapters.py
bash scripts/validate.sh
ruff check scripts/ eval/
```

Acceptance requires all of the following:

- [ ] Every duplicate-bearing consumer preserves last-key-wins and emits the exact stderr warning.
- [ ] Valid JSON stdout parses without filtering warning text.
- [ ] Missing/malformed behavior matches §3.3.
- [ ] No direct project-config `json.loads` remains in the two specified consumer sites.
- [ ] No new runtime helper ships; both mirrored copies survive generation byte-identically, and
      `tests/test_json_loader_parity.py` passes against canon.
- [ ] Generated runtime helpers were regenerated, not hand-edited.
- [ ] The drift guard reports no adapter difference.
- [ ] No runtime dependency, network call, history scan, model turn, or config migration was added.
