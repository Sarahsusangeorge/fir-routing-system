"""
Routing engine.

Maps predicted IPC sections to the police unit that should handle the
complaint. A lookup table rather than a model, and that is a feature:
jurisdictions differ in how they organise specialised units, so routing
policy has to be configurable by an administrator without retraining.

Precedence: lower number wins. The ordering is victim-centric -- offences
against women and children outrank general violent crime, so a complaint
citing both Section 302 and Section 376 routes to the Women & Child
Protection Unit rather than Crime Branch.

Fallback is the Local Police Station, which is also the correct real-world
default: every complaint has a jurisdiction even when no specialised unit
applies.
"""

DEFAULT_UNIT = "Local Police Station"


def route_complaint(sections, rules, section_titles=None):
    """
    Decide which unit handles this complaint.

    Args:
        sections: list of {"code": str, "confidence": float}
        rules:    list of {"section_code", "unit", "precedence"}
        section_titles: optional {code: title} for a readable reason

    Returns:
        {"unit": str, "reason": str, "matched_section": str|None}
    """
    if not sections or not rules:
        return {
            "unit": DEFAULT_UNIT,
            "reason": "No specialised unit matched; routed to jurisdiction by default.",
            "matched_section": None,
        }

    predicted = {s["code"] for s in sections}
    applicable = [r for r in rules if r["section_code"] in predicted]

    if not applicable:
        return {
            "unit": DEFAULT_UNIT,
            "reason": "No routing rule matched the predicted sections.",
            "matched_section": None,
        }

    # Lowest precedence wins; ties broken by the higher-confidence section.
    confidence = {s["code"]: float(s["confidence"]) for s in sections}
    winner = min(
        applicable,
        key=lambda r: (r["precedence"], -confidence.get(r["section_code"], 0.0)),
    )

    code = winner["section_code"]
    title = (section_titles or {}).get(code)
    descriptor = f"Section {code}" + (f" ({title})" if title else "")

    other_units = {r["unit"] for r in applicable} - {winner["unit"]}
    if other_units:
        reason = (
            f"{descriptor} takes precedence over "
            f"{', '.join(sorted(other_units))}."
        )
    else:
        reason = f"{descriptor} is handled by {winner['unit']}."

    return {
        "unit": winner["unit"],
        "reason": reason,
        "matched_section": code,
    }
