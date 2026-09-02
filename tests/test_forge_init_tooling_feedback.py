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
        ("never overwrite it", "the idempotence contract"),
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
    assert "`AGENTS.md` always" in block
    assert "`CLAUDE.md` only when the host is Claude" in block


def test_root_hygiene_declares_a_rung_3_default() -> None:
    """INV-6: the prompt declares its non-interactive default, and states it in output."""
    block = _root_hygiene_block()
    assert "Rung-3 default" in block, "no rung-3 default declared for the root write"
    assert "write nothing" in block, "the rung-3 default is not the no-write option"
    assert "state that the tooling-feedback section was skipped" in block, (
        "the rung-3 default is taken silently — INV-6 requires it be stated"
    )
    assert "not a *preflight remedy*" in block, (
        "the site class is unexplained, so the block reads as borrowing the preflight "
        "row it does not sit in (doctor emitted no remedy here)"
    )


def test_root_hygiene_separates_the_three_pre_existing_cases() -> None:
    """An existing root file splits into "already has the section" and "does not".

    Collapsing them is a real defect, not a nicety: an unconditional "print the block
    for the operator to paste" fires on the SECOND `forge-init` run — the run the
    specs-hygiene pointer actively tells people to make — and pastes a duplicate of a
    section the file already carries. The plan's acceptance criterion is "a second run
    does not duplicate or overwrite"; the `[ -f ]` guard delivers "not overwrite", and
    only this case split delivers "not duplicate".
    """
    block = _root_hygiene_block()
    assert "grep -q '^## Tooling feedback'" in block, (
        "no test for whether the existing file already carries the section — the "
        "already-there case cannot be distinguished from the project-owns-it case"
    )
    assert "Say nothing and do not prompt" in block, (
        "the already-there case does not resolve to silence, so a second forge-init "
        "run is repetitive rather than idempotent"
    )
    assert "paste" in block, "no paste-it-yourself path for a project that owns its file"
    assert "never append to it" in block, "the project-owns-it case permits a mutation"


def test_root_hygiene_looks_before_it_asks() -> None:
    """The existence test precedes the question, so nothing unwritable is prompted."""
    block = _root_hygiene_block()
    assert "Look before you ask" in block
    ask = block.index("ask **once**")
    missing = block.index("which variants are missing")
    assert missing < ask, (
        "the consolidated question is described before the missing-variant test, which "
        "is the ordering that prompts for writes that cannot happen"
    )


def test_root_hygiene_resolves_host_the_same_way_its_sibling_does() -> None:
    """The host gate is the build-substituted `--host` — locked decision D2.

    An earlier revision of this block pointed at `.feature-forge-bundle.json`'s `agent`
    field instead, reasoning that `--host` is not readable from anything forge-init
    loads. That is a real gap, but the sentinel is the wrong answer to it: the file
    exists in the six `adapters/*/` bundles and NOT at the mainline repo root, which is
    exactly where `$R` resolves on a dogfood install — so the read would fail with no
    stated fallback, leaving the host undetermined on the very install this repo uses.
    It also diverged from D2 for a mechanism this phase is not chartered to change.

    So this block resolves host identically to the Specs Directory Hygiene sibling 25
    lines above. The underlying "how does an agent actually read `--host`" gap is
    canon-wide, predates P3, and is tracked on #261 with the sibling rung-detection
    problem rather than being half-solved here.
    """
    block = _root_hygiene_block()
    assert "build-substituted `--host` value" in block, (
        "the host gate no longer names D2's mechanism"
    )
    assert ".feature-forge-bundle.json" not in block, (
        "the host gate points at a sentinel that is absent from a mainline install"
    )


def test_root_hygiene_anchors_the_write_at_the_project_root() -> None:
    """A bare `$PWD`-relative target can create `~/AGENTS.md` — a machine-scope file.

    The `[ -f … ] ||` guard prevents a clobber but NOT a creation, and a shell's cwd
    persists between calls. The Specs sibling is anchored by construction (its target
    is the config-derived `<specsDir>` path); this block's targets are bare, so it
    needs the assertion the sibling gets for free.
    """
    block = _root_hygiene_block()
    assert "[ -f forge.config.json ]" in block, (
        "nothing asserts the cwd is the project root before a root-scope write"
    )
    assert "not at the project root" in block


def test_root_hygiene_stages_what_it_writes() -> None:
    """forge-init has no commit step, so an unstaged new root file drifts."""
    block = _root_hygiene_block()
    assert "git add" in block, (
        "a file written here is left untracked and gets swept into whatever commits "
        "next — including a loop iteration's first commit"
    )


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


@pytest.mark.parametrize("check_id", ["gh-available", "root-version-skew"])
def test_forge_init_preflights_the_named_checks(check_id: str) -> None:
    """The narrowed `doctor` call names its ids explicitly — never the full catalog."""
    body = _body(read(FORGE_INIT))
    assert f"--check {check_id}" in body, f"forge-init's preflight lost --check {check_id}"


def test_forge_init_does_not_preflight_a_check_that_cannot_fire() -> None:
    """`plugin-root` is excluded on purpose, and the exclusion is explained in place.

    `_check_plugin_root` warns only when the resolver fails — and forge-init's own
    prelude hard-exits 1 on exactly that failure, several lines before `doctor` runs.
    So from THIS call site the check can only ever return `ok`. Narrowing to it would
    look like coverage while asserting nothing, and would leave a reader wondering why
    a `blocking`-severity check sits in an advisory-only preflight.
    """
    body = _body(read(FORGE_INIT))
    assert "--check plugin-root" not in body, (
        "forge-init narrows to `plugin-root`, which cannot fire below its own prelude"
    )
    assert "deliberately **not** in that list" in body, (
        "the exclusion is unexplained, so the next reader will 'fix' it by adding it back"
    )


