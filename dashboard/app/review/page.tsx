import type { Metadata } from "next";
import { decide } from "@/app/actions";
import { FilterBar } from "@/components/FilterBar";
import { HeaderCell } from "@/components/HeaderCell";
import { JudgeVerdicts } from "@/components/Judges";
import { Shell } from "@/components/Shell";
import { ViewCards } from "@/components/ViewCards";
import { Details, Flash, TitleLink } from "@/components/bits";
import { callDetails, deadlineNote, noDeadlineLabel } from "@/lib/details";
import { choiceLinks, filterHref, JUDGE_CHOICES, pickMany, pickSort, pickState, sortLink, sortParams, type Params, type Sort } from "@/lib/filters";
import { formatDue, formatTime } from "@/lib/format";
import { dayMonth } from "@/lib/home";
import { pickJudgeFilter, verdictsFor } from "@/lib/judges";
import { aliasesFor, displayPerson } from "@/lib/people";
import { countCalls, decisionsOn, latestJudgments, portals, queueCounts, reviewQueue, tagOptions, tagsOn } from "@/lib/queries";
import { tagsByCall, withoutTags } from "@/lib/tags";
import { peopleSplit, votesByCall } from "@/lib/scoreboard";
import { shows } from "@/lib/columns";
import { displayTimeZone, hiddenColumns, queueMode } from "@/lib/settings";
import { firstParam, isClosed, votedHref } from "@/lib/text";
import { DECISIONS, isDecision, pickAllowed, STATUS_LABELS } from "@/lib/values";
import { callViewCards, DUE_SOON_DAYS, pickCallView } from "@/lib/views";
import { allowlist, currentViewer } from "@/lib/viewer";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Needs review" };

const VIEW_TITLES = { "needs-review": "Needs review", "due-soon": "Due soon" } as const;
/** Due soon opens soonest first; Needs review newest first. */
const VIEW_SORTS: Record<keyof typeof VIEW_TITLES, Sort | undefined> = { "needs-review": undefined, "due-soon": { key: "due", dir: "asc" } };

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

const VERDICT_CHOICES = [
  { value: "", label: "Yes and maybe" },
  { value: "yes", label: "Yes" },
  { value: "maybe", label: "Maybe" },
];
const TIER_CHOICES = [
  { value: "", label: "Any" },
  { value: "tight", label: "Tight" },
  { value: "broad", label: "Broad" },
];

