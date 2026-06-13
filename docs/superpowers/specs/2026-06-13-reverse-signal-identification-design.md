# Reverse signal identification — design

**Date:** 2026-06-13
**Status:** Approved design, pending implementation plan
**Repo:** `colregs-mcp` (tools) + `colregs-vault` (data)

## Problem

The watch-stander's real question is a reverse lookup: *"I see two red lights
stacked, nothing else — what is that?"* or *"three day-shapes, ball over diamond
over ball — what kind of ship?"*

The MCP today only runs **forward**: given a vessel profile (class, length,
propulsion, regime, condition) it computes required lights/shapes from
`requirements.yaml`. `check_compliance` compares an observed set against
requirements, but only once you *already know* the vessel. Two gaps:

1. **No reverse tool** inverts observed signals → candidate vessel states.
2. **The data does not encode arrangement.** Forward direction lists a light
   *set*; it never needs to know the two reds are *vertically stacked*. But
   top-to-bottom ordering is the entire diagnosis ("red over red, the captain is
   dead" vs "red over white, fishing at night"). The existing
   `all_round_red_upper/lower` IDs capture this only weakly, and the LLM would
   have to guess canonical IDs to call any tool.

## Division of labor

The MCP holds a **pre-indexed canonical vocabulary of arrangements**. The LLM
does the one thing it is reliably good at: translating a spoken observation
("two red stacked lights") into the canonical token sequence (`[red, red]`).
Neither side does the part it is bad at — the MCP never fuzzy-matches prose, and
the LLM never invents rule numbers. The canonical tokens are exactly the strings
the LLM already associates with the mnemonics, so the NL→token step is reliable.

## Architecture

### 1. `sightings.yaml` — curated reverse field-guide

New file in `colregs-vault`, sibling to `requirements.yaml`. Each row is one
classic sighting. The canonical pattern is an **ordered, top-to-bottom list of
tokens**; that ordering is the diagnosis. Hand-authored and hand-reviewable
(~20–30 rows — the classic catalog).

```yaml
version: 1
patterns:
  - id: red-over-red-night
    arrangement: [red, red]          # top → bottom; all-round unless noted
    condition: night
    mnemonic: "red over red, the captain is dead"
    candidates:
      - situation: not_under_command
        rule: "Rule 27(a)"
        note: "Two all-round reds in a vertical line."
    confirm:
      - "Also see anchor (white) light(s)? → may be AGROUND (Rule 30), not NUC."
      - "Sidelights + sternlight and moving → making way; none/stationary → stopped."

  - id: ball-diamond-ball-day
    arrangement: [ball, diamond, ball]
    condition: day
    candidates:
      - situation: restricted_manoeuvrability
        rule: "Rule 27(b)"
        note: "Ball-diamond-ball in a vertical line."
```

**Row fields:**

| Field | Meaning |
|---|---|
| `id` | stable slug |
| `arrangement` | ordered top→bottom token list (the canonical pattern key) |
| `condition` | `day` / `night` / `restricted_visibility` |
| `mnemonic` | optional human mnemonic, surfaced in output |
| `candidates[]` | `{ situation, rule, note }`, ordered most-likely first |
| `confirm[]` | disambiguating follow-up cues to narrow between candidates |
| `regime` | optional; present only where Inland/Canadian genuinely differ |

### 2. Token vocabularies (two disjoint namespaces)

`kind` is **inferred** from which namespace the tokens come from, then validated
against `condition` (day ⇒ shapes, night ⇒ lights).

- **Light colors:** `red`, `white`, `green`, `yellow`. All-round assumed.
  Sidelights / sternlight / masthead are *confirmatory*, not part of the stacked
  identity signal.
- **Day shapes:** `ball`, `diamond`, `cylinder`, `cone_up`, `cone_down`.

Mapping examples the LLM produces: `red over red` → `[red, red]`,
`red over white` → `[red, white]`, `ball-diamond-ball` → `[ball, diamond, ball]`.

### 3. Tools

- **`identify_signals(arrangement, condition, regime?)`** → ranked candidates +
  confirm cues + citations. The reverse lookup.
- **`list_signal_patterns()`** → the canonical token vocabulary and the catalog
  of known patterns, so the LLM can browse the target tokens to translate into.

## Ambiguity handling

Three kinds of ambiguity, three mechanisms:

1. **Same arrangement, genuinely different vessels** (e.g. `[red, red]` at night
   = NUC *or* aground). Lives **inside one row** as multiple `candidates[]`,
   ordered most-likely first, with `confirm[]` carrying the tiebreaker. The tool
   returns all candidates plus cues; it never collapses to a false single answer.

2. **Observer flipped top/bottom** (`red over white` = fishing vs
   `white over red` = pilot — opposite meanings). On an exact-order miss, the
   tool falls back to **permutation matches**, lower rank, explicitly flagged.
   Never silently reorders.

3. **Partial sighting** (saw `[red, red]`; it was really `[red, red, red]` =
   constrained-by-draught). On a miss, the tool returns **superset matches**
   (known patterns that contain the observed sequence *in order*), flagged.

**Ranking order:** exact → superset (missed a light) → permutation (flipped
order). Each result carries a `match_type` field (`exact` / `superset` /
`permutation`) so the LLM knows how much to hedge in its spoken reply.

The deterministic contract stays clean: the MCP only ever matches typed tokens
against the index — but it is *generous* about near-misses because real
observations are noisy.

## Drift prevention

A pytest cross-check: for every `sightings.yaml` candidate, assert the situation
exists in `requirements.yaml` **and** that the sighting's `arrangement` is
consistent with the lights/shapes that situation is required to show. If
`requirements.yaml` later changes (e.g. NUC's lights), the test fails until
`sightings.yaml` is reconciled. The curated reverse table can never silently
disagree with the forward source of truth.

## Scope (v1)

**In:**
- The classic catalog — NUC, RAM, constrained-by-draught, aground, anchored,
  fishing, trawling, pilot, towing (incl. long tow), sailing, motorsailing;
  night lights + day shapes.
- International regime first; `regime` override only where Inland/Canadian
  genuinely differ (e.g. US Inland towing / special-flashing).

**Out (YAGNI):**
- Sector-geometry reasoning (visible arcs, range-by-length).
- Bearing / aspect math, AIS fusion.
- NL parsing in the MCP — stays the LLM's job, per the division of labor.

## Deliverables

1. `colregs-vault/sightings.yaml` — curated reverse field-guide.
2. `colregs-mcp` loader + `identify_signals` and `list_signal_patterns` tools.
3. Exact → superset → permutation matcher with `match_type` flags.
4. Drift test cross-checking `sightings.yaml` against `requirements.yaml`.
5. `SPEC.md` + `README.md` updates documenting the new tools and token vocabulary.
