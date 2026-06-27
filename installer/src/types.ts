/**
 * Shared type system, error hierarchy, and constants for the cross-agent installer.
 *
 * This module is the foundation: every other module imports the types, constants, and
 * `Result` defined here and does not redefine them (spec 00-core-definitions). Named
 * exports only; `node:` built-ins only where applicable; zero runtime dependencies.
 */

// ---------------------------------------------------------------------------
// 1. Primitive aliases and enumerations
// ---------------------------------------------------------------------------

/**
 * The five coding agents this installer targets (REQ-DET-01). Order is the canonical
 * iteration order used by detection, planning, and reporting so output is deterministic.
 */
export const AGENT_IDS = ["claude", "codex", "copilot", "cursor", "gemini"] as const;

/** A supported coding-agent identifier. */
export type AgentId = (typeof AGENT_IDS)[number];

/**
 * Install scope (REQ-FLAG-02). `"project"` (default) installs into the current project's
 * agent dir (e.g. `./.claude/skills/feature-forge/`); `"global"` installs into the
 * user-level dir (e.g. `~/.claude/skills/feature-forge/`).
 */
export type Scope = "project" | "global";

/**
 * Materialization mode (REQ-FLAG-03). `"copy"` is the default and the only mode on Windows;
 * `"symlink"` links the whole namespace dir to the source bundle (opt-in via `--symlink`).
 */
export type Mode = "copy" | "symlink";

/** The four invocable subcommands (aliases resolved before this type, spec 07). */
export type Subcommand = "install" | "update" | "uninstall" | "list";

/** Process exit codes (REQ-OBS-01/03, spec 07). */
export const EXIT = { SUCCESS: 0, FAILURE: 1, USAGE: 2 } as const;
export type ExitCode = (typeof EXIT)[keyof typeof EXIT];

/**
 * Manifest schema version. v2 (A4b) adds the optional `placements[]` array for agents whose
 * install spans a second filesystem root (codex `.codex/agents`, copilot `.github/copilot-
 * instructions.md`). A v1 manifest (no `placements`) is still read verbatim by the back-compat
 * reader — bumped only on a breaking manifest-shape change.
 */
export const SCHEMA_VERSION = 2 as const;

/** Versions of the manifest this installer can READ (write is always SCHEMA_VERSION). */
export const READABLE_SCHEMA_VERSIONS = [1, 2] as const;

/** A manifest schemaVersion this installer accepts on read (back-compat v1 + current v2). */
export type ReadableSchemaVersion = (typeof READABLE_SCHEMA_VERSIONS)[number];

/** The single namespace directory name written inside each agent's install location [D5]. */
export const FEATURE_FORGE_NS = "feature-forge" as const;

/** Filename prefix for the hidden parent-sibling manifest, completed by the scope (§3, spec 05). */
export const MANIFEST_PREFIX = ".feature-forge." as const;

// ---------------------------------------------------------------------------
// 2. The agent detection map contract (`AgentTarget`)
// ---------------------------------------------------------------------------

/**
 * How honestly an agent's install paths track current vendor docs (Finding 6 / A4).
 * - "confirmed"        — source-verified end-to-end (claude).
 * - "verified-current" — matches the vendor's current docs, re-verified in A0 (2026-06-26).
 * - "best-known"       — plausible but not doc-confirmed for this scope; install proceeds,
 *                        labeled honestly in the report so users know it may not be loaded.
 * - "unsupported"      — no usable install surface; not installed (reserved; none today).
 */
export type Confidence = "confirmed" | "verified-current" | "best-known" | "unsupported";

/** How an agent consumes the bundle (documentation + future per-kind apply behavior). */
export type InstallKind = "skills" | "extension" | "rules" | "instructions";

/**
 * Kind of a SECONDARY install placement (A4b). The primary bundle (the `feature-forge/` namespace
 * dir) is always present and is never a placement; placements describe extra writes under a
 * DIFFERENT filesystem root than the primary bundle:
 * - "mirror"        — copy a subset of bundle files flat into a second dir (codex `.codex/agents/`,
 *                     where Codex loads custom agents — it does not read them from `.agents/skills`).
 * - "managed-block" — write/merge a sentinel-delimited block into a (possibly user-owned) instructions
 *                     file (copilot `.github/copilot-instructions.md`), preserving the rest of the file.
 */
export type PlacementKind = "mirror" | "managed-block";

