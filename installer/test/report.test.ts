/**
 * Tests for report.ts (spec 07 §3.5/§3.6): renderReport({json}) round-trips to a RunReport;
 * the human form names path + remedy on a failure; the list line decodes the synthetic status
 * rows; every actionVerb branch is covered; formatError falls back to DEFAULT_REMEDY.
 *
 * Imports the built artifact (../dist/report.js) per the type-stripping import rule (item 002).
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { renderReport, formatError, actionVerb } from "../dist/report.js";
import type {
  AgentReport,
  FileActionKind,
  InstallerError,
  RunReport,
} from "../dist/types.js";

/** A representative install RunReport with one ok agent (per-file actions) and one failed agent. */
function sampleReport(): RunReport {
  const ok: AgentReport = {
    agent: "claude",
    detected: true,
    ok: true,
    actions: [
      { relpath: "skills/forge-1-prd/SKILL.md", action: "create" },
      { relpath: "skills/forge-2-tech/SKILL.md", action: "unchanged" },
    ],
    raufPin: "@garygentry/rauf@0.11.0",
  };
  const bad: AgentReport = {
    agent: "codex",
    detected: true,
    ok: false,
    actions: [],
    error: {
      code: "WRITE_DENIED",
      message: "no write permission",
      agent: "codex",
      path: "/sandbox/.codex/skills/feature-forge",
    },
  };
  return {
    subcommand: "install",
    scope: "project",
    mode: "copy",
    dryRun: true,
    agents: [ok, bad],
    exitCode: 1,
  };
}

test("renderReport({json:true}) round-trips deep-equal to the RunReport", () => {
  const report = sampleReport();
  const json = renderReport(report, { json: true });
  const parsed = JSON.parse(json);
  assert.deepEqual(parsed, report);
});

test("human form has header, per-agent ok/FAILED blocks, action verbs, and summary", () => {
  const report = sampleReport();
  const text = renderReport(report, { json: false });
  const lines = text.split("\n");

  assert.equal(lines[0], "install (project, copy) — dry-run");
  assert.ok(text.includes("claude: ok"));
  assert.ok(text.includes(`  ${actionVerb("create")} skills/forge-1-prd/SKILL.md`));
  assert.ok(text.includes(`  ${actionVerb("unchanged")} skills/forge-2-tech/SKILL.md`));
  assert.ok(text.includes("rauf default runner pinned: @garygentry/rauf@0.11.0"));
  assert.ok(text.includes("codex: FAILED — WRITE_DENIED"));
  assert.ok(text.includes("Summary: 1 ok, 1 failed (exit 1)"));
});

test("a failed agent line names the path and a DEFAULT_REMEDY fallback remedy", () => {
  const report = sampleReport();
  const text = renderReport(report, { json: false });
  // path comes from the error; remedy from DEFAULT_REMEDY[WRITE_DENIED] since error.remedy is absent.
  assert.ok(text.includes("path: /sandbox/.codex/skills/feature-forge"));
  assert.ok(text.includes("remedy: check write permission to the path"));
});

test("formatError prefers the error's own remedy when present", () => {
  const e: InstallerError = {
    code: "SOURCE_MISSING",
    message: "bundle not found",
    path: "/x/adapters/claude",
    remedy: "do the specific thing",
  };
  const line = formatError(e);
  assert.equal(line, "bundle not found — path: /x/adapters/claude — remedy: do the specific thing");
});

test("formatError falls back to the per-code DEFAULT_REMEDY when remedy is absent", () => {
  const e: InstallerError = {
    code: "MANIFEST_CORRUPT",
    message: "bad json",
    path: "/x/.feature-forge.project.json",
  };
  const line = formatError(e);
  assert.ok(line.startsWith("bad json — path: /x/.feature-forge.project.json — remedy: "));
  assert.ok(line.includes("remove the corrupt"));
});

