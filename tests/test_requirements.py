from colregs_mcp.requirements import entry_matches

def test_entry_matches_situation_condition_and_length():
    match = {"situation": "anchored", "condition": "night", "length_lt": 50}
    eff = {"situation": "anchored", "condition": "night", "length_m": 14.9, "regime": "canadian"}
    assert entry_matches(match, eff) is True

def test_entry_matches_rejects_wrong_length_band():
    match = {"situation": "anchored", "condition": "night", "length_gte": 50}
    eff = {"situation": "anchored", "condition": "night", "length_m": 14.9, "regime": "canadian"}
    assert entry_matches(match, eff) is False

def test_entry_matches_regime_omitted_means_all():
    match = {"situation": "power_driven", "condition": "night"}
    eff = {"situation": "power_driven", "condition": "night", "length_m": 14.9, "regime": "inland"}
    assert entry_matches(match, eff) is True

def test_entry_matches_regime_specific():
    match = {"situation": "power_driven", "condition": "night", "regime": "inland"}
    eff = {"situation": "power_driven", "condition": "night", "length_m": 14.9, "regime": "international"}
    assert entry_matches(match, eff) is False

from pathlib import Path
from colregs_mcp.models import Profile
from colregs_mcp.requirements import required_signals
from colregs_mcp.vault import Vault

FIXTURE = Path(__file__).parent / "fixtures" / "vault"

def _reqs():
    return Vault.load(FIXTURE).requirements

def _ids(signals):
    return {l["id"] for l in signals}

def test_anchored_night_requires_anchor_light_only():
    out = required_signals(_reqs(), Profile("anchored", 14.9, "machinery", "canadian", "night"))
    assert _ids(out["lights"]) == {"anchor_light"}
    assert "Rule 30(a)" in out["citations"]

def test_motorsailing_night_is_power_lights_not_tricolor():
    out = required_signals(_reqs(), Profile("sailing", 14.9, "sail_and_machinery", "canadian", "night"))
    assert _ids(out["lights"]) == {"masthead_steaming", "sidelights", "sternlight"}
    assert "tricolor" in out["forbids"]

def test_motorsailing_day_requires_cone():
    out = required_signals(_reqs(), Profile("sailing", 14.9, "sail_and_machinery", "canadian", "day"))
    assert {s["id"] for s in out["shapes"]} == {"cone_apex_down"}

def test_sailing_under_20m_offers_sidelights_or_tricolor():
    out = required_signals(_reqs(), Profile("sailing", 11.0, "sail", "international", "night"))
    option_id_sets = [{l["id"] for l in grp} for grp in out["light_options"]]
    assert {"sidelights", "sternlight"} in option_id_sets
    assert {"tricolor"} in option_id_sets

def test_constrained_by_draught_three_reds():
    out = required_signals(_reqs(), Profile("constrained_by_draught", 14.9, "machinery", "international", "night"))
    assert len(out["lights"]) == 3
