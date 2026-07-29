# Claude 5 Skill Library Review Playbook

**Audience:** an agent tasked with reviewing and refining an existing library of Agent Skills, `CLAUDE.md` files, and system prompts for Claude Opus 5 and Claude Fable 5.

**Status of this document:** operating instructions. Part 2 is a procedure to execute in order, not advice to consider. Parts 1, 3 and 4 are reference material to consult during that procedure.

**Sources:** Anthropic documentation and engineering blog, as of July 2026. Prompt snippets are *adapted restatements*, not verbatim copies — see linked pages for official wording. Full source list at the end.

---

## Part 0 — Operating instructions for the reviewing agent

### 0.1 Your role

You are auditing and refactoring a skill library. You are **not** authoring new capability. Your deliverables are: a per-skill findings record, a set of proposed edits, and a library-level report. You do not merge changes without human review.

### 0.2 The prescriptiveness paradox — read this first

This document is highly prescriptive about *the review procedure*. The skills you produce must be *less* prescriptive than the ones you started with. These are not in tension: Anthropic's own degrees-of-freedom framework says a fragile, consistency-critical, must-run-in-sequence operation warrants exact instructions ("narrow bridge"), while open-ended work where many paths succeed warrants general direction ("open field"). A library-wide audit is a narrow bridge. The skills themselves are usually open fields.

Do not carry this document's density into the artifacts you write.

### 0.3 Non-negotiables

1. **Delete before you rewrite.** When a legacy instruction duplicates a native Claude 5 behavior, remove it. Do not soften it, do not qualify it, do not add a condition. Softening preserves the compounding problem at lower volume.
2. **Never branch on model self-identity.** Do not write "if you are Opus 5, do X." See §3.4 for why.
3. **Every edit must be attributable** to a rule in Part 3 or to observed eval evidence. If you cannot name the rule, do not make the edit.
4. **Preserve domain knowledge unconditionally.** Schemas, API references, business rules, validated commands, and gotchas are model-invariant. You are removing *behavioral scaffolding*, never institutional knowledge.
5. **Do not delete a skill because it looks redundant.** Redundancy is an eval question (§2.5), not a reading-comprehension question.
6. **Report uncertainty rather than resolving it silently.** Flag and continue.

### 0.4 Scope confirmation before you begin

Confirm with the human: which skill directories are in scope; which models the library must support; whether any skills are enterprise-managed or plugin-sourced (you may not be able to edit those); and whether an eval harness exists. Do not start editing until these are answered.

---

## Part 1 — Why skills break on Claude 5

### 1.1 The three failure mechanics

| Mechanic | What happens | Signature in the wild |
|---|---|---|
| **Compounding** | The model already performs the behavior; your instruction stacks on top | Doubled verification passes, runaway subagent spawning, bloated narration, cost up with no quality gain |
| **Conflict** | System prompt, `CLAUDE.md`, skill, and user turn disagree | Unstable behavior across runs; model "ignores" the skill; reasoning spent on arbitration |
| **Literalism** | Sharper instruction following takes hedges at face value | Skill under-delivers; review skills report less; "be conservative" honored exactly |

Anthropic removed **over 80% of Claude Code's system prompt** for Opus 5 / Fable 5 with no measurable loss on coding evals. The reference example: guidance to write no comments and never produce multi-line comment blocks was replaced with a single instruction to match the surrounding code's comment density, naming, and idiom.

### 1.2 The six documented shifts

| Then | Now |
|---|---|
| Give Claude rules | Let Claude use judgement |
| Give Claude examples for tool use | Design better tool interfaces; examples now constrain exploration |
| Put it all upfront | Progressive disclosure |
| Repeat yourself across layers | One instruction, in the tool description |
| Memory in `CLAUDE.md` | Auto-memory |
| Simple markdown specs | Rich references — HTML artifacts, test suites, real source, rubrics |

### 1.3 Claude Opus 5 — behavioral deltas

Thinking is **on by default**; it can be disabled only at effort `high` or below (`xhigh`/`max` + disabled returns 400).

