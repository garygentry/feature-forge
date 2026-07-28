/**
 * Behavioural gate for the vendored AskUserQuestion extension.
 *
 * `ask-user-question/` is a third-party snapshot (see ../UPSTREAM.md), so the
 * risk this file exists to cover is NOT "did we write this correctly" — it is
 * "did a refresh to a newer upstream, or a re-applied patch, silently change
 * what feature-forge depends on". Every assertion below is therefore a
 * feature-forge contract, not a restatement of upstream's own test suite:
 *
 *   - the tool registers under Claude's name, `AskUserQuestion` (patch 1)
 *   - FEATURE_FORGE_ROOT is seeded from the bundle root (patch 3)
 *   - feature-forge's pinned guidance reaches the model, not user config (patch 4)
 *   - the schema still matches what canon tells the model to send
 *   - the TUI, the RPC fallback, and the validation guards still behave
 *
 * The extension is loaded through jiti — the same loader Pi uses — so a module
 * graph that resolves here resolves in a real session. The TUI is driven
 * headlessly: `QuestionnaireSession` takes a `{terminal, requestRender}` tui
 * and raw terminal input, so real key handling and real rendering run with no
 * terminal attached.
 */
import { strict as assert } from "node:assert";
import { test, before, describe } from "node:test";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createJiti } from "jiti";

const HERE = dirname(fileURLToPath(import.meta.url));
const SRC_ROOT = dirname(HERE);
const ENTRY = join(SRC_ROOT, "extensions", "ask-user-question", "index.ts");
const WIDTH = 92;

