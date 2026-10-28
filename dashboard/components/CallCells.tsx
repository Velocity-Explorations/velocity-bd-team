// The cells Needs review and All calls share (PRO-571, PRO-572): the Call cell, Votes, Description and Due.

import { MessageSquareText } from "lucide-react";
import { PortalLogo } from "@/components/PortalLogo";
import { panelId } from "@/components/RowPanels";
import { Badge, Details, TitleLink } from "@/components/bits";
import { callDetails, deadlineNote, noDeadlineLabel, type Detail } from "@/lib/details";
import { descriptionCell, splitDetails } from "@/lib/description";
import { formatDue } from "@/lib/format";
import { daysLeftText } from "@/lib/home";
import { JUDGES, judgesConflict, judgesDisagree, type Verdicts } from "@/lib/judges";
import { peopleSplit, type Vote } from "@/lib/scoreboard";
import { withoutTags, type TagBadge } from "@/lib/tags";
import { isClosed } from "@/lib/text";
import { isDecision, STATUS_LABELS } from "@/lib/values";

type CallFields = Parameters<typeof callDetails>[0] & { id: string; portal: string; title: string | null; url: string | null; extra: string | null };

/**
 * The Call cell: the portal's logo tile, the title linked to the portal's page, the details line (the
 * portal, then the facts the portal gives, separated by dots), the badges line (with Top 10, #N for a
 * call in this week's Top 10), the tags line, and, below 1280px, Claude's reason folded under it.
 */
export function CallCell({ row, tags, details, reason, topRank }: {
  row: CallFields;
  tags: TagBadge[];
  details: boolean;
  reason: string | null;
  topRank?: number;
}) {
  const { facts, badges } = splitDetails<Detail>(withoutTags(callDetails(row), tags));
  const closed = isClosed(row.extra);
  return (
    <td className="call">
      <div className="call-with-logo">
        <PortalLogo portal={row.portal} />
        <div className="call-body">
          <TitleLink title={row.title} url={row.url} fallback={row.id} />
          <div className="meta details">
            <span>{row.portal}</span>
            {details ? <Details items={facts} /> : null}
          </div>
          {closed || badges.length || topRank ? (
            <div className="meta badges">
              {topRank ? <span className="badge tone-grey">Top 10, #{topRank}</span> : null}
              {closed ? <span className="badge tone-grey">closed</span> : null}
              <Details items={badges} />
            </div>
          ) : null}
          {tags.length ? (
            <div className="meta tags">
              <Details items={tags} />
            </div>
          ) : null}
          {reason ? <p className="folded-reason">{reason}</p> : null}
        </div>
      </div>
    </td>
  );
}

function NoteButton({ panel, label }: { panel: string; label: string }) {
  return (
    <button type="button" className="note-btn" data-panel={panel} aria-controls={panel} aria-expanded="false" title={label}>
      <MessageSquareText aria-hidden="true" />
      <span className="sr-only">{label}</span>
    </button>
  );
}

/**
 * Votes: each judge's verdict with a note button that opens the reasons panel, flagged when the
 * judges disagree; then, under a dashed rule, each person's latest vote, with a note button when they
 * left a note. `votes` is null where people's votes are not listed.
 */
export function VotesCell({ callId, verdicts, votes, notesBy }: { callId: string; verdicts: Verdicts; votes: Vote[] | null; notesBy: Set<string> }) {
  const reasons = panelId("reasons", callId);
  return (
    <td className="votes-cell">
      <div className="judges">
        {JUDGES.map(({ key, label }) => (
          <div key={key} className="judge">
            <span className="who">{label}</span>
            <Badge value={verdicts[key]?.verdict} empty={key === "grok" ? "not yet" : "not reviewed"} />
            {verdicts[key]?.reasoning ? <NoteButton panel={reasons} label={`${label}'s reason`} /> : null}
          </div>
        ))}
        {judgesConflict(verdicts) ? (
          <span className="badge tone-bad">judges: yes vs no</span>
        ) : judgesDisagree(verdicts) ? (
          <span className="badge tone-warn">judges disagree</span>
        ) : null}
      </div>
      {votes ? (
        <div className="people-votes">
          {votes.length ? (
            <ul className="notes votes">
              {votes.map((v) => (
                <li key={v.person}>
                  {v.person}: {isDecision(v.status) ? STATUS_LABELS[v.status] : v.status}
                  {notesBy.has(v.person) ? <NoteButton panel={panelId("notes", callId)} label={`${v.person}'s notes`} /> : null}
                </li>
              ))}
            </ul>
          ) : (
            <span className="muted">nobody yet</span>
          )}
          {peopleSplit(votes) ? <span className="badge tone-warn">people disagree</span> : null}
        </div>
      ) : null}
    </td>
  );
}

/** Description (Q13): 300 characters over four lines, the rest on hover and keyboard focus, labelled where it is not the portal's. */
export function DescriptionCell({ portal, description, extra }: { portal: string; description: string | null; extra: string | null }) {
  const cell = descriptionCell(portal, description, extra);
  return (
    <td className="description wide">
      {cell.label || cell.text ? (
        <p className="clamp-4" title={cell.full || undefined} tabIndex={cell.full ? 0 : undefined}>
          {cell.label ? <span className="desc-label">{cell.label}</span> : null}
          {cell.label && cell.text ? " " : null}
          {cell.text}
        </p>
      ) : (
        <span className="muted">No description in the ledger yet</span>
      )}
    </td>
  );
}

/** Due: the deadline in the dashboard's zone (or as the portal wrote it), then the days left; where it came from on hover. */
export function DueCell({ due, daysLeft, extra, tz }: { due: string | null; daysLeft: number | null; extra: string | null; tz: string }) {
  const note = deadlineNote(extra);
  const shown = formatDue(due, tz);
  return (
    <td className="when due">
      <span title={note ?? undefined} tabIndex={note ? 0 : undefined} className={note ? "tip" : undefined}>
        {shown || <span className="muted">{noDeadlineLabel(extra)}</span>}
      </span>
      {shown && daysLeft !== null ? <div className="meta days-left">{daysLeftText(daysLeft)}</div> : null}
    </td>
  );
}
