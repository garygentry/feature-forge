# 01 — Architecture & Layout

> How **forge-bootstrap** is structured inside the feature-forge plugin repository. This
> feature is **purely additive**: a new unnumbered skill, a new deterministic Python helper,
> a new template tree, one additive JSON-schema field, and a new pytest file — plus
> regenerated adapter bundles. With bootstrap unused, every existing forge flow behaves
> byte-for-byte as before (PRD §6, Success Criteria "Additivity").
>
> This repository **is** the plugin: the marketplace catalog
> (`.claude-plugin/marketplace.json`) and the plugin manifest
> (`.claude-plugin/plugin.json`) both live at the repo root with `"source": "."` (see
> `scripts/validate.sh`). All paths below are repo-root-relative.

## Requirement Coverage

| REQ ID | Requirement | Section |
|--------|-------------|---------|
| REQ-PORT-02 | Portable-root resolution; no Claude-only mechanism | 2, 3 |
| REQ-CFG-02 | Mirror forge-init config behavior (no schema change to existing fields) | 4 (note) |
| REQ-MONO-05 | Additive `workspaces[]` schema extension | 4 |
| REQ-SCAF-* | Editable per-stack template assets | 1, 5 |
| REQ-STACK-01 | Five stack template directories | 5 |
| — (packaging) | Unnumbered skill; spec-purity budget; adapter regen | 1, 6 |
| — (testing) | pytest suite wired into validate.sh | 6 |

---

## 1. File Inventory

### 1.1 New files

```
skills/forge-bootstrap/
  SKILL.md                                # interview + orchestration (≤300 lines / ≤5000 words — §6.1) — see 04
  references/
    templates/
      typescript/                         # package.json, tsconfig.json, src/index.ts,
                                          #   test/smoke.test.ts, .gitignore
      python/                             # pyproject.toml, src/{{PKG}}/__init__.py,
                                          #   src/{{PKG}}/main.py, tests/test_smoke.py, .gitignore
      go/                                 # go.mod, main.go, main_test.go, .gitignore
      rust/                               # Cargo.toml, src/main.rs, src/lib.rs,
                                          #   tests/smoke.rs, .gitignore (lib.rs exposes
                                          #   greet() so the smoke integration crate links it — 03 §5.2)
      generic/                            # run.sh, test.sh, .gitignore
      ci/
        github-actions.yml                # composed per-member when ci:true — see 03 §9, 04
      hygiene/                            # README.md, AGENTS.md, CLAUDE.md — repo-level
                                          #   hygiene stubs (REQ-SCAF-06) — see 03 §10
      licenses/                           # MIT/LICENSE, Apache-2.0/LICENSE — bundled,
                                          #   tokenized license texts (REQ-INPUT-05) — see 03 §10
scripts/
  forge-bootstrap.py                      # deterministic helper CLI (stdlib only) — see 02
tests/
  test_forge_bootstrap.py                 # pytest; auto-run by validate.sh's tests/ sweep — see 05
```

> Template directories hold the per-stack scaffold files (03-stack-templates.md §1). They
> are **editable assets**, not generated — the helper composes them with light token
> substitution (00 §6.2). Each `templates/<stack>/` maps 1:1 to a `Stack` value (00 §2).

### 1.2 Modified files

| File | Change | Spec doc |
|------|--------|----------|
| `references/forge-config-schema.json` | **Additive** optional `workspaces[]` array (00 §7.1). No existing field changes. | 00 §7.1 |
| `scripts/validate.sh` | Add a `py_compile` check for `scripts/forge-bootstrap.py` alongside the existing helper compile-check. The `tests/` pytest sweep already picks up `test_forge_bootstrap.py` with no change. | 6, 05 §5 |
| `adapters/**` | **Regenerated** via `python3 scripts/build-adapters.py` (the new skill + its `references/` propagate automatically). Hard CI gate (`validate.sh` runs `build-adapters.py --check` over `adapters/`). | 6 |

