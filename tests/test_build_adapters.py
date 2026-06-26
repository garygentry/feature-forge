"""Tests for scripts/build-adapters.py — the canonical→per-agent generator.

Drives the generator as a subprocess over small canon fixture trees (clean +
malformed), following tests/conftest.py conventions (fixture_copy + a local
subprocess runner, mirroring tests/test_check_spec_purity.py). Verifies
determinism/idempotency (REQ-DET-01/03), full regenerate (REQ-DET-02),
self-containment (REQ-GEN-04), the verbatim resolver (REQ-GEN-05), the three
provenance forms (REQ-OUT-01), the Claude argument-hint round-trip (REQ-VND-01),
description byte-fidelity (REQ-FMT-04), per-file drop-with-record
(REQ-FMT-03/REQ-OBS-01), fail-fast (REQ-ROB-01/REQ-OBS-02), and the drift guard
(REQ-CI-01/03). The purity exemption (REQ-PUR-01/02) is tested in
tests/test_check_spec_purity.py. Shared contracts: 00-core-definitions.md.

This module imports NO YAML library at collection time (06 §2 preamble): the
generated output is read as text/bytes and JSON; the only YAML decode (§3.6,
§3.7) is a lazy ``pytest.importorskip("yaml")`` inside the test that needs it.
The generator itself needs the pinned YAML dep, so ``run_build`` is driven by an
interpreter that can import it — preferring the gitignored ``.venv-adapters``
when provisioned, else ``sys.executable`` — and the whole module is skipped if
no available interpreter can import ``yaml`` (so the file stays collectable
without the venv, and actually runs once provisioned).
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GENERATOR = REPO_ROOT / "scripts" / "build-adapters.py"
AGENT_TARGETS = ("claude", "codex", "copilot", "cursor", "gemini")  # 00 §1


def _generator_interpreter() -> str:
    """Return the python interpreter used to run the generator subprocess.

    Prefers the gitignored ``.venv-adapters`` (where the pinned YAML dep is
    provisioned by validate.sh step 6b / item 006), else falls back to the
    interpreter running pytest (06 §2 / item 007 notes).
    """
    venv_py = REPO_ROOT / ".venv-adapters" / "bin" / "python3"
    return str(venv_py) if venv_py.exists() else sys.executable


def _generator_yaml_available() -> bool:
    """Whether the chosen interpreter can import the generator's YAML dep."""
    proc = subprocess.run(
        [_generator_interpreter(), "-c", "import yaml"],
        capture_output=True,
    )
    return proc.returncode == 0


# Keep the module collectable without the venv (06 §2 preamble) while actually
# running once an interpreter that can import yaml is available.
pytestmark = pytest.mark.skipif(
    not _generator_yaml_available(),
    reason="build-adapters.py requires the pinned YAML dep — provision .venv-adapters",
)


def run_build(root: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    """Run build-adapters.py against a fixture tree.

    Args:
        root: A copied canon fixture tree (its `adapters/` is written/checked in place).
        *extra: Additional CLI flags, e.g. ``"--check"``.

    Returns:
        The completed process (returncode + captured stdout/stderr). Exit codes
        follow 00-core-definitions.md §9 (0 ok / 1 canon-error|drift / 2 usage).
    """
    return subprocess.run(
        [_generator_interpreter(), str(GENERATOR), "--root", str(root), *extra],
        capture_output=True,
        text=True,
    )


def hash_tree(root: Path) -> dict[str, str]:
    """Return {posix-relpath: sha256-hex} for every file under ``root``.

    Path-keyed and content-hashed so two trees compare byte-for-byte AND
    structurally (a missing/extra file shows as a key diff). Used to assert
    determinism (REQ-DET-01) and idempotency (REQ-DET-03).
    """
    out: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


# --------------------------------------------------------------------------- #
# 3.1 Determinism & idempotency (REQ-DET-01, REQ-DET-03)
# --------------------------------------------------------------------------- #

# A header carrying any of these would be non-deterministic across runs/hosts.
_TIMESTAMP_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}|\b\d{10,}\b|generated (on|at)\b",
    re.IGNORECASE,
)


def test_build_is_deterministic(fixture_copy):
    """Building the same canon twice yields byte-identical adapters/ trees (REQ-DET-01/03)."""
    root_a = fixture_copy("minimal-canon")
    # A second independent copy (fixture_copy can't be called twice with one name).
    root_b = root_a.parent / "minimal-canon-b"
    shutil.copytree(root_a, root_b)
    assert run_build(root_a).returncode == 0
    assert run_build(root_b).returncode == 0
    assert hash_tree(root_a / "adapters") == hash_tree(root_b / "adapters")


