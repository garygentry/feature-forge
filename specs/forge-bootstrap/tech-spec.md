# forge-bootstrap — Technical Specification

> Built on PRD v1 (`PRD.md`) and the three-researcher integration report.
> Answers HOW; requirements (REQ-*) and open questions (OQ-*) are referenced by ID.

## 1. Overview

`forge-bootstrap` is a new **unnumbered forge skill** that scaffolds a brand-new
empty repository to a pipeline-ready, green baseline. Its deterministic mechanics
live in a new Python helper (`scripts/forge-bootstrap.py`); the `SKILL.md` body
runs the interview (host-adapted `AskUserQuestion`) and orchestrates the helper via
the canonical portable-root prelude.

Key architectural decisions:

- **Hybrid split** — Python helper owns all deterministic logic (gate, git init,
  scaffold emission, config write, resume marker, verification, commit); the skill
  owns the conversation and decisions. Mirrors the established `epic-manifest.py`
  pattern (testable, deterministic, keeps `SKILL.md` under the 300-line/5000-word
  spec-purity budget).
- **Editable template assets** — per-stack scaffold files live under
  `skills/forge-bootstrap/references/templates/<stack>/`; the helper composes them
  (a monorepo composes one set per member).
- **Additive schema extension** — `forge.config.json` gains an optional
  `workspaces[]` array to represent a mixed-language monorepo (OQ-01).
- **Transient root sentinel** — `.forge-bootstrap.json` at the target repo root is
  the resume marker; it is in the greenfield allow-list and is removed before the
  baseline commit, never entering history (OQ-03).

## 2. Module Structure

New and modified files in the plugin repo:

```
skills/forge-bootstrap/
  SKILL.md                              # NEW — interview + orchestration (≤300 lines)
  references/
    templates/
      typescript/  {package.json, tsconfig.json, src/index.ts, test/smoke.test.ts, .gitignore}
      python/      {pyproject.toml, src/<pkg>/__init__.py, src/<pkg>/main.py, tests/test_smoke.py, .gitignore}
      go/          {go.mod, main.go, main_test.go, .gitignore}
      rust/        {Cargo.toml, src/lib.rs, src/main.rs, tests/smoke.rs, .gitignore}
      generic/     {run.sh, test.sh, .gitignore}
      ci/          {github-actions.yml}   # composed per-member when ci:true (§3.11)
scripts/
  forge-bootstrap.py                    # NEW — helper CLI (subcommands below)
tests/
  test_forge_bootstrap.py               # NEW — pytest, run by validate.sh
references/
  forge-config-schema.json              # MODIFIED — add optional workspaces[]
adapters/**                             # REGENERATED — python3 scripts/build-adapters.py
```

No edits needed to `plugin.json`, `marketplace.json`, `hooks/hooks.json`, or
`build-adapters.py` (skills are glob-discovered; `references/` is auto-propagated to
adapters).

### Helper public API surface (REQ-* in parens)

`scripts/forge-bootstrap.py <subcommand> <target-dir> [--json] [...]`, Python 3
stdlib only, exit codes `0` ok / `1` findings / `2` usage-or-IO error, structured
findings on stdout under `--json`, plain errors on stderr — matching the
`epic-manifest.py` convention.

| Subcommand | Purpose | REQ |
|---|---|---|
| `check` | Greenfield gate + recovery detection. Returns `{eligible, disqualifying[], hasGit, resumeMarker}`. If the sentinel is present → signals recovery instead of refusal. | REQ-GATE-01/02, REQ-LIFE-02 |
| `scaffold` | git init if absent; compose templates per `--answers`; write files + `forge.config.json`; track each written path into the sentinel. Resumable (skips files already recorded). | REQ-GATE-03, REQ-SCAF-01..09, REQ-MONO-01/02/03/04/05, REQ-CFG-01..03 |
| `verify` | Detect toolchain (`command -v`); run resolved lint+test (per member for monorepo). Returns `{toolchainPresent, lint, test}`. exit 0 green / 1 not-green / 2 toolchain-missing. | REQ-SCAF-05, REQ-STACK-02, REQ-LIFE-03 |
| `commit` | Stage the EXACT tracked file list (never `git add -A`); single baseline commit, or `--stage-only` to stop at staged; then finalize/remove the sentinel. | REQ-LIFE-05/06, REQ-SEC-02, REQ-SCAF-08 |
| `status` | Inspect the sentinel for the resume/recovery flow (answers, artifacts, status). | REQ-LIFE-01/02 |

