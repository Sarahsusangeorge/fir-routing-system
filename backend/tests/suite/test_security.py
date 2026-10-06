"""
Security regression tests: authentication, sessions, authorization, input
handling and HTTP hardening. Each test states the secure behaviour; a failure
is a reproducible vulnerability.
"""

import datetime as dt

import jwt as pyjwt
import pytest

import app as appmod
import db
import workflow
from conftest import (
    ADMIN_PW, CITIZEN_PHONE, PW, TEXT_FRAUD, TEXT_SEXUAL, TEXT_THEFT,
    Client, clear_rate_limits, complaint_ids,
)

ACCESS_COOKIE = "access_token_cookie"


def access_cookie(cl):
    ck = cl.c.get_cookie(ACCESS_COOKIE, domain="localhost", path="/api/")
    return ck.value if ck else None


def replay(token):
    """A fresh client presenting a previously captured session token."""
    cl = Client()
    cl.c.set_cookie(ACCESS_COOKIE, token, domain="localhost", path="/api/")
    return cl


# ---------------------------------------------------------------------------
# Unauthenticated access
# ---------------------------------------------------------------------------

PROTECTED = [
    ("GET", "/api/complaints"), ("GET", "/api/complaints/1"), ("PATCH", "/api/complaints/1"),
    ("POST", "/api/complaints/1/diary"), ("POST", "/api/classify"), ("GET", "/api/my/complaints"),
    ("GET", "/api/officers"), ("PATCH", "/api/me/availability"), ("GET", "/api/stats"),
    ("GET", "/api/units"), ("GET", "/api/stations"), ("GET", "/api/sections"),
    ("GET", "/api/admin/users"), ("POST", "/api/admin/users"), ("PATCH", "/api/admin/users/2"),
    ("PUT", "/api/admin/users/9/phone"), ("GET", "/api/auth/me"),
    ("POST", "/api/complaints/12/sign/request"), ("POST", "/api/complaints/12/sign"),
    ("POST", "/api/auth/phone/change/request"), ("POST", "/api/auth/phone/change/verify"),
]


@pytest.mark.parametrize("method,path", PROTECTED)
def test_protected_endpoints_require_a_session(anon, method, path):
    r = anon.c.open(path, method=method, json={})
    assert r.status_code == 401
    assert r.get_json()["code"] == "AUTH_REQUIRED"


def test_forged_token_is_rejected(anon):
    forged = pyjwt.encode(
        {"sub": "1", "type": "access", "fresh": False, "csrf": "x",
         "iat": dt.datetime.now(dt.timezone.utc), "exp": dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)},
        "not-the-server-secret", algorithm="HS256",
    )
    assert replay(forged).get("/api/auth/me").status_code == 401


def test_unsigned_alg_none_token_is_rejected():
    token = pyjwt.encode({"sub": "1", "type": "access"}, key="", algorithm="none")
    assert replay(token).get("/api/auth/me").status_code == 401


def test_expired_token_is_rejected(staff):
    with appmod.app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(identity="2", expires_delta=dt.timedelta(seconds=-5))
    assert replay(token).get("/api/auth/me").status_code == 401


# ---------------------------------------------------------------------------
# Staff password sign-in
# ---------------------------------------------------------------------------

def test_wrong_username_and_wrong_password_look_identical(anon):
    a = anon.post("/api/auth/login", json={"username": "nobody.here", "password": "Whatever123"})
    b = anon.post("/api/auth/login", json={"username": "arjun.rao", "password": "Whatever123"})
    assert a.status_code == b.status_code == 401
    assert a.get_json() == b.get_json()


def test_login_lockout_after_repeated_failures(anon):
    for _ in range(5):
        anon.post("/api/auth/login", json={"username": "arjun.rao", "password": "Wrong-Pass-1"})
    r = anon.post("/api/auth/login", json={"username": "arjun.rao", "password": PW})
    assert r.status_code == 429


def test_citizen_cannot_use_password_route(anon):
    r = anon.post("/api/auth/login", json={"username": CITIZEN_PHONE, "password": "anything"})
    assert r.status_code == 401


def test_passwords_are_hashed():
    conn = db.get_connection()
    rows = conn.execute("SELECT password_hash FROM users WHERE password_hash IS NOT NULL").fetchall()
    conn.close()
    assert rows and all(PW not in r[0] and ADMIN_PW not in r[0] for r in rows)
    assert all(r[0].startswith(("scrypt:", "pbkdf2:")) for r in rows)


