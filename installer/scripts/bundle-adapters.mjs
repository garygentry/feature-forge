// Pack-time bundling for the published npm package.
//
// The adapter bundles live at the repo root (`../adapters`), but npm can only
// pack files inside the package root. The runtime resolves bundles from the
// "packaged copy" path `<installerPkgRoot>/adapters/<agent>` (see
// src/source.ts → bundleCandidates, "packaged copy (D7)"), so the published
// tarball MUST carry `adapters/` at the package root. This script copies it in
// (and the repo LICENSE) just before `npm pack` / `npm publish`.
//
// `installer/adapters/` and `installer/LICENSE` are gitignored — these are
// build artifacts, never committed. Runs via the package.json `prepack` hook.
//
// VCS/Python build artifacts (`__pycache__/`, `*.pyc`) are filtered out so the
// published package stays clean.

import { cpSync, rmSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url)); // installer/scripts
const pkgRoot = resolve(here, ".."); // installer/
const repoRoot = resolve(pkgRoot, ".."); // repo root

const srcAdapters = join(repoRoot, "adapters");
const destAdapters = join(pkgRoot, "adapters");

if (!existsSync(srcAdapters)) {
  console.error(`bundle-adapters: source not found: ${srcAdapters}`);
  process.exit(1);
}

// Exclude Python build artifacts from the published bundle.
const filter = (src) => !/(?:^|[\\/])__pycache__(?:[\\/]|$)/.test(src) && !src.endsWith(".pyc");

// Start clean so a stale bundle never lingers.
rmSync(destAdapters, { recursive: true, force: true });
cpSync(srcAdapters, destAdapters, { recursive: true, filter });

// Carry the license into the published package.
const srcLicense = join(repoRoot, "LICENSE");
if (existsSync(srcLicense)) {
  cpSync(srcLicense, join(pkgRoot, "LICENSE"));
}

console.log(`bundle-adapters: copied adapters/ (+LICENSE) into ${pkgRoot} for packing.`);
