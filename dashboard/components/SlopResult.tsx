import { ArrowLeft, RefreshCw } from "lucide-react";
import { checkAgainAction } from "@/app/actions";
import { formatTime } from "@/lib/format";
import type { PursuitRow, WorkspaceCall } from "@/lib/queries";
import {
  bandNotes,
  bandTone,
  excerpt,
  jobState,
  lineNotes,
  parseLines,
  slopHref,
  slopView,
  type FamilyView,
  type ScanJob,
  type ScanRow,
  type SlopView,
} from "@/lib/slop";
import { stepInfo, stepTitle, type StepRow } from "@/lib/workspace";

const SPOTS_SHOWN = 12;

function lines(first: number, last: number): string {
  return first === last ? `Line ${first}` : `Lines ${first} to ${last}`;
}

function amount(n: number, one: string, many = `${one}s`): string {
  return `${Number.isInteger(n) ? n : n.toFixed(1)} ${n === 1 ? one : many}`;
}

/** A family of findings with its fix and where each one is (PW20, parts 4 and 5). */
function Family({ step, family, prefix }: { step: string; family: FamilyView; prefix: string }) {
  const rate = `${family.per1k.toFixed(1)} per 1,000 words`;
  return (
    <li className="ws-family">
      <div className="ws-family-head">
        <strong>{family.label}</strong>
        <span className="meta">{family.tier}</span>
        <span className="ws-family-count">
          {amount(family.hits, "hit")}, {rate}
          {prefix === "f" ? (family.points ? `, ${amount(family.points, "point")}` : ", under its line") : ""}
        </span>
      </div>
      {family.fix ? (
        <p className="ws-fix"><span className="field-label">Fix</span> {family.fix}</p>
      ) : null}
      <ul className="ws-spots">
        {family.spots.slice(0, SPOTS_SHOWN).map((spot) => {
          const id = `${prefix}-${family.key}-${spot.line}-${spot.column}`;
          return (
            <li key={id} id={id}>
              <a href={slopHref(step, spot.line, spot.line, id)}>Line {spot.line}, col {spot.column}</a>
              <span className="ws-match">{spot.match}</span>
            </li>
          );
        })}
      </ul>
      {family.spots.length > SPOTS_SHOWN ? <p className="hint">{SPOTS_SHOWN} of {family.spots.length} shown.</p> : null}
    </li>
  );
}

/** The scanned text beside the list, at the linked lines, with what was found on each (PW20). */
function TextBeside({ step, view, first, last }: { step: string; view: SlopView; first: number; last: number }) {
  const notes = lineNotes(view);
  return (
    <aside className="ws-slop-text" aria-label="The text as scanned">
      <div className="ws-panel-head">
        <h3 className="field-label">{view.draft}, {lines(first, last).toLowerCase()}</h3>
        <a className="btn-text" href={slopHref(step)}>Close</a>
      </div>
      <p className="hint">The text as scanned, saved with the result. Edit the draft, then check again.</p>
      <ol className="ws-text-lines">
        {excerpt(view.lines, first, last).map((line) => (
          <li key={line.n} className={line.hit ? "hit" : undefined}>
            <span className="ws-line-n">{line.n}</span>
            <span className="ws-line-text">
              {line.text || " "}
              {(notes.get(line.n) ?? []).map((note) => <span key={note} className="ws-line-note">{note}</span>)}
            </span>
          </li>
        ))}
      </ol>
    </aside>
  );
}

/**
 * The AI slop check's result (PW20 to PW23), opened from Reviews or a draft's step: the verdict line, the open
 * placeholders by kind, the paragraphs to revise first, the findings by family with their fix, the proposal faults
 * apart, and Check again. It shows the newest scan the worker saved and never runs the scanner.
 */
