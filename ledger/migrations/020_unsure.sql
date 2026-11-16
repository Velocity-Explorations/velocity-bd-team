-- 020_unsure: Unsure, a person's decision that holds a call for the team to settle (David, 16 Nov 2026). It is a vote
-- in decisions only: calls.human_status never takes it, so the call keeps no team decision and lists under Calls'
-- Unsure view until someone decides it, and the judges are scored against nobody's Unsure. Only the check on
-- decisions.status changes. Postgres replaces the check in place. SQLite cannot change a check, so it moves the table
-- aside, creates it again with the wider check, copies every row back and drops the old copy (SQLite holds only test
-- and trial ledgers).

@@POSTGRES@@ ALTER TABLE decisions DROP CONSTRAINT IF EXISTS decisions_status_check;
@@POSTGRES@@ ALTER TABLE decisions ADD CONSTRAINT decisions_status_check
  CHECK (status IN ('pursue', 'not_relevant', 'submitted', 'dismissed', 'unsure'));

@@SQLITE@@ ALTER TABLE decisions RENAME TO decisions_019;
@@SQLITE@@ CREATE TABLE decisions (
  id          INTEGER PRIMARY KEY @@AUTOINCREMENT@@,
  call_id     TEXT NOT NULL REFERENCES calls (id),
  decided_by  TEXT NOT NULL,
  status      TEXT NOT NULL CHECK (status IN ('pursue', 'not_relevant', 'submitted', 'dismissed', 'unsure')),
  note        TEXT,
  decided_at  TEXT NOT NULL
);
@@SQLITE@@ INSERT INTO decisions SELECT * FROM decisions_019;
@@SQLITE@@ DROP TABLE decisions_019;
@@SQLITE@@ CREATE INDEX IF NOT EXISTS idx_decisions_call ON decisions (call_id, id);