def test_login_rejects_non_json_body_against_login_csrf(anon):
    r = anon.c.post("/api/auth/login", data="username=arjun.rao&password=" + PW,
                    content_type="application/x-www-form-urlencoded")
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# One-time codes
# ---------------------------------------------------------------------------

def _request(cl, phone):
    return cl.post("/api/auth/otp/request", json={"channel": "sms", "identifier": phone})


def test_otp_is_stored_only_as_a_hash(anon, otp_box):
    _request(anon, "9876500001")
    code = otp_box["+919876500001"]
    conn = db.get_connection()
    row = conn.execute("SELECT code_hash FROM login_codes WHERE identifier = '+919876500001'").fetchone()
    conn.close()
    assert code not in row["code_hash"]


def test_otp_is_single_use(anon, otp_box):
    _request(anon, "9876500002")
    code = otp_box["+919876500002"]
    body = {"channel": "sms", "identifier": "+919876500002", "code": code, "name": "Synthetic User"}
    assert anon.post("/api/auth/otp/verify", json=body).status_code == 200
    assert Client().post("/api/auth/otp/verify", json=body).status_code == 400


def test_otp_locks_after_five_wrong_attempts(anon, otp_box):
    _request(anon, "9876500003")
    code = otp_box["+919876500003"]
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        anon.post("/api/auth/otp/verify", json={"channel": "sms", "identifier": "+919876500003", "code": wrong})
    r = anon.post("/api/auth/otp/verify",
                  json={"channel": "sms", "identifier": "+919876500003", "code": code, "name": "Synthetic User"})
    assert r.status_code == 400


def test_expired_otp_is_rejected(anon, otp_box):
    _request(anon, "9876500004")
    conn = db.get_connection()
    conn.execute("UPDATE login_codes SET expires_at = datetime('now', '-1 minute')")
    conn.commit()
    conn.close()
    r = anon.post("/api/auth/otp/verify", json={"channel": "sms", "identifier": "+919876500004",
                                                "code": otp_box["+919876500004"], "name": "Synthetic User"})
    assert r.status_code == 400


def test_otp_resend_is_rate_limited(anon, otp_box):
    assert _request(anon, "9876500005").status_code == 200
    assert _request(anon, "9876500005").status_code == 429


def test_staff_address_never_receives_a_sign_in_code(anon, otp_box):
    r = anon.post("/api/auth/otp/request", json={"channel": "email", "identifier": "admin@nivara.test"})
    assert r.status_code == 200
    assert "admin@nivara.test" not in otp_box


def test_otp_verification_failures_are_capped_across_codes(anon, otp_box):
    """Requesting fresh codes must not give an attacker unlimited guesses at one number."""
    phone = "+919876500006"
    for _ in range(4):
        clear_rate_limits_for_requests()
        _request(anon, phone)
        for _ in range(5):
            anon.post("/api/auth/otp/verify", json={"channel": "sms", "identifier": phone, "code": "000000"})
    clear_rate_limits_for_requests()
    _request(anon, phone)
    r = anon.post("/api/auth/otp/verify",
                  json={"channel": "sms", "identifier": phone, "code": otp_box[phone], "name": "Synthetic User"})
    assert r.status_code in (400, 429), "a correct code after 20 failed guesses should still be refused"


def clear_rate_limits_for_requests():
    conn = db.get_connection()
    conn.execute("DELETE FROM auth_attempts WHERE kind IN ('code_request', 'code_request_ip')")
    conn.commit()
    conn.close()


def test_sign_in_code_cannot_be_used_to_sign_a_complaint(citizen, otp_box):
    """A code is bound to its purpose: a sign-in code is not a signature."""
    target = complaint_ids(filed_by=citizen.user["id"])[-1]
    conn = db.get_connection()
    conn.execute("UPDATE complaints SET status = 'New', signature_confirmed_at = NULL, "
                 "received_at = datetime('now') WHERE id = ?", (target,))
    conn.commit()
    conn.close()
    clear_rate_limits()
    _request(Client(), CITIZEN_PHONE)
    sign_in_code = otp_box[CITIZEN_PHONE]
    r = citizen.post(f"/api/complaints/{target}/sign", json={"code": sign_in_code, "declaration": True})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

