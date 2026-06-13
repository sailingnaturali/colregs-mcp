# Reverse Signal Identification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reverse lookup so a watch-stander's "I see two red lights stacked — what is it?" maps an observed light/shape arrangement to ranked candidate vessel states with rule citations and disambiguating cues.

**Architecture:** A curated reverse field-guide (`sightings.yaml`) lives in `colregs-vault` beside `requirements.yaml`. Each row is an ordered, top-to-bottom token list → candidate situations + confirm cues. The MCP loads and validates it, and a deterministic matcher (exact → superset → permutation) answers `identify_signals`. The LLM does the natural-language→token translation; the MCP never fuzzy-matches prose. A drift test cross-checks every sighting against `requirements.yaml` so the forward and reverse data can't silently disagree.

**Tech Stack:** Python 3.11, `mcp` server SDK, PyYAML, pytest, `uv`.

---

## File Structure

**colregs-mcp (this repo):**
- `src/colregs_mcp/models.py` — *modify*: add the signal-token vocabularies and `token_kind` / kind↔condition map.
- `src/colregs_mcp/vault.py` — *modify*: add the `Sightings` dataclass, `_validate_sightings`, and load `sightings.yaml` into `Vault`.
- `src/colregs_mcp/sightings.py` — *create*: `identify_signals`, `list_signal_patterns`, and `sightings_drift` (the cross-check).
- `src/colregs_mcp/tools.py` — *modify*: thin `identify_signals_tool` / `list_signal_patterns_tool` wrappers.
- `src/colregs_mcp/server.py` — *modify*: register both tools in `dispatch` and `list_tools` with input schemas.
- `tests/fixtures/vault/requirements.yaml` — *modify*: add a `restricted_manoeuvrability` night row so the fixture covers a 3-light, multi-colour stack.
- `tests/fixtures/vault/sightings.yaml` — *create*: small fixture catalog the tests match against.
- `tests/test_sightings.py` — *create*: matcher + vocabulary unit tests.
- `tests/test_sightings_drift.py` — *create*: drift cross-check tests.
- `tests/test_vault.py` — *modify*: sightings load + validation tests.
- `tests/test_server.py` — *modify*: dispatch wiring tests for the two new tools.
- `SPEC.md`, `README.md` — *modify*: document the new tools and token vocabulary.

**colregs-vault (sibling repo):**
- `sightings.yaml` — *create*: the real classic catalog (NUC, RAM, constrained-by-draught, aground, anchored, fishing, trawling, pilot, towing, motorsailing).

---

## Task 1: Signal-token vocabulary in models.py

**Files:**
- Modify: `src/colregs_mcp/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_models.py`:

```python
def test_token_kind_classifies_colours_and_shapes():
    from colregs_mcp.models import token_kind
    assert token_kind("red") == "lights"
    assert token_kind("ball") == "shapes"

def test_token_kind_rejects_unknown_token():
    import pytest
    from colregs_mcp.models import token_kind
    with pytest.raises(ValueError, match="unknown signal token"):
        token_kind("purple")

def test_signal_conditions_pair_kinds_to_conditions():
    from colregs_mcp.models import SIGNAL_CONDITIONS
    assert SIGNAL_CONDITIONS["shapes"] == {"day"}
    assert SIGNAL_CONDITIONS["lights"] == {"night", "restricted_visibility"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models.py -k "token_kind or signal_conditions" -v`
Expected: FAIL with `ImportError: cannot import name 'token_kind'`.

- [ ] **Step 3: Write minimal implementation**

Add to `src/colregs_mcp/models.py`, after the existing `CONDITIONS` definition:

