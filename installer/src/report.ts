/**
 * The run reporter (spec 07 §3.5/§3.6). Pure: turns a `RunReport` into a string;
 * the caller (`cli.ts`) writes it. No I/O. Imports only types from `./types.js`.
 *
 * The `--json` form emits the same `RunReport` data — the machine surface the
 * `agent-detection-map` consumers (OS-matrix dry-runs) read (REQ-DET-05).
 */

import {
  type AgentReport,
  type ErrorCode,
  type FileActionKind,
  type InstallerError,
  type RunReport,
} from "./types.js";

/** Options for rendering a run report. */
export interface RenderOpts {
  /** Emit machine-readable JSON instead of human text (REQ-DET-05, REQ-OBS-01). */
  readonly json: boolean;
}

/**
 * Render a RunReport to a string (REQ-OBS-01). Pure — no I/O; the caller writes it.
 *
 * Human form (default): a header line, then per agent a block, then a final
 * `Summary: N ok, N failed (exit X)` line. JSON form: `JSON.stringify(report)`
 * (the same RunReport data) so non-Node consumers can parse it (REQ-DET-05).
 *
 * @param report - the assembled run report.
 * @param opts - { json } selecting the output form.
 * @returns the rendered string (no trailing newline; the caller adds one).
 */
export function renderReport(report: RunReport, opts: RenderOpts): string {
  if (opts.json) {
    return JSON.stringify(report);
  }
  return renderHuman(report);
}

/** Human-readable rendering (REQ-OBS-01/02). */
function renderHuman(report: RunReport): string {
  const out: string[] = [];
  const dr = report.dryRun ? " — dry-run" : "";
  out.push(`${report.subcommand} (${report.scope}, ${report.mode})${dr}`);

  for (const a of report.agents) {
    out.push(...renderAgent(report.subcommand, a));
  }

  // Run-level rauf preflight failure (spec 07 §3.2): skills still installed, but surface it.
  if (report.raufError) {
    out.push(`rauf: FAILED — ${report.raufError.code}`);
    out.push(`  ${formatError(report.raufError)}`);
  }

  const okCount = report.agents.filter((a) => a.ok).length;
  const failCount = report.agents.length - okCount;
  out.push(`Summary: ${okCount} ok, ${failCount} failed (exit ${report.exitCode})`);
  return out.join("\n");
}

/** One agent's block: status line, per-file actions, and (if failed) the actionable error. */
function renderAgent(subcommand: RunReport["subcommand"], a: AgentReport): string[] {
  const lines: string[] = [];

  if (subcommand === "list") {
    // Decode the synthetic status rows (§3.3) into one human line.
    const status = a.actions.map((f) => f.relpath).join("  ");
    lines.push(`${a.agent}: ${a.detected ? "detected" : "not detected"}  ${status}`);
    const note = confidenceNote(a);
    if (note) lines.push(`  ${note}`);
    return lines;
  }

  if (!a.ok && a.error) {
    lines.push(`${a.agent}: FAILED — ${a.error.code}`);
    lines.push(`  ${formatError(a.error)}`); // actionable: agent + path + remedy (REQ-OBS-02)
    return lines;
  }

  lines.push(`${a.agent}: ok`);
  for (const f of a.actions) {
    lines.push(`  ${actionVerb(f.action)} ${f.relpath}`);
  }
  const note = confidenceNote(a);
  if (note) lines.push(`  ${note}`);
  if (a.raufPin) lines.push(`  rauf default runner pinned: ${a.raufPin}`);
  return lines;
}

/**
 * Honest per-agent confidence note (A4 / Finding 6): silent for fully-trusted targets
 * (`confirmed`/`verified-current`), explicit for `best-known`/`unsupported` so a user knows
 * an install path may not be auto-loaded by that agent and where to check current docs. Pure.
 */
function confidenceNote(a: AgentReport): string | null {
  if (!a.confidence || a.confidence === "confirmed" || a.confidence === "verified-current") {
    return null;
  }
  const where = a.docsUrl ? ` — see ${a.docsUrl}` : "";
  if (a.confidence === "unsupported") {
    return `note: ${a.agent} has no confirmed install surface (unsupported)${where}`;
  }
  return `note: ${a.agent} install path is best-known, not vendor-confirmed${where}`;
}

/** Map a FileActionKind to its human verb (REQ-OBS-01 vocabulary). */
export function actionVerb(kind: FileActionKind): string {
  switch (kind) {
    case "create":
      return "create   ";
    case "overwrite":
      return "overwrite";
    case "skip-modified":
      return "skip     "; // (locally modified — see error/remedy)
    case "unchanged":
      return "unchanged";
    case "remove":
      return "remove   ";
  }
}

/**
 * Compose a single actionable line from a structured error (REQ-OBS-02): always prefer
 * the error's own `message`/`remedy`; supply a per-code default remedy when absent. Pure.
 *
 * @param e - the structured error.
 * @returns "<message> — path: <path> — remedy: <remedy>" (agent is already in the header).
 */
export function formatError(e: InstallerError): string {
  const parts: string[] = [e.message];
  if (e.path) parts.push(`path: ${e.path}`);
  const remedy = e.remedy ?? DEFAULT_REMEDY[e.code];
  if (remedy) parts.push(`remedy: ${remedy}`);
  return parts.join(" — ");
}

/**
 * Per-code default remedy when the error did not carry one (REQ-OBS-02). Intentionally
 * `Partial` over `ErrorCode`: `UNEXPECTED` is surfaced via the `cli.ts` boundary message
 * (spec 07 §3.1/§4), not `formatError`, so it has no entry here.
 */
const DEFAULT_REMEDY: Partial<Record<ErrorCode, string>> = {
  USAGE: "run 'feature-forge --help' for usage",
  SOURCE_MISSING: "run the adapters build to generate adapters/<agent>/",
  SOURCE_INVALID: "regenerate the bundle (run the adapters build)",
  LOCALLY_MODIFIED: "re-run with --force to overwrite local changes",
  WRITE_DENIED: "check write permission to the path, or choose --global vs project scope",
  PATH_ESCAPE: "report this — a destination resolved outside the agent config dir",
  RAUF_UNRESOLVABLE:
    "the default loop will be unavailable until rauf publishes (see packaging-docs-ci); skills were still installed",
  MANIFEST_CORRUPT: "remove the corrupt .feature-forge.<scope>.json and re-run install",
};
