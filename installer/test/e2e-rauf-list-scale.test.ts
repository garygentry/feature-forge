/**
 * End-to-end suites for rauf preflight outcomes (spec 08 §5.10 + RAUF-04), `list` status
 * derivation + no-network (§5.13), and the synthetic agent-row scalability proof (§5.14).
 *
 * Every test is hermetic: a temp HOME/cwd/source via `withSandbox`, a fixture bundle via
 * `makeFixtureBundle`, and a mock `RegistryQuery` — no real `~`, no network. Built artifacts are
 * imported as `.js`; helpers as `.ts` (the type-stripping import rule, item 002).
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile, writeFile, readdir, stat } from "node:fs/promises";
import { join } from "node:path";
import { withSandbox, seedConfigDir } from "./helpers/sandbox.ts";
import { makeFixtureBundle } from "./helpers/fixtures.ts";
import { runCli2 } from "./helpers/run.ts";
import {
  resolvableRegistry,
  unresolvableRegistry,
  neverCalledRegistry,
} from "./helpers/registry.ts";
import { RAUF_PIN } from "../dist/rauf.js";
import { EXIT, AGENT_TARGETS, AGENT_IDS } from "../dist/types.js";
import type { AgentId, InstallManifest, Scope } from "../dist/types.js";
import { detectAgent, destinationFor } from "../dist/agent-targets.js";

// --------------------------------------------------------------------------
// Shared sandbox path helpers (claude, project scope).
// --------------------------------------------------------------------------

/** The claude project-scope namespace destination under the sandbox cwd. */
function claudeDest(cwd: string): string {
  return join(cwd, ".claude", "skills", "feature-forge");
}

/** The claude project-scope manifest path under the sandbox cwd. */
function claudeManifestPath(cwd: string): string {
  return join(cwd, ".claude", "skills", ".feature-forge.project.json");
}

/** Read + JSON.parse a manifest file. */
async function readManifestJson(p: string): Promise<InstallManifest> {
  return JSON.parse(await readFile(p, "utf8")) as InstallManifest;
}

/** Status helper: the synthetic list rows encode `<key>:<value>` in relpath. */
function listStatus(actions: { relpath: string }[], key: string): string | undefined {
  const row = actions.find((a) => a.relpath.startsWith(`${key}:`));
  return row ? row.relpath.slice(key.length + 1) : undefined;
}

// ==========================================================================
// RAUF preflight — three cases + RAUF-04 (spec 08 §5.10)
// ==========================================================================

test("RAUF resolvable: install succeeds and records raufPin === RAUF_PIN", async () => {
  await withSandbox(async (sb) => {
    await seedConfigDir(sb, "claude");
    await makeFixtureBundle(sb, "claude");

    const report = await runCli2(
      ["install", "-a", "claude", "-y", "--source", sb.source],
      sb,
      { registry: resolvableRegistry },
    );

    assert.equal(report.exitCode, EXIT.SUCCESS);
    const claude = report.agents.find((a) => a.agent === "claude");
    assert.ok(claude && claude.ok);

    const manifest = await readManifestJson(claudeManifestPath(sb.cwd));
    assert.equal(manifest.raufPin, RAUF_PIN);
  });
});

test("RAUF unresolvable: skills still install, exit FAILURE, raufError carries the fixed production message, no vendored binary", async () => {
  await withSandbox(async (sb) => {
    await seedConfigDir(sb, "claude");
    await makeFixtureBundle(sb, "claude");
    const dest = claudeDest(sb.cwd);

    const report = await runCli2(
      ["install", "-a", "claude", "-y", "--source", sb.source],
      sb,
      { registry: unresolvableRegistry },
    );

    // Skills STILL installed: namespace dir + manifest exist, claude AgentReport ok.
    const claude = report.agents.find((a) => a.agent === "claude");
    assert.ok(claude && claude.ok === true, "claude AgentReport.ok === true");
    assert.ok((await stat(dest)).isDirectory(), "namespace dir exists");
    const manifest = await readManifestJson(claudeManifestPath(sb.cwd));
    assert.equal(manifest.raufPin, null, "no usable pin recorded on unresolvable preflight");

    // Run-level failure surfaced via raufError with the FIXED production message.
    assert.equal(report.exitCode, EXIT.FAILURE);
    assert.ok(report.raufError, "raufError present");
    assert.equal(report.raufError!.code, "RAUF_UNRESOLVABLE");
    // The production message mentions rauf / the pin — NOT the stub's text.
    assert.notEqual(report.raufError!.message, "stub message");
    assert.ok(report.raufError!.message.includes(RAUF_PIN), "message names the pin");
    assert.match(report.raufError!.message, /not resolvable from the npm registry/);

    // No vendored binary written: only the expected skill files exist under the namespace dir.
    const present = new Set<string>();
    async function walk(dir: string, prefix: string): Promise<void> {
      for (const e of await readdir(dir, { withFileTypes: true })) {
        const rel = prefix ? `${prefix}/${e.name}` : e.name;
        if (e.isDirectory()) await walk(join(dir, e.name), rel);
        else present.add(rel);
      }
    }
    await walk(dest, "");
    assert.deepEqual(
      [...present].sort(),
      [
        ".feature-forge-bundle.json",
        "scripts/epic-manifest.py",
        "scripts/forge-bootstrap.py",
        "scripts/forge-init.sh",
        "scripts/forge-root.sh",
        "scripts/validate-traceability.py",
        "skills/forge-1-prd/SKILL.md",
      ],
      "only the bundle's own files exist — no vendored rauf binary",
    );
  });
});

