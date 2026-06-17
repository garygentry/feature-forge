/**
 * The apply engine (spec 04 §5) — the executor that turns a pure `PlannedAction` into filesystem
 * mutations, then records the install manifest. `apply` NEVER throws for expected errors: a failure
 * (write denied, path escape, manifest unwritable) returns `AgentReport{ ok:false, error }` so the
 * CLI loop (07) can record one agent's failure and proceed with the others (REQ-OBS-03).
 *
 * Every mutation routes through the sandboxed `fsutil` primitives (each preceded by a
 * `resolveWithin` containment check, REQ-SEC-01/02/03). There is NO gemini-specific branch — the
 * bundle's `gemini-extension.json` is just another file in `source.files` (D9). There is no
 * `applyUninstall`: an all-`"remove"` plan from `planUninstall` (05) is executed here (§5.3).
 *
 * Zero runtime dependencies; only `node:` built-ins.
 */

import * as fsp from "node:fs/promises";
import * as path from "node:path";
import type {
  AgentReport,
  InstallManifest,
  InstallerError,
  ManifestFile,
  Mode,
  PlannedAction,
  Result,
  Scope,
  AgentId,
} from "./types.js";
import { ok, err } from "./types.js";
import { sha256File } from "./hash.js";
import {
  resolveWithin,
  symlinkDir,
  removePath,
  removeEmptyDirsWithin,
} from "./fsutil.js";
import { buildManifest, writeManifest } from "./manifest.js";
import type { LocatedSource } from "./source.js";

/**
 * Apply-time context for ONE agent (spec 04 §5). `agentRoot` is the containment boundary every
 * write is checked against (REQ-SEC-02): the resolved `<scopeRoot>/<configDirName>` (from 02).
 * `destination` is the namespace dir; `manifestPath` the parent-sibling hidden file (05).
 */
export interface ApplyContext {
  readonly agent: AgentId;
  readonly scope: Scope;
  readonly mode: Mode;
  /** Containment boundary for REQ-SEC-02: the agent's config root (e.g. `<home>/.claude`). */
  readonly agentRoot: string;
  /** The `feature-forge/` namespace dir (manifest.destination). */
  readonly destination: string;
  /** Hidden parent-sibling manifest path, from 05 `manifestPath`. */
  readonly manifestPath: string;
  /** Located source bundle (copy bytes / symlink target). `null` only for uninstall. */
  readonly source: LocatedSource | null;
  /** Pinned rauf coordinate to record in the manifest (06); `null` under `--skip-rauf`. */
  readonly raufPin: string | null;
  /** ISO-8601 "now" (injectable for deterministic tests). */
  readonly now: string;
  /** Prior manifest (for preserving `installedAt` across updates, and carrying inventory). */
  readonly priorManifest: InstallManifest | null;
  /**
   * Injectable per-file write seam (tests force a deterministic WRITE_DENIED). Default:
   * mkdir parent + `fs.copyFile`. Returns `Result` and never throws for expected errors.
   */
  readonly writeFileSeam?: (srcAbs: string, destAbs: string) => Promise<Result<void>>;
}

/**
 * Execute one agent's `PlannedAction` against the filesystem, then write/delete the manifest.
 * Returns an `AgentReport` instead of throwing (REQ-OBS-03). See spec 04 §5.
 */
export async function apply(
  planned: PlannedAction,
  ctx: ApplyContext,
): Promise<AgentReport> {
  // Empty-files plan (e.g. uninstall with no prior manifest) is a no-op — touch nothing.
  if (planned.files.length === 0) return success(ctx, planned);

  const isUninstall = planned.files.every((f) => f.action === "remove");

  if (ctx.mode === "symlink") {
    return isUninstall
      ? applySymlinkUninstall(planned, ctx)
      : applySymlinkInstall(planned, ctx);
  }
  return isUninstall
    ? applyCopyUninstall(planned, ctx)
    : applyCopyInstall(planned, ctx);
}

// ---------------------------------------------------------------------------
// Copy mode
// ---------------------------------------------------------------------------

