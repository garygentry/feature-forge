---
# GENERATED — DO NOT EDIT. Source: skills/forge-bootstrap/SKILL.md. Regenerate: python3 scripts/build-adapters.py
name: forge-bootstrap
description: Scaffold a brand-new empty repository to a pipeline-ready, green baseline (structure, toolchain, passing lint+test, forge.config.json), then optionally chain into the pipeline. Use when the user runs /feature-forge:forge-bootstrap or asks to bootstrap/scaffold a new empty project for forge. Do NOT trigger on a non-empty repo (that is forge-init), or for general project setup outside the forge pipeline.
---

# Bootstrap a Greenfield Repo

Take a **brand-new, empty** repository to a pipeline-ready, **green** baseline — a
scaffolded stack, a valid `forge.config.json`, and a passing lint+test — then optionally
chain into the pipeline (Mode B). You own the **conversation and decisions only**; every
mechanic (the greenfield gate, `git init`, scaffolding, the config write, the toolchain
probe, the commit) is delegated to the helper `scripts/forge-bootstrap.py`. Never inline
file generation, template contents, the config field list, or the greenfield allow-list —
they live in the helper and templates, referenced here, never duplicated.

`<target-dir>` below is the project being bootstrapped (default `.`, or the argument) — it is
**distinct from `$R`**, the plugin root. Drive control flow off the helper's exit codes and
JSON: **0** = ok, **1** = actionable findings, **2** = usage/IO **or** verify
toolchain-missing.

## Host adaptation (conversational fallback)

If the host's question mechanism is available, ask the interview questions through it. If it is
**not** available (a non-Claude host such as Codex), emit the same questions as a single
**numbered text list** — each line one question with its options in brackets and the default
marked — then **stop and wait for a single text reply**. Parse the reply positionally
(answer N → question N); re-prompt only the unparseable items. The question content (text,
options, defaults) and the conditional gating (Q4 skipped for go/rust/generic; Q6a only for
monorepo; Q8 only after a verified-green baseline) are **identical** across both paths — only
the rendering changes. Never assume answers; always wait for the reply.

Emit any context as plain text, then route **all** questions through the host's question mechanism (or the
fallback) — never as inline prose questions, which stall the session.

## Flow (Mode A — default)

```
1. Portable-root prelude            → locate $R
2. check                            → gate + recovery detection
     ├─ eligible:false   (exit 1)   → Greenfield refusal — STOP
     └─ resumeMarker != null        → Resume / restart / cancel
3. Interview                        → assemble the Answers payload
4. scaffold --answers <json>        → git init if absent; compose templates; write config;
                                       track artifacts into the sentinel
5. verify                          → toolchain probe + lint/test per member
     ├─ toolchainPresent:false (2)  → Missing toolchain: scaffold-anyway-unverified vs abort
     ├─ green:false      (exit 1)   → Not-green: surface failures, offer fix/abort
     └─ green:true       (exit 0)   → proceed
6. commit  [--stage-only per Q9]    → stage exact tracked list; single baseline commit;
                                       remove the sentinel before staging
7. Completion summary / Mode B hand-off
```

### Step 1 — locate the helper

Every bash invocation begins with the byte-identical portable-root prelude, then calls the
helper. Pass `--specs-dir ./specs` (the default) so the gate allow-lists the specs directory.

```bash
R="$(bash -c 'for d in "${FEATURE_FORGE_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-bootstrap.py" check "<target-dir>" --json --specs-dir ./specs
```

Never hardcode a plugin path or a `~/.claude/...` path — always go through `$R`.

### Step 2 — gate (`check`)

Read `CheckResult{eligible, disqualifying[], resumeMarker}`.

- **`eligible:false` (exit 1) → Greenfield refusal.** Name **every** path in `disqualifying[]`
  verbatim, then direct the user to the right tool — run `forge-init`, then `forge-1-prd`.
  **Touch no files** and STOP (the gate is read-only).

  ```
  This repo is not empty — forge-bootstrap only scaffolds a brand-new project.
  Disqualifying files found:
    - package.json
    - src/index.ts
  To set forge up on an existing project, run:  /feature-forge:forge-init
  Then start the pipeline with:                 /feature-forge:forge-1-prd <feature>
  ```

