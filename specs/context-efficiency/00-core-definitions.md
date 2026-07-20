# 00 — Core Definitions

> The shared contracts every other document in this suite builds on. Because
> `context-efficiency` is a **behavior-preserving instruction-token
> optimization** of the forge pipeline itself (tech-spec §1), its "type system"
> is not a new domain model — it is (a) the `forge-session.py` script
> conventions the R4/R5 subcommands must follow verbatim, (b) the
> `.pipeline-state.json` JSON shapes the R4 verbs must emit, (c) the
> compact-prelude canonical wording R2 introduces, (d) the citation /
> portability contract every moved file must satisfy, and (e) the CHECK-ID
> inventory R1 must preserve exactly. Every later doc references these by
> section rather than re-deriving them.
>
> Nothing here changes runtime behavior. These are the definitions that keep the
> six independently-revertible units (R1–R6) consistent with each other and with
> the existing scripts.

## Requirement Coverage

| REQ ID | Requirement | Section |
|--------|-------------|---------|
| REQ-R4-01 | Stages no longer read the full state schema per invocation | §3 (verbs replace hand-authored JSON), §4 (state shapes) |
| REQ-R4-03 | Schema remains CI source of truth | §4 (shapes restate, not replace, the schema) |
| REQ-R4-04 | All seven state-write touch points covered | §5 (touch-point inventory) |
| REQ-R5-01 | Resolved loopRunner config without reading full config schema | §6 (effective-config contract) |
| REQ-R1-05 | Every mode's CHECK-IDs preserved exactly | §7 (CHECK-ID inventory) |
| REQ-R2-01/02 | Within-file prelude dedup, no cross-file pointer | §8 (compact-prelude wording) |
| REQ-PORT-01/02 | New/moved files citation-discoverable + host-neutral | §9 (portability contract) |
| REQ-BEHAV-01/02 | Zero behavioral diff; frozen protocols verbatim | §2 (prime directive), §10 (invariants) |

---

## 1. Scope & Non-Goals

This document defines **shared contracts only**. It does not specify any single
unit's edits — those live in:

