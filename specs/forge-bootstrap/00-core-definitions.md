# 00 — Core Definitions

> Shared data contracts for **forge-bootstrap**. Every other spec document in this suite
> references the schemas, constants, and result shapes defined here. Where a contract is a
> JSON document on disk (the `.forge-bootstrap.json` sentinel, the `--answers` payload,
> `forge.config.json`), the canonical definition is its shape as given here; where it is a
> Python value passed between functions inside `scripts/forge-bootstrap.py`, the canonical
> definition is the typed structure (`TypedDict`) shown here.
>
> Stack: **prose plugin + Python 3 helper** (stdlib only). Python in this suite targets
> Python 3.10+ and follows `references/stacks/python.md` conventions (Google-style
> docstrings, `X | Y` unions, complete type annotations, single-file CLI — no `__all__`
> required), mirroring the established `scripts/epic-manifest.py` helper.
>
> **No `REQ-XXX-NN` spine of its own:** forge-bootstrap is an *unnumbered* forge skill
> (PRD §5 Constraints), so its requirement IDs are the functional families from the PRD —
> `REQ-GATE-*`, `REQ-INPUT-*`, `REQ-SCAF-*`, `REQ-STACK-*`, `REQ-MONO-*`, `REQ-MODEB-*`,
> `REQ-CFG-*`, `REQ-LIFE-*`, `REQ-OUT-*`, `REQ-SEC-*`, `REQ-OBS-*`, `REQ-PORT-*`.

## Requirement Coverage

| REQ ID | Requirement | Section |
|--------|-------------|---------|
| REQ-GATE-01 | Greenfield gate: only repo-meta files allowed | 3 (allow-list), 4 (`CheckResult`) |
| REQ-GATE-04 | Fresh-remote (README+LICENSE) is eligible | 3 (allow-list rules) |
| REQ-INPUT-01..07 | Interview answer set | 5 (`Answers`/`Member`) |
| REQ-STACK-01 | Five stack profiles (ts/python/go/rust/generic) | 2 (`Stack` enum) |
| REQ-STACK-02 | Verification commands match the stack profile | 6 (per-stack command table) |
| REQ-MONO-01/02/05 | Monorepo members; mixed-language; config representation | 5 (`Member`), 7 (`workspaces[]`) |
| REQ-CFG-01/02/03 | Valid `forge.config.json` ≡ forge-init + `loopRunner` | 7 (config field set) |
| REQ-LIFE-01/02 | Resume marker; recovery detection | 8 (sentinel schema), 4 (`resumeMarker`) |
| REQ-LIFE-03/04 | Toolchain detection; unverified marking | 4 (`VerifyResult`) |
| REQ-LIFE-05 | Commit style chosen at run time | 5 (`commitStyle`) |
| REQ-SEC-01 | Never modify/delete pre-existing files | 3 (allow-list), 9 (exit codes) |
| REQ-OBS-01 | All terminal outcomes explicit | 4 (result shapes), 9 (exit codes) |
| REQ-PORT-02 | Portable-root resolution | 1 (invocation) |

---

## 1. Domain Overview

`forge-bootstrap` takes a **brand-new empty repository** to a *pipeline-ready, green
baseline* — a stack-appropriate structure, a configured toolchain, a passing lint + test,
and a valid `forge.config.json` — so that `forge-1-prd <feature>` (or `forge-0-epic
<epic>`) is the next logical step (PRD §1). It is an **unnumbered** sibling of
`forge-init` / `forge-fix` / `forge-verify`, purely additive: every existing flow is
unchanged.

The feature is split into a deterministic **Python helper** and a prose **skill body**
(tech-spec §1, §3.1):

| Actor | Owns | Canonical doc |
|-------|------|---------------|
| `scripts/forge-bootstrap.py` | gate, git init, scaffold emission, config write, resume marker, verification, commit | 02-helper-cli.md |
| `skills/forge-bootstrap/SKILL.md` | the interview, all decisions, completion summary, Mode B hand-off | 04-skill-orchestration.md |
| `skills/forge-bootstrap/references/templates/<stack>/` | the per-stack scaffold files | 03-stack-templates.md |

