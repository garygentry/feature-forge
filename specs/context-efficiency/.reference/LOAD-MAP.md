# Load Map — What Loads When, Measured

> Measured 2026-07-19 @ b9f0871 with `wc -l` / `wc -w`. Token estimates use
> ~1.3 tokens/word for markdown prose (JSON schemas run higher).
> **Re-measure at PRD time** — these numbers drift with every release.

## Always loaded (every session, every user)

| Surface | Size | Notes |
|---|---|---|
| 13 skill frontmatter descriptions | ~4.9k chars ≈ 1.2k tok | 280–550 chars each; well-scoped, no action |
| `SessionStart` hook output | 0 in common case | `session-check.sh` exits silently unless state exists w/o config |

## Skill bodies (loaded on invoke)

| Skill | Lines | Words | Local refs |
|---|---|---|---|
| forge (navigator) | 233 | 4,005 | — |
| forge-0-epic | 298 | 2,606 | edit-mode.md 266L/1,934w · epic-manifest-subcommands.md 75L/707w (both conditional) |
| forge-1-prd | 154 | 2,587 | prd-template.md 106L/547w (needed) |
| forge-2-tech | 215 | 2,481 | stack-discovery-checklist.md 95L/477w |
| forge-3-specs | 168 | 1,891 | spec-archetypes.md 106L/586w · spec-examples.md 71L/432w |
| forge-4-backlog | 165 | 2,289 | — |
| forge-5-loop | 304 | 4,481 | runner-contract.md 341L/2,864w · result-reporting.md 85L/505w |
| forge-6-docs | 192 | 1,769 | doc-conventions.md 126L/437w |
| forge-bootstrap | 240 | 1,965 | templates (cp'd, not read) |
| forge-fix | 88 | 1,154 | — |
| forge-guide | 182 | 1,623 | — (grounds in shared refs on demand) |
| forge-init | 60 | 537 | — |
| forge-verify | 263 | 2,554 | verification-checklists.md 477L/4,755w |

NOTE: `check-spec-purity.py` (CI) caps bodies at 300 lines; forge-5-loop is at
304 (grandfathered/cap-adjacent — treat as at-cap).

## Shared references (`references/`)

| File | Lines | Words | Read by |
|---|---|---|---|
| shared-conventions.md | 295 | 4,569 | ~10 skills, **unconditional** ("read and follow … before proceeding") |
| stage-exit-protocol.md | 258 | 2,531 | Cited everywhere but stamp is inline → effectively build-time only |
| ralph-loop-contract.md | 221 | 1,674 | forge-guide on demand; loop cites |
| process-overview.md | 143 | 1,326 | navigator (Step 1, ambiguous conditionality), forge-guide |
| portable-root.md | 71 | 676 | doc; cited |
| stack-resolution.md | 54 | 386 | forge-guide |
| vendor-construct-inventory.md | 50 | 643 | doc |
| stacks/*.md | 111–184 | 761–1,295 | conditional on config `stack` |
| forge-config-schema.json | 236 | 2,068 | forge-4-backlog, forge-5-loop (for loopRunner defaults), forge-guide |
| pipeline-state-schema.json | 191 | 1,149 | cited by 8 skills ("write state conforming to") |
| epic-manifest-schema.json | 125 | 479 | epic paths |

## shared-conventions.md block inventory (the R7 target)

13 blocks: Feature Name Requirement · User Input Protocol (AskUserQuestion +
Decision Support) · Configuration Reading · Feature Directory Resolution (+
cross-branch discovery + anti-fabrication) · Specs Directory Hygiene · Epic
Context Injection · Epic-Member Base Guard · Pipeline State Protocol /
Staleness · Branch Setup · Branch Reconciliation · Git Commit Protocol ·
Stage-Entry Guard · Stage-Completion Re-check · Force Mode.

Usage is partial per consumer, e.g.:
- **forge-verify** uses: name/config/Decision Support/Dir Resolution. Dead
  weight: Branch Setup, Branch Reconciliation, Git Commit, Stage-Entry Guard,
  Stage-Completion Re-check, both epic guards.
- **navigator** (read-only by design) never fires: Git Commit, Stage-Entry
  Guard, Stage-Completion Re-check, Branch Setup.
- **forge-1-prd** (a full authoring stage) never uses Branch Reconciliation
  (loop-only).

## verification-checklists.md section spans (the R1 target)

| Section | Lines | Consumer |
|---|---|---|
| PRD Mode Checklist | 7–31 | verifier (mode=prd) |
| Tech-Spec Mode | 32–60 | verifier (mode=tech) |
| Specs Mode | 61–118 | verifier fan-out (mode=specs, 3+ instances) |
| Backlog Mode | 119–209 | verifier fan-out (mode=backlog) |
| Implementation Mode | 210–251 | verifier fan-out (mode=impl) |
| Epic Mode | 252–324 | single verifier (mode=epic) |
| Findings Document Template | 325–374 | **orchestrator** (Synthesize step) |
| Example Findings | 375–408 | orchestrator |
| Epic Mode State Write Detail | 409–477 | orchestrator |

Every verifier instance currently reads all 477 lines. A specs-mode fan-out of
3 instances ≈ 18k checklist tokens loaded to use ~2k.

## runner-contract.md section spans (the R6 target)

| Section | Lines | Actually needed |
|---|---|---|
| Model selection precedence | 10–22 | every run |
| Agent selection | 23–111 | **only when `loopRunner.agentArgument` configured** |
| Run mode (rauf) | 112–152 | every rauf run |
| Optional flags catalog | 153–168 | rarely |
| Launch detail | 169–230 | every run |
| Monitor arming | 231–269 | every run |
| Event reactions | 270–299 | every run |
| Inform-user template | 300–341 | every run |

## Plugin-root prelude (`R="$(bash -c 'for d in …')"`) occurrences

skills: forge 5 · forge-0-epic 6 · forge-bootstrap 4 · forge-1-prd 2 ·
forge-5-loop 2 · one each in forge-2-tech/3-specs/4-backlog/6-docs/init/verify.
references: shared-conventions 6 · stage-exit-protocol 1 (stamp).
**≈31 copies in runtime-loaded surfaces** (excludes portable-root.md ×11 and
vendor-construct-inventory ×4, which are docs). ~85 words ≈ 110 tok per copy.
A navigator run holds ~11 copies (~1.2k tok) of identical text.

## Agent definitions (loaded into each subagent)

forge-researcher 136L/810w · forge-spec-writer 114L/763w ·
forge-verifier 122L/1,077w.

## Per-invocation instruction-load estimates (before reading any artifact)

| Invocation | Composition | ≈ tokens |
|---|---|---|
| Navigator `/forge` | body 4,005 + shared-conv 4,569 + process-overview 1,326 | ~13k |
| forge-2-tech | body 2,481 + shared-conv 4,569 + checklist 477 + state-schema 1,149 + stack ~1,000 | ~13k |
| forge-5-loop | body 4,481 + shared-conv 4,569 + runner-contract 2,864 + config-schema 2,068 + result-reporting 505 | ~19k |
| verifier subagent (each) | agent 1,077 + forge-verify skill 2,554 + checklists 4,755 | ~11k |

Full feature run ≈ 6–8 stage sessions (each fresh post-`/clear`) + verify
subagents ⇒ **~100–150k instruction tokens per feature**, excluding artifacts.

## Savings model (per-invocation, by recommendation)

> Realistic projections, not promises — static file-size sums assuming each
> cited read actually happens. Validate against dogfood transcripts before
> adopting as success criteria (see `GUARDRAILS.md` §7). R7 figures are the
> deferred follow-up feature, shown for completeness.

| Invocation | Baseline | R1–R6 savings | After R1–R6 | +R7 later | Final |
|---|---|---|---|---|---|
| `/forge` navigator | ~13k | −2.7k (R3 1.7k, R2 ~1.0k) | ~10.3k (−21%) | −3k | ~7.3k (−44%) |
| forge-1-prd | ~11.5k | −2.2k (R4 1.5k, R2 0.7k) | ~9.3k (−19%) | −3k | ~6.3k (−45%) |
| forge-2-tech | ~13k | −2.2k (R4, R2) | ~10.8k (−17%) | −3k | ~7.8k (−40%) |
| forge-3-specs | ~12.5k | −2.2k (R4, R2) | ~10.3k (−18%) | −3k | ~7.3k (−42%) |
| forge-4-backlog | ~13k | −4.8k (R5 2.7k, R4 1.5k, R2 0.6k) | ~8.2k (−37%) | −3k | ~5.2k (−60%) |
| forge-5-loop | ~19k | −4.6k (R5 2.7k, R6 1.1k, R2 0.8k) | ~14.4k (−24%) | −3k | ~11.4k (−40%) |
| forge-6-docs | ~9k | −1.6k (R4, R2) | ~7.4k (−18%) | −3k | ~4.4k (−51%) |
| verifier subagent (each) | ~11k | −4.4k (R1) | ~6.6k (−40%) | 0 † | ~6.6k |

† R7 helps the verify *orchestrator* session, not the subagent (the subagent
does not read shared-conventions).

Modeling notes:

- **R1 carries a fan-out multiplier.** ~4.4k saved per verifier instance; a
  feature running all five verify gates with parallel fan-out on the large
  modes dispatches ~9–11 instances (**~40–50k/feature** max case; ~20–30k
  typical, since some gates run single-instance or are skipped).
- **R7 nets ~2.5–3.5k per consumer, not the full 6k** — every stage keeps the
  ~2k universal core (name/config/AskUserQuestion) plus the 1–2k of blocks it
  actually invokes. Applies to all 9 shared-conventions consumers (every
  stage above plus forge-fix).
- **R4's realized savings depend on read frequency** — if transcripts show
  the model already skips the schema read sometimes, scale down accordingly.
- The loop's ~14.4k post-R1–R6 floor is sticky: shared-conventions (until
  R7) plus the always-needed launch/monitor sections of runner-contract are
  genuinely used.
- Artifact tokens (PRDs, specs, code read by researcher/writers) are out of
  scope — appropriately spent, and dominant in later stages.

### Per-feature rollup

Typical full run: each authoring stage once, navigator ~3×, five verify
gates, ~7 verifier instances.

| | Instruction tokens / feature |
|---|---|
| Baseline | ~115–140k |
| After R1–R6 | ~75–95k (**−30–35%**; roughly half from R1's multiplier) |
| After R7 too | ~55–75k (**−45–50%** vs. baseline) |
