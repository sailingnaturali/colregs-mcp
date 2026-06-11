"""Load the rules/ markdown, requirements.yaml, and regime polygons from COLREGS_VAULT_PATH."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from colregs_mcp.models import CONDITIONS, REGIMES, SITUATIONS, Rule

logger = logging.getLogger(__name__)

_MATCH_KEYS = {"situation", "condition", "regime", "length_lt", "length_gte"}


def vault_path() -> Path:
    return Path(os.environ.get("COLREGS_VAULT_PATH", "~/.colregs-vault")).expanduser()


def _validate_entries(entries: list) -> None:
    """Fail loudly at load on a malformed curated table — a typo'd match key or a
    catch-all empty match silently corrupts every verdict downstream."""
    for i, entry in enumerate(entries):
        ident = entry.get("id", f"entries[{i}]") if isinstance(entry, dict) else f"entries[{i}]"
        if not isinstance(entry, dict):
            raise ValueError(f"requirements.yaml: {ident} is not a mapping")
        match = entry.get("match")
        if not isinstance(match, dict) or not match:
            raise ValueError(f"requirements.yaml: {ident} has an empty or missing "
                             "match — it would attach to every profile")
        unknown = set(match) - _MATCH_KEYS
        if unknown:
            raise ValueError(f"requirements.yaml: {ident} has unknown match "
                             f"key(s) {sorted(unknown)}; allowed: {sorted(_MATCH_KEYS)}")
        sit = match.get("situation")
        if sit is not None and sit not in SITUATIONS:
            raise ValueError(f"requirements.yaml: {ident} has unknown situation "
                             f"{sit!r}; allowed: {sorted(SITUATIONS)}")
        cond = match.get("condition")
        if cond is not None and cond not in CONDITIONS:
            raise ValueError(f"requirements.yaml: {ident} has unknown condition {cond!r}")
        regime = match.get("regime")
        if regime is not None and regime != "any" and regime not in REGIMES:
            raise ValueError(f"requirements.yaml: {ident} has unknown regime {regime!r}")


@dataclass
class Requirements:
    version: int = 1
    entries: list[dict] = field(default_factory=list)

    def coverage_gaps(self) -> list[str]:
        """Report profile space the table does not model. These are warnings,
        not errors: an uncovered profile now fails safe at runtime (not_modeled),
        but the gaps should shrink as the curated table grows."""
        gaps: list[str] = []
        if not self.entries:
            gaps.append("requirements.yaml is empty — every compliance check will "
                        "report not_modeled")
            return gaps
        matches = [e.get("match", {}) for e in self.entries]
        for condition in sorted(CONDITIONS):
            if not any(m.get("condition") in (None, condition) for m in matches):
                gaps.append(f"no rows cover condition {condition!r}")
        # Per (situation, condition): do the length bands tile [0, inf)?
        seen = {(m.get("situation"), m.get("condition"))
                for m in matches if m.get("situation")}
        for situation, condition in sorted(seen, key=str):
            rows = [m for m in matches
                    if m.get("situation") == situation
                    and m.get("condition") in (None, condition)]
            if any("length_lt" not in m and "length_gte" not in m for m in rows):
                continue                      # an unbanded row covers all lengths
            top = 0.0
            for m in sorted(rows, key=lambda m: m.get("length_gte", 0.0)):
                if m.get("length_gte", 0.0) > top:
                    break                     # gap below this band
                top = max(top, m.get("length_lt", float("inf")))
            if top != float("inf"):
                gaps.append(f"{situation!r} ({condition}) length bands stop at "
                            f"{top:g} m — vessels at or above are not modeled")
        return gaps


@dataclass
class Vault:
    root: Path
    rules: list[Rule]
    requirements: Requirements
    regime_features: list[dict]

    @classmethod
    def load(cls, root: Path | None = None) -> "Vault":
        root = Path(root) if root is not None else vault_path()
        rules: list[Rule] = []
        rules_dir = root / "rules"
        if rules_dir.is_dir():
            for md in sorted(rules_dir.rglob("*.md")):
                rules.append(Rule.from_markdown(md.read_text(encoding="utf-8")))

        reqs = Requirements()
        req_file = root / "requirements.yaml"
        if req_file.is_file():
            data = yaml.safe_load(req_file.read_text(encoding="utf-8")) or {}
            entries = list(data.get("entries", []))
            _validate_entries(entries)
            reqs = Requirements(version=int(data.get("version", 1)), entries=entries)
        else:
            logger.warning("no requirements.yaml under %s — every compliance check "
                           "will report not_modeled", root)
        for gap in reqs.coverage_gaps():
            logger.warning("requirements coverage gap: %s", gap)

        features: list[dict] = []
        geo = root / "regime-polygons.geojson"
        if geo.is_file():
            gj = json.loads(geo.read_text(encoding="utf-8"))
            for feat in gj.get("features", []):
                features.append({
                    "regime": feat.get("properties", {}).get("regime"),
                    "geometry": feat.get("geometry", {}),
                })
        return cls(root=root, rules=rules, requirements=reqs, regime_features=features)

    def get_rule(self, number: str, regime: str) -> Rule | None:
        for r in self.rules:
            if r.number == str(number) and r.regime == regime:
                return r
        return None

    def rules_for_number(self, number: str) -> list[Rule]:
        return [r for r in self.rules if r.number == str(number)]
