/**
 * Shared types for the forge-loop-supervisor Pi extension.
 *
 * The extension launches a rauf loop in rauf's own detached/server-managed mode
 * (`rauf loop run . --backlog <dir> --detached`), which returns immediately and
 * leaves the loop running inside rauf's server daemon — so the loop outlives the
 * Pi session by design. The supervisor then watches rauf's native, single-writer
 * event stream (`<stateDir>/events.ndjson`), turning routine milestones into
 * quiet deterministic progress and waking the session only on the events that
 * need a human or the loop's own close-out.
 *
 * These types are host-agnostic on purpose: the core (classification, the NDJSON
 * tailer, the task registry) takes a {@link SupervisorHost} so it can be unit
 * tested with a fake host and a temp file, exactly as the vendored
 * ask-user-question extension decouples its questionnaire from the live TUI.
 */

/** A rauf persisted loop event. Only the fields this extension reads are typed;
 *  every record also carries `timestamp`, `projectPath`, and a per-run `seq`
 *  (rauf `packages/core/src/schemas.ts`). Unknown/extra fields are preserved. */
export interface RaufEvent {
	type: string;
	seq?: number;
	timestamp?: string;
	itemId?: string;
	title?: string;
	reason?: string;
	silentMs?: number;
	completedCount?: number;
	blockedCount?: number;
	needsHumanCount?: number;
	[key: string]: unknown;
}

/** How the supervisor treats one event.
 *  - `progress`: a routine per-item milestone → one quiet deterministic line, NO
 *    model turn.
 *  - `exception`: something a human should see now (needs-human, block, stuck,
 *    review failure, error, cancellation) → notify AND wake the session.
 *  - `terminal`: the run finished → wake the session so the loop stage resumes
 *    its post-run steps.
 *  - `ignore`: firehose/interior events the supervisor does not surface. */
export type EventClass = "progress" | "exception" | "terminal" | "ignore";

/** Durable identity of one supervised loop, persisted so a later Pi session can
 *  reattach to a still-running (or already-finished) loop without relaunching. */
export interface SupervisorTask {
	/** Backlog directory passed to `--backlog` (the forge {backlogDir}). */
	backlogDir: string;
	/** The runner state directory holding events.ndjson (default `<backlogDir>/.rauf`). */
	stateDir: string;
	/** Absolute path to the watched event file (`<stateDir>/events.ndjson`). */
	eventsFile: string;
	/** ISO timestamp of the launch (for display + staleness reasoning). */
	launchedAt: string;
	/** Total backlog items at launch, when known — enables the `[N/M]` progress
	 *  line. Absent when the launcher could not count the backlog. */
	total?: number;
	/** Highest event `seq` already surfaced — the dedup cursor across reattach. */
	lastSeq: number;
	/** Whether the supervisor has already surfaced a terminal event for this task. */
	closed: boolean;
}

/** The narrow surface the pure core needs from its host (pi, or a test stub).
 *  Everything the supervisor does to the outside world goes through this, so the
 *  core carries no pi import and is unit-testable. */
export interface SupervisorHost {
	/** A non-turn, user-visible line (routine progress + startup/info). */
	notify(message: string, level: "info" | "warning" | "error"): void;
	/** Wake the active session with a message that triggers a model turn when
	 *  idle (pi `sendMessage(..., { triggerTurn: true })`). Used ONLY for
	 *  exception and terminal events — never routine progress. */
	wake(message: string): void;
	/** Persist the task record durably (pi `appendEntry` + a file mirror). */
	persist(task: SupervisorTask): void;
	/** Current time as ISO-8601, injectable for deterministic tests. */
	now(): string;
}
