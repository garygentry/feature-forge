# Traceability Matrix — context-efficiency

Maps every PRD requirement to the implementation-spec document(s) and section(s)
that cover it. Generated at forge-3-specs completion. Primary owner listed first;
supporting docs in parentheses.

## Functional Requirements

### R1 — Verification-checklist mode split

| REQ ID | Requirement | Doc → Section |
|--------|-------------|---------------|
| REQ-R1-01 | Verifier loads only its mode's checklist | `02` §2 (partition), §3 (load path) |
| REQ-R1-02 | Orchestrator material not in verifier contexts | `02` §3, §5, §7.4 · `00` §7 |
| REQ-R1-03 | Dual-role "which role are you?" guard intact | `02` §3, §6 |
| REQ-R1-04 | Per-mode "N of M" self-check stays correct | `02` §7.3 · `00` §7 · `06` §3.1 |
| REQ-R1-05 | Every CHECK-ID preserved exactly | `02` §2, §4, §9 · `00` §7 · `06` §3.1 |

### R2 — Within-file prelude dedup

| REQ ID | Requirement | Doc → Section |
|--------|-------------|---------------|
| REQ-R2-01 | 1st prelude verbatim, rest compact; behavior unchanged | `05` R2 §1.1/1.3/1.4 · `00` §8 |
| REQ-R2-02 | Within-file only; no cross-file pointer | `05` R2 §1.2/1.5/1.6 · `00` §8 |

### R3 — Conditional process-overview read

| REQ ID | Requirement | Doc → Section |
|--------|-------------|---------------|
| REQ-R3-01 | process-overview.md read only on how-it-works questions | `05` R3 §2.1/2.2 · `06` §3.3 |

### R4 — Targeted state verbs (eliminate per-stage schema read)

| REQ ID | Requirement | Doc → Section |
|--------|-------------|---------------|
| REQ-R4-01 | No per-stage full schema read to author state | `03` §2, §4–§10 · `00` §3/§5 |
| REQ-R4-02 | Script-extraction mechanism (verbs), annotated-example fallback | `03` §2, §3 |
| REQ-R4-03 | Schema stays CI source of truth | `03` §3.4, §12 · `00` §4 · `04` §9 · `06` §4 |
| REQ-R4-04 | All 7 state-write touch points covered | `03` §4–§10, §11.2 · `00` §5 · `01` §1 |

### R5 — Resolved loop-runner config subcommand

| REQ ID | Requirement | Doc → Section |
|--------|-------------|---------------|
| REQ-R5-01 | Resolved loopRunner config without reading full config schema | `04` §2/§3/§4/§7 · `00` §6 |
| REQ-R5-02 | Deterministic resolution kills "mis-merged defaults" errors | `04` §3/§4/§5/§8 |

### R6 — Runner-contract always/conditional split

| REQ ID | Requirement | Doc → Section |
|--------|-------------|---------------|
| REQ-R6-01 | Always-needed sections load every run | `05` R6 §3.1/3.2 · `06` §3.6 |
| REQ-R6-02 | Agent-selection loads only at the agentArgument gate | `05` R6 §3.2/3.3 |
| REQ-R6-03 | No text pushed back into the 300-line-capped loop body | `05` R6 §3.4 · `01` §2.2 · `04` §... (cap ledger) |

### Cross-cutting delivery & portability

| REQ ID | Requirement | Doc → Section |
|--------|-------------|---------------|
| REQ-DELIV-01 | Each R independently shippable + revertible | `01` §4 (revert boundaries), §5 (sequencing) |
| REQ-PORT-01 | Every new/moved file cited by ≥1 skill body | `00` §9 · `01` §3 · `02` §8 · `04` §... · `05` R3/R6 · `06` §5 |
| REQ-PORT-02 | Moved files host-neutral (no Claude-only tokens) | `00` §9 · `02` §8 · `04` · `05` R6 §3.6 |
| REQ-PORT-03 | All five adapters regenerate; fixtures refreshed | `00` §9 · `01` §6 · `02` · `06` §6 |

## Non-Functional Requirements

