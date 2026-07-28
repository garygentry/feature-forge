/**
 * The sandbox test fixture (spec 08 §3.1). Allocates a disposable HOME + project cwd +
 * adapters-source root under `os.tmpdir()`, runs a test body against them, and tears the whole
 * tree down (even on throw). No test ever touches the real `~`, cwd, or network (REQ-SEC-02).
 *
 * Reused by items 003, 005, 007, 008, 011 — name/locate exactly per spec 08 §3.1. NOT a
 * `.test.ts` file, so the `test/*.test.ts` glob ignores it.
 */

import { mkdtemp, rm, mkdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { AgentId, ResolveOpts, Scope } from "../../dist/types.js";
import { AGENT_TARGETS } from "../../dist/agent-targets.js";

/** The disposable roots a single test operates within. All absolute, all under os.tmpdir(). */
export interface Sandbox {
  /** Temp HOME — stands in for `~`; global-scope destinations resolve under here. */
  readonly home: string;
  /** Temp project dir — stands in for `process.cwd()`; project-scope destinations resolve here. */
  readonly cwd: string;
  /** Temp adapters source root — passed to the installer as `--source <dir>` / `source` flag. */
  readonly source: string;
  /** Build a ResolveOpts bound to this sandbox (never the real ~ ). */
  resolve(scope?: Scope): ResolveOpts;
}

/**
 * Allocate a fresh {@link Sandbox}, run `fn` against it, and remove the whole tree afterwards
 * (even on throw). No real `~`, cwd, or network is touched (REQ-SEC-02). Each call is
 * independent so `node --test` may run suites concurrently.
 */
export async function withSandbox(fn: (sb: Sandbox) => Promise<void>): Promise<void> {
  const base = await mkdtemp(join(tmpdir(), "ffi-test-"));
  const home = join(base, "home");
  const cwd = join(base, "project");
  const source = join(base, "adapters");
  const sb: Sandbox = {
    home,
    cwd,
    source,
    resolve: (scope: Scope = "project"): ResolveOpts => ({ home, cwd, scope }),
  };
  try {
    await fn(sb);
  } finally {
    await rm(base, { recursive: true, force: true });
  }
}

/**
 * Create an agent's config dir inside the sandbox so detection (REQ-DET-02) sees it as
 * installed. For project scope the dir is created under `cwd`; for global under `home`.
 * @returns the absolute config-dir path created.
 */
export async function seedConfigDir(
  sb: Sandbox,
  agent: AgentId,
  scope: Scope = "project",
): Promise<string> {
  const root = scope === "global" ? sb.home : sb.cwd;
  const target = AGENT_TARGETS[agent];
  const configDirName = scope === "global"
    ? target.globalConfigDirName ?? target.configDirName
    : target.projectConfigDirName ?? target.configDirName;
  const dir = join(root, configDirName);
  await mkdir(dir, { recursive: true });
  return dir;
}
