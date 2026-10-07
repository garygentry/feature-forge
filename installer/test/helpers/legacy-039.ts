/**
 * Reproduces the Copilot install that the published installer (@garygentry/feature-forge <= 0.3.9,
 * ff <= 0.21.0) wrote, so migration tests start from what real users have on disk rather than from
 * a reshaped current install. Captured from `npm pack @garygentry/feature-forge@0.3.9` installs
 * (project/global x copy/symlink):
 *  - primary runtime at `<scope>/.github/feature-forge` (personal scope too: `~/.github`), skills as
 *    `skills/<name>/<name>.md`, agents as `agents/<name>.md`;
 *  - manifest `<scope>/.github/.feature-forge.<scope>.json`, schemaVersion 2, copy files hashed,
 *    symlink files path-only plus `link.target`;
 *  - one `managed-block` placement in `<scope>/.github/copilot-instructions.md`, whose body is 0.3.9's
 *    `renderCopilotBlock` verbatim.
 * NOT a `.test.ts` file, so the test glob ignores it.
 */

import { createHash } from "node:crypto";
import { mkdir, readFile, readdir, symlink, writeFile } from "node:fs/promises";
import { dirname, join, relative } from "node:path";
import type { Sandbox } from "./sandbox.ts";

const START = "<!-- feature-forge:managed:start -->";
const END = "<!-- feature-forge:managed:end -->";

/** 0.3.9 `renderCopilotBlock`, verbatim. */
export function render039Block(skills: readonly string[]): string {
  return [
    "# feature-forge",
    "",
    "The feature-forge skill suite is installed in this repository under",
    "`.github/feature-forge/`. GitHub Copilot has no skills loader, so consult those files",
    "directly when a feature-forge workflow is requested.",
    "",
    "Each skill lives at `.github/feature-forge/skills/<name>/SKILL.md`. Available skills:",
    "",
    ...[...skills].sort().map((s) => `- ${s}`),
    "",
    "Shared references are under `.github/feature-forge/references/`; helper scripts under",
    "`.github/feature-forge/scripts/`.",
  ].join("\n");
}

export interface Legacy039 {
  /** `<scope root>/.github`. */
  readonly githubDir: string;
  /** `<scope root>/.github/feature-forge` (a dir, or a symlink to `bundle`). */
  readonly runtime: string;
  readonly manifestPath: string;
  readonly instructions: string;
  /** The 0.3.9 adapter bundle (an npx cache stand-in); a symlink install points here. */
  readonly bundle: string;
  readonly userPrefix: string;
  readonly userSuffix: string;
}

const sha = (data: string | Buffer) => createHash("sha256").update(data).digest("hex");

async function listFiles(root: string, dir = root): Promise<string[]> {
  const out: string[] = [];
  for (const e of await readdir(dir, { withFileTypes: true })) {
    const abs = join(dir, e.name);
    if (e.isDirectory()) out.push(...await listFiles(root, abs));
    else out.push(relative(root, abs).split("\\").join("/"));
  }
  return out.sort();
}

/** Seed a 0.3.9 Copilot install, with user instructions around the managed block. */
export async function seed039Copilot(
  sb: Sandbox,
  scope: "project" | "global",
  mode: "copy" | "symlink",
  skills: readonly string[] = ["forge-1-prd"],
  agents: readonly string[] = ["forge-verifier"],
): Promise<Legacy039> {
  const bundle = join(dirname(sb.source), "npx-cache-039", "adapters", "copilot");
  await mkdir(join(bundle, "scripts"), { recursive: true });
  await writeFile(join(bundle, "scripts", "forge-root.sh"), "#!/usr/bin/env bash\n# 0.3.9\n");
  await writeFile(
    join(bundle, ".feature-forge-bundle.json"),
    JSON.stringify({ name: "feature-forge", version: "0.21.0", agent: "copilot", generatedBy: "python3 scripts/build-adapters.py" }, null, 2) + "\n",
  );
  for (const id of skills) {
    await mkdir(join(bundle, "skills", id, "references"), { recursive: true });
    await writeFile(join(bundle, "skills", id, `${id}.md`), `# ${id}\n0.3.9 skill body\n`);
    await writeFile(join(bundle, "skills", id, "references", "shared-conventions.md"), "0.3.9 ref\n");
  }
  await mkdir(join(bundle, "agents"), { recursive: true });
  for (const id of agents) await writeFile(join(bundle, "agents", `${id}.md`), `# ${id}\n0.3.9 agent\n`);

  const scopeRoot = scope === "global" ? sb.home : sb.cwd;
  const githubDir = join(scopeRoot, ".github");
  const runtime = join(githubDir, "feature-forge");
  await mkdir(githubDir, { recursive: true });
  const rels = await listFiles(bundle);
  if (mode === "symlink") {
    await symlink(bundle, runtime, "dir");
  } else {
    for (const rel of rels) {
      await mkdir(dirname(join(runtime, rel)), { recursive: true });
      await writeFile(join(runtime, rel), await readFile(join(bundle, rel)));
    }
  }
  const files = await Promise.all(rels.map(async (rel) => mode === "symlink"
    ? { path: rel }
    : { path: rel, sha256: sha(await readFile(join(bundle, rel))) }));

  const region = `${START}\n${render039Block(skills)}\n${END}`;
  const userPrefix = "# My team rules\n";
  const userSuffix = "Always run tests.\n";
  const instructions = join(githubDir, "copilot-instructions.md");
  await writeFile(instructions, `${userPrefix}\n${region}\n\n${userSuffix}`);

  const now = "2026-09-30T12:00:00.000Z";
  const manifest = {
    schemaVersion: 2,
    agent: "copilot",
    scope,
    mode,
    destination: runtime,
    featureForgeVersion: null,
    sourceHash: sha("0.3.9"),
    raufPin: null,
    installedAt: now,
    updatedAt: now,
    skills: [...skills].sort(),
    files,
    ...(mode === "symlink" ? { link: { target: bundle } } : {}),
    placements: [{
      kind: "managed-block",
      root: githubDir,
      destination: instructions,
      files: [{ path: "copilot-instructions.md", sha256: sha(region) }],
    }],
  };
  const manifestPath = join(githubDir, `.feature-forge.${scope}.json`);
  await writeFile(manifestPath, JSON.stringify(manifest, null, 2) + "\n");
  return { githubDir, runtime, manifestPath, instructions, bundle, userPrefix, userSuffix };
}

/** Every regular file and symlink under `root` (relative, sorted), with each file's hash. */
export async function snapshotTree(root: string): Promise<string[]> {
  const out: string[] = [];
  const walk = async (dir: string): Promise<void> => {
    let entries;
    try {
      entries = await readdir(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const e of entries) {
      const abs = join(dir, e.name);
      const rel = relative(root, abs).split("\\").join("/");
      if (e.isSymbolicLink()) out.push(`${rel} -> link`);
      else if (e.isDirectory()) await walk(abs);
      else out.push(`${rel} ${sha(await readFile(abs))}`);
    }
  };
  await walk(root);
  return out.sort();
}
