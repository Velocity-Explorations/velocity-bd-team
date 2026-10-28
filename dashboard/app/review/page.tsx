import type { Metadata } from "next";
import { CallCell, DescriptionCell, DueCell, VotesCell } from "@/components/CallCells";
import { DecideCell } from "@/components/DecideCell";
import { FilterBar } from "@/components/FilterBar";
import { HeaderCell } from "@/components/HeaderCell";
import { NotesPanel, ReasonsPanel } from "@/components/RowPanels";
import { Shell } from "@/components/Shell";
import { ViewCards } from "@/components/ViewCards";
import { Flash } from "@/components/bits";
import { weekLabel } from "@/lib/brief";
import { shows } from "@/lib/columns";
import { yourVote } from "@/lib/decide";
import { callDetails, deadlineNote } from "@/lib/details";
import { detailSources } from "@/lib/description";
import { choiceLinks, filterHref, JUDGE_CHOICES, pickMany, pickSort, pickState, sortChoices, sortLink, sortParams, type Params, type Sort } from "@/lib/filters";
import { formatTime } from "@/lib/format";
import { dayMonth } from "@/lib/home";
import { pickJudgeFilter, verdictsFor, type JudgeFilter } from "@/lib/judges";
import { aliasesFor, displayPerson } from "@/lib/people";
import {
  countAmong,
  countCalls,
  decisionsOn,
  judgeAgreement,
  latestJudgments,
  portals,
  queueCounts,
  reviewQueue,
  tagOptions,
  tagsOn,
  topTenIds,
} from "@/lib/queries";
import { votesByCall } from "@/lib/scoreboard";
import { displayTimeZone, hiddenColumns, queueMode } from "@/lib/settings";
import { tagsByCall } from "@/lib/tags";
import { firstParam, parseNoteLine, votedHref } from "@/lib/text";
import { pickAllowed } from "@/lib/values";
import { callViewCards, DUE_SOON_DAYS, NEW_DAYS, pickCallView, pressedCard, viewJudges, VIEW_LABELS, type CallView } from "@/lib/views";
import { allowlist, currentViewer } from "@/lib/viewer";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Needs review" };

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

/** A view's own first sort: Due soon closing soonest first; the rest newest first (Top 10 in the brief's order). */
const VIEW_SORTS: Partial<Record<CallView, Sort>> = { "due-soon": { key: "due", dir: "asc" } };

const VERDICT_CHOICES = [
  { value: "", label: "Yes and maybe" },
  { value: "yes", label: "Yes" },
  { value: "maybe", label: "Maybe" },
];

/** What an empty view says (Q11). */
function emptyTitle(view: CallView, filtered: boolean, perPerson: boolean): string {
  if (filtered) return "No calls match these filters.";
  switch (view) {
    case "top10":
      return "Nothing to rank yet.";
    case "due-soon":
      return `Nothing waiting closes in the next ${DUE_SOON_DAYS} days.`;
    case "judges-agree":
      return "No waiting call where Claude and Grok agree.";
    case "judges-disagree":
      return "No waiting call where Claude and Grok disagree.";
    case "new":
      return "Nothing new this week.";
    default:
      return perPerson ? "Nothing waiting for you." : "Nothing waiting for a decision.";
  }
}

/**
 * Needs review and its views (PRO-570, PRO-571, PRO-572): the calls waiting for the viewer, narrowed
 * to Due soon, Judges agree or disagree, or New this week; and Top 10, this week's ten, decided or
 * not. Opened from Home's Top 10, the chosen call is marked and focused with its reasons open.
 */
