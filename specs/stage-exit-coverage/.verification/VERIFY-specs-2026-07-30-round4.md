# Verification Report: stage-exit-coverage (specs) — Round 4

Date: 2026-07-30
Pipeline Stage: forge-3-specs (re-verify after `f8f01c9` — `scripts/forge_json.py` dropped, loader mirrored)
Mode: specs, require-clean

## Summary

- Checks executed: 38 of 38 — 26 pass, 12 fail, 0 not-applicable
- Total findings: **14** — 1 gap, 3 inconsistencies, 5 improvements, 5 errors
- All 5 round-3 findings remain resolved

**Headline:** the `forge_json` excision was clean at the **name** level — one grep-verifiable mention
survives repo-wide, and it is the intended rationale sentence in `01` §3.4 — but **not at the
semantic level**. The specs still instructed an implementer to add a sibling import (twice, above two
now-*empty* `python` fences), still said `_load_config` "import[s] this helper", still specified
runtime `ModuleNotFoundError` handling for a module that no longer exists, and still asserted a "new
runtime helper" ships to every adapter. `07` was updated correctly; `05` was updated only in its
headline claims and left stale in its integration, distribution-failure, and test-adoption prose.

The lesson, recorded for future excisions: **a name-level grep proves a module was removed; the real
residue is the prose that survives around the deleted code.** Grep for the deleted concept's *verbs*
— import, ships, resolves, distributes — not only its identifier.

Independent validator run: `valid: true`, 55 requirements, 8 spec files, 0 uncovered, 0 orphaned.
Confirmed separately: 55 unique bolded definitions, no foreign-feature `REQ-*` citation, 55 matrix
rows with an identical ID set, 0 broken section citations across all 11 documents.

## Round-3 Findings: Disposition

| ID | Status |
|---|---|
| R3-V-001 REQ-REL-04 had no verification coverage | Still resolved |
| R3-V-002 phantom `forge-update` in exclusion set | Still resolved |
| R3-V-003 epic-root concurrency candidate unrecorded | Still resolved |
| R3-V-004 tech-spec §2.1 omitted `forge-bootstrap.py` | Still resolved |
| R3-V-005 phantom `REQ-PORT` row in `01` | Still resolved |

## Findings

| ID | Severity | Location | Issue |
|---|---|---|---|
| R4-V-001 | error | `05` §3.1, §3.2 | Two **empty** `python` fences still introduced as "add this sibling import". Nothing to add — both scripts already import `json`, `sys`, `Path`. |
| R4-V-002 | error | `00` §8 | "…and the corresponding bootstrap config read **import this helper**" — contradicts §8's own opening and §1's bullet. Highest-leverage stale claim, since `00` is the shared-vocabulary document. |
| R4-V-003 | error | `05` §2.1 | The "complete implementation contract" block still led with module scaffolding (docstring, `from __future__`, three imports). Pasted verbatim it is a **SyntaxError** — `from __future__` must precede all statements. It also omitted the `#: mirrors …` comment the drift guard asserts. |
| R4-V-004 | inconsistency | `05` §5.2, §5.3, §8.2 | Runtime `ModuleNotFoundError` handling specified for a module that does not exist, contradicting §5.1's own "no import has to resolve at runtime". |
| R4-V-005 | error | `05` §1 | Still claimed the document covers "distribution of the **new runtime helper**". |
| R4-V-006 | error | `01` §6 | "New helper presence is asserted for all six targets" — the last place instructing a test to assert a seventh helper ships. |
| R4-V-007 | error | `tech-spec` §6.1 | "`RUNTIME_HELPERS` copies `forge-session.py` and `epic-manifest.py`" — it copies **six** files. Tolerable before `f8f01c9`; not now, because `forge-bootstrap.py` carries a mirrored copy and whether it reaches every bundle is the distribution question. |
| R4-V-008 | inconsistency | `05` API / §8.1, `00` API, `07` §5.1 | Three-way conflict: loader "callable by nobody outside the two scripts", yet tests must call it, via "placing `scripts/` on the test import path" — mechanically impossible, both filenames are hyphenated. `07` §5.1's `spec_from_file_location` instruction is the sound one. |
| R4-V-009 | improvement | `05` §4 | "Circular import" rationale is stale. The rule that matters now is stronger: a copy referencing its host's `UsageError` could not stay byte-identical, and the drift guard would fail. |
| R4-V-010 | inconsistency | `01` §2, `tech-spec` §2.1 | `build-adapters.py` marked `M` (modified) with an annotation saying nothing changes. |
| R4-V-011 | improvement | `07` §5.1, `01` §3.4 | Drift guard **assessed sound and sufficient**, but under-specified in three ways: "normalize leading indentation" read per-line would flatten the nested `object_from_pairs` and mask divergence (needs uniform `textwrap.dedent`); missing-copy behavior unspecified; comment scope/count ambiguous between "one per file" and "one per function". |
| R4-V-012 | improvement | `07` §8.2, `tech-spec` §2.1 | `tests/test_json_loader_parity.py` — the feature's only new test file — missing from the focused pytest groups and the tech-spec test list. |
| R4-V-013 | improvement | `01` §5, `05` §7, `07` §5.2, `tech-spec` §6.4 | Residual "shared parser / shared helper / adapter helper copy" wording. |
| R4-V-014 | gap | `01` §2, `tech-spec` §2.1 | `tests/test_forge_bootstrap.py` required by `05` §8.1 and `07` §8.2 but absent from both file maps. Load-bearing since `f8f01c9`: bootstrap's mirrored copy has its *behavior* exercised only there. |

