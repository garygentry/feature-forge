/**
 * End-to-end update + uninstall suite (spec 08 §5.4 reconcile add/change/remove + multi-skill
 * SCALE-02 + manifest-scoped orphan; §5.5 skip-modified + --force; §5.6 uninstall exactness +
 * idempotency). Each test is fully hermetic via `withSandbox` (temp HOME/cwd/source, mock
 * registry) — no real `~`, no network.
 *
 * Built artifacts import with `.js`; test helpers import with `.ts` (Node type-stripping rule).
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile, writeFile, mkdir, rm, access } from "node:fs/promises";
import { join } from "node:path";
import { EXIT } from "../dist/types.js";
import type { FileAction, InstallManifest } from "../dist/types.js";
import { withSandbox, seedConfigDir, type Sandbox } from "./helpers/sandbox.ts";
import { makeFixtureBundle } from "./helpers/fixtures.ts";
import { runCli2 } from "./helpers/run.ts";

// --- paths bound to the claude project install -----------------------------

/** The claude project install destination (namespace dir). */
const destDir = (sb: Sandbox): string => join(sb.cwd, ".claude", "skills", "feature-forge");
/** The claude project manifest sibling path. */
const manifestPath = (sb: Sandbox): string =>
  join(sb.cwd, ".claude", "skills", ".feature-forge.project.json");

/** Absolute path of a skill's SKILL.md in the source bundle. */
const srcSkill = (sb: Sandbox, id: string): string =>
  join(sb.source, "claude", "skills", id, "SKILL.md");

/** Read + parse the on-disk manifest. */
async function readManifest(sb: Sandbox): Promise<InstallManifest> {
  return JSON.parse(await readFile(manifestPath(sb), "utf8")) as InstallManifest;
}

/** True iff `p` exists on disk. */
async function exists(p: string): Promise<boolean> {
  try {
    await access(p);
    return true;
  } catch {
    return false;
  }
}

/** The single agent report's actions (claude). */
function actionsOf(report: { agents: { agent: string; actions: FileAction[] }[] }): FileAction[] {
  const a = report.agents.find((x) => x.agent === "claude");
  assert.ok(a, "expected a claude agent report");
  return a.actions;
}

/** Find the action for a destination relpath. */
function actionFor(actions: FileAction[], relpath: string): FileAction | undefined {
  return actions.find((a) => a.relpath === relpath);
}

/** Standard install argv for claude against the sandbox source. */
const installArgs = (sb: Sandbox): string[] => ["install", "-a", "claude", "--source", sb.source, "-y"];
const updateArgs = (sb: Sandbox, force = false): string[] => [
  "update",
  "-a",
  "claude",
  "--source",
  sb.source,
  ...(force ? ["--force"] : []),
  "-y",
];
const uninstallArgs = (sb: Sandbox): string[] => ["uninstall", "-a", "claude", "--source", sb.source, "-y"];

// ===========================================================================
// §5.4 update reconcile — add
// ===========================================================================

test("update: adds a new skill (create action, on disk, in manifest)", async () => {
  await withSandbox(async (sb) => {
    await seedConfigDir(sb, "claude", "project");
    await makeFixtureBundle(sb, "claude", ["a"]);
    assert.equal((await runCli2(installArgs(sb), sb)).exitCode, EXIT.SUCCESS);

    // Extend the source bundle with a second skill.
    await makeFixtureBundle(sb, "claude", ["a", "b"]);
    const report = await runCli2(updateArgs(sb), sb);
    assert.equal(report.exitCode, EXIT.SUCCESS);

    const created = actionFor(actionsOf(report), "skills/b/SKILL.md");
    assert.ok(created, "expected an action for skills/b/SKILL.md");
    assert.equal(created.action, "create");

    assert.ok(await exists(join(destDir(sb), "skills", "b", "SKILL.md")), "b SKILL.md should exist");

    const m = await readManifest(sb);
    assert.ok(m.skills.includes("a"), "manifest keeps a");
    assert.ok(m.skills.includes("b"), "manifest gains b");
  });
});