| Behavior | Consequence for skills | Required action |
|---|---|---|
| Self-verifies natively | Legacy verification instructions compound | **Delete** all "verify / double-check / re-verify / use a subagent to verify" |
| Expands task scope | Skill delivers more than asked | Add a scope-discipline block (§3.2) to narrow skills |
| Longer default responses | Effort does **not** reliably shorten visible output | Prompt explicitly for concision |
| Longer written deliverables | Files on disk are padded | Add length calibration to document-producing skills |
| Narrates readily | Verbose agentic sessions | Describe desired cadence; positive examples beat prohibitions |
| Narrates its own corrections | Noisy user-facing output | Scope corrections to those that change the user's decisions |
| Delegates readily | Cost/latency multiplication on small tasks | Give delegation criteria or a hard cap |
| Literal on hedges | Review skills under-report | Report everything, filter in a second pass |
| Code review precision holds at low effort | Fast pass / thorough pass is viable | Re-run an effort sweep; use `low`/`medium` liberally |

**Thinking-disabled artifacts.** If any skill or harness disables thinking: tool calls can be emitted as plain text (never executed, and the leaked text persists in agentic history), and internal XML tags can leak into visible output. A system-prompt rule telling the model not to think *increases* leakage — remove it. Preferred mitigation is thinking enabled at low effort rather than thinking disabled.

### 1.4 Claude Fable 5 — behavioral deltas

Always thinking, adaptive only. No `budget_tokens`. Assistant prefill returns 400. Raw chain of thought never returned.

| Behavior | Consequence for skills | Required action |
|---|---|---|
| **Prior-model skills are often too prescriptive and can degrade output** | This is the explicit, documented warning | Treat every pre-Claude-5 skill as suspect |
| `reasoning_extraction` refusal category | Skills instructing the model to echo/transcribe/explain internal reasoning trigger refusals and elevated fallback to Opus 4.8 | **Audit and remove all show-your-thinking instructions** |
| Very long turns | Minutes per request, hours per run | Harness concern: timeouts, streaming, async check-ins |
| Tidies/refactors at high effort | Unrequested scope creep | Add a minimalism block |
| Strong instruction following | One short instruction replaces an enumerated list | Collapse enumerations |
| Occasional fabricated progress claims | Status reports not grounded in tool results | Add a progress-grounding instruction |
| Occasional unrequested actions | Drafts emails, creates defensive branches | State boundaries: assessment-only until asked |
| Occasional early stop / permission-asking | Turn ends on a statement of intent | Add an autonomous-operation reminder |
| Context-budget anxiety | Suggests new session, trims own work | **Stop surfacing remaining-token countdowns to the model** |
| Performs better knowing *why* | — | Include intent, not just the request |
| Rewards a memory system | — | Provide a notes directory with a one-lesson-per-file convention |

Fable 5 also runs safety classifiers over offensive-cyber and bio/life-sciences content; benign work in those areas can trigger them. Configure fallback rather than prompt around it.

### 1.5 Long-horizon failure modes (relevant to workflow-shaped skills)

Anthropic names three failure modes that emerge when planning and execution share one context window: **agentic laziness** (declaring a multi-part task done after partial progress), **self-preferential bias** (favoring its own outputs when verifying them), and **goal drift** (fidelity to the original objective fraying over many turns, especially after compaction).

Consequence for your review: **self-critique instructions are structurally weak.** Where a skill needs verification, prefer a fresh-context verifier subagent over an instruction to check its own work. The Fable 5 guidance says the same — separate, fresh-context verifiers tend to outperform self-critique.

---

## Part 2 — The review procedure

Execute phases in order. Do not skip Phase 0 or Phase 1.

### Phase 0 — Inventory and instrumentation

**0.1** Enumerate every skill. For each, record: path, scope level (enterprise / personal / project / plugin / nested), `SKILL.md` line count, total directory size, file count, frontmatter fields present, and `description` character count.

**0.2** Run `/doctor`. Record the skill-listing context cost and its largest contributors. Run with `--debug` and capture any listing-overflow warning. Record the Skills row from `/context`.

