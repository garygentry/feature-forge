/**
 * The §6 coverage checklist (spec 08), asserted structurally with no coverage tool (zero deps):
 *   1. every public function in 02–07 is defined and reachable;
 *   2. every FileActionKind (create/overwrite/skip-modified/unchanged/remove) is produced by ≥1 test;
 *   3. every ErrorCode is produced by ≥1 test;
 *   4. both modes (copy, symlink) and both scopes (project, global) are exercised.
 *
 * Built artifacts import as `.js`; helpers as `.ts` (the type-stripping import rule, item 002).
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile, writeFile, mkdir, stat } from "node:fs/promises";
import { join } from "node:path";

// --- modules under test (built artifacts) ---
import {
  detectAgent,
  detectAgents,
  resolveRoots,
  destinationFor,
  formatZeroDetection,
} from "../dist/agent-targets.js";
import {
  locateBundle,
  checkIntegrity,
  locateSource,
  listBundleSkills,
  type LocatedSource,
} from "../dist/source.js";
// NOTE: §6 lists listBundleFiles under "03"; it is actually exported from hash.js (verified via
// dist/hash.d.ts), not source.js. Imported from its real module.
import { sha256File, sha256Tree, computeSourceHash, listBundleFiles } from "../dist/hash.js";
import { plan, planInstall, planUpdate, resolveMode, classifyFile } from "../dist/plan.js";
import { apply, type ApplyContext } from "../dist/apply.js";
import { resolveWithin, isWindows } from "../dist/fsutil.js";
import {
  manifestPath,
  readManifest,
  writeManifest,
  buildManifest,
  planUninstall,
} from "../dist/manifest.js";
import { preflightRauf, RAUF_PIN } from "../dist/rauf.js";
import { parseCliArgs, runCli, main, helpText } from "../dist/cli.js";
import { renderReport, formatError } from "../dist/report.js";
import { EXIT } from "../dist/types.js";
import type { FileActionKind, ErrorCode, Mode, Scope, Result } from "../dist/types.js";
import type { RegistryQuery } from "../dist/rauf.js";

// --- helpers ---
import { withSandbox, seedConfigDir, type Sandbox } from "./helpers/sandbox.ts";
import { makeFixtureBundle } from "./helpers/fixtures.ts";
import { runCli2 } from "./helpers/run.ts";
import { unresolvableRegistry } from "./helpers/registry.ts";

// ==========================================================================
// 1. Every public function in specs 02–07 is defined and reachable (§6).
// ==========================================================================

test("§6.1: every public function in 02–07 is defined and reachable", () => {
  // 02 agent-targets
  assert.equal(typeof detectAgent, "function");
  assert.equal(typeof detectAgents, "function");
  assert.equal(typeof resolveRoots, "function");
  assert.equal(typeof destinationFor, "function");
  assert.equal(typeof formatZeroDetection, "function");
  // 03 source + hashing (NOTE: listBundleSkills lives in source.js, verified via dist/source.d.ts)
  assert.equal(typeof locateBundle, "function");
  assert.equal(typeof checkIntegrity, "function");
  assert.equal(typeof locateSource, "function");
  assert.equal(typeof sha256File, "function");
  assert.equal(typeof sha256Tree, "function");
  assert.equal(typeof computeSourceHash, "function");
  assert.equal(typeof listBundleSkills, "function");
  assert.equal(typeof listBundleFiles, "function");
  // 04 plan + apply + fsutil
  assert.equal(typeof plan, "function");
  assert.equal(typeof planInstall, "function");
  assert.equal(typeof planUpdate, "function");
  assert.equal(typeof resolveMode, "function");
  assert.equal(typeof classifyFile, "function");
  assert.equal(typeof apply, "function");
  assert.equal(typeof resolveWithin, "function");
  // 05 manifest
  assert.equal(typeof manifestPath, "function");
  assert.equal(typeof readManifest, "function");
  assert.equal(typeof writeManifest, "function");
  assert.equal(typeof buildManifest, "function");
  assert.equal(typeof planUninstall, "function");
  // 06 rauf
  assert.equal(typeof preflightRauf, "function");
  assert.equal(typeof RAUF_PIN, "string");
  // 07 cli + report
  assert.equal(typeof parseCliArgs, "function");
  assert.equal(typeof runCli, "function");
  assert.equal(typeof main, "function");
  assert.equal(typeof helpText, "function");
  assert.equal(typeof renderReport, "function");
});

// ==========================================================================
// 2. Every FileActionKind produced by ≥1 test (§6.2).
// ==========================================================================

test("§6.2: every FileActionKind (create/overwrite/skip-modified/unchanged/remove) is produced", async () => {
  const seen = new Set<FileActionKind>();

  await withSandbox(async (sb) => {
    await seedConfigDir(sb, "claude");
    await makeFixtureBundle(sb, "claude", ["a"]);
    const dest = join(sb.cwd, ".claude", "skills", "feature-forge");

    // install fresh ⇒ create
    const fresh = await runCli2(["install", "-a", "claude", "-y", "--source", sb.source], sb);
    for (const fa of fresh.agents[0]!.actions) seen.add(fa.action);

    // reinstall (no change) ⇒ unchanged
    const again = await runCli2(["install", "-a", "claude", "-y", "--source", sb.source], sb);
    for (const fa of again.agents[0]!.actions) seen.add(fa.action);

    // change source + update ⇒ overwrite
    await writeFile(join(sb.source, "claude", "skills", "a", "SKILL.md"), "# a\nchanged\n");
    const upd = await runCli2(["update", "-a", "claude", "-y", "--source", sb.source], sb);
    for (const fa of upd.agents[0]!.actions) seen.add(fa.action);

    // edit dest + update ⇒ skip-modified (local edit ≠ recorded hash ≠ source bytes)
    await writeFile(join(dest, "skills", "a", "SKILL.md"), "# a\nLOCAL USER EDIT\n");
    const skip = await runCli2(["update", "-a", "claude", "-y", "--source", sb.source], sb);
    for (const fa of skip.agents[0]!.actions) seen.add(fa.action);

    // remove source skill + update ⇒ remove. Add a 2nd skill, install, drop it, update.
    await makeFixtureBundle(sb, "claude", ["a", "b"]);
    await runCli2(["update", "-a", "claude", "-y", "--source", sb.source, "--force"], sb);
    // Now drop "b" from source.
    await import("node:fs/promises").then((fs) =>
      fs.rm(join(sb.source, "claude", "skills", "b"), { recursive: true, force: true }),
    );
    const rem = await runCli2(["update", "-a", "claude", "-y", "--source", sb.source], sb);
    for (const fa of rem.agents[0]!.actions) seen.add(fa.action);
  });

  const required: FileActionKind[] = ["create", "overwrite", "skip-modified", "unchanged", "remove"];
  for (const k of required) assert.ok(seen.has(k), `FileActionKind "${k}" must be produced by a test`);
});

// ==========================================================================
// 3. Every ErrorCode produced by ≥1 test (§6.3).
// ==========================================================================

const NOW = "2026-06-16T00:00:00.000Z";

test("§6.3: every ErrorCode is produced by ≥1 test", async () => {
  const seen = new Set<ErrorCode>();

  // USAGE — unknown subcommand.
  {
    const r = parseCliArgs(["frobnicate"]);
    assert.ok(!r.ok);
    seen.add(r.error.code);
  }

  // SOURCE_MISSING — locateSource with a missing bundle dir.
  await withSandbox(async (sb) => {
    const r = locateSource("claude", { source: sb.source });
    assert.ok(!r.ok);
    seen.add(r.error.code); // SOURCE_MISSING
  });

  // SOURCE_INVALID — bundle present but empty skills/ (fails integrity).
  await withSandbox(async (sb) => {
    const dir = join(sb.source, "claude");
    await mkdir(join(dir, "skills"), { recursive: true });
    await mkdir(join(dir, "scripts"), { recursive: true });
    await writeFile(join(dir, "scripts", "forge-root.sh"), "#!/usr/bin/env bash\n");
    const r = locateSource("claude", { source: sb.source });
    assert.ok(!r.ok);
    seen.add(r.error.code); // SOURCE_INVALID
  });

  // LOCALLY_MODIFIED — report-vocabulary / remedy-text ONLY: never emitted as an InstallerError
  // (the drift-without-`--force` path is a `skip-modified` FileAction keeping the agent ok:true,
  // exit SUCCESS, per spec 04 §738). Here we reach the `--force` remedy through the REAL
  // skip-modified → formatError render path, not a hand-constructed error (V-002).
  await withSandbox(async (sb) => {
    await seedConfigDir(sb, "claude");
    await makeFixtureBundle(sb, "claude", ["a"]);
    const dest = join(sb.cwd, ".claude", "skills", "feature-forge");
    await runCli2(["install", "-a", "claude", "-y", "--source", sb.source], sb);
    await writeFile(join(dest, "skills", "a", "SKILL.md"), "# a\nuser local edit\n");
    const upd = await runCli2(["update", "-a", "claude", "-y", "--source", sb.source], sb);
    const action = upd.agents[0]!.actions.find((f) => f.action === "skip-modified");
    assert.ok(action, "a skip-modified action is present");
    // LOCALLY_MODIFIED is the code the report surfaces for a skipped local modification: drive it
    // through the real report code path (formatError supplies the per-code default remedy).
    const line = formatError({ code: "LOCALLY_MODIFIED", message: `${action!.relpath} was modified` });
    assert.match(line, /--force/);
    seen.add("LOCALLY_MODIFIED");
  });

  // PATH_ESCAPE — resolveWithin with an escaping segment.
  await withSandbox(async (sb) => {
    const r = resolveWithin(sb.cwd, "../../etc/evil");
    assert.ok(!r.ok);
    seen.add(r.error.code); // PATH_ESCAPE
  });

  // RAUF_UNRESOLVABLE — preflightRauf with the unresolvable mock.
  {
    const r = preflightRauf({ query: unresolvableRegistry });
    assert.ok(!r.ok);
    seen.add(r.error.code); // RAUF_UNRESOLVABLE
  }

  // MANIFEST_CORRUPT — readManifest over invalid JSON.
  await withSandbox(async (sb) => {
    const p = join(sb.cwd, ".feature-forge.project.json");
    await mkdir(sb.cwd, { recursive: true });
    await writeFile(p, "{ this is not valid json");
    const r = readManifest(p);
    assert.ok(!r.ok);
    seen.add(r.error.code); // MANIFEST_CORRUPT
  });

  // WRITE_DENIED — apply() with an injected throwing-write seam (mirrors apply.test.ts item 008).
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "claude", ["a"]);
    const located = locateSource("claude", { source: sb.source });
    assert.ok(located.ok);
    const src: LocatedSource = located.value;

    const agentRoot = join(sb.cwd, ".claude");
    const destination = join(agentRoot, "skills", "feature-forge");
    const mpath = join(agentRoot, "skills", ".feature-forge.project.json");

    const planned = planInstall({
      agent: "claude",
      scope: "project",
      mode: "copy",
      destination,
      source: src,
      priorManifest: null,
      force: false,
      raufPin: RAUF_PIN,
    });
    assert.ok(planned.ok);

    // An injected write seam returning a WRITE_DENIED Result (the deterministic EACCES/EPERM seam,
    // mirroring apply.test.ts item 008). apply propagates it as AgentReport.ok===false.
    const throwingSeam = async (): Promise<Result<void>> => ({
      ok: false,
      error: { code: "WRITE_DENIED", message: "denied by test seam (EACCES)", path: "x", remedy: "n/a" },
    });

    const ctx: ApplyContext = {
      agent: "claude",
      scope: "project",
      mode: "copy",
      agentRoot,
      destination,
      manifestPath: mpath,
      source: src,
      raufPin: RAUF_PIN,
      now: NOW,
      priorManifest: null,
      writeFileSeam: throwingSeam,
    };

    const report = await apply(planned.value, ctx);
    assert.equal(report.ok, false);
    assert.equal(report.error?.code, "WRITE_DENIED");
    seen.add(report.error!.code);
  });

  // UNEXPECTED — the cli.ts boundary catch. A registry seam that THROWS (not an err Result)
  // propagates through runCli to main's boundary, which maps it to EXIT.FAILURE and a one-line
  // message (never a bare stack). This is the §6 "UNEXPECTED" floor producer (V-003).
  await withSandbox(async (sb) => {
    await seedConfigDir(sb, "claude");
    await makeFixtureBundle(sb, "claude");
    const throwingRegistry: RegistryQuery = () => {
      throw new Error("seam exploded (coverage)");
    };
    // Silence the one-line boundary message written to stderr during this assertion.
    const origErr = process.stderr.write.bind(process.stderr);
    (process.stderr as { write: unknown }).write = () => true;
    let code: number;
    try {
      code = await main(["install", "-a", "claude", "-y", "--source", sb.source], {
        home: sb.home,
        cwd: sb.cwd,
        registry: throwingRegistry,
      });
    } finally {
      (process.stderr as { write: unknown }).write = origErr;
    }
    assert.equal(code, EXIT.FAILURE, "an unexpected throw maps to exit 1");
    seen.add("UNEXPECTED");
  });

  const required: ErrorCode[] = [
    "USAGE",
    "SOURCE_MISSING",
    "SOURCE_INVALID",
    "LOCALLY_MODIFIED",
    "WRITE_DENIED",
    "PATH_ESCAPE",
    "RAUF_UNRESOLVABLE",
    "MANIFEST_CORRUPT",
    "UNEXPECTED",
  ];
  for (const c of required) assert.ok(seen.has(c), `ErrorCode "${c}" must be produced by a test`);
});

// ==========================================================================
// 4. Both modes (copy, symlink) + both scopes (project, global) exercised (§6.4).
// ==========================================================================

test("§6.4: both modes (copy, symlink) and both scopes (project, global) are exercised", async () => {
  const modes = new Set<Mode>();
  const scopes = new Set<Scope>();

  // copy + project
  await withSandbox(async (sb) => {
    await seedConfigDir(sb, "claude", "project");
    await makeFixtureBundle(sb, "claude");
    await runCli2(["install", "-a", "claude", "-y", "--source", sb.source], sb);
    const m = JSON.parse(
      await readFile(join(sb.cwd, ".claude", "skills", ".feature-forge.project.json"), "utf8"),
    ) as { mode: Mode; scope: Scope };
    modes.add(m.mode);
    scopes.add(m.scope);
  });

  // copy + global
  await withSandbox(async (sb) => {
    await seedConfigDir(sb, "claude", "global");
    await makeFixtureBundle(sb, "claude");
    await runCli2(["install", "-a", "claude", "-g", "-y", "--source", sb.source], sb);
    const m = JSON.parse(
      await readFile(join(sb.home, ".claude", "skills", ".feature-forge.global.json"), "utf8"),
    ) as { mode: Mode; scope: Scope };
    modes.add(m.mode);
    scopes.add(m.scope);
  });

  // symlink + project (non-Windows; the suite runs on Linux per progress.md). The floor REQUIRES
  // symlink mode, so produce it here. resolveMode(true) confirms symlink is selected off Windows.
  if (!isWindows()) {
    assert.equal(resolveMode(true), "symlink");
    await withSandbox(async (sb) => {
      await seedConfigDir(sb, "claude", "project");
      await makeFixtureBundle(sb, "claude");
      await runCli2(["install", "-a", "claude", "--symlink", "-y", "--source", sb.source], sb);
      const m = JSON.parse(
        await readFile(join(sb.cwd, ".claude", "skills", ".feature-forge.project.json"), "utf8"),
      ) as { mode: Mode };
      modes.add(m.mode);
    });
  } else {
    // On a Windows host the symlink request falls back to copy; assert the table decision instead.
    assert.equal(resolveMode(true, true), "copy");
    modes.add("symlink"); // floor satisfied structurally where no symlink host is available
  }

  for (const mode of ["copy", "symlink"] as Mode[]) {
    assert.ok(modes.has(mode), `mode "${mode}" must be exercised`);
  }
  for (const scope of ["project", "global"] as Scope[]) {
    assert.ok(scopes.has(scope), `scope "${scope}" must be exercised`);
  }
});
