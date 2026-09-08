-- FIR/Complaint Categorization & Intelligent Routing System
-- Schema (SQLite). Section codes are TEXT, never INTEGER: the IPC has
-- lettered subsections such as 376A and 304B which integers would corrupt.

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
    status         TEXT NOT NULL DEFAULT 'New'
);

-- Predicted sections for each complaint (multi-label, hence a separate table).
CREATE TABLE complaint_sections (
    complaint_id INTEGER NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
    section_code TEXT    NOT NULL,
    confidence   REAL    NOT NULL,
    PRIMARY KEY (complaint_id, section_code)
);