**0.3** Compute listing pressure: the description listing budget scales at **1% of the model's context window**, and each entry's combined `description` + `when_to_use` is capped at **1,536 characters**. When the listing overflows, Claude Code drops descriptions **starting with the least-invoked skills**. Flag the library as *listing-pressured* if `/doctor` reports overflow.

**0.4** Establish version control state. Every subsequent phase produces reviewable diffs.

**Gate:** do not proceed until you can name every skill and know whether the library is listing-pressured.

### Phase 1 — Triage by skill type

Classify every skill into exactly one bucket. This determines what happens to it.

| Type | Definition | Durability | Review posture |
|---|---|---|---|
| **Capability uplift** | Helps Claude do something the base model can't do, or can't do consistently (e.g. document-format manipulation) | **May be obsoleted by model improvement** | Test with and without. If baseline passes without it, the skill is a retirement candidate, not a broken skill |
| **Encoded preference** | Every step is within base-model ability; the skill sequences them to *your* process (e.g. NDA review against set criteria, weekly update assembly) | **Durable** | Keep. Strip behavioral scaffolding. Verify fidelity to the actual workflow |
| **Reference/knowledge** | Schemas, API docs, domain facts, gotchas | **Durable, model-invariant** | Preserve. May need relocation into `references/` |
| **Deterministic procedure** | Exact command sequences, migrations, fragile operations | **Durable** | Preserve low degrees of freedom. Do **not** loosen |

Record the classification in the findings record. **Misclassifying an encoded-preference skill as capability uplift and retiring it destroys institutional knowledge — when uncertain, classify as encoded preference and flag.**

**Gate:** every skill classified before any edit.

### Phase 2 — Static audit

For each skill, run the following checks. Each produces a verdict: `PASS`, `EDIT`, `SPLIT`, `FLAG`, or `RETIRE-CANDIDATE`.

#### 2.1 Mechanical checks

| # | Check | Fail condition | Verdict |
|---|---|---|---|
| M1 | `SKILL.md` body length | > 500 lines | `SPLIT` |
| M2 | Reference depth | Any reference reachable only via another reference | `EDIT` — flatten to one level from `SKILL.md` |
| M3 | Reference file TOC | Reference file > 100 lines with no table of contents | `EDIT` |
| M4 | Path separators | Any backslash path | `EDIT` |
| M5 | Description specificity | Vague ("helps with documents"), missing *when to use*, or first person | `EDIT` |
| M6 | Description length | Combined `description` + `when_to_use` > 1,536 chars | `EDIT` — key use case first |
| M7 | Frontmatter validity | Malformed YAML | `FLAG` — body loads with empty metadata, so `/name` works but auto-trigger silently fails |
| M8 | MCP tool references | Unqualified tool name | `EDIT` — use `ServerName:tool_name` |
| M9 | Time-sensitive content | Dates, "before/after X" conditionals | `EDIT` — move to a collapsed "old patterns" section |
| M10 | Terminology drift | Same concept, multiple names | `EDIT` |
| M11 | Dependency assumptions | Package used without being declared available | `EDIT` |
| M12 | Voodoo constants | Unjustified numeric literals in bundled scripts | `EDIT` |
| M13 | Option menus | Multiple approaches offered without a default | `EDIT` — one default plus a named escape hatch |
| M14 | Execution intent | Ambiguous whether a script is run or read | `EDIT` |

#### 2.2 Behavioral-scaffolding scan

Grep the library. Every hit requires a verdict; most require deletion.

```bash
# Over-verification (Opus 5 compounds these)
grep -rniE "double.?check|re-?verify|verification step|verify (your|the) work|use a subagent to verify|sanity.?check" .

# Escalation language (now overtriggers)
grep -rniE "CRITICAL:|IMPORTANT:|you MUST|ALWAYS |NEVER |if in doubt|default to using" .

# Reasoning extraction (Fable 5 refusal risk)
grep -rniE "show your (reasoning|thinking|work)|explain your (reasoning|thought)|chain of thought|think out loud|transcribe your|walk through your reasoning" .

# Anti-thinking rules (increase XML leakage on Opus 5)
grep -rniE "do not think|don't reason|without thinking|skip reasoning" .

# Hedges taken literally
grep -rniE "be conservative|only report (high|critical)|err on the side of|when in doubt, (skip|omit)" .

# Prohibition stacks (candidates for positive restatement)
grep -rniE "do not (add|create|write|include)|never (add|create|write)|avoid (adding|creating)" .

# Context-budget surfacing (triggers Fable 5 wrap-up behavior)
grep -rniE "tokens remaining|context (left|remaining)|budget remaining|running low on context" .
```

