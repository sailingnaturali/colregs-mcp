# Reverse identification — COLREGS Part C completeness

**Date:** 2026-06-14
**Status:** Approved design, pending implementation plan
**Repo:** `colregs-mcp` (model + tools) + `colregs-vault` (data)
**Builds on:** `2026-06-13-reverse-signal-identification-design.md`

## Problem

The reverse-identification catalog (`sightings.yaml`) currently covers the
all-round, vertically-stacked signals — NUC, RAM, constrained-by-draught,
fishing/trawling, pilot, anchored, motorsailing. Bryan verified that draft and
asked for the rest of COLREGS Part C: towing (incl. tows over 200 m),
vessel-being-towed, mine-clearance, and the remaining distinctive signals.

These break two assumptions baked into the current model:

1. **Sector lights as identity.** Towing is recognised by *sector* lights — a
   vertical line of 2 (tow ≤200 m) or 3 (>200 m) masthead lights forward, plus a
   **yellow towing light over the white sternlight** aft. The drift check drops
   sector lights as non-diagnostic, so towing has no band today.
2. **Non-vertical geometry.** Mine-clearance shows three all-round greens / three
   balls in a **triangle** (one at the masthead, two at the yard-ends at the same
   height). And **three balls in a triangle (mine-clearance) vs three balls in a
   vertical line (aground)** are the *same token multiset* — geometry is the only
   discriminator, exactly as top/bottom order discriminates pilot from fishing.

Plus flashing signals (air-cushion, WIG) that have no representation at all.

## Schema delta

Four additions; everything else reuses existing mechanisms.

### 1. `token:` on requirement signals (the sector-light fix)

Today `_signal_token` *guesses* a signal's reverse-ID token from its id prefix
(`all_round_red_*` → red) and drops everything else. Add an optional `token:`
field to each `lights` / `shapes` / `light_options` signal entry in
`requirements.yaml`, declaring its reverse-ID token explicitly. The drift check
uses `sig.get("token") or _signal_token(sig["id"])` — so:

- Existing `all_round_*` and shape rows keep working via the heuristic fallback —
  **zero churn to the verified rows.**
- Towing's masthead-line lights declare `token: white`; the towing light declares
  `token: yellow`; the sternlight, *in the towing-stern entry*, declares
  `token: white` (it is part of the recognisable yellow-over-white picture).
  Shared sidelights/sternlight elsewhere declare nothing and stay non-diagnostic.

`token` is per-occurrence, so the same id (`sternlight`) can be diagnostic in one
entry and not in another.

### 2. `geometry:` on patterns + optional `identify_signals` input

Each `sightings.yaml` pattern gains an optional `geometry`:
`vertical` (default) | `triangle` | `fore_and_aft`. Matching is symmetric with
top/bottom order:

- `identify_signals` gains an optional `geometry` argument.
- If the query supplies geometry, it must equal the pattern's geometry (patterns
  without geometry are treated as `vertical`).
- If the query omits it, geometry is **not** filtered on; every match carries its
  `geometry` in the output so the caller can disambiguate (e.g. `[ball,ball,ball]`
  returns both aground (vertical) and mine-clearance (triangle), each flagged).

Geometry is a typed field, not fuzzy reasoning — the deterministic contract holds.
Geometry does **not** affect drift bands (those are token multisets); it is purely
a sighting-side discriminator for the matcher.

### 3. Flashing light tokens

`models.py` gains `FLASHING_LIGHTS = frozenset({"flashing_yellow", "flashing_red"})`.
`token_kind` returns `"lights"` for them (shown at night / restricted visibility).
The lights namespace becomes `LIGHT_COLORS | FLASHING_LIGHTS`; `SIGNAL_TOKENS`
includes them; the server `_ARRANGEMENT_SCHEMA` enum picks them up automatically.

### 4. New vessel-classes

`models.py` `_SPECIAL` gains `mine_clearance`, `air_cushion`, `wig`.
(`towing`, `being_towed`, `vessel_aground`, `pilot_vessel` already exist.) The
server `vessel_class` enum derives from `VESSEL_CLASSES`, so it updates
automatically; the existing `test_profile_schema_enum_matches_canonical_vocabulary`
guards the sync.

## Towing — no new machinery

Towing's distributed identity is modelled with existing mechanisms:

- `towing-masthead-night` — a `light_options` with two alternative groups: two
  white masthead lights (`token: white`) and three white masthead lights — drift
  yields bands `[white, white]` and `[white, white, white]`; the forward tool
  reads it correctly as "shows one alternative."
