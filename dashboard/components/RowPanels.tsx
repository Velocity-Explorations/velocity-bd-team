import { X } from "lucide-react";
import type { ReactNode } from "react";
import { Badge } from "@/components/bits";
import { noteSource } from "@/lib/decide";
import { formatTime } from "@/lib/format";
import { JUDGES, type Verdicts } from "@/lib/judges";
import type { NoteParts } from "@/lib/text";

/** A panel's element id: one reasons and one notes panel per call, under its row. */
export function panelId(kind: "reasons" | "notes", callId: string): string {
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

/** Notes (PRO-572): each note with who left it, when, and where: on the dashboard or a Slack thread reply. */
export function NotesPanel({ callId, colSpan, notes, nameOf, tz }: {
  callId: string;
  colSpan: number;
  notes: NoteParts[];
  nameOf: (by: string | null) => string;
  tz: string;
}) {
  return (
    <Panel id={panelId("notes", callId)} callId={callId} colSpan={colSpan} title="Notes" open={false}>
      <ul className="panel-notes">
        {notes.map((n, i) => (
          <li key={i}>
            <p>{n.text}</p>
            <p className="meta">
              {n.by ? <span>{nameOf(n.by)}</span> : null}
              {n.at ? <span className="when">{formatTime(n.at, tz)}</span> : null}
              <span>{noteSource(n.by)}</span>
            </p>
          </li>
        ))}
      </ul>
    </Panel>
  );
}
