# 03 — forge-fix Integration

> The exact prose additions to `skills/forge-fix/SKILL.md` that wire `scripts/fix-sweep.py`
> into the fix pass: a plan-coverage gate in **Step 2**, the corrected-claim sweep and its
> dispositions as the closing sub-steps of **Step 4**, and enumerated disposition staging in
> **Step 5**. Every block below is written ready to paste, in forge-fix's own voice.
>
> **No step renumbering.** Steps 1–7 keep their numbers. `references/stage-exit-protocol.md`
> cites "`skills/forge-fix/SKILL.md` Step 6" (verified in the live tree at line 458, inside
> the "Re-verify scope and convergence" section) and that citation must stay valid — so this
> document adds **no new step heading** and moves nothing.
>
> Shared vocabulary lives in `00-core-definitions.md`; the CLI this document invokes is
> specified in `02-fix-sweep-script.md`. Anchors below are quoted **text**, never line
> numbers — line numbers in the live skill will drift.

## Requirement Coverage

| REQ ID | Requirement | Section |
|---|---|---|
| REQ-CARD-01 | Fix Execution Plan covers every finding; omissions named | §3 (Step 2 addition) |
| REQ-SWEEP-01 | Sweep runs after fix steps, before the pass closes | §4.1 (placement + invocation) |
| REQ-SWEEP-04 | Every survivor dispositioned before the pass closes | §4.3 (three-way disposition), §4.4 (re-run) |
| REQ-SWEEP-05 | Sweep results + dispositions recorded in the findings document | §4.2 (sweep record), §5 (it rides Commit 1) |
| REQ-SWEEP-06 | Outcome routing uses existing rows only | §6 |
| REQ-SWEEP-07 | Skip is visible, never silent | §4.5 (NOT RUN notice) |
| REQ-OBS-01 | Hits name file, location, matched text — no re-derivation | §4.3 (disposition prose relies on it) |
| (C-1) | R-06 / the re-verify is untouched | §1.2, §9 |
| (C-4) | forge-fix body stays under the 300-line cap | §7 (line budget) |
| (C-5) | Prose survives the host-term translation pass | §8 |
| (C-6) | No new `--outcome` values, no schema/config change | §6, §9 |

## 1. Integration Contract

### 1.1 What this document changes

Exactly one file: `skills/forge-fix/SKILL.md` (inventory row 3 in
`01-architecture-layout.md` §2). Three insertions, all **inside existing steps**:

| # | Step | What lands | REQ |
|---|---|---|---|
| A | Step 2 — *Parse Fix Execution Plan* | A new numbered item 4: run `plan-coverage`, route exit 1 through the question mechanism | REQ-CARD-01 |
| B | Step 4 — *Execute Fix Steps* | Closing sub-steps at the end of the step: run `sweep`, disposition every hit, record it, re-run once, never skip silently | REQ-SWEEP-01/04/05/07 |
| C | Step 5 — *Record the Fixes Through `state-verify` and Commit* | One paragraph requiring enumerated `git add <path>` for disposition-edited files before Commit 1 | REQ-SWEEP-05 |

No headings are added, renamed, or renumbered. No existing sentence is deleted or
rewritten; every block is an **insertion** at a quoted anchor (§2).

### 1.2 Why Steps 2/4/5 and not "Steps 5/6"

The PRD's parenthetical "forge-fix Steps 5/6" (PRD §1, REQ-SWEEP-01 Notes, C-1) is
superseded by tech-spec §3.6 and needs no PRD edit. C-1's binding content is that the sweep
lives in the **fix pass** and never in the **re-verify** — Steps 2, 4, and 5 all satisfy
that. The pre-Commit-1 placement follows from the delta definition in
`00-core-definitions.md` §3: the delta is `git diff HEAD` taken while the tree is dirty, so
the sweep must run **before** Step 5 commits, and the sweep record — which lives under
`{resolvedFeatureDir}/.verification/` — then rides Commit 1 with the fixes it documents.

