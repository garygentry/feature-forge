"""Guard test: no leaked Claude-only token or broken grammar in non-Claude adapters.

Chunk B of the plugin-QA remediation, extended by #167. The generator
(scripts/build-adapters.py) degrades Claude-native tool names to host-neutral
phrasing when emitting the codex/copilot/cursor/gemini adapters (see
``_HOST_TERM_REPLACEMENTS`` / ``translate_host_terms``), and — since #167 — runs
the same per-agent pass over the copied ``references/`` closure
(``_translate_reference_host_terms``). This test locks that contract for the
*committed* adapter trees: it walks every non-Claude skill **body** AND every
bundled **reference** markdown file and asserts none of the Claude-only tokens or
the double-article grammar bug survive.

Scope (deliberate):
- Non-Claude targets only — ``claude/`` is authored-verbatim by design (its
  references stay byte-identical to canon; tests/test_build_adapters.py pins that).
- Pi is scanned with its OWN token set: the Pi bundle ships an ``AskUserQuestion``
  compatibility extension, so that token is legitimate there — but Claude's
  ``/clear`` and ``/feature-forge:`` must have degraded to Pi's real ``/new`` /
  ``/skill:`` commands everywhere, references included.
- The #167 translation-exempt reference files (``templates/`` scaffolding,
  ``vendor-construct-inventory.md``, ``portable-root.md``) are scanned WITHOUT
  exemption: they carry zero forbidden tokens today, so an edit that introduces
  one surfaces here as an explicit decision instead of silent drift.

Stdlib-only (no yaml, no generator subprocess) so it runs under bare
``pytest tests`` regardless of the ``.venv-adapters`` provisioning state. It reads
the committed output rather than regenerating, so a hand-edit that reintroduces a
token is caught too, not only a generator regression.
"""

from __future__ import annotations

from pathlib import Path

import json
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ADAPTERS_ROOT = REPO_ROOT / "adapters"
NON_CLAUDE_TARGETS = ("codex", "copilot", "cursor", "gemini")  # 00 §1 minus claude & pi

# Tokens that must NOT appear in a non-Claude, non-Pi skill body or bundled
# reference. Each is either a literal Claude tool name that the host-term pass is
# supposed to degrade, a Claude-only slash command, or the double-article grammar
# the article-aware pairs kill.
FORBIDDEN_TOKENS: tuple[str, ...] = (
    "the the ",          # double-article (lowercase)
    "The the ",          # double-article (sentence start)
    "`Agent` tool",      # literal Claude subagent tool (backticked)
    "`Skill` tool",      # literal Claude skill-invocation tool (backticked)
    "`Monitor` tool",    # literal Claude monitoring tool (backticked)
    "/clear",            # Claude-only slash command (must degrade to plain prose)
    "AskUserQuestion",   # literal Claude question tool
)

# Pi keeps `AskUserQuestion` (the bundle ships a compatibility extension) and the
# generic tool degradations, but Claude's slash commands must have become Pi's
# real commands (`/new`, `/skill:`) — in bodies AND in the reference closure.
PI_FORBIDDEN_TOKENS: tuple[str, ...] = (
    "the the ",
    "The the ",
    "/clear",              # Pi's fresh-session command is /new
    "/feature-forge:",     # Pi's skill-invocation prefix is /skill:
    # forge-5-loop's Claude-shaped supervision lifecycle tokens: on Pi these are
    # degraded to the forge-loop-supervisor extension's surface (#235/#236), so a
    # literal one surviving means the Pi host-term pass regressed. (Still present
    # in the OTHER non-Claude agents, which have no supervisor extension — hence
    # Pi-only here, not in FORBIDDEN_TOKENS.)
    "`PushNotification`",
    "`TaskStop`",
    "`persistent: true`",
)


def _scan_paths(target: str) -> list[Path]:
    """Every committed skill body AND reference markdown of one adapter target.

    Walks ``skills/`` (bodies + skill-local ``references/``, both in scope since
    #167) and the bundle-root ``references/`` closure.
    """
    paths: list[Path] = []
    for subdir in ("skills", "references"):
        tree = ADAPTERS_ROOT / target / subdir
        if not tree.is_dir():
            continue
        for path in sorted(tree.rglob("*")):
            if path.suffix in (".md", ".mdc"):
                paths.append(path)
    return paths


