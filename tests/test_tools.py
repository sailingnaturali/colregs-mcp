from pathlib import Path
from colregs_mcp.tools import get_rule, search_rules
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
