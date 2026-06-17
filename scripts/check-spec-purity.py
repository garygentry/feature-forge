#!/usr/bin/env python3
"""Validate the feature-forge skill canon for spec purity (REQ-VER-01..03).

Stdlib-only (no pyyaml), matching scripts/epic-manifest.py. Enforces the five
rules from tech-spec.md §3.4 against the canonical skill surfaces, printing a
human-readable report (REQ-OBS-01) and exiting non-zero on any violation
(REQ-VER-02). See spec docs 00-core-definitions.md (types/constants) and
05-spec-purity-checker.md (this implementation).

Usage:
    python3 check-spec-purity.py [--root DIR]

Exit codes:
    0 = canon clean (zero violations)
    1 = one or more violations (each printed as `file: reason`)
    2 = usage error (argparse)
"""

from __future__ import annotations

import argparse
import enum
import fnmatch
import json
import re
from dataclasses import dataclass
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# Shared contracts (00-core-definitions.md). Defined once here for a stdlib-only,
# import-free single-file checker; kept byte-aligned with the spec's §1/§2/§3/§5.
# ─────────────────────────────────────────────────────────────────────────────

# §1 — frontmatter schema (REQ-FM-01, REQ-VND-01).
#
# The allowed/required key sets are LOADED from the single declarative source of
# truth, references/skill-frontmatter.schema.json (00 §3 / tech-spec §3.3), so the
# schema and this checker can never drift. The schema fixes WHICH keys are allowed;
# the two checks JSON Schema cannot express (name == directory, residual
# ${CLAUDE_PLUGIN_ROOT} / prelude / body-size) stay in Python below. The module
# globals below are placeholders re-bound in main() from the resolved root
# (REQ-CI-02): a SKILL.md gate with no schema is meaningless, so the loader fails
# loudly if the schema is missing/unparseable.
#: Path to the canonical SKILL.md frontmatter schema, relative to the repo root.
SCHEMA_REL_PATH: str = "references/skill-frontmatter.schema.json"

