# 02 — Verification-Checklist Mode Split (R1)

> HOW R1 lands. This document specifies the mechanical split of the single
> 477-line `skills/forge-verify/references/verification-checklists.md` into six
> per-mode checklist files plus one orchestrator-only `findings-template.md`, so
> a `forge-verifier` leaf subagent loads only its mode's checks (~1/6 the
> content, zero orchestrator material). It is a **pure relocation** of
> instruction text (00-core-definitions.md §2, kind 1) — no check is added,
> dropped, reworded, or renumbered.
>
> Builds on `00-core-definitions.md`: §7 (CHECK-ID inventory — the authoritative
> per-mode counts), §9 (citation / portability contract), §10 (R1 frozen-protocol
> invariant). This document does **not** restate those; it references them and
> specifies the file surgery.

## Requirement Coverage

| REQ ID | Requirement | Section |
|--------|-------------|---------|
| REQ-R1-01 | A verifier loads only its mode's checklist, not all six | §2 (mode-file partition), §3 (load path) |
| REQ-R1-02 | Orchestrator material never loads into the verifier context | §3 (load path), §5 (findings-template.md contents) |
| REQ-R1-03 | Dual-role "which role are you?" guard stays intact; no self-dispatch | §3 (dual-role preservation) |
| REQ-R1-04 | Per-mode "executed N of M" self-check remains correct against the reduced file | §7 (Step-3 expected-count reconciliation) |
| REQ-R1-05 | Every CHECK-ID preserved exactly across the split | §2 (partition table), §4 (copy rules), §9 (drift guard) |
| REQ-PORT-01 | Every new file cited by ≥1 skill body → ships to all adapters | §8 (citation/portability) |
| REQ-PORT-02 | Moved files host-neutral (no `/clear`, no Claude-only tokens) | §8 (citation/portability) |
| REQ-MAINT-01 (R1 slice) | Drift-guard asserts per-file CHECK-IDs + matching expected-count table | §9 (drift-guard requirement) |

---

## 1. Purpose & Scope

**In scope (R1 only):**

1. Delete `skills/forge-verify/references/verification-checklists.md` (477 lines).
2. Create six per-mode files under
   `skills/forge-verify/references/verification-checklists/` — one per mode,
   each carrying exactly that mode's CHECK-IDs copied byte-for-byte.
3. Create `skills/forge-verify/references/findings-template.md` holding the three
   orchestrator-only sections.
4. Re-point the `forge-verify` SKILL body's citations (Step 2 mode dispatch,
   Step 3 self-check, Steps 4/6) at the new files, and reconcile the Step-3
   expected-count table to the exact per-file totals.
5. Re-point the `agents/forge-verifier.md` leaf agent's guidance so a dispatched
   verifier reads only `verification-checklists/{mode}.md`.

**Out of scope:** any rewording of a check's text, any change to the dual-role
guard's meaning, any change to how findings are written or how state is updated
(those sections move verbatim). The drift-guard test itself is authored in
`06-testing-strategy.md`; this document specifies **what** that guard must assert
(§9).

**Prime-directive kind (00-core-definitions.md §2):** relocation. Every CHECK-ID
line and every orchestrator section moves byte-for-byte to a new file; nothing is
reworded.

## 2. The mode-file partition (REQ-R1-01, REQ-R1-05)

The current source `verification-checklists.md` is partitioned along its existing
`## … Mode Checklist` headings. Each mode's `##` section (and all its `###`
subsections and CHECK-ID lines) moves **verbatim** into its own file. The
authoritative per-mode CHECK-ID counts are fixed in **00-core-definitions.md §7**
and MUST NOT be re-derived here differently; they are restated for the partition
mapping only.

