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
