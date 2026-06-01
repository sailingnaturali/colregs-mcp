"""Deterministic keyword ranking over rule text. No external deps."""

from __future__ import annotations

import re

from colregs_mcp.models import Rule

_WORD = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def _score(rule: Rule, terms: list[str]) -> int:
    haystack = _tokens(f"{rule.title} {rule.prose}")
    counts = {t: haystack.count(t) for t in set(terms)}
    return sum(counts.values())


def rank_rules(rules: list[Rule], query: str, limit: int = 5) -> list[Rule]:
    terms = _tokens(query)
    scored = [(r, _score(r, terms)) for r in rules]
    scored = [(r, s) for r, s in scored if s > 0]
    scored.sort(key=lambda pair: (-pair[1], pair[0].number, pair[0].regime))
    return [r for r, _ in scored[:limit]]
