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
