// The columns the review queue and All calls show, and which ones a person has hidden in the
// Settings dialog (PRO-555), kept per browser in a cookie. No imports, so `node --test` can load it.

export type TablePage = "queue" | "calls";
export type Column = { key: string; label: string; fixed?: boolean };
export type Hidden = Record<TablePage, string[]>;

export const COLUMNS_COOKIE = "bd_columns";

/** Every column in the order the table shows it. A fixed column always shows. */
export const COLUMNS: Record<TablePage, Column[]> = {
  queue: [
    { key: "judges", label: "Claude / Grok" },
    { key: "call", label: "Call", fixed: true },
    { key: "due", label: "Due" },
    { key: "tier", label: "Tier" },
    { key: "reason", label: "AI reason" },
    { key: "seen", label: "First seen" },
    { key: "votes", label: "Decided so far" },
    { key: "decide", label: "Decide", fixed: true },
  ],
  calls: [
    { key: "call", label: "Call", fixed: true },
    { key: "filter", label: "Filter" },
    { key: "judges", label: "Claude / Grok" },
    { key: "decision", label: "Decision", fixed: true },
    { key: "notes", label: "Notes" },
    { key: "due", label: "Due" },
    { key: "seen", label: "First seen" },
  ],
};

// Tier (the keyword filter's match strength) is hidden until a person shows it.
const DEFAULT_HIDDEN: Hidden = { queue: ["tier"], calls: [] };
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
