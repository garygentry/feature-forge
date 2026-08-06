# 03 — Outcome Vocabulary & Truthful Attribution

> The `resolved` loop outcome and dependency-starvation attribution. This document
> owns the **enum-to-report** slice of `loop-recovery`: the new `resolved` value and
> its route/text/ladder wiring (REQ-OUT), the truthful pending attribution that
> replaces the hardcoded "(iteration limit reached)" with a `selectable`-driven
> conditional (REQ-ATTR), the `stage-exit --cause dependency-starvation` extension,
> and the deliberate ripple into the stage-exit directive matrix (REQ-COMPAT).
>
> It builds directly on `00-core-definitions.md` §5 (the vocabulary contract) and §8
> (the `backlog-topology` output that supplies `selectable` and the blocking roots).
> It does **not** re-derive the enum change, the schema, or the topology verb — those
> are defined once in `00` and referenced here. It does **not** author the recovery
> procedure that *selects* `resolved` (that is `05-recovery-procedure.md`) nor the
> topology/clustering verb internals (`06-clustering-and-topology.md`); it consumes
> both.

## Requirement Coverage

| REQ ID | Requirement | Section |
|--------|-------------|---------|
| REQ-OUT-01 | Vocabulary expresses "decision made and applied" | §2.1 (the `resolved` value + text) |
| REQ-OUT-02 | `resolved` routes **resume**, not recover | §2.2 (route table), §2.3 (`_loop_route`) |
| REQ-OUT-03 | `resolved` gated on decision/tree/per-item preconditions | §3 (the procedural gate) |
| REQ-ATTR-01 | `selectable` computed from authoritative counts | §5.1 (`selectable` source) |
| REQ-ATTR-02 | Starvation named (roots + gated-subtree size), not the limit | §5.2 (starvation render) |
| REQ-ATTR-03 | No surface attributes a cause the counters contradict | §6 (conditional "(iteration limit reached)") |
| REQ-ATTR-04 | Starvation = cause annotation, not an enum value | §5 (annotation rationale) |
| REQ-COMPAT-01 | Vocabulary/routing ripple into the directive matrix deliberately | §4 (ladder two-place edit), §7 (matrix + tests) |
| REQ-COMPAT-02 | Clean-tree happy path adds no new prompt from this doc | §8 (compat note) |
| REQ-OBS-01 | The pending/starvation template cites its authoritative counts | §5.2, §6 (citation basis) |

---

## 1. Scope & Dependencies

**Owns.** The `resolved` route/text rows in `scripts/forge-session.py`; the `resolved`
rung in the Step 7 ladder (both canonical copies); the starvation-conditional pending
template and the starved next-steps note in `result-reporting.md`; the
`stage-exit --cause` argparse option, its validation, and its text swap; the
`stage-exit-protocol.md:50` directive-matrix row; and the description of the resulting
test ripple in `test_stage_exit.py` / `test_stage_exit_protocol.py` (the tests
themselves are authored per `07-testing-strategy.md`).

**Consumes (does not define):**

- `00-core-definitions.md` §5.1 — `LoopOutcome += "resolved"` and the derived
  `EXIT_OUTCOMES["forge-5-loop"]`. This doc **references** that single edit point; it
  never re-lists the enum. §5.2/§5.3 already fix the *contract* (route = resume, ladder
  first, no Step-4b template, starvation = annotation); this doc supplies the concrete
  Python and prose that realize it.
- `00-core-definitions.md` §8 — the `backlog-topology` verb output
  (`selectable`, `starvation.blockingRoots[].{id,gatedCount}`, `maxChainDepth`). This
  doc reads those fields; `06-clustering-and-topology.md` owns the verb.
- `00-core-definitions.md` §9 — the citation-basis contract that binds §5.2 and §6.

**Depended on by:** `05-recovery-procedure.md` (selects `resolved` and evaluates the §3
gate), `07-testing-strategy.md` (authors the §7 test ripple + the eval probe).

