# First-Class GitHub Copilot Adapter Support

Status: Implementation in progress; native plugin foundation verified
Created: 2026-08-23
Owners: feature-forge maintainers
Target: GitHub Copilot in VS Code, Copilot CLI, and Copilot Agent Host

> **Tracking:** `unified-copilot-adaptation-plan.md` controls sequencing and completion. This file
> retains feature-forge design detail and local subtask status. See `README.md` before resuming.

## 1. Purpose

Extend feature-forge's generated Copilot adapter from its current instruction-only fallback into a first-class Copilot integration with:

- Native Agent Skills, including discovery, automatic loading, and slash invocation.
- Native custom agents with least-privilege tools and subagent delegation.
- Correct project and personal installation paths.
- A tested legacy Copilot-format plugin for managed distribution; Agent Plugins 1.0 is not claimed.
- Safe migration from the existing staged bundle and managed instruction block.
- Runtime verification in addition to byte-level generator and installer tests.

This is a planning document, not an implementation specification. Decisions and task status should be updated here as product behavior is verified and implementation work proceeds.

## 2. Current State

feature-forge has a spec-pure canonical source and deterministic adapter pipeline:

1. Canonical skills live under `skills/<name>/SKILL.md`.
2. Canonical agents live under `agents/<name>.md`.
3. `scripts/build-adapters.py` parses canon and emits target-specific trees under `adapters/`.
4. The npm installer deploys generated bundles using the target table in `installer/src/types.ts`.
5. `bash scripts/validate.sh` is the repository's complete verification gate.

The legacy Copilot path was designed around assumptions that are no longer true. As of the
2026-08-23 implementation session, generator output has been migrated to native skills/agents and a
plugin manifest, while installer placement and migration still use the legacy behavior:

- `CopilotEmitter` now writes native `skills/<name>/SKILL.md` and preserves `argument-hint`.
- Agents now emit as root `agents/<name>.agent.md` with fail-loud Copilot tool aliases,
  `user-invocable: false`, and `agents: []`; unsupported fields remain drop-recorded.
- `adapters/copilot/plugin.json` is generated at the bundle root and participates in version sync.
- The installer stages the whole bundle at `.github/feature-forge/`.
- A managed block in `.github/copilot-instructions.md` tells Copilot to consult that staged bundle manually.
- Copilot is labeled `best-known` because the implementation predates native skill and custom-agent support.

Copilot CLI 1.0.78 cached local installation discovers all 13 generated skills. A structured prompt
session discovers the three namespaced agents with no warnings/errors and the intended tool sets.
`--plugin-dir` loads agents but omits skills in this CLI version, so installation lifecycle tests are
the required skill-discovery proof.

The unified plan's 2026-08-23 support matrix sets Copilot CLI 1.0.78 and the VS Code
1.134.0/Copilot 0.62.0 pair as the initial floor, uses floor-plus-current revalidation, and limits
the initial full Copilot runtime claim to Linux x64 including WSL2. Cross-platform installer CI is
not treated as runtime discovery or process-control proof.

Current Copilot documentation now confirms these native surfaces:

| Capability | Project location | Personal location |
| --- | --- | --- |
| Skills | `.github/skills/<name>/SKILL.md` | `~/.copilot/skills/<name>/SKILL.md` |
| Custom agents | `.github/agents/*.agent.md` | `~/.copilot/agents/*.agent.md` |
| Instructions | `.github/copilot-instructions.md` or `AGENTS.md` | `~/.copilot/instructions/` |
| Agent plugins | Installed plugin root | `~/.copilot/installed-plugins/` via Copilot CLI |

Relevant upstream documentation:

- <https://code.visualstudio.com/docs/copilot/customization/agent-skills>
- <https://code.visualstudio.com/docs/copilot/customization/custom-agents>
- <https://code.visualstudio.com/docs/copilot/customization/agent-plugins>
- <https://code.visualstudio.com/docs/agents/run/subagents>
- <https://code.visualstudio.com/docs/agents/concepts/agent-host>

## 3. Goals

### G1. Native skills

Every canonical feature-forge skill is discoverable by Copilot as a native Agent Skill, can load automatically from its description, and can be invoked manually as a slash command.

### G2. Native agents

