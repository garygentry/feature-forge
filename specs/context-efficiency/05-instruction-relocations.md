# 05 — Instruction Relocations (R2, R3, R6)

> **Markdown surgery, not code.** This document specifies three
> pure-text-relocation units — **R2** (within-file plugin-root prelude dedup),
> **R3** (conditional `process-overview.md` read), and **R6** (runner-contract
> always/conditional split). No script code changes here; every edit is a
> relocation or a dedup of instruction text in an existing `skills/…/SKILL.md`
> body or a skill-local `references/*.md` file. The compact-prelude canonical
> wording, portability contract, and frozen-protocol invariants these edits obey
> are defined once in `00-core-definitions.md` and referenced here, not
> re-derived.
>
> Builds on `00-core-definitions.md` (§8 compact prelude, §9 portability/citation,
> §10 invariants) and `01-architecture-layout.md` (§1 manifest, §2.2 cap ledger,
> §3 citation graph). The drift guards that enforce each unit live in
> `06-testing-strategy.md`.

## Requirement Coverage

| REQ ID | Requirement | Section |
|--------|-------------|---------|
| REQ-R2-01 | 1st prelude verbatim; subsequent occurrences → compact form, execution unchanged | R2 §1.1, §1.3, §1.4 |
| REQ-R2-02 | Dedup is within-file only; no cross-file prelude pointer in any executable path | R2 §1.2, §1.5 |
| REQ-R3-01 | Navigator reads `process-overview.md` only for "how does the pipeline work" questions | R3 §2.1, §2.2 |
| REQ-R6-01 | Always-loaded runner-contract sections load on every run | R6 §3.1, §3.2 (table) |
| REQ-R6-02 | Agent-selection loads only under the `agentArgument` gate; optional-flags reachable-not-default | R6 §3.2 (table), §3.3 |
| REQ-R6-03 | Split must not push runner-contract text back into the 300/300 forge-5-loop body | R6 §3.4 |
| REQ-PORT-01 | Every new/moved file cited by ≥1 skill body | R3 §2.3, R6 §3.5 |
| REQ-PORT-02 | Moved reference files host-neutral (no Claude-only tokens) | R6 §3.6, R3 §2.3 |
| REQ-MAINT-01 (R2/R3/R6) | Drift guard per moved/split file | R2 §1.6, R3 §2.4, R6 §3.7 |
| C-5 | Prelude dedup within-file only (no cross-file pointer) | R2 §1.2 |
| REQ-BEHAV-01/02 | Zero behavioral diff; frozen protocols preserved | all three §Invariant subsections |

---

# R2 — Within-file plugin-root prelude dedup (REQ-R2-01/02, C-5)

## 1.1 What moves

Four skill **bodies** repeat the full 3-line plugin-root resolver prelude
(`00-core-definitions.md §8`) at multiple call sites. The **first** occurrence in
each file stays **byte-verbatim**; the **2nd-and-subsequent** occurrences are
reduced to the sentinel-free **compact form**. Verified occurrence counts (fixed-
string `grep` of the prelude sentinel against the current source):

| File | Full preludes today | After R2 | Prelude line numbers (verified) |
|------|--------------------:|:---------|---------------------------------|
| `skills/forge/SKILL.md` | 5 | 1 full + 4 compact | 32, 40, 106, 146, 219 |
| `skills/forge-0-epic/SKILL.md` | 5 | 1 full + 4 compact | 42, 78, 122, 182, 254 |
| `skills/forge-bootstrap/SKILL.md` | 4 | 1 full + 3 compact | 62, 139, 147, 173 |
| `skills/forge-1-prd/SKILL.md` | 2 | 1 full + 1 compact | 31, 142 |

> Line numbers are the verified positions of the `R="$(bash -c …` block start at
> spec-authoring time; treat the **occurrence identity** (1st vs. subsequent), not
> the absolute line number, as binding — an intervening edit may shift them.

The full prelude that stays verbatim on occurrence 1 is exactly (both lines, from
`00-core-definitions.md §8` and the byte-pinned `BOOTSTRAP_PRELUDE` in
`check-spec-purity.py` L131–139):

```
R="$(bash -c 'for d in "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
```

## 1.2 Scope: within-file only, reference files EXCLUDED (C-5, REQ-R2-02)

