"""
FIR/Complaint Categorization & Intelligent Routing System
Backend API (Track B).

Routes are deliberately thin: they validate input, call the pipeline, and
shape the response to the frozen contract. All decision logic lives in
scoring.py and routing.py so it can be tested and presented separately.

Every route except /api/health requires a signed-in user; see auth.py for
how sessions work and which role can do what.

Run:
    python app.py
"""

import os
import re
import traceback
from datetime import datetime, timezone

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:  # python-dotenv is optional
    pass

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import current_user

import admin
import auth
import classifier
import db
import routing as routing_engine
import scoring
import workflow
from auth import STAFF_ROLES, role_required

app = Flask(__name__)

# Cookies only travel cross-origin when CORS names the exact frontend origin
# and allows credentials. Use the same hostname for both servers (localhost
# with localhost, not localhost with 127.0.0.1), or the browser treats them
# as different sites and drops the session cookie.
ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get(
        "NIVARA_FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",") if o.strip()
]
CORS(
    app,
    origins=ALLOWED_ORIGINS,
    supports_credentials=True,
    expose_headers=["X-CSRF-TOKEN"],
)

auth.init_app(app)
app.register_blueprint(admin.bp)
db.init_db()
# Place any open case still waiting for an officer (for example, cases from
# a database created before allocation existed).
db.allocate_unassigned()

MAX_INPUT_CHARS = 20000
MIN_INPUT_CHARS = 15
MAX_DIARY_CHARS = 2000


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def process_complaint(text, filed_by=None, source="officer", station=None):
    """
    Full pipeline: classify -> score -> route -> persist -> allocate.
    Returns the response body defined by the API contract.
    """
    raw_sections = classifier.predict(text)
    codes = [s["code"] for s in raw_sections]

    reference = db.get_sections_by_code(codes)
    severity_lookup = {c: reference[c]["severity_weight"] for c in reference}
    titles = {c: reference[c]["title"] for c in reference}

    sections = [
        {
            "code": s["code"],
            "title": titles.get(s["code"], "Unmapped section"),
            "confidence": round(float(s["confidence"]), 4),
        }
        for s in raw_sections
    ]

    priority = scoring.score_complaint(sections, severity_lookup)
    priority["basis"] = scoring.explain_score(priority, severity_lookup, sections)

    rules = db.get_routing_rules(codes)
    route = routing_engine.route_complaint(sections, rules, titles)

    explanation = classifier.explain(text, raw_sections)

    complaint_id, received_at = db.save_complaint(
        text, sections, priority, route, explanation,
        filed_by=filed_by, source=source, station=station,
    )
    db.allocate(complaint_id, actor_id=filed_by)
    assignment = db.get_complaint(complaint_id)["assignment"]

    return {
        "complaint_id": complaint_id,
        "complaint_text": text,
        "received_at": received_at,
        "sections": sections,
        "priority": priority,
        "routing": route,
        "explanation": explanation,
        "model_backend": classifier.backend_name(),
        "status": workflow.NEW,
        "source": source,
        "station": station,
        "assignment": assignment,
    }


def citizen_view(c):
    """
    What a complainant sees. The model's section predictions and priority are
    an officer's working material, not a legal determination, so they are
    not shown. The unit and investigating officer are shown once an officer
    has reviewed the complaint.
    """
    review = c["review"]
    reviewed = bool(review["reviewed_at"])
    return {
        "complaint_id": c["complaint_id"],
        "complaint_text": c["complaint_text"],
        "received_at": c["received_at"],
        "status": c["status"],
        "station": c["station"],
        "unit": c["routing"]["unit"] if reviewed else None,
        "officer": c["assignment"]["officer_name"] if reviewed else None,
        "officer_unit": c["assignment"]["officer_unit"] if reviewed else None,
        "officer_station": c["assignment"]["officer_station"] if reviewed else None,
        "officer_note": review["officer_note"],
        "signature_due_at": review["signature_due_at"],
        "signature_confirmed_at": review["signature_confirmed_at"],
        "signature_method": review["signature_method"],
        "can_sign_digitally": (
            c["source"] == "citizen"
            and not review["signature_confirmed_at"]
            and c["status"] in (workflow.NEW, workflow.UNDER_REVIEW)
        ),
        "events": [
            {"action": e["action"], "detail": e["detail"], "created_at": e["created_at"]}
            for e in db.list_events(c["complaint_id"])
            # The case diary and internal notes are not the complainant's to see.
            if e["action"] in ("filed", "assigned", "status_changed", "signature_confirmed")
        ],
    }


