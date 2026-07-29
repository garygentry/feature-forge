# Tuning Skills and Prompts for Claude 5 Models (Opus 5 / Fable 5)

**Purpose.** Drop this into an agent's context when asking it to audit, rewrite, or debug Skills, `CLAUDE.md` files, or system prompts that were written for Claude 4.x-generation models and now behave unreliably on Claude Opus 5 or Claude Fable 5.

**Scope note.** Prompt snippets below are *adapted* restatements of guidance in Anthropic's docs, not verbatim copies. Follow the linked source pages for official wording. Sources are listed at the end; everything here traces to Anthropic documentation or the Anthropic engineering blog unless marked otherwise.

---

## 1. The core thesis

Claude 5 models are **overconstrained** by context written for earlier models. Anthropic removed **over 80% of Claude Code's system prompt** for Opus 5 / Fable 5 with no measurable loss on their coding evals ([blog, Jul 24 2026](https://claude.com/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models)).

Three failure mechanics explain most "my skill stopped working" reports:

1. **Compounding.** The model already does the behavior natively. Your instruction stacks on top of it → over-verification, over-narration, over-delegation, doubled cost, no quality gain.
2. **Conflict.** System prompt, `CLAUDE.md`, skill, and user turn now disagree ("leave documentation as appropriate" vs. "DO NOT add comments"). The model resolves it, but spends reasoning on arbitration instead of the task, and the resolution is unstable.
3. **Literalism.** Instruction following is sharper. Hedging language you wrote as a soft nudge ("be conservative", "only report high-severity issues") is now obeyed exactly, and the skill under-delivers.

**Default remediation is deletion, not rewriting.** When migrating a skill, remove the legacy instruction rather than softening it.

---

## 2. The six shifts (Anthropic, Jul 2026)

| Then (4.x-era practice) | Now (Claude 5) |
|---|---|
| Give Claude rules | Let Claude use judgement — describe the *goal state*, not the prohibition |
| Give Claude examples for tool use | Design better tool/script **interfaces**; examples now constrain the exploration space |
| Put it all upfront | Progressive disclosure — load context at the moment it's needed |
| Repeat yourself across layers | Put tool instructions in the **tool description**, once |
| Memory lives in `CLAUDE.md` | Auto-memory; Claude writes its own memories |
| Specs are simple markdown | Rich references — HTML artifacts, test suites, real source code, rubrics |

Concrete example of the first shift, from Claude Code's own system prompt:

- **Removed:** default to no comments; never write multi-line comment blocks; don't create planning/analysis documents unless asked.
- **Replaced with:** write code that reads like the surrounding code — match its comment density, naming, and idiom.

That is the pattern to imitate throughout your skill library: replace a prohibition with a description of what "correct" looks like in context.

---

## 3. Claude Opus 5 — behavioral deltas and fixes

Source: [Prompting Claude Opus 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5)

Opus 5 runs **thinking on by default**. Thinking can only be disabled at effort `high` or below; disabling at `xhigh`/`max` returns a 400 error.

### 3.1 Over-verification — the single most common skill regression

Opus 5 verifies its own work without being told to. Legacy instructions compound with that native behavior.

**Delete these patterns from skills and harnesses:**
- "Include a final verification step for any non-trivial task"
- "Use a subagent to verify"
- "Double-check your answer" / "re-verify before responding"
- Separate verification stages in harness scaffolding that exist only because 4.x needed them

Removing them reduces token spend with no quality loss. Do **not** rewrite them more gently — remove them.

### 3.2 Scope expansion

Opus 5 will add steps that weren't requested and apply its own judgement about what the task *should* be. For narrow skills, constrain scope explicitly.

*Adapted snippet:*
> Deliver what was asked at the scope intended. Make routine judgement calls yourself; check in only when different readings of the request would lead to materially different work. If the request looks mistaken or a better approach exists, say so in one sentence and proceed as asked rather than quietly narrowing, widening, or transforming the task. Finish the whole task and stop short of anything clearly beyond it.

### 3.3 Verbosity — effort is the wrong lever

Opus 5's default user-facing responses run longer than prior Opus models. **Lowering `effort` reduces thinking volume, not visible response length.** Prompt for length explicitly.

