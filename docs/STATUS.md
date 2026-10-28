# Status

Kept by the Coordinator. Read before starting work; update in your PR if your change affects it.

## Live

- Ledger (Phase 0), migration 001_initial applied to the hosted Supabase Postgres on
  2026-10-16, 002_change_requests on 2026-10-17, 003_judgments and 004_decisions on
  2026-10-20. Tables: calls, change_requests, decisions, judgments, proposals, runs,
  schema_migrations. Connect through the Session pooler URL (the
  direct URL is IPv6-only and unreachable from David's network). Each thread keeps one
  connection open across its transactions (`ledger/db.py`): reconnecting cost about 585 ms a
  query against 183 ms reused, and ran two portals' fetches past their limit in the first full
  scan on 24 Oct (PRO-550).

## In progress

- Phase 7 (pipeline): `python run.py` runs every registered portal (fetch under a hard timeout,
  filter, review, digest) and writes data/logs/run_*.log. Scheduled weekly (Sunday 22:00 since 2026-10-20) via
  scripts/install-schedule.ps1 as of 2026-10-16. Failure alerts go to Slack once SLACK_CHANNEL_ID
  is set; until then they are log warnings.
- Phase 8 (Slack delivery and feedback): cards and a summary per run; thread replies polled into
  notes and cards edited to show decisions (`run.py --feedback-only`, daily task). Live on
  2026-10-16. Since 2026-10-17 reactions are not read: decisions are made on the dashboard.
- Phase 9 (dashboard): Next.js 16.4 app in dashboard/, run locally with `npm run dev`. The only
  place decisions are made: review queue buttons, plus a change control on all calls. Several
  people can decide (DASHBOARD_USERS lists David and Shaun since 2026-10-20); each person's
  decisions are kept and a judges page scores Claude and Grok against them. While the judges
  are trained, everyone decides every call: each person's queue holds the calls they have not
  decided (DASHBOARD_QUEUE=each, the default). A Monday brief page (2026-10-21) shows the week
  the Monday summary posted, with a Top 10 across portals. Runs and proposals pages too. Not deployed yet: since 2026-10-21 a container image
  (dashboard/Dockerfile) is ready for Alec to host on GKE behind Google's IAP, which signs in each
  person by email (PRO-511; the deployment is PRO-477). Until then only David can decide.

- Phase 2 (Vulcan SOF login): working as of 2026-10-16. Username, password, then the emailed
  code read over Gmail IMAP (VELOCITY_GMAIL_APP_USERNAME + VELOCITY_GMAIL_APP_PASSWORD; gog CLI
  is used instead when installed). Calls listing reachable, 120 call links seen.
- Phase 3 (session persistence): cookies saved to data/vulcan_sof/cookies.json after each successful
  login and restored first on the next run; verified 2026-10-16.
- Portal assistant, step 1 (2026-10-17): read tools in assistant/ (explain, brief, deadlines,
  scraper health, weekly summary, portal profile, settings preview, tuning report), daily
  deadline reminders, the Monday summary and the scraper watch. No model connected yet.
- Portal assistant, step 2 (2026-10-17): approvals. Propose tools (keyword change, re-review,
  scan now, start a draft, fault report) record requests in change_requests (migration 002);
  the dashboard's Requests page approves or rejects them; `run.py --apply-requests` carries
  them out twice a day, at 12:07 and 17:07. Drafts wait for the Writer; fault reports wait for a GitHub
  remote. The reminder and summary jobs moved from `python -m assistant` to run.py.
- GitHub (2026-10-18): the repo is at Velocity-Explorations/velocity-bd-team, public since
  2026-10-19 (a scan of every commit found no credentials first), with main
  pushed. Approved fault reports now file there as issues.
- GitHub token (2026-10-19): fault reports file with the pipeline's own token
  (`BD_GITHUB_TOKEN`), a classic token with the repo scope that expires 2027-01-17, and with
  the gh login when `.env` has none. A token limited to this repo's issues would need
  fine-grained tokens enabled for Velocity-Explorations. Renewal steps are in
  docs/RUNBOOK.md, "GitHub token".
- Drafts (2026-10-21): drafting phase 7.6 leaves each draft's opening paragraph, and its abstract's
  first three sentences, for a person to write: a [PERSON WRITES: ...] placeholder with points to
  land under it, and a checklist item (PRO-494).
  Phase 7.7 then runs the AI slop detection skill's scanner and ends with a verdict, such as
  "Not ready: 1 PERSON WRITES, 34 NEEDS INPUT; band clean (provisional)"; `python -m drafting.cli check
  --draft <file>` reruns it after edits (PRO-510). The scanner must be installed wherever drafts run
  (AI_SLOP_SCAN); its bands stay provisional until calibrated on past Velocity proposals.
- Proposal Library (2026-10-21): the "00 Proposal Register" sheet and "00 README" are in the BD Proposal
  Library Drive folder, with one row per Submissions folder. `library/register.py` checks the rows and
  syncs them into `proposals`; Claude runs it on request through David's Google connectors, as no
  scheduled job can read the sheet until gog or a service account exists (PRO-475).
- Plans (2026-10-18): the Writer Plan, the Draft-Ready Upgrade and the Proposal Library plan were revised
  so the dashboard decides. Drafts are requested with the dashboard's Draft button, an approved
  draft request from the assistant, or the CLI. Offline copies are in docs/plans/.
- Shared portal helpers (2026-10-17): browser, saved sessions, emailed sign-in codes and the
  keyword filter live in portals/shared/ for every adapter; Vulcan SOF keeps only its own
  login, scraping and keywords.yaml.
- Phase 4 (Vulcan SOF scrape): `python -m portals.vulcan_sof.run_scrape` writes every listed call
  (60 on 2026-10-16, 18 open and 42 closed; closed flagged in extra.vulcan_closed) in about 170 s
  with 100% field fill. Descriptions are stored at up to 1,500 characters (widened from 400 on 2026-10-16).
- Phase 5 (keyword filter): `python -m portals.vulcan_sof.run_filter` (add `--all` after editing
  portals/vulcan_sof/keywords.yaml). On 2026-10-16: 60 rows, 58 kept (6 tight, 52 broad), 2 rejected.
  The `ai` substring keeps most rows in broad; the LLM review is the real gate.
- Phase 6 (LLM review): `python -m review.run_review` reviews kept, unreviewed rows of the latest run
  with claude-haiku-5-5. On 2026-10-16: 58 rows, yes 17, maybe 33, no 8, 206 s. Model failure yields
  "maybe" with a "Review error" reason, never "no".
- APFIT (2026-10-24): portals/apfit/ reads the cycle-status posts on the APFIT page, one request
  a run: one call per cycle with its status, and how a company takes part (through a government
  sponsor). A cycle in final selection, evaluation or awarded is closed; both on 24 Oct were, so
  nothing was stored. Runs with the Sunday scan (PRO-547).
- Space Florida (2026-10-24): portals/space_florida/ reads the active RFPs on Space Florida's
  solicitations page, one request a run: title, documents, notes, published and due dates. An RFP
  past its due date or with a notice of intent to award counts as closed; the one listed on 24
  Oct was both, so nothing was stored. Runs with the Sunday scan (PRO-546).
- NASA Forecast (2026-10-24): portals/nasa_forecast/ reads NASA's acquisition forecast
  spreadsheet with the standard library: one download a run, each planned buy one call of type
  Forecast with no deadline, its expected solicitation and award quarters in the description.
  Kept on Velocity's five NAICS codes or its topics. Runs with the Sunday scan (PRO-545).
- DOE SBIR (2026-10-24): portals/doe_sbir/ reads DOE's SBIR and STTR solicitations from its
  Application Hub's public WordPress API (sbir-sttr.connectwerx.org), since the programs moved to
  DOE's Office of Technology Commercialization and the Office of Science page Yukon read is
  closed. One request a run. Both listings were closed on 24 Oct, so nothing is stored until the
  next opens. Every listing reaches the judges. Runs with the Sunday scan (PRO-543).
- SpaceWERX (2026-10-23): portals/spacewerx/ reads the Space Force's listings on SpaceWERX's Get
  Funded page, which uses AFWERX's template: SBIR and STTR cycles, and STRATFI and TACFI notices
  for Phase II holders (one, a TACFI notice open on a continuous basis, on 23 Oct). One request a
  run; both adapters share portals/shared/funding_list.py. Kept on "sbir", "sttr", "stratfi" or
  "tacfi". Runs with the Sunday scan (PRO-538).
- AFWERX (2026-10-23): portals/afwerx/ reads the SBIR and STTR cycles on AFWERX's Get Funded page
  (those with Air Force or Space Force topics): one request a run. Each cycle is one call with its
  pre-release, open and close dates. The topics are on DSIP, whose robots.txt forbids automated
  access, so the call links DSIP's topic search for a person to read them. Kept on "sbir" or
  "sttr". Runs with the Sunday scan (PRO-536).
- DIU (2026-10-23): portals/diu/ reads DIU's open CSOs, prize challenges and CLASS ACT bridge
  solicitations from the state its open-solicitations page embeds, without running the page's
  code: one request a run. Each call has the solicitation text and eligibility, and the close
  time in Eastern time. Runs with the Sunday scan (PRO-534).
- NSTXL (2026-10-22): portals/nstxl/ reads the S2MARTS, SpEC, JDEC and Microelectronics Commons
  opportunities from NSTXL's public WordPress API, with stable ids: Current and Coming Soon items,
  less those awarded, canceled or stale. Member-only pages (mostly SpEC) are stored with their
  title and a note; reading them needs a member sign-in (PRO-531). Deadlines are read from the
  page text. Runs with the Sunday scan (PRO-530).
- SAM.gov (2026-10-22): portals/sam_gov/ reads the public Opportunities API with one key
  (BD_SAM_API_KEY): open notices under five NAICS codes, solicitation and notice types Velocity
  pursues, full and open, small business and WOSB set-asides. A run spends at most 900 requests
  and reads new notices' descriptions soonest deadline first; the rest wait for the next run.
  Requests go over IPv4 (SAM.gov's IPv6 address hangs from the scan PC). A notice Front Door
  reposts is stored once, by whichever adapter sees it first. Built, not yet run for real
  (PRO-525). It also searches IARPA's office whatever the NAICS code, because iarpa.gov refuses
  automated clients (PRO-537), and notice titles naming TRMC, which runs JMETC and posts some
  notices with no NAICS code (PRO-548).
- SSC Front Door (2026-10-21): portals/ssc_front_door/ reads the site's public Events list over
  plain HTTP, with no login and no browser, and stores listings that have not ended. Most are events
  (conferences, industry days, webinars); both judges rate those on their topic. It runs with the
  Sunday scan; `python run.py --portal ssc_front_door --dry-run` tests it.
- Second judge (2026-10-20): Grok (grok-4.7) judges every call the Claude review rates, with the
  same prompt, when BD_XAI_API_KEY is set. Both verdicts go to the judgments table (migration 003)
  and show on the dashboard with how often they agree; Claude's verdict still decides what is
  posted. `python run.py --backfill-judgments` fills the history once.
- Tags (2026-10-24): every call carries tags from the list in review/tags.yaml, in four groups: one
  type, and any work, customer and access tags (call_tags, migration 006). Rules set what a call's
  data makes certain, such as SOCOM on Vulcan calls; Claude and Grok tag the rest in the review
  answer they already give. `python run.py --backfill-tags` tags stored calls (PRO-556). The
  dashboard shows them under each title, type first, with a Tag filter (tag_list, migration 007,
  PRO-557).
- Dashboard redesign brief (2026-10-25): docs/design/ holds the design spec, a static snapshot
  of the dashboard on public-portal data, the Velocity Theme design system and the build prompts,
  so Claude Design on the Velocity account can read them from GitHub (PRO-559). The redesign
  itself waits on that design. On 2026-10-26 the brief moved from seven pages to four sections:
  Home (new), Calls, Proposals and Automation, with an account menu and Profile settings.
- Dashboard redesign build (from 2026-10-28): Claude Design's handoff is in docs/design/handoff/,
  its spec updates are merged into the spec, and docs/design/redesign-plan.md sets the build in
  phases 0 to 11, with Google sign-in last (PRO-565, PRO-566).
  - Phase 1 (PRO-568): migration 008 adds the proposal workspace's tables (pursuits, pursuit_steps,
    step_changes, pursuit_events, checklist_items, drive_items, slop_scans, profiles, worker_jobs,
    workers) and `ledger/queries.py` the pursuit lifecycle. `ledger/schema.sql` had stopped at 002;
    it now matches every migration, and a test keeps it so.
  - Phase 2a (PRO-569): every page wears the dark BD Team theme from the handoff (tokens, fonts,
    Lucide icons, buttons, badges, tags, menus, notices, tooltips, tables, fields), with no change
    in what the pages do.
  - Phases 2b and 3a (PRO-570): the top bar has four sections (Home, Calls, Proposals, Automation)
    with count chips, and the account menu replaces the Deciding as picker. Home is at `/` (five
    link cards, the Top 10, the status line). The queue moved to `/review`, with a Due soon view.
    Each section opens on view cards in place of a title. Calls' other views, Automation's
    Decided requests and Scan problems, and Profile settings come with phases 3b and 3c.
  - Phase 3b, part 1 (PRO-571): Calls has all seven views. The tables have the handoff's columns:
    logos, the dotted details line, Votes, Description, and days left. Below 1280px the AI reason
    folds under the call. The Decide menu, the reasons and notes panels, the header menus' search
    and Hide column, and the Top 10 focus from Home follow in part 2.

## Known breakages