/** HTML-comment sentinels delimiting a `managed-block` placement (mirrors rauf's convention). */
export const MANAGED_BLOCK_START = "<!-- feature-forge:managed:start -->" as const;
export const MANAGED_BLOCK_END = "<!-- feature-forge:managed:end -->" as const;

/**
 * Declarative descriptor of one secondary placement on an {@link AgentTarget} (A4b). Pure data, so a
 * new agent (or a new second-root rule) stays one table edit (REQ-SCALE-01). The absolute root and
 * destination are derived under a scope by {@link resolvePlacements}; nothing here is stored.
 */
export interface PlacementSpec {
  readonly kind: PlacementKind;
  /** Second-root dir under the scope root, e.g. ".codex" (mirror) or ".github" (managed-block). */
  readonly baseDir: string;
  /**
   * Path under `baseDir`. For "mirror" this is the destination DIR (e.g. "agents"); for
   * "managed-block" this is the target FILE (e.g. "copilot-instructions.md").
   */
  readonly subpath: string;
  /**
   * "mirror" only: bundle-relative prefix selecting which source files to copy (e.g. "agents/").
   * Files matching the prefix are copied FLAT (basename only) into the placement destination.
   */
  readonly sourcePrefix?: string;
}

/**
 * One row of the static per-agent detection map (REQ-DET-01, REQ-DET-05). Adding a new
 * agent is exactly adding one entry to `AGENT_TARGETS` — no logic change (REQ-SCALE-01).
 *
 * The on-disk destination for an agent under a given scope is derived, not stored:
 *   <scopeRoot>/<installBaseDir>/<installSubpath>/<FEATURE_FORGE_NS>/
 * where scopeRoot is the resolved home (global) or cwd (project), and `installSubpath` may
 * be "" (installed directly under `installBaseDir`). Detection (`configDirName`) is decoupled
 * from the install location because some agents load content from a different tree than the
 * dir that signals their presence (A4): codex detects ".codex" but loads skills from
 * ".agents/skills"; copilot detects ".copilot" but instructions live under ".github".
 */
export interface AgentTarget {
  /** Stable agent identifier. */
  readonly id: AgentId;
  /**
   * Basename of the agent's config directory, probed for detection (REQ-DET-02),
   * e.g. ".claude", ".codex", ".cursor". Detection is `stat` on this dir, never a subprocess.
   */
  readonly configDirName: string;
  /**
   * Top-level dir under the scope root that holds the install AND is the containment boundary
   * every write is checked against (REQ-SEC-02). Usually equals `configDirName`; decoupled for
   * codex (".agents") and copilot (".github").
   */
  readonly installBaseDir: string;
  /**
   * Path under `installBaseDir` to the namespace parent, e.g. "skills" (claude/codex),
   * "rules" (cursor), "extensions" (gemini), "" (copilot — directly under `.github`).
   */
  readonly installSubpath: string;
  /** How this agent consumes the bundle (REQ-SCALE-01; per-kind placement extended in A4b). */
  readonly installKind: InstallKind;
  /**
   * Informational: the skill-file form this agent's bundle uses — "SKILL.md" (claude, codex),
   * "<name>.md" (copilot/gemini), "<name>.mdc" (cursor). The installer copies the
   * bundle verbatim (REQ-SCALE-02) and does not parse skill files, so this is documentation.
   */
  readonly skillFileForm: string;
  /** Confidence for the default (global) scope. */
  readonly confidence: Confidence;
  /** Optional scope-specific override for project scope (e.g. gemini project = best-known). */
  readonly projectConfidence?: Confidence;
  /** Current vendor/docs URL for this target's install convention (surfaced in reports). */
  readonly docsUrl: string;
  /**
   * Secondary install placements under a DIFFERENT root than the primary bundle (A4b). Absent for
   * agents whose whole install is the single namespace dir (claude/cursor/gemini). Declarative data
   * only — resolved to absolute roots by {@link resolvePlacements}; a new rule is one table edit.
   */
  readonly placements?: readonly PlacementSpec[];
}

/** Options for path resolution, injectable so tests never touch the real `~` (spec 02, spec 08). */
export interface ResolveOpts {
  /** Home dir for global scope. Default: `os.homedir()`. */
  readonly home?: string;
  /** Working dir for project scope. Default: `process.cwd()`. */
  readonly cwd?: string;
  /** Active scope. Default: `"project"`. */
  readonly scope?: Scope;
}

