# Decision: single-writer state model — detection welcome, locking out of scope

**Decided:** 2026-08-08 · **Issue:** [#180](https://github.com/garygentry/feature-forge/issues/180) · **Owner:** repository owner

## The decision

Concurrent multi-session mutation of forge state is **out of scope**. Every forge state
writer — `forge-session.py` (`.pipeline-state.json`) and `epic-manifest.py`
(`epic-manifest.json`, `.epic-state.json`) — assumes a **single writer**. Atomicity
(sibling temp file → flush/fsync → `os.replace`) protects against an *interrupted* write;
it is not, and is not intended to be, mutual exclusion between simultaneous writers.

The standing posture is **detection, not locking**:

- **No locking mechanism will be added on the authority of a verification finding or a
  single feature's spec.** If concurrent multi-session use ever becomes a supported
  workflow, that is a product decision needing its own PRD — and a state lock alone would
  be false comfort, because git operations, the two-commit provenance protocol, and
  adapter regeneration are equally unsynchronized.
- **Cheap, opportunistic detection is welcome if someone proposes it** — e.g. an
  epic-root writer re-reading and failing loudly on an unexpected `revision` before
  `os.replace`. It is an explicitly optional hardening, not a requirement, and nothing is
  scheduled.

## Accepted residual risk

Everything in-session is sequential, and member `.pipeline-state.json` files are
disjoint. The one real exposure: two sessions working **different members of one epic**
share two epic-root files, `epic-manifest.json` and `.epic-state.json`. A lost
read-modify-write increment of the manifest's `revision` can leave it unchanged after a
semantic mutation landed, and the freshness comparison then classifies a **stale epic
verification as `fresh`** — a correctness consequence, not just a lost edit.

This is **accepted and documented**, not mitigated. Anyone who hits it has this document
to cite; do not run two concurrent sessions against members of the same epic.

## What this means for verification (CHECK-S27)

When `CHECK-S27` ("Concurrent access scenarios are addressed if relevant") fires against
forge state writes, the answer is a **citation, not a design**: cite this document (or
the per-feature requirement restating it, e.g. `stage-exit-coverage` `REQ-REL-04`,
`epic-orchestration` `REQ-ROBUST-03`). A PRD silent on concurrency gets a one-sentence
position recorded; a verifier must never answer the silence by specifying a mechanism.

## Provenance

Both precedents ran the same check; the only variable was whether the PRD had a position:

- `stage-exit-coverage` V-006 raised CHECK-S27 against a silent PRD, was filed as a
  `gap`, and induced a ~140-line portable lock protocol answering no requirement. It was
  removed (`302c93f`), and the PRD now records the position as `REQ-REL-04`.
- `epic-orchestration` V-008 raised the same check against a PRD that had scoped
  concurrency out (`REQ-ROBUST-03`), was filed as an `improvement`, and cost one sentence.
