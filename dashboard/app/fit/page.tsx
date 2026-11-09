import type { Metadata } from "next";
import { saveFitRatingAction } from "@/app/actions";
import { AutomationCards } from "@/components/AutomationCards";
import { FitNote } from "@/components/FitNote";
import { FitSlider } from "@/components/FitSlider";
import { preloadShell, Shell } from "@/components/Shell";
import { Badge, Flash } from "@/components/bits";
import { buildFitRows, SECTIONS, SLIDER, type FitRow, type Mix } from "@/lib/fitratings";
import { formatTime } from "@/lib/format";
import { timeZone } from "@/lib/me";
import { fitOverview, fitRatingInputs } from "@/lib/queries";
import { firstParam } from "@/lib/text";
import { STATUS_LABELS, isDecision } from "@/lib/values";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Fit ratings" };

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

const BANDS = ["strong", "possible", "weak", "ruled out"];

export default async function FitRatingsPage({ searchParams }: { searchParams: SearchParams }) {
  preloadShell("automation");   // the frame's queries run beside this page's
  const sp = await searchParams;
  const [inputs, overview, tz] = await Promise.all([fitRatingInputs(), fitOverview(), timeZone()]);
  const rows = inputs ? buildFitRows(inputs) : [];
  const unrated = rows.filter((r) => !r.rating).length;
  const bands = overview ? BANDS.filter((b) => overview.bands[b]).map((b) => `${overview.bands[b]} ${b}`).join(", ") : "";
  const job = overview?.job;

  return (
    <Shell section="automation">
      <h1 className="sr-only">Fit ratings</h1>
      <AutomationCards current="fit" />
      <Flash notice={firstParam(sp.notice, 300)} error={firstParam(sp.error, 300)} />
      <div className="lead-line">
        <p className="muted">
          How well each tag, keyword and NAICS code fits Velocity. Every call&apos;s fit score is built from these, with its
          primary focus (the work that is most of what the buyer wants) counting most, and anything not rated counts as Neutral. Slide a rating from Never to Core; it saves when you let
          go, and Clear sets it back to not rated. A note saves as you type.
        </p>
      </div>

      {!inputs ? (
        <div className="empty">
          <p className="title">Fit ratings need migration 013.</p>
          <p className="muted">
            Run <code>python -m ledger.migrate</code> against the live database, then reload this page.
          </p>
        </div>
      ) : (
        <>
          <ul className="fit-scale" aria-label="The rating scale">
            {SLIDER.map((s) => (
              <li key={s.key} className={`tone-${s.tone}`}>
                <b>{s.label}{s.points ? <span>{s.points}</span> : null}</b>
                {s.means}
              </li>
            ))}
          </ul>
          <p className="fit-status">
            {bands ? <>Open calls now: {bands}. </> : null}
            {job && (job.state === "queued" || job.state === "working")
              ? "Scoring again with the latest ratings; this takes about a minute."
              : job?.finished_at
                ? `Scores last updated ${formatTime(job.finished_at, tz)}. A change here updates them within about a minute.`
                : "A change here updates the scores within about a minute."}
          </p>
          <nav className="fit-nav" aria-label="Sections">
            {SECTIONS.map((s) => {
              const own = rows.filter((r) => r.section === s.key);
              const open = own.filter((r) => !r.rating).length;
              return (
                <a key={s.key} href={`#${s.key}`}>
                  {s.label} <span className="muted">{own.length}</span>
                  {open ? <span className="badge tone-warn">{open} not rated</span> : null}
                </a>
              );
            })}
            {unrated ? null : <span className="muted">Everything is rated.</span>}
          </nav>
          {SECTIONS.map((s) => (
            <section key={s.key} id={s.key} className="fit-section" aria-labelledby={`fit-${s.key}`}>
              <div className="section-head">
                <h2 id={`fit-${s.key}`}>{s.label}</h2>
                <p>{s.question}. {s.hint ?? ""}</p>
              </div>
              <div className="table-wrap">
                <table className="fit-table">
                  <thead>
                    <tr>
                      <th><HeadHelp label={s.label} tip={`What is being rated, what it covers, and example calls. ${s.question}.`} /></th>
                      <th className="fit-rating-col"><HeadHelp label="Rating and note" tip={RATING_TIP} /></th>
                      <th className="num"><HeadHelp label="Calls" tip={s.key === "work" ? CALLS_WORK_TIP : CALLS_TIP} /></th>
                      <th><HeadHelp label="Judges (yes, maybe, no)" tip={JUDGES_TIP} /></th>
                      <th><HeadHelp label="Team" tip={TEAM_TIP} /></th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.filter((r) => r.section === s.key).map((row) => <FitRatingRow key={row.key} row={row} tz={tz} focus={s.key === "work"} />)}
                  </tbody>
                </table>
              </div>
            </section>
          ))}
        </>
      )}
    </Shell>
  );
}