// ---------------------------------------------------------------------------
// 3. Detection result and install manifest
// ---------------------------------------------------------------------------

/**
 * One agent's detection outcome (REQ-DET-02/04). Returned by `detectAgent`/`detectAgents`
 * (spec 02) and the data half of the `agent-detection-map` surface (REQ-DET-05).
 */
export interface DetectionResult {
  readonly agent: AgentId;
  /** True iff the agent's config dir is present (primary signal, REQ-DET-02). */
  readonly detected: boolean;
  /** Every config dir probed — named verbatim in the zero-detection report (REQ-DET-04). */
  readonly configDirsProbed: string[];
  /** Secondary, advisory only: whether the agent's CLI is on PATH (never the detection signal). */
  readonly cliOnPath?: boolean;
  /** Resolved absolute install destination for the active scope (the `feature-forge/` namespace dir). */
  readonly destination: string;
  /** Effective confidence for the active scope (REQ-DET-05; honest dry-run/list labeling, A4). */
  readonly confidence: Confidence;
  /** Current vendor/docs URL for this target (REQ-DET-05). */
  readonly docsUrl: string;
}

/** One file recorded in the manifest inventory (REQ-SAFE-01). */
export interface ManifestFile {
  /** Path relative to the manifest's `destination`. */
  readonly path: string;
  /** SHA-256 of the written bytes. Omitted for symlink mode (no per-file copy exists). */
  readonly sha256?: string;
}

/**
 * One persisted SECONDARY placement (manifest v2, A4b). Records the absolute second root + dest and
 * an inventory of what we wrote there, so `update`/`uninstall` reconcile it exactly like the primary
 * bundle but under its own containment boundary (`root`). For "managed-block", `files` holds a single
 * entry whose `path` is the file basename and whose `sha256` fingerprints the block region we wrote
 * (drift/clean detection); the rest of that file is user-owned and never recorded.
 */
export interface Placement {
  readonly kind: PlacementKind;
  /** Absolute containment boundary every write for this placement is checked against (REQ-SEC-02). */
  readonly root: string;
  /** Absolute destination: a DIR ("mirror") or a FILE ("managed-block"). */
  readonly destination: string;
  /** Per-file inventory written under this placement (paths relative to `destination`'s dir). */
  readonly files: ManifestFile[];
}

/**
 * The persisted per-install manifest (REQ-SAFE-01/03), written as the hidden parent-sibling
 * `<installSubdir>/.feature-forge.<scope>.json` (spec 05). It is the sole record `list`/`update`/
 * `uninstall` use to tell installer-written content from user content and to detect drift.
 */
export interface InstallManifest {
  /** Always {@link SCHEMA_VERSION} when written; v1 is still accepted on read (back-compat). */
  readonly schemaVersion: ReadableSchemaVersion;
  readonly agent: AgentId;
  readonly scope: Scope;
  readonly mode: Mode;
  /** Absolute path of the `feature-forge/` namespace dir this manifest governs. */
  readonly destination: string;
  /**
   * Bundle version coordinate. **`null` today** — the consumed `adapters/` bundles carry no
   * version (no plugin.json / version header; gemini's `gemini-extension.json` version is a
   * `0.0.0` placeholder). Recording a real value is deferred to the generator under OQ-A/IR-1;
   * C-3 forbids the installer reading outside `adapters/` to synthesize one.
   */
  readonly featureForgeVersion: string | null;
  /** SHA-256 over the source bundle's canonical (sorted-path) file set — drift anchor (OQ-4, spec 03). */
  readonly sourceHash: string;
  /** Pinned rauf coordinate recorded at install, e.g. "@garygentry/rauf@0.10.1"; `null` if `--skip-rauf` (spec 06). */
  readonly raufPin: string | null;
  /** ISO-8601 timestamps. */
  readonly installedAt: string;
  readonly updatedAt: string;
  /** Installed skill ids (the bundle's `skills/*` dir names). */
  readonly skills: string[];
  /** Per-file inventory (copy mode); `sha256` omitted in symlink mode. */
  readonly files: ManifestFile[];
  /** Symlink mode only: the source bundle the namespace dir links to (REQ-SAFE-02). */
  readonly link?: { readonly target: string };
  /**
   * Secondary placements written under a different root than the primary bundle (manifest v2, A4b).
   * Absent on agents without a second-root rule (claude/cursor/gemini) and on legacy v1 manifests.
   */
  readonly placements?: Placement[];
}