Dedup applies **only within linearly-read skill bodies**. The compact form points
"to the top of **this** skill" — never to another file — so no executable path
depends on a cross-file pointer (C-5, REQ-R2-02). Each edited body keeps exactly
**one** full prelude, so every call site can still resolve the plugin root from
that same file.

The following reference files hold preludes and are **NOT touched by R2** — their
preludes sit inside **independently-invoked recipe blocks** ("invoke this block"),
which a caller may execute in isolation, so a "see the block above" pointer would
dangle:

| Excluded reference file | Prelude occurrences (verified) | Why excluded |
|-------------------------|-------------------------------:|--------------|
| `references/shared-conventions.md` | 6 | invoked-block recipes (Feature Directory Resolution, Branch Reconciliation, Git Commit Protocol, …) |
| `references/portable-root.md` | 2 | the canonical prelude documentation itself |
| `skills/forge-0-epic/references/edit-mode.md` | 2 | independently-invoked edit-mode recipe |

## 1.3 Constraint 1 — shell state does not persist across bash tool calls

The compact form is an **instruction-text** reduction (what the model *reads*),
**not** a runtime `$R` reuse. Shell state does not persist across separate Bash
tool invocations, so a later call site cannot consume a `$R` exported by an
earlier one. The compact form therefore **instructs the model to re-expand the
resolver** when it executes the later call site — execution behavior at each call
site is **byte-identical to today** (REQ-R2-01). The token saving is in the read
surface, not the executed command.

## 1.4 Constraint 2 — the compact form MUST be sentinel-free (Rule 5)

`check-spec-purity.py` Rule 5 (`check_prelude_identity`, L528–553) is a
**per-file** check:

```python
if _PRELUDE_SENTINEL in normalized and BOOTSTRAP_PRELUDE not in normalized:
    …VR_PRELUDE_DRIFT…
```

`_PRELUDE_SENTINEL` is the inner line
`[ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"`
(L156–158). Two consequences for R2:

1. **Keeping one full prelude satisfies Rule 5 for the whole file.** Because the
   check is `… in normalized` (file-scoped), the retained verbatim occurrence
   makes `BOOTSTRAP_PRELUDE in normalized` true, so the rule cannot fire on that
   file — regardless of how many compact forms follow.
2. **The compact form MUST still omit the sentinel line.** Defense in depth: the
   compact form contains **no** `forge-root.sh` sentinel substring, so even in
   isolation it never *looks* like a drifted prelude. This is the binding wording
   requirement — see §1.6.

## 1.5 The compact form (canonical, sentinel-free — `00-core-definitions.md §8`)

Every 2nd-and-subsequent occurrence is replaced, verbatim, by:

```
Resolve `$R` via the plugin-root prelude shown at the top of this skill, then run:
python3 "$R/scripts/<script>.py" <args>
```

Substitute `<script>.py <args>` with the real script + arguments that were in the
fenced command at that call site. No sentinel line, no cross-file pointer.

### Concrete before → after (one call site)

**File:** `skills/forge/SKILL.md`, **occurrence 4** (the context-usage helper,
verified at L104–109). This is a *subsequent* occurrence, so it becomes compact.

**Before** (verbatim today, L104–109):

```
**2. Check the context window.** Run the context-usage helper …:
```bash
R="$(bash -c 'for d in "${CLAUDE_PLUGIN_ROOT:-}" … [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-session.py" context-usage --json
```
```

**After** (compact, sentinel-free):

```
**2. Check the context window.** Run the context-usage helper …:

Resolve `$R` via the plugin-root prelude shown at the top of this skill, then run:
python3 "$R/scripts/forge-session.py" context-usage --json
```

The **first** occurrence in `skills/forge/SKILL.md` (L32, inside the epic-rollup
step) stays byte-verbatim and is what "the top of this skill" refers to.

> **Cap side-benefit (`01-architecture-layout.md §2.2`).** R2 is a net line
> reduction, easing pressure on `forge-0-epic/SKILL.md` (298/300 today) and
> `forge-bootstrap/SKILL.md`. R2 must never *raise* a body's line count.

## 1.6 R2 invariant + drift-guard requirement

**Invariant (`00-core-definitions.md §10`, R2 row):** every call site still
resolves the plugin root independently; **exactly one** full `BOOTSTRAP_PRELUDE`
remains per edited body; the compact form is **sentinel-free**.

**What `06-testing-strategy.md` (R2 guard) asserts:**
- Each of the four edited bodies contains **exactly one** full `BOOTSTRAP_PRELUDE`
  (string-equality against the canonical two-line block).