**Step 6 is untouched.** The re-verify gate keeps its scope per "Re-verify scope and
convergence" in `references/stage-exit-protocol.md` (R-06): confirm the prior report's
findings against their acceptance evidence and examine the fix delta — never a fresh
full-checklist sweep. The corrected-claim sweep is *not* a checklist sweep and does not run
there; it has already run and closed out in Step 4 by the time Step 6 is reached.

### 1.3 Invariants an implementation must not break

1. **Exactly one close.** The pass still invokes the Scripted Stage Exit exactly once, in
   Step 7. Nothing added here closes a stage, prints a terminal block, or short-circuits
   Step 7.
2. **Existing outcome rows only** (C-6). §6 maps every new situation onto rows that already
   exist in the Step 7 table.
3. **The script never writes.** `fix-sweep.py` is read-only over the corpus
   (`00-core-definitions.md` §1, REQ-CONC-01). The **agent** authors the sweep record; the
   prose must say so implicitly by instructing the agent to append it.
4. **Anchors are text.** An implementer locates each insertion point by the quoted sentence
   in §2, not by line number.

## 2. Anchor Map

| Block | Insert **immediately after** this existing text | Insert **immediately before** |
|---|---|---|
| A (Step 2) | `3. Check for a ` `` `## Fix Progress` `` ` section at the bottom of the findings document — if present, some steps were already applied in a previous interrupted run` | the `## Step 3: Handle User Decisions` heading |
| B (Step 4) | `The evidence — what was probed, how, with what result — belongs in the findings document's ` `` `## Fix Progress` `` ` entry (and the commit message), which are the sanctioned records for acceptance evidence.` (the last sentence of the anti-churn paragraph) | the `## Step 5: Record the Fixes Through ` `` `state-verify` `` ` and Commit` heading |
| C (Step 5) | the closing ```` ``` ```` of Step 5's `state-verify` fence | the `Then follow the Git Commit Protocol in ` `` `references/shared-conventions.md` `` `.` paragraph |

Each insertion is separated from its neighbours by one blank line (already counted in the
line budgets in §7).

**Placement notes that matter mechanically:**

- Block A's fenced invocation sits at the **left margin**, not indented under the list item.
  Two `scripts/check-spec-purity.py` rules bind: rule 6 requires an `^R=` assignment anchored
  at column 0 inside every runnable shell fence (shell variables do not survive across
  fences), and rule 5 pins the prelude byte-identical to canon — an indented fence is not
  even recognized by rule 6's column-0 fence scanner, and its indented second prelude line
  trips rule 5 as `bootstrap prelude not byte-identical to canon`. The existing Step 5
  fences are at the margin for the same reason — match them.
- Block B goes **after** the anti-churn paragraph so the sweep is literally the last thing
  Step 4 says, matching "closing sub-steps" (tech-spec §3.6). It is prose, not a numbered
  item: Step 4's list is *per fix step* ("For each step in the 'Execution Steps' section, in
  order:") and the sweep runs **once**, after the last one.
- Block C goes **before** the Git Commit Protocol paragraph, so the enumerated staging is
  read before the stage-and-commit instruction it qualifies — an agent executing Step 5
  linearly must see "stage the disposition-edited paths" before it reaches the sentence
  that stages and commits.

## 3. Block A — Step 2 Plan-Coverage Gate (REQ-CARD-01)

### 3.1 Rationale trace

REQ-CARD-01 requires the fix pass to assert that the Fix Execution Plan **covers every
finding**, with omissions reported **by name** and claimed totals re-derived. Tech-spec §3.5
puts that assertion in `fix-sweep.py plan-coverage`; tech-spec §3.6 places the invocation in
Step 2 **so an incomplete plan is caught before any fix executes** — the 15-of-16 incident
class is an agent miscount, and C-2 forbids resolving it with agent judgment. Exit codes and
the payload are fixed by `00-core-definitions.md` §6.2/§6.3; `applicable: false` is the
REQ-CARD-04 analog at the fix-pass level.

### 3.2 Prose to insert (paste-ready)

````markdown
4. **Assert the plan covers every finding** before any fix executes. Exit 1 is that assertion firing, not a tool failure; only exit 2 is a tool failure. Run:

```bash
R="$(bash -c 'for d in "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/fix-sweep.py" plan-coverage "{resolvedFeatureDir}/.verification/{findingsFile}" --json
```

Exit 0 with `"applicable": false` means the document declares no findings set or no plan to assert — proceed silently. Exit 1 → surface the **named** uncovered findings and any `claimed N, actual M` total mismatch, then resolve each one through `AskUserQuestion` per the **Decision Support** protocol in `references/shared-conventions.md`: either **author a covering execution step** into the Fix Execution Plan and execute it in this pass's Step 4, or **record an explicit justification** against that finding in the findings document. Never resolve a mismatch by editing the claimed total to match — re-derive which finding is missing and name it. Any finding still uncovered when you stop closes with `decisions` in Step 7, no advancement. Exit 2 → surface the `Error:` line verbatim and close with `failed`.
````

### 3.3 Substitutions

| Placeholder | Meaning | Established by |
|---|---|---|
| `{resolvedFeatureDir}` | The resolved feature directory | Step 1.2 of the live skill (existing placeholder — reused verbatim) |
| `{findingsFile}` | The `VERIFY-{mode}-{YYYY-MM-DD}.md` report selected in Step 1.2 | Step 1.2 ("find the most recent `VERIFY-*-*.md` file") |

The prelude is copied **byte-identical** from the existing Step 5 / Step 7 fences (rule 5 of
`check-spec-purity.py` compares it against canon and fails on any drift). No `--repo-root`,
no other flags.

### 3.4 Error handling

| Condition | Payload / signal | Required agent behavior | Outcome |
|---|---|---|---|
| Fully covered, totals consistent | exit 0, `uncovered: []`, `totalMismatch: false` | Proceed to Step 3 | (unchanged) |
| No `## Findings` or no `## Fix Execution Plan` | exit 0, `applicable: false` | Proceed **silently** — say nothing, assert nothing | (unchanged) |
| Uncovered findings and/or claimed-total mismatch | exit 1, `uncovered: [...]`, `totalMismatch: true` | Surface names + `claimed N, actual M`; resolve via the question mechanism: author a covering step (executed this pass) **or** record an explicit justification | (unchanged) if resolved |
| Resolution not obtained (deferred, no answer, question mechanism unavailable) | — | Do not proceed as though covered | `decisions` |
| Missing/unreadable document, bad flags | exit 2, `Error: …` on stderr | Surface the line verbatim | `failed` |

