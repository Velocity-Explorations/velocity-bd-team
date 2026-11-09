// Change requests (docs/LEDGER_SCHEMA.md, table change_requests): the allowed values and
// small parsers for the Requests page. No imports, so `node --test` can load it directly.

// No "draft" since 9 Nov 2026 (David): a draft starts from Start the draft.
export const REQUEST_KINDS = ["keyword_change", "rereview", "scan", "fault_report"] as const;
export const REQUEST_STATUSES = ["proposed", "approved", "rejected", "applying", "applied", "failed"] as const;

export type RequestKind = (typeof REQUEST_KINDS)[number];
export type RequestChoice = "approve" | "reject";

export const KIND_LABELS: Record<RequestKind, string> = {
  keyword_change: "Keyword change",
  rereview: "Re-review",
  scan: "Scan now",
  fault_report: "Fault report",
};

/** When the scan machine carries out approved requests (scripts/install-schedule.ps1, -RequestsAt). */
export const APPLY_WHEN = "at its next pass (12:07 or 17:07)";

export function isRequestChoice(value: unknown): value is RequestChoice {
  return value === "approve" || value === "reject";
}

export function kindLabel(kind: string): string {
  return (KIND_LABELS as Record<string, string>)[kind] ?? kind;
}

/** The preview's `text`, or "" when the JSON is missing or malformed. */
export function previewText(preview: string | null | undefined): string {
  if (!preview) return "";
  try {
    const data: unknown = JSON.parse(preview);
    if (data && typeof data === "object" && typeof (data as { text?: unknown }).text === "string") {
      return (data as { text: string }).text;
    }
  } catch {
    // fall through
  }
  return "";
}

/** What happens next, or what happened, for a request that has been decided. */
export function nextStep(kind: string, status: string, result: string | null): string {
  if (status === "approved") {
    if (result) return result;
    return `Approved. The scan machine carries it out ${APPLY_WHEN}.`;
  }
  if (status === "applying") return "Being carried out now.";
  return result ?? "";
}
