from pathlib import Path
from colregs_mcp.vault import Vault

FIXTURE = Path(__file__).parent / "fixtures" / "vault"

def test_vault_loads_rules_requirements_and_regions():
    v = Vault.load(FIXTURE)
    assert any(r.number == "30" and r.regime == "international" for r in v.rules)
    assert v.requirements.entries[0]["id"] == "anchored-under-50m-night"
    assert v.regime_features[0]["regime"] == "canadian"

def test_vault_get_rule_by_number_and_regime():
    v = Vault.load(FIXTURE)
    r = v.get_rule("30", "international")
    assert r is not None and "ball" in r.prose
    assert v.get_rule("30", "inland") is None

def _write_vault(tmp_path, requirements_yaml: str) -> Path:
    (tmp_path / "requirements.yaml").write_text(requirements_yaml, encoding="utf-8")
    return tmp_path

def _write_sightings_vault(tmp_path, sightings_yaml: str) -> Path:
    (tmp_path / "sightings.yaml").write_text(sightings_yaml, encoding="utf-8")
    return tmp_path

def test_requirements_rejects_unknown_match_key(tmp_path):
    import pytest
    root = _write_vault(tmp_path, (
        "version: 1\n"
        "entries:\n"
        "  - id: typo-row\n"
        "    match: { situation: anchored, lenght_lt: 50 }\n"   # typo'd key
        "    lights: [{ id: anchor_light, rule: 'Rule 30(a)' }]\n"
    ))
    with pytest.raises(ValueError, match="lenght_lt"):
        Vault.load(root)

def test_requirements_rejects_empty_match(tmp_path):
    import pytest
    root = _write_vault(tmp_path, (
        "version: 1\n"
        "entries:\n"
        "  - id: catch-all\n"
        "    match: {}\n"
        "    lights: [{ id: anchor_light, rule: 'Rule 30(a)' }]\n"
    ))
    with pytest.raises(ValueError, match="catch-all"):
        Vault.load(root)

def test_requirements_rejects_unknown_situation(tmp_path):
    import pytest
    root = _write_vault(tmp_path, (
        "version: 1\n"
        "entries:\n"
        "  - id: bad-situation\n"
        "    match: { situation: submarine, condition: night }\n"
        "    lights: [{ id: anchor_light, rule: 'Rule 30(a)' }]\n"
    ))
    with pytest.raises(ValueError, match="submarine"):
        Vault.load(root)

def test_coverage_gaps_reported_for_fixture():
    # The fixture (like the live vault) has no restricted-visibility rows and a
    # power_driven night band that stops at 50 m — both must surface as gaps.
    v = Vault.load(FIXTURE)
    gaps = v.requirements.coverage_gaps()
    assert any("restricted_visibility" in g for g in gaps)
    assert any("power_driven" in g and "50" in g for g in gaps)

def test_vault_loads_sightings():
    v = Vault.load(FIXTURE)
    ids = [p["id"] for p in v.sightings.patterns]
    assert "red-over-red-night" in ids

def test_sightings_rejects_unknown_token(tmp_path):
    import pytest
    with pytest.raises(ValueError, match="unknown token"):
        Vault.load(_write_sightings_vault(tmp_path,
            "version: 1\n"
            "patterns:\n"
            "  - id: bad-token\n"
            "    arrangement: [purple]\n"
            "    condition: night\n"
            "    candidates: [{ situation: anchored, rule: 'Rule 30' }]\n"))

def test_sightings_rejects_kind_condition_mismatch(tmp_path):
    import pytest
    with pytest.raises(ValueError, match="not a shapes condition"):
        Vault.load(_write_sightings_vault(tmp_path,
            "version: 1\n"
            "patterns:\n"
            "  - id: shape-by-night\n"
            "    arrangement: [ball]\n"
            "    condition: night\n"
            "    candidates: [{ situation: anchored, rule: 'Rule 30' }]\n"))

def test_sightings_rejects_unknown_situation(tmp_path):
    import pytest
    with pytest.raises(ValueError, match="unknown situation"):
        Vault.load(_write_sightings_vault(tmp_path,
            "version: 1\n"
            "patterns:\n"
            "  - id: bad-situation\n"
            "    arrangement: [red, red]\n"
            "    condition: night\n"
            "    candidates: [{ situation: submarine, rule: 'Rule 27' }]\n"))

def test_sightings_rejects_missing_condition(tmp_path):
    import pytest
    with pytest.raises(ValueError, match="missing required field 'condition'"):
        Vault.load(_write_sightings_vault(tmp_path,
            "version: 1\n"
            "patterns:\n"
            "  - id: no-condition\n"
            "    arrangement: [red, red]\n"
            "    candidates: [{ situation: not_under_command, rule: 'Rule 27' }]\n"))

def test_sightings_accepts_geometry(tmp_path):
    (tmp_path / "sightings.yaml").write_text(
        "version: 1\n"
        "patterns:\n"
        "  - id: tri\n"
        "    arrangement: [green, green, green]\n"
        "    condition: night\n"
        "    geometry: triangle\n"
        "    candidates: [{ situation: mine_clearance, rule: 'Rule 27(f)' }]\n",
        encoding="utf-8")
    v = Vault.load(tmp_path)
    assert v.sightings.patterns[0]["geometry"] == "triangle"

def test_sightings_rejects_unknown_geometry(tmp_path):
    import pytest
    (tmp_path / "sightings.yaml").write_text(
        "version: 1\n"
        "patterns:\n"
        "  - id: bad-geo\n"
        "    arrangement: [red, red]\n"
        "    condition: night\n"
        "    geometry: sideways\n"
        "    candidates: [{ situation: not_under_command, rule: 'Rule 27' }]\n",
        encoding="utf-8")
    with pytest.raises(ValueError, match="unknown geometry"):
        Vault.load(tmp_path)

def test_requirements_rejects_unknown_token(tmp_path):
    import pytest
    (tmp_path / "requirements.yaml").write_text(
        "version: 1\n"
        "entries:\n"
        "  - id: bad-token\n"
        "    match: { situation: towing, condition: night }\n"
        "    lights: [{ id: x, token: chartreuse, rule: 'Rule 24' }]\n",
        encoding="utf-8")
    with pytest.raises(ValueError, match="unknown token"):
        Vault.load(tmp_path)

def test_requirements_accepts_null_token(tmp_path):
    (tmp_path / "requirements.yaml").write_text(
        "version: 1\n"
        "entries:\n"
        "  - id: aground-like\n"
        "    match: { situation: vessel_aground, condition: night }\n"
        "    lights:\n"
        "      - { id: all_round_red_upper, rule: 'Rule 30' }\n"
        "      - { id: anchor_light, token: null, rule: 'Rule 30' }\n",
        encoding="utf-8")
    v = Vault.load(tmp_path)  # must not raise
    assert v.requirements.entries[0]["id"] == "aground-like"
