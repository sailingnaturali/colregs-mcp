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

def test_profile_schema_enum_matches_canonical_vocabulary():
    from colregs_mcp.models import VESSEL_CLASSES
    from colregs_mcp.server import _PROFILE_SCHEMA
    assert set(_PROFILE_SCHEMA["properties"]["vessel_class"]["enum"]) == set(VESSEL_CLASSES)
    # The SPEC names must be in the schema agents build against
    assert "restricted_manoeuvrability" in VESSEL_CLASSES
    assert "vessel_aground" in VESSEL_CLASSES
    assert "pilot_vessel" in VESSEL_CLASSES
