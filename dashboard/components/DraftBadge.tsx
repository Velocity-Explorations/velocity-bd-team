import { draftBadge, stepLabel, stepStateWords } from "@/lib/proposals";
import type { DraftInfo } from "@/lib/queries";

/**
 * A call's draft badge (DB1 to DB3, PRO-576), on its own line under the call's details: draft started,
 * step N, draft finished, or submitted with its date. It opens a menu: the draft in Google Drive, the
 * call in Proposals, and a line saying who owns it and where it stands, or who submitted it, when, and
 * when the result is expected.
 */
export function DraftBadge({ draft, nameOf }: { draft: DraftInfo; nameOf: (by: string | null) => string }) {
  const badge = draftBadge(draft);
  if (!badge) return null;
  const submitted = draft.pursuit_state === "submitted";
  const drive = draft.drive_folder_id ? `https://drive.google.com/drive/folders/${encodeURIComponent(draft.drive_folder_id)}` : null;
  const line = submitted
    ? `Submitted by ${nameOf(draft.submitted_by)}${draft.submitted_at ? ` on ${draft.submitted_at.slice(0, 10)}` : ""}${draft.result_expected_by ? `; result expected by ${draft.result_expected_by}` : ""}.`
    : `Owned by ${nameOf(draft.owner)}: ${stepLabel(draft.current_step)}, ${stepStateWords(draft.step_state)}.`;
  return (
    <div className="meta draft-line">
      <details className="menu draft-badge">
        <summary className={`badge tone-${badge.tone}`}>{badge.text}</summary>
        <div className="menu-body">
          <p className="hint">{line}</p>
          {drive ? (
            <a href={drive} target="_blank" rel="noreferrer">
              {submitted ? "View the submission in Google Drive" : "View the draft in Google Drive"}
            </a>
          ) : (
            <p className="hint">The Drive folder shows here once the worker creates it.</p>
          )}
          <a href={submitted ? "/proposals/submitted" : "/proposals?view=drafting"}>View in Proposals</a>
        </div>
      </details>
    </div>
  );
}
