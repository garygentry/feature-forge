# context-efficiency — Technical Specification

> HOW, not WHAT. Requirements live in `PRD.md`; every decision below cites the
> REQ-IDs it satisfies. Evidence base: the four-researcher codebase scan of
> 2026-07-20 against `forge/context-efficiency` (line counts, section
> boundaries, citation graph, and script conventions verified first-hand, not
> from the audit snapshot).

## 1. Overview

This feature is a **behavior-preserving instruction-token optimization** of the
forge pipeline itself (dogfooded on its own repo). It ships as **six
independently revertible units** (R1–R6, REQ-DELIV-01), each a *relocation*,
*dedup*, or *script-extraction* of instruction text — never a rewording of an
interactive protocol (C-1, REQ-BEHAV-01/02).

Key architectural decisions, all confirmed in the interview:

- **R1** — split the 477-line `verification-checklists.md` into 6 per-mode files
  + 1 orchestrator-only `findings-template.md`, so a verifier subagent loads only
  its mode (~1/6 the content, zero orchestrator material).
- **R2** — dedup the 3-line plugin-root prelude **within linear skill bodies
  only** (conservative scope), leaving the independently-invoked reference-block
  recipes verbatim.
- **R3** — gate the navigator's `process-overview.md` read behind
  "how does the pipeline work" questions.
- **R4** — replace all hand-authored `.pipeline-state.json` writes with a set of
  **targeted `forge-session.py` state verbs**, removing both the per-stage schema
  read and hand-authored-JSON drift.
- **R5** — add a `forge-session.py effective-config` subcommand that resolves the
  `loopRunner` block by reading the schema's machine-readable defaults at runtime.
- **R6** — split the 341-line `runner-contract.md`, moving the three
  agent-conditional sections into `agent-selection.md` (loaded only when
  `loopRunner.agentArgument` is set).

The two new script capabilities (R4, R5) live in the existing `forge-session.py`
(a `RUNTIME_HELPER`, so they ship to every adapter automatically), are
**stdlib-only** (no `jsonschema`, C-2), and follow the script's established
conventions verbatim. Every moved/split reference file stays
**citation-discoverable and host-neutral** (REQ-PORT-01/02); all five adapters
regenerate and fixtures refresh mechanically (REQ-PORT-03).

## 2. Module Structure

No new package. Changes are confined to the canonical surfaces the adapter build
fans out from. Files touched, grouped by unit:

```
scripts/
  forge-session.py                 # R4: +7 state verbs; R5: +effective-config
                                   #     (1,866 lines today; argparse + if-dispatch)
references/
  pipeline-state-schema.json       # R4: unchanged content; remains CI source of truth
  forge-config-schema.json         # R5: unchanged content; read at runtime for defaults
  process-overview.md              # R3: read-site relocated (file unchanged)
skills/forge/SKILL.md              # R2 (5→1+4) + R3 (gate the read)
skills/forge-0-epic/SKILL.md       # R2 (5→1+4); R4 (state verbs)
skills/forge-bootstrap/SKILL.md    # R2 (4→1+3)
skills/forge-1-prd/SKILL.md        # R2 (2→1+1); R4 (state verbs)
skills/forge-2-tech/SKILL.md       # R4 (state verbs)
skills/forge-3-specs/SKILL.md      # R4 (state verbs)
skills/forge-4-backlog/SKILL.md    # R4 (state verbs)
references/shared-conventions.md   # R4: Stage-Entry Guard / Branch Setup / completion
                                   #     switch to state-verb invocations (prose unchanged)
skills/forge-verify/
  SKILL.md                         # R1: cite the 6 mode files + findings-template.md
  references/
    verification-checklists.md     # R1: DELETED, replaced by ↓
    verification-checklists/        # R1: NEW
      prd.md tech.md specs.md backlog.md impl.md epic.md
    findings-template.md           # R1: NEW (orchestrator-only)
skills/forge-5-loop/
  SKILL.md                         # R6: 1:1 citation swap (line-neutral, cap-bound)
  references/
    runner-contract.md             # R6: keeps always-loaded sections
    agent-selection.md             # R6: NEW (3 conditional sections)
tests/                             # NEW drift guards (see §8); fixtures refreshed
```

