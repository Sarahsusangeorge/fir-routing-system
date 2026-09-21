-- FIR/Complaint Categorization & Intelligent Routing System
-- Schema (SQLite). Section codes are TEXT, never INTEGER: the IPC has
-- lettered subsections such as 376A and 304B which integers would corrupt.

DROP TABLE IF EXISTS complaint_events;
DROP TABLE IF EXISTS complaint_sections;
DROP TABLE IF EXISTS complaints;
DROP TABLE IF EXISTS routing_rules;
DROP TABLE IF EXISTS ipc_sections;

-- Reference data: one row per IPC section the classifier can predict.
CREATE TABLE ipc_sections (
    code                 TEXT PRIMARY KEY,
    title                TEXT    NOT NULL,
    cognizable           INTEGER NOT NULL,   -- 1 = yes, 0 = no
    bailable             INTEGER NOT NULL,   -- 1 = yes, 0 = no
    max_punishment_years REAL,               -- NULL = life or death
    severity_weight      REAL    NOT NULL    -- 1..10, see seed.sql for rubric
);

-- Which police unit handles which section. Lower precedence wins when a
-- complaint matches several sections.
CREATE TABLE routing_rules (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    section_code TEXT NOT NULL REFERENCES ipc_sections(code),
    unit         TEXT NOT NULL,
    precedence   INTEGER NOT NULL
);

CREATE INDEX idx_routing_section ON routing_rules(section_code);

-- One row per submitted complaint.
CREATE TABLE complaints (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_text TEXT NOT NULL,
    received_at    TEXT NOT NULL DEFAULT (datetime('now')),
    priority_level TEXT,
    priority_score REAL,
    routed_unit    TEXT,
    routing_reason TEXT,
    explanation    TEXT,              -- JSON array of {token, weight}
    status         TEXT NOT NULL DEFAULT 'New',
    -- Who filed it: 'citizen' through the portal, or 'officer' at the station.
    source                 TEXT NOT NULL DEFAULT 'officer',
    filed_by               INTEGER REFERENCES users(id),
    -- Officer review. original_unit is set only when routing is overridden.
    reviewed_by            INTEGER REFERENCES users(id),
    reviewed_at            TEXT,
    officer_note           TEXT,
    original_unit          TEXT,
    override_reason        TEXT,
    -- BNSS s.173: information given electronically is taken on record once
    -- the informant signs it within three days.
    signature_confirmed_at TEXT,
    signature_method       TEXT CHECK (signature_method IN ('digital', 'in_person')),
    signature_evidence     TEXT,       -- how the signature was verified
    -- Station handling the complaint.
    station                TEXT,
    -- The investigating officer the complaint is allocated to.
    assigned_to            INTEGER REFERENCES users(id),
    assigned_at            TEXT
);

CREATE INDEX idx_complaints_filed_by ON complaints(filed_by);
CREATE INDEX idx_complaints_unit ON complaints(routed_unit);
CREATE INDEX idx_complaints_assigned ON complaints(assigned_to, status);

-- Predicted sections for each complaint (multi-label, hence a separate table).
CREATE TABLE complaint_sections (
    complaint_id INTEGER NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
    section_code TEXT    NOT NULL,
    confidence   REAL    NOT NULL,
    PRIMARY KEY (complaint_id, section_code)
);

-- Audit trail: one row per action taken on a complaint (NFR4).
CREATE TABLE complaint_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id INTEGER NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
    actor_id     INTEGER REFERENCES users(id),
    action       TEXT NOT NULL,     -- filed, assigned, status_changed, rerouted,
                                    -- signature_confirmed, note_added, diary_entry
    detail       TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_events_complaint ON complaint_events(complaint_id);