| Mode | New file (`skills/forge-verify/references/`) | CHECK-ID range | Count | Source `##` heading (line) → moves whole |
|------|----------------------------------------------|----------------|-------|-------------------------------------------|
| prd | `verification-checklists/prd.md` | CHECK-P01..P15 | **15** | `## PRD Mode Checklist` (src L7) |
| tech | `verification-checklists/tech.md` | CHECK-T01..T17 | **17** | `## Tech-Spec Mode Checklist` (src L32) |
| specs | `verification-checklists/specs.md` | CHECK-S01..S38 | **38** | `## Specs Mode Checklist` (src L61) |
| backlog | `verification-checklists/backlog.md` | CHECK-B01..B27 | **27** | `## Backlog Mode Checklist` (src L119) |
| impl | `verification-checklists/impl.md` | CHECK-I01..I23 (incl. Runnability I21/I22/I23) | **23** | `## Implementation Mode Checklist` (src L210) |
| epic | `verification-checklists/epic.md` | CHECK-E01..E10 | **10** | `## Epic Mode Checklist` (src L252) |
| | | **Total** | **130** | |

### 2.1 Exact `###` subsections carried into each file

These are the `###` subsection headings that live under each mode's `##` heading
in the source and MUST travel with it (verified against the source file):

- **prd.md** — `### Completeness`, `### Requirement Quality`,
  `### Non-Functional Requirements`, `### Open-Ended Analysis`.
- **tech.md** — `### Requirement Traceability`, `### Integration Analysis`,
  `### Design Quality`, `### Completeness`, `### Open-Ended Analysis`.
- **specs.md** — `### Requirement Coverage`,
  `### Tech Spec ↔ Implementation Spec Consistency`, `### Type System Integrity`,
  `### Cross-Reference Consistency`, `### Error Handling Coverage`,
  `### Integration Point Completeness`, `### Edge Cases and Non-Functional`,
  `### Testing Strategy`, `### Traceability`.
- **backlog.md** — `### Schema Compliance`, `### Spec Coverage`,
  `### Task Quality`, `### Dependency Ordering`, `### Completeness`,
  `### Generated-Artifact Freshness`, `### Artifact Lifecycle Consistency`.
- **impl.md** — `### Spec Compliance`, `### Backlog Completion`,
  `### Integration`, `### Code Quality`, `### Documentation`, `### Runnability`
  (the last carries its "When these fire" callout blockquote and CHECK-I21/I22/I23
  verbatim, including the nested `#149` sub-bullets under CHECK-I21).
