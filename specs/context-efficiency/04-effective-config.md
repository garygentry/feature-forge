# 04 — `effective-config` Subcommand (R5)

> HOW R5 ships. Adds a single `forge-session.py effective-config` subcommand that
> resolves the `loopRunner` configuration by reading the schema's
> machine-readable `default` keywords at runtime and deep-merging the user's
> `loopRunner` block over them — so **forge-5-loop and forge-4-backlog never read
> the ~2k-word `forge-config-schema.json` just to fill defaults** (REQ-R5-01),
> and default resolution is **deterministic** rather than a model merge
> (REQ-R5-02).
>
> Builds on `00-core-definitions.md` §3 (forge-session script conventions), §6
> (the `effective-config` contract summary), and §10 (the R5 invariant). Reuses
> the shared forge-session dispatch/exit conventions specified in
> `03-state-verbs.md`. Does not restate those; references them.

## Requirement Coverage

| REQ ID | Requirement | Section |
|--------|-------------|---------|
| REQ-R5-01 | Resolved `loopRunner` config without the model reading the full config schema | §2 (CLI contract), §3 (default extraction), §4 (deep-merge), §7 (consumer change) |
| REQ-R5-02 | Deterministic resolution eliminates "model mis-merged the defaults" errors | §3, §4 (script merges, model does not), §5 (output), §8 (worked example) |
| REQ-R4-03 | Config schema remains the single source of truth (no hardcoded duplication) | §3 (defaults read from schema at runtime), §9 (drift guard) |
| REQ-MAINT-01 (R5 slice) | Drift guard asserts `effective-config` output validates against `forge-config-schema.json` | §9 (drift-guard requirement) |

---

## 1. Purpose & Scope

**Purpose.** Move `loopRunner` default resolution out of model prose and into a
deterministic `forge-session.py` subcommand. Today forge-5-loop and
forge-4-backlog read `forge-config-schema.json` (236 lines, ~2k words) largely to
learn the 22 `loopRunner` defaults, then the model mentally merges any user
overrides on top. R5 replaces that with one subcommand call that returns the
fully-resolved block.

**In scope (this document):**

- The `effective-config` CLI contract (§2).
- Reading `properties.loopRunner.properties.*.default` from the schema — full
  Python, stdlib-only (§3).
- Deep-merging the user's `loopRunner` block over those defaults via the existing
  `_load_config` (§4).
- argparse registration + the `if args.cmd == "effective-config"` dispatch branch,
  matching forge-session's style (§6).
- The `--json` output shape (resolved 22-field object) and readable-summary sketch
  (§5).
- Error handling: unreadable schema → exit 2; loop stages degrade to existing
  behavior (§10).
- The consumer change in forge-5-loop / forge-4-backlog (§7).
- The R5 drift-guard requirement (§9).

**Out of scope:** the R4 state verbs (`03-state-verbs.md`); any change to the
schema *content* (unchanged — tech-spec §4); placeholder/template substitution
(`{bin}`, `{backlogDir}`, `{iterations}` stay literal in the resolved output —
`effective-config` resolves **defaults**, not templates; see §3 note).

**Shared-pattern relationship (tech-spec §3.7, `01-architecture-layout.md §5`).**
R5 ships **before** R4 deliberately: it is the smaller, lower-risk unit that
establishes the "add a forge-session subcommand + stdlib schema drift-guard"
pattern. R4 (the seven state verbs) then reuses that same pattern at larger scale.
Both are additive functions in the same `forge-session.py`, independently named,
so a `git revert` of one leaves the other intact (`01-architecture-layout.md §4`).

## 2. CLI Contract

