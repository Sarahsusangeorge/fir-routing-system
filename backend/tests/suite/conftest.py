"""
Shared fixtures for the NIVARA pytest suite.

Every test runs against its own copy of a freshly seeded SQLite database in
a temporary directory, with synthetic demo data only. The real
backend/fir_system.db is never touched.
"""

import contextlib
import io
import os
import re
import shutil
import sys
import tempfile

_TMP = tempfile.mkdtemp(prefix="nivara-tests-")
_DB = os.path.join(_TMP, "test.db")
_TEMPLATE = os.path.join(_TMP, "template.db")

os.environ["NIVARA_DB_PATH"] = _DB
os.environ["NIVARA_JWT_SECRET"] = "test-secret-" + "x" * 48
os.environ.setdefault("NIVARA_ENV", "development")
os.environ.pop("SMTP_HOST", None)
os.environ["SMS_PROVIDER"] = "console"

BACKEND = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BACKEND)

import pytest  # noqa: E402

import app as appmod  # noqa: E402
import auth  # noqa: E402
import db  # noqa: E402
import seed_demo  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    seed_demo.main()
shutil.copyfile(_DB, _TEMPLATE)

PW = seed_demo.OFFICER_PASSWORD
ADMIN_PW = "NivaraAdmin2026"
CITIZEN_PHONE = seed_demo.DEMO_CITIZEN_PHONE

# Synthetic complaint narratives used across tests. None describe a real person.
TEXT_THEFT = "Unknown persons stole my bicycle from outside the library on Tuesday evening."
TEXT_FRAUD = "The caller cheated me by posing as a bank officer and defrauded me of savings."
TEXT_SEXUAL = "The accused sexually assaulted the complainant at her workplace last week."


@pytest.fixture(autouse=True)
def fresh_db():
    shutil.copyfile(_TEMPLATE, _DB)
    for suffix in ("-wal", "-shm"):
        with contextlib.suppress(FileNotFoundError):
            os.remove(_DB + suffix)
    appmod.app.config["TESTING"] = True
    yield


@pytest.fixture
def otp_box(monkeypatch):
    """Captures one-time codes that development mode would print to the console."""
    box = {}

    def capture(identifier, code, how):
        box[identifier] = code

    monkeypatch.setattr(auth, "_print_code", capture)
    return box


class Client:
    """A test client that remembers its CSRF token and signed-in user."""

    def __init__(self):
        self.c = appmod.app.test_client()
        self.csrf = None
        self.user = None

    def _h(self, headers=None):
        h = dict(headers or {})
        if self.csrf and "X-CSRF-TOKEN" not in h:
            h["X-CSRF-TOKEN"] = self.csrf
        return h

    def get(self, path, **kw):
        return self.c.get(path, headers=self._h(kw.pop("headers", None)), **kw)

    def post(self, path, **kw):
        return self.c.post(path, headers=self._h(kw.pop("headers", None)), **kw)

    def patch(self, path, **kw):
        return self.c.patch(path, headers=self._h(kw.pop("headers", None)), **kw)

    def put(self, path, **kw):
        return self.c.put(path, headers=self._h(kw.pop("headers", None)), **kw)

    def delete(self, path, **kw):
        return self.c.delete(path, headers=self._h(kw.pop("headers", None)), **kw)

    def accept(self, r):
        assert r.status_code == 200, r.get_json()
        self.csrf = r.get_json()["csrf_token"]
        self.user = r.get_json()["user"]
        return self


@pytest.fixture
def anon():
    return Client()


@pytest.fixture
def staff():
    def login(username, password=PW):
        cl = Client()
        return cl.accept(cl.post("/api/auth/login", json={"username": username, "password": password}))
    return login


@pytest.fixture
def admin(staff):
    return staff("admin", ADMIN_PW)


@pytest.fixture
def citizen_login(otp_box):
    def login(phone=CITIZEN_PHONE, name="Test Citizen"):
        cl = Client()
        r = cl.post("/api/auth/otp/request", json={"channel": "sms", "identifier": phone})
        assert r.status_code == 200, r.get_json()
        norm = r.get_json()["identifier"]
        body = {"channel": "sms", "identifier": norm, "code": otp_box[norm]}
        r = cl.post("/api/auth/otp/verify", json=body)
        if r.status_code == 400 and r.get_json().get("code") == "NAME_REQUIRED":
            r = cl.post("/api/auth/otp/verify", json={**body, "name": name})
        return cl.accept(r)
    return login


@pytest.fixture
def citizen(citizen_login):
    return citizen_login()


def clear_rate_limits():
    conn = db.get_connection()
    conn.execute("DELETE FROM auth_attempts")
    conn.commit()
    conn.close()


def complaint_ids(filed_by=None):
    conn = db.get_connection()
    if filed_by is None:
        rows = conn.execute("SELECT id FROM complaints ORDER BY id").fetchall()
    else:
        rows = conn.execute("SELECT id FROM complaints WHERE filed_by = ? ORDER BY id", (filed_by,)).fetchall()
    conn.close()
    return [r["id"] for r in rows]


def code_digits(s):
    return re.sub(r"\D", "", s)
