-- Schema definitions for student_club
-- Auto-extracted from sources/student_club/postgres.sh

-- Table: budget
CREATE TABLE IF NOT EXISTS budget (
    budget_id     TEXT PRIMARY KEY,
    category      TEXT,
    spent         REAL,
    remaining     REAL,
    amount        INTEGER,
    event_status  TEXT,
    link_to_event TEXT
);

-- Table: expense
CREATE TABLE IF NOT EXISTS expense (
    expense_id          TEXT PRIMARY KEY,
    expense_description TEXT,
    expense_date        DATE,
    cost                REAL,
    approved            TEXT,
    link_to_member      TEXT,
    link_to_budget      TEXT
);

-- Table: income
CREATE TABLE IF NOT EXISTS income (
    income_id      TEXT PRIMARY KEY,
    date_received  DATE,
    amount         INTEGER,
    source         TEXT,
    notes          TEXT,
    link_to_member TEXT
);