const KEY = { down: "\x1b[B", up: "\x1b[A", tab: "\t", enter: "\r", space: " ", esc: "\x1b" };
const strip = (s) => s.replace(/\x1b\[[0-9;]*m/g, "");

/** Recursive no-op proxy so `pi.events.emit(...)` &c. work unmodelled. */
const deepStub = () =>
	new Proxy(function () {}, {
		get: (_t, p) => (p === "then" ? undefined : deepStub()),
		apply: () => undefined,
	});

let tool;
let theme;

before(async () => {
	const jiti = createJiti(import.meta.url);

	// Public API only: initTheme() publishes the live Theme on a global-registry
	// symbol precisely so separate module instances (tsx, jiti) share it. Reading
	// it back avoids importing pi's internal theme module by path, which is not
	// part of the package's "exports" map and would be a Pi-upgrade tripwire.
	const { initTheme } = await jiti.import("@earendil-works/pi-coding-agent");
	initTheme("dark");
	theme = globalThis[Symbol.for("@earendil-works/pi-coding-agent:theme")];
	assert.ok(theme, "expected initTheme() to publish a Theme on the global symbol");

	const tools = [];
	const api = new Proxy(
		{ registerTool: (t) => tools.push(t) },
		{ get: (t, p) => (p in t ? t[p] : deepStub()) },
	);
	const extension = await jiti.import(ENTRY, { default: true });
	extension(api);
	assert.equal(tools.length, 1, "expected exactly one registered tool");
	tool = tools[0];
});

/** Start a tool call and expose the live component alongside the pending result. */
function start(params, { mode = "tui" } = {}) {
	let component = null;
	const ctx = {
		hasUI: true,
		mode,
		ui: {
			custom(factory) {
				return new Promise((resolve) => {
					component = factory(
						{ terminal: { columns: WIDTH, rows: 40 }, requestRender() {} },
						theme,
						{},
						resolve,
					);
				});
			},
			notify() {},
		},
	};
	const result = tool.execute("test-call", params, undefined, undefined, ctx);
	return {
		get component() {
			return component;
		},
		result,
	};
}

/** The view graph is imported lazily inside execute(); give it a turn to land. */
const settle = () => new Promise((r) => setTimeout(r, 500));
const render = (c) => c.render(WIDTH).map(strip);
const cursorLine = (c) => render(c).find((l) => l.trimStart().startsWith("❯")) ?? "";

/** Move the cursor onto the row matching `re` without wrapping past it. */
function gotoRow(c, re, max = 10) {
	for (let i = 0; i < max; i++) {
		if (re.test(cursorLine(c))) return true;
		c.handleInput(KEY.down);
	}
	return false;
}

describe("registration contract", () => {
	test("registers under Claude's tool name (vendor patch 1)", () => {
		assert.equal(tool.name, "AskUserQuestion");
	});

	test("seeds FEATURE_FORGE_ROOT from the bundle root (vendor patch 3)", () => {
		// index.ts sits at <root>/extensions/ask-user-question/index.ts, so three
		// dirnames up is the bundle root. In-tree that resolves to adapter-src/pi.
		assert.equal(process.env.FEATURE_FORGE_ROOT, SRC_ROOT);
	});

	test("serves feature-forge's pinned guidance, not user config (vendor patch 4)", () => {
		assert.match(tool.promptSnippet, /Claude-shaped answers/);
		assert.ok(
			tool.promptGuidelines.some((g) => /never author an option labelled "Other"/.test(g)),
			`guidelines did not warn against authoring Other: ${JSON.stringify(tool.promptGuidelines)}`,
		);
	});

	test("schema matches what canon instructs the model to send", () => {
		const questions = tool.parameters.properties.questions;
		const item = questions.items.properties;
		assert.equal(questions.minItems, 1);
		assert.equal(questions.maxItems, 4);
		assert.equal(item.options.minItems, 2);
		assert.equal(item.options.maxItems, 4);
		assert.ok(questions.items.required.includes("header"), "header must be required");
		assert.ok("preview" in item.options.items.properties, "forge-2-tech relies on preview");
		assert.ok("multiSelect" in item, "forge-5-loop relies on multiSelect");
	});
});

describe("TUI questionnaire", () => {
	test("renders, answers two questions, and returns both selections", async () => {
		const session = start({
			questions: [
				{
					question: "Which vendoring strategy should the Pi adapter use?",
					header: "Vendoring",
					options: [
						{ label: "Vendor upstream", description: "Copy the tree into adapter-src." },
						{ label: "npm peer dep", description: "Let the installer prompt.", preview: "peerDependencies: {}" },
					],
				},
				{
					question: "What happens to the duplicate?",
					header: "Duplicate",
					options: [
						{ label: "Delete it", description: "One source of truth." },
						{ label: "Keep it", description: "Fallback for other hosts." },
					],
				},
			],
		});
		await settle();
		const c = session.component;
		assert.ok(c, "expected ui.custom() to yield a component");

		const first = render(c);
		assert.ok(first.some((l) => l.includes("Which vendoring strategy")), "question text missing");
		assert.ok(first.some((l) => l.includes("Vendor upstream")), "option label missing");
		assert.ok(
			first.some((l) => l.includes("Type something")),
			"upstream appends its own custom-answer row; canon promises the user can always type one",
		);

		// The preview pane is what forge-2-tech uses to show candidates side by side.
		c.handleInput(KEY.down);
		assert.ok(
			render(c).some((l) => l.includes("peerDependencies")),
			"focused option's preview did not render",
		);
		c.handleInput(KEY.up);

		c.handleInput(KEY.enter); // answer q1, auto-advance
		c.handleInput(KEY.down);
		c.handleInput(KEY.enter); // answer q2 with the second option
		assert.ok(gotoRow(c, /submit/i), "could not reach the submit row");
		c.handleInput(KEY.enter);

		const { details, content } = await session.result;
		assert.equal(details.cancelled, false);
		assert.deepEqual(
			details.answers.map((a) => a.answer),
			["Vendor upstream", "Keep it"],
		);
		assert.match(content[0].text, /User has answered your questions/);
	});

	test("multi-select returns every toggled label", async () => {
		const session = start({
			questions: [
				{
					question: "Which gates should run?",
					header: "Gates",
					multiSelect: true,
					options: [
						{ label: "typecheck", description: "tsc over the tree" },
						{ label: "drift guard", description: "adapters match a fresh build" },
						{ label: "load probe", description: "import and assert registration" },
					],
				},
			],
		});
		await settle();
		const c = session.component;

		c.handleInput(KEY.space); // typecheck
		c.handleInput(KEY.down);
		c.handleInput(KEY.down);
		c.handleInput(KEY.space); // load probe
		assert.ok(gotoRow(c, /submit/i), "could not reach the submit row");
		c.handleInput(KEY.enter);
		c.handleInput(KEY.enter);

		const { details } = await session.result;
		assert.equal(details.answers[0].kind, "multi");
		assert.deepEqual(details.answers[0].selected, ["typecheck", "load probe"]);
	});

	test("escape cancels without inventing an answer", async () => {
		const session = start({
			questions: [
				{ question: "Proceed?", header: "Gate", options: [
					{ label: "Yes", description: "go" },
					{ label: "No", description: "stop" },
				] },
			],
		});
		await settle();
		session.component.handleInput(KEY.esc);

		const { details, content } = await session.result;
		assert.equal(details.cancelled, true);
		assert.deepEqual(details.answers, []);
		assert.match(content[0].text, /declined/i);
	});
});

describe("RPC fallback", () => {
	// Hosts such as the VSCode pendant and ACP clients (Zed, Paseo) report a UI
	// but cannot render ui.custom(). Without this path the pipeline's interview
	// stages would stall there rather than degrade.
	test("walks questions with select/input when custom UI is unavailable", async () => {
		const selects = [];
		const result = await tool.execute(
			"test-rpc",
			{
				questions: [
					{ question: "Which runner?", header: "Runner", options: [
						{ label: "rauf", description: "the default loop runner" },
						{ label: "other", description: "something else" },
					] },
				],
			},
			undefined,
			undefined,
			{
				hasUI: true,
				mode: "rpc",
				ui: {
					async select(title, options) {
						selects.push({ title, options });
						return options[0]; // ui.select resolves the chosen string, not an index
					},
					async input() {
						return "typed";
					},
					notify() {},
				},
			},
		);
		assert.equal(selects.length, 1, "expected the fallback to drive ui.select");
		assert.equal(result.details.cancelled, false);
		assert.equal(result.details.answers[0].answer, "rauf");
	});
});

describe("validation guards", () => {
	const reject = async (questions) =>
		(await tool.execute("test-bad", { questions }, undefined, undefined, {
			hasUI: true,
			mode: "tui",
			ui: {},
		})).details.error;

	test('rejects an author-supplied "Other" option', async () => {
		// Canon tells the model never to author one; upstream enforces it, because
		// the custom-answer row is the single source of truth for free text.
		assert.equal(
			await reject([
				{ question: "Q?", header: "H", options: [
					{ label: "A", description: "a" },
					{ label: "Other", description: "o" },
				] },
			]),
			"reserved_label",
		);
	});

	test("rejects a question with too few options", async () => {
		assert.equal(
			await reject([{ question: "Q?", header: "H", options: [{ label: "A", description: "a" }] }]),
			"empty_options",
		);
	});

	test("reports no_ui rather than fabricating a decline", async () => {
		const result = await tool.execute(
			"test-noui",
			{ questions: [{ question: "Q?", header: "H", options: [
				{ label: "A", description: "a" },
				{ label: "B", description: "b" },
			] }] },
			undefined,
			undefined,
			{ hasUI: false, mode: "tui", ui: {} },
		);
		assert.equal(result.details.error, "no_ui");
		assert.equal(result.details.cancelled, true);
	});
});
