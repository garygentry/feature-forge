# Stage Exit Coverage — Traceability Matrix

> PRD v2 → implementation specification suite. Every PRD requirement is mapped to its
> primary implementation contract and its final verification matrix. Supporting shared
> types and file ownership are in `00-core-definitions.md` and
> `01-architecture-layout.md`.

| Requirement | Implementation specification | Verification specification |
|---|---|---|
| REQ-EXIT-01 | `02-stage-exit-routing.md` §2–§3 — seven production stages accepted | `07-testing-strategy.md` §3.1, §6.1 |
| REQ-EXIT-02 | `02-stage-exit-routing.md` §2–§3 — direct verify/fix accepted | `07-testing-strategy.md` §3.1–§3.2, §6.1 |
| REQ-EXIT-03 | `02-stage-exit-routing.md` §4, §6 — one sentinel-last direct exit | `07-testing-strategy.md` §3.3, §6.1, §7.2 |
| REQ-EXIT-04 | `02-stage-exit-routing.md` §4 — outer/nested ownership | `07-testing-strategy.md` §3.3, §6.1, §7.2 |
| REQ-EXIT-05 | `02-stage-exit-routing.md` §5–§6 — Claude/Pi/generic rendering | `07-testing-strategy.md` §3.4, §6.3 |
| REQ-EXIT-06 | `02-stage-exit-routing.md` §5–§6 — verify-first primary command | `07-testing-strategy.md` §3.4 |
| REQ-EXIT-07 | `02-stage-exit-routing.md` §5 — capability-aware Standard Verify Gate | `07-testing-strategy.md` §3.4, §6.2–§6.3 |
| REQ-ROUTE-01 | `02-stage-exit-routing.md` §3, §6 — explicit served stage | `07-testing-strategy.md` §3.2 |
| REQ-ROUTE-02 | `02-stage-exit-routing.md` §3 — unique verify-mode inference | `07-testing-strategy.md` §3.2 |
| REQ-ROUTE-03 | `02-stage-exit-routing.md` §3, §10 — fail-closed missing/ambiguous context | `07-testing-strategy.md` §3.2, §9 |
| REQ-ROUTE-04 | `02-stage-exit-routing.md` §6 — verify/fix/re-verify rejoin table | `07-testing-strategy.md` §3.3, §7 |
| REQ-ROUTE-05 | `02-stage-exit-routing.md` §6.2 — complete fix outcome matrix | `07-testing-strategy.md` §3.3 |
| REQ-ROUTE-06 | `02-stage-exit-routing.md` §6.1 — complete verify outcome matrix | `07-testing-strategy.md` §3.3 |
| REQ-PROD-01 | `02-stage-exit-routing.md` §7; `04-skill-integration.md` §6 — all loop outcomes | `07-testing-strategy.md` §3.5, §6.2 |
| REQ-PROD-02 | `02-stage-exit-routing.md` §7 — non-complete recovery without advancement | `07-testing-strategy.md` §3.5 |
| REQ-PROD-03 | `02-stage-exit-routing.md` §8; `04-skill-integration.md` §7 — scripted docs exit | `07-testing-strategy.md` §3.6, §6.1 |
| REQ-PROD-04 | `02-stage-exit-routing.md` §8 — standalone/epic docs handoff | `07-testing-strategy.md` §3.6 |
| REQ-PROD-05 | `02-stage-exit-routing.md` §9 — live epic-member progress routing | `07-testing-strategy.md` §3.7 |
| REQ-PROD-06 | `02-stage-exit-routing.md` §9–§10 — safe named fallback | `07-testing-strategy.md` §3.7, §9 |
| REQ-DEBT-01 | `03-verification-state.md` §4.1, §5.1 — pending write before directive | `07-testing-strategy.md` §4.1 |
| REQ-DEBT-02 | `03-verification-state.md` §2.1, §5.2 — distinct auto-pending state | `07-testing-strategy.md` §4.1, §4.3 |
| REQ-DEBT-03 | `03-verification-state.md` §3.3, §4.2 — terminal replacement writer | `07-testing-strategy.md` §4.2 |
| REQ-DEBT-04 | `03-verification-state.md` §4.1, §7.2 — interruption preserves debt | `07-testing-strategy.md` §4.1, §4.3 |
| REQ-DEBT-05 | `03-verification-state.md` §5 — classifier/navigator/status parity | `07-testing-strategy.md` §4.1, §4.6 |
| REQ-DEBT-06 | `03-verification-state.md` §2.1, §6.2 — additive legacy loading | `07-testing-strategy.md` §4.4, §4.6 |
| REQ-STATE-01 | `03-verification-state.md` §3.4, §6.1 — full hashes on new writes | `07-testing-strategy.md` §4.5 |
| REQ-STATE-02 | `03-verification-state.md` §6.2 — permissive legacy short-hash reads | `07-testing-strategy.md` §4.4–§4.5 |
| REQ-STATE-03 | `03-verification-state.md` §3–§4, §7.1 — targeted atomic writer | `07-testing-strategy.md` §4.2–§4.3 |
| REQ-STATE-04 | `03-verification-state.md` §6.3 — two commits, never amend | `07-testing-strategy.md` §4.5 |
| REQ-CONFIG-01 | `05-config-and-distribution.md` §2.2, §4 — visible duplicate warning | `07-testing-strategy.md` §5.1–§5.2 |
| REQ-CONFIG-02 | `05-config-and-distribution.md` §3 — shared consumer path | `07-testing-strategy.md` §5.2–§5.3 |
| REQ-CONFIG-03 | `05-config-and-distribution.md` §2.1, §3, §6.1 — warning-only last-key-wins | `07-testing-strategy.md` §5.1–§5.3 |
| REQ-CONFIG-04 | `05-config-and-distribution.md` §2.1, §5.1 — arbitrary recursive keys | `07-testing-strategy.md` §5.1 |
| REQ-GUARD-01 | `06-compliance-and-coverage.md` §2 — explicit canonical set | `07-testing-strategy.md` §6.1 |
| REQ-GUARD-02 | `06-compliance-and-coverage.md` §2.1–§2.3 — included/excluded skills | `07-testing-strategy.md` §6.1 |
| REQ-GUARD-03 | `06-compliance-and-coverage.md` §2.4 — replace bespoke assertions | `07-testing-strategy.md` §6.1 |
| REQ-EVAL-01 | `06-compliance-and-coverage.md` §3–§5 — branch compliance fixture | `07-testing-strategy.md` §7.1–§7.2 |
| REQ-EVAL-02 | `06-compliance-and-coverage.md` §3.2, §4–§5 — success/recovery with command evidence | `07-testing-strategy.md` §7.1–§7.2 |
| REQ-EVAL-03 | `06-compliance-and-coverage.md` §6 — separate linear/branch reporting | `07-testing-strategy.md` §7.3 |
| REQ-CAP-01 | `04-skill-integration.md` §6.3 — preserve completed Step 2d split/caps | `07-testing-strategy.md` §6.2 |
| REQ-FOLLOW-01 | `04-skill-integration.md` §6.3 — correct runner wording, retain conditional load | `07-testing-strategy.md` §6.2 |
| REQ-FOLLOW-02 | `04-skill-integration.md` §4.2 — immediate targeted state-note recipe | `07-testing-strategy.md` §6.2 |
| REQ-REL-01 | `02-stage-exit-routing.md` §3–§10; `03-verification-state.md` §4.1 | `07-testing-strategy.md` §3–§5, §7 |
| REQ-REL-02 | `02-stage-exit-routing.md` §3, §10; `03-verification-state.md` §3.2, §7.1 | `07-testing-strategy.md` §3.2, §3.7, §4.3, §9 |
| REQ-REL-03 | `03-verification-state.md` §4.1, §7.2 — durable crash recovery | `07-testing-strategy.md` §4.1–§4.3 |
| REQ-COMPAT-01 | `02-stage-exit-routing.md` §3–§9; `04-skill-integration.md` §2–§9 | `07-testing-strategy.md` §3.8, §6.3 |
| REQ-COMPAT-02 | `03-verification-state.md` §2–§6; `05-config-and-distribution.md` §3.3 | `07-testing-strategy.md` §4.4, §5, §6.3 |
| REQ-COMPAT-03 | `01-architecture-layout.md` §6; `06-compliance-and-coverage.md` §6–§8 | `07-testing-strategy.md` §8.3 |
| REQ-PERF-01 | `02-stage-exit-routing.md` §8–§10; `05-config-and-distribution.md` §6.3 | `07-testing-strategy.md` §5.4, §8.2 |
| REQ-PERF-02 | `02-stage-exit-routing.md` §8–§10; `05-config-and-distribution.md` §2.3, §6.3 | `07-testing-strategy.md` §5.4, §8.2 |
| REQ-OBS-01 | `00-core-definitions.md` §4, §6; `06-compliance-and-coverage.md` §4–§5 | `07-testing-strategy.md` §3–§4, §7 |
| REQ-OBS-02 | `02-stage-exit-routing.md` §3, §6, §10; `05-config-and-distribution.md` §2.2, §4 | `07-testing-strategy.md` §3–§5, §9 |
| REQ-SEC-01 | `02-stage-exit-routing.md` §3, §9–§10; `03-verification-state.md` §3.2, §3.5, §7.1 | `07-testing-strategy.md` §3.7, §4.3, §5.3, §9 |
| REQ-A11Y-01 | `02-stage-exit-routing.md` §5.1; `04-skill-integration.md` §3.2, §5 | `07-testing-strategy.md` §6.2 |