Five on-disk / in-process contracts are defined here and consumed everywhere else:

| Contract | Kind | Canonical definition | Section |
|----------|------|----------------------|---------|
| `.forge-bootstrap.json` sentinel | on-disk JSON (transient) | this doc | 8 |
| `--answers` payload (skill → helper) | CLI JSON arg | this doc (`Answers`) | 5 |
| `forge.config.json` (incl. `workspaces[]`) | on-disk JSON | `references/forge-config-schema.json` | 7 |
| `CheckResult` / `VerifyResult` / `CommitResult` | helper stdout JSON | this doc | 4 |
| Allowed-meta-file set + `Stack` enum + command table | constants | this doc | 2, 3, 6 |

### 1.1 Invocation (REQ-PORT-02)

The skill locates the helper via the byte-identical portable-root prelude already used by
`epic-manifest.py` (01-architecture-layout.md §3; `references/portable-root.md`), then:

```bash
python3 "$R/scripts/forge-bootstrap.py" <subcommand> <target-dir> [--json] [...]
```

`<target-dir>` is the project root being bootstrapped (the cwd), **not** the plugin root.
The helper resolves its own template directory from `__file__`
(`<root>/skills/forge-bootstrap/references/templates/`), so no environment variable is
needed (tech-spec §2).

---

## 2. Stack Identifiers (REQ-STACK-01)

```python
from typing import Final, Literal

#: The five built-in stack profiles, parity with references/stacks/*.md (REQ-STACK-01).
Stack = Literal["typescript", "python", "go", "rust", "generic"]

#: Stacks that have a meaningful package-manager choice (drives REQ-INPUT-04).
#: A stack absent from this map skips the package-manager question entirely.
PACKAGE_MANAGERS: Final[dict[str, list[str]]] = {
    "typescript": ["npm", "pnpm", "yarn"],
    "python": ["uv", "poetry", "pip"],
    # go, rust, generic: no package-manager question (tech-spec §3.9 row 4).
}
```

`Stack` values map 1:1 to `references/stacks/<stack>.md` (`generic` → `_generic.md`) and to
a template directory `skills/forge-bootstrap/references/templates/<stack>/` (03 §1).

---

## 3. Greenfield Allow-List (REQ-GATE-01/04, REQ-SEC-01)

The greenfield gate permits **only** repo-meta files. Anything else — any source file,
package manifest, or build/tooling config — disqualifies the repo (REQ-GATE-01). The gate
**never modifies or deletes** anything; it only reads directory entries and decides
eligibility (REQ-SEC-01).

```python
import re
from typing import Final

#: Exact directory entries always permitted at the target repo root.
ALLOWED_META_DIRS: Final[frozenset[str]] = frozenset({".git"})

#: The transient resume sentinel (§8) is allow-listed so a re-run over a partial
#: scaffold is routed to recovery, not refused (REQ-LIFE-02, tech-spec §3.4).
SENTINEL_FILENAME: Final = ".forge-bootstrap.json"

#: Case-insensitive filename patterns for allowed repo-meta files (REQ-GATE-01/04, OQ-02).
#: A fresh remote's auto-generated README + LICENSE must pass (REQ-GATE-04).
ALLOWED_META_FILE_RE: Final = re.compile(
    r"""^(
        README(\.md|\.txt|\.rst)?     # README, README.md, README.txt, README.rst
      | LICENSE(\.md|\.txt)?          # LICENSE, LICENSE.md, LICENSE.txt
      | \.gitignore
      | \.gitattributes
    )$""",
    re.IGNORECASE | re.VERBOSE,
)
```

**Allow rules (tech-spec §3.4, resolving OQ-02):**

1. `.git/` and the configured `specsDir` (default `./specs`) directory are always allowed.
2. A regular file whose name matches `ALLOWED_META_FILE_RE` (case-insensitive) is allowed.
3. The `SENTINEL_FILENAME` is allowed (recovery routing, not refusal — §4, §8).
4. **Any other entry** — a source file, a `package.json`/`pyproject.toml`/`go.mod`/
   `Cargo.toml`/`Makefile`, a `src/` tree, a dotfile not in the list — is **disqualifying**
   and its path is recorded in `CheckResult.disqualifying[]` (REQ-GATE-01/02).

