import {
  Check,
  ChevronRight,
  CircleX,
  FileText,
  FolderOpen,
  History,
  ListChecks,
  MessageSquare,
  Paperclip,
  RefreshCw,
  RotateCcw,
  Send,
  Users,
} from "lucide-react";
import {
  addMaterialAction,
  approveStepAction,
  askChangesAction,
  checkAgainAction,
  markSubmittedAction,
  noGoAction,
  raiseCapAction,
  retryStepAction,
  setCollaboratorsAction,
} from "@/app/actions";
import { PortalLogo } from "@/components/PortalLogo";
import {
  AlignmentView,
  Checklist,
  ComplianceView,
  DirectionChoice,
  DiscoveryView,
  DraftView,
  FinalView,
  GateBrief,
  OutlineView,
  RequirementsView,
  ReviewsView,
  SubmitView,
  SummaryView,
} from "@/components/StepScreens";
import { formatDue, formatTime, isoNow, localInput } from "@/lib/format";
import type { ChecklistRow, EventRow, PursuitRow, WorkspaceCall } from "@/lib/queries";
import { finalGate, jobState, type ScanJob, type ScanRow } from "@/lib/slop";
import {
  actionsFor,
  approveLabel,
  changeCounts,
  checklistProgress,
  expectedDefault,
  locked,
  money,
  openChangesReason,
  parseJson,
  stageStates,
  STAGES,
  stateTone,
  stateWord,
  stepInfo,
  STEPS,
  stepTitle,
  type ChangeRow,
  type StepRow,
} from "@/lib/workspace";

type Label = (name: string) => string;
type Can = { decide: boolean; contribute: boolean };
/** The Proposal Library's index as the Outline offers it (phase 6b). */
export type Library = { groups: { title: string; items: { id: string; label: string }[] }[]; indexed: string | null };

const STOPPED: Record<string, string> = { no_go: "No-go", submitted: "Submitted", closed: "Closed" };

/**
 * The workspace header (PW1, PW19, PW24): the logo, the breadcrumb with the stage, the title, and a line with
 * the portal, format, deadline, owner, the people working with them, the approval mode, the spend against the
 * cap and the folder. People, Checklist (once step 4 has made one) and Show history open panels under it.
 */
export function WorkspaceHeader({ call, pursuit, checklist, label, tz }: {
  call: WorkspaceCall;
  pursuit: PursuitRow;
  checklist: ChecklistRow[];
  label: Label;
  tz: string;
}) {
  const collaborators = parseJson<string[]>(pursuit.collaborators, []);
  const stage = STAGES.find((s) => s.name === stepInfo(pursuit.current_step)?.stage);
  const { done, total } = checklistProgress(checklist);
  const due = formatDue(call.due_date, tz);
  return (
    <header className="ws-head">
      <PortalLogo portal={call.portal} />
      <div className="ws-head-text">
        <nav className="ws-crumb" aria-label="Breadcrumb">
          <a href="/proposals?view=drafting">Proposals</a>
          <ChevronRight aria-hidden="true" />
          <span>{pursuit.state === "working" ? stage?.doing : (STOPPED[pursuit.state] ?? pursuit.state)}</span>
        </nav>
        <h1 className="ws-title">{call.title || call.id}</h1>
        <p className="ws-facts">
          <span>{call.portal}</span>
          {pursuit.format ? <span>{pursuit.format}</span> : null}
          <span>
            Due <strong>{due || "not given"}</strong>
            {call.days_left !== null && call.days_left >= 0 ? `, ${call.days_left} ${call.days_left === 1 ? "day" : "days"} left` : ""}
          </span>
          <span>Owner: {label(pursuit.owner)}</span>
          {collaborators.length ? <span>Working with: {collaborators.map(label).join(", ")}</span> : null}
          <span>User approval required: {pursuit.approval_mode === "key_gates" ? "key gates only" : "every step"}</span>
          <span>
            Spent {money(pursuit.cost_usd)} of {money(pursuit.budget_usd)}
          </span>
          <span className="ws-folder">
            <FolderOpen aria-hidden="true" />
            {pursuit.drive_folder_id ? (
              <a href={`https://drive.google.com/drive/folders/${encodeURIComponent(pursuit.drive_folder_id)}`} target="_blank" rel="noreferrer">
                {pursuit.drive_folder_name || "The Drive folder"}
              </a>
            ) : (
              <span title="The documents stay on the scan PC until Drive is set up">On the scan PC until Drive is set up</span>
            )}
          </span>
        </p>
      </div>
      <div className="ws-tools">
        <button type="button" className="btn" data-panel="ws-people" aria-expanded="false">
          <Users aria-hidden="true" />
          People
        </button>
        {total ? (
          <button type="button" className="btn" data-panel="ws-checklist" aria-expanded="false">
            <ListChecks aria-hidden="true" />
            Checklist, {done} of {total} done
          </button>
        ) : null}
        <button type="button" className="btn" data-panel="ws-history" aria-expanded="false">
          <History aria-hidden="true" />
          Show history
        </button>
      </div>
    </header>
  );
}