Apply the deletion catalog in §3.1 to each hit.

#### 2.3 Conflict detection

Build a matrix of directives across layers: system prompt × `CLAUDE.md` × each skill. Flag any pair of directives that could both apply to one request and imply different actions. Documentation density, comment policy, file creation, verification, and narration are the highest-yield axes. Every conflict is a `FLAG` requiring human adjudication — you may not unilaterally decide which layer wins.

#### 2.4 Knowledge/behavior seam

For each skill, tag every section as **knowledge** (model-invariant: schemas, rules, references, commands) or **behavior** (model-dependent: verification, narration, scope, examples, tone). Record the ratio. A skill that is >60% behavior is a prime refactor target. This tagging drives Phase 3 and Phase 4.

#### 2.5 Obsolescence probe (capability-uplift skills only)

For each capability-uplift skill, construct three realistic prompts and run each **in a fresh session** with the skill available and again with it disabled via `skillOverrides`. A fresh session is mandatory — leftover authoring context masks gaps in the written instructions.

If the no-skill baseline passes your assertions, mark `RETIRE-CANDIDATE`. The skill is not broken; the model absorbed its technique.

**Gate:** no edits proposed until every skill has a verdict on M1–M14, the scaffolding scan, and the knowledge/behavior tag.

### Phase 3 — Restructure

#### 3.1 Apply the deletion catalog

Work through §3.1's table. Delete first; rewrite only where the instruction encodes knowledge the model cannot infer.

#### 3.2 Split knowledge from behavior

Target layout:

```
skill-name/
├── SKILL.md              # Navigation + behavior. Lean. The variant surface.
├── references/
│   ├── schema.md         # Knowledge. Model-invariant. Shared.
│   ├── domain-rules.md   # Knowledge. Model-invariant. Shared.
│   └── gotchas.md        # Knowledge. Model-invariant. Shared.
├── scripts/
│   └── validate.py       # Deterministic. Executed, never loaded.
├── assets/
│   └── template.md
└── evals/
    └── evals.json        # Test cases; see Phase 5.
```

Rules:
- `SKILL.md` is a table of contents plus the minimum behavioral guidance. Under 500 lines; under ~5,000 tokens is the standard's recommendation.
- Every reference file links **directly from `SKILL.md`**. One level. No chains.
- Knowledge files are never duplicated across skill variants — they are shared.
- Scripts are preferred over generated code for deterministic operations; their source never enters context.

#### 3.3 Convert prohibitions to target-state descriptions

For each prohibition stack, write the positive form. The canonical transformation is the comment-policy example in §1.1: a list of bans became one instruction describing what correct output looks like in context. Apply the same move to file creation, documentation, formatting, and tone rules.

#### 3.4 Do not add model-conditional branches

Prohibited construction:

```markdown
<!-- DO NOT DO THIS -->
If you are Claude Opus 5 or later, skip the verification section below.
Otherwise, follow it.
```

Three reasons, in order of severity:

1. **Model self-identification is unreliable.** Anthropic's prompting guide contains a "model self-knowledge" section whose entire premise is that you must *tell* Claude which model it is in the system prompt if you want it to identify correctly. Branching on self-report branches on something the model may get wrong.
2. **A conditional block is the conflict mechanic** from §1.1 in its purest form.
3. **Both branches cost tokens on every activation**, and once a skill loads, its content stays in context for the rest of the session.

Use the mechanisms in §3.3 (multi-model reference) instead.

#### 3.5 Prefer verifier subagents over self-critique

Where a skill needs a quality gate, replace self-check instructions with either a deterministic validator script (best — machine-verifiable, objective) or a fresh-context verifier subagent with an explicit rubric. Self-preferential bias makes a model a weak judge of its own output.

