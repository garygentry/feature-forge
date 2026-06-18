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
import { readFileSync, mkdtempSync, rmSync, symlinkSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  parseCliArgs,
  mapErrorToExit,
  helpText,
  main,
  SUBCOMMANDS,
  FLAGS,
} from "../dist/cli.js";
import { EXIT } from "../dist/types.js";
import type { RegistryQuery } from "../dist/rauf.js";
import { withSandbox, seedConfigDir } from "./helpers/sandbox.ts";
import { makeFixtureBundle } from "./helpers/fixtures.ts";
import { resolvableRegistry } from "./helpers/registry.ts";

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

// --- bin executability ------------------------------------------------------

test("dist/cli.js bin entry begins with a node shebang (npx / global-install executability)", () => {
  // Regression guard: without `#!/usr/bin/env node` the published bin is ENOEXEC on
  // Linux/macOS (the kernel falls back to /bin/sh, which chokes on the JS). tsc preserves
  // a leading shebang from cli.ts into the emit; this asserts it survives.
  const cli = readFileSync(new URL("../dist/cli.js", import.meta.url), "utf8");
  assert.equal(cli.split("\n", 1)[0], "#!/usr/bin/env node");
});

test("bin entry runs main() when invoked through a symlink (npx / `npm i -g` path)", () => {
  // Regression guard for the entry shim: npm/npx install the bin as a SYMLINK, so
  // process.argv[1] is the symlink while import.meta.url is the resolved real path. If the
  // shim compares them without resolving symlinks, main() silently no-ops (exit 0, no
  // output) under every real install path. Spawn the built bin through a symlink and assert
  // it actually executes (prints a version, exit 0) rather than no-op'ing.
  const cliPath = fileURLToPath(new URL("../dist/cli.js", import.meta.url));
  const dir = mkdtempSync(join(tmpdir(), "ff-bin-symlink-"));
  try {
    const link = join(dir, "feature-forge");
    symlinkSync(cliPath, link);
    const res = spawnSync(process.execPath, [link, "--version"], { encoding: "utf8" });
    assert.equal(res.status, 0);
    assert.match(res.stdout.trim(), /^\d+\.\d+\.\d+/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

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

// --- UNEXPECTED boundary: a thrown seam ⇒ exit 1 + one-line stderr, no stack (V-003) ---

test("main: an UNEXPECTED throw at the boundary ⇒ EXIT.FAILURE + one-line stderr, never a bare stack", async () => {
  await withSandbox(async (sb) => {
    // Seed a detected agent + bundle so the run reaches the rauf preflight (install, non-dry-run).
    await seedConfigDir(sb, "claude");
    await makeFixtureBundle(sb, "claude");

    // A registry that THROWS (not an err Result): preflightRauf calls it without catching, so the
    // exception propagates up through runCli to main's boundary catch — the UNEXPECTED path.
    const throwingRegistry: RegistryQuery = () => {
      throw new Error("seam exploded");
    };

    const { code, out, err } = await captureIO(() =>
      main(["install", "-a", "claude", "-y", "--source", sb.source], {
        home: sb.home,
        cwd: sb.cwd,
        registry: throwingRegistry,
      }),
    );

    assert.equal(code, EXIT.FAILURE, "unexpected throw maps to exit 1");
    assert.equal(out, "", "no report is rendered to stdout on the unexpected path");
    assert.ok(err.includes("seam exploded"), "the one-line message names the failure");
    // The hallmark of a Node stack frame is a line beginning with "    at ". The boundary message
    // must be a single actionable line, NEVER a bare stack (tech-spec §7).
    assert.ok(!err.includes("\n    at "), "stderr must not contain a stack frame");
    assert.equal(err.trim().split("\n").length, 1, "stderr is a single line");
  });
});

// --- exit-code triad through main: success→0, partial-failure→1, unknown-subcommand→2 (V-007) ---

test("main exit-code triad: success→0, partial-failure→1, unknown subcommand→2", async () => {
  await withSandbox(async (sb) => {
    // Leg 0 — success: install claude clean ⇒ EXIT.SUCCESS.
    await seedConfigDir(sb, "claude");
    await makeFixtureBundle(sb, "claude");
    {
      const { code } = await captureIO(() =>
        main(["install", "-a", "claude", "-y", "--source", sb.source], {
          home: sb.home,
          cwd: sb.cwd,
          registry: resolvableRegistry,
        }),
      );
      assert.equal(code, EXIT.SUCCESS, "clean install ⇒ exit 0");
    }

    // Leg 1 — partial failure: also seed gemini but leave its bundle absent ⇒ gemini fails,
    // claude succeeds, run exit is FAILURE (mirrors the e2e partial-failure setup).
    await seedConfigDir(sb, "gemini"); // gemini bundle deliberately NOT created
    {
      const { code } = await captureIO(() =>
        main(["install", "-y", "--source", sb.source], {
          home: sb.home,
          cwd: sb.cwd,
          registry: resolvableRegistry,
        }),
      );
      assert.equal(code, EXIT.FAILURE, "one agent failing ⇒ exit 1");
    }

    // Leg 2 — usage: an unknown subcommand ⇒ EXIT.USAGE.
    {
      const { code } = await captureIO(() => main(["frobnicate"]));
      assert.equal(code, EXIT.USAGE, "unknown subcommand ⇒ exit 2");
    }
  });
});

// --- non-interactivity proof: the built CLI reads no stdin (REQ-DIST-02, V-006) ---

test("the built CLI source contains no stdin/readline reference (non-interactive, REQ-DIST-02)", () => {
  const cliSrc = readFileSync(new URL("../dist/cli.js", import.meta.url), "utf8");
  assert.ok(!cliSrc.includes("process.stdin"), "built cli.js must not reference process.stdin");
  assert.ok(!/\breadline\b/.test(cliSrc), "built cli.js must not reference readline");
});
