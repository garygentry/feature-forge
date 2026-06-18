/**
 * The persisted install manifest (read/write/build) and the manifest-driven uninstall-exactness
 * policy (spec 05). This module locates the hidden parent-sibling manifest, reads/validates and
 * atomically writes it, builds an {@link InstallManifest} from an apply result, and owns the
 * uninstall removal POLICY (`planUninstall`). The safe EXECUTION of that plan is `apply()` in
 * spec 04 — there is no `applyUninstall` here.
 *
 * Zero runtime dependencies; only `node:` built-ins. Named exports only. Core functions return
 * `Result<T, E>` and never throw for expected errors; `JSON.parse` is wrapped in `try/catch`.
 */

import * as fs from "node:fs";
import * as path from "node:path";
import {
  AGENT_TARGETS,
  MANIFEST_PREFIX,
  SCHEMA_VERSION,
  ok,
  err,
  type AgentId,
  type InstallManifest,
  type ManifestFile,
  type Mode,
  type PlannedAction,
  type ResolveOpts,
  type Result,
  type Scope,
} from "./types.js";
import { destinationFor } from "./agent-targets.js";

// ---------------------------------------------------------------------------
// buildManifest
// ---------------------------------------------------------------------------

/**
 * Inputs to {@link buildManifest}. The caller (apply.ts, spec 04) assembles this from the resolved
 * detection target, the chosen scope/mode, and the apply result's per-file inventory.
 */
export interface BuildManifestArgs {
  readonly agent: AgentId;
  readonly scope: Scope;
  readonly mode: Mode;
  /** Absolute path of the `feature-forge/` namespace dir this manifest governs. */
  readonly destination: string;
  /**
   * Per-file inventory of what was written, paths relative to `destination`. In `"symlink"` mode
   * this is `[]` (no per-file copy exists). In `"copy"` mode each entry carries its `sha256`.
   */
  readonly files: readonly ManifestFile[];
  /** Installed skill ids (the bundle's `skills/*` dir names). */
  readonly skills: readonly string[];
  /** SHA-256 over the source bundle's canonical (sorted-path) file set — drift anchor (spec 03). */
  readonly sourceHash: string;
  /** Recorded pinned rauf coordinate (e.g. "@garygentry/rauf@0.7.0"); `null` when `--skip-rauf` (spec 06). */
  readonly raufPin: string | null;
  /** Symlink mode only: the source bundle the namespace dir links to (REQ-SAFE-02). */
  readonly link?: { readonly target: string };
  /** Prior manifest, if any. When present, its `installedAt` is preserved (this is an update). */
  readonly previous?: InstallManifest | null;
  /** Injectable clock for deterministic tests. Default: `() => new Date()`. */
  readonly now?: () => Date;
}

/**
 * Assemble an {@link InstallManifest} from an apply result (REQ-SAFE-01/03). Pure — no I/O.
 *
 * Timestamp policy: `updatedAt` is always "now"; `installedAt` is `previous.installedAt` when
 * reconciling an existing install, else "now". `featureForgeVersion` is always `null` today
 * (OQ-A/IR-1; C-3 forbids synthesizing one).
 */
export function buildManifest(args: BuildManifestArgs): InstallManifest {
  const now = (args.now ?? (() => new Date()))().toISOString();
  const installedAt = args.previous?.installedAt ?? now;

  const files: ManifestFile[] = [...args.files]
    .map((f) => ({ path: f.path, ...(f.sha256 !== undefined ? { sha256: f.sha256 } : {}) }))
    .sort((a, b) => (a.path < b.path ? -1 : a.path > b.path ? 1 : 0));

  const skills = [...args.skills].sort();

  return {
    schemaVersion: SCHEMA_VERSION,
    agent: args.agent,
    scope: args.scope,
    mode: args.mode,
    destination: args.destination,
    featureForgeVersion: null, // null today (OQ-A/IR-1); C-3 forbids synthesizing one.
    sourceHash: args.sourceHash,
    raufPin: args.raufPin,
    installedAt,
    updatedAt: now,
    skills,
    files,
    ...(args.link !== undefined ? { link: args.link } : {}),
  };
}