- The compact form contains **no** `forge-root.sh` sentinel substring anywhere
  it appears (no accidental Rule-5 trigger).
- The three excluded reference files (`shared-conventions.md`,
  `portable-root.md`, `forge-0-epic/references/edit-mode.md`) retain their
  original prelude occurrence counts (6 / 2 / 2) — untouched.
- No compact form contains a cross-file phrase (e.g. "see … .md") — the pointer
  text is always "the top of this skill" (REQ-R2-02 / C-5).

---

# R3 — Conditional `process-overview.md` read (REQ-R3-01)

## 2.1 What moves

`skills/forge/SKILL.md` currently reads `references/process-overview.md` as an
**unconditional setup step**. Verified single occurrence (line 18):

```
For pipeline architecture details, read `references/process-overview.md`.
```

It sits inside `### 1. Read Configuration`, before `### 2. Determine Context`, so
**every** navigator invocation — including routine dashboard/status rendering
(`rank-features` + render-status) — pays the 143-line file's cost today.

R3 moves the **read site** into a branch taken **only** when the user asks how the
pipeline works / architecture / stage-ordering questions. `process-overview.md`
itself is **unchanged** (still 143 lines) and stays cited so it still ships
(REQ-PORT-01).

## 2.2 Before → after (exact conditional-branch shape)

**Before** (unconditional, L18):

```
### 1. Read Configuration

Read and follow `references/shared-conventions.md` for configuration reading …

For pipeline architecture details, read `references/process-overview.md`.
```

**After** — the line is removed from unconditional setup and re-homed under an
explicit conditional. Add, at the point where the navigator classifies the user's
request (a new gated clause; wording is new *navigator instruction* text, not a
frozen interactive protocol, so it may be authored fresh):

```
### 1. Read Configuration

Read and follow `references/shared-conventions.md` for configuration reading …

(No architecture read here — routine status/dashboard rendering must not load it.)
```

and, in the request-classification region:

```
**If the user is asking how the pipeline works** — architecture, stage ordering,
what a stage does, or "explain forge" — **then** read
`references/process-overview.md` for the details before answering. For a plain
status/dashboard request, do **not** read it.
```

The binding shape is: **the only `read references/process-overview.md`
instruction in the file lives under a condition** whose trigger is "how does the
pipeline work / architecture / stage-ordering," and **no unconditional read line
remains**. Routine `rank-features` + render-status paths reach the dashboard
without loading the file.

## 2.3 Portability (REQ-PORT-01/02)

- **Citation-discoverable:** the literal citation `references/process-overview.md`
  MUST remain present in the `skills/forge/SKILL.md` body (now inside the
  conditional clause) so `build-adapters.py`'s `_fan_out_shared_references()`
  still ships it (`00-core-definitions.md §9`, `01-architecture-layout.md §3.1`).
  Moving the *read site* must not drop the *citation string*.
- **Host-neutral:** no new Claude-only tokens introduced; the conditional clause
  is host-neutral instruction prose (REQ-PORT-02). `process-overview.md`'s content
  is unchanged, so its portability posture is unchanged.

## 2.4 R3 invariant + drift-guard requirement

**Invariant (`00-core-definitions.md §10`, R3 row):** the navigator's
status/dashboard path is byte-identical; **only** the read-site of
`process-overview.md` moves behind the "how does the pipeline work" branch. No
dashboard prose, no `AskUserQuestion` gate, no ranker call changes.

**What `06-testing-strategy.md` (R3 guard) asserts:**
- `references/process-overview.md` is still **cited** in the `forge` SKILL body
  (grep for the literal path) — it still ships.
- The read is **conditional**: no unconditional `read …process-overview.md`
  instruction remains (assert the citation co-occurs with the conditional
  trigger text, e.g. a "how … pipeline works" / "architecture" cue on or near the
  same clause; assert the original L18 unconditional sentence is gone).
- `process-overview.md` file content is unchanged (byte / line-count check: still
  143 lines).

---

# R6 — Runner-contract always/conditional split (REQ-R6-01/02/03)

## 3.1 What moves

`skills/forge-5-loop/references/runner-contract.md` (341 lines, verified) is split
into two skill-local reference files. The **three agent-conditional sections**
move into a **new** `skills/forge-5-loop/references/agent-selection.md`;
`runner-contract.md` **keeps** the six always-loaded sections. No section text is
reworded — this is a cut-and-paste relocation by section boundary
(`00-core-definitions.md §10`, R6 row: every original section still reachable).

