// The Description cell (Q13, PRO-571) and the Call cell's two lines of portal facts. No imports, so
// `node --test` can load it directly.

/** What the table shows of a description; the cell's hover and focus show `full`. */
const SHOWN = 300;
/** How much of a description the queries read, for the hover. The rest stays in the ledger. */
export const DESCRIPTION_READ = 1200;

/** Portals whose description the scanner writes, not the portal (handover-discovery, question 12). */
const WRITTEN_BY_SCANNER = new Set(["AFWERX", "SpaceWERX", "APFIT", "NASA Forecast"]);

export type DescriptionCell = { label: "Summary" | "Scanner summary" | "Members only" | null; text: string; full: string };

function membersOnly(extra: string | null | undefined): boolean {
  if (!extra) return false;
  try {
    const data: unknown = JSON.parse(extra);
    return Boolean(data && typeof data === "object" && (data as Record<string, unknown>).nstxl_members_only === true);
  } catch {
    return false;
  }
}

/**
 * Claude's executive summary of the call when the review wrote one (phase 9c), else the first 300 characters of its
 * description, labelled where the text is not the portal's own: Scanner summary for the text an adapter writes,
 * Members only for NSTXL's placeholder. The cell's hover shows the description in full either way.
 */
export function descriptionCell(
  portal: string,
  description: string | null | undefined,
  extra: string | null | undefined,
  summary?: string | null,
): DescriptionCell {
  const full = (description ?? "").trim();
  if (membersOnly(extra)) return { label: "Members only", text: "", full };
  if (summary?.trim()) return { label: "Summary", text: summary.trim(), full };
  const text = full.length > SHOWN ? `${full.slice(0, SHOWN).trimEnd()}…` : full;
  return { label: full && WRITTEN_BY_SCANNER.has(portal) ? "Scanner summary" : null, text, full };
}

type Item = { text: string; tone?: string };

/** The details line holds plain facts, separated by dots; anything with a tone is a badge on its own line. */
export function splitDetails<T extends Item>(items: T[]): { facts: T[]; badges: T[] } {
  return { facts: items.filter((i) => !i.tone), badges: items.filter((i) => Boolean(i.tone)) };
}

/** Where a call's details come from, for its reasons panel: each detail with a source, then the deadline's. */
export function detailSources(items: { text: string; title?: string }[], deadlineNote: string | null): { text: string; source: string }[] {
  const found = items.filter((i) => i.title).map((i) => ({ text: i.text, source: i.title as string }));
  return deadlineNote ? [...found, { text: "Deadline", source: deadlineNote }] : found;
}
