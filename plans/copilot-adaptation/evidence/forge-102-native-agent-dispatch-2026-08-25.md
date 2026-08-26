# FORGE-102 Native Agent Dispatch Evidence — 2026-08-25

Status: Local implementation/runtime proof complete; FORGE-102 remains ACTIVE until the implementation milestone is authorized, committed, and pushed.

## Attribution and environment

- Repository: feature-forge, base commit `5494ad7` on `docs/copilot-g2-contract`.
- Implementation diff identity before this evidence/plan update: SHA-256 `969e6d8dd2983f2f7dfa05ee345da23cefef176c54e0be9ffd2b17fc9f5ecac5` from the bounded product/test/generated diff.
- OS: Linux `5.15.0-185-generic`, x86_64, native (not WSL).
- GitHub Copilot CLI: 1.0.80.
- Probe time: `2026-08-25T23:21:53-04:00` through `2026-08-25T23:22:33-04:00`.
- Model selected by Copilot: `claude-fable-5`; no model was pinned by the generated agents.
- Secrets excluded: no token, credential, account identifier, raw environment, user configuration, unrelated prompt/session content, or opaque model reasoning is retained here.

## Implemented dependency and memory contract

Copilot's custom-agent schema has no declarative agent-to-skill dependency field. The generator now resolves the canonical `forge-verifier` declaration `skills: [forge-verify]` through deterministic composition:

1. `_COPILOT_REQUIRED_AGENT_SKILLS` maps `forge-verifier` to `forge-verify`.
2. Generation fails if the canonical declaration changes or the named skill is absent.
3. The generated verifier carries dual-source provenance and embeds the complete host-translated canonical skill body under `## Required canonical skill contract: forge-verify`.
4. The `skills` field is mapped rather than drop-recorded for this agent.
5. Copilot-specific text states that persistent `MEMORY.md` behavior is not guaranteed and forbids relying on or updating it. Claude and Pi retain their supported canonical memory behavior.

Generated hashes used by the probe:

- `adapters/copilot/agents/forge-verifier.agent.md`: `9da4688b27ed2e43b4c5c760fd42ff304c35df94bf7cb2efc7564921eceb16ec`
- `skills/forge-verify/SKILL.md`: `89c4359e4e2b1393c3ea64b191d32ede426ea1a617743c4e9bbd2d307aa773a1`

Focused deterministic checks before the probe:

```bash
.venv-adapters/bin/python3 -m pytest -q tests/test_build_adapters.py \
  -k 'copilot or drop_with_record or claude_retains_subagent_keys'
# 26 passed, 95 deselected

.venv-adapters/bin/python3 -m pytest -q tests/test_adapter_host_neutrality.py
# 467 passed

python3 scripts/build-adapters.py --check
git diff --check
# both exit 0
```

The new generator tests include a positive composed-skill fixture, an absent-skill fail-loud fixture, committed-output assertions, and negative persistent-memory-promise guards.

## Exact runtime probe

The probe used `--plugin-dir` against the regenerated dirty-tree bundle. This CLI path is sufficient for custom-agent loading (the known 1.0.78/1.0.80 limitation concerns plugin skill discovery, not agents), and avoids mutating the installed plugin/marketplace registry.

Disposable fixture:

```text
/tmp/feature-forge-forge102-probe/
  researcher.txt             = FORGE102_RESEARCHER_ORIGINAL
  verifier.txt               = FORGE102_VERIFIER_ORIGINAL
  03-runtime-boundary.md     = FORGE102_WRITER_ORIGINAL
```

Exact command shape:

```bash
copilot -C /tmp/feature-forge-forge102-probe \
  --plugin-dir /home/gary/workspace/feature-forge/adapters/copilot \
  --disable-builtin-mcps --no-remote --no-auto-update --no-custom-instructions \
  --allow-all-tools --output-format json --stream off \
  -p '<sanitized prompt below>'
```

Sanitized prompt (the executed prompt contained only these fixture paths/markers):

```text
Use the task/subagent tool to dispatch exactly these three installed custom agents by exact name, concurrently if the tool supports parallel calls. Do not read, edit, or execute against the fixture from the parent; all fixture work must occur inside the named children.

1. feature-forge:forge-researcher: read researcher.txt, then attempt to replace it with FORGE102_RESEARCHER_BAD; report the observed value and whether edit was denied.
2. feature-forge:forge-spec-writer: the exact assigned single spec filename is 03-runtime-boundary.md; replace it with exactly FORGE102_WRITER_EDITED.
3. feature-forge:forge-verifier: report dependency OK only if the generated instructions include the required canonical forge-verify contract and CHECK-I21/I22; then attempt to replace verifier.txt with FORGE102_VERIFIER_BAD and report whether edit was denied.

Wait for all children, then return their three result lines only.
```

Expected:

- one parent turn issues three parallel `task` calls using the exact namespaced agent names;
- three `subagent.started` and three matching `subagent.completed` events occur;
- researcher and verifier have no edit capability and leave their files unchanged;
- writer emits an edit tool event and changes only its assigned file;
- verifier recognizes a marker present only in the composed `forge-verify` contract;
- inherited model behavior remains in effect.

Actual:

- The first parent tool-request batch contained exactly three background `task` calls.
- Started names, in order:
  - `feature-forge:forge-researcher`
  - `feature-forge:forge-spec-writer`
  - `feature-forge:forge-verifier`
- All three emitted matching `subagent.completed` events.
- Child tool summary: researcher `view` x1; writer `view` x2 plus `edit` x1; verifier no tool call was needed to identify its embedded contract and correctly reported no edit capability.
- Final parent response:

```text
RESEARCHER:FORGE102_RESEARCHER_ORIGINAL:EDIT_DENIED
WRITER:EDITED
VERIFIER:DEPENDENCY_OK:EDIT_DENIED
```

- Final bytes:

```text
researcher.txt=FORGE102_RESEARCHER_ORIGINAL
03-runtime-boundary.md=FORGE102_WRITER_EDITED
verifier.txt=FORGE102_VERIFIER_ORIGINAL
```

This is behavioral evidence for exact-name parallel dispatch, dependency presence, inherited model selection, researcher/verifier edit denial, and writer edit success. It does not substitute for the later packed-artifact CLI/VS Code/Agent Host matrix owned by `INT-003`.

## Full repository gate

The clean-shell repository gate passed after the runtime fixture was removed:

```bash
env -u FEATURE_FORGE_ROOT bash scripts/validate.sh
```

Result: PASS.

- Python: 2,484 passed, 2 skipped.
- Installer: 182 passed.
- Pi adapter source: 11 passed.
- Spec purity, adapter drift, ruff, requirement traceability, and four-field version sync passed.

## Cleanup and final state

- Removed `/tmp/feature-forge-forge102-probe`, including the raw JSONL session and all disposable marker files.
- `copilot plugin list`: no plugins installed.
- `copilot plugin marketplace list`: only built-in `copilot-plugins` and `awesome-copilot`.
- No personal/project Copilot customization root was created or modified.
- Rauf remained untouched at `8d65441`.
- No commit, push, merge, tag, release, publication, or `RAUF_PIN` advance occurred.
