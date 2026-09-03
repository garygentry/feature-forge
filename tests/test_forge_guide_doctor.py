"""Guard: forge-guide's `--doctor` repair surface (#244 P4, #254).

PROTECTS:
  1. `skills/forge-guide/SKILL.md` carries a `--doctor` mode that cites
     `references/preflight-and-self-heal.md` by path (the literal citation is what
     `scripts/build-adapters.py` fans the reference into forge-guide's own bundle
     `references/` with — see `tests/test_reference_citations.py`) and the Interaction
     Capability Ladder by title.
  2. The carve-out is *narrowing*, not lifting: `local-write` only on an explicit yes,
     `global-install`/`network` advise-only, and the "never invokes stage skills" clause
     survives alongside the original advisory-only rule.
  3. The rung-3 outcome is report-only and **stated**, using the ladder's own literal.
  4. `argument-hint` offers `--doctor`; the `description:` is untouched, so the
     always-loaded frontmatter budget (4688, `tests/test_always_loaded_surface.py`) is
     unmoved — `argument-hint` is not part of that budget.
  5. The pointer wiring: forge-guide's first Troubleshooting starter and forge-5-loop's
     1c/1d STOP text both name the command, and forge-5-loop stays inside the caps P1
     measured it against.
  6. Every generated bundle renders the command in its own host's dialect
     (`/skill:forge-guide --doctor` on Pi, `/feature-forge:…` elsewhere).

NON-GOALS:
  - Runtime behavior of the mode. Nothing here executes a skill; that is the live
    headless smoke recorded in `plans/federated-bubbling-micali.md` § P4.
  - Re-testing the preflight procedure itself (`tests/test_preflight_self_heal.py`) or
    the ladder's own prose (`tests/test_interaction_ladder_prose.py`).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import pytest

from _forge_paths import REFERENCES, REPO_ROOT, SKILLS, read

FORGE_GUIDE: Final[Path] = SKILLS / "forge-guide" / "SKILL.md"
FORGE_5_LOOP: Final[Path] = SKILLS / "forge-5-loop" / "SKILL.md"
PREFLIGHT: Final[Path] = REFERENCES / "preflight-and-self-heal.md"
SHARED_CONVENTIONS: Final[Path] = REFERENCES / "shared-conventions.md"
DOCTOR_CHECKS_DOC: Final[Path] = REPO_ROOT / "docs" / "doctor-checks.md"
ADAPTERS_ROOT: Final[Path] = REPO_ROOT / "adapters"

#: The command as an operator types it on Claude. Pi's bundle rewrites the prefix.
COMMAND: Final[str] = "/feature-forge:forge-guide --doctor"

#: The ladder's literal rung-3 statement. Pinned as one string on purpose: P3.5's smoke
#: showed a host will paraphrase it unless canon spells it out (Codex phrased it
#: semantically until the exact literal was in front of it).
RUNG_3_LITERAL: Final[str] = (
    "interaction: rung 3 (non-interactive) — declared defaults\napply"
)

#: Clauses the carve-out must keep. Each is load-bearing: drop any one and the mode
#: reads as permission to write freely, which is the failure this phase exists to avoid.
CARVE_OUT_CLAUSES: Final[tuple[str, ...]] = (
    "`local-write`",
    "advise-only",
    "never invokes stage skills",
)


def _body(text: str) -> str:
    """The skill body with YAML frontmatter stripped — what the builder scans."""
    match = re.match(r"^---\n.*?\n---\n", text, re.DOTALL)
    return text[match.end() :] if match else text


def _frontmatter(text: str) -> str:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, f"{FORGE_GUIDE.name} has no YAML frontmatter"
    return match.group(1)


def _doctor_section(text: str) -> str:
    """The `## --doctor mode` section alone, so a clause elsewhere cannot vouch for it.

    Fence-aware on purpose: the section carries a ```bash block, and a naive
    `find("\\n## ")` would end the section early at any `## ` line that landed inside a
    fence — silently shrinking what every guard below inspects, which is a false pass
    rather than a failure.
    """
    body = _body(text)
    lines = body[body.index("## `--doctor` mode") :].split("\n")
    out, in_fence = [lines[0]], False
    for line in lines[1:]:
        if line.startswith("```"):
            in_fence = not in_fence
        elif not in_fence and line.startswith("## "):
            break
        out.append(line)
    return "\n".join(out)


# --------------------------------------------------------------------------------------
# Guard 1 — the mode exists and is grounded in the shared procedure
# --------------------------------------------------------------------------------------


def test_forge_guide_has_a_doctor_mode_section() -> None:
    assert "## `--doctor` mode" in _body(read(FORGE_GUIDE)), (
        "forge-guide lost its `## --doctor` mode heading — D1 put the repair surface on "
        "this skill precisely so it costs no new frontmatter; without the section the "
        "argument-hint advertises a mode with no instructions behind it"
    )


def test_doctor_mode_cites_the_preflight_reference_by_path() -> None:
    section = _doctor_section(read(FORGE_GUIDE))
    assert "references/preflight-and-self-heal.md" in section, (
        "the `--doctor` section no longer cites references/preflight-and-self-heal.md. "
        "The literal path is not decoration: build-adapters.py fans shared references "
        "into a skill's own references/ BY CITATION, so dropping it ships a bundle whose "
        "repair surface points at a file that is not beside it"
    )
    assert PREFLIGHT.is_file(), "the cited preflight reference itself is missing"


def test_doctor_mode_points_at_the_ladder_by_title() -> None:
    section = _doctor_section(read(FORGE_GUIDE))
    assert "Interaction Capability Ladder" in section, (
        "the `--doctor` section must name the Interaction Capability Ladder by title — "
        "canon's rule is that every prompting surface points at the one canonical "
        "statement rather than restating its rows"
    )
    assert "## Interaction Capability Ladder" in read(SHARED_CONVENTIONS), (
        "the ladder section this guard pins has moved or been renamed at the source"
    )


def test_doctor_mode_reads_the_interaction_mode_record_it_already_holds() -> None:
    """The full-catalog run carries the record, so the mode must not re-derive the rung."""
    section = _doctor_section(read(FORGE_GUIDE))
    assert "interaction-mode" in section and "evidence.mode" in section, (
        "the `--doctor` section must take the rung from the `interaction-mode` record in "
        "the report it just ran (P3.5's whole point: the rung is data a skill reads, "
        "never a fact it guesses)"
    )


# --------------------------------------------------------------------------------------
# Guard 2 — the carve-out narrows the never-write rule instead of lifting it
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("clause", CARVE_OUT_CLAUSES)
def test_carve_out_keeps_every_load_bearing_clause(clause: str) -> None:
    section = _doctor_section(read(FORGE_GUIDE))
    assert clause in section, (
        f"the `--doctor` carve-out dropped {clause!r}. The carve-out is only safe while "
        "it is narrower than the rule it excepts: read-only doctor always, local-write "
        "on an explicit yes, global-install/network never, stage skills never"
    )


def test_the_advisory_only_rule_still_stands_outside_doctor_mode() -> None:
    body = _body(read(FORGE_GUIDE))
    assert "Do NOT actually invoke stage skills or write files" in body, (
        "forge-guide's advisory-only rule is gone — `--doctor` was specified as a "
        "carve-out FROM that rule, so deleting the rule turns a narrow exception into "
        "blanket write permission for every invocation"
    )


def test_doctor_mode_is_entered_only_on_the_explicit_argument() -> None:
    """Pin the gating sentence, not two words that appear all over the section.

    `"only" in section and "--doctor" in section` was the first draft and it was
    tautological: the heading alone satisfies the second clause and "only" occurs in the
    carve-out, so deleting the gate entirely left the test green.
    """
    normalized = " ".join(_doctor_section(read(FORGE_GUIDE)).split())
    assert "Enter this mode **only** when the argument is `--doctor`" in normalized, (
        "the `--doctor` section lost its entry gate. Without it an ordinary advisory "
        "invocation (`forge-guide troubleshoot`) can read on into a mode that is "
        "permitted to write"
    )


def test_the_entry_gate_guard_is_not_satisfied_by_stray_words() -> None:
    """Non-vacuity for the guard above: the loose form it replaced passes on junk."""
    junk = "## `--doctor` mode\nrun it only when you like, --doctor is a flag.\n"
    assert "only" in junk and "--doctor" in junk  # the old assertion — passes
    assert "Enter this mode **only** when the argument is `--doctor`" not in junk


def test_read_only_remedies_are_named_as_the_unprompted_tier() -> None:
    """All four tiers must be partitioned where the agent acts, not 30 lines above it.

    `read-only` clusters are never prompted and simply run (preflight §2 step 3); a step
    that says "ask one question per cluster" without that partition tells the agent to
    prompt for a tier that must not be prompted — and, worse, to prompt for
    `global-install`/`network`, which a yes could then be read as authorizing.
    """
    section = _doctor_section(read(FORGE_GUIDE))
    for token in ("`read-only` runs unprompted", "global-install", "network", "advise-only"):
        assert token in section, (
            f"step 4's tier partition dropped {token!r} — the safety ladder's four tiers "
            "must be resolved in the sentence that acts on them"
        )


def test_checkout_and_pipeline_state_remedies_are_excluded_from_apply() -> None:
    """The carve-out promises this skill never edits `.pipeline-state.json`.

    `branch-state` emits two `local-write` remedies that break that promise if applied:
    `git switch <branch>` rewrites the working tree (and is not idempotent, which the
    tier assumes), and `state-branch --feature … --branch …` writes the feature's
    `.pipeline-state.json`. Both are reachable only here, because this is the only caller
    that runs the full catalog.
    """
    section = _doctor_section(read(FORGE_GUIDE))
    normalized = " ".join(section.split())
    assert "Excluded from apply" in section, (
        "the `--doctor` section dropped its exclusion rule — with the full catalog in "
        "scope, an approved `branch-state` remedy would switch the operator's branch or "
        "rewrite a feature's recorded branch, contradicting the carve-out two paragraphs up"
    )
    for command in ("git switch", "state-branch"):
        assert command in normalized, (
            f"the exclusion no longer names {command!r} — naming today's instances is what "
            "makes the rule checkable against the registry"
        )


def test_consent_does_not_persist_across_doctor_invocations() -> None:
    """The ladder's once-per-session memo would otherwise apply on a second look.

    `local-write` asks "once per distinct `remedy.command` per session", written for a
    gate that runs once per launch. `--doctor` is operator-typed and its advertised
    output is a report, so a second invocation must not silently re-apply a remedy the
    first one was told to run.
    """
    section = _doctor_section(read(FORGE_GUIDE))
    assert "Consent does not persist across invocations" in section, (
        "the `--doctor` section no longer overrides the once-per-session consent memo: "
        "an operator running `--doctor` twice to *look* at the report would have the "
        "remedy re-applied with no question asked"
    )


def test_unknown_mode_is_not_treated_as_rung_3() -> None:
    """`unknown` is the common Codex answer, not a corner case.

    P3.5 excludes Codex from ancestry detection, so an unstamped `codex exec` always
    reports `mode: unknown`. Reading that as rung 3 is the silent behavior change the
    ladder forbids; leaving it unhandled is the stall P4 exists to prevent.
    """
    section = _doctor_section(read(FORGE_GUIDE))
    normalized = " ".join(section.split())
    assert "`unknown` is never rung 3" in normalized, (
        "step 3 no longer says what `unknown` means. The ladder's table says self-assess "
        "and prefer rung 2's prose question; a section that names only the rung-3 branch "
        "leaves the most common Codex answer with no instruction at all"
    )
    assert "evidence.conflict" in normalized, (
        "step 3 dropped the conflict case — P3.5 resolves two contradicting signals to "
        "`warn` + `unknown` precisely so a leaked env stamp cannot silence questions"
    )


def test_the_affected_set_is_warn_or_fail_never_na() -> None:
    """`na` is not a finding; rendering it as one breaks INV-2 on a healthy project."""
    section = _doctor_section(read(FORGE_GUIDE))
    normalized = " ".join(section.split())
    assert "`na` is not a finding" in normalized, (
        "the `--doctor` section must exclude `na` from the affected set (preflight §2 "
        "step 1 defines it as `warn` or `fail`). This repo reports `backlog-valid` as "
        "`na` while healthy — rendering it as a finding and closing with 'the command "
        "that would clear it' names a command that does not exist"
    )


# --------------------------------------------------------------------------------------
# Guard 3 — rung 3 is report-only, and says so in the ladder's own words
# --------------------------------------------------------------------------------------


def test_rung_3_is_report_only_and_states_the_ladders_literal() -> None:
    section = _doctor_section(read(FORGE_GUIDE))
    normalized = " ".join(section.split())
    expected = " ".join(RUNG_3_LITERAL.split())
    assert expected in normalized, (
        "the `--doctor` section must carry the ladder's exact rung-3 statement "
        f"({expected!r}). A host paraphrases it when canon does not spell it out — "
        "measured in P3.5's smoke — and a paraphrase is not a verifiable exit criterion"
    )
    assert "unaskable→advise-only" in section, (
        "a rung-3 `--doctor` run must record each local-write cluster as "
        "`unaskable→advise-only` (preflight-and-self-heal.md §2 step 4's outcome token)"
    )


def test_the_rung_3_literal_still_matches_the_ladder_at_the_source() -> None:
    """Non-vacuity: this guard is only meaningful while it pins the ladder's own words."""
    normalized_ladder = " ".join(read(SHARED_CONVENTIONS).split())
    assert " ".join(RUNG_3_LITERAL.split()) in normalized_ladder, (
        "the literal pinned here no longer appears in shared-conventions.md — the "
        "ladder's statement changed at the source and this guard is now pinning a "
        "string canon does not use"
    )


