# Plan — unattended pipeline runs: decision authority, the brief, and the adversary

**Written:** 2026-09-02, on `main` @ `6015b36` (v0.19.0 / installer 0.3.6; Interaction Capability
Ladder merged, #258).
**Status:** **proposal** — assessment and recommended shape only; no code written, no owner approval yet.
**Tracking:** none yet.
**Scope:** let a forge pipeline run with most or all operator input **front-loaded**, while keeping
every stage's discipline (interview categories, integration analysis, traceability, verification)
intact; make that behavior correct on Claude, Codex, and Pi as first-class hosts; and change
**nothing** about the default, operator-driven pipeline.

This document lives in `roadmap/` (tracked, never published to the docs site — see
[`roadmap/README.md`](README.md)). It folds together a repo assessment (§2–§5) and an
architectural reframe that came out of discussing it (§6). §9 lists the decisions the owner
must settle before anything is built.

> **Reading this cold?** §1 is the problem and the reframe. §3 is the load-bearing design point
> (a fourth axis, not a fourth rung). §6 is the recommended shape. §8 is the phasing.
> If you only read two sections, read **§3** and **§6**.

---

## 1. The problem, and the reframe

### 1.1 The problem as first posed

The pipeline's value is a disciplined, detailed path through the whole feature lifecycle instead
of one-shot prompting that shortcuts the thinking. Its cost is a long process with frequent,
drawn-out pauses for operator input, especially in `forge-1-prd` and `forge-2-tech`. Most of
those pauses end with the operator picking the option the agent already labelled
`(recommended)`; wall-clock is gated on a human confirming what the agent proposed.

The first framing of a fix was: a config option under which the agent takes the recommended
option instead of prompting, chains stages, and ideally has a second agent (a different model)
answer the interview instead of the human.

### 1.2 Why that framing is only half right

The assessment (§4) shows the closed-choice half of that is cheap and precedented. The interview
half is not, for a structural reason: **most interview questions are open elicitation with no
option to select**. The operator is the *source* of requirements, not a chooser among the
agent's proposals. A second agent asked "what are the failure modes?" with no operator intent
to draw on produces generic, plausible, wrong requirements. Auto-selecting at an open question
is fabrication with a friendlier name.

### 1.3 The reframe: front-load the input, keep the discipline

If the goal is unattended automation, the better positioning is not "automate the interview" but
"**move the operator's input to the front, then run the prescribed process against it**." The
agent still walks every interview category, still does integration analysis, still weighs
alternatives — but it interviews a **brief** the operator wrote once, not a person sitting at the
terminal. Where the brief is silent, it decides within declared limits or escalates. And to keep
the agent honest when it is both proposer and decider, an **adversary** — a separate agent,
ideally on a different model — attacks its recommendations with the same context the agent had.

This is already how every other stage works: each consumes upstream *artifacts*, never
conversation. The interview is the one place where the truth lives in a human's head instead of
a file. The epic charter is the existing precedent — a feature under an epic arrives with
front-loaded intent (`charter`, `exposes`, `consumes`) that `forge-1-prd` treats as requirement
inputs. A standalone brief is the single-feature version of a charter.

Some decisions will not surface until later in the process. That is an acceptable trade-off
with an explicit escape hatch (§6.4), because pipeline state is already stage-resumable.

---

## 2. Ground truth (verified 2026-09-02 against `main` @ `6015b36`)

### 2.1 Three interaction axes exist; a fourth fits cleanly

| Axis | Nature | Where stated |
|---|---|---|
| **Host** (`--host claude\|pi\|generic`) | static per adapter bundle, build-substituted; selects command syntax and fresh-session wording, "nothing else" | `references/stage-exit-protocol.md` § Host and capability determination |
| **Interaction rung** (1 structured tool / 2 prose prompt / 3 non-interactive) | dynamic, self-assessed per turn | `references/shared-conventions.md` § Interaction Capability Ladder |
| **Verify capability** (`interactive\|manual`) | dynamic, permission-based | `references/stage-exit-protocol.md` |

Rung 3 is **conservative-only** (INV-6 in `roadmap/self-healing-resilience.md`): the declared
default "never advances a pipeline stage, launches a loop, applies a remedy, creates a branch,
commits, or records a decision", and interview sites at rung 3 emit `no-default: abort`.
`tests/test_interaction_ladder_prose.py` pins those clauses and requires every canon file that
contains `AskUserQuestion` to cite the ladder by title.

### 2.2 The zero-prompt flag pattern is established and tested

`loopRunner.reviewMode` (`prompt|always|never`), `loopRunner.agentMode` (`prompt|auto`),
`docsStage` (`prompt|skip`), `autoVerify`/`autoVerifyStages`/`autoFix`, `autoInvokeNextStage`.
Shared properties, pinned by `tests/test_zero_prompt_loop_config.py` and `tests/test_auto_verify.py`:

- the `prompt` default reproduces today's behavior **byte-identically**;
- the auto mode suppresses **only the interactive pick** — probes, verdicts, guards still run;
- the resolved choice is **always printed** ("never hidden");
- strict-`true` coercion (a string `"true"` does not enable);
- semantics live in an uncapped reference file; the capped skill body carries a pointer.

Cost of one flag, traced via `autoVerify`: schema; `scripts/forge-init.sh` heredoc **and** echo
block; `scripts/forge-bootstrap.py` config dict; `references/shared-conventions.md`
§ Configuration Reading; a resolver in `scripts/forge-session.py`; navigator and `forge-guide`
prose; a dedicated test file; README table; `docs-site/…/advanced/config.mdx`; CHANGELOG;
adapter regeneration. `tests/test_config_defaults_parity.py` fails if schema and `forge-init.sh`
disagree. Prefer the `loopRunner` / `effective-config` pattern (schema is the sole default
source) over the `autoVerify` pattern (defaults duplicated in Python and prose).

### 2.3 Existing automation of stage chaining

`/feature-forge:forge run` (navigator §6) is an opt-in auto-advance loop over consecutive stages.
Its stop conditions are explicit: an interview/decision stage (`forge-1-prd`, `forge-2-tech`),
`nextStage: null`, context over threshold, or a stage signalling needs-human. So chaining exists;
the gap is exactly the interview stages.

### 2.4 Answers-as-data has precedent

- `scripts/forge-bootstrap.py scaffold --answers <json>`: the interview yields a typed payload
  consumed by a script; the skill renders questions, the script owns semantics.
- `forge-decisions.json` (`references/forge-decisions-schema.json`): append-only,
  `question`/`answer`/`recordedBy`/`appliedBy`, written only by verbs. rauf ≥ 0.14 injects a
  recorded answer into the next loop iteration (`backlog answer`, `resume --answer`).
- The stage-exit DIRECTIVES payload (`runInStageVerify`, `autoFixEligible`, `verifyGate`) is the
  sanctioned "script decides, skill obeys" channel.
- `deferredDecisions[]` in `.pipeline-state.json` and the `notes` baton already carry decisions
  and concerns across sessions and stages.

**No per-feature record of interview answers exists.** Nothing captures "the operator chose B
over the recommendation." That store is the largest genuinely new surface in this plan.

### 2.5 Decision Support already produces the shape an adversary needs

`references/shared-conventions.md` § Decision Support requires every substantive question to
lead with a `(recommended)` option, put the trade-off in each option's description, give a
one-line rationale, and declare whether the recommendation is **evidence-backed** or
**preference**. `forge-2-tech` Step 3 calls itself "the richest decision surface in the
pipeline" and asks for exactly this. The tech-spec template's §3 carries "Decision, rationale,
alternatives considered." That is the adversary's input, produced today as prose convention.

### 2.6 Harness matrix for interaction and dispatch

| | Claude | Pi | Codex | Gemini / Copilot / Cursor |
|---|---|---|---|---|
| Question tool | `AskUserQuestion` | vendored extension registering the same name; **stripped** in `-p` / `--mode json` | none (prose, rung 2) | none (rung 2→3) |
| Programmatic answer channel | `PreToolUse` `updatedInput` exists in general; **no documented `answers` shape** for this tool; only `askUserQuestionTimeout` (auto-close, not auto-answer) | extension emits `rpiv:ask-user:prompt` events but has **no response channel**; its config shim reads no filesystem | none | none |
| Subagent dispatch | `Agent` tool, Anthropic models only | `pi-subagents`, cross-vendor, incl. external-CLI runner agents | `agents/*.toml`, only when asked | none |
| Non-interactive invocation | `claude -p` | `pi -p`, `--mode json` | `codex exec` | varies |

The build rewrites `AskUserQuestion` → "the host's question mechanism" for codex / gemini /
copilot / cursor and forbids the literal in those bundles (`tests/test_adapter_host_neutrality.py`).
**Any contract here must read correctly as prose after translation** — the constraint the ladder
was written under.

### 2.7 Headless foreign-agent invocation already exists one repo over

rauf's provider registry has **verified** non-interactive argv for `claude-cli`, `codex`
(`codex --ask-for-approval <p> exec --sandbox <m> -`, prompt on stdin), `gemini --yolo`,
`copilot --allow-all-tools`, `cursor-agent --print --force`, `pi -p`, and `generic-cli`
(`packages/loop/src/providers/` in the rauf repo). `rauf agents --json` reports availability.
This is the reusable primitive for invoking a *different* agent from *any* host, because every
host can run Bash. `docs/research/subagent-model-configuration.md` (2026-09-01) reached the same
conclusion for cross-vendor verification: Pi has it natively; everywhere else, shell out.

### 2.8 Prior stances this plan revisits

- **D5**, `plans/feature-forge-dx-context-enhancement-ideas.md` (local, gitignored): "interviews
  stay hard stops — never let a subagent conduct the PRD/tech interview." Its reason: the human's
  exposure to *what was decided* shrinks. Its mitigation (**D3**) is a decision ledger with
  `needsHuman` hoisting. This plan adopts D3 as the condition for reversing D5.
- **REQ-MODEB-03**, `specs/forge-bootstrap/PRD.md`: "Mode B MUST NOT run stages unattended."
  Scoped to bootstrap Mode B; not violated, but a bootstrap-launched pipeline with authority set
  needs one sentence of reconciliation.
- **Anti-churn verify-loop hardening** (R-05 severity floor, R-07 round ledger, R-08 narrative
  rule; #185): agent-versus-agent review loops did not converge on their own. The adversary
  inherits a round cap and a severity floor from day one.
- **Budget constraints** (`roadmap/self-healing-resilience.md` §2.3–2.4): `forge-verify` is at
  300/300 body lines; `forge-5-loop` at 4845/5000 words; the frontmatter description total is
  pinned at 4688/4688 and `EXPECTED_SKILL_COUNT` at 13. A new skill or any capped-body growth is
  a priced trade, not a free choice.

---

## 3. The load-bearing design point: a fourth axis, not a fourth rung

**Definition.** *Decision authority* answers: "who may answer a question this skill would
otherwise pose to the operator?"

| Authority | Meaning | Who answers |
|---|---|---|
| `operator` (default) | today, byte-identical | the operator, through the ladder |
| `auto` | at eligible closed-choice sites, take the `(recommended)` option; state it; log it | the driving agent |
| `brief` | answer from `BRIEF.md`; decide within declared limits where it is silent; escalate otherwise; adversary reviews recommendations | the brief, the driving agent within limits, the adversary as check |

**Rung 3 means "nobody can answer." Authority means "someone other than the operator is
authorized to answer."** They must never be the same knob:

- Rung 3's defaults stay no-write / no-proceed, exactly as the ladder states them. A headless run
  with **no** authority configured is still rung 3 and still stops. INV-6 and its test probes are
  untouched.
- Authority is **config-declared, never self-assessed**. Neither host, nor rung, nor the absence
  of a TTY implies it. This is INV-5 ("a host never implies a capability") extended one axis.
- The two compose: at rung 1 with authority `auto`, the agent simply does not pose the eligible
  question; at rung 3 with authority `brief`, the pipeline runs headless *because the config
  granted it*, and states that on every decision it takes.

Modelling this as a relaxation of rung 3 ("non-interactive may proceed if…") would break the
ladder's contract, its tests, and its safety story. Modelling it as a fourth axis leaves every
existing invariant alone.

---

## 4. Site taxonomy (what can actually be automated)

The 117 `AskUserQuestion` sites across canon fall into four kinds. The kind, not the count,
determines viability.

| Kind | Examples | `auto` | `brief` | Notes |
|---|---|---|---|---|
| **K1 Closed choice with a recommended option** | Standard Verify Gate; forge-3 document plan; forge-4 breakdown plan; forge-6 generate-vs-skip; Branch Setup; navigator advance gate; forge-5 re-verify-first; impl-verify offer | **yes** — take `(recommended)`; branch creation is reversible and *is* the recommended option, so allow it under declared authority (rung 3 alone still never creates) | yes (as `auto`) | the bulk of the "operator just picks recommended" pain |
| **K2 Open elicitation** | PRD interview categories (7 × 2–3 questions); tech interview decision areas (9); epic decomposition; "anything I'm missing?" | **no** — nothing to select; self-answering is fabrication | **only path** — answer from the brief; escalate on silence | the interview *is* requirements capture |
| **K3 Destructive / irreversible** | overwrite a completed artifact (Stage-Entry Guard case 3, Completion Re-check); `abandon`; `--force-standalone` fork; epic member pause; reconcile switch/fetch | **never** | **never** | falls through to the ladder's conservative default or STOP |
| **K4 Recovery / needs-human** | loop recovery interview; interrupted resume-vs-restart; preflight `local-write` remedies | resume is already the conservative default; allow `local-write` remedies (idempotent, git-visible) | later, with evidence | keep the operator in v1 |

Consequence: **`auto` over K1 makes `forge run` genuinely unattended from `forge-3-specs`
through `forge-6-docs`.** `brief` is what K2 needs, and is where the risk lives.

---

## 5. Harness agnosticism

**The contract is the prose protocol, on every host.** A rule of the form "when authority is
`auto` and the site class is eligible, do not pose the question; take the recommended option,
state it, log it via `decision-log`" reads identically after host-term translation, at every
rung. The User Input Protocol's rung-1 MUST needs one qualifier ("for every question you pose
*to the operator*") because `test_user_input_protocol_keeps_rung1_must` pins that sentence.

Compliance is probabilistic on every host. `eval/run-compliance-eval.py` is the existing
instrument; a new probe ("parked at a K1 gate with `auto` on: did the model log and advance
without prompting? at a K3 site: did it refuse?") is the acceptance test.

**Host-specific accelerators are optional and never the contract:**

- **Claude** — a `PreToolUse` hook auto-answering with the `(Recommended)` option would be
  *deterministic* rather than prose-compliant, which is attractive, but the `updatedInput` shape
  for supplying answers is undocumented. One-hour spike; Claude-only enforcement if it works.
- **Pi** — the vendored extension has an event seam but no answer channel; a patch there is
  re-applied by hand on every upstream refresh (`adapter-src/pi/UPSTREAM.md`). A first-party
  sibling extension (the `forge-loop-supervisor` precedent) is the cleaner home. Not needed for v1.
- **Codex / Gemini / Copilot / Cursor** — prose only.

The adversary and any other-model invocation are agnostic for one reason: they are a **Bash
shell-out to a foreign CLI** (§2.7), not a host feature.

---

## 6. Recommended shape

### 6.1 Two agent roles, kept apart

The first framing conflated them. They have different inputs, different prompts, and different
trust.

| Role | Purpose | Input | Honest outputs | Adversarial? |
|---|---|---|---|---|
| **Answerer** | proxy for the operator at K2 sites | `BRIEF.md`, the question, the stage so far | "the brief says X" · "the brief is silent; low blast radius; deciding Y with rationale" · `escalate` | **no** — it is brief-bound; an adversarial proxy misrepresents the operator |
| **Adversary** | attack the driver's recommendation at decision sites | PRD, persisted research report, the proposed decision, rejected alternatives, stated rationale, stack profile, epic charter | `agree` · `prefer <alternative> because …` · `needs-operator because …` | **yes** — that is its whole job |

The answerer needs operator intent and nothing else. The adversary needs no operator intent and
**full context in advance**, which on `forge-2-tech` is bounded and already artifact-shaped
(§6.3). The answerer may be the driving agent itself reading the brief; the adversary should be a
different agent, ideally a different model family, so its failure modes decorrelate.

### 6.2 Draft-then-critique instead of ask-then-answer

The "1–2 decision areas per turn, then wait" pacing exists for humans. Against a brief it is
unnecessary. The unattended shape of an interview stage is:

1. **Draft.** The driver runs the full interview *against the brief* — every category, every
   decision area — and drafts the complete artifact (PRD or tech spec), recording each decision
   with its alternatives and rationale, and marking each as evidence-backed or preference.
2. **Critique.** The adversary reviews the whole decision set once, with the full context.
3. **Revise.** The driver accepts, records a dispute, or escalates per decision.
4. **Gate.** Escalations are collected at the stage's existing blocking review gate.

That is one or two adversary calls per stage instead of fifteen, the adversary gets full
context by construction, and it slots into the review gate that already exists at
`forge-1-prd` Step 5 / `forge-2-tech` Step 6: the adversary review runs *before* the operator
review, or replaces it when the run is fully headless. It is structurally the same move as
"verify before the operator sees it" that in-stage auto-verify already made.

### 6.3 Two prerequisites that fall out of §6.2

- **The `forge-researcher` report becomes a persisted artifact** in the feature directory
  (e.g. `research.md`), not an ephemeral subagent return. The adversary needs it; resumability
  benefits regardless.
- **"Alternatives Considered" becomes load-bearing.** The tech-spec §3 decision entries carry
  decision / rationale / alternatives / mode in a shape the adversary can consume — a prose
  convention today, a structured obligation under `brief`.

### 6.4 Late-surfacing decisions: the escape hatch

Some decisions will not surface until the process reaches them. Tier the response by blast radius:

| Tier | Condition | Action |
|---|---|---|
| covered | the brief answers it | proceed; log `source: brief` |
| decide | brief silent **and** reversible **and** low blast radius | decide with recorded rationale; flag for review; log `source: inference` |
| escalate | irreversible, high blast radius, contradicts the brief, or the adversary returns `needs-operator` | hold the decision; **batch** at the stage boundary; pause the stage `in-progress` |

Pausing is cheap because the pipeline is already stage-resumable: the Stage-Entry Guard's
*Interrupted* arm, the `notes` baton, `deferredDecisions[]`, and rauf's needs-human /
answer-injection pattern all exist. The operator answers a short consolidated list and resumes —
`forge-bootstrap`'s `--answers` idea applied to a stage. Never pause mid-stage on a non-blocking
question; batch to the boundary.

### 6.5 The decision ledger

Every non-operator decision is appended to a per-feature, schema'd, append-only ledger by one
verb (`decision-log`), before the stage advances:

```json
{ "seq": 7, "stage": "forge-2-tech", "siteClass": "tech-decision", "authority": "brief",
  "question": "Session storage: JWT vs server-side?", "options": ["JWT (recommended)", "server-side"],
  "chosen": "JWT (recommended)", "mode": "evidence", "source": "brief",
  "rationale": "brief §Constraints: stateless API tier", "adversary": "agree",
  "recordedAt": "2026-09-02T18:04:11Z", "agent": null, "reviewedAt": null }
```

The ledger is what turns the operator's job into *reviewing decisions, not diffs*: the navigator
dashboard shows "N decisions since last operator review, M preference-mode, K escalated", and
every blocking review presents the artifact **plus** the ledger digest. It is the D3 mitigation
that makes reversing D5 defensible. Do **not** reuse `forge-decisions.json` — wrong key
(`itemId`), wrong lifecycle.

### 6.6 Where this genuinely loses

Features where the operator does not know what they want until probed. A live interview's
probing value is real. Mitigations: the brief interview (§6.7) is itself probing and can be as
long as today's PRD interview, but happens once and asynchronously; escalations catch the rest.
State this plainly in the docs rather than pretend the brief is always sufficient.

### 6.7 Surfaces: one new skill, one new agent, one axis

- **`forge-brief` (new skill).** The operator interview moved to stage minus one, producing
  `BRIEF.md` — goals, users, non-goals, constraints, risk appetite, preferences, and explicit
  "decide for me" areas. The only place the operator is expected to be present. It is a skill,
  not a template, because eliciting a good brief is an interview. **Budget:** trips
  `EXPECTED_SKILL_COUNT` and the frontmatter total (4688/4688, zero slack) — its description must
  be paid for by shrinking another (`forge-guide` at 528 and `forge-0-epic` at 485 are the
  candidates named in the sibling plan), or by a reviewed budget bump with a re-measurement.
- **`forge-adversary` (new agent definition).** Like `forge-verifier`: clean-room, read-only,
  own context, dispatched by the stage skill. On Pi it can be cross-vendor natively; elsewhere
  via the shell-out verb below.
- **`decisions` config object** carrying the axis (§3) — not a scatter of flat keys.
- **Unattended driving through the existing `forge run`** with authority set; stage skills gain
  one abstraction ("source of answers": operator | brief) rather than a second copy of each
  interview.
- **`forge-session.py` verbs:** `decision-log` (ledger writer); `ask-agent` (renders a prompt
  to a configured foreign CLI headlessly and returns JSON — the M1 mechanism, with an allow-listed
  provider table lifted from rauf's verified argv, read-only sandbox flags, and a probe).

### 6.8 Invariants (the "does not destabilize" contract)

| # | Invariant |
|---|---|
| **AP-1** | **Off by default, byte-identical.** `operator` reproduces every prompt exactly; guarded like `reviewMode`. |
| **AP-2** | **Authority is declared, never inferred.** Neither host, rung, nor no-TTY implies it. Rung-3 defaults are unchanged. |
| **AP-3** | **Never hidden.** Every non-operator decision is printed once and appended to the ledger before the stage advances. |
| **AP-4** | **Class-gated.** Eligibility is per site class via a new *Authority disposition* column on the ladder's site-class table; K3 is never eligible. |
| **AP-5** | **Safety surfaces still run.** Verify still runs clean-room or degrades as today; probes, guards, dirty-tree checks, version gates unaffected. Only the pick is suppressed. |
| **AP-6** | **Preference mode is policy-gated.** `policy: evidence-only` (default) takes only evidence-backed recommendations and escalates the rest; `all` takes both. |
| **AP-7** | **Stage review gates stay blocking by default.** They become the operator's batch checkpoint and show the ledger digest. A separate `stageReviewMode: auto` is required to auto-confirm them (fully headless CI only). |
| **AP-8** | **Budget-neutral in capped bodies.** Semantics go to an uncapped `references/decision-authority.md`; skill bodies get pointer clauses. |
| **AP-9** | **The adversary is a check, never an authority.** It cannot advance a stage or record a decision; it returns a verdict the driver must log. Round cap and severity floor apply (the #185 lessons). |
| **AP-10** | **The answerer is brief-bound.** It never invents intent; silence in the brief is `decide` or `escalate` (§6.4), never a guess presented as the operator's. |
| **AP-11** | **Different-model guard.** If the adversary resolves to the driver's own vendor and family, warn and log; decorrelation is the point. |

---

## 7. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Rubber-stamping: the driver labels whatever it wants `(recommended)` and takes it | medium | high | AP-6 default; adversary on every tech decision; ledger surfaces evidence vs preference; a `forge-verify` check that preference-mode decisions were reviewed; AP-7 |
| Weakening the ladder: authority phrased as "rung 3 may proceed" | medium | high | AP-2 wording in the canonical section; existing clause probes keep "never advances a pipeline stage" for rung-3 defaults; add a probe for "declared, never inferred" |
| Prose non-compliance: prompts anyway (benign) or auto-answers a K3 site (harmful) | medium | medium/high | site-class column, not per-site prose; compliance-eval probe; K3 sites carry an explicit "authority never applies here" clause |
| Brief-driven runs produce confident nonsense | high without a brief | high | brief mandatory for `brief`; §6.4 tiers; adversary; ledger + review gate; **measure before defaulting** |
| Adversary loop does not converge | medium | medium | AP-9 round cap + severity floor; adversary reviews the *set* once, not each question |
| Body budget breach | high if naive | medium (CI red) | AP-8; re-measure per PR |
| Adapter drift / host-neutrality failures | high first pass | low (CI catches) | regenerate adapters; keep the tool literal only in canon |
| Loss of operator steering in practice | medium | high | ledger digest at every review; dashboard counter; nothing auto-confirms a review without `stageReviewMode: auto` |
| New skill blows the frontmatter budget | certain | medium | priced trade (§6.7); decide before P2 |

---

## 8. The work

Each phase is one PR, independently revertible, behind `decisions.authority` defaulting to
`operator`.

**P0 — Canon design (prose + schema; zero behavior change).**
`references/decision-authority.md` (the axis, AP-1…AP-11, the site-class disposition column,
the output-line format, the escalation tiers, the two agent roles); one paragraph in the ladder
section stating that authority is a separate declared axis and rung-3 defaults are unchanged;
`references/forge-config-schema.json` gains `decisions { authority, policy, stageReviewMode,
stages, adversary { agent, model?, command? }, briefFile }` resolved via the schema-defaults
pattern; `references/forge-decision-ledger-schema.json` and the `decision-log` verb; prose
guards, schema/parity tests, verb conformance tests.

**P1 — `auto` at K1 sites.** `stage-exit` / `rank-features` emit `decisionAuthority` in
DIRECTIVES; the navigator advance gate, Standard Verify Gate, forge-3/4/6 plan gates, Branch
Setup, and forge-5 verify offers consume it; navigator dashboard and every blocking review show
the ledger digest; compliance-eval probe (K1 advance without prompt; K3 refusal). Result:
`forge run` unattended from `forge-3-specs` through `forge-6-docs`. Optional spike: the Claude
`PreToolUse` hook as an accelerator.

**P2 — `brief` for the interview stages.** `forge-brief` skill and `BRIEF.md` convention;
persisted research artifact; `forge-adversary` agent; `ask-agent` verb; draft-then-critique in
`forge-1-prd` and `forge-2-tech` under `brief`; escalation tiers and stage-boundary batching;
ledger + escalations at the blocking review. **Run this phase through the forge pipeline
itself** — it is a product change with real open questions, and the PRD interview for it is the
best test of whether a brief can carry a feature.

**P3 — Measure, then talk about defaults.** On a dogfood feature, produce the tech spec under
`operator`, `auto`, and `brief` (with and without the adversary) and compare `forge-verify`
findings. Only then discuss whether `auto` should ever be the `forge-init` recommendation. The
cheap pre-experiment: run today's `forge-2-tech` interview once with a foreign CLI reviewing the
drafted decision set, by hand, and see whether it changes anything.

**Do not:** add a fourth rung; reuse `forge-decisions.json`; infer authority from `-p` / no-TTY;
let `auto` touch K3; make the Claude hook or the Pi extension the mechanism; auto-confirm stage
reviews without a distinct opt-in; let the adversary decide anything.

---

## 9. Open decisions for the owner

| # | Decision | Recommendation |
|---|---|---|
| D1 | Nested `decisions{}` object vs flat keys in the `docsStage` / `agentMode` style | nested; five related knobs will otherwise sprawl |
| D2 | Is branch creation eligible under `auto`? (rung 3 says never create; the recommended option *is* create) | eligible under declared authority; rung 3 alone unchanged |
| D3 | `evidence-only` or `all` as the default policy | `evidence-only` |
| D4 | `ask-agent` as a forge verb vs a rauf verb (`rauf ask --agent …`) | forge verb; a rauf verb couples an interview feature to the loop runner and raises `minRunnerVersion` again |
| D5 | Pay for `forge-brief` by shrinking which description(s), or bump the frontmatter budget | decide before P2; shrink first |
| D6 | Attempt `brief` for `forge-0-epic` decomposition in P2, or defer | defer; decomposition is the highest-leverage operator decision in the pipeline |
| D7 | Should the adversary also review `forge-3-specs` plans and `forge-4-backlog` breakdowns | not in P2; measure on forge-2 first |
| D8 | Record the D5 reversal and its conditions (ledger, brief, evidence-only, adversary) in the P0 reference | yes |

---

## 10. Provenance

Assessment performed 2026-09-02 against `main` @ `6015b36` with read-only exploration of
canon, `scripts/forge-session.py`, the adapter builder and its host-neutrality tests, the Pi
`ask-user-question` extension, rauf's provider presets, and Claude Code's hooks / headless
documentation. The reframe in §1.3 and §6 came from the owner's observation that the product's
value is the disciplined path, not the interview mechanics, and that unattended runs should
therefore front-load operator input and keep the discipline rather than automate the pauses.
Line references above were verified at that commit; re-check before acting on them.
