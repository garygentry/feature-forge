# 06 — Testing Strategy

> How every split/moved file and every new script verb is proven correct and
> kept from drifting. Because `context-efficiency` is a **behavior-preserving**
> optimization, the test suite's job is not "does the feature work" but "did
> anything *change* that should not have" — so it is dominated by **drift
> guards** (one per revert unit) plus a **stdlib schema validator** for the R4/R5
> script output, and a **measurement procedure** that turns the token-saving
> claim into a reproducible before/after rather than a review judgment.
>
> Builds on `00-core-definitions.md` (§3.4 stdlib-only, §4 state shapes, §7
> CHECK-ID inventory), `01-architecture-layout.md` (§6 test surface), and each
> domain doc's "drift-guard requirement" subsection — this document owns the
> actual assertions those docs defer to.

## Requirement Coverage

| REQ ID | Requirement | Section |
|--------|-------------|---------|
| REQ-MAINT-01 | Drift-guard discipline extended to every split/moved file | §3 (per-unit guards), §4 (validator), §5 (catch-all) |
| REQ-PERF-01 | Each R shows a measured net reduction on its targeted invocation | §7 (measurement) |
| REQ-PERF-02 | No increase in always-loaded surface (frontmatter + hook) | §7.3 (green/red guard) |
| REQ-OBS-01 | Baselines re-measured from real transcripts; method recorded | §7.1, §7.2 |
| REQ-OBS-02 | R4 read-frequency confirmed from transcripts; reported saving scaled | §7.4 |
| REQ-R4-03 | Schema stays CI source of truth (test-enforced) | §4 (validator) |
| REQ-R1-05 | Every mode's CHECK-IDs preserved | §3.1 |
| REQ-R6-01/02 | Runner-contract split preserves every section; gated load | §3.6 |
| SC-4 | Tests green + drift coverage for every split/moved file | §3–§6 |
| SC-1/SC-2 | Per-R reduction + directional aggregate | §7 |

---

## 1. Framework & conventions

- **Runner:** `python3 -m pytest tests` (the project `testCommand`). New tests live
  under `tests/` as `test_*.py`.
- **Stdlib only (C-2).** No `jsonschema` (absent in CI), no third-party imports.
  The schema validator is hand-rolled (§4), mirroring `epic-manifest.py`'s
  `_schema_findings()` precedent.