def test_no_timestamp_in_generated_headers(fixture_copy):
    """No generated file carries a timestamp/host/PID (REQ-DET-01, 04 §1 no-timestamp rule)."""
    root = fixture_copy("minimal-canon")
    assert run_build(root).returncode == 0
    for path in sorted((root / "adapters").rglob("*")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        assert not _TIMESTAMP_RE.search(text), f"non-deterministic value in {path}"


def test_matches_committed_snapshot(fixture_copy):
    """A fresh build of `minimal-canon` equals its committed expected snapshot (REQ-DET-01)."""
    root = fixture_copy("minimal-canon")
    assert run_build(root).returncode == 0
    assert hash_tree(root / "adapters") == hash_tree(root / "expected-adapters")


# --------------------------------------------------------------------------- #
# 3.2 Full regenerate / orphan purge (REQ-DET-02)
# --------------------------------------------------------------------------- #


def test_orphan_file_is_purged(fixture_copy):
    """A stale file under adapters/ does not survive a regenerate (REQ-DET-02)."""
    root = fixture_copy("minimal-canon")
    assert run_build(root).returncode == 0  # establish a committed-style tree
    orphan = root / "adapters" / "claude" / "STALE-ORPHAN.md"
    orphan.write_text("stale\n", encoding="utf-8")
    assert run_build(root).returncode == 0
    assert not orphan.exists(), "orphan survived regenerate — publish was not atomic"
    assert (root / "adapters" / "GENERATION-REPORT.md").is_file()


# --------------------------------------------------------------------------- #
# 3.3 Self-containment (REQ-GEN-04, D5)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("agent", AGENT_TARGETS)
def test_bundle_is_self_contained(fixture_copy, agent):
    """Each agent bundle ships its own + shared references/ and the resolver (REQ-GEN-04, D5)."""
    root = fixture_copy("minimal-canon")
    assert run_build(root).returncode == 0
    bundle = root / "adapters" / agent
    assert (bundle / "references" / "shared-conventions.md").is_file()
    assert (bundle / "references" / "stacks" / "python.md").is_file()  # nested → whole-tree copy
    assert (bundle / "scripts" / "forge-root.sh").is_file()
    # Every runtime helper a skill can invoke ships in the bundle (REQ-GEN-04), so a
    # non-Claude install can run helper-backed skills after install.
    for helper in (
        "forge-init.sh",
        "epic-manifest.py",
        "validate-traceability.py",
        "forge-bootstrap.py",
    ):
        assert (bundle / "scripts" / helper).is_file(), helper
    # The neutral cross-agent sentinel forge-root.sh self-locates on (NOT plugin.json).
    sentinel = bundle / ".feature-forge-bundle.json"
    assert sentinel.is_file()
    meta = json.loads(sentinel.read_text())
    assert meta == {
        "name": "feature-forge",
        "version": meta["version"],  # canon-sourced; identity-checked elsewhere
        "agent": agent,
        "generatedBy": "python3 scripts/build-adapters.py",
    }
    # the fixture's `with-refs` skill has an own references/ subdir
    assert (bundle / "skills" / "with-refs" / "references" / "detail.md").is_file()
    # NEGATIVE (V-017): the `noarg` skill has no own references/ — none must be copied.
    assert not (bundle / "skills" / "noarg" / "references").exists()


# --------------------------------------------------------------------------- #
# 3.4 Verbatim resolver (REQ-GEN-05)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("agent", AGENT_TARGETS)
def test_forge_root_is_verbatim(fixture_copy, agent):
    """The copied forge-root.sh is byte-identical to canon, no header (REQ-GEN-05)."""
    root = fixture_copy("minimal-canon")
    assert run_build(root).returncode == 0
    canon = (root / "scripts" / "forge-root.sh").read_bytes()
    copy = (root / "adapters" / agent / "scripts" / "forge-root.sh").read_bytes()
    assert hashlib.sha256(copy).hexdigest() == hashlib.sha256(canon).hexdigest()
    assert b"GENERATED" not in copy  # no header injected (REQ-GEN-05)


# --------------------------------------------------------------------------- #
# 3.5 Provenance (REQ-OUT-01) — three forms + exempt
# --------------------------------------------------------------------------- #


def test_provenance_form_a_in_frontmatter(fixture_copy):
    """Generated files with frontmatter carry the in-block provenance comment (Form A)."""
    root = fixture_copy("minimal-canon")
    assert run_build(root).returncode == 0
    text = (root / "adapters" / "claude" / "skills" / "with-refs" / "SKILL.md").read_text("utf-8")
    lines = text.splitlines()
    assert lines[0] == "---"
    assert lines[1].startswith("# GENERATED — DO NOT EDIT. Source: skills/with-refs/SKILL.md")
    assert "Regenerate: python3 scripts/build-adapters.py" in lines[1]


def test_provenance_form_b_in_report(fixture_copy):
    """GENERATION-REPORT.md (no frontmatter) carries a body-top HTML provenance line (Form B)."""
    root = fixture_copy("minimal-canon")
    assert run_build(root).returncode == 0
    report = (root / "adapters" / "GENERATION-REPORT.md").read_text("utf-8")
    first = report.splitlines()[0]
    assert first.startswith("<!-- GENERATED — DO NOT EDIT.")
    assert "python3 scripts/build-adapters.py" in first
    assert first.endswith("-->")


def test_provenance_form_c_in_gemini_manifest(fixture_copy):
    """gemini-extension.json carries a `_generated` provenance object (Form C)."""
    root = fixture_copy("minimal-canon")
    assert run_build(root).returncode == 0
    manifest = json.loads(
        (root / "adapters" / "gemini" / "gemini-extension.json").read_text("utf-8")
    )
    gen = manifest["_generated"]
    assert gen["regenerate"] == "python3 scripts/build-adapters.py"
    assert gen["source"]  # non-empty canonical source path


# --------------------------------------------------------------------------- #
# 3.6 Claude round-trip (REQ-VND-01)
# --------------------------------------------------------------------------- #


def _frontmatter_value(skill_md: Path, key: str) -> str | None:
    """Return the raw scalar value of a top-level frontmatter `key`, or None.

    A minimal line-scan of the first `---`…`---` block (no YAML import needed —
    see 06 §2 preamble); sufficient for the single-line scalar keys these
    assertions check. The returned value is the raw on-disk text (still quoted);
    use ``_decode_scalar`` when comparing the decoded value (00 §2 / 03 §2.1).
    """
    lines = skill_md.read_text("utf-8").splitlines()
    assert lines[0] == "---"
    for line in lines[1:]:
        if line == "---":
            return None
        if line.startswith(f"{key}:"):
            return line[len(key) + 1 :].strip()
    return None


def _decode_scalar(raw: str | None) -> str | None:
    """Decode a raw frontmatter scalar to its VALUE, discarding on-disk quoting.

    REQ-FMT-04 / REQ-VND-01's contract is that the *decoded* scalar round-trips,
    NOT the quoting style (00 §2, 03 §2.1) — the shared `safe_dump` may legally
    re-quote (canon `"x"` → emitted `x` or `'x'`) while preserving the value. So
    we compare decoded values, never the raw lines. Uses the pinned YAML lib,
    loaded lazily so the module imports no YAML at collection time.
    """
    if raw is None:
        return None
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load(raw)


def test_claude_argument_hint_roundtrip(fixture_copy):
    """Claude restores top-level argument-hint; a hintless skill emits none (REQ-VND-01).

    The decoded scalar is compared (not the raw quoting) because the shared YAML
    dumper legally re-quotes ``[target]`` as ``'[target]'`` (00 §2 / 03 §2.1).
    """
    root = fixture_copy("minimal-canon")
    assert run_build(root).returncode == 0
    with_hint = root / "adapters" / "claude" / "skills" / "with-refs" / "SKILL.md"
    no_hint = root / "adapters" / "claude" / "skills" / "noarg" / "SKILL.md"
    assert _decode_scalar(_frontmatter_value(with_hint, "argument-hint")) == "[target]"
    assert _decode_scalar(_frontmatter_value(no_hint, "argument-hint")) is None


# --------------------------------------------------------------------------- #
# 3.7 Description byte-fidelity (REQ-FMT-04)
# --------------------------------------------------------------------------- #


def test_description_byte_fidelity(fixture_copy):
    """Decoded `description` equals canon for every target with a description field (REQ-FMT-04)."""
    root = fixture_copy("minimal-canon")
    assert run_build(root).returncode == 0
    canon_desc = _decode_scalar(
        _frontmatter_value(root / "skills" / "with-refs" / "SKILL.md", "description")
    )
    assert canon_desc is not None

    # Frontmatter-bearing targets. Native skill filename differs per emitter
    # (03 §3.1/§4.1/§5.1): claude → SKILL.md; codex/copilot → <name>.md;
    # cursor → <name>.mdc (06 §3.7 implementer note: same _frontmatter_value scan).
    for agent, fname in [
        ("claude", "SKILL.md"),
        ("codex", "with-refs.md"),
        ("copilot", "with-refs.md"),
        ("cursor", "with-refs.mdc"),
    ]:
        md = root / "adapters" / agent / "skills" / "with-refs" / fname
        assert _decode_scalar(_frontmatter_value(md, "description")) == canon_desc, agent

    # gemini manifest description (already a decoded JSON string)
    manifest = json.loads(
        (root / "adapters" / "gemini" / "gemini-extension.json").read_text("utf-8")
    )
    assert any(
        s.get("description") == canon_desc for s in manifest.get("skills", [])
    ), "gemini manifest description not byte-identical to canon"


# --------------------------------------------------------------------------- #
# 3.8 Drop-with-record — per-file enumeration (REQ-FMT-03, REQ-OBS-01)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("agent", ["codex", "copilot", "cursor", "gemini"])
def test_drop_with_record_enumerates_per_file(fixture_copy, agent):
    """Sub-agent Claude-only keys are dropped from non-Claude output AND recorded per-file.

    Targets single-agent keys — `effort` (only the researcher) and
    `memory`/`skills` (only the verifier) — so a generator dropping a hard-coded
    {tools, model, maxTurns} list would FAIL (per-file enumeration, V-001).
    """
    root = fixture_copy("minimal-canon")
    assert run_build(root).returncode == 0
    report = (root / "adapters" / "GENERATION-REPORT.md").read_text("utf-8")
    for key in ("effort", "memory", "skills"):
        assert key in report, f"{key} missing from GENERATION-REPORT.md"
        assert agent in report  # the report names the target that dropped it
    # and the keys do NOT leak into the non-Claude agent's emitted artifacts
    agent_files = list((root / "adapters" / agent).rglob("*"))
    bodies = "".join(
        p.read_text("utf-8", errors="ignore") for p in agent_files if p.is_file()
    )
    for token in ("effort:", "memory:", "skills:"):
        assert token not in bodies, f"{token!r} leaked into {agent} output"


def test_claude_retains_subagent_keys(fixture_copy):
    """The Claude target RETAINS sub-agent Claude-only keys (REQ-VND-02), unlike non-Claude."""
    root = fixture_copy("minimal-canon")
    assert run_build(root).returncode == 0
    researcher = root / "adapters" / "claude" / "agents" / "researcher.md"
    text = researcher.read_text("utf-8")
    assert "effort:" in text  # retained for the Claude target
    verifier = (root / "adapters" / "claude" / "agents" / "verifier.md").read_text("utf-8")
    assert "memory:" in verifier
    assert "skills:" in verifier


# --------------------------------------------------------------------------- #
# 3.9 Fail-fast on malformed canon (REQ-ROB-01, REQ-OBS-02)
# --------------------------------------------------------------------------- #


def test_malformed_canon_fails_fast(fixture_copy):
    """Malformed canon aborts with non-zero exit, names the file, writes no partial tree."""
    root = fixture_copy("malformed-canon")
    result = run_build(root)
    assert result.returncode == 1, result.stderr
    assert "skills/broken/SKILL.md" in result.stderr  # names the offending file (REQ-OBS-02)
    assert not (root / "adapters").exists(), "partial adapters/ tree was written"
    # the sibling temp staging dir must also be cleaned up (no adapters.tmp-* leak)
    assert not list(root.glob("adapters.tmp-*")), "staging temp dir leaked after failure"


def test_missing_name_fails_fast(fixture_copy):
    """Canon missing required `name` aborts with MissingNameError, no partial tree (REQ-ROB-01)."""
    root = fixture_copy("malformed-canon-noname")
    result = run_build(root)
    assert result.returncode == 1
    assert "skills/anon/SKILL.md" in result.stderr
    assert not (root / "adapters").exists()
    assert not list(root.glob("adapters.tmp-*")), "staging temp dir leaked after failure"


# --------------------------------------------------------------------------- #
# 3.10 Drift guard (REQ-CI-01, REQ-CI-03)
# --------------------------------------------------------------------------- #


def test_drift_guard_clean_passes(fixture_copy):
    """`--check` on a freshly-built tree exits 0 (no drift) (REQ-CI-01, REQ-DET-03)."""
    root = fixture_copy("minimal-canon")
    assert run_build(root).returncode == 0
    before = hash_tree(root / "adapters")
    result = run_build(root, "--check")
    assert result.returncode == 0, result.stdout + result.stderr
    assert hash_tree(root / "adapters") == before  # --check never mutates adapters/


def test_drift_guard_detects_mutation(fixture_copy):
    """Mutating one committed adapter file makes `--check` fail with remediation (REQ-CI-01/03)."""
    root = fixture_copy("minimal-canon")
    assert run_build(root).returncode == 0
    target = root / "adapters" / "claude" / "skills" / "with-refs" / "SKILL.md"
    target.write_text(target.read_text("utf-8") + "\n<!-- tampered -->\n", encoding="utf-8")
    result = run_build(root, "--check")
    assert result.returncode == 1
    combined = result.stdout + result.stderr
    assert "adapters/ is out of date" in combined
    assert "python3 scripts/build-adapters.py" in combined
