#!/usr/bin/env python3
"""Generate self-contained, per-agent adapter bundles from spec-pure canon.

This is the ``build-adapters`` generator for the ``forge-agent-adapters-build``
feature. It walks the spec-pure canon (``skills/``, ``agents/``, the
``references/`` trees) and emits a provenance-stamped ``adapters/<agent>/`` tree
for each target agent (claude, codex, copilot, cursor, gemini, pi), plus a
``GENERATION-REPORT.md`` drop-with-record report and a regenerate-and-diff
drift guard wired into ``scripts/validate.sh``.

This module is built up incrementally across backlog items: this foundation
layer defines the shared contracts (target set, record types, emitter protocol +
registry, drop/provenance data models, error hierarchy, fixed key order, and the
CLI exit-code constants). Later items add discovery/parse, the per-agent
emitters, the provenance/self-containment/report passes, and the engine
orchestration to THIS file.

3.10 baseline, Google-style docstrings, full type annotations — matching the
existing ``scripts/epic-manifest.py`` conventions.

Source of truth: ``specs/agent-agnostic/forge-agent-adapters-build/00-core-definitions.md``.
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import yaml


# --------------------------------------------------------------------------- #
# 1. Target Agents (00 §1, REQ-GEN-03, REQ-DET-01)
# --------------------------------------------------------------------------- #

# The v1 target agents (REQ-GEN-03). Order is FIXED (alphabetical) and is the
# emit/report iteration order — never sort at runtime, never reorder (REQ-DET-01).
AGENT_TARGETS: tuple[str, ...] = ("claude", "codex", "copilot", "cursor", "gemini", "pi")


# --------------------------------------------------------------------------- #
# 2. Canonical Record Types (00 §2, REQ-GEN-01)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SkillRecord:
    """One parsed canonical skill (`skills/<name>/SKILL.md`).

    Attributes:
        name: The skill id; MUST equal the containing directory name
            (`skills/<name>/`). Emitters MUST NOT rename it.
        description: Skill description, preserved BYTE-FOR-BYTE from canon
            (REQ-FMT-04). Never reflowed, re-quoted lossily, or trimmed.
        metadata: The optional `metadata` map, or None. For 10 of 11 skills this
            holds `{"argument-hint": "<...>"}` (relocated from Claude's top-level
            key upstream); `forge-init` has no metadata (None). The Claude emitter
            reconstructs top-level `argument-hint` from `metadata["argument-hint"]`
            (REQ-VND-01).
        body: The markdown body — everything after the closing frontmatter `---`.
            Copied verbatim into each target's skill artifact.
        own_refs: Absolute path to this skill's own `references/` subdir if it has
            one, else None. 7 of 11 skills have one (see `01-architecture-layout.md §7`).
        source_path: Repo-relative POSIX path of the SKILL.md (for provenance + errors).
    """

    name: str
    description: str
    metadata: dict[str, object] | None
    body: str
    own_refs: Path | None
    source_path: str


@dataclass(frozen=True)
class AgentRecord:
    """One parsed canonical sub-agent (`agents/<name>.md`).

    Sub-agent frontmatter is NOT a fixed schema (tech-spec §4 / verifier V-001):
    each file carries its own subset of Claude-only keys, discovered per-file. The
    union actually present across the current 3 agents is
    {tools, model, maxTurns, effort, memory, skills} — `effort` only on
    forge-researcher, `memory`+`skills` only on forge-verifier. A future agent that
    adds a new Claude-only key is auto-covered: `claude_keys` carries whatever
    non-{name,description} keys the file actually has (REQ-SCALE-01).

    Attributes:
        name: Sub-agent id; equals `agents/<name>.md` stem.
        description: Preserved BYTE-FOR-BYTE (REQ-FMT-04).
        body: Markdown body after the closing frontmatter `---`.
        claude_keys: Ordered mapping of every parsed frontmatter key EXCEPT
            `name`/`description`, in source order. Drives drop-with-record: each
            emitter enumerates THIS dict, never a hard-coded list, so no key is
            silently dropped (REQ-GEN-06, REQ-FMT-03, REQ-OBS-01).
        source_path: Repo-relative POSIX path (for provenance + errors).
    """

    name: str
    description: str
    body: str
    claude_keys: dict[str, object]
    source_path: str


# --------------------------------------------------------------------------- #
# 4. Fixed Key-Emission Order (00 §4, REQ-DET-01)
# --------------------------------------------------------------------------- #

# Fixed frontmatter key-emission order for determinism (REQ-DET-01). Emitters
# project their native key set onto this order; keys a target doesn't use are
# skipped, never reordered. `description` is emitted verbatim (REQ-FMT-04).
FRONTMATTER_KEY_ORDER: tuple[str, ...] = (
    "name",
    "description",
    "argument-hint",   # claude only (reconstructed, REQ-VND-01)
    "globs",           # cursor .mdc
    "alwaysApply",     # cursor .mdc
    "tools",           # sub-agents, where representable
    "model",
    "maxTurns",
    "turnBudget",      # pi (mapped from maxTurns)
    "effort",
    "thinking",        # pi (mapped from effort)
    "memory",
    "skills",
    "inheritProjectContext",  # pi-only
    "acceptanceRole",         # pi-only
    "completionGuard",        # pi-only
)


# --------------------------------------------------------------------------- #
# 5. Emitter Protocol & Registry (00 §5, REQ-FMT-01, REQ-GEN-06)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class EmittedFile:
    """One file an emitter produces, relative to its agent bundle root.

    Attributes:
        relpath: Path under `adapters/<agent>/` (POSIX). E.g.
            `skills/forge-1-prd/SKILL.md` or `gemini-extension.json`.
        content: Full file bytes as text, provenance header already applied (§7).
            The engine writes this verbatim. Applies to emitter-produced native
            artifacts (Form A/C, §7); the frontmatter-less report (Form B) and the
            verbatim/EXEMPT copies (forge-root.sh, references/) are NOT `EmittedFile`s
            — they are written by the engine's report / self-containment passes
            (`04-provenance-selfcontainment-report.md §1.5`).
        mode: POSIX file mode; 0o644 default, 0o755 for copied scripts
            (forge-root.sh, REQ-GEN-05).
    """

    relpath: str
    content: str
    mode: int = 0o644


@dataclass(frozen=True)
class ManifestEntry:
    """One per-record contribution to a target's whole-bundle manifest.

    Two targets aggregate per-record data into a SINGLE bundle-level manifest
    that is not 1:1 with any one record: Codex's `agents/openai.yaml` (one entry
    per sub-agent) and Gemini's `gemini-extension.json` (one entry per skill).
    An emitter cannot write these manifests itself — it does not see the other
    records — so it returns a `ManifestEntry` per record and the ENGINE collects
    all of them across the per-record loop, then writes the merged manifest once
    after the loop (`02-generator-engine.md §4.1`, serialization in
    `04-provenance-selfcontainment-report.md §1.3`). Emitters whose native format
    has no whole-bundle manifest (claude, cursor) never populate this.

    Attributes:
        name: The record id (skill name or sub-agent name) the entry describes.
        description: The record description, preserved byte-for-byte (REQ-FMT-04).
        extra: Any additional target-specific manifest fields confirmed against the
            agent's native manifest schema (TQ-1) — e.g. an invocation hint. Empty
            for the minimal name+description manifest. Merged into the entry's
            serialized object in `FRONTMATTER_KEY_ORDER`-stable order (§4).
    """

    name: str
    description: str
    extra: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class EmitResult:
    """Everything one emitter produces for one canonical record.

    Attributes:
        files: The native artifact(s) for this record (skill body, etc.).
            References + forge-root.sh copies are added by the engine's
            self-containment pass, not the emitter (`04-...-report.md §2`).
        drops: Constructs that had no native representation in this target
            (REQ-FMT-03), each recorded for the generation report (§6, REQ-OBS-01).
        manifest_entries: Per-record contributions to a target's whole-bundle
            manifest (Codex `agents/openai.yaml`, Gemini `gemini-extension.json`),
            collected and merged by the engine after the per-record loop
            (`02-generator-engine.md §4.1`). Non-empty ONLY for manifest-bearing
            emitters (codex `emit_agent`, gemini `emit_skill`); `()` for everyone
            else. A manifest-bearing emitter therefore returns its body file in
            `files` AND its manifest contribution in `manifest_entries` — it never
            writes the aggregate manifest as a file itself.
    """

    files: tuple[EmittedFile, ...]
    drops: tuple["DropRecord", ...]
    manifest_entries: tuple[ManifestEntry, ...] = ()


class Emitter(Protocol):
    """Translates one canonical record into one target agent's native artifacts.

    One implementation per agent id in AGENT_TARGETS. Emitters are PURE: given the
    same record they return byte-identical EmitResults (REQ-DET-01); they read no
    clock, env, RNG, or filesystem. The engine owns discovery, the references/
    closure, atomic publish, and report assembly — the emitter only maps a record
    to native bytes + drop records.
    """

    agent_id: str  # one of AGENT_TARGETS

    def emit_skill(self, skill: SkillRecord) -> EmitResult:
        """Map a canonical skill to this agent's native skill artifact(s)."""
        ...

    def emit_agent(self, agent: AgentRecord) -> EmitResult:
        """Map a canonical sub-agent to this agent's native agent construct, or
        record every claude_keys entry as dropped where no construct exists
        (REQ-GEN-06)."""
        ...


# --------------------------------------------------------------------------- #
# 6. Drop-With-Record Data Model (00 §6, REQ-FMT-03, REQ-OBS-01)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class DropRecord:
    """One canonical construct that a target agent could not represent.

    Attributes:
        agent: Target agent id (AGENT_TARGETS) that dropped it.
        source: Repo-relative POSIX path of the canonical file it came from.
        construct: Stable identifier of the dropped construct, e.g.
            `sub-agent key 'effort'`, `argument-hint`, `hooks.json`.
        reason: Short human-readable why, e.g. `no Cursor equivalent`.
    """

    agent: str
    source: str
    construct: str
    reason: str


# --------------------------------------------------------------------------- #
# 7. Provenance (00 §7, REQ-OUT-01)
# --------------------------------------------------------------------------- #

# The regenerate command, single-sourced (REQ-OUT-01). Used in every provenance
# form and in the drift-guard remediation message (§9).
REGENERATE_CMD: str = "python3 scripts/build-adapters.py"

# Form A — files WITH a YAML frontmatter block (SKILL.md mirrors, .mdc, agent
# files): a YAML COMMENT as the first line INSIDE the block (`---` stays byte 0
# for strict parsers). `{source}` = canonical source path.
PROVENANCE_FM_COMMENT: str = (
    "# GENERATED — DO NOT EDIT. Source: {source}. Regenerate: " + REGENERATE_CMD
)

# Form B — frontmatter-LESS generated markdown (GENERATION-REPORT.md): an HTML
# comment as the file's first line (verifier V-003).
PROVENANCE_BODY_TOP: str = (
    "<!-- GENERATED — DO NOT EDIT. Regenerate: " + REGENERATE_CMD + " -->"
)


# Form C — strict JSON (gemini-extension.json), no comments possible (OQ-2): a
# documented top-level `_generated` object, serialized with the manifest.
def provenance_json(source: str) -> dict[str, str]:
    """Return the `_generated` provenance object for strict-JSON manifests."""
    return {"source": source, "regenerate": REGENERATE_CMD}


PROVENANCE_JSON_KEY: str = "_generated"

# The gemini-extension.json `version` value — a FIXED, canon-sourced constant, NOT
# read from a package manifest (feature-forge ships no package.json; C-2). It pins
# the manifest's required `version` key to a determinic value (REQ-DET-01) so two
# builds are byte-identical. Bump deliberately if the gemini extension schema (TQ-1)
# requires it; never derive it at runtime. Source of record: this constant.
GEMINI_EXTENSION_VERSION: str = "0.12.9"

# Exempt — `forge-root.sh`: copied BYTE-IDENTICAL (REQ-GEN-05), so NO header is
# injected. Its provenance is documented in GENERATION-REPORT.md instead.