Where the operation is batch, destructive, or high-stakes, use the plan-validate-execute pattern: produce a structured plan file, validate it with a script, then execute. Validation scripts should name the specific problem and list valid alternatives, not just fail.

### Phase 4 — Multi-model handling

Only if the library must serve both legacy and Claude 5 models. See §3.3 for the mechanism table and §3.4 for the prohibition.

**4.1** Determine per skill whether the legacy/current delta is *knowledge-shaped* (no action — knowledge is invariant) or *behavior-shaped* (requires a strategy below).

**4.2** Choose the lowest-cost strategy that works:

| Order | Strategy | Use when |
|---|---|---|
| 1 | **No fork.** Write to the Claude 5 shape and accept slightly weaker legacy behavior | The delta is small, or legacy traffic is a shrinking minority |
| 2 | **Fork the body, share the references.** Two `SKILL.md` files, one `references/` directory | The delta is behavior-shaped and material |
| 3 | **Pin with `model:` frontmatter** | A skill only works well on one model and switching is acceptable |
| 4 | **Adapt on effort via `${CLAUDE_EFFORT}`** | Capability tier, not identity, is the real variable |
| 5 | **Render externally via `` !`command` ``** | The harness knows the target and can emit the right block as preprocessing |
| 6 | **Select at the API call site** | You control the harness; cleanest separation |

**4.3** If you fork, mitigate the listing-budget tax: set the legacy variant to `"name-only"` in `skillOverrides`, or `disable-model-invocation: true` so it loads only on explicit invocation and consumes no listing context.

**4.4** Tag every fork for retirement. Use the open standard's `metadata` block:

```yaml
metadata:
  tuned-for: "claude-opus-5"
  supersedes: "invoice-review-legacy"
  review-by: "2026-10-01"
```

Neither `metadata` nor `compatibility` is machine-enforced — `compatibility` is free text describing environment requirements and is marked experimental with varying cross-implementation support. These are documentation for humans and for your own tooling.

**4.5** Record a retirement condition for each fork: the eval result that would justify deleting the legacy variant. A permanent two-branch library is a compounding maintenance liability.

### Phase 5 — Evaluate

**5.1** Install the tooling if absent:

```
/plugin install skill-creator@claude-plugins-official
/reload-plugins
```

If the marketplace is missing: `/plugin marketplace add anthropics/claude-plugins-official`. If the plugin is missing from it: `/plugin marketplace update claude-plugins-official`.

**5.2** Write at least **three** eval cases per skill before finalizing edits. Each case pairs a realistic prompt (plus input files where needed) with specific, verifiable assertions. Store in `evals/evals.json` inside the skill directory.

**5.3** Run the modes in this order:

| Mode | Question it answers |
|---|---|
| **Eval** | Does the skill produce correct output on realistic prompts? |
| **Benchmark** | What are pass rate, elapsed time, and token usage — with and without the skill? |
| **Comparator (blind A/B)** | Is the edited version actually better than the original? |
| **Description tuning** | Does it trigger on the prompts it should and stay quiet on the ones it shouldn't? |

Each eval case runs in its own subagent with a clean context and its own token/timing metrics, so runs do not contaminate each other. The comparator judges outputs without knowing which version produced them.

**5.4** Acceptance thresholds. An edit ships only if **all** hold:
- Pass rate ≥ baseline.
- Token usage ≤ baseline (this is the point of the exercise; an edit that improves quality at higher cost is a `FLAG`, not an automatic pass).
- Blind A/B favors the new version or is neutral.
- Trigger hit rate is unchanged or improved.

**5.5** For `RETIRE-CANDIDATE` skills, the decision rule is: retire if the no-skill baseline meets assertions across all eval cases. Otherwise reclassify and keep.

**5.6** Note the description-tuning precedent: Anthropic ran it across its public document-creation skills and saw improved triggering on 5 of 6. Expect description edits to be among your highest-yield changes.

### Phase 6 — Report and hand off

Produce the artifacts in Part 4. Do not merge. Present diffs grouped by rule, so a reviewer can accept or reject an entire class of change at once.

---

## Part 3 — Reference tables