test("formatError omits path/remedy sections when neither is available", () => {
  const e: InstallerError = { code: "UNEXPECTED", message: "boom" };
  assert.equal(formatError(e), "boom");
});

test("list subcommand decodes the synthetic status rows into one line", () => {
  const report: RunReport = {
    subcommand: "list",
    scope: "global",
    mode: "copy",
    dryRun: false,
    agents: [
      {
        agent: "claude",
        detected: true,
        ok: true,
        actions: [
          { relpath: "detected:true", action: "unchanged" },
          { relpath: "installed:true", action: "unchanged" },
          { relpath: "up-to-date:false", action: "unchanged" },
        ],
        raufPin: "@garygentry/rauf@0.11.0",
      },
      {
        agent: "cursor",
        detected: false,
        ok: true,
        actions: [
          { relpath: "detected:false", action: "unchanged" },
          { relpath: "installed:false", action: "unchanged" },
        ],
      },
    ],
    exitCode: 0,
  };
  const text = renderReport(report, { json: false });
  assert.ok(
    text.includes("claude: detected  detected:true  installed:true  up-to-date:false"),
  );
  assert.ok(text.includes("cursor: not detected  detected:false  installed:false"));
  assert.ok(text.includes("Summary: 2 ok, 0 failed (exit 0)"));
});

test("actionVerb covers every FileActionKind branch", () => {
  const kinds: FileActionKind[] = [
    "create",
    "overwrite",
    "skip-modified",
    "unchanged",
    "remove",
  ];
  for (const k of kinds) {
    const v = actionVerb(k);
    assert.equal(typeof v, "string");
    assert.ok(v.length > 0);
  }
  // Distinct, recognizable verbs.
  assert.ok(actionVerb("create").trim() === "create");
  assert.ok(actionVerb("overwrite").trim() === "overwrite");
  assert.ok(actionVerb("skip-modified").trim() === "skip");
  assert.ok(actionVerb("unchanged").trim() === "unchanged");
  assert.ok(actionVerb("remove").trim() === "remove");
});

// --------------------------------------------------------------------------- //
// A4: honest confidence labeling (Finding 6)
// --------------------------------------------------------------------------- //

test("A4: human report shows a best-known note with docs URL, and stays silent for confirmed", () => {
  const report: RunReport = {
    subcommand: "install",
    scope: "project",
    mode: "copy",
    dryRun: true,
    exitCode: 0,
    agents: [
      {
        agent: "copilot",
        detected: true,
        ok: true,
        actions: [{ relpath: "skills/forge-1-prd/forge-1-prd.md", action: "create" }],
        confidence: "best-known",
        docsUrl: "https://docs.github.com/copilot",
      },
      {
        agent: "claude",
        detected: true,
        ok: true,
        actions: [{ relpath: "skills/forge-1-prd/SKILL.md", action: "create" }],
        confidence: "confirmed",
        docsUrl: "https://docs.claude.com/skills",
      },
    ],
  };
  const text = renderReport(report, { json: false });
  assert.ok(text.includes("copilot install path is best-known"));
  assert.ok(text.includes("https://docs.github.com/copilot"));
  // No note for a confirmed agent.
  assert.ok(!text.includes("claude install path is best-known"));
});

test("A4: confidence + docsUrl ride the --json machine surface", () => {
  const report: RunReport = {
    subcommand: "list",
    scope: "global",
    mode: "copy",
    dryRun: false,
    exitCode: 0,
    agents: [
      {
        agent: "gemini",
        detected: false,
        ok: true,
        actions: [{ relpath: "detected:false", action: "unchanged" }],
        confidence: "verified-current",
        docsUrl: "https://example.test/gemini",
      },
    ],
  };
  const parsed = JSON.parse(renderReport(report, { json: true })) as RunReport;
  assert.equal(parsed.agents[0]!.confidence, "verified-current");
  assert.equal(parsed.agents[0]!.docsUrl, "https://example.test/gemini");
});
