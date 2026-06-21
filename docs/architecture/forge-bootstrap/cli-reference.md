---
title: "CLI Reference — `scripts/forge-bootstrap.py`"
---

# CLI Reference — `scripts/forge-bootstrap.py`

The deterministic core of forge-bootstrap: the greenfield gate, template
composition, config write, the resume sentinel, toolchain probing, lint/test, and
the baseline commit. Stdlib-only Python 3, no third-party packages.

The skill body invokes it via the portable-root prelude, e.g.:

```bash
R="$(for d in "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/*/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done)"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-bootstrap.py" <subcommand> "<target-dir>" --json [...]
```

`<target-dir>` is the project being bootstrapped (default `.`), distinct from `$R`
(the plugin root). The helper resolves its own template directory from `__file__`,
so no environment variable is needed.

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | success: eligible / green / committed-or-staged |
| `1` | findings: gate refusal (`eligible:false`) or verify not-green |
| `2` | usage or I/O error — **including** verify toolchain-missing |

- **Exit 1** prints the result JSON (a `CheckResult` or `VerifyResult`) on
  **stdout** — there are findings to act on.
- **Exit 2** prints a plain `Error: …` line on **stderr** with empty stdout — a
  usage/IO failure, or the distinct verify "toolchain missing" terminal outcome.

`--json` is accepted on every subcommand and selects machine-readable output.

## `check` — greenfield gate + recovery detection

```
forge-bootstrap.py check <target-dir> [--specs-dir ./specs] [--json]
```

Read-only. Walks the target's top-level entries and allows only repo-meta: `.git/`,
the configured specs directory, the sentinel, and files matching the allowed-meta
pattern (README / LICENSE / `.gitignore`). Anything else is disqualifying. If this
tool's own `.forge-bootstrap.json` sentinel is present, it is surfaced as
`resumeMarker` and the run is **not** treated as a refusal.

Returns `CheckResult`:

```json
{ "eligible": true, "disqualifying": [], "resumeMarker": null }
```

Exit `0` when eligible (or resumable); exit `1` on refusal with `disqualifying[]`
populated. Touches no files.

## `scaffold` — emit the pipeline-ready baseline

```
forge-bootstrap.py scaffold <target-dir> --answers '<JSON>' [--json]
```

`--answers` is the resolved `Answers` payload (required). Writes the sentinel first,
runs `git init` if no `.git/` exists, composes each member's stack templates with
token substitution, emits the repo-hygiene files (README, LICENSE unless
`license=="none"`, `AGENTS.md` always, `CLAUDE.md` when `host=="claude"`), writes
`forge.config.json`, and emits CI when `ci` is true. Every written path is recorded
in the sentinel's `artifactsWritten[]`; a path already recorded is skipped
(idempotent resume), and a pre-existing allowed-meta file is kept untouched.

`--json` prints `{ "artifactsWritten": [...] }`. Exit `0` on success; `2` on IO
error (missing template dir, unwritable target, malformed `--answers`, `git init`
failure).

## `verify` — toolchain detection + lint/test

```
forge-bootstrap.py verify <target-dir> --answers '<JSON>' [--json]
```

Probes the chosen stack(s)' toolchain (`command -v`), then runs each member's
resolved `typeCheckCommand` (lint) and `testCommand` from `STACK_COMMANDS`, in that
member's directory. Returns `VerifyResult`:

```json
{
  "green": true,
  "toolchainPresent": true,
  "lint": [{ "command": "mypy .", "ok": true, "member": "." }],
  "test": [{ "command": "pytest", "ok": true, "member": "." }]
}
```

Each `CommandOutcome.member` is the member's **path** (`"."` for a single package,
e.g. `packages/api` for a monorepo member). `green` is true iff `toolchainPresent`
and every outcome `ok`. Exit `0` green; `1` not-green (toolchain present, a command
failed); `2` toolchain missing (`toolchainPresent:false`) — the false-green guard
the Mode B gate depends on.

## `commit` — exact-list baseline commit

```
forge-bootstrap.py commit <target-dir> --answers '<JSON>' [--stage-only] [--json]
```

Follows the Git Commit Protocol. Stages exactly `sentinel.artifactsWritten[]` with
`git add -- <paths>` (never `git add -A`, `--force`, or `--no-verify`), after
removing the sentinel so it never enters history. The commit message prefix is read
from the just-written `forge.config.json` `commitPrefix` (default `forge`). With
`--stage-only` (or `commitStyle == "stage-only"`) it leaves the scaffold staged
with no commit. Returns `CommitResult`:

```json
{ "committed": true, "commitHash": "a1b2c3d", "staged": ["..."], "sentinelRemoved": true }
```

Exit `0` on success; `2` on a git/IO failure (the sentinel is already removed, so
the run is re-stageable).

## `status` — inspect the resume sentinel

```
forge-bootstrap.py status <target-dir> [--json]
```

Read-only. Emits the full `Sentinel` JSON (`version`, `status`, `startedAt`,
mirrored `answers`, `artifactsWritten[]`) when `.forge-bootstrap.json` exists, or
`null` when it does not. Exit `0` either way.

## The `Answers` payload

The skill body assembles one `Answers` object and passes it verbatim to
`scaffold`/`verify`/`commit`:

| Field | Meaning |
|-------|---------|
| `projectName` | project name (default inferred from the target dir) |
| `purpose` | one-line purpose (seeds README + config) |
| `layout` | `"single"` or `"monorepo"` |
| `license` | SPDX-ish id (`MIT`, `Apache-2.0`) or `"none"` |
| `members[]` | one `Member{name, path, stack, packageManager}` per package (single → one at `path:"."`) |
| `modeB` / `modeBTarget` | Mode B opt-in + `"feature"`/`"epic"` |
| `ci` | emit a CI workflow |
| `commitStyle` | `"commit"` or `"stage-only"` |
| `author` | LICENSE copyright holder (seeded from `git config user.name`, else project name) |
| `host` | `"claude"` / `"codex"` / `"other"` / null — drives the host-conditional `CLAUDE.md` |

Example (single Python package, commit, no Mode B):

```json
{
  "projectName": "acme-svc", "purpose": "Billing service",
  "layout": "single", "license": "MIT",
  "members": [{ "name": "acme-svc", "path": ".", "stack": "python", "packageManager": "uv" }],
  "modeB": false, "modeBTarget": null, "ci": false, "commitStyle": "commit",
  "author": "Ada Lovelace", "host": "claude"
}
```
