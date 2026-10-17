// Who is looking at the dashboard. There is no auth system yet: decisions are attributed to a
// name from the DASHBOARD_USERS allowlist, or to the value of a trusted request header.
// No imports, so `node --test` can load it directly.

export type Person = { name: string; slackId: string | null };

/** "David Wood=U08V7ULPH1N, Aisha" -> [{name, slackId}, {name, slackId: null}] */
export function parseUsers(raw: string | null | undefined): Person[] {
  const seen = new Set<string>();
  const people: Person[] = [];
  for (const chunk of (raw ?? "").split(",")) {
    const eq = chunk.indexOf("=");
    const name = (eq === -1 ? chunk : chunk.slice(0, eq)).trim();
    if (!name || seen.has(name)) continue;
    seen.add(name);
    const slackId = eq === -1 ? "" : chunk.slice(eq + 1).trim();
    people.push({ name, slackId: slackId || null });
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
 * Header mode (DASHBOARD_USER_HEADER set): the header alone decides, and must be on the
 * allowlist when there is one. Otherwise: the picker cookie if it names an allowlisted
 * person, else the only allowlisted person, else nobody.
 */
export function pickViewer({ users, headerMode, headerValue, cookieValue }: ViewerInputs): string | null {
  const names = users.map((u) => u.name);
  if (headerMode) {
    const value = (headerValue ?? "").trim();
    if (!value) return null;
    return names.length === 0 || names.includes(value) ? value : null;
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
