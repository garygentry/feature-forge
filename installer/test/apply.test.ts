/**
 * Tests for apply.ts (spec 04 §5): copy install writes files + manifest; an all-unchanged plan
 * performs zero writes and preserves updatedAt; symlink install creates a real link + records
 * mode:'symlink' + link.target; a WRITE_DENIED via an injected throwing write seam → ok:false and
 * manifest NOT written; uninstall removes recorded files + manifest (copy) and unlinks the link
 * leaving the target tree intact (symlink); a gemini copy lands a parseable gemini-extension.json.
 *
 * apply is tested directly with a hand-built ApplyContext + a real fixture LocatedSource (unit
 * tier). Imports built artifacts (../dist/*.js) and helper sources (.ts) per the type-stripping
 * import rule (progress log, item 002).
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import * as fs from "node:fs";
import * as path from "node:path";
import { apply, type ApplyContext } from "../dist/apply.js";
import { planInstall, planUpdate, resolveMode } from "../dist/plan.js";
import { locateSource, type LocatedSource } from "../dist/source.js";
import { readManifest, manifestPath } from "../dist/manifest.js";
import { planUninstall } from "../dist/manifest.js";
import type { AgentId, InstallManifest, PlannedAction, Result } from "../dist/types.js";
import { isWindows } from "../dist/fsutil.js";
import { withSandbox, type Sandbox } from "./helpers/sandbox.ts";
import { makeFixtureBundle } from "./helpers/fixtures.ts";

const NOW = "2026-06-16T00:00:00.000Z";

/** Resolve a fixture LocatedSource for `agent` from the sandbox's source root. */
function located(sb: Sandbox, agent: AgentId): LocatedSource {
  const r = locateSource(agent, { source: sb.source });
  assert.ok(r.ok, `locateSource(${agent}) should succeed`);
  return r.value;
}

/** The agent config root + namespace destination + manifest path for project scope. */
function dests(sb: Sandbox, agent: AgentId): {
  agentRoot: string;
  destination: string;
  manifestPath: string;
} {
  const cfg = { claude: ".claude", codex: ".agents", copilot: ".github", cursor: ".cursor", gemini: ".gemini", pi: ".pi" };
  const sub = { claude: "skills", codex: "skills", copilot: "", cursor: "rules", gemini: "extensions", pi: "skills" };
  const agentRoot = path.join(sb.cwd, cfg[agent as keyof typeof cfg]);
  const destination = path.join(agentRoot, sub[agent as keyof typeof sub], "feature-forge");
  return { agentRoot, destination, manifestPath: manifestPath(agent, "project", sb.resolve()) };
}

function ctxFor(
  sb: Sandbox,
  agent: AgentId,
  src: LocatedSource | null,
  mode: "copy" | "symlink",
  extra: Partial<ApplyContext> = {},
): ApplyContext {
  const d = dests(sb, agent);
  return {
    agent,
    scope: "project",
    mode,
    agentRoot: d.agentRoot,
    destination: d.destination,
    manifestPath: d.manifestPath,
    source: src,
    raufPin: "@garygentry/rauf@0.12.0",
    now: NOW,
    priorManifest: null,
    ...extra,
  };
}

// ---------------------------------------------------------------------------
// Copy install
// ---------------------------------------------------------------------------

test("copy install: create files land on disk with a recorded sha256 + manifest", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "claude", ["forge-1-prd", "forge-2-tech"]);
    const src = located(sb, "claude");
    const ctx = ctxFor(sb, "claude", src, "copy");

    const planned = planInstall({
      agent: "claude", scope: "project", mode: "copy", destination: ctx.destination,
      source: src, priorManifest: null, force: false, raufPin: ctx.raufPin,
    });
    assert.ok(planned.ok);

    const report = await apply(planned.value, ctx);
    assert.equal(report.ok, true);

    // Files exist on disk.
    for (const f of src.files) {
      assert.ok(fs.existsSync(path.join(ctx.destination, f.relpath)), `${f.relpath} written`);
    }

    // Manifest written with a per-file sha256 for each copied file.
    const m = readManifest(ctx.manifestPath);
    assert.ok(m.ok && m.value !== null);
    assert.equal(m.value.mode, "copy");
    assert.equal(m.value.files.length, src.files.length);
    for (const mf of m.value.files) {
      assert.equal(typeof mf.sha256, "string");
      assert.equal(mf.sha256!.length, 64);
    }
    assert.deepEqual([...m.value.skills].sort(), ["forge-1-prd", "forge-2-tech"]);
  });
});

