/**
 * LoopSupervisor — the host-agnostic core that turns a stream of rauf events
 * into the right user-facing behavior, with exactly-once reporting across
 * session restarts.
 *
 * Reporting rule (issue #236):
 *   - routine `item_completed` → one quiet deterministic line, no model turn;
 *   - exception (`needs_human` / block / stuck / review-failed / error /
 *     cancellation) → notify AND wake the session;
 *   - terminal (`loop_completed` / error / cancelled) → wake the session so the
 *     loop stage runs its post-run close-out, then stop watching.
 *
 * Dedup + reattach: every rauf record carries a monotonic per-run `seq`. A task
 * persists the highest `seq` it has already surfaced (`lastSeq`). When a fresh
 * Pi session reattaches, its tailer re-reads events.ndjson from the top; records
 * with `seq <= lastSeq` are REPLAYED SILENTLY — they still rebuild the in-memory
 * `done` counter, but they are never re-notified — while records past `lastSeq`
 * are surfaced live. That is what lets a restart reconcile a running loop without
 * duplicate reports.
 *
 * Duplicate watchers are prevented by keying active tasks on their stateDir: a
 * second `attach` for the same stateDir returns the existing handle.
 */

import { classifyEvent, formatProgress, formatSignal } from "./events.js";
import type { RaufEvent, SupervisorHost, SupervisorTask } from "./types.js";

/** A live watch handle the host drives: `poll()` on file change, `close()` on
 *  teardown. Reattach-safe and idempotent. */
export interface TaskHandle {
	poll(): void;
	close(): void;
	readonly stateDir: string;
}

interface ActiveTask {
	task: SupervisorTask;
	/** Running count of completed items, rebuilt from replayed history. */
	done: number;
	/** Highest item_completed seq already counted into `done` — guards the counter
	 *  against a re-read double-count independently of the notify cursor. */
	doneCursor: number;
	/** Total backlog items, when the launcher recorded it (`task.total`). */
	total?: number;
	closed: boolean;
}

export class LoopSupervisor {
	private readonly active = new Map<string, ActiveTask>();

	constructor(private readonly host: SupervisorHost) {}

	/** Whether a task for this stateDir is already being supervised. */
	isActive(stateDir: string): boolean {
		return this.active.has(stateDir);
	}

	/** Snapshot of the current progress for a task (for the status tool). */
	progress(stateDir: string): { done: number; total?: number; closed: boolean } | null {
		const a = this.active.get(stateDir);
		return a ? { done: a.done, total: a.total, closed: a.closed } : null;
	}

	/**
	 * Begin (or reattach) supervision of one task. The returned handle's `poll`
	 * feeds new NDJSON records through {@link handleRecord}; the host is expected
	 * to call it on file-change and once immediately (to replay history). A
	 * second attach for the same stateDir is a no-op that returns the live handle
	 * — the dedup guard against duplicate watchers.
	 *
	 * @param makeReader  Builds a reader (typically an NdjsonTailer bound to
	 *   `task.eventsFile`) whose `poll` dispatches each parsed record to `onRecord`.
	 */
	attach(
		task: SupervisorTask,
		makeReader: (
			onRecord: (rec: RaufEvent) => void,
			onRotate: () => void,
		) => { poll(): void },
	): TaskHandle {
		const existing = this.active.get(task.stateDir);
		if (existing) return this.handleFor(task.stateDir);

		const entry: ActiveTask = {
			task: { ...task },
			done: 0,
			doneCursor: -1,
			total: task.total,
			closed: task.closed,
		};
		this.active.set(task.stateDir, entry);
		const reader = makeReader(
			(rec) => this.handleRecord(task.stateDir, rec),
			() => this.handleRotate(task.stateDir),
		);
		return {
			stateDir: task.stateDir,
			poll: () => reader.poll(),
			close: () => this.detach(task.stateDir),
		};
	}

	/** Stop tracking a task in memory (watcher teardown / stop). Does NOT touch
	 *  the detached runner — the loop is server-owned and outlives the session. */
	detach(stateDir: string): void {
		this.active.delete(stateDir);
	}

	/** Process one parsed rauf record for a task: dedup, classify, dispatch. */
	private handleRecord(stateDir: string, rec: RaufEvent): void {
		const entry = this.active.get(stateDir);
		if (!entry) return;
		const seq = typeof rec.seq === "number" ? rec.seq : null;
		const alreadySeen = seq !== null && seq <= entry.task.lastSeq;
		const cls = classifyEvent(rec);

		// Count completed items for the [N/M] line. Guard against double-counting a
		// replayed item: only count when its seq is past the counter's cursor. On a
		// fresh attach the cursor is -1 so the whole history counts; on a re-read of
		// the same run (a spurious re-poll) already-counted items are skipped. A
		// genuine new run arrives via handleRotate, which resets the cursor first.
		if (rec.type === "item_completed") {
			if (seq === null || seq > entry.doneCursor) {
				entry.done += 1;
				if (seq !== null) entry.doneCursor = seq;
			}
		}

		if (alreadySeen) return; // replayed history — rebuilt state, never re-notify

		let surfaced = true;
		switch (cls) {
			case "progress":
				this.host.notify(formatProgress(rec, entry.done, entry.total), "info");
				break;
			case "exception":
				this.host.notify(formatSignal(rec), "warning");
				this.host.wake(formatSignal(rec));
				break;
			case "terminal":
				this.host.notify(formatSignal(rec), "info");
				this.host.wake(formatSignal(rec));
				entry.closed = true;
				entry.task.closed = true;
				break;
			case "ignore":
				surfaced = false;
				break;
		}

		// Advance the cursor and persist ONLY for a surfaced event. A firehose
		// (`ignore`) event must not trigger a disk write + session entry per record
		// (rauf emits many per second); ignored events re-classify as `ignore` on
		// any later replay, so not persisting their seq is harmless. A terminal
		// event persists `closed`, letting a later session know the run is done.
		if (surfaced && seq !== null && seq > entry.task.lastSeq) {
			entry.task.lastSeq = seq;
			this.host.persist({ ...entry.task });
		}
	}

	/** A rotation was detected (rauf started a new run — event `seq` restarts at
	 *  0). Reset the per-run cursor and counters so the new run is surfaced from
	 *  its start instead of being swallowed by the previous run's high-water seq. */
	private handleRotate(stateDir: string): void {
		const entry = this.active.get(stateDir);
		if (!entry) return;
		entry.task.lastSeq = -1;
		entry.doneCursor = -1;
		entry.done = 0;
		entry.closed = false;
		entry.task.closed = false;
		this.host.persist({ ...entry.task });
	}

	private handleFor(stateDir: string): TaskHandle {
		return {
			stateDir,
			poll: () => {},
			close: () => this.detach(stateDir),
		};
	}
}
