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

import { existsSync, mkdirSync, readFileSync, renameSync, rmSync, statSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";

import type { SupervisorTask } from "./types.js";

/** Path of the registry mirror for a runner state directory. */
export function mirrorPath(stateDir: string): string {
	return join(stateDir, ".forge-supervisor.json");
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
