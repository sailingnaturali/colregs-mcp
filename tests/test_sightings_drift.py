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


def test_light_options_band_matches_one_alternative():
    # Diagnostic lights expressed via light_options must be matched per-alternative,
    # not dropped. red-white is one alternative; a lone red matches no band.
    reqs = Requirements(entries=[
        {"id": "opt-night", "match": {"situation": "fishing", "condition": "night"},
         "light_options": [
            [{"id": "all_round_red_a", "rule": "X"}, {"id": "all_round_white_b", "rule": "X"}],
            [{"id": "all_round_green_a", "rule": "X"}, {"id": "all_round_white_b", "rule": "X"}],
         ]},
    ])
    ok = Sightings(patterns=[
        {"id": "rw", "arrangement": ["red", "white"], "condition": "night",
         "candidates": [{"situation": "fishing", "rule": "X"}]},
    ])
    assert sightings_drift(ok, reqs) == []
    bad = Sightings(patterns=[
        {"id": "r-only", "arrangement": ["red"], "condition": "night",
         "candidates": [{"situation": "fishing", "rule": "X"}]},
    ])
    assert any("no matching requirements band" in p for p in sightings_drift(bad, reqs))


def test_signal_token_maps_diagnostic_and_drops_sector_lights():
    from colregs_mcp.sightings import _signal_token
    assert _signal_token("all_round_red_upper") == "red"
    assert _signal_token("all_round_white_mid") == "white"
    assert _signal_token("anchor_light") == "white"
    assert _signal_token("cone_apex_down") == "cone_down"
    assert _signal_token("sidelights") is None
    assert _signal_token("tricolor") is None
    assert _signal_token("masthead_steaming") is None
    assert _signal_token("totally_unknown") is None
