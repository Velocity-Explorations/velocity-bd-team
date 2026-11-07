-- 014_fit_rating_changes: who last changed a fit rating on the dashboard's Fit ratings page; NULL for a rating loaded from
-- the first ratings page with run.py --load-fit-ratings. loaded_at is when it was loaded or last changed.

ALTER TABLE fit_ratings ADD COLUMN changed_by TEXT;
