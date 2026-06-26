/**
 * Tests for source.ts (spec 03, REQ-OPS-06). --source precedence, SOURCE_MISSING/SOURCE_INVALID
 * naming the offending path, checkIntegrity passing without plugin.json, and locateSource
 * fingerprinting.
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { rm } from "node:fs/promises";
import { join } from "node:path";

import {
  locateBundle,
  checkIntegrity,
  listBundleSkills,
  locateSource,
} from "../dist/source.js";
import { computeSourceHash } from "../dist/hash.js";
import { withSandbox } from "./helpers/sandbox.ts";
import { makeFixtureBundle } from "./helpers/fixtures.ts";

test("locateBundle resolves --source to <source>/<agent> before other candidates", async () => {
  await withSandbox(async (sb) => {
    const fx = await makeFixtureBundle(sb, "claude");
    const r = locateBundle("claude", { source: sb.source });
    assert.ok(r.ok);
    assert.equal(r.value, fx.dir);
  });
});

test("locateBundle returns SOURCE_MISSING naming the expected path + remedy", async () => {
  await withSandbox(async (sb) => {
    // empty source root, no bundle written
    const r = locateBundle("codex", { source: sb.source });
    assert.ok(!r.ok);
    assert.equal(r.error.code, "SOURCE_MISSING");
    assert.equal(r.error.agent, "codex");
    assert.equal(r.error.path, join(sb.source, "codex"));
    assert.match(r.error.message, /codex/);
    assert.ok(r.error.remedy && r.error.remedy.length > 0);
  });
});

test("checkIntegrity passes for a minimal valid bundle without the Claude-only plugin.json", async () => {
  await withSandbox(async (sb) => {
    const fx = await makeFixtureBundle(sb, "claude");
    const r = checkIntegrity(fx.dir, "claude");
    assert.ok(r.ok);
  });
});

test("checkIntegrity returns SOURCE_INVALID naming a missing .feature-forge-bundle.json", async () => {
  await withSandbox(async (sb) => {
    const fx = await makeFixtureBundle(sb, "claude");
    await rm(join(fx.dir, ".feature-forge-bundle.json"), { force: true });
    const r = checkIntegrity(fx.dir, "claude");
    assert.ok(!r.ok);
    assert.equal(r.error.code, "SOURCE_INVALID");
    assert.equal(r.error.path, join(fx.dir, ".feature-forge-bundle.json"));
  });
});

test("checkIntegrity returns SOURCE_INVALID naming empty skills/", async () => {
  await withSandbox(async (sb) => {
    const fx = await makeFixtureBundle(sb, "claude");
    await rm(join(fx.dir, "skills"), { recursive: true, force: true });
    const r = checkIntegrity(fx.dir, "claude");
    assert.ok(!r.ok);
    assert.equal(r.error.code, "SOURCE_INVALID");
    assert.equal(r.error.path, join(fx.dir, "skills"));
  });
});

test("checkIntegrity returns SOURCE_INVALID naming a missing forge-root.sh", async () => {
  await withSandbox(async (sb) => {
    const fx = await makeFixtureBundle(sb, "claude");
    await rm(join(fx.dir, "scripts", "forge-root.sh"), { force: true });
    const r = checkIntegrity(fx.dir, "claude");
    assert.ok(!r.ok);
    assert.equal(r.error.code, "SOURCE_INVALID");
    assert.equal(r.error.path, join(fx.dir, "scripts", "forge-root.sh"));
  });
});

test("checkIntegrity requires gemini-extension.json for gemini only", async () => {
  await withSandbox(async (sb) => {
    const fx = await makeFixtureBundle(sb, "gemini");
    assert.ok(checkIntegrity(fx.dir, "gemini").ok);
    await rm(join(fx.dir, "gemini-extension.json"), { force: true });
    const r = checkIntegrity(fx.dir, "gemini");
    assert.ok(!r.ok);
    assert.equal(r.error.code, "SOURCE_INVALID");
    assert.equal(r.error.path, join(fx.dir, "gemini-extension.json"));
  });
});

test("listBundleSkills returns sorted skill dir names only", async () => {
  await withSandbox(async (sb) => {
    const fx = await makeFixtureBundle(sb, "claude", ["forge-2-tech", "forge-1-prd"]);
    assert.deepEqual(listBundleSkills(fx.dir), ["forge-1-prd", "forge-2-tech"]);
  });
});

test("locateSource fingerprints a valid bundle (root/sourceHash/skills/files)", async () => {
  await withSandbox(async (sb) => {
    const fx = await makeFixtureBundle(sb, "claude", ["forge-1-prd"]);
    const r = locateSource("claude", { source: sb.source });
    assert.ok(r.ok);
    assert.equal(r.value.root, fx.dir);
    assert.equal(r.value.sourceHash, computeSourceHash(fx.dir));
    assert.deepEqual(r.value.skills, ["forge-1-prd"]);
    assert.ok(r.value.files.some((f) => f.relpath === "skills/forge-1-prd/SKILL.md"));
    assert.ok(r.value.files.some((f) => f.relpath === "scripts/forge-root.sh"));
  });
});

test("locateSource returns SOURCE_MISSING then SOURCE_INVALID from its constituents", async () => {
  await withSandbox(async (sb) => {
    const missing = locateSource("claude", { source: sb.source });
    assert.ok(!missing.ok);
    assert.equal(missing.error.code, "SOURCE_MISSING");

    const fx = await makeFixtureBundle(sb, "claude");
    await rm(join(fx.dir, "scripts", "forge-root.sh"), { force: true });
    const invalid = locateSource("claude", { source: sb.source });
    assert.ok(!invalid.ok);
    assert.equal(invalid.error.code, "SOURCE_INVALID");
  });
});
