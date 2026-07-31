# Verification Report: stage-exit-coverage (impl, round 2)

Date: 2026-07-31
Pipeline Stage: forge-5-loop (complete, v1)
Mode: impl — served production stage `forge-5-loop`
Method: clean-room `forge-verifier` re-verification in require-clean mode, over the fix pass recorded in `VERIFY-impl-2026-07-31.md` (commits `493ce46` + `f70909d`).

## Summary

Round 1 reported 18 findings. After the fix pass:

- **12 cleanly resolved** — V-001, V-002, V-004, V-006, V-007, V-008, V-010, V-012, V-013, V-014, V-015, V-016
- **2 partially resolved** — V-003, V-005
- **3 still open** — V-009, V-011, V-017 (V-011 and V-017 had no execution step in round 1's plan; V-009's Step 11 was declined)
- **1 deferred by recorded decision** — V-018
- **5 new defects introduced by the fix pass** — N-1 … N-5

Total findings in this round: **10** (N-1…N-5, plus the carried-forward V-003, V-005, V-009, V-011, V-017).

Both judgment calls flagged for adversarial scrutiny survived review: V-004's `verifyGate == "none"` is correct and the round-1 suggestion of `"manual-print"` would have pinned a spec violation; the `forge-5-loop` line-cap reclamation dropped no normative content (word-level diff shows the four rewrapped paragraphs are word-identical).

**Root cause of N-1…N-3:** the fix pass validated its 192-site bulk edit with the same regex that produced it, so anything the pattern could not see was invisible to the check as well. Gate coverage cannot substitute here — Python does not parse comments or docstring prose, so all three corruptions pass every test, `ruff`, and `py_compile`.

### Gate (re-run independently, not taken on report)

| Check | Result |
|---|---|
| `bash scripts/validate.sh` ×2 back-to-back | exit **0** / exit **0**, both `PASS: epic-manifest pytest suite`, `✔ Validation passed` |
| Suite | **1762 passed, 2 skipped** |
| `tests/fixtures` bytecode after both runs | zero — V-001's idempotency defect genuinely fixed |
| `python3 scripts/build-adapters.py --check` | exit **0**, no drift |
| `ruff check scripts/ eval/` | exit **0**, `All checks passed!` |

---

## Findings

### N-1: The citation strip de-indented three docstring continuation lines to column 0

- **Severity:** error
- **Location:** `scripts/forge-session.py:5013` and `:3378`; `scripts/epic-manifest.py:884`; mirrored into all six `adapters/*/scripts/` copies
- **Issue:** `strip_citations.py`'s `re.sub(r"\s*\x01", "", out)` consumed the **leading indentation** of any continuation line whose entire content was the coordinate parenthetical. Three sites landed as broken prose at column 0:

  | File:line | Current (broken) | Original coordinate removed |
  |---|---|---|
  | `forge-session.py:5013` | `. Resolved through the same` | `` (`03-verification-state.md` §3.2 step 2). `` |
  | `forge-session.py:3378` | `, never by the successor table: for an epic member the adjacent` | `(02 §8),` |
  | `epic-manifest.py:884` | `.` (bare period) | `(04-pipeline-integration.md).` |

  `forge-session.py:5013` is inside `cmd_state_verify`'s public `Args:` block — the very docstring round 1's V-005 asked to be rewritten for clarity. No gate can see this: comments and docstring prose are not parsed, so `py_compile`, `ruff`, and all 1762 tests pass over it.
- **Suggested fix:** Restore the 6/8/12-space indentation at each site and rejoin the fragment to its sentence, then re-run `python3 scripts/build-adapters.py`. Verify by eye, not by the strip regex.
- **References:** `493ce46`; the fix pass's `strip_citations.py` line-joining rules

### N-2: The same script merged two words across a removed space

- **Severity:** error
- **Location:** `scripts/epic-manifest.py:1297`, mirrored six times
- **Issue:** `re.sub(r"\s+\.", ".", out)` — added to clean up a space left before a sentence-ending period — also collapsed the legitimate space in `read from .epic-state.json alone`, producing `read from.epic-state.json alone`. Same invisibility as N-1.
- **Suggested fix:** Restore the space. Then audit every other `\s+\.` application in the same commit for the same class of false positive (the fix pass caught three `#:.pipeline-state.json` instances of this during the pass and repaired them; this one was missed).

### N-3: Six spec coordinates survive in `forge-session.py`, invisible to V-005's own grep

