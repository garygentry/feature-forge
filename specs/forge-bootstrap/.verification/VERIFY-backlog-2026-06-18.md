# Verification Findings — forge-bootstrap (backlog mode)

- **Feature:** forge-bootstrap
- **Mode:** backlog
- **Date:** 2026-06-18
- **Verifier:** forge-verify (4 parallel `forge-verifier` instances, dimensioned fan-out)
- **Artifacts verified:** specs/forge-bootstrap/backlog.json (14 items) against PRD.md, tech-spec.md, 00–05 specs, TRACEABILITY.md, and .rauf/backlog.schema.json

## Summary

- **Findings:** 5 (3 `gap`, 2 `improvement`)
- **Runner validation:** `rauf backlog validate . --backlog specs/forge-bootstrap --specs-dir specs/forge-bootstrap` → `{valid:true, findings:[]}` (exit 0).
- **Schema/enum dimension:** fully clean — all 14 items conform (type/status/priority enums, zero-padded unique ids, correct `dependsOn` key, valid `agentDelegation` shape, all `completedAt` null/`status` pending). 12/12 checks pass.
- **Checks executed across dimensions:** ~35 (scoping/AC 7, dependency/ordering 8, coverage/traceability 8, schema/enum 12).
- **Overall:** The backlog is high quality — self-contained descriptions, a runnable verification command on every item, a valid DAG, and foundation-first ordering. Two issues need attention before the loop runs: a missing dependency edge (V-001, mechanical) and a genuine REQ-SCAF-06 coverage gap (V-002/V-003) that traces back to the specs and **requires a user scope decision**. The agentDelegation on item 005 (concurrency 3 = 3 disjoint stack subtasks) was reviewed and is sound — no finding.

---

## Findings

### V-001 — Item 011 (integration tests) is under-constrained: missing `dependsOn` 003 (`check`)
- **Severity:** gap
- **Location:** `specs/forge-bootstrap/backlog.json` item `011`, `dependsOn: ["006","008","009"]`
- **What's wrong:** Item 011 exercises full check→scaffold→verify→commit flows, and two of its four required terminal-outcome assertions depend directly on the `check` subcommand: "greenfield refusal (check eligible:false names disqualifying[])" and "partial-state resume (own sentinel → check resumeMarker set)". `check` is implemented by item **003** (02 §3 is the sole `check` implementation; 006/008/009 implement scaffold/verify/commit only). After item 002 but before 003, `check` is a `NotImplementedError` stub, so item 011's refusal and resume assertions cannot pass. This is a true consume dependency, not a logical preference — item 012 correctly lists 003 alongside 006/008/009 for the same check-driven flow, which makes 011's omission an oversight.
- **Suggested fix:** Add `"003"` to item 011's `dependsOn`, making it `["003","006","008","009"]`.
- **References:** 02-helper-cli.md §3 (check = item 003); 05-testing-strategy.md §3 (refusal/resume tests); item 012's dependsOn as the correct precedent.
- **Checklist:** CHECK-B (dependency under-constrained / missing technical dependency), CHECK-B (foundation-first ordering)

