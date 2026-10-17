# Portal assistant

The assistant's actions, built as a toolbox in `assistant/` before any model is connected.
Each action is a plain, tested function: a model (Grok or Claude) will choose which one to
call and phrase the answer, and the function does the exact work. Facts therefore come from
the ledger and the portals' files, never from the model.

Two kinds of tool:

- **Read tools** only read. They are safe to call at any time.
- **Propose tools** only record a change request. A person approves it on the dashboard, and
  the scan machine carries it out (see "Approvals" below).

## Read tools

| Tool | What it answers |
|---|---|
| `portal_profile` | How one portal works, how to submit, its keyword settings, its calls and its last scan |
| `explain_call` | Why a call was kept or rejected, what the AI review said, what the team decided |
| `brief_call` | Deadline and days left, how to submit, required files, documents, what they want |
| `upcoming_deadlines` | Calls marked Pursue, not yet submitted, due within N days (default 14) |
| `scraper_health` | Each portal's last run, failures in a row, pages read badly, overdue scans |
| `weekly_summary` | New calls by verdict, calls closing within 14 days, decisions made |
| `preview_keyword_change` | Which stored calls a keyword change would newly keep or drop; changes nothing |
| `tuning_report` | Patterns in the team's decisions that suggest a keyword or company-profile change |

Every result is a JSON-ready dict with a `text` field in plain words.

## Try them

From the repo root, in the venv:

```powershell
python -m assistant tools
python -m assistant profile vulcan_sof
python -m assistant explain vulcan-1418c132-ffef-4e9a-a83b-c7adf5798c70
python -m assistant brief vulcan-1418c132-ffef-4e9a-a83b-c7adf5798c70
python -m assistant deadlines --days 14
python -m assistant health
python -m assistant summary --days 7
python -m assistant preview vulcan_sof --add-broad "digital twin"
python -m assistant tuning vulcan_sof
```

Add `--json` to any of them for the full result.

## Scheduled posts

| Job | When | What it posts to Slack |
|---|---|---|
| `python -m assistant remind` | Daily 08:00 | Calls marked Pursue and due within 14 days, nearest first. Nothing when none are due. |
| `python -m assistant post-summary` | Mondays 09:00 | Each portal's week: new calls, closing soon, decisions, scraper health. |
| Scraper watch, inside `run.py` | After every scan | An alert when at least 3 pages, and at least a tenth of the scan, were read badly. |

`scripts/install-schedule.ps1` registers the two jobs beside the pipeline's own tasks.

## What the tools read

- The ledger: `calls`, `runs` and, once filled, `proposals`.
- Each portal's own files, named in its `PORTAL` dict: `keywords` (its keywords.yaml),
  `how_to_submit` (one line) and `notes` (its NOTES.md, what the assistant should know).
- Page fields a portal stores in `calls.extra`, found by suffix so every portal can use
  them: `<prefix>_objectives`, `_documents`, `_files_required`, `_tags` (lists),
  `_instructions` (text), and the flags `_closed` and `_description_fallback`.
- Deadlines as the portal writes them, such as "30 OCT 2026 : 21:59 MDT", read by
  `assistant/dates.py`.

## Connecting a model later

`assistant.tools.TOOLS` lists every tool with its name, description, permission and a JSON
schema of its parameters, the shape model APIs expect for function tools. The model gets
those definitions and the results; it never gets credentials, and read tools cannot change
anything.