# --------------------------------------------------------------------------------------
# Guard 4 — argument-hint advertises it; the frontmatter budget does not move
# --------------------------------------------------------------------------------------


def test_argument_hint_offers_doctor() -> None:
    assert "--doctor" in _frontmatter(read(FORGE_GUIDE)), (
        "forge-guide's argument-hint no longer offers `--doctor` — the mode is "
        "undiscoverable from the skill's own surface"
    )


def test_description_does_not_mention_doctor() -> None:
    """`description:` is the always-loaded surface; `argument-hint` is not (REQ-PERF-02)."""
    match = re.search(r'^description:\s*(.+)$', _frontmatter(read(FORGE_GUIDE)), re.MULTILINE)
    assert match, "forge-guide has no description:"
    assert "--doctor" not in match.group(1), (
        "the `--doctor` mode was advertised in `description:`, which is loaded into every "
        "session for every skill and is budgeted at 4688 chars total "
        "(tests/test_always_loaded_surface.py). D1 chose forge-guide precisely because "
        "`argument-hint` carries the hint at zero always-loaded cost"
    )


# --------------------------------------------------------------------------------------
# Guard 5 — the pointers that make the mode reachable
# --------------------------------------------------------------------------------------


def test_troubleshooting_starters_lead_with_the_command() -> None:
    body = _body(read(FORGE_GUIDE))
    starters = body[body.index("## Troubleshooting starters") :]
    first_bullet = next(line for line in starters.splitlines() if line.startswith("- "))
    assert COMMAND in first_bullet, (
        "the first Troubleshooting starter must be the repair command; a reader who "
        f"reaches this section has already told us something is wrong. Got: {first_bullet!r}"
    )