> An empty directory (or a non-existent one) is trivially eligible. The matching is on the
> **basename** only; the gate does not descend into allowed directories.

---

## 4. Helper Result Shapes (REQ-GATE-01, REQ-LIFE-02/03/04, REQ-OBS-01)

The helper emits one JSON object per subcommand on stdout under `--json` (02 fleshes out
each subcommand). The shapes are defined here so the skill body and the pytest suite share
one source of truth. Each maps to a terminal outcome the skill must surface (REQ-OBS-01;
tech-spec §3.10).

```python
from typing import Literal, TypedDict


class CheckResult(TypedDict):
    """Output of `check` — greenfield gate + recovery detection (REQ-GATE-01/02, REQ-LIFE-02).

    Attributes:
        eligible: True iff the target is a permitted greenfield (§3) OR a resume of
            this tool's own partial scaffold. False ⇒ greenfield refusal.
        disqualifying: Repo-relative paths that fail the allow-list (§3). Empty when
            eligible. Drives the REQ-GATE-02 refusal message.
        hasGit: True iff the target already contains a `.git/` repository (REQ-GATE-03
            decides whether `scaffold` runs `git init`).
        resumeMarker: The parsed sentinel (§8) when one is present, else None. When
            non-None the skill routes to resume / restart / cancel (REQ-LIFE-02) rather
            than treating `eligible` as a fresh-start signal.
    """
    eligible: bool
    disqualifying: list[str]
    hasGit: bool
    resumeMarker: "Sentinel | None"


class CommandOutcome(TypedDict):
    """Result of one resolved lint or test command (REQ-SCAF-05, REQ-STACK-02).

    Attributes:
        command: The exact command string that was run (from the §6 table).
        ok: True iff the command exited 0.
        member: The member's repo-relative path the command ran for ("." for a
            single package; e.g. "packages/api" for a monorepo member).
    """
    command: str
    ok: bool
    member: str


class VerifyResult(TypedDict):
    """Output of `verify` — toolchain detection + lint/test (REQ-SCAF-05, REQ-LIFE-03/04).

    Attributes:
        toolchainPresent: True iff every required tool for the resolved stack(s) was
            found via `command -v`. False ⇒ missing-toolchain outcome (exit 2): the
            skill offers scaffold-anyway-unverified vs abort and marks the baseline
            **unverified** (REQ-LIFE-04).
        lint: One CommandOutcome per resolved lint command (per member for a monorepo).
        test: One CommandOutcome per resolved test command (per member for a monorepo).
        green: True iff toolchainPresent AND every lint/test outcome is ok. The single
            predicate Mode B gates on (REQ-MODEB-04).
    """
    toolchainPresent: bool
    lint: list[CommandOutcome]
    test: list[CommandOutcome]
    green: bool


class CommitResult(TypedDict):
    """Output of `commit` — staged-or-committed baseline (REQ-LIFE-05/06, REQ-SCAF-08).

    Attributes:
        committed: True iff a baseline commit was made; False when `--stage-only` left
            the scaffold staged with no commit (REQ-LIFE-05).
        commitHash: The new commit's hash when committed, else None.
        staged: The exact list of repo-relative paths staged (the tracked artifact set;
            never via `git add -A` — REQ-SEC-02, tech-spec §3.4).
        sentinelRemoved: True once the sentinel was deleted before staging so it never
            enters history (REQ-SCAF-08, OQ-T3).
    """
    committed: bool
    commitHash: str | None
    staged: list[str]
    sentinelRemoved: bool
```

The four terminal outcomes the skill renders from these (tech-spec §3.10):

| Outcome | Source | Skill action |
|---------|--------|--------------|
| Success | `commit` exit 0 + `VerifyResult.green` | REQ-OUT-01 summary (or Mode B launch) |
| Greenfield refusal | `CheckResult.eligible == false` + `disqualifying[]` | name the paths; point to `forge-init` + `forge-1-prd` |
| Missing toolchain | `VerifyResult.toolchainPresent == false` (exit 2) | offer scaffold-anyway-unverified vs abort; mark **unverified** |
| Partial-state detected | `CheckResult.resumeMarker != null` | route to resume / restart / cancel |