const CALLS_TIP = "How many calls the keyword filter kept that carry this.";
const CALLS_WORK_TIP = "How many calls the keyword filter kept that carry this work, and below, how many of them a judge named it " +
  "the primary focus of: the work that is most of what the buyer wants. A Never rules a call out only when this is its primary focus.";
const JUDGES_TIP = "Claude's and Grok's newest verdicts on those calls: how many yes, maybe and no.";
const TEAM_TIP = "What the team decided on those calls: Pursue, Not relevant, Submitted or Dismissed.";
const RATING_TIP = "How well this fits Velocity, from Never to Core; every call's fit score is built from these. The rating saves " +
  "when you let go of the slider, and the note, which says why, saves as you type.";

/** A column header that explains itself on hover, or on keyboard focus through the TooltipController (David, 9 Nov 2026). */
function HeadHelp({ label, tip }: { label: string; tip: string }) {
  return (
    <span className="th-help" title={tip} tabIndex={0}>
      {label}
    </span>
  );
}

function FitRatingRow({ row, tz, focus }: { row: FitRow; tz: string; focus: boolean }) {
  return (
    <tr id={row.key}>
      <td className="fit-item">
        <span className="fit-name">{row.name}</span>
        {row.kind === "notice" ? <span className="badge tone-none">notice type</span> : null}
        {row.rating ? null : <span className="badge tone-warn">not rated</span>}
        {row.covers ? <div className="meta">{row.covers}</div> : null}
        {row.codes.length ? (
          <ul className="fit-codes">
            {row.codes.map((c) => <li key={c.code}><code>{c.code}</code> {c.title} <span className="muted">{c.calls}</span></li>)}
          </ul>
        ) : null}
        {row.examples.length ? (
          <details className="fit-examples">
            <summary>Examples</summary>
            <ul>
              {row.examples.map((x) => (
                <li key={x.id}>
                  {x.url ? <a href={x.url} target="_blank" rel="noreferrer">{x.title}</a> : x.title}
                  <span className="muted"> Claude {x.claude ?? "not yet"}, Grok {x.grok ?? "not yet"}</span>
                  {x.team ? <> <Badge value={x.team} /></> : null}
                </li>
              ))}
            </ul>
          </details>
        ) : null}
      </td>
      <td>
        <form action={saveFitRatingAction} className="fit-form">
          <input type="hidden" name="key" value={row.key} />
          <input type="hidden" name="name" value={row.name} />
          <FitSlider name={row.name} rating={row.rating} />
          <FitNote id={`note-${row.key}`} name={row.name} note={row.note} rated={Boolean(row.rating)} />
          {row.changedBy ? <div className="meta">Changed by {row.changedBy}{row.changedAt ? `, ${formatTime(row.changedAt, tz)}` : ""}</div> : null}
        </form>
      </td>
      <td className="num">
        {row.calls}
        {focus ? (
          <div className="fit-focus" title={`${row.mainWork ?? 0} of these ${row.calls} calls have this as their primary focus`}>
            <span className="fit-focus-bar" aria-hidden="true">
              <span style={{ width: `${row.calls ? Math.round((100 * (row.mainWork ?? 0)) / row.calls) : 0}%` }} />
            </span>
            <span className="meta">{row.mainWork ?? 0} as primary focus</span>
          </div>
        ) : null}
      </td>
      <td className="fit-judges">
        <MixLine who="Claude" mix={row.claude} />
        <MixLine who="Grok" mix={row.grok} />
      </td>
      <td className="fit-team">
        {row.team.length
          ? row.team.map(([status, n]) => <div key={status}>{n} {isDecision(status) ? STATUS_LABELS[status] : status}</div>)
          : <span className="muted">none yet</span>}
      </td>
    </tr>
  );
}

function MixLine({ who, mix }: { who: string; mix: Mix }) {
  const total = mix[0] + mix[1] + mix[2];
  return (
    <div className="fit-mix">
      <span className="who">{who}</span>
      <span className="nums">{mix[0]}, {mix[1]}, {mix[2]}</span>
      <span className={total ? "bar" : "bar empty"} role="img" aria-label={`${who}: ${mix[0]} yes, ${mix[1]} maybe, ${mix[2]} no`}>
        {mix.map((n, i) => (n ? <span key={i} className={`seg seg-${i}`} style={{ flexGrow: n }} /> : null))}
      </span>
    </div>
  );
}