**Anti-pattern the prose names explicitly:** "resolve" a mismatch by editing
`Total findings: N` in `## Summary` down to the enumerated count. That erases the evidence of
the omission — exactly the defect REQ-CARD-01 exists to catch. The prose forbids it in one
clause.

## 4. Block B — Step 4 Closing Sub-Steps: the Sweep (REQ-SWEEP-01/04/05/07)

### 4.1 Placement and invocation (REQ-SWEEP-01)

The sweep runs **after the last plan step is applied** and **before Step 5's Commit 1**,
while the working tree is dirty — the delta definition in `00-core-definitions.md` §3
depends on it. The invocation passes **no `--exclude` flags**: the script's conditional
defaults (`00-core-definitions.md` §5.2 — unconditional `.verification`, conditional
`adapters/` gated on `scripts/build-adapters.py` existing at the repo root) are correct in
both this repository and a consumer repository. `--exclude` and `--min-chars` remain
operator escape hatches, deliberately **not advertised in skill prose** (tech-spec §3.6, §5).

**Exit 1 is normal — when a payload came with it.** A survivor-bearing sweep exits 1 by
the standalone-script convention (`00-core-definitions.md` §6.3). The prose says so out
loud because an agent that reads a non-zero exit as a tool failure would close `failed` on
a working sweep. The discriminator: exit 1 **with** a parseable JSON payload on stdout is
the sweep working; exit 1 with **no** JSON object on stdout is a crash, not a finding —
treat it as a tool failure, surface the stderr traceback, and close `failed`
(`02-fix-sweep-script.md` §6; the "never partial" invariant makes the payload's presence a
sound discriminator).

