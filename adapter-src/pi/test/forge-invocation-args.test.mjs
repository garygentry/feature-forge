/**
 * Behavioural gate for the first-party forge-invocation-args extension (issue #303).
 *
 * The extension is loaded through jiti — the same loader Pi uses — so a module
 * graph that resolves here resolves in a real session. A fake pi captures the one
 * `input` handler the extension registers; the tests then drive that handler with
 * the documented `InputEvent` shapes, exercising the "input fires before skill
 * expansion" lifecycle headlessly. Pure helpers (escapeXml / buildEnvelope /
 * normalizeInput) are imported from wiring.ts and asserted directly.
 *
 * Every assertion is a feature-forge contract for the fix:
 *   - a `/skill:forge-*` invocation is rewritten to inject a versioned envelope
 *   - zero / one / multiple args, flags, multiline, and XML-special chars survive
 *   - unrelated skills and ordinary prompts pass through untouched
 *   - extension-injected messages are left alone; the handler never throws
 *   - an already-enveloped invocation is not double-wrapped
 */
import { strict as assert } from "node:assert";
import { test, before, describe } from "node:test";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createJiti } from "jiti";

const HERE = dirname(fileURLToPath(import.meta.url));
const SRC_ROOT = dirname(HERE);
const EXT_DIR = join(SRC_ROOT, "extensions", "forge-invocation-args");
const ENTRY = join(EXT_DIR, "index.ts");
const WIRING = join(EXT_DIR, "wiring.ts");

let inputHandler;
let onCalls;
let wiring;

before(async () => {
	const jiti = createJiti(import.meta.url);
	wiring = await jiti.import(WIRING);

	onCalls = [];
	const pi = {
		on(event, handler) {
			onCalls.push(event);
			if (event === "input") inputHandler = handler;
		},
	};
	const extension = await jiti.import(ENTRY, { default: true });
	extension(pi);
});

/** Drive the registered handler, tolerating a sync or promised result. */
async function run(text, { source = "interactive", ctx = {} } = {}) {
	return await Promise.resolve(inputHandler({ text, source }, ctx));
}

describe("registration contract", () => {
	test("registers exactly one handler, on the input event", () => {
		assert.deepEqual(onCalls, ["input"]);
		assert.equal(typeof inputHandler, "function");
	});
});

describe("pure helpers", () => {
	test("escapeXml escapes &, <, > and does not double-escape", () => {
		assert.equal(wiring.escapeXml("a<b>c&d"), "a&lt;b&gt;c&amp;d");
		// `&` is replaced first, so an existing `<` becomes `&lt;`, never `&amp;lt;`.
		assert.equal(wiring.escapeXml("<"), "&lt;");
		assert.equal(wiring.escapeXml("&"), "&amp;");
		assert.equal(wiring.escapeXml("plain --flag text"), "plain --flag text");
	});

	test("buildEnvelope wraps skill + escaped args with the versioned tag", () => {
		const env = wiring.buildEnvelope("forge-1-prd", "rendered-model-v2");
		assert.match(env, /^<feature-forge-invocation version="1">/);
		assert.match(env, /<skill>forge-1-prd<\/skill>/);
		assert.match(env, /<arguments>rendered-model-v2<\/arguments>/);
		assert.match(env, /<\/feature-forge-invocation>$/);
	});

	test("buildEnvelope emits an empty <arguments> for zero args", () => {
		assert.match(wiring.buildEnvelope("forge-1-prd", ""), /<arguments><\/arguments>/);
	});

	test("a literal </arguments> in raw args cannot close the element", () => {
		const env = wiring.buildEnvelope("forge-1-prd", "x</arguments>y");
		assert.match(env, /<arguments>x&lt;\/arguments&gt;y<\/arguments>/);
		// Exactly one real closing tag survives.
		assert.equal(env.match(/<\/arguments>/g).length, 1);
	});
});

