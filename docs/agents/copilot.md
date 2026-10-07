---
title: "feature-forge on Copilot"
---

# feature-forge on Copilot

> Canonical skills for the feature-forge pipeline, installed onto GitHub Copilot.
> The skills are spec-pure; Copilot's adapter is generated from canon (do not hand-edit
> `adapters/copilot/`).

Copilot loads feature-forge natively: `skills/<name>/SKILL.md` Agent Skills plus
`<name>.agent.md` custom agents. Nothing is written into `.github/copilot-instructions.md`.

## Supported versions

| Surface | Supported |
| --- | --- |
| GitHub Copilot CLI | 1.0.78 or later. Discovery, invocation and runtime-root resolution are runtime-verified on 1.0.80. |
| VS Code + Copilot Chat | VS Code 1.134.0 with Copilot Chat 0.62.0 or later |
| Platform | Linux x64, including WSL2. The installer itself is CI-tested on Ubuntu, macOS and Windows, but Copilot runtime behavior is verified on Linux x64 only. |
| Node.js (installer) | 18 or later |
| Python (runtime helpers) | 3.10 or later |

## Install

There are two ways to get the bundle into Copilot: as a Copilot **plugin**, or as a **direct
install** with the npm installer. Plugins are Copilot's preferred distribution, but feature-forge
does not yet publish a Copilot plugin source that works out of the box (see
[Plugin install](#plugin-install)). **Use the direct install.**

### Direct install (recommended)

Project scope writes one complete runtime bundle at `.github/feature-forge/` plus native discovery
mirrors under `.github/skills/` and `.github/agents/`:

```bash
npx @garygentry/feature-forge install -a copilot
```

Personal scope writes the complete runtime at `~/.copilot/feature-forge/` plus mirrors under
`~/.copilot/skills/` and `~/.copilot/agents/`:

```bash
npx @garygentry/feature-forge install -a copilot --global
```

To see the exact destinations without writing anything:

```bash
npx @garygentry/feature-forge install -a copilot --dry-run --json
```

The plan lists the complete-runtime destination and every native placement. GitHub documents
project skills at `.github/skills/` and personal skills at `~/.copilot/skills/`. Both scopes are
runtime-verified on Copilot CLI 1.0.80, so the installer reports them as `verified-current`.

The installer records every file it writes in a manifest (`.github/.feature-forge.project.json`,
or `~/.copilot/.feature-forge.global.json` for personal scope). It never takes ownership of a file
it did not write: an existing skill or agent file with the same name is left in place, and
`uninstall` will not remove it.

### Plugin install

A Copilot plugin install of feature-forge works when a Copilot plugin marketplace serves the
generated `adapters/copilot/` bundle as its `feature-forge` plugin:

```bash
copilot plugin marketplace add <marketplace-source>
copilot plugin install feature-forge@<marketplace>
```

Copilot then places the bundle at `~/.copilot/installed-plugins/<marketplace>/feature-forge/`, where
the skills find their runtime with no extra setup. This is the layout verified on Copilot CLI 1.0.80.

Two routes look like they should work but do not today (tracked in
[#360](https://github.com/garygentry/feature-forge/issues/360)):

- `copilot plugin marketplace add garygentry/feature-forge` reads this repository's Claude
  marketplace, so `feature-forge@feature-forge` installs the **Claude** bundle, not the Copilot one.
- `copilot plugin install garygentry/feature-forge:adapters/copilot` installs the right bundle, but
  under `~/.copilot/installed-plugins/_direct/garygentry--feature-forge--adapters-copilot/`, which
  the runtime resolver does not search. Skills then fail to find their runtime unless you set
  `FEATURE_FORGE_ROOT` to that directory. Copilot also marks direct repository installs deprecated.

## Invoking skills

Copilot names the same skill differently depending on how it was installed:

| Install | Invocation |
| --- | --- |
| Plugin | `/feature-forge:<name>` (for example `/feature-forge:forge-1-prd my-feature`) |
| Direct (project or personal) | `/<name>` (for example `/forge-1-prd my-feature`) |

So the bundle never hard-codes either form. Skill bodies, references and the stage-exit NEXT STEPS
block (`forge-session.py stage-exit --host copilot`) write `invoke-skill: <name> [arguments]`, and
each skill's closing "Host execution notes (GitHub Copilot)" section tells Copilot to map that to
whichever form your install provides. When a skill says `invoke-skill: forge-2-tech my-feature`,
type `/forge-2-tech my-feature` on a direct install or `/feature-forge:forge-2-tech my-feature` on a
plugin install.

The three worker agents (`forge-researcher`, `forge-spec-writer`, `forge-verifier`) are subagents
only (`user-invocable: false`). They do not appear in the agent picker; the stage skills dispatch
them. Each carries least-privilege Copilot tool aliases (`read`, `search`, `execute`, and `edit` for
the spec writer only), inherits the parent's model, and cannot delegate further. Copilot custom
agents have no skill-dependency field, so `forge-verifier` embeds the complete `forge-verify`
procedure. Copilot also guarantees no per-agent persistent memory, so the verifier does not keep a
`MEMORY.md`.

## Where skills find their runtime

Skills run helper scripts (`forge-session.py`, `epic-manifest.py`, …) from the complete runtime
bundle. On Copilot each skill resolves that bundle in this order and uses the first match:

1. `FEATURE_FORGE_ROOT`, if set. It must be a complete bundle containing
   `scripts/forge-root.sh`; otherwise the skill stops with an error instead of guessing.
2. `.github/feature-forge/` in the current directory or the nearest parent directory that has one
   (so a project install works from any subdirectory).
3. A plugin install: `~/.copilot/installed-plugins/*/feature-forge/`.
4. The personal install: `~/.copilot/feature-forge/`.
5. Other agents' install roots (Claude, Codex/agents), last, so another agent's bundle never
   shadows the Copilot one.

A bundle with missing files is reported as `install incomplete/degraded` rather than used. Set
`FEATURE_FORGE_ROOT` when you keep the runtime somewhere else or need to force one bundle:

```bash
export FEATURE_FORGE_ROOT="$HOME/.copilot/feature-forge"
```

## Upgrading an install from installer 0.3.9 or earlier

Installer 0.3.9 and earlier (feature-forge 0.21.0 and earlier) put the whole bundle at
`.github/feature-forge/` in both scopes (personal installs under `~/.github/`), with skills as
`skills/<name>/<name>.md`, and wrote a pointer block between
`<!-- feature-forge:managed:start -->` and `<!-- feature-forge:managed:end -->` in
`.github/copilot-instructions.md`. Migrate it with:

```bash
npx @garygentry/feature-forge update -a copilot      # project install
npx @garygentry/feature-forge update -a copilot -g   # personal install
```

A plain `update` (or `update -g`) with no `-a` also finds and migrates an old Copilot install,
because its install manifest counts as detecting Copilot even when `.copilot/` does not exist.

- The update writes and hash-verifies the new runtime and native mirrors first, then removes only
  the files the old manifest recorded, then writes the new manifest. A personal install moves from
  `~/.github/feature-forge/` to `~/.copilot/feature-forge/`.
- If the update fails partway, run it again. It journals the files it is about to write
  (`<manifest>.migrating`), so a retry takes ownership of exactly those files and nothing else.
- A symlinked old runtime is unlinked, never followed, so the package it pointed at is untouched.
- The pointer block is removed only if you never edited it. Your own text in the file stays. An
  edited block is kept and `list` reports `retired-block:edited` until you run
  `update -a copilot --force`, which strips only the text between the sentinels.
- An old copy install cannot switch straight to `--symlink`: update without `--symlink`, or add
  `--force` to replace it.

## Checking an install

```bash
npx @garygentry/feature-forge list -a copilot        # project scope; add -g for personal
```

`list` reports whether the install is present and up to date. An install from 0.3.9 or earlier shows
`legacy-layout:true` (run `update`); a kept edited pointer block shows `retired-block:edited`.

For the environment as feature-forge sees it, ask Copilot to run the doctor:
`/forge-guide --doctor` on a direct install, or `/feature-forge:forge-guide --doctor` on a plugin
install. It runs `forge-session.py doctor` from the resolved runtime (the report includes
`hostArg: copilot`), explains each finding and offers the repairs. You can also run it yourself:

```bash
python3 .github/feature-forge/scripts/forge-session.py doctor --json            # project install
python3 ~/.copilot/feature-forge/scripts/forge-session.py doctor --json         # personal install
```

To confirm Copilot discovered the skills, run `copilot skill list --json`. Invoke one skill (for
example `/forge-init`) to confirm it resolves its runtime.

## Uninstall

Direct install:

```bash
npx @garygentry/feature-forge uninstall -a copilot      # project install
npx @garygentry/feature-forge uninstall -a copilot -g   # personal install
```

`uninstall` removes only the files the manifest records, after checking that the manifest's
runtime and mirror paths belong to Copilot and this scope. Files the installer did not write,
such as your own skills in `.github/skills/`, are left in place. It also removes an install from 0.3.9 or earlier (old runtime, its manifest and an unedited
pointer block) without upgrading it first.

Plugin install:

```bash
copilot plugin uninstall feature-forge
```

## Loop runner (forge-5-loop)

See [The default loop runner](claude.md#the-default-loop-runner): feature-forge defaults to
rauf and selects the coding agent via the documented precedence.
