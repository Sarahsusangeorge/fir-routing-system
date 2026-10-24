"""
Station and unit administration.

Both are reference data that officer allocation reads directly: a case is kept
at the station it was filed at, and eligibility is decided by unit. Neither is
protected by a foreign key -- users.station, complaints.station and users.unit
are plain text -- so the tests that matter most here are the ones about what
happens to those references when a station or unit is removed or renamed.
"""

THEFT = "Unknown persons stole my bicycle from outside the library on Tuesday evening."


def _units(admin):
    return {u["name"]: u for u in admin.get("/api/admin/units").get_json()["units"]}


def _stations(admin):
    return {s["code"]: s for s in admin.get("/api/admin/stations").get_json()["stations"]}


# ---------------------------------------------------------------------------
# Stations
# ---------------------------------------------------------------------------

def test_stations_are_listed_with_what_depends_on_them(admin):
    stations = _stations(admin)
    assert stations, "seed data should provide stations"
    sample = next(iter(stations.values()))
    assert {"code", "name", "officers", "complaints"} <= set(sample)


def test_a_station_can_be_added_and_renamed(admin):
    r = admin.post("/api/admin/stations",
                   json={"code": "ps-west", "name": "West Police Station", "district": "Vellore"})
    assert r.status_code == 201, r.get_json()
    # The code is normalised, because officers and complaints store it verbatim.
    assert r.get_json()["station"]["code"] == "PS-WEST"

    r = admin.patch("/api/admin/stations/PS-WEST", json={"name": "West Station"})
    assert r.status_code == 200
    assert r.get_json()["station"]["name"] == "West Station"
    assert _stations(admin)["PS-WEST"]["name"] == "West Station"


def test_a_station_code_must_look_like_a_code(admin):
    for bad in ("", "x", "ps west", "ps_west!", "a" * 40):
        r = admin.post("/api/admin/stations", json={"code": bad, "name": "Somewhere"})
        assert r.status_code == 400, f"{bad!r} should be rejected"


def test_a_duplicate_station_code_is_refused(admin):
    body = {"code": "PS-WEST", "name": "West Police Station"}
    assert admin.post("/api/admin/stations", json=body).status_code == 201
    assert admin.post("/api/admin/stations", json=body).status_code == 409


def test_an_unused_station_can_be_removed(admin):
    assert admin.post("/api/admin/stations",
                      json={"code": "PS-WEST", "name": "West Police Station"}).status_code == 201
    assert admin.delete("/api/admin/stations/PS-WEST").status_code == 200
    assert "PS-WEST" not in _stations(admin)


def test_a_station_an_officer_is_posted_to_cannot_be_removed(admin):
    assert admin.post("/api/admin/stations",
                      json={"code": "PS-WEST", "name": "West Police Station"}).status_code == 201
    created = admin.post("/api/admin/users", json={
        "email": "west.officer@example.gov.in", "name": "West Officer", "role": "officer",
        "password": "Password123", "station": "PS-WEST",
    })
    assert created.status_code == 201, created.get_json()

    r = admin.delete("/api/admin/stations/PS-WEST")
    assert r.status_code == 409
    body = r.get_json()
    assert body["officers"] == 1
    # The reason names the count, so the administrator knows what to move.
    assert "1 officer" in body["error"]
    assert "PS-WEST" in _stations(admin)


def test_a_station_with_complaints_cannot_be_removed(admin):
    station = next(iter(_stations(admin)))
    r = admin.post("/api/classify", json={"complaint_text": THEFT, "station": station})
    assert r.status_code == 200, r.get_json()

    r = admin.delete(f"/api/admin/stations/{station}")
    assert r.status_code == 409
    assert r.get_json()["complaints"] >= 1


def test_a_station_still_referenced_but_never_registered_is_still_shown(admin):
    """A deleted-then-still-referenced code must not vanish from the screen."""
    assert admin.post("/api/admin/stations",
                      json={"code": "PS-WEST", "name": "West Police Station"}).status_code == 201
    assert admin.post("/api/admin/users", json={
        "email": "west2@example.gov.in", "name": "West Officer", "role": "officer",
        "password": "Password123", "station": "PS-WEST",
    }).status_code == 201

    # Remove it behind the endpoint's back, as a stray database edit would.
    import db
    db.delete_station("PS-WEST", actor_id=None)

    shown = _stations(admin)["PS-WEST"]
    assert shown["unregistered"] is True
    assert shown["officers"] == 1


def test_missing_station_is_not_found(admin):
    assert admin.patch("/api/admin/stations/PS-NOWHERE", json={"name": "x y"}).status_code == 404
    assert admin.delete("/api/admin/stations/PS-NOWHERE").status_code == 404


# ---------------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------------

def test_units_in_use_appear_even_when_never_registered(admin):
    """Seed data names units only in routing rules, and those must still list."""
    units = _units(admin)
    assert "Women & Child Protection Unit" in units
    assert units["Women & Child Protection Unit"]["registered"] is False
    assert units["Women & Child Protection Unit"]["rules"] > 0
    assert units["Local Police Station"]["is_default"] is True


def test_a_unit_can_be_created_before_anything_uses_it(admin):
    r = admin.post("/api/admin/units",
                   json={"name": "Narcotics Cell", "description": "Drug offences"})
    assert r.status_code == 201, r.get_json()

    unit = _units(admin)["Narcotics Cell"]
    assert unit["registered"] is True
    assert unit["officers"] == 0 and unit["rules"] == 0
    # And it is immediately offered when posting an officer.
    assert admin.post("/api/admin/users", json={
        "email": "narc@example.gov.in", "name": "Narcotics Officer", "role": "officer",
        "password": "Password123", "unit": "Narcotics Cell",
    }).status_code == 201


