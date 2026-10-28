import { Check, Pencil, X } from "lucide-react";
import type { ReactNode } from "react";
import { changeBuildsOnAction, setDirectionAction, tickChecklistAction } from "@/app/actions";
import { formatDue, formatTime } from "@/lib/format";
import type { ChecklistRow, PursuitRow, WorkspaceCall } from "@/lib/queries";
import {
  DISCOVERY_TASKS,
  fitTone,
  parseJson,
  RECOMMENDATIONS,
  REQUIREMENT_ROWS,
  tagTone,
  taskLine,
  taskWord,
  type StepRow,
} from "@/lib/workspace";

type Content = Record<string, unknown>;
type Label = (name: string) => string;

function text(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function list(value: unknown): string[] {
  return Array.isArray(value) ? value.map((v) => String(v).trim()).filter(Boolean) : [];
}

function Rows({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="ws-rows">
      {rows.map(([label, value]) => (
        <div key={label}>
          <dt className="field-label">{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

const PARTS: [string, string][] = [
  ["registrations", "2.1 Registrations and eligibility"],
  ["documents", "2.2 Required documents and volumes"],
  ["inputs", "2.3 Inputs needed from the owner and the team"],
  ["formatting", "2.4 Formatting and packaging"],
  ["reviews", "2.5 Reviews and approvals"],
  ["submission", "2.6 Submission"],
];

/** The submission checklist in its six parts (PW9), tickable by the owner and the people working with them. */
export function Checklist({ callId, step, items, editable, label }: {
  callId: string;
  step: string;
  items: ChecklistRow[];
  editable: boolean;
  label: Label;
}) {
  return (
    <div className="ws-checklist">
      {PARTS.map(([part, title]) => {
        const mine = items.filter((item) => item.part === part);
        if (mine.length === 0) return null;
        return (
          <div key={part} className="ws-check-part">
            <h3 className="field-label">{title}</h3>
            <ul>
              {mine.map((item) => (
                <li key={item.id} className={item.done ? "done" : undefined}>
                  {editable ? (
                    <form action={tickChecklistAction}>
                      <input type="hidden" name="call_id" value={callId} />
                      <input type="hidden" name="step" value={step} />
                      <input type="hidden" name="item_id" value={item.id} />
                      <input type="hidden" name="expected_done" value={item.done ? "1" : "0"} />
                      <button type="submit" name="done" value={item.done ? "0" : "1"} className="ws-tick" aria-pressed={Boolean(item.done)}
                        aria-label={`${item.done ? "Untick" : "Tick"}: ${item.text}`}>
                        {item.done ? <Check aria-hidden="true" /> : null}
                      </button>
                    </form>
                  ) : (
                    <span className="ws-tick" aria-hidden="true">{item.done ? <Check /> : null}</span>
                  )}
                  <span className="ws-check-text">
                    {item.text}
                    {item.source ? <span className="meta"> {item.source}</span> : null}
                  </span>
                  <span className="ws-check-owner">{item.owner ? label(item.owner) : ""}</span>
                  <span className="when">{item.due_date ?? ""}</span>
                  <span className={`badge tone-${item.done ? "good" : "grey"}`}>{item.done ? "done" : "to do"}</span>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}

const TASK_TONES: Record<string, string> = { done: "good", working: "info", "for you": "warn", waiting: "grey" };

/** Step 1 (PW6): the eight tasks with their states, what is left for the owner, and when the result is expected. */
export function DiscoveryView({ row, content }: { row: StepRow; content: Content }) {
  const tasks = parseJson<Record<string, string>>(row.task_states, {}) ?? {};
  const fetch = list(content.owner_fetch);
  const expected = (content.result_expected ?? {}) as { date?: string | null; source?: string | null };
  return (
    <section className="ws-screen" aria-label="Discovery's tasks">
      <p className="ws-progress">{taskLine(tasks)}</p>
      <ol className="ws-tasks">
        {DISCOVERY_TASKS.map((task, i) => {
          const word = taskWord(tasks[task.id]);
          return (
            <li key={task.id}>
              <span className="ws-step-num">{i + 1}</span>
              <span>
                <strong>{task.label}</strong>
                <span className="meta">{task.detail}</span>
              </span>
              <span className={`badge tone-${TASK_TONES[word] ?? "grey"}`}>{word}</span>
            </li>
          );
        })}
      </ol>
      {fetch.length ? (
        <div className="ws-subsection">
          <h3 className="field-label">For you to fetch</h3>
          <ul>
            {fetch.map((item, i) => <li key={i}>{item}</li>)}
          </ul>
        </div>
      ) : null}
      {expected.date ? (
        <p className="meta">
          Result expected by {expected.date}
          {expected.source ? `: ${expected.source}` : ""}
        </p>
      ) : null}
    </section>
  );
}

/** Step 2 (PW7): the summary in a two-minute read, with the call's key facts. */
export function SummaryView({ call, content, tz }: { call: WorkspaceCall; content: Content; tz: string }) {
  const document = text(content.document);
  const first = document.split(/\n\s*\n/).map((p) => p.trim()).find((p) => p && !p.startsWith("#")) ?? "";
  const due = formatDue(call.due_date, tz);
  return (
    <section className="ws-screen" aria-label="Summary">
      {first ? <p className="ws-lead">{first}</p> : null}
      <Rows rows={[
        ["Agency", call.department || "not given"],
        ["Type", call.type || "not given"],
        ["Deadline", `${due || "not given"}${call.days_left !== null && call.days_left >= 0 ? `, ${call.days_left} days left` : ""}`],
        ["Portal", call.portal],
      ]} />
    </section>
  );
}

/** Step 3 (PW8): the verdict, how the call aligns for Velocity, and the owner's direction beside Claude's angle. */
export function AlignmentView({ pursuit, content, label, tz }: { pursuit: PursuitRow; content: Content; label: Label; tz: string }) {
  const points = Array.isArray(content.points) ? (content.points as { tag: string; text: string; source?: string }[]) : [];
  return (
    <section className="ws-screen" aria-label="How it aligns for Velocity">
      <div className="ws-subsection">
        <h3 className="field-label">How it aligns for Velocity</h3>
        {text(content.verdict) ? <p className="ws-verdict">{text(content.verdict)}</p> : null}
        {points.length ? (
          <ul className="ws-tagged">
            {points.map((point, i) => (
              <li key={i}>
                <span className={`badge tone-${tagTone(point.tag)}`}>{point.tag}</span>
                <span>{point.text}</span>
                <span className="meta">{point.source ?? ""}</span>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
      <div className="ws-pair">
        <div className="ws-box">
          <h3 className="field-label">Your direction, from Start the draft</h3>
          <p>{text(content.direction) || "You gave no direction at Start the draft."}</p>
          <p className="meta">{label(pursuit.owner)}, {formatTime(pursuit.created_at, tz)}</p>
        </div>
        <div className="ws-box">
          <h3 className="field-label">Claude&apos;s proposed angle</h3>
          <p>{text(content.angle) || "No angle was given."}</p>
          {text(content.comparison) ? <p className="meta">{text(content.comparison)}</p> : null}
        </div>
      </div>
    </section>
  );
}

/** Alignment's choice inside Your call (PW8): keep the owner's direction, take Claude's angle, or write a new one. */
export function DirectionChoice({ content }: { content: Content }) {
  const mine = text(content.direction);
  return (
    <fieldset className="ws-choice">
      <legend className="sr-only">The direction to carry forward</legend>
      <div className="radio-cards ws-choice-cards">
        <label className="radio-card">
          <input type="radio" name="direction_choice" value="keep" defaultChecked={Boolean(mine)} disabled={!mine} />
          <span><strong>Keep mine</strong></span>
        </label>
        <label className="radio-card">
          <input type="radio" name="direction_choice" value="claude" defaultChecked={!mine} disabled={!text(content.angle)} />
          <span><strong>Use Claude&apos;s angle</strong></span>
        </label>
        <label className="radio-card">
          <input type="radio" name="direction_choice" value="new" />
          <span><strong>Write a new one</strong></span>
        </label>
      </div>
      <label className="field">
        <span className="field-label">A new direction, when you write one</span>
        <textarea name="direction" rows={3} maxLength={2000} defaultValue={mine || text(content.angle)} />
      </label>
      <p className="hint">Shown once more above the Outline (step 5), then locked.</p>
    </fieldset>
  );
}

/** Step 4 (PW9): the requirements in a few rows, then the checklist in its six parts. */
export function RequirementsView({ callId, content, checklist, editable, label }: {
  callId: string;
  content: Content;
  checklist: ChecklistRow[];
  editable: boolean;
  label: Label;
}) {
  const rows = (content.requirements ?? {}) as Record<string, string>;
  const shown = REQUIREMENT_ROWS.filter(([key]) => text(rows[key]));
  const done = checklist.filter((item) => item.done).length;
  return (
    <section className="ws-screen" aria-label="Requirements">
      {shown.length ? <Rows rows={shown.map(([key, title]) => [title, rows[key]])} /> : null}
      {text(content.submit_by) ? <p className="meta">Internal submit-by date: {text(content.submit_by)}</p> : null}
      {checklist.length ? (
        <div className="ws-subsection">
          <h3 className="field-label">Submission checklist, {done} of {checklist.length} done</h3>
          <p className="hint">Each item is specific to this call and says where it comes from. Items already met start ticked.</p>
          <Checklist callId={callId} step="requirements" items={checklist} editable={editable} label={label} />
        </div>
      ) : null}
    </section>
  );
}

/** The Go or no-go gate (PW10): Claude's decision brief, then what each choice does. */
export function GateBrief({ content }: { content: Content }) {
  const gaps = Array.isArray(content.gaps) ? (content.gaps as { gap: string; mitigation?: string }[]) : [];
  const fit = text(content.fit);
  const recommendation = text(content.recommendation);
  const rows: [string, ReactNode][] = [];
  if (fit || text(content.fit_reason)) {
    rows.push(["Fit rating", <>{fit ? <span className={`badge tone-${fitTone(fit)}`}>{fit}</span> : null} {text(content.fit_reason)}</>]);
  }
  if (list(content.win_themes).length) rows.push(["Win themes", <ul>{list(content.win_themes).map((t, i) => <li key={i}>{t}</li>)}</ul>]);
  if (gaps.length) {
    rows.push(["Critical gaps", <ul>{gaps.map((g, i) => <li key={i}><strong>{g.gap}.</strong> {g.mitigation ?? ""}</li>)}</ul>]);
  }
  if (text(content.effort)) rows.push(["Effort and timing", text(content.effort)]);
  if (recommendation || text(content.recommendation_text)) {
    rows.push(["Recommendation", <>{recommendation ? <span className={`badge tone-${recommendation === "no_go" ? "conflict" : "good"}`}>{RECOMMENDATIONS[recommendation] ?? recommendation}</span> : null} {text(content.recommendation_text)}</>]);
  }
  return (
    <section className="ws-screen" aria-label="Decision brief">
      {rows.length ? (
        <div className="ws-subsection">
          <h3 className="field-label">Decision brief</h3>
          <Rows rows={rows} />
        </div>
      ) : null}
      <Rows rows={[
        ["Go", "The proposal moves to Plan and the work continues."],
        ["Go with conditions", "The same, and each condition joins the checklist."],
        ["No-go", "The call becomes Not relevant with your note, and the draft stops."],
      ]} />
    </section>
  );
}

/** Step 5 (PW11): the direction and the past work, a last chance to change them, then the sections. */
export function OutlineView({ call, pursuit, content, row, canDecide, canContribute, isLocked }: {
  call: WorkspaceCall;
  pursuit: PursuitRow;
  content: Content;
  row: StepRow;
  canDecide: boolean;
  canContribute: boolean;
  isLocked: boolean;
}) {
  const sections = Array.isArray(content.sections)
    ? (content.sections as { title: string; criteria?: string[]; share?: string | null; evidence?: string[] }[])
    : [];
  const pastWork = parseJson<{ name: string }[]>(pursuit.builds_on, []).filter((item) => item && item.name);
  const open = !isLocked && pursuit.state === "working";
  const hidden = (
    <>
      <input type="hidden" name="call_id" value={call.id} />
      <input type="hidden" name="step" value={row.step} />
    </>
  );
  return (
    <section className="ws-screen" aria-label="Outline">
      <div className="ws-box">
        <h3 className="field-label">{open ? "Direction, last chance to change" : "Direction"}</h3>
        <p>{pursuit.direction?.trim() || "No direction was set."}</p>
        {open && canDecide ? (
          <details className="ws-more">
            <summary className="btn-text"><Pencil aria-hidden="true" />Edit</summary>
            <form action={setDirectionAction} className="ws-more-form">
              {hidden}
              <label className="field">
                <span className="field-label">The direction</span>
                <textarea name="direction" rows={3} maxLength={2000} defaultValue={pursuit.direction ?? ""} required />
              </label>
              <button type="submit" className="btn fn-change">Save the direction</button>
            </form>
          </details>
        ) : null}
      </div>
      <div className="ws-box">
        <h3 className="field-label">{open ? "Past work, last chance to change" : "Past work"}</h3>
        {pastWork.length ? (
          <ul className="ws-chips">
            {pastWork.map((item) => (
              <li key={item.name} className="chip">
                {item.name}
                {open && canContribute ? (
                  <form action={changeBuildsOnAction}>
                    {hidden}
                    <input type="hidden" name="remove" value={item.name} />
                    <button type="submit" className="chip-remove" aria-label={`Remove ${item.name}`}><X aria-hidden="true" /></button>
                  </form>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No past work chosen.</p>
        )}
        {open && canContribute ? (
          <form action={changeBuildsOnAction} className="ws-inline-form">
            {hidden}
            <label className="field">
              <span className="field-label">Add past work: a proposal, a project or a link</span>
              <input type="text" name="add" maxLength={300} required />
            </label>
            <button type="submit" className="btn fn-change">Add</button>
          </form>
        ) : null}
        {open ? <p className="hint">Choosing from Drive and uploading files arrive with Drive.</p> : null}
      </div>
      {sections.length ? (
        <div className="ws-subsection">
          <h3 className="field-label">Sections{text(content.page_limit) ? `, ${text(content.page_limit)}` : ""}</h3>
          <div className="table-wrap">
            <table className="ws-sections">
              <thead>
                <tr>
                  <th>Section</th>
                  <th>Criterion</th>
                  <th>Share</th>
                  <th>Draws on</th>
                </tr>
              </thead>
              <tbody>
                {sections.map((section, i) => (
                  <tr key={i}>
                    <td>{section.title}</td>
                    <td>{(section.criteria ?? []).join("; ")}</td>
                    <td className="when">{section.share ?? ""}</td>
                    <td>{(section.evidence ?? []).join("; ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
      {list(content.unmapped_criteria).length ? (
        <p className="ws-notice tone-warn">No section answers: {list(content.unmapped_criteria).join("; ")}</p>
      ) : null}
    </section>
  );
}

/** Steps 6 and 7: the draft's size and what is left to fill, and what the compliance check corrected. */
export function DraftView({ content }: { content: Content }) {
  const counts = (content.placeholders ?? {}) as Record<string, number>;
  const open = Object.entries(counts).filter(([, n]) => n);
  return (
    <section className="ws-screen" aria-label="The draft">
      <Rows rows={[
        ["Words", typeof content.words === "number" ? content.words.toLocaleString("en-US") : "not counted"],
        ["To fill", open.length ? open.map(([kind, n]) => `${n} ${kind === "other" ? "other bracketed notes" : kind}`).join(", ") : "nothing"],
      ]} />
    </section>
  );
}

export function ComplianceView({ content }: { content: Content }) {
  return (
    <section className="ws-screen" aria-label="Compliance">
      <Rows rows={[
        ["Corrected", typeof content.corrections === "number" ? `${content.corrections} in Draft v2` : "none reported"],
        ["To check", typeof content.warnings === "number" ? `${content.warnings} warnings` : "none reported"],
      ]} />
    </section>
  );
}
