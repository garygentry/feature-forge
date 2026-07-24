# Pi setup

feature-forge ships a generated Pi package under `adapters/pi/`. It contains Pi skills plus an `AskUserQuestion` compatibility extension so the interactive forge interview flow can use Pi's TUI instead of falling back to prose prompts.

## Install

Project-local install:

```bash
npx @garygentry/feature-forge install -a pi
```

Global install:

```bash
npx @garygentry/feature-forge install -a pi --global
```

The installer writes the Pi bundle to:

- project: `./.pi/skills/feature-forge/`
- global: `~/.pi/agent/skills/feature-forge/`

Pi package metadata lives in the real bundle `package.json`; there is no `package.json.pi` file.

For temporary local development you can also load the generated bundle directly:

```bash
pi -e ./adapters/pi
```

For project-local resources, trust the project in Pi (`/trust`) or use `--approve` for non-interactive tests.

## Commands

Pi invokes forge stages as skills:

```text
/skill:forge-init
/skill:forge-1-prd <feature-name>
/skill:forge <feature-name>
/skill:forge-verify <feature-name>
```

Do not use Claude plugin commands such as `/feature-forge:forge` in Pi.

## Notes and limitations

- Interactive input uses the bundled `AskUserQuestion` compatibility tool — a vendored snapshot of `@juicesharp/rpiv-ask-user-question` (see `adapter-src/pi/UPSTREAM.md`). In a terminal it renders a tabbed questionnaire with previews, multi-select, per-option notes, and a final review. On RPC/ACP hosts that report a UI but cannot render a custom overlay (the VSCode pendant, Zed, Paseo) it degrades to sequential select/input dialogs rather than failing. In genuinely non-interactive print/JSON runs it still fails clearly rather than hanging or picking a default.
- Pi has no `Skill` dispatch tool; forge stages are invoked as `/skill:<name>` commands.
- If `forge-root.sh` cannot find the bundle in a custom package layout, set `FEATURE_FORGE_ROOT` to the generated `adapters/pi` bundle root.

## Subagents

forge defines three custom agents — `forge-researcher`, `forge-spec-writer`, and `forge-verifier`. The bundle ships them in `agents/` and declares that directory in its `package.json`:

```json
"pi-subagents": { "agents": ["./agents"] }
```

Pi core does not read that key. A subagent extension does — the key follows [`pi-subagents`](https://github.com/nicobailon/pi-subagents) 0.35.1's manifest schema, a third-party contract feature-forge does not own. It is emitted unconditionally and is inert when no such extension is installed, so the bundle never depends on one.

`pi-subagents` is **recommended, not required**. With it installed, forge dispatches `{ agent: "forge-verifier", task: "..." }` and fans spec writers out with `{ tasks: [...] }`. Without it, every skill's Host execution notes tell the model to run that step inline instead, so the pipeline completes either way — the verify gate is just weaker.

Two limitations to know:

- **Only the package install path registers the agents.** Discovery resolves package roots from the `packages` list in Pi settings, so the agents are found when the bundle directory is listed there (for example `~/workspace/feature-forge-pi/adapters/pi`). The `npx ... install -a pi` paths above copy the bundle under `skills/`, which is not a package root — those installs get the skills but not the agents.
- **The agents carry no tool allowlist yet.** Only `name` and `description` are translated into Pi frontmatter; canon's `tools`, `maxTurns`, `memory`, and `model` keys are drop-recorded (see `adapters/GENERATION-REPORT.md`). A dispatched `forge-verifier` therefore runs with the host's default tool set, `write`/`edit` included. Its system prompt still declares it read-only, so that guarantee is prose-enforced rather than tool-enforced.

Model pins are deliberately not emitted: `opus`/`sonnet` are Claude aliases, not Pi model ids. Unpinned agents inherit the session model or `subagents.defaultModel`. To give one role a stronger model, set an override in Pi settings rather than editing the generated agent file:

```json
{ "subagents": { "agentOverrides": { "forge-verifier": { "model": "anthropic/claude-opus-4-8" } } } }
```

## rauf loop runner

After rauf has Pi provider support available, prefer:

```bash
rauf loop run <project> --agent pi --no-model
```

`--no-model` avoids forwarding Claude-authored model pins to Pi.
