import type { Metadata } from "next";
import { Shell } from "@/components/Shell";
import { Badge } from "@/components/bits";
import { listProposals, winRateByPortal } from "@/lib/queries";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Proposals" };

export default async function ProposalsPage() {
  const [rows, rates] = await Promise.all([listProposals(), winRateByPortal()]);
  const won = rates.reduce((sum, r) => sum + r.won, 0);
  const decided = rates.reduce((sum, r) => sum + r.decided, 0);

  return (
    <Shell current="proposals">
      <div className="page-head">
        <div>
          <h1>Proposals</h1>
          <p className="muted">The register of past submissions from the proposals table.</p>
        </div>
      </div>

      {rows.length === 0 ? (
        <div className="empty">
          <p className="title">No past submissions in the register yet.</p>
          <p className="muted">
            The Proposal Corpus plan fills the proposals table from the hand-built register and the Drive folders. Once
            it runs, this page lists every submission with its outcome, strength rating and exemplar flag, plus win
            rates by portal.
          </p>
        </div>
      ) : (
        <>
          <div className="tiles">
            <div className="tile">
              <div className="label">All portals</div>
              <div className="value num">{decided ? `${((100 * won) / decided).toFixed(1)}%` : "n/a"}</div>
              <div className="muted num">
                {won} won of {decided} decided
              </div>
            </div>
            {rates.map((r) => (
              <div className="tile" key={r.portal ?? "unknown"}>
                <div className="label">{r.portal ?? "no portal"}</div>
                <div className="value num">{r.win_rate_pct === null ? "n/a" : `${r.win_rate_pct.toFixed(1)}%`}</div>
                <div className="muted num">
                  {r.won} won of {r.decided} decided
                </div>
              </div>
            ))}
          </div>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Submission</th>
                  <th>Portal</th>
                  <th>Type</th>
                  <th>Submitted</th>
                  <th>Outcome</th>
                  <th>Strength</th>
                  <th>Exemplar</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((p) => (
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
                    <td>{p.use_as_exemplar ? <span className="badge tone-info">exemplar</span> : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Shell>
  );
}
