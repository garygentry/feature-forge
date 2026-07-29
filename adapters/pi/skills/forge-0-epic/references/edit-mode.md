# forge-0-epic — Edit Mode (E1–E6) + Observability / Pipeline State & Commit

Lookup detail relocated out of the `forge-0-epic` SKILL.md body. The skill body keeps the
entry condition (the **EXISTS** branch from Step 0) and the high-level "every mutation is
committed individually" rule, and points here for the full mechanics. The exact mutator flag
surface and per-subcommand exit-code handling live in `references/epic-manifest-subcommands.md`.

Entered from Step 0 when `{specsDir}/{epic}/epic-manifest.json` already exists (the **EXISTS**
branch). The edit branch mutates the manifest **only** through helper mutators — the skill never
hand-rolls an in-place write. Every mutator is atomic (temp file + `os.replace`) and re-validates
the edited graph internally, so a refused write leaves the manifest **byte-identical**. Every
question goes through `AskUserQuestion`.

## Step E1 — Load + Validate, Refuse if Invalid

Before offering any edit, validate the existing manifest:

```bash
R="$(bash -c 'for d in "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/epic-manifest.py" validate "{epic}" --specs-dir "{specsDir}" --json
```

- Exit `0` → the manifest is well-formed; proceed to E2.
- Exit `1` or `2` → the manifest is corrupt or invalid (hand-edited, `corrupt-json`, `cycle`,
  `dangling-ref`, `duplicate-name`, `cached-status`, `unsafe-name`, …). Surface **every**
  `findings[]` entry **verbatim**, then **refuse ALL mutation** until the user repairs the
  manifest by hand. **Never auto-repair**, never offer an edit operation, and never proceed past
  this gate. Tell the user what is wrong and STOP.

## Step E0-read — Surface Pending Epic Change Requests (backflow)

