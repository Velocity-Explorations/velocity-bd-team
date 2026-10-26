import type { Metadata } from "next";
import { decide } from "./actions";
import { FilterBar } from "@/components/FilterBar";
import { HeaderCell } from "@/components/HeaderCell";
import { JudgeVerdicts } from "@/components/Judges";
import { Shell } from "@/components/Shell";
import { Details, Flash, TitleLink } from "@/components/bits";
import { callDetails, deadlineNote, noDeadlineLabel } from "@/lib/details";
import { choiceLinks, filterHref, JUDGE_CHOICES, pickMany, pickSort, pickState, sortLink, sortParams, type Params } from "@/lib/filters";
import { formatDue, formatTime } from "@/lib/format";
import { agreementText, pickJudgeFilter, verdictsFor } from "@/lib/judges";
import { aliasesFor, displayPerson } from "@/lib/people";
import { decisionsOn, judgeAgreement, latestJudgments, newThisWeek, portals, reviewQueue, tagOptions, tagsOn } from "@/lib/queries";
import { tagsByCall, withoutTags } from "@/lib/tags";
import { peopleSplit, votesByCall } from "@/lib/scoreboard";
import { shows } from "@/lib/columns";
import { displayTimeZone, hiddenColumns, queueMode } from "@/lib/settings";
import { firstParam, isClosed, votedHref } from "@/lib/text";
import { DECISIONS, isDecision, pickAllowed, STATUS_LABELS } from "@/lib/values";
import { allowlist, currentViewer } from "@/lib/viewer";

export const dynamic = "force-dynamic";
// The title template in layout.tsx only applies below the root segment, so this one is spelled out.
export const metadata: Metadata = { title: "Review queue | Velocity BD" };

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
  const [portalList, tagChoices] = await Promise.all([portals(), tagOptions()]);
  const filters = {
    portals: pickMany(sp.portal, portalList.map((p) => p.name)),
    state: pickState(sp.state, sp.open),
    sort: pickSort(sp.sort, sp.dir, ["seen", "due", "title", "verdict", "tier"]),
    judges: pickJudgeFilter(sp.judges),
    verdict: pickAllowed(sp.verdict, ["yes", "maybe"] as const),
    tier: pickAllowed(sp.tier, ["tight", "broad"] as const),
    tag: pickAllowed(sp.tag, tagChoices.map((t) => t.name)),
  };
  // The view as link params: every bar control, header and decision keeps the rest of it.
  const params: Params = {
    portal: filters.portals,
    state: filters.state,
    tag: filters.tag,
    judges: filters.judges,
    verdict: filters.verdict,
    tier: filters.tier,
    ...sortParams(filters.sort),
  };

  // While everyone decides every call, the queue is the viewer's own: the calls they have not decided.
  const users = allowlist();
  const viewer = await currentViewer();
  const waitingFor = queueMode() === "each" && viewer ? aliasesFor(viewer, users) : null;
  const [{ rows, perPerson }, weekCount, agreement] = await Promise.all([
    reviewQueue(filters, waitingFor),
    newThisWeek(),
    judgeAgreement(),
  ]);
  const ids = rows.map((r) => r.id);
  const [judged, decisions, tagRows] = await Promise.all([latestJudgments(ids), decisionsOn(perPerson ? ids : []), tagsOn(ids)]);
  const tagsFor = tagsByCall(tagRows);
  const votes = votesByCall(decisions, (by) => displayPerson(by, users));
  const tz = displayTimeZone();
  const show = shows(await hiddenColumns(), "queue");   // the columns chosen in Settings
  const returnTo = filterHref("/", params);
  const yesCount = rows.filter((r) => r.ai_verdict === "yes").length;
  const filtered = Object.values(params).some((value) => value.length > 0);

  return (
    <Shell current="queue">
      <div className="page-head">
        <div>
          <h1>Review queue</h1>
          <p className="muted">
            {perPerson
              ? "Calls the reviewer rated yes or maybe that you have not decided yet. While the judges are being trained, everyone decides every call: the first decision becomes the call's decision, and later ones are kept beside it."
              : "Calls the reviewer rated yes or maybe that nobody has decided on yet."}
          </p>
        </div>
        <dl className="stats">
          <div>
            <dt>{perPerson ? "Waiting for you" : "Waiting"}</dt>
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
          {agreement && agreement.both ? (
            <div title={agreementText(agreement.both, agreement.agree)}>
              <dt>Judges agree</dt>
              <dd>{Math.round((100 * agreement.agree) / agreement.both)}%</dd>
            </div>
          ) : null}
        </dl>
      </div>

      <Flash notice={firstParam(sp.notice, 300)} error={firstParam(sp.error, 300)} link={voted ? { href: votedHref(voted), label: "See everyone's votes on All calls" } : null} />

      <FilterBar
        action="/"
        params={params}
        portals={portalList}
        selected={filters.portals}
        tags={tagChoices}
        tag={filters.tag}
        state={filters.state}
        filtered={filtered}
      />

      <section>
        {rows.length === 0 ? (
          <div className="empty">
            <p className="title">
              {filtered ? "No calls match these filters." : perPerson ? "Nothing waiting for you." : "Nothing waiting for a decision."}
            </p>
            <p className="muted">
              New yes and maybe calls land here after each scan.{" "}
              {perPerson
                ? "A call leaves your list when you decide it and stays on everyone else's until they do."
                : "Deciding takes a call off this list."}{" "}
              Change a call&apos;s decision on All calls.
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
                      sort={sortLink("/", params, filters.sort, "verdict")}
                      menu={{
                        active: Boolean(filters.verdict || filters.judges),
                        groups: [
                          { title: "Claude's verdict", items: choiceLinks("/", params, "verdict", VERDICT_CHOICES, filters.verdict) },
                          { title: "Judges", items: choiceLinks("/", params, "judges", JUDGE_CHOICES, filters.judges) },
                        ],
                      }}
                    />
                  ) : null}
                  <HeaderCell label="Call" sort={sortLink("/", params, filters.sort, "title")} />
                  {show("due") ? <HeaderCell label="Due" sort={sortLink("/", params, filters.sort, "due")} /> : null}
                  {show("tier") ? (
                    <HeaderCell
                      label="Tier"
                      sort={sortLink("/", params, filters.sort, "tier")}
                      menu={{ active: Boolean(filters.tier), groups: [{ items: choiceLinks("/", params, "tier", TIER_CHOICES, filters.tier) }] }}
                    />
                  ) : null}
                  {show("reason") ? <HeaderCell label="AI reason" /> : null}
                  {show("seen") ? <HeaderCell label="First seen" sort={sortLink("/", params, filters.sort, "seen")} /> : null}
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
