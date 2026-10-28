import type { Metadata } from "next";
import { decide } from "@/app/actions";
import { CallCell, DescriptionCell, DueCell, VotesCell } from "@/components/CallCells";
import { FilterBar } from "@/components/FilterBar";
import { HeaderCell } from "@/components/HeaderCell";
import { Shell } from "@/components/Shell";
import { ViewCards } from "@/components/ViewCards";
import { Badge, Flash } from "@/components/bits";
import { weekLabel } from "@/lib/brief";
import { shows } from "@/lib/columns";
import { choiceLinks, filterHref, JUDGE_CHOICES, pickMany, pickSort, pickState, sortLink, sortParams, type Params } from "@/lib/filters";
import { formatTime } from "@/lib/format";
import { dayMonth } from "@/lib/home";
import { pickJudgeFilter, verdictsFor } from "@/lib/judges";
import { aliasesFor, displayPerson } from "@/lib/people";
import {
  countAmong,
  decisionsOn,
  judgeAgreement,
  latestJudgments,
  listCalls,
  portals,
  queueCounts,
  tagOptions,
  tagsOn,
  topTenIds,
  type CallFilters,
} from "@/lib/queries";
import { votesByCall } from "@/lib/scoreboard";
import { displayTimeZone, hiddenColumns, queueMode } from "@/lib/settings";
import { tagsByCall } from "@/lib/tags";
import { firstParam, parseNoteLine } from "@/lib/text";
import { DECISIONS, FILTER_RESULTS, HUMAN_STATUSES, isDecision, pickAllowed, STATUS_LABELS, VERDICTS } from "@/lib/values";
import { callViewCards, DUE_SOON_DAYS, NEW_DAYS } from "@/lib/views";
import { allowlist, currentViewer } from "@/lib/viewer";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "All calls" };

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

const LIMIT = 200;
const FILTER_CHOICES = [{ value: "", label: "Any" }, ...FILTER_RESULTS.map((v) => ({ value: v, label: v }))];
const VERDICT_CHOICES = [{ value: "", label: "Any" }, ...VERDICTS.map((v) => ({ value: v, label: v })), { value: "none", label: "not reviewed" }];
const STATUS_CHOICES = [
  { value: "", label: "Any" },
  ...HUMAN_STATUSES.map((v) => ({ value: v, label: v.replace("_", " ") })),
  { value: "none", label: "undecided" },
];

/**
 * All calls (PRO-571): every call the scanner has seen, the filter's rejects included, newest first,
 * 200 at a time. Its columns: Call, Filter, Votes, Description, AI reason, Notes, Due, First seen,
 * Decide. A decision here changes the call's (the newest wins), and every person's is kept.
 */
