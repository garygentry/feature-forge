# Preflight & Self-Heal Procedure

The named procedure that turns "the environment is missing/stale/misconfigured" into a
clear stop or a scripted, consented repair — instead of a cryptic mid-run failure or a
silent unasked mutation. It runs whenever a skill gates on `doctor`'s structured
`checks[]` (`roadmap/self-healing-resilience.md` §5.2); today that is `forge-5-loop`'s
gates 1c/1d (`skills/forge-5-loop/SKILL.md`), which resolve the loop runner **before**
touching it. Its seven ordered steps: **enumerate → cluster → consolidated prompts →
record → apply → prove → return**.

## 1. Scope and the failure rule

**Input contract:** the caller has already run `doctor --json` narrowed to the `--check`
ids it cares about (never the full catalog inside a hard gate — an advisory check must
never block a launch it has no bearing on) and hands this procedure that call's `checks[]`
and `remedyClusters[]`. The procedure orchestrates that data; it never re-derives it and
never invents a remedy `doctor` did not emit (INV-4).

**The failure rule (applies to every step).** `doctor` itself never exits non-zero and
never raises (INV-3) — there is no non-zero exit to catch here. What *can* fail is a
remedy command: any remedy invocation that exits non-zero, times out, or produces
output the re-run in step 6 cannot confirm is surfaced **verbatim** and **STOPS** the
procedure with a **failed preflight** report — never reported as healed. This mirrors
`recovery-procedure.md` §1's failure rule exactly, narrowed to remedies (preflight has no
runner-answer/unblock apply mechanism of its own).

## 2. The seven steps

### Step 1 — Enumerate

- **Input:** the caller's `doctor --json` result (§1).
- **Decision point:** if every requested check is `ok` or `na`, there is nothing to
  cluster, prompt, apply, or prove: **skip steps 2–6 and return `ok` with no output and
  no prompt** (INV-2 — a fully healthy project produces zero new preflight text). This is
  the only step whose outcome the caller checks before calling the rest of the
  procedure at all.
- **Output:** the affected `checks[]` subset (`status` is `warn` or `fail`) with each
  entry's `remedy` and `severity`.

### Step 2 — Cluster

- **Input:** the affected checks from step 1.
- **Mechanism:** `remedyClusters[]`, already computed by `doctor_report` (pure
  `cluster_checks`, `scripts/forge-session.py`) — group by identical `remedy.command`,
  most-conservative `safety` wins the merge, `remedy: null` checks are **not** clustered
  (report-only, no prompt to build). Reuse it as-is; do not re-cluster by hand.
- **Output:** the final cluster set — one entry per distinct runnable remedy, each
  carrying its `checkIds[]`, `command`, `safety`, and `description` — plus the
  report-only set (affected checks with no `remedy` or no `remedy.command`).

### Step 3 — Consolidated prompts

- **Input:** the cluster set from step 2.
- **Mechanism:** one question per cluster (never one per check) via the host's question mechanism
  (rung 1/2) or the ladder's rung-3 default (§4). Name the **exact remedy command**, its
  **safety tier**, and **every member check id** the cluster covers — e.g. *"`runner-wired`
  and `runner-legacy-layout` both resolve by running `{bin} migrate .` (local-write).
  Run it?"*
- **Per the safety ladder** (`references/shared-conventions.md` § Remedy Safety Ladder):
  a `read-only` cluster is never prompted (run it and move to step 5); `local-write` asks
  **once per remedy class per session** — re-affirming the same `remedy.command` string a
  second time in the same session skips straight to apply; `global-install`/`network` are
  **never** prompted for execution — surface them as report-only advice (§5's
  advise-only path) even though `doctor` clustered them.
- **Report-only set — three shapes, all print once, plainly, with no question:** checks
  with no `remedy` at all (a corrupt manifest, an unresolvable config); a `remedy` whose
  `command` is `null` (reinstall-only or config-edit advice with nothing to run — never
  clustered, since `cluster_checks` skips these); and a `global-install`/`network`
  remedy (clustered by `doctor`, but never prompted for execution here).
- **Output:** per cluster, one of {approved, declined, advise-only (tier forbids
  execution), unaskable→advise-only (genuinely no way to ask and wait, §4)}.

### Step 4 — Record

- **Input:** every outcome from step 3.
- **Mechanism:** **output only** — a `preflight:` line per cluster, e.g.
  `preflight: runner-wired,runner-legacy-layout → {bin} migrate . [local-write] — approved+run`.
  The five outcome tokens are `run` (read-only, no prompt needed), `approved+run`,
  `declined`, `advise-only` (tier forbids execution — includes the report-only,
  null-command shape from §2 step 3), `unaskable→advise-only` (rung 3, no default
  permits the write). **The backlog's item-keyed decision record** (the durable
  store post-run recovery uses to survive a session boundary) **is NOT used here** — a
  preflight remedy is environment repair, not a backlog decision, and writing one there
  would durably attribute an environment fix to a backlog item that never asked for it.
- **Output:** the stated line, printed before step 5 acts on anything.

### Step 5 — Apply

- **Input:** every cluster whose step-4 outcome is `run` or `approved+run`.
- **Mechanism:** run `remedy.command` **verbatim** — never edited, never re-templated.
  `doctor` already rendered every token (`{bin}`, paths) into the command string; the
  procedure's only job is to execute exactly what was clustered.
- **Error:** a remedy that exits non-zero, times out, or cannot be run at all (binary
  vanished between the check and the apply) is surfaced verbatim and **STOPS** the
  procedure — **failed preflight**, per §1. Declined and advise-only clusters are not
  applied at all; they proceed straight to step 7's report.

