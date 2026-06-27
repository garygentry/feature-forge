/**
 * The pure planner (spec 04 §3-§6) — the dry-run = real-run engine.
 *
 * `plan.ts` performs ZERO filesystem writes and ZERO network calls. It MAY read destination bytes
 * (via `sha256File`) and the prior manifest (already read by 05 and passed in via `PlanContext`).
 * It diffs three facts per bundle-relative path — source hash (S), destination hash (D), and the
 * manifest-recorded hash (M) — and emits a `PlannedAction`. The CLI hands the SAME object to
 * `apply()` on a real run, so dry-run and real run can never drift. Zero runtime dependencies.
 */

import * as fs from "node:fs";
import * as path from "node:path";
import type {
  AgentId,
  FileAction,
  FileActionKind,
  ManifestFile,
  Mode,
  Placement,
  PlacementFileAction,
  PlannedAction,
  PlannedPlacement,
  Result,
  Scope,
  InstallManifest,
} from "./types.js";
import { ok, err } from "./types.js";
import { sha256File, sha256String } from "./hash.js";
import { type LocatedSource } from "./source.js";
import {
  type ResolvedPlacement,
  selectMirrorFiles,
  renderCopilotBlock,
  wrapBlock,
  extractManagedRegion,
} from "./placements.js";
import { planUninstall } from "./manifest.js";
import { isWindows } from "./fsutil.js";

/**
 * Everything the pure planner needs to diff source ⇆ destination ⇆ manifest for ONE agent
 * (spec 04 §4). Built by cli.ts (07); the planner reads these and writes nothing.
 */
export interface PlanContext {
  /** The agent being planned. */
  readonly agent: AgentId;
  /** Active scope; copied onto the plan. */
  readonly scope: Scope;
  /** Resolved materialization mode. MUST already account for Windows (see `resolveMode`). */
  readonly mode: Mode;
  /** Absolute path of the `feature-forge/` namespace dir to be governed. */
  readonly destination: string;
  /** The located, integrity-checked source bundle (03), or `null` (absent/invalid bundle). */
  readonly source: LocatedSource | null;
  /** The prior manifest for this destination, or `null` if none exists (fresh install). */
  readonly priorManifest: InstallManifest | null;
  /** `--force`: overwrite `skip-modified` destinations instead of skipping. */
  readonly force: boolean;
  /** The pinned rauf coordinate to surface on the plan (06); the planner only echoes it. */
  readonly raufPin?: string | null;
  /**
   * Resolved secondary placements for this agent (A4b), or absent/empty when it has none. Supplied by
   * cli.ts (which holds the scope roots); the planner diffs each against its destination and the prior
   * manifest's matching placement inventory.
   */
  readonly placements?: ResolvedPlacement[];
}

/**
 * Classify one bundle-relative path (spec 04 §6 table). PURE: hashes are read, nothing is written.
 *
 * @param relpath      bundle-relative POSIX path (informational; not used in the decision)
 * @param srcHash      sha256 of the source file (S)
 * @param destHash     sha256 of the destination file, or undefined if absent (D)
 * @param manifestHash sha256 recorded for this path in the prior manifest, or undefined (M)
 * @param force        whether --force promotes skip-modified → overwrite
 */
export function classifyFile(
  relpath: string,
  srcHash: string,
  destHash: string | undefined,
  manifestHash: string | undefined,
  force: boolean,
): FileActionKind {
  void relpath;
  if (destHash === undefined) return "create"; // row 1
  if (destHash === srcHash) return "unchanged"; // row 3 (wins over rows 2/4)
  // dest exists and differs from source:
  const clean = manifestHash !== undefined && destHash === manifestHash;
  if (clean) return "overwrite"; // row 2 (REQ-IDEM-03: clean prior, source changed, no --force)
  return force ? "overwrite" : "skip-modified"; // rows 4/5 (REQ-IDEM-02/REQ-FLAG-04)
}

/**
 * PURE. Compute the install plan for one agent (spec 04 §4.1). Writes nothing. Returns
 * err(SOURCE_MISSING/SOURCE_INVALID) when `ctx.source` is null.
 */
export function planInstall(ctx: PlanContext): Result<PlannedAction> {
  return buildPlan(ctx, /* withOrphans */ false);
}

/**
 * PURE. Compute the update/reconcile plan for one agent (spec 04 §4.2): identical to planInstall
 * for create/overwrite/unchanged/skip-modified, PLUS manifest-scoped orphan removal — any path in
 * `priorManifest.files` the current source no longer contains becomes `remove`. With no prior
 * manifest, behaves exactly like planInstall (first install).
 */