**Delivery position (`01-architecture-layout.md` §4):** OUT then ATTR — both after DEC
(`02`) and the rauf apply surface (`04`), because the ladder edit is forced by the
directive-matrix test only once `LoopOutcome` carries `resolved`.

## 2. The `resolved` outcome (REQ-OUT-01, REQ-OUT-02)

### 2.1 Why it exists, and its rendered text

`resolved` is the vocabulary answer to issue #189: the agent collected a needs-human
decision, applied it, and proved the affected items ran again — but the only outcomes
available were `needs-human` ("decisions still outstanding", routes to the navigator)
and `complete` ("every item done", claims downstream readiness). Neither is true after a
successful recovery. `resolved` names exactly that state: *a needs-human stop that was
subsequently resolved* — recorded, applied, per-item-verified-unblocked, tree clean —
and, like `partial`/`deferred`, resumable with **nothing downstream ready**.

The enum value itself is added once in `00` §5.1
(`LoopOutcome = Literal[..., "deferred", "resolved"]`); `EXIT_OUTCOMES["forge-5-loop"]`
derives it automatically. This document adds only the **route** and **text** rows.

The new `_LOOP_OUTCOME_TEXT` entry (author it here, matching the tone of the existing
`partial`/`deferred` sentences at `forge-session.py:2964` — three clauses: what
happened, nothing-downstream-is-ready, the fenced resume action):

```python
_LOOP_OUTCOME_TEXT: Final[dict[str, str]] = {
    # ... existing partial / deferred / blocked / needs-human rows unchanged ...
    "resolved": (
        "The needs-human stop for {feature} was resolved — the recorded decisions "
        "were applied and every affected item was verified, per item, to have left "
        "blocked/needsHuman, with the working tree clean. The recorded state is "
        "resumable and nothing downstream is ready: run the loop again below to "
        "continue from where it stopped."
    ),
}
```

Rationale for the wording, traced to requirements:

- "the recorded decisions were applied" — REQ-OUT-03 precondition (a) + REQ-DEC apply.
- "verified, per item, to have left blocked/needsHuman" — REQ-OUT-03 precondition (c),
  the REQ-UNB-02 per-item test (never aggregate counts).
- "the working tree clean" — REQ-OUT-03 precondition (b).
- "nothing downstream is ready" — the non-complete invariant enforced by
  `test_no_non_complete_loop_outcome_claims_downstream_readiness` (§4); no other
  non-complete sentence may imply docs can start, and neither may this one.
- "run the loop again below" — REQ-OUT-02: the fenced action is the loop resume, not the
  navigator.

### 2.2 Route table: `resolved` is a **resume** (REQ-OUT-02)

The one route row, added to `_LOOP_ROUTE_KIND` (`forge-session.py:2952`):

```python
_LOOP_ROUTE_KIND: Final[dict[str, str]] = {
    "complete": "handoff",
    "partial": "resume",
    "deferred": "resume",
    "resolved": "resume",   # REQ-OUT-02 — fences /feature-forge:forge-5-loop {feature}
    "blocked": "recover",
    "needs-human": "recover",
}
```

`resume` (not `recover`) is the whole point of REQ-OUT-02: a resolved stop must fence
the relaunch command `/feature-forge:forge-5-loop {feature}`, exactly like
`partial`/`deferred`, and must **never** point at the navigator
(`/feature-forge:forge {feature}`), whose text — "see the live pipeline state from disk
and recover" — directly contradicts what just happened (the recovery already ran and
succeeded). This is issue #189's core defect: closing a successful recovery by telling
the operator to go re-derive state from disk.

### 2.3 No structural change to `_loop_route()`

`_loop_route()` (`forge-session.py:3117`) already dispatches purely on
`_LOOP_ROUTE_KIND[outcome]`:

```python
kind = _LOOP_ROUTE_KIND[outcome]
if kind != "handoff":
    primary = (
        f"/feature-forge:forge-5-loop {feature}"
        if kind == "resume"
        else f"/feature-forge:forge {feature}"
    )
    return primary, None, _LOOP_OUTCOME_TEXT[outcome].format(feature=feature), False
```

