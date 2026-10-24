import type { Metadata } from "next";
import { decide } from "../actions";
import { FilterBar } from "@/components/FilterBar";
import { HeaderCell } from "@/components/HeaderCell";
import { JudgeVerdicts } from "@/components/Judges";
import { Shell } from "@/components/Shell";
import { Badge, Details, Flash, TitleLink } from "@/components/bits";
import { callDetails, deadlineNote, noDeadlineLabel } from "@/lib/details";
import { displayPerson } from "@/lib/people";
import { choiceLinks, filterHref, JUDGE_CHOICES, pickMany, pickSort, pickState, sortLink, sortParams, type Params } from "@/lib/filters";
import { formatDue, formatTime } from "@/lib/format";
import { agreementText, pickJudgeFilter, verdictsFor } from "@/lib/judges";
import { decisionsOn, judgeAgreement, latestJudgments, listCalls, portals, tagOptions, tagsOn, type CallFilters } from "@/lib/queries";
import { tagsByCall, withoutTags } from "@/lib/tags";
import { peopleSplit, votesByCall } from "@/lib/scoreboard";
import { shows } from "@/lib/columns";
import { displayTimeZone, hiddenColumns } from "@/lib/settings";
import { firstParam, isClosed, parseNoteLine } from "@/lib/text";
import { DECISIONS, FILTER_RESULTS, HUMAN_STATUSES, isDecision, pickAllowed, STATUS_LABELS, VERDICTS } from "@/lib/values";
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

export default async function CallsPage({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  const [portalList, tagChoices] = await Promise.all([portals(), tagOptions()]);
  const filters: CallFilters = {
    portals: pickMany(sp.portal, portalList),
    state: pickState(sp.state, sp.open),
    sort: pickSort(sp.sort, sp.dir, ["seen", "due", "title", "verdict", "decision", "filter"]),
    judges: pickJudgeFilter(sp.judges),
    filterResult: pickAllowed(sp.filter_result, FILTER_RESULTS),
    verdict: pickAllowed(sp.verdict, [...VERDICTS, "none"] as const),
    status: pickAllowed(sp.status, [...HUMAN_STATUSES, "none"] as const),
    q: firstParam(sp.q, 120),
    tag: pickAllowed(sp.tag, tagChoices.map((t) => t.name)),
  };
  const [{ rows, total }, agreement] = await Promise.all([listCalls(filters, LIMIT), judgeAgreement()]);
  const ids = rows.map((r) => r.id);
  const [judged, decisions, viewer, tagRows] = await Promise.all([latestJudgments(ids), decisionsOn(ids), currentViewer(), tagsOn(ids)]);
  const tagsFor = tagsByCall(tagRows);
  const tz = displayTimeZone();
  const show = shows(await hiddenColumns(), "calls");   // the columns chosen in Settings
  const users = allowlist();
  const votes = votesByCall(decisions, (by) => displayPerson(by, users));
  // The view as link params: every bar control, header and decision keeps the rest of it.
  const params: Params = {
    q: filters.q,
    portal: filters.portals,
    state: filters.state,
    tag: filters.tag,
    judges: filters.judges,
    filter_result: filters.filterResult,
    verdict: filters.verdict,
    status: filters.status,
    ...sortParams(filters.sort),
  };
  const filtered = Object.values(params).some((value) => value.length > 0);
  const returnTo = filterHref("/calls", params);

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
      />

      <section>
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
                  {show("judges") ? (
                    <HeaderCell
                      label="Claude / Grok"
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
                  <HeaderCell
                    label="Decision"
                    sort={sortLink("/calls", params, filters.sort, "decision")}
                    menu={{ active: Boolean(filters.status), groups: [{ items: choiceLinks("/calls", params, "status", STATUS_CHOICES, filters.status) }] }}
                  />
                  {show("notes") ? <HeaderCell label="Notes" /> : null}
                  {show("due") ? <HeaderCell label="Due" sort={sortLink("/calls", params, filters.sort, "due")} /> : null}
                  {show("seen") ? <HeaderCell label="First seen" sort={sortLink("/calls", params, filters.sort, "seen")} /> : null}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const notes = (r.human_notes ?? "").split("\n").filter(Boolean).map(parseNoteLine);
                  const callVotes = votes.get(r.id) ?? [];
                  const decidedByViewer = callVotes.length
                    ? callVotes.some((v) => v.person === viewer)
                    : displayPerson(r.human_by, users) === viewer;
                  const badges = show("tags") ? (tagsFor.get(r.id) ?? []) : [];
                  return (
                    <tr key={r.id}>
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
                      {show("filter") ? (
                        <td>
                          <Badge value={r.filter_result} />
                          {r.match_tier ? <div className="meta">{r.match_tier} tier</div> : null}
                          {r.filter_result === "rejected" && r.filter_reason ? <div className="meta">{r.filter_reason}</div> : null}
                        </td>
                      ) : null}
                      {show("judges") ? (
                        <td>
                          <JudgeVerdicts verdicts={verdictsFor(judged.get(r.id), r.ai_verdict, r.ai_reasoning)} reasonsFor={["claude", "grok"]} />
                        </td>
                      ) : null}
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
                      {show("due") ? (
                        <td className="when" title={deadlineNote(r.extra) ?? undefined}>{formatDue(r.due_date, tz) || <span className="muted">{noDeadlineLabel(r.extra)}</span>}</td>
                      ) : null}
                      {show("seen") ? <td className="when">{formatTime(r.first_seen_at, tz)}</td> : null}
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
