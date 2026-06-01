"""Sync tool implementations. server.py wraps these for MCP; tests call them directly."""

from __future__ import annotations

from dataclasses import asdict

from colregs_mcp.compliance import check_compliance
from colregs_mcp.models import Profile
from colregs_mcp.regime import locate_regime
from colregs_mcp.requirements import required_signals
from colregs_mcp.search import rank_rules
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
    return Profile(
        vessel_class=d["vessel_class"], length_m=float(d["length_m"]),
        propulsion=d["propulsion"], regime=d["regime"], condition=d["condition"],
    )


def required_signals_tool(vault: Vault, profile: dict) -> dict:
    return required_signals(vault.requirements, _profile(profile))


def check_compliance_tool(vault: Vault, profile: dict, observed) -> dict:
    return check_compliance(vault.requirements, _profile(profile), observed or [])
