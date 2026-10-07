# AGENTS.md — feature-forge

> **Which task are you here for?**
> This file is for agents **contributing to the feature-forge repository itself** — building the
> adapters, running the checks, opening PRs against this repo.
> If you were asked to **install or use feature-forge in another project** (the user pasted this
> repo's URL, or said "set up feature-forge for me"), **stop reading this file** and follow
> [`AGENTS-SETUP.md`](AGENTS-SETUP.md) instead — it is the deterministic install-and-start
> procedure. Nothing below applies to that task.

feature-forge is a vendor-neutral, spec-pure skill canon that builds per-agent adapters
deterministically. This file is the cross-agent entry point: it tells any AI coding agent
(Claude, Codex, Copilot, Cursor, Gemini, or a future target) how to build, test, and
contribute to this repository.

## Build & Test

| Command | Purpose |
|---------|---------|
| `bash scripts/validate.sh` | **Single verify gate** — runs all checks (spec-purity, drift guard, tests). This is the only command you need before committing. |
| `python3 scripts/build-adapters.py` | Regenerate all per-agent adapter bundles under `adapters/`. Run this whenever you edit canon (`skills/`, `agents/`, `references/`). |
| `python3 scripts/build-adapters.py --check` | Check that `adapters/` matches a fresh generation without writing anything. Exits 0 if in sync, 1 if there is drift. |
| `python3 scripts/check-spec-purity.py` | Check that the canonical surfaces (`skills/`, `agents/`, `references/`) are free of vendor-specific frontmatter. |

`bash scripts/validate.sh` auto-provisions the pinned YAML dependency into `.venv-adapters`
and the pinned test dependencies (pytest, jsonschema, PyYAML) into `.venv-test` the first time
it runs — no manual setup is needed. The first run needs network access; if provisioning fails
the gate FAILS loudly rather than skipping the suite.

## Branching & merging

Every change reaches `main` **via a pull request** with green CI (`ci.yml` /
`os-matrix.yml`, which run `bash scripts/validate.sh`) — never a direct push to `main`:

1. Branch from an up-to-date `main`.
2. Make the change; run `bash scripts/validate.sh` locally until green (regenerate adapters if
   you touched canon — the drift guard blocks an out-of-date `adapters/` tree).
3. Push the branch, open a PR, let CI go green, then merge.

This mirrors the sibling **rauf** repo's process. The shared release principles across both
repos: (1) a merge to `main` **never publishes**; (2) publishing is **tag-triggered and gated
by one owner approval** on the `release` environment (ADR 0046 Amendment 4) — the agent runs
everything up to the gate, only the owner can approve it; (3) **bump the version before
publishing** (npm rejects republishing a version); (4) **offer, don't act** — suggest a release,
and cut one (prep PR + tag) only once the user has said yes. rauf and
feature-forge are versioned **independently** (no lockstep); the only coupling is the
`RAUF_PIN` provisioned-default coordinate plus `COMPATIBILITY.md`.

## Verification conventions (forge-verify on this repo)

**`CHECK-I21` runs the configured `smokeCommand` on this repo.** `forge.config.json` sets
`"smokeCommand": "python3 scripts/forge-session.py doctor --json"` — a legitimate,
non-fabricated health smoke that exits 0 and emits valid health JSON. `CHECK-I21`
runs it and passes iff exit 0. The heavier `"testCommand": "bash scripts/validate.sh"`
remains a strict superset for coverage — it drives spec-purity, the adapter drift gate,
the full pytest suite, the `adapter-src/pi` verify, ruff, traceability, and version-sync —
but the smoke is retained because keeping it means "clean" also proves the CLI *runs*.
(This supersedes the earlier `null`-by-design / `not-applicable` convention from owner
decision 2026-07-29, finding V-013 of the `context-efficiency` impl verify; reinstated by
finding V-001 of the `loop-recovery` impl verify.) Never fabricate a command.

## Prose-change gate (compliance eval)

`eval/run-compliance-eval.py` is the **regression oracle for prose changes** — the only
instrument that measures what a model does with the canon it actually reads, once a skill
is driving. It is not a correctness gate: it reports a *rate over N runs*, never
pass/fail, and CI never runs it on the merge path (costs money, needs the Claude CLI,
weekly cron is trigger-accuracy only).

A PR whose diff touches `skills/*/SKILL.md` body text, `references/stage-exit-protocol.md`,
or `references/shared-conventions.md` **records a compliance-eval result in its description**
before merge — the narrowest probe that covers the change (`--probe stage-exit`,
`branch-path`, `r2-prelude`, or `loop-outcome`) with `--n 5` per model. Two ways to run it:

- Locally: `python3 eval/run-compliance-eval.py --probe <p> --n 5 --json --out eval/last.json`
  (documented in `eval/README.md` § Quick invocations; ~$14–20 per probe).
- From Actions on demand: **Actions → trigger-accuracy-eval → Run workflow**, set `probe`
  to the desired value (`none` keeps the trigger-accuracy behaviour). Uploads
  `compliance-eval-<probe>-<run>.json` as an artifact.

Compare against the recorded baseline at
[`docs/claude-5/phase-0-compliance-baseline.md`](docs/claude-5/phase-0-compliance-baseline.md).
A *rate drop* on the touched probe is the finding to explain in the PR — a maintained rate
is what the gate is looking for. A single run says nothing (the failure mode this eval
measures is intermittent), which is why the runbook always sets `--n`.

Pipeline-mechanical changes (scripts, adapters, tests, docs, workflows) are outside the
gate: they cannot move the numbers this eval measures. Frontmatter-only edits are outside
too — trigger accuracy is the `run-eval.py` weekly cron, not this one.

## Repository Conventions

### Spec-pure canon

`skills/`, `agents/`, and `references/` are the **single source of truth** for all skill and
agent definitions. These directories are spec-pure: they carry only vendor-neutral frontmatter
fields. Per-agent output is **generated** into `adapters/` by `scripts/build-adapters.py` and
**never hand-edited**. If you need to change what an adapter emits, edit the canonical source
and regenerate.

### Hand-written adapter sources

Most of what lands in `adapters/` is generated from canon prose. The exception is real code
that a target agent loads at runtime — today Pi's `AskUserQuestion` TUI extension. Those
artifacts live under `adapter-src/<agent>/` and are read by `scripts/build-adapters.py` at
build time, which prepends the `GENERATED — DO NOT EDIT` header naming the `adapter-src` path.
Edit the file under `adapter-src/`, never the emitted copy, then regenerate.

**Source layout mirrors emitted layout.** `adapter-src/pi/extensions/…` becomes
`adapters/pi/extensions/…` at the same relative path. That is a correctness requirement, not
tidiness: the Pi extension resolves its own bundle root by walking up from `import.meta.url`,
so a source tree at a different depth would typecheck and test green in-tree while resolving
the wrong root once emitted.

**Not all of it is ours.** `adapter-src/pi/extensions/ask-user-question/` is a *vendored*
snapshot of the third-party `@juicesharp/rpiv-ask-user-question` package, carried with a
four-patch delta. Read `adapter-src/pi/UPSTREAM.md` before touching anything in that tree —
reformatting or refactoring it is friction at the next upstream refresh, and every local edit
has to be re-applied by hand. Files that cannot carry a line-comment header (`LICENSE`,
`locales/*.json`) are emitted verbatim; the regen-and-diff drift guard is what protects them.

**The Pi agent output follows a third-party schema, in two places.** `adapters/pi/package.json`
carries a top-level `pi-subagents` block declaring the bundle's `agents/` directory, and each
`adapters/pi/agents/<name>.md` carries frontmatter (`tools`, `turnBudget`, `thinking`, `memory`,
`skills`, `acceptanceRole`, `completionGuard`, `inheritProjectContext`) in the shape
[`pi-subagents`](https://github.com/nicobailon/pi-subagents) 0.35.1 expects. Pi core reads none of
it; the extension does, and that schema is not ours. The manifest key is kept out of the core-Pi
`pi` block precisely so the coupling stays visible, and it is emitted unconditionally because an
unread key is inert — the bundle must never require an extension it does not ship. Unknown keys are
tolerated by that loader, so schema drift degrades rather than breaks. **Two frontmatter shapes bite
silently, so they are verified against pi-subagents' real loader, not its README** (see the mapping
notes above `PiEmitter` in `scripts/build-adapters.py`): `turnBudget` is `JSON.parse`d and must be a
single-line JSON string, and Pi's line parser drops block-sequence `tools`/`skills`, so both are
emitted comma-joined. See `docs/agents/pi.md` for the user-facing behaviour and the full mapping.

The npm installer adds a **second** coupling to the same extension: the manifest key is only read
where the bundle sits in Pi's `packages` list, which the `-a pi` install (under `skills/`) is not.
So the Pi target carries a `mirror` placement copying `agents/*.md` into the directories
`pi-subagents` scans directly — `~/.pi/agent/agents/` (user scope) and `.pi/agents/` (project
scope). Those paths are a behavioural contract, not a schema, and were confirmed read-only against
pi-subagents 0.35.1's `discoverAgents` source rather than its README. If a future version renames
those scan dirs the mirror lands in the wrong place silently, so re-confirm them on an upgrade.

Each agent directory owns its own toolchain and opts into verification by exposing a `verify`
script in its `package.json`; `scripts/validate.sh` iterates `adapter-src/*/` and runs each one.
A directory with no `verify` script is reported as a visible `SKIP` — shipping unverified code
is allowed, but never silently. Pi's `verify` is `tsc --noEmit` over the whole tree plus
`node --test`, which drives the real extension through a fake `ExtensionAPI` and a headless
TUI — registration, the questionnaire state machine, the RPC fallback, and the validation
guards — so an upstream refresh that breaks a feature-forge contract fails before it ships.
Anything here is dev-only: `adapter-src/*/node_modules/` is gitignored and nothing from it is
published.

### Docs: the site is canonical for stage detail; README is a quick tour

`docs-site/` (published to <https://garygentry.github.io/feature-forge/>) is the **canonical**
home for per-stage detail — what each stage consumes, produces, and does — and for the
`forge.config.json` reference, the dashboard/navigator, verification, epics, and troubleshooting.
`README.md` is a deliberately short quick tour (hero, agent-led setup, install, quick start, and a
stage-summary table) that **links out** to the site for detail rather than restating it. When stage
behavior changes, update the docs-site page; do not grow the README back into a second copy. The
drift guard (`docs-site/check-docs.mjs`, run by `npm run docs:check` and the `docs.yml` PR build)
protects the site's internal links and sidebar parity. Contributor/local-dev material lives in
[`CONTRIBUTING.md`](CONTRIBUTING.md), not the README.

### Tooling — Python stdlib + pinned YAML; npm confined to two dirs

The generator is Python 3 (3.10+ baseline) + Bash + Markdown. There is exactly one runtime
dependency beyond the standard library: a pinned YAML library specified in
`scripts/requirements-adapters.txt`. `bash scripts/validate.sh` auto-provisions it into the
gitignored `.venv-adapters` virtual environment on first run; subsequent runs reuse the venv.
The test suite additionally uses pytest and `jsonschema`, pinned (with the YAML pin) in
`scripts/requirements-test.txt` — test-only, never imported by runtime code, which stays
stdlib-only. `validate.sh` provisions them into the gitignored `.venv-test` (recreated from
scratch whenever the requirements or `python3` version change) and runs the suite there, with
its `bin/` on `PATH`, locally and in CI alike. A bare `python3 -m pytest tests` without them still works (the
dep-gated tests skip), but under a truthy `CI` `tests/_ci_deps.py` hard-imports them, so a
missing dep fails instead of silently skipping.
There is no `pnpm`.

Node/npm and TypeScript are confined to exactly two places, both gated by `validate.sh` and
neither part of the generator itself: `installer/` (the published CLI, built with `tsc` and
tested with `node --test`) and `adapter-src/<agent>/` (hand-written adapter sources, each
verified by its own toolchain). `bash scripts/validate.sh` remains the single verify command.

### The resolver/prelude pattern

`scripts/forge-root.sh` is the portable plugin-root resolver. It is copied **byte-identical**
into each adapter bundle (under `adapters/<agent>/scripts/forge-root.sh`) during generation.
The canonical bootstrap prelude is byte-identical everywhere it appears; the build step asserts
this with a SHA-256 comparison and fails loudly on any divergence.

### Generated-output provenance

Every file under `adapters/` that contains frontmatter carries a `GENERATED — DO NOT EDIT`
header naming its canonical source file and the command to regenerate it
(`python3 scripts/build-adapters.py`). If you see that header, do not edit the file directly —
edit the canonical source and regenerate.

## Installation

**Preferred — Claude Code marketplace / plugin install.** Installing via the Claude Code
marketplace or plugin path is the first-class, canonical install method. It gives you the
skills and agents as a managed plugin with automatic updates.

**Fallback — universal cross-agent install path.** For agents other than Claude Code, the
cross-agent installer (a separate tool, `cross-agent-installer`) copies the relevant
`adapters/<agent>/` bundle into the agent's config directory. Refer to that installer's
documentation for mechanics; this file does not duplicate them.

## Publishing to npm

The installer is published to npm as `@garygentry/feature-forge` — this is what backs
`npx @garygentry/feature-forge` and `npm i -g @garygentry/feature-forge`. Publishing goes
through **one human approval per release**, which an agent cannot give itself (ADR 0046
Amendment 4, #356). **A merge to `main` never publishes.**

- **`.github/workflows/release.yml` is the only workflow that publishes.** Its sole trigger is
  pushing a `v*` tag. npm Trusted Publishing trusts it **by filename and the `release`
  environment**, so never rename it or add a second publishing workflow. No npm token exists,
  anywhere.
- **The tag tracks the installer version:** `v<installer/package.json version>`, e.g. `v0.3.10`.
  Every tag is exactly one npm publish. The plugin version (`.claude-plugin/plugin.json`, the
  0.21.x line) stays independent; the workflow reports it in the summary and puts it in the
  GitHub Release title (`v0.3.10 (plugin 0.21.0)`). A plugin release still bumps the installer
  so that it gets a tag.
- **`verify` job** (no publish credentials) checks that the tag matches
  `installer/package.json` and runs the full Quality Gate plus the adapters-drift and
  version-sync pre-publish check. It also confirms that the version isn't on npm yet, packs the
  tarball (`prepack` builds `dist/` and bundles `adapters/`), and writes the release summary
  (version, plugin version, changelog section, `git diff --stat` since the previous tag, and a
  loud flag if `.github/` changed).
- **`publish` job** (`environment: release`) waits for the owner's approval. It then attests
  the tarball (`actions/attest-build-provenance`), runs `npm publish <tgz> --provenance` (dist-tag
  `next` for a prerelease version), and creates the GitHub Release with the changelog section
  as notes.

### Does this change impact the published build?

The npm package bundles `dist/` (built from `installer/src/`) **and** the generated `adapters/`
tree. So a change reaches `npx` users — and is **publish-worthy** — when it touches any of:

- `installer/` source, CLI behavior, `package.json`, or `prepack`/bundling;
- **canon** (`skills/`, `agents/`, `references/`) — because regenerating `adapters/` changes what
  the package ships (this is the easy one to miss: a docs-only edit to a SKILL.md still ships);
- `RAUF_PIN` / the provisioned rauf coordinate;
- anything else that lands in the npm tarball (`cd installer && npm pack --dry-run` to see it).

Pure-repo changes that **don't** ship (CI config, `scripts/` dev tooling, `AGENTS.md`/docs not
under canon, tests) are not publish-worthy on their own.

### Agent guidance — prompt after merge, then offer to run the runbook

When a **publish-worthy** change (per above) is merged to `main`, **proactively prompt the user**:
note that the change is now on `main` but not yet on npm, and ask whether they want to release.
Do **not** release unprompted and do **not** treat a merge as implying a release. Once the user
approves, **offer to run the runbook below on their behalf**. You do everything up to the gate;
the owner approves the `release` environment, in GitHub Mobile or on the web.

### Release runbook

1. **Decide the version.** Compare `installer/package.json` `version` against npm
   (`npm view @garygentry/feature-forge version`). If local is **already ahead** and unpublished
   (a prior change bumped it), reuse it — **do not double-bump**. Otherwise bump
   `installer/package.json` `version` (independent line; npm rejects republishing a version, 409).
   For a plugin release, also bump the synced plugin fields (`scripts/check-version-sync.py`).
2. **CHANGELOG.** The release notes are the top released section of `CHANGELOG.md`, and
   `release.yml`'s `verify` job fails unless `## [Unreleased]` is empty and that section names
   this release: `## [<plugin version>]` for a plugin release, `## [installer X.Y.Z]` for an
   installer-only one (e.g. a RAUF_PIN advance). Three
   standing rules, all learned from the 0.14.0 release (which bumped versions without cutting
   `[Unreleased]`, and was followed by two feature merges with no CHANGELOG entries at all — a
   process gap, not a one-off):
   - **Every feature PR adds its own CHANGELOG entry** under `## [Unreleased]`, in the PR
     itself — never deferred to "the release".
   - **Every release cuts `[Unreleased]` into a dated heading in the release commit**, leaving
     an empty `## [Unreleased]` behind: `## [X.Y.Z] — YYYY-MM-DD` for a plugin release (the same
     commit that bumps the synced version fields), `## [installer X.Y.Z] — YYYY-MM-DD` for an
     installer-only release.
   - **Keep entries short: a CHANGELOG entry is a bulleted list, under ~150 words per version.**
     A bullet names *what changed* and points at the issue/PR; the *design rationale* — the why,
     the alternatives weighed, the invariants — belongs in `roadmap/` or `references/decisions/`,
     linked from the entry, not inlined into it. (Existing long entries are grandfathered; this
     applies to new entries. See the multi-hundred-word `[Unreleased]` bullets for the anti-pattern.)
3. **Regenerate + verify** if canon changed: `python3 scripts/build-adapters.py` then
   `bash scripts/validate.sh` (green).
4. **Pre-flight the package locally** to catch build/bundle failures before spending a CI run:
   `cd installer && npm ci && npm run prepack && npm pack --dry-run`. Confirm the new version and
   that `adapters/` carries your change (`grep -rl <marker> adapters/`). **Clean up afterward:**
   `prepack` copies the repo `adapters/` tree into `installer/adapters/` (gitignored, so it never
   commits) — but if left in place it pollutes the test glob and makes `bash scripts/validate.sh`
   report **false failures** (e.g. template `smoke.test.ts` files failing with
   `Cannot find package 'vitest'`). Remove it before re-validating: `rm -rf installer/adapters`.
   CI never hits this (fresh checkout), so a failure that disappears after that `rm` is the
   leftover copy, not your change.
5. **Release-prep PR → merge.** The version bump and CHANGELOG edit go through a PR with green
   CI, never a direct push to `main`.
6. **Tag the merge commit:** `git tag v<installer version> <merge-sha> && git push origin
   v<installer version>`. This starts `release.yml`. (If the push is rejected with GH007, the
   pusher's commit email is private-protected; the owner fixes that in their git config.) If `verify` fails, fix the problem in a new
   PR and bump the version again; never move or reuse a pushed tag.
7. **Hand the gate to the owner.** Tell the user the run is waiting on the `release`
   environment and link it (`gh run list --workflow release.yml`). Point them at the `verify`
   summary to review, especially the `.github/` flag. Then wait: `gh run watch <run-id>
   --exit-status`.
8. **Verify it's live.** The registry can lag a few minutes after `publish` succeeds (E404 on
   read-back is normal at first), so poll rather than failing on the first miss:
   `until npm view @garygentry/feature-forge@<v> version; do sleep 30; done`.
   - `npm view @garygentry/feature-forge version dist-tags` shows the new version under `latest`.
   - The package page shows provenance.
   - The GitHub Release exists.
   - The `RAUF_PIN resolves` CI check is green.
   - A dev-box install (`npx @garygentry/feature-forge@<v>`) followed by `doctor` is healthy.

**Human prerequisites (one-time, operator-only):** the npm package's **Trusted Publisher** points
at this repo, workflow `release.yml`, **environment `release`**, with **"Allow npm publish"**
checked (the workflow runs `npm publish`, not `npm stage publish`; the `release` environment
approval is the human gate, per ADR 0046 A4). Its publishing access is
"Require two-factor authentication and disallow tokens". The `release` environment requires the
owner's review and only deploys `v*` tags.

### On a new rauf release — advance the pin

`installer/src/rauf.ts` `RAUF_PIN` pins the rauf coordinate a fresh install provisions as the
default loop runner. When rauf publishes a new compatible release, advance it (PR like any
change):

1. Set `RAUF_PIN` to the new `@garygentry/rauf@X.Y.Z` (update the prose pin in
   `references/forge-config-schema.json`'s `installHint` and the installer doc-comments/README
   too — `grep -rn "@garygentry/rauf@" references installer/src installer/README.md`).
2. Update the installer's tests that assert the pin (`installer/test/*.ts`).
3. Regenerate adapters (`python3 scripts/build-adapters.py`) so the schema `installHint`
   propagates; the drift guard fails otherwise.
4. Bump `installer/package.json` `version` (independent line) and add a `CHANGELOG.md` note.
5. Update `COMPATIBILITY.md` (the pin coordinate; `minRunnerVersion` only changes if rauf
   raised the agent-surface floor).

The pin is a **dependency** advance, not version coupling — rauf and feature-forge version
independently.

## Dependency Upgrades

Upgrading the pinned YAML library version in `scripts/requirements-adapters.txt` is a
**behavior change**, not a routine version bump. The YAML library controls how frontmatter
is serialized in every generated file. After changing the pin:

1. Regenerate all adapters: `python3 scripts/build-adapters.py`
2. Review the diff against the previously committed `adapters/` tree.
3. Commit the regenerated tree together with the version bump.

The drift guard (`python3 scripts/build-adapters.py --check`, wired into
`bash scripts/validate.sh`) will fail the gate if the committed `adapters/` tree does not
match a fresh generation — so a version bump without regeneration will block CI.

<!-- rauf:agents:start -->
## Autonomous Loop (Rauf)

This repository uses **rauf**, an autonomous coding loop. When you are running as a
rauf loop iteration, follow these operational rules. They are host-agnostic — they
apply whichever coding agent (Claude, Codex, Gemini, …) drives the iteration.

### Reading Your Task
1. Read `.rauf/RAUF.md` for detailed per-iteration instructions
2. Read the backlog (`.rauf/backlog.json`) — find the current `in_progress` item
3. The item's `acceptanceCriteria` define "done" for this iteration

### Working
4. Implement the changes described in the item's description
5. Follow acceptance criteria precisely — each one must pass
6. Run the verification command before considering work complete

### Completing
7. If all acceptance criteria pass: output `RAUF_DONE` as your final line
8. If blocked (missing dependency, unclear requirement): output `RAUF_BLOCKED:<reason>`
9. If human input needed (API key, design decision): output `RAUF_NEEDS_HUMAN:<reason>`
10. Do NOT commit or stage — the iteration agent never commits or stages; the loop runner owns the commit. Leave your changes in the working tree.

> Output the signal on a line by itself, as your final line — that's the safest
> habit. The runner scans backwards from the end and uses the **last** signal
> line, so trailing text after it (a commit message, a summary) does **not** break
> detection.

### Rules
- ONE item per iteration — do not work on multiple items
- Do not modify `backlog.json` — the loop runner manages status
- Do not modify `state.json` — the loop runner manages state
- Read `progress.md` for accumulated project learnings
- Append new learnings to `progress.md` if you discover important patterns

### Delegation
- If a backlog item carries `agentDelegation` and your host agent provides a
  subagent/delegation mechanism, use it to parallelize the independent subtasks;
  if it does not, complete the subtasks inline in the main session.
- You (the main agent) own the `RAUF_*` exit signal — delegated subtasks do not emit it.

### Model Selection
The runner picks the model by precedence (highest wins):
`item.model` > `--model` / options > project default > provider default.
(`rauf loop run --no-model` ignores `item.model` for one run — useful for running
a backlog whose items carry Claude-only tier aliases under a non-Claude `--agent`.)
<!-- rauf:agents:end -->
