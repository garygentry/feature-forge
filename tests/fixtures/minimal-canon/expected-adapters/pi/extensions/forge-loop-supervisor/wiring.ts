// GENERATED — DO NOT EDIT. Source: adapter-src/pi/extensions/forge-loop-supervisor/wiring.ts
// Regenerate with: python3 scripts/build-adapters.py
/**
 * Pi wiring for the forge-loop-supervisor — builds the host, the three tools
 * (launch / status / stop) and the session-lifecycle hooks on a given
 * `ExtensionAPI`. Every side-effecting dependency (process spawn, file watch,
 * clock) is injected so the whole extension is unit-testable with a fake pi and
 * fake deps, mirroring how the vendored ask-user-question extension is driven
 * headlessly in its own test.
 *
 * pi surface used (resolved against the installed pi types, stable across the
 * pinned 0.81.x): `pi.registerTool`, `pi.on("session_start"|"session_shutdown")`,
 * `pi.sendMessage(msg, { triggerTurn })` (wake the session — the file-trigger.ts
 * pattern), `pi.appendEntry(type, data)` (durable task record), `pi.exec` (run
 * `rauf status --json` / `rauf loop stop`), and `ctx.ui.notify` (quiet toasts).
 * rauf's `--detached` loop is server-owned and outlives the session, so cleanup
 * on shutdown tears down watchers only — never the runner.
 */

import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { Type } from "typebox";

import { clearMirror, readMirror, writeMirror } from "./registry.js";
import { LoopSupervisor, type TaskHandle } from "./supervisor.js";
import { NdjsonTailer } from "./tailer.js";
import type { SupervisorHost, SupervisorTask } from "./types.js";

/** The custom-entry type under which task identity is persisted into the pi
 *  session (read back on `session_start` for reattach). */
export const TASK_ENTRY_TYPE = "forge-loop-task";
/** The custom-message type used to wake the session on exception/terminal. */
export const WAKE_MESSAGE_TYPE = "forge-loop";

/** A live poll trigger for one watched file: `close()` stops it. The real
 *  factory wires `fs.watch` on the containing directory (so rotation-by-rename
 *  is caught) plus a low-frequency backstop; a test injects a manual trigger. */
export interface WatchHandle {
	close(): void;
}

/** Injectable side effects. Production values live in index.ts. */
export interface Deps {
	/** Launch the runner DETACHED so it outlives the session. Returns nothing —
	 *  the loop is owned by the runner's server, not by a tracked child. `onError`
	 *  reports an ASYNCHRONOUS spawn failure (e.g. ENOENT for a bad bin, which
	 *  Node surfaces on the child's 'error' event, not as a throw). */
	spawnDetached(bin: string, args: string[], cwd: string, onError?: (message: string) => void): void;
	/** Watch `filePath` for changes, calling `onChange` on each (real: fs.watch
	 *  on its directory + backstop interval). */
	watch(filePath: string, onChange: () => void): WatchHandle;
	/** Current time as ISO-8601. */
	now(): string;
}

/** Minimal shape of the pi API this wiring needs (kept structural so the fake pi
 *  in tests satisfies it without importing pi). */
export interface PiLike {
	registerTool(def: unknown): void;
	on(event: string, handler: (event: unknown, ctx: unknown) => void | Promise<void>): void;
	sendMessage(
		message: { customType: string; content: string; display?: boolean },
		options?: { triggerTurn?: boolean },
	): void;
	appendEntry(customType: string, data?: unknown): void;
	exec?(
		command: string,
		args: string[],
		options?: { cwd?: string; timeout?: number },
	): Promise<{ stdout: string; stderr: string; code: number }>;
}

interface UiLike {
	notify?(message: string, level?: "info" | "warning" | "error"): void;
}
interface CtxLike {
	cwd?: string;
	hasUI?: boolean;
	ui?: UiLike;
	sessionManager?: { getEntries?(): Array<{ type?: string; customType?: string; data?: unknown }> };
}

function textResult(text: string, details: Record<string, unknown>) {
	return { content: [{ type: "text" as const, text }], details };
}