test("copy: an all-unchanged re-run performs zero writes and does not rewrite the manifest", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "claude");
    const src = located(sb, "claude");
    const ctx = ctxFor(sb, "claude", src, "copy");

    const first = planInstall({
      agent: "claude", scope: "project", mode: "copy", destination: ctx.destination,
      source: src, priorManifest: null, force: false, raufPin: ctx.raufPin,
    });
    assert.ok(first.ok);
    await apply(first.value, ctx);

    const m1 = readManifest(ctx.manifestPath);
    assert.ok(m1.ok && m1.value !== null);
    const updatedAt1 = m1.value.updatedAt;
    const mtime1 = fs.statSync(ctx.manifestPath).mtimeMs;

    // Re-plan against the now-installed dest + prior manifest → all unchanged.
    const second = planInstall({
      agent: "claude", scope: "project", mode: "copy", destination: ctx.destination,
      source: src, priorManifest: m1.value, force: false, raufPin: ctx.raufPin,
    });
    assert.ok(second.ok);
    assert.ok(second.value.files.every((f) => f.action === "unchanged"), "all unchanged");

    const ctx2 = ctxFor(sb, "claude", src, "copy", { now: "2099-01-01T00:00:00.000Z", priorManifest: m1.value });
    const report = await apply(second.value, ctx2);
    assert.equal(report.ok, true);

    const m2 = readManifest(ctx.manifestPath);
    assert.ok(m2.ok && m2.value !== null);
    assert.equal(m2.value.updatedAt, updatedAt1, "updatedAt preserved (manifest not rewritten)");
    assert.equal(fs.statSync(ctx.manifestPath).mtimeMs, mtime1, "manifest file untouched");
  });
});

// ---------------------------------------------------------------------------
// WRITE_DENIED via injected seam — manifest NOT written
// ---------------------------------------------------------------------------

test("copy: an injected throwing write seam → ok:false WRITE_DENIED and manifest not written", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "claude");
    const src = located(sb, "claude");
    const denyingSeam = async (): Promise<Result<void>> => ({
      ok: false,
      error: { code: "WRITE_DENIED", message: "denied by test seam", path: "x", remedy: "n/a" },
    });
    const ctx = ctxFor(sb, "claude", src, "copy", { writeFileSeam: denyingSeam });

    const planned = planInstall({
      agent: "claude", scope: "project", mode: "copy", destination: ctx.destination,
      source: src, priorManifest: null, force: false, raufPin: ctx.raufPin,
    });
    assert.ok(planned.ok);

    const report = await apply(planned.value, ctx);
    assert.equal(report.ok, false);
    assert.equal(report.error?.code, "WRITE_DENIED");

    const m = readManifest(ctx.manifestPath);
    assert.ok(m.ok && m.value === null, "manifest must NOT be written on a mid-loop failure");
  });
});

// ---------------------------------------------------------------------------
// Gemini — no special branch, parseable gemini-extension.json at the destination
// ---------------------------------------------------------------------------

test("gemini copy: lands a valid parseable gemini-extension.json at the destination", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "gemini");
    const src = located(sb, "gemini");
    const ctx = ctxFor(sb, "gemini", src, "copy");

    const planned = planInstall({
      agent: "gemini", scope: "project", mode: "copy", destination: ctx.destination,
      source: src, priorManifest: null, force: false, raufPin: ctx.raufPin,
    });
    assert.ok(planned.ok);
    const report = await apply(planned.value, ctx);
    assert.equal(report.ok, true);

    const extPath = path.join(ctx.destination, "gemini-extension.json");
    assert.ok(fs.existsSync(extPath), "gemini-extension.json copied verbatim");
    const parsed = JSON.parse(fs.readFileSync(extPath, "utf8"));
    assert.equal(parsed.name, "feature-forge");
  });
});

// ---------------------------------------------------------------------------
// Copy uninstall
// ---------------------------------------------------------------------------