def test_forge_5_loop_gate_points_at_the_repair_surface() -> None:
    body = _body(read(FORGE_5_LOOP))
    assert COMMAND in body, (
        "forge-5-loop's 1c/1d STOP text no longer names the repair surface — a hard gate "
        "that stops without naming the one command that clears it is the dead end #244 "
        "set out to remove"
    )


def test_forge_5_loop_gate_slice_stayed_within_the_pre_p1_budget() -> None:
    """The pointer spends words P1 freed; it must not spend more than P1 freed."""
    lines = _body(read(FORGE_5_LOOP)).split("\n")
    start = next(i for i, line in enumerate(lines) if line.startswith("### 1c."))
    end = next(i for i, line in enumerate(lines) if line.startswith("### 1e."))
    slice_ = lines[start:end]
    n_words = sum(len(line.split()) for line in slice_)
    assert len(slice_) <= 26, f"1c→1e slice grew to {len(slice_)} lines (was 26 pre-P1)"
    assert n_words <= 329, f"1c→1e slice grew to {n_words} words (was 329 pre-P1)"


def test_docs_catalog_links_the_repair_surface() -> None:
    assert COMMAND in read(DOCTOR_CHECKS_DOC), (
        "docs/doctor-checks.md no longer names the repair surface — the catalog page is "
        "where an operator lands after reading a report, and it should say what to run"
    )


