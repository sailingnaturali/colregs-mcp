# colregs-mcp

MCP server for the navigation rules: queryable rule text plus deterministic required-lights/shapes and compliance checking.

**Two layers:**
- **Reference layer** — `get_rule`, `search_rules`: retrieve and search rule prose from the markdown vault. Deterministic given vault state.
- **Safety layer** — `resolve_regime`, `required_signals`, `check_compliance`: point-in-polygon regime detection, and required-lights/shapes + compliance checking driven by a curated `requirements.yaml`. Fully deterministic, no LLM involved.

> **Draft status.** The companion vault (`colregs-vault`, see below) is an **UNVERIFIED DRAFT** pending expert review. Do not use `required_signals` or `check_compliance` output as the sole basis for any real navigation decision. Always verify against the current official rules.

## Install

    uv sync --all-extras --dev

## Run the server

    COLREGS_VAULT_PATH=/path/to/vault uv run colregs-mcp

`COLREGS_VAULT_PATH` defaults to `~/.colregs-vault` when not set.

## Vault layout

```
<vault>/
  rules/
    international/rule-NN.md
    inland/rule-NN.md
    canadian/rule-NN.md
  requirements.yaml        # curated light/shape requirements
  sightings.yaml           # curated reverse field-guide (observed signals -> vessel states)
  regime-polygons.geojson  # US Inland + Canadian polygon boundaries
  manifest.yaml            # version and source attribution
```

`sightings.yaml` is the curated reverse field-guide: each row maps an ordered,
top-to-bottom arrangement of all-round light colours (night) or day shapes to
candidate vessel states. A drift test cross-checks every row against
`requirements.yaml` so the forward and reverse data cannot silently disagree.

The companion vault lives at `../colregs-vault` (public repo). Rule text is sourced from the USCG Navigation Rules handbook (public domain) and the Canadian Collision Regulations, reproduced under the Reproduction of Federal Law Order.

## Tools

| Tool | Description |
|---|---|
| `get_rule` | Return full rule text by number, optionally filtered to one regime (`international`, `inland`, `canadian`) |
| `search_rules` | Keyword search over rule prose; deterministic ranking (title matches outrank prose) |
| `resolve_regime` | Point-in-polygon lookup — returns `international`, `inland`, or `canadian` for a lat/lon |
| `required_signals` | Return required lights, shapes, and option groups for a vessel profile (vessel class, length, propulsion, regime, day/night/restricted visibility) |
| `check_compliance` | Compare an observed set of light/shape IDs against requirements; returns `ok`, `missing`, `extra`, and unsatisfied option groups |
| `identify_signals` | Reverse lookup — observed top-to-bottom light/shape arrangement (optionally with `geometry`: vertical/triangle/fore_and_aft) → ranked candidate vessel states with citations and confirm cues (`match_type`: exact / superset / permutation) |
| `list_signal_patterns` | The canonical token vocabulary (light colours, day shapes) and the catalog of known sighting patterns |

See `SPEC.md` for full input/output contracts, the profile schema, and the normalized light-ID vocabulary.

## Motorsailing note

`propulsion: sail_and_machinery` is treated as **power-driven**. A motorsailing vessel must show the masthead steaming light at night and the black cone (apex down) by day — not a tricolor.

## License

MIT — see `LICENSE`.
