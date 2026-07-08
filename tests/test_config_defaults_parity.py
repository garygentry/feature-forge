"""Guard: forge-init.sh's emitted config agrees with forge-config-schema.json.

Part of Chunk G's coverage-gap gates. `forge-init.sh` writes the canonical
`forge.config.json` defaults; `references/forge-config-schema.json` is the shared
contract every consumer validates against. They drifted historically (the
`backlogDir` contract-lie class). This locks them: every key forge-init emits is a
real schema property, and its value equals the schema's declared default.

Scope note — the full config-defaults parity chain is
`forge-init.sh ↔ forge-bootstrap.py ↔ schema ↔ README`. This test owns the
`forge-init.sh ↔ schema` leg (both are canon, always present). The other legs are
locked by their own chunks so this test stays green independently:
- `forge-bootstrap.py ↔ forge-init.sh` field set — `tests/test_forge_bootstrap.py`
  (`test_scaffolded_config_matches_forge_init_field_set`).
- schema ↔ README table completeness — the docs-reconciliation chunk's acceptance.

Stdlib-only (json + text parsing) so it runs under bare `pytest tests` / CI's gate.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FORGE_INIT = REPO_ROOT / "scripts" / "forge-init.sh"
SCHEMA = REPO_ROOT / "references" / "forge-config-schema.json"


def _forge_init_config() -> dict:
    """Parse the `forge.config.json` JSON object emitted by forge-init.sh's heredoc."""
    text = FORGE_INIT.read_text(encoding="utf-8")
    marker = "<< 'EOF'\n"
    start = text.index(marker) + len(marker)
    end = text.index("\nEOF", start)
    return json.loads(text[start:end])


def _schema_props() -> dict:
    return json.load(SCHEMA.open(encoding="utf-8"))["properties"]


def test_forge_init_keys_are_all_schema_properties() -> None:
    """Every key forge-init.sh writes is a declared property in the schema."""
    init = _forge_init_config()
    props = _schema_props()
    unknown = [k for k in init if k not in props]
    assert not unknown, f"forge-init.sh emits keys absent from the schema: {unknown}"


def test_forge_init_values_match_schema_defaults() -> None:
    """forge-init.sh's emitted value equals the schema default for each key.

    For the three null-until-resolved keys (`stack`, `typeCheckCommand`,
    `testCommand`) the schema declares no `default` (they are set during Stage 2);
    forge-init must emit JSON `null` for them.
    """
    init = _forge_init_config()
    props = _schema_props()
    mismatches: list[str] = []
    for key, value in init.items():
        prop = props.get(key, {})
        if "default" in prop:
            if value != prop["default"]:
                mismatches.append(f"{key}: forge-init={value!r} schema_default={prop['default']!r}")
        else:
            # No schema default → the resolve-later convention: forge-init emits null.
            if value is not None:
                mismatches.append(f"{key}: no schema default but forge-init emits {value!r} (expected null)")
    assert not mismatches, "forge-init.sh ↔ schema default drift: " + "; ".join(mismatches)
