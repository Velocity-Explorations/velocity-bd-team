# Status

Kept by the Coordinator. Read before starting work; update in your PR if your change affects it.

## Live

- Ledger (Phase 0), migration 001_initial applied to the hosted Supabase Postgres on
  2026-10-16. Tables: calls, proposals, runs, schema_migrations. `python -m ledger.migrate`
  is a no-op until a new migration lands. Connect through the Session pooler URL (the
  direct URL is IPv6-only and unreachable from David's network).

## In progress

- Phase 2 (Vulcan SOF login): working as of 2026-10-16. Username, password, then the emailed
  code read over Gmail IMAP (VELOCITY_GMAIL_APP_USERNAME + VELOCITY_GMAIL_APP_PASSWORD; gog CLI
  is used instead when installed). Calls listing reachable, 120 call links seen.
- Phase 3 (session persistence): cookies saved to data/vulcan_cookies.json after each successful
  login and restored first on the next run; verified 2026-10-16. Phase 4 scrapes the listing.

## Known breakages