- `02-verify-checklist-split.md` (R1)
- `03-state-verbs.md` (R4)
- `04-effective-config.md` (R5)
- `05-instruction-relocations.md` (R2, R3, R6)
- `06-testing-strategy.md` (all units' drift guards + measurement)

`01-architecture-layout.md` owns the file-move manifest, the `forge-session.py`
module layout, and the delivery sequencing.

**Non-goals** (from PRD §6): no restructuring of `shared-conventions.md` (R7,
deferred); no change to Epic Context Injection dep-spec loading (W1); no change
to any interactive protocol, only relocation of its text.

## 2. The Prime Directive (C-1, REQ-BEHAV-01/02)

Every change in this feature is exactly one of three kinds:

1. **Relocation** — moving instruction text from one file/site to another
   (R1, R3, R6).
2. **Dedup** — reducing a repeated block to a compact reference form within the
   same file (R2).
3. **Script-extraction** — moving JSON-authoring or default-merging work out of
   model prose into deterministic `forge-session.py` code (R4, R5).

**Never a rewording of interactive-protocol content.** The `AskUserQuestion`
turn structure, Decision Support protocol, Branch Setup/Reconciliation prompts,
Stage-Entry Guard / Stage-Completion Re-check classification, the two-commit Git
Commit Protocol (never `--amend`), verify gates, stage-exit directive handling,
and anti-fabrication guards keep their exact prose and turn structure. §10
lists the invariants each unit must preserve. If moving a sentence forces a
wording change, that MUST be flagged in review, never silently adapted
(REQ-BEHAV-02).

## 3. `forge-session.py` script conventions (R4 + R5 host)

The R4 state verbs and the R5 `effective-config` subcommand are added to the
existing `scripts/forge-session.py` (1,866 lines today; verified integration
surface, tech-spec §6.1). New handlers MUST mirror the script verbatim:

### 3.1 Structural conventions

| Convention | Existing precedent (verified) | Requirement |
|---|---|---|
| Subcommand registration | `sub.add_parser("stage-exit", …)` in `main()` (L1750) | Register each new verb as an `argparse` subparser in `main()`. |
| Dispatch | `if args.cmd == "stage-exit":` chain in `main()` (L1840) | Add an `if args.cmd == "<verb>":` branch in the same chain. |
| JSON flag | `add_argument("--json", action="store_true", dest="json_output")` | Every new verb accepts `--json`; the dest is `json_output`. |
| JSON emission | `print(json.dumps(payload, indent=2, ensure_ascii=False))` | Same call, same kwargs, to stdout. |
| Human output | dedicated `_print_<verb>(payload)` helper | Provide a readable non-`--json` printer per verb. |
| Specs dir | `add_argument("--specs-dir", default="./specs")` | Same default and flag name. |

### 3.2 Exit-code contract (**0 / 2**, NOT 0/1/2)

`forge-session.py` uses the **two-code** convention — distinct from
`epic-manifest.py`'s 0/1/2 (00-core-definitions of *that* suite). New verbs MUST
follow forge-session:

```
0 = ok (mutation applied / config resolved)
2 = usage error or I/O error (missing file, unreadable, unsafe path, bad args)
```

There is **no exit 1**. All recoverable conditions **degrade to data** and still
exit 0 under the single top-level handler in `main()` (verified, L1857–1862):

```python
    except UsageError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
```

`UsageError` (defined L168) is raised for bad arguments; `OSError` covers I/O.
Diagnostic text goes to **stderr**; the JSON payload or resolved value goes to
**stdout**, so a caller can capture stdout cleanly.

### 3.3 State read/write path (new for R4)

`forge-session.py` today only **reads** state via `_read_state(state_path)`
(L177), which downgrades a missing/corrupt file to `{}`. The R4 verbs are the
**first state writers** in this script, so they introduce a shared write path
that every verb reuses:

```python
def _write_state(state_path: Path, state: dict) -> None:
    """Atomically write a `.pipeline-state.json` (temp file + os.replace).

    Mirrors epic-manifest.py's atomic_write: write to a sibling temp file in the
    same directory, flush+fsync, then os.replace() onto the target so a crash
    can never leave a half-written state file (REQ-ROBUST-03 pattern).
    """
    tmp = state_path.with_suffix(state_path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    os.replace(tmp, state_path)
```

Every `state-*` verb follows the same **resolve → load → mutate → refresh
`updatedAt` → write-back** sequence (full detail in `03-state-verbs.md §3`):

```python
state_dir = _resolve_feature_dir(specs_dir, feature, epic)   # existing, L1416
state_path = state_dir / PIPELINE_STATE_FILENAME
state = _read_state(state_path)          # {} if absent — verbs create-or-update
# ... verb-specific mutation ...
state["updatedAt"] = _now_iso()          # ALWAYS refresh on mutation
_write_state(state_path, state)
```

`_now_iso()` is a small UTC-ISO-8601 formatter the R4 work **introduces** — the
script today inlines `datetime.now(timezone.utc)` rather than exposing a named
helper (verified: no `_now_iso` exists yet), so R4 adds one for the verbs to
share (`03-state-verbs.md §3.1`). `_write_state` needs `import tempfile` if it
uses the `mkstemp`+`fsync` form; the zero-new-import `with_suffix` form shown
above avoids that. `PIPELINE_STATE_FILENAME` and `_resolve_feature_dir` already
exist and MUST be reused, not re-implemented.

### 3.4 stdlib-only (C-2)

No `jsonschema`, no third-party imports. The R4/R5 verbs and their drift guards
use plain `json` + dict access only. Precedent: `test_config_defaults_parity.py`
already stdlib-parses the schema defaults; `epic-manifest.py`'s hand-rolled
`_schema_findings()` is the pattern the R4/R5 drift validator reuses
(`06-testing-strategy.md §4`).

## 4. Pipeline-state JSON shapes (what the R4 verbs emit)

`references/pipeline-state-schema.json` (191 lines, draft-07) is **unchanged**
and **remains the CI source of truth** (REQ-R4-03). The shapes below are
restated here **only** so the verbs can be specified against them — the schema,
not this table, is authoritative. A drift guard asserts each verb's output
validates against the schema (`06-testing-strategy.md §4`).

### 4.1 Top-level object

Required: `feature`, `createdAt`, `updatedAt`, `currentStage`, `stages`,
`pipelineStatus`. Optional: `epic`, `branch`, `notes`, `epicChangeRequests[]`,
`deferredDecisions[]`.

- `currentStage` — enum incl. all production + verify stage ids, plus
  `complete`. Set by `state-enter` to the entering stage's id ("where the
  pipeline IS", O1).
- `pipelineStatus` — `active | paused | abandoned` (default `active`).
- `branch` — set by `state-branch`.
- `notes` — set by `state-note`.

### 4.2 `stages.{stage}` — `stageEntry` (production stages)

```jsonc
{
  "status": "pending | in-progress | complete | stale",   // required
  "version": 2,                        // integer; bumped by state-complete
  "artifacts": ["PRD.md", "..."],      // string[]; appended by state-artifact
  "startedAt": "2026-07-20T03:30:00Z", // ISO-8601 or null
  "completedAt": "…" | null,
  "commitHash": "…" | null,            // null at state-complete; set via --commit-hash
  "basedOnVersions": { "forge-1-prd": 2 }  // {stageId: int}
}
```

The verify stages use the separate `verifyEntry` shape (`status ∈ {pending,
passed, findings-reported, findings-applied, skipped}`, plus `findingsFile`,
`findingsCount`, `verifiedAt`, `fixedAt`, `commitHash`, `verifiedStageVersion`).
**R4 does not add a verb for verify entries** — forge-verify/forge-fix keep
their existing write path; R4 covers only the production `stageEntry` touch
points plus the two array types below.

### 4.3 `deferredDecisions[]` item (emitted by `state-decision`)

```jsonc
{
  "question": "…",        // required
  "rationale": "…",       // optional
  "targetStage": "forge-2-tech",  // optional; enum of production stages
  "raisedBy": "forge-1-prd",      // required; enum forge-1-prd..forge-4-backlog
  "raisedAt": "…",        // required; date-time
  "status": "open"        // required; open|addressed|dismissed (recorder writes "open")
}
```

### 4.4 `epicChangeRequests[]` item (emitted by `state-ecr`)

```jsonc
{
  "kind": "add-feature | redep | move-boundary | split",  // required
  "target": "…",          // required
  "rationale": "…",       // required
  "blocksCurrent": true,  // required; boolean — drives stage-exit routing
  "raisedBy": "forge-1-prd | forge-2-tech",  // required
  "raisedAt": "…",        // required; date-time
  "status": "open"        // required; open|applied|dismissed (recorder writes "open")
}
```

`additionalProperties: false` on both array item shapes — the verbs MUST emit
exactly these keys and no others.

## 5. State-write touch-point inventory (REQ-R4-04)

R4 is **not acceptable as a partial extraction** — every hand-authored state
write in the pipeline must route through a verb. The seven touch points and
their owning verb (full contracts in `03-state-verbs.md`):

| # | Touch point | Where it fires today | Verb |
|---|---|---|---|
| 1 | Entry stamp | Stage-Entry Guard (shared-conventions.md) | `state-enter` |
| 2 | Incremental `artifacts[]` | after each artifact write (e.g. forge-3-specs per spec file) | `state-artifact` |
| 3 | Completion (+ version bump, basedOnVersions, staleness cascade) | each stage's "Update Pipeline State" step | `state-complete` |
| 4 | `notes` | stage-exit "offer a note" step | `state-note` |
| 5 | `deferredDecisions[]` | deferred-decisions rule (stage-exit-protocol.md) | `state-decision` |
| 6 | `epicChangeRequests[]` | epic-backflow recording (forge-1-prd/forge-2-tech) | `state-ecr` |
| 7 | `branch` | Branch Setup / Branch Reconciliation (shared-conventions.md) | `state-branch` |

The commit-hash follow-up write (Commit 2 of the Git Commit Protocol) reuses
`state-complete --commit-hash <h>` (tech-spec §3.4 note; finalized in
`03-state-verbs.md §4`).

## 6. `effective-config` contract (R5)

`effective-config` resolves the `loopRunner` block deterministically so no model
ever reads the ~2k-word `forge-config-schema.json` for defaults (REQ-R5-01):

- **Input:** `--config` (default `./forge.config.json`), `--schema` (default the
  bundled `references/forge-config-schema.json`), `--json`.
- **Algorithm:** read `properties.loopRunner.properties.*.default` from the
  schema (verified: **all 22 fields carry a machine-readable `default`**), then
  deep-merge the user's `loopRunner` block (via the existing `_load_config`,
  L526) over those defaults.