The helper resolves its own template dir from `__file__` (`<root>/skills/forge-bootstrap/references/templates/`); no env var needed.

## 3. Technical Decisions

### 3.1 Hybrid helper + skill orchestration (REQ-SCAF-*, REQ-LIFE-*, REQ-PORT-02)
Deterministic mechanics in `scripts/forge-bootstrap.py`; interview/decisions in
`SKILL.md`. Rationale: testability (pytest gate), determinism of the green-baseline
guarantee, and the spec-purity body budget. Alternatives considered: fully
agent-authored scaffolding (rejected — non-deterministic, untestable, risks budget);
thin-script + agent file authoring (rejected — splits the green-baseline guarantee
across two actors).

### 3.2 Mixed-language monorepo via `workspaces[]` (REQ-MONO-*, OQ-01)
Extend `forge-config-schema.json` with an optional array:

```jsonc
"workspaces": {
  "type": "array",
  "description": "Monorepo members. Absent for single-package projects.",
  "items": {
    "type": "object",
    "required": ["name", "path", "stack"],
    "additionalProperties": false,
    "properties": {
      "name":             { "type": "string" },
      "path":             { "type": "string", "description": "Repo-relative member dir" },
      "stack":            { "type": "string" },
      "typeCheckCommand": { "type": ["string", "null"] },
      "testCommand":      { "type": ["string", "null"] }
    }
  }
}
```

Single-package projects keep the existing top-level scalar `stack` /
`typeCheckCommand` / `testCommand` and omit `workspaces` (byte-for-byte back-compat,
fully additive). A monorepo populates `workspaces[]`; the top-level `stack` MAY be a
nominated primary or `null`. **Boundary:** forge-bootstrap *writes* this
representation (REQ-MONO-05); making downstream stages (forge-2-tech/4-backlog)
*resolve* a member's stack from it is a follow-up — see §10 OQ-T1.

### 3.3 Config written directly, mirroring forge-init (REQ-CFG-01/02/03)
The helper writes `forge.config.json` itself rather than calling
`scripts/forge-init.sh` (which writes `stack`/commands = null and no `loopRunner`).
It reuses forge-init's **exact field set + default values** for equivalence
(REQ-CFG-02). Concretely, the helper reproduces every field forge-init emits, matching
its defaults byte-for-byte except where bootstrap has resolved a real value:

| Field | forge-init default | bootstrap value |
|---|---|---|
| `specsDir` | `./specs` | same |
| `docsDir` | `./docs/architecture` | same |
| `backlogDir` | `null` | same |
| `gitCommitAfterStage` | `true` | same |
| `commitPrefix` | `forge` | same |
| `loopIterationMultiplier` | `1.5` | same |
| `stack` | `null` | resolved from interview (or `null` + `workspaces[]` for monorepo) |
| `typeCheckCommand` | `null` | resolved per stack (§3.5) |
| `testCommand` | `null` | resolved per stack (§3.5) |

