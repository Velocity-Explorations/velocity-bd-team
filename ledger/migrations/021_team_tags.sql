-- 021_team_tags: a person's own tag on a call, source "team" (David, 16 Nov 2026). For now only the listing kind: the
-- Decide menu's "Umbrella announcement only" tags a call Umbrella, and "This is a call" puts it back. review/tags.py
-- listing_of reads the team's tag before the rule's and the judges', so the next run keeps it. Only the check on
-- call_tags.source changes. Postgres replaces the check in place. SQLite cannot change a check, so it moves the table
-- aside, creates it again with the wider check, copies every row back and drops the old copy (SQLite holds only test
-- and trial ledgers).

@@POSTGRES@@ ALTER TABLE call_tags DROP CONSTRAINT IF EXISTS call_tags_source_check;
@@POSTGRES@@ ALTER TABLE call_tags ADD CONSTRAINT call_tags_source_check
  CHECK (source IN ('rule', 'claude', 'grok', 'team'));

@@SQLITE@@ ALTER TABLE call_tags RENAME TO call_tags_020;
@@SQLITE@@ CREATE TABLE call_tags (
  id          INTEGER PRIMARY KEY @@AUTOINCREMENT@@,
  call_id     TEXT NOT NULL REFERENCES calls (id),
  tag         TEXT NOT NULL,
  source      TEXT NOT NULL CHECK (source IN ('rule', 'claude', 'grok', 'team')),
  tagged_at   TEXT NOT NULL,
  UNIQUE (call_id, tag, source)
);
@@SQLITE@@ INSERT INTO call_tags SELECT * FROM call_tags_020;
@@SQLITE@@ DROP TABLE call_tags_020;
@@SQLITE@@ CREATE INDEX IF NOT EXISTS idx_call_tags_tag ON call_tags (tag);
