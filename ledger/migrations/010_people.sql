-- 010_people: everyone who has signed in to the dashboard with their Velocity Google account (phase 11; sign-in is
-- open to every company account since 29 Oct). With DASHBOARD_USERS, the team the dashboard offers for Working with
-- and the people panels. A person keeps the name first recorded here, so their decisions stay under one name.

CREATE TABLE IF NOT EXISTS people (
  email          TEXT PRIMARY KEY,
  name           TEXT NOT NULL,
  first_seen_at  TEXT NOT NULL,
  last_seen_at   TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_people_name ON people (name);