---

## 5. Interview Answers (REQ-INPUT-01..07, REQ-LIFE-05)

The **skill body owns the question set** (04 §2); the helper receives only the resolved
answers as a single `--answers <json>` payload (tech-spec §3.9, §4). The payload is
mirrored verbatim into the sentinel for resume (§8).

```python
from typing import Literal, TypedDict


class Member(TypedDict):
    """One package to scaffold. A single-package project has exactly one implicit member.

    Attributes:
        name: Package name. For a single package this equals the project name; for a
            monorepo member it is the user-supplied member name (REQ-MONO-01).
        path: Repo-relative directory for this member ("." for a single package;
            e.g. "packages/api" for a monorepo member). Becomes workspaces[].path (§7).
        stack: The member's stack profile (REQ-MONO-02 allows mixed-language members).
        packageManager: The chosen package manager when the stack has a choice
            (PACKAGE_MANAGERS, §2), else None (go/rust/generic).
    """
    name: str
    path: str
    stack: Stack
    packageManager: str | None


class Answers(TypedDict):
    """The resolved interview payload (skill → helper), mirrored into the sentinel (§8).

    Attributes:
        projectName: Project name (REQ-INPUT-01; default inferred from the target dir).
        purpose: One-line project purpose, seeds README + config metadata (REQ-INPUT-02).
        layout: "single" or "monorepo" (REQ-INPUT-06; default "single").
        license: SPDX-ish identifier (e.g. "MIT", "Apache-2.0") or "none" (REQ-INPUT-05).
        members: One Member for a single package, ≥1 for a monorepo (REQ-MONO-01).
        modeB: True iff the user opted into pipeline hand-off (REQ-MODEB-01; default False).
        modeBTarget: "feature" or "epic" when modeB is True, else None (REQ-INPUT-07).
        ci: True iff a CI workflow should be emitted (REQ-SCAF-07, REQ-MONO-04).
        commitStyle: "commit" (single baseline commit) or "stage-only" (REQ-LIFE-05).
    """
    projectName: str
    purpose: str
    layout: Literal["single", "monorepo"]
    license: str
    members: list[Member]
    modeB: bool
    modeBTarget: Literal["feature", "epic"] | None
    ci: bool
    commitStyle: Literal["commit", "stage-only"]
```

> A single-package project is modeled as `layout="single"` with exactly one `Member` whose
> `path` is `"."`. This keeps the helper's scaffold/verify/commit logic uniform across
> single and monorepo layouts (02 §3): "scaffold every member" degenerates to "scaffold the
> one member at the repo root."

---

## 6. Per-Stack Command Table (REQ-STACK-02)

`references/stacks/*.md` are the **source of truth** for verification commands; the scaffold
must emit a baseline that these exact commands pass, so downstream acceptance-criteria
verification runs against the baseline without adjustment (REQ-STACK-02, tech-spec §3.5).
The canonical resolved commands written into `forge.config.json` (or per-member
`workspaces[]`) and satisfied by the templates (03):

| Stack | `typeCheckCommand` (lint) | `testCommand` | Toolchain probe (`command -v`) | Notes |
|-------|---------------------------|---------------|--------------------------------|-------|
| `typescript` | `npx tsc --noEmit` | `<pm> test` → `vitest run` | `node`, `<pm>` | `<pm>` ∈ {npm,pnpm,yarn} (REQ-INPUT-04); runner is **Vitest** (tech-spec §3.5, OQ-T2) |
| `python` | `mypy .` | `pytest` | `python3`, `<pm>` | `<pm>` ∈ {uv,poetry,pip}; trivial typed module passes mypy |
| `go` | `go vet ./...` | `go test ./...` | `go` | go modules; no pm question |
| `rust` | `cargo clippy` | `cargo test` | `cargo` | cargo; no pm question |
| `generic` | `sh -n run.sh test.sh` | `./test.sh` | `sh` | zero-dependency, **bootstrap-defined** (§6.1) |

