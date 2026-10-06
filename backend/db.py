"""
Database access for the FIR routing system.

SQLite is used for the Review 2 prototype: it requires no server, no
credentials and no installation, which removes an entire class of
setup failure on demo day. The schema is portable to MySQL for
deployment -- only the connection helper below would change.
"""

import json
import os
import sqlite3

import workflow

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("NIVARA_DB_PATH") or os.path.join(BASE_DIR, "fir_system.db")


def get_connection():
    """Open a connection with row access by column name and FKs enforced."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(force=False):
    """
    Create the schema and load seed data, then bring older databases up to
    date with the authentication tables and complaint workflow columns.

    Safe to call repeatedly: complaint data is rebuilt only when the database
    is new or force=True. User accounts are never dropped by a rebuild.
    """
    fresh = force or not os.path.exists(DB_PATH)

    if not fresh:
        conn = get_connection()
        try:
            count = conn.execute("SELECT COUNT(*) FROM ipc_sections").fetchone()[0]
            fresh = count == 0
        except sqlite3.OperationalError:
            fresh = True  # tables missing; build them
        conn.close()

    conn = get_connection()
    try:
        _run_sql_file(conn, "schema_auth.sql")
        _upgrade_users_table(conn)
        if fresh:
            _run_sql_file(conn, "schema.sql")
            _run_sql_file(conn, "seed.sql")
        _migrate_complaints(conn)
        conn.commit()
    finally:
        conn.close()
    return fresh


def _run_sql_file(conn, filename):
    with open(os.path.join(BASE_DIR, filename), "r", encoding="utf-8") as f:
        conn.executescript(f.read())


def _columns(conn, table):
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}


def _upgrade_users_table(conn):
    """
    The first version of the users table required an email and treated phone
    as unverified contact detail. SQLite cannot change column constraints in
    place, so the table is rebuilt: existing phone numbers move to
    contact_phone, and phone becomes a verified sign-in number.
    """
    if "contact_phone" in _columns(conn, "users"):
        return
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        with open(os.path.join(BASE_DIR, "schema_auth.sql"), encoding="utf-8") as f:
            ddl = f.read()
        start = ddl.index("CREATE TABLE IF NOT EXISTS users")
        users_ddl = ddl[start:ddl.index(");", start) + 2].replace(
            "CREATE TABLE IF NOT EXISTS users", "CREATE TABLE users_v2"
        )
        conn.executescript(f"""
            BEGIN;
            {users_ddl}
            INSERT INTO users_v2 (id, email, phone, name, role, password_hash, unit,
                                  contact_email, contact_phone, active, created_at, last_login_at)
                SELECT id, email, NULL, name, role, password_hash, unit,
                       NULL, phone, active, created_at, last_login_at
                FROM users;
            DROP TABLE users;
            ALTER TABLE users_v2 RENAME TO users;
            DROP TABLE IF EXISTS email_otps;
            COMMIT;
        """)
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


# Columns added to complaints after Review 2. A database created before then
# gets them here, so nobody has to delete fir_system.db to pick up the change.
_COMPLAINT_COLUMNS = {
    "source": "TEXT NOT NULL DEFAULT 'officer'",
    "filed_by": "INTEGER REFERENCES users(id)",
    "reviewed_by": "INTEGER REFERENCES users(id)",
    "reviewed_at": "TEXT",
    "officer_note": "TEXT",
    "original_unit": "TEXT",
    "override_reason": "TEXT",
    "signature_confirmed_at": "TEXT",
    "assigned_to": "INTEGER REFERENCES users(id)",
    "assigned_at": "TEXT",
    "signature_method": "TEXT",
    "signature_evidence": "TEXT",
    "station": "TEXT",
    # Which classifier actually produced the predictions, so a later model
    # swap can be reconciled against what was decided at the time.
    "model_backend": "TEXT",
    # JSON list of reasons an officer should double-check the triage.
    "review_flags": "TEXT",
}

# Columns added to users after the first release of authentication.
_USER_EXTRA_COLUMNS = {
    "username": "TEXT",
    "station": "TEXT",
    "availability": "TEXT NOT NULL DEFAULT 'available'",
    "capacity": "INTEGER NOT NULL DEFAULT 10",
    "token_version": "INTEGER NOT NULL DEFAULT 0",
}


class Conflict(Exception):
    """The record changed after it was read; the caller's update was not applied."""


