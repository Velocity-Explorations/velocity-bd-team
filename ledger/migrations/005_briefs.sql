-- 005_briefs: the Monday brief, kept per week for the dashboard. One row per portal (that
-- portal's week, as the Monday Slack summary posts it) and one row with no portal for the Top 10
-- across portals. written_by names the program or bot that wrote the row.

CREATE TABLE IF NOT EXISTS briefs (
  id          INTEGER PRIMARY KEY @@AUTOINCREMENT@@,
  week_of     TEXT NOT NULL,
  portal      TEXT,
  body        TEXT NOT NULL,
  written_by  TEXT NOT NULL,
  created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_briefs_week ON briefs (week_of, id);
