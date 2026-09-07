// GENERATED — DO NOT EDIT. Source: adapter-src/pi/extensions/forge-invocation-args/index.ts
// Regenerate with: python3 scripts/build-adapters.py
/**
 * forge-invocation-args — a first-party Pi compatibility extension that gives
 * `/skill:forge-*` invocation arguments an explicit, versioned semantic boundary
 * before Pi's skill expansion drops it (issue #303). See wiring.ts for the full
 * rationale and mechanics.
 *
 * The pi-facing glue is thin: all logic lives in the injectable {@link
 * createExtension} factory (wiring.ts), unit-tested with a fake pi. This file
 * adapts the real ExtensionAPI to the structural PiLike the wiring consumes — each
 * member is accessed by name off the concrete `pi`, so a method renamed or removed
 * in a future pi is a COMPILE error here rather than a silent runtime failure.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

import { createExtension, type InputResult, type PiLike } from "./wiring.js";

export default function (pi: ExtensionAPI) {
	const piLike: PiLike = {
		on: (event, handler) =>
			(
				pi.on as unknown as (
					e: string,
					h: (ev: unknown, ctx: unknown) => InputResult | Promise<InputResult>,
				) => void
			)(event, handler as (ev: unknown, ctx: unknown) => InputResult | Promise<InputResult>),
	};
	createExtension(piLike);
}