def test_logout_revokes_the_session_token(staff):
    officer = staff("arjun.rao")
    token = access_cookie(officer)
    assert officer.post("/api/auth/logout").status_code == 200
    assert replay(token).get("/api/auth/me").status_code == 401


def test_password_reset_revokes_existing_sessions(staff, admin):
    officer = staff("arjun.rao")
    token = access_cookie(officer)
    r = admin.patch(f"/api/admin/users/{officer.user['id']}", json={"password": "Fresh-Pass-2026"})
    assert r.status_code == 200
    assert replay(token).get("/api/auth/me").status_code == 401


def test_admin_phone_recovery_revokes_existing_sessions(citizen, admin):
    token = access_cookie(citizen)
    r = admin.put(f"/api/admin/users/{citizen.user['id']}/phone",
                  json={"phone": "9811100000", "reason": "Aadhaar checked at PS-CENTRAL counter"})
    assert r.status_code == 200
    assert replay(token).get("/api/auth/me").status_code == 401


def test_deactivated_officer_loses_access_immediately(staff, admin):
    officer = staff("meena.pillai")
    admin.patch(f"/api/admin/users/{officer.user['id']}", json={"active": False})
    assert officer.get("/api/complaints").status_code == 401


def test_session_has_an_absolute_lifetime(staff, monkeypatch):
    """Sliding renewal must not keep one sign-in alive forever."""
    import auth
    officer = staff("arjun.rao")
    real_now = auth._now
    monkeypatch.setattr(auth, "_now", lambda: real_now() + dt.timedelta(hours=13))
    assert officer.get("/api/auth/me").status_code == 401


def test_state_changing_request_without_csrf_header_is_refused(staff):
    officer = staff("arjun.rao")
    r = officer.c.patch("/api/me/availability", json={"availability": "busy"})
    assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Authorization and object-level access
# ---------------------------------------------------------------------------

def test_citizen_cannot_read_another_citizens_complaint(citizen, citizen_login):
    other = citizen_login("9876500010", "Other Synthetic Citizen")
    mine = complaint_ids(filed_by=citizen.user["id"])[0]
    assert other.get(f"/api/complaints/{mine}").status_code == 404
    assert other.post(f"/api/complaints/{mine}/sign/request").status_code == 404
    listed = other.get("/api/my/complaints").get_json()["complaints"]
    assert mine not in [c["complaint_id"] for c in listed]


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/complaints"), ("GET", "/api/officers"), ("GET", "/api/stats"),
    ("GET", "/api/admin/users"), ("PATCH", "/api/complaints/1"), ("GET", "/api/sections"),
])
def test_citizen_cannot_use_staff_endpoints(citizen, method, path):
    r = citizen.c.open(path, method=method, json={}, headers={"X-CSRF-TOKEN": citizen.csrf})
    assert r.status_code == 403


def test_citizen_never_sees_model_predictions(citizen):
    r = citizen.post("/api/classify", json={"complaint_text": TEXT_THEFT})
    body = r.get_json()
    assert r.status_code == 200
    for key in ("sections", "priority", "routing", "explanation", "model_backend"):
        assert key not in body


def test_officer_cannot_act_on_a_case_allocated_to_someone_else(staff):
    farhan = staff("farhan.ali")
    case = next(c for c in farhan.get("/api/complaints").get_json()["complaints"]
                if c["assignment"]["officer_id"] not in (None, farhan.user["id"]))
    cid = case["complaint_id"]
    assert farhan.patch(f"/api/complaints/{cid}", json={"note": "x"}).status_code == 403
    assert farhan.post(f"/api/complaints/{cid}/diary", json={"entry": "x"}).status_code == 403


def test_officer_cannot_reassign_even_their_own_case(staff):
    arjun = staff("arjun.rao")
    mine = arjun.get("/api/complaints?view=mine").get_json()["complaints"][0]["complaint_id"]
    r = arjun.patch(f"/api/complaints/{mine}", json={"assigned_to": 3})
    assert r.status_code == 400
    assert db.get_complaint(mine)["assignment"]["officer_id"] == arjun.user["id"]


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/admin/users"), ("POST", "/api/admin/users"),
    ("PATCH", "/api/admin/users/3"), ("PUT", "/api/admin/users/9/phone"),
])
def test_officer_cannot_use_admin_endpoints(staff, method, path):
    officer = staff("kavya.nair")
    r = officer.c.open(path, method=method, json={"active": False}, headers={"X-CSRF-TOKEN": officer.csrf})
    assert r.status_code == 403


