-- 002_change_requests: the assistant's approval queue (docs/ASSISTANT.md, "Approvals").
-- A propose tool records a request; a person approves or rejects it on the dashboard;
-- run.py --apply-requests carries out approved ones. Drafts wait for the Writer.
-- Statuses: proposed -> approved | rejected; approved -> applying -> applied | failed.
-- An approved request that cannot run yet stays approved with a "Waiting: ..." result.

CREATE TABLE IF NOT EXISTS change_requests (
  id             INTEGER PRIMARY KEY @@AUTOINCREMENT@@,
  kind           TEXT NOT NULL CHECK (kind IN ('keyword_change', 'rereview', 'scan', 'draft', 'fault_report')),
  portal         TEXT,
  call_id        TEXT,
  summary        TEXT NOT NULL,
  reason         TEXT,
  payload        TEXT,
  preview        TEXT,
  status         TEXT NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed', 'approved', 'rejected', 'applying', 'applied', 'failed')),
  requested_by   TEXT NOT NULL,
  requested_at   TEXT NOT NULL,
  decided_by     TEXT,
  decided_at     TEXT,
  decision_note  TEXT,
  applied_at     TEXT,
  result         TEXT,
  updated_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_change_requests_status ON change_requests (status, id);
