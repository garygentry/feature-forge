# Epic Verification Checklist

Detailed checklist for the **epic** verification mode, loaded by the `forge-verifier` leaf subagent dispatched for that mode. Execute EVERY check — do not skip.

> **Stack-specific details:** When a stack profile exists at `references/stacks/{stack}.md`, load it alongside this checklist for language-specific check criteria (e.g., what "valid syntax" means, what the type check command is, how module exports work).

## Epic Mode Checklist

Run `epic-manifest.py validate "{epic}" --specs-dir "{specsDir}" --json` once; map its
findings to E01/E02/E03/E08. Then perform the judgment checks E04–E07, E09, and E10 by
reading the manifest, EPIC.md, completed members' specs, and (for E10) sibling members'
committed tests.

```bash
R="$(bash -c 'for d in "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/epic-manifest.py" validate "{epic}" --specs-dir "{specsDir}" --json
```

### Manifest Integrity (helper-delegated)
- [ ] **CHECK-E01**: `epic-manifest.json` conforms to `epic-manifest-schema.json`
  (delegated: `validate` reports `schema` / `corrupt-json` findings).
- [ ] **CHECK-E02**: the `dependsOn` graph is **acyclic** (delegated: `validate` reports
  `cycle`).
- [ ] **CHECK-E03**: no dangling `dependsOn` / `consumes.from` — every reference names a
  feature in `features[]` (delegated: `validate` reports `dangling-ref`).
- [ ] **CHECK-E08**: **global name uniqueness** across the specs tree — no feature name
  resolves to more than one feature-shaped dir (delegated: `validate` / `check-name`
  report `duplicate-name` / `ambiguous`). Surfaced non-fatally for manual cleanup.

### Charter & Contract Coverage (verifier judgment)
- [ ] **CHECK-E04**: **charter coverage** — every feature has a non-empty `charter`
  stating scope **and** contract obligations (REQ-EPIC-04).
- [ ] **CHECK-E05**: each feature has a meaningful `exposes`/`consumes` declaration — flag
  a feature with empty contracts that the narrative implies should have them
  (REQ-EPIC-03). (Empty is *schema-legal* but suspicious for a feature other features
  depend on.)
- [ ] **CHECK-E06**: **EPIC.md ⇆ manifest contract drift, for completed features only** —
  the contracts in `EPIC.md` match the manifest `exposes`/`consumes`, and a completed
  feature's specs actually deliver what it `exposes`. Drift between EPIC.md prose and the
  manifest, or between the manifest and the built spec, is a finding (REQ-VERIFY-01).
- [ ] **CHECK-E07**: **back-pointer ⇆ manifest consistency** — every member's
  `.pipeline-state.json` `epic` value names this epic, and every `features[]` entry has a
  matching member directory. On conflict the **manifest wins** (REQ-STATE-01); report, do
  not auto-repair.
- [ ] **CHECK-E09**: **open epic change requests** — any member whose `.pipeline-state.json`
  carries `epicChangeRequests[]` entries with `status: "open"` is surfaced as a **non-fatal**
  finding (one per open request). Severity keys off `blocksCurrent`: a **blocking** request →
  `error` (decision-bearing: the epic decomposition and an in-flight member disagree, stage
  exits interpose reconcile-first on it, and specs written now would build on a soon-invalid
  premise), a **non-blocking** request → `improvement` (a peer/downstream change to reconcile
  when convenient). Name the request's `kind`, `target`,
  and `rationale`, and point at `/feature-forge:forge-0-epic {epic}` to reconcile. **Report, do
  not repair** (same posture as CHECK-E07). Which members have open requests comes from the
  same `render-status --json` counts the navigator uses (`features[].openEpicChangeRequests` /
  `.blockingEpicChangeRequests`); the per-request `kind`/`target`/`rationale` detail is read
  from the member `.pipeline-state.json` already loaded in Step 2. This is the pre-emptive
  surface for the divergence class CHECK-E06/E07 otherwise catch only after the fact.
- [ ] **CHECK-E10**: **cross-member shared-state test coupling** (#144). A member that writes or
  migrates a file a *sibling's* committed tests already pin will break the sibling's suite the
  moment it runs — blocking every one of its own commits from a green test gate — yet nothing in
  E04–E09 catches it (contracts cover code symbols, not shared data files). Detect it heuristically,
  per member `M`:
  1. **Collect `M`'s mutated paths.** Take `M`'s `mutatesShared[]` from the manifest if present
     (the authored precision hint). If absent or empty, fall back to grepping `M`'s specs
     (change-maps / "files this writes") and backlog item `execute` steps for project-root-relative
     paths it creates, writes, or migrates (data corpora, generated fixtures, migration outputs —
     not `M`'s own source modules or its own tests).
  2. **Grep sibling tests for reads of those paths.** For every *other* member `S` that is already
     **`complete`** (derived status — its regression suite is live and gating), grep `S`'s committed
     **test** files/globs for a read/import/load of any path in step 1. Use the stack profile
     (`references/stacks/{stack}.md`) for what a test glob looks like in this language.
  3. **Emit the finding.** A hit → a non-fatal `inconsistency` finding: name `M`, the shared path,
     the sibling `S` and the specific test, and **recommend a reconciliation backlog item** on `M`
     (regenerate/re-pin `S`'s fixture, or update `S`'s test to the new shape) scheduled *before*
     `M`'s first mutating item — so the coupling is planned, not discovered mid-loop on a red gate.
     **Report, do not repair** (same posture as CHECK-E07/E09). Degrades to a clean no-op when no
     member declares or greps a shared write, or when no completed sibling reads it — never a
     spurious hard-fail.