- **epic.md** — the mode preamble paragraph ("Run `epic-manifest.py validate …`
  once; map its findings to E01/E02/E03/E08 …"), the **`epic-manifest.py validate`
  bash recipe block** (src L259–263, including its plugin-root prelude), plus
  `### Manifest Integrity (helper-delegated)` and
  `### Charter & Contract Coverage (verifier judgment)`.

### 2.2 Shared preamble each mode file carries

The source file opens (src L1–5) with a header and a stack-profile note:

```
# Verification Checklists

Detailed checklists for each verification mode. Execute EVERY check — do not skip.

> **Stack-specific details:** When a stack profile exists at `references/stacks/{stack}.md`, load it alongside this checklist for language-specific check criteria …
```

Each per-mode file MUST keep an equivalent single-mode header and the same
stack-profile blockquote **verbatim**, so a lone-loaded mode file is
self-contained. Recommended per-file top (example for `tech.md`):

```markdown
# Tech-Spec Verification Checklist

Detailed checklist for **tech** verification mode. Execute EVERY check — do not skip.

> **Stack-specific details:** When a stack profile exists at `references/stacks/{stack}.md`, load it alongside this checklist for language-specific check criteria (e.g., what "valid syntax" means, what the type check command is, how module exports work).

## Tech-Spec Mode Checklist
... (CHECK-T01..T17 verbatim) ...
```

The stack-profile blockquote is copied byte-for-byte (it is host-neutral, §8).

### 2.3 No cross-mode leakage

Each mode file contains **only** its own CHECK-IDs and no other mode's. Concretely:

- `prd.md` contains `CHECK-P01`..`CHECK-P15` and **no** `CHECK-T`/`S`/`B`/`I`/`E`.
- `tech.md` contains `CHECK-T01`..`CHECK-T17` and no other prefix. (…and so on.)
- No mode file contains any of the three orchestrator sections (§5).

This is the drift-guard's core assertion (§9).

## 3. Load path & dual-role preservation (REQ-R1-01, REQ-R1-02, REQ-R1-03)

The v0.12.1 dual-role architecture in `forge-verify/SKILL.md` (the
"## Which role are you? (read this first)" block, SKILL L12–17) has **two roles**;
R1 preserves that split exactly, and the file partition is what makes it *stronger*:

| Role | What it reads after R1 | What it MUST NOT read |
|------|------------------------|-----------------------|
| **`forge-verifier` leaf subagent** (dispatched via Agent tool; read-only tools; no Agent/Task tool) | **Only** `references/verification-checklists/{mode}.md` for its dispatched mode | Any other mode file; **any** of the three orchestrator sections (now physically absent from every mode file) |
| **Parent orchestrator** (navigator / in-stage auto-verify / direct invocation; has Agent tool) | `references/findings-template.md` at Step 4 and Step 6 | — |

**Why the split preserves REQ-R1-02 mechanically (not by discipline).** Today the
leaf reads the whole 477-line file, which physically contains the orchestrator
sections (src L325–477) — the guard relies on the leaf *ignoring* them. After R1,
the leaf reads only `{mode}.md`, which **does not contain** the Findings Document
Template, Example Findings, or Epic Mode State Write Detail. Orchestrator material
cannot leak into a verifier context because it is no longer in any file the
verifier is told to read.

**REQ-R1-03 — no self-dispatch reintroduced.** The split changes only *which file*
each role reads; it does not add any Agent/Task capability to the leaf, does not
change the "## Which role are you?" guard prose, and does not add a dispatch step
anywhere the leaf executes. The leaf's own instruction file
(`agents/forge-verifier.md`, §6) keeps its "**You ARE the verifier — you never
dispatch one**" paragraph verbatim. The `forge-verifier` frontmatter `tools: Read,
Glob, Grep, Bash` (agent L4) is unchanged — no Agent tool is added.

**Epic-mode note.** Epic mode still dispatches a **single** `forge-verifier`
(SKILL Step 3, L168). That verifier reads `verification-checklists/epic.md` only.
The `epic-manifest.py validate` recipe (which E01/E02/E03/E08 delegate to) travels
into `epic.md` (§2.1), so the leaf can still run it. The **Epic Mode State Write
Detail** section is orchestrator-only and moves to `findings-template.md` (§5) —
the leaf never writes `.epic-state.json`; the parent does (SKILL Step 6).

## 4. Copy rules (REQ-R1-05)

To guarantee "no check added, dropped, or renumbered":

1. **Byte-for-byte CHECK lines.** Every `- [ ] **CHECK-XNN**: …` line — including
   its full body, nested sub-bullets (e.g. CHECK-B26's numbered `1./2./3.`,
   CHECK-I21's `#149` sub-bullets, CHECK-E10's `1./2./3.` steps), and any
   blockquote callouts (e.g. the CHECK-B27 "Anti-pattern" blockquote, the
   `### Runnability` "When these fire" blockquote) — is copied verbatim into its
   mode file. No renumbering: `CHECK-T17` stays `CHECK-T17`.
2. **No merge, no split of check bodies.** A multi-paragraph check (CHECK-B26,
   CHECK-B27, CHECK-I21, CHECK-I22, CHECK-I23, CHECK-E09, CHECK-E10) moves as one
   unit; its internal structure is not touched.
3. **The epic bash recipe** (src L259–263) moves into `epic.md` including its
   plugin-root prelude line verbatim — it is a skill-local recipe that must stay
   runnable by the leaf (this prelude is **not** subject to R2's dedup; R2 is
   out of scope here and touches only linear skill *bodies*, not reference files —
   see `00-core-definitions.md §8`, `05-instruction-relocations.md §1`).
4. **Deletion is total.** `verification-checklists.md` is removed (git delete),
   not left as a stub — leaving a stub would let the leaf keep loading the whole
   thing and defeat REQ-R1-01.

## 5. `findings-template.md` contents (REQ-R1-02)

`skills/forge-verify/references/findings-template.md` (NEW, orchestrator-only)
holds the **three** sections that currently live at the tail of the source file,
moved **verbatim**:

| # | Section heading (moves verbatim) | Source lines | Used by (orchestrator) |
|---|----------------------------------|--------------|------------------------|
| 1 | `## Findings Document Template (Step 4)` | src L325–373 | SKILL Step 4 (write the findings document) |
| 2 | `## Example Findings (Step 4)` | src L375–407 | SKILL Step 4 (worked gap/inconsistency/improvement examples) |
| 3 | `## Epic Mode State Write Detail (Step 6)` | src L409–477 | SKILL Step 6 (write `.epic-state.json`) |

Recommended file preamble (host-neutral, §8):

```markdown
# Verify Findings Template (orchestrator-only)

Loaded by the **parent orchestrator** role of `forge-verify` at Step 4 (write the
findings document) and Step 6 (epic-mode state write). The `forge-verifier` leaf
subagent MUST NOT load this file — it holds only orchestrator-facing material
(see `SKILL.md` → "Which role are you?").

## Findings Document Template (Step 4)
... (verbatim from source L325–373) ...

## Example Findings (Step 4)
... (verbatim from source L375–407) ...

## Epic Mode State Write Detail (Step 6)
... (verbatim from source L409–477) ...
```

**Host-neutrality of section 3 (REQ-PORT-02).** The Epic Mode State Write Detail
section contains an embedded `python3 - … <<'PY' … PY` heredoc (src L446–476). It
uses only stdlib (`json, os, sys, tempfile`) and contains **no** `/clear` and no
Claude-only tool name — it is host-neutral and copies verbatim. (Confirmed by
reading the source: the heredoc is pure Python.)

## 6. `agents/forge-verifier.md` dispatch change (REQ-R1-01, REQ-R1-03)

The leaf agent file is **read-only** (`tools: Read, Glob, Grep, Bash`, L4) and its
"You ARE the verifier — you never dispatch one" guard (L20) is preserved verbatim.
The only change is to make explicit that the leaf reads its single mode file.

**Current** (agent L27, "How You Work" step 3):

> 3. Execute every check in the verification checklists (loaded via the forge-verify skill)

**After R1** — reword the *file-loading instruction only* (not the guard, not the
output format), to name the mode-scoped file:

> 3. Read **only your dispatched mode's checklist** —
>    `references/verification-checklists/{mode}.md` (the parent's dispatch prompt
>    names your `{mode}`) — and execute every check in it. Do **not** read the
>    other five mode files or `references/findings-template.md`; those are for
>    other modes and for the parent orchestrator respectively.

Because this touches the wording of an instruction sentence (not a frozen
interactive protocol, but still a moved-content edit), it is a **flagged** change
per REQ-BEHAV-02 / 00-core-definitions.md §2 — call it out in the R1 PR
description ("agent step-3 file-load instruction reworded to name the per-mode
file") rather than adapting it silently.

> WARNING: OQ-4 (tech-spec §10) — it is **unconfirmed** whether the adapter
> build's citation fan-out scans `agents/*.md` bodies. This agent edit is
> therefore treated as **non-load-bearing for portability**: the six mode paths
> and `findings-template.md` are cited from the **forge-verify SKILL body** (§8),
> so shipping does not depend on the agent-body citation. Verify OQ-4 during R1
> implementation; if fan-out does scan agent bodies, the `{mode}.md` template
> reference above is a bonus discoverable path, not a requirement.

## 7. `forge-verify/SKILL.md` citation & expected-count changes

Three edit sites in the SKILL body. All are 1:1 citation re-points plus one
count-table reconciliation; none inline orchestrator material (that would push the
257/300 body over cap — `01-architecture-layout.md §2.2`).

### 7.1 Step 2 — parallel-dispatch group mapping (SKILL L38–46)

The "Suggested groups (map to the category clusters in
`references/verification-checklists.md`)" pointer (SKILL L39) re-points to the
per-mode file the group belongs to. Concretely, replace the single
`references/verification-checklists.md` reference with the mode-specific path so a
dispatcher of a `specs` fan-out cites `references/verification-checklists/specs.md`
(and `backlog`→`backlog.md`, `impl`→`impl.md`). The **dimension groups themselves
are unchanged** (they still map to the same `###` clusters, which now live in the
per-mode file). This is a relocation of the pointer, not a change to the fan-out
plan.

### 7.2 Step 3 — checklist read + self-check (SKILL L164–168)

**Current** (SKILL L164):

> Read `references/verification-checklists.md` for the detailed checklists per
> mode. … That same reference also holds the relocated **Findings Document
> Template (Step 4)**, the worked **Example Findings (Step 4)**, and the **Epic
> Mode State Write Detail (Step 6)** sections used later in this skill.

**After R1** — the checklist read becomes mode-scoped, and the "same reference
holds the templates" clause re-points to `findings-template.md`:

> Read `references/verification-checklists/{mode}.md` for the detailed checklist
> for the mode being verified (`{mode}` ∈ `prd | tech | specs | backlog | impl |
> epic`). Execute every check. Do not skip checks because things "look fine." The
> orchestrator-only **Findings Document Template (Step 4)**, worked **Example
> Findings (Step 4)**, and **Epic Mode State Write Detail (Step 6)** sections now
> live in `references/findings-template.md`, read later by the parent role at
> Steps 4/6.

The mode-ID sentence (SKILL L166, "Each check … has a unique ID (CHECK-P01,
CHECK-T01, …)") is unchanged.

### 7.3 Step 3 — expected-count reconciliation (REQ-R1-04)

The self-check sentence (SKILL L166) currently carries **approximate** totals that
are wrong for `tech`. This is exactly the mismatch REQ-R1-04 requires reconciling.
The table below is authoritative (00-core-definitions.md §7):

| Mode | SKILL L166 **before** (approximate) | **After** (exact per-file total) |
|------|-------------------------------------|----------------------------------|
| prd | `prd: ~15 checks` | `prd: 15 checks` |
| tech | `tech: ~15 checks` ← **wrong** | `tech: 17 checks` |
| specs | `specs: ~38 checks` | `specs: 38 checks` |
| backlog | `backlog: ~27 checks` | `backlog: 27 checks` |
| impl | `impl: ~23 checks` | `impl: 23 checks` |
| epic | `epic: ~10 checks` | `epic: 10 checks` |

**Exact edit.** In SKILL L166, replace the parenthetical
`(prd: ~15 checks, tech: ~15 checks, specs: ~38 checks, backlog: ~27 checks,
impl: ~23 checks, epic: ~10 checks)` with
`(prd: 15 checks, tech: 17 checks, specs: 38 checks, backlog: 27 checks,
impl: 23 checks, epic: 10 checks)`. Drop the `~` so the count is exact and
drift-guardable — because the verifier now loads the mode-scoped file, "Executed
N of M" can be checked against a single, exact M (more robust, not weaker,
REQ-R1-04).

