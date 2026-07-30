---
title: "Context Efficiency · Architecture"
---

# Context Efficiency — Architecture

Design decisions behind the five shipped units, the trade-offs each one makes, and the
candidates that were deliberately left on the table.

## Design Goals

1. **Behavior preservation is the prime directive.** Every change is a *relocation* of
   instruction text, a *dedup*, or a *script extraction*. No interactive protocol was
   reworded: the question turn structure, the decision-support framing, the branch prompts,
   the stage-entry classification, the two-commit git sequence, the verify gates and the
   anti-fabrication guards all keep their exact prose. Where a sentence had to change to
   move, that was flagged in review rather than silently adapted.
2. **Each unit is independently revertible.** A regression in one reverts one change, not
   a batch. This drove the delivery sequence and rules out any refactor that entangles two
   units in one commit.
3. **Measure the targeted invocation, and count the cost.** A unit is judged by its net
   delta on the specific call it optimizes, against a baseline re-measured at
   implementation time. Always-paid growth (a new gating clause, a new file preamble) is
   subtracted from the saving, not omitted from it.
4. **Portability is not optional.** Every new or moved reference file must remain
   discoverable by the adapter build's citation fan-out and stay host-neutral, so all six
   adapter targets still resolve it.
5. **Don't weaken the guards.** Splitting a file creates a new way for two files to
   disagree. Each split shipped with a drift guard that fails when they do.

## Component Overview

Nothing new was packaged. The work lands entirely on surfaces that already existed:

```
scripts/forge-session.py            # R4: +7 state verbs   R5: +effective-config
references/
  pipeline-state-schema.json        # R4: contract, unchanged structurally
  forge-config-schema.json          # R5: default source, unchanged
  process-overview.md               # R3: read-site relocated; file unchanged
  shared-conventions.md             # R4: state-write blocks call verbs
skills/forge/SKILL.md               # R3 gate; R4 state-note
skills/forge-{0-epic,1-prd,2-tech,3-specs,4-backlog,5-loop,6-docs}/SKILL.md
                                    # R4 state verbs; R5 consumer swap (4-backlog, 5-loop)
skills/forge-verify/
  SKILL.md                          # R1: cites 6 mode files + findings-template.md
  references/verification-checklists/{prd,tech,specs,backlog,impl,epic}.md
  references/findings-template.md   # R1: orchestrator-only
skills/forge-5-loop/references/
  runner-contract.md                # R6: always-loaded half
  agent-selection.md                # R6: agent-conditional half
tests/                              # drift guards for every split/moved surface
```

The only genuinely new *contract* is the set of `forge-session.py` subcommands, documented
in the [CLI Reference](./cli-reference.md).

## R1 — Verification-checklist mode split

**Problem.** A single 477-line checklist file carried every verify mode's checks *and* the
orchestrator-only findings material. A verifier leaf running `prd` mode loaded all six
modes plus material it must never act on — and a parallel fan-out paid that cost per
instance.

**Decision.** One file per mode, plus one orchestrator-only file:

| File | Checks |
|------|--------|
| `verification-checklists/prd.md` | CHECK-P01…P15 (15) |
| `verification-checklists/tech.md` | CHECK-T01…T17 (17) |
| `verification-checklists/specs.md` | CHECK-S01…S38 (38) |
| `verification-checklists/backlog.md` | CHECK-B01…B27 (27) |
| `verification-checklists/impl.md` | CHECK-I01…I23 (23) |
| `verification-checklists/epic.md` | CHECK-E01…E10 (10) |
| `findings-template.md` | none — findings document template, example findings, epic-mode state-write detail |

No check was added, dropped, or renumbered. The IDs were copied across verbatim.

**Load path.** The `forge-verifier` **leaf** subagent is dispatched with a mode and reads
`references/verification-checklists/{mode}.md` — one file, and nothing that speaks to the
orchestrator's role. The **orchestrator** reads `findings-template.md` when it writes the
findings document. This keeps the dual-role separation (the "which role are you?" guard)
intact: the split moves material *away* from the leaf, so it cannot reintroduce
self-dispatch or leak orchestrator instructions into a verifier context.

**Self-check got stronger, not weaker.** The "executed N of M checks" self-check used to
carry approximate per-mode totals (it said `tech ~15` while the file actually held 17).
Each mode file now has an exact count, the skill's expected-count table matches it, and a
drift guard asserts both. A verifier that under-executes is now caught against a precise
number over a file it definitely loaded.

**Rejected:** inlining the orchestrator material into the `forge-verify` body — it was at
257/300 lines and this would have added ~150. Also rejected: keeping one file and slicing
by anchor, since the whole 477 lines still enter the subagent's context, which is the cost
the unit exists to remove.