// ---------------------------------------------------------------------------
// 4. The plan model (dry-run engine output)
// ---------------------------------------------------------------------------

/**
 * The per-file action the planner assigns by diffing source ⇆ destination ⇆ manifest (spec 04).
 * - "create": destination file absent → will be written.
 * - "overwrite": clean prior file whose source bytes changed → will be refreshed.
 * - "skip-modified": destination locally modified (≠ recorded hash AND ≠ what we'd write)
 *   → left untouched and reported, unless `--force` (REQ-IDEM-02, REQ-FLAG-04).
 * - "unchanged": destination matches source → no write (REQ-IDEM-01).
 * - "remove": manifest records it but canon no longer has it → removed by `update` (REQ-OPS-02).
 */
export type FileActionKind =
  | "create"
  | "overwrite"
  | "skip-modified"
  | "unchanged"
  | "remove";

/** A single planned file action (REQ-OPS-05). */
export interface FileAction {
  /** Path relative to the agent's install destination. */
  readonly relpath: string;
  readonly action: FileActionKind;
}

/**
 * One agent's complete plan (REQ-OPS-05). `--dry-run` prints exactly this; a real run hands
 * the *same* `PlannedAction` to `apply` (spec 04), guaranteeing "dry-run = real run".
 */
export interface PlannedAction {
  readonly agent: AgentId;
  readonly scope: Scope;
  readonly mode: Mode;
  readonly files: FileAction[];
  /** Surfaced in the plan/report for visibility (spec 06); not a file action. */
  readonly raufPin?: string | null;
  /**
   * Resolved secondary-placement plans (A4b). Each carries its own absolute root + destination, the
   * per-file diff actions, and (for "managed-block") the exact block content a real run will write —
   * so dry-run shows, and `apply` performs, identical work. Absent when the agent has no placements.
   */
  readonly placements?: PlannedPlacement[];
}

/**
 * One secondary placement's resolved plan (A4b): the dry-run = real-run unit for a second root. The
 * planner fills `files` by diffing source ⇆ destination (same classifier as the primary bundle) and,
 * for "managed-block", attaches the rendered `blockContent` the apply step writes between sentinels.
 */
export interface PlannedPlacement {
  readonly kind: PlacementKind;
  /** Absolute containment boundary (REQ-SEC-02). */
  readonly root: string;
  /** Absolute destination dir ("mirror") or file ("managed-block"). */
  readonly destination: string;
  /**
   * Per-file diff actions. "mirror" entries carry `srcRelpath` (the bundle-relative source to copy);
   * "managed-block" has a single entry whose `relpath` is the file basename (no `srcRelpath`).
   */
  readonly files: PlacementFileAction[];
  /** "managed-block" only: the rendered block body (without sentinels) a create/overwrite writes. */
  readonly blockContent?: string;
}

/** A placement file action: a {@link FileAction} plus the bundle-relative source for "mirror" copies. */
export interface PlacementFileAction extends FileAction {
  /** "mirror" only: bundle-relative source path to copy into `<destination>/<relpath>`. */
  readonly srcRelpath?: string;
}

// ---------------------------------------------------------------------------
// 5. Reporting types
// ---------------------------------------------------------------------------

/** One agent's outcome in a run summary (REQ-OBS-01/03). */
export interface AgentReport {
  readonly agent: AgentId;
  readonly detected: boolean;
  /** False iff this agent's operation failed (others still proceed — REQ-OBS-03). */
  readonly ok: boolean;
  /** The actions performed (or planned, under `--dry-run`). */
  readonly actions: FileAction[];
  /** Present iff `ok` is false. */
  readonly error?: InstallerError;
  readonly raufPin?: string | null;
  /** Effective install-path confidence for the active scope (A4; honest report labeling). */
  readonly confidence?: Confidence;
  /** Vendor/docs URL for this target (A4; shown when confidence is not full). */
  readonly docsUrl?: string;
}

