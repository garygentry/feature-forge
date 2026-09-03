<!--
  Fill this in. The three checkboxes and one required line below are what
  reviewers look for first. See `CONTRIBUTING.md` and `AGENTS.md` for the
  scoping rules referenced here.
-->

## Summary

<!-- One or two sentences on what changes and why. -->

## Type of change

<!-- Reviewers rely on this partition. See CONTRIBUTING.md § Scoping rules. -->

- [ ] This PR changes **either** the generator (`scripts/build-adapters.py`, `adapter-src/`) **or** canon (`skills/`, `agents/`, `references/`) — **not both**.
- [ ] If canon **prose** changed (a `skills/*/SKILL.md` body or `references/stage-exit-protocol.md` / `shared-conventions.md`), it is confined to **one** skill family, and the compliance-eval result for the narrowest covering probe is pasted in the description below (`AGENTS.md` § Prose-change gate).
- [ ] `bash scripts/validate.sh` is green locally.

## Drift diff-stat (required)

<!--
  Adapters are generated from canon by `scripts/build-adapters.py`. A canon edit
  legitimately touches ~900 generated files; an emitter edit that touches ~900 files
  is the case to read carefully.

  Paste one of these, whichever is quickest:
    python3 scripts/build-adapters.py --check   # exits 0 if adapters/ is in sync
    git diff --stat -- adapters/ | tail -1      # after `python3 scripts/build-adapters.py`
-->

```
<paste the last line here>
```

## Notes for reviewers

<!--
  Anything that would not be obvious from the diff:
    - Deviations from an issue's stated scope, with the reason.
    - A compliance-eval JSON summary if this PR touches canon prose.
    - Cross-links to related PRs or issues (e.g. "gated by #266").
-->