/** §5.1 copy flow: per-file copy/remove, then write the manifest (unless every action unchanged). */
async function applyCopyInstall(
  planned: PlannedAction,
  ctx: ApplyContext,
): Promise<AgentReport> {
  const source = ctx.source;
  if (source === null) {
    return fail(ctx, planned, {
      code: "UNEXPECTED",
      agent: ctx.agent,
      message: `apply(copy) for "${ctx.agent}" requires a located source bundle but got null`,
    });
  }

  const priorByPath = new Map<string, ManifestFile>();
  for (const f of ctx.priorManifest?.files ?? []) priorByPath.set(f.path, f);

  const writeFile = ctx.writeFileSeam ?? defaultCopyFile;
  const inventory: ManifestFile[] = [];

  for (const fa of planned.files) {
    const resolved = resolveWithin(ctx.agentRoot, ctx.destination, fa.relpath);
    if (!resolved.ok) return fail(ctx, planned, resolved.error);
    const destAbs = resolved.value;

    switch (fa.action) {
      case "create":
      case "overwrite": {
        const srcAbs = path.join(source.root, fa.relpath);
        const wrote = await writeFile(srcAbs, destAbs);
        if (!wrote.ok) return fail(ctx, planned, wrote.error);
        inventory.push({ path: fa.relpath, sha256: sha256File(destAbs) });
        break;
      }
      case "remove": {
        const removed = await removePath(destAbs);
        if (!removed.ok) return fail(ctx, planned, removed.error);
        break;
      }
      case "unchanged":
      case "skip-modified": {
        // No write. Carry the prior inventory entry forward so the rewritten manifest is faithful.
        const prior = priorByPath.get(fa.relpath);
        if (prior !== undefined) inventory.push(prior);
        break;
      }
    }
  }

  // No-op short-circuit (REQ-IDEM-01): every action unchanged ⇒ zero writes, manifest untouched.
  if (planned.files.every((f) => f.action === "unchanged")) {
    return success(ctx, planned);
  }

  const manifest = buildManifest({
    agent: ctx.agent,
    scope: ctx.scope,
    mode: "copy",
    destination: ctx.destination,
    files: inventory,
    skills: source.skills,
    sourceHash: source.sourceHash,
    raufPin: ctx.raufPin,
    previous: ctx.priorManifest,
    now: () => new Date(ctx.now),
  });
  const wrote = writeManifest(ctx.manifestPath, manifest);
  if (!wrote.ok) return fail(ctx, planned, wrote.error);
  return success(ctx, planned);
}

/** §5.3 copy-mode uninstall: remove recorded files, prune empty dirs, delete the manifest LAST. */
async function applyCopyUninstall(
  planned: PlannedAction,
  ctx: ApplyContext,
): Promise<AgentReport> {
  for (const fa of planned.files) {
    const resolved = resolveWithin(ctx.agentRoot, ctx.destination, fa.relpath);
    if (!resolved.ok) return fail(ctx, planned, resolved.error);
    const removed = await removePath(resolved.value);
    if (!removed.ok) return fail(ctx, planned, removed.error);
  }

  const pruned = await removeEmptyDirsWithin(ctx.destination, ctx.agentRoot);
  if (!pruned.ok) return fail(ctx, planned, pruned.error);

  const deleted = await deleteManifest(ctx);
  if (!deleted.ok) return fail(ctx, planned, deleted.error);
  return success(ctx, planned);
}

// ---------------------------------------------------------------------------
// Symlink mode
// ---------------------------------------------------------------------------

