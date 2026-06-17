/**
 * Unit tests for the CLI parse + dispatch boundary (spec 07, item 010). Covers alias
 * resolution, the USAGE rejections (unknown subcommand/flag/agent → exit 2), --help/--version
 * precedence, and the bare-invocation help-to-stderr path. The full hermetic e2e matrix
 * (install/update/uninstall/list against a sandbox) is item 011.
 *
 * Imports the built ../dist/cli.js (.js); no real `~`/network is touched.
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  parseCliArgs,
  mapErrorToExit,
  helpText,
  main,
  SUBCOMMANDS,
  FLAGS,
} from "../dist/cli.js";
import { EXIT } from "../dist/types.js";

/** Capture process.stdout/stderr writes for the duration of `fn`. */
async function captureIO(fn: () => Promise<number>): Promise<{ code: number; out: string; err: string }> {
  const origOut = process.stdout.write.bind(process.stdout);
  const origErr = process.stderr.write.bind(process.stderr);
  let out = "";
  let err = "";
  (process.stdout as { write: unknown }).write = (chunk: unknown) => {
    out += String(chunk);
    return true;
  };
  (process.stderr as { write: unknown }).write = (chunk: unknown) => {
    err += String(chunk);
    return true;
  };
  try {
    const code = await fn();
    return { code, out, err };
  } finally {
    (process.stdout as { write: unknown }).write = origOut;
    (process.stderr as { write: unknown }).write = origErr;
  }
}

// --- alias resolution -------------------------------------------------------

test("parseCliArgs resolves aliases add→install, remove→uninstall, ls→list", () => {
  for (const [alias, canonical] of [
    ["add", "install"],
    ["remove", "uninstall"],
    ["ls", "list"],
  ] as const) {
    const r = parseCliArgs([alias]);
    assert.ok(r.ok, `${alias} should parse ok`);
    assert.equal(r.value.subcommand, canonical);
  }
});

test("parseCliArgs accepts the canonical subcommands and normalizes flags", () => {
  const r = parseCliArgs(["install", "-a", "claude", "--global", "--dry-run", "--json"]);
  assert.ok(r.ok);
  assert.equal(r.value.subcommand, "install");
  assert.equal(r.value.flags.agent, "claude");
  assert.equal(r.value.flags.global, true);
  assert.equal(r.value.flags.dryRun, true);
  assert.equal(r.value.flags.json, true);
  assert.equal(r.value.flags.force, false);
});

// --- USAGE rejections → exit 2 ---------------------------------------------

test("unknown subcommand → USAGE, mapErrorToExit = EXIT.USAGE (2)", () => {
  const r = parseCliArgs(["frobnicate"]);
  assert.ok(!r.ok);
  assert.equal(r.error.code, "USAGE");
  assert.equal(mapErrorToExit(r.error), EXIT.USAGE);
});

test("unknown flag → USAGE (parseArgs throw caught)", () => {
  const r = parseCliArgs(["install", "--nope"]);
  assert.ok(!r.ok);
  assert.equal(r.error.code, "USAGE");
  assert.equal(mapErrorToExit(r.error), EXIT.USAGE);
});

test("unknown --agent → USAGE", () => {
  const r = parseCliArgs(["install", "-a", "vscode"]);
  assert.ok(!r.ok);
  assert.equal(r.error.code, "USAGE");
  assert.equal(mapErrorToExit(r.error), EXIT.USAGE);
});

test("missing subcommand (with no help/version) → USAGE", () => {
  const r = parseCliArgs([]);
  assert.ok(!r.ok);
  assert.equal(r.error.code, "USAGE");
});

test("mapErrorToExit maps every non-USAGE code to EXIT.FAILURE (1)", () => {
  for (const code of [
    "SOURCE_MISSING",
    "SOURCE_INVALID",
    "LOCALLY_MODIFIED",
    "WRITE_DENIED",
    "PATH_ESCAPE",
    "RAUF_UNRESOLVABLE",
    "MANIFEST_CORRUPT",
    "UNEXPECTED",
  ] as const) {
    assert.equal(mapErrorToExit({ code, message: "x" }), EXIT.FAILURE);
  }
  assert.equal(mapErrorToExit({ code: "USAGE", message: "x" }), EXIT.USAGE);
});

// --- helpText surface == parse surface -------------------------------------

test("helpText lists every non-hidden flag and subcommand and omits --source", () => {
  const h = helpText();
  for (const s of SUBCOMMANDS) assert.ok(h.includes(s.canonical), `help lists ${s.canonical}`);
  for (const f of FLAGS) {
    if (f.hidden) {
      assert.ok(!h.includes(`--${f.name}`), `help hides --${f.name}`);
    } else {
      assert.ok(h.includes(`--${f.name}`), `help lists --${f.name}`);
    }
  }
  // --yes is accepted and shown (REQ-DIST-02).
  assert.ok(h.includes("--yes"));
});

// --- main: help/version precedence + bare invocation -----------------------

test("main(['--help']) prints helpText to stdout and returns 0", async () => {
  const { code, out } = await captureIO(() => main(["--help"]));
  assert.equal(code, EXIT.SUCCESS);
  assert.ok(out.includes("cross-agent installer"));
  assert.ok(out.includes("COMMANDS:"));
});

test("main(['install','--help']) prints helpText and returns 0", async () => {
  const { code, out } = await captureIO(() => main(["install", "--help"]));
  assert.equal(code, EXIT.SUCCESS);
  assert.ok(out.includes("COMMANDS:"));
});

test("main([]) prints help to stderr and returns 2", async () => {
  const { code, out, err } = await captureIO(() => main([]));
  assert.equal(code, EXIT.USAGE);
  assert.equal(out, "");
  assert.ok(err.includes("no subcommand"));
  assert.ok(err.includes("COMMANDS:"));
});

test("main(['--version']) prints the package version and returns 0", async () => {
  const pkg = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8")) as {
    version: string;
  };
  const { code, out } = await captureIO(() => main(["--version"]));
  assert.equal(code, EXIT.SUCCESS);
  assert.equal(out.trim(), pkg.version);
});

test("main(['frobnicate']) prints the error + help to stderr and returns 2", async () => {
  const { code, out, err } = await captureIO(() => main(["frobnicate"]));
  assert.equal(code, EXIT.USAGE);
  assert.equal(out, "");
  assert.ok(err.includes("unknown subcommand"));
});