A `resume`-kinded `resolved` therefore flows through the existing non-handoff branch
with **no** new code: it takes the resume `primary`, its `_LOOP_OUTCOME_TEXT["resolved"]`
sentence, and `advancing=False` (no `nextStage`). The **only** function-body edit in
`_loop_route()` for this document is the `--cause` text swap in §5.3 — and that is a
one-line conditional, not a new branch. Confirmed against source: the dispatcher keys on
the route table alone, so adding a table row is sufficient for routing.

### 2.4 `resolved` joins the non-complete bucket

`resolved` is **not** `complete`. It must carry no `nextStage`, no `nextCommand`, no
`runInStageVerify`, no owed auto-verify debt, and no downstream-readiness claim — the
same suppression `partial`/`deferred`/`blocked`/`needs-human` already get, enforced by
`test_no_non_complete_loop_outcome_claims_downstream_readiness` and
`test_a_non_complete_loop_outcome_states_nothing_downstream_is_ready`
(`test_stage_exit.py`). Because `NON_COMPLETE_LOOP_OUTCOMES` is **derived**
(`tuple(o for o in LOOP_OUTCOMES if o != "complete")`, `test_stage_exit.py:2305`), it
picks `resolved` up automatically once `EXIT_OUTCOMES` mirrors the enum — the invariant
tests then parametrize over it with no per-test edit. See §7 for the full ripple.

## 3. The `resolved` gate (REQ-OUT-03)

`resolved` is **selected procedurally** by the Post-Run Recovery Procedure
(`05-recovery-procedure.md`), never asserted by `stage-exit`. `stage-exit` has no runner
access — it cannot re-read the backlog, run `git status`, or enumerate decision
records — so it **cannot** and **does not** re-verify the gate server-side. This is a
deliberate, recorded decision (OTQ-1 in tech-spec §10): enforcement is **procedural**
(the recovery procedure evaluates the gate before it passes `--outcome resolved`),
**eval-measured** (the `loop-outcome` fixture, `07`, asserts the route emits its
sentinel), and **directive-matrix-tested** (§7). Server-side gate verification — e.g. a
future `--evidence` counts payload — is explicitly deferred.

The gate is the conjunction of **all three** conditions, evaluated by the recovery
procedure (`05`), each citing its authoritative source per `00` §9:

| # | Condition | How the procedure checks it | Source |
|---|-----------|-----------------------------|--------|
| (a) | Every recorded needs-human item has an **applied** decision | `decision-list --unapplied` returns empty **for the affected items** | `02` §5.1 |
| (b) | The working tree is **clean** | `git status --porcelain` is empty | git |
| (c) | Every affected item **left** `blocked`/`needsHuman` | the per-item `listCommand` re-read (REQ-UNB-02) — `status != "blocked"` for each affected id | `04` |

Condition (b) holds **by construction** for the decision record itself: the record lives
at `{backlogDir}/{stateDir}/forge-decisions.json`, git-ignored under `**/.rauf/*`
(`00` §3, REQ-DEC-01), so `git status --porcelain` never lists it. A clean tree can
therefore coexist with a freshly written decision record — the untracked-artifact
exclusion in REQ-OUT-03 is satisfied without any special-casing in the porcelain check.

Any single condition failing means the recovery did not fully succeed, and the ladder
(§4) falls through past `resolved` to `needs-human`/`blocked` as today — a partial
unblock (some affected items still `blocked`) is a **failed recovery** (REQ-UNB-03,
owned by `04`), never a `resolved`. Claiming `resolved` without all three is a defect
(REQ-OUT-03).

## 4. Ladder position & the two-place edit (REQ-COMPAT-01)

### 4.1 New ladder order

`resolved` is evaluated **first**, ahead of `needs-human`:

```
resolved → needs-human → blocked → deferred → partial → complete
```