describe("normalization via the input handler", () => {
	test("one argument is wrapped and presented explicitly", async () => {
		const r = await run("/skill:forge-1-prd rendered-model-v2");
		assert.equal(r.action, "transform");
		assert.ok(r.text.startsWith("/skill:forge-1-prd "), "keeps the skill command prefix");
		assert.match(r.text, /<skill>forge-1-prd<\/skill>/);
		assert.match(r.text, /<arguments>rendered-model-v2<\/arguments>/);
	});

	test("zero arguments yields an explicit empty envelope", async () => {
		const r = await run("/skill:forge-1-prd");
		assert.equal(r.action, "transform");
		assert.match(r.text, /<skill>forge-1-prd<\/skill>/);
		assert.match(r.text, /<arguments><\/arguments>/);
	});

	test("multiple arguments and flags are preserved verbatim", async () => {
		const r = await run("/skill:forge-1-prd auth --force-standalone");
		assert.match(r.text, /<arguments>auth --force-standalone<\/arguments>/);
	});

	test("multiline argument text is not lost", async () => {
		const r = await run("/skill:forge-2-tech auth\nsecond line\nthird");
		assert.match(r.text, /<arguments>auth\nsecond line\nthird<\/arguments>/);
	});

	test("XML-special characters round-trip through escaping", async () => {
		const r = await run("/skill:forge-1-prd a<b>c&d</arguments>");
		assert.match(r.text, /<arguments>a&lt;b&gt;c&amp;d&lt;\/arguments&gt;<\/arguments>/);
	});

	test("the forge navigator (bare name, optional arg) is matched", async () => {
		const r = await run("/skill:forge");
		assert.equal(r.action, "transform");
		assert.match(r.text, /<skill>forge<\/skill>/);
	});

	test("other forge entry points use the same path (forge-0-epic, forge-verify)", async () => {
		assert.equal((await run("/skill:forge-0-epic checkout")).action, "transform");
		assert.equal((await run("/skill:forge-verify auth impl")).action, "transform");
	});
});

describe("passthrough (leaves unrelated input unchanged)", () => {
	test("an unrelated skill command is untouched", async () => {
		assert.deepEqual(await run("/skill:brave-search rust ownership"), { action: "continue" });
	});

	test("a skill whose name merely starts with 'forge' is not matched", async () => {
		// `forgery` is not `forge` or `forge-<...>`, so the boundary lookahead fails.
		assert.deepEqual(await run("/skill:forgery something"), { action: "continue" });
	});

	test("an ordinary prompt is untouched", async () => {
		assert.deepEqual(await run("please summarize the forge pipeline"), { action: "continue" });
	});

	test("extension-injected input (source 'extension') is left alone", async () => {
		assert.deepEqual(
			await run("/skill:forge-1-prd auth", { source: "extension" }),
			{ action: "continue" },
		);
	});

	test("rpc-sourced input IS normalized (covers -p / --mode json)", async () => {
		assert.equal((await run("/skill:forge-1-prd auth", { source: "rpc" })).action, "transform");
	});

	test("an already-enveloped invocation is not double-wrapped", async () => {
		const once = await run("/skill:forge-1-prd auth");
		assert.equal(once.action, "transform");
		const twice = await run(once.text);
		assert.deepEqual(twice, { action: "continue" });
	});
});

describe("fail-loud (never silently reintroduce the bug)", () => {
	test("an internal error notifies and passes the input through unchanged", async () => {
		const notified = [];
		const ctx = { ui: { notify: (msg, level) => notified.push([msg, level]) } };
		// Force an error inside normalizeInput by making `.text` throw on access,
		// after the source guard (which reads `.source`) has passed.
		const evt = {
			source: "interactive",
			get text() {
				throw new Error("boom");
			},
		};
		const r = await Promise.resolve(inputHandler(evt, ctx));
		assert.deepEqual(r, { action: "continue" }, "must not throw; passes through");
		assert.equal(notified.length, 1, "must fail loudly via notify");
		assert.equal(notified[0][1], "error");
	});
});