/** The panels the header's buttons open (PW1, PW16, PW24): People, Checklist and Show history. */
export function WorkspacePanels({ call, pursuit, checklist, events, step, can, people, label, tz }: {
  call: WorkspaceCall;
  pursuit: PursuitRow;
  checklist: ChecklistRow[];
  events: EventRow[];
  step: string;
  can: Can;
  people: { name: string; label: string }[];
  label: Label;
  tz: string;
}) {
  const collaborators = parseJson<string[]>(pursuit.collaborators, []);
  const others = people.filter((person) => person.name !== pursuit.owner);
  return (
    <>
      <section id="ws-people" className="ws-panel" hidden aria-label="People">
        <div className="ws-panel-head">
          <h2>People</h2>
          <button type="button" className="btn-text" data-close-panel="ws-people">Close</button>
        </div>
        <p>
          <strong>{label(pursuit.owner)}</strong>, the owner
          {collaborators.length ? <>; working with {collaborators.map(label).join(", ")}</> : "; nobody else is working on it yet"}.
        </p>
        <p className="hint">
          Only the owner approves steps and decides the gates. The people working with them add material and past work, and
          tick checklist items.
        </p>
        {can.decide && pursuit.state === "working" && others.length ? (
          <form action={setCollaboratorsAction} className="ws-more-form">
            <input type="hidden" name="call_id" value={call.id} />
            <input type="hidden" name="step" value={step} />
            <fieldset className="field">
              <legend className="field-label">Working with</legend>
              <div className="chip-checks">
                {others.map((person) => (
                  <label key={person.name} className="chip-check">
                    <input type="checkbox" name="with" value={person.name} defaultChecked={collaborators.includes(person.name)} />
                    {person.label}
                  </label>
                ))}
              </div>
            </fieldset>
            <button type="submit" className="btn fn-change">Save who works on it</button>
          </form>
        ) : null}
      </section>
      {checklist.length ? (
        <section id="ws-checklist" className="ws-panel" hidden aria-label="Checklist">
          <div className="ws-panel-head">
            <h2>Submission checklist</h2>
            <button type="button" className="btn-text" data-close-panel="ws-checklist">Close</button>
          </div>
          <Checklist callId={call.id} step={step} items={checklist} editable={can.contribute && pursuit.state === "working"} label={label} />
        </section>
      ) : null}
      <section id="ws-history" className="ws-panel" hidden aria-label="History">
        <div className="ws-panel-head">
          <h2>History</h2>
          <button type="button" className="btn-text" data-close-panel="ws-history">Close</button>
        </div>
        <ol className="ws-history">
          {events.map((event) => (
            <li key={event.id}>
              <span className="when">{formatTime(event.at, tz)}</span>
              <span className="ws-history-who">{event.who === "worker" ? "Worker" : label(event.who)}</span>
              <span>{event.text}</span>
            </li>
          ))}
        </ol>
      </section>
    </>
  );
}

/** The stage strip (PW1): six stages, each done, now or next. */
export function StageStrip({ current, pursuitState }: { current: string; pursuitState: string }) {
  const states = stageStates(current, pursuitState);
  return (
    <ol className="ws-strip" aria-label="Stages">
      {STAGES.map((stage) => (
        <li key={stage.name} className={`ws-stage ${states[stage.name]}`} aria-current={states[stage.name] === "now" ? "step" : undefined}>
          <span className="ws-stage-name">{stage.label}</span>
          <span className="ws-stage-state">{states[stage.name]}</span>
        </li>
      ))}
    </ol>
  );
}

