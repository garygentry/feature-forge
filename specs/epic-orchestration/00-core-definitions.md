# 00 — Core Definitions

> Shared data contracts for Epic Orchestration. Every other spec document in this suite
> references the types, schemas, and constants defined here. Where a contract is a JSON
> document on disk, the canonical definition is its JSON Schema; where it is a Python
> value passed between functions inside `scripts/epic-manifest.py`, the canonical
> definition is the typed structure (`TypedDict` / `dataclass`) shown here.
>
> Stack: **prose plugin + Python 3 helpers** (stdlib only). Python code in this suite
> targets Python 3.10+ and follows `references/stacks/python.md` conventions
> (Google-style docstrings, `X | Y` unions, complete type annotations, `__all__` not
> required for a single-file CLI script).

## Requirement Coverage

| REQ ID | Requirement | Section |
|--------|-------------|---------|
| REQ-EPIC-02 | Machine-readable manifest fields | 1, 2 |
| REQ-EPIC-03 | Structured `exposes`/`consumes` contract | 1, 2 |
| REQ-EPIC-04 | Per-feature charter only (no full PRD at creation) | 1, 2 |
| REQ-EPIC-05 | Acyclic dependency graph | 4 (Finding taxonomy), 6 |
| REQ-DIR-04 | Globally unique feature names | 4, 6 |
| REQ-STATE-01 | Manifest canonical; per-feature `epic` back-pointer | 3 |
| REQ-STATE-02 | No cached per-feature status | 1 (no `status` field), 5 |
| REQ-ORCH-01 | Completion rule for orchestration | 7 |
| REQ-ORCH-03 | Actionable / parallel-eligible derived sets | 5, 8 |
| REQ-ORCH-05 | Epic lifecycle states | 2 (`status` enum) |
| REQ-ROBUST-02 | Corrupt manifest → actionable findings | 4 |
| REQ-SEC-01 | Trust model: safe handling of corrupt/hand-edited input | 4 (Trust model) |
| REQ-SEC-02 | Path/name containment | 4 (Finding taxonomy), 6 |
| REQ-OBS-01 | `updatedAt` timestamp on every mutation | 2 |

---

## 1. Domain Overview

An **epic** is a named grouping of related forge features with declared dependencies, a
single machine-readable **manifest** (`epic-manifest.json`), and a human-readable
**narrative** (`EPIC.md`). The manifest is the single source of truth for membership,
dependency edges, per-feature charters, and structured contracts. Per-feature *status* is
**never** stored in the manifest — it is derived live from each member feature's own
`.pipeline-state.json` (REQ-STATE-02).

Three on-disk contracts and three in-process value contracts are defined here:

| Contract | Kind | Canonical definition | Section |
|----------|------|----------------------|---------|
| `epic-manifest.json` | on-disk JSON | `references/epic-manifest-schema.json` | 2 |
| `.pipeline-state.json` `epic` back-pointer | on-disk JSON (additive) | `references/pipeline-state-schema.json` | 3 |
| `render-status` output | CLI JSON (stdout) | this doc | 5 |
| `Finding` | in-process + CLI JSON | this doc | 4 |
| `FeatureStatus` (derived) | in-process | this doc | 7 |
| Derived sets (`actionable`, `parallelEligible`) | in-process + CLI JSON | this doc | 8 |

---

## 2. `epic-manifest.json` — Manifest Schema (REQ-EPIC-02/03/04, REQ-ORCH-05, REQ-OBS-01)

The manifest lives at `{specsDir}/{epic}/epic-manifest.json`. It is the canonical record
of membership, dependency edges, charters, and contracts. It carries **no** per-feature
`status` field (REQ-STATE-02).

### 2.1 Field reference

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `schemaVersion` | integer (const `1`) | yes | Schema evolution guard. |
| `epic` | string (kebab-case) | yes | Matches the epic subtree directory name. Globally unique. |
| `description` | string | yes | One-paragraph epic summary. |
| `status` | enum | yes | `active` \| `paused` \| `abandoned` \| `complete` (REQ-ORCH-05). |
| `narrativeDoc` | string (const `EPIC.md`) | yes | Relative pointer to the narrative (REQ-EPIC-03). |
| `createdAt` | string (ISO-8601 date-time) | yes | Set once at creation. |
| `updatedAt` | string (ISO-8601 date-time) | yes | Bumped by **every** mutator on each atomic write (REQ-OBS-01). |
| `features` | array of `Feature` | yes | Ordered. Order is the user-declared sequence; it is **not** a dependency ordering. |

