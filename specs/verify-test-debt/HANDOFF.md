# verify-test-debt — Loop Record

> **This is a post-loop record, not an in-flight handoff.** An earlier revision of this
> file was written mid-run and described a stalled loop with 0 of 16 items done. That
> state is historical; §1 below is current. Nothing here asks to be acted on.

**Originally written:** 2026-08-04, after the first (stalled) `forge-5-loop` run.
**Rewritten:** 2026-08-04, after the loop completed, by the `forge-fix` pass applying
finding V-005 of `.verification/VERIFY-impl-2026-08-04.md`.

**Branch:** `forge/verify-test-debt`

---

## 1. Where the feature stands

`forge-5-loop` is **complete** at v1. **All 16 backlog items are `done`** — 0 pending,
0 in-progress, 0 blocked, 0 needs-human. Verify with:

```
rauf-stable status . --backlog specs/verify-test-debt --json
```

Each item landed as its own commit, prefixed `[rauf] NNN:`, through `bcb5cff`.

The ordered gate list from `07-testing-strategy.md` §3 is green:

| Gate | Result |
|---|---|
| `bash scripts/validate.sh` | exit 0 — `All checks passed!` |
| `python3 -m pytest tests -q` | 1802 passed, 2 skipped — **1804 collected**, matching the current `07` §5.4 figure. The loop itself closed at **1799**, exactly as §5.4 predicted; the `+5` is the post-verify allowlist guard recorded in `07` §5.5 |
| `python3 scripts/build-adapters.py --check` | exit 0 |
| `python3 scripts/check-spec-purity.py` | PASS — 0 violations |
| `ruff check scripts/ eval/` | clean |
| `ruff check tests/` | 19 errors, the accepted pre-existing baseline (`07` §3 gate 5 budget is ≤19) |
| `CANONICAL_EXIT_SITES` import gate | resolves, 9 entries |

The two pytest skips are pre-existing and environment-gated
(`tests/test_forge_bootstrap.py:919` — `mypy` and `cargo-clippy` absent), not this
feature's.

`forge-verify-impl` ran on 2026-08-04 and reported findings; see
`.verification/VERIFY-impl-2026-08-04.md`. The implementation itself was found sound —
every item's acceptance criteria hold against the code on disk.

## 2. Why the first run stalled, and how it was resolved

Recorded because the resolution changed a shipped script, and because the failure mode
is worth recognizing again.

The first launch used 5 of 24 iterations and stopped with nothing selectable — it did
not hit the iteration limit and did not circuit-break. Items `001`, `002`, `004` are the
backlog's only roots, and all three emitted `needs_human` for the **same** reason:
`bash scripts/validate.sh` was red at HEAD on three traceability orphans
(`REQ-DEBT-04`, `REQ-REL-01`, `REQ-STATE-01`). Each item's own acceptance criteria
passed; only the shared final AC — a green `validate.sh` — failed. Every remaining item
descends from those three roots, so one shared red gate halted the entire backlog:

```
001 -> 005 -> 006 -> 007 -> 008 -> 009 -> 010 -+
                                               +-> 011 -> 012 -> 013 -> 014 -> 015 -+
002 -> 003 ------------------------------------+                                    +-> 016
004 --------------------------------------------------------------------------------+
```

**Resolution.** The operator chose to add an allowlist to `validate-traceability.py`.
The three ids are genuine quotations of test docstrings from the antecedent
`stage-exit-coverage` feature, where they are *defined*; they are not requirements of
this suite. The script gained a repeatable `--allow-orphan REQ-ID` flag plus
auto-discovery of `<specs-dir>/.traceability-allowlist`, with allowed ids reported as
`ALLOWED FOREIGN REFERENCES` rather than silently dropped. The ids are deliberately
**not** hardcoded — that file ships into every adapter bundle and consuming repo.

This change is inventoried in `01-architecture-layout.md` §3.4, recorded in
`TRACEABILITY.md` § Coverage Verification, and documented for users in `README.md` and
`CHANGELOG.md`. The tree was reconciled and the loop relaunched; it then ran to 16/16.

## 3. Known process gaps (filed)

These are the tooling gaps that made this run need a hand-written record rather than
producing one automatically. They are recorded for whoever works on the loop tooling
next; they are not blockers for this feature, which is complete.

| Issue | Gap |
|---|---|
| [#196](https://github.com/garygentry/feature-forge/issues/196) | needs-human answers are collected but never persisted |
| [#189](https://github.com/garygentry/feature-forge/issues/189) | no stage-exit outcome for a decision already made and applied |
| [#190](https://github.com/garygentry/feature-forge/issues/190) | pending items always misreported as "iteration limit reached" |
| [#191](https://github.com/garygentry/feature-forge/issues/191) | no systemic-cause detection across repeated needs-human signals |
| [#192](https://github.com/garygentry/feature-forge/issues/192) | no post-run tree reconciliation |
| [#193](https://github.com/garygentry/feature-forge/issues/193) | resolved items are never unblocked |
| [#194](https://github.com/garygentry/feature-forge/issues/194) | no dependency-topology check on the backlog |
| [#195](https://github.com/garygentry/feature-forge/issues/195) | `.gitignore` misses `**/.rauf/progress.md` — **resolved**; the rule is now in `.gitignore`, alongside a `*.json.bak` rule added for the same class of stray runner artifact |
