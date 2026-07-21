# Vendor-Construct Inventory

> Feature: `forge-skill-spec-purity` (epic `agent-agnostic`, target repo **feature-forge**).
> Source of truth: `PRD.md` (v1) + `tech-spec.md` (v1).
> This file is the REQ-VND-03 audit output — the single, exhaustive record of every vendor-specific
> construct found across all 11 skills and their `references/`, each with exactly one disposition.

## Disposition Legend

Every disposition cell in the inventory below is exactly one member of the closed `Disposition`
vocabulary defined in `00-core-definitions.md` §8. No free-form values are permitted.

| Disposition | Meaning |
|---|---|
| `relocated` | Moved to a spec-allowed location (e.g. `metadata`). |
| `removed` | Deleted from canon (none expected in this tree). |
| `preserved-as-spec-allowed` | Kept as-is; already spec-legal. |
| `out-of-canon` | Kept but documented as non-canonical (e.g. `hooks/hooks.json`). |
| `routed-through-resolver` | `${CLAUDE_PLUGIN_ROOT}` replaced by the bootstrap prelude + `scripts/forge-root.sh`. |

## Inventory

| Construct | Locations / count | Disposition | Rationale / notes |
|---|---|---|---|
| `argument-hint` (top-level frontmatter key) | 10 `skills/*/SKILL.md` (all skills **except** `forge-init`) | `relocated` | Claude-specific vendor key (constraint C-2). Moved verbatim to `metadata.argument-hint` per REQ-VND-01 (see `02-frontmatter-purity-and-inventory.md` §2). Value byte-identical; `description` untouched. |
| `${CLAUDE_PLUGIN_ROOT}` — canonical invocations + prose | 23 occurrences across 9 canonical surfaces: `skills/forge-0-epic/SKILL.md` (12), `skills/forge/SKILL.md` (3), `skills/forge-5-loop/SKILL.md` (1), `skills/forge-6-docs/SKILL.md` (1), `skills/forge-init/SKILL.md` (1), `skills/forge-verify/SKILL.md` (1), `skills/forge-verify/references/verification-checklists.md` (1), `references/shared-conventions.md` (2), `agents/forge-verifier.md` (1) | `routed-through-resolver` | Claude-only env var. Routed through the byte-identical bootstrap prelude + `scripts/forge-root.sh` per REQ-RES-03. Mechanics owned by `03-portable-root-resolver.md`; recorded here for audit completeness. |
| `${CLAUDE_PLUGIN_ROOT}` — sanctioned residual | 1 occurrence in `scripts/forge-root.sh` (env-fallback, REQ-RES-02 step 3) | `preserved-as-spec-allowed` | The single sanctioned residual: the resolver's documented Claude-compat fallback (REQ-RES-03 / REQ-RES-05). Exempt from the residual-var scan (`00-core-definitions.md` §6 `RESIDUAL_VAR_EXEMPT`). |
| `${CLAUDE_PLUGIN_ROOT:-}` — bootstrap-prelude first-hint (Chunk 2b) | 1 occurrence per prelude across every canonical stamp site (the byte-pinned `BOOTSTRAP_PRELUDE`) | `preserved-as-spec-allowed` | The prelude's first resolver candidate — exact, glob-free root resolution on any Claude layout; expands to empty and is skipped when unset. Rule 3 allows it by stripping the byte-pinned prelude before its scan (detection is by `${CLAUDE_PLUGIN_ROOT` prefix, so the `:-}` default form is not an escape hatch elsewhere). `forge-agent-adapters-build` translates it to `${FEATURE_FORGE_ROOT:-}` in non-Claude bundles. |
| `${CLAUDE_PLUGIN_ROOT}` — in `hooks/hooks.json` | 1 occurrence in `hooks/hooks.json` | `out-of-canon` | Non-canonical Claude artifact (REQ-VND-04). Not a canonical surface; exempt from the REQ-RES-03 scan. Left in place. |
| `hooks/hooks.json` SessionStart wiring | 1 file (`hooks/hooks.json`) — Claude `SessionStart` → `bash ${CLAUDE_PLUGIN_ROOT}/scripts/session-check.sh` | `out-of-canon` | Claude-specific plugin hook wiring (REQ-VND-04, decision D3). Preserved + documented so `forge-agent-adapters-build` treats it as a Claude artifact, not portable canon. |
| (contingency) any other vendor invocation directive | none found in the audit | — | REQ-VND-02 contingency did not fire (see Notes). If one is later surfaced, add a row with `removed` or `out-of-canon` per `02-frontmatter-purity-and-inventory.md` §3. |

## Notes

- **REQ-VND-02 contingency did not fire.** The exhaustive audit found **no** Codex / Copilot /
  Cursor / Gemini invocation directive — and no other agent-specific run-this command block — in any
  skill body or frontmatter. The only vendor constructs in scope across the suite are the three
  recorded above: `argument-hint`, `${CLAUDE_PLUGIN_ROOT}`, and the `hooks/hooks.json` SessionStart
  wiring. Treating REQ-VND-02 as a contingency rather than an action item is therefore correct.
- **`${CLAUDE_PLUGIN_ROOT}` relocation mechanics** — the prelude replacement, the resolver, and the
  canonical-surface routing — are owned by `03-portable-root-resolver.md`; this file only records the
  inventory dispositions.
- **The closed `Disposition` vocabulary** is defined in `00-core-definitions.md` §8; the legend above
  reproduces it so this file is self-contained for a downstream reader.
- The two surviving `${CLAUDE_PLUGIN_ROOT}` instances (the `forge-root.sh` env fallback and the
  `hooks/hooks.json` literal) are written here as descriptive text in code spans so they are not
  routable invocations and do not trip the spec-purity checker's residual-var rule, consistent with
  how `02-frontmatter-purity-and-inventory.md` §5 records them.
</content>
</invoke>