*Adapted snippet:*
> Keep responses focused, brief, and concise. Keep disclaimers and caveats short and spend most of the response on the main answer. When explaining something, give a high-level summary unless an in-depth explanation was specifically requested.

In a long system prompt, pair this with a short reminder tag near the end (e.g. a `<tone_preference>` block), since position matters less than repetition of intent.

### 3.4 Written deliverable length

Separate axis from conversational verbosity: **files Opus 5 writes to disk** (reports, markdown, summaries) run longer than on prior models. If your skill produces documents, add explicit length calibration — cover the substance, no filler sections, no redundant summaries, no boilerplate.

### 3.5 Narration

Opus 5 announces what it is about to do, and per-message output in agentic sessions is longer. Tune by describing the *cadence and shape* you want, not by prohibiting narration:

*Adapted snippet:*
> Before your first tool call, say in one sentence what you're about to do. While working, give a brief update only when you find something important or change direction. When you finish, lead with the outcome — the first sentence answers "what happened" or "what did you find" — with supporting detail after.

Positive examples of the communication style you want outperform instructions about what not to do.

### 3.6 Correction narration

Opus 5 narrates corrections to its own earlier statements more than prior models — often undesirable in user-facing products. Scope it: only flag an earlier statement when the error would change the user's code, conclusions, or decisions; otherwise fix silently and continue.

### 3.7 Subagent over-delegation

Opus 5 delegates more readily. Delegation pays on genuinely independent, sizeable tracks; it multiplies cost and latency on small ones. Give explicit criteria or set a deterministic cap.

*Adapted snippet:*
> Delegate to a subagent only for large, genuinely independent, parallelizable work such as a wide multi-file investigation. Don't delegate work you could finish in a handful of tool calls, and don't use subagents to verify your own work. If one subagent suffices, use one.

### 3.8 Literal instruction following in review skills

If a code-review skill says "only report high-severity issues" or "be conservative," Opus 5 obeys literally and reports less. **Ask it to report everything and filter in a separate pass.**

### 3.9 Thinking-disabled artifacts

If your integration disables thinking, two artifacts can appear:
- **Tool calls emitted as text** instead of structured `tool_use` blocks. The call never runs; in agentic loops the leaked text persists in history and poisons later turns. Most common on tool-heavy/search workloads.
- **Internal XML tags** (`<thinking>` etc.) leaking into visible output. If your system prompt contains a rule telling the model not to think or not to reason, **remove it** — that instruction *increases* leakage.

Primary mitigation: keep thinking enabled and control cost with lower effort instead. Thinking enabled at `low` effort generally beats thinking disabled at comparable cost. If you must disable thinking, a general instruction (may speak briefly before a tool call; say so if no tool fits; no internal or system XML tags in the response) works better than naming the tags specifically.

### 3.10 Effort

Opus 5 supports all five levels; API default is `high`. Start at `high`; use `low`/`medium` **liberally** as the primary cost/latency control wherever evals hold; step to `xhigh` for demanding agentic coding. Accuracy on code review holds at lower effort, which supports a fast pass now / thorough pass later pattern. **Re-run an effort sweep** — don't carry 4.8-era settings (which recommended explicit `xhigh`) forward.

---

## 4. Claude Fable 5 — behavioral deltas and fixes

Source: [Prompting Claude Fable 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5)

Fable 5 (and Mythos 5) is **always thinking**, adaptive-only. `budget_tokens` is gone; assistant prefill returns 400; raw chain of thought is never returned.

### 4.1 The explicit skill warning

> Skills developed for prior models are often **too prescriptive** for Fable 5 and can degrade output quality.

Anthropic's stated remedy: review and consider removing older instructions where default performance is better. Fable 5 also updates skills on the fly based on what it learns during a task.

### 4.2 `reasoning_extraction` refusals — a silent skill killer

Prompts, skills, or harness instructions that tell the model to **echo, transcribe, or explain its internal reasoning as response text** can trigger the `reasoning_extraction` refusal category, causing elevated fallbacks to Opus 4.8.

**Audit every skill for:** "show your thinking", "explain your reasoning step by step in your response", "output your chain of thought", reflection templates that ask the model to transcribe deliberation. If you need reasoning visibility, read the structured `thinking` blocks from adaptive thinking instead.

