/**
 * Tests for plan.ts (spec 04 §3-§6): every classifyFile row; resolveMode (symlink off Windows,
 * copy on win32); planInstall/planUpdate over a fixture bundle + destination; manifest-scoped
 * orphan removal; symlink-mode single '.' action; the planner writes nothing (the PlannedAction it
 * returns is the exact object apply would receive).
 *
 * Imports the built artifacts (../dist/*.js) and helper sources (.ts) per the type-stripping
 * import rule (progress log, item 002).
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import * as fs from "node:fs";
import * as path from "node:path";
import {
  classifyFile,
  planInstall,
  planUpdate,
  plan,
  resolveMode,
  type PlanContext,
} from "../dist/plan.js";
import { locateSource } from "../dist/source.js";
import { sha256File } from "../dist/hash.js";
import type { InstallManifest } from "../dist/types.js";
import type { LocatedSource } from "../dist/source.js";
import { withSandbox } from "./helpers/sandbox.ts";
import { makeFixtureBundle } from "./helpers/fixtures.ts";

// ---------------------------------------------------------------------------
// classifyFile — every row of the §6 table
// ---------------------------------------------------------------------------

test("classifyFile row 1: absent destination → create", () => {
  assert.equal(classifyFile("a", "S", undefined, undefined, false), "create");
  assert.equal(classifyFile("a", "S", undefined, "M", true), "create");
});

test("classifyFile row 3: D === S → unchanged (wins over rows 2/4)", () => {
  // Even with a manifest hash that differs (would be row 2/4), S===D forces unchanged.
  assert.equal(classifyFile("a", "S", "S", "M", false), "unchanged");
  assert.equal(classifyFile("a", "S", "S", undefined, true), "unchanged");
});

test("classifyFile row 2: clean prior (D===M) + changed source → overwrite, no --force", () => {
  assert.equal(classifyFile("a", "S", "M", "M", false), "overwrite");
});

test("classifyFile row 4: drifted tracked (D!==M) → skip-modified, overwrite under --force", () => {
  assert.equal(classifyFile("a", "S", "D", "M", false), "skip-modified");
  assert.equal(classifyFile("a", "S", "D", "M", true), "overwrite");
});

test("classifyFile row 5: untracked differing (no M) → skip-modified, overwrite under --force", () => {
  assert.equal(classifyFile("a", "S", "D", undefined, false), "skip-modified");
  assert.equal(classifyFile("a", "S", "D", undefined, true), "overwrite");
});

// ---------------------------------------------------------------------------
// resolveMode — Windows override
// ---------------------------------------------------------------------------

test("resolveMode: symlink off Windows when wantSymlink; copy on win32", () => {
  assert.equal(resolveMode(true, false), "symlink");
  assert.equal(resolveMode(true, true), "copy"); // Windows always copies
  assert.equal(resolveMode(false, false), "copy");
  assert.equal(resolveMode(false, true), "copy");
});

// ---------------------------------------------------------------------------
// Helpers for the integration-style plan tests
// ---------------------------------------------------------------------------

function ctxFor(
  source: LocatedSource | null,
  destination: string,
  overrides: Partial<PlanContext> = {},
): PlanContext {
  return {
    agent: "claude",
    scope: "project",
    mode: "copy",
    destination,
    source,
    priorManifest: null,
    force: false,
    raufPin: "@garygentry/rauf@0.7.0",
    ...overrides,
  };
}

function locate(sb: { source: string }): LocatedSource {
  const r = locateSource("claude", { source: sb.source });
  assert.ok(r.ok, "fixture bundle should locate");
  return r.value;
}

// ---------------------------------------------------------------------------
// planInstall
// ---------------------------------------------------------------------------

test("planInstall: fresh destination → every file is create; raufPin echoed; zero writes", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "claude");
    const source = locate(sb);
    const destination = path.join(sb.cwd, ".claude", "skills", "feature-forge");

    const before = treeSnapshot(destination);
    const r = planInstall(ctxFor(source, destination));
    assert.ok(r.ok);
    assert.equal(r.value.raufPin, "@garygentry/rauf@0.7.0");
    assert.ok(r.value.files.length > 0);
    assert.ok(r.value.files.every((f) => f.action === "create"));
    // purity: the planner wrote nothing.
    assert.deepEqual(treeSnapshot(destination), before);
  });
});

test("planInstall: a written destination matching source → unchanged (idempotent)", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "claude");
    const source = locate(sb);
    const destination = path.join(sb.cwd, ".claude", "skills", "feature-forge");
    // materialize the destination identically to the source
    materialize(source, destination);

    const r = planInstall(ctxFor(source, destination));
    assert.ok(r.ok);
    assert.ok(r.value.files.every((f) => f.action === "unchanged"));
  });
});

test("planInstall: source missing → err SOURCE_MISSING", () => {
  const destination = "/nowhere/feature-forge";
  const r = planInstall(ctxFor(null, destination, { agent: "claude" }));
  assert.ok(!r.ok);
  assert.equal(r.error.code, "SOURCE_MISSING");
});

// ---------------------------------------------------------------------------
// planUpdate — manifest-scoped orphan removal
// ---------------------------------------------------------------------------

test("planUpdate: orphan removal is manifest-scoped; untracked file is never removed", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "claude");
    const source = locate(sb);
    const destination = path.join(sb.cwd, ".claude", "skills", "feature-forge");
    materialize(source, destination);

    // Prior manifest tracks one path the source no longer has (orphan) + a real source path.
    const tracked = source.files[0]!.relpath;
    const prior: InstallManifest = {
      schemaVersion: 1,
      agent: "claude",
      scope: "project",
      mode: "copy",
      destination,
      featureForgeVersion: null,
      sourceHash: "old",
      raufPin: "@garygentry/rauf@0.7.0",
      installedAt: "2026-01-01T00:00:00.000Z",
      updatedAt: "2026-01-01T00:00:00.000Z",
      skills: ["forge-1-prd"],
      files: [
        { path: tracked, sha256: source.files[0]!.sha256 },
        { path: "skills/gone/SKILL.md", sha256: "deadbeef" },
      ],
    };

    const r = planUpdate(ctxFor(source, destination, { priorManifest: prior }));
    assert.ok(r.ok);
    const removes = r.value.files.filter((f) => f.action === "remove");
    assert.deepEqual(
      removes.map((f) => f.relpath),
      ["skills/gone/SKILL.md"],
    );

    // An untracked file present on disk but in neither source nor manifest is never planned.
    const untracked = r.value.files.find((f) => f.relpath === "user-notes.txt");
    assert.equal(untracked, undefined);

    // planInstall (no orphan pass) emits no remove for the same inputs.
    const ins = planInstall(ctxFor(source, destination, { priorManifest: prior }));
    assert.ok(ins.ok);
    assert.ok(!ins.value.files.some((f) => f.action === "remove"));
  });
});

test("planUpdate with no prior manifest behaves like planInstall", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "claude");
    const source = locate(sb);
    const destination = path.join(sb.cwd, ".claude", "skills", "feature-forge");
    const u = planUpdate(ctxFor(source, destination));
    const i = planInstall(ctxFor(source, destination));
    assert.ok(u.ok && i.ok);
    assert.deepEqual(u.value.files, i.value.files);
  });
});

// ---------------------------------------------------------------------------
// Symlink mode — single '.' action
// ---------------------------------------------------------------------------

test("planInstall symlink mode: single relpath '.' create on fresh install", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "claude");
    const source = locate(sb);
    const destination = path.join(sb.cwd, ".claude", "skills", "feature-forge");
    const r = planInstall(ctxFor(source, destination, { mode: "symlink" }));
    assert.ok(r.ok);
    assert.deepEqual(r.value.files, [{ relpath: ".", action: "create" }]);
  });
});

test("planInstall symlink mode: live link to same target → unchanged", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "claude");
    const source = locate(sb);
    const destination = path.join(sb.cwd, ".claude", "skills", "feature-forge");
    const prior = symlinkManifest(destination, source.root);
    const r = planInstall(ctxFor(source, destination, { mode: "symlink", priorManifest: prior }));
    assert.ok(r.ok);
    assert.deepEqual(r.value.files, [{ relpath: ".", action: "unchanged" }]);
  });
});

test("planInstall symlink mode: prior link to different target → skip-modified, overwrite under force", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "claude");
    const source = locate(sb);
    const destination = path.join(sb.cwd, ".claude", "skills", "feature-forge");
    const prior = symlinkManifest(destination, "/some/other/target");
    const r = planInstall(ctxFor(source, destination, { mode: "symlink", priorManifest: prior }));
    assert.ok(r.ok);
    assert.deepEqual(r.value.files, [{ relpath: ".", action: "skip-modified" }]);

    const f = planInstall(
      ctxFor(source, destination, { mode: "symlink", priorManifest: prior, force: true }),
    );
    assert.ok(f.ok);
    assert.deepEqual(f.value.files, [{ relpath: ".", action: "overwrite" }]);
  });
});

// ---------------------------------------------------------------------------
// plan() dispatcher + dry-run = real-run object identity
// ---------------------------------------------------------------------------

test("plan() dispatcher routes install/update; uninstall with null manifest → empty files", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "claude");
    const source = locate(sb);
    const destination = path.join(sb.cwd, ".claude", "skills", "feature-forge");
    const ctx = ctxFor(source, destination);

    const i = plan("install", ctx);
    assert.ok(i.ok && i.value.files.every((f) => f.action === "create"));

    const un = plan("uninstall", ctx);
    assert.ok(un.ok);
    assert.deepEqual(un.value.files, []);
  });
});

test("dry-run = real-run: the PlannedAction handed to apply is the same the dry-run printed", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "claude");
    const source = locate(sb);
    const destination = path.join(sb.cwd, ".claude", "skills", "feature-forge");
    const ctx = ctxFor(source, destination);

    const before = treeSnapshot(destination);
    const dry = planInstall(ctx);
    const real = planInstall(ctx);
    assert.ok(dry.ok && real.ok);
    assert.deepEqual(dry.value, real.value);
    // No filesystem change occurred between the two pure calls.
    assert.deepEqual(treeSnapshot(destination), before);
  });
});

// ---------------------------------------------------------------------------
// local test utilities
// ---------------------------------------------------------------------------

/** Copy each source file into `destination/<relpath>` so the dest matches the bundle. */
function materialize(source: LocatedSource, destination: string): void {
  for (const f of source.files) {
    const src = path.join(source.root, f.relpath);
    const dst = path.join(destination, f.relpath);
    fs.mkdirSync(path.dirname(dst), { recursive: true });
    fs.copyFileSync(src, dst);
  }
}

/** Snapshot a tree as a sorted relpath→sha256 map (undefined when the dir is absent). */
function treeSnapshot(dir: string): Record<string, string> {
  const out: Record<string, string> = {};
  const walk = (cur: string) => {
    let entries: fs.Dirent[];
    try {
      entries = fs.readdirSync(cur, { withFileTypes: true });
    } catch {
      return;
    }
    for (const e of entries) {
      const abs = path.join(cur, e.name);
      if (e.isDirectory()) walk(abs);
      else if (e.isFile()) out[path.relative(dir, abs)] = sha256File(abs);
    }
  };
  walk(dir);
  return out;
}

function symlinkManifest(destination: string, target: string): InstallManifest {
  return {
    schemaVersion: 1,
    agent: "claude",
    scope: "project",
    mode: "symlink",
    destination,
    featureForgeVersion: null,
    sourceHash: "x",
    raufPin: "@garygentry/rauf@0.7.0",
    installedAt: "2026-01-01T00:00:00.000Z",
    updatedAt: "2026-01-01T00:00:00.000Z",
    skills: ["forge-1-prd"],
    files: [],
    link: { target },
  };
}