### 4.2 The sweep record (REQ-SWEEP-05)

The record is written by the **agent**, appended under `## Fix Progress` in the findings
document, in the grammar fixed by `00-core-definitions.md` §7.2 — reproduced verbatim in the
paste block below so the skill is self-sufficient at read time. `{K}` is `len(needles)`,
`{N}` is `len(hits)`, `{M}` is the number of disposition lines written; `M == N` whenever the
pass closes on an advancing outcome.

### 4.3 Disposition (REQ-SWEEP-04, REQ-OBS-01)

Every hit gets exactly one of the three tokens from `00-core-definitions.md` §8.1 —
`FIXED`, `JUSTIFIED: {reason}`, `FALSE-POSITIVE: {reason}`. The prose leans on REQ-OBS-01:
each hit already names file, line, and the matched removed text, so disposition needs no
re-derivation. Judgment calls route through `AskUserQuestion` under the **Decision Support**
protocol the skill already cites in Step 3 — recommended option first, trade-off in each
option's description.

### 4.4 Re-run semantics

A `FIXED` disposition edits files, and those edits join the same `git diff HEAD` delta — so a
second sweep sees their removed lines as new needles. The prose therefore requires **one**
re-run when (and only when) a disposition edited files, appends a **second** `- Sweep:`
block, and matches already-dispositioned hits by `(file, matched text)`. That suppression is
**disposition-aware**: a re-run hit whose first-block disposition was `JUSTIFIED` or
`FALSE-POSITIVE` legitimately re-appears and needs no second disposition. A re-run hit whose
first-block disposition was **`FIXED` is a failed fix**, not an already-handled hit — the
edit did not remove every occurrence. Re-disposition it: correct it now (still within the
single re-run) or close `failed`; never leave it recorded as `FIXED`. The loop is capped at
one re-run explicitly: without that cap, a fix that rewrites a sentence can generate a fresh
needle on every pass and never converge — the same divergence hazard R-06 addresses for the
re-verify.

### 4.5 Skip is visible (REQ-SWEEP-07)

`"skipped": true` with exit 0 (reason `not-a-git-repo` or `no-head`,
`00-core-definitions.md` §6.1) is **not** a finding and **not** a failure — but it is also
never silent. The agent appends `- Sweep: NOT RUN — no git delta ({reason})` under
`## Fix Progress`, using the payload's `reason` verbatim, and continues on the pass's normal
outcome. Exit 2 is the opposite case and is stated adjacently so the two are not conflated.

### 4.6 Prose to insert (paste-ready)

````markdown
**Closing sub-step — sweep for surviving occurrences of what you just corrected.** After the last plan step is applied and BEFORE Step 5 commits anything, while the working tree is still dirty, sweep this fix's own delta for text you removed that survives elsewhere. Pass no flags beyond `--json` — the exclusions the script applies by default are the correct ones in both a plugin repository and a consumer repository. Exit 1 means survivors were found: that is the sweep working, not a tool failure. Run:

```bash
R="$(bash -c 'for d in "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/fix-sweep.py" sweep --json
```

**Disposition every hit before Step 5.** Each hit names the file, the line, and the removed text it matched, so nothing needs re-deriving. Give every hit exactly one disposition — `FIXED` (you corrected the survivor now, in this pass, so the edit joins this same delta), `JUSTIFIED: {reason}` (it stands by decision: a deliberate quote, a historical or audit record), or `FALSE-POSITIVE: {reason}` (the match is not the corrected claim) — and record the sweep with its dispositions in the `## Fix Progress` section of the findings document, in this shape:

