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
| `list_change_requests` | Change requests, newest first, and where each stands |
| `get_change_request` | One change request in full: what it asks, its preview, the decision and the result |

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
python -m assistant requests
```

Add `--json` to any of them for the full result.

## Scheduled jobs

| Job | When | What it does |
|---|---|---|
| `python run.py --remind` | Daily 08:00 | Posts the calls marked Pursue and due within 14 days, nearest first. Posts nothing when none are due. |
| `python run.py --post-summary` | Mondays 09:00 | Posts the Monday summary to Slack: for each portal, new calls, open calls waiting for a decision, the top picks (yes before maybe, then nearest deadline) with links and reasons, pursued calls closing within 14 days, the week's decisions by name, and scraper health. |
| `python run.py --apply-requests` | Daily at 12:07 and 17:07 | Carries out the change requests approved on the dashboard (see "Approvals"). |
| Scraper watch, inside `run.py` | After every scan | Alerts when at least 3 pages, and at least a tenth of the scan, were read badly. |

These run from `run.py`, not from `assistant/`, because the assistant may only read the
ledger and the portals' files; `run.py` is the one place that wires components together
(AGENTS.md, hard rule 1). `scripts/install-schedule.ps1` registers them beside the
pipeline's own tasks.

## Approvals

Five actions change something, so the assistant only asks for them. Each propose tool
checks the request, works out what it would do, and records it in the ledger's
`change_requests` table (docs/LEDGER_SCHEMA.md). Nothing else happens until a person
approves it.

| Tool | What it asks for | What happens once approved |
|---|---|---|
| `propose_keyword_change` | Add or remove broad keywords, tight keywords or blocklist patterns for one portal. The preview lists the stored calls it would newly keep or drop, with a warning for any the team pursued or the AI rated yes. | The portal's `keywords.yaml` is edited (only the lines added or removed, under a dated comment naming the request and the approver) and committed to `main`. Every stored call of that portal is filtered again, and newly kept calls are reviewed. |
| `propose_rereview` | Run one call's AI review again with context from the team, for example when the AI said no to a call the team thinks fits. Refused for a call the keyword filter rejected; that needs a keyword change. | The reviewer is asked again with "Context from the team: ..." in the prompt. Its answer replaces the old one, and the result says how it changed. |
| `propose_scan` | Scan one portal now instead of waiting for Monday. The preview says when the last scan ran and how long it took. | One pipeline run for that portal: fetch, filter, review, Slack cards for new calls. |
| `propose_draft` | Start a response draft for one call. The preview is the call's brief. Refused when the call is closed or its deadline has passed. | Stays approved for the Writer (`drafting/`, not built yet), which will read approved `draft` requests from the ledger and mark them applied. |
| `propose_fault_report` | File a scraper fault as a GitHub issue. The body is the description, the scraper's health and its recent runs. | Filed with `gh issue create`. Until the repo has a GitHub remote, it stays approved and says so. |

How a request moves:

1. **Proposed.** A propose tool records it. Asking twice for exactly the same thing returns
   the open request instead of a second one.
2. **Approved or rejected** on the dashboard's Requests page (`/requests`), by whoever is
   deciding there, with an optional note. A request is decided once.
3. **Carried out** by `python run.py --apply-requests`, twice a day at 12:07 and 17:07. It takes the
   pipeline lock only when an approved request is ready, so it never runs alongside a scan.
   Each request ends `applied` or `failed`, with a `result` in words, and one Slack message
   lists what was carried out.

An approved request that cannot run yet stays approved, and its result says why:

- A keyword change commits to `main` only. While the scan machine's checkout is on another
  branch, or the keywords file has uncommitted edits, the change waits.
- A fault report waits until the repo has a GitHub remote and `gh` is installed.
- When a scan is running, the job tries again on its next pass.

A request left half done by a job that stopped is marked failed on the next pass, and can
be proposed again.

From the command line, with `--by` naming who is asking:

```powershell
python -m assistant propose keyword vulcan_sof --add-broad "digital twin" --reason "Two twin calls were rejected" --by "David Wood"
python -m assistant propose rereview <call id> --context "It is a software layer over existing radios."
python -m assistant propose scan vulcan_sof
python -m assistant propose draft <call id> --notes "Lead with Echo C2."
python -m assistant propose fault vulcan_sof --description "Logins have failed twice this week."
python -m assistant requests --status proposed
```

## What the tools read

- The ledger: `calls`, `runs`, `change_requests` and, once filled, `proposals`.
- Each portal's own files, named in its `PORTAL` dict: `keywords` (its keywords.yaml),
  `how_to_submit` (one line) and `notes` (its NOTES.md, what the assistant should know).
- Page fields a portal stores in `calls.extra`, found by suffix so every portal can use
  them: `<prefix>_objectives`, `_documents`, `_files_required`, `_tags` (lists),
  `_instructions` (text), and the flags `_closed` and `_description_fallback`.
- Deadlines as the portal writes them, such as "30 OCT 2026 : 21:59 MDT", read by
  `assistant/dates.py`.

## Connecting a model later

`assistant.tools.all_tools()` lists every tool with its name, description, permission and a
JSON schema of its parameters, the shape model APIs expect for function tools. The model
gets those definitions and the results; it never gets credentials.

- Read tools cannot change anything.
- Propose tools only record requests. The code that runs a tool for the model passes
  `requested_by` (the Slack user who asked); it is not a parameter the model can set.
- No tool approves a request. Approval happens on the dashboard, by a person.
