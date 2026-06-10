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


from colregs_mcp.models import VESSEL_CLASSES, _SPECIAL

def test_canonical_special_classes_override_propulsion_not_fall_through():
    # The SPEC-documented special classes must map to their own situation, never to
    # power_driven via propulsion (the CRIT-2 vocab mismatch).
    for klass in ["restricted_manoeuvrability", "vessel_aground", "being_towed",
                  "pilot_vessel", "seaplane", "towing", "not_under_command",
                  "constrained_by_draught", "fishing", "anchored"]:
        p = Profile(klass, 30.0, "machinery", "international", "night")
        assert derive_situation(p) == klass, f"{klass} fell through to {derive_situation(p)}"

def test_special_set_matches_canonical_vocabulary():
    assert _SPECIAL == frozenset(VESSEL_CLASSES) - {"power_driven", "sailing"}
    assert "restricted_manoeuvrability" in _SPECIAL
    assert "vessel_aground" in _SPECIAL

def test_unknown_vessel_class_never_becomes_power_driven():
    # An out-of-vocab class with machinery propulsion must NOT be folded into power_driven.
    p = Profile("restricted_in_ability_to_maneuver", 30.0, "machinery", "international", "night")
    assert derive_situation(p) == "restricted_in_ability_to_maneuver"