```
python3 forge-session.py effective-config \
    [--config ./forge.config.json] \
    [--schema <path>] \
    [--json]
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--config` | `./forge.config.json` | Path to the project config. Read via the existing `_load_config` (line 526), which tolerates a missing/corrupt file by returning `{}` (so a project with no config resolves to pure defaults). |
| `--schema` | the bundled `references/forge-config-schema.json` resolved relative to the script (§3.2) | The schema whose `properties.loopRunner.properties.*.default` supply the defaults. Overridable for tests. |
| `--json` | off | When set, emit the resolved `loopRunner` object as `json.dumps(payload, indent=2, ensure_ascii=False)` (00-core-definitions §3.1). When absent, emit the readable summary (§5.2). |

**Exit codes (00-core-definitions §3.2 — 0/2, NO exit 1):**

- `0` — resolved config emitted (JSON or summary).
- `2` — the schema is unreadable/unparseable, or bad args. Deterministic failure
  surfaced on stderr as `Error: …`; the loop stages then fall back to their
  existing behavior (§10, tech-spec §7).

The `--config` flag intentionally does **not** cause exit 2 on a missing/corrupt
file: `_load_config` already degrades that to `{}` (the schema defaults then stand
alone). Only an unreadable **schema** is fatal, because without it there are no
defaults to resolve.

## 3. Schema-default extraction (stdlib-only, C-2)

### 3.1 The premise (verified)

Every one of the **22** `loopRunner` fields in `forge-config-schema.json` carries
a machine-readable `default`. Verified field list (from
`properties.loopRunner.properties`, the source of truth):

```
name, bin, runCommand, eventStreamCommand, validateCommand, statusCommand,
statusJsonCommand, listCommand, followCommand, logCommand, watchCommand,
versionCommand, agentArgument, agentsProbeCommand, defaultAgent,
preconditionFile, stateDir, logFile, setupHint, installHint, schemaVersion,
minRunnerVersion
```

Representative defaults (the full 22 live in the schema — do NOT hardcode them,
REQ-R4-03):

| Field | Default |
|-------|---------|
| `name` | `"rauf"` |
| `bin` | `"rauf"` |
| `runCommand` | `"{bin} loop run . --backlog {backlogDir} --iterations {iterations}"` |
| `agentArgument` | `"--agent {agent}"` |
| `defaultAgent` | `""` (empty string — a real, non-null default) |
| `preconditionFile` | `".rauf.json"` |
| `stateDir` | `".rauf"` |
| `schemaVersion` | `"1"` |
| `minRunnerVersion` | `"0.6.0"` |

**Note on templates.** Some defaults contain `{placeholder}` tokens (`{bin}`,
`{backlogDir}`, `{iterations}`, `{agent}`). `effective-config` copies these
**literally** — it resolves *defaults*, not the call-time template substitution
(which forge-5-loop performs later at launch). The resolved output therefore still
contains `{bin} loop run …`, exactly as the model would have carried it.

**Precedent.** `tests/test_config_defaults_parity.py` already stdlib-parses these
same `properties.*.default` values (`json.load` + `props.get(key, {})` +
`"default" in prop`). The extraction below mirrors that approach exactly — no
`jsonschema`, no third-party import (C-2, 00-core-definitions §3.4).

### 3.2 Locating the bundled schema

The schema lives at `references/forge-config-schema.json`, a sibling of the
`scripts/` directory. Resolve it relative to the script file so the subcommand
works regardless of the caller's cwd:

```python
def _default_schema_path() -> Path:
    """Return the bundled forge-config-schema.json path (sibling references/ dir).

    Resolved relative to this script file so `effective-config` works from any
    cwd. Overridable via the ``--schema`` flag (chiefly for tests).

    Returns:
        The Path to ``references/forge-config-schema.json`` next to ``scripts/``.
    """
    return Path(__file__).resolve().parent.parent / "references" / "forge-config-schema.json"
```

> If `Path(__file__).resolve().parent.parent / "references"` is not the canonical
> location on the target adapter build, WARNING: verify the bundled-schema path at
> implementation time — the extraction logic is unaffected, only this resolver.
> (In the canonical repo layout `scripts/forge-session.py` and
> `references/forge-config-schema.json` are siblings under the plugin root, so
> `parent.parent / "references"` is correct.)

