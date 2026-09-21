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
CITIZEN = "+919000000001"

def login(username, pw=PW):
    c = app.test_client()
    r = c.post("/api/auth/login", json={"username": username, "password": pw})
    assert r.status_code == 200, (username, r.json)
    c.h = {"X-CSRF-TOKEN": r.json["csrf_token"]}
    c.user = r.json["user"]
    return c

def code_for(client, path, body):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r = client.post(path, json=body, headers=getattr(client, "h", None))
    m = re.search(r"code for (\S+): (\d{6})", buf.getvalue())
    return r, (m.group(2) if m else None)

def sms_login(phone, name=None):
    c = app.test_client()
    r, code = code_for(c, "/api/auth/otp/request", {"channel": "sms", "identifier": phone})
    assert code, r.json
    body = {"channel": "sms", "identifier": phone, "code": code}
    if name: body["name"] = name
    r = c.post("/api/auth/otp/verify", json=body)
    assert r.status_code == 200, r.json
    c.h = {"X-CSRF-TOKEN": r.json["csrf_token"]}
    c.user = r.json["user"]
    return c

def clear_limits():
    conn = db.get_connection(); conn.execute("DELETE FROM auth_attempts"); conn.commit(); conn.close()

# ---------------- staff sign in with username or email
c = app.test_client()
r = c.post("/api/auth/login", json={"username": "arjun.rao", "password": PW})
check("officer signs in with username", r.status_code == 200 and r.json["user"]["username"] == "arjun.rao", r.json)
r = app.test_client().post("/api/auth/login", json={"email": "lps.officer@nivara.test", "password": PW})
check("email still works for staff", r.status_code == 200)
r = app.test_client().post("/api/auth/login", json={"username": "arjun.rao", "password": "wrong"})
check("wrong password generic message", r.status_code == 401 and r.json["error"] == "Incorrect username or password.")
r = app.test_client().post("/api/auth/login", json={"username": CITIZEN, "password": "x"})
check("citizen cannot use the staff password route", r.status_code == 401)

arjun = login("arjun.rao"); meena = login("meena.pillai"); farhan = login("farhan.ali")
kavya = login("kavya.nair"); nikhil = login("nikhil.das"); admin = login("admin", "NivaraAdmin2026")

# ---------------- citizen: phone + OTP + name
clear_limits()
citizen = sms_login(CITIZEN)
check("citizen signs in with mobile + code", citizen.user["phone"] == CITIZEN and citizen.user["role"] == "citizen")
new_cit = app.test_client()
r, code = code_for(new_cit, "/api/auth/otp/request", {"channel": "sms", "identifier": "9123456780"})
r = new_cit.post("/api/auth/otp/verify", json={"channel": "sms", "identifier": "9123456780", "code": code})
check("new number must give a name", r.status_code == 400 and r.json["code"] == "NAME_REQUIRED")
r = new_cit.post("/api/auth/otp/verify", json={"channel": "sms", "identifier": "9123456780", "code": code, "name": "Priya S"})
check("new citizen account created with name", r.status_code == 200 and r.json["user"]["name"] == "Priya S")
priya_h = {"X-CSRF-TOKEN": r.json["csrf_token"]}
new_cit.h = priya_h

# file a complaint and follow it
r = new_cit.post("/api/classify", json={"complaint_text": "My gold chain was snatched by two men on a motorcycle near the bus stand yesterday evening.", "station": "PS-NORTH"}, headers=priya_h)
check("citizen files with a station", r.status_code == 200 and r.json["station"] == "PS-NORTH", r.json)
case_id = r.json["complaint_id"]
full = db.get_complaint(case_id)
check("auto-assigned on filing", full["assignment"]["officer_id"] is not None, full["assignment"])
v = new_cit.get(f"/api/complaints/{case_id}").json
check("citizen sees status + signature deadline, no analysis", v["status"] == "New" and v["signature_due_at"] and "sections" not in v)
check("citizen tracking shows officer only after review", v["officer"] is None and v["can_sign_digitally"] is True, v)

