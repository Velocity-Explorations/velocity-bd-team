import type { Metadata } from "next";
import { Shell } from "@/components/Shell";
import { Badge, toneOf } from "@/components/bits";
import { formatAgo, formatDuration, formatTime, parseStageCounts } from "@/lib/format";
import { listRuns, type RunRow } from "@/lib/queries";
import { displayTimeZone } from "@/lib/settings";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Runs" };

const STALE_MS = 2 * 60 * 60 * 1000;

function isStale(run: RunRow, now: Date): boolean {
  return run.status === "running" && !run.finished_at && now.getTime() - new Date(run.started_at).getTime() > STALE_MS;
}

function headline(run: RunRow, now: Date): string {
  if (isStale(run, now)) return "No finish recorded";
  switch (run.status) {
    case "completed":
      return "Completed";
    case "skipped_timeout":
      return "Fetch timed out and was skipped";
    case "error":
      return "Failed";
    case "running":
      return "Running now";
    default:
      return run.status;
  }
}

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

export default async function RunsPage() {
  const runs = await listRuns(100);
  const tz = displayTimeZone();
  const now = new Date();
  const latest = runs[0];

  return (
    <Shell current="runs">
      <div className="page-head">
        <div>
          <h1>Runs</h1>
          <p className="muted">Scan history from the runs table, newest first.</p>
        </div>
      </div>

      {latest ? (
        <section className={`latest edge-${isStale(latest, now) ? "warn" : toneOf(latest.status)}`} aria-label="Most recent run">
          <div className="meta">
            <span>Most recent run</span>
            <span className="num">#{latest.id}</span>
            <span>{latest.portal ?? latest.component}</span>
            {latest.dry_run ? <span className="badge tone-grey">dry run</span> : null}
          </div>
          <p className="big">
            <Badge value={latest.status} /> {headline(latest, now)}
          </p>
          <p>
            Started <span className="when">{formatTime(latest.started_at, tz)}</span> ({formatAgo(latest.started_at, now)})
            {latest.finished_at ? (
              <>
                , took <span className="num">{formatDuration(latest.started_at, latest.finished_at)}</span>
              </>
            ) : null}
            .
          </p>
          <p>
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
          ) : null}
        </section>
      ) : null}

      {runs.length === 0 ? (
        <div className="empty">
          <p className="title">No runs recorded yet.</p>
          <p className="muted">Each pipeline run (python run.py) adds a row here.</p>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Run</th>
                <th>Portal</th>
                <th>Status</th>
                <th>Started</th>
                <th>Finished</th>
                <th>Took</th>
                <th>Stage counts</th>
                <th>Error</th>
                <th>Log</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id}>
                  <td className="num">
                    #{run.id}
                    {run.dry_run ? (
                      <div className="meta">
                        <span className="badge tone-grey">dry run</span>
                      </div>
                    ) : null}
                  </td>
                  <td className="nowrap">{run.portal ?? run.component}</td>
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