### 3.3 Reading the defaults

```python
def _loop_runner_defaults(schema_path: Path) -> dict[str, object]:
    """Extract every ``loopRunner`` field's schema ``default``.

    Reads ``properties.loopRunner.properties.<field>.default`` for each field.
    Stdlib-only (``json`` + dict access), mirroring
    ``tests/test_config_defaults_parity.py`` — no ``jsonschema`` (C-2). The schema
    is the single source of truth; nothing here is hardcoded (REQ-R4-03).

    Only fields that actually declare a ``default`` keyword are included. Per the
    verified schema, all 22 ``loopRunner`` fields do; a field without one would be
    a schema regression caught by the drift guard (§9), not silently dropped here.

    Args:
        schema_path: Path to ``forge-config-schema.json``.

    Returns:
        A dict mapping each ``loopRunner`` field name to its declared default
        value (templates such as ``"{bin} loop run …"`` are returned literally).

    Raises:
        UsageError: If the schema is missing, unreadable, unparseable, or lacks a
            ``loopRunner.properties`` object — a deterministic failure that must
            exit 2 (§10). Never returns partial/empty defaults silently.
    """
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise UsageError(f"config schema unreadable: {schema_path} ({exc})") from exc
    except json.JSONDecodeError as exc:
        raise UsageError(f"config schema is not valid JSON: {schema_path} ({exc})") from exc

    props = (
        schema.get("properties", {})
        .get("loopRunner", {})
        .get("properties")
    )
    if not isinstance(props, dict) or not props:
        raise UsageError(
            f"config schema has no loopRunner.properties object: {schema_path}"
        )

    return {
        field: spec["default"]
        for field, spec in props.items()
        if isinstance(spec, dict) and "default" in spec
    }
```

**Why `UsageError` (not degrade-to-`{}`).** Unlike `_load_config` — where a
missing project config legitimately means "use pure defaults" — a missing/broken
**schema** means there are *no defaults to resolve*. Emitting partial defaults
would silently hand the loop a wrong config (the exact failure class R5 exists to
kill). `UsageError` routes to exit 2 via the existing top-level handler
(00-core-definitions §3.2), so the loop stages fall back to their prior behavior
deterministically (§10).

## 4. Deep-merge over user config

The user's `loopRunner` block (if any) overrides the defaults field-by-field. Each
`loopRunner` field is a scalar (string / empty-string), so the merge is a flat
per-key override — no nested-object recursion is needed for the current schema.
The merge is still written as a small, explicit helper so a future nested field
would be an obvious edit site, and so the "deep-merge" intent from tech-spec §3.5
is honored precisely.

```python
def resolve_loop_runner(config_path: Path, schema_path: Path) -> dict[str, object]:
    """Resolve the effective ``loopRunner`` config: schema defaults + user overrides.

    Reads the 22 schema defaults (§3.3), then merges the user's ``loopRunner``
    block (from ``forge.config.json`` via the existing ``_load_config``, line 526)
    OVER them. A user field replaces the default; an absent field keeps the
    default. The result is the fully-resolved block the loop consumes — computed
    deterministically so no model ever merges by hand (REQ-R5-02).

    Args:
        config_path: Path to ``forge.config.json`` (``_load_config`` tolerates a
            missing/corrupt file, yielding pure defaults).
        schema_path: Path to ``forge-config-schema.json`` (source of the defaults).

    Returns:
        The resolved ``loopRunner`` object: every schema-defaulted field present,
        with user overrides applied.

    Raises:
        UsageError: If the schema is unreadable/unparseable (propagated from
            ``_loop_runner_defaults``) — exit 2, deterministic failure (§10).
    """
    resolved: dict[str, object] = dict(_loop_runner_defaults(schema_path))

    user_config = _load_config(config_path)          # existing helper, L526; {} on error
    user_loop_runner = user_config.get("loopRunner")
    if isinstance(user_loop_runner, dict):
        for key, value in user_loop_runner.items():
            # Flat override: a user value replaces the default for that field.
            # (A future nested loopRunner field would recurse here; today all 22
            # fields are scalars, so a shallow override is exact.)
            resolved[key] = value

    return resolved
```

