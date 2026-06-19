/**
 * Rauf provisioning (spec 06): the single pinned rauf coordinate (`RAUF_PIN`), the
 * install-time read-only resolvability preflight, the `--skip-rauf` short-circuit, and the
 * fixed unavailable-pin failure mode.
 *
 * Scope: this module makes rauf the *provisioned default* loop runner by recording a pin and
 * preflighting its resolvability — it never vendors a binary, never mutates global npm state,
 * never invokes rauf, and performs NO filesystem write. The only side effect is the read-only
 * `npm view` registry query in the default registry query (skipped when `opts.skip` or an
 * injected query is used). Named exports only; zero runtime dependencies (only `node:`
 * built-ins). No throw for expected errors — returns `Result<T, E>` from `00-core-definitions`.
 */

import { spawnSync } from "node:child_process";
import { err, ok, type InstallerError, type Result } from "./types.js";

/**
 * The single pinned rauf coordinate the install provisions as the default loop runner
 * (REQ-RAUF-03). One source of truth: re-exported by `src/index.ts` so importers and the
 * downstream `forge-rauf-loop-default` read the same value, and recorded into each manifest
 * as `InstallManifest.raufPin` (05-manifest-and-uninstall.md).
 *
 * Shape: `<name>@<version>` — the SCOPED package `@garygentry/rauf` (the unscoped `rauf` name is
 * blocked by npm's similarity filter). Advanced on each feature-forge release to a new
 * known-compatible rauf (REQ-RAUF-03). The current rauf version is 0.8.0.
 *
 * rauf is now PUBLISHED (rauf#28): `@garygentry/rauf@0.8.0` resolves from the npm registry, so the
 * preflight below passes by default. (Historically this pin pointed at an unpublished package and
 * the preflight was a designed-to-fail check — see the `--skip-rauf` escape hatch.)
 */
export const RAUF_PIN = "@garygentry/rauf@0.8.0";

/**
 * An injectable, READ-ONLY registry query (D1). Given a coordinate `name@version`, returns the
 * resolved version string on success, or an `InstallerError` if it is not resolvable.
 *
 * Injectable so tests mock the registry with NO real network: the default implementation
 * (`defaultRegistryQuery`) shells `npm view <coordinate> version`; a test passes a stub
 * returning `ok("0.7.0")` or `err({ code: "RAUF_UNRESOLVABLE", ... })`.
 *
 * Contract: the query MUST be read-only — it MUST NOT install, MUST NOT mutate global npm
 * state, and MUST NOT execute rauf. `npm view` satisfies this (it only reads registry metadata).
 *
 * @param coordinate - the `name@version` to resolve, e.g. "@garygentry/rauf@0.8.0"
 * @returns Result<string> — the resolved version on success; RAUF_UNRESOLVABLE on failure.
 */
export type RegistryQuery = (coordinate: string) => Result<string>;

/** Options for the rauf preflight. */
export interface PreflightRaufOpts {
  /**
   * When true (the `--skip-rauf` flag), skip the preflight entirely: perform NO network call
   * and return `{ raufPin: null }`. For environments that knowingly defer rauf (e.g. offline
   * installs or CI dry-runs that won't use the default loop).
   */
  readonly skip?: boolean;
  /**
   * The registry query to use. Default: `defaultRegistryQuery` (`npm view <RAUF_PIN> version`
   * via node:child_process). Tests inject a stub so no real network call is made.
   */
  readonly query?: RegistryQuery;
}

