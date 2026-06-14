# COLREGS Part C Completeness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the reverse-identification catalog to the rest of COLREGS Part C — towing (incl. >200 m), being-towed, mine-clearance, aground, ≥50 m anchored, air-cushion, WIG, sailing's optional masthead, CBD/fishing day shapes, and the supplementary fishing signals (gear >150 m, Annex II) — adding the small model machinery they need (per-signal diagnostic `token`, pattern `geometry`, flashing light tokens, new vessel-classes).

**Architecture:** Three code changes unlock everything: (1) an explicit per-signal `token:` on `requirements.yaml` entries that the drift check honours, so *sector* lights (towing's masthead line, yellow towing light) can be diagnostic without rewriting the all-round heuristic; (2) an optional `geometry` field on sightings (`vertical`/`triangle`/`fore_and_aft`) that the matcher filters on like it already filters on top/bottom order, resolving the 3-ball aground-vs-minesweeper collision; (3) flashing light tokens and three new vessel-classes. The data then lands in `../colregs-vault` in incremental batches, each keeping the real-vault drift gate green. Reference: `docs/superpowers/specs/2026-06-14-part-c-completeness-design.md`.

**Tech Stack:** Python 3.11, `mcp` SDK, PyYAML, pytest, `uv`. Two repos: `colregs-mcp` (code) and the sibling `../colregs-vault` (data).

---

## File Structure

**colregs-mcp:**
- `src/colregs_mcp/models.py` — *modify*: `FLASHING_LIGHTS`, `LIGHT_TOKENS`, updated `token_kind`, `GEOMETRIES`, new `_SPECIAL` members.
- `src/colregs_mcp/vault.py` — *modify*: validate `geometry` on sightings; validate per-signal `token` on requirements.
- `src/colregs_mcp/sightings.py` — *modify*: drift honours per-signal `token`; matcher filters/returns `geometry`; `list_signal_patterns` surfaces geometry + flashing vocab.
- `src/colregs_mcp/tools.py` — *modify*: `identify_signals_tool` gains `geometry`.
- `src/colregs_mcp/server.py` — *modify*: `geometry` in the `identify_signals` input schema.
- Tests: `tests/test_models.py`, `tests/test_vault.py`, `tests/test_sightings.py`, `tests/test_sightings_drift.py`, `tests/test_server.py`.

**colregs-vault:**
- `requirements.yaml` — *modify*: new forward bands with explicit `token`s.
- `sightings.yaml` — *modify*: the new patterns with geometry.

---

## Task 1: Model vocabulary — flashing tokens, geometry set, new vessel-classes

**Files:**
- Modify: `src/colregs_mcp/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_models.py`:

```python
def test_token_kind_classifies_flashing_lights():
    from colregs_mcp.models import token_kind
    assert token_kind("flashing_yellow") == "lights"
    assert token_kind("flashing_red") == "lights"

def test_flashing_tokens_are_signal_tokens():
    from colregs_mcp.models import SIGNAL_TOKENS
    assert {"flashing_yellow", "flashing_red"} <= SIGNAL_TOKENS

def test_new_vessel_classes_present():
    from colregs_mcp.models import VESSEL_CLASSES
    assert {"mine_clearance", "air_cushion", "wig"} <= VESSEL_CLASSES

def test_geometries_vocabulary():
    from colregs_mcp.models import GEOMETRIES
    assert GEOMETRIES == {"vertical", "triangle", "fore_and_aft"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_models.py -k "flashing or new_vessel or geometries" -v`
Expected: FAIL — `ImportError`/`AssertionError` (names not defined).

- [ ] **Step 3: Implement**

In `src/colregs_mcp/models.py`, add the three new special states to `_SPECIAL`:

```python
_SPECIAL = frozenset({
    "anchored", "vessel_aground", "not_under_command", "restricted_manoeuvrability",
    "constrained_by_draught", "fishing", "towing", "being_towed", "pilot_vessel",
    "seaplane", "mine_clearance", "air_cushion", "wig",
})
```

Replace the reverse-identification vocabulary block (the `LIGHT_COLORS` / `DAY_SHAPES` / `SIGNAL_TOKENS` lines) with:

```python
# Reverse-identification vocabulary. Two disjoint token namespaces: light tokens
# (all-round colours assumed; sidelights/sternlight/masthead are confirmatory unless
# a requirements row declares them diagnostic) and day shapes. Flashing lights carry
# their own tokens. `kind` is inferred from the namespace.
LIGHT_COLORS = frozenset({"red", "white", "green", "yellow"})
FLASHING_LIGHTS = frozenset({"flashing_yellow", "flashing_red"})
LIGHT_TOKENS = LIGHT_COLORS | FLASHING_LIGHTS
DAY_SHAPES = frozenset({"ball", "diamond", "cylinder", "cone_up", "cone_down"})
SIGNAL_TOKENS = LIGHT_TOKENS | DAY_SHAPES

# How an observed arrangement is laid out. `vertical` is the default; `triangle`
# (mine-clearance) and `fore_and_aft` (towing, ≥50 m anchor lights) disambiguate
# signals that share a token multiset.
GEOMETRIES = frozenset({"vertical", "triangle", "fore_and_aft"})

# Shapes are a daytime signal; lights are shown at night and in restricted visibility.
SIGNAL_CONDITIONS = {"shapes": {"day"}, "lights": {"night", "restricted_visibility"}}
```

Update `token_kind` to use `LIGHT_TOKENS`:

```python
def token_kind(token: str) -> str:
    """'lights' for a colour/flashing token, 'shapes' for a day-shape token. Raises on
    unknown — an unrecognized token must never be silently dropped from an identification."""
    if token in LIGHT_TOKENS:
        return "lights"
    if token in DAY_SHAPES:
        return "shapes"
    raise ValueError(f"unknown signal token {token!r}; expected one of {sorted(SIGNAL_TOKENS)}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_models.py -v`
Expected: PASS (all, including the 4 new).

- [ ] **Step 5: Commit**

```bash
git add src/colregs_mcp/models.py tests/test_models.py
git commit -m "feat: flashing tokens, geometry vocabulary, mine-clearance/air-cushion/wig classes"
```

---

## Task 2: Validate `geometry` (sightings) and per-signal `token` (requirements)

**Files:**
- Modify: `src/colregs_mcp/vault.py`
- Test: `tests/test_vault.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_vault.py`:

```python
def test_sightings_accepts_geometry(tmp_path):
    (tmp_path / "sightings.yaml").write_text(
        "version: 1\n"
        "patterns:\n"
        "  - id: tri\n"
        "    arrangement: [green, green, green]\n"
        "    condition: night\n"
        "    geometry: triangle\n"
        "    candidates: [{ situation: mine_clearance, rule: 'Rule 27(f)' }]\n",
        encoding="utf-8")
    v = Vault.load(tmp_path)
    assert v.sightings.patterns[0]["geometry"] == "triangle"

def test_sightings_rejects_unknown_geometry(tmp_path):
    import pytest
    (tmp_path / "sightings.yaml").write_text(
        "version: 1\n"
        "patterns:\n"
        "  - id: bad-geo\n"
        "    arrangement: [red, red]\n"
        "    condition: night\n"
        "    geometry: sideways\n"
        "    candidates: [{ situation: not_under_command, rule: 'Rule 27' }]\n",
        encoding="utf-8")
    with pytest.raises(ValueError, match="unknown geometry"):
        Vault.load(tmp_path)

def test_requirements_rejects_unknown_token(tmp_path):
    import pytest
    (tmp_path / "requirements.yaml").write_text(
        "version: 1\n"
        "entries:\n"
        "  - id: bad-token\n"
        "    match: { situation: towing, condition: night }\n"
        "    lights: [{ id: x, token: chartreuse, rule: 'Rule 24' }]\n",
        encoding="utf-8")
    with pytest.raises(ValueError, match="unknown token"):
        Vault.load(tmp_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_vault.py -k "geometry or unknown_token" -v`
Expected: FAIL — geometry not stored / no token validation.

- [ ] **Step 3: Implement geometry validation in `_validate_sightings`**

In `src/colregs_mcp/vault.py`, extend the models import to add `GEOMETRIES`:

```python
from colregs_mcp.models import (
    CONDITIONS, GEOMETRIES, REGIMES, SIGNAL_CONDITIONS, SIGNAL_TOKENS, SITUATIONS,
    Rule, token_kind,
)
```

In `_validate_sightings`, after the `regime` check and before the `candidates` check, add:

```python
        geometry = p.get("geometry")
        if geometry is not None and geometry not in GEOMETRIES:
            raise ValueError(f"sightings.yaml: {ident} has unknown geometry {geometry!r}; "
                             f"allowed: {sorted(GEOMETRIES)}")
```

- [ ] **Step 4: Implement token validation in `_validate_entries`**

`requirements.yaml` signals may now declare a `token`. Validate it. In `_validate_entries` (in `vault.py`), add a helper call. First add this module-level helper just above `_validate_entries`:

```python
def _validate_signal_tokens(ident: str, entry: dict) -> None:
    """A requirements signal may declare an explicit reverse-ID `token`; if present it
    must be a known signal token (or null, meaning 'not diagnostic')."""
    groups = [entry.get("lights", []), entry.get("shapes", [])]
    groups += list(entry.get("light_options", []))
    for group in groups:
        for sig in group:
            if isinstance(sig, dict) and "token" in sig:
                tok = sig["token"]
                if tok is not None and tok not in SIGNAL_TOKENS:
                    raise ValueError(f"requirements.yaml: {ident} signal {sig.get('id')!r} "
                                     f"has unknown token {tok!r}; allowed: {sorted(SIGNAL_TOKENS)}")
```

Then call it inside `_validate_entries`'s per-entry loop, after the existing match-key checks (i.e. just before the loop's end):

