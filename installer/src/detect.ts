/**
 * Internal detection probes for the agent-detection-map surface (spec 02 §5.1, §5.3).
 *
 * Two probes, both total and non-throwing:
 *   - `probeConfigDir` — the PRIMARY detection signal: a single `fs.statSync`. Never mkdir,
 *     never throws (REQ-DET-02/04, REQ-PERF-01).
 *   - `cliOnPath` — SECONDARY, advisory only: is the agent's CLI on PATH? Never gates
 *     `detected` (REQ-DET-02). `cursor` is intentionally omitted (IDE/GUI agent, no CLI).
 *
 * Zero runtime dependencies; only `node:` built-ins.
 */

import * as fs from "node:fs";
import { execFileSync } from "node:child_process";
import type { AgentId } from "./types.js";

/**
 * The primary detection signal (REQ-DET-02): is `configDir` an existing directory?
 * Uses a single synchronous `fs.statSync` — never an agent subprocess (detection stays
 * instant, REQ-PERF-01) and never creates the dir (REQ-DET-04). Any stat failure
 * (`ENOENT` not present, `EACCES` unreadable, or a non-directory at the path) ⇒ `false`.
 *
 * Synchronous by design: exactly one stat per agent (five total), so async adds no
 * throughput and would complicate the pure-derivation surface.
 */
export function probeConfigDir(configDir: string): boolean {
  try {
    return fs.statSync(configDir).isDirectory();
  } catch {
    return false; // ENOENT / EACCES / not-a-dir → not detected (never throws, REQ-DET-04)
  }
}

/** Per-agent CLI executable basename probed on PATH (advisory only). */
const CLI_NAMES: Partial<Record<AgentId, string>> = {
  claude: "claude",
  codex: "codex",
  copilot: "copilot",
  gemini: "gemini",
  // cursor: intentionally omitted — IDE/GUI agent, no canonical CLI on PATH (REQ-DET-02).
};

/**
 * Secondary, **advisory** info (REQ-DET-02): is the agent's CLI resolvable on PATH? This is
 * reported as `DetectionResult.cliOnPath` but **never** gates `detected`. Uses the platform's
 * resolver (`where` on Windows, `command -v` elsewhere) once per agent. Any failure — no
 * resolver, not found, spawn error — yields `false`; it never throws and never blocks detection.
 *
 * Agents without a canonical CLI (cursor) always report `false` here without spawning.
 */
export function cliOnPath(id: AgentId): boolean {
  const bin = CLI_NAMES[id];
  if (!bin) return false;
  const isWin = process.platform === "win32";
  try {
    execFileSync(isWin ? "where" : "command", isWin ? [bin] : ["-v", bin], {
      stdio: "ignore",
    });
    return true;
  } catch {
    return false; // advisory; absence is normal, never an error
  }
}