# ---------------- digital signature
r = new_cit.post(f"/api/complaints/{case_id}/sign", json={"declaration": True, "code": "000000"}, headers=priya_h)
check("signing needs a valid code", r.status_code == 400)
r, sign_code = code_for(new_cit, f"/api/complaints/{case_id}/sign/request", {})
check("signature code sent to the account's mobile", r.status_code == 200 and sign_code and r.json["channel"] == "sms", r.json)
r = new_cit.post(f"/api/complaints/{case_id}/sign", json={"code": sign_code}, headers=priya_h)
check("declaration must be ticked", r.status_code == 400 and "declaration" in r.json["error"].lower())
r = new_cit.post(f"/api/complaints/{case_id}/sign", json={"declaration": True, "code": sign_code}, headers=priya_h)
check("complaint signed digitally", r.status_code == 200 and r.json["signature_method"] == "digital" and r.json["signature_confirmed_at"], r.json)
check("signature recorded in the audit trail", any(e["action"] == "signature_confirmed" for e in r.json["events"]))
owner_id = db.get_complaint(case_id)["assignment"]["officer_id"]
owner = login(db.get_user(owner_id)["username"])
r = owner.patch(f"/api/complaints/{case_id}", json={"status": "Registered"}, headers=owner.h)
check("digitally signed complaint can be registered without a station visit", r.status_code == 200 and r.json["status"] == "Registered", r.json)
r, again = code_for(new_cit, f"/api/complaints/{case_id}/sign/request", {})
check("cannot sign twice", r.status_code == 409)

# ---------------- changing phone number
clear_limits()
r, change_code = code_for(citizen, "/api/auth/phone/change/request", {"phone": "9123456780"})
check("cannot move to a number in use", r.status_code == 409, r.json)
before = [c["complaint_id"] for c in citizen.get("/api/my/complaints").json["complaints"]]
r, change_code = code_for(citizen, "/api/auth/phone/change/request", {"phone": "9555500001"})
check("change code sent to the new number", r.status_code == 200 and change_code, r.json)
r = citizen.post("/api/auth/phone/change/verify", json={"phone": "9555500001", "code": "111111"}, headers=citizen.h)
check("wrong change code rejected", r.status_code == 400)
r = citizen.post("/api/auth/phone/change/verify", json={"phone": "9555500001", "code": change_code}, headers=citizen.h)
check("number changed", r.status_code == 200 and r.json["user"]["phone"] == "+919555500001" and r.json["previous_phone"] == CITIZEN, r.json)
after = [c["complaint_id"] for c in citizen.get("/api/my/complaints").json["complaints"]]
check("complaints follow the citizen to the new number", after == before and len(after) > 0, (before, after))
clear_limits()
moved = sms_login("9555500001")
check("signing in on the new number reaches the same account", moved.user["id"] == citizen.user["id"])

# the old number, reissued to someone else, must start empty
clear_limits()
stranger = sms_login(CITIZEN, name="Someone Else")
check("recycled number creates a NEW account", stranger.user["id"] != citizen.user["id"], (stranger.user, citizen.user))
check("recycled number sees none of the old complaints", stranger.get("/api/my/complaints").json["complaints"] == [])
old_case = before[0]
check("recycled number cannot open the old complaints", stranger.get(f"/api/complaints/{old_case}").status_code == 404)
check("number change recorded in history", db.list_phone_history(citizen.user["id"])[0]["phone"] == CITIZEN)

# admin recovery for a lost SIM
r = admin.put(f"/api/admin/users/{citizen.user['id']}/phone", json={"phone": "9555500002"}, headers=admin.h)
check("recovery requires a verification note", r.status_code == 400)
r = admin.put(f"/api/admin/users/{citizen.user['id']}/phone", json={"phone": "9555500002", "reason": "Aadhaar checked at PS-CENTRAL"}, headers=admin.h)
check("admin re-points a lost-SIM account, logged", r.status_code == 200 and r.json["user"]["phone"] == "+919555500002"
      and "Station verification" in r.json["history"][0]["reason"], r.json)
check("officers cannot re-point accounts", arjun.put(f"/api/admin/users/{citizen.user['id']}/phone", json={"phone": "9555500003", "reason": "x"}, headers=arjun.h).status_code == 403)

# ---------------- transparency: every officer sees every case
total = db.get_stats()["total_complaints"]
all_cases = arjun.get("/api/complaints?limit=200").json["complaints"]
check("officer sees every case in the district", len(all_cases) == total, (len(all_cases), total))
check("every case shows who holds it", all(("officer_name" in c["assignment"]) for c in all_cases))
mine = arjun.get("/api/complaints?view=mine").json["complaints"]
check("view=mine gives own caseload", mine and all(c["assignment"]["officer_id"] == arjun.user["id"] for c in mine))
check("filter by station", all(c["station"] == "PS-NORTH" for c in arjun.get("/api/complaints?station=PS-NORTH").json["complaints"]))
others = [c for c in all_cases if c["assignment"]["officer_id"] != arjun.user["id"] and c["complainant"]]
check("complainant contact masked on other officers' cases",
      bool(others) and others[0]["complainant"]["masked"] and "****" in (others[0]["complainant"]["phone"] or ""), others[:1])
