# Verification Report: stage-exit-coverage (backlog)
Date: 2026-07-30
Pipeline Stage: forge-4-backlog — **stale** (backlog v2 authored against specs v3; specs are now v4 @ `effe263`)
Artifacts Reviewed: `backlog.json` (29 items, 001–029), `PRD.md`, `tech-spec.md`, `TRACEABILITY.md`,
all eight `##-*.md` specs, `.verification/VERIFY-specs-2026-07-30-round5.md`; corroborating repo
reads of `scripts/forge-session.py`, `scripts/validate.sh`, `scripts/build-adapters.py`,
`tests/test_state_verb_call_sites.py`, `references/shared-conventions.md`, and the skill bodies
under `skills/`.

Method: four parallel `forge-verifier` instances over disjoint CHECK-ID slices (item scoping &
acceptance criteria, dependency/ordering, spec coverage & traceability, schema/enum). 39 raw
findings merged to 32 after dedup; `V-NNN` IDs renumbered and `Checklist:` IDs unioned.

**Executed 27 of 27 checks. Results: 9 pass, 17 fail, 1 not-applicable.**

Deterministic corroboration: `rauf-stable backlog validate . --backlog specs/stage-exit-coverage
--specs-dir specs/stage-exit-coverage --json` → `{"valid": true, "findings": []}`. The runner's
schema check passes on every in-domain value; everything below is the semantic layer it cannot see.

**Both standing invariants hold, confirmed independently by three slices.** No item creates
`scripts/forge_json.py` (items 003 and 029 forbid it explicitly; `RUNTIME_HELPERS` is six entries at
`scripts/build-adapters.py:314-321`). No item introduces locking, leasing, or optimistic versioning
(item 007 step 5 and item 029 AC 4 add guard tests forbidding them).

**Framing: this backlog is not wrong about specs v3 — it is stale against v4.** One slice verified
via `git show effe263` that every spec clause cited below was *added* by the round-5 fix pass. The
dominant failure mode is therefore silent under-coverage: 29 well-formed items that no longer
describe the whole job.

## Summary
- Total findings: 32
- Gaps: 21
- Inconsistencies: 6
- Improvements: 5
- Errors: 0

---

## A. Uncovered v4 obligations (no item schedules the work)

### V-001: The navigator `skills/forge/SKILL.md` has no scheduling item at all
- **Severity:** gap
- **Location:** no item; `01-architecture-layout.md` §2, tech-spec §2.1, `04-skill-integration.md` §4.3
- **Issue:** `04` §4.3 specifies four concrete edits: extend the closed `verifyState` list (`skills/forge/SKILL.md:44`, `:90`) with `auto-pending`; add the durable-debt case to the `verifyPending` explanation (`:111`) and fire the catch-up branch on it; add a dashboard legend marker using `03` §5.3's wording; pass `owner: nested` when the catch-up chain dispatches `forge-verify`/`forge-fix`. A full-text scan of all 29 items returns **zero** hits for `skills/forge/SKILL.md`. Item 008 covers only the script side; item 023 covers stages 1–4. The file ships unedited, its documented enum becomes factually wrong the moment `auto-pending` is emitted, and its adapters are not regenerated.
- **Suggested fix:** **ADD item 030** "Teach the navigator skill the auto-pending label and nested-owner dispatch", `type: feature`, `priority: 1`, `dependsOn: ["008","017"]`, `specReferences`: `04`, `03`, `07`. ACs mirroring `07` §6.2: `verifyState` list includes `auto-pending`; the `verifyPending` explanation names durable debt and the catch-up branch fires on it; a legend marker exists; catch-up dispatch passes the literal `owner: nested`; adapters regenerated and committed. Add `"030"` to items **024** and **029** `dependsOn`. **See User Decision D2.**
- **Checklist:** CHECK-B07, CHECK-B22, CHECK-B23

### V-002: The `state-verify` registration in `references/shared-conventions.md` is unscheduled
- **Severity:** gap
- **Location:** item 023 (covers only the `state-note` half); `04-skill-integration.md` §4.3 edit 1
- **Issue:** `04` §4.3 requires two edits: register `state-verify` in the Pipeline State Protocol verb inventory (today `state-branch`/`state-complete`/`state-enter`/`state-artifact`, `references/shared-conventions.md:186` ff.) with its `--epic` rule and exit-2 protocol; and add the named `state-note` recipe. Item 023 covers only the second. `"Pipeline State Protocol"` and `"verb inventory"` return zero hits across all items. `04` §4.3 notes `tests/test_state_verb_call_sites.py::test_the_epic_mandate_itself_is_still_documented` treats this file as the mandate's normative home, so shipping the eighth verb against a seven-verb protocol is exactly the drift the protocol prevents.
- **Suggested fix:** **AMEND item 023**: add the registration step and the AC "`references/shared-conventions.md`'s Pipeline State Protocol lists `state-verify` among the `state-*` verbs with its `--epic` member rule". Add `"005"` to item 023 `dependsOn` (the verb must exist before it is documented), and add `"023"` to items **018** and **019** `dependsOn` per `04` §10's ordering.
- **Checklist:** CHECK-B07, CHECK-B22, CHECK-B23

