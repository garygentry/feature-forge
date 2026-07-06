# 04 — Skill Orchestration (`skills/forge-bootstrap/SKILL.md`)

> Specifies the **prose** deliverable `skills/forge-bootstrap/SKILL.md`: the interview
> question set, the conversational fallback for non-`AskUserQuestion` hosts, the Mode A and
> Mode B flows, the completion summary, the four terminal outcomes, and the portable-root
> prelude. The skill body owns *conversation and decisions only*; all deterministic
> mechanics are delegated to the helper (`02-helper-cli.md`) so the body stays inside the
> spec-purity budget (`01-architecture-layout.md` §6.1).

## Requirement Coverage

| REQ ID | Requirement | Section |
|--------|-------------|---------|
| REQ-INPUT-01 | Project name (default from target dir) | 4 (Q1), 5 |
| REQ-INPUT-02 | One-line purpose | 4 (Q2) |
| REQ-INPUT-03 | Language/stack from the five profiles | 4 (Q3) |
| REQ-INPUT-04 | Package manager — only when stack has a choice | 4 (Q4) |
| REQ-INPUT-05 | License (incl. "none"; seed from existing LICENSE) | 4 (Q5) |
| REQ-INPUT-06 | Single package vs monorepo (+ member count/names) | 4 (Q6, Q6a) |
| REQ-INPUT-07 | Feature vs epic (Mode B only) | 4 (Q8), 8 |
| REQ-INPUT-08 | Host-adapted structured input + conversational fallback | 5, 6 |
| REQ-MODEB-01 | Mode B opt-in; default Mode A only | 4 (Q7), 8 |
| REQ-MODEB-02 | After green baseline, ask feature/epic, auto-launch | 8 |
| REQ-MODEB-03 | Subsequent stages stay user-driven | 8 |
| REQ-MODEB-04 | MUST NOT launch if unverified (no override) | 8 |
| REQ-OUT-01 | Success summary: artifacts, stack(s), verdict, next command | 9 |
| REQ-OUT-02 | Mode B launches the next stage instead of printing | 8, 9 |
| REQ-OBS-01 | All four terminal outcomes explicit + actionable | 10 |
| REQ-PORT-01 | Works on any host via conversational fallback | 6 |
| REQ-PORT-02 | Portable-root resolution; no Claude-only mechanism | 3 |
| REQ-GATE-02 | Refusal names disqualifying paths; points to alternative | 7.1, 10 |
| REQ-LIFE-02 | Resume / restart / cancel over own partial scaffold | 7.2 |
| REQ-LIFE-03 | Missing-toolchain branch (scaffold-anyway vs abort) | 7.4 |
| REQ-LIFE-04 | Unverified baseline clearly marked | 7.4, 9 |
| REQ-LIFE-05 | Commit style chosen at run time | 4 (Q9), 7.6 |

> **Boundary.** This document specifies the *orchestration half* of the lifecycle REQs.
> The mechanics they invoke — the gate check, scaffold emission, toolchain probe, commit —
> are specified in `02-helper-cli.md`. This document does NOT respecify helper internals
> (`02-helper-cli.md`) or template contents (`03-stack-templates.md`); it references both.

---

## 1. Deliverable & Front-Matter

The deliverable is a single prose skill body, `skills/forge-bootstrap/SKILL.md`, structured
and toned like the existing sibling skills (`skills/forge-init/SKILL.md`,
`skills/forge-verify/SKILL.md`). It opens with YAML front-matter:

```yaml
---
name: forge-bootstrap
description: "Scaffold a brand-new empty repository to a pipeline-ready, green baseline (structure, toolchain, passing lint+test, forge.config.json), then optionally chain into the pipeline. Use when the user runs /feature-forge:forge-bootstrap or asks to bootstrap/scaffold a new empty project for forge. Do NOT trigger on a non-empty repo (that is forge-init), or for general project setup outside the forge pipeline."
metadata:
  argument-hint: "[--mode-b] [--here|<target-dir>]"
---
```

Front-matter rules:

- `name` MUST be `forge-bootstrap` (matches the skill directory and the glob-discovered
  command `/feature-forge:forge-bootstrap`).
- The `description` MUST encode the trigger ("bootstrap/scaffold a new empty project") and
  the **negative** trigger that disambiguates it from `forge-init` (non-empty repo) and from
  generic setup tasks — mirroring the negative-trigger convention in
  `skills/forge-init/SKILL.md` and `skills/forge-verify/SKILL.md`.
- The skill is **unnumbered** (PRD §5): no `REQ-XXX-NN` spine, a sibling of `forge-init` /
  `forge-fix` / `forge-verify`, not a numbered pipeline stage.

### 1.1 Spec-purity body budget (constraint)

The prose **body** (everything after the front-matter) MUST stay **≤ 300 lines and ≤ 5000
words** — a hard `validate.sh` gate (`01-architecture-layout.md` §6.1,
`scripts/check-spec-purity.py`). This is the architectural reason the body delegates **all**
mechanics to `scripts/forge-bootstrap.py`: the body holds only the interview text, the
decision branches, the completion-summary template, and the Mode B hand-off. The body MUST
NOT inline file-generation logic, template contents, config field lists, or the greenfield
allow-list — those live in the helper (`02-helper-cli.md`) and in `00-core-definitions.md`
(referenced, not duplicated). Keeping the body lean is a correctness requirement, not just
style: a body over budget fails CI.

---

## 2. Skill Responsibilities (what the body owns)

Per the actor split (`00-core-definitions.md` §1, tech-spec §3.1), the skill body owns
exactly:

1. The **interview** — the question set (§4), host-adapted via `AskUserQuestion` with a
   conversational fallback (§5, §6). The **skill owns the question set**; the helper receives
   only the resolved `--answers` JSON (`00-core-definitions.md` §5, tech-spec §3.9).
2. All **decisions** that branch the flow — gate refusal, resume vs restart vs cancel,
   scaffold-anyway-unverified vs abort, commit vs stage-only, Mode A vs Mode B.
3. The **completion summary** — rendered from the helper's JSON (§9).
4. The **Mode B hand-off** — invoking `forge-1-prd <feature>` or `forge-0-epic <epic>`
   skill-to-skill (§8).

Everything else (gate, git init, scaffold, config write, sentinel, verify, commit) is the
helper's; the body invokes it as a black box over the contracts in `00-core-definitions.md`
§4/§5/§8 and `02-helper-cli.md`.

---

## 3. Portable-Root Prelude (REQ-PORT-02)

Every bash invocation in the body MUST begin with the **byte-identical** portable-root
prelude used across the pipeline (`01-architecture-layout.md` §2.2,
`references/shared-conventions.md`, `references/portable-root.md`), then invoke the helper:

```bash
R="$(bash -c 'for d in "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/*/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-bootstrap.py" <subcommand> "<target-dir>" --json [...]
```

Rules (REQ-PORT-02):

- `forge-root.sh` is **content-addressed** (it identifies a plugin root by the presence of
  `scripts/epic-manifest.py` + `.claude-plugin/plugin.json`), so it resolves under any
  agent's directory layout — **no Claude-only mechanism** (`01-architecture-layout.md` §2.2).
- `<target-dir>` is the **project cwd being bootstrapped** (default `.`, or the
  `<target-dir>` argument), distinct from `$R` (the plugin root). The helper resolves its own
  template dir from `__file__`, so no env var is needed (`00-core-definitions.md` §1.1).
- The body MUST NOT hardcode any plugin path, `~/.claude/...` path, or assume a Claude-only
  install location — it always goes through `$R`.

The skill reads `forge.config.json` for `specsDir` only if one already exists (normally it
does not on greenfield); when absent it passes the default `--specs-dir ./specs` so the gate
allow-lists the right specs directory (`00-core-definitions.md` §3, allow rule 1).

---

## 4. Interview Question Set (REQ-INPUT-01..07)

