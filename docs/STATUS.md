# Status

Kept by the Coordinator. Read before starting work; update in your PR if your change affects it.

## Live

- Ledger (Phase 0), migration 001_initial applied to the hosted Supabase Postgres on
  2026-10-16. Tables: calls, proposals, runs, schema_migrations. `python -m ledger.migrate`
  is a no-op until a new migration lands. Connect through the Session pooler URL (the
  direct URL is IPv6-only and unreachable from David's network).

## In progress

- Phase 1 (Vulcan SOF recon): Playwright 1.64 with Chromium 156 installed; headless load of the
  login page confirmed on 2026-10-16 (data/recon_login.png). Login itself is Phase 2.

## Known breakages
