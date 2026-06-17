/**
 * The `agent-detection-map` exposed surface (spec 02): the static per-agent table plus the
 * pure path derivations and the stat-based detection over it.
 *
 * One contract, two halves (REQ-DET-05):
 *   - static  — `AGENT_TARGETS` (re-exported), `resolveRoots`, `destinationFor`
 *   - behavioral — `detectAgent`, `detectAgents`, `formatZeroDetection`
 *
 * Every function is data-driven over `AGENT_TARGETS` / `AGENT_IDS`, so a new agent is exactly
 * one table row (REQ-SCALE-01) with no edit here. Read-only and total: nothing writes, spawns
 * an agent, or creates a directory. Zero runtime dependencies; only `node:` built-ins.
 */

import * as os from "node:os";
import * as path from "node:path";
import {
  AGENT_IDS,
  AGENT_TARGETS,
  FEATURE_FORGE_NS,
  type AgentId,
  type AgentTarget,
  type DetectionResult,
  type ResolveOpts,
  type Scope,
} from "./types.js";
import { probeConfigDir, cliOnPath } from "./detect.js";

// Re-export the static table so importers reach the data and the behavior from one surface
// (REQ-DET-01, REQ-DET-05).
export { AGENT_TARGETS } from "./types.js";

/**
 * Resolve the two filesystem roots all destinations derive from, applying defaults. This is
 * the single injection point for the home and working directories, so tests sandbox every
 * path computation without touching the real `~` (spec 02 §4.2).
 *
 * - `home` (global scope root) defaults to `os.homedir()`.
 * - `cwd`  (project scope root) defaults to `process.cwd()`.
 *
 * Both returned paths are absolute and `path.resolve`d. Pure: reads no files, spawns nothing.
 */
export function resolveRoots(opts?: ResolveOpts): { home: string; cwd: string } {
  return {
    home: path.resolve(opts?.home ?? os.homedir()),
    cwd: path.resolve(opts?.cwd ?? process.cwd()),
  };
}

/**
 * Internal: select the root directory for a scope (REQ-FLAG-02).
 * `"global"` → the resolved home dir; `"project"` → the resolved cwd.
 */
function scopeRootFor(scope: Scope, roots: { home: string; cwd: string }): string {
  return scope === "global" ? roots.home : roots.cwd;
}

/**
 * Derive the absolute install destination for one agent under a given scope (REQ-DET-01,
 * REQ-FLAG-02):
 *
 *     <scopeRoot>/<configDirName>/<installSubdir>/<FEATURE_FORGE_NS>/
 *
 * where `scopeRoot` is the home dir for `"global"` and the cwd for `"project"`. The path is
 * derived, never stored, so a new agent is one `AGENT_TARGETS` row (REQ-SCALE-01). Pure.
 *
 * @example destinationFor(AGENT_TARGETS.claude, "global", { home: "/h" })
 *   // → "/h/.claude/skills/feature-forge"
 */
export function destinationFor(
  target: AgentTarget,
  scope: Scope,
  opts?: ResolveOpts,
): string {
  const roots = resolveRoots(opts);
  const root = scopeRootFor(scope, roots);
  return path.resolve(
    root,
    target.configDirName,
    target.installSubdir,
    FEATURE_FORGE_NS,
  );
}

/**
 * Detect a single agent on the host (REQ-DET-02). Detection is decided solely by the presence
 * of the agent's config dir under the active scope root (a `stat`, never an agent subprocess).
 *
 * Populates `configDirsProbed` (named in the zero-detection report, REQ-DET-04), `destination`
 * (the resolved install dest for the active scope), and the advisory-only `cliOnPath` (never the
 * detection signal). Total: any valid `AgentId` yields a `DetectionResult`; absence is
 * `detected: false`, never an error.
 */
export function detectAgent(id: AgentId, opts?: ResolveOpts): DetectionResult {
  const target = AGENT_TARGETS[id];
  const scope: Scope = opts?.scope ?? "project";
  const roots = resolveRoots(opts);
  const root = scopeRootFor(scope, roots);

  // Primary signal (REQ-DET-02): presence of the config dir under the active scope root.
  const configDir = path.resolve(root, target.configDirName);
  const detected = probeConfigDir(configDir);

  return {
    agent: id,
    detected,
    configDirsProbed: [configDir],
    destination: destinationFor(target, scope, opts),
    cliOnPath: cliOnPath(id), // advisory only; never gates `detected`
  };
}

/** Options for {@link detectAgents}: {@link ResolveOpts} plus a single-agent scope (REQ-FLAG-01). */
export interface DetectAgentsOpts extends ResolveOpts {
  /** Restrict detection to this one agent (`--agent/-a`). Absent ⇒ all five (REQ-DET-03). */
  readonly only?: AgentId;
}

/**
 * Detect every supported agent in canonical `AGENT_IDS` order (REQ-DET-03). Pass `opts.only`
 * to scope to a single agent (REQ-FLAG-01); the result is then a one-element array. The default
 * project/global scope comes from `opts.scope`. Total — never throws; each agent is probed
 * independently.
 */
export function detectAgents(opts?: DetectAgentsOpts): DetectionResult[] {
  const ids: readonly AgentId[] = opts?.only ? [opts.only] : AGENT_IDS;
  return ids.map((id) => detectAgent(id, opts));
}

/**
 * Build the clear, actionable message for the zero-agents-detected case (REQ-DET-04). Names
 * every config dir probed (drawn from the supplied results' `configDirsProbed`) so the user sees
 * exactly where the installer looked. Creates no directory and produces no opaque error.
 * Pure: derives text from already-computed {@link DetectionResult}s.
 */
export function formatZeroDetection(results: DetectionResult[], scope: Scope): string {
  const probed = results.flatMap((r) => r.configDirsProbed);
  const lines = [
    `No supported coding agents detected (scope: ${scope}).`,
    `Probed config directories (none present):`,
    ...probed.map((p) => `  - ${p}`),
    `No directories were created. Install an agent (or pass --global/project scope, or`,
    `--source for tests) and re-run.`,
  ];
  return lines.join("\n");
}