def test_read_only_view_masks_contact_and_hides_diary(staff):
    farhan = staff("farhan.ali")
    case = next(c for c in farhan.get("/api/complaints").get_json()["complaints"]
                if c["source"] == "citizen" and c["assignment"]["officer_id"] != farhan.user["id"])
    view = farhan.get(f"/api/complaints/{case['complaint_id']}").get_json()
    assert view["can_act"] is False
    assert view["complainant"]["masked"] is True
    assert "+91900000" not in str(view["complainant"])
    assert all(e["action"] != "diary_entry" for e in view["events"])


def test_sexual_offence_narrative_is_not_disclosed_outside_the_handling_unit(citizen, staff):
    """The identity and account of a sexual-offence victim must not be readable by every officer."""
    filed = citizen.post("/api/classify", json={"complaint_text": TEXT_SEXUAL}).get_json()
    cid = filed["complaint_id"]
    assert db.get_complaint(cid)["routing"]["unit"] == "Women & Child Protection Unit"
    outsider = staff("nikhil.das")
    detail = outsider.get(f"/api/complaints/{cid}").get_json()
    listed = next(c for c in outsider.get("/api/complaints").get_json()["complaints"] if c["complaint_id"] == cid)
    for view in (detail, listed):
        assert "sexually assaulted" not in view["complaint_text"]
        assert view["complainant"] is None or view["complainant"]["name"] != citizen.user["name"]


def test_admin_cannot_change_a_role_through_staff_update(admin):
    r = admin.patch("/api/admin/users/3", json={"role": "admin", "capacity": 9})
    assert r.status_code == 200
    assert db.get_user(3)["role"] == "officer"


def test_client_cannot_choose_priority_routing_or_owner(citizen):
    r = citizen.post("/api/classify", json={
        "complaint_text": TEXT_THEFT, "priority": {"level": "High", "score": 10},
        "routing": {"unit": "Crime Branch"}, "assigned_to": 1, "filed_by": 1, "status": "Registered",
    })
    cid = r.get_json()["complaint_id"]
    stored = db.get_complaint(cid)
    assert stored["filed_by"] == citizen.user["id"]
    assert stored["status"] == workflow.NEW
    assert stored["routing"]["unit"] != "Crime Branch"
    assert stored["priority"]["level"] != "High"


# ---------------------------------------------------------------------------
# Input handling
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("payload", ["' OR 1=1 --", "x'; DROP TABLE complaints; --", '") OR ("1"="1'])
def test_query_filters_are_not_injectable(staff, payload):
    officer = staff("kavya.nair")
    for param in ("unit", "station"):
        r = officer.get("/api/complaints", query_string={param: payload})
        assert r.status_code == 200 and r.get_json()["complaints"] == []
    assert len(complaint_ids()) >= 15


@pytest.mark.parametrize("body", ["[1, 2]", '"just a string"', "42", "null"])
@pytest.mark.parametrize("path", ["/api/classify", "/api/auth/login", "/api/auth/otp/request"])
def test_non_object_json_is_a_client_error(staff, body, path):
    officer = staff("kavya.nair")
    r = officer.c.post(path, data=body, content_type="application/json",
                       headers={"X-CSRF-TOKEN": officer.csrf})
    assert r.status_code == 400


@pytest.mark.parametrize("value", [12345, {"a": 1}, ["x"], True])
def test_wrongly_typed_fields_are_a_client_error(citizen, value):
    assert citizen.post("/api/classify", json={"complaint_text": value}).status_code == 400


def test_malformed_json_is_a_client_error(citizen):
    r = citizen.c.post("/api/classify", data="{not json", content_type="application/json",
                       headers={"X-CSRF-TOKEN": citizen.csrf})
    assert r.status_code == 400


def test_oversized_request_body_is_refused(citizen):
    r = citizen.post("/api/classify", json={"complaint_text": "a" * 2_000_000})
    assert r.status_code == 413


