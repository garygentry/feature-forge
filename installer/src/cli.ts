#!/usr/bin/env node
/**
 * CLI entry & dispatch (spec 07). The installer's process entry point and orchestration
 * layer: it parses `process.argv` via `node:util.parseArgs`, resolves the target agent set,
 * runs the per-agent plan/apply (or list) pipeline catching per-agent failures, renders the
 * `RunReport`, and returns the process exit code.
 *
 * Zero runtime deps (`node:` built-ins only). Core functions return `Result`/`RunReport` and
 * never throw for expected errors; `main` is the single boundary that maps to exit codes and
 * touches `process`. `runCli` is the env-injectable testable core (the hermetic seam item 011
 * relies on). Named exports only.
 */

import { parseArgs } from "node:util";
import process from "node:process";
import { readFileSync, realpathSync } from "node:fs";
import { pathToFileURL } from "node:url";
import * as path from "node:path";
import {
  type AgentId,
  type AgentReport,
  type CliFlags,
  type DetectionResult,
  type ExitCode,
  type FileAction,
  type InstallManifest,
  type InstallerError,
  type Mode,
  type PlannedAction,
  type Result,
  type RunReport,
  type Scope,
  type Subcommand,
  AGENT_IDS,
  AGENT_TARGETS,
  EXIT,
  err,
  ok,
} from "./types.js";
import { detectAgent, detectAgents, agentRootFor } from "./agent-targets.js"; // 02
import { resolvePlacements } from "./placements.js"; // 02 (A4b second-root placements)
import { locateSource } from "./source.js"; // 03
import { plan, resolveMode, type PlanContext } from "./plan.js"; // 04
import { apply, type ApplyContext } from "./apply.js"; // 04
import { manifestPath, readManifest, planUninstall } from "./manifest.js"; // 05
import { preflightRauf, RAUF_PIN, type RegistryQuery } from "./rauf.js"; // 06
import { sha256File, sha256String } from "./hash.js"; // 03 (list destination-drift hashing)
import { extractManagedRegion } from "./placements.js"; // A4b managed-block drift
import { renderReport } from "./report.js"; // 09

// ---------------------------------------------------------------------------
// 1. The single CLI spec (CLI_SPEC) — source of truth for parse + help (§1.5)
// ---------------------------------------------------------------------------

/** A flag's declarative spec — drives both parseArgs config and helpText (REQ-DIST-03). */
interface FlagSpec {
  /** Long name without leading dashes, e.g. "agent". */
  readonly name: string;
  /** Single-char alias without dash, e.g. "a"; omitted if none. */
  readonly short?: string;
  /** parseArgs type. */
  readonly type: "boolean" | "string";
  /** One-line help description. */
  readonly help: string;
  /** Hidden from --help (e.g. --source for tests). */
  readonly hidden?: boolean;
  /** Placeholder shown in help for string flags, e.g. "<id>". */
  readonly arg?: string;
}

/** A subcommand's declarative spec. */
interface SubcommandSpec {
  readonly canonical: Subcommand;
  /** Accepted aliases that resolve to `canonical` (e.g. ["add"]). */
  readonly aliases: readonly string[];
  readonly help: string;
}

/** Canonical subcommand table (REQ-DIST-03, §1.2). */
export const SUBCOMMANDS: readonly SubcommandSpec[] = [
  { canonical: "install", aliases: ["add"], help: "Install feature-forge into the target agent(s)." },
  { canonical: "update", aliases: [], help: "Reconcile an existing install to the current adapters." },
  { canonical: "uninstall", aliases: ["remove"], help: "Remove a prior install (manifest-tracked files only)." },
  { canonical: "list", aliases: ["ls"], help: "Report per-agent detected / installed / up-to-date status." },
];

