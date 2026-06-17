/**
 * E2E tests (spec 08 §5.7-5.9, §5.11) driven through the hermetic CLI seam (runCli2): symlink
 * install + uninstall-target-intact, Windows-forced copy via injected platform, source-integrity /
 * partial-failure isolation across two detected agents, the gemini extension-manifest outcome, and
 * the resolveWithin PATH_ESCAPE sandbox unit. Authors ONLY this file (item 011 slice).
 *
 * Imports built artifacts as ../dist/*.js and helpers as ./helpers/*.ts per the type-stripping rule.
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { lstat, readlink, readFile, readdir, rm, stat } from "node:fs/promises";
import { join } from "node:path";
import { EXIT } from "../dist/types.js";
import { resolveWithin, isWindows } from "../dist/fsutil.js";
import { readManifest } from "../dist/manifest.js";
import { withSandbox, seedConfigDir, type Sandbox } from "./helpers/sandbox.ts";
import { makeFixtureBundle } from "./helpers/fixtures.ts";
import { runCli2 } from "./helpers/run.ts";

// Project-scope namespace + manifest paths (cli.ts derives these from AGENT_TARGETS).
const claudeDest = (sb: Sandbox) => join(sb.cwd, ".claude", "skills", "feature-forge");
const claudeManifest = (sb: Sandbox) => join(sb.cwd, ".claude", "skills", ".feature-forge.project.json");
const geminiDest = (sb: Sandbox) => join(sb.cwd, ".gemini", "extensions", "feature-forge");

/** Snapshot a directory tree as a sorted map of relpath → bytes (utf8), for byte-for-byte compare. */
async function snapshotTree(root: string): Promise<Record<string, string>> {
  const out: Record<string, string> = {};
  async function walk(dir: string, rel: string): Promise<void> {
    for (const ent of await readdir(dir, { withFileTypes: true })) {
      const abs = join(dir, ent.name);
      const r = rel ? `${rel}/${ent.name}` : ent.name;
      if (ent.isDirectory()) await walk(abs, r);
      else out[r] = await readFile(abs, "utf8");
    }
  }
  await walk(root, "");
  return out;
}

const report = (r: { agents: { agent: string }[] }, agent: string) => {
  const a = r.agents.find((x) => x.agent === agent);
  assert.ok(a, `expected an AgentReport for ${agent}`);
  return a as { agent: string; ok: boolean; error?: { code: string } };
};

// ---------------------------------------------------------------------------
// §5.7 — symlink install (non-Windows)
// ---------------------------------------------------------------------------

test("symlink install: namespace dir is a symlink to the source bundle; manifest records symlink mode", { skip: isWindows() }, async () => {
  await withSandbox(async (sb) => {
    await seedConfigDir(sb, "claude");
    await makeFixtureBundle(sb, "claude");

    const r = await runCli2(["install", "-a", "claude", "--symlink", "-y", "--source", sb.source], sb);
    assert.equal(r.exitCode, EXIT.SUCCESS);

    const dest = claudeDest(sb);
    assert.ok((await lstat(dest)).isSymbolicLink(), "namespace dir is a symlink");
    const target = await readlink(dest);
    assert.equal(target, join(sb.source, "claude"), "link target resolves to the source bundle");

    const m = readManifest(claudeManifest(sb));
    assert.ok(m.ok && m.value !== null);
    assert.equal(m.value.mode, "symlink");
    assert.equal(m.value.link?.target, join(sb.source, "claude"));
    assert.ok(m.value.files.every((f) => f.sha256 === undefined), "per-file sha256 omitted in symlink mode");
  });
});

// ---------------------------------------------------------------------------
// §5.7 SAFE-02/SEC-03 — symlink uninstall leaves the source target intact
// ---------------------------------------------------------------------------

test("symlink uninstall: link is removed and the source bundle tree is byte-for-byte intact", { skip: isWindows() }, async () => {
  await withSandbox(async (sb) => {
    await seedConfigDir(sb, "claude");
    await makeFixtureBundle(sb, "claude", ["forge-1-prd", "forge-2-tech"]);

    const inst = await runCli2(["install", "-a", "claude", "--symlink", "-y", "--source", sb.source], sb);
    assert.equal(inst.exitCode, EXIT.SUCCESS);

    const before = await snapshotTree(join(sb.source, "claude"));

    const uninst = await runCli2(["uninstall", "-a", "claude", "-y", "--source", sb.source], sb);
    assert.equal(uninst.exitCode, EXIT.SUCCESS);

    await assert.rejects(lstat(claudeDest(sb)), "the symlink is gone");

    const after = await snapshotTree(join(sb.source, "claude"));
    assert.deepEqual(after, before, "source bundle tree unchanged (byte-for-byte)");
  });
});

// ---------------------------------------------------------------------------
// §5.7 FLAG-03 — Windows always copies (platform injected; runs on any host)
// ---------------------------------------------------------------------------

