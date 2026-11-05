-- 012_linear_issues: the Linear issue the pipeline opens for each call the team pursues, in the Pursuits project
-- of Velocity's Operations team (David, 4 Nov 2026), and the stage of the call it last showed: pursued, drafting,
-- submitted, result or withdrawn. The sync (linear/pursuits.py) moves an issue only when its call's stage moves
-- on, so a person may move it by hand meanwhile. One row per call: a call pursued again after its issue was
-- canceled gets a new issue, recorded in the same row.

CREATE TABLE IF NOT EXISTS linear_issues (
  call_id     TEXT PRIMARY KEY REFERENCES calls (id),
  issue_id    TEXT NOT NULL,
  identifier  TEXT NOT NULL,
  url         TEXT NOT NULL,
  stage       TEXT NOT NULL CHECK (stage IN ('pursued', 'drafting', 'submitted', 'result', 'withdrawn')),
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);
