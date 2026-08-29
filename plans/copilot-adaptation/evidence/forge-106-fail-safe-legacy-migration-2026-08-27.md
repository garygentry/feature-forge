# FORGE-106 fail-safe legacy migration — 2026-08-27

## Scope and identity

- Task: `FORGE-106` only; ownership-safe migration of legacy direct Copilot installs.
- Repository: `/home/gary/workspace/feature-forge`.
- Branch/base: `docs/copilot-g2-contract` at `04eff0538db8981411996fad27704aaa39a846f4`, initially `0 0` against upstream.
- Current state: implementation is uncommitted and remains ACTIVE pending owner authorization for commit/push.
- Tracked patch identity before this receipt: `git diff --binary | sha256sum` = `09459e4ce8b034a0f9623c0cbdfae541f92860de0446295cca219bccb83c7eec`.
- Rauf, `RAUF_PIN`, release coordinates, tags, and publication were not modified.

## Environment

- Native Linux x86_64, kernel `5.15.0-185-generic`.
- Node.js `v24.14.0`.
- No authenticated Copilot process was required: this task changes the install/update/uninstall filesystem transaction already runtime-proven for fresh layouts in FORGE-105.
- No credentials, tokens, account identifiers, or environment dumps are retained.

## Implemented migration contract

1. Fresh project/personal Copilot installs no longer create the obsolete managed instruction block.
2. Update discovers and strictly validates both current manifests and the historical personal manifest at `~/.github/.feature-forge.global.json`; primary identity and every placement must match trusted current/legacy boundaries before mutation.
3. Copy and symlink flows execute in phases: apply the new primary runtime, apply native skill/agent mirrors, hash-verify all required new leaves, remove only manifest-inventoried old files/retired placements, then atomically write the new manifest.
4. The historical personal runtime at `~/.github/feature-forge` migrates to `~/.copilot/feature-forge`; old copy inventories are removed leaf-by-leaf and old symlinks are unlinked without following their targets.
5. A recorded managed region is removed only when its apply-time hash still matches the recorded hash. Edited, unreadable, or malformed regions are preserved as `skip-modified`; `--force` removes only a well-formed sentinel-bounded region and preserves surrounding instructions. A missing region drops obsolete ownership.
6. A stable edited-region conflict is a repeated-update no-op. Clean migrated updates and uninstall are idempotent.
7. Cross-root recovery never adopts byte-identical files by inference: equal untracked files in the new primary root are planned and executed as overwrites before ownership is recorded.
8. Runtime symlink fallback to copy hashes every copied source leaf and records copy-mode hashes before legacy cleanup.
9. A failed new-file apply leaves legacy files and the old manifest untouched. A final-manifest failure leaves the verified new layout in place but retains the old manifest; retry rewrites/reverifies the new primary, reconciles cleanup idempotently, commits the new manifest, then removes the superseded manifest.
10. Untracked lookalike skills, agents, instruction content, and primary siblings are never selected by filename alone and survive migration/uninstall.

## Focused verification

Command:

```bash
cd installer && npm test
```

Result: PASS, 208 tests passed, 0 failed. Added/updated coverage proves:

- no managed block on fresh project installs;
- unchanged, edited, malformed, missing, and forced managed-region migration;
- old personal copy and symlink roots;
- apply-first/verify-before-cleanup ordering;
- deterministic new-file and final-manifest failures plus successful retry;
- runtime symlink-to-copy fallback verification and hash inventory;
- dry-run cleanup visibility and no writes;
- repeated update no-op;
- migrated and fresh exact uninstall;
- preservation of untracked skill/agent/instruction lookalikes;
- current and legacy containment/identity rejection paths.

`git diff --check` passed.

## Independent review

An independent read-only review initially found four blockers: absent/malformed retired ownership reconciliation, repeated `skip-modified` manifest rewrites, unverified runtime symlink fallback copies, and unsafe cross-root ownership adoption. Each was corrected and regression-tested. The same reviewer re-read the final diff and reported no remaining issue, with merge verdict `OK` subject to the parent gates.

## Full repository gate

Command:

```bash
env -u FEATURE_FORGE_ROOT bash scripts/validate.sh
```

Result: PASS.

- 2,496 Python tests passed, 2 skipped.
- 208 installer tests passed.
- 11 Pi adapter-source tests passed.
- Plugin validation, frontmatter, permissions, spec purity, generated adapter drift, ruff, traceability, and four-field version synchronization passed.

## Cleanup and remaining durability boundary

All installer fixtures were hermetic under temporary sandboxes and removed by test traps. No personal Copilot paths, plugin registries, runtime probes, copied package trees, or raw transcripts were created outside test sandboxes. The worktree contains only the intended source/tests/changelog/receipt changes.

FORGE-106 remains ACTIVE until the owner explicitly authorizes commit/push and a fresh clone verifies the exact pushed implementation. Do not begin FORGE-107 from this local-only receipt.