test("Windows always copies: --symlink under win32 yields a real dir and manifest mode 'copy'", async () => {
  await withSandbox(async (sb) => {
    await seedConfigDir(sb, "claude");
    await makeFixtureBundle(sb, "claude");

    const r = await runCli2(["install", "-a", "claude", "--symlink", "-y", "--source", sb.source], sb, { platform: "win32" });
    assert.equal(r.exitCode, EXIT.SUCCESS);

    const dest = claudeDest(sb);
    const st = await lstat(dest);
    assert.ok(st.isDirectory() && !st.isSymbolicLink(), "namespace dir is a real directory, not a symlink");
    assert.ok((await stat(join(dest, "skills", "forge-1-prd", "SKILL.md"))).isFile(), "skill copied on disk");

    const m = readManifest(claudeManifest(sb));
    assert.ok(m.ok && m.value !== null);
    assert.equal(m.value.mode, "copy");
  });
});

// ---------------------------------------------------------------------------
// §5.8 — source integrity / partial-failure isolation (claude OK, gemini fails)
// ---------------------------------------------------------------------------

/** Drive a 2-agent install (no -a, both detected); assert claude succeeds and gemini fails with `code`. */
async function partialFailure(sb: Sandbox, code: string): Promise<void> {
  await seedConfigDir(sb, "claude");
  await seedConfigDir(sb, "gemini");
  await makeFixtureBundle(sb, "claude");
  // caller has already broken/omitted the gemini bundle before this point

  const r = await runCli2(["install", "-y", "--source", sb.source], sb);

  const claude = report(r, "claude");
  assert.equal(claude.ok, true, "claude install succeeds");
  assert.ok((await stat(join(claudeDest(sb), "skills", "forge-1-prd", "SKILL.md"))).isFile(), "claude files on disk");

  const gemini = report(r, "gemini");
  assert.equal(gemini.ok, false, "gemini install fails");
  assert.equal(gemini.error?.code, code);

  // No partial gemini install: the namespace dir must not exist.
  await assert.rejects(lstat(geminiDest(sb)), "no gemini namespace dir created");

  assert.equal(r.exitCode, EXIT.FAILURE, "run exitCode is FAILURE when any agent failed");
}

test("§5.8 partial failure: gemini bundle absent ⇒ SOURCE_MISSING; claude still installs", async () => {
  await withSandbox(async (sb) => {
    // gemini bundle deliberately not created
    await partialFailure(sb, "SOURCE_MISSING");
  });
});

test("§5.8 partial failure: gemini skills/ empty ⇒ SOURCE_INVALID; claude still installs", async () => {
  await withSandbox(async (sb) => {
    const fx = await makeFixtureBundle(sb, "gemini");
    await rm(join(fx.dir, "skills"), { recursive: true, force: true });
    await partialFailure(sb, "SOURCE_INVALID");
  });
});

test("§5.8 partial failure: gemini missing gemini-extension.json ⇒ SOURCE_INVALID; claude still installs", async () => {
  await withSandbox(async (sb) => {
    const fx = await makeFixtureBundle(sb, "gemini");
    await rm(join(fx.dir, "gemini-extension.json"), { force: true });
    await partialFailure(sb, "SOURCE_INVALID");
  });
});

// ---------------------------------------------------------------------------
// §5.9 — gemini outcome: parseable gemini-extension.json at the destination
// ---------------------------------------------------------------------------

test("§5.9 gemini outcome: a parseable gemini-extension.json lands at the gemini destination", async () => {
  await withSandbox(async (sb) => {
    await seedConfigDir(sb, "gemini");
    await makeFixtureBundle(sb, "gemini");

    const r = await runCli2(["install", "-a", "gemini", "-y", "--source", sb.source], sb);
    assert.equal(r.exitCode, EXIT.SUCCESS);

    const extPath = join(geminiDest(sb), "gemini-extension.json");
    const parsed = JSON.parse(await readFile(extPath, "utf8"));
    assert.equal(typeof parsed.name, "string");
    assert.equal(typeof parsed.version, "string");
    assert.ok(Array.isArray(parsed.skills), "skills is an array");
  });
});

// ---------------------------------------------------------------------------
// §5.11 — PATH_ESCAPE path sandbox (unit level; no write occurs)
// ---------------------------------------------------------------------------

test("§5.11 resolveWithin rejects escapes with PATH_ESCAPE before any write and admits in-root segments", async () => {
  await withSandbox(async (sb) => {
    await seedConfigDir(sb, "claude");
    const root = join(sb.cwd, ".claude");
    const before = await snapshotTree(root);

    const escape1 = resolveWithin(root, "..", "..", "etc");
    assert.ok(!escape1.ok);
    assert.equal(escape1.error.code, "PATH_ESCAPE");

    const escape2 = resolveWithin(root, "../../../evil");
    assert.ok(!escape2.ok);
    assert.equal(escape2.error.code, "PATH_ESCAPE");

    const inside = resolveWithin(root, "skills", "feature-forge");
    assert.ok(inside.ok, "an in-root segment resolves");

    const after = await snapshotTree(root);
    assert.deepEqual(after, before, "sandbox tree unchanged by resolveWithin (pure, no write)");
  });
});
