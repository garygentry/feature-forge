/**
 * Codex Stop-hook wiring (#346): consent, decline, idempotency, and never without consent.
 * Hermetic: the hook file resolves under the sandbox HOME (`<home>/.codex/hooks.json`).
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdir, readFile, writeFile, stat } from "node:fs/promises";
import { join } from "node:path";
import { EXIT } from "../dist/types.js";
import { CODEX_STOP_HOOK_COMMAND, hooksFeatureEnabled, wireCodexStopHook } from "../dist/codex-hook.js";
import { withSandbox, seedConfigDir, type Sandbox } from "./helpers/sandbox.ts";
import { makeFixtureBundle } from "./helpers/fixtures.ts";
import { runCli2 } from "./helpers/run.ts";

const exists = (p: string) => stat(p).then(() => true, () => false);
const hooksPath = (sb: Sandbox) => join(sb.home, ".codex", "hooks.json");

async function codexSandbox(sb: Sandbox): Promise<void> {
  await makeFixtureBundle(sb, "codex", ["forge-1-prd"], ["forge-verifier"]);
  await seedConfigDir(sb, "codex");
}

function stopCommands(doc: { hooks?: { Stop?: { hooks: { command: string }[] }[] } }): string[] {
  return (doc.hooks?.Stop ?? []).flatMap((g) => g.hooks.map((h) => h.command));
}

test("--codex-stop-hook wires the hook, keeping existing hooks", async () => {
  await withSandbox(async (sb) => {
    await codexSandbox(sb);
    await mkdir(join(sb.home, ".codex"), { recursive: true });
    const existing = { hooks: { SessionStart: [{ hooks: [{ type: "command", command: "echo hi" }] }] } };
    await writeFile(hooksPath(sb), JSON.stringify(existing));

    const r = await runCli2(["install", "-a", "codex", "--source", sb.source, "--codex-stop-hook"], sb);
    assert.equal(r.exitCode, EXIT.SUCCESS);
    assert.equal(r.codexStopHook?.status, "wired");

    const doc = JSON.parse(await readFile(hooksPath(sb), "utf8"));
    assert.deepEqual(stopCommands(doc), [CODEX_STOP_HOOK_COMMAND]);
    assert.deepEqual(doc.hooks.SessionStart, existing.hooks.SessionStart);
  });
});

test("without --codex-stop-hook nothing is written; the report says how to opt in", async () => {
  await withSandbox(async (sb) => {
    await codexSandbox(sb);
    const r = await runCli2(["install", "-a", "codex", "--source", sb.source], sb);
    assert.equal(r.codexStopHook?.status, "not-offered");
    assert.match(r.codexStopHook?.message ?? "", /--codex-stop-hook/);
    assert.equal(await exists(hooksPath(sb)), false);
  });
});

test("idempotent: an already-wired file is not rewritten", async () => {
  await withSandbox(async (sb) => {
    await codexSandbox(sb);
    await runCli2(["install", "-a", "codex", "--source", sb.source, "--codex-stop-hook"], sb);
    const before = await readFile(hooksPath(sb), "utf8");
    const again = await runCli2(["update", "-a", "codex", "--source", sb.source, "--codex-stop-hook"], sb);
    assert.equal(again.codexStopHook?.status, "already-wired");
    assert.equal(await readFile(hooksPath(sb), "utf8"), before);
    assert.deepEqual(stopCommands(JSON.parse(before)), [CODEX_STOP_HOOK_COMMAND]);
  });
});

test("--yes alone, --dry-run, and non-codex installs never write it", async () => {
  await withSandbox(async (sb) => {
    await codexSandbox(sb);
    const yes = await runCli2(["install", "-a", "codex", "--source", sb.source, "--yes"], sb);
    assert.equal(yes.codexStopHook?.status, "not-offered");
    const dry = await runCli2(["install", "-a", "codex", "--source", sb.source, "--dry-run", "--codex-stop-hook"], sb);
    assert.equal(dry.codexStopHook, undefined);
    assert.equal(await exists(hooksPath(sb)), false);
  });
  await withSandbox(async (sb) => {
    await makeFixtureBundle(sb, "claude", ["forge-1-prd"]);
    await seedConfigDir(sb, "claude");
    const r = await runCli2(["install", "-a", "claude", "--source", sb.source, "--codex-stop-hook"], sb);
    assert.equal(r.codexStopHook, undefined);
    assert.equal(await exists(hooksPath(sb)), false);
  });
});

test("a requested hook that cannot be written fails the run; unrequested, the bad file is named", async () => {
  await withSandbox(async (sb) => {
    await codexSandbox(sb);
    await mkdir(join(sb.home, ".codex"), { recursive: true });
    await writeFile(hooksPath(sb), "{not json");
    const plain = await runCli2(["install", "-a", "codex", "--source", sb.source], sb);
    assert.equal(plain.exitCode, EXIT.SUCCESS);
    assert.equal(plain.codexStopHook?.status, "not-offered");
    assert.match(plain.codexStopHook?.message ?? "", /not valid JSON/);

    const flagged = await runCli2(["update", "-a", "codex", "--source", sb.source, "--codex-stop-hook"], sb);
    assert.equal(flagged.codexStopHook?.status, "failed");
    assert.equal(flagged.exitCode, EXIT.FAILURE);
    assert.equal(await readFile(hooksPath(sb), "utf8"), "{not json");
  });
});

test("a malformed hooks.json is reported, never overwritten", async () => {
  await withSandbox(async (sb) => {
    await mkdir(join(sb.home, ".codex"), { recursive: true });
    await writeFile(hooksPath(sb), "{not json");
    const r = wireCodexStopHook(join(sb.home, ".codex"));
    assert.equal(r.status, "failed");
    assert.equal(await readFile(hooksPath(sb), "utf8"), "{not json");
  });
});

test("hooksFeatureEnabled reads [features] hooks = true from config.toml", async () => {
  await withSandbox(async (sb) => {
    const home = join(sb.home, ".codex");
    await mkdir(home, { recursive: true });
    assert.equal(hooksFeatureEnabled(home), false);
    await writeFile(join(home, "config.toml"), 'model = "x"\n\n[features]\nhooks = true\n\n[other]\nhooks = false\n');
    assert.equal(hooksFeatureEnabled(home), true);
    await writeFile(join(home, "config.toml"), "[features]\nfoo = 1\n[x]\nhooks = true\n");
    assert.equal(hooksFeatureEnabled(home), false);
  });
});