/** The step list (PW2, PW3): each step under its stage with its state in words; a reached step opens. */
export function StepList({ latest, open }: { latest: Map<string, StepRow>; open: string }) {
  return (
    <nav className="ws-steps" aria-label="Steps">
      {STAGES.map((stage) => (
        <div key={stage.name}>
          <h2 className="ws-steps-stage">{stage.label}</h2>
          <ol>
            {STEPS.filter((s) => s.stage === stage.name).map((s) => {
              const word = stateWord(latest.get(s.name));
              const inner = (
                <>
                  <span className="ws-step-num" aria-hidden="true">{s.number ?? "◆"}</span>
                  <span className="ws-step-name">{s.label}</span>
                  <span className={`badge tone-${stateTone(word)}`}>{word}</span>
                </>
              );
              return (
                <li key={s.name} className={s.name === open ? "open" : undefined}>
                  {latest.has(s.name) ? (
                    <a href={`?step=${s.name}`} aria-current={s.name === open ? "page" : undefined}>{inner}</a>
                  ) : (
                    <span className="ws-step-unreached">{inner}</span>
                  )}
                </li>
              );
            })}
          </ol>
        </div>
      ))}
    </nav>
  );
}

function Fields({ callId, row }: { callId: string; row: StepRow }) {
  return (
    <>
      <input type="hidden" name="call_id" value={callId} />
      <input type="hidden" name="step" value={row.step} />
      <input type="hidden" name="step_id" value={row.id} />
      <input type="hidden" name="expected" value={row.updated_at} />
    </>
  );
}

/** What a step's state says on its card (PW15, PW19): waiting, working, failed with Retry, budget reached with Raise the cap. */
function StateNotice({ callId, pursuit, row, can, worker, tz, label }: {
  callId: string;
  pursuit: PursuitRow;
  row: StepRow;
  can: Can;
  worker: { readiness: string; seenAt: string | null };
  tz: string;
  label: Label;
}) {
  const acts = actionsFor(row, { pursuitState: pursuit.state, decide: can.decide });
  switch (row.state) {
    case "queued":
      return (
        <p className="ws-notice">
          Waiting for the worker since {formatTime(row.queued_at, tz)}.
          {worker.readiness === "offline" ? ` The worker was last seen ${worker.seenAt ? formatTime(worker.seenAt, tz) : "a while ago"}; the step starts when it is back.` : ""}
          {worker.readiness === "not set up" ? " Drafting is not set up yet: the worker has not run." : ""}
        </p>
      );
    case "working":
      return <p className="ws-notice tone-info">The Writer is working on this step and asks nothing until it is saved.</p>;
    case "failed":
      return (
        <div className="ws-notice tone-conflict">
          <p>This step failed: {row.error || "no reason was recorded"}</p>
          {acts.retry ? (
            <form action={retryStepAction}>
              <Fields callId={callId} row={row} />
              <button type="submit" className="btn fn-change"><RotateCcw aria-hidden="true" />Retry</button>
            </form>
          ) : row.decision === "retried" ? <p className="meta">Retried by {label(row.decided_by ?? "")}.</p> : null}
        </div>
      );
    case "blocked":
      return (
        <div className="ws-notice tone-warn">
          <p>Budget reached: {money(pursuit.cost_usd)} spent of the {money(pursuit.budget_usd)} cap.</p>
          {acts.raiseCap ? (
            <form action={raiseCapAction} className="ws-inline-form">
              <Fields callId={callId} row={row} />
              <label className="field">
                <span className="field-label">New cap, in dollars</span>
                <input type="number" name="budget" min={Math.ceil(pursuit.budget_usd) + 1} max={10000} step="1" defaultValue={Math.ceil(pursuit.budget_usd) + 100} required />
              </label>
              <button type="submit" className="btn fn-change">Raise the cap</button>
            </form>
          ) : null}
        </div>
      );
    case "stopped":
      return <p className="ws-notice">{row.decision === "no_go" ? `Stopped with a no-go: ${row.decision_note ?? ""}` : "Stopped: the draft was closed."}</p>;
    default:
      return null;
  }
}

