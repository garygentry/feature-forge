#!/usr/bin/env python3
"""Generate self-contained, per-agent adapter bundles from spec-pure canon.

This is the ``build-adapters`` generator for the ``forge-agent-adapters-build``
feature. It walks the spec-pure canon (``skills/``, ``agents/``, the
``references/`` trees) and emits a provenance-stamped ``adapters/<agent>/`` tree
for each of the five v1 target agents (claude, codex, copilot, cursor, gemini),
plus a ``GENERATION-REPORT.md`` drop-with-record report and a regenerate-and-diff
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

import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import yaml


# --------------------------------------------------------------------------- #
# 1. Target Agents (00 §1, REQ-GEN-03, REQ-DET-01)
# --------------------------------------------------------------------------- #

# The five v1 target agents (REQ-GEN-03). Order is FIXED (alphabetical) and is the
# emit/report iteration order — never sort at runtime, never reorder (REQ-DET-01).
AGENT_TARGETS: tuple[str, ...] = ("claude", "codex", "copilot", "cursor", "gemini")


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
    "effort",
    "memory",
    "skills",
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


def provenance_json(source: str) -> dict[str, str]:
    """Return the `_generated` provenance object for strict-JSON manifests."""
    return {"source": source, "regenerate": REGENERATE_CMD}


PROVENANCE_JSON_KEY: str = "_generated"

# The gemini-extension.json `version` value — a FIXED, canon-sourced constant, NOT
# read from a package manifest (feature-forge ships no package.json; C-2). It pins
# the manifest's required `version` key to a determinic value (REQ-DET-01) so two
# builds are byte-identical. Bump deliberately if the gemini extension schema (TQ-1)
# requires it; never derive it at runtime. Source of record: this constant.
GEMINI_EXTENSION_VERSION: str = "0.0.0"

# Exempt — `forge-root.sh`: copied BYTE-IDENTICAL (REQ-GEN-05), so NO header is
# injected. Its provenance is documented in GENERATION-REPORT.md instead.


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
