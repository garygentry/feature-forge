# FORGE-105 fresh project and personal installs — 2026-08-26

## Scope and identity

- Task: `FORGE-105` only; fresh direct GitHub Copilot project and personal installs.
- Repository: `/home/gary/workspace/feature-forge`.
- Branch: `docs/copilot-g2-contract`.
- Base commit: `5a401ca43df98e0f8e4e87bc5a360cde296e4e30` (`0 0` against upstream before implementation).
- Implementation commit: `797fc60b60817af897d28ab57939a0a17d53c14a` (authorized and pushed to `origin/docs/copilot-g2-contract`).
- Current state: implementation and fresh-clone verification are durable; FORGE-105 may close.
- Pre-receipt tracked patch identity: `git diff --binary | sha256sum` = `7fa38a7b986414e9b2f90f0b4e06c80c1ca91a4ec299eb24bd020c5fada7c4ac`.
- Final post-review-fix tracked patch identity: `f4939c2b59084335198e738c3ebd16c5c571baef5219acc4204089f0c07e1935` (the untracked receipt itself is excluded).
- Rauf was not modified; FORGE-106 migration work was not started.

## Environment and source evidence

- OS: native Linux x86_64, kernel `5.15.0-185-generic`.
- Node: `v24.14.0`.
- GitHub Copilot CLI: `1.0.80`.
- Official GitHub Agent Skills documentation accessed 2026-08-26:
  `https://docs.github.com/en/copilot/concepts/agents/about-agent-skills`.
- The documentation identifies project skills at `.github/skills` (also `.claude/skills` or
  `.agents/skills`) and personal skills at `~/.copilot/skills` (also `~/.agents/skills`).
- `copilot skill --help` on 1.0.80 independently printed the same project and personal roots.
- Copilot CLI 1.0.80's installed runtime source creates project custom agents under
  `.github/agents/<name>.agent.md` and personal custom agents under its user config
  `agents/` directory. Runtime dispatch below proved both installer placements.

No token, credential, account identifier, raw environment dump, or complete model transcript is
retained. Runtime output was parsed only for bounded paths and PASS markers, then deleted.

## Implemented contract

1. Project direct installs retain one complete namespaced runtime at
   `<project>/.github/feature-forge` and native discovery mirrors at `.github/skills` and
   `.github/agents`.
2. Fresh personal installs now place the complete runtime at `~/.copilot/feature-forge`, beside
   native `~/.copilot/skills` and `~/.copilot/agents` mirrors. They no longer create a fresh
   primary bundle at `~/.github/feature-forge`.
3. Both direct scopes report Copilot confidence `verified-current` and the current Agent Skills
   documentation URL only after the runtime proof in this receipt passed.
4. Existing FORGE-104 containment, proven-only ownership, dry-run, copy/symlink, Windows fallback,
   and exact-file uninstall mechanics are unchanged. Focused tests additionally verify that the
   global manifest moves under `.copilot`, inventories the complete runtime and mirrors, and removes
   only owned files.
5. The legacy managed block remains present exactly as required by the task boundary. Existing old
   personal-layout discovery/migration is deferred to FORGE-106; no old manifest or content was
   removed or rewritten by this task.

## Focused installer verification

Command:

```bash
cd installer && npm test
```

Initial result: PASS, 201 tests passed, 0 failed. After independent review found a forged-primary
manifest boundary, the focused suite was expanded and rerun: PASS, 203 tests passed, 0 failed.
Relevant coverage includes:

- project `.github/feature-forge` complete runtime plus recursive skills and flat agents;
- personal `~/.copilot/feature-forge` complete runtime plus personal native mirrors;
- `verified-current` and current documentation URL propagation;
- global manifest destination/inventory and owned-file uninstall;
- fail-closed agent/scope/primary-destination ownership validation before uninstall, including a
  forged personal primary destination that cannot remove unrelated `~/.copilot/config.json`;
- explicit `-a copilot` behavior without generic `.github` auto-detection;
- recursive orphan pruning, pre-existing equal/different file non-ownership, symlink-ancestor
  rejection, manifest-root rejection, dry-run parity, primary symlink behavior, and Windows copy
  fallback.

`git diff --check` passed before this receipt.

## Full repository gate

Command:

```bash
env -u FEATURE_FORGE_ROOT bash scripts/validate.sh
```

Result: PASS.

- 2,496 Python tests passed, 2 skipped.
- 203 installer tests passed on the post-review-fix full-gate rerun.
- 11 Pi adapter-source tests passed.
- Plugin structure, strict Claude validation, frontmatter, permissions, spec purity, generated
  adapter drift, ruff, traceability, and four-field version synchronization passed.

## Copilot CLI 1.0.80 runtime proof

