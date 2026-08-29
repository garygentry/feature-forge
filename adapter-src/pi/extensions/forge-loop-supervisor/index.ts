/**
 * forge-loop-supervisor — a first-party Pi extension that lets forge-5-loop run
 * the rauf autonomous coding loop WITHOUT blocking the Pi session, and supervises
 * its native event stream.
 *
 * Pi has no built-in background bash, persistent monitor, or push-notification
 * surface, so the generic Claude-first forge-5-loop contract (background the
 * process, arm a `Monitor` on events.ndjson, `PushNotification` on exceptions)
 * cannot be followed literally on Pi. This extension provides the real mechanism:
 * `forge_loop_launch` starts the runner detached (it runs in rauf's server and
 * outlives the session), then a rotation-aware NDJSON watcher turns each
 * `item_completed` into a quiet progress line and wakes the session — via
 * `pi.sendMessage(..., { triggerTurn: true })` — only on needs-human / blocked /
 * stuck / review-failed / error / completion. `forge_loop_status` and
 * `forge_loop_stop` round out the launch/attach/status/stop surface. Task
 * identity is persisted (session entry + a file mirror beside the runner state)
 * so a restarted session reattaches without duplicate reporting, and shutdown
 * tears down watchers only — never the runner.
 *
 * The pi-facing glue is thin: all logic lives in the injectable {@link
 * createExtension} factory (see wiring.ts), so the extension is unit-tested with
 * a fake pi and fake deps. This file supplies the production dependencies.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { spawn } from "node:child_process";
import { watch as fsWatch } from "node:fs";
import { basename, dirname } from "node:path";

import { createExtension, type Deps, type PiLike, type WatchHandle } from "./wiring.js";

/** How often the backstop poll fires (ms). fs.watch can miss events or drop on
 *  some platforms; a low-frequency interval guarantees the tail keeps up without
 *  busy-waiting. */
const BACKSTOP_MS = 2000;
/** Debounce window (ms) coalescing a burst of fs.watch events into one poll. */
const DEBOUNCE_MS = 120;

const productionDeps: Deps = {
	spawnDetached(bin, args, cwd, onError) {
		// detached + unref + ignored stdio: the child is fully decoupled from the
		// Pi process and survives session shutdown. rauf hands the loop to its
		// server and this launcher exits quickly; a non-self-detaching runner still
		// stays off the session.
		const child = spawn(bin, args, { cwd, detached: true, stdio: "ignore" });
		// ENOENT (bad bin) and other spawn failures arrive here asynchronously —
		// report them so a launch that never happened does not look successful.
		child.on("error", (err) => onError?.(err instanceof Error ? err.message : String(err)));
		child.unref();
	},
	watch(filePath, onChange): WatchHandle {
		const dir = dirname(filePath);
		const base = basename(filePath);
		let debounce: NodeJS.Timeout | null = null;
		const fire = () => {
			if (debounce) return;
			debounce = setTimeout(() => {
				debounce = null;
				onChange();
			}, DEBOUNCE_MS);
		};
		let fsw: ReturnType<typeof fsWatch> | null = null;
		try {
			// Watch the DIRECTORY (not the file) so rotation-by-rename — rauf moves
			// events.ndjson into archive/ and recreates it each run — keeps firing.
			fsw = fsWatch(dir, (_evt, name) => {
				if (!name || name === base) fire();
			});
			fsw.on?.("error", () => {
				/* directory vanished; the backstop interval keeps polling */
			});
		} catch {
			fsw = null;
		}
		const interval = setInterval(onChange, BACKSTOP_MS);
		return {
			close() {
				try {
					fsw?.close();
				} catch {
					/* ignore */
				}
				if (debounce) clearTimeout(debounce);
				clearInterval(interval);
			},
		};
	},
	now: () => new Date().toISOString(),
};

export default function (pi: ExtensionAPI) {
	// Adapt the real ExtensionAPI to the structural PiLike the wiring consumes.
	// Each member is accessed by name off the concrete `pi`, so a method renamed
	// or removed in a future pi is a COMPILE error here (not a silent runtime
	// failure hidden behind a blanket cast) — while PiLike stays loose enough for
	// the fake pi in tests. Argument casts bridge PiLike's minimal shapes to pi's
	// stricter generic signatures; the pi-API contract this was built against
	// pins the exact shapes.
	const piLike: PiLike = {
		registerTool: (def) => (pi.registerTool as (d: unknown) => void)(def),
		on: (event, handler) =>
			(pi.on as unknown as (e: string, h: (ev: unknown, ctx: unknown) => void | Promise<void>) => void)(event, handler),
		sendMessage: (message, options) =>
			pi.sendMessage(message as Parameters<typeof pi.sendMessage>[0], options),
		appendEntry: (customType, data) => pi.appendEntry(customType, data),
		exec:
			typeof pi.exec === "function"
				? (command, args, opts) => pi.exec(command, args, opts)
				: undefined,
	};
	createExtension(piLike, productionDeps);
}