```python
# Reverse-identification vocabulary. Two disjoint token namespaces: light colours
# (all-round assumed; sidelights/sternlight/masthead are confirmatory, never part
# of the stacked identity) and day shapes. `kind` is inferred from the namespace.
LIGHT_COLORS = frozenset({"red", "white", "green", "yellow"})
DAY_SHAPES = frozenset({"ball", "diamond", "cylinder", "cone_up", "cone_down"})
SIGNAL_TOKENS = LIGHT_COLORS | DAY_SHAPES

# Shapes are a daytime signal; lights are shown at night and in restricted visibility.
SIGNAL_CONDITIONS = {"shapes": {"day"}, "lights": {"night", "restricted_visibility"}}


def token_kind(token: str) -> str:
    """'lights' for a colour token, 'shapes' for a day-shape token. Raises on unknown —
    an unrecognized token must never be silently dropped from an identification."""
    if token in LIGHT_COLORS:
        return "lights"
    if token in DAY_SHAPES:
        return "shapes"
    raise ValueError(f"unknown signal token {token!r}; expected one of {sorted(SIGNAL_TOKENS)}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_models.py -k "token_kind or signal_conditions" -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/colregs_mcp/models.py tests/test_models.py
git commit -m "feat: add reverse-identification token vocabulary to models"
```

---

## Task 2: Load and validate sightings.yaml in the vault

**Files:**
- Modify: `src/colregs_mcp/vault.py`
- Create: `tests/fixtures/vault/sightings.yaml`
- Modify: `tests/fixtures/vault/requirements.yaml`, `tests/test_vault.py`

- [ ] **Step 1: Add the RAM row to the fixture requirements**

Append to `tests/fixtures/vault/requirements.yaml` (gives the fixture a 3-light, multi-colour stack for later matcher tests):

```yaml
  - id: ram-night
    match: { situation: restricted_manoeuvrability, condition: night }
    lights:
      - { id: all_round_red_top, desc: "all-round red", rule: "Rule 27(b)(i)" }
      - { id: all_round_white_mid, desc: "all-round white", rule: "Rule 27(b)(i)" }
      - { id: all_round_red_bot, desc: "all-round red", rule: "Rule 27(b)(i)" }
```

- [ ] **Step 2: Create the fixture sightings catalog**

Create `tests/fixtures/vault/sightings.yaml`:

```yaml
version: 1
patterns:
  - id: red-over-red-night
    arrangement: [red, red]
    condition: night
    mnemonic: "red over red, the captain is dead"
    candidates:
      - situation: not_under_command
        rule: "Rule 27(a)"
        note: "Two all-round reds in a vertical line."
    confirm:
      - "Also see a white anchor light? May be AGROUND (Rule 30), not NUC."
  - id: red-red-red-night
    arrangement: [red, red, red]
    condition: night
    candidates:
      - situation: constrained_by_draught
        rule: "Rule 28"
        note: "Three all-round reds in a vertical line."
  - id: red-white-red-night
    arrangement: [red, white, red]
    condition: night
    candidates:
      - situation: restricted_manoeuvrability
        rule: "Rule 27(b)"
        note: "Red-white-red all-round, vertical."
  - id: anchor-white-night
    arrangement: [white]
    condition: night
    candidates:
      - situation: anchored
        rule: "Rule 30(a)"
        note: "Single all-round white forward."
  - id: anchor-ball-day
    arrangement: [ball]
    condition: day
    candidates:
      - situation: anchored
        rule: "Rule 30(a)"
        note: "One ball, forward."
```

- [ ] **Step 3: Write the failing test**

Add to `tests/test_vault.py`:

