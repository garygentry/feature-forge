# FORGE-104 installer placement primitives — 2026-08-26

## Scope and identity

- Task: `FORGE-104` only; feature-forge installer placement primitives.
- Repository: `/home/gary/workspace/feature-forge`.
- Branch: `docs/copilot-g2-contract`.
- Base commit: `6a9c8a1b8d6cf0ab51396035c042c93293047915` (`0 0` against upstream before and after implementation).
- Implementation commit: `c65b691dbd21cae9ef40309775b56fd739bd9b9f` (pushed to `origin/docs/copilot-g2-contract`).
- Pre-commit tracked patch identity: `git diff --binary | sha256sum` = `3df1d3ec96f3955f0ce6c96237707d785df2aceccf529d8b3c4f692851243d55` (the then-untracked receipt itself was necessarily excluded).
- No rauf repository files were read or changed during implementation.

## Environment

- OS: native Linux x86_64 (`/proc/version` contains no Microsoft/WSL marker), kernel `5.15.0-185-generic`.
- Node: `v24.14.0`.
- npm: `11.9.0`.
- No Copilot runtime claim is made by this task; fresh runtime discovery and complete scope roots remain FORGE-105.

## Expected result

1. A backward-compatible mirror placement can preserve complete source paths below a prefix for native skill trees while Codex/Pi/custom-agent mirrors remain flat.
2. Copilot project native mirrors target `.github/skills` and `.github/agents`; personal native mirrors target `~/.copilot/skills` and `~/.copilot/agents`.
3. Primary copy and symlink modes both copy native mirror leaves, record only proven-owned files with hashes, expose identical placement plans in dry-run and real-run reports, and uninstall only recorded leaves.
4. Recursive orphan removal prunes empty owned directories without removing untracked sibling skills/agents.
5. Malformed placement paths and manifest-forged roots fail before mutation.
6. A generic `.github` directory does not auto-detect Copilot; explicit `-a copilot` remains authoritative.
7. FORGE-105/106 boundaries remain intact: the complete personal runtime root is not moved, confidence is not raised, and the legacy managed block is retained until ownership-safe migration.

## Implementation result

- Added `PlacementSpec.mirrorLayout` with backward-compatible `flat` default and `recursive` prefix-relative projection.
- Added Copilot recursive skill and flat agent placements with scope-specific project/personal roots while retaining the legacy managed-block placement.
- Planner now rejects escaping placement destinations before destination reads, rejects empty/duplicate mirror projections, containment-checks orphan paths, and refuses existing symlink ancestors from each placement root through its destination leaf.
- Manifest validation rejects unsafe relative inventory paths and placement destinations outside their roots. Uninstall additionally compares every manifest placement boundary against the current trusted scope-resolved target configuration, so a manifest root cannot authorize itself.
- `AgentReport.placements` carries exact placement actions through dry-run, apply, JSON, and human reporting.
- Mirror inventory records only files created/overwritten by this installer or already proven by a prior placement record. Differing and byte-identical pre-existing files are not claimed and survive uninstall.
- Recursive update/uninstall pruning starts from each removed leaf's parent and stops at the trusted placement root, preserving non-empty user directories.
- Existing Codex/Pi flat mirrors and Copilot managed-block behavior remain covered and green.

## Focused checks

Command:

```bash
cd installer && npm test
```

Actual result before independent-review fixes: 195 tests passed. Review found three blocking gaps across two passes: identical-file ownership, Windows symlink-test portability, and lexical-only containment through symlink ancestors. All were fixed. Focused placement/apply/fsutil reruns passed 40 tests, including:

- project and personal recursive skill / flat agent mirrors;
- nested skill resources and complete manifest leaf inventory;
- recursive update orphan removal and empty-directory pruning;
- dry-run zero writes plus exact real-run placement action parity;
- native primary symlink lifecycle and Windows forced-copy fallback;
- differing and byte-identical pre-existing file non-ownership;
- manifest-forged root rejection before mutation;
- install/update/uninstall rejection of recursive mirror symlink ancestors before outside writes or removals;
- generic `.github` negative detection and explicit `-a copilot` targeting;
- Codex/Pi flat and legacy managed-block regressions.

Independent review's findings were fixed: unchanged files without prior ownership are verified but not inventoried; the native-link assertion is skipped on Windows with a separate forced-copy test; and a new `resolveWithinNoSymlinks` guard runs before planner reads and again immediately before placement mutations/removals. Final independent re-review found no issues and returned merge verdict `OK`; it noted only the unavoidable local filesystem race between the final `lstatSync` and mutation and deferred real Windows-junction behavior to the later OS matrix.

## Full repository gate

The first plain `bash scripts/validate.sh` inherited this interactive Pi package's external `FEATURE_FORGE_ROOT` and therefore made FORGE-103 root-resolution tests resolve the installed npm bundle instead of this checkout. This was an environment contamination, not an implementation failure. The clean-shell command required by the predecessor evidence was then used:

```bash
env -u FEATURE_FORGE_ROOT bash scripts/validate.sh
```

Actual result: PASS.

- 2,496 Python tests passed, 2 skipped.
- 201 installer tests passed.
- 11 Pi adapter-source tests passed.
- Plugin structure, strict Claude validation, frontmatter, permissions, spec purity, adapter drift, ruff, traceability, and four-field version synchronization passed.
- `git diff --check` passed.

## Ownership and cleanup assertions

- No adapter canon or generator input changed; `adapters/` remained byte-synchronized and was not regenerated.
- No external Copilot plugins, marketplaces, personal/project install fixtures, registry entries, or package copies were created; all installer fixtures were hermetic temporary directories removed by the test harness.
- No credentials, tokens, prompts containing secrets, or authenticated host state were used or recorded.
- The authorized implementation/evidence commit was pushed; no merge, tag, publish, release, or `RAUF_PIN` advance occurred.

## Deferred work

- FORGE-105: move/prove the complete personal runtime root, prove project/personal runtime discovery, update current documentation URL as required, and only then mark confidence `verified-current`.
- FORGE-106: ownership-safe legacy managed-block and old personal-layout migration, including apply/verify/remove/write-last behavior.

## Fresh-clone durability

A disposable single-branch clone was created from GitHub after the authorized push. It resolved exact
HEAD `c65b691dbd21cae9ef40309775b56fd739bd9b9f`, contained this evidence and the ACTIVE FORGE-104
ledger row, ran `npm ci` plus the complete installer `npm test` suite (201 passed), passed
`git diff --check`, and remained clean. The clone was removed by a shell trap.

FORGE-104 is therefore durable and may close; the next ledger cursor is FORGE-105.
