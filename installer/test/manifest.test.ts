/**
 * Tests for manifest.ts (spec 05): manifestPath parent-sibling formula; readManifest
 * ok(null)/MANIFEST_CORRUPT; writeManifest atomic + WRITE_DENIED; buildManifest null version +
 * installedAt preservation + symlink files:[]; planUninstall copy vs symlink shapes.
 *
 * Imports the built artifacts (../dist/*.js) and the sandbox helper source (.ts) per the
 * type-stripping import rule (progress log, item 002).
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import * as fs from "node:fs";
import * as path from "node:path";
import {
  buildManifest,
  manifestPath,
  planUninstall,
  readManifest,
  writeManifest,
} from "../dist/manifest.js";
import type { InstallManifest } from "../dist/types.js";
import { withSandbox } from "./helpers/sandbox.ts";

const FIXED_NOW = () => new Date("2026-01-01T00:00:00.000Z");

function copyManifest(overrides: Partial<InstallManifest> = {}): InstallManifest {
  return {
    schemaVersion: 1,
    agent: "claude",
    scope: "global",
    mode: "copy",
    destination: "/home/u/.claude/skills/feature-forge",
    featureForgeVersion: null,
    sourceHash: "deadbeef",
    raufPin: "rauf@0.6.0",
    installedAt: "2026-01-01T00:00:00.000Z",
    updatedAt: "2026-01-01T00:00:00.000Z",
    skills: ["forge-1-prd"],
    files: [{ path: "skills/forge-1-prd/SKILL.md", sha256: "ab" }],
    ...overrides,
  };
}

// --- manifestPath -----------------------------------------------------------

test("manifestPath: parent-sibling formula (global + project)", () => {
  assert.equal(
    manifestPath("claude", "global", { home: "/home/u" }),
    "/home/u/.claude/skills/.feature-forge.global.json",
  );
  assert.equal(
    manifestPath("claude", "project", { cwd: "/work/proj" }),
    "/work/proj/.claude/skills/.feature-forge.project.json",
  );
  // cursor uses a different installSubdir (rules), same formula.
  assert.equal(
    manifestPath("cursor", "global", { home: "/home/u" }),
    "/home/u/.cursor/rules/.feature-forge.global.json",
  );
});

// --- readManifest -----------------------------------------------------------

test("readManifest: ok(null) for ENOENT", async () => {
  await withSandbox(async (sb) => {
    const p = path.join(sb.home, "nope", ".feature-forge.global.json");
    const r = readManifest(p);
    assert.ok(r.ok);
    assert.equal(r.value, null);
  });
});

test("readManifest: round-trips a valid manifest", async () => {
  await withSandbox(async (sb) => {
    const p = path.join(sb.home, ".feature-forge.global.json");
    const m = copyManifest();
    assert.ok(writeManifest(p, m).ok);
    const r = readManifest(p);
    assert.ok(r.ok);
    assert.deepEqual(r.value, m);
  });
});

test("readManifest: MANIFEST_CORRUPT on invalid JSON", async () => {
  await withSandbox(async (sb) => {
    const p = path.join(sb.home, ".feature-forge.global.json");
    fs.mkdirSync(sb.home, { recursive: true });
    fs.writeFileSync(p, "{ not json", "utf8");
    const r = readManifest(p);
    assert.ok(!r.ok);
    assert.equal(r.error.code, "MANIFEST_CORRUPT");
  });
});

test("readManifest: MANIFEST_CORRUPT on schemaVersion mismatch", async () => {
  await withSandbox(async (sb) => {
    const p = path.join(sb.home, ".feature-forge.global.json");
    fs.mkdirSync(sb.home, { recursive: true });
    fs.writeFileSync(p, JSON.stringify({ ...copyManifest(), schemaVersion: 2 }), "utf8");
    const r = readManifest(p);
    assert.ok(!r.ok);
    assert.equal(r.error.code, "MANIFEST_CORRUPT");
  });
});

// --- writeManifest ----------------------------------------------------------

test("writeManifest: atomic write leaves no .tmp and creates parent", async () => {
  await withSandbox(async (sb) => {
    const p = path.join(sb.home, "skills", ".feature-forge.global.json");
    const w = writeManifest(p, copyManifest());
    assert.ok(w.ok);
    assert.ok(fs.existsSync(p));
    assert.ok(!fs.existsSync(`${p}.tmp`));
  });
});

test("writeManifest: WRITE_DENIED on a read-only dir", async () => {
  await withSandbox(async (sb) => {
    const dir = path.join(sb.home, "ro");
    fs.mkdirSync(dir, { recursive: true });
    fs.chmodSync(dir, 0o500);
    try {
      const p = path.join(dir, ".feature-forge.global.json");
      const w = writeManifest(p, copyManifest());
      assert.ok(!w.ok);
      assert.equal(w.error.code, "WRITE_DENIED");
    } finally {
      fs.chmodSync(dir, 0o700);
    }
  });
});

// --- buildManifest ----------------------------------------------------------

test("buildManifest: featureForgeVersion null, sorts files/skills, fresh timestamps", () => {
  const m = buildManifest({
    agent: "claude",
    scope: "global",
    mode: "copy",
    destination: "/d/feature-forge",
    files: [
      { path: "b.md", sha256: "2" },
      { path: "a.md", sha256: "1" },
    ],
    skills: ["z", "a"],
    sourceHash: "h",
    raufPin: "rauf@0.6.0",
    now: FIXED_NOW,
  });
  assert.equal(m.featureForgeVersion, null);
  assert.deepEqual(
    m.files.map((f) => f.path),
    ["a.md", "b.md"],
  );
  assert.deepEqual(m.skills, ["a", "z"]);
  assert.equal(m.installedAt, "2026-01-01T00:00:00.000Z");
  assert.equal(m.updatedAt, "2026-01-01T00:00:00.000Z");
  assert.equal(m.link, undefined);
});

test("buildManifest: preserves previous.installedAt on update", () => {
  const previous = copyManifest({ installedAt: "2025-06-01T00:00:00.000Z" });
  const m = buildManifest({
    agent: "claude",
    scope: "global",
    mode: "copy",
    destination: "/d/feature-forge",
    files: [],
    skills: [],
    sourceHash: "h",
    raufPin: null,
    previous,
    now: FIXED_NOW,
  });
  assert.equal(m.installedAt, "2025-06-01T00:00:00.000Z");
  assert.equal(m.updatedAt, "2026-01-01T00:00:00.000Z");
});

test("buildManifest: symlink mode emits files:[] and records link", () => {
  const m = buildManifest({
    agent: "claude",
    scope: "global",
    mode: "symlink",
    destination: "/d/feature-forge",
    files: [],
    skills: ["forge-1-prd"],
    sourceHash: "h",
    raufPin: "rauf@0.6.0",
    link: { target: "/src/adapters/claude" },
    now: FIXED_NOW,
  });
  assert.deepEqual(m.files, []);
  assert.deepEqual(m.link, { target: "/src/adapters/claude" });
});

// --- planUninstall ----------------------------------------------------------

test("planUninstall: copy mode — one remove per files[].path in order", () => {
  const m = copyManifest({
    files: [
      { path: "skills/a/SKILL.md", sha256: "1" },
      { path: "scripts/forge-root.sh", sha256: "2" },
    ],
  });
  const r = planUninstall(m);
  assert.ok(r.ok);
  assert.deepEqual(r.value.files, [
    { relpath: "skills/a/SKILL.md", action: "remove" },
    { relpath: "scripts/forge-root.sh", action: "remove" },
  ]);
  assert.equal(r.value.mode, "copy");
});

test("planUninstall: symlink mode — single relpath '.' remove", () => {
  const m = copyManifest({
    mode: "symlink",
    files: [],
    link: { target: "/src/adapters/claude" },
  });
  const r = planUninstall(m);
  assert.ok(r.ok);
  assert.deepEqual(r.value.files, [{ relpath: ".", action: "remove" }]);
});

test("planUninstall: empty copy manifest yields empty-files plan", () => {
  const r = planUninstall(copyManifest({ files: [] }));
  assert.ok(r.ok);
  assert.deepEqual(r.value.files, []);
});
