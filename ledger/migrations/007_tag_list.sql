-- 007_tag_list: the tag list from review/tags.yaml, so the dashboard can group and order each
-- call's tags and offer every tag in its filter without reading another component's files
-- (PRO-557). The pipeline rewrites it whenever it tags (tag_by_rules, run.py --backfill-tags).

CREATE TABLE IF NOT EXISTS tag_list (
  name        TEXT PRIMARY KEY,
  tag_group   TEXT NOT NULL CHECK (tag_group IN ('type', 'work', 'customer', 'access')),
  covers      TEXT,
  position    INTEGER NOT NULL
);
