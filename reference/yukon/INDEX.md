# reference/yukon — proven prior art from the retired Yukon scanner

Read-only. Nothing in the repo imports these. Read the relevant file before implementing a phase;
the playbook prompts describe this code, but the code is the source of truth for what actually worked.
Copied 2026-10-15 from /Users/dwood/yukon; scanned for secrets, none present.

| File | What it is | Used by |
|---|---|---|
| vulcan_sof.py | Vulcan SOF adapter: cookie-first login, OTP via `gog gmail`, selector cascades, call listing + detail regexes, force_close | Playbook Phases 1–4 |
| 2026-04-18_vulcan-sof-hanging.md | Post-mortem: `networkidle` never fires on Vulcan's Angular app; the fixes | Playbook Phases 1–4, 7 |
| filter.py | NAICS/keyword gate, exclusion patterns, set-aside filter, rejection reasons | Playbook Phase 5 |
| profile.yaml | Velocity profile: NAICS, broad/scrape/bidnet keyword lists, portal list | Playbook Phase 5 |
| review.py | Stage-1 regex blocklist; stage-2 LLM review prompt, company context, VERDICT/REASON parser, RAG context | Playbook Phases 5–6 |
| feedback_examples.py | Builds the few-shot "recent human decisions" block for the review prompt | Playbook Phase 8 |
| slack_events_server.py | Reaction handling (👍 👎 ✅ ❌), message parsing, BD card creation, feedback logging | Playbook Phase 8 |
| alert.py | Slack/Discord message formatting for opportunities | Playbook Phase 8 |
| text_extract.py | Text extraction for docx/pdf/pptx/xlsx + Ollama embedding helper | Corpus Phase C |
| ingest_past_submissions.py | Chunk + embed past submissions into ChromaDB; doc_type inference | Corpus Phase C |
| rfp_response_agent.py | The proposal pipeline: phases 1–8 incl. terminology extraction, alignment, 4-pass review, compliance check, delivery | Writer Plan W0 |
| templates/*.md | Per-opportunity-type response templates (sbir_phase1, baa_response, ota_white_paper, cso_response, capability_statement, full_proposal) | Writer Plan W0 |
| knowledge-base/*.md | Company context: company_profile, capabilities, past_performance, personnel, win_themes, boilerplate | Writer W1 fallback; also belongs in Drive "01 Company Reference" |
