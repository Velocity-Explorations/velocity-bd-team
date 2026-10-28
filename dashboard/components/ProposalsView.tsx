import { FolderOpen } from "lucide-react";
import { CallCell, DueCell } from "@/components/CallCells";
import { FilterBar } from "@/components/FilterBar";
import { HeaderCell } from "@/components/HeaderCell";
import { Shell } from "@/components/Shell";
import { ViewCards } from "@/components/ViewCards";
import { Badge, Flash } from "@/components/bits";
import { filterHref, pickMany, pickState, type Params } from "@/lib/filters";
import { formatTime } from "@/lib/format";
import { dayMonth } from "@/lib/home";
import { verdictsFor, type Verdicts } from "@/lib/judges";
import { labeler, timeZone } from "@/lib/me";
import { displayPerson } from "@/lib/people";
import {
  draftBlock,
  proposalCards,
  resultExpected,
  sortIntoViews,
  stepLabel,
  stepStateWords,
  waitingDays,
  CLOSING_DAYS,
  type ProposalCall,
  type ProposalView,
} from "@/lib/proposals";
import { latestJudgments, listProposals, portals, proposalCalls, tagOptions, winRateByPortal } from "@/lib/queries";
import { firstParam } from "@/lib/text";
import { pickAllowed } from "@/lib/values";
import { allowlist } from "@/lib/viewer";

type SearchParams = Record<string, string | string[] | undefined>;

const TITLES: Record<ProposalView, string> = {
  closing: "Closing in 14 days",
  "to-draft": "To draft",
  drafting: "Drafting",
  submitted: "Submitted and waiting",
  results: "Results",
};

const PATHS: Record<ProposalView, string> = {
  closing: "/proposals",
  "to-draft": "/proposals",
  drafting: "/proposals",
  submitted: "/proposals/submitted",
  results: "/proposals/results",
};

/** Each view's key column and the direction it opens in (P1). */
const KEYS: Record<ProposalView, { label: string; first: "asc" | "desc" }> = {
  closing: { label: "Due", first: "asc" },
  "to-draft": { label: "Due", first: "asc" },
  drafting: { label: "Due", first: "asc" },
  submitted: { label: "Waiting", first: "desc" },
  results: { label: "Submitted", first: "desc" },
};

function Judges({ verdicts }: { verdicts: Verdicts }) {
  return (
    <div className="judges">
      <div className="judge">
        <span className="who">Claude</span>
        <Badge value={verdicts.claude?.verdict} empty="not reviewed" />
      </div>
      <div className="judge">
        <span className="who">Grok</span>
        <Badge value={verdicts.grok?.verdict} empty="not yet" />
      </div>
    </div>
  );
}

function Empty({ view, filtered, clearHref }: { view: ProposalView; filtered: boolean; clearHref: string }) {
  const lines: Record<ProposalView, [string, string]> = {
    closing: [`Nothing pursued closes in the next ${CLOSING_DAYS} days.`, "Pursued calls and drafts under way show here as their deadlines come near."],
    "to-draft": ["No proposals to draft", "Choose Pursue in a call's Decide menu and it shows here until it is submitted."],
    drafting: ["No draft under way.", "A draft shows here from Start the draft until it is submitted."],
    submitted: ["Nothing submitted is waiting on a result.", "A call shows here once it is marked Submitted, until its result is recorded."],
    results: ["No results yet.", "Results recorded here and the Proposal Register's submissions show here, with win rate by portal."],
  };
  const [title, why] = lines[view];
  return (
    <div className="empty">
      <p className="title">{title}</p>
      <p className="muted">
        {why} {filtered ? <a href={clearHref}>Clear filters</a> : null}
      </p>
    </div>
  );
}

/**
 * The Proposals section (P1 to P5, PRO-575): five view cards over the pursued, drafting and submitted
 * calls and the Proposal Register, the filter bar as on Calls, and each view's table with its key
 * column sortable.
 */