// ===========================================================================
// §5.4 update reconcile — change
// ===========================================================================

test("update: changed source bytes ⇒ overwrite, disk matches, manifest sha changes", async () => {
  await withSandbox(async (sb) => {
    await seedConfigDir(sb, "claude", "project");
    await makeFixtureBundle(sb, "claude", ["a"]);
    assert.equal((await runCli2(installArgs(sb), sb)).exitCode, EXIT.SUCCESS);

    const before = await readManifest(sb);
    const beforeSha = before.files.find((f) => f.path === "skills/a/SKILL.md")?.sha256;
    assert.ok(beforeSha, "expected a recorded sha for skills/a/SKILL.md");

    const newBytes = "# a\nCHANGED fixture skill body — new bytes\n";
    await writeFile(srcSkill(sb, "a"), newBytes);

    const report = await runCli2(updateArgs(sb), sb);
    assert.equal(report.exitCode, EXIT.SUCCESS);

    const act = actionFor(actionsOf(report), "skills/a/SKILL.md");
    assert.ok(act, "expected action for skills/a/SKILL.md");
    assert.equal(act.action, "overwrite");

    const onDisk = await readFile(join(destDir(sb), "skills", "a", "SKILL.md"), "utf8");
    assert.equal(onDisk, newBytes, "on-disk bytes should match new source");

    const after = await readManifest(sb);
    const afterSha = after.files.find((f) => f.path === "skills/a/SKILL.md")?.sha256;
    assert.ok(afterSha, "expected an updated sha");
    assert.notEqual(afterSha, beforeSha, "manifest sha256 should change");
  });
});

// ===========================================================================
// §5.4 update reconcile — remove + manifest-scoped orphan
// ===========================================================================

test("update: removed-from-source skill ⇒ remove; untracked sibling survives", async () => {
  await withSandbox(async (sb) => {
    await seedConfigDir(sb, "claude", "project");
    await makeFixtureBundle(sb, "claude", ["a", "b"]);
    assert.equal((await runCli2(installArgs(sb), sb)).exitCode, EXIT.SUCCESS);

    // An UNTRACKED user file inside the namespace dir — must survive update.
    const userNote = join(destDir(sb), "user-note.txt");
    await writeFile(userNote, "user content\n");

    // Truly remove skill "a" from the source bundle (fixtures only creates the ids passed).
    await rm(join(sb.source, "claude", "skills", "a"), { recursive: true, force: true });

    const report = await runCli2(updateArgs(sb), sb);
    assert.equal(report.exitCode, EXIT.SUCCESS);

    const act = actionFor(actionsOf(report), "skills/a/SKILL.md");
    assert.ok(act, "expected a remove action for skills/a/SKILL.md");
    assert.equal(act.action, "remove");

    assert.equal(await exists(join(destDir(sb), "skills", "a", "SKILL.md")), false, "a removed from disk");

    const m = await readManifest(sb);
    assert.ok(!m.skills.includes("a"), "manifest no longer lists a");
    assert.ok(m.skills.includes("b"), "manifest still lists b");

    // Orphan removal is manifest-scoped only: the untracked file survives.
    assert.ok(await exists(userNote), "untracked user-note.txt must survive");
  });
});

// ===========================================================================
// §5.4 multi-skill SCALE-02
// ===========================================================================

test("install: multiple skills land on disk and in the manifest (SCALE-02)", async () => {
  await withSandbox(async (sb) => {
    await seedConfigDir(sb, "claude", "project");
    await makeFixtureBundle(sb, "claude", ["a", "b", "c"]);

    const report = await runCli2(installArgs(sb), sb);
    assert.equal(report.exitCode, EXIT.SUCCESS);

    for (const id of ["a", "b", "c"]) {
      assert.ok(await exists(join(destDir(sb), "skills", id, "SKILL.md")), `${id} SKILL.md on disk`);
    }
    const m = await readManifest(sb);
    for (const id of ["a", "b", "c"]) {
      assert.ok(m.skills.includes(id), `manifest lists ${id}`);
    }
  });
});

