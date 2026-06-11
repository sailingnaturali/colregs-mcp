"""Evaluate the curated requirements.yaml decision table against a vessel profile."""

from __future__ import annotations

from colregs_mcp.models import Profile, derive_situation
from colregs_mcp.vault import Requirements


def entry_matches(match: dict, eff: dict) -> bool:
    """True iff every constraint in `match` holds for the effective profile `eff`."""
    if "situation" in match and match["situation"] != eff["situation"]:
        return False
    if "condition" in match and match["condition"] != eff["condition"]:
        return False
    regime = match.get("regime")
    if regime not in (None, "any") and regime != eff["regime"]:
        return False
    if "length_lt" in match and not (eff["length_m"] < match["length_lt"]):
        return False
    if "length_gte" in match and not (eff["length_m"] >= match["length_gte"]):
        return False
    return True


def required_signals(reqs: Requirements, profile: Profile) -> dict:
    situation = derive_situation(profile)
    eff = {
        "situation": situation,
        "condition": profile.condition,
        "length_m": profile.length_m,
        "regime": profile.regime,
    }
    lights: list[dict] = []
    light_options: list[list[dict]] = []
    shapes: list[dict] = []
    forbids: list[str] = []
    citations: list[str] = []
    matched = False

    for entry in reqs.entries:
        if not entry_matches(entry.get("match", {}), eff):
            continue
        matched = True
        lights.extend(entry.get("lights", []))
        light_options.extend(entry.get("light_options", []))
        shapes.extend(entry.get("shapes", []))
        forbids.extend(entry.get("forbids", []))

    for sig in lights + shapes + [l for grp in light_options for l in grp]:
        if sig.get("rule") and sig["rule"] not in citations:
            citations.append(sig["rule"])

    forbids = list(dict.fromkeys(forbids))
    return {
        "situation": situation,
        # False = no requirements row covers this profile. Callers must treat
        # that as "not modeled", never as "nothing required" (R1).
        "matched": matched,
        "lights": lights,
        "light_options": light_options,
        "shapes": shapes,
        "forbids": forbids,
        "citations": citations,
    }