Related: Fable 5 runs safety classifiers covering offensive-cyber and bio/life-sciences content. Benign work in those areas can trigger them. Configure fallback to Opus 4.8 for declined requests.

### 4.3 Long turns

Individual requests on hard tasks run for many minutes at higher effort; autonomous runs extend for hours. Adjust client timeouts, streaming, and progress indicators **before** migrating; prefer asynchronous check-ins over blocking.

To stop overplanning on ambiguous tasks: when there's enough information to act, act; don't re-derive established facts, re-litigate settled decisions, or narrate options that won't be pursued. Give a recommendation, not an exhaustive survey. (Scope that instruction to user-facing messages, not thinking blocks.)

### 4.4 Unrequested tidying at high effort

At higher effort Fable 5 may refactor, abstract, or harden beyond the task. Counter with a scope discipline block: no features/refactors/abstractions beyond what the task requires; a bug fix doesn't need surrounding cleanup; no design for hypothetical future requirements; no defensive handling for impossible scenarios; validate only at system boundaries.

### 4.5 Brevity via one short instruction

Instruction following is strong enough that **one short instruction replaces an enumerated list of behaviors**. Rather than listing "don't survey options, don't over-explain root causes, don't over-structure PR descriptions, don't narrate the next line in comments," a single lead-with-the-outcome instruction covers all of it. Note the distinction the docs draw: keep output short by being *selective about what you include*, not by compressing into fragments, arrow chains, or jargon.

### 4.6 Grounding progress claims

On long autonomous runs, instruct the model to audit each progress claim against an actual tool result from the session and to only report work it can point to evidence for. Anthropic reports this nearly eliminated fabricated status reports even on tasks designed to elicit them.

### 4.7 Boundaries on unrequested action

Fable 5 occasionally takes unrequested actions (drafting an email, creating defensive git branches). State explicitly: when the user is describing a problem, asking a question, or thinking out loud, the deliverable is your assessment — report findings and stop, don't apply a fix until asked.

### 4.8 Rare early stopping

Deep in long sessions Fable 5 may end a turn with a statement of intent ("I'll now run X") without the tool call. For autonomous pipelines, add a system reminder that the user isn't watching, that reversible actions following from the original request should proceed without asking, and that before ending a turn the model should check whether its last paragraph is a plan/question/promise — and if so, do the work now.

### 4.9 Context-budget anxiety

In very long sessions Fable 5 may suggest a new session or trim its own work — most often triggered when **the harness surfaces a remaining-token countdown**. Avoid showing explicit context-budget counts. If you must, add reassurance that ample context remains and the work should continue.

### 4.10 Memory

Fable 5 performs notably better when it can record lessons from prior runs and reference them. A plain markdown notes directory is sufficient: one lesson per file, one-line summary at top, record corrections and confirmed approaches with the reason they mattered, update rather than duplicate, delete what turns out wrong.

### 4.11 Give the reason, not only the request

Fable 5 connects tasks to relevant information better when it knows *why*. Pattern: "I'm working on [larger task] for [audience]. They need [what the output enables]. With that in mind: [request]."

---

## 5. What to delete from existing skills — audit table

| Legacy pattern in your skill | Action on Claude 5 |
|---|---|
| "Always verify / double-check / re-verify" | **Delete** (Opus 5 compounds it) |
| "Use a subagent to verify your work" | **Delete**; add delegation criteria instead |
| "CRITICAL: You MUST use this tool when…" | Downgrade to plain "Use this tool when…" — aggressive language now overtriggers |
| "If in doubt, use [tool]" / "Default to [tool]" | Replace with targeted "Use [tool] when it would improve your understanding of X" |
| "Show your reasoning / explain your thinking in the response" | **Delete** — risks `reasoning_extraction` refusal on Fable 5 |
| Long few-shot example blocks for tool usage | Replace with a better tool interface (expressive enum params, self-describing schema) |
| Enumerated lists of forbidden behaviors | Collapse to one positive instruction describing the target style |
| "Do not add comments" / rigid formatting bans | Replace with match-the-surrounding-code guidance |
| Everything-in-one-file skill bodies | Split into `SKILL.md` navigation + one-level-deep reference files |
| "Be conservative / only report high-severity" | **Delete** — taken literally; report all, filter in a second pass |
| Instructions telling the model not to think/reason | **Delete** — increases XML tag leakage on Opus 5 |
| Duplicate instructions in both system prompt and tool description | Keep only the tool description |

