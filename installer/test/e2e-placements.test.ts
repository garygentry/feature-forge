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
import { readFile, writeFile, stat, lstat, mkdir, rm, symlink } from "node:fs/promises";
import { dirname, join } from "node:path";
import { EXIT } from "../dist/types.js";
import { isWindows } from "../dist/fsutil.js";
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

test("pi global install mirrors agents/*.md into ~/.pi/agent/agents and uninstall removes them", async () => {
  await withSandbox(async (sb) => {
    // Global scope is the npm-installer path W4 fixes: the primary bundle lands in
    // ~/.pi/agent/skills/feature-forge (not a pi-subagents package root), so agents are only
    // reachable via the mirror into ~/.pi/agent/agents, the user scope pi-subagents scans.
    await makeFixtureBundle(sb, "pi", ["forge-1-prd"], ["forge-researcher", "forge-verifier"]);
    await seedConfigDir(sb, "pi", "global");

    const r = await runCli2(["install", "-a", "pi", "-g", "--source", sb.source], sb);
    assert.equal(r.exitCode, EXIT.SUCCESS);
    // primary bundle under the global pi skills dir
    assert.ok(await exists(join(sb.home, ".pi/agent/skills/feature-forge/skills/forge-1-prd/SKILL.md")));
    // mirror (flat) under ~/.pi/agent/agents
    assert.ok(await exists(join(sb.home, ".pi/agent/agents/forge-researcher.md")));
    assert.ok(await exists(join(sb.home, ".pi/agent/agents/forge-verifier.md")));

    // manifest records the mirror at the global second root
    const mf = JSON.parse(await readFile(join(sb.home, ".pi/agent/skills/.feature-forge.global.json"), "utf8"));
    assert.equal(mf.placements.length, 1);
    assert.equal(mf.placements[0].kind, "mirror");
    assert.equal(mf.placements[0].destination, join(sb.home, ".pi/agent/agents"));

    await runCli2(["uninstall", "-a", "pi", "-g", "--source", sb.source], sb);
    assert.equal(await exists(join(sb.home, ".pi/agent/agents/forge-researcher.md")), false);
    assert.equal(await exists(join(sb.home, ".pi/agent/agents/forge-verifier.md")), false);
  });
});

test("pi project install mirrors agents/*.md into .pi/agents (not .pi/agent/agents)", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "pi", ["forge-1-prd"], ["forge-researcher"]);
    await seedConfigDir(sb, "pi", "project");

    const r = await runCli2(["install", "-a", "pi", "--source", sb.source], sb);
    assert.equal(r.exitCode, EXIT.SUCCESS);
    // project scope scans <root>/.pi/agents — NOT the global .pi/agent/agents subtree
    assert.ok(await exists(join(sb.cwd, ".pi/agents/forge-researcher.md")));
    assert.equal(await exists(join(sb.cwd, ".pi/agent/agents/forge-researcher.md")), false);

    const mf = JSON.parse(await readFile(join(sb.cwd, ".pi/skills/.feature-forge.project.json"), "utf8"));
    assert.equal(mf.placements[0].destination, join(sb.cwd, ".pi/agents"));
  });
});

test("explicit -a copilot targets a generic .github project without auto-detecting it", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "copilot", ["forge-1-prd"], ["forge-verifier"]);
    await mkdir(join(sb.cwd, ".github"), { recursive: true });

    const r = await runCli2(["install", "-a", "copilot", "--source", sb.source], sb);
    assert.equal(r.exitCode, EXIT.SUCCESS);
    assert.equal(r.agents[0]!.detected, false);
    assert.ok(await exists(join(sb.cwd, ".github/skills/forge-1-prd/SKILL.md")));
    assert.ok(await exists(join(sb.cwd, ".github/agents/forge-verifier.agent.md")));
  });
});