export async function ProposalsView({ view, sp }: { view: ProposalView; sp: SearchParams }) {
  const [portalList, tagChoices] = await Promise.all([portals(), tagOptions()]);
  const bar = {
    portals: pickMany(sp.portal, portalList.map((p) => p.name)),
    state: pickState(sp.state, sp.open),
    tag: pickAllowed(sp.tag, tagChoices.map((t) => t.name)),
  };
  const key = KEYS[view];
  const dir = sp.dir === "asc" || sp.dir === "desc" ? sp.dir : key.first;
  const [rows, register, rates, tz, label] = await Promise.all([
    proposalCalls(bar),
    listProposals(bar.portals, view === "results" ? dir : "desc"),
    winRateByPortal(),
    timeZone(),
    labeler(),
  ]);
  const views = sortIntoViews(rows);
  const users = allowlist();
  const nameOf = (by: string | null) => label(displayPerson(by, users));
  const now = new Date();
  const today = now.toISOString().slice(0, 10);
  const listed = dir === key.first ? views[view] : [...views[view]].reverse();
  const judged = await latestJudgments(listed.map((r) => r.id));
  const won = rates.reduce((sum, r) => sum + r.won, 0) + views.results.filter((r) => r.result === "won").length;
  const lost = rates.reduce((sum, r) => sum + (r.decided - r.won), 0) + views.results.filter((r) => r.result === "lost").length;
  const barParams: Params = { portal: bar.portals, state: bar.state, tag: bar.tag };
  const viewName = view === "closing" || view === "drafting" ? view : "";
  const params: Params = { view: viewName, ...barParams, dir: dir === key.first ? "" : dir };
  const path = PATHS[view];
  const filtered = Object.values(barParams).some((v) => v.length > 0);
  const clearHref = filterHref(path, { view: viewName });
  const shown = view === "results" ? listed.length + register.length : listed.length;
  const sortHeader = {
    href: filterHref(path, { ...params, dir: dir === key.first ? (key.first === "asc" ? "desc" : "asc") : "" }),
    active: true,
    dir,
  } as const;

  return (
    <Shell section="proposals">
      <h1 className="sr-only">{TITLES[view]}</h1>
      <ViewCards
        label="Proposals views"
        cards={proposalCards({
          current: view,
          params: barParams,
          counts: {
            closing: views.closing.length,
            "to-draft": views["to-draft"].length,
            drafting: views.drafting.length,
            submitted: views.submitted.length,
            results: views.results.length + register.length,
          },
          dueBy: dayMonth(new Date(now.getTime() + CLOSING_DAYS * 24 * 3600 * 1000), tz),
          longestWait: Math.max(0, ...views.submitted.map((r) => waitingDays(r, now))),
          results: { won, lost },
        })}
      />
      <Flash notice={firstParam(sp.notice, 300)} error={firstParam(sp.error, 300)} />
      <FilterBar
        action={path}
        params={params}
        portals={portalList}
        selected={bar.portals}
        tags={tagChoices}
        tag={bar.tag}
        state={bar.state}
        filtered={filtered}
        clearHref={clearHref}
        settings={false}
        summary={`${shown} ${view === "results" ? (shown === 1 ? "proposal" : "proposals") : shown === 1 ? "call" : "calls"}`}
      />

      {view === "results" ? (
        <div className="win-rates">
          <span>
            <strong>All portals</strong> {won + lost ? `${((100 * won) / (won + lost)).toFixed(1)}%` : "n/a"}
            <span className="muted"> {won} won of {won + lost} decided</span>
          </span>
          {rates
            .filter((r) => r.decided > 0)
            .map((r) => (
              <span key={r.portal ?? "none"}>
                <strong>{r.portal ?? "no portal"}</strong> {r.win_rate_pct === null ? "n/a" : `${r.win_rate_pct.toFixed(1)}%`}
                <span className="muted">
                  {" "}
                  {r.won} won of {r.decided} decided
                </span>
              </span>
            ))}
        </div>
      ) : null}

      {shown === 0 ? (
        <Empty view={view} filtered={filtered} clearHref={clearHref} />
      ) : (
        <div className="table-wrap">
          <table className="proposals-table">
            <thead>
              <tr>
                {view === "results" ? (
                  <>
                    <th>Submission</th>
                    <th>Portal</th>
                    <th>Type</th>
                    <HeaderCell label="Submitted" tableSettings={false} sort={sortHeader} />
                    <th>Outcome</th>
                    <th>Strength</th>
                    <th>Exemplar</th>
                  </>
                ) : view === "submitted" ? (
                  <>
                    <th>Call</th>
                    <th>Submitted by</th>
                    <th>Submitted</th>
                    <HeaderCell label="Waiting" tableSettings={false} sort={sortHeader} />
                    <th>Due</th>
                    <th>Claude / Grok</th>
                    <th>Result</th>
                  </>
                ) : (
                  <>
                    <th>Call</th>
                    <HeaderCell label="Due" tableSettings={false} sort={sortHeader} />
                    {view === "to-draft" ? <th>Claude / Grok</th> : <th>Where it stands</th>}
                    <th>{view === "to-draft" ? "Pursued" : "Owner"}</th>
                    <th>{view === "drafting" ? "Open" : "Draft"}</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              {view === "results" ? (
                <>
                  {listed.map((r) => (
                    <tr key={r.id} data-call-id={r.id}>
                      <td className="call">{r.title || r.id}</td>
                      <td>{r.portal}</td>
                      <td>{r.type ?? ""}</td>
                      <td className="when">{formatTime(r.submitted_at ?? r.human_at, tz)}</td>
                      <td>
                        <Badge value={r.result} />
                      </td>
                      <td></td>
                      <td></td>
                    </tr>
                  ))}
                  {register.map((p) => (
                    <tr key={p.submission_id}>
                      <td className="call">
                        {p.drive_link ? (
                          <a href={p.drive_link} target="_blank" rel="noreferrer">
                            {p.title || p.submission_id}
                          </a>
                        ) : (
                          p.title || p.submission_id
                        )}
                        <div className="meta">
                          <code>{p.submission_id}</code>
                          {p.agency ? <span>{p.agency}</span> : null}
                        </div>
                      </td>
                      <td>{p.portal ?? ""}</td>
                      <td>{p.type ?? ""}</td>
                      <td className="when">{p.submitted_date ?? ""}</td>
                      <td>
                        <Badge value={p.outcome} empty="unknown" />
                      </td>
                      <td className="num">{p.strength_rating === null ? "" : `${p.strength_rating}/5`}</td>
                      <td>{p.use_as_exemplar ? <span className="badge tone-info">exemplar</span> : "no"}</td>
                    </tr>
                  ))}
                </>
              ) : view === "submitted" ? (
                listed.map((r) => {
                  const expected = resultExpected(r, today);
                  const days = waitingDays(r, now);
                  return (
                    <tr key={r.id} data-call-id={r.id}>
                      <CallCell row={r} tags={[]} details={false} reason={null} />
                      <td>{nameOf(r.submitted_by ?? r.human_by)}</td>
                      <td className="when">{formatTime(r.submitted_at ?? r.human_at, tz)}</td>
                      <td className="num">
                        {days}
                        <div className="meta">{days === 1 ? "day waiting" : "days waiting"}</div>
                      </td>
                      <DueCell due={r.due_date} daysLeft={r.days_left} extra={r.extra} tz={tz} />
                      <td>
                        <Judges verdicts={verdictsFor(judged.get(r.id), r.ai_verdict, r.ai_reasoning)} />
                      </td>
                      <td>
                        {expected.date ? (
                          <span className="tip" title={expected.source} tabIndex={0}>
                            Result expected by {expected.date}
                          </span>
                        ) : (
                          <span className="muted">{expected.source}</span>
                        )}
                        {expected.overdue ? (
                          <div>
                            <span className="badge tone-warn">result overdue</span>
                          </div>
                        ) : null}
                        {r.confirmation_number ? <div className="meta">Confirmation {r.confirmation_number}</div> : null}
                      </td>
                    </tr>
                  );
                })
              ) : (
                listed.map((r) => {
                  const block = draftBlock(r);
                  const drive = r.drive_folder_id ? `https://drive.google.com/drive/folders/${encodeURIComponent(r.drive_folder_id)}` : null;
                  return (
                    <tr key={r.id} data-call-id={r.id}>
                      <CallCell row={r} tags={[]} details reason={null} />
                      <DueCell due={r.due_date} daysLeft={r.days_left} extra={r.extra} tz={tz} />
                      {view === "to-draft" ? (
                        <td>
                          <Judges verdicts={verdictsFor(judged.get(r.id), r.ai_verdict, r.ai_reasoning)} />
                        </td>
                      ) : (
                        <td>
                          {r.pursuit_id ? (
                            <>
                              {stepLabel(r.current_step)}
                              <div className="meta">{stepStateWords(r.step_state)}</div>
                            </>
                          ) : (
                            <span className="muted">to draft</span>
                          )}
                        </td>
                      )}
                      <td>
                        {view === "to-draft" || !r.pursuit_id ? (
                          <>
                            {nameOf(r.human_by)}
                            <div className="meta when">{formatTime(r.human_at, tz)}</div>
                          </>
                        ) : (
                          nameOf(r.owner)
                        )}
                      </td>
                      <td className="draft-cell">
                        {r.pursuit_id ? (
                          <div className="buttons">
                            <a className="btn" href={`/proposals/${encodeURIComponent(r.id)}`}>
                              Open workspace
                            </a>
                            {drive ? (
                              <a className="btn" href={drive} target="_blank" rel="noreferrer">
                                <FolderOpen aria-hidden="true" />
                                Open Drive folder
                              </a>
                            ) : null}
                          </div>
                        ) : block ? (
                          <span className="muted">Cannot draft: {block}</span>
                        ) : (
                          <>
                            <button type="button" disabled>
                              Start the draft
                            </button>
                            <div className="meta">Drafting is not set up yet.</div>
                          </>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      )}
    </Shell>
  );
}