def is_admin(user):
    return user["role"] == "admin"


def owns_case(user, complaint):
    """Who may act on a case: the officer it is allocated to, or an administrator."""
    return is_admin(user) or complaint["assignment"]["officer_id"] == user["id"]


def _mask_contact(complainant):
    """
    Officers can see every case in the district, but a complainant's contact
    details are personal data, so they are shown only to the officer handling
    the case and to administrators.
    """
    if not complainant:
        return None
    phone = complainant.get("phone")
    email = complainant.get("email")
    return {
        "name": complainant["name"],
        "phone": f"{phone[:-4]}****" if phone else None,
        "email": f"{email.split('@')[0][:2]}***@{email.split('@')[1]}" if email and "@" in email else None,
        "masked": True,
    }


def staff_view(complaint_id, full=True):
    """
    A case as staff see it. full=False is the transparency view: every
    officer can read any case and see who holds it, without the
    complainant's contact details or the investigating officer's case diary.
    """
    c = db.get_complaint(complaint_id)
    events = db.list_events(complaint_id)
    if full:
        c["events"] = events
        c["allowed_statuses"] = list(workflow.allowed_next(c["status"], is_admin(current_user)))
        c["can_act"] = True
    else:
        c["complainant"] = _mask_contact(c["complainant"])
        c["events"] = [e for e in events if e["action"] != "diary_entry"]
        c["allowed_statuses"] = []
        c["can_act"] = False
    return c


def _utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _limit_arg():
    try:
        return max(1, min(int(request.args.get("limit", 50)), 200))
    except ValueError:
        return 50


def _scope_arg():
    """?scope=open|closed|all (default all) -> open_only flag for db queries."""
    return {"open": True, "closed": False}.get(request.args.get("scope"))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "model_backend": classifier.backend_name(),
        "sections_loaded": len(db.get_sections_by_code(
            [r["code"] for r in _all_section_codes()]
        )),
    })


def _all_section_codes():
    conn = db.get_connection()
    rows = conn.execute("SELECT code FROM ipc_sections").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.route("/api/classify", methods=["POST"])
@role_required("citizen", *STAFF_ROLES)
def classify():
    payload = request.get_json(silent=True) or {}
    text = (payload.get("complaint_text") or "").strip()

    if not text:
        return jsonify({"error": "complaint_text is required"}), 400
    if len(text) < MIN_INPUT_CHARS:
        return jsonify({
            "error": f"complaint_text must be at least {MIN_INPUT_CHARS} characters"
        }), 400
    if len(text) > MAX_INPUT_CHARS:
        return jsonify({
            "error": f"complaint_text exceeds {MAX_INPUT_CHARS} characters"
        }), 400

    is_citizen = current_user["role"] == "citizen"
    station = (payload.get("station") or "").strip() or None
    if station and not db.station_exists(station):
        return jsonify({"error": "Unknown police station."}), 400
    if station is None and not is_citizen:
        station = current_user.get("station")

    try:
        result = process_complaint(
            text,
            filed_by=current_user["id"],
            source="citizen" if is_citizen else "officer",
            station=station,
        )
        if is_citizen:
            return jsonify(citizen_view(db.get_complaint(result["complaint_id"]))), 200
        return jsonify(result), 200
    except Exception:
        traceback.print_exc()
        return jsonify({"error": "Classification failed. Please try again."}), 500


