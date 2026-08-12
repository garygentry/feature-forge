# verify-fix-sweep — Traceability Matrix

Every PRD requirement mapped to the spec document(s) and section(s) that implement it.
**Primary** is where the implementing detail lives; **Supporting** is where the contract
is defined or tested. Verified by `scripts/validate-traceability.py` (16/16 covered,
zero orphans) at suite completion.

| REQ ID | Requirement (short) | Primary | Supporting |
|---|---|---|---|
| REQ-SWEEP-01 | Sweep extracts corrected text from the fix delta, runs in the fix pass | `02-fix-sweep-script.md` §4.1–§4.2, §4.7 | `00-core-definitions.md` §3–§4; `03-forge-fix-integration.md` §4.1, §4.6 |
| REQ-SWEEP-02 | Deterministic normalized matching, min-length floor, reflow caught | `02-fix-sweep-script.md` §4.2–§4.6 | `00-core-definitions.md` §2, §4.3, §5.3; `05-testing-strategy.md` §2.3–§2.4 |
| REQ-SWEEP-03 | Corpus = tracked+untracked minus `.verification/` + drift-gated trees | `02-fix-sweep-script.md` §4.4 | `00-core-definitions.md` §5.1–§5.2; `05-testing-strategy.md` §2.2, §2.6 |
| REQ-SWEEP-04 | Every survivor dispositioned before the pass closes | `03-forge-fix-integration.md` §4.3–§4.4 | `00-core-definitions.md` §8.1; `05-testing-strategy.md` §2.11 |
| REQ-SWEEP-05 | Sweep record + dispositions recorded in the findings document | `03-forge-fix-integration.md` §4.2, §5 | `00-core-definitions.md` §7.2; `05-testing-strategy.md` §2.11 |
| REQ-SWEEP-06 | Unresolved survivors route through existing outcome rows | `03-forge-fix-integration.md` §6 | `00-core-definitions.md` §8.2 |
| REQ-SWEEP-07 | No-delta skip is a visible notice, never silent | `02-fix-sweep-script.md` §3 (skip shape); `03-forge-fix-integration.md` §4.5 (notice) | `00-core-definitions.md` §6.1, §7.2; `05-testing-strategy.md` §2.5, §2.11 |
| REQ-CARD-01 | Fix Execution Plan covers every finding; totals re-derived; omissions named | `02-fix-sweep-script.md` §5 (`plan-coverage`); `03-forge-fix-integration.md` §3 (Step 2 gate) | `00-core-definitions.md` §6.2, §7.1; `05-testing-strategy.md` §2.7 |
| REQ-CARD-02 | Backlog-mode cardinality CHECK | `04-verification-checks.md` §3.1 (CHECK-B29) | `00-core-definitions.md` §9; `05-testing-strategy.md` §2.11, §3 |
| REQ-CARD-03 | Impl-mode cardinality CHECK | `04-verification-checks.md` §3.2 (CHECK-I24) | `00-core-definitions.md` §9; `05-testing-strategy.md` §2.11, §3 |
| REQ-CARD-04 | Cardinality checks degrade to not-applicable | `04-verification-checks.md` §3.1–§3.2 (step 1), §6 | `00-core-definitions.md` §9; `02-fix-sweep-script.md` §5.2 (`applicable: false`); `05-testing-strategy.md` §2.7 |
| REQ-CONS-01 | Internal-consistency CHECKs in specs + impl checklists | `04-verification-checks.md` §3.3 (CHECK-I25), §3.4 (CHECK-S39) | `00-core-definitions.md` §9; `05-testing-strategy.md` §2.11, §3 |
| REQ-PERF-01 | Cheap, deterministic, no network/model; seconds at repo scale | `02-fix-sweep-script.md` §7 | `00-core-definitions.md` §5.3; `05-testing-strategy.md` §2.10, §5 |
| REQ-OBS-01 | Every hit names file, location, matched removed text | `02-fix-sweep-script.md` §2.3, §4.6–§4.7 | `00-core-definitions.md` §6.1; `05-testing-strategy.md` §2.2, §2.8 |
| REQ-CONC-01 | Read-only over corpus; single-writer; no locking | `00-core-definitions.md` §1 | `02-fix-sweep-script.md` §1, §3; `05-testing-strategy.md` §2.9 |
| REQ-SEC-01 | Matched text echoed verbatim; no elision; not a secret scrubber | `00-core-definitions.md` §6.1 | `02-fix-sweep-script.md` §2.3, §4.6; `05-testing-strategy.md` §2.8 |

## Constraint coverage (tech-spec bindings, not REQ ids)

| Constraint | Where honored |
|---|---|
| C-1 (R-06 untouched) | `03-forge-fix-integration.md` §1.2, §9; `01-architecture-layout.md` §2 (out-of-bounds list) |
| C-2 (no model) | `02-fix-sweep-script.md` (deterministic throughout); `04-verification-checks.md` §1 |
| C-3 (stdlib-only, `scripts/`) | `00-core-definitions.md` §1; `01-architecture-layout.md` §1, §5 |
| C-4 (line/word budgets) | `01-architecture-layout.md` §4; `03-forge-fix-integration.md` §7 (projected 167/300); `04-verification-checks.md` (zero-net-new-line, 298/300 held) |
| C-5 (canon build discipline, host neutrality) | `01-architecture-layout.md` §5.2; `04-verification-checks.md` §2; `05-testing-strategy.md` §3 (host-neutrality row) |
| C-6 (schema stability) | `00-core-definitions.md` §1, §8.2; `03-forge-fix-integration.md` §6; `05-testing-strategy.md` §2.11 (outcome-table guard) |

## Known deltas from the tech spec (recorded resolutions, not gaps)

1. **Two fenced invocation blocks, not one** (`03-forge-fix-integration.md` §7):
   `check-spec-purity.py` requires each shell fence to bind `$R` in-fence, so Step 2
   and Step 4 each carry a prelude. The tech-spec §3.6 line-estimate *range* (25–35)
   still holds at 33 projected lines.
2. **Six pinned test files, not five** (`05-testing-strategy.md` §3): the tech-spec §2
   table enumerates five; `tests/test_adapter_host_neutrality.py` is listed as a
   sixth row explicitly to record that it needs **no** edit (host-neutral prose is
   authored, not exempted).
3. **Hit identity** (`02-fix-sweep-script.md`): one hit per distinct `(file, needle)`
   at first match offset — chosen to align with the `(file, needle)` re-run
   disposition matching in `00-core-definitions.md` §7.2.
4. **Claimed totals = `Total findings: N` only** (`00-core-definitions.md` §6.2,
   `02-fix-sweep-script.md` §5.2): `plan-coverage` re-derives `## Summary`'s
   `Total findings: N` and nothing else, per recorded Decision 3. Tech-spec §3.5's
   "and the per-severity counts when present" parenthetical is a tech-spec residual
   tracked as V-103 in `.verification/VERIFY-tech-2026-08-10-round2.md` — not a
   specs-suite gap.
