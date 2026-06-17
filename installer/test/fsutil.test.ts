import { test } from "node:test";
import assert from "node:assert/strict";
import * as fsp from "node:fs/promises";
import * as path from "node:path";
import { withSandbox } from "./helpers/sandbox.ts";
import {
  resolveWithin,
  copyDir,
  symlinkDir,
  removePath,
  removeEmptyDirsWithin,
  isWindows,
} from "../dist/fsutil.js";

test("named exports are present", () => {
  for (const fn of [resolveWithin, copyDir, symlinkDir, removePath, removeEmptyDirsWithin, isWindows]) {
    assert.equal(typeof fn, "function");
  }
});

test("resolveWithin accepts in-root segments and rejects escapes before any write", async () => {
  await withSandbox(async (sb) => {
    const root = sb.home;
    const inside = resolveWithin(root, "skills/feature-forge", "forge/SKILL.md");
    assert.ok(inside.ok);
    assert.equal(inside.value, path.resolve(root, "skills/feature-forge/forge/SKILL.md"));

    // empty segments → root itself is inside
    assert.ok(resolveWithin(root).ok);

    const escape = resolveWithin(root, "skills/feature-forge", "../../../etc/passwd");
    assert.ok(!escape.ok);
    assert.equal(escape.error.code, "PATH_ESCAPE");

    const abs = resolveWithin(root, "/etc/passwd");
    assert.ok(!abs.ok);
    assert.equal(abs.error.code, "PATH_ESCAPE");

    // sibling prefix must NOT false-pass (the /root-evil trap)
    const sibling = resolveWithin(root, "..", `${path.basename(root)}-evil`, "x");
    assert.ok(!sibling.ok);
    assert.equal(sibling.error.code, "PATH_ESCAPE");

    // no filesystem entries were created by resolveWithin
    const entries = await fsp.readdir(root).catch(() => []);
    assert.deepEqual(entries, []);
  });
});

test("removePath on a symlinked dir unlinks the link and leaves the target byte-intact", async (t) => {
  if (isWindows()) return t.skip("symlink semantics differ on Windows");
  await withSandbox(async (sb) => {
    const target = path.join(sb.home, "target");
    await fsp.mkdir(target, { recursive: true });
    await fsp.writeFile(path.join(target, "a.txt"), "hello");
    await fsp.mkdir(path.join(target, "sub"), { recursive: true });
    await fsp.writeFile(path.join(target, "sub/b.txt"), "world");

    const link = path.join(sb.home, "link");
    await fsp.symlink(target, link, "dir");

    const res = await removePath(link);
    assert.ok(res.ok);

    // link gone, target tree fully intact
    await assert.rejects(fsp.lstat(link));
    assert.equal(await fsp.readFile(path.join(target, "a.txt"), "utf8"), "hello");
    assert.equal(await fsp.readFile(path.join(target, "sub/b.txt"), "utf8"), "world");
  });
});

test("removePath removes a real dir recursively and is idempotent on a missing path", async () => {
  await withSandbox(async (sb) => {
    const dir = path.join(sb.home, "realdir");
    await fsp.mkdir(path.join(dir, "nested"), { recursive: true });
    await fsp.writeFile(path.join(dir, "nested/f.txt"), "x");

    assert.ok((await removePath(dir)).ok);
    await assert.rejects(fsp.stat(dir));

    // already-gone → ok (idempotent)
    assert.ok((await removePath(dir)).ok);
    assert.ok((await removePath(path.join(sb.home, "never-existed"))).ok);
  });
});

test("removeEmptyDirsWithin prunes empties but halts on a dir holding an untracked file", async () => {
  await withSandbox(async (sb) => {
    const stopRoot = path.join(sb.home, ".claude", "skills");
    const ns = path.join(stopRoot, "feature-forge");
    const deep = path.join(ns, "forge", "inner");
    await fsp.mkdir(deep, { recursive: true });

    // all empty → prune up to but excluding stopRoot
    const res = await removeEmptyDirsWithin(deep, stopRoot);
    assert.ok(res.ok);
    await assert.rejects(fsp.stat(ns), "namespace dir pruned");
    assert.ok((await fsp.stat(stopRoot)).isDirectory(), "stopRoot preserved");

    // now a tree with an untracked file deep inside → halt at the holder
    const ns2 = path.join(stopRoot, "feature-forge");
    const branch = path.join(ns2, "skills", "x");
    await fsp.mkdir(branch, { recursive: true });
    await fsp.writeFile(path.join(ns2, "skills", "untracked.txt"), "keep me");
    const emptyLeaf = path.join(ns2, "skills", "x");

    const res2 = await removeEmptyDirsWithin(emptyLeaf, stopRoot);
    assert.ok(res2.ok);
    assert.ok((await fsp.stat(path.join(ns2, "skills"))).isDirectory(), "non-empty dir kept");
    assert.equal(await fsp.readFile(path.join(ns2, "skills/untracked.txt"), "utf8"), "keep me");
  });
});

test("removeEmptyDirsWithin rejects a startDir outside stopRoot with PATH_ESCAPE", async () => {
  await withSandbox(async (sb) => {
    const stopRoot = path.join(sb.home, "boundary");
    await fsp.mkdir(stopRoot, { recursive: true });
    const outside = path.join(sb.home, "elsewhere");
    const res = await removeEmptyDirsWithin(outside, stopRoot);
    assert.ok(!res.ok);
    assert.equal(res.error.code, "PATH_ESCAPE");
  });
});

test("copyDir copies a tree and symlinkDir links off-Windows / copies on Windows", async () => {
  await withSandbox(async (sb) => {
    const src = path.join(sb.home, "src");
    await fsp.mkdir(src, { recursive: true });
    await fsp.writeFile(path.join(src, "f.txt"), "data");

    const dest = path.join(sb.home, "dest", "ns");
    assert.ok((await copyDir(src, dest)).ok);
    assert.equal(await fsp.readFile(path.join(dest, "f.txt"), "utf8"), "data");

    const link = path.join(sb.home, "linkns");
    const sl = await symlinkDir(src, link);
    assert.ok(sl.ok);
    assert.equal(sl.value.mode, isWindows() ? "copy" : "symlink");
    assert.equal(await fsp.readFile(path.join(link, "f.txt"), "utf8"), "data");
  });
});
