# Field observations — stage-exit compliance in real runs

Real-session counterpart to `run-compliance-eval.py`'s probe 1. The probe measures fresh
4–16-turn headless sessions; this file records what happens at genuine interview length,
on the interactive gates, and on the stages the probe does not drive. See
`eval/README.md` § *What this probe cannot see* for the procedure and why it exists.

Append one row per stage exit. A `no` in any of the last four columns is the evidence the
synthetic probe cannot produce — quote the actual text when you record one.

| date · model · stage | ctx at exit | sentinel last? | after sentinel | block verbatim? | `stage-exit` run? |
|---|---|---|---|---|---|
| 2026-07-29 · opus-5 · `forge-4-backlog` | ~61k reported (see N-2) | **yes** | none | **yes** | **yes** |

## Notes

Record anything a table row cannot hold — the wording that preceded the drift, what the
model appeared to be optimizing for, whether a re-run reproduced it.

### N-1 — 2026-07-29, `forge-4-backlog`, Phase 1 context-efficiency

**First real-session observation. Clean on all four criteria.** The exit ran at the end of
a long interactive session (merge + re-measurement + a five-instance verify fan-out + a
36-finding fix pass + backlog authoring), which is far past the `warm` variant's ≈16 turns
— the condition Phase 0 §2 named as the probe's main blind spot. No summarization of the
block, no text after the sentinel, no "improvement" of the wording.

Three things this row does **not** cover, recorded so the next reader does not over-read it:

- **The `verifyGate: "standard"` directive was not presented as an `AskUserQuestion`**, by
  explicit user instruction ("create handoff doc then print prompt to execute in a clean
  session"). That is a user override, not model drift — but it means this observation
  covers the NEXT-STEPS invariant only, not the full directive contract. The interactive
  gate remains unmeasured in the field, exactly as it is in the probe. `forge-verify-backlog`
  was deliberately left absent from pipeline state rather than recorded as `skipped`, so the
  ledger still reads "never verified."
- **Trailing content pressure was present and resisted.** The same user turn asked for a
  handoff document *and* a paste-able kickoff prompt. Both were placed **before** the
  NEXT-STEPS block rather than after it, keeping the sentinel last. This is the closest a
  real session has come to the failure mode B1 was proposed to guard, and the invariant
  held — one more data point against building the `Stop` hook.
- **n=1.** One clean exit is not evidence of a rate. Phase 0's 20/20 plus this is two
  independent instruments agreeing, which is what §6.4 of the baseline asked for, but the
  case for B1 reopens only on observed `no` rows — keep appending.

### N-2 — instrument caveat: `context-usage` under-reports and mis-identifies the model

`python3 scripts/forge-session.py context-usage --json` returned
`{"tokens": 60815, "pct": 0.0608, "model": "claude-opus-4-7"}` at this exit. Two problems
for anyone using this figure as the "ctx at exit" column:

1. **The model string is wrong.** The session ran on Opus 5; the script reported
   `claude-opus-4-7`. `windowTokens` was correct only because `forge.config.json` pins
   `contextWindowTokens: 1000000` — the inference path would have been wrong too.
2. **~61k is implausibly low** for a session of this length, so the token count is
   probably measuring something narrower than the live context (likely the transcript file
   rather than the assembled window).

Treat the number as a lower bound, not a measurement. If this column is ever used to test
"does drift correlate with accumulated context", the instrument needs fixing first —
otherwise the correlation is computed against a figure that does not track the thing it
names. Worth a feature-forge issue independent of this programme.
