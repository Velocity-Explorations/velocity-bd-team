// Who is looking at the dashboard. Decisions are attributed to a name from the DASHBOARD_USERS
// allowlist: picked in the dashboard, or named by a sign-in proxy (Google's IAP, or another
// proxy's trusted header) by name or email.
// No imports, so `node --test` can load it directly.

export type Person = { name: string; email: string | null; slackId: string | null };

/** IAP's plain identity header puts this before the email. */
const IAP_PREFIX = "accounts.google.com:";

/** "David Wood <david@x.com>=U08V7ULPH1N, Aisha" -> [{name, email, slackId}, {name, email: null, slackId: null}] */
export function parseUsers(raw: string | null | undefined): Person[] {
  const seen = new Set<string>();
  const people: Person[] = [];
  for (const chunk of (raw ?? "").split(",")) {
    const eq = chunk.indexOf("=");
    const who = (eq === -1 ? chunk : chunk.slice(0, eq)).trim();
    const bracket = /^(.*?)\s*<([^<>\s]+)>$/.exec(who);
    const name = bracket ? bracket[1].trim() : who;
    if (!name || seen.has(name)) continue;
    seen.add(name);
    const slackId = eq === -1 ? "" : chunk.slice(eq + 1).trim();
    people.push({ name, email: bracket ? bracket[2] : null, slackId: slackId || null });
  }
  return people;
}

type ViewerInputs = {
  users: Person[];
  headerMode: boolean;
  headerValue?: string | null;
  cookieValue?: string | null;
};

/**
 * Header mode (a sign-in proxy names the viewer): that identity alone decides. It must match an
 * allowlisted name, or an allowlisted email in any case, when there is an allowlist; the
 * person's name is returned either way. Otherwise: the picker cookie if it names an
 * allowlisted person, else the only allowlisted person, else nobody.
 */
export function pickViewer({ users, headerMode, headerValue, cookieValue }: ViewerInputs): string | null {
  const names = users.map((u) => u.name);
  if (headerMode) {
    let value = (headerValue ?? "").trim();
    if (value.toLowerCase().startsWith(IAP_PREFIX)) value = value.slice(IAP_PREFIX.length);
    if (!value) return null;
    if (names.length === 0) return value;
    const lower = value.toLowerCase();
    return users.find((u) => u.name === value || u.email?.toLowerCase() === lower)?.name ?? null;
  }
  const chosen = (cookieValue ?? "").trim();
  if (chosen && names.includes(chosen)) return chosen;
  return names.length === 1 ? names[0] : null;
}

/** Slack decisions store a Slack user id in human_by; show the allowlisted name instead. */
export function displayPerson(by: string | null | undefined, users: Person[]): string {
  if (!by) return "";
  return users.find((u) => u.slackId === by)?.name ?? by;
}

/** The names a person's decisions are recorded under: their name, and their Slack id for decisions made in Slack. */
export function aliasesFor(name: string, users: Person[]): string[] {
  const slackId = users.find((u) => u.name === name)?.slackId;
  return slackId ? [name, slackId] : [name];
}
