# Plan — self-healing resilience across harnesses

**Written:** 2026-09-01, on `main` @ `3357c49` (v0.19.0 / installer 0.3.6, clean tree).
**Status:** **proposal** — no code written, no owner approval yet.
**Tracking:** [#244](https://github.com/garygentry/feature-forge/issues/244)
**Scope:** make the forge pipeline *diagnose and repair* environment/configuration faults
instead of halting on them, and make that behavior correct on **Claude, Codex, and Pi as
first-class hosts** with Copilot / Cursor / Gemini as best-effort.

This document lives in `roadmap/` (tracked, never published to the docs site — see
[`roadmap/README.md`](README.md)). Per-phase execution is tracked in GitHub issues; §11 lists
the decisions that must be settled before the phases they gate.

> **Reading this cold?** §1–§4 are the argument and the rules. §5 is the architecture.
> §6 is the harness matrix. §7 is the work. §8 is the constraint registry you *must* obey.
> If you only read two sections, read **§4 (invariants)** and **§8 (constraints)**.

---

## 1. The problem

feature-forge spans 13 skills, 6 adapter targets, an external loop runner (rauf), two
independent config surfaces, and a scripted state layer. The surface area for
configuration drift and environment failure is large, and the current design converts
almost all of it into a **hard stop with a printed hint**.

Two failure classes matter, and they are different:

**Class A — hard environment faults.** The runner is missing, too old, unwired, or the
configured `bin` is not on PATH. Today: an accurate diagnosis, a correct-in-the-common-case
hint, and a halt. The agent holds Bash and could fix most of these, but nothing tells it
that it may, or under what approval.

**Class B — silent partial configuration.** `stack`, `typeCheckCommand`, `testCommand`,
`smokeCommand` are `null` until forge-2-tech sets them. Skip or `--force` past that stage
and the pipeline *keeps working*: forge-3 writes specs, forge-4 writes a backlog, the loop
runs — but acceptance criteria carry no runnable command and forge-verify's `CHECK-I11` /
`CHECK-I21` degrade to advisory `not-applicable`. The result is a green pipeline producing
unverifiable output. Nothing warns at any point. **This is the more dangerous class**, and
it is the one the current architecture is least equipped for, because there is no failure
to catch — only an absence.

A third dimension multiplies both: **harness divergence**. The canon mandates
`AskUserQuestion` absolutely; the adapter build translates the *name* of that tool per host
but cannot conjure the *mechanism* where none exists. On a headless Codex or Pi print-mode
run, every gate in both classes becomes a silent stall rather than a stop.

---

## 2. Ground truth (verified 2026-09-01, not recalled)

Everything in this section was checked against the tree at `3357c49`.

### 2.1 What already works well

- **`forge-session.py doctor`** assembles real ground truth in one shot and **always exits
  0**: resolved plugin root + `version` + short `commit`, current branch, per-feature
  `stateBranch` / `branchMatchesState` / `branchReconcile` (`adopt-current` vs `warn-drift`),
  composed `backlogPath` + `backlogExists`, `invalidAutoVerifyKeys`, `duplicateConfigKeys`,
  `rootSandbox`. Covered by 15 tests in `tests/test_doctor.py`.
- **`forge-5-loop`'s post-run recovery** (`skills/forge-5-loop/references/recovery-procedure.md`)
  is a genuine repair loop: *enumerate → cluster → consolidated prompts → record-at-collection
  → apply → prove → gate & exit*, over an append-only `forge-decisions.json` written only by
  scripted verbs, with an explicit failure rule ("any scripted step that exits non-zero is
  surfaced verbatim and STOPS as a failed recovery — never reported as recorded"). **This is
  the pattern to generalize.**
- **Host/capability separation already exists and is doctrinally correct.**
  `stage-exit --host claude|generic|pi --verify-capability interactive|manual`, with
  `EXIT_HOSTS` commented *"A host NEVER implies a verification capability (REQ-EXIT-07)"* and
  `references/stage-exit-protocol.md` §"Host and capability determination" carrying an
  explicit **"Do not use `host == claude` as a capability proxy"** rule with worked cases.
  Guarded by `tests/test_capability_determination_prose.py` (including a non-vacuity test and
  an unskippable-guard test).
- **Every adapter target receives the full `scripts/` tree.** `adapters/{claude,codex,copilot,
  cursor,gemini,pi}/scripts/forge-session.py` all exist. **Anything implemented in a script is
  portable to all six hosts for free.** This is the single most important architectural fact
  in this plan.
- **Graceful degradation exists where someone thought about it:** `CHECK-I21` with a null
  `smokeCommand` → advisory `not-applicable`; `context-usage` on a non-Claude host →
  `{"available": false}`, exit 0; forge-verify skipping `rauf backlog validate` when the
  runner is absent.

### 2.2 The gaps

| # | Gap | Evidence |
|---|---|---|
| G1 | `doctor` is an **orphan** — **no skill invokes it**. | The only canon references are descriptive, not invocations: a parenthetical at `skills/forge-5-loop/references/runner-contract.md:104` and a field note at `references/pipeline-state-schema.json:36`. |
| G2 | `doctor` knows nothing about the **runner or toolchain**: no binary presence, no version-vs-`minRunnerVersion`, no `preconditionFile`, no null-command detection, no `gh`. | `doctor_report()` field list, `scripts/forge-session.py:1488`. |
| G3 | Gates **prescribe a hint, never an action**. | `skills/forge-5-loop/SKILL.md:84-106` — 1c/1d print `installHint`/`setupHint` and STOP. |
| G4 | The remedy can be **wrong when config is customized**. This repo sets `loopRunner.bin: "rauf-stable"`; if that binary vanishes, gate 1c fires and tells the operator to install `@garygentry/rauf` — the wrong fix. | `forge.config.json` + `effective-config` output. |
| G5 | Two config surfaces **diverge silently**: `forge.config.json.testCommand` vs `.rauf.json`'s `profile.commands.test` **and** `profile.verify` (note `verify` is a *sibling* of `commands`, not a member — `profile.commands` holds only test/typecheck/lint/build/format). The loop's iteration agent runs the runner's verify; forge-verify runs forge's. `.rauf.json` is checked for **existence only**. Also unchecked: `.rauf.json.installedBy` (here `rauf-manager@0.13.0`) vs the live runner. | `skills/forge-5-loop/SKILL.md:103`; grep shows no other `.rauf.json` reader in canon. |
| G6 | **Class B has no detector at all.** No stage asserts which config keys it needs. | No `config-completeness` concept anywhere. |
| G7 | **Host-capability divergence is undeclared for questions.** Only `forge-init` documents a degrade ladder; `shared-conventions.md` states an absolute mandate. | `skills/forge-init/SKILL.md:54-57` is the sole instance. |
| G8 | **Plugin-root failure is a bare `exit 1`** with no remedy, repeated ~20× as the bootstrap prelude. No root-version-vs-loaded-skills skew check. | The prelude literal; `_resolve_plugin_root()` returns version+commit but nobody compares. |
| G9 | **The feedback path has a dangling pointer in every non-bootstrapped project.** `references/templates/specs-hygiene/{AGENTS,CLAUDE}.md` *do* carry a "Tooling feedback" section with both issue URLs and the loop-safe rule, and shared-conventions' **Specs Directory Hygiene** copies them into `{specsDir}/` from **any** stage that first creates the specs tree — so a `forge-init` project does receive guidance. But those templates say *"See the project-root `AGENTS.md` 'Tooling feedback' section for the full flow"*, and **only `forge-bootstrap` writes that root section**. In a `forge-init` project (the existing-repo path — the common one) the pointer resolves to nothing. Separately, no skill knows to offer filing an issue when it hits an internal inconsistency. | `references/templates/specs-hygiene/CLAUDE.md:24-29`; `references/shared-conventions.md` § Specs Directory Hygiene; `skills/forge-bootstrap/references/templates/hygiene/CLAUDE.md:27-36`. |
| G10 | **No repair entry point.** `forge-guide` explains how the pipeline works, not how to fix it. | `skills/forge-guide/SKILL.md`. |

### 2.3 The binding constraint nobody can plan around

`scripts/check-spec-purity.py` Rule 4 hard-fails any `SKILL.md` **body** over
**300 lines** or **5000 words**. Measured at `3357c49`:

| Skill | Lines | Words | Line headroom |
|---|---|---|---|
| **forge-verify** | **300** | 4497 | **0** |
| **forge-5-loop** | **296** | **4990** | **4 lines / 10 words** |
| **forge-0-epic** | **297** | 2784 | **3** |
| forge-6-docs | 259 | 3268 | 41 |
| forge-2-tech | 241 | 3213 | 59 |
| forge (navigator) | 234 | **4660** | 66 lines / **340 words** |
| forge-bootstrap | 234 | 1900 | 66 |
| forge-4-backlog | 226 | 3544 | 74 |
| forge-3-specs | 185 | 2403 | 115 |
| forge-1-prd | 178 | 3392 | 122 |
| forge-guide | 176 | 1511 | 124 |
| forge-fix | 168 | 3762 | 132 |
| forge-init | 56 | 492 | 244 |

**The three skills this plan most wants to change have between 0 and 4 lines of headroom.**
That is not an obstacle to route around — it is the constraint that *dictates the
architecture*: logic goes in **scripts** (uncapped, portable to all 6 adapters, unit-testable),
prose goes in **`references/`** (uncapped), and skill bodies get **pointers only**.

Compounding it: **a new `references/` file only ships if a skill body cites it.**
`_fan_out_shared_references` in `scripts/build-adapters.py` copies a shared reference into each
bundle *by scanning skill bodies for the citation* — an uncited reference is silently omitted
from all six adapter bundles. So each new reference costs at least one body line, and on
forge-verify / forge-5-loop that line must be **bought back** by condensing existing prose in
the same PR.

> **The build is the only enforcer, and it fails silently.**
> `tests/test_reference_citations.py::test_every_new_or_moved_reference_file_is_still_cited`
> looks like a guard for this but is **not** one: it iterates a hardcoded `NEW_FILES` tuple of
> 9 files from a prior feature (`tests/test_reference_citations.py:43-56`). A newly added
> reference is invisible to it. **Any PR adding a `references/` file must append it to
> `NEW_FILES` by hand**, or CI stays green while the file ships nowhere.

### 2.4 The second binding constraint: the always-loaded frontmatter budget

`tests/test_always_loaded_surface.py` pins the **sum of all 13 skill `description:` values**
(raw, quotes included) at `FRONTMATTER_CHAR_BUDGET = 4688`, commented *"REQ-PERF-02 admits no
headroom, so this is an exact ceiling"*. It also pins `EXPECTED_SKILL_COUNT = 13` so deleting a
skill cannot silently create headroom.

Measured at `3357c49`: **4688 / 4688 — zero slack.**

| Skill | chars | | Skill | chars |
|---|---|---|---|---|
| forge-guide | **528** | | forge-4-backlog | 378 |
| forge-0-epic | **485** | | forge | 349 |
| forge-bootstrap | 407 | | forge-2-tech | 318 |
| forge-5-loop | 392 | | forge-1-prd | 317 |
| forge-3-specs | 357 | | forge-6-docs | 304 |
| forge-verify | 297 | | forge-init | 287 |
| forge-fix | 269 | | | |

**Consequence: a 14th skill cannot be added without paying for it.** Adding `forge-doctor`
(P4) requires *both* bumping `EXPECTED_SKILL_COUNT` (reviewable, fine) *and* either shrinking
existing descriptions by the new one's full length or bumping `FRONTMATTER_CHAR_BUDGET` with a
recorded re-measurement in the same PR — the exact process the constant's own comment
prescribes. `forge-guide` (528) and `forge-0-epic` (485) are the plausible donors. This
constraint, not aesthetics, is what decides D1.

---

## 3. What we are *not* going to do

Stated up front, because the failure mode of a "self-healing" project is scope creep into
autonomy the operator never asked for.

1. **We are not softening the hard gates.** A missing runner still stops the loop. The change
   is what happens *before* the stop: diagnose precisely, propose the exact command, offer to
   run it. `STOP` semantics on refusal are unchanged.
2. **We are not fabricating commands.** The repo has a strong, explicit norm here (`CHECK-I21`
   / `smokeCommand`: *"never fabricate or guess a command — run only the user-configured one"*).
   Auto-detecting `testCommand` is **detect → show evidence → confirm → write**, never silent
   inference.
3. **We are not letting the loop iteration agent self-heal.** It cannot ask, and `CLAUDE.md`
   already bars it from `backlog.json` / `state.json`. Its correct move on a broken environment
   is `RAUF_NEEDS_HUMAN:<reason>` plus a `progress.md` note. Self-healing belongs to
   forge-5-loop's preflight and post-run recovery, which *can* ask.
4. **We are not installing anything without explicit approval,** and never anything global or
   networked without it being named as such in the prompt.
5. **We are not filing GitHub issues autonomously.** Every issue is proposed, shown in full,
   and filed only on the operator's go-ahead — matching the wording the hygiene templates
   already use.
6. **We are not adding a second host-capability model.** We extend the existing
   `--host` / `--verify-capability` doctrine rather than inventing a parallel one.
7. **We are not touching `adapters/` by hand.** Ever. Canon → `build-adapters.py` → regenerate.

---

## 4. Invariants (the "does not destabilize" contract)

Every phase below must hold all of these. A PR that violates one is wrong even if it passes CI.

| ID | Invariant |
|---|---|
| **INV-1** | **Additive-by-default.** Every new check is `warn`-only on first landing. Nothing is promoted to `fail` until it has run clean against this repo *and* at least one dogfood project. |
| **INV-2** | **Zero happy-path output change.** On a fully-configured, healthy project, the new preflight prints **nothing** and asks **nothing**. This mirrors the recovery procedure's existing clean-tree silence. Tested explicitly. |
| **INV-3** | **`doctor` never exits non-zero and never raises.** It is a diagnostic; a broken environment is exactly when it must still run. Existing behavior, preserved and re-tested. |
| **INV-4** | **Remedies are data, not prose.** A remedy is a `{description, command, safety}` record emitted by a script — never a sentence duplicated across 13 skills. Prose duplication is how the 300-line cap gets breached and how hosts drift. |
| **INV-5** | **A host never implies a capability.** Reuse the existing REQ-EXIT-07 doctrine verbatim. `host == "claude"` is not a proxy for "can ask" or "can install", in either direction. |
| **INV-6** | **Every prompt declares its non-interactive default.** If the ladder bottoms out with no question mechanism, the documented default is taken and *stated in output*, never silently. |
| **INV-7** | **No skill body grows net-positive** in `forge-verify`, `forge-5-loop`, or `forge-0-epic`. Additions there are pointer lines paid for by condensing in the same PR. Verified by re-running the §2.3 measurement in each PR. |
| **INV-8** | **Reversible in one commit.** Each phase is a self-contained PR revertible without touching the others. No phase depends on an un-landed later phase. |
| **INV-9** | **Spec purity + drift guard green.** `python3 scripts/build-adapters.py` regenerated and `bash scripts/validate.sh` passing before every PR. Non-negotiable, per `AGENTS.md`. |
| **INV-10** | **First-class hosts are tested, not assumed.** Claude, Codex, and Pi each get an explicit assertion in `tests/test_adapter_host_neutrality.py` for anything this plan adds to canon prose. |

---

## 5. Architecture

### 5.1 Three layers, and why the split is forced

```text
  Layer 3  Skill bodies      pointers only          capped (§2.3) — 0–4 lines free
  Layer 2  references/*.md   procedures & doctrine  uncapped, host-translated at build
  Layer 1  scripts/*.py      detection & remedies   uncapped, portable to all 6 adapters,
                                                    unit-testable, host-independent
```

The cap in §2.3 makes this the only viable split, and it happens to be the *right* one:
detection logic in Layer 1 is exercised by pytest on every CI run and reaches Codex, Pi,
Copilot, Cursor and Gemini identically, with no prose translation risk.

**Rule of thumb for every item below: if it can be a script check, it is a script check.**

### 5.2 The check record

`doctor --json` gains a top-level `checks[]`. This is the load-bearing contract of the
whole plan.

```jsonc
{
  "id": "runner-version",                  // stable, kebab-case, documented in §12
  "status": "ok" | "warn" | "fail" | "na", // na = genuinely not applicable here
  "severity": "blocking" | "advisory",     // blocking = a stage gate depends on it
  "detail": "rauf-stable reports 0.13.2; minRunnerVersion is 0.14.0",
  "evidence": { "reported": "0.13.2", "required": "0.14.0", "bin": "rauf-stable" },
  "remedy": {
    "description": "Upgrade the configured runner binary",
    "command": "npm i -g @garygentry/rauf@0.15.0",
    "safety": "global-install"             // see 5.3
  } | null
}
```

Design notes:

- **`na` is a first-class outcome**, not a soft fail. A pure library with no runnable surface
  legitimately has no `smokeCommand` — precisely how `CHECK-I21` already behaves.
- **`remedy` may be `null`.** Some faults have no scripted fix (a corrupt manifest). Emitting
  `null` is honest; inventing a command violates §3.2.
- **`evidence` is structured**, so a skill can phrase the message rather than parroting a
  pre-baked English sentence that the host-term translator would have to rewrite.
- **`checks[]` is append-only across releases.** Removing or renaming an id is a breaking
  change to any skill that references it; add a new id and mark the old `na` instead.

### 5.3 The remediation safety ladder

Four tiers, declared **once** in `references/shared-conventions.md`, referenced by id everywhere:

| `safety` | Meaning | Policy |
|---|---|---|
| `read-only` | Diagnoses only. | Run freely, no prompt. |
| `local-write` | Writes inside the project, idempotent, git-visible. (`rauf install .`, writing a detected `testCommand`, copying a hygiene template.) | **Ask once, then run.** Precedent: the specs-hygiene `AGENTS.md` copy already auto-runs at this tier. |
| `global-install` | Touches the machine outside the project. (`npm i -g`, PATH edits.) | **Advise only.** Print the command; never run it. |
| `network` | Fetches from a remote. (registry queries, `curl \| bash`.) | **Advise only.** Never run. |

The **default posture is one tier more conservative than the tier permits** when the session
cannot ask (§5.4 rung 3): a `local-write` remedy with no question mechanism degrades to
advise-only rather than running unasked.

### 5.4 The Interaction Capability Ladder

This is the harness-divergence fix, and it generalizes what `forge-init` already does alone.
It is **parallel to, and independent of, `--verify-capability`** (INV-5): a session may be able
to ask but not dispatch, or neither.

```text
  Rung 1  Structured question tool present   →  use it (Claude AskUserQuestion; Pi's
                                                 bundled ask-user-question extension)
  Rung 2  No structured tool, but the host    →  ask in plain prose, wait for the reply.
          can still prompt and be answered       Same choice, different rendering.
          (Codex interactive)
  Rung 3  Genuinely non-interactive           →  take the DECLARED default, STATE that you
          (print/JSON mode, headless CI)          took it and why, and record it. Never stall.
```

Three obligations this imposes on canon:

1. **Every `AskUserQuestion` site declares a rung-3 default.** Today most do not, so rung 3
   is a stall. Auditing and annotating the sites is real work — see Phase P2.
2. **The ladder is stated once**, in `shared-conventions.md`, and pointed at — mirroring how
   `stage-exit-protocol.md` states the capability rule once and is guarded for it by
   `tests/test_capability_determination_prose.py`. Add an analogous guard.
3. **The build's host-term table already renames the mechanism** (`AskUserQuestion` →
   "the host's question mechanism") but cannot supply one where none exists. The ladder is the
   missing half. Any new prose must read correctly *after* translation — verified by
   `tests/test_adapter_host_neutrality.py`.

### 5.5 Reusing the recovery-procedure shape

The environment-repair procedure takes the same seven-step shape as the post-run recovery,
because that shape is proven in this codebase:

**enumerate** (`doctor --json` → `checks[]`) → **cluster** (group by remedy, so one prompt
covers "runner missing + not wired" rather than two) → **consolidated prompt** (one
`AskUserQuestion` per cluster, never per check) → **record** → **apply** (safety-ladder gated)
→ **prove** (re-run `doctor`, assert the check flipped to `ok`) → **gate & exit**.

It inherits the same **failure rule**: any scripted step exiting non-zero is surfaced verbatim
and stops the procedure as a *failed repair* — never reported as repaired. The **prove** step
is what makes this safe: no repair is ever claimed without re-running the detector.

---

## 6. Harness matrix

**First-class = tested and guaranteed. Best-effort = must not break, not guaranteed to be
optimal.**

| Capability | Claude | Codex | Pi | Copilot / Cursor / Gemini |
|---|---|---|---|---|
| Tier | **first-class** | **first-class** | **first-class** | best-effort |
| Gets `scripts/forge-session.py` | ✅ | ✅ | ✅ | ✅ (all adapters do) |
| Question mechanism | `AskUserQuestion` (rung 1) | prose prompt (rung 2) | bundled `ask-user-question` ext (rung 1); degrades to sequential dialogs on RPC/ACP; **fails clearly in print/JSON** (rung 3) | assume rung 2, degrade to 3 |
| Subagent dispatch | `Agent`/`Task` | `agents/*.toml` | `pi-subagents` ext (`agents/*.md` + `package.json` block + mirror placement) | varies — assume none |
| Background execution | `run_in_background` | none assumed | `forge-loop-supervisor` ext (Pi has no built-in background surface) | none assumed |
| `--host` value | `claude` | `generic` | `pi` | `generic` |
| Slash surface | `/feature-forge:*` | `/feature-forge:*` | `/skill:*` (translated) | `/feature-forge:*` |
| Fresh-session wording | `/clear` | neutral prose | `/new` | neutral prose |

### 6.1 Per-host obligations this plan creates

- **Claude** — no new mechanism. Rung 1 throughout. The `--host claude` literal in canon stays
  canonical and the build translates it (`_HOST_TERM_REPLACEMENTS`).
- **Codex** — the **rung-2 path is the one that must actually work**, because Codex has no
  structured question tool and today only `forge-init` documents the prose fallback. Every
  prompt this plan adds must read correctly as plain prose after host-term translation. This is
  the highest-risk host for the plan and gets its own test in P2.
- **Pi** — rung 1 *when the extension loaded*, rung 3 in print/JSON mode where the extension
  **fails clearly by design** (`docs/agents/pi.md:51`). So Pi is the host that most needs
  INV-6's declared defaults: a Pi headless run must take the default and say so, not error out
  of a preflight. Also the only host where the loop is supervised via an extension rather than
  backgrounded — the repair procedure must not assume a foreground runner.
  `tests/test_adapter_host_neutrality.py::test_pi_forge_5_loop_supervises_via_extension_not_foreground`
  already guards the adjacent property; extend it rather than adding a parallel guard.
- **Copilot / Cursor / Gemini** — inherit `--host generic`, rung 2→3. No target-specific work.
  The obligation is *only* that nothing regresses: the host-neutrality suite must stay green,
  and every new check must behave sanely with no question mechanism at all.

### 6.2 The host-detection question (open — see §11)

Nothing in canon tells a skill how to determine its own host or rung. `stage-exit` takes
`--host` as an argument whose literal value the *build* substitutes per bundle — an elegant
dodge that works because the value is static per bundle. The same trick works for the
capability ladder's **host** axis but **not** for its **rung** axis, which is dynamic per
session (Pi interactive vs Pi print mode differ within one bundle).

Recommended resolution: **build-substituted `--host` (static) + self-assessed rung
(dynamic, stated in prose once, exactly as `--verify-capability` is self-assessed today)**.
This is consistent with existing doctrine and adds no new mechanism. Confirm before P2.

---

## 7. The work

Six phases. **P0–P2 are the plan's core value; P3–P5 are worthwhile follow-ons.** Each phase is
one PR, independently revertible (INV-8).

---

### P0 — Extend `doctor` into a real health surface  *(script-only; zero canon churn)*

**Why first:** it is pure Layer 1 — no skill bodies, no `references/`, no adapter prose, no
body-cap pressure, no host divergence. It lands the `checks[]` contract everything else reads,
and it is independently useful the day it merges (`python3 scripts/forge-session.py doctor`
becomes the thing you run when a project is confused).

**Files:** `scripts/forge-session.py` (+ `tests/test_doctor.py`).

**Deliver:**
1. `checks[]` per §5.2, plus a `checksSummary: {ok, warn, fail, na}` rollup.
2. The check catalog in §12 — implemented **`warn`-only** (INV-1).
3. `--check <id>` to run one check, and `--json` unchanged in shape for every existing field
   (**strictly additive** — existing consumers and all 15 current tests keep passing).
4. Human output: `checks` rendered under the existing report, `ok`/`na` suppressed unless
   `--verbose`, so INV-2 holds for the human surface too.

**Explicitly in scope, because they are §2.2's worst gaps:**
- `runner-binary` / `runner-version` distinguishing **three** causes (G4): configured `bin` not
  on PATH ≠ runner not installed ≠ runner below `minRunnerVersion`. The remedy must follow the
  cause, and when `loopRunner.bin` is customized the remedy names *that* binary.
- `runner-wired` (`preconditionFile` present) and `runner-artifacts-stale`
  (`.rauf.json.installedBy` version vs live runner version) — G5.
- `runner-profile-drift`: `forge.config.json.testCommand` vs `.rauf.json.profile.commands.test`
  / `.verify` — G5. **`warn` forever**, never `fail`: divergence can be deliberate.
- `config-completeness`: per-stage required-key table, the Class-B detector — G6.
- `root-version-skew` — G8.

**Tests:** one per check id — a healthy fixture (`ok`), a faulted fixture (`warn` + correct
remedy + correct `safety`), and an inapplicable fixture (`na`). Plus: `doctor` still exits 0
with an unresolvable root and a bare directory (extend the existing
`test_doctor_survives_unresolvable_root_and_bare_dir`), and a **no-network** assertion — no
check may make a network call (INV-3, and it would make `doctor` slow and flaky).

**Rollback:** revert the commit. Nothing reads `checks[]` yet.

**Exit criteria:** `bash scripts/validate.sh` green; `doctor --json` on this repo reports
`fail: 0` and only expected `warn`s; every check id documented in §12.

---

### P1 — The Preflight & Self-Heal procedure  *(new reference; wired into forge-5-loop only)*

**Why second:** proves the §5.5 shape on the **one skill where the failure classes actually
bite in the field** (the loop), before generalizing. Deliberately narrow.

**Files:** new `references/preflight-and-self-heal.md`; `references/shared-conventions.md`
(safety ladder §5.3, stated once); `skills/forge-5-loop/SKILL.md` (**pointer lines only** —
INV-7, budget 4 lines, buy back by condensing 1c/1d prose into the new reference, which is a
net simplification of a currently-verbose section).

**Deliver:**
1. `references/preflight-and-self-heal.md` — the seven-step procedure, the failure rule
   (verbatim in spirit from `recovery-procedure.md` §1), the cluster-then-prompt rule, and the
   **prove** step.
2. The safety ladder in `shared-conventions.md`, referenced by `safety` value.
3. forge-5-loop gates 1c/1d rewritten as: run `doctor --check runner-*` → cluster → **one**
   consolidated prompt naming the exact remedy and its safety tier → apply if permitted →
   **prove** → proceed or STOP. **STOP semantics on refusal are unchanged** (§3.1).

**Tests:** `tests/test_preflight_self_heal.py` — clustering (runner-missing + not-wired → one
prompt, not two); safety-ladder gating (a `global-install` remedy is never executed); the prove
step (a remedy that does not flip the check to `ok` reports *failed repair*, never success);
INV-2 (a healthy fixture produces no output and no prompt). Also re-run the §2.3 line-count
measurement and record it in the PR body.

> **⚠ P1's most likely silent failure.** `references/preflight-and-self-heal.md` ships to the
> six bundles **only if a skill body cites it** (§2.3). INV-7 budgets just 4 lines in
> `forge-5-loop`, so dropping the citation line is the tempting shortcut — and nothing catches
> it: `tests/test_reference_citations.py` only scans its hardcoded `NEW_FILES` tuple, so CI
> goes green while `_fan_out_shared_references` silently ships the reference **nowhere**. The
> PR must (a) cite the file from `forge-5-loop/SKILL.md` and (b) **append it to `NEW_FILES`**.
> Verify by grepping the regenerated `adapters/*/` for the new filename before pushing.

**Rollback:** revert; gates 1c/1d return to today's text.

**Exit criteria:** forge-5-loop body ≤ 296 lines / ≤ 4990 words (**no net growth**);
`validate.sh` green; adapters regenerated.

---

### P2 — The Interaction Capability Ladder  *(the harness-divergence fix)*

**Why third:** P1's consolidated prompt is only correct on Claude until this lands. This is
the phase that makes Codex and headless Pi first-class rather than aspirational.

**Files:** `references/shared-conventions.md` (the ladder, stated once);
`skills/forge-init/SKILL.md` (replace its bespoke ladder with a pointer — it is the existing
prior art and should become the *reference implementation*, not a duplicate); an audit pass
adding declared rung-3 defaults at each `AskUserQuestion` site.

**Deliver:**
1. The ladder per §5.4 in `shared-conventions.md`, phrased to survive host-term translation.
2. Resolve §6.2 (host static / rung dynamic) and state it.
3. **Audit every `AskUserQuestion` site** and annotate its rung-3 default. Sites that are
   genuinely undefaultable (an interview question — there is no sane default for "what should
   this feature do") are marked **`no-default: abort with a stated reason`**, which is a
   legitimate and *documented* outcome, distinct from today's silent stall.
4. Soften the absolute mandate in `shared-conventions.md` § "User Input Protocol" to point at
   the ladder — **without** weakening the rung-1 requirement on hosts that have the tool. The
   existing anti-stall warning ("the user may not be prompted and the session will stall") is
   the *reason for* the ladder and stays.

**Tests:**
- `tests/test_interaction_ladder_prose.py` — modeled directly on
  `tests/test_capability_determination_prose.py`: the rule is stated once, every prompting
  surface carries the rule or a pointer, the guard is non-vacuous, the guard is unskippable.
- `tests/test_adapter_host_neutrality.py` — extend: the ladder text reads correctly in the
  **codex** (`generic`) and **pi** bundles after translation; no leaked `AskUserQuestion`
  literal in a non-Claude bundle.
- An explicit **Pi print-mode** assertion: the documented behavior is *take the default and say
  so*, not error (per `docs/agents/pi.md:51` this is the host where it matters most).

**Risk:** this is the highest-risk phase — it edits the most-loaded shared file and touches
prompt behavior on every host. Mitigations: prose-only (no logic change), the two prose guards
above, and INV-2 means a healthy Claude session sees **zero** behavioral difference.

**Rollback:** revert; `forge-init` keeps its local ladder (it is untouched by the revert if the
pointer swap is the last commit in the PR — **sequence it that way**).

---

### P3 — Tooling Feedback Protocol  *(closes G9)*

> **Scope note.** G9 is narrower than "no feedback path exists". The specs-hygiene templates
> already carry the guidance and already reach a `forge-init` project (shared-conventions'
> Specs Directory Hygiene fires from whichever stage first creates the specs tree, regardless
> of init vs bootstrap). The actual defect is a **dangling pointer**: those templates defer to
> a project-root "Tooling feedback" section that **only `forge-bootstrap` writes**. P3 closes
> that, and adds the missing skill-side behavior — no skill currently knows to *offer* filing
> an issue when it hits an internal inconsistency.

**Files:** `references/shared-conventions.md` (the protocol, once); `skills/forge-init/SKILL.md`
(emit the root hygiene block idempotently — it has 244 lines of headroom, the most in the repo);
pointer lines from the skills' failure paths.

**Deliver:**
1. A **Tooling Feedback Protocol** block: the two repos
   (`garygentry/feature-forge`, `garygentry/rauf`), the routing rule, the capture template
   (*what you ran / what you expected / what happened / a fix idea*), `gh issue create`, the
   **operator-approval-required** rule, and the **loop-safe rule** — *in an autonomous
   iteration, append to `progress.md`; never file mid-loop*. This text already exists and is
   well-written in `skills/forge-bootstrap/references/templates/hygiene/CLAUDE.md:27-36`;
   **lift it, don't rewrite it**, so the three copies stay consistent.
2. `forge-init` copies the hygiene block into the project's `AGENTS.md` / `CLAUDE.md`
   **idempotently, never overwriting** — the exact contract the specs-hygiene copy already uses
   in `shared-conventions.md` § "Specs Directory Hygiene". Reuse that block's shape verbatim.
3. A `gh-available` check in `doctor` (P0) so the protocol degrades to "here is the issue text,
   file it yourself" when `gh` is absent — rather than proposing a command that cannot run.

**Tests:** idempotence (second `forge-init` run does not duplicate or overwrite); the block
lands in both `AGENTS.md` and `CLAUDE.md` with correct host framing; `gh`-absent degradation.

**Note:** P3 is independent of P1/P2 and can land in parallel or first if a session is short.

---

### P4 — `forge-doctor` surface  *(closes G1/G10)*

**Files:** either a new `skills/forge-doctor/SKILL.md` **or** a `--doctor` mode on an existing
skill (see D1); adapter regeneration. Skills are **auto-discovered** by directory — there is no
manifest entry to add — but see the budget below.

**Deliver:** run the extended `doctor`, render `checks[]` grouped by severity with remedies,
offer to apply the safe ones through the P1 procedure and the P2 ladder. This is where P0–P2
become a thing the operator can *invoke*.

**Decision required first (D1), and §2.4 constrains it hard:**

- A **new skill** trips `EXPECTED_SKILL_COUNT = 13` *and* the frontmatter budget, which sits at
  **4688 / 4688 with zero slack**. Its description must be paid for by shrinking `forge-guide`
  (528) / `forge-0-epic` (485), or by a reviewed `FRONTMATTER_CHAR_BUDGET` bump with a recorded
  re-measurement in the same PR.
- **`--doctor` on the navigator** costs no new surface but spends the scarcest word headroom
  *among the P4 candidates* (**340 words**; repo-wide the scarcest is forge-5-loop at **10**),
  and mixes repair into a status dashboard.
- **`--doctor` on `forge-guide`** costs no new surface, has **124 lines / 3489 words free**,
  and is already the "ask instead of running a stage" advisory surface — repair fits its remit
  better than the navigator's.

**Revised recommendation: `forge-guide --doctor`.** It is the only option that adds no
always-loaded cost, has genuine body headroom, and is topically correct. A standalone
`forge-doctor` is still defensible if discoverability matters more than the budget — but that
is now an explicit, priced trade rather than a free choice.

---

### P5 — Promote checks from `warn` to `fail`  *(the INV-1 payoff)*

After P0–P4 have run against this repo and at least one dogfood project, promote the checks
that have proven zero false positives to `severity: blocking`, and wire the corresponding stage
gates to honor them. **`runner-profile-drift` stays advisory permanently** (divergence can be
deliberate). `config-completeness` is the candidate that matters most, because it is the only
detector for Class B.

This phase is deliberately unscheduled: it is gated on **field evidence**, not on a date.

---

## 8. Constraint registry — check this list before every PR

| # | Constraint | Where enforced |
|---|---|---|
| C1 | `SKILL.md` body ≤ 300 lines **and** ≤ 5000 words. forge-verify has **0** lines free; forge-5-loop **4**; forge-0-epic **3**. | `scripts/check-spec-purity.py` Rule 4 |
| C2 | Canon (`skills/`, `agents/`, `references/`) is **spec-pure** — no vendor frontmatter, no un-routed `${CLAUDE_PLUGIN_ROOT}`. | `check-spec-purity.py` |
| C3 | `adapters/` is **generated**. Regenerate with `python3 scripts/build-adapters.py`; the drift guard blocks an out-of-date tree. | `build-adapters.py --check` in `validate.sh` |
| C4 | Every new `references/` file **must be cited** from a skill body — which costs a body line (see C1) — **and appended to `NEW_FILES` by hand**. An uncited reference is **silently omitted from all six bundles with CI green**: the real enforcer is the citation-driven copy, and the test only scans a hardcoded list. | `_fan_out_shared_references` in `scripts/build-adapters.py` (the actual enforcer); `tests/test_reference_citations.py` `NEW_FILES` (pinned list, **not** a general guard) |
| C5 | Host-term translation rewrites `AskUserQuestion`, `Agent`/`Task`, `Monitor`, `run_in_background`, `/clear`, `--host claude`, `${CLAUDE_PLUGIN_ROOT}`. **New prose must read correctly after translation.** | `_HOST_TERM_REPLACEMENTS`; `tests/test_adapter_host_neutrality.py` |
| C6 | The bootstrap prelude is **byte-pinned**. Do not reformat it; spec-purity strips the exact bytes before its residual-var scan. | `check-spec-purity.py` |
| C7 | Pi's `adapter-src/pi/extensions/ask-user-question/` is a **vendored third-party snapshot** with a four-patch delta. Read `adapter-src/pi/UPSTREAM.md` before touching it. This plan should not need to. | `AGENTS.md` |
| C8 | Every change reaches `main` **via PR with green CI**. Never a direct push. | `AGENTS.md` |
| C9 | `bash scripts/validate.sh` is the single gate. Run it locally until green before pushing. | `AGENTS.md` |
| C10 | This repo's `smokeCommand` is `python3 scripts/forge-session.py doctor --json` — **P0 changes the smoke command's own output.** Confirm `CHECK-I21` still passes (exit 0) after every P0 commit. | `forge.config.json`; `CLAUDE.md` |
| C11 | Sum of the 13 skill `description:` values is pinned at **4688 chars with zero slack**, and the skill count is pinned at **13**. A 14th skill or any description edit must pay for itself in the same PR. | `tests/test_always_loaded_surface.py` (`FRONTMATTER_CHAR_BUDGET`, `EXPECTED_SKILL_COUNT`) |
| C12 | `tests/test_always_loaded_surface.py` **duplicates** the Rule 4 body caps in pytest (because `validate.sh` runs `check-spec-purity.py` separately). A body-cap breach therefore fails in **two** places — fix the body, never a constant. | same file |

> **C10 is the sharpest edge in this plan.** `doctor` is this repo's health smoke. Breaking it
> breaks the repo's own verification. Every P0 commit must end with
> `python3 scripts/forge-session.py doctor --json; echo $?` → `0`.

---

## 9. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| P0 breaks `doctor`'s exit-0 contract and takes out this repo's `smokeCommand`. | low | **high** | INV-3; C10 check after every commit; the 15 existing `test_doctor.py` tests are a regression net; wrap every new check in a per-check try/except that degrades to `status: "na", detail: "<error>"` rather than propagating. |
| P2's prose edits change prompt behavior on a healthy Claude session. | medium | high | INV-2 tested explicitly; P2 is prose-only; the two prose guards; sequence the `forge-init` pointer swap last so revert is clean. |
| Body-cap breach forces an emergency condense mid-PR. | **high** | medium | Re-run the §2.3 measurement *before* writing prose, not after; budget lines in the PR description; Layer-1-first architecture keeps most additions out of bodies entirely. Note the cap fails in **two** places (C12). |
| P4 stalls on the zero-slack frontmatter budget (§2.4) discovered late. | medium | medium | D1 is now priced and must be settled *before* P4's session starts (§10). The `forge-guide --doctor` option sidesteps it entirely. |
| A remedy is wrong for a customized config and the agent runs it. | medium | high | G4 is an explicit P0 deliverable (three distinct causes); the **prove** step catches a wrong remedy before it is reported as fixed; `global-install`/`network` are never executed. |
| Self-healing masks a real problem the operator should see. | medium | medium | Every applied remedy is stated in output; `warn`s are never auto-suppressed; the prove step reports what changed. INV-2 only silences the *healthy* path. |
| Codex rung-2 prose reads wrong after host-term translation. | medium | medium | Explicit codex-bundle assertion in P2's neutrality test; review the generated `adapters/codex/` text by eye once per phase. |
| Pi print-mode hits a rung-3 site with no declared default and errors. | medium | medium | P2 item 3 audits *every* site; the `no-default: abort with a stated reason` outcome makes the gap explicit rather than latent. |
| Scope creep into autonomous repair. | medium | high | §3 is the guardrail; the safety ladder caps blast radius by construction. |

---

## 10. Sequencing

```text
P0  (script-only, self-contained)          ──┐
P3  (independent; forge-init has headroom) ──┼─→ can run in parallel / either order
                                             │
P1  (needs P0's checks[])  ────────────────→ P2  (makes P1 correct off-Claude)
                                                  │
                                                  └─→ P4 (surface)  ──→ P5 (promote, field-gated)
```

**Suggested session boundaries** — each is one PR, one clean session:

| Session | Phase | Why it fits one session |
|---|---|---|
| 1 | **P0** | Script + tests only. No canon, no adapters, no body-cap math, no host reasoning. Largest single value/risk ratio in the plan. |
| 2 | **P3** | Small, independent, mostly lifting existing text into `forge-init` (244 lines free). Good short session. |
| 3 | **P1** | Needs the §2.3 buy-back math and careful forge-5-loop condensing. Do not combine with P2. |
| 4 | **P2** | Highest-risk prose phase; needs the full audit and two new prose guards. Own session. |
| 5 | **P4** | D1 (§11) must be settled *before* this session starts — §2.4's zero-slack budget makes it a priced decision, not a preference. |

**Start with P0.** It is the only phase with no canon churn, it de-risks everything downstream
by making the contract concrete, and it is independently useful even if the plan stops there.

---

## 11. Open decisions for the owner

| # | Decision | Recommendation |
|---|---|---|
| D1 | **P4 surface:** new `forge-doctor` skill, `--doctor` on the navigator, or `--doctor` on `forge-guide`. | **`forge-guide --doctor`.** §2.4: the always-loaded frontmatter budget is at **4688/4688, zero slack**, so a 14th skill must be paid for by shrinking another description or a reviewed budget bump. `forge-guide` has 124 lines / 3489 words free, adds no always-loaded cost, and repair fits its advisory remit. A standalone skill is defensible if discoverability outweighs the budget — but price it first. |
| D2 | **§6.2 rung detection:** build-substituted host + self-assessed rung, or something else? | Build-substituted host (static per bundle) + self-assessed rung (dynamic per session), mirroring `--verify-capability`. Adds no new mechanism. |
| D3 | **Does `local-write` auto-run after one approval, or ask every time?** | Ask once per session per remedy class. Precedent: the specs-hygiene copy already auto-runs at this tier with no prompt at all. |
| D4 | **Is `config-completeness` ever `fail`, or advisory forever?** | Blocking at P5 for forge-4-backlog and forge-verify only (the stages whose *output quality* depends on it); advisory everywhere else. |
| D5 | **Issue-filing:** file these as GitHub issues now, or track in this plan until P0 lands? | File P0 and P3 as issues now (independently actionable); hold P1/P2/P4 until P0's contract is real, so their issue text can cite actual field names. |
| D6 | **Dogfood target for INV-1 promotion:** which project? | Needs an answer before P5. `~/workspace/rauf` is the obvious sibling, but it is not a forge-pipeline consumer — a real consumer project is better evidence. |

---

## 12. Appendix — proposed check catalog

`warn`-only on landing (INV-1). Ids are stable and append-only (§5.2).

| id | Detects | Remedy `safety` | Gap |
|---|---|---|---|
| `plugin-root` | Root unresolvable, or resolver missing. | `null` (no scripted fix) | G8 |
| `root-version-skew` | Resolved root's `version`/`commit` differs from the loaded bundle's. | `global-install` | G8 |
| `runner-binary` | Configured `loopRunner.bin` not on PATH. **Distinguishes custom-bin from not-installed.** | `global-install` | G2, **G4** |
| `runner-version` | `versionCommand` output below `minRunnerVersion`, or unparseable. | `global-install` | G2 |
| `runner-wired` | `loopRunner.preconditionFile` absent (`.rauf.json`). | `local-write` (`rauf install .`) | G2 |
| `runner-legacy-layout` | `.ralph.json` / `.ralph/` present — un-migrated Ralph project. | `local-write` (`rauf migrate .`) | existing 1d case |
| `runner-artifacts-stale` | `.rauf.json.installedBy` version < live runner version. | `local-write` | G5 |
| `runner-profile-drift` | `forge.config.json.testCommand` ≠ `.rauf.json` `profile.commands.test` / `profile.verify`. **`verify` is a sibling of `commands`, not a member** — reading `profile.commands.verify` yields `None` and mis-reports. **Advisory forever.** | `null` | **G5** |
| `config-completeness` | Per-stage required keys null/absent (`stack`, `typeCheckCommand`, `testCommand`). **The Class-B detector.** | `local-write` after detect→confirm | **G6** |
| `config-schema` | `forge.config.json` fails `references/forge-config-schema.json`; duplicate keys; invalid `autoVerifyStages` keys. *(Partly exists — fold in, don't duplicate.)* | `local-write` | — |
| `backlog-present` | Composed backlog path missing for a feature past forge-4. *(Exists as `backlogExists` — promote to a check.)* | `null` | — |
| `backlog-valid` | Runner's `validateCommand` reports findings. | `null` | — |
| `branch-state` | `stateBranch` ≠ current. *(Exists as `branchReconcile` — promote.)* | `local-write` | — |
| `gh-available` | `gh` absent or unauthenticated — gates the P3 feedback protocol. | `global-install` | G9 |
| `sandbox-root` | Running as root without `IS_SANDBOX`. *(Exists as `rootSandbox` — promote.)* | `read-only` | — |

Five of the fifteen already exist as ad-hoc `doctor` fields. **Promote them into `checks[]`
rather than duplicating**, keeping the legacy top-level fields for the existing consumers and
tests (strictly-additive, per P0 deliverable 3).

---

## 13. Provenance

Investigated 2026-09-01 against `main` @ `3357c49`. Read in full: all 13 `skills/*/SKILL.md`
frontmatter + the gate/failure sections of forge-5-loop, forge-init, forge (navigator),
forge-verify; `references/shared-conventions.md`; `references/stage-exit-protocol.md`
§"Host and capability determination"; `references/vendor-construct-inventory.md`;
`skills/forge-5-loop/references/{recovery-procedure,agent-selection,runner-contract}.md`;
`AGENTS.md`; `AGENTS-SETUP.md`; `docs/agents/{codex,pi}.md`;
`scripts/forge-session.py` (`doctor_report`, `_resolve_plugin_root`, `EXIT_HOSTS`,
`VerifyCapability`, subcommand table); `scripts/build-adapters.py`
(`_HOST_TERM_REPLACEMENTS`, `_PI_HOST_TERM_REPLACEMENTS`, emitter list);
`scripts/check-spec-purity.py` (Rule 4); `tests/test_always_loaded_surface.py`
(`FRONTMATTER_CHAR_BUDGET`, `EXPECTED_SKILL_COUNT`, the duplicated body caps);
`tests/test_capability_determination_prose.py`, `tests/test_reference_citations.py`,
`tests/test_adapter_host_neutrality.py`, `tests/test_doctor.py` (guard shapes to model on).
Figures in §2.3 and §2.4 were **measured**, not recalled. Live checks: `doctor`,
`effective-config`, `check-spec-purity`, tool availability (`rauf` 0.15.0, `rauf-stable`
0.14.0, `gh`, `python3`, `node`).

**Two constraints were discovered mid-planning and changed the plan's shape**, which is why
they are called out rather than buried: §2.3 (0–4 lines of body headroom in the three target
skills) forced the Layer-1-first architecture in §5.1, and §2.4 (frontmatter budget at
4688/4688) inverted the P4 surface recommendation. Re-measure both before starting any phase —
they move with every merge to `main`.
