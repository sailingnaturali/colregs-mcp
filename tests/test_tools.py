from pathlib import Path
from colregs_mcp.tools import get_rule
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
