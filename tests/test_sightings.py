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
