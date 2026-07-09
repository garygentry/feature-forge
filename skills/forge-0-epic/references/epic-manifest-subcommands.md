# forge-0-epic — `epic-manifest.py` Subcommand Reference

Lookup detail relocated out of the `forge-0-epic` SKILL.md body (Step E3 command
catalog + exit-code disposition, and the Error Handling table). The skill body keeps
the decision logic and step ordering; this file is the flag-surface catalog and the
per-subcommand exit-code reference.

## Edit-Mode Mutator Flag Surface (Step E3)

Issue the chosen mutator. Each writes atomically and re-runs full validation internally, refusing
the write if it would introduce a cycle, dangling ref, duplicate, or schema violation. The exact
flag surface (owned by 02 §7):

```bash
R="$(bash -c 'for d in "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
# Add a feature — seeds EMPTY exposes/consumes; contracts are populated below.
python3 "$R/scripts/epic-manifest.py" add-feature "{epic}" "{feature}" \
  --charter "…" --specs-dir "{specsDir}" [--depends-on a,b]

# Remove a feature (drops its manifest entry; directory is left in place — see E3 note).
python3 "$R/scripts/epic-manifest.py" remove-feature "{epic}" "{feature}" \
  --specs-dir "{specsDir}"

# Reorder the features[] sequence (must be an exact permutation of current member names).
python3 "$R/scripts/epic-manifest.py" reorder "{epic}" \
  --order "feat-a,feat-c,feat-b" --specs-dir "{specsDir}"

# Change a dependency edge (--depends-on "" clears it).
python3 "$R/scripts/epic-manifest.py" set-dep "{epic}" "{feature}" \
  --depends-on "config-store,token-service" --specs-dir "{specsDir}"

# Change epic lifecycle status (active|paused|abandoned|complete).
python3 "$R/scripts/epic-manifest.py" set-status "{epic}" \
  --status paused --specs-dir "{specsDir}"
```

### Per-Subcommand Exit-Code Disposition (Step E3)

- Exit `0` → the mutator wrote the manifest and bumped `updatedAt`. Proceed to E4/E5.
- Exit `1` → surface the `findings[]` **verbatim** and **abort the edit**. The manifest is
  unchanged (the write was refused atomically — byte-identical). Loop back to E2 or re-elicit.
- Exit `2` → unsafe name / missing|corrupt manifest / bad `--status` value / write failure.
  Surface and STOP.

## Error Handling

The skill **never** repairs a corrupt manifest automatically and **never** proceeds past a gating
helper exit `≥ 1`. All findings are surfaced **verbatim**.

| Condition | Helper signal | Skill behavior |
|-----------|---------------|----------------|
| Epic name duplicates an existing name | `check-name` exit 1 (`duplicate-name`) | STOP creation; surface finding; ask for a new name via `AskUserQuestion` |
| Member feature name duplicates | `check-name` exit 1 (`duplicate-name`) | Reject that name in C2 / add-feature; surface verbatim; re-prompt |
| Unsafe name (`/`, `..`, absolute) | `check-name`/mutator exit 2 (`unsafe-name`) | Reject; surface; re-prompt |
| Composed manifest has a cycle | `validate` exit 1 (`cycle`) | Surface verbatim; re-open the dependency interview (C4); never finalize |
| Dangling `dependsOn`/`consumes.from` | `validate` exit 1 (`dangling-ref`) | Surface verbatim; re-open C4 (bad `dependsOn`) or C3 (bad `consumes.from`) |
| Corrupt/unparseable manifest (edit) | `validate` exit 1 (`corrupt-json`) | Surface ALL findings verbatim; **refuse all mutation** until repaired; never auto-repair |
| Existing manifest otherwise invalid (edit) | `validate` exit 1/2 | Surface ALL findings verbatim; **refuse all mutation** (E1) |
| Mutator would introduce cycle/dangling ref/duplicate | mutator exit 1 | Abort the edit; manifest byte-identical (atomic refusal); surface finding |
| Bad `--status` value | `set-status` exit 2 (argparse) | Surface; re-prompt via `AskUserQuestion` with the valid choices |
| Edit affects in-flight/completed feature | `render-status` derived status (`in-progress`/`complete`) | Warn naming the affected feature(s); require confirmation before applying (E4) |
| `render-status` over an invalid graph | `render-status` exit ≥ 1 | Surface findings; STOP (do not mutate over an invalid graph) |
| Git commit fails | — | Report; leave state `in-progress`; never bypass hooks (`--no-verify`/`--force`) |
