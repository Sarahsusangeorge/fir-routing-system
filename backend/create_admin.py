"""
Create an administrator account.

    python create_admin.py

Administrators create officer accounts from the Staff page in the app, so
this script is only needed once, for the first administrator (or to recover
access if every administrator account is lost).
"""

import getpass
import sqlite3
import sys

from werkzeug.security import generate_password_hash

import db
from admin import password_problem
from auth import EMAIL_RE


def main():
    db.init_db()
    email = input("Admin email: ").strip().lower()
    if not EMAIL_RE.match(email):
        sys.exit("That is not a valid email address.")
    name = input("Full name: ").strip()
    if len(name) < 2:
        sys.exit("Enter a name.")

    password = getpass.getpass("Password: ")
    problem = password_problem(password)
    if problem:
        sys.exit(problem)
    if getpass.getpass("Repeat password: ") != password:
        sys.exit("Passwords do not match.")

    try:
        db.create_user(email, name, "admin", generate_password_hash(password))
    except sqlite3.IntegrityError:
        sys.exit("An account with this email already exists.")
    print(f"Administrator {email} created. Sign in from the Police staff tab.")


if __name__ == "__main__":
    main()