The body MUST present exactly the following questions, in order, each mapped to its
requirement and default/seed rule (tech-spec §3.9). The resolved answers populate the
`Answers` payload (`00-core-definitions.md` §5) handed to `scaffold --answers`. Questions Q7,
Q8 govern Mode B; Q9 governs commit style (REQ-LIFE-05).

| # | Question | REQ | Default / seed rule | `AskUserQuestion` option set |
|---|----------|-----|---------------------|------------------------------|
| Q1 | Project name? | REQ-INPUT-01 | default = inferred from the target directory basename (confirm) | free-text confirm; pre-filled with the inferred default |
| Q2 | One-line purpose? | REQ-INPUT-02 | no default; seeds README + config metadata | free-text |
| Q3 | Language / stack? | REQ-INPUT-03 | required; no default | `typescript` / `python` / `go` / `rust` / `generic` |
| Q4 | Package manager? | REQ-INPUT-04 | **asked only when** `PACKAGE_MANAGERS` (`00-core-definitions.md` §2) has the stack — TS: `npm`/`pnpm`/`yarn`, Python: `uv`/`poetry`/`pip`; **skipped** for go/rust/generic | the stack's `PACKAGE_MANAGERS[stack]` options |
| Q5 | License? | REQ-INPUT-05 | includes a `none` option; **seeded from a pre-existing `LICENSE`** when present (detect → default to it) | `MIT` / `Apache-2.0` / `none` (+ common others); pre-select the detected one |
| Q6 | Single package or monorepo? | REQ-INPUT-06 | default `single` | `single` / `monorepo` |
| Q6a | (monorepo only) How many members, and their names + per-member stack? | REQ-INPUT-06, REQ-MONO-01/02 | no default; one `Member` per name, each with its own stack (mixed-language allowed) | count then per-member name + stack (loop) |
| Q7 | Chain into the pipeline now (Mode B)? | REQ-MODEB-01 | default `no` (Mode A only) | `no, scaffold only` / `yes, chain into the pipeline` |
| Q8 | (Mode B only) First build: a single feature or an epic? | REQ-INPUT-07 | asked only when Q7 = yes | `feature` / `epic` |
| Q9 | Commit the baseline, or leave it staged? | REQ-LIFE-05 | default `commit` (single baseline commit) | `commit` (single baseline commit) / `stage only (no commit)` |

Question-ordering and gating rules:

- **Q4 is conditional**: the body checks the chosen stack against `PACKAGE_MANAGERS`
  (`00-core-definitions.md` §2) and **only asks Q4 when the stack is a key there**
  (REQ-INPUT-04). For go/rust/generic the member's `packageManager` is `null`.
- **Q5 seeding (REQ-INPUT-05, REQ-SCAF-09)**: when an allowed-meta `LICENSE` already exists
  (the gate allow-lists it, `00-core-definitions.md` §3), the body pre-selects the detected
  license as the default; the helper will **not overwrite** the existing file and will note
  it as a kept file in the summary (REQ-SCAF-09 — helper-side; surfaced in §9). The body never
  deletes or rewrites it.
- **Q6a (monorepo)**: asked only when Q6 = `monorepo`. The body collects member count, then
  per-member `name` and `stack` (and Q4-style package manager where that member's stack has a
  choice). Each becomes one `Member` (`00-core-definitions.md` §5) with a `path`
  (e.g. `packages/<name>`); a single package is one implicit `Member` with `path = "."`.
- **CI (`ci`)**: the body MAY also offer an optional "generate a CI workflow (lint+test)?"
  question (default per host); it sets `Answers.ci` (REQ-SCAF-07, REQ-MONO-04). CI templating
  is helper/template work (`02-helper-cli.md` §scaffold, `03-stack-templates.md` §CI).
- **Q7/Q8 placement**: Mode B opt-in (Q7) MAY be asked up-front; Q8 (feature vs epic) is
  asked only after a verified-green baseline and a successful commit (§8) — it MUST NOT be
  asked, nor Mode B launched, before that gate (REQ-MODEB-04).

