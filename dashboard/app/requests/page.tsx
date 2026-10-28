import type { Metadata } from "next";
import { decideRequestAction } from "@/app/actions";
import { Shell } from "@/components/Shell";
import { Badge, Flash } from "@/components/bits";
import { formatTime } from "@/lib/format";
import { decidedRequests, waitingRequests, type RequestRow } from "@/lib/queries";
import { APPLY_WHEN, kindLabel, nextStep, previewText } from "@/lib/requests";
import { displayTimeZone } from "@/lib/settings";
import { firstParam } from "@/lib/text";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Requests" };

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function WaitingCard({ req, tz }: { req: RequestRow; tz: string }) {
  const preview = previewText(req.preview);
  return (
    <section className="latest edge-warn request" aria-label={`Request ${req.id}`} data-request-id={req.id}>
      <div className="meta">
        <span className="num">#{req.id}</span>
        <span className="badge tone-info">{kindLabel(req.kind)}</span>
        <span>
          asked by {req.requested_by}, <span className="when">{formatTime(req.requested_at, tz)}</span>
        </span>
      </div>
      <p className="request-summary">{req.summary}</p>
      {req.reason ? <p className="muted">Why: {req.reason}</p> : null}
      {preview ? <p className="preview">{preview}</p> : null}
      <form action={decideRequestAction} className="request-decide">
        <input type="hidden" name="id" value={req.id} />
        <input type="text" name="note" maxLength={2000} placeholder="Note (optional)" aria-label={`Note on request ${req.id}`} />
        <div className="buttons">
          <button type="submit" name="choice" value="approve" className="fn-approve" title={`Approve request ${req.id}`}>
            Approve
          </button>
          <button type="submit" name="choice" value="reject" className="fn-stop" title={`Reject request ${req.id}`}>
            Reject
          </button>
        </div>
      </form>
    </section>
  );
}

export default async function RequestsPage({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  const [waiting, decided] = await Promise.all([waitingRequests(), decidedRequests(50)]);
  const tz = displayTimeZone();

  return (
    <Shell current="requests">
      <div className="page-head">
        <div>
          <h1>Requests</h1>
          <p className="muted">
            Changes the portal assistant was asked to make. Nothing changes until someone approves a request here; the
            scan machine then carries it out {APPLY_WHEN}.
          </p>
        </div>
        <dl className="stats">
          <div>
            <dt>Waiting</dt>
            <dd>{waiting.length}</dd>
          </div>
        </dl>
      </div>

      <Flash notice={firstParam(sp.notice, 300)} error={firstParam(sp.error, 300)} />

      <h2>Waiting for approval</h2>
      {waiting.length === 0 ? (
        <div className="empty">
          <p className="title">Nothing is waiting for approval.</p>
          <p className="muted">
            A request appears here when someone asks the assistant to change a portal&apos;s keywords, review a call
            again, scan a portal now, start a draft or report a scraper fault.
          </p>
        </div>
      ) : (
        waiting.map((req) => <WaitingCard key={req.id} req={req} tz={tz} />)
      )}

      <h2>Decided</h2>
      {decided.length === 0 ? (
        <div className="empty">
          <p className="muted">No request has been decided yet.</p>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Request</th>
                <th>Status</th>
                <th>Asked by</th>
                <th>Decided</th>
                <th>Result</th>
              </tr>
            </thead>
            <tbody>
              {decided.map((req) => (
                <tr key={req.id} data-request-id={req.id}>
                  <td className="call">
                    <span>
                      <span className="num">#{req.id}</span> {req.summary}
                    </span>
                    <div className="meta">
                      <span>{kindLabel(req.kind)}</span>
                    </div>
                  </td>
                  <td>
                    <Badge value={req.status} />
                  </td>
                  <td className="nowrap">{req.requested_by}</td>
                  <td>
                    <span className="nowrap">{req.decided_by ?? ""}</span>
                    <div className="meta">
                      <span className="when">{formatTime(req.decided_at, tz)}</span>
                    </div>
                    {req.decision_note ? <div className="muted">{req.decision_note}</div> : null}
                  </td>
                  <td className="reason">
                    {req.status === "failed" ? (
                      <span className="error-text">{nextStep(req.kind, req.status, req.result)}</span>
                    ) : (
                      nextStep(req.kind, req.status, req.result)
                    )}
                    {req.applied_at ? (
                      <div className="meta">
                        <span className="when">{formatTime(req.applied_at, tz)}</span>
                      </div>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Shell>
  );
}
