# 01 — Architecture & Layout

> How Epic Orchestration is structured inside the feature-forge plugin repository.
> This feature is **purely additive**: a new stage skill, a new deterministic Python
> helper, a new JSON schema, a new pytest suite, plus conditional epic-aware blocks
> grafted into existing skills. With no epic involved, every existing flow is unchanged
> (REQ-COMPAT-01/02/03).
>
> This repository **is** the plugin (the marketplace catalog and plugin manifest both
> live at the repo root with `"source": "."`; see `scripts/validate.sh`). All paths below
> are repo-root-relative.

## Requirement Coverage

| REQ ID | Requirement | Section |
|--------|-------------|---------|
| REQ-EPIC-01 | `forge-0-epic` creation stage | 1, 3 |
| REQ-DIR-01 | Self-contained epic subtree | 4 |
| REQ-DIR-02 | Standalone features unchanged | 4 |
| REQ-COMPAT-01/02/03 | Additive only, no migration | 1, 2, 6 |
| REQ-EPIC-02/03 | Manifest + narrative + schema | 4, 5 |
| testing | pytest suite wired into validate.sh | 1, 6 |

---

## 1. File Inventory

### 1.1 New files

```
skills/forge-0-epic/SKILL.md            # epic creation + edit stage (REQ-EPIC-01..06) — see 03-forge-0-epic-stage.md
scripts/epic-manifest.py                # deterministic manifest core (Python 3, stdlib only) — see 02-manifest-helper-cli.md
references/epic-manifest-schema.json    # JSON Schema for epic-manifest.json (REQ-EPIC-02) — see 00-core-definitions.md §2
tests/                                   # pytest suite + fixture epic trees — see 05-testing-strategy.md
  test_epic_manifest.py
  conftest.py
  fixtures/
    valid-epic/                          # well-formed 4-feature epic
    cyclic-epic/                         # dependsOn cycle (REQ-EPIC-05)
    dup-name/                            # duplicate feature name, flat vs nested (REQ-DIR-04)
    path-escape/                         # unsafe name / path-escape manifest (REQ-SEC-02)
    corrupt/                             # non-parseable epic-manifest.json (REQ-ROBUST-02)
    status-derivation/                   # synthetic .pipeline-state.json trees for each §7 branch
```

### 1.2 Modified files

| File | Change | Spec doc |
|------|--------|----------|
| `references/shared-conventions.md` | Add **Feature Directory Resolution** block + **Epic Context Injection** block. | 04 §3, §4 |
| `references/pipeline-state-schema.json` | Add optional `epic` back-pointer; add `forge-0-epic` + `forge-verify-epic` to `currentStage` enum and `stages` keys. | 04 §2 |
| `references/forge-config-schema.json` | No change required — `stack`/`testCommand`/`typeCheckCommand` already present (verified). | 04 §2 (note) |
| `skills/forge/SKILL.md` | Epic dashboard view; 2-tier no-arg discovery with rollup; epic lifecycle verbs; resolve nested names. | 04 §8 |
| `skills/forge-1-prd/SKILL.md` | Central dir resolution; inject epic context before interview. | 04 §5 |
| `skills/forge-2-tech/SKILL.md` | Central dir resolution; depth-2 context glob; epic context into forge-researcher dispatch. | 04 §5 |
| `skills/forge-3-specs/SKILL.md` | Central dir resolution; depth-2 spec glob; epic context into forge-spec-writer prompts. | 04 §5 |
| `skills/forge-4-backlog/SKILL.md` | Central dir resolution; per-feature backlog subpath when `backlogDir` configured. | 04 §6 |
| `skills/forge-5-loop/SKILL.md` | Central dir resolution; dependency gate (Step 1b-epic); handoff (Step 6). | 04 §7 |
| `skills/forge-6-docs/SKILL.md` | Central dir resolution; epic-level doc offer when all members complete. | 04 §10 |
| `skills/forge-verify/SKILL.md` | New `epic` mode (CHECK-E01..E08, single verifier). | 04 §9 |
| `skills/forge-fix/SKILL.md` | Central dir resolution. | 04 §11.1 |
| `skills/forge-verify/references/verification-checklists.md` | Append `## Epic Mode Checklist` (CHECK-E01..E08). | 04 §9.5 |
| `agents/forge-researcher.md` | Widen `specs/*/…` globs to find nested features. | 04 §11.2 |
| `scripts/validate.sh` | Invoke the pytest suite for the helper. | 6, 05 §5 |