Per the User Input Protocol (`references/shared-conventions.md`), the body MUST emit context
as plain text, then route **all** questions through `AskUserQuestion` (or the §6 fallback) —
never as inline prose questions, which stall the session.

### 4.1 Assembling the `--answers` payload

After the interview, the body assembles a single `Answers` JSON object
(`00-core-definitions.md` §5) — `projectName`, `purpose`, `layout`, `license`, `members[]`,
`modeB`, `modeBTarget`, `ci`, `commitStyle`, `author`, `host` — and passes it verbatim to
`scaffold --answers '<json>'`. The body does **not** invent fields beyond that schema; the
helper mirrors the payload into the sentinel (`00-core-definitions.md` §8) for resume.

Two fields are **not** interview questions — the body fills them from its runtime
(REQ-SCAF-06): `author` is seeded from `git config user.name` when available, else the
project name (it becomes the LICENSE copyright holder, 03 §10.2); `host` is the running
agent host (`"claude"` when the body runs under a Claude host — e.g. `AskUserQuestion` is
available — else `"codex"`/`"other"`/null). `host` drives the host-conditional agent file:
the helper always emits `AGENTS.md` and adds `CLAUDE.md` only when `host == "claude"`
(02 §4.5, 03 §10.1).

Example payload (single Python package, commit, no Mode B):

```json
{
  "projectName": "acme-svc", "purpose": "Billing service",
  "layout": "single", "license": "MIT",
  "members": [
    { "name": "acme-svc", "path": ".", "stack": "python", "packageManager": "uv" }
  ],
  "modeB": false, "modeBTarget": null, "ci": false, "commitStyle": "commit",
  "author": "Ada Lovelace", "host": "claude"
}
```

---

## 5. Host-Adapted Structured Input (REQ-INPUT-08)

All questions in §4 use **host-adapted structured input**: on a host that provides
`AskUserQuestion` (e.g. Claude), the body calls `AskUserQuestion` with the option sets in
§4, following the User Input Protocol (`references/shared-conventions.md`): context as text,
questions via the tool, recommend an option only when there is clear rationale (e.g.
recommend the inferred project name, the detected license).

When `AskUserQuestion` is unavailable, the body falls back to §6. The question **content**
(text, options, defaults) is identical across both paths — only the rendering changes.

---

## 6. Conversational Fallback (REQ-PORT-01, REQ-INPUT-08) — host-adaptation note

**forge-bootstrap pioneers this pattern** (tech-spec §3.7); there is no prior precedent in
the pipeline. The body MUST include a short, reusable **host-adaptation note** documenting it:

> **Host adaptation.** If the `AskUserQuestion` tool is available, ask the §4 questions
> through it. If it is **not** available (a non-Claude host such as Codex), emit the same
> questions as a single **numbered text list** — each line is one question with its options
> in brackets and the default marked — then **stop and wait for a single text reply**. Parse
> the reply positionally (answer N → question N); re-prompt only the unparseable items.

Fallback rendering example (numbered text list the body emits when `AskUserQuestion` is
unavailable):

```
Please answer these (reply with one line per number):
1. Project name? [default: acme-svc]
2. One-line purpose?
3. Stack? [typescript | python | go | rust | generic]
4. Package manager? [uv | poetry | pip]            (only shown for ts/python)
5. License? [MIT | Apache-2.0 | none]  (default: MIT — detected existing LICENSE)
6. Single package or monorepo? [single | monorepo] (default: single)
7. Chain into the pipeline now (Mode B)? [no | yes] (default: no)
9. Commit the baseline or leave it staged? [commit | stage-only] (default: commit)
```

Rules:

- The fallback list MUST contain the **identical** questions, options, and defaults as the
  `AskUserQuestion` path (REQ-INPUT-08); conditional questions (Q4 skipped for
  go/rust/generic; Q6a only for monorepo; Q8 only after a green baseline in Mode B) follow
  the same gating in both paths.
- After emitting the list, the body **waits for a text reply** before proceeding — it never
  assumes answers. This satisfies REQ-PORT-01 (works on any supported host) and REQ-INPUT-08
  (documented conversational fallback).