export function planUpdate(ctx: PlanContext): Result<PlannedAction> {
  return buildPlan(ctx, /* withOrphans */ true);
}

/**
 * Convenience dispatcher used by cli.ts (07). Routes install/update to the typed planner;
 * `uninstall` delegates to `planUninstall` (manifest-driven, from 05) — an absent prior manifest
 * yields an empty-files plan (no-op).
 */
export function plan(
  subcommand: "install" | "update" | "uninstall",
  ctx: PlanContext,
): Result<PlannedAction> {
  switch (subcommand) {
    case "install":
      return planInstall(ctx);
    case "update":
      return planUpdate(ctx);
    case "uninstall":
      return ctx.priorManifest === null
        ? ok({
            agent: ctx.agent,
            scope: ctx.scope,
            mode: ctx.mode,
            destination: ctx.destination,
            files: [],
          })
        : planUninstall(ctx.priorManifest);
  }
}

/**
 * Resolve the effective materialization mode (spec 04, REQ-FLAG-03, D8). `--symlink` requests
 * symlink, but Windows ALWAYS copies. Pure; `windows` is injectable for tests.
 */
export function resolveMode(wantSymlink: boolean, windows = isWindows()): Mode {
  return wantSymlink && !windows ? "symlink" : "copy";
}

// ---------------------------------------------------------------------------
// Internal — plan assembly
// ---------------------------------------------------------------------------

/** Shared core of planInstall/planUpdate (the orphan pass differs). */
function buildPlan(ctx: PlanContext, withOrphans: boolean): Result<PlannedAction> {
  if (ctx.source === null) {
    // A null source means 03 already failed to locate/validate the bundle (SOURCE_MISSING or
    // SOURCE_INVALID). The CLI (07) surfaces 03's exact error; the planner only refuses to plan.
    return err({
      code: "SOURCE_MISSING",
      agent: ctx.agent,
      message: `no usable source bundle for agent "${ctx.agent}"`,
      remedy: "run the adapters build to generate adapters/<agent>/, or pass --source <dir>",
    });
  }

  const files =
    ctx.mode === "symlink"
      ? planSymlink(ctx)
      : planCopy(ctx, withOrphans);

  // Secondary placements (A4b) are always copy-style regardless of the primary mode: a mirror is a
  // few flat files and a managed-block is a merge, neither of which a whole-dir symlink expresses.
  const placements = planPlacements(ctx, withOrphans);

  const action: PlannedAction = {
    agent: ctx.agent,
    scope: ctx.scope,
    mode: ctx.mode,
    files,
    ...(ctx.raufPin !== undefined ? { raufPin: ctx.raufPin } : {}),
    ...(placements.length > 0 ? { placements } : {}),
  };
  return ok(action);
}

// ---------------------------------------------------------------------------
// Secondary placements (A4b)
// ---------------------------------------------------------------------------

/** Plan every resolved secondary placement (A4b). `ctx.source` is non-null here. */
function planPlacements(ctx: PlanContext, withOrphans: boolean): PlannedPlacement[] {
  const resolved = ctx.placements ?? [];
  if (resolved.length === 0) return [];
  const source = ctx.source as LocatedSource;
  const priorByDest = priorPlacementIndex(ctx.priorManifest);
  return resolved.map((rp) =>
    rp.kind === "mirror"
      ? planMirror(ctx, rp, source, priorByDest.get(rp.destination) ?? null, withOrphans)
      : planManagedBlock(ctx, rp, source, priorByDest.get(rp.destination) ?? null),
  );
}

/** Index prior-manifest placements by their absolute destination, for clean/orphan reconciliation. */
function priorPlacementIndex(prior: InstallManifest | null): Map<string, Placement> {
  const m = new Map<string, Placement>();
  for (const p of prior?.placements ?? []) m.set(p.destination, p);
  return m;
}

/** Diff a "mirror" placement: each selected bundle file vs its flat destination + recorded hash. */
function planMirror(
  ctx: PlanContext,
  rp: ResolvedPlacement,
  source: LocatedSource,
  prior: Placement | null,
  withOrphans: boolean,
): PlannedPlacement {
  const recorded = new Map<string, ManifestFile>();
  for (const f of prior?.files ?? []) recorded.set(f.path, f);

  const mirror = selectMirrorFiles(source, rp.spec);
  const files: PlacementFileAction[] = mirror.map((mf) => {
    const destAbs = path.join(rp.destination, mf.destRelpath);
    const destHash = hashIfExists(destAbs);
    const manifestHash = recorded.get(mf.destRelpath)?.sha256;
    const action = classifyFile(mf.destRelpath, mf.srcHash, destHash, manifestHash, ctx.force);
    return { relpath: mf.destRelpath, action, srcRelpath: mf.srcRelpath };
  });

  if (withOrphans && prior !== null) {
    const live = new Set(mirror.map((mf) => mf.destRelpath));
    for (const f of prior.files) {
      if (!live.has(f.path)) files.push({ relpath: f.path, action: "remove" });
    }
  }
  return { kind: "mirror", root: rp.root, destination: rp.destination, files };
}

