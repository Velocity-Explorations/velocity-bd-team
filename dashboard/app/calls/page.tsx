import type { Metadata } from "next";
import { decide } from "../actions";
import { FilterPanel } from "@/components/FilterPanel";
import { JudgeVerdicts } from "@/components/Judges";
import { Shell } from "@/components/Shell";
import { Badge, Details, Flash, TitleLink } from "@/components/bits";
import { callDetails, deadlineNote, noDeadlineLabel } from "@/lib/details";
import { displayPerson } from "@/lib/people";
import { filterHref, pickMany, pickSort, pickState } from "@/lib/filters";
import { formatDue, formatTime } from "@/lib/format";
import { agreementText, pickJudgeFilter, verdictsFor } from "@/lib/judges";
import { decisionsOn, judgeAgreement, latestJudgments, listCalls, portals, type CallFilters } from "@/lib/queries";
import { peopleSplit, votesByCall } from "@/lib/scoreboard";
import { displayTimeZone } from "@/lib/settings";
import { firstParam, isClosed, parseNoteLine } from "@/lib/text";
import { DECISIONS, FILTER_RESULTS, HUMAN_STATUSES, isDecision, pickAllowed, STATUS_LABELS, VERDICTS } from "@/lib/values";
import { allowlist, currentViewer } from "@/lib/viewer";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "All calls" };

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

const LIMIT = 200;

export default async function CallsPage({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  const portalList = await portals();
  const filters: CallFilters = {
    portals: pickMany(sp.portal, portalList),
    state: pickState(sp.state, sp.open),
    sort: pickSort(sp.sort),
    judges: pickJudgeFilter(sp.judges),
    filterResult: pickAllowed(sp.filter_result, FILTER_RESULTS),
    verdict: pickAllowed(sp.verdict, [...VERDICTS, "none"] as const),
    status: pickAllowed(sp.status, [...HUMAN_STATUSES, "none"] as const),
    q: firstParam(sp.q, 120),
  };
  const [{ rows, total }, agreement] = await Promise.all([listCalls(filters, LIMIT), judgeAgreement()]);
  const ids = rows.map((r) => r.id);
  const [judged, decisions, viewer] = await Promise.all([latestJudgments(ids), decisionsOn(ids), currentViewer()]);
  const tz = displayTimeZone();
  const users = allowlist();
  const votes = votesByCall(decisions, (by) => displayPerson(by, users));
  const filtered = Boolean(
    filters.portals.length || filters.state || filters.sort === "due" || filters.judges || filters.filterResult ||
      filters.verdict || filters.status || filters.q,
  );
  const returnTo = filterHref("/calls", {
    q: filters.q,
    portal: filters.portals,
    state: filters.state,
    sort: filters.sort === "due" ? "due" : "",
    judges: filters.judges,
    filter_result: filters.filterResult,
    verdict: filters.verdict,
    status: filters.status,
  });

  return (
    <Shell current="calls">
      <div className="page-head">
        <div>
          <h1>All calls</h1>
          <p className="muted">
            Every call the scanner has seen, including the ones the filter or the reviewer ruled out.{" "}
            <span className="num">
              Showing {rows.length} of {total}
            </span>
            {total > rows.length ? ". Narrow the filters to see the rest." : "."}
            {agreement && agreement.both ? ` ${agreementText(agreement.both, agreement.agree)}` : ""}
          </p>
        </div>
      </div>

      <Flash notice={firstParam(sp.notice, 300)} error={firstParam(sp.error, 300)} />

      <div className="with-panel">
        <FilterPanel
          action="/calls"
          portals={portalList}
          selected={filters.portals}
          state={filters.state}
          sort={filters.sort}
          judges={filters.judges}
          filtered={filtered}
        >
          <label className="field">
            Title contains
            <input type="search" name="q" defaultValue={filters.q} placeholder="e.g. C2" />
          </label>
          <label className="field">
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
          <label className="field">
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
          <label className="field">
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
        </FilterPanel>

        <section className="panel-body">
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
                    <th>Claude / Grok</th>
                    <th>Decision</th>
                    <th>Notes</th>
                    <th>Due</th>
                    <th>First seen</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => {
                    const notes = (r.human_notes ?? "").split("\n").filter(Boolean).map(parseNoteLine);
                    const callVotes = votes.get(r.id) ?? [];
                    const decidedByViewer = callVotes.length
                      ? callVotes.some((v) => v.person === viewer)
                      : displayPerson(r.human_by, users) === viewer;
                    return (
                      <tr key={r.id}>
                        <td className="call">
                          <TitleLink title={r.title} url={r.url} fallback={r.id} />
                          <div className="meta">
                            <span>{r.portal}</span>
                            <Details items={callDetails(r)} />
                            {isClosed(r.extra) ? <span className="badge tone-grey">closed</span> : null}
                          </div>
                        </td>
                        <td>
                          <Badge value={r.filter_result} />
                          {r.match_tier ? <div className="meta">{r.match_tier} tier</div> : null}
                          {r.filter_result === "rejected" && r.filter_reason ? <div className="meta">{r.filter_reason}</div> : null}
                        </td>
                        <td>
                          <JudgeVerdicts verdicts={verdictsFor(judged.get(r.id), r.ai_verdict, r.ai_reasoning)} reasonsFor={["claude", "grok"]} />
                        </td>
                        <td>
                          <Badge value={r.human_status} empty="undecided" />
                          {peopleSplit(callVotes) ? <span className="badge tone-warn">people disagree</span> : null}
                          {callVotes.length > 1 ? (
                            <ul className="notes votes">
                              {callVotes.map((v) => (
                                <li key={v.person}>
                                  {v.person}: {isDecision(v.status) ? STATUS_LABELS[v.status] : v.status}{" "}
                                  <span className="when">{formatTime(v.decided_at, tz)}</span>
                                </li>
                              ))}
                            </ul>
                          ) : r.human_status ? (
                            <div className="meta">
                              <span>{displayPerson(r.human_by, users)}</span>
                              <span className="when">{formatTime(r.human_at, tz)}</span>
                            </div>
                          ) : null}
                          <details className="change">
                            <summary>{!r.human_status ? "decide" : decidedByViewer ? "change" : "add yours"}</summary>
                            <form action={decide}>
                              <input type="hidden" name="id" value={r.id} />
                              <input type="hidden" name="expected" value={isDecision(r.human_status) ? r.human_status : ""} />
                              <input type="hidden" name="return_to" value={returnTo} />
                              <select name="status" defaultValue={isDecision(r.human_status) ? r.human_status : ""} required aria-label={`Decision on ${r.title ?? r.id}`}>
                                <option value="" disabled>
                                  Choose
                                </option>
                                {DECISIONS.map((d) => (
                                  <option key={d.value} value={d.value}>
                                    {STATUS_LABELS[d.value]}
                                  </option>
                                ))}
                              </select>
                              <input type="text" name="note" maxLength={2000} placeholder="Note (optional)" aria-label={`Note on ${r.title ?? r.id}`} />
                              <button type="submit">Save</button>
                            </form>
                          </details>
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
                        <td className="when" title={deadlineNote(r.extra) ?? undefined}>{formatDue(r.due_date, tz) || <span className="muted">{noDeadlineLabel(r.extra)}</span>}</td>
                        <td className="when">{formatTime(r.first_seen_at, tz)}</td>
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
