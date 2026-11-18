import { ArrowRight } from "lucide-react";
import { cache } from "react";
import { rateTopPickAction } from "@/app/actions";
import { DecideCell } from "@/components/DecideCell";
import { DecideButton, RowOutcome } from "@/components/DecideControls";
import { DraftBadge } from "@/components/DraftBadge";
import { PersonName } from "@/components/PersonName";
import { PortalLogo } from "@/components/PortalLogo";
import { Badge, FitBadge, TitleLink } from "@/components/bits";
import { asksReason, rowAnchor, yourVote } from "@/lib/decide";
import { descriptionCell } from "@/lib/description";
import { formatDue } from "@/lib/format";
import { daysLeftText, topTenOrder } from "@/lib/home";
import { verdictsFor } from "@/lib/judges";
import { MAX_PICK_COMMENT, PICK_LABELS, PICK_RATINGS, PICK_TONES, type PickRated } from "@/lib/toppicks";
import { fitBadge } from "@/lib/fit";
import { listingBadge } from "@/lib/listing";
import { displayPerson } from "@/lib/people";
import { draftBlock, draftFormat } from "@/lib/proposals";
import { decisionsOn, draftsFor, latestJudgments, topTenRows } from "@/lib/queries";
import { votesByCall } from "@/lib/scoreboard";
import { allowlist } from "@/lib/viewer";

/** The calls' rows, both judges, their drafts and everyone's votes, read together once per request (the ids as JSON,
 *  the cache key). */
const topTenData = cache(async (key: string) => {
  const ids = JSON.parse(key) as string[];
  const [rows, judged, drafts, decisions] = await Promise.all([topTenRows(ids), latestJudgments(ids), draftsFor(ids), decisionsOn(ids)]);
  const byId = new Map(rows.map((r) => [r.id, r]));
  const users = allowlist();
  const votes = votesByCall(decisions, (by) => displayPerson(by, users));   // by the name decisions are recorded under
  return { byId, order: topTenOrder(ids, new Set(byId.keys())), judged, drafts, votes };
});

/** What deciding from the table needs (Home, David 5 Nov): who is deciding, whether everyone decides every call
 *  (the queue's "keep"), and whether drafting is set up. */
export type TopTenDecide = { viewer: string | null; keep: boolean; drafting: boolean };

/** Home's rating of the week's picks (Task 5, 18 Nov 2026): the brief's week, the viewer's own ratings and everyone else's. */
export type TopTenRate = {
  week: string;
  mine: Map<string, PickRated>;
  others: Map<string, { person: string; rating: string; comment: string | null }[]>;
};

/** Start reading the Top 10 as soon as its ids are known, beside the page's other queries. */
export function preloadTopTen(ids: string[]): void {
  topTenData(JSON.stringify(ids)).catch(() => undefined);
}

/**
 * The Top 10 table Home and the past weekly briefs share (H2, PRO-570, PRO-573): rank, logo, title
 * and portal, the deadline and days left, both verdicts, the decision now, the description (Home only:
 * Claude's executive summary where there is one, the portal's words on hover) and Claude's reason, each
 * as the ledger has them now; a call with a draft shows its badge
 * (DB1). A row opens Calls, Top 10 with that call focused, except on the list to watch (`watch`), which Calls' Top 10
 * does not hold. An umbrella or announcement wears its badge. With `decide` (Home), each row also has the Decide menu,
 * and a decision comes back to Home.
 */
