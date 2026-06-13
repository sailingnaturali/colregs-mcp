# colregs-mcp — Tool Contract

MCP server for the navigation rules: queryable rule text plus deterministic required-lights/shapes and compliance checking.

## Overview

`colregs-mcp` exposes five tools split across two layers:

| Layer | Tools | Determinism |
|---|---|---|
| Reference | `get_rule`, `search_rules` | Vault-sourced prose; deterministic given vault state |
| Safety | `resolve_regime`, `required_signals`, `check_compliance` | Fully deterministic; driven by curated `requirements.yaml` |

The reference layer surfaces the rule text from the markdown vault and is only as authoritative as the vault content. The safety layer — `resolve_regime`, `required_signals`, `check_compliance` — is driven exclusively by `requirements.yaml`, a curated, human-reviewed data file that must be verified against the official rules before use in any operational context.

---

## Vault Structure

The vault is a directory tree read from `COLREGS_VAULT_PATH` (default: `~/.colregs-vault`).

```
<vault>/
  rules/
    international/
      rule-01.md
      rule-02.md
      …
    inland/
      rule-01.md
      …
    canadian/
      rule-01.md
      …
  requirements.yaml        # curated light/shape requirements per vessel profile
  regime-polygons.geojson  # polygon boundaries for US Inland and Canadian waters
  manifest.yaml            # vault metadata (version, source attribution)
```

Each `rule-NN.md` file has YAML front-matter with fields `number`, `regime`, `part`, `title`, and optionally `source_pdf` (back-link to the source document and page).

---

## Profile Schema

Several tools accept a `profile` object describing the vessel situation:

```json
{
  "vessel_class": "power_driven | sailing | anchored | towing | being_towed | not_under_command | restricted_manoeuvrability | constrained_by_draught | fishing | pilot_vessel | vessel_aground | seaplane",
  "length_m": 12.5,
  "propulsion": "sail | machinery | sail_and_machinery",
  "regime": "international | inland | canadian",
  "condition": "day | night | restricted_visibility"
}
```

All fields are required for `required_signals` and `check_compliance`. `resolve_regime` does not use `profile`.

**Motorsailing note.** `propulsion: sail_and_machinery` (motorsailing) is treated as **power-driven** for lighting purposes. A motorsailing vessel must show the masthead steaming light at night and the black cone (apex down) by day — not a tricolor.

---

## Normalized Light/Shape ID Vocabulary

These identifiers are used in `requirements.yaml`, in the `observed` list passed to `check_compliance`, and in all tool responses. Agents must use these exact strings.

| ID | Description |
|---|---|
| `anchor_light` | All-round white anchor light |
| `masthead_steaming` | Masthead steaming light (white, forward arc 225°) |
| `sidelights` | Port (red) and starboard (green) sidelights |
| `sternlight` | White sternlight (135° arc aft) |
| `tricolor` | Combined tri-color (masthead, sailing vessels ≤20 m at sea) |
| `ball` | Black ball shape |
| `cone_apex_down` | Black cone shape, apex pointing down |
| `all_round_red_*` | All-round red light (suffix disambiguates when multiple apply) |

Additional IDs may appear in `requirements.yaml` for specialized vessel classes (e.g., `towing_light`, `flashing_yellow`, `all_round_green`). The vocabulary is open but curated — check `requirements.yaml` for the full set applicable to a given `vessel_class`.

---

## Tools

### `get_rule`

Return the full rule text for a single rule number, optionally filtered to one regime.

**Input:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `number` | string | yes | Rule number, e.g. `"25"` or `"Rule 25"` (normalized internally) |
| `regime` | `international \| inland \| canadian` | no | If omitted, all regimes are returned |

**Output (single regime):**

```json
{
  "found": true,
  "rule": {
    "number": "25",
    "regime": "international",
    "part": "C",
    "title": "Sailing Vessels Underway and Vessels Under Oars",
    "source_pdf": "colregs-72.pdf p. 14",
    "prose": "…full rule text…"
  }
}
```

**Output (all regimes, regime omitted):**

```json
{
  "found": true,
  "number": "25",
  "regimes": {
    "international": { "number": "25", "regime": "international", … },
    "inland": { "number": "25", "regime": "inland", … }
  }
}
```

When `found` is `false`, the rule object or regimes map is absent.

---

### `search_rules`

Keyword search over the vault. Deterministic ranking: matches in `title` outrank matches in `prose`; ties broken by rule number then regime.

**Input:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `query` | string | yes | — | Space-separated keywords |
| `regime` | `international \| inland \| canadian` | no | all | Restrict to one regime |
| `limit` | integer | no | 5 | Max hits to return |

**Output:**

```json
{
  "query": "sailing lights",
  "hits": [
    {
      "number": "25",
      "regime": "international",
      "title": "Sailing Vessels Underway and Vessels Under Oars",
      "excerpt": "…first matching sentence…",
      "citation": "Rule 25 (international)"
    }
  ]
}
```

An empty `hits` list is returned when no rules match — never an error.

---

### `resolve_regime`

Determine the applicable navigation regime for a geographic position using point-in-polygon lookup over `regime-polygons.geojson`. Defaults to `international` when no polygon matches (open ocean).