def _cases() -> list[tuple[Path, tuple[str, ...]]]:
    cases = [(p, FORBIDDEN_TOKENS) for t in NON_CLAUDE_TARGETS for p in _scan_paths(t)]
    cases += [(p, PI_FORBIDDEN_TOKENS) for p in _scan_paths("pi")]
    return cases


def test_scan_surface_discovered() -> None:
    """Sanity guard: the walk finds files so the token assertion can't pass vacuously."""
    for target in (*NON_CLAUDE_TARGETS, "pi"):
        paths = _scan_paths(target)
        bodies = [p for p in paths if "references" not in p.parts]
        refs = [p for p in paths if "references" in p.parts]
        assert len(bodies) >= 5, (
            f"{target}: expected at least ~one skill body per skill; the adapter "
            f"tree looks unbuilt or the glob is wrong (found {len(bodies)})"
        )
        assert len(refs) >= 10, (
            f"{target}: expected the bundled reference closure in scope (#167); "
            f"found only {len(refs)} reference markdown files"
        )


def test_pi_forge_5_loop_supervises_via_extension_not_foreground() -> None:
    """Pi forge-5-loop drives the loop through the bundled forge-loop-supervisor
    extension — no foreground, no background/foreground contradiction (#235/#236).

    The generic contract is Claude-shaped (background the process, arm a Monitor,
    PushNotification on exceptions). Pi has no such surface, so the generated
    skill must (a) name the concrete registered tools, and (b) NOT carry the old
    overlay's affirmative "run long-lived commands in the foreground" instruction,
    which contradicted the body's own "background it" (the exact defect #235
    reported). The prohibition "Never run the run command in the foreground" is
    fine — that is the anti-pattern, not an instruction to foreground.
    """
    skill = ADAPTERS_ROOT / "pi" / "skills" / "forge-5-loop" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")

    for tool in ("forge_loop_launch", "forge_loop_status", "forge_loop_stop"):
        assert tool in text, f"Pi forge-5-loop must name the concrete supervision tool {tool!r}"
    assert "forge-loop-supervisor" in text, "the overlay must name the supervision extension"

    for banned in (
        "run long-lived commands in the foreground",
        "in the foreground and report progress",
    ):
        assert banned not in text, (
            f"Pi forge-5-loop still carries the removed foreground instruction {banned!r} "
            f"— it contradicts the body's background/supervise contract (#235). Fix "
            f"`_HOST_NOTES_PI` in scripts/build-adapters.py and rebuild adapters."
        )

    # The redirect must PRECEDE the manual launch prose, not merely appear somewhere
    # (the appended overlay alone left the operative Steps 3b-3f still describing the
    # Claude-shaped manual path — the contradiction the self-review caught). Assert
    # `forge_loop_launch` is introduced under the Step 3b header BEFORE the
    # "Launch the loop backgrounded" manual instruction.
    anchor = "### 3b. Launch Background Process"
    assert anchor in text, "the Step 3b header anchor moved — update the Pi redirect injection"
    after_3b = text.split(anchor, 1)[1]
    launch_pos = after_3b.find("forge_loop_launch")
    manual_pos = after_3b.find("Launch the loop **backgrounded**")
    assert launch_pos != -1, "forge_loop_launch must be introduced at Step 3b"
    assert manual_pos == -1 or launch_pos < manual_pos, (
        "the forge_loop_launch redirect must come BEFORE the manual 'background it' "
        "prose at Step 3b, so the model reads the authoritative tool instruction first "
        "(#235). Fix inject_pi_supervise_redirect in scripts/build-adapters.py."
    )

    # The runner-contract reference must front-load the same redirect (the manual
    # launch/monitor recipe lives here too), so forge_loop_launch appears near the top.
    contract = ADAPTERS_ROOT / "pi" / "skills" / "forge-5-loop" / "references" / "runner-contract.md"
    ctext = contract.read_text(encoding="utf-8")
    assert "forge_loop_launch" in ctext[:800], (
        "the Pi runner-contract must front-load the forge_loop_launch redirect, ahead "
        "of the manual launch/monitor detail (#235/#236)."
    )


