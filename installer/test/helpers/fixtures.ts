/**
 * The fixture-bundle factory (spec 08 §3.2). Writes a minimal valid `<source>/<agent>/` bundle
 * that passes the integrity check (skills/ non-empty + scripts/forge-root.sh [+ gemini-extension.json
 * for gemini]) without copying the real (large) adapters tree.
 *
 * Reused by items 003, 005, 007, 008, 011. NOT a `.test.ts` file, so the test glob ignores it.
 */

import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import type { AgentId } from "../../dist/types.js";
import type { Sandbox } from "./sandbox.ts";

/** What was materialized, so tests can mutate/inspect individual files deterministically. */
export interface FixtureBundle {
  /** Absolute path of the bundle root: `<sb.source>/<agent>`. */
  readonly dir: string;
  /** The skill ids written (default: one skill "forge-1-prd"). */
  readonly skills: string[];
}

/**
 * Materialize a minimal valid `<source>/<agent>/` bundle that passes the integrity check
 * (skills/ non-empty + scripts/forge-root.sh [+ gemini-extension.json for gemini]). Mirrors the
 * verified ground-truth shape of the real adapters bundles (00 §6) at minimal size.
 *
 * @param sb     the sandbox whose `source` root receives the bundle
 * @param agent  which agent bundle to write
 * @param skills skill ids to include (default ["forge-1-prd"]); each becomes skills/<id>/SKILL.md
 */
export async function makeFixtureBundle(
  sb: Sandbox,
  agent: AgentId,
  skills: string[] = ["forge-1-prd"],
  /** Custom-agent ids to materialize as `agents/<id>.toml` (A4b codex mirror source). Default: none. */
  agents: string[] = [],
): Promise<FixtureBundle> {
  const dir = join(sb.source, agent);
  await mkdir(join(dir, "scripts"), { recursive: true });
  await writeFile(join(dir, "scripts", "forge-root.sh"), "#!/usr/bin/env bash\n# fixture\n");
  // The runtime helpers a skill can invoke — required of every bundle so helper-backed skills
  // run after install on any agent (BUNDLE_REQUIRED_PATHS.common).
  for (const helper of [
    "forge-init.sh",
    "epic-manifest.py",
    "validate-traceability.py",
    "forge-bootstrap.py",
  ]) {
    await writeFile(join(dir, "scripts", helper), `# fixture ${helper}\n`);
  }
  // The neutral cross-agent bundle sentinel.
  await writeFile(
    join(dir, ".feature-forge-bundle.json"),
    JSON.stringify({ name: "feature-forge", version: "0.0.0", agent, generatedBy: "test-fixture" }, null, 2) + "\n",
  );
  for (const id of skills) {
    await mkdir(join(dir, "skills", id), { recursive: true });
    await writeFile(join(dir, "skills", id, "SKILL.md"), `# ${id}\nfixture skill body\n`);
  }
  if (agent === "gemini") {
    const ext = { name: "feature-forge", version: "0.0.0", skills: skills.map((name) => ({ name })) };
    await writeFile(join(dir, "gemini-extension.json"), JSON.stringify(ext, null, 2) + "\n");
  }
  if (agent === "pi") {
    // The real bundle ships the extension as a vendored tree, not one file.
    await mkdir(join(dir, "extensions", "ask-user-question"), { recursive: true });
    await writeFile(join(dir, "extensions", "ask-user-question", "index.ts"), "export default {};\n");
    await writeFile(
      join(dir, "package.json"),
      JSON.stringify({ name: "feature-forge-pi", keywords: ["pi-package"], pi: { skills: ["./skills"], extensions: ["./extensions/ask-user-question/index.ts"] } }, null, 2) + "\n",
    );
  }
  // Custom-agent source files for a "mirror" placement. codex loads `.toml`, pi loads `.md`;
  // the mirror itself selects by path prefix, agnostic to extension.
  const agentExt = agent === "pi" ? "md" : "toml";
  for (const id of agents) {
    await mkdir(join(dir, "agents"), { recursive: true });
    await writeFile(join(dir, "agents", `${id}.${agentExt}`), `name = "${id}"\n# fixture custom agent\n`);
  }
  return { dir, skills };
}
