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

from flask import Blueprint, jsonify, request
from flask_jwt_extended import current_user
from werkzeug.security import generate_password_hash

import db
import routing as routing_engine
from auth import EMAIL_RE, MIN_PASSWORD_LENGTH, STAFF_ROLES, normalise_mobile, role_required

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
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    username = (payload.get("username") or "").strip().lower() or None
    name = (payload.get("name") or "").strip()
    role = payload.get("role")
    password = payload.get("password") or ""
    unit = (payload.get("unit") or "").strip() or None
    station = (payload.get("station") or "").strip() or None
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
    if capacity is not None and not (isinstance(capacity, int) and 1 <= capacity <= 100):
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

    payload = request.get_json(silent=True) or {}
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
        unit = (payload["unit"] or "").strip() or None
        if unit and not _valid_unit(unit):
            return jsonify({"error": "Unknown unit."}), 400
        changes["unit"] = unit

    if "station" in payload and user["role"] == "officer":
        station = (payload["station"] or "").strip() or None
        if station and not db.station_exists(station):
            return jsonify({"error": "Unknown police station."}), 400
        changes["station"] = station

    if "availability" in payload and user["role"] == "officer":
        if payload["availability"] not in ("available", "busy", "on_leave"):
            return jsonify({"error": "availability must be available, busy or on_leave."}), 400
        changes["availability"] = payload["availability"]

    if "capacity" in payload and user["role"] == "officer":
        capacity = payload["capacity"]
        if not (isinstance(capacity, int) and 1 <= capacity <= 100):
            return jsonify({"error": "Capacity must be a whole number between 1 and 100."}), 400
        changes["capacity"] = capacity

    if payload.get("password"):
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

    payload = request.get_json(silent=True) or {}
    phone = normalise_mobile(payload.get("phone"))
    reason = (payload.get("reason") or "").strip()
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