**Public API surface** (what other pipeline code consumes): the new
`forge-session.py` subcommands. Their contracts (§5) are the only new "exports."

## 3. Technical Decisions

### 3.1 R1 — Verification-checklist mode split (REQ-R1-01..05)

**Decision.** Replace `skills/forge-verify/references/verification-checklists.md`
(477 lines) with:

- `references/verification-checklists/{prd,tech,specs,backlog,impl,epic}.md` — one
  file per mode, each carrying **exactly** that mode's checks with CHECK-IDs
  copied byte-for-byte (`prd`→CHECK-P01..P15, `tech`→CHECK-T01..T17,
  `specs`→CHECK-S01..S38, `backlog`→CHECK-B01..B27, `impl`→CHECK-I01..I23 incl.
  the Runnability sub-block I21/I22/I23, `epic`→CHECK-E01..E10). No check added,
  dropped, or renumbered (REQ-R1-05).
- `references/findings-template.md` — the three **orchestrator-only** sections
  (Findings Document Template, Example Findings, Epic Mode State Write Detail),
  read only by the orchestrator role at Steps 4/6 (REQ-R1-02).

**Load path.** The `forge-verifier` **leaf** subagent is dispatched with a mode
and reads only `references/verification-checklists/{mode}.md`. The **orchestrator**
(forge-verify SKILL) reads `references/findings-template.md` at Steps 4/6. This
preserves the v0.12.1 dual-role "which role are you?" guard intact (REQ-R1-03):
the leaf never sees orchestrator material, and the split introduces no
self-dispatch.

**Self-check tightening (REQ-R1-04).** The SKILL's Step-3 self-check currently
carries *approximate* totals ("tech ~15" while the file actually holds 17). Each
per-mode file gets an exact, drift-guarded count; the SKILL's expected-count table
is reconciled to the exact per-file totals so "executed N of M" is checked
against the reduced, mode-scoped file — more robust, not weaker.

**Citation/portability (REQ-PORT-01).** Citation fan-out scans **skill bodies**
(`_fan_out_shared_references()` regex `references/([A-Za-z0-9_][A-Za-z0-9_./{}*-]*)`).
All six mode paths **and** `findings-template.md` MUST appear as literal
`references/...` citations **in the forge-verify SKILL body** (not only in the
`forge-verifier` agent file, whose body may not drive fan-out — see OQ-4), so every
file ships to all five adapters. Because the paths contain `/`, they match the
regex character class (`.` and `/` are included), and they are skill-local own-refs
(`skills/forge-verify/references/...`) so they copy verbatim under the per-skill
own-refs step, not the shared-root fan-out — either way, cite them from the body.