### 6.1 Generic baseline is real and zero-dependency (REQ-STACK-03, OQ-04)

`_generic.md` specifies no concrete verification command (there is no language toolchain to
defer to), so the generic row is **bootstrap-defined** (tech-spec §3.6): the template emits
a POSIX `run.sh` (prints a greeting), a `test.sh` that runs it and **asserts the output**
(a real behavioral assertion — non-zero exit on mismatch), and lints by syntax-checking both
scripts with `sh -n`. This is a genuinely real lint + test wherever a POSIX shell exists,
keeping the generic baseline green with no language toolchain assumed (REQ-STACK-03).

### 6.2 Token substitution

Templates carry light token substitution — simple string replacement, **not** a templating
engine (tech-spec §3.5):

| Token | Replaced with |
|-------|---------------|
| `{{PROJECT_NAME}}` | `Answers.projectName` |
| `{{PKG}}` | the member's package identifier (sanitized `Member.name`) |
| `{{PM}}` | the member's `packageManager` (where applicable) |
| `{{PURPOSE}}` | `Answers.purpose` (README seed) |

---

## 7. `forge.config.json` Field Set + `workspaces[]` Extension (REQ-CFG-01/02/03, REQ-MONO-05)

The helper **writes `forge.config.json` directly**, reproducing `forge-init`'s exact field
set and default values so the result is equivalent to what `forge-init` would write
(REQ-CFG-02), differing only where bootstrap has resolved a real value (tech-spec §3.3).
After bootstrap, running `forge-init` is unnecessary (REQ-CFG-03).

> **REQ-CFG-02 equivalence is semantic, not byte-order.** Equivalence means the same
> key/value *set* as `forge-init` (plus the explicit `loopRunner` block, appended last);
> it does **not** pin JSON key ordering. The table below and `write_config` (02 §4.3) may
> list fields in different orders without breaking equivalence.

| Field | forge-init default | bootstrap value |
|-------|--------------------|-----------------|
| `specsDir` | `./specs` | same |
| `docsDir` | `./docs/architecture` | same |
| `backlogDir` | `null` | same |
| `gitCommitAfterStage` | `true` | same |
| `commitPrefix` | `forge` | same |
| `loopIterationMultiplier` | `1.5` | same |
| `stack` | `null` | resolved from interview (single) — or `null` for a monorepo (§7.1) |
| `typeCheckCommand` | `null` | resolved per stack (§6) — or `null` for a monorepo |
| `testCommand` | `null` | resolved per stack (§6) — or `null` for a monorepo |

In addition the helper writes a **minimal explicit** `loopRunner` block, satisfying
REQ-CFG-01's explicit-block letter while every other `loopRunner` field resolves from the
schema defaults in `references/forge-config-schema.json`:

```json
"loopRunner": { "name": "rauf", "bin": "rauf" }
```

### 7.1 Monorepo representation — additive `workspaces[]` (REQ-MONO-05, OQ-01)

`references/forge-config-schema.json` gains an optional `workspaces[]` array (tech-spec
§3.2). Single-package projects **omit** it entirely and keep the top-level scalar `stack` /
`typeCheckCommand` / `testCommand` — byte-for-byte back-compatible and fully additive. A
monorepo populates `workspaces[]` and sets the three top-level scalars to `null` (the
top-level `stack` MAY instead name a nominated primary; bootstrap writes `null`).

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

> **Closed shape, by design.** The `workspaces[]` item schema uses
> `additionalProperties: false` (stricter than the open top-level config object) and
> intentionally **omits** `packageManager` — even though `Member` (§5) carries it —
> because each entry's `typeCheckCommand` / `testCommand` are already fully resolved (§6),
> so no downstream consumer needs the raw package manager. Do not re-add `packageManager`
> to an entry: it would trip the closed schema.

Each `workspaces[]` entry's `path`/`stack`/`typeCheckCommand`/`testCommand` come from the
corresponding `Member` (§5) and the §6 command table. **Boundary (tech-spec §3.2, §10
OQ-T1):** forge-bootstrap *writes* this representation (REQ-MONO-05 is satisfied at the
representation level); making downstream stages (forge-2-tech / forge-4-backlog) *resolve* a
member's stack from it is an explicit follow-up beyond this feature's scope.

