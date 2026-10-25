"""
Decision policy: severity weights and routing rules (FR9).

Priority and routing are driven by two reference tables rather than by model
weights. The paper rests a claim on that -- a jurisdiction can change policy
without retraining -- so these tests check the claim end to end: an
administrator edits a table, and the next complaint is scored or routed
differently, while results already recorded are left alone.

Every narrative below is synthetic and describes no real person.
"""

THEFT = "Unknown persons stole my bicycle from outside the library on Tuesday evening."
ASSAULT = "The accused sexually assaulted the complainant at her workplace last week."


def _classify(client, text):
    r = client.post("/api/classify", json={"complaint_text": text})
    assert r.status_code == 200, r.get_json()
    return r.get_json()


# ---------------------------------------------------------------------------
# Severity weights
# ---------------------------------------------------------------------------

def test_admin_sees_sections_with_their_severity_weights(admin):
    r = admin.get("/api/admin/sections")
    assert r.status_code == 200
    sections = r.get_json()["sections"]
    assert sections, "seed data should provide IPC sections"
    assert {"code", "title", "severity_weight", "cognizable", "bailable"} <= set(sections[0])
    # Returned gravest first, which is the order an administrator reviews them in.
    weights = [s["severity_weight"] for s in sections]
    assert weights == sorted(weights, reverse=True)


def test_raising_a_severity_weight_raises_the_priority_of_the_next_complaint(admin):
    """Theft scores Medium at severity 5; at severity 10 the same text is High."""
    before = _classify(admin, THEFT)
    assert before["priority"]["level"] == "Medium"
    assert before["priority"]["driver"] == "379"

    r = admin.patch("/api/admin/sections/379", json={"severity_weight": 10})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["section"]["severity_weight"] == 10

    after = _classify(admin, THEFT + " The cycle was locked to the stand.")
    assert after["priority"]["level"] == "High"
    assert after["priority"]["score"] > before["priority"]["score"]


def test_a_severity_change_does_not_rewrite_results_already_recorded(admin):
    filed = _classify(admin, THEFT)
    complaint_id = filed["complaint_id"]
    recorded = filed["priority"]["score"]

    assert admin.patch("/api/admin/sections/379", json={"severity_weight": 10}).status_code == 200

    r = admin.get(f"/api/complaints/{complaint_id}")
    assert r.status_code == 200
    assert r.get_json()["priority"]["score"] == recorded


def test_severity_weight_outside_the_rubric_is_rejected(admin):
    for bad in (0, 11, -3, "high", True, None):
        r = admin.patch("/api/admin/sections/379", json={"severity_weight": bad})
        assert r.status_code == 400, f"{bad!r} should be rejected"
    assert admin.get("/api/admin/sections").status_code == 200


def test_max_punishment_accepts_null_for_life_or_death(admin):
    r = admin.patch("/api/admin/sections/379", json={"max_punishment_years": None})
    assert r.status_code == 200
    assert r.get_json()["section"]["max_punishment_years"] is None

    assert admin.patch("/api/admin/sections/379", json={"max_punishment_years": 0}).status_code == 400
    assert admin.patch("/api/admin/sections/379", json={"max_punishment_years": 500}).status_code == 400


def test_cognizable_and_bailable_must_be_boolean(admin):
    assert admin.patch("/api/admin/sections/379", json={"cognizable": "yes"}).status_code == 400
    r = admin.patch("/api/admin/sections/379", json={"cognizable": False, "bailable": True})
    assert r.status_code == 200
    assert r.get_json()["section"]["cognizable"] == 0
    assert r.get_json()["section"]["bailable"] == 1


def test_unknown_section_is_not_found(admin):
    assert admin.patch("/api/admin/sections/999ZZ", json={"severity_weight": 5}).status_code == 404


def test_empty_section_update_is_rejected(admin):
    assert admin.patch("/api/admin/sections/379", json={}).status_code == 400


# ---------------------------------------------------------------------------
# Routing rules
# ---------------------------------------------------------------------------

def test_admin_sees_routing_rules_with_their_units(admin):
    r = admin.get("/api/admin/routing-rules")
    assert r.status_code == 200
    body = r.get_json()
    assert body["rules"], "seed data should provide routing rules"
    assert body["default_unit"] == "Local Police Station"
    assert {"id", "section_code", "unit", "precedence", "section_title"} <= set(body["rules"][0])
    # Lowest precedence first, which is the order the routing engine resolves.
    assert body["rules"][0]["precedence"] <= body["rules"][-1]["precedence"]
    assert set(body["officers_by_unit"]) == set(body["units"])


