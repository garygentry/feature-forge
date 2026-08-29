/**
 * Behavioural gate for the first-party forge-loop-supervisor Pi extension.
 *
 * Unlike the vendored ask-user-question test (which guards a third-party
 * snapshot), this extension is feature-forge-authored, so these assertions are
 * the spec: they pin the contract issue #236 requires — a detached launch that
 * returns immediately, one quiet progress line per completed item, a session
 * wake ONLY on exception/terminal events, rotation- and malformed-tolerant
 * tailing, and reattach across a session restart with no duplicate reporting.
 *
 * The modules are loaded through jiti (the loader Pi uses) so a graph that
 * resolves here resolves in a real session. The pure core (events, tailer,
 * supervisor) is driven directly; the pi-facing wiring is driven with a fake pi
 * and injected deps (no real child processes, no fs.watch timing).
 */
import { strict as assert } from "node:assert";
import { test, before, describe } from "node:test";
import {
	appendFileSync,
	mkdtempSync,
	mkdirSync,
	renameSync,
	rmSync,
	statSync,
	writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createJiti } from "jiti";

const HERE = dirname(fileURLToPath(import.meta.url));
const EXT = join(dirname(HERE), "extensions", "forge-loop-supervisor");

let events;
let NdjsonTailer;
let LoopSupervisor;
let createExtension;
let TASK_ENTRY_TYPE;

before(async () => {
	const jiti = createJiti(import.meta.url);
	events = await jiti.import(join(EXT, "events.ts"));
	({ NdjsonTailer } = await jiti.import(join(EXT, "tailer.ts")));
	({ LoopSupervisor } = await jiti.import(join(EXT, "supervisor.ts")));
	({ createExtension, TASK_ENTRY_TYPE } = await jiti.import(join(EXT, "wiring.ts")));
});

const nl = (obj) => `${JSON.stringify(obj)}\n`;
const tmp = () => mkdtempSync(join(tmpdir(), "forge-loop-"));

describe("event classification", () => {
	test("routine, exception, terminal, and ignore are separated", () => {
		assert.equal(events.classifyEvent({ type: "item_completed" }), "progress");
		assert.equal(events.classifyEvent({ type: "needs_human" }), "exception");
		assert.equal(events.classifyEvent({ type: "item_blocked" }), "exception");
		assert.equal(events.classifyEvent({ type: "llm_stuck_warning" }), "exception");
		assert.equal(events.classifyEvent({ type: "review_failed" }), "exception");
		assert.equal(events.classifyEvent({ type: "loop_completed" }), "terminal");
		assert.equal(events.classifyEvent({ type: "loop_error" }), "terminal");
		assert.equal(events.classifyEvent({ type: "loop_cancelled" }), "terminal");
		// loop_paused is an exception ONLY for the needs-human reason.
		assert.equal(events.classifyEvent({ type: "loop_paused", reason: "needs_human" }), "exception");
		assert.equal(events.classifyEvent({ type: "loop_paused", reason: "usage_limit" }), "ignore");
		// firehose / interior events are never surfaced.
		assert.equal(events.classifyEvent({ type: "llm_token_update" }), "ignore");
		assert.equal(events.classifyEvent({ type: "iteration_start" }), "ignore");
		assert.equal(events.classifyEvent({}), "ignore");
	});

	test("progress line carries [N/M] and the item title", () => {
		assert.match(events.formatProgress({ type: "item_completed", title: "Add auth" }, 3, 10), /\[3\/10\] .*Add auth/);
		// missing total → no fraction, still names the item
		assert.match(events.formatProgress({ type: "item_completed", itemId: "x" }, 2), /completed x/);
	});

	test("terminal summary names counts and tells the model to close out", () => {
		const line = events.formatSignal({ type: "loop_completed", completedCount: 8, blockedCount: 1, needsHumanCount: 2 });
		assert.match(line, /8 done/);
		assert.match(line, /1 blocked/);
		assert.match(line, /2 need a human/);
		assert.match(line, /close-out/i);
	});
});