@app.route("/api/complaints", methods=["GET"])
@role_required(*STAFF_ROLES)
def complaints():
    """
    Every complaint in the district, for any officer: this is the
    transparency view, and each record names the officer holding it.

    ?view=mine limits the list to the caller's own caseload.
    ?officer=<id>|unassigned, ?unit=, ?station= narrow it further, and
    ?scope=open|closed|all selects the stage.
    """
    filters = {"open_only": _scope_arg()}
    if request.args.get("view") == "mine":
        filters["assigned_to"] = current_user["id"]
    else:
        officer = request.args.get("officer")
        if officer == "unassigned":
            filters["unassigned"] = True
        elif officer:
            try:
                filters["assigned_to"] = int(officer)
            except ValueError:
                return jsonify({"error": "officer must be an id or 'unassigned'"}), 400
        filters["unit"] = request.args.get("unit") or None
        filters["station"] = request.args.get("station") or None

    rows = db.list_complaints(_limit_arg(), **filters)
    if not is_admin(current_user):
        for c in rows:
            if c["assignment"]["officer_id"] != current_user["id"]:
                c["complainant"] = _mask_contact(c["complainant"])
    return jsonify({"complaints": rows}), 200


@app.route("/api/complaints/<int:complaint_id>", methods=["GET"])
@role_required("citizen", *STAFF_ROLES)
def complaint_detail(complaint_id):
    c = db.get_complaint(complaint_id)
    if current_user["role"] == "citizen":
        if c is None or c["filed_by"] != current_user["id"]:
            return jsonify({"error": "Complaint not found"}), 404
        return jsonify(citizen_view(c)), 200
    if c is None:
        return jsonify({"error": "Case not found"}), 404
    return jsonify(staff_view(complaint_id, full=owns_case(current_user, c))), 200


@app.route("/api/complaints/<int:complaint_id>", methods=["PATCH"])
@role_required(*STAFF_ROLES)
def review_complaint(complaint_id):
    """
    Work a case: move it through the workflow, transfer it to another unit,
    confirm the informant's signature, or leave a note for the complainant.
    Administrators can also reassign it. The rules live in workflow.py;
    every change is written to the audit trail.
    """
    c = db.get_complaint(complaint_id)
    if c is None:
        return jsonify({"error": "Case not found"}), 404
    if not owns_case(current_user, c):
        return jsonify({
            "error": "This case is allocated to "
                     f"{c['assignment']['officer_name'] or 'no one yet'}. "
                     "Only the officer handling it, or an administrator, can act on it."
        }), 403

    payload = request.get_json(silent=True) or {}
    if "assigned_to" in payload and payload["assigned_to"] is not None:
        try:
            payload["assigned_to"] = int(payload["assigned_to"])
        except (TypeError, ValueError):
            return jsonify({"error": "Choose an active officer."}), 400

    try:
        changes, events, reallocate = workflow.plan_review(
            c, payload,
            is_admin=is_admin(current_user),
            known_units=db.list_units(routing_engine.DEFAULT_UNIT),
            officer_ids=db.active_officer_ids(),
            now=_utc_now(),
            actor_name=current_user["name"],
        )
    except workflow.ReviewError as err:
        return jsonify({"error": str(err)}), 400

    db.review_complaint(complaint_id, current_user["id"], changes, events)
    if reallocate:
        db.allocate(complaint_id, actor_id=current_user["id"])
    return jsonify(staff_view(complaint_id)), 200


