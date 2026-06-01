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
