# Epic Orchestration — Technical Specification

> Based on PRD v1 (commit `e69b7fe`, 7 verification findings applied). Every decision below traces to a PRD requirement ID. The PRD answers WHAT; this spec answers HOW.

## 1. Overview

Epic Orchestration adds a **named grouping of related forge features** with declared dependencies, a shared contract document, and prompted thread-of-execution handoff — without changing how a standalone feature flows through the pipeline (REQ-COMPAT-01/02/03).

Key architectural decisions:

1. **A deterministic Python helper (`scripts/epic-manifest.py`) is the manifest's read/validate/write core.** All logic that must be repeatable and correct — acyclicity (REQ-EPIC-05), corrupt-manifest validation (REQ-ROBUST-02), atomic writes (REQ-ROBUST-03), global name uniqueness (REQ-DIR-04), path containment (REQ-SEC-02), name→directory resolution (REQ-DIR-03), and live status derivation (REQ-STATE-02) — lives in this script, mirroring the existing `scripts/validate-traceability.py` pattern. Skills never eyeball a dependency graph for cycles.
2. **The manifest (`epic-manifest.json`) is the single machine-readable source of truth** for membership, dependency edges, per-feature charters, and structured `exposes`/`consumes` contracts. `EPIC.md` is the human-readable narrative that mirrors those contracts as prose plus rationale (REQ-EPIC-03).
3. **Per-feature status is never cached in the manifest** — it is recomputed from each feature's own `.pipeline-state.json` at read time (REQ-STATE-02).
4. **Name→directory resolution is centralized** in a new `shared-conventions.md` block that every stage skill references and that delegates to the helper, so flat (`{specsDir}/{feature}/`) and nested (`{specsDir}/{epic}/{feature}/`) layouts both resolve from a bare feature name (REQ-DIR-03), with standalone features behaving exactly as today.
5. **Epic support is purely additive**: a new `forge-0-epic` stage, additive schema fields, and conditional epic-aware blocks gated on epic membership. When no epic is involved, every existing flow is byte-for-byte unchanged (REQ-COMPAT-01).

## 2. Module Structure

This is a prose/markdown Claude Code plugin; deterministic logic lives in Python/Bash helpers. Stack confirmed as **prose plugin + Python helpers** (generic, language-neutral spec conventions).

### 2.1 New files

```
skills/forge-0-epic/SKILL.md                  # epic-creation + edit stage (REQ-EPIC-01..06)
scripts/epic-manifest.py                      # deterministic manifest core (Python 3, stdlib only)
references/epic-manifest-schema.json          # JSON Schema for epic-manifest.json (REQ-EPIC-02)
tests/                                         # pytest suite + fixture epic trees for the helper
  test_epic_manifest.py
  fixtures/…                                   # valid, cyclic, dup-name, path-escape, corrupt, status-derivation trees
```

### 2.2 Modified files

