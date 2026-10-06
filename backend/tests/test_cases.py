import io, re, sys, contextlib
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as appmod, db, workflow
app = appmod.app
app.config["TESTING"] = True

fails = 0
def check(name, cond, extra=""):
    global fails
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -> {extra}"))
    if not cond: fails += 1

PW = "NivaraOfficer2026"
TEXT = "The accused fraudulently induced the complainant to transfer money for a fake investment scheme."

def login(email, pw):
    c = app.test_client()
    r = c.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, (email, r.json)
    c.h = {"X-CSRF-TOKEN": r.json["csrf_token"]}
    c.user = r.json["user"]
    return c

def request_code(client, **body):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r = client.post("/api/auth/otp/request", json=body)
    m = re.search(r"code for (\S+): (\d{6})", buf.getvalue())
    return r, (m.group(2) if m else None), (m.group(1) if m else None)

def clear_limits():
    conn = db.get_connection(); conn.execute("DELETE FROM auth_attempts"); conn.commit(); conn.close()

anon = app.test_client()

# ---------------- basics
check("health public", anon.get("/api/health").status_code == 200)
check("classify needs login", anon.post("/api/classify", json={"complaint_text": TEXT}).status_code == 401)
r = anon.post("/api/auth/login", json={"email": "lps.officer@nivara.test", "password": "nope"})
check("wrong password generic", r.status_code == 401 and r.json["error"] == "Incorrect username or password.")

# ---------------- citizen sign-in: email (new and legacy request shapes)
cit = app.test_client()
r, code, ident = request_code(cit, channel="email", identifier="Asha@Example.com")
check("email code sent, identifier normalised", r.status_code == 200 and code and ident == "asha@example.com", (r.json, ident))
r = cit.post("/api/auth/otp/verify", json={"channel": "email", "identifier": "asha@example.com", "code": code})
check("new email user needs name", r.status_code == 400 and r.json.get("code") == "NAME_REQUIRED")
r = cit.post("/api/auth/otp/verify", json={"channel": "email", "identifier": "asha@example.com", "code": code,
                                           "name": "Asha Menon", "contact": "bad-number"})
check("invalid optional mobile rejected", r.status_code == 400 and "mobile" in r.json["error"], r.json)
r = cit.post("/api/auth/otp/verify", json={"channel": "email", "identifier": "asha@example.com", "code": code,
                                           "name": "Asha Menon", "contact": "98400 11111"})
check("email citizen created", r.status_code == 200 and r.json["user"]["email"] == "asha@example.com" and r.json["user"]["phone"] is None, r.json)
asha_h = {"X-CSRF-TOKEN": r.json["csrf_token"]}
row = db.get_user_by_login(email="asha@example.com")
check("unverified mobile kept as contact only", row["contact_phone"] == "+919840011111" and row["phone"] is None, row)

legacy = app.test_client()
r, code, _ = request_code(legacy, email="legacy@example.com")
r = legacy.post("/api/auth/otp/verify", json={"email": "legacy@example.com", "code": code, "name": "Old Client"})
check("legacy {email} request shape still works", r.status_code == 200, r.json)

# ---------------- citizen sign-in: mobile
sms = app.test_client()
r, _, _ = request_code(sms, channel="sms", identifier="12345")
check("invalid mobile rejected", r.status_code == 400 and "mobile" in r.json["error"])
r, _, _ = request_code(sms, channel="sms", identifier="5876543210")
check("non-Indian-mobile prefix rejected", r.status_code == 400)
# the number Asha typed but never verified must still be claimable by its owner
r, code, ident = request_code(sms, channel="sms", identifier="+91 98400-11111")
check("sms code sent, number normalised to E.164", r.status_code == 200 and ident == "+919840011111", (r.json, ident))
r = sms.post("/api/auth/otp/verify", json={"channel": "email", "identifier": "x@example.com", "code": code})
check("code bound to its channel/identifier", r.status_code == 400)
r = sms.post("/api/auth/otp/verify", json={"channel": "sms", "identifier": "09840011111", "code": code, "name": "Ravi K",
                                           "contact": "ravi@example.com"})
