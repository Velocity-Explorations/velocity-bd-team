import { X } from "lucide-react";
import type { ReactNode } from "react";
import { Badge } from "@/components/bits";
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

/** Reasons (PRO-572): both judges' verdicts and reasons, then where the call's details come from. */
export function ReasonsPanel({ callId, colSpan, verdicts, sources, open = false }: {
  callId: string;
  colSpan: number;
  verdicts: Verdicts;
  sources: { text: string; source: string }[];
  open?: boolean;
}) {
  return (
    <Panel id={panelId("reasons", callId)} callId={callId} colSpan={colSpan} title="Reasons" open={open}>
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