def _migrate_complaints(conn):
    users = _columns(conn, "users")
    for column, definition in _USER_EXTRA_COLUMNS.items():
        if column not in users:
            conn.execute(f"ALTER TABLE users ADD COLUMN {column} {definition}")
    if "username" not in users:
        # UNIQUE cannot be added by ALTER TABLE; a unique index does the same job.
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username)")

    if "purpose" not in _columns(conn, "login_codes"):
        conn.execute("ALTER TABLE login_codes ADD COLUMN purpose TEXT NOT NULL DEFAULT 'sign-in'")

    existing = _columns(conn, "complaints")
    for column, definition in _COMPLAINT_COLUMNS.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE complaints ADD COLUMN {column} {definition}")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS complaint_events (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id INTEGER NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
            actor_id     INTEGER REFERENCES users(id),
            action       TEXT NOT NULL,
            detail       TEXT,
            created_at   TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_events_complaint ON complaint_events(complaint_id);
        CREATE INDEX IF NOT EXISTS idx_complaints_filed_by ON complaints(filed_by);
        CREATE INDEX IF NOT EXISTS idx_complaints_unit ON complaints(routed_unit);
        CREATE INDEX IF NOT EXISTS idx_complaints_assigned ON complaints(assigned_to, status);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username);
        CREATE TABLE IF NOT EXISTS phone_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            phone       TEXT NOT NULL,
            released_at TEXT NOT NULL DEFAULT (datetime('now')),
            changed_by  INTEGER REFERENCES users(id),
            reason      TEXT
        );
        CREATE TABLE IF NOT EXISTS stations (
            code     TEXT PRIMARY KEY,
            name     TEXT NOT NULL,
            district TEXT
        );
    """)


def _placeholders(values):
    return ",".join("?" for _ in values)


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

def get_sections_by_code(codes):
    """Return {code: sqlite3.Row} for the given section codes."""
    if not codes:
        return {}
    conn = get_connection()
    rows = conn.execute(
        f"SELECT * FROM ipc_sections WHERE code IN ({_placeholders(codes)})",
        list(codes),
    ).fetchall()
    conn.close()
    return {r["code"]: r for r in rows}


def get_routing_rules(codes):
    """Return routing rules matching any of the given section codes."""
    if not codes:
        return []
    conn = get_connection()
    rows = conn.execute(
        f"SELECT * FROM routing_rules WHERE section_code IN ({_placeholders(codes)}) "
        f"ORDER BY precedence ASC",
        list(codes),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_units(default_unit):
    """Every unit a complaint can be routed to."""
    conn = get_connection()
    rows = conn.execute("SELECT DISTINCT unit FROM routing_rules ORDER BY unit").fetchall()
    conn.close()
    units = [r["unit"] for r in rows]
    if default_unit not in units:
        units.append(default_unit)
    return sorted(units)


# ---------------------------------------------------------------------------
# Complaints
# ---------------------------------------------------------------------------

def _add_event(conn, complaint_id, actor_id, action, detail):
    conn.execute(
        "INSERT INTO complaint_events (complaint_id, actor_id, action, detail) VALUES (?, ?, ?, ?)",
        (complaint_id, actor_id, action, detail),
    )


def save_complaint(text, sections, priority, routing, explanation=None,
                   filed_by=None, source="officer", station=None,
                   model_backend=None, review_flags=None):
    """
    Persist a complaint, its predicted sections and its token attributions
    in one transaction. Returns (complaint_id, received_at).
    """
    conn = get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO complaints
               (complaint_text, priority_level, priority_score,
                routed_unit, routing_reason, explanation, filed_by, source, station,
                model_backend, review_flags)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (text, priority["level"], priority["score"],
             routing["unit"], routing["reason"],
             json.dumps(explanation or []), filed_by, source, station,
             model_backend, json.dumps(review_flags or [])),
        )
        complaint_id = cur.lastrowid

        conn.executemany(
            """INSERT INTO complaint_sections
               (complaint_id, section_code, confidence)
               VALUES (?, ?, ?)""",
            [(complaint_id, s["code"], s["confidence"]) for s in sections],
        )
        _add_event(conn, complaint_id, filed_by, "filed",
                   f"Filed via {source}; routed to {routing['unit']}")
        conn.commit()

        received_at = conn.execute(
            "SELECT received_at FROM complaints WHERE id = ?", (complaint_id,)
        ).fetchone()["received_at"]
        return complaint_id, received_at
    finally:
        conn.close()


_COMPLAINT_SELECT = """
    SELECT c.*,
           datetime(c.received_at, '+3 days') AS signature_due_at,
           f.name  AS filer_name,
           COALESCE(f.email, f.contact_email) AS filer_email,
           COALESCE(f.phone, f.contact_phone) AS filer_phone,
           r.name  AS reviewer_name,
           a.name    AS officer_name,
           a.unit    AS officer_unit,
           a.station AS officer_station
    FROM complaints c
    LEFT JOIN users f ON f.id = c.filed_by
    LEFT JOIN users r ON r.id = c.reviewed_by
    LEFT JOIN users a ON a.id = c.assigned_to