- **Output:** the fully-resolved 22-field `loopRunner` object as JSON (`--json`)
  or a readable summary.
- **Exit:** 0 on success; **2** if the schema is unreadable (deterministic
  failure — the loop stages then fall back to existing behavior, tech-spec §7).

The **script** reads the schema, so the **model** never does; the schema stays
the single source of truth (REQ-R4-03), with no hardcoded duplication of the 22
defaults. Full contract in `04-effective-config.md`.

## 7. CHECK-ID inventory (R1 must preserve exactly — REQ-R1-05)

The 477-line `verification-checklists.md` splits into six per-mode files. Every
CHECK-ID is copied **byte-for-byte**; none added, dropped, or renumbered. The
authoritative counts (verified against the current source, not the SKILL's
approximate self-check table):

| Mode | File | CHECK-IDs | Count |
|------|------|-----------|-------|
| prd | `verification-checklists/prd.md` | CHECK-P01..P15 | **15** |
| tech | `verification-checklists/tech.md` | CHECK-T01..T17 | **17** |
| specs | `verification-checklists/specs.md` | CHECK-S01..S38 | **38** |
| backlog | `verification-checklists/backlog.md` | CHECK-B01..B27 | **27** |
| impl | `verification-checklists/impl.md` | CHECK-I01..I23 (incl. Runnability I21/I22/I23) | **23** |
| epic | `verification-checklists/epic.md` | CHECK-E01..E10 | **10** |
| | | **Total** | **130** |