- **Assert against canon, never adapters.** Following the
  `test_stage_exit_protocol.py` discipline: resolve paths from a module-level
  `REPO_ROOT`, and assert against `skills/` / `references/` / `scripts/` — never
  the generated `adapters/` tree (that is `test_build_adapters.py`'s job).

```python
# tests/_forge_paths.py  (shared helper, mirrors test_stage_exit_protocol.py)
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS = REPO_ROOT / "skills"
REFERENCES = REPO_ROOT / "references"
SCRIPTS = REPO_ROOT / "scripts"


def read(path: Path) -> str:
    """Read a canon file as UTF-8; fail loudly if a spec'd file is missing."""
    assert path.is_file(), f"expected canon file missing: {path}"
    return path.read_text(encoding="utf-8")
```

- **Local gate before every push** (tech-spec §8): `bash scripts/validate.sh`
  (regen-diff + purity + traceability + installer) **and** `ruff check scripts/
  eval/` (CI-only; run locally, C-2).

## 2. What must stay green (regression baseline)

These existing guards MUST continue to pass unchanged — they are the "we did not
break behavior" backstop:

- `test_config_defaults_parity.py` (the 22 loopRunner defaults; R5 reads the same)
- `test_pipeline_state_schema.py` (schema validity; R4 leaves the schema untouched)
- `test_stage_exit_protocol.py` (stage-exit directives; R4 leaves stage-exit prose intact)
- `test_build_adapters.py` snapshot (after the fixture refresh in §6)

## 3. Per-unit drift guards (REQ-MAINT-01)

One guard file per revert unit, so a unit's regression fails an isolated test.

### 3.1 R1 — `tests/test_verification_checklists_split.py`

Asserts the split preserved every CHECK-ID and leaked no orchestrator material
(`00-core-definitions.md §7`; `02-verify-checklist-split.md §9`):

```python
import re
from _forge_paths import SKILLS, read

VC_DIR = SKILLS / "forge-verify" / "references" / "verification-checklists"
EXPECTED = {  # verified against the pre-split source
    "prd": ("P", 15), "tech": ("T", 17), "specs": ("S", 38),
    "backlog": ("B", 27), "impl": ("I", 23), "epic": ("E", 10),
}
ORCH_HEADINGS = (
    "Findings Document Template", "Example Findings",
    "Epic Mode State Write Detail",
)


def _ids(text: str, letter: str) -> list[str]:
    return sorted(set(re.findall(rf"CHECK-{letter}\d\d", text)))


def test_each_mode_file_has_exactly_its_check_ids():
    for mode, (letter, count) in EXPECTED.items():
        text = read(VC_DIR / f"{mode}.md")
        ids = _ids(text, letter)
        assert len(ids) == count, f"{mode}: {len(ids)} ids, expected {count}"
        # contiguous 01..NN, none dropped/renumbered (REQ-R1-05)
        assert ids == [f"CHECK-{letter}{n:02d}" for n in range(1, count + 1)]


def test_no_cross_mode_leakage():
    letters = {m: l for m, (l, _) in EXPECTED.items()}
    for mode, letter in letters.items():
        text = read(VC_DIR / f"{mode}.md")
        others = [l for m, l in letters.items() if m != mode]
        for other in others:
            assert not re.search(rf"CHECK-{other}\d\d", text), \
                f"{mode}.md leaks a CHECK-{other} id"


def test_findings_template_holds_orchestrator_sections_and_modes_do_not():
    ft = read(SKILLS / "forge-verify" / "references" / "findings-template.md")
    for heading in ORCH_HEADINGS:
        assert heading in ft, f"findings-template.md missing '{heading}'"
    for mode in EXPECTED:
        text = read(VC_DIR / f"{mode}.md")
        for heading in ORCH_HEADINGS:
            assert heading not in text, f"{mode}.md leaks orchestrator '{heading}'"


def test_skill_expected_count_table_matches_per_file_totals():
    # REQ-R1-04: the SKILL's Step-3 self-check totals must equal the real counts
    skill = read(SKILLS / "forge-verify" / "SKILL.md")
    for mode, (_, count) in EXPECTED.items():
        assert re.search(rf"{mode}:\s*{count}\b", skill), \
            f"SKILL expected-count table wrong/missing for {mode} (want {count})"
```

The total (130) and the reconciliation of the SKILL's old "tech ~15 → 17" wording
are covered by the two count assertions above.

### 3.2 R2 — `tests/test_prelude_dedup.py`

Asserts the compact form is sentinel-free and each edited body keeps exactly one
full prelude; excluded reference files are untouched (`05-instruction-relocations.md §1`):

```python
from _forge_paths import SKILLS, REFERENCES, read

SENTINEL = '[ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"'
EDITED = {  # skill body -> expected full-prelude count after dedup
    "forge": 1, "forge-0-epic": 1, "forge-bootstrap": 1, "forge-1-prd": 1,
}
EXCLUDED = {  # reference files keep their preludes verbatim (recipe blocks)
    REFERENCES / "shared-conventions.md": 6,
    REFERENCES / "portable-root.md": 2,
    SKILLS / "forge-0-epic" / "references" / "edit-mode.md": 2,
}


def test_edited_bodies_keep_exactly_one_full_prelude():
    for skill, expected in EDITED.items():
        text = read(SKILLS / skill / "SKILL.md")
        assert text.count(SENTINEL) == expected, \
            f"{skill}: {text.count(SENTINEL)} full preludes, expected {expected}"


def test_excluded_reference_files_untouched():
    for path, expected in EXCLUDED.items():
        assert read(path).count(SENTINEL) == expected, \
            f"{path.name}: prelude count drifted (expected {expected})"
```

The **compact form is sentinel-free by construction**: because Rule 5 of
`check-spec-purity.py` fires `VR_PRELUDE_DRIFT` on any sentinel line lacking the
full byte-identical prelude, `bash scripts/validate.sh` (which runs purity) is
the enforcing gate — the pytest above corroborates the full-prelude count.

### 3.3 R3 — `tests/test_process_overview_read.py`

Asserts `process-overview.md` is still cited (ships) but read only under the
conditional branch (`05-instruction-relocations.md §2`):

```python
from _forge_paths import SKILLS, read

def test_process_overview_still_cited_and_conditional():
    body = read(SKILLS / "forge" / "SKILL.md")
    assert "references/process-overview.md" in body, "no longer cited — won't ship"
    # No UNCONDITIONAL setup read: the citation must sit under the
    # "how does the pipeline work / architecture" branch, not a bare setup step.
    idx = body.index("references/process-overview.md")
    window = body[max(0, idx - 400):idx]
    assert any(kw in window.lower() for kw in
               ("how does the pipeline", "architecture", "stage order", "how it works")), \
        "process-overview.md read is not gated behind a how-it-works branch"
```

> Implementation note: this "nearby keyword" assertion is a heuristic. If R3's
> branch marker is a stable anchor (e.g. an HTML comment `<!-- gate:how-it-works
> -->`), assert on that anchor instead for a non-brittle guard — coordinate the
> anchor text with `05-instruction-relocations.md §2`.

### 3.4 R4/R5 — the stdlib schema validator (see §4)

R4 (`tests/test_state_verbs.py`) and R5 (`tests/test_effective_config.py`) share
the hand-rolled validator in §4. R4 covers every verb + the staleness cascade;
R5 validates `effective-config` output against the config schema.

### 3.5 R4 verb coverage — `tests/test_state_verbs.py`

Runs each verb as a subprocess against a temp specs dir and validates the
resulting state (`03-state-verbs.md §12`):

```python
import json
import subprocess
from pathlib import Path
from _forge_paths import SCRIPTS
from _state_schema import validate_state  # §4

FS = str(SCRIPTS / "forge-session.py")


def _run(args: list[str], specs: Path) -> dict:
    r = subprocess.run(
        ["python3", FS, *args, "--specs-dir", str(specs), "--json"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, f"exit {r.returncode}: {r.stderr}"
    return json.loads(r.stdout)


def _seed(tmp_path: Path) -> Path:
    specs = tmp_path / "specs"
    feat = specs / "demo"
    feat.mkdir(parents=True)
    (feat / ".pipeline-state.json").write_text(json.dumps({
        "feature": "demo", "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z", "currentStage": "forge-1-prd",
        "pipelineStatus": "active", "stages": {},
    }))
    return specs


def test_state_enter_then_complete_validates(tmp_path):
    specs = _seed(tmp_path)
    _run(["state-enter", "--feature", "demo", "--stage", "forge-1-prd"], specs)
    _run(["state-artifact", "--feature", "demo", "--stage", "forge-1-prd",
          "--path", "PRD.md"], specs)
    state = _run(["state-complete", "--feature", "demo", "--stage", "forge-1-prd",
                  "--version", "1", "--artifact", "PRD.md"], specs)
    assert validate_state(state) == [], validate_state(state)
    assert state["stages"]["forge-1-prd"]["status"] == "complete"
    assert state["stages"]["forge-1-prd"]["commitHash"] is None  # Commit 1


def test_commit_hash_followup_points_at_artifact_commit(tmp_path):
    specs = _seed(tmp_path)
    _run(["state-enter", "--feature", "demo", "--stage", "forge-1-prd"], specs)
    _run(["state-complete", "--feature", "demo", "--stage", "forge-1-prd",
          "--version", "1", "--artifact", "PRD.md"], specs)
    state = _run(["state-complete", "--feature", "demo", "--stage", "forge-1-prd",
                  "--version", "1", "--artifact", "PRD.md",
                  "--commit-hash", "abc123"], specs)
    assert state["stages"]["forge-1-prd"]["commitHash"] == "abc123"


def test_artifact_append_is_idempotent(tmp_path):
    specs = _seed(tmp_path)
    _run(["state-enter", "--feature", "demo", "--stage", "forge-3-specs"], specs)
    _run(["state-artifact", "--feature", "demo", "--stage", "forge-3-specs",
          "--path", "00-core-definitions.md"], specs)
    state = _run(["state-artifact", "--feature", "demo", "--stage", "forge-3-specs",
                  "--path", "00-core-definitions.md"], specs)
    arts = state["stages"]["forge-3-specs"]["artifacts"]
    assert arts.count("00-core-definitions.md") == 1


def test_decision_and_ecr_and_note_and_branch_validate(tmp_path):
    specs = _seed(tmp_path)
    _run(["state-note", "--feature", "demo", "--note", "hi"], specs)
    _run(["state-branch", "--feature", "demo", "--branch", "forge/demo"], specs)
    _run(["state-decision", "--feature", "demo", "--question", "cache backend?",
          "--raised-by", "forge-1-prd"], specs)
    state = _run(["state-ecr", "--feature", "demo", "--kind", "add-feature",
                  "--target", "sibling", "--rationale", "why", "--raised-by",
                  "forge-2-tech", "--blocks-current", "false"], specs)
    assert validate_state(state) == [], validate_state(state)


def test_staleness_cascade_marks_downstream_stale(tmp_path):
    # a downstream stage built on an OLDER version flips to "stale" on re-complete
    specs = _seed(tmp_path)
    feat = specs / "demo" / ".pipeline-state.json"
    state = json.loads(feat.read_text())
    state["stages"]["forge-2-tech"] = {"status": "complete", "version": 1}
    state["stages"]["forge-3-specs"] = {
        "status": "complete", "version": 1, "basedOnVersions": {"forge-2-tech": 1}}
    feat.write_text(json.dumps(state))
    out = _run(["state-complete", "--feature", "demo", "--stage", "forge-2-tech",
                "--version", "2"], specs)
    assert out["stages"]["forge-3-specs"]["status"] == "stale"


def test_missing_feature_dir_exits_2(tmp_path):
    specs = tmp_path / "specs"; specs.mkdir()
    r = subprocess.run(
        ["python3", FS, "state-note", "--feature", "nope", "--note", "x",
         "--specs-dir", str(specs), "--json"], capture_output=True, text=True)
    assert r.returncode == 2 and r.stdout == ""
```

### 3.6 R6 — `tests/test_runner_contract_split.py`

Asserts every original section survives, the split is disjoint, `agent-selection.md`
is gated, and the loop body stays ≤300 lines (`05-instruction-relocations.md §3`):

```python
from _forge_paths import SKILLS, read

LOOP = SKILLS / "forge-5-loop"
ALWAYS = read(LOOP / "references" / "runner-contract.md")
COND = read(LOOP / "references" / "agent-selection.md")
BODY = read(LOOP / "SKILL.md")

ALWAYS_SECTIONS = [
    "Model selection precedence", "Run mode", "Launch detail",
    "Arm a Monitor", "React to events", "Inform-user output template",
]
COND_SECTIONS = [
    "Agent selection", "Claude-only model-alias guard", "Optional flags catalog",
]


def test_always_sections_stay_in_runner_contract():
    for s in ALWAYS_SECTIONS:
        assert s in ALWAYS, f"runner-contract.md lost always-section '{s}'"


def test_conditional_sections_moved_to_agent_selection():
    for s in COND_SECTIONS:
        assert s in COND, f"agent-selection.md missing '{s}'"
        assert s not in ALWAYS, f"'{s}' still in runner-contract.md (not moved)"


def test_agent_selection_cited_at_capability_gate():
    assert "references/agent-selection.md" in BODY
    idx = BODY.index("references/agent-selection.md")
    window = BODY[max(0, idx - 500):idx + 200]
    assert "agentArgument" in window, \
        "agent-selection.md not cited at the loopRunner.agentArgument gate"


def test_loop_body_within_cap():
    # Rule 4: body <= 300 lines (R6 is a 1:1 citation swap, net zero)
    assert len(BODY.splitlines()) <= 300, "forge-5-loop SKILL exceeds 300 lines"
```

## 4. The stdlib schema validator (REQ-R4-03, C-2)

A hand-rolled structural validator — **no `jsonschema`** — reused by the R4 and
R5 guards. It mirrors `epic-manifest.py`'s `_schema_findings()`: load the JSON
Schema, walk `required` + `properties` + `enum` + `type`, return a list of
human-readable violations (empty = valid). It only needs the draft-07 subset the
two schemas actually use (`type`, `required`, `properties`, `enum`, `items`,
`additionalProperties: false`, `$ref` to `#/definitions/*`).

```python
# tests/_state_schema.py
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_STATE_SCHEMA = json.loads(
    (REPO_ROOT / "references" / "pipeline-state-schema.json").read_text())
_CONFIG_SCHEMA = json.loads(
    (REPO_ROOT / "references" / "forge-config-schema.json").read_text())

_JSON_TYPES = {
    "object": dict, "array": list, "string": str,
    "integer": int, "number": (int, float), "boolean": bool, "null": type(None),
}


def _check(node: dict, schema: dict, schema_root: dict, path: str) -> list[str]:
    """Return a list of schema violations for `node` (empty == valid)."""
    out: list[str] = []
    if "$ref" in schema:
        ref = schema["$ref"].split("/")[-1]
        schema = schema_root["definitions"][ref]
    t = schema.get("type")
    if t and t != "null":
        py = _JSON_TYPES[t] if isinstance(t, str) else tuple(
            _JSON_TYPES[x] for x in t)
        if not isinstance(node, py):
            return [f"{path}: expected {t}, got {type(node).__name__}"]
    if schema.get("enum") is not None and node not in schema["enum"]:
        out.append(f"{path}: {node!r} not in enum {schema['enum']}")
    if isinstance(node, dict):
        for req in schema.get("required", []):
            if req not in node:
                out.append(f"{path}: missing required '{req}'")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for k in node:
                if k not in props:
                    out.append(f"{path}: unexpected key '{k}'")
        for k, v in node.items():
            if k in props:
                out += _check(v, props[k], schema_root, f"{path}.{k}")
    if isinstance(node, list) and "items" in schema:
        for i, item in enumerate(node):
            out += _check(item, schema["items"], schema_root, f"{path}[{i}]")
    return out


def validate_state(state: dict) -> list[str]:
    """Validate a pipeline-state object against pipeline-state-schema.json."""
    return _check(state, _STATE_SCHEMA, _STATE_SCHEMA, "$")


def validate_effective_config(loop_runner: dict) -> list[str]:
    """Validate a resolved loopRunner block against forge-config-schema.json."""
    schema = _CONFIG_SCHEMA["properties"]["loopRunner"]
    return _check(loop_runner, schema, _CONFIG_SCHEMA, "$.loopRunner")
```

> The validator is deliberately minimal — it is a **drift guard**, not a general
> JSON-Schema engine. If a future schema construct is used (e.g. `oneOf`), extend
> `_check` rather than reaching for `jsonschema`. This keeps CI dependency-free
> (C-2) while making REQ-R4-03 test-enforced: the verbs' output is checked
> against the unchanged schema on every run.

### 4.1 R5 — `tests/test_effective_config.py`

```python
import json, subprocess
from pathlib import Path
from _forge_paths import SCRIPTS, REFERENCES
from _state_schema import validate_effective_config

FS = str(SCRIPTS / "forge-session.py")


def test_effective_config_defaults_only_validates(tmp_path):
    cfg = tmp_path / "forge.config.json"
    cfg.write_text(json.dumps({}))  # no loopRunner -> pure defaults
    r = subprocess.run(["python3", FS, "effective-config", "--config", str(cfg),
                        "--json"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    resolved = json.loads(r.stdout)
    assert len(resolved) == 22 and resolved["name"] == "rauf"
    assert validate_effective_config(resolved) == []


def test_user_override_wins_over_default(tmp_path):
    cfg = tmp_path / "forge.config.json"
    cfg.write_text(json.dumps({"loopRunner": {"bin": "myrunner"}}))
    r = subprocess.run(["python3", FS, "effective-config", "--config", str(cfg),
                        "--json"], capture_output=True, text=True)
    resolved = json.loads(r.stdout)
    assert resolved["bin"] == "myrunner"          # override
    assert resolved["name"] == "rauf"             # default preserved


def test_unreadable_schema_exits_2(tmp_path):
    cfg = tmp_path / "forge.config.json"; cfg.write_text("{}")
    r = subprocess.run(["python3", FS, "effective-config", "--config", str(cfg),
                        "--schema", str(tmp_path / "nope.json"), "--json"],
                       capture_output=True, text=True)
    assert r.returncode == 2 and r.stdout == ""
```

## 5. Catch-all citation guard — `tests/test_reference_citations.py` (REQ-MAINT-01)

Two assertions that protect portability regardless of unit:

```python
import re
from _forge_paths import SKILLS, REFERENCES, read

CITE_RE = re.compile(r"references/([A-Za-z0-9_][A-Za-z0-9_./{}*-]*)")
NEW_FILES = [  # every new/moved reference file must be cited by >=1 skill body
    "verification-checklists/prd.md", "verification-checklists/tech.md",
    "verification-checklists/specs.md", "verification-checklists/backlog.md",
    "verification-checklists/impl.md", "verification-checklists/epic.md",
    "findings-template.md", "agent-selection.md", "process-overview.md",
]


def _all_skill_bodies() -> str:
    return "\n".join(read(p) for p in SKILLS.glob("*/SKILL.md"))


def test_every_new_reference_file_is_cited():
    bodies = _all_skill_bodies()
    for rel in NEW_FILES:
        assert rel in bodies, f"{rel} not cited by any skill body — won't ship"


def test_every_invoke_point_citation_names_an_existing_file():
    for skill in SKILLS.glob("*/SKILL.md"):
        body = read(skill)
        for m in CITE_RE.finditer(body):
            rel = m.group(1)
            if any(ch in rel for ch in "{}*"):   # skip templated paths
                continue
            local = skill.parent / "references" / rel
            shared = REFERENCES / rel
            assert local.is_file() or shared.is_file(), \
                f"{skill.parent.name} cites missing references/{rel}"
```

## 6. Portability & fixtures (REQ-PORT-03, SC-5)

After every moved/split file, refresh adapter fixtures and re-run the snapshot:

- **Gemini fixture** — rebuild via the minimal-canon **scratch-build** and
  `command cp -f` procedure (C-3), never a copy of the real adapter. (Memory:
  build `--root minimal-canon` scratch, then `command cp -f` the output into the
  fixture — copying the real adapter re-introduces host-translated tokens.)
- **Snapshot** — `python3 -m pytest tests/test_build_adapters.py` must pass after
  the refresh, proving all five adapters regenerate cleanly with the new files
  present and every citation resolved.

## 7. Measurement (REQ-PERF-01/02, REQ-OBS-01/02, SC-1/SC-2)

The token-saving claim is **evidence-gated**, not asserted from the audit
snapshot. This section is a *procedure*, run at implementation time, not a pytest.

### 7.1 Re-measure the baseline first (REQ-OBS-01)

Before adopting any numeric target, re-measure per-invocation **instruction-token
load** from real dogfood transcripts (the consumption-data-refresh runs are the
evidence source). The LOAD-MAP figures have drifted since b9f0871 and are
**non-binding goals** (OQ-2).

### 7.2 Record the method (REQ-OBS-01)

The recorded, reproducible method: for a targeted invocation, count the
instruction tokens loaded *before the first artifact read* by inspecting the
transcript's system/skill/reference-load spans (the same span the audit measured).
Record the exact transcript ids, the counting script, and the commit so
before/after is reproducible by anyone.

### 7.3 Green/red guard on the always-loaded surface (REQ-PERF-02)

`tests/test_always_loaded_surface.py` — a pass/fail guard, not a judgment:

```python
import re
from _forge_paths import SKILLS, read

FRONTMATTER_CHAR_BUDGET = 9000   # ~1.2k tokens across 13 descriptions; set from
                                 # the re-measured baseline (§7.1), not the audit


def test_frontmatter_description_budget_not_increased():
    total = 0
    for skill in SKILLS.glob("*/SKILL.md"):
        m = re.search(r"^description:\s*(.+)$", read(skill), re.M)
        if m:
            total += len(m.group(1))
    assert total <= FRONTMATTER_CHAR_BUDGET, \
        f"always-loaded frontmatter grew to {total} chars (budget {FRONTMATTER_CHAR_BUDGET})"


def test_session_hook_common_path_stays_silent():
    # the SessionStart hook must emit nothing on the common path (unchanged)
    hook = (SKILLS.parent / "hooks" / "session-start.py")
    if hook.is_file():
        text = hook.read_text(encoding="utf-8")
        assert "print(" not in text or "common" in text.lower(), \
            "SessionStart hook may have gained common-path output — verify"
```

> The char budget and the hook assertion are pinned to the **re-measured**
> baseline (§7.1), not the audit's static ~1.2k figure — set the constant when
> the baseline is measured. This makes REQ-PERF-02 a green/red test rather than a
> review call.

### 7.4 R4 read-frequency scaling (REQ-OBS-02)

Confirm from transcripts how often stages actually performed the per-stage
`pipeline-state-schema.json` read (OQ-1). Scale the **reported** R4 saving to the
observed frequency. This affects *reporting only* — R4 ships regardless, because
the drift-removal benefit (deterministic JSON authoring) justifies it even if the
read was infrequent.

### 7.5 Per-R acceptance (SC-1)

Each shipped R must show a **measured net reduction** on its targeted invocation
vs the re-measured baseline, correctly attributed:

| Unit | Targeted invocation | Measured surface |
|------|---------------------|------------------|
| R1 | a `forge-verifier` leaf subagent | one mode file vs the whole 477-line file |
| R2 | forge / forge-0-epic / forge-bootstrap / forge-1-prd body load | dedup'd body vs original |
| R3 | navigator status/dashboard render | no process-overview.md load |
| R4 | any state-writing stage | no schema read; deterministic verb call |
| R5 | forge-5-loop / forge-4-backlog default resolution | no config-schema read |
| R6 | forge-5-loop without `agentArgument` | runner-contract.md minus 3 sections |

SC-2 (the ~30–35% aggregate) is **directional, not a gate**.

## 8. Coverage targets

- Every new `forge-session.py` verb and `effective-config` has ≥1 happy-path test
  that validates output against the schema, plus ≥1 exit-2 error-path test.
- The staleness cascade has a dedicated test (§3.5).
- Every split/moved reference file has a drift guard asserting its content
  boundary (§3) and is covered by the catch-all citation guard (§5).
- No line-coverage percentage target — these are **structural drift guards**;
  correctness is "the boundary held", not "N% of lines executed".

## Dependencies

- `00-core-definitions.md` (§4 state shapes, §7 CHECK-ID inventory, §3.4 stdlib rule)
- `02-verify-checklist-split.md` (R1 boundaries), `03-state-verbs.md` (R4 verbs
  + cascade), `04-effective-config.md` (R5 output), `05-instruction-relocations.md`
  (R2/R3/R6 boundaries) — this document asserts what those docs promise.
- `01-architecture-layout.md §6` (test surface + fixture procedure).

## Verification

- [ ] `python3 -m pytest tests` passes with all new guards present.
- [ ] `ruff check scripts/ eval/` and `bash scripts/validate.sh` pass locally.
- [ ] Each per-unit guard fails if its unit's boundary is violated (mutation-test
      the guards: remove a CHECK-ID, un-move a section, and confirm red).
- [ ] The stdlib validator flags an intentionally-malformed state/config object.
- [ ] `test_build_adapters.py` snapshot passes after the gemini fixture refresh.
- [ ] The measurement procedure (§7) is recorded with transcript ids + commit,
      and each shipped R shows a net reduction on its targeted invocation.