export async function TopTenTable({ ids, description, tz, nameOf, decide, rate, watch = false }: {
  ids: string[];
  description: boolean;
  tz: string;
  nameOf: (by: string | null) => string;
  decide?: TopTenDecide;
  rate?: TopTenRate;
  watch?: boolean;
}) {
  const { byId, order, judged, drafts, votes } = await topTenData(JSON.stringify(ids));
  if (order.length === 0) {
    return (
      <div className="empty">
        <p className="title">{watch ? "Nothing to watch yet." : "Nothing to rank yet."}</p>
        <p className="muted">
          {watch
            ? "This list holds open yes and maybe umbrellas and announcements nobody has decided: standing CSOs, BAAs and cycles, and notices with nothing to submit yet."
            : "The Top 10 lists open yes and maybe calls nobody has decided. New ones arrive with each scan."}
        </p>
      </div>
    );
  }
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th className="rank">#</th>
            <th>Call</th>
            <th className="due">Deadline</th>
            <th className="fit">Fit</th>
            <th className="verdict-col">Claude</th>
            <th className="verdict-col">Grok</th>
            <th className="decision">Decision now</th>
            {description ? <th className="wide">Summary description</th> : null}
            <th className="wide">Judges&apos; reasons</th>
            {rate ? <th className="pick">Good pick?</th> : null}
            {decide ? <th className="decide">Decide</th> : null}
            <th className="row-arrow">
              <span className="sr-only">Open</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {order.map((id, i) => {
            const call = byId.get(id)!;
            const verdicts = verdictsFor(judged.get(id), call.ai_verdict, call.ai_reasoning);
            const cell = descriptionCell(call.portal, call.description, call.extra, call.ai_summary);
            const draft = drafts.get(id);
            const kind = listingBadge(call.listing);
            return (
              <tr
                key={id}
                id={rowAnchor(id)}
                data-call-id={id}
                className={watch ? undefined : "row-link"}
                data-href={watch ? undefined : `/review?view=top10&focus=${encodeURIComponent(id)}`}
                tabIndex={watch ? undefined : 0}
                aria-label={watch ? undefined : `${call.title || call.id}: open it in Calls, Top 10`}
              >
                <td className="rank num">{i + 1}</td>
                <td className="call">
                  <div className="call-with-logo">
                    <PortalLogo portal={call.portal} />
                    <div>
                      <TitleLink title={call.title} url={call.url} fallback={call.id} />
                      <div className="meta">{call.portal}</div>
                      {kind ? <div className="meta badges"><span className="badge tone-info" title={kind.title}>{kind.text}</span></div> : null}
                      {draft ? <DraftBadge draft={draft} nameOf={nameOf} /> : null}
                    </div>
                  </div>
                </td>
                <td className="when">
                  {formatDue(call.due_date, tz) || <span className="muted">no deadline</span>}
                  {call.days_left !== null ? <div className="meta">{daysLeftText(call.days_left)}</div> : null}
                </td>
                <td className="fit">
                  {fitBadge(call) ? <FitBadge row={call} /> : <span className="muted">not yet</span>}
                </td>
                <td>
                  <Badge value={verdicts.claude?.verdict} empty="not reviewed" />
                </td>
                <td>
                  <Badge value={verdicts.grok?.verdict} empty="not yet" />
                </td>
                <td>
                  {call.human_status ? (
                    <>
                      <Badge value={call.human_status} />
                      <div className="meta"><PersonName by={call.human_by}>{nameOf(call.human_by)}</PersonName></div>
                    </>
                  ) : (
                    <span className="muted">undecided</span>
                  )}
                </td>
                {description ? (
                  <td className="wide reason">
                    {cell.label || cell.text ? (
                      <p className={cell.summary ? "clamp whole" : "clamp"} title={cell.full.slice(0, 1000) || undefined}
                        tabIndex={cell.full ? 0 : undefined}>
                        {cell.label ? <span className="desc-label">{cell.label}</span> : null}
                        {cell.label && cell.text ? " " : null}
                        {cell.text}
                      </p>
                    ) : (
                      <span className="muted">No description in the ledger</span>
                    )}
                  </td>
                ) : null}
                <td className="wide reason">
                  {/* Both judges' reasons (Task 4, 18 Nov 2026): Grok gives one with every verdict. */}
                  <p className="clamp judge-reason"><b>Claude</b> {verdicts.claude?.reasoning ?? "not reviewed"}</p>
                  <p className="clamp judge-reason"><b>Grok</b> {verdicts.grok?.reasoning ?? "not yet"}</p>
                </td>
                {rate ? <PickCell id={id} title={call.title || call.id} rate={rate} nameOf={nameOf} /> : null}
                {decide ? (
                  <DecideCell
                    call={call}
                    mode="mixed"
                    viewer={decide.viewer}
                    yours={yourVote(votes.get(id) ?? [], decide.viewer)}
                    eligible={call.ai_verdict === "yes" || call.ai_verdict === "maybe"}
                    decidedBy=""
                    returnTo="/"
                    keep={decide.keep || Boolean(call.human_status)}
                    note
                    tz={tz}
                    draft={draft}
                    drafting={decide.drafting}
                    start={{ portal: call.portal, due: formatDue(call.due_date, tz), format: draftFormat(call.type), block: draftBlock(call) }}
                    startIn="/proposals"
                    askReason={asksReason(call.ai_verdict)}
                  />
                ) : null}
                <td className="row-arrow" aria-hidden="true">
                  {watch ? null : <ArrowRight />}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/**
 * Is this a good pick for the Top 10? (Task 5 of the 9 Nov review, 18 Nov 2026): the viewer rates the pick Good pick, Not
 * a fit or Unsure, with a reason if they want, apart from their decision on the call; everyone else's ratings show under.
 */
function PickCell({ id, title, rate, nameOf }: { id: string; title: string; rate: TopTenRate; nameOf: (by: string | null) => string }) {
  const mine = rate.mine.get(id);
  const others = rate.others.get(id) ?? [];
  return (
    <td className="pick">
      <form action={rateTopPickAction} className="pick-form">
        <input type="hidden" name="week" value={rate.week} />
        <input type="hidden" name="call_id" value={id} />
        <input type="hidden" name="return_to" value="/" />
        <div className="pick-choices" role="group" aria-label={`Is ${title} a good pick for this week's Top 10?`}>
          {PICK_RATINGS.map((r) => (
            <DecideButton key={r} name="rating" value={r} pressed={mine?.rating === r}
              className={`pick-choice tone-${PICK_TONES[r]}${mine?.rating === r ? " on" : ""}`}>
              {PICK_LABELS[r]}
            </DecideButton>
          ))}
        </div>
        <details className="pick-why" open={Boolean(mine?.comment)}>
          <summary className="btn-text">{mine?.comment ? "Why" : "Add why"}</summary>
          <textarea name="comment" rows={2} maxLength={MAX_PICK_COMMENT} defaultValue={mine?.comment ?? ""}
            aria-label={`Why, for ${title}`} placeholder="A few words; saved with the rating" />
        </details>
        <RowOutcome callId={id} param="rated" className="pick-outcome" />
        {others.length ? (
          <ul className="pick-others">
            {others.map((o) => (
              <li key={o.person}>
                <PersonName by={o.person}>{nameOf(o.person)}</PersonName>{" "}
                <span className={`badge tone-${PICK_TONES[o.rating as keyof typeof PICK_TONES] ?? "none"}`}>
                  {PICK_LABELS[o.rating as keyof typeof PICK_LABELS] ?? o.rating}
                </span>
                {o.comment ? <span className="muted"> {o.comment}</span> : null}
              </li>
            ))}
          </ul>
        ) : null}
      </form>
    </td>
  );
}
