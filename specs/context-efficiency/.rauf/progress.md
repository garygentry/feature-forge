# Progress — context-efficiency

## Item 001 — extract six per-mode checklists + findings-template.md

- All seven files were produced by `sed -n 'START,ENDp'` over the monolith, so the
  extracted bodies are provably byte-identical to their source spans. Every mode file
  has a **fixed 6-line header** (title, blank, one-sentence preamble carrying the
  `Execute EVERY check — do not skip.` directive verbatim, blank, the source-L5
  stack-profile blockquote verbatim, blank); `findings-template.md` has a 4-line header.
  Re-verify a span with:
  `diff <(tail -n +7 <mode>.md) <(sed -n 'S,Ep' verification-checklists.md)`
  (`tail -n +5` for findings-template.md). Useful for item 002/003 if the files are
  ever regenerated.
- CHECK-ID counting: use `sort -u`. Raw occurrence counts are higher for impl (28 vs
  23) and epic (13 vs 10) because CHECK-I21/I22 and CHECK-E06/E07 are cross-referenced
  in surrounding prose — those cross-references are part of the verbatim text.
- Creating files under a skill's own `references/` makes `adapters/` stale immediately:
  `build-adapters.py _emit_bundle` copies the whole dir into all **six** bundles
  (claude, codex, copilot, cursor, gemini, pi). Regenerating added 6×7 = 42 adapter
  files here. `build-adapters.py --check` (validate.sh step 6b) catches this; pytest
  does not.
- `.venv-adapters` already existed and was reused; `bash scripts/validate.sh` is green.

## Item 002 — switch consumers to the split checklists, delete the monolith

### R1 measured net instruction-token delta (spec 06 §7.5 row "R1", §7.2 method)

Baseline of record: `specs/context-efficiency/.reference/REMEASURE-0.13.0.md`.
Method: `wc -l` / `wc -w` over the canonical surface, prose at ~1.3 tok/word.

Targeted invocation — **a `forge-verifier` leaf subagent**. Before it loaded the whole
`references/verification-checklists.md` (477 L / 4,755 w ≈ **6,182 tok**); after R1 it
loads exactly one mode file:

| mode | after (L / w / tok) | net delta |
|---|---|---|
| prd | 31 / 286 / 372 | **−5,810** |
| tech | 35 / 308 / 400 | **−5,782** |
| specs | 64 / 662 / 861 | **−5,321** |
| backlog | 97 / 1,112 / 1,446 | **−4,736** |
| impl | 48 / 1,094 / 1,422 | **−4,760** |
| epic | 79 / 804 / 1,045 | **−5,137** |

Per-leaf band **−4.7k … −5.8k tok**, i.e. 99–109% of the re-measured −4.8k…−5.9k claim
(108–132% of the original −4.4k PRD claim). The parent orchestrator also improves: its
Step-4/Step-6 template read is now `references/findings-template.md` (157 L / 859 w ≈
1,117 tok) instead of the same 6,182-tok monolith → **−5,065 tok**.

Costs, correctly attributed: `forge-verify/SKILL.md` body 263→265 L, 2,554→2,580 w
(**+34 tok** — the six literal mode citations); `agents/forge-verifier.md` 122 L,
1,077→1,108 w (**+40 tok**). Net reduction holds on every mode.

### Learnings

- **Never write the brace-enumeration citation form.** `build-adapters.py`'s fan-out
  regex character class has no comma, so `{prd,tech,…}.md` captures one bogus token and
  resolves nothing. Step 3 names all six paths as separate literals; `{mode}.md` is the
  only brace form in canon (it matches, since the class holds `{`/`}`/`/`).
- The repo's interactive `rm` alias silently no-ops in a non-tty tool call — the file
  survived and only `ls` revealed it. Use `command rm -f` for canon deletions.
- Two of the three repointed tests sliced a mode section using the *next mode's* `##`
  heading as terminator. Those headings now live in sibling files; a `str.split()` on a
  missing terminator returns the whole remainder, so the tests would have stayed green
  while asserting over a wider slice. Both now slice to EOF explicitly.
- `references/vendor-construct-inventory.md` (the REQ-VND-03 audit artifact) names each
  file holding a `${CLAUDE_PLUGIN_ROOT}` occurrence — the epic bash recipe's prelude moved
  with the split, so that row was repointed to `verification-checklists/epic.md`. No test
  pins it; it goes stale silently. Worth re-grepping on any future reference-file move.

## Item 003 — `tests/_forge_paths.py` + the R1 checklist-split drift guard

### Mutation-test evidence (AC 2 / AC 3)

Recorded here as well as in the commit message, since a transient experiment leaves no
trace. Each mutation was applied to canon, the guard run, then the file restored and
confirmed byte-identical with `git diff --stat` (empty).

1. **Deleted the `CHECK-S38` line from `verification-checklists/specs.md`** → 3 failures:
   - `test_mode_checklist_is_complete_and_contiguous[specs]`:
     `AssertionError: specs.md: expected 38 contiguous CHECK-S IDs, found 37`
   - `test_split_preserves_the_full_check_inventory`:
     `AssertionError: split inventory drifted from 130 unique CHECK-IDs: {'prd': 15, 'tech': 17, 'specs': 37, 'backlog': 27, 'impl': 23, 'epic': 10}`
   - `test_skill_expected_count_table_matches_the_files`:
     `AssertionError: SKILL expected-count table says specs: 38 checks, but specs.md holds 37`
   The third failing *for free* is the point of reading the table against the counted
   values: a deletion is caught by the file guard **and** by the table guard.