| File | Change | Reqs |
|------|--------|------|
| `references/shared-conventions.md` | Add **"Feature Directory Resolution"** block (delegates to `epic-manifest.py resolve`); add **"Epic Context Injection"** block (load EPIC.md + charter + direct completed deps). | REQ-DIR-03, REQ-CTX-01/02 |
| `references/pipeline-state-schema.json` | Add optional `epic` back-pointer field; add `forge-0-epic` + `forge-verify-epic` to `currentStage` enum and `stages` keys. | REQ-STATE-01, REQ-VERIFY-01 |
| `skills/forge/SKILL.md` | Epic dashboard view (REQ-VIS-01); 2-tier no-arg discovery with rollup (REQ-VIS-02); epic lifecycle verbs (REQ-ORCH-05); resolve nested names. | REQ-VIS-01/02, REQ-DIR-03, REQ-ORCH-05 |
| `skills/forge-1-prd/SKILL.md` | Resolve dir centrally; inject epic context before interview. | REQ-CTX-01/02, REQ-DIR-03 |
| `skills/forge-2-tech/SKILL.md` | Same; widen context-scan glob to depth-2; pass epic context into forge-researcher dispatch. | REQ-CTX-01/02, REQ-DIR-03 |
| `skills/forge-3-specs/SKILL.md` | Same; widen depth-1 spec glob; thread epic context into forge-spec-writer prompts. | REQ-CTX-01/02, REQ-DIR-03 |
| `skills/forge-4-backlog/SKILL.md` | Resolve dir centrally; compose per-feature backlog path when `backlogDir` is configured (see §5.7). | REQ-DIR-03, REQ-COMPAT-03 |
| `skills/forge-5-loop/SKILL.md` | Resolve dir; **dependency gate** (new Step 1b-epic); **handoff** (new Step 6). | REQ-ORCH-01/02/03/04, REQ-DIR-03 |
| `skills/forge-6-docs/SKILL.md` | Resolve dir; epic-level doc offer when all members complete. | REQ-DOCS-01, REQ-DIR-03 |
| `skills/forge-verify/SKILL.md` | New `epic` mode (CHECK-E0N checklist, single verifier). | REQ-VERIFY-01 |
| `skills/forge-fix/SKILL.md` | Resolve dir centrally. | REQ-DIR-03 |
| `skills/forge-verify/references/verification-checklists.md` | Append `## Epic Mode Checklist` (CHECK-E01..E08). | REQ-VERIFY-01 |
| `agents/forge-researcher.md` | Widen `specs/*/…` globs to find nested features. | REQ-DIR-03 |
| `scripts/validate.sh` | Invoke the pytest suite for the helper. | testing |
| `forge.config.json` (new, this repo) | Stack persistence: `stack`, `testCommand`, `typeCheckCommand` (schema + consumers in §2.4). **Deferred in v1** — not created; `scripts/validate.sh` hardcodes the helper commands as the built-in defaults (see §2.4). | stack resolution |

### 2.3 Public surface of `scripts/epic-manifest.py`

A single CLI, stdlib-only (Python 3), exit codes mirroring the rauf validate contract: **0 = ok/valid, 1 = findings/validation-fail, 2 = usage/IO error**.

| Subcommand | Purpose | Output |
|------------|---------|--------|
| `resolve <name> [--specs-dir DIR]` | Resolve bare feature/epic name → absolute directory, handling flat + nested. Enforces uniqueness and path containment. | Prints dir on stdout; exit 1 with actionable message if ambiguous/missing/unsafe |
| `validate <epic> [--json]` | Schema conformance + acyclicity + name-uniqueness + path-containment + dangling-`dependsOn` detection. | `{ "valid": bool, "findings": [...] }` |
| `check-name <name> [--specs-dir DIR]` | Reject a name that already exists anywhere in the specs tree (flat or nested). | exit 0 unique / 1 duplicate |
| `render-status <epic> [--json]` | Live epic dashboard data: per-feature derived status (from each `.pipeline-state.json`), blocked vs actionable set, parallel-eligible set, recommended next command. | JSON (see §4.4) |
| `add-feature / remove-feature / reorder / set-dep / set-status` | Atomic manifest mutations (temp-file + `os.replace`), each followed by full re-validation; refuse the write if it would introduce a cycle or dangling ref. | Updated manifest or exit 1 + findings |

The script reads only within `{specsDir}` and rejects any `name`/path with separators, `..` segments, or absolute paths before touching the filesystem (REQ-SEC-02).

### 2.4 Configuration (`forge.config.json`)

This feature reads the existing forge config keys via the shared-conventions config-reading protocol (defaults apply when absent):

| Key | Default | Consumed by this feature for |
|-----|---------|------------------------------|
| `specsDir` | `./specs` | All name→dir resolution, path containment, nested-vs-flat globbing |
| `backlogDir` | null (→ `{resolvedFeatureDir}/backlog.json`) | Per-feature backlog path composition (§5.7) |
| `gitCommitAfterStage` | true | Whether `forge-0-epic` creation/edits and the §5.3 handoff commit per the git-commit-after-stage protocol |
| `commitPrefix` | `forge` | Commit message prefix for epic-stage commits |

The new `stack` / `testCommand` / `typeCheckCommand` fields persist stack resolution for this repo (a prose plugin + Python helpers). Schema and consumers:

```jsonc
{
  "stack": "prose-plugin-python",   // string; resolved stack profile, written once at forge-init/stack-resolution time
  "testCommand": "bash scripts/validate.sh",    // string; how forge-verify / CI run the helper pytest suite (§7)
  "typeCheckCommand": "python3 -m py_compile scripts/epic-manifest.py"  // string; lightweight static check for the helper
}
```

- **Consumers:** `scripts/validate.sh` (and forge-verify impl mode, CHECK-I11) run `testCommand`/`typeCheckCommand`; `stack` is read by stack-resolution to skip re-prompting. These fields are optional — absence falls back to the built-in defaults shown above. They do not affect epic resolution or any runtime gating logic.

  **v1 status:** `forge.config.json` is **not shipped** in this repo. `scripts/validate.sh` hardcodes the helper commands (`python3 -m py_compile scripts/epic-manifest.py` and the pytest suite) directly — i.e. it runs the built-in defaults rather than reading them from config. The file is intentionally deferred because the defaults are the intended operating mode and no observed stack re-prompting problem justifies the added config surface. If the file is later introduced, `validate.sh` should source `testCommand`/`typeCheckCommand` from it with fallback to the current hardcoded defaults.

## 3. Technical Decisions

### 3.1 Deterministic manifest core in Python (REQ-EPIC-05, REQ-ROBUST-01/02/03, REQ-DIR-04, REQ-SEC-02)

Decision: graph, validation, resolution, status-derivation, and atomic-write logic live in `scripts/epic-manifest.py`, invoked by skills via `Bash`. Rationale: these requirements demand repeatable correctness and sub-second performance for ≤20 features; an LLM walking a dependency graph for cycles is non-deterministic and unverifiable. The existing `validate-traceability.py` establishes the pattern (deterministic check called by a skill). Acyclicity uses a standard DFS / Kahn topological sort; `O(V+E)` is trivially <1s for ≤20 nodes (REQ-ROBUST-01). **Alternative considered:** prose-only (LLM does it inline) — rejected for non-determinism and inability to guarantee atomicity/`<1s`.

### 3.2 Manifest as single source; EPIC.md as generated narrative (REQ-EPIC-02/03)

Decision: charters and structured `exposes`/`consumes` arrays live in `epic-manifest.json`; `EPIC.md` mirrors them as prose + decomposition rationale. Rationale: contract-drift checking (REQ-VERIFY-01) and context injection (REQ-CTX-02) read structured JSON rather than parsing markdown — far less brittle. `forge-0-epic` keeps EPIC.md in sync when it writes the manifest. **Alternative considered:** EPIC.md as source-of-truth with markdown-section parsing — rejected as brittle for drift-diffing.

### 3.3 No cached per-feature status (REQ-STATE-02)

Decision: the manifest stores **no** per-feature `status` field. `render-status` opens each member feature's `.pipeline-state.json` on every read and derives status live. Acceptance test (from PRD): editing a feature's pipeline-state file then rendering the epic view reflects the change with no refresh step — satisfied because there is nothing to refresh.

### 3.4 Centralized name→directory resolution (REQ-DIR-03/04, REQ-SEC-02, REQ-COMPAT-01/02)

Decision: a new `shared-conventions.md` block instructs every stage skill to obtain the feature directory via `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/epic-manifest.py resolve <name>` before any file I/O, replacing hardcoded `{specsDir}/{feature}/`. Resolution algorithm: (1) reject unsafe names; (2) look for `{specsDir}/{name}/.pipeline-state.json` (flat); (3) look for exactly one `{specsDir}/*/{name}/.pipeline-state.json` (nested); (4) more than one match anywhere → error (uniqueness violation, REQ-DIR-04); (5) zero matches → not-found error. Standalone features resolve to their flat path exactly as today (REQ-COMPAT-01/02). All globs the helper runs for resolution and uniqueness are **bounded to feature-shaped directories** — i.e. directories that directly contain a `.pipeline-state.json` — so non-feature subtrees (`.verification/`, `tests/`, fixture dirs) are never matched as features. **Alternative considered:** prose dual-path globbing per skill — rejected; duplicates uniqueness/containment logic across 10 skills.

