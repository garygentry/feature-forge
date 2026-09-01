# Configurable subagent models (including cross-vendor verification)

**Date:** 2026-09-01 · **Status:** research only — no decision, no implementation
**Question:** Can forge specify, via configuration, which model (and vendor) a subagent runs on —
in particular the *verification* subagent, so that a different model family checks the supervising
model's work?

> Internal research, like `docs/claude-5/`. Not wired into `docs-site` and deliberately unpublished.
> Everything below is a snapshot of the tree at `55928e0`; re-check line references before acting on it.

---

## 1. How subagents are managed today

### 1.1 Canon → generated adapters, one way

Three canonical subagents live in `agents/*.md`:

| Agent | `model` | Other frontmatter |
|---|---|---|
| `forge-researcher` | `sonnet` | `maxTurns: 25`, `effort: medium` |
| `forge-spec-writer` | `opus` | `maxTurns: 30` |
| `forge-verifier` | `opus` | `maxTurns: 40`, `memory: project`, `skills: [forge-verify]` |

`scripts/build-adapters.py` fans these out to six targets. The property that matters most for this
question is at `scripts/build-adapters.py:85-113`: **subagent frontmatter is deliberately not a
fixed schema.** Each `AgentRecord` carries `claude_keys` — whatever non-`{name,description}` keys
the file actually has, in source order — and every emitter *enumerates that dict* rather than a
hardcoded list, so an unmapped key is drop-recorded rather than silently emitted
(REQ-GEN-06 / REQ-SCALE-01). `model` is already a first-class entry in `FRONTMATTER_KEY_ORDER`
(`scripts/build-adapters.py:120-152`).

**Adding a model-configuration key is cheap on the generator side.** That is not where the cost is.

### 1.2 Where `model` actually survives

| Target | Subagent construct | `model` disposition |
|---|---|---|
| `claude` | native `agents/*.md` | passed through verbatim |
| `pi` | `agents/*.md`, translated frontmatter | **dropped by decision D1** (see §2.1) |
| `codex` | `agents/*.toml` (name/description/instructions) | dropped — "no Codex custom-agent equivalent in safe mapping (TQ-1)" |
| `gemini` | prose only | dropped — no subagent construct |
| `copilot` | prose only | dropped — no subagent construct |
| `cursor` | prose only | dropped — no subagent equivalent |

Every drop is recorded in `adapters/GENERATION-REPORT.md`. **Four of six hosts have no subagent
surface at all**; on those, the verify step falls back to running inline in the main session
(`references/process-overview.md`: "All three subagents are optional… the corresponding skills fall
back to running inline").

### 1.3 Dispatch is prose-driven, not code-driven

No script spawns a subagent. Skills instruct the host in prose — `skills/forge-2-tech/SKILL.md:36`
("Spawn the `forge-researcher` subagent via the Agent tool"), `skills/forge-verify/SKILL.md:31`
(`subagent_type="forge-verifier"`). The host resolves *name → agent file → model*.

A configured model must therefore reach one of exactly three places:

1. the generated agent file's frontmatter,
2. the host's own settings (outside forge's control), or
3. the dispatch prose the orchestrating model reads.

---

## 2. Viability by host

### 2.1 The question has already been decided once, against — for Pi

`plans/pi-subagent-first-class.md` **decision D1 (2026-07-23)**: drop the `model` pin for Pi,
because "`opus`/`sonnet` are Claude aliases, not Pi model ids, and pinning fights whichever provider
the user is running." The accepted cost was documented, not eliminated; the mitigation is
`docs/agents/pi.md:93-96` — set `subagents.agentOverrides.<name>.model` in *Pi settings*, not in
forge config. The drop reason is emitted programmatically (`scripts/build-adapters.py:1310-1316`).

### 2.2 Claude Code — cross-vendor is impossible; cross-family is free

The `Agent` tool's `model` parameter is an enum: `sonnet | opus | haiku | fable`. Anthropic-only.
There is no vendor axis to configure.

What *is* achievable is cross-**family within Anthropic** (e.g. an Opus supervisor, a Fable
verifier). That decorrelates some failure modes but is not "a different vendor checks the
supervisor." Adjacent in-repo evidence that family choice measurably changes behaviour:
`docs/claude-5/phase-0-compliance-baseline.md` found Opus 5 enforces stage-exit guards *more*
faithfully than the reference model.

Cost to experiment here is ~zero: the dispatch-time `model` override already exists on the tool.

### 2.3 Pi — genuinely cross-vendor, and already richer than forge would build

`pi-subagents` supports, per its `docs/models.md`:

- `subagents.defaultModel`, `subagents.defaultProvider`
- `subagents.agentOverrides.<name>.model` — accepts fully-qualified `provider/model`
  (`anthropic/claude-sonnet-4`, `openrouter/openai/gpt-5-mini`)
- `subagents.agentOverridesByProvider.<provider>.<name>` — layer role fields by the *active parent
  provider*. This is precisely "verify with a family other than the supervisor's", expressed
  declaratively.