"""


def _complaint_dict(conn, r):
    secs = conn.execute(
        """SELECT cs.section_code AS code, cs.confidence,
                  COALESCE(s.title, '') AS title
           FROM complaint_sections cs
           LEFT JOIN ipc_sections s ON s.code = cs.section_code
           WHERE cs.complaint_id = ?
           ORDER BY cs.confidence DESC""",
        (r["id"],),
    ).fetchall()

    try:
        explanation = json.loads(r["explanation"] or "[]")
    except (TypeError, ValueError):
        explanation = []
    try:
        flags = json.loads(r["review_flags"] or "[]")
    except (TypeError, ValueError):
        flags = []

    return {
        "complaint_id": r["id"],
        "complaint_text": r["complaint_text"],
        "received_at": r["received_at"],
        "status": r["status"],
        "priority": {"level": r["priority_level"], "score": r["priority_score"],
                     "review_required": bool(flags), "review_reasons": flags},
        "model_backend": r["model_backend"],
        "routing": {"unit": r["routed_unit"], "reason": r["routing_reason"]},
        "sections": [dict(s) for s in secs],
        "explanation": explanation,
        "source": r["source"],
        "filed_by": r["filed_by"],
        "complainant": (
            {"name": r["filer_name"], "email": r["filer_email"], "phone": r["filer_phone"]}
            if r["source"] == "citizen" and r["filer_name"] else None
        ),
        "station": r["station"],
        "assignment": {
            "officer_id": r["assigned_to"],
            "officer_name": r["officer_name"],
            "officer_unit": r["officer_unit"],
            "officer_station": r["officer_station"],
            "assigned_at": r["assigned_at"],
        },
        "review": {
            "reviewed_by": r["reviewer_name"],
            "reviewed_at": r["reviewed_at"],
            "officer_note": r["officer_note"],
            "original_unit": r["original_unit"],
            "override_reason": r["override_reason"],
            "signature_confirmed_at": r["signature_confirmed_at"],
            "signature_method": r["signature_method"],
            "signature_evidence": r["signature_evidence"],
            "signature_due_at": r["signature_due_at"] if r["source"] == "citizen" else None,
        },
    }


def list_complaints(limit=50, unit=None, filed_by=None, assigned_to=None,
                    unassigned=False, open_only=None, station=None):
    """
    Complaints, highest priority first, with their sections.

    unit:        only complaints currently routed to this unit
    filed_by:    only complaints filed by this user (a citizen's own)
    assigned_to: only complaints allocated to this officer (their caseload)
    unassigned:  only complaints with no officer
    open_only:   True for open cases, False for closed, None for both
    """
    where, params = [], []
    if unit:
        where.append("c.routed_unit = ?")
        params.append(unit)
    if station:
        where.append("c.station = ?")
        params.append(station)
    if filed_by is not None:
        where.append("c.filed_by = ?")
        params.append(filed_by)
    if assigned_to is not None:
        where.append("c.assigned_to = ?")
        params.append(assigned_to)
    if unassigned:
        where.append("c.assigned_to IS NULL")
    if open_only is not None:
        where.append(
            f"c.status {'NOT IN' if open_only else 'IN'} ({_placeholders(workflow.FINAL_STATUSES)})"
        )
        params.extend(workflow.FINAL_STATUSES)
    clause = f"WHERE {' AND '.join(where)}" if where else ""

    conn = get_connection()
    try:
        rows = conn.execute(
            f"""{_COMPLAINT_SELECT} {clause}
                ORDER BY CASE c.priority_level
                           WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END,
                         c.received_at DESC, c.id DESC
                LIMIT ?""",
            params + [limit],
        ).fetchall()
        return [_complaint_dict(conn, r) for r in rows]
    finally:
        conn.close()


def get_complaint(complaint_id):
    conn = get_connection()
    try:
        r = conn.execute(f"{_COMPLAINT_SELECT} WHERE c.id = ?", (complaint_id,)).fetchone()
        return _complaint_dict(conn, r) if r else None
    finally:
        conn.close()


_UNCHECKED = object()


def review_complaint(complaint_id, actor_id, changes, events,
                     expected_status=_UNCHECKED, expected_assignee=_UNCHECKED, mark_reviewed=True):
    """
    Apply an officer's review in one transaction.

    changes: {column: value} for the complaints row
    events:  [(action, detail), ...] written to the audit trail
    expected_status / expected_assignee: the values the caller's decision was
        based on. If the row no longer has them (someone else acted in the
        meantime), nothing is written and Conflict is raised.
    mark_reviewed: False for changes that are not an officer's review (the
        complainant signing online), so reviewed_by/at stay an officer's.
    """
    allowed = {"status", "routed_unit", "officer_note", "original_unit",
               "override_reason", "signature_confirmed_at", "signature_method",
               "signature_evidence", "assigned_to"}
    if not set(changes) <= allowed:
        raise ValueError(f"Unexpected columns: {set(changes) - allowed}")

    guard, guard_params = "", []
    if expected_status is not _UNCHECKED:
        guard += " AND status = ?"
        guard_params.append(expected_status)
    if expected_assignee is not _UNCHECKED:
        guard += " AND assigned_to IS ?"
        guard_params.append(expected_assignee)

    conn = get_connection()
    try:
        extra = ", assigned_at = datetime('now')" if "assigned_to" in changes else ""
        assignments = ", ".join(f"{col} = ?" for col in changes)
        reviewed = ", reviewed_by = ?, reviewed_at = datetime('now')" if mark_reviewed else ""
        cur = conn.execute(
            f"UPDATE complaints SET {assignments}{extra}{reviewed} WHERE id = ?{guard}",
            list(changes.values()) + ([actor_id] if mark_reviewed else []) + [complaint_id] + guard_params,
        )
        if cur.rowcount == 0:
            conn.rollback()
            raise Conflict(complaint_id)
        if "assigned_to" in changes:
            officer = conn.execute(
                "SELECT name FROM users WHERE id = ?", (changes["assigned_to"],)
            ).fetchone()
            events = list(events) + [("assigned", f"Assigned to {officer['name']}")]
        for action, detail in events:
            _add_event(conn, complaint_id, actor_id, action, detail)
        conn.commit()
    finally:
        conn.close()


def add_diary_entry(complaint_id, actor_id, entry):
    conn = get_connection()
    try:
        _add_event(conn, complaint_id, actor_id, "diary_entry", entry)
        conn.commit()
    finally:
        conn.close()


def list_events(complaint_id):
    conn = get_connection()
    rows = conn.execute(
        """SELECT e.action, e.detail, e.created_at, u.name AS actor, u.role AS actor_role
           FROM complaint_events e
           LEFT JOIN users u ON u.id = e.actor_id
           WHERE e.complaint_id = ?
           ORDER BY e.id""",
        (complaint_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats(unit=None, assigned_to=None):
    """Dashboard counters, optionally limited to one unit or one officer."""
    where, params = [], []
    if unit:
        where.append("routed_unit = ?")
        params.append(unit)
    if assigned_to is not None:
        where.append("assigned_to = ?")
        params.append(assigned_to)
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    conn = get_connection()
    total = conn.execute(f"SELECT COUNT(*) FROM complaints {clause}", params).fetchone()[0]
    by_priority = conn.execute(
        f"SELECT priority_level AS level, COUNT(*) AS n FROM complaints {clause} "
        "GROUP BY priority_level", params
    ).fetchall()
    by_unit = conn.execute(
        f"SELECT routed_unit AS unit, COUNT(*) AS n FROM complaints {clause} "
        "GROUP BY routed_unit ORDER BY n DESC", params
    ).fetchall()
    by_status = conn.execute(
        f"SELECT status, COUNT(*) AS n FROM complaints {clause} GROUP BY status", params
    ).fetchall()
    conn.close()
    return {
        "total_complaints": total,
        "by_priority": {r["level"]: r["n"] for r in by_priority},
        "by_unit": {r["unit"]: r["n"] for r in by_unit},
        "by_status": {r["status"]: r["n"] for r in by_status},
    }


# ---------------------------------------------------------------------------
# Allocation
# ---------------------------------------------------------------------------

def officer_metrics(conn=None, exclude_id=None):
    """
    Every officer with the numbers allocation uses: how many open cases they
    hold, the weighted load those represent, their capacity and availability.
    Also what the portal shows officers about each other.
    """
    close = conn is None
    conn = conn or get_connection()
    try:
        weights = " ".join(
            f"WHEN '{level}' THEN {weight}" for level, weight in workflow.PRIORITY_WEIGHT.items()
        )
        rows = conn.execute(
            f"""
            SELECT u.id, u.name, u.username, u.email, u.unit, u.station, u.availability,
                   u.capacity, u.active,
                   (SELECT COUNT(*) FROM complaints c
                     WHERE c.assigned_to = u.id
                       AND c.status NOT IN ({_placeholders(workflow.FINAL_STATUSES)})) AS open_cases,
                   (SELECT COALESCE(SUM(CASE c.priority_level {weights} ELSE 1.0 END), 0)
                      FROM complaints c
                     WHERE c.assigned_to = u.id
                       AND c.status NOT IN ({_placeholders(workflow.FINAL_STATUSES)})) AS weighted_load,
                   (SELECT MAX(c.assigned_at) FROM complaints c WHERE c.assigned_to = u.id) AS last_assigned_at
            FROM users u
            WHERE u.role = 'officer' AND u.id IS NOT ?
            ORDER BY u.name
            """,
            list(workflow.FINAL_STATUSES) * 2 + [exclude_id],
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        if close:
            conn.close()


def allocate(complaint_id, actor_id=None, exclude_id=None):
    """
    Assign the complaint to the best-fitting, least-loaded officer for its
    unit and station (see workflow.rank_officers). Returns the officer's id,
    or None if nobody is eligible.

    Reading every officer's current load and then writing the chosen one is
    two steps, so two requests arriving at the same time could both read the
    same "least loaded" officer before either write lands, and both assign
    their case to them -- overshooting that officer's capacity while a
    colleague at zero load gets nothing. BEGIN IMMEDIATE takes SQLite's
    write lock before the read, so a second concurrent call blocks until the
    first one's write has committed and then reads the updated load,
    closing the race instead of racing on a stale snapshot.
    """
    conn = get_connection()
    conn.isolation_level = None  # manage the transaction explicitly below
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT routed_unit, station FROM complaints WHERE id = ?", (complaint_id,)
        ).fetchone()
        candidates = [o for o in officer_metrics(conn, exclude_id) if o["active"]]
        ranked = workflow.rank_officers(candidates, row["routed_unit"], row["station"])
        if not ranked:
            conn.execute(
                "UPDATE complaints SET assigned_to = NULL, assigned_at = NULL WHERE id = ?",
                (complaint_id,),
            )
            _add_event(conn, complaint_id, actor_id, "assigned",
                       f"No officer available for {row['routed_unit']}; awaiting assignment")
            conn.execute("COMMIT")
            return None

        best = ranked[0]
        conn.execute(
            "UPDATE complaints SET assigned_to = ?, assigned_at = datetime('now') WHERE id = ?",
            (best["id"], complaint_id),
        )
        detail = (f"Assigned to {best['name']} "
                  f"({best['open_cases']} open cases, workload {int(best['load_ratio'] * 100)}% of capacity)")
        _add_event(conn, complaint_id, actor_id, "assigned", detail)
        conn.execute("COMMIT")
        return best["id"]
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def open_case_ids(assigned_to=None, unassigned=False):
    final = workflow.FINAL_STATUSES
    conn = get_connection()
    if unassigned:
        rows = conn.execute(
            f"SELECT id FROM complaints WHERE assigned_to IS NULL "
            f"AND status NOT IN ({_placeholders(final)}) ORDER BY received_at",
            list(final),
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT id FROM complaints WHERE assigned_to = ? "
            f"AND status NOT IN ({_placeholders(final)}) ORDER BY received_at",
            [assigned_to] + list(final),
        ).fetchall()
    conn.close()
    return [r["id"] for r in rows]


def redistribute_cases(officer_id, actor_id):
    """Move an officer's open cases to colleagues. Returns how many moved."""
    moved = 0
    for cid in open_case_ids(assigned_to=officer_id):
        allocate(cid, actor_id=actor_id, exclude_id=officer_id)
        moved += 1
    return moved