test("copilot project install mirrors recursive skills and flat agents with complete ownership", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(
      sb,
      "copilot",
      ["forge-1-prd", "forge-2-tech"],
      ["forge-researcher", "forge-verifier"],
    );
    await seedConfigDir(sb, "copilot");
    await mkdir(join(sb.source, "copilot/skills/forge-1-prd/references"), { recursive: true });
    await writeFile(
      join(sb.source, "copilot/skills/forge-1-prd/references/example.md"),
      "nested skill resource\n",
    );

    const r = await runCli2(["install", "-a", "copilot", "--source", sb.source], sb);
    assert.equal(r.exitCode, EXIT.SUCCESS);
    for (const skill of ["forge-1-prd", "forge-2-tech"]) {
      assert.ok(await exists(join(sb.cwd, ".github/skills", skill, "SKILL.md")));
    }
    for (const agent of ["forge-researcher", "forge-verifier"]) {
      assert.ok(await exists(join(sb.cwd, ".github/agents", `${agent}.agent.md`)));
    }

    const mf = JSON.parse(await readFile(join(sb.cwd, ".github/.feature-forge.project.json"), "utf8"));
    const skills = mf.placements.find((p: { destination: string }) =>
      p.destination === join(sb.cwd, ".github/skills"));
    const agents = mf.placements.find((p: { destination: string }) =>
      p.destination === join(sb.cwd, ".github/agents"));
    assert.deepEqual(
      skills.files.map((f: { path: string }) => f.path),
      [
        "forge-1-prd/SKILL.md",
        "forge-1-prd/references/example.md",
        "forge-2-tech/SKILL.md",
      ],
    );
    assert.deepEqual(
      agents.files.map((f: { path: string }) => f.path),
      ["forge-researcher.agent.md", "forge-verifier.agent.md"],
    );
    assert.ok([...skills.files, ...agents.files].every((f: { sha256?: string }) =>
      typeof f.sha256 === "string"));
  });
});

test("copilot update removes recursive mirror orphans and prunes only their empty directories", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "copilot", ["forge-1-prd", "forge-2-tech"]);
    await seedConfigDir(sb, "copilot");
    await runCli2(["install", "-a", "copilot", "--source", sb.source], sb);
    const userSkill = join(sb.cwd, ".github/skills/my-skill/SKILL.md");
    await mkdir(join(sb.cwd, ".github/skills/my-skill"), { recursive: true });
    await writeFile(userSkill, "user skill\n");

    await rm(join(sb.source, "copilot/skills/forge-2-tech"), { recursive: true, force: true });
    const updated = await runCli2(["update", "-a", "copilot", "--source", sb.source], sb);
    assert.equal(updated.exitCode, EXIT.SUCCESS);
    const skillMirror = updated.agents[0]!.placements!.find((p) =>
      p.destination === join(sb.cwd, ".github/skills"))!;
    assert.ok(skillMirror.files.some((f) =>
      f.relpath === "forge-2-tech/SKILL.md" && f.action === "remove"));
    assert.equal(await exists(join(sb.cwd, ".github/skills/forge-2-tech")), false);
    assert.ok(await exists(join(sb.cwd, ".github/skills/forge-1-prd/SKILL.md")));
    assert.ok(await exists(userSkill));
  });
});

test("copilot global native mirrors use ~/.copilot while the complete-root migration remains deferred", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "copilot", ["forge-1-prd"], ["forge-verifier"]);
    await seedConfigDir(sb, "copilot", "global");

    const r = await runCli2(["install", "-a", "copilot", "-g", "--source", sb.source], sb);
    assert.equal(r.exitCode, EXIT.SUCCESS);
    assert.ok(await exists(join(sb.home, ".copilot/skills/forge-1-prd/SKILL.md")));
    assert.ok(await exists(join(sb.home, ".copilot/agents/forge-verifier.agent.md")));
    // FORGE-105 owns moving/proving the complete personal runtime root.
    assert.ok(await exists(join(sb.home, ".github/feature-forge/.feature-forge-bundle.json")));
  });
});

test("copilot dry-run reports exact placement actions, writes nothing, and matches the real run", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "copilot", ["forge-1-prd"], ["forge-verifier"]);
    await seedConfigDir(sb, "copilot");

    const dry = await runCli2(
      ["install", "-a", "copilot", "--dry-run", "--json", "--source", sb.source],
      sb,
    );
    const dryAgent = dry.agents[0]!;
    assert.ok(dryAgent.placements && dryAgent.placements.length === 3);
    assert.equal(await exists(join(sb.cwd, ".github/skills/forge-1-prd/SKILL.md")), false);
    assert.equal(await exists(join(sb.cwd, ".github/agents/forge-verifier.agent.md")), false);
    assert.equal(await exists(join(sb.cwd, ".github/.feature-forge.project.json")), false);

    const real = await runCli2(["install", "-a", "copilot", "--source", sb.source], sb);
    const realAgent = real.agents[0]!;
    const actionShape = (placements: NonNullable<typeof dryAgent.placements>) =>
      placements.map((p) => ({
        kind: p.kind,
        destination: p.destination,
        files: p.files.map((f) => ({ relpath: f.relpath, action: f.action })),
      }));
    assert.deepEqual(actionShape(realAgent.placements!), actionShape(dryAgent.placements));
  });
});