// ---------------------------------------------------------------------------
// manifestPath
// ---------------------------------------------------------------------------

/**
 * Absolute path of the hidden parent-sibling manifest for an agent + scope (D6/D8):
 *   `<scopeRoot>/<configDirName>/<installSubdir>/.feature-forge.<scope>.json`
 * e.g. `~/.claude/skills/.feature-forge.global.json`. Identical for copy and symlink mode.
 */
export function manifestPath(
  agent: AgentId,
  scope: Scope,
  opts?: Omit<ResolveOpts, "scope">,
): string {
  const destination = destinationFor(AGENT_TARGETS[agent], scope, opts);
  const installSubdirAbs = path.dirname(destination); // the skills/rules/extensions dir
  return path.join(installSubdirAbs, `${MANIFEST_PREFIX}${scope}.json`);
}

// ---------------------------------------------------------------------------
// readManifest / writeManifest
// ---------------------------------------------------------------------------

/**
 * Read and validate the manifest at `p`. Absent (`ENOENT`) → `ok(null)`; present + valid →
 * `ok(manifest)`; unreadable / invalid JSON / failed shape validation → `err(MANIFEST_CORRUPT)`.
 */
export function readManifest(p: string): Result<InstallManifest | null> {
  let raw: string;
  try {
    raw = fs.readFileSync(p, "utf8");
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code === "ENOENT") return ok(null);
    return err({
      code: "MANIFEST_CORRUPT",
      message: `cannot read install manifest at ${p}: ${(e as Error).message}`,
      path: p,
      remedy: "check read permissions, or remove the file to force a fresh install",
    });
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (e) {
    return err({
      code: "MANIFEST_CORRUPT",
      message: `install manifest at ${p} is not valid JSON: ${(e as Error).message}`,
      path: p,
      remedy: "the manifest is corrupt; remove it and re-run install to regenerate it",
    });
  }

  const v = validateManifest(parsed);
  if (!v.ok) {
    return err({
      code: "MANIFEST_CORRUPT",
      message: `install manifest at ${p} failed validation: ${v.reason}`,
      path: p,
      remedy: "the manifest is corrupt; remove it and re-run install to regenerate it",
    });
  }
  return ok(v.value);
}

/**
 * Atomically write the manifest to `p` (write `<p>.tmp` → `rename`). Creates the parent dir if
 * missing. Returns `err(WRITE_DENIED)` on a permission failure, cleaning up the temp file.
 */
export function writeManifest(p: string, m: InstallManifest): Result<void> {
  const tmp = `${p}.tmp`;
  try {
    fs.mkdirSync(path.dirname(p), { recursive: true });
    fs.writeFileSync(tmp, `${JSON.stringify(m, null, 2)}\n`, "utf8");
    fs.renameSync(tmp, p); // atomic on a single filesystem
    return ok(undefined);
  } catch (e) {
    // Best-effort cleanup of the temp file; ignore secondary failures.
    try {
      fs.rmSync(tmp, { force: true });
    } catch {
      /* ignore */
    }
    const code = (e as NodeJS.ErrnoException).code;
    if (code === "EACCES" || code === "EPERM") {
      return err({
        code: "WRITE_DENIED",
        message: `no write permission for install manifest at ${p}`,
        path: p,
        remedy: `ensure you can write to ${path.dirname(p)} (do not use elevated privileges)`,
      });
    }
    return err({
      code: "UNEXPECTED",
      message: `failed to write install manifest at ${p}: ${(e as Error).message}`,
      path: p,
    });
  }
}

// ---------------------------------------------------------------------------
// validateManifest (internal)
// ---------------------------------------------------------------------------

type ValidateResult =
  | { readonly ok: true; readonly value: InstallManifest }
  | { readonly ok: false; readonly reason: string };

const AGENT_IDS_SET = new Set(["claude", "codex", "copilot", "cursor", "gemini"]);

