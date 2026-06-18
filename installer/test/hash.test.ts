/**
 * Tests for hash.ts (spec 03 §3.3-§3.6, OQ-4). Content-defined, relocation-invariant,
 * mtime-stable digests; a content edit changes the digest; the inventory mirrors the tree walk.
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, rm, mkdir, writeFile, utimes } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import {
  sha256File,
  sha256Tree,
  computeSourceHash,
  listBundleFiles,
} from "../dist/hash.js";

/** Materialize a small fixed tree under a fresh temp dir; returns the root. */
async function makeTree(base: string, name: string): Promise<string> {
  const root = join(base, name);
  await mkdir(join(root, "skills", "a"), { recursive: true });
  await mkdir(join(root, "scripts"), { recursive: true });
  await writeFile(join(root, "skills", "a", "SKILL.md"), "# a\nbody\n");
  await writeFile(join(root, "scripts", "forge-root.sh"), "#!/usr/bin/env bash\n");
  return root;
}

async function withTmp(fn: (base: string) => Promise<void>): Promise<void> {
  const base = await mkdtemp(join(tmpdir(), "ffi-hash-"));
  try {
    await fn(base);
  } finally {
    await rm(base, { recursive: true, force: true });
  }
}

test("sha256File matches an independent digest of the same bytes", async () => {
  await withTmp(async (base) => {
    const p = join(base, "f.txt");
    const bytes = "hello forge\n";
    await writeFile(p, bytes);
    const expected = createHash("sha256").update(Buffer.from(bytes)).digest("hex");
    const got = sha256File(p);
    assert.equal(got, expected);
    assert.match(got, /^[0-9a-f]{64}$/);
  });
});

test("sha256Tree/computeSourceHash are relocation-invariant", async () => {
  await withTmp(async (base) => {
    const a = await makeTree(base, "copyA");
    const b = await makeTree(base, "copyB");
    assert.equal(sha256Tree(a), sha256Tree(b));
    assert.equal(computeSourceHash(a), computeSourceHash(b));
  });
});

test("sha256Tree is stable under an mtime-only touch (OQ-4)", async () => {
  await withTmp(async (base) => {
    const root = await makeTree(base, "tree");
    const before = sha256Tree(root);
    const future = new Date(Date.now() + 1_000_000);
    await utimes(join(root, "skills", "a", "SKILL.md"), future, future);
    assert.equal(sha256Tree(root), before);
  });
});

test("sha256Tree changes after a content edit (content-defined)", async () => {
  await withTmp(async (base) => {
    const root = await makeTree(base, "tree");
    const before = sha256Tree(root);
    await writeFile(join(root, "skills", "a", "SKILL.md"), "# a\nedited body\n");
    assert.notEqual(sha256Tree(root), before);
  });
});

test("listBundleFiles is sorted by POSIX relpath and agrees with sha256File", async () => {
  await withTmp(async (base) => {
    const root = await makeTree(base, "tree");
    const inv = listBundleFiles(root);
    const relpaths = inv.map((e) => e.relpath);
    assert.deepEqual(relpaths, ["scripts/forge-root.sh", "skills/a/SKILL.md"]);
    for (const e of inv) {
      assert.equal(e.sha256, sha256File(join(root, ...e.relpath.split("/"))));
      assert.match(e.sha256, /^[0-9a-f]{64}$/);
    }
  });
});
