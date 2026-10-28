-- 008_pursuits: the proposal workspace (docs/design/redesign-plan.md, phase 1; PRO-568).
-- A pursuit is one call being drafted from the dashboard, at most one per call. Each attempt at a
-- workspace step is a row in pursuit_steps: the worker claims queued rows and saves its work, and
-- the owner approves, asks for changes (a new attempt) or stops. step_changes holds the reviewers'
-- proposed changes, pursuit_events the history, checklist_items the submission checklist.
-- drive_items indexes the shared drive for Builds on, slop_scans keeps each AI slop check, profiles
-- each person's settings, worker_jobs the worker's other jobs (a Drive refresh, Check again) and
-- workers its heartbeat. Step names, event kinds, job kinds and checklist parts are free text
-- checked in code (ledger/queries.py), so their lists can grow without a constraint change.

CREATE TABLE IF NOT EXISTS pursuits (
  id                      INTEGER PRIMARY KEY @@AUTOINCREMENT@@,
  call_id                 TEXT NOT NULL REFERENCES calls (id),
  owner                   TEXT NOT NULL,
  collaborators           TEXT,
  format                  TEXT,
  approval_mode           TEXT NOT NULL DEFAULT 'every_step' CHECK (approval_mode IN ('every_step', 'key_gates')),
  direction               TEXT,
  builds_on               TEXT,
  drive_folder_id         TEXT,
  drive_folder_name       TEXT,
  current_step            TEXT NOT NULL,
  state                   TEXT NOT NULL DEFAULT 'working' CHECK (state IN ('working', 'no_go', 'submitted', 'closed')),
  target_dates            TEXT,
  cost_usd                REAL NOT NULL DEFAULT 0,
  budget_usd              REAL NOT NULL DEFAULT 200,
  submitted_at            TEXT,
  submitted_by            TEXT,
  confirmation_number     TEXT,
  result_expected_by      TEXT,
  result_expected_source  TEXT,
  result                  TEXT CHECK (result IS NULL OR result IN ('won', 'lost', 'withdrawn', 'cancelled_by_agency')),
  result_at               TEXT,
  result_by               TEXT,
  debrief                 TEXT,
  next_time               TEXT,
  submission_id           TEXT,
  created_at              TEXT NOT NULL,
  updated_at              TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_pursuits_call ON pursuits (call_id);

CREATE TABLE IF NOT EXISTS pursuit_steps (
  id             INTEGER PRIMARY KEY @@AUTOINCREMENT@@,
  pursuit_id     INTEGER NOT NULL REFERENCES pursuits (id),
  step           TEXT NOT NULL,
  attempt        INTEGER NOT NULL DEFAULT 1,
  state          TEXT NOT NULL DEFAULT 'queued' CHECK (state IN ('queued', 'working', 'ready', 'approved', 'changes_asked', 'failed', 'blocked', 'stopped', 'skipped')),
  requested_by   TEXT NOT NULL,
  request_note   TEXT,
  summary        TEXT,
  files          TEXT,
  content        TEXT,
  task_states    TEXT,
  error          TEXT,
  cost_usd       REAL NOT NULL DEFAULT 0,
  decision       TEXT,
  decided_by     TEXT,
  decided_at     TEXT,
  decision_note  TEXT,
  notified_at    TEXT,
  queued_at      TEXT NOT NULL,
  started_at     TEXT,
  finished_at    TEXT,
  updated_at     TEXT NOT NULL,
  UNIQUE (pursuit_id, step, attempt)
);

CREATE INDEX IF NOT EXISTS idx_pursuit_steps_state ON pursuit_steps (state, id);

CREATE TABLE IF NOT EXISTS step_changes (
  id           INTEGER PRIMARY KEY @@AUTOINCREMENT@@,
  step_id      INTEGER NOT NULL REFERENCES pursuit_steps (id),
  reviewer     TEXT NOT NULL,
  section      TEXT,
  before_text  TEXT,
  after_text   TEXT,
  reason       TEXT,
  state        TEXT NOT NULL DEFAULT 'proposed' CHECK (state IN ('proposed', 'accepted', 'rejected', 'edited')),
  edited_text  TEXT,
  decided_by   TEXT,
  decided_at   TEXT,
  created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_step_changes_step ON step_changes (step_id, id);

CREATE TABLE IF NOT EXISTS pursuit_events (
  id          INTEGER PRIMARY KEY @@AUTOINCREMENT@@,
  pursuit_id  INTEGER NOT NULL REFERENCES pursuits (id),
  step_id     INTEGER REFERENCES pursuit_steps (id),
  at          TEXT NOT NULL,
  who         TEXT NOT NULL,
  kind        TEXT NOT NULL,
  text        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pursuit_events_pursuit ON pursuit_events (pursuit_id, id);

CREATE TABLE IF NOT EXISTS checklist_items (
  id          INTEGER PRIMARY KEY @@AUTOINCREMENT@@,
  pursuit_id  INTEGER NOT NULL REFERENCES pursuits (id),
  part        TEXT NOT NULL,
  position    INTEGER NOT NULL,
  text        TEXT NOT NULL,
  source      TEXT,
  owner       TEXT,
  due_date    TEXT,
  origin      TEXT NOT NULL,
  done        INTEGER NOT NULL DEFAULT 0,
  done_by     TEXT,
  done_at     TEXT,
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_checklist_items_pursuit ON checklist_items (pursuit_id, position);

CREATE TABLE IF NOT EXISTS drive_items (
  id           TEXT PRIMARY KEY,
  name         TEXT NOT NULL,
  mime         TEXT,
  path         TEXT,
  parent_id    TEXT,
  web_link     TEXT,
  modified_at  TEXT,
  indexed_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_drive_items_parent ON drive_items (parent_id);

CREATE TABLE IF NOT EXISTS slop_scans (
  id             INTEGER PRIMARY KEY @@AUTOINCREMENT@@,
  pursuit_id     INTEGER NOT NULL REFERENCES pursuits (id),
  step_id        INTEGER REFERENCES pursuit_steps (id),
  draft_file_id  TEXT,
  draft_name     TEXT,
  scanned_at     TEXT NOT NULL,
  words          INTEGER,
  band           TEXT,
  confidence     TEXT,
  points         REAL,
  provisional    INTEGER NOT NULL DEFAULT 1,
  ready          INTEGER NOT NULL DEFAULT 0,
  verdict        TEXT NOT NULL,
  fixed_count    INTEGER NOT NULL DEFAULT 0,
  result_json    TEXT NOT NULL,
  text_lines     TEXT
);

CREATE INDEX IF NOT EXISTS idx_slop_scans_pursuit ON slop_scans (pursuit_id, id);

CREATE TABLE IF NOT EXISTS profiles (
  name             TEXT PRIMARY KEY,
  display_name     TEXT,
  initials         TEXT,
  opens            TEXT NOT NULL DEFAULT 'home' CHECK (opens IN ('home', 'calls')),
  default_filters  TEXT,
  time_zone        TEXT,
  updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS worker_jobs (
  id            INTEGER PRIMARY KEY @@AUTOINCREMENT@@,
  kind          TEXT NOT NULL,
  pursuit_id    INTEGER REFERENCES pursuits (id),
  payload       TEXT,
  state         TEXT NOT NULL DEFAULT 'queued' CHECK (state IN ('queued', 'working', 'done', 'failed')),
  requested_by  TEXT NOT NULL,
  requested_at  TEXT NOT NULL,
  started_at    TEXT,
  finished_at   TEXT,
  result        TEXT,
  updated_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_worker_jobs_state ON worker_jobs (state, id);

CREATE TABLE IF NOT EXISTS workers (
  name        TEXT PRIMARY KEY,
  started_at  TEXT NOT NULL,
  seen_at     TEXT NOT NULL,
  state       TEXT NOT NULL CHECK (state IN ('idle', 'working', 'stopped')),
  doing       TEXT
);
