import { ArrowRight } from "lucide-react";
import { DraftBadge } from "@/components/DraftBadge";
import { PortalLogo } from "@/components/PortalLogo";
import { Badge, TitleLink } from "@/components/bits";
import { descriptionCell } from "@/lib/description";
import { formatDue } from "@/lib/format";
import { daysLeftText, topTenOrder } from "@/lib/home";
import { verdictsFor } from "@/lib/judges";
import { draftsFor, latestJudgments, topTenRows } from "@/lib/queries";

/**
 * The Top 10 table Home and the past weekly briefs share (H2, PRO-570, PRO-573): rank, logo, title
 * and portal, the deadline and days left, both verdicts, the decision now, the description (Home only:
 * Claude's executive summary where there is one, the portal's words on hover) and Claude's reason, each
 * as the ledger has them now; a call with a draft shows its badge
 * (DB1). A row opens Calls, Top 10 with that call focused.
 */
export async function TopTenTable({ ids, description, tz, nameOf }: {
  ids: string[];
  description: boolean;
  tz: string;
  nameOf: (by: string | null) => string;
}) {
  const rows = await topTenRows(ids);
  const byId = new Map(rows.map((r) => [r.id, r]));
  const order = topTenOrder(ids, new Set(byId.keys()));
  const [judged, drafts] = await Promise.all([latestJudgments(order), draftsFor(order)]);
  if (order.length === 0) {
    return (
      <div className="empty">
        <p className="title">Nothing to rank yet.</p>
        <p className="muted">The Top 10 lists open yes and maybe calls nobody has decided. New ones arrive with each scan.</p>
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
            <th>Deadline</th>
            <th>Claude</th>
            <th>Grok</th>
            <th>Decision now</th>
            {description ? <th className="wide">Description</th> : null}
            <th className="wide">Claude&apos;s reason</th>
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
            return (
              <tr
                key={id}
                className="row-link"
                data-href={`/review?view=top10&focus=${encodeURIComponent(id)}`}
                tabIndex={0}
                aria-label={`${call.title || call.id}: open it in Calls, Top 10`}
              >
                <td className="rank num">{i + 1}</td>
                <td className="call">
                  <div className="call-with-logo">
                    <PortalLogo portal={call.portal} />
                    <div>
                      <TitleLink title={call.title} url={call.url} fallback={call.id} />
                      <div className="meta">{call.portal}</div>
                      {draft ? <DraftBadge draft={draft} nameOf={nameOf} /> : null}
                    </div>
                  </div>
                </td>
                <td className="when">
                  {formatDue(call.due_date, tz) || <span className="muted">no deadline</span>}
                  {call.days_left !== null ? <div className="meta">{daysLeftText(call.days_left)}</div> : null}
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
                      <div className="meta">{nameOf(call.human_by)}</div>
                    </>
                  ) : (
                    <span className="muted">undecided</span>
                  )}
                </td>
                {description ? (
                  <td className="wide reason">
                    {cell.label || cell.text ? (
                      <p className={cell.label === "Summary" ? "clamp whole" : "clamp"} title={cell.full.slice(0, 1000) || undefined}
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
                  <p className="clamp">{call.ai_reasoning ?? ""}</p>
                </td>
                <td className="row-arrow" aria-hidden="true">
                  <ArrowRight />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