2. **`forge-verify/SKILL.md` table drift, `backlog: 27 checks` → `26`** →
   `AssertionError: SKILL expected-count table says backlog: 26 checks, but backlog.md holds 27`
3. **Table re-hedged, `impl: 23 checks` → `impl: ~23 checks`** →
   `AssertionError: SKILL expected-count table still hedges impl with '~' — the split made the totals exact`
   (item 002 dropped the `~`; the regex captures an optional `~` so the hedge is caught
   rather than silently matching the digits.)

A renumber-in-place (`CHECK-S38` → `CHECK-S99`) also goes red, on the contiguity list
comparison rather than the length one.

### Learnings

- **Contiguity alone is not a removal guard.** Deleting the *highest* ID (S38) leaves
  `01..37` perfectly contiguous. The guard needs a frozen expected count too — so
  `EXPECTED` holds one hardcoded count per mode (the REQ-R1-05 inventory) and the SKILL
  table is compared against counts *read back out of the files*. That is the "no number
  hardcoded in two places" split: one frozen inventory, one derived comparison.
- `_ids()` unique-s deliberately. Raw `CHECK-I` occurrences in `impl.md` are 28 (not 23)
  and `CHECK-E` in `epic.md` are 13 (not 10) because I21/I22 and E06/E07 are
  cross-referenced in surrounding prose — those cross-references are part of the verbatim
  moved text, so `sort -u` / `set()` is mandatory, not a convenience.
- `tests/` has no `__init__.py`, so pytest's default `prepend` import mode puts `tests/`
  on `sys.path` and a bare `from _forge_paths import …` resolves. The leading underscore
  also keeps the module out of collection. Items 004/005/007–010/014–016 can import it
  the same way.
- `tests/` is **not** in `validate.sh`'s `RUFF_TARGETS` (`scripts/ eval/` only), so ruff
  does not lint the guards. Keep them tidy by hand.
- Restoring a mutated canon file: `command cp -f` (the repo's interactive `cp`/`rm`
  aliases no-op in a non-tty tool call — same gotcha item 002 hit with `rm`).

## Item 004 — gate the navigator's `process-overview.md` read (R3)

### R3 measured net instruction-token delta (spec 06 §7.5 row "R3", §7.2 method)

Baseline of record: `specs/context-efficiency/.reference/REMEASURE-0.13.0.md` (§R3 row:
`−1.72k` re-measured, 101% of the `−1.7k` PRD claim).
Method: `wc -l` / `wc -w` over the canonical surface, prose at ~1.3 tok/word.

Targeted invocation — **a routine navigator status/dashboard render**. It no longer
loads `references/process-overview.md` (143 L / 1,326 w ≈ **1,724 tok**, unchanged
file). Cost: the navigator body grew 3,936 → 3,967 w (227 L, unchanged) for the gating
clause — **+40 tok**, paid on *every* invocation.

**Net on the targeted invocation: −1,684 tok** (98% of the −1.72k baseline claim).
On an architecture/"how does forge work" question the file still loads, so that path is
**+40 tok** — the correct attribution: R3 trades a small always-paid cost for removing a
large cost from the overwhelmingly common path.

### Learnings

- The gating clause was placed at the **top of `### 2. Determine Context`**, not left in
  `### 1. Read Configuration`. §1 is unconditional setup — any read instruction there is
  paid by every invocation regardless of how it is worded, so re-wording *in place* would
  have satisfied a naive grep while changing nothing. The gate has to live where the
  navigator classifies the request.
- The guard asserts **sentence-scoped**, not window-scoped. Spec 06 §3.3's sketch used a
  400-char window before the citation, which passes if an *unrelated* conditional happens
  to sit in the preceding paragraph — and §2's neighbourhood is full of `**If a feature
  name is provided**` branches, so that heuristic was live-fire false-positive-prone here.
  `_citing_sentences()` splits on `". "` and requires the gating cue **and** the
  architecture-topic cue inside the same sentence as the citation.
- Presence and conditionality are **two independent guards**, deliberately. A citation
  reintroduced as a bare imperative keeps the fan-out guard green while restoring the
  unconditional load; a moved read-site with the literal path dropped keeps the
  conditionality guard green while silently unshipping the file from the non-Claude
  adapter bundles. Neither alone is coverage.
- Mutation-tested by reverting the clause to the verbatim pre-R3 line
  `For pipeline architecture details, read \`references/process-overview.md\`.` → 2 of 4
  tests red (`test_the_unconditional_setup_read_is_gone`,
  `test_every_citation_sits_inside_a_how_it_works_conditional`), restored with
  `command cp -f`.
- Editing one skill body restages **6** adapter files (one per target) — the navigator
  body is copied into every bundle. `process-overview.md` itself is a *shared* reference,
  fanned out by citation: it still resolves 3× per target after the move, confirming the
  literal-citation requirement did its job.
