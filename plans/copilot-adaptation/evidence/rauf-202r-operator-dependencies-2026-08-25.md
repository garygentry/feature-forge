# RAUF-202R Copilot Operator Dependency Evidence — 2026-08-25

Status: Complete; implementation and evidence are pushed, and the execution cursor advanced to
`RAUF-203`.

## Attribution

- Task: `RAUF-202R`
- Rauf base commit: `02f8e67846ccf1ae59443a75c310458d6236ea6d`
- Rauf milestone commit: `4668553` (`feat(adapters): compose Copilot operator skills`)
- Branch: `feat/copilot-g2-contract`, clean and tracking its matching origin after push
- Final dirty-tree diff identity after all adapter regeneration: SHA-256
  `76461c9c8e13bc792fb55ca639061a850681d4c95087fc3523a61b2091db534c`
- Platform: Ubuntu 22.04.5 LTS, native Linux x86_64
- Kernel: `5.15.0-185-generic #195-Ubuntu SMP Fri Jun 19 17:11:50 UTC 2026`
- Bun: 1.3.10
- pnpm: 9.15.0
- Copilot CLI: exact npm package `@github/copilot@1.0.80`, invoked through `npx --yes`
- Authentication: existing user context; no credential values inspected or retained
- Secrets retained: none

## Dependency mechanism

The captured Copilot custom-agent contract has no declarative skill-dependency frontmatter field.
The generator now gives each explicit agent policy a fail-loud `requiredSkill`:

- `rauf-backlog-reviewer` → `review-backlog`
- `rauf-loop-driver` → `drive-rauf-loop`

It parses every canonical skill first, rejects an unknown dependency, and composes the complete
required canonical skill body into the generated custom-agent body. Generated provenance and
`COPILOT-BUNDLE-REPORT.md` name both canonical sources. This preserves one canonical skill source
while ensuring its complete procedure is present in the custom-agent context rather than relying on
an aspirational body reference or an unsupported schema key.

Generated hashes used by the runtime probes:

```text
80c6ea974ccd4269b65de3cd7901c4066cfced65979b83f64a5ca5c535a96c4c  adapters/copilot/plugin.json
ce597b02d6ea4deb2f2739748e288ea80904f6ffb3be57dcd38915158f4deac9  adapters/copilot/agents/rauf-backlog-reviewer.agent.md
6b862fe366fec3a15e00092988e1d191e3453a2622b7f665c48c76eb5f98a09c  adapters/copilot/agents/rauf-loop-driver.agent.md
```

## Host-neutral canonical wording

The portable `skills/author-backlog/SKILL.md` no longer tells every provider to use Claude's
`Task tool`. It now says the loop agent uses its host's subagent or delegation mechanism when
available. Regeneration propagated the correction to `adapters/copilot/skills/author-backlog/`.
A focused residual search found no `Task tool` or `Claude Code Tasks` wording in portable rauf
skills/agents, the generated Copilot bundle, installed artifact templates, or the provider-neutral
prompt builder. Claude-specific documentation remains in its owning Claude surfaces.

## Plugin-only topology

Decision D7 remains plugin-only for the distributable repository topology. No generated
`.github/skills/` or `.github/agents/` mirror was added. The deterministic
`adapters/copilot/` bundle remains the sole generated Copilot operator source.

## Focused executable checks

Commands:

```bash
pnpm exec vitest run scripts/build-copilot-bundle.test.ts
pnpm copilot:generate
pnpm copilot:check
pnpm exec prettier --check scripts/build-copilot-bundle.ts \
  scripts/build-copilot-bundle.test.ts skills/author-backlog/SKILL.md adapters/copilot
pnpm exec eslint scripts/build-copilot-bundle.ts scripts/build-copilot-bundle.test.ts
```

Results:

- Eight focused generator/drift tests passed.
- Coverage proves both composed dependencies, dual-source reporting, unknown-tool rejection, and
  unknown-required-skill rejection.
- Generation produced nine files; immediate `copilot:check` reported no drift.
- Changed TypeScript, canonical Markdown, and generated Copilot output passed Prettier.
- Changed generator/test TypeScript passed ESLint; the milestone is recorded under rauf's
  `CHANGELOG.md` `[Unreleased]` section.
