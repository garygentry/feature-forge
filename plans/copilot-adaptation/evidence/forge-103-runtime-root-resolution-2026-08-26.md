# FORGE-103 Runtime-Root Resolution Evidence — 2026-08-26

Status: Implementation, Linux/Copilot runtime probes, cleanup, and the full clean-shell repository gate pass in the uncommitted feature-forge worktree; FORGE-103 remains ACTIVE pending authorized push and fresh-clone durability.

## Attribution and environment

- Repository: feature-forge, base commit `93de3c95c8f204d392eff76dbbffac9d94f78e69` on `docs/copilot-g2-contract`.
- Implementation-source dirty-diff identity: SHA-256 `9ce8e1d30c718a6d20198358d43e353f7c4bfa94233e633feede71cc4c355e92` from `git diff -- scripts skills references tests eval | sha256sum` after review fixes and before the full gate.
- OS: Linux 5.15.0-185-generic, x86_64, native (not WSL).
- GitHub Copilot CLI: 1.0.80.
- Generated product version: 0.18.0.
- Disposable marketplace commits: initial `10d9ae9f244a22323fbc31cac2e3e4f7fa8f0508`; regenerated final `649df5db0c8cd9725fd33e39287d0aed3374b3c3`.
- Secrets excluded: no credential, token, account identifier, raw environment dump, unrelated user configuration, or full model transcript is retained.

## Implemented contract

Runtime-root precedence is now:

1. explicit, complete `FEATURE_FORGE_ROOT`;
2. package-owned resolver self-location;
3. bounded conventional candidates, including Copilot personal and managed-plugin roots;
4. bounded ancestor probes for project `.github/feature-forge` and existing Pi `.pi/skills/feature-forge` roots;
5. legacy `CLAUDE_PLUGIN_ROOT` compatibility;
6. distinct degraded or generic actionable failure.

A partial candidate is remembered but never accepted when a complete candidate is available later. The canonical bootstrap is byte-pinned across canon. Copilot-emitted executable preludes apply project-over-global ordering, then managed/personal Copilot roots, then other-host compatibility roots. The resolver and generated Copilot script contain no generic `${PLUGIN_ROOT}` or `$PLUGIN_ROOT` dependency.

Resolver hash, identical in canon and the generated Copilot bundle:

```text
6a9f1598e23377b83b1b34dc1db360a2522d488464c0b8ad7dbb52b680161f4b
```

Generated Copilot `skills/forge/SKILL.md` hash:

```text
a4934e180f62e687678cec49f501de16ccb9ff967dc2a5c426a0ca390cf6e694
```

## Deterministic checks

Commands and results before this receipt:

```bash
pytest -q tests/test_adapter_host_neutrality.py tests/test_build_adapters.py \
  tests/test_forge_root.py tests/test_clean_env_repro.py tests/test_compliance_eval.py
# 815 passed

python3 scripts/build-adapters.py --check
git diff --check
# both exit 0

cmp scripts/forge-root.sh adapters/copilot/scripts/forge-root.sh
! rg -n '\$\{PLUGIN_ROOT|\$PLUGIN_ROOT' \
  scripts/forge-root.sh adapters/copilot/scripts/forge-root.sh
# both exit 0
```

Coverage includes override precedence, self-location, Copilot personal and installed-plugin roots, project invocation from nested directories, complete-over-partial selection, distinct degraded failure, neutral sentinels, spaces and shell metacharacters, guarded ancestor traversal failure, Claude cache/version precedence, Codex/Cursor/Gemini fixed layouts, and existing Pi ancestor/package layouts.

## Actual Copilot CLI runtime probes

A disposable local marketplace named `forge103-runtime-probe` copied regenerated `adapters/copilot/` and added one bounded `root-probe` skill. CLI installation reported `Installed 14 skills`; `copilot skill list --json` discovered the probe. The final installed resolver hash matched source byte-for-byte.

All successful invocations used this bounded host shape:

```bash
copilot -C '<nested fixture path>' \
  --allow-all --no-custom-instructions --disable-builtin-mcps \
  --no-remote --no-auto-update --output-format json --stream off \
  -p '<exact slash skill>'
```

### Managed plugin self-location

Command prompt: `/feature-forge:root-probe`, from a nested unrelated workspace, with `FEATURE_FORGE_ROOT` removed from the parent environment.

Expected and actual final output:

```text
FORGE103_ROOT=/home/gary/.copilot/installed-plugins/forge103-runtime-probe/feature-forge
FORGE103_SELF_LOCATION=PASS
```

