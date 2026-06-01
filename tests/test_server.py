from pathlib import Path
from colregs_mcp.server import dispatch
from colregs_mcp.vault import Vault

FIXTURE = Path(__file__).parent / "fixtures" / "vault"

def _vault():
    return Vault.load(FIXTURE)

def test_dispatch_get_rule():
    out = dispatch(_vault(), "get_rule", {"number": "30", "regime": "international"})
    assert out["found"] is True

def test_dispatch_check_compliance():
    out = dispatch(_vault(), "check_compliance", {
        "profile": {"vessel_class": "anchored", "length_m": 14.9, "propulsion": "machinery",
                    "regime": "canadian", "condition": "night"},
        "observed": ["anchor_light"]})
    assert out["ok"] is True

def test_dispatch_unknown_tool_raises():
    import pytest
    with pytest.raises(ValueError):
        dispatch(_vault(), "nope", {})
