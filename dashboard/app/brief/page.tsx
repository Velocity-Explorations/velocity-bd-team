import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import { Shell } from "@/components/Shell";
import { Badge, TitleLink } from "@/components/bits";
import { closesText, judgesSentence, parseBrief, parseTop, weekLabel, type BriefCall, type PortalBrief } from "@/lib/brief";
import { formatTime } from "@/lib/format";
import { displayPerson, type Person } from "@/lib/people";
import { briefRows, briefWeeks, currentDecisions, type CallDecision } from "@/lib/queries";
import { displayTimeZone } from "@/lib/settings";
import { firstParam } from "@/lib/text";
import { isDecision, STATUS_LABELS } from "@/lib/values";
import { allowlist } from "@/lib/viewer";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Monday brief" };

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function statusLabel(status: string | null): string {
  return status && isDecision(status) ? STATUS_LABELS[status] : status ?? "";
}

function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`;
}

/** The call's decision as of now: a badge and who made it, or "undecided". */
function DecisionNow({ decision, users }: { decision: CallDecision | undefined; users: Person[] }) {
  if (!decision?.status) return <span className="muted">undecided</span>;
  return (
    <span>
      <Badge value={decision.status} /> <span className="muted">{displayPerson(decision.by, users)}</span>
    </span>
  );
}

function Empty({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Shell current="brief">
      <div className="page-head">
        <div>
          <h1>Monday brief</h1>
        </div>
      </div>
      <div className="empty">
        <p className="title">{title}</p>
        <p className="muted">{children}</p>
      </div>
    </Shell>
  );
}

export default async function BriefPage({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  const weeks = await briefWeeks();
  if (weeks === null) {
    return (
      <Empty title="The Monday brief needs migration 005.">
        Run <code>python -m ledger.migrate</code> against the live database, then reload this page.
      </Empty>
    );
  }
  if (weeks.length === 0) {
    return (
      <Empty title="No brief yet.">
        The Monday 9:00 job writes one each week, when it posts the summary to Slack. <code>python run.py --write-brief</code> writes
        this week&apos;s now, without posting.
      </Empty>
    );
  }

  const asked = firstParam(sp.week, 10);
  const week = weeks.includes(asked) ? asked : weeks[0];
  const rows = await briefRows(week);
  const top = parseTop(rows.find((r) => r.portal === null)?.body);
  const boards = rows
    .filter((r) => r.portal !== null)
    .map((r) => parseBrief(r.body))
    .filter((b): b is PortalBrief => b !== null);
  const listed: BriefCall[] = [...(top?.top ?? []), ...boards.flatMap((b) => b.topPicks)];
  const decisions = await currentDecisions([...new Set(listed.map((c) => c.id))]);
  const users = allowlist();
  const tz = displayTimeZone();
  const written = rows.at(-1)?.created_at ?? null;
  const judges = top ? judgesSentence(top.judges) : "";

  return (
    <Shell current="brief">
      <div className="page-head">
        <div>
          <h1>Monday brief, {weekLabel(week)}</h1>
          <p className="muted">
            The week as the Monday summary posted it to Slack{written ? `, written ${formatTime(written, tz)}` : ""}. Each listed
            call also shows its decision as of now.
          </p>
        </div>
      </div>

      {weeks.length > 1 ? (
        <p className="muted">
          Other weeks:{" "}
          {weeks
            .filter((w) => w !== week)
            .slice(0, 8)
            .map((w, i) => (
              <span key={w}>
                {i ? " · " : ""}
                <Link href={`/brief?week=${w}`}>{weekLabel(w)}</Link>
              </span>
            ))}
        </p>
      ) : null}

      <h2>Top 10 across portals</h2>
      {top && top.top.length ? (
        <>
          <p className="muted">
            Open calls nobody had decided when the brief was written{top.rankedBy ? `, ranked ${top.rankedBy}` : ""}. The fit score
            will replace this order.
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Call</th>
                  <th>Portal</th>
                  <th>Verdict</th>
                  <th>Closes</th>
                  <th>Why</th>
                  <th>Decision now</th>
                </tr>
              </thead>
              <tbody>
                {top.top.map((c, i) => (
                  <tr key={c.id}>
                    <td className="num">{i + 1}</td>
                    <td className="call">
                      <TitleLink title={c.title} url={c.url} fallback={c.id} />
                    </td>
                    <td>{c.portal ?? ""}</td>
                    <td>
                      <Badge value={c.verdict} />
                    </td>
                    <td className="when">{closesText(c.deadline, c.daysLeft)}</td>
                    <td className="reason">{c.reason}</td>
                    <td>
                      <DecisionNow decision={decisions.get(c.id)} users={users} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <p className="muted">No open, undecided yes or maybe calls that week.</p>
      )}

      {boards.map((b) => {
        const pursued = b.closingSoon.filter((c) => c.status === "pursue");
        return (
          <section key={b.portal} className="board">
            <h2>{b.portal}</h2>
            <p>
              {b.newTotal} new this week
              {b.newByVerdict.length ? ` (${b.newByVerdict.map(([v, n]) => `${n} ${v}`).join(", ")})` : ""};{" "}
              {plural(b.waiting, "open call", "open calls")} waiting for a decision.
            </p>
            {b.topPicks.length ? (
              <>
                <h3>Top picks</h3>
                <ol>
                  {b.topPicks.map((c) => (
                    <li key={c.id}>
                      <TitleLink title={c.title} url={c.url} fallback={c.id} />{" "}
                      <span className="muted">
                        {c.verdict ?? ""}, closes {closesText(c.deadline, c.daysLeft)}
                      </span>
                      {decisions.get(c.id)?.status ? (
                        <>
                          {" "}
                          <DecisionNow decision={decisions.get(c.id)} users={users} />
                        </>
                      ) : null}
                      {c.reason ? <div className="muted">{c.reason}</div> : null}
                    </li>
                  ))}
                </ol>
              </>
            ) : null}
            {pursued.length ? (
              <>
                <h3>Pursued, closing within 14 days</h3>
                <ul>
                  {pursued.map((c) => (
                    <li key={c.id}>
                      <TitleLink title={c.title} url={c.url} fallback={c.id} />{" "}
                      <span className="muted">closes {closesText(c.deadline, c.daysLeft)}</span>
                    </li>
                  ))}
                </ul>
              </>
            ) : null}
            {b.decided.length ? (
              <>
                <h3>Decided this week</h3>
                <ul>
                  {b.decided.map((c) => (
                    <li key={c.id}>
                      {statusLabel(c.status)}: <TitleLink title={c.title} url={c.url} fallback={c.id} />{" "}
                      <span className="muted">({displayPerson(c.by, users)})</span>
                    </li>
                  ))}
                </ul>
              </>
            ) : null}
            {b.health ? <p className="muted">Scraper: {b.health}</p> : null}
          </section>
        );
      })}

      {judges ? (
        <p className="muted board">
          {judges} <Link href="/judges">See the judges page.</Link>
        </p>
      ) : null}
    </Shell>
  );
}