## Drift-Guard Assessment (R4-V-011)

The approach is **sound and sufficient**. Comparing normalized function source is the right
substitute for `ast.literal_eval` when the mirrored unit is a pair of functions; it catches every
divergence that matters (body, docstring, signature, warning text) that a behavioral test would
catch only by luck; it is pinned to `scripts/` canon rather than `adapters/`; and pairing it with
§5.1's "parametrize over both copies" means divergence fails structurally *and* behaviourally. The
`#: mirrors …` assertion is right in kind — `tests/test_stage_constants_parity.py` notes both
existing copies already carry "mirrors …" comments that "neither was enforced", so enforcing it here
is the correct increment. The three gaps above were closed rather than left to implementation.

## Observations (not findings)

- `04` §5 refers to a bare `references/result-reporting.md` that does not exist at the repo root;
  lines 26 and 337 of the same document pin the correct skill-local path. Same class as the
  known-and-accepted REQ-CAP-01 bare path, in a document `f8f01c9` did not touch. Noted so a future
  round does not rediscover it as new.
- `02`, `03`, `04`, and `06` contain **zero** shared-module assumptions. The excision residue was
  confined to `00` §8, `05`, `01`, and `tech-spec`.
- `07` came through `f8f01c9` cleanest — §5.1's hyphenated-filename note, §6.3's six-entry
  assertion, and §2.3's "no new fixture file" are all correct and independently verified.

## Fix Progress

- Steps 1–6: [APPLIED] 2026-07-30 — All 14 findings fixed. `05`: §1 reframed; both empty fences and
  their "add this import" sentences replaced with mirrored-placement instructions naming the exact
  insertion point in each script; §2.1 block stripped to comment + two `def`s with a paragraph
  defining the mirrored region and the SyntaxError rationale; §4 circular-import rationale replaced
  with the byte-identity rule; §5.2/§5.3/§8.2 `ModuleNotFoundError` language replaced with
  divergence-risk language; §7 and §8.1 reworded, §8.1 now naming `spec_from_file_location`; Public
  API bullet now permits `tests/` to load a copy while forbidding production callers. `00`: §8 "each
  call their own in-file copy"; the two helpers moved out of the importable bullet into a new
  "Mirrored private, per-script" bullet. `01`: §6 helper-presence bullet replaced with byte-identity;
  `build-adapters.py` marker `M` → `—`; `test_forge_bootstrap.py` row added; §5 step 2 reworded;
  §3.4 drift-guard paragraph gained the dedent and one-comment-per-file rules. `tech-spec`: §6.1
  now enumerates all six helpers; §2.1 marker clarified; `test_json_loader_parity.py` and
  `test_forge_bootstrap.py` added to the test block; §6.4 reworded. `07`: §5.1 gained the
  extraction-success, `textwrap.dedent`, and comment-scope sentences; §8.2 group 3 gained the drift
  guard; §5.2 reworded.
- Step 7: [APPLIED] 2026-07-30 — Re-validated. `valid: true`, 55 requirements, 0 uncovered, 0
  orphaned; matrix 55 rows. Verifier's own greps all clean: `sibling import`, `ModuleNotFoundError`,
  `the shared helper`, `shared duplicate-aware parser`, `test import path`, and `New helper presence`
  all occur **0×**; zero empty `python` fences; every fenced Python block parses; `forge_json` occurs
  exactly **once**, in `01` §3.4's rationale. `ruff` and `bash scripts/validate.sh` both green.
- Version bumps: [APPLIED] 2026-07-30 — See below.

## Version Assessment — Applied

The verifier recommended bumping both stages, and the argument holds:

`f8f01c9` was **author-initiated structural revision**, not a fix pass — it deleted a planned file,
removed the feature's only intra-project import boundary, changed its `RUNTIME_HELPERS` posture, and
rewrote sections of six documents *after* the stage was marked `findings-applied`. Rounds 1–3
legitimately did not bump, because those were fix passes inside the verify cycle. This one is not.
Leaving `forge-3-specs` at v1 asserted that verification covered the current document set; it did
not, and this round's 14 findings — concentrated in exactly those six documents — are the empirical
demonstration, not a hypothetical.

The stronger case was `forge-2-tech`: `f8f01c9` edited `tech-spec.md` §§2.1/3.9/6.2/6.4/8 while
`forge-verify-tech` remained `passed` with `verifiedStageVersion: 2` and zero findings — a *passed*
claim over unverified content, with R4-V-007 (a factual error) sitting in one of the edited
sections. That is a worse failure mode than a stale `findings-applied`.

Applied: `forge-2-tech` → v3, `forge-3-specs` → v2 (`basedOnVersions` `{forge-1-prd: 3,
forge-2-tech: 3}`), `forge-verify-specs` → `findings-applied` at `verifiedStageVersion: 2`.
`forge-verify-tech` is left at its `passed`/v2 record, which the ledger now correctly reads as
**stale** — a tech-mode re-verify is owed before `forge-4-backlog`.
