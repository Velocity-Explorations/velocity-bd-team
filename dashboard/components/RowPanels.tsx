import { X } from "lucide-react";
import type { ReactNode } from "react";
import { Badge } from "@/components/bits";
import { rankReason, whyThisScore, type FitColumns } from "@/lib/fit";
import { JUDGES, type Verdicts } from "@/lib/judges";

/** A panel's element id: one reasons panel per call, under its row. A person's notes sit beside their vote (NoteTip in
 *  CallCells) since 16 Nov 2026, in place of the notes panel. */
export function panelId(kind: "reasons", callId: string): string {
  return `${kind}-${callId}`;
}

function Panel({ id, callId, colSpan, title, open, children }: {
  id: string;
  callId: string;
  colSpan: number;
  title: string;
  open: boolean;
  children: ReactNode;
}) {
  return (
    <tr className="panel-row" id={id} data-for={callId} hidden={!open}>
      <td colSpan={colSpan}>
        <div className="panel">
          <div className="panel-head">
            <p className="menu-title">{title}</p>
            <button type="button" className="panel-close" data-close-panel={id} aria-label={`Close ${title.toLowerCase()}`}>
              <X aria-hidden="true" />
            </button>
          </div>
          {children}
        </div>
      </td>
    </tr>
  );
}

/**
 * Reasons (PRO-572): why the call scored what it did, both judges' verdicts and reasons, then where the call's details
 * come from. Why this score (Task 4, 18 Nov 2026) shows only what was computed: the score and band, each part
 * review/fit.py rated, the keywords the filter matched, and, for a call in this week's Top 10, how its rule ranked it.
 */
export function ReasonsPanel({ callId, colSpan, verdicts, sources, fit, rank, open = false }: {
  callId: string;
  colSpan: number;
  verdicts: Verdicts;
  sources: { text: string; source: string }[];
  fit?: Partial<FitColumns>;
  rank?: { place: number; daysLeft: number | null } | null;
  open?: boolean;
}) {
  const why = fit ? whyThisScore(fit) : null;
  return (
    <Panel id={panelId("reasons", callId)} callId={callId} colSpan={colSpan} title="Reasons" open={open}>
      {why ? (
        <div className="panel-why">
          <p className="menu-title">Why this score</p>
          <p className="why-headline">{why.headline}</p>
          {why.parts.length ? (
            <ul className="why-parts">
              {why.parts.map((part) => <li key={part}>{part}</li>)}
            </ul>
          ) : null}
          {why.matched.length ? (
            <p className="why-note">
              Keywords the filter matched: {why.matched.join(", ")}. Each counts only where the team rated it and it stands
              as a whole word; anything not rated counts as Neutral and is not listed.
            </p>
          ) : null}
          {rank ? (
            <p className="why-rank">
              <strong>#{rank.place} in this week&apos;s Top 10.</strong>{" "}
              {rankReason({ claude: verdicts.claude?.verdict ?? null, grok: verdicts.grok?.verdict ?? null, daysLeft: rank.daysLeft, score: fit?.fit_score ?? null })}
            </p>
          ) : null}
        </div>
      ) : null}
      <div className="panel-reasons">
        {JUDGES.map(({ key, label }) => (
          <div key={key}>
            <p className="panel-who">
              {label} <Badge value={verdicts[key]?.verdict} empty={key === "grok" ? "not yet" : "not reviewed"} />
            </p>
            <p>{verdicts[key]?.reasoning || "No reason recorded."}</p>
          </div>
        ))}
      </div>
      {sources.length ? (
        <>
          <p className="menu-title">Where the details come from</p>
          <ul className="panel-sources">
            {sources.map((s) => (
              <li key={`${s.text}:${s.source}`}>
                <strong>{s.text}:</strong> {s.source}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </Panel>
  );
}
