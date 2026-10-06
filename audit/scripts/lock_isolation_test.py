"""Minimal, Flask-free check: does BEGIN IMMEDIATE on connection 2 actually
block while connection 1 (a different connection, same process, different
thread) holds the write lock?"""
import os
import sqlite3
import tempfile
import threading
import time

DB = os.path.join(tempfile.mkdtemp(prefix="nivara-lock-"), "lock_test.db")

conn0 = sqlite3.connect(DB)
conn0.execute("CREATE TABLE IF NOT EXISTS t (x INTEGER)")
conn0.execute("DELETE FROM t")
conn0.commit()
conn0.close()

t0 = time.time()
log = []


def holder():
    conn = sqlite3.connect(DB)
    conn.isolation_level = None
    conn.execute("BEGIN IMMEDIATE")
    log.append(("holder acquired lock", round(time.time() - t0, 3)))
    time.sleep(1.5)
    conn.execute("INSERT INTO t VALUES (1)")
    conn.execute("COMMIT")
    log.append(("holder committed", round(time.time() - t0, 3)))
    conn.close()


def contender():
    time.sleep(0.2)  # ensure holder goes first
    conn = sqlite3.connect(DB)  # default timeout=5.0
    conn.isolation_level = None
    log.append(("contender calling BEGIN IMMEDIATE", round(time.time() - t0, 3)))
    conn.execute("BEGIN IMMEDIATE")
    log.append(("contender acquired lock", round(time.time() - t0, 3)))
    conn.execute("COMMIT")
    conn.close()


th1 = threading.Thread(target=holder)
th2 = threading.Thread(target=contender)
th1.start()
th2.start()
th1.join()
th2.join()

print("Timeline:")
for entry in log:
    print(" ", entry)

gap = None
for i, (name, t) in enumerate(log):
    if name == "contender calling BEGIN IMMEDIATE":
        call_t = t
    if name == "contender acquired lock":
        gap = t - call_t

print(f"\nContender waited {gap:.3f}s between calling BEGIN IMMEDIATE and acquiring it.")
print("EXPECTED if locking works: >= ~1.3s (it had to wait for holder's 1.5s sleep + commit).")
print("If locking is broken: ~0s (acquired immediately despite holder still sleeping).")