First-match-wins, as today. `resolved` leads because it is gated (§3) on "the recovery
procedure ran **this session** and its gate passed": a stop the recovery just cleared
must not re-trigger the `needs-human` rung its own recovery resolved. If the gate did
not pass, `resolved` does not match and evaluation continues down the existing ladder
unchanged. This ordering is a superset of today's ladder — no existing rung's condition
or precedence changes.

### 4.2 The ladder lives in two canonical places — both change

The ladder text is duplicated, and both copies **must** move in lockstep:

1. **Body copy — `skills/forge-5-loop/SKILL.md:271`.** Step 7's inline ladder currently
   reads:
   > First select the single `LoopOutcome` with the ladder in
   > `references/result-reporting.md` (`needs-human` → `blocked` → `deferred` →
   > `partial` → `complete`, first match wins) …

   becomes:
   > First select the single `LoopOutcome` with the ladder in
   > `references/result-reporting.md` (`resolved` → `needs-human` → `blocked` →
   > `deferred` → `partial` → `complete`, first match wins) …

   This edit is **mandatory, not optional prose**: `test_stage_exit_protocol.py:379-388`
   reads the canon-derived outcome domain (`_exit_outcomes().get("forge-5-loop")`) and
   asserts that **every** member appears as a backtick token (`` `{outcome}` ``) in the
   loop skill's exit surface — "outcome `{outcome!r}` has no documented selection rule".
   Once `LoopOutcome` gains `resolved`, that guard fails until `` `resolved` `` appears
   in the SKILL body. The ladder line is where it lands (it is the documented selection
   rule). This is REQ-COMPAT-01 in miniature: a vocabulary change forces a deliberate
   body edit, and the test is what makes the coupling visible rather than silent.

2. **Rung definitions — `skills/forge-5-loop/references/result-reporting.md`.** The
   numbered "Selecting the one `LoopOutcome`" list (currently rungs 1–5) gains a new
   first rung:
   > 0. **`resolved`** — the Post-Run Recovery Procedure
   >    (`references/recovery-procedure.md`) ran this session and its gate passed: every
   >    affected needs-human item has an applied decision record, the working tree is
   >    clean, and each affected item left `blocked`/`needsHuman` per the per-item
   >    re-read. This outranks `needs-human` so a stop the recovery just cleared is not
   >    re-reported as still needing a human.

   (Renumber the existing rungs, or lead with `resolved` and keep the "first match wins"
   framing — the numbering is prose, the order is load-bearing.)

The two-place consistency is a Verification checklist item (§9): the SKILL body ladder
and the `result-reporting.md` rung order must list the same six values in the same order.

### 4.3 `resolved` gains **no** Step-4b result template

`SKILL.md:232` describes "The **five** verbatim result-report output templates —
**all-done**, **needs-human**, **blocked**, **deferred**, and **pending** (…)". That
count stays **five** — deliberately. Step 4b templates describe **run results read from
the runner's counts** (done/blocked/needsHuman/deferred/pending). `resolved` is not a
count-derived run result: it is **asserted by the recovery procedure** whose own report
(`05` step 6 / §3.9 citation basis) is the reporting surface for a resolved recovery.
Adding a sixth Step-4b template would imply the loop's own count read can conclude
`resolved`, which it cannot — the gate (§3) needs the recovery procedure's decision-list
and per-item re-read, not the Step 4a tally. So `SKILL.md:232`'s "five" is unchanged and
this is not an omission. (`07` asserts the template count did not drift.)

## 5. Starvation as a cause annotation, not an enum value (REQ-ATTR-04)

### 5.1 Why an annotation, and what `selectable` is

Per `00` §5.1 and OQ-1, dependency starvation is **not** a new `LoopOutcome` value. A
`partial-starved` value would route **identically** to `partial` (both resume, `00`
§5.3) — it would buy only different next-steps text at the cost of doubling the
enum/routing/test/eval ripple (a new `EXIT_OUTCOMES` member, a new route row, a new text
row, new parametrized routing tests, a new eval probe branch). The truthful-attribution
requirement (REQ-ATTR-04 leaves the encoding to the tech spec) is met more cheaply by a
**cause annotation** on the existing `partial` outcome: a `--cause` flag (§5.3) and a
conditional report template (§6).

