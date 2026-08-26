# Copilot Host Contract Evidence - 2026-08-23

Status: COP-003 complete; discovery/delegation pass and `${PLUGIN_ROOT}` is unavailable on the tested host, with self-location plus explicit `FEATURE_FORGE_ROOT` required.

## Environment

- Platform: Linux 6.6.87.2-microsoft-standard-WSL2, x86_64
- GitHub Copilot CLI: 1.0.78
- VS Code: 1.134.0 stable, commit `110a328ea54b42367b803ec53ee0bf52ef26b419`
- Built-in GitHub Copilot extension: `github.copilot-chat` 0.62.0, build 1
- Agent Host log: `~/.vscode-server/data/logs/20260822T165755/agenthost.log`; current process started 2026-08-23 03:46:31 local time.
- Copilot extension log: `~/.vscode-server/data/logs/20260822T165755/exthost5/GitHub.copilot-chat/GitHub Copilot Chat.log`; extension host initialized 2026-08-23 09:07:39 local time.
- Final predeclared-probe host: VS Code 1.134.0 stable, commit `110a328ea54b42367b803ec53ee0bf52ef26b419`; Copilot Chat 0.62.0; Agent Host process 3541753 started 2026-08-23 09:47:18 local time and logged startup at 09:47:27 under `~/.vscode-server/data/logs/20260823T094724/agenthost.log`.
- Final hook diagnostics: `~/.vscode-server/data/logs/20260823T094724/exthost1/GitHub.copilot-chat/GitHub Copilot Chat Hooks.log`.
- Agent Plugins 1.0 probe host: VS Code 1.134.0 stable, commit `110a328ea54b42367b803ec53ee0bf52ef26b419`; Copilot Chat 0.62.0; logs under `~/.vscode-server/data/logs/20260823T103918/`.
- Agent Plugins 1.0 hook diagnostics: `~/.vscode-server/data/logs/20260823T103918/exthost1/GitHub.copilot-chat/GitHub Copilot Chat Hooks.log`.
- Authentication: existing Copilot account; no token, credential value, prompt payload, or raw user configuration is retained here.

## Official Contract Captured

Retrieved 2026-08-23 from current VS Code and GitHub Copilot documentation:

- Skills: project `.github/skills/<name>/SKILL.md`; personal `~/.copilot/skills/<name>/SKILL.md`.
- Agents: project `.github/agents/*.agent.md`; personal `~/.copilot/agents/*.agent.md`.
- Plugin skills receive `/plugin-name:skill-name`; direct skills use `/skill-name`.
- `user-invocable: false` hides an agent from the picker while preserving model/subagent invocation.
- `agents: []` prevents nested subagent use.
- Tool fields accept built-in aliases; this bundle uses `read`, `search`, `execute`, and `edit`.
- The generated manifest has no Agent Plugins 1.0 `$schema`, so it is the supported legacy Copilot plugin format. Root `agents/` is correct for that format. A future Agent Plugins 1.0 migration would require Copilot-specific agents under `com.github.copilot/agents/`.
- `${PLUGIN_ROOT}` is documented for packaged plugin paths and hook/MCP processes. It is not documented as an ambient variable for every shell tool.
- Current VS Code plugin documentation, retrieved 2026-08-23, confirms that legacy Copilot-format plugins auto-discover `hooks.json` at the plugin root; no hook path is listed in `plugin.json`. Agent Plugins 1.0 instead uses `com.github.copilot/hooks/hooks.json`. The remaining probe intentionally uses the legacy root layout because the generated manifest has no Agent Plugins `$schema`.
- For Copilot-format hooks, VS Code documents `${PLUGIN_ROOT}` in the command as a runtime-expanded token and `PLUGIN_ROOT` as an environment variable exported to the hook process. The probe checks both command expansion and the exported variable by comparing it with script self-location.

## Passing Runtime Probes

All probes used a disposable local marketplace and temporary project. The plugin, marketplace, personal roots, and temporary directories were removed afterward.

1. Cached plugin lifecycle
   - Command shape: `copilot plugin marketplace add <local-git-dir>`, `copilot plugin install feature-forge@feature-forge-g1-probe`.
   - Result: plugin 0.18.0 installed; CLI reported `Installed 13 skills`.
   - `copilot skill list --json` returned all 13 forge skills with `source: plugin`, enabled.
   - `copilot --plugin-dir adapters/copilot plugin list` listed the external plugin, but CLI 1.0.78 omitted its skills. This is diagnostic-only and is not skill-discovery proof.

