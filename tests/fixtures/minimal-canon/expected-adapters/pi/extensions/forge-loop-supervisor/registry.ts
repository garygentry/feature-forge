// GENERATED — DO NOT EDIT. Source: adapter-src/pi/extensions/forge-loop-supervisor/registry.ts
// Regenerate with: python3 scripts/build-adapters.py
/**
 * Durable task registry — a small JSON mirror of the supervised task, written
 * beside the runner's own state so a brand-new Pi session (or a full pi restart,
 * where the session file itself differs) can rediscover a loop it did not launch.
 *
 * Why a file and not only `pi.appendEntry`: appendEntry records survive session
 * reload/branch within pi, but a cold restart may open a different session file.
 * The mirror lives at `<stateDir>/.forge-supervisor.json`, next to rauf's own
 * `state.json` / `events.ndjson`, so it is discoverable from the backlog dir
 * alone. rauf's detached loop is server-managed (no single child pid to signal),
 * so liveness is judged from the event stream and `rauf status --json`, never a
 * tracked pid — the mirror deliberately stores no pid.
 */

import {
	existsSync,
	mkdirSync,
	readdirSync,
	readFileSync,
	renameSync,
	rmSync,
	statSync,
	writeFileSync,
} from "node:fs";
import { dirname, join } from "node:path";

import type { SupervisorTask } from "./types.js";

/** The mirror filename, discoverable by scanning (see {@link discoverMirrors}). */
export const MIRROR_NAME = ".forge-supervisor.json";

/** Directory names never worth descending into during a mirror scan. */
const SKIP_DIRS = new Set(["node_modules", ".git", "dist", "archive", ".pi", ".claude"]);
/** How deep the scan descends from the project root — mirrors live at
 *  `<backlogDir>/.rauf/.forge-supervisor.json`, so a shallow bound reaches the
 *  common `specs/<feature>/.rauf/` layout without walking the whole tree. */
const SCAN_MAX_DEPTH = 5;

/** Path of the registry mirror for a runner state directory. */
export function mirrorPath(stateDir: string): string {
	return join(stateDir, MIRROR_NAME);
}

/** Read the mirrored task for a state dir, or null if absent/unreadable/corrupt.
 *  A corrupt mirror is treated as "no task" rather than throwing — a half-written
 *  file must never wedge session startup. */
export function readMirror(stateDir: string): SupervisorTask | null {
	const path = mirrorPath(stateDir);
	if (!existsSync(path)) return null;
	try {
		const parsed = JSON.parse(readFileSync(path, "utf8")) as Partial<SupervisorTask>;
		if (
			parsed &&
			typeof parsed.stateDir === "string" &&
			typeof parsed.eventsFile === "string" &&
			typeof parsed.backlogDir === "string"
		) {
			return {
				backlogDir: parsed.backlogDir,
				stateDir: parsed.stateDir,
				eventsFile: parsed.eventsFile,
				launchedAt: typeof parsed.launchedAt === "string" ? parsed.launchedAt : "",
				total: typeof parsed.total === "number" ? parsed.total : undefined,
				eventsIno: typeof parsed.eventsIno === "number" ? parsed.eventsIno : undefined,
				lastSeq: typeof parsed.lastSeq === "number" ? parsed.lastSeq : -1,
				closed: parsed.closed === true,
			};
		}
	} catch {
		// fall through — corrupt mirror is "no task"
	}
	return null;
}

/** Persist the task mirror atomically (write-temp + rename), creating the state
 *  dir if the launcher raced ahead of the runner. */
export function writeMirror(task: SupervisorTask): void {
	const path = mirrorPath(task.stateDir);
	try {
		// Stamp the CURRENT events-file inode so a later session can tell whether the
		// file was rotated (a new run) while it was away — see SupervisorTask.eventsIno.
		let eventsIno = task.eventsIno;
		try {
			eventsIno = statSync(task.eventsFile).ino;
		} catch {
			// events file not present yet — keep whatever the task carried (if any)
		}
		const record: SupervisorTask = { ...task, eventsIno };
		mkdirSync(dirname(path), { recursive: true });
		const tmp = `${path}.tmp-${process.pid}`;
		writeFileSync(tmp, `${JSON.stringify(record, null, 2)}\n`, "utf8");
		renameSync(tmp, path);
	} catch {
		// Best-effort durability; a failed mirror write must not break the tool.
	}
}

/** Remove the mirror (on an explicit stop of a task the session owns). */
export function clearMirror(stateDir: string): void {
	try {
		rmSync(mirrorPath(stateDir), { force: true });
	} catch {
		// best-effort
	}
}

/**
 * Find every supervised-task mirror under `root`, so a BRAND-NEW Pi session (a
 * fresh session file with no `forge-loop-task` entry of its own) can still
 * rediscover and reattach to a loop a previous session launched. Bounded, cheap,
 * and failure-tolerant: skips heavy directories, caps depth, and treats any
 * unreadable dir or corrupt mirror as absent rather than throwing.
 */
export function discoverMirrors(root: string): SupervisorTask[] {
	const found: SupervisorTask[] = [];
	const walk = (dir: string, depth: number): void => {
		if (depth > SCAN_MAX_DEPTH) return;
		let entries: import("node:fs").Dirent[];
		try {
			entries = readdirSync(dir, { withFileTypes: true });
		} catch {
			return;
		}
		for (const entry of entries) {
			if (entry.isFile() && entry.name === MIRROR_NAME) {
				const task = readMirror(dir); // mirror lives AT <stateDir>/<MIRROR_NAME>
				if (task) found.push(task);
			} else if (entry.isDirectory() && !SKIP_DIRS.has(entry.name)) {
				walk(join(dir, entry.name), depth + 1);
			}
		}
	};
	walk(root, 0);
	return found;
}