export function SlopResult({ call, pursuit, row, scan, job, hasDraft, canCheck, linesParam, tz }: {
  call: WorkspaceCall;
  pursuit: PursuitRow;
  row: StepRow;
  scan: ScanRow | null;
  job: ScanJob | null;
  hasDraft: boolean;
  canCheck: boolean;
  linesParam: string | undefined;
  tz: string;
}) {
  const view = scan ? slopView(scan) : null;
  const span = view ? parseLines(linesParam, view.lines.length) : null;
  const state = jobState(job, scan?.scanned_at ?? null);
  const step = row.step;
  return (
    <section className="ws-card" aria-labelledby="ws-step-title">
      <div className="ws-band">
        <h2 id="ws-step-title">{stepTitle(step)} · AI slop check</h2>
        {view ? <span className={`badge tone-${view.ready ? "good" : "warn"}`}>{view.ready ? "ready" : "not ready"}</span> : null}
      </div>
      <div className="ws-card-body">
        <nav className="ws-subcrumb" aria-label="Back to the step">
          <a href={`?step=${encodeURIComponent(step)}`}><ArrowLeft aria-hidden="true" />{stepInfo(step)?.label ?? step}</a>
          <span>/ AI slop check</span>
        </nav>
        <p className="ws-purpose">
          The AI slop check runs on every new draft and fixes what it can on its own. This is what is left. It reports
          writing patterns and how to fix them; it never judges who or what wrote the text.
        </p>
        {state === "queued" && job ? (
          <p className="ws-notice tone-info">
            <span className="badge tone-info">queued</span> Check again is waiting for the worker since {formatTime(job.requested_at, tz)}.
            The last result stays shown until the new one is saved.
          </p>
        ) : null}
        {state === "working" && job ? (
          <p className="ws-notice tone-info">
            <span className="badge tone-info">working</span> Checking the newest draft.
            {job.started_at ? ` Started ${formatTime(job.started_at, tz)}.` : ""} The last result stays shown until the new one is saved.
          </p>
        ) : null}
        {state === "failed" && job ? <p className="ws-notice tone-conflict">The last Check again did not run: {job.result || "no reason was recorded"}</p> : null}
        {!view ? (
          <p className="ws-notice">
            {hasDraft ? "No scan of the draft is saved yet." : "No draft has been checked yet. The check runs on its own when the first draft is saved."}
          </p>
        ) : (
          <>
            <div className={`ws-verdict-box tone-${view.ready ? "good" : "warn"}`}>
              <p className="ws-verdict-line">
                <span className={`badge tone-${view.ready ? "good" : "warn"}`}>{view.ready ? "ready" : "not ready"}</span>
                <strong>{view.verdict}</strong>
              </p>
              <p className="ws-verdict-facts">
                <span>Band <span className={`badge tone-${bandTone(view.band)}`}>{view.band ?? "none"}</span></span>
                {view.band && view.points !== null ? <span>{amount(view.points, "point")}</span> : null}
                <span>{view.band ? `Confidence: ${view.confidence}, ` : ""}{view.words.toLocaleString("en-US")} words</span>
                <span>Last scan <strong>{formatTime(view.scannedAt, tz)}</strong>, on {view.draft}</span>
              </p>
              {bandNotes(view).map((note) => <p key={note} className="hint">{note}</p>)}
            </div>
            <p className="ws-fixed">
              <span className="badge tone-grey">automatic</span>
              {view.fixed
                ? ` Fixed on its own before this scan: ${view.fixed}, dashes and tracking parameters in links.`
                : " Nothing needed fixing on its own before this scan."}
            </p>
            <div className={span ? "ws-slop with-text" : "ws-slop"}>
              <div className="ws-slop-list">
                <section className="ws-slop-part" aria-label="Open placeholders">
                  <h3 className="field-label">Open placeholders, {view.open}</h3>
                  {view.placeholders.length ? view.placeholders.map((group) => (
                    <div key={group.kind} className="ws-placeholder-kind">
                      <p className="ws-kind"><strong>{group.kind}</strong> <span className="meta">{group.items.length}, {group.note}</span></p>
                      <ul className="ws-spots">
                        {group.items.map((item) => {
                          const id = `p-${item.line}`;
                          return (
                            <li key={`${item.line}-${item.match}`} id={id}>
                              <span className="ws-match">{item.section ? `${item.section}. ` : ""}{item.match}</span>
                              <a href={slopHref(step, item.line, item.line, id)}>Line {item.line}</a>
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  )) : <p className="muted">None open.</p>}
                </section>
                <section className="ws-slop-part" aria-label="Paragraphs to revise first">
                  <h3 className="field-label">Paragraphs to revise first, {view.hot.length} of up to 5</h3>
                  {view.hot.length ? (
                    <ol className="ws-hot">
                      {view.hot.map((p, i) => {
                        const id = `h-${i + 1}`;
                        return (
                          <li key={id} id={id}>
                            <span className="ws-step-num">{i + 1}</span>
                            <span>
                              <strong>{p.section || "The draft"}</strong>
                              <span className="meta">{amount(p.findings, "finding")}{p.families.length ? `: ${p.families.join(", ").toLowerCase()}` : ""}</span>
                            </span>
                            <a href={slopHref(step, p.first, p.last, id)}>{lines(p.first, p.last)}</a>
                          </li>
                        );
                      })}
                    </ol>
                  ) : <p className="muted">No paragraph stands out.</p>}
                </section>
                <section className="ws-slop-part" aria-label="Findings by family">
                  <h3 className="field-label">Findings by family, {view.families.reduce((n, f) => n + f.spots.length, 0)} left after its own fixes</h3>
                  <p className="hint">These count toward the band once a family passes its line.</p>
                  {view.families.length ? (
                    <ul className="ws-families">
                      {view.families.map((family) => <Family key={family.key} step={step} family={family} prefix="f" />)}
                    </ul>
                  ) : <p className="muted">Nothing left that counts toward the band.</p>}
                  {view.quiet.length ? <p className="ws-quiet">{view.quiet.map((tier) => `${tier}: none`).join(" · ")}</p> : null}
                </section>
                <section className="ws-slop-part" aria-label="Proposal faults">
                  <h3 className="field-label">Proposal faults, {view.faults.reduce((n, f) => n + f.spots.length, 0)}, listed apart</h3>
                  <p className="hint">These do not count toward the band.</p>
                  {view.faults.length ? (
                    <ul className="ws-families">
                      {view.faults.map((family) => <Family key={family.key} step={step} family={family} prefix="x" />)}
                    </ul>
                  ) : <p className="muted">None found.</p>}
                  <p className="hint">
                    The solicitation&apos;s own words are exempt from every other check
                    {view.exempt ? `; ${view.exempt} ${view.exempt === 1 ? "finding was" : "findings were"} left out for that reason` : ""}.
                  </p>
                </section>
              </div>
              {span ? <TextBeside step={step} view={view} first={span.first} last={span.last} /> : null}
            </div>
          </>
        )}
        <div className="ws-call">
          <p className="ws-call-label">Your call</p>
          <p className="ws-question">{view?.ready ? "The newest draft is Ready." : "Fill the placeholders and revise what is listed, then check again."}</p>
          <p className="hint">
            The scan runs in the worker, never in this page; the result here updates when it finishes. The steps carry on
            meanwhile, but Submit opens only once the newest draft is Ready.
            {pursuit.drive_folder_id ? "" : " Until Drive is set up, the drafts are on the scan PC."}
          </p>
          {canCheck && pursuit.state === "working" && hasDraft ? (
            <div className="ws-actions">
              {state === "queued" || state === "working" ? (
                <button type="button" className="btn" disabled><RefreshCw aria-hidden="true" />Check again</button>
              ) : (
                <form action={checkAgainAction}>
                  <input type="hidden" name="call_id" value={call.id} />
                  <input type="hidden" name="step" value={step} />
                  <input type="hidden" name="view" value="slop" />
                  <button type="submit" className="btn fn-change"><RefreshCw aria-hidden="true" />Check again</button>
                </form>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