/** Best-effort count of backlog items for the `[N/M]` progress line. */
function countBacklog(cwd: string, backlogDir: string): number | undefined {
	for (const candidate of [join(cwd, backlogDir, "backlog.json"), join(backlogDir, "backlog.json")]) {
		try {
			if (!existsSync(candidate)) continue;
			const parsed = JSON.parse(readFileSync(candidate, "utf8")) as { items?: unknown[] };
			if (Array.isArray(parsed.items)) return parsed.items.length;
		} catch {
			// unreadable/unparseable backlog → no total, not an error
		}
	}
	return undefined;
}

/** Resolve `dir` against `cwd` unless it is already absolute. */
function resolveDir(cwd: string, dir: string): string {
	return dir.startsWith("/") ? dir : join(cwd, dir);
}

/**
 * Register the supervisor's tools and lifecycle hooks on `pi`. Returns a small
 * control object (used by tests) exposing the live supervisor and watcher map.
 */
export function createExtension(pi: PiLike, deps: Deps) {
	const watchers = new Map<string, { handle: TaskHandle; watch: WatchHandle }>();
	let ui: UiLike | null = null;

	const host: SupervisorHost = {
		notify(message, level) {
			try {
				ui?.notify?.(message, level);
			} catch {
				/* headless / no dialog UI */
			}
		},
		wake(message) {
			try {
				pi.sendMessage({ customType: WAKE_MESSAGE_TYPE, content: message, display: true }, { triggerTurn: true });
			} catch {
				/* sendMessage unavailable — nothing else to do */
			}
		},
		persist(task) {
			try {
				pi.appendEntry(TASK_ENTRY_TYPE, task);
			} catch {
				/* appendEntry best-effort */
			}
			writeMirror(task);
		},
		now: () => deps.now(),
	};

	const supervisor = new LoopSupervisor(host);

	/** Keep the notify target current from whatever ctx we last saw (tool call or
	 *  session_start). ctx can go stale across a session replacement, so we always
	 *  prefer the most recent one. */
	function refreshUi(ctx: CtxLike): void {
		if (ctx?.ui) ui = ctx.ui;
	}

	/** Begin watching a task's event file. Idempotent per stateDir (the dedup
	 *  guard against duplicate watchers). Does an initial poll to replay history. */
	function startWatch(task: SupervisorTask): void {
		if (watchers.has(task.stateDir)) return;
		const handle = supervisor.attach(task, (onRecord, onRotate) =>
			new NdjsonTailer(task.eventsFile, onRecord, undefined, onRotate, task.eventsIno),
		);
		// Poll, then tear the watcher down once a terminal event has closed the task
		// (its wake was already sent inside poll). This stops the fs.watch + backstop
		// interval for a finished loop and frees a relaunch on the same backlog — the
		// detached runner is untouched, exactly as on session end.
		const pump = () => {
			handle.poll();
			if (supervisor.progress(task.stateDir)?.closed) stopWatch(task.stateDir);
		};
		const watch = deps.watch(task.eventsFile, pump);
		watchers.set(task.stateDir, { handle, watch });
		pump();
	}

	/** Stop watching a task (teardown / stop) WITHOUT touching the runner. */
	function stopWatch(stateDir: string): void {
		const w = watchers.get(stateDir);
		if (!w) return;
		try {
			w.watch.close();
		} catch {
			/* ignore */
		}
		w.handle.close();
		watchers.delete(stateDir);
	}

	// ---- Tools -------------------------------------------------------------

	pi.registerTool({
		name: "forge_loop_launch",
		label: "Launch forge loop",
		description:
			"Launch the forge autonomous coding loop (rauf) DETACHED and supervise it. " +
			"The loop runs in rauf's server and outlives this session; this tool returns " +
			"immediately. It then reports each completed backlog item as a quiet line and " +
			"WAKES this session on needs-human, blocked, stuck, review-failed, error, or " +
			"completion. Use this for forge-5-loop's loop run on Pi instead of running the " +
			"runner in the foreground.",
		promptSnippet:
			"Start a forge/rauf loop without blocking the session and supervise its events.ndjson.",
		parameters: Type.Object({
			backlogDir: Type.String({ description: "Forge backlog directory passed to --backlog (e.g. specs/auth)." }),
			bin: Type.Optional(Type.String({ description: "Runner binary. Default 'rauf'." })),
			stateDir: Type.Optional(
				Type.String({ description: "Runner state dir holding events.ndjson. Default '<backlogDir>/.rauf'." }),
			),
			iterations: Type.Optional(Type.Number({ description: "Max iterations (--iterations). Omit for the runner default." })),
			review: Type.Optional(Type.Boolean({ description: "Append --review to run the loop's review pass." })),
			agent: Type.Optional(Type.String({ description: "Coding-agent id passed as --agent." })),
		}),
		async execute(_id: string, params: unknown, _signal: unknown, _onUpdate: unknown, ctx: CtxLike) {
			const p = params as {
				backlogDir: string;
				bin?: string;
				stateDir?: string;
				iterations?: number;
				review?: boolean;
				agent?: string;
			};
			refreshUi(ctx);
			const cwd = ctx.cwd ?? process.cwd();
			const bin = p.bin || "rauf";
			const stateDir = resolveDir(cwd, p.stateDir || join(p.backlogDir, ".rauf"));
			const eventsFile = join(stateDir, "events.ndjson");

			if (supervisor.isActive(stateDir)) {
				return textResult(
					`A forge loop is already being supervised for ${stateDir}. Use forge_loop_status to check it, or forge_loop_stop first.`,
					{ launched: false, stateDir },
				);
			}

			const args = ["loop", "run", ".", "--backlog", p.backlogDir, "--detached"];
			if (typeof p.iterations === "number") args.push("--iterations", String(p.iterations));
			if (p.review) args.push("--review");
			if (p.agent) args.push("--agent", p.agent);

			try {
				// A synchronous throw is a definite failure. An ASYNC spawn error
				// (ENOENT for a bad bin) arrives after this returns, so surface it as
				// a notification when it fires rather than silently claiming success.
				deps.spawnDetached(bin, args, cwd, (msg) =>
					host.notify(`forge loop: failed to launch ${bin} — ${msg}. The loop did not start.`, "error"),
				);
			} catch (e) {
				const msg = e instanceof Error ? e.message : String(e);
				return textResult(`Failed to launch ${bin}: ${msg}`, { launched: false, stateDir, error: msg });
			}

			const task: SupervisorTask = {
				backlogDir: p.backlogDir,
				stateDir,
				eventsFile,
				launchedAt: host.now(),
				total: countBacklog(cwd, p.backlogDir),
				lastSeq: -1,
				closed: false,
			};
			host.persist(task);
			startWatch(task);

			return textResult(
				`Launched \`${bin} ${args.join(" ")}\` detached; now supervising ${eventsFile}. ` +
					"I'll report each completed item and wake this session on needs-human / blocked / " +
					"stuck / review-failed / error / completion. Run forge_loop_status to confirm it started. " +
					"Do NOT run the loop in the foreground.",
				{ launched: true, stateDir, eventsFile },
			);
		},
	});

	pi.registerTool({
		name: "forge_loop_status",
		label: "Forge loop status",
		description:
			"Report the status of a supervised forge/rauf loop: how many items are done, " +
			"whether it has finished, and the runner's authoritative counts (via " +
			"`rauf status --json`). Use to confirm a launch or check progress on demand.",
		parameters: Type.Object({
			backlogDir: Type.Optional(Type.String({ description: "Backlog dir of the loop to report. Omit for the only supervised loop." })),
			stateDir: Type.Optional(Type.String({ description: "State dir of the loop. Overrides backlogDir when set." })),
			bin: Type.Optional(Type.String({ description: "Runner binary for the status query. Default 'rauf'." })),
		}),
		async execute(_id: string, params: unknown, _signal: unknown, _onUpdate: unknown, ctx: CtxLike) {
			const p = params as { backlogDir?: string; stateDir?: string; bin?: string };
			refreshUi(ctx);
			const cwd = ctx.cwd ?? process.cwd();
			const stateDir = p.stateDir
				? resolveDir(cwd, p.stateDir)
				: p.backlogDir
					? resolveDir(cwd, join(p.backlogDir, ".rauf"))
					: [...watchers.keys()][0];

			const progress = stateDir ? supervisor.progress(stateDir) : null;
			let runnerLine = "";
			if (pi.exec) {
				try {
					const res = await pi.exec(p.bin || "rauf", ["status", "--json"], { cwd, timeout: 15000 });
					runnerLine = res.code === 0 ? ` Runner: ${res.stdout.trim()}` : ` Runner status exited ${res.code}.`;
				} catch {
					runnerLine = " (could not query the runner for authoritative status)";
				}
			}

			if (!progress) {
				return textResult(
					`No forge loop is being supervised in this session${stateDir ? ` for ${stateDir}` : ""}.${runnerLine}`,
					{ supervised: false, stateDir, runner: runnerLine.trim() },
				);
			}
			const totalPart = typeof progress.total === "number" ? `/${progress.total}` : "";
			return textResult(
				`Forge loop ${progress.closed ? "finished" : "running"}: ${progress.done}${totalPart} items completed so far.${runnerLine}`,
				{ supervised: true, stateDir, done: progress.done, total: progress.total, closed: progress.closed },
			);
		},
	});

	pi.registerTool({
		name: "forge_loop_stop",
		label: "Stop forge loop",
		description:
			"Stop a supervised forge/rauf loop and stop watching it. This DELIBERATELY " +
			"terminates the runner (via `rauf loop stop`) — unlike ending the session, " +
			"which leaves the detached loop running. Use only when the user wants the loop " +
			"to actually stop.",
		parameters: Type.Object({
			backlogDir: Type.Optional(Type.String({ description: "Backlog dir of the loop to stop. Omit for the only supervised loop." })),
			stateDir: Type.Optional(Type.String({ description: "State dir of the loop. Overrides backlogDir when set." })),
			bin: Type.Optional(Type.String({ description: "Runner binary. Default 'rauf'." })),
		}),
		async execute(_id: string, params: unknown, _signal: unknown, _onUpdate: unknown, ctx: CtxLike) {
			const p = params as { backlogDir?: string; stateDir?: string; bin?: string };
			refreshUi(ctx);
			const cwd = ctx.cwd ?? process.cwd();
			const stateDir = p.stateDir
				? resolveDir(cwd, p.stateDir)
				: p.backlogDir
					? resolveDir(cwd, join(p.backlogDir, ".rauf"))
					: [...watchers.keys()][0];

			let stopLine = "";
			if (pi.exec) {
				try {
					const res = await pi.exec(p.bin || "rauf", ["loop", "stop"], { cwd, timeout: 30000 });
					stopLine = res.code === 0 ? "Runner stop requested." : `Runner stop exited ${res.code}: ${res.stderr.trim()}`;
				} catch (e) {
					stopLine = `Could not run the stop command: ${e instanceof Error ? e.message : String(e)}`;
				}
			}
			if (stateDir) {
				stopWatch(stateDir);
				supervisor.detach(stateDir);
				clearMirror(stateDir);
			}
			return textResult(`Stopped supervising${stateDir ? ` ${stateDir}` : ""}. ${stopLine}`, {
				stopped: true,
				stateDir,
			});
		},
	});

	// ---- Lifecycle ---------------------------------------------------------

	// Reattach on every session start (startup / reload / resume / fork): rebuild
	// the watcher for any loop this session (or a previous one) launched, without
	// duplicate reporting — the dedup cursor (lastSeq) makes replayed history silent.
	pi.on("session_start", (_event: unknown, ctx: unknown) => {
		const c = ctx as CtxLike;
		ui = c.ui ?? null;
		const seen = new Set<string>();
		const consider = (task: SupervisorTask | null) => {
			if (!task || seen.has(task.stateDir) || watchers.has(task.stateDir)) return;
			seen.add(task.stateDir);
			// Prefer the on-disk mirror (most current lastSeq/closed); fall back to
			// the session entry's own copy.
			const fresh = readMirror(task.stateDir) ?? task;
			if (fresh.closed) return; // already surfaced its terminal — nothing to resume
			startWatch(fresh);
		};
		const entries = c.sessionManager?.getEntries?.() ?? [];
		for (const entry of entries) {
			if (entry?.type === "custom" && entry?.customType === TASK_ENTRY_TYPE) {
				consider(entry.data as SupervisorTask);
			}
		}
	});

	// Cleanup on shutdown: close every watcher, but LEAVE the detached runner
	// running (it is server-owned and meant to outlive the session) and leave the
	// mirror in place so the next session reattaches.
	pi.on("session_shutdown", () => {
		for (const stateDir of [...watchers.keys()]) stopWatch(stateDir);
	});

	return { supervisor, watchers, startWatch, stopWatch, host };
}