def test_forge_init_declares_that_a_preflight_warn_is_not_a_stop() -> None:
    """A caller must declare its own gate outcome; the procedure never picks one.

    `preflight-and-self-heal.md` §7 is explicit that the caller owns the gate, and its
    failure taxonomy says a blocking check "stays a hard gate failure" for the caller
    that treats it as one. Without a declaration here, an agent has textual license to
    abort a healthy init on an advisory warn.
    """
    body = _body(read(FORGE_INIT))
    assert "Neither check is a stop for `forge-init`" in body


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


def test_forge_init_rung_2_test_is_not_tool_presence() -> None:
    """forge-init's rung-2 test matches the ladder's: "can be answered", not "no tool".

    This guards WORDING, and only wording. Its history matters, so it is recorded here
    rather than in a commit message nobody will read at the failure site:

    forge-init used to condense the ladder as "rung 2 (no structured tool, host can
    still prompt and wait)". That inverts which half is the test — the ladder says "no
    structured tool, BUT the host can still prompt and be answered" — and it directly
    contradicts the ladder's own per-host detection table, which calls `codex exec` and
    Pi's `-p`/`--mode json` rung 3. The sentence is now aligned with canon.

    What this did NOT do is change behavior. Measured on this branch, four headless
    runs (`pi -p --mode json` and `codex exec`, before and after the rewording, plus a
    `main` baseline): every one self-assessed **rung 2**, emitted a prose question at
    the auto-verify site, and stopped — after the fix Codex still reported "rung 2
    (interactive Codex)" while running under `codex exec`. The mis-read sentence was a
    contributing inaccuracy, not the cause. The cause is that a model has no
    model-visible signal for "this invocation has no reply channel", which is roadmap
    §6.2 D2's accepted limitation ("self-assessed, adds no new mechanism") meeting its
    first hard evidence. Fixing it needs a mechanism — a `doctor`-reported interaction
    mode the skill can READ rather than guess — which is a new mechanism and therefore
    an operator decision, tracked separately.

    So: if this test fails, the wording drifted back. It never asserted the stall was
    fixed, and a future reader should not infer that it was.
    """
    body = _body(read(FORGE_INIT))
    assert "not** whether a structured tool is present" in body, (
        "forge-init no longer disambiguates the rung-2 test from tool presence, and is "
        "back to contradicting the ladder's own per-host detection table"
    )
    for headless in ("-p", "--mode json", "codex exec"):
        assert headless in body, (
            f"forge-init no longer names {headless!r} as a rung-3 invocation"
        )
    assert "never emit a question a rung-3 run cannot answer" in body, (
        "the rung assessment is scoped to one question again, not to the whole skill"
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
    assert "forge-init" in text, "no recovery path when the root file is absent"


def _write_hygiene_docstring() -> str:
    """`write_hygiene`'s docstring, resolved by parsing rather than by string slicing.

    A `split('def write_hygiene(')[1].split('\"\"\"')[1]` slice silently retargets to the
    NEXT function's docstring if this one is ever deleted — passing or failing on
    unrelated text. Parsing fails loudly instead.
    """
    import ast

    tree = ast.parse(read(BOOTSTRAP_SCRIPT))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "write_hygiene":
            doc = ast.get_docstring(node)
            assert doc, "write_hygiene has no docstring"
            return doc
    raise AssertionError("write_hygiene not found in scripts/forge-bootstrap.py")


def test_bootstrap_records_the_real_anti_duplication_mechanism() -> None:
    """The docstring names the mechanism that actually fires, not the obvious one.

    `_write_artifact`'s never-overwrite guard reads like the thing that keeps
    forge-init and forge-bootstrap from duplicating each other's block. It is not:
    a forge-init'd target holds `forge.config.json`, which `ALLOWED_META_FILE_RE`
    does not permit, so the greenfield gate refuses the run before `write_hygiene`
    is ever reached. Documenting the wrong mechanism is worse than documenting none —
    it invites someone to relax the gate believing the guard has them covered.
    """
    doc = _write_hygiene_docstring()
    assert "forge-init" in doc
    assert "greenfield gate" in doc, (
        "the docstring credits the never-overwrite guard with an interop the "
        "greenfield gate actually provides"
    )
    assert "REQ-LIFE-02" in doc, "the guard's real remaining role is unstated"
    assert 'Root Hygiene (Tooling Feedback)' in doc, (
        "cites shared-conventions.md without naming the section — the same "
        "by-title rule this module enforces for forge-init"
    )


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


def test_specs_hygiene_agents_variant_names_no_claude_only_command() -> None:
    """The AGENTS variant ships to Copilot/Cursor/Gemini, which have no `/feature-forge:`.

    `references/templates/` is exempt from the reference host-term pass, so whatever
    this file says reaches a non-Claude user verbatim — and Copilot has no skills
    loader or slash-command namespace at all. The CLAUDE variant may name the command
    (it is only ever written on the Claude host); its AGENTS sibling may not. The
    root-hygiene templates added by this same phase already draw the line this way.
    """
    text = read(SPECS_HYGIENE_DIR / "AGENTS.md")
    assert "/feature-forge:" not in text, (
        "specs-hygiene/AGENTS.md names a Claude-only slash command in project content "
        "shipped verbatim to hosts that have no such command"
    )
    assert "/feature-forge:" in read(SPECS_HYGIENE_DIR / "CLAUDE.md"), (
        "the Claude variant lost the command it is entitled to name"
    )