# Runtime helper scripts copied BYTE-IDENTICAL into EVERY adapter bundle so a non-Claude
# install can execute helper-backed skill instructions after install (REQ-GEN-04). The
# resolver (forge-root.sh) leads; the rest are the helpers skills invoke through the bootstrap
# prelude as `$R/scripts/<x>`. Editing skill helper calls? Keep this list in sync.
RUNTIME_HELPERS: tuple[str, ...] = (
    "forge-root.sh",
    "forge-init.sh",
    "epic-manifest.py",
    "forge-session.py",
    "validate-traceability.py",
    "forge-bootstrap.py",
)

# The neutral, cross-agent bundle sentinel filename. forge-root.sh keys its is_root() predicate
# on this file (NOT .claude-plugin/plugin.json), so every per-agent bundle is self-locatable.
BUNDLE_SENTINEL_NAME: str = ".feature-forge-bundle.json"


#: Deterministic version when no plugin manifest is present (e.g. the minimal-canon test
#: fixture carries no .claude-plugin/plugin.json). Real installs always source the live version.
_FALLBACK_BUNDLE_VERSION: str = "0.0.0"


def _bundle_version(repo_root: Path) -> str:
    """Read the canonical plugin version from .claude-plugin/plugin.json (source of record).

    Falls back to a fixed, deterministic version when the manifest is absent or carries no
    ``version`` (the canon-only test fixtures ship no plugin manifest) so the generator stays
    byte-deterministic (REQ-DET-01) instead of crashing on a fixture build.
    """
    try:
        manifest = json.loads(
            (repo_root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        return str(manifest["version"])
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        return _FALLBACK_BUNDLE_VERSION


# --------------------------------------------------------------------------- #
# 8. Error Hierarchy (00 §8, REQ-ROB-01, REQ-OBS-02)
# --------------------------------------------------------------------------- #


class CanonError(Exception):
    """Base: the generator cannot process a canonical input (REQ-ROB-01).

    Carries the offending file so the top-level handler can render
    `<source_path>: <reason>` to stderr (REQ-OBS-02).

    Attributes:
        source_path: Repo-relative POSIX path of the offending canonical file.
        reason: Human-readable cause.
    """

    def __init__(self, source_path: str, reason: str) -> None:
        super().__init__(f"{source_path}: {reason}")
        self.source_path = source_path
        self.reason = reason


class MalformedFrontmatterError(CanonError):
    """Frontmatter block missing/unbalanced `---`, not a YAML mapping, or a
    required field has the wrong type (e.g. non-string `description`, non-mapping
    `metadata`) — `02-generator-engine.md §3` raises it for both the block-structure
    and the field-value-type cases."""


class MissingNameError(CanonError):
    """Required `name` absent, non-string, or != its identity source (skills:
    directory name; agents: file stem) — `02-generator-engine.md §3` `parse_agent`
    raises it for the agent stem mismatch."""


class UnreadableFileError(CanonError):
    """A canonical file could not be read (permissions, encoding, I/O)."""


# --------------------------------------------------------------------------- #
# 9. CLI Exit-Code Contract (00 §9, REQ-GEN-02, REQ-CI-01, REQ-CI-03)
# --------------------------------------------------------------------------- #

# Drift-guard remediation, single-sourced (REQ-CI-03). Printed after the diff on
# `--check` mismatch and by validate.sh step 6b.
REMEDIATION_MESSAGE: str = (
    "adapters/ is out of date — run `" + REGENERATE_CMD + "` and commit the result."
)


# --------------------------------------------------------------------------- #
# Stage 1 — Discovery (02 §1, REQ-GEN-01, REQ-SCALE-01, REQ-DET-01)
# --------------------------------------------------------------------------- #

# Discovery globs, relative to the resolved repo root (REQ-GEN-01). Mirrors
# check-spec-purity.py's surfaces so generator input == purity-gated canon.
SKILLS_GLOB: str = "skills/*/SKILL.md"
AGENTS_GLOB: str = "agents/*.md"
REFERENCES_ROOT: str = "references"  # whole-tree copy (D5); not parsed, see stage 2.


def discover_skill_paths(root: Path) -> list[Path]:
    """Return every canonical SKILL.md, sorted by repo-relative POSIX path.

    Args:
        root: The resolved repo root.

    Returns:
        Absolute paths to ``skills/<name>/SKILL.md``, sorted (LC_ALL=C / byte
        order) for deterministic emit ordering (REQ-DET-01). Currently 11.
    """
    return sorted(
        root.glob(SKILLS_GLOB),
        key=lambda p: p.relative_to(root).as_posix(),
    )


def discover_agent_paths(root: Path) -> list[Path]:
    """Return every canonical sub-agent definition, sorted by relpath.

    Args:
        root: The resolved repo root.

    Returns:
        Absolute paths to ``agents/<name>.md``, sorted (byte order). Currently 3
        (``forge-researcher``, ``forge-spec-writer``, ``forge-verifier``).
    """
    return sorted(
        root.glob(AGENTS_GLOB),
        key=lambda p: p.relative_to(root).as_posix(),
    )


# --------------------------------------------------------------------------- #
# Stage 2 — Parse (02 §3, contract in 00 §3, REQ-GEN-01, REQ-ROB-01, REQ-OBS-02)
# --------------------------------------------------------------------------- #

# Frontmatter delimiter: a line that is exactly "---" (column 0). Per REQ-GEN-01
# (parse) + REQ-ROB-01 (fail-fast): a file without a well-formed open/close pair
# is a MalformedFrontmatterError (reported source_path: reason), not a crash.
_FM_DELIM: str = "---"


def split_frontmatter(text: str, source_path: str) -> tuple[dict[str, object], str]:
    """Split a canonical markdown file into (frontmatter_map, body).

    The frontmatter block is delimited by the first column-0 ``---`` and the next
    column-0 ``---``. The block is ``safe_load``-ed and MUST be a mapping.

    Args:
        text: Full file contents (already newline-normalized to ``\\n``).
        source_path: Repo-relative POSIX path, for error messages (REQ-OBS-02).

    Returns:
        (frontmatter_map, body) where body is everything after the closing ``---``.

    Raises:
        MalformedFrontmatterError: No balanced ``---/---`` pair, or the block is
            not a YAML mapping, or YAML fails to load (REQ-ROB-01).
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != _FM_DELIM:
        raise MalformedFrontmatterError(source_path, "missing opening frontmatter '---'")
    close_idx: int | None = None
    for i in range(1, len(lines)):
        if lines[i].strip() == _FM_DELIM:
            close_idx = i
            break
    if close_idx is None:
        raise MalformedFrontmatterError(source_path, "missing closing frontmatter '---'")

    block = "\n".join(lines[1:close_idx])
    body = "\n".join(lines[close_idx + 1 :])
    try:
        loaded = yaml.safe_load(io.StringIO(block))
    except yaml.YAMLError as exc:  # pinned-dep parse failure
        raise MalformedFrontmatterError(source_path, f"invalid YAML frontmatter: {exc}")
    if not isinstance(loaded, dict):
        raise MalformedFrontmatterError(
            source_path, "frontmatter is not a YAML mapping"
        )
    return loaded, body


def read_canon_text(path: Path, source_path: str) -> str:
    """Read a canonical file as UTF-8 text with normalized ``\\n`` newlines.

    Args:
        path: Absolute path to the canonical file.
        source_path: Repo-relative POSIX path, for error messages.

    Returns:
        File contents with CRLF/CR normalized to ``\\n`` (REQ-DET-01).

    Raises:
        UnreadableFileError: The file cannot be read (permissions, encoding, I/O).
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise UnreadableFileError(source_path, f"cannot read file: {exc}")
    return raw.replace("\r\n", "\n").replace("\r", "\n")


def parse_skill(path: Path, root: Path) -> SkillRecord:
    """Parse one ``skills/<name>/SKILL.md`` into a SkillRecord (00 §2).

    Args:
        path: Absolute path to the SKILL.md.
        root: Resolved repo root (to compute source_path + own_refs).

    Returns:
        A frozen SkillRecord; ``description`` preserved byte-for-byte (REQ-FMT-04).

    Raises:
        UnreadableFileError, MalformedFrontmatterError, MissingNameError: per
            the parse contract (00 §3, §8) — fail-fast (REQ-ROB-01).
    """
    source_path = path.relative_to(root).as_posix()
    fm, body = split_frontmatter(read_canon_text(path, source_path), source_path)

    name = fm.get("name")
    if not isinstance(name, str) or not name:
        raise MissingNameError(source_path, "missing or non-string 'name'")
    dir_name = path.parent.name
    if name != dir_name:
        raise MissingNameError(
            source_path, f"name '{name}' != directory '{dir_name}'"
        )

    description = fm.get("description", "")
    if not isinstance(description, str):
        raise MalformedFrontmatterError(source_path, "'description' is not a string")

    metadata = fm.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        raise MalformedFrontmatterError(source_path, "'metadata' is not a mapping")

    own_refs_dir = path.parent / "references"
    own_refs = own_refs_dir if own_refs_dir.is_dir() else None

    return SkillRecord(
        name=name,
        description=description,
        metadata=metadata,
        body=body,
        own_refs=own_refs,
        source_path=source_path,
    )


def parse_agent(path: Path, root: Path) -> AgentRecord:
    """Parse one ``agents/<name>.md`` into an AgentRecord (00 §2).

    ``claude_keys`` = the parsed frontmatter MINUS ``name``/``description``, in
    source order (Python dict insertion order == YAML document order). NOT a fixed
    schema — whatever Claude-only keys the file carries are captured per-file, so a
    future sub-agent's new key is auto-covered (REQ-SCALE-01, REQ-GEN-06).

    Args:
        path: Absolute path to the agent file.
        root: Resolved repo root.

    Returns:
        A frozen AgentRecord.

    Raises:
        UnreadableFileError, MalformedFrontmatterError, MissingNameError: per the
            parse contract (00 §3, §8).
    """
    source_path = path.relative_to(root).as_posix()
    fm, body = split_frontmatter(read_canon_text(path, source_path), source_path)

    name = fm.get("name")
    if not isinstance(name, str) or not name:
        raise MissingNameError(source_path, "missing or non-string 'name'")
    if name != path.stem:
        raise MissingNameError(source_path, f"name '{name}' != file stem '{path.stem}'")

    description = fm.get("description", "")
    if not isinstance(description, str):
        raise MalformedFrontmatterError(source_path, "'description' is not a string")

    claude_keys: dict[str, object] = {
        k: v for k, v in fm.items() if k not in ("name", "description")
    }

    return AgentRecord(
        name=name,
        description=description,
        body=body,
        claude_keys=claude_keys,
        source_path=source_path,
    )


# --------------------------------------------------------------------------- #
# Cross-cutting emitter helpers (03 §2.1-§2.3, REQ-FMT-02/04, REQ-GEN-06)
# --------------------------------------------------------------------------- #


def render_frontmatter_block(fields: dict[str, Any], source_path: str) -> str:
    """Serialize a frontmatter mapping into a provenance-stamped ``---`` block.

    The keys of ``fields`` MUST already be a subset of FRONTMATTER_KEY_ORDER
    (00 §4) in that fixed order; this helper does NOT reorder (``sort_keys=False``),
    so the caller is responsible for projecting onto the canonical order via
    ``order_fields``. The provenance comment (00 §7, Form A) is emitted as the
    first line INSIDE the block so ``---`` stays byte 0 for strict parsers
    (04-provenance-selfcontainment-report.md §1).

    Args:
        fields: Native frontmatter keys → values, already in FRONTMATTER_KEY_ORDER.
            ``description``'s value is the decoded canonical scalar; the dumper
            preserves it byte-for-byte (REQ-FMT-04).
        source_path: Repo-relative POSIX path of the canonical source, for the
            provenance comment (REQ-OUT-01).

    Returns:
        A complete frontmatter block: ``---\\n# GENERATED…\\n<yaml>---\\n``.
    """
    body = yaml.safe_dump(
        fields,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=4096,
    )
    comment = PROVENANCE_FM_COMMENT.format(source=source_path)
    return f"---\n{comment}\n{body}---\n"


def order_fields(native: dict[str, Any]) -> dict[str, Any]:
    """Project a native field map onto FRONTMATTER_KEY_ORDER (00 §4).

    Drops keys the canonical order does not name and skips keys absent from
    ``native``. A key present in ``native`` but absent from FRONTMATTER_KEY_ORDER
    is a generator bug (emitters MUST only use ordered keys); it is asserted, not
    silently passed.
    """
    out: dict[str, Any] = {}
    for key in FRONTMATTER_KEY_ORDER:
        if key in native:
            out[key] = native[key]
    assert set(native) <= set(FRONTMATTER_KEY_ORDER), (
        f"emitter produced un-ordered keys: {set(native) - set(FRONTMATTER_KEY_ORDER)}"
    )
    return out


def hint_value(skill: SkillRecord) -> str | None:
    """Return the canonical argument-hint scalar, or None if the skill has none.

    None for ``forge-init`` (no metadata) — emitters emit no hint AND record no
    drop for it (there is no construct to drop). For the other 10 skills this is
    the verbatim relocated value (REQ-VND-01 / REQ-FMT-02).
    """
    if skill.metadata is None:
        return None
    hint = skill.metadata.get("argument-hint")
    return hint if isinstance(hint, str) else None


def drop_all_claude_keys(
    agent: AgentRecord, agent_id: str, reason: str
) -> tuple[DropRecord, ...]:
    """Record EVERY claude_keys entry of one sub-agent as dropped.

    For a target that has no native sub-agent construct (REQ-GEN-06 / REQ-FMT-03 /
    REQ-OBS-01). Enumerates ``agent.claude_keys`` (per-file, not hard-coded), so a
    future Claude-only key is auto-covered (REQ-SCALE-01). ``description`` and
    ``name`` are NOT dropped — they are preserved into the body artifact the target
    still receives.
    """
    return tuple(
        DropRecord(
            agent=agent_id,
            source=agent.source_path,
            construct=f"sub-agent key '{key}'",
            reason=reason,
        )
        for key in agent.claude_keys  # source order (00 §3) → deterministic
    )


# --------------------------------------------------------------------------- #
# Host-specific instruction translation (Finding 4, A3) — non-Claude only
# --------------------------------------------------------------------------- #
#
# Canon is authored Claude-first and names Claude-native tools directly
# (`AskUserQuestion`, the Agent/Task tool, `subagent_type=`, `run_in_background`,
# the `Monitor` tool). Those names are correct and rich for the Claude adapter,
# which therefore emits canon VERBATIM (ClaudeEmitter is unchanged — byte-identical
# guarantee). For every NON-Claude adapter we run a deterministic, explicit
# translation pass over the emitted body so the output never instructs a host to
# use a tool it does not have, then append a per-target "Host execution notes"
# overlay (review Option B) that states the host-native way to ask questions,
# dispatch subagents, and run/monitor background work.
#
# The translation is a fixed table of literal substitutions (longest-match-first
# so wrapper phrases like "the `AskUserQuestion` tool" collapse cleanly) plus one
# regex for the parameterized `subagent_type="<name>"` form. No fuzzy matching —
# every replacement is an explicit constant (review: "avoid brittle regex if a
# small set of known tokens can be replaced by constants"). The pass is applied
# only to emitter bodies (skills + sub-agents); the verbatim references closure
# (run_self_containment_pass) is unchanged, and the overlay tells non-Claude hosts
# how to read any residual tool references in those bundled reference files.

# (literal_old, replacement) — applied in order; longest/most-specific first so a
# wrapper phrase is consumed before its bare token. Backticked forms precede bare.
_HOST_TERM_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    # user-input surface → host question mechanism. Article-aware pairs come first
    # (longest-match) so a canon "the" preceding the token is consumed rather than
    # doubled ("the the host's …" — the #79 `an the` class, now for the article).
    # Backticked forms precede bare tokens.
    ("the `AskUserQuestion` tool", "the host's question mechanism"),
    ("the `AskUserQuestion`", "the host's question mechanism"),
    ("the AskUserQuestion", "the host's question mechanism"),
    ("`AskUserQuestion` tool", "the host's question mechanism"),
    ("`AskUserQuestion`", "the host's question mechanism"),
    ("AskUserQuestion", "the host's question mechanism"),
    # The compound "the `Skill`/`Agent` tools" must be consumed BEFORE either the
    # single `Skill` or `Agent` forms below — otherwise the bare `Agent` tools pair
    # eats "`Agent` tools" from inside it and strands a literal `Skill` token.
    ("the `Skill`/`Agent` tools", "the host's skill-invocation and subagent mechanisms"),
    ("`Skill`/`Agent` tools", "host's skill-invocation and subagent mechanisms"),
    # sub-agent dispatch surface → host subagent mechanism. Backticked `Agent`
    # forms (article-aware first, then plural, then bare) precede the un-backticked
    # `Agent`/`Task` tokens so a non-Claude reader never sees a literal `Agent` tool.
    ("the `Agent` tool", "the host's subagent mechanism"),
    ("`Agent` tools", "host's subagent mechanisms"),
    ("`Agent` tool", "host's subagent mechanism"),
    ("the Agent tool", "the host's subagent mechanism"),
    ("the Task tool", "the host's subagent mechanism"),
    ("Agent tool", "host's subagent mechanism"),
    ("Task tool", "host's subagent mechanism"),
    # skill-invocation surface → host skill-invocation mechanism (single-tool forms;
    # the compound above already handled the "`Skill`/`Agent` tools" construct).
    ("the `Skill` tool", "the host's skill-invocation mechanism"),
    ("`Skill` tool", "host's skill-invocation mechanism"),
    # background-execution surface → host background mechanism
    ("`run_in_background: true`", "the host's background-execution mechanism"),
    ("run_in_background: true", "the host's background-execution mechanism"),
    ("`run_in_background`", "the host's background-execution mechanism"),
    ("run_in_background", "the host's background-execution mechanism"),
    # monitoring surface → host monitoring mechanism (backtick-scoped so the bare
    # verb "Monitor the stream" is never rewritten — only the tool reference is).
    # Bold- and article-aware variants first so a preceding "the **" / "The " is not
    # doubled into "the **the …" / "The the …".
    ("the **`Monitor` tool**", "the **host's monitoring mechanism**"),
    ("the `Monitor` tool", "the host's monitoring mechanism"),
    ("`Monitor` tool", "the host's monitoring mechanism"),
    ("The `Monitor`", "The host's monitoring mechanism"),
    ("the `Monitor`", "the host's monitoring mechanism"),
    ("`Monitor`", "the host's monitoring mechanism"),
    ("Monitor tool", "host's monitoring mechanism"),
    # Claude slash-command surface → host-neutral phrasing. The Stage Exit Protocol
    # (references/stage-exit-protocol.md) stamps a literal `/clear` into every stage
    # closing; on a non-Claude host that is not a real command, so degrade it to a
    # plain instruction. Backticked form precedes the bare token (longest-match-first)
    # so `` `/clear` `` collapses cleanly without leaving stray backticks.
    ("`/clear`", "clear your session / start a fresh session"),
    ("/clear", "clear your session / start a fresh session"),
    # Scripted Stage Exit host flag: the canon stamp invokes
    # `forge-session.py stage-exit … --host claude` so the emitted NEXT-STEPS block
    # uses Claude's `/clear` wording. Non-Claude bundles must ask for the
    # host-neutral wording instead — translate the flag value, not just the prose.
    ("--host claude", "--host generic"),
    # Bootstrap-prelude root hint: canon uses Claude's `${CLAUDE_PLUGIN_ROOT:-}` as
    # the prelude's first resolver candidate. Non-Claude hosts set the neutral
    # `${FEATURE_FORGE_ROOT}` instead (forge-root.sh already prefers it), so translate
    # the hint in emitted bodies — otherwise the host-neutrality suite flags a residual
    # `CLAUDE_PLUGIN_ROOT` in the non-Claude prelude. The verbatim forge-root.sh copy
    # keeps its own sanctioned `${CLAUDE_PLUGIN_ROOT}` fallback (it is not body-translated).
    ("${CLAUDE_PLUGIN_ROOT:-}", "${FEATURE_FORGE_ROOT:-}"),
    ("${CLAUDE_PLUGIN_ROOT}", "${FEATURE_FORGE_ROOT}"),
)

# subagent_type="forge-verifier" → "the forge-verifier custom agent"
_SUBAGENT_TYPE_QUOTED = re.compile(r'subagent_type="([^"]+)"')
_SUBAGENT_TYPE_BARE = re.compile(r"subagent_type=(\S+)")

# "Agent call"/"Agent calls" (the Claude Agent-tool dispatch idiom) → "subagent
# call(s)". Whitespace-tolerant so the canon line-wrapped "Agent\ncalls" matches too.
_AGENT_CALL = re.compile(r"\bAgent(\s+)call")

# Per-target overlay appended to each non-Claude SKILL.md body. Claude is absent
# (verbatim). Codex gets a Codex-native note; the other non-Claude targets share a
# neutral note. Overlays deliberately avoid the literal Claude tool tokens so the
# adapter-contract tests (no `AskUserQuestion`/`subagent_type=`/`Monitor` in
# non-Claude skill bodies) hold for the overlay text too.
_HOST_NOTES_CODEX = (
    "## Host execution notes (Codex)\n\n"
    "This skill was authored Claude-first; the body above refers to "
    "\"the host's question mechanism\", \"the host's subagent mechanism\", and "
    "\"the host's background-execution mechanism\". On Codex:\n\n"
    "- **User input:** Codex has no structured question tool — ask the question "
    "directly and wait for the user's reply before proceeding. Never skip a "
    "required question or assume an answer.\n"
    "- **Subagents:** spawn a Codex subagent using the named custom agent under "
    "`.codex/agents/<name>.toml`. Codex spawns a subagent only when explicitly "
    "asked; if the custom agent is unavailable, run that step inline yourself.\n"
    "- **Background / monitoring:** run long-lived runner commands in your shell "
    "session and report progress as it arrives — there is no Claude-style "
    "background or monitoring tool to arm.\n"
)
_HOST_NOTES_NEUTRAL = (
    "## Host execution notes\n\n"
    "This skill was authored Claude-first; the body above refers to "
    "\"the host's question mechanism\", \"the host's subagent mechanism\", and "
    "\"the host's background-execution mechanism\". Use your runtime's equivalent "
    "for each — and if your runtime has no such tool:\n\n"
    "- **User input:** ask the question directly and wait for the answer before "
    "proceeding. Do not skip a required question or assume an answer.\n"
    "- **Subagents:** if your host cannot dispatch the named custom agent, run "
    "that step inline yourself.\n"
    "- **Background / monitoring:** run long-lived commands in the foreground (or "
    "your host's background facility) and report progress as it arrives.\n"
)
_HOST_NOTES_PI = (
    "## Host execution notes (Pi)\n\n"
    "This Pi bundle preserves Claude's `AskUserQuestion` references because it ships "
    "a Pi compatibility extension registering an `AskUserQuestion` tool. On Pi:\n\n"
    "- **User input:** use `AskUserQuestion` for genuine user decisions. It supports "
    "multiple questions, option descriptions, recommended ordering, multi-select, "
    "previews, and free-form Other/custom answers.\n"
    "- **Skill dispatch:** Pi uses `/skill:<name>` commands. If you cannot invoke a "
    "skill directly, print the exact `/skill:<name> ...` command for the user to run.\n"
    "- **Subagents:** this bundle declares its custom agents (`forge-researcher`, "
    "`forge-spec-writer`, `forge-verifier`) as package agents. If a `subagent` tool "
    "is registered, dispatch one with `{ agent: \"forge-verifier\", task: \"...\" }`, "
    "or fan several out concurrently with "
    "`{ tasks: [{ agent: \"forge-spec-writer\", task: \"...\" }, ...] }`. If no "
    "`subagent` tool is available, run that step inline yourself.\n"
    "- **Background / monitoring:** run long-lived commands in the foreground and "
    "report progress as it arrives.\n"
)
_HOST_NOTES: dict[str, str] = {
    "codex": _HOST_NOTES_CODEX,
    "gemini": _HOST_NOTES_NEUTRAL,
    "copilot": _HOST_NOTES_NEUTRAL,
    "cursor": _HOST_NOTES_NEUTRAL,
    "pi": _HOST_NOTES_PI,
}

# Base host-term pairs Pi overrides with its own real command names instead of the
# host-neutral phrasing the generic table uses. Pi has an actual fresh-session command
# (`/new`, verified against Pi's quickstart.md / extensions.md) and its own stage-exit
# host value, so these degrade-to-prose rules are dropped for Pi and replaced below.
_PI_OVERRIDDEN_HOST_TERMS: frozenset[str] = frozenset({"`/clear`", "/clear", "--host claude"})

_PI_HOST_TERM_REPLACEMENTS: tuple[tuple[str, str], ...] = tuple(
    pair for pair in _HOST_TERM_REPLACEMENTS
    if "AskUserQuestion" not in pair[0] and pair[0] not in _PI_OVERRIDDEN_HOST_TERMS
) + (
    # ONLY the slash-command prefix is rewritten. An unanchored `feature-forge:` rule would
    # also mangle diagnostic prose that is not a command — e.g. the install-root failure
    # `echo "feature-forge: cannot locate plugin root"` would become `skill: cannot locate
    # plugin root`, naming a tool that does not exist. Keep this in step with
    # _translate_pi_support_command_strings(), which applies the same single substitution to
    # copied support files.
    ("/feature-forge:", "/skill:"),
    # Pi's fresh-session command is `/new`, not Claude's `/clear`. A bare-token replace
    # keeps any surrounding backticks, so `` `/clear` `` -> `` `/new` `` and a plain
    # /clear -> /new both read as a real Pi command.
    ("/clear", "/new"),
    # The scripted stage-exit stamp runs forge-session.py with a host flag; Pi gets its own
    # `--host pi` wording (the `/new` next-steps block, /skill: commands) instead of the
    # host-neutral `--host generic` output.
    ("--host claude", "--host pi"),
)


def translate_host_terms(text: str, *, agent_id: str | None = None) -> str:
    """Rewrite Claude-native tool names to host-specific safe phrasing.

    Applied to NON-Claude emitter bodies only. Literal substitutions run in a fixed
    order (longest/most-specific first); the parameterized ``subagent_type="<name>``
    form is rewritten by regex. Pi uses a specialized table that preserves
    ``AskUserQuestion`` because the Pi bundle ships a compatibility extension for it.
    """
    text = _SUBAGENT_TYPE_QUOTED.sub(r"the \1 custom agent", text)
    text = _SUBAGENT_TYPE_BARE.sub(r"the \1 custom agent", text)
    text = _AGENT_CALL.sub(r"subagent\1call", text)
    replacements = _PI_HOST_TERM_REPLACEMENTS if agent_id == "pi" else _HOST_TERM_REPLACEMENTS
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def skill_body_for(body: str, agent_id: str) -> str:
    """Body for a skill on ``agent_id``: verbatim for Claude; translated + overlay else."""
    if agent_id == "claude":
        return body
    translated = translate_host_terms(body, agent_id=agent_id)
    overlay = _HOST_NOTES.get(agent_id, _HOST_NOTES_NEUTRAL)
    # Separate the overlay from the body with a horizontal rule; body already ends
    # in a newline (canon invariant), so one blank line then the rule.
    return f"{translated}\n---\n\n{overlay}"


def agent_body_for(body: str, agent_id: str) -> str:
    """Body for a sub-agent on ``agent_id``: verbatim for Claude; translated else.

    No overlay — a sub-agent definition is not an interactive instruction surface;
    the tool-name translation alone keeps its developer_instructions executable.
    """
    return body if agent_id == "claude" else translate_host_terms(body, agent_id=agent_id)

# --------------------------------------------------------------------------- #
# claude emitter (03 §3, REQ-VND-01, REQ-VND-02, REQ-GEN-06) — CONFIRMED
# --------------------------------------------------------------------------- #


class ClaudeEmitter:
    """Emitter for the ``claude`` target (REQ-GEN-03).

    Restores Claude-native skills (top-level argument-hint, REQ-VND-01) and full
    sub-agent frontmatter; retains Claude-only artifacts (REQ-VND-02). D1:
    adapters/claude/ is a parallel packaging copy — plugin.json keeps loading
    skills/ canon (00 §1 / tech-spec D1).
    """

    agent_id = "claude"

    def emit_skill(self, skill: SkillRecord) -> EmitResult:
        """Emit ``skills/<name>/SKILL.md`` with {name, description, argument-hint?}."""
        native: dict[str, Any] = {"name": skill.name, "description": skill.description}
        hint = hint_value(skill)
        if hint is not None:  # REQ-VND-01: reconstruct top-level argument-hint
            native["argument-hint"] = hint
        fields = order_fields(native)
        content = render_frontmatter_block(fields, skill.source_path) + skill.body
        rel = f"skills/{skill.name}/SKILL.md"
        return EmitResult(files=(EmittedFile(relpath=rel, content=content),), drops=())

    def emit_agent(self, agent: AgentRecord) -> EmitResult:
        """Emit ``agents/<name>.md`` with full {name, description, **claude_keys}."""
        native: dict[str, Any] = {"name": agent.name, "description": agent.description}
        native.update(agent.claude_keys)  # all representable for Claude → no drops
        fields = order_fields(native)
        content = render_frontmatter_block(fields, agent.source_path) + agent.body
        rel = f"agents/{agent.name}.md"
        return EmitResult(files=(EmittedFile(relpath=rel, content=content),), drops=())


# --------------------------------------------------------------------------- #
# cursor emitter (03 §6, REQ-FMT-01..03, REQ-GEN-06) — CONFIRMED .mdc schema
# --------------------------------------------------------------------------- #


class CursorEmitter:
    """Emitter for ``cursor``: ``.mdc`` rule files (description, globs, alwaysApply).

    No name field (carried by filename), no hint field (drop-recorded), no
    sub-agent construct (every claude_keys entry drop-recorded). Confirmed format.
    """

    agent_id = "cursor"

    def emit_skill(self, skill: SkillRecord) -> EmitResult:
        """Emit ``skills/<name>/<name>.mdc`` with description/globs/alwaysApply only."""
        native = order_fields({
            "description": skill.description,  # verbatim, REQ-FMT-04
            "globs": [],                       # deterministic default (REQ-DET-01)
            "alwaysApply": False,
        })
        content = render_frontmatter_block(native, skill.source_path) + skill_body_for(
            skill.body, "cursor"
        )
        rel = f"skills/{skill.name}/{skill.name}.mdc"
        drops: tuple[DropRecord, ...] = ()
        if hint_value(skill) is not None:
            drops = (DropRecord("cursor", skill.source_path, "argument-hint",
                                "no Cursor .mdc invocation-hint field"),)
        return EmitResult(files=(EmittedFile(rel, content),), drops=drops)

    def emit_agent(self, agent: AgentRecord) -> EmitResult:
        """Emit a body-only ``agents/<name>.mdc`` and drop-record every claude_keys."""
        native = order_fields({"description": agent.description, "globs": [],
                               "alwaysApply": False})
        rel = f"agents/{agent.name}.mdc"
        content = render_frontmatter_block(native, agent.source_path) + agent_body_for(
            agent.body, "cursor"
        )
        drops = drop_all_claude_keys(agent, "cursor", "no Cursor sub-agent equivalent")
        return EmitResult(files=(EmittedFile(rel, content),), drops=drops)


# --------------------------------------------------------------------------- #
# codex emitter (03 §4, REQ-GEN-06, REQ-FMT-01..03) — TQ-1 (safe defaults)
# --------------------------------------------------------------------------- #
#
# TQ-1 resolution (03 §8). Official docs WERE reachable at implementation
# (context7 `/openai/codex`). The authoritative Codex skill format
# (`skills/src/assets/samples/skill-creator/SKILL.md`) states that `name` and
# `description` are "the only fields Codex reads to determine when the skill gets
# used" — so the documented safe default (emit {name, description}, drop-record
# the invocation hint) is CONFIRMED, not merely assumed. Codex's native agents
# config is a config.toml `[agents.<role>]` table (config_toml.rs `AgentsToml`),
# whose representable keys do not include the canonical sub-agent structural keys
# (tools/model/maxTurns/effort/memory/skills); `_CODEX_AGENT_KEYS` therefore stays
# empty and every claude_keys entry is drop-recorded. Net: the safe-default tree is
# the committed baseline (item 009) regardless of doc reachability (REQ-DET-01).


def _toml_basic_string(value: str) -> str:
    """Serialize ``value`` as a TOML basic string (single line), minimally escaped.

    Escapes backslash and double-quote and the control chars TOML disallows bare
    (tab/newline/CR), so a description with quotes round-trips. Deterministic.
    """
    out = value.replace("\\", "\\\\").replace('"', '\\"')
    out = out.replace("\t", "\\t").replace("\r", "\\r").replace("\n", "\\n")
    return f'"{out}"'


def _toml_multiline_string(value: str) -> str:
    """Serialize ``value`` as a TOML multi-line basic string (``\"\"\" … \"\"\"``).

    Escapes backslashes, then any literal ``\"\"\"`` (so the body cannot close the
    string early). A leading newline after the opening delimiter is TOML-trimmed, so
    we add one for readable output; the trailing newline before the close is real
    content and preserved. Deterministic (REQ-DET-01).
    """
    escaped = value.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    return f'"""\n{escaped}"""'


class CodexEmitter:
    """Emitter for ``codex``: ``skills/<name>/SKILL.md`` + per-agent ``agents/<name>.toml``.

    Skills use Codex's documented directory shape (a ``SKILL.md`` with ``name`` +
    ``description`` frontmatter — the only fields Codex reads). Custom agents are
    standalone TOML files (``name`` / ``description`` / ``developer_instructions``),
    the current Codex custom-agent format; Claude-only structural keys
    (tools/model/maxTurns/effort/memory/skills) have no representable Codex
    custom-agent equivalent in this safe mapping and are drop-recorded so nothing is
    silently lost (REQ-GEN-06 / REQ-OBS-01). No aggregate ``agents/openai.yaml`` is
    emitted — Codex does not load it as custom-agent definitions.
    """

    agent_id = "codex"

    def emit_skill(self, skill: SkillRecord) -> EmitResult:
        """Emit ``skills/<name>/SKILL.md`` with {name, description} + body."""
        native = order_fields({"name": skill.name, "description": skill.description})
        content = render_frontmatter_block(native, skill.source_path) + skill_body_for(
            skill.body, "codex"
        )
        rel = f"skills/{skill.name}/SKILL.md"
        drops: tuple[DropRecord, ...] = ()
        if hint_value(skill) is not None:  # REQ-FMT-02 branch 2 (TQ-1)
            drops = (DropRecord("codex", skill.source_path, "argument-hint",
                                "no confirmed Codex invocation-hint field (TQ-1)"),)
        return EmitResult(files=(EmittedFile(rel, content),), drops=drops)

    def emit_agent(self, agent: AgentRecord) -> EmitResult:
        """Emit a Codex custom-agent ``agents/<name>.toml`` (name/description/instructions).

        The agent body becomes ``developer_instructions`` (REQ-FMT-04). Claude-only
        structural keys are drop-recorded (REQ-GEN-06): they have no representable key
        in this safe Codex custom-agent mapping, and Claude model aliases must never
        leak into Codex config. No ManifestEntry is returned (no ``openai.yaml``).
        """
        dropped = drop_all_claude_keys(
            agent, "codex", "no Codex custom-agent equivalent in safe mapping (TQ-1)"
        )
        header = PROVENANCE_FM_COMMENT.format(source=agent.source_path)
        instructions = _toml_multiline_string(agent_body_for(agent.body, "codex"))
        toml = (
            f"{header}\n"
            f"name = {_toml_basic_string(agent.name)}\n"
            f"description = {_toml_basic_string(agent.description)}\n"
            f"developer_instructions = {instructions}\n"
        )
        rel = f"agents/{agent.name}.toml"
        return EmitResult(files=(EmittedFile(rel, toml),), drops=dropped)


# --------------------------------------------------------------------------- #
# copilot emitter (03 §5, REQ-FMT-01..03, REQ-GEN-06) — TQ-1 (safe defaults)
# --------------------------------------------------------------------------- #
#
# TQ-1 resolution (03 §8): GitHub Copilot exposes no confirmed skill invocation-hint
# field and no native sub-agent construct, so the documented safe default holds —
# {name, description} skill frontmatter, hint drop-recorded, every sub-agent
# claude_keys entry drop-recorded (body-only instruction file).


class CopilotEmitter:
    """Emitter for ``copilot``: skill copy with Copilot frontmatter.

    Hint + sub-agent structural keys are TQ-1-unconfirmed → drop-recorded
    (REQ-FMT-03 / REQ-GEN-06).
    """

    agent_id = "copilot"

    def emit_skill(self, skill: SkillRecord) -> EmitResult:
        """Emit ``skills/<name>/<name>.md`` with {name, description} + body."""
        native = order_fields({"name": skill.name, "description": skill.description})
        content = render_frontmatter_block(native, skill.source_path) + skill_body_for(
            skill.body, "copilot"
        )
        rel = f"skills/{skill.name}/{skill.name}.md"
        drops: tuple[DropRecord, ...] = ()
        if hint_value(skill) is not None:
            drops = (DropRecord("copilot", skill.source_path, "argument-hint",
                                "no known Copilot invocation-hint field (TQ-1)"),)
        return EmitResult(files=(EmittedFile(rel, content),), drops=drops)

    def emit_agent(self, agent: AgentRecord) -> EmitResult:
        """Emit a body-only ``agents/<name>.md`` and drop-record every claude_keys."""
        rel = f"agents/{agent.name}.md"
        content = render_frontmatter_block(
            order_fields({"name": agent.name, "description": agent.description}),
            agent.source_path,
        ) + agent_body_for(agent.body, "copilot")
        drops = drop_all_claude_keys(agent, "copilot", "no Copilot sub-agent construct (TQ-1)")
        return EmitResult(files=(EmittedFile(rel, content),), drops=drops)


# --------------------------------------------------------------------------- #
# Claude -> Pi sub-agent frontmatter mapping (W2)
# --------------------------------------------------------------------------- #
#
# Canon sub-agents are authored Claude-first. `pi-subagents` (0.35.1) has its own
# frontmatter schema, read by `loadAgentsFromDir` (src/agents/agents.ts) — NOT ours.
# Every shape below was confirmed by round-tripping a candidate file through that real
# loader, not from the README. Two shapes bite:
#   - `turnBudget` is `JSON.parse`d, so it must serialize as a single-line JSON *string*
#     (`turnBudget: '{"maxTurns": 40}'`), never a YAML block — a block makes JSON.parse throw.
#   - `tools`/`skills` go through `parseFrontmatterList`, but Pi's line parser only captures
#     block-sequence items indented UNDER the key; PyYAML dedents them to column 0, where the
#     parser drops them. Emit them comma-joined (a single scalar) instead. Block *mappings*
#     (`memory`) are indented by PyYAML and parse fine.

# Canon (Claude) tool name -> Pi builtin tool name(s). Pi's read-only builtins are
# read/grep/find/ls; Glob has no single Pi analogue, so it expands to find+ls. Confirmed
# against pi-subagents' READ_ONLY_BUILTIN_TOOLS (src/runs/shared/completion-guard.ts)
# and `pi --help`.
_PI_TOOL_MAP: dict[str, tuple[str, ...]] = {
    "Read": ("read",),
    "Glob": ("find", "ls"),
    "Grep": ("grep",),
    "Bash": ("bash",),
    "Write": ("write", "edit"),
}

# Canon sub-agent keys the Pi emitter TRANSLATES. Any other claude_keys entry (e.g. `model`)
# is drop-recorded, so a future canon key is auto-covered rather than silently emitted (REQ-GEN-06).
_PI_MAPPED_AGENT_KEYS: frozenset[str] = frozenset(
    {"tools", "maxTurns", "effort", "memory", "skills"}
)


def _canon_tool_tokens(raw: object) -> list[str]:
    """Split a canon ``tools`` value (``"Read, Glob"`` scalar or a YAML list) into tokens."""
    if raw is None:
        return []
    items = raw.split(",") if isinstance(raw, str) else list(raw)  # type: ignore[arg-type]
    return [str(tok).strip() for tok in items if str(tok).strip()]


def _pi_map_tools(tokens: list[str], agent_name: str) -> list[str]:
    """Map canon tool tokens onto Pi builtin names, deduped in first-seen order.

    Raises on an unmapped token rather than silently dropping it: canon is in-repo and adding
    an agent tool is deliberate, so an unknown name is a generator defect a human must map.
    """
    out: list[str] = []
    for tok in tokens:
        mapped = _PI_TOOL_MAP.get(tok)
        if mapped is None:
            raise ValueError(
                f"agent '{agent_name}': canon tool '{tok}' has no Pi builtin mapping "
                f"(add it to _PI_TOOL_MAP)"
            )
        for pi_name in mapped:
            if pi_name not in out:
                out.append(pi_name)
    return out


def _pi_drop_reason(key: str) -> str:
    """Per-key drop reason. `model` is deliberate (D1); anything else is genuinely unmapped."""
    if key == "model":
        return (
            "Claude model aliases (opus/sonnet) are not Pi model ids; pin via "
            "subagents.agentOverrides.<name>.model in Pi settings instead (D1)"
        )
    return "no Pi sub-agent frontmatter equivalent"


def _pi_agent_frontmatter(agent: "AgentRecord") -> tuple[dict[str, Any], tuple["DropRecord", ...]]:
    """Translate one canon sub-agent's frontmatter into Pi's schema (W2).

    Returns the native field map (pre-``order_fields``) and the drops for every canon key that
    has no Pi analogue. `acceptanceRole`/`completionGuard` are DERIVED from the tool allowlist:
    an agent with `Write` is a `writer`; a read-only agent carries `bash` (which pi-subagents
    treats as mutation-capable), so it must set `completionGuard: false` or a correctly
    no-op verify run is judged a failed implementation.
    """
    keys = agent.claude_keys
    native: dict[str, Any] = {
        "name": agent.name,
        "description": translate_host_terms(agent.description, agent_id="pi"),
    }
    tokens = _canon_tool_tokens(keys.get("tools"))
    if tokens:
        native["tools"] = ", ".join(_pi_map_tools(tokens, agent.name))
    if "maxTurns" in keys:
        native["turnBudget"] = json.dumps({"maxTurns": int(keys["maxTurns"])})  # type: ignore[arg-type]
    if "effort" in keys:
        native["thinking"] = str(keys["effort"])
    if "memory" in keys:
        # canon `memory: project` (a scope scalar) -> Pi {scope, path}; the agent name is the
        # durable per-role memory path (pi-subagents namespaces it under agent-memory/).
        native["memory"] = {"scope": str(keys["memory"]), "path": agent.name}
    if "skills" in keys:
        skills = keys["skills"]
        skill_list = list(skills) if isinstance(skills, list) else [str(skills)]
        native["skills"] = ", ".join(str(s) for s in skill_list)
    # Pi-only, load-bearing fields canon has no analogue for. Non-builtin agents default
    # inheritProjectContext=false, so a forge agent would ignore the target repo's AGENTS.md
    # without this.
    is_writer = "Write" in tokens
    native["inheritProjectContext"] = True
    native["acceptanceRole"] = "writer" if is_writer else "read-only"
    if not is_writer:
        native["completionGuard"] = False
    drops = tuple(
        DropRecord("pi", agent.source_path, f"sub-agent key '{key}'", _pi_drop_reason(key))
        for key in keys
        if key not in _PI_MAPPED_AGENT_KEYS
    )
    return native, drops


# --------------------------------------------------------------------------- #
# pi emitter — Pi package with high-fidelity AskUserQuestion compatibility
# --------------------------------------------------------------------------- #


class PiEmitter:
    """Emitter for ``pi``: Pi package root with skills plus AskUserQuestion extension.

    Pi loads SKILL.md folders and TypeScript extensions from package manifest paths.
    Skills preserve ``AskUserQuestion`` and translate Claude-only slash commands to
    Pi's ``/skill:`` surface; the package-level extension registers a compatible
    ``AskUserQuestion`` tool.
    """

    agent_id = "pi"

    def emit_skill(self, skill: SkillRecord) -> EmitResult:
        """Emit ``skills/<name>/SKILL.md`` with {name, description} + Pi-safe body."""
        native = order_fields(
            {
                "name": skill.name,
                "description": translate_host_terms(skill.description, agent_id="pi"),
            }
        )
        content = render_frontmatter_block(native, skill.source_path) + skill_body_for(
            skill.body, "pi"
        )
        rel = f"skills/{skill.name}/SKILL.md"
        drops: tuple[DropRecord, ...] = ()
        if hint_value(skill) is not None:
            drops = (DropRecord("pi", skill.source_path, "argument-hint",
                                "Pi skills have no invocation-hint field"),)
        return EmitResult(files=(EmittedFile(rel, content),), drops=drops)

    def emit_agent(self, agent: AgentRecord) -> EmitResult:
        """Emit a Pi-dispatchable ``agents/<name>.md`` with translated frontmatter (W2).

        The file is declared to Pi through the manifest's ``pi-subagents`` key (see
        ``_write_pi_package_assets``), so a Pi host with a subagent extension installed can
        dispatch it by name. Canon's Claude frontmatter is translated to Pi's schema by
        ``_pi_agent_frontmatter`` (tool allowlist, turn budget, thinking, memory, skills, plus
        the Pi-only acceptance/completion-guard/project-context fields); ``model`` is
        deliberately dropped (D1) along with any other unmapped canon key.
        """
        native, drops = _pi_agent_frontmatter(agent)
        content = render_frontmatter_block(
            order_fields(native), agent.source_path
        ) + agent_body_for(agent.body, "pi")
        rel = f"agents/{agent.name}.md"
        return EmitResult(files=(EmittedFile(rel, content),), drops=drops)


# --------------------------------------------------------------------------- #
# gemini emitter (03 §7, REQ-FMT-01..03, REQ-GEN-06) — TQ-1 (safe defaults)
# --------------------------------------------------------------------------- #
#
# TQ-1 resolution (03 §8). Official docs WERE reachable (context7
# `/google-gemini/gemini-cli`). The Gemini SKILL.md frontmatter is confirmed to be
# {name, description} (skills/builtin/skill-creator/SKILL.md), and the
# gemini-extension.json manifest schema (docs/extensions/reference.md) carries
# name/version/description/mcpServers/contextFileName — it does not define a native
# command invocation-hint field, so the hint stays drop-recorded. The per-skill
# manifest registration shape and `_generated`/`version` serialization are owned by
# the engine (02 §4.1 / 04 §1.3); this emitter only contributes a ManifestEntry per
# skill. Net: documented safe defaults hold; the safe-default tree is the baseline.


class GeminiEmitter:
    """Emitter for ``gemini``: body files + a ``gemini-extension.json`` manifest.

    The manifest (strict JSON → ``_generated`` provenance, 00 §7 Form C) is assembled
    by the engine from each skill's ManifestEntry (02 §4.1, 04 §1.3); any command hint
    field is TQ-1 → drop-recorded.
    """

    agent_id = "gemini"

    def emit_skill(self, skill: SkillRecord) -> EmitResult:
        """Emit ``skills/<name>/<name>.md`` body + one ManifestEntry per skill."""
        rel = f"skills/{skill.name}/{skill.name}.md"
        content = render_frontmatter_block(
            order_fields({"name": skill.name, "description": skill.description}),
            skill.source_path,
        ) + skill_body_for(skill.body, "gemini")
        drops: tuple[DropRecord, ...] = ()
        if hint_value(skill) is not None:
            drops = (DropRecord("gemini", skill.source_path, "argument-hint",
                                "Gemini manifest hint field unconfirmed (TQ-1)"),)
        entry = ManifestEntry(name=skill.name, description=skill.description)
        return EmitResult(
            files=(EmittedFile(rel, content),),
            drops=drops,
            manifest_entries=(entry,),
        )

    def emit_agent(self, agent: AgentRecord) -> EmitResult:
        """Emit a body-only ``agents/<name>.md`` and drop-record every claude_keys."""
        rel = f"agents/{agent.name}.md"
        content = render_frontmatter_block(
            order_fields({"name": agent.name, "description": agent.description}),
            agent.source_path,
        ) + agent_body_for(agent.body, "gemini")
        drops = drop_all_claude_keys(agent, "gemini", "no Gemini sub-agent construct (TQ-1)")
        return EmitResult(files=(EmittedFile(rel, content),), drops=drops)


# --------------------------------------------------------------------------- #
# Self-containment pass (04 §2, REQ-GEN-04, REQ-GEN-05, REQ-SEC-01, REQ-DET-01)
# --------------------------------------------------------------------------- #


def run_self_containment_pass(
    bundle_root: Path,
    repo_root: Path,
    skills: tuple[SkillRecord, ...],
) -> None:
    """Add the reference closure + verbatim forge-root.sh to one agent bundle.

    Runs once per ``adapters/<agent>/`` bundle, AFTER its emitters have written
    native artifacts and BEFORE atomic publish (``02-generator-engine.md §4``).
    Applies to every agent uniformly — NOT per-emitter (``00-core-definitions.md §5``).
    Satisfies REQ-GEN-04 (self-containment) + REQ-GEN-05 (byte-identical resolver).

    Args:
        bundle_root: The agent's bundle dir (e.g. ``<repo>/adapters.tmp-<pid>/claude``).
        repo_root: The resolved feature-forge repo root (canon lives here; read-only, C-3).
        skills: Parsed skills, used to copy each skill's own ``references/`` (§2.2).

    Raises:
        AssertionError: If ``forge-root.sh`` byte-identity fails (REQ-GEN-05) or an
            output path escapes ``bundle_root`` (REQ-SEC-01). Surfaced as a generator
            defect, not a ``CanonError`` (canon is pre-gated pure upstream).
    """
    # (1) Whole-tree shared references/ copy, verbatim (D5, §2.1).
    src_refs = repo_root / "references"
    dst_refs = bundle_root / "references"
    _copytree_verbatim(src_refs, dst_refs, bundle_root)

    # (2) Each skill's own references/ subdir, where present (§2.2, REQ-SCALE-01).
    for skill in skills:
        if skill.own_refs is None:
            continue
        dst_own = bundle_root / "skills" / skill.name / "references"
        _copytree_verbatim(skill.own_refs, dst_own, bundle_root)

    # (2b) Fan out each CITED bundle-root SHARED reference into the skill's own
    #      references/ so a bare `references/X` prose read resolves skill-local on
    #      EVERY install layout — including the non-plugin npm-installer Claude tree
    #      (~/.claude/skills/feature-forge/, no ${CLAUDE_PLUGIN_ROOT}), where the
    #      bundle-root references/ from (1) is unreachable from a skill dir (#122/#132).
    #      Runs AFTER (2) so a skill's own refs are never shadowed. Bundle-root (1) is
    #      kept intact (scripts resolve via `$R`; the plugin path still uses it).
    for skill in skills:
        _fan_out_shared_references(skill, bundle_root, repo_root)

    # (3) Byte-identical runtime-helper copies, NO header (§2.3, REQ-GEN-04/05). forge-root.sh
    #     plus every helper a skill invokes via the bootstrap prelude. `.sh` files are mode 0755
    #     (run via `bash`); `.py` files 0644 (run via `python3 <path>`). Each is asserted
    #     byte-identical to canon so the resolver and helpers behave identically across agents.
    for helper in RUNTIME_HELPERS:
        src_helper = repo_root / "scripts" / helper
        dst_helper = bundle_root / "scripts" / helper
        dst_helper.parent.mkdir(parents=True, exist_ok=True)
        _assert_within(dst_helper, bundle_root)
        shutil.copyfile(src_helper, dst_helper)  # bytes only — never copystat/edit
        dst_helper.chmod(0o755 if helper.endswith(".sh") else 0o644)
        # Unconditional (REQ-GEN-05): the pi slash-command translation runs AFTER this loop,
        # so every agent — pi included — is asserted byte-identical at copy time. The pi pass
        # below then re-verifies that its ONLY divergence is the expected substitution.
        _assert_byte_identical(src_helper, dst_helper)  # REQ-GEN-05 hard assertion

    if bundle_root.name == "pi":
        _translate_pi_support_command_strings(bundle_root, repo_root)

    # (4) Neutral bundle sentinel `.feature-forge-bundle.json` (REQ-GEN-04): the cross-agent root
    #     marker forge-root.sh keys on, making every bundle self-locatable WITHOUT a Claude
    #     plugin manifest. Fixed key order for byte-determinism (REQ-DET-01).
    sentinel = {
        "name": "feature-forge",
        "version": _bundle_version(repo_root),
        "agent": bundle_root.name,
        "generatedBy": REGENERATE_CMD,
    }
    safe_write(
        bundle_root,
        BUNDLE_SENTINEL_NAME,
        json.dumps(sentinel, indent=2, sort_keys=False, ensure_ascii=False) + "\n",
    )

    if bundle_root.name == "pi":
        _write_pi_package_assets(bundle_root)



def _write_pi_package_assets(bundle_root: Path) -> None:
    """Write Pi package manifest and the vendored AskUserQuestion extension tree.

    The extension is a vendored snapshot of ``@juicesharp/rpiv-ask-user-question``
    (see ``adapter-src/pi/UPSTREAM.md``) rather than feature-forge-authored code,
    and ships inside the bundle rather than as a dependency so a Pi install needs
    no second ``pi install`` — the pipeline's interview stages have no fallback
    question mechanism on Pi, so a missing dependency would be a hard stall.
    """
    package = {
        "name": "feature-forge-pi-adapter",
        "private": True,
        "version": "0.0.0",
        "keywords": ["pi-package"],
        "pi": {
            "skills": ["./skills"],
            "extensions": ["./extensions/ask-user-question/index.ts"],
        },
        # Declares the emitted agents/ dir to a Pi subagent extension (the schema is
        # pi-subagents 0.35.1's; it also accepts the equivalent `pi.subagents.agents`).
        # Kept OUT of the `pi` block on purpose: `pi` is core-Pi manifest surface, and
        # this is a third-party contract we do not own, so it stays visibly namespaced.
        # Emitted unconditionally — with no such extension installed the key is inert:
        # nothing reads it, nothing errors. That is what keeps the bundle free of a
        # runtime dependency that could hard-stall the pipeline when it is missing.
        "pi-subagents": {"agents": ["./agents"]},
        "peerDependencies": {
            "@earendil-works/pi-coding-agent": "*",
            "@earendil-works/pi-tui": "*",
            "typebox": "*",
        },
    }
    safe_write(
        bundle_root,
        "package.json",
        json.dumps(package, indent=2, sort_keys=False, ensure_ascii=False) + "\n",
    )
    for relpath, content in adapter_tree(agent="pi", subdir="extensions"):
        safe_write(bundle_root, relpath, content)


# Hand-written, agent-keyed source that FEEDS the generated bundles. Artifacts
# that are real code (rather than canon prose) live at
# ``adapter-src/<agent>/<file>`` so each one can carry its own toolchain and be
# verified before it ships — see the adapter-src loop in scripts/validate.sh,
# which runs every agent dir's ``npm run verify``. Contrast ``adapters/``, which
# is 100% generated and drift-guarded, and so can never hold source.
#
# Resolved from THIS FILE's location, never from ``--root``: this is repo-owned
# tooling, not canon content, so a scratch build against an alternate canon root
# (e.g. tests/fixtures/minimal-canon) must still find it.
ADAPTER_SRC_ROOT = Path(__file__).resolve().parent.parent / "adapter-src"


@functools.lru_cache(maxsize=None)
def adapter_source(agent: str, relpath: str, comment: str) -> str:
    """Return an ``adapter-src`` file's body behind a generated-file header.

    The header is prepended at emit time rather than stored in the source, so the
    checked-in file stays directly compilable by its own toolchain while the
    emitted copy still warns against hand-editing and names its provenance.

    Args:
        agent: Agent id — the ``adapter-src/`` subdirectory to read from.
        relpath: Path of the source file within that agent's directory.
        comment: Line-comment token for the emitted header (e.g. ``"//"``, ``"#"``).

    Returns:
        Header + verbatim source body.

    Raises:
        UnreadableFileError: if the source is missing or unreadable — a broken
            checkout must fail loudly with the standard ``<source_path>: <reason>``
            diagnostic (REQ-OBS-02), never emit a headless or empty artifact.
    """
    rel = f"adapter-src/{agent}/{relpath}"
    try:
        body = (ADAPTER_SRC_ROOT / agent / relpath).read_text(encoding="utf-8")
    except OSError as exc:
        raise UnreadableFileError(
            rel, f"adapter source is missing or unreadable ({exc.strerror or exc})"
        ) from exc
    header = (
        f"{comment} GENERATED — DO NOT EDIT. Source: {rel}\n"
        f"{comment} Regenerate with: python3 scripts/build-adapters.py\n"
    )
    return header + body


# Suffix -> line-comment token for files that CAN carry a provenance header.
# Anything absent is emitted verbatim: JSON has no comment syntax, and a LICENSE
# must stay byte-identical to keep its attribution intact. Those files are not
# left unprotected — adapters/ is covered wholesale by the regen-and-diff drift
# guard (validate.sh 6b), which is what actually catches a hand-edit.
_TREE_HEADER_COMMENTS = {".ts": "//"}


def adapter_tree(agent: str, subdir: str) -> list[tuple[str, str]]:
    """Return every file under ``adapter-src/<agent>/<subdir>/`` ready to emit.

    The single-file :func:`adapter_source` covers an artifact that is one module.
    A vendored third-party package is a tree (Pi's AskUserQuestion extension is
    39 modules plus locales and a LICENSE), so this walks it whole. Source layout
    mirrors emitted layout exactly — ``adapter-src/pi/extensions/...`` becomes
    ``adapters/pi/extensions/...`` — because the extension resolves its own
    bundle root by walking up from ``import.meta.url``; a source tree at a
    different depth would typecheck and test green in-tree while resolving the
    wrong root once emitted.

    Args:
        agent: Agent id — the ``adapter-src/`` subdirectory to read from.
        subdir: Path of the tree within that agent's directory (e.g. ``extensions``).

    Returns:
        ``(relpath, content)`` pairs in sorted POSIX order (REQ-DET-01), relpath
        being relative to the agent dir and therefore directly usable as the
        bundle-relative destination. ``.ts`` files carry the generated header;
        everything else is verbatim.

    Raises:
        UnreadableFileError: if the tree is missing, or holds a file that is not
            valid UTF-8 — a broken or binary-polluted checkout must fail loudly
            (REQ-OBS-02) rather than emit a corrupt bundle.
    """
    root = ADAPTER_SRC_ROOT / agent / subdir
    if not root.is_dir():
        raise UnreadableFileError(
            f"adapter-src/{agent}/{subdir}", "adapter source tree is missing or not a directory"
        )
    emitted: list[tuple[str, str]] = []
    for entry in sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix()):
        # Defensive: a stray `npm install` inside a vendored tree must never
        # balloon the bundle. adapter-src keeps its node_modules one level up.
        if "node_modules" in entry.parts or not entry.is_file():
            continue
        relpath = f"{subdir}/{entry.relative_to(root).as_posix()}"
        rel = f"adapter-src/{agent}/{relpath}"
        try:
            body = entry.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            reason = getattr(exc, "strerror", None) or exc
            raise UnreadableFileError(
                rel, f"adapter source is missing or unreadable ({reason})"
            ) from exc
        comment = _TREE_HEADER_COMMENTS.get(entry.suffix)
        if comment:
            body = (
                f"{comment} GENERATED — DO NOT EDIT. Source: {rel}\n"
                f"{comment} Regenerate with: python3 scripts/build-adapters.py\n"
            ) + body
        emitted.append((relpath, body))
    return emitted


