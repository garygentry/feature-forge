/**
 * Tests for the internal detection probes (spec 02 §5.1/§5.3): probeConfigDir (primary,
 * stat-based, never throws, never mkdir) and cliOnPath (advisory only).
 * Imports the built ../dist/*.js (spec 08 §2).
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { writeFile, readdir } from "node:fs/promises";
import { join } from "node:path";
import { basename } from "node:path";
import { probeConfigDir, cliOnPath, realPathResolver } from "../dist/detect.js";
import { withSandbox, seedConfigDir } from "./helpers/sandbox.ts";

test("probeConfigDir returns true for an existing directory", async () => {
  await withSandbox(async (sb) => {
    const dir = await seedConfigDir(sb, "claude", "project");
    assert.equal(probeConfigDir(dir), true);
  });
});

test("probeConfigDir returns false (never throws) for a missing path", async () => {
  await withSandbox(async (sb) => {
    assert.equal(probeConfigDir(join(sb.cwd, ".nope")), false);
  });
});

test("probeConfigDir returns false for a non-directory (a file)", async () => {
  await withSandbox(async (sb) => {
    await seedConfigDir(sb, "claude", "project"); // ensures sb.cwd exists
    const file = join(sb.cwd, "afile");
    await writeFile(file, "x");
    assert.equal(probeConfigDir(file), false);
  });
});

test("probeConfigDir never creates the probed directory", async () => {
  await withSandbox(async (sb) => {
    await seedConfigDir(sb, "claude", "project"); // make sb.cwd exist
    const before = (await readdir(sb.cwd)).sort();
    const target = join(sb.cwd, ".gemini");
    assert.equal(probeConfigDir(target), false);
    const after = (await readdir(sb.cwd)).sort();
    assert.deepEqual(after, before, "probe must not mkdir");
  });
});

test("cliOnPath is advisory and never throws; cursor is always false (no CLI)", () => {
  // cursor has no CLI_NAMES entry → false without spawning.
  assert.equal(cliOnPath("cursor"), false);
  // For other agents the result is a boolean (whatever the host PATH says) — never a throw.
  for (const id of ["claude", "codex", "copilot", "gemini", "pi"] as const) {
    assert.equal(typeof cliOnPath(id), "boolean");
  }
});

test("realPathResolver resolves a known-present binary and not an absent one (V-001)", () => {
  // process.execPath is the running `node` binary; its basename is reliably on PATH in CI.
  const nodeBin = basename(process.execPath); // "node" (or "node.exe" on Windows)
  assert.equal(realPathResolver(nodeBin), true, "the running node binary must resolve on PATH");
  // A binary that cannot plausibly exist on PATH resolves false (never throws).
  assert.equal(
    realPathResolver("this-binary-does-not-exist-ffi-xyz"),
    false,
    "an absent binary resolves false",
  );
});

test("cliOnPath honors the injected resolver seam for present/absent (V-001)", () => {
  // Present: a resolver that always returns true makes a CLI-bearing agent report true.
  assert.equal(cliOnPath("claude", () => true), true);
  // Absent: a resolver that always returns false makes the same agent report false.
  assert.equal(cliOnPath("claude", () => false), false);
  // cursor has no CLI basename, so the resolver is never consulted (stays false).
  let consulted = false;
  assert.equal(
    cliOnPath("cursor", () => {
      consulted = true;
      return true;
    }),
    false,
  );
  assert.equal(consulted, false, "cursor never consults the resolver (no CLI basename)");
  // A throwing resolver is swallowed (advisory, never throws).
  assert.equal(
    cliOnPath("claude", () => {
      throw new Error("boom");
    }),
    false,
  );
});
