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

- **Subprocess helper invocations use `sys.executable`**, matching `tests/conftest.py`'s
  `run_cli` fixture and 10 of the existing test modules. Reserve a literal `python3` for
  tests that deliberately assert a *shipped command string* (the only two that do are
  `test_build_adapters.py` and `test_forge_bootstrap.py`). Under a venv or a CI image
  where `python3` is not the interpreter running pytest, a hardcoded `python3` tests a
  different interpreter than the suite runs on — this repo has been bitten by that class
  before (`jsonschema` absent in CI).
- **Body-line counts strip frontmatter.** `check-spec-purity.py` Rule 4 measures the
  region after the closing `---`, and gates **both** `MAX_BODY_LINES = 300` (L89) and
  `MAX_BODY_WORDS = 5000` (L169). A raw `wc -l` overcounts by the frontmatter length —
  use the `_body_lines()` helper below.

```python
def _body_lines(text: str) -> list[str]:
    """Body = everything after the closing `---` (check-spec-purity Rule 4)."""
    lines = text.replace("\r\n", "\n").split("\n")
    assert lines and lines[0].strip() == "---", "no frontmatter block"
    close = next(i for i, l in enumerate(lines[1:], 1) if l.strip() == "---")
    body = lines[close + 1:]
    if body and body[-1] == "":
        body = body[:-1]
    return body
```

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

### 3.0 Existing tests R1 must update (not "stay green unchanged")

R1 deletes `skills/forge-verify/references/verification-checklists.md`
(`02-verify-checklist-split.md` §4.4: deletion is total, not left as a stub) **and** drops
the `~` from the Step-2/Step-3 count figures (§7.3). Three committed tests read that exact
path and assert those exact strings, so **R1 lands red on CI unless they are updated in
the same PR.** They are not part of §2's untouched baseline — they require a mechanical
repoint, and doing it inside the R1 PR is what keeps R1 independently revertible
(REQ-DELIV-01).

| Test | Repoint `CHECKLISTS` to | Also change |
|---|---|---|
| `tests/test_lifecycle_artifact_check.py` (L20; reads at L26) | `…/verification-checklists/backlog.md` | drop the `## Implementation Mode Checklist` split terminator in `test_b27_present_and_advisory` (that heading no longer exists in `backlog.md` — slice to end-of-file); L49–50 → `"backlog: 27 checks"` / `"backlog 27"` |
| `tests/test_dev_runtime_smoke.py` (L23; reads at L30) | `…/verification-checklists/impl.md` | in `_runnability()` drop the `## Epic Mode Checklist` terminator (slice `### Runnability` to end-of-file); L68–69 → `"impl: 23 checks"` / `"impl 23"` |
| `tests/test_smoke_command.py` (L25; reads at L57, L65) | `…/verification-checklists/impl.md` | L78–79 → `"impl: 23 checks"` / `"impl 23"` |


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

### 3.2 R2 — not authored (scoped out)

> **R2 is SCOPED OUT (2026-07-28; PRD §3.2).** No `tests/test_prelude_dedup.py` is
> written. A guard authored here would be **red by construction**: it would expect exactly
> one full prelude in `forge`, `forge-0-epic`, `forge-bootstrap` and `forge-1-prd`, whose
> on-disk counts are 5 / 5 / 4 / 2 and will not change. The transform is preserved in
> `05-instruction-relocations.md` §1, and the `r2-prelude` probe in
> `eval/run-compliance-eval.py` remains the gate if R2 is ever revived (re-run it at a
> larger n first — 4/5 on n=5 is a wide interval).
>
> §3.3–§3.6 keep their existing numbering so cross-references from
> `01-architecture-layout.md` §6 and the domain docs stay valid.

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
        [sys.executable, FS, *args, "--specs-dir", str(specs), "--json"],
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


def test_unknown_feature_is_a_usage_error(tmp_path):
    specs = tmp_path / "specs"; specs.mkdir()
    r = subprocess.run(
        [sys.executable, FS, "state-note", "--feature", "nope", "--note", "x",
         "--specs-dir", str(specs), "--json"], capture_output=True, text=True)
    assert r.returncode == 2 and r.stdout == "" and "Error:" in r.stderr  # mechanism, not just the code (03 §3.4)
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


