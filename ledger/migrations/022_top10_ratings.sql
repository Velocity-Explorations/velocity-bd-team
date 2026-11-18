-- 022_top10_ratings: what each person thinks of each pick in a week's Top 10 (Task 5 of the 9 Nov review, 18 Nov 2026):
-- Good pick, Not a fit or Unsure, with an optional comment, kept apart from their decision on the call (decisions), so
-- someone can call a pick right for the list and still not pursue it. One row per week, call and person; rating again
-- replaces that person's row for that week's pick. Written by the dashboard from Home's Top 10; read by Automation's
-- Top 10 reviews. Nothing ranks calls by it.

CREATE TABLE IF NOT EXISTS top10_ratings (
  id         INTEGER PRIMARY KEY @@AUTOINCREMENT@@,
  week_of    TEXT NOT NULL,
  call_id    TEXT NOT NULL REFERENCES calls (id),
  rated_by   TEXT NOT NULL,
  rating     TEXT NOT NULL CHECK (rating IN ('good_pick', 'not_a_fit', 'unsure')),
  comment    TEXT,
  rated_at   TEXT NOT NULL,
  UNIQUE (week_of, call_id, rated_by)
);

CREATE INDEX IF NOT EXISTS idx_top10_ratings_week ON top10_ratings (week_of, call_id);