check("mobile citizen created despite someone listing that number as contact",
      r.status_code == 200 and r.json["user"]["phone"] == "+919840011111" and r.json["user"]["email"] is None, r.json)
ravi_h = {"X-CSRF-TOKEN": r.json["csrf_token"]}
sms2 = app.test_client()
clear_limits()
r, code, _ = request_code(sms2, channel="sms", identifier="9840011111")
r = sms2.post("/api/auth/otp/verify", json={"channel": "sms", "identifier": "9840011111", "code": code})
check("returning mobile user signs straight in", r.status_code == 200 and r.json["user"]["name"] == "Ravi K", r.json)

staff_code = app.test_client()
r, code, _ = request_code(staff_code, channel="email", identifier="admin@nivara.test")
check("staff email gets no code, same response", r.status_code == 200 and code is None)

# ---------------- filing and allocation
r = cit.post("/api/classify", json={"complaint_text": TEXT}, headers=asha_h)
check("citizen files, limited view", r.status_code == 200 and "sections" not in r.json and r.json["officer"] is None, r.json)
asha_case = r.json["complaint_id"]
c = db.get_complaint(asha_case)
check("citizen case auto-assigned to EOW officer", c["assignment"]["officer_name"] == "Inspector Farhan Ali", c["assignment"])

lps = login("lps.officer@nivara.test", PW)
lps2 = login("lps2.officer@nivara.test", PW)
eow = login("eow.officer@nivara.test", PW)
duty = login("duty.officer@nivara.test", PW)
admin = login("admin@nivara.test", "NivaraAdmin2026")
# Keep allocation inside this test predictable.
for username in ("nikhil.das",):
    u = db.get_user_by_login(username=username)
    db.update_user(u["id"], availability="available")

theft = "Unknown persons entered the house at night and stole cash and household articles from the cupboard."
r1 = lps.post("/api/classify", json={"complaint_text": theft}, headers=lps.h).json
check("staff classify returns assignment", r1["assignment"]["officer_id"] is not None and r1["routing"]["unit"] == "Local Police Station", r1.get("assignment"))
check("station preference: a case filed at PS-CENTRAL goes to the PS-CENTRAL officer",
      r1["assignment"]["officer_id"] == lps.user["id"], r1["assignment"])

# With both officers at the same station, workload decides instead. Give the
# second officer plenty of headroom so capacity is not the deciding factor.
db.update_user(lps2.user["id"], station="PS-CENTRAL", capacity=50)
db.update_user(lps.user["id"], capacity=50)
# Distinct narratives: identical text within ten minutes is now treated as an
# accidental resubmission and returns the complaint already filed.
picks = [lps.post("/api/classify", json={"complaint_text": f"{theft} (incident {i})"}, headers=lps.h)
         .json["assignment"]["officer_id"]
         for i in range(4)]
check("least-loaded balancing across same-station officers",
      lps.user["id"] in picks and lps2.user["id"] in picks, picks)
db.update_user(lps2.user["id"], station="PS-NORTH", capacity=6)

mine = lps.get("/api/complaints?view=mine").json["complaints"]
check("officer sees only own caseload", mine and all(x["assignment"]["officer_id"] == lps.user["id"] for x in mine))
other = next(x for x in admin.get("/api/complaints?limit=200").json["complaints"] if x["assignment"]["officer_id"] != lps.user["id"])
d = lps.get(f"/api/complaints/{other['complaint_id']}")
check("officer can read another officer's case (transparency)", d.status_code == 200 and d.json["can_act"] is False)
check("officer cannot act on another officer's case",
      lps.patch(f"/api/complaints/{other['complaint_id']}", json={"note": "x"}, headers=lps.h).status_code == 403)
total = db.get_stats()["total_complaints"]
check("admin sees every case", len(admin.get("/api/complaints?limit=200").json["complaints"]) == total, total)
by_officer = admin.get(f"/api/complaints?officer={lps.user['id']}&limit=200").json["complaints"]
check("admin filter by officer", {x["complaint_id"] for x in by_officer} == {x["complaint_id"] for x in mine})
check("officer stats scoped to caseload", lps.get("/api/stats").json["total_complaints"] == len(mine))
check("citizen blocked from staff list", cit.get("/api/complaints").status_code == 403)

