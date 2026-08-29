---
title: "Context Efficiency · CLI Reference"
---

# CLI Reference — the new `scripts/forge-session.py` subcommands

Eight subcommands were added: seven `state-*` verbs that write
`.pipeline-state.json` (R4), and `effective-config`, which resolves the `loopRunner`
block (R5). They sit alongside the script's existing read-only subcommands
(`rank-features`, `context-usage`, `doctor`, `discover-feature`, `reconcile-branch`,
`check-epic-base`, `stage-exit`).

The script ships to every adapter target as a runtime helper, so these are available from
any install. Invoke it through the resolved plugin root:

```bash
python3 "$R/scripts/forge-session.py" <subcommand> [flags]
```

## Exit Codes

`forge-session.py` uses a **two-code** convention. Note this differs from
`scripts/epic-manifest.py`, which uses 0/1/2 — there, exit 1 carries a structured
*finding*. There is no exit 1 here.

| Code | Meaning |
|------|---------|
| **0** | Success. Recoverable conditions degrade to data at exit 0 rather than failing (a missing config, an absent optional field). |
| **2** | Usage or I/O error. A plain `Error: …` line on stderr, empty stdout. Nothing was written. |

For the `state-*` verbs, exit 2 is a **hard stop with no partial write**. Surface the
stderr line verbatim, do not proceed to the next step of the surrounding protocol, and do
not hand-author the JSON as a workaround — the stage remains resumable because the entry
stamp is already on disk, so re-run the verb once the cause is fixed.

## Common Flags

Every `state-*` verb accepts these:

| Flag | Default | Description |
|------|---------|-------------|
| `--feature NAME` | *required* | The feature whose state to write. |
| `--specs-dir DIR` | `./specs` | The configured specs directory. |
| `--epic NAME` | none | The owning epic. **Required whenever the feature is an epic member** — see [Epic members must pass `--epic`](#epic-members-must-pass---epic). |
| `--json` | off | Echo the resulting state as JSON instead of a one-line human summary. |

`--stage` takes one of `forge-0-epic`, `forge-1-prd`, `forge-2-tech`, `forge-3-specs`,
`forge-4-backlog`, `forge-5-loop`, `forge-6-docs`. An out-of-domain value is rejected at
parse time.

### Epic members must pass `--epic`

The write path resolves fail-closed. Without `--epic`, a bare `--feature api` that matches
both a standalone `{specsDir}/api/` and a member `{specsDir}/{epic}/api/` — each carrying a
state file — is **refused** rather than guessed at:

```
Error: ambiguous feature 'api': 2 directories carry a state file
(specs/api, specs/auth-overhaul/api) — pass --epic <epic> to name the one to write.
Refusing to guess; nothing was written.
```

A standalone feature omits the flag. This is deliberately stricter than the read-only
resolver, which tolerates ambiguity because a read can safely downgrade to "not started";
a writer cannot.

## `effective-config`

```
effective-config [--config ./forge.config.json] [--schema PATH] [--json]
```

Resolves the effective `loopRunner` configuration: every field's default is read from
`references/forge-config-schema.json` at runtime, then the project's `loopRunner` block is
merged over the top. Nothing is hardcoded, so the schema stays the single source of truth.

**Flags:**

- `--config PATH` (default `./forge.config.json`) — the project config. A missing or
  corrupt file is tolerated and yields pure defaults.
- `--schema PATH` (default: the bundled `references/forge-config-schema.json`, resolved
  relative to the script so it works from any working directory) — chiefly for tests.
- `--json` — emit the resolved object as JSON.

**Exit contract:**

| Condition | Exit | Result |
|-----------|------|--------|
| Config present and valid | **0** | Defaults with the project's overrides applied. |
| Config **missing** | **0** | Pure schema defaults. |
| Config present but **corrupt** | **0** | Pure schema defaults — the config loader tolerates it. |
| Schema unreadable, unparseable, or lacking `loopRunner.properties` | **2** | `Error: config schema unreadable: …` (or `…is not valid JSON`, `…has no loopRunner.properties object`). Nothing is emitted — a partial default set would be worse than failing. |

**Merge semantics.** A user field replaces that field's default one-for-one. An absent field
keeps its default. An unknown key is carried through rather than dropped (the config schema
is the authority that flags it at author time).

**Example — human-readable:**

```bash
$ python3 "$R/scripts/forge-session.py" effective-config --config ./forge.config.json
Effective loopRunner config:
  agentArgument      : '--agent {agent}'
  agentsProbeCommand : '{bin} agents --json'
  bin                : 'rauf'
  defaultAgent       : ''
  eventStreamCommand : '{bin} loop run . --backlog {backlogDir} --iterations {iterations} --ndjson'
  …
  minRunnerVersion   : '0.14.0'
  name               : 'rauf'
  preconditionFile   : '.rauf.json'
  runCommand         : '{bin} loop run . --backlog {backlogDir} --iterations {iterations}'
  stateDir           : '.rauf'
```

**Example — JSON, for a skill step that needs one field:**

```bash
$ python3 "$R/scripts/forge-session.py" effective-config --json
{
  "name": "rauf",
  "bin": "rauf",
  "runCommand": "{bin} loop run . --backlog {backlogDir} --iterations {iterations}",
  "minRunnerVersion": "0.14.0",
  ...
}
```

Command templates are returned **literally**, with their `{bin}` / `{backlogDir}` /
`{iterations}` placeholders intact. Substitution is the caller's job.

## State-Write Verbs

All seven share the same path: resolve the feature directory (fail-closed) → load state →
apply exactly one mutation → refresh `updatedAt` → write atomically. Common failure modes,
all exit 2: an unknown feature directory (a verb never *creates* one), a state file that
exists but is not valid JSON (refused, left byte-intact), or a failed atomic write.

### `state-enter`

```
state-enter --feature F --stage S [--specs-dir D] [--epic E] [--json]
```

Applies the **Entry Stamp**: sets `stages.{stage}.status = "in-progress"`, stamps
`startedAt`, and moves top-level `currentStage` to this stage.

Idempotent on re-entry within the same run — re-stamping an already in-progress stage just
refreshes the timestamps. The verb never prompts; the resume-vs-restart decision stays with
the calling skill.

The write is intentionally left **uncommitted**, to be swept up by the stage's own exit
commit. If a run dies after the stamp but before that commit, the marker survives on disk
and the next entry classifies the stage as interrupted — which is the point.

```bash
$ python3 "$R/scripts/forge-session.py" state-enter --feature auth --stage forge-2-tech
entered forge-2-tech (in-progress) for auth
```

### `state-artifact`

```
state-artifact --feature F --stage S --path P [--path P …] [--specs-dir D] [--epic E] [--json]
```

Appends each `--path` to `stages.{stage}.artifacts`, de-duplicating. Call it after writing
*each* file, not only at stage completion — that is what makes the interrupted-run
inventory precise about which files actually landed.

`--path` is repeatable. Paths are relative to the feature directory. The verb does **not**
stat the file; it records the path the caller asserts it wrote. An already-tracked path is
a no-op, but `updatedAt` is still refreshed, keeping "state was touched" honest.

```bash
$ python3 "$R/scripts/forge-session.py" state-artifact --feature auth \
    --stage forge-3-specs --path 00-core-definitions.md --path 01-architecture-layout.md
tracked forge-3-specs artifact(s): 00-core-definitions.md, 01-architecture-layout.md (2 total)
```

### `state-complete`

```
state-complete --feature F --stage S --version N
               [--based-on STAGE=N …] [--artifact PATH …]
               [--commit-hash H] [--status complete|in-progress]
               [--resumable] [--preserve-commit-hash]
               [--specs-dir D] [--epic E] [--json]
```

The completion write — and, via its flags, the other two moves in the two-commit git
protocol. It has three branches, in this precedence order:

**1. `--commit-hash` given — commit 2.** Records *only* `commitHash`, leaving
status/version/provenance/artifacts intact. Refuses (exit 2) if the stage is not already
`complete`, so a mistyped `--stage` cannot create a lone `{"commitHash": …}` entry:

```
Error: --commit-hash requires forge-2-tech to be complete (status: 'pending');
run state-complete without --commit-hash first
```

**2. `--resumable` — the failed-commit-1 revert.** Records *only*
`status = "in-progress"`. No `completedAt`, no version bump, no `basedOnVersions` or
`artifacts` write, no `commitHash` reset, no staleness cascade. `--version` is still
**required by the parser** and must be passed even though this branch does not write it —
omitting it makes the recovery command exit 2 every time. `--resumable --status complete`
is contradictory and refused.

**3. Otherwise — the completion write.** Sets `status` (default `complete`),
`completedAt`, `version`, `basedOnVersions`, `artifacts`, and `commitHash: null` (commit
1), then runs the **downstream staleness cascade**.

**Flags:**

- `--version N` — the stage's new version. Always required.
- `--based-on STAGE=N` — repeatable provenance: the upstream version this artifact was
  built on. `forge-1-prd` legitimately records none (`basedOnVersions == {}`). A token
  without `=`, or with a non-integer version, is exit 2.
- `--artifact PATH` — repeatable; the final canonical artifact list for this stage.
- `--status complete|in-progress` — `in-progress` is for `forge-5-loop`'s **partial**
  completion, which is a real completion (it keeps `completedAt`, `version`,
  `basedOnVersions` and `artifacts`) where only the status differs. This is *not* the same
  as `--resumable`.
- `--preserve-commit-hash` — skip the `commitHash = null` reset, for the git protocol's
  "nothing to commit" branch where there is no new artifact commit to record.

**The staleness cascade.** For each downstream stage in `forge-2-tech` … `forge-6-docs`: if
it is currently `complete` **and** its `basedOnVersions[thisStage]` is an integer strictly
less than `--version`, it flips to `stale`. A stage that never referenced this upstream,
already references the new version, or is not `complete`, is untouched. `forge-1-prd` is
never a cascade target. The cascade result is reported to you but is not itself persisted:

```bash
$ python3 "$R/scripts/forge-session.py" state-complete --feature auth \
    --stage forge-1-prd --version 2 --artifact PRD.md
completed forge-1-prd v2 (commitHash: null); marked stale: forge-2-tech, forge-3-specs
```

Then, after the artifact commit lands:

```bash
$ python3 "$R/scripts/forge-session.py" state-complete --feature auth \
    --stage forge-1-prd --version 2 --commit-hash "$(git rev-parse HEAD)"
recorded forge-1-prd commitHash: 706c96ecd21ff607c40f084b78d258d5f97de505
```

### `state-branch`

```
state-branch --feature F --branch B [--specs-dir D] [--epic E] [--json]
```

Sets the top-level `branch` field to the branch resolved by Branch Setup or Branch
Reconciliation. The verb writes only the field — the prompts, and the visible one-line note
when reconciliation adopts a different branch, stay with the calling skill.

Because Branch Setup fires *before* the entry stamp, this can legitimately be the first
thing to touch a feature's state file. The shared loader seeds the schema-required
top-level fields on every verb, so that first write is still valid.

```bash
$ python3 "$R/scripts/forge-session.py" state-branch --feature auth --branch forge/auth
recorded branch for auth: forge/auth
```

### `state-note`

```
state-note --feature F --note TEXT [--specs-dir D] [--epic E] [--json]
```

Sets the top-level `notes` field. This **overwrites** any existing note — the field is a
single free-text string, not an append log. Run it only when the user volunteered a note;
the "offer a note, don't force one" framing is the skill's, not the verb's.

```bash
$ python3 "$R/scripts/forge-session.py" state-note --feature auth \
    --note "OAuth provider list deferred to the integration spec"
note set for auth (52 chars)
```

### `state-decision`

```
state-decision --feature F --question Q --raised-by S
               [--rationale X] [--target-stage T] [--specs-dir D] [--epic E] [--json]
```

Appends an open item to `deferredDecisions[]`. The recorded item carries exactly the schema
keys — the array item sets `additionalProperties: false`, so an extra convenience field
would be a hard validation failure. `status` is always `"open"`; the verb never resolves a
decision (the target stage flips it to `addressed`).

- `--raised-by` — one of `forge-1-prd`, `forge-2-tech`, `forge-3-specs`, `forge-4-backlog`.
- `--target-stage` — optional; any of the six production stages.
- `--rationale` — optional; why it is being deferred.

```bash
$ python3 "$R/scripts/forge-session.py" state-decision --feature auth \
    --question "Which OAuth providers ship in v1?" \
    --raised-by forge-1-prd --target-stage forge-2-tech \
    --rationale "Needs a provider-cost comparison the PRD interview could not settle"
deferred decision recorded (raisedBy forge-1-prd → forge-2-tech)
```

### `state-ecr`

```
state-ecr --feature F --kind K --target T --rationale X --raised-by S
          --blocks-current true|false [--specs-dir D] [--epic E] [--json]
```

Appends an open **epic change request** to `epicChangeRequests[]` — a member feature's
report that the epic's decomposition itself needs to change.

- `--kind` — one of `add-feature`, `redep`, `move-boundary`, `split`.
- `--target` — the sibling feature to add, or the feature/boundary affected.
- `--raised-by` — `forge-1-prd` or `forge-2-tech`.
- `--blocks-current true|false` — `true` means pause and reconcile the epic before
  proceeding; `false` means finish this feature, then edit the epic.

```bash
$ python3 "$R/scripts/forge-session.py" state-ecr --feature token-service \
    --kind add-feature --target rate-limiter \
    --rationale "Token issuance needs a shared rate limiter no member owns" \
    --raised-by forge-2-tech --blocks-current false
epic change request recorded (add-feature → rate-limiter, blocksCurrent=false)
```

## Notes

- **`--json` echoes the resulting state**, so a caller can confirm the write without
  re-reading the file. `state-complete` additionally reports which stages the cascade
  marked stale, under a synthetic key that is *not* written to disk.
- **The verbs are the only writers in this script.** Everything else is read-only.
- **The state schema is still the contract.** `references/pipeline-state-schema.json` is no
  longer read per stage, but a drift guard validates every verb's output against it, so
  non-conformant output is a CI failure rather than a corrupted pipeline.
- **Never hand-author `.pipeline-state.json` as a workaround** for a verb that exits 2. Fix
  the cause and re-run; the whole point of the verbs is that no hand-authored JSON reaches
  the file.