**Also reconcile Step 2's approximate totals for internal consistency.** The
single-vs-parallel rule (SKILL L30, L33) also carries `~` figures ("prd ~15, tech
~15", "specs ~38, backlog ~27, impl ~23"). Update `tech ~15` → `tech 17` there too
so the two places agree; the single-vs-parallel *thresholds* (small vs large) are
unchanged (tech stays a "small mode → single verifier" at 17). This is a flagged
wording change (REQ-BEHAV-02) — the routing decision is identical, only the
displayed count is corrected.

### 7.4 Step 4 and Step 6 — findings-template re-point (REQ-R1-02)

- **Step 4** (SKILL L190–194): the pointer "The full findings-document template …
  and the worked **Example Findings** … live in `references/verification-checklists.md`
  under the **Findings Document Template (Step 4)** and **Example Findings (Step 4)**
  sections" re-points to `references/findings-template.md` (same section headings,
  new file). "follow that template verbatim" is unchanged.
- **Step 6** (SKILL L241–245): the pointer "The full `.epic-state.json` schema …
  and the atomic … **write-mechanism** detail … live in
  `references/verification-checklists.md` under the **Epic Mode State Write Detail
  (Step 6)** section" re-points to `references/findings-template.md`. "Follow it
  verbatim." is unchanged.

