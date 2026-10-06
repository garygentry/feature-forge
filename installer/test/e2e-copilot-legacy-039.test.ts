/**
 * Upgrading a real installer-0.3.9 Copilot layout (see helpers/legacy-039.ts) to the native layout,
 * hermetic via `withSandbox`: project and personal scopes, copy and symlink modes. Covers list/
 * uninstall of a stranded `~/.github` personal install, dry-run parity, migration with user
 * instructions preserved, repeat no-op, exact uninstall, a purged npx-cache link target, an
 * interrupted migration's retry, and that no update ever writes or removes through the old link.
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { chmod, lstat, mkdir, readFile, readlink, rm, stat, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { EXIT } from "../dist/types.js";
import { isWindows } from "../dist/fsutil.js";
import { withSandbox, seedConfigDir, type Sandbox } from "./helpers/sandbox.ts";
import { makeFixtureBundle } from "./helpers/fixtures.ts";
import { runCli2 } from "./helpers/run.ts";
import { seed039Copilot, snapshotTree } from "./helpers/legacy-039.ts";

const exists = (p: string) => lstat(p).then(() => true, () => false);
const SKILLS = ["forge", "forge-1-prd"];
const AGENTS = ["forge-verifier"];

type Scope = "project" | "global";
type Mode = "copy" | "symlink";
const CASES: Array<[Scope, Mode]> = [["project", "copy"], ["project", "symlink"], ["global", "copy"], ["global", "symlink"]];

const scopeFlag = (scope: Scope) => (scope === "global" ? ["-g"] : []);
const nativeRoot = (sb: Sandbox, scope: Scope) => (scope === "global" ? join(sb.home, ".copilot") : join(sb.cwd, ".github"));

async function setup(sb: Sandbox, scope: Scope, mode: Mode) {
  await makeFixtureBundle(sb, "copilot", SKILLS, AGENTS);
  await seedConfigDir(sb, "copilot", scope);
  return seed039Copilot(sb, scope, mode, SKILLS, AGENTS);
}

/** Everything left under both scope roots except the config dir seed. */
async function leftovers(sb: Sandbox): Promise<string[]> {
  return [
    ...(await snapshotTree(sb.home)).map((l) => `~/${l.split(" ")[0]}`),
    ...(await snapshotTree(sb.cwd)).map((l) => `./${l.split(" ")[0]}`),
  ];
}

