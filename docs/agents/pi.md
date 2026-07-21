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

- Interactive input uses the bundled `AskUserQuestion` compatibility tool. In non-interactive print/JSON/RPC modes, that tool fails clearly rather than hanging or picking a default.
- Pi does not provide Claude-style subagents or the `Skill` dispatch tool. Where forge asks for researcher/verifier-style review, run the work inline or start a fresh Pi session manually.
- If `forge-root.sh` cannot find the bundle in a custom package layout, set `FEATURE_FORGE_ROOT` to the generated `adapters/pi` bundle root.

## rauf loop runner

After rauf has Pi provider support available, prefer:

```bash
rauf loop run <project> --agent pi --no-model
```

`--no-model` avoids forwarding Claude-authored model pins to Pi.