Both are read by the **parent orchestrator** role only — preserving REQ-R1-02.

## 8. Citation & portability (REQ-PORT-01, REQ-PORT-02)

Per `00-core-definitions.md §9`, every new reference file must be
**citation-discoverable from a skill body** and **host-neutral**.

**Discoverable (REQ-PORT-01).** All seven new paths MUST appear as literal
`references/...` citations **in the `forge-verify` SKILL body** (not only the
agent body — OQ-4, §6 WARNING):

| New file | Cited from SKILL body site |
|----------|----------------------------|
| `references/verification-checklists/prd.md` | Step 3 read (§7.2), via the `{mode}` template expanding to `prd` |
| `references/verification-checklists/tech.md` | Step 3 read (§7.2) |
| `references/verification-checklists/specs.md` | Step 2 group map (§7.1) + Step 3 read |
| `references/verification-checklists/backlog.md` | Step 2 group map (§7.1) + Step 3 read |
| `references/verification-checklists/impl.md` | Step 2 group map (§7.1) + Step 3 read |
| `references/verification-checklists/epic.md` | Step 3 epic-dispatch note (SKILL L168) |
| `references/findings-template.md` | Step 4 (§7.4) + Step 6 (§7.4) |

Because the fan-out regex is
`references/([A-Za-z0-9_][A-Za-z0-9_./{}*-]*)` (00-core-definitions.md §9), the
`{mode}` template token matches (the class includes `{`, `}`, `/`), and each
concrete path matches (the class includes `/` and `.`). To remove any dependence
on template-brace matching, the SKILL body SHOULD **also** name at least the six
literal paths once — e.g. an inline enumeration in the Step 3 read note:
"(`references/verification-checklists/{prd,tech,specs,backlog,impl,epic}.md`)".
These are **skill-local own-refs** (`skills/forge-verify/references/...`) so they
copy verbatim under the per-skill own-refs step regardless; citing from the body
is belt-and-suspenders per the OQ-4 mitigation.