2. Command name and plugin invocation
   - Prompt began `/feature-forge:forge-guide`.
   - JSONL emitted `session.skills_loaded` for all 13 plugin skills.
   - Final assistant response was exactly `G1_SKILL_OK`.

3. Plugin custom agents
   - `session.custom_agents_updated` loaded:
     - `feature-forge:forge-researcher`: `read`, `search`, `execute`; `userInvocable: false`.
     - `feature-forge:forge-spec-writer`: `read`, `search`, `execute`, `edit`; `userInvocable: false`.
     - `feature-forge:forge-verifier`: `read`, `search`, `execute`; `userInvocable: false`.

4. Direct project and personal discovery
   - A disposable project `.github/skills/forge-guide` returned `source: project`.
   - Its `.github/agents` files loaded all three unprefixed workers with expected tools.
   - A temporary `~/.copilot/skills/forge-guide` returned `source: personal-copilot`.
   - Temporary `~/.copilot/agents` loaded all three unprefixed workers with expected tools.
   - Both personal directories were confirmed absent before creation and removed after the probe.

5. Worker capability and delegation behavior
   - Researcher read a disposable marker and returned `RESEARCHER_READ:G1_ORIGINAL`.
   - Verifier was asked to edit, returned `VERIFIER_RESULT:denied`, and the marker remained `G1_ORIGINAL`.
   - Spec writer emitted an `edit` tool event, returned `WRITER_RESULT:edited`, and the marker became `G1_WRITER_EDITED`.
   - A default parent emitted `task`, `subagent.started`, and `subagent.completed`, then returned `SUBAGENT_RESULT:G1_WRITER_EDITED` from `feature-forge:forge-researcher`.

6. Fresh VS Code and Agent Host discovery and invocation
   - The active Agent Host process started at 2026-08-23 03:46:31, after the disposable plugin was installed. The Copilot extension host initialized at 09:07:39 with VS Code 1.134.0 and Copilot Chat 0.62.0.
   - Runtime customization context exposed all 13 installed forge skills and the three generated agents. The agent tool sets were `read/search/execute` for researcher and verifier and `read/search/execute/edit` for spec writer; no feature-forge customization warning was reported.
   - `/feature-forge:forge-guide` resolved to the installed generated `skills/forge-guide/SKILL.md` and loaded its advisory workflow.
   - Parent-to-worker delegation ran through the host's `runSubagent` surface as `forge-researcher`, the API identity for installed `feature-forge:forge-researcher`. The child read `/tmp/feature-forge-copilot-g1/.github/plugin/marketplace.json`, returned its exact non-secret content, reported read-only access, and performed no edit.
   - The extension log records `subagent=true` and repeated `[tool/runSubagent-forge-researcher]` requests followed by a successful stop hook.

## Failed or Unproven Criteria

1. `${PLUGIN_ROOT}` runtime
   - A plugin researcher shell printed `PLUGIN_ROOT=`.
   - Disposable SessionStart hooks using both platform-specific `bash` and portable `command` keys did not execute under Copilot CLI 1.0.78, even when present in the cached plugin and declared in the legacy manifest.
   - In the fresh VS Code host, a reversible `hooks.json` and executable probe were added to the disposable installed plugin after Agent Host startup. A newly dispatched researcher subagent reported that `/tmp/feature-forge-copilot-g1/vscode-plugin-root.txt` did not exist. This proves the host did not dynamically register a post-start plugin hook; it does not prove or disprove expansion for a hook present before host startup.
   - Conclusion: do not infer `${PLUGIN_ROOT}` availability in ordinary CLI shell tools. The documented VS Code hook/MCP expansion still needs a fresh-host runtime probe. `FORGE-103` must retain self-location and explicit `FEATURE_FORGE_ROOT` fallbacks.

2. Predeclared legacy-plugin hook probe after full restart
   - The disposable fixture was commit `d0c18ec2063bf32964c1718f2cf23a44f7bb2720`; `feature-forge@feature-forge-g1-probe` 0.18.0 was installed before the new VS Code and Agent Host process started.
   - The installed root was `/home/gary/.copilot/installed-plugins/feature-forge-g1-probe/feature-forge`. Its root `hooks.json` and executable `scripts/plugin-root-probe.sh` matched the fixture byte-for-byte; the script mode was 0755.
   - On the first message of the new chat, VS Code registered two SessionStart hooks. The Databricks hook succeeded. The feature-forge hook was logged with the literal command `bash "${PLUGIN_ROOT}/scripts/plugin-root-probe.sh"`, then failed in 11 ms with `bash: /scripts/plugin-root-probe.sh: No such file or directory`.
   - `/tmp/feature-forge-copilot-g1/vscode-plugin-root.txt` was absent after execution. The shell result proves the command token was not host-expanded and the hook process did not receive a non-empty `PLUGIN_ROOT` environment variable.
   - No feature-forge customization warning preceded execution; this was a runtime hook error, not an absent registration. The Chat customization diagnostics UI could not be captured because the available host tools exposed no general VS Code command/UI control.
   - Result: the required `PLUGIN_ROOT == SELF_ROOT` and `MATCH=true` cell failed. `COP-003` remains unchecked, G1 remains open, and `COP-004` must not start.
   - Cleanup completed: the disposable plugin, marketplace, installed cache, and `/tmp` fixture were removed. Registry verification showed only `databricks@databricks-agent-skills` 0.2.10 and marketplace `databricks-agent-skills` remained.