describe("NdjsonTailer", () => {
	test("reads only new complete lines incrementally", () => {
		const dir = tmp();
		const file = join(dir, "events.ndjson");
		const got = [];
		const t = new NdjsonTailer(file, (r) => got.push(r));
		t.poll(); // file absent → no-op
		writeFileSync(file, nl({ type: "a", seq: 1 }) + nl({ type: "b", seq: 2 }));
		t.poll();
		assert.deepEqual(got.map((r) => r.seq), [1, 2]);
		appendFileSync(file, nl({ type: "c", seq: 3 }));
		t.poll();
		assert.deepEqual(got.map((r) => r.seq), [1, 2, 3]);
		rmSync(dir, { recursive: true, force: true });
	});

	test("buffers a partial trailing line until its newline arrives", () => {
		const dir = tmp();
		const file = join(dir, "events.ndjson");
		const got = [];
		const t = new NdjsonTailer(file, (r) => got.push(r));
		writeFileSync(file, '{"type":"a","seq":1'); // no closing brace/newline yet
		t.poll();
		assert.equal(got.length, 0, "incomplete line must not be dispatched");
		appendFileSync(file, "}\n");
		t.poll();
		assert.deepEqual(got.map((r) => r.seq), [1]);
		rmSync(dir, { recursive: true, force: true });
	});

	test("skips malformed records without stalling the tail", () => {
		const dir = tmp();
		const file = join(dir, "events.ndjson");
		const got = [];
		const errs = [];
		const t = new NdjsonTailer(file, (r) => got.push(r), (e) => errs.push(e));
		writeFileSync(file, nl({ type: "a", seq: 1 }) + "not json at all\n" + nl({ type: "b", seq: 2 }));
		t.poll();
		assert.deepEqual(got.map((r) => r.seq), [1, 2], "valid records still flow past a bad line");
		assert.equal(errs.length, 1);
		rmSync(dir, { recursive: true, force: true });
	});

	test("survives rotation by truncation (size shrinks below the cursor)", () => {
		const dir = tmp();
		const file = join(dir, "events.ndjson");
		const got = [];
		const t = new NdjsonTailer(file, (r) => got.push(r));
		// Two lines so the old file is comfortably larger than the new one.
		writeFileSync(file, nl({ type: "old", seq: 8 }) + nl({ type: "old", seq: 9 }));
		t.poll();
		// New run truncates in place + rewrites a single shorter line at seq 0, so
		// the size drops below the read cursor.
		writeFileSync(file, nl({ type: "new", seq: 0 }));
		t.poll();
		assert.deepEqual(got.map((r) => r.type), ["old", "old", "new"]);
		rmSync(dir, { recursive: true, force: true });
	});

	test("survives rotation by rename+recreate (inode changes) and signals onRotate", () => {
		const dir = tmp();
		const file = join(dir, "events.ndjson");
		const got = [];
		let rotations = 0;
		const t = new NdjsonTailer(file, (r) => got.push(r), undefined, () => { rotations += 1; });
		writeFileSync(file, nl({ type: "run1a", seq: 1 }) + nl({ type: "run1b", seq: 2 }));
		t.poll();
		assert.equal(rotations, 0, "the first read is not a rotation");
		// rauf archives the file and recreates it: move away, then a fresh file
		// (new inode) whose content happens to be LONGER than the old cursor, so
		// only the inode change catches the rotation.
		renameSync(file, join(dir, "archived.ndjson"));
		writeFileSync(file, nl({ type: "run2a", seq: 1 }) + nl({ type: "run2b", seq: 2 }) + nl({ type: "run2c", seq: 3 }));
		t.poll();
		assert.equal(rotations, 1, "the inode change fired onRotate exactly once");
		assert.deepEqual(got.map((r) => r.type), ["run1a", "run1b", "run2a", "run2b", "run2c"]);
		rmSync(dir, { recursive: true, force: true });
	});

	test("a seeded inode makes the FIRST poll detect a rotation that happened while away", () => {
		const dir = tmp();
		const file = join(dir, "events.ndjson");
		writeFileSync(file, nl({ type: "run2", seq: 0 }));
		const currentIno = statSync(file).ino;
		const got = [];
		let rotations = 0;
		// Seed a DIFFERENT inode (the file we last watched, now rotated away).
		const staleIno = currentIno + 1000000;
		const t = new NdjsonTailer(file, (r) => got.push(r), undefined, () => { rotations += 1; }, staleIno);
		t.poll();
		assert.equal(rotations, 1, "the first poll saw a different inode → rotation");
		assert.deepEqual(got.map((r) => r.type), ["run2"]);
		rmSync(dir, { recursive: true, force: true });
	});

	test("decodes a UTF-8 multibyte character split across two reads (#F4)", () => {
		const dir = tmp();
		const file = join(dir, "events.ndjson");
		const got = [];
		const t = new NdjsonTailer(file, (r) => got.push(r));
		// "café" — the é is two bytes (0xC3 0xA9). Split the write between them.
		const buf = Buffer.from(nl({ type: "item_completed", title: "café", seq: 0 }), "utf8");
		const splitAt = buf.indexOf(0xc3) + 1; // between é's two bytes
		writeFileSync(file, buf.subarray(0, splitAt));
		t.poll();
		assert.equal(got.length, 0, "no complete line yet");
		appendFileSync(file, buf.subarray(splitAt));
		t.poll();
		assert.equal(got.length, 1);
		assert.equal(got[0].title, "café", "the multibyte char survived the read boundary");
		rmSync(dir, { recursive: true, force: true });
	});
});

