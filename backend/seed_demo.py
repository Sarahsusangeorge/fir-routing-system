"""
Push realistic complaints through the pipeline so the dashboard has
history to display during the demo.

    python seed_demo.py

Written in the anonymised register the ILSI corpus uses -- named entities
are masked in that dataset, so demo text written with real names and
places would be out of distribution and would make the model look worse
than it is. Say this out loud if a panelist asks why the complaints read
oddly.
"""

import db
from app import process_complaint

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


def main():
    db.init_db()
    print(f"Seeding {len(COMPLAINTS)} complaints...\n")
    for i, text in enumerate(COMPLAINTS, 1):
        result = process_complaint(text)
        codes = ", ".join(s["code"] for s in result["sections"])
        print(
            f"{i:>2}. [{result['priority']['level']:<6} "
            f"{result['priority']['score']:>4}]  {codes:<20} -> "
            f"{result['routing']['unit']}"
        )
    print(f"\nDone. {len(COMPLAINTS)} complaints in the database.")


if __name__ == "__main__":
    main()
