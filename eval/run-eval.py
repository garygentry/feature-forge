#!/usr/bin/env python3
"""Advisory trigger-accuracy eval for feature-forge skills.

For each eval/fixtures/<skill>.json the harness asks a small Claude model to pick the
best-matching skill from the canonical skills/*/SKILL.md descriptions, then scores:
  - a shouldTrigger prompt is correct when the expected skill is chosen;
  - a shouldNotTrigger prompt is correct when the expected skill is NOT chosen.

Advisory only (REQ-EVAL-02): always exits 0 for a low score or an absent API key.
The only non-zero exit is a harness bug (bad fixture / unexpected error).

Usage:
    python3 eval/run-eval.py [--json]

Reads ANTHROPIC_API_KEY from the environment (REQ-SEC-02 — never hardcoded, never
echoed). When absent, prints "skipped (no key)" and exits 0.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Pinned, low-cost model (OQ-D). Date-suffixed Haiku id is intentional for a hard pin
# of an advisory job; see shared/models.md (claude-api skill).
MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 64  # the judge returns just a skill name; keep the cap tiny (OQ-D / cost)

REPO_ROOT = Path(__file__).resolve().parent.parent  # eval/ -> feature-forge/
SKILLS_DIR = REPO_ROOT / "skills"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

NONE_SENTINEL = "none"


@dataclass
class CaseResult:
    prompt: str
    kind: str  # "shouldTrigger" | "shouldNotTrigger"
    chosen: str
    correct: bool


@dataclass
class SkillResult:
    skill: str
    total: int = 0
    correct: int = 0
    accuracy: float = 0.0
    cases: list[CaseResult] = field(default_factory=list)


@dataclass
class Report:
    model: str
    skills: list[SkillResult] = field(default_factory=list)
    total_cases: int = 0
    total_correct: int = 0
    accuracy: float = 0.0
    skipped: bool = False
    skip_reason: str | None = None


def load_catalog() -> dict[str, str]:
    """Map skill name -> description from every skills/*/SKILL.md frontmatter."""
    catalog: dict[str, str] = {}
    for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        text = skill_md.read_text(encoding="utf-8")
        name = _frontmatter_value(text, "name") or skill_md.parent.name
        desc = _frontmatter_value(text, "description") or ""
        catalog[name] = desc
    return catalog


def _frontmatter_value(text: str, key: str) -> str | None:
    """Extract a scalar frontmatter value (quoted, plain, or block-scalar) for `key`.

    Tolerant by design: skill descriptions use ``"..."``, ``|-`` blocks, and plain
    forms across the suite. We only need name/description, so a focused parser avoids a
    PyYAML dependency (the adapter venv pins PyYAML, but the eval job does not install it).
    """
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    fm = text[3:end]
    # Quoted single-line: key: "value"
    m = re.search(rf'^{re.escape(key)}:\s*"(.*)"\s*$', fm, re.MULTILINE)
    if m:
        return m.group(1)
    # Block scalar: key: |- (or |, >-, >) then indented lines
    m = re.search(rf"^{re.escape(key)}:\s*[|>][+-]?\s*\n", fm, re.MULTILINE)
    if m:
        lines = fm[m.end() :].splitlines()
        block: list[str] = []
        for line in lines:
            if line and not line.startswith((" ", "\t")):
                break
            block.append(line.strip())
        return " ".join(s for s in block if s).strip()
    # Plain single-line: key: value
    m = re.search(rf"^{re.escape(key)}:\s*(.+?)\s*$", fm, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return None


def build_system_prompt(catalog: dict[str, str]) -> str:
    """The judge instructions + the candidate skill catalog (stable prefix)."""
    lines = [
        "You are a skill router. Given a user request, choose the SINGLE skill whose "
        "description best matches it, or 'none' if no skill is a good match.",
        "",
        "Respond with ONLY the skill name (e.g. forge-1-prd) or the word none. "
        "No punctuation, no explanation.",
        "",
        "Available skills:",
    ]
    for name, desc in catalog.items():
        lines.append(f"- {name}: {desc}")
    return "\n".join(lines)


def judge(client, system_prompt: str, prompt: str, valid: set[str]) -> str:
    """Ask the model to pick one skill; normalise to a known name or NONE_SENTINEL."""
    resp = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = "".join(b.text for b in resp.content if b.type == "text").strip()
    token = raw.split()[0].strip(".,:`\"'").lower() if raw else NONE_SENTINEL
    if token in valid:
        return token
    return NONE_SENTINEL


def score_fixture(client, system_prompt: str, fixture: dict, valid: set[str]) -> SkillResult:
    skill = fixture["skill"]
    if skill not in valid:
        raise ValueError(f"fixture skill {skill!r} is not a known skills/ directory")
    result = SkillResult(skill=skill)
    for kind in ("shouldTrigger", "shouldNotTrigger"):
        for prompt in fixture.get(kind, []):
            chosen = judge(client, system_prompt, prompt, valid)
            if kind == "shouldTrigger":
                correct = chosen == skill
            else:
                correct = chosen != skill
            result.cases.append(CaseResult(prompt, kind, chosen, correct))
            result.total += 1
            result.correct += int(correct)
    result.accuracy = (result.correct / result.total) if result.total else 0.0
    return result


def load_fixtures() -> list[dict]:
    if not FIXTURES_DIR.is_dir():
        return []
    fixtures = []
    for path in sorted(FIXTURES_DIR.glob("*.json")):
        fixtures.append(json.loads(path.read_text(encoding="utf-8")))
    return fixtures


def print_human(report: Report) -> None:
    if report.skipped:
        print(f"trigger-accuracy eval: skipped ({report.skip_reason})")
        return
    print(f"trigger-accuracy eval (model={report.model})")
    for sr in report.skills:
        pct = round(sr.accuracy * 100, 1)
        print(f"  {sr.skill}: {sr.correct}/{sr.total} ({pct}%)")
        for c in sr.cases:
            mark = "ok " if c.correct else "MISS"
            print(f"    [{mark}] {c.kind}: chose {c.chosen!r} <- {c.prompt!r}")
    overall = round(report.accuracy * 100, 1)
    print(f"OVERALL trigger-accuracy: {report.total_correct}/{report.total_cases} ({overall}%)")


def main(argv: list[str]) -> int:
    as_json = "--json" in argv

    if not os.environ.get("ANTHROPIC_API_KEY"):
        report = Report(model=MODEL, skipped=True, skip_reason="no ANTHROPIC_API_KEY")
        print(
            json.dumps(asdict(report))
            if as_json
            else "trigger-accuracy eval: skipped (no key)"
        )
        return 0  # advisory — absent key is not a failure (REQ-SEC-02, REQ-EVAL-02)

    import anthropic  # imported only when a key is present (keeps absent-key path dep-free)

    catalog = load_catalog()
    valid = set(catalog.keys())
    system_prompt = build_system_prompt(catalog)
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment

    report = Report(model=MODEL)
    for fixture in load_fixtures():
        sr = score_fixture(client, system_prompt, fixture, valid)
        report.skills.append(sr)
        report.total_cases += sr.total
        report.total_correct += sr.correct
    report.accuracy = (report.total_correct / report.total_cases) if report.total_cases else 0.0

    print(json.dumps(asdict(report), indent=2) if as_json else "")
    if not as_json:
        print_human(report)
    return 0  # advisory — a low score never fails the job (REQ-EVAL-02)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
