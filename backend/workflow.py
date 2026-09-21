"""
Case workflow: statuses, allowed transitions, officer allocation and the
rules an officer's review must satisfy.

Pure functions, no Flask and no database, in the same spirit as scoring.py
and routing.py: the rules can be tested standalone and shown on a slide.

Lifecycle of a complaint:

    New ──> Under Review ──> Registered ──> Under Investigation ──> Charge Sheet Filed
     │            │              │                   │
     │            │              └───────────────────┴──> Closed
     └────────────┴──> Not Registered

"Not Registered", "Charge Sheet Filed" and "Closed" are final. Only an
administrator can move a complaint out of a final status.
"""

NEW = "New"
UNDER_REVIEW = "Under Review"
REGISTERED = "Registered"
NOT_REGISTERED = "Not Registered"
UNDER_INVESTIGATION = "Under Investigation"
CHARGE_SHEET_FILED = "Charge Sheet Filed"
CLOSED = "Closed"

STATUSES = (
    NEW, UNDER_REVIEW, REGISTERED, NOT_REGISTERED,
    UNDER_INVESTIGATION, CHARGE_SHEET_FILED, CLOSED,
)
FINAL_STATUSES = (NOT_REGISTERED, CHARGE_SHEET_FILED, CLOSED)
OPEN_STATUSES = tuple(s for s in STATUSES if s not in FINAL_STATUSES)

TRANSITIONS = {
    NEW: (UNDER_REVIEW, REGISTERED, NOT_REGISTERED),
    UNDER_REVIEW: (REGISTERED, NOT_REGISTERED),
    REGISTERED: (UNDER_INVESTIGATION, CLOSED),
    UNDER_INVESTIGATION: (CHARGE_SHEET_FILED, CLOSED),
    NOT_REGISTERED: (),
    CHARGE_SHEET_FILED: (),
    CLOSED: (),
}

# Statuses that need a note to the complainant explaining the outcome.
NOTE_REQUIRED = (NOT_REGISTERED, CLOSED)

MAX_TEXT = 1000


class ReviewError(ValueError):
    """A review request that breaks a workflow rule. The message is user-facing."""


def allowed_next(status, is_admin=False):
    """Statuses a complaint may move to from `status`."""
    if is_admin:
        return tuple(s for s in STATUSES if s != status)
    return TRANSITIONS.get(status, ())


# How much of an officer's capacity one open case consumes, by priority. A
# high-priority investigation takes more of an officer's time than a low one,
# so counting cases alone would load the wrong officer.
PRIORITY_WEIGHT = {"High": 3.0, "Medium": 2.0, "Low": 1.0}

# Availability multipliers. An officer marked busy is not excluded, but is
# chosen only when the alternative is a heavily loaded colleague.
AVAILABILITY_PENALTY = {"available": 0.0, "busy": 0.5}
UNAVAILABLE = "on_leave"


def case_weight(priority_level):
    return PRIORITY_WEIGHT.get(priority_level, 1.0)


def eligibility_tier(officer, unit, station):
    """
    How well an officer fits a case. Lower is better; None means not eligible.

      0  the case's unit, at the station handling it
      1  the case's unit, another station
      2  general duty (no unit), at that station
      3  general duty, anywhere
    """
    if not officer.get("active", True) or officer.get("availability") == UNAVAILABLE:
        return None
    same_station = station is not None and officer.get("station") == station
    if officer.get("unit") == unit:
        return 0 if same_station else 1
    if officer.get("unit") is None:
        return 2 if same_station else 3
    return None


def workload_ratio(officer):
    """Weighted open caseload as a fraction of the officer's capacity."""
    capacity = max(float(officer.get("capacity") or 1), 1.0)
    return float(officer.get("weighted_load") or 0) / capacity


def rank_officers(candidates, unit, station=None):
    """
    Eligible officers for a case, best first, each with the numbers behind the
    decision. Used both to allocate and to show why (the portal displays it).
    """
    ranked = []
    for officer in candidates:
        tier = eligibility_tier(officer, unit, station)
        if tier is None:
            continue
        load = workload_ratio(officer)
        score = tier + load + AVAILABILITY_PENALTY.get(officer.get("availability"), 0.0)
        ranked.append({
            **officer,
            "tier": tier,
            "load_ratio": round(load, 3),
            "score": round(score, 3),
        })
    # Ties break on who was given a case least recently, then on id, so the
    # same inputs always produce the same allocation.
    ranked.sort(key=lambda o: (o["score"], o["last_assigned_at"] or "", o["id"]))
    return ranked


