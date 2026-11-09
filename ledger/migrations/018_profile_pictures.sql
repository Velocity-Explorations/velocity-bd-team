-- 018_profile_pictures: each person's profile picture (David, 9 Nov 2026), uploaded on Profile settings and shown in
-- place of their initials. The dashboard re-encodes every upload itself to a 256 by 256 WebP, which drops the file's
-- own data such as where a photo was taken, and keeps it as base64 so both dialects hold it the same way. It is kept
-- apart from profiles so that Reset to defaults leaves it, and so reading everyone's profile stays small.

CREATE TABLE IF NOT EXISTS profile_pictures (
  name          TEXT PRIMARY KEY,
  picture       TEXT NOT NULL,
  content_type  TEXT NOT NULL,
  updated_at    TEXT NOT NULL
);