- **`resumeMarker != null` → Partial-state detected.** A `.forge-bootstrap.json` sentinel
  from this tool's own prior run exists — do **not** treat it as a refusal. Surface the prior
  run's `startedAt` and `artifactsWritten[]`, then ask **resume / restart / cancel**:
  - **Resume** — reuse the sentinel's mirrored `answers` (no re-interview), re-run `scaffold`
    (idempotent — the helper skips already-recorded files), continue from step 5.
  - **Restart** — discard the partial: delete the recorded `artifactsWritten[]` tree + the `.forge-bootstrap.json` sentinel (a skill-orchestration step — the helper has no clean subcommand), then run the interview and `scaffold` fresh.
  - **Cancel** — stop without changes.

  You perform no cleanup yourself; you only render the choice and dispatch the subcommand.

### Step 3 — interview

Ask exactly these, in order. Resolved answers become the `Answers` payload handed to
`scaffold --answers`.

| # | Question | Default / seed rule | Options |
|---|----------|---------------------|---------|
| Q1 | Project name? | default = target directory basename (confirm) | free-text, pre-filled |
| Q2 | One-line purpose? | no default; seeds README + config | free-text |
| Q3 | Language / stack? | required | `typescript` / `python` / `go` / `rust` / `generic` |
| Q4 | Package manager? | **only when the stack has a choice** — TS: `npm`/`pnpm`/`yarn`, Python: `uv`/`poetry`/`pip`; **skipped** for go/rust/generic | the stack's options |
| Q5 | License? | **detect & pre-select** from a pre-existing `LICENSE` (see gating); else default `MIT`. The helper keeps an existing `LICENSE` (REQ-SCAF-09) | `MIT` / `Apache-2.0` / `none` |
| Q6 | Single package or monorepo? | default `single` | `single` / `monorepo` |
| Q6a | (monorepo only) member count, then per-member name + stack | no default; one member each (mixed-language allowed) | loop |
| Q7 | Chain into the pipeline now (Mode B)? | default `no` | `no, scaffold only` / `yes, chain in` |
| Q8 | (Mode B only) First build: feature or epic? | asked **only after a verified-green baseline** | `feature` / `epic` |
| Q9 | Commit the baseline, or leave it staged? | default `commit` | `commit` / `stage only` |

Gating: Q4 is asked only when the chosen stack has a package-manager choice; Q6a only when
Q6 = `monorepo` (each member gets a `path` like `packages/<name>`; a single package is one
member with `path = "."`); Q7 may be asked up-front, but Q8 / Mode B launch are gated on a
verified-green, committed baseline (see below). You may also offer an optional
"generate a CI workflow (lint+test)?" question, setting `Answers.ci`.

License detect-and-seed (Q5, REQ-SCAF-09): when a `LICENSE` already exists in the target
(an allowed-meta file the gate let through), **read its first lines** and pre-select the
matching Q5 default — "MIT License" → `MIT`, "Apache License" → `Apache-2.0`, otherwise
keep the default and note the unrecognized license. The helper never overwrites the existing
`LICENSE`; this only seeds the interview default. Also set `Answers.author` from
`git config user.name` (fallback: the project name) and `Answers.host` to `claude` when
running on a Claude host (so the helper emits `CLAUDE.md` alongside `AGENTS.md`), else leave
it null.

