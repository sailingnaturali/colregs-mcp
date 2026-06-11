from colregs_mcp.models import Rule

MD = """---
number: "30"
regime: international
part: D
title: Anchored Vessels and Vessels Aground
source_pdf: ../sources/uscg-navrules.pdf#page=40
---
A vessel at anchor shall exhibit where it can best be seen an all-round white light.
"""

def test_rule_from_markdown_parses_frontmatter_and_prose():
    r = Rule.from_markdown(MD)
    assert r.number == "30"
    assert r.regime == "international"
    assert r.part == "D"
    assert r.title.startswith("Anchored")
    assert "all-round white light" in r.prose
    assert r.source_pdf.endswith("page=40")

def test_rule_requires_frontmatter_fence():
    import pytest
    with pytest.raises(ValueError):
        Rule.from_markdown("no fence here")

from colregs_mcp.models import Profile, derive_situation

def test_derive_situation_motorsailing_is_power_not_sailing():
    p = Profile(vessel_class="sailing", length_m=14.9, propulsion="sail_and_machinery",
                regime="canadian", condition="night")
    assert derive_situation(p) == "motorsailing"

def test_derive_situation_special_state_overrides_propulsion():
    p = Profile(vessel_class="anchored", length_m=14.9, propulsion="machinery",
                regime="inland", condition="night")
    assert derive_situation(p) == "anchored"

def test_derive_situation_plain_sailing_and_power():
    assert derive_situation(Profile("sailing", 10, "sail", "international", "night")) == "sailing"
    assert derive_situation(Profile("power_driven", 10, "machinery", "international", "night")) == "power_driven"

def test_every_spec_special_class_overrides_propulsion():
    # The SPEC vocabulary, not the old internal names: a RAM vessel under power
    # must derive its special situation, never fall through to power_driven.
    for vc in ("anchored", "vessel_aground", "not_under_command", "restricted_manoeuvrability",
               "constrained_by_draught", "fishing", "towing", "being_towed", "pilot_vessel",
               "seaplane"):
        p = Profile(vc, 60.0, "machinery", "international", "night")
        assert derive_situation(p) == vc, vc

def test_derive_situation_rejects_unknown_vessel_class():
    import pytest
    with pytest.raises(ValueError, match="vessel_class"):
        derive_situation(Profile("submarine", 10, "machinery", "international", "night"))

def test_derive_situation_rejects_unknown_propulsion():
    import pytest
    with pytest.raises(ValueError, match="propulsion"):
        derive_situation(Profile("power_driven", 10, "nuclear", "international", "night"))
