from pathlib import Path
from colregs_mcp.sightings import sightings_drift
from colregs_mcp.vault import Requirements, Sightings, Vault

FIXTURE = Path(__file__).parent / "fixtures" / "vault"

def test_fixture_catalog_has_no_drift():
    v = Vault.load(FIXTURE)
    assert sightings_drift(v.sightings, v.requirements) == []

def test_candidate_situation_not_modeled_is_flagged():
    reqs = Requirements(entries=[
        {"id": "anchored-night", "match": {"situation": "anchored", "condition": "night"},
         "lights": [{"id": "anchor_light", "rule": "Rule 30(a)"}]},
    ])
    sightings = Sightings(patterns=[
        {"id": "two-red", "arrangement": ["red", "red"], "condition": "night",
         "candidates": [{"situation": "not_under_command", "rule": "Rule 27(a)"}]},
    ])
    problems = sightings_drift(sightings, reqs)
    assert any("not modeled" in p and "not_under_command" in p for p in problems)

def test_arrangement_inconsistent_with_required_lights_is_flagged():
    # requirements say NUC shows TWO reds; the sighting claims THREE -> drift.
    reqs = Requirements(entries=[
        {"id": "nuc-night", "match": {"situation": "not_under_command", "condition": "night"},
         "lights": [{"id": "all_round_red_upper", "rule": "Rule 27(a)"},
                    {"id": "all_round_red_lower", "rule": "Rule 27(a)"}]},
    ])
    sightings = Sightings(patterns=[
        {"id": "three-red", "arrangement": ["red", "red", "red"], "condition": "night",
         "candidates": [{"situation": "not_under_command", "rule": "Rule 27(a)"}]},
    ])
    problems = sightings_drift(sightings, reqs)
    assert any("no matching requirements band" in p for p in problems)