/** Diff a "managed-block" placement: render the block, compare its region to the on-disk region. */
function planManagedBlock(
  ctx: PlanContext,
  rp: ResolvedPlacement,
  source: LocatedSource,
  prior: Placement | null,
): PlannedPlacement {
  const blockContent = renderCopilotBlock(source.skills);
  const newHash = sha256String(wrapBlock(blockContent));
  const basename = path.basename(rp.destination);

  const current = readManagedRegionHash(rp.destination);
  const recordedHash = prior?.files.find((f) => f.path === basename)?.sha256;

  let action: FileActionKind;
  if (current === undefined) {
    action = "create"; // no managed region present yet
  } else if (current === newHash) {
    action = "unchanged";
  } else {
    const clean = recordedHash !== undefined && current === recordedHash;
    action = clean ? "overwrite" : ctx.force ? "overwrite" : "skip-modified";
  }

  return {
    kind: "managed-block",
    root: rp.root,
    destination: rp.destination,
    files: [{ relpath: basename, action }],
    blockContent,
  };
}

/** Hash of the managed region currently in the target file, or undefined if absent/unreadable. */
function readManagedRegionHash(file: string): string | undefined {
  let content: string;
  try {
    content = fs.readFileSync(file, "utf8");
  } catch {
    return undefined;
  }
  const region = extractManagedRegion(content);
  return region === null ? undefined : sha256String(region);
}

/** Copy-mode per-file diff (spec 04 §6). `ctx.source` is non-null here. */
function planCopy(ctx: PlanContext, withOrphans: boolean): FileAction[] {
  const source = ctx.source as LocatedSource;
  const manifestByPath = new Map<string, ManifestFile>();
  for (const f of ctx.priorManifest?.files ?? []) manifestByPath.set(f.path, f);

  const actions: FileAction[] = [];
  for (const sf of source.files) {
    const destAbs = path.join(ctx.destination, sf.relpath);
    const destHash = hashIfExists(destAbs);
    const manifestHash = manifestByPath.get(sf.relpath)?.sha256;
    const kind = classifyFile(sf.relpath, sf.sha256, destHash, manifestHash, ctx.force);
    actions.push({ relpath: sf.relpath, action: kind });
  }

  if (withOrphans && ctx.priorManifest !== null) {
    actions.push(...orphanRemovals(ctx.priorManifest.files, source.files));
  }
  return actions;
}

/**
 * Symlink-mode plan shape (spec 04 §6): a single synthetic FileAction for the namespace dir.
 * The prior-state decision is read from the manifest (no `readlink`), keeping the planner pure.
 */
function planSymlink(ctx: PlanContext): FileAction[] {
  const source = ctx.source as LocatedSource;
  const prior = ctx.priorManifest;
  const priorExists = prior !== null;
  const priorIsLiveSymlinkToSameTarget =
    priorExists && prior.link?.target === source.root;

  const action: FileActionKind = priorIsLiveSymlinkToSameTarget
    ? "unchanged"
    : priorExists
      ? ctx.force
        ? "overwrite"
        : "skip-modified"
      : "create";

  return [{ relpath: ".", action }];
}

/** Paths in the prior manifest that the current source no longer contains → `remove` (row 6). */
function orphanRemovals(
  priorFiles: readonly ManifestFile[],
  sourceFiles: ReadonlyArray<{ readonly relpath: string; readonly sha256: string }>,
): FileAction[] {
  const inSource = new Set(sourceFiles.map((f) => f.relpath));
  return priorFiles
    .filter((f) => !inSource.has(f.path))
    .map((f) => ({ relpath: f.path, action: "remove" as const }));
}

/** sha256 of a destination file if it exists as a regular file, else undefined. PURE read. */
function hashIfExists(absPath: string): string | undefined {
  let st: fs.Stats;
  try {
    st = fs.lstatSync(absPath);
  } catch {
    return undefined;
  }
  if (!st.isFile()) return undefined;
  return sha256File(absPath);
}