The canonical `forge-researcher`, `forge-spec-writer`, and `forge-verifier` roles are emitted as Copilot custom agents and can run as named subagents with appropriate tool restrictions.

### G3. Correct deployment

Project and personal installations use Copilot's documented discovery paths. A complete runtime bundle remains available for shared scripts and references.

### G4. Managed distribution

The generated Copilot adapter is a runtime-proven legacy Copilot-format package that can be installed
and managed through current Copilot and VS Code plugin flows. FORGE-101 deliberately selected this
narrower claim instead of migrating formats: the current five-field manifest declares root
`skills`/`agents` paths and has no Agent Plugins 1.0 `$schema`, so it is not Agent Plugins 1.0.

### G5. Safe migration

Updating an existing Copilot installation removes feature-forge's obsolete managed instruction block and old files only when ownership can be proved, without deleting or overwriting user-authored content.

### G6. Verified behavior

Tests prove generated structure and installer behavior, while a documented smoke matrix proves that Copilot actually discovers skills, invokes commands, runs custom agents, and resolves feature-forge runtime assets.

## 4. Non-Goals

- Rewriting the spec-pure canonical skills solely for Copilot.
- Making all Claude-only metadata semantically identical when Copilot has no equivalent.
- Requiring a fixed Copilot model for every installation.
- Adding MCP servers or lifecycle hooks unless a concrete feature-forge requirement emerges.
- Replacing the Claude marketplace installation path.
- Publishing automatically after merge. Releases remain manual and owner-gated.

## 5. Proposed Architecture

### 5.1 Generated plugin bundle

Selected legacy Copilot-format architecture (the Agent Plugins 1.0 schema/layout is explicitly out
of the current support claim):

```text
adapters/copilot/
  plugin.json
  .feature-forge-bundle.json
  skills/
    forge/
      SKILL.md
      references/
    forge-1-prd/
      SKILL.md
      references/
    ...
  agents/
    forge-researcher.agent.md
    forge-spec-writer.agent.md
    forge-verifier.agent.md
  references/
  scripts/
```

Portable skills and Copilot-specific agents live in their native root component directories. The root-level `references/` and `scripts/` preserve the existing complete runtime bundle and portable root-resolution contract.

### 5.2 Direct-install layout

The npm installer remains available for repository-local and personal installs.

Project scope:

```text
.github/
  skills/<skill>/SKILL.md
  agents/<agent>.agent.md
  feature-forge/
    .feature-forge-bundle.json
    references/
    scripts/
    ...
```

Personal scope:

```text
~/.copilot/
  skills/<skill>/SKILL.md
  agents/<agent>.agent.md
  feature-forge/
    .feature-forge-bundle.json
    references/
    scripts/
    ...
```

Native discovery files are mirrors owned by the installer manifest. The complete namespaced runtime bundle remains the stable root used by helper scripts and shared references.

### 5.3 Distribution-specific command names

Plugin-provided skills receive the plugin prefix and are invoked as `/feature-forge:<skill>`. Directly installed skills are invoked as `/<skill>`.

The implementation must not emit instructions that claim one form works in the other distribution. Choose one of these approaches during Phase 1:

1. Generate separate plugin and direct-install skill variants.
2. Translate command prose to a distribution-neutral form and document both invocation forms in a short Copilot overlay.
3. Make the npm installer deploy the plugin bundle through Copilot's plugin mechanism so only the prefixed form exists.

Selected direction: use the tested legacy Copilot plugin as the primary distribution and retain
direct-install output as an explicitly documented compatibility mode. Generated command prose uses
`invoke-skill: <name> [arguments]` notation; the Copilot overlay maps it to plugin
`/feature-forge:<name>` and direct `/<name>` forms without claiming either is universal.

### 5.4 Runtime root resolution

Skills require shared scripts and references beyond their individual directories. `scripts/forge-root.sh` remains the authoritative resolver and must recognize:

- The script's own plugin or runtime-bundle location.
- `${PLUGIN_ROOT}` where Copilot expands it.
- `${FEATURE_FORGE_ROOT}` as the host-neutral override.
- `~/.copilot/feature-forge`.
- `<workspace>/.github/feature-forge`.
- Copilot installed-plugin roots when self-location is unavailable.
- Project installs when a command runs from a workspace subdirectory.

