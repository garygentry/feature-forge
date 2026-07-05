# Context & Session Management — Analysis Canon

**Status:** pre-implementation canon / future-PRD input — **not** an implementation plan.
**Scope:** the context- and session-economics of the Feature Forge pipeline — the warm-vs-cold
session tradeoff, the re-read tax, auto-verify, lean handoffs, and a root-orchestrator thought
experiment.
**Method:** distilled from an extended design conversation that worked the tradeoffs from first
principles (token economics, attention/quality, subagent orchestration, cross-session recall) and
pressure-tested each lever adversarially. This document captures *the reasoning and the open
tensions* — the substance a future
[`/feature-forge:forge-1-prd context-management`](../../skills) run would consume. It deliberately
does **not** decide the design; the open questions are left open by intent.

> Companion, not duplicate: the broad DX survey lives in
> `plans/feature-forge-dx-context-enhancement-ideas.md` (idea backlog across five lenses, ranked by
> impact/effort). This document goes **narrower and deeper** on the context/session axis alone. The
> operator-facing "what should I do today" guidance lives in the docs site at
> [`pipeline/managing-context`](../../docs-site/src/content/docs/pipeline/managing-context.mdx).

---

## 1. Purpose & status

Feature Forge runs a feature through ~10 discrete steps — a stage per `forge-1`…`forge-6` plus
verify gates — and each step tends to be its own session. That structure trades cheap-to-run lean
windows against an expensive-to-enter re-read, and it repeats the warm-vs-cold decision at every
transition. This canon exists so that reasoning is not lost to the conversation that produced it:
it is the input to a future PRD that would optimize context handling in the implementation. Nothing
here is committed as design.

## 2. Current mechanisms (what we build on)

- **Fresh window per stage.** Each stage is meant to start lean and read the upstream artifact on
  disk, not rely on conversation memory.
- **Externalized state.** Per-feature `{specsDir}/{feature}/.pipeline-state.json` holds per-stage
  `{status, version, artifacts[], basedOnVersions, commitHash, branch, notes}`, so a session can die
  and resume. Epics layer an epic manifest on top.
- **Navigator context gate.** The `forge` navigator (`scripts/forge-session.py`, `context-usage`
  helper) measures session fullness against `contextWindowTokens` and, past
  `contextWarnThreshold`, recommends a clean session before advancing. It **recommends but never
  auto-clears** — the `/clear` is always the operator's act.
- **Verify as subagent.** `forge-verify` runs in its own fresh subagent, clean-room by construction.
- **Config keys already in play** (`references/forge-config-schema.json`):
  `contextWindowTokens`, `contextWarnThreshold`, `autoInvokeNextStage`.

## 3. Warm vs. cold session economics

Frame each transition with three quantities:

- **`C`** — *carried* context a warm session brings into the next stage (everything already in the
  window).
- **`R`** — *re-read entry cost* a cold session pays to re-establish (re-reading PRD + tech spec +
  spec suite: easily 15–20k tokens before any work).
- **`W`** — the *window* budget the stage has to work within.

**Cold is the default** because it keeps each stage's `W` lean and independent: the stage reads the
upstream artifact as a contract and judges it on its own merits.

**Warm's cost is not flat overhead — it compounds.** The excess `C` a warm session carries is paid
**per turn × remaining turns** of the stage: every subsequent model turn re-attends the carried
context. A stage with many turns pays the carry many times over, which is why "just stay warm, it's
already loaded" understates the true cost.

**The prompt-caching asterisk.** Warm sessions keep a hot prompt cache, so re-attending `C` is
cheaper than a naive token count implies; a cold session pays a per-stage cache-miss to re-establish
`R`. Caching **narrows** the warm-vs-cold gap but usually does **not reverse** it — the compounding
per-turn attention cost and the independence argument survive.

**The parity argument.** Even when warm and cold reach *token parity*, cold still wins on
**attention/quality**: a lean window focused on exactly this stage's work produces better output
than a fuller window diluted with prior-stage residue. Independence is not just economy; it's
accuracy.

## 4. Auto-verify

Verification is almost always wanted after a stage, yet is manually invoked every time. Making it
default-on is attractive, but only under tight constraints:

- **Clean-room by construction.** Verify already runs in a fresh subagent — it inherits no context,
  so it is safe to run automatically without polluting the dispatching session.
- **Default-on only at the existing gates**, not everywhere — respect the places the pipeline
  already pauses.
- **Gate on the *dispatching* session's context, not the verifier's.** The verifier is always fresh;
  the decision to auto-run keys off how full the session that would trigger it is.
- **Return a compact digest,** not the full analysis, so a clean verify costs the main window almost
  nothing.
