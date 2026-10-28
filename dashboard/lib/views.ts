// The view cards each section opens on (PRO-570): Calls' views of the queue and All calls, and
// Automation's pages. Switching cards keeps the bar's portal, tag and open or closed filters and
// drops the sort and the column filters (N6). No imports, so `node --test` can load it directly.

export type CallView = "needs-review" | "due-soon";
export type CallCard = CallView | "all";
export type AutomationPage = "requests" | "runs" | "judges";

/** One card: its band, number and line, where it goes, and whether it is the open view. */
export type ViewCard = {
  key: string;
  label: string;
  count: number | string;
  description: string;
  href: string;
  current: boolean;
  needsYou: boolean;
};

const CALL_VIEWS: CallView[] = ["needs-review", "due-soon"];

/** The bar's filters, which every card keeps. */
const KEPT = ["portal", "tag", "state"] as const;

/** Days ahead that make a waiting call Due soon. */
export const DUE_SOON_DAYS = 14;

export function pickCallView(raw: string | string[] | undefined): CallView {
  const value = Array.isArray(raw) ? raw[0] : raw;
  return CALL_VIEWS.includes(value as CallView) ? (value as CallView) : "needs-review";
}

function href(base: string, view: string | null, params: Record<string, string | readonly string[]>): string {
  const query = new URLSearchParams();
  if (view) query.append("view", view);
  for (const key of KEPT) {
    const value = params[key];
    for (const item of typeof value === "string" ? [value] : (value ?? [])) {
      if (item) query.append(key, item);
    }
  }
  const text = query.toString();
  return text ? `${base}?${text}` : base;
}

/** Calls' cards: Needs review (the count that needs the viewer, in the accent), Due soon, All calls. */
export function callViewCards(input: {
  current: CallCard;
  params: Record<string, string | readonly string[]>;
  counts: Record<CallCard, number>;
  perPerson: boolean;
  dueBy: string;
}): ViewCard[] {
  const { current, params, counts } = input;
  return [
    {
      key: "needs-review",
      label: "Needs review",
      count: counts["needs-review"],
      description: input.perPerson ? "every call waiting for you" : "every call nobody has decided",
      href: href("/review", null, params),
      current: current === "needs-review",
      needsYou: true,
    },
    {
      key: "due-soon",
      label: "Due soon",
      count: counts["due-soon"],
      description: `closing by ${input.dueBy}`,
      href: href("/review", "due-soon", params),
      current: current === "due-soon",
      needsYou: false,
    },
    {
      key: "all",
      label: "All calls",
      count: counts.all,
      description: "every call scanned, rejects too",
      href: href("/calls", null, params),
      current: current === "all",
      needsYou: false,
    },
  ];
}

/** Automation's cards: Agent update requests (in the accent), Scans, Judges agree. */
export function automationCards(input: {
  current: AutomationPage;
  waiting: number;
  kinds: string;
  runs: number;
  lastRun: string;
  agree: { both: number; agree: number } | null;
}): ViewCard[] {
  const { agree } = input;
  return [
    {
      key: "requests",
      label: "Agent update requests",
      count: input.waiting,
      description: input.waiting ? input.kinds : "nothing waiting",
      href: "/requests",
      current: input.current === "requests",
      needsYou: true,
    },
    {
      key: "runs",
      label: "Scans",
      count: input.runs,
      description: input.runs ? input.lastRun : "no scans yet",
      href: "/runs",
      current: input.current === "runs",
      needsYou: false,
    },
    {
      key: "judges",
      label: "Judges agree",
      count: agree && agree.both ? `${Math.round((100 * agree.agree) / agree.both)}%` : "none",
      description: agree && agree.both ? `${agree.agree} of ${agree.both} calls` : "no call judged by both yet",
      href: "/judges",
      current: input.current === "judges",
      needsYou: false,
    },
  ];
}
