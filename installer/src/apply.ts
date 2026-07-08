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
import * as fs from "node:fs";
import * as path from "node:path";
import type {
  AgentReport,
  InstallManifest,
  InstallerError,
  ManifestFile,
  Mode,
  Placement,
  PlannedAction,
  PlannedPlacement,
  Result,
  Scope,
  AgentId,
} from "./types.js";
import { ok, err } from "./types.js";
import { sha256File, sha256String } from "./hash.js";
import {
  resolveWithin,
  symlinkDir,
  removePath,
  removeEmptyDirsWithin,
} from "./fsutil.js";
import { buildManifest, writeManifest } from "./manifest.js";
import { wrapBlock, upsertBlock, removeBlock } from "./placements.js";
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

  // Secondary placements (A4b) execute regardless of the primary mode; collect their inventory.
  const placementResult = await applyPlacements(planned.placements ?? [], ctx, source);
  if (!placementResult.ok) return fail(ctx, planned, placementResult.error);

  // No-op short-circuit (REQ-IDEM-01): every action — primary AND placement — unchanged ⇒ zero
  // writes, manifest untouched — UNLESS manifest metadata (raufPin) drifted, which must persist
  // even with no file change (F1) so report / on-disk manifest / a later `list` agree.
  if (allUnchanged(planned) && !manifestNeedsRewrite(ctx)) {
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
    placements: placementResult.value,
    previous: ctx.priorManifest,
    now: () => new Date(ctx.now),
  });
  const wrote = writeManifest(ctx.manifestPath, manifest);
  if (!wrote.ok) return fail(ctx, planned, wrote.error);
  return success(ctx, planned);
}

/**
 * True when manifest metadata diverges from the prior manifest, so the manifest must be rewritten
 * even when every file action is "unchanged" (F1). Today the only such field is `raufPin`; a null
 * prior manifest also counts (there is nothing recorded yet). `updatedAt` is deliberately NOT a
 * trigger — it is a consequence of writing, so keying on it would defeat the idempotency short-circuit.
 */
function manifestNeedsRewrite(ctx: ApplyContext): boolean {
  const prior = ctx.priorManifest;
  if (prior === null) return true;
  return prior.raufPin !== ctx.raufPin;
}

