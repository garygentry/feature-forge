/**
 * A4b secondary-placement tests: the pure `placements` helpers (resolve, mirror selection, managed-
 * block string transforms) plus the planner's per-kind diff. End-to-end apply/uninstall behavior for
 * codex (`.codex/agents`) and copilot (`.github/copilot-instructions.md`) lives in
 * e2e-placements.test.ts. Hermetic — no real `~`, no network.
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { AGENT_TARGETS } from "../dist/types.js";
import {
  resolvePlacements,
  resolveLegacyCopilotBlock,
  selectMirrorFiles,
  renderCopilotBlock,
  wrapBlock,
  upsertBlock,
  removeBlock,
  extractManagedRegion,
} from "../dist/placements.js";
import { planInstall } from "../dist/plan.js";

const opts = { home: "/h", cwd: "/p" };

test("resolvePlacements: codex mirror resolves to .codex/agents under the scope root", () => {
  const project = resolvePlacements(AGENT_TARGETS.codex, "project", opts);
  assert.equal(project.length, 1);
  assert.equal(project[0]!.kind, "mirror");
  assert.equal(project[0]!.root, "/p/.codex");
  assert.equal(project[0]!.destination, "/p/.codex/agents");

  const global = resolvePlacements(AGENT_TARGETS.codex, "global", opts);
  assert.equal(global[0]!.root, "/h/.codex");
  assert.equal(global[0]!.destination, "/h/.codex/agents");
});

test("resolvePlacements: fresh copilot uses only native mirrors; legacy block is cleanup-only", () => {
  const project = resolvePlacements(AGENT_TARGETS.copilot, "project", opts);
  assert.deepEqual(
    project.map((p) => [p.kind, p.root, p.destination]),
    [
      ["mirror", "/p/.github", "/p/.github/skills"],
      ["mirror", "/p/.github", "/p/.github/agents"],
    ],
  );

  const global = resolvePlacements(AGENT_TARGETS.copilot, "global", opts);
  assert.deepEqual(
    global.map((p) => [p.kind, p.root, p.destination]),
    [
      ["mirror", "/h/.copilot", "/h/.copilot/skills"],
      ["mirror", "/h/.copilot", "/h/.copilot/agents"],
    ],
  );
  assert.equal(resolveLegacyCopilotBlock("project", opts).destination, "/p/.github/copilot-instructions.md");
  assert.equal(resolveLegacyCopilotBlock("global", opts).destination, "/h/.github/copilot-instructions.md");
});

test("resolvePlacements: agents without a rule return []", () => {
  for (const id of ["claude", "cursor", "gemini"] as const) {
    assert.deepEqual(resolvePlacements(AGENT_TARGETS[id], "project", opts), []);
  }
});

test("resolvePlacements: pi mirror uses a scope-aware second root (.pi/agent global, .pi project)", () => {
  // pi-subagents scans ~/.pi/agent/agents at user scope but <root>/.pi/agents at project scope —
  // one baseDir string can't express both, hence globalBaseDir/projectBaseDir on the spec.
  const global = resolvePlacements(AGENT_TARGETS.pi, "global", opts);
  assert.equal(global.length, 1);
  assert.equal(global[0]!.kind, "mirror");
  assert.equal(global[0]!.root, "/h/.pi/agent");
  assert.equal(global[0]!.destination, "/h/.pi/agent/agents");

  const project = resolvePlacements(AGENT_TARGETS.pi, "project", opts);
  assert.equal(project[0]!.root, "/p/.pi");
  assert.equal(project[0]!.destination, "/p/.pi/agents");
});

test("selectMirrorFiles: picks agents/* flat, sorted, ignores non-prefixed", () => {
  const source = {
    root: "/src",
    sourceHash: "x",
    skills: [],
    files: [
      { relpath: "agents/forge-verifier.toml", sha256: "v" },
      { relpath: "agents/forge-researcher.toml", sha256: "r" },
      { relpath: "skills/forge-1-prd/SKILL.md", sha256: "s" },
      { relpath: "scripts/forge-root.sh", sha256: "h" },
    ],
  };
  const mirror = selectMirrorFiles(source as never, AGENT_TARGETS.codex.placements![0]!);
  assert.deepEqual(
    mirror.map((m) => m.destRelpath),
    ["forge-researcher.toml", "forge-verifier.toml"],
  );
  assert.equal(mirror[0]!.srcRelpath, "agents/forge-researcher.toml");
  assert.equal(mirror[0]!.srcHash, "r");
});

test("placement planning rejects an escaping destination before reading or writing it", () => {
  const target = {
    ...AGENT_TARGETS.codex,
    placements: [{
      kind: "mirror" as const,
      baseDir: ".codex",
      subpath: "../../escape",
      sourcePrefix: "agents/",
    }],
  };
  const placements = resolvePlacements(target, "project", opts);
  const result = planInstall({
    agent: "codex",
    scope: "project",
    mode: "copy",
    destination: "/p/.agents/skills/feature-forge",
    source: {
      root: "/src",
      sourceHash: "x",
      skills: ["forge"],
      files: [{ relpath: "agents/forge.toml", sha256: "a" }],
    },
    priorManifest: null,
    force: false,
    placements,
  });
  assert.ok(!result.ok);
  assert.equal(result.error.code, "PATH_ESCAPE");
});

test("selectMirrorFiles: recursive mirrors preserve paths below sourcePrefix", () => {
  const source = {
    root: "/src",
    sourceHash: "x",
    skills: ["forge-1-prd", "forge-2-tech"],
    files: [
      { relpath: "skills/forge-2-tech/SKILL.md", sha256: "two" },
      { relpath: "skills/forge-1-prd/references/example.md", sha256: "ref" },
      { relpath: "skills/forge-1-prd/SKILL.md", sha256: "one" },
      { relpath: "agents/forge-verifier.agent.md", sha256: "agent" },
    ],
  };
  const spec = {
    kind: "mirror" as const,
    baseDir: ".github",
    subpath: "skills",
    sourcePrefix: "skills/",
    mirrorLayout: "recursive" as const,
  };

  const mirror = selectMirrorFiles(source as never, spec);
  assert.deepEqual(
    mirror.map((m) => [m.srcRelpath, m.destRelpath]),
    [
      ["skills/forge-1-prd/SKILL.md", "forge-1-prd/SKILL.md"],
      ["skills/forge-1-prd/references/example.md", "forge-1-prd/references/example.md"],
      ["skills/forge-2-tech/SKILL.md", "forge-2-tech/SKILL.md"],
    ],
  );
});

test("renderCopilotBlock: deterministic, lists sorted skills, points at .github/feature-forge", () => {
  const a = renderCopilotBlock(["forge-2-tech", "forge-1-prd"]);
  const b = renderCopilotBlock(["forge-2-tech", "forge-1-prd"]);
  assert.equal(a, b);
  assert.match(a, /\.github\/feature-forge/);
  assert.ok(a.indexOf("- forge-1-prd") < a.indexOf("- forge-2-tech"));
});

test("upsertBlock: into empty content yields just the wrapped block + trailing newline", () => {
  const body = renderCopilotBlock(["forge-1-prd"]);
  const out = upsertBlock("", body);
  assert.equal(out, wrapBlock(body) + "\n");
  assert.equal(extractManagedRegion(out), wrapBlock(body));
});

test("upsertBlock: appends after user content, preserving it", () => {
  const body = renderCopilotBlock(["forge-1-prd"]);
  const out = upsertBlock("# My repo rules\n\nBe nice.\n", body);
  assert.match(out, /^# My repo rules/);
  assert.match(out, /Be nice\./);
  assert.equal(extractManagedRegion(out), wrapBlock(body));
});

test("upsertBlock: replaces an existing block in place, leaving surrounding content", () => {
  const v1 = renderCopilotBlock(["forge-1-prd"]);
  const withUser = upsertBlock("intro\n", v1);
  const v2 = renderCopilotBlock(["forge-1-prd", "forge-2-tech"]);
  const out = upsertBlock(withUser, v2);
  assert.match(out, /^intro/);
  assert.equal(extractManagedRegion(out), wrapBlock(v2));
  // exactly one managed region remains
  assert.equal(out.indexOf("feature-forge:managed:start"), out.lastIndexOf("feature-forge:managed:start"));
});

test("removeBlock: strips the block but keeps user content", () => {
  const body = renderCopilotBlock(["forge-1-prd"]);
  const full = upsertBlock("# rules\n\nstuff\n", body);
  const out = removeBlock(full);
  assert.doesNotMatch(out, /feature-forge:managed/);
  assert.match(out, /# rules/);
  assert.match(out, /stuff/);
});

test("removeBlock: returns '' when only the block (and whitespace) remained", () => {
  const body = renderCopilotBlock(["forge-1-prd"]);
  assert.equal(removeBlock(upsertBlock("", body)), "");
});

test("extractManagedRegion: null when no well-formed region", () => {
  assert.equal(extractManagedRegion("nothing here"), null);
  assert.equal(extractManagedRegion("<!-- feature-forge:managed:start -->\nno end"), null);
});