**Pre-existing name-collision handling (REQ-COMPAT-01, REQ-DIR-04):** an existing specs tree may already contain two features that share a bare name (e.g. a legacy flat feature and an unrelated nested one) — a state that predates epic support and that standalone resolution previously never noticed. To avoid regressing previously-working standalone commands, the resolver distinguishes *introducing* a collision from *encountering* a pre-existing one: `check-name` (run by `forge-0-epic` before creating a new member) hard-rejects any name that already exists anywhere, so no **new** collision can be introduced (REQ-DIR-04). `resolve` (run by every stage skill) reports an ambiguity error listing all matching paths **only** when the requested name genuinely matches more than one feature-shaped dir; a name that matches exactly one dir always resolves cleanly. A one-time uniqueness audit is surfaced (non-fatally) by `forge-verify` epic mode (CHECK-E08) and by the navigator rather than aborting unrelated standalone commands, so a latent pre-existing duplicate is reported for manual cleanup without breaking features whose names are unique.

### 3.5 Completion rule for orchestration (REQ-ORCH-01)

A feature is **complete for orchestration** when:

```
stages.forge-5-loop.status == "complete"
  AND (forge-verify-impl is absent OR its status ∈ {"passed", "findings-applied"})
```

A feature whose `forge-verify-impl` is `findings-reported` (unfixed) is **not** complete and does **not** unblock dependents. This rule is implemented once in `render-status` and reused by the dependency gate and handoff. At handoff (§5.3) the just-finished feature's impl-verify is **offered as a recommended-but-skippable step** before unblocking dependents (resolves PRD §7 open question). Merge/PR status is not tracked (PRD Out of Scope).

### 3.6 Dependency model (REQ-EPIC-02, REQ-ORCH-03)

Each feature carries `dependsOn: [featureName,…]`. Derived sets computed by `render-status`:
- **actionable** = features whose every `dependsOn` is complete (per §3.5) and that are not themselves complete;
- **parallel-eligible** = actionable features that do not (transitively) depend on each other — surfaced for future parallel execution, but v1 execution is serial (REQ-ORCH-03, PRD Out of Scope). No separate `parallelGroup` field; the graph already expresses eligibility.

### 3.7 forge-0-epic creation & edit mode (REQ-EPIC-01/04/06)

A single skill handles both: if no manifest exists for the named epic, run the **decomposition interview** (AskUserQuestion-driven) producing the manifest + EPIC.md + one charter per feature (short scope + contract obligations only — **no full PRDs**, REQ-EPIC-04). If a manifest exists, enter **edit mode** supporting add/remove/reorder features and change deps via the helper's atomic mutators, each re-validated for acyclicity, with a warning when a change affects in-flight or completed features (REQ-EPIC-06). Member feature subdirectories are created empty (with a `.pipeline-state.json` carrying the `epic` back-pointer) so the navigator and resolver can see them.

**Observability / audit (REQ-OBS-01):** every helper mutator (`add-feature` / `remove-feature` / `reorder` / `set-dep` / `set-status`) bumps the manifest's top-level `updatedAt` to the current ISO-8601 timestamp as part of the same atomic write (§4.1). v1 records **only** the latest `updatedAt` (last-write timestamp) — no per-action audit history log is kept; a full audit trail is **deferred** as out of scope for v1 because the git history of `epic-manifest.json` already provides a per-commit record of every epic-affecting action (each mutation is committed, see below), making a separate in-manifest log redundant. After `forge-0-epic` creation and after each edit-mode mutation, and after the §5.3 handoff writes a feature's completion, the owning skill invokes the existing **git-commit-after-stage protocol** (shared-conventions) — gated on `gitCommitAfterStage` — staging `{specsDir}/{epic}/` so manifest + EPIC.md + member state changes are committed atomically with the standard `{commitPrefix}({feature}): …` message.

## 4. Data Model

### 4.1 `epic-manifest.json` (`references/epic-manifest-schema.json`)