test("copy uninstall: removes recorded files + manifest; an untracked sibling survives", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "claude");
    const src = located(sb, "claude");
    const ctx = ctxFor(sb, "claude", src, "copy");

    const planned = planInstall({
      agent: "claude", scope: "project", mode: "copy", destination: ctx.destination,
      source: src, priorManifest: null, force: false, raufPin: ctx.raufPin,
    });
    assert.ok(planned.ok);
    await apply(planned.value, ctx);

    // Drop an untracked user file inside the namespace dir.
    const untracked = path.join(ctx.destination, "skills", "forge-1-prd", "user-notes.md");
    fs.writeFileSync(untracked, "mine\n");

    const m = readManifest(ctx.manifestPath);
    assert.ok(m.ok && m.value !== null);

    const uplan = planUninstall(m.value);
    assert.ok(uplan.ok);
    const report = await apply(uplan.value, ctxFor(sb, "claude", null, "copy", { priorManifest: m.value }));
    assert.equal(report.ok, true);

    assert.ok(fs.existsSync(untracked), "untracked user file survives uninstall (REQ-SAFE-01)");
    assert.ok(!fs.existsSync(ctx.manifestPath), "manifest deleted");
    // The recorded SKILL.md is gone.
    assert.ok(!fs.existsSync(path.join(ctx.destination, "skills", "forge-1-prd", "SKILL.md")));
  });
});

// ---------------------------------------------------------------------------
// Symlink mode (off Windows)
// ---------------------------------------------------------------------------

test("symlink install: creates a real link, records mode:'symlink' + link.target, sha256 omitted", { skip: isWindows() }, async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "claude");
    const src = located(sb, "claude");
    const mode = resolveMode(true);
    assert.equal(mode, "symlink");
    const ctx = ctxFor(sb, "claude", src, "symlink");

    const planned = planInstall({
      agent: "claude", scope: "project", mode: "symlink", destination: ctx.destination,
      source: src, priorManifest: null, force: false, raufPin: ctx.raufPin,
    });
    assert.ok(planned.ok);
    const report = await apply(planned.value, ctx);
    assert.equal(report.ok, true);

    const st = fs.lstatSync(ctx.destination);
    assert.ok(st.isSymbolicLink(), "destination is a real symlink");
    assert.equal(fs.readlinkSync(ctx.destination), src.root);

    const m = readManifest(ctx.manifestPath);
    assert.ok(m.ok && m.value !== null);
    assert.equal(m.value.mode, "symlink");
    assert.equal(m.value.link?.target, src.root);
    assert.ok(m.value.files.every((f) => f.sha256 === undefined), "per-file sha256 omitted in symlink mode");
  });
});

test("symlink uninstall: unlinks the link and leaves the source target tree intact", { skip: isWindows() }, async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "claude");
    const src = located(sb, "claude");
    const ctx = ctxFor(sb, "claude", src, "symlink");

    const planned = planInstall({
      agent: "claude", scope: "project", mode: "symlink", destination: ctx.destination,
      source: src, priorManifest: null, force: false, raufPin: ctx.raufPin,
    });
    assert.ok(planned.ok);
    await apply(planned.value, ctx);

    const m = readManifest(ctx.manifestPath);
    assert.ok(m.ok && m.value !== null);

    const uplan = planUninstall(m.value);
    assert.ok(uplan.ok);
    const report = await apply(uplan.value, ctxFor(sb, "claude", null, "symlink", { priorManifest: m.value }));
    assert.equal(report.ok, true);

    assert.ok(!fs.existsSync(ctx.destination), "the link is gone");
    // The source bundle (link target) is fully intact.
    assert.ok(fs.existsSync(path.join(src.root, "skills", "forge-1-prd", "SKILL.md")), "target tree intact");
    assert.ok(!fs.existsSync(ctx.manifestPath), "manifest deleted");
  });
});

// ---------------------------------------------------------------------------
// never throws for expected errors (PATH_ESCAPE smoke)
// ---------------------------------------------------------------------------

test("update orphan removal: a dropped source file is removed on disk", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "claude", ["forge-1-prd", "forge-2-tech"]);
    const src = located(sb, "claude");
    const ctx = ctxFor(sb, "claude", src, "copy");

    const planned = planInstall({
      agent: "claude", scope: "project", mode: "copy", destination: ctx.destination,
      source: src, priorManifest: null, force: false, raufPin: ctx.raufPin,
    });
    assert.ok(planned.ok);
    await apply(planned.value, ctx);
    const m = readManifest(ctx.manifestPath);
    assert.ok(m.ok && m.value !== null);

    // Rebuild a smaller bundle (drop forge-2-tech) and re-locate.
    fs.rmSync(path.join(sb.source, "claude"), { recursive: true, force: true });
    await makeFixtureBundle(sb, "claude", ["forge-1-prd"]);
    const src2 = located(sb, "claude");

    const upd = planUpdate({
      agent: "claude", scope: "project", mode: "copy", destination: ctx.destination,
      source: src2, priorManifest: m.value, force: false, raufPin: ctx.raufPin,
    });
    assert.ok(upd.ok);
    assert.ok(upd.value.files.some((f) => f.action === "remove"), "orphan remove planned");

    const report = await apply(upd.value, ctxFor(sb, "claude", src2, "copy", { priorManifest: m.value }));
    assert.equal(report.ok, true);
    assert.ok(!fs.existsSync(path.join(ctx.destination, "skills", "forge-2-tech", "SKILL.md")), "orphan removed");
    assert.ok(fs.existsSync(path.join(ctx.destination, "skills", "forge-1-prd", "SKILL.md")), "kept file remains");
  });
});