**Host-neutral (REQ-PORT-02).** None of the seven files may contain a literal
`/clear` or a Claude-only tool name. Verified against the source content that
moves: the mode checklists reference `AskUserQuestion` only inside prose *about
findings* (none present in the moved checklist bodies), the epic recipe and the
findings-template heredoc are stdlib Python. The moved content is host-neutral;
the drift guard asserts this (§9).

**Regenerates cleanly (REQ-PORT-03, owned by `06-testing-strategy.md`).** All five
adapters regenerate and the `test_build_adapters.py` snapshot refreshes via the
minimal-canon scratch-build + `command cp -f` procedure (C-3). The old
`verification-checklists.md` path disappears from every adapter; the seven new
paths appear.

## 9. R1 drift-guard requirement (REQ-MAINT-01, R1 slice)

`06-testing-strategy.md` owns the actual pytest; this section fixes **what it MUST
assert** (stdlib-only, `REPO_ROOT`-relative, asserting against `skills/` canon
never `adapters/`, per `01-architecture-layout.md §6`). The R1 guard MUST assert:

1. **Per-file CHECK-IDs exact.** For each mode file, `grep -oE 'CHECK-<X>[0-9]{2}'`
   (X ∈ P/T/S/B/I/E) yields **exactly** its expected set with the exact count:
   prd→15 (P01..P15), tech→17 (T01..T17), specs→38 (S01..S38), backlog→27
   (B01..B27), impl→23 (I01..I23), epic→10 (E01..E10). No ID missing, no ID added,
   contiguous numbering.
2. **No cross-mode leakage.** Each mode file contains **only** its own prefix — e.g.
   `tech.md` contains no `CHECK-P`/`S`/`B`/`I`/`E` id (§2.3).
3. **Total preserved.** The union across the six files equals the original 130
   CHECK-IDs (00-core-definitions.md §7) — none dropped in the split.
4. **findings-template holds the three sections; no mode file does.**
   `findings-template.md` contains all three headings
   (`## Findings Document Template (Step 4)`, `## Example Findings (Step 4)`,
   `## Epic Mode State Write Detail (Step 6)`), and **no** mode file contains any
   of them (REQ-R1-02 enforced mechanically).
