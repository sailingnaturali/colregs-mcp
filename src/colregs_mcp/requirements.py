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
