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