@pytest.mark.parametrize(
    ("path", "forbidden"),
    _cases(),
    ids=lambda v: str(v.relative_to(ADAPTERS_ROOT)) if isinstance(v, Path) else "",
)
def test_no_leaked_host_token(path: Path, forbidden: tuple[str, ...]) -> None:
    """No non-Claude body or bundled reference carries a leaked Claude token."""
    text = path.read_text(encoding="utf-8")
    leaked = [tok for tok in forbidden if tok in text]
    assert not leaked, (
        f"{path.relative_to(REPO_ROOT)} leaks host-neutral-degradation token(s) "
        f"{leaked!r}. Fix scripts/build-adapters.py `_HOST_TERM_REPLACEMENTS` / "
        f"`_translate_reference_host_terms` and rebuild adapters — do not "
        f"hand-edit adapters/."
    )


#: #244 P2 (#252): the Interaction Capability Ladder's canonical title, checked against
#: the bundled shared-conventions.md of every target.
_LADDER_TITLE = "Interaction Capability Ladder"

#: The Pi rung-3 backstop error, verbatim — must survive translation unmangled since it
#: is a literal string a Pi agent matches against, not prose paraphrased per host.
_PI_RUNG3_ERROR_LITERAL = "Error: UI not available (running in non-interactive mode)"


@pytest.mark.parametrize("target", NON_CLAUDE_TARGETS)
def test_ladder_title_present_in_neutral_bundle(target: str) -> None:
    """Every non-Claude, non-Pi bundle's shared-conventions.md names the ladder by title.

    The ladder generalizes across hosts precisely because every prompting surface points
    at one canonical section instead of restating rung-3 behavior locally — a bundle that
    lost the section itself (a fan-out regression, not a token leak) would defeat that
    without tripping `test_no_leaked_host_token` at all.
    """
    path = ADAPTERS_ROOT / target / "references" / "shared-conventions.md"
    assert path.is_file(), f"{target} bundle is missing references/shared-conventions.md"
    text = path.read_text(encoding="utf-8")
    assert _LADDER_TITLE in text, (
        f"{path.relative_to(REPO_ROOT)} no longer carries '{_LADDER_TITLE}' — the "
        f"{target} bundle would have no canonical rung-3 doctrine to point at"
    )
    assert "AskUserQuestion" not in text, (
        f"{path.relative_to(REPO_ROOT)} leaks the literal AskUserQuestion token in its "
        "ladder section — already covered by test_no_leaked_host_token, restated here "
        "so a ladder-specific regression reads as a ladder failure, not a generic one"
    )


def test_ladder_title_and_pi_literals_present_in_pi_bundle() -> None:
    """The Pi bundle keeps both the ladder title AND the literal rung-3 vocabulary.

    Pi is the one target that must NOT degrade `AskUserQuestion` (it ships a real
    compatibility tool by that name) — this is the positive-presence counterpart to
    `PI_FORBIDDEN_TOKENS`, which only checks what must be ABSENT.
    """
    path = ADAPTERS_ROOT / "pi" / "references" / "shared-conventions.md"
    assert path.is_file(), "pi bundle is missing references/shared-conventions.md"
    text = path.read_text(encoding="utf-8")
    assert _LADDER_TITLE in text, (
        f"{path.relative_to(REPO_ROOT)} no longer carries '{_LADDER_TITLE}'"
    )
    assert "AskUserQuestion" in text, (
        f"{path.relative_to(REPO_ROOT)} lost the literal AskUserQuestion token in its "
        "ladder section — Pi's compatibility extension registers a real tool by this "
        "name, so degrading it here would misdescribe Pi's actual rung-1 mechanism"
    )
    assert _PI_RUNG3_ERROR_LITERAL in text, (
        f"{path.relative_to(REPO_ROOT)} lost the Pi rung-3 backstop error literal "
        f"{_PI_RUNG3_ERROR_LITERAL!r} — a Pi agent matches this string to distinguish "
        "a non-interactive stripped-tool failure from a genuine user decline"
    )


