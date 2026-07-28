/**
 * Secondary install placements (A4b) — the second-root generalization the single-`destination`
 * install model can't express. Two kinds (see {@link PlacementKind}):
 *   - "mirror"        — codex copies the bundle's `agents/*.toml` FLAT into `.codex/agents/`, where
 *                       Codex loads custom agents (it does NOT read them from `.agents/skills`).
 *   - "managed-block" — copilot writes a sentinel-delimited pointer block into the (possibly
 *                       user-owned) `.github/copilot-instructions.md`, preserving the rest of it.
 *
 * This module is PURE: it resolves declarative {@link PlacementSpec}s to absolute roots, selects the
 * mirror source files, and provides the managed-block string transforms (render/upsert/remove/read).
 * The planner (plan.ts) decides actions and the apply engine (apply.ts) executes them; neither knows
 * the per-kind string mechanics — those live here. Zero runtime dependencies; only `node:` built-ins.
 */

import * as path from "node:path";
import {
  MANAGED_BLOCK_END,
  MANAGED_BLOCK_START,
  type AgentTarget,
  type PlacementKind,
  type PlacementSpec,
  type ResolveOpts,
  type Scope,
} from "./types.js";
import { resolveRoots } from "./agent-targets.js";
import type { LocatedSource } from "./source.js";

/** A {@link PlacementSpec} resolved to absolute paths under a scope. Pure derivation; nothing stored. */
export interface ResolvedPlacement {
  readonly kind: PlacementKind;
  /** Absolute containment boundary (REQ-SEC-02): `<scopeRoot>/<spec.baseDir>`. */
  readonly root: string;
  /** Absolute destination: a DIR ("mirror") or a FILE ("managed-block"): `<root>/<spec.subpath>`. */
  readonly destination: string;
  readonly spec: PlacementSpec;
}

/**
 * Resolve every secondary placement declared on `target` to absolute roots under `scope` (A4b).
 * Returns `[]` for agents with no placements (claude/cursor/gemini). Pure; the single derivation
 * point so a new rule stays one `AGENT_TARGETS` edit (REQ-SCALE-01).
 */
export function resolvePlacements(
  target: AgentTarget,
  scope: Scope,
  opts?: ResolveOpts,
): ResolvedPlacement[] {
  const roots = resolveRoots(opts);
  const scopeRoot = scope === "global" ? roots.home : roots.cwd;
  return (target.placements ?? []).map((spec) => {
    // Scope-aware second root: pi mirrors into `~/.pi/agent/agents` (global) but `.pi/agents`
    // (project), which one `baseDir` string cannot express. Fall back to `baseDir` for the common
    // case (codex/copilot) where the second root is scope-invariant.
    const baseDir = (scope === "global" ? spec.globalBaseDir : spec.projectBaseDir) ?? spec.baseDir;
    const root = path.resolve(scopeRoot, baseDir);
    return { kind: spec.kind, root, destination: path.resolve(root, spec.subpath), spec };
  });
}

/** One selected mirror source: the bundle-relative source and its FLAT destination basename. */
export interface MirrorFile {
  readonly srcRelpath: string;
  readonly destRelpath: string;
  readonly srcHash: string;
}

/**
 * Select the bundle files a "mirror" placement copies (A4b): every `source.files` entry whose
 * POSIX relpath starts with `spec.sourcePrefix`, copied FLAT (basename only) into the destination.
 * Sorted by destination basename for deterministic plans. Pure.
 */
export function selectMirrorFiles(source: LocatedSource, spec: PlacementSpec): MirrorFile[] {
  const prefix = spec.sourcePrefix ?? "";
  return source.files
    .filter((f) => f.relpath.startsWith(prefix))
    .map((f) => ({ srcRelpath: f.relpath, destRelpath: path.posix.basename(f.relpath), srcHash: f.sha256 }))
    .sort((a, b) => (a.destRelpath < b.destRelpath ? -1 : a.destRelpath > b.destRelpath ? 1 : 0));
}

// ---------------------------------------------------------------------------
// Managed-block string transforms (pure)
// ---------------------------------------------------------------------------

/**
 * Render the managed-block BODY (without sentinels) for copilot (A4b). Points Copilot — which has no
 * skills loader — at the staged bundle under `.github/feature-forge/` and lists the available skills.
 * Deterministic given the bundle's skill ids. Pure.
 */
export function renderCopilotBlock(skills: readonly string[]): string {
  const lines = [
    "# feature-forge",
    "",
    "The feature-forge skill suite is installed in this repository under",
    "`.github/feature-forge/`. GitHub Copilot has no skills loader, so consult those files",
    "directly when a feature-forge workflow is requested.",
    "",
    "Each skill lives at `.github/feature-forge/skills/<name>/SKILL.md`. Available skills:",
    "",
    ...[...skills].sort().map((s) => `- ${s}`),
    "",
    "Shared references are under `.github/feature-forge/references/`; helper scripts under",
    "`.github/feature-forge/scripts/`.",
  ];
  return lines.join("\n");
}

/** Wrap a rendered block body in the managed sentinels — the exact region written on disk. */
export function wrapBlock(body: string): string {
  return `${MANAGED_BLOCK_START}\n${body}\n${MANAGED_BLOCK_END}`;
}

/**
 * Extract the full managed region (sentinels INCLUDED) currently present in `content`, or `null` if
 * no well-formed `start…end` region exists. The region is what `wrapBlock` produces, so its hash is
 * directly comparable to a freshly rendered block. Pure.
 */
export function extractManagedRegion(content: string): string | null {
  const startIdx = content.indexOf(MANAGED_BLOCK_START);
  if (startIdx === -1) return null;
  const endIdx = content.indexOf(MANAGED_BLOCK_END, startIdx + MANAGED_BLOCK_START.length);
  if (endIdx === -1) return null;
  return content.slice(startIdx, endIdx + MANAGED_BLOCK_END.length);
}

/**
 * Insert or replace the managed block in `existing`, preserving all user content outside the
 * sentinels (A4b). If a region exists it is replaced in place; otherwise the block is appended after
 * the existing content (separated by a blank line). `existing` is `""` for a not-yet-created file.
 * The result always ends with a single trailing newline. Pure.
 */
export function upsertBlock(existing: string, body: string): string {
  const region = wrapBlock(body);
  const current = extractManagedRegion(existing);
  if (current !== null) {
    return ensureTrailingNewline(existing.replace(current, region));
  }
  if (existing.trim() === "") return ensureTrailingNewline(region);
  return ensureTrailingNewline(`${existing.replace(/\n+$/, "")}\n\n${region}`);
}

/**
 * Remove the managed block from `existing`, preserving the rest (A4b uninstall). Returns the
 * remaining content (trailing whitespace trimmed to a single newline), or `""` if nothing but the
 * block (and whitespace) remains — the caller deletes the file in that case. Pure.
 */
export function removeBlock(existing: string): string {
  const region = extractManagedRegion(existing);
  if (region === null) return existing;
  const without = existing.replace(region, "").replace(/\n{3,}/g, "\n\n").trim();
  return without === "" ? "" : `${without}\n`;
}

/** Ensure exactly one trailing newline. */
function ensureTrailingNewline(s: string): string {
  return `${s.replace(/\n+$/, "")}\n`;
}
