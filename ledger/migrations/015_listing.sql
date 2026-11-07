-- 015_listing: what kind of listing each call is (David, 7 Nov 2026): Call (something to respond to now), Umbrella
-- (a standing CSO, BAA or cycle whose calls come under it) or Announcement (nothing to submit yet). From the listing
-- tags (review/tags.py listing_of); NULL until someone has said, which counts as a call. The tag list's group check
-- also takes the new listing group. Postgres replaces the check in place. SQLite cannot change a check, so it moves
-- the table aside, creates it again with the wider check, copies every row back and drops the old copy (as 011 did).

ALTER TABLE calls ADD COLUMN listing TEXT;

@@POSTGRES@@ ALTER TABLE tag_list DROP CONSTRAINT IF EXISTS tag_list_tag_group_check;
@@POSTGRES@@ ALTER TABLE tag_list ADD CONSTRAINT tag_list_tag_group_check
  CHECK (tag_group IN ('type', 'work', 'customer', 'access', 'listing'));

@@SQLITE@@ ALTER TABLE tag_list RENAME TO tag_list_014;
@@SQLITE@@ CREATE TABLE tag_list (
  name        TEXT PRIMARY KEY,
  tag_group   TEXT NOT NULL CHECK (tag_group IN ('type', 'work', 'customer', 'access', 'listing')),
  covers      TEXT,
  position    INTEGER NOT NULL
);
@@SQLITE@@ INSERT INTO tag_list SELECT * FROM tag_list_014;
@@SQLITE@@ DROP TABLE tag_list_014;
