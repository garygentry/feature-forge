---
title: "Stage Exit Coverage — Integration Guide"
---

# Integration Guide

How to close a skill through the Scripted Stage Exit, consume its directives correctly, and
extend coverage to a new pipeline-advancing skill without tripping the guards.

## Closing a stage through the scripted exit

Every covered skill ends with **one** stamped block — the canonical scripted stage-exit
stamp from `references/stage-exit-protocol.md`. It is stamped *verbatim* into each skill; the
only build-time slot is the per-stage argument list. A production stage:

```bash
R="$(bash -c 'for d in "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.claude/skills/feature-forge …; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-session.py" stage-exit \
  --feature "{feature}" --stage forge-2-tech \
  --specs-dir "{specsDir}" --host claude --verify-capability "{verify-capability}"
```

Then obey the DIRECTIVES the script prints, in the fixed order below, and — only when
`terminalOwnedBy` is `"self"` — print the NEXT-STEPS block verbatim as your **absolute last
output**, with nothing after the sentinel line.

> **Do not improvise a "Next steps" list.** The script already decides freshness, gate form,
> host wording, branch rejoin, and the next command from live state. A second hand-written
> block can only disagree with it — the exact routing fork this feature removed.

## Determining `--host` and `--verify-capability`

Compute the two independently; a host never implies a capability.

- **`--host`** — the active adapter surface: `claude`, `pi`, or `generic`. It selects
  command syntax (`/feature-forge:` vs `/skill:` vs host-neutral) and fresh-session wording
  (`/clear` vs `/new` vs neutral prose). The canon stamp is literally `--host claude`; the
  adapter build (`scripts/build-adapters.py`) rewrites it per target — this one token is not
  a placeholder.
- **`--verify-capability`** — `interactive` **only** when both (a) a question mechanism like
  `AskUserQuestion` is available, and (b) a clean-room `forge-verifier` subagent can be
  dispatched *right now*. Otherwise `manual`.

The trap: **(b) tests permission, not tool presence.** A session can carry a standing host
instruction against unsolicited subagent dispatch. If dispatch is barred *only unless the
user asked* and a question mechanism exists, still pass `interactive` — the `standard` gate's
own prompt supplies the missing request. Pass `manual` only when there is *no* question
mechanism *and* *no* permitted dispatch.

## Consuming directives, in order

The script has already computed every conditional, so a directive is an instruction, not a
question to re-derive. Execute them in this exact order:

1. **Surface `invalidAutoVerifyKeys` and every `warnings` entry** — before any terminal
   output. `warnings` is a list in a fixed order; print every entry, don't merge or
   summarize, and never dump the state file.
2. **`runInStageVerify: true`** → run the in-stage verify → fix → re-verify chain
   synchronously *now*, in this session (verify before the clear). This is the one directive
   that asks for an *unsolicited* dispatch, so it is exactly where a no-unsolicited-dispatch
   bar bites: when dispatch needs consent and a question mechanism exists, present the
   Standard Verify Gate's consent form first (two choices — *Verify now* / *Skip for now* —
   the second choice omitted), dispatch on the affirmative, then continue the chain. Honor
   `autoFixEligible`.
3. **`verifyGate: "standard"`** → present the Standard Verify Gate. Persist a pass, findings,
   or an explicit skip and recompute routing before printing any block.
4. **`verifyGate: "manual-print"`** → print `verifyCommand` for the user; do **not** dispatch
   inline.
5. **Print `nextSteps` byte-for-byte** — only when `terminalOwnedBy == "self"`.

## The owner token (branch skills only)

`forge-verify` and `forge-fix` are dispatched via Skill/Agent, not a CLI, so no `--owner`
flag arrives on its own — and ownership is **never** inferred from phrasing. The dispatching
caller states it with a literal token in its invocation prompt:

- **`owner: nested`** — used by in-stage auto-verify chains, the navigator catch-up, and a
  nested re-verify. The branch skill returns its structured result and prints no terminal
  block.
- **`owner: direct`** — the branch skill owns the terminal block. A user-typed
  `/feature-forge:forge-verify` carries no dispatcher, so **absent the token, treat yourself
  as `direct`.**

Pass the resolved value straight through as `--owner direct|nested`. Getting this wrong is
not cosmetic: a nested verify that self-reports `direct` emits a second sentinel *inside* an
outer stage's exit, breaking the exactly-one-terminal-block rule.

## Extending coverage to a new advancing skill

Coverage is an **explicit allow-list**, by design — a new advisory `forge-something` skill is
not silently covered, and a new advancing skill cannot land without an intentional edit. To
add one:

1. **Add its id to the `ExitStage` alias** in `scripts/forge-session.py`.
   `EXIT_STAGES`, `_BRANCH_STAGES`, and `_EXIT_PRODUCTION_STAGES` derive from it via
   `get_args` — never hand-list them, or the copies drift.
2. **Give it routing** in `stage_exit()`: if it takes a multi-way result, add its enum to
   `EXIT_OUTCOMES`; if it is a diversion, decide its served-stage handling.
3. **Add its row to `CANONICAL_EXIT_SITES`** in `tests/test_stage_exit_protocol.py`, naming
   the canon file(s) that own its terminus. This table's skill column must equal
   `EXIT_STAGES` in the same order — the guard asserts it.
4. **Stamp the canonical scripted block** into its `SKILL.md` and regenerate adapters in the
   **same commit** (`scripts/build-adapters.py`), or the drift and adapter guards fail.

## Testing and drift guards

| Guard | What it protects |
|-------|------------------|
| `tests/test_stage_exit.py` | The directive matrix: given state/config/host/outcome, `stage_exit()` returns the expected directives and one sentinel. |
| `tests/test_stage_exit_protocol.py` | Two things: the canonical stamp is present verbatim in every covered skill, and `CANONICAL_EXIT_SITES` names exactly the nine `EXIT_STAGES` in order. Removing a skill's exit or drifting the table fails loudly. |
| `tests/test_stage_constants_parity.py` | The derived constant lists match their `Literal` source domains. |
| `tests/test_json_loader_parity.py` | The duplicate-aware JSON loader mirrored into `forge-session.py` and `forge-bootstrap.py` stays identical. |
| `tests/test_state_verb_call_sites.py` | Every `state-verify` bash fence carries its `--epic` sentence within the guard's line window. |

### The compliance fixture

`eval/fixtures/compliance/verify-fix-reverify.json` drives the full branch path
(verify → fix → re-verify) and scores that **exactly one** correct terminal sentinel emerges
(REQ-EVAL-01). Each scenario declares the outcome at each step and asserts the exact
`stage-exit` invocation flags (`--stage`, `--owner`, `--outcome`, `--served-stage` /
`--verify-mode`) and the expected `primaryCommand` — including a `successful-rejoin` path and
a findings/recovery path, scored on command evidence rather than prose (REQ-EVAL-02). It is
independent of the original `forge-1-prd` compliance fixture, which measured only the already
scripted linear path (REQ-EVAL-03). Run the compliance eval via `eval/run-compliance-eval.py`.

Run the whole guard suite the same way CI does — pytest alone is insufficient:

```bash
bash scripts/validate.sh
ruff check scripts/ eval/
```

## Further Reading

- [README](./README.md) — what the feature is and the failures it fixes.
- [Architecture](./architecture.md) — the directive payload, verify-first ordering, and the scheduling boundary.
- [CLI Reference](./cli-reference.md) — every `stage-exit` flag, the per-stage matrix, and exit codes.