```python
        _validate_signal_tokens(ident, entry)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_vault.py -v`
Expected: PASS (all, including the 3 new).

- [ ] **Step 6: Commit**

```bash
git add src/colregs_mcp/vault.py tests/test_vault.py
git commit -m "feat: validate sighting geometry and requirement signal tokens"
```

---

## Task 3: Drift check honours per-signal `token` (Approach A)

**Files:**
- Modify: `src/colregs_mcp/sightings.py`
- Test: `tests/test_sightings_drift.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_sightings_drift.py`:

```python
def test_explicit_token_makes_sector_light_diagnostic():
    # towing's yellow towing light + sternlight (declared white) form a [yellow, white] band.
    reqs = Requirements(entries=[
        {"id": "towing-stern", "match": {"situation": "towing", "condition": "night"},
         "lights": [{"id": "towing_light", "token": "yellow", "rule": "R24"},
                    {"id": "sternlight", "token": "white", "rule": "R24"}]},
    ])
    ok = Sightings(patterns=[
        {"id": "tow-aft", "arrangement": ["yellow", "white"], "condition": "night",
         "candidates": [{"situation": "towing", "rule": "R24"}]},
    ])
    assert sightings_drift(ok, reqs) == []

def test_null_token_suppresses_heuristic():
    # aground shows two reds + an anchor light; token:null keeps the anchor light out of
    # the band so the recognizable signal stays [red, red] (not [red, red, white]).
    reqs = Requirements(entries=[
        {"id": "aground", "match": {"situation": "vessel_aground", "condition": "night"},
         "lights": [{"id": "all_round_red_upper", "rule": "R30"},
                    {"id": "all_round_red_lower", "rule": "R30"},
                    {"id": "anchor_light", "token": None, "rule": "R30"}]},
    ])
    ok = Sightings(patterns=[
        {"id": "ag", "arrangement": ["red", "red"], "condition": "night",
         "candidates": [{"situation": "vessel_aground", "rule": "R30"}]},
    ])
    assert sightings_drift(ok, reqs) == []

def test_flashing_token_band():
    reqs = Requirements(entries=[
        {"id": "ac", "match": {"situation": "air_cushion", "condition": "night"},
         "lights": [{"id": "fy", "token": "flashing_yellow", "rule": "R23"}]},
    ])
    ok = Sightings(patterns=[
        {"id": "acs", "arrangement": ["flashing_yellow"], "condition": "night",
         "candidates": [{"situation": "air_cushion", "rule": "R23"}]},
    ])
    assert sightings_drift(ok, reqs) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_sightings_drift.py -k "explicit_token or null_token or flashing" -v`