```jsonc
{
  "schemaVersion": 1,
  "epic": "auth-overhaul",                  // kebab-case, matches subtree dir name
  "description": "…",
  "status": "active",                       // active | paused | abandoned | complete  (REQ-ORCH-05)
  "narrativeDoc": "EPIC.md",
  "createdAt": "ISO-8601",
  "updatedAt": "ISO-8601",                  // bumped by every mutator on each atomic write (REQ-OBS-01, §3.7)
  "features": [
    {
      "name": "token-service",              // kebab-case, globally unique (REQ-DIR-04)
      "charter": "One-paragraph scope statement…",   // REQ-EPIC-04
      "dependsOn": ["config-store"],        // names of sibling features (REQ-EPIC-02)
      "exposes":  [                         // structured contract (REQ-EPIC-03)
        { "name": "verifyJwt", "kind": "function|type|endpoint|module|event", "summary": "…" }
      ],
      "consumes": [
        { "from": "config-store", "name": "JWT_SECRET", "summary": "…" }
      ]
    }
  ]
}
```

Constraints enforced by `validate`: unique `epic` and `feature` names; every `dependsOn` and every `consumes.from` references a feature present in `features[]` (no dangling refs, REQ-ROBUST-02); the `dependsOn` graph is acyclic (REQ-EPIC-05); no name contains a path separator/`..`/absolute path (REQ-SEC-02). **No `status` field per feature** (REQ-STATE-02).

### 4.2 EPIC.md (REQ-EPIC-03)

Markdown narrative: overall goal, decomposition rationale, and a per-feature **Contracts** section rendering each feature's `exposes`/`consumes` as readable prose. Maintained in sync with the manifest by `forge-0-epic`. Drift between EPIC.md prose and manifest contracts is itself a verify check (CHECK-E06).

### 4.3 Pipeline-state additions (REQ-STATE-01)

Additive, optional — preserves REQ-COMPAT-02 (no migration):

```jsonc
{
  "epic": "auth-overhaul"   // optional back-pointer; absent for standalone features
}
```

`currentStage` enum and `stages` keys gain `forge-0-epic` and `forge-verify-epic`. On any manifest-vs-back-pointer conflict, **the manifest wins** (REQ-STATE-01); `forge-verify` epic mode flags the inconsistency (CHECK-E07).

### 4.4 `render-status` output (drives REQ-VIS-01)

```jsonc
{
  "epic": "auth-overhaul", "status": "active",
  "features": [
    { "name": "config-store", "stage": "forge-5-loop", "status": "complete", "blocked": false },
    { "name": "token-service", "stage": "forge-1-prd", "status": "in-progress",
      "blocked": false, "unmetDeps": [] }
  ],
  "actionable": ["token-service"],
  "parallelEligible": ["token-service"],
  "rollup": { "complete": 1, "total": 4 },
  "nextCommand": "/feature-forge:forge-1-prd token-service"
}
```

Per-feature `status` reuses the existing navigator status indicators (REQ-VIS-01).

## 5. Integration Points

### 5.1 shared-conventions.md → every stage skill
- **Feature Directory Resolution** block: skills call `epic-manifest.py resolve <name>`; the returned dir replaces hardcoded `{specsDir}/{feature}/`. Standalone features unaffected (REQ-COMPAT-01).
- **Epic Context Injection** block (REQ-CTX-01/02): after resolving the dir, if the feature's `.pipeline-state.json` has an `epic` back-pointer, load `{specsDir}/{epic}/EPIC.md`, the feature's `charter` from the manifest, and the `PRD.md`/`tech-spec.md` of each **direct** `dependsOn` feature that is complete. Transitive deps are surfaced only via EPIC.md contract sections — never by loading their specs (bounded, deterministic context).

### 5.2 forge-1/2/3 context injection
- forge-1-prd: inject before the interview (Step 2).
- forge-2-tech: inject after reading PRD (Step 1); add epic paths to the `forge-researcher` dispatch prompt; widen cross-feature glob from `{specsDir}/*/tech-spec.md` to also match `{specsDir}/*/*/tech-spec.md`.
- forge-3-specs: inject after reading PRD+tech-spec (Step 1); thread relevant EPIC.md sections + direct-dep tech-specs into each `forge-spec-writer` prompt; widen `{specsDir}/*/[0-9][0-9]-*.md` glob to depth-2.
- **Glob scoping:** the widened depth-2 globs are constrained to feature-shaped directories — only directories that contain a sibling `.pipeline-state.json` are treated as features. This prevents the depth-2 patterns from matching non-feature subtrees that legitimately hold matching filenames (e.g. a `tests/fixtures/…/tech-spec.md`, a numbered file under `.verification/`). In practice this means filtering glob results to paths whose parent dir also contains `.pipeline-state.json`, or delegating the listing to `epic-manifest.py` which already applies this bound.