> **Stack config note:** the tech spec lists `forge.config.json (new, this repo)` as a
> modified file for persisting `stack`/`testCommand`/`typeCheckCommand`. The *schema*
> (`references/forge-config-schema.json`) already defines all three keys (verified at read
> time), so no schema change is needed. Whether to author a repo-level `forge.config.json`
> is an operational choice for forge-init, not an artifact this feature must ship; the
> helper and skills fall back to built-in defaults when it is absent.

---

## 2. Dependencies & Build

### 2.1 Runtime / tooling

- **`scripts/epic-manifest.py`**: Python 3.10+, **standard library only** (no third-party
  packages) — exactly mirroring `scripts/validate-traceability.py`. No build step; invoked
  directly via `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/epic-manifest.py …`.
- **Tests**: `pytest` as a dev/test dependency only (not a plugin runtime dependency).
- **Skills**: prose markdown; no build.
- **Loop runner (rauf)**: unchanged (REQ-COMPAT-03) — no version bump, no schema change.

### 2.2 Invocation convention

Skills invoke the helper through the established plugin-root convention already used for
`validate-traceability.py` (e.g. `forge-verify/SKILL.md` invokes
`${CLAUDE_PLUGIN_ROOT}/scripts/validate-traceability.py`):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/epic-manifest.py" resolve <name> --specs-dir "<specsDir>"
```

`${CLAUDE_PLUGIN_ROOT}` resolves to the installed plugin root; in this repo it is the repo
root. The `--specs-dir` argument carries the project's configured `specsDir` (default
`./specs`), resolved against the **project** cwd, not the plugin root.

---

## 3. `epic-manifest.py` Module Structure

A single self-contained CLI module, organized as `validate-traceability.py` is (module
docstring with usage + exit codes; small pure functions; an `argparse` dispatch in
`main()`; `sys.exit(main())` guard). Full signatures are in 02-manifest-helper-cli.md;
the layout is:

```
scripts/epic-manifest.py
├── module docstring                      # usage + exit-code contract (00 §9)
├── constants                             # SAFE_NAME_RE, *_FILENAME (00 §6)
├── Finding / typed structures            # mirror 00 §4, §5; Rollup/RenderStatus per 02 §8.4
├── safety layer
│   ├── assert_safe_name(name) -> None
│   └── contained_path(base, *parts) -> Path
├── manifest I/O
│   ├── load_manifest(epic_dir) -> dict          # parse + corrupt-json finding
│   └── atomic_write(path, data) -> None         # temp file + os.replace (REQ-ROBUST-03)
├── graph
│   ├── find_cycle(features) -> list[str] | None # DFS/Kahn (REQ-EPIC-05)
│   └── unmet_deps(name, features, status_map) -> list[str]
├── resolution
│   ├── feature_dirs(specs_dir) -> dict[str, list[Path]]   # name -> dirs (uniqueness)
│   └── resolve(name, specs_dir) -> Path
├── status derivation
│   ├── derive_status(feature_dir) -> FeatureStatus        # 00 §5
│   ├── is_complete_for_orchestration(state) -> bool       # 00 §7 completion rule
│   └── render_status(epic_dir, specs_dir) -> RenderStatus  # 00 §5, §8
├── validation
│   └── validate(epic_dir, specs_dir) -> list[Finding]
├── mutators
│   └── add_feature / remove_feature / reorder / set_dep / set_status   # atomic + re-validate
└── main()                                # argparse subcommand dispatch -> exit code
```

No class hierarchy is required; the script is a flat collection of pure-ish functions plus
the I/O layer, consistent with the existing helper's style.

---

## 4. Directory Layout — Epic Subtree vs Flat (REQ-DIR-01/02)

### 4.1 Epic subtree (new)

```
{specsDir}/
  {epic}/                          # e.g. specs/auth-overhaul/
    epic-manifest.json             # single source of truth (00 §2)
    EPIC.md                        # human-readable narrative (00 §2, 03 §4)
    .verification/                 # epic-mode verify findings (VERIFY-epic-{date}.md)
    {feature-a}/                   # member feature — standard pipeline artifacts
      .pipeline-state.json         #   carries "epic": "{epic}" back-pointer (00 §3)
      PRD.md  tech-spec.md  ##-*.md  backlog.json  …
    {feature-b}/
      .pipeline-state.json
      …