def allocate_unassigned(actor_id=None):
    """Try to place every unassigned open case. Returns how many were placed."""
    placed = 0
    for cid in open_case_ids(unassigned=True):
        conn = get_connection()
        row = conn.execute("SELECT routed_unit, station FROM complaints WHERE id = ?", (cid,)).fetchone()
        has_candidate = bool(workflow.rank_officers(
            [o for o in officer_metrics(conn) if o["active"]], row["routed_unit"], row["station"]
        ))
        conn.close()
        if has_candidate and allocate(cid, actor_id=actor_id):
            placed += 1
    return placed


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

_USER_COLUMNS = ("id, username, email, phone, name, role, unit, station, availability, "
                 "capacity, contact_email, contact_phone, active, created_at, last_login_at, token_version")


def get_user(user_id):
    conn = get_connection()
    row = conn.execute(f"SELECT {_USER_COLUMNS} FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_login(email=None, phone=None, username=None, name_or_email=None):
    """
    Includes password_hash. Use only inside the sign-in checks.

    name_or_email lets staff sign in with either their username or their
    email address, since both are unique.
    """
    conn = get_connection()
    if name_or_email is not None:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ? OR email = ?", (name_or_email, name_or_email)
        ).fetchone()
    elif username is not None:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    elif email is not None:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    else:
        row = conn.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_with_secret(email):
    return get_user_by_login(email=email)


