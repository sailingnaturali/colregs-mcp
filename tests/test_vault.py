from pathlib import Path
from colregs_mcp.vault import Vault

FIXTURE = Path(__file__).parent / "fixtures" / "vault"

def test_vault_loads_rules_requirements_and_regions():
    v = Vault.load(FIXTURE)
    assert any(r.number == "30" and r.regime == "international" for r in v.rules)
    assert v.requirements.entries[0]["id"] == "anchored-under-50m-night"
    assert v.regime_features[0]["regime"] == "canadian"

def test_vault_get_rule_by_number_and_regime():
    v = Vault.load(FIXTURE)
    r = v.get_rule("30", "international")
    assert r is not None and "ball" in r.prose
    assert v.get_rule("30", "inland") is None
