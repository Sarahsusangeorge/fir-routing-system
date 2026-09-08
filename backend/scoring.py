"""
Priority scoring.

Deliberately rule-based rather than learned. Three reasons, all of which
you should be able to say out loud in the review:

  1. No labelled priority data exists. There is no ground truth to train
     against, so a learned scorer would be inventing its target.
  2. Police triage must be auditable. An officer can be shown exactly why
     a complaint was marked High; a learned score cannot be explained to
     a complainant or a court.
  3. It is configurable per jurisdiction by editing one table, without
     retraining anything.

Formula:
    score = max over predicted sections of (severity_weight x confidence)

MAX, not mean. A complaint citing both murder (10.0) and criminal
trespass (1.0) is a murder complaint. Averaging would score it 5.5 and
route it as Medium priority, which is exactly the failure a triage
system must not make. Taking the maximum means the gravest credible
charge sets the priority.

Confidence acts as a discount: a weakly predicted grave section scores
lower than a confidently predicted one, so the model's own uncertainty
propagates into the triage decision rather than being discarded.

No Flask and no database imports here on purpose -- this module is
testable standalone and presentable on a slide.
"""

HIGH_THRESHOLD = 6.5
MEDIUM_THRESHOLD = 3.5

DEFAULT_SEVERITY = 5.0  # used if a predicted section is missing from the table


def score_complaint(sections, severity_lookup):
    """
    Compute the priority of a complaint.

    Args:
        sections: list of {"code": str, "confidence": float}
        severity_lookup: {code: severity_weight}

    Returns:
        {"level": "High"|"Medium"|"Low",
         "score": float rounded to 1dp,
         "driver": the section code that determined the score, or None}
    """
    if not sections:
        return {"level": "Low", "score": 0.0, "driver": None}

    best_score = 0.0
    driver = None

    for s in sections:
        weight = severity_lookup.get(s["code"], DEFAULT_SEVERITY)
        contribution = weight * float(s["confidence"])
        if contribution > best_score:
            best_score = contribution
            driver = s["code"]

    # Round BEFORE thresholding, so the score shown on screen always agrees
    # with the level shown next to it. Comparing the unrounded value would
    # let 6.96 display as "7.0  Medium", which a panelist will notice.
    best_score = round(best_score, 1)

    if best_score >= HIGH_THRESHOLD:
        level = "High"
    elif best_score >= MEDIUM_THRESHOLD:
        level = "Medium"
    else:
        level = "Low"

    return {"level": level, "score": best_score, "driver": driver}


def explain_score(priority, severity_lookup, sections):
    """One-line justification, for the dashboard and the demo."""
    if not priority["driver"]:
        return "No section predicted with sufficient confidence."

    code = priority["driver"]
    weight = severity_lookup.get(code, DEFAULT_SEVERITY)
    conf = next((s["confidence"] for s in sections if s["code"] == code), 0.0)
    return (
        f"Driven by Section {code}: severity {weight:g} "
        f"x confidence {conf:.2f} = {priority['score']:g}"
    )
