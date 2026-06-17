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
  PlannedAction,
  Result,
  Scope,
  InstallManifest,
} from "./types.js";
import { ok, err } from "./types.js";
import { sha256File } from "./hash.js";
import { type LocatedSource } from "./source.js";
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

  const action: PlannedAction = {
    agent: ctx.agent,
    scope: ctx.scope,
    mode: ctx.mode,
    files,
    ...(ctx.raufPin !== undefined ? { raufPin: ctx.raufPin } : {}),
  };
  return ok(action);
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