## 3.2 Full section partition (every section accounted for — none dropped)

Verified section headings and line boundaries in the current `runner-contract.md`.
This table mirrors R1's section-count preservation: **all nine** original
sections have a destination; none is dropped.

| # | Section heading (verbatim) | Source lines | Destination | Load gate |
|---|----------------------------|-------------:|-------------|-----------|
| 1 | `## Model selection precedence (Step 2d)` | L10–22 | `runner-contract.md` (keeps) | **ALWAYS** — every run |
| 2 | `## Agent selection (Step 2d)` | L23–82 | **`agent-selection.md`** (moves) | CONDITIONAL — `loopRunner.agentArgument` present |
| 3 | `### Claude-only model-alias guard (Step 2d, sub-step d-model)` | L83–111 | **`agent-selection.md`** (moves) | CONDITIONAL — same gate (nested under §2) |
| 4 | `## Run mode (Step 2d, rauf)` | L112–152 | `runner-contract.md` (keeps) | **ALWAYS** — every rauf run |
| 5 | `## Optional flags catalog (Step 2d, rauf)` | L153–168 | **`agent-selection.md`** (moves) | CONDITIONAL — reachable-but-not-default |
| 6 | `## Launch detail (Step 3b — background process)` | L169–230 | `runner-contract.md` (keeps) | **ALWAYS** — every run |
| 7 | `## Arm a Monitor on the event stream (Step 3d)` | L231–269 | `runner-contract.md` (keeps) | **ALWAYS** — every run |
| 8 | `## React to events as they land (Step 3e)` | L270–299 | `runner-contract.md` (keeps) | **ALWAYS** — every run |
| 9 | `## Inform-user output template (Step 3c)` | L300–341 | `runner-contract.md` (keeps) | **ALWAYS** — every run |

**Result:** `runner-contract.md` retains sections {1, 4, 6, 7, 8, 9} (six
always-loaded — REQ-R6-01). `agent-selection.md` receives sections {2, 3, 5}
(three conditional — REQ-R6-02).

> **Ordering note.** Section 3 (`### Claude-only model-alias guard`) is nested
> **under** section 2 (`## Agent selection`) in the source (it is an `###`
> sub-heading of the agent surface, L83 immediately following L23–82), so the two
> move together as a contiguous unit. Section 5 (`## Optional flags catalog`)
> currently sits *between* Run mode (kept) and Launch detail (kept) at L153–168;
> extracting it leaves Run mode (ends L152) adjacent to Launch detail (starts
> L169) in `runner-contract.md` — verify no orphaned prose spans the L152→L169
> seam after removal.

### `agent-selection.md` — new file frontmatter/preamble

`agent-selection.md` opens with a one-line orientation preamble (new prose,
host-neutral, no Claude-only tokens) then the three moved sections **in source
order**: Agent selection → Claude-only model-alias guard → Optional flags
catalog. Suggested preamble:

```
# forge-5-loop — Agent Selection (Step 2d, conditional)

The agent-selection surface, its Claude-only model-alias guard, and the optional-
flags catalog. Loaded ONLY when `loopRunner.agentArgument` is present (the Step 2d
capability gate); when the gate is off, Step 2d is byte-identical to today and this
file is never read.
```

## 3.3 Load gate (REQ-R6-02)

`agent-selection.md` is cited **only at the forge-5-loop capability gate**
(`skills/forge-5-loop/SKILL.md`, the "Agent selection (gated on
`loopRunner.agentArgument`)" block at ~L172–182, whose opening sentence is
"**Capability gate.** Everything below applies **only when** the effective
`loopRunner.agentArgument` is present and non-empty …"). Because the citation
lives inside that gated block, the file is read only when the gate is on
(REQ-R6-02).

The **optional-flags catalog** (section 5) co-locates in `agent-selection.md`:
it is *reachable* (the model reads it when it opens the file at the gate) but
*not loaded by default* (a gate-off run never opens the file). This satisfies
REQ-R6-02's "reachable but not loaded by default." The catalog also documents
`--agent`, which is meaningful only under the same gate, so co-location is
semantically correct.

## 3.4 Cap constraint — strict 1:1 citation swap (REQ-R6-03)