```python
def test_vault_loads_sightings():
    v = Vault.load(FIXTURE)
    ids = [p["id"] for p in v.sightings.patterns]
    assert "red-over-red-night" in ids

def test_sightings_rejects_unknown_token(tmp_path):
    import pytest
    (tmp_path / "sightings.yaml").write_text(
        "version: 1\n"
        "patterns:\n"
        "  - id: bad-token\n"
        "    arrangement: [purple]\n"
        "    condition: night\n"
        "    candidates: [{ situation: anchored, rule: 'Rule 30' }]\n",
        encoding="utf-8")
    with pytest.raises(ValueError, match="unknown token"):
        Vault.load(tmp_path)

def test_sightings_rejects_kind_condition_mismatch(tmp_path):
    import pytest
    (tmp_path / "sightings.yaml").write_text(
        "version: 1\n"
        "patterns:\n"
        "  - id: shape-by-night\n"
        "    arrangement: [ball]\n"
        "    condition: night\n"
        "    candidates: [{ situation: anchored, rule: 'Rule 30' }]\n",
        encoding="utf-8")
    with pytest.raises(ValueError, match="not a shapes condition"):
        Vault.load(tmp_path)

def test_sightings_rejects_unknown_situation(tmp_path):
    import pytest
    (tmp_path / "sightings.yaml").write_text(
        "version: 1\n"
        "patterns:\n"
        "  - id: bad-situation\n"
        "    arrangement: [red, red]\n"
        "    condition: night\n"
        "    candidates: [{ situation: submarine, rule: 'Rule 27' }]\n",
        encoding="utf-8")
    with pytest.raises(ValueError, match="unknown situation"):
        Vault.load(tmp_path)
```

- [ ] **Step 4: Run test to verify it fails**

Run: `uv run pytest tests/test_vault.py -k sightings -v`
Expected: FAIL — `AttributeError: 'Vault' object has no attribute 'sightings'`.

- [ ] **Step 5: Implement Sightings, validation, and loading**

In `src/colregs_mcp/vault.py`, extend the models import line:

```python
from colregs_mcp.models import (
    CONDITIONS, REGIMES, SIGNAL_CONDITIONS, SIGNAL_TOKENS, SITUATIONS, Rule, token_kind,
)
```

Add the validator after `_validate_entries`:

```python
def _validate_sightings(patterns: list) -> None:
    """Fail loudly at load on a malformed reverse field-guide — a typo'd token or a
    candidate pointing at a non-vessel-state would corrupt identification output."""
    for i, p in enumerate(patterns):
        ident = p.get("id", f"patterns[{i}]") if isinstance(p, dict) else f"patterns[{i}]"
        if not isinstance(p, dict):
            raise ValueError(f"sightings.yaml: {ident} is not a mapping")
        arr = p.get("arrangement")
        if not isinstance(arr, list) or not arr:
            raise ValueError(f"sightings.yaml: {ident} has an empty or missing arrangement")
        unknown = [t for t in arr if t not in SIGNAL_TOKENS]
        if unknown:
            raise ValueError(f"sightings.yaml: {ident} has unknown token(s) {unknown}; "
                             f"allowed: {sorted(SIGNAL_TOKENS)}")
        kinds = {token_kind(t) for t in arr}
        if len(kinds) != 1:
            raise ValueError(f"sightings.yaml: {ident} mixes lights and shapes in arrangement")
        kind = kinds.pop()
        cond = p.get("condition")
        if cond not in CONDITIONS:
            raise ValueError(f"sightings.yaml: {ident} has unknown condition {cond!r}")
        if cond not in SIGNAL_CONDITIONS[kind]:
            raise ValueError(f"sightings.yaml: {ident} is {kind} but {cond!r} is not a "
                             f"{kind} condition")
        regime = p.get("regime")
        if regime is not None and regime not in REGIMES:
            raise ValueError(f"sightings.yaml: {ident} has unknown regime {regime!r}")
        cands = p.get("candidates")
        if not isinstance(cands, list) or not cands:
            raise ValueError(f"sightings.yaml: {ident} has no candidates")
        for c in cands:
            if not isinstance(c, dict) or "situation" not in c:
                raise ValueError(f"sightings.yaml: {ident} has a candidate without a situation")
            if c["situation"] not in SITUATIONS:
                raise ValueError(f"sightings.yaml: {ident} candidate has unknown situation "
                                 f"{c['situation']!r}; allowed: {sorted(SITUATIONS)}")
        confirm = p.get("confirm", [])
        if not isinstance(confirm, list):
            raise ValueError(f"sightings.yaml: {ident} confirm must be a list")
```

Add the dataclass after `Requirements`:

```python
@dataclass
class Sightings:
    """Curated reverse field-guide: observed arrangement -> candidate vessel states."""
    version: int = 1
    patterns: list[dict] = field(default_factory=list)
```