#: The `## Root Hygiene` section title (#244 P3). Like the ladder, it is a title every
#: pointer cites, so a bundle that lost the section leaves those pointers dangling.
_ROOT_HYGIENE_TITLE = "## Root Hygiene (Tooling Feedback)"

#: The two project-root templates forge-init copies. They are `templates/` scaffolding —
#: `_reference_translation_exempt` deliberately skips the host-term pass over them, since
#: they are project content a user reads, not agent-facing guidance.
_ROOT_HYGIENE_TEMPLATES = ("AGENTS.md", "CLAUDE.md")

_ALL_TARGETS = ("claude", "pi") + NON_CLAUDE_TARGETS


@pytest.mark.parametrize("target", _ALL_TARGETS)
def test_root_hygiene_section_present_in_every_bundle(target: str) -> None:
    """Every bundle's shared-conventions.md keeps the Root Hygiene section.

    forge-init points at it by title on every host; a bundle that lost the section
    (a fan-out or translation regression, not a token leak) would leave forge-init
    citing a contract its own bundle cannot show — invisible to the token scan.
    """
    path = ADAPTERS_ROOT / target / "references" / "shared-conventions.md"
    assert path.is_file(), f"{target} bundle is missing references/shared-conventions.md"
    assert _ROOT_HYGIENE_TITLE in path.read_text(encoding="utf-8"), (
        f"{path.relative_to(REPO_ROOT)} no longer carries '{_ROOT_HYGIENE_TITLE}' — "
        f"forge-init's tooling-feedback step would point at nothing on {target}"
    )


@pytest.mark.parametrize("target", _ALL_TARGETS)
@pytest.mark.parametrize("filename", _ROOT_HYGIENE_TEMPLATES)
def test_root_hygiene_template_ships_untranslated(target: str, filename: str) -> None:
    """The copied root-hygiene template carries no host-term degradation.

    It is `cp`-ed verbatim into a user's repo, so a host-term substitution would ship
    degraded prose into project content. `templates/` is exempt from
    `_translate_reference_host_terms` for exactly this reason, and this asserts the
    exemption still holds for the new subtree: byte-identical to canon everywhere.

    Pi is the one sanctioned exception, and it is a *correct* one — the Pi pass rewrites
    `/feature-forge:` to `/skill:` bundle-wide, and a template landing in a Pi-driven
    project should name the command that project actually has. The assertion is
    therefore "identical once that one substitution is undone", which is strictly
    stronger than skipping Pi: any OTHER divergence still fails.
    """
    rel = Path("references") / "templates" / "root-hygiene" / filename
    shipped = ADAPTERS_ROOT / target / rel
    canon = REPO_ROOT / rel
    assert shipped.is_file(), f"{target} bundle is missing {rel.as_posix()}"
    text = shipped.read_text(encoding="utf-8")
    if target == "pi":
        text = text.replace("/skill:", "/feature-forge:")
    assert text == canon.read_text(encoding="utf-8"), (
        f"{shipped.relative_to(REPO_ROOT)} diverges from canon — project-content "
        "templates must ship verbatim (build-adapters.py `_reference_translation_exempt`)"
    )


# --------------------------------------------------------------------------- #
# #244 P3.5 (#261): the rung is DATA a skill reads, on every first-class host
# --------------------------------------------------------------------------- #

#: The check id and launcher contract the ladder tells every host to read.
_INTERACTION_CHECK_ID = "interaction-mode"
_INTERACTION_ENV_VAR = "FORGE_INTERACTION"