export default async function ReviewQueuePage({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  const voted = firstParam(sp.voted, 300);   // the call just voted on, for the notice's link
  const view = pickCallView(sp.view);
  const [portalList, tagChoices] = await Promise.all([portals(), tagOptions()]);
  const filters = {
    view,
    portals: pickMany(sp.portal, portalList.map((p) => p.name)),
    state: pickState(sp.state, sp.open),
    sort: pickSort(sp.sort, sp.dir, ["seen", "due", "title", "verdict", "tier"], VIEW_SORTS[view]),
    judges: pickJudgeFilter(sp.judges),
    verdict: pickAllowed(sp.verdict, ["yes", "maybe"] as const),
    tier: pickAllowed(sp.tier, ["tight", "broad"] as const),
    tag: pickAllowed(sp.tag, tagChoices.map((t) => t.name)),
  };
  // The view as link params: every bar control, header and decision keeps the rest of it.
  const columnParams: Params = {
    judges: filters.judges,
    verdict: filters.verdict,
    tier: filters.tier,
    ...sortParams(filters.sort, VIEW_SORTS[view]),
  };
  const barParams: Params = { portal: filters.portals, state: filters.state, tag: filters.tag };
  const params: Params = { view: view === "needs-review" ? "" : view, ...barParams, ...columnParams };

  // While everyone decides every call, the queue is the viewer's own: the calls they have not decided.
  const users = allowlist();
  const viewer = await currentViewer();
  const waitingFor = queueMode() === "each" && viewer ? aliasesFor(viewer, users) : null;
  const [{ rows, perPerson }, counts, total] = await Promise.all([
    reviewQueue(filters, waitingFor),
    queueCounts(filters, waitingFor),
    countCalls(filters),
  ]);
  const ids = rows.map((r) => r.id);
  const [judged, decisions, tagRows] = await Promise.all([latestJudgments(ids), decisionsOn(perPerson ? ids : []), tagsOn(ids)]);
  const tagsFor = tagsByCall(tagRows);
  const votes = votesByCall(decisions, (by) => displayPerson(by, users));
  const tz = displayTimeZone();
  const show = shows(await hiddenColumns(), "queue");   // the columns chosen in Table settings
  const returnTo = filterHref("/review", params);
  const filtered = Object.values({ ...barParams, ...columnParams }).some((value) => value.length > 0);
  const order = sp.sort !== undefined ? "" : view === "due-soon" ? ", closing soonest first" : ", newest first";
  const viewHome = view === "needs-review" ? "/review" : `/review?view=${view}`;
  const dueBy = dayMonth(new Date(Date.now() + DUE_SOON_DAYS * 24 * 3600 * 1000), tz);

  return (
    <Shell section="calls">
      <h1 className="sr-only">{VIEW_TITLES[view]}</h1>
      <ViewCards
        label="Calls views"
        cards={callViewCards({ current: view, params: barParams, counts: { "needs-review": counts.waiting, "due-soon": counts.dueSoon, all: total }, perPerson, dueBy })}
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
            <p className="title">
              {filtered
                ? "No calls match these filters."
                : view === "due-soon"
                  ? `Nothing waiting closes in the next ${DUE_SOON_DAYS} days.`
                  : perPerson
                    ? "Nothing waiting for you."
                    : "Nothing waiting for a decision."}
            </p>
            <p className="muted">
              New yes and maybe calls land here after each scan.{" "}
              {perPerson
                ? "A call leaves your list when you decide it and stays on everyone else's until they do."
                : "Deciding takes a call off this list."}{" "}
              Change a call&apos;s decision on <a href="/calls">All calls</a>.
            </p>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  {show("judges") ? (
                    <HeaderCell
                      label="Claude / Grok"
                      sort={sortLink("/review", params, filters.sort, "verdict", VIEW_SORTS[view])}
                      menu={{
                        active: Boolean(filters.verdict || filters.judges),
                        groups: [
                          { title: "Claude's verdict", items: choiceLinks("/review", params, "verdict", VERDICT_CHOICES, filters.verdict) },
                          { title: "Judges", items: choiceLinks("/review", params, "judges", JUDGE_CHOICES, filters.judges) },
                        ],
                      }}
                    />
                  ) : null}
                  <HeaderCell label="Call" sort={sortLink("/review", params, filters.sort, "title", VIEW_SORTS[view])} />
                  {show("due") ? <HeaderCell label="Due" sort={sortLink("/review", params, filters.sort, "due", VIEW_SORTS[view])} /> : null}
                  {show("tier") ? (
                    <HeaderCell
                      label="Tier"
                      sort={sortLink("/review", params, filters.sort, "tier", VIEW_SORTS[view])}
                      menu={{ active: Boolean(filters.tier), groups: [{ items: choiceLinks("/review", params, "tier", TIER_CHOICES, filters.tier) }] }}
                    />
                  ) : null}
                  {show("reason") ? <HeaderCell label="AI reason" /> : null}
                  {show("seen") ? <HeaderCell label="First seen" sort={sortLink("/review", params, filters.sort, "seen", VIEW_SORTS[view])} /> : null}
                  {perPerson && show("votes") ? <HeaderCell label="Decided so far" /> : null}
                  <HeaderCell label="Decide" />
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const label = r.title || r.id;
                  const callVotes = votes.get(r.id) ?? [];
                  const badges = show("tags") ? (tagsFor.get(r.id) ?? []) : [];
                  return (
                    <tr key={r.id} data-call-id={r.id}>
                      {show("judges") ? (
                        <td>
                          <JudgeVerdicts verdicts={verdictsFor(judged.get(r.id), r.ai_verdict, r.ai_reasoning)} reasonsFor={["grok"]} />
                        </td>
                      ) : null}
                      <td className="call">
                        <TitleLink title={r.title} url={r.url} fallback={r.id} />
                        <div className="meta">
                          <span>{r.portal}</span>
                          <Details items={withoutTags(callDetails(r), badges)} />
                          {isClosed(r.extra) ? <span className="badge tone-grey">closed</span> : null}
                        </div>
                        {badges.length ? (
                          <div className="meta tags">
                            <Details items={badges} />
                          </div>
                        ) : null}
                      </td>
                      {show("due") ? (
                        <td className="when" title={deadlineNote(r.extra) ?? undefined}>{formatDue(r.due_date, tz) || <span className="muted">{noDeadlineLabel(r.extra)}</span>}</td>
                      ) : null}
                      {show("tier") ? <td>{r.match_tier ?? ""}</td> : null}
                      {show("reason") ? <td className="reason">{r.ai_reasoning ?? ""}</td> : null}
                      {show("seen") ? <td className="when">{formatTime(r.first_seen_at, tz)}</td> : null}
                      {perPerson && show("votes") ? (
                        <td>
                          {callVotes.length ? (
                            <ul className="notes votes">
                              {callVotes.map((v) => (
                                <li key={v.person}>
                                  {v.person}: {isDecision(v.status) ? STATUS_LABELS[v.status] : v.status}
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <span className="muted">nobody yet</span>
                          )}
                          {peopleSplit(callVotes) ? <span className="badge tone-warn">people disagree</span> : null}
                        </td>
                      ) : null}
                      <td className="decide">
                        <form action={decide}>
                          <input type="hidden" name="id" value={r.id} />
                          <input type="hidden" name="expected" value={isDecision(r.human_status) ? r.human_status : ""} />
                          {perPerson ? <input type="hidden" name="keep" value="1" /> : null}
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
    </Shell>
  );
}