Expected: FAIL — `towing_light`/`sternlight`/`fy` resolve via the heuristic to None, so the bands are wrong.

- [ ] **Step 3: Implement**

In `src/colregs_mcp/sightings.py`, add a resolver above `_entry_token_bands`:

```python
def _diagnostic_token(sig: dict) -> str | None:
    """The reverse-ID token for one requirements signal. An explicit `token` key wins
    (a value, or null to force 'not diagnostic'); otherwise fall back to the all-round
    id heuristic."""
    if "token" in sig:
        return sig["token"]
    return _signal_token(sig["id"])
```

In `_entry_token_bands`, replace the token-extraction line:

```python
        tokens = sorted(t for sig in sigs if (t := _diagnostic_token(sig)) is not None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_sightings_drift.py -v`
Expected: PASS (all, including the 3 new). The real-vault gate (if present) still passes — existing rows have no `token` key and use the heuristic unchanged.

- [ ] **Step 5: Commit**

```bash
git add src/colregs_mcp/sightings.py tests/test_sightings_drift.py
git commit -m "feat: drift check honours explicit per-signal tokens (incl. null to suppress)"
```

---

## Task 4: Matcher filters and returns `geometry`

**Files:**
- Modify: `src/colregs_mcp/sightings.py`
- Test: `tests/test_sightings.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_sightings.py` (these build `Sightings` directly, no fixture needed):

```python
from colregs_mcp.vault import Sightings

def _geo_catalog():
    return Sightings(patterns=[
        {"id": "aground-day", "arrangement": ["ball", "ball", "ball"], "condition": "day",
         "candidates": [{"situation": "vessel_aground", "rule": "R30"}]},   # geometry defaults vertical
        {"id": "minesweep-day", "arrangement": ["ball", "ball", "ball"], "condition": "day",
         "geometry": "triangle",
         "candidates": [{"situation": "mine_clearance", "rule": "R27"}]},
    ])

def test_geometry_omitted_returns_both_with_geometry_labels():
    out = identify_signals(_geo_catalog(), ["ball", "ball", "ball"], "day")
    sits = {c["situation"] for m in out["matches"] for c in m["candidates"]}
    geos = {m["geometry"] for m in out["matches"]}
    assert sits == {"vessel_aground", "mine_clearance"}
    assert geos == {"vertical", "triangle"}

def test_geometry_given_filters_to_matching_geometry():
    out = identify_signals(_geo_catalog(), ["ball", "ball", "ball"], "day", geometry="triangle")
    assert [c["situation"] for m in out["matches"] for c in m["candidates"]] == ["mine_clearance"]

def test_geometry_defaults_vertical_when_pattern_omits_it():
    out = identify_signals(_geo_catalog(), ["ball", "ball", "ball"], "day", geometry="vertical")
    assert [c["situation"] for m in out["matches"] for c in m["candidates"]] == ["vessel_aground"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_sightings.py -k geometry -v`
Expected: FAIL — `identify_signals` takes no `geometry` and `_match` has no `geometry` key.

- [ ] **Step 3: Implement**

In `src/colregs_mcp/sightings.py`, update `_match` to carry geometry:

```python
def _match(pattern: dict, match_type: str) -> dict:
    return {
        "match_type": match_type,
        "pattern_id": pattern["id"],
        "mnemonic": pattern.get("mnemonic"),
        "geometry": pattern.get("geometry", "vertical"),
        "candidates": pattern["candidates"],
        "confirm": pattern.get("confirm", []),
    }
```

Update `identify_signals`'s signature and pool filter:

```python
def identify_signals(sightings: Sightings, arrangement, condition: str,
                     regime: str | None = None, geometry: str | None = None) -> dict:
```

and, inside it, replace the `pool = [...]` comprehension with one that also filters geometry when the caller supplies it:

```python
    def geometry_ok(p: dict) -> bool:
        return geometry is None or p.get("geometry", "vertical") == geometry

    pool = [p for p in sightings.patterns
            if p["condition"] == condition and regime_ok(p) and geometry_ok(p)
            and _infer_kind(p["arrangement"]) == kind]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_sightings.py -v`
Expected: PASS (all, including the 3 new).

- [ ] **Step 5: Commit**

```bash
git add src/colregs_mcp/sightings.py tests/test_sightings.py
git commit -m "feat: identify_signals filters and returns pattern geometry"
```

---

## Task 5: Surface geometry + flashing vocab through the tool layer

**Files:**
- Modify: `src/colregs_mcp/sightings.py`, `src/colregs_mcp/tools.py`, `src/colregs_mcp/server.py`
- Test: `tests/test_sightings.py`, `tests/test_server.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_sightings.py`:

```python
def test_list_signal_patterns_includes_flashing_and_geometry():
    from colregs_mcp.sightings import list_signal_patterns
    s = Sightings(patterns=[
        {"id": "tri", "arrangement": ["green", "green", "green"], "condition": "night",
         "geometry": "triangle",
         "candidates": [{"situation": "mine_clearance", "rule": "R27"}]},
    ])
    out = list_signal_patterns(s)
    assert "flashing_yellow" in out["flashing_lights"]
    assert out["patterns"][0]["geometry"] == "triangle"
```

Add to `tests/test_server.py`:

```python
def test_identify_signals_schema_exposes_geometry_enum():
    import asyncio, mcp.types as types
    from colregs_mcp.models import GEOMETRIES
    from colregs_mcp.server import build_server
    server = build_server(_vault())
    handler = server.request_handlers[types.ListToolsRequest]
    result = asyncio.run(handler(types.ListToolsRequest(method="tools/list")))
    tool = next(t for t in result.root.tools if t.name == "identify_signals")
    assert set(tool.inputSchema["properties"]["geometry"]["enum"]) == set(GEOMETRIES)

def test_dispatch_identify_signals_passes_geometry():
    out = dispatch(_vault(), "identify_signals",
                   {"arrangement": ["red", "red"], "condition": "night", "geometry": "vertical"})
    assert out["matches"]  # red-over-red is vertical, so it still matches
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_sightings.py -k flashing_and_geometry tests/test_server.py -k "geometry or passes_geometry" -v`
Expected: FAIL — no `flashing_lights` key, no `geometry` in schema, dispatch drops geometry.

- [ ] **Step 3: Update `list_signal_patterns`**

In `src/colregs_mcp/sightings.py`, add `FLASHING_LIGHTS` to the import:

```python
from colregs_mcp.models import (
    DAY_SHAPES, FLASHING_LIGHTS, LIGHT_COLORS, SIGNAL_CONDITIONS, token_kind,
)
```

and update `list_signal_patterns`:

```python
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
```

- [ ] **Step 4: Update the tool wrapper and server schema**

In `src/colregs_mcp/tools.py`, update `identify_signals_tool`:

```python
def identify_signals_tool(vault: Vault, arrangement, condition: str,
                          regime: str | None = None, geometry: str | None = None) -> dict:
    return identify_signals(vault.sightings, arrangement or [], condition, regime, geometry)
```

In `src/colregs_mcp/server.py`, in `dispatch`, pass geometry:

```python
    if name == "identify_signals":
        return tools.identify_signals_tool(vault, arrangement=args["arrangement"],
                                           condition=args["condition"], regime=args.get("regime"),
                                           geometry=args.get("geometry"))
```

and in the `identify_signals` `types.Tool(...)` registration, add a `geometry` property to its `inputSchema["properties"]` (alongside `arrangement`, `condition`, `regime`):

```python
                    "geometry": {"type": "string", "enum": sorted(models_vocab.GEOMETRIES),
                                 "description": "layout, if known: vertical (default), triangle, or fore_and_aft"},
```

Also extend the `identify_signals` tool `description` with a sentence on geometry:

```python
                description=("Identify a vessel from its lights or shapes. Given an observed "
                             "top-to-bottom arrangement of all-round light colours (night) or day "
                             "shapes, returns ranked candidate vessel states with rule citations and "
                             "confirm cues; each match_type is exact, superset (a light may have been "
                             "missed), or permutation (top/bottom may be flipped). Pass geometry "
                             "(triangle/fore_and_aft) when the lights are not a vertical stack."),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_sightings.py tests/test_server.py -v`
Expected: PASS (all, including the new ones).

- [ ] **Step 6: Run the full suite (no regressions)**

Run: `uv run pytest -q`
Expected: PASS (all).

- [ ] **Step 7: Commit**

```bash
git add src/colregs_mcp/sightings.py src/colregs_mcp/tools.py src/colregs_mcp/server.py tests/test_sightings.py tests/test_server.py
git commit -m "feat: expose geometry input/output and flashing vocabulary through the tools"
```

---

## Task 6: Vault data — towing & being-towed

**Files:**
- Modify: `../colregs-vault/requirements.yaml`, `../colregs-vault/sightings.yaml`
- Test: `tests/test_real_vault_drift.py` (existing gate), `tests/test_sightings.py`

> **Drift rule (applies to every data task):** for each sighting candidate, the sorted token multiset of the arrangement must equal a band the matching requirements entries produce. `[yellow, white]` sorts to `[white, yellow]`. The real-vault gate enforces this; never weaken it to pass.

- [ ] **Step 1: Append the towing requirements entries**

Append to `../colregs-vault/requirements.yaml` (under `entries:`, matching the existing 2-space style):

```yaml
  - id: towing-masthead-night
    match: { situation: towing, condition: night }
    light_options:
      - [{ id: masthead_white_1, token: white, desc: "masthead light, forward", rule: "Rule 24(a)(i)" }, { id: masthead_white_2, token: white, desc: "masthead light below the first (vertical line)", rule: "Rule 24(a)(i)" }]
      - [{ id: masthead_white_1, token: white, desc: "masthead light, forward", rule: "Rule 24(c)" }, { id: masthead_white_2, token: white, desc: "second masthead light", rule: "Rule 24(c)" }, { id: masthead_white_3, token: white, desc: "third masthead light (tow exceeds 200 m)", rule: "Rule 24(c)" }]
  - id: towing-stern-night
    match: { situation: towing, condition: night }
    lights:
      - { id: towing_light, token: yellow, desc: "yellow towing light above the sternlight", rule: "Rule 24(a)(iv)" }
      - { id: sternlight, token: white, desc: "sternlight", rule: "Rule 24(a)(iii)" }
  - id: towing-day-over-200m
    match: { situation: towing, condition: day }
    shapes:
      - { id: diamond, desc: "diamond where best seen — tow exceeds 200 m", rule: "Rule 24(a)(v)" }
  - id: being-towed-day-over-200m
    match: { situation: being_towed, condition: day }
    shapes:
      - { id: diamond, desc: "diamond where best seen — tow exceeds 200 m", rule: "Rule 24(e)(ii)" }
```