def _copytree_verbatim(src: Path, dst: Path, bundle_root: Path) -> None:
    """Recursively copy ``src`` → ``dst`` byte-for-byte (no header injection, §1.6).

    Walks ``src`` in sorted POSIX order (REQ-DET-01) so any incidental ordering is
    stable. Every destination is asserted within ``bundle_root`` (REQ-SEC-01).
    """
    for entry in sorted(src.rglob("*"), key=lambda p: p.relative_to(src).as_posix()):
        rel = entry.relative_to(src)
        # Executable-spec Python modules (e.g. references/loop-agent-selection.py) are
        # canonical-but-NOT-generated: test-only + doc artifacts imported by pytest, never
        # wired into a runtime an adapter calls (OQ-T1 RESOLVED, 07-testing-strategy.md §2).
        # They are excluded from the adapter bundle so the drift guard does not touch them.
        # Scaffolding under references/templates/ is project-content the bootstrap skill
        # copies verbatim into a NEW user project — NOT an executable-spec module — so a
        # template's own `.py` files (e.g. python/src/{{PKG}}/main.py) MUST ship. Skipping
        # them also left untrackable empty dirs (git cannot track them), so a clean checkout
        # always drifted from a fresh build.
        if "__pycache__" in rel.parts or entry.suffix == ".pyc":
            continue
        if entry.suffix == ".py" and "templates" not in rel.parts:
            continue
        target = dst / rel
        _assert_within(target, bundle_root)
        if entry.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(entry, target)  # verbatim bytes; no stamp, no reflow


