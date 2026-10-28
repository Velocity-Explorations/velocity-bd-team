-- 009_call_summaries: a short summary of each call for an executive, written by the per-call review
-- (phase 9c of docs/design/redesign-plan.md). The dashboard's Description column shows it in place of
-- the portal's own words, which stay in calls.description and show on hover.

ALTER TABLE calls ADD COLUMN ai_summary TEXT;
