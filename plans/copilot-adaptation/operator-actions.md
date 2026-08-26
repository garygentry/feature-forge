# Copilot Adaptation Operator Actions — Historical, Do Not Execute

Status: Completed; both root probes failed, cleanup passed, and G1 closed by scope decision
Updated: 2026-08-24
Scope: archived external evidence for `COP-003` / gate G1

This file preserves historical commands and prompts for audit only. **Do not execute any procedure
below.** The restarted host left the command token literal and exported no `PLUGIN_ROOT`; the dated
scope decision in the host-contract evidence requires package self-location plus explicit
`FEATURE_FORGE_ROOT` and closes G1. Both disposable probes were removed and the original registry
was verified. Current work is tracked only in `EXECUTION.md`.

## Historical Agent Plugins 1.0 Handoff — Completed

Prepared and validated before restart:

- Disposable repository: `/tmp/feature-forge-copilot-g1-v1`, commit `1145ffb`.
- Installed plugin: `feature-forge-g1-v1-probe@feature-forge-g1-v1` 0.0.1.
- Installed root:
  `~/.copilot/installed-plugins/feature-forge-g1-v1/feature-forge-g1-v1-probe`.
- Package marker: canonical Agent Plugins 1.0 `$schema` in root `plugin.json`.
- Hook location: `com.github.copilot/hooks/hooks.json`.
- CLI result: package accepted and one `root-probe` skill discovered.
- Cached manifest, hook, and executable script: byte-identical to the fixture.
- Runtime output directory: absent before restart.

The hooks test two contracts independently. The first uses a single-quoted `${PLUGIN_ROOT}` token,
which Bash cannot expand; its script can run only if the host expands the command token. The second
uses an absolute helper path and records the exported environment variable without relying on the
token.

### Historical external action — already completed; do not repeat

1. Close every VS Code window connected to this WSL environment.
2. In a separate WSL terminal, wait until this returns no Agent Host process:

   ```bash
   pgrep -af 'bootstrap-fork --type=agentHost' || true
   ```

3. Reopen `/home/gary/workspace/feature-forge` in VS Code.
4. Start a completely new Copilot Chat and use the continuation prompt below as its first message.

### Continuation Prompt For The New Host

```text
Continue COP-003 from plans/copilot-adaptation/operator-actions.md. Read the governing AGENTS.md
files, the unified plan, README, and host-contract evidence first; preserve both worktrees.

The Agent Plugins 1.0 probe was installed before this VS Code/Agent Host started. Inspect:
/tmp/feature-forge-copilot-g1-v1/runtime/command-token.txt
/tmp/feature-forge-copilot-g1-v1/runtime/exported-env.txt

Correlate both with the installed root at
~/.copilot/installed-plugins/feature-forge-g1-v1/feature-forge-g1-v1-probe and with the current
Copilot hook log. A pass requires TOKEN_SCRIPT_RAN=true, SELF_ROOT equal to the installed root, and
PLUGIN_ROOT equal to the installed root. Capture only sanitized evidence. Do not infer a pass from
CLI discovery.

If both channels pass, close COP-003/G1 and continue with COP-004. If either fails, add the dated
scope decision that PLUGIN_ROOT is unavailable on this tested host and require package self-location
plus explicit FEATURE_FORGE_ROOT fallback, then close COP-003/G1 on that evidence before COP-004.
In either case, uninstall only feature-forge-g1-v1-probe@feature-forge-g1-v1, remove only marketplace
feature-forge-g1-v1 and /tmp/feature-forge-copilot-g1-v1, verify the original Databricks registry,
and follow the session close protocol. Do not repeat the legacy probe.
```

Expected passing files:

```text
TOKEN_SCRIPT_RAN=true
SELF_ROOT=/home/gary/.copilot/installed-plugins/feature-forge-g1-v1/feature-forge-g1-v1-probe
```

```text
PLUGIN_ROOT=/home/gary/.copilot/installed-plugins/feature-forge-g1-v1/feature-forge-g1-v1-probe
```

Historical cleanup commands (already completed; do not repeat):

```bash
copilot plugin uninstall feature-forge-g1-v1-probe@feature-forge-g1-v1
copilot plugin marketplace remove feature-forge-g1-v1
rm -rf /tmp/feature-forge-copilot-g1-v1
```

## Historical Legacy Probe Runbook

Everything below this heading records the completed legacy probe and must not be executed again.

## Outcome

The historical legacy operator restart and first-message probe were completed on 2026-08-23. VS Code 1.134.0 with
Copilot Chat 0.62.0 registered the predeclared feature-forge SessionStart hook, but logged the
literal command `bash "${PLUGIN_ROOT}/scripts/plugin-root-probe.sh"` and failed with
`bash: /scripts/plugin-root-probe.sh: No such file or directory`. The output file was absent, so
`COP-003` and G1 remain open and `COP-004` was not started.