def _translate_pi_support_command_strings(bundle_root: Path, repo_root: Path) -> None:
    """Rewrite Claude slash-command strings in Pi support files.

    Skill bodies/frontmatter are translated at emit time, but support files copied for
    self-containment (reference markdown and helper scripts such as forge-session.py)
    can also surface next-step commands to the user. Keep helper logic intact and only
    rewrite the concrete slash-command prefix, leaving diagnostic strings like
    ``feature-forge: cannot locate install root`` unchanged.

    Runtime helpers are re-verified against canon afterwards (REQ-GEN-05): a translated
    helper must differ from its source by EXACTLY this substitution and nothing else, so
    silent corruption of a helper is still caught on pi.
    """
    for path in sorted(bundle_root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in {".json", ".md", ".py", ".sh"}:
            continue
        text = path.read_text(encoding="utf-8", errors="surrogateescape")
        translated = text.replace("/feature-forge:", "/skill:")
        if translated != text:
            path.write_text(translated, encoding="utf-8", errors="surrogateescape")

    for helper in RUNTIME_HELPERS:
        src_helper = repo_root / "scripts" / helper
        dst_helper = bundle_root / "scripts" / helper
        expected = src_helper.read_text(
            encoding="utf-8", errors="surrogateescape"
        ).replace("/feature-forge:", "/skill:")
        actual = dst_helper.read_text(encoding="utf-8", errors="surrogateescape")
        if actual != expected:
            raise SystemExit(
                f"REQ-GEN-05 violation: pi helper {dst_helper} diverges from canon "
                f"{src_helper} by more than the '/feature-forge:' → '/skill:' substitution"
            )


# A prose citation of a bundle reference: `references/<subpath>`. The subpath char
# class allows the `{stack}` placeholder and `*` glob forms skills use for the
# dynamic stacks/ tree (e.g. `references/stacks/{stack}.md`, `references/stacks/*.md`).
_REFERENCE_CITATION_RE: re.Pattern[str] = re.compile(
    r"references/([A-Za-z0-9_][A-Za-z0-9_./{}*-]*)"
)


def _fan_out_shared_references(
    skill: SkillRecord, bundle_root: Path, repo_root: Path
) -> None:
    """Copy each bundle-root SHARED reference a skill CITES into its own references/.

    Canon cites shared bundle-root refs (``references/shared-conventions.md``, …) and
    a skill's OWN refs (``references/prd-template.md``, …) with the same bare
    ``references/X`` prefix, though they live in different dirs. On the plugin layout
    the bootstrap prelude resolves the shared refs via ``${CLAUDE_PLUGIN_ROOT}``; on
    the non-plugin npm-installer Claude layout (``~/.claude/skills/feature-forge/``,
    no ``${CLAUDE_PLUGIN_ROOT}``) a bare ``references/<shared>`` prose read does NOT
    resolve from a skill dir, so the agent degrades to manual reconstruction (#122).
    This fans every CITED bundle-root shared ref into the skill's own ``references/``
    so the bare path resolves skill-local on every layout — WITHOUT touching any skill
    body (the bare paths simply start resolving). The bundle-root ``references/`` tree
    (self-containment step 1) is KEPT; this only ADDS skill-local copies (#132).

    Citation-driven (only what a skill actually reads is fanned) and deterministic
    (sorted iteration, byte-verbatim copy) so the regenerate-and-diff drift guard
    stays byte-stable (REQ-DET-01).

    Args:
        skill: The parsed skill whose body is scanned for ``references/X`` citations.
        bundle_root: The agent bundle dir (self-containment §1/§2 already ran into it).
        repo_root: The resolved repo root; bundle-root shared refs live in ``references/``.
    """
    src_refs = repo_root / "references"
    dst_skill_refs = bundle_root / "skills" / skill.name / "references"
    stacks_fanned = False
    for subpath in sorted(set(_REFERENCE_CITATION_RE.findall(skill.body))):
        head = subpath.split("/", 1)[0]
        # The stacks/ profile is dynamic — the stack is unknown at build time — so a
        # `references/stacks/{stack}.md` / `stacks/*.md` / `stacks/_generic.md`
        # citation fans the WHOLE stacks/ tree once (REQ-SCALE-01).
        if head == "stacks":
            src_stacks = src_refs / "stacks"
            if not stacks_fanned and src_stacks.is_dir():
                _copytree_verbatim(src_stacks, dst_skill_refs / "stacks", bundle_root)
                stacks_fanned = True
            continue
        # Executable-spec modules are test/doc artifacts, never shipped in a bundle
        # (see _copytree_verbatim); no skill cites one, but stay consistent if one does.
        if subpath.endswith(".py"):
            continue
        # A skill-local ref (self-containment step 2) already resolves from the skill
        # dir — never shadow it with a bundle-root file of the same name.
        if skill.own_refs is not None and (skill.own_refs / subpath).is_file():
            continue
        src = src_refs / subpath
        # Only bundle-root SHARED files are fanned. A citation that resolves to
        # NEITHER skill-local NOR bundle-root (e.g. `references/stack-decisions.md`, a
        # PROJECT-level path the skill tells the user to create) is left untouched.
        if not src.is_file():
            continue
        dst = dst_skill_refs / subpath
        _assert_within(dst, bundle_root)  # REQ-SEC-01 — record-derived path guard
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)  # verbatim bytes; no stamp, no reflow