/** §5.2 symlink flow: remove any prior, link the whole namespace dir → source bundle root. */
async function applySymlinkInstall(
  planned: PlannedAction,
  ctx: ApplyContext,
): Promise<AgentReport> {
  const source = ctx.source;
  if (source === null) {
    return fail(ctx, planned, {
      code: "UNEXPECTED",
      agent: ctx.agent,
      message: `apply(symlink) for "${ctx.agent}" requires a located source bundle but got null`,
    });
  }

  const resolved = resolveWithin(ctx.agentRoot, ctx.destination);
  if (!resolved.ok) return fail(ctx, planned, resolved.error);
  const linkPath = resolved.value;

  // Unchanged (live link already points at the same target) ⇒ zero writes, manifest untouched.
  if (planned.files.every((f) => f.action === "unchanged")) {
    return success(ctx, planned);
  }
  // skip-modified (prior exists, no --force) ⇒ leave it; report, write nothing.
  if (planned.files.every((f) => f.action === "skip-modified")) {
    return success(ctx, planned);
  }

  const removed = await removePath(linkPath);
  if (!removed.ok) return fail(ctx, planned, removed.error);

  const linked = await symlinkDir(source.root, linkPath);
  if (!linked.ok) return fail(ctx, planned, linked.error);
  const effectiveMode: Mode = linked.value.mode;

  // files[] lists the bundle-relative paths with sha256 OMITTED (no per-file copy exists, 00 §3).
  const files: ManifestFile[] = source.files.map((f) => ({ path: f.relpath }));

  const manifest = buildManifest({
    agent: ctx.agent,
    scope: ctx.scope,
    mode: effectiveMode,
    destination: ctx.destination,
    files,
    skills: source.skills,
    sourceHash: source.sourceHash,
    raufPin: ctx.raufPin,
    // Truthful record: a copy fallback must NOT carry link (copy-mode manifest invariant, 05).
    ...(effectiveMode === "symlink" ? { link: { target: source.root } } : {}),
    previous: ctx.priorManifest,
    now: () => new Date(ctx.now),
  });
  const wrote = writeManifest(ctx.manifestPath, manifest);
  if (!wrote.ok) return fail(ctx, planned, wrote.error);
  return success(ctx, planned);
}

/** §5.3 symlink-mode uninstall: `lstat`+`unlink` the link only (never recurse), delete manifest. */
async function applySymlinkUninstall(
  planned: PlannedAction,
  ctx: ApplyContext,
): Promise<AgentReport> {
  const resolved = resolveWithin(ctx.agentRoot, ctx.destination);
  if (!resolved.ok) return fail(ctx, planned, resolved.error);

  const removed = await removePath(resolved.value);
  if (!removed.ok) return fail(ctx, planned, removed.error);

  const deleted = await deleteManifest(ctx);
  if (!deleted.ok) return fail(ctx, planned, deleted.error);
  return success(ctx, planned);
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/** Default per-file write seam: ensure the parent dir, then copy the source bytes. */
async function defaultCopyFile(
  srcAbs: string,
  destAbs: string,
): Promise<Result<void>> {
  try {
    await fsp.mkdir(path.dirname(destAbs), { recursive: true });
    await fsp.copyFile(srcAbs, destAbs);
    return ok(undefined);
  } catch (e) {
    const code = (e as NodeJS.ErrnoException)?.code;
    if (code === "EACCES" || code === "EPERM") {
      return err<InstallerError>({
        code: "WRITE_DENIED",
        message: `no write permission to ${destAbs}`,
        path: destAbs,
        remedy: "check directory permissions, or choose a different scope (--global vs project)",
      });
    }
    return err<InstallerError>({
      code: "UNEXPECTED",
      message: `filesystem error at ${destAbs}: ${(e as Error)?.message ?? String(e)}`,
      path: destAbs,
    });
  }
}

/** Delete the manifest file (containment-checked), idempotent (ENOENT → ok). */
async function deleteManifest(ctx: ApplyContext): Promise<Result<void>> {
  const resolved = resolveWithin(ctx.agentRoot, ctx.manifestPath);
  if (!resolved.ok) return resolved;
  return removePath(resolved.value);
}

/** Build a successful AgentReport for `ctx`/`planned`. */
function success(ctx: ApplyContext, planned: PlannedAction): AgentReport {
  return {
    agent: ctx.agent,
    detected: true,
    ok: true,
    actions: planned.files,
    raufPin: ctx.raufPin,
  };
}

/** Build a failed AgentReport carrying `error` (never throws — REQ-OBS-03). */
function fail(
  ctx: ApplyContext,
  planned: PlannedAction,
  error: InstallerError,
): AgentReport {
  return {
    agent: ctx.agent,
    detected: true,
    ok: false,
    actions: planned.files,
    error,
    raufPin: ctx.raufPin,
  };
}
