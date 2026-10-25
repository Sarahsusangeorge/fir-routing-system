"""
Administrator endpoints: staff account management.

Officer and administrator accounts are created here, never through
self-registration. Citizens create their own accounts by verifying a code
sent to their email or mobile number (see auth.py).

Staff changes keep case allocation consistent: a new or reactivated officer
picks up waiting cases, and a deactivated officer's open cases move to
colleagues.
"""

import re
import sqlite3

from flask import Blueprint, jsonify
from flask_jwt_extended import current_user
from werkzeug.security import generate_password_hash

import db
import routing as routing_engine
from auth import EMAIL_RE, MIN_PASSWORD_LENGTH, STAFF_ROLES, json_object, normalise_mobile, role_required, text_field

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def password_problem(password):
    """Return a message if the password is too weak, else None."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if password.lower() == password or password.upper() == password or not any(c.isdigit() for c in password):
        return "Password must mix upper- and lower-case letters and include a number."
    return None


def _valid_unit(unit):
    return unit in db.list_units(routing_engine.DEFAULT_UNIT)


@bp.route("/users", methods=["GET"])
@role_required("admin")
def list_staff():
    return jsonify({"users": db.list_users(roles=STAFF_ROLES)}), 200


@bp.route("/users", methods=["POST"])
@role_required("admin")
def create_staff():
    payload = json_object()
    email = text_field(payload, "email").strip().lower()
    username = text_field(payload, "username").strip().lower() or None
    name = text_field(payload, "name").strip()
    role = payload.get("role")
    password = text_field(payload, "password")
    unit = text_field(payload, "unit").strip() or None
    station = text_field(payload, "station").strip() or None
    capacity = payload.get("capacity")

    if not EMAIL_RE.match(email):
        return jsonify({"error": "Enter a valid email address."}), 400
    if not 2 <= len(name) <= 120:
        return jsonify({"error": "Enter the staff member's full name."}), 400
    if role not in STAFF_ROLES:
        return jsonify({"error": "Role must be officer or admin."}), 400
    if role == "admin":
        unit = None
    if unit and not _valid_unit(unit):
        return jsonify({"error": "Unknown unit."}), 400
    if station and not db.station_exists(station):
        return jsonify({"error": "Unknown police station."}), 400
    if username and not re.fullmatch(r"[a-z0-9._-]{3,32}", username):
        return jsonify({"error": "Username must be 3-32 characters: letters, digits, dot, dash or underscore."}), 400
    if capacity is not None and (isinstance(capacity, bool) or not (isinstance(capacity, int) and 1 <= capacity <= 100)):
        return jsonify({"error": "Capacity must be a whole number between 1 and 100."}), 400
    problem = password_problem(password)
    if problem:
        return jsonify({"error": problem}), 400

    try:
        user_id = db.create_user(email, name, role, generate_password_hash(password), unit=unit,
                                 username=username, station=station, capacity=capacity)
    except sqlite3.IntegrityError:
        return jsonify({"error": "An account with this email or username already exists."}), 409
    placed = db.allocate_unassigned(actor_id=current_user["id"]) if role == "officer" else 0
    return jsonify({"user": _staff_row(user_id), "cases_assigned": placed}), 201


def _staff_row(user_id):
    return next(u for u in db.list_users(roles=STAFF_ROLES) if u["id"] == user_id)


@bp.route("/users/<int:user_id>", methods=["PATCH"])
@role_required("admin")
def update_staff(user_id):
    user = db.get_user(user_id)
    if user is None or user["role"] not in STAFF_ROLES:
        return jsonify({"error": "Staff account not found."}), 404

    payload = json_object()
    changes = {}

    if "active" in payload:
        active = 1 if payload["active"] else 0
        if not active and user["role"] == "admin":
            if user_id == current_user["id"]:
                return jsonify({"error": "You cannot deactivate your own account."}), 400
            if db.count_active_admins() <= 1:
                return jsonify({"error": "At least one administrator must remain active."}), 400
        changes["active"] = active

    if "unit" in payload and user["role"] == "officer":
        unit = text_field(payload, "unit").strip() or None
        if unit and not _valid_unit(unit):
            return jsonify({"error": "Unknown unit."}), 400
        changes["unit"] = unit

    if "station" in payload and user["role"] == "officer":
        station = text_field(payload, "station").strip() or None
        if station and not db.station_exists(station):
            return jsonify({"error": "Unknown police station."}), 400
        changes["station"] = station

    if "availability" in payload and user["role"] == "officer":
        if payload["availability"] not in ("available", "busy", "on_leave"):
            return jsonify({"error": "availability must be available, busy or on_leave."}), 400
        changes["availability"] = payload["availability"]

    if "capacity" in payload and user["role"] == "officer":
        capacity = payload["capacity"]
        if isinstance(capacity, bool) or not (isinstance(capacity, int) and 1 <= capacity <= 100):
            return jsonify({"error": "Capacity must be a whole number between 1 and 100."}), 400
        changes["capacity"] = capacity

    if text_field(payload, "password"):
        problem = password_problem(payload["password"])
        if problem:
            return jsonify({"error": problem}), 400
        changes["password_hash"] = generate_password_hash(payload["password"])

    if not changes:
        return jsonify({"error": "Nothing to update."}), 400

    db.update_user(user_id, **changes)

    moved = placed = 0
    if user["role"] == "officer":
        deactivated = changes.get("active") == 0 and user["active"]
        on_leave = changes.get("availability") == "on_leave"
        unit_changed = "unit" in changes and changes["unit"] != user["unit"]
        if deactivated or unit_changed or on_leave:
            moved = db.redistribute_cases(user_id, actor_id=current_user["id"])
        if changes.get("active") == 1 or unit_changed:
            placed = db.allocate_unassigned(actor_id=current_user["id"])
    return jsonify({"user": _staff_row(user_id), "cases_moved": moved, "cases_assigned": placed}), 200


@bp.route("/users/<int:user_id>/phone", methods=["PUT"])
@role_required("admin")
def repoint_phone(user_id):
    """
    Move a citizen's account to a new mobile number after their identity has
    been verified in person.

    This is the recovery path for someone who lost the SIM they signed up
    with and so cannot verify the change themselves. It keeps the account id,
    so their complaints stay with them, and it is recorded in phone_history
    with the administrator who did it.
    """
    user = db.get_user(user_id)
    if user is None or user["role"] != "citizen":
        return jsonify({"error": "Citizen account not found."}), 404

    payload = json_object()
    phone = normalise_mobile(payload.get("phone"))
    reason = text_field(payload, "reason").strip()
    if phone is None:
        return jsonify({"error": "Enter a valid 10-digit Indian mobile number."}), 400
    if not reason:
        return jsonify({"error": "Record how the citizen's identity was verified."}), 400
    if db.get_user_by_login(phone=phone):
        return jsonify({"error": "That number is already registered to another account."}), 409

    try:
        old = db.change_phone(user_id, phone, current_user["id"], f"Station verification: {reason}")
    except sqlite3.IntegrityError:
        return jsonify({"error": "That number is already registered to another account."}), 409
    return jsonify({"user": db.get_user(user_id), "previous_phone": old,
                    "history": db.list_phone_history(user_id)}), 200


# ---------------------------------------------------------------------------
# Decision policy: severity weights and routing rules (FR9)
# ---------------------------------------------------------------------------
#
# Priority and routing are driven by two reference tables rather than by model
# weights, so a jurisdiction can change policy without retraining. These
# endpoints are what make that claim true in the running system. Every change
# is recorded in policy_changes with the administrator who made it, and takes
# effect for complaints analysed afterwards; results already stored against a
# complaint are left exactly as they were recorded.

MIN_SEVERITY, MAX_SEVERITY = 1.0, 10.0
MAX_PRECEDENCE = 999


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


@bp.route("/sections", methods=["GET"])
@role_required("admin")
def list_sections():
    return jsonify({"sections": db.list_sections()}), 200


@bp.route("/sections/<code>", methods=["PATCH"])
@role_required("admin")
def update_section(code):
    section = db.get_section(code)
    if section is None:
        return jsonify({"error": "Unknown IPC section."}), 404

    payload = json_object()
    changes = {}

    if "severity_weight" in payload:
        weight = _number(payload["severity_weight"])
        if weight is None or not MIN_SEVERITY <= weight <= MAX_SEVERITY:
            return jsonify({"error": f"Severity weight must be a number between "
                                     f"{MIN_SEVERITY:g} and {MAX_SEVERITY:g}."}), 400
        changes["severity_weight"] = weight

    for flag in ("cognizable", "bailable"):
        if flag in payload:
            if not isinstance(payload[flag], bool):
                return jsonify({"error": f"{flag} must be true or false."}), 400
            changes[flag] = 1 if payload[flag] else 0

    if "max_punishment_years" in payload:
        years = payload["max_punishment_years"]
        if years is None:
            changes["max_punishment_years"] = None          # life imprisonment or death
        else:
            years = _number(years)
            if years is None or not 0 < years <= 100:
                return jsonify({"error": "Maximum punishment must be a number of years above 0, "
                                         "or null for life imprisonment or death."}), 400
            changes["max_punishment_years"] = years

    if not changes:
        return jsonify({"error": "Nothing to update."}), 400

    updated = db.update_section(code, changes, actor_id=current_user["id"])
    return jsonify({"section": updated,
                    "note": "Applies to complaints analysed from now on; "
                            "results already recorded are unchanged."}), 200


@bp.route("/routing-rules", methods=["GET"])
@role_required("admin")
def list_routing_rules():
    rules = db.list_all_routing_rules()
    units = sorted({r["unit"] for r in rules} | {routing_engine.DEFAULT_UNIT})
    return jsonify({
        "rules": rules,
        "units": units,
        "default_unit": routing_engine.DEFAULT_UNIT,
        "officers_by_unit": {u: db.count_officers_for_unit(u) for u in units},
    }), 200


def _rule_fields(payload, require_all):
    """Validate unit and precedence. Returns (changes, error_response)."""
    changes = {}

    if "unit" in payload or require_all:
        unit = text_field(payload, "unit").strip()
        if not 2 <= len(unit) <= 80:
            return None, (jsonify({"error": "Enter the unit that should handle this section."}), 400)
        changes["unit"] = unit

    if "precedence" in payload or require_all:
        precedence = payload.get("precedence")
        if isinstance(precedence, bool) or not isinstance(precedence, int) \
                or not 1 <= precedence <= MAX_PRECEDENCE:
            return None, (jsonify({"error": f"Precedence must be a whole number between 1 and "
                                            f"{MAX_PRECEDENCE}; lower wins."}), 400)
        changes["precedence"] = precedence

    return changes, None


@bp.route("/routing-rules", methods=["POST"])
@role_required("admin")
def create_routing_rule():
    payload = json_object()
    code = text_field(payload, "section_code").strip()
    if db.get_section(code) is None:
        return jsonify({"error": "Unknown IPC section."}), 404

    changes, error = _rule_fields(payload, require_all=True)
    if error:
        return error
    if db.routing_rule_exists(code, changes["unit"]):
        return jsonify({"error": "That section already routes to that unit."}), 409

    rule = db.create_routing_rule(code, changes["unit"], changes["precedence"],
                                  actor_id=current_user["id"])
    return jsonify({"rule": rule,
                    "officers_available": db.count_officers_for_unit(changes["unit"])}), 201


@bp.route("/routing-rules/<int:rule_id>", methods=["PATCH"])
@role_required("admin")
def update_routing_rule(rule_id):
    rule = db.get_routing_rule(rule_id)
    if rule is None:
        return jsonify({"error": "Routing rule not found."}), 404

    payload = json_object()
    changes, error = _rule_fields(payload, require_all=False)
    if error:
        return error
    if not changes:
        return jsonify({"error": "Nothing to update."}), 400
    if "unit" in changes and db.routing_rule_exists(rule["section_code"], changes["unit"],
                                                    exclude_id=rule_id):
        return jsonify({"error": "That section already routes to that unit."}), 409

    updated = db.update_routing_rule(rule_id, changes, actor_id=current_user["id"])
    return jsonify({"rule": updated,
                    "officers_available": db.count_officers_for_unit(updated["unit"])}), 200


@bp.route("/routing-rules/<int:rule_id>", methods=["DELETE"])
@role_required("admin")
def delete_routing_rule(rule_id):
    rule = db.get_routing_rule(rule_id)
    if rule is None:
        return jsonify({"error": "Routing rule not found."}), 404
    db.delete_routing_rule(rule_id, actor_id=current_user["id"])
    return jsonify({"deleted": rule_id,
                    "note": f"Complaints citing Section {rule['section_code']} will no longer "
                            f"route to {rule['unit']} on that rule."}), 200


@bp.route("/policy-changes", methods=["GET"])
@role_required("admin")
def policy_changes():
    return jsonify({"changes": db.list_policy_changes(limit=200)}), 200


# ---------------------------------------------------------------------------
# Stations and units (FR9, reference data)
# ---------------------------------------------------------------------------
#
# Allocation keeps a case at the station it was filed at and decides
# eligibility by unit, so both are part of how the system decides and both
# belong in the policy change log. Neither is protected by a foreign key, so
# removing or renaming one has to account for what already points at it.

STATION_CODE_RE = re.compile(r"[A-Z0-9][A-Z0-9-]{1,31}")


@bp.route("/stations", methods=["GET"])
@role_required("admin")
def list_stations_admin():
    usage = db.stations_in_use()
    stations = [
        {**s, **usage.get(s["code"], {"officers": 0, "complaints": 0})}
        for s in db.list_stations()
    ]
    # A station that officers or complaints still name but that was never
    # registered would otherwise be invisible here while remaining in use.
    known = {s["code"] for s in stations}
    orphans = [
        {"code": code, "name": None, "district": None, "unregistered": True, **counts}
        for code, counts in sorted(usage.items())
        if code not in known
    ]
    return jsonify({"stations": stations + orphans}), 200


@bp.route("/stations", methods=["POST"])
@role_required("admin")
def create_station():
    payload = json_object()
    code = text_field(payload, "code").strip().upper()
    name = text_field(payload, "name").strip()
    district = text_field(payload, "district").strip() or None

    if not STATION_CODE_RE.fullmatch(code):
        return jsonify({"error": "Station code must be 2-32 characters: capitals, digits or dashes."}), 400
    if not 2 <= len(name) <= 120:
        return jsonify({"error": "Enter the station's name."}), 400
    if db.get_station(code):
        return jsonify({"error": "A station with that code already exists."}), 409

    station = db.create_station(code, name, district, actor_id=current_user["id"])
    return jsonify({"station": {**station, "officers": 0, "complaints": 0}}), 201


@bp.route("/stations/<code>", methods=["PATCH"])
@role_required("admin")
def update_station(code):
    if db.get_station(code) is None:
        return jsonify({"error": "Station not found."}), 404

    payload = json_object()
    changes = {}
    if "name" in payload:
        name = text_field(payload, "name").strip()
        if not 2 <= len(name) <= 120:
            return jsonify({"error": "Enter the station's name."}), 400
        changes["name"] = name
    if "district" in payload:
        changes["district"] = text_field(payload, "district").strip() or None
    if not changes:
        return jsonify({"error": "Nothing to update."}), 400

    # The code is the identifier officers and complaints store, so it is not
    # editable: changing it would orphan every record that holds it.
    updated = db.update_station(code, changes, actor_id=current_user["id"])
    usage = db.stations_in_use().get(code, {"officers": 0, "complaints": 0})
    return jsonify({"station": {**updated, **usage}}), 200


@bp.route("/stations/<code>", methods=["DELETE"])
@role_required("admin")
def delete_station(code):
    station = db.get_station(code)
    if station is None:
        return jsonify({"error": "Station not found."}), 404

    usage = db.stations_in_use().get(code, {"officers": 0, "complaints": 0})
    if usage["officers"] or usage["complaints"]:
        return jsonify({
            "error": f"{station['name']} is still in use by {usage['officers']} officer(s) and "
                     f"{usage['complaints']} complaint(s). Move them first.",
            "officers": usage["officers"],
            "complaints": usage["complaints"],
        }), 409

    db.delete_station(code, actor_id=current_user["id"])
    return jsonify({"deleted": code}), 200


@bp.route("/units", methods=["GET"])
@role_required("admin")
def list_units_admin():
    usage = db.units_in_use()
    registered = {u["name"]: u for u in db.list_registered_units()}
    units = []
    for name in db.list_units(routing_engine.DEFAULT_UNIT):
        counts = usage.get(name, {"officers": 0, "rules": 0})
        units.append({
            "name": name,
            "description": registered.get(name, {}).get("description"),
            "registered": name in registered,
            "is_default": name == routing_engine.DEFAULT_UNIT,
            **counts,
        })
    return jsonify({"units": units, "default_unit": routing_engine.DEFAULT_UNIT}), 200


@bp.route("/units", methods=["POST"])
@role_required("admin")
def create_unit():
    payload = json_object()
    name = text_field(payload, "name").strip()
    description = text_field(payload, "description").strip() or None

    if not 2 <= len(name) <= 80:
        return jsonify({"error": "Enter the unit's name."}), 400
    if db.unit_is_registered(name):
        return jsonify({"error": "That unit already exists."}), 409

    unit = db.create_unit(name, description, actor_id=current_user["id"])
    return jsonify({"unit": {**unit, "registered": True, "officers": 0, "rules": 0,
                             "is_default": name == routing_engine.DEFAULT_UNIT}}), 201


@bp.route("/units/<name>", methods=["PATCH"])
@role_required("admin")
def update_unit(name):
    if not db.unit_is_registered(name):
        return jsonify({"error": "Unit not found. Units already in use but never "
                                 "registered must be created here first."}), 404

    payload = json_object()
    new_name = text_field(payload, "name").strip() if "name" in payload else name
    description = (text_field(payload, "description").strip() or None
                   if "description" in payload else db.UNSET)

    if not 2 <= len(new_name) <= 80:
        return jsonify({"error": "Enter the unit's name."}), 400
    if new_name != name and db.unit_is_registered(new_name):
        return jsonify({"error": "Another unit already has that name."}), 409
    if new_name == name and description is db.UNSET:
        return jsonify({"error": "Nothing to update."}), 400

    moved = db.units_in_use().get(name, {"officers": 0, "rules": 0})
    unit = db.rename_unit(name, new_name, description, actor_id=current_user["id"])
    return jsonify({
        "unit": {**unit, "registered": True,
                 "is_default": new_name == routing_engine.DEFAULT_UNIT,
                 **db.units_in_use().get(new_name, {"officers": 0, "rules": 0})},
        "officers_moved": moved["officers"] if new_name != name else 0,
        "rules_moved": moved["rules"] if new_name != name else 0,
    }), 200


@bp.route("/units/<name>", methods=["DELETE"])
@role_required("admin")
def delete_unit(name):
    if not db.unit_is_registered(name):
        return jsonify({"error": "Unit not found."}), 404
    if name == routing_engine.DEFAULT_UNIT:
        return jsonify({"error": f"{name} is the fallback every unmatched complaint "
                                 f"routes to and cannot be removed."}), 400

    usage = db.units_in_use().get(name, {"officers": 0, "rules": 0})
    if usage["officers"] or usage["rules"]:
        return jsonify({
            "error": f"{name} is still used by {usage['officers']} officer(s) and "
                     f"{usage['rules']} routing rule(s). Reassign them first.",
            "officers": usage["officers"],
            "rules": usage["rules"],
        }), 409

    db.delete_unit(name, actor_id=current_user["id"])
    return jsonify({"deleted": name}), 200