/** The whole-run summary, rendered human-readable or as `--json` (REQ-OBS-01, REQ-DET-05). */
export interface RunReport {
  readonly subcommand: Subcommand;
  readonly scope: Scope;
  readonly mode: Mode;
  readonly dryRun: boolean;
  readonly agents: AgentReport[];
  /** EXIT.SUCCESS unless any agent failed (FAILURE) or args were invalid (USAGE). */
  readonly exitCode: ExitCode;
  /**
   * Run-level rauf preflight failure (spec 07 §3.2): set when the install/update rauf
   * resolvability check failed. Skills still install (each `AgentReport.ok` stays true) but the
   * run `exitCode` is FAILURE and the renderer surfaces this message. Absent on success.
   *
   * This is the sanctioned run-level field spec 07 §3.2 permits in lieu of the `attachRaufError`
   * hook (see cli.ts run-report assembly). It is part of the `--json` machine surface
   * (REQ-DET-05): consumers reading `renderReport(report, { json: true })` see it verbatim.
   */
  readonly raufError?: InstallerError;
}

// ---------------------------------------------------------------------------
// 6. Constants — the `AGENT_TARGETS` table
// ---------------------------------------------------------------------------

/**
 * The static detection map (REQ-DET-01, REQ-SCALE-01). Keyed by AgentId; iteration order
 * follows `AGENT_IDS`. Paths for non-claude agents are "best-known" (TQ-1) — re-verify each
 * against the agent's current config-dir/skills-dir convention at implementation (OQ-B).
 *
 * Verified ground truth: every bundle has `skills/` (11 skills), `references/`,
 * `scripts/forge-root.sh`, `agents/`; gemini adds a root `gemini-extension.json`,
 * codex ships `skills/<name>/SKILL.md` + standalone `agents/<name>.toml` custom agents,
 * cursor uses `.mdc` files.
 *
 * A4 per-agent reality check (A0 re-verified vendor docs, 2026-06-26):
 *  - codex   — detects `.codex`, loads skills from `.agents/skills` (verified-current).
 *              The `.codex/agents/*.toml` second placement is added in A4b.
 *  - copilot — detects `.copilot`, but has no skills loader; the bundle is staged under
 *              `.github/feature-forge` and the managed instructions block (.github/
 *              copilot-instructions.md) is added in A4b (best-known).
 *  - cursor  — `.cursor/rules/*.mdc` confirmed current (verified-current).
 *  - gemini  — `~/.gemini/extensions/feature-forge` global confirmed; project scope is
 *              best-known (project extension install is not clearly documented).
 */
export const AGENT_TARGETS: Readonly<Record<AgentId, AgentTarget>> = {
  claude: { id: "claude", configDirName: ".claude", installBaseDir: ".claude", installSubpath: "skills", installKind: "skills", skillFileForm: "SKILL.md", confidence: "confirmed", docsUrl: "https://docs.claude.com/en/docs/claude-code/skills" },
  codex: { id: "codex", configDirName: ".codex", installBaseDir: ".agents", installSubpath: "skills", installKind: "skills", skillFileForm: "SKILL.md", confidence: "verified-current", docsUrl: "https://developers.openai.com/codex/skills", placements: [{ kind: "mirror", baseDir: ".codex", subpath: "agents", sourcePrefix: "agents/" }] },
  copilot: { id: "copilot", configDirName: ".copilot", installBaseDir: ".github", installSubpath: "", installKind: "instructions", skillFileForm: "<name>.md", confidence: "best-known", docsUrl: "https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions", placements: [{ kind: "managed-block", baseDir: ".github", subpath: "copilot-instructions.md" }] },
  cursor: { id: "cursor", configDirName: ".cursor", installBaseDir: ".cursor", installSubpath: "rules", installKind: "rules", skillFileForm: "<name>.mdc", confidence: "verified-current", docsUrl: "https://cursor.com/docs/context/rules" },
  gemini: { id: "gemini", configDirName: ".gemini", installBaseDir: ".gemini", installSubpath: "extensions", installKind: "extension", skillFileForm: "<name>.md", confidence: "verified-current", projectConfidence: "best-known", docsUrl: "https://github.com/google-gemini/gemini-cli/blob/main/docs/extensions/index.md" },
} as const;

/**
 * Minimal integrity check (REQ-OPS-06, spec 03): a located bundle is valid iff `skills/` is a
 * non-empty dir, the neutral bundle sentinel `.feature-forge-bundle.json` exists, every runtime
 * helper script a skill can invoke is present (so helper-backed skills run after install on ANY
 * agent), and — for gemini only — `gemini-extension.json` exists at the bundle root. Defined here
 * as data so the check is a localized table read.
 */
