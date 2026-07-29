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
