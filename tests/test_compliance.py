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

def test_unmodeled_situation_is_never_compliant():
    # A dark 60 m power vessel matches no row (only length_lt:50 exists) — absence
    # of a rule must read "not modeled", not "compliant" (fleet conventions R1).
    out = check_compliance(_reqs(), Profile("power_driven", 60.0, "machinery", "international", "night"),
                           observed=[])
    assert out["ok"] is False
    assert out["not_modeled"] is True
    assert "do not rely" in out["note"]

def test_restricted_visibility_is_not_modeled_not_compliant():
    out = check_compliance(_reqs(),
                           Profile("power_driven", 14.9, "machinery", "international", "restricted_visibility"),
                           observed=["masthead_steaming", "sidelights", "sternlight"])
    assert out["ok"] is False
    assert out["not_modeled"] is True

def test_modeled_situation_carries_not_modeled_false():
    out = check_compliance(_reqs(), Profile("anchored", 14.9, "machinery", "canadian", "night"),
                           observed=["anchor_light"])
    assert out["ok"] is True and out["not_modeled"] is False
