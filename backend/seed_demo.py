"""
Push realistic complaints through the pipeline so the dashboard has
history to display during the demo.

    python seed_demo.py

Written in the anonymised register the ILSI corpus uses -- named entities
are masked in that dataset, so demo text written with real names and
places would be out of distribution and would make the model look worse
than it is. Say this out loud if a panelist asks why the complaints read
oddly.

Also creates demo accounts (listed in DEMO_USERS) so every role can be shown.
Their passwords are public, so never run this against a deployed database.
"""

import sqlite3

from werkzeug.security import generate_password_hash

import db
import workflow
from app import _utc_now, process_complaint

# (email, name, role, password, unit). Citizens have no password.
# The duty officer has no unit, so they pick up cases for any unit that has
# no officer of its own.
OFFICER_PASSWORD = "NivaraOfficer2026"

# (username, email, name, role, password, unit, station, capacity).
# The duty officer has no unit, so they pick up cases for any unit with no
# officer of its own. Capacities differ so workload-based allocation is
# visible in the demo.
DEMO_USERS = [
    ("admin", "admin@nivara.test", "Demo Administrator", "admin", "NivaraAdmin2026", None, None, 10),
    ("kavya.nair", "duty.officer@nivara.test", "SI Kavya Nair", "officer", OFFICER_PASSWORD, None, "PS-CENTRAL", 12),
    ("arjun.rao", "lps.officer@nivara.test", "SI Arjun Rao", "officer", OFFICER_PASSWORD, "Local Police Station", "PS-CENTRAL", 10),
    ("meena.pillai", "lps2.officer@nivara.test", "ASI Meena Pillai", "officer", OFFICER_PASSWORD, "Local Police Station", "PS-NORTH", 6),
    ("farhan.ali", "eow.officer@nivara.test", "Inspector Farhan Ali", "officer", OFFICER_PASSWORD, "Economic Offences Wing", "PS-CENTRAL", 10),
    ("deepa.menon", "crime.officer@nivara.test", "Inspector Deepa Menon", "officer", OFFICER_PASSWORD, "Crime Branch", "PS-CENTRAL", 10),
    ("lakshmi.iyer", "wcpu.officer@nivara.test", "SI Lakshmi Iyer", "officer", OFFICER_PASSWORD, "Women & Child Protection Unit", "PS-SOUTH", 8),
    ("nikhil.das", "cyber.officer@nivara.test", "SI Nikhil Das", "officer", OFFICER_PASSWORD, "Cyber Cell", "PS-CYBER", 10),
    (None, None, "Demo Citizen", "citizen", None, None, None, None),
]

# The demo citizen signs in with this mobile number (code printed in the console).
DEMO_CITIZEN_PHONE = "+919000000001"

STATIONS = ["PS-CENTRAL", "PS-NORTH", "PS-SOUTH", "PS-CYBER"]

# The last few complaints are filed as if through the citizen portal.
CITIZEN_FILED = 4

COMPLAINTS = [
    "The complainant states that the accused fraudulently induced him to "
    "transfer a substantial sum towards a promised investment return, and "
    "subsequently became untraceable. No returns were ever credited.",

    "The deceased was stabbed to death by the accused following a prolonged "
    "dispute over ancestral property. The body was recovered the next morning "
    "from the adjoining field.",

    "The complainant states that she was continuously harassed for dowry by "
    "her husband and his relatives over a period of two years, and was "
    "subjected to cruelty and physical assault.",

    "Unknown persons entered the premises without permission during the night "
    "and stole household articles and cash kept in the almirah.",

    "The accused, posing as a bank official, obtained the complainant's "
    "account credentials over the telephone and effected unauthorised "
    "transfers from the account.",

    "The accused attacked the complainant with an iron rod causing grievous "
    "injuries including a fracture to the left arm, following an argument "
    "over parking.",

    "The accused abducted the minor from outside her school and was "
    "apprehended by local residents before leaving the locality.",

    "The complainant, employed as a cashier, alleges that the accused, being "
    "entrusted with company funds, misappropriated a portion for personal use "
    "and fabricated the accounts to conceal it.",

    "A group of men armed with weapons entered the shop, threatened the "
    "occupants and looted cash from the counter before fleeing on motorcycles.",

    "The accused forged the signature of the complainant on a valuable "
    "security and used the forged document as genuine to transfer the "
    "property.",

    "The accused threatened the complainant with dire consequences if he "
    "pursued the pending civil matter, causing him to apprehend for his "
    "safety.",

    "The accused slapped and punched the complainant during a verbal "
    "altercation at the market, causing minor injuries.",

    "The complainant alleges that the accused trespassed onto the disputed "
    "plot and erected a boundary wall without any authority.",

    "The accused, in furtherance of common intention along with his "
    "associates, waylaid the complainant and snatched his belongings while "
    "threatening him with a knife.",

    "The complainant states that the accused molested her in a public "
    "conveyance and fled when other passengers intervened.",
]


