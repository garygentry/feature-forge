---
title: "Context Efficiency · Integration Guide"
---

# Integration Guide — Working With the Optimized Surfaces

Practical guidance for anyone editing the pipeline after this refactor: how to write a skill
step that calls a state verb, how to keep a new reference file from silently unshipping, and
which drift guard to extend when you change a split surface.

## Calling a State Verb From a Skill Step

Every state-write step follows the same shape. Resolve the plugin root, then call the verb.

```bash
R="$(bash -c 'for d in "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-session.py" state-enter \
  --feature "{feature}" --stage "{stage}" --specs-dir "{specsDir}"
```

Four rules govern every such call site.

**1. The prelude goes inside the fence.** Shell state does not persist between tool calls,
so `$R` set in one fence is gone by the next. Every fence that expands `$R` must bind it
in-fence — this is enforced by `check-spec-purity.py` Rule 6, which fails any shell fence
using `$R` without an in-fence `R=`, and Rule 5, which requires each prelude occurrence to
be byte-identical to canon. Do not "save lines" by pointing at a prelude in another fence.

**2. Epic members must pass `--epic`.** Append `--epic "{epic}"` to *every* `state-*` call
when the feature resolves as a nested epic member. Without it the verb refuses an ambiguous
name (exit 2) rather than guessing — which is the desired failure, but it means a call site
that forgets the flag is broken for every epic member. `tests/test_state_verb_call_sites.py`
asserts the mandate appears near each call site in canon.

**3. Exit 2 is a hard stop.** On exit 2, surface the plain `Error: …` stderr line verbatim,
do **not** proceed to the next step of the surrounding protocol, and do **not** hand-author
the JSON as a workaround. Nothing was written, and the stage is still resumable because the
entry stamp is already on disk — fix the cause and re-run the verb.

**4. One verb, one mutation.** If a step needs two changes (a completion *and* a note),
that is two calls. Do not reach for a generic patch; there isn't one, deliberately.

### Conditional calls in a shared fence

When a step bundles an unconditional verb with a conditional one, mark the condition
**inside** the fence as a comment, not only in the surrounding prose — prose above a fence
does not reliably gate a call the model is about to execute:

```bash
python3 "$R/scripts/forge-session.py" state-complete \
  --feature "{feature}" --stage "{stage}" --version {n} --artifact "<file>" --specs-dir "{specsDir}"
# ONLY run the next call if the user volunteered a note — otherwise stop here.
python3 "$R/scripts/forge-session.py" state-note \
  --feature "{feature}" --note "<text>" --specs-dir "{specsDir}"
```

## Pairing With the Two-Commit Git Protocol

The stage's `commitHash` cannot be known until *after* the commit that contains the state
file, and amending is forbidden (a hash captured before an amend points at an orphaned
commit). So a stage exit is always two commits, and `state-complete` is called twice:

```bash
# Commit 1 — artifacts + state. commitHash is set to null.
python3 "$R/scripts/forge-session.py" state-complete \
  --feature "{feature}" --stage "{stage}" --version {n} \
  --based-on "forge-1-prd=2" --artifact "<file>" --specs-dir "{specsDir}"
git add {specsDir}/{feature}/ && git commit -m "{commitPrefix}({feature}): <action>"

# Commit 2 — record the artifact commit's hash. Touches nothing else.
python3 "$R/scripts/forge-session.py" state-complete \
  --feature "{feature}" --stage "{stage}" --version {n} \
  --commit-hash "$(git rev-parse HEAD)" --specs-dir "{specsDir}"
git add {specsDir}/{feature}/.pipeline-state.json
git commit -m "{commitPrefix}({feature}): record stage commit hash"
```

Two recovery branches use the same verb:

- **Commit 1 failed** (a pre-commit hook, a conflict) — do not record a completion. Call
  `state-complete … --version {n} --resumable`, which records only
  `status: "in-progress"`. `--version` is still required by the parser even though this
  branch does not write it; omitting it makes the recovery command exit 2 every time.
- **Nothing to commit** (all artifacts were already committed) — mark the stage complete
  but pass `--preserve-commit-hash` so the existing hash is left alone instead of being
  reset to `null`. There is no new artifact commit to record, so skip commit 2.

Never use `git add -A`, `--amend`, `--no-verify`, or `--force`.

## Consuming `effective-config`

If a step needs a `loopRunner` field, ask the script — do not read
`references/forge-config-schema.json` for the defaults, and do not merge them by hand:

```bash
python3 "$R/scripts/forge-session.py" effective-config --config ./forge.config.json --json
```

Every field comes back resolved. Command templates keep their `{bin}` / `{backlogDir}` /
`{iterations}` placeholders — substitution is the caller's job. A missing or corrupt
`forge.config.json` yields pure defaults at exit 0, so there is no "is the config there?"
branch to write. Only an unreadable schema exits 2, and at that point the stage should fall
back to its existing behavior rather than improvising defaults.

Adding a new `loopRunner` field is a one-line schema change: give it a `default` in
`references/forge-config-schema.json` and `effective-config` picks it up automatically.
Nothing is hardcoded on the Python side.

## Verify Modes and the Checklist Split

The verify checklists are one file per mode. Two rules keep the split honest.