/** Canonical flag table (REQ-FLAG-01..05, §1.3). */
export const FLAGS: readonly FlagSpec[] = [
  { name: "agent", short: "a", type: "string", arg: "<id>", help: `Scope to one agent (${AGENT_IDS.join("|")}). Default: all detected.` },
  { name: "global", short: "g", type: "boolean", help: "Install into the user-level config dir (default: project-local)." },
  { name: "symlink", type: "boolean", help: "Symlink the bundle instead of copying (default: copy; Windows always copies)." },
  { name: "force", type: "boolean", help: "Overwrite a locally-modified destination that would otherwise be skipped." },
  { name: "dry-run", type: "boolean", help: "Print the planned actions without changing anything." },
  { name: "yes", short: "y", type: "boolean", help: "Non-interactive: assume confirmed; never block on input." },
  { name: "json", type: "boolean", help: "Emit the run report as JSON." },
  { name: "skip-rauf", type: "boolean", help: "Skip the rauf resolvability preflight (records raufPin: null)." },
  { name: "source", type: "string", arg: "<dir>", hidden: true, help: "(test only) Override the adapters source directory." },
  { name: "help", short: "h", type: "boolean", help: "Show this help and exit." },
  { name: "version", type: "boolean", help: "Print the installer version and exit." },
];

// ---------------------------------------------------------------------------
// 2. Public parse surface
// ---------------------------------------------------------------------------

/** Parsed CLI invocation: a resolved subcommand plus normalized flags. */
export interface ParsedCli {
  readonly subcommand: Subcommand;
  readonly flags: CliFlags;
}

/**
 * Parse and validate `argv` (already sliced past `node` + script — `process.argv.slice(2)`)
 * via `node:util.parseArgs` (zero-dep). Resolves aliases, rejects unknown
 * subcommand/flag/agent (and a parseArgs throw) as a `USAGE` error. Pure: no I/O, no exit.
 */
export function parseCliArgs(argv: string[]): Result<ParsedCli> {
  let parsed: ReturnType<typeof parseArgs>;
  try {
    parsed = parseArgs({ args: argv, options: buildParseOptions(), allowPositionals: true });
  } catch (e) {
    return usage(`invalid arguments: ${(e as Error).message}`);
  }

  const positionals = parsed.positionals;
  const values = parsed.values as Record<string, string | boolean | undefined>;

  const wantsHelp = values.help === true;
  const wantsVersion = values.version === true;

  // Resolve the subcommand (first positional) unless help/version short-circuits in main().
  const raw = positionals[0];
  let subcommand: Subcommand | undefined;
  if (raw !== undefined) {
    subcommand = resolveSubcommand(raw);
    if (subcommand === undefined) {
      return usage(`unknown subcommand '${raw}'. Run 'feature-forge --help' for usage.`);
    }
    if (positionals.length > 1) {
      return usage(`unexpected extra argument '${positionals[1]}'.`);
    }
  } else if (!wantsHelp && !wantsVersion) {
    return usage("no subcommand given. Run 'feature-forge --help' for usage.");
  }

  // Validate --agent against the closed set (REQ-FLAG-01).
  let agent: AgentId | undefined;
  const agentRaw = values.agent;
  if (typeof agentRaw === "string") {
    if (!isAgentId(agentRaw)) {
      return usage(`unknown agent '${agentRaw}'. Valid: ${AGENT_IDS.join(", ")}.`);
    }
    agent = agentRaw;
  }

  const flags: CliFlags = {
    agent,
    global: values.global === true,
    symlink: values.symlink === true,
    force: values.force === true,
    dryRun: values["dry-run"] === true,
    yes: values.yes === true,
    json: values.json === true,
    skipRauf: values["skip-rauf"] === true,
    source: typeof values.source === "string" ? values.source : undefined,
  };

  // help/version with no subcommand is still "ok": main() acts on flags before requiring a
  // subcommand. "list" is a harmless placeholder main() never reaches in that case.
  return ok({ subcommand: subcommand ?? "list", flags });
}

/**
 * Build the `node:util.parseArgs` `options` object from the single FLAGS spec (§1.5) so parsing
 * always equals the documented surface (REQ-DIST-03). The SOLE source of the parse config —
 * shared by `parseCliArgs` and `rawParse` so the two can never drift.
 */
function buildParseOptions(): Record<string, { type: "boolean" | "string"; short?: string }> {
  const options: Record<string, { type: "boolean" | "string"; short?: string }> = {};
  for (const f of FLAGS) {
    options[f.name] = f.short ? { type: f.type, short: f.short } : { type: f.type };
  }
  return options;
}

/** Resolve an alias/canonical token to a `Subcommand`, or undefined if unknown. */
function resolveSubcommand(token: string): Subcommand | undefined {
  for (const s of SUBCOMMANDS) {
    if (s.canonical === token || s.aliases.includes(token)) return s.canonical;
  }
  return undefined;
}

