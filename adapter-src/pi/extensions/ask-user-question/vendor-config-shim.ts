/**
 * FEATURE-FORGE VENDOR PATCH — local stand-in for `@juicesharp/rpiv-config`.
 *
 * Upstream `config.ts` imports three symbols from `@juicesharp/rpiv-config`
 * (316 LOC, its only hard dependency). Feature-forge vendors this package to
 * keep `adapters/pi/` dependency-free, so those three symbols are supplied
 * here instead:
 *
 * - `GuidanceFields` / `validateGuidanceFields` — copied verbatim from
 *   rpiv-config@2.1.0 `config.ts:180-221`.
 * - `loadJsonConfigWithLegacyFallback` — upstream reads user JSON config from
 *   `~/.config/rpiv-ask-user-question/config.json` so users can override the
 *   tool's LLM-facing guidance. Feature-forge pins its own guidance instead:
 *   the skills are written against these exact strings, so a user override
 *   would silently change how the pipeline's interview stages behave. This
 *   returns the fixed feature-forge config and never touches the filesystem.
 */

export interface GuidanceFields {
	promptSnippet?: string;
	promptGuidelines?: string[];
}

/** Verbatim from rpiv-config@2.1.0 (config.ts:207). */
export function validateGuidanceFields(fields: unknown): GuidanceFields {
	if (!fields || typeof fields !== "object") return {};
	const g = fields as Record<string, unknown>;
	const result: GuidanceFields = {};
	if (typeof g.promptSnippet === "string" && g.promptSnippet.length > 0) {
		result.promptSnippet = g.promptSnippet;
	}
	if (
		Array.isArray(g.promptGuidelines) &&
		g.promptGuidelines.length > 0 &&
		g.promptGuidelines.every((s) => typeof s === "string" && s.length > 0)
	) {
		result.promptGuidelines = g.promptGuidelines;
	}
	return result;
}

/**
 * Feature-forge's pinned guidance, replacing upstream's user-config load.
 *
 * Carried over from `adapter-src/pi/ask-user-question.ts` with one wording fix:
 * upstream appends a `Type something.` row rather than an `Other` option, and
 * reserves the literal label `Other`, so the guideline names the behaviour
 * rather than the Claude label.
 */
const FEATURE_FORGE_CONFIG = {
	guidance: {
		promptSnippet: "Ask the user structured multiple-choice questions and return Claude-shaped answers.",
		promptGuidelines: [
			"Use AskUserQuestion only for genuine user decisions or requirements clarification.",
			"AskUserQuestion accepts 1-4 questions with 2-4 options each; the UI appends a custom free-text row automatically — never author an option labelled \"Other\".",
			"Use AskUserQuestion multiSelect only when several options can validly apply together.",
		],
	},
};

export function loadJsonConfigWithLegacyFallback<T>(_name: string, _file: string = "config.json"): T {
	return FEATURE_FORGE_CONFIG as T;
}