REQUIRED_FRONTMATTER_KEYS: frozenset[str] = frozenset({"name", "description"})
ALLOWED_FRONTMATTER_KEYS: frozenset[str] = frozenset(
    {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
)


def _load_frontmatter_key_sets(root: Path) -> tuple[frozenset[str], frozenset[str]]:
    """Load (REQUIRED, ALLOWED) frontmatter key sets from the JSON Schema (00 §3).

    REQUIRED = the schema's ``required`` array; ALLOWED = the schema's
    ``properties`` keys. additionalProperties:false in the schema means ALLOWED is
    the exact closed set (REQ-CONST-03). Stdlib json only — no jsonschema dep.

    Args:
        root: The repo root (the schema sits at SCHEMA_REL_PATH beneath it).

    Returns:
        (REQUIRED_FRONTMATTER_KEYS, ALLOWED_FRONTMATTER_KEYS) as frozensets.

    Raises:
        SystemExit: if the schema is missing or unparseable — a hard config error
            (a SKILL.md gate with no schema is meaningless; fail loudly, REQ-OBS-01).
    """
    schema_path = root / SCHEMA_REL_PATH
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(
            f"check-spec-purity: FATAL — schema not found at {schema_path} "
            f"(REQ-CI-02 requires references/skill-frontmatter.schema.json; see 00 §3)."
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(
            f"check-spec-purity: FATAL — schema at {schema_path} is unreadable/"
            f"invalid JSON: {exc}"
        )
    required = frozenset(schema.get("required", []))
    allowed = frozenset(schema.get("properties", {}).keys())
    return required, allowed

# §2 — size budget (REQ-SIZE-03, decision D1).
MAX_BODY_LINES: int = 300
MAX_BODY_WORDS: int = 5000

# §6 — canonical surfaces scanned by rules 3 and 5 (REQ-RES-03). The recursive
# patterns end in `/**/*` (not `/**`): a bare trailing `/**` matches directories
# only, so `/**/*` is required to reach the files inside references/ trees.
CANONICAL_SURFACES: tuple[str, ...] = (
    "skills/**/SKILL.md",
    "skills/**/references/**/*",
    "references/**/*",
    "agents/*.md",
)

# §6 — loci exempt from the residual-var scan (rule 3). scripts/forge-root.sh
# holds the single sanctioned ${CLAUDE_PLUGIN_ROOT} fallback (REQ-RES-02/05);
# hooks/hooks.json is out-of-canon (REQ-VND-04); specs/plans/docs are
# non-canonical; references/vendor-construct-inventory.md is the REQ-VND-03 audit
# artifact, which documents the literal as prose *inside* a canonical surface and
# so must be exempted by name (it is not excluded by the globs). Matched with
# fnmatch against the repo-relative POSIX path.
RESIDUAL_VAR_EXEMPT: tuple[str, ...] = (
    "scripts/forge-root.sh",
    "hooks/hooks.json",
    "specs/**",
    "plans/**",
    "docs/**",
    "references/vendor-construct-inventory.md",
    # adapters/** is the GENERATED per-agent tree (forge-agent-adapters-build).
    # It is outside CANONICAL_SURFACES by construction (it is not under skills/,
    # the repo-root references/, or agents/*.md), so generated vendor frontmatter
    # never reaches the scan. This NAMED entry is belt-and-suspenders +
    # regression-proofing: each bundle carries a VERBATIM scripts/forge-root.sh
    # copy (the sanctioned ${CLAUDE_PLUGIN_ROOT} fallback, REQ-GEN-05) and verbatim
    # references/ copies (the canonical bootstrap prelude, D5); this entry keeps
    # rule 3 (and the prelude scan that shares iter_canonical_files) from ever
    # re-flagging them if CANONICAL_SURFACES is later widened. Additive only — it
    # does NOT relax enforcement over skills/, references/, or agents/ (REQ-PUR-02).
    "adapters/**",
)

# §3 — the canonical bootstrap prelude (REQ-RES-05). Byte-identical to the
# fenced block in references/portable-root.md and BOOTSTRAP_PRELUDE in 00 §3.
BOOTSTRAP_PRELUDE: str = (
    'R="$(for d in "$HOME"/.claude/skills/feature-forge '
    '"$HOME"/.claude/plugins/*/feature-forge; do '
    '[ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done)"\n'
    '[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }'
)

#: The forbidden literal (00 §6). The sanctioned residual in scripts/forge-root.sh
#: and the documentary occurrences in references/vendor-construct-inventory.md are
#: skipped via RESIDUAL_VAR_EXEMPT; other exempt loci fall outside the canonical globs.
_RESIDUAL_VAR: str = "${CLAUDE_PLUGIN_ROOT}"

#: First-discoverable-resolver inner line — marks a prelude occurrence to verify.
_PRELUDE_SENTINEL: str = (
    '[ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"'
)

# §5 — canonical violation reason strings (single source of truth; never
# re-typed inline). Placeholder fields are filled with str.format() at emit time;
# no-placeholder strings are used verbatim.
VR_DISALLOWED_KEY: str = "disallowed frontmatter key '{key}'"
VR_MISSING_REQUIRED: str = "missing required frontmatter key '{key}'"
VR_MALFORMED_FM: str = "malformed frontmatter block"
VR_NAME_MISMATCH: str = "name '{name}' != directory '{dir}'"
VR_RESIDUAL_VAR: str = "residual ${CLAUDE_PLUGIN_ROOT} in canonical surface"
VR_BODY_LINES: str = "body {n} lines exceeds {limit}"
VR_BODY_WORDS: str = "body {n} words exceeds {limit}"
VR_PRELUDE_DRIFT: str = "bootstrap prelude not byte-identical to canon"


class Rule(str, enum.Enum):
    """The five spec-purity rules check-spec-purity.py enforces (tech-spec §3.4).

    Uses the ``str, enum.Enum`` mixin (rather than 3.11's ``enum.StrEnum``) so the
    checker runs on the repo's Python 3.10 baseline; ``.value`` is a plain ``str``,
    which is all the ordering/output logic relies on.
    """

    FRONTMATTER_KEYS = "frontmatter-keys"  # rule 1 — REQ-FM-01/04
    NAME_MATCHES_DIR = "name-matches-dir"  # rule 2 — REQ-FM-02
    NO_RESIDUAL_VAR = "no-residual-var"  # rule 3 — REQ-RES-03
    BODY_SIZE = "body-size"  # rule 4 — REQ-SIZE-03 (hard fail)
    PRELUDE_IDENTITY = "prelude-identity"  # rule 5 — REQ-RES-05 / REQ-MAINT-01


@dataclass(frozen=True)
class Violation:
    """One spec-purity violation, rendered as `file: reason` (REQ-VER-02, REQ-OBS-01).

    Attributes:
        path: Repo-relative path of the offending file (POSIX separators).
        rule: Which Rule was violated.
        reason: Human-readable explanation, suitable for CI logs.
    """

    path: str
    rule: Rule
    reason: str

    def render(self) -> str:
        """Return the canonical one-line form: ``<path>: <reason>``."""
        return f"{self.path}: {self.reason}"


@dataclass(frozen=True)
class Frontmatter:
    """Result of parsing a SKILL.md frontmatter block (00 §4 contract).

    Attributes:
        ok: True iff a well-formed ``---`` … ``---`` block was found and parsed.
        keys: Ordered tuple of top-level keys (column-0 ``key:`` lines), in
            file order. Empty when ``ok`` is False.
        body_start_line: 0-based line index of the first body line (the line
            after the closing ``---``). ``-1`` when ``ok`` is False. Used by
            rule 4 (§3.4) to slice the body.
    """

    ok: bool
    keys: tuple[str, ...]
    body_start_line: int


# ─────────────────────────────────────────────────────────────────────────────
# §2 — the stdlib frontmatter reader (REQ-FM-04)
# ─────────────────────────────────────────────────────────────────────────────

#: A column-0 top-level key: a letter, then word chars / hyphens, then a colon.
#: Anchored at column 0 — indented and quoted/folded value lines never match.
_TOP_LEVEL_KEY_RE: re.Pattern[str] = re.compile(r"^([A-Za-z][\w-]*):")

#: Capture a column-0 `name:` value (unquoted or single/double quoted scalar).
_NAME_VALUE_RE: re.Pattern[str] = re.compile(
    r'^name:\s*["\']?([^"\'\r\n]+?)["\']?\s*$'
)


def read_frontmatter(text: str) -> Frontmatter:
    """Parse a Markdown file's YAML frontmatter without pyyaml (00 §4).

    Locates the leading ``---`` … ``---`` fence and extracts only the
    column-0 ``key:`` lines as top-level keys. Values (including colon-bearing
    or ``>`` / ``|`` block scalars), indented/nested keys, continuation lines,
    and blank lines are NOT re-scanned for keys. CRLF endings are tolerated.

    Args:
        text: The full file contents (already decoded to ``str``).

    Returns:
        A ``Frontmatter`` with ``ok=True`` and the ordered top-level keys when a
        well-formed block is found; otherwise ``ok=False`` (a malformed-block
        signal, never an exception — REQ-FM-04).
    """
    # Normalize CRLF (and lone CR) so column-0 matching is line-ending agnostic.
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    # The opening fence must be the first non-empty line and be exactly "---".
    open_idx = -1
    for i, line in enumerate(lines):
        if line == "":
            continue
        open_idx = i if line == "---" else -1
        break
    if open_idx == -1:
        return Frontmatter(ok=False, keys=(), body_start_line=-1)

    # The closing fence is the next column-0 "---" after the opener.
    close_idx = -1
    for i in range(open_idx + 1, len(lines)):
        if lines[i] == "---":
            close_idx = i
            break
    if close_idx == -1:
        return Frontmatter(ok=False, keys=(), body_start_line=-1)

    keys: list[str] = []
    in_block_scalar = False
    for line in lines[open_idx + 1 : close_idx]:
        if line.strip() == "":
            continue
        # Inside a `>` / `|` block scalar, every more-indented line is value
        # content — skip until indentation returns to column 0.
        if in_block_scalar:
            if line[:1] in (" ", "\t"):
                continue
            in_block_scalar = False
        # Indented lines are nested keys or values — never top-level keys.
        if line[:1] in (" ", "\t"):
            continue
        match = _TOP_LEVEL_KEY_RE.match(line)
        if match is None:
            # A column-0 line that is neither blank nor `key:` (e.g. a stray
            # list item or malformed YAML) makes the block ill-formed.
            return Frontmatter(ok=False, keys=(), body_start_line=-1)
        keys.append(match.group(1))
        # Detect the start of a block scalar so its indented body is skipped.
        value = line[match.end() :].strip()
        if value in (">", "|") or value.startswith((">", "|")):
            in_block_scalar = True

    if not keys:
        # A well-fenced but empty / keyless block is malformed for our purposes.
        return Frontmatter(ok=False, keys=(), body_start_line=-1)

    return Frontmatter(ok=True, keys=tuple(keys), body_start_line=close_idx + 1)


# ─────────────────────────────────────────────────────────────────────────────
# §3 — discovery helpers
# ─────────────────────────────────────────────────────────────────────────────


def iter_canonical_files(root: Path) -> list[Path]:
    """Return every readable file under the canonical surfaces, deduped + sorted.

    Honors CANONICAL_SURFACES (00 §6). Directories matched by recursive globs
    are filtered out (only files are returned). Result is sorted by POSIX path
    for deterministic violation ordering (§7).

    Args:
        root: The repo root to scan.

    Returns:
        Sorted unique list of file ``Path`` objects under the canonical surfaces.
    """
    seen: set[Path] = set()
    for pattern in CANONICAL_SURFACES:
        for path in root.glob(pattern):
            if path.is_file():
                seen.add(path)
    return sorted(seen, key=lambda p: p.relative_to(root).as_posix())


def _read_text(path: Path) -> str | None:
    """Read a file as UTF-8, returning None when it cannot be read (§7).

    Args:
        path: File to read.

    Returns:
        The decoded contents, or None on OSError / decode failure.
    """
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _skill_md_files(root: Path) -> list[Path]:
    """Return every ``skills/*/SKILL.md`` in sorted POSIX-path order."""
    return sorted(
        root.glob("skills/*/SKILL.md"),
        key=lambda p: p.relative_to(root).as_posix(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# §3.1–§3.5 — the five rules
# ─────────────────────────────────────────────────────────────────────────────


def check_frontmatter_keys(root: Path) -> list[Violation]:
    """Rule 1: every SKILL.md frontmatter well-formed, keys ⊆ allowed, name+description present.

    Maps to REQ-FM-01 (closed allow-list) and REQ-FM-04 (parseable; malformed =
    reported violation, not crash).

    Args:
        root: The repo root to scan.

    Returns:
        One or more Violation per offending SKILL.md, in file order.
    """
    violations: list[Violation] = []
    for skill_md in _skill_md_files(root):
        rel = skill_md.relative_to(root).as_posix()
        text = _read_text(skill_md)
        if text is None:
            violations.append(
                Violation(
                    rel,
                    Rule.FRONTMATTER_KEYS,
                    f"{VR_MALFORMED_FM} (unreadable file)",
                )
            )
            continue
        fm = read_frontmatter(text)
        if not fm.ok:
            violations.append(Violation(rel, Rule.FRONTMATTER_KEYS, VR_MALFORMED_FM))
            continue
        keys = set(fm.keys)
        for key in sorted(keys - ALLOWED_FRONTMATTER_KEYS):
            violations.append(
                Violation(
                    rel, Rule.FRONTMATTER_KEYS, VR_DISALLOWED_KEY.format(key=key)
                )
            )
        for key in sorted(REQUIRED_FRONTMATTER_KEYS - keys):
            violations.append(
                Violation(
                    rel, Rule.FRONTMATTER_KEYS, VR_MISSING_REQUIRED.format(key=key)
                )
            )
    return violations


def check_name_matches_dir(root: Path) -> list[Violation]:
    """Rule 2: each skill's frontmatter `name` equals its containing directory (REQ-FM-02).

    Emits VR_NAME_MISMATCH (00 §5) when they differ. Skills with a malformed
    block or absent `name` are already reported by rule 1; rule 2 skips them.

    Args:
        root: The repo root to scan.

    Returns:
        One Violation per skill whose name != directory, in directory order.
    """
    violations: list[Violation] = []
    for skill_md in _skill_md_files(root):
        rel = skill_md.relative_to(root).as_posix()
        dir_name = skill_md.parent.name
        text = _read_text(skill_md)
        if text is None:
            continue  # rule 1 reports unreadable/malformed
        name_value: str | None = None
        for line in text.replace("\r\n", "\n").split("\n"):
            if line == "---" and name_value is None:
                continue
            match = _NAME_VALUE_RE.match(line)
            if match is not None:
                name_value = match.group(1).strip()
                break
        if name_value is not None and name_value != dir_name:
            violations.append(
                Violation(
                    rel,
                    Rule.NAME_MATCHES_DIR,
                    VR_NAME_MISMATCH.format(name=name_value, dir=dir_name),
                )
            )
    return violations


def check_no_residual_var(root: Path) -> list[Violation]:
    """Rule 3: zero ${CLAUDE_PLUGIN_ROOT} across canonical surfaces (REQ-RES-03).

    Scans CANONICAL_SURFACES (00 §6), skipping paths in RESIDUAL_VAR_EXEMPT — the
    sanctioned scripts/forge-root.sh fallback and the in-surface
    references/vendor-construct-inventory.md audit artifact are exempted by name;
    the remaining exempt globs (hooks.json, specs/plans/docs) fall outside the
    canonical surfaces anyway. Emits VR_RESIDUAL_VAR (00 §5).

    Args:
        root: The repo root to scan.

    Returns:
        One Violation per offending canonical file, in sorted path order.
    """
    violations: list[Violation] = []
    for path in iter_canonical_files(root):
        rel = path.relative_to(root).as_posix()
        if any(fnmatch.fnmatch(rel, pattern) for pattern in RESIDUAL_VAR_EXEMPT):
            continue
        text = _read_text(path)
        if text is None:
            continue
        if _RESIDUAL_VAR in text:
            violations.append(Violation(rel, Rule.NO_RESIDUAL_VAR, VR_RESIDUAL_VAR))
    return violations


def check_body_size(root: Path) -> list[Violation]:
    """Rule 4: each SKILL.md body ≤300 lines AND ≤5000 words (REQ-SIZE-03, hard fail).

    Body = content after the closing frontmatter `---` (00 §2). Both limits are
    checked independently, so an over-line and an over-word body produce two
    violations. Emits VR_BODY_LINES / VR_BODY_WORDS (00 §5).

    Args:
        root: The repo root to scan.

    Returns:
        Up to two Violation per offending skill (lines and/or words), in
        directory order.
    """
    violations: list[Violation] = []
    for skill_md in _skill_md_files(root):
        rel = skill_md.relative_to(root).as_posix()
        text = _read_text(skill_md)
        if text is None:
            continue  # rule 1 reports unreadable
        fm = read_frontmatter(text)
        if not fm.ok:
            continue  # rule 1 reports malformed; body undefined without close fence
        body_lines = text.replace("\r\n", "\n").split("\n")[fm.body_start_line :]
        # Drop a single trailing empty element from a final newline so the count
        # reflects real body lines, not the split artifact.
        if body_lines and body_lines[-1] == "":
            body_lines = body_lines[:-1]
        n_lines = len(body_lines)
        n_words = sum(len(line.split()) for line in body_lines)
        if n_lines > MAX_BODY_LINES:
            violations.append(
                Violation(
                    rel,
                    Rule.BODY_SIZE,
                    VR_BODY_LINES.format(n=n_lines, limit=MAX_BODY_LINES),
                )
            )
        if n_words > MAX_BODY_WORDS:
            violations.append(
                Violation(
                    rel,
                    Rule.BODY_SIZE,
                    VR_BODY_WORDS.format(n=n_words, limit=MAX_BODY_WORDS),
                )
            )
    return violations


def check_prelude_identity(root: Path) -> list[Violation]:
    """Rule 5: every bootstrap-prelude occurrence is byte-identical to canon (REQ-RES-05).

    A file is "using the prelude" iff it contains _PRELUDE_SENTINEL. For each such
    file, assert the canonical BOOTSTRAP_PRELUDE string appears verbatim; if the
    sentinel is present but the exact two-line snippet is not, the prelude has
    drifted. Emits VR_PRELUDE_DRIFT (00 §5). Guards REQ-MAINT-01.

    Args:
        root: The repo root to scan.

    Returns:
        One Violation per file whose prelude is not byte-identical to canon.
    """
    violations: list[Violation] = []
    for path in iter_canonical_files(root):
        text = _read_text(path)
        if text is None:
            continue
        normalized = text.replace("\r\n", "\n")
        if _PRELUDE_SENTINEL in normalized and BOOTSTRAP_PRELUDE not in normalized:
            rel = path.relative_to(root).as_posix()
            violations.append(
                Violation(rel, Rule.PRELUDE_IDENTITY, VR_PRELUDE_DRIFT)
            )
    return violations


def collect_violations(root: Path) -> list[Violation]:
    """Run all five rules and return their violations in deterministic order (§7).

    Args:
        root: The repo root to scan.

    Returns:
        The concatenation of every rule's violations, then globally sorted for
        stable CI output (§7).
    """
    violations: list[Violation] = []
    violations += check_frontmatter_keys(root)  # rule 1 — REQ-FM-01/04
    violations += check_name_matches_dir(root)  # rule 2 — REQ-FM-02
    violations += check_no_residual_var(root)  # rule 3 — REQ-RES-03
    violations += check_body_size(root)  # rule 4 — REQ-SIZE-03
    violations += check_prelude_identity(root)  # rule 5 — REQ-RES-05
    return sorted(violations, key=lambda v: (v.path, v.rule.value, v.reason))


# ─────────────────────────────────────────────────────────────────────────────
# §4 — output
# ─────────────────────────────────────────────────────────────────────────────


def report(violations: list[Violation]) -> int:
    """Print the human-readable report and return the exit code (REQ-OBS-01, REQ-VER-02).

    Args:
        violations: The deterministically ordered violations from
            ``collect_violations``.

    Returns:
        0 when ``violations`` is empty (canon clean), else 1.
    """
    if not violations:
        print("spec-purity: PASS — 0 violations across canonical surfaces.")
        return 0

    print(f"spec-purity: FAIL — {len(violations)} violation(s):")
    for v in violations:
        print(f"  {v.render()}")  # `<path>: <reason>` (00 §5 Violation.render)
    # Per-rule tally aids triage and stays machine-parseable.
    counts: dict[str, int] = {}
    for v in violations:
        counts[v.rule.value] = counts.get(v.rule.value, 0) + 1
    summary = ", ".join(f"{rule}={n}" for rule, n in sorted(counts.items()))
    print(f"spec-purity: by rule — {summary}")
    return 1


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, run all rules, print the report, return an exit code.

    Args:
        argv: Argument vector excluding the program name. Defaults to
            ``sys.argv[1:]`` when None.

    Returns:
        0 when the canon is clean, 1 when any violation was found.
    """
    parser = argparse.ArgumentParser(
        prog="check-spec-purity.py",
        description="Validate the feature-forge skill canon for spec purity.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Repo root to scan (default: parent of this script's dir).",
    )
    args = parser.parse_args(argv)
    root: Path = args.root.resolve()

    # Load the schema-driven key sets (REQ-CI-02 / tech-spec §3.3). The schema is
    # a property of the canon (it ships beside this script), so it is resolved from
    # the script's own repo root — NOT the scanned --root, which may be an external
    # skill tree (e.g. a test fixture) that carries no schema.
    global REQUIRED_FRONTMATTER_KEYS, ALLOWED_FRONTMATTER_KEYS
    schema_root = Path(__file__).resolve().parent.parent
    REQUIRED_FRONTMATTER_KEYS, ALLOWED_FRONTMATTER_KEYS = _load_frontmatter_key_sets(schema_root)

    violations = collect_violations(root)
    return report(violations)


if __name__ == "__main__":
    raise SystemExit(main())