**Rejected:** inlining orchestrator material into the forge-verify SKILL body
(at 257/300, +~150 lines blows the cap); keeping one file and slicing by anchor
(the 477-line file still loads into the subagent — fails REQ-R1-01's intent).

### 3.2 R2 — Within-file prelude dedup, conservative scope (REQ-R2-01/02, C-5)

**Decision.** Reduce the 2nd-and-subsequent occurrences of the 3-line `R="$(bash
-c '…forge-root.sh…')"` resolver **only within linearly-read skill bodies**:
`skills/forge/SKILL.md` (5→1 full + 4 compact), `skills/forge-0-epic/SKILL.md`
(5→1+4), `skills/forge-bootstrap/SKILL.md` (4→1+3), `skills/forge-1-prd/SKILL.md`
(2→1+1). **Reference files are excluded** — `shared-conventions.md` (6),
`portable-root.md` (2), and `forge-0-epic/references/edit-mode.md` (2) hold their
preludes inside **independently-invoked recipe blocks** ("invoke this block"),
which a single skill may call in isolation; a "see the block above" pointer would
dangle (this is why aggressive dedup was rejected).

**Two hard constraints drove the scope:**
1. **Shell state does not persist across bash tool calls** — a later block cannot
   consume `$R` set by an earlier one. The compact form is therefore an
   *instruction-text* reduction (what the model reads), not a runtime `$R` reuse;
   the model re-expands the resolver when it executes the later call site, so
   execution behavior at each call site is unchanged (REQ-R2-01).
2. **check-spec-purity Rule 5** (`check_prelude_identity`) fires `VR_PRELUDE_DRIFT`
   whenever the sentinel line `[ -x "$d/scripts/forge-root.sh" ] && exec
   "$d/scripts/forge-root.sh"` appears without the full byte-identical
   `BOOTSTRAP_PRELUDE`. **The compact form MUST omit that sentinel line** so
   Rule 5 does not apply to it.

**Compact form (canonical wording, sentinel-free, within-file only — C-5):**

```
Resolve `$R` via the plugin-root prelude shown at the top of this skill, then run:
python3 "$R/scripts/<script>.py" <args>
```

No cross-file prelude pointer exists in any executable path (REQ-R2-02): the full
prelude remains present once per file. Side benefit: frees ~4 lines in
`forge-0-epic` (292/300) and `forge-bootstrap`, easing cap pressure.

### 3.3 R3 — Conditional process-overview read (REQ-R3-01)

**Decision.** In `skills/forge/SKILL.md`, move the `references/process-overview.md`
read out of unconditional setup into a branch taken only for
"how does the pipeline work / architecture / stage-ordering" questions. Routine
dashboard/status rendering (rank-features + render-status) no longer loads the
143-line file. Pure read-site relocation; the file is unchanged and stays cited
(so it still ships).

### 3.4 R4 — Targeted state verbs, eliminating the per-stage schema read (REQ-R4-01..04)

**Decision.** Add **targeted state-write subcommands** to `forge-session.py`,
replacing every hand-authored `.pipeline-state.json` edit. All seven REQ-R4-04
touch points are covered:

| Subcommand | Touch point | Writes |
|---|---|---|
| `state-enter` | Entry stamp | `stages.{stage}.status=in-progress`, `.startedAt`, top-level `currentStage`, `updatedAt` |
| `state-artifact` | Incremental `artifacts[]` | append to `stages.{stage}.artifacts` (idempotent) |
| `state-complete` | Completion | `status=complete`, `completedAt`, `version` (bump), `basedOnVersions`, `artifacts`; **+ deterministic downstream staleness cascade** |
| `state-note` | `notes` | set top-level `notes` |
| `state-decision` | `deferredDecisions[]` | append a `{question,rationale?,targetStage?,raisedBy,raisedAt,status:open}` item |
| `state-ecr` | `epicChangeRequests[]` | append a `{kind,target,rationale,raisedBy,raisedAt,status:open,blocksCurrent}` item |
| `state-branch` | `branch` | set top-level `branch` |

**Why targeted verbs (not a generic patch).** Chosen in interview: each call is
self-validating, self-documenting, and a clean CI-checkable unit (REQ-MAINT-01);
fully removes hand-authored JSON (the drift-removal benefit that justifies R4 per
PRD §3.4). A generic `state-patch` would leave the model authoring the JSON
fragment, only partially delivering the benefit.

**Deterministic gains folded in.** `state-complete` performs the version bump,
`basedOnVersions` record, and the **downstream staleness cascade** (mark
forge-3-specs..forge-6-docs `stale` when their `basedOnVersions` reference an
older version of the just-completed stage) — logic that is model prose today and
becomes deterministic.

**Conventions (verified, must match).** New handlers follow the script verbatim:
argparse subparser registered in `_build_parser`-equivalent + `if args.cmd ==`
dispatch in `main()`; `--json`/`dest="json_output"` emitting
`json.dumps(payload, indent=2, ensure_ascii=False)`; exit codes **0 (ok) / 2
(usage or I/O error)** — the forge-session convention (note: *not* the 0/1/2
finding convention of `epic-manifest.py`); errors degrade to data under the
top-level `try/except`. State is read via the same resolve→load→mutate→write-back
path, always refreshing `updatedAt`, writing atomically.

**Schema stays source of truth (REQ-R4-03).** The verbs emit conforming state;
`pipeline-state-schema.json` is unchanged and remains the CI/validation authority.
A stdlib drift guard (§8) asserts each verb's output validates against it.

**Interactive-protocol invariant (C-1, REQ-BEHAV-02).** R4 changes only the
*JSON-authoring mechanics*. The surrounding Stage-Entry Guard classification,
Branch Setup/Reconciliation prompts, the "offer a note" statement, and the
two-commit Git Commit Protocol (never `--amend`) keep their exact prose and
turn structure — the verb invocation slots in where the "edit the JSON" step
was. The entry stamp remains **uncommitted** until the stage's exit commit.

**Note on the two-commit protocol.** `state-complete` sets `commitHash: null`
(Commit 1). Recording the real hash (Commit 2) still uses a distinct one-line
write — either a second `state-complete --commit-hash <h>` invocation or a
`state-set`-style hash write; the tech decision is to give `state-complete` an
optional `--commit-hash` so the follow-up commit reuses the same verb. This
preserves the "hash points at the artifact commit, never an amend" guarantee.

### 3.5 R5 — Resolved loop-runner config subcommand (REQ-R5-01/02)

**Decision.** Add `forge-session.py effective-config` that:
1. reads `references/forge-config-schema.json` and extracts
   `properties.loopRunner.properties.*.default` (verified: **all 22 fields carry a
   machine-readable `default` keyword**),
2. deep-merges the user's `loopRunner` block (via the existing `_load_config`,
   line 526) over those defaults,