- The note is written so other pipeline skills can reuse it (it is the first occurrence of
  the pattern).

---

## 7. Mode A Orchestration Flow (default)

Mode A is the default path (REQ-MODEB-01): scaffold to a pipeline-ready baseline and print
the next command (§9). The body runs these numbered steps, each mapping to a helper
subcommand (tech-spec §5 skill→helper contract: **check → scaffold → verify → commit**):

```
1. Portable-root prelude (§3)            → locate $R
2. check                                  → gate + recovery detection
     ├─ eligible:false        → §7.1 greenfield refusal (REQ-GATE-02) — STOP
     └─ resumeMarker != null  → §7.2 resume / restart / cancel (REQ-LIFE-02)
3. Interview (§4)                         → assemble Answers (§4.1)
4. scaffold --answers <json>              → git init if absent; compose templates; write
                                            config; track artifacts into the sentinel
5. verify                                 → toolchain probe + lint/test per member
     ├─ toolchainPresent:false (exit 2) → §7.4 scaffold-anyway-unverified vs abort
     ├─ green:false  (exit 1)           → §7.5 not-green: surface failures, offer fix/abort
     └─ green:true   (exit 0)           → proceed
6. Completion summary (§9) — pre-commit preview                  (optional)
7. commit  [--stage-only per Q9]          → stage exact tracked list; single baseline commit;
                                            finalize/remove sentinel (REQ-LIFE-05/06)
8. Completion summary (§9) / Mode B hand-off (§8)
```

The body drives control flow off the helper's **exit codes and JSON** verbatim
(`00-core-definitions.md` §9): exit 0 ok, exit 1 actionable findings, exit 2 usage/IO **or
verify toolchain-missing**. The body never re-derives the gate or re-runs lint/test itself.

### 7.1 Greenfield refusal (REQ-GATE-02)

When `check` returns `eligible:false` (exit 1, `00-core-definitions.md` §4), the body MUST:

- Name **every** path in `CheckResult.disqualifying[]` (the disqualifying files), surfacing
  them verbatim.
- Direct the user to the correct alternative: **run `forge-init`, then `forge-1-prd`** (this
  repo already has content, so bootstrap is the wrong tool — PRD §3.1, REQ-GATE-02).
- **Touch no files** and STOP (the gate is read-only — REQ-SEC-01; the body adds nothing).

Example refusal text:

```
This repo is not empty — forge-bootstrap only scaffolds a brand-new project.
Disqualifying files found:
  - package.json
  - src/index.ts
To set forge up on an existing project, run:  /feature-forge:forge-init
Then start the pipeline with:                 /feature-forge:forge-1-prd <feature>
```

### 7.2 Resume / restart / cancel (REQ-LIFE-02)

When `check` returns `CheckResult.resumeMarker != null` (a `.forge-bootstrap.json` sentinel
from this tool's own prior partial run, `00-core-definitions.md` §4/§8), the body MUST NOT
treat it as a greenfield refusal (REQ-LIFE-02). It surfaces the prior run's `startedAt` and
`artifactsWritten[]`, then asks (via `AskUserQuestion`/fallback):

- **Resume** — re-use the sentinel's mirrored `answers` (no re-interview), re-run `scaffold`
  (idempotent over `artifactsWritten[]` — helper skips files already recorded,
  `02-helper-cli.md`), continue from step 5.
- **Restart** — discard the prior partial: the **body** deletes the recorded
  `artifactsWritten[]` tree + the sentinel (a skill-orchestration step — the helper exposes
  no clean/restart subcommand, `02-helper-cli.md` §8.2; cf. `05-testing-strategy.md` §3.7),
  then the interview runs fresh and `scaffold` re-emits from scratch.
- **Cancel** — stop without changes.

Resume is helper-backed (idempotent `scaffold` over `artifactsWritten[]`,
`02-helper-cli.md`). Restart cleanup is the **body's** responsibility (delete the recorded
tree + sentinel), since the helper exposes no clean/restart subcommand
(`05-testing-strategy.md` §3.7); the body then dispatches a fresh `scaffold`.