```
- Sweep: {date} — {K} needle(s), {N} survivor(s), {M} disposition(s)
  - {file}:{line} — "{matched removed text}" → FIXED {date}
  - {file}:{line} — "{matched removed text}" → JUSTIFIED: {reason}
  - {file}:{line} — "{matched removed text}" → FALSE-POSITIVE: {reason}
```

Detection is mechanical; disposition is judgment — a hit is a candidate, not automatically a defect. When you cannot classify a hit confidently, route that hit through `AskUserQuestion` following the same **Decision Support** protocol as Step 3: lead with a recommended disposition and put the trade-off in each option's description. A survivor left awaiting a user decision closes with `decisions` in Step 7; a survivor you can neither fix nor justify closes with `failed`; a fully dispositioned sweep leaves this pass on whatever outcome it otherwise maps to.

**Re-run the sweep once when a disposition edited files.** Those edits joined the same delta, so run the same command again to confirm they introduced no fresh survivors, and append a second `- Sweep:` block for the re-run. A hit already dispositioned `JUSTIFIED` or `FALSE-POSITIVE` — same file, same matched text — legitimately re-appears and needs no second disposition. A re-appearing hit that was dispositioned `FIXED` means the fix did not remove every occurrence: re-disposition it — correct it now, or close with `failed` — never leave it recorded as `FIXED`. One re-run is enough: do not loop. Exit 1 with no JSON payload on stdout is a crash, not survivors — surface the stderr traceback and close with `failed`.

**The sweep is never silent.** When the payload reports `"skipped": true` (exit 0 — no delta was available), append the visible notice `- Sweep: NOT RUN — no git delta ({reason})` under `## Fix Progress`, using the payload's `reason` verbatim, and continue on this pass's normal outcome. A skip is not a failure; exit 2 is — surface its `Error:` line verbatim and close with `failed`.
````

### 4.7 Error handling

| Condition | Payload / signal | Required agent behavior | Outcome |
|---|---|---|---|
| No survivors | exit 0, `skipped: false`, `hits: []` | Append the `- Sweep:` header line with `0 survivor(s)` | (unchanged) |
| Survivors, all dispositioned | exit 1, `hits: [...]` | One disposition line per hit; `FIXED` edits join the delta | (unchanged) |
| A survivor needs a user decision that does not arrive | exit 1 | Do not fabricate a disposition | `decisions` |
| A survivor is neither fixable nor justifiable | exit 1 | Record what was attempted in `## Fix Progress` | `failed` |
| No git delta available | exit 0, `skipped: true`, `reason` set | Append `- Sweep: NOT RUN — no git delta ({reason})` | (unchanged) |
| Git failure inside a valid repo, bad flags | exit 2, `Error: …` on stderr | Surface the line verbatim | `failed` |
| Exit 1 with **no** JSON payload on stdout | crash (unexpected exception) | Surface the stderr traceback; not survivors | `failed` |
| Re-run after `FIXED` edits reports a fresh survivor | exit 1 on the second run | Disposition the new hit in the second `- Sweep:` block; do not start a third round | per the rows above |
| Re-run re-reports a hit dispositioned `FIXED` | exit 1 on the second run | The fix did not land: correct it now, or record the attempt and stop | `failed` if still surviving |

## 5. Block C — Step 5 Enumerated Disposition Staging (REQ-SWEEP-05)

### 5.1 Rationale trace

