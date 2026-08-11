# 01 — Architecture & Layout

> Where every change in `verify-fix-sweep` lands, which document owns it, what depends
> on what, and how the one new script is distributed to non-Claude adapter bundles.
> This feature adds **no package, no module import surface, no config key, and no
> schema change** — its "architecture" is one standalone CLI script plus coordinated
> prose edits across two skills, three checklists, and six test files.
>
> Shared vocabulary: `00-core-definitions.md`. Locate symbols and prose anchors by
> name, never line number.

## Requirement Coverage

| REQ ID | Requirement | Section |
|---|---|---|
| REQ-SWEEP-01..07 | Sweep tool + fix-pass integration exist and are wired | §1, §2 (inventory rows 1–3), §3 |
| REQ-CARD-01 | plan-coverage subcommand ships in the same script | §1, §2 row 1 |
| REQ-CARD-02/03, REQ-CONS-01 | CHECKs land in checklist files + SKILL totals | §2 rows 4–8, §4 |
| REQ-PERF-01 | Single-process stdlib script, no services | §1 |
| REQ-CONC-01 | No new writers; script is read-only | §1 |
| (C-3) | stdlib-only, ships in `scripts/` | §1, §5 |
| (C-4) | Line/word budgets respected per file | §4.1 |
| (C-5) | Adapter regen + host-neutral prose | §5 |
| (C-6) | No outcome/schema/config additions | §1 |

## 1. Shape of the Feature

Three workstreams, all deterministic and model-free (C-2):

1. **The script** — `scripts/fix-sweep.py`, stdlib-only, two subcommands (`sweep`,
   `plan-coverage`), standalone-script exit convention `0/1/2`. It is **not** a
   `forge-session.py` verb (tech-spec §3.1: exit-convention mismatch, mega-file
   growth) and deliberately does not import from `forge-session.py` — it carries its
   own ~10-line bounded-subprocess git helper following the same conventions
   (tech-spec §6.8).
2. **forge-fix integration** — prose additions to Steps 2, 4, and 5 of
   `skills/forge-fix/SKILL.md`. **No step renumbering**: existing Steps 1–7 keep
   their numbers, so internal cross-references and
   `references/stage-exit-protocol.md`'s "forge-fix SKILL.md Step 6" citation stay
   valid.
3. **Verification CHECKs** — four checklist entries (CHECK-B29/I24/I25/S39) in the
   uncapped checklist reference files, zero-net-new-line numeric/ownership edits to
   `skills/forge-verify/SKILL.md`, and six pinned tests updated in lockstep.

## 2. File Inventory (authoritative)

| # | Path | Kind | Owning document |
|---|---|---|---|
| 1 | `scripts/fix-sweep.py` | **NEW** — stdlib-only CLI, 2 subcommands | `02-fix-sweep-script.md` |
| 2 | `tests/test_fix_sweep.py` | **NEW** — behavior + prose guards | `05-testing-strategy.md` |
| 3 | `skills/forge-fix/SKILL.md` | EDIT — Step 2 + Step 4 + Step 5 additions | `03-forge-fix-integration.md` |
| 4 | `skills/forge-verify/SKILL.md` | EDIT — totals + dimension-group tags (anchors §4.1) | `04-verification-checks.md` |
| 5 | `skills/forge-verify/references/verification-checklists/backlog.md` | EDIT — +CHECK-B29 | `04-verification-checks.md` |
| 6 | `skills/forge-verify/references/verification-checklists/impl.md` | EDIT — +CHECK-I24, +CHECK-I25 | `04-verification-checks.md` |
| 7 | `skills/forge-verify/references/verification-checklists/specs.md` | EDIT — +CHECK-S39 | `04-verification-checks.md` |
| 8 | `scripts/build-adapters.py` | EDIT — +`"fix-sweep.py"` in `RUNTIME_HELPERS` | this document, §5 |
| 9 | `tests/test_build_adapters.py` | EDIT — `RUNTIME_HELPERS` length pin 6 → 7 | `05-testing-strategy.md` |
| 10 | `tests/test_dev_runtime_smoke.py` | EDIT — pinned `"impl: 23 checks"` / `"impl 23"` → 25 | `05-testing-strategy.md` |
| 11 | `tests/test_smoke_command.py` | EDIT — same impl pins → 25 | `05-testing-strategy.md` |
| 12 | `tests/test_lifecycle_artifact_check.py` | EDIT — `"backlog: 28 checks"` / `"backlog 28"` → 29 | `05-testing-strategy.md` |
| 13 | `tests/test_verification_checklists_split.py` | EDIT — `EXPECTED` table + 131 → 135 | `05-testing-strategy.md` |
| 14 | `CHANGELOG.md` | EDIT — `[Unreleased]` entry (publish rule, §5) | this document, §5 |
| 15 | `adapters/**` | REGEN — via `build-adapters.py` (C-5), incl. `adapters/*/scripts/fix-sweep.py` | this document, §5 |