def _assert_within(path: Path, allowed_root: Path) -> Path:
    """Return the resolved ``path``, asserting it is inside ``allowed_root``.

    The single path-traversal guard (REQ-SEC-01). Used both by the
    self-containment pass and by ``safe_write`` (02 §4.2): a record-derived
    path segment (a malicious ``name`` with ``../``, or an absolute relpath) that
    resolves outside the staging/``adapters/`` root is refused with an
    AssertionError before any byte is written — a generator bug, never silently
    allowed.

    Args:
        path: Candidate output path (may be relative or contain ``..``).
        allowed_root: The staging dir (``adapters.tmp-<pid>/``) or a bundle dir
            under it, or post-swap ``adapters/`` under the resolved repo root.

    Returns:
        The resolved absolute path.

    Raises:
        AssertionError: If the resolved path escapes ``allowed_root``.
    """
    resolved = path.resolve()
    root_resolved = allowed_root.resolve()
    assert (
        resolved == root_resolved or root_resolved in resolved.parents
    ), f"refusing to write outside sandbox: {resolved} not under {root_resolved}"
    return resolved


def _assert_byte_identical(src: Path, dst: Path) -> None:
    """Assert ``dst`` is byte-for-byte identical to ``src`` (REQ-GEN-05)."""
    src_hash = hashlib.sha256(src.read_bytes()).hexdigest()
    dst_hash = hashlib.sha256(dst.read_bytes()).hexdigest()
    assert src_hash == dst_hash, (
        f"forge-root.sh copy is not byte-identical to canon "
        f"(src {src_hash[:12]} != dst {dst_hash[:12]}) — REQ-GEN-05 violated"
    )


