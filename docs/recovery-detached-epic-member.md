---
title: "Recovering a detached epic member"
---

# Recovering a detached epic member (split-brain epic)

This is the manual recovery recipe for the **split-brain epic** failure
([Issue #125](https://github.com/garygentry/feature-forge/issues/125)): a feature
that *should* be a member of an epic was instead forged as a **flat, standalone
feature** — usually because the pipeline was started on a branch cut from *before*
the epic-manifest commit, so the epic was invisible at mint time. The result is
two disjoint copies of the same feature:

- the epic's empty **member stub** at `specs/{epic}/{feature}/` on the epic branch
  (created by `forge-0-epic`, carrying an `epic` back-pointer), and
- a **detached standalone** at `specs/{feature}/` on the other branch, carrying no
  `epic` back-pointer and none of the epic's contracts.

The pipeline now guards against creating this state going forward — `forge-1-prd`
refuses to mint a known epic member as a standalone unless you pass
`--force-standalone`, and the authoring stages refuse to run a nested member on a
branch that lacks the epic manifest (`check-epic-base` → `warn-detached-base`).
This document covers **recovering an epic that already split**.

> There is no automated "adopt into epic" command yet — that is tracked as
> [Issue #126](https://github.com/garygentry/feature-forge/issues/126) (the deferred
> epic-backflow **Phase 3**, composite manifest+specs mutators). Until then, use the
> manual branch surgery below.

## Before you start

- Work on a clean tree (`git status --porcelain` prints nothing) and make a backup
  branch of the detached work: `git branch backup/{feature}-detached`.
- Identify the two branches. `discover-feature` shows you both:
  ```bash
  python3 "$R/scripts/forge-session.py" discover-feature "{feature}" --json
  ```
  The candidate with `isEpicMember: true` is the epic's member stub; its
  `stateBranch` is the epic's **home branch**. The `isEpicMember: false` candidate
  is the detached standalone.
- Decide which artifacts are canonical. Usually the **detached standalone** holds
  the real work (PRD, tech spec, specs, backlog) and the **member stub** is empty
  or only has an early stage — so you are moving the standalone's artifacts *into*
  the member slot, preserving the stub's `epic`/`branch` back-pointers.

## Recovery steps

1. **Switch to the epic's home branch** (the one that contains
   `specs/{epic}/epic-manifest.json`):
   ```bash
   git switch {homeBranch}
   ```

2. **Bring the detached standalone's artifacts onto this branch.** If the
   standalone lives on another branch, check out just its directory:
   ```bash
   git checkout {detachedBranch} -- specs/{feature}
   ```
   You now have `specs/{feature}/` (flat, detached) and
   `specs/{epic}/{feature}/` (the nested member stub) side by side.

3. **Relocate the artifacts into the member slot**, keeping the stub's
   `.pipeline-state.json` (it holds the correct `epic` and `branch` fields). Move
   the authored files (`PRD.md`, `tech-spec.md`, the `##-*.md` spec suite,
   `TRACEABILITY.md`, `backlog.json`) from `specs/{feature}/` into
   `specs/{epic}/{feature}/`, but **merge state deliberately** — do not overwrite
   the stub's `.pipeline-state.json` wholesale:
   - Copy the completed stages' entries (`stages.forge-1-prd`, `forge-2-tech`, …)
     and `artifacts` from the standalone state into the member stub's state.
   - **Keep** the stub's top-level `epic` back-pointer and its `branch` field.
   - Update `currentStage` to the furthest completed stage.

4. **Remove the flat standalone directory:**
   ```bash
   git rm -r specs/{feature}
   ```

5. **Reconcile the manifest.** Confirm `specs/{epic}/epic-manifest.json` lists
   `{feature}` as a member with the right `dependsOn`/`exposes`/`consumes`. If the
   feature was never added to the epic, add it via `forge-0-epic` edit mode rather
   than hand-editing the manifest:
   ```bash
   /feature-forge:forge-0-epic {epic}
   ```
   (edit mode: add the feature, set its dependencies and contracts).

6. **Regenerate the derived layer** (the `EPIC.md` narrative and any dashboards are
   derived from the manifest + member states). Re-running the epic dashboard
   confirms the member now attributes to the epic:
   ```bash
   /feature-forge:forge {epic}
   ```

7. **Verify and commit.** Run `/feature-forge:forge-verify {feature}` to confirm the
   member's contracts and traceability are intact, then commit the surgery on the
   epic's home branch following the Git Commit Protocol (stage `specs/{epic}/` and
   the removed `specs/{feature}/`).

## Verifying the fix

- `discover-feature "{feature}" --json` should now return a **single** candidate,
  nested under the epic (`path: specs/{epic}/{feature}/.pipeline-state.json`,
  `isEpicMember: true`), with no separate flat standalone.
- `check-epic-base --feature "{feature}"` should report `action: none` (the manifest
  is present on this branch).
- The epic dashboard (`/feature-forge:forge {epic}`) lists `{feature}` under the
  epic rollup, not as a standalone feature.

## Avoiding it next time

- Start member features from the epic's home branch, or fetch it first, so the
  epic manifest is present when `forge-1-prd` runs.
- Heed the mint guard: if `forge-1-prd` says `{feature}` is a known epic member,
  switch to the recorded branch instead of passing `--force-standalone`.
