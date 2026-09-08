"""
Database access for the FIR routing system.

SQLite is used for the Review 2 prototype: it requires no server, no
credentials and no installation, which removes an entire class of
setup failure on demo day. The schema is portable to MySQL for
deployment -- only the connection helper below would change.
"""

import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "fir_system.db")


def get_connection():
    """Open a connection with row access by column name and FKs enforced."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(force=False):
    """
    Create the schema and load seed data.

    Safe to call repeatedly: it does nothing if the database already has
    sections loaded, unless force=True (which drops everything).
    """
    fresh = force or not os.path.exists(DB_PATH)

    if not fresh:
        conn = get_connection()
        try:
            count = conn.execute("SELECT COUNT(*) FROM ipc_sections").fetchone()[0]
            if count > 0:
                conn.close()
                return False
        except sqlite3.OperationalError:
            pass  # tables missing; fall through and build them
        conn.close()

    conn = get_connection()
    for filename in ("schema.sql", "seed.sql"):
        path = os.path.join(BASE_DIR, filename)
        with open(path, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
    conn.commit()
    conn.close()
    return True


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

def get_sections_by_code(codes):
    """Return {code: sqlite3.Row} for the given section codes."""
    if not codes:
        return {}
    placeholders = ",".join("?" for _ in codes)
    conn = get_connection()
    rows = conn.execute(
        f"SELECT * FROM ipc_sections WHERE code IN ({placeholders})",
        list(codes),
    ).fetchall()
    conn.close()
    return {r["code"]: r for r in rows}


def get_routing_rules(codes):
    """Return routing rules matching any of the given section codes."""
    if not codes:
        return []
    placeholders = ",".join("?" for _ in codes)
    conn = get_connection()
    rows = conn.execute(
        f"SELECT * FROM routing_rules WHERE section_code IN ({placeholders}) "
        f"ORDER BY precedence ASC",
        list(codes),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Complaints
# ---------------------------------------------------------------------------

def save_complaint(text, sections, priority, routing):
    """
    Persist a complaint and its predicted sections in one transaction.
    Returns (complaint_id, received_at).
    """
    conn = get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO complaints
               (complaint_text, priority_level, priority_score,
                routed_unit, routing_reason)
               VALUES (?, ?, ?, ?, ?)""",
            (text, priority["level"], priority["score"],
             routing["unit"], routing["reason"]),
        )
        complaint_id = cur.lastrowid

        conn.executemany(
            """INSERT INTO complaint_sections
               (complaint_id, section_code, confidence)
               VALUES (?, ?, ?)""",
            [(complaint_id, s["code"], s["confidence"]) for s in sections],
        )
        conn.commit()

        received_at = conn.execute(
            "SELECT received_at FROM complaints WHERE id = ?", (complaint_id,)
        ).fetchone()["received_at"]
        return complaint_id, received_at
    finally:
        conn.close()


def list_complaints(limit=50):
    """Most recent complaints, highest priority first, with their sections."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM complaints
           ORDER BY CASE priority_level
                      WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END,
                    received_at DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()

    out = []
    for r in rows:
        secs = conn.execute(
            """SELECT cs.section_code AS code, cs.confidence,
                      COALESCE(s.title, '') AS title
               FROM complaint_sections cs
               LEFT JOIN ipc_sections s ON s.code = cs.section_code
               WHERE cs.complaint_id = ?
               ORDER BY cs.confidence DESC""",
            (r["id"],),
        ).fetchall()

        out.append({
            "complaint_id": r["id"],
            "complaint_text": r["complaint_text"],
            "received_at": r["received_at"],
            "status": r["status"],
            "priority": {"level": r["priority_level"], "score": r["priority_score"]},
            "routing": {"unit": r["routed_unit"], "reason": r["routing_reason"]},
            "sections": [dict(s) for s in secs],
        })
    conn.close()
    return out


def get_stats():
    """Dashboard counters."""
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
    by_priority = conn.execute(
        "SELECT priority_level AS level, COUNT(*) AS n FROM complaints "
        "GROUP BY priority_level"
    ).fetchall()
    by_unit = conn.execute(
        "SELECT routed_unit AS unit, COUNT(*) AS n FROM complaints "
        "GROUP BY routed_unit ORDER BY n DESC"
    ).fetchall()
    conn.close()
    return {
        "total_complaints": total,
        "by_priority": {r["level"]: r["n"] for r in by_priority},
        "by_unit": {r["unit"]: r["n"] for r in by_unit},
    }