`skills/forge-5-loop/SKILL.md` is at the **300-line CI cap** (Rule 4,
`01-architecture-layout.md §2.2`). R6's SKILL edit is a **strict 1:1 citation
swap** with **zero net lines** — **no** runner-contract text is pushed back into
the body.

The existing SKILL body cites `references/runner-contract.md` at several points.
The two pointers whose target material **moves to `agent-selection.md`** re-point;
the pointers whose target material **stays** are untouched:

| SKILL body citation (verified) | Refers to | Action |
|--------------------------------|-----------|--------|
| L165 "…read `references/runner-contract.md`." (model-selection precedence + **optional-flags catalog**) | §1 (stays) **+** §5 (moves) | **Split the pointer**: keep `runner-contract.md` for model-selection precedence; add/redirect the optional-flags-catalog reference to `references/agent-selection.md` |
| L168 "…`## Run mode (Step 2d, rauf)` in `references/runner-contract.md`." | §4 (stays) | **Unchanged** |
| L170 "For the full loop-runner contract … read `references/runner-contract.md`." | §{1,4,6,7,8,9} (stay) | **Unchanged** |
| L174 "The full algorithm … are in `## Agent selection` of `references/runner-contract.md`; read it." | §2 (**moves**) | **Re-point** to `references/agent-selection.md` |
| L180 "Full rationale: `references/runner-contract.md`." (Claude-only model-alias guard) | §3 (**moves**) | **Re-point** to `references/agent-selection.md` |

**Line-neutrality rule:** each re-point is a same-line filename substitution
(`runner-contract.md` → `agent-selection.md`) or an in-place pointer split that
adds **0** net lines. If any edit would add a line, the body would exceed 300 and
the change is invalid — the drift guard (§3.7) enforces `≤300`.