The probe used a disposable copy of `adapters/copilot` plus one bounded direct skill named
`forge105-scope-probe`. That skill ran the same Copilot root-selection prelude emitted by the
adapter, required the selected complete root's `scripts/forge-root.sh`, executed the installed
`forge-session.py doctor --json` helper, and printed only a root plus PASS marker. All Copilot
processes ran with `FEATURE_FORGE_ROOT` removed so the maintainer's Pi package could not contaminate
selection.

Before personal install, the harness refused to proceed if any complete-root, manifest, legacy
instruction file, skill, or agent destination already existed. A trap always ran installer
uninstall and removed only empty primary directories on failure.

### Fresh project scope

The built installer ran from a disposable project root with `-a copilot --skip-rauf --source`.
Copilot ran from `src/deep` for skill discovery and invocation.

`copilot skill list --json` reported:

```text
name=forge105-scope-probe
source=inherited
path=<fixture>/.github/skills/forge105-scope-probe
enabled=true
```

Exact direct invocation `/forge105-scope-probe` returned:

```text
FORGE105_ROOT=<fixture>/.github/feature-forge
FORGE105_RUNTIME=PASS
```

The installed project custom agent dispatched by exact name from the project root and returned:

```text
FORGE105_PROJECT_AGENT=PASS
```

The installer JSON reported `confidence=verified-current` and 140 primary runtime file creates.

### Fresh personal scope

The built installer ran with `-a copilot -g --skip-rauf --source` against the authenticated user's
otherwise-empty feature-forge personal targets. Copilot then ran from an unrelated disposable
working directory with no project customization root.

`copilot skill list --json` reported:

```text
name=forge105-scope-probe
source=personal-copilot
path=/home/gary/.copilot/skills/forge105-scope-probe
enabled=true
```

Exact direct invocation `/forge105-scope-probe` returned:

```text
FORGE105_ROOT=/home/gary/.copilot/feature-forge
FORGE105_RUNTIME=PASS
```

The personal custom agent dispatched by exact name and returned:

```text
FORGE105_PERSONAL_AGENT=PASS
```

The installer JSON reported `confidence=verified-current` and 140 primary runtime file creates.

### Probe correction record

No failed probe was counted as success. Initial harness attempts exposed three harness constraints:
project scope derives from the installer's current working directory; nested Copilot skill discovery
labels an ancestor project skill `inherited`; and `--no-custom-instructions` disables custom-agent
selection. A later run also exposed the interactive Pi package's exported `FEATURE_FORGE_ROOT`, which
correctly outranked installed roots. The final bounded run installed from the project root, invoked
project agents from that root, omitted `--no-custom-instructions` only for agent dispatch, and removed
`FEATURE_FORGE_ROOT` from every Copilot process. All four final runtime assertions then passed.

## Cleanup and safety

The personal install was uninstalled through the built installer. The disposable primary's now-empty
directory tree was pruned by the harness. Final checks confirmed all of these absent:

- `~/.copilot/feature-forge`;
- `~/.copilot/.feature-forge.global.json`;
- `~/.github/copilot-instructions.md`;
- `~/.copilot/skills/forge105-scope-probe`;
- `~/.copilot/agents/forge-researcher.agent.md`;
- all `/tmp/feature-forge-forge105.*` fixtures and raw JSONL output.

Project fixtures were removed by the same trap. No plugin marketplace, installed-plugin registry,
rauf file, release coordinate, tag, publication, or `RAUF_PIN` changed.

## Independent review and correction

Independent review found one P1: after the personal primary containment root moved to `~/.copilot`,
a forged manifest could claim the root itself as its primary destination and inventory unrelated
Copilot configuration. The review also found one P2 documentation overstatement about which paths
GitHub documents.

The implementation now validates manifest agent, scope, and exact primary destination against the
current trusted target before planning any uninstall mutation, then performs the existing trusted
placement validation. Unit coverage rejects each identity mismatch; a global Copilot E2E regression
forges `destination=~/.copilot` plus `files=[config.json]` and proves the user file, real installed
runtime, and manifest all survive the fail-closed uninstall. The README now distinguishes
vendor-documented native skill roots from runtime-proven complete/agent layouts. The focused suite
and post-fix clean-shell full gate pass 203/203 after these fixes. A final targeted diff review
confirmed both independent findings are resolved and found no remaining blocker.

## Fresh-clone durability and closure

After the authorized push, a disposable single-branch clone resolved exact HEAD
`797fc60b60817af897d28ab57939a0a17d53c14a` at `0 0` against its remote branch. The clone contained
the ACTIVE FORGE-105 ledger row and this receipt, reproduced the `.copilot` global target and primary
ownership guard, ran `npm ci --ignore-scripts` plus the complete installer `npm test` suite (203
passed), passed `git diff --check`, and remained clean. The disposable clone was removed by a trap.

FORGE-105 is durable and may close. Advance exactly one cursor to FORGE-106; no merge, tag, release,
publication, rauf modification, or `RAUF_PIN` change is authorized or performed.
