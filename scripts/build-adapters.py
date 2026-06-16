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

import argparse
import hashlib
import io
import json
import os
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
        content = render_frontmatter_block(native, skill.source_path) + skill.body
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
        content = render_frontmatter_block(native, agent.source_path) + agent.body
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


class CodexEmitter:
    """Emitter for ``codex``: skill mirror (.md) + an aggregate ``agents/openai.yaml``.

    The native agent schema's representable key set is TQ-1 (03 §8); the safe
    default emits ``name`` + ``description`` and drop-records the rest so no key is
    silently lost (REQ-GEN-06 / REQ-OBS-01). The aggregate ``agents/openai.yaml`` is
    written by the ENGINE from the collected ``manifest_entries`` (02 §4.1), never by
    this emitter.
    """

    agent_id = "codex"
    # Keys confirmed representable in agents/openai.yaml. EMPTY until TQ-1 confirms
    # the schema; expand (e.g. {"model", "tools"}) once verified against OpenAI docs.
    _CODEX_AGENT_KEYS: frozenset[str] = frozenset()

    def emit_skill(self, skill: SkillRecord) -> EmitResult:
        """Emit ``skills/<name>/<name>.md`` with {name, description} + body."""
        native = order_fields({"name": skill.name, "description": skill.description})
        content = render_frontmatter_block(native, skill.source_path) + skill.body
        rel = f"skills/{skill.name}/{skill.name}.md"
        drops: tuple[DropRecord, ...] = ()
        if hint_value(skill) is not None:  # REQ-FMT-02 branch 2 (TQ-1)
            drops = (DropRecord("codex", skill.source_path, "argument-hint",
                                "no confirmed Codex invocation-hint field (TQ-1)"),)
        return EmitResult(files=(EmittedFile(rel, content),), drops=drops)

    def emit_agent(self, agent: AgentRecord) -> EmitResult:
        """Emit a body artifact ``agents/<name>.md`` + one ManifestEntry per sub-agent.

        Body+description preserved (REQ-FMT-04); structural keys not in
        ``_CODEX_AGENT_KEYS`` are drop-recorded (REQ-GEN-06). The aggregate
        ``agents/openai.yaml`` is NOT written here — the engine merges the returned
        ManifestEntry(-ies) into the single manifest after the per-record loop
        (00 §5, 02 §4.1).
        """
        dropped = tuple(
            DropRecord("codex", agent.source_path, f"sub-agent key '{k}'",
                       "not representable in agents/openai.yaml (TQ-1)")
            for k in agent.claude_keys if k not in self._CODEX_AGENT_KEYS
        )
        rel = f"agents/{agent.name}.md"  # body artifact retains behavior text
        content = render_frontmatter_block(
            order_fields({"name": agent.name, "description": agent.description}),
            agent.source_path,
        ) + agent.body
        # Representable structural keys (none until TQ-1 expands _CODEX_AGENT_KEYS)
        # carried in `extra`; serialization/key-order owned by 04 §1.3.
        extra = {k: agent.claude_keys[k] for k in agent.claude_keys
                 if k in self._CODEX_AGENT_KEYS}
        entry = ManifestEntry(name=agent.name, description=agent.description, extra=extra)
        return EmitResult(
            files=(EmittedFile(rel, content),),
            drops=dropped,
            manifest_entries=(entry,),
        )


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
        content = render_frontmatter_block(native, skill.source_path) + skill.body
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
        ) + agent.body
        drops = drop_all_claude_keys(agent, "copilot", "no Copilot sub-agent construct (TQ-1)")
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
        ) + skill.body
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
        ) + agent.body
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

    # (3) Byte-identical forge-root.sh copy, mode 0755, NO header (§2.3, REQ-GEN-05).
    src_resolver = repo_root / "scripts" / "forge-root.sh"
    dst_resolver = bundle_root / "scripts" / "forge-root.sh"
    dst_resolver.parent.mkdir(parents=True, exist_ok=True)
    _assert_within(dst_resolver, bundle_root)
    shutil.copyfile(src_resolver, dst_resolver)   # bytes only — never copystat/edit
    dst_resolver.chmod(0o755)
    _assert_byte_identical(src_resolver, dst_resolver)  # REQ-GEN-05 hard assertion


def _copytree_verbatim(src: Path, dst: Path, bundle_root: Path) -> None:
    """Recursively copy ``src`` → ``dst`` byte-for-byte (no header injection, §1.6).

    Walks ``src`` in sorted POSIX order (REQ-DET-01) so any incidental ordering is
    stable. Every destination is asserted within ``bundle_root`` (REQ-SEC-01).
    """
    for entry in sorted(src.rglob("*"), key=lambda p: p.relative_to(src).as_posix()):
        rel = entry.relative_to(src)
        target = dst / rel
        _assert_within(target, bundle_root)
        if entry.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(entry, target)  # verbatim bytes; no stamp, no reflow


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
    elif agent_id == "codex":
        # agents/openai.yaml: same `_generated`-first rule (00 §7 / §1.3). The codex
        # agent manifest is YAML; `_generated` provenance is the first serialized key,
        # then the per-sub-agent array. Native key set is TQ-1 (03 §4) → entries carry
        # {name, description} (+ any confirmed `extra`) only.
        manifest = {
            PROVENANCE_JSON_KEY: provenance_json("agents/"),
            "agents": [
                {"name": e.name, "description": e.description, **e.extra}
                for e in entries
            ],
        }
        rel = "agents/openai.yaml"
        content = yaml.safe_dump(
            manifest,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
            width=4096,
        )
        safe_write(dest / agent_id, rel, content)  # 02 §4.2 sandbox guard


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
        "- the whole repo-root `references/` tree (14 files: 9 root + `stacks/`×5) "
        "→ `adapters/<agent>/references/` (verbatim — REQ-GEN-04 / D5).",
        "- each skill's own `references/` subdir → "
        "`adapters/<agent>/skills/<name>/references/` (verbatim, where present).",
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
    if final.exists():
        os.replace(final, backup)  # move old out of the way (same filesystem)
    os.replace(staging, final)  # publish the new tree atomically
    if backup.exists():
        shutil.rmtree(backup, ignore_errors=True)
    return 0


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