def choose_officer(candidates, unit=None, station=None):
    """
    Pick the officer a new case should go to: the best-fitting unit and
    station, then the lightest weighted workload against their own capacity,
    with officers on leave skipped and busy officers deprioritised.

    Returns the officer's id, or None when nobody is eligible (the case then
    waits in the unassigned queue for an administrator).
    """
    ranked = rank_officers(candidates, unit, station)
    return ranked[0]["id"] if ranked else None


def plan_review(complaint, request, *, is_admin, known_units, officer_ids, now, actor_name=None):
    """
    Turn an officer's review request into database changes and audit events.

    complaint:   the current record, as returned by db.get_complaint()
    request:     dict with any of status, unit, override_reason, note,
                 signature_confirmed, assigned_to (admin only)
    known_units: units a complaint can be routed to
    officer_ids: ids of active officers (for reassignment)
    now:         UTC timestamp string for signature confirmation

    Returns (changes, events, reallocate):
      changes    -- {column: value} for the complaints row
      events     -- [(action, detail), ...] for the audit trail
      reallocate -- True when the unit changed and no officer was named,
                    so the caller should allocate within the new unit
    Raises ReviewError when a rule is broken.
    """
    current = complaint["status"]
    review = complaint["review"]
    is_citizen = complaint["source"] == "citizen"

    status = request.get("status") or None
    unit = (request.get("unit") or "").strip() or None
    reason = (request.get("override_reason") or "").strip() or None
    note = (request.get("note") or "").strip() or None
    confirm_signature = request.get("signature_confirmed") is True
    assign_to = request.get("assigned_to")

    if any(v and len(v) > MAX_TEXT for v in (note, reason)):
        raise ReviewError(f"Notes must be under {MAX_TEXT} characters.")
    if current in FINAL_STATUSES and not is_admin:
        raise ReviewError("This case is closed. Only an administrator can reopen it.")
    if status is not None and status not in STATUSES:
        raise ReviewError(f"Status must be one of: {', '.join(STATUSES)}.")
    if status and status != current and status not in allowed_next(current, is_admin):
        raise ReviewError(f"A case that is {current} cannot move to {status}.")
    if assign_to is not None and not is_admin:
        raise ReviewError("Only an administrator can reassign a case.")

    changes, events = {}, []
    reallocate = False

    if unit and unit != complaint["routing"]["unit"]:
        if unit not in known_units:
            raise ReviewError("Unknown unit.")
        if not reason:
            raise ReviewError("Give a reason for transferring the case.")
        changes["routed_unit"] = unit
        changes["override_reason"] = reason
        if not review["original_unit"]:
            changes["original_unit"] = complaint["routing"]["unit"]
        events.append(("rerouted", f"{complaint['routing']['unit']} -> {unit}: {reason}"))
        reallocate = assign_to is None

    if assign_to is not None:
        if assign_to not in officer_ids:
            raise ReviewError("Choose an active officer.")
        if assign_to != complaint["assignment"]["officer_id"]:
            changes["assigned_to"] = assign_to

    signed = bool(review["signature_confirmed_at"])
    if confirm_signature and is_citizen and not signed:
        # The complainant signed at the station and the officer is recording
        # it. A complainant signing online goes through the signing endpoint,
        # which records method "digital" instead.
        evidence = f"Signed at the station, confirmed by {actor_name or 'the officer'}"
        changes["signature_confirmed_at"] = now
        changes["signature_method"] = "in_person"
        changes["signature_evidence"] = evidence
        events.append(("signature_confirmed", evidence))
        signed = True

    if status in NOTE_REQUIRED and not (note or review["officer_note"]):
        raise ReviewError("Add a note to the complainant explaining the outcome.")
    if status == REGISTERED and is_citizen and not signed:
        raise ReviewError("Confirm the informant has signed the complaint before registering it.")

    # Any officer action on a new case means it is being looked at. A bare
    # reassignment by an administrator does not count.
    acted = note or any(k != "assigned_to" for k in changes)
    if status is None and current == NEW and acted:
        status = UNDER_REVIEW
    if status and status != current:
        changes["status"] = status
        events.append(("status_changed", f"{current} -> {status}"))

    if note and note != review["officer_note"]:
        changes["officer_note"] = note
        events.append(("note_added", note))

    if not changes:
        raise ReviewError("Nothing to update.")
    return changes, events, reallocate