`selectable` (REQ-ATTR-01) is defined once in `00` §8 as a `backlog-topology` output
field: **pending items whose `dependsOn` are all `done`**, computed by the verb over the
runner's `listCommand` JSON (never off-disk `backlog.json` — single data source,
`00` §8). This document **reads** `selectable`; `06-clustering-and-topology.md` owns its
computation. Because it comes from the runner's authoritative item array, every claim
derived from it cites authoritative counts (REQ-OBS-01, `00` §9).

### 5.2 The starvation render condition (REQ-ATTR-02, REQ-OBS-01)

Dependency starvation is rendered — in place of the iteration-limit attribution — when
**all three** hold, read from the runner's status and the topology verb:

```
selectable == 0  AND  pending > 0  AND  iterationsUsed < iterationsGranted
```

where `iterationsUsed`/`iterationsGranted` are `iteration`/`maxIterations` from
`{stateDir}/state.json`. The three-way test is exactly issue #190's fingerprint: work
remains (`pending > 0`), the budget was **not** the constraint
(`iterationsUsed < iterationsGranted`), and nothing was runnable
(`selectable == 0`) — so attributing the pending items to the iteration limit is a lie
the counters contradict.

When it fires, the report names the **blocking roots and each root's gated-subtree
size** — sourced from `backlog-topology`'s `starvation.blockingRoots[].{id, gatedCount}`
(`00` §8) — instead of "(iteration limit reached)":

```
Loop stopped for {feature} with {pending} item(s) still pending, but the iteration
limit was NOT the constraint ({iterationsUsed}/{iterationsGranted} iterations used).
No pending item was selectable — every one is gated behind unblocked roots:
  - {rootId}: {rootTitle} — gates {gatedCount}/{itemCount} items
  - {rootId}: {rootTitle} — gates {gatedCount}/{itemCount} items
Unblock these roots (their subtrees free up on the next run), then run the loop again.
```

**Citation basis (REQ-OBS-01, `00` §9 row 1):** this template derives its claims from
`backlogSummary` counts (`pending`) + `backlog-topology` output (`selectable`,
`blockingRoots`, `gatedCount`, `itemCount`) + the iteration counters from `state.json`.
The `recovery-procedure.md` / `result-reporting.md` prose carries this obligation
verbatim — a claim any of those sources contradicts is a reportable defect.

### 5.3 `stage-exit --cause dependency-starvation` (tech-spec §5.3)

When the report renders starvation (§5.2), the loop stage closes with
`--cause dependency-starvation` so the fenced next-steps sentence names the unblock path
rather than the (false) iteration-limit resume framing.

**Validity: forge-5-loop / partial ONLY.** The flag is accepted **only** with
`--stage forge-5-loop --outcome partial`; any other stage or outcome exits 2 **before
any payload is emitted** (fail-closed, no sentinel — mirrors the existing
outcome-domain validation at `stage_exit`'s deterministic validation block,
`forge-session.py:3453+`).

**Argparse addition** (`forge-session.py`, in the `stage-exit` parser at `:5653`,
alongside `--outcome`):

```python
p_exit.add_argument(
    "--cause", default=None, dest="cause", choices=("dependency-starvation",),
    help="Pending-attribution cause; valid only with "
         "--stage forge-5-loop --outcome partial",
)
```

**Validation** (in `stage_exit()`, immediately after the outcome-domain check at
`forge-session.py:3481`, so it runs before routing and before any output):

```python
# --cause is a forge-5-loop/partial-only attribution annotation (REQ-ATTR-04).
# argparse `choices` already restricts the value; this restricts the combination.
if cause is not None and not (stage == "forge-5-loop" and outcome == "partial"):
    raise UsageError(
        "--cause dependency-starvation is valid only with "
        "--stage forge-5-loop --outcome partial"
    )
```

**Plumbing.** `cause` threads through the same path as `outcome`:

