import { ChevronDown } from "lucide-react";
import { decide } from "@/app/actions";
import { Badge, toneOf } from "@/components/bits";
import { decideLabel, dueLine, type VoteLike } from "@/lib/decide";
import { formatTime } from "@/lib/format";
import { stepLabel } from "@/lib/proposals";
import type { DraftInfo } from "@/lib/queries";
import { DECISIONS, isDecision, STATUS_LABELS } from "@/lib/values";

/**
 * Where the cell sits: `waiting`, the queue's views that hold only calls waiting for the viewer;
 * `mixed`, Top 10, which holds calls decided or not; `all`, All calls, which also shows the call's own
 * decision with who made it and when.
 */
export type DecideMode = "waiting" | "mixed" | "all";

/**
 * The Decide cell (Q9, Q14, PRO-572). The Decide menu lists Pursue, Not relevant, Submitted and
 * Dismiss, each with its tone square and word; choosing one records it at once, with the note when
 * Add a note was opened. Pursue and start the draft waits for the proposal workspace (P8). Where the
 * view mixes calls you have and have not decided, the cell says which: needs your decision (with
 * when it is due, within 14 days) or You: and your decision. The button carries the accent border
 * on a call waiting for you, and reads Decide, Change or Add yours. A pursued call with no draft shows
 * Start the draft; one with a draft, Open workspace with its current step (Q17, PRO-576).
 */
export function DecideCell({ call, mode, viewer, yours, eligible, decidedBy, returnTo, keep, note, tz, draft, drafting, start }: {
  call: { id: string; title: string | null; human_status: string | null; human_at?: string | null; days_left: number | null };
  mode: DecideMode;
  viewer: string | null;
  yours: VoteLike | null;
  eligible: boolean;
  decidedBy: string;
  returnTo: string;
  keep: boolean;
  note: boolean;
  tz: string;
  draft?: DraftInfo | null;
  drafting: boolean;
  start: { portal: string; due: string; format: string; block: string | null };
}) {
  const label = mode === "waiting" ? "Decide" : decideLabel({ yours, callStatus: call.human_status });
  const waitingForYou = mode === "waiting" || (Boolean(viewer) && eligible && !yours);
  const due = dueLine(call.days_left);
  return (
    <td className="decide">
      {mode === "all" ? (
        <div className="call-decision">
          <Badge value={call.human_status} empty="undecided" />
          {call.human_status ? (
            <div className="meta">
              <span>{decidedBy}</span>
              <span className="when">{formatTime(call.human_at, tz)}</span>
            </div>
          ) : null}
        </div>
      ) : null}
      {mode !== "waiting" && viewer && yours ? (
        <div className="your-status">
          <span className={`badge tone-${toneOf(yours.status)}`}>You: {isDecision(yours.status) ? STATUS_LABELS[yours.status] : yours.status}</span>
          <div className="meta when">{formatTime(yours.decided_at, tz)}</div>
        </div>
      ) : null}
      {mode !== "waiting" && waitingForYou ? (
        <div className="your-status">
          <span className="badge tone-warn">needs your decision</span>
          {due ? <div className="due-line">{due}</div> : null}
        </div>
      ) : null}
      <form action={decide} className="decide-form">
        <input type="hidden" name="id" value={call.id} />
        <input type="hidden" name="expected" value={isDecision(call.human_status) ? call.human_status : ""} />
        {keep ? <input type="hidden" name="keep" value="1" /> : null}
        <input type="hidden" name="return_to" value={returnTo} />
        <details className="menu decide-menu">
          <summary className={waitingForYou ? "btn decide-button needs-you" : "btn decide-button"}>
            {label}
            <span className="sr-only"> on {call.title || call.id}</span>
            <ChevronDown aria-hidden="true" />
          </summary>
          <div className="menu-body">
            {DECISIONS.map((d) => (
              <button key={d.value} type="submit" name="status" value={d.value} className={`menu-item tone-${toneOf(d.value)}`}>
                <span className="sq" aria-hidden="true" />
                {d.label}
              </button>
            ))}
            {draft ? null : (
              <button type="submit" name="status" value="pursue_draft" className="menu-item tone-good" disabled={!drafting || Boolean(start.block)}>
                <span className="sq" aria-hidden="true" />
                Pursue and start the draft
              </button>
            )}
            <p className="hint">
              {draft || (drafting && !start.block)
                ? "Choosing records it at once."
                : !drafting
                  ? "Choosing records it at once. Drafting is not set up yet, so Start the draft waits for it."
                  : `Choosing records it at once. Cannot draft: ${start.block}.`}
            </p>
          </div>
        </details>
        {draft ? (
          <div className="draft-action">
            <a className="btn" href={`/proposals/${encodeURIComponent(call.id)}`}>
              Open workspace
            </a>
            <div className="meta">{stepLabel(draft.current_step)}</div>
          </div>
        ) : call.human_status === "pursue" && start.block ? (
          <div className="draft-action meta">Cannot draft: {start.block}</div>
        ) : call.human_status === "pursue" ? (
          <div className="draft-action">
            <button
              type="button"
              className="fn-approve"
              data-start-draft={call.id}
              data-title={call.title || call.id}
              data-portal={start.portal}
              data-due={start.due}
              data-format={start.format}
            >
              Start the draft
            </button>
          </div>
        ) : null}
        {note ? (
          <details className="add-note">
            <summary className="btn-text">Add a note</summary>
            <textarea name="note" maxLength={2000} rows={3} placeholder="Sent with the decision you choose" aria-label={`Note on ${call.title || call.id}`} />
          </details>
        ) : null}
      </form>
    </td>
  );
}
