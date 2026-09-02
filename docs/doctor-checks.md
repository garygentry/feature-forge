---
title: "Doctor Checks"
---

# `doctor` checks catalog

`python3 scripts/forge-session.py doctor --json` reports, after its eleven legacy
fields, a `checks[]` array — one record per entry in the registry below — plus a
`checksSummary {ok, warn, fail, na}` and `remedyClusters[]` (records whose remedies
share an identical `command`, merged, carrying the most conservative `safety` tier).
The human report ends with the same information: a `checks:` summary line, one
`! id: detail` line per finding and its `remedy [tier]: …` beneath; `--verbose`
adds the `ok`/`na` lines and `--check ID` (repeatable) narrows the registry.

This page is the reference for the ids, what each detects, when it is not
applicable, and what it suggests. It is kept in lockstep with the registry by
`tests/test_doctor_checks.py` (the **id** and **severity** columns must equal
`DOCTOR_CHECKS`, in order).

## Contract

- **Exit 0 for everything it finds.** A crashing check becomes an `na` record
  (`check crashed: …`); a crashing driver degrades every check to `na`; unreadable, non-UTF-8
  or wrongly-typed inputs are reported as data (a specs dir the process cannot list becomes a
  `specsDirError` field and an empty feature scan). The only non-zero exit is the command's own
  argument error — a `--check` typo — never a finding.