def create_user(email, name, role, password_hash=None, unit=None, phone=None,
                contact_email=None, contact_phone=None, username=None, station=None,
                capacity=None):
    """Returns the new user's id. Raises sqlite3.IntegrityError on a duplicate email or phone."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO users (email, phone, name, role, password_hash, unit, "
            "contact_email, contact_phone, username, station, capacity) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, 10))",
            (email, phone, name, role, password_hash, unit, contact_email, contact_phone,
             username, station, capacity),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_user(user_id, **fields):
    allowed = {"name", "unit", "active", "password_hash", "contact_email", "contact_phone",
               "station", "availability", "capacity", "username"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return
    conn = get_connection()
    try:
        assignments = ", ".join(f"{k} = ?" for k in fields)
        # A new password or a change of active status ends every existing
        # session, so a stolen token cannot outlive a reset or a reactivation.
        revoke = ", token_version = token_version + 1" if {"password_hash", "active"} & set(fields) else ""
        conn.execute(f"UPDATE users SET {assignments}{revoke} WHERE id = ?",
                     list(fields.values()) + [user_id])
        conn.commit()
    finally:
        conn.close()


def touch_last_login(user_id):
    conn = get_connection()
    conn.execute("UPDATE users SET last_login_at = datetime('now') WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def list_users(roles=None):
    """Users, with each officer's count of open cases."""
    final = workflow.FINAL_STATUSES
    cols = ", ".join(f"u.{c.strip()}" for c in _USER_COLUMNS.split(","))
    sql = f"""
        SELECT {cols},
               (SELECT COUNT(*) FROM complaints c
                 WHERE c.assigned_to = u.id AND c.status NOT IN ({_placeholders(final)})) AS open_cases
        FROM users u
    """
    params = list(final)
    if roles:
        sql += f" WHERE u.role IN ({_placeholders(roles)})"
        params += list(roles)
    sql += " ORDER BY u.role, u.name"
    conn = get_connection()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def active_officer_ids():
    conn = get_connection()
    rows = conn.execute("SELECT id FROM users WHERE role = 'officer' AND active = 1").fetchall()
    conn.close()
    return {r["id"] for r in rows}