5. **Expected-count table matches (REQ-R1-04).** The forge-verify SKILL body's
   Step-3 expected-count parenthetical parses to exactly `{prd:15, tech:17,
   specs:38, backlog:27, impl:23, epic:10}` — i.e. the table matches the actual
   per-file grep counts, and no `~` remains on those figures.
6. **Old file gone.** `verification-checklists.md` no longer exists under
   `skills/forge-verify/references/` (deletion is total, §4.4).
7. **Every new file cited (REQ-PORT-01).** Each of the seven new paths appears as
   a literal `references/...` citation in `forge-verify/SKILL.md` (the catch-all
   from REQ-MAINT-01: every new reference file is cited by ≥1 skill body).

Assertions 1–3 are the direct analog of the existing CHECK-ID-count discipline;
assertion 5 is the R1-specific "expected-count table matches" clause of
REQ-MAINT-01.

## 10. Worked example (load path before vs after)

**Before R1** — parent dispatches a `specs` fan-out instance:

- Leaf loads `references/verification-checklists.md` (477 lines): all six modes'
  checks **plus** the Findings Template, Example Findings, and Epic State Write
  Detail. It uses only the ~38 `specs` checks; the other ~92 checks and all
  orchestrator material are dead weight in its context.

**After R1** — same dispatch:

- Leaf loads `references/verification-checklists/specs.md` only: the 38 `specs`
  checks (`CHECK-S01..S38`) and nothing else. Its "Executed N of M" line checks
  against the single exact M=38. The parent, at Step 4, loads
  `references/findings-template.md` to write the document — the leaf never sees it.

## Dependencies

- **`00-core-definitions.md`** — §7 (CHECK-ID inventory / authoritative counts,
  the source of truth for the partition table §2 and the reconciliation §7.3), §9
  (citation/portability contract applied in §8), §10 (R1 frozen-protocol
  invariant preserved in §3). This split MUST match §7 exactly.
- **`06-testing-strategy.md`** — owns the actual R1 drift-guard pytest; §9 above
  fixes what it must assert. Implement the guard there, not here.
- **Ordering:** R1 is a "quick win" and file-disjoint from R2–R6
  (`01-architecture-layout.md §4`); it may land in any order among R1/R2/R3.

## Verification

Confirm an implementation matches this spec:

- [ ] `skills/forge-verify/references/verification-checklists.md` is **deleted**
      (no stub remains).
- [ ] Six files exist under
      `skills/forge-verify/references/verification-checklists/`: `prd.md`,
      `tech.md`, `specs.md`, `backlog.md`, `impl.md`, `epic.md`.
- [ ] `grep -oE 'CHECK-[A-Z][0-9]{2}'` per file yields exactly:
      prd=15, tech=17, specs=38, backlog=27, impl=23, epic=10 (total 130), with
      no cross-mode prefix in any file (§9.1–9.3).
- [ ] `skills/forge-verify/references/findings-template.md` exists and contains
      **all three** orchestrator section headings; **no** mode file contains any
      of them (§9.4).
- [ ] The forge-verify SKILL Step-3 expected-count parenthetical reads
      `prd: 15 … tech: 17 … specs: 38 … backlog: 27 … impl: 23 … epic: 10` with
      no `~` (§7.3); the Step-2 single-vs-parallel note's `tech` figure is 17.
- [ ] All seven new paths appear as literal `references/...` citations in
      `forge-verify/SKILL.md` (§8).
- [ ] The forge-verify SKILL Steps 4 and 6 cite `references/findings-template.md`
      (not `verification-checklists.md`) for the templates (§7.4).
- [ ] `agents/forge-verifier.md` "How You Work" step 3 names
      `references/verification-checklists/{mode}.md`; the "You ARE the verifier —
      you never dispatch one" guard and `tools: Read, Glob, Grep, Bash` are
      unchanged (§6).
- [ ] No moved file contains a literal `/clear` or a Claude-only tool name
      (REQ-PORT-02, §8).
- [ ] The R1 drift guard in `06-testing-strategy.md` asserts §9.1–9.7 and is green.
- [ ] All five adapters regenerate; `test_build_adapters.py` snapshot passes after
      fixture refresh; the old path is gone and the seven new paths present
      (REQ-PORT-03).