---

## 6. Structural rules that still hold

These predate Claude 5 and remain correct ([Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)):

- **`SKILL.md` body under 500 lines.** Beyond that, split.
- **References one level deep from `SKILL.md`.** Nested references get partially read (`head -100` style previews) and yield incomplete information.
- **Reference files over 100 lines get a table of contents** so partial reads still reveal full scope.
- **`description` carries the trigger load.** Third person, states both *what it does* and *when to use it*, includes the terms users actually say.
- **Set degrees of freedom to match fragility.** High freedom for open-ended judgement work; low freedom (exact scripts, no variation) for fragile, must-be-consistent operations like migrations. Claude 5 shifts the *default* toward high freedom — it does not eliminate the low-freedom case for genuinely narrow-bridge tasks.
- **Consistent terminology**, no time-sensitive statements, one recommended default rather than a menu of options.
- **Prefer scripts for deterministic operations** — script code never enters context, only output does.
- **Build evals before writing extensive documentation.** Measure baseline without the skill, write the minimum that closes the gap.

---

## 7. Claude Code mechanics that cause "unreliable" skills

These are harness behaviors, not model behaviors, and they account for a surprising share of intermittent skill failures ([Claude Code skills docs](https://code.claude.com/docs/en/skills)).

### 7.1 Skill descriptions get truncated when you have many skills

Claude Code loads a listing of skill names + descriptions into context. The listing budget scales at **1% of the model's context window**. When it overflows, descriptions are dropped **starting with the skills you invoke least** — stripping the exact keywords needed for matching. Each entry's combined `description` + `when_to_use` is also capped at **1,536 characters**.

**Diagnose:** run `/doctor` for an estimate of listing cost and its biggest contributors; check the Skills row in `/context`; run with `--debug` for the overflow warning.

**Fix:** put the key use case first in the description; set low-priority skills to `"name-only"` in `skillOverrides`; raise `skillListingBudgetFraction` (e.g. `0.02`); or `skillListingMaxDescChars`.

### 7.2 Skill content persists — and gets dropped at compaction

Invoked skill content enters the conversation once and **stays for the session**; Claude Code does not re-read the file on later turns. Write standing instructions, not one-time steps.

At auto-compaction, invoked skills are re-attached after the summary keeping only the **first 5,000 tokens each**, sharing a **combined 25,000-token budget**, filled most-recent-first. If you invoked many skills in one session, older ones can be dropped entirely.

**Symptom:** "the skill worked at first, then stopped." Usually the content is still present and the model is choosing other approaches — strengthen the description and instructions, or enforce deterministically with hooks. If it's large or you invoked several since, re-invoke it after compaction.

### 7.3 Frontmatter levers worth using

| Field | Use for |
|---|---|
| `disable-model-invocation: true` | Side-effecting workflows (deploy, commit, send). Also removes the skill from Claude's context entirely. |
| `user-invocable: false` | Background knowledge that isn't a meaningful user command. |
| `effort` | Per-skill effort override — e.g. `low` for a routine formatting skill, `xhigh` for a deep refactor skill. |
| `model` | Pin a skill to a specific model for the turn. |
| `paths` | Glob-limit when the skill auto-activates. Cuts false triggers in monorepos. |
| `context: fork` (+ `agent`) | Run in an isolated subagent. **Only for skills with an actionable task** — a pure conventions/guidelines skill forked into a subagent returns nothing useful. |
| `disallowed-tools` | Remove tools from the pool while the skill is active (e.g. block `AskUserQuestion` in a background loop). |
| `!` `` `command` `` injection | Pre-render live data (diffs, PR contents) into the prompt before the model sees it. |

### 7.4 Triggering troubleshooting

- Not triggering → description keywords, verify it appears in "What skills are available?", check for malformed YAML (a parse error loads the body with empty metadata, so `/skill-name` works but auto-matching silently doesn't).
- Triggering too often → tighten the description, or `disable-model-invocation: true`.
- **`/doctor`** is the bundled skill Anthropic shipped specifically to rightsize skills and `CLAUDE.md` files against this guidance.
- **`skill-creator`** plugin (`/plugin install skill-creator@claude-plugins-official`) automates the with-skill vs. without-skill baseline comparison, per-case subagent isolation, blind A/B between skill versions, and description trigger-rate tuning.

---

## 8. Layer allocation

Where content belongs, per Anthropic's framing:

- **System prompt** — product context: what the agent is and what it's doing. In Claude Code you won't touch it; in your own harness this is where to spend effort.
- **`CLAUDE.md`** — lightweight. Brief statement of what the repo is; spend most tokens on **gotchas** (e.g. "all types live in one monolithic file"). Avoid stating the obvious that's discoverable from the filesystem. Push multi-step procedures out into skills.
- **Skills** — lightweight guides Claude finds when needed. Encode *your* opinions, team knowledge, product-specific practice. Avoid overconstraint except in genuinely high-stakes areas. Long skills get split across files.
- **References** — `@`-mentioned files. **Prefer code over prose.** An HTML mockup beats a design description or a screenshot. A detailed test suite is a spec. A function in another codebase is a portable specification. Rubrics let verifier subagents check taste.

---

## 9. Suggested audit procedure

1. Inventory: list every skill, its line count, and its `description`.
2. Run `/doctor`; note listing cost and truncation warnings.
3. Grep the library for the deletion triggers in §5 — verification instructions, `CRITICAL:`/`MUST` escalation, "show your reasoning", "if in doubt use", enumerated prohibition lists.
4. Delete first, rewrite only where the instruction encodes genuine local knowledge the model can't infer.
5. Split anything over 500 lines; flatten nested references to one level.
6. Re-tune descriptions: key use case first, real user vocabulary, under the character cap.
7. Set per-skill `effort` deliberately; run a fresh effort sweep rather than carrying over 4.x settings.
8. Establish a baseline: run realistic prompts in fresh sessions with and without the skill. A fresh session matters — leftover authoring context masks gaps in the written instructions.
9. Iterate with `skill-creator` evals; confirm each edit is an improvement via blind A/B before committing.

---

## 10. A caveat worth holding

Anthropic's own guidance is that Opus 5 performs well out of the box on existing Opus 4.8 prompts, and that the tuning above addresses the behaviors that *most often* need adjustment. Independent early testing has been more mixed — notably [Every's evaluation](https://www.ai.joaoqueiros.com/blog/claude-opus-5-review-effort-skills-migration) (secondary summary) reported Opus 5 being less dependable than Fable inside mature, skill-driven workflows built around a predecessor. The practical read: a stronger model can perform worse inside a system designed for its predecessor, and the fix is to **simplify the behavioral scaffolding while keeping acceptance criteria strict** — not to write a longer prompt or crank effort to `max`.

---

## Sources

**Primary (Anthropic):**
- [The new rules of context engineering for Claude 5 generation models](https://claude.com/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models) — Jul 24, 2026
- [Prompting Claude Opus 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5)
- [Prompting Claude Fable 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5)
- [Prompting best practices (all current models)](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- [Extend Claude with skills (Claude Code)](https://code.claude.com/docs/en/skills)
- [Effort](https://platform.claude.com/docs/en/build-with-claude/effort)
- [Migration guide](https://platform.claude.com/docs/en/about-claude/models/migration-guide) · [What's new in Opus 5](https://platform.claude.com/docs/en/about-claude/models/whats-new-opus-5)
- [A field guide to Claude Fable 5: finding your unknowns](https://claude.com/blog/a-field-guide-to-claude-fable-finding-your-unknowns)
- [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [A harness for every task: dynamic workflows in Claude Code](https://claude.com/blog/a-harness-for-every-task-dynamic-workflows-in-claude-code)
- [Building verification loops in Claude Code with skills](https://claude.com/blog/building-verification-loops-in-claude-code-with-skills)

**Community (use with judgement):**
- [Evaluating skill output quality](https://agentskills.io/skill-creation/evaluating-skills) — agentskills.io, the Agent Skills open standard
- [Opus 5 review: effort, skills, migration](https://www.ai.joaoqueiros.com/blog/claude-opus-5-review-effort-skills-migration)