**Reuse, don't reimplement.** `_load_config(config_path: Path) -> dict` already
exists at line 526 (verified signature and degrade-to-`{}` behavior). R5 imports
nothing new and adds no config-reading path of its own.

**Unknown user keys.** If a user's `loopRunner` carries a key not in the schema
defaults (e.g. a typo, or a forward-compat field), it is preserved in the resolved
output — the model would have carried it through too, so this keeps parity
(REQ-R5-02, 00-core-definitions §10 R5 invariant). The config schema, not
`effective-config`, is the authority that flags an unknown key at author time.

## 5. Output

### 5.1 `--json` shape (the resolved 22-field object)

`--json` emits the resolved block via the shared emission convention
(`print(json.dumps(payload, indent=2, ensure_ascii=False))`, 00-core-definitions
§3.1). The payload is the resolved `loopRunner` object itself — all 22 fields,
defaults plus overrides:

```jsonc
{
  "name": "rauf",
  "bin": "rauf",
  "runCommand": "{bin} loop run . --backlog {backlogDir} --iterations {iterations}",
  "eventStreamCommand": "{bin} loop run . --backlog {backlogDir} --iterations {iterations} --ndjson",
  "validateCommand": "{bin} backlog validate . --backlog {backlogDir} --specs-dir {specsDir} --json",
  "statusCommand": "{bin} status . --backlog {backlogDir}",
  "statusJsonCommand": "{bin} status . --backlog {backlogDir} --json",
  "listCommand": "{bin} backlog list . --backlog {backlogDir} --json",
  "followCommand": "{bin} follow . --backlog {backlogDir}",
  "logCommand": "{bin} log . --backlog {backlogDir} --follow",
  "watchCommand": "{bin} status . --backlog {backlogDir} --json",
  "versionCommand": "{bin} version --json",
  "agentArgument": "--agent {agent}",
  "agentsProbeCommand": "{bin} agents --json",
  "defaultAgent": "",
  "preconditionFile": ".rauf.json",
  "stateDir": ".rauf",
  "logFile": "rauf.log",
  "setupHint": "Run `rauf install .` to install rauf's per-project artifacts (.rauf/, RAUF.md, schema), then re-run forge-5.",
  "installHint": "Provision rauf for a multi-agent setup with the cross-agent installer: `npx @garygentry/feature-forge install` …",
  "schemaVersion": "1",
  "minRunnerVersion": "0.6.0"
}
```

> This is the **all-defaults** output (empty/absent config). Values shown for
> `setupHint`/`installHint` are truncated here for readability; the resolved
> output carries the schema's full default strings verbatim.

The dispatch prints this object directly (it is the resolved slice the caller
wants). Consumers parse it with `json.loads` or `jq`; there is no wrapping
envelope, matching the "prints the resolved `loopRunner`" contract
(00-core-definitions §6, tech-spec §5).

### 5.2 Readable summary (non-`--json`) — sketch

Provide a `_print_effective_config(resolved)` helper (per the dedicated-printer
convention, 00-core-definitions §3.1) that renders an aligned key/value table to
stdout:

```python
def _print_effective_config(resolved: dict[str, object]) -> None:
    """Print the resolved loopRunner config as an aligned key: value table.

    Args:
        resolved: The resolved loopRunner object from ``resolve_loop_runner``.
    """
    print("Effective loopRunner config:")
    width = max((len(k) for k in resolved), default=0)
    for key in sorted(resolved):
        print(f"  {key.ljust(width)} : {resolved[key]!r}")
```

The summary is a human monitoring aid; the loop stages consume `--json`.

## 6. argparse registration + dispatch