### 7.3 Scaffold

The body invokes `scaffold --answers '<Answers JSON>'` (§4.1). This is helper-owned
(git init if absent, template composition, config write, sentinel tracking —
`02-helper-cli.md`, `03-stack-templates.md`); the body does not inline any of it. On success
the body proceeds to verify.

### 7.4 Missing toolchain — scaffold-anyway-unverified vs abort (REQ-LIFE-03/04)

When `verify` returns `toolchainPresent:false` (exit 2, `00-core-definitions.md` §4/§9), the
required tools for the chosen stack(s) are not installed on this machine. The body MUST:

1. Warn, naming which stack's toolchain is missing (from the `VerifyResult`).
2. Ask **scaffold-anyway (unverified) vs abort** (`AskUserQuestion`/fallback, REQ-LIFE-03).
3. **If scaffold-anyway:** proceed to commit, and **clearly mark the baseline `unverified`**
   in the completion summary (§9, REQ-LIFE-04) — the body never claims a green baseline it
   could not verify.
4. **If abort:** stop; the sentinel stays `in-progress` so a later re-run can resume (§7.2).

An unverified baseline disqualifies Mode B from launching the next stage (REQ-MODEB-04, §8).

### 7.5 Not-green (lint/test failed)

When `verify` returns `green:false` with `toolchainPresent:true` (exit 1), the toolchain is
present but a resolved lint/test command failed. The body surfaces the failing
`CommandOutcome` entries (command + member, `00-core-definitions.md` §4) verbatim and offers
to abort or retry after the user investigates. This is a scaffold/template defect surface,
not a normal terminal outcome; the body does not silently proceed to a "green" summary.

### 7.6 Commit (REQ-LIFE-05/06)

The body invokes `commit` (or `commit --stage-only`, per Q9). This is helper-owned and MUST
follow the Git Commit Protocol (`references/shared-conventions.md`, REQ-SEC-02): stage the
**exact tracked file list** (never `git add -A`/`--force`/`--no-verify`), a **single baseline
commit** of the whole scaffold + `forge.config.json` (REQ-LIFE-06), then remove the sentinel
before staging so it never enters history (`00-core-definitions.md` §8). With `--stage-only`
the helper leaves the scaffold staged with no commit (REQ-LIFE-05). The body reads
`CommitResult` (`00-core-definitions.md` §4) — `committed`, `commitHash`, `staged[]` — and
renders it into the summary (§9). On commit failure the body surfaces the error and leaves
the sentinel `in-progress` (resumable) — it does **not** declare success.

---

## 8. Mode B Hand-off (REQ-MODEB-01..04, REQ-OUT-02)

Mode B is **opt-in** (Q7; default Mode A only — REQ-MODEB-01) and **agent-driven**: it hands
skill-to-skill to the next pipeline stage, **not** through the helper (tech-spec §3.8).

**Gate (REQ-MODEB-04):** Mode B launches the next stage **only after both**:

1. a **verified-green** baseline — `VerifyResult.green == true` (the single predicate Mode B
   gates on, `00-core-definitions.md` §4); and
2. a **successful commit** — `CommitResult.committed == true` (or, where the user chose
   stage-only, an explicit user override is required; bootstrap's default Mode B path
   expects a real commit).

If the baseline is **unverified** (toolchain missing, §7.4) or **not-green** (§7.5), the body
MUST NOT launch the next stage and MUST NOT even ask Q8 — it falls back to the Mode A summary
with the next command printed (§9), so the user can run it manually after fixing the
toolchain (REQ-MODEB-04). There is no "launch anyway on red" path.

**Flow when the gate passes:**

1. Ask Q8 — feature vs epic (REQ-INPUT-07) — if not already resolved.
2. **Feature path:** invoke `forge-1-prd <feature>` skill-to-skill, seeding `<feature>` from
   a confirmed name (kebab-cased per `references/shared-conventions.md`).