- **Severity:** inconsistency
- **Location:** `scripts/forge-session.py:520`, `:593`, `:603`, `:604`, `:605`, `:609`
- **Issue:** V-005's pattern requires a literal space (`\b0[0-7] §[0-9]`), so the **backticked** variant is invisible to it. Six such coordinates remain: `` `02` §3.1 `` (:520), `` `02` §10 `` (:593), `` `02` §9 `` (:603), `` `03` §5.1 `` (:604), `` `03` §5.3 `` (:605), `` `04` §2.2 `` (:609). Base `9a663e1` had **zero**, so all six were added by this loop and fall squarely inside V-005's scope. Bare `§` references in the same file also went 3 → 12. The fix pass's "0 remaining in all three files" is therefore an artifact of measuring with the producing regex.
- **Suggested fix:** Extend the pattern to `` `?0[0-7]`?\s*§ `` and re-strip, handling each of the six by hand since all sit in prose. Re-measure with a **different** pattern than the one used to edit.

### N-4: The V-003 guard's clause (c) is unfalsifiable

- **Severity:** improvement
- **Location:** `tests/test_capability_determination_prose.py`, `CLAUSES["c"]` (lines 69–87)
- **Issue:** The accepted phrasing `"Standard Verify Gate first when you may not dispatch unsolicited"` lives in the DIRECTIVES-consumption paragraph that appears **verbatim in all nine exit skills**, including the three listed in `SURFACES_WITHOUT_PROSE`. Verified by mutation on copies: deleting `skills/forge-1-prd/SKILL.md`'s and `skills/forge-verify/SKILL.md`'s real clause-(c) sentences left the guard **green** both times. `skills/forge-fix/SKILL.md` carries no clause-(c) statement in its capability paragraph at all and passes solely on that boilerplate. Negative control 3 fails only because it deletes the shared boilerplate too — not a degradation any real edit would produce.
- **Suggested fix:** Scope the clause match to the capability paragraph itself, or drop the boilerplate fragment from `CLAUSES["c"]` so the clause must be stated where it is determined.

### N-5: Clause (b) is degradable on `forge-verify`, and the controls only exercise one surface

- **Severity:** improvement
- **Location:** `tests/test_capability_determination_prose.py`, `CLAUSES["b"]` and `_representative_surface()`
- **Issue:** `skills/forge-verify/SKILL.md` matches clause (b) only via `"Reserve \`manual\`"`, a token carrying no semantic content. Rewriting `:261` to *"Reserve `manual` for any session that may not dispatch a subagent unsolicited"* — **the exact misreading §6.2 exists to prevent** — left the guard green on a copy. Negative control 2 never exercises this path because `_representative_surface()` returns `forge-1-prd`, which matches on the other phrasing.
- **Suggested fix:** Require the `"**no** question mechanism **and** **no** permitted dispatch"` conjunction for clause (b), and run the three negative controls over **every** surface in the roster rather than one representative.

### Carried forward from round 1

- **V-003 (partially resolved):** the guard landed with a derived 6-surface roster, a floor, three controls, and an unskippable check — structurally sound — but two of three clauses are too loose. See N-4, N-5.
- **V-005 (partially resolved):** substance preserved and no code damaged (word-level `difflib` versus `493ce46~1` shows every non-equal opcode is a coordinate deletion with the sentence retained, or a clean hand rewrite), and the rewritten `cmd_state_verify` status matrix is **accurate** against the validation code at `forge-session.py:5143-5212`. Remaining: N-1, N-2, N-3.
- **V-009 (not resolved):** Step 11 declined. The reasoning holds on its facts — 30 files in scope still match, so a blanket rule would red-gate and a 26-entry allowlist would gut it — **but the conclusion is over-broad**: V-009 explicitly asked for an allowlist, and a file-level *ratchet* (lock the files Step 6 cleaned, grandfather the rest with a shrinking documented list) was landable and was not considered. Note the sting: even a Rule 7 scoped to only the three files Step 6 touched would have gone **red on N-3**. The rule declined is precisely the rule that would have caught the leak that was missed.
- **V-011 (not resolved):** `LOOKBEHIND = 12` / `LOOKAHEAD = 8` still unpinned by any test; the message at `tests/test_state_verb_call_sites.py:136` still reads "{LOOKBEHIND} lines above" only.
- **V-017 (not resolved):** `ruff check tests/` → 21 errors, including the F841 at `tests/test_forge_bootstrap.py:733` and F541 at `tests/test_stage_exit.py:2362`.

---

## Fix Execution Plan

### User Decisions Required