export default async function NeedsReviewPage({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  const voted = firstParam(sp.voted, 300);   // the call just voted on, for the notice's link
  const view = pickCallView(sp.view);
  const viewSort = VIEW_SORTS[view];
  const focusId = view === "top10" ? firstParam(sp.focus, 300) : "";
  const [portalList, tagChoices, top] = await Promise.all([portals(), tagOptions(), topTenIds()]);
  const asked = pickJudgeFilter(sp.judges);
  const filters = {
    view,
    ids: top.ids,
    portals: pickMany(sp.portal, portalList.map((p) => p.name)),
    state: pickState(sp.state, sp.open),
    sort: pickSort(sp.sort, sp.dir, ["seen", "due", "title", "verdict"], viewSort),
    judges: viewJudges(view, asked) as JudgeFilter,
    verdict: pickAllowed(sp.verdict, ["yes", "maybe"] as const),
    tier: pickAllowed(sp.tier, ["tight", "broad"] as const),
    tag: pickAllowed(sp.tag, tagChoices.map((t) => t.name)),
    q: firstParam(sp.q, 120),
    desc: firstParam(sp.desc, 120),
    why: firstParam(sp.why, 120),
  };
  // The view as link params: every bar control, header and decision keeps the rest of it.
  const columnParams: Params = {
    judges: view === "judges-agree" || view === "judges-disagree" ? "" : filters.judges,
    verdict: filters.verdict,
    tier: filters.tier,
    q: filters.q,
    desc: filters.desc,
    why: filters.why,
    ...sortParams(filters.sort, viewSort),
  };
  const barParams: Params = { portal: filters.portals, state: filters.state, tag: filters.tag };
  const params: Params = { view: view === "needs-review" ? "" : view, ...barParams, ...columnParams };

  // While everyone decides every call, the queue is the viewer's own: the calls they have not decided.
  const users = allowlist();
  const viewer = await currentViewer();
  const waitingFor = queueMode() === "each" && viewer ? aliasesFor(viewer, users) : null;
  const [queue, counts, total, topCount, agreement] = await Promise.all([
    reviewQueue(filters, waitingFor),
    queueCounts(filters, waitingFor),
    countCalls(filters),
    countAmong(top.ids, filters),
    judgeAgreement(),
  ]);
  const { perPerson } = queue;
  // Top 10 keeps the brief's order unless a header sorts it.
  const rows = view === "top10" && sp.sort === undefined
    ? [...queue.rows].sort((a, b) => top.ids.indexOf(a.id) - top.ids.indexOf(b.id))
    : queue.rows;
  const ids = rows.map((r) => r.id);
  const [judged, decisions, tagRows] = await Promise.all([latestJudgments(ids), decisionsOn(ids), tagsOn(ids)]);
  const tagsFor = tagsByCall(tagRows);
  const votes = votesByCall(decisions, (by) => displayPerson(by, users));
  const nameOf = (by: string | null) => displayPerson(by, users);
  const tz = displayTimeZone();
  const show = shows(await hiddenColumns(), "queue");   // the columns chosen in Table settings
  const returnTo = filterHref("/review", params);
  const filtered = Object.values({ ...barParams, ...columnParams }).some((value) => value.length > 0);
  const order = sp.sort !== undefined ? "" : view === "due-soon" ? ", closing soonest first" : view === "top10" ? ", in the brief's order" : ", newest first";
  const viewHome = view === "needs-review" ? "/review" : `/review?view=${view}`;
  const now = Date.now();
  const keywords = Boolean(filters.q || filters.desc || filters.why);
  const pressed = keywords ? null : pressedCard(view, { judges: columnParams.judges as string, verdict: filters.verdict, tier: filters.tier });
  const listVotes = perPerson || view === "top10";
  const colSpan = 2 + ["votes", "description", "reason", "due", "seen"].filter((key) => show(key)).length;
  const search = (name: "q" | "desc" | "why", placeholder: string) => ({ action: "/review", name, value: filters[name], params, placeholder });

  return (
    <Shell section="calls">
      <h1 className="sr-only">{VIEW_LABELS[view]}</h1>
      <ViewCards
        label="Calls views"
        cards={callViewCards({
          current: pressed,
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
          perPerson,
          dueBy: dayMonth(new Date(now + DUE_SOON_DAYS * 24 * 3600 * 1000), tz),
          newSince: dayMonth(new Date(now - NEW_DAYS * 24 * 3600 * 1000), tz),
          briefWeek: top.week ? weekLabel(top.week) : null,
          agree: agreement,
        })}
      />

      <Flash notice={firstParam(sp.notice, 300)} error={firstParam(sp.error, 300)} link={voted ? { href: votedHref(voted), label: "See everyone's votes on All calls" } : null} />

      <FilterBar
        action="/review"
        params={params}
        portals={portalList}
        selected={filters.portals}
        tags={tagChoices}
        tag={filters.tag}
        state={filters.state}
        filtered={filtered}
        clearHref={viewHome}
        summary={`${rows.length} ${rows.length === 1 ? "call" : "calls"}${order}`}
      />

      <section>
        {rows.length === 0 ? (
          <div className="empty">
            <p className="title">{emptyTitle(view, filtered, perPerson)}</p>
            <p className="muted">
              New yes and maybe calls land here after each scan.{" "}
              {perPerson
                ? "A call leaves your list when you decide it and stays on everyone else's until they do."
                : "Deciding takes a call off this list."}{" "}
              {filtered ? <a href={viewHome}>Clear filters</a> : <>Change a call&apos;s decision on <a href="/calls">All calls</a>.</>}
            </p>
          </div>
        ) : (
          <div className="table-wrap">
            <table className="calls-table">
              <thead>
                <tr>
                  <HeaderCell
                    label="Call"
                    sort={sortLink("/review", params, filters.sort, "title", viewSort)}
                    menu={{
                      sorts: sortChoices("/review", params, filters.sort, "title", viewSort),
                      search: search("q", "Search titles, Enter to apply"),
                      active: Boolean(filters.q),
                    }}
                  />
                  {show("votes") ? (
                    <HeaderCell
                      label="Votes"
                      sort={sortLink("/review", params, filters.sort, "verdict", viewSort)}
                      menu={{
                        sorts: sortChoices("/review", params, filters.sort, "verdict", viewSort),
                        active: Boolean(filters.verdict || columnParams.judges),
                        groups: [
                          { title: "Claude's verdict", items: choiceLinks("/review", params, "verdict", VERDICT_CHOICES, filters.verdict) },
                          ...(view === "judges-agree" || view === "judges-disagree"
                            ? []
                            : [{ title: "Judges", items: choiceLinks("/review", params, "judges", JUDGE_CHOICES, filters.judges) }]),
                        ],
                        hide: { page: "queue", key: "votes" },
                      }}
                    />
                  ) : null}
                  {show("description") ? (
                    <HeaderCell
                      label="Description"
                      className="wide"
                      menu={{ search: search("desc", "Search descriptions, Enter to apply"), active: Boolean(filters.desc), hide: { page: "queue", key: "description" } }}
                    />
                  ) : null}
                  {show("reason") ? (
                    <HeaderCell
                      label="AI reason"
                      className="wide"
                      menu={{ search: search("why", "Search reasons, Enter to apply"), active: Boolean(filters.why), hide: { page: "queue", key: "reason" } }}
                    />
                  ) : null}
                  {show("due") ? (
                    <HeaderCell
                      label="Due"
                      sort={sortLink("/review", params, filters.sort, "due", viewSort)}
                      menu={{ sorts: sortChoices("/review", params, filters.sort, "due", viewSort), hide: { page: "queue", key: "due" } }}
                    />
                  ) : null}
                  {show("seen") ? (
                    <HeaderCell
                      label="First seen"
                      sort={sortLink("/review", params, filters.sort, "seen", viewSort)}
                      menu={{ sorts: sortChoices("/review", params, filters.sort, "seen", viewSort), hide: { page: "queue", key: "seen" } }}
                    />
                  ) : null}
                  <HeaderCell label="Decide" className="decide" />
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const callVotes = votes.get(r.id) ?? [];
                  const notes = (r.human_notes ?? "").split("\n").filter(Boolean).map(parseNoteLine);
                  const verdicts = verdictsFor(judged.get(r.id), r.ai_verdict, r.ai_reasoning);
                  const focused = r.id === focusId;
                  const rank = top.ids.indexOf(r.id);
                  return [
                    <tr
                      key={r.id}
                      data-call-id={r.id}
                      className={focused ? "focused panel-open" : undefined}
                      data-focus={focused ? "" : undefined}
                      tabIndex={focused ? -1 : undefined}
                    >
                      <CallCell
                        row={r}
                        tags={show("tags") ? (tagsFor.get(r.id) ?? []) : []}
                        details={show("details")}
                        reason={show("reason") ? r.ai_reasoning : null}
                        topRank={rank >= 0 ? rank + 1 : undefined}
                      />
                      {show("votes") ? (
                        <VotesCell
                          callId={r.id}
                          verdicts={verdicts}
                          votes={listVotes ? callVotes : null}
                          notesBy={new Set(notes.map((n) => nameOf(n.by)).filter(Boolean))}
                        />
                      ) : null}
                      {show("description") ? <DescriptionCell portal={r.portal} description={r.description} extra={r.extra} /> : null}
                      {show("reason") ? <td className="reason wide">{r.ai_reasoning ?? ""}</td> : null}
                      {show("due") ? <DueCell due={r.due_date} daysLeft={r.days_left} extra={r.extra} tz={tz} /> : null}
                      {show("seen") ? <td className="when">{formatTime(r.first_seen_at, tz)}</td> : null}
                      <DecideCell
                        call={r}
                        mode={view === "top10" ? "mixed" : "waiting"}
                        viewer={viewer}
                        yours={yourVote(callVotes, viewer)}
                        eligible
                        decidedBy=""
                        returnTo={returnTo}
                        keep={perPerson || Boolean(r.human_status)}
                        note={show("note")}
                        tz={tz}
                      />
                    </tr>,
                    <ReasonsPanel
                      key={`reasons-${r.id}`}
                      callId={r.id}
                      colSpan={colSpan}
                      verdicts={verdicts}
                      sources={detailSources(callDetails(r), deadlineNote(r.extra))}
                      open={focused}
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
