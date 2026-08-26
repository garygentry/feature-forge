# RAUF-203 Child Instruction Ownership Evidence — 2026-08-25

Status: Complete; implementation and evidence are pushed, and the execution cursor advances to
`RAUF-204`.

## Attribution

- Task: `RAUF-203`
- Rauf base commit: `46685532c473db766c47d04d0534d9910fa52b44`
- Rauf branch: `feat/copilot-g2-contract`
- Rauf implementation commit: `f02f0e77f3fb0820b1fae1b805984e6a6c4fc42b`
  (`feat(installer): preserve child instruction ownership`), pushed to
  `origin/feat/copilot-g2-contract`
- Pre-commit binary diff SHA-256 after implementation, changelog, generation, tests, and gate:
  `91d87d69cd9ced2f3e7c2f9504b6031a15601779ebecb238e5f01155ba36b3f2`
- Feature-forge planning base: `dc58d9514eb2c873ae51c9c844b48ee011e4ad72`
- Platform: Ubuntu 22.04, native Linux x86_64
- Kernel: `5.15.0-185-generic #195-Ubuntu SMP Fri Jun 19 17:11:50 UTC 2026`
- Bun: 1.3.10
- pnpm: 9.15.0
- Node.js: 24.14.0
- Copilot CLI: exact npm package `@github/copilot@1.0.80`, invoked through `npx --yes`
- Authentication: existing user context; no credential values inspected, logged, or retained
- Secrets retained: none

## Ownership contract implemented

Rauf now keeps three independent instruction surfaces:

1. Root `AGENTS.md` contains the host-neutral `<!-- rauf:agents:start/end -->` block used by
   ordinary standalone agents, including Copilot.
2. Root `CLAUDE.md` retains only the Claude specialization in its independent
   `<!-- rauf:start/end -->` block.
3. `.rauf/RAUF.md` contains the complete iteration-child contract inside
   `<!-- rauf:managed:start/end -->`. Project-specific content belongs below the explicit user
   anchor and survives install, update, repeated update, and uninstall.

The real Copilot iteration provider still passes `--no-custom-instructions`; `buildPrompt` reads the
resolved `.rauf/RAUF.md` and passes that content to the provider. Tests also prove that `AGENTS.md`
and `CLAUDE.md` sentinels are not copied into the generated iteration prompt.

Legacy behavior is fail-safe:

- The prior verification-only sentinel layout migrates to the full managed contract while preserving
  bytes below its documented user anchor.
- An existing unbounded `RAUF.md` is preserved verbatim below the new managed contract rather than
  overwritten.
- Missing, reversed, or duplicate ownership sentinels fail closed without rewriting or deleting the
  file.
- Uninstall removes only managed instructions. It deletes a managed-only `RAUF.md`, but preserves
  project-specific content and removes the installation marker only after safe instruction cleanup.
- Automated lifecycle coverage proves rauf and feature-forge managed regions coexist in `AGENTS.md`.

## Focused executable checks

Commands:

```bash
pnpm --filter @rauf/core exec vitest run \
  src/installer.test.ts src/agent-instructions.test.ts src/repo-integrity.test.ts
pnpm --filter @rauf/core typecheck
pnpm --filter @rauf/loop exec vitest run \
  src/prompt-builder.test.ts src/providers/copilot-cli.test.ts
pnpm --filter @rauf/loop typecheck
pnpm exec prettier --check <changed implementation/test/template/spec files>
git diff --check
```

Results:

- Core ownership slice: 107 tests passed.
- Loop prompt/provider isolation slice: 67 tests passed.
- Core and loop typechecks passed.
- Changed files passed Prettier and `git diff --check`.

Canonical/reference changes were regenerated and checked:

```bash
pnpm pi:generate
pnpm codex:generate
pnpm copilot:generate
pnpm pi:check
pnpm codex:check
pnpm copilot:check
```

The generated Pi references changed because `docs/SPEC-CORE.md` is included by those bundles.
Codex and Copilot outputs remained synchronized. The user-facing lifecycle change is recorded under
`CHANGELOG.md` `[Unreleased]`.

## Full repository gate

The first isolated-home gate correctly stopped at `pi:check` after the canonical spec changed. The
Pi, Codex, and Copilot outputs were regenerated; all three drift checks passed. The complete gate was
then rerun with a disposable empty `HOME`:

```bash
tmp_home=$(mktemp -d /tmp/rauf-rauf203-home.XXXXXX)
trap 'rm -rf "$tmp_home"' EXIT
HOME="$tmp_home" pnpm gate
```

