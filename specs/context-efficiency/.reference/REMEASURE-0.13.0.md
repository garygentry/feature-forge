# Baseline Re-measurement @ v0.13.0

> Taken 2026-07-28 against `forge/context-efficiency` after merging `main` @ `e96b754`
> (plugin v0.13.0 / installer 0.3.0). Satisfies the re-measurement rule pinned in
> `AUDIT.md` and PRD REQ-PERF-01 / REQ-OBS-01 / OQ-3. Supersedes `LOAD-MAP.md`'s
> figures as the baseline of record for SC-1.
>
> **Method, identical to LOAD-MAP so the comparison is apples-to-apples:** `wc -l` /
> `wc -w`, prose estimated at ~1.3 tokens/word. A `chars ÷ 4` estimate is shown as a
> cross-check where it diverges (JSON tokenizes denser than prose; where the two
> disagree, the 1.3 tok/word figure is the one compared against the claim, because
> that is how the claim was computed).

## Headline: the canonical surface did not move

The branch was 4 commits behind `main` and predated 0.13.0; it has been merged so the
measurement is genuinely at 0.13.0. Across the entire runtime-loaded canon —
`skills/`, `references/`, `agents/` — the diff from the audit base (`b9f0871`) to
0.13.0 is:

```
references/forge-config-schema.json | 4 ++--
1 file changed, 2 insertions(+), 2 deletions(-)
```

...a rauf pin version string (`0.12.0` → `0.13.0`) inside a `default` and a
`description`. No line-count or word-count change. **Every LOAD-MAP figure reproduces
byte-for-byte.** The Pi adapter work landed in `adapter-src/`, `adapters/pi/`,
`scripts/build-adapters.py`, `scripts/forge-root.sh`, `scripts/validate.sh` and test
fixtures — build and host-porting machinery, none of it loaded into a Claude stage
session.

This makes the re-measurement a *confirmation* rather than an independent second
number. That is a weaker result than a genuinely fresh measurement would be, and it
should be read as such: it establishes that the audit's arithmetic has not decayed, not
that it has been independently reproduced by a different method.

## Per-recommendation verdict against the <50% rule

| R | Target | Claim (LOAD-MAP) | Re-measured @0.13.0 | % of claim | Verdict |
|---|---|---|---|---|---|
| **R1** | `verification-checklists.md` split, per verifier instance | −4.4k | **−4.8k to −5.9k** | 109–134% | **SHIP** |
| **R3** | navigator `process-overview.md` conditional | −1.7k | **−1.72k** | 101% | **SHIP** |
| **R4** | per-stage `pipeline-state-schema.json` read | −1.5k | **−1.49k** (char/4: −2.75k) | 100% | **SHIP** (see §Frequency) |
| **R5** | `forge-config-schema.json` → `effective-config` | −2.7k | **−2.69k** (char/4: −4.40k) | 100% | **SHIP** |
| **R6** | `runner-contract.md` always/conditional split | −1.1k | **−1.19k** | 108% | **SHIP** |

**No recommendation lands below ~50% of its claim. The pinned stop-rule does not fire
for any of R1, R3, R4, R5, R6.** Proceed to backlog authoring for all five.

(R2 is dropped — PRD §3.2. R7 is out of scope — PRD §6.)

### Supporting measurements

**R1 — `skills/forge-verify/references/verification-checklists.md`, 477 L / 4,755 w
(6,182 tok).** Section spans are unchanged from LOAD-MAP:

| Mode | Lines | Words | Tokens | Saved if split | % of 4.4k claim |
|---|---|---|---|---|---|
| prd | 7–31 (25) | 224 | 291 | −5,890 | 134% |
| tech | 32–60 (29) | 246 | 320 | −5,862 | 133% |
| specs | 61–118 (58) | 600 | 780 | −5,402 | 123% |
| backlog | 119–209 (91) | 1,050 | 1,365 | **−4,817** | **109%** |
| impl | 210–251 (42) | 1,032 | 1,342 | −4,840 | 110% |
| epic | 252–324 (73) | 742 | 965 | −5,217 | 119% |

Worst case (backlog mode, the largest) still clears the claim. Orchestrator-facing
material — Findings Document Template, Example Findings, Epic Mode State Write Detail,
L325–478 = 153 L / 811 w — is a further ~1.05k tok that REQ-R1-02 removes from every
subagent context. CHECK-ID counts to preserve exactly across the split (REQ-R1-05):

```
CHECK-P 15 · CHECK-T 17 · CHECK-S 38 · CHECK-B 27 · CHECK-I 23 · CHECK-E 10
```

**R6 — `skills/forge-5-loop/references/runner-contract.md`, 341 L / 2,864 w.** Spans
unchanged. The conditional slice is `## Agent selection` (L23–111, 89 L / 806 w) plus
`## Optional flags catalog` (L153–168, 16 L / 107 w) = 105 L / 913 w ≈ **1,187 tok**.
The remaining six sections are needed on every run (REQ-R6-01).

**R3 — `references/process-overview.md`, 143 L / 1,326 w ≈ 1,724 tok.** The
unconditional citation is a single line, `skills/forge/SKILL.md:18` — "For pipeline
architecture details, read `references/process-overview.md`." `forge-guide` cites it
three more times, all already conditional and out of R3's scope.