def test_changing_a_rules_unit_changes_where_the_next_complaint_goes(admin):
    before = _classify(admin, ASSAULT)
    assert before["routing"]["unit"] == "Women & Child Protection Unit"
    assert before["routing"]["matched_section"] == "376"

    rules = admin.get("/api/admin/routing-rules").get_json()["rules"]
    rule = next(r for r in rules if r["section_code"] == "376")
    r = admin.patch(f"/api/admin/routing-rules/{rule['id']}", json={"unit": "Crime Branch"})
    assert r.status_code == 200, r.get_json()

    after = _classify(admin, ASSAULT + " A complaint was made the same day.")
    assert after["routing"]["unit"] == "Crime Branch"


def test_deleting_a_rule_falls_back_to_the_jurisdiction(admin):
    rules = admin.get("/api/admin/routing-rules").get_json()["rules"]
    for rule in [r for r in rules if r["section_code"] in ("376", "323")]:
        assert admin.delete(f"/api/admin/routing-rules/{rule['id']}").status_code == 200

    after = _classify(admin, ASSAULT)
    assert after["routing"]["unit"] == "Local Police Station"


def test_a_section_cannot_route_twice_to_the_same_unit(admin):
    body = {"section_code": "379", "unit": "Cyber Cell", "precedence": 4}
    assert admin.post("/api/admin/routing-rules", json=body).status_code == 201
    r = admin.post("/api/admin/routing-rules", json=body)
    assert r.status_code == 409


def test_a_new_rule_reports_whether_any_officer_serves_that_unit(admin):
    r = admin.post("/api/admin/routing-rules",
                   json={"section_code": "379", "unit": "Narcotics Cell", "precedence": 6})
    assert r.status_code == 201, r.get_json()
    # A unit nobody staffs is allowed -- jurisdictions reorganise -- but the
    # administrator is told at once, because cases routed there wait.
    assert r.get_json()["officers_available"] == 0


def test_precedence_must_be_a_whole_number_in_range(admin):
    for bad in (0, 1000, 2.5, "first", True):
        r = admin.post("/api/admin/routing-rules",
                       json={"section_code": "379", "unit": "Cyber Cell", "precedence": bad})
        assert r.status_code == 400, f"{bad!r} should be rejected"


def test_a_rule_for_an_unknown_section_is_not_found(admin):
    r = admin.post("/api/admin/routing-rules",
                   json={"section_code": "999ZZ", "unit": "Cyber Cell", "precedence": 3})
    assert r.status_code == 404


def test_missing_rule_is_not_found(admin):
    assert admin.patch("/api/admin/routing-rules/999999", json={"precedence": 2}).status_code == 404
    assert admin.delete("/api/admin/routing-rules/999999").status_code == 404


# ---------------------------------------------------------------------------
# Who may change policy, and whether the change is attributable
# ---------------------------------------------------------------------------

def test_officers_cannot_change_decision_policy(staff):
    officer = staff("arjun.rao")
    assert officer.get("/api/admin/sections").status_code == 403
    assert officer.patch("/api/admin/sections/379", json={"severity_weight": 9}).status_code == 403
    assert officer.get("/api/admin/routing-rules").status_code == 403
    assert officer.post("/api/admin/routing-rules",
                        json={"section_code": "379", "unit": "Cyber Cell",
                              "precedence": 3}).status_code == 403
    assert officer.get("/api/admin/policy-changes").status_code == 403


def test_citizens_cannot_change_decision_policy(citizen_login):
    citizen = citizen_login()
    assert citizen.get("/api/admin/sections").status_code == 403
    assert citizen.patch("/api/admin/sections/379", json={"severity_weight": 9}).status_code == 403


def test_every_policy_change_records_who_made_it(admin):
    admin.patch("/api/admin/sections/379", json={"severity_weight": 9})
    rules = admin.get("/api/admin/routing-rules").get_json()["rules"]
    rule = next(r for r in rules if r["section_code"] == "376")
    admin.patch(f"/api/admin/routing-rules/{rule['id']}", json={"precedence": 2})
    admin.delete(f"/api/admin/routing-rules/{rule['id']}")

    changes = admin.get("/api/admin/policy-changes").get_json()["changes"]
    fields = [(c["entity"], c["field"]) for c in changes]
    assert ("ipc_section", "severity_weight") in fields
    assert ("routing_rule", "precedence") in fields
    assert ("routing_rule", "deleted") in fields

    weight_change = next(c for c in changes if c["field"] == "severity_weight")
    assert weight_change["record_key"] == "379"
    assert weight_change["old_value"] == "5.0"
    assert weight_change["new_value"] == "9.0"
    assert weight_change["actor_name"], "the administrator must be named"


def test_a_change_that_alters_nothing_is_not_logged(admin):
    current = next(s for s in admin.get("/api/admin/sections").get_json()["sections"]
                   if s["code"] == "379")
    before = len(admin.get("/api/admin/policy-changes").get_json()["changes"])
    admin.patch("/api/admin/sections/379", json={"severity_weight": current["severity_weight"]})
    after = len(admin.get("/api/admin/policy-changes").get_json()["changes"])
    assert after == before