3. **Epic path (OQ-05):** invoke `forge-0-epic <epic>` skill-to-skill. The epic **name and
   initial decomposition are seeded from the project name + purpose** collected in the
   interview (Q1/Q2) and **user-confirmed** before hand-off — the body proposes a seed, the
   user edits/approves, then it launches (tech-spec §3.8, PRD OQ-05).
4. The body **launches** that stage **instead of printing its command** (REQ-OUT-02).

**Boundaries:**

- Mode B auto-launches **only the immediate next stage**; all **subsequent** pipeline stages
  remain normal, user-driven steps (REQ-MODEB-03). Mode B MUST NOT run stages unattended
  (PRD §6).
- The hand-off is skill-to-skill (invoking `forge-1-prd` / `forge-0-epic`), never via
  `forge-bootstrap.py`.

---

## 9. Completion Summary (REQ-OUT-01, REQ-LIFE-04)

On the success path (Mode A, or Mode B before/instead-of launch), the body **renders the
human-facing summary from the helper's JSON** (`VerifyResult` + `CommitResult`,
`00-core-definitions.md` §4) — the helper emits only structured JSON; the body owns the prose
(tech-spec §3.10). The summary MUST state:

1. **Created artifacts** — from `CommitResult.staged[]` (the scaffolded files +
   `forge.config.json`), including any **kept** pre-existing meta file (README/LICENSE not
   overwritten, REQ-SCAF-09).
2. **Resolved stack(s)** — the single stack, or each monorepo member's name + stack
   (from `Answers.members[]`).
3. **Verification verdict** — **`green`** (`VerifyResult.green == true`) or **`unverified`**
   (toolchain missing, §7.4 — REQ-LIFE-04). The body MUST never print "green" for an
   unverified baseline.
4. **Commit state** — committed (with `CommitResult.commitHash`) or staged-only.
5. **The exact next command** — `forge-1-prd <feature>` or `forge-0-epic <epic>`
   (REQ-OUT-01). **In Mode B the body launches that stage instead of printing the command**
   (REQ-OUT-02, §8).

Example success summary (Mode A, green, committed):

```
Bootstrap complete — pipeline-ready baseline.
  Stack:        python (uv)
  Created:      pyproject.toml, src/acme_svc/__init__.py, src/acme_svc/main.py,
                tests/test_smoke.py, .gitignore, README.md, LICENSE, AGENTS.md,
                CLAUDE.md, forge.config.json
  Kept:         (none — README/LICENSE generated fresh)
  Verification: green  (mypy . ✓   pytest ✓)
  Commit:       baseline committed (a1b2c3d)
  Next step:    /feature-forge:forge-1-prd <feature>
```

Example unverified variant (toolchain missing, scaffolded anyway):

```
  Verification: UNVERIFIED — python3/mypy not found on this machine; lint+test were not run.
                The baseline may not be green. Install the toolchain and re-run verify.
```

---

## 10. The Four Terminal Outcomes (REQ-OBS-01)

Every run of the skill ends in exactly one of four explicit, actionable outcomes
(`00-core-definitions.md` §4 table, tech-spec §3.10). Each is sourced from a helper result;
the body renders the matching action:

| Outcome | Source (helper) | Body action | REQ |
|---------|-----------------|-------------|-----|
| **Success** | `commit` exit 0 + `VerifyResult.green` (or §7.4 unverified-but-proceeded) | §9 summary, or Mode B launch (§8) | REQ-OUT-01/02, REQ-OBS-01 |
| **Greenfield refusal** | `check` `eligible:false` + `disqualifying[]` | §7.1: name the paths; point to `forge-init` + `forge-1-prd`; touch nothing | REQ-GATE-02, REQ-OBS-01 |
| **Missing toolchain** | `verify` `toolchainPresent:false` (exit 2) | §7.4: scaffold-anyway-unverified vs abort; mark **unverified** | REQ-LIFE-03/04, REQ-OBS-01 |
| **Partial-state detected** | `check` `resumeMarker != null` | §7.2: resume / restart / cancel | REQ-LIFE-02, REQ-OBS-01 |

