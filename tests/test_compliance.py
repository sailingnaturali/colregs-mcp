from pathlib import Path
from colregs_mcp.compliance import check_compliance
from colregs_mcp.models import Profile
from colregs_mcp.vault import Vault

FIXTURE = Path(__file__).parent / "fixtures" / "vault"

def _reqs():
    return Vault.load(FIXTURE).requirements

def test_anchored_with_anchor_light_on_is_ok():
    out = check_compliance(_reqs(), Profile("anchored", 14.9, "machinery", "canadian", "night"),
                           observed=["anchor_light"])
    assert out["ok"] is True
    assert out["missing"] == []

def test_anchored_with_anchor_light_off_flags_missing():
    out = check_compliance(_reqs(), Profile("anchored", 14.9, "machinery", "canadian", "night"),
                           observed=["sidelights"])
    assert out["ok"] is False
    assert "anchor_light" in out["missing"]
    assert "sidelights" in out["extra"]          # forbidden-and-on

def test_motorsailing_with_tricolor_on_is_a_conflict():
    out = check_compliance(_reqs(), Profile("sailing", 14.9, "sail_and_machinery", "canadian", "night"),
                           observed=["masthead_steaming", "sidelights", "sternlight", "tricolor"])
    assert out["ok"] is False
    assert "tricolor" in out["extra"]

def test_sailing_tricolor_satisfies_option_group():
    out = check_compliance(_reqs(), Profile("sailing", 11.0, "sail", "international", "night"),
                           observed=["tricolor"])
    assert out["ok"] is True
    assert out["unsatisfied_options"] == []

def test_sailing_no_lights_reports_unsatisfied_option():
    out = check_compliance(_reqs(), Profile("sailing", 11.0, "sail", "international", "night"),
                           observed=[])
    assert out["ok"] is False
    assert out["unsatisfied_options"]            # at least one group unmet
