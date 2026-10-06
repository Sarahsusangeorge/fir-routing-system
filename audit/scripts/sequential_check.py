"""Fire the same 12 requests strictly sequentially (no concurrency at all) to
see whether the occasional 2-in-a-row to the same officer is a concurrency
artifact or a property of the ranking/scoring itself."""
import sys
import sqlite3
import requests

PORT = sys.argv[1] if len(sys.argv) > 1 else "5001"
BASE = f"http://localhost:{PORT}"
SUFFIX = sys.argv[2] if len(sys.argv) > 2 else "Seq"
DB_PATH = sys.argv[3] if len(sys.argv) > 3 else "fir_system.db"


def session_login(username=None, password="NivaraAdmin2026"):
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"password": password, "username": username})
    r.raise_for_status()
    s.headers.update({"X-CSRF-TOKEN": r.json()["csrf_token"]})
    return s


admin = session_login(username="admin")
staff = admin.get(f"{BASE}/api/admin/users").json()["users"]
for u in staff:
    if u.get("role") == "officer" and u.get("active"):
        admin.patch(f"{BASE}/api/admin/users/{u['id']}", json={"active": False})

conn = sqlite3.connect(DB_PATH)
conn.execute("UPDATE complaints SET routed_unit='Local Police Station' WHERE routed_unit='Cyber Cell' AND assigned_to IS NULL")
conn.commit()
conn.close()

OA, OB = f"seq{SUFFIX}1".lower(), f"seq{SUFFIX}2".lower()
for uname in (OA, OB):
    r = admin.post(f"{BASE}/api/admin/users", json={
        "username": uname, "email": f"{uname}@nivara.test", "name": uname,
        "role": "officer", "password": "RaceTest2026x",
        "unit": "Cyber Cell", "station": "PS-CYBER", "capacity": 1,
    })
    assert r.status_code == 201, r.text

filer = session_login(username="admin")
TEXT = ("The accused, posing as a bank official, obtained the complainant's "
        "account details over the telephone and withdrew money without authorization.")

results = []
for i in range(12):
    r = filer.post(f"{BASE}/api/classify", json={"complaint_text": TEXT, "station": "PS-CYBER"})
    j = r.json()
    results.append((j["assignment"]["officer_name"], j["assignment"].get("officer_id"),
                     j.get("routing", {}).get("priority_level")))

print("Sequential results:")
for r in results:
    print(" ", r)

names = [r[0] for r in results]
max_streak = streak = 1
for i in range(1, len(names)):
    if names[i] == names[i-1]:
        streak += 1
        max_streak = max(max_streak, streak)
    else:
        streak = 1
print("\nLongest consecutive-same-officer streak (sequential, no concurrency):", max_streak)