### 3.1 Deletion catalog

| Pattern found | Verdict | Replacement |
|---|---|---|
| "Always verify / double-check / re-verify" | **Delete** | None. Opus 5 verifies natively |
| "Use a subagent to verify your work" | **Delete** | None; add delegation criteria elsewhere |
| "Include a final verification step" | **Delete** | Deterministic validator script if a gate is genuinely needed |
| "CRITICAL: You MUST use this tool when…" | **Downgrade** | "Use this tool when…" |
| "If in doubt, use [tool]" / "Default to [tool]" | **Replace** | "Use [tool] when it would improve your understanding of X" |
| "Show your reasoning in the response" | **Delete** | Read structured `thinking` blocks; use a send-to-user tool for progress |
| "Do not think / do not reason" | **Delete** | None — the instruction increases tag leakage |
| Long few-shot blocks for tool usage | **Replace** | Better tool interface: expressive enums, self-describing params |
| Enumerated prohibition lists | **Collapse** | One positive instruction describing target output |
| "Do not add comments" / rigid format bans | **Replace** | Match the surrounding code's density, naming, and idiom |
| "Be conservative" / "only report high-severity" | **Delete** | Report everything; filter in a separate pass |
| Everything-in-one-file body | **Split** | Navigation + one-level references |
| Duplicate instruction in system prompt *and* tool description | **Delete one** | Keep the tool description |
| Self-critique gate | **Replace** | Fresh-context verifier subagent or validator script |
| Remaining-token countdown surfaced to model | **Delete** | Suppress; add reassurance if unavoidable |
| Model-conditional branch | **Delete** | See §3.3 |

### 3.2 Instruction blocks to add (adapted; see source pages for official wording)

Add only where the audit showed the corresponding symptom. Do not add prophylactically.

| Symptom | Block to add |
|---|---|
| Scope creep (Opus 5) | Deliver what was asked at the scope intended. Make routine judgement calls yourself; check in only when different readings would lead to materially different work. If the request seems mistaken, say so in one sentence and proceed as asked rather than quietly transforming it. Finish the whole task and stop short of anything clearly beyond it. |
| Verbose responses (Opus 5) | Keep responses focused, brief, and concise. Keep caveats short and spend most of the response on the main answer. When explaining, give a high-level summary unless depth was requested. |
| Padded deliverables (Opus 5) | Match document length to what the task needs. Cover the substance; do not pad with filler sections, redundant summaries, or boilerplate. |
| Excess narration (Opus 5) | One sentence before the first tool call. Brief updates only on important findings or direction changes. Lead the finish with the outcome. |
| Correction noise (Opus 5) | Correct an earlier statement only when the error would change the user's code, conclusions, or decisions. Otherwise fix silently and continue. |
| Over-delegation (Opus 5) | Delegate only for large, genuinely independent, parallelizable work. Do not delegate what you could finish in a handful of tool calls. Do not use subagents to check your own work. |
| Unrequested tidying (Fable 5) | No features, refactors, or abstractions beyond what the task requires. No design for hypothetical future needs. No error handling for scenarios that cannot occur. Validate only at system boundaries. |
| Fabricated progress (Fable 5) | Before reporting progress, check each claim against a tool result from this session. Report only work you can point to evidence for; state explicitly what is unverified. |
| Unrequested action (Fable 5) | When the user is describing a problem or thinking out loud rather than requesting a change, the deliverable is your assessment. Report and stop. |
| Early stopping (Fable 5, autonomous) | You are operating autonomously; the user cannot answer mid-task. Proceed on reversible actions that follow from the original request. Before ending a turn, check whether your last paragraph is a plan, question, or promise — if so, do that work now. |
| Context anxiety (Fable 5) | Ample context remains. Do not stop, summarize, or suggest a new session on account of context limits. |

### 3.3 Multi-model mechanism reference

