from pathlib import Path
from colregs_mcp.tools import get_rule, search_rules, resolve_regime, required_signals_tool, check_compliance_tool
from colregs_mcp.vault import Vault

FIXTURE = Path(__file__).parent / "fixtures" / "vault"

def _vault():
    return Vault.load(FIXTURE)

def test_get_rule_single_regime():
    out = get_rule(_vault(), number="30", regime="international")
    assert out["found"] is True
    assert out["rule"]["regime"] == "international"
    assert "ball" in out["rule"]["prose"]

def test_get_rule_all_regimes_when_regime_omitted():
    out = get_rule(_vault(), number="30", regime=None)
    assert out["found"] is True
    assert "international" in out["regimes"]

def test_get_rule_missing():
    out = get_rule(_vault(), number="99", regime="international")
    assert out["found"] is False

def test_search_rules_tool_returns_citations():
    out = search_rules(_vault(), query="conical shape apex")
    assert out["hits"][0]["number"] == "25"
    assert out["hits"][0]["citation"] == "Rule 25"

def test_resolve_regime_tool():
    out = resolve_regime(_vault(), lat=48.89, lon=-123.39)
    assert out["regime"] == "canadian"

def test_required_signals_tool_motorsailing():
    out = required_signals_tool(_vault(), profile={
        "vessel_class": "sailing", "length_m": 14.9,
        "propulsion": "sail_and_machinery", "regime": "canadian", "condition": "night"})
    assert {l["id"] for l in out["lights"]} == {"masthead_steaming", "sidelights", "sternlight"}

def test_check_compliance_tool_flags_missing_anchor_light():
    out = check_compliance_tool(_vault(), profile={
        "vessel_class": "anchored", "length_m": 14.9, "propulsion": "machinery",
        "regime": "canadian", "condition": "night"}, observed=["sidelights"])
    assert out["ok"] is False and "anchor_light" in out["missing"]

def test_profile_unknown_vessel_class_returns_structured_error():
    out = check_compliance_tool(_vault(), profile={
        "vessel_class": "submarine", "length_m": 10.0, "propulsion": "machinery",
        "regime": "international", "condition": "night"}, observed=[])
    assert out["found"] is False and "vessel_class" in out["error"]

def test_profile_missing_length_returns_structured_error():
    out = required_signals_tool(_vault(), profile={
        "vessel_class": "sailing", "propulsion": "sail",
        "regime": "international", "condition": "night"})
    assert out["found"] is False and "length_m" in out["error"]

def test_profile_non_numeric_length_returns_structured_error():
    out = required_signals_tool(_vault(), profile={
        "vessel_class": "sailing", "length_m": "twelve", "propulsion": "sail",
        "regime": "international", "condition": "night"})
    assert out["found"] is False and "length_m" in out["error"]
