# @garygentry/feature-forge

Cross-agent installer for the [**feature-forge**](https://github.com/garygentry/feature-forge)
skill suite — an end-to-end feature-development pipeline that runs on any coding agent
(Claude, Codex, Copilot, Cursor, or Gemini).

This package installs the canonical forge skills into the agents detected on your machine.
It is dependency-free and performs sandboxed, manifest-tracked writes.

## Usage

```bash
# Install into every detected agent:
npx @garygentry/feature-forge install

# Scope to one agent:
npx @garygentry/feature-forge install -a codex

# Preview the plan without writing anything:
npx @garygentry/feature-forge install --dry-run --json
```

### Commands

| Command            | Description                                                       |
| ------------------ | ----------------------------------------------------------------- |
| `install` (`add`)  | Install feature-forge into the target agent(s).                   |
| `update`           | Reconcile an existing install to the current adapters.            |
| `uninstall` (`remove`) | Remove a prior install (manifest-tracked files only).         |
| `list` (`ls`)      | Report per-agent detected / installed / up-to-date status.        |

### Common flags

| Flag                | Description                                                            |
| ------------------- | --------------------------------------------------------------------- |
| `-a, --agent <id>`  | Scope to one agent (`claude`/`codex`/`copilot`/`cursor`/`gemini`).    |
| `-g, --global`      | Install into the user-level config dir (default: project-local).      |
| `--symlink`         | Symlink the bundle instead of copying (Windows always copies).        |
| `--dry-run`         | Print the planned actions without changing anything.                  |
| `--json`            | Emit the run report as JSON.                                          |
| `--skip-rauf`       | Skip the rauf resolvability preflight (records `raufPin: null`).      |

## Claude

Claude Code users can alternatively install via the plugin marketplace:

```bash
/plugin marketplace add garygentry/feature-forge
/plugin install feature-forge@feature-forge
```

## Notes

The default loop runner is [**rauf**](https://github.com/garygentry/rauf), published as
[`@garygentry/rauf`](https://www.npmjs.com/package/@garygentry/rauf). The installer runs a
read-only resolvability preflight on the pin (`@garygentry/rauf@0.8.0`) and records it; pass
`--skip-rauf` to defer the check (e.g. offline installs). Install the rauf CLI itself with
`npx @garygentry/rauf` or its
[binary script](https://github.com/garygentry/rauf#install). See the
[feature-forge README](https://github.com/garygentry/feature-forge#readme) for the full
pipeline documentation and per-agent setup guides.

## License

MIT