- **Staleness ledger** so "always verify" means "verify when the artifact *changed*" — re-verifying
  an unchanged artifact is pure waste.
- **Never auto-`forge-fix`.** Fixing mutates artifacts and must stay human-gated. Auto-verify is
  read-only; auto-fix is not.
- **Payoff, asymmetric by path.** On the **green path**, auto-verify roughly *halves* the clears (no
  separate verify round-trip). On the **red path**, it stays a full loop — findings → human → fix.
- **Amortize the cost.** Have the verifier also emit the lean handoff digest (see §5), so even a
  clean verify is never pure overhead — it produces the next stage's entry context.

## 5. Lean handoff reframing

The re-read tax (§3, `R`) and clean-room verify (§4) are the **same mechanism** viewed twice: the
verifier's fresh, independent read of the artifact *is* exactly the re-establishment context the
next stage needs. So the verifier should emit a **lean handoff digest** — a few-hundred-token
contract summary — that the next cold session enters on instead of paying the full `R`. One read,
two uses: it verifies *and* it shrinks the next entry. This collapses "verify" and "re-orient" into
a single disposable-subagent pass.

## 6. Orchestrator / controller thought experiment

Could one root session run all stages end-to-end? Viable in principle, but the hard pitfalls define
the shape:

- **Interview stages can't be headless subagents.** PRD and tech-spec are interactive; they must be
  pinned to the **foreground** with a human in the loop. They are natural breakpoints, not links to
  automate away.
- **Subagent nesting-depth caps the fan-out stages.** Specs and verify already fan out into
  subagents; an orchestrator that is itself a subagent hits nesting limits. The controller has to
  live at the top.
- **Reliability demands a deterministic controller, not an LLM holding control flow.** Loop/branch
  logic belongs in **code**; an LLM improvising the state machine across ten stages is where
  reliability goes to die. (The **Workflow** primitive already embodies exactly this — deterministic
  control flow orchestrating model-driven steps.)
- **Digest-only chaining removes human eyeballs from intermediate artifacts.** If stages hand off
  compact digests, no human reads the full PRD/spec between stages. **Auto-verify between stages is
  the mitigating checkpoint** — the independent read that substitutes for the human's skim.
- **The payoff:** once state is fully externalized, **single-session and cross-session become the
  same architecture.** A resumable deterministic controller doesn't care whether it runs in one
  sitting or ten — the state file is the truth either way.

**Recommended shape (as a hypothesis, not a decision):** a thin **deterministic controller** +
**stage-subagents** + **foreground human breakpoints** at the interview stages, with **auto-verify
digests** as the inter-stage checkpoints.

## 7. Implied config surface (surfaced as questions, not decisions)

These are the knobs the above *implies*. None is proposed here:

- `autoVerify` — default-on at gates? Scope? Off-switch granularity?
- `autoAdvance` vs. auto-fix split — advancing is safe to automate; fixing is mutating and must
  stay human-gated. Where exactly is the line?
- **Measured** auto-invoke — replace the current heuristic with an actual comparison of
  `C + R` (stay-warm cost) vs. `W · contextWarnThreshold` (headroom), so the recommendation is
  computed, not guessed.

## 8. Open questions for the PRD

1. Is the lean handoff digest **trustworthy enough** to enter a stage on, or does each stage still
   need to re-read the full artifact to be safe? (The whole §5 payoff hinges on this.)
2. What is the **staleness signal** — `commitHash`? artifact `version`? a content hash? — that makes
   "verify when changed" reliable?
3. How much does **prompt caching** actually move the warm-vs-cold break-even in practice? (§3 is
   reasoned, not measured.)
4. For the orchestrator: which stages are **safe to chain on digests alone**, and which must keep a
   human reading the full artifact?
5. What is the **failure/recovery** contract when an auto-verify between stages goes red mid-chain —
   halt, notify, or roll back to a breakpoint?
6. Does removing intermediate human review **degrade artifact quality** enough to outweigh the
   token/latency savings?

## 9. Cross-references

- `plans/feature-forge-dx-context-enhancement-ideas.md` — broad DX/idea companion (gitignored; the
  wider survey this doc narrows).
- [`docs-site/src/content/docs/pipeline/managing-context.mdx`](../../docs-site/src/content/docs/pipeline/managing-context.mdx)
  — operator-facing when-to-clear guidance (the practical altitude of this analysis).
- `scripts/forge-session.py` — navigator, `context-usage` / `rank-features` helpers.
- `references/forge-config-schema.json` — existing config keys (`contextWindowTokens`,
  `contextWarnThreshold`, `autoInvokeNextStage`).
- `references/shared-conventions.md` — pipeline conventions and invariants.