## R3 — Conditional process-overview read

**Problem.** The navigator opened the 143-line `process-overview.md` as an unconditional
setup step. A dashboard render — the navigator's most common job, and one that needs no
pipeline theory at all — paid for it every time.

**Decision.** The read moved into a branch taken only when the user is asking how the
pipeline works: architecture, stage ordering, what a stage does, "explain forge". Routine
status rendering does not open it. The file itself is unchanged and still cited, so it
still ships to every adapter.

**The trade, stated honestly.** The gating clause is always-paid body growth (+40 tok on
*every* navigator invocation, including the architecture ones). A routine render nets
−1,684. An architecture question nets +40 and still loads the file. That is the correct
shape for a conditional read: a small fixed cost on both paths buys a large removal from
the common one.

## R4 — Targeted state verbs

**Problem.** Every stage wrote `.pipeline-state.json` by hand. To do that correctly a stage
had to know the shape — which is why the instructions pointed at a 191-line JSON Schema —
and had to *perform* rules that were only ever expressed as prose: bump the version,
refresh `updatedAt`, record `basedOnVersions`, set `commitHash` to null for commit 1, and
mark downstream stages stale when they were built on an older version. Each of those is a
chance for a model to write plausible-but-wrong JSON.

**Decision.** Seven targeted subcommands, one per touch point:

| Verb | Touch point | Writes |
|------|-------------|--------|
| `state-enter` | Entry stamp | `stages.{stage}.status=in-progress`, `startedAt`, top-level `currentStage` |
| `state-artifact` | Incremental artifact tracking | append to `stages.{stage}.artifacts`, de-duplicated |
| `state-complete` | Completion | `status`, `completedAt`, `version`, `basedOnVersions`, `artifacts`, `commitHash`, + staleness cascade |
| `state-branch` | Branch record | top-level `branch` |
| `state-note` | Free-text note | top-level `notes` |
| `state-decision` | Deferred decision | append to `deferredDecisions[]` |
| `state-ecr` | Epic change request | append to `epicChangeRequests[]` |

**Why targeted verbs rather than one generic patch command.** A generic `state-patch` would
leave the model authoring the JSON fragment — which is most of the defect surface the unit
exists to close. Each targeted verb is instead self-validating (its arguments *are* the
schema constraint), self-documenting at the call site, and a clean unit to test.

### The shared write path

Every verb follows the same sequence: resolve the feature directory → load state → mutate
→ refresh `updatedAt` → atomic write. Four properties of that path are load-bearing.

**The writer resolves fail-closed.** The read path's resolver is deliberately tolerant: on
an ambiguous name it falls back to the flat `{specsDir}/{feature}` path, which is safe for
a read-only sweep that can downgrade to "not started". A writer inheriting that tolerance
would mutate a standalone `{specsDir}/api/` while an epic member `{specsDir}/{epic}/api/`
of the same name was silently left behind — cross-feature state corruption at exit 0. So
the write path has its own resolver that refuses a multi-candidate match outright and tells
you to pass `--epic`. **This is why `--epic` is mandatory for epic members** on every verb.

**A corrupt state file is never overwritten.** The read path downgrades unparseable JSON to
`{}`; a writer that did the same would atomically replace a corrupt-but-recoverable file
with a near-empty one and exit 0. The write path refuses instead (exit 2) and leaves the
file byte-intact.

**A verb never creates a feature directory.** An unknown `--feature` is a usage error, not
a silent create.

**The first write is still schema-valid.** Branch Setup fires `state-branch` before the
entry stamp, so `state-branch` can legitimately be the first thing to touch a feature's
state. The shared loader seeds the schema-required top-level fields on every verb, so that
first write cannot persist a `{branch, updatedAt}`-only file.

### The staleness cascade

`state-complete` marks a downstream stage `stale` when its recorded
`basedOnVersions[completedStage]` is strictly less than the new version *and* it is
currently `complete`. The cascade scope is `forge-2-tech` … `forge-6-docs`: a PRD revision
invalidates the tech spec first, and nothing downstream feeds back into the PRD, so
`forge-1-prd` is never a cascade target. A stage that never referenced the completing
upstream, already references the new version, or is not `complete`, is untouched — only a
finished artifact can go stale. The cascade result is echoed to the caller but is not
itself persisted as state.

### `state-complete`'s three branches

The verb reads as one command but has three distinct modes, in precedence order:

1. **`--commit-hash` given** — commit 2 of the two-commit git protocol. Writes *only*
   `commitHash`, leaving status/version/artifacts intact, and refuses if the stage is not
   already `complete` (so a mistyped `--stage` cannot leave a lone `{"commitHash": …}`
   entry that violates the schema's required `status`).
2. **`--resumable`** — the failed-commit-1 revert. Records *only*
   `status: "in-progress"`: no `completedAt`, no version bump, no provenance or artifact
   write, no `commitHash` reset, no cascade. The frozen contract is "leave state resumable",
   and stamping a completion off a commit that never landed would be a behavior change.
3. **Otherwise** — the completion write, ending in `commitHash: null` (commit 1) and the
   cascade.

Branch 2 keys off `--resumable`, deliberately *not* off `status == "in-progress"`, because
`forge-5-loop`'s **partial** completion also passes `--status in-progress` while being a
real completion with artifacts and provenance. Conflating them would silently discard the
loop's `--based-on` record.

### What R4 did not change

The interactive protocol around each write is untouched. Stage-entry classification, the
branch prompts and their visible reconciliation note, the "offer a note, don't force one"
statement, and the two-commit git sequence (never `--amend`) all keep their prose and turn
structure — the verb call slots in exactly where "edit the JSON" was. The entry stamp is
still left uncommitted so an interrupted run is classified as interrupted on re-entry.

The state schema remains the CI source of truth. It is no longer *read per stage*, but the
verbs are asserted against it: a drift guard validates each verb's output with a
stdlib structural validator, so a verb that starts emitting non-conformant state fails CI
rather than a user's pipeline.

### Honest accounting

R4 is the clearest case where token savings are the *secondary* justification. The state
schema was read 2× across a 188-session corpus, not once per stage; three of the four
surfaces R4 touched are net *positive* in tokens because gating prose and inlined preludes
cost more than the removed citation saved. The unit stands on determinism: the version
bump, `updatedAt`, `commitHash: null`, and the cascade are computed rather than
transcribed, and every write is atomic and conformant by construction. That benefit does
not depend on how often the schema was being read.

## R5 — `effective-config`

**Problem.** `forge-4-backlog` and `forge-5-loop` needed the resolved `loopRunner`
configuration — 22 fields, each with a schema default that a project may override. The
instruction was to read the ~2k-word config schema and merge the defaults, which is both
expensive and a live source of "the model mis-merged the defaults" errors.

**Decision.** `forge-session.py effective-config` reads
`properties.loopRunner.properties.*.default` from the schema at runtime, merges the
project's `loopRunner` block over the top, and prints the result. The **script** reads the
schema, so no skill has to — and because the schema is the input rather than a hardcoded
table, it stays the single source of truth with no duplication to drift.

Resolution is stdlib-only (`json.load` plus dict access — the CI environment has no
`jsonschema`), and a user field replaces a default one-for-one. An unknown key is carried
through rather than dropped: a model would have carried it too, and the config schema is
the authority that flags it at author time.

**Failure posture.** A missing or corrupt `forge.config.json` is *not* an error — it
resolves to pure defaults and exits 0, which is exactly what an unconfigured project
should get. An unreadable, unparseable, or `loopRunner`-less schema *is* fatal (exit 2),
because then there are no defaults to resolve and emitting a partial merge would be worse
than failing. The unit never silently returns half a config.

**Rejected:** hardcoding the 22 defaults in Python — needless duplication of a schema that
is already machine-readable.

## R6 — Runner-contract split

**Problem.** The 341-line runner contract carried three sections that only mean anything
when agent selection is enabled: the agent-selection surface, its Claude-only model-alias
guard, and the optional-flags catalog. Every loop launch loaded them.

**Decision.** Those three sections moved to `agent-selection.md` (116 lines).
`runner-contract.md` (248 lines) keeps what every launch needs: model-selection precedence,
run mode, launch detail, monitor arming, event reactions, and the inform-user template.
`agent-selection.md` is cited **only from inside the capability gate** in the
`forge-5-loop` body, so a gate-off run never opens it. The model-selection pointer above
the gate still points only at `runner-contract.md`.

**Cap constraint.** The `forge-5-loop` body sits at 298/300 lines and ~4,560/5,000 words —
CI hard-fails on either limit. R6's body edit was therefore a strict citation swap with no
net lines added, and no runner-contract text was pushed back into the body.

### R6's saving is conditional on a non-default config

This is the finding most worth carrying forward. "Not loaded by default" is true of the
*file open*, but the gate condition — a non-empty effective `loopRunner.agentArgument` — is
**satisfied by the config schema's own default**, `--agent {agent}`. So on a
default-configured project:

- the gate is **on**,
- `agent-selection.md` **is** opened, and all 116 of its lines load,
- the two nested sections are gated for *application*, not for *load* (the model-alias
  guard is an `###` inside the agent-selection section; the flags catalog follows it in the
  same file).

The realized instruction-load saving on a default-config run is therefore **approximately
zero** — marginally negative, against the new file's preamble. A gate-off launch nets
−1,151 tok; a gate-on launch nets **+98**. A project only lands on the saving by explicitly
blanking `loopRunner.agentArgument`. R6 still delivers the structural win (the conditional
material is now separable, and the gate is real), but quoting −1,151 as typical would be
wrong.

## R2 — scoped out

**R2 does not ship.** The proposal was to leave the first plugin-root prelude in a file
verbatim and reduce later occurrences in the same file to a compact pointer.

It was gated on a compliance probe, which cleared the stated objection — all five runs
resolved the root correctly and executed clean — but byte-identity came back 4/5, so the
"byte-identical to today" claim is not unconditionally true. The deciding argument is the
risk/reward the probe left standing: R2 was the smallest payoff of the six (~2k tokens
across four files) and the only one that converts a *verbatim copy* into a
*reconstruct-from-memory* operation. The same baseline work found that the productive
direction is removing compliance-dependent operations, so adding one for the smallest gain
runs against the evidence.

Dropping it cost nothing structurally, because each unit was required to be independently
shippable from the start. The `r2-prelude` probe remains in
`eval/run-compliance-eval.py` as the gate if the idea is ever revived — it should be
re-run at a larger sample size first, since 4/5 on n=5 is a wide interval.

**Read R2's absence from the code as intended, not as a coverage gap.**

## Drift-guard coverage

Splitting a file creates a new way for two files to disagree, so each unit shipped with a
guard. All are stdlib pytest, asserting against the canonical `skills/` surfaces rather
than generated `adapters/` output.

| Guard | What it fails on |
|-------|------------------|
| `tests/test_verification_checklists_split.py` | A mode file losing or gaining a CHECK-ID, cross-mode leakage, the skill's expected-count table disagreeing with the per-file totals, orchestrator sections appearing in a mode file. |
| `tests/test_process_overview_read.py` | An unconditional `process-overview.md` read reappearing in the navigator, or the file losing its citation. |
| `tests/test_effective_config.py` | The defaults/overrides merge, the exit-0-on-missing-config contract, and the exit-2-on-unreadable-schema contract. |
| `tests/test_state_verbs.py` | The shared write machinery and every verb's CLI contract (77 tests). |
| `tests/test_state_schema_conformance.py` | A verb emitting state that does not validate against `pipeline-state-schema.json`; the schema's structural digest changing. |
| `tests/test_state_verb_call_sites.py` | A `state-*` call site missing its `--epic` mandate; the documented failure-protocol clauses or exit-2 messages disappearing. |
| `tests/test_stage_constants_parity.py` | The two flat scripts' duplicated stage-order and verify-status constants drifting apart, or from the schema enum. |
| `tests/test_runner_contract_split.py` | A runner-contract section lost in the split; `agent-selection.md` cited outside the capability gate; the `forge-5-loop` body crossing the line cap. |
| `tests/test_reference_citations.py` | A citation naming a file that does not exist, or a reference file no skill cites (which would silently unship it from the non-Claude adapters). |
| `tests/test_always_loaded_surface.py` | Growth in the always-loaded surface — the frontmatter descriptions and the session hook's common-path output. |

These sit alongside the pre-existing gates, which are constraints rather than tests of this
feature: `scripts/check-spec-purity.py` Rule 4 (body ≤300 lines **and** ≤5,000 words),
Rule 5 (prelude byte-identity), and Rule 6 (a shell fence using `$R` must bind it
in-fence); `ruff check scripts/ eval/`; and `bash scripts/validate.sh`, which includes the
adapter regen-and-diff check.

## Scope Boundaries

Deliberately **not** in this feature:

- **Restructuring `shared-conventions.md`** into a thin core plus per-block files. The
  highest-payoff remaining candidate, and the only structurally risky one — it carries a
  mandatory prototype gate and belongs to its own follow-up.
- **Trimming epic dependency-spec loading.** Bounding context injection to *direct*
  dependencies is a deliberate product decision, not waste. Revisit only with transcript
  evidence.
- **Consolidating the duplicated epic-backflow paragraph** in `forge-1-prd` /
  `forge-2-tech`. Roughly token-neutral; not worth a change until a body hits the line cap.
- **Any change to interactive behavior.** Content may move; it must not change.
- **The frontmatter descriptions and the session hook** — the only always-loaded surfaces,
  already minimal and already silent. Guarded against growth rather than shrunk.
- **Non-Claude adapter behavior**, beyond mechanical regeneration.
