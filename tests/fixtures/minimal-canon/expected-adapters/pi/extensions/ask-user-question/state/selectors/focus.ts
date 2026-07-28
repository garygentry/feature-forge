// GENERATED — DO NOT EDIT. Source: adapter-src/pi/extensions/ask-user-question/state/selectors/focus.ts
// Regenerate with: python3 scripts/build-adapters.py
import type { ActiveView } from "../../view/stateful-view.js";

/**
 * Discriminated focus selector — single source of truth for "which view owns
 * focus this tick?" Priority order matches the dispatcher cascade
 * (`key-router.ts`) and the reducer's defensive clears (`state-reducer.ts`).
 *
 * Priority: notes > submit > options.
 */
export function selectActiveView(
	state: { notesVisible: boolean; currentTab: number },
	totalQuestions: number,
): ActiveView {
	if (state.notesVisible) return "notes";
	if (state.currentTab === totalQuestions) return "submit";
	return "options";
}