In addition it writes a **minimal explicit** `loopRunner` block
`{ "name": "rauf", "bin": "rauf" }` — satisfying REQ-CFG-01's explicit-block letter
while all other loopRunner fields resolve from schema defaults (equivalent in spirit
to forge-init's implicit default). After bootstrap, `forge-init` is unnecessary
(REQ-CFG-03).

### 3.4 Greenfield gate + transient resume sentinel (REQ-GATE-*, REQ-LIFE-01/02, OQ-03)
`check` allows only repo-meta files: `.git/`, a README (`README`/`README.md`),
`LICENSE`(`.md`/`.txt`), `.gitignore`, the configured specs dir, **and the
`.forge-bootstrap.json` sentinel**. Anything else (source, manifest, build config)
→ `eligible:false` with the disqualifying paths named (REQ-GATE-02). The sentinel is
written FIRST, before any scaffold file, recording status, ISO `startedAt`, the
interview answers, and the running `artifactsWritten[]`. If `check` finds the
sentinel, it routes to the recovery flow (resume / restart / cancel — REQ-LIFE-02)
instead of refusing the partial scaffold. On a successful `commit` the sentinel is
removed before staging, so it never enters history; it is also listed in the
scaffolded `.gitignore` as belt-and-suspenders.

### 3.5 Per-stack verification commands (REQ-STACK-01/02, sourced from references/stacks/*.md)
The `references/stacks/*.md` profiles are the **source of truth**; the scaffold's
commands MUST match what the pipeline's stack profile expects. Canonical choices
written into config + satisfied by the templates:

| Stack | typeCheckCommand | testCommand | Notes |
|---|---|---|---|
| typescript | `npx tsc --noEmit` | `<pm> test` → `vitest run` | `<pm>` from REQ-INPUT-04 (npm/pnpm/yarn); test runner is **Vitest**, matching the `typescript.md` profile (dev-deps: typescript, vitest) |
| python | `mypy .` | `pytest` | install via REQ-INPUT-04 pm (uv/poetry/pip); trivial typed module passes mypy |
| go | `go vet ./...` | `go test ./...` | go modules; no pm question |
| rust | `cargo clippy` | `cargo test` | cargo; no pm question |
| generic | `sh -n run.sh test.sh` | `./test.sh` | zero-dependency, see §3.6 |

The generic row's commands are **bootstrap-defined** because `_generic.md` specifies
no concrete verification command (there is no language toolchain to defer to); see §3.6.

Templates carry light token substitution (`{{PROJECT_NAME}}`, `{{PKG}}`, `{{PM}}`)
— simple string replacement, not a templating engine.

### 3.6 Generic baseline is real and zero-dependency (REQ-STACK-03, OQ-04)
Generic scaffolds a POSIX `run.sh` (prints a greeting), a `test.sh` that runs it and
asserts the output (real behavioral assertion, non-zero on mismatch), and lints via
`sh -n` syntax-checking the scripts. Genuinely real lint+test wherever a shell
exists — no language toolchain assumed.

### 3.7 Conversational fallback for non-AskUserQuestion hosts (REQ-PORT-01, REQ-INPUT-08)
No precedent exists. forge-bootstrap pioneers the pattern: when `AskUserQuestion` is
unavailable, the skill emits the identical questions as a numbered text list and
waits for a text reply. Documented as a short host-adaptation note in `SKILL.md`,
establishing a reusable pattern. The question SET is owned by the skill body, not the
helper.

### 3.8 Mode B hand-off is agent-driven (REQ-MODEB-*)
Mode B is opt-in. After a verified-green baseline and a successful commit, the skill
asks feature-vs-epic and invokes `forge-1-prd <feature>` or `forge-0-epic <epic>`
(skill-to-skill, not the helper). It MUST NOT launch if the baseline is unverified
(REQ-MODEB-04). Subsequent stages remain normal user-driven steps (REQ-MODEB-03).

### 3.9 Interview question set (REQ-INPUT-01..08)
The question set is **owned by the skill body** (not the helper); the helper only
receives the resolved `--answers` JSON. Each question maps to a requirement and a
default/seed rule:

| # | Question | REQ | Default / seed rule |
|---|---|---|---|
| 1 | Project name | REQ-INPUT-01 | default inferred from the target directory name |
| 2 | One-line purpose | REQ-INPUT-02 | no default; seeds the README and config |
| 3 | Language/stack | REQ-INPUT-03 | from the built-in profiles (typescript/python/go/rust/generic) |
| 4 | Package manager | REQ-INPUT-04 | asked **only when** the chosen stack has alternatives (TS: npm/pnpm/yarn; Python: uv/poetry/pip); skipped for go/rust/generic |
| 5 | License | REQ-INPUT-05 | includes a "none" option; seeded from a pre-existing LICENSE when present (§7 no-overwrite) |
| 6 | Single package vs monorepo | REQ-INPUT-06 | default `single` |
| 7 | Feature vs epic (Mode B only) | REQ-INPUT-07 | asked only when Mode B is opted in (§3.8) |

All questions use host-adapted structured input, falling back to the numbered-text
prompt of §3.7 when `AskUserQuestion` is unavailable (REQ-INPUT-08).

### 3.10 Completion summary & terminal outcomes (REQ-OUT-01/02, REQ-OBS-01)
The **skill body** renders the human-facing output from the helper's JSON; the helper
itself only emits structured JSON + exit codes (§5, §7). On the **success path**
(REQ-OUT-01, P0) the skill prints: the created artifacts, the resolved stack(s), the
verification verdict (**green** or **unverified**), and the exact next command
(`forge-1-prd <feature>` or `forge-0-epic <epic>`). In **Mode B** (REQ-OUT-02) it
launches that next stage instead of printing the command.

All four terminal outcomes (REQ-OBS-01) MUST be explicit and actionable, each sourced
from a helper result:

| Outcome | Source | Skill action |
|---|---|---|
| Success | `commit` exit 0 + `verify` verdict | REQ-OUT-01 summary (or Mode B launch) |
| Greenfield refusal | `check` `eligible:false` + `disqualifying[]` (§7) | name the paths; point to `forge-init` + `forge-1-prd` |
| Missing toolchain | `verify` `toolchainPresent:false`, exit 2 (§7) | offer scaffold-anyway-unverified vs abort; mark baseline **unverified** |
| Partial-state detected | `check` finds the sentinel (§3.4) | route to resume/restart/cancel |

### 3.11 Monorepo CI generation (REQ-MONO-04)
When CI is enabled (`ci:true`) for a **monorepo**, the scaffold emits a CI workflow
artifact (a GitHub Actions workflow under `.github/workflows/ci.yml`) that iterates
the `workspaces[]` members and runs **each member's** resolved lint + test command
(per §3.5), so CI exercises every member (REQ-MONO-04). For a single-package project
with CI enabled, the workflow runs the top-level `typeCheckCommand` + `testCommand`.
The workflow is composed from a template (`references/templates/ci/github-actions.yml`)
with per-member steps generated from the resolved answers. CI generation is gated on
the `ci` interview answer; when CI is disabled no workflow is written.

## 4. Data Model

- **`forge.config.json`** — existing fields + new optional `workspaces[]` (§3.2);
  loopRunner minimal block (§3.3).
- **`.forge-bootstrap.json` sentinel** (target repo root, transient):
  ```jsonc
  {
    "version": 1,
    "status": "in-progress",            // "in-progress" | "complete"
    "startedAt": "<ISO-8601>",
    "answers": {
      "projectName": "...", "purpose": "...",
      "layout": "single",               // "single" | "monorepo"
      "license": "MIT",                 // or "none"
      "members": [                      // single-package = one implicit member
        { "name": "...", "path": ".", "stack": "python", "packageManager": "uv" }
      ],
      "modeB": false, "ci": false, "commitStyle": "commit"  // "commit" | "stage-only"
    },
    "artifactsWritten": ["pyproject.toml", "src/...", "..."]
  }
  ```
- **Interview answers** flow skill → helper as a JSON `--answers` payload, mirrored
  into the sentinel for resume.

## 5. API Design

The helper subcommand surface is the API (§2). Skill→helper contract: the skill
collects answers, calls `check`, then `scaffold --answers <json>`, then `verify`,
presents the summary, then `commit` (or `--stage-only`). All structured exchange is
JSON over stdout under `--json`; exit codes drive control flow.

## 6. Integration Points

| Target | Direction | Contract / change |
|---|---|---|
| `references/forge-config-schema.json` | bootstrap writes config conforming to it | **Additive** `workspaces[]` (§3.2). No existing field changes. |
| `scripts/forge-root.sh` + `references/portable-root.md` | skill consumes | Byte-identical prelude to locate `$R`, then `python3 "$R/scripts/forge-bootstrap.py"`. |
| `scripts/forge-init.sh` | bootstrap mirrors, does not call | Reuse field set + defaults for REQ-CFG-02 equivalence. |
| `references/stacks/*.md` | source of truth | Canonical verification commands (§3.5). |
| `scripts/build-adapters.py` + `adapters/**` | regenerate | `python3 scripts/build-adapters.py`; commit regenerated bundles. **Hard CI gate** (`validate.sh` runs `build-adapters.py --check` over `adapters/`). No generator code change. |
| `scripts/validate.sh` | gates the new code | spec-purity (SKILL.md), adapter drift, and `pytest tests/` run automatically. |
| `hooks/hooks.json` | unaffected | Operates pre-config; the session-start hook exits 0 when no config/specs. No change. |
| `forge-1-prd` / `forge-0-epic` | Mode B hand-off | Skill invokes the next stage (§3.8). |

**Verified signatures/paths:** portable prelude and `forge-root.sh` sentinel
(`scripts/epic-manifest.py` + `.claude-plugin/plugin.json`) confirmed; forge-init
default field set confirmed; schema has no existing workspace concept (the extension
is genuinely new). No WARNINGs outstanding.

## 7. Error Handling

- **Helper exit codes:** `0` success / `1` actionable findings (gate refusal,
  not-green) / `2` usage or IO error. Findings as JSON on stdout under `--json`;
  plain `Error:` lines on stderr (stdout empty) on exit 2 — matching `epic-manifest.py`.
- **Greenfield refusal (REQ-GATE-01/02):** `check` returns `eligible:false` with
  `disqualifying[]`; the skill surfaces the paths and points to `forge-init` +
  `forge-1-prd`. No files touched (REQ-SEC-01).
- **Missing toolchain (REQ-LIFE-03/04):** `verify` returns `toolchainPresent:false`
  (exit 2); the skill asks scaffold-anyway-unverified vs abort and, if proceeding,
  marks the baseline **unverified** in the completion summary.
- **Interrupted run (REQ-LIFE-02):** sentinel presence routes `check` to
  resume/restart/cancel; `scaffold` is idempotent over `artifactsWritten[]`.
- **Commit failure (REQ-SEC-02):** never `--no-verify`/`--force`/`-A`; on failure the
  sentinel stays `in-progress` and the error is surfaced (resumable).
- **No-overwrite (REQ-SCAF-09):** when an allowed-meta README/LICENSE pre-exists, the
  helper skips generating it, seeds the interview default from it where sensible, and
  records the kept file in the summary.

## 8. Testing Approach

`tests/test_forge_bootstrap.py` (pytest, stdlib `tempfile`/`subprocess`, run by
`validate.sh`). Fixtures = temporary target repos. Coverage:

- **Gate (`check`):** empty → eligible; meta-only (README+LICENSE+.gitignore) →
  eligible (REQ-GATE-04); with source/manifest → refuse + disqualifying paths;
  sentinel present → recovery (REQ-LIFE-02).
- **Scaffold + verify per stack:** each of the 5 stacks produces the expected file
  set and a valid `forge.config.json`; `verify` is green where the toolchain is
  present (skip/xfail when `command -v` misses, so CI stays portable); generic is
  green with no language toolchain (REQ-STACK-03).
- **Monorepo:** multiple members compose; config has a well-formed `workspaces[]`
  validating against the extended schema; mixed-language members coexist; each member
  has its own runnable entrypoint + at least one test (REQ-MONO-03). When `ci:true`,
  the generated `.github/workflows/ci.yml` contains a lint+test step for **every**
  member (REQ-MONO-04).
- **Config equivalence (REQ-CFG-02):** the emitted config carries forge-init's exact
  field set — `specsDir`, `docsDir`, `backlogDir`, `gitCommitAfterStage`,
  `commitPrefix`, `loopIterationMultiplier`, `stack`, `typeCheckCommand`,
  `testCommand` — with defaults matching forge-init except the resolved stack/commands;
  the minimal `loopRunner` block is present; config validates against
  `forge-config-schema.json`.
- **Resume:** interrupt after partial `scaffold`, re-run → resumes without
  re-writing; restart → clean.
- **Commit:** stages exactly the tracked files (assert no `-A`), single baseline
  commit; `--stage-only` leaves them staged; sentinel removed and absent from the
  commit (REQ-LIFE-06, REQ-SCAF-08).

Coverage target: every subcommand path + each stack template smoke-tested; the
schema extension exercised by at least one monorepo case.

## 9. Dependencies

- **Runtime (plugin side):** Python 3 stdlib only (no new deps), consistent with
  existing helpers. Git CLI (already assumed by the pipeline).
- **Scaffolded-project toolchains** are the *user's* machine concern, detected at
  `verify` time (REQ-LIFE-03), never installed by bootstrap. Templates favor minimal
  dev-deps (e.g. TS pins only `typescript` + `vitest`, matching the stack profile).
- **No new internal package**; this is additive within the existing plugin.

## 10. Open Technical Questions

- **OQ-T1 (downstream consumption of `workspaces[]`):** forge-bootstrap writes the
  monorepo representation, but forge-2-tech/forge-4-backlog do not yet *read* it to
  target a member's stack. Full pipeline monorepo-awareness is a follow-up beyond
  this feature's scope (REQ-MONO-05 is satisfied at the representation level here).
- **OQ-T2 (TS minimal dev-deps):** the runner is **Vitest** (matching the
  `typescript.md` profile, resolving the earlier node --test-vs-runner question). Pin
  the smallest `typescript` + `vitest` dev-dep set that keeps the TS baseline green
  across npm/pnpm/yarn — finalize exact versions during implementation.
- **OQ-T3 (sentinel safety):** confirm the `.gitignore` entry + removal ordering fully
  prevents the sentinel from ever being committed even on a crash between stage and
  delete.