d = arjun.get(f"/api/complaints/{others[0]['complaint_id']}").json
check("other officer's case is read-only", d["can_act"] is False and d["allowed_statuses"] == [])
check("case diary stays with the assigned officer", all(e["action"] != "diary_entry" for e in d["events"]))
r = arjun.patch(f"/api/complaints/{others[0]['complaint_id']}", json={"note": "x"}, headers=arjun.h)
check("non-assigned officer cannot act", r.status_code == 403 and "allocated to" in r.json["error"], r.json)
own = mine[0]["complaint_id"]
check("assigned officer sees full contact", arjun.get(f"/api/complaints/{own}").json["complainant"] is None or
      not arjun.get(f"/api/complaints/{own}").json["complainant"].get("masked"))
check("assigned officer can act", arjun.patch(f"/api/complaints/{own}", json={"note": "Contacted the complainant."}, headers=arjun.h).status_code == 200)
check("admin sees unmasked contact", any(c["complainant"] and not c["complainant"].get("masked")
      for c in admin.get("/api/complaints?limit=200").json["complaints"] if c["complainant"]))

# ---------------- workload-aware allocation
w = arjun.get("/api/officers").json
check("officer workload visible to officers", {"open_cases", "capacity", "load_percent", "availability"} <= set(w["officers"][0]), w["officers"][0])
check("weights published", w["weights"]["High"] > w["weights"]["Low"])

theft = "Unknown persons broke the lock of the shop and removed goods during the night."
db.update_user(meena.user["id"], capacity=3)
loads = {o["name"]: o for o in admin.get("/api/officers").json["officers"]}
r = admin.post("/api/complaints", json={})  # not a real route; ignored
picks = []
for _ in range(3):
    picks.append(arjun.post("/api/classify", json={"complaint_text": theft, "station": "PS-CENTRAL"}, headers=arjun.h).json["assignment"]["officer_name"])
check("allocation respects capacity (low-capacity officer not overloaded)", picks.count("ASI Meena Pillai") <= 1, picks)
check("station preference applied", picks.count("SI Arjun Rao") >= 2, picks)

r = meena.patch("/api/me/availability", json={"availability": "on_leave"}, headers=meena.h)
check("officer marks leave; open cases move away", r.status_code == 200 and not db.open_case_ids(assigned_to=meena.user["id"]), r.json)
pick = arjun.post("/api/classify", json={"complaint_text": theft, "station": "PS-NORTH"}, headers=arjun.h).json
check("officer on leave gets no new cases", pick["assignment"]["officer_name"] != "ASI Meena Pillai", pick["assignment"])
r = meena.patch("/api/me/availability", json={"availability": "nap"}, headers=meena.h)
check("invalid availability rejected", r.status_code == 400)
r = admin.patch(f"/api/admin/users/{meena.user['id']}", json={"availability": "available", "capacity": 8}, headers=admin.h)
check("admin sets availability and capacity", r.status_code == 200 and r.json["user"]["capacity"] == 8, r.json)

busy_before = [o for o in admin.get("/api/officers").json["officers"] if o["name"] == "SI Arjun Rao"][0]
db.update_user(arjun.user["id"], availability="busy")
pick = admin.get(f"/api/officers?unit=Local Police Station&station=PS-CENTRAL").json["officers"]
ranked = sorted([o for o in pick if o["allocation_score"] is not None], key=lambda o: o["allocation_score"])
check("busy officers rank below available ones", ranked[0]["name"] != "SI Arjun Rao" or busy_before["load_percent"] == 0, [o["name"] for o in ranked[:2]])
db.update_user(arjun.user["id"], availability="available")

r = admin.post("/api/admin/users", json={"username": "new.officer", "email": "new@nivara.test", "name": "SI New",
                                          "role": "officer", "password": "StationX2026a", "unit": "Cyber Cell",
                                          "station": "PS-CYBER", "capacity": 15}, headers=admin.h)
check("admin creates officer with username, station and capacity", r.status_code == 201 and r.json["user"]["capacity"] == 15, r.json)
check("new officer can sign in with their username", app.test_client().post("/api/auth/login", json={"username": "new.officer", "password": "StationX2026a"}).status_code == 200)
r = admin.post("/api/admin/users", json={"username": "arjun.rao", "email": "dup@nivara.test", "name": "Dup",
                                          "role": "officer", "password": "StationX2026a"}, headers=admin.h)
check("duplicate username rejected", r.status_code == 409, r.json)
check("stations listed", len(admin.get("/api/stations").json["stations"]) == 4)

print(f"\n{'ALL PASSED' if not fails else str(fails) + ' FAILED'}")
