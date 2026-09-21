-- Authentication tables for NIVARA.
--
-- Kept separate from schema.sql on purpose: schema.sql drops and rebuilds
-- the complaint data whenever the demo database is reset, but user accounts
-- should survive a reset. Everything here uses IF NOT EXISTS, so this file
-- is safe to run on every startup. Databases created before a column was
-- added are upgraded in db._migrate().

-- One row per account.
--   Citizens sign in with a one-time code sent to their email or mobile
--   number, and have no password. email/phone hold only verified sign-in
--   addresses; anything a citizen types in without verifying it goes in
--   contact_email/contact_phone, so nobody can claim someone else's number.
--   Officers and administrators sign in with email and password, and are
--   created by an administrator, never through self-registration.
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE COLLATE NOCASE,   -- staff sign-in name
    email         TEXT UNIQUE COLLATE NOCASE,
    phone         TEXT UNIQUE,         -- E.164, e.g. +919876543210
    name          TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('citizen', 'officer', 'admin')),
    password_hash TEXT,                -- NULL for citizens
    unit          TEXT,                -- officers: their unit; NULL = general duty
    station       TEXT,                -- officers: the police station they work at
    availability  TEXT NOT NULL DEFAULT 'available'
                  CHECK (availability IN ('available', 'busy', 'on_leave')),
    capacity      INTEGER NOT NULL DEFAULT 10,   -- workload the officer can carry
    contact_email TEXT,
    contact_phone TEXT,
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    last_login_at TEXT,
    CHECK (email IS NOT NULL OR phone IS NOT NULL),
    CHECK (role = 'citizen' OR (password_hash IS NOT NULL AND email IS NOT NULL))
);

-- Mobile numbers an account has used. A citizen who changes number keeps the
-- same account id, so their FIRs follow them; the old number is released and
-- no longer opens the account, so whoever is issued it next starts empty.
CREATE TABLE IF NOT EXISTS phone_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    phone      TEXT NOT NULL,
    released_at TEXT NOT NULL DEFAULT (datetime('now')),
    changed_by INTEGER REFERENCES users(id),   -- the citizen, or an admin doing recovery
    reason     TEXT
);

CREATE INDEX IF NOT EXISTS idx_phone_history_user ON phone_history(user_id);

-- Police stations complaints can be filed at.
CREATE TABLE IF NOT EXISTS stations (
    code     TEXT PRIMARY KEY,
    name     TEXT NOT NULL,
    district TEXT
);

-- One-time sign-in codes for citizens. Only a hash of the code is stored.
-- identifier is an email address or an E.164 mobile number.
CREATE TABLE IF NOT EXISTS login_codes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    identifier TEXT NOT NULL COLLATE NOCASE,
    channel    TEXT NOT NULL CHECK (channel IN ('email', 'sms')),
    code_hash  TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    attempts   INTEGER NOT NULL DEFAULT 0,
    used_at    TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_login_codes ON login_codes(identifier, created_at);

-- Rate limiting for sign-in. kind is 'login_fail' or 'code_request';
-- key is an email address, a mobile number or a client IP address.
CREATE TABLE IF NOT EXISTS auth_attempts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT NOT NULL,
    key        TEXT NOT NULL COLLATE NOCASE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_attempts_lookup ON auth_attempts(kind, key, created_at);
