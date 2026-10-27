"""
Run the decision pipeline on one complaint and print every intermediate value.

    python explain_pipeline.py                      # the built-in examples
    python explain_pipeline.py "complaint text"     # your own text

This is the pipeline described in Chapter 5 of the report, with no Flask and
no web server: classify -> score -> route -> allocate. It exists to make the
rules inspectable on a terminal, which is easier to follow in a review than
clicking through the interface, and it is also how you check a rule change
without restarting the app.

It reads the policy tables (severity weights, routing rules) from the same
database the application uses. With NIVARA_DB_PATH unset it builds a throwaway
one from schema.sql and seed.sql, so it never touches your demo data.

Set FIR_USE_MODEL=1 to run the trained DistilBERT instead of the keyword
fallback. That needs the weights in backend/model/ and torch installed; the
output says which classifier actually produced the prediction either way.
"""

import os
import sys
import tempfile

# Point at a throwaway database unless the caller named one, before importing
# db: it resolves DB_PATH at import time.
_TEMP_DB = None
if not os.environ.get("NIVARA_DB_PATH"):
    _TEMP_DB = os.path.join(tempfile.mkdtemp(prefix="nivara-explain-"), "demo.db")
    os.environ["NIVARA_DB_PATH"] = _TEMP_DB

import classifier
import db
import routing as routing_engine
import scoring
import workflow

EXAMPLES = [
    ("The deceased was stabbed to death by the accused following a prolonged "
     "dispute over ancestral property."),
    ("The complainant states that the accused fraudulently induced him to "
     "transfer a substantial sum towards a promised investment return, and "
     "subsequently became untraceable."),
    ("The accused outraged her modesty by inappropriately touching the "
     "complainant at her workplace."),
]

RULE = "-" * 72


def head(text):
    print(f"\n{text}\n{RULE}")


def explain(text, station="PS-CENTRAL"):
    print("=" * 72)
    print(f"COMPLAINT: {text[:200]}")
    print("=" * 72)

    # ---- 1. classify -------------------------------------------------
    raw, backend = classifier.predict_with_backend(text)
    head(f"1. CLASSIFY  (classifier: {backend})")
    if not raw:
        print("  no sections predicted")
        return
    # get_sections_by_code returns sqlite3.Row values, which have no .get()
    reference = {c: dict(r) for c, r in
                 db.get_sections_by_code([s["code"] for s in raw]).items()}
    for s in raw:
        ref = reference.get(s["code"], {})
        print(f"  Section {s['code']:<6} conf {float(s['confidence']):.4f}  "
              f"severity {ref.get('severity_weight', scoring.DEFAULT_SEVERITY):<5} "
              f"{ref.get('title', 'unmapped')[:40]}")

    sections = [{"code": s["code"],
                 "title": reference.get(s["code"], {}).get("title", "Unmapped section"),
                 "confidence": round(float(s["confidence"]), 4)}
                for s in raw]
    severity = {c: reference[c]["severity_weight"] for c in reference}

    # ---- 2. score ----------------------------------------------------
    head("2. SCORE  (max over sections of severity x confidence)")
    for s in sections:
        w = severity.get(s["code"], scoring.DEFAULT_SEVERITY)
        print(f"  {w} x {s['confidence']:.4f} = {w * s['confidence']:.4f}   "
              f"Section {s['code']}")
    priority = scoring.score_complaint(sections, severity)
    print(f"\n  -> score {priority['score']}  level {priority['level']}  "
          f"driver Section {priority['driver']}")
    print(f"     thresholds: High >= {scoring.HIGH_THRESHOLD}, "
          f"Medium >= {scoring.MEDIUM_THRESHOLD}")

    # ---- 3. route ----------------------------------------------------
    codes = [s["code"] for s in sections]
    rules = db.get_routing_rules(codes)
    head("3. ROUTE  (lowest precedence wins)")
    if rules:
        for r in sorted(rules, key=lambda r: r["precedence"]):
            print(f"  precedence {r['precedence']:<3} Section {r['section_code']:<6} -> {r['unit']}")
    else:
        print("  no routing rule matched")
    route = routing_engine.route_complaint(
        sections, rules, {c: reference[c]["title"] for c in reference})
    print(f"\n  -> unit {route['unit']}")
    print(f"     reason: {route['reason']}")

    # ---- 4. allocate -------------------------------------------------
    head(f"4. ALLOCATE  (score = tier + load/capacity + penalty; station {station})")
    officers = db.officer_metrics()
    ranked = workflow.rank_officers(officers, route["unit"], station)
    if not ranked:
        print("  nobody eligible; the case waits in the unassigned queue")
        return
    print(f"  {'officer':<22}{'unit':<30}{'tier':>5}{'load':>7}{'score':>8}")
    for o in ranked[:6]:
        print(f"  {o['name'][:21]:<22}{str(o['unit'] or 'general duty')[:29]:<30}"
              f"{o['tier']:>5}{o['load_ratio']:>7.3f}{o['score']:>8.3f}")
    print(f"\n  -> assigned to {ranked[0]['name']}")


# Officers for the throwaway database. init_db() seeds the policy tables but
# no staff, so without these step 4 has nobody to rank. Mirrors the demo set
# in seed_demo.py, including the unequal capacities and the specialist who
# sits at a different station, so the ranking has something to show.
DEMO_OFFICERS = [
    ("kavya@nivara.test", "SI Kavya Nair", None, "PS-CENTRAL", 12, "available"),
    ("arjun@nivara.test", "SI Arjun Rao", "Local Police Station", "PS-CENTRAL", 10, "available"),
    ("meena@nivara.test", "ASI Meena Pillai", "Local Police Station", "PS-NORTH", 6, "available"),
    ("farhan@nivara.test", "Inspector Farhan Ali", "Economic Offences Wing", "PS-CENTRAL", 10, "available"),
    ("deepa@nivara.test", "Inspector Deepa Menon", "Crime Branch", "PS-CENTRAL", 10, "busy"),
    ("lakshmi@nivara.test", "SI Lakshmi Iyer", "Women & Child Protection Unit", "PS-SOUTH", 8, "available"),
    ("nikhil@nivara.test", "SI Nikhil Das", "Cyber Cell", "PS-CYBER", 10, "available"),
]


def seed_officers():
    # Staff rows need an email and a password hash. These carry .test
    # addresses and a hash of a fresh random secret that is discarded, so the
    # rows satisfy the constraint and no one can ever sign in as them. This
    # only ever runs against the throwaway database.
    from werkzeug.security import generate_password_hash

    unusable = generate_password_hash(os.urandom(32).hex())
    conn = db.get_connection()
    try:
        if conn.execute("SELECT COUNT(*) FROM users WHERE role='officer'").fetchone()[0]:
            return
        conn.executemany(
            "INSERT INTO users (email, password_hash, name, role, unit, station, capacity, availability) "
            "VALUES (?, ?, ?, 'officer', ?, ?, ?, ?)",
            [(email, unusable, name, unit, station, cap, avail)
             for email, name, unit, station, cap, avail in DEMO_OFFICERS],
        )
        conn.commit()
    finally:
        conn.close()


def main():
    db.init_db()
    if _TEMP_DB:
        seed_officers()
        print(f"(throwaway database at {_TEMP_DB}, seeded with demo officers)")
    texts = sys.argv[1:] or EXAMPLES
    for i, text in enumerate(texts):
        if i:
            print()
        explain(text)


if __name__ == "__main__":
    main()