@app.route("/api/complaints/<int:complaint_id>/diary", methods=["POST"])
@role_required(*STAFF_ROLES)
def add_diary_entry(complaint_id):
    """Case diary: the investigating officer's private, timestamped record."""
    c = db.get_complaint(complaint_id)
    if c is None:
        return jsonify({"error": "Case not found"}), 404
    if not owns_case(current_user, c):
        return jsonify({"error": "Only the officer handling this case can write in its diary."}), 403
    entry = ((request.get_json(silent=True) or {}).get("entry") or "").strip()
    if not entry:
        return jsonify({"error": "Write the diary entry first."}), 400
    if len(entry) > MAX_DIARY_CHARS:
        return jsonify({"error": f"Diary entries must be under {MAX_DIARY_CHARS} characters."}), 400
    db.add_diary_entry(complaint_id, current_user["id"], entry)
    return jsonify(staff_view(complaint_id)), 201


@app.route("/api/my/complaints", methods=["GET"])
@role_required("citizen")
def my_complaints():
    rows = db.list_complaints(_limit_arg(), filed_by=current_user["id"])
    rows.sort(key=lambda c: (c["received_at"], c["complaint_id"]), reverse=True)
    return jsonify({"complaints": [citizen_view(c) for c in rows]}), 200


@app.route("/api/stats", methods=["GET"])
@role_required(*STAFF_ROLES)
def stats():
    mine = None if is_admin(current_user) else current_user["id"]
    return jsonify(db.get_stats(assigned_to=mine)), 200


@app.route("/api/units", methods=["GET"])
@role_required(*STAFF_ROLES)
def units():
    return jsonify({"units": db.list_units(routing_engine.DEFAULT_UNIT)}), 200


@app.route("/api/sections", methods=["GET"])
@role_required(*STAFF_ROLES)
def sections():
    conn = db.get_connection()
    rows = conn.execute(
        "SELECT * FROM ipc_sections ORDER BY severity_weight DESC"
    ).fetchall()
    conn.close()
    return jsonify({"sections": [dict(r) for r in rows]}), 200


@app.route("/api/stations", methods=["GET"])
@role_required("citizen", *STAFF_ROLES)
def stations():
    return jsonify({"stations": db.list_stations()}), 200


# ---------------------------------------------------------------------------
# Signing a complaint
# ---------------------------------------------------------------------------
#
# BNSS s.173 takes electronically-given information on record once the
# informant signs it within three days. A complainant can do that in person,
# which an officer confirms, or digitally here: they re-enter a code sent to
# the mobile number on their account, and that declaration is recorded
# against the complaint. Production would use Aadhaar e-Sign or a DSC for a
# signature with statutory backing; the flow below is the same either way.

@app.route("/api/complaints/<int:complaint_id>/sign/request", methods=["POST"])
@role_required("citizen")
def request_signature_code(complaint_id):
    c = db.get_complaint(complaint_id)
    if c is None or c["filed_by"] != current_user["id"]:
        return jsonify({"error": "Complaint not found"}), 404
    if c["review"]["signature_confirmed_at"]:
        return jsonify({"error": "This complaint has already been signed."}), 409
    if c["status"] not in (workflow.NEW, workflow.UNDER_REVIEW):
        return jsonify({"error": "This complaint can no longer be signed here."}), 409

    channel = "sms" if current_user.get("phone") else "email"
    identifier = current_user.get("phone") or current_user.get("email")
    if not identifier:
        return jsonify({"error": "Add a mobile number to your account first."}), 400

    limited = auth.throttled(identifier, request.remote_addr or "unknown", kind="signature")
    if limited:
        return limited
    try:
        auth.issue_code(identifier, channel, purpose="signature")
    except Exception:
        traceback.print_exc()
        return jsonify({"error": "We could not send the code. Please try again."}), 502
    return jsonify({"message": "We sent a code to confirm your signature.", "channel": channel}), 200


