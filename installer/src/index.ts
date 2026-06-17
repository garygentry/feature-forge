/**
 * Library barrel (spec 01 §4): the public surface of the cross-agent installer as a Node
 * library. Re-exports the agent-detection-map surface, the rauf pin, and the shared spec-00
 * types. Named exports only; no runtime logic of its own.
 */

// The agent-detection-map surface (spec 02).
export {
  AGENT_TARGETS,
  resolveRoots,
  destinationFor,
  detectAgent,
  detectAgents,
  formatZeroDetection,
} from "./agent-targets.js";

// The pinned default loop-runner coordinate (spec 06).
export { RAUF_PIN } from "./rauf.js";

// The shared types (spec 00-core-definitions).
export type {
  AgentId,
  AgentTarget,
  DetectionResult,
  ResolveOpts,
  Scope,
  Mode,
  InstallManifest,
  PlannedAction,
  RunReport,
} from "./types.js";