export const BUNDLE_REQUIRED_PATHS = {
  /** Required of every agent bundle. */
  common: [
    "skills",
    ".feature-forge-bundle.json",
    "scripts/forge-root.sh",
    "scripts/forge-init.sh",
    "scripts/epic-manifest.py",
    "scripts/validate-traceability.py",
    "scripts/forge-bootstrap.py",
  ] as const,
  /** Additional per-agent requirements. */
  perAgent: { gemini: ["gemini-extension.json"] } as Partial<Record<AgentId, readonly string[]>>,
} as const;

// ---------------------------------------------------------------------------
// 7. Error hierarchy and `Result`
// ---------------------------------------------------------------------------

/**
 * Stable error codes. Each maps to an actionable message form (REQ-OBS-02) and, at the CLI
 * boundary, an exit code (spec 07): USAGE → EXIT.USAGE (2); everything else → EXIT.FAILURE (1).
 */
export type ErrorCode =
  | "USAGE"            // unknown subcommand/flag/agent (REQ-DIST-03) → exit 2
  | "SOURCE_MISSING"   // detected agent but adapters/<agent>/ absent (REQ-OPS-06)
  | "SOURCE_INVALID"   // bundle fails the minimal integrity check (REQ-OPS-06)
  // LOCALLY_MODIFIED is report-vocabulary / remedy-text ONLY: it names the "destination drifted;
  // re-run with --force" remedy and is INTENTIONALLY never emitted as an InstallerError. The
  // drift-without-`--force` path is a per-file `skip-modified` FileAction that keeps the agent
  // `ok:true` and the run at exit SUCCESS (spec 04 §738) — never a failure. See report.ts
  // DEFAULT_REMEDY[LOCALLY_MODIFIED], surfaced via formatError, not via an emitted error.
  | "LOCALLY_MODIFIED" // destination drifted; needs --force (REQ-IDEM-02, REQ-FLAG-04)
  | "WRITE_DENIED"     // no write permission to a destination path (REQ-OBS-02)
  | "PATH_ESCAPE"      // a resolved destination escaped the agent root (REQ-SEC-02)
  | "RAUF_UNRESOLVABLE"// pinned rauf not resolvable from the registry (REQ-RAUF, spec 06)
  | "MANIFEST_CORRUPT" // existing manifest is unreadable/invalid JSON (spec 05)
  | "UNEXPECTED";      // caught exception fallback

/**
 * A structured, actionable installer error (REQ-OBS-02). `message` must name the agent, the
 * path, and the remedy where applicable; `remedy` optionally carries the suggested fix verbatim.
 */
export interface InstallerError {
  readonly code: ErrorCode;
  readonly message: string;
  readonly agent?: AgentId;
  readonly path?: string;
  readonly remedy?: string;
}

/** Result<T,E> — success carries a value; failure carries a structured error. */
export type Result<T, E = InstallerError> =
  | { readonly ok: true; readonly value: T }
  | { readonly ok: false; readonly error: E };

/** Success constructor. */
export const ok = <T>(value: T): Result<T, never> => ({ ok: true, value });

/** Failure constructor. */
export const err = <E>(error: E): Result<never, E> => ({ ok: false, error });

// ---------------------------------------------------------------------------
// 8. CLI flag model
// ---------------------------------------------------------------------------

/**
 * Parsed, normalized CLI flags (REQ-FLAG-01..05, REQ-DIST-02). Produced by `cli.ts` from
 * `node:util.parseArgs` (spec 07). `agent` undefined ⇒ all detected agents (REQ-DET-03).
 */
export interface CliFlags {
  readonly agent?: AgentId;
  readonly global: boolean;    // --global/-g (REQ-FLAG-02); false ⇒ project scope
  readonly symlink: boolean;   // --symlink (REQ-FLAG-03); ignored ⇒ copy on Windows
  readonly force: boolean;     // --force (REQ-FLAG-04)
  readonly dryRun: boolean;    // --dry-run (REQ-OPS-05)
  readonly yes: boolean;       // -y/--yes (REQ-DIST-02, REQ-FLAG-05)
  readonly json: boolean;      // --json (REQ-DET-05, REQ-OBS-01)
  readonly skipRauf: boolean;  // --skip-rauf (spec 06)
  readonly source?: string;    // hidden --source <dir> for tests (D7, spec 03)
}