> **Reconciliation note (REQ-R1-04):** the forge-verify SKILL's current Step-3
> self-check carries *approximate* totals ("tech: ~15 checks" while the file
> holds **17**; verified). R1 reconciles the SKILL's expected-count table to
> these exact per-file totals so "Executed N of M" is checked against the
> reduced, mode-scoped file — more robust, not weaker. See
> `02-verify-checklist-split.md §4`.

The three **orchestrator-only** sections (Findings Document Template,
Example Findings, Epic Mode State Write Detail — source lines 325, 375, 409)
move to `references/findings-template.md` and MUST NOT appear in any per-mode
file (REQ-R1-02).

## 8. Compact-prelude canonical wording (R2 — REQ-R2-01/02, C-5)

The full plugin-root resolver prelude (the `R="$(bash -c '…forge-root.sh…')"`
block ending in the sentinel line
`[ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"`) remains
**verbatim on its first occurrence** in every file. Second-and-subsequent
occurrences **within a linearly-read skill body only** reduce to this canonical
compact form:

```
Resolve `$R` via the plugin-root prelude shown at the top of this skill, then run:
python3 "$R/scripts/<script>.py" <args>
```

**Two hard constraints (tech-spec §3.2):**

1. **Shell state does not persist across bash tool calls.** The compact form is
   an *instruction-text* reduction (what the model reads), not runtime `$R`
   reuse — the model re-expands the resolver when it executes the later call
   site, so execution behavior at each call site is unchanged (REQ-R2-01).
2. **The compact form MUST be sentinel-free.** `check-spec-purity.py` Rule 5
   (`check_prelude_identity`) fires `VR_PRELUDE_DRIFT` whenever the sentinel
   line appears without the full byte-identical `BOOTSTRAP_PRELUDE`. Omitting
   the sentinel line means Rule 5 does not apply to the compact form.