Anything not in this table is **out of bounds** for the implementation — in
particular `references/stage-exit-protocol.md` (C-1: R-06 untouched),
`skills/forge-verify/references/findings-template.md` (read-only parse contract),
`scripts/forge-session.py`, `forge.config.json` schema, and
`references/pipeline-state-schema.json` (C-6).

## 3. Dependency Graph (implementation order)

```
scripts/fix-sweep.py  (row 1)          ← no dependencies; build first
    │
    ├─→ tests/test_fix_sweep.py behavior tests (row 2)
    │
    ├─→ skills/forge-fix/SKILL.md integration (row 3)
    │       └─→ prose guards in test_fix_sweep.py (row 2)
    │
    └─→ scripts/build-adapters.py RUNTIME_HELPERS (row 8)
            └─→ tests/test_build_adapters.py pin 6→7 (row 9)
                    └─→ adapters/** regen (row 15)

checklist files (rows 5–7)  ← independent of the script; can build in parallel
    └─→ skills/forge-verify/SKILL.md totals+tags (row 4)
            └─→ pinned tests (rows 10–13)
                    └─→ adapters/** regen (row 15, same single regen)

CHANGELOG.md (row 14)  ← last, summarizes the change
```

Two independent chains join only at the single `adapters/**` regeneration — run
`build-adapters.py` **once, after all canon edits land**, so the drift gate
(`validate.sh` step 6b) sees one consistent regeneration.

## 4. Edit Anchors in Capped Files (C-4)

### 4.1 `skills/forge-verify/SKILL.md` — at the 298/300 body-line cap

Three edit sites, all **in place with zero net new lines** (2 lines of headroom
remain untouched). Anchors are quoted text, not line numbers:

1. **Dispatch-size line** (the "Large modes" bullet): `"Large modes (specs 38,
   backlog 28, impl 23): parallel dimensioned fan-out."` → `specs 39, backlog 29,
   impl 25`.
2. **Dimension-group bullets** (the three mode lists under it) — append ownership
   tags so each new CHECK has an owning fan-out dimension (a cluster owned by no
   group is silently never executed):
   - backlog *(3) spec coverage & traceability* group → append `(owns CHECK-B29)`
   - impl *(1) requirement coverage vs specs* group → append `(owns CHECK-I24/I25)`
   - specs *(3) cross-reference & traceability* group → append `(owns CHECK-S39)`
   The impl *(5) runnability* group already carries `(owns CHECK-I21/I22 …)` — the
   established tag format to match.
3. **Per-mode expected totals** (Step 3 paragraph): `"(prd: 15 checks, tech: 17
   checks, specs: 38 checks, backlog: 28 checks, impl: 23 checks, epic: 10
   checks)"` → `specs: 39 / backlog: 29 / impl: 25`.

Exact replacement strings: `04-verification-checks.md` §4.

### 4.2 `skills/forge-fix/SKILL.md` — 134/300 body lines