Register the subparser in `main()` alongside the existing ones (00-core-definitions
§3.1; the `stage-exit` parser at L1750 is the pattern), and add the dispatch branch
to the `if args.cmd == …` chain (the `stage-exit` branch at L1840 is the pattern),
inside the existing top-level `try` that already yields the 0/2 exit contract
(L1857–1862).

**Subparser (add near the other `sub.add_parser(...)` calls, ~L1765):**

```python
    p_eff = sub.add_parser(
        "effective-config",
        help="Resolve the loopRunner config from schema defaults + user overrides",
    )
    p_eff.add_argument(
        "--config", default="./forge.config.json", help="forge.config.json path"
    )
    p_eff.add_argument(
        "--schema", default=None,
        help="forge-config-schema.json path (default: bundled references/ copy)",
    )
    p_eff.add_argument("--json", action="store_true", dest="json_output")
```

**Dispatch branch (add to the chain, before the final `raise UsageError`):**

```python
        if args.cmd == "effective-config":
            schema_path = (
                Path(args.schema) if args.schema else _default_schema_path()
            )
            resolved = resolve_loop_runner(Path(args.config), schema_path)
            if args.json_output:
                print(json.dumps(resolved, indent=2, ensure_ascii=False))
            else:
                _print_effective_config(resolved)
            return 0
```

The `UsageError` raised by `_loop_runner_defaults` (unreadable schema) propagates
to the existing handler and returns 2 (00-core-definitions §3.2); no new
exception type and no new exit code are introduced. See `03-state-verbs.md` for
the shared forge-session dispatch conventions this branch matches.

**Module docstring.** Add one usage line to the top-of-file docstring block
(00-core-definitions §3, `01-architecture-layout.md §2.1`):

```
    python3 forge-session.py effective-config [--config FILE] [--schema PATH] [--json]
```

## 7. Consumer change (forge-5-loop / forge-4-backlog)

R5's payoff is at the two consumers (tech-spec §3.5). Both currently read the full
schema to learn defaults; after R5 they call `effective-config`.

**Before (forge-5-loop / forge-4-backlog SKILL body, conceptually):**

> Read `references/forge-config-schema.json`; find `loopRunner`; note each
> field's `default`; merge the project's `loopRunner` overrides on top to get the
> effective config.

**After (both SKILL bodies):**

> Resolve `$R` via the plugin-root prelude shown at the top of this skill (the R2
> compact-prelude form, 00-core-definitions §8), then run:
>
> ```
> python3 "$R/scripts/forge-session.py" effective-config --config ./forge.config.json --json
> ```
>
> Use the returned object as the effective `loopRunner` config. Do not read the
> config schema for defaults.

**Constraints on the consumer edit:**

- **forge-5-loop is at the 300-line cap** (`01-architecture-layout.md §2.2`).
  The R5 consumer edit MUST be a **1-for-1 swap** — the "read the schema for
  defaults" instruction is replaced by the one-line call, net **zero** added
  lines. It must not push schema text back into the body (mirrors REQ-R6-03's
  cap discipline). If the swap would add net lines, WARNING: flag it and trim in
  review rather than exceeding the cap.
- **forge-4-backlog** has headroom; same swap.
- Both edits are **relocations of a read-for-defaults step into a script call**
  (00-core-definitions §2, script-extraction) — no interactive-protocol prose
  changes (REQ-BEHAV-02).
- The `references/forge-config-schema.json` citation may still be needed elsewhere
  (author-time validation guidance); R5 only removes the *read-for-defaults*
  step, not the file. The schema stays cited so it still ships (REQ-PORT-01).

**Portability (REQ-PORT-01/02).** No new reference file is introduced by R5, so
there is no new citation to add for fan-out; `forge-session.py` is already a
`RUNTIME_HELPER` that ships to every adapter (tech-spec §6.9,
`01-architecture-layout.md §3.2`). The new subcommand rides along automatically.
The one-line call is host-neutral (no `/clear`, no Claude-only tool names —
REQ-PORT-02).

