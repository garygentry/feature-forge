/**
 * Tests for the agent-detection-map surface (spec 02): resolveRoots, destinationFor,
 * detectAgent, detectAgents, formatZeroDetection, and the AGENT_TARGETS re-export.
 * Imports the built ../dist/*.js (spec 08 §2).
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readdir, mkdir } from "node:fs/promises";
import { join } from "node:path";
import {
  AGENT_TARGETS,
  resolveRoots,
  destinationFor,
  agentRootFor,
  confidenceFor,
  detectAgent,
  detectAgents,
  formatZeroDetection,
} from "../dist/agent-targets.js";
import { withSandbox, seedConfigDir } from "./helpers/sandbox.ts";

test("re-exports AGENT_TARGETS with all five rows", () => {
  assert.deepEqual(
    Object.keys(AGENT_TARGETS).sort(),
    ["claude", "codex", "copilot", "cursor", "gemini"],
  );
});

// --------------------------------------------------------------------------- //
// A4: per-agent install-strategy reshape (Finding 6)
// --------------------------------------------------------------------------- //

test("A4: every destination is contained within its agentRootFor (REQ-SEC-02)", () => {
  for (const id of Object.keys(AGENT_TARGETS) as Array<keyof typeof AGENT_TARGETS>) {
    for (const scope of ["project", "global"] as const) {
      const opts = scope === "global" ? { home: "/h" } : { cwd: "/p" };
      const root = agentRootFor(AGENT_TARGETS[id], scope, opts);
      const dest = destinationFor(AGENT_TARGETS[id], scope, opts);
      assert.ok(
        dest === root || dest.startsWith(root + "/"),
        `${id}/${scope}: destination ${dest} escapes agentRoot ${root}`,
      );
    }
  }
});

test("A4: codex installs under .agents, copilot under .github (decoupled from detection dir)", () => {
  // Detection still probes the agent's own config dir...
  assert.equal(AGENT_TARGETS.codex.configDirName, ".codex");
  assert.equal(AGENT_TARGETS.copilot.configDirName, ".copilot");
  // ...but the install + containment root is the agent-neutral location.
  assert.equal(agentRootFor(AGENT_TARGETS.codex, "global", { home: "/h" }), "/h/.agents");
  assert.equal(agentRootFor(AGENT_TARGETS.copilot, "global", { home: "/h" }), "/h/.github");
  assert.equal(destinationFor(AGENT_TARGETS.copilot, "global", { home: "/h" }), "/h/.github/feature-forge");
});

test("A4: confidenceFor applies the project-scope override (gemini) only on project scope", () => {
  assert.equal(confidenceFor(AGENT_TARGETS.gemini, "global"), "verified-current");
  assert.equal(confidenceFor(AGENT_TARGETS.gemini, "project"), "best-known");
  // Targets without an override return the same confidence in both scopes.
  assert.equal(confidenceFor(AGENT_TARGETS.claude, "project"), "confirmed");
  assert.equal(confidenceFor(AGENT_TARGETS.codex, "project"), "verified-current");
});

test("A4: detectAgent surfaces scope-effective confidence + docsUrl", () => {
  const g = detectAgent("gemini", { home: "/h", scope: "global" });
  assert.equal(g.confidence, "verified-current");
  const p = detectAgent("gemini", { cwd: "/p", scope: "project" });
  assert.equal(p.confidence, "best-known");
  assert.ok(p.docsUrl.startsWith("https://"));
});

test("A4: every AGENT_TARGETS row carries a docsUrl and a valid installKind", () => {
  const kinds = new Set(["skills", "extension", "rules", "instructions"]);
  for (const id of Object.keys(AGENT_TARGETS) as Array<keyof typeof AGENT_TARGETS>) {
    const t = AGENT_TARGETS[id];
    assert.ok(t.docsUrl.startsWith("https://"), `${id} docsUrl`);
    assert.ok(kinds.has(t.installKind), `${id} installKind ${t.installKind}`);
  }
});

test("resolveRoots honors overrides and resolves to absolute paths", () => {
  const roots = resolveRoots({ home: "/tmp/fakehome", cwd: "/tmp/fakeproj" });
  assert.equal(roots.home, "/tmp/fakehome");
  assert.equal(roots.cwd, "/tmp/fakeproj");
  // Defaults are non-empty absolute paths (never throws).
  const def = resolveRoots();
  assert.ok(def.home.length > 0 && def.cwd.length > 0);
});

test("destinationFor matches the 5-agent x 2-scope table", () => {
  const cases: Array<[keyof typeof AGENT_TARGETS, "global" | "project", string, string]> = [
    ["claude", "global", "/home/.claude/skills/feature-forge", "/home"],
    // A4: codex installs under the agent-neutral `.agents/skills`, copilot under `.github`.
    ["codex", "global", "/home/.agents/skills/feature-forge", "/home"],
    ["copilot", "global", "/home/.github/feature-forge", "/home"],
    ["cursor", "global", "/home/.cursor/rules/feature-forge", "/home"],
    ["gemini", "global", "/home/.gemini/extensions/feature-forge", "/home"],
  ];
  for (const [agent, scope, expected, home] of cases) {
    assert.equal(destinationFor(AGENT_TARGETS[agent], scope, { home }), expected);
  }
  // Project scope derives from cwd.
  assert.equal(
    destinationFor(AGENT_TARGETS.cursor, "project", { cwd: "/proj" }),
    "/proj/.cursor/rules/feature-forge",
  );
  assert.equal(
    destinationFor(AGENT_TARGETS.claude, "project", { cwd: "/proj" }),
    "/proj/.claude/skills/feature-forge",
  );
});

test("detection is stat-based: only the seeded agent is detected", async () => {
  await withSandbox(async (sb) => {
    await seedConfigDir(sb, "claude", "global");
    const results = detectAgents({ ...sb.resolve("global") });
    const detected = results.filter((r) => r.detected).map((r) => r.agent);
    assert.deepEqual(detected, ["claude"]);
    // configDirsProbed names a real, scope-correct path.
    const claude = results.find((r) => r.agent === "claude")!;
    assert.equal(claude.configDirsProbed[0], join(sb.home, ".claude"));
    assert.equal(claude.destination, join(sb.home, ".claude", "skills", "feature-forge"));
  });
});

test("detectAgents returns all five in AGENT_IDS order; only scopes to one", async () => {
  await withSandbox(async (sb) => {
    const all = detectAgents({ ...sb.resolve() });
    assert.deepEqual(all.map((r) => r.agent), [
      "claude", "codex", "copilot", "cursor", "gemini",
    ]);
    const one = detectAgents({ ...sb.resolve(), only: "codex" });
    assert.equal(one.length, 1);
    assert.equal(one[0]!.agent, "codex");
  });
});

test("zero-detection: names every probed dir and creates no directory", async () => {
  await withSandbox(async (sb) => {
    // Sandbox project root exists but has no .<agent> dirs.
    await mkdir(sb.cwd, { recursive: true });
    const results = detectAgents({ ...sb.resolve("project") });
    assert.ok(results.every((r) => !r.detected));

    const msg = formatZeroDetection(results, "project");
    for (const r of results) {
      for (const p of r.configDirsProbed) {
        assert.ok(msg.includes(p), `message must name probed dir ${p}`);
      }
    }
    assert.ok(msg.includes("scope: project"));
    assert.ok(msg.includes("No directories were created"));

    // No config dir was created by detection.
    const entries = await readdir(sb.cwd);
    assert.deepEqual(entries, []);
  });
});

test("synthetic 6th AGENT_TARGETS row flows through detection/destination with no function edit", async () => {
  await withSandbox(async (sb) => {
    // A synthetic agent row (REQ-SCALE-01) — adding an agent is exactly a new table row.
    const fakeTarget = {
      id: "frobnik" as any,
      configDirName: ".frobnik",
      installBaseDir: ".frobnik",
      installSubpath: "skills",
      installKind: "skills" as const,
      skillFileForm: "SKILL.md",
      confidence: "best-known" as const,
      docsUrl: "https://example.test/frobnik",
    };

    // destinationFor is data-driven over the passed target row — no function edit needed.
    const dest = destinationFor(fakeTarget, "global", { home: sb.home });
    assert.equal(dest, join(sb.home, ".frobnik", "skills", "feature-forge"));

    // Inject the row into the runtime table so detectAgent (which derives over AGENT_TARGETS[id])
    // covers it with no logic change; remove it afterward so module state is untouched.
    const table = AGENT_TARGETS as unknown as Record<string, typeof fakeTarget>;
    table["frobnik"] = fakeTarget;
    try {
      await mkdir(join(sb.home, ".frobnik"), { recursive: true });
      const res = detectAgent("frobnik" as any, sb.resolve("global"));
      assert.equal(res.detected, true);
      assert.equal(res.configDirsProbed[0], join(sb.home, ".frobnik"));
      assert.equal(res.destination, join(sb.home, ".frobnik", "skills", "feature-forge"));
    } finally {
      delete table["frobnik"];
    }
  });
});