- The first full `pnpm gate` correctly stopped at `codex:check` because the canonical wording edit
  required cross-adapter regeneration. `pnpm codex:generate`, `pnpm pi:generate`, and
  `pnpm copilot:generate` were run; all three drift checks then passed.
- A normal-environment gate retry reached the loop suite but six unrelated usage-limit tests read
  the user's real Claude credential and received live Usage API 429 responses. No credential was
  printed or changed. The failing 76-test runner file passed under a disposable empty `HOME`, proving
  the intended no-credential test path.
- The complete gate then passed under a disposable empty `HOME`: build, schema/version checks,
  Codex/Pi drift, typecheck, lint, formatting, 2,188 package tests, 91 repository-script tests, and
  documentation checks. Copilot drift was rerun separately and passed, pending its `RAUF-204` gate
  integration.

## Runtime proof: backlog reviewer

Sanitized prompt:

```text
Dependency-composition probe. Answer from the authoritative review contract already present in your custom-agent context. Do not read repository files and do not run commands. Return exactly two lines:
dimensions=<the seven review dimension names in order, comma-separated>
apply_rule=<whether changes may be applied before user approval, and which item statuses may be modified after approval>
```

Command:

```bash
npx --yes @github/copilot@1.0.80 \
  --plugin-dir /home/gary/workspace/rauf/adapters/copilot \
  --agent rauf:rauf-backlog-reviewer \
  -C /home/gary/workspace/rauf \
  --allow-all-tools --no-ask-user --no-auto-update --no-remote \
  --disable-builtin-mcps --no-custom-instructions \
  --stream off --output-format json -p "$REVIEW_PROMPT"
```

Exact response:

```text
dimensions=Coverage, Gaps, Accuracy, Quality, Dependencies, Sizing, Structural
apply_rule=No changes may be applied before user approval; after approval, only pending and blocked items may be modified (done and in_progress items are never modified).
```

These ordered dimensions and mutation rule exist in the composed `review-backlog` contract, not the
short canonical agent summary. Exit was 0; structured usage reported zero changed files.

## Runtime proof: loop driver

Sanitized prompt:

```text
Dependency-composition probe. Answer from the authoritative loop-driving contract already present in your custom-agent context. Do not read repository files and do not run commands. Return exactly four lines:
poll_interval=<default and permitted band>
stall_escalation=<required consecutive poll count>
reset_trigger=<the exact lock condition that permits reset>
decision_precedence=<the four decision rows in order>
```

Command:

```bash
npx --yes @github/copilot@1.0.80 \
  --plugin-dir /home/gary/workspace/rauf/adapters/copilot \
  --agent rauf:rauf-loop-driver \
  -C /home/gary/workspace/rauf \
  --allow-all-tools --no-ask-user --no-auto-update --no-remote \
  --disable-builtin-mcps --no-custom-instructions \
  --stream off --output-format json -p "$DRIVER_PROMPT"
```

Exact response:

```text
poll_interval=5s default, band 5–10s
stall_escalation=3 consecutive polls
reset_trigger=lock.stale === true && lock.alive === false
decision_precedence=done > needs-human > recoverable stall > healthy in-progress
```

These values and precedence exist in the composed `drive-rauf-loop` contract, not the short
canonical agent summary. Exit was 0; structured usage reported zero changed files.

## Cleanup and final-state checks

Disposable structured logs lived only under `/tmp/rauf-copilot-rauf202r-2026-08-25` and are removed
with:

```bash
rm -rf /tmp/rauf-copilot-rauf202r-2026-08-25
test ! -e /tmp/rauf-copilot-rauf202r-2026-08-25
```

The probes used ephemeral `--plugin-dir`; they installed no plugin and made no workspace edits.
Post-cleanup registry verification reported no installed plugins and only Copilot's included
`copilot-plugins` and `awesome-copilot` marketplaces. Commit `4668553` is pushed on the adaptation
branch; `EXECUTION.md` records the clean milestone and advances the sole cursor to `RAUF-203`.
