"""Sync tool implementations. server.py wraps these for MCP; tests call them directly."""

from __future__ import annotations

from dataclasses import asdict

from colregs_mcp.vault import Vault


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
