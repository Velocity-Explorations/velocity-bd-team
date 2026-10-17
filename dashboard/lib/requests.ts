// Change requests (docs/LEDGER_SCHEMA.md, table change_requests): the allowed values and
// small parsers for the Requests page. No imports, so `node --test` can load it directly.

export const REQUEST_KINDS = ["keyword_change", "rereview", "scan", "draft", "fault_report"] as const;
export const REQUEST_STATUSES = ["proposed", "approved", "rejected", "applying", "applied", "failed"] as const;

export type RequestKind = (typeof REQUEST_KINDS)[number];
export type RequestChoice = "approve" | "reject";

export const KIND_LABELS: Record<RequestKind, string> = {
  keyword_change: "Keyword change",
  rereview: "Re-review",
  scan: "Scan now",
  draft: "Start a draft",
  fault_report: "Fault report",
};

/** How often the scan machine looks for approved requests (scripts/install-schedule.ps1). */
export const APPLY_EVERY = "15 minutes";

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
    if (kind === "draft") return "Approved. The Writer starts the draft once it is built.";
    if (result) return result;
    return `Approved. The scan machine carries it out within ${APPLY_EVERY}.`;
  }
  if (status === "applying") return "Being carried out now.";
  return result ?? "";
}