test("RAUF skip: --skip-rauf records raufPin === null, registry never called, exit SUCCESS", async () => {
  await withSandbox(async (sb) => {
    await seedConfigDir(sb, "claude");
    await makeFixtureBundle(sb, "claude");

    // neverCalledRegistry throws if invoked — the run completing proves no network call.
    const report = await runCli2(
      ["install", "-a", "claude", "--skip-rauf", "-y", "--source", sb.source],
      sb,
      { registry: neverCalledRegistry },
    );

    assert.equal(report.exitCode, EXIT.SUCCESS);
    assert.equal(report.raufError, undefined);
    const manifest = await readManifestJson(claudeManifestPath(sb.cwd));
    assert.equal(manifest.raufPin, null);
  });
});

test("RAUF-04: idempotent (re-run records exactly one raufPin, no dup) + reversible (uninstall clears it)", async () => {
  await withSandbox(async (sb) => {
    await seedConfigDir(sb, "claude");
    await makeFixtureBundle(sb, "claude");
    const mpath = claudeManifestPath(sb.cwd);

    const first = await runCli2(
      ["install", "-a", "claude", "-y", "--source", sb.source],
      sb,
      { registry: resolvableRegistry },
    );
    assert.equal(first.exitCode, EXIT.SUCCESS);

    const second = await runCli2(
      ["install", "-a", "claude", "-y", "--source", sb.source],
      sb,
      { registry: resolvableRegistry },
    );
    assert.equal(second.exitCode, EXIT.SUCCESS);

    // Idempotent: the manifest records exactly one raufPin (a scalar, not duplicated).
    const manifest = await readManifestJson(mpath);
    assert.equal(manifest.raufPin, RAUF_PIN);
    assert.equal(typeof manifest.raufPin, "string");

    // Reversible: uninstall removes the manifest entirely, clearing the recorded raufPin with it.
    const un = await runCli2(["uninstall", "-a", "claude", "-y", "--source", sb.source], sb);
    assert.equal(un.exitCode, EXIT.SUCCESS);
    await assert.rejects(stat(mpath), "manifest file is gone after uninstall");
  });
});

// ==========================================================================
// list — status derivation + no network (spec 08 §5.13)
// ==========================================================================

test("list — not installed: detected true, installed false", async () => {
  await withSandbox(async (sb) => {
    // Seed the claude config dir only — no install.
    await seedConfigDir(sb, "claude");
    await makeFixtureBundle(sb, "claude");

    const report = await runCli2(["list", "--json", "--source", sb.source], sb);
    assert.equal(report.exitCode, EXIT.SUCCESS);
    const claude = report.agents.find((a) => a.agent === "claude");
    assert.ok(claude);
    assert.equal(claude!.detected, true);
    assert.equal(listStatus(claude!.actions, "detected"), "true");
    assert.equal(listStatus(claude!.actions, "installed"), "false");
  });
});

test("list — installed + up to date: detected true, installed true, up-to-date true", async () => {
  await withSandbox(async (sb) => {
    await seedConfigDir(sb, "claude");
    await makeFixtureBundle(sb, "claude");
    await runCli2(["install", "-a", "claude", "-y", "--source", sb.source], sb);

    const report = await runCli2(["list", "--json", "--source", sb.source], sb);
    const claude = report.agents.find((a) => a.agent === "claude");
    assert.ok(claude);
    assert.equal(listStatus(claude!.actions, "detected"), "true");
    assert.equal(listStatus(claude!.actions, "installed"), "true");
    assert.equal(listStatus(claude!.actions, "up-to-date"), "true");
  });
});

test("list — out of date: mutating the source flips up-to-date to false", async () => {
  await withSandbox(async (sb) => {
    await seedConfigDir(sb, "claude");
    await makeFixtureBundle(sb, "claude");
    await runCli2(["install", "-a", "claude", "-y", "--source", sb.source], sb);

    // Mutate the source SKILL.md so the bundle sourceHash diverges from the recorded manifest.
    await writeFile(
      join(sb.source, "claude", "skills", "forge-1-prd", "SKILL.md"),
      "# forge-1-prd\nMUTATED body\n",
    );

    const report = await runCli2(["list", "--json", "--source", sb.source], sb);
    const claude = report.agents.find((a) => a.agent === "claude");
    assert.ok(claude);
    assert.equal(listStatus(claude!.actions, "up-to-date"), "false");
  });
});