Additions of ~25–35 lines (including one fenced invocation block with the standard
plugin-root prelude) land inside existing Steps 2, 4, and 5 — comfortably under the
cap. `scripts/check-spec-purity.py` measures the body (fenced code counts); CI's
Quality Gate runs it, plain pytest does not — check locally. Exact prose:
`03-forge-fix-integration.md`.

### 4.3 Checklist files — uncapped

`backlog.md`, `impl.md`, `specs.md` under
`skills/forge-verify/references/verification-checklists/` are `references/`-tier and
uncapped; explanatory prose belongs there, not in SKILL bodies.

## 5. Distribution & Build

### 5.1 `RUNTIME_HELPERS` (row 8)

A `scripts/*.py` invoked from skill prose as `$R/scripts/<x>.py` must be in
`build-adapters.py`'s `RUNTIME_HELPERS` tuple or it is absent from every non-Claude
adapter bundle — and the forge-fix sweep invocation would fail there. Precedent:
`validate-traceability.py` is listed (skill-invoked); dev-only `check-spec-purity.py`
is not. The edit:

```python
RUNTIME_HELPERS: tuple[str, ...] = (
    "forge-root.sh",
    "forge-init.sh",
    "epic-manifest.py",
    "forge-session.py",
    "validate-traceability.py",
    "forge-bootstrap.py",
    "fix-sweep.py",          # NEW — invoked by forge-fix Steps 2 and 4
)
```

`tests/test_build_adapters.py` hard-pins `len(mod.RUNTIME_HELPERS) == 6` (→ 7) and
asserts each bundle's `scripts/` holds **exactly** `RUNTIME_HELPERS`, so the
regenerated `adapters/*/scripts/fix-sweep.py` copies are test-enforced.

### 5.2 Adapter regeneration (row 15, C-5)

Canon edits (skills, checklists) regenerate `adapters/` via
`python3 scripts/build-adapters.py`, run **once after all canon edits** (§3).
Constraints the regeneration imposes on authored prose:

- **Host-neutrality:** the checklist files carry zero host terms and are **not**
  translation-exempt — new CHECK prose must be written host-neutral from the start
  (`tests/test_adapter_host_neutrality.py` enforces). Reference prose that
  *mentions* (rather than uses) a host term garbles under the #167 translation pass
  — reword or exempt; for this feature, reword.
- forge-fix SKILL.md prose **is** host-translated per adapter; the fenced invocation
  block uses the standard plugin-root prelude, which the translation pass already
  handles for every other skill.

### 5.3 Publish worthiness & CHANGELOG (row 14)

This change is **publish-worthy** per AGENTS.md: a canon edit regenerates `adapters/`
and changes what the npm package ships. The `[Unreleased]` CHANGELOG entry lands in
the same PR (standing rule). The version bump/publish itself is owner-gated and out
of scope.

### 5.4 Validation gate (every workstream)

```
bash scripts/validate.sh          # full suite incl. adapter drift check (step 6b)
ruff check scripts/ eval/         # CI-only gate — run locally, pytest won't catch it
```

Both green, adapters regenerated with no drift, is the definition of done for every
document in this suite (PRD Success Criteria).

## 6. Dependencies

- `00-core-definitions.md` — every contract referenced here.

## 7. Verification

- [ ] `git status` after implementation shows changes to exactly the 15 inventory
      rows (plus regenerated `adapters/**`).
- [ ] `references/stage-exit-protocol.md`, `findings-template.md`,
      `forge-session.py`, and both schemas are untouched (C-1/C-6).
- [ ] `grep -c "fix-sweep.py" scripts/build-adapters.py` ≥ 1; every
      `adapters/*/scripts/` contains `fix-sweep.py` after regen.
- [ ] `python3 scripts/check-spec-purity.py` passes: forge-verify body ≤ 300 lines
      (unchanged at 298), forge-fix body ≤ 300 lines.
- [ ] `bash scripts/validate.sh` + `ruff check scripts/ eval/` green.
