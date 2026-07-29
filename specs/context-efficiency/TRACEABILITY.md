# Traceability Matrix — context-efficiency

Maps every PRD requirement to the implementation-spec document(s) and section(s)
that cover it. Generated at forge-3-specs completion. Primary owner listed first;
supporting docs in parentheses.

> **Machine verification of the `REQ-R*-NN` rows** (finding V-018, resolved
> 2026-07-29). `scripts/validate-traceability.py` matched requirement IDs with
> `REQ-[A-Z]+-\d+`, which cannot match the digit in a category segment like `R1`. Every
> row in this file with a numbered category — all of R1–R6, 17 of this feature's 29
> requirements — was therefore invisible to `validate.sh` step 8, which nonetheless
> reported "All requirements covered" from the 12 it could see. The pattern is now
> `REQ-[A-Z][A-Z0-9]*-\d+` and step 8 reads all 29. Rows authored before that fix were
> confirmed by review, not by the gate.

## Functional Requirements

### R1 — Verification-checklist mode split

| REQ ID | Requirement | Doc → Section |
|--------|-------------|---------------|
| REQ-R1-01 | Verifier loads only its mode's checklist | `02` §2 (partition), §3 (load path) |
| REQ-R1-02 | Orchestrator material not in verifier contexts | `02` §3, §5, §7.4 · `00` §7 |
| REQ-R1-03 | Dual-role "which role are you?" guard intact | `02` §3, §6 |
| REQ-R1-04 | Per-mode "N of M" self-check stays correct | `02` §7.3 · `00` §7 · `06` §3.1 |
| REQ-R1-05 | Every CHECK-ID preserved exactly | `02` §2, §4, §9 · `00` §7 · `06` §3.1 |

### R2 — Within-file prelude dedup · **SCOPED OUT (2026-07-28)**

Not implemented in this feature — see PRD §3.2 for the rationale. Spec coverage is
retained below so the analysis survives if R2 is revived; expect no backlog items and no
implementation against these rows.

| REQ ID | Requirement | Doc → Section |
|--------|-------------|---------------|
| ~~REQ-R2-01~~ | 1st prelude verbatim, rest compact; behavior unchanged | `05` R2 §1.1/1.3/1.4 · `00` §8 |
| ~~REQ-R2-02~~ | Within-file only; no cross-file pointer | `05` R2 §1.2/1.5/1.6 · `00` §8 |

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
| REQ-R6-03 | No text pushed back into the capped loop body (298/300, 2 spare) | `05` R6 §3.4 · `01` §2.2 (cap ledger) · `04` §7 (cap discipline) |

### Cross-cutting delivery & portability

| REQ ID | Requirement | Doc → Section |
|--------|-------------|---------------|
| REQ-DELIV-01 | Each R independently shippable + revertible | `01` §4 (revert boundaries), §5 (sequencing) |
| REQ-PORT-01 | Every new/moved file cited by ≥1 skill body | `00` §9 · `01` §3.1/§3.1.1 · `02` §8 · `04` §7 · `05` R3/R6 · `06` §5 |
| REQ-PORT-02 | Moved files host-neutral (no Claude-only tokens) | `00` §9 · `02` §8 · `04` §7 · `05` R6 §3.6 |
| REQ-PORT-03 | All **six** adapter targets regenerate; fixtures refreshed | `00` §9 · `01` §6 · `02` §8 · `06` §6 |

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
| C-4 | Preferred mechanisms (R4 verbs, R5 effective-config) | `03` §2 · `04` §1/§3 |
| C-5 | Prelude dedup within-file only | `00` §8 · `05` R2 §1.2 — **moot: R2 scoped out**; every new call site uses the full prelude (`01` §2.2.1) |
| C-6 | Measure first (targets vs re-measured baseline) | `06` §7.1 · `.reference/REMEASURE-0.13.0.md` (**done**, 2026-07-28) |
| C-7 | No release items in the backlog | `01` §5 (noted; enforced at forge-4-backlog) |

## Success Criteria

| SC | Criterion | Where demonstrated |
|----|-----------|--------------------|
| SC-1 | Per-recommendation measured reduction | `06` §7.5 |
| SC-2 | Directional aggregate (~30–35%), not a gate | `06` §7.5 |
| SC-3 | Zero behavioral diff (full dogfood run) | `00` §10 · `06` §2 (regression baseline) |
| SC-4 | Tests green + drift coverage for every split/moved file | `06` §3–§6 |
| SC-5 | Clean portability across all six adapter targets | `06` §6 · `01` §3 |
| SC-6 | Each R landed as its own revertible unit | `01` §4/§5 |

## Open Questions (resolved at implementation time)

| OQ | Question | Owner |
|----|----------|-------|
| OQ-1 (PRD OQ-1) | Actual per-stage schema-read frequency (scales reported R4/R5 saving) | `06` §7.4 — **RESOLVED**: not per-stage in practice (2 / 1 reads across 188 sessions) |
| — (PRD OQ-2) | R4 mechanism: script-helper vs annotated-example fallback | `tech-spec` §3.4 — **RESOLVED**: targeted state verbs chosen |
| OQ-2 (PRD OQ-3) | Re-measured baseline token counts per invocation | `06` §7.1 — **RESOLVED**: `.reference/REMEASURE-0.13.0.md` is the baseline of record |
| OQ-3 (tech-spec OQ-3) | `state-complete --commit-hash` vs a separate hash-writer verb | `03` §6.5 — **RESOLVED**: same verb, `--commit-hash` |
| OQ-4 (tech-spec OQ-4) | Does citation fan-out scan agent bodies? | `02` §6/§8 · `00` §9 — **RESOLVED: no** (`build-adapters.py` L1402, L1672–1701) |

> Numbering follows `tech-spec` §10, which renumbers the PRD's questions. The provenance
> is annotated per row so a reader cross-referencing "PRD OQ-2" lands on the right one.

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
  - `import tempfile` **is** required: `03` §3.3 selects the `mkstemp`+fsync form as
    canonical, so it is the one new stdlib import this feature adds.
  - R4 `--stage` domain: `03` §3.7 defines `STATE_VERB_STAGES`. **`PRODUCTION_STAGES`
    already exists** at `forge-session.py` L99 (6 entries, order-sensitive) and must
    never be redefined — doing so breaks `next_stage()`.
  - Two REQ-BEHAV-02 wording changes flagged for the R1 PR (`02`): the
    forge-verifier "How You Work" file-load line, and the SKILL "tech ~15 → 17"
    correction. Both must be called out in review, not silently adapted.
  - **REQ-PERF-02's hook target is resolved:** `hooks/hooks.json` wires `SessionStart`
    to `bash ${CLAUDE_PLUGIN_ROOT}/scripts/session-check.sh`; there is no
    `hooks/session-start.py`. `06` §7.3 executes that script and asserts empty stdout on
    the common path, with a control case proving the silence is real — green/red, never
    a skip.
  - **R2 is scoped out (PRD §3.2).** Author no backlog items for REQ-R2-01/02, and no
    `tests/test_prelude_dedup.py`. Every new R4/R5 fenced call site uses the **full**
    `BOOTSTRAP_PRELUDE` — there is no compact form (`01` §2.2.1).
