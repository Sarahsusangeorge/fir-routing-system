"""Quick adversarial API probes: IDOR, SQLi-in-text, malformed/oversized
payloads, CORS header check. Run against a freshly-seeded server on :5000."""
import json
import requests

BASE = "http://localhost:5000"
results = []


def check(name, cond, detail=""):
    results.append((name, cond, detail))
    print(("PASS" if cond else "FAIL"), name, ("--", detail) if detail else "")


s_admin = requests.Session()
r = s_admin.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "NivaraAdmin2026"})
s_admin.headers.update({"X-CSRF-TOKEN": r.json()["csrf_token"]})

# --- SQLi probe in complaint_text (free text, parameterized storage expected) ---
sqli_text = "Robbery reported'; DROP TABLE complaints; -- at the market by an armed man"
r = s_admin.post(f"{BASE}/api/classify", json={"complaint_text": sqli_text, "station": "PS-CENTRAL"})
check("SQLi payload in complaint_text handled without 500 / table intact",
      r.status_code == 200, f"status={r.status_code}")
r2 = s_admin.get(f"{BASE}/api/complaints?scope=all")
check("complaints table still queryable after SQLi attempt (not dropped)",
      r2.status_code == 200 and "complaints" in r2.json())

# --- SQLi probe via query params ---
r = s_admin.get(f"{BASE}/api/complaints?unit=' OR '1'='1")
check("SQLi in query param doesn't 500 / doesn't bypass filtering oddly",
      r.status_code in (200, 400), f"status={r.status_code}")

# --- Oversized payload ---
huge_text = "A" * 2_000_000  # 2MB of text
try:
    r = s_admin.post(f"{BASE}/api/classify", json={"complaint_text": huge_text, "station": "PS-CENTRAL"}, timeout=15)
    check("2MB complaint_text handled (not a crash / hang)", r.status_code in (200, 400, 413), f"status={r.status_code}")
except requests.exceptions.RequestException as e:
    check("2MB complaint_text handled (not a crash / hang)", False, str(e))

# --- Malformed JSON ---
r = s_admin.post(f"{BASE}/api/classify", data="{not valid json", headers={"Content-Type": "application/json",
                  "X-CSRF-TOKEN": s_admin.headers.get("X-CSRF-TOKEN", "")})
check("malformed JSON body returns 4xx, not 500", 400 <= r.status_code < 500, f"status={r.status_code}")

# --- Missing field ---
r = s_admin.post(f"{BASE}/api/classify", json={})
check("missing complaint_text returns 4xx, not 500", 400 <= r.status_code < 500, f"status={r.status_code}")

# --- CORS: disallowed origin ---
r = requests.options(f"{BASE}/api/health", headers={"Origin": "https://evil.example.com",
                      "Access-Control-Request-Method": "GET"})
acao = r.headers.get("Access-Control-Allow-Origin")
check("CORS does not reflect an arbitrary/untrusted Origin", acao != "https://evil.example.com", f"ACAO={acao}")

# --- IDOR: citizen A trying to read citizen B's complaint ---
import re
import subprocess

LOG_PATH = "/tmp/adv_backend.log"


def otp_login(email, name):
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/otp/request", json={"email": email})
    assert r.status_code == 200, (email, r.status_code, r.text)
    # read the dev-mode code from the server's stdout log
    out = subprocess.run(["grep", "-a", f"Sign-in code for {email}", LOG_PATH],
                          capture_output=True, text=True).stdout
    m = re.search(r"code for " + re.escape(email) + r": (\d+)", out.splitlines()[-1])
    code = m.group(1)
    r = s.post(f"{BASE}/api/auth/otp/verify", json={"email": email, "code": code, "name": name})
    assert r.status_code == 200, (email, r.status_code, r.text)
    s.headers.update({"X-CSRF-TOKEN": r.json()["csrf_token"]})
    return s, r.json()["user"]


import time as _time
_suf = int(_time.time())
citizen_a, user_a = otp_login(f"citizen.a{_suf}@nivara.test", "Citizen A Test")
citizen_b, user_b = otp_login(f"citizen.b{_suf}@nivara.test", "Citizen B Test")

# Citizen A files a complaint
r = citizen_a.post(f"{BASE}/api/classify", json={
    "complaint_text": "My neighbor threatened me with a knife during an argument over parking.",
    "station": "PS-CENTRAL",
})
check("citizen A could file a complaint", r.status_code == 200, f"status={r.status_code}")
a_complaint_id = r.json()["complaint_id"]

# Citizen B tries to read citizen A's complaint by guessing the id (IDOR probe)
r = citizen_b.get(f"{BASE}/api/complaints/{a_complaint_id}")
check("IDOR: citizen B cannot read citizen A's complaint by id",
      r.status_code == 404, f"status={r.status_code} body={r.text[:150]}")

# Citizen B tries citizen A's own complaints list endpoint semantics (should only ever see their own via /api/my/complaints)
r = citizen_b.get(f"{BASE}/api/my/complaints")
mine_ids = [c["complaint_id"] for c in r.json().get("complaints", [])]
check("IDOR: citizen B's own complaints list never includes citizen A's complaint",
      a_complaint_id not in mine_ids, f"mine_ids={mine_ids}")

print("\n--- SUMMARY ---")
passed = sum(1 for _, ok, _ in results if ok)
print(f"{passed}/{len(results)} adversarial probes passed")
for name, ok, detail in results:
    if not ok:
        print("  FAILED:", name, detail)