/** Narrowing guard for the closed `AgentId` set. */
function isAgentId(v: string): v is AgentId {
  return (AGENT_IDS as readonly string[]).includes(v);
}

/** Small helper: a USAGE Result (mapped to EXIT.USAGE at the boundary). */
function usage(message: string): Result<never> {
  return err({ code: "USAGE", message, remedy: "Run 'feature-forge --help' for usage." });
}

/**
 * Map a structured `InstallerError` to a process exit code (tech-spec §7).
 * "USAGE" → EXIT.USAGE (2); everything else → EXIT.FAILURE (1).
 */
export function mapErrorToExit(error: InstallerError): ExitCode {
  return error.code === "USAGE" ? EXIT.USAGE : EXIT.FAILURE;
}

// ---------------------------------------------------------------------------
// 3. The injectable programmatic entry (hermetic-test seam, §3.1a)
// ---------------------------------------------------------------------------

/**
 * Injected environment for a programmatic CLI run (the hermetic-test seam, 08 §3.4). Every
 * field is optional; an omitted field falls back to the real default `main` uses.
 */
export interface CliEnv {
  /** Stand-in for `~` — threaded into detection/destination/manifest resolution as ResolveOpts.home. */
  readonly home?: string;
  /** Stand-in for `process.cwd()` — threaded into resolution as ResolveOpts.cwd. */
  readonly cwd?: string;
  /** Mock rauf registry query (06) for the preflight; default = the real `npm view` query. */
  readonly registry?: RegistryQuery;
  /** Forced platform for the copy/symlink mode decision (REQ-FLAG-03); default = process.platform. */
  readonly platform?: NodeJS.Platform;
}

/**
 * Run the full CLI pipeline programmatically and return the assembled `RunReport` WITHOUT
 * touching `process` (no argv read, no stdout/stderr write, no exit). This is the testable
 * core (08 §3.4): it threads env.home/cwd into detection/manifest calls, env.registry into the
 * rauf preflight, and env.platform into the copy/symlink mode decision.
 */
export async function runCli(argv: string[], env: CliEnv = {}): Promise<RunReport> {
  const parsed = parseCliArgs(argv);
  if (!parsed.ok) {
    // runCli's contract is the dispatch core; parse validation is owned by main (§3.1). Direct
    // callers with malformed argv surface here as an unexpected throw (main never reaches this).
    throw new Error(parsed.error.message);
  }
  const { subcommand, flags } = parsed.value;
  return subcommand === "list"
    ? runList(flags, env)
    : runMutation(subcommand, flags, env);
}

// ---------------------------------------------------------------------------
// 4. main — the dispatch boundary (§3.1)
// ---------------------------------------------------------------------------

/**
 * Parse → help/version precedence → run pipeline (catching per-agent errors via runCli) →
 * render → exit code. The only place that writes to stdout/stderr and decides the exit code.
 * Never reads stdin (REQ-DIST-02).
 *
 * @param argv - the post-`node` argument list (`process.argv.slice(2)` in production).
 * @param env  - the injectable CLI env (the hermetic-test seam, §3.1a); default `{}` = real
 *               defaults. Tests inject a throwing seam (e.g. a registry that throws) here to
 *               exercise the UNEXPECTED boundary catch deterministically without a network call.
 */
export async function main(argv: string[], env: CliEnv = {}): Promise<ExitCode> {
  let report: RunReport;
  let json = false;
  try {
    const parsed = parseCliArgs(argv);
    if (!parsed.ok) {
      process.stderr.write(`error: ${parsed.error.message}\n\n`);
      process.stderr.write(helpText() + "\n");
      return mapErrorToExit(parsed.error); // EXIT.USAGE
    }

    const { flags } = parsed.value;
    json = flags.json;
    const meta = parseMetaFlags(argv); // --help/--version (not part of CliFlags)

    if (meta.help) {
      process.stdout.write(helpText() + "\n");
      return EXIT.SUCCESS;
    }
    if (meta.version) {
      process.stdout.write(readInstallerVersion() + "\n");
      return EXIT.SUCCESS;
    }
    if (!hadSubcommand(argv)) {
      process.stderr.write("error: no subcommand given.\n\n");
      process.stderr.write(helpText() + "\n");
      return EXIT.USAGE;
    }

    report = await runCli(argv, env);
  } catch (e) {
    // Boundary catch: an UNEXPECTED exception must never surface as a bare stack alone
    // (tech-spec §7). Print a one-line actionable message and exit 1.
    const msg = e instanceof Error ? e.message : String(e);
    process.stderr.write(`error: unexpected failure: ${msg}\n`);
    return EXIT.FAILURE;
  }

  process.stdout.write(renderReport(report, { json }) + "\n");
  return report.exitCode;
}