Result: build, schema/version checks, Codex/Pi drift, typecheck, lint, formatting, documentation,
2,194 package tests, and 91 repository-script tests passed. `pnpm copilot:check` was also rerun and
passed; wiring it into `pnpm gate` remains owned by `RAUF-204`.

## Runtime proof: standalone Copilot loads installed AGENTS.md

A disposable Git repository was created under
`/tmp/rauf-copilot-rauf203-2026-08-25/project`. Before installation its root instruction file
contained the sanitized nonce `AGENTS_NONCE=rauf203-agents-loaded`. Source `scripts/bin/rauf install`
merged the canonical host-neutral rauf block.

Sanitized prompt:

```text
Do not use tools or read files. From repository custom instructions already loaded at session
start, return exactly two lines:
agents_nonce=<value of AGENTS_NONCE or UNSET>
rauf_instruction=<the path named for detailed per-iteration instructions or UNSET>
```

Command:

```bash
npx --yes @github/copilot@1.0.80 -C "$FIXTURE" \
  --no-ask-user --no-auto-update --no-remote --disable-builtin-mcps \
  --stream off --output-format json -p "$STANDALONE_PROMPT"
```

Exact assistant response:

```text
agents_nonce=rauf203-agents-loaded
rauf_instruction=.rauf/RAUF.md
```

Exit was 0, no tool requests were emitted, and structured usage reported zero changed files. This
proves ordinary standalone Copilot loaded the installed root `AGENTS.md` block without reading it as
a tool action.

## Runtime proof: isolated iteration-style prompt

The same fixture contained distinct ambient `AGENTS.md` and `CLAUDE.md` nonces. An iteration-style
prompt file supplied only:

```text
prompt_nonce=rauf203-prompt-injected
agents_nonce=UNSET
claude_nonce=UNSET
```

Command (matching the provider's frozen isolation/permission flags; model omitted):

```bash
npx --yes @github/copilot@1.0.80 -C "$FIXTURE" \
  --output-format json --stream off \
  --allow-tool=read --allow-tool=write --allow-tool=shell \
  '--deny-tool=shell(git commit:*)' '--deny-tool=shell(git push:*)' \
  --no-ask-user --no-remote --no-remote-export --no-custom-instructions \
  --disable-builtin-mcps --no-auto-update \
  -p 'Read the complete instructions from isolated-prompt.md, follow them, and do not modify that file.'
```

Exact assistant response:

```text
prompt_nonce=rauf203-prompt-injected
agents_nonce=UNSET
claude_nonce=UNSET
```

Exit was 0 and structured usage reported zero changed files. The model's first broad shell lookup was
denied, after which workspace glob/view found the named prompt file. This additionally demonstrates
the bounded permission behavior; neither ambient nonce entered the response. The repository tests
remain the exact production-chain proof: resolved `RAUF.md` -> `buildPrompt` -> provider prompt file,
with `--no-custom-instructions` asserted on the provider argv.

## Runtime proof: repeated update and uninstall

Against the installed disposable fixture:

```bash
scripts/bin/rauf update "$FIXTURE"
scripts/bin/rauf update "$FIXTURE"
scripts/bin/rauf uninstall "$FIXTURE"
```

The combined SHA-256 of `AGENTS.md`, `CLAUDE.md`, and `.rauf/RAUF.md` was identical before update,
after update 1, and after update 2:

```text
c18d6970db638814f0e1073dad7c39fe82cfbac3a69ae9f3a401b4d61c0a2da9
```

After uninstall:

- the pre-existing AGENTS nonce remained;
- the pre-existing CLAUDE nonce remained;
- project-specific `RAUF203_PROMPT_NONCE=rauf203-prompt-injected` remained;
- all three rauf managed sentinels were absent; and
- `.rauf.json` was absent.

## Cleanup and final state

The runtime JSONL logs, prompt file, fixture, and temporary command outputs were removed:

```bash
rm -rf /tmp/rauf-copilot-rauf203-2026-08-25 \
  /tmp/rauf203-install.out /tmp/rauf203-update1.out \
  /tmp/rauf203-update2.out /tmp/rauf203-uninstall.out
test ! -e /tmp/rauf-copilot-rauf203-2026-08-25
```

No plugin was installed and no registry entry was changed. The rauf branch is clean, synchronized
with its matching origin, and contains commit `f02f0e7`. The feature-forge tracker/evidence update is
committed separately on its owning adaptation branch.
