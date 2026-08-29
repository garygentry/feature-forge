// GENERATED — DO NOT EDIT. Source: adapter-src/pi/extensions/forge-loop-supervisor/tailer.ts
// Regenerate with: python3 scripts/build-adapters.py
/**
 * NdjsonTailer — a rotation-aware, malformed-tolerant tail of an append-only
 * NDJSON file, decoupled from any watch mechanism so it is unit-testable by
 * driving {@link NdjsonTailer.poll} against a temp file.
 *
 * rauf is the single writer of `events.ndjson` and rotates it at the START of
 * each run — the old file is moved to `<stateDir>/archive/{ts}-events.ndjson`
 * and a fresh empty file takes its place (rauf `packages/core/src/events-log.ts`).
 * So a live supervisor must survive the file being replaced by name mid-watch.
 * Two independent signals catch a rotation: the file's inode changing, and its
 * size shrinking below our read cursor. Either resets the cursor to 0 and
 * re-reads from the top of the new file.
 *
 * Reads are incremental from a byte offset (never re-reading the whole file), a
 * trailing partial line with no newline yet is buffered until its newline
 * arrives, and a line that is not valid JSON is skipped rather than throwing —
 * a half-flushed or corrupt record must never stall the tail.
 */

import { closeSync, openSync, readSync, statSync } from "node:fs";

import type { RaufEvent } from "./types.js";

export class NdjsonTailer {
	private offset = 0;
	private ino: number | null = null;
	private partial = "";

	/**
	 * @param filePath  Absolute path to the NDJSON file (may not exist yet).
	 * @param onRecord  Called once per successfully-parsed JSON line, in order.
	 * @param onError   Optional; called with a short reason when a line is
	 *                  skipped as malformed (for observability/tests).
	 */
	constructor(
		private readonly filePath: string,
		private readonly onRecord: (rec: RaufEvent) => void,
		private readonly onError?: (reason: string) => void,
	) {}

	/**
	 * Read whatever is new since the last poll and dispatch each complete record.
	 * Idempotent and cheap when nothing changed. Safe to call before the file
	 * exists (no-op) and across a rotation (resets and re-reads the new file).
	 */
	poll(): void {
		let size: number;
		let ino: number;
		try {
			const st = statSync(this.filePath);
			size = st.size;
			ino = st.ino;
		} catch {
			// File gone (pre-launch, or mid-rotation between unlink and recreate).
			// Reset so the next existing file is read from its start.
			this.offset = 0;
			this.ino = null;
			this.partial = "";
			return;
		}

		// Rotation: a new inode, or the file shrank below our cursor (truncate /
		// replace). Re-read from the top of whatever file is there now.
		if ((this.ino !== null && ino !== this.ino) || size < this.offset) {
			this.offset = 0;
			this.partial = "";
		}
		this.ino = ino;

		if (size <= this.offset) return; // nothing new

		let chunk: string;
		let fd: number | null = null;
		try {
			fd = openSync(this.filePath, "r");
			const length = size - this.offset;
			const buf = Buffer.allocUnsafe(length);
			const read = readSync(fd, buf, 0, length, this.offset);
			chunk = buf.subarray(0, read).toString("utf8");
			this.offset += read;
		} catch {
			return; // transient read failure; try again next poll
		} finally {
			if (fd !== null) closeSync(fd);
		}

		this.partial += chunk;
		const lines = this.partial.split("\n");
		// The last element is an incomplete trailing line (empty when the chunk
		// ended on a newline) — hold it until its newline arrives.
		this.partial = lines.pop() ?? "";

		for (const line of lines) {
			const trimmed = line.trim();
			if (!trimmed) continue;
			let rec: RaufEvent;
			try {
				rec = JSON.parse(trimmed) as RaufEvent;
			} catch {
				this.onError?.(`skipped malformed NDJSON line (${trimmed.length} chars)`);
				continue;
			}
			if (rec && typeof rec === "object") this.onRecord(rec);
		}
	}
}
