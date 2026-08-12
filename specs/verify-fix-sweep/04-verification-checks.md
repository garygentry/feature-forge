# 04 — Verification CHECKs

> The four new verification checklist entries (`CHECK-B29`, `CHECK-I24`, `CHECK-I25`,
> `CHECK-S39`) and the three zero-net-new-line edits to `skills/forge-verify/SKILL.md`
> that make them reachable and counted.
>
> This document carries the **ready-to-paste prose**. The implementing engineer copies
> §3's fenced blocks verbatim into the three checklist files and applies §4's exact
> before → after replacements to the SKILL body. Nothing here is a sketch to be
> re-worded: the wording is load-bearing (host-neutrality per C-5, and the literals
> `05-testing-strategy.md`'s prose guards pin).
>
> Shared vocabulary and the authoritative id/severity table: `00-core-definitions.md`
> §9. File inventory and edit anchors: `01-architecture-layout.md` §2, §4.1. Locate
> every anchor by **quoted text**, never by line number — the line numbers cited in
> tech-spec §2/§3.7 are as-of-authoring hints and are expected to drift.

## Requirement Coverage

| REQ ID | Requirement | Section |
|---|---|---|
| REQ-CARD-02 | Backlog-mode CHECK: declared per-item work list re-derived from the actual item set, omissions named | §3.1 (`CHECK-B29`), §5.1, §7.1 |
| REQ-CARD-03 | Impl-mode CHECK: same assertion over implementation artifacts (the 15-of-16 work order) | §3.2 (`CHECK-I24`), §5.1, §7.1 |
| REQ-CARD-04 | Cardinality assertions degrade to not-applicable, never a hard fail | §3.1 step 1, §3.2 step 1, §6 (degradation matrix) |
| REQ-CONS-01 | Specs- **and** impl-checklist CHECK flagging an artifact that restates one quantity or claim inconsistently | §3.3 (`CHECK-I25`), §3.4 (`CHECK-S39`), §6, §7.2 |
| (C-2) | Verifier judgment / checklist prose only — no mechanical extractor in milestone 1 | §1, §3.3, §3.4 |
| (C-4) | Prose lands in uncapped `references/`-tier files; SKILL edits are zero net new lines | §3 preamble, §4.5 |
| (C-5) | Host-neutral wording; checklist files are not translation-exempt | §2 |

## 1. Scope and Non-Goals

**In scope.** Four checklist entries and three in-place edits to the forge-verify SKILL
body, per `00-core-definitions.md` §9:

| CHECK ID | File | New section | Covers | Severity of a true hit |
|---|---|---|---|---|
| `CHECK-B29` | `verification-checklists/backlog.md` | `### Work-Order Cardinality` | REQ-CARD-02 | `gap` (blocking) |
| `CHECK-I24` | `verification-checklists/impl.md` | `### Work-Order Cardinality` | REQ-CARD-03 | `gap` (blocking) |
| `CHECK-I25` | `verification-checklists/impl.md` | `### Internal Consistency` | REQ-CONS-01 | `inconsistency` (advisory); `error` only when decision-bearing |
| `CHECK-S39` | `verification-checklists/specs.md` | `### Internal Consistency` | REQ-CONS-01 | `inconsistency` (advisory); `error` only when decision-bearing |

**Out of scope for this document.**

- **Any mechanical extractor.** All four checks are **verifier judgment executed from
  checklist prose** (C-2, PRD §6 "A mechanical numeric-claim extractor … milestone 1
  realizes REQ-CONS-01 as verifier judgment only"). No script, no regex miner, no
  `fix-sweep.py` subcommand backs them. `CHECK-B29`/`CHECK-I24` are *deterministic in
  method* — re-derive the set, difference it — but the derivation is performed by the
  verifier reading artifacts, not by a tool this feature ships.
- **`scripts/fix-sweep.py`** and its `plan-coverage` subcommand (REQ-CARD-01 — the
  *fix-pass-level* cardinality assertion): `02-fix-sweep-script.md`. `CHECK-B29`/
  `CHECK-I24` are the *verify-pass-level* siblings; they share the incident class but
  no code.
- **forge-fix SKILL.md**: `03-forge-fix-integration.md`.
- **The four pinned test files** that move in lockstep with §4's numeric edits
  (a fifth, `tests/test_build_adapters.py`, moves with the `RUNTIME_HELPERS` edit on
  the other chain — `01-architecture-layout.md` §5.1): `05-testing-strategy.md`
  (pointers only in §5.2 here).
- **`references/stage-exit-protocol.md`** and `findings-template.md` are **untouched**
  (C-1, `01-architecture-layout.md` §2).

## 2. Host-Neutrality Constraint (C-5) — hard

The three checklist files are copied into every adapter bundle and run through the #167
host-term translation pass, and they are **not** translation-exempt.
`tests/test_adapter_host_neutrality.py` walks every non-Claude bundle's skill bodies
**and** its bundled `references/` closure (`_scan_paths` covers `skills/` and
`references/`) and fails on any surviving forbidden token. Its `FORBIDDEN_TOKENS`
tuple today is:

```
"the the ", "The the ", "`Agent` tool", "`Skill` tool", "`Monitor` tool",
"/clear", "AskUserQuestion"
```

with an additional Pi-specific set (`/clear`, `/feature-forge:`). Consequences the new
prose must obey — this is why §3's blocks are written the way they are, and why an
implementer must not "improve" the wording:

1. **Never name a host, a host tool, or a host command.** No product names, no
   dispatch/question/monitoring tool names, no slash commands, no plugin-prefixed
   command strings. The vocabulary already present in these files is the whole
   permitted set: *the verifier*, *this check*, *flag*, *report*, *record*, *finding*,
   *pass* / *not-applicable*, *advisory*, *blocking*.
2. **Do not write prose that merely *mentions* a host term.** The translation pass
   rewrites tokens inside copied prose without understanding whether the term is being
   *used* or *discussed*, so a sentence that says "do not rely on a particular
   assistant's tooling" garbles in the mirrors. Reword — never exempt (per
   `01-architecture-layout.md` §5.2, "for this feature, reword").
3. **Avoid the double-article trap.** The article-aware replacement pairs can produce
   `the the ` when authored prose already supplies an article before a translated
   noun phrase. §3's prose avoids the construction entirely by never placing an
   article immediately before a tool-shaped noun phrase.

Verification of this constraint is a checkbox in §9 and is enforced in CI by
`tests/test_adapter_host_neutrality.py` after the single `adapters/**` regeneration
(`01-architecture-layout.md` §3).

## 3. Checklist Entries (ready to paste)

All three files are `references/`-tier and **uncapped** (`01-architecture-layout.md`
§4.3) — explanatory depth belongs here, not in the SKILL body (C-4).

**Placement rule for all three files:** append the new section(s) at **end of file**,
after the current final content line, keeping the file's existing single trailing blank
line. All three files end today with one content line followed by one blank line;
append so that shape is preserved. End-of-file placement keeps each file's CHECK ids
document-order monotonic and matches how `CHECK-B26`/`B27`/`B28` and `CHECK-I21`–`I23`
were added. It is also test-safe — see §5.2.

**Style contract** (matched from `CHECK-B26`/`B27`/`B28` and `CHECK-I21`–`I23`):

- Entry line shape: `- [ ] **CHECK-XNN**: **Bold title.** prose…` with an issue
  citation `(#170)` after the bold title.
- An italic degradation/severity clause immediately after the title, in the
  `*Advisory heuristic — … **not-applicable** when …*` shape.
- Numbered sub-steps when the check is a procedure rather than a single question.
- `**Report, do not repair.**` as the closing directive where the check's output is a
  finding for an author to act on.
- A `> **When these fire:**` / `> **When this fires:**` blockquote preamble on a new
  section that needs one — `### Runnability` in `impl.md` is the exemplar.

### 3.1 `CHECK-B29` — Work-Order Cardinality, backlog mode (REQ-CARD-02, REQ-CARD-04)

Paste at the end of
`skills/forge-verify/references/verification-checklists/backlog.md`:

```markdown
### Work-Order Cardinality

> **When this fires:** only when the backlog, or an artifact the backlog derives from,
> **declares an enumerated per-item work list that claims to cover a set**. A backlog
> with no such list yields **not-applicable** — absence of a declared list is never a
> hard fail. The defect this catches is not a wrong item; it is a **missing** one, and
> a missing entry is invisible to every reader who checks the entries that are present.

- [ ] **CHECK-B29**: **A declared per-item work list covers the whole set it claims — name what is missing** (#170).
  *Heuristic with a mechanical method — **not-applicable** when no enumerated per-item work
  list is declared anywhere in the backlog or the artifacts it derives from; absence is
  **never a hard fail**. A true omission is a `gap` (blocking): an unreviewed member is
  missing coverage.* When the backlog — or an artifact it derives from, such as a
  hand-authored work order, a per-item review sheet, a "one entry per item" table in a
  plan the backlog cites, or a stated total in a summary line — declares an enumerated
  list **claiming coverage of a set**, the list's cardinality must be **re-derived from
  the actual member set** and never trusted from the list's own header, its numbering, or
  a stated total. In the incident behind this check a hand-authored work order enumerated
  **15 of 16** artifacts; it passed authoring and a full review, and the dropped
  sixteenth would have been published unreviewed. Verify by re-deriving, never by
  eyeballing:
  1. **Find the declared lists.** Scan the backlog and the artifacts it cites for an
     enumerated list that claims coverage of a nameable set — one entry per backlog item,
     per spec document, per requirement id, per generated artifact, per file to touch. The
     coverage claim reads as "one per …", "all …", "every …", "each …", or as a stated
     total ("16 artifacts", "covers the full set"). If **no** such list exists, this check
     is **not-applicable** — record it and move on.
  2. **Re-derive the member set from its own source of record.** Build the actual set
     independently of the list: backlog items from `backlog.json`, spec documents from the
     spec directory listing, requirement ids from the PRD, artifacts from the paths the
     items name. Count what you built; do not adopt any count the list asserts about
     itself.
  3. **Difference both directions and name every discrepancy.** Report each member of the
     re-derived set that has **no** entry in the declared list **by name** — the item id,
     file path, or requirement id — never as a count delta ("one short", "off by one"),
     which hands the reader back exactly the derivation this check just performed. Report
     the reverse direction too: a list entry naming something absent from the re-derived
     set is a stale entry.
  4. **Severity, and what to report.** A named omission is a `gap`. A stale entry, or a
     stated total that disagrees with a list whose membership is nevertheless complete, is
     an `inconsistency`. Every finding names the list, the source of record the set was
     re-derived from, and each missing or stale member by name. **Report, do not repair** —
     authoring the missing entry belongs to the fix pass.
```

**Traceability.** Steps 1–3 realize REQ-CARD-02 ("the list's cardinality is re-derived
from the actual item set and any missing item is named"). The italic clause and step 1's
exit realize REQ-CARD-04 ("no declared work list yields not-applicable, never a hard
fail"). The `gap` severity is fixed by `00-core-definitions.md` §9.

### 3.2 `CHECK-I24` — Work-Order Cardinality, impl mode (REQ-CARD-03, REQ-CARD-04)

Paste at the end of `skills/forge-verify/references/verification-checklists/impl.md`
(after `### Runnability`, before the `### Internal Consistency` block from §3.3 — the
two new sections are appended in this order):

```markdown
### Work-Order Cardinality

> **When this fires:** only when the implementation ships or cites an **enumerated work
> order, coverage list, or inventory that claims to cover a set of artifacts** — a
> per-file work order, a "files changed" table, a per-artifact review checklist, an
> inventory table in a spec this implementation realizes, or a registry constant in code
> that claims to list every member of a class. No such list yields **not-applicable**;
> absence is never a hard fail.

- [ ] **CHECK-I24**: **A declared work order or coverage list covers the whole artifact set it claims — name what is missing** (#170).
  *Heuristic with a mechanical method — **not-applicable** when the implementation declares
  no enumerated work order, coverage list, or registry claiming full coverage; absence is
  **never a hard fail**. A true omission is a `gap` (blocking): an unreviewed artifact is
  missing coverage.* Any declared work order or coverage list must be checked against the
  **actual artifact set it claims to cover**, with omissions named. The incident behind
  this check is a hand-authored work order that enumerated **15 of 16** artifacts: the
  sixteenth was never reviewed and would have shipped, because every reviewer worked the
  list that was in front of them. Verify by re-deriving, never by reading the list back to
  itself:
  1. **Find the declared lists.** Look for enumerated lists claiming coverage of a set:
     a work order or handoff enumerating files to change, a "files changed" or "artifacts
     touched" table, a per-artifact review or sign-off checklist, an inventory table in an
     implementation spec, and **registry-shaped constants in code** — a tuple, array, or
     map documented as holding every helper, every adapter target, every generated file.
     If no such list exists, this check is **not-applicable**.
  2. **Re-derive the covered set from its source of record.** Enumerate the actual set
     independently: the directory listing for a per-file list, the spec's own file
     inventory for an implementation work order, the on-disk members for a registry
     constant, the test suite's own collected set for a coverage table. A registry claiming
     to hold "every script the skills invoke" is re-derived by finding the invocations, not
     by reading the tuple.
  3. **Difference both directions and name every discrepancy.** Every member of the
     re-derived set with no entry in the declared list is reported **by name** — path,
     symbol, or artifact id — never as a count delta. A list entry pointing at something
     that does not exist is a stale entry, reported the same way.
  4. **Severity, and what to report.** A named omission is a `gap`; a stale entry, or a
     stated total that disagrees with an otherwise complete list, is an `inconsistency`.
     Name the list, the source of record used for the re-derivation, and each missing or
     stale member. This check is deliberately narrower than `CHECK-I01` (which asks whether
     each file the architecture spec lists exists): here the *list itself* is the suspect,
     not the artifacts it names. **Report, do not repair.**
```

**Traceability.** REQ-CARD-03 ("any declared work order / coverage list is checked
against the actual artifact set it claims to cover, naming omissions (the 15-of-16
hand-authored work-order case)"), plus REQ-CARD-04's degradation in the italic clause
and step 1.

**Cross-mode-leak warning.** This entry must not name a `CHECK-B`, `CHECK-S`, `CHECK-P`,
`CHECK-T`, or `CHECK-E` id — see §5.1. `CHECK-I01` is same-mode and therefore safe.

### 3.3 `CHECK-I25` — Internal Consistency, impl mode (REQ-CONS-01)

Paste at the end of `skills/forge-verify/references/verification-checklists/impl.md`,
after the §3.2 block:

```markdown
### Internal Consistency

> **When this fires:** on any artifact that states the same quantity, scope claim, or
> status **in more than one place** — front matter vs body, a summary block vs the prose
> below it, a table vs the narrative that explains it, a docstring vs the code it
> documents. This is deliberately **intra-artifact**: contradictions *between* artifacts
> are already the subject of the spec-compliance checks above. An artifact that states
> each quantity exactly once yields **not-applicable** — it degrades naturally, with
> nothing to compare.

- [ ] **CHECK-I25**: **One artifact, one answer — a quantity or claim restated inconsistently inside a single artifact** (#170).
  *Verifier judgment — read and compare; no extractor runs (deliberately, this milestone).
  **not-applicable** when nothing is restated. Severity defaults to `inconsistency`
  (advisory) and escalates to `error` only when the contradiction is decision-bearing, per
  the severity conventions in the verify skill.* An artifact can be internally false while
  every cross-artifact check passes: in the incident behind this check, one artifact
  asserted a claim held **universally**, while its own body — two sections below — stated
  the correct **4-of-7** breakdown. The false summary survived a full review, propagated
  into generated output, and would have shipped. Verify by comparing the artifact against
  itself:
  1. **Collect the restatements.** Read the artifact end to end and note every place it
     states: a **count or total** ("16 files", "N of M", "all four"), a **scope claim**
     ("every", "all", "none", "only", "universal", "always", "never"), a **status claim**
     ("complete", "pending", "removed", "supported"), or a **named identifier or version**
     it repeats. Note each statement with its location. Anything stated exactly once is not
     in scope for this check.
  2. **Compare statements about the same subject.** Group the notes by what they describe,
     then compare within each group. Two disagreeing numbers is the obvious hit; the
     costlier one is a **scope word contradicted by the artifact's own detail** — a
     universal claim sitting above a partial breakdown, an "all supported" above a table
     with a gap, a "removed" beside a surviving reference.
  3. **Decide which statement the artifact's own evidence supports.** Prefer the
     **enumerated detail** — the table, the list, the breakdown, the code — over the
     summary that restates it: the summary is the derived form and is usually the one that
     drifted. Say in the finding which statement the evidence supports and why, so the fix
     is unambiguous.
  4. **Set severity deliberately.** Default to `inconsistency` (advisory). Escalate to
     `error` only when the contradiction is **decision-bearing** — a reader acting on the
     wrong statement takes a materially different action, or the wrong statement is copied
     into generated output, a published artifact, or a gate. An inaccuracy confined to a
     comment, a docstring, or test narration stays at `inconsistency` under the severity
     floor. Quote both locations verbatim in the finding. **Report, do not repair.**
```

**Traceability.** REQ-CONS-01 for the impl checklist ("front matter vs body, summary
block vs prose"), with the F-5 artifact as the motivating example (PRD §1). Step 4's
severity rule is the "Severity floor (anti-churn)" paragraph in
`skills/forge-verify/SKILL.md` Step 3 restated in-check, not a new convention.

### 3.4 `CHECK-S39` — Internal Consistency, specs mode (REQ-CONS-01)

Paste at the end of
`skills/forge-verify/references/verification-checklists/specs.md`:

```markdown
### Internal Consistency

> **When this fires:** on any single spec document that states the same quantity, scope
> claim, or status **in more than one place** — a Requirement Coverage table vs the
> sections it points at, a summary or overview paragraph vs the detail below it, a
> Dependencies list vs the cross-references in the body, a stated count of documents or
> types vs the list actually enumerated. It is **intra-document**: a contradiction
> *between* two spec documents is already covered by the tech-spec-consistency and
> cross-reference checks above. A document that states each quantity exactly once yields
> **not-applicable**.

- [ ] **CHECK-S39**: **One document, one answer — a quantity or claim restated inconsistently inside a single spec** (#170).
  *Verifier judgment — read and compare; no extractor runs (deliberately, this milestone).
  **not-applicable** when nothing is restated. Severity defaults to `inconsistency`
  (advisory) and escalates to `error` only when the contradiction is decision-bearing, per
  the severity conventions in the verify skill.* A spec document can contradict itself
  while every cross-document check passes: in the incident behind this check, one artifact
  asserted a claim held **universally**, while its own body — two sections below — stated
  the correct **4-of-7** breakdown. The summary was the part downstream artifacts copied.
  Verify by comparing the document against itself:
  1. **Collect the restatements.** Note every place the document states a **count or
     total** ("five documents", "N of M", "all three subcommands"), a **scope claim**
     ("every", "all", "none", "only", "universal", "always", "never"), a **status claim**
     ("out of scope", "deferred", "removed", "required"), or a **repeated identifier**
     (a type name, a file path, a requirement id, a constant's value). Record each with its
     location. Anything stated exactly once is not in scope for this check.
  2. **Compare statements about the same subject.** Group by subject and compare within
     each group. Watch specifically for: a Requirement Coverage table row pointing at a
     section that no longer makes that claim; a count in an overview that disagrees with
     the list enumerated below it; a scope word ("all", "universal", "never") that the
     document's own breakdown contradicts; a constant given one value in a type definition
     and another in prose.
  3. **Decide which statement the document's own evidence supports.** Prefer the
     **enumerated detail** — the table, the type definition, the numbered list — over the
     summary that restates it. Name in the finding which statement the evidence supports,
     so the fix does not have to re-derive it.
  4. **Set severity deliberately.** Default to `inconsistency` (advisory). Escalate to
     `error` only when the contradiction is **decision-bearing**: an implementer building
     from the wrong statement writes different code, or the wrong statement is what a
     downstream artifact or generated output copies. Quote both locations verbatim.
     **Report, do not repair.**
```

**Traceability.** REQ-CONS-01 for the specs checklist. `CHECK-S08` and `CHECK-S12` cover
contradictions *across* documents; `CHECK-S39` is the intra-document complement, which
is why the preamble says so explicitly (both are same-mode ids and safe to name here).

**Cross-mode-leak warning.** This entry must not name `CHECK-I25` — see §5.1. The two
entries are intentionally near-duplicates that cannot reference each other.

## 4. `skills/forge-verify/SKILL.md` — three anchors, zero net new lines

The forge-verify body is at **298/300 lines** and **4447/5000 words** as measured by
`scripts/check-spec-purity.py` (front matter is lines 1–6; body is everything after,
minus a trailing empty line — 304 total file lines − 6 = 298). C-4 leaves 2 lines of
headroom that this change **does not spend**: all three edits are performed **in place**,
each replacing N lines with exactly N lines.

### 4.1 Why the ownership tags matter (not cosmetic)

Large modes do **not** dispatch one verifier over the whole checklist. The dispatch
section says so:

> Each instance owns a disjoint slice of CHECK-IDs, so it verifies deeper over a
> narrower scope and they all run concurrently.

and the per-instance prompt is required to carry "the **exact CHECK-IDs it owns**". The
slices are derived from the dimension-group bullets. A CHECK id that belongs to **no**
group's cluster is therefore **silently never executed** in the mode's normal (fan-out)
path — no error, no warning; the mode simply reports fewer checks than its expected
total, which reads as ordinary verifier undercounting. `CHECK-I21`/`I22` already carry an
explicit `(owns CHECK-I21/I22 — …)` tag on the impl *runnability* group for exactly this
reason; the three new tags below extend that established format so the four new checks
are reachable.

Group assignment (fixed by `01-architecture-layout.md` §4.1):

| New check | Mode | Owning dimension group |
|---|---|---|
| `CHECK-B29` | backlog | (3) *spec coverage & traceability* |
| `CHECK-I24`, `CHECK-I25` | impl | (1) *requirement coverage vs specs* |
| `CHECK-S39` | specs | (3) *cross-reference & traceability* |

`CHECK-I24` and `CHECK-I25` share one group deliberately: both ask "does this artifact's
own claim survive contact with what it claims about", and splitting them across groups
would duplicate the same artifact reads in two parallel instances.

### 4.2 Replacement 1 — the "Large modes" dispatch-size bullet

Anchor: the bullet immediately following **"Small modes (prd 15, tech 17): single
verifier."** One line → one line, identical character count (each of the three numbers
grows within the same width class: `38`→`39`, `28`→`29`, `23`→`25`).

**Before**

```
- **Large modes (specs 38, backlog 28, impl 23): parallel dimensioned fan-out.**
```

**After**

```
- **Large modes (specs 39, backlog 29, impl 25): parallel dimensioned fan-out.**
```

Net lines: **0**. Net words: **0**.

### 4.3 Replacement 2 — the three dimension-group bullets

All three are appends of an ownership tag with **in-place re-wrapping**: the bullet's
text grows, but the same number of physical lines is emitted. Apply each as a whole-block
replacement so the re-wrap is unambiguous.

#### 4.3a specs group — append `(owns CHECK-S39)` to group (3)

**Before** (3 lines)

```
  - **specs** (`references/verification-checklists/specs.md`): (1) types/contracts,
    (2) architecture/layout, (3) cross-reference &
    traceability, (4) testing strategy, (5) integration.
```

**After** (3 lines)

```
  - **specs** (`references/verification-checklists/specs.md`): (1) types/contracts,
    (2) architecture/layout, (3) cross-reference & traceability (owns CHECK-S39),
    (4) testing strategy, (5) integration.
```

Line 1 is untouched. Lines 2–3 absorb the tag by pulling `traceability,` up onto line 2
(the existing wrap point was already mid-phrase). Longest changed line: 81 characters
(line 2); line 1 is untouched at 83.
Net lines: **0**. Net words: **+2**.

#### 4.3b backlog group — append `(owns CHECK-B29)` to group (3)

**Before** (3 lines)

```
  - **backlog** (`references/verification-checklists/backlog.md`): (1) item scoping &
    acceptance criteria, (2) dependency/ordering sanity,
    (3) spec coverage & traceability, (4) schema/enum correctness.
```

**After** (3 lines)

```
  - **backlog** (`references/verification-checklists/backlog.md`): (1) item scoping &
    acceptance criteria, (2) dependency/ordering sanity,
    (3) spec coverage & traceability (owns CHECK-B29), (4) schema/enum correctness.
```

Only line 3 changes; it grows from 66 to 83 characters. Net lines: **0**. Net words: **+2**.

#### 4.3c impl group — append `(owns CHECK-I24/I25)` to group (1)

The impl bullet's existing wrap is uneven (line 1 is 124 characters, line 3 is 57), so
the recommended replacement **rebalances across the same three lines** rather than
pushing line 1 to 145 characters.

**Before** (3 lines)

```
  - **impl** (`references/verification-checklists/impl.md`): (1) requirement coverage vs specs, (2) integration correctness,
    (3) testing, (4) code-quality/conventions, (5) runnability (owns CHECK-I21/I22 —
    the smoke command and the non-test-caller heuristic).
```

**After** (3 lines — recommended)

```
  - **impl** (`references/verification-checklists/impl.md`): (1) requirement coverage vs specs (owns CHECK-I24/I25),
    (2) integration correctness, (3) testing, (4) code-quality/conventions,
    (5) runnability (owns CHECK-I21/I22 — the smoke command and the non-test-caller heuristic).
```

Resulting line lengths 116 / 75 / 95 — all at or below the 124-character maximum this
bullet block already contains, so no new line-width precedent is set. The em dash in
`CHECK-I21/I22 — the smoke command` is preserved verbatim (U+2014). Net lines: **0**.
Net words: **+2**.

*Minimal-diff alternative*, if a reviewer prefers a single-line edit: append
` (owns CHECK-I24/I25)` directly after `(1) requirement coverage vs specs` on line 1 and
leave lines 2–3 byte-identical. Also zero net lines; the only cost is a 145-character
line. Either form satisfies §9's checkboxes.

### 4.4 Replacement 3 — Step 3's per-mode expected totals

Anchor: the sentence beginning "If your count is significantly below the expected total
for the mode" in **Step 3: Run Verification Checklists**. This is a **substring**
replacement inside one long paragraph line — replace the parenthetical only, do not
re-wrap the paragraph.

**Before**

```
(prd: 15 checks, tech: 17 checks, specs: 38 checks, backlog: 28 checks, impl: 23 checks, epic: 10 checks)
```

**After**

```
(prd: 15 checks, tech: 17 checks, specs: 39 checks, backlog: 29 checks, impl: 25 checks, epic: 10 checks)
```

Identical character count. Net lines: **0**. Net words: **0**.

`tests/test_verification_checklists_split.py::test_skill_expected_count_table_matches_the_files`
reads these numbers back out of the SKILL and compares them to the ids **counted from
the checklist files** (not to its own `EXPECTED` table), so this edit and §3's edits must
land together or that test goes red in whichever direction drifted. It also rejects a
`~` hedge before the number — write the bare integer.

### 4.5 Budget arithmetic after all three edits

| Metric | Before | After | Cap |
|---|---|---|---|
| Body lines | 298 | 298 | 300 (`MAX_BODY_LINES`) |
| Body words | 4447 | 4453 (+6: three two-word tags) | 5000 (`MAX_BODY_WORDS`) |

`python3 scripts/check-spec-purity.py` must still report `spec-purity: PASS`. The two
lines of headroom C-4 records remain unspent and available to a later change.

## 5. ID Discipline and Test-Surface Interactions

### 5.1 Contiguity and cross-mode leakage (binding, enforced)

`tests/test_verification_checklists_split.py` imposes three hard rules on id assignment.
Its id scanner is `re.findall(rf"CHECK-{letter}\d\d", text)` over the **whole file**, so
every mention counts — prose cross-references included.

1. **Contiguity.** Each mode file's unique id set must equal `CHECK-X01 … CHECK-X{count}`
   with no gaps. Current maxima (confirmed against the live tree): `B28`, `I23`, `S38`.
   The new ids are therefore forced: `B29`, `I24`, `I25`, `S39` — next-in-sequence,
   zero-padded to two digits. No other numbering is legal.
2. **No cross-mode leakage.** A mode file may not contain **any** other mode's id
   pattern. Practical consequences for §3's prose:
   - `impl.md` may reference `CHECK-I01`, `CHECK-I21`, `CHECK-I22` (same mode) but must
     **never** name `CHECK-S39`, `CHECK-B29`, or any `CHECK-P`/`CHECK-T`/`CHECK-E` id.
   - `specs.md` may reference `CHECK-S08`/`CHECK-S12` but must **never** name
     `CHECK-I25`.
   - `backlog.md` may reference `CHECK-B…` ids only.
   This is why `CHECK-I25` and `CHECK-S39` — deliberate near-duplicates serving one
   requirement — carry no pointer to each other. The relationship is recorded here, in
   this spec, instead.
3. **Inventory total.** `test_split_preserves_the_full_check_inventory` asserts the six
   files sum to a pinned total; it moves `131 → 135` (+1 backlog, +2 impl, +1 specs).

### 5.2 Pinned tests that move in lockstep (pointer only — see `05-testing-strategy.md`)

This document does **not** specify the test edits; it names them so the implementer
knows nothing else is hiding. Full specification: `05-testing-strategy.md`.

| Test file | Pinned literal(s) | Moves to |
|---|---|---|
| `tests/test_dev_runtime_smoke.py` | `"impl: 23 checks"`, `"impl 23"` | `25` |
| `tests/test_smoke_command.py` | `"impl: 23 checks"`, `"impl 23"` | `25` |
| `tests/test_lifecycle_artifact_check.py` | `"backlog: 28 checks"`, `"backlog 28"` | `29` |
| `tests/test_verification_checklists_split.py` | `EXPECTED` rows `specs 38` / `backlog 28` / `impl 23`, and the `131` inventory total | `39` / `29` / `25`, total `135` |

Note the `"impl 23"` and `"backlog 28"` literals are satisfied by §4.2's **Large modes**
bullet, and the `"impl: 23 checks"` / `"backlog: 28 checks"` literals by §4.4's Step 3
parenthetical — one test literal per anchor, which is why both edits are mandatory
rather than either/or.

**End-of-file placement is test-safe.** `test_dev_runtime_smoke.py::_runnability()` and
`test_smoke_command.py::test_runnability_checks_degrade_gracefully()` both slice
`impl.md` as `text.split("### Runnability", 1)[1]` — from that heading to end of file —
and then assert **membership only** (`"not-applicable" in …`, `"never a hard fail" in …`,
`"never mid-loop" in …`, `"smokeCommand" in …`, `"non-test" in …`, plus a
`**CHECK-I23**`-anchored sub-slice). Appending §3.2 and §3.3 after `### Runnability`
grows that slice but cannot falsify a membership assertion, so both tests stay green
without modification. Three comments state a "last section" claim that becomes stale:
the two "`### Runnability` is impl.md's last section" comments in those files, and
`tests/test_lifecycle_artifact_check.py`'s comment that `backlog.md` ends with
`### Artifact Lifecycle Consistency` (its
`text.split("### Artifact Lifecycle Consistency", 1)[1]` slice is likewise
membership-only and stays green). Refreshing them is an editorial item for
`05-testing-strategy.md` — and per its D3 resolution the two impl slices are also
heading-terminated so the guards keep their bite. (Alternative, if a reviewer prefers
the slice to stay byte-identical: insert both new impl sections *before* `### Runnability`.
That is also legal — the contiguity test sorts ids and is indifferent to document order —
at the cost of non-monotonic section ordering. The recommendation stands at end-of-file.)

### 5.3 Prose literals the guards will pin

`05-testing-strategy.md` specifies prose guards over the new entries (tech-spec §8:
"CHECK-B29/I24/I25/S39 present in their checklist files with their degradation clauses").
§3's prose therefore **guarantees these literals**, and an implementer rewording must
preserve them:

| Entry | Guaranteed literals |
|---|---|
| `CHECK-B29` | `**CHECK-B29**`, `not-applicable`, `never a hard fail`, `by name`, `` `gap` ``, `Report, do not repair` |
| `CHECK-I24` | `**CHECK-I24**`, `not-applicable`, `never a hard fail`, `by name`, `` `gap` ``, `Report, do not repair` |
| `CHECK-I25` | `**CHECK-I25**`, `not-applicable`, `` `inconsistency` ``, `` `error` ``, `decision-bearing`, `Report, do not repair` |
| `CHECK-S39` | `**CHECK-S39**`, `not-applicable`, `` `inconsistency` ``, `` `error` ``, `decision-bearing`, `Report, do not repair` |

Each entry also contains its issue citation `(#170)`.

## 6. Degradation and Severity Matrix (error handling for a prose check)

These checks execute no operations that can raise — their "error handling" is the
**degradation and severity contract**, which is what makes them safe to run on every
artifact set. Every row is normative.

| Situation | `CHECK-B29` / `CHECK-I24` | `CHECK-I25` / `CHECK-S39` |
|---|---|---|
| Trigger structure absent (no declared list / nothing restated) | **not-applicable**, recorded as such. Never a hard fail (REQ-CARD-04) | **not-applicable**, recorded as such |
| Trigger present, no discrepancy found | **pass** — record that the set was re-derived and matched | **pass** — record that restatements were compared and agreed |
| A member of the re-derived set is missing from the list | `gap` (blocking), omission named | n/a |
| A list entry names a non-existent member (stale) | `inconsistency` (advisory) | n/a |
| A stated total disagrees with an otherwise complete list | `inconsistency` (advisory) | `inconsistency` (advisory) |
| Two statements of the same quantity disagree | n/a | `inconsistency` (advisory) by default |
| The contradiction is decision-bearing (different action, or copied into generated/published output or a gate) | n/a | escalate to `error` |
| The inaccuracy is confined to a comment, docstring, or test narration | n/a | stays `inconsistency` (severity floor) |
| The source of record for re-derivation cannot be determined | Report as `improvement`: state that the list's coverage claim is unverifiable and name what source of record would make it checkable. Never guess a set and never fail on the ambiguity | n/a |
| The artifact is silent on which restatement is correct | n/a | Still report; state which statement the enumerated detail supports and mark the other as the suspect. Do not invent a third answer |

The `gap` / `error` = **blocking**, `inconsistency` / `improvement` = **advisory**
routing is the existing convention in `skills/forge-verify/SKILL.md` Step 3 ("Severity
floor (anti-churn)") — these checks consume it, they do not extend it. Consequently a
`CHECK-B29`/`CHECK-I24` omission routes the report to `findings-reported` → forge-fix,
while a lone `CHECK-I25`/`CHECK-S39` inconsistency records `passed` with the report
attached and the pipeline advances.

## 7. Worked Examples

These are illustrations for the implementer, not text to paste.

### 7.1 A `CHECK-I24` hit (the motivating 15-of-16 incident)

> **V-004** — `gap` — **Work order omits one artifact from the set it claims to cover**
> **Location:** `plans/closeout-work-order.md` § "Per-artifact review (16 artifacts)"
> **What's wrong:** The work order's heading claims coverage of 16 artifacts and
> enumerates 15 entries. Re-deriving the set from the directory listing of
> `data/providers/` yields 16 members; the entry for `data/providers/aurora.md` is
> absent. Nothing else in the closeout references that file, so it would have been
> published unreviewed.
> **Suggested fix:** Add a per-artifact review entry for `data/providers/aurora.md` and
> execute it before the closeout completes.
> **Checklist:** CHECK-I24

Note what makes this compliant: the omission is named (`aurora.md`), the source of record
is named (`data/providers/` listing), and the finding does not say "one short".

### 7.2 A `CHECK-S39` / `CHECK-I25` hit (the F-5 self-contradiction)

> **V-007** — `error` — **Document contradicts itself about the scope of a claim**
> **Location:** `data/providers/aurora.md` § Summary (line 12) vs § Regional Coverage
> (line 48)
> **What's wrong:** The Summary states the capability is "universal among the tracked
> hyperscalers"; § Regional Coverage two sections below enumerates 4 of 7 with the
> capability and 3 without. The enumerated breakdown is the evidence; the Summary is the
> restatement and is wrong. Escalated to `error` rather than `inconsistency` because the
> Summary sentence is the text copied into `src/generated/coverage.ts`, so the false
> claim reaches shipped output.
> **Suggested fix:** Replace the Summary sentence with the 4-of-7 form the Regional
> Coverage section states, then check for surviving copies of the old sentence elsewhere.
> **Checklist:** CHECK-S39

Note the severity reasoning is explicit (decision-bearing → copied into generated
output), and the finding names which of the two statements the evidence supports.

## 8. Dependencies

**Must be read/implemented first:**

- `00-core-definitions.md` **§9** — the authoritative CHECK id / file / section /
  severity table and the "next-in-sequence, host-neutral, degrade to not-applicable"
  contract. This document expands §9; it does not redefine it. Where anything here
  appears to disagree with §9, §9 wins.
- `01-architecture-layout.md` **§2** (file inventory rows 4–7), **§4.1** (the three
  SKILL edit anchors and the C-4 budget), **§4.3** (checklist files are uncapped), and
  **§5.2** (host-neutrality under adapter regeneration).

**Independent of:**

- `02-fix-sweep-script.md` and `03-forge-fix-integration.md`. Per
  `01-architecture-layout.md` §3 the checklist chain and the script chain are two
  independent branches — this document's work can be implemented **in parallel** with
  both. It shares no symbol, no file, and no ordering constraint with them.

**Joins the other chain at exactly one point:** the single `adapters/**` regeneration
(`python3 scripts/build-adapters.py`), which per `01-architecture-layout.md` §3 runs
**once, after all canon edits land** — so the drift gate (`validate.sh` step 6b) sees one
consistent regeneration. Do not regenerate adapters as part of this document's work in
isolation.

**Consumed by:** `05-testing-strategy.md` (prose guards over §3's literals, and the four
pinned-count test edits listed in §5.2).

## 9. Verification

Structural:

- [ ] **Contiguity.** `python3 -m pytest tests/test_verification_checklists_split.py`
      passes with `EXPECTED` at `specs 39 / backlog 29 / impl 25` and the inventory total
      at `135`; the new ids are exactly `CHECK-B29`, `CHECK-I24`, `CHECK-I25`,
      `CHECK-S39` — next-in-sequence, no gaps, two-digit padded.
- [ ] **One mode file per id.** Each new id appears in exactly **one** checklist file
      (`grep -rl "CHECK-B29\|CHECK-I24\|CHECK-I25\|CHECK-S39"
      skills/forge-verify/references/verification-checklists/` returns `backlog.md`,
      `impl.md`, `specs.md` and nothing else), and no mode file names another mode's id.
- [ ] **One ownership tag per id.** Each new id appears in exactly one dimension-group
      bullet in `skills/forge-verify/SKILL.md`: `CHECK-B29` on the backlog *(3) spec
      coverage & traceability* group, `CHECK-I24/I25` on the impl *(1) requirement
      coverage vs specs* group, `CHECK-S39` on the specs *(3) cross-reference &
      traceability* group. No new check is left owned by no group.

Budget and purity:

- [ ] **Line count unchanged.** The forge-verify body is still **298** lines
      (`wc -l skills/forge-verify/SKILL.md` = 304; body = 304 − 6 front-matter lines) and
      `python3 scripts/check-spec-purity.py` reports `spec-purity: PASS`.
- [ ] **Each replacement is line-for-line.** Replacement 1 replaces 1 line with 1;
      replacements 2a/2b/2c each replace 3 lines with 3; replacement 3 is a substring edit
      inside a single existing line.

Consistency:

- [ ] **Totals agree in both SKILL anchors and with the files.** The "Large modes" bullet
      reads `specs 39, backlog 29, impl 25`, the Step 3 parenthetical reads
      `specs: 39 checks, backlog: 29 checks, impl: 25 checks`, and
      `test_skill_expected_count_table_matches_the_files` (which counts ids out of the
      checklist files) passes against both.
- [ ] **Pinned literals moved.** `tests/test_dev_runtime_smoke.py`,
      `tests/test_smoke_command.py`, and `tests/test_lifecycle_artifact_check.py` pass
      with their updated literals (`05-testing-strategy.md`).

Host-neutrality (C-5):

- [ ] **Zero host terms in the new prose.** No product name, host tool name, question or
      dispatch tool name, slash command, or plugin command prefix appears in any of §3's
      pasted blocks — checked before regeneration by reading the diff, and after
      regeneration by `python3 -m pytest tests/test_adapter_host_neutrality.py`.
- [ ] **No double-article artifact.** After regeneration, `grep -rn "the the "
      adapters/*/skills/forge-verify/references/verification-checklists/` returns nothing.

Behavioral (executable spot-checks):

- [ ] **Degradation.** Running backlog mode against a backlog with no declared work list
      records `CHECK-B29` as **not-applicable**, not a failure; running impl mode against
      an implementation with no work order or registry does the same for `CHECK-I24`
      (REQ-CARD-04).
- [ ] **Named omission.** Running impl mode against an artifact set with a 15-of-16 work
      order produces a `gap` finding naming the missing sixteenth member by path — not a
      count delta.
- [ ] **Self-contradiction.** Running specs mode against a document whose summary states
      a universal claim contradicted by its own breakdown produces a `CHECK-S39` finding
      at `inconsistency`, escalated to `error` only when the summary text is what a
      downstream or generated artifact copies.

Full gate (`01-architecture-layout.md` §5.4): `bash scripts/validate.sh` and
`ruff check scripts/ eval/` green, adapters regenerated with no drift.