**R4 — `references/pipeline-state-schema.json`, 191 L / 1,149 w / 10,984 chars.** Cited
by 8 skill bodies (9 citations: forge-1-prd ×2, forge-2-tech ×2, and one each in
forge-0-epic, forge-3-specs, forge-4-backlog, forge-6-docs, forge-verify, forge), plus
`shared-conventions.md`, `stage-exit-protocol.md`, and `forge-0-epic/references/edit-mode.md`.

**R5 — `references/forge-config-schema.json`, 236 L / 2,068 w / 17,600 chars.** Cited by
`forge-4-backlog` (runner `bin` / `validateCommand` / `versionCommand` /
`minRunnerVersion` / `installHint`), `forge-5-loop` (loopRunner defaults), and
`forge-guide` ×2.

## Read-frequency evidence (REQ-OBS-02 / OQ-1) — thin, but it points one way

Source: the `consumption-data-refresh` dogfood transcripts, 188 sessions. This is the
honest instrument — the `feature-forge` project dir cannot be used, because this repo is
the plugin's own source and a path *mention* there is development, not a runtime read.

| Reference | `Read` tool calls |
|---|---|
| `shared-conventions.md` (unconditional "read before proceeding") | **12** |
| `.pipeline-state.json` (the artifact itself) | 103 |
| `runner-contract.md` | 2 |
| **`pipeline-state-schema.json`** | **2** |
| **`forge-config-schema.json`** | **1** |
| `process-overview.md` | 0 |
| `verification-checklists.md` | 0 |

**Read this carefully — two limits bound what it can support.**

1. **Subagent tool calls are not captured.** Zero files in either project dir contain
   `"isSidechain":true` entries. Verifier, researcher, and spec-writer reads are
   invisible to this instrument, which is why `verification-checklists.md` shows 0. R1's
   savings therefore remain a *static* projection — the transcripts can neither confirm
   nor refute its read frequency, and the 0 must not be read as "nobody loads it."
2. **The denominator is small.** Only 4 `stage-exit` invocations across the corpus. This
   is a directional signal, not a rate.

With those caveats, the signal is consistent and worth recording: the file with an
unconditional read instruction was opened **12×**, while the two schemas cited as "write
state conforming to …" were opened **2×** and **1×** — against 103 reads of the state
artifact itself. **The per-stage schema read is not, in practice, per-stage.**

**Consequence, exactly as PRD REQ-OBS-02 anticipated:** R4's and R5's *realized* token
savings are meaningfully below their static projections, because the read they eliminate
often was not happening. This changes the *reported savings*, not whether they ship —
REQ-R4-02 and REQ-R5-02 justify the extraction on drift-removal and deterministic default
resolution, which hold at any read frequency. **Backlog authors: do not write an
acceptance criterion asserting a ~1.5k or ~2.7k measured per-stage saving for R4/R5.**
Scale the claim, or state the benefit as drift-removal and let SC-1's "measured net
reduction, correctly attributed" be satisfied by the static file-load delta on the
invocations where the read does occur.

## Line-cap headroom — the binding constraint on R4 and R6

`check-spec-purity.py` caps skill bodies at 300 lines (`MAX_BODY_LINES`, hard fail,
CI-only — pytest does not run it). Measured body lines at 0.13.0:

| Skill | Body lines | Headroom |
|---|---|---|
| **forge-5-loop** | **298** | **2** |
| **forge-0-epic** | **292** | **8** |
| forge-verify | 257 | 43 |
| forge-bootstrap | 234 | 66 |
| forge (navigator) | 227 | 73 |
| forge-2-tech | 209 | 91 |
| forge-6-docs | 186 | 114 |
| forge-guide | 176 | 124 |
| forge-3-specs | 162 | 138 |
| forge-4-backlog | 159 | 141 |
| forge-1-prd | 148 | 152 |
| forge-fix | 82 | 218 |
| forge-init | 56 | 244 |

Two of these bind Phase 1 work:

- **`forge-5-loop` has 2 lines of headroom, not the "at the cap" the specs assume.**
  R6 must be strictly line-neutral in the body (REQ-R6-03), and R4's state-write
  citation swap in this skill must not add a line either. Two changes each "just adding
  a line" is a CI failure.
- **`forge-0-epic` has 8 lines of headroom, not 12.** Dropping R2 removed the slack R4
  was expected to inherit here. R4 must be strictly in-place in this body.

## Non-regression baselines (REQ-PERF-02)

Frozen here so the "must not increase the always-loaded surface" guard is a green/red
assertion rather than a review judgment:

- **13 skill frontmatter descriptions: 4,688 chars total ≈ 1.17k tok.** Per skill:
  forge-guide 528 · forge-0-epic 485 · forge-bootstrap 407 · forge-5-loop 392 ·
  forge-4-backlog 378 · forge-3-specs 357 · forge 349 · forge-2-tech 318 ·
  forge-1-prd 317 · forge-6-docs 304 · forge-verify 297 · forge-init 287 · forge-fix 269.
- **`SessionStart` hook common-path output: empty, exit 0.** `scripts/session-check.sh`
  produces no output when `forge.config.json` exists.

## Gate state at the time of measurement

`python3 -m pytest tests` → 462 passed, 2 skipped · `ruff check scripts/ eval/` → clean ·
`python3 scripts/check-spec-purity.py` → PASS, 0 violations.

(462, not the 497 quoted in the Phase 0 handoff: the 35 `tests/test_compliance_eval.py`
cases live on `test/claude-5-compliance-eval` and are not on this branch.)