- add a `cause: str | None = None` parameter to `stage_exit()`
  (`forge-session.py:3324`), positioned after `verify_capability` (keyword-defaulted so
  no existing caller breaks);
- pass `args.cause` in the dispatch tail (`forge-session.py:5893`) as the new final
  argument;
- pass `cause` from `stage_exit()` into `_loop_route()` (add a
  `cause: str | None = None` parameter there too).

**Text swap** (`_loop_route()`, `forge-session.py:3174`). Add a sibling constant and
select it when the annotation is present:

```python
#: The starvation variant of the `partial` next-steps sentence (REQ-ATTR-02): names the
#: unblock path instead of the iteration limit, which was NOT the binding constraint.
_LOOP_PARTIAL_STARVED_TEXT: Final[str] = (
    "The loop stopped for {feature} with backlog items still pending, but the "
    "iteration limit was NOT the constraint — no pending item was selectable because "
    "unblocked root items gate the rest of the backlog. The recorded state is "
    "resumable and nothing downstream is ready: unblock the roots named in the "
    "starvation report above, then run the loop again below to continue."
)
```

and in the non-handoff branch of `_loop_route()`:

```python
if outcome == "partial" and cause == "dependency-starvation":
    text = _LOOP_PARTIAL_STARVED_TEXT.format(feature=feature)
else:
    text = _LOOP_OUTCOME_TEXT[outcome].format(feature=feature)
return primary, None, text, False
```

Absent `--cause`, `partial` renders today's `_LOOP_OUTCOME_TEXT["partial"]` sentence
verbatim — no behavioral change to any existing exit.

## 6. Conditional "(iteration limit reached)" (REQ-ATTR-03, REQ-OBS-01)

Three canonical literals hardcode "(iteration limit reached)" today and each becomes
conditional (REQ-ATTR-03: no surface may attribute a cause the iteration counters
contradict):

| Occurrence | File:line | Today | Becomes |
|---|---|---|---|
| Pending template header | `result-reporting.md:67` | `**Some items still pending (iteration limit reached):**` | header renders `({cause})` — see below |
| Pending template body | `result-reporting.md:71` | `Pending:   {pending} items (iteration limit reached)` | body renders `({cause})` — see below |
| Step-4b template list | `SKILL.md:232` | `**pending** (iteration limit reached)` | `**pending** (with a conditional cause)` |

**The render rule.** The parenthetical cause is chosen, not hardcoded:

- Render **"(iteration limit reached)"** only when `iteration == maxIterations` (the
  limit was genuinely the binding constraint) **AND** `selectable > 0` (there was
  runnable work the budget cut off).
- Otherwise — i.e. the §5.2 starvation condition
  (`selectable == 0 && pending > 0 && iterationsUsed < iterationsGranted`) — render the
  **starvation line** (§5.2) naming the blocking roots and gated-subtree sizes, and
  close the stage with `--cause dependency-starvation` (§5.3).

The pending template in `result-reporting.md` is rewritten to carry this rule inline
(prose, not a hardcoded parenthetical). Illustrative rewrite:

```
**Some items still pending:**  (render the cause per the rule below)
```
Loop completed for {feature}.
  Completed: {done}/{total}
  Pending:   {pending} items ({cause})
  Blocked:   {blocked} items
```
`{cause}` = "iteration limit reached" only when `iteration == maxIterations` AND
`selectable > 0` (cite `state.json` iteration counters + `backlog-topology.selectable`);
otherwise render the dependency-starvation line from §5.2 instead of this parenthetical
and close with `--cause dependency-starvation`.
```

**Citation basis (REQ-OBS-01).** Both branches cite authoritative counts: the
iteration-limit branch cites `state.json`'s `iteration`/`maxIterations`; the starvation
branch cites `backlogSummary` + `backlog-topology` (`00` §9 row 1). The template must
name the source it derived the cause from; a `{cause}` a counter contradicts (e.g.
"iteration limit reached" when `iteration < maxIterations`) is a reportable defect
(REQ-ATTR-03, generalized by REQ-OBS-01).