for (const [scope, mode] of CASES) {
  const symlinkCase = mode === "symlink";
  test(`0.3.9 ${scope} ${mode}: list flags it, update migrates, repeat is a no-op, uninstall is exact`, { skip: symlinkCase && isWindows() }, async () => {
    await withSandbox(async (sb) => {
      const old = await setup(sb, scope, mode);
      const bundleBefore = await snapshotTree(old.bundle);
      const args = ["-a", "copilot", ...scopeFlag(scope), "--source", sb.source];

      const listed = await runCli2(["list", ...args], sb);
      const rows = listed.agents[0]!.actions.map((a) => a.relpath);
      assert.ok(rows.includes("installed:true"), rows.join(" "));
      assert.ok(rows.includes("legacy-layout:true(run update)"), rows.join(" "));

      const before = [...await snapshotTree(sb.home), ...await snapshotTree(sb.cwd)];
      const dry = await runCli2(["update", "--dry-run", ...args], sb);
      assert.equal(dry.exitCode, EXIT.SUCCESS);
      assert.deepEqual([...await snapshotTree(sb.home), ...await snapshotTree(sb.cwd)], before, "dry-run writes nothing");

      const real = await runCli2(["update", ...args], sb);
      assert.equal(real.exitCode, EXIT.SUCCESS, JSON.stringify(real.agents[0]!.error));
      assert.deepEqual(real.agents[0]!.actions, dry.agents[0]!.actions);
      assert.deepEqual(real.agents[0]!.placements, dry.agents[0]!.placements);

      const root = nativeRoot(sb, scope);
      const runtime = join(root, "feature-forge");
      assert.ok(!(await lstat(runtime)).isSymbolicLink(), "default update migrates to a copied runtime");
      assert.ok(await exists(join(runtime, "skills/forge/SKILL.md")));
      assert.equal(await exists(join(runtime, "skills/forge/forge.md")), false, "0.3.9 <name>.md leaves are gone");
      assert.ok(await exists(join(root, "skills/forge-1-prd/SKILL.md")));
      assert.ok(await exists(join(root, "agents/forge-verifier.agent.md")));
      if (scope === "global") {
        assert.equal(await exists(old.runtime), false, "old ~/.github runtime removed");
        assert.equal(await exists(old.manifestPath), false, "old ~/.github manifest removed");
      }
      assert.equal(await readFile(old.instructions, "utf8"), `${old.userPrefix}\n${old.userSuffix}`, "only the installer region is removed");
      assert.deepEqual(await snapshotTree(old.bundle), bundleBefore, "the old link target is never written");

      const manifest = join(root, `.feature-forge.${scope}.json`);
      const mtime = (await stat(manifest)).mtimeMs;
      const again = await runCli2(["update", ...args], sb);
      assert.ok(again.agents[0]!.actions.every((f) => f.action === "unchanged"));
      assert.ok(again.agents[0]!.placements!.every((p) => p.files.every((f) => f.action === "unchanged")));
      assert.equal((await stat(manifest)).mtimeMs, mtime, "repeated update leaves the manifest untouched");
      const relisted = (await runCli2(["list", ...args], sb)).agents[0]!.actions.map((a) => a.relpath);
      assert.ok(relisted.includes("up-to-date:true") && !relisted.some((r) => r.startsWith("legacy-layout")), relisted.join(" "));

      const removed = await runCli2(["uninstall", ...args], sb);
      assert.equal(removed.exitCode, EXIT.SUCCESS);
      const base = scope === "global" ? "~" : ".";
      assert.deepEqual(await leftovers(sb), [`${base}/.github/copilot-instructions.md`]);
      assert.deepEqual(await snapshotTree(old.bundle), bundleBefore);
    });
  });

  test(`0.3.9 ${scope} ${mode}: uninstall without updating removes it exactly`, { skip: symlinkCase && isWindows() }, async () => {
    await withSandbox(async (sb) => {
      const old = await setup(sb, scope, mode);
      const bundleBefore = await snapshotTree(old.bundle);
      await mkdir(join(old.githubDir, "workflows"), { recursive: true });
      await writeFile(join(old.githubDir, "workflows/ci.yml"), "name: ci\n");
      const removed = await runCli2(["uninstall", "-a", "copilot", ...scopeFlag(scope)], sb);
      assert.equal(removed.exitCode, EXIT.SUCCESS);
      const base = scope === "global" ? "~" : ".";
      assert.deepEqual((await leftovers(sb)).sort(), [`${base}/.github/copilot-instructions.md`, `${base}/.github/workflows/ci.yml`]);
      assert.equal(await readFile(old.instructions, "utf8"), `${old.userPrefix}\n${old.userSuffix}`);
      assert.deepEqual(await snapshotTree(old.bundle), bundleBefore);
      const listed = await runCli2(["list", "-a", "copilot", ...scopeFlag(scope)], sb);
      assert.ok(listed.agents[0]!.actions.some((a) => a.relpath === "installed:false"));
    });
  });
}

