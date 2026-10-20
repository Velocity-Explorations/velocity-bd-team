-- 004_decisions: every triage decision, kept per person, so several people can give feedback
-- and the judges can be scored against each of them. calls.human_status stays the team's
-- current decision (the latest one); this table keeps all of them, oldest first. Decisions
-- made before this migration are copied in from calls.

CREATE TABLE IF NOT EXISTS decisions (
  id          INTEGER PRIMARY KEY @@AUTOINCREMENT@@,
  call_id     TEXT NOT NULL REFERENCES calls (id),
  decided_by  TEXT NOT NULL,
  status      TEXT NOT NULL CHECK (status IN ('pursue', 'not_relevant', 'submitted', 'dismissed')),
  note        TEXT,
  decided_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_decisions_call ON decisions (call_id, id);

INSERT INTO decisions (call_id, decided_by, status, decided_at)
SELECT id, COALESCE(human_by, 'unknown'), human_status, COALESCE(human_at, updated_at)
FROM calls
WHERE human_status IN ('pursue', 'not_relevant', 'submitted', 'dismissed');