/** A step's own screen (PW6 to PW12), drawn from what the worker saved. */
function StepScreen({ call, pursuit, row, steps, checklist, changes, scan, library, content, can, label, tz }: {
  call: WorkspaceCall;
  pursuit: PursuitRow;
  row: StepRow;
  steps: StepRow[];
  checklist: ChecklistRow[];
  changes: ChangeRow[];
  scan: ScanRow | null;
  library: Library;
  content: Record<string, unknown>;
  can: Can;
  label: Label;
  tz: string;
}) {
  switch (row.step) {
    case "discovery":
      return <DiscoveryView row={row} content={content} />;
    case "summary":
      return <SummaryView call={call} content={content} tz={tz} />;
    case "alignment":
      return <AlignmentView pursuit={pursuit} content={content} label={label} tz={tz} />;
    case "requirements":
      return <RequirementsView callId={call.id} content={content} checklist={checklist}
        editable={can.contribute && pursuit.state === "working"} label={label} />;
    case "go_no_go":
      return <GateBrief content={content} />;
    case "outline":
      return <OutlineView call={call} pursuit={pursuit} content={content} row={row} canDecide={can.decide}
        canContribute={can.contribute} isLocked={locked(steps)} library={library} />;
    case "draft":
      return <DraftView step={row.step} content={content} />;
    case "compliance":
      return <ComplianceView step={row.step} content={content} />;
    case "reviews":
      return <ReviewsView callId={call.id} row={row} content={content} changes={changes} scan={scan}
        decidable={can.decide && row.state === "ready" && pursuit.state === "working"} label={label} tz={tz} />;
    case "final":
      return <FinalView callId={call.id} row={row} content={content} scan={scan} checklist={checklist}
        editable={can.contribute && pursuit.state === "working"} owner={pursuit.owner} label={label} />;
    case "submit":
      return <SubmitView call={call} content={content} checklist={checklist} tz={tz} />;
    default:
      return null;
  }
}

