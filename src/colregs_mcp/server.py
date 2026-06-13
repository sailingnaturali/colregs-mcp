"""colregs-mcp server. Exposes navigation-rule tools over stdio.

Vault directory comes from COLREGS_VAULT_PATH (default ~/.colregs-vault).
"""

from __future__ import annotations

import asyncio
import json
import logging

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from colregs_mcp import models as models_vocab
from colregs_mcp import tools
from colregs_mcp.vault import Vault

logger = logging.getLogger(__name__)

_PROFILE_SCHEMA = {
    "type": "object",
    "properties": {
        "vessel_class": {"type": "string", "enum": sorted(models_vocab.VESSEL_CLASSES)},
        "length_m": {"type": "number"},
        "propulsion": {"type": "string", "enum": ["sail", "machinery", "sail_and_machinery"]},
        "regime": {"type": "string", "enum": ["international", "inland", "canadian"]},
        "condition": {"type": "string", "enum": ["day", "night", "restricted_visibility"]},
    },
    "required": ["vessel_class", "length_m", "propulsion", "regime", "condition"],
}

_ARRANGEMENT_SCHEMA = {
    "type": "array",
    "items": {"type": "string", "enum": sorted(models_vocab.SIGNAL_TOKENS)},
    "description": "observed signals, top to bottom; light colours OR day shapes, not both",
}


def dispatch(vault: Vault, name: str, args: dict) -> dict:
    """Route a tool call to its implementation. Shared by the server and tests."""
    if name == "get_rule":
        return tools.get_rule(vault, number=str(args["number"]), regime=args.get("regime"))
    if name == "search_rules":
        return tools.search_rules(vault, query=args["query"], regime=args.get("regime"),
                                  limit=args.get("limit", 5))
    if name == "resolve_regime":
        return tools.resolve_regime(vault, lat=args["lat"], lon=args["lon"])
    if name == "required_signals":
        return tools.required_signals_tool(vault, profile=args["profile"])
    if name == "check_compliance":
        return tools.check_compliance_tool(vault, profile=args["profile"],
                                           observed=args.get("observed", []))
    if name == "identify_signals":
        return tools.identify_signals_tool(vault, arrangement=args["arrangement"],
                                           condition=args["condition"], regime=args.get("regime"))
    if name == "list_signal_patterns":
        return tools.list_signal_patterns_tool(vault)
    raise ValueError(f"Unknown tool: {name}")


def build_server(vault: Vault) -> Server:
    server = Server("colregs-mcp")

    @server.list_tools()
    async def _list_tools() -> list[types.Tool]:
        return [
            types.Tool(name="get_rule",
                description="Full text of a navigation rule. Omit `regime` to get all three regimes.",
                inputSchema={"type": "object", "properties": {
                    "number": {"type": "string"},
                    "regime": {"type": "string", "enum": ["international", "inland", "canadian"]},
                }, "required": ["number"]}),
            types.Tool(name="search_rules",
                description="Keyword search across rule text; returns ranked excerpts with citations.",
                inputSchema={"type": "object", "properties": {
                    "query": {"type": "string"},
                    "regime": {"type": "string", "enum": ["international", "inland", "canadian"]},
                    "limit": {"type": "number"},
                }, "required": ["query"]}),
            types.Tool(name="resolve_regime",
                description="Which regime (international/inland/canadian) applies at a position.",
                inputSchema={"type": "object", "properties": {
                    "lat": {"type": "number"}, "lon": {"type": "number"},
                }, "required": ["lat", "lon"]}),
            types.Tool(name="required_signals",
                description="Lights and shapes the rules require for a vessel situation, with citations.",
                inputSchema={"type": "object", "properties": {"profile": _PROFILE_SCHEMA},
                             "required": ["profile"]}),
            types.Tool(name="check_compliance",
                description="Diff required lights against the lights actually shown (a set of normalized light ids).",
                inputSchema={"type": "object", "properties": {
                    "profile": _PROFILE_SCHEMA,
                    "observed": {"type": "array", "items": {"type": "string"}},
                }, "required": ["profile", "observed"]}),
            types.Tool(name="identify_signals",
                description=("Identify a vessel from its lights or shapes. Given an observed "
                             "top-to-bottom arrangement of all-round light colours (night) or day "
                             "shapes, returns ranked candidate vessel states with rule citations and "
                             "confirm cues; each match_type is exact, superset (a light may have been "
                             "missed), or permutation (top/bottom may be flipped)."),
                inputSchema={"type": "object", "properties": {
                    "arrangement": _ARRANGEMENT_SCHEMA,
                    "condition": {"type": "string", "enum": ["day", "night", "restricted_visibility"]},
                    "regime": {"type": "string", "enum": ["international", "inland", "canadian"]},
                }, "required": ["arrangement", "condition"]}),
            types.Tool(name="list_signal_patterns",
                description=("Browse the canonical token vocabulary (light colours, day shapes) and "
                             "the catalog of known sighting patterns — use it to find the exact tokens "
                             "to pass to identify_signals."),
                inputSchema={"type": "object", "properties": {}}),
        ]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
        result = dispatch(vault, name, arguments or {})
        return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    return server


async def _run() -> None:
    vault = Vault.load()
    logger.info("loaded %d rules from %s", len(vault.rules), vault.root)
    server = build_server(vault)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_run())


if __name__ == "__main__":
    main()