/** Raw parseArgs over the single FLAGS spec (shared `buildParseOptions`); null if argv is malformed. */
function rawParse(argv: string[]): ReturnType<typeof parseArgs> | null {
  try {
    return parseArgs({ args: argv, options: buildParseOptions(), allowPositionals: true });
  } catch {
    return null;
  }
}

/** Read the `--help`/`--version` booleans (recognized before subcommand validation, §1.4). */
function parseMetaFlags(argv: string[]): { help: boolean; version: boolean } {
  const parsed = rawParse(argv);
  const values = (parsed?.values ?? {}) as Record<string, string | boolean | undefined>;
  return { help: values.help === true, version: values.version === true };
}

/** True iff `argv` carries a leading positional (a subcommand token), per parseArgs. */
function hadSubcommand(argv: string[]): boolean {
  const parsed = rawParse(argv);
  return parsed !== null && parsed.positionals.length > 0;
}

// ---------------------------------------------------------------------------
// 5. runMutation — install / update / uninstall (§3.2)
// ---------------------------------------------------------------------------

/** Orchestrate a mutating run (install | update | uninstall). Never throws for expected errors. */
async function runMutation(
  subcommand: Exclude<Subcommand, "list">,
  flags: CliFlags,
  env: CliEnv,
): Promise<RunReport> {
  const scope: Scope = flags.global ? "global" : "project";
  const mode: Mode = resolveMode(flags.symlink, (env.platform ?? process.platform) === "win32");
  const ropts = { home: env.home, cwd: env.cwd, scope };

  const targets: AgentId[] = flags.agent
    ? [flags.agent]
    : detectAgents(ropts).filter((d) => d.detected).map((d) => d.agent);

  let raufPin: string | null = flags.skipRauf ? null : RAUF_PIN;
  let raufError: InstallerError | undefined;

  // Rauf preflight: install/update only, once, network only when not dry-run/skip AND there is at
  // least one target (zero detected ⇒ nothing to do, so no network query — DET-04, REQ-PERF-01).
  if (
    targets.length > 0 &&
    (subcommand === "install" || subcommand === "update") &&
    !flags.skipRauf &&
    !flags.dryRun
  ) {
    const pf = preflightRauf({ skip: flags.skipRauf, query: env.registry });
    if (!pf.ok) {
      raufError = pf.error; // RAUF_UNRESOLVABLE — recorded, does NOT abort skill installs
      raufPin = null; // not resolvable ⇒ no usable pin recorded this run
    }
  }

  const agentReports: AgentReport[] = [];
  for (const agent of targets) {
    const detection = detectAgent(agent, ropts);
    const r = await runOneAgent(subcommand, agent, detection, flags, scope, mode, raufPin, env);
    // Carry the scope-effective confidence + docs URL onto the report for honest labeling (A4).
    agentReports.push({ ...r, confidence: detection.confidence, docsUrl: detection.docsUrl });
  }

  const anyAgentFailed = agentReports.some((r) => !r.ok);
  const exitCode = anyAgentFailed || raufError !== undefined ? EXIT.FAILURE : EXIT.SUCCESS;

  // NOTE (spec 07 §3.2): the `attachRaufError(reports, raufError)` hook is intentionally elided in
  // favor of the sanctioned run-level `RunReport.raufError` field (a §3.2 MAY). renderReport surfaces
  // it and it rides the `--json` machine surface (REQ-DET-05); there is no separate attach step.
  return {
    subcommand,
    scope,
    mode,
    dryRun: flags.dryRun,
    agents: agentReports,
    exitCode,
    ...(raufError ? { raufError } : {}),
  };
}

