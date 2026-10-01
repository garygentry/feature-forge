/**
 * codex-hook — wire rauf's Codex Stop hook into the user's Codex config (#346).
 *
 * Codex cannot wake a model when a background process prints or exits, so a Codex session
 * supervising a rauf loop that ends its turn leaves the loop unwatched. rauf ≥ 0.18.0 ships
 * `rauf hook codex-stop`, a Stop hook that blocks the session from ending its turn while a loop
 * it supervises still runs (and lets go otherwise — it is inert for sessions that never touch
 * rauf). This module adds that hook to `$CODEX_HOME/hooks.json` (default `~/.codex/hooks.json`).
 *
 * It is a write to the user's GLOBAL Codex config, outside any install's bundle, so it happens
 * only with explicit consent — the `--codex-stop-hook` flag — and never for `--yes` alone. The write is additive and idempotent: existing hooks are kept,
 * and an already-wired file is left untouched. Uninstall does not remove it (it is not a
 * manifest-tracked bundle file, and it is harmless without rauf markers).
 */

import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";

/** The command the hook runs (rauf ≥ 0.18.0). */
export const CODEX_STOP_HOOK_COMMAND = "rauf hook codex-stop";

/** The hooks.json entry added under `hooks.Stop` — identical to `rauf hook codex-stop --print-config`. */
export const CODEX_STOP_HOOK_ENTRY = {
  hooks: [{ type: "command", command: CODEX_STOP_HOOK_COMMAND, timeout: 30 }],
} as const;

/** Outcome of the Stop-hook step, carried on the run report. */
export interface CodexStopHookReport {
  readonly status: "wired" | "already-wired" | "not-offered" | "failed";
  /** The hooks.json this step read (and, when `wired`, wrote). */
  readonly hooksPath: string;
  /** One human line for the report. */
  readonly message: string;
  /** Whether `[features] hooks = true` was found in Codex's config.toml. */
  readonly hooksFeatureEnabled: boolean;
}

/** `$CODEX_HOME`, else `<home>/.codex`. */
export function codexHome(opts: { home?: string; env?: NodeJS.ProcessEnv } = {}): string {
  const env = opts.env ?? process.env;
  return env.CODEX_HOME && env.CODEX_HOME.trim() !== ""
    ? env.CODEX_HOME
    : join(opts.home ?? homedir(), ".codex");
}

type HooksDoc = { hooks?: { Stop?: unknown } & Record<string, unknown> } & Record<string, unknown>;

function readHooks(path: string): { ok: true; doc: HooksDoc } | { ok: false; message: string } {
  if (!existsSync(path)) return { ok: true, doc: {} };
  try {
    const parsed: unknown = JSON.parse(readFileSync(path, "utf8"));
    if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
      return { ok: false, message: `${path} is not a JSON object` };
    }
    return { ok: true, doc: parsed as HooksDoc };
  } catch (e) {
    return { ok: false, message: `${path} is not valid JSON (${(e as Error).message})` };
  }
}

/** Whether a hooks document already runs `rauf hook codex-stop` on Stop. */
export function hasStopHook(doc: HooksDoc): boolean {
  const groups = doc.hooks?.Stop;
  if (!Array.isArray(groups)) return false;
  return groups.some(
    (g) =>
      g !== null &&
      typeof g === "object" &&
      Array.isArray((g as { hooks?: unknown }).hooks) &&
      ((g as { hooks: unknown[] }).hooks).some(
        (h) =>
          h !== null &&
          typeof h === "object" &&
          String((h as { command?: unknown }).command ?? "").includes("hook codex-stop"),
      ),
  );
}

/** Whether Codex's config.toml enables hooks (`hooks = true` under `[features]`). */
export function hooksFeatureEnabled(home: string): boolean {
  try {
    const toml = readFileSync(join(home, "config.toml"), "utf8");
    const features = /^\[features\][^\n]*\n([\s\S]*?)(?=^\[|(?![\s\S]))/m.exec(toml);
    return features !== null && /^\s*hooks\s*=\s*true\b/m.test(features[1] ?? "");
  } catch {
    return false;
  }
}

/** Current state, without writing: is the hook wired, and where is the file. */
export function inspectCodexStopHook(home: string): { hooksPath: string; wired: boolean; error?: string } {
  const hooksPath = join(home, "hooks.json");
  const read = readHooks(hooksPath);
  if (!read.ok) return { hooksPath, wired: false, error: read.message };
  return { hooksPath, wired: hasStopHook(read.doc) };
}

/**
 * Add the Stop hook to `<home>/hooks.json` (creating it if absent). Additive: every existing
 * key and hook is kept; an already-wired file is not rewritten. Atomic (temp + rename).
 */
export function wireCodexStopHook(home: string): CodexStopHookReport {
  const hooksPath = join(home, "hooks.json");
  const feature = hooksFeatureEnabled(home);
  const read = readHooks(hooksPath);
  if (!read.ok) {
    return { status: "failed", hooksPath, hooksFeatureEnabled: feature, message: `not wired: ${read.message}` };
  }
  if (hasStopHook(read.doc)) {
    return { status: "already-wired", hooksPath, hooksFeatureEnabled: feature, message: `already wired in ${hooksPath}` };
  }
  const doc: HooksDoc = { ...read.doc };
  const hooks: Record<string, unknown> =
    doc.hooks && typeof doc.hooks === "object" && !Array.isArray(doc.hooks) ? { ...doc.hooks } : {};
  const stop = Array.isArray(hooks.Stop) ? [...(hooks.Stop as unknown[])] : [];
  stop.push(structuredClone(CODEX_STOP_HOOK_ENTRY));
  hooks.Stop = stop;
  doc.hooks = hooks;
  try {
    mkdirSync(dirname(hooksPath), { recursive: true });
    const tmp = `${hooksPath}.tmp-${process.pid}`;
    writeFileSync(tmp, JSON.stringify(doc, null, 2) + "\n", "utf8");
    renameSync(tmp, hooksPath);
  } catch (e) {
    return { status: "failed", hooksPath, hooksFeatureEnabled: feature, message: `not wired: ${(e as Error).message}` };
  }
  return {
    status: "wired",
    hooksPath,
    hooksFeatureEnabled: feature,
    message: `added a Stop hook (\`${CODEX_STOP_HOOK_COMMAND}\`) to ${hooksPath}`,
  };
}