**Within-file only (C-5, REQ-R2-02):** no executable path may depend on a
cross-file "see another file for the prelude" pointer. Reference files are
**excluded** because their preludes sit inside independently-invoked recipe
blocks (see §9 and `05-instruction-relocations.md §1`).

## 9. Portability / citation contract (REQ-PORT-01/02/03)

Every new or moved reference file MUST be **citation-discoverable** and
**host-neutral**, or it will not ship to the four non-Claude adapters.

- **Citation-discoverable (REQ-PORT-01):** `build-adapters.py`'s
  `_fan_out_shared_references()` scans **skill bodies** with the regex
  `references/([A-Za-z0-9_][A-Za-z0-9_./{}*-]*)`. Every new file's path
  (`verification-checklists/prd.md`, …, `findings-template.md`,
  `agent-selection.md`) MUST appear as a literal `references/...` citation **in
  a skill body**. Paths containing `/` match because the class includes `.` and
  `/`. Skill-local own-refs (`skills/<skill>/references/...`) copy verbatim
  under the per-skill own-refs step; either way, **cite from the body**.
  - **OQ-4 mitigation (tech-spec §10):** it is unconfirmed whether fan-out also
    scans `agents/*.md` bodies. R1 therefore cites all six mode files **and**
    `findings-template.md` from the **forge-verify SKILL body**, never relying
    on the `forge-verifier` agent body — so portability does not depend on the
    answer.
- **Host-neutral (REQ-PORT-02):** moved content MUST NOT contain Claude-only
  tokens — no literal `/clear`, no Claude-only tool names. The shared-refs
  resolution gap (#122/#132) is the cautionary tale.
- **Regenerates cleanly (REQ-PORT-03):** all five adapters (claude, gemini,
  codex, cursor, copilot) regenerate and fixtures refresh via the minimal-canon
  scratch-build + `command cp -f` procedure (C-3), never a copy of a real
  adapter.

## 10. Frozen-protocol invariants (per unit)

Each unit MUST preserve, verbatim, the protocols it touches. The drift guards in
`06-testing-strategy.md` enforce these mechanically.

| Unit | Invariant that MUST NOT change |
|------|--------------------------------|
| R1 | forge-verify dual-role "which role are you?" guard (v0.12.1); leaf never sees orchestrator material; every CHECK-ID preserved. |
| R2 | Every call site still resolves the plugin root independently; exactly one full `BOOTSTRAP_PRELUDE` per edited skill body; compact form sentinel-free. |
| R3 | The navigator's status/dashboard path is byte-identical; only the *read site* of `process-overview.md` moves behind the "how does the pipeline work" branch. |
| R4 | Stage-Entry Guard classification, Branch Setup/Reconciliation prompts, "offer a note" statement, two-commit Git Commit Protocol (never `--amend`), entry stamp stays uncommitted until the exit commit. Only the "edit the JSON" mechanic changes. |
| R5 | forge-5-loop / forge-4-backlog default resolution produces the same effective config the model would have merged by hand. |
| R6 | Every original `runner-contract.md` section still reachable; `agent-selection.md` loads only at the `loopRunner.agentArgument` gate; forge-5-loop body stays ≤300 lines. |

## Dependencies

None — this is the foundation document. Every other document in the suite
depends on it.

## Verification

- [ ] The CHECK-ID counts in §7 match `grep -oE "CHECK-X[0-9][0-9]"` on the
      current `verification-checklists.md` (P15/T17/S38/B27/I23/E10 = 130).
- [ ] The state shapes in §4 validate against `pipeline-state-schema.json`
      unchanged (no schema edit).
- [ ] All 22 `loopRunner` fields carry a `default` in `forge-config-schema.json`
      (§6 premise).
- [ ] The compact-prelude form (§8) contains no `forge-root.sh` sentinel line.
- [ ] The forge-session exit-code contract (§3.2) is 0/2 with no exit-1 branch.
