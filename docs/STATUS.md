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
  login and restored first on the next run; verified 2026-10-16.
- Phase 4 (Vulcan SOF scrape): `python -m portals.vulcan_sof.run_scrape` writes every listed call
  (60 on 2026-10-16, 18 open and 42 closed; closed flagged in extra.vulcan_closed) in about 170 s
  with 100% field fill.
- Phase 5 (keyword filter): `python -m portals.vulcan_sof.run_filter` (add `--all` after editing
  portals/vulcan_sof/keywords.yaml). On 2026-10-16: 60 rows, 58 kept (6 tight, 52 broad), 2 rejected.
  The `ai` substring keeps most rows in broad; the LLM review is the real gate.
- Phase 6 (LLM review): `python -m review.run_review` reviews kept, unreviewed rows of the latest run
  with claude-haiku-5-5. On 2026-10-16: 58 rows, yes 17, maybe 33, no 8, 206 s. Model failure yields
  "maybe" with a "Review error" reason, never "no".

## Known breakages
