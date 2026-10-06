"""
Rigorous concurrency test for backend/db.py's allocate().

Unlike the earlier race_test.py (which fired requests from N client-side
threads against the *default* single-threaded dev server -- meaning the
server itself serialized every request regardless of the client's
"concurrency", making the result inconclusive), this version:

  1. Targets a server started with threaded=True (run_threaded.py, port
     5001), so the server can genuinely execute multiple requests'
     allocate() calls at overlapping times.
  2. Uses a threading.Barrier so all N client threads release their HTTP
     request at the same instant, instead of however ThreadPoolExecutor
     happens to schedule them.
  3. Isolates exactly two equally-eligible, zero-loaded officers in one
     unit/station, with every other officer in that unit/station
     deactivated, so there is no third "fallback" to muddy the
     distribution -- a clean allocation must alternate them evenly, and
     any officer ending up over its stated capacity is unambiguous
     evidence of a lost update.

Usage:
    python race_test_barrier.py <port>
"""
import sys
import sqlite3
import threading
import concurrent.futures
import requests
from collections import Counter

PORT = sys.argv[1] if len(sys.argv) > 1 else "5001"
BASE = f"http://localhost:{PORT}"
N = 12
SUFFIX = sys.argv[2] if len(sys.argv) > 2 else "A"  # vary to get fresh usernames per run
DB_PATH = sys.argv[3] if len(sys.argv) > 3 else "fir_system.db"


def neutralize_stray_cyber_cell_complaints():
    """
    The demo seed has complaint id=5 (routed_unit='Cyber Cell', station=
    'PS-NORTH') pre-assigned to the seeded Cyber Cell officer. Deactivating
    every active officer below (to isolate our two fresh test officers)
    unassigns it via admin.py's redistribute_cases(), and once it is
    unassigned it gets auto-backfilled onto whichever test officer is
    created first (allocate_unassigned() runs on officer creation) --
    giving that officer an artificial head start before the timed batch
    even starts. Must run AFTER the deactivation loop (that's when the
    complaint actually becomes unassigned), not before.
    """
    conn = sqlite3.connect(DB_PATH)
    n = conn.execute(
        "UPDATE complaints SET routed_unit = 'Local Police Station' "
        "WHERE routed_unit = 'Cyber Cell' AND assigned_to IS NULL"
    ).rowcount
    conn.commit()
    conn.close()
    if n:
        print(f"(neutralized {n} pre-existing unassigned Cyber-Cell complaint(s) to avoid a head-start confound)")


def session_login(username=None, password="NivaraAdmin2026"):
    s = requests.Session()
    body = {"password": password, "username": username}
    r = s.post(f"{BASE}/api/auth/login", json=body)
    r.raise_for_status()
    s.headers.update({"X-CSRF-TOKEN": r.json()["csrf_token"]})
    return s, r.json()["user"]


admin, admin_user = session_login(username="admin")

# Deactivate every existing *active* officer (including unit-less "generalist"
# officers, who turn out to be fallback-eligible for any unit -- not just
# officers explicitly in Cyber Cell) so only our two fresh, zero-loaded test
# officers are eligible for the Cyber Cell / PS-CYBER routing below.
staff = admin.get(f"{BASE}/api/admin/users").json()["users"]
for u in staff:
    if u.get("role") == "officer" and u.get("active"):
        admin.patch(f"{BASE}/api/admin/users/{u['id']}", json={"active": False})

neutralize_stray_cyber_cell_complaints()

OFFICER_A = f"barrier{SUFFIX}1".lower()  # the backend lowercases usernames
OFFICER_B = f"barrier{SUFFIX}2".lower()
created = []
for uname in (OFFICER_A, OFFICER_B):
    r = admin.post(f"{BASE}/api/admin/users", json={
        "username": uname, "email": f"{uname}@nivara.test", "name": uname,
        "role": "officer", "password": "RaceTest2026x",
        "unit": "Cyber Cell", "station": "PS-CYBER", "capacity": 1,
    })
    if r.status_code != 201:
        print("setup failed:", r.status_code, r.text[:300])
        sys.exit(1)
    created.append(r.json()["user"])

print(f"Port {PORT}: created officers {[(c['id'], c['username']) for c in created]}")

filer, _ = session_login(username="admin")

TEXT = ("The accused, posing as a bank official, obtained the complainant's "
        "account details over the telephone and withdrew money without authorization.")

barrier = threading.Barrier(N)
results = [None] * N


def file_one(i):
    barrier.wait()  # all N threads unblock at (as close to) the same instant
    r = filer.post(f"{BASE}/api/classify", json={"complaint_text": TEXT, "station": "PS-CYBER"})
    if r.status_code != 200:
        return ("ERROR", r.status_code, r.text[:200])
    j = r.json()
    return (j["routing"]["unit"], j["assignment"]["officer_name"], j["assignment"]["officer_id"])


with concurrent.futures.ThreadPoolExecutor(max_workers=N) as ex:
    futures = [ex.submit(file_one, i) for i in range(N)]
    results = [f.result() for f in futures]

print(f"\n{N} barrier-synchronized concurrent /api/classify requests -> Cyber Cell / PS-CYBER")
print(f"eligible officers: {OFFICER_A} (capacity 1), {OFFICER_B} (capacity 1) only\n")
for r in results:
    print(" ", r)

counts = Counter(r[1] for r in results)
print("\nDistribution (this batch of", N, "requests only):", dict(counts))

officers_after = admin.get(f"{BASE}/api/officers?unit=Cyber Cell&station=PS-CYBER").json()["officers"]
for o in officers_after:
    if o["username"] in (OFFICER_A, OFFICER_B):
        print(f"  {o['username']}: open_cases(all-time)={o['open_cases']} capacity={o['capacity']} "
              f"load_percent={o['load_percent']}")

# Judge races by how this batch alone was distributed (ids captured in `results`,
# unaffected by any pre-existing/stray case either officer carried in from
# before the batch started), not by the live open_cases total, which can
# legitimately include a head start from an earlier unrelated assignment
# (e.g. a pre-existing unassigned complaint auto-backfilled onto whichever
# test officer was created first) and would otherwise look like a false
# capacity violation.
batch_counts = Counter(r[1] for r in results)
most, fewest = max(batch_counts.values()), min(batch_counts.values())
imbalanced = (most - fewest) > 1  # strict alternation between 2 equal officers should differ by <=1

# A correct serialized allocator, choosing the *currently* least-loaded of two
# equal-capacity officers each time, should alternate: once one officer gets a
# case its load rises above the other's, so the other is strictly preferred
# next. A run of >=2 consecutive assignments to the SAME officer (while the
# other remains equally eligible) means multiple requests read the "who's
# least loaded" state before any of their writes had landed -- i.e. a lost
# update -- even if the final totals happen to balance out over 12 requests.
names = [r[1] for r in results]
max_streak = 1
streak = 1
for i in range(1, len(names)):
    if names[i] == names[i - 1]:
        streak += 1
        max_streak = max(max_streak, streak)
    else:
        streak = 1

print("\nBatch split between the two officers:", dict(batch_counts))
print("Longest run of consecutive same-officer assignments:", max_streak)
race = imbalanced or max_streak >= 2
print("RESULT:", "RACE DETECTED (lost update)" if race else "NO RACE (strict alternation)")
