from pathlib import Path
import pytest
from colregs_mcp.sightings import sightings_drift
from colregs_mcp.vault import Vault

REAL_VAULT = Path(__file__).resolve().parents[2] / "colregs-vault"

@pytest.mark.skipif(not (REAL_VAULT / "sightings.yaml").is_file(),
                    reason="sibling colregs-vault not present")
def test_real_sightings_have_no_drift():
    v = Vault.load(REAL_VAULT)
    assert sightings_drift(v.sightings, v.requirements) == []