@app.route("/api/complaints/<int:complaint_id>/sign", methods=["POST"])
@role_required("citizen")
def sign_complaint(complaint_id):
    c = db.get_complaint(complaint_id)
    if c is None or c["filed_by"] != current_user["id"]:
        return jsonify({"error": "Complaint not found"}), 404
    if c["review"]["signature_confirmed_at"]:
        return jsonify({"error": "This complaint has already been signed."}), 409

    payload = request.get_json(silent=True) or {}
    if payload.get("declaration") is not True:
        return jsonify({"error": "Confirm the declaration to sign."}), 400

    channel = "sms" if current_user.get("phone") else "email"
    identifier = current_user.get("phone") or current_user.get("email")
    code = re.sub(r"\s", "", str(payload.get("code") or ""))
    if not auth.check_code(identifier, channel, code):
        return jsonify({"error": "That code is incorrect or has expired."}), 400

    evidence = f"One-time code verified on {identifier} at {_utc_now()} UTC"
    db.review_complaint(
        complaint_id, current_user["id"],
        {"signature_confirmed_at": _utc_now(), "signature_method": "digital",
         "signature_evidence": evidence},
        [("signature_confirmed", f"Signed digitally by {current_user['name']}; {evidence}")],
    )
    return jsonify(citizen_view(db.get_complaint(complaint_id))), 200


# ---------------------------------------------------------------------------
# Officers
# ---------------------------------------------------------------------------

@app.route("/api/officers", methods=["GET"])
@role_required(*STAFF_ROLES)
def officers():
    """
    Who is available and what everyone is carrying. Any officer can see this:
    it is the basis on which cases are allocated, so it is not hidden.
    """
    metrics = db.officer_metrics()
    ranked = {o["id"]: o for o in workflow.rank_officers(
        [o for o in metrics if o["active"]], request.args.get("unit"), request.args.get("station")
    )}
    return jsonify({
        "officers": [
            {
                "id": o["id"],
                "name": o["name"],
                "username": o["username"],
                "unit": o["unit"],
                "station": o["station"],
                "availability": o["availability"],
                "active": bool(o["active"]),
                "open_cases": o["open_cases"],
                "weighted_load": round(float(o["weighted_load"]), 1),
                "capacity": o["capacity"],
                "load_percent": round(workflow.workload_ratio(o) * 100),
                "last_assigned_at": o["last_assigned_at"],
                # Only present when a unit is given: the allocation ranking.
                "allocation_score": ranked.get(o["id"], {}).get("score"),
            }
            for o in metrics
        ],
        "weights": workflow.PRIORITY_WEIGHT,
    }), 200


@app.route("/api/me/availability", methods=["PATCH"])
@role_required("officer")
def set_availability():
    """An officer marks themselves available, busy or on leave."""
    value = (request.get_json(silent=True) or {}).get("availability")
    if value not in ("available", "busy", "on_leave"):
        return jsonify({"error": "availability must be available, busy or on_leave."}), 400
    db.update_user(current_user["id"], availability=value)
    moved = 0
    if value == "on_leave":
        # Cases cannot sit with an officer who is away.
        moved = db.redistribute_cases(current_user["id"], actor_id=current_user["id"])
    else:
        db.allocate_unassigned(actor_id=current_user["id"])
    return jsonify({"user": auth.public_user(db.get_user(current_user["id"])), "cases_moved": moved}), 200


@app.errorhandler(404)
def not_found(_):
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(405)
def method_not_allowed(_):
    return jsonify({"error": "Method not allowed"}), 405


if __name__ == "__main__":
    print(f"Database at {db.DB_PATH}")
    print(f"Classifier backend: {classifier.backend_name()}")
    print(f"Accepting browser requests from: {', '.join(ALLOWED_ORIGINS)}")
    if not db.list_users(roles=("admin",)):
        print("No administrator account yet. Create one with: python create_admin.py")
    print("Listening on http://localhost:5000")
    # The debugger allows running code from the browser, so turn it off
    # (FLASK_DEBUG=0) anywhere other than your own machine.
    app.run(debug=os.environ.get("FLASK_DEBUG", "1") == "1", port=5000)