# ---------------- workflow rules
d = eow.get(f"/api/complaints/{asha_case}").json
check("detail has events + allowed statuses", d["events"][0]["action"] == "filed" and d["allowed_statuses"] == ["Under Review", "Registered", "Not Registered"], d.get("allowed_statuses"))
r = eow.patch(f"/api/complaints/{asha_case}", json={"status": "Under Investigation"}, headers=eow.h)
check("illegal transition rejected", r.status_code == 400 and "cannot move" in r.json["error"], r.json)
r = eow.patch(f"/api/complaints/{asha_case}", json={"status": "Registered"}, headers=eow.h)
check("citizen case can't register unsigned", r.status_code == 400 and "signed" in r.json["error"])
r = eow.patch(f"/api/complaints/{asha_case}", json={"status": "Registered", "signature_confirmed": True}, headers=eow.h)
check("register with signature", r.status_code == 200 and r.json["status"] == "Registered"
      and r.json["review"]["signature_method"] == "in_person", r.json)
check("after registration: investigation or close", r.json["allowed_statuses"] == ["Under Investigation", "Closed"])
r = eow.post(f"/api/complaints/{asha_case}/diary", json={"entry": "  "}, headers=eow.h)
check("empty diary entry rejected", r.status_code == 400)
r = eow.post(f"/api/complaints/{asha_case}/diary", json={"entry": "Called the complainant; bank details collected."}, headers=eow.h)
check("diary entry recorded", r.status_code == 201 and r.json["events"][-1]["action"] == "diary_entry")
check("citizen cannot write diary", cit.post(f"/api/complaints/{asha_case}/diary", json={"entry": "x"}, headers=asha_h).status_code == 403)
r = eow.patch(f"/api/complaints/{asha_case}", json={"status": "Under Investigation"}, headers=eow.h)
check("move to investigation", r.status_code == 200)
r = eow.patch(f"/api/complaints/{asha_case}", json={"status": "Closed"}, headers=eow.h)
check("closing needs a note", r.status_code == 400 and "note" in r.json["error"])
r = eow.patch(f"/api/complaints/{asha_case}", json={"status": "Charge Sheet Filed", "note": "Charge sheet filed before the magistrate."}, headers=eow.h)
check("charge sheet filed (final)", r.status_code == 200 and r.json["allowed_statuses"] == [])
check("officer cannot reopen final case", eow.patch(f"/api/complaints/{asha_case}", json={"status": "Under Investigation"}, headers=eow.h).status_code == 400)
v = cit.get(f"/api/complaints/{asha_case}").json
check("citizen sees status, unit, officer, note; no diary",
      v["status"] == "Charge Sheet Filed" and v["officer"] == "Inspector Farhan Ali"
      and v["unit"] == "Economic Offences Wing"
      and "Called the complainant" not in str(v)
      and all(e["action"] != "diary_entry" for e in v["events"]), v)
check("admin can reopen", admin.patch(f"/api/complaints/{asha_case}", json={"status": "Under Investigation"}, headers=admin.h).status_code == 200)

# ---------------- transfer and reassignment
case = r1["complaint_id"]
owner = login(db.get_user(db.get_complaint(case)["assignment"]["officer_id"])["email"], PW)
r = owner.patch(f"/api/complaints/{case}", json={"unit": "Cyber Cell"}, headers=owner.h)
check("transfer needs a reason", r.status_code == 400)
r = owner.patch(f"/api/complaints/{case}", json={"assigned_to": owner.user["id"]}, headers=owner.h)
check("officer cannot reassign", r.status_code == 400 and "administrator" in r.json["error"])
r = owner.patch(f"/api/complaints/{case}", json={"unit": "Cyber Cell", "override_reason": "Entry was made using a cloned smart lock."}, headers=owner.h)
new_officer_id = r.json["assignment"]["officer_id"]
check("transfer re-allocates to a Cyber Cell officer",
      r.status_code == 200 and r.json["routing"]["unit"] == "Cyber Cell" and new_officer_id != owner.user["id"]
      and db.get_user(new_officer_id)["unit"] in ("Cyber Cell", None)
      and r.json["review"]["original_unit"] == "Local Police Station", r.json.get("assignment"))
