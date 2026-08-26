# FORGE-101 Native Skills and Invocation Evidence — 2026-08-25

Status: Local implementation, runtime proof, and full gate complete; task remains ACTIVE until authorized commit/push durability.

## Attribution and environment

- Repository: feature-forge, base commit `12e52666d98bafda2e7c59a8872d3ea2178c1d73` on `docs/copilot-g2-contract`.
- Implementation-source diff identity before planning/evidence edits: SHA-256 `70a48532a43cd6f76cd27b82a1bec1e0ecd40fa9fe5b39f804985496df4990ed` from `git diff -- scripts/build-adapters.py scripts/forge-session.py tests/test_build_adapters.py tests/test_stage_exit.py | sha256sum`.
- OS: Linux 5.15.0-185-generic, x86_64, native (not WSL).
- GitHub Copilot CLI: 1.0.80.
- Generated product version: 0.18.0.
- Probe repository commit: `2f4c2fd0ca2236474dfd78ef4bfcc6256b9d5016` (disposable and removed).
- Secrets excluded: no token, credential, account identifier, raw environment, user configuration, or unrelated prompt/session content is retained.

## Format decision and primary evidence

FORGE-101 retains the generated manifest as the **legacy Copilot plugin format** and explicitly does not claim Agent Plugins 1.0.

Official sources accessed 2026-08-25:

1. <https://code.visualstudio.com/docs/copilot/customization/agent-plugins>
   - Agent Plugins 1.0 requires root `$schema` equal to `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`.
   - Portable skills are discovered implicitly from `skills/`; component paths are not listed as top-level manifest fields.
   - Copilot-specific agents belong under `com.github.copilot/agents/`.
   - A root `plugin.json` without another format marker defaults to the Copilot format.
2. <https://agent-plugins.org/schemas/1.0.0/plugin.schema.json>
   - The schema requires `$schema` and `name`, rejects additional properties, and therefore does not permit the legacy top-level `agents` and `skills` path fields.
3. <https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference>
   - The Copilot plugin format permits `agents` and `skills` path fields; their defaults are root `agents/` and `skills/`.
4. <https://code.visualstudio.com/docs/copilot/customization/agent-skills>
   - Plugin skills receive a plugin-name prefix (example `/my-plugin:test-runner`); directly discovered skills use their unprefixed skill names.

Actual generated `adapters/copilot/plugin.json` is the five-field object `{name, description, version, agents, skills}`. It has no `$schema`, declares root paths explicitly, and keeps custom agents at root `agents/`. The only accurate classification is legacy Copilot format.

## Deterministic translation contract

Generated Copilot skill descriptions, bodies, agent descriptions, copied reference Markdown, and scripted stage-exit output translate canonical `/feature-forge:<name>` commands to:

```text
invoke-skill: <name> [arguments]
```

This is explicitly labeled as notation, not a literal pasteable command. Every generated Copilot skill overlay maps it as follows:

- plugin install: `/feature-forge:<name> [arguments]`;
- direct project/personal install: `/<name> [arguments]`;
- no universal slash name; use the skill discovery source and do not guess.

Exempt project scaffolding templates remain intentionally target-specific source material rather than Copilot host guidance.

## Focused deterministic checks

Commands and results:

```bash
.venv-adapters/bin/python3 -m pytest -q tests/test_build_adapters.py
# 118 passed

python3 -m pytest -q tests/test_stage_exit.py tests/test_adapter_host_neutrality.py
# 1009 passed

python3 scripts/build-adapters.py --check
git diff --check
# both exit 0

rg -n '/feature-forge:' adapters/copilot -g '*.md' \
  | grep -v 'Plugin install' | grep -v '/templates/'
# no output
```

The focused tests include negative guards for the old universal prefix in Copilot body/reference prose, exact plugin/direct overlay forms, and structured plus human stage-exit output.

## Installed-plugin runtime probe

A disposable local Git marketplace copied the regenerated `adapters/copilot/` tree byte-for-byte. The bounded command sequence was:

```bash
copilot plugin marketplace add /tmp/feature-forge-forge101-probe
copilot plugin install feature-forge@feature-forge-forge101-probe
copilot skill list --json
copilot -C /home/gary/workspace/feature-forge \
  --no-custom-instructions --disable-builtin-mcps --no-remote --no-auto-update \
  --output-format json --stream off \
  -p '/feature-forge:forge-guide Answer with exactly FORGE101_PLUGIN_OK if the loaded feature-forge skill says plugin installs use /feature-forge:<name> and direct installs use /<name>; otherwise answer FORGE101_PLUGIN_BAD.'
```

Expected:

- installation succeeds using the legacy five-field manifest;
- exactly the generated 13 skills are discovered from the plugin source;
- `/feature-forge:forge-guide` loads the regenerated guide and reports the overlay contract;
- installed files match source bytes.

Actual:

- CLI printed `Plugin "feature-forge" installed successfully. Installed 13 skills.`
- `copilot skill list --json` contained the feature-forge plugin skills.
- JSONL contained the loaded `forge-guide` identity and final `FORGE101_PLUGIN_OK`.
- Source and installed hashes matched:
  - `plugin.json`: `b71672fb2f96103bccbb38876d7ce55353ac1363dea2195c61c7e56d52465ad1`
  - `skills/forge-guide/SKILL.md`: `3f7cb92dc3a8a8aab6ed3d40d3ef0363b50e06b8d7a1b00d10441da9b9c6ccd6`

This proves current Copilot CLI acceptance/discovery and the plugin-prefixed invocation path. The direct `/<name>` form remains backed by the prior direct project/personal discovery evidence in `copilot-host-contract-2026-08-23.md`; FORGE-104/105 own future installer placement and packed fresh-install lifecycle proof.

## Full repository gate

The first invocation inherited `FEATURE_FORGE_ROOT=/home/gary/workspace/feature-forge/adapters/pi` from the active Pi compatibility extension. That parent-process override correctly won resolver precedence but contaminated two clean-environment resolver fixtures and the adapter-src Pi self-location assertion. The run otherwise reached 2,479 passed Python tests and 182 passed installer tests. No source fix was made for an external environment override.

The clean-shell gate was rerun with only that variable removed:

```bash
env -u FEATURE_FORGE_ROOT bash scripts/validate.sh
```

Result: PASS.

- Python: 2,481 passed, 2 skipped.
- Installer: 182 passed.
- Pi adapter source: 11 passed.
- Spec purity, adapter drift, ruff, traceability, and four-field version sync: passed.
- The spec-purity grandfather annotation for `scripts/build-adapters.py` was lowered from 83 to its new live count 82, removing the shrinking-debt warning.

## Cleanup and final registry state

A shell `EXIT` trap uninstalled `feature-forge@feature-forge-forge101-probe`, removed marketplace `feature-forge-forge101-probe`, and deleted `/tmp/feature-forge-forge101-probe`. Follow-up checks showed:

- `copilot plugin list`: no plugins installed;
- `copilot plugin marketplace list`: only built-in `copilot-plugins` and `awesome-copilot`;
- probe path absent;
- cleanup logs removed;
- feature-forge and rauf branches otherwise retained their existing worktree state; no commit, push, merge, tag, release, publication, or rauf pin advance occurred.
