"""
Regression tests for controls added during the audit: production guards,
restricted-case access, decision provenance, and behaviour under real
concurrency.
"""

import re
import threading

import pytest

import app as appmod
import auth
import classifier
import db
from conftest import TEXT_SEXUAL, TEXT_THEFT, Client


# ---------------------------------------------------------------------------
# Production configuration
# ---------------------------------------------------------------------------

def test_production_refuses_demo_credentials_and_unsafe_settings(monkeypatch):
    monkeypatch.setenv("NIVARA_JWT_SECRET", "short")
    monkeypatch.delenv("NIVARA_COOKIE_SECURE", raising=False)
    monkeypatch.setenv("SMS_PROVIDER", "console")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.setenv("FIR_DEBUG", "1")
    problems = " ".join(appmod.production_problems())
    for expected in ("NIVARA_JWT_SECRET", "NIVARA_COOKIE_SECURE", "sign-in codes", "debugger", "'admin'"):
        assert expected in problems


def test_production_configuration_with_everything_set_has_no_problems(monkeypatch):
    monkeypatch.setenv("NIVARA_JWT_SECRET", "s" * 48)
    monkeypatch.setenv("NIVARA_COOKIE_SECURE", "1")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.delenv("FIR_DEBUG", raising=False)
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    conn = db.get_connection()
    conn.execute("UPDATE users SET active = 0 WHERE username IN ('admin', 'kavya.nair')")
    conn.commit()
    conn.close()
    assert appmod.production_problems() == []


def test_production_never_prints_codes(anon, monkeypatch, capsys):
    monkeypatch.setenv("NIVARA_ENV", "production")
    r = anon.post("/api/auth/otp/request", json={"channel": "sms", "identifier": "9876500030"})
    assert r.status_code == 502
    assert not re.search(r"\b\d{6}\b", capsys.readouterr().out)


def test_production_requires_an_explicit_jwt_secret(monkeypatch):
    monkeypatch.setenv("NIVARA_ENV", "production")
    monkeypatch.delenv("NIVARA_JWT_SECRET", raising=False)
    with pytest.raises(RuntimeError):
        auth._load_secret()


def test_revoked_session_gets_a_clear_message(staff):
    officer = staff("arjun.rao")
    ck = officer.c.get_cookie("access_token_cookie", domain="localhost", path="/api/").value
    officer.post("/api/auth/logout")
    cl = Client()
    cl.c.set_cookie("access_token_cookie", ck, domain="localhost", path="/api/")
    r = cl.get("/api/auth/me")
    assert r.status_code == 401 and r.get_json()["code"] == "AUTH_REQUIRED"


def test_responses_are_json_for_client_errors(citizen):
    r = citizen.post("/api/classify", json={"complaint_text": ["not", "text"]})
    assert r.status_code == 400 and r.get_json()["error"] == "complaint_text must be text."
    r = citizen.post("/api/classify", json={"complaint_text": "z" * 400_000})
    assert r.status_code == 413 and r.get_json()["error"]


# ---------------------------------------------------------------------------
# Restricted cases
# ---------------------------------------------------------------------------

@pytest.fixture
def sexual_offence_case(citizen):
    r = citizen.post("/api/classify", json={"complaint_text": TEXT_SEXUAL})
    return r.get_json()["complaint_id"], citizen


@pytest.mark.parametrize("username", ["lakshmi.iyer"])
def test_handling_unit_can_read_restricted_case(staff, sexual_offence_case, username):
    cid, cit = sexual_offence_case
    view = staff(username).get(f"/api/complaints/{cid}").get_json()
    assert "sexually assaulted" in view["complaint_text"]
    assert not view.get("restricted")


def test_admin_can_read_restricted_case(admin, sexual_offence_case):
    cid, _ = sexual_offence_case
    assert "sexually assaulted" in admin.get(f"/api/complaints/{cid}").get_json()["complaint_text"]


def test_redacted_view_still_shows_who_holds_the_case(staff, sexual_offence_case):
    cid, _ = sexual_offence_case
    view = staff("farhan.ali").get(f"/api/complaints/{cid}").get_json()
    assert view["restricted"] is True
    assert view["assignment"]["officer_name"] and view["routing"]["unit"] == "Women & Child Protection Unit"
    assert view["explanation"] == [] and view["complainant"] is None