def count_active_admins():
    conn = get_connection()
    n = conn.execute(
        "SELECT COUNT(*) FROM users WHERE role = 'admin' AND active = 1"
    ).fetchone()[0]
    conn.close()
    return n


# ---------------------------------------------------------------------------
# One-time codes and rate limiting
# ---------------------------------------------------------------------------

def store_login_code(identifier, channel, code_hash, ttl_minutes, purpose="sign-in"):
    conn = get_connection()
    try:
        # A new code replaces any earlier unused one for the same purpose.
        conn.execute(
            "UPDATE login_codes SET used_at = datetime('now') "
            "WHERE identifier = ? AND purpose = ? AND used_at IS NULL", (identifier, purpose)
        )
        conn.execute(
            "INSERT INTO login_codes (identifier, channel, purpose, code_hash, expires_at) "
            "VALUES (?, ?, ?, ?, datetime('now', ?))",
            (identifier, channel, purpose, code_hash, f"+{int(ttl_minutes)} minutes"),
        )
        conn.commit()
    finally:
        conn.close()


def get_active_login_code(identifier, purpose="sign-in"):
    conn = get_connection()
    row = conn.execute(
        """SELECT * FROM login_codes
           WHERE identifier = ? AND purpose = ? AND used_at IS NULL AND expires_at > datetime('now')
           ORDER BY id DESC LIMIT 1""",
        (identifier, purpose),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Session revocation
# ---------------------------------------------------------------------------

def bump_token_version(user_id):
    conn = get_connection()
    try:
        conn.execute("UPDATE users SET token_version = token_version + 1 WHERE id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()


def revoke_token(jti, exp_epoch):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM revoked_tokens WHERE expires_at < datetime('now')")
        conn.execute(
            "INSERT OR IGNORE INTO revoked_tokens (jti, expires_at) VALUES (?, datetime(?, 'unixepoch'))",
            (jti, int(exp_epoch or 0)),
        )
        conn.commit()
    finally:
        conn.close()


def is_token_revoked(jti):
    if not jti:
        return True
    conn = get_connection()
    row = conn.execute("SELECT 1 FROM revoked_tokens WHERE jti = ?", (jti,)).fetchone()
    conn.close()
    return row is not None


def find_recent_duplicate(filed_by, text, minutes):
    """The id of an identical complaint the same person filed in the last `minutes`, if any."""
    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM complaints WHERE filed_by = ? AND complaint_text = ? "
        "AND received_at > datetime('now', ?) ORDER BY id DESC LIMIT 1",
        (filed_by, text, f"-{int(minutes)} minutes"),
    ).fetchone()
    conn.close()
    return row["id"] if row else None


def bump_code_attempts(code_id):
    conn = get_connection()
    conn.execute("UPDATE login_codes SET attempts = attempts + 1 WHERE id = ?", (code_id,))
    conn.commit()
    conn.close()


def consume_login_code(code_id):
    conn = get_connection()
    conn.execute("UPDATE login_codes SET used_at = datetime('now') WHERE id = ?", (code_id,))
    conn.commit()
    conn.close()


def record_attempt(kind, key):
    conn = get_connection()
    conn.execute("INSERT INTO auth_attempts (kind, key) VALUES (?, ?)", (kind, key))
    # Keep the table small: anything older than a day is irrelevant.
    conn.execute("DELETE FROM auth_attempts WHERE created_at < datetime('now', '-1 day')")
    conn.commit()
    conn.close()


def count_attempts(kind, key, window_seconds):
    conn = get_connection()
    n = conn.execute(
        "SELECT COUNT(*) FROM auth_attempts WHERE kind = ? AND key = ? "
        "AND created_at > datetime('now', ?)",
        (kind, key, f"-{int(window_seconds)} seconds"),
    ).fetchone()[0]
    conn.close()
    return n


def clear_attempts(kind, key):
    conn = get_connection()
    conn.execute("DELETE FROM auth_attempts WHERE kind = ? AND key = ?", (kind, key))
    conn.commit()
    conn.close()


def change_phone(user_id, new_phone, changed_by, reason):
    """
    Move an account to a new mobile number.

    The account id never changes, so every complaint filed under the old
    number stays with the citizen. The old number is released into
    phone_history and no longer opens the account, so the next person to be
    issued that number starts with a new, empty account.

    Raises sqlite3.IntegrityError if the number already belongs to someone.
    """
    conn = get_connection()
    try:
        old = conn.execute("SELECT phone FROM users WHERE id = ?", (user_id,)).fetchone()["phone"]
        # Whoever holds the old SIM may still have a session open; end it.
        conn.execute("UPDATE users SET phone = ?, token_version = token_version + 1 WHERE id = ?",
                     (new_phone, user_id))
        if old:
            conn.execute(
                "INSERT INTO phone_history (user_id, phone, changed_by, reason) VALUES (?, ?, ?, ?)",
                (user_id, old, changed_by, reason),
            )
        conn.commit()
        return old
    finally:
        conn.close()


def list_phone_history(user_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT phone, released_at, reason FROM phone_history WHERE user_id = ? ORDER BY id DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_stations():
    conn = get_connection()
    rows = conn.execute("SELECT code, name, district FROM stations ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def station_exists(code):
    conn = get_connection()
    row = conn.execute("SELECT 1 FROM stations WHERE code = ?", (code,)).fetchone()
    conn.close()
    return row is not None
