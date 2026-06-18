/**
 * Mock RegistryQuery stubs for the rauf preflight (spec 06). These let tests exercise the
 * resolvable / unresolvable / skipped paths with NO real network call.
 *
 * Imports the built ../../dist/*.js for ok/err and the RegistryQuery type (spec 08 §2).
 */

import { ok, err } from "../../dist/types.js";
import type { RegistryQuery } from "../../dist/rauf.js";

/** A query that resolves: returns a version string. */
export const resolvableRegistry: RegistryQuery = () => ok("0.6.0");

/**
 * A query that fails with RAUF_UNRESOLVABLE. The message here is intentionally a STUB — the
 * production fixed message is supplied by `preflightRauf`, not the stub.
 */
export const unresolvableRegistry: RegistryQuery = () =>
  err({ code: "RAUF_UNRESOLVABLE", message: "stub message", remedy: "stub remedy" });

/** A query that must never be invoked (asserts no network call on the --skip-rauf path). */
export const neverCalledRegistry: RegistryQuery = () => {
  throw new Error("registry query must not be called");
};
