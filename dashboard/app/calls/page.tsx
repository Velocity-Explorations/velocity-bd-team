import type { Metadata } from "next";
import { CallCell, DescriptionCell, DueCell, VotesCell } from "@/components/CallCells";
import { DecideCell } from "@/components/DecideCell";
import { FilterBar } from "@/components/FilterBar";
import { HeaderCell } from "@/components/HeaderCell";
import { NotesPanel, ReasonsPanel } from "@/components/RowPanels";
import { Shell } from "@/components/Shell";
import { ViewCards } from "@/components/ViewCards";
import { Badge, Flash } from "@/components/bits";
import { weekLabel } from "@/lib/brief";
import { shows } from "@/lib/columns";
import { yourVote } from "@/lib/decide";
import { callDetails, deadlineNote } from "@/lib/details";
import { detailSources } from "@/lib/description";
import { choiceLinks, filterHref, JUDGE_CHOICES, pickMany, pickSort, pickState, sortChoices, sortLink, sortParams, type Params } from "@/lib/filters";
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
import { FILTER_RESULTS, HUMAN_STATUSES, pickAllowed, VERDICTS } from "@/lib/values";
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
 * All calls (PRO-571, PRO-572): every call the scanner has seen, the filter's rejects included, newest
 * first, 200 at a time. Its columns: Call, Filter, Votes, Description, AI reason, Due, First seen,
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
    desc: firstParam(sp.desc, 120),
    why: firstParam(sp.why, 120),
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
  const nameOf = (by: string | null) => displayPerson(by, users);
  const votes = votesByCall(decisions, nameOf);
  // The view as link params: every bar control, header and decision keeps the rest of it.
  const barParams: Params = { portal: filters.portals, state: filters.state, tag: filters.tag };
  const params: Params = {
    q: filters.q ?? "",
    desc: filters.desc ?? "",
    why: filters.why ?? "",
    ...barParams,
    judges: filters.judges,
    filter_result: filters.filterResult,
    verdict: filters.verdict,
    status: filters.status,
    ...sortParams(filters.sort),
  };
  const filtered = Object.values(params).some((value) => value.length > 0);
  const columnFilter = Boolean(filters.q || filters.desc || filters.why || filters.judges || filters.filterResult || filters.verdict || filters.status);
  const returnTo = filterHref("/calls", params);
  const now = Date.now();
  const colSpan = 2 + ["filter", "votes", "description", "reason", "due", "seen"].filter((key) => show(key)).length;
  const search = (name: "q" | "desc" | "why", placeholder: string) => ({ action: "/calls", name, value: filters[name] ?? "", params, placeholder });

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
                  <HeaderCell
                    label="Call"
                    sort={sortLink("/calls", params, filters.sort, "title")}
                    menu={{ sorts: sortChoices("/calls", params, filters.sort, "title"), search: search("q", "Search titles, Enter to apply"), active: Boolean(filters.q) }}
                  />
                  {show("filter") ? (
                    <HeaderCell
                      label="Filter"
                      sort={sortLink("/calls", params, filters.sort, "filter")}
                      menu={{
                        sorts: sortChoices("/calls", params, filters.sort, "filter"),
                        active: Boolean(filters.filterResult),
                        groups: [{ title: "Filter result", items: choiceLinks("/calls", params, "filter_result", FILTER_CHOICES, filters.filterResult) }],
                        hide: { page: "calls", key: "filter" },
                      }}
                    />
                  ) : null}
                  {show("votes") ? (
                    <HeaderCell
                      label="Votes"
                      sort={sortLink("/calls", params, filters.sort, "verdict")}
                      menu={{
                        sorts: sortChoices("/calls", params, filters.sort, "verdict"),
                        active: Boolean(filters.verdict || filters.judges),
                        groups: [
                          { title: "Claude's verdict", items: choiceLinks("/calls", params, "verdict", VERDICT_CHOICES, filters.verdict) },
                          { title: "Judges", items: choiceLinks("/calls", params, "judges", JUDGE_CHOICES, filters.judges) },
                        ],
                        hide: { page: "calls", key: "votes" },
                      }}
                    />
                  ) : null}
                  {show("description") ? (
                    <HeaderCell
                      label="Description"
                      className="wide"
                      menu={{ search: search("desc", "Search descriptions, Enter to apply"), active: Boolean(filters.desc), hide: { page: "calls", key: "description" } }}
                    />
                  ) : null}
                  {show("reason") ? (
                    <HeaderCell
                      label="AI reason"
                      className="wide"
                      menu={{ search: search("why", "Search reasons, Enter to apply"), active: Boolean(filters.why), hide: { page: "calls", key: "reason" } }}
                    />
                  ) : null}
                  {show("due") ? (
                    <HeaderCell
                      label="Due"
                      sort={sortLink("/calls", params, filters.sort, "due")}
                      menu={{ sorts: sortChoices("/calls", params, filters.sort, "due"), hide: { page: "calls", key: "due" } }}
                    />
                  ) : null}
                  {show("seen") ? (
                    <HeaderCell
                      label="First seen"
                      sort={sortLink("/calls", params, filters.sort, "seen")}
                      menu={{ sorts: sortChoices("/calls", params, filters.sort, "seen"), hide: { page: "calls", key: "seen" } }}
                    />
                  ) : null}
                  <HeaderCell
                    label="Decide"
                    className="decide"
                    sort={sortLink("/calls", params, filters.sort, "decision")}
                    menu={{
                      sorts: sortChoices("/calls", params, filters.sort, "decision"),
                      active: Boolean(filters.status),
                      groups: [{ title: "Decision", items: choiceLinks("/calls", params, "status", STATUS_CHOICES, filters.status) }],
                    }}
                  />
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const notes = (r.human_notes ?? "").split("\n").filter(Boolean).map(parseNoteLine);
                  const callVotes = votes.get(r.id) ?? [];
                  const verdicts = verdictsFor(judged.get(r.id), r.ai_verdict, r.ai_reasoning);
                  const rank = top.ids.indexOf(r.id);
                  return [
                    <tr key={r.id} data-call-id={r.id}>
                      <CallCell
                        row={r}
                        tags={show("tags") ? (tagsFor.get(r.id) ?? []) : []}
                        details={show("details")}
                        reason={show("reason") ? r.ai_reasoning : null}
                        topRank={rank >= 0 ? rank + 1 : undefined}
                      />
                      {show("filter") ? (
                        <td>
                          <Badge value={r.filter_result} />
                          {r.match_tier ? <div className="meta">{r.match_tier} tier</div> : null}
                          {r.filter_result === "rejected" && r.filter_reason ? <div className="meta">{r.filter_reason}</div> : null}
                        </td>
                      ) : null}
                      {show("votes") ? (
                        <VotesCell callId={r.id} verdicts={verdicts} votes={callVotes} notesBy={new Set(notes.map((n) => nameOf(n.by)).filter(Boolean))} />
                      ) : null}
                      {show("description") ? <DescriptionCell portal={r.portal} description={r.description} extra={r.extra} /> : null}
                      {show("reason") ? <td className="reason wide">{r.ai_reasoning ?? ""}</td> : null}
                      {show("due") ? <DueCell due={r.due_date} daysLeft={r.days_left} extra={r.extra} tz={tz} /> : null}
                      {show("seen") ? <td className="when">{formatTime(r.first_seen_at, tz)}</td> : null}
                      <DecideCell
                        call={r}
                        mode="all"
                        viewer={viewer}
                        yours={yourVote(callVotes, viewer)}
                        eligible={r.filter_result === "kept" && (r.ai_verdict === "yes" || r.ai_verdict === "maybe")}
                        decidedBy={nameOf(r.human_by)}
                        returnTo={returnTo}
                        keep={false}
                        note
                        tz={tz}
                      />
                    </tr>,
                    <ReasonsPanel
                      key={`reasons-${r.id}`}
                      callId={r.id}
                      colSpan={colSpan}
                      verdicts={verdicts}
                      sources={detailSources(callDetails(r), deadlineNote(r.extra))}
                    />,
                    notes.length ? <NotesPanel key={`notes-${r.id}`} callId={r.id} colSpan={colSpan} notes={notes} nameOf={nameOf} tz={tz} /> : null,
                  ];
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </Shell>
  );
}