## Technical-Decision Coverage

| Tech-spec decision | Implemented by |
|---|---|
| Explicit stage/outcome tables and typed branch context | `00-core-definitions.md` §2–§4; `02-stage-exit-routing.md` §2–§4 |
| Verify-first capability-aware terminal rendering | `02-stage-exit-routing.md` §5–§6 |
| Compatibility-split resolution policy | `02-stage-exit-routing.md` §3, §9–§10 |
| Live epic/docs and loop outcome routing | `02-stage-exit-routing.md` §7–§9; `04-skill-integration.md` §6–§8 |
| Unified verification writer and durable debt | `03-verification-state.md` §2–§7 |
| Epic manifest revision freshness | `03-verification-state.md` §4–§6 |
| Full new hashes and legacy reads | `03-verification-state.md` §6 |
| Recursive duplicate diagnostics and runtime fan-out | `05-config-and-distribution.md` §2–§7 |
| Canonical nine-skill exit and explicit guard | `04-skill-integration.md` §2–§10; `06-compliance-and-coverage.md` §2 |
| Branch compliance evaluation | `06-compliance-and-coverage.md` §3–§6 |
| Complete repository verification | `07-testing-strategy.md` §2–§9 |

## Validation Summary

- All 54 PRD requirement IDs have at least one primary implementation mapping.
- Every numbered document has a Requirement Coverage table and Dependencies and
  Verification sections.
- Cross-document references use existing filenames; no broken numbered-spec reference was
  found.
- Shared stage/outcome/status types are single-sourced in `00-core-definitions.md` and
  reused by all domain documents.
- Expected not-yet-implemented exports are called out explicitly with `WARNING:` at their
  integration sites rather than represented as existing code.
