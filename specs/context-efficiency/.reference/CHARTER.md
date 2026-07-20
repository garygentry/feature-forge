# context-efficiency — Charter

> Pre-PRD brief. Input to `forge-1-prd context-efficiency` (or, if decomposed,
> `forge-0-epic context-efficiency`). When the pipeline starts for this feature,
> **read every document in this `.reference/` directory first** — they are the
> evidence base for the interview. Describes *what* this work is and the scope
> it owns — deliberately light on *how*, which the pipeline (PRD → tech →
> specs) will decide.

## One-liner

Reduce the fixed instruction-token overhead of every forge pipeline invocation
by tightening progressive disclosure — load only the slice of guidance a given
skill/stage/subagent actually needs, when it needs it — **without changing any
observable behavior**.

## Problem

A top-to-bottom audit (2026-07-19, at v0.12.9 / commit b9f0871 — see
`AUDIT.md`) found the architecture fundamentally sound: deterministic compute
lives in scripts, heavy content is delegated to disposable subagent contexts,
the session hook is near-silent. But **granularity** is off in a few places:
three files are loaded whole when only a slice is needed, boilerplate is
duplicated ~31 times across loaded surfaces, and a verbose JSON Schema is read
per stage. A typical stage session carries **~13–19k tokens of instruction
overhead before touching any artifact**, and because the pipeline deliberately
recommends `/clear` at every stage boundary, that fixed overhead is re-paid per
stage — roughly **100–150k instruction tokens across a full feature run**, of
which an estimated **30–40% is recoverable** at low-to-moderate risk.

Full measurements: `LOAD-MAP.md`. Ranked findings: `RECOMMENDATIONS.md`.

## Scope

### In scope

- **R1 — Split `skills/forge-verify/references/verification-checklists.md` per
  mode** so each verifier subagent (and each member of a parallel fan-out)
  loads only its mode's checklist, not all six plus orchestrator-facing
  template/example sections.
- **R2 — Deduplicate the plugin-root prelude within files**: define the 3-line
  `R=` resolver block once per file, reference it thereafter. Within-file only
  (see `GUARDRAILS.md` on why cross-file dedup is off the table).
- **R3 — Make the navigator's `process-overview.md` read explicitly
  conditional** (wording change in `skills/forge/SKILL.md` Step 1).
- **R4 — Replace the per-stage `pipeline-state-schema.json` read**: either a
  `forge-session.py` state-write/patch helper (preferred — also kills
  hand-authored-JSON drift) or a compact annotated example.
- **R5 — Add a `forge-session.py effective-config` subcommand** emitting the
  resolved `loopRunner` block, so forge-5-loop and forge-4-backlog stop reading
  `forge-config-schema.json` (~2k words) for defaults.
- **R6 — Split `skills/forge-5-loop/references/runner-contract.md`** into
  always-needed (launch, monitor, event reactions) vs. rarely-needed (agent
  selection — only when `agentArgument` is configured; optional-flags catalog).
- **R7 — Restructure `references/shared-conventions.md`** (the ~6k-token
  monolith read unconditionally by ~10 skills, each using roughly half its 13
  blocks) into a thin universal core plus per-block files read at invoke
  points. **Highest payoff, only structurally risky item** — prototype on one
  low-stakes skill first (see `RECOMMENDATIONS.md` §R7 and `GUARDRAILS.md`).
- Extending the existing drift-guard test discipline to cover any new
  block/reference files, and regenerating adapters + fixtures for moved paths.

### Out of scope / non-goals

- Any change to interactive behavior: AskUserQuestion protocols, Decision
  Support, guards (Stage-Entry, Stage-Completion Re-check, Epic-Member Base),
  verify gates, stage-exit routing. Content may *move*; it must not *change*.
- Frontmatter descriptions (already minimal and well-scoped — measured ~1.2k
  tokens for all 13 skills, the only always-loaded surface).
- The `SessionStart` hook (already silent on the common path).
- Trimming Epic Context Injection's dep-spec loading (a deliberate product
  decision; flagged as a watch item only — see `RECOMMENDATIONS.md` §W1).
- Consolidating the duplicated epic-backflow paragraph in forge-1-prd /
  forge-2-tech (roughly token-neutral; watch item W2).
- Non-Claude adapter behavior changes beyond mechanical regeneration.

## Constraints (hard)

See `GUARDRAILS.md` for the full list with rationale. Headlines:

1. **Behavior-preserving.** The system works well in extensive real use; every
   change must be a pure relocation/dedup of instruction text or a
   script-extraction of deterministic logic.
2. **CI gates:** `check-spec-purity.py` caps skill bodies at 300 lines
   (forge-5-loop is *at* the cap); `ruff` on `scripts/` + `eval/` is CI-only —
   run locally.
3. **Adapter fan-out:** `build-adapters.py` discovers reference files via
   citations in skill bodies; new/moved reference paths must stay
   citation-discoverable, and adapters + fixtures must be regenerated.
4. **Drift guards:** `tests/test_stage_exit_protocol.py`-style stamp assertions
   must be extended, not weakened, for any split file.
5. **Measure first.** Validate assumptions (e.g. "the schema read actually
   happens") against real dogfood transcripts before optimizing.

## Success criteria (candidate REQs for the PRD interview)

- Per-invocation instruction load measurably reduced: verifier subagent from
  ~11k to ≤4k tokens; loop from ~19k to ≤14k; stage skills by ≥2k each once R7
  lands. (Baselines in `LOAD-MAP.md` — re-measure, don't trust, at PRD time.)
- Zero behavioral diff: a full dogfooded feature run (all stages + verify +
  loop + docs) exhibits the same prompts, gates, guards, and outputs as before.
- All existing tests green; new drift-guard coverage for every split file.
- Adapters regenerate cleanly; fixture snapshots updated.

## Decomposition option (if run as an epic)

R1–R3 are independent and low-risk ("quick wins"); R4–R6 are the
script-extraction family (shared `forge-session.py` surface); R7 is its own
high-touch effort with a prototype gate. A natural 3-member epic:
`quick-wins` (R1+R2+R3) → no deps; `config-and-state-helpers` (R4+R5+R6) → no
deps; `conventions-split` (R7) → depends on quick-wins landing (to observe the
measurement deltas first). A single feature with phased specs is equally
viable — decide at pipeline start.
