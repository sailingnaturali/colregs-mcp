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


# Canonical vessel_class vocabulary — the single source shared by SPEC.md, the
# server input schema enum, and the special-state set below. An input outside
# this set is rejected, never silently mapped to ordinary power-driven lights.
_SPECIAL = frozenset({
    "anchored", "vessel_aground", "not_under_command", "restricted_manoeuvrability",
    "constrained_by_draught", "fishing", "towing", "being_towed", "pilot_vessel",
    "seaplane",
})
VESSEL_CLASSES = frozenset({"power_driven", "sailing"}) | _SPECIAL
PROPULSIONS = frozenset({"sail", "machinery", "sail_and_machinery"})
REGIMES = frozenset({"international", "inland", "canadian"})
CONDITIONS = frozenset({"day", "night", "restricted_visibility"})

# Situations a requirements.yaml row may target: every special state, the two
# ordinary classes, plus the derived motorsailing state.
SITUATIONS = VESSEL_CLASSES | {"motorsailing"}


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
    Out-of-vocabulary input raises — an unrecognized vessel must never fall through
    to ordinary power-driven lights (fleet conventions R1)."""
    if p.vessel_class not in VESSEL_CLASSES:
        raise ValueError(
            f"unknown vessel_class {p.vessel_class!r}; expected one of {sorted(VESSEL_CLASSES)}")
    if p.vessel_class in _SPECIAL:
        return p.vessel_class
    if p.propulsion not in PROPULSIONS:
        raise ValueError(
            f"unknown propulsion {p.propulsion!r}; expected one of {sorted(PROPULSIONS)}")
    if p.propulsion == "sail_and_machinery":
        return "motorsailing"
    if p.propulsion == "machinery":
        return "power_driven"
    return "sailing"
