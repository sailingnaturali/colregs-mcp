"""Sync tool implementations. server.py wraps these for MCP; tests call them directly."""

from __future__ import annotations

from dataclasses import asdict

from colregs_mcp.compliance import check_compliance
from colregs_mcp.models import Profile
from colregs_mcp.regime import locate_regime
from colregs_mcp.requirements import required_signals
from colregs_mcp.search import rank_rules
from colregs_mcp.sightings import identify_signals, list_signal_patterns
from colregs_mcp.vault import Vault


def search_rules(vault: Vault, query: str, regime: str | None = None, limit: int = 5) -> dict:
    rules = vault.rules if regime is None else [r for r in vault.rules if r.regime == regime]
    hits = rank_rules(rules, query, limit=limit)
    return {"query": query, "hits": [
        {"number": r.number, "regime": r.regime, "title": r.title,
         "excerpt": r.prose[:280], "citation": f"Rule {r.number}"}
        for r in hits
    ]}


def get_rule(vault: Vault, number: str, regime: str | None = None) -> dict:
    if regime:
        r = vault.get_rule(number, regime)
        if r is None:
            return {"found": False, "number": str(number), "regime": regime}
        return {"found": True, "rule": asdict(r)}
    rules = vault.rules_for_number(number)
    if not rules:
        return {"found": False, "number": str(number)}
    return {"found": True, "number": str(number),
            "regimes": {r.regime: asdict(r) for r in rules}}


def resolve_regime(vault: Vault, lat: float, lon: float) -> dict:
    regime = locate_regime(vault.regime_features, lat, lon, default="international")
    return {"lat": lat, "lon": lon, "regime": regime}


def _profile(d: dict) -> Profile:
    from colregs_mcp.models import CONDITIONS, PROPULSIONS, REGIMES, VESSEL_CLASSES

    for key in ("vessel_class", "length_m", "propulsion", "regime", "condition"):
        if key not in d:
            raise ValueError(f"profile is missing required field {key!r}")
    try:
        length_m = float(d["length_m"])
    except (TypeError, ValueError):
        raise ValueError(f"profile length_m must be a number, got {d['length_m']!r}") from None
    for key, vocab in (("vessel_class", VESSEL_CLASSES), ("propulsion", PROPULSIONS),
                       ("regime", REGIMES), ("condition", CONDITIONS)):
        if d[key] not in vocab:
            raise ValueError(f"unknown {key} {d[key]!r}; expected one of {sorted(vocab)}")
    return Profile(
        vessel_class=d["vessel_class"], length_m=length_m,
        propulsion=d["propulsion"], regime=d["regime"], condition=d["condition"],
    )


def required_signals_tool(vault: Vault, profile: dict) -> dict:
    try:
        p = _profile(profile)
    except ValueError as e:
        return {"error": str(e), "found": False}
    return required_signals(vault.requirements, p)


def check_compliance_tool(vault: Vault, profile: dict, observed) -> dict:
    try:
        p = _profile(profile)
    except ValueError as e:
        return {"error": str(e), "found": False}
    return check_compliance(vault.requirements, p, observed or [])


def identify_signals_tool(vault: Vault, arrangement: list[str], condition: str,
                          regime: str | None = None) -> dict:
    return identify_signals(vault.sightings, arrangement or [], condition, regime)


def list_signal_patterns_tool(vault: Vault) -> dict:
    return list_signal_patterns(vault.sightings)