/**
 * Resolvability preflight for the pinned default loop runner (D1; REQ-RAUF-01/02/03, OQ-1).
 *
 * Behavior:
 *  - `opts.skip` (the `--skip-rauf` flag) ⇒ return `ok({ raufPin: null })` immediately, with NO
 *    network call.
 *  - otherwise ⇒ run a READ-ONLY registry resolvability check on `RAUF_PIN` (default query:
 *    `npm view <RAUF_PIN> version`). No install, no global-npm mutation, no execution of rauf.
 *      · resolvable  ⇒ return `ok({ raufPin: RAUF_PIN })` — the value the manifest records.
 *      · unresolvable ⇒ return `err(<RAUF_UNRESOLVABLE>)` carrying the FIXED message (§6).
 *
 * NEVER throws for the expected unresolvable case — that is an `err(...)`. An unexpected spawn
 * failure inside the default query is normalized to the same `RAUF_UNRESOLVABLE` error, so
 * callers handle one code. Performs no filesystem write.
 *
 * @param opts - skip flag and/or an injected registry query (tests)
 * @returns Result<{ raufPin: string | null }>:
 *          ok + `raufPin: RAUF_PIN`  when resolvable,
 *          ok + `raufPin: null`      when skipped,
 *          err(RAUF_UNRESOLVABLE)    when the pin is not resolvable.
 */
export function preflightRauf(
  opts?: { skip?: boolean; query?: RegistryQuery },
): Result<{ raufPin: string | null }> {
  // --skip-rauf: no network, record null.
  if (opts?.skip) {
    return ok({ raufPin: null });
  }

  const query: RegistryQuery = opts?.query ?? defaultRegistryQuery;
  const resolved = query(RAUF_PIN);

  if (resolved.ok) {
    // Resolvable: record the pin. (We deliberately ignore the resolved version string — the
    // recorded coordinate is RAUF_PIN itself, the single source of truth, REQ-RAUF-03.)
    return ok({ raufPin: RAUF_PIN });
  }

  // Unresolvable: the designed failure mode (§6). Surface the FIXED, actionable error,
  // regardless of any message the injected query returned.
  return err(raufUnresolvableError());
}

/**
 * Internal: the default read-only registry query. Runs `npm view <coordinate> version` via
 * `node:child_process.spawnSync` — registry metadata read ONLY (no install, no global mutation,
 * no rauf execution). Network is permitted at install (C-7).
 *
 * Resolution rule:
 *  - exit code 0 AND non-empty stdout ⇒ ok(trimmed stdout) (the resolved version).
 *  - anything else (non-zero exit, E404, a spawn error, npm absent) ⇒ err(RAUF_UNRESOLVABLE).
 *
 * NOT exported as public API — `preflightRauf`'s `query` option is the seam tests use.
 */
function defaultRegistryQuery(coordinate: string): Result<string> {
  let res: ReturnType<typeof spawnSync>;
  try {
    res = spawnSync("npm", ["view", coordinate, "version"], {
      encoding: "utf8",
      // No shell; argv form avoids injection. Timeout bounds a hung registry.
      timeout: 30_000,
      windowsHide: true,
    });
  } catch {
    // spawn itself threw (e.g. npm not found on some platforms) — treat as unresolvable.
    return err(raufUnresolvableError());
  }

  if (res.error || res.status !== 0) {
    return err(raufUnresolvableError());
  }
  const version = String(res.stdout ?? "").trim();
  if (version.length === 0) {
    return err(raufUnresolvableError());
  }
  return ok(version);
}

/**
 * Internal: builds the structured RAUF_UNRESOLVABLE error with the FIXED message (§6,
 * REQ-OBS-02). `<pin>` in the message is substituted with `RAUF_PIN`. Single constructor so the
 * wording is identical everywhere the failure can arise (preflight + default query).
 */
function raufUnresolvableError(): InstallerError {
  return {
    code: "RAUF_UNRESOLVABLE",
    message:
      "pinned default loop runner `" +
      RAUF_PIN +
      "` is not resolvable from the npm registry. Network is required at " +
      "install; this usually means no network access or a registry that cannot " +
      "see the pin. Skills were still installed; the default loop will be " +
      "unavailable until the pin resolves.",
    remedy:
      "Ensure network access and that `" +
      RAUF_PIN +
      "` is resolvable (`npm view " +
      RAUF_PIN +
      " version`), or re-run with `--skip-rauf` to defer the default loop.",
  };
}
