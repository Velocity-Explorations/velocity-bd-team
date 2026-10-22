# reference/yukon — proven prior art from the retired Yukon scanner

Read-only. Nothing in the repo imports these files. Read the relevant ones before implementing a phase:
the plan prompts describe this code, but the code is the source of truth for what actually worked.

- First copied 2026-10-15: the Vulcan SOF, review, Slack, corpus and Writer files (top level).
- Completed 2026-10-22: every other portal adapter (portals/), the rest of the scan pipeline (scanner/), and the remaining scripts (scripts/).
- Scanned for secrets both times; none present. Not included: .env files, Slack tokens, data/ (databases, caches, checkpoints), logs.
- Imports inside these files still use Yukon's package paths (for example `from scanner.checkpoint import ...`). Adapt them when porting.

## SAM.gov quick start

| File | Why you need it |
|---|---|
| portals/sam_gov.py | The adapter. SAM.gov Opportunities API v2, queried by (ptype × NAICS) with rdlfrom=today. Ran nightly. |
| scanner/checkpoint.py | Resume support for long SAM.gov fetches (small JSON files under data/checkpoints/). sam_gov.py imports it. |
| scanner/attachments.py | Scan-time attachment enrichment: downloads the most relevant SOW/PWS/RFP files for filtered opportunities and adds their text. |
| scanner/rfp_attachments.py | Draft-time downloader: every attachment for one opportunity, text extracted, originals uploaded to Drive. |
| scanner/main.py | How the scan called SAM.gov: no outer timeout (the adapter manages per-request timeouts and key rotation itself), resume and reset-checkpoint flags, and the attachment step between filter and review. |
| 2026-04-20_sam-gov-checkpoint-autoclear-bug.md | Checkpoints never cleared when page caps were hit; fixed in sam_gov.py. |
| 2026-05-06_naics-gate-irrelevant-matches.md | The NAICS gate let opportunities through without a keyword check. Read before writing a SAM.gov filter. |
| profile.yaml | The NAICS codes and keyword lists SAM.gov filtering used. |

API keys, from the code:
- sam_gov.py assumes 1,000 requests per key per day, keeps a 50-request reserve, skips a run that would exceed it, and rotates through SAM_GOV_API_KEY, SAM_GOV_API_KEY_2 and SAM_GOV_API_KEY_3 when a key returns 429.
- Attachment downloads, at scan time and draft time, used a separate key, SAM_GOV_RFP_AGENT_KEY, so they never spent the search keys' quota.

## Top level