def test_redacted_audit_trail_does_not_name_the_complainant(staff, sexual_offence_case):
    """Found in the live UI walkthrough: the 'Filed' event named the victim as its actor."""
    cid, cit = sexual_offence_case
    view = staff("farhan.ali").get(f"/api/complaints/{cid}").get_json()
    assert cit.user["name"] not in str(view)
    assert any(e["actor"] == "Complainant" for e in view["events"])


# ---------------------------------------------------------------------------
# Decision provenance and review flags
# ---------------------------------------------------------------------------

def test_backend_and_flags_are_stored_with_the_case(staff):
    officer = staff("kavya.nair")
    r = officer.post("/api/classify", json={"complaint_text": "My neighbour set fire to my house while we slept inside."})
    body = r.get_json()
    assert body["priority"]["review_required"] is True
    stored = db.get_complaint(body["complaint_id"])
    assert stored["model_backend"] == "keyword-stub"
    assert stored["priority"]["review_required"] is True and stored["priority"]["review_reasons"]


def test_health_reports_a_failed_model(anon, monkeypatch):
    monkeypatch.setattr(classifier, "USE_MODEL", True)
    monkeypatch.setattr(classifier, "_predict_model", lambda t: (_ for _ in ()).throw(OSError("missing")))
    monkeypatch.setattr(classifier, "_model_failed", False)
    classifier.predict("The accused cheated me of money.")
    assert anon.get("/api/health").get_json()["model_backend"] == classifier.FALLBACK_NAME


# ---------------------------------------------------------------------------
# Real concurrency (threads against the Flask app and the SQLite file)
# ---------------------------------------------------------------------------

def test_concurrent_filings_balance_and_do_not_double_allocate(staff):
    conn = db.get_connection()
    conn.execute("UPDATE users SET active = 0 WHERE role = 'officer' AND username NOT IN ('arjun.rao', 'meena.pillai')")
    conn.execute("UPDATE users SET station = 'PS-CENTRAL', capacity = 50 WHERE username IN ('arjun.rao', 'meena.pillai')")
    conn.execute("UPDATE complaints SET status = 'Closed'")
    conn.commit()
    conn.close()
    filer = staff("arjun.rao")
    barrier = threading.Barrier(12)
    results, errors = [], []

    def file(i):
        cl = Client()
        cl.c.set_cookie("access_token_cookie",
                        filer.c.get_cookie("access_token_cookie", domain="localhost", path="/api/").value,
                        domain="localhost", path="/api/")
        cl.csrf = filer.csrf
        barrier.wait()
        try:
            r = cl.post("/api/classify", json={"complaint_text": f"{TEXT_THEFT} Concurrent report number {i}."})
            results.append(r.get_json()["assignment"]["officer_id"] if r.status_code == 200 else r.status_code)
        except Exception as e:  # noqa: BLE001
            errors.append(repr(e))

    threads = [threading.Thread(target=file, args=(i,)) for i in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors and len(results) == 12 and all(isinstance(x, int) for x in results), (errors, results)
    counts = sorted(results.count(x) for x in set(results))
    assert counts == [6, 6], counts


def test_concurrent_status_changes_keep_a_consistent_audit_chain(staff, admin):
    officer = staff("arjun.rao")
    cid = officer.post("/api/classify", json={"complaint_text": f"{TEXT_THEFT} Chain test."}).get_json()["complaint_id"]
    conn = db.get_connection()
    conn.execute("UPDATE complaints SET assigned_to = ? WHERE id = ?", (officer.user["id"], cid))
    conn.commit()
    conn.close()
    barrier = threading.Barrier(2)
    codes = []

    def act(cl, body):
        barrier.wait()
        codes.append(cl.patch(f"/api/complaints/{cid}", json=body).status_code)

    t1 = threading.Thread(target=act, args=(officer, {"status": "Registered"}))
    t2 = threading.Thread(target=act, args=(admin, {"status": "Not Registered", "note": "Civil matter."}))
    t1.start(); t2.start(); t1.join(); t2.join()
    assert 200 in codes
    chain = [e["detail"] for e in db.list_events(cid) if e["action"] == "status_changed"]
    state = "New"
    for step in chain:
        before, after = step.split(" -> ")
        assert before == state, chain
        state = after
    assert state == db.get_complaint(cid)["status"]
