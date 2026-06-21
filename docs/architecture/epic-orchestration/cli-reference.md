---
title: "CLI Reference — `scripts/epic-manifest.py`"
---

# CLI Reference — `scripts/epic-manifest.py`

The deterministic core of Epic Orchestration: name→directory resolution,
acyclicity and schema validation, global name-uniqueness, path containment, live
per-feature status derivation, and atomic manifest mutation. Stdlib-only Python
3, no third-party packages.

Skills invoke it via Bash, typically as:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/epic-manifest.py" <subcommand> …
```

## Exit Codes

The contract mirrors the rauf validate convention:

| Code | Meaning |
|------|---------|
| `0` | ok / valid / unique / resolved |
| `1` | findings / validation failure / duplicate / ambiguous / not-found |
| `2` | usage error or I/O error (missing file, unreadable, unsafe path) |

For gating operations, callers surface findings verbatim and stop on exit ≥ 1.
A key distinction when scripting:

- **Exit 1** with `--json` emits a `{ "valid": …, "findings": [...] }` (or
  resolution findings) envelope on **stdout**.
- **Exit 2** emits a plain `Error: …` line on **stderr** with empty stdout —
  there is no findings JSON to parse.

Finding objects carry a stable `code` field. Known codes:
`not-found`, `ambiguous`, `unsafe-name`, `cycle`, `duplicate-name`,
`dangling-ref`, `schema`.

## Common Flag

`--specs-dir DIR` — the specs root to operate within (default `./specs`). All
resolution, globbing, and path-containment are scoped to it.

---

## Read / Validate Subcommands

### `resolve <name> [--specs-dir DIR]`

Resolve a bare feature or epic name to its absolute directory, handling both
flat (`{specsDir}/{name}/`) and nested (`{specsDir}/{epic}/{name}/`) layouts.
Enforces uniqueness and path containment.

- **Success (exit 0):** prints the absolute directory to stdout.
- **Ambiguous / missing / unsafe (exit 1):** actionable message; with `--json`,
  a `{valid, findings[]}` envelope on stdout.
- **Usage / containment error (exit 2):** `Error: …` on stderr.

```bash
$ python3 scripts/epic-manifest.py resolve config-store --specs-dir specs
/abs/specs/auth-overhaul/config-store
```

### `validate <epic> [--specs-dir DIR] [--json]`

Validate an epic manifest: schema conformance + acyclicity + name-uniqueness +
path-containment + dangling-`dependsOn`/`consumes.from` detection.

```bash
$ python3 scripts/epic-manifest.py validate cyclic-epic --specs-dir tests/fixtures/cyclic-epic --json
{
  "valid": false,
  "findings": [
    { "code": "cycle",
      "message": "cycle: token-service → api-gateway → token-service",
      "feature": "token-service" }
  ]
}      # exit 1
```

### `check-name <name> [--specs-dir DIR]`

Reject a name that already exists anywhere in the specs tree (flat or nested).
Run by `forge-0-epic` before creating a new member so no new name collision can
be introduced.

- exit 0 — unique.
- exit 1 — duplicate, with the colliding path.

```bash
$ python3 scripts/epic-manifest.py check-name token-service --specs-dir specs
duplicate-name: duplicate feature name 'token-service' (also at /abs/specs/auth-overhaul/token-service)   # exit 1
```

### `render-status <epic> [--specs-dir DIR] [--json]`

Render the live epic dashboard data. Opens each member's `.pipeline-state.json`
and derives status **live** — nothing is cached in the manifest. Drives the
forge navigator's epic dashboard, the forge-5-loop dependency gate, and the
completion handoff.

Output fields:

| Field | Meaning |
|-------|---------|
| `epic`, `status` | Epic name and lifecycle status. |
| `features[]` | Per feature: `name`, `stage`, derived `status`, `blocked`, `unmetDeps[]`. |
| `actionable[]` | Features whose every dependency is complete and that aren't themselves complete. |
| `parallelEligible[]` | Actionable features not (transitively) interdependent. Informational in v1 (execution is serial). |
| `rollup` | `{ complete, total }` member counts. |
| `nextCommand` | Recommended next pipeline command. |

```bash
$ python3 scripts/epic-manifest.py render-status auth-overhaul --specs-dir specs --json
{
  "epic": "auth-overhaul", "status": "active",
  "features": [
    { "name": "config-store", "stage": "forge-1-prd", "status": "not-started",
      "blocked": false, "unmetDeps": [] },
    { "name": "token-service", "stage": "forge-1-prd", "status": "not-started",
      "blocked": true, "unmetDeps": ["config-store"] }
  ],
  "actionable": ["config-store", "audit-log"],
  "parallelEligible": ["config-store", "audit-log"],
  "rollup": { "complete": 0, "total": 4 },
  "nextCommand": "/feature-forge:forge-1-prd config-store"
}
```

---

## Atomic Mutation Subcommands

Each mutator performs a temp-file + `os.replace` atomic write, bumps the
manifest's top-level `updatedAt`, and runs **full re-validation** afterward. A
mutation that would introduce a cycle or a dangling reference is **refused**
(exit 1 + findings) and the manifest is left untouched.

### `add-feature <epic> <name> --charter TEXT [--depends-on A,B] [--specs-dir DIR]`

Add a member feature with its charter and optional dependency list. The name is
checked for global uniqueness first.

```bash
python3 scripts/epic-manifest.py add-feature auth-overhaul audit-log \
  --charter "Append-only audit trail for auth events." \
  --depends-on token-service
```

### `remove-feature <epic> <name> [--specs-dir DIR]`

Remove a member feature and drop its manifest entry. (Per v1 policy the feature
subdirectory is left in place; relocation is manual.)

### `reorder <epic> --order A,B,C [--specs-dir DIR]`

Replace the ordered feature list. The `--order` list must be a permutation of
the existing feature names.

```bash
python3 scripts/epic-manifest.py reorder auth-overhaul \
  --order config-store,token-service,api-gateway,audit-log
```

### `set-dep <epic> <name> --depends-on A,B [--specs-dir DIR]`

Replace a feature's entire `dependsOn` list. Re-validated for acyclicity and
dangling refs.

```bash
python3 scripts/epic-manifest.py set-dep auth-overhaul api-gateway \
  --depends-on token-service,config-store
```

### `set-status <epic> --status STATE [--specs-dir DIR]`

Set the epic lifecycle status: `active | paused | abandoned | complete`. This is
the *epic's* status — per-feature status is always derived, never set here.

```bash
python3 scripts/epic-manifest.py set-status auth-overhaul --status complete
```

---

## Notes

- **Safety first.** Every subcommand rejects a `name`/path with separators,
  `..` segments, or absolute paths *before* touching the filesystem.
- **No caching.** There is deliberately no subcommand to write a per-feature
  status into the manifest — status is derived from each `.pipeline-state.json`
  by `render-status` on every read.
- **Pattern parity.** Invocation, exit-code semantics, and the
  `${CLAUDE_PLUGIN_ROOT}` convention match the pre-existing
  `scripts/validate-traceability.py`.