The body MUST make each outcome **explicit and actionable** in its output (REQ-OBS-01): the
success path via §9; the other three via §7.1, §7.4, §7.2 respectively. No run may end
silently or ambiguously.

---

## Dependencies

Implement these first (this document builds on their definitions):

- **00-core-definitions.md** — `Answers`/`Member` (the interview output, §4/§4.1),
  `CheckResult`/`VerifyResult`/`CommitResult` (control-flow inputs, §7–§10), the `Stack` enum
  + `PACKAGE_MANAGERS` (Q3/Q4 gating, §4), the four-terminal-outcome table (§10), the
  exit-code contract (§7), and the sentinel schema (§7.2). **Referenced, never redefined.**
- **02-helper-cli.md** — the `check` / `scaffold` / `verify` / `commit` / `status` subcommands
  the body invokes (§7); the body treats them as a black box over their JSON + exit codes.
- **03-stack-templates.md** — what `scaffold` emits per stack + the CI template (§4 `ci`,
  §7.3); the body never inlines template contents.
- **01-architecture-layout.md** — the portable prelude (§3) and the ≤300-line/≤5000-word
  spec-purity body budget (§1.1).
- **references/shared-conventions.md** — User Input Protocol (§4/§5), Git Commit Protocol
  (§7.6), feature-name kebab-casing (§8).

Mode B additionally invokes the existing `forge-1-prd` / `forge-0-epic` skills (§8) — present
in the repo (`skills/forge-1-prd/`, `skills/forge-0-epic/`); no change to them is required.

## Verification

An implementation of `skills/forge-bootstrap/SKILL.md` matches this spec when:

- [ ] `bash scripts/validate.sh` passes spec-purity for the body: **≤ 300 lines and ≤ 5000
      words** (§1.1) — measured on the prose body after front-matter.
- [ ] The body contains all §4 questions in order, with Q4 gated on `PACKAGE_MANAGERS`
      (skipped for go/rust/generic), Q6a gated on monorepo, and Q8 gated on a verified-green
      Mode B baseline (REQ-INPUT-01..07).
- [ ] The body documents the conversational fallback (§6) with an identical question set to
      the `AskUserQuestion` path and an explicit "wait for a text reply" instruction
      (REQ-INPUT-08, REQ-PORT-01).
- [ ] Every helper invocation in the body uses the byte-identical portable-root prelude (§3)
      and passes `<target-dir>` distinct from `$R` (REQ-PORT-02); no hardcoded/Claude-only
      path appears.
- [ ] The body drives control flow off `check`/`verify`/`commit` exit codes + JSON
      (`00-core-definitions.md` §4/§9), branching to all four terminal outcomes (§10):
      success, greenfield refusal (names `disqualifying[]`, points to `forge-init` +
      `forge-1-prd` — REQ-GATE-02), missing toolchain (scaffold-anyway-unverified vs abort,
      marks **unverified** — REQ-LIFE-03/04), partial-state (resume/restart/cancel —
      REQ-LIFE-02).
- [ ] On greenfield refusal the body touches **no** files (REQ-SEC-01) and the flow STOPs.
- [ ] The completion summary (§9) reports created artifacts, resolved stack(s), the
      verification verdict (**green**/**unverified**, never "green" when unverified —
      REQ-OUT-01, REQ-LIFE-04), commit state, and the exact next command.
- [ ] Mode B (§8) launches `forge-1-prd <feature>` or `forge-0-epic <epic>` skill-to-skill
      **only** when `VerifyResult.green == true` and the commit succeeded — never on
      unverified/not-green (REQ-MODEB-04) — launching instead of printing the command
      (REQ-OUT-02), and seeding the epic name/decomposition from project name + purpose,
      user-confirmed (OQ-05). Subsequent stages stay user-driven (REQ-MODEB-03).
- [ ] The body inlines **no** mechanics that belong to the helper or templates (gate
      allow-list, file generation, config field set) — those are referenced, not duplicated
      (§1.1, §2).
