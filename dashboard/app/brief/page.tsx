import type { Metadata } from "next";
import { ArrowRight, ChevronRight } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { Shell } from "@/components/Shell";
import { TopTenTable } from "@/components/TopTenTable";
import { Badge, TitleLink } from "@/components/bits";
import { boardHref, closesText, judgesSentence, parseBrief, parseTop, weekLabel, type BriefCall, type PortalBrief } from "@/lib/brief";
import { formatTime } from "@/lib/format";
import { displayPerson } from "@/lib/people";
import { briefRows, briefWeeks, currentDecisions, type CallDecision } from "@/lib/queries";
import { labeler, timeZone } from "@/lib/me";
import { firstParam } from "@/lib/text";
import { isDecision, STATUS_LABELS } from "@/lib/values";
import { allowlist } from "@/lib/viewer";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Past weekly briefs" };

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function statusLabel(status: string | null): string {
  return status && isDecision(status) ? STATUS_LABELS[status] : status ?? "";
}

function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`;
}

/** The call's decision as of now: a badge and who made it, or "undecided". */
function DecisionNow({ decision, nameOf }: { decision: CallDecision | undefined; nameOf: (by: string | null) => string }) {
  if (!decision?.status) return <span className="muted">undecided</span>;
  return (
    <span>
      <Badge value={decision.status} /> <span className="muted">{nameOf(decision.by)}</span>
    </span>
  );
}

/** The way back to Home (spec, Pages): the briefs sit outside the top bar's sections. */
function Breadcrumb() {
  return (
    <nav className="breadcrumb" aria-label="Breadcrumb">
      <Link href="/">Home</Link>
      <ChevronRight aria-hidden="true" />
      <span aria-current="page">Past weekly briefs</span>
    </nav>
  );
}

function Empty({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Shell section="home">
      <Breadcrumb />
      <h1>Past weekly briefs</h1>
      <div className="empty">
        <p className="title">{title}</p>
        <p className="muted">{children}</p>
      </div>
    </Shell>
  );
}

/**
 * Past weekly briefs (PRO-573): the week as the Monday 9:00 job posted it, the Top 10 table as on
 * Home, then one board per portal, each a content card whose label band links to that portal's
 * calls. Earlier weeks are linked at the top. Monday's Slack post links here.
 */
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
  const listed: BriefCall[] = boards.flatMap((b) => b.topPicks);
  const decisions = await currentDecisions([...new Set(listed.map((c) => c.id))]);
  const users = allowlist();
  const tz = await timeZone();
  const label = await labeler();
  const nameOf = (by: string | null) => label(displayPerson(by, users));
  const written = rows.at(-1)?.created_at ?? null;
  const judges = top ? judgesSentence(top.judges) : "";
  const others = weeks.filter((w) => w !== week).slice(0, 8);

  return (
    <Shell section="home">
      <Breadcrumb />
      <div className="brief-head">
        <h1>Monday brief, {weekLabel(week)}</h1>
        <p className="muted">
          {written ? `Written ${formatTime(written, tz)}. ` : ""}
          {others.length ? (
            <>
              Other weeks:{" "}
              {others.map((w, i) => (
                <span key={w}>
                  {i ? " · " : ""}
                  <Link href={`/brief?week=${w}`}>{weekLabel(w)}</Link>
                </span>
              ))}
            </>
          ) : (
            "The first brief; earlier weeks appear here as they are posted."
          )}
        </p>
      </div>

      <section className="top-ten" aria-labelledby="top-ten-title">
        <div className="section-head">
          <h2 id="top-ten-title">Top 10 across portals</h2>
          <p className="muted">
            As the Monday 9:00 job posted it to Slack{top?.rankedBy ? `, ranked ${top.rankedBy}` : ""}, with each call&apos;s decision as of now.
          </p>
        </div>
        {top && top.top.length ? (
          <TopTenTable ids={top.top.map((c) => c.id)} description={false} tz={tz} nameOf={nameOf} />
        ) : (
          <div className="empty">
            <p className="title">No Top 10 that week.</p>
            <p className="muted">No open, undecided yes or maybe calls when the brief was written.</p>
          </div>
        )}
      </section>

      <div className="board-grid">
        {boards.map((b) => {
          const pursued = b.closingSoon.filter((c) => c.status === "pursue");
          return (
            <section key={b.portal} className="content-card board-card" aria-label={b.portal}>
              <a className="content-card__label" href={boardHref(b.portal)}>
                <span>{b.portal}</span>
                <ArrowRight aria-hidden="true" />
              </a>
              <div className="content-card__body">
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
                              <DecisionNow decision={decisions.get(c.id)} nameOf={nameOf} />
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
                          <span className="muted">({nameOf(c.by)})</span>
                        </li>
                      ))}
                    </ul>
                  </>
                ) : null}
                {b.health ? <p className="muted">Scraper: {b.health}</p> : null}
              </div>
            </section>
          );
        })}
      </div>

      {judges ? (
        <p className="muted board">
          {judges} <Link href="/judges">See the judges page.</Link>
        </p>
      ) : null}
    </Shell>
  );
}
