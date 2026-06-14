"""Reverse lookup: an observed light/shape arrangement -> candidate vessel states.

The LLM translates a spoken observation ("two red lights stacked") into canonical
tokens (["red", "red"]); this module matches those tokens against the curated
sightings catalog. Matching is deterministic — never fuzzy over prose — but
generous about near-misses (a missed light, a flipped order) because real
observations are noisy. Ranking: exact -> superset (missed a light) ->
permutation (flipped order)."""

from __future__ import annotations

from colregs_mcp.models import (
    DAY_SHAPES, FLASHING_LIGHTS, LIGHT_COLORS, SIGNAL_CONDITIONS, token_kind,
)
from colregs_mcp.vault import Requirements, Sightings


def _infer_kind(arrangement: list[str]) -> str:
    kinds = {token_kind(t) for t in arrangement}  # raises on unknown token
    if len(kinds) != 1:
        raise ValueError(f"arrangement mixes lights and shapes: {arrangement!r}")
    return kinds.pop()


def _is_subsequence(short: list[str], long: list[str]) -> bool:
    """True iff `short` appears in `long` in order (gaps allowed) — i.e. the observer
    could have missed lights from `long` and seen `short`."""
    it = iter(long)
    return all(tok in it for tok in short)


def _match(pattern: dict, match_type: str) -> dict:
    return {
        "match_type": match_type,
        "pattern_id": pattern["id"],
        "mnemonic": pattern.get("mnemonic"),
        "geometry": pattern.get("geometry", "vertical"),
        "candidates": pattern["candidates"],
        "confirm": pattern.get("confirm", []),
    }


def identify_signals(sightings: Sightings, arrangement, condition: str,
                     regime: str | None = None, geometry: str | None = None) -> dict:
    arrangement = list(arrangement or [])
    if not arrangement:
        return {"error": "arrangement is empty", "matches": []}
    try:
        kind = _infer_kind(arrangement)
    except ValueError as e:
        return {"error": str(e), "matches": []}
    if condition not in SIGNAL_CONDITIONS[kind]:
        return {"error": f"{kind} are not shown in condition {condition!r}",
                "kind": kind, "matches": []}

    def regime_ok(p: dict) -> bool:
        pr = p.get("regime")
        return pr is None or regime is None or pr == regime

    def geometry_ok(p: dict) -> bool:
        return geometry is None or p.get("geometry", "vertical") == geometry

    pool = [p for p in sightings.patterns
            if p["condition"] == condition and regime_ok(p) and geometry_ok(p)
            and _infer_kind(p["arrangement"]) == kind]

    exact, superset, permutation = [], [], []
    for p in pool:
        pa = p["arrangement"]
        if pa == arrangement:
            exact.append(_match(p, "exact"))
        elif _is_subsequence(arrangement, pa):
            superset.append(_match(p, "superset"))
        elif sorted(pa) == sorted(arrangement):
            permutation.append(_match(p, "permutation"))

    matches = exact or (superset + permutation)
    return {"arrangement": arrangement, "condition": condition, "kind": kind,
            "matches": matches}


_SHAPE_TOKENS = {"ball": "ball", "diamond": "diamond", "cylinder": "cylinder",
                 "cone_apex_down": "cone_down", "cone_apex_up": "cone_up"}


def _signal_token(sig_id: str) -> str | None:
    """Map a requirements.yaml signal id to its stacked-identity token, or None if it
    is not diagnostic. Non-diagnostic ids include the sector/combined lights
    (sidelights, sternlight, masthead_steaming, tricolor) and any id outside the
    all-round colour and day-shape vocabularies."""
    for colour in sorted(LIGHT_COLORS):
        if sig_id == f"all_round_{colour}" or sig_id.startswith(f"all_round_{colour}_"):
            return colour
    if sig_id == "anchor_light":
        return "white"
    return _SHAPE_TOKENS.get(sig_id)


