# Changelog

All notable changes to feature-forge are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.0] — 2026-06-09

### Changed

- **Extracted to its own repository.** feature-forge now lives at
  [`garygentry/feature-forge`](https://github.com/garygentry/feature-forge)
  instead of inside the `garygentry/agent-plugins` monorepo. Full commit
  history was preserved via `git subtree split`.
- The repository root **is** the plugin: it carries both the marketplace
  catalog (`.claude-plugin/marketplace.json`, registered with `"source": "."`)
  and the plugin manifest (`.claude-plugin/plugin.json`).
- Added a self-contained `scripts/validate.sh` that validates the flattened
  single-plugin layout (the monorepo previously supplied a marketplace-wide
  validator).

### Install

```
/plugin marketplace add garygentry/feature-forge
/plugin install feature-forge@feature-forge
```

The previous `feature-forge@gwg-plugins` entry in `agent-plugins` remains as a
deprecated stub for one release cycle so existing installs keep working.

### Notes

- This release is a **pure structural move** — no skill behavior changed. The
  pipeline still invokes the `rauf` CLI exactly as in 0.7.0. Config-driven
  loop-runner indirection and delegation to rauf's backlog contract land in a
  later release (tracked in `COMPATIBILITY.md`).

## [0.7.0] and earlier

See git history (`git log`) for changes prior to the repository extraction,
including the `ralph` → `rauf` rename and the stack-agnostic profile system.