## 8. Worked example

**Project config** `forge.config.json` with two `loopRunner` overrides (a custom
runner name/bin and a pinned agent):

```jsonc
{
  "specsDir": "./specs",
  "loopRunner": {
    "name": "ralph",
    "bin": "/usr/local/bin/ralph",
    "defaultAgent": "codex"
  }
}
```

**Command:**

```
python3 forge-session.py effective-config --config ./forge.config.json --json
```

**Resolved output** (defaults for all 22 fields, with the three overrides
applied; abridged to the fields that changed plus a representative default):

```jsonc
{
  "name": "ralph",                       // overridden
  "bin": "/usr/local/bin/ralph",         // overridden
  "runCommand": "{bin} loop run . --backlog {backlogDir} --iterations {iterations}",  // default (template stays literal)
  "agentArgument": "--agent {agent}",    // default
  "defaultAgent": "codex",               // overridden
  "preconditionFile": ".rauf.json",      // default
  "stateDir": ".rauf",                   // default
  "schemaVersion": "1",                  // default
  "minRunnerVersion": "0.6.0"            // default
  // … the remaining 13 fields all resolve to their schema defaults …
}
```

The model reads **only this resolved object** — never the schema — and the merge
is guaranteed correct because the script performed it (REQ-R5-01, REQ-R5-02). Note
`runCommand` still carries the literal `{bin}` template; forge-5-loop substitutes
`{bin}` → `/usr/local/bin/ralph` later at launch (§3 note), not here.

## 9. Drift-guard requirement (REQ-MAINT-01 R5 slice, REQ-R4-03)

