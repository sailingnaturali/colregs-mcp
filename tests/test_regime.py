from pathlib import Path
from colregs_mcp.regime import locate_regime
from colregs_mcp.vault import Vault

FIXTURE = Path(__file__).parent / "fixtures" / "vault"

def _features():
    return Vault.load(FIXTURE).regime_features

def test_point_in_canadian_box():
    assert locate_regime(_features(), lat=48.89, lon=-123.39, default="international") == "canadian"

def test_point_outside_falls_back_to_default():
    assert locate_regime(_features(), lat=10.0, lon=-140.0, default="international") == "international"