1. **V-009 / Rule 7 shape.** Land a file-level **ratchet** (lock the cleaned files, grandfather the rest in a shrinking documented list), or keep it deferred pending a repo-wide citation purge? The ratchet is the reviewer's recommendation and would have caught N-3.
   - **RESOLVED 2026-07-31 — land the file-level ratchet.** Lock the files cleaned by the round-1 fix pass so any new citation there fails the gate; grandfather the remaining matching files in a documented, shrinking allowlist.
2. **V-017.** Option (a) record why `tests/` is out of lint scope in `ruff.toml`, or (b) fix the two non-cosmetic hits (F841, F541). Unchanged from round 1.
   - **RESOLVED 2026-07-31 — option (b).** Fix the two non-cosmetic hits (F841 at `tests/test_forge_bootstrap.py:733`, F541 at `tests/test_stage_exit.py:2362`); leave the 19 cosmetic hits and do not change `ruff.toml`.

### Execution Steps

#### Step 1: Repair the three de-indented docstrings and the merged word
- **Files:** `scripts/forge-session.py` (:5013, :3378), `scripts/epic-manifest.py` (:884, :1297)
- **Addresses:** N-1, N-2
- **Action:** Restore indentation and rejoin each fragment to its sentence; restore the space in `read from .epic-state.json`. Read each site in full context — do **not** pattern-match. Then `python3 scripts/build-adapters.py`.
- **Depends on:** none — do this first; it is shipped-surface corruption.

#### Step 2: Strip the six backticked coordinates
- **Files:** `scripts/forge-session.py` (:520, :593, :603, :604, :605, :609)
- **Addresses:** N-3
- **Action:** Rewrite each by hand, keeping the sentence. Then re-measure with a **different** pattern than the one used to edit — e.g. `` grep -nE '`?0[0-7]`?\s*§|\b0[0-9]-[a-z][a-z-]*[a-z]\.md|tech-spec' ``.
- **Depends on:** Step 1

#### Step 3: Tighten the capability guard's clauses (b) and (c)
- **Files:** `tests/test_capability_determination_prose.py`
- **Addresses:** N-4, N-5
- **Action:** Drop the shared-boilerplate fragment from `CLAUSES["c"]` (or scope matching to the capability paragraph); require the "no question mechanism **and** no permitted dispatch" conjunction for clause (b); run the three negative controls over every roster surface, not one representative. Re-run the mutations in N-4/N-5 and confirm each now fails.
- **Depends on:** none

#### Step 4: Address V-011
- **Files:** `tests/test_state_verb_call_sites.py`
- **Addresses:** V-011
- **Action:** Per round 1's V-011 suggested fix — add `test_the_window_is_no_wider_than_the_measured_maximum` asserting `LOOKBEHIND <= 12 and LOOKAHEAD <= 8`, and reword the message to "within {LOOKBEHIND} lines above or {LOOKAHEAD} lines below".
- **Depends on:** none

#### Step 5: Apply Decisions 1 and 2
- **Files:** `scripts/check-spec-purity.py`, `tests/test_check_spec_purity.py`, `ruff.toml` or the two test files
- **Addresses:** V-009, V-017
- **Depends on:** Decisions 1, 2; Steps 1–2 (a ratchet red-gates until N-3 is cleared)

#### Step 6: Regenerate and re-gate
- **Action:** `python3 scripts/build-adapters.py`, then `bash scripts/validate.sh` **twice** (both exit 0, both `PASS`), then `ruff check scripts/ eval/`.
- **Depends on:** Steps 1–5

---

## Fix Progress