Self-location and explicit environment roots should remain preferable to broad filesystem probes.

## 6. Metadata Mapping

### 6.1 Skills

| Canonical field | Copilot mapping | Policy |
| --- | --- | --- |
| `name` | `name` | Preserve; must match parent directory. |
| `description` | `description` | Preserve byte-for-byte after YAML decoding/encoding. |
| `metadata.argument-hint` | `argument-hint` | Preserve. |
| Body | `SKILL.md` body | Apply Copilot host-term and command translation. |
| Invocation defaults | Omit flags | Default to user-invocable and model-invocable. |
| `context` | Omit initially | Evaluate `fork` only with explicit per-skill evidence. |

### 6.2 Agents

| Canonical field | Copilot mapping | Initial policy |
| --- | --- | --- |
| `name` | `name` | Preserve exact identifier. |
| `description` | `description` | Preserve and retain delegation trigger phrases. |
| `tools` | `tools` | Translate through a fail-loud mapping table. |
| `model` | Omit/drop-record | Claude aliases are not portable Copilot model identifiers. |
| `maxTurns` | Omit/drop-record | No confirmed equivalent. |
| `effort` | Omit/drop-record | No confirmed equivalent. |
| `memory` | Omit/drop-record | No equivalent with the same semantics. |
| `skills` | Body link or mapped support | Ensure the verifier can load `forge-verify`; do not silently drop behavior. |
| Visibility | `user-invocable: false` | Pipeline workers remain available as subagents without picker clutter. |
| Subagent use | `agents: []` | Workers do not need nested delegation. |

Initial tool mapping:

| Canonical token | Copilot alias |
| --- | --- |
| `Read` | `read` |
| `Glob` | `search` |
| `Grep` | `search` |
| `Bash` | `execute` |
| `Write` | `edit` |

Unknown canonical tool tokens must fail generation with an actionable error rather than being silently removed.

## 7. Work Plan

### Phase 0: Capture requirements and fixtures

Status: In progress; schema/path evidence, fixtures, invocation strategy, and support matrix captured

- [ ] Create an implementation feature/epic using the normal forge pipeline.
- [x] Record the upstream Copilot schemas and paths as dated evidence in the unified implementation tracker.
- [x] Add minimal canonical fixtures that exercise every currently used skill and agent metadata field.
- [x] Define and runtime-prove the expected plugin tree; retain the documented direct-install tree for installer work.
- [x] Use plugin-prefixed commands for managed distribution, direct names for compatibility
  installs, and distribution-neutral generated transition prose with a short Copilot overlay.

Exit criteria:

- The expected Copilot file trees, supported metadata, unsupported metadata, and invocation names are explicit and testable.

### Phase 1: Native skill emission

Status: Complete locally; pending authorized commit/push durability in the execution tracker

Primary files:

- `scripts/build-adapters.py`
- `tests/test_build_adapters.py`
- `tests/test_adapter_host_neutrality.py`
- `tests/fixtures/minimal-canon/expected-adapters/copilot/`

Tasks:

- [x] Change Copilot skill output to `skills/<name>/SKILL.md`.
- [x] Preserve `argument-hint` instead of recording it as dropped.
- [x] Add supported Copilot keys to deterministic frontmatter ordering.
- [x] Add a Copilot-specific host overlay describing distribution-aware invocation plus the real question and subagent mechanisms.
- [x] Translate Claude marketplace commands into distribution-neutral `invoke-skill:` notation.
- [x] Ensure Copilot reference Markdown receives the same command translation as skill bodies.
- [x] Emit a Copilot-accepted legacy-format `plugin.json` with synchronized product version and metadata.
- [x] Narrow the supported distribution claim and user-facing terminology to the runtime-proven
      legacy Copilot format; do not claim Agent Plugins 1.0.
- [x] Update the generation report so only genuinely unsupported fields remain.

Exit criteria:

- Every Copilot skill has a valid folder/name match and `SKILL.md`.
- Argument hints round-trip.
- No generated Copilot skill tells the user to invoke an unavailable command.
- `python3 scripts/build-adapters.py --check` passes after regeneration.

### Phase 2: Native custom-agent emission

Status: In progress; native files and metadata verified, behavioral dispatch/dependency proof open

Primary files:

- `scripts/build-adapters.py`
- `agents/*.md`
- `tests/test_build_adapters.py`
- `tests/test_adapter_host_neutrality.py`

Tasks:

- [x] Emit root `agents/<name>.agent.md`, the current Copilot plugin layout.
- [x] Implement the canonical-to-Copilot tool alias map.
- [x] Fail generation on an unmapped tool token.
- [x] Set workers to `user-invocable: false` and `agents: []`.
- [x] Preserve descriptions and bodies with Copilot host-term translation.
- [ ] Resolve the verifier's `skills: [forge-verify]` dependency through a tested Copilot mechanism.
- [x] Drop-record `model`, `maxTurns`, `effort`, and `memory` with accurate reasons.
- [x] Verify that read-only agents cannot edit and that `forge-spec-writer` can edit; the tracked
      host-contract evidence records the runtime result. Durable dispatch-pattern and verifier-skill
      dependency proof remain open.

Exit criteria:

- All three agents appear in Copilot customization diagnostics.
- The main Copilot agent can select each worker by exact name.
- Tool access matches the canonical intent.
- Parallel researcher, writer, and verifier dispatch patterns work where requested by skills.

### Phase 3: Runtime asset resolution

Status: Not started; next feature-forge implementation phase after remaining native-agent residuals

Primary files:

- `scripts/forge-root.sh`
- Canonical skill bootstrap preludes
- Portable-root references and resolver tests

Tasks:

- [ ] Add Copilot personal and project runtime candidates.
- [ ] Use package self-location plus explicit `${FEATURE_FORGE_ROOT}` without weakening legacy Claude support; do not depend on `${PLUGIN_ROOT}` on the tested Copilot host.
- [ ] Add ancestor probing for project-scoped Copilot runtime bundles if subdirectory execution requires it.
- [ ] Keep degraded-install detection and core-asset checks intact.
- [ ] Verify spaces and shell metacharacters in installation paths.
- [ ] Verify plugin, project, and personal layouts on Linux, macOS, and Windows CI where applicable.

Exit criteria:

- Every Copilot deployment mode resolves one complete runtime root.
- A partial install fails distinctly as degraded.
- Existing Claude, Codex, Cursor, Gemini, and Pi resolver tests remain green.

### Phase 4: Installer deployment and migration

Status: Not started; blocked by Phase 3 runtime-root contract

Primary files:

- `installer/src/types.ts`
- `installer/src/agent-targets.ts`
- `installer/src/placements.ts`
- `installer/src/plan.ts`
- `installer/src/apply.ts`
- `installer/src/manifest.ts`
- `installer/test/agent-targets.test.ts`
- `installer/test/placements.test.ts`
- `installer/test/e2e-placements.test.ts`

Tasks:

- [ ] Change Copilot to `verified-current` with the current vendor documentation URL.
- [ ] Configure project roots under `.github` and personal roots under `.copilot`.
- [ ] Preserve a namespaced complete runtime bundle in each scope.
- [ ] Extend mirror placements to support recursive skill directories, not only flat files.
- [ ] Mirror agents into `.github/agents` or `~/.copilot/agents`.
- [ ] Track every native mirror file in the install manifest.
- [ ] Remove the managed instruction block from new-install behavior.
- [ ] On update, remove an old managed block only when it matches the recorded feature-forge region; preserve external content.
- [ ] Migrate old personal installs from `~/.github/feature-forge` to `~/.copilot/feature-forge`.
- [ ] Remove old owned paths as orphans after a successful migration.
- [ ] Preserve `--force`, dry-run, copy, symlink, containment, update, and uninstall semantics.
- [ ] Reassess automatic detection separately from explicit `-a copilot`; do not treat any repository with `.github/` as a detected Copilot installation.

Exit criteria:

- Fresh project and personal installs land in documented native paths.
- Updating the old layout produces the new layout and removes only proven-owned legacy content.
- Uninstall removes manifest-owned skill, agent, and runtime files while preserving user files.
- Dry-run JSON accurately reports all primary and placement actions.

### Phase 5: Agent Plugins distribution

Status: In progress; generated plugin/install discovery verified, packaged distribution remains open

Primary files:

- `adapters/copilot/plugin.json` (generated)
- `installer/scripts/bundle-adapters.mjs`
- `installer/package.json`
- Marketplace configuration or a dedicated Copilot marketplace artifact

Tasks:

- [ ] Include the complete generated Copilot plugin in the npm tarball.
- [x] Validate the generated `plugin.json` shape against current Copilot CLI 1.0.78 loading behavior.
- [x] Confirm that Copilot-specific agents are discovered from root `agents/` with expected tool metadata.
- [ ] Test installation from a Git repository source.
- [ ] Test installation through Copilot CLI and discovery by VS Code.
- [ ] Decide whether the existing root marketplace can serve both Claude and Copilot or needs a generated Copilot-specific package root.
- [ ] Document plugin enable, disable, update, and uninstall behavior.
- [ ] Add optional workspace plugin recommendations only after the marketplace identity is stable.

Exit criteria:

- Installing the plugin exposes all skills and agents without writing a workspace instruction block.
- Disabling or uninstalling the plugin removes its customizations through Copilot's management surface.
- The npm tarball and repository-source plugin carry the same generated content.

### Phase 6: Runtime integration verification

Status: G1 host contract closed; broader runtime matrix remains open

Automated checks:

- [x] Validate generated `plugin.json` and representative `SKILL.md` frontmatter in focused fixtures.
- [x] Validate generated `.agent.md` frontmatter through fixture tests and Copilot runtime loading.
- [x] Assert name/folder and name/file consistency in generated fixtures.
- [x] Assert exact tool mappings and invocation controls in generator tests and runtime events.
- [x] Assert unsupported Claude model aliases are omitted/drop-recorded from Copilot output.
- [ ] Assert all referenced local resources exist.
- [ ] Run full installer lifecycle tests for both scopes and both installation generations.

Copilot smoke matrix:

| Scenario | VS Code | Copilot CLI | Agent Host |
| --- | --- | --- | --- |
| Skills listed in diagnostics | Required | Required | Required |
| Slash invoke `forge-init` | Required | Required | Required |
| Automatic `forge-init` discovery | Required | Required | Required |
| `forge-researcher` subagent | Required | Required | Required |
| Parallel `forge-spec-writer` calls | Required | Required | Required |
| Read-only `forge-verifier` | Required | Required | Required |
| Shared script/root resolution | Required | Required | Required |
| Project install | Required | Required | Required |
| Personal/plugin install | Required | Required | Required |

Record the tested product versions and any required feature flags. Experimental capabilities must be labeled as such in user-facing documentation.

Progress (2026-08-23): cached CLI discovery, plugin-prefixed invocation, direct project/personal
discovery, all three worker tool boundaries, and parent-to-researcher subagent dispatch pass. A
fresh VS Code/Agent Host process also loaded all 13 skills and all three agents, resolved the
installed guide, and completed a read-only researcher delegation. Both the predeclared legacy and
Agent Plugins 1.0 root probes failed after full restarts: command tokens remained literal and the
environment exported no `PLUGIN_ROOT`. The dated scope decision therefore requires package
self-location plus explicit `FEATURE_FORGE_ROOT`, closes unified `COP-003`/G1, and forbids runtime
root dependence on `PLUGIN_ROOT`. See `evidence/copilot-host-contract-2026-08-23.md`. The broader
runtime matrix remains open.

Exit criteria:

- The complete smoke matrix passes, or unsupported cells are explicitly documented with a tested fallback.
- `bash scripts/validate.sh` passes.

### Phase 7: Documentation and release

Status: In progress; release bookkeeping started, user-facing docs and package preflight remain open

Primary files:

- `docs/agents/copilot.md`
- `installer/README.md`
- `AGENTS-SETUP.md`
- `README.md`
- `CHANGELOG.md`
- `scripts/check-version-sync.py`

Tasks:

- [ ] Document plugin installation as the preferred Copilot path.
- [ ] Document direct project and personal installation as compatibility paths.
- [ ] Replace the dry-run-only first-use proof with native discovery and invocation checks.
- [ ] Document command naming for plugin and direct installs.
- [ ] Document the legacy managed-block migration.
- [ ] Add troubleshooting through Copilot customization diagnostics.
- [x] Add Copilot `plugin.json` to the product version-sync contract.
- [x] Add a changelog entry under `[Unreleased]` in the implementation worktree.
- [x] Regenerate all adapters and review `adapters/GENERATION-REPORT.md`.
- [x] Run `bash scripts/validate.sh`.
- [ ] Run installer prepack and `npm pack --dry-run`, then remove `installer/adapters/` before final validation.