| REQ ID | Requirement | Doc → Section |
|--------|-------------|---------------|
| REQ-PERF-01 | Each R shows measured net reduction on its invocation | `06` §7 (§7.5 per-R table) |
| REQ-PERF-02 | No increase in always-loaded surface (frontmatter + hook) | `06` §7.3 (green/red guard) |
| REQ-BEHAV-01 | Zero behavioral diff on a full dogfood run | `00` §2/§10 · `03` §13 · `05` invariants |
| REQ-BEHAV-02 | Frozen interactive protocols preserved verbatim | `00` §2/§10 · `02` (flagged wording) · `03` §6.5/§13 · `04` · `05` |
| REQ-OBS-01 | Baselines re-measured; method recorded | `06` §7.1/§7.2 |
| REQ-OBS-02 | R4 read-frequency confirmed; reported saving scaled | `06` §7.4 |
| REQ-MAINT-01 | Drift-guard discipline extended to every split/moved file | `06` §3–§5 · `01` §6 · each domain doc's drift-guard subsection |

## Constraints

| ID | Constraint | Where honored |
|----|------------|---------------|
| C-1 | Behavior preservation is the prime directive | `00` §2 · all docs' invariant subsections |
| C-2 | CI gates: 300-line cap, ruff CI-only, no jsonschema | `00` §3.4 · `01` §2.2 · `03`/`04`/`06` (stdlib) |
| C-3 | Adapter build: citation fan-out, host-neutral, gemini scratch-build | `00` §9 · `06` §6 |
| C-4 | Preferred mechanisms (R4 verbs, R5 effective-config) | `03` §2 · `04` §... |
| C-5 | Prelude dedup within-file only | `00` §8 · `05` R2 §1.2 |
| C-6 | Measure first (targets vs re-measured baseline) | `06` §7.1 |
| C-7 | No release items in the backlog | `01` §5 (noted; enforced at forge-4-backlog) |

## Success Criteria

| SC | Criterion | Where demonstrated |
|----|-----------|--------------------|
| SC-1 | Per-recommendation measured reduction | `06` §7.5 |
| SC-2 | Directional aggregate (~30–35%), not a gate | `06` §7.5 |
| SC-3 | Zero behavioral diff (full dogfood run) | `00` §10 · `06` §2 (regression baseline) |
| SC-4 | Tests green + drift coverage for every split/moved file | `06` §3–§6 |
| SC-5 | Clean portability across five adapters | `06` §6 · `01` §3 |
| SC-6 | Each R landed as its own revertible unit | `01` §4/§5 |

## Open Questions (resolved at implementation time)

| OQ | Question | Owner |
|----|----------|-------|
| OQ-1 | Actual per-stage schema-read frequency (scales reported R4 saving) | `06` §7.4 |
| OQ-2 | Re-measured baseline token counts per invocation | `06` §7.1 |
| OQ-3 | `state-complete --commit-hash` vs a separate hash-writer verb | `03` §6.5 (leans `--commit-hash`) |
| OQ-4 | Does citation fan-out scan agent bodies? (mitigated regardless) | `02` §6/§8 · `00` §9 |

## Coverage Notes

- **All in-scope PRD requirements are covered.** Every REQ-ID defined in PRD §3
  and §4 maps to at least one spec document.
- **REQ-CTX-01 is intentionally uncovered.** It appears only in PRD §6 (Out of
  Scope) as the rationale for excluding W1 (trimming Epic Context Injection); it
  is a requirement of the *epic-orchestration* feature, not this one. No coverage
  is required.
- **Implementation-time flags carried from the writers (not gaps, but verify
  during the relevant unit's PR):**
  - `_now_iso()` does not yet exist in `forge-session.py` — R4 introduces it
    (`00` §3.3, `03` §3.1).
  - `import tempfile` is needed only for the `mkstemp` form of `_write_state`;
    the `with_suffix` form avoids the new import (`03` §3.3).
  - R4 `--stage` domain: `03` §3.7 uses a `PRODUCTION_STAGES` (7) constant;
    narrow to the 5 `EXIT_STAGES` if forge-4-backlog restricts verbs there.
  - The `06` §7.3 hook-silence guard references `hooks/session-start.py`; the
    repo wires hooks via `hooks.json` — confirm the real common-path hook target
    when implementing REQ-PERF-02's guard (test is `is_file()`-guarded, so it
    degrades to a no-op until wired).
  - Two REQ-BEHAV-02 wording changes flagged for the R1 PR (`02`): the
    forge-verifier "How You Work" file-load line, and the SKILL "tech ~15 → 17"
    correction. Both must be called out in review, not silently adapted.