Immediately after E1's validate gate passes, and **before** offering the E2 operation menu,
scan for epic-level change requests that a member stage recorded during the pipeline (the
backflow path — see `references/pipeline-state-schema.json` `epicChangeRequests[]`, written by
`forge-1-prd`/`forge-2-tech`). Enumerate the manifest's feature list (already loaded in E1) and
read each member's `{specsDir}/{epic}/{member}/.pipeline-state.json`, collecting every
`epicChangeRequests[]` entry with `status: "open"`. If a member state is missing or unreadable,
report it and continue with the rest — do **not** abort edit mode over one bad member file (mirror
E1's "report, never silently repair" posture).

If any open requests exist, present them grouped (show `kind`, `target`, `rationale`,
`blocksCurrent`, `raisedBy`), then for **each** request use `AskUserQuestion` to offer **Apply**,
**Dismiss**, or **Skip for now**:

- **Apply — simple kinds (`add-feature`, `redep`):** pre-fill the matching E2 operation and flow
  through E3→E4→E5→E6 unchanged. `add-feature` seeds the new feature's charter from the request's
  `rationale` (the user still edits `exposes`/`consumes`/`dependsOn` before commit, exactly as
  C3/C4/C5); `redep` pre-fills `set-dep {epic} {target} --depends-on "…"`. The existing E4 impact
  warning fires normally — a `blocksCurrent` boundary change naturally trips it, which is correct.
- **Apply — composite kinds (`move-boundary`, `split`):** there is no single mutator (v1). Walk the
  user through a **guided-manual** sequence — the relevant `set-dep` and/or direct `exposes`/
  `consumes` edits on the composed manifest entries (per E3's "Contracts have no mutator" rule),
  across **both** affected features — re-validating after each step. Confirm each mutation via
  `AskUserQuestion`; never batch-apply.
- **Dismiss:** the user decides the epic is fine after all — flip the source request's `status` to
  `"dismissed"` (no manifest mutation). Explicit only; there is **no auto-expiry**.
- **Skip for now:** leave the request `open`; it resurfaces on the next edit-mode entry and stays
  visible in the navigator/verify (once Phase 2 surfacing lands).

**On a successful Apply** (mutator exit 0, or the guided-manual sequence confirmed), flip the
**source** request's `status` from `"open"` to `"applied"` in its member `.pipeline-state.json`,
using the same atomic temp-file + `os.replace` write the skill uses for any state edit. The E6 git
step already stages the whole `{specsDir}/{epic}/` subtree, so the flipped member state is captured
in the **same commit** as the manifest mutation — no new commit machinery. If a **Dismiss** is the
only action taken (no manifest mutation follows), still commit the member-state change under the
standard edit-mode message form, e.g. `forge({epic}): dismiss epic change request`.

E0-read is **read-then-offer** — it never auto-applies. Every apply still passes through E3/E4 with
explicit human confirmation, preserving the human-approves-every-mutation invariant. If **no** open
requests exist, say nothing and proceed straight to E2.

## Step E2 — Choose Operation

Use `AskUserQuestion` to offer the edit operations, each mapping to one helper mutator:

| Operation | Helper subcommand |
|-----------|-------------------|
| Add a feature | `add-feature` |
| Remove a feature | `remove-feature` |
| Reorder features | `reorder` |
| Change a dependency edge | `set-dep` |
| Change epic lifecycle status | `set-status` |

For **add-feature**, first run `check-name "{feature}"` (exactly as C2) so no new duplicate is
introduced — surface a `duplicate-name`/`unsafe-name` finding verbatim and re-prompt — then
elicit the new feature's **charter** + **`exposes`/`consumes`** + **`dependsOn`** exactly as in
C3/C4.

## Step E3 — Apply via Helper Mutator (re-validated)

Issue the chosen mutator. Each writes atomically and re-runs full validation internally, refusing
the write if it would introduce a cycle, dangling ref, duplicate, or schema violation. For the
exact `epic-manifest.py` mutator flag surface and per-subcommand exit-code handling, read
`references/epic-manifest-subcommands.md`.

**Contracts have no mutator.** `add-feature` seeds empty `exposes`/`consumes`. To populate the
new feature's contracts, edit its `exposes`/`consumes` arrays **directly in the composed manifest
entry** (exactly as creation C5 does), then re-run `validate "{epic}" --json` to confirm — there
is intentionally no `--exposes-json`/`--consumes-json` flag.

**remove-feature leaves the member directory in place (§7.5).** The mutator drops only the
manifest entry. The skill does **not** delete or relocate `{specsDir}/{epic}/{feature}/`. WARN the
user verbatim:

> Removed `{feature}` from the manifest. Its directory `{specsDir}/{epic}/{feature}/` is left in
> place; move it to `{specsDir}/{feature}/` by hand if you want it as a standalone feature.
> Relocation is manual — there is no migration tooling.

The orphaned subdir still holds a `.pipeline-state.json` with an `epic` back-pointer the manifest
no longer lists; per the conflict rule the **manifest wins**, and `forge-verify` epic mode
CHECK-E07 reports the inconsistency non-fatally. The skill does **not** silently edit the orphaned
state file.

## Step E4 — Impact Warning (in-flight / completed features)

Before applying — or immediately after eliciting — a mutation that affects a feature whose derived
status is **not** `not-started`, warn the user. Read the **live** status (never re-derive
completion in prose):

```bash
R="$(bash -c 'for d in "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/epic-manifest.py" render-status "{epic}" --specs-dir "{specsDir}" --json
```

If the operation removes, reorders-around, or re-deps a feature whose derived status is
`in-progress` or `complete`, use `AskUserQuestion` with an explicit warning naming the affected
in-flight/completed feature(s) and **require confirmation** before applying. Example: "`token-service`
is already in-progress (forge-3-specs). Removing `config-store`, which it consumes `JWT_SECRET`
from, may invalidate its in-flight specs. Proceed?" If `render-status` exits `≥ 1`, surface the
findings and STOP (do not mutate over an invalid graph).

## Step E5 — Patch EPIC.md

Patch **only** the affected feature/Contracts section(s) — the section(s) for the added, removed,
or changed feature and any feature whose `dependsOn`/`consumes` changed — applying the §C6 mirror
rule (one bullet per `exposes`/`consumes` entry). **Full regeneration happens only on explicit
user request**: offer it via `AskUserQuestion` but default to the targeted patch. The skill keeps
EPIC.md in sync but does not itself diff it against the manifest — drift detection is `forge-verify`
epic mode CHECK-E06.

## Step E6 — Pipeline State & Commit

Proceed to the **Observability, Pipeline State & Commit** section below. Each edit-mode mutation is
committed individually so git history is the audit trail.

## Observability, Pipeline State & Commit

### Manifest `updatedAt`

Every helper mutator bumps the manifest's top-level `updatedAt` to the current ISO-8601 UTC
timestamp as part of the same atomic write. The skill does **not** bump it manually in edit mode.
For the initial creation write (C5) the skill sets `createdAt == updatedAt`.

### Pipeline state

- **Epic-level:** the epic subtree has **no `.pipeline-state.json` of its own** (that is what
  distinguishes an epic root from a feature). The epic's lifecycle lives in the manifest `status`
  field. The `forge-0-epic` run is recorded in **member** states, not in an epic-level state file.
- **Member-level (creation):** each member's `.pipeline-state.json` records
  `stages["forge-0-epic"].status = "complete"` and `currentStage = "forge-1-prd"` (see C7).
- **Edit mode:** edits mutate the **manifest**, not member pipeline states — except the
  newly-created subdir for `add-feature`, which follows C7 (create the member subdir + back-pointer
  state). The skill does **not** rewrite existing members' `stages` on an edit.
- **`.epic-state.json` (lazily created, written by skills — NOT the helper):** epic-*scoped* stage
  entries that belong to no single member — currently only `forge-verify-epic` — are persisted in a
  dedicated `{specsDir}/{epic}/.epic-state.json`. It holds **only** epic-scoped stage entries,
  never derived per-feature status (so it does not violate REQ-STATE-02). `forge-0-epic` does
  **not** create this file — no epic-scoped stage runs during creation or edit; it appears only once
  `forge-verify` epic mode runs. When a skill does write it (e.g. forge-verify epic mode), it writes
  **directly** using an atomic temp-file + `os.replace` pattern — the helper exposes no subcommand
  for it. On I/O failure the skill reports and leaves any prior file intact (never a partial write).
  Minimal schema:

  ```jsonc
  {
    "epic": "auth-overhaul",            // matches manifest `epic`
    "stages": {
      "forge-verify-epic": {
        "status": "findings-reported",   // "findings-reported" | "passed" | "findings-applied"
        "findingsFile": ".verification/VERIFY-epic-2026-06-12.md",
        "findingsCount": 3,
        "verifiedAt": "2026-06-12T00:00:00Z"
      }
    }
  }
  ```

  The git-commit step below stages the whole epic subtree, so `.epic-state.json` is captured
  automatically when present.

### Git Commit Protocol

After creation (C8) **and after each edit-mode mutation (E6)**, if `gitCommitAfterStage` is true,
follow the Git Commit Protocol in shared-conventions:

1. Stage the whole epic subtree only: `git add {specsDir}/{epic}/` — **never** `git add -A`. This
   captures `epic-manifest.json`, `EPIC.md`, member `.pipeline-state.json` files, and any
   `.epic-state.json` together atomically.
2. Commit with message `"{commitPrefix}({epic}): <action>"`, e.g.
   `"forge({epic}): create epic with 4 features"`, `"forge({epic}): add feature api-gateway"`,
   `"forge({epic}): remove feature legacy-session"`, `"forge({epic}): reorder features"`,
   `"forge({epic}): set dependency on token-service"`, or `"forge({epic}): set status paused"`.
3. On success, capture the commit hash for reporting only — the epic manifest has no `commitHash`
   field, so nothing is written back into a committed file and the two-commit step of the Git Commit
   Protocol does not apply here. On failure (pre-commit hook, conflict), report and do **not** mark
   complete; never use `--amend`/`--no-verify`/`--force`.

Because every mutation is committed, the git history of `epic-manifest.json` is the audit trail; no
separate in-manifest audit log is kept.

### Closing message

After a successful **creation**, present the next-steps message (already specified in C8). After a
successful **edit-mode mutation**, confirm the change and re-surface the dashboard pointer:

> Epic `{epic}` updated (`<action>`). Run `/skill:forge {epic}` to see the refreshed
> dashboard, or re-run `/skill:forge-0-epic {epic}` to make another change.

## EPIC.md Mirror Template (creation C6 / edit E5)

`forge-0-epic` Step C6 generates `{specsDir}/{epic}/EPIC.md` from the **validated** manifest; the
edit-mode E5 patch applies the **same mirror rule** to the affected sections. The full skeleton:

```markdown
# {epic} — Epic

## Overall Goal
{the epic goal from C1, expanded into narrative prose}

## Decomposition Rationale
{why the change was split this way; right-sizing notes; ordering rationale}

## Features
{for each feature, in manifest order:}

### {feature.name}
{feature.charter, as prose}

**Depends on:** {comma-separated dependsOn, or "nothing"}

#### Contracts
**Exposes:**
- `{exposes[i].name}` ({exposes[i].kind}) — {exposes[i].summary}
{… or "Nothing exposed." if the exposes array is empty}

**Consumes:**
- `{consumes[i].name}` from `{consumes[i].from}` — {consumes[i].summary}
{… or "Nothing consumed." if the consumes array is empty}
```

## Member State Example (creation C7)

Each member's `.pipeline-state.json` (created in Step C7) conforms to
`references/pipeline-state-schema.json`. Example member state:

```json
{
  "epic": "{epic}",
  "currentStage": "forge-1-prd",
  "stages": {
    "forge-0-epic": { "status": "complete", "version": 1, "completedAt": "<iso-8601-utc>" }
  }
}
```