# --------------------------------------------------------------------------------------
# Guard 6 — every bundle renders the command in its own host's dialect
# --------------------------------------------------------------------------------------


def _bundle_guide(target: str) -> Path:
    """forge-guide's body in a built bundle.

    Three layouts ship: `SKILL.md` (claude/codex/pi), `<skill>/<skill>.md`
    (copilot/gemini) and `<skill>/<skill>.mdc` (cursor's rule format). Resolving all
    three matters — a helper that only knew the first would `skip` on half the targets,
    and a guard that skips is a guard that asserts nothing. `adapters/` is committed, so
    a missing file here is a real failure (rebuild with
    `python3 scripts/build-adapters.py`), never a reason to skip.
    """
    skill_dir = ADAPTERS_ROOT / target / "skills" / "forge-guide"
    for name in ("SKILL.md", "forge-guide.md", "forge-guide.mdc"):
        candidate = skill_dir / name
        if candidate.is_file():
            return candidate
    raise AssertionError(
        f"no forge-guide body in the {target} bundle ({skill_dir}) — adapters/ is "
        "committed and regenerated by scripts/build-adapters.py; rebuild it"
    )


#: Every built bundle. `claude` belongs here too — leaving it out asserted the command
#: literal on five of six hosts and let the drift guard vouch for the sixth by implication.
BUNDLE_TARGETS: Final[tuple[str, ...]] = (
    "claude", "codex", "copilot", "cursor", "gemini", "pi",
)


