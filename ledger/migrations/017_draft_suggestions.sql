-- 017_draft_suggestions: what Start the draft suggests (David, 7 Nov 2026). The dialog's Suggest button writes a request
-- (queued); run.py --assistant has Claude, the Writer's model, read the call, Velocity's facts, the Proposal Register
-- and the library's list (drafting/suggest.py), and writes the suggestion: the format, how to approve, a direction and
-- the past work to build on (done, or failed with the reason). The newest done row for a call fills the dialog.

CREATE TABLE IF NOT EXISTS draft_suggestions (
  id           INTEGER PRIMARY KEY @@AUTOINCREMENT@@,
  call_id      TEXT NOT NULL,
  asked_by     TEXT NOT NULL,
  state        TEXT NOT NULL DEFAULT 'queued' CHECK (state IN ('queued', 'working', 'done', 'failed')),
  suggestion   TEXT,
  note         TEXT,
  model        TEXT,
  cost_usd     REAL,
  asked_at     TEXT NOT NULL,
  started_at   TEXT,
  answered_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_draft_suggestions_state ON draft_suggestions (state, id);
CREATE INDEX IF NOT EXISTS idx_draft_suggestions_call ON draft_suggestions (call_id, id);