test("copilot primary symlink keeps native mirrors as owned regular files and uninstalls exactly", { skip: isWindows() }, async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "copilot", ["forge-1-prd"], ["forge-verifier"]);
    await seedConfigDir(sb, "copilot");
    const userSkill = join(sb.cwd, ".github/skills/my-skill/SKILL.md");
    const userAgent = join(sb.cwd, ".github/agents/my-agent.agent.md");
    await mkdir(join(sb.cwd, ".github/skills/my-skill"), { recursive: true });
    await mkdir(join(sb.cwd, ".github/agents"), { recursive: true });
    await writeFile(userSkill, "user skill\n");
    await writeFile(userAgent, "user agent\n");

    const r = await runCli2(
      ["install", "-a", "copilot", "--symlink", "--source", sb.source],
      sb,
    );
    assert.equal(r.exitCode, EXIT.SUCCESS);
    assert.ok((await lstat(join(sb.cwd, ".github/feature-forge"))).isSymbolicLink());
    assert.ok((await lstat(join(sb.cwd, ".github/skills/forge-1-prd/SKILL.md"))).isFile());
    assert.ok((await lstat(join(sb.cwd, ".github/agents/forge-verifier.agent.md"))).isFile());

    await runCli2(["uninstall", "-a", "copilot", "--source", sb.source], sb);
    assert.equal(await exists(join(sb.cwd, ".github/feature-forge")), false);
    assert.equal(await exists(join(sb.cwd, ".github/skills/forge-1-prd/SKILL.md")), false);
    assert.equal(await exists(join(sb.cwd, ".github/skills/forge-1-prd")), false);
    assert.equal(await exists(join(sb.cwd, ".github/agents/forge-verifier.agent.md")), false);
    assert.ok(await exists(userSkill));
    assert.ok(await exists(userAgent));
    assert.ok(await exists(join(sb.source, "copilot/skills/forge-1-prd/SKILL.md")));
  });
});

test("copilot --symlink under Windows falls back to copied primary and native mirror files", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "copilot", ["forge-1-prd"], ["forge-verifier"]);
    await seedConfigDir(sb, "copilot");

    const r = await runCli2(
      ["install", "-a", "copilot", "--symlink", "--source", sb.source],
      sb,
      { platform: "win32" },
    );
    assert.equal(r.exitCode, EXIT.SUCCESS);
    assert.ok((await lstat(join(sb.cwd, ".github/feature-forge"))).isDirectory());
    assert.ok((await lstat(join(sb.cwd, ".github/skills/forge-1-prd/SKILL.md"))).isFile());
    assert.ok((await lstat(join(sb.cwd, ".github/agents/forge-verifier.agent.md"))).isFile());
    const mf = JSON.parse(await readFile(join(sb.cwd, ".github/.feature-forge.project.json"), "utf8"));
    assert.equal(mf.mode, "copy");
    assert.ok(mf.placements.filter((p: { kind: string }) => p.kind === "mirror")
      .flatMap((p: { files: Array<{ sha256?: string }> }) => p.files)
      .every((f: { sha256?: string }) => typeof f.sha256 === "string"));
  });
});

