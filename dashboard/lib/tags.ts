// Each call's tags as the dashboard shows them (PRO-557). call_tags keeps who set each tag: the
// call's own data ("rule"), Claude or Grok; tag_list gives each tag's group and place in the list.
// No imports, so `node --test` can load it directly.

export type TagRow = { call_id: string; tag: string; source: string; tag_group: string | null; position: number | null };
export type TagOption = { name: string; tag_group: string; covers: string | null };
export type TagBadge = { text: string; tone: "info" | "grey"; title: string };

const SOURCES = ["rule", "claude", "grok"];   // the order a call's type is chosen in, and who is named first
const SOURCE_NAMES: Record<string, string> = { rule: "the call's data", claude: "Claude", grok: "Grok" };
const GROUPS: [string, string][] = [["type", "Type"], ["work", "Work"], ["customer", "Customer"], ["access", "Access"]];

function listed(names: string[]): string {
  return names.length < 2 ? names.join("") : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

function setBy(sources: Set<string>): string {
  return listed(SOURCES.filter((s) => sources.has(s)).map((s) => SOURCE_NAMES[s]));
}

/**
 * Each call's tags as badges: its one type first (from the call's data, else Claude's, else Grok's),
 * then the rest in the list's order, a tag no longer on the list last. Hovering says who set each,
 * and which other type a judge picked.
 */
export function tagsByCall(rows: TagRow[]): Map<string, TagBadge[]> {
  const byCall = new Map<string, TagRow[]>();
  for (const row of rows) byCall.set(row.call_id, [...(byCall.get(row.call_id) ?? []), row]);
  const shown = new Map<string, TagBadge[]>();
  for (const [callId, callRows] of byCall) {
    const who = new Map<string, Set<string>>();
    const place = new Map<string, { group: string | null; position: number }>();
    const typeBy = new Map<string, string>();
    for (const row of callRows) {
      who.set(row.tag, (who.get(row.tag) ?? new Set<string>()).add(row.source));
      place.set(row.tag, { group: row.tag_group, position: row.position ?? Number.MAX_SAFE_INTEGER });
      if (row.tag_group === "type" && !typeBy.has(row.source)) typeBy.set(row.source, row.tag);
    }
    const badges: TagBadge[] = [];
    const type = SOURCES.map((s) => typeBy.get(s)).find((t): t is string => Boolean(t));
    if (type) {
      const others = SOURCES.filter((s) => typeBy.has(s) && typeBy.get(s) !== type)
        .map((s) => ` ${SOURCE_NAMES[s]} picked ${typeBy.get(s)}.`)
        .join("");
      badges.push({ text: type, tone: "info", title: `Type, set by ${setBy(who.get(type) ?? new Set())}.${others}` });
    }
    const rest = [...who.keys()]
      .filter((tag) => place.get(tag)?.group !== "type")
      .sort((a, b) => (place.get(a)?.position ?? 0) - (place.get(b)?.position ?? 0) || a.localeCompare(b));
    for (const tag of rest) badges.push({ text: tag, tone: "grey", title: `Set by ${setBy(who.get(tag) ?? new Set())}` });
    shown.set(callId, badges);
  }
  return shown;
}

/** The Tag filter's choices, grouped as the list is. */
export function optionGroups(options: TagOption[]): { label: string; names: string[] }[] {
  return GROUPS.map(([group, label]) => ({ label, names: options.filter((o) => o.tag_group === group).map((o) => o.name) }))
    .filter((g) => g.names.length > 0);
}

/** A call's details without any that repeat a tag it shows (NSTXL's "members only" badge, say). */
export function withoutTags<T extends { text: string }>(details: T[], badges: TagBadge[]): T[] {
  const tagged = new Set(badges.map((b) => b.text.toLowerCase()));
  return details.filter((d) => !tagged.has(d.text.toLowerCase()));
}
