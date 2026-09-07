// GENERATED — DO NOT EDIT. Source: adapter-src/pi/extensions/forge-invocation-args/wiring.ts
// Regenerate with: python3 scripts/build-adapters.py
/**
 * Pi wiring for forge-invocation-args — the injectable, unit-testable core of the
 * extension. All logic lives here behind a structural {@link PiLike} so the whole
 * thing is driven by a fake pi in test (mirroring how forge-loop-supervisor is
 * tested headlessly). index.ts supplies the real ExtensionAPI.
 *
 * WHY THIS EXISTS (issue #303): Pi expands `/skill:<name> <args>` by appending the
 * raw args after the `</skill>` block with only a bare `\n\n` separator — no
 * semantic boundary. Pi's docs say args arrive as `User: <args>`, but the
 * implementation has bare-appended since Pi v0.50.0 (commit 7868b25a2), true
 * through the installed 0.84.4 and tested 0.85.1. With no boundary, a model can
 * read a forge feature-name argument as trailing prose and wrongly trip
 * feature-forge's "no feature name → STOP and ask" rule. The feature name keys
 * directory resolution, branch naming, and every pipeline-state write, so losing
 * it silently is high-impact.
 *
 * THE FIX: hook Pi's `input` event, which fires BEFORE skill/template expansion
 * (and after extension-command dispatch — `/skill:` is not an extension command,
 * so it reaches us). For a `/skill:forge*` invocation we rewrite the input to
 * `/skill:<name> <envelope>`, wrapping the raw argument string in an explicit,
 * versioned envelope. Pi then expands the skill and appends the envelope as args
 * — verified against Pi's `_expandSkillCommand`: skill name is the text up to the
 * first space, args are the ENTIRE remainder (newlines preserved) end-trimmed, so
 * a multiline entity-escaped envelope survives re-parse. We keep Pi's built-in
 * expansion rather than replicating its private skill-block wrapper (which would
 * drift across versions).
 *
 * pi surface used: `pi.on("input", handler)` returning an `InputEventResult`
 * (`continue` | `transform`), and `ctx.ui.notify` for the fail-loud path.
 */

/** The envelope element name and its schema version. Consumers (the forge skill
 *  bodies, via references/shared-conventions.md) read the feature name from
 *  <arguments> and treat an empty element as "no feature name supplied". */
export const ENVELOPE_TAG = "feature-forge-invocation";
export const ENVELOPE_VERSION = "1";

/** Matches a feature-forge skill command and captures its (un-namespaced) name.
 *  Pi package skills register as `/skill:<name>` with NO `<pkg>:` prefix; the
 *  forge names are `forge` and `forge-<...>`. The `(?=\s|$)` boundary keeps this
 *  from matching an unrelated skill like `/skill:forgery`. */
const FORGE_SKILL_RE = /^\/skill:(forge(?:-[a-z0-9-]+)?)(?=\s|$)/;

/** Result subset this extension ever returns (a strict subset of Pi's
 *  InputEventResult — we never return `handled`, which would skip the agent). */
export type InputResult = { action: "continue" } | { action: "transform"; text: string };

interface InputEventLike {
	text: string;
	source?: string;
	streamingBehavior?: string;
}
interface UiLike {
	notify?(message: string, level?: "info" | "warning" | "error"): void;
}
interface CtxLike {
	ui?: UiLike;
}

/** Minimal structural shape of the pi API this wiring needs. Kept loose so the
 *  fake pi in tests satisfies it without importing pi; index.ts adapts the real
 *  ExtensionAPI to it (a renamed/removed `on` becomes a compile error there). */
export interface PiLike {
	on(
		event: string,
		handler: (event: InputEventLike, ctx: CtxLike) => InputResult | Promise<InputResult>,
	): void;
}

/** Entity-escape the three XML metacharacters. Total and lossless: every input is
 *  representable, and a literal `</arguments>` in the raw args becomes
 *  `&lt;/arguments&gt;`, which cannot close the real element (no injection). `&`
 *  must be replaced first so already-escaped output is not double-escaped. Flags,
 *  quotes, and newlines pass through untouched. */
export function escapeXml(value: string): string {
	return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/** Build the versioned invocation envelope for a matched forge skill. `skillName`
 *  is a kebab token (no escaping needed); `rawArgs` is entity-escaped. Zero args
 *  yields an empty <arguments> element — the deterministic "no feature name"
 *  signal. */
export function buildEnvelope(skillName: string, rawArgs: string): string {
	return (
		`<${ENVELOPE_TAG} version="${ENVELOPE_VERSION}">\n` +
		`  <skill>${skillName}</skill>\n` +
		`  <arguments>${escapeXml(rawArgs)}</arguments>\n` +
		`</${ENVELOPE_TAG}>`
	);
}

/**
 * Pure normalization: given raw input text, return the transform (for a matched
 * `/skill:forge*` command) or `continue` (for everything else). Exported so it can
 * be unit-tested directly. Parses the command the same way Pi does — name = the
 * matched forge token, args = the entire remainder, trimmed — so the rewritten
 * text re-expands identically.
 */
export function normalizeInput(text: string): InputResult {
	const match = FORGE_SKILL_RE.exec(text);
	if (!match) return { action: "continue" };

	const skillName = match[1];
	const rawArgs = text.slice(match[0].length).trim();

	// Idempotency: input handlers chain (each sees the prior's output), and a
	// resend could re-enter here. Never wrap an already-enveloped invocation.
	if (rawArgs.startsWith(`<${ENVELOPE_TAG}`)) return { action: "continue" };

	const envelope = buildEnvelope(skillName, rawArgs);
	return { action: "transform", text: `/skill:${skillName} ${envelope}` };
}

/**
 * Register the single `input` handler on `pi`. Returns nothing; all behavior is
 * in the handler and the pure helpers above.
 */
export function createExtension(pi: PiLike): void {
	pi.on("input", (event, ctx) => {
		// Only normalize user-typed ("interactive") and API ("rpc") input.
		// Extension-injected messages ("extension", via sendUserMessage) are
		// dispatched with expandPromptTemplates:false and never expand, so there is
		// no boundary bug to fix — and rewriting a programmatic message could corrupt
		// it. This mirrors Pi's own input-transform example.
		if (event?.source === "extension") return { action: "continue" };

		try {
			return normalizeInput(event.text);
		} catch (error) {
			// Fail LOUDLY, never silently. A thrown input handler makes the Pi runner
			// log the error and continue with the ORIGINAL untransformed text — which
			// would silently reintroduce the dropped-argument bug this extension exists
			// to prevent. So we surface it via notify and pass the input through
			// unchanged rather than throwing. (Entity-escaping makes this path
			// effectively unreachable; it is defense in depth.)
			const message = error instanceof Error ? error.message : String(error);
			try {
				ctx?.ui?.notify?.(
					`forge-invocation-args: could not normalize a /skill:forge invocation (${message}); passing it through unchanged.`,
					"error",
				);
			} catch {
				/* headless / no notify surface */
			}
			return { action: "continue" };
		}
	});
}
