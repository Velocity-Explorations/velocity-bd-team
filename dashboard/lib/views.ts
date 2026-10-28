// The view cards each section opens on (PRO-570, PRO-571): Calls' views of the queue and All calls,
// and Automation's pages. Switching cards keeps the bar's portal, tag and open or closed filters and
// drops the sort and the column filters (N6). No imports, so `node --test` can load it directly.

export type CallView = "needs-review" | "top10" | "due-soon" | "judges-agree" | "judges-disagree" | "new";
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

const CALL_VIEWS: CallView[] = ["needs-review", "top10", "due-soon", "judges-agree", "judges-disagree", "new"];

export const VIEW_LABELS: Record<CallCard, string> = {
  "needs-review": "Needs review",
  top10: "Top 10",
  "due-soon": "Due soon",
  "judges-agree": "Judges agree",
  "judges-disagree": "Judges disagree",
  new: "New this week",
  all: "All calls",
};

/** The bar's filters, which every card keeps. */
const KEPT = ["portal", "tag", "state"] as const;

/** Days ahead that make a waiting call Due soon. */
export const DUE_SOON_DAYS = 14;
/** Days back that make a waiting call New this week. */
export const NEW_DAYS = 7;

export function pickCallView(raw: string | string[] | undefined): CallView {
  const value = Array.isArray(raw) ? raw[0] : raw;
  return CALL_VIEWS.includes(value as CallView) ? (value as CallView) : "needs-review";
}

/** The judges filter a view applies: the judges views set it themselves, the others take the header's. */
export function viewJudges(view: CallView, judges: string): string {
  if (view === "judges-agree") return "agree";
  if (view === "judges-disagree") return "disagree";
  return judges;
}

/**
 * The card a view and its column filters show as pressed (VC4): the view's own, or Judges agree or
 * disagree when Needs review's judges filter says so; none when a column filter narrows the table
 * past every view.
 */
export function pressedCard(view: CallView, columns: { judges: string; verdict: string; tier: string }): CallView | null {
  if (columns.verdict || columns.tier) return null;
  if (view === "judges-agree" || view === "judges-disagree" || !columns.judges) return view;
  if (view === "needs-review") return columns.judges === "agree" ? "judges-agree" : "judges-disagree";
  return null;
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

/**
 * Calls' cards in order: Needs review (the count that needs the viewer), Top 10, Due soon, Judges
 * agree, Judges disagree, New this week, All calls. `current` null leaves none pressed.
 */
export function callViewCards(input: {
  current: CallCard | null;
  params: Record<string, string | readonly string[]>;
  counts: Record<CallCard, number>;
  perPerson: boolean;
  dueBy: string;
  newSince: string;
  briefWeek: string | null;
  agree: { both: number; agree: number } | null;
}): ViewCard[] {
  const { agree } = input;
  const lines: Record<CallCard, string> = {
    "needs-review": input.perPerson ? "every call waiting for you" : "nobody has decided these",
    top10: input.briefWeek ? `Monday brief, ${input.briefWeek}, decided or not` : "the live ranking, until the first brief",
    "due-soon": `closing by ${input.dueBy}`,
    "judges-agree": agree && agree.both
      ? `same verdict; ${Math.round((100 * agree.agree) / agree.both)}% of all calls, ${agree.agree} of ${agree.both}`
      : "same verdict",
    "judges-disagree": "yes vs no listed first",
    new: `first seen since ${input.newSince}`,
    all: "every call scanned, rejects too",
  };
  return ([...CALL_VIEWS, "all"] as CallCard[]).map((key) => ({
    key,
    label: VIEW_LABELS[key],
    count: input.counts[key],
    description: lines[key],
    href: key === "all" ? href("/calls", null, input.params) : href("/review", key === "needs-review" ? null : key, input.params),
    current: input.current === key,
    needsYou: key === "needs-review",
  }));
}

/** Automation's cards: Agent update requests (the count that needs the viewer), Scans, Judges agree. */
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