The disposable plugin, marketplace, installed cache, and `/tmp` fixture were removed. The original
Databricks plugin and marketplace remain. Do not repeat Sections 1-3 unchanged; the next recovery is
recorded in `evidence/copilot-host-contract-2026-08-23.md` and the controlling unified plan.

## Preparation State

Completed 2026-08-23 in the current session:

- The generated Copilot adapter was copied to
  `/tmp/feature-forge-copilot-g1/plugins/feature-forge`.
- Root `hooks.json` contains the predeclared `SessionStart` command with a literal
  `${PLUGIN_ROOT}` token.
- `scripts/plugin-root-probe.sh` contains literal Bash without Markdown or HTML escaping and is
  executable.
- `.github/plugin/marketplace.json` is present and valid JSON.
- Both JSON files parse, the script passes `bash -n`, and its manual self-location check returned
  `MATCH=true`.
- The disposable repository is clean at commit `d0c18ec` (`feature-forge G1 predeclared root
  probe`). This commit exists only under `/tmp`; neither source repository was committed or staged.
- Marketplace `feature-forge-g1-probe` is registered and
  `feature-forge@feature-forge-g1-probe` version `0.18.0` is installed.
- The installed `hooks.json` and probe script compare byte-for-byte with the disposable source; the
  installed script is executable.
- `/tmp/feature-forge-copilot-g1/vscode-plugin-root.txt` was removed after manual validation and is
  absent before restart.

Sections 1–3 are complete historical evidence. No operator action remains in this file. Any future
host-version revalidation must receive a new dated task and disposable fixture rather than reusing
these commands.

## Why A Restart Is Required

The remaining contract is VS Code's runtime handling of `${PLUGIN_ROOT}` for a packaged plugin hook.
The previous session added a hook after Agent Host startup; VS Code did not dynamically register it.
Current VS Code documentation states that a legacy Copilot-format plugin discovers `hooks.json` at
the plugin root automatically, expands `${PLUGIN_ROOT}` in hook commands, and exports `PLUGIN_ROOT`
to the hook process. The hook must therefore exist before installation and before VS Code and Agent
Host start.

This is not a Copilot CLI discovery test. Do not use `--plugin-dir` as proof; Copilot CLI 1.0.78 does
not discover plugin skills correctly through that option.

## Preconditions

Run these commands in a WSL shell. They preserve both source worktrees and create only a disposable
Git repository under `/tmp`.

```bash
cd /home/gary/workspace/feature-forge

git status --short
git -C ../rauf status --short
copilot plugin list
copilot plugin marketplace list

test ! -e /tmp/feature-forge-copilot-g1
test ! -e "$HOME/.copilot/installed-plugins/feature-forge-g1-probe"
```

Expected registry before the probe:

- `databricks@databricks-agent-skills` remains installed.
- `databricks-agent-skills` remains registered.
- `feature-forge@feature-forge-g1-probe` and marketplace `feature-forge-g1-probe` are absent.

Stop if either feature-forge probe entry already exists. Do not remove an installation unless it is
clearly the disposable `feature-forge-g1-probe` named here.

## 1. Build The Disposable Marketplace

The fixture copies the existing generated adapter without modifying it. The only Git commit below is
inside `/tmp/feature-forge-copilot-g1`; do not commit or stage either source repository.

```bash
cd /home/gary/workspace/feature-forge
mkdir -p /tmp/feature-forge-copilot-g1/plugins
cp -a adapters/copilot /tmp/feature-forge-copilot-g1/plugins/feature-forge
mkdir -p /tmp/feature-forge-copilot-g1/.github/plugin
```

Create `/tmp/feature-forge-copilot-g1/plugins/feature-forge/hooks.json` with exactly:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "type": "command",
        "command": "bash \"${PLUGIN_ROOT}/scripts/plugin-root-probe.sh\"",
        "timeout": 15
      }
    ]
  }
}
```

Create `/tmp/feature-forge-copilot-g1/plugins/feature-forge/scripts/plugin-root-probe.sh` with
exactly:

```bash
#!/usr/bin/env bash
set -euo pipefail

output=/tmp/feature-forge-copilot-g1/vscode-plugin-root.txt
self_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
plugin_root="${PLUGIN_ROOT:-UNSET}"
match=false
[ "$plugin_root" = "$self_root" ] && match=true

printf 'PLUGIN_ROOT=%s\nSELF_ROOT=%s\nMATCH=%s\n' \
  "$plugin_root" "$self_root" "$match" > "$output"
printf '{"continue":true,"systemMessage":"feature-forge G1 PLUGIN_ROOT probe ran"}\n'
```

Then make it executable:

```bash
chmod +x /tmp/feature-forge-copilot-g1/plugins/feature-forge/scripts/plugin-root-probe.sh
```

Create `/tmp/feature-forge-copilot-g1/.github/plugin/marketplace.json` with exactly:

```json
{
  "name": "feature-forge-g1-probe",
  "owner": {
    "name": "feature-forge G1 probe",
    "email": "g1-probe@example.com"
  },
  "metadata": {
    "description": "Disposable local marketplace for Copilot host-contract verification.",
    "version": "0.18.0"
  },
  "plugins": [
    {
      "name": "feature-forge",
      "description": "Disposable feature-forge Copilot adapter probe.",
      "version": "0.18.0",
      "source": "./plugins/feature-forge"
    }
  ]
}
```

Initialize and commit only the disposable repository:

```bash
cd /tmp/feature-forge-copilot-g1
git init -b main
git add .
git -c user.name='G1 Probe' \
    -c user.email='g1-probe@example.com' \
    commit -m 'feature-forge G1 predeclared root probe'