### V-003: `findings-template.md`'s hand-authored `.epic-state.json` heredoc is never converted
- **Severity:** gap
- **Location:** no item (item 006's `notes` only *cites* the file); `04-skill-integration.md` §5.4
- **Issue:** `04` §5.4 requires deleting the "Write mechanism" paragraph and its `python3 - <<'PY'` heredoc (`tempfile.mkstemp` + `os.replace`) and substituting the `state-verify --stage forge-0-epic` fence. Leaving it (a) violates REQ-STATE-03 (P0) on the one epic path, (b) makes **every** epic verification classify `stale` under `03` §5.2 — a silent functional regression — and (c) makes canon self-contradictory. The only backlog mention is item 006's `notes` saying the contract "must stay additive", which *preserves* rather than converts, and item 006 lists neither the file nor its adapter regeneration.
- **Suggested fix:** **AMEND item 018** (which owns `skills/forge-verify/` canon): add the §5.4 conversion step, the ACs "no `.epic-state.json` write recipe, `tempfile.mkstemp`, or `os.replace` snippet survives anywhere under `skills/`" and "`findings-template.md` is in the regenerated adapter batch", and add `"006"` to `dependsOn`. Correct item 006's `notes`, which currently implies preservation.
- **Checklist:** CHECK-B07, CHECK-B08, CHECK-B22

### V-004: REQ-DEBT-05's fourth consumer class — downstream pre-flight gates — has no covering item
- **Severity:** gap
- **Location:** no item; `03-verification-state.md` §5.4, `04-skill-integration.md` §6.4, §7.2
- **Issue:** REQ-DEBT-05 (P0) names four consumers; items 008/009/012 cover three. The fourth needs two live skill edits, both verified present: `skills/forge-5-loop/SKILL.md` Step 1b (`:57`) warns "Backlog hasn't been verified yet" for anything outside `{passed, findings-applied}`, reporting owed-and-dropped auto-verify as never-scheduled; `skills/forge-6-docs/SKILL.md` Step 1 (`:40`) warns only on absent-or-`skipped` and proceeds silently on the resolved set — `auto-verify-pending` matches neither branch and proceeds silently, treating owed debt as discharged. `"Step 1b"` returns zero hits; `auto-verify-pending` appears in items 001/005/008/009/012 only (all script-side), in neither 020 nor 021.
- **Suggested fix:** **AMEND item 020** with the `04` §6.4 Step 1b third case and its AC; **AMEND item 021** with the `04` §7.2 backstop enumeration extension and its AC. Add `"008"` to both `dependsOn` (the §5.3 diagnostic wording originates there).
- **Checklist:** CHECK-B08, CHECK-B22, CHECK-B23

### V-005: The canon prose this feature falsifies is never scheduled for deletion or rewrite
- **Severity:** gap
- **Location:** items 018, 019; `04-skill-integration.md` §5.2, §5.3
- **Issue:** `04` §5.2 requires **deleting** the "Deliberate R4 exclusion" blockquote (`skills/forge-verify/SKILL.md:228`) because it "actively instructs a model to hand-author verify state". `04` §5.3 names three further sites that "would survive an edit scoped to Step 6": `skills/forge-fix/SKILL.md` Step 5's `verifiedStageVersion` write (`:69`), the two ledger claims (`:79`, `:86`), and the "Skip for now" wording. All four literals confirmed present. Item 018 says only "Replace hand-authored verify state with `state-verify` calls"; item 019 says only "Replace the current open-ended Step 6" — the exact scoping that leaves the other three intact. `"R4 exclusion"` and `"fresh in the ledger"` return zero hits.
- **Suggested fix:** **AMEND item 018** with the blockquote deletion + pointer substitution and the AC "no passage justifies hand-authoring a verify entry". **AMEND item 019** with the Step 5 replacement, both freshness rewrites, and the "Skip for now" → `deferred` reclassification, plus ACs asserting no "fresh in the ledger" claim and no hand-written `verifiedStageVersion` remain.
- **Checklist:** CHECK-B22, CHECK-B23

### V-006: The new `state-verify` fences will red-gate `validate.sh` — no item schedules the adjacent `--epic` instruction
- **Severity:** gap
- **Location:** items 018, 019, 023; `04-skill-integration.md` §5.1 final paragraph
- **Issue:** Confirmed against the live test: `CALL_RE = re.compile(r'forge-session\.py"?\s+(state-[a-z]+)')` (`:36`) matches `state-verify`, `LOOKBEHIND = 12` / `LOOKAHEAD = 8` (`:50-51`), and `_canon_files()` scans `skills/*/SKILL.md` plus `references/shared-conventions.md` — so all three new fence sites are in scope. Items 018/019 carry `bash scripts/validate.sh passes` as an AC but give no instruction that would make it pass; an implementer meets this as an unexplained red gate. Separately `07` §6.2 says "the `MIN_CALL_SITES` floor rises with them" (currently `21`, `:41`) — a deliberate tightening no item schedules.
- **Suggested fix:** **AMEND items 018 and 019** with the fence-adjacency requirement (and, for the `--stage forge-0-epic` fence, the `--feature`-names-the-epic exception stated adjacent), plus the AC "`python3 -m pytest tests/test_state_verb_call_sites.py` passes with the new `state-verify` call sites, each carrying `--epic` inside the guard's window". **AMEND item 029**'s sweep: "raise `MIN_CALL_SITES` to the new actual call-site count".
- **Checklist:** CHECK-B23, CHECK-B24

### V-007: The `owner: nested` / `owner: direct` token appears in no item
- **Severity:** gap
- **Location:** items 017, 018, 019; `04-skill-integration.md` §5.1 "How ownership reaches the skill"
- **Issue:** `04` §5.1 names the carrier that §3.1 forbids inferring: the dispatching caller states ownership with the literal token, and "absent the token the skill treats itself as `direct`". The spec warns a misclassification yields a second sentinel inside an outer stage's exit and that "the §10 canon guard cannot catch it, because both wordings legitimately appear in the same file". Items 018/019 say only "Determine `direct` vs `nested` at entry" — the judgment call §3.1 forbids — and never name the carrier. Scan for `owner: nested`/`owner: direct`: zero hits (the 24 `owner` hits are all `--owner` flag mentions).
- **Suggested fix:** **AMEND item 017** to record the token contract in `references/stage-exit-protocol.md`. **AMEND items 018 and 019** to read the token rather than determine ownership, delete the retired inference precedent (`skills/forge-fix/SKILL.md:81`), and pass the value through as `--owner`; AC on both: "the skill reads ownership from the literal `owner:` token and defaults to `direct` when absent; no path infers ownership from invocation phrasing".
- **Checklist:** CHECK-B22, CHECK-B23

### V-008: `verifyStage` and `warnings: list[str]` are scheduled by no item
- **Severity:** gap
- **Location:** items 010, 011, 012, 013, 016; `00-core-definitions.md` §4
- **Issue:** v4 adds `verifyStage: str | None` (distinct from branch-only `servedStage`) and converts `warning: str` to `warnings: list[str]` with the fixed order epic-fallback → debt-metadata → revision-mismatch. Scan: `verifyStage` zero case-sensitive hits (the two case-insensitive hits are `autoVerifyStages`); the `warnings` hits are items 004/009, unrelated. Item 013 AC 6 enumerates the directive set as a **closed list** — "`servedStage`, `outcome`, `nextStage`, `primaryCommand`, `terminalOwnedBy`" — which now reads complete but is short. Item 017 still instructs surfacing singular `warning`.
  **Correction worth carrying forward:** one slice verified against `scripts/forge-session.py:1735-1750` that `stageNoun` **already exists** in the live directives dict (`:1737`). The round-5 spec finding was that the *contract document* omitted it; the implementation has it. So the backlog obligation is to **retain** `stageNoun` verbatim, not to add it — an item instructed to "add" it would be working from a false premise.
- **Suggested fix:** **AMEND item 010** (which lands the directives surface) to add `verifyStage` and `warnings: list[str]`, noting `stageNoun` is pre-existing and retained verbatim; ACs for both new keys. **AMEND item 017**: `warning` → `warnings` (a list, rendered in `00` §4's fixed order). **AMEND item 013** AC 6 to include `verifyStage` so the closed list stays truthful.
- **Checklist:** CHECK-B08, CHECK-B13, CHECK-B21, CHECK-B22

### V-009: The consent-gate variant on a `none` gate is scheduled by no item
- **Severity:** gap
- **Location:** item 017 step 4; `02-stage-exit-routing.md` §5.1, `04` §3.3 step 2, tech-spec §3.3
- **Issue:** v4 adds a second rendered gate form: `verifyGate` stays `none`, and the caller reuses the gate block **with choice 2 omitted**, because "enable auto-verify going forward" is a no-op when auto-verify is already effective and "offering a choice with no trade-off behind it violates REQ-A11Y-01". Item 017 step 4 specifies only the three-choice form, and its AC reads "The Standard Verify Gate is specified with **three** labeled choices" — which, applied as written, produces the REQ-A11Y-01 violation the spec calls out.
- **Suggested fix:** **AMEND item 017** step 4 with the consent variant (exactly two choices; `verifyGate` stays `none`; skip persisted as `skipped` before any advancing block) and the AC "the consent variant on a `none` gate is documented with exactly two labeled choices and its `verifyGate` stays `none`". Mirror one sentence into item 023's capability recipe.
- **Checklist:** CHECK-B22

### V-010: `--findings-file` relative-and-contained validation has no covering item
- **Severity:** gap
- **Location:** item 005; `03-verification-state.md` §3.3, §7.1
- **Issue:** v4 requires `findings-reported` to take a `findings_file` that is relative and contained, rejecting absolute paths, `..` segments, and NUL/control characters **before any mutation** (REQ-SEC-01, P0). Item 005 mentions `--findings-file` only as an argparse flag name; none of its eleven ACs assert containment, and its §3.3 matrix step enumerates the other rows' rules without this one. No containment rule for this flag appears anywhere in the backlog.
- **Suggested fix:** **AMEND item 005** step 5 with the containment rule and the AC "`--findings-file` values that are absolute, contain a `..` segment, carry NUL/control characters, or otherwise escape the resolved feature/epic directory each exit 2 before mutation and leave the state file byte-identical", plus the matching `07` §4.2 negative rows.
- **Checklist:** CHECK-B08, CHECK-B22

### V-011: The `00` §4/§6 result types are declared public surface but scheduled by no item
- **Severity:** gap
- **Location:** no item; `00-core-definitions.md` §4, §6, Public API section
- **Issue:** `00`'s Public API lists `EpicReconcile`, `StageExitDirectives`, `StageExitPayload`, and `VerifyEntry` as "repository-internal, importable by sibling modules and tests". `scripts/forge-session.py` imports `TypedDict` (`:146`) and defines only `FeatureRow` (`:236`) — none of the four exist. All four return zero hits across the backlog. Item 001 explicitly limits itself to "the `Literal` aliases … and the `Final` constants". So the feature's declared internal type surface is never written, and the normative invariants those types carry in their field comments (the `autoVerifyDebtRecorded` unreachability, the `total=False` absence-vs-null rule, the `warnings` ordering, the `deferred`-is-a-command rule) have no landing site.
- **Suggested fix:** **AMEND item 001** to add the four `TypedDict`s beside `FeatureRow`, copying field comments verbatim, with the AC that `stage_exit`/`cmd_state_verify` are typed against them. **See User Decision D1** — the alternative is a spec edit striking them from `00`'s Public API list.
- **Checklist:** CHECK-B21

---

## B. Items that contradict the amended specs

### V-012: Item 015 prescribes the exact `render-status` invocation v4 §8 forbids, and omits the timeout
- **Severity:** inconsistency
- **Location:** item 015 steps 2 and 5, AC 6; `02-stage-exit-routing.md` §8, §10
- **Issue:** Item 015 step 2 still says `python3 <bundle-root>/scripts/epic-manifest.py render-status …`. v4 §8's Invocation contract opens by forbidding exactly that: "`<bundle-root>` is not a path the router may guess … Resolve the helper as `Path(__file__).resolve().parent / "epic-manifest.py"` … invoke it with `sys.executable` rather than a bare `python3`, and bound it." A fresh agent following the item literally writes the banned form, and no AC catches it. AC 6 also omits three failure modes v4 §10 adds — subprocess timeout at the 10s bound, missing sibling helper, spawn failure — and no AC asserts the bound at all, so the item can be accepted with an unbounded subprocess on the one blocking call in the docs exit path. Scan: `sys.executable` and `TimeoutExpired` zero hits; `timeout` appears once, in prose.
- **Suggested fix:** **AMEND item 015**: replace step 2's command with the sibling-resolution + `sys.executable` + `subprocess.run(..., capture_output=True, text=True, timeout=10, check=False)` form; extend step 5's failure list with `TimeoutExpired`, `OSError`, and missing sibling, mapping each to exit 2 naming the epic and `/feature-forge:forge-0-epic EPIC`; extend step 6 with the `TimeoutExpired` injection from `07` §3.6; replace AC 6 with the seven-mode form; add the AC "the helper is resolved as a sibling of `forge-session.py` and invoked with `sys.executable`, never a guessed bundle root or a bare `python3`".
- **Checklist:** CHECK-B12, CHECK-B13, CHECK-B22

### V-013: Item 001 instructs hand-listing domains that `00` §2 now derives
- **Severity:** inconsistency
- **Location:** item 001 step 1, ACs 1–2; `00-core-definitions.md` §2
- **Issue:** v4 §2 carries an explicit comment — "Derived, never hand-listed … a hand-copied second list would drift silently — the failure this repository has already been bitten by twice" — and defines `EXIT_STAGES = get_args(ExitStage)` with `EXIT_OUTCOMES` from the four outcome aliases, plus the `VERIFY_MODE_TO_STAGE` parity sentence. Item 001 says "copy the literals verbatim" with AC "`scripts/forge-session.py` defines `EXIT_STAGES` with exactly the nine ids from `00` §2, in that order" — read literally, that authorizes precisely the second hand-maintained list §2 forbids. Scan: `get_args` zero hits.
- **Suggested fix:** **AMEND item 001** step 1 to the `get_args` derivation (adding the `typing` import) and rewrite AC 1 as "`EXIT_STAGES` and `EXIT_OUTCOMES` are derived from their `Literal` aliases via `get_args`; no second hand-written copy of any domain exists", adding the `VERIFY_MODE_TO_STAGE` parity assertion. Update step 4's `tests/test_stage_constants_parity.py` instruction accordingly.
- **Checklist:** CHECK-B21

### V-014: Item 017 is typed `refactor` but introduces new behavior six items depend on
- **Severity:** inconsistency
- **Location:** item 017, `"type": "refactor"`
- **Issue:** rauf's enum table defines `refactor` as "Restructuring existing code **without changing behavior**". Item 017 does the opposite: it replaces the five-stage wording and legacy terminal blocks with a new canonical stamp carrying new typed flags, newly specifies the Standard Verify Gate, the directive consumption order, the sentinel-last rule, and the `CLEAN_ROOM_UNAVAILABLE` recovery path. Items 018–023 stamp *from* it and 024 matches it verbatim. It is also the odd one out against the backlog's own convention: every sibling editing behavioral canon under `skills/` is `feature`; the one editing human docs (item 028) is `chore`. rauf surfaces `item.type` to the implementing agent, so `refactor` actively invites the "preserve current behavior" reading on the one item whose purpose is to replace the current contract.
- **Suggested fix:** **AMEND item 017**: `"type": "refactor"` → `"type": "feature"`.
- **Checklist:** CHECK-B04

### V-015: Item 020's REQ-FOLLOW-01 fix does not name the replacement pointer
- **Severity:** improvement
- **Location:** item 020 step 6; `04-skill-integration.md` §6.5
- **Issue:** REQ-FOLLOW-01 *is* covered — item 020 correctly schedules the `runner-contract.md` `--model` fix and preserves the conditional-load constraint. But v4 §6.5 now names the exact replacement ("a pointer to `## Optional flags catalog (Step 2d, rauf)` in `references/agent-selection.md`") and adds "This is a wording fix to one sentence, not a restructuring." Item 020 leaves the target to implementer judgment on a file guarded by body-cap and always-loaded-surface tests.
- **Suggested fix:** **AMEND item 020** step 6 to name the pointer and the one-sentence scope; extend its AC accordingly.
- **Checklist:** CHECK-B22

---

## C. Dependency and ordering defects

### V-016: The terminal sweep (029) asserts invariants produced by six items outside its closure
- **Severity:** gap
- **Location:** item 029, `dependsOn: ["024","028"]`
- **Issue:** 029's transitive closure is `{001, 005, 008, 010–028}` — it **excludes 002, 003, 004, 006, 007, 009**. Yet its own ACs assert exactly what those items establish: the `forge_json.py`-absent / `RUNTIME_HELPERS`-at-six / loader-parity invariants (items 003, 004); the no-lock/no-amend guard (item 007); and requirement traceability, which cannot hold while REQ-DEBT-01/05, REQ-REL-01 and REQ-OBS-02 work sits in items 002, 006, 009. A scheduler reaching 029 early would either fail the sweep for absent work or — worse — pass a vacuous sweep and present the feature as closed. Only id-order tie-breaking prevents this today; the graph does not.
- **Suggested fix:** **AMEND item 029** `dependsOn` → `["004","007","009","024","028"]` — the graph's four leaf nodes plus 028, making 029 provably last.
- **Checklist:** CHECK-B18, CHECK-B19

### V-017: Items 018 and 019 invoke `state-verify` modes that items 006 and 007 create
- **Severity:** gap
- **Location:** items 018, 019, both `dependsOn: ["005","013","017"]`
- **Issue:** Item 005 explicitly scopes itself to feature targets in result mode: "Leave the `forge-0-epic` branch to item 006 — reject it with a clear `UsageError` for now" and "Commit-2 mode lands in item 007." Yet item 018 step 3 requires `state-verify --commit-hash <40-hex>` (item 007) and step 1 requires epic mode rooted at `.epic-state.json` (item 006, which 005 is specified to *reject*). Item 019 writes fix results through the same `03` §4.2 sequence and needs 007 identically. As written both become ready after 005/013/017 and would document a CLI surface that exits 2.
- **Suggested fix:** **AMEND** `dependsOn` for items **018** and **019** → `["005","007","013","017"]`. Item 007 already depends on 006 → 002/005, so both prerequisites arrive transitively.
- **Checklist:** CHECK-B18

### V-018: Item 012's `forge-0-epic` scheduling branch needs items 006 and 002
- **Severity:** gap
- **Location:** item 012, `dependsOn: ["005","010","011"]`
- **Issue:** Item 012 step 5 requires "For `--stage forge-0-epic`, read `.epic-state.json` and the manifest revision directly", but the `.epic-state.json` read/lazy-create is item **006** (005 rejects the epic stage) and the canonical manifest `revision` is item **002**. 012's closure is `{001, 005, 010, 011, 008}` — neither is present, so step 2 is satisfiable only for feature targets.
- **Suggested fix:** **AMEND item 012** `dependsOn` → `["006","010","011"]` (006 pulls in 005 and 002, keeping the edge set minimal). `["005","006","010","011"]` is equally correct if explicitness is preferred.
- **Checklist:** CHECK-B18

### V-019: Item 014 names item 015 as the provider of machinery it reuses, with no edge
- **Severity:** gap
- **Location:** item 014, `dependsOn: ["010","011"]`
- **Issue:** Item 014 step 5 says verbatim: "delegate to the live epic status routing rather than duplicating dependency logic here (**item 015 lands the `render-status` consumption; reuse it**)". 014 and 015 share the identical dependency set, so the runner may select 014 first, leaving its `complete` route nothing to delegate to and the agent's only path to green being to duplicate the derivation inside `forge-session.py` — which `02` §8 and tech-spec §3.5 forbid. This leaks to item 020, whose step 5 says the same and which therefore also has no path to 015.
- **Suggested fix:** **AMEND item 014** `dependsOn` → `["010","011","015"]`. 020's path becomes transitive. Do not weaken step 5 — the no-duplication rule is spec-mandated.
- **Checklist:** CHECK-B18

### V-020: Item 029 (priority 1) depends on item 028 (priority 2)
- **Severity:** inconsistency
- **Location:** items 028, 029
- **Issue:** The only priority inversion in the backlog, found independently by two slices. Priority claims 028 is deferrable while the graph makes it mandatory and on the critical path to feature completion. A runner filtering or ranking by priority defers 028 and starves the terminal gate sweep.
- **Suggested fix:** **AMEND item 028** `"priority": 2` → `1`. Do not instead drop the `029 → 028` edge: the final sweep should run `bash scripts/validate.sh` after the last `eval/README.md` change. After this the backlog is uniformly priority 1 — intentional, since ordering is expressed entirely through `dependsOn`.
- **Checklist:** CHECK-B05, CHECK-B19

### V-021: Item 015 has no edge to item 009 despite the v4 `02 → 03` dependency declaration
- **Severity:** improvement
- **Location:** item 015, `dependsOn: ["010","011"]`; item 009 is a dangling leaf
- **Issue:** Item 009 implements `03` §5.2 — `_verify_status_warnings` accepting `auto-verify-pending`, `_next_command` routing a production-complete member with pending debt to `forge-verify`, and a deterministic obligation warning in `render_status`'s `warnings` array. Item 015 is the sole consumer of `render-status --json`, reading exactly that surface. With no edge, 015 can land first and pin expectations against a contract 009 then alters, forcing rework. Rework risk, not a blocker.
- **Suggested fix:** **AMEND item 015** `dependsOn` → `["009","010","011"]`. This also gives item 009 a consumer.
- **Checklist:** CHECK-B18, CHECK-B19

### V-022: The compliance chain has no edge into the converted branch skills
- **Severity:** improvement
- **Location:** items 025, 026, 027
- **Issue:** `01` §5 sequences step 6 (skill adoption, items 017–023) before step 7 (coverage/compliance, 024–027). Item 024 honours this; the 025→026→027 chain hangs off 013 alone. For 025/026 that is fine — their ground truth comes from executing the real `stage-exit` CLI. But item **027** registers the live `branch-path` probe against `skills/forge-verify/SKILL.md` and `skills/forge-fix/SKILL.md`; run before items 018/019 it scores *unconverted* canon, producing a misleading recorded baseline. Advisory harness, so not a blocker.
- **Suggested fix:** **AMEND item 027** `dependsOn` → `["018","019","025","026"]`. Leave 025 and 026 unchanged — adding edges there would serialize work unnecessarily.
- **Checklist:** CHECK-B19

---

## D. Acceptance-criteria quality

### V-023: 27 of 29 items accept `bash scripts/validate.sh passes` as test evidence, which v4 §8.2 says is insufficient
- **Severity:** gap
- **Location:** ACs of items 001–023, 025, 026, 028, 029; `07-testing-strategy.md` §8.2 and Verification checklist
- **Issue:** Confirmed at `scripts/validate.sh:210-218`: the pytest leg is conditional and non-fatal (`SKIP: pytest not installed … (non-fatal)`). v4 §8.2 makes this normative — "**a `SKIP` there is not a pass**" — and requires an explicit `python3 -m pytest tests -q` wherever the line is not `PASS`. No item encodes it; only items 024 and 027 name a pytest invocation at all, each for a single file. The sharpest cases are the items whose entire deliverable is test/eval code with the gate as their only execution evidence: **item 004** (type `test`, seven steps building the whole duplicate-key matrix — AC 9 is validate.sh, AC 10 is `ruff check scripts/ eval/`, which is *vacuous* since the item touches neither directory), **item 025**, and **item 026**. On an interpreter without pytest all three go green with zero tests executed.
- **Suggested fix:** Append to every item whose ACs contain `bash scripts/validate.sh passes`: `bash scripts/validate.sh output shows "PASS: epic-manifest pytest suite"; if it shows "SKIP: pytest not installed", python3 -m pytest tests -q was run explicitly and passed`. Give the test-bearing items targeted criteria in the shape 024/027 already use: item 004 → `python3 -m pytest tests/test_effective_config.py tests/test_forge_bootstrap.py tests/test_build_adapters.py passes` (replacing the vacuous ruff criterion); items 025/026 → `python3 -m pytest tests/test_compliance_eval.py passes`.
- **Checklist:** CHECK-B02, CHECK-B13, CHECK-B26

### V-024: Item 024's guard is vacuously satisfiable — the anti-hardcoding rule is missing
- **Severity:** gap
- **Location:** item 024 step 2, AC 1; `06-compliance-and-coverage.md` §2.1
- **Issue:** Item 024 asserts "`CANONICAL_EXIT_SITES` equals the nine `EXIT_STAGES` ids in order" but never says **where `EXIT_STAGES` comes from**. v4 §2.1 adds a paragraph specifically about this: obtain it by regex + `ast.literal_eval` per `tests/test_stage_constants_parity.py`, and "It **MUST NOT re-list the nine names in the test file**: a hardcoded copy is precisely the second hand-maintained allow-list REQ-GUARD-01 forbids, and it would make the equality assertion **vacuous** — the test would then be comparing the table against itself." Given the hyphenated, non-importable filename, hardcoding is the path of least resistance. This is the one item whose entire purpose is to be the mechanical guard for the other eight sites. Scan: `ast.literal_eval` and `spec_from_file_location` zero hits.
- **Suggested fix:** **AMEND item 024** step 2 with the sourcing rule and the explicit prohibition, and add the AC "the guard reads `EXIT_STAGES` from `scripts/forge-session.py` at runtime and contains no hardcoded list of the nine stage ids; editing `EXIT_STAGES` without editing `CANONICAL_EXIT_SITES` makes the test fail."
- **Checklist:** CHECK-B12, CHECK-B13, CHECK-B24

### V-025: Item 012's description step 6 has no acceptance criterion
- **Severity:** gap
- **Location:** item 012 step 6 vs ACs 1–11
- **Issue:** Step 6 reads "Also expose `autoVerifyEffective` and `invalidAutoVerifyKeys` in directives per `00` §4." None of the eleven ACs mention either key. This is the **only** description step in the backlog with zero AC coverage — it can be silently dropped and the item still passes its own gate.
- **Suggested fix:** **AMEND item 012** with two ACs: `directives.autoVerifyEffective` reports the per-stage effective value after `autoVerifyStages` overrides, not the raw config value; and an `autoVerifyStages` key naming no verify-capable stage appears in `directives.invalidAutoVerifyKeys` and produces the exact `00` §4 warning text, in sorted order, without failing the exit.
- **Checklist:** CHECK-B13

### V-026: The two exact warning templates `07` §3 asserts verbatim are not pinned by any item
- **Severity:** gap
- **Location:** items 016, 012; `02-stage-exit-routing.md` §9, `00-core-definitions.md` §4
- **Issue:** `02` §9 supplies the epic-member fallback warning as a normative literal with `{reason}` exactly one of four values, appended to `directives.warnings` as entry 1, and states "The template is normative — `07` §3 asserts this literal, not a paraphrase." Item 016 says only "emit a NAMED warning directive", and its AC 4's failure vocabulary ("Missing, corrupt, non-object, or unreadable") does not map onto the four normative reasons — there is no `corrupt` or `non-object` reason, and `not a member of this epic` is absent entirely. An implementation emitting a hand-worded warning with an invented reason satisfies AC 4 and fails the `07` §3 literal assertion. Item 012 has the same looseness for `invalidAutoVerifyKeys`.
- **Suggested fix:** **AMEND item 016** step 4 to quote the template verbatim, name `directives.warnings` entry 1, and enumerate the four `{reason}` values; replace AC 4 with the literal-asserting form. Align item **022** AC 5 ("surfaces the exact `02` §9 warning template"). **AMEND item 012** step 6 for the `invalidAutoVerifyKeys` template in sorted order.
- **Checklist:** CHECK-B08, CHECK-B13, CHECK-B22

### V-027: `score_branch_path`'s `RuntimeError` contract is not in item 027
- **Severity:** gap
- **Location:** item 027; `06-compliance-and-coverage.md` §5.1, §7
- **Issue:** v4 §5.1 specifies `RuntimeError` (not `KeyError`) for a malformed `expected_payload` and requires explicit key validation before indexing, because "an unguarded `KeyError` reaching `_to_result`/`run_branch_probe` is indistinguishable from an ordinary dict-access bug". Item 027 details the eight scorer keys but says nothing about the exception contract. Scan: `KeyError` zero hits; the two `RuntimeError` hits are item 025's fixture loader. Item 027's own AC "only harness defects exit non-zero" depends on this distinction.
- **Suggested fix:** **AMEND item 027** step 1 with the pre-index validation and `RuntimeError` contract, plus the AC "`score_branch_path` raises `RuntimeError`, not `KeyError`, for an `expected_payload` missing `directives`, `nextSteps`, `sentinel`, or `directives.primaryCommand`, and each case is covered offline."
- **Checklist:** CHECK-B22, CHECK-B24

### V-028: The `_load_config` stderr-unwritable case has no test row
- **Severity:** improvement
- **Location:** item 003 AC 5, item 004; `05-config-and-distribution.md` §3.1, §3.3
- **Issue:** Item 003 step 4 says "Rewrite `_load_config` … **exactly as `05` §3.1 shows**", which does reach the new `try/except OSError: pass` block — so this is not a hard gap. But item 003's AC 5 enumerates "missing, unreadable, malformed, scalar-root, array-root" without the stderr case, and item 004 — the test item owning the loader matrix — has no row or AC for it. The deliberate asymmetry between the session guard and bootstrap's propagation is exactly what a test matrix should pin.
- **Suggested fix:** **AMEND item 003** AC 5 to add "and a `warn_duplicate_keys` `OSError` (unwritable stderr) is swallowed so the read path still returns the parsed dict". **AMEND item 004** step 2 with the stderr-unwritable row covering both consumers' divergent policies, plus its AC.
- **Checklist:** CHECK-B24

### V-029: Item 005 does not require the `cmd_state_verify` docstring `00` §6 now specifies in full
- **Severity:** improvement
- **Location:** item 005; `00-core-definitions.md` §6
- **Issue:** v4 §6 gives the verb a complete `Args:` block for all nine parameters plus `Returns:`, and several entries carry normative content — `feature` is the *epic* name when `stage == "forge-0-epic"`; `status` defers authority to the `03` §3.3 matrix; `commit_hash` is "Full 40-hex only … abbreviations are rejected rather than expanded"; `Returns:` specifies the resolved target path so callers need not re-read state. Item 005 specifies signature and behavior but never the docstring, and the `Returns` contract is asserted in no AC.
- **Suggested fix:** **AMEND item 005** step 1 to carry the `00` §6 docstring verbatim, with the AC "`cmd_state_verify`'s `--json` result contains the written verify entry and the resolved target path, so a caller need not re-read state."
- **Checklist:** CHECK-B22

---

## E. Presentation and calibration

### V-030: The six core routing items never name `scripts/forge-session.py` as the file to modify
- **Severity:** improvement
- **Location:** items 011–016
- **Issue:** Items 001–010 and 017–029 all name their targets. Items 011–016 name only functions ("Extend `_next_steps_block`", "In `stage_exit`, compute…") and their test files, not the implementation file. Item 015 names a source file only negatively. The target is inferable — item 010 is a `dependsOn` for all six and states where `stage_exit` lives — so this does not block.
- **Suggested fix:** Add an explicit `Files: scripts/forge-session.py, tests/test_stage_exit.py` line (`tests/test_auto_verify.py` for 012) to each description, matching the convention items 001–010 already use.
- **Checklist:** CHECK-B14

### V-031: `estimatedIterations` is applied inconsistently
- **Severity:** improvement
- **Location:** items 017, 026 (=1) vs 010, 011, 013, 027 (=2)
- **Issue:** Only four items carry `2`, and the assignment tracks no consistent axis. Item **017** has the largest description in the backlog (404 words vs 251 for item 010, which got 2), rewrites the entire canonical contract across seven mandated sections, and is the verbatim source six items stamp from — estimated at 1. Item **026** (308 words) rewrites `parse_transcript` with id-based pairing, exit-code normalization, and a new subsequence matcher — estimated at 1, while item 027 at identical length got 2. `estimatedIterations` is real budget input (rauf's `computeMaxIterations` sums it; forge budgets `ceil(29 × 1.5) = 44` against a total estimate of 33), so systematic understatement quietly eats retry headroom rather than hard-failing.
- **Suggested fix:** Raise items **017** and **026** to `2`. Review 001, 023, 024 against the same bar; if left at 1, add a one-line `notes` sentence so the estimate reads as a decision rather than a default.
- **Checklist:** CHECK-B02

### V-032: Item 023 bundles two independent deliverables under one gate
- **Severity:** improvement
- **Location:** item 023
- **Issue:** Two unrelated changes across nine files under a single 11-criterion gate: (a) add `--verify-capability` + `--epic` to the four authoring skills' existing `stage-exit` invocations (ACs 1, 2, 10, 11), and (b) replace the PRD/tech parking-lot promise with immediate `state-note` calls plus the shared-conventions recipe (ACs 3–7). They share no code path. Item 024 depends on 023, so a stall in half (b) blocks a guard that only needs half (a). Largest item by file count after 020, at `estimatedIterations: 1`.
- **Suggested fix:** Optionally split into 023a (capability flags; what 024 actually needs) and 023b (`state-note` + shared-conventions recipe, `dependsOn: ["023a"]`), updating item 024's `dependsOn` to 023a. Weigh against churn: both halves edit the same two SKILL.md files. If left bundled, raise `estimatedIterations` to 2. **See User Decision D3.**
- **Checklist:** CHECK-B25

---

## Fix Execution Plan

### User Decisions Required

> **All three decisions were resolved by the user on 2026-07-30, each taking the recommended
> option. They are RESOLVED — apply the recommended path and do not re-ask.**
>
> - **D1 → Land the four `TypedDict`s as code** (amend item 001).
> - **D2 → New item 030** for the navigator, with `"030"` added to items 024 and 029.
> - **D3 → Leave item 023 bundled** and raise its `estimatedIterations` to 2.

**D1 (V-011) — are the `00` §4/§6 `TypedDict`s in scope as code, or documentation-only?**
*Recommended: land them as code* (amend item 001). `00`'s Public API declares them
"repository-internal, importable", and several carry normative invariants that otherwise live
nowhere in the repo. The alternative is a spec edit striking them from that list — a spec decision,
not a backlog one.

**D2 (V-001) — new item 030 for the navigator, or fold into item 023?**
*Recommended: new item 030.* The navigator is a distinct skill with its own read-side semantics and
a different dependency (`008`), and item 023 already spans four skills plus a shared-conventions
edit — and is itself a split candidate (V-032).

**D3 (V-032) — split item 023, or leave bundled?**
*Recommended: leave bundled and raise `estimatedIterations` to 2.* Both halves edit the same two
SKILL.md files, so splitting buys ordering clarity at the cost of two commits touching the same
files. Split only if item 024's readiness is judged more important than that churn.

Everything else is a direct amendment to `backlog.json`.

### Execution Steps

#### Step 1: Foundation item — derivation, types, and the directives surface
- **Files:** `backlog.json` (items 001, 010, 013)
- **Addresses:** V-011, V-013, V-008
- **Action:** Item 001 — replace "copy the literals verbatim" with the `get_args` derivation (adding the `typing` import), rewrite ACs 1–2, add the `VERIFY_MODE_TO_STAGE` parity assertion, and (per D1) add the four `00` §4/§6 `TypedDict`s with their verbatim field comments. Item 010 — add `verifyStage: str | None` and `warnings: list[str]` (fixed order) to the directives surface, noting `stageNoun` is **pre-existing** at `scripts/forge-session.py:1737` and retained verbatim, not added. Item 013 — extend AC 6's closed enumeration with `verifyStage`.
- **Depends on:** none (D1)

#### Step 2: The `state-verify` writer and the docs router
- **Files:** `backlog.json` (items 005, 015)
- **Addresses:** V-010, V-029, V-012, V-021
- **Action:** Item 005 — add `--findings-file` relative-and-contained validation to step 5 with its AC and `07` §4.2 negative rows; carry the `00` §6 docstring verbatim in step 1 with the `Returns` AC. Item 015 — replace step 2's invocation with sibling resolution + `sys.executable` + `timeout=10`; extend step 5's failure list and step 6's tests; replace AC 6 with the seven-mode form and add the resolution AC; set `dependsOn` → `["009","010","011"]`.
- **Depends on:** Step 1

#### Step 3: Shared protocol — ownership token, consent variant, warnings
- **Files:** `backlog.json` (items 017, 012, 016, 022)
- **Addresses:** V-007 (protocol half), V-009, V-008 (wording), V-025, V-026, V-014, V-031
- **Action:** Item 017 — add the `owner: nested`/`owner: direct` token contract with the absent-means-`direct` default; add the consent-variant subsection (two choices, `verifyGate` stays `none`) with its AC; change "surface `invalidAutoVerifyKeys` and `warning`" to `warnings`; set `"type": "feature"`; set `estimatedIterations: 2`. Item 012 — add the two ACs for step 6 and the exact `invalidAutoVerifyKeys` template in sorted order; set `dependsOn` → `["006","010","011"]`. Item 016 — quote the `02` §9 template verbatim with its four `{reason}` values as `warnings` entry 1; replace AC 4. Item 022 — align AC 5 to the exact template.
- **Depends on:** Step 2

#### Step 4: Branch skills — canon obligations and fence adjacency
- **Files:** `backlog.json` (items 018, 019, 023)
- **Addresses:** V-002, V-003, V-005, V-006, V-007 (skill half), V-017, V-032
- **Action:** Item 023 — add the `state-verify` verb-inventory registration to `references/shared-conventions.md` with its AC; add the consent-variant sentence to the capability recipe; add `"005"` to `dependsOn`; apply D3. Item 018 — add the `findings-template.md` §5.4 conversion, the R4-blockquote deletion, the `--epic` fence-adjacency requirement, and the `owner:` token read; `dependsOn` → `["005","006","007","013","017","023"]`. Item 019 — add the Step 5 write replacement, both freshness rewrites, the "Skip for now" reclassification, the fence-adjacency requirement, the `owner:` token read, and deletion of the retired inference precedent; `dependsOn` → `["005","007","013","017","023"]`.
- **Depends on:** Step 3

#### Step 5: Loop and docs — pre-flight parity
- **Files:** `backlog.json` (items 020, 021, 014)
- **Addresses:** V-004, V-015, V-019
- **Action:** Item 020 — add the `04` §6.4 Step 1b `auto-verify-pending` third case with its AC; name `## Optional flags catalog (Step 2d, rauf)` as the REQ-FOLLOW-01 replacement target and extend that AC; add `"008"` to `dependsOn`. Item 021 — add the `04` §7.2 backstop enumeration extension with its AC; add `"008"` to `dependsOn`. Item 014 — `dependsOn` → `["010","011","015"]`.
- **Depends on:** Step 4

#### Step 6: The navigator item
- **Files:** `backlog.json` (new item 030; items 024, 029)
- **Addresses:** V-001
- **Action:** Per D2, insert item 030 as specified in V-001 and add `"030"` to items 024 and 029 `dependsOn`.
- **Depends on:** Step 5 (D2)

#### Step 7: Test items and the terminal sweep
- **Files:** `backlog.json` (items 003, 004, 024, 026, 027, 028, 029)
- **Addresses:** V-024, V-027, V-028, V-006 (`MIN_CALL_SITES`), V-016, V-020, V-022, V-031
- **Action:** Item 024 — add the `EXIT_STAGES` regex + `ast.literal_eval` convention and the no-hardcoded-list AC. Item 027 — add the `RuntimeError`/pre-index-validation step and AC; `dependsOn` → `["018","019","025","026"]`. Item 003 — extend AC 5 with the swallowed-`OSError` case. Item 004 — add the stderr-unwritable row and AC. Item 026 — `estimatedIterations: 2`. Item 028 — `"priority": 1`. Item 029 — add the `MIN_CALL_SITES` raise to the sweep; `dependsOn` → `["004","007","009","024","028","030"]`.
- **Depends on:** Step 6

#### Step 8: The cross-cutting acceptance-criterion sweep
- **Files:** `backlog.json` (all items carrying `bash scripts/validate.sh passes`)
- **Addresses:** V-023, V-030
- **Action:** Append the `PASS: epic-manifest pytest suite` criterion to every item whose ACs contain `bash scripts/validate.sh passes`; give items 004, 025, 026 their targeted pytest criteria and replace item 004's vacuous ruff criterion. Add the `Files:` line to items 011–016. Apply last, so it covers items added or amended in Steps 1–7.
- **Depends on:** Steps 1–7

#### Step 9: Re-validate and re-stamp
- **Files:** `backlog.json`, `.pipeline-state.json`
- **Action:** Re-run `rauf-stable backlog validate . --backlog specs/stage-exit-coverage --specs-dir specs/stage-exit-coverage --json` and confirm `{"valid": true, "findings": []}`. Confirm three properties the runner does not check: the graph is still acyclic (the new `014 → 015` edge is safe — 015's closure contains no path back to 014); no dependency carries a numerically larger `priority` than its dependent; and item 029's transitive closure now contains every other item id. Then bump `forge-4-backlog`'s `version` to 3 with `basedOnVersions.forge-3-specs = 4` via `state-complete`, clearing the `stale` status so the freshness ledger reflects the amended backlog.
- **Depends on:** Step 8

## Fix Progress

- Step 1: [APPLIED] 2026-07-30 — item 001 switched to `get_args` derivation with the `VERIFY_MODE_TO_STAGE` parity AC (V-013) and given the four `00` §4/§6 `TypedDict`s per D1 (V-011); item 010 given `verifyStage` and `warnings: list[str]`, with `stageNoun` explicitly marked pre-existing and retained (V-008); item 013 AC 6 extended with `verifyStage`.
- Step 2: [APPLIED] 2026-07-30 — item 005 given `--findings-file` containment validation and the verbatim `00` §6 docstring (V-010, V-029); item 015's banned `<bundle-root>` invocation replaced with sibling resolution + `sys.executable` + `timeout=10`, AC 6 rewritten to seven failure modes, `dependsOn` → 009,010,011 (V-012, V-021).
- Step 3: [APPLIED] 2026-07-30 — item 017 retyped `feature`, estimate 2, given the ownership-token and consent-variant contracts and the `warnings`-is-a-list correction (V-014, V-007, V-009, V-008, V-031); item 012 given the two step-6 ACs, the exact `invalidAutoVerifyKeys` template, and `dependsOn` → 006,010,011 (V-025, V-026, V-018); item 016 given the verbatim `02` §9 template with its four reasons (V-026); item 022 AC aligned.
- Step 4: [APPLIED] 2026-07-30 — item 023 given the `shared-conventions.md` `state-verify` registration, the consent-variant mirror, the fence-adjacency rule, estimate 2, `dependsOn` +005 (V-002, V-006, V-032/D3); item 018 given the `findings-template.md` conversion, the R4-blockquote deletion, the owner token, and the fence rule, `dependsOn` +006,007,023 (V-003, V-005, V-006, V-007, V-017); item 019 given the Step 5 replacement, both freshness rewrites, the "Skip for now" reclassification, the retired-inference deletion, the owner token, and the fence rule, `dependsOn` +007,023 (V-005, V-006, V-007, V-017).
- Step 5: [APPLIED] 2026-07-30 — item 020 given the `04` §6.4 Step 1b third case and the named REQ-FOLLOW-01 pointer, `dependsOn` +008 (V-004, V-015); item 021 given the `04` §7.2 backstop extension, `dependsOn` +008 (V-004); item 014 `dependsOn` +015 (V-019).
- Step 6: [APPLIED] 2026-07-30 — item **030** added for the navigator per D2, `dependsOn` 008,017; added to items 024 and 029 (V-001).
- Step 7: [APPLIED] 2026-07-30 — item 024 given the `EXIT_STAGES` regex + `ast.literal_eval` convention and the no-hardcoded-list AC (V-024); item 027 given the `RuntimeError` contract, `dependsOn` → 018,019,025,026 (V-027, V-022); item 003 AC 5 extended and item 004 given the stderr-unwritable row (V-028); item 026 estimate 2, item 028 priority 1 (V-031, V-020); item 029 given the `MIN_CALL_SITES` raise and `dependsOn` → 004,007,009,024,028,030 (V-006, V-016).
- Step 8: [APPLIED] 2026-07-30 — the `PASS: epic-manifest pytest suite` criterion added to all 30 items; item 004's vacuous `ruff check scripts/ eval/` criterion replaced with a targeted pytest run; items 025/026 given targeted pytest criteria; `Files:` lines added to items 011–016 (V-023, V-030).
- Step 9: [APPLIED] 2026-07-30 — `rauf backlog validate` → `{"valid": true, "findings": []}`. Graph properties confirmed beyond the runner: 30 items (001–030), all `dependsOn` resolve, **acyclic**, **no priority inversions** (uniform priority 1), single root (001), and item **029's transitive closure covers all 29 other items**. Types: 25 feature / 2 chore / 2 test / 1 bugfix. Total `estimatedIterations` 37.