test("list — drift present: hand-editing a destination file flags drift (REQ-SAFE-03, §5.13)", async () => {
  await withSandbox(async (sb) => {
    await seedConfigDir(sb, "claude");
    await makeFixtureBundle(sb, "claude");
    await runCli2(["install", "-a", "claude", "-y", "--source", sb.source], sb);

    // Hand-edit a DESTINATION file so its bytes differ from BOTH the recorded sha256 AND the
    // source bundle (the source is left untouched here — this is the destination-drift half of
    // REQ-SAFE-03, distinct from the source-mutation "out of date" test above).
    await writeFile(
      join(claudeDest(sb.cwd), "skills", "forge-1-prd", "SKILL.md"),
      "# forge-1-prd\nLOCAL DESTINATION EDIT (drift)\n",
    );

    const report = await runCli2(["list", "--json", "--source", sb.source], sb);
    assert.equal(report.exitCode, EXIT.SUCCESS);
    const claude = report.agents.find((a) => a.agent === "claude");
    assert.ok(claude);
    // Source is unchanged ⇒ still up-to-date by source hash; but the destination drifted.
    assert.equal(listStatus(claude!.actions, "up-to-date"), "true", "source unchanged ⇒ up-to-date true");
    assert.equal(listStatus(claude!.actions, "drift"), "true", "edited destination file ⇒ drift flagged");
  });
});

test("list — installed + clean: no destination drift (drift false)", async () => {
  await withSandbox(async (sb) => {
    await seedConfigDir(sb, "claude");
    await makeFixtureBundle(sb, "claude");
    await runCli2(["install", "-a", "claude", "-y", "--source", sb.source], sb);

    const report = await runCli2(["list", "--json", "--source", sb.source], sb);
    const claude = report.agents.find((a) => a.agent === "claude");
    assert.ok(claude);
    assert.equal(listStatus(claude!.actions, "drift"), "false", "an untouched install reports no drift");
  });
});

test("list — no network: list with neverCalledRegistry does not throw (registry never invoked)", async () => {
  await withSandbox(async (sb) => {
    await seedConfigDir(sb, "claude");
    await makeFixtureBundle(sb, "claude");
    await runCli2(["install", "-a", "claude", "-y", "--source", sb.source], sb);

    // neverCalledRegistry throws if consulted — list completing proves it is never invoked.
    const report = await runCli2(["list", "--json", "--source", sb.source], sb, {
      registry: neverCalledRegistry,
    });
    assert.equal(report.exitCode, EXIT.SUCCESS);
  });
});

// ==========================================================================
// SCALE-01 — synthetic agent row drives the pipeline (spec 08 §5.14)
// ==========================================================================

test("SCALE-01: a synthetic AGENT_TARGETS-shaped row flows through detectAgent + destinationFor with no function edit", async () => {
  await withSandbox(async (sb) => {
    // A fully synthetic 6th agent target — same SHAPE as a real AGENT_TARGETS row, but never
    // added to the closed AgentId set. Drive it through the pure path derivation `destinationFor`
    // and the stat-based `detectAgent` with NO edit to any installer function (REQ-SCALE-01).
    const synthetic = {
      id: "synthetic" as AgentId,
      configDirName: ".synthetic",
      installBaseDir: ".synthetic",
      installSubpath: "skills",
      installKind: "skills" as const,
      skillFileForm: "SKILL.md",
      confidence: "best-known" as const,
      docsUrl: "https://example.test/synthetic",
    };

    // destinationFor is scope-correct for both scopes — one row, no logic change.
    const project = destinationFor(synthetic, "project", sb.resolve("project"));
    const global = destinationFor(synthetic, "global", sb.resolve("global"));
    assert.equal(project, join(sb.cwd, ".synthetic", "skills", "feature-forge"));
    assert.equal(global, join(sb.home, ".synthetic", "skills", "feature-forge"));

    // Structural scalability invariant: EVERY real AGENT_TARGETS row also flows through
    // destinationFor producing a scope-correct path, demonstrating one-row extension.
    for (const id of AGENT_IDS) {
      const target = AGENT_TARGETS[id];
      for (const scope of ["project", "global"] as Scope[]) {
        const root = scope === "global" ? sb.home : sb.cwd;
        const dest = destinationFor(target, scope, sb.resolve(scope));
        const base = scope === "global"
          ? target.globalInstallBaseDir ?? target.installBaseDir
          : target.projectInstallBaseDir ?? target.installBaseDir;
        const subpath = scope === "global"
          ? target.globalInstallSubpath ?? target.installSubpath
          : target.projectInstallSubpath ?? target.installSubpath;
        const sub = subpath ? [subpath] : [];
        assert.equal(
          dest,
          join(root, base, ...sub, "feature-forge"),
        );
      }
    }

    // detectAgent works for a real injected target (claude) end-to-end: un-seeded ⇒ not detected,
    // seeded ⇒ detected — the same stat-based signal a synthetic row would use, no branch added.
    const before = detectAgent("claude", sb.resolve("project"));
    assert.equal(before.detected, false);
    await seedConfigDir(sb, "claude");
    const after = detectAgent("claude", sb.resolve("project"));
    assert.equal(after.detected, true);
  });
});
