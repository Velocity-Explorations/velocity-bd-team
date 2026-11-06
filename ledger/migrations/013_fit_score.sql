-- 013_fit_score: the fit score (PRO-487). Each judge names the one work tag that is most of what the buyer wants
-- (judgments.main_work); the team rates each tag, keyword and NAICS code on the Call Fit Ratings page (fit_ratings,
-- loaded by run.py --load-fit-ratings, kept here and out of the public repo); review/fit.py turns those into each
-- call's score, band and reasons (calls.fit_score, fit_band, fit_why).

ALTER TABLE judgments ADD COLUMN main_work TEXT;

ALTER TABLE calls ADD COLUMN fit_score INTEGER;
ALTER TABLE calls ADD COLUMN fit_band TEXT;
ALTER TABLE calls ADD COLUMN fit_why TEXT;

CREATE TABLE IF NOT EXISTS fit_ratings (
  key         TEXT PRIMARY KEY,
  section     TEXT NOT NULL,
  name        TEXT NOT NULL,
  rating      TEXT NOT NULL CHECK (rating IN ('core', 'good', 'neutral', 'poor', 'never')),
  note        TEXT,
  loaded_at   TEXT NOT NULL
);