def test_complaint_length_bounds(citizen):
    assert citizen.post("/api/classify", json={"complaint_text": "short"}).status_code == 400
    assert citizen.post("/api/classify", json={"complaint_text": "   "}).status_code == 400
    assert citizen.post("/api/classify", json={"complaint_text": "b" * 20001}).status_code == 400


def test_unicode_and_control_characters_are_handled(citizen):
    text = "शिकायत: my phone was stolen 📱 near the market ‮\u0000 yesterday evening."
    r = citizen.post("/api/classify", json={"complaint_text": text})
    assert r.status_code == 200


def test_unknown_route_and_method_return_json(staff):
    officer = staff("kavya.nair")
    assert officer.get("/api/does-not-exist").get_json()["error"]
    r = officer.c.delete("/api/complaints/1", headers={"X-CSRF-TOKEN": officer.csrf})
    assert r.status_code == 405 and r.get_json()["error"]


def test_unexpected_server_error_hides_internals(staff, monkeypatch):
    officer = staff("kavya.nair")
    appmod.app.config["PROPAGATE_EXCEPTIONS"] = False
    appmod.app.config["TESTING"] = False

    def boom(*a, **k):
        raise RuntimeError("secret internal detail /etc/passwd")

    monkeypatch.setattr(db, "get_stats", boom)
    try:
        r = officer.get("/api/stats")
    finally:
        appmod.app.config["TESTING"] = True
        appmod.app.config["PROPAGATE_EXCEPTIONS"] = None
    assert r.status_code == 500
    assert r.is_json and "secret internal detail" not in r.get_data(as_text=True)


def test_cors_does_not_trust_arbitrary_origins(anon):
    r = anon.c.get("/api/health", headers={"Origin": "https://evil.example"})
    assert r.headers.get("Access-Control-Allow-Origin") is None


# ---------------------------------------------------------------------------
# HTTP hardening
# ---------------------------------------------------------------------------

def test_security_headers_are_set(anon):
    h = anon.get("/api/health").headers
    assert h.get("X-Content-Type-Options") == "nosniff"
    assert h.get("X-Frame-Options") == "DENY" or "frame-ancestors 'none'" in h.get("Content-Security-Policy", "")
    assert h.get("Referrer-Policy") == "no-referrer"
    assert "default-src 'none'" in h.get("Content-Security-Policy", "")


def test_personal_data_responses_are_not_cached(staff):
    r = staff("kavya.nair").get("/api/complaints")
    assert "no-store" in r.headers.get("Cache-Control", "")


def test_session_cookie_is_httponly_and_samesite(anon):
    r = anon.post("/api/auth/login", json={"username": "arjun.rao", "password": PW})
    cookies = [v for k, v in r.headers.items() if k == "Set-Cookie" and v.startswith(ACCESS_COOKIE)]
    assert cookies and "HttpOnly" in cookies[0] and "SameSite=Lax" in cookies[0]


# ---------------------------------------------------------------------------
# Enumeration and abuse
# ---------------------------------------------------------------------------

def test_number_change_does_not_reveal_registered_numbers(citizen, citizen_login):
    citizen_login("9876500020", "Registered Synthetic Citizen")
    clear_rate_limits()
    taken = citizen.post("/api/auth/phone/change/request", json={"phone": "9876500020"})
    clear_rate_limits()
    free = citizen.post("/api/auth/phone/change/request", json={"phone": "9876500021"})
    assert taken.status_code == free.status_code
    assert taken.get_json()["message"] == free.get_json()["message"]


def test_citizen_complaint_submissions_are_rate_limited(citizen):
    statuses = [
        citizen.post("/api/classify", json={"complaint_text": f"{TEXT_THEFT} Incident reference {i}."}).status_code
        for i in range(12)
    ]
    assert 429 in statuses


def test_accidental_double_submission_creates_one_complaint(citizen):
    before = len(complaint_ids(filed_by=citizen.user["id"]))
    a = citizen.post("/api/classify", json={"complaint_text": TEXT_FRAUD})
    b = citizen.post("/api/classify", json={"complaint_text": TEXT_FRAUD})
    assert a.status_code == 200 and b.status_code == 200
    assert a.get_json()["complaint_id"] == b.get_json()["complaint_id"]
    assert len(complaint_ids(filed_by=citizen.user["id"])) == before + 1