**Assemble the payload.** Build one `Answers` JSON object — `projectName`, `purpose`,
`layout`, `license`, `members[]`, `modeB`, `modeBTarget`, `ci`, `commitStyle`, `author`,
`host` — and pass it verbatim to `scaffold --answers '<json>'`. Invent no fields beyond that
schema. Two fields come from your runtime, not the interview: `author` from `git config
user.name` (else the project name; it is the LICENSE copyright holder), and `host` — `"claude"`
when running under a Claude host (e.g. the host's question mechanism is available), else `"codex"`/`"other"`.
`host` drives the host-conditional agent file: the helper always emits `AGENTS.md` and adds
`CLAUDE.md` only when `host == "claude"`.

```bash
R="$(bash -c 'for d in "${FEATURE_FORGE_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-bootstrap.py" scaffold "<target-dir>" --json --answers '<Answers JSON>'
```

### Step 5 — verify

```bash
R="$(bash -c 'for d in "${FEATURE_FORGE_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-bootstrap.py" verify "<target-dir>" --json --answers '<Answers JSON>'
```

Read `VerifyResult{green, toolchainPresent, lint[], test[]}`.

- **`toolchainPresent:false` (exit 2) → Missing toolchain.** Warn, naming which stack's
  toolchain is missing. Ask **scaffold-anyway (unverified) vs abort**. If scaffold-anyway,
  proceed to commit and mark the baseline **unverified** in the summary — never claim green
  you could not verify. If abort, stop; the sentinel stays in-progress for a later resume. An
  unverified baseline **disqualifies Mode B** (no override).
- **`green:false` with `toolchainPresent:true` (exit 1) → Not-green.** Surface the failing
  `CommandOutcome` entries (command + member) verbatim; offer abort or retry-after-investigation.
  Do not silently proceed to a "green" summary.
- **`green:true` (exit 0)** → proceed to commit.

### Step 6 — commit

Invoke `commit` (or `commit --stage-only`, per Q9). Helper-owned: it stages the **exact
tracked list** (never `git add -A`/`--force`/`--no-verify`), makes a single baseline commit,
and removes the sentinel before staging so it never enters history. Read
`CommitResult{committed, commitHash, staged[]}`. On commit failure, surface the error and
leave the sentinel in-progress (resumable) — do **not** declare success.

```bash
R="$(bash -c 'for d in "${FEATURE_FORGE_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-bootstrap.py" commit "<target-dir>" --json --answers '<Answers JSON>' [--stage-only]
```

## Completion summary

Render the human-facing summary from the helper's JSON (`VerifyResult` + `CommitResult`). State:
created artifacts (from `CommitResult.staged[]`, including any kept pre-existing meta file);
resolved stack(s) (single, or each monorepo member's name + stack); the **verification
verdict** — `green` or `unverified` (never "green" for an unverified baseline); the commit
state (with `commitHash`, or staged-only); and the exact next command. In Mode B, **launch**
the next stage instead of printing the command.

```
Bootstrap complete — pipeline-ready baseline.
  Stack:        python (uv)
  Created:      pyproject.toml, src/acme_svc/..., tests/test_smoke.py, .gitignore,
                README.md, LICENSE, AGENTS.md, CLAUDE.md, forge.config.json
  Kept:         (none — README/LICENSE generated fresh)
  Verification: green  (mypy ✓   pytest ✓)
  Commit:       baseline committed (a1b2c3d)
  Next step:    /feature-forge:forge-1-prd <feature>
```

Unverified variant:

```
  Verification: UNVERIFIED — toolchain not found on this machine; lint+test were not run.
                Install the toolchain and re-run verify before relying on the baseline.
```

## Mode B hand-off (opt-in)

Mode B is **opt-in** (Q7; default Mode A) and **agent-driven** — it hands skill-to-skill to
the next pipeline stage, not through the helper.

**Gate:** launch the next stage **only after both** a verified-green baseline
(`VerifyResult.green == true`) **and** a successful commit (`CommitResult.committed == true`).
If the baseline is unverified or not-green, you MUST NOT launch the next stage and MUST NOT
even ask Q8 — fall back to the Mode A summary with the next command printed. There is no
"launch anyway on red" path.

When the gate passes:

1. Ask Q8 — feature vs epic — if not already resolved.
2. **Feature:** invoke `forge-1-prd <feature>` skill-to-skill, seeding `<feature>` from a
   confirmed, kebab-cased name.
3. **Epic:** invoke `forge-0-epic <epic>` skill-to-skill. Seed the epic name and initial
   decomposition from the project name + purpose (Q1/Q2), **propose it, let the user
   edit/approve**, then launch.
4. **Launch** that stage instead of printing its command.

Mode B auto-launches **only the immediate next stage**; every subsequent pipeline stage stays
a normal, user-driven step. The hand-off is always skill-to-skill, never via the helper.

## The four terminal outcomes

Every run ends in exactly one explicit, actionable outcome — make it explicit in your output;
no run ends silently:

- **Success** — `commit` exit 0 + green (or unverified-but-proceeded) → completion summary, or
  Mode B launch.
- **Greenfield refusal** — `check` `eligible:false` → name `disqualifying[]`, point to
  `forge-init` + `forge-1-prd`, touch nothing.
- **Missing toolchain** — `verify` `toolchainPresent:false` (exit 2) → scaffold-anyway-unverified
  vs abort; mark **unverified**.
- **Partial-state detected** — `check` `resumeMarker != null` → resume / restart / cancel.

---

## Host execution notes (Codex)

This skill was authored Claude-first; the body above refers to "the host's question mechanism", "the host's subagent mechanism", and "the host's background-execution mechanism". On Codex:

- **User input:** Codex has no structured question tool — ask the question directly and wait for the user's reply before proceeding. Never skip a required question or assume an answer.
- **Subagents:** spawn a Codex subagent using the named custom agent under `.codex/agents/<name>.toml`. Codex spawns a subagent only when explicitly asked; if the custom agent is unavailable, run that step inline yourself.
- **Background / monitoring:** run long-lived runner commands in your shell session and report progress as it arrives — there is no Claude-style background or monitoring tool to arm.
