# Field observations — stage-exit compliance in real runs

Real-session counterpart to `run-compliance-eval.py`'s probe 1. The probe measures fresh
4–16-turn headless sessions; this file records what happens at genuine interview length,
on the interactive gates, and on the stages the probe does not drive. See
`eval/README.md` § *What this probe cannot see* for the procedure and why it exists.

Append one row per stage exit. A `no` in any of the last four columns is the evidence the
synthetic probe cannot produce — quote the actual text when you record one.

| date · model · stage | ctx at exit | sentinel last? | after sentinel | block verbatim? | `stage-exit` run? |
|---|---|---|---|---|---|
| _(no observations recorded yet)_ | | | | | |

## Notes

Record anything a table row cannot hold — the wording that preceded the drift, what the
model appeared to be optimizing for, whether a re-run reproduced it.
