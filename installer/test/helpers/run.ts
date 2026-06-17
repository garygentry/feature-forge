/**
 * The hermetic CLI driver (spec 08 §3.4): `runCli2` wraps the built `runCli` with a sandbox's
 * HOME/cwd/source roots and a default mock RegistryQuery so the whole pipeline runs against a
 * temp `~` with no real network. Item 011's e2e suite drives every scenario through this seam.
 *
 * Imports the built ../../dist/*.js (same rule as the other helpers); cross-imports the sandbox
 * helper as .ts.
 */

import { runCli, type CliEnv } from "../../dist/cli.js";
import type { RunReport } from "../../dist/types.js";
import type { RegistryQuery } from "../../dist/rauf.js";
import { resolvableRegistry } from "./registry.ts";
import type { Sandbox } from "./sandbox.ts";

/** Per-run overrides for {@link runCli2}. */
export interface RunCli2Opts {
  /** Mock rauf registry; default = a resolvable stub (no real network). */
  readonly registry?: RegistryQuery;
  /** Forced platform for the copy/symlink mode decision (e.g. "win32"). */
  readonly platform?: NodeJS.Platform;
}

/**
 * Run the CLI against a sandbox: threads `sb.home`/`sb.cwd` into resolution, defaults the rauf
 * registry to a resolvable stub, and forwards an optional forced platform. The `--source` flag
 * is the caller's responsibility (pass `--source <sb.source>/<agent-parent>` in `argv`).
 *
 * @param argv - the post-`node` argument list (e.g. `["install","-a","claude","--source",dir]`).
 * @param sb   - the active {@link Sandbox} (temp HOME/cwd/source).
 * @param opts - optional registry / platform overrides.
 * @returns the assembled {@link RunReport} (no `process` touched).
 */
export function runCli2(argv: string[], sb: Sandbox, opts: RunCli2Opts = {}): Promise<RunReport> {
  const env: CliEnv = {
    home: sb.home,
    cwd: sb.cwd,
    registry: opts.registry ?? resolvableRegistry,
    ...(opts.platform ? { platform: opts.platform } : {}),
  };
  return runCli(argv, env);
}