Release note:

This change is publish-worthy because generated adapters and installer behavior ship in the npm package. Merge does not publish. After merge, offer the owner the normal version-bump and manual publish runbook; do not publish without approval.

## 8. Test Inventory

Existing tests likely to change:

- `tests/test_build_adapters.py`
- `tests/test_adapter_host_neutrality.py`
- `tests/test_agent_targets_parity.py`
- `tests/fixtures/minimal-canon/expected-adapters/copilot/`
- `installer/test/agent-targets.test.ts`
- `installer/test/placements.test.ts`
- `installer/test/e2e-placements.test.ts`
- `installer/test/apply.test.ts`
- `installer/test/report.test.ts`

New focused tests likely needed:

- Copilot plugin manifest schema and version synchronization.
- Copilot skill frontmatter and directory-name validation.
- Copilot agent frontmatter and tool mapping.
- Recursive mirror planning and apply behavior.
- Legacy managed-block and old-root migration.
- Project-versus-personal containment boundaries.
- Runtime root resolution from plugin and direct installations.
- Cross-platform path handling for native mirror roots.
- A repeatable Copilot smoke-test fixture or documented harness script.

## 9. Migration Contract

The migration from the current Copilot layout is a user-data boundary and must be fail-safe.

1. Read the prior feature-forge install manifest.
2. Install the new complete runtime bundle and native mirrors.
3. Verify all required new files were applied or intentionally skipped as user-modified.
4. Remove old manifest-owned bundle files that no longer belong to the new tree.
5. Remove the managed instruction region only if it is unchanged from the recorded hash.
6. If the region was modified, preserve it and report `skip-modified`; require `--force` for replacement/removal.
7. Delete `.github/copilot-instructions.md` only if it becomes empty after removing the owned region.
8. Write the new manifest only after successful apply/reconciliation.
9. Make a repeated update a no-op.
10. Make uninstall exact for both migrated and fresh installations.

No migration step may remove an untracked skill or agent solely because its filename matches a feature-forge name.

## 10. Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Copilot APIs are evolving | Paths or fields may change | Pin decisions to dated docs and keep schema/runtime smoke tests. |
| Plugin and direct commands differ | Generated instructions may invoke the wrong command | Adopt an explicit command strategy before emitter work. |
| Shared resources sit outside a native skill directory | Skill loads but helper execution fails | Preserve a complete runtime root and test root resolution end to end. |
| Agent tool aliases vary by harness | Agent silently gains or loses capability | Use documented aliases, fail on unmapped canon tokens, and run capability probes. |
| Model aliases are account-dependent | Agent fails to start | Inherit the parent model initially; add fallback arrays only from verified names. |
| Recursive mirrors widen installer writes | Containment or uninstall defect | Extend manifest ownership and path-containment tests before enabling Copilot. |
| Existing managed block was user-edited | Migration could destroy user instructions | Hash-check the exact managed region and preserve modified content by default. |
| `.github` is not a reliable detection signal | Automatic install targets false positives | Keep explicit `-a copilot` authoritative and define conservative detection evidence. |
| Experimental forked skills or nested agents regress | Pipeline orchestration becomes unreliable | Do not depend on experimental features for baseline support. |

## 11. Open Decisions

Update each item with a dated decision and rationale.

### D1. One generated plugin or plugin plus direct variant?

Status: Accepted 2026-08-23
Decision: Keep one plugin-shaped canonical Copilot bundle and let the installer mirror its
components into direct discovery roots. Introduce a second skill-body variant only if command
prefixes cannot be expressed accurately otherwise.

### D2. How should direct-install skill commands be referenced?

Status: Accepted 2026-08-23
Decision: Use neutral prose in generated workflow transitions, with a Copilot host note stating
both plugin and direct forms.

### D3. Should any skill use `context: fork`?

Status: Accepted 2026-08-23
Decision: Do not use `context: fork` for the first release. Existing custom agents provide
intentional context isolation while skill forking remains experimental.

