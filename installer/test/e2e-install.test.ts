/**
 * End-to-end install suite (spec 08 §5.2 dry-run=real-run, §5.3 idempotency, §5.2 SEC-01
 * positive containment, plus a global-scope install). Each test is fully hermetic via
 * `withSandbox` (temp HOME/cwd/source, mock registry) — no real `~`, no network.
 *
 * Built artifacts import with `.js`; test helpers import with `.ts` (Node type-stripping rule).
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readdir, readFile, stat, lstat } from "node:fs/promises";
import { join } from "node:path";
import { EXIT, AGENT_TARGETS } from "../dist/types.js";
import { withSandbox, seedConfigDir, type Sandbox } from "./helpers/sandbox.ts";
import { makeFixtureBundle } from "./helpers/fixtures.ts";
import { runCli2 } from "./helpers/run.ts";
import { resolvableRegistry, neverCalledRegistry } from "./helpers/registry.ts";

/** Recursively list relpath→bytes for a tree, for byte-identical snapshot comparison. */
async function snapshot(root: string): Promise<Record<string, string>> {
  const out: Record<string, string> = {};
  async function walk(dir: string, prefix: string): Promise<void> {
    let entries;
    try {
      entries = await readdir(dir, { withFileTypes: true });
    } catch {
      return; // dir absent ⇒ empty snapshot (e.g. before any install)
    }
    for (const e of entries.sort((a, b) => a.name.localeCompare(b.name))) {
      const abs = join(dir, e.name);
      const rel = prefix ? `${prefix}/${e.name}` : e.name;
      if (e.isDirectory()) await walk(abs, rel);
      else out[rel] = await readFile(abs, "utf8");
    }
  }
  await walk(root, "");
  return out;
}