- Step 1: [APPLIED] 2026-07-31 — Restored the three de-indented docstring continuations (`forge-session.py` `cmd_state_verify` Args block and the `forge-6-docs` routing paragraph; `epic-manifest.py` `is_complete_for_orchestration`) and the merged word `read from .epic-state.json`. Audit of the full fix-pass diff found a **fourth** site of the same class the report did not list — a bare `.` at `forge-session.py:3300`, orphaned from the `verify_capability` Args entry — now repaired. A `[a-z]{2,}\.[a-z]{2,}` sweep over every added line confirms no other space-collapse merges remain. `build-adapters.py` re-run; all six adapter copies verified clean.
- Step 2: [APPLIED] 2026-07-31 — Rewrote by hand all nine coordinates this loop added to `forge-session.py`: the six backticked ones from N-3 (`:520`, `:593`, `:603`, `:604`, `:605`, `:609`) plus three bare-`§` additions the finding's prose also flagged (`:513`, `:2110`, `:3600`). Re-measured with an independent pattern (`§|\b0[0-9]-[a-z-]+\.md`): `forge-session.py` is back to **3** — byte-for-byte the three references present at base `9a663e1` — and `epic-manifest.py` is at **0** (base 66).
- Step 3: [APPLIED] 2026-07-31 — Tightened `tests/test_capability_determination_prose.py` on both axes. Clause matching is now **scoped to the capability paragraph** (`_capability_paragraph`), so the DIRECTIVES boilerplate that appears verbatim in all nine exit skills can no longer satisfy a clause; the boilerplate fragment was also dropped from `CLAUSES["c"]`. `shared-conventions.md` is scoped to its **Verify Capability section** instead, since it states the clauses across a bulleted section. Clause (b) now requires the conjunction `"**no** question mechanism **and** **no** permitted dispatch"` in place of the semantically empty `"Reserve \`manual\`"`. The three negative controls are `parametrize`d over **every** roster surface (6), replacing `_representative_surface()`, plus a new `test_the_controls_cover_every_determining_surface`. **Root-cause fix beyond the finding:** N-4 exposed that `skills/forge-fix/SKILL.md` carried *no* clause-(c) statement in its capability paragraph — it passed on boilerplate alone — so the missing sentence was added to canon; dropping the fragment without it would have red-gated a genuine gap rather than fixing it. All four mutations from N-4/N-5 re-run and confirmed **red** (previously green): deleting the real clause-(c) sentence from forge-1-prd, forge-verify, and forge-fix, and rewriting forge-verify's clause (b) into the exact misreading §6.2 exists to prevent.
- Step 4: [APPLIED] 2026-07-31 — `tests/test_state_verb_call_sites.py`: added `test_the_window_is_no_wider_than_the_measured_maximum` pinning `LOOKBEHIND <= 12` and `LOOKAHEAD <= 8` (with the buried-mandate failure mode documented as the reason), reworded Guard 1's message to "within {LOOKBEHIND} lines above or {LOOKAHEAD} lines below", and added `test_the_failure_message_describes_the_whole_window` so the message cannot silently drift back to describing one limb.
- Step 5: [APPLIED] 2026-07-31 — Both decisions.
  - **Decision 1 (V-009) — file-level ratchet landed as Rule 7** in `scripts/check-spec-purity.py` (`check_no_spec_citations`, `Rule.SELF_CONTAINMENT`, `VR_SPEC_CITATION`). **Default-deny** over `scripts/`, `references/`, `skills/`, `eval/`, with the 29 files carrying existing debt grandfathered by exact path in `CITATION_GRANDFATHERED` (each annotated with its count; a rename re-locks). The three files the round-1 pass cleaned — `forge-session.py`, `epic-manifest.py`, `eval/run-compliance-eval.py` — are deliberately **not** grandfathered, so they can never regress, and any new file starts locked. The pattern accepts the backticked variant (`` `02` §3.1 ``) that N-3 slipped through, and deliberately does **not** match a bare intra-file `§`. Coverage added in `tests/test_check_spec_purity.py` (8 tests incl. a sorted/deduped/must-still-be-dirty allowlist audit that makes "delete the line" the natural maintenance action). **The reviewer's claim was measured, not assumed:** run against `99e63e6:scripts/forge-session.py`, Rule 7 reports exactly **6** citations — it would have caught N-3. Pinned as `test_the_ratchet_would_have_caught_the_n3_leak`.
  - **Decision 2 (V-017) — option (b).** Fixed F841 (`tests/test_forge_bootstrap.py:733`, unused `worker`) and F541 (`tests/test_stage_exit.py:2362`, extraneous `f` prefix). `ruff check tests/ --select F841,F541` → clean; the 19 cosmetic hits are left as decided and `ruff.toml` is unchanged.
- Step 6: [APPLIED] 2026-07-31 — `build-adapters.py` regenerated, `--check` exit 0 (no drift). `bash scripts/validate.sh` twice back-to-back: exit **0** / exit **0**, both `All checks passed!`. Suite **1789 passed, 2 skipped** (was 1762 + 2; +27 from the new Rule 7 and per-surface control coverage). `tests/fixtures` bytecode after both runs: **zero**. `ruff check scripts/ eval/` → `All checks passed!`.

### Round-2 outcome

All 10 findings addressed: N-1, N-2, N-3, N-4, N-5 fixed; V-003 and V-005 closed out by Steps 1–3; V-009 resolved by the ratchet (Decision 1); V-011 by Step 4; V-017 by Decision 2. Two defects were found during this pass that the report did not list — a fourth de-indented docstring site (`forge-session.py:3300`) and three bare-`§` coordinates beyond N-3's six — and both were repaired.