for (const scope of ["project", "global"] as const) {
  test(`0.3.9 ${scope} symlink whose npx cache was purged still migrates and uninstalls`, { skip: isWindows() }, async () => {
    await withSandbox(async (sb) => {
      const old = await setup(sb, scope, "symlink");
      await rm(old.bundle, { recursive: true, force: true });
      const args = ["-a", "copilot", ...scopeFlag(scope), "--source", sb.source];
      const migrated = await runCli2(["update", ...args], sb);
      assert.equal(migrated.exitCode, EXIT.SUCCESS, JSON.stringify(migrated.agents[0]!.error));
      assert.ok(await exists(join(nativeRoot(sb, scope), "feature-forge/skills/forge/SKILL.md")));
      assert.equal((await runCli2(["uninstall", ...args], sb)).exitCode, EXIT.SUCCESS);
      const base = scope === "global" ? "~" : ".";
      assert.deepEqual(await leftovers(sb), [`${base}/.github/copilot-instructions.md`]);
    });
  });

  test(`0.3.9 ${scope} migration that cannot journal its intent fails before any write`, { skip: isWindows() || process.getuid?.() === 0 }, async () => {
    await withSandbox(async (sb) => {
      await setup(sb, scope, "copy");
      const root = nativeRoot(sb, scope);
      await mkdir(root, { recursive: true });
      const before = [...await snapshotTree(sb.home), ...await snapshotTree(sb.cwd)];
      await chmod(root, 0o555);
      let failed;
      try {
        failed = await runCli2(["update", "-a", "copilot", ...scopeFlag(scope), "--source", sb.source], sb);
      } finally {
        await chmod(root, 0o755);
      }
      assert.equal(failed.exitCode, EXIT.FAILURE);
      assert.deepEqual([...await snapshotTree(sb.home), ...await snapshotTree(sb.cwd)], before);
    });
  });

  test(`0.3.9 ${scope} migration interrupted at the final manifest write is owned in full by the retry`, async () => {
    await withSandbox(async (sb) => {
      await setup(sb, scope, "copy");
      const root = nativeRoot(sb, scope);
      const args = ["-a", "copilot", ...scopeFlag(scope), "--source", sb.source];
      const failed = await runCli2(["update", ...args], sb, {
        writeManifestSeam: () => ({ ok: false, error: { code: "WRITE_DENIED", message: "interrupted" } }),
      });
      assert.equal(failed.exitCode, EXIT.FAILURE);
      assert.ok(await exists(join(root, "skills/forge/SKILL.md")), "the new layout was applied before the manifest");

      const retry = await runCli2(["update", ...args], sb);
      assert.equal(retry.exitCode, EXIT.SUCCESS, JSON.stringify(retry.agents[0]!.error));
      const manifest = join(root, `.feature-forge.${scope}.json`);
      const mf = JSON.parse(await readFile(manifest, "utf8"));
      const recorded = mf.placements.filter((p: { kind: string }) => p.kind === "mirror")
        .flatMap((p: { files: { path: string }[] }) => p.files.map((f) => f.path));
      assert.ok(recorded.includes("forge/SKILL.md") && recorded.includes("forge-verifier.agent.md"), recorded.join(","));
      assert.ok(mf.files.some((f: { path: string }) => f.path === "skills/forge/SKILL.md"));
      assert.equal(await exists(`${manifest}.migrating`), false, "journal removed once the manifest commits");
      const again = await runCli2(["update", ...args], sb);
      assert.ok(again.agents[0]!.placements!.every((p) => p.files.every((f) => f.action === "unchanged")));

      assert.equal((await runCli2(["uninstall", ...args], sb)).exitCode, EXIT.SUCCESS);
      const base = scope === "global" ? "~" : ".";
      assert.deepEqual(await leftovers(sb), [`${base}/.github/copilot-instructions.md`]);
    });
  });

  test(`0.3.9 ${scope} migration never claims a byte-identical file the user already placed`, async () => {
    await withSandbox(async (sb) => {
      await setup(sb, scope, "copy");
      const root = nativeRoot(sb, scope);
      const committed = join(root, "skills/forge/SKILL.md");
      await mkdir(join(root, "skills/forge"), { recursive: true });
      await writeFile(committed, await readFile(join(sb.source, "copilot/skills/forge/SKILL.md")));
      const args = ["-a", "copilot", ...scopeFlag(scope), "--source", sb.source];
      assert.equal((await runCli2(["update", ...args], sb)).exitCode, EXIT.SUCCESS);
      assert.equal((await runCli2(["uninstall", ...args], sb)).exitCode, EXIT.SUCCESS);
      assert.ok(await exists(committed), "a pre-existing equal file is not ours to delete");
    });
  });
}