Add `sightings` to the `Vault` dataclass fields (after `regime_features`):

```python
    sightings: Sightings = field(default_factory=Sightings)
```

In `Vault.load`, after the requirements block and before the regime/geojson block, add:

```python
        sightings = Sightings()
        s_file = root / "sightings.yaml"
        if s_file.is_file():
            data = yaml.safe_load(s_file.read_text(encoding="utf-8")) or {}
            patterns = list(data.get("patterns", []))
            _validate_sightings(patterns)
            sightings = Sightings(version=int(data.get("version", 1)), patterns=patterns)
```

Update the final `return cls(...)` to pass it:

```python
        return cls(root=root, rules=rules, requirements=reqs,
                   regime_features=features, sightings=sightings)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_vault.py -k sightings -v`
Expected: PASS (4 tests).

- [ ] **Step 7: Run the full vault test file (no regressions)**

Run: `uv run pytest tests/test_vault.py -v`
Expected: PASS (all).

- [ ] **Step 8: Commit**

```bash
git add src/colregs_mcp/vault.py tests/fixtures/vault/sightings.yaml tests/fixtures/vault/requirements.yaml tests/test_vault.py
git commit -m "feat: load and validate sightings.yaml in the vault"
```

---

## Task 3: The identify_signals matcher

**Files:**
- Create: `src/colregs_mcp/sightings.py`
- Test: `tests/test_sightings.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_sightings.py`:

```python
from pathlib import Path
from colregs_mcp.sightings import identify_signals
from colregs_mcp.vault import Vault

FIXTURE = Path(__file__).parent / "fixtures" / "vault"

def _s():
    return Vault.load(FIXTURE).sightings

def test_exact_match_returns_single_candidate():
    out = identify_signals(_s(), ["red", "red"], "night")
    assert [m["match_type"] for m in out["matches"]] == ["exact"]
    assert out["matches"][0]["candidates"][0]["situation"] == "not_under_command"
    assert out["kind"] == "lights"

def test_exact_match_carries_confirm_cues():
    out = identify_signals(_s(), ["red", "red"], "night")
    assert any("AGROUND" in c for c in out["matches"][0]["confirm"])

def test_partial_sighting_returns_superset_matches():
    out = identify_signals(_s(), ["red"], "night")
    types = {m["match_type"] for m in out["matches"]}
    sits = {c["situation"] for m in out["matches"] for c in m["candidates"]}
    assert types == {"superset"}
    assert "not_under_command" in sits and "constrained_by_draught" in sits

def test_flipped_order_returns_permutation_match():
    out = identify_signals(_s(), ["white", "red", "red"], "night")
    assert [m["match_type"] for m in out["matches"]] == ["permutation"]
    assert out["matches"][0]["candidates"][0]["situation"] == "restricted_manoeuvrability"

def test_no_match_returns_empty_matches():
    out = identify_signals(_s(), ["green", "green"], "night")
    assert out["matches"] == []

def test_lights_by_day_is_an_error():
    out = identify_signals(_s(), ["red", "red"], "day")
    assert "error" in out and out["matches"] == []

def test_mixed_tokens_is_an_error():
    out = identify_signals(_s(), ["red", "ball"], "night")
    assert "error" in out and out["matches"] == []

def test_unknown_token_is_an_error():
    out = identify_signals(_s(), ["purple"], "night")
    assert "error" in out and out["matches"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_sightings.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'colregs_mcp.sightings'`.

- [ ] **Step 3: Implement the matcher**

Create `src/colregs_mcp/sightings.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_sightings.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add src/colregs_mcp/sightings.py tests/test_sightings.py
git commit -m "feat: identify_signals reverse matcher (exact/superset/permutation)"
```

---

## Task 4: list_signal_patterns vocabulary browser

**Files:**
- Modify: `src/colregs_mcp/sightings.py`
- Test: `tests/test_sightings.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_sightings.py`:

```python
def test_list_signal_patterns_returns_vocabulary_and_catalog():
    from colregs_mcp.sightings import list_signal_patterns
    out = list_signal_patterns(_s())
    assert set(out["light_colors"]) == {"red", "white", "green", "yellow"}
    assert "ball" in out["day_shapes"]
    ids = [p["id"] for p in out["patterns"]]
    assert "red-over-red-night" in ids
    entry = next(p for p in out["patterns"] if p["id"] == "red-over-red-night")
    assert entry["situations"] == ["not_under_command"]
    assert entry["arrangement"] == ["red", "red"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_sightings.py -k list_signal_patterns -v`
Expected: FAIL — `ImportError: cannot import name 'list_signal_patterns'`.

- [ ] **Step 3: Implement list_signal_patterns**

Append to `src/colregs_mcp/sightings.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_sightings.py -k list_signal_patterns -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/colregs_mcp/sightings.py tests/test_sightings.py
git commit -m "feat: list_signal_patterns vocabulary browser"
```

---

## Task 5: The drift cross-check against requirements.yaml

**Files:**
- Modify: `src/colregs_mcp/sightings.py`
- Create: `tests/test_sightings_drift.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_sightings_drift.py`:

```python
from pathlib import Path
from colregs_mcp.sightings import sightings_drift
from colregs_mcp.vault import Requirements, Sightings, Vault

FIXTURE = Path(__file__).parent / "fixtures" / "vault"

def test_fixture_catalog_has_no_drift():
    v = Vault.load(FIXTURE)
    assert sightings_drift(v.sightings, v.requirements) == []

def test_candidate_situation_not_modeled_is_flagged():
    reqs = Requirements(entries=[
        {"id": "anchored-night", "match": {"situation": "anchored", "condition": "night"},
         "lights": [{"id": "anchor_light", "rule": "Rule 30(a)"}]},
    ])
    sightings = Sightings(patterns=[
        {"id": "two-red", "arrangement": ["red", "red"], "condition": "night",
         "candidates": [{"situation": "not_under_command", "rule": "Rule 27(a)"}]},
    ])
    problems = sightings_drift(sightings, reqs)
    assert any("not modeled" in p and "not_under_command" in p for p in problems)

def test_arrangement_inconsistent_with_required_lights_is_flagged():
    # requirements say NUC shows TWO reds; the sighting claims THREE -> drift.
    reqs = Requirements(entries=[
        {"id": "nuc-night", "match": {"situation": "not_under_command", "condition": "night"},
         "lights": [{"id": "all_round_red_upper", "rule": "Rule 27(a)"},
                    {"id": "all_round_red_lower", "rule": "Rule 27(a)"}]},
    ])
    sightings = Sightings(patterns=[
        {"id": "three-red", "arrangement": ["red", "red", "red"], "condition": "night",
         "candidates": [{"situation": "not_under_command", "rule": "Rule 27(a)"}]},
    ])
    problems = sightings_drift(sightings, reqs)
    assert any("no matching requirements band" in p for p in problems)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_sightings_drift.py -v`
Expected: FAIL — `ImportError: cannot import name 'sightings_drift'`.

- [ ] **Step 3: Implement the drift cross-check**

Append to `src/colregs_mcp/sightings.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_sightings_drift.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/colregs_mcp/sightings.py tests/test_sightings_drift.py
git commit -m "feat: sightings_drift cross-check against requirements.yaml"
```

---

## Task 6: Wire the tools into the server

**Files:**
- Modify: `src/colregs_mcp/tools.py`, `src/colregs_mcp/server.py`
- Test: `tests/test_server.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_server.py`:

```python
def test_dispatch_identify_signals():
    out = dispatch(_vault(), "identify_signals",
                   {"arrangement": ["red", "red"], "condition": "night"})
    assert out["matches"][0]["candidates"][0]["situation"] == "not_under_command"

def test_dispatch_list_signal_patterns():
    out = dispatch(_vault(), "list_signal_patterns", {})
    assert "red" in out["light_colors"]
    assert any(p["id"] == "red-over-red-night" for p in out["patterns"])

def test_identify_signals_schema_enum_matches_token_vocabulary():
    import asyncio
    from colregs_mcp.models import SIGNAL_TOKENS
    from colregs_mcp.server import build_server
    tools_list = asyncio.run(build_server(_vault()).list_tools())
    tool = next(t for t in tools_list if t.name == "identify_signals")
    enum = set(tool.inputSchema["properties"]["arrangement"]["items"]["enum"])
    assert enum == set(SIGNAL_TOKENS)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_server.py -k "identify_signals or list_signal_patterns" -v`
Expected: FAIL — `ValueError: Unknown tool: identify_signals`.

- [ ] **Step 3: Add the tool wrappers**

In `src/colregs_mcp/tools.py`, add the import near the other imports:

```python
from colregs_mcp.sightings import identify_signals, list_signal_patterns
```

Append the wrappers at the end of the file:

```python
def identify_signals_tool(vault: Vault, arrangement, condition: str,
                          regime: str | None = None) -> dict:
    return identify_signals(vault.sightings, arrangement or [], condition, regime)


def list_signal_patterns_tool(vault: Vault) -> dict:
    return list_signal_patterns(vault.sightings)
```

- [ ] **Step 4: Register dispatch routes and schemas**

In `src/colregs_mcp/server.py`, add a token-array schema constant after `_PROFILE_SCHEMA`:

```python
_ARRANGEMENT_SCHEMA = {
    "type": "array",
    "items": {"type": "string", "enum": sorted(models_vocab.SIGNAL_TOKENS)},
    "description": "observed signals, top to bottom; light colours OR day shapes, not both",
}
```

In `dispatch`, add before the final `raise`:

```python
    if name == "identify_signals":
        return tools.identify_signals_tool(vault, arrangement=args["arrangement"],
                                           condition=args["condition"], regime=args.get("regime"))
    if name == "list_signal_patterns":
        return tools.list_signal_patterns_tool(vault)
```

In `_list_tools`, add two `types.Tool(...)` entries to the returned list:

```python
            types.Tool(name="identify_signals",
                description=("Reverse lookup: given an observed top-to-bottom arrangement of "
                             "all-round light colours (night) or day shapes, return ranked "
                             "candidate vessel states with citations and confirm cues. "
                             "match_type is exact, superset (a light may have been missed), or "
                             "permutation (top/bottom may be flipped)."),
                inputSchema={"type": "object", "properties": {
                    "arrangement": _ARRANGEMENT_SCHEMA,
                    "condition": {"type": "string", "enum": ["day", "night", "restricted_visibility"]},
                    "regime": {"type": "string", "enum": ["international", "inland", "canadian"]},
                }, "required": ["arrangement", "condition"]}),
            types.Tool(name="list_signal_patterns",
                description=("The canonical token vocabulary (light colours, day shapes) and the "
                             "catalog of known sighting patterns — browse this to learn the exact "
                             "tokens to pass to identify_signals."),
                inputSchema={"type": "object", "properties": {}}),
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_server.py -v`
Expected: PASS (all, including the three new tests).

- [ ] **Step 6: Commit**

```bash
git add src/colregs_mcp/tools.py src/colregs_mcp/server.py tests/test_server.py
git commit -m "feat: expose identify_signals and list_signal_patterns tools"
```

---

## Task 7: Author the real sightings.yaml in colregs-vault

**Files:**
- Create: `../colregs-vault/sightings.yaml`
- Create: `tests/test_real_vault_drift.py` (guarded; runs only when the sibling vault is present)

- [ ] **Step 1: Author the classic catalog**

Create `../colregs-vault/sightings.yaml`. Author one row per classic sighting; every `situation` and arrangement must correspond to a modeled `requirements.yaml` band (Task 5's drift check enforces this — expect to extend `requirements.yaml` rows in lockstep where a situation isn't yet modeled). Start from the night-lights core and the day-shapes core:

```yaml
version: 1
# ⚠️ UNVERIFIED DRAFT — pending Bryan's line-by-line review against the rule text.
# arrangement: ordered top -> bottom; all-round lights assumed.
patterns:
  - id: red-over-red-night
    arrangement: [red, red]
    condition: night
    mnemonic: "red over red, the captain is dead"
    candidates:
      - situation: not_under_command
        rule: "Rule 27(a)"
        note: "Two all-round reds in a vertical line."
    confirm:
      - "Also see a white anchor light or two? May be AGROUND (Rule 30), not NUC."
      - "Sidelights + sternlight and moving -> making way; none/stationary -> stopped."
  - id: red-red-red-night
    arrangement: [red, red, red]
    condition: night
    candidates:
      - situation: constrained_by_draught
        rule: "Rule 28"
        note: "Three all-round reds in a vertical line."
  - id: red-white-red-night
    arrangement: [red, white, red]
    condition: night
    candidates:
      - situation: restricted_manoeuvrability
        rule: "Rule 27(b)"
        note: "Red-white-red all-round, vertical."
  - id: green-over-white-night
    arrangement: [green, white]
    condition: night
    mnemonic: "green over white, trawling at night"
    candidates:
      - situation: fishing
        rule: "Rule 26(b)"
        note: "Trawler: all-round green over all-round white."
  - id: red-over-white-night
    arrangement: [red, white]
    condition: night
    mnemonic: "red over white, fishing at night"
    candidates:
      - situation: fishing
        rule: "Rule 26(c)"
        note: "Fishing (not trawling): all-round red over all-round white."
  - id: white-over-red-night
    arrangement: [white, red]
    condition: night
    mnemonic: "white over red, pilot ahead"
    candidates:
      - situation: pilot_vessel
        rule: "Rule 29"
        note: "Pilot vessel on duty: all-round white over all-round red."
  - id: anchor-white-night
    arrangement: [white]
    condition: night
    candidates:
      - situation: anchored
        rule: "Rule 30(a)"
        note: "Single all-round white forward (vessel under 50 m)."
  # --- day shapes ---
  - id: anchor-ball-day
    arrangement: [ball]
    condition: day
    candidates:
      - situation: anchored
        rule: "Rule 30(a)"
        note: "One ball, forward."
  - id: ball-diamond-ball-day
    arrangement: [ball, diamond, ball]
    condition: day
    candidates:
      - situation: restricted_manoeuvrability
        rule: "Rule 27(b)"
        note: "Ball-diamond-ball in a vertical line."
  - id: ball-ball-day
    arrangement: [ball, ball]
    condition: day
    candidates:
      - situation: not_under_command
        rule: "Rule 27(a)"
        note: "Two balls in a vertical line."
  - id: cone-down-day
    arrangement: [cone_down]
    condition: day
    candidates:
      - situation: motorsailing
        rule: "Rule 25(e)"
        note: "One cone, apex down: sailing vessel also under power."
```

> **Note for the implementer:** This list is the *starting* catalog, not the final word. For each row you add, confirm `requirements.yaml` models that situation+condition with a matching diagnostic-token band; if it doesn't, add/adjust the `requirements.yaml` row first (e.g. `pilot_vessel` night, `fishing` night, `restricted_manoeuvrability` night, `not_under_command` day, `constrained_by_draught` night may need rows). The drift test in Step 2 is the gate.

- [ ] **Step 2: Add the guarded real-vault drift test**

Create `tests/test_real_vault_drift.py`:

```python
from pathlib import Path
import pytest
from colregs_mcp.sightings import sightings_drift
from colregs_mcp.vault import Vault

REAL_VAULT = Path(__file__).resolve().parents[2] / "colregs-vault"

@pytest.mark.skipif(not (REAL_VAULT / "sightings.yaml").is_file(),
                    reason="sibling colregs-vault not present")
def test_real_sightings_have_no_drift():
    v = Vault.load(REAL_VAULT)
    assert sightings_drift(v.sightings, v.requirements) == []
```

- [ ] **Step 3: Run the drift gate against the real vault**