def test_a_duplicate_unit_is_refused(admin):
    body = {"name": "Narcotics Cell"}
    assert admin.post("/api/admin/units", json=body).status_code == 201
    assert admin.post("/api/admin/units", json=body).status_code == 409


def test_renaming_a_unit_carries_its_officers_and_rules_with_it(admin):
    assert admin.post("/api/admin/units", json={"name": "Narcotics Cell"}).status_code == 201
    assert admin.post("/api/admin/users", json={
        "email": "narc2@example.gov.in", "name": "Narcotics Officer", "role": "officer",
        "password": "Password123", "unit": "Narcotics Cell",
    }).status_code == 201
    assert admin.post("/api/admin/routing-rules", json={
        "section_code": "379", "unit": "Narcotics Cell", "precedence": 6,
    }).status_code == 201

    r = admin.patch("/api/admin/units/Narcotics Cell", json={"name": "Anti-Narcotics Cell"})
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["officers_moved"] == 1
    assert body["rules_moved"] == 1

    units = _units(admin)
    assert "Narcotics Cell" not in units
    moved = units["Anti-Narcotics Cell"]
    assert moved["officers"] == 1 and moved["rules"] == 1

    # The routing rule now names the new unit, so routing still resolves.
    rules = admin.get("/api/admin/routing-rules").get_json()["rules"]
    assert any(r["unit"] == "Anti-Narcotics Cell" for r in rules)
    assert not any(r["unit"] == "Narcotics Cell" for r in rules)


def test_renaming_onto_an_existing_unit_is_refused(admin):
    assert admin.post("/api/admin/units", json={"name": "Narcotics Cell"}).status_code == 201
    assert admin.post("/api/admin/units", json={"name": "Traffic Cell"}).status_code == 201
    r = admin.patch("/api/admin/units/Narcotics Cell", json={"name": "Traffic Cell"})
    assert r.status_code == 409


def test_a_unit_description_can_be_set_and_cleared(admin):
    assert admin.post("/api/admin/units",
                      json={"name": "Narcotics Cell", "description": "Drug offences"}).status_code == 201
    assert _units(admin)["Narcotics Cell"]["description"] == "Drug offences"

    r = admin.patch("/api/admin/units/Narcotics Cell", json={"description": ""})
    assert r.status_code == 200
    assert _units(admin)["Narcotics Cell"]["description"] is None


def test_an_unused_unit_can_be_removed(admin):
    assert admin.post("/api/admin/units", json={"name": "Narcotics Cell"}).status_code == 201
    assert admin.delete("/api/admin/units/Narcotics Cell").status_code == 200
    assert "Narcotics Cell" not in _units(admin)


def test_a_unit_with_officers_or_rules_cannot_be_removed(admin):
    assert admin.post("/api/admin/units", json={"name": "Narcotics Cell"}).status_code == 201
    assert admin.post("/api/admin/routing-rules", json={
        "section_code": "379", "unit": "Narcotics Cell", "precedence": 6,
    }).status_code == 201

    r = admin.delete("/api/admin/units/Narcotics Cell")
    assert r.status_code == 409
    assert r.get_json()["rules"] == 1
    assert "Narcotics Cell" in _units(admin)


def test_the_fallback_unit_cannot_be_removed(admin):
    assert admin.post("/api/admin/units", json={"name": "Local Police Station"}).status_code == 201
    r = admin.delete("/api/admin/units/Local Police Station")
    assert r.status_code == 400
    assert "fallback" in r.get_json()["error"]


def test_an_unregistered_unit_must_be_created_before_it_can_be_edited(admin):
    r = admin.patch("/api/admin/units/Crime Branch", json={"name": "Crime Wing"})
    assert r.status_code == 404
    assert "registered" in r.get_json()["error"]


# ---------------------------------------------------------------------------
# Who may do any of this, and whether it is recorded
# ---------------------------------------------------------------------------

def test_officers_cannot_administer_stations_or_units(staff):
    officer = staff("arjun.rao")
    assert officer.get("/api/admin/stations").status_code == 403
    assert officer.post("/api/admin/stations",
                        json={"code": "PS-X", "name": "X"}).status_code == 403
    assert officer.get("/api/admin/units").status_code == 403
    assert officer.delete("/api/admin/units/Crime Branch").status_code == 403


def test_station_and_unit_changes_reach_the_policy_log(admin):
    admin.post("/api/admin/stations", json={"code": "PS-WEST", "name": "West Police Station"})
    admin.patch("/api/admin/stations/PS-WEST", json={"district": "Ranipet"})
    admin.post("/api/admin/units", json={"name": "Narcotics Cell"})
    admin.patch("/api/admin/units/Narcotics Cell", json={"name": "Anti-Narcotics Cell"})

    changes = admin.get("/api/admin/policy-changes").get_json()["changes"]
    recorded = [(c["entity"], c["field"]) for c in changes]
    assert ("station", "created") in recorded
    assert ("station", "district") in recorded
    assert ("unit", "created") in recorded
    assert ("unit", "renamed") in recorded
    assert all(c["actor_name"] for c in changes if c["entity"] in ("station", "unit"))