// ---------------------------------------------------------------------------
// F1 — a metadata-only (raufPin) change rewrites the manifest even when every
// file action is unchanged (the old allUnchanged short-circuit dropped it).
// ---------------------------------------------------------------------------

test("copy: an all-unchanged re-run with a CHANGED raufPin rewrites the manifest (F1)", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "claude");
    const src = located(sb, "claude");
    const ctx = ctxFor(sb, "claude", src, "copy");

    const first = planInstall({
      agent: "claude", scope: "project", mode: "copy", destination: ctx.destination,
      source: src, priorManifest: null, force: false, raufPin: "@garygentry/rauf@0.12.0",
    });
    assert.ok(first.ok);
    await apply(first.value, ctxFor(sb, "claude", src, "copy", { raufPin: "@garygentry/rauf@0.12.0" }));

    const m1 = readManifest(ctx.manifestPath);
    assert.ok(m1.ok && m1.value !== null);
    assert.equal(m1.value.raufPin, "@garygentry/rauf@0.12.0");

    // Re-plan: files all unchanged, but the pin was bumped.
    const second = planInstall({
      agent: "claude", scope: "project", mode: "copy", destination: ctx.destination,
      source: src, priorManifest: m1.value, force: false, raufPin: "@garygentry/rauf@0.13.0",
    });
    assert.ok(second.ok);
    assert.ok(second.value.files.every((f) => f.action === "unchanged"), "all files unchanged");

    const report = await apply(
      second.value,
      ctxFor(sb, "claude", src, "copy", { priorManifest: m1.value, raufPin: "@garygentry/rauf@0.13.0" }),
    );
    assert.equal(report.ok, true);

    const m2 = readManifest(ctx.manifestPath);
    assert.ok(m2.ok && m2.value !== null);
    assert.equal(m2.value.raufPin, "@garygentry/rauf@0.13.0", "pin change persisted despite all-unchanged files");
  });
});

// ---------------------------------------------------------------------------
// F3 — a TOCTOU vanish on the mirror unchanged-reconstruct path returns an err
// Result, never throws ENOENT out of apply (would abort every sibling agent).
// ---------------------------------------------------------------------------

test("copy: a vanished mirror file on the reconstruct path → err Result, not a throw (F3)", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "codex");
    const src = located(sb, "codex");
    const ctx = ctxFor(sb, "codex", src, "copy");
    const mirrorRoot = path.join(sb.cwd, ".codex");
    const mirrorDest = path.join(mirrorRoot, "agents");

    // Prior manifest records the mirror placement but WITHOUT this file, so apply takes the
    // reconstruct-by-hash branch (priorByPath miss) — and the file is absent on disk (TOCTOU vanish).
    const prior: InstallManifest = {
      schemaVersion: 2, agent: "codex", scope: "project", mode: "copy",
      destination: ctx.destination, featureForgeVersion: null, sourceHash: "deadbeef",
      raufPin: ctx.raufPin, installedAt: NOW, updatedAt: NOW, skills: [], files: [],
      placements: [{ kind: "mirror", root: mirrorRoot, destination: mirrorDest, files: [] }],
    };
    // One unchanged primary action keeps apply past its empty-plan no-op short-circuit (carried
    // forward, no disk read) so the crafted mirror placement below is the only thing that can fail.
    const planned: PlannedAction = {
      agent: "codex", scope: "project", mode: "copy", destination: ctx.destination,
      raufPin: ctx.raufPin,
      files: [{ relpath: src.files[0].relpath, action: "unchanged" }],
      placements: [{
        kind: "mirror", root: mirrorRoot, destination: mirrorDest,
        files: [{ relpath: "vanished.toml", action: "unchanged", srcRelpath: "vanished.toml" }],
      }],
    };

    // Must resolve to an err Result — never reject/throw.
    const report = await apply(planned, ctxFor(sb, "codex", src, "copy", { priorManifest: prior }));
    assert.equal(report.ok, false);
    assert.equal(report.error?.code, "UNEXPECTED");
  });
});