3. emits the resolved block as JSON (`--json`) or a readable summary.

The **script** reads the schema, so the **model** never does (REQ-R5-01 satisfied);
the schema stays the single source of truth (REQ-R4-03), there is **no hardcoded
duplication**, and default resolution is deterministic — eliminating the
"model mis-merged the defaults" error class (REQ-R5-02). Precedent:
`test_config_defaults_parity.py` already stdlib-parses these same defaults.
No `jsonschema` (C-2): plain `json.load` + dict access.

**Consumers.** `forge-5-loop` and `forge-4-backlog` call `effective-config` in
place of reading the ~2k-word schema for defaults.

**Rejected:** hardcoding the 22 defaults in Python — needless duplication of a
schema that is already machine-readable.

### 3.6 R6 — Runner-contract always/conditional split (REQ-R6-01/02/03)

**Decision.** Split `skills/forge-5-loop/references/runner-contract.md` (341
lines) by moving its three **agent-conditional** sections into a new
`skills/forge-5-loop/references/agent-selection.md`:

- `## Agent selection (Step 2d)` (L23–82)
- `### Claude-only model-alias guard (Step 2d, sub-step d-model)` (L83–111)
- `## Optional flags catalog (Step 2d, rauf)` (L153–168)

`runner-contract.md` keeps the **always-loaded** sections: Model-selection
precedence, Run mode (rauf), Launch detail, Arm a Monitor, React to events,
Inform-user template (REQ-R6-01).

