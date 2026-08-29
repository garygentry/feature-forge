/**
 * Event classification + display formatting — pure functions over one rauf event.
 *
 * The classification mirrors the coverage-complete filter the generic
 * forge-5-loop contract arms on Claude (`Monitor` on events.ndjson): every
 * terminal and exception state is surfaced (silence is never success), while
 * routine milestones stay quiet. See rauf's event union in
 * `packages/core/src/schemas.ts` for the authoritative field list.
 */

import type { EventClass, RaufEvent } from "./types.js";

/** Events that mean "the run is over" — the supervisor wakes the session so the
 *  loop stage runs its post-run close-out (Steps 4–7), then stops watching. */
const TERMINAL = new Set(["loop_completed", "loop_error", "loop_cancelled"]);

/** Events a human must see immediately. `loop_paused` carries `reason` and only
 *  the needs-human pause is surfaced here (the runner sets the item aside and
 *  keeps going — it is not a full stop). Everything else in this set is an
 *  unconditional exception. */
const EXCEPTION = new Set([
	"needs_human",
	"item_blocked",
	"llm_stuck_warning",
	"review_failed",
]);

/** The single routine milestone that earns a quiet progress line. */
const PROGRESS = new Set(["item_completed"]);

/** Classify one event. Unknown/interior/firehose types (token updates, tool
 *  activity, iteration boundaries, review start, usage-limit chatter, …) are
 *  `ignore` — the supervisor never surfaces them. */
export function classifyEvent(evt: RaufEvent): EventClass {
	const type = evt?.type;
	if (typeof type !== "string") return "ignore";
	if (TERMINAL.has(type)) return "terminal";
	if (EXCEPTION.has(type)) return "exception";
	// `loop_paused` is an exception ONLY when it is the needs-human pause.
	if (type === "loop_paused" && evt.reason === "needs_human") return "exception";
	if (PROGRESS.has(type)) return "progress";
	return "ignore";
}

/** A concise, deterministic one-line report for a routine `item_completed`.
 *  `done`/`total` are threaded in when known so the line reads `[3/10] …`. */
export function formatProgress(
	evt: RaufEvent,
	done?: number,
	total?: number,
): string {
	const count =
		typeof done === "number" && typeof total === "number" ? `[${done}/${total}] ` : "";
	const title = typeof evt.title === "string" && evt.title ? evt.title : evt.itemId ?? "item";
	return `${count}forge loop: completed ${title}`;
}

/** A human-facing line for an exception or terminal event, used both for the
 *  toast and for the wake message that triggers the session's next turn. */
export function formatSignal(evt: RaufEvent): string {
	switch (evt.type) {
		case "needs_human":
			return `forge loop: item ${evt.itemId ?? "?"} needs a human — ${evt.reason ?? "no reason given"}`;
		case "loop_paused":
			return `forge loop: paused for human input on ${evt.itemId ?? "an item"}`;
		case "item_blocked":
			return `forge loop: item ${evt.itemId ?? "?"} blocked — ${evt.reason ?? "no reason given"}`;
		case "llm_stuck_warning":
			return `forge loop: item ${evt.itemId ?? "?"} looks stuck (no output for ${Math.round((evt.silentMs ?? 0) / 1000)}s)`;
		case "review_failed":
			return `forge loop: review failed — ${evt.reason ?? "no reason given"}`;
		case "loop_error":
			return `forge loop: the run errored — ${evt.reason ?? "see the runner log"}`;
		case "loop_cancelled":
			return "forge loop: the run was cancelled";
		case "loop_completed": {
			const done = evt.completedCount ?? 0;
			const blocked = evt.blockedCount ?? 0;
			const needsHuman = evt.needsHumanCount ?? 0;
			const parts = [`${done} done`];
			if (blocked) parts.push(`${blocked} blocked`);
			if (needsHuman) parts.push(`${needsHuman} need a human`);
			return `forge loop: run complete — ${parts.join(", ")}. Read the authoritative counts (status --json) and run the post-run close-out.`;
		}
		default:
			return `forge loop: ${evt.type}`;
	}
}