- `fallbackModels`, per-role `thinking`, and per-run `reviewer[model=anthropic/claude-sonnet-4:high]`
- **external-CLI runner agents** — shipped `codex-exec`, `claude-code`, `cursor-agent` agents with
  `runner: { type: external-cli, adapter: codex-exec, command: codex }`, i.e. a subagent that *is*
  another vendor's CLI.

Resolution order (strongest first): per-run override → **agent frontmatter `model`** →
provider-scoped role override → `agentOverrides.<name>.model` → `subagents.defaultModel` → parent
session model.

> **Trap.** Agent-frontmatter `model` *outranks* `agentOverrides`. If forge started emitting `model`
> into Pi agent files, it would silently override the user's own settings — exactly the
> "pinning fights whichever provider the user is running" failure D1 avoided. Any future emission
> must be opt-in and written only when the user has explicitly configured it.

### 2.4 codex / gemini / copilot / cursor — nothing to configure

No subagent construct exists to carry a model. Cross-model verification on these hosts would need a
different mechanism entirely (the verify step shelling out to a foreign CLI), which is a much larger
design than a config key.

---

## 3. The precedent to copy: `loopRunner` agent selection

Forge already solved a structurally identical problem one layer down — choosing the *coding agent*
for the autonomous loop. See `references/forge-config-schema.json` → `loopRunner`:
`agentArgument`, `defaultAgent`, `agentMode`, `agentsProbeCommand`; the algorithm is captured
executably in `references/loop-agent-selection.py` and presented in `skills/forge-5-loop/SKILL.md`
Step 2d.

Three properties of that design are what make a subagent-model surface tractable:

1. **Presence-gated capability.** `agentArgument` present ⇒ the runner has an agent surface; absent
   or empty ⇒ behaviour is *byte-identical* to before (REQ-PLUG-02 / REQ-COMPAT-01). This is how a
   new key can be added without disturbing the four hosts that cannot use it.
2. **Probe, then validate.** `agentsProbeCommand` yields an advertised set which doubles as the
   only allow-list for interpolation (REQ-SEC-01); an UNKNOWN id hard-rejects *before any loop
   side-effect*, with no proceed-anyway.
3. **The alias-leak guard already exists, and was earned.** `skills/forge-5-loop/SKILL.md:182`
   (step **d-model**) exists because forwarding a Claude alias to a non-Claude agent makes every
   spawn exit 1 and rauf circuit-break ("3 consecutive infra failures — halting") with no hint of
   the cause. A naive subagent-model config reproduces that bug in a new place.

**Gap worth noting:** `loopRunner` has `agentArgument`/`defaultAgent` but **no `modelArgument` or
`defaultModel`**. Loop-level model choice comes from `item.model` in `backlog.json` plus rauf's own
precedence. Forge has *no* model-configuration surface anywhere today; a subagent one would be the
first.

---

## 4. Cost and risk

| Vector | Detail |
|---|---|
| **Spec purity** | `scripts/check-spec-purity.py` enforces canon vendor-neutrality, and `references/vendor-construct-inventory.md` is the exhaustive audit under a closed `Disposition` vocabulary. Concrete model ids are a new vendor-construct class needing a disposition. `forge.config.json` is the natural home (user-owned, not canon), but the skill prose that *reads* it must stay neutral. |
| **Golden fixtures** | `tests/fixtures/minimal-canon/expected-adapters/` covers all six targets. Any frontmatter emission change means regenerating goldens — a repeat gotcha in this repo. |
| **Executable-spec cost** | `references/loop-agent-selection.py` exists so the agent-selection algorithm cannot drift from skill prose. A subagent-model resolver of comparable complexity warrants the same treatment, putting this at roughly the size of the existing agent-selection feature — not a small config addition. |
| **Unmeasured premise** | Nothing in-repo has measured cross-family verification *yield*. `eval/` (`run-eval.py`, `run-compliance-eval.py`, `fixtures/`) is the natural place to test it. |

---

## 5. Assessment

Viable, but the value is concentrated in a single host.

- **Cheap and available now** — cross-*family* Anthropic verification on Claude Code, via the
  dispatch-time `model` override. No schema change is required to experiment.
- **Genuinely cross-vendor** — Pi only, and the capability already exists in `pi-subagents`
  settings in a richer form than forge would build. The forge-side work is arguably documentation
  and a config passthrough, not a new mechanism.
- **Not addressable** — codex, gemini, copilot, cursor. No subagent construct to configure.

**Recommendation: measure before building.** A config surface carrying the full
probe / validate / alias-guard treatment is a feature-sized investment, justified only if
cross-family verification demonstrably finds defects that same-family verification misses. The cheap
experiment is to run the existing `forge-verify` checklists over identical artifacts under two model
families and compare the findings sets.

## Open questions

- Does a cross-family verifier find *different* findings, or merely *fewer/more* of the same? Only
  the former justifies the mechanism.
- If the answer is Pi-only, is the right deliverable a `forge.config.json` key at all — or an
  expanded `docs/agents/pi.md` section plus a recommended `agentOverridesByProvider` recipe?
- Does the `forge-spec-writer` fan-out benefit from family diversity too, or is that value specific
  to verification?