/** Structural validation of a parsed manifest (internal to manifest.ts). */
function validateManifest(x: unknown): ValidateResult {
  if (typeof x !== "object" || x === null) return { ok: false, reason: "not an object" };
  const o = x as Record<string, unknown>;

  if (o.schemaVersion !== SCHEMA_VERSION) {
    return { ok: false, reason: `unsupported schemaVersion ${String(o.schemaVersion)}` };
  }
  if (typeof o.agent !== "string" || !AGENT_IDS_SET.has(o.agent)) {
    return { ok: false, reason: `invalid agent ${String(o.agent)}` };
  }
  if (o.scope !== "global" && o.scope !== "project") {
    return { ok: false, reason: `invalid scope ${String(o.scope)}` };
  }
  if (o.mode !== "copy" && o.mode !== "symlink") {
    return { ok: false, reason: `invalid mode ${String(o.mode)}` };
  }
  if (typeof o.destination !== "string" || o.destination.length === 0) {
    return { ok: false, reason: "missing destination" };
  }
  if (!(o.featureForgeVersion === null || typeof o.featureForgeVersion === "string")) {
    return { ok: false, reason: "invalid featureForgeVersion" };
  }
  if (typeof o.sourceHash !== "string") return { ok: false, reason: "missing sourceHash" };
  if (!(o.raufPin === null || typeof o.raufPin === "string")) {
    return { ok: false, reason: "invalid raufPin" };
  }
  if (typeof o.installedAt !== "string" || typeof o.updatedAt !== "string") {
    return { ok: false, reason: "missing timestamps" };
  }
  if (!Array.isArray(o.skills) || !o.skills.every((s) => typeof s === "string")) {
    return { ok: false, reason: "invalid skills[]" };
  }
  if (!Array.isArray(o.files)) return { ok: false, reason: "invalid files[]" };
  for (const f of o.files) {
    if (typeof f !== "object" || f === null) return { ok: false, reason: "invalid files[] entry" };
    const ff = f as Record<string, unknown>;
    if (typeof ff.path !== "string") return { ok: false, reason: "files[].path not a string" };
    if (ff.sha256 !== undefined && typeof ff.sha256 !== "string") {
      return { ok: false, reason: "files[].sha256 not a string" };
    }
  }
  if (o.link !== undefined) {
    const l = o.link as Record<string, unknown>;
    if (typeof l !== "object" || l === null || typeof l.target !== "string") {
      return { ok: false, reason: "invalid link" };
    }
  }
  // Cross-field: symlink ⇒ link present; copy ⇒ link absent (D8 invariant).
  if (o.mode === "symlink" && o.link === undefined) {
    return { ok: false, reason: "symlink mode manifest missing link.target" };
  }
  if (o.mode === "copy" && o.link !== undefined) {
    return { ok: false, reason: "copy mode manifest must not carry link" };
  }
  return { ok: true, value: x as InstallManifest };
}

// ---------------------------------------------------------------------------
// planUninstall — the uninstall removal POLICY
// ---------------------------------------------------------------------------

/**
 * Compute the uninstall plan from a manifest (REQ-OPS-03, REQ-SAFE-01/02). PURE — no I/O,
 * manifest only. Returns an all-`"remove"` {@link PlannedAction}: copy mode one
 * `{ relpath, action: "remove" }` per `manifest.files[].path` in recorded order; symlink mode the
 * single `{ relpath: ".", action: "remove" }`. The safe EXECUTION is `apply()` in spec 04.
 */
export function planUninstall(manifest: InstallManifest): Result<PlannedAction> {
  const isSymlink = manifest.mode === "symlink" || manifest.link !== undefined;
  const files = isSymlink
    ? [{ relpath: ".", action: "remove" as const }]
    : manifest.files.map((f) => ({ relpath: f.path, action: "remove" as const }));
  return ok({
    agent: manifest.agent,
    scope: manifest.scope,
    mode: manifest.mode,
    destination: manifest.destination,
    files,
  });
}