- [ ] **Step 2: Append the towing sightings patterns**

Append to `../colregs-vault/sightings.yaml` (under `patterns:`):

```yaml
  - id: towing-masthead-2-night
    arrangement: [white, white]
    condition: night
    candidates:
      - situation: towing
        rule: "Rule 24(a)"
        note: "Two white masthead lights in a vertical line — towing, tow 200 m or less."
    confirm:
      - "Three whites in the vertical line → tow exceeds 200 m."
      - "Two whites that are fore-and-aft (forward higher) and stationary → a vessel 50 m+ at ANCHOR, not towing."
      - "Includes pushing ahead / towing alongside (Rule 24(c))."
  - id: towing-masthead-3-night
    arrangement: [white, white, white]
    condition: night
    candidates:
      - situation: towing
        rule: "Rule 24(c)"
        note: "Three white masthead lights in a vertical line — tow exceeds 200 m."
  - id: towing-light-aft-night
    arrangement: [yellow, white]
    condition: night
    geometry: fore_and_aft
    mnemonic: "yellow over white, towing tonight"
    candidates:
      - situation: towing
        rule: "Rule 24(a)"
        note: "Yellow towing light directly above the white sternlight, seen from astern."
  - id: tow-diamond-day
    arrangement: [diamond]
    condition: day
    candidates:
      - situation: towing
        rule: "Rule 24(a)(v)"
        note: "Diamond shape — tow exceeds 200 m (shown by towing vessel and tow)."
      - situation: being_towed
        rule: "Rule 24(e)(ii)"
        note: "The towed vessel/object shows the same diamond."
```

- [ ] **Step 3: Run the drift gate + a focused matcher check**

Add to `tests/test_sightings.py`:

```python
def test_real_vault_towing_yellow_over_white(tmp_path):
    import pytest
    from pathlib import Path
    REAL = Path(__file__).resolve().parents[2] / "colregs-vault"
    if not (REAL / "sightings.yaml").is_file():
        pytest.skip("sibling colregs-vault not present")
    from colregs_mcp.vault import Vault
    v = Vault.load(REAL)
    out = identify_signals(v.sightings, ["yellow", "white"], "night", geometry="fore_and_aft")
    assert any(c["situation"] == "towing" for m in out["matches"] for c in m["candidates"])
```

Run: `uv run pytest tests/test_real_vault_drift.py tests/test_sightings.py -k "drift or towing" -v`
Expected: PASS — real-vault drift gate green; the towing aft view resolves to `towing`.

- [ ] **Step 4: Commit (both repos)**

```bash
git -C ../colregs-vault add requirements.yaml sightings.yaml
git -C ../colregs-vault commit -m "feat: towing and being-towed reverse-id signals (draft)"
git add tests/test_sightings.py
git commit -m "test: towing reverse-id against the real vault"
```

---

## Task 7: Vault data — mine-clearance, aground, ≥50 m anchored (the geometry cases)

**Files:**
- Modify: `../colregs-vault/requirements.yaml`, `../colregs-vault/sightings.yaml`
- Test: `tests/test_real_vault_drift.py`, `tests/test_sightings.py`

- [ ] **Step 1: Append the requirements entries**

Append to `../colregs-vault/requirements.yaml`:

```yaml
  - id: mine-clearance-night
    match: { situation: mine_clearance, condition: night }
    lights:
      - { id: all_round_green_masthead, desc: "all-round green at the foremast head", rule: "Rule 27(f)" }
      - { id: all_round_green_yard_1, desc: "all-round green, one end of the fore yard", rule: "Rule 27(f)" }
      - { id: all_round_green_yard_2, desc: "all-round green, other end of the fore yard", rule: "Rule 27(f)" }
  - id: mine-clearance-day
    match: { situation: mine_clearance, condition: day }
    shapes:
      - { id: ball_masthead, token: ball, desc: "ball at the foremast head", rule: "Rule 27(f)" }
      - { id: ball_yard_1, token: ball, desc: "ball, one end of the fore yard", rule: "Rule 27(f)" }
      - { id: ball_yard_2, token: ball, desc: "ball, other end of the fore yard", rule: "Rule 27(f)" }
  - id: aground-night
    match: { situation: vessel_aground, condition: night }
    lights:
      - { id: all_round_red_upper, desc: "all-round red", rule: "Rule 30(d)(i)" }
      - { id: all_round_red_lower, desc: "all-round red, below the first", rule: "Rule 30(d)(i)" }
      - { id: anchor_light, token: null, desc: "anchor light(s) also shown (context, not part of the two-red signal)", rule: "Rule 30(d)" }
  - id: aground-day
    match: { situation: vessel_aground, condition: day }
    shapes:
      - { id: ball_upper, token: ball, desc: "ball, uppermost", rule: "Rule 30(d)(ii)" }
      - { id: ball_middle, token: ball, desc: "ball, middle", rule: "Rule 30(d)(ii)" }
      - { id: ball_lower, token: ball, desc: "ball, lowest", rule: "Rule 30(d)(ii)" }
  - id: anchored-over-50m-night
    match: { situation: anchored, condition: night, length_gte: 50 }
    lights:
      - { id: anchor_light_forward, token: white, desc: "forward anchor light, higher", rule: "Rule 30(a)(i)" }
      - { id: anchor_light_aft, token: white, desc: "after anchor light, lower", rule: "Rule 30(a)(ii)" }
```

