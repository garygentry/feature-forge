/**
 * Sandboxed filesystem primitives (spec 04 §7). Every filesystem mutation in `apply` routes through
 * these — they are the single place REQ-SEC-01/02/03 are enforced. Cross-platform: node:fs/promises,
 * node:path, node:os only (no shelling out). No throw for expected errors — all return `Result`.
 */
import * as fsp from "node:fs/promises";
import * as path from "node:path";
import * as os from "node:os";
import type { InstallerError, Result } from "./types.js";
import { ok, err } from "./types.js";

/**
 * Resolve `segs` against `root` and assert the result lies WITHIN `root` (REQ-SEC-02). Returns the
 * resolved absolute path on success, or a PATH_ESCAPE InstallerError if a `..` segment or a
 * malformed agent id would escape the agent config root. MUST be called before ANY write/delete.
 *
 * Uses `path.relative` + the `..` prefix test (the robust boundary check — a bare string startsWith
 * would false-pass `/root-evil`).
 *
 * @param root - the containment boundary (the agent config root, e.g. <home>/.claude)
 * @param segs - path segments to join under root (destination, then a bundle-relative path)
 * @returns ok(absolutePath) if inside; err(PATH_ESCAPE) otherwise.
 */
export function resolveWithin(root: string, ...segs: string[]): Result<string> {
  const base = path.resolve(root);
  const target = path.resolve(base, ...segs);
  const rel = path.relative(base, target);
  const inside = rel === "" || (!rel.startsWith("..") && !path.isAbsolute(rel));
  if (!inside) {
    return err({
      code: "PATH_ESCAPE",
      message: `refusing to write outside the agent config root: resolved "${target}" escapes "${base}"`,
      path: target,
      remedy: "this indicates a malformed agent id or path segment; report it as a bug",
    });
  }
  return ok(target);
}

/**
 * Recursively copy `src` → `dest` (copy mode). The CALLER is responsible for having
 * containment-checked `dest` via resolveWithin first (REQ-SEC-02).
 *
 * @returns ok(undefined) on success; err(WRITE_DENIED) on EACCES/EPERM, naming `dest`.
 */
export async function copyDir(src: string, dest: string): Promise<Result<void>> {
  try {
    await fsp.mkdir(path.dirname(dest), { recursive: true });
    await fsp.cp(src, dest, { recursive: true, force: true, dereference: false });
    return ok(undefined);
  } catch (e) {
    return err(toWriteError(e, dest));
  }
}

/**
 * Link the whole namespace dir `linkPath` → `target` (REQ-FLAG-03). On Windows, OR if the symlink
 * syscall fails for any reason, FALL BACK to copyDir and report it via the `mode` so apply records
 * the truthful mode.
 *
 * @returns ok({ mode }) where mode is "symlink" (link created) or "copy" (fallback fired);
 *          err(WRITE_DENIED) if even the copy fallback fails.
 */
export async function symlinkDir(
  target: string,
  linkPath: string,
): Promise<Result<{ mode: "symlink" | "copy" }>> {
  if (isWindows()) {
    const copied = await copyDir(target, linkPath);
    return copied.ok ? ok({ mode: "copy" }) : err(copied.error);
  }
  try {
    await fsp.mkdir(path.dirname(linkPath), { recursive: true });
    await fsp.symlink(target, linkPath, "dir");
    return ok({ mode: "symlink" });
  } catch {
    const copied = await copyDir(target, linkPath);
    return copied.ok ? ok({ mode: "copy" }) : err(copied.error);
  }
}

/**
 * Remove `p` safely (REQ-SEC-03/REQ-SAFE-02). NEVER follows a symlink to delete its target — uses
 * `lstat` (which does not dereference) to distinguish a symbolic link (unlink the link only), a real
 * directory (recursive rm), and a real file (unlink). ENOENT → ok (idempotent removal).
 *
 * The CALLER must have containment-checked `p` via resolveWithin first (REQ-SEC-02).
 *
 * @returns ok(undefined) on success or already-absent; err(WRITE_DENIED) on EACCES/EPERM.
 */
export async function removePath(p: string): Promise<Result<void>> {
  let st;
  try {
    st = await fsp.lstat(p); // lstat: does NOT dereference the link
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code === "ENOENT") return ok(undefined);
    return err(toWriteError(e, p));
  }
  try {
    if (st.isSymbolicLink()) {
      await fsp.unlink(p); // remove the LINK only — never the target (REQ-SAFE-02)
    } else if (st.isDirectory()) {
      await fsp.rm(p, { recursive: true, force: true });
    } else {
      await fsp.unlink(p);
    }
    return ok(undefined);
  } catch (e) {
    return err(toWriteError(e, p));
  }
}

/**
 * Prune now-empty directories from `startDir` UPWARD, stopping before `stopRoot` (exclusive). Used by
 * `apply`'s copy-mode uninstall (§5.3) after the recorded files are removed. NEVER removes a
 * non-empty dir nor `stopRoot` itself (REQ-SAFE-01). A non-existent `cur` is treated as
 * already-removed and the ascent continues.
 *
 * @param startDir - the deepest dir to consider pruning (e.g. the namespace dir).
 * @param stopRoot - the boundary; pruning never removes `stopRoot` itself nor anything outside it.
 * @returns ok(undefined) when the upward prune completes (or halts on a non-empty dir);
 *          err(PATH_ESCAPE) if `startDir` is not within `stopRoot`; err(WRITE_DENIED) on EACCES/EPERM.
 */
export async function removeEmptyDirsWithin(
  startDir: string,
  stopRoot: string,
): Promise<Result<void>> {
  const contained = resolveWithin(stopRoot, startDir);
  if (!contained.ok) return contained;
  const stop = path.resolve(stopRoot);
  let cur = contained.value;
  while (cur !== stop && cur.startsWith(stop)) {
    let entries: string[];
    try {
      entries = await fsp.readdir(cur);
    } catch (e) {
      if ((e as NodeJS.ErrnoException).code === "ENOENT") {
        cur = path.dirname(cur);
        continue;
      }
      return err(toWriteError(e, cur));
    }
    if (entries.length > 0) break; // non-empty ⇒ MUST NOT remove (REQ-SAFE-01) — halt
    try {
      await fsp.rmdir(cur); // remove this now-empty dir only
    } catch (e) {
      return err(toWriteError(e, cur));
    }
    cur = path.dirname(cur); // ascend
  }
  return ok(undefined);
}

/** Platform check (REQ-FLAG-03, C-6). Centralized so resolveMode/symlinkDir share one decision. */
export function isWindows(): boolean {
  return os.platform() === "win32";
}

/**
 * Map a caught fs exception to an actionable InstallerError (REQ-OBS-02). EACCES/EPERM → WRITE_DENIED;
 * anything else → UNEXPECTED carrying the message. Internal helper (not exported as public surface).
 */
function toWriteError(e: unknown, p: string): InstallerError {
  const code = (e as NodeJS.ErrnoException)?.code;
  if (code === "EACCES" || code === "EPERM") {
    return {
      code: "WRITE_DENIED",
      message: `no write permission to ${p}`,
      path: p,
      remedy: "check directory permissions, or choose a different scope (--global vs project)",
    };
  }
  return {
    code: "UNEXPECTED",
    message: `filesystem error at ${p}: ${(e as Error)?.message ?? String(e)}`,
    path: p,
  };
}