The `SKILL.md:232` edit is **in-line, zero net line growth** (the parenthetical text
changes, the sentence stays one line) — required by the body-cap budget
(`01` §5: forge-5-loop is at ≈293/300 after this feature's other edits).

## 7. Directive-matrix ripple & test coverage (REQ-COMPAT-01)

### 7.1 The directive matrix (`stage-exit-protocol.md:50`)

The loop outcome-domain row in the stage-exit directive matrix is a documented guard,
and it is **deliberately** widened (REQ-COMPAT-01 — guard *updates* are expected and in
scope; silent guard *weakening* is not). Row `:50` today:

> | `forge-5-loop` | `forge-5-loop` | `--outcome` — one of `complete`, `partial`, `blocked`, `needs-human`, `deferred` |

becomes:

> | `forge-5-loop` | `forge-5-loop` | `--outcome` — one of `complete`, `partial`, `blocked`, `needs-human`, `deferred`, `resolved`; optional `--cause dependency-starvation` with `--outcome partial` |

This is a widening (a new legal value + a new optional constrained flag), not a
loosening: every previously rejected combination stays rejected (the `--cause` validity
matrix in §5.3 exits 2 for any non-`partial` outcome or non-loop stage). The row change
keeps the human-readable matrix in sync with `EXIT_OUTCOMES`, which
`test_stage_exit_protocol.py` cross-checks against canon.

### 7.2 The test ripple (authored per `07`)

This document **describes** the ripple; `07-testing-strategy.md` authors/edits the tests.
Because the outcome domain is **derived** from `LoopOutcome`, most of the ripple is
automatic once `EXIT_OUTCOMES["forge-5-loop"]` mirrors the enum:

- **`test_stage_exit.py:626`** — the mirrored `EXIT_OUTCOMES["forge-5-loop"]` literal
  tuple gains `"resolved"` (the one hand-maintained mirror of the derived canon set).
  This automatically extends `LOOP_OUTCOMES` (`:2304`) and the derived
  `NON_COMPLETE_LOOP_OUTCOMES` (`:2305`), so
  `test_no_non_complete_loop_outcome_claims_downstream_readiness` (`:2372`) and
  `test_a_non_complete_loop_outcome_states_nothing_downstream_is_ready` (`:2473`) now
  parametrize over `resolved` with **no per-test edit** — it inherits the
  nothing-downstream-ready invariant (§2.4).
- **Resume routing** — the hand-listed resume-fence parametrize
  (`test_loop_partial_and_deferred_fence_the_loop_resume`, `:2348`) gains a `resolved`
  case (or a sibling test): `resolved` fences `LOOP_RESUME`
  (`/feature-forge:forge-5-loop widget`). The recover-fence parametrize
  (`test_loop_blocked_and_needs_human_fence_the_navigator`, `:2358`) deliberately does
  **not** gain `resolved` — asserting, by omission, that `resolved` does not route to
  the navigator (REQ-OUT-02).
- **`--cause` validity matrix** — new cases: `--cause dependency-starvation` accepted
  with `forge-5-loop`/`partial` (payload renders the starved sentence); exit 2 for
  `--cause` with any other outcome (`complete`/`blocked`/`needs-human`/`deferred`/
  `resolved`) or any non-loop stage. This is REQ-COMPAT-01's "deliberate guard update,
  no silent weakening" made executable.
- **`test_stage_exit_protocol.py`** — **no code change**; its canon-derived
  outcome-domain assertion (`:379-388`) is precisely what **forces** the `SKILL.md:271`
  ladder edit (§4.2). If the body edit is missed, this test fails with "outcome
  'resolved' has no documented selection rule" — the intended coupling.

## 8. Compatibility (REQ-COMPAT-02)

A run that never enters `needs-human`/`blocked` produces **no** `resolved` outcome (the
§3 gate is only ever evaluated by the recovery procedure, which only runs when there is
something to recover) and **no** new prompt from this document. The `--cause` annotation
only appears on a `partial` run that is *already* starved — it changes the closing
sentence's wording, never adds a prompt or a required operator decision. The only new
happy-path **output** in this feature is the Step 2a max-chain-depth line, owned by
`06-clustering-and-topology.md` (REQ-TOPO-03) — not this document. This document's
surfaces (`resolved` text, starvation text, conditional pending template) render **only**
on the non-clean-tree / non-complete paths they attribute. SC-4's clean-tree baseline
equivalence (PRD §8) therefore holds against everything this doc adds.

## Dependencies

- **`00-core-definitions.md`** — §5 (the `LoopOutcome += "resolved"` single edit point,
  the route=resume / ladder-first / no-Step-4b-template / starvation-is-annotation
  contract), §8 (`backlog-topology` output: `selectable`,
  `starvation.blockingRoots`, `maxChainDepth`), §9 (citation-basis contract), §10
  (the `_LOOP_ROUTE_KIND`/`_LOOP_OUTCOME_TEXT`/`_loop_route` helper contracts). **Must
  be implemented first** — the enum value and topology verb are prerequisites.
- **`04` (apply mechanism)** — the per-item re-read that condition (c) of the §3 gate
  depends on. Sequenced before OUT in `01` §4.
- **`06-clustering-and-topology.md`** — owns the `backlog-topology` verb and
  `compute_topology()` that produce `selectable` and `blockingRoots`; this doc reads
  their output.

Consumed by **`05-recovery-procedure.md`** (selects `resolved`, evaluates the §3 gate,
decides when to render starvation and pass `--cause`) and **`07-testing-strategy.md`**
(authors the §7 test ripple and the `loop-outcome` compliance probe).

## Verification

An implementation matches this document when:

- [ ] `_LOOP_ROUTE_KIND["resolved"] == "resume"`; `stage-exit --stage forge-5-loop
      --outcome resolved` fences `/feature-forge:forge-5-loop {feature}` and never
      `/feature-forge:forge {feature}`.
- [ ] `_LOOP_OUTCOME_TEXT["resolved"]` renders the §2.1 sentence (recorded+applied,
      per-item verified, tree clean, resumable, nothing downstream ready) and appears in
      the payload for `--outcome resolved`.
- [ ] `resolved` carries no `nextStage`/`nextCommand`/`runInStageVerify` and makes no
      downstream-readiness claim — the derived
      `NON_COMPLETE_LOOP_OUTCOMES` invariant tests pass with `resolved` included.
- [ ] The ladder reads `resolved → needs-human → blocked → deferred → partial →
      complete` in **both** `SKILL.md:271` (backtick-tokened, so
      `test_stage_exit_protocol.py:379-388` passes) **and** `result-reporting.md`'s rung
      list — same six values, same order (two-place consistency).
- [ ] Step-4b template count is still **five** at `SKILL.md:232` (no `resolved`
      template added); the parenthetical there is the conditional-cause wording, in-line,
      with zero net body-line growth.
- [ ] **`--cause` validity matrix:** `--cause dependency-starvation` is accepted **only**
      with `--stage forge-5-loop --outcome partial` (swapping in the
      `_LOOP_PARTIAL_STARVED_TEXT` sentence); it exits **2 before any output** for every
      other stage or outcome. argparse `choices` rejects any other `--cause` value.
- [ ] The pending template renders "(iteration limit reached)" **only** when
      `iteration == maxIterations` AND `selectable > 0`; otherwise it renders the
      §5.2 starvation line naming blocking roots + per-root gated-subtree sizes, and the
      stage closes with `--cause dependency-starvation`.
- [ ] Every §5.2/§6 report surface cites its authoritative source (`backlogSummary` +
      `backlog-topology` + `state.json` counters); a cause a counter contradicts is
      caught as a defect.
- [ ] `stage-exit-protocol.md:50` lists `resolved` and the optional `--cause`; no
      previously-rejected combination is now accepted (guard widened, not weakened).
- [ ] `bash scripts/validate.sh` is green (spec purity, adapter non-drift, pytest,
      ruff, traceability); `adapters/**` regenerated after every canon edit.