> **WARNING (verify before implementing):** L165's pointer bundles two concerns —
> model-selection precedence (stays in `runner-contract.md`) **and** the
> optional-flags catalog (moves to `agent-selection.md`). Splitting it into two
> file references without adding a net line requires reusing the existing
> sentence structure (e.g. "…read `references/runner-contract.md`; the optional-
> flags catalog is in `references/agent-selection.md`."). Confirm this fits on the
> existing line budget at implementation time; if it forces a new line, prefer
> redirecting L165 wholly to the file that holds the majority concern and rely on
> the L174/L180 agent-selection citations for fan-out discoverability — but do
> **not** exceed 300 lines.

## 3.5 Portability — citation discoverability (REQ-PORT-01)

`agent-selection.md` is a **skill-local own-ref**
(`skills/forge-5-loop/references/agent-selection.md`), so it copies verbatim under
`build-adapters.py`'s per-skill own-refs step. Per the belt-and-suspenders
mitigation (`00-core-definitions.md §9`), it MUST **also** be cited by literal path
from the SKILL **body** (the L174/L180 re-points above provide this) so citation
fan-out has a discoverable path regardless of OQ-4. The path
`references/agent-selection.md` matches the fan-out regex
`references/([A-Za-z0-9_][A-Za-z0-9_./{}*-]*)` (no `/` or special chars beyond the
class).

`runner-contract.md` remains cited (L168/L170 unchanged) — it still ships.

## 3.6 Portability — host-neutral moved content (REQ-PORT-02)

The three moved sections MUST contain **no Claude-only tokens** — no literal
`/clear`, no Claude-only tool names. Verified against the source:

- **Section 2 (Agent selection)** and **Section 5 (Optional flags catalog)** are
  runner/agent-neutral (they discuss `rauf agents`, `--agent`, precedence) — no
  Claude-only tokens. Safe to move.
- **Section 3 (Claude-only model-alias guard)** is *about* Claude tier aliases
  (`opus`/`sonnet`/`haiku`, `claude-*`) — its **subject** is Claude-specific, but
  it contains **no host-only control tokens**: no literal `/clear`, no
  Claude-only tool name. It is guidance a non-Claude host reads to understand why
  a Claude alias would break a non-Claude agent. It stays **as-is** (content
  unchanged) and is host-neutral in the operative sense (does not break other
  adapters' regeneration). **No portability concern found.** If implementation
  surfaces a literal `/clear` or a Claude-only tool name in any moved section,
  **flag it in review** rather than silently adapting (REQ-BEHAV-02).

## 3.7 R6 invariant + drift-guard requirement

**Invariant (`00-core-definitions.md §10`, R6 row):** every original
`runner-contract.md` section is still reachable; `agent-selection.md` loads only
at the `loopRunner.agentArgument` gate; the forge-5-loop body stays **≤300
lines**.

**What `06-testing-strategy.md` (R6 guard) asserts** (mirrors the R1 section-count
pattern):
- **Section preservation:** the union of section headings in `runner-contract.md`
  ∪ `agent-selection.md` equals the original nine headings in §3.2 — none dropped,
  none duplicated. Specifically `runner-contract.md` holds exactly {1,4,6,7,8,9}
  and `agent-selection.md` holds exactly {2,3,5}.
- **Load-gate citation:** `agent-selection.md` is cited from the forge-5-loop
  SKILL body **inside** the `loopRunner.agentArgument` capability-gate block
  (assert the citation co-occurs with the gate sentinel text "applies only when …
  `loopRunner.agentArgument`").
- **Cap:** `forge-5-loop/SKILL.md` body is **≤300 lines** after the swap (`wc -l`
  over the region Rule 4 measures).
- **`runner-contract.md` still cited** (it still ships) and **`agent-selection.md`
  cited by ≥1 skill body** (fan-out precondition, REQ-PORT-01).

---

## Dependencies

- **`00-core-definitions.md`** — §8 (compact-prelude canonical wording, sentinel-
  free requirement), §9 (portability / citation-discoverability contract, OQ-4
  mitigation), §10 (per-unit frozen-protocol invariants). Referenced, not
  restated.
- **`01-architecture-layout.md`** — §1 (file-move manifest: the four R2 skills, the
  R3 read-site relocation, the R6 `agent-selection.md` new file), §2.2 (skill-body
  line-cap ledger — the 300/300 forge-5-loop constraint and forge-0-epic 298/300
  headroom), §3.1 (required citations table).
- **No dependency on R1/R4/R5.** R2/R3/R6 are file-disjoint quick wins
  (`01-architecture-layout.md §4`); R6 shares only `forge-5-loop/SKILL.md` with R5
  (line-disjoint edits, §4 caveat) and must land line-neutral either way.

This is a leaf spec: no other document depends on it. It must be implemented
against the two foundation docs above.

## Verification

**R2:**
- [ ] Each of `forge`, `forge-0-epic`, `forge-bootstrap`, `forge-1-prd` SKILL
      bodies contains **exactly one** full `BOOTSTRAP_PRELUDE` (the two-line block
      in §1.1).
- [ ] Every compact form is the canonical wording in §1.5 and contains **no**
      `forge-root.sh` sentinel substring.
- [ ] `grep -c` of the prelude sentinel gives 1/1/1/1 for the four skills, and
      6/2/2 for the untouched `shared-conventions.md` / `portable-root.md` /
      `forge-0-epic/references/edit-mode.md`.
- [ ] `check-spec-purity.py` passes (Rule 5 does not fire; Rule 4 line counts do
      not increase).
- [ ] No compact form contains a cross-file "see … .md" pointer (REQ-R2-02/C-5).

**R3:**
- [ ] `references/process-overview.md` still cited in `skills/forge/SKILL.md`
      (grep the literal path) — still ships.
- [ ] The read is under a "how does the pipeline work / architecture / stage-
      ordering" conditional; the original unconditional L18 read line is gone.
- [ ] A routine status/dashboard trace (name given or recency default) reaches the
      dashboard without a `process-overview.md` read.
- [ ] `process-overview.md` file content unchanged (143 lines).

**R6:**
- [ ] `agent-selection.md` exists at `skills/forge-5-loop/references/` and holds
      sections {2 Agent selection, 3 Claude-only model-alias guard, 5 Optional
      flags catalog} in source order.
- [ ] `runner-contract.md` holds sections {1,4,6,7,8,9}; the L152→L169 seam has no
      orphaned prose after §5 removal.
- [ ] Union of the two files' headings == the original nine (none dropped).
- [ ] `agent-selection.md` is cited from the forge-5-loop SKILL body inside the
      `loopRunner.agentArgument` capability gate; `runner-contract.md` still cited.
- [ ] `forge-5-loop/SKILL.md` body is **≤300 lines** after the 1:1 citation swap
      (`check-spec-purity.py` Rule 4 passes).
- [ ] No moved section contains a literal `/clear` or Claude-only tool name
      (REQ-PORT-02); any exception flagged in review, not silently adapted.