- [ ] **Step 2: Append/extend the sightings patterns**

Append these new patterns to `../colregs-vault/sightings.yaml`:

```yaml
  - id: minesweep-3-green-night
    arrangement: [green, green, green]
    condition: night
    geometry: triangle
    mnemonic: "three greens, mines unseen"
    candidates:
      - situation: mine_clearance
        rule: "Rule 27(f)"
        note: "Three all-round greens in a triangle — keep 1000 m clear."
  - id: minesweep-3-ball-day
    arrangement: [ball, ball, ball]
    condition: day
    geometry: triangle
    candidates:
      - situation: mine_clearance
        rule: "Rule 27(f)"
        note: "Three balls in a triangle (masthead + both yard-ends)."
  - id: aground-3-ball-day
    arrangement: [ball, ball, ball]
    condition: day
    candidates:
      - situation: vessel_aground
        rule: "Rule 30(d)(ii)"
        note: "Three balls in a VERTICAL line — aground."
    confirm:
      - "Three balls in a TRIANGLE → mine-clearance (Rule 27(f)), not aground."
  - id: anchored-two-white-night
    arrangement: [white, white]
    condition: night
    geometry: fore_and_aft
    candidates:
      - situation: anchored
        rule: "Rule 30(a)"
        note: "Forward (higher) and after (lower) anchor lights — vessel 50 m or more, at anchor."
    confirm:
      - "Two whites in a VERTICAL line → towing (Rule 24), not anchored."
```

Then extend the existing `red-over-red-night` pattern in `../colregs-vault/sightings.yaml`: add `vessel_aground` as a second candidate (its confirm already mentions aground). Its `candidates:` block becomes:

```yaml
    candidates:
      - situation: not_under_command
        rule: "Rule 27(a)"
        note: "Two all-round reds in a vertical line."
      - situation: vessel_aground
        rule: "Rule 30(d)(i)"
        note: "Two all-round reds — if also showing anchor light(s) and not making way, aground."
```

- [ ] **Step 3: Run the drift gate + collision checks**

Add to `tests/test_sightings.py`:

```python
def test_real_vault_three_ball_geometry_collision(tmp_path):
    import pytest
    from pathlib import Path
    REAL = Path(__file__).resolve().parents[2] / "colregs-vault"
    if not (REAL / "sightings.yaml").is_file():
        pytest.skip("sibling colregs-vault not present")
    from colregs_mcp.vault import Vault
    v = Vault.load(REAL)
    both = identify_signals(v.sightings, ["ball", "ball", "ball"], "day")
    sits = {c["situation"] for m in both["matches"] for c in m["candidates"]}
    assert {"vessel_aground", "mine_clearance"} <= sits
    tri = identify_signals(v.sightings, ["ball", "ball", "ball"], "day", geometry="triangle")
    assert [c["situation"] for m in tri["matches"] for c in m["candidates"]] == ["mine_clearance"]
```

Run: `uv run pytest tests/test_real_vault_drift.py tests/test_sightings.py -k "drift or three_ball" -v`
Expected: PASS — drift gate green; the 3-ball collision splits by geometry.

- [ ] **Step 4: Commit (both repos)**

```bash
git -C ../colregs-vault add requirements.yaml sightings.yaml
git -C ../colregs-vault commit -m "feat: mine-clearance, aground, and 50 m+ anchor reverse-id signals (draft)"
git add tests/test_sightings.py
git commit -m "test: 3-ball geometry collision against the real vault"
```

---

## Task 8: Vault data — air-cushion, WIG, sailing masthead, CBD day, fishing day shape

**Files:**
- Modify: `../colregs-vault/requirements.yaml`, `../colregs-vault/sightings.yaml`
- Test: `tests/test_real_vault_drift.py`

- [ ] **Step 1: Append the requirements entries**

Append to `../colregs-vault/requirements.yaml`:

```yaml
  - id: air-cushion-night
    match: { situation: air_cushion, condition: night }
    lights:
      - { id: flashing_yellow_allround, token: flashing_yellow, desc: "all-round flashing yellow (non-displacement mode)", rule: "Rule 23(b)" }
  - id: wig-night
    match: { situation: wig, condition: night }
    lights:
      - { id: flashing_red_hi_intensity, token: flashing_red, desc: "high-intensity all-round flashing red (taking off / landing / in flight)", rule: "Rule 23(c)" }
  - id: sailing-masthead-night
    match: { situation: sailing, condition: night }
    lights:
      - { id: all_round_red_masthead, desc: "all-round red at the masthead", rule: "Rule 25(c)" }
      - { id: all_round_green_masthead_low, desc: "all-round green below the red", rule: "Rule 25(c)" }
  - id: constrained-by-draught-day
    match: { situation: constrained_by_draught, condition: day }
    shapes:
      - { id: cylinder, desc: "cylinder where best seen", rule: "Rule 28" }
  - id: fishing-day
    match: { situation: fishing, condition: day }
    shapes:
      - { id: cone_apex_down, desc: "upper cone, apex downward", rule: "Rule 26(c)(i)" }
      - { id: cone_apex_up, desc: "lower cone, apex upward (apexes together)", rule: "Rule 26(c)(i)" }
```

> Note: `all_round_green_masthead_low` ends with `_low`, so the heuristic still maps it to `green` (it starts with `all_round_green_`). The two masthead lights yield band `[green, red]`.

- [ ] **Step 2: Append the sightings patterns**

Append to `../colregs-vault/sightings.yaml`:

```yaml
  - id: air-cushion-night
    arrangement: [flashing_yellow]
    condition: night
    candidates:
      - situation: air_cushion
        rule: "Rule 23(b)"
        note: "All-round flashing yellow (in addition to ordinary power-driven lights)."
  - id: wig-night
    arrangement: [flashing_red]
    condition: night
    candidates:
      - situation: wig
        rule: "Rule 23(c)"
        note: "High-intensity all-round flashing red — WIG craft taking off, landing, or in flight."
  - id: sailing-red-over-green-night
    arrangement: [red, green]
    condition: night
    mnemonic: "red over green, sailing machine"
    candidates:
      - situation: sailing
        rule: "Rule 25(c)"
        note: "Optional all-round red over green at the masthead (with sidelights + sternlight below)."
  - id: cbd-cylinder-day
    arrangement: [cylinder]
    condition: day
    candidates:
      - situation: constrained_by_draught
        rule: "Rule 28"
        note: "A cylinder — constrained by draught."
  - id: fishing-cones-day
    arrangement: [cone_down, cone_up]
    condition: day
    candidates:
      - situation: fishing
        rule: "Rule 26(c)(i)"
        note: "Two cones with apexes together (upper apex down, lower apex up)."
```

- [ ] **Step 3: Run the drift gate**

Run: `uv run pytest tests/test_real_vault_drift.py -v`
Expected: PASS (1, not skipped). If any drift is reported, fix the offending row's tokens/arrangement — do not weaken the gate.

- [ ] **Step 4: Commit (vault repo)**

```bash
git -C ../colregs-vault add requirements.yaml sightings.yaml
git -C ../colregs-vault commit -m "feat: air-cushion, WIG, sailing masthead, CBD day, fishing day reverse-id signals (draft)"
```

---

## Task 9: Vault data — fishing supplementary signals (gear, Annex II)

**Files:**
- Modify: `../colregs-vault/requirements.yaml`, `../colregs-vault/sightings.yaml`
- Test: `tests/test_real_vault_drift.py`, `tests/test_sightings.py`

- [ ] **Step 1: Append the requirements entries**

Append to `../colregs-vault/requirements.yaml`:

```yaml
  - id: fishing-gear-day
    match: { situation: fishing, condition: day }
    shapes:
      - { id: cone_apex_up, desc: "cone, apex up, toward outlying gear (gear extends over 150 m)", rule: "Rule 26(c)(ii)" }
  - id: fishing-annex2-night
    match: { situation: fishing, condition: night }
    light_options:
      - [{ id: shoot_white_1, token: white, desc: "two white in a vertical line — shooting nets", rule: "Annex II 2(a)" }, { id: shoot_white_2, token: white, desc: "lower white", rule: "Annex II 2(a)" }]
      - [{ id: haul_white, token: white, desc: "white over red — hauling nets", rule: "Annex II 2(b)" }, { id: haul_red, token: red, desc: "lower red", rule: "Annex II 2(b)" }]
      - [{ id: netfast_red_1, token: red, desc: "two red in a vertical line — net fast on an obstruction", rule: "Annex II 2(c)" }, { id: netfast_red_2, token: red, desc: "lower red", rule: "Annex II 2(c)" }]
      - [{ id: purse_yellow_1, token: flashing_yellow, desc: "two yellow flashing alternately — purse-seine hampered by gear", rule: "Annex II 3" }, { id: purse_yellow_2, token: flashing_yellow, desc: "lower yellow", rule: "Annex II 3" }]
```

- [ ] **Step 2: Append/extend the sightings patterns**

Append these new patterns to `../colregs-vault/sightings.yaml`:

```yaml
  - id: fishing-gear-cone-up-day
    arrangement: [cone_up]
    condition: day
    candidates:
      - situation: fishing
        rule: "Rule 26(c)(ii)"
        note: "A single cone apex-up shown toward outlying gear extending over 150 m."
  - id: fishing-shooting-night
    arrangement: [white, white]
    condition: night
    candidates:
      - situation: fishing
        rule: "Annex II 2(a)"
        note: "Two whites in a vertical line — trawler shooting nets (in addition to green-over-white)."
    confirm:
      - "Also showing green-over-white → confirms a trawler. Vertical whites with a towing config → towing."
  - id: fishing-hauling-night
    arrangement: [white, red]
    condition: night
    candidates:
      - situation: fishing
        rule: "Annex II 2(b)"
        note: "White over red — trawler hauling nets (in addition to green-over-white)."
    confirm:
      - "On a pilot station with no trawling lights → pilot vessel (Rule 29), not hauling."
  - id: fishing-purse-seine-night
    arrangement: [flashing_yellow, flashing_yellow]
    condition: night
    candidates:
      - situation: fishing
        rule: "Annex II 3"
        note: "Two yellow lights flashing alternately every second — purse-seiner hampered by its gear."
```

Then extend the existing `red-over-red-night` pattern (which already lists `not_under_command` and `vessel_aground` after Task 7): add a third candidate. Its `candidates:` block becomes:

```yaml
    candidates:
      - situation: not_under_command
        rule: "Rule 27(a)"
        note: "Two all-round reds in a vertical line."
      - situation: vessel_aground
        rule: "Rule 30(d)(i)"
        note: "Two all-round reds — if also showing anchor light(s) and not making way, aground."
      - situation: fishing
        rule: "Annex II 2(c)"
        note: "Two reds — a trawler with its net fast on an obstruction (with green-over-white)."
```

Also add a fishing-at-anchor confirm to the existing `red-over-white-night` and `green-over-white-night` patterns — append this line to each pattern's `confirm:` list (create the `confirm:` key on `green-over-white-night` if absent):

```yaml
      - "A fishing vessel shows these at anchor too; fishing lights do not imply making way."
```

- [ ] **Step 3: Run the drift gate + collision checks**

Add to `tests/test_sightings.py`:

```python
def test_real_vault_red_red_three_candidates(tmp_path):
    import pytest
    from pathlib import Path
    REAL = Path(__file__).resolve().parents[2] / "colregs-vault"
    if not (REAL / "sightings.yaml").is_file():
        pytest.skip("sibling colregs-vault not present")
    from colregs_mcp.vault import Vault
    v = Vault.load(REAL)
    out = identify_signals(v.sightings, ["red", "red"], "night")
    sits = {c["situation"] for m in out["matches"] for c in m["candidates"]}
    assert {"not_under_command", "vessel_aground", "fishing"} <= sits

def test_real_vault_white_red_pilot_and_fishing(tmp_path):
    import pytest
    from pathlib import Path
    REAL = Path(__file__).resolve().parents[2] / "colregs-vault"
    if not (REAL / "sightings.yaml").is_file():
        pytest.skip("sibling colregs-vault not present")
    from colregs_mcp.vault import Vault
    v = Vault.load(REAL)
    out = identify_signals(v.sightings, ["white", "red"], "night")
    sits = {c["situation"] for m in out["matches"] for c in m["candidates"]}
    assert {"pilot_vessel", "fishing"} <= sits
```

Run: `uv run pytest tests/test_real_vault_drift.py tests/test_sightings.py -k "drift or three_candidates or pilot_and_fishing" -v`
Expected: PASS — drift gate green; `[red,red]` returns NUC+aground+fishing; `[white,red]` returns pilot+fishing.

- [ ] **Step 4: Commit (both repos)**

```bash
git -C ../colregs-vault add requirements.yaml sightings.yaml
git -C ../colregs-vault commit -m "feat: fishing supplementary signals — gear, Annex II, at-anchor (draft)"
git add tests/test_sightings.py
git commit -m "test: fishing collisions against the real vault"
```

---

## Task 10: Documentation + final verification

**Files:**
- Modify: `README.md`, `SPEC.md`
- Test: full suite

- [ ] **Step 1: Update SPEC.md — token vocabulary and new fields**

In `SPEC.md`, in the "Reverse identification" section's "Token vocabulary" list, add the flashing lights and geometry. After the day-shapes bullet, add:

```markdown
- **Flashing lights** (night): `flashing_yellow` (air-cushion, Rule 23(b)),
  `flashing_red` (WIG craft, Rule 23(c)).

`geometry` is an optional per-pattern layout — `vertical` (default), `triangle`
(mine-clearance), or `fore_and_aft` (towing, ≥50 m anchor lights). `identify_signals`
accepts an optional `geometry` argument: when supplied it must match the pattern's
geometry; when omitted, all geometries are returned and each match carries its own.
A `requirements.yaml` signal may declare an explicit `token:` (a reverse-ID token, or
`null` to mark it non-diagnostic); otherwise the all-round id heuristic applies.
```

In the `identify_signals` input/output description, note the `geometry` field is returned on each match and accepted as input. Update the input line to:

```markdown
Input: `{ arrangement: string[], condition: "day"|"night"|"restricted_visibility", regime?: ..., geometry?: "vertical"|"triangle"|"fore_and_aft" }`.
```

and add to the per-match output shape: `geometry`. In the `list_signal_patterns` output line add `flashing_lights`, `geometries`, and per-pattern `geometry`.

- [ ] **Step 2: Update README.md**

In `README.md`, update the `identify_signals` Tools-table row to mention geometry:

```markdown
| `identify_signals` | Reverse lookup — observed top-to-bottom light/shape arrangement (optionally with `geometry`: vertical/triangle/fore_and_aft) → ranked candidate vessel states with citations and confirm cues (`match_type`: exact / superset / permutation) |
```

- [ ] **Step 3: Final full suite + drift gate**

Run: `uv run pytest -q`
Expected: PASS (all). Confirm `tests/test_real_vault_drift.py::test_real_sightings_have_no_drift` is among them and not skipped.

- [ ] **Step 4: Commit**

```bash
git add README.md SPEC.md
git commit -m "docs: document geometry, flashing tokens, and explicit signal tokens"
```

---

## Self-Review Notes

- **Spec coverage:** schema delta — per-signal `token` (Task 2 validate, Task 3 drift), `geometry` (Task 2 validate, Task 4 matcher, Task 5 surface), flashing tokens (Task 1), new vessel-classes (Task 1). Catalog — towing incl. >200 m + aft + day diamond + being-towed (Task 6); mine-clearance, aground night/day, ≥50 m anchor (Task 7); air-cushion, WIG, sailing masthead, CBD day, fishing day (Task 8); fishing gear day + Annex II + at-anchor confirms (Task 9). Collisions — 3-ball geometry (Task 7 test), `[red,red]` three-candidate and `[white,red]` pilot+fishing (Task 9 tests), `[white,white]` vertical-vs-fore_and_aft (Task 6/7 confirms). Docs (Task 10).
- **Drift invariant honoured:** every new sighting's sorted arrangement equals a band its candidate's requirements entries produce — verified by construction (e.g. `[yellow,white]`→`[white,yellow]` from towing-stern; `[red,red]` from aground (anchor `token:null`) and fishing net-fast; `[green,red]` from sailing masthead). The real-vault gate runs at Tasks 6–9 and Task 10.
- **No forward-table corruption:** mutually-exclusive multi-state signals (towing 2-vs-3 masthead, fishing Annex II states) use `light_options` so the forward tool reads them as alternatives.
- **Type/name consistency:** `geometry` default `"vertical"` is applied identically in `_match`, `geometry_ok`, `list_signal_patterns`, and validation; `_diagnostic_token` uses `"token" in sig` (so `null` suppresses) consistently with the Task 2 validator that allows `token: null`.
- **YAGNI:** pushing/alongside and night gear-light stay confirm cues; no range/aspect/AIS.
