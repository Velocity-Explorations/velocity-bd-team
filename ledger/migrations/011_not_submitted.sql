-- 011_not_submitted: the Register's outcome not_submitted, for a proposal prepared but never sent in
-- (docs/LIBRARY_CONVENTIONS.md). Only the check on proposals.outcome changes: no table or column is added,
-- renamed or dropped. Postgres replaces the check in place. SQLite cannot change a check, so it moves the
-- table aside, creates it again with the wider check, copies every row back and drops the old copy
-- (SQLite holds only test and trial ledgers).

@@POSTGRES@@ ALTER TABLE proposals DROP CONSTRAINT IF EXISTS proposals_outcome_check;
@@POSTGRES@@ ALTER TABLE proposals ADD CONSTRAINT proposals_outcome_check
  CHECK (outcome IS NULL OR outcome IN ('won', 'lost', 'no_award', 'pending', 'withdrawn', 'shortlisted', 'not_submitted'));

@@SQLITE@@ ALTER TABLE proposals RENAME TO proposals_010;
@@SQLITE@@ CREATE TABLE proposals (
  submission_id     TEXT PRIMARY KEY,
  title             TEXT,
  portal            TEXT,
  agency            TEXT,
  solicitation_id   TEXT,
  type              TEXT,
  role              TEXT,
  partners          TEXT,
  submitted_date    TEXT,
  due_date          TEXT,
  requested_value   TEXT,
  outcome           TEXT CHECK (outcome IS NULL OR outcome IN ('won', 'lost', 'no_award', 'pending', 'withdrawn', 'shortlisted', 'not_submitted')),
  outcome_date      TEXT,
  award_value       TEXT,
  strength_rating   INTEGER CHECK (strength_rating IS NULL OR strength_rating BETWEEN 1 AND 5),
  strength_reason   TEXT,
  why_won_or_lost   TEXT,
  use_as_exemplar   INTEGER NOT NULL DEFAULT 0,
  themes            TEXT,
  drive_link        TEXT,
  brief             TEXT,
  synced_at         TEXT,
  updated_at        TEXT NOT NULL
);
@@SQLITE@@ INSERT INTO proposals SELECT * FROM proposals_010;
@@SQLITE@@ DROP TABLE proposals_010;
@@SQLITE@@ CREATE INDEX IF NOT EXISTS idx_proposals_portal_outcome ON proposals (portal, outcome);
