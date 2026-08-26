# RAUF-204 Copilot Adapter Gates and Packaging Evidence — 2026-08-25

Status: Complete; implementation and evidence are pushed, Phase C exits, and the execution cursor
advances to `FORGE-101`.

## Attribution

- Task: `RAUF-204`
- Rauf base commit: `f02f0e77f3fb0820b1fae1b805984e6a6c4fc42b`
- Rauf branch: `feat/copilot-g2-contract`
- Rauf implementation commit: `8d6544123b5f873afb9fe313e6985dda5f35bdc8`
  (`build(copilot): gate adapter distribution`), pushed to
  `origin/feat/copilot-g2-contract`
- Pre-commit binary diff SHA-256:
  `a46cfbd78b876f3f17ac38f63009d3406c8eab2647ac3595fd19d1c0e837aa04`
- Platform: Ubuntu 22.04, native Linux x86_64
- Bun: 1.3.10
- pnpm: 9.15.0
- Node.js: 24.14.0
- Secrets retained: none

## Gates implemented

- Root `pnpm gate` now runs `copilot:check` after Codex/Pi adapter drift checks.
- Root `pnpm gate` also runs new `copilot:package:check` after build.
- `scripts/check-versions.ts` explicitly compares `adapters/copilot/plugin.json` with canonical
  `packages/core/src/version.ts`, in addition to all package manifests.
- `scripts/check-copilot-distribution.ts` verifies:
  - required repository plugin, four skills, and two agents exist;
  - the generated plugin version matches canonical rauf version;
  - built loop output contains the dedicated `copilot` provider;
  - built core output contains embedded `AGENTS_ADDON.md`, `.rauf/RAUF.md.tmpl`, and its managed
    ownership marker;
  - `npm-dist/` and its package `files` allowlist remain exactly the thin launcher surface
    (`LICENSE`, `README.md`, `package.json`, `rauf.mjs`);
  - the npm launcher resolves the same-version GitHub release binary; and
  - when `--binary <path>` is supplied, the compiled binary reports the canonical version and
    enumerates the dedicated `copilot` provider.

The operator plugin is intentionally repository/plugin distribution, not duplicated inside the thin
npm launcher. The npm artifact downloads the same-version compiled binary, which carries the runtime
provider and embedded installed-child instructions.

## Focused positive and negative checks

Commands:

```bash
pnpm build
pnpm version:check
pnpm copilot:check
pnpm copilot:package:check
pnpm exec eslint scripts/check-copilot-distribution.ts scripts/check-versions.ts
git diff --check
```

All passed.

Two disposable negative probes also passed:

1. Changed only `adapters/copilot/plugin.json` version from `0.14.0` to `9.9.9`.
   `pnpm version:check` failed and named the exact plugin path/value/expected version.
2. Appended a stale marker to `adapters/copilot/agents/rauf-loop-driver.agent.md`.
   `pnpm copilot:check` failed and named the changed generated path.

Both files were restored byte-for-byte, and the positive checks passed afterward.

## Compiled binary and npm package proof

A release-shaped Linux x64 baseline binary was compiled and checked:

```bash
bun build --compile --target=bun-linux-x64-baseline \
  scripts/binary-entry.ts --outfile /tmp/rauf-rauf204-linux-x64
bun run scripts/check-copilot-distribution.ts \
  --binary /tmp/rauf-rauf204-linux-x64
```

The binary returned canonical version `0.14.0` and enumerated provider id `copilot`. It then installed
into a disposable Git fixture with `--agent copilot`; the installed root `AGENTS.md` contained the
rauf host-neutral sentinel and `.rauf/RAUF.md` contained the managed child-instruction sentinel,
proving the compiled artifact carries the intended embedded instructions.

The npm launcher package was inspected without publishing:

```bash
cd npm-dist
npm pack --dry-run --json
```

Result:

```text
version=0.14.0
files=LICENSE,README.md,package.json,rauf.mjs
```

No adapter source or unrelated repository file entered the launcher tarball.

## Full repository gate

The complete gate ran under a disposable empty `HOME`:

```bash
tmp_home=$(mktemp -d /tmp/rauf-rauf204-home.XXXXXX)
trap 'rm -rf "$tmp_home"' EXIT
HOME="$tmp_home" pnpm gate
```

Result: build, schema/version checks, Codex/Pi/Copilot drift, Copilot distribution check, typecheck,
lint, formatting, documentation, 2,194 package tests, and 91 repository-script tests passed.

## Cleanup and final state

The compiled binary, package JSON receipt, install fixture, negative-probe outputs, and disposable
HOME were removed. No registry, plugin, release, tag, or published artifact was changed. The rauf
branch is clean and synchronized with its matching origin at commit `8d65441`; feature-forge records
this milestone separately on its owning adaptation branch.
