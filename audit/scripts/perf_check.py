"""
Latency measurements for NIVARA (local, synthetic data only).

Part A: HTTP latency of read endpoints against a running API
        (default http://localhost:5001), with concurrent clients.
Part B: in-process latency of the full filing pipeline
        (classify -> score -> route -> save -> allocate) on an isolated
        temporary database, bypassing HTTP and rate limits.

Usage (from the repository root, API running on NIVARA_URL):
    backend/venv/bin/python audit/scripts/perf_check.py

These are local development-machine numbers on the Flask development
server and SQLite. They are not production performance guarantees.
"""

import http.cookiejar
import json
import os
import shutil
import statistics
import sys
import tempfile
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

URL = os.environ.get("NIVARA_URL", "http://localhost:5001")
REQUESTS_PER_ENDPOINT = int(os.environ.get("PERF_REQUESTS", "300"))
CONCURRENCY = int(os.environ.get("PERF_CONCURRENCY", "8"))


def pct(values, p):
    values = sorted(values)
    k = max(0, min(len(values) - 1, round(p / 100 * (len(values) - 1))))
    return values[k]


def summary(name, ms, errors):
    return (f"{name:<34} n={len(ms):<4} errors={errors:<3} "
            f"p50={pct(ms, 50):7.1f} ms  p95={pct(ms, 95):7.1f} ms  p99={pct(ms, 99):7.1f} ms  "
            f"mean={statistics.mean(ms):7.1f} ms")


def login(username, password):
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    req = urllib.request.Request(f"{URL}/api/auth/login", method="POST",
                                 data=json.dumps({"username": username, "password": password}).encode(),
                                 headers={"Content-Type": "application/json"})
    with opener.open(req, timeout=10) as r:
        assert r.status == 200
    return opener


def part_a():
    print(f"Part A: HTTP read latency against {URL} "
          f"({REQUESTS_PER_ENDPOINT} requests per endpoint, {CONCURRENCY} concurrent clients)")
    opener = login("kavya.nair", "NivaraOfficer2026")  # published demo account, local only
    endpoints = ["/api/health", "/api/auth/me", "/api/complaints?limit=200", "/api/complaints/1", "/api/officers"]
    for path in endpoints:
        def one(_):
            t = time.perf_counter()
            try:
                with opener.open(f"{URL}{path}", timeout=10) as r:
                    r.read()
                    ok = r.status == 200
            except Exception:
                ok = False
            return (time.perf_counter() - t) * 1000, ok

        with ThreadPoolExecutor(CONCURRENCY) as pool:
            results = list(pool.map(one, range(REQUESTS_PER_ENDPOINT)))
        ms = [r[0] for r in results]
        print("  " + summary(f"GET {path}", ms, sum(1 for r in results if not r[1])))


def part_b():
    tmp = tempfile.mkdtemp(prefix="nivara-perf-")
    os.environ["NIVARA_DB_PATH"] = os.path.join(tmp, "perf.db")
    os.environ.setdefault("NIVARA_JWT_SECRET", "perf-" + "x" * 48)
    backend = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "backend")
    sys.path.insert(0, backend)
    import contextlib
    import io

    import seed_demo
    from app import process_complaint
    with contextlib.redirect_stdout(io.StringIO()):
        seed_demo.main()
    officer_id = 2
    narratives = [
        "Two men on a motorcycle snatched my chain near the bus stand. Report {i}.",
        "The caller posing as a bank officer cheated me and took money from my account. Report {i}.",
        "My neighbour threatened me with dire consequences over the boundary wall. Report {i}.",
        "Unknown persons stole my bicycle from outside the library last night. Report {i}.",
        "A long narrative " + "describing the sequence of events in considerable detail " * 60 + "Report {i}.",
    ]
    print("Part B: in-process filing pipeline on an isolated database (no HTTP)")
    for template in narratives:
        ms = []
        for i in range(60):
            t = time.perf_counter()
            process_complaint(template.format(i=i), filed_by=officer_id, source="officer", station="PS-CENTRAL")
            ms.append((time.perf_counter() - t) * 1000)
        label = f"file ({len(template)} chars)"
        print("  " + summary(label, ms, 0))
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    part_a()
    part_b()
