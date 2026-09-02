"""Guard: the Tooling Feedback Protocol — forge-init's root hygiene + `gh-available` (#244 P3).

PROTECTS:
  1. `references/shared-conventions.md` § Root Hygiene (Tooling Feedback) is the single
     home for the protocol: both routing URLs, the capture template, the go-ahead rule,
     the loop-safe rule, the never-overwrite guard for BOTH root files, the `local-write`
     tier, the INV-5 host/tool-availability split, and a stated rung-3 default.
  2. `references/templates/root-hygiene/{AGENTS,CLAUDE}.md` carry the tooling-feedback
     section **lifted verbatim** from `skills/forge-bootstrap`'s hygiene templates — one
     source of truth across the three copies, so a reword in one is a red test, not drift.
  3. `skills/forge-init/SKILL.md` runs the narrowed `doctor` preflight (naming
     `gh-available` and the other two ids), follows `references/preflight-and-self-heal.md`,
     and points at the Root Hygiene block by title while saying `local-write` — pointing,
     not restating (INV-4's prose-duplication rule applied to canon).
  4. The `specs/` hygiene templates' project-root pointer no longer dangles: it names how
     the root file gets written (G9, the actual defect behind "no feedback path exists").
  5. `scripts/forge-bootstrap.py` records that its never-overwrite guard is what keeps a
     forge-init-written root file from being duplicated.

NON-GOALS:
  - Executing forge-init (there is no harness here to run a skill against a fixture; that
    is the live headless smoke in `plans/federated-bubbling-micali.md`).
  - The adapter bundles' copies — `tests/test_adapter_host_neutrality.py` owns those.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import pytest

from _forge_paths import REFERENCES, SCRIPTS, SKILLS, read

SHARED_CONVENTIONS: Final[Path] = REFERENCES / "shared-conventions.md"
FORGE_INIT: Final[Path] = SKILLS / "forge-init" / "SKILL.md"
BOOTSTRAP_SCRIPT: Final[Path] = SCRIPTS / "forge-bootstrap.py"
ROOT_HYGIENE_DIR: Final[Path] = REFERENCES / "templates" / "root-hygiene"
SPECS_HYGIENE_DIR: Final[Path] = REFERENCES / "templates" / "specs-hygiene"
BOOTSTRAP_HYGIENE_DIR: Final[Path] = (
    SKILLS / "forge-bootstrap" / "references" / "templates" / "hygiene"
)

#: The section heading the three copies share. Lifting is asserted against this anchor,
#: so a renamed heading fails loudly rather than silently emptying the comparison.
TOOLING_HEADING: Final[str] = "## Tooling feedback (feature-forge / rauf)"

#: The `## Root Hygiene` title every pointer cites. Pointing BY TITLE is the rule the
#: ladder and safety-ladder blocks already established — a bare file citation does not
#: tell the reader which of that file's 20 sections owns the contract.
ROOT_HYGIENE_TITLE: Final[str] = "## Root Hygiene (Tooling Feedback)"


def _body(skill_text: str) -> str:
    """The skill BODY — frontmatter stripped, exactly as `build-adapters.py` scans it."""
    if not skill_text.startswith("---\n"):
        return skill_text
    return skill_text.split("---\n", 2)[2]


def _section(text: str, heading: str) -> str:
    """The text under `heading` up to the next same-or-higher-level heading.

    Fails if the heading is absent: an empty slice would make every equality
    assertion below vacuously true.
    """
    assert heading in text, f"heading missing: {heading!r}"
    level = len(heading) - len(heading.lstrip("#"))
    after = text.split(heading, 1)[1]
    stop = re.search(rf"^#{{1,{level}}} ", after, flags=re.MULTILINE)
    return (after[: stop.start()] if stop else after).strip()


def _root_hygiene_block() -> str:
    """The `## Root Hygiene (Tooling Feedback)` section of shared-conventions.md."""
    return _section(read(SHARED_CONVENTIONS), ROOT_HYGIENE_TITLE)


# --------------------------------------------------------------------------- #
# 1. The protocol is stated once, completely, in shared-conventions.md
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("clause", "why"),
    [
        ("https://github.com/garygentry/feature-forge/issues", "the forge routing target"),
        ("https://github.com/garygentry/rauf/issues", "the rauf routing target"),
        ("what you ran", "the capture template"),
        ("what you expected", "the capture template"),
        ("what actually happened", "the capture template"),
        ("a fix idea", "the capture template"),
        ("gh issue create", "the filing command the gh-available check backs"),
        ("go-ahead", "operator approval is required before filing"),
        ("progress.md", "the loop-safe rule: append, never file mid-loop"),
        ("`local-write`", "the safety tier a project-root write sits at"),
        ("INV-5", "host identity, never tool availability, picks the variants"),
        ("never overwrite an existing root file", "the idempotence contract"),
    ],
)
def test_root_hygiene_states_the_whole_protocol(clause: str, why: str) -> None:
    """Every load-bearing clause of the protocol lives in the one canonical block."""
    assert clause in _root_hygiene_block(), f"{ROOT_HYGIENE_TITLE} lost {why}: {clause!r}"


@pytest.mark.parametrize("filename", ["AGENTS.md", "CLAUDE.md"])
def test_root_hygiene_copy_is_guarded_and_targets_the_project_root(filename: str) -> None:
    """Each copy is `[ -f <root file> ] || cp …` — never an unguarded overwrite.

    The target is the bare project-root path, not `<specsDir>/…`: copying the root
    block into `specs/` is exactly the confusion the specs-hygiene siblings exist to
    avoid, and it would leave the pointer dangling all the same.
    """
    block = _root_hygiene_block()
    expected = (
        f'[ -f {filename} ] || cp '
        f'"$R/references/templates/root-hygiene/{filename}" {filename}'
    )
    assert expected in block, f"Root Hygiene lost the guarded copy for {filename}"


def test_root_hygiene_claude_variant_is_host_gated() -> None:
    """`CLAUDE.md` is offered on the Claude host only — and `AGENTS.md` always."""
    block = _root_hygiene_block()
    assert "`AGENTS.md` is always offered" in block
    assert "`CLAUDE.md` only when the host is Claude" in block


def test_root_hygiene_declares_a_rung_3_default() -> None:
    """INV-6: the prompt declares its non-interactive default, and states it in output."""
    block = _root_hygiene_block()
    assert "Rung-3 default" in block, "no rung-3 default declared for the root write"
    assert "advise-only" in block, "the degraded tier is not named"
    assert "write nothing" in block, "the rung-3 default is not the no-write option"


def test_root_hygiene_handles_a_pre_existing_root_file() -> None:
    """An existing root file is neither overwritten nor silently merged."""
    block = _root_hygiene_block()
    assert "already exists" in block
    assert "paste" in block, "no paste-it-yourself path for a project that owns its file"


# --------------------------------------------------------------------------- #
# 2. The three copies of the section are one text (lift, don't rewrite)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("filename", ["AGENTS.md", "CLAUDE.md"])
def test_root_hygiene_template_is_lifted_verbatim_from_bootstrap(filename: str) -> None:
    """The shipped template's section is byte-equal to forge-bootstrap's.

    Two writers emit this block into a project root (`forge-init` for an existing
    repo, `forge-bootstrap` for a scaffolded one). Divergence between them is a
    silent inconsistency in project-facing guidance, so it is a test failure.
    """
    template = _section(read(ROOT_HYGIENE_DIR / filename), TOOLING_HEADING)
    bootstrap = _section(read(BOOTSTRAP_HYGIENE_DIR / filename), TOOLING_HEADING)
    # The bootstrap template's section is the last one in its file; the root-hygiene
    # template appends a provenance line after it. Compare only the shared prefix,
    # which is the block itself.
    template_block = template.split("\nThis file was generated by feature-forge.")[0].strip()
    assert template_block == bootstrap, (
        f"references/templates/root-hygiene/{filename} has drifted from "
        f"skills/forge-bootstrap/references/templates/hygiene/{filename} — "
        "lift the text, do not rewrite it (roadmap §7 P3)"
    )


@pytest.mark.parametrize("filename", ["AGENTS.md", "CLAUDE.md"])
def test_root_hygiene_template_stands_alone_as_a_root_file(filename: str) -> None:
    """The template is written verbatim as a whole file, so it needs its own title.

    It also must carry no `{{TOKEN}}` placeholder: unlike bootstrap's templates it is
    `cp`-ed, never composed, so an unsubstituted token would ship to the user's repo.
    """
    text = read(ROOT_HYGIENE_DIR / filename)
    assert text.startswith("# "), f"{filename} has no H1 — it ships as a whole root file"
    assert "{{" not in text, f"{filename} carries a placeholder nothing substitutes"
    assert "This file was generated by feature-forge." in text, (
        f"{filename} does not tell the reader where it came from"
    )


# --------------------------------------------------------------------------- #
# 3. forge-init runs the preflight and points at the block
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "check_id", ["gh-available", "plugin-root", "root-version-skew"]
)
def test_forge_init_preflights_the_named_checks(check_id: str) -> None:
    """The narrowed `doctor` call names its ids explicitly — never the full catalog."""
    body = _body(read(FORGE_INIT))
    assert f"--check {check_id}" in body, f"forge-init's preflight lost --check {check_id}"


def test_forge_init_follows_the_preflight_procedure() -> None:
    """The gate delegates to the P1 procedure rather than re-deriving one."""
    body = _body(read(FORGE_INIT))
    assert "references/preflight-and-self-heal.md" in body, (
        "forge-init's preflight cites no procedure — and an uncited reference is also "
        "not fanned into the skill's bundle (tests/test_reference_citations.py)"
    )


def test_forge_init_gh_remedies_are_advise_only() -> None:
    """`gh` is installed/authenticated off-project: both tiers are never executed."""
    body = _body(read(FORGE_INIT))
    assert "advise-only" in body
    assert "global-install" in body and "network" in body


def test_forge_init_points_at_root_hygiene_by_title() -> None:
    """Pointer, not restatement — the protocol text lives in exactly one place."""
    body = _body(read(FORGE_INIT))
    assert "Tooling feedback" in body, "forge-init never names the step"
    assert "`local-write`" in body, "forge-init does not state the write's safety tier"
    assert "Root Hygiene (Tooling Feedback)" in body, (
        "forge-init cites shared-conventions.md without naming the section that owns "
        "the contract"
    )
    assert "https://github.com/garygentry" not in body, (
        "forge-init restates the routing URLs the Root Hygiene block owns — pointer only"
    )


# --------------------------------------------------------------------------- #
# 4. The G9 dangling pointer is closed
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("filename", ["AGENTS.md", "CLAUDE.md"])
def test_specs_hygiene_pointer_no_longer_dangles(filename: str) -> None:
    """The `specs/` file says how the project-root section it defers to gets written.

    Before P3 only `forge-bootstrap` ever wrote that root section, so in a
    `forge-init` project the pointer named a file that did not exist (G9).
    """
    text = read(SPECS_HYGIENE_DIR / filename)
    assert f"project-root `{filename}`" in text, "the pointer itself is gone"
    assert "written by forge-init or forge-bootstrap" in text, (
        f"specs-hygiene/{filename} still defers to a root section without saying who "
        "writes it"
    )
    assert "/feature-forge:forge-init" in text, "no recovery path when the root file is absent"


def test_bootstrap_records_the_never_overwrite_interop() -> None:
    """`write_hygiene` documents why a forge-init-written root file is never duplicated."""
    source = read(BOOTSTRAP_SCRIPT)
    hygiene_doc = source.split("def write_hygiene(", 1)[1].split('"""', 2)[1]
    assert "forge-init" in hygiene_doc
    assert "never-overwrite" in hygiene_doc or "never overwrite" in hygiene_doc


# --------------------------------------------------------------------------- #
# 5. Non-vacuity — the helpers this module leans on actually discriminate
# --------------------------------------------------------------------------- #


def test_section_helper_rejects_a_missing_heading() -> None:
    """`_section` must fail loudly; a silent empty slice would pass every test above."""
    with pytest.raises(AssertionError):
        _section("# Title\n\nbody\n", "## Not Present")


def test_section_helper_stops_at_the_next_heading() -> None:
    """A section must not swallow its successor, or the lift comparison is meaningless."""
    text = "## A\n\nalpha\n\n## B\n\nbeta\n"
    assert _section(text, "## A") == "alpha"
