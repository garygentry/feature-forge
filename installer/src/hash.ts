/**
 * Content hashing for the cross-agent installer (spec 03 §3.3-§3.6, OQ-4).
 *
 * Drift detection is decided by SHA-256 *content* hashing, NEVER mtime. The tree digest is a
 * function of the set of `{ relativePosixPath, fileContentHash }` pairs only, so two
 * materializations of the same bundle at different paths/times hash identically. Zero runtime
 * dependencies — only `node:` built-ins.
 */

import { createHash } from "node:crypto";
import * as fs from "node:fs";
import * as path from "node:path";

/**
 * SHA-256 of a single file's bytes, hex-encoded (OQ-4 — content hash, never mtime).
 *
 * @param filePath - Absolute path to a regular file.
 * @returns 64-char lowercase hex digest of the file's bytes.
 * @throws Propagates the underlying node:fs error (ENOENT/EACCES) — an *unexpected* IO failure
 *         for an already-located, integrity-checked bundle, caught at the operation boundary.
 */
export function sha256File(filePath: string): string {
  const buf = fs.readFileSync(filePath);
  return createHash("sha256").update(buf).digest("hex");
}

/**
 * Deterministic SHA-256 over a directory tree's file set (OQ-4). The digest is a function of the
 * set of `{ relativePosixPath, fileContentHash }` pairs ONLY — never of mtime, inode, or
 * traversal order.
 *
 * Canonical form: walk regular files, compute POSIX-relative paths, sort byte-wise, then fold a
 * single hash over `update(rel); update("\0"); update(contentHash); update("\n")` per file.
 *
 * @param dir - Absolute path to the directory whose tree to hash.
 * @returns 64-char lowercase hex digest, invariant under relocation and traversal order.
 */
export function sha256Tree(dir: string): string {
  const files = walkFiles(dir);
  const entries = files
    .map((abs) => ({
      rel: toPosix(path.relative(dir, abs)),
      contentHash: sha256File(abs),
    }))
    .sort((a, b) => (a.rel < b.rel ? -1 : a.rel > b.rel ? 1 : 0));

  const h = createHash("sha256");
  for (const e of entries) {
    h.update(e.rel);
    h.update("\0");
    h.update(e.contentHash);
    h.update("\n");
  }
  return h.digest("hex");
}

/**
 * Compute the `sourceHash` stored in InstallManifest (spec 00 §3, spec 03 §3.4). It is exactly
 * `sha256Tree(bundlePath)` — the sorted-path canonical digest over the bundle's file set, so two
 * materializations of the same bundle produce the SAME hash (REQ-IDEM-01 basis).
 *
 * @param bundlePath - Absolute path to a *located, integrity-checked* bundle dir.
 * @returns 64-char lowercase hex digest — store verbatim in `InstallManifest.sourceHash`.
 */
export function computeSourceHash(bundlePath: string): string {
  return sha256Tree(bundlePath);
}

/**
 * The bundle's per-file inventory: every regular file under `bundlePath`, each as its
 * bundle-relative POSIX path plus the content `sha256`. Sorted by relative POSIX path — the SAME
 * sorted walk `sha256Tree` folds over, so the inventory and `sourceHash` always agree.
 *
 * @param bundlePath - Absolute path to a located, integrity-checked bundle dir.
 * @returns Array of `{ relpath, sha256 }`, sorted by `relpath` (POSIX `/` separators).
 */
export function listBundleFiles(
  bundlePath: string,
): Array<{ relpath: string; sha256: string }> {
  const files = walkFiles(bundlePath);
  return files
    .map((abs) => ({
      relpath: toPosix(path.relative(bundlePath, abs)),
      sha256: sha256File(abs),
    }))
    .sort((a, b) => (a.relpath < b.relpath ? -1 : a.relpath > b.relpath ? 1 : 0));
}

// ---------------------------------------------------------------------------
// Internal helpers (module-private — spec 03 §4.2)
// ---------------------------------------------------------------------------

/**
 * Recursively collect every REGULAR FILE under `dir` (absolute paths). Directories contribute only
 * via their files; symlink entries are NOT followed and NOT included. Order is unspecified —
 * callers sort by relative path so traversal order never affects the digest.
 */
function walkFiles(dir: string): string[] {
  const out: string[] = [];
  const stack: string[] = [dir];
  while (stack.length > 0) {
    const cur = stack.pop() as string;
    for (const ent of fs.readdirSync(cur, { withFileTypes: true })) {
      const abs = path.join(cur, ent.name);
      if (ent.isDirectory()) stack.push(abs);
      else if (ent.isFile()) out.push(abs);
      // symlinks / sockets / fifos: ignored (not expected in a copied bundle)
    }
  }
  return out;
}

/** Normalize an OS-relative path to POSIX separators so hashes match across Windows and POSIX. */
function toPosix(rel: string): string {
  return rel.split(path.sep).join("/");
}
