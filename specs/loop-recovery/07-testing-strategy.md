# 07 — Testing Strategy

> **HOW this feature is proven.** `loop-recovery` touches state (a new schema-backed
> record), the loop outcome vocabulary and its directive matrix, two pure graph
> functions, a new runner subcommand in a second repo, and the compliance eval. This
> document is the test matrix across all of it: the R4 conformance/schema guards, the
> topology/clustering unit tests, the stage-exit routing ripple, the rauf-side
> subcommand tests, and the new `loop-outcome` compliance probe that keeps the new
> outcome from shipping unmeasured (REQ-EVAL-01, the #176 lesson). It also carries the
> two forge-2-tech re-verify advisories the pipeline parked for this stage: **V-012**
> (the outcome-count test rename) and **V-015** (the vendored clustering fixture).
>
> **Stdlib-only pytest.** CI has no third-party deps; `jsonschema` behavioral tests use
> `importorskip` as today, and all schema conformance goes through
> `tests/_state_schema.py`'s hand-rolled validator (`00-core-definitions.md §10`). Every
> subprocess test invokes `sys.executable`, never a bare `python3`.

## Requirement Coverage

| REQ ID | Requirement | Section |
|--------|-------------|---------|
| REQ-EVAL-01 | New outcome measured by a compliance probe | §6 (loop-outcome probe + fixture) |
| REQ-STATE-01 | Schema + verb + conformance test | §2 (schema + conformance) |
| REQ-DEC-01..07 | Decision-record behavior proven | §2 (conformance sequences) |
| REQ-UNB-01..03 | Per-item unblock proof proven | §3 (stage-exit + rauf), §5 (rauf) |
| REQ-OUT-01..03 | Resolved outcome/routing/gate | §4 (stage-exit routing) |
| REQ-ATTR-01..04 | Starvation attribution + `--cause` | §4 (`--cause` matrix), §7 (topology) — see `06`/`03` |
| REQ-CLU-01 | Deterministic clustering substrate | §7 (clustering unit tests, V-015 fixture) |
| REQ-TOPO-01..03 | Topology metrics + warn triggers | §7 (topology unit tests + observed-incident fixture) |
| REQ-COMPAT-01 | Directive-matrix guard updated deliberately | §4 (protocol test + EXIT_OUTCOMES mirror) |
| REQ-COMPAT-02 | Clean-tree happy path unchanged but for depth line | §8 (SC-4 baseline) |
| REQ-PERF-01 | Topology/cluster linear + bounded | §7 (complexity assertions) |
| REQ-OBS-01 | Report surfaces cite authoritative counts | §4/§7 (assertions on citation fields) |
| all Success Criteria | SC-1..SC-4 replay & baseline | §8 |

---

## 1. Scope, Framework & Layout

- **Framework:** `pytest`, stdlib only. Fixtures via `conftest.py`; module loading of
  `scripts/forge-session.py` via the existing `importlib`/`_forge_paths` helpers the
  current tests use (see `tests/test_state_verbs.py`, `tests/_forge_paths.py`).
- **Location:** all under `tests/`, co-located flat `test_*.py` (repo convention — no
  `src/` tree). rauf tests live in the rauf repo alongside its backlog-command tests.
- **Verification commands** (the merge bar): `bash scripts/validate.sh` (spec purity,
  adapter non-drift, pytest, ruff, traceability) + `python3 scripts/forge-session.py
  doctor --json` (smoke). CI's Quality Gate additionally runs
  `ruff check scripts/ eval/` and `check-spec-purity.py`.

New / edited test files (from `01-architecture-layout.md §1.4`):

| File | Kind | Proves |
|------|------|--------|
| `tests/test_forge_decisions_schema.py` | NEW | schema structure (§2.1) |
| `tests/test_decisions_schema_conformance.py` | NEW | R4 drift guard for `decision-*` (§2.2) |
| `tests/test_backlog_topology.py` | NEW | `compute_topology` metrics + warns (§7.1) |
| `tests/test_decision_clustering.py` | NEW | Jaccard clustering + V-015 fixture (§7.2) |
| `tests/test_stage_exit.py` | EDIT | resolved routing + `--cause` matrix + **V-012 rename** (§4) |
| `tests/test_stage_exit_protocol.py` | no code change | its `:379-388` assertion forces the `SKILL.md:271` ladder edit (§4.3) |
| `tests/test_lifecycle_artifact_check.py` | EDIT | `27`→`28` literal assertions (§7.3) |
| `tests/test_compliance_eval.py` | EDIT | `--probe all` list `+= run_loop_outcome_probe` (§6) |
| rauf `packages/cli` tests | EDIT | `backlog answer` (§5) |

## 2. Decision-record: schema + R4 conformance (REQ-STATE-01, REQ-DEC-01..07)

### 2.1 `tests/test_forge_decisions_schema.py` (structural)

Mirrors `tests/test_pipeline_state_schema.py`. Loads `references/forge-decisions-schema.json`
and asserts, structurally (no runner, no verbs):

- Top-level `additionalProperties: false`; required set is exactly
  `{schemaVersion, feature, createdAt, updatedAt, decisions}`.
- `schemaVersion` enum is exactly `["1"]`.
- `decisions.items.$ref` → `#/definitions/decision`; the `decision` definition sets
  `additionalProperties: false` and required
  `{itemId, question, answer, deferred, decidedAt, recordedBy, appliedAt, appliedBy}`
  (`clusterId` is optional — present in `properties`, absent from `required`).
- `answer`/`appliedAt`/`appliedBy` accept `["string","null"]`; `deferred` is boolean.
- The schema uses **only** the draft-07 subset `tests/_state_schema.py` supports (a
  guard assertion: no `oneOf`/`anyOf`/`pattern`/`format` key appears) — so the
  conformance validator can never silently pass an unvalidated construct.

### 2.2 `tests/test_decisions_schema_conformance.py` (R4 drift guard)

Clones `tests/test_state_schema_conformance.py`'s structure exactly (out-of-process
`_run()` via `sys.executable`, a temp backlog dir, output validated through a **new**
`validate_decisions()` wrapper in `tests/_state_schema.py`). It asserts:

- **Registry-completeness** (the anti-#181 guard): a regex scan of `forge-session.py`
  for `add_parser("decision-…")` proves every registered `decision-*` verb appears in
  this test's `VERB_INVOCATIONS` — a new verb with no conformance coverage fails CI.
- **Single-invocation conformance:** each verb's output file validates against the
  unchanged schema.
- **Realistic multi-verb sequences** (the defects a single-call test misses):
  1. `record --answer` → file has the 5 top-level fields + one fully-formed entry
     (`appliedAt: null`).
  2. `record --deferred` for a second item → `answer: null, deferred: true`.
  3. `record --answer` **again** for item 1 (re-raised) → **append**, not overwrite;
     the earlier entry's audit fields are byte-identical (append-only, REQ-DEC-07).
  4. `apply --item 1` → stamps `appliedAt`/`appliedBy` on the **latest** item-1 entry
     only; every other entry untouched.
  5. `list --unapplied` → returns exactly the latest-per-item entries where
     `appliedAt == null` (item 2's deferral present; item 1 absent after apply).
- **First-write edge cases:** verbs against an absent file create it with the top-level
  stamp; a `--cluster CID` on two `--item`s writes the shared `clusterId` (REQ-CLU-04).
- **Failure exits (REQ-REL-02 write side):** `apply` with nothing unapplied for the id →
  exit 2, `Error:` on stderr, file unchanged; `record` with both `--answer` and
  `--deferred` (and with neither) → exit 2 before any write.

`tests/_state_schema.py` gains `_DECISIONS_SCHEMA` (loaded like `_STATE_SCHEMA`/
`_CONFIG_SCHEMA`, lines 26–31) and `validate_decisions()` (~12 lines mirroring
`validate_state`); the module docstring's "Both entry points" / "state verbs and
effective-config" scoping updates to cover **three** schemas.

## 3. Apply & per-item unblock proof (REQ-UNB-01..03, REQ-REL-02)

The forge-side apply/proof logic (`04-apply-and-unblock.md`) is exercised with the rauf
CLI **stubbed** (unit tests do not require a live rauf): a fake `listCommand`/
`versionCommand`/`answer`/`unblock` returning canned JSON. Assertions:

- **Version dispatch:** probe → `≥ RECOVERY_MIN_RUNNER_VERSION` selects `backlog answer`;
  below it selects the degraded `backlog unblock` and the report states the answer was
  **not** prompt-injected + carries the `installHint`.
- **Per-item proof (REQ-UNB-02):** after apply, the re-read tests **each** affected item
  `status != "blocked"`. A stub where item A moved but item B did not → **failed
  recovery** naming A as mover and B as non-mover (REQ-UNB-03); the aggregate count is
  never consulted (a fixture where the count is unchanged but items swapped still fails).
- **Failed apply vs nothing-moved (REQ-REL-02):** a stub `answer` exiting non-zero stops
  **before** the per-item test (failed apply, verbatim error); a stub `answer` exiting 0
  but leaving the item blocked fails **at** the per-item test (ran-but-nothing-moved) —
  the two are distinctly reported.
- **`decision-apply` ordering (REQ-UNB-01):** the record is stamped applied **only after**
  the runner apply returns success (a failing apply leaves `appliedAt: null`, so the item
  re-surfaces via `--unapplied`).

Live end-to-end apply (real rauf 0.14.0) is a manual dogfood step (§8, SC-1), not a CI
gate — CI stays stdlib-only.

## 4. Stage-exit routing ripple (REQ-OUT-01..03, REQ-ATTR-04, REQ-COMPAT-01)

`tests/test_stage_exit.py` edits (the derived-enum ripple is the point — it must NOT be
weakened silently, REQ-COMPAT-01):

### 4.1 The mirrored enum + its downstream tests

- `EXIT_OUTCOMES["forge-5-loop"]` mirror at `:626` gains `"resolved"`, which automatically
  extends the derived `NON_COMPLETE_LOOP_OUTCOMES` at `:2305` and therefore
  `test_no_non_complete_loop_outcome_claims_downstream_readiness` (`:2372`) and
  `test_a_non_complete_loop_outcome_states_nothing_downstream_is_ready` (`:2473`) — both
  now assert over `resolved` too, with no test-body change (they iterate the derived set).
- **V-012 (carried advisory):** the parametrized `test_loop_accepts_exactly_the_five_loop_
  outcomes` (`tests/test_stage_exit.py:2341`) is **renamed** to
  `test_loop_accepts_exactly_the_six_loop_outcomes` and its parametrize list gains
  `"resolved"`. This rename is **mandatory**, not cosmetic: left unrenamed the test keeps
  a stale "five" contract and goes green silently against a six-member enum, hiding a
  future accidental drop of an outcome. (Grep the repo for any other `five`/`5`-outcome
  literal in test names or asserts and update in lockstep.)

### 4.2 Resolved routing + `--cause` matrix

- **Resolved routes resume — the hand-listed parametrizes that need `"resolved"`.** The
  derived `NON_COMPLETE_LOOP_OUTCOMES` (`:2305`) auto-covers the derived tests, but three
  **hand-listed** sites do not and must each gain `"resolved"`: the `EXIT_OUTCOMES`
  mirror (`:626`), the resume-fence parametrize
  `test_loop_partial_and_deferred_fence_the_loop_resume` (`:2348`, the resume-routing
  assertion — primary = `/feature-forge:forge-5-loop {feature}`, never the navigator), and
  the no-continuation invariant `test_a_non_complete_loop_outcome_still_offers_no_continuation`
  (`:3207`, parametrized over all non-complete outcomes). The recover-fence parametrize
  (`:2358`) deliberately does **not** gain it — `resolved` is not a recover outcome.
- **`--cause` validity matrix:** `--cause dependency-starvation` is **accepted** on
  `--stage forge-5-loop --outcome partial` (swaps to the starvation sentence) and
  **exits 2** on every other stage/outcome combination — a table-driven test enumerates
  accepted vs rejected pairs. The rejection is asserted to occur **before** any payload
  output (exit 2, empty stdout, `Error:` on stderr).
- **Resolved outcome text:** asserts `_LOOP_OUTCOME_TEXT["resolved"]` renders, names the
  relaunch, and states nothing downstream is ready (no downstream-readiness wording).

### 4.3 The protocol test forces the body edit (REQ-COMPAT-01)

`tests/test_stage_exit_protocol.py` needs **no code change**: its canon-derived
outcome-domain assertion (`:379-388`) reads the loop outcome domain from the SKILL body
copy at `skills/forge-5-loop/SKILL.md:271`. It will **fail** until that ladder line gains
`resolved` — which is exactly why the `03`/`05` body edit is mandatory, not optional
prose. This test is the tripwire that keeps the two ladder copies in sync.

## 5. rauf `backlog answer` (REQ-UNB-01, rauf repo)

In the rauf repo, alongside the existing backlog-command tests
(`packages/cli` tests, per `04-apply-and-unblock.md §1.5`):

- **Happy path:** `backlog answer <path> <id> "<text>"` on a `blocked` item sets
  `humanAnswer: text, status: "pending", needsHuman: false, blockedReason: null` and does
  **not** relaunch; `--json` emits `{ answered: "<id>", status: "pending" }`.
- **Not-blocked refusal:** the same on a non-`blocked` item exits non-zero with a message
  and mutates nothing (mirrors `unblockItems`' not-blocked guard).
- **Missing item:** unknown id exits non-zero with a message.
- **Transition legality:** the `blocked → pending` transition is already legal in
  `VALID_STATUS_TRANSITIONS`; a regression asserting that pairing stays covered.

## 6. Compliance eval — the `loop-outcome` probe (REQ-EVAL-01)

The new outcome must bite on every full sweep (decision V-004). In
`eval/run-compliance-eval.py`:

- **New probe `run_loop_outcome_probe`** + fixture
  `eval/fixtures/compliance/loop-outcome-resolved.json`. The probe drives a forge-5-loop
  close with `--outcome resolved` and scores (a) **exactly one** sentinel
  (`─ forge: end of stage ─`), (b) **nothing** after it, (c) the primary command is the
  fenced relaunch `/feature-forge:forge-5-loop {feature}`.
- **Own required-key set:** the fixture declares `{schemaVersion, feature, scenarios}`
  with per-scenario `{name, outcome, expectedPrimaryCommand}`, read by its **own** loader
  that shares only the hard-fail `schemaVersion` guard idiom with the branch-path reader
  (`run-compliance-eval.py:996, 1109-1112`). It is **not** a mirror of
  `verify-fix-reverify.json` (whose `servedStage`/`verifyMode` keys don't apply).
- **Joins `--probe all`** (REQ-EVAL-01 must bite on the full sweep): the three→four update
  lands in all four places, in lockstep:
  1. the module "Three probes" docstring (line 9) → "Four probes";
  2. the usage string (line 55) → adds `|loop-outcome`;
  3. the argparse `--probe` `choices` (line ~1936) → adds `"loop-outcome"`;
  4. the `all` dispatch (lines ~1976-1980) → `report.probes.extend(run_loop_outcome_probe(...))`.
- **`tests/test_compliance_eval.py`** exact-equality guard (`:1948-1954`): the monkeypatched
  probe-name list and the `assert calls == [...]` add `"run_loop_outcome_probe"` as the
  fourth entry (order matches the `all` dispatch). A single-probe `--probe loop-outcome`
  case asserts it runs alone.

The probe runs via the existing advisory harness (it does not block CI on model behavior);
its **presence** and the argparse/`all`-list wiring are what `test_compliance_eval.py`
enforces deterministically.

## 7. Topology & clustering unit tests (REQ-TOPO-01..03, REQ-CLU-01, REQ-PERF-01)

### 7.1 `tests/test_backlog_topology.py`

`compute_topology` loaded via `importlib`. Graph fixtures: **line**, **diamond**,
**parallel roots**, **trivial** (single node / no edges), and a **cycle** fixture (the
visited-set guard must terminate even though rauf normally rejects cycles). Assertions:

- `rootCount`, per-root `gatedCount`/`gatedIds`, `maxChainDepth`, `itemCount`, and the
  status-aware `selectable` (pending items whose `dependsOn` are all `done`, REQ-ATTR-01).
- **Warn triggers:** `single-root-fanout` fires iff a root's `gatedCount ≥ ceil(0.5·
  itemCount)`; `chain-depth` fires iff `maxChainDepth ≥ ceil(0.5·itemCount)`; neither
  fires on the trivial graph (`not-applicable`).
- **The observed-incident fixture** (feeds SC-1): 16 items, 3 roots gating 81%, a 13-deep
  chain. Asserts **both** warn tokens fire, `selectable == 0`, and `starvation.starved`
  with `blockingRoots` naming the three roots — the exact shape the starvation report
  (`03`) and the consolidated prompt (`05`) consume.
- **Determinism:** output `roots`/`clusters` ordering is by lowest member id and is stable
  across shuffled input (no dependence on dict/hash order).
- **Performance (REQ-PERF-01):** an assertion that a synthetic ~1000-item chain computes
  well under a generous wall-clock bound (linear memoized DFS) — a guard against an
  accidental O(n²) regression, not a benchmark.

### 7.2 `tests/test_decision_clustering.py`

`cluster_blocked` loaded via `importlib`. Assertions:

- **Normalization:** lowercase; split on non-alphanumeric; pure-number tokens (`^\d+$`)
  and item-id-shaped tokens (`^[a-z]*\d+$`) dropped; token **set** (dedup within an item).
- **Jaccard boundary:** a pair at exactly `0.5` clusters (the `≥` boundary); a pair just
  below does not.
- **Union-find transitivity:** A~B and B~C but A≁C directly still yields one cluster
  {A,B,C}.
- **Determinism:** items processed in id order; clusters emitted sorted by lowest member
  id; ties never depend on hash order.
- **V-015 — the vendored one-cause-three-phrasings fixture (carried advisory):** three
  `blockedReason` strings are copied **verbatim** from the actual verify-test-debt run
  (they are vendored **into the test file**, not read from the `.rauf` archive, which is
  prunable) and must cluster into **exactly one** candidate. Because the binding pair
  clears `CLUSTER_JACCARD_THRESHOLD = 0.5` by only ~0.028, the test **pins the constant to
  the incident**: a comment records the measured Jaccard so a future threshold change that
  would re-split the incident is caught. This is the calibration that makes
  `CLUSTER_JACCARD_THRESHOLD` falsifiable against the failure that motivated REQ-CLU, not
  merely asserted.
- **Under-clustering is acceptable, over-clustering is not:** a fixture of two genuinely
  distinct causes must **not** merge (the agent holds merge authority; the scripted floor
  must never over-merge).

### 7.3 `tests/test_lifecycle_artifact_check.py` (count-literal lockstep)

The `"backlog 27"` / `"backlog: 27 checks"` literal assertions at `:49-52` become `28`,
in the **same change** as the two `skills/forge-verify/SKILL.md` literals (`:33`, `:171`)
and the new CHECK-B28. A guard against a split-brain where the body says 28 but the test
still asserts 27 (or vice-versa).

## 8. Success-criteria replay & baseline (SC-1..SC-4)

- **SC-1 (issue replay):** the observed-incident fixture (§7.1) is the substrate for
  replaying each of the seven issues' "Observed in" scenarios against a backlog reproducing
  the observed topology (3 roots, 13-deep chain, one shared blocking cause) — asserting the
  required behavior now occurs (decision persisted; items provably unblocked per item; tree
  reconciled; resolved routed resume; starvation named; one consolidated prompt; topology
  reported). The scripted portions live in the unit tests above; the end-to-end apply
  against real rauf 0.14.0 is a manual dogfood step recorded in `progress.md`.
- **SC-2:** `bash scripts/validate.sh` green — including the new schema-conformance and
  directive-matrix tests; `adapters/` regenerated and drift-free.
- **SC-3:** the `loop-outcome` probe (§6) passes.
- **SC-4 (REQ-COMPAT-02):** **capture a clean-tree happy-path run transcript BEFORE
  merging** (no needs-human, no blocked, nothing stranded) and assert post-change
  equivalence **modulo the Step 2a depth line** — the only sanctioned new happy-path
  output. This baseline is the compat tripwire; it must be captured on the pre-change tree
  because it cannot be reconstructed after.

## Dependencies

- `00-core-definitions.md` — schema, enum, constants, output shapes under test.
- `02-decision-record.md` — the verbs the conformance guard drives.
- `03-outcome-and-attribution.md` — the routing/`--cause` behavior §4 asserts.
- `04-apply-and-unblock.md` — the apply/proof logic §3/§5 exercise.
- `05-recovery-procedure.md` — the SC-1 replay scenario.
- `06-clustering-and-topology.md` — the functions §7 tests.

## Verification

- [ ] `bash scripts/validate.sh` green: all NEW tests present and passing; adapter
      non-drift; ruff clean over `scripts/`+`eval/`; spec purity within body caps.
- [ ] The R4 registry-completeness scan fails if a `decision-*` verb is added without a
      `VERB_INVOCATIONS` entry (prove by temporarily adding a dummy verb locally).
- [ ] `test_loop_accepts_exactly_the_six_loop_outcomes` exists (no lingering `five`); the
      derived non-complete tests iterate a 6-member enum.
- [ ] `test_stage_exit_protocol.py:379-388` passes **only** after the `SKILL.md:271` ladder
      gains `resolved`.
- [ ] The V-015 fixture clusters the three vendored strings into exactly one candidate; a
      comment records the measured Jaccard margin (~0.028 over 0.5).
- [ ] `test_compliance_eval.py` asserts a four-entry `--probe all` list ending in
      `run_loop_outcome_probe`; `--probe loop-outcome` runs it alone.
- [ ] The three count literals (`SKILL.md:33`, `SKILL.md:171`, `test_lifecycle_artifact_
      check.py:49-52`) all read `28` — no split-brain.
- [ ] SC-4 baseline transcript captured on the pre-change tree and referenced by the
      equivalence assertion.