export default async function CallsPage({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  const [portalList, tagChoices, top] = await Promise.all([portals(), tagOptions(), topTenIds()]);
  const filters: CallFilters = {
    portals: pickMany(sp.portal, portalList.map((p) => p.name)),
    state: pickState(sp.state, sp.open),
    sort: pickSort(sp.sort, sp.dir, ["seen", "due", "title", "verdict", "decision", "filter"]),
    judges: pickJudgeFilter(sp.judges),
    filterResult: pickAllowed(sp.filter_result, FILTER_RESULTS),
    verdict: pickAllowed(sp.verdict, [...VERDICTS, "none"] as const),
    status: pickAllowed(sp.status, [...HUMAN_STATUSES, "none"] as const),
    q: firstParam(sp.q, 120),
    tag: pickAllowed(sp.tag, tagChoices.map((t) => t.name)),
  };
  const viewer = await currentViewer();
  const users = allowlist();
  const waitingFor = queueMode() === "each" && viewer ? aliasesFor(viewer, users) : null;
  const [{ rows, total }, counts, topCount, agreement] = await Promise.all([
    listCalls(filters, LIMIT),
    queueCounts(filters, waitingFor),
    countAmong(top.ids, filters),
    judgeAgreement(),
  ]);
  const ids = rows.map((r) => r.id);
  const [judged, decisions, tagRows] = await Promise.all([latestJudgments(ids), decisionsOn(ids), tagsOn(ids)]);
  const tagsFor = tagsByCall(tagRows);
  const tz = displayTimeZone();
  const show = shows(await hiddenColumns(), "calls");   // the columns chosen in Table settings
  const votes = votesByCall(decisions, (by) => displayPerson(by, users));
  // The view as link params: every bar control, header and decision keeps the rest of it.
  const barParams: Params = { portal: filters.portals, state: filters.state, tag: filters.tag };
  const params: Params = {
    q: filters.q,
    ...barParams,
    judges: filters.judges,
    filter_result: filters.filterResult,
    verdict: filters.verdict,
    status: filters.status,
    ...sortParams(filters.sort),
  };
  const filtered = Object.values(params).some((value) => value.length > 0);
  const columnFilter = Boolean(filters.q || filters.judges || filters.filterResult || filters.verdict || filters.status);
  const returnTo = filterHref("/calls", params);
  const now = Date.now();

  return (
    <Shell section="calls">
      <h1 className="sr-only">All calls</h1>
      <ViewCards
        label="Calls views"
        cards={callViewCards({
          current: columnFilter ? null : "all",
          params: barParams,
          counts: {
            "needs-review": counts.waiting,
            top10: topCount,
            "due-soon": counts.dueSoon,
            "judges-agree": counts.agree,
            "judges-disagree": counts.disagree,
            new: counts.fresh,
            all: total,
          },
          perPerson: Boolean(waitingFor),
          dueBy: dayMonth(new Date(now + DUE_SOON_DAYS * 24 * 3600 * 1000), tz),
          newSince: dayMonth(new Date(now - NEW_DAYS * 24 * 3600 * 1000), tz),
          briefWeek: top.week ? weekLabel(top.week) : null,
          agree: agreement,
        })}
      />

      <Flash notice={firstParam(sp.notice, 300)} error={firstParam(sp.error, 300)} />

      <FilterBar
        action="/calls"
        params={params}
        portals={portalList}
        selected={filters.portals}
        tags={tagChoices}
        tag={filters.tag}
        state={filters.state}
        search={filters.q}
        filtered={filtered}
        summary={`Showing ${rows.length} of ${total}${total > rows.length ? ", narrow the filters to see the rest" : ""}`}
      />

      <section>
        {rows.length === 0 ? (
          <div className="empty">
            <p className="title">{filtered ? "No calls match these filters." : "The ledger has no calls yet."}</p>
            <p className="muted">
              {filtered ? <a href="/calls">Clear filters</a> : "Calls appear after the first scan (python run.py)."}
            </p>
          </div>
        ) : (
          <div className="table-wrap">
            <table className="calls-table">
              <thead>
                <tr>
                  <HeaderCell label="Call" sort={sortLink("/calls", params, filters.sort, "title")} />
                  {show("filter") ? (
                    <HeaderCell
                      label="Filter"
                      sort={sortLink("/calls", params, filters.sort, "filter")}
                      menu={{
                        active: Boolean(filters.filterResult),
                        groups: [{ items: choiceLinks("/calls", params, "filter_result", FILTER_CHOICES, filters.filterResult) }],
                      }}
                    />
                  ) : null}
                  {show("votes") ? (
                    <HeaderCell
                      label="Votes"
                      sort={sortLink("/calls", params, filters.sort, "verdict")}
                      menu={{
                        active: Boolean(filters.verdict || filters.judges),
                        groups: [
                          { title: "Claude's verdict", items: choiceLinks("/calls", params, "verdict", VERDICT_CHOICES, filters.verdict) },
                          { title: "Judges", items: choiceLinks("/calls", params, "judges", JUDGE_CHOICES, filters.judges) },
                        ],
                      }}
                    />
                  ) : null}
                  {show("description") ? <HeaderCell label="Description" className="wide" /> : null}
                  {show("reason") ? <HeaderCell label="AI reason" className="wide" /> : null}
                  {show("notes") ? <HeaderCell label="Notes" /> : null}
                  {show("due") ? <HeaderCell label="Due" sort={sortLink("/calls", params, filters.sort, "due")} /> : null}
                  {show("seen") ? <HeaderCell label="First seen" sort={sortLink("/calls", params, filters.sort, "seen")} /> : null}
                  <HeaderCell
                    label="Decide"
                    className="decide"
                    sort={sortLink("/calls", params, filters.sort, "decision")}
                    menu={{ active: Boolean(filters.status), groups: [{ items: choiceLinks("/calls", params, "status", STATUS_CHOICES, filters.status) }] }}
                  />
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
                    <tr key={r.id} data-call-id={r.id}>
                      <CallCell
                        row={r}
                        tags={show("tags") ? (tagsFor.get(r.id) ?? []) : []}
                        details={show("details")}
                        reason={show("reason") ? r.ai_reasoning : null}
                      />
                      {show("filter") ? (
                        <td>
                          <Badge value={r.filter_result} />
                          {r.match_tier ? <div className="meta">{r.match_tier} tier</div> : null}
                          {r.filter_result === "rejected" && r.filter_reason ? <div className="meta">{r.filter_reason}</div> : null}
                        </td>
                      ) : null}
                      {show("votes") ? <VotesCell verdicts={verdictsFor(judged.get(r.id), r.ai_verdict, r.ai_reasoning)} votes={callVotes} /> : null}
                      {show("description") ? <DescriptionCell portal={r.portal} description={r.description} extra={r.extra} /> : null}
                      {show("reason") ? <td className="reason wide">{r.ai_reasoning ?? ""}</td> : null}
                      {show("notes") ? (
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
                      ) : null}
                      {show("due") ? <DueCell due={r.due_date} daysLeft={r.days_left} extra={r.extra} tz={tz} /> : null}
                      {show("seen") ? <td className="when">{formatTime(r.first_seen_at, tz)}</td> : null}
                      <td className="decide">
                        <Badge value={r.human_status} empty="undecided" />
                        {r.human_status ? (
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
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </Shell>
  );
}
