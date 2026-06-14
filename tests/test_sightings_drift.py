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

def test_signal_token_requires_colour_delimiter():
    from colregs_mcp.sightings import _signal_token
    assert _signal_token("all_round_red") == "red"
    assert _signal_token("all_round_red_upper") == "red"
    assert _signal_token("all_round_reddish") is None

def test_explicit_token_makes_sector_light_diagnostic():
    # towing's yellow towing light + sternlight (declared white) form a [yellow, white] band.
    reqs = Requirements(entries=[
        {"id": "towing-stern", "match": {"situation": "towing", "condition": "night"},
         "lights": [{"id": "towing_light", "token": "yellow", "rule": "R24"},
                    {"id": "sternlight", "token": "white", "rule": "R24"}]},
    ])
    ok = Sightings(patterns=[
        {"id": "tow-aft", "arrangement": ["yellow", "white"], "condition": "night",
         "candidates": [{"situation": "towing", "rule": "R24"}]},
    ])
    assert sightings_drift(ok, reqs) == []

def test_null_token_suppresses_heuristic():
    # aground shows two reds + an anchor light; token:null keeps the anchor light out of
    # the band so the recognizable signal stays [red, red] (not [red, red, white]).
    reqs = Requirements(entries=[
        {"id": "aground", "match": {"situation": "vessel_aground", "condition": "night"},
         "lights": [{"id": "all_round_red_upper", "rule": "R30"},
                    {"id": "all_round_red_lower", "rule": "R30"},
                    {"id": "anchor_light", "token": None, "rule": "R30"}]},
    ])
    ok = Sightings(patterns=[
        {"id": "ag", "arrangement": ["red", "red"], "condition": "night",
         "candidates": [{"situation": "vessel_aground", "rule": "R30"}]},
    ])
    assert sightings_drift(ok, reqs) == []

def test_flashing_token_band():
    reqs = Requirements(entries=[
        {"id": "ac", "match": {"situation": "air_cushion", "condition": "night"},
         "lights": [{"id": "fy", "token": "flashing_yellow", "rule": "R23"}]},
    ])
    ok = Sightings(patterns=[
        {"id": "acs", "arrangement": ["flashing_yellow"], "condition": "night",
         "candidates": [{"situation": "air_cushion", "rule": "R23"}]},
    ])
    assert sightings_drift(ok, reqs) == []