`06-testing-strategy.md` owns the exact assertions; the binding requirement here:
a stdlib-only pytest drift guard MUST assert that **`effective-config`'s output
validates against `forge-config-schema.json`** — so REQ-R4-03 ("schema remains the
single source of truth") is *test-enforced*, not just asserted in prose.

The guard MUST cover, at minimum:

1. **All-defaults parity.** With no `loopRunner` in the config, the resolved
   object equals `properties.loopRunner.properties.*.default` for **all 22**
   fields (mirroring `test_config_defaults_parity.py`'s parse). This catches a
   field losing its `default`, or a new field being added without one.
2. **Override wins.** A user `loopRunner` field overrides its default in the
   resolved output; an absent field keeps the default.
3. **Schema conformance.** The resolved object validates against the
   `loopRunner` sub-schema using the hand-rolled stdlib structural validator
   (`epic-manifest.py`'s `_schema_findings()` pattern — **no `jsonschema`**, C-2;
   00-core-definitions §3.4, tech-spec §8). No jsonschema import in CI.
4. **Unreadable-schema failure.** A missing/corrupt `--schema` path drives exit 2
   (deterministic), not a silent partial result (§10).

This drift guard is the R5 half of the shared "new forge-session subcommand +
stdlib schema drift-guard" pattern R4 reuses (`01-architecture-layout.md §5`).

## 10. Error handling

| Condition | Handling | Exit |
|-----------|----------|------|
| Schema unreadable / not valid JSON / no `loopRunner.properties` | `_loop_runner_defaults` raises `UsageError` → top-level handler prints `Error: …` to **stderr** | **2** |
| Bad CLI args (unknown flag) | argparse / `UsageError` | **2** |
| Config file missing or corrupt | `_load_config` returns `{}` → **pure defaults resolved** (not an error) | **0** |
| Config present, `loopRunner` absent | pure defaults resolved | **0** |
| Config `loopRunner` present with overrides | defaults + overrides resolved | **0** |
| I/O error reading schema | `OSError` → `UsageError` (wrapped) → stderr | **2** |

There is **no exit 1** (00-core-definitions §3.2). Diagnostic text goes to
**stderr**; the resolved JSON/summary goes to **stdout**, so a consumer can capture
stdout cleanly.

**Degrade behavior at the consumer (tech-spec §7).** When `effective-config`
exits 2 (schema unreadable — an install-level fault), the loop stages **fall back
to their existing behavior**: forge-5-loop / forge-4-backlog treat the loop-runner
config as its documented rauf defaults (the schema's own defaults, which are the
rauf baseline) exactly as they did before R5. R5 never leaves the loop with a
*partial* or *mis-merged* config — it is all-or-nothing by design, which is the
whole point of eliminating the "model mis-merged the defaults" error class
(REQ-R5-02). This preserves the R5 frozen-protocol invariant: the loop's effective
config is byte-identical to what the model would have merged by hand
(00-core-definitions §10, R5 row).

## Dependencies

Must be understood/available before implementing this document:

- **`00-core-definitions.md`** — §3 (forge-session script conventions: subparser
  registration, dispatch chain, `--json`/`json_output`, `_print_*` helpers, the
  0/2 exit contract, `UsageError`), §6 (the `effective-config` contract summary),
  §10 (the R5 invariant).
- **`03-state-verbs.md`** — the shared forge-session dispatch/registration
  conventions this subcommand matches (R5 and R4 both extend the same `main()`).
  R5 ships **before** R4 but they are additive and independently named.
- **`06-testing-strategy.md`** — owns the exact drift-guard assertions summarized
  in §9.
- **Existing code (verified, reuse — do not reimplement):**
  - `scripts/forge-session.py` — `_load_config(config_path: Path) -> dict` (L526,
    degrades to `{}`); `UsageError` (L168); the `main()` subparser + dispatch
    pattern (~L1700–1863) and the 0/2 exit tail (L1857–1862).
  - `references/forge-config-schema.json` — **unchanged**; `properties.loopRunner.
    properties.*.default` (all 22 fields verified to declare a `default`) is the
    runtime default source and stays the single source of truth (REQ-R4-03).
  - `tests/test_config_defaults_parity.py` — the stdlib-parse precedent §3/§9
    mirror.

**No new external dependency.** Python 3.10+ stdlib only (C-2): `json` + `pathlib`
are already imported in `forge-session.py`. No `jsonschema`.

## Verification

An implementation matches this spec when:

- [ ] `effective-config` is registered as an `argparse` subparser in `main()` and
      dispatched via an `if args.cmd == "effective-config":` branch inside the
      existing top-level `try` (§6).
- [ ] `--config` defaults to `./forge.config.json`; `--schema` defaults to the
      bundled `references/forge-config-schema.json`; `--json` uses
      `dest="json_output"` (§2).
- [ ] With no config (or `--config` pointing at a missing file),
      `effective-config --json` emits **all 22** `loopRunner` fields, each equal to
      its schema `default` (§3, §5.1) — verified against
      `properties.loopRunner.properties.*.default`.
- [ ] A user `loopRunner` override replaces the corresponding default in the
      output; absent fields keep their default (§4, §8 worked example).
- [ ] Template defaults (e.g. `runCommand`'s `{bin} …`) appear **literally** in the
      output — `effective-config` does not substitute placeholders (§3 note).
- [ ] An unreadable/unparseable `--schema` exits **2** with `Error: …` on stderr;
      the resolved JSON/summary goes to stdout (§10).
- [ ] No `jsonschema` import; defaults are read via plain `json.load` + dict access
      (§3, C-2).
- [ ] The 22 defaults are **not** hardcoded in Python — they are read from the
      schema at runtime (REQ-R4-03, §3).
- [ ] The R5 drift guard asserts all-defaults parity, override-wins, schema
      conformance (stdlib validator), and unreadable-schema exit 2 (§9).
- [ ] forge-5-loop and forge-4-backlog no longer read the config schema for
      defaults; each swaps in the one-line `effective-config` call; forge-5-loop
      body stays ≤300 lines (§7, `01-architecture-layout.md §2.2`).
- [ ] `ruff check scripts/ eval/` passes (CI-only gate, C-2) and
      `python3 -m pytest tests` is green.
