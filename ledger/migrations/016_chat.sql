-- 016_chat: Ask Grok (David, 7 Nov 2026). Each question asked from the dashboard's panel, one row with its answer:
-- the dashboard writes the question (queued); run.py --assistant takes it (working), has Grok answer it with read-only
-- tools, and writes the answer, its sources, the tools it called and what it cost (done, or failed with the reason).
-- A person reads only their own threads.

CREATE TABLE IF NOT EXISTS chat_messages (
  id           INTEGER PRIMARY KEY @@AUTOINCREMENT@@,
  thread_id    TEXT NOT NULL,
  asked_by     TEXT NOT NULL,
  page         TEXT,
  question     TEXT NOT NULL,
  state        TEXT NOT NULL DEFAULT 'queued' CHECK (state IN ('queued', 'working', 'done', 'failed')),
  answer       TEXT,
  sources      TEXT,
  tools        TEXT,
  model        TEXT,
  cost_usd     REAL,
  asked_at     TEXT NOT NULL,
  started_at   TEXT,
  answered_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_state ON chat_messages (state, id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_thread ON chat_messages (asked_by, thread_id, id);