/** Run the pipeline for a single agent, returning its AgentReport (catches every expected error). */
async function runOneAgent(
  subcommand: Exclude<Subcommand, "list">,
  agent: AgentId,
  detection: DetectionResult,
  flags: CliFlags,
  scope: Scope,
  mode: Mode,
  raufPin: string | null,
  env: CliEnv,
): Promise<AgentReport> {
  const mpath = manifestPath(agent, scope, { home: env.home, cwd: env.cwd });
  // Containment boundary = the agent's install base dir (A4: decoupled from the detection dir,
  // so codex contains under `.agents` and copilot under `.github`).
  const agentRoot = agentRootFor(AGENT_TARGETS[agent], scope, { home: env.home, cwd: env.cwd });

  // uninstall path: manifest → planUninstall → apply.
  if (subcommand === "uninstall") {
    const m = readManifest(mpath);
    if (!m.ok) return failed(agent, detection.detected, m.error);
    if (m.value === null) {
      // Nothing installed for this agent: not an error — an "ok, no-op" report.
      return { agent, detected: detection.detected, ok: true, actions: [], raufPin: null };
    }
    const rp = planUninstall(m.value);
    if (!rp.ok) return failed(agent, detection.detected, rp.error);
    const ctx: ApplyContext = {
      agent,
      scope,
      mode: m.value.mode,
      agentRoot,
      destination: m.value.destination,
      manifestPath: mpath,
      source: null,
      raufPin: null,
      now: new Date().toISOString(),
      priorManifest: m.value,
    };
    return finishAgent(agent, detection.detected, rp.value, flags, raufPin, ctx);
  }

  // install/update path: locate+integrity+fingerprint → readManifest → plan → apply.
  const located = locateSource(agent, { source: flags.source });
  if (!located.ok) return failed(agent, detection.detected, located.error);

  const prior = readManifest(mpath);
  if (!prior.ok) return failed(agent, detection.detected, prior.error);

  const planCtx: PlanContext = {
    agent,
    scope,
    mode,
    destination: detection.destination,
    source: located.value,
    priorManifest: prior.value,
    force: flags.force,
    raufPin,
    // A4b: resolve any second-root placements for this agent under the active scope (codex
    // `.codex/agents`, copilot `.github/copilot-instructions.md`); empty for the rest.
    placements: resolvePlacements(AGENT_TARGETS[agent], scope, { home: env.home, cwd: env.cwd }),
  };
  const planned = plan(subcommand, planCtx);
  if (!planned.ok) return failed(agent, detection.detected, planned.error);

  const ctx: ApplyContext = {
    agent,
    scope,
    mode,
    agentRoot,
    destination: detection.destination,
    manifestPath: mpath,
    source: located.value,
    raufPin,
    now: new Date().toISOString(),
    priorManifest: prior.value,
  };
  return finishAgent(agent, detection.detected, planned.value, flags, raufPin, ctx);
}

/** Apply a plan unless --dry-run; build the agent's report either way. */
async function finishAgent(
  agent: AgentId,
  detected: boolean,
  planned: PlannedAction,
  flags: CliFlags,
  raufPin: string | null,
  ctx: ApplyContext,
): Promise<AgentReport> {
  if (flags.dryRun) {
    // Plan only: the actions shown are exactly what a real run performs (REQ-OPS-05). No writes.
    return { agent, detected, ok: true, actions: planned.files, raufPin };
  }
  const report = await apply(planned, ctx);
  if (!report.ok) return failed(agent, detected, report.error ?? unexpected(agent));
  return { agent, detected, ok: true, actions: report.actions, raufPin };
}

/** A failed single-agent report (REQ-OBS-03): ok:false + the structured error. */
function failed(agent: AgentId, detected: boolean, error: InstallerError): AgentReport {
  return { agent, detected, ok: false, actions: [], error };
}

/** Fallback error if apply reports ok:false with no attached error (defensive). */
function unexpected(agent: AgentId): InstallerError {
  return { code: "UNEXPECTED", agent, message: `apply for "${agent}" failed without an error` };
}

// ---------------------------------------------------------------------------
// 6. runList — read-only list/ls (§3.3, REQ-OPS-04, REQ-PERF-01)
// ---------------------------------------------------------------------------