| Mechanism | Where | Behavior | Caveat |
|---|---|---|---|
| `model:` | Skill frontmatter | Sets the model for the rest of the current turn; not saved to settings; session model resumes next prompt. Accepts `/model` values or `inherit` | **Silently ignored** if outside the org's `availableModels` allowlist — the session keeps its current model |
| `effort:` | Skill frontmatter | Overrides session effort while active. `low`/`medium`/`high`/`xhigh`/`max`, availability varies by model | Effort ≠ visible response length on Opus 5 |
| `${CLAUDE_EFFORT}` | Skill body | Substitutes the active effort level; documented for adapting instructions to it | A capability-tier proxy, not model identity |
| `` !`command` `` | Skill body | Shell output replaces the placeholder **before** Claude sees the content | Pure preprocessing — no model awareness. Substitution runs once; output is not re-scanned |
| `paths:` | Skill frontmatter | Globs limiting auto-activation | Reduces false triggers; does not vary content |
| `context: fork` + `agent:` | Skill frontmatter | Runs in an isolated subagent; skill content becomes the prompt | **Only for skills with an actionable task.** A conventions-only skill forked to a subagent returns nothing useful |
| `metadata:` / `compatibility:` | Frontmatter (open standard) | Free-form documentation | Not machine-enforced; `compatibility` is experimental with varying support |
| Per-model bundle selection | API call site | Attach different skills per model | Cleanest; requires harness control |

### 3.4 Harness mechanics that produce flaky skills

Check these before concluding a skill's *wording* is at fault.

| Mechanic | Effect | Diagnostic | Mitigation |
|---|---|---|---|
| **Listing budget** | Descriptions truncated or dropped, starting with least-invoked skills; budget = 1% of context window; per-entry cap 1,536 chars | `/doctor`, `/context` Skills row, `--debug` | Key use case first; `"name-only"` for low-priority; raise `skillListingBudgetFraction` or `skillListingMaxDescChars` |
| **Content lifecycle** | Invoked content enters context once and persists; the file is **not re-read** on later turns | Behavior degrades over a session | Write standing instructions, not one-time steps |
| **Compaction carry-forward** | Re-attached after summary at **first 5,000 tokens each**, sharing a **25,000-token** pool, filled most-recent-first; older skills can be dropped entirely | "Worked at first, then stopped" | Re-invoke after compaction; reduce skill count per session |
| **Permission grant scope** | `allowed-tools` applies only to the invoking turn; clears on the next user message | Unexpected permission prompts | Use session-level permission rules for persistent grants |
| **Name resolution** | Enterprise > personal > project; any level overrides a bundled skill of the same name; nested variants get directory-qualified names | Wrong variant runs | Audit for name collisions across levels |
| **Malformed YAML** | Body loads with empty metadata: `/name` works, auto-trigger silently does not | `--debug` shows the parse error | Validate frontmatter |
| **Cowork / cloud sessions** | Do not read `~/.claude/skills/` | "Skill not found" in routines | Enable for the account, or commit to the repo's `.claude/skills/` |
| **Background fork tool set** | Backgrounded `context: fork` skills run with the narrower background-subagent tool set; their edits fall outside checkpoints, so `/rewind` won't undo them | Missing tools; unrevertable edits | `background: false` where the full tool set is needed |

### 3.5 Layer allocation

| Layer | Contains | Does not contain |
|---|---|---|
| **System prompt** | Product context: what the agent is, what it's doing | Task procedures |
| **`CLAUDE.md`** | Brief repo purpose; **gotchas** (e.g. types live in one monolithic file) | Anything discoverable from the filesystem; multi-step procedures |
| **Skills** | Your team's opinions, workflows, domain knowledge | Generic best practice the model already has |
| **References** | Specs, mockups, test suites, real source code, rubrics | Prose descriptions of things better shown as code |

Prefer code as reference. An HTML mockup outperforms a design description or a screenshot; a test suite is a spec; a function in another codebase is a portable specification.

---

## Part 4 — Required output artifacts

### 4.1 Per-skill findings record

One record per skill, machine-readable:

```json
{
  "skill": "invoice-review",
  "path": ".claude/skills/invoice-review/SKILL.md",
  "scope": "project",
  "classification": "encoded-preference",
  "body_lines": 612,
  "knowledge_behavior_ratio": "35/65",
  "listing_chars": 388,
  "findings": [
    {"rule": "M1", "severity": "high", "detail": "body exceeds 500 lines", "action": "SPLIT"},
    {"rule": "D-verify", "severity": "high", "detail": "3 verification instructions", "action": "DELETE"},
    {"rule": "M2", "severity": "medium", "detail": "reference chain 2 deep", "action": "EDIT"}
  ],
  "eval_cases": 3,
  "baseline_pass_without_skill": false,
  "verdict": "EDIT+SPLIT",
  "open_questions": ["Conflicts with CLAUDE.md line 44 on comment policy — needs adjudication"]
}
```

### 4.2 Library-level report

Must contain, in this order:

1. **Executive summary** — skill count, total listing cost, number by verdict, headline token reduction achieved.
2. **Retirement candidates** — capability-uplift skills whose no-skill baseline passed, with evidence.
3. **Conflicts requiring human adjudication** — the Phase 2.3 matrix, unresolved.
4. **Changes by rule class** — grouped so a reviewer can accept/reject a whole class.
5. **Benchmark deltas** — pass rate, time, tokens: before vs. after, per skill.
6. **Multi-model forks created**, with retirement conditions.
7. **Deferred items** — anything you flagged rather than fixed, and why.

### 4.3 Change control

- One commit per rule class, not per skill. A reviewer should be able to revert "all verification-instruction deletions" atomically.
- Never mix a structural split with a content edit in the same commit.
- Include the before/after benchmark numbers in the commit body.

---

## Part 5 — Stop conditions

Stop and escalate to the human when any of these occur:

1. A conflict between layers whose resolution changes user-visible behavior.
2. A skill classified `RETIRE-CANDIDATE` that is enterprise-managed or referenced by another skill.
3. An edit that improves quality but increases token cost.
4. Any skill you cannot classify with confidence in Phase 1.
5. Frontmatter you cannot edit (plugin- or enterprise-sourced).
6. Eval results that contradict a rule in this document. **The evidence wins; report the discrepancy.**
7. More than 30% of the library flagged — that indicates a systemic authoring convention worth fixing at the template level rather than skill by skill.

---

## Sources

**Anthropic — primary:**
- [The new rules of context engineering for Claude 5 generation models](https://claude.com/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models) (Jul 24, 2026)
- [Prompting Claude Opus 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5)
- [Prompting Claude Fable 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5)
- [Prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- [Extend Claude with skills (Claude Code)](https://code.claude.com/docs/en/skills)
- [Improving skill-creator: test, measure, and refine Agent Skills](https://claude.com/blog/improving-skill-creator-test-measure-and-refine-agent-skills) (Mar 3, 2026) — capability-uplift vs. encoded-preference taxonomy
- [A harness for every task: dynamic workflows in Claude Code](https://claude.com/blog/a-harness-for-every-task-dynamic-workflows-in-claude-code) (Jun 2, 2026) — agentic laziness, self-preferential bias, goal drift
- [A field guide to Claude Fable 5: finding your unknowns](https://claude.com/blog/a-field-guide-to-claude-fable-finding-your-unknowns)
- [Building verification loops in Claude Code with skills](https://claude.com/blog/building-verification-loops-in-claude-code-with-skills)
- [Effort](https://platform.claude.com/docs/en/build-with-claude/effort) · [Migration guide](https://platform.claude.com/docs/en/about-claude/models/migration-guide) · [What's new in Opus 5](https://platform.claude.com/docs/en/about-claude/models/whats-new-opus-5)
- [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [anthropics/skills — skill-creator](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md)

**Open standard:**
- [Agent Skills specification](https://agentskills.io/specification) — frontmatter schema, `compatibility` and `metadata` fields, progressive disclosure tiers
- [Evaluating skill output quality](https://agentskills.io/skill-creation/evaluating-skills)

**Community (use with judgement):**
- [Opus 5 review: effort, skills, migration](https://www.ai.joaoqueiros.com/blog/claude-opus-5-review-effort-skills-migration) — independent testing reporting Opus 5 as less dependable inside mature skill-driven workflows built for a predecessor
- [Claude model migration guide](https://hidekazu-konishi.com/entry/anthropic_claude_model_migration_guide.html)