test("copilot does not claim or uninstall byte-identical pre-existing native mirror files", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "copilot", ["forge-1-prd"], ["forge-verifier"]);
    await seedConfigDir(sb, "copilot");
    const skill = join(sb.cwd, ".github/skills/forge-1-prd/SKILL.md");
    const agent = join(sb.cwd, ".github/agents/forge-verifier.agent.md");
    await mkdir(join(sb.cwd, ".github/skills/forge-1-prd"), { recursive: true });
    await mkdir(join(sb.cwd, ".github/agents"), { recursive: true });
    await writeFile(skill, await readFile(join(sb.source, "copilot/skills/forge-1-prd/SKILL.md")));
    await writeFile(agent, await readFile(join(sb.source, "copilot/agents/forge-verifier.agent.md")));

    const r = await runCli2(["install", "-a", "copilot", "--source", sb.source], sb);
    assert.equal(r.exitCode, EXIT.SUCCESS);
    const mirrors = r.agents[0]!.placements!.filter((p) => p.kind === "mirror");
    assert.ok(mirrors.every((p) => p.files.every((f) => f.action === "unchanged")));
    const mf = JSON.parse(await readFile(join(sb.cwd, ".github/.feature-forge.project.json"), "utf8"));
    assert.ok(mf.placements.filter((p: { kind: string }) => p.kind === "mirror")
      .every((p: { files: unknown[] }) => p.files.length === 0));

    await runCli2(["uninstall", "-a", "copilot", "--source", sb.source], sb);
    assert.ok(await exists(skill));
    assert.ok(await exists(agent));
  });
});

test("copilot does not claim or uninstall modified pre-existing native mirror files", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "copilot", ["forge-1-prd"], ["forge-verifier"]);
    await seedConfigDir(sb, "copilot");
    const skill = join(sb.cwd, ".github/skills/forge-1-prd/SKILL.md");
    const agent = join(sb.cwd, ".github/agents/forge-verifier.agent.md");
    await mkdir(join(sb.cwd, ".github/skills/forge-1-prd"), { recursive: true });
    await mkdir(join(sb.cwd, ".github/agents"), { recursive: true });
    await writeFile(skill, "user-owned differing skill\n");
    await writeFile(agent, "user-owned differing agent\n");

    const r = await runCli2(["install", "-a", "copilot", "--source", sb.source], sb);
    assert.equal(r.exitCode, EXIT.SUCCESS);
    const mirrors = r.agents[0]!.placements!.filter((p) => p.kind === "mirror");
    assert.ok(mirrors.every((p) => p.files.every((f) => f.action === "skip-modified")));

    const mf = JSON.parse(await readFile(join(sb.cwd, ".github/.feature-forge.project.json"), "utf8"));
    assert.ok(mf.placements.filter((p: { kind: string }) => p.kind === "mirror")
      .every((p: { files: unknown[] }) => p.files.length === 0));

    await runCli2(["uninstall", "-a", "copilot", "--source", sb.source], sb);
    assert.equal(await readFile(skill, "utf8"), "user-owned differing skill\n");
    assert.equal(await readFile(agent, "utf8"), "user-owned differing agent\n");
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
    const block = mf.placements.find((p: { kind: string }) => p.kind === "managed-block");
    assert.equal(block.files[0].path, "copilot-instructions.md");
    assert.ok(typeof block.files[0].sha256 === "string");
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

test("copilot install rejects a recursive mirror symlink ancestor before writing outside", { skip: isWindows() }, async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "copilot", ["forge-1-prd"]);
    await seedConfigDir(sb, "copilot");
    const outside = join(dirname(sb.cwd), "outside-install");
    await mkdir(outside, { recursive: true });
    await mkdir(join(sb.cwd, ".github/skills"), { recursive: true });
    await symlink(outside, join(sb.cwd, ".github/skills/forge-1-prd"), "dir");

    const result = await runCli2(["install", "-a", "copilot", "--source", sb.source], sb);
    assert.equal(result.exitCode, EXIT.FAILURE);
    assert.equal(result.agents[0]!.error?.code, "PATH_ESCAPE");
    assert.equal(await exists(join(outside, "SKILL.md")), false);
    assert.equal(await exists(join(sb.cwd, ".github/.feature-forge.project.json")), false);
  });
});