# --------------------------------------------------------------------------- #
# Manifest serialization (04 §1.3, OQ-2, REQ-OUT-01, REQ-DET-01) — Form C
# --------------------------------------------------------------------------- #


def _publish_manifest(
    root: Path, dest: Path, agent_id: str, entries: tuple[ManifestEntry, ...]
) -> None:
    """Serialize the whole-bundle manifest from collected ManifestEntry-s (V-001).

    Only ``gemini`` (gemini-extension.json) and ``codex`` (agents/openai.yaml) reach
    here; other targets pass no entries (02 §4.1). The serialized object is FIXED-
    ORDER for determinism (REQ-DET-01): ``_generated`` first, then the manifest's own
    keys, then the per-record array built from ``entries`` in their (deterministic)
    accumulation order. ``version`` is the fixed ``GEMINI_EXTENSION_VERSION`` constant
    (00 §7) — never a timestamp.

    Args:
        root: Resolved repo root (unused for serialization; kept for engine symmetry
            with the other publish passes / future schema needs).
        dest: Staging root under which ``<agent_id>/`` bundles live.
        agent_id: The bundle id; only ``gemini``/``codex`` serialize a manifest.
        entries: The per-record ManifestEntry-s collected across the emit loop.
    """
    if agent_id == "gemini":
        manifest: dict[str, object] = {
            PROVENANCE_JSON_KEY: provenance_json("skills/"),
            "name": "feature-forge",
            "version": GEMINI_EXTENSION_VERSION,  # fixed constant, 00 §7 (V-002)
            "skills": [
                {"name": e.name, "description": e.description, **e.extra}
                for e in entries
            ],
        }
        rel = "gemini-extension.json"
        content = json.dumps(manifest, indent=2, sort_keys=False, ensure_ascii=False) + "\n"
        safe_write(dest / agent_id, rel, content)  # 02 §4.2 sandbox guard
    # codex emits no aggregate manifest: custom agents are standalone TOML files
    # (CodexEmitter.emit_agent), which Codex loads directly from agents/<name>.toml.


