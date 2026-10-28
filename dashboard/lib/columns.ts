// The columns the review queue and All calls show, and which ones a person has hidden in the
// Table settings (PRO-555), kept per browser in a cookie. No imports, so `node --test` can load it.

export type TablePage = "queue" | "calls";
export type Column = { key: string; label: string; fixed?: boolean };
export type Hidden = Record<TablePage, string[]>;

export const COLUMNS_COOKIE = "bd_columns";

/**
 * Every column in the order the table shows it (PRO-571), with the Call cell's details and tags lines
 * and Needs review's note box as choices too (S1). A fixed column always shows.
 */
export const COLUMNS: Record<TablePage, Column[]> = {
  queue: [
    { key: "call", label: "Call", fixed: true },
    { key: "details", label: "Details under the title" },
    { key: "tags", label: "Tags under the title" },
    { key: "votes", label: "Votes" },
    { key: "description", label: "Description" },
    { key: "reason", label: "AI reason" },
    { key: "due", label: "Due" },
    { key: "seen", label: "First seen" },
    { key: "note", label: "Note box" },
    { key: "decide", label: "Decide", fixed: true },
  ],
  calls: [
    { key: "call", label: "Call", fixed: true },
    { key: "details", label: "Details under the title" },
    { key: "tags", label: "Tags under the title" },
    { key: "filter", label: "Filter" },
    { key: "votes", label: "Votes" },
    { key: "description", label: "Description" },
    { key: "reason", label: "AI reason" },
    { key: "notes", label: "Notes" },
    { key: "due", label: "Due" },
    { key: "seen", label: "First seen" },
    { key: "decide", label: "Decide", fixed: true },
  ],
};

// First seen is hidden until a person shows it (S4). All calls' Notes column, which the handoff
// replaces with a notes panel, is hidden too, so the table fits at 1280px.
const DEFAULT_HIDDEN: Hidden = { queue: ["seen"], calls: ["notes", "seen"] };
const PAGES = Object.keys(COLUMNS) as TablePage[];

function defaults(): Hidden {
  return { queue: [...DEFAULT_HIDDEN.queue], calls: [...DEFAULT_HIDDEN.calls] };
}

/** The columns hidden on each table: the cookie's choice, or the defaults where it has none. */
export function readHidden(cookie: string | null | undefined): Hidden {
  const hidden = defaults();
  if (!cookie) return hidden;
  let data: unknown;
  try {
    data = JSON.parse(cookie);
  } catch {
    return hidden;
  }
  if (!data || typeof data !== "object" || Array.isArray(data)) return hidden;
  for (const page of PAGES) {
    const keys = (data as Record<string, unknown>)[page];
    if (Array.isArray(keys)) hidden[page] = COLUMNS[page].filter((c) => !c.fixed && keys.includes(c.key)).map((c) => c.key);
  }
  return hidden;
}

/** What the Settings form saves: every column whose box was left unticked. */
export function hiddenFromForm(ticked: Set<string>): Hidden {
  const hidden = defaults();
  for (const page of PAGES) {
    hidden[page] = COLUMNS[page].filter((c) => !c.fixed && !ticked.has(`show:${page}:${c.key}`)).map((c) => c.key);
  }
  return hidden;
}

/** Whether a table shows a column. */
export function shows(hidden: Hidden, page: TablePage): (key: string) => boolean {
  return (key) => !hidden[page].includes(key);
}
