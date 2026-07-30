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

**Between stages, forge recommends starting a fresh session with Pi's `/new`** (Claude's equivalent is `/clear`). Every artifact is on disk, so the work survives it; a clean session is the recommended default at each stage boundary. Both the skill prose and the scripted stage-exit block (`forge-session.py --host pi`) name `/new` and emit `/skill:` next-commands. One residual: the copied `references/` files (e.g. `stage-exit-protocol.md`) are self-contained **verbatim** copies of canon and still show Claude's `/clear`/`/feature-forge:` — they are secondary model-facing guidance; the SKILL body is the primary instruction surface and is fully translated.

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

Both install paths register the agents, by different routes:

- **Package install** (the bundle directory listed in the `packages` list in Pi settings, for example `~/workspace/feature-forge-pi/adapters/pi`): discovery resolves package roots from `packages` and reads the `pi-subagents.agents` manifest key above.
- **`npx ... install -a pi`**: the copied bundle under `skills/` is not a package root, so the manifest key is never read there. Instead the installer *mirrors* `agents/*.md` flat into the scope pi-subagents scans directly — `~/.pi/agent/agents/` with `--global`, `.pi/agents/` for a project install. Same three agents, registered at user/project scope rather than package scope.

### Translated frontmatter

Canon's Claude agent frontmatter is translated into `pi-subagents`' schema, not dropped. The mapping (in `PiEmitter.emit_agent`) was confirmed by round-tripping each generated file through pi-subagents 0.35.1's real loader:

| canon (Claude) | Pi frontmatter | notes |
|---|---|---|
| `tools: Read, Glob, Grep, Bash` | `tools: read, find, ls, grep, bash` | Pi builtin names; `Glob` has no single analogue, so it expands to `find`+`ls` |
| `+ Write` (spec-writer) | `+ write, edit` | |
| `maxTurns: N` | `turnBudget: '{"maxTurns": N}'` | a single-line JSON string — pi `JSON.parse`s it |
| `effort: medium` | `thinking: medium` | |
| `memory: project` | `memory: { scope: project, path: <agent-name> }` | durable per-role memory |
| `skills: [forge-verify]` | `skills: forge-verify` | |
| `model: opus` / `sonnet` | *dropped* | see the model-override note below |

Plus three Pi-only fields canon has no analogue for, each derived from the tool allowlist so a new agent needs no extra wiring:

- **`inheritProjectContext: true`** — non-builtin agents default to `false`, so without this a forge agent would ignore the target repo's `AGENTS.md`/`CLAUDE.md`.
- **`acceptanceRole`** — `writer` for an agent that carries `Write` (spec-writer), `read-only` otherwise. This makes `forge-verifier`'s read-only contract **tool-enforced**, not just prose-enforced.
- **`completionGuard: false`** on the read-only agents — they carry `bash`, which pi-subagents classifies as mutation-capable, so a verifier that correctly changes nothing would otherwise be judged a failed implementation agent.

The one canon key still dropped is `model`: `opus`/`sonnet` are Claude aliases, not Pi model ids. Unpinned agents inherit the session model or `subagents.defaultModel`. To give one role a stronger model, set an override in Pi settings rather than editing the generated agent file:

```json
{ "subagents": { "agentOverrides": { "forge-verifier": { "model": "anthropic/claude-opus-4-8" } } } }
```

## rauf loop runner

After rauf has Pi provider support available, prefer:

```bash
rauf loop run <project> --agent pi --no-model
```

`--no-model` avoids forwarding Claude-authored model pins to Pi.