test("0.3.9 project copy: --symlink migration refuses before writing; --force replaces it", { skip: isWindows() }, async () => {
  await withSandbox(async (sb) => {
    const old = await setup(sb, "project", "copy");
    const before = await snapshotTree(sb.cwd);
    const args = ["-a", "copilot", "--symlink", "--source", sb.source];
    const refused = await runCli2(["update", ...args], sb);
    assert.equal(refused.exitCode, EXIT.FAILURE);
    assert.match(refused.agents[0]!.error!.remedy ?? "", /without --symlink|--force/);
    assert.deepEqual(await snapshotTree(sb.cwd), before, "nothing written");

    const forced = await runCli2(["update", "--force", ...args], sb);
    assert.equal(forced.exitCode, EXIT.SUCCESS, JSON.stringify(forced.agents[0]!.error));
    assert.equal(await readlink(old.runtime), join(sb.source, "copilot"));
    assert.equal(await readFile(old.instructions, "utf8"), `${old.userPrefix}\n${old.userSuffix}`);
  });
});

test("0.3.9 edited block is kept, listed as retired, and stripped only by --force", async () => {
  await withSandbox(async (sb) => {
    const old = await setup(sb, "global", "copy");
    const text = await readFile(old.instructions, "utf8");
    await writeFile(old.instructions, text.replace("consult those files", "ALWAYS consult those files"));
    const args = ["-a", "copilot", "-g", "--source", sb.source];
    assert.equal((await runCli2(["update", ...args], sb)).exitCode, EXIT.SUCCESS);
    assert.match(await readFile(old.instructions, "utf8"), /ALWAYS consult/);
    const rows = (await runCli2(["list", ...args], sb)).agents[0]!.actions.map((a) => a.relpath);
    assert.ok(rows.includes("retired-block:edited(update --force strips it)"), rows.join(" "));
    assert.equal((await runCli2(["update", "--force", ...args], sb)).exitCode, EXIT.SUCCESS);
    assert.equal(await readFile(old.instructions, "utf8"), `${old.userPrefix}\n${old.userSuffix}`);
  });
});

test("a forged legacy personal manifest is rejected before any removal", async () => {
  await withSandbox(async (sb) => {
    const old = await setup(sb, "global", "copy");
    const victim = join(sb.home, "precious");
    await mkdir(victim, { recursive: true });
    await writeFile(join(victim, "keep.txt"), "keep\n");
    const mf = JSON.parse(await readFile(old.manifestPath, "utf8"));
    mf.destination = victim;
    mf.files = [{ path: "keep.txt" }];
    await writeFile(old.manifestPath, JSON.stringify(mf));
    for (const sub of ["uninstall", "update", "list"]) {
      const r = await runCli2([sub, "-a", "copilot", "-g", "--source", sb.source], sb);
      assert.equal(r.exitCode, EXIT.FAILURE, sub);
      assert.equal(r.agents[0]!.error?.code, "MANIFEST_CORRUPT", sub);
    }
    assert.ok(await exists(join(victim, "keep.txt")));
    assert.ok(await exists(old.runtime));
  });
});

test("update without --symlink over a symlink install never writes into the old link target", { skip: isWindows() }, async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "claude", ["forge-1-prd"]);
    await seedConfigDir(sb, "claude", "project");
    const first = join(sb.home, "old-cache");
    await runCli2(["install", "-a", "claude", "--symlink", "--source", sb.source], sb);
    // Move the linked source aside (a new npx cache dir per version) and relink to it, as 0.3.9 left it.
    const { rename, symlink } = await import("node:fs/promises");
    await mkdir(sb.home, { recursive: true });
    await rename(join(sb.source, "claude"), first);
    const dest = join(sb.cwd, ".claude/skills/feature-forge");
    await rm(dest);
    await symlink(first, dest, "dir");
    const mfPath = join(sb.cwd, ".claude/skills/.feature-forge.project.json");
    const mf = JSON.parse(await readFile(mfPath, "utf8"));
    mf.link = { target: first };
    await writeFile(mfPath, JSON.stringify(mf));
    await makeFixtureBundle(sb, "claude", ["forge-1-prd", "forge-2-tech"]);
    const firstBefore = await snapshotTree(first);

    const updated = await runCli2(["update", "-a", "claude", "--source", sb.source], sb);
    assert.equal(updated.exitCode, EXIT.SUCCESS, JSON.stringify(updated.agents[0]!.error));
    assert.ok(!(await lstat(dest)).isSymbolicLink());
    assert.ok(await exists(join(dest, "skills/forge-2-tech/SKILL.md")));
    assert.deepEqual(await snapshotTree(first), firstBefore, "old target untouched by update");
    assert.equal((await runCli2(["uninstall", "-a", "claude"], sb)).exitCode, EXIT.SUCCESS);
    assert.deepEqual(await snapshotTree(first), firstBefore, "old target untouched by uninstall");
  });
});