### 2.2 `Feature` object

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `name` | string (kebab-case) | yes | Globally unique across the whole specs tree (REQ-DIR-04). |
| `charter` | string | yes | One-paragraph scope statement + contract obligations (REQ-EPIC-04). No full PRD at creation. |
| `dependsOn` | array of string | yes (may be empty) | Names of sibling features in this epic (REQ-EPIC-02). Every entry must be a `name` in `features[]`. |
| `exposes` | array of `Contract` | yes (may be empty) | What this feature provides to dependents (REQ-EPIC-03). |
| `consumes` | array of `ConsumedContract` | yes (may be empty) | What this feature relies on from its dependencies (REQ-EPIC-03). |

> **No `status` field on `Feature`.** A schema validator MUST reject a manifest that
> includes a per-feature `status` key, to prevent reintroducing cached status
> (REQ-STATE-02). See §5 for how status is derived instead.

### 2.3 `Contract` object (an `exposes[]` entry)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `name` | string | yes | Identifier of the exposed artifact (e.g. `verifyJwt`, `JWT_SECRET`). |
| `kind` | enum | yes | `function` \| `type` \| `endpoint` \| `module` \| `event`. |
| `summary` | string | yes | One-line human description. |

### 2.4 `ConsumedContract` object (a `consumes[]` entry)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `from` | string | yes | Name of the sibling feature providing this. Must be present in `features[]`. |
| `name` | string | yes | Identifier being consumed; should match an `exposes[].name` of the `from` feature (drift check CHECK-E06 verifies this for completed features). |
| `summary` | string | yes | One-line human description. |

### 2.5 Canonical example

```jsonc
{
  "schemaVersion": 1,
  "epic": "auth-overhaul",
  "description": "Replace the legacy session system with a JWT-based auth stack.",
  "status": "active",
  "narrativeDoc": "EPIC.md",
  "createdAt": "2026-06-12T00:00:00Z",
  "updatedAt": "2026-06-12T00:00:00Z",
  "features": [
    {
      "name": "config-store",
      "charter": "Central typed config store exposing secrets and feature flags to the rest of the epic. Must expose JWT_SECRET before token-service can build.",
      "dependsOn": [],
      "exposes": [
        { "name": "JWT_SECRET", "kind": "type", "summary": "Signing secret accessor" }
      ],
      "consumes": []
    },
    {
      "name": "token-service",
      "charter": "Issue and verify JWTs. Consumes JWT_SECRET from config-store; exposes verifyJwt to downstream API features.",
      "dependsOn": ["config-store"],
      "exposes": [
        { "name": "verifyJwt", "kind": "function", "summary": "Validate a JWT, return claims or raise" }
      ],
      "consumes": [
        { "from": "config-store", "name": "JWT_SECRET", "summary": "Signing secret for verification" }
      ]
    }
  ]
}
```

### 2.6 Invariants enforced by `validate` (see 02-manifest-helper-cli.md §`validate`)

1. JSON parses (else `corrupt-json` finding, REQ-ROBUST-02).
2. Conforms to `references/epic-manifest-schema.json` (else `schema` findings).
3. `epic` and every `features[].name` are unique within the manifest and safe (no path
   separator / `..` / absolute path — REQ-SEC-02).
4. Every `dependsOn[]` entry and every `consumes[].from` references a `name` present in
   `features[]` (else `dangling-ref` finding, REQ-ROBUST-02).
5. The `dependsOn` graph is acyclic (else `cycle` finding, REQ-EPIC-05). A feature's
   `dependsOn[]` MUST NOT contain its own `name` (self-dependency): a self-edge is a
   degenerate cycle and is reported as a `cycle` finding with message `cycle: X → X`
   (the same code/exit path as any other cycle — see 02 §4, §6.2).
6. No `Feature` carries a `status` key (REQ-STATE-02).

---

## 3. Pipeline-State Additions (REQ-STATE-01)

The per-feature `.pipeline-state.json` schema (`references/pipeline-state-schema.json`)
gains additive, optional fields. **No migration is required** for existing flat features
(REQ-COMPAT-02) — absence of these fields means "standalone feature".

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `epic` | string \| absent | no | Back-pointer to the owning epic's name. Absent for standalone features. |

The `currentStage` enum and the `stages` object keys each gain two new members:
`forge-0-epic` and `forge-verify-epic`.