/** Orchestrate the read-only `list` operation: no network, no apply, no writes. */
async function runList(flags: CliFlags, env: CliEnv): Promise<RunReport> {
  const scope: Scope = flags.global ? "global" : "project";
  const ropts = { home: env.home, cwd: env.cwd, scope };
  const targets: AgentId[] = flags.agent ? [flags.agent] : [...AGENT_IDS];

  const agentReports: AgentReport[] = [];
  for (const agent of targets) {
    const detection = detectAgent(agent, ropts);
    const base = listOneAgent(agent, detection, flags, scope, env);
    agentReports.push({ ...base, confidence: detection.confidence, docsUrl: detection.docsUrl });
  }

  const anyFailed = agentReports.some((r) => !r.ok);
  return {
    subcommand: "list",
    scope,
    mode: "copy", // mode is irrelevant for list; report the default for shape stability
    dryRun: false,
    agents: agentReports,
    exitCode: anyFailed ? EXIT.FAILURE : EXIT.SUCCESS,
  };
}

/** Compute one agent's list status without any write or network call (REQ-PERF-01). */
function listOneAgent(
  agent: AgentId,
  detection: DetectionResult,
  flags: CliFlags,
  scope: Scope,
  env: CliEnv,
): AgentReport {
  const mpath = manifestPath(agent, scope, { home: env.home, cwd: env.cwd });
  const m = readManifest(mpath);
  if (!m.ok) return failed(agent, detection.detected, m.error);

  const installed = m.value !== null;
  // Status is carried as synthetic FileAction rows the renderer decodes (status, not file writes):
  const statusActions: FileAction[] = [
    { relpath: `detected:${detection.detected}`, action: "unchanged" },
    { relpath: `installed:${installed}`, action: "unchanged" },
  ];

  if (installed && m.value !== null) {
    const located = locateSource(agent, { source: flags.source });
    if (located.ok) {
      const upToDate = located.value.sourceHash === m.value.sourceHash;
      statusActions.push({ relpath: `up-to-date:${upToDate}`, action: "unchanged" });
    } else {
      statusActions.push({ relpath: "up-to-date:unknown(source-missing)", action: "unchanged" });
    }

    // Destination drift (REQ-SAFE-03, §5.13 list half): a copy-mode install is "drifted" when any
    // manifest-recorded file's bytes on disk no longer match its recorded sha256 — a local user
    // edit, independent of whether the SOURCE changed. Reads ONLY the manifest (per-file sha256)
    // against a fresh local hash (no network, no source needed). Symlink mode has no per-file
    // sha256 to compare, so drift is reported as not-applicable.
    statusActions.push({ relpath: `drift:${detectDestinationDrift(m.value)}`, action: "unchanged" });
  }

  return {
    agent,
    detected: detection.detected,
    ok: true,
    actions: statusActions,
    raufPin: m.value?.raufPin ?? null,
  };
}

/**
 * Return `"true"` if any manifest-recorded file's on-disk bytes differ from its recorded sha256
 * (a locally-modified destination, REQ-SAFE-03), `"false"` if every recorded file matches, or
 * `"n/a(symlink)"` for a symlink-mode primary install (no per-file sha256 to compare). A missing
 * recorded file also counts as drift. Pure read of the manifest's per-file sha256 against a fresh
 * local hash — no network, no source bundle needed (REQ-PERF-01). Hash errors are swallowed as drift
 * (an unreadable recorded file is itself a deviation from the clean install).
 *
 * Secondary placements (A4b) are checked in EVERY mode — they are always copy-written with a recorded
 * hash even when the primary namespace is a symlink, so ignoring them (the prior behavior) left codex
 * `.toml` mirrors and copilot managed blocks unwatched for drift.
 */
function detectDestinationDrift(manifest: InstallManifest): "true" | "false" | "n/a(symlink)" {
  if (detectPlacementDrift(manifest)) return "true";
  if (manifest.mode === "symlink") return "n/a(symlink)";
  for (const f of manifest.files) {
    if (f.sha256 === undefined) continue; // no recorded hash to compare against
    try {
      if (sha256File(path.join(manifest.destination, f.path)) !== f.sha256) return "true";
    } catch {
      return "true"; // unreadable/absent recorded file ⇒ drift
    }
  }
  return "false";
}

/**
 * True iff any secondary placement diverges from its recorded hash. A "mirror" file drifts when its
 * on-disk bytes differ from the recorded sha256 (destination is a DIR, paths relative to it). A
 * "managed-block" drifts when the sentinel region extracted from the (user-owned) target FILE no
 * longer hashes to the recorded region hash — or the region is gone entirely. Read errors count as
 * drift, matching the primary check.
 */
