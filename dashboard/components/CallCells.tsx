// The cells Needs review and All calls share (PRO-571, PRO-572): the Call cell, Votes, Description and Due.

import { MessageSquareText } from "lucide-react";
import type { ReactNode } from "react";
import { PersonName } from "@/components/PersonName";
import { PortalLogo } from "@/components/PortalLogo";
import { panelId } from "@/components/RowPanels";
import { Badge, Details, FitBadge, TitleLink } from "@/components/bits";
import { callDetails, deadlineNote, noDeadlineLabel, type Detail } from "@/lib/details";
import { descriptionCell, splitDetails } from "@/lib/description";
import { fitBadge, type FitColumns } from "@/lib/fit";
import { listingBadge } from "@/lib/listing";
import { noteSource } from "@/lib/decide";
import { formatDue, formatTime } from "@/lib/format";
import { daysLeftText } from "@/lib/home";
import { JUDGES, judgesConflict, judgesDisagree, type Verdicts } from "@/lib/judges";
import { peopleSplit, type Vote } from "@/lib/scoreboard";
import { withoutTags, type TagBadge } from "@/lib/tags";
import { isClosed, type NoteParts, type PersonNotes } from "@/lib/text";
import { isDecision, STATUS_LABELS } from "@/lib/values";

type CallFields = Parameters<typeof callDetails>[0] & {
  id: string; portal: string; title: string | null; url: string | null; extra: string | null; listing?: string | null;
};

/**
 * The Call cell: the portal's logo tile, the title linked to the portal's page, the details line (the
 * portal, then the facts the portal gives, separated by dots), the draft badge on its own line (DB1),
 * the badges line (with Top 10, #N for a call in this week's Top 10), the tags line, and, below
 * 1280px, Claude's reason folded under it.
 */
export function CallCell({ row, tags, details, reason, topRank, draft }: {
  row: CallFields;
  tags: TagBadge[];
  details: boolean;
  reason: string | null;
  topRank?: number;
  draft?: ReactNode;
}) {
  const { facts, badges } = splitDetails<Detail>(withoutTags(callDetails(row), tags));
  const closed = isClosed(row.extra);
  const kind = listingBadge(row.listing);   // an umbrella or announcement says so (David, 7 Nov)
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
          {draft ?? null}
          {closed || badges.length || topRank || kind ? (
            <div className="meta badges">
              {topRank ? <span className="badge tone-grey">Top 10, #{topRank}</span> : null}
              {kind ? <span className="badge tone-info" title={kind.title}>{kind.text}</span> : null}
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
 * A person's notes beside their vote (David, 16 Nov 2026): the note button shows them in a box beside it on hover or
 * keyboard focus, and a click keeps the box open until a click elsewhere or Escape (TableController). Each note with
 * when it was written, and Slack thread reply where it came from one.
 */
function NoteTip({ id, person, notes, tz }: { id: string; person: string; notes: NoteParts[]; tz: string }) {
  return (
    <>
      <button type="button" className="note-btn" data-note-tip={id} aria-describedby={id} aria-expanded="false" aria-label={person ? `${person}'s notes` : "Unsigned notes"}>
        <MessageSquareText aria-hidden="true" />
      </button>
      <div id={id} className="note-tip" role="tooltip" hidden>
        {notes.map((n, i) => (
          <div key={i} className="note-tip-item">
            <p>{n.text}</p>
            {n.at || noteSource(n.by) === "Slack thread reply" ? (
              <p className="meta">
                {n.at ? <span className="when">{formatTime(n.at, tz)}</span> : null}
                {noteSource(n.by) === "Slack thread reply" ? <span>Slack thread reply</span> : null}
              </p>
            ) : null}
          </div>
        ))}
      </div>
    </>
  );
}

/**
 * Votes: each judge's verdict with a note button that opens the reasons panel, flagged when the
 * judges disagree; then, under a dashed rule, each person's latest vote, with their notes beside it
 * (NoteTip), and a line for anyone who left a note without voting, since a note saves on its own
 * (David, 16 Nov 2026). `votes` is null where people's votes are not listed.
 */
export function VotesCell({ callId, verdicts, votes, notes, tz, fit }: {
  callId: string;
  verdicts: Verdicts;
  votes: Vote[] | null;
  notes: PersonNotes[];
  tz: string;
  fit?: Partial<FitColumns>;
}) {
  const reasons = panelId("reasons", callId);
  const voters = new Set((votes ?? []).map((v) => v.person));
  const noVote = notes.filter((group) => !voters.has(group.person));
  const tipFor = (person: string) => {
    const index = notes.findIndex((group) => group.person === person);
    return index < 0 ? null : <NoteTip id={`note-tip-${index}-${callId}`} person={person} notes={notes[index].notes} tz={tz} />;
  };
  return (
    <td className="votes-cell">
      <div className="judges">
        {fit && fitBadge(fit) ? (
          <div className="judge fit">
            <span className="who">Fit</span>
            <FitBadge row={fit} />
          </div>
        ) : null}
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
          {votes.length || noVote.length ? (
            <ul className="notes votes">
              {votes.map((v) => (
                <li key={v.person}>
                  <PersonName by={v.person}>{v.person}:</PersonName> {isDecision(v.status) ? STATUS_LABELS[v.status] : v.status}
                  {tipFor(v.person)}
                </li>
              ))}
              {noVote.map((group) => (
                <li key={`notes:${group.person}`}>
                  {group.person ? <PersonName by={group.person}>{group.person}:</PersonName> : "Unsigned:"} <span className="muted">no vote</span>
                  {tipFor(group.person)}
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

/** Summary description (Q13, phase 9c): Claude's executive summary, else 300 characters of the description over four
 *  lines, labelled where an adapter wrote it or NSTXL hides it; the portal's own words in full on hover and keyboard focus. */
export function DescriptionCell({ portal, description, extra, summary }: {
  portal: string;
  description: string | null;
  extra: string | null;
  summary?: string | null;
}) {
  const cell = descriptionCell(portal, description, extra, summary);
  return (
    <td className="description wide">
      {cell.label || cell.text ? (
        <p className={cell.summary ? "clamp-4 whole" : "clamp-4"} title={cell.full || undefined} tabIndex={cell.full ? 0 : undefined}>
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