/** Collect every regular-file relpath (relative to `root`) found under `root`. */
async function walkFiles(root: string): Promise<string[]> {
  const out: string[] = [];
  async function walk(dir: string, prefix: string): Promise<void> {
    let entries;
    try {
      entries = await readdir(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const e of entries) {
      const rel = prefix ? `${prefix}/${e.name}` : e.name;
      if (e.isDirectory()) await walk(join(dir, e.name), rel);
      else out.push(rel);
    }
  }
  await walk(root, "");
  return out;
}

const ISO = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/;

/** Read+parse the claude project-scope manifest for a sandbox. */
async function readManifestJson(
  sb: Sandbox,
  scope: "project" | "global" = "project",
): Promise<any> {
  const root = scope === "global" ? sb.home : sb.cwd;
  const p = join(root, ".claude", "skills", `.feature-forge.${scope}.json`);
  return JSON.parse(await readFile(p, "utf8"));
}

test("install: --dry-run prints exactly the plan a real run performs, and writes nothing", async () => {
  await withSandbox(async (sb) => {
    await seedConfigDir(sb, "claude", "project");
    await makeFixtureBundle(sb, "claude", ["forge-1-prd"]);
    const dest = join(sb.cwd, ".claude", "skills", "feature-forge");

    // Act 1 — dry run; snapshot dest before and after, assert byte-identical (wrote nothing).
    const before = await snapshot(dest);
    const dry = await runCli2(
      ["install", "-a", "claude", "--dry-run", "-y", "--source", sb.source],
      sb,
      { registry: resolvableRegistry },
    );
    const afterDry = await snapshot(dest);

    assert.equal(dry.exitCode, EXIT.SUCCESS);
    assert.deepEqual(afterDry, before, "--dry-run must not write any file");

    // Act 2 — real run.
    const real = await runCli2(
      ["install", "-a", "claude", "-y", "--source", sb.source],
      sb,
      { registry: resolvableRegistry },
    );

    assert.equal(real.exitCode, EXIT.SUCCESS);
    const dryActions = dry.agents.find((a) => a.agent === "claude")?.actions ?? [];
    const realActions = real.agents.find((a) => a.agent === "claude")?.actions ?? [];
    assert.deepEqual(realActions, dryActions, "real run actions must equal the dry-run plan");

    // Every planned `create` produced a real file on disk.
    const creates = realActions.filter((a) => a.action === "create");
    assert.ok(creates.length > 0, "the install plan should contain at least one create");
    for (const fa of creates) {
      const s = await stat(join(dest, fa.relpath));
      assert.ok(s.isFile(), `${fa.relpath} should exist after the real install`);
    }
  });
});

test("install: a second identical install is a zero-write no-op (idempotency)", async () => {
  await withSandbox(async (sb) => {
    await seedConfigDir(sb, "claude", "project");
    await makeFixtureBundle(sb, "claude", ["forge-1-prd"]);
    const dest = join(sb.cwd, ".claude", "skills", "feature-forge");

    const first = await runCli2(
      ["install", "-a", "claude", "-y", "--source", sb.source],
      sb,
    );
    assert.equal(first.exitCode, EXIT.SUCCESS);

    const treeAfterFirst = await snapshot(dest);
    const manifestAfterFirst = await readManifestJson(sb);
    assert.match(manifestAfterFirst.updatedAt, ISO, "manifest updatedAt is ISO-8601");

    // Re-run: nothing should change.
    const second = await runCli2(
      ["install", "-a", "claude", "-y", "--source", sb.source],
      sb,
    );
    assert.equal(second.exitCode, EXIT.SUCCESS);

    const actions = second.agents.find((a) => a.agent === "claude")?.actions ?? [];
    assert.ok(actions.length > 0, "the re-run report should still list the tracked files");
    for (const fa of actions) {
      assert.equal(fa.action, "unchanged", `${fa.relpath} must be unchanged on re-run`);
    }

    const treeAfterSecond = await snapshot(dest);
    assert.deepEqual(treeAfterSecond, treeAfterFirst, "dest tree must be byte-identical on re-run");

    const manifestAfterSecond = await readManifestJson(sb);
    assert.equal(
      manifestAfterSecond.updatedAt,
      manifestAfterFirst.updatedAt,
      "no file changed ⇒ manifest updatedAt must be unchanged (zero writes)",
    );
  });
});

test("install: SEC-01 positive containment — every write stays under .claude/skills/", async () => {
  await withSandbox(async (sb) => {
    await seedConfigDir(sb, "claude", "project");
    await makeFixtureBundle(sb, "claude", ["forge-1-prd"]);
    const dest = join(sb.cwd, ".claude", "skills", "feature-forge");

    const res = await runCli2(
      ["install", "-a", "claude", "-y", "--source", sb.source],
      sb,
    );
    assert.equal(res.exitCode, EXIT.SUCCESS);

    const actions = res.agents.find((a) => a.agent === "claude")?.actions ?? [];

    // Every created/written path resolves under the namespace dir (which is under .claude/skills/).
    for (const fa of actions) {
      const abs = join(dest, fa.relpath);
      assert.ok(
        abs.startsWith(join(sb.cwd, ".claude", "skills") + "/"),
        `${fa.relpath} must lie under .claude/skills/`,
      );
    }

    // Walk HOME and cwd: the only installer-written/seeded files live under .claude/skills/.
    const allowedPrefix = ".claude/skills/";
    for (const root of [sb.home, sb.cwd]) {
      for (const rel of await walkFiles(root)) {
        assert.ok(
          rel.startsWith(allowedPrefix),
          `no installer-written file may exist outside .claude/skills/ — found ${rel} under ${root}`,
        );
      }
    }

    // The manifest is the parent-sibling under .claude/skills/, and it parses.
    const manifest = await readManifestJson(sb);
    assert.equal(manifest.agent, "claude");
    // The namespace dir is a real directory (copy mode), confirming containment of bundle contents.
    const dstat = await lstat(dest);
    assert.ok(dstat.isDirectory(), "copy-mode namespace dir should be a real directory");
  });
});

test("install: DET-04 zero detected ⇒ exit SUCCESS, no namespace dir created (§5.1)", async () => {
  await withSandbox(async (sb) => {
    // Nothing seeded: no agent config dir under HOME or cwd ⇒ every agent undetected.
    // neverCalledRegistry throws if consulted — with no detected agents the rauf preflight still
    // runs, but no namespace dir may be created and the run must exit SUCCESS ("nothing to do").
    const report = await runCli2(["install", "-y", "--source", sb.source], sb, {
      registry: neverCalledRegistry,
    });

    assert.equal(report.exitCode, EXIT.SUCCESS, "zero detected is not a failure (DET-04)");
    for (const a of report.agents) {
      assert.equal(a.detected, false, `${a.agent} must be undetected`);
    }

    // No feature-forge namespace dir was created anywhere under HOME or cwd.
    for (const root of [sb.home, sb.cwd]) {
      for (const rel of await walkFiles(root)) {
        assert.ok(
          !rel.includes("feature-forge"),
          `no namespace dir may be created on the zero-detected path — found ${rel} under ${root}`,
        );
      }
    }
  });
});

test("install: DET-03 default scope acts on every detected agent, all succeed (§5.1)", async () => {
  await withSandbox(async (sb) => {
    // Seed claude + gemini with VALID bundles; run install with NO -a (default = all detected).
    await seedConfigDir(sb, "claude");
    await seedConfigDir(sb, "gemini");
    await makeFixtureBundle(sb, "claude");
    await makeFixtureBundle(sb, "gemini");

    const report = await runCli2(["install", "-y", "--source", sb.source], sb, {
      registry: resolvableRegistry,
    });

    assert.equal(report.exitCode, EXIT.SUCCESS, "all detected agents succeed ⇒ exit SUCCESS");

    for (const id of ["claude", "gemini"] as const) {
      const a = report.agents.find((r) => r.agent === id);
      assert.ok(a, `${id} present in report.agents`);
      assert.equal(a!.ok, true, `${id} install ok`);
      assert.equal(a!.detected, true, `${id} detected`);
      // The namespace dir is on disk for each agent.
      const dest = join(sb.cwd, AGENT_TARGETS[id].configDirName, AGENT_TARGETS[id].installSubdir, "feature-forge");
      assert.ok((await stat(dest)).isDirectory(), `${id} namespace dir exists on disk`);
    }
  });
});

test("install -g: global scope lands files under <home>/.claude/skills/feature-forge", async () => {
  await withSandbox(async (sb) => {
    await seedConfigDir(sb, "claude", "global");
    await makeFixtureBundle(sb, "claude", ["forge-1-prd"]);
    const dest = join(sb.home, ".claude", "skills", "feature-forge");

    const res = await runCli2(
      ["install", "-g", "-a", "claude", "-y", "--source", sb.source],
      sb,
    );
    assert.equal(res.exitCode, EXIT.SUCCESS);

    const agent = res.agents.find((a) => a.agent === "claude");
    assert.ok(agent?.ok, "claude install should succeed under global scope");

    const actions = agent?.actions ?? [];
    const creates = actions.filter((a) => a.action === "create");
    assert.ok(creates.length > 0, "global install plan should contain creates");
    for (const fa of creates) {
      const s = await stat(join(dest, fa.relpath));
      assert.ok(s.isFile(), `${fa.relpath} should exist under <home> for global scope`);
    }

    // Manifest is the global parent-sibling and records the global scope.
    const manifest = await readManifestJson(sb, "global");
    assert.equal(manifest.scope, "global");
    assert.match(manifest.installedAt, ISO, "manifest installedAt is ISO-8601");

    // Nothing leaked into the project cwd.
    const projectFiles = await walkFiles(sb.cwd);
    assert.deepEqual(projectFiles, [], "global install must not write under the project cwd");
  });
});
