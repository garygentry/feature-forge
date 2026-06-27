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
  selectMirrorFiles,
  renderCopilotBlock,
  wrapBlock,
  upsertBlock,
  removeBlock,
  extractManagedRegion,
} from "../dist/placements.js";

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

test("resolvePlacements: copilot managed-block targets .github/copilot-instructions.md", () => {
  const r = resolvePlacements(AGENT_TARGETS.copilot, "project", opts);
  assert.equal(r.length, 1);
  assert.equal(r[0]!.kind, "managed-block");
  assert.equal(r[0]!.root, "/p/.github");
  assert.equal(r[0]!.destination, "/p/.github/copilot-instructions.md");
});

test("resolvePlacements: agents without a rule return []", () => {
  for (const id of ["claude", "cursor", "gemini"] as const) {
    assert.deepEqual(resolvePlacements(AGENT_TARGETS[id], "project", opts), []);
  }
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