Commit 1's staging scope is `git add {resolvedFeatureDir}/` (or `{specsDir}/{epic}/` for an
epic member) — the feature directory **only**. A `FIXED` disposition frequently edits a file
*outside* it: the F-5 survivors lived in a sibling spec artifact and in `src/generated/*.ts`.
Left unstaged, those fixes (a) do not ride the commit that the findings document says fixed
them, and (b) leave a dirty tree that trips the next stage's dirty-tree check and muddies the
re-verify's delta. Tech-spec §3.2/§3.6 therefore adds enumerated staging here.

**Enumerated, never bulk.** `git add -A` / `git add .` would sweep in unrelated working-tree
changes — including the user's own uncommitted work — into a stage-owned commit. The prose
forbids both by name and requires one `git add <path>` per file recorded as `FIXED` in the
sweep record, which is exactly why the record enumerates paths (§4.2).

### 5.2 Prose to insert (paste-ready)

````markdown
**Stage every disposition-edited path explicitly.** Commit 1's staging scope is the feature directory only, so a survivor you fixed outside it (Step 4's sweep) would otherwise be left uncommitted. Before committing, run one `git add <path>` per file recorded as `FIXED` in the sweep record — enumerated, one path at a time, never `git add -A` and never `git add .`. Those fixes then ride Commit 1 alongside the findings document that records them, and the tree is left clean for the re-verify and for the next stage's dirty-tree check.
````

### 5.3 Error handling

| Condition | Required agent behavior | Outcome |
|---|---|---|
| A `git add <path>` fails (path gone, ignored, outside the repo) | Surface the git error; do not proceed to the commit as though the fix were staged | `failed` (Step 7 row: "a commit … failed") |
| The sweep record lists no `FIXED` path | Stage nothing extra; Commit 1 proceeds unchanged | (unchanged) |
| A `FIXED` path is inside `{resolvedFeatureDir}` already | The explicit `git add` is a harmless no-op; still enumerate it | (unchanged) |

## 6. Outcome Routing — Existing Rows Only (REQ-SWEEP-06, C-6)

**No Step 7 edit is required.** Every situation these three blocks can produce already has a
row in the live outcome table. This section is the mapping an implementer verifies against;
it adds no `--outcome` value, no table row, and no schema change.

| Situation introduced here | Existing Step 7 row (verbatim `--outcome`) | Existing row text it lands on |
|---|---|---|
| `plan-coverage` exit 1 unresolved (Block A) | `decisions` | "User decisions remain unresolved (Step 3)" |
| Survivor awaiting a user decision (Block B) | `decisions` | same row |
| Survivor unfixable / unjustifiable (Block B) | `failed` | "A fix step, a validation, a commit, or a state write failed (Steps 4–6)" |
| `plan-coverage` or `sweep` exit 2 (Blocks A, B) | `failed` | same row |
| A disposition `git add` failed (Block C) | `failed` | same row |
| Every hit dispositioned (Block B) | (unchanged) | whatever the pass otherwise maps to — `applied`, `reverified`, `reverify-findings`, `deferred` |
| Sweep skipped with the NOT RUN notice recorded (Block B) | (unchanged) | the notice is the whole obligation |

Consistent with `00-core-definitions.md` §8.2. Two invariants an implementation must
preserve:

1. An undispositioned survivor blocks every **advancing** close, but never blocks the
   **close itself** — the pass still invokes the Scripted Stage Exit exactly once in Step 7
   (`references/stage-exit-protocol.md`).
2. The `decisions` and `failed` rows are reused **verbatim**; their "Authoritative action"
   cells are not edited to mention the sweep. The existing action text ("Resume `forge-fix`
   naming the unresolved decisions" / "Fix/navigator recovery") already covers these cases,
   and editing the table would cost lines against C-4 for no behavioral gain.

## 7. Line Budget (C-4)

`skills/forge-fix/SKILL.md` measures **134 body lines / 2,941 body words** against
`scripts/check-spec-purity.py`'s `MAX_BODY_LINES = 300` / `MAX_BODY_WORDS = 5000` (measured
in the live tree at authoring time; body = everything after the frontmatter's closing `---`,
trailing blank excluded).

