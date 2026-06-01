"""Diff what the rules require against the lights actually shown (from the bus)."""

from __future__ import annotations

from colregs_mcp.models import Profile
from colregs_mcp.requirements import required_signals
from colregs_mcp.vault import Requirements


def check_compliance(reqs: Requirements, profile: Profile, observed) -> dict:
    req = required_signals(reqs, profile)
    on = set(observed)

    mandatory = {l["id"] for l in req["lights"]}
    missing = sorted(mandatory - on)
    satisfied = sorted(mandatory & on)

    unsatisfied_options: list[list[str]] = []
    for group in req["light_options"]:
        group_ids = {l["id"] for l in group}
        if group_ids & on == group_ids and group_ids:
            satisfied.extend(sorted(group_ids))
        else:
            unsatisfied_options.append(sorted(group_ids))
    # If any option group is satisfied, the requirement is met; only flag when NONE is.
    has_options = bool(req["light_options"])
    any_option_met = has_options and len(unsatisfied_options) < len(req["light_options"])
    options_unmet = has_options and not any_option_met

    extra = sorted(on & set(req["forbids"]))     # forbidden lights that are ON

    ok = not missing and not extra and not options_unmet
    return {
        "ok": ok,
        "missing": missing,
        "extra": extra,
        "unsatisfied_options": [] if any_option_met else unsatisfied_options,
        "satisfied": sorted(set(satisfied)),
        "citations": req["citations"],
    }
