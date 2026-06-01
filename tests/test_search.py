from pathlib import Path
from colregs_mcp.search import rank_rules
from colregs_mcp.vault import Vault

FIXTURE = Path(__file__).parent / "fixtures" / "vault"

def test_rank_rules_finds_motorsailing_cone():
    hits = rank_rules(Vault.load(FIXTURE).rules, "motorsailing conical shape", limit=3)
    assert hits[0].number == "25"

def test_rank_rules_returns_empty_for_no_overlap():
    hits = rank_rules(Vault.load(FIXTURE).rules, "zzzqqq", limit=3)
    assert hits == []