### Step 6 — Prove

- **Input:** every cluster step 5 actually applied.
- **Mechanism:** re-run the **identical** `doctor --json` invocation the caller made in
  §1 (same `--check` ids, same flags) and re-read the member check ids' `status`.
- **Decision point:** **every** member check now `ok` → the cluster is healed, continue.
  **Any** member still `warn`/`fail` — including a partial move where some member ids
  flipped and others did not — is a **failed preflight**: report it, naming the healed and
  still-failing check ids from this re-read, never from the first run's stale statuses.
  A remedy that ran but did not prove is a failure, not a partial success (mirrors
  `recovery-procedure.md` §6's ran-but-nothing-moved shape).
- **Output:** either "all affected checks now `ok` → return" or a failed-preflight report.

### Step 7 — Return

- Return the final per-check statuses (post-prove where a remedy ran, original where
  declined/advise-only/report-only) to the caller. The procedure never selects the
  caller's own gate outcome — `forge-5-loop`'s 1c/1d decide HARD GATE FAILURE vs. STOP vs.
  proceed from these statuses; this reference only guarantees the statuses it returns are
  either the original `doctor` read (nothing was touched) or a freshly proven re-read
  (§6) — never a claim this procedure did not verify.

## 3. Safety ladder (pointer)

Every apply/prompt decision above is gated by the four-tier ladder declared once in
`references/shared-conventions.md` § Remedy Safety Ladder — `read-only` / `local-write` /
`global-install` / `network`. This reference never restates the tiers; it only names
which step consults them (§2 steps 3 and 5).

## 4. Rung-3 default (interim)

Until the Interaction Capability Ladder is canon (`roadmap/self-healing-resilience.md`
§5.4, forge#252), "cannot be asked" (§2 step 3) means genuinely **no way to ask and wait
for a reply at all** — neither a structured question tool NOR plain prose with a wait for
the answer. It is **not** the same as "no structured tool": a host that lacks a
structured tool but can still prompt in prose and wait (an interactive Codex session,
per its own turn-taking rules) is askable, and Step 3 asks it that way — this interim
rule never fires there. It fires only for a genuinely non-interactive invocation (a
headless `-p`/`exec`/JSON-mode run with no reply channel). Such a session follows the
conservative rule the safety ladder already implies: **degrade one tier stricter** — a
`local-write` cluster that cannot be asked is treated as `advise-only` (print the
command, never run it), and the outcome is recorded as `unaskable→advise-only` (§2 step
4). Never silently skip the report, and never take an unasked write as implied consent.

## 5. Message shapes

- **`runner-binary` / `runner-version` not `ok`** (blocking, no remedy proven) — **HARD
  GATE FAILURE**: STOP, do not proceed to run the loop, show the failing check's own
  `remedy.description` (and `remedy.command` when set) plus its raw `detail`/`evidence`
  for diagnosis. **Never substitute `loopRunner.installHint` for this** — three of
  `runner-binary`'s four warn shapes and one of `runner-version`'s are a **config fix**
  (a customized `bin` missing while the default is on PATH points at the config, not the
  install — G4), and `installHint` only ever describes installing the default package.
  When the remedy's `command` is `null` (a reinstall-only or config-edit instruction),
  there is nothing to cluster or apply — print the `remedy.description` as report-only
  advice (§2 step 3's report-only set) and STOP regardless.
- **`runner-legacy-layout` warn** — STOP: *"This project is still on the legacy **Ralph**
  layout. Run {check's `remedy.command`, e.g. `{bin} migrate .`} first (the loop runner
  only understands `.rauf/` and `RAUF_*` signals), then re-run
  `/feature-forge:forge-5-loop {feature}`."* Use the check's own `remedy.command` — never
  a hardcoded `rauf migrate .` — a customized `loopRunner.bin` changes the binary name.
- **`runner-wired` warn** — STOP and show `loopRunner.setupHint`, e.g. *"The loop runner
  isn't set up in this project ({preconditionFile} is missing). {setupHint}"*.
- A STOP lifts **only** after a permitted `local-write` remedy ran (§2 step 5) **and**
  the re-run (§2 step 6) shows the gating check `ok` — never on the remedy's exit code
  alone.

## 6. Failure taxonomy

| Failure | When it occurs | Reaches step 6's per-check test? | Report |
|---|---|---|---|
| **Failed apply** | A `run`/`approved+run` remedy exits non-zero, times out, or cannot start | No — stops before the test | Verbatim command output + which cluster; **failed preflight**; procedure stops |
| **Ran-but-not-healed** | The remedy exited 0, but the re-run still shows `warn`/`fail` for a member check | Yes — is the test failing | Healed/still-failing check ids named from the re-read; **failed preflight** |
| **Declined / advise-only / unaskable** | The operator declined, the tier forbids execution, or the session genuinely had no way to ask and wait (§4) | N/A — no apply attempted | Reported per §2 step 4; **not** a failure — the original `doctor` statuses stand, and the caller's gate (§2 step 7) still applies to them |

Rules: never report healed/succeeded past a failed step; a failed apply stops before the
per-check test, so a remedy that errored is never conflated with one that ran cleanly but
fixed nothing; a declined/advise-only/unaskable cluster is a normal outcome, not a
procedure failure — the caller's own gate still decides what an unhealed `warn`/`fail`
means for it (a blocking check stays a hard gate failure; an advisory one is just
reported).