### V-002 — REQ-SCAF-06 hygiene-file generation (README/LICENSE) has no grounded deliverable; item 006 instructs ungrounded work
- **Severity:** gap
- **Location:** `specs/forge-bootstrap/backlog.json` item `006` (description + acceptance criterion 3); root cause in specs 02 §4 and 03 §2–6
- **What's wrong:** REQ-SCAF-06 (PRD §3.3, P1) requires four hygiene artifacts: `.gitignore`, a **README stub seeded with name+purpose**, a **LICENSE per the user's selection**, and the **host agent-instruction file(s)**. Only `.gitignore` is an actual deliverable (it ships in every stack template, 03 §2.5/§3.5/§4.5/§5.5/§6.5). README, LICENSE, and agent files have **no specified generation mechanism**: no stack template (03 §2–6 file lists) contains a `README.md`/`LICENSE`, `compose_member` only copies files found in `templates/<stack>/` (02 §4.2), `write_config` only writes `forge.config.json` (02 §4.3), and the scaffold algorithm (02 §4, steps 1–6) has no repo-hygiene step. Yet 04 §9's example summary lists "Created: …README.md, LICENSE" and "Kept: (none — README/LICENSE generated fresh)", and TRACEABILITY.md claims REQ-SCAF-06 is covered by "02 §4 (compose_member, write_config)". So item 006's "generate repo-hygiene files (README/LICENSE/.gitignore/AGENTS.md|CLAUDE.md)" asks the implementer to invent an unspecified path — LICENSE-per-selection especially (where does MIT/Apache-2.0 license text come from?).
- **Suggested fix (requires user scope decision):** Either **(a) in scope** — add a hygiene-template set (e.g. `templates/_meta/` README/LICENSE/agent-file assets with `{{PROJECT_NAME}}`/`{{PURPOSE}}`/`{{LICENSE}}` tokens), add a scaffold step "5b. emit hygiene files" to 02 §4 (including the LICENSE-text source), give a backlog item the authoring job, and add explicit acceptance criteria to item 006; or **(b) defer** — de-scope README/LICENSE/agent-file *generation*, mark REQ-SCAF-06 "partial (.gitignore only)" in TRACEABILITY.md, strip the ungrounded language from item 006, and remove the "README.md, LICENSE … generated fresh" claims in 04 §9.
- **References:** PRD §3.3 (REQ-SCAF-06); 02-helper-cli.md §4/§4.2/§4.3; 03-stack-templates.md §2–6; 04-skill-orchestration.md §9; TRACEABILITY.md REQ-SCAF-06 row.
- **Checklist:** CHECK-B (PRD-family coverage), CHECK-B (no item invents ungrounded work), CHECK-B (orphaned/under-grounded deliverable)

