"""Rule record with markdown-frontmatter (de)serialization, and the vessel Profile."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields

import yaml

_FENCE = "---"


@dataclass
class Rule:
    number: str
    regime: str
    part: str = ""
    title: str = ""
    source_pdf: str | None = None
    prose: str = ""

    @classmethod
    def from_markdown(cls, text: str) -> "Rule":
        if not text.startswith(_FENCE):
            raise ValueError("markdown must start with a '---' frontmatter fence")
        _, fm, body = text.split(_FENCE, 2)
        data = yaml.safe_load(fm) or {}
        known = {f.name for f in fields(cls)} - {"prose"}
        kwargs = {k: v for k, v in data.items() if k in known}
        kwargs["number"] = str(kwargs.get("number", ""))  # YAML may parse 30 as int
        return cls(prose=body.lstrip("\n"), **kwargs)

    def to_markdown(self) -> str:
        data = {k: v for k, v in asdict(self).items() if k != "prose"}
        data = {k: v for k, v in data.items() if v not in (None, "")}
        fm = yaml.safe_dump(data, sort_keys=False, allow_unicode=True).strip()
        return f"{_FENCE}\n{fm}\n{_FENCE}\n{self.prose}"


# Canonical vessel_class vocabulary — the single source of truth. Kept in sync with the
# server input-schema enum (server.py) and the Profile Schema in SPEC.md. Every entry except
# the two propulsion-derived classes (power_driven / sailing) is a "special" status whose
# lighting overrides propulsion and maps to a requirements.yaml `situation` of the same name.
VESSEL_CLASSES = (
    "power_driven",
    "sailing",
    "anchored",
    "towing",
    "being_towed",
    "not_under_command",
    "restricted_manoeuvrability",
    "constrained_by_draught",
    "fishing",
    "pilot_vessel",
    "vessel_aground",
    "seaplane",
)

# Special states that override propulsion when deriving the lights situation. Derived from
# VESSEL_CLASSES so the two vocabularies can never drift (the SPEC↔code mismatch that let a
# RAM/aground/pilot vessel fall through to ordinary steaming lights — see issue #2).
_SPECIAL = frozenset(VESSEL_CLASSES) - {"power_driven", "sailing"}


@dataclass
class Profile:
    vessel_class: str
    length_m: float
    propulsion: str            # sail | machinery | sail_and_machinery
    regime: str                # international | inland | canadian
    condition: str             # day | night | restricted_visibility


def derive_situation(p: Profile) -> str:
    """Resolve the effective lights situation. Special states override propulsion;
    otherwise propulsion is authoritative (motorsailing is power-driven, not sailing).

    An unrecognized vessel_class is returned unchanged — never folded into power_driven —
    so it matches no requirements row and is surfaced as "not modeled" by check_compliance
    rather than silently passing with ordinary steaming lights."""
    if p.vessel_class in _SPECIAL:
        return p.vessel_class
    if p.vessel_class not in VESSEL_CLASSES:
        return p.vessel_class
    if p.propulsion == "sail_and_machinery":
        return "motorsailing"
    if p.propulsion == "machinery":
        return "power_driven"
    if p.propulsion == "sail":
        return "sailing"
    return p.vessel_class
