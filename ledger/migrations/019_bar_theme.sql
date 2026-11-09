-- 019_bar_theme: the top bar's theme each person picks on Profile settings (David, 9 Nov 2026): deep-field,
-- line-clear or ground-drift. NULL, or a value no longer offered, shows the default (dashboard/lib/barthemes.ts), so a
-- theme can be retired without another migration. Checked by the dashboard, not by the table.

ALTER TABLE profiles ADD COLUMN bar_theme TEXT;
