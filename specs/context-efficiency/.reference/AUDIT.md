# Token-Efficiency Audit — Full Assessment

> Conducted 2026-07-19 against `main` @ b9f0871 (plugin v0.12.9 / installer
> 0.2.14). Method: read the complete canonical surface (all 13 SKILL.md bodies,
> shared `references/`, skill-local references, agent definitions, hooks,
> scripts inventory) and measured word/line counts of everything that loads at
> each point in the pipeline. Read-only; no changes made.

> ## ✅ Re-measured at v0.13.0 (2026-07-28) — see `REMEASURE-0.13.0.md`
>
> **Result: every figure below reproduces. No R falls below the ~50% stop-rule; R1, R3,
> R4, R5 and R6 all measure at 100–134% of their claims.** The canonical surface
> (`skills/`, `references/`, `agents/`) is byte-identical to the audit base apart from a
> rauf pin version string in `forge-config-schema.json` — the Pi adapter work landed in
> build and host-porting machinery, not in anything a stage session loads.
>
> Two results in `REMEASURE-0.13.0.md` change how the backlog should be authored, and are
> not visible in the numbers below: transcript evidence that the per-stage schema read is
> **not** in fact per-stage (so R4/R5's *realized* savings are below projection — scale the
> claim, don't assert it), and the line-cap headroom table (`forge-5-loop` has **2** lines,
> `forge-0-epic` **8**).
>
> ---
>
> ## Original staleness warning (retained for provenance)
>
> These figures predate **v0.13.0**, which added the Pi adapter target. The charter's rule is
> "measure first — re-measure, don't trust," so re-take every baseline this document
> claims a saving against, at the current HEAD, before sizing any backlog item.
>
> **Decision rule, set in advance (2026-07-28) so it is not a judgement call made under
> momentum:** if an R's re-measured saving comes in **below ~50% of the figure claimed
> here**, stop and surface it as an explicit ship/drop call rather than proceeding. SC-6
> (REQ-DELIV-01) makes dropping any single R free, so the cost of asking is near zero and
> the cost of shipping a relocation that no longer pays for its risk is not.
>
> R2 has already been dropped on this basis — see PRD §3.2.

## Verdict

The architecture is fundamentally sound. The big progressive-disclosure moves
are already in place and working. The main inefficiency is **granularity**:
a few files load whole when only a slice is needed. The fixed per-stage
instruction overhead (~13–19k tokens) is re-paid at every stage boundary
because the pipeline (correctly, for other reasons) recommends `/clear`
between stages.

## What is already done well — DO NOT REGRESS THESE

These are deliberate design wins. Any remediation must preserve them.

1. **Minimal session-start surface.** The `SessionStart` hook
   (`scripts/session-check.sh`) is silent in the common case — exits 0 with no
   output when `forge.config.json` exists or no pipeline state is found. The
   always-loaded cost is 13 frontmatter descriptions (~280–550 chars each,
   ~1.2k tokens total), each with crisp "Do NOT trigger" anti-scoping.

2. **Deterministic compute lives in scripts, not prose.**
   `scripts/forge-session.py` (`stage-exit`, `rank-features`, `context-usage`,
   `reconcile-branch`, `check-epic-base`, `discover-feature`) and
   `scripts/epic-manifest.py` (`resolve`, `render-status`, `validate`,
   mutators) replace pages of model-side derivation with compact JSON. The
   stage-exit migration is the single best token decision in the repo: "all
   the conditional logic the old prose blocks asked the model to compute now
   lives in the script, deterministically."

3. **Heavy content is pushed into disposable subagent contexts.**
   - forge-2-tech → `forge-researcher` fan-out (parallel for large codebases),
     returns distilled integration reports.
   - forge-3-specs → sequential foundation docs, then parallel
     `forge-spec-writer` subagents, one per numbered doc.
   - forge-verify → clean-room `forge-verifier` subagent(s); single dispatch
     for small modes (prd ~15, tech ~15 checks), parallel dimensioned fan-out
     for large modes (specs ~38, backlog ~27, impl ~23). Only digests return.

4. **Many references are genuinely conditional.** `edit-mode.md` and
   `epic-manifest-subcommands.md` (forge-0-epic, edit paths only),
   `spec-examples.md` / `spec-archetypes.md` (forge-3-specs, at need),
   `result-reporting.md` (loop, only at exit), `stacks/{stack}.md` (gated on
   config `stack` key). Templates (`references/templates/specs-hygiene/*`,
   bootstrap templates) are **cp'd by script, never read into context**.

5. **Epic Context Injection is deliberately bounded.** Direct completed
   dependencies only, no transitive (REQ-CTX-01); `render-status` supplies
   contracts + completion in one call.

6. **The scripted-stage-exit stamp is self-contained.** The inline stamp in
   each authoring skill summarizes the directive contract, so
   `references/stage-exit-protocol.md` (2.5k words) is effectively
   build-time/maintenance documentation, not a runtime read.

7. **The verifier role guard** (v0.12.1 fix) cleanly separates
   orchestrator-POV from subagent-POV in the dual-role forge-verify skill.

## The core findings (summary — full detail in RECOMMENDATIONS.md)

| # | Finding | Loaded surface | Waste mechanism |
|---|---------|----------------|-----------------|
| R7 | `references/shared-conventions.md` monolith | 295 L / 4,569 w (~6k tok) | Read unconditionally by ~10 skills; each uses ~half of its 13 blocks |
| R1 | `verification-checklists.md` not mode-split | 477 L / 4,755 w (~6k tok) | Every verifier instance loads all 6 modes + orchestrator sections to run one mode (or ⅓ of one mode in fan-out) |
| R2 | Plugin-root prelude duplicated | ~110 tok × ~31 copies | 6× in shared-conventions alone, 5× in navigator; ~11 copies in context during one navigator run |
| R4 | `pipeline-state-schema.json` per-stage read | 191 L / 1,149 w (~1.5k tok) | Cited by 8 skills; JSON-Schema verbosity ≫ information content |
| R5/R6 | forge-5-loop load | ~19k tok total | `runner-contract.md` nominally-conditional but effectively always read whole; `forge-config-schema.json` (2,068 w) read just for loopRunner defaults |
| R3 | Navigator reads `process-overview.md` | 143 L / 1,326 w | Unconditional wording in Step 1; dashboards never need architecture |

## Watch items (no action now)

- **W1:** Epic Context Injection loads each completed direct dep's full
  `PRD.md` + `tech-spec.md` — can dominate an interview session for a wide
  epic. Deliberate product decision; revisit only with transcript evidence of
  crowding.
- **W2:** The epic-backflow paragraph (~350 w) is duplicated near-verbatim in
  `forge-1-prd` (line ~102) and `forge-2-tech` (line ~97). Consolidation is
  roughly token-neutral; leave unless those bodies approach the 300-line cap.

## Estimated recovery

~30–40% of the ~100–150k instruction tokens per full feature run, dominated
by R7 (per-stage) and R1 (per-verify × parallel multiplier).
