"""
Case lifecycle, transfers, allocation side effects and audit trail,
exercised through the HTTP API.
"""

import itertools

import pytest

import app as appmod
import db
import workflow
from conftest import TEXT_THEFT, complaint_ids

ALL = workflow.STATUSES

# Derived from the implementation (workflow.TRANSITIONS) and checked against
# the README lifecycle: New -> Under Review -> Registered / Not Registered,
# then Under Investigation -> Charge Sheet Filed / Closed.
EXPECTED_OFFICER_TRANSITIONS = {
    "New": {"Under Review", "Registered", "Not Registered"},
    "Under Review": {"Registered", "Not Registered"},
    "Registered": {"Under Investigation", "Closed"},
    "Under Investigation": {"Charge Sheet Filed", "Closed"},
    "Not Registered": set(),
    "Charge Sheet Filed": set(),
    "Closed": set(),
}


def test_transition_table_matches_the_documented_lifecycle():
    assert {k: set(v) for k, v in workflow.TRANSITIONS.items()} == EXPECTED_OFFICER_TRANSITIONS


def officer_case(staff, username="arjun.rao"):
    """A fresh officer-filed case allocated to `username`, for transition tests."""
    o = staff(username)
    r = o.post("/api/classify", json={"complaint_text": TEXT_THEFT})
    cid = r.get_json()["complaint_id"]
    conn = db.get_connection()
    conn.execute("UPDATE complaints SET assigned_to = ? WHERE id = ?", (o.user["id"], cid))
    conn.commit()
    conn.close()
    return o, cid


def set_status(cid, status):
    conn = db.get_connection()
    conn.execute("UPDATE complaints SET status = ? WHERE id = ?", (status, cid))
    conn.commit()
    conn.close()


@pytest.mark.parametrize("current,target", [p for p in itertools.product(ALL, ALL) if p[0] != p[1]])
def test_officer_transitions(staff, current, target):
    o, cid = officer_case(staff)
    set_status(cid, current)
    r = o.patch(f"/api/complaints/{cid}", json={"status": target, "note": "Outcome explained to complainant."})
    stored = db.get_complaint(cid)["status"]
    if target in EXPECTED_OFFICER_TRANSITIONS[current]:
        assert r.status_code == 200, r.get_json()
        assert stored == target
    else:
        assert r.status_code == 400, r.get_json()
        assert stored == current


def test_admin_can_reopen_a_closed_case(staff, admin):
    o, cid = officer_case(staff)
    set_status(cid, "Closed")
    assert admin.patch(f"/api/complaints/{cid}", json={"status": "Under Investigation"}).status_code == 200


def test_repeating_the_current_status_changes_nothing(staff):
    o, cid = officer_case(staff)
    before = len(db.list_events(cid))
    assert o.patch(f"/api/complaints/{cid}", json={"status": "New"}).status_code == 400
    assert len(db.list_events(cid)) == before


def test_unknown_status_is_rejected(staff):
    o, cid = officer_case(staff)
    assert o.patch(f"/api/complaints/{cid}", json={"status": "Solved"}).status_code == 400


def test_closing_requires_a_note(staff):
    o, cid = officer_case(staff)
    set_status(cid, "Registered")
    assert o.patch(f"/api/complaints/{cid}", json={"status": "Closed"}).status_code == 400


def test_citizen_complaint_needs_a_signature_before_registration(citizen, admin):
    cid = citizen.post("/api/classify", json={"complaint_text": TEXT_THEFT}).get_json()["complaint_id"]
    r = admin.patch(f"/api/complaints/{cid}", json={"status": "Registered"})
    assert r.status_code == 400
    r = admin.patch(f"/api/complaints/{cid}", json={"status": "Registered", "signature_confirmed": True})
    assert r.status_code == 200 and r.get_json()["review"]["signature_method"] == "in_person"


def test_every_change_is_audited_with_its_actor(staff):
    o, cid = officer_case(staff)
    o.patch(f"/api/complaints/{cid}", json={"status": "Registered"})
    o.post(f"/api/complaints/{cid}/diary", json={"entry": "Visited the library; CCTV requested."})
    events = db.list_events(cid)
    actions = [e["action"] for e in events]
    assert "status_changed" in actions and "diary_entry" in actions
    assert all(e["actor"] == o.user["name"] for e in events if e["action"] in ("status_changed", "diary_entry"))


def test_transfer_requires_a_reason_and_a_known_unit(staff):
    o, cid = officer_case(staff)
    assert o.patch(f"/api/complaints/{cid}", json={"unit": "Cyber Cell"}).status_code == 400
    assert o.patch(f"/api/complaints/{cid}", json={"unit": "Ministry of Magic", "override_reason": "x"}).status_code == 400
    r = o.patch(f"/api/complaints/{cid}", json={"unit": "Cyber Cell", "override_reason": "Theft was of a phone used for UPI fraud."})
    assert r.status_code == 200
    c = db.get_complaint(cid)
    assert c["routing"]["unit"] == "Cyber Cell" and c["review"]["original_unit"] == "Local Police Station"
    assert c["assignment"]["officer_id"] != o.user["id"]


def test_leave_moves_open_cases_and_return_picks_up_the_queue(staff):
    meena = staff("meena.pillai")
    held = db.open_case_ids(assigned_to=meena.user["id"])
    assert held
    r = meena.patch("/api/me/availability", json={"availability": "on_leave"})
    assert r.status_code == 200 and r.get_json()["cases_moved"] == len(held)
    assert db.open_case_ids(assigned_to=meena.user["id"]) == []