/** A recording host for driving LoopSupervisor directly. */
function recordingHost() {
	const notified = [];
	const woke = [];
	const persisted = [];
	return {
		host: {
			notify: (m, l) => notified.push({ m, l }),
			wake: (m) => woke.push(m),
			persist: (t) => persisted.push({ ...t }),
			now: () => "2026-08-29T00:00:00.000Z",
		},
		notified,
		woke,
		persisted,
	};
}

/** Build a tailer-less reader that a test feeds records into by hand. */
function manualReader() {
	let sink = null;
	let rotate = null;
	return {
		make: (onRecord, onRotate) => {
			sink = onRecord;
			rotate = onRotate;
			return { poll() {} };
		},
		feed: (rec) => sink(rec),
		rotate: () => rotate?.(),
	};
}

describe("LoopSupervisor", () => {
	const task = (over = {}) => ({
		backlogDir: "specs/auth",
		stateDir: "/s/auth/.rauf",
		eventsFile: "/s/auth/.rauf/events.ndjson",
		launchedAt: "t0",
		total: 3,
		lastSeq: -1,
		closed: false,
		...over,
	});

	test("progress notifies but never wakes; exception both; terminal wakes and closes", () => {
		const { host, notified, woke } = recordingHost();
		const sup = new LoopSupervisor(host);
		const r = manualReader();
		sup.attach(task(), r.make);

		r.feed({ type: "item_completed", title: "A", seq: 0 });
		assert.equal(woke.length, 0, "routine progress must not wake the session");
		assert.equal(notified.length, 1);
		assert.match(notified[0].m, /completed A/);

		r.feed({ type: "needs_human", itemId: "2", reason: "api key", seq: 1 });
		assert.equal(woke.length, 1, "exception wakes");
		assert.match(woke[0], /needs a human/);

		r.feed({ type: "loop_completed", completedCount: 1, blockedCount: 0, seq: 2 });
		assert.equal(woke.length, 2, "terminal wakes");
		assert.equal(sup.progress("/s/auth/.rauf").closed, true, "terminal closes the task");
	});

	test("dedup: replayed history (seq <= lastSeq) rebuilds done silently, never re-notifies", () => {
		const { host, notified, woke } = recordingHost();
		const sup = new LoopSupervisor(host);
		const r = manualReader();
		// A reattach whose cursor already covers seq 0 and 1.
		sup.attach(task({ lastSeq: 1 }), r.make);

		r.feed({ type: "item_completed", title: "A", seq: 0 }); // replayed
		r.feed({ type: "needs_human", itemId: "2", reason: "x", seq: 1 }); // replayed
		assert.equal(notified.length, 0, "replayed history is silent");
		assert.equal(woke.length, 0);
		assert.equal(sup.progress("/s/auth/.rauf").done, 1, "but the done counter is rebuilt");

		r.feed({ type: "item_completed", title: "B", seq: 2 }); // live
		assert.equal(notified.length, 1, "records past the cursor are surfaced");
		assert.equal(sup.progress("/s/auth/.rauf").done, 2);
	});

	test("rotation resets the per-run cursor so a new run is surfaced, not swallowed (#F3)", () => {
		const { host, notified, woke } = recordingHost();
		const sup = new LoopSupervisor(host);
		const r = manualReader();
		sup.attach(task(), r.make);

		// Run 1 reaches seq 2.
		r.feed({ type: "item_completed", title: "A", seq: 0 });
		r.feed({ type: "item_completed", title: "B", seq: 1 });
		r.feed({ type: "loop_completed", completedCount: 2, blockedCount: 0, seq: 2 });
		assert.equal(sup.progress("/s/auth/.rauf").done, 2);
		const wokeAfterRun1 = woke.length;

		// A rotation (rauf started run 2 — seq restarts at 0). Without the reset the
		// run-2 events (seq 0,1) would be <= run-1's lastSeq=2 and be swallowed.
		r.rotate();
		const p = sup.progress("/s/auth/.rauf");
		assert.equal(p.done, 0, "done reset for the new run");
		assert.equal(p.closed, false, "closed reset for the new run");

		const notifiedBefore = notified.length;
		r.feed({ type: "item_completed", title: "A2", seq: 0 });
		assert.equal(notified.length, notifiedBefore + 1, "run-2 seq 0 is surfaced, not swallowed");
		assert.equal(sup.progress("/s/auth/.rauf").done, 1);
		r.feed({ type: "loop_completed", completedCount: 1, blockedCount: 0, seq: 1 });
		assert.equal(woke.length, wokeAfterRun1 + 1, "run-2 terminal wakes");
	});

	test("a second attach for the same stateDir does not create a duplicate", () => {
		const { host } = recordingHost();
		const sup = new LoopSupervisor(host);
		let made = 0;
		const mk = (_onRecord) => {
			made += 1;
			return { poll() {} };
		};
		sup.attach(task(), mk);
		sup.attach(task(), mk);
		assert.equal(made, 1, "the dedup guard prevents a second reader/watcher");
	});
});

