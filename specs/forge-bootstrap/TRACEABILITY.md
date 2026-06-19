# forge-bootstrap — Requirement Traceability Matrix

Maps every PRD requirement to the implementation spec document(s) that cover it. Generated
during forge-3-specs. The **primary** doc is the one that fully specifies the requirement;
**supporting** docs reference or test it.

> forge-bootstrap is an *unnumbered* forge skill (PRD §5), so its requirement IDs are the
> PRD's functional families rather than a per-feature `REQ-XXX-NN` spine.

Document key: `00` core-definitions · `01` architecture-layout · `02` helper-cli ·
`03` stack-templates · `04` skill-orchestration · `05` testing-strategy.

| REQ ID | Requirement (abbrev.) | Primary | Supporting |
|--------|-----------------------|---------|------------|
| REQ-GATE-01 | Greenfield gate: only repo-meta files | 00 §3 | 02 §3, 05 §3.1 |
| REQ-GATE-02 | Refusal names paths + points to forge-init | 02 §3 | 00 §4, 04 §7.1/§10, 05 §3.1 |
| REQ-GATE-03 | `git init` if no repo | 02 §4 | 00 §4, 05 §3.4/§3.6 |
| REQ-GATE-04 | Fresh-remote (README+LICENSE) eligible | 00 §3 | 02 §3, 05 §3.1 |
| REQ-GATE-05 | Never modify/delete pre-existing files | 02 §3/§4.1 | 00 §3 |
| REQ-INPUT-01 | Project name (dir default) | 04 §4 | 00 §5 |
| REQ-INPUT-02 | One-line purpose | 04 §4 | 00 §5 |
| REQ-INPUT-03 | Language/stack (5 profiles) | 04 §4 | 00 §2 |
| REQ-INPUT-04 | Package manager (only when meaningful) | 04 §4 | 00 §2, 02 |
| REQ-INPUT-05 | License (incl. "none") | 04 §4 | 00 §5 |
| REQ-INPUT-06 | Single package vs monorepo | 04 §4 | 00 §5 |
| REQ-INPUT-07 | Feature vs epic (Mode B only) | 04 §4/§8 | 00 §5 |
| REQ-INPUT-08 | Host-adapted input + conversational fallback | 04 §5/§6 | — |
| REQ-SCAF-01 | Stack-appropriate structure | 03 §2–6 | 02 §4.2, 05 §3.2 |
| REQ-SCAF-02 | Toolchain config (manifest/lint/fmt/test) | 03 §2–6 | 02 §4.2 |
| REQ-SCAF-03 | Runnable entrypoint | 03 §2–6 | 02 §4.2, 05 §3.2 |
| REQ-SCAF-04 | ≥1 passing test | 03 §2–6 | 02 §4.2 |
| REQ-SCAF-05 | Green baseline (lint + test pass) | 02 §5 | 00 §6, 03, 05 §3.3 |
| REQ-SCAF-06 | Repo-hygiene files (.gitignore/README/LICENSE/agent files) | 03 §2–6 | 02 §4.2/§4.3 |
| REQ-SCAF-07 | Optional CI workflow | 02 §4.4 | 00 §7, 04 |
| REQ-SCAF-08 | No untracked/dangling scaffold files | 02 §6 | 00 §4/§8, 05 §3.6 |
| REQ-SCAF-09 | No-overwrite of pre-existing allowed-meta files | 02 §4.1 | 04 |
| REQ-STACK-01 | TS/Python/Go/Rust/generic parity | 03 §1–6 | 00 §2, 01 §5, 05 §3.2 |
| REQ-STACK-02 | Verification commands match stack profile | 00 §6 | 02 §5, 03, 05 §3.2/§3.5 |
| REQ-STACK-03 | Generic fallback real + green | 00 §6.1 / 03 §6 | 02 §5, 05 §3.3 |
| REQ-MONO-01 | Interview members; scaffold root + members | 02 §4 | 00 §5, 03 §8, 04, 05 §3.4 |
| REQ-MONO-02 | Mixed-language members | 03 §8.1 | 00 §5, 02 §4.2 |
| REQ-MONO-03 | Each member runnable + tested; aggregate green | 02 §5 | 03 §8.2, 05 §3.4 |
| REQ-MONO-04 | CI runs lint+test for all members | 03 §9 | 00 §7, 02 §4.4, 04, 05 §3.4 |
| REQ-MONO-05 | Config represents workspace (additive `workspaces[]`) | 00 §7.1 | 01 §4, 02 §4.3, 05 §3.4 |
| REQ-MODEB-01 | Mode B opt-in; default Mode A | 04 §4/§8 | 00 |
| REQ-MODEB-02 | Post-green ask feature/epic + auto-launch | 04 §8 | — |
| REQ-MODEB-03 | Subsequent stages user-driven | 04 §8 | — |
| REQ-MODEB-04 | No launch if not verified green | 04 §8 | 00, 02 §5, 05 §3.3 |
| REQ-CFG-01 | Valid `forge.config.json` + `loopRunner` | 00 §7 | 02 §4.3, 05 §3.5 |
| REQ-CFG-02 | Config ≡ forge-init field set | 02 §4.3 | 00 §7, 01 §4, 05 §3.5 |
| REQ-CFG-03 | forge-init unnecessary after bootstrap | 00 §7 | 02 §4.3, 05 §3.5 |
| REQ-LIFE-01 | In-progress resume marker | 00 §8 | 02 §4/§7, 05 §3.7 |
| REQ-LIFE-02 | Resume/restart/cancel; no self-refusal | 02 §3/§4 | 00 §4/§8, 04 §7.2, 05 §3.1/§3.7 |
| REQ-LIFE-03 | Toolchain detection; warn/abort | 02 §5 | 00 §4, 01 §2.1, 04 §7.4 |
| REQ-LIFE-04 | Unverified baseline clearly marked | 02 §5 | 00 §4, 04 §7.4/§9 |
| REQ-LIFE-05 | Commit style at run time | 02 §6 | 00 §5, 04 §4/§7.6, 05 §3.6 |
| REQ-LIFE-06 | Single baseline commit when committing | 02 §6 | 04, 05 §3.6 |
| REQ-OUT-01 | Success summary + next command | 04 §9 | 00 §4, 02 |
| REQ-OUT-02 | Mode B launches instead of printing | 04 §8/§9 | — |
| REQ-PERF-01 | **No numeric target (deliberate non-requirement)** | — (PRD §4.1) | N/A — nothing to implement |
| REQ-SEC-01 | Never modify/delete user files | 00 §3 | 02 §3/§4.1, 04, 05 §3.1 |
| REQ-SEC-02 | Git protocol; no `-A`/`--force`/`--no-verify` | 02 §6 | 00, 04, 05 §3.6 |
| REQ-OBS-01 | All terminal outcomes explicit | 00 §4 | 02 §9, 04 §10 |
| REQ-PORT-01 | Works on any host (fallback) | 04 §6 | — |
| REQ-PORT-02 | Portable-root resolution | 00 §1.1 / 01 §2.2 | 04 §3 |

## Coverage Summary

- **51** PRD requirements total.
- **50** have implementation-spec coverage.
- **1** (REQ-PERF-01) is an explicit non-requirement (PRD §4.1 deliberately declines a
  numeric target); it has no implementation and is intentionally uncovered.

## Open Technical Questions carried into implementation

From tech-spec §10 — surfaced here so they are not lost at backlog time:

- **OQ-T1** — downstream consumption of `workspaces[]` (forge-2-tech/forge-4-backlog
  reading it to target a member's stack) is a **follow-up beyond this feature's scope**;
  forge-bootstrap satisfies REQ-MONO-05 at the *representation* level (00 §7.1, 02 §4.3).
- **OQ-T2** — TS minimal dev-deps: runner is **Vitest**; pin the smallest
  `typescript` + `vitest` set that stays green across npm/pnpm/yarn — finalize exact
  versions during implementation (03 §2).
- **OQ-T3** — sentinel `.gitignore` entry + removal ordering guaranteeing the sentinel
  never enters history even on a crash (00 §8, 02 §6, 03 `.gitignore` templates).
