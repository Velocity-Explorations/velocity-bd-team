# Putting a call no scanner found through the pursuit flow

10 Nov 2026. The question: how to run the drafting worker on an opportunity that no portal adapter scans. The case was
three Navy topics from DSIP, whose rules bar automated access, so `portals/shared/funding_list.py` only links to it.
The topics were saved by hand into `data/dsip/` (local, never committed), screened, and three were pursued as
pursuits 2 to 4.

## What worked

1. **Add the call under a run of its own.** `start_run(portal="dsip", component="dsip_manual")`, then
   `ledger.queries.upsert_call(record, run_id)` with the shared columns only. `extra` stays `{}`, because a new key
   prefix has to be documented in docs/LEDGER_SCHEMA.md first. Id `dsip-<topic number>`, portal `DSIP`,
   source_type `manual`, and the description is the topic's Objective, Description, Phase I and Phase II text.
2. **Keep it and review it.** `set_filter(id, "kept", reason)`, then
   `review.reviewer.review_calls(calls_for_review(run_id), AnthropicModel())`, which writes the verdict. A call without
   `kept` and a yes or maybe verdict does not appear in Needs review.
3. **Close the run.** `finish_run(run_id, "completed", counts)`. `runs.status` takes only running, completed,
   skipped_timeout or error; `ok` fails the check constraint (run 92 hit this and was closed again).
4. **Pursue and start the draft on the dashboard**, with the Decide menu's "Pursue and start the draft", so the
   decision, pursuit, steps and worker job are written exactly as a click writes them.

## What the worker cannot do, and the workaround

- It cannot open portal pages or download attachments (`drafting/inputs.py`). Discovery marks the call page,
  attachments, parent instructions and key facts "for owner". The steps read the call's description and `extra`, and
  workspace material.
- It creates `00_solicitation/` but never reads it back, so files saved there are for people. Upload them with the
  worker's own client: `drafting.drive.client()`, `find(pursuit_folder_id, "00_solicitation", True)`, then
  `upload(folder_id, path, name, mime)`. The folder exists only once that pursuit's Discovery has started, and the
  worker runs one step at a time, so later pursuits wait their turn.
- Facts the steps need (closing time, page limit, funding caps, the STTR work split) go in as workspace material:
  `ledger.queries.add_event(pursuit_id, who, "material", text)`, the event the dashboard's Add material writes, at most
  2,000 characters a note (`MAX_NOTE_CHARS` in `dashboard/app/actions.ts`). The steps after the note picked the numbers
  up; Alignment and Requirements quoted them.

## Cost and results

Discovery through to the go/no-go gate cost about $0.8 to $0.9 a pursuit. All three gate briefs kept every
do-not-use claim out, as warnings only.

## A screening lesson

Department of the Air Force Direct to Phase II topics say feasibility documentation "cannot be based upon or logically
extend from any prior or ongoing federally funded SBIR or STTR work" (DAF 27.BZ D2P2 Release 1 instructions). A
product that grew out of an SBIR needs a feasibility case built on other work before a DAF D2P2 is worth writing.

## Not done

There is no run.py command for this; the scripts were one-offs in a session scratchpad. If manual calls recur, a
`run.py --add-call` that does steps 1 to 3 from a Markdown file would replace them.