/** Fake pi + injected deps for driving the wiring end to end. */
function harness(cwd) {
	const tools = new Map();
	const on = new Map();
	const sent = [];
	const entries = [];
	const execCalls = [];
	const pi = {
		registerTool: (t) => tools.set(t.name, t),
		on: (e, h) => on.set(e, h),
		sendMessage: (m, o) => sent.push({ m, o }),
		appendEntry: (type, data) => entries.push({ type, data }),
		exec: async (command, args, options) => {
			execCalls.push({ command, args, options });
			return { stdout: '{"status":"RUNNING"}', stderr: "", code: 0 };
		},
	};
	const spawns = [];
	const watches = [];
	const deps = {
		spawnDetached: (bin, args) => spawns.push({ bin, args }),
		watch: (filePath, onChange) => {
			const w = { filePath, onChange, closed: false, close() { this.closed = true; } };
			watches.push(w);
			return w;
		},
		now: () => "2026-08-29T00:00:00.000Z",
	};
	const notifies = [];
	const ctx = {
		cwd,
		hasUI: true,
		ui: { notify: (m, l) => notifies.push({ m, l }) },
		sessionManager: { getEntries: () => entries.map((e) => ({ type: "custom", customType: e.type, data: e.data })) },
	};
	const control = createExtension(pi, deps);
	return { pi, tools, on, sent, entries, execCalls, spawns, watches, notifies, ctx, control, deps };
}