---

## 8. `.forge-bootstrap.json` Sentinel (REQ-LIFE-01/02, OQ-03)

The sentinel is the transient resume marker at the **target repo root**. It is written
**first**, before any scaffold file, and is removed before the baseline commit so it never
enters history (tech-spec §3.4; it is also listed in the scaffolded `.gitignore` as
belt-and-suspenders — OQ-T3). It is allow-listed by the gate (§3) so a re-run recognizes its
own partial scaffold instead of refusing it (REQ-LIFE-02).

```python
from typing import Literal, TypedDict


class Sentinel(TypedDict):
    """The transient `.forge-bootstrap.json` resume marker (target repo root).

    Attributes:
        version: Schema guard (const 1).
        status: "in-progress" while scaffolding; "complete" only in the instant
            between a successful verify/commit decision and sentinel removal.
        startedAt: ISO-8601 timestamp set once when the sentinel is first written.
        answers: The full interview Answers (§5), mirrored so a resume reconstructs
            prior answers with no re-interview (REQ-LIFE-02, OQ-03).
        artifactsWritten: Repo-relative paths the helper has written so far. `scaffold`
            is idempotent over this list (skips files already recorded), enabling resume.
    """
    version: Literal[1]
    status: Literal["in-progress", "complete"]
    startedAt: str
    answers: Answers
    artifactsWritten: list[str]
```

Canonical example:

```jsonc
{
  "version": 1,
  "status": "in-progress",
  "startedAt": "2026-06-19T00:00:00Z",
  "answers": {
    "projectName": "acme-svc", "purpose": "Billing service",
    "layout": "single", "license": "MIT",
    "members": [
      { "name": "acme-svc", "path": ".", "stack": "python", "packageManager": "uv" }
    ],
    "modeB": false, "modeBTarget": null, "ci": false, "commitStyle": "commit"
  },
  "artifactsWritten": ["pyproject.toml", "src/acme_svc/__init__.py"]
}
```

---

## 9. Exit-Code Contract

`scripts/forge-bootstrap.py` follows the `epic-manifest.py` convention exactly (tech-spec
§2, §7): structured findings as JSON on stdout under `--json`; plain `Error:` lines on
stderr (stdout empty) on exit 2.

| Exit | Meaning |
|------|---------|
| `0` | success: eligible / green / committed-or-staged |
| `1` | actionable findings: gate refusal (`eligible:false`), or `verify` not-green |
| `2` | usage or IO error — **including `verify` toolchain-missing** (the distinct missing-toolchain outcome, §4 / tech-spec §3.10) |

The skill surfaces findings **verbatim** and routes each non-zero outcome to the matching
terminal action in §4. `verify`'s exit codes specifically (tech-spec §2 helper table):
**0 green / 1 not-green / 2 toolchain-missing**.

---

## Dependencies

None — this is the foundation document. All other documents in this suite depend on it.

## Verification

- [ ] `references/forge-config-schema.json` gains an optional `workspaces[]` matching §7.1;
      a single-package config (no `workspaces`) and a monorepo config both validate against
      it (REQ-CFG-01, REQ-MONO-05).
- [ ] The emitted single-package `forge.config.json` carries forge-init's exact field set
      with matching defaults except the resolved `stack`/commands, plus the minimal
      `loopRunner` block (REQ-CFG-02).
- [ ] Each `Stack` value in §2 has a matching `references/stacks/<stack>.md` profile and a
      `templates/<stack>/` directory (03 §1).
- [ ] Every per-stack command in §6 matches the corresponding `references/stacks/*.md`
      profile's verification command (REQ-STACK-02); the generic row is real (§6.1).
- [ ] A meta-only repo (README + LICENSE + `.gitignore`) passes the §3 allow-list
      (REQ-GATE-04); a repo with any source/manifest file is disqualified with that path in
      `CheckResult.disqualifying[]` (REQ-GATE-01).
- [ ] The sentinel (§8) is allow-listed (§3) so a re-run is routed to recovery, and is
      absent from the baseline commit (REQ-LIFE-02, REQ-SCAF-08).