test("update --symlink relinks a link that still points at its recorded target", { skip: isWindows() }, async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "claude", ["forge-1-prd"]);
    await seedConfigDir(sb, "claude", "project");
    const dest = join(sb.cwd, ".claude/skills/feature-forge");
    const mfPath = join(sb.cwd, ".claude/skills/.feature-forge.project.json");
    await runCli2(["install", "-a", "claude", "--symlink", "--source", sb.source], sb);
    const mf = JSON.parse(await readFile(mfPath, "utf8"));
    const elsewhere = join(sb.home, "old-cache");
    const { rename, symlink } = await import("node:fs/promises");
    await mkdir(sb.home, { recursive: true });
    await rename(join(sb.source, "claude"), elsewhere);
    await makeFixtureBundle(sb, "claude", ["forge-1-prd"]);
    await rm(dest);
    await symlink(elsewhere, dest, "dir");
    mf.link = { target: elsewhere };
    await writeFile(mfPath, JSON.stringify(mf));

    const r = await runCli2(["update", "-a", "claude", "--symlink", "--source", sb.source], sb);
    assert.equal(r.exitCode, EXIT.SUCCESS);
    assert.deepEqual(r.agents[0]!.actions, [{ relpath: ".", action: "overwrite" }]);
    assert.equal(await readlink(dest), join(sb.source, "claude"));

    // A link the user re-pointed elsewhere is still theirs: skip-modified, untouched.
    const theirs = join(sb.home, "theirs");
    await mkdir(theirs, { recursive: true });
    await rm(dest);
    await symlink(theirs, dest, "dir");
    const mf2 = JSON.parse(await readFile(mfPath, "utf8"));
    mf2.link = { target: elsewhere };
    await writeFile(mfPath, JSON.stringify(mf2));
    const kept = await runCli2(["update", "-a", "claude", "--symlink", "--source", sb.source], sb);
    assert.deepEqual(kept.agents[0]!.actions, [{ relpath: ".", action: "skip-modified" }]);
    assert.equal(await readlink(dest), theirs);
  });
});

test("update --symlink keeps a user directory that replaced a stale link instead of failing", { skip: isWindows() }, async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "claude", ["forge-1-prd"]);
    await seedConfigDir(sb, "claude", "project");
    await runCli2(["install", "-a", "claude", "--symlink", "--source", sb.source], sb);
    const dest = join(sb.cwd, ".claude/skills/feature-forge");
    const mfPath = join(sb.cwd, ".claude/skills/.feature-forge.project.json");
    const mf = JSON.parse(await readFile(mfPath, "utf8"));
    mf.link = { target: join(sb.home, "old-npx-cache") };
    await writeFile(mfPath, JSON.stringify(mf));
    await rm(dest);
    await mkdir(dest, { recursive: true });
    await writeFile(join(dest, "mine.md"), "mine\n");

    const r = await runCli2(["update", "-a", "claude", "--symlink", "--source", sb.source], sb);
    assert.equal(r.exitCode, EXIT.SUCCESS, JSON.stringify(r.agents[0]!.error));
    assert.deepEqual(r.agents[0]!.actions, [{ relpath: ".", action: "skip-modified" }]);
    assert.equal(await readFile(join(dest, "mine.md"), "utf8"), "mine\n");
  });
});