**Load gate (REQ-R6-02).** `agent-selection.md` is cited **only at the
forge-5-loop capability gate** (SKILL body line ~174, "everything below applies
only when `loopRunner.agentArgument` is present"), so it loads only then. The
optional-flags catalog moves with it (reachable-but-not-default), co-located
because it is surfaced only during the same Step-2d detail.

**Cap constraint (REQ-R6-03).** `forge-5-loop` SKILL is **at 300/300**. R6's SKILL
edits are a strict **1:1 citation swap** (the existing "read
`references/runner-contract.md`" pointers at lines 165/174 that reference agent
material re-point to `references/agent-selection.md`) — **zero net lines added**,
no runner-contract text pushed back into the body. `agent-selection.md` is a
skill-local own-ref (copied verbatim), so it ships without fan-out ambiguity, but
the citation still gives fan-out a discoverable path.

### 3.7 Delivery, sequencing, portability (REQ-DELIV-01, REQ-PORT-01..03, C-7)

Each of R1–R6 lands as its **own PR/change**, revertible without touching the
others (REQ-DELIV-01, SC-6). Sequence per the audit: **R1 + R2 + R3** (quick
wins) → **R5** → **R4** (largest surface) → **R6**. R5 precedes R4 because it is
lower-risk and exercises the "add a forge-session subcommand + stdlib schema
drift-guard" pattern that R4 then reuses at larger scale.

Every new/moved file is cited by path from ≥1 skill body (REQ-PORT-01), contains
no Claude-only tokens — no literal `/clear`, no Claude-only tool names
(REQ-PORT-02) — and all five adapters regenerate with fixtures refreshed via the
minimal-canon scratch-build + `command cp -f` procedure (REQ-PORT-03, C-3).
**Releases are out of scope** (C-7): no backlog release items.

## 4. Data Model

No persistent data-model change. The two schemas are **unchanged in content**:

- `pipeline-state-schema.json` (191 lines): top-level `feature`, `createdAt`,
  `updatedAt`, `currentStage`, `stages`, `pipelineStatus` (required); `epic`,
  `branch`, `notes`, `epicChangeRequests[]`, `deferredDecisions[]` (optional).
  `stages` values are `stageEntry` (production) or `verifyEntry` (verify) shapes.
  The R4 verbs are the new *authoring path* for this same shape.
- `forge-config-schema.json` (236 lines): `loopRunner` object, all 22 fields with
  `default` keywords — the R5 subcommand's default source.

## 5. API Design

New `forge-session.py` subcommands (exit **0/2**, `--json` on all; degrade-to-data):

```
state-enter     --feature F --stage S [--specs-dir D] [--json]
state-artifact  --feature F --stage S --path P [--specs-dir D] [--json]
state-complete  --feature F --stage S --version N [--based-on K=V]...
                --artifact P... [--commit-hash H] [--specs-dir D] [--json]
state-note      --feature F --note TEXT [--specs-dir D] [--json]
state-decision  --feature F --question Q --raised-by R [--rationale X]
                [--target-stage T] [--specs-dir D] [--json]
state-ecr       --feature F --kind K --target T --rationale X --raised-by R
                --blocks-current BOOL [--specs-dir D] [--json]
state-branch    --feature F --branch B [--specs-dir D] [--json]
effective-config [--config ./forge.config.json] [--schema <path>] [--json]
```

Each `state-*` verb resolves the feature dir (reusing the existing resolver),
loads `.pipeline-state.json`, applies its mutation, refreshes `updatedAt`, and
writes back; `--json` echoes the resulting state (or the mutated slice) for the
caller to confirm. `effective-config` reads config + schema and prints the
resolved `loopRunner`.

## 6. Integration Points

**Depends on (reads/modifies existing code):**

1. **`scripts/forge-session.py`** (1,866 lines) — the host for R4+R5. Verified
   integration surface: `_load_config(config_path: Path) -> dict` (line 526,
   returns `{}` on error, callers `.get(k, default)`); argparse subparsers +
   `if args.cmd == …` dispatch in `main()`; `--json`→`dest="json_output"`;
   exit **0/2**; top-level `try/except` degrade-to-data. Existing subcommands
   (`rank-features`, `context-usage`, `doctor`, `discover-feature`,
   `reconcile-branch`, `check-epic-base`, `stage-exit`) are the pattern to mirror.
2. **`references/pipeline-state-schema.json`** — data contract the R4 verbs must
   satisfy; unchanged; the R4 stdlib drift guard reads it.
3. **`references/forge-config-schema.json`** — R5 reads `properties.loopRunner`
   defaults; unchanged.
4. **`skills/forge-verify/SKILL.md`** — Step 2 mode-dispatch and Step 3 self-check
   re-cite the six per-mode files; Steps 4/6 re-cite `findings-template.md`.
   Dual-role guard preserved (REQ-R1-03).
5. **`agents/forge-verifier.md`** — the leaf agent's dispatch prompt must name the
   mode so it reads only `verification-checklists/{mode}.md`. (Read-only agent;
   no tool change.)
6. **`skills/forge-5-loop/SKILL.md`** — 1:1 citation swap only; **at the 300-line
   cap**, so verified line-neutrality is mandatory.
7. **`references/shared-conventions.md`** — Stage-Entry Guard (entry stamp +
   incremental artifacts), Branch Setup (`branch` write), and the per-stage
   completion instructions switch to state-verb calls. **Prose/prompts unchanged.**
8. **State-writing skills** (`forge-0-epic`, `forge-1-prd`, `forge-2-tech`,
   `forge-3-specs`, `forge-4-backlog`, `forge-verify`) — each stage's
   "Write pipeline state" step swaps hand-authored JSON for the matching verb(s).
9. **`scripts/build-adapters.py`** — **no code change expected.** Its citation
   fan-out + own-refs copy + `RUNTIME_HELPERS` (which already includes
   `forge-session.py`) carry the new subcommands and files automatically —
   *provided* every new reference file is cited by path from a skill body
   (the load-bearing precondition, REQ-PORT-01).
10. **`scripts/check-spec-purity.py`** — **no change**; it is a *constraint*:
    Rule 5 (prelude byte-identity) bounds R2's compact form; Rule 4 (≤300 lines)
    bounds forge-5-loop.

**Imported-from by:** nothing outside the pipeline — this is internal
instruction/script refactoring. "Consumers" are the skills and the adapter build.

**In-progress-feature conflicts:** none. `epic-orchestration` and
`forge-bootstrap` are both fully `complete`; this feature does not touch their
spec dirs.

**Data flow (R4 example):** skill step → `python3 "$R/scripts/forge-session.py"
state-complete --feature … --stage … --version …` → resolve dir → load state →
mutate + cascade staleness → write back + `updatedAt` → `--json` echo → skill
proceeds to Git Commit Protocol (unchanged).

## 7. Error Handling

- **R4/R5 subcommands** inherit forge-session's contract: unreadable I/O, missing
  feature dir, or malformed args → **exit 2** with a plain `Error:` line on
  stderr; all recoverable conditions **degrade to data at exit 0** under the
  top-level `try/except`. No new exit-code semantics (stays 0/2, distinct from
  epic-manifest's 0/1/2).
- **Schema conformance:** the R4 verbs construct state programmatically, so
  malformed state is a code bug caught by the stdlib drift guard in CI — not a
  runtime user error.
- **R5 default resolution:** if the schema is unreadable, `effective-config`
  surfaces exit 2 (deterministic failure) rather than silently emitting partial
  defaults — the loop stages then fall back to their existing behavior.
- **R2:** no runtime error surface — instruction-text change only; the resolver
  the model executes is unchanged.
- **R1/R6:** no runtime error surface; a mis-split (missing check / dropped
  section) is caught by the drift guards, not at runtime.

## 8. Testing Approach

Stdlib-only pytest under `tests/` (CI's `python3 -m pytest tests`), extending the
existing drift-guard discipline (`test_stage_exit_protocol.py` style: `REPO_ROOT`
relative paths, assert against `skills/` canon never `adapters/`). New/extended
guards (REQ-MAINT-01, SC-4):

- **R1** — a guard asserts each `verification-checklists/{mode}.md` contains
  exactly its expected CHECK-IDs (P/T/S/B/I/E ranges), no cross-mode leakage, and
  that the forge-verify SKILL's expected-count table matches the per-file totals.
  Also assert `findings-template.md` holds the three orchestrator sections and
  that no mode file contains them.
- **R2** — assert the compact form is **sentinel-free** (no
  `check_prelude_identity` trigger) and that each targeted skill body retains
  **exactly one** full `BOOTSTRAP_PRELUDE`; assert reference files
  (`shared-conventions.md`, `portable-root.md`, `edit-mode.md`) are untouched.
- **R3** — assert `process-overview.md` is cited (still ships) and read only under
  the conditional branch (no unconditional read line remains).
- **R4/R5** — a **stdlib structural validator** (reusing `epic-manifest.py`'s
  hand-rolled `_schema_findings()` pattern — **no `jsonschema`**, C-2) asserts each
  state verb's emitted state validates against `pipeline-state-schema.json`, and
  `effective-config`'s output validates against `forge-config-schema.json`
  (REQ-R4-03 test-enforced). Cover every verb + the staleness cascade.
- **R6** — assert `agent-selection.md` is cited **at the forge-5-loop capability
  gate**, that the always-vs-conditional split preserves **every** original
  `runner-contract.md` section (mirroring the R1 section-count assertion), and
  that forge-5-loop body stays ≤300 lines.
- **Catch-all (REQ-MAINT-01):** every invoke-point citation names an existing
  file; every new reference file is cited by ≥1 skill body.
- **Portability:** `test_build_adapters.py` snapshot passes after fixture refresh;
  existing `test_config_defaults_parity.py`, `test_pipeline_state_schema.py`,
  `test_stage_exit_protocol.py` stay green.

**Measurement (REQ-PERF-01/02, REQ-OBS-01/02, SC-1/2):** before adopting any
numeric target, **re-measure baselines from real dogfood transcripts**
(consumption-data-refresh runs) and **record the method** (per-invocation
instruction-token count via transcript inspection) so before/after is
reproducible. Each shipped R must show a measured net reduction on its targeted
invocation vs the re-measured baseline. A frontmatter char/word-count assertion +
a `SessionStart`-hook empty-common-path check guard the "no increase in
always-loaded surface" bar (REQ-PERF-02) as a green/red test. For R4, confirm the
actual per-stage schema-read frequency from transcripts and scale the *reported*
saving accordingly (REQ-OBS-02) — this affects reporting, not whether R4 ships.

**Local gate before every push:** `bash scripts/validate.sh` (regen-diff +
purity + traceability + installer) **and** `ruff check scripts/ eval/` (CI-only,
C-2).

## 9. Dependencies

- **External:** none added. Python 3.10+ stdlib only (C-2: no `jsonschema`). Node
  20 only for the installer build (unchanged).
- **Internal:** `forge-session.py`, `epic-manifest.py` (pattern precedent for the
  stdlib validator), `build-adapters.py` (citation fan-out), `check-spec-purity.py`
  (Rule 4/5 constraints), the two schemas.
- **Version constraints:** none new.

## 10. Open Technical Questions

- **OQ-1 (was PRD OQ-1/OBS-02):** actual per-stage read frequency of
  `pipeline-state-schema.json` in real transcripts — resolve from
  consumption-data-refresh dogfood evidence at implementation time; scales R4's
  *reported* saving only.
- **OQ-2 (PRD OQ-3):** re-measured baseline token counts per invocation at
  implementation time (LOAD-MAP figures have drifted since b9f0871).
- **OQ-3 — `state-complete` follow-up-commit shape:** give `state-complete` an
  optional `--commit-hash` (reuse one verb) vs a tiny separate `state-set`-style
  hash writer. Leaning `--commit-hash` (fewer verbs); finalize in specs.
- **OQ-4 — does citation fan-out scan agent bodies?** `_fan_out_shared_references()`
  scans *skill* bodies; whether `agents/*.md` bodies also drive fan-out is
  unconfirmed. **Mitigation is already the plan:** cite all R1 mode files from the
  forge-verify **SKILL** body, so portability does not depend on the answer.
  Confirm during R1 implementation.
```
