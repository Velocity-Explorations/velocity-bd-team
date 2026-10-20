import type { Metadata } from "next";
import { decide } from "./actions";
import { FilterPanel } from "@/components/FilterPanel";
import { Shell } from "@/components/Shell";
import { Badge, Flash, TitleLink } from "@/components/bits";
import { filterHref, pickMany, pickSort, pickState } from "@/lib/filters";
import { formatTime } from "@/lib/format";
import { newThisWeek, portals, reviewQueue } from "@/lib/queries";
import { displayTimeZone } from "@/lib/settings";
import { firstParam, isClosed } from "@/lib/text";
import { DECISIONS, pickAllowed } from "@/lib/values";

export const dynamic = "force-dynamic";
// The title template in layout.tsx only applies below the root segment, so this one is spelled out.
export const metadata: Metadata = { title: "Review queue | Velocity BD" };

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

export default async function ReviewQueuePage({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  const portalList = await portals();
  const filters = {
    portals: pickMany(sp.portal, portalList),
    state: pickState(sp.state, sp.open),
    sort: pickSort(sp.sort),
    verdict: pickAllowed(sp.verdict, ["yes", "maybe"] as const),
  };

  const [rows, weekCount] = await Promise.all([reviewQueue(filters), newThisWeek()]);
  const tz = displayTimeZone();
  const returnTo = filterHref("/", {
    portal: filters.portals,
    state: filters.state,
    sort: filters.sort === "due" ? "due" : "",
    verdict: filters.verdict,
  });
  const yesCount = rows.filter((r) => r.ai_verdict === "yes").length;
  const filtered = Boolean(filters.portals.length || filters.state || filters.sort === "due" || filters.verdict);

  return (
    <Shell current="queue">
      <div className="page-head">
        <div>
          <h1>Review queue</h1>
          <p className="muted">Calls the reviewer rated yes or maybe that nobody has decided on yet.</p>
        </div>
        <dl className="stats">
          <div>
            <dt>Waiting</dt>
            <dd>{rows.length}</dd>
          </div>
          <div>
            <dt>Yes</dt>
            <dd>{yesCount}</dd>
          </div>
          <div>
            <dt>Maybe</dt>
            <dd>{rows.length - yesCount}</dd>
          </div>
          <div>
            <dt>New this week</dt>
            <dd>{weekCount}</dd>
          </div>
        </dl>
      </div>

      <Flash notice={firstParam(sp.notice, 300)} error={firstParam(sp.error, 300)} />

      <div className="with-panel">
        <FilterPanel
          action="/"
          portals={portalList}
          selected={filters.portals}
          state={filters.state}
          sort={filters.sort}
          filtered={filtered}
        >
          <label className="field">
            Verdict
            <select name="verdict" defaultValue={filters.verdict}>
              <option value="">Yes and maybe</option>
              <option value="yes">Yes</option>
              <option value="maybe">Maybe</option>
            </select>
          </label>
        </FilterPanel>

        <section className="panel-body">
          {rows.length === 0 ? (
            <div className="empty">
              <p className="title">{filtered ? "No calls match these filters." : "Nothing waiting for a decision."}</p>
              <p className="muted">
                New yes and maybe calls land here after each scan. Deciding takes a call off this list; change a
                decision later on All calls.
              </p>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Verdict</th>
                    <th>Call</th>
                    <th>Due</th>
                    <th>Tier</th>
                    <th>AI reason</th>
                    <th>First seen</th>
                    <th>Decide</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => {
                    const label = r.title || r.id;
                    return (
                      <tr key={r.id} data-call-id={r.id}>
                        <td>
                          <Badge value={r.ai_verdict} />
                        </td>
                        <td className="call">
                          <TitleLink title={r.title} url={r.url} fallback={r.id} />
                          <div className="meta">
                            <span>{r.portal}</span>
                            {isClosed(r.extra) ? <span className="badge tone-grey">closed</span> : null}
                          </div>
                        </td>
                        <td className="when">{r.due_date ?? ""}</td>
                        <td>{r.match_tier ?? ""}</td>
                        <td className="reason">{r.ai_reasoning ?? ""}</td>
                        <td className="when">{formatTime(r.first_seen_at, tz)}</td>
                        <td className="decide">
                          <form action={decide}>
                            <input type="hidden" name="id" value={r.id} />
                            <input type="hidden" name="expected" value="" />
                            <input type="hidden" name="return_to" value={returnTo} />
                            <input type="text" name="note" maxLength={2000} placeholder="Note (optional)" aria-label={`Note on ${label}`} />
                            <div className="buttons">
                              {DECISIONS.map((d) => (
                                <button key={d.value} type="submit" name="status" value={d.value} className={`btn-${d.value}`} title={`${d.label}: ${label}`}>
                                  {d.label}
                                </button>
                              ))}
                            </div>
                          </form>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </Shell>
  );
}