def _diagnostic_token(sig: dict) -> str | None:
    """The reverse-ID token for one requirements signal. An explicit `token` key wins
    (a value, or null to force 'not diagnostic'); otherwise fall back to the all-round
    id heuristic."""
    if "token" in sig:
        return sig["token"]
    return _signal_token(sig["id"])


def _entry_token_bands(entry: dict) -> list[list[str]]:
    """The sorted diagnostic-token multiset(s) for one requirements entry. An entry
    with `light_options` yields one band per alternative group (the vessel shows its
    mandatory lights plus exactly one option group); otherwise a single band. Non-
    diagnostic signals drop out, so an all-sector configuration (e.g. a plain sailing
    vessel) yields an empty band that only an empty arrangement could match."""
    base = list(entry.get("lights", [])) + list(entry.get("shapes", []))
    groups = entry.get("light_options") or [[]]
    bands: list[list[str]] = []
    for group in groups:
        sigs = base + list(group)
        tokens = sorted(t for sig in sigs if (t := _diagnostic_token(sig)) is not None)
        bands.append(tokens)
    return bands


def _required_token_bands(reqs: Requirements, situation: str, condition: str,
                          regime: str | None) -> list[list[str]]:
    """For one situation+condition, the diagnostic-token bands of each matching
    requirements entry (one band per light-option alternative). A sighting arrangement
    must equal one of these bands."""
    bands: list[list[str]] = []
    for e in reqs.entries:
        m = e.get("match", {})
        if m.get("situation") != situation:
            continue
        if m.get("condition") not in (None, condition):
            continue
        r = m.get("regime")
        if r not in (None, "any") and regime is not None and r != regime:
            continue
        bands.extend(_entry_token_bands(e))
    return bands


def sightings_drift(sightings: Sightings, reqs: Requirements) -> list[str]:
    """Cross-check the reverse field-guide against the forward requirements table.
    Returns a list of human-readable inconsistencies (empty == consistent). Every
    sighting candidate must (a) name a situation the rules table models for that
    condition and (b) carry an arrangement whose diagnostic tokens match some
    modeled length band. Run as a test so the two files can't silently diverge.

    Known limitation: bands are aggregated across all length and regime variants of a
    situation, so a regime-agnostic sighting is validated against the union of every
    regime's requirements rather than each in isolation. This is acceptable while the
    vault has no regime- or length-specific divergence in diagnostic stacked signals;
    revisit if such entries are added."""
    problems: list[str] = []
    for p in sightings.patterns:
        arr = sorted(p["arrangement"])
        for c in p["candidates"]:
            sit, cond, regime = c["situation"], p["condition"], p.get("regime")
            bands = _required_token_bands(reqs, sit, cond, regime)
            if not bands:
                problems.append(f"{p['id']}: candidate situation {sit!r} ({cond}) is not "
                                "modeled in requirements.yaml")
            elif arr not in bands:
                problems.append(f"{p['id']}: arrangement {p['arrangement']} has no matching "
                                f"requirements band for {sit!r} ({cond}); modeled bands: {bands}")
    return problems


def list_signal_patterns(sightings: Sightings) -> dict:
    """The canonical token vocabulary plus the catalog of known patterns, so the LLM
    can browse the exact tokens to translate a spoken observation into."""
    return {
        "light_colors": sorted(LIGHT_COLORS),
        "flashing_lights": sorted(FLASHING_LIGHTS),
        "day_shapes": sorted(DAY_SHAPES),
        "geometries": ["vertical", "triangle", "fore_and_aft"],
        "note": ("arrangement is an ordered list of tokens, top to bottom; all-round "
                 "lights assumed; geometry defaults to vertical"),
        "patterns": [
            {"id": p["id"], "arrangement": p["arrangement"], "condition": p["condition"],
             "geometry": p.get("geometry", "vertical"),
             "mnemonic": p.get("mnemonic"), "confirm": p.get("confirm", []),
             "situations": [c["situation"] for c in p["candidates"]]}
            for p in sightings.patterns
        ],
    }