3. Customization diagnostics UI
   - Runtime customization context and logs prove fresh-host discovery, invocation, source files, and tool sets, but the exposed VS Code command runner is restricted to workspace-creation flows and could not open the Chat customization diagnostics UI.
   - This is no longer a discovery blocker, but a future smoke should capture the user-facing diagnostics UI to verify the documented troubleshooting path.

4. Agent Plugins 1.0 root contract after full restart
   - The disposable package at commit `1145ffb` was installed before the restarted VS Code and Agent Host under `/home/gary/.copilot/installed-plugins/feature-forge-g1-v1/feature-forge-g1-v1-probe`.
   - The host registered three SessionStart hooks. The original Databricks hook completed successfully. The command-token probe was invoked literally as `bash '${PLUGIN_ROOT}/scripts/command-token-probe.sh'` and failed in 7 ms because that literal path did not exist.
   - `/tmp/feature-forge-copilot-g1-v1/runtime/command-token.txt` was absent, so `TOKEN_SCRIPT_RAN=true` and the required self-located root were not produced.
   - The independent absolute helper completed successfully in 8 ms and wrote `PLUGIN_ROOT=UNSET` to `/tmp/feature-forge-copilot-g1-v1/runtime/exported-env.txt`.
   - Result: neither documented root channel passed. CLI installation and skill discovery are not used as runtime-root evidence.

## Scope Decision - 2026-08-23

On VS Code 1.134.0 with Copilot Chat 0.62.0 under Linux x64/WSL2, `PLUGIN_ROOT` is unavailable to Agent Plugins 1.0 hooks through both documented channels: the host neither substitutes the command token nor exports the environment variable. Copilot runtime-root design must therefore self-locate from package-owned executable code and retain explicit `FEATURE_FORGE_ROOT` as the operator override. It must not require, advertise, or infer `PLUGIN_ROOT` on this tested host.

This dated narrowing closes `COP-003` and G1. It does not claim that future host versions behave identically; support-matrix promotion requires a fresh runtime probe. `COP-004` may proceed.

## Exact Recovery

The legacy root-hook recovery was executed exactly and failed. The replacement recovery was
prepared on 2026-08-23:

- Current VS Code documentation explicitly selects Agent Plugins 1.0 when root `plugin.json`
   declares `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`, and assigns Copilot hooks
   to `com.github.copilot/hooks/hooks.json`.
- `/tmp/feature-forge-copilot-g1-v1` is a minimal disposable marketplace repository at commit
   `1145ffb`. Its manifest uses only fields allowed by the closed Agent Plugins schema.
- `feature-forge-g1-v1-probe@feature-forge-g1-v1` 0.0.1 is installed under
   `~/.copilot/installed-plugins/feature-forge-g1-v1/feature-forge-g1-v1-probe`.
- Copilot CLI 1.0.78 accepted the package and discovered its `root-probe` skill. The installed
   manifest, namespaced hook file, and executable token-probe script match the fixture byte-for-byte.
- The command-token hook uses `bash '${PLUGIN_ROOT}/scripts/command-token-probe.sh'`. Single quotes
   prevent Bash environment expansion, so successful invocation proves host token expansion.
- The environment hook invokes the absolute disposable helper
   `/tmp/feature-forge-copilot-g1-v1/exported-env-probe.sh`, so it records the hook process's
   `PLUGIN_ROOT` without depending on command-token expansion.
- `/tmp/feature-forge-copilot-g1-v1/runtime` was removed after manual fixture validation and is
   absent before restart.

The full restart was completed. Both root channels failed as recorded above, so the required dated
scope decision now controls runtime-root work. The disposable installation and marketplace are
removed during session close; no legacy probe is repeated. Cleanup verification retained only
`databricks@databricks-agent-skills` 0.2.10 and marketplace `databricks-agent-skills`; the named
feature-forge installation, marketplace, installed root, and `/tmp` fixture were absent.