@pytest.mark.parametrize("target", ("claude", "codex", "copilot", "cursor", "gemini"))
def test_non_pi_bundles_keep_the_command_prefix(target: str) -> None:
    assert COMMAND in _bundle_guide(target).read_text(encoding="utf-8"), (
        f"the {target} forge-guide bundle lost `{COMMAND}` — the host-term pass rewrites "
        "only Pi's slash-command prefix, so every other target keeps canon's spelling"
    )


@pytest.mark.parametrize("target", BUNDLE_TARGETS)
def test_every_bundle_carries_the_doctor_section_itself(target: str) -> None:
    """The command string alone is not proof the mode shipped.

    `/feature-forge:forge-guide --doctor` also appears in the Troubleshooting starter, so
    a bundle that lost the whole `## --doctor mode` section would still satisfy the
    command-prefix guards above.
    """
    text = _bundle_guide(target).read_text(encoding="utf-8")
    assert "## `--doctor` mode" in text, (
        f"the {target} bundle carries the command but not the section that defines it — "
        "an agent would be pointed at a mode with no instructions behind it"
    )


@pytest.mark.parametrize("target", BUNDLE_TARGETS)
def test_every_bundle_fans_the_preflight_reference_beside_forge_guide(target: str) -> None:
    """The citation must actually deliver the file, not just name it.

    forge-guide reads `references/preflight-and-self-heal.md` as a bare relative path, so
    on the npm-installer Claude layout (no `${CLAUDE_PLUGIN_ROOT}`) only the skill-local
    copy resolves — the #122 degradation the by-citation fan-out exists to prevent.
    `adapters/` is committed, so a missing bundle is a failure, not a skip.
    """
    fanned = _bundle_guide(target).parent / "references" / "preflight-and-self-heal.md"
    assert fanned.is_file(), (
        f"{target}: preflight-and-self-heal.md was not fanned into forge-guide's own "
        "references/ — the bare `references/…` path the body reads will not resolve "
        "from the skill dir on the non-plugin Claude layout"
    )


@pytest.mark.parametrize("target", BUNDLE_TARGETS)
def test_the_ladder_title_pointer_resolves_in_every_bundle(target: str) -> None:
    """Step 3 points at the ladder BY TITLE, so the title must survive translation.

    A title-pointer into a fanned file whose heading the host-term pass renamed is a dead
    instruction: the agent is told to go read a section that is not there.
    """
    fanned = _bundle_guide(target).parent / "references" / "shared-conventions.md"
    assert fanned.is_file(), f"{target}: shared-conventions.md is not beside forge-guide"
    assert "## Interaction Capability Ladder" in fanned.read_text(encoding="utf-8"), (
        f"{target}: the fanned shared-conventions.md no longer carries the ladder under "
        "the exact title the `--doctor` section points at"
    )


def test_pi_bundle_translates_the_command_to_its_own_prefix() -> None:
    text = _bundle_guide("pi").read_text(encoding="utf-8")
    assert "/skill:forge-guide --doctor" in text, (
        "the Pi bundle must render the repair command as `/skill:forge-guide --doctor`; "
        "Pi has no `/feature-forge:` prefix, so an untranslated command names nothing"
    )
    assert COMMAND not in text, (
        "the Pi bundle still carries the untranslated `/feature-forge:` command — "
        "build-adapters.py's `/feature-forge:` → `/skill:` substitution did not reach it"
    )