```

## 2. Install Before Restarting VS Code

```bash
copilot plugin marketplace add /tmp/feature-forge-copilot-g1
copilot plugin install feature-forge@feature-forge-g1-probe
copilot plugin list
copilot plugin marketplace list
```

Confirm the installed copy already contains the hook and executable script:

```bash
installed_root="$HOME/.copilot/installed-plugins/feature-forge-g1-probe/feature-forge"
test -f "$installed_root/hooks.json"
test -x "$installed_root/scripts/plugin-root-probe.sh"
grep -F '${PLUGIN_ROOT}/scripts/plugin-root-probe.sh' "$installed_root/hooks.json"
rm -f /tmp/feature-forge-copilot-g1/vscode-plugin-root.txt
```

Expected result: the plugin is listed as version `0.18.0`, the marketplace is registered, all three
checks pass, and the output file is absent before restart.

Do not invoke Copilot CLI prompts as proof. Do not modify the cached installed copy after this point.

## 3. Fully Restart VS Code And Agent Host

1. Close every VS Code window connected to this WSL environment.
2. Wait until the old VS Code remote Agent Host process exits. In a separate WSL terminal, check:

   ```bash
   pgrep -af 'bootstrap-fork --type=agentHost' || true
   ```

   Continue only when no old Agent Host process is shown. Do not kill unrelated processes.
3. Reopen `/home/gary/workspace/feature-forge` in VS Code.
4. Open a completely new Copilot Chat session. Do not reopen or continue this old chat.
5. Paste the continuation prompt below as the first message. `SessionStart` fires on that first
   message, so the new agent must check the output only after receiving the prompt.

## Continuation Prompt

```text
Continue the GitHub Copilot adaptation across feature-forge and ../rauf from the durable handoff.

Read plans/copilot-adaptation/README.md, plans/copilot-adaptation/operator-actions.md,
plans/copilot-adaptation/evidence/copilot-host-contract-2026-08-23.md, the controlling
plans/copilot-adaptation/unified-copilot-adaptation-plan.md, and both repositories' AGENTS.md files
first. Preserve both worktrees and do not commit, publish, tag, or discard existing changes.

The operator has installed feature-forge@feature-forge-g1-probe from the disposable marketplace
/tmp/feature-forge-copilot-g1 before starting this new VS Code and Agent Host process. Resume only
the final COP-003 cell first. Read /tmp/feature-forge-copilot-g1/vscode-plugin-root.txt and verify
that PLUGIN_ROOT equals SELF_ROOT and MATCH=true. Correlate it with the installed root under
~/.copilot/installed-plugins/feature-forge-g1-probe/feature-forge and capture the current VS Code,
Copilot extension, Agent Host process, hook diagnostics, and non-secret logs. Also capture the Chat
customization diagnostics UI if the available host tools permit it.

If the probe passes, update all durable status surfaces, mark COP-003 complete, close G1 using the
README close protocol, remove the disposable plugin, marketplace, installed cache, and /tmp fixture,
verify the original registry, and continue with COP-004. If the probe fails or the file is absent,
record the exact failure and recovery action, clean up the disposable resources, keep COP-003/G1
open, and do not start COP-004. Do not infer VS Code or Agent Host behavior from CLI discovery, and
do not treat --plugin-dir as skill-discovery proof on Copilot CLI 1.0.78.
```

## What The Next Agent Must Observe

A passing `/tmp/feature-forge-copilot-g1/vscode-plugin-root.txt` has this shape:

```text
PLUGIN_ROOT=/home/gary/.copilot/installed-plugins/feature-forge-g1-probe/feature-forge
SELF_ROOT=/home/gary/.copilot/installed-plugins/feature-forge-g1-probe/feature-forge
MATCH=true
```

The exact installed path is authoritative; if the cache layout differs, equality and `MATCH=true`
are what matter. `PLUGIN_ROOT=UNSET`, unequal roots, an absent file, a hook configuration warning,
or a script execution error fails the cell.

## Cleanup Ownership

Do not uninstall the probe before the new chat evaluates it. The next agent owns cleanup after
capturing evidence:

```bash
copilot plugin uninstall feature-forge@feature-forge-g1-probe
copilot plugin marketplace remove feature-forge-g1-probe
rm -rf /tmp/feature-forge-copilot-g1
```

It must then verify that only the pre-existing plugin and marketplace registrations remain and run
the normal close-protocol checks in both repositories.