# --------------------------------------------------------------------------- #
# Generation report (04 §3, REQ-OBS-01, REQ-FMT-03, REQ-DET-01, OQ-3) — Form B
# --------------------------------------------------------------------------- #


def render_generation_report(drops: tuple[DropRecord, ...]) -> str:
    """Render the committed ``adapters/GENERATION-REPORT.md`` body (REQ-OBS-01).

    Carries the Form B body-top provenance line (§1.2) as line 1. Drop rows are
    grouped by agent (AGENT_TARGETS order, ``00-core-definitions.md §1``) and within
    each agent sorted by (source, construct) — the same total order as the global
    (agent, source, construct) sort in ``00-core-definitions.md §6``, so output is
    deterministic (REQ-DET-01).

    Args:
        drops: Every DropRecord produced by every emitter this run.

    Returns:
        The full report text, newline-normalized to ``\\n``, ending in a single ``\\n``.
    """
    lines: list[str] = [PROVENANCE_BODY_TOP, "", "# Adapter Generation Report", ""]
    lines.append(
        "Generated by `" + REGENERATE_CMD + "`. Each row is a canonical construct "
        "that the target agent's format cannot represent and that was therefore "
        "omitted (REQ-FMT-03) and recorded here (REQ-OBS-01)."
    )
    lines.append("")

    # Stable total order over all drops (REQ-DET-01).
    ordered = sorted(drops, key=lambda d: (d.agent, d.source, d.construct))

    for agent in AGENT_TARGETS:                      # fixed iteration order
        agent_drops = [d for d in ordered if d.agent == agent]
        lines.append(f"## {agent}")
        lines.append("")
        if not agent_drops:
            lines.append("_No dropped constructs — every canonical construct is "
                         "representable in this agent's format._")
            lines.append("")
            continue
        lines.append("| Source | Construct | Reason |")
        lines.append("|--------|-----------|--------|")
        for d in agent_drops:
            lines.append(f"| `{d.source}` | `{d.construct}` | {d.reason} |")
        lines.append("")

    lines.extend(_render_verbatim_copies_section())  # §3.3
    return "\n".join(lines) + "\n"