**Conflict rule (REQ-STATE-01):** if a feature's `epic` back-pointer names an epic whose
manifest does not list that feature (or vice versa), **the manifest wins**. The
inconsistency is reported by `forge-verify` epic mode (CHECK-E07), not silently repaired
at read time.

> The exact JSON-Schema edits to `pipeline-state-schema.json` are specified in
> 04-pipeline-integration.md §2. This section defines the *contract*; that section
> defines the *schema patch*.

---

## 4. Finding Taxonomy (REQ-ROBUST-02, REQ-SEC-02, REQ-EPIC-05, REQ-DIR-04)

**Trust model (REQ-SEC-01).** All epic artifacts (manifest, `EPIC.md`, charters) are
trusted, local, developer-authored files — there is no untrusted or network input. The
security concern is therefore the *safe handling of corrupt or hand-edited input*, not
adversarial defense. The `Finding` taxonomy below is the embodiment of that requirement:
every malformed, corrupt, or unsafe input produces a specific, actionable `Finding` and a
non-zero exit code rather than a crash or undefined behavior (cf. REQ-ROBUST-02,
REQ-SEC-02).

Every validation/resolution failure is reported as a structured `Finding`. Findings are
emitted in the `findings[]` array of `validate` / `render-status` JSON output and printed
as human lines in non-JSON mode. Skills surface findings **verbatim** and stop on exit
code ≥ 1 for any gating operation.

### 4.1 `Finding` shape

```python
from typing import TypedDict, Literal

FindingCode = Literal[
    "corrupt-json",     # manifest is not parseable JSON (REQ-ROBUST-02)
    "schema",           # manifest violates epic-manifest-schema.json
    "duplicate-name",   # a feature/epic name occurs more than once in the tree (REQ-DIR-04)
    "dangling-ref",     # dependsOn / consumes.from references an unknown feature (REQ-ROBUST-02)
    "cycle",            # the dependsOn graph contains a cycle (REQ-EPIC-05)
    "unsafe-name",      # a name contains a path separator, "..", or is absolute (REQ-SEC-02)
    "not-found",        # a name resolves to zero feature-shaped directories
    "ambiguous",        # a name resolves to more than one feature-shaped directory (REQ-DIR-04)
    "cached-status",    # a Feature object illegally carries a status field (REQ-STATE-02)
]


class Finding(TypedDict):
    """A single, actionable validation or resolution failure.

    Attributes:
        code: Machine-readable category (see FindingCode).
        message: Human-readable, actionable description. Includes offending
            identifiers and, where relevant, the conflicting paths.
        feature: The feature name the finding pertains to, or None for
            manifest- or epic-level findings.
    """
    code: FindingCode
    message: str
    feature: str | None
```

### 4.2 Message conventions

Messages are concrete and actionable. Canonical examples (exact strings are illustrative;
the *shape* is normative):

| Code | Example message |
|------|-----------------|
| `cycle` | `cycle: token-service → api-gateway → token-service` |
| `duplicate-name` | `duplicate feature name 'token-service' (also at specs/other-epic/token-service)` |
| `dangling-ref` | `unknown dependsOn 'config-stor' in feature 'token-service'` |
| `unsafe-name` | `unsafe name '../escape'` |
| `not-found` | `no feature named 'tokn-service' found under specs/` |
| `ambiguous` | `ambiguous name 'token-service': matches specs/token-service and specs/auth-overhaul/token-service` |
| `cached-status` | `feature 'token-service' has an illegal 'status' field; status is derived, not stored` |

---

## 5. Derived Per-Feature Status (REQ-STATE-02)

Because the manifest stores no status, the helper derives a `FeatureStatus` for each
member by reading that feature's own `.pipeline-state.json` at request time.

```python
from typing import TypedDict, Literal

DerivedStatus = Literal[
    "not-started",   # no .pipeline-state.json, or all stages pending
    "in-progress",   # at least one stage started, loop not complete-for-orchestration
    "complete",      # complete-for-orchestration per §7
]


class FeatureStatus(TypedDict):
    """Live per-feature status derived from its own pipeline state.

    Attributes:
        name: Feature name.
        stage: The feature's current pipeline stage (its currentStage), or
            "forge-0-epic" if the member directory exists but no stage has run.
        status: Coarse derived status (see DerivedStatus). Reuses existing
            navigator status semantics for display.
        blocked: True if any entry in unmetDeps is non-empty.
        unmetDeps: Names of this feature's direct dependencies that are not yet
            complete-for-orchestration (§7). Empty when actionable or complete.
    """
    name: str
    stage: str
    status: DerivedStatus
    blocked: bool
    unmetDeps: list[str]
```