describe("wiring: launch / supervise / stop / lifecycle", () => {
	test("launch spawns rauf detached, returns immediately, and starts one watcher", async () => {
		const cwd = tmp();
		mkdirSync(join(cwd, "specs/auth/.rauf"), { recursive: true });
		writeFileSync(join(cwd, "specs/auth/backlog.json"), JSON.stringify({ items: [{}, {}, {}] }));
		const h = harness(cwd);

		const res = await h.tools.get("forge_loop_launch").execute(
			"id", { backlogDir: "specs/auth", review: true }, undefined, undefined, h.ctx,
		);
		assert.equal(res.details.launched, true);
		assert.deepEqual(h.spawns[0].args, ["loop", "run", ".", "--backlog", "specs/auth", "--detached", "--review"]);
		assert.equal(h.watches.length, 1, "exactly one watcher");
		assert.ok(h.entries.some((e) => e.type === TASK_ENTRY_TYPE), "task identity persisted to the session");
		// A second launch for the same loop does not relaunch or double-watch.
		const again = await h.tools.get("forge_loop_launch").execute("id2", { backlogDir: "specs/auth" }, undefined, undefined, h.ctx);
		assert.equal(again.details.launched, false);
		assert.equal(h.spawns.length, 1);
		rmSync(cwd, { recursive: true, force: true });
	});

	test("supervision: progress notifies quietly, exception + terminal wake exactly once each", async () => {
		const cwd = tmp();
		const stateDir = join(cwd, "specs/auth/.rauf");
		mkdirSync(stateDir, { recursive: true });
		const eventsFile = join(stateDir, "events.ndjson");
		const h = harness(cwd);
		await h.tools.get("forge_loop_launch").execute("id", { backlogDir: "specs/auth" }, undefined, undefined, h.ctx);
		const trigger = () => h.watches[0].onChange();

		writeFileSync(eventsFile, nl({ type: "item_completed", title: "A", seq: 0 }));
		trigger();
		assert.equal(h.sent.length, 0, "progress does not wake");
		assert.ok(h.notifies.some((n) => /completed A/.test(n.m)), "progress notified");

		appendFileSync(eventsFile, nl({ type: "needs_human", itemId: "2", reason: "key", seq: 1 }));
		trigger();
		assert.equal(h.sent.length, 1);
		assert.equal(h.sent[0].o.triggerTurn, true, "wake triggers a turn");
		assert.match(h.sent[0].m.content, /needs a human/);

		appendFileSync(eventsFile, nl({ type: "loop_completed", completedCount: 1, blockedCount: 0, seq: 2 }));
		trigger();
		assert.equal(h.sent.length, 2, "terminal wakes exactly once");
		// The terminal event tears the watcher down (its wake already fired) — no
		// leaked fs.watch/interval for a finished loop, and isActive frees relaunch.
		assert.equal(h.watches[0].closed, true, "watcher closed after terminal");
		assert.equal(h.control.supervisor.isActive(stateDir), false, "task no longer active after terminal");
		// A redundant trigger with no new bytes must not re-wake.
		trigger();
		assert.equal(h.sent.length, 2, "no duplicate terminal wake");
		rmSync(cwd, { recursive: true, force: true });
	});

	test("firehose (ignore) events do not trigger a mirror/session write (#F1)", async () => {
		const cwd = tmp();
		const stateDir = join(cwd, "specs/auth/.rauf");
		mkdirSync(stateDir, { recursive: true });
		const eventsFile = join(stateDir, "events.ndjson");
		const h = harness(cwd);
		await h.tools.get("forge_loop_launch").execute("id", { backlogDir: "specs/auth" }, undefined, undefined, h.ctx);
		const entriesAfterLaunch = h.entries.length; // launch persists once
		const trigger = () => h.watches[0].onChange();

		// A burst of ignore-classified firehose events must NOT each persist.
		writeFileSync(eventsFile, nl({ type: "llm_token_update", seq: 0 }) + nl({ type: "iteration_start", seq: 1 }));
		trigger();
		assert.equal(h.entries.length, entriesAfterLaunch, "firehose events persisted nothing");
		// A surfaced event DOES persist (advancing the durable cursor).
		appendFileSync(eventsFile, nl({ type: "item_completed", title: "A", seq: 2 }));
		trigger();
		assert.equal(h.entries.length, entriesAfterLaunch + 1, "a surfaced event persists once");
		rmSync(cwd, { recursive: true, force: true });
	});

	test("a loop can be relaunched after it completes (#F2 frees isActive)", async () => {
		const cwd = tmp();
		const stateDir = join(cwd, "specs/auth/.rauf");
		mkdirSync(stateDir, { recursive: true });
		const eventsFile = join(stateDir, "events.ndjson");
		const h = harness(cwd);
		await h.tools.get("forge_loop_launch").execute("id", { backlogDir: "specs/auth" }, undefined, undefined, h.ctx);
		writeFileSync(eventsFile, nl({ type: "loop_completed", completedCount: 0, blockedCount: 0, seq: 0 }));
		h.watches[0].onChange();
		assert.equal(h.control.supervisor.isActive(stateDir), false);
		const again = await h.tools.get("forge_loop_launch").execute("id2", { backlogDir: "specs/auth" }, undefined, undefined, h.ctx);
		assert.equal(again.details.launched, true, "a finished loop can be relaunched");
		assert.equal(h.spawns.length, 2);
		rmSync(cwd, { recursive: true, force: true });
	});

	test("async spawn failure (bad bin) is surfaced as an error notification (#F5)", async () => {
		const cwd = tmp();
		mkdirSync(join(cwd, "specs/auth/.rauf"), { recursive: true });
		const h = harness(cwd);
		// Make spawnDetached fire its onError asynchronously, as Node does for ENOENT.
		h.deps.spawnDetached = (_bin, _args, _cwd, onError) => onError?.("spawn raufx ENOENT");
		const res = await h.tools.get("forge_loop_launch").execute("id", { backlogDir: "specs/auth", bin: "raufx" }, undefined, undefined, h.ctx);
		assert.equal(res.details.launched, true, "the tool still returns (the error is async)");
		assert.ok(
			h.notifies.some((n) => n.l === "error" && /failed to launch raufx/.test(n.m)),
			"the async spawn failure surfaced as an error notification",
		);
		rmSync(cwd, { recursive: true, force: true });
	});

	test("session_shutdown closes watchers but never stops the runner", async () => {
		const cwd = tmp();
		mkdirSync(join(cwd, "specs/auth/.rauf"), { recursive: true });
		const h = harness(cwd);
		await h.tools.get("forge_loop_launch").execute("id", { backlogDir: "specs/auth" }, undefined, undefined, h.ctx);
		assert.equal(h.watches[0].closed, false);
		h.on.get("session_shutdown")({ type: "session_shutdown", reason: "quit" }, {});
		assert.equal(h.watches[0].closed, true, "watcher torn down");
		assert.equal(h.execCalls.length, 0, "the detached runner is NOT stopped on shutdown");
		rmSync(cwd, { recursive: true, force: true });
	});

	test("explicit stop terminates the runner and clears the mirror", async () => {
		const cwd = tmp();
		mkdirSync(join(cwd, "specs/auth/.rauf"), { recursive: true });
		const h = harness(cwd);
		await h.tools.get("forge_loop_launch").execute("id", { backlogDir: "specs/auth" }, undefined, undefined, h.ctx);
		const res = await h.tools.get("forge_loop_stop").execute("id", { backlogDir: "specs/auth" }, undefined, undefined, h.ctx);
		assert.equal(res.details.stopped, true);
		assert.ok(
			h.execCalls.some((c) => c.args.join(" ") === "loop stop --backlog specs/auth"),
			"stop runs `rauf loop stop` scoped to the backlog",
		);
		assert.equal(h.watches[0].closed, true);
		rmSync(cwd, { recursive: true, force: true });
	});

	test("stop refuses to kill a loop it never supervised (#codex-2)", async () => {
		const cwd = tmp();
		const h = harness(cwd);
		// Nothing launched, no args: must NOT run `rauf loop stop` (which would kill
		// whatever loop happens to be in this project).
		const res = await h.tools.get("forge_loop_stop").execute("id", {}, undefined, undefined, h.ctx);
		assert.equal(res.details.stopped, false);
		assert.equal(h.execCalls.length, 0, "no stop command was run");
		rmSync(cwd, { recursive: true, force: true });
	});

	test("status scopes the runner query to the supervised backlog (#codex-2)", async () => {
		const cwd = tmp();
		mkdirSync(join(cwd, "specs/auth/.rauf"), { recursive: true });
		const h = harness(cwd);
		await h.tools.get("forge_loop_launch").execute("id", { backlogDir: "specs/auth" }, undefined, undefined, h.ctx);
		await h.tools.get("forge_loop_status").execute("id", {}, undefined, undefined, h.ctx);
		assert.ok(
			h.execCalls.some((c) => c.args.join(" ") === "status --json --backlog specs/auth"),
			"status queries the runner scoped to the backlog",
		);
		rmSync(cwd, { recursive: true, force: true });
	});

	test("a brand-new session reattaches from the disk mirror alone (#codex-3)", async () => {
		const cwd = tmp();
		const stateDir = join(cwd, "specs/auth/.rauf");
		mkdirSync(stateDir, { recursive: true });
		const eventsFile = join(stateDir, "events.ndjson");
		writeFileSync(eventsFile, nl({ type: "item_completed", title: "A", seq: 0 }));
		// A previous session left a mirror; the NEW session has NO forge-loop-task entry.
		writeFileSync(join(stateDir, ".forge-supervisor.json"), JSON.stringify({
			backlogDir: "specs/auth", stateDir, eventsFile, launchedAt: "t0", total: 3, lastSeq: 0, closed: false,
		}));

		const h = harness(cwd); // ctx.sessionManager.getEntries() returns [] (no entries)
		h.on.get("session_start")({ type: "session_start", reason: "startup" }, h.ctx);
		assert.equal(h.watches.length, 1, "discovered the mirror by scanning cwd and reattached");
		assert.equal(h.control.supervisor.progress(stateDir).done, 1, "rebuilt state from the mirror's run");

		// A new terminal event past the cursor wakes the freshly-reattached session.
		appendFileSync(eventsFile, nl({ type: "loop_completed", completedCount: 1, blockedCount: 0, seq: 1 }));
		h.watches[0].onChange();
		assert.equal(h.sent.length, 1, "the reattached session is woken by the new terminal event");
		rmSync(cwd, { recursive: true, force: true });
	});

	test("reattach on session_start does not re-report events already seen", async () => {
		const cwd = tmp();
		const stateDir = join(cwd, "specs/auth/.rauf");
		mkdirSync(stateDir, { recursive: true });
		const eventsFile = join(stateDir, "events.ndjson");
		// A prior run left two events on disk and a mirror whose cursor covers both.
		writeFileSync(eventsFile, nl({ type: "item_completed", title: "A", seq: 0 }) + nl({ type: "item_completed", title: "B", seq: 1 }));
		writeFileSync(join(stateDir, ".forge-supervisor.json"), JSON.stringify({
			backlogDir: "specs/auth", stateDir, eventsFile, launchedAt: "t0", total: 3, lastSeq: 1, closed: false,
		}));

		const h = harness(cwd);
		// The session records the task entry so session_start rediscovers it.
		h.entries.push({ type: TASK_ENTRY_TYPE, data: { backlogDir: "specs/auth", stateDir, eventsFile, lastSeq: 1, closed: false } });
		h.on.get("session_start")({ type: "session_start", reason: "resume" }, h.ctx);

		assert.equal(h.watches.length, 1, "reattached exactly one watcher");
		assert.equal(h.notifies.length, 0, "already-seen history is not re-notified");
		assert.equal(h.sent.length, 0);
		assert.equal(h.control.supervisor.progress(stateDir).done, 2, "done counter rebuilt from replay");

		// A genuinely new event past the cursor is surfaced.
		appendFileSync(eventsFile, nl({ type: "loop_completed", completedCount: 2, blockedCount: 0, seq: 2 }));
		h.watches[0].onChange();
		assert.equal(h.sent.length, 1, "the new terminal event wakes the reattached session");
		rmSync(cwd, { recursive: true, force: true });
	});
});
