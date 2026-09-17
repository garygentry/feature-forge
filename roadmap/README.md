# roadmap/

Durable, version-controlled design proposals and multi-phase plans for feature-forge.

## What belongs here

Plans that need to outlive a session and be referenced from GitHub issues: multi-phase
programs, architecture proposals, and hardening designs whose rationale matters months later.

Each document should be **standalone** — readable by a fresh session with no prior context,
stating the constraints it was written against and the date those were measured.

## What does not belong here

| Not this | Put it here instead |
|---|---|
| Session scratch, handoffs, working notes | `plans/` (gitignored, local-only) |
| Shipped-architecture documentation | `docs/architecture/` (pipeline `forge-6-docs` output) |
| Contributor conventions | `AGENTS.md` |
| Living project status | `STATUS.md` |
| Skill/agent behavior contracts | `references/` (canonical, spec-pure) |

## Not published to the docs site

The docs site is **allow-list driven**: only pages listed in `docs-site/docs.manifest.json`
are symlinked into the Starlight content collection. `roadmap/` is deliberately absent from
that manifest, is not under `docs/` (so it does not trigger the `docs.yml` deploy or the
lychee link scan), and is therefore never rendered at
<https://garygentry.github.io/feature-forge/>.

Keep it that way. These are internal engineering plans, not user documentation — if a plan's
content becomes user-facing, write a real docs page for it rather than adding `roadmap/` to
the manifest.

## Not a canonical surface

`roadmap/` is not scanned by `scripts/check-spec-purity.py` (which covers `skills/`, `agents/`,
`references/`) and is not consumed by `scripts/build-adapters.py`. Nothing here ships in an
adapter bundle. Markdown here is linted only by the advisory, non-blocking `markdownlint` job.

## Status convention

Every document opens with a status line so a reader knows what they are looking at:

- **proposal** — written, not approved; nothing implemented
- **accepted** — approved, tracked by a GitHub issue (link it)
- **in progress** — partially landed; the document records which phases shipped
- **superseded by `<file>`** — kept for provenance, do not act on
- **shipped** — fully landed; consider moving the durable parts into `docs/architecture/`

## Index

| Document | Status | Tracking |
|---|---|---|
| [`self-healing-resilience.md`](self-healing-resilience.md) — pipeline self-healing for environment/config faults across Claude, Codex, and Pi | proposal | [#244](https://github.com/garygentry/feature-forge/issues/244) |
| [`unattended-decision-authority.md`](unattended-decision-authority.md) — unattended pipeline runs: a config-declared decision-authority axis, front-loaded operator brief, and an adversary agent that keeps the driver honest | proposal | none yet |