### V-003 — Host agent-instruction file (AGENTS.md/CLAUDE.md) selection is unspecified and untested in item 006
- **Severity:** gap
- **Location:** `specs/forge-bootstrap/backlog.json` item `006`; no covering spec section exists
- **What's wrong:** REQ-SCAF-06 explicitly requires "the host agent-instruction file(s) (`AGENTS.md` / `CLAUDE.md` as applicable to the host)", but no spec section defines which file is written on which host, its content/template, or whether the skill body or the helper decides "as applicable to the host". Item 006's acceptance criteria 1–5 do not test agent-file emission at all (only the parenthetical in the description mentions it), so an implementer could ship nothing and the item still passes — a silent hole for a named P1 sub-requirement. Closely related to V-002; resolve together.
- **Suggested fix (tied to V-002's decision):** If in scope, specify the agent-file behavior — host-selection rule belongs with the host-adaptation pattern (04 §5/§6) — and add an explicit acceptance criterion to item 006 (or the new hygiene item) asserting the correct agent file is emitted. If deferred, record the deferral in TRACEABILITY.md alongside the V-002 decision.
- **References:** PRD §3.3 (REQ-SCAF-06); 04-skill-orchestration.md §5/§6 (host-adaptation); TRACEABILITY.md REQ-SCAF-06; 02-helper-cli.md §4.
- **Checklist:** CHECK-B (PRD-family coverage completeness), CHECK-B (acceptance criteria cover the cited requirement)

### V-004 — Item 011 acceptance criteria use a non-objective "skip-guarded" outcome
- **Severity:** improvement
- **Location:** `specs/forge-bootstrap/backlog.json` item `011`, acceptanceCriteria[0]
- **What's wrong:** AC[0] ("toolchain-present cases assert green:true/exit 0; absence is skip-guarded") is partly self-judging — a loop agent can't objectively confirm "absence is skip-guarded" without knowing which toolchains the host has; pass/fail depends on host state. The deterministic missing-toolchain case (PATH='') is correctly host-independent; only the green-baseline cases are conditional.
- **Suggested fix:** Reword AC[0] to make the mechanism verifiable rather than the outcome, e.g. "Each green-baseline test asserts green:true/exit 0 when the stack toolchain is detected and is explicitly `pytest.skip`-guarded (with a skip reason) when absent — verified by reading that every green-baseline test has a `shutil.which`/skip guard, not by host outcome."
- **References:** 05-testing-strategy.md §3/§4 (portability/skip scheme); item 008 AC[2] (the contrasting deterministic case).
- **Checklist:** CHECK-B (acceptance criteria objectively verifiable)

### V-005 — `schemaVersion` omitted at top level (optional)
- **Severity:** improvement
- **Location:** `specs/forge-bootstrap/backlog.json` top-level object
- **What's wrong:** `schemaVersion` is absent. The schema declares it optional with `default: "1"`, so omission is valid and rauf stamps it on read — not a violation. Noted only for explicitness.
- **Suggested fix:** Optionally add `"schemaVersion": "1"` at the top level. No action required.
- **References:** .rauf/backlog.schema.json lines 4–7.
- **Checklist:** CHECK-B (schema conformance)

---

## Fix Execution Plan

### User Decisions Required
- **V-002 / V-003 (REQ-SCAF-06 hygiene generation):** Decide whether README / LICENSE / AGENTS.md / CLAUDE.md **generation** is **in scope for this feature** or **deferred**. The key sub-decision is the LICENSE-text source (bundled license texts vs. SPDX fetch vs. stub-only). This cannot be auto-applied and touches both the specs and the backlog. Resolve this before running the loop, since it changes item 006's scope.

### Execution Steps

#### Step 1 — Add the missing dependency edge (V-001)
- **File:** `specs/forge-bootstrap/backlog.json`
- **Addresses:** V-001
- **Action:** Set item 011's `dependsOn` to `["003","006","008","009"]`.
- **Depends on:** none. Re-run `rauf backlog validate . --backlog specs/forge-bootstrap --specs-dir specs/forge-bootstrap --json` and confirm exit 0.

#### Step 2 — Ground or defer REQ-SCAF-06 hygiene generation (V-002, V-003)
- **Files:** `specs/forge-bootstrap/02-helper-cli.md` (or `04-skill-orchestration.md`), `specs/forge-bootstrap/03-stack-templates.md`, `specs/forge-bootstrap/04-skill-orchestration.md` (§9 example), `specs/forge-bootstrap/TRACEABILITY.md`, `specs/forge-bootstrap/backlog.json` (item 006, possibly a new item)
- **Addresses:** V-002, V-003
- **Action (per the user's scope decision):**
  - **In scope:** add hygiene-template assets + a scaffold "5b. emit hygiene files" step (with the LICENSE-text source and the AGENTS.md/CLAUDE.md host-selection rule), give a backlog item the authoring job, and add explicit acceptance criteria to item 006 covering README seeding, LICENSE-per-selection, and agent-file emission.
  - **Deferred:** mark REQ-SCAF-06 "partial (.gitignore only)" in TRACEABILITY.md, strip the ungrounded "generate repo-hygiene files (README/LICENSE/AGENTS.md|CLAUDE.md)" language from item 006, and remove the "README.md, LICENSE … generated fresh" claims in 04 §9.
- **Depends on:** the user scope decision above.

#### Step 3 — Tighten acceptance-criteria wording (V-004) and optionally stamp schemaVersion (V-005)
- **File:** `specs/forge-bootstrap/backlog.json`
- **Addresses:** V-004, V-005
- **Action:** Reword item 011 AC[0] to assert the skip-guard mechanism (readable from code) rather than a host-dependent outcome. Optionally add `"schemaVersion": "1"` at the top level.
- **Depends on:** none.

---

## Fix Progress

User scope decision: **REQ-SCAF-06 hygiene generation = IN SCOPE.** LICENSE source = bundled MIT + Apache-2.0 tokenized templates (offline). Agent files = AGENTS.md always + CLAUDE.md when host==claude.

- Step 1: [APPLIED] 2026-06-18 — V-001: item 011 dependsOn now ["003","006","008","009"]; re-validated (exit 0).
- Step 2: [APPLIED] 2026-06-18 — V-002/V-003: grounded REQ-SCAF-06 in specs — 00 §5 (Answers.author/host) + §6.2 ({{AUTHOR}}/{{YEAR}}/{{LICENSE}} tokens); 02 §4 (scaffold step 4 + write_hygiene §4.5); 03 §10 (hygiene/ + licenses/ template assets); 01 §1.1 tree + §5 surface; 04 §4.1 payload + §9 summary; TRACEABILITY REQ-SCAF-06/09/INPUT-05 rows. Backlog: new item 015 (author hygiene+license templates), item 006 wired to write_hygiene (+dep 015, +AC, +specRef 03), item 014 +dep 015. Traceability re-validated (51 reqs, 0 uncovered, 0 orphaned).
- Step 3: [APPLIED] 2026-06-18 — V-004: item 011 AC[0] reworded to assert the skip-guard mechanism (readable from code), not host outcome. V-005: schemaVersion "1" added at top level.

Backlog re-validated after all edits: `rauf backlog validate` exit 0, 15 items.