| Block | Content | Lines |
|---|---|---|
| A (Step 2) | item-4 line, blank, `bash` fence (open + 2 prelude + 1 command + close), blank, routing paragraph | **9** |
| B (Step 4) | intro line, blank, `bash` fence (5), blank, disposition lead-in, blank, record-grammar fence (6), blank, disposition/routing paragraph, blank, re-run paragraph, blank, skip paragraph | **22** |
| C (Step 5) | staging paragraph, blank separator | **2** |
| | **Total added** | **33** |

**Projected: 167 / 300 body lines** — 133 lines of headroom. Words added are approximately
**+680** (the paragraphs are long unwrapped lines, the repo's SKILL.md idiom; the
disposition-aware re-run and crash-discriminator clauses extend existing lines without
adding any), projecting **≈3,620 / 5,000 body words**.

Two budget notes:

- Tech-spec §3.6 estimated "~25–35 lines including **one** fenced invocation block". The
  implementation needs **two** runnable `bash` fences (one per subcommand, in different
  steps) because `check-spec-purity.py` rule 6 requires each shell fence to bind `$R`
  in-fence — variables do not survive across fences. At 6 lines per fence the total is still
  33, inside the estimated range; the estimate's *range* holds, its *parenthetical* does not.
- Line counts are what CI's Quality Gate measures. Keep each paragraph a **single unwrapped
  line** — hard-wrapping the four prose paragraphs at 100 columns would add roughly 20 more
  lines for zero content.

Confirm after editing with `python3 scripts/check-spec-purity.py` (CI's Quality Gate runs it;
plain `pytest` does not).

## 8. Host-Translation Constraints (C-5)

`skills/forge-fix/SKILL.md` **is** host-translated per adapter by
`scripts/build-adapters.py` step 2c. Two rules the prose above obeys:

1. **Only host terms the skill already uses.** The sole host term introduced is
   `AskUserQuestion`, which the live skill already carries in the Turn-structure reminder,
   Step 3, and Step 6 — it translates automatically, exactly as it does there. Nothing else
   in the added prose names a host construct (no dispatch mechanism, no tool name, no
   session concept).
2. **Use, never mention.** Reference prose that *mentions* a host term (rather than using it
   as an instruction) garbles under translation. The added prose only ever **uses**
   `AskUserQuestion` as a routing instruction — it never talks *about* it — so no exemption
   is needed.

The fenced blocks use the standard plugin-root prelude, which the build already handles for
every other skill, and `$R/scripts/fix-sweep.py` resolves in non-Claude bundles **only if**
`"fix-sweep.py"` is added to `RUNTIME_HELPERS` (`01-architecture-layout.md` §5.1). That edit
is a hard prerequisite for these blocks — without it, both invocations fail on every
non-Claude adapter.

## 9. Out of Bounds

Named explicitly so an implementer does not "helpfully" extend the change:

| Not touched | Why |
|---|---|
| `## Step 6: Re-verify Gate` | C-1 / R-06 — a re-verify is never a fresh sweep; the corrected-claim sweep has already closed out in Step 4 |
| `references/stage-exit-protocol.md` | C-1. Its "`skills/forge-fix/SKILL.md` Step 6" citation must stay valid, which no-renumbering guarantees |
| Step 7's outcome table, `--outcome` values, flag surface | C-6 (§6) — existing rows only, `Pass no other flags` still holds |
| The Step 7 stage-exit fenced invocation | Unchanged; the pass still closes exactly once |
| `skills/forge-verify/references/findings-template.md` | Read-only parse contract (`00-core-definitions.md` §7.1). The sweep record extends `## Fix Progress`, a forge-fix-owned section the template does not define |
| Step headings and their numbers | No renumbering (§1.1) |
| `forge.config.json`, pipeline-state schema | C-6 — no config key, no schema change |

## 10. Dependencies

Implement in this order:

1. **`00-core-definitions.md`** — the sweep-record grammar (§7.2), the disposition vocabulary
   and outcome mapping (§8), the payload shapes and exit-code convention (§6). This document
   cites those contracts; it does not redefine them.
2. **`02-fix-sweep-script.md`** → `scripts/fix-sweep.py` **must exist and be executable
   before this edit lands**. The prose invokes `plan-coverage` and `sweep` by path; shipping
   the skill prose ahead of the script yields a fix pass that fails at Step 2 on every run.
3. **`01-architecture-layout.md` §5.1** — `"fix-sweep.py"` in `build-adapters.py`'s
   `RUNTIME_HELPERS`, plus the `adapters/**` regeneration, so `$R/scripts/fix-sweep.py`
   resolves outside Claude bundles (§8).

Siblings this document does **not** depend on: `04-verification-checks.md` (the four new
CHECKs are an independent workstream — `01-architecture-layout.md` §3) and
`05-testing-strategy.md` (which consumes this document's exact strings as prose guards, §11).

## 11. Verification

Prose guards `05-testing-strategy.md` pins in `tests/test_fix_sweep.py` (pattern:
`tests/test_lifecycle_artifact_check.py`), asserted against
`skills/forge-fix/SKILL.md`:

- [ ] **Sweep invocation present** — the body contains `scripts/fix-sweep.py` with `sweep`
      and `--json`, inside a `bash` fence.
- [ ] **Plan-coverage invocation present** — the body contains `plan-coverage` invoked as
      `$R/scripts/fix-sweep.py`.
- [ ] **NOT-RUN wording present** — the body contains the literal
      `- Sweep: NOT RUN — no git delta ({reason})` (REQ-SWEEP-07). Match the em dash and the
      `{reason}` placeholder exactly; this string is the whole guarantee that a skip is
      visible.
- [ ] **Disposition vocabulary present** — the body contains all three tokens `FIXED`,
      `JUSTIFIED:`, `FALSE-POSITIVE:` (REQ-SWEEP-04).
- [ ] **Enumerated staging prose present** — the body contains `git add <path>` and forbids
      the bulk forms (contains both `git add -A` and `git add .` in a prohibitive clause)
      (REQ-SWEEP-05).
- [ ] **No `--exclude` in skill prose** — the body contains no `--exclude` and no
      `--min-chars` (they stay operator escape hatches, §4.1).

Structural and budget checks:

- [ ] **No renumbering** — the body still contains headings `## Step 1:` … `## Step 7:` with
      their existing titles, and `## Step 6: Re-verify Gate` is byte-identical to its
      pre-change content (C-1).
- [ ] **`references/stage-exit-protocol.md` is unmodified**, and its
      "`skills/forge-fix/SKILL.md` Step 6" citation still resolves to the Re-verify Gate.
- [ ] **No new outcome values** — the Step 7 table's `--outcome` column still holds exactly
      `no-findings`, `decisions`, `failed`, `applied`, `reverified`, `reverify-findings`,
      `deferred` (C-6).
- [ ] **Body ≤ 300 lines / ≤ 5000 words** — `python3 scripts/check-spec-purity.py` passes;
      expected ≈167 lines (§7).
- [ ] **Prelude identity + presence** — both new `bash` fences carry the byte-identical
      canonical prelude at the **left margin** (rules 5 and 6 of `check-spec-purity.py`).
- [ ] **Host neutrality survives the build** — `python3 scripts/build-adapters.py` regenerates
      cleanly and `bash scripts/validate.sh` (adapter drift, step 6b) is green (C-5).

Behavioral confirmation (milestone acceptance, PRD §8 — observed, not automated):

- [ ] On a real fix pass, the sweep runs, its `- Sweep:` block appears under `## Fix Progress`
      in the findings document, and every hit carries exactly one disposition token.
- [ ] A pass run outside a git repository records the NOT-RUN notice and still closes exactly
      once through Step 7.
