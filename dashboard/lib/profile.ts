// Profile settings (U2 to U6, PRO-574): reading and checking the form, the default filters for Calls,
// and when an arrival counts as opening the dashboard. One row per person in the ledger's profiles
// table. No imports, so `node --test` can load it directly.

export type CallState = "" | "open" | "closed";
export type DefaultFilters = { portals: string[]; tag: string; state: CallState };
export type ProfileFields = {
  display_name: string | null;
  initials: string | null;
  opens: "home" | "calls";
  default_filters: DefaultFilters | null;
  time_zone: string | null;
};

const NO_FILTERS: DefaultFilters = { portals: [], tag: "", state: "" };

/** The zones offered in Profile settings, US first. Any zone the runtime knows is accepted. */
export const TIME_ZONES = [
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Phoenix",
  "America/Los_Angeles",
  "America/Anchorage",
  "Pacific/Honolulu",
  "UTC",
  "Europe/London",
];

function pickState(value: unknown): CallState {
  return value === "open" || value === "closed" ? value : "";
}

/** A profile's default_filters JSON, read defensively: anything odd reads as no filter. */
export function parseDefaultFilters(text: string | null | undefined): DefaultFilters {
  if (!text) return { ...NO_FILTERS };
  try {
    const data: unknown = JSON.parse(text);
    if (!data || typeof data !== "object" || Array.isArray(data)) return { ...NO_FILTERS };
    const d = data as Record<string, unknown>;
    return {
      portals: Array.isArray(d.portals) ? d.portals.filter((p): p is string => typeof p === "string") : [],
      tag: typeof d.tag === "string" ? d.tag : "",
      state: pickState(d.state),
    };
  } catch {
    return { ...NO_FILTERS };
  }
}

/** Where the Calls link goes: Needs review with the person's default filters (U4). */
export function callsHref(filters: DefaultFilters | null): string {
  const query = new URLSearchParams();
  for (const portal of filters?.portals ?? []) query.append("portal", portal);
  if (filters?.tag) query.append("tag", filters.tag);
  if (filters?.state) query.append("state", filters.state);
  const text = query.toString();
  return text ? `/review?${text}` : "/review";
}

export function isValidTimeZone(zone: string): boolean {
  if (!zone) return false;
  try {
    new Intl.DateTimeFormat("en-US", { timeZone: zone });
    return true;
  } catch {
    return false;
  }
}

/**
 * The form, checked: the display name trimmed to 60 characters, initials as up to three capital
 * letters, the default filters among the portals and tags that exist, and a time zone the runtime
 * knows. A value equal to the default is stored as no setting, so the default can change later.
 */
export function profileFromForm(
  form: { get(key: string): string[] | undefined },
  name: string,
  known: { portals: string[]; tags: string[] },
): ProfileFields {
  const one = (key: string) => (form.get(key) ?? [])[0]?.trim() ?? "";
  const displayName = one("display_name").slice(0, 60);
  const initials = one("initials").replace(/[^A-Za-z]/g, "").slice(0, 3).toUpperCase();
  const portals = [...new Set(form.get("portal") ?? [])].filter((p) => known.portals.includes(p));
  const tag = known.tags.includes(one("tag")) ? one("tag") : "";
  const filters: DefaultFilters = { portals, tag, state: pickState(one("state")) };
  const zone = one("time_zone");
  return {
    display_name: displayName && displayName !== name ? displayName : null,
    initials: initials || null,
    opens: one("opens") === "calls" ? "calls" : "home",
    default_filters: portals.length || tag || filters.state ? filters : null,
    time_zone: isValidTimeZone(zone) ? zone : null,
  };
}

/** Whether a Referer is one of the dashboard's own pages. */
export function sameOrigin(referer: string, host: string): boolean {
  try {
    return new URL(referer).host === host;
  } catch {
    return false;
  }
}

/** Opening the dashboard: an arrival with no Referer or one from elsewhere, not a move between its pages (U3). */
export function isFreshArrival(referer: string | null, host: string): boolean {
  return !referer || !sameOrigin(referer, host);
}

/**
 * Where Calls opened fresh with no bar filter in its address goes instead: the same address with the
 * person's default filters (U4). Null when the address has its own (a shared link wins) or there are
 * no defaults.
 */
export function withDefaultFilters(
  path: string,
  params: Record<string, string | string[] | undefined>,
  defaults: DefaultFilters | null,
): string | null {
  if (!defaults || (!defaults.portals.length && !defaults.tag && !defaults.state)) return null;
  if (["portal", "tag", "state", "open"].some((key) => params[key] !== undefined)) return null;
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    for (const item of Array.isArray(value) ? value : value === undefined ? [] : [value]) query.append(key, item);
  }
  for (const portal of defaults.portals) query.append("portal", portal);
  if (defaults.tag) query.append("tag", defaults.tag);
  if (defaults.state) query.append("state", defaults.state);
  return `${path}?${query.toString()}`;
}