**A verifier leaf reads exactly one mode file.** The dispatch prompt names the mode, and the
leaf reads `references/verification-checklists/{mode}.md` — nothing else. Never hand a leaf
`findings-template.md`; that material is the orchestrator's, and the whole point of the
split is that a verifier context cannot see instructions addressed to the role that
dispatched it.

**Adding or removing a check means touching two places.** The check goes in its mode file,
*and* the expected-count table in the `forge-verify` body has to move with it.
`tests/test_verification_checklists_split.py` fails if they disagree, if a CHECK-ID leaks
across modes, or if an orchestrator section appears in a mode file.

## The Loop's Capability Gate

`skills/forge-5-loop/references/agent-selection.md` may only be cited from **inside** the
capability gate in the `forge-5-loop` body — the block that applies when the effective
`loopRunner.agentArgument` is present and non-empty. A citation above the gate would open
the file on every launch and erase the split's reason for existing;
`tests/test_runner_contract_split.py` fails on exactly that.

Two constraints when editing that body:

- **It is at 298/300 lines and ~4,560/5,000 words.** `check-spec-purity.py` Rule 4 hard-fails
  on either limit, and CI reaches it before pytest does. Any edit has to be
  line- *and* word-neutral, or buy headroom first by relocating a paragraph into
  `runner-contract.md` and leaving a one-line pointer.
- **Never push runner-contract text back into the body.** The reference file exists so the
  body stays under the cap.

## Keeping a New Reference File Discoverable

`scripts/build-adapters.py` fans shared reference files out to the non-Claude adapters **by
citation**: it scans skill bodies for literal `references/…md` paths. A file nothing cites
is a file that silently stops shipping — and the forward "does this path exist?" check stays
perfectly green while it happens.

So, when you add or move a reference file:

1. **Cite it by literal path from at least one skill body.** Not from an agent file, and not
   only from another reference file.
2. **Prefer host-neutral wording.** Since #167 the build host-term-translates reference
   markdown for non-Claude bundles (Claude tool names, `/clear`, the stage-command
   prefix), so a Claude-only term no longer ships verbatim to five other hosts — but the
   translation is a fixed table, not a rewriter: phrasing it neutrally in the first place
   still degrades best, and prose that *mentions* a host term (rather than uses it) can
   garble under substitution. `tests/test_adapter_host_neutrality.py` scans the emitted
   references and fails on leaked tokens.
3. **Regenerate the adapters in the same commit:** `python3 scripts/build-adapters.py`.
   Adapter freshness is a hard gate — `scripts/validate.sh` runs a regen-and-diff check, so
   a canon edit without a regeneration fails CI.
4. **If it is a `skills/<skill>/references/` own-ref**, it is copied verbatim rather than
   fanned out — but cite it anyway, so the discovery path does not depend on which mechanism
   carries it.

`tests/test_reference_citations.py` guards both directions: every citation names a real
file, and every file this feature created or moved is still cited.

## Which Guard To Extend

| If you change… | Extend / expect a failure in |
|---|---|
| A verify check or a mode's total | `tests/test_verification_checklists_split.py` |
| The navigator's `process-overview.md` read | `tests/test_process_overview_read.py` |
| A `loopRunner` default or `effective-config`'s contract | `tests/test_effective_config.py`, `tests/test_config_defaults_parity.py` |
| A state verb's arguments or write behavior | `tests/test_state_verbs.py` |
| The state schema, or what a verb emits | `tests/test_state_schema_conformance.py` |
| A `state-*` call site in canon | `tests/test_state_verb_call_sites.py` |
| Stage order or the verify-status vocabulary | `tests/test_stage_constants_parity.py` |
| A runner-contract section, or the loop body's size | `tests/test_runner_contract_split.py` |
| Any reference-file citation | `tests/test_reference_citations.py` |
| Frontmatter descriptions or the session hook | `tests/test_always_loaded_surface.py` |

All are stdlib-only pytest and assert against the canonical `skills/` surfaces, never
generated `adapters/` output. None may be skipped or marked xfail.

## Local Gates Before Pushing

Three gates, of which only the first is what most people run:

```bash
bash scripts/validate.sh        # structure + purity + adapter regen-diff + traceability + installer
ruff check scripts/ eval/       # CI-only otherwise — nothing local surfaces it
python3 -m pytest tests         # the drift guards
```

Two traps worth knowing: `ruff` and `check-spec-purity.py`'s body-size caps are **CI gates
that local pytest does not surface**, and the CI environment has **no `jsonschema`** — any
new validation code must be stdlib-only.

## Adding a Sixth Optimization

If you are continuing this line of work, the pattern that held up across five units:

1. **Name the targeted invocation** before touching anything. "Saves tokens" is not a claim;
   "saves N tokens on a gate-off loop launch" is.
2. **Re-measure the baseline** at implementation time rather than trusting an audit
   snapshot — line/word counts over the canonical surface drift with every release.
3. **Count the cost.** A gating clause is always-paid. Subtract it, and report the path
   where the unit is net-negative as well as the one where it wins.
4. **Check whether the gate is actually off by default.** R6's saving evaporated on a
   default config because the gate condition is satisfied by a schema default. Verify the
   default posture, not just the mechanism.
5. **Ship the drift guard in the same change.** A split without a guard is two files free to
   disagree.
6. **Keep it independently revertible**, and keep the interactive protocol byte-identical.
   If a sentence has to change wording to move, flag it in review rather than adapting it
   silently.
