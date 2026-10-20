-- 003_judgments: each judge's verdict on each call, so the judges can be compared.
-- The Claude review still writes calls.ai_verdict, the verdict that decides what is posted;
-- it also writes a row here, as does every other judge (Grok, as the portal's analyst). A
-- newer row for the same call and judge supersedes the older one, which stays as history.
-- Review errors are not judgments and are never written here.

CREATE TABLE IF NOT EXISTS judgments (
  id         INTEGER PRIMARY KEY @@AUTOINCREMENT@@,
  call_id    TEXT NOT NULL REFERENCES calls (id),
  judge      TEXT NOT NULL,
  model      TEXT NOT NULL,
  verdict    TEXT NOT NULL CHECK (verdict IN ('yes', 'maybe', 'no')),
  reasoning  TEXT,
  rated_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_judgments_call ON judgments (call_id, judge, id);