def test_case_with_no_eligible_officer_waits_and_is_picked_up_later(admin):
    conn = db.get_connection()
    conn.execute("UPDATE users SET active = 0 WHERE role = 'officer'")
    conn.commit()
    conn.close()
    r = admin.post("/api/classify", json={"complaint_text": TEXT_THEFT})
    cid = r.get_json()["complaint_id"]
    assert db.get_complaint(cid)["assignment"]["officer_id"] is None
    r = admin.patch("/api/admin/users/3", json={"active": True})
    assert r.status_code == 200
    assert db.get_complaint(cid)["assignment"]["officer_id"] == 3


def test_stale_update_cannot_overwrite_a_newer_status(staff, admin, monkeypatch):
    """Two people act on the same case at once: the second, working from stale data, must be refused."""
    o, cid = officer_case(staff)
    stale = db.get_complaint(cid)
    assert admin.patch(f"/api/complaints/{cid}",
                       json={"status": "Not Registered", "note": "Civil dispute; advised to approach court."}).status_code == 200
    real_get = db.get_complaint
    calls = {"n": 0}

    def first_call_stale(complaint_id):
        calls["n"] += 1
        return stale if calls["n"] == 1 and complaint_id == cid else real_get(complaint_id)

    monkeypatch.setattr(appmod.db, "get_complaint", first_call_stale)
    r = o.patch(f"/api/complaints/{cid}", json={"status": "Registered"})
    monkeypatch.undo()
    assert r.status_code == 409
    assert db.get_complaint(cid)["status"] == "Not Registered"


def test_digital_signature_is_refused_after_the_three_day_window(citizen, otp_box):
    cid = complaint_ids(filed_by=citizen.user["id"])[-1]
    conn = db.get_connection()
    conn.execute("UPDATE complaints SET status = 'New', signature_confirmed_at = NULL, "
                 "received_at = datetime('now', '-4 days') WHERE id = ?", (cid,))
    conn.commit()
    conn.close()
    assert citizen.post(f"/api/complaints/{cid}/sign/request").status_code == 409


def test_closed_complaint_cannot_be_signed_online(citizen, otp_box):
    cid = complaint_ids(filed_by=citizen.user["id"])[-1]
    conn = db.get_connection()
    conn.execute("UPDATE complaints SET status = 'New', signature_confirmed_at = NULL, "
                 "received_at = datetime('now') WHERE id = ?", (cid,))
    conn.commit()
    conn.close()
    assert citizen.post(f"/api/complaints/{cid}/sign/request").status_code == 200
    code = otp_box[citizen.user["phone"]]
    set_status(cid, "Not Registered")
    r = citizen.post(f"/api/complaints/{cid}/sign", json={"code": code, "declaration": True})
    assert r.status_code == 409
    assert db.get_complaint(cid)["review"]["signature_confirmed_at"] is None


def test_signing_does_not_count_as_an_officer_review(citizen, otp_box):
    """Found in the live walkthrough: signing set reviewed_by to the citizen."""
    cid = citizen.post("/api/classify", json={"complaint_text": f"{TEXT_THEFT} Signature review test."}).get_json()["complaint_id"]
    assert citizen.post(f"/api/complaints/{cid}/sign/request").status_code == 200
    r = citizen.post(f"/api/complaints/{cid}/sign", json={"code": otp_box[citizen.user["phone"]], "declaration": True})
    assert r.status_code == 200
    assert r.get_json()["unit"] is None and r.get_json()["officer"] is None
    review = db.get_complaint(cid)["review"]
    assert review["reviewed_by"] is None and review["reviewed_at"] is None
    assert review["signature_method"] == "digital"


def test_online_signature_happy_path(citizen, otp_box):
    cid = complaint_ids(filed_by=citizen.user["id"])[-1]
    conn = db.get_connection()
    conn.execute("UPDATE complaints SET status = 'New', signature_confirmed_at = NULL, "
                 "received_at = datetime('now') WHERE id = ?", (cid,))
    conn.commit()
    conn.close()
    assert citizen.post(f"/api/complaints/{cid}/sign/request").status_code == 200
    code = otp_box[citizen.user["phone"]]
    r = citizen.post(f"/api/complaints/{cid}/sign", json={"code": code, "declaration": True})
    assert r.status_code == 200 and r.get_json()["signature_method"] == "digital"


def test_allocation_failure_does_not_report_a_filed_complaint_as_failed(citizen, monkeypatch):
    """
    The complaint is committed before allocation. If allocation then fails,
    the citizen must be told it was received (it was), not "failed, try again",
    which used to leave an orphaned case and invite a duplicate.
    """
    before = complaint_ids()

    def fail(*a, **k):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(db, "allocate", fail)
    r = citizen.post("/api/classify", json={"complaint_text": TEXT_THEFT})
    monkeypatch.undo()
    assert r.status_code == 200
    new = [i for i in complaint_ids() if i not in before]
    assert len(new) == 1 and r.get_json()["complaint_id"] == new[0]
    assert db.get_complaint(new[0])["assignment"]["officer_id"] is None
    retry = citizen.post("/api/classify", json={"complaint_text": TEXT_THEFT})
    assert retry.get_json()["complaint_id"] == new[0]


def test_classifier_failure_stores_nothing(citizen, monkeypatch):
    import classifier
    before = complaint_ids()

    def fail(*a, **k):
        raise RuntimeError("inference crashed")

    monkeypatch.setattr(classifier, "predict_with_backend", fail)
    r = citizen.post("/api/classify", json={"complaint_text": TEXT_THEFT})
    assert r.status_code == 500 and "inference" not in r.get_data(as_text=True)
    assert complaint_ids() == before
