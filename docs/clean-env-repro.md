# Clean-environment repro: forge pipeline flakiness

Executable repros for the two root causes behind the remote-environment pipeline failures
(stage confusion, re-prompting of completed stages, fabricated pipeline history, PRD mode on
an existing feature). Each repro is anchored by a `strict=True` xfail in
`tests/test_clean_env_repro.py`; when a fix lands, its xfail marker is removed in the same PR,
so this document and the suite cannot drift apart.

Run `python3 scripts/forge-session.py doctor --json` in any suspect environment first — it
captures the ground truth both repros are about (resolved plugin root + version/commit, current
vs. recorded branch, backlog-path existence) in one shot.

## Symptom → root cause

| Symptom observed in the remote test | Root cause |
| --- | --- |
| Every helper dies with `feature-forge: cannot locate plugin root` | A — candidate globs miss the marketplace-cache install path |
| Helpers work but behave like a different plugin version (version skew) | A — probe resolves the marketplace *clone* instead of the versioned cache install |
| Stage skill re-prompts a completed stage; forge-2-tech behaves like PRD mode | A (helpers dead → agent improvises state) or B (state on another branch) |
| Agent asserts pipeline state that never existed, or denies state that does | A/B — resolution returned nothing, so the agent narrated from conversational momentum |
| Navigator offers "start with forge-1-prd" for a feature that has specs | B — state lives only on the topic branch |
| "Backlog never existed" during forge-5-loop despite a verified backlog | Path mismatch hypothesis — check `doctor`'s `backlogPath`/`backlogExists` per feature |

## Root cause A: plugin-root discovery misses real marketplace installs

Claude Code installs marketplace plugins at:

```text
~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/
```

The bootstrap prelude (stamped byte-identically across the skills; canon in
`scripts/check-spec-purity.py:BOOTSTRAP_PRELUDE`) and `scripts/forge-root.sh` step 2 probe
`~/.claude/plugins/*/feature-forge` — a single `*` matches exactly one path segment, so the
cache install (three segments below `plugins/`) is invisible. Worse, the marketplace *clone*
at `~/.claude/plugins/marketplaces/<marketplace>/` can match `plugins/*/feature-forge`-shaped
probes when the marketplace repo root is itself a plugin root, silently handing scripts from a
different commit than the installed skills.

Local development never sees this because `~/.claude/skills/feature-forge` (the dev symlink)
matches the first candidate.

### Repro

```bash
FAKE_HOME="$(mktemp -d)"
INSTALL="$FAKE_HOME/.claude/plugins/cache/test-mp/feature-forge/9.9.9"
mkdir -p "$INSTALL/scripts" "$INSTALL/.claude-plugin"
printf '{"name":"feature-forge","version":"9.9.9"}\n' > "$INSTALL/.claude-plugin/plugin.json"
cp scripts/forge-root.sh "$INSTALL/scripts/" && chmod +x "$INSTALL/scripts/forge-root.sh"

# The PRE-FIX prelude (as stamped before the cache glob landed):
HOME="$FAKE_HOME" CLAUDE_PLUGIN_ROOT= FEATURE_FORGE_ROOT= bash -c '
R="$(bash -c '\''for d in "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done'\'')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
echo "resolved: $R"'
```

**Pre-fix:** `feature-forge: cannot locate plugin root` (exit 1), despite a complete, valid
install. **Fixed** by adding `"$HOME"/.claude/plugins/cache/*/feature-forge/*` ahead of the
single-star plugins glob in the canonical prelude (and a newest-`plugin.json`-first cache probe
in `forge-root.sh` step 2a) — the current prelude prints `resolved: $INSTALL`. Anchor:
`test_prelude_resolves_marketplace_cache_install` (xfail removed with the fix).

Once the prelude fails, *every* deterministic helper is unreachable — feature resolution,
`forge-session.py rank-features` (the navigator's entire status model), `epic-manifest.py` —
and the skills' STOP instruction leaves the agent to reconstruct pipeline state from the
conversation. That single failure explains the stage confusion, the re-prompting, and the
fabricated history.

## Root cause B: pipeline state invisible across branches

With `branchPerFeature: true`, `specs/<feature>/` (artifacts + `.pipeline-state.json`) exists
only on the topic branch. A session on the default branch — a fresh remote clone, or ordinary
branch drift — finds no `specs/<feature>/`, the Feature Directory Resolution returns
`not-found`, and the navigator offers to start the pipeline from scratch. Nothing looks across
branches; the state file's own `branch` field is unreachable because you must already be on the
branch to read it.

### Repro

```bash
SCRATCH="$(mktemp -d)" && cd "$SCRATCH"
git init -b main && git commit --allow-empty -m init
git checkout -b forge/widget
mkdir -p specs/widget
printf '{"feature":"widget","branch":"forge/widget","currentStage":"forge-2-tech","stages":{"forge-1-prd":{"status":"complete","version":1}}}\n' \
  > specs/widget/.pipeline-state.json
git add specs && git commit -m "forge: widget prd state"
git checkout main
ls specs/widget 2>&1   # No such file or directory — the pipeline has "vanished"
```

**Today:** from `main` there is no way for the pipeline to learn that `widget` exists (a
single-branch clone of `main` is even blinder: the topic branch isn't fetched at all).
**After the fix:** `python3 scripts/forge-session.py discover-feature widget --specs-dir specs
--json` lists `forge/widget` with its recorded stage, and emits fetch/switch commands when the
branch is only on the remote. Anchor: `test_discover_feature_finds_state_on_other_branch`.

## Verifying a real environment

In the suspect environment (e.g. a fresh remote session after the marketplace setup script):

1. `python3 <plugin-root>/scripts/forge-session.py doctor --json` — if you cannot name the
   plugin root, that *is* root cause A; find the script under
   `~/.claude/plugins/cache/*/feature-forge/*/scripts/`.
2. Check `pluginRoot.resolved`, and that `pluginRoot.root` is the versioned cache install (not
   `~/.claude/plugins/marketplaces/...`); compare `pluginRoot.version`/`commit` with the skill
   text the session loaded if version skew is suspected.
3. Check `currentBranch` vs. each feature's `stateBranch` (root cause B when they diverge).
4. Check `backlogPath`/`backlogExists` per feature before trusting any claim about the backlog.