def _render_verbatim_copies_section() -> list[str]:
    """Render the fixed 'copied verbatim' provenance section (§1.4 / §1.6).

    These files carry NO per-file header to preserve byte-identity (REQ-GEN-05) /
    verbatim transport; their provenance is documented here instead, satisfying
    REQ-OUT-01's intent that every generated artifact's provenance is discoverable.
    Fixed text → deterministic (REQ-DET-01).
    """
    return [
        "## Copied verbatim (no provenance header)",
        "",
        "These files are transported byte-for-byte from canon into every "
        "`adapters/<agent>/` bundle and intentionally carry **no** provenance "
        "header (a header would break byte-identity / corrupt parsed files):",
        "",
        "- `scripts/forge-root.sh` → `adapters/<agent>/scripts/forge-root.sh` "
        "(mode 0755, byte-identical — REQ-GEN-05).",
        "- the whole repo-root `references/` tree (all root files plus the "
        "`stacks/` and `templates/specs-hygiene/` subtrees) "
        "→ `adapters/<agent>/references/` (verbatim — REQ-GEN-04 / D5).",
        "- each skill's own `references/` subdir → "
        "`adapters/<agent>/skills/<name>/references/` (verbatim, where present).",
        "- each bundle-root SHARED reference a skill cites (e.g. "
        "`references/shared-conventions.md`, `references/stacks/`) → that skill's "
        "`adapters/<agent>/skills/<name>/references/` (verbatim), so a bare "
        "`references/X` prose read resolves skill-local on every install layout "
        "— including the non-plugin Claude tree with no `${CLAUDE_PLUGIN_ROOT}` (#132).",
        "",
        "Regenerate all adapter output with `" + REGENERATE_CMD + "`.",
        "",
    ]


# --------------------------------------------------------------------------- #
# Emitter registry (02 §2, REQ-GEN-03, REQ-DET-01)
# --------------------------------------------------------------------------- #

# Registry literal: agent id -> emitter factory. Keys MUST equal AGENT_TARGETS
# exactly (asserted in build_emitters). One entry per target (REQ-GEN-03); adding
# a sixth agent is one new entry + one AGENT_TARGETS element, never a structural
# change (00 §1).
AGENT_TARGETS_REGISTRY: dict[str, type] = {
    "claude": ClaudeEmitter,
    "codex": CodexEmitter,
    "copilot": CopilotEmitter,
    "cursor": CursorEmitter,
    "gemini": GeminiEmitter,
    "pi": PiEmitter,
}


def build_emitters() -> dict[str, Emitter]:
    """Instantiate one emitter per target, validating registry coverage.

    Returns:
        Mapping agent id -> Emitter, iterated in AGENT_TARGETS order (00 §1).

    Raises:
        AssertionError: If the registry keys do not exactly equal AGENT_TARGETS
            (a generator bug, not a CanonError — fail loud).
    """
    assert set(AGENT_TARGETS_REGISTRY) == set(AGENT_TARGETS), (
        "AGENT_TARGETS_REGISTRY must cover exactly AGENT_TARGETS (00 §1)"
    )
    return {agent_id: AGENT_TARGETS_REGISTRY[agent_id]() for agent_id in AGENT_TARGETS}


# --------------------------------------------------------------------------- #
# Path-safety sandbox — safe_write (02 §4.2, REQ-SEC-01, REQ-DET-01)
# --------------------------------------------------------------------------- #


def safe_write(
    allowed_root: Path, relpath: str, content: str, mode: int = 0o644
) -> None:
    """Write ``content`` to ``allowed_root/relpath``, sandbox-checked (REQ-SEC-01).

    Newlines are already normalized to ``\\n`` by the emitters; this writes bytes
    verbatim (``newline=""`` → no platform CRLF translation) for cross-OS
    byte-identity (REQ-DET-01).

    Args:
        allowed_root: The staging/bundle dir for the current build.
        relpath: POSIX-relative path under ``allowed_root`` (EmittedFile.relpath).
        content: Full file text (provenance header already applied, 04 §1).
        mode: POSIX mode; 0o644 default, 0o755 for copied scripts (00 §5).

    Raises:
        AssertionError: If the target escapes the sandbox (``_assert_within``).
    """
    target = _assert_within(allowed_root / relpath, allowed_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    # newline="" → write content's `\n` verbatim, never translate to CRLF.
    with open(target, "w", encoding="utf-8", newline="") as fh:
        fh.write(content)
    os.chmod(target, mode)


# --------------------------------------------------------------------------- #
# Atomic publish & pipeline (02 §4.1/§4.3, REQ-DET-02/03, REQ-ROB-01)
# --------------------------------------------------------------------------- #

ADAPTERS_DIRNAME: str = "adapters"


def _new_staging_dir(root: Path) -> Path:
    """Return a fresh sibling staging dir ``adapters.tmp-<pid>/``.

    Matches the ``.gitignore`` glob (01 §2.1). Removed/replaced by the caller.
    """
    staging = root / f"{ADAPTERS_DIRNAME}.tmp-{os.getpid()}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    return staging


def _publish_emit_result(
    root: Path, dest: Path, agent_id: str, result: EmitResult
) -> None:
    """Write one EmitResult's native files into the agent bundle (REQ-SEC-01).

    Each EmittedFile is written under ``dest/<agent_id>/`` via ``safe_write``, so
    every byte goes through the path-traversal guard (02 §4.2). References, the
    forge-root.sh copy, and manifests are NOT written here (04 §2 / §1.3).
    """
    bundle_root = dest / agent_id
    for emitted in result.files:
        safe_write(bundle_root, emitted.relpath, emitted.content, emitted.mode)


def build_tree(root: Path, dest: Path) -> tuple[EmitResult, ...]:
    """Build the COMPLETE adapters tree into ``dest`` (a fresh empty dir).

    Stages 1–3: discover (§1) → parse (§3) → per-agent emit (§2). After each
    agent's emit loop the merged whole-bundle manifest is written (04 §1.3) and
    the references-closure + verbatim forge-root.sh are added (04 §2). The
    GENERATION-REPORT.md is assembled from all DropRecords (04 §3) after every
    agent is built.

    Args:
        root: Resolved repo root (canon source).
        dest: A fresh staging dir to populate (§4.2). MUST be empty/new;
            ``build_tree`` never writes outside it (REQ-SEC-01).

    Returns:
        The tuple of EmitResults (for the report assembly).

    Raises:
        CanonError: Any unprocessable canon (00 §8) — aborts before publish so no
            partial ``adapters/`` is ever produced (REQ-ROB-01).
    """
    emitters = build_emitters()  # §2

    skills = [parse_skill(p, root) for p in discover_skill_paths(root)]  # §1, §3
    agents = [parse_agent(p, root) for p in discover_agent_paths(root)]  # §1, §3

    results: list[EmitResult] = []
    all_drops: list[DropRecord] = []
    # AGENT_TARGETS order (00 §1) — deterministic emit/write order (REQ-DET-01).
    for agent_id, emitter in emitters.items():
        manifest_entries: list[ManifestEntry] = []
        for skill in skills:
            result = emitter.emit_skill(skill)
            _publish_emit_result(root, dest, agent_id, result)
            manifest_entries.extend(result.manifest_entries)
            all_drops.extend(result.drops)
            results.append(result)
        for agent in agents:
            result = emitter.emit_agent(agent)
            _publish_emit_result(root, dest, agent_id, result)
            manifest_entries.extend(result.manifest_entries)
            all_drops.extend(result.drops)
            results.append(result)
        # Merged whole-bundle manifest, if this target emits one (codex/gemini).
        if manifest_entries:
            _publish_manifest(root, dest, agent_id, tuple(manifest_entries))  # 04 §1.3
        # References closure + verbatim forge-root.sh copy for this bundle (04 §2).
        run_self_containment_pass(dest / agent_id, root, tuple(skills))

    # GENERATION-REPORT.md from all DropRecords (04 §3).
    report = render_generation_report(tuple(all_drops))
    safe_write(dest, "GENERATION-REPORT.md", report)

    return tuple(results)


def generate(root: Path) -> int:
    """Full regenerate: build to temp, atomic-swap over ``adapters/`` (REQ-DET-02).

    On a CanonError, the staging dir is removed and ``adapters/`` is left intact —
    no partial tree (REQ-ROB-01). Returns the process exit code (00 §9).
    """
    staging = _new_staging_dir(root)
    try:
        build_tree(root, staging)  # §4.1 — raises CanonError on bad canon
    except CanonError as exc:
        shutil.rmtree(staging, ignore_errors=True)
        print(str(exc), file=sys.stderr)  # "<source_path>: <reason>" (REQ-OBS-02)
        return 1
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise  # a generator bug — propagate as a stack trace (00 §8)

    # Atomic swap: replace adapters/ wholesale (REQ-DET-02 — no orphan survives).
    final = root / ADAPTERS_DIRNAME
    backup = root / f"{ADAPTERS_DIRNAME}.tmp-{os.getpid()}.prev"
    moved = False
    if final.exists():
        os.replace(final, backup)  # move old out of the way (same filesystem)
        moved = True
    try:
        os.replace(staging, final)  # publish the new tree atomically
    except BaseException:
        # Publish failed after the old tree was moved aside: restore it so
        # adapters/ is never left missing (REQ-ROB-01 — no partial/absent tree).
        if moved and not final.exists():
            os.replace(backup, final)
        shutil.rmtree(staging, ignore_errors=True)
        raise
    if backup.exists():
        shutil.rmtree(backup, ignore_errors=True)
    _fsync_dir(root)  # best-effort: durably record the rename in the parent dir
    return 0


def _fsync_dir(path: Path) -> None:
    """Best-effort fsync of a directory so a rename into it is durable on crash.

    Silently no-ops where directory fsync is unsupported (some platforms/filesystems
    reject ``O_RDONLY`` fsync) — durability is a hardening bonus, never a hard
    requirement of the build.
    """
    try:
        dir_fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        pass


def check(root: Path) -> int:
    """Drift guard: build to temp, ``diff -r`` vs committed ``adapters/``, never
    mutate ``adapters/`` (REQ-CI-01, REQ-DET-03). Returns the exit code (00 §9).
    """
    staging = _new_staging_dir(root)
    try:
        build_tree(root, staging)
    except CanonError as exc:
        shutil.rmtree(staging, ignore_errors=True)
        print(str(exc), file=sys.stderr)
        return 1
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    committed = root / ADAPTERS_DIRNAME
    try:
        # `diff -r` exit 0 == identical; 1 == differs; >1 == diff TOOL error.
        proc = subprocess.run(
            ["diff", "-r", str(committed), str(staging)],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        # `diff` is not installed — an environment fault, NOT a drift verdict.
        shutil.rmtree(staging, ignore_errors=True)
        print(
            "adapters: `diff` executable not found — cannot run the drift guard; "
            "this is an environment fault, not a drift verdict.",
            file=sys.stderr,
        )
        return 2
    finally:
        shutil.rmtree(staging, ignore_errors=True)  # never leave a tmp tree

    if proc.returncode == 0:
        return 0  # identical — no drift
    if proc.returncode == 1:
        # Real drift: show the diff + remediation (REQ-CI-03). exit 1 is a verdict.
        sys.stdout.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        print(REMEDIATION_MESSAGE, file=sys.stderr)  # 00 §9, single-sourced
        return 1
    # returncode > 1: `diff` itself failed. A TOOL error, never drift — do NOT
    # print REMEDIATION_MESSAGE (it would be misleading).
    sys.stderr.write(proc.stderr)
    print(
        f"adapters: `diff -r` failed to compare trees (exit {proc.returncode}) — "
        "this is a diff-tool error, not a drift verdict.",
        file=sys.stderr,
    )
    return 2


# --------------------------------------------------------------------------- #
# main() & argparse control flow (02 §5, REQ-GEN-02)
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    """Parse args and run the generator (REQ-GEN-02). Returns an exit code (00 §9).

    Args:
        argv: CLI args (excluding program name); None → sys.argv[1:].

    Returns:
        0 ok; 1 canon error (default) or drift (`--check`); argparse exits 2 on a
        usage error before this returns (a caller mistake, never a verdict, 00 §9).
    """
    parser = argparse.ArgumentParser(
        prog="build-adapters.py",
        description=(
            "Generate per-agent adapters/ from the feature-forge canon "
            "(skills/, agents/, references/). Deterministic, full-regenerate."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Drift guard: regenerate to a temp dir and diff vs committed "
        "adapters/; exit non-zero on drift. Does not modify adapters/.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Repo root (default: parent of this script's dir), mirroring "
        "check-spec-purity.py.",
    )
    args = parser.parse_args(argv)
    root: Path = args.root.resolve()

    return check(root) if args.check else generate(root)


if __name__ == "__main__":
    raise SystemExit(main())