function detectPlacementDrift(manifest: InstallManifest): boolean {
  for (const p of manifest.placements ?? []) {
    for (const f of p.files) {
      if (f.sha256 === undefined) continue;
      try {
        if (p.kind === "managed-block") {
          const region = extractManagedRegion(readFileSync(p.destination, "utf8"));
          if (region === null || sha256String(region) !== f.sha256) return true;
        } else if (sha256File(path.join(p.destination, f.path)) !== f.sha256) {
          return true;
        }
      } catch {
        return true; // unreadable/absent recorded placement ⇒ drift
      }
    }
  }
  return false;
}

// ---------------------------------------------------------------------------
// 7. helpText and --version (§3.4)
// ---------------------------------------------------------------------------

/**
 * Build the full `--help` text from the single CLI_SPEC (SUBCOMMANDS + FLAGS, §1.5) so the
 * listed surface can never drift from what parseArgs accepts (REQ-DIST-03). Hidden flags
 * (--source) are omitted. Pure: returns a string, no I/O.
 */
export function helpText(): string {
  const lines: string[] = [];
  lines.push("feature-forge — cross-agent installer for the feature-forge skill suite");
  lines.push("");
  lines.push("USAGE:");
  lines.push("  feature-forge <command> [flags]");
  lines.push("");
  lines.push("COMMANDS:");
  for (const s of SUBCOMMANDS) {
    const alias = s.aliases.length ? ` (alias: ${s.aliases.join(", ")})` : "";
    lines.push(`  ${s.canonical.padEnd(10)} ${s.help}${alias}`);
  }
  lines.push("");
  lines.push("FLAGS:");
  for (const f of FLAGS) {
    if (f.hidden) continue;
    const long = `--${f.name}${f.arg ? " " + f.arg : ""}`;
    const short = f.short ? `-${f.short}, ` : "    ";
    lines.push(`  ${short}${long.padEnd(18)} ${f.help}`);
  }
  lines.push("");
  lines.push("EXAMPLES:");
  lines.push("  npx feature-forge install                 # install into all detected agents (project scope)");
  lines.push("  npx feature-forge install -a claude -g    # install into ~/.claude only");
  lines.push("  npx feature-forge update --dry-run        # preview an update, change nothing");
  lines.push("  npx feature-forge list --json             # machine-readable per-agent status");
  lines.push("  npx feature-forge uninstall -a cursor     # remove the cursor install (manifest-tracked only)");
  return lines.join("\n");
}

/**
 * Read the installer package's own version from the bundled package.json (REQ-DIST-03). Resolved
 * relative to the compiled module via `import.meta.url` so it works when run via `npx`. On any
 * read error, fall back to "unknown" (never throw from --version).
 */
function readInstallerVersion(): string {
  try {
    const url = new URL("../package.json", import.meta.url);
    const pkg = JSON.parse(readFileSync(url, "utf8")) as { version?: unknown };
    return typeof pkg.version === "string" ? pkg.version : "unknown";
  } catch {
    return "unknown";
  }
}

// ---------------------------------------------------------------------------
// 8. Process entry shim
// ---------------------------------------------------------------------------

// Only run when invoked as the bin (not when imported by tests / index.ts).
// npm/npx install the bin as a SYMLINK (…/bin/feature-forge → …/dist/cli.js), so
// process.argv[1] is the symlink while import.meta.url is the resolved real path —
// resolve the symlink before comparing, or the entry point silently no-ops under
// npx / `npm i -g` (the real invocation paths). Fall back to the raw path if argv[1]
// is not a stat-able file.
const entry = process.argv[1];
function entryHref(p: string): string {
  try {
    return pathToFileURL(realpathSync(p)).href;
  } catch {
    return pathToFileURL(p).href;
  }
}
if (entry !== undefined && import.meta.url === entryHref(entry)) {
  main(process.argv.slice(2))
    .then((code) => {
      process.exitCode = code;
    })
    .catch((e) => {
      process.stderr.write(`error: fatal: ${e instanceof Error ? e.message : String(e)}\n`);
      process.exitCode = EXIT.FAILURE;
    });
}