| File | What it is | Used by |
|---|---|---|
| vulcan_sof.py | Vulcan SOF adapter: cookie-first login, OTP via `gog gmail`, selector cascades, call listing and detail regexes, force_close | Playbook Phases 1–4 |
| 2026-04-18_vulcan-sof-hanging.md | Post-mortem: `networkidle` never fires on Vulcan's Angular app; the fixes | Playbook Phases 1–4, 7 |
| filter.py | NAICS/keyword gate, exclusion patterns, set-aside filter, rejection reasons | Playbook Phase 5 |
| profile.yaml | Velocity profile: NAICS codes, broad/scrape/bidnet keyword lists, portal list | Playbook Phase 5, SAM.gov |
| review.py | Stage-1 regex blocklist; stage-2 LLM review prompt, company context, VERDICT/REASON parser, RAG context | Playbook Phases 5–6 |
| feedback_examples.py | Builds the few-shot "recent human decisions" block for the review prompt | Playbook Phase 8 |
| slack_events_server.py | Reaction handling (👍 👎 ✅ ❌), message parsing, BD card creation, feedback logging. For Velocity, 👍 also launched the RFP agent | Playbook Phase 8, Writer Plan |
| alert.py | Slack/Discord message formatting for opportunities | Playbook Phase 8 |
| text_extract.py | Text extraction for docx/pdf/pptx/xlsx plus an Ollama embedding helper | Corpus Phase C |
| ingest_past_submissions.py | Chunk and embed past submissions into ChromaDB; doc_type inference | Corpus Phase C |
| rfp_response_agent.py | The proposal pipeline: phases 1–8, including terminology extraction, alignment, 4-pass review, compliance check, delivery | Writer Plan W0 |
| templates/*.md | Per-opportunity-type response templates (sbir_phase1, baa_response, ota_white_paper, cso_response, capability_statement, full_proposal) | Writer Plan W0 |
| knowledge-base/*.md | Company context: company_profile, capabilities, past_performance, personnel, win_themes, boilerplate | Writer W1 fallback until the corpus reference material is in place |

## portals/ — every other portal adapter (vulcan_sof.py is at the top level)

| File | Portal | How it fetched |
|---|---|---|
| sam_gov.py | SAM.gov | API v2, nightly; needs API keys (see above) |
| nstxl.py | NSTXL OTA consortia (S2MARTS, SpEC, Microelectronics Commons) | HTML scrape |
| diu.py | DIU Commercial Solutions Openings | HTML scrape |
| afwerx.py | AFWERX "Get Funded" SBIR/STTR (STRIKEWERX has no solicitations page) | HTML scrape |
| ac_cto.py | AC CTO / APFIT cycle status | HTML scrape (WordPress) |
| doe_sbir.py | DOE Office of Science SBIR funding opportunities | HTML tables |
| iarpa.py | IARPA BAAs and CSOs across four pages | Playwright |
| space_force.py | Space Force, via SpaceWERX (my.spaceforce.mil needs SSO) | HTML scrape |
| space_florida.py | Space Florida RFPs | HTML scrape |
| bidnet.py | BidNet Direct state and local bids, Colorado and Florida | HTML scrape |
| nasa_forecast.py | NASA Acquisition Forecast | Excel download, filtered by NAICS and keywords |
| jmetc.py | TRMC / JMETC (the wiki needs auth; scrapes public pages) | HTML scrape; not enabled in any Yukon profile |

## scanner/ — the rest of the scan pipeline

| File | What it did |
|---|---|
| main.py | Scan orchestrator: per-portal dispatch and timeouts, then filter → attachments (SAM.gov) → review → dedup → score → summarize → ingest |
| checkpoint.py | Resume support for long fetches (SAM.gov) |
| attachments.py | Scan-time SAM.gov attachment download and text extraction |
| rfp_attachments.py | Draft-time attachment downloader for one opportunity (SAM.gov first), dedicated key, uploads originals to Drive |
| reenrich.py | Re-fetched attachments for existing SAM.gov opportunities and re-scored them |
| forecast_xref.py | Matched NASA forecast rows to live SAM.gov solicitations |
| velocity_scorer.py | Velocity / Echo C2 fit score 1–10 with RAG context and heuristics |
| profile_scorer.py | Keyword-based 1–10 scorer for non-Velocity profiles |
| calibration.py | Per-profile keyword weight adjustments learned from triage decisions |
| scorer.py | The original ranking scorer (top-5 daily picks) |
| summarize.py | 2–3 sentence summaries via `claude -p` |
| profile.py | Loaded profile.yaml and .env |
| dedup.py | SQLite seen-opportunity store (the ledger's first_seen replaces it) |
| api_sink.py | Posted results to the retired Prospector web app (the ledger replaces it) |
| sheet.py | Google Sheets writer (legacy) |

## scripts/

| File | What it did |
|---|---|
| ingest_submitted_draft.py | Embedded submitted drafts from Drive into the vector store |
| reingest_with_sources.py | Re-embedded past submissions with per-file source metadata |
| backfill_descriptions.py | One-shot: fetched SAM.gov descriptions and re-summarized them |
| process_inbox.py | Legacy Inbox-sheet triage processor |
| backfill_sheet.py | Legacy Google Sheet backfill |
| scheduler-tick.sh | The Mac scheduler tick that triggered scans |