The first non-interactive attempt intentionally lacked permissions and was denied before executing the block. After adding the documented `--allow-all` permission boundary, an intermediate run exposed a real precedence defect: the maintainer's separate `~/.agents/skills/feature-forge` dogfood install shadowed the loaded Copilot plugin. The implementation was corrected so Copilot-emitted preludes prefer Copilot package roots over other-host global roots; the final output above then passed. No failed output was treated as success.

### Nested project runtime with adversarial path

A direct project skill and complete runtime bundle were placed under:

```text
/tmp/feature-forge-forge103-project [draft] $v1;safe/.github/
```

Invocation ran from `src [pkg]/deep;$dir` while the disposable managed plugin and the maintainer's global dogfood install both still existed. Exact direct skill: `/forge103-project-root`.

Expected and actual final output:

```text
FORGE103_PROJECT_ROOT=/tmp/feature-forge-forge103-project [draft] $v1;safe/.github/feature-forge
FORGE103_PROJECT_NESTED=PASS
```

This proves project-over-global precedence, bounded ancestor bootstrap, resolver ancestor discovery, and quoting across spaces plus `[`, `]`, `$`, and `;` metacharacters.

### Personal direct runtime

A disposable direct personal skill was placed at `~/.copilot/skills/forge103-personal-root` and a complete runtime bundle at `~/.copilot/feature-forge`. No managed plugin or project runtime existed for this probe; the maintainer's unrelated `~/.agents` dogfood install remained present. Exact direct skill: `/forge103-personal-root`.

Expected and actual final output:

```text
FORGE103_PERSONAL_ROOT=/home/gary/.copilot/feature-forge
FORGE103_PERSONAL=PASS
```

An `EXIT` trap removed both personal paths, the temporary workspace, and raw JSONL output. Follow-up path checks passed.

### Explicit operator override

With the same nested project and installed plugin present, the parent process set:

```text
FEATURE_FORGE_ROOT=/tmp/feature-forge-forge103-override [ops] $root;safe
```

Exact direct skill: `/forge103-override-root`.

Expected and actual final output:

```text
FORGE103_OVERRIDE_ROOT=/tmp/feature-forge-forge103-override [ops] $root;safe
FORGE103_OVERRIDE=PASS
```

This proves the explicit neutral override reaches the Copilot tool shell and outranks both project and managed-plugin roots.

## Degraded-layout probe

A copied Copilot bundle at `/tmp/feature-forge-forge103-degraded [partial]` had `references/pipeline-state-schema.json` removed. With all unrelated root hints isolated, its resolver exited 1 and printed:

```text
feature-forge: install incomplete/degraded at /tmp/feature-forge-forge103-degraded [partial] (missing references/pipeline-state-schema.json) — reinstall with 'npx @garygentry/feature-forge' (or 'feature-forge update' for a stale install).
```

No root was printed to stdout.

## Full repository gate

The first clean-shell gate exposed three stale spec-purity fixtures after the prelude sentinel changed; no production failure was ignored. The clean fixture was updated to the new byte-pinned prelude, both negative fixtures retained intentionally drifted commands with the new sentinel, and their 232-test focused slice passed. The full gate was then rerun:

```bash
env -u FEATURE_FORGE_ROOT bash scripts/validate.sh
```

Result: PASS.

- Python: 2,496 passed, 2 skipped.
- Installer: 182 passed.
- Pi adapter source: 11 passed.
- Spec purity, adapter drift, ruff, traceability, and four-field version sync: passed.

## Cleanup and remaining closure work

The disposable plugin, marketplace, copied project/personal/degraded roots, raw JSONL outputs, and temporary workspaces were removed. Registry verification showed no installed plugins and only the built-in `copilot-plugins` and `awesome-copilot` marketplaces; every named fixture path was absent. No repository files were modified by the runtime probes.

An independent read-only review found one unguarded-ancestor-loop defect and one stale inventory description. The loop now uses `cd ..||break`, a `BASH_ENV` failure-injection test proves it terminates when traversal fails, and the inventory identifies the neutral override first plus legacy Claude fallback at resolver step 4. No review findings remain open before the full gate.

FORGE-103 remains ACTIVE until:

1. the implementation/evidence is committed and pushed only with explicit user authorization;
2. a fresh clone reproduces the focused checks and generated hashes.

No merge, tag, release, publication, rauf change, or `RAUF_PIN` advance is authorized or performed.