for (const scope of ["project", "global"] as const) {
  test(`0.3.9 ${scope} copy install with no .copilot dir: plain update finds it by its manifest and migrates it`, async () => {
    await withSandbox(async (sb) => {
      await makeFixtureBundle(sb, "copilot", SKILLS, AGENTS);
      const old = await seed039Copilot(sb, scope, "copy", SKILLS, AGENTS);
      const configDir = join(scope === "global" ? sb.home : sb.cwd, ".copilot");
      assert.equal(await exists(configDir), false);

      const listed = await runCli2(["list", ...scopeFlag(scope), "--source", sb.source], sb);
      const copilot = listed.agents.find((a) => a.agent === "copilot")!;
      assert.equal(copilot.detected, true, "a recorded install counts as detected");
      assert.ok(copilot.actions.some((a) => a.relpath === "legacy-layout:true(run update)"));

      const r = await runCli2(["update", ...scopeFlag(scope), "--source", sb.source], sb);
      assert.equal(r.exitCode, EXIT.SUCCESS, JSON.stringify(r.agents.map((a) => a.error)));
      assert.deepEqual(r.agents.map((a) => a.agent), ["copilot"]);
      const root = nativeRoot(sb, scope);
      assert.ok(await exists(join(root, "skills/forge/SKILL.md")));
      assert.ok(await exists(join(root, "agents/forge-verifier.agent.md")));
      assert.ok(await exists(join(root, `.feature-forge.${scope}.json`)));
      if (scope === "global") assert.equal(await exists(old.manifestPath), false);
      assert.equal(await readFile(old.instructions, "utf8"), `${old.userPrefix}\n${old.userSuffix}`);
    });
  });

  test(`${scope}: .github content without a manifest is never detection for plain update or list`, async () => {
    await withSandbox(async (sb) => {
      await makeFixtureBundle(sb, "copilot", SKILLS, AGENTS);
      const github = join(scope === "global" ? sb.home : sb.cwd, ".github");
      await mkdir(join(github, "feature-forge"), { recursive: true });
      await writeFile(join(github, "copilot-instructions.md"), "# mine\n");
      const before = await snapshotTree(github);

      const listed = await runCli2(["list", ...scopeFlag(scope), "--source", sb.source], sb);
      assert.equal(listed.agents.find((a) => a.agent === "copilot")!.detected, false);
      const r = await runCli2(["update", ...scopeFlag(scope), "--source", sb.source], sb);
      assert.deepEqual(r.agents, []);
      assert.deepEqual(await snapshotTree(github), before);
    });
  });
}

for (const scope of ["project", "global"] as const) {
  test(`0.3.9 ${scope} symlink install replaced by a user directory is left in place`, async () => {
    await withSandbox(async (sb) => {
      const old = await setup(sb, scope, "symlink");
      await rm(old.runtime);
      await mkdir(old.runtime, { recursive: true });
      await writeFile(join(old.runtime, "mine.md"), "mine\n");
      const args = ["-a", "copilot", ...scopeFlag(scope), "--source", sb.source];
      if (scope === "global") {
        assert.equal((await runCli2(["update", ...args], sb)).exitCode, EXIT.SUCCESS);
      } else {
        assert.equal((await runCli2(["uninstall", ...args], sb)).exitCode, EXIT.SUCCESS);
      }
      assert.equal(await readFile(join(old.runtime, "mine.md"), "utf8"), "mine\n");
    });
  });
}

test("plain uninstall -g removes a 0.3.9 personal install that has no ~/.copilot dir", async () => {
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "copilot", SKILLS, AGENTS);
    const old = await seed039Copilot(sb, "global", "copy", SKILLS, AGENTS);
    const r = await runCli2(["uninstall", "-g"], sb);
    assert.equal(r.exitCode, EXIT.SUCCESS);
    assert.deepEqual(r.agents.map((a) => a.agent), ["copilot"]);
    assert.deepEqual(await snapshotTree(old.runtime), [], "no runtime files remain");
    assert.equal(await exists(old.manifestPath), false);
    assert.deepEqual(await leftovers(sb), ["~/.github/copilot-instructions.md"]);
  });
});