// ===========================================================================
// §5.5 skip-modified + --force
// ===========================================================================

test("update: locally modified file is skip-modified (preserved); --force overwrites", async () => {
  await withSandbox(async (sb) => {
    await seedConfigDir(sb, "claude", "project");
    await makeFixtureBundle(sb, "claude", ["a"]);
    assert.equal((await runCli2(installArgs(sb), sb)).exitCode, EXIT.SUCCESS);

    // Hand-edit the destination file so its bytes differ from BOTH the recorded hash and source.
    const destFile = join(destDir(sb), "skills", "a", "SKILL.md");
    const userBytes = "# a\nLOCAL USER EDIT — do not clobber\n";
    await writeFile(destFile, userBytes);

    // Plain update: must NOT touch the user edit.
    const skipped = await runCli2(updateArgs(sb), sb);
    const skipAct = actionFor(actionsOf(skipped), "skills/a/SKILL.md");
    assert.ok(skipAct, "expected an action for the modified file");
    assert.equal(skipAct.action, "skip-modified");
    assert.equal(await readFile(destFile, "utf8"), userBytes, "user edit must survive plain update");

    // --force: must overwrite with source bytes.
    const forced = await runCli2(updateArgs(sb, true), sb);
    const forceAct = actionFor(actionsOf(forced), "skills/a/SKILL.md");
    assert.ok(forceAct, "expected an action under --force");
    assert.equal(forceAct.action, "overwrite");

    const sourceBytes = await readFile(srcSkill(sb, "a"), "utf8");
    assert.equal(await readFile(destFile, "utf8"), sourceBytes, "--force restores source bytes");
  });
});

// ===========================================================================
// §5.6 uninstall exactness + idempotency
// ===========================================================================

test("uninstall: removes recorded files + manifest, spares outside files, idempotent", async () => {
  await withSandbox(async (sb) => {
    await seedConfigDir(sb, "claude", "project");
    await makeFixtureBundle(sb, "claude", ["a"]);
    assert.equal((await runCli2(installArgs(sb), sb)).exitCode, EXIT.SUCCESS);

    const m = await readManifest(sb);
    const recorded = m.files.map((f) => join(destDir(sb), f.path));
    for (const p of recorded) assert.ok(await exists(p), `recorded file present pre-uninstall: ${p}`);

    // An unrelated user skill OUTSIDE the namespace dir — must survive.
    const outsideFile = join(sb.cwd, ".claude", "skills", "my-own-skill", "SKILL.md");
    await mkdir(join(sb.cwd, ".claude", "skills", "my-own-skill"), { recursive: true });
    await writeFile(outsideFile, "my own skill\n");

    // An untracked file INSIDE the namespace dir.
    const insideUntracked = join(destDir(sb), "untracked.txt");
    await writeFile(insideUntracked, "scratch\n");

    const report = await runCli2(uninstallArgs(sb), sb);
    assert.equal(report.exitCode, EXIT.SUCCESS);
    for (const a of actionsOf(report)) assert.equal(a.action, "remove");

    // Manifest-recorded files are gone.
    for (const p of recorded) assert.equal(await exists(p), false, `recorded file removed: ${p}`);
    // The manifest file itself is gone.
    assert.equal(await exists(manifestPath(sb)), false, "manifest file removed");
    // The unrelated file OUTSIDE the namespace survives.
    assert.ok(await exists(outsideFile), "outside user skill must survive uninstall");

    // Re-run uninstall ⇒ no-op, SUCCESS (idempotent).
    const again = await runCli2(uninstallArgs(sb), sb);
    assert.equal(again.exitCode, EXIT.SUCCESS, "second uninstall is idempotent SUCCESS");
    assert.deepEqual(actionsOf(again), [], "second uninstall performs no file actions");
  });
});
