# velocity-bd-team

Opportunity pipeline for Velocity Explorations: scan government and prime-contractor
portals (first: Vulcan SOF), filter and review the open calls for fit, surface them in
Slack, record the team's decisions, keep a corpus of past proposals, and show it all on a
dashboard.

## Layout

| Path | What it is |
|---|---|
| run.py | Pipeline entry point. `python run.py --portal vulcan_sof --dry-run` tests one portal. |
| ledger/ | The shared database: `db.py` (connections), `migrate.py` (migrations), `queries.py` (every query any component uses), `schema.sql` (current schema), `migrations/`. |
| portals/<slug>/ | One adapter per portal. |
| review/ | Per-call review, regex gate then LLM verdict. |
| slack/ | Alerts, delivery, reaction handling. |
| corpus/ | Past-proposal corpus: Drive sync, extraction, embeddings. |
| dashboard/ | Next.js triage dashboard over the ledger: review queue, all calls, runs, proposals. See docs/DASHBOARD.md. |
| docs/ | LEDGER_SCHEMA.md, DASHBOARD.md, RUNBOOK.md, OWNERS.md, STATUS.md, plans/. |
| tests/ | pytest suite, runs on SQLite. |
| data/ | Runtime files per component. Git-ignored. |
| reference/yukon/ | Read-only prior art from the retired Yukon scanner. Never imported. |

Agents working here read AGENTS.md first.

## The one rule

Components communicate only through the ledger database. There is no HTTP between them
and no shared files. A component writes what it produced to the ledger, records its run
in the `runs` table, and the next component reads from there. The schema is documented in
docs/LEDGER_SCHEMA.md well enough to build a dashboard from the document alone.

## Setup (Windows, PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set `DATABASE_URL`. Hosted Postgres (Neon or Supabase) is the real
ledger; `sqlite:///data/dev.db` works for local development. Never commit `.env` and
never print its values.

Apply the schema (safe to rerun; a second run reports nothing to do):

```powershell
python -m ledger.migrate
python -m ledger.migrate --list
```

Run the tests (they use a throwaway SQLite file, not your DATABASE_URL):

```powershell
pytest
```

## Status

Phase 0 of 9: repository and ledger. No scraping yet. See docs/STATUS.md.
