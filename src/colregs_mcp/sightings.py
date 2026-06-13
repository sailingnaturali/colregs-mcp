"""Reverse lookup: an observed light/shape arrangement -> candidate vessel states.

The LLM translates a spoken observation ("two red lights stacked") into canonical
tokens (["red", "red"]); this module matches those tokens against the curated
sightings catalog. Matching is deterministic — never fuzzy over prose — but
generous about near-misses (a missed light, a flipped order) because real
observations are noisy. Ranking: exact -> superset (missed a light) ->
permutation (flipped order)."""

from __future__ import annotations

from colregs_mcp.models import DAY_SHAPES, LIGHT_COLORS, SIGNAL_CONDITIONS, token_kind
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
        "candidates": pattern["candidates"],
        "confirm": pattern.get("confirm", []),
    }


def identify_signals(sightings: Sightings, arrangement, condition: str,
                     regime: str | None = None) -> dict:
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

    pool = [p for p in sightings.patterns
            if p["condition"] == condition and regime_ok(p)
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


def _signal_token(sig_id: str) -> str | None:
    """Map a requirements.yaml signal id to its stacked-identity token, or None if it
    is not diagnostic (sidelights, sternlight, masthead steaming, tricolor — sector
    or combined lights, never part of the vertical all-round stack)."""
    for colour in ("red", "white", "green", "yellow"):
        if sig_id.startswith(f"all_round_{colour}"):
            return colour
    if sig_id == "anchor_light":
        return "white"
    _SHAPES = {"ball": "ball", "diamond": "diamond", "cylinder": "cylinder",
               "cone_apex_down": "cone_down", "cone_apex_up": "cone_up"}
    return _SHAPES.get(sig_id)


def _required_token_bands(reqs: Requirements, situation: str, condition: str,
                          regime: str | None) -> list[list[str]]:
    """For one situation+condition, the sorted diagnostic-token multiset of each
    matching requirements length band. A sighting must equal one of these bands."""
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
        tokens = [t for sig in (e.get("lights", []) + e.get("shapes", []))
                  if (t := _signal_token(sig["id"])) is not None]
        bands.append(sorted(tokens))
    return bands


def sightings_drift(sightings: Sightings, reqs: Requirements) -> list[str]:
    """Cross-check the reverse field-guide against the forward requirements table.
    Returns a list of human-readable inconsistencies (empty == consistent). Every
    sighting candidate must (a) name a situation the rules table models for that
    condition and (b) carry an arrangement whose diagnostic tokens match some
    modeled length band. Run as a test so the two files can't silently diverge."""
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
        "day_shapes": sorted(DAY_SHAPES),
        "note": ("arrangement is an ordered list of tokens, top to bottom; "
                 "all-round lights assumed"),
        "patterns": [
            {"id": p["id"], "arrangement": p["arrangement"], "condition": p["condition"],
             "mnemonic": p.get("mnemonic"),
             "situations": [c["situation"] for c in p["candidates"]]}
            for p in sightings.patterns
        ],
    }