```

Each member-feature subdirectory holds exactly the **same** artifact set a standalone
feature holds — the layout mirrors the flat layout one level deeper (REQ-DIR-01). At epic
creation, member subdirectories are created with only a `.pipeline-state.json` (carrying
the `epic` back-pointer, `currentStage: forge-0-epic` or `forge-1-prd`) so the navigator
and resolver can see them before any stage runs (03-forge-0-epic-stage.md §5).

### 4.2 Flat standalone feature (unchanged — REQ-DIR-02)

```
{specsDir}/
  {feature}/                       # e.g. specs/agent-agnostic/
    .pipeline-state.json           # no "epic" field
    PRD.md  tech-spec.md  …
```

A standalone feature's `.pipeline-state.json` has no `epic` key; every skill behaves
exactly as today. The resolver (02 §4) returns the flat path for such names with no epic
logic engaged.

### 4.3 Distinguishing the two

- An **epic directory** is any `{specsDir}/*/` that directly contains `epic-manifest.json`.
- A **feature directory** is any directory that directly contains `.pipeline-state.json`
  (00 §6) — whether flat (`{specsDir}/{feature}/`) or nested
  (`{specsDir}/{epic}/{feature}/`).
- A `{specsDir}/{epic}/` directory contains `epic-manifest.json` but **no**
  `.pipeline-state.json` of its own, so it is recognized as an epic and never mistaken for
  a feature.

---

## 5. Module Export / Public Surface

This is a prose plugin; the "exports" are the CLI subcommands of `epic-manifest.py` and
the on-disk schemas. The complete public surface:

| Surface | Consumers |
|---------|-----------|
| `epic-manifest.py` subcommands: `resolve`, `validate`, `check-name`, `render-status`, `add-feature`, `remove-feature`, `reorder`, `set-dep`, `set-status` | every stage skill (resolution), forge-0-epic (mutations), forge navigator (render-status), forge-verify epic mode (validate). See 02. |
| `references/epic-manifest-schema.json` | `validate` subcommand; forge-verify epic mode CHECK-E01. |
| `epic-manifest.json` (on disk, per epic) | all of the above. |
| `EPIC.md` (on disk, per epic) | context injection (04 §4), forge-6-docs, forge-verify CHECK-E06. |
| `.pipeline-state.json` `epic` field | resolver, context injection, navigator. |

No Python symbols are imported across module boundaries — every cross-skill call goes
through the CLI (Bash), keeping the deterministic core in one auditable place.

---

## 6. Build, Test, and Deployment Wiring

- **`scripts/validate.sh`** gains a step that runs the helper's pytest suite (and a
  lightweight `py_compile` static check), gated on `pytest` availability so the existing
  plugin-structure checks still pass on machines without pytest installed. Exact wiring is
  in 05-testing-strategy.md §5. The commands mirror the `forge.config.json`
  `testCommand` / `typeCheckCommand` defaults:
  - `testCommand` default: `bash scripts/validate.sh`
  - `typeCheckCommand` default: `python3 -m py_compile scripts/epic-manifest.py`
- **Script permissions:** `validate.sh` already asserts every `scripts/*.sh` is
  executable. `epic-manifest.py` is invoked via `python3 …` (like
  `validate-traceability.py`), so it does **not** need the executable bit; no new
  permission check is required.
- **Deployment:** none beyond shipping the new files in the plugin. No marketplace/plugin
  manifest change is required (the new skill is auto-discovered under `skills/`).

---

## Dependencies

- 00-core-definitions.md — all schemas, constants, and the completion rule referenced here.

## Verification

- [ ] `bash scripts/validate.sh` passes with the new files present (frontmatter on
      `skills/forge-0-epic/SKILL.md`, valid JSON for `epic-manifest-schema.json`).
- [ ] `python3 -m py_compile scripts/epic-manifest.py` exits 0.
- [ ] A nested epic subtree and a flat feature coexist under `{specsDir}` and each
      resolves correctly (02 §4 verification).
- [ ] `{specsDir}/{epic}/` is recognized as an epic (has `epic-manifest.json`, no
      `.pipeline-state.json`) and is not listed as a standalone feature by the navigator.