- `towing-stern-night` — `lights: [towing_light (token yellow), sternlight
  (token white)]` → band `[yellow, white]`. The forward tool merges this with the
  masthead entry, correctly reporting the full towing light suite.
- `towing-day-over-200m` — `shapes: [diamond]` → band `[diamond]`, shared by the
  towed vessel.

## Full catalog additions

| Signal | Pattern (top→bottom) | geometry | → situation(s) | Rule |
|---|---|---|---|---|
| Sailing optional masthead | `[red, green]` night | vertical | sailing | 25(c) |
| CBD by day | `[cylinder]` day | vertical | constrained_by_draught | 28 |
| Fishing by day | `[cone_down, cone_up]` day | vertical | fishing | 26(c) |
| Towing masthead (≤200 m) | `[white, white]` night | vertical | towing | 24(a) |
| Towing masthead (>200 m) | `[white, white, white]` night | vertical | towing | 24(a),(c) |
| Towing light aft | `[yellow, white]` night | fore_and_aft | towing | 24(a) |
| Tow >200 m by day | `[diamond]` day | vertical | towing, being_towed | 24(e) |
| Mine-clearance night | `[green, green, green]` night | triangle | mine_clearance | 27(f) |
| Mine-clearance day | `[ball, ball, ball]` day | triangle | mine_clearance | 27(f) |
| Aground night | `[red, red]` night | vertical | not_under_command, vessel_aground | 30(d) |
| Aground day | `[ball, ball, ball]` day | vertical | vessel_aground | 30(d) |
| Anchored ≥50 m | `[white, white]` night | fore_and_aft | anchored | 30(b) |
| Air-cushion | `[flashing_yellow]` night | vertical | air_cushion | 23(b) |
| WIG craft | `[flashing_red]` night | vertical | wig | 23(c) |

**Aground night** is added as a second `candidate` on the existing
`red-over-red-night` pattern (its confirm cue already points at aground); a new
`vessel_aground` night requirements band of two all-round reds (`token: red`, the
anchor light non-diagnostic) keeps drift `[red, red]`-consistent.

## Collisions and their discriminators

All resolved by an existing-style discriminator — no new tie-break logic:

- `[white, white]`: **vertical** → towing; **fore_and_aft** → anchored ≥50 m.
- `[ball, ball, ball]`: **vertical** → aground; **triangle** → mine-clearance.
- `[red, red]`: NUC *or* aground (multi-candidate + confirm — anchor lights and
  not making way → aground; making way → NUC).
- `[yellow, white]`, `[red, green]`, `[flashing_yellow]`, `[flashing_red]`: unique.

## Out of scope (YAGNI)

- **Fishing gear extending >150 m** (R26(c)(ii)) and **pushing / towing alongside**
  (R24(c)) fold into **confirm cues** on their parent patterns — they are
  directional or variant, not distinct stacked pictures.
- No range/visibility geometry, no bearing/aspect maths, no AIS fusion (unchanged
  from the base design).

## Affected components

- `src/colregs_mcp/models.py` — `FLASHING_LIGHTS`, lights namespace, `token_kind`,
  `_SPECIAL` additions, `GEOMETRIES` set.
- `src/colregs_mcp/vault.py` — validate `geometry` and per-signal `token` in
  `_validate_sightings` / requirements load; surface them on the dataclasses.
- `src/colregs_mcp/sightings.py` — `identify_signals` gains `geometry` filter +
  output; `_match` carries geometry; drift uses `sig.get("token") or
  _signal_token(...)`; `list_signal_patterns` surfaces geometry.
- `src/colregs_mcp/server.py` — `geometry` in the `identify_signals` input schema.
- `../colregs-vault/requirements.yaml` — new forward bands with explicit `token`s.
- `../colregs-vault/sightings.yaml` — the new patterns above.
- Tests across `test_models`, `test_vault`, `test_sightings`, `test_sightings_drift`,
  `test_server`, and the real-vault drift gate.

## Testing

- Unit: `token_kind` over flashing tokens; geometry validation; per-signal `token`
  override in drift; geometry filter in the matcher (must-match-when-given,
  all-returned-when-omitted); the `[ball,ball,ball]` and `[white,white]` collision
  cases returning the right candidates under each geometry.
- Drift: the real-vault gate stays green with every new band; explicit-`token`
  rows (towing, flashing) produce the expected bands.
- Schema-sync: the existing vessel_class and arrangement-enum guards cover the new
  vocabulary automatically.
