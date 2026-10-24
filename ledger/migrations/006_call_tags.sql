-- 006_call_tags: tags from the set list in review/tags.yaml on each call (PRO-556), kept per
-- source: "rule" for the tags a call's own data makes certain, and each judge ("claude", "grok")
-- for the tags it picked in its review. Setting a source's tags replaces that source's rows.

CREATE TABLE IF NOT EXISTS call_tags (
  id          INTEGER PRIMARY KEY @@AUTOINCREMENT@@,
  call_id     TEXT NOT NULL REFERENCES calls (id),
  tag         TEXT NOT NULL,
  source      TEXT NOT NULL CHECK (source IN ('rule', 'claude', 'grok')),
  tagged_at   TEXT NOT NULL,
  UNIQUE (call_id, tag, source)
);

CREATE INDEX IF NOT EXISTS idx_call_tags_tag ON call_tags (tag);