def test_every_skill_body_within_cap():
    """Rule 4 is CI-only (check-spec-purity), so surface it in pytest too.

    Green today: the largest body is forge-5-loop at 298/300 lines, 4,415/5,000
    words. forge-0-epic is 292/300 -- R4 must be strictly in-place there.
    """
    for skill in sorted(SKILLS.glob("*/SKILL.md")):
        body = _body_lines(read(skill))
        n_lines = len(body)
        n_words = sum(len(line.split()) for line in body)
        assert n_lines <= 300, f"{skill.parent.name}: {n_lines} body lines (cap 300)"
        assert n_words <= 5000, f"{skill.parent.name}: {n_words} body words (cap 5000)"
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
    r = subprocess.run([sys.executable, FS, "effective-config", "--config", str(cfg),
                        "--json"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    resolved = json.loads(r.stdout)
    assert len(resolved) == 22 and resolved["name"] == "rauf"
    assert validate_effective_config(resolved) == []


def test_user_override_wins_over_default(tmp_path):
    cfg = tmp_path / "forge.config.json"
    cfg.write_text(json.dumps({"loopRunner": {"bin": "myrunner"}}))
    r = subprocess.run([sys.executable, FS, "effective-config", "--config", str(cfg),
                        "--json"], capture_output=True, text=True)
    resolved = json.loads(r.stdout)
    assert resolved["bin"] == "myrunner"          # override
    assert resolved["name"] == "rauf"             # default preserved


def test_unreadable_schema_exits_2(tmp_path):
    cfg = tmp_path / "forge.config.json"; cfg.write_text("{}")
    r = subprocess.run([sys.executable, FS, "effective-config", "--config", str(cfg),
                        "--schema", str(tmp_path / "nope.json"), "--json"],
                       capture_output=True, text=True)
    assert r.returncode == 2 and r.stdout == "" and "Error:" in r.stderr  # mechanism, not just the code (03 §3.4)
```

## 5. Catch-all citation guard — `tests/test_reference_citations.py` (REQ-MAINT-01)

Two assertions that protect portability regardless of unit:

```python
import re
from _forge_paths import SKILLS, REFERENCES, read

# Anchor on a non-path prefix so `.agents/references/...` and
# `.claude/references/...` (project-level paths in forge-2-tech L61, which
# intentionally do not exist in the bundle) are skipped, and stop at `.md` so a
# sentence-final period is not swallowed into the filename (forge-5-loop L165).
# Verified 2026-07-29 on the unmodified repo: 118 resolvable citations across the
# 13 skill bodies, ZERO misses. (The pre-fix regex produced 3 false positives:
# .agents/ and .claude/ project paths in forge-2-tech L61 x2, and the trailing
# period on forge-5-loop L165.) Green pre-change, so any future red is a real
# regression -- re-run the check before changing this pattern.
CITE_RE = re.compile(r"(?<![./\w-])references/([A-Za-z0-9_][A-Za-z0-9_./{}*-]*?\.md)\b")
# Depends on 02-verify-checklist-split.md §8: the six mode paths are cited
# LITERALLY (one path each), never as a `{mode}` template or a `{prd,tech,...}`
# brace list -- the fan-out regex has no comma in its character class, so a brace
# list yields zero usable paths.
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
  the refresh, proving all **six** adapter targets regenerate cleanly with the new files
  present and every citation resolved: `claude`, `codex`, `copilot`, `cursor`, `gemini`,
  **`pi`** (`scripts/build-adapters.py` `AGENT_TARGETS`, L49).
- **Pi** resolves references through its own extension (`adapter-src/pi/`). Confirm each
  moved/split reference path appears under `adapters/pi/` after regeneration, not only
  under the five agent bundles — a path verified on five hosts and broken on the sixth is
  the #122/#132 failure class REQ-PORT-01/02 exist to prevent.
- **Note** `tests/test_build_adapters.py` carries its own local `AGENT_TARGETS`
  five-tuple (L38); check it when the moved files land.

## 7. Measurement (REQ-PERF-01/02, REQ-OBS-01/02, SC-1/SC-2)

The token-saving claim is **evidence-gated**, not asserted from the audit
snapshot. This section is a *procedure*, run at implementation time, not a pytest.

### 7.1 Baseline of record (REQ-OBS-01, OQ-3 — RESOLVED)

**The re-measurement is done.** `.reference/REMEASURE-0.13.0.md` (2026-07-28, at
plugin 0.13.0 after merging `main` @ `e96b754`) declares itself the baseline of record for
SC-1 and supersedes `LOAD-MAP.md`. Do **not** ask for a fresh measurement before
implementation; compare against that file.

Headline: the canonical surface (`skills/`, `references/`, `agents/`) is byte-identical to
the audit base apart from a rauf pin version string, so every LOAD-MAP figure reproduces.
No recommendation fell below the pinned ~50% stop-rule.

| R | Claim | Re-measured @0.13.0 | % of claim |
|---|---|---|---|
| R1 (per verifier instance) | −4.4k | **−4.8k to −5.9k** | 109–134% |
| R3 | −1.7k | **−1.72k** | 101% |
| R4 | −1.5k | **−1.49k** | 100% |
| R5 | −2.7k | **−2.69k** | 100% |
| R6 | −1.1k | **−1.19k** | 108% |

### 7.2 Method (REQ-OBS-01)

Recorded so before/after comparisons are reproducible: `wc -l` / `wc -w` over the
canonical surface, prose at ~1.3 tokens/word, cross-checked against `chars ÷ 4` (JSON
tokenizes denser than prose; where the two disagree, the 1.3 tok/word figure is the one
compared against a claim, because that is how the claims were computed). Body-line
figures strip frontmatter (§1).

**Evidence location under a loop run** (finding V-007, resolved 2026-07-29). The loop
runner owns the commit message (`[rauf] NNN: <title>`, no body) and the iteration agent
is forbidden from committing or staging at all (project `CLAUDE.md` → "Autonomous Loop
(Rauf)", Completing rule 10), so an iteration agent **cannot** write to it. Any
acceptance criterion phrased "recorded in the commit message" is satisfied by a per-item
section in `{resolvedFeatureDir}/.rauf/progress.md` naming the item id. This applies to
items 002/003/004/006/013/015/016, whose evidence lives at `progress.md` lines 26, 72,
119, 744+769, 691, 832+838, and 1009 respectively.

For future backlogs, the AC template changes from "recorded in the commit message" to
"recorded in `progress.md` under a heading naming the item id (and in the commit message
if the authoring agent owns the commit)".

### 7.3 Green/red guard on the always-loaded surface (REQ-PERF-02)
`tests/test_always_loaded_surface.py` — a pass/fail guard, not a judgment:

```python
import re
from _forge_paths import SKILLS, read

# 13 skill frontmatter descriptions, measured 2026-07-28 @0.13.0
# (.reference/REMEASURE-0.13.0.md §Non-regression baselines). REQ-PERF-02 is a
# NON-INCREASE requirement, so this is an exact ceiling, not a budget. If a
# description must legitimately change, update this constant in the SAME PR with
# the new measurement recorded, so the bump is reviewable.
FRONTMATTER_CHAR_BUDGET = 4688


def test_frontmatter_description_budget_not_increased():
    total = 0
    for skill in SKILLS.glob("*/SKILL.md"):
        m = re.search(r"^description:\s*(.+)$", read(skill), re.M)
        if m:
            total += len(m.group(1))
    assert total <= FRONTMATTER_CHAR_BUDGET, \
        f"always-loaded frontmatter grew to {total} chars (budget {FRONTMATTER_CHAR_BUDGET})"


# hooks/hooks.json wires SessionStart to `bash ${CLAUDE_PLUGIN_ROOT}/scripts/
# session-check.sh`. There is no hooks/session-start.py -- an earlier draft
# guarded that path behind `if hook.is_file()`, which made the whole assertion a
# permanent no-op and satisfied REQ-PERF-02 vacuously. Execute the real hook, and
# assert both directions so silence is proven rather than assumed.
HOOK = REPO_ROOT / "scripts" / "session-check.sh"


def test_session_hook_is_silent_on_the_common_path(tmp_path):
    (tmp_path / "forge.config.json").write_text("{}")
    r = subprocess.run(["bash", str(HOOK)], cwd=tmp_path,
                       capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout == "", r.stdout


def test_session_hook_still_warns_when_config_missing(tmp_path):
    # Control: proves the silence above is real, not a broken invocation.
    feat = tmp_path / "specs" / "demo"
    feat.mkdir(parents=True)
    (feat / ".pipeline-state.json").write_text("{}")
    r = subprocess.run(["bash", str(HOOK)], cwd=tmp_path,
                       capture_output=True, text=True)
    assert r.returncode == 0 and "forge-init" in r.stdout
```

> Both assertions are pinned to the re-measured baseline in
> `.reference/REMEASURE-0.13.0.md` §Non-regression baselines (4,688 chars; hook silent,
> exit 0). Neither may degrade to a skip: a `hook.is_file()` guard or a tautological
> string match turns REQ-PERF-02 back into the review call it explicitly forbids.

### 7.4 R4/R5 read frequency (REQ-OBS-02, OQ-1 — RESOLVED)

**Answered, and it changes what may be claimed.** Across the 188-session
`consumption-data-refresh` dogfood corpus: `pipeline-state-schema.json` was opened
**2×** and `forge-config-schema.json` **1×**, against **12** reads of the
unconditionally-cited `shared-conventions.md` and **103** reads of the state artifact
itself. **The per-stage schema read is not, in practice, per-stage.**

Two limits bound that evidence and must be stated wherever it is used: subagent
sidechains are absent from those transcripts (so R1's read frequency is unmeasurable by
this instrument and stays a static projection), and the denominator is small (4
`stage-exit` invocations) — it is a direction, not a rate.

**Consequence, carried verbatim from `.reference/REMEASURE-0.13.0.md`: do not write an
acceptance criterion asserting a ~1.5k or ~2.7k measured per-stage saving for R4/R5.**
Their realized savings are below the static projection because the read they eliminate
often was not happening. Ship them on **drift-removal** (REQ-R4-02) and **deterministic
default resolution** (REQ-R5-02), and let SC-1's "measured net reduction, correctly
attributed" be satisfied by the static file-load delta on the invocations where the read
does occur.

### 7.5 Per-R acceptance (SC-1)

Each shipped R must show a **measured net reduction** on its targeted invocation
vs the baseline of record (§7.1, `.reference/REMEASURE-0.13.0.md`), correctly attributed.
**R4 and R5 are the exception the evidence forces** — their realized per-stage savings are
below projection because the read they remove often was not happening (§7.4), so their
acceptance is the static delta *plus* the drift-removal benefit, never an asserted
per-stage token figure:

| Unit | Targeted invocation | Measured surface |
|------|---------------------|------------------|
| R1 | a `forge-verifier` leaf subagent | one mode file vs the whole 477-line file |
| R3 | navigator status/dashboard render | no process-overview.md load |
| R4 | any state-writing stage | static file-load delta on invocations where the schema read occurs, **plus** drift-removal (REQ-R4-02) — see §7.4: do **not** claim a ~1.5k per-stage saving |
| R5 | forge-5-loop / forge-4-backlog default resolution | static file-load delta where the config-schema read occurs, **plus** deterministic default resolution (REQ-R5-02) — see §7.4: do **not** claim a ~2.7k per-stage saving |
| R6 | forge-5-loop without `agentArgument` | runner-contract.md minus 3 sections — **but see `05-instruction-relocations.md` §3.2 (finding V-003): the gate is true under the schema default, so this invocation requires a project that has explicitly blanked `agentArgument`. Do **not** claim a per-run saving for a default-config project — there, the file is opened and all 115 lines load.** |

SC-2 (the ~30–35% aggregate) is **directional, not a gate**.

## 8. Coverage targets

- Every new `forge-session.py` verb and `effective-config` has ≥1 happy-path test
  that validates output against the schema, plus ≥1 exit-2 error-path test.
- The staleness cascade has a dedicated test (§3.5).
- Every split/moved reference file has a drift guard asserting its content
  boundary (§3) and is covered by the catch-all citation guard (§5).
- **Every skill body edited by any unit is covered by the ≤300-line / ≤5,000-word guard**
  (§3.6), which surfaces the CI-only `check-spec-purity.py` Rule 4 cap inside pytest
  (C-2). The binding bodies are `forge-5-loop` (2 lines spare) and `forge-0-epic` (8).
- No line-coverage percentage target — these are **structural drift guards**;
  correctness is "the boundary held", not "N% of lines executed".

## 9. Behavior-preservation run (SC-3, REQ-BEHAV-01/02)

Every guard above is a **static** drift assertion over file content. Nothing in the suite
exercises a *running* pipeline — yet SC-3 is the feature's headline criterion ("a full
dogfooded feature run … exhibits the same prompts, gates, guards, and outputs as before").
This section owns that gap; `00-core-definitions.md` §10 is a table of invariants, not a
procedure, and §2 is a list of static guards.

**When.** Once per shipped unit's PR for the units that touch an interactive surface (R4,
R6); once for the batch before release. R1, R3 and R5 may ride the batch run.

**What.** Drive a small real feature through `forge-1-prd` → `forge-6-docs` on a branch,
recording the prompt/gate/output surface at each stage.

**Comparison basis.** The pre-change transcripts in the `consumption-data-refresh` dogfood
corpus (already the evidence source for §7.4). These surfaces MUST be identical:

- `AskUserQuestion` option sets, their order, and the "(recommended)" labelling
- Decision Support wording
- Branch Setup / Branch Reconciliation prompts
- Stage-Entry Guard and Stage-Completion Re-check classification
- The two-commit Git Commit Protocol (never `--amend`), including both L245/L248 failure
  branches — which R4 now routes through `--resumable` (L245) and
  `--preserve-commit-hash` (L248) (`03-state-verbs.md` §6.5)
- Verify gate routing and stage-exit directive handling
- The NEXT-STEPS block and its sentinel

**Reduced substitute**, if a full run is too costly for a given unit — name it explicitly
rather than leaving SC-3 unassigned: **R1** → one real verify fan-out on a large mode,
diffing the findings-document shape; **R6** → one gate-off and one gate-on loop launch,
confirming `agent-selection.md` is read only in the second; **R4** → one authoring stage
plus a deliberately failed Commit 1, confirming the `--resumable` revert path
(status-only: assert `completedAt` is absent and `version` unchanged — a bare
`--status in-progress` would write both).

**Record.** Write the result to `.verification/` alongside the verify findings, naming the
comparison transcripts used. A run with no recorded comparison basis does not satisfy SC-3.

## Dependencies

- `00-core-definitions.md` (§4 state shapes, §7 CHECK-ID inventory, §3.4 stdlib rule)
- `02-verify-checklist-split.md` (R1 boundaries), `03-state-verbs.md` (R4 verbs
  + cascade), `04-effective-config.md` (R5 output), `05-instruction-relocations.md`
  (R3/R6 boundaries) — this document asserts what those docs promise.
- `01-architecture-layout.md §6` (test surface + fixture procedure).

## Verification

- [ ] `python3 -m pytest tests` passes with all new guards present.
- [ ] `ruff check scripts/ eval/` and `bash scripts/validate.sh` pass locally.
- [ ] Each per-unit guard fails if its unit's boundary is violated (mutation-test
      the guards: remove a CHECK-ID, un-move a section, and confirm red).
- [ ] The stdlib validator flags an intentionally-malformed state/config object.
- [ ] `test_build_adapters.py` snapshot passes after the gemini fixture refresh, with all
      **six** adapter targets (incl. `pi`) regenerating cleanly.
- [ ] `python3 scripts/check-spec-purity.py` passes (CI-only gate pytest does not run).
- [ ] The measurement procedure (§7) is recorded with transcript ids + commit,
      and each shipped R shows a net reduction on its targeted invocation.
- [ ] The behavior-preservation run (§9) is recorded for R4 and R6, naming the
      comparison transcripts used (SC-3).