### D4. Should Copilot agents pin models?

Status: Accepted 2026-08-23
Decision: Do not pin models initially. Inherit the selected parent model and retain canonical model
intent only as a drop record until stable qualified fallback names can be tested.

### D5. How is verifier memory represented?

Status: Accepted 2026-08-23
Decision: Treat persistent agent memory as unsupported for parity. Preserve verifier behavior and
state that no persistent `MEMORY.md` update is guaranteed without a verified mechanism.

### D6. What proves Copilot is installed for automatic targeting?

Status: Accepted 2026-08-23
Decision: Probe documented Copilot-specific customization roots or installed-plugin state. Do not
use a generic `.github` directory alone.

### D7. Can the existing marketplace serve Copilot directly?

Status: Accepted 2026-08-23
Decision: Test VS Code source installation against the generated Agent Plugins root before adding
another marketplace repository or package.

## 12. Definition of Done

The initiative is complete when all of the following are true:

- [ ] Every canonical skill is emitted as a valid Copilot `SKILL.md` with its argument hint.
- [ ] All three canonical agents are valid Copilot custom agents with tested tool restrictions.
- [ ] Skills can dispatch the named agents and receive their final results.
- [ ] Project and personal installs use documented Copilot discovery roots.
- [ ] The complete runtime bundle resolves from every supported Copilot deployment mode.
- [ ] Existing Copilot installs migrate without losing user-authored instructions or customizations.
- [x] The generated adapter is a valid tested legacy Copilot-format package; Agent Plugins 1.0 is explicitly not claimed.
- [ ] Plugin installation works in VS Code and Copilot CLI and is visible to Agent Host sessions.
- [ ] Generator, installer, migration, resolver, and runtime smoke tests pass.
- [ ] Documentation accurately describes invocation, installation, verification, and limitations.
- [ ] `adapters/GENERATION-REPORT.md` records every unsupported canonical field and no supported Copilot field as dropped.
- [ ] `bash scripts/validate.sh` passes from a clean checkout.
- [ ] The npm package dry run contains the complete Copilot adapter.

## 13. Change Log for This Plan

| Date | Change |
| --- | --- |
| 2026-08-23 | Initial plan created from repository and current Copilot harness investigation. |
| 2026-08-23 | Native plugin foundation implemented and verified: root manifest, 13 skills, three agents, fixtures, version gate, and Copilot CLI 1.0.78 discovery evidence. Installer migration and full harness verification remain open. |
| 2026-08-23 | Accepted D1–D7 through unified `COP-001`; plugin-first distribution with direct compatibility mirrors and neutral transition prose is the frozen baseline. |
| 2026-08-23 | Unified `COP-002` froze the floor-plus-current product/runtime matrix and initial Linux x64/WSL2 Copilot support boundary; cross-platform promotion requires runtime smokes. |
| 2026-08-23 | Unified `COP-003` CLI/direct probes passed, including behavioral worker and subagent checks; VS Code/Agent Host and runtime `${PLUGIN_ROOT}` proof remain blocked on a fresh host session. |
| 2026-08-23 | Fresh VS Code/Agent Host discovery, guide loading, and researcher delegation passed; a post-start hook was not dynamically registered, so unified `COP-003` remains open only on a predeclared hook/MCP `${PLUGIN_ROOT}` expansion probe. |
| 2026-08-23 | Added the durable `operator-actions.md` handoff for the one remaining external G1 probe; no feature-forge or rauf implementation task advanced. |
| 2026-08-23 | Executed the predeclared legacy hook after a full host restart; VS Code registered it but did not expand or export `${PLUGIN_ROOT}`, so the probe failed, cleanup completed, and unified `COP-003`/G1 remain open. |
| 2026-08-23 | Executed the Agent Plugins 1.0 replacement hooks after a full restart; command-token expansion failed and the independent helper recorded `PLUGIN_ROOT=UNSET`. The dated fallback decision requires package self-location plus explicit `FEATURE_FORGE_ROOT`, closing unified `COP-003`/G1 and advancing to `COP-004`. |
| 2026-08-23 | Prepared and installed the schema-marked Agent Plugins 1.0 replacement probe with independent command-token and environment checks; CLI discovery and cache integrity pass, while fresh-host runtime evidence remains pending. |