The `stage`/`status` strings reuse the existing navigator status indicators so the
dashboard renders consistently with standalone features (REQ-VIS-01). The richer per-stage
detail (e.g. `forge-3-specs: in-progress`) comes straight from the feature's
`.pipeline-state.json` and is not re-modeled here.

---

## 6. Name & Path Safety Constants (REQ-SEC-02, REQ-DIR-04)

```python
import re
from typing import Final

#: A safe feature/epic name: one kebab-case token. No path separators, no dots.
SAFE_NAME_RE: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

#: A directory is "feature-shaped" iff it directly contains this file.
PIPELINE_STATE_FILENAME: Final = ".pipeline-state.json"

#: Canonical filenames sited at the epic subtree root.
MANIFEST_FILENAME: Final = "epic-manifest.json"
NARRATIVE_FILENAME: Final = "EPIC.md"
```

A name is **rejected** (`unsafe-name`) if it fails `SAFE_NAME_RE`, contains `/` or `\`,
equals `..`, or is an absolute path. A resolved path is also **rejected** if its real
(symlink-resolved) form is not contained within the real form of `{specsDir}`; this
containment violation surfaces only as an **exit-2 `UsageError`** (`resolved path escapes
specs dir: …`), not a Finding code. These checks run *before* any filesystem access
(02-manifest-helper-cli.md §6).

A directory is treated as a **feature** for resolution, uniqueness, and globbing **only**
if it directly contains a `.pipeline-state.json`. Non-feature subtrees (`.verification/`,
`tests/`, fixture dirs) are therefore never matched as features (tech-spec §3.4).

---

## 7. Completion Rule for Orchestration (REQ-ORCH-01)

A feature is **complete-for-orchestration** — the single predicate that unblocks
dependents and drives the handoff — when:

```
stages.forge-5-loop.status == "complete"
  AND (forge-verify-impl is absent
       OR stages["forge-verify-impl"].status ∈ {"passed", "findings-applied"})
```

A feature whose `forge-verify-impl.status` is `findings-reported` (unfixed) is **not**
complete and does **not** unblock dependents. Merge/PR status is not tracked in v1
(PRD Out of Scope). This predicate is implemented **once** in `render-status`
(02-manifest-helper-cli.md §8.1 (predicate) / §6.4 (`render-status` subcommand)) and
reused by the dependency gate and the handoff (04-pipeline-integration.md §6).

---

## 8. Derived Sets (REQ-ORCH-03)

Computed by `render-status` over the dependency graph + each feature's §7 completion:

- **`actionable`** — every feature whose direct `dependsOn` are all
  complete-for-orchestration (§7) **and** that is not itself complete.
- **`parallelEligible`** — the subset of `actionable` features that do **not**
  (transitively) depend on one another. Surfaced for *future* parallel execution; v1
  execution is serial (REQ-ORCH-03). There is **no** `parallelGroup` field in the
  manifest — the graph already expresses eligibility.

The full `render-status` output object that carries these sets is defined in
02-manifest-helper-cli.md §8.4 (it is the helper's public output contract; reproduced
there so the CLI doc is self-contained).

---

## 9. Exit-Code Contract

All `epic-manifest.py` subcommands follow the rauf/`validate-traceability.py` convention:

| Exit | Meaning |
|------|---------|
| `0` | ok / valid / unique / resolved |
| `1` | findings / validation failure / duplicate / ambiguous / not-found |
| `2` | usage error or I/O error (missing file, unreadable, unsafe path before FS access) |

Skills treat exit ≥ 1 as a stop condition for gating operations and surface the emitted
findings verbatim.

---

## Dependencies

None — this is the foundation document. All other documents in this suite depend on it.

## Verification

- [ ] `references/epic-manifest-schema.json` exists and a manifest with a per-feature
      `status` field fails validation against it (REQ-STATE-02).
- [ ] The canonical example in §2.5 validates clean.
- [ ] Every `FindingCode` value in §4.1 is producible by at least one helper subcommand
      (cross-checked against 02-manifest-helper-cli.md and the pytest suite in
      05-testing-strategy.md).
- [ ] The completion predicate in §7 matches the implementation in `render-status` and
      the dependency gate in 04-pipeline-integration.md.
