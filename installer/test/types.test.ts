import { test } from "node:test";
import assert from "node:assert/strict";

import {
  AGENT_IDS,
  AGENT_TARGETS,
  EXIT,
  MANIFEST_PREFIX,
} from "../dist/types.js";

test("AGENT_IDS is the canonical determinism order (spec 08 §2)", () => {
  assert.deepEqual(AGENT_IDS, ["claude", "codex", "copilot", "cursor", "gemini", "pi"]);
});

test("Object.keys(AGENT_TARGETS) covers exactly AGENT_IDS", () => {
  assert.deepEqual(Object.keys(AGENT_TARGETS), [...AGENT_IDS]);
});

test("EXIT codes are SUCCESS:0, FAILURE:1, USAGE:2", () => {
  assert.deepEqual(EXIT, { SUCCESS: 0, FAILURE: 1, USAGE: 2 });
});

test("MANIFEST_PREFIX is '.feature-forge.'", () => {
  assert.equal(MANIFEST_PREFIX, ".feature-forge.");
});

test("each AGENT_TARGETS row's id matches its key", () => {
  for (const id of AGENT_IDS) {
    assert.equal(AGENT_TARGETS[id].id, id);
  }
});
