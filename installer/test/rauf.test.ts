/**
 * Tests for rauf provisioning (spec 06): RAUF_PIN, preflightRauf, and the RegistryQuery seam.
 * Imports the built ../dist/*.js (spec 08 §2). All registry access is mocked — no real network.
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { RAUF_PIN, preflightRauf } from "../dist/rauf.js";
import {
  resolvableRegistry,
  unresolvableRegistry,
  neverCalledRegistry,
} from "./helpers/registry.ts";

test("RAUF_PIN is the pinned coordinate @garygentry/rauf@0.12.0", () => {
  assert.equal(RAUF_PIN, "@garygentry/rauf@0.12.0");
});

test("--skip-rauf returns ok({raufPin:null}) and makes no network call", () => {
  // neverCalledRegistry throws if invoked — proves the query is never consulted.
  const res = preflightRauf({ skip: true, query: neverCalledRegistry });
  assert.equal(res.ok, true);
  assert.ok(res.ok);
  assert.deepEqual(res.value, { raufPin: null });
});

test("resolvable query returns ok({raufPin:RAUF_PIN})", () => {
  const res = preflightRauf({ query: resolvableRegistry });
  assert.equal(res.ok, true);
  assert.ok(res.ok);
  assert.deepEqual(res.value, { raufPin: RAUF_PIN });
});

test("unresolvable query returns err RAUF_UNRESOLVABLE with the fixed production message", () => {
  const res = preflightRauf({ query: unresolvableRegistry });
  assert.equal(res.ok, false);
  assert.ok(!res.ok);
  assert.equal(res.error.code, "RAUF_UNRESOLVABLE");
  // The production message is supplied by preflightRauf, not the stub.
  assert.notEqual(res.error.message, "stub message");
  assert.notEqual(res.error.remedy, "stub remedy");
  // The pin is substituted into the message (verified verbatim in the next test);
  // here we assert the fixed wording shape around it.
  assert.match(res.error.message, /pinned default loop runner `/);
  assert.match(res.error.message, /not resolvable from the npm registry/);
  assert.match(res.error.message, /Skills were still installed/);
  assert.match(res.error.remedy ?? "", /--skip-rauf/);
});

test("RAUF_PIN appears verbatim in the fixed message (pin substitution)", () => {
  const res = preflightRauf({ query: unresolvableRegistry });
  assert.ok(!res.ok);
  assert.ok(res.error.message.includes(RAUF_PIN));
  assert.ok((res.error.remedy ?? "").includes(RAUF_PIN));
});