@pytest.mark.parametrize("target", ("claude", "pi") + NON_CLAUDE_TARGETS)
def test_ladder_points_every_bundle_at_the_interaction_record(target: str) -> None:
    """Every bundle's ladder names the check that supplies the rung.

    Without this the ladder is back to asking for a self-assessment no model can
    make (#261): five headless runs across two hosts each guessed "interactive"
    and stalled. The pointer, not the prose, is what made rung 3 reachable.
    """
    text = (ADAPTERS_ROOT / target / "references" / "shared-conventions.md").read_text(
        encoding="utf-8",
    )
    assert _INTERACTION_CHECK_ID in text, (
        f"{target}'s bundled ladder no longer names the `{_INTERACTION_CHECK_ID}` check "
        "— the rung would fall back to a self-assessment that is measurably wrong"
    )
    assert _INTERACTION_ENV_VAR in text, (
        f"{target}'s bundled ladder lost the `{_INTERACTION_ENV_VAR}` launcher contract "
        "— the only signal that reaches a host with no observable one"
    )
    assert "`unknown` is never" in text, (
        f"{target}'s bundled ladder lost the rule that undetermined is NEVER read as "
        "headless — guessing headless makes an interactive run skip its questions"
    )


@pytest.mark.parametrize("target", ("codex",) + NON_CLAUDE_TARGETS)
def test_host_overlay_defers_the_rung_to_the_record_not_to_self_judgement(
    target: str,
) -> None:
    """The overlays' own rung instruction points at the record.

    Codex is the pointed case: its overlay used to say "under `codex exec` … take
    the conservative default", which is unreachable — run 5 of #261 had Codex
    report `rung 2 (interactive Codex)` *while running under `codex exec`*. An
    overlay that asks a Codex agent to judge its own mode is inert by construction.
    """
    skill_dir = ADAPTERS_ROOT / target / "skills" / "forge-init"
    # Bundles differ in the emitted filename (SKILL.md vs <name>.md) — take whichever
    # this target emits rather than hardcoding one layout.
    candidates = sorted(p for p in skill_dir.iterdir() if p.suffix in (".md", ".mdc"))
    assert candidates, f"{target} bundle has no forge-init skill file"
    overlay = candidates[0].read_text(encoding="utf-8")
    assert "Host execution notes" in overlay, f"{target}/forge-init lost its host overlay"
    assert _INTERACTION_CHECK_ID in overlay, (
        f"{target}'s host overlay no longer defers the rung to the "
        f"`{_INTERACTION_CHECK_ID}` record"
    )


def test_codex_overlay_states_the_rung_is_not_self_observable() -> None:
    """Codex's overlay says *why* it must read the record, not just that it should.

    The failure mode is a confident wrong answer, not a missing one, so the overlay
    has to contradict the agent's intuition explicitly.
    """
    overlay = next(
        (ADAPTERS_ROOT / "codex" / "skills" / "forge-init").glob("*.md")
    ).read_text(encoding="utf-8")
    assert "not** observable from inside the session" in overlay, (
        "the Codex overlay no longer states that the rung is unobservable from inside "
        "the session — a Codex agent that trusts its own read reports rung 2 under "
        "`codex exec` (measured, #261 run 5)"
    )


def test_the_interaction_record_is_reachable_from_every_bundle() -> None:
    """Each bundle ships the script whose check the ladder tells it to run.

    The ladder's pointer is only as good as the copy of `forge-session.py` beside
    it; a bundle missing the check would send its agent to a command that exits 2.
    """
    for target in ("claude", "pi") + NON_CLAUDE_TARGETS:
        script = ADAPTERS_ROOT / target / "scripts" / "forge-session.py"
        assert script.is_file(), f"{target} bundle is missing scripts/forge-session.py"
        source = script.read_text(encoding="utf-8")
        assert f'_make_spec("{_INTERACTION_CHECK_ID}"' in source, (
            f"{target}'s bundled forge-session.py has no `{_INTERACTION_CHECK_ID}` check, "
            "so its ladder points at a command that cannot answer"
        )
        sentinel = ADAPTERS_ROOT / target / ".feature-forge-bundle.json"
        assert json.loads(sentinel.read_text(encoding="utf-8"))["agent"] == target, (
            f"{target}'s bundle sentinel does not name itself — the check reads this "
            "field for the host axis, so a wrong value misreports the host"
        )
