# Compatibility

feature-forge's pipeline ends in an autonomous **loop runner** (the `rauf`
tool) that consumes a `backlog.json` conforming to a published schema. This
document tracks which feature-forge versions work with which rauf releases and
backlog `schemaVersion`.

## feature-forge ↔ rauf ↔ schemaVersion

| feature-forge | Loop runner             | Backlog `schemaVersion` | Notes                                                                 |
|---------------|-------------------------|-------------------------|-----------------------------------------------------------------------|
| 0.8.0         | `rauf` (hardcoded CLI)  | _(unversioned)_         | Structural extraction only. Invokes `rauf` exactly as 0.7.0 did. No `loopRunner` config block yet; no `rauf backlog validate` dependency. |

### Planned

A later feature-forge release introduces a config-driven `loopRunner` block
(`forge.config.json`) and delegates backlog validation to the runner's
`validate` verb, conforming to rauf's `SPEC-BACKLOG-TOOL-CONTRACT.md`. When
that lands, this matrix gains a `min rauf version` column pinned to the rauf
release that first ships `rauf backlog validate` + backlog `schemaVersion`.

> rauf is the **default and reference** loop runner. The contract is designed
> so an alternative ralph-style runner can be supplied via `loopRunner`
> without editing the pipeline skills.
