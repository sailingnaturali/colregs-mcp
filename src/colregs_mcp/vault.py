"""Load the rules/ markdown, requirements.yaml, and regime polygons from COLREGS_VAULT_PATH."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from colregs_mcp.models import Rule


def vault_path() -> Path:
    return Path(os.environ.get("COLREGS_VAULT_PATH", "~/.colregs-vault")).expanduser()


@dataclass
class Requirements:
    version: int = 1
    entries: list[dict] = field(default_factory=list)


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
            reqs = Requirements(version=int(data.get("version", 1)),
                                entries=list(data.get("entries", [])))

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