/** The open step's card (PW4): what it is for, its state, the files saved, what the Writer prepared, and Your call. */
export function StepCard({ call, pursuit, row, steps, checklist, changes, scan, job, library, can, worker, label, tz }: {
  call: WorkspaceCall;
  pursuit: PursuitRow;
  row: StepRow;
  steps: StepRow[];
  checklist: ChecklistRow[];
  changes: ChangeRow[];
  scan: ScanRow | null;
  job: ScanJob | null;
  library: Library;
  can: Can;
  worker: { readiness: string; seenAt: string | null };
  label: Label;
  tz: string;
}) {
  const word = stateWord(row);
  const content = parseJson<Record<string, unknown>>(row.content, {});
  const shown = row.content !== null || (row.step === "discovery" && row.task_states !== null);
  const conditions = Array.isArray(content.conditions) ? content.conditions.map(String).join("\n") : "";
  const files = parseJson<{ name: string; local?: string; word?: string; link?: string }[]>(row.files, []);
  const points = (row.summary ?? "").split("\n").map((line) => line.replace(/^\s*-\s*/, "").trim()).filter(Boolean);
  const document = typeof content.document === "string" ? content.document : "";
  const question = typeof content.question === "string" ? content.question : "Approve it to continue, or ask for changes.";
  const acts = actionsFor(row, { pursuitState: pursuit.state, decide: can.decide });
  const working = pursuit.state === "working";
  const mine = changes.filter((c) => c.step_id === row.id);
  // Reviews is approved once every change is decided (PW12); Final checks once the final version is Ready (PW13).
  const waiting = row.step === "reviews" ? openChangesReason(changeCounts(mine).proposed) : row.step === "final" ? finalGate(scan) : null;
  const checking = jobState(job, scan?.scanned_at ?? null);
  const discovery = steps.filter((s) => s.step === "discovery" && s.content).at(-1);
  const expected = expectedDefault({
    pursuit: pursuit.result_expected_by, pursuitSource: pursuit.result_expected_source,
    discovery: parseJson<{ result_expected?: { date?: string | null; source?: string | null } }>(discovery?.content, {}).result_expected ?? null,
    due: call.due_date,
  });
  return (
    <section className="ws-card" aria-labelledby="ws-step-title">
      <div className="ws-band">
        <h2 id="ws-step-title">
          {stepTitle(row.step)}
          {row.attempt > 1 ? <span className="ws-attempt"> · attempt {row.attempt}</span> : null}
        </h2>
        <span className={`badge tone-${stateTone(word)}`}>{word}</span>
      </div>
      <div className="ws-card-body">
        <p className="ws-purpose">
          {stepInfo(row.step)?.purpose}
          {row.state === "working" && row.started_at ? ` Started ${formatTime(row.started_at, tz)}.` : ""}
        </p>
        {row.request_note ? <p className="ws-redo">Redone after {label(row.requested_by)} asked: {row.request_note}</p> : null}
        <StateNotice callId={call.id} pursuit={pursuit} row={row} can={can} worker={worker} tz={tz} label={label} />
        {files.length ? (
          <ul className="ws-files">
            {files.map((file) => (
              <li key={file.name}>
                <FileText aria-hidden="true" />
                <span>
                  <strong>{file.name}</strong>
                  <span className="meta">
                    {file.link ? `Saved to the folder ${row.finished_at ? formatTime(row.finished_at, tz) : ""}` : `On the scan PC: data/drafting/pursuits/${file.word ?? file.local ?? ""}`}
                  </span>
                </span>
                {file.link ? <a href={file.link} target="_blank" rel="noreferrer">Open in Drive</a> : null}
              </li>
            ))}
          </ul>
        ) : null}
        {shown ? (
          <StepScreen call={call} pursuit={pursuit} row={row} steps={steps} checklist={checklist} changes={mine} scan={scan}
            library={library} content={content} can={can} label={label} tz={tz} />
        ) : null}
        {points.length ? (
          <section className="ws-points" aria-label="What the Writer prepared">
            <h3 className="field-label">What the Writer prepared</h3>
            <ul>
              {points.map((point, i) => <li key={i}>{point}</li>)}
            </ul>
          </section>
        ) : null}
        {document ? (
          <details className="ws-document">
            <summary>The full document</summary>
            <div className="ws-doc">{document}</div>
          </details>
        ) : null}
        {row.state === "approved" && row.decided_by ? (
          <p className="meta">
            Approved by {row.decided_by === "worker (key gates only)" ? "the worker (key gates only)" : label(row.decided_by)}
            {row.decided_at ? ` on ${formatTime(row.decided_at, tz)}` : ""}
            {row.decision_note ? `: ${row.decision_note}` : ""}
          </p>
        ) : null}
        {row.state === "ready" ? (
          <div className="ws-call">
            <p className="ws-call-label">Your call</p>
            <p className="ws-question">{question}</p>
            {!can.decide ? <p className="hint">Waiting on {label(pursuit.owner)}, the owner, to decide this step.</p> : null}
            {can.decide && waiting ? <p className="hint ws-waiting">{waiting}</p> : null}
            {row.step === "reviews" ? (
              <p className="hint">
                Approving queues Final checks, which puts the changes you accepted or edited into Draft v3; the AI slop check
                then runs on the final version on its own.
              </p>
            ) : null}
            {row.step === "final" && waiting ? (
              <p className="hint">
                Until Drive is set up, the final version is on the scan PC. Check again scans it once more; the result here
                updates when the worker has run it.
                {checking === "queued" || checking === "working" ? " A check is waiting for the worker now." : ""}
              </p>
            ) : null}
            {acts.submit ? (
              <form action={markSubmittedAction} className="ws-submit-form">
                <Fields callId={call.id} row={row} />
                <input type="hidden" name="expected_call" value={call.human_status ?? ""} />
                <input type="hidden" name="default_result_by" value={expected.date} />
                <input type="hidden" name="result_source" value={expected.note} />
                <div className="ws-submit-fields">
                  <label className="field">
                    <span className="field-label">Confirmation number from {call.portal}</span>
                    <input type="text" name="confirmation" maxLength={200} />
                  </label>
                  <label className="field">
                    <span className="field-label">Submitted at</span>
                    <input type="datetime-local" name="submitted_at" required defaultValue={localInput(isoNow(), tz)} />
                  </label>
                  <label className="field">
                    <span className="field-label">Result expected by</span>
                    <input type="date" name="result_by" required defaultValue={expected.date} />
                    {expected.note ? <span className="hint">{expected.note}</span> : null}
                  </label>
                </div>
                <p className="hint">
                  Mark submitted ends the workflow: the proposal waits in Proposals, Submitted and waiting, until its result is
                  recorded, and the call is recorded as Submitted.
                </p>
                <button type="submit" className="btn-primary fn-approve"><Send aria-hidden="true" />Mark submitted</button>
              </form>
            ) : null}
            <div className="ws-actions">
              {acts.approve ? (
                <form action={approveStepAction} className={row.step === "alignment" ? "ws-approve-direction" : undefined}>
                  <Fields callId={call.id} row={row} />
                  {row.step === "alignment" ? <DirectionChoice content={content} /> : null}
                  <button type="submit" className="btn-primary fn-approve" disabled={Boolean(waiting)}>
                    <Check aria-hidden="true" />{approveLabel(row.step)}
                  </button>
                </form>
              ) : null}
              {acts.gate ? (
                <>
                  <form action={approveStepAction}>
                    <Fields callId={call.id} row={row} />
                    <input type="hidden" name="decision" value="go" />
                    <button type="submit" className="btn-primary fn-approve"><Check aria-hidden="true" />Go</button>
                  </form>
                  <details className="ws-more">
                    <summary className="btn fn-approve">Go with conditions</summary>
                    <form action={approveStepAction} className="ws-more-form">
                      <Fields callId={call.id} row={row} />
                      <input type="hidden" name="decision" value="go_with_conditions" />
                      <label className="field">
                        <span className="field-label">Conditions, one per line</span>
                        <textarea name="conditions" rows={3} required maxLength={2000} defaultValue={conditions} />
                      </label>
                      <p className="hint">Each condition becomes a checklist item you own.</p>
                      <button type="submit" className="btn-primary fn-approve">Go with conditions</button>
                    </form>
                  </details>
                  <details className="ws-more">
                    <summary className="btn btn-destructive"><CircleX aria-hidden="true" />No-go</summary>
                    <form action={noGoAction} className="ws-more-form">
                      <Fields callId={call.id} row={row} />
                      <label className="field">
                        <span className="field-label">The reason, and what would change the answer</span>
                        <textarea name="note" rows={3} required maxLength={2000} />
                      </label>
                      <p className="hint">The call is marked Not relevant with your reason.</p>
                      <button type="submit" className="btn btn-destructive">Record the no-go</button>
                    </form>
                  </details>
                </>
              ) : null}
              {row.step === "final" && waiting && can.contribute && working ? (
                <form action={checkAgainAction}>
                  <Fields callId={call.id} row={row} />
                  <button type="submit" className="btn fn-change" disabled={checking === "queued" || checking === "working"}>
                    <RefreshCw aria-hidden="true" />Check again
                  </button>
                </form>
              ) : null}
              {acts.askChanges ? (
                <details className="ws-more">
                  <summary className="btn fn-change"><MessageSquare aria-hidden="true" />Ask for changes</summary>
                  <form action={askChangesAction} className="ws-more-form">
                    <Fields callId={call.id} row={row} />
                    <label className="field">
                      <span className="field-label">What to change</span>
                      <textarea name="note" rows={3} required maxLength={2000} />
                    </label>
                    <p className="hint">The Writer redoes the step with your note and its last version.</p>
                    <button type="submit" className="btn fn-change">Ask for changes</button>
                  </form>
                </details>
              ) : null}
              {acts.noGo ? (
                <details className="ws-more ws-stop">
                  <summary className="btn btn-destructive"><CircleX aria-hidden="true" />Stop here, no-go</summary>
                  <form action={noGoAction} className="ws-more-form">
                    <Fields callId={call.id} row={row} />
                    <label className="field">
                      <span className="field-label">The reason, and what would change the answer</span>
                      <textarea name="note" rows={3} required maxLength={2000} />
                    </label>
                    <p className="hint">The draft stops and the call is marked Not relevant with your reason.</p>
                    <button type="submit" className="btn btn-destructive">Stop here, no-go</button>
                  </form>
                </details>
              ) : null}
            </div>
          </div>
        ) : null}
        {can.contribute && working ? (
          <details className="ws-more ws-material">
            <summary className="btn fn-change"><Paperclip aria-hidden="true" />Add material</summary>
            <form action={addMaterialAction} className="ws-more-form">
              <Fields callId={call.id} row={row} />
              <label className="field">
                <span className="field-label">A note, or a link to a page or file</span>
                <textarea name="material" rows={3} required maxLength={2000} />
              </label>
              <p className="hint">The Writer reads it from the next step on. Files go in the draft&apos;s Drive folder once Drive is set up.</p>
              <button type="submit" className="btn fn-change">Add material</button>
            </form>
          </details>
        ) : null}
      </div>
    </section>
  );
}