**Input:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `lat` | number | yes | Latitude (decimal degrees, WGS-84) |
| `lon` | number | yes | Longitude (decimal degrees, WGS-84) |

**Output:**

```json
{
  "lat": 48.5,
  "lon": -123.2,
  "regime": "international"
}
```

Possible `regime` values: `international`, `inland`, `canadian`.

---

### `required_signals`

Return the lights, shapes, and sound/fog signals required for a vessel in a given situation. Driven exclusively by `requirements.yaml` — deterministic for a given vault version.

**Input:** A `profile` object (see Profile Schema above).

**Output:**

```json
{
  "situation": "sailing",
  "matched": true,
  "lights": [
    { "id": "sidelights", "desc": "Port and starboard sidelights", "rule": "25(a)(i)" },
    { "id": "sternlight", "desc": "Sternlight", "rule": "25(a)(i)" }
  ],
  "light_options": [
    ["tricolor"],
    ["masthead_steaming", "sidelights", "sternlight"]
  ],
  "shapes": [],
  "forbids": ["masthead_steaming"],
  "citations": ["Rule 25 (international)"]
}
```

`light_options` is a list of option groups; each group is a list of light IDs. At least one complete group must be satisfied for full compliance. `forbids` lists IDs that must not be shown in this situation. `situation` is the derived effective situation. **`matched` is `false` when no `requirements.yaml` row covers the profile** — callers must treat that as "not modeled", never as "nothing required".

---

### `check_compliance`

Check whether the set of lights/shapes currently observed satisfies the requirements for the given situation.

**Input:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `profile` | object | yes | Vessel profile (see Profile Schema) |
| `observed` | array of string | yes | Light/shape IDs currently shown (from normalized vocabulary) |

**Output:**

```json
{
  "ok": false,
  "not_modeled": false,
  "missing": ["sternlight"],
  "extra": [],
  "unsatisfied_options": [["tricolor"], ["masthead_steaming", "sidelights", "sternlight"]],
  "satisfied": ["sidelights"],
  "citations": ["Rule 25 (international)"]
}
```

| Field | Description |
|---|---|
| `ok` | `true` only when the situation is modeled, `missing` is empty, `extra` is empty, and every option group has ≥1 group fully satisfied |
| `not_modeled` | `true` when no `requirements.yaml` row covers the profile; `ok` is forced `false` and a `note` field says "do not rely on this verdict" |
| `missing` | Required lights absent from `observed` |
| `extra` | Forbidden lights present in `observed` |
| `unsatisfied_options` | Option groups with no fully-satisfied group |
| `satisfied` | Required lights present in `observed` |
| `citations` | Rule references |

`extra` contains forbidden lights that are present. `ok` is `false` when any forbidden light is on, any mandatory light is missing, no option group is fully satisfied (when option groups exist), or the situation is not modeled at all. **Absence of a matching requirements row is never compliance** — an unmodeled situation returns `ok: false, not_modeled: true` so the agent warns instead of staying silent.

---

## Reverse identification

### Token vocabulary

- **Light colours** (night / restricted visibility): `red`, `white`, `green`, `yellow`.
  All-round assumed; sidelights, sternlight and masthead lights are confirmatory,
  never part of the stacked identity.
- **Day shapes**: `ball`, `diamond`, `cylinder`, `cone_up`, `cone_down`.

`arrangement` is an ordered list of tokens, top to bottom. Light and shape tokens
must not be mixed in one arrangement. The two namespaces are disjoint, so `kind`
(lights vs shapes) is inferred from the tokens and validated against `condition`
(shapes ⇒ `day`; lights ⇒ `night` / `restricted_visibility`).

### `identify_signals`

Input: `{ arrangement: string[], condition: "day"|"night"|"restricted_visibility", regime?: ... }`.
Output: `{ arrangement, condition, kind, matches: [...] }` where each match is
`{ match_type, pattern_id, mnemonic, candidates: [{situation, rule, note}], confirm: string[] }`.
`match_type` ranks results: `exact` → `superset` (a light may have been missed) →
`permutation` (top/bottom may be flipped). On an exact hit only exact matches are
returned; otherwise superset and permutation near-misses are returned, each flagged.
Errors (empty/mixed/unknown tokens, kind/condition mismatch) return `{ error, matches: [] }`
(a kind/condition mismatch also echoes `kind`).

### `list_signal_patterns`

Input: `{}`. Output: `{ light_colors, day_shapes, note, patterns: [{id, arrangement,
condition, mnemonic, situations}] }` — the vocabulary and catalog the LLM browses to
learn the exact tokens to pass to `identify_signals`.

---

## Error Handling

All tools return structured JSON. On vault load failure or missing `requirements.yaml`, the server starts but affected tools return `{"error": "…", "found": false}` rather than raising. This prevents a stale vault from crashing the agent runtime.

---

## Safety Note

`requirements.yaml` and `regime-polygons.geojson` are curated data files maintained alongside this server. The bundled `colregs-vault` is an **UNVERIFIED DRAFT** pending expert review. Do not use for real navigation decisions without independent verification against the official published rules.