No edits are needed to `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`hooks/hooks.json`, or `scripts/build-adapters.py` — skills are glob-discovered under
`skills/`, and a skill's `references/` tree is auto-propagated to adapters by the existing
generator (tech-spec §2). The session-start hook operates pre-config and already exits 0
when no `forge.config.json`/specs exist, so it is unaffected (tech-spec §6).

---

## 2. Dependencies & Build

### 2.1 Runtime / tooling

- **`scripts/forge-bootstrap.py`**: Python 3.10+, **standard library only** — no third-party
  packages, mirroring `scripts/epic-manifest.py` and `scripts/validate-traceability.py`. No
  build step; invoked directly via `python3 …`. Uses `subprocess` for `git`, `command -v`
  toolchain probes, and the resolved lint/test commands; `shutil`/`pathlib` for template
  composition; `json` for the sentinel, `--answers`, and `forge.config.json`.
- **Git CLI**: already assumed by the pipeline (used for `git init` and the baseline commit).
- **Scaffolded-project toolchains** (node/vitest, python/mypy/pytest, go, cargo, sh) are the
  **user's machine concern**, detected at `verify` time (REQ-LIFE-03) and **never installed**
  by bootstrap (tech-spec §9). Templates favor minimal dev-deps (TS pins only `typescript` +
  `vitest`, matching `typescript.md`; OQ-T2).
- **Tests**: `pytest` as a dev/test dependency only — not a plugin runtime dependency.
- **Skills / templates**: prose markdown + plain text assets; no build.

### 2.2 Invocation convention (REQ-PORT-02)

The skill locates the plugin root with the byte-identical portable-root prelude used across
the pipeline, then invokes the helper (00 §1.1):

```bash
R="$(for d in "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/*/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done)"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-bootstrap.py" check "." --specs-dir "<specsDir>"
```

`forge-root.sh` is content-addressed (it identifies a plugin root by the presence of
`scripts/epic-manifest.py` + `.claude-plugin/plugin.json`), so it works under any agent's
directory layout — no Claude-only mechanism (REQ-PORT-02). The `<target-dir>` positional is
the **project** cwd being bootstrapped, distinct from `$R` (the plugin root).

---

## 3. `forge-bootstrap.py` Module Structure

A single self-contained CLI module organized exactly like `scripts/epic-manifest.py`: a
module docstring with usage + the 00 §9 exit-code contract; module constants; small
pure-ish functions; a `subprocess`/`pathlib` I/O layer; an `argparse` subcommand dispatch in
`main()` guarded by `if __name__ == "__main__": sys.exit(main())`. Full signatures are in
02-helper-cli.md; the layout:

```
scripts/forge-bootstrap.py
├── module docstring                       # usage + exit-code contract (00 §9)
├── constants                              # ALLOWED_META_FILE_RE, SENTINEL_FILENAME,
│                                          #   Stack, PACKAGE_MANAGERS, STACK_COMMANDS (00 §2/§3/§6)
├── typed structures                       # Sentinel, Answers, Member, CheckResult,
│                                          #   VerifyResult, CommitResult (mirror 00 §4/§5/§8)
├── internal exceptions                    # UsageError (exit 2), FindingsError (exit 1) — as in epic-manifest.py §2
├── safety / IO layer
│   ├── read_sentinel / write_sentinel(target) # transient marker (00 §8)
│   └── run(cmd, cwd) -> CompletedProcess   # subprocess wrapper (git, toolchain, lint/test)
├── gate
│   └── check(target, specs_dir) -> CheckResult        # greenfield + recovery (02 §3)
├── scaffold
│   ├── compose_member(member, target)      # template copy + token substitution (02 §4);
│   │                                        #   template root = <repo-root>/skills/forge-bootstrap/
│   │                                        #   references/templates/<stack> (helper at scripts/, §1.1)
│   ├── write_config(answers, target)       # forge.config.json + workspaces[] (02 §4.3)
│   └── scaffold(target, answers) -> list[str]  # git init; per-member compose; idempotent
├── verify
│   ├── toolchain_present(stacks, pms) -> bool          # command -v probes (02 §5)
│   └── verify(target, answers) -> VerifyResult         # resolved lint/test per member
├── commit
│   └── commit(target, answers, stage_only) -> CommitResult  # exact-list stage; sentinel removal
├── status
│   └── status(target) -> Sentinel | None   # inspect the marker for resume (02 §6)
└── main()                                  # argparse subcommand dispatch -> exit code
```

No class hierarchy is required; the script is a flat collection of functions plus the I/O
layer, consistent with the existing helper's style.

---

## 4. Schema Extension (REQ-MONO-05, REQ-CFG-02)

`references/forge-config-schema.json` is the only existing reference file modified, and the
change is **purely additive**: a new optional `workspaces[]` property (00 §7.1, tech-spec
§3.2). No existing property is altered, so every current `forge.config.json` validates
unchanged (REQ-COMPAT). The three keys bootstrap resolves — `stack`, `typeCheckCommand`,
`testCommand` — already exist in the schema (verified against the on-disk schema), so the
**only** schema edit is adding `workspaces`.

> **forge-init equivalence (REQ-CFG-02):** bootstrap reproduces `forge-init.sh`'s exact
> emitted field set + defaults (00 §7) rather than calling the script (which writes
> `stack`/commands = `null` and no `loopRunner`). The schema is the shared contract both
> conform to.

---

## 5. Template Tree & Public Surface

This is a prose plugin; its "exports" are the helper's CLI subcommands and the on-disk
assets. The complete public surface:

| Surface | Consumers |
|---------|-----------|
| `forge-bootstrap.py` subcommands: `check`, `scaffold`, `verify`, `commit`, `status` | the `forge-bootstrap` skill body (02). |
| `skills/forge-bootstrap/references/templates/<stack>/` | `scaffold` (composes them; 03). |
| `skills/forge-bootstrap/references/templates/ci/github-actions.yml` | `scaffold` when `ci:true` (03 §9). |
| `skills/forge-bootstrap/references/templates/hygiene/` + `licenses/` | `scaffold` `write_hygiene` (README/LICENSE/agent files; 02 §4.5, 03 §10). |
| `.forge-bootstrap.json` sentinel (on disk, transient) | `check` / `scaffold` / `commit` / `status` (00 §8). |
| `forge.config.json` (on disk, produced) | the whole pipeline downstream (00 §7). |
| `references/forge-config-schema.json` `workspaces[]` | `write_config`; any future member-resolution consumer (OQ-T1). |

Each `templates/<stack>/` directory holds exactly the files listed in §1.1, with tokens
(`{{PROJECT_NAME}}`, `{{PKG}}`, `{{PM}}`, `{{PURPOSE}}`; 00 §6.2) substituted at compose
time. The directory set is the single source of truth for "what a stack scaffold contains,"
referenced by both `scaffold` (02 §4) and the per-stack tests (05).

---

## 6. Build, Test & Deployment Wiring

### 6.1 Spec-purity budget (`scripts/check-spec-purity.py`)

`SKILL.md` is subject to the repo's spec-purity checker, a **hard** `validate.sh` gate
(never soft-skipped): the prose **body** must stay ≤ **300 lines** and ≤ **5000 words**
(`MAX_BODY_LINES` / `MAX_BODY_WORDS`). This is the architectural reason the deterministic
mechanics live in the Python helper rather than in skill prose (tech-spec §3.1): the skill
body holds only the interview, decisions, and orchestration (04), delegating all file
generation to `forge-bootstrap.py`.

### 6.2 `validate.sh`

`scripts/validate.sh` already (a) runs the spec-purity checker (hard gate), (b) checks
`adapters/` is in sync via `build-adapters.py --check` (hard gate), and (c) compiles
`epic-manifest.py` and runs the **whole** `tests/` directory under pytest (soft-skipped when
pytest is absent). Two wiring touches:

- **Add** a `python3 -m py_compile scripts/forge-bootstrap.py` check next to the existing
  `epic-manifest.py` compile-check, mirroring its `PASS:`/`FAIL:` + `ERRORS=$((ERRORS + 1))`
  style (the `typeCheckCommand` analogue for the new helper).
- **No change** is needed to wire the new tests: the pytest step already runs
  `python3 -m pytest "$REPO_ROOT/tests" -q`, which discovers `test_forge_bootstrap.py`
  automatically (05 §5).

### 6.3 Adapter regeneration (hard gate)

After adding `skills/forge-bootstrap/` (SKILL.md + `references/templates/`), regenerate the
per-agent bundles with `python3 scripts/build-adapters.py` and commit the result. The
generator discovers the new skill by glob and propagates its `references/` tree
automatically — **no generator code change**. `validate.sh` runs `build-adapters.py --check`
(regenerate to a temp dir, `diff -r` vs committed `adapters/`) as a hard gate, so a missing
regeneration fails CI ("adapters/ is out of date — run 'python3 scripts/build-adapters.py'
and commit the result").

### 6.4 Deployment

None beyond shipping the new files in the plugin. The new skill is auto-discovered under
`skills/`; no marketplace/plugin-manifest change is required.

---

## Dependencies

- **00-core-definitions.md** — all schemas, constants, result/answer/sentinel shapes, the
  per-stack command table, and the exit-code contract referenced here.

## Verification

- [ ] `bash scripts/validate.sh` passes with the new files present: spec-purity clean for
      `skills/forge-bootstrap/SKILL.md` (body ≤300 lines / ≤5000 words, §6.1), valid JSON for
      the extended `references/forge-config-schema.json`, and `adapters/` in sync (§6.3).
- [ ] `python3 -m py_compile scripts/forge-bootstrap.py` exits 0 (§6.2).
- [ ] `python3 scripts/build-adapters.py --check` exits 0 after regeneration (§6.3).
- [ ] Each of the five `Stack` values has a populated `templates/<stack>/` directory whose
      file set matches §1.1 / 03 §1 (REQ-STACK-01).
- [ ] A pre-existing `forge.config.json` (no `workspaces`) still validates against the
      extended schema (§4, additive-only guarantee).
- [ ] With `skills/forge-bootstrap/` removed from discovery, every existing forge-* command
      and `validate.sh` behave identically (additivity).