def create_demo_users():
    """Returns {username or phone: user_id} for the demo accounts."""
    ids = {}
    for username, email, name, role, password, unit, station, capacity in DEMO_USERS:
        phone = DEMO_CITIZEN_PHONE if role == "citizen" else None
        key = username or phone
        existing = (db.get_user_by_login(username=username) if username
                    else db.get_user_by_login(phone=phone))
        if existing:
            ids[key] = existing["id"]
            continue
        try:
            ids[key] = db.create_user(
                email, name, role,
                generate_password_hash(password) if password else None,
                unit=unit, phone=phone, username=username, station=station, capacity=capacity,
            )
        except sqlite3.IntegrityError:
            continue
    return ids


def progress(complaint_id, officer_id, steps):
    """Walk a demo case through the workflow as its officer would."""
    for step in steps:
        if "diary" in step:
            db.add_diary_entry(complaint_id, officer_id, step["diary"])
            continue
        c = db.get_complaint(complaint_id)
        changes, events, _ = workflow.plan_review(
            c, step, is_admin=False, known_units=[], officer_ids=set(), now=_utc_now()
        )
        db.review_complaint(complaint_id, officer_id, changes, events)


def main():
    db.init_db()
    ids = create_demo_users()
    print("Demo accounts (never use these outside a local demo):")
    for username, _email, _name, role, password, unit, station, _cap in DEMO_USERS:
        if role == "citizen":
            print(f"  {role:<8} {DEMO_CITIZEN_PHONE:<16} sign-in code, printed in the backend console")
            continue
        scope = f"  [{unit or 'general duty'}, {station or '-'}]" if role == "officer" else ""
        print(f"  {role:<8} {username:<16} password {password}{scope}")

    print(f"\nSeeding {len(COMPLAINTS)} complaints...\n")
    first_citizen = len(COMPLAINTS) - CITIZEN_FILED + 1
    results = []
    for i, text in enumerate(COMPLAINTS, 1):
        citizen = i >= first_citizen
        result = process_complaint(
            text,
            filed_by=ids.get(DEMO_CITIZEN_PHONE if citizen else "kavya.nair"),
            source="citizen" if citizen else "officer",
            station=STATIONS[i % len(STATIONS)],
        )
        results.append(result)
        codes = ", ".join(s["code"] for s in result["sections"])
        officer = result["assignment"]["officer_name"] or "unassigned"
        print(
            f"{i:>2}. [{result['priority']['level']:<6} "
            f"{result['priority']['score']:>4}]  {codes:<20} -> "
            f"{result['routing']['unit']:<30} {officer}"
        )

    # A few cases already under way, so each portal has something to show.
    walkthroughs = {
        0: [
            {"status": workflow.REGISTERED},
            {"status": workflow.UNDER_INVESTIGATION},
            {"diary": "Obtained bank statements for the account the money was sent to."},
            {"diary": "Transfer traced to a second account; notice sent to the bank to freeze it."},
        ],
        1: [
            {"status": workflow.REGISTERED},
            {"status": workflow.UNDER_INVESTIGATION},
            {"diary": "Scene visited and inquest conducted. Two witnesses examined."},
        ],
        len(COMPLAINTS) - 1: [
            {"status": workflow.UNDER_REVIEW,
             "note": "We have received your complaint. Please visit the station to sign it."},
        ],
    }
    for index, steps in walkthroughs.items():
        officer_id = results[index]["assignment"]["officer_id"]
        if officer_id:
            progress(results[index]["complaint_id"], officer_id, steps)

    print(f"\nDone. {len(COMPLAINTS)} complaints in the database.")


if __name__ == "__main__":
    main()
