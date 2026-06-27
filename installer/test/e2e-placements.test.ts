/**
 * End-to-end A4b second-root placement behavior, hermetic via `withSandbox`:
 *  - codex   → primary bundle under `.agents/skills/feature-forge` AND a mirror of `agents/*.toml`
 *              into `.codex/agents/` (where Codex actually loads custom agents).
 *  - copilot → primary bundle under `.github/feature-forge` AND a managed block merged into
 *              `.github/copilot-instructions.md`, preserving any pre-existing user content.
 * Covers install, idempotent update, --force over a user-edited block, uninstall (mirror removal +
 * block strip with file preservation), and manifest v1 → v2 back-compat read.
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile, writeFile, stat, mkdir, rm } from "node:fs/promises";
import { join } from "node:path";
import { EXIT } from "../dist/types.js";
import { withSandbox, seedConfigDir } from "./helpers/sandbox.ts";
import { makeFixtureBundle } from "./helpers/fixtures.ts";
import { runCli2 } from "./helpers/run.ts";

const exists = (p: string) => stat(p).then(() => true, () => false);

test("codex install mirrors agents/*.toml into .codex/agents and records a placement", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "codex", ["forge-1-prd"], ["forge-researcher", "forge-verifier"]);
    await seedConfigDir(sb, "codex");

    const r = await runCli2(["install", "-a", "codex", "--source", sb.source], sb);
    assert.equal(r.exitCode, EXIT.SUCCESS);

    // primary bundle
    assert.ok(await exists(join(sb.cwd, ".agents/skills/feature-forge/skills/forge-1-prd/SKILL.md")));
    // mirror (flat) under .codex/agents
    assert.ok(await exists(join(sb.cwd, ".codex/agents/forge-researcher.toml")));
    assert.ok(await exists(join(sb.cwd, ".codex/agents/forge-verifier.toml")));

    // manifest records the placement
    const mfPath = join(sb.cwd, ".agents/skills/.feature-forge.project.json");
    const mf = JSON.parse(await readFile(mfPath, "utf8"));
    assert.equal(mf.schemaVersion, 2);
    assert.equal(mf.placements.length, 1);
    assert.equal(mf.placements[0].kind, "mirror");
    assert.equal(mf.placements[0].destination, join(sb.cwd, ".codex/agents"));
    assert.deepEqual(
      mf.placements[0].files.map((f: { path: string }) => f.path).sort(),
      ["forge-researcher.toml", "forge-verifier.toml"],
    );
  });
});

test("codex update is idempotent and prunes an orphaned mirror file", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "codex", ["forge-1-prd"], ["forge-researcher", "forge-verifier"]);
    await seedConfigDir(sb, "codex");
    await runCli2(["install", "-a", "codex", "--source", sb.source], sb);

    // re-run install: no changes
    const again = await runCli2(["install", "-a", "codex", "--source", sb.source], sb);
    assert.equal(again.exitCode, EXIT.SUCCESS);

    // drop forge-verifier from the SOURCE bundle, then update → it should be pruned from the mirror
    await rm(join(sb.source, "codex/agents/forge-verifier.toml"));
    const upd = await runCli2(["update", "-a", "codex", "--source", sb.source], sb);
    assert.equal(upd.exitCode, EXIT.SUCCESS);
    assert.ok(await exists(join(sb.cwd, ".codex/agents/forge-researcher.toml")));
    assert.equal(await exists(join(sb.cwd, ".codex/agents/forge-verifier.toml")), false);
  });
});

test("copilot install merges a managed block, preserving pre-existing user content", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "copilot", ["forge-1-prd"]);
    await seedConfigDir(sb, "copilot");
    // user already has a copilot-instructions.md with their own rules
    const file = join(sb.cwd, ".github/copilot-instructions.md");
    await mkdir(join(sb.cwd, ".github"), { recursive: true });
    await writeFile(file, "# House rules\n\nAlways write tests.\n");

    const r = await runCli2(["install", "-a", "copilot", "--source", sb.source], sb);
    assert.equal(r.exitCode, EXIT.SUCCESS);

    const content = await readFile(file, "utf8");
    assert.match(content, /# House rules/);
    assert.match(content, /Always write tests\./);
    assert.match(content, /feature-forge:managed:start/);
    assert.match(content, /\.github\/feature-forge/);

    const mf = JSON.parse(
      await readFile(join(sb.cwd, ".github/.feature-forge.project.json"), "utf8"),
    );
    assert.equal(mf.placements[0].kind, "managed-block");
    assert.equal(mf.placements[0].files[0].path, "copilot-instructions.md");
    assert.ok(typeof mf.placements[0].files[0].sha256 === "string");
  });
});

test("copilot re-install is a no-op; a user edit inside the block is skipped without --force", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "copilot", ["forge-1-prd"]);
    await seedConfigDir(sb, "copilot");
    await runCli2(["install", "-a", "copilot", "--source", sb.source], sb);
    const file = join(sb.cwd, ".github/copilot-instructions.md");
    const afterInstall = await readFile(file, "utf8");

    // idempotent re-install: bytes unchanged
    await runCli2(["update", "-a", "copilot", "--source", sb.source], sb);
    assert.equal(await readFile(file, "utf8"), afterInstall);

    // user tampers INSIDE the managed region
    const tampered = afterInstall.replace("forge-1-prd", "forge-1-prd EDITED");
    await writeFile(file, tampered);
    await runCli2(["update", "-a", "copilot", "--source", sb.source], sb);
    // without --force the edit is preserved (skip-modified)
    assert.match(await readFile(file, "utf8"), /forge-1-prd EDITED/);

    // with --force the block is restored
    await runCli2(["update", "-a", "copilot", "--force", "--source", sb.source], sb);
    assert.doesNotMatch(await readFile(file, "utf8"), /EDITED/);
  });
});

test("uninstall removes the codex mirror and strips the copilot block, keeping user content", async () => {
  await withSandbox(async (sb) => {
    // codex
    await makeFixtureBundle(sb, "codex", ["forge-1-prd"], ["forge-researcher"]);
    await seedConfigDir(sb, "codex");
    await runCli2(["install", "-a", "codex", "--source", sb.source], sb);
    await runCli2(["uninstall", "-a", "codex", "--source", sb.source], sb);
    assert.equal(await exists(join(sb.cwd, ".codex/agents/forge-researcher.toml")), false);

    // copilot with surrounding user content
    await makeFixtureBundle(sb, "copilot", ["forge-1-prd"]);
    await seedConfigDir(sb, "copilot");
    const file = join(sb.cwd, ".github/copilot-instructions.md");
    await mkdir(join(sb.cwd, ".github"), { recursive: true });
    await writeFile(file, "# House rules\n\nstuff\n");
    await runCli2(["install", "-a", "copilot", "--source", sb.source], sb);
    await runCli2(["uninstall", "-a", "copilot", "--source", sb.source], sb);

    const content = await readFile(file, "utf8");
    assert.doesNotMatch(content, /feature-forge:managed/);
    assert.match(content, /# House rules/);
    assert.match(content, /stuff/);
  });
});

test("uninstall deletes a copilot-instructions.md that held only our block", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "copilot", ["forge-1-prd"]);
    await seedConfigDir(sb, "copilot");
    const file = join(sb.cwd, ".github/copilot-instructions.md");
    await runCli2(["install", "-a", "copilot", "--source", sb.source], sb);
    assert.ok(await exists(file));
    await runCli2(["uninstall", "-a", "copilot", "--source", sb.source], sb);
    assert.equal(await exists(file), false);
  });
});

test("manifest v1 (no placements) is still read and reconciled to v2 on update", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "codex", ["forge-1-prd"], ["forge-researcher"]);
    await seedConfigDir(sb, "codex");
    await runCli2(["install", "-a", "codex", "--source", sb.source], sb);

    // downgrade the on-disk manifest to a v1 shape (drop placements + schemaVersion 1)
    const mfPath = join(sb.cwd, ".agents/skills/.feature-forge.project.json");
    const mf = JSON.parse(await readFile(mfPath, "utf8"));
    delete mf.placements;
    mf.schemaVersion = 1;
    await writeFile(mfPath, JSON.stringify(mf, null, 2));

    // add a NEW custom agent so update has real work to do, forcing a manifest rewrite
    await makeFixtureBundle(sb, "codex", ["forge-1-prd"], ["forge-researcher", "forge-verifier"]);

    // update reads the v1 manifest without error and re-establishes the placements as v2
    const upd = await runCli2(["update", "-a", "codex", "--source", sb.source], sb);
    assert.equal(upd.exitCode, EXIT.SUCCESS);
    const mf2 = JSON.parse(await readFile(mfPath, "utf8"));
    assert.equal(mf2.schemaVersion, 2);
    assert.equal(mf2.placements[0].kind, "mirror");
    assert.deepEqual(
      mf2.placements[0].files.map((f: { path: string }) => f.path).sort(),
      ["forge-researcher.toml", "forge-verifier.toml"],
    );
  });
});