/** True iff every planned action — primary files and all placement files — is "unchanged". */
function allUnchanged(planned: PlannedAction): boolean {
  return (
    planned.files.every((f) => f.action === "unchanged") &&
    (planned.placements ?? []).every((p) => p.files.every((f) => f.action === "unchanged"))
  );
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

  const placementsRemoved = await removePlacements(planned.placements ?? []);
  if (!placementsRemoved.ok) return fail(ctx, planned, placementsRemoved.error);

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

  // Secondary placements (A4b) apply even in symlink mode — they live under a different root than the
  // symlinked namespace dir. Run them first so a placement-only change still rewrites the manifest.
  const placementResult = await applyPlacements(planned.placements ?? [], ctx, source);
  if (!placementResult.ok) return fail(ctx, planned, placementResult.error);

  const primary = planned.files;
  const primaryUntouched =
    primary.every((f) => f.action === "unchanged") ||
    primary.every((f) => f.action === "skip-modified");

  // Nothing changed anywhere ⇒ zero writes, manifest untouched — unless raufPin drifted (F1).
  if (allUnchanged(planned) && !manifestNeedsRewrite(ctx)) {
    return success(ctx, planned);
  }

  // The recorded mode/link reflect the primary namespace dir: only (re)link when it actually changed
  // (a placement-only change leaves a live link and its prior manifest mode/link intact).
  let effectiveMode: Mode = ctx.priorManifest?.mode ?? "symlink";
  let linkTarget: string | undefined =
    ctx.priorManifest?.link?.target ?? (effectiveMode === "symlink" ? source.root : undefined);
  let files: ManifestFile[] = ctx.priorManifest?.files ?? source.files.map((f) => ({ path: f.relpath }));

  if (!primaryUntouched) {
    const removed = await removePath(linkPath);
    if (!removed.ok) return fail(ctx, planned, removed.error);

    const linked = await symlinkDir(source.root, linkPath);
    if (!linked.ok) return fail(ctx, planned, linked.error);
    effectiveMode = linked.value.mode;
    linkTarget = effectiveMode === "symlink" ? source.root : undefined;
    // files[] lists the bundle-relative paths with sha256 OMITTED (no per-file copy exists, 00 §3).
    files = source.files.map((f) => ({ path: f.relpath }));
  }

  const manifest = buildManifest({
    agent: ctx.agent,
    scope: ctx.scope,
    mode: effectiveMode,
    destination: ctx.destination,
    files,
    skills: source.skills,
    sourceHash: source.sourceHash,
    raufPin: ctx.raufPin,
    placements: placementResult.value,
    // Truthful record: a copy fallback must NOT carry link (copy-mode manifest invariant, 05).
    ...(linkTarget !== undefined ? { link: { target: linkTarget } } : {}),
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

  const placementsRemoved = await removePlacements(planned.placements ?? []);
  if (!placementsRemoved.ok) return fail(ctx, planned, placementsRemoved.error);

  const deleted = await deleteManifest(ctx);
  if (!deleted.ok) return fail(ctx, planned, deleted.error);
  return success(ctx, planned);
}

// ---------------------------------------------------------------------------
// Secondary placements (A4b)
// ---------------------------------------------------------------------------

/**
 * Execute every secondary placement for an install/update and return the inventory to record in the
 * manifest. Each placement is contained to ITS OWN root (`resolveWithin(placement.root, …)`), so a
 * mirror under `.codex` and a managed block under `.github` never escape their boundary (REQ-SEC-02).
 * Unchanged/skip-modified entries carry their prior recorded hash forward so the manifest stays
 * faithful. Never throws for expected errors.
 */
async function applyPlacements(
  placements: readonly PlannedPlacement[],
  ctx: ApplyContext,
  source: LocatedSource,
): Promise<Result<Placement[]>> {
  const priorByDest = new Map<string, Placement>();
  for (const p of ctx.priorManifest?.placements ?? []) priorByDest.set(p.destination, p);

  const out: Placement[] = [];
  for (const pl of placements) {
    const prior = priorByDest.get(pl.destination) ?? null;
    const res =
      pl.kind === "mirror"
        ? await applyMirror(pl, ctx, source, prior)
        : await applyManagedBlock(pl, prior);
    if (!res.ok) return res;
    out.push(res.value);
  }
  return ok(out);
}

/** §A4b mirror: copy/refresh/remove flat files under the second root; record per-file sha256. */
async function applyMirror(
  pl: PlannedPlacement,
  ctx: ApplyContext,
  source: LocatedSource,
  prior: Placement | null,
): Promise<Result<Placement>> {
  const priorByPath = new Map<string, ManifestFile>();
  for (const f of prior?.files ?? []) priorByPath.set(f.path, f);

  const writeFile = ctx.writeFileSeam ?? defaultCopyFile;
  const inventory: ManifestFile[] = [];

  for (const fa of pl.files) {
    const resolved = resolveWithin(pl.root, pl.destination, fa.relpath);
    if (!resolved.ok) return resolved;
    const destAbs = resolved.value;

    switch (fa.action) {
      case "create":
      case "overwrite": {
        if (fa.srcRelpath === undefined) {
          return err<InstallerError>({
            code: "UNEXPECTED",
            agent: ctx.agent,
            message: `mirror action for "${fa.relpath}" is missing its source path`,
          });
        }
        const wrote = await writeFile(path.join(source.root, fa.srcRelpath), destAbs);
        if (!wrote.ok) return wrote;
        inventory.push({ path: fa.relpath, sha256: sha256File(destAbs) });
        break;
      }
      case "remove": {
        const removed = await removePath(destAbs);
        if (!removed.ok) return removed;
        break;
      }
      case "unchanged":
      case "skip-modified": {
        // Carry the prior record forward; if none exists (e.g. a v1→v2 manifest migration where the
        // file is already on disk), reconstruct it by hashing the destination so the inventory stays
        // faithful rather than silently dropping an unrecorded-but-present file. Guard the hash: a
        // TOCTOU vanish (file removed after planning) must yield an err Result, never throw ENOENT
        // out of apply (REQ-OBS-03 — a throw would abort every sibling agent at the CLI boundary).
        const p = priorByPath.get(fa.relpath);
        if (p !== undefined) {
          inventory.push(p);
        } else {
          try {
            inventory.push({ path: fa.relpath, sha256: sha256File(destAbs) });
          } catch {
            return err<InstallerError>({
              code: "UNEXPECTED",
              agent: ctx.agent,
              message: `mirror file "${fa.relpath}" vanished before it could be recorded (${destAbs})`,
            });
          }
        }
        break;
      }
    }
  }
  return ok({ kind: "mirror", root: pl.root, destination: pl.destination, files: inventory });
}

/**
 * §A4b managed-block: merge/refresh the sentinel block into the (possibly user-owned) target file,
 * preserving everything outside the sentinels. Records a single inventory entry whose sha256 is the
 * written region's hash. skip-modified/unchanged carry the prior record forward (no write).
 */
async function applyManagedBlock(
  pl: PlannedPlacement,
  prior: Placement | null,
): Promise<Result<Placement>> {
  const fa = pl.files[0];
  const basename = fa?.relpath ?? path.basename(pl.destination);
  const resolved = resolveWithin(pl.root, pl.destination);
  if (!resolved.ok) return resolved;
  const fileAbs = resolved.value;

  const carry = (): Placement => {
    const p = prior?.files.find((f) => f.path === basename);
    return {
      kind: "managed-block",
      root: pl.root,
      destination: pl.destination,
      files: p !== undefined ? [p] : [],
    };
  };

  if (fa === undefined || fa.action === "unchanged" || fa.action === "skip-modified") {
    return ok(carry());
  }

  if (fa.action === "remove") {
    // Uninstall is handled by removePlacements; an install-plan never yields "remove" here.
    return ok(carry());
  }

  // create | overwrite — read existing (or treat as empty), upsert the block, write back.
  const body = pl.blockContent ?? "";
  let existing = "";
  try {
    existing = fs.readFileSync(fileAbs, "utf8");
  } catch {
    existing = "";
  }
  const next = upsertBlock(existing, body);
  const wrote = await writeText(fileAbs, next);
  if (!wrote.ok) return wrote;

  return ok({
    kind: "managed-block",
    root: pl.root,
    destination: pl.destination,
    files: [{ path: basename, sha256: sha256String(wrapBlock(body)) }],
  });
}

/**
 * Remove every secondary placement during uninstall (A4b): a "mirror" deletes each recorded file
 * (and prunes its now-empty dir); a "managed-block" strips ONLY the sentinel region, deleting the
 * file only if nothing else remains. User content outside the block is always preserved.
 */
async function removePlacements(
  placements: readonly PlannedPlacement[],
): Promise<Result<void>> {
  for (const pl of placements) {
    if (pl.kind === "managed-block") {
      const resolved = resolveWithin(pl.root, pl.destination);
      if (!resolved.ok) return resolved;
      const fileAbs = resolved.value;
      let existing: string;
      try {
        existing = fs.readFileSync(fileAbs, "utf8");
      } catch {
        continue; // already gone — nothing to strip
      }
      const stripped = removeBlock(existing);
      if (stripped === "") {
        const removed = await removePath(fileAbs);
        if (!removed.ok) return removed;
      } else {
        const wrote = await writeText(fileAbs, stripped);
        if (!wrote.ok) return wrote;
      }
      continue;
    }
    // mirror: remove each recorded file, then prune the now-empty destination dir.
    for (const fa of pl.files) {
      const resolved = resolveWithin(pl.root, pl.destination, fa.relpath);
      if (!resolved.ok) return resolved;
      const removed = await removePath(resolved.value);
      if (!removed.ok) return removed;
    }
    const pruned = await removeEmptyDirsWithin(pl.destination, pl.root);
    if (!pruned.ok) return pruned;
  }
  return ok(undefined);
}

/** Write text content to `destAbs`, creating the parent dir; maps EACCES/EPERM to WRITE_DENIED. */
async function writeText(destAbs: string, content: string): Promise<Result<void>> {
  try {
    await fsp.mkdir(path.dirname(destAbs), { recursive: true });
    await fsp.writeFile(destAbs, content, "utf8");
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
