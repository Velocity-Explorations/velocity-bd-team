import type { Metadata } from "next";
import { AutomationCards } from "@/components/AutomationCards";
import { PersonName } from "@/components/PersonName";
import { preloadShell, Shell } from "@/components/Shell";
import { Flash } from "@/components/bits";
import { weekLabel } from "@/lib/brief";
import { displayPerson } from "@/lib/people";
import { labeler } from "@/lib/me";
import { hasTopRatings, reviewBriefs, topPickRatings } from "@/lib/queries";
import { firstParam } from "@/lib/text";
import { PICK_LABELS, PICK_TONES, reviewWeeks, type Agreement } from "@/lib/toppicks";
import { allowlist } from "@/lib/viewer";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Top 10 reviews" };

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

const AGREEMENT: Record<Agreement, { text: string; tone: string }> = {
  agree: { text: "agree", tone: "good" },
  split: { text: "split", tone: "warn" },
  one: { text: "one rating", tone: "none" },
  none: { text: "not rated", tone: "none" },
};

/**
 * Top 10 reviews (Task 5 of the 9 Nov review, 18 Nov 2026; section Automation): each week's Top 10, newest first, with every
 * reviewer's rating of each pick (Good pick, Not a fit or Unsure, and why) from Home, and whether they agree. The ratings
 * are kept apart from decisions, and nothing ranks calls by them yet.
 */
export default async function TopTenReviewsPage({ searchParams }: { searchParams: SearchParams }) {
  preloadShell("automation");
  const sp = await searchParams;
  const ready = await hasTopRatings();
  const briefs = ready ? await reviewBriefs(8) : [];
  const weeks = reviewWeeks(briefs, await topPickRatings(briefs.map((b) => b.week)));
  const users = allowlist();
  const label = await labeler();
  const nameOf = (by: string) => label(displayPerson(by, users));

  return (
    <Shell section="automation">
      <h1 className="sr-only">Top 10 reviews</h1>
      <AutomationCards current="reviews" />
      <Flash notice={firstParam(sp.notice, 300)} error={firstParam(sp.error, 300)} />
      <div className="lead-line">
        <p className="muted">
          How each person rated each week&apos;s Top 10 picks on Home: Good pick, Not a fit or Unsure, and why. A split is a
          pick people see differently. The ratings are kept apart from decisions, and nothing ranks calls by them yet.
        </p>
      </div>
      {!ready ? (
        <div className="empty">
          <p className="title">Top 10 reviews need migration 022.</p>
          <p className="muted">
            Run <code>python -m ledger.migrate</code> against the live database, then reload this page.
          </p>
        </div>
      ) : weeks.length === 0 ? (
        <div className="empty">
          <p className="title">No Monday brief yet.</p>
          <p className="muted">Each week&apos;s Top 10 shows here once the Monday brief has picked it.</p>
        </div>
      ) : (
        weeks.map((w) => (
          <section key={w.week} className="review-week" aria-label={`Top 10, ${weekLabel(w.week)}`}>
            <h2>Top 10, {weekLabel(w.week)}</h2>
            <p className="muted review-summary">
              {w.summary.rated} of {w.summary.picks} picks rated
              {w.summary.agree || w.summary.split ? `; people agree on ${w.summary.agree} and split on ${w.summary.split}` : ""}.
            </p>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th className="num">#</th>
                    <th>Call</th>
                    {w.reviewers.map((r) => <th key={r}>{nameOf(r)}</th>)}
                    <th>Agreement</th>
                  </tr>
                </thead>
                <tbody>
                  {w.picks.map((p) => (
                    <tr key={p.id} data-call-id={p.id}>
                      <td className="num">{p.place}</td>
                      <td>
                        {p.title}
                        {p.portal ? <div className="meta">{p.portal}</div> : null}
                      </td>
                      {w.reviewers.map((r) => {
                        const rated = p.by[r];
                        return (
                          <td key={r} data-person={r}>
                            {rated ? (
                              <>
                                <span className={`badge tone-${PICK_TONES[rated.rating as keyof typeof PICK_TONES] ?? "none"}`}>
                                  {PICK_LABELS[rated.rating as keyof typeof PICK_LABELS] ?? rated.rating}
                                </span>
                                {rated.comment ? <span className="muted">{rated.comment}</span> : null}
                              </>
                            ) : (
                              <span className="muted">not rated</span>
                            )}
                          </td>
                        );
                      })}
                      <td className="agreement">
                        <span className={`badge tone-${AGREEMENT[p.agreement].tone}`}>{AGREEMENT[p.agreement].text}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {w.reviewers.length ? (
              <p className="muted">
                Rated by{" "}
                {w.reviewers.map((r, i) => (
                  <span key={r}>
                    {i ? ", " : ""}
                    <PersonName by={r}>{nameOf(r)}</PersonName>
                  </span>
                ))}
                .
              </p>
            ) : null}
          </section>
        ))
      )}
    </Shell>
  );
}
