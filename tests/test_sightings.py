from pathlib import Path
from colregs_mcp.sightings import identify_signals
from colregs_mcp.vault import Vault

FIXTURE = Path(__file__).parent / "fixtures" / "vault"

def _s():
    return Vault.load(FIXTURE).sightings

def test_exact_match_returns_single_candidate():
    out = identify_signals(_s(), ["red", "red"], "night")
    assert [m["match_type"] for m in out["matches"]] == ["exact"]
    assert out["matches"][0]["candidates"][0]["situation"] == "not_under_command"
    assert out["kind"] == "lights"

def test_exact_match_carries_confirm_cues():
    out = identify_signals(_s(), ["red", "red"], "night")
    assert any("AGROUND" in c for c in out["matches"][0]["confirm"])

def test_partial_sighting_returns_superset_matches():
    out = identify_signals(_s(), ["red"], "night")
    types = {m["match_type"] for m in out["matches"]}
    sits = {c["situation"] for m in out["matches"] for c in m["candidates"]}
    assert types == {"superset"}
    assert "not_under_command" in sits and "constrained_by_draught" in sits

def test_flipped_order_returns_permutation_match():
    out = identify_signals(_s(), ["white", "red", "red"], "night")
    assert [m["match_type"] for m in out["matches"]] == ["permutation"]
    assert out["matches"][0]["candidates"][0]["situation"] == "restricted_manoeuvrability"

def test_no_match_returns_empty_matches():
    out = identify_signals(_s(), ["green", "green"], "night")
    assert out["matches"] == []

def test_lights_by_day_is_an_error():
    out = identify_signals(_s(), ["red", "red"], "day")
    assert "error" in out and out["matches"] == []

def test_mixed_tokens_is_an_error():
    out = identify_signals(_s(), ["red", "ball"], "night")
    assert "error" in out and out["matches"] == []

def test_unknown_token_is_an_error():
    out = identify_signals(_s(), ["purple"], "night")
    assert "error" in out and out["matches"] == []

def test_list_signal_patterns_returns_vocabulary_and_catalog():
    from colregs_mcp.sightings import list_signal_patterns
    out = list_signal_patterns(_s())
    assert set(out["light_colors"]) == {"red", "white", "green", "yellow"}
    assert "ball" in out["day_shapes"]
    ids = [p["id"] for p in out["patterns"]]
    assert "red-over-red-night" in ids
    entry = next(p for p in out["patterns"] if p["id"] == "red-over-red-night")
    assert entry["situations"] == ["not_under_command"]
    assert entry["arrangement"] == ["red", "red"]
    assert entry["confirm"]  # confirm cues are surfaced for browsing


from colregs_mcp.vault import Sightings

def _geo_catalog():
    return Sightings(patterns=[
        {"id": "aground-day", "arrangement": ["ball", "ball", "ball"], "condition": "day",
         "candidates": [{"situation": "vessel_aground", "rule": "R30"}]},   # geometry defaults vertical
        {"id": "minesweep-day", "arrangement": ["ball", "ball", "ball"], "condition": "day",
         "geometry": "triangle",
         "candidates": [{"situation": "mine_clearance", "rule": "R27"}]},
    ])

def test_geometry_omitted_returns_both_with_geometry_labels():
    out = identify_signals(_geo_catalog(), ["ball", "ball", "ball"], "day")
    sits = {c["situation"] for m in out["matches"] for c in m["candidates"]}
    geos = {m["geometry"] for m in out["matches"]}
    assert sits == {"vessel_aground", "mine_clearance"}
    assert geos == {"vertical", "triangle"}

def test_geometry_given_filters_to_matching_geometry():
    out = identify_signals(_geo_catalog(), ["ball", "ball", "ball"], "day", geometry="triangle")
    assert [c["situation"] for m in out["matches"] for c in m["candidates"]] == ["mine_clearance"]

def test_geometry_defaults_vertical_when_pattern_omits_it():
    out = identify_signals(_geo_catalog(), ["ball", "ball", "ball"], "day", geometry="vertical")
    assert [c["situation"] for m in out["matches"] for c in m["candidates"]] == ["vessel_aground"]


def test_list_signal_patterns_includes_flashing_and_geometry():
    from colregs_mcp.sightings import list_signal_patterns
    s = Sightings(patterns=[
        {"id": "tri", "arrangement": ["green", "green", "green"], "condition": "night",
         "geometry": "triangle",
         "candidates": [{"situation": "mine_clearance", "rule": "R27"}]},
    ])
    out = list_signal_patterns(s)
    assert "flashing_yellow" in out["flashing_lights"]
    assert out["patterns"][0]["geometry"] == "triangle"


def test_real_vault_towing_yellow_over_white(tmp_path):
    import pytest
    from pathlib import Path
    REAL = Path(__file__).resolve().parents[2] / "colregs-vault"
    if not (REAL / "sightings.yaml").is_file():
        pytest.skip("sibling colregs-vault not present")
    from colregs_mcp.vault import Vault
    v = Vault.load(REAL)
    out = identify_signals(v.sightings, ["yellow", "white"], "night", geometry="fore_and_aft")
    assert any(c["situation"] == "towing" for m in out["matches"] for c in m["candidates"])


def test_real_vault_three_ball_geometry_collision(tmp_path):
    import pytest
    from pathlib import Path
    REAL = Path(__file__).resolve().parents[2] / "colregs-vault"
    if not (REAL / "sightings.yaml").is_file():
        pytest.skip("sibling colregs-vault not present")
    from colregs_mcp.vault import Vault
    v = Vault.load(REAL)
    both = identify_signals(v.sightings, ["ball", "ball", "ball"], "day")
    sits = {c["situation"] for m in both["matches"] for c in m["candidates"]}
    assert {"vessel_aground", "mine_clearance"} <= sits
    tri = identify_signals(v.sightings, ["ball", "ball", "ball"], "day", geometry="triangle")
    assert [c["situation"] for m in tri["matches"] for c in m["candidates"]] == ["mine_clearance"]


def test_real_vault_red_red_three_candidates(tmp_path):
    import pytest
    from pathlib import Path
    REAL = Path(__file__).resolve().parents[2] / "colregs-vault"
    if not (REAL / "sightings.yaml").is_file():
        pytest.skip("sibling colregs-vault not present")
    from colregs_mcp.vault import Vault
    v = Vault.load(REAL)
    out = identify_signals(v.sightings, ["red", "red"], "night")
    sits = {c["situation"] for m in out["matches"] for c in m["candidates"]}
    assert {"not_under_command", "vessel_aground", "fishing"} <= sits

def test_real_vault_white_red_pilot_and_fishing(tmp_path):
    import pytest
    from pathlib import Path
    REAL = Path(__file__).resolve().parents[2] / "colregs-vault"
    if not (REAL / "sightings.yaml").is_file():
        pytest.skip("sibling colregs-vault not present")
    from colregs_mcp.vault import Vault
    v = Vault.load(REAL)
    out = identify_signals(v.sightings, ["white", "red"], "night")
    sits = {c["situation"] for m in out["matches"] for c in m["candidates"]}
    assert {"pilot_vessel", "fishing"} <= sits