Run: `uv run pytest tests/test_real_vault_drift.py -v`
Expected: PASS. If it FAILS, read each reported problem and either fix the sighting arrangement/situation or add the missing `requirements.yaml` band in `../colregs-vault`, then re-run until green. Do not weaken the drift check to pass.

- [ ] **Step 4: Commit (two repos)**

```bash
git -C ../colregs-vault add sightings.yaml requirements.yaml
git -C ../colregs-vault commit -m "feat: add sightings.yaml reverse field-guide (draft)"
git add tests/test_real_vault_drift.py
git commit -m "test: guard real-vault sightings against drift"
```

---

## Task 8: Documentation

**Files:**
- Modify: `README.md`, `SPEC.md`

- [ ] **Step 1: Update the README tools table**

In `README.md`, add two rows to the Tools table:

```markdown
| `identify_signals` | Reverse lookup — observed top-to-bottom light/shape arrangement → ranked candidate vessel states with citations and confirm cues (`match_type`: exact / superset / permutation) |
| `list_signal_patterns` | The canonical token vocabulary (light colours, day shapes) and the catalog of known sighting patterns |
```

And add a short paragraph after the Vault layout block noting the new file:

```markdown
`sightings.yaml` is the curated reverse field-guide: each row maps an ordered,
top-to-bottom arrangement of all-round light colours (night) or day shapes to
candidate vessel states. A drift test cross-checks every row against
`requirements.yaml` so the forward and reverse data cannot silently disagree.
```

- [ ] **Step 2: Update SPEC.md**

In `SPEC.md`, document the two tools' input/output contracts and the token vocabulary. Add this section (place it after the existing tool contracts):

```markdown
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

### identify_signals

Input: `{ arrangement: string[], condition: "day"|"night"|"restricted_visibility", regime?: ... }`.
Output: `{ arrangement, condition, kind, matches: [...] }` where each match is
`{ match_type, pattern_id, mnemonic, candidates: [{situation, rule, note}], confirm: string[] }`.
`match_type` ranks results: `exact` → `superset` (a light may have been missed) →
`permutation` (top/bottom may be flipped). On an exact hit only exact matches are
returned; otherwise superset and permutation near-misses are returned, each flagged.
Errors (empty/mixed/unknown tokens, kind/condition mismatch) return `{ error, matches: [] }`.

### list_signal_patterns

Input: `{}`. Output: `{ light_colors, day_shapes, note, patterns: [{id, arrangement,
condition, mnemonic, situations}] }` — the vocabulary and catalog the LLM browses to
learn the exact tokens to pass to `identify_signals`.
```

- [ ] **Step 3: Run the full test suite (final verification)**

Run: `uv run pytest -q`
Expected: PASS (all tests across the suite).

- [ ] **Step 4: Commit**

```bash
git add README.md SPEC.md
git commit -m "docs: document identify_signals and list_signal_patterns"
```

---

## Self-Review Notes

- **Spec coverage:** `sightings.yaml` schema (Task 2), token vocabularies (Task 1), `identify_signals` + `list_signal_patterns` (Tasks 3-4), exact/superset/permutation + `match_type` (Task 3), ambiguity via multiple `candidates[]`/`confirm[]` (fixture + Task 3 tests), drift prevention (Task 5 + guarded real-vault test Task 7), International-first scope with optional `regime` (validation in Task 2, matcher `regime_ok` in Task 3), docs (Task 8). No NL parsing in the MCP — confirmed (matcher only consumes typed tokens).
- **Out of scope (per spec):** sector geometry, range-by-length, bearing/aspect, AIS fusion — none introduced.
- **Type consistency:** `Sightings`/`Requirements` dataclasses used consistently; `identify_signals(sightings, arrangement, condition, regime=None)` signature matches the tool wrapper and dispatch; `match_type` values (`exact`/`superset`/`permutation`) consistent across matcher, tests, schema description, and SPEC.
- **Known follow-up:** the real catalog in Task 7 will likely require new `requirements.yaml` bands (pilot, fishing, RAM-night, NUC-day) — the drift gate forces that reconciliation rather than letting the reverse table outrun the forward one.