check("previous officer can no longer act on it",
      owner.patch(f"/api/complaints/{case}", json={"note": "x"}, headers=owner.h).status_code == 403)
cyber = login(db.get_user(new_officer_id)["email"], PW)
check("new officer can act on it", cyber.patch(f"/api/complaints/{case}", json={"note": "Taking this on."}, headers=cyber.h).status_code == 200)
r = admin.patch(f"/api/complaints/{case}", json={"assigned_to": 99999}, headers=admin.h)
check("reassign to unknown officer rejected", r.status_code == 400)
r = admin.patch(f"/api/complaints/{case}", json={"assigned_to": eow.user["id"]}, headers=admin.h)
acts = [e["action"] for e in r.json["events"]]
check("admin reassigns, logged, status untouched", r.status_code == 200 and r.json["assignment"]["officer_id"] == eow.user["id"]
      and acts[-1] == "assigned" and r.json["status"] == "Under Review", (r.json.get("status"), acts))

# ---------------- staff changes rebalance cases
lps_open = len(db.open_case_ids(assigned_to=lps.user["id"]))
r = admin.patch(f"/api/admin/users/{lps.user['id']}", json={"active": False}, headers=admin.h)
check("deactivation moves open cases to colleague", r.status_code == 200 and r.json["cases_moved"] == lps_open
      and not db.open_case_ids(assigned_to=lps.user["id"]), r.json)
check("deactivated officer's session rejected", lps.get("/api/complaints").status_code == 401)

cyber_case = lps2.post("/api/classify", json={"complaint_text": "The accused posing as a bank official obtained account credentials over the telephone and made unauthorised transfers."}, headers=lps2.h).json
check("cyber complaint goes to a cyber officer", cyber_case["routing"]["unit"] == "Cyber Cell" and cyber_case["assignment"]["officer_id"], cyber_case.get("routing"))
# Take every officer who could hold a Cyber Cell case out of service.
for username in ("nikhil.das", "kavya.nair", "duty.officer@nivara.test"):
    u = db.get_user_by_login(username=username) or db.get_user_by_login(email=username)
    if u:
        admin.patch(f"/api/admin/users/{u['id']}", json={"active": False}, headers=admin.h)
check("with nobody left for Cyber Cell, cases wait unassigned",
      cyber_case["complaint_id"] in db.open_case_ids(unassigned=True))
un = admin.get("/api/complaints?officer=unassigned").json["complaints"]
check("admin unassigned filter", cyber_case["complaint_id"] in [x["complaint_id"] for x in un])
r = admin.post("/api/admin/users", json={"email": "cyber2@nivara.test", "username": "rehan.s", "name": "SI Rehan S",
                                          "role": "officer", "password": "CyberCell2026x", "unit": "Cyber Cell",
                                          "station": "PS-CYBER"}, headers=admin.h)
check("new Cyber Cell officer picks up waiting cases", r.status_code == 201 and r.json["cases_assigned"] >= 1
      and r.json["user"]["open_cases"] >= 1, r.json)
staff = admin.get("/api/admin/users").json["users"]
check("staff list has open case counts", all("open_cases" in u for u in staff))

# ---------------- misc security
r = eow.post("/api/classify", json={"complaint_text": TEXT})
check("POST without CSRF rejected", r.status_code == 401)
r = anon.options("/api/classify", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
check("CORS allows frontend with credentials", r.headers.get("Access-Control-Allow-Credentials") == "true")
clear_limits()
codes = [anon.post("/api/auth/login", json={"email": "admin@nivara.test", "password": "bad"}).status_code for _ in range(6)]
check("login rate limited", codes[5] == 429, codes)

print(f"\n{'ALL PASSED' if not fails else str(fails) + ' FAILED'}")
sys.exit(1 if fails else 0)
