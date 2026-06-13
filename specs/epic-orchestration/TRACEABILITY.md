# Traceability Matrix — epic-orchestration

Maps every PRD requirement (REQ-XXX-NN) to the implementation spec document(s) that cover it. Generated and validated via `scripts/validate-traceability.py` (all requirements covered, no orphans).

**Coverage: 32/32 requirements, 0 uncovered, 0 orphaned.**

| REQ ID | Requirement | Covering spec document(s) |
|--------|-------------|---------------------------|
| REQ-COMPAT-01 | All existing single-feature workflows, commands, artifacts, and sta... | 01-architecture-layout.md, 02-manifest-helper-cli.md, 04-pipeline-integration.md, 05-testing-strategy.md |
| REQ-COMPAT-02 | Existing projects with flat `{specsDir}/{feature}/` layouts and exi... | 00-core-definitions.md, 04-pipeline-integration.md, 05-testing-strategy.md |
| REQ-COMPAT-03 | The loop runner contract (rauf) must require no changes; per-featur... | 01-architecture-layout.md, 04-pipeline-integration.md |
| REQ-CTX-01 | When stages 1–3 (PRD, tech spec, implementation specs) run for a fe... | 04-pipeline-integration.md, 05-testing-strategy.md |
| REQ-CTX-02 | Context injection must surface the feature's contract obligations f... | 04-pipeline-integration.md |
| REQ-DIR-01 | An epic must be a self-contained subtree containing the manifest, t... | 01-architecture-layout.md, 03-forge-0-epic-stage.md |
| REQ-DIR-02 | Standalone (non-epic) features must continue to live flat at `{spec... | 01-architecture-layout.md |
| REQ-DIR-03 | Feature discovery must handle both layouts: tooling must distinguis... | 02-manifest-helper-cli.md, 04-pipeline-integration.md, 05-testing-strategy.md |
| REQ-DIR-04 | Feature names must be globally unique across the entire specs tree ... | 00-core-definitions.md, 01-architecture-layout.md, 02-manifest-helper-cli.md, 03-forge-0-epic-stage.md, 04-pipeline-integration.md, 05-testing-strategy.md |
| REQ-DOCS-01 | forge-6-docs must be epic-aware: when all member features are compl... | 04-pipeline-integration.md |
| REQ-EPIC-01 | A dedicated epic-creation pipeline stage must create an epic throug... | 01-architecture-layout.md, 03-forge-0-epic-stage.md, 05-testing-strategy.md |
| REQ-EPIC-02 | Epic creation must produce a machine-readable manifest recording: e... | 00-core-definitions.md, 01-architecture-layout.md, 03-forge-0-epic-stage.md, 05-testing-strategy.md |
| REQ-EPIC-03 | Epic creation must produce a human-readable narrative document capt... | 00-core-definitions.md, 03-forge-0-epic-stage.md, 04-pipeline-integration.md |
| REQ-EPIC-04 | At epic creation, each feature receives only a short charter (one-p... | 00-core-definitions.md, 03-forge-0-epic-stage.md, 04-pipeline-integration.md |
| REQ-EPIC-05 | The dependency graph declared in an epic must be validated as acycl... | 00-core-definitions.md, 01-architecture-layout.md, 02-manifest-helper-cli.md, 03-forge-0-epic-stage.md, 05-testing-strategy.md |
| REQ-EPIC-06 | Re-running forge-0-epic on an existing epic must enter an edit mode... | 02-manifest-helper-cli.md, 03-forge-0-epic-stage.md |
| REQ-OBS-01 | Epic-affecting actions (creation, edits, feature completion, handof... | 00-core-definitions.md, 02-manifest-helper-cli.md, 03-forge-0-epic-stage.md, 04-pipeline-integration.md |
| REQ-ORCH-01 | A feature is considered complete for orchestration purposes when it... | 00-core-definitions.md, 02-manifest-helper-cli.md, 04-pipeline-integration.md, 05-testing-strategy.md |
| REQ-ORCH-02 | When a member feature completes, forge must update the epic's view,... | 04-pipeline-integration.md |
| REQ-ORCH-03 | When multiple features are simultaneously unblocked, execution is s... | 00-core-definitions.md, 02-manifest-helper-cli.md, 04-pipeline-integration.md, 05-testing-strategy.md |
| REQ-ORCH-04 | Running the loop stage for a feature with incomplete dependencies m... | 04-pipeline-integration.md, 05-testing-strategy.md |
| REQ-ORCH-05 | Epic lifecycle states (active, paused, abandoned, complete) must be... | 00-core-definitions.md, 02-manifest-helper-cli.md, 04-pipeline-integration.md |
| REQ-ROBUST-01 | Epic state must survive across sessions: any session can reconstruc... | 02-manifest-helper-cli.md, 04-pipeline-integration.md, 05-testing-strategy.md |
| REQ-ROBUST-02 | A corrupted or hand-edited manifest must fail validation with actio... | 00-core-definitions.md, 01-architecture-layout.md, 02-manifest-helper-cli.md, 03-forge-0-epic-stage.md, 04-pipeline-integration.md, 05-testing-strategy.md |
| REQ-ROBUST-03 | All manifest writes must be atomic (write to a temporary file then ... | 01-architecture-layout.md, 02-manifest-helper-cli.md, 03-forge-0-epic-stage.md, 05-testing-strategy.md |
| REQ-SEC-01 | All epic artifacts (manifest, EPIC.md, charters) are trusted local ... | 00-core-definitions.md |
| REQ-SEC-02 | When resolving feature directories and manifest back-pointers, feat... | 00-core-definitions.md, 01-architecture-layout.md, 02-manifest-helper-cli.md, 03-forge-0-epic-stage.md, 05-testing-strategy.md |
| REQ-STATE-01 | The epic manifest is the canonical record of epic membership; each ... | 00-core-definitions.md, 02-manifest-helper-cli.md, 03-forge-0-epic-stage.md, 04-pipeline-integration.md |
| REQ-STATE-02 | Per-feature status shown at the epic level must be derived from eac... | 00-core-definitions.md, 02-manifest-helper-cli.md, 03-forge-0-epic-stage.md, 04-pipeline-integration.md, 05-testing-strategy.md |
| REQ-VERIFY-01 | forge-verify must support an epic mode checking: manifest/state con... | 03-forge-0-epic-stage.md, 04-pipeline-integration.md, 05-testing-strategy.md |
| REQ-VIS-01 | The forge navigator must provide an epic dashboard showing: epic st... | 00-core-definitions.md, 02-manifest-helper-cli.md, 04-pipeline-integration.md, 05-testing-strategy.md |
| REQ-VIS-02 | The navigator's no-argument discovery view must list epics alongsid... | 04-pipeline-integration.md |