- **Warn-only in this release.** No check is promoted to `fail` yet
  (`FAIL_PROMOTED_CHECK_IDS` is empty); a check that reported `fail` is demoted to `warn` with
  `evidence.demotedFromFail: true`. Promotion is a later phase (#244 P5).
- **Remedies are data.** `remedy` is `{description, command, safety}` or `null`; doctor never
  executes one. `safety` is one of `read-only` < `local-write` < `global-install` < `network`.
- **No network.** The only subprocesses are `git` and `forge-root.sh` (legacy fields),
  `{bin} version --json` (once), `{bin} backlog validate …` (once per distinct backlog dir),
  `gh --version` and `gh auth token` (exit code only; stdout goes to `/dev/null`). The two
  runner templates come from `loopRunner` config and are only run by doctor when they start with
  `{bin}` — doctor only ever invokes the configured runner binary. The schema permits other
  shapes (`env X=1 {bin} …`, `node ./runner.js …`) and forge-4/forge-5 still run them; doctor
  simply reports such a template as unrenderable (`na` / a probe-error row) and cannot vouch for
  it. Never
  `gh auth status`, never the runner's `agentsProbeCommand`, never `rauf update --check`, never
  a remedy command. `tests/test_doctor_checks.py` proves this three ways: an argv allowlist over
  what scrubbed-PATH fake binaries record; an in-process `subprocess.run` recorder asserting every
  spawn is on the allowlist and equals no emitted remedy command (with `socket` patched to raise);
  and a run under `unshare -rn` giving identical verdicts.
- **Record shape.** `{id, status, severity, detail, evidence, remedy}` in that key order;
  `status ∈ ok|warn|fail|na`, `severity ∈ blocking|advisory`. Ids are stable and append-only.
- **Legacy output is untouched.** The eleven pre-existing keys keep their order and content, so
  `doctor --json` consumers written before the registry keep working.

`severity` says what a finding *would* mean for forge-5-loop once promoted: `blocking` checks
guard the loop launch; `advisory` checks are worth knowing but never gate anything.

## Registry

| id | severity | detects | `na` when | remedy (`safety`) |
|---|---|---|---|---|
| `plugin-root` | blocking | The sibling `forge-root.sh` fails to resolve an install root. | never | reinstall / set `FEATURE_FORGE_ROOT` (`global-install`, no command) |
| `root-version-skew` | advisory | This script's own bundle, the resolved root, and any `FEATURE_FORGE_ROOT`/`CLAUDE_PLUGIN_ROOT` override are different installs (different real path *and* not the same declared version). | `plugin-root` unresolved | reinstall so one bundle loads, or unset the override (`global-install`, no command) |
| `runner-binary` | blocking | `loopRunner.bin` is not on PATH. A customised `bin` missing while the default is present is a config fix, never the install hint. | `loopRunner` config unavailable (schema unreadable) | `installHint` (`network` when it fetches from a registry, else `global-install`) · config edit (`local-write`) |
| `runner-version` | blocking | `versionCommand` fails, prints no plain semver (pre-releases count as unparseable), or reports below `minRunnerVersion`. | runner not on PATH · `versionCommand` unrenderable | `installHint` (`network`/`global-install`) · reinstall (`global-install`) · fix `minRunnerVersion` (`local-write`) |
| `runner-wired` | blocking | `loopRunner.preconditionFile` (`.rauf.json`) is absent although a feature has reached forge-4-backlog. | file unset · absent before any feature reaches forge-4-backlog | `{bin} install .` (`local-write`) |
| `runner-legacy-layout` | blocking | `.ralph.json` or `.ralph/` beside a rauf project (un-migrated Ralph layout). | runner is not rauf | `{bin} migrate .` (`local-write`) |
| `runner-artifacts-stale` | advisory | `.rauf.json.installedBy` version differs from the live runner (older → refresh; newer → install the newer runner). | precondition file absent · live version unknown | `{bin} update .` (`local-write`) · `installHint` (`network`/`global-install`) |
| `runner-profile-drift` | advisory | `testCommand` matches neither `.rauf.json` `profile.commands.test` nor its sibling `profile.verify` (whitespace-normalised). Divergence may be deliberate. | `testCommand` unset · no precondition file · profile declares neither command | none |
| `config-completeness` | advisory | Keys forge-2-tech records are missing or blank for a feature far enough along: `stack` from forge-3-specs; `stack`, `typeCheckCommand`, `testCommand` from forge-4-backlog on (and for complete features). `smokeCommand` is optional — `evidence.optionalMissing` only. | no active feature has reached forge-3-specs | record the keys in `forge.config.json` (`local-write`, no command) |
| `config-schema` | advisory | `forge.config.json` is unreadable, not an object, has duplicate keys, invalid `autoVerifyStages` keys, or violates the bundled schema. Unknown top-level keys are `evidence.unknownKeys` only. | `forge.config.json` absent | fix the first finding (`local-write`) · reinstall when the bundled schema itself is unreadable (`global-install`) |
| `backlog-present` | blocking | A feature past forge-4-backlog (or complete) has no composed `backlog.json` on disk. | no feature has completed forge-4-backlog | none (re-run `/feature-forge:forge-4-backlog`) |
| `backlog-valid` | blocking | `{bin} backlog validate` reports findings (exit 1; first five in evidence) or breaks (timeout, crash, unrenderable `validateCommand`) for a feature whose next stage is forge-5-loop and whose backlog exists. One probe per distinct backlog dir. | `loopRunner` unavailable · runner not on PATH · `validateCommand` unset · no loop-ready feature with a backlog | none (fix the findings or re-run forge-4-backlog) |
| `branch-state` | advisory | A pending (non-complete) feature's recorded state branch differs from the current branch: `adopt-current` on a topic branch, `warn-drift` on the default branch. | not a git repo · no feature has a pending stage | `state-branch --feature … --branch <current>` · `git switch <recorded>` (both `local-write`) |
| `gh-available` | advisory | GitHub CLI absent, `gh --version` failing, or `gh auth token` exiting non-zero (no credentials). `evidence.tokenFromEnv` notes `GH_TOKEN`/`GITHUB_TOKEN`. | never | install gh (`global-install`, no command) · `gh auth login` (`network`) |
| `sandbox-root` | advisory | Running as root without `IS_SANDBOX` — the condition forge-5-loop patches at launch. | `os.geteuid` unavailable (Windows) | `export IS_SANDBOX=1` (`read-only`) |
| `interaction-mode` | advisory | Reports the session's interaction mode and host as **data** rather than a fault: `evidence.mode` is `interactive`/`non-interactive` (`rung: 3` for the latter) and `evidence.host` is the adapter id. Precedence: the `FORGE_INTERACTION` launcher stamp, then verified process ancestry, then `unknown`. Always `ok` when determined. | no signal is readable — reported as `unknown`, **never** as non-interactive | state it explicitly via `FORGE_INTERACTION` (`read-only`, no command) |

Per-feature checks (`config-completeness`, `backlog-present`, `backlog-valid`, `branch-state`)
carry one row per feature in `evidence.features[]`, each with its own `remedy`. The record's
top-level `remedy` is that row's remedy when every affected feature agrees (typically one), else
a `per-feature — see evidence.features[].remedy` pointer at the most conservative tier among
them, so a consumer never runs one feature's command for another.

## `interaction-mode`: the rung a skill reads instead of guessing

`references/shared-conventions.md` § Interaction Capability Ladder tells a skill to determine its
interaction rung. A model can observe **rung 1 vs rung 2** — whether it has a structured question
tool. It cannot observe **rung 2 vs rung 3** — whether anyone is there to answer. Left to guess it
guesses "interactive", emits a question into a headless run and stalls (#261). This check supplies
exactly the half the model cannot see, and deliberately not the half it can, so it informs the
ladder without becoming the host-implies-capability proxy INV-5 forbids.

**`unknown` is never `non-interactive`.** Guessing headless would make an interactive session
silently skip its questions and take no-write defaults — a silent behavior change traded for a
visible stall, which is worse than the bug. `unknown` means "self-assess the rung as before".

### `FORGE_INTERACTION` — the launcher contract

A launcher that *knows* the session it spawns has no reply channel states so:

```
FORGE_INTERACTION=non-interactive   # no reply channel: rung 3, declared defaults apply
FORGE_INTERACTION=interactive       # a human can answer
```

feature-forge only ever **reads** this variable — it never sets or exports it. Any other value is
`unknown` plus an `envStampError`. The name carries no `KEY`/`SECRET`/`TOKEN` substring, so no
host's environment policy strips it before the session sees it (verified through `codex exec`).

This is the only signal that reaches Codex. Every subprocess-observable alternative is disproven:
`isatty()` is false even in a fully interactive session; `CODEX_CI` and `TERM=dumb` are injected
into *every* Codex tool call in both modes; and Codex's shell tool executes under a long-lived,
init-parented `app-server` daemon that predates the session, so process ancestry there describes
the daemon's launch mode rather than this session's. `codex` is therefore excluded from the
ancestry mode detector by design — it still identifies the *host*, never the mode.

### Ancestry fallback

For direct headless runs outside a launcher, the nearest recognised harness ancestor decides:
carrying `-p`/`--print` is `non-interactive`, exposing arguments without one is `interactive`.
The asymmetry is deliberate — claiming non-interactive makes a skill take silent defaults, so it
is claimed only from a verified harness with an explicit headless flag, while claiming
interactive merely risks a question nobody answers, which is today's behavior.

**A harness that exposes no arguments at all yields no mode.** Measured: Pi overwrites its own
argv with its process title, so `/proc/<pid>/cmdline` for a `pi -p --mode json --no-session
--approve` session reads back as exactly `pi` with the flags erased. Without this rule that
session looks like "a verified harness with no headless flag" and is claimed as *interactive* —
a confident wrong answer in the dangerous direction, and the first P3.5 smoke run stalled at
rung 2 for exactly that reason. Note this also means a wrapper's argv is never borrowed: `timeout
600 pi -p …` puts `-p` in `timeout`'s command line, not Pi's, and under the loop the parent is
the runner's `node` process, which carries no such flag at all. The rule is written against the
argv rather than against Pi, so it covers any harness that sets a process title, and Pi begins
detecting for free if it ever stops.

So in practice ancestry answers for **Claude** (verified live: `claude -p` → `non-interactive`,
`rung 3`, via ancestry) and identifies the host — but not the mode — for Pi and Codex. Those two
get their mode from the launcher stamp, which is how every loop iteration is covered.

`evidence.ancestry` carries **only** each ancestor's pid, executable basename and any headless
flags. Raw argv never appears, and a basename that does not look like an executable (`sshd: gary
@pts/6`, kernel threads) is redacted to `?` — a parent's command line can carry credentials or a
username, and evidence lands in output that gets pasted into issues.

When the stamp and ancestry **positively contradict** each other, the check trusts neither: it
reports `warn` with `evidence.conflict` and a mode of `unknown`, so skills self-assess (i.e. ask)
rather than skip a question. That is the safe resolution in both directions, and `warn` is what
gets the record printed on the human path — an `ok` record is suppressed, so the operator whose
stray `export FORGE_INTERACTION=non-interactive` caused it would otherwise see nothing at all.

Ancestry that merely *cannot read* a mode is not a contradiction — that is the normal loop shape
for Pi and Codex, where the stamp rightly decides. The residual gap is a stamp leaked into a shell
whose harness ancestry also yields no mode (a bare `claude` with no arguments): nothing contradicts
it, so it is honoured. Accepted — it requires a deliberate manual `export`, and honouring an
explicit statement is the contract.

## Reading a report

```
checks: 13 ok, 2 warn, 0 fail, 1 na
   ! runner-artifacts-stale: .rauf.json was written by rauf-manager@0.13.0; the live runner is 0.14.0
      remedy [local-write]: rauf update .
   ! branch-state: 1 feature(s) with branch drift: widget (warn-drift: on 'main', state records 'forge/widget')
      remedy [local-write]: git switch forge/widget
```

A `warn` on a `blocking` check is the thing to fix before launching forge-5-loop; an
`advisory` warn is context. `na` is never a problem by itself — its `detail` names the
prerequisite (often another check id) that would make it applicable.
