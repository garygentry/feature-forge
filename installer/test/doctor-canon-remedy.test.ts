/**
 * Cross-check (#314/#338): doctor's canon-root remedy (`_CANON_ROOT_REMEDY` in
 * scripts/forge_session/doctor.py) tells the user what `npx @garygentry/feature-forge install`
 * writes (#283/#317 remedy truthfulness). Derived here from the installer's own typed contract —
 * `manifestPath` and `resolvePlacements` over every `AGENT_TARGETS` entry, both scopes — so a new
 * or moved installer write fails this test until the remedy names it. Hermetic: fake home/cwd.
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { AGENT_IDS, AGENT_TARGETS, MANIFEST_PREFIX } from "../dist/types.js";
import { destinationFor } from "../dist/agent-targets.js";
import { manifestPath } from "../dist/manifest.js";
import { resolvePlacements } from "../dist/placements.js";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const HOME = "/fake-home";
const CWD = "/fake-project";
const SCOPES = ["global", "project"] as const;

function npxClause(): string {
  const res = spawnSync(
    "python3",
    ["-c", "import sys; sys.path.insert(0, 'scripts'); "
      + "from forge_session.doctor import _CANON_ROOT_REMEDY as r; print(r)"],
    { cwd: REPO_ROOT, encoding: "utf8" },
  );
  assert.equal(res.status, 0, res.stderr);
  const remedy = res.stdout;
  const start = remedy.indexOf("npx @garygentry/feature-forge install");
  const end = remedy.indexOf("Source dogfood");
  assert.ok(start >= 0 && end > start, "remedy lost its npx clause");
  return remedy.slice(start, end);
}

/** How the remedy spells a path: project-relative, or `~/`-prefixed under the fake home. */
function spelled(scope: (typeof SCOPES)[number], abs: string): string {
  return scope === "global" ? `~/${path.relative(HOME, abs)}` : path.relative(CWD, abs);
}

test("remedy names the sibling scope manifest the installer writes", () => {
  const clause = npxClause();
  assert.ok(clause.includes(`${MANIFEST_PREFIX}<scope>.json`), clause);
  assert.ok(clause.includes("sibling"), clause);
  for (const agent of AGENT_IDS) {
    for (const scope of SCOPES) {
      const opts = { home: HOME, cwd: CWD };
      const manifest = manifestPath(agent, scope, opts);
      const bundle = destinationFor(AGENT_TARGETS[agent], scope, opts);
      assert.equal(path.basename(manifest), `${MANIFEST_PREFIX}${scope}.json`);
      assert.equal(path.dirname(manifest), path.dirname(bundle), `${agent}/${scope}: not a sibling`);
    }
  }
});

test("remedy names every secondary placement, in each scope's spelling", () => {
  const clause = npxClause();
  let seen = 0;
  for (const agent of AGENT_IDS) {
    for (const scope of SCOPES) {
      for (const p of resolvePlacements(AGENT_TARGETS[agent], scope, { home: HOME, cwd: CWD })) {
        seen += 1;
        const project = path.relative(scope === "global" ? HOME : CWD, p.destination);
        // A scope-invariant placement is named once, scope-relative (the clause says the root is
        // the project or ~); a placement whose global root differs must be spelled out as ~/…
        const want = scope === "global" && project !== spelledProject(agent, p.spec)
          ? spelled(scope, p.destination)
          : project;
        assert.ok(clause.includes(want), `${agent}/${scope}: remedy omits ${want}\n${clause}`);
      }
    }
  }
  assert.ok(seen > 0, "no placements resolved — contract changed shape");
});

function spelledProject(agent: (typeof AGENT_IDS)[number], spec: unknown): string {
  const p = resolvePlacements(AGENT_TARGETS[agent], "project", { home: HOME, cwd: CWD })
    .find((r) => r.spec === spec);
  assert.ok(p, `${agent}: placement has no project-scope counterpart`);
  return path.relative(CWD, p.destination);
}