test("copilot update rejects a recursive mirror symlink ancestor before outside overwrite", { skip: isWindows() }, async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "copilot", ["forge-1-prd"]);
    await seedConfigDir(sb, "copilot");
    await runCli2(["install", "-a", "copilot", "--source", sb.source], sb);
    const skillDir = join(sb.cwd, ".github/skills/forge-1-prd");
    const outside = join(dirname(sb.cwd), "outside-update");
    await rm(skillDir, { recursive: true, force: true });
    await mkdir(outside, { recursive: true });
    await writeFile(join(outside, "SKILL.md"), "outside bytes\n");
    await symlink(outside, skillDir, "dir");
    await writeFile(
      join(sb.source, "copilot/skills/forge-1-prd/SKILL.md"),
      "changed source bytes\n",
    );

    const result = await runCli2(["update", "-a", "copilot", "--source", sb.source], sb);
    assert.equal(result.exitCode, EXIT.FAILURE);
    assert.equal(result.agents[0]!.error?.code, "PATH_ESCAPE");
    assert.equal(await readFile(join(outside, "SKILL.md"), "utf8"), "outside bytes\n");
  });
});

test("copilot uninstall rejects a recursive mirror symlink ancestor before outside removal", { skip: isWindows() }, async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "copilot", ["forge-1-prd"]);
    await seedConfigDir(sb, "copilot");
    await runCli2(["install", "-a", "copilot", "--source", sb.source], sb);
    const skillDir = join(sb.cwd, ".github/skills/forge-1-prd");
    const outside = join(dirname(sb.cwd), "outside-uninstall");
    await rm(skillDir, { recursive: true, force: true });
    await mkdir(outside, { recursive: true });
    await writeFile(join(outside, "SKILL.md"), "must survive\n");
    await symlink(outside, skillDir, "dir");

    const result = await runCli2(["uninstall", "-a", "copilot", "--source", sb.source], sb);
    assert.equal(result.exitCode, EXIT.FAILURE);
    assert.equal(result.agents[0]!.error?.code, "PATH_ESCAPE");
    assert.equal(await readFile(join(outside, "SKILL.md"), "utf8"), "must survive\n");
    assert.ok(await exists(join(sb.cwd, ".github/.feature-forge.project.json")));
  });
});

test("uninstall rejects a manifest-forged placement root before mutating owned files", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "copilot", ["forge-1-prd"]);
    await seedConfigDir(sb, "copilot");
    await runCli2(["install", "-a", "copilot", "--source", sb.source], sb);

    const mfPath = join(sb.cwd, ".github/.feature-forge.project.json");
    const mf = JSON.parse(await readFile(mfPath, "utf8"));
    const skillPlacement = mf.placements.find((p: { destination: string }) =>
      p.destination === join(sb.cwd, ".github/skills"));
    skillPlacement.root = sb.cwd;
    skillPlacement.destination = join(sb.cwd, "forged");
    skillPlacement.files = [{ path: "victim.txt", sha256: "x" }];
    await mkdir(join(sb.cwd, "forged"), { recursive: true });
    await writeFile(join(sb.cwd, "forged/victim.txt"), "must survive\n");
    await writeFile(mfPath, JSON.stringify(mf, null, 2));

    const result = await runCli2(["uninstall", "-a", "copilot", "--source", sb.source], sb);
    assert.equal(result.exitCode, EXIT.FAILURE);
    assert.equal(result.agents[0]!.error?.code, "MANIFEST_CORRUPT");
    assert.ok(await exists(join(sb.cwd, "forged/victim.txt")));
    assert.ok(await exists(join(sb.cwd, ".github/skills/forge-1-prd/SKILL.md")));
    assert.ok(await exists(mfPath));
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

test("manifest v1 update records new mirror writes without claiming equal unowned files", async () => {
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

    // Update reads v1 and writes v2. The newly-created verifier is owned; the equal pre-existing
    // researcher has no placement record, so byte equality alone must not manufacture ownership.
    const upd = await runCli2(["update", "-a", "codex", "--source", sb.source], sb);
    assert.equal(upd.exitCode, EXIT.SUCCESS);
    const mf2 = JSON.parse(await readFile(mfPath, "utf8"));
    assert.equal(mf2.schemaVersion, 2);
    assert.equal(mf2.placements[0].kind, "mirror");
    assert.deepEqual(
      mf2.placements[0].files.map((f: { path: string }) => f.path),
      ["forge-verifier.toml"],
    );
    await runCli2(["uninstall", "-a", "codex", "--source", sb.source], sb);
    assert.ok(await exists(join(sb.cwd, ".codex/agents/forge-researcher.toml")));
    assert.equal(await exists(join(sb.cwd, ".codex/agents/forge-verifier.toml")), false);
  });
});