### 5.3 forge-5-loop (REQ-ORCH-01/02/03/04)
- **Dependency gate** — new Step 1b-epic, between the backlog-verify soft gate (1b) and the runner version gate (1c): if the feature has an `epic` back-pointer, read the manifest, compute unmet deps via the §3.5 rule; if any are unmet, `AskUserQuestion` warn with the list and require explicit confirmation to proceed (REQ-ORCH-04). Absent back-pointer → gate skips entirely (REQ-COMPAT-01).
- **Handoff** — new Step 6, after pipeline state is written `complete`: if epic member, run `render-status`, announce completion, offer to run `forge-verify` impl on the just-finished feature (recommended, skippable, §3.5), then present the actionable next feature(s) via `AskUserQuestion`, offering to author the chosen one's PRD if absent (REQ-ORCH-02). Serial selection when multiple are unblocked (REQ-ORCH-03). No autonomous chaining (PRD Out of Scope). The completion write and any manifest `updatedAt` bump are committed via the git-commit-after-stage protocol when `gitCommitAfterStage` is true (REQ-OBS-01, §3.7).

### 5.4 forge navigator (REQ-VIS-01/02, REQ-ORCH-05)
- Named-epic argument → epic dashboard from `render-status` (graph, per-feature stage/status, blocked vs actionable, next command).
- No-arg discovery → 2-tier listing: epics (with `complete/total` rollup) above standalone features. Epic directories are recognized by the presence of `epic-manifest.json`; their nested `.pipeline-state.json` files are attributed to the epic, not listed as standalone.
- Lifecycle verbs (`pause/resume/abandon`) extended to epics; pausing/abandoning an epic does **not** silently mutate member features' own states — the relationship is surfaced explicitly to the user (REQ-ORCH-05).

### 5.5 forge-verify epic mode (REQ-VERIFY-01)
New `epic` mode: loads manifest + EPIC.md + each member `.pipeline-state.json`; runs CHECK-E01..E08 via a single `forge-verifier` instance (small checklist); writes `{specsDir}/{epic}/.verification/VERIFY-epic-{date}.md`; records `stages.forge-verify-epic`. Checks: valid manifest schema (E01), acyclic graph (E02), no dangling `dependsOn` (E03), charter coverage (E04), non-empty exposes/consumes per feature (E05), EPIC.md-vs-manifest contract drift for completed features (E06), back-pointer ↔ manifest consistency (E07), global name uniqueness (E08). E01/E02/E03/E08 delegate to `epic-manifest.py validate`; E04/E05/E06/E07 are verifier judgment.

### 5.6 forge-6-docs (REQ-DOCS-01)
After the per-feature completeness check, if the feature is an epic member and **all** members are complete (§3.5), offer (AskUserQuestion) to synthesize an epic-level architecture doc at `{docsDir}/{epic}/` in addition to per-feature docs. Source material: EPIC.md narrative, per-feature docs, manifest contracts. Per-feature `currentStage: complete` behavior unchanged.

### 5.7 Loop runner (rauf) — no change (REQ-COMPAT-03)
Backlogs remain per-feature and independent; dependencies are resolved only at feature granularity, before the loop launches. No rauf or backlog-schema change.

**`backlogDir` resolution rule (preserves per-feature independence, REQ-COMPAT-03):**
- When `backlogDir` is **unset** in `forge.config.json` (the default), the backlog lives at the resolved feature directory — `{resolvedFeatureDir}/backlog.json` — exactly as today, for both flat and nested features.
- When `backlogDir` **is configured**, it is treated by the existing forge-4 skill as a single path. To keep each epic member's backlog independent, forge-4 composes a per-feature subpath: **`{backlogDir}/{feature}/`**. A bare configured `backlogDir` (shared across all features) would otherwise collide for multi-feature epics and violate REQ-COMPAT-03; composing the `{feature}` segment prevents that. Standalone features under a configured `backlogDir` likewise resolve to `{backlogDir}/{feature}/`, which is backward-compatible because each standalone feature already had a unique name.

