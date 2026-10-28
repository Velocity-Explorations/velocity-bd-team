import type { Metadata } from "next";
import { ArrowRight, ChevronDown } from "lucide-react";
import { AutomationCards } from "@/components/AutomationCards";
import { HeaderCell } from "@/components/HeaderCell";
import { PortalLogo } from "@/components/PortalLogo";
import { Shell } from "@/components/Shell";
import { Badge, toneOf } from "@/components/bits";
import { filterHref, pickMany } from "@/lib/filters";
import { formatAgo, formatDuration, formatTime, parseStageCounts } from "@/lib/format";
import { listRuns, runPortals } from "@/lib/queries";
import { isProblem, isStale, pickRunsSort, runHeadline } from "@/lib/runs";
import { displayTimeZone } from "@/lib/settings";
import { firstParam } from "@/lib/text";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Scans" };

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function Counts({ text }: { text: string | null }) {
  const counts = parseStageCounts(text);
  if (!counts.length) return null;
  return (
    <span className="counts">
      {counts.map(([key, value]) => (
        <span key={key}>
          <strong>{value}</strong> {key}
        </span>
      ))}
    </span>
  );
}

/**
 * Scans and Scan problems (PRO-573): the most recent run as a card, then the last 100 runs, or only
 * those that failed, timed out or never finished (`?view=problems`), with a Portals filter and a
 * sortable Started column.
 */
export default async function ScansPage({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  const view = firstParam(sp.view, 20) === "problems" ? "problems" : "runs";
  const known = await runPortals();
  const portals = pickMany(sp.portal, known);
  const dir = pickRunsSort(sp.dir);
  const runs = await listRuns(100, { portals, problems: view === "problems", dir });
  const tz = displayTimeZone();
  const now = new Date();
  const latest = runs[0];
  const params = { view: view === "problems" ? "problems" : "", portal: portals, dir: dir === "asc" ? "asc" : "" };
  const chosen = portals.length === 0 ? "All" : portals.length === 1 ? portals[0] : `${portals.length} chosen`;

  return (
    <Shell section="automation">
      <h1 className="sr-only">{view === "problems" ? "Scan problems" : "Scans"}</h1>
      <AutomationCards current={view} />

      <div className="filter-bar" role="search" aria-label="Filters">
        <details className="menu" data-apply-on-close="">
          <summary>
            Portals: {chosen}
            <ChevronDown aria-hidden="true" />
          </summary>
          <div className="menu-body">
            <form action="/runs">
              {view === "problems" ? <input type="hidden" name="view" value="problems" /> : null}
              {dir === "asc" ? <input type="hidden" name="dir" value="asc" /> : null}
              {known.map((name) => (
                <label key={name} className="check">
                  <input type="checkbox" name="portal" value={name} defaultChecked={portals.includes(name)} /> {name}
                </label>
              ))}
              <p className="hint">None ticked shows every portal. Applies when this menu closes.</p>
              <button type="submit" className="btn-primary">
                Apply
              </button>
            </form>
          </div>
        </details>
        <p className="muted bar-lead">
          {view === "problems"
            ? "Runs that failed, timed out, or never recorded a finish."
            : "Scan history from the runs table. A run still running after two hours is flagged."}
        </p>
        <p className="bar-count">
          {runs.length} {runs.length === 1 ? "run" : "runs"}, {dir === "asc" ? "oldest first" : "newest first"}
        </p>
      </div>

      {latest ? (
        <section className={`content-card latest-run edge-${isStale(latest, now) ? "warn" : toneOf(latest.status)}`} aria-label="Most recent run">
          <p className="content-card__label">
            <span>Most recent run</span>
            {latest.log_path ? (
              <a href={`/runs/${latest.id}/log`} aria-label={`Open the log of run ${latest.id}`}>
                <ArrowRight aria-hidden="true" />
              </a>
            ) : null}
          </p>
          <div className="content-card__body">
            <p className="latest-line">
              <span className="num">#{latest.id}</span>
              <strong>{latest.portal ?? latest.component}</strong>
              <Badge value={isStale(latest, now) ? "error" : latest.status} />
              {latest.dry_run ? <span className="badge tone-grey">dry run</span> : null}
              <span>
                {runHeadline(latest, now)}. Started <span className="when">{formatTime(latest.started_at, tz)}</span> (
                {formatAgo(latest.started_at, now)})
                {latest.finished_at ? (
                  <>
                    , took <span className="num">{formatDuration(latest.started_at, latest.finished_at)}</span>
                  </>
                ) : null}
              </span>
              <Counts text={latest.stage_counts} />
            </p>
            {latest.error ? <p className="error-text">{latest.error}</p> : null}
            {isStale(latest, now) ? (
              <p className="muted">The run started over two hours ago and never finished; the process probably died. Check the log and data/pipeline.lock.</p>
            ) : null}
            {latest.log_path ? (
              <p>
                <a href={`/runs/${latest.id}/log`}>Open log</a> <code>{latest.log_path}</code>
              </p>
            ) : (
              <p className="muted">No log link for this run.</p>
            )}
          </div>
        </section>
      ) : null}

      {runs.length === 0 ? (
        <div className="empty">
          <p className="title">{view === "problems" ? "No scan problems." : "No runs recorded yet."}</p>
          <p className="muted">
            {view === "problems" ? "Every recorded scan completed. " : "Each pipeline run (python run.py) adds a row here. "}
            {portals.length ? <a href={filterHref("/runs", { view: params.view })}>Clear filters</a> : null}
          </p>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Run</th>
                <th>Portal</th>
                <th>Status</th>
                <HeaderCell
                  label="Started"
                  tableSettings={false}
                  sort={{ href: filterHref("/runs", { ...params, dir: dir === "asc" ? "" : "asc" }), active: true, dir }}
                />
                <th>Finished</th>
                <th>Took</th>
                <th>Stage counts</th>
                <th>Error</th>
                <th>Log</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id} className={isProblem(run, now) ? "problem" : undefined}>
                  <td className="num">
                    #{run.id}
                    {run.dry_run ? (
                      <div className="meta">
                        <span className="badge tone-grey">dry run</span>
                      </div>
                    ) : null}
                  </td>
                  <td className="nowrap">
                    <span className="portal-with-logo">
                      {run.portal ? <PortalLogo portal={run.portal} small /> : null}
                      {run.portal ?? run.component}
                    </span>
                  </td>
                  <td>
                    <Badge value={isStale(run, now) ? "error" : run.status} />
                    {isStale(run, now) ? <div className="meta">no finish recorded</div> : null}
                  </td>
                  <td className="when">{formatTime(run.started_at, tz)}</td>
                  <td className="when">{formatTime(run.finished_at, tz)}</td>
                  <td className="num">{formatDuration(run.started_at, run.finished_at)}</td>
                  <td>
                    <Counts text={run.stage_counts} />
                  </td>
                  <td className="reason">{run.error ? <span className="error-text" title={run.error}>{run.error.slice(0, 160)}</span> : null}</td>
                  <td>{run.log_path ? <a href={`/runs/${run.id}/log`}>log</a> : null}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Shell>
  );
}
