import Link from "next/link";
import type { Metadata } from "next";
import { Shell } from "@/components/Shell";
import { Badge, TitleLink } from "@/components/bits";
import { displayPerson } from "@/lib/people";
import { formatTime } from "@/lib/format";
import { listCalls, portals, type CallFilters } from "@/lib/queries";
import { displayTimeZone } from "@/lib/settings";
import { firstParam, isClosed, parseNoteLine } from "@/lib/text";
import { FILTER_RESULTS, HUMAN_STATUSES, pickAllowed, VERDICTS } from "@/lib/values";
import { allowlist } from "@/lib/viewer";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "All calls" };

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

const LIMIT = 200;

export default async function CallsPage({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  const filters: CallFilters = {
    portal: firstParam(sp.portal, 100),
    filterResult: pickAllowed(sp.filter_result, FILTER_RESULTS),
    verdict: pickAllowed(sp.verdict, [...VERDICTS, "none"] as const),
    status: pickAllowed(sp.status, [...HUMAN_STATUSES, "none"] as const),
    q: firstParam(sp.q, 120),
  };
  const [{ rows, total }, portalList] = await Promise.all([listCalls(filters, LIMIT), portals()]);
  const tz = displayTimeZone();
  const users = allowlist();
  const filtered = Object.values(filters).some(Boolean);

  return (
    <Shell current="calls">
      <div className="page-head">
        <div>
          <h1>All calls</h1>
          <p className="muted">
            Every call the scanner has seen, newest first.{" "}
            <span className="num">
              Showing {rows.length} of {total}
            </span>
            {total > rows.length ? ". Narrow the filters to see the rest." : "."}
          </p>
        </div>
      </div>

      <form className="filters" action="/calls">
        <label>
          Title contains
          <input type="search" name="q" defaultValue={filters.q} placeholder="e.g. C2" />
        </label>
        <label>
          Portal
          <select name="portal" defaultValue={filters.portal}>
            <option value="">All portals</option>
            {portalList.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>
        <label>
          Filter
          <select name="filter_result" defaultValue={filters.filterResult}>
            <option value="">Any</option>
            {FILTER_RESULTS.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <label>
          AI verdict
          <select name="verdict" defaultValue={filters.verdict}>
            <option value="">Any</option>
            {VERDICTS.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
            <option value="none">not reviewed</option>
          </select>
        </label>
        <label>
          Decision
          <select name="status" defaultValue={filters.status}>
            <option value="">Any</option>
            {HUMAN_STATUSES.map((v) => (
              <option key={v} value={v}>
                {v.replace("_", " ")}
              </option>
            ))}
            <option value="none">undecided</option>
          </select>
        </label>
        <button type="submit">Apply</button>
        {filtered ? (
          <Link href="/calls" className="reset">
            Clear filters
          </Link>
        ) : null}
      </form>

      {rows.length === 0 ? (
        <div className="empty">
          <p className="title">{filtered ? "No calls match these filters." : "The ledger has no calls yet."}</p>
          <p className="muted">Calls appear after the first scan (python run.py).</p>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Call</th>
                <th>Filter</th>
                <th>AI verdict</th>
                <th>Decision</th>
                <th>Notes</th>
                <th>Due</th>
                <th>First seen</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const notes = (r.human_notes ?? "").split("\n").filter(Boolean).map(parseNoteLine);
                return (
                  <tr key={r.id}>
                    <td className="call">
                      <TitleLink title={r.title} url={r.url} fallback={r.id} />
                      <div className="meta">
                        <span>{r.portal}</span>
                        {r.type ? <span>{r.type}</span> : null}
                        {isClosed(r.extra) ? <span className="badge tone-grey">closed</span> : null}
                      </div>
                    </td>
                    <td>
                      <Badge value={r.filter_result} />
                      {r.match_tier ? <div className="meta">{r.match_tier} tier</div> : null}
                      {r.filter_result === "rejected" && r.filter_reason ? <div className="meta">{r.filter_reason}</div> : null}
                    </td>
                    <td>
                      <Badge value={r.ai_verdict} empty="not reviewed" />
                      {r.ai_reasoning ? (
                        <details>
                          <summary>reason</summary>
                          <p>{r.ai_reasoning}</p>
                        </details>
                      ) : null}
                    </td>
                    <td>
                      <Badge value={r.human_status} empty="undecided" />
                      {r.human_status ? (
                        <div className="meta">
                          <span>{displayPerson(r.human_by, users)}</span>
                          <span className="when">{formatTime(r.human_at, tz)}</span>
                        </div>
                      ) : null}
                    </td>
                    <td>
                      {notes.length ? (
                        <ul className="notes">
                          {notes.map((n, i) => (
                            <li key={i}>
                              {n.text}
                              {n.by ? (
                                <span className="muted">
                                  {" "}
                                  ({displayPerson(n.by, users)}
                                  {n.at ? `, ${formatTime(n.at, tz)}` : ""})
                                </span>
                              ) : null}
                            </li>
                          ))}
                        </ul>
                      ) : null}
                    </td>
                    <td className="when">{r.due_date ?? ""}</td>
                    <td className="when">{formatTime(r.first_seen_at, tz)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Shell>
  );
}