This rule is implemented once in `skills/forge-4-backlog/SKILL.md` after central directory resolution.

## 6. Error Handling

- **Helper exit codes:** 0 ok/valid, 1 findings/validation-fail, 2 usage/IO. `validate`/`render-status` emit `{valid|…, findings[]}` with actionable messages (e.g., `cycle: a → b → a`, `duplicate feature name 'x' (also at specs/other/x)`, `unknown dependsOn 'y' in feature 'x'`, `unsafe name '../z'`). Skills surface findings verbatim and stop on exit ≥1 for gating operations.
- **Corrupt/hand-edited manifest (REQ-ROBUST-02):** `validate` reports specific, actionable findings rather than crashing; skills present them and refuse to proceed with mutations until resolved.
- **Atomic writes (REQ-ROBUST-03):** all mutations write a temp file in the same directory then `os.replace` (atomic on POSIX); an interrupted write never leaves a partial manifest. Concurrent multi-session mutation is out of scope (single-writer assumed).
- **Resolution failures:** ambiguous/missing/unsafe names produce a clear error and abort the calling skill before any file I/O.
- **Path containment (REQ-SEC-02):** the helper canonicalizes and asserts every resolved path stays within `{specsDir}` before reading/writing; violations are exit-2 errors.

## 7. Testing Approach

- **`scripts/epic-manifest.py`:** pytest suite in `tests/` over fixture epic trees covering: valid manifest round-trip; cyclic graph rejection; duplicate-name detection (flat vs nested); path-escape/unsafe-name rejection; corrupt-JSON handling; dangling-`dependsOn` detection; status derivation from synthetic `.pipeline-state.json` files (each §3.5 branch: loop incomplete, loop complete + no impl-verify, loop complete + impl findings-reported, loop complete + findings-applied); atomic-write behavior (temp file + replace); `render-status` actionable/parallel-eligible/rollup correctness; performance sanity at 20 features (<1s, REQ-ROBUST-01). Wired into `scripts/validate.sh`.
- **Skill prose:** not unit-testable; validated via `forge-verify` epic mode (CHECK-E0N) and the PRD success-criteria walkthrough (decompose ≥2-feature epic, run stages 1–3 with context injection, blocked-loop gate, completion handoff, fresh-session dashboard reconstruction, unchanged standalone flows).
- **Coverage target:** every helper subcommand and every §3.5 status branch exercised by at least one fixture.

## 8. Dependencies

- **External:** Python 3 standard library only (no third-party packages) — matches `validate-traceability.py`. `pytest` as a dev/test dependency. No change to plugin runtime dependencies.
- **Internal:** `shared-conventions.md` (resolution + context-injection blocks), `pipeline-state-schema.json` (additive fields), `forge-verifier`/`forge-researcher`/`forge-spec-writer` agents (prompt additions only, no behavioral change).
- **Version constraints:** none new for rauf (REQ-COMPAT-03).

## 9. Open Technical Questions

- **Removed-feature directory treatment (PRD §7, unresolved):** when `forge-0-epic` edit mode removes a feature, leave its subdirectory in place under the epic subtree (v1 default) vs. relocate to flat specs. Proposed v1: leave in place, drop its manifest entry, warn the user; relocation is manual (consistent with PRD Out of Scope "no migration tooling"). To confirm during forge-3-specs.
- **EPIC.md regeneration on edit:** whether edit-mode mutations regenerate EPIC.md wholesale or patch the affected sections. Proposed: patch affected contract sections; full regen only on request. To confirm during specs.
- ~~`${CLAUDE_PLUGIN_ROOT}` availability for helper invocation~~ **Resolved:** `forge-verify/SKILL.md:259` invokes `${CLAUDE_PLUGIN_ROOT}/scripts/validate-traceability.py …`; `epic-manifest.py` reuses this exact convention.
```
