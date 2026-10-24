// The portal details shown under each call's title, read from its columns and calls.extra.
// Each portal adapter documents its extra keys in docs/LEDGER_SCHEMA.md.
// No imports, so `node --test` can load it directly.

export type Detail = { text: string; href?: string; tone?: "warn" | "info" | "grey"; title?: string };

export type DetailRow = {
  portal: string | null;
  type: string | null;
  department: string | null;
  naics_code: string | null;
  set_aside: string | null;
  extra: string | null;
};

const MEMBERS_NOTE = "Member-only page on NSTXL: sign in as a member to read it.";
const GET_FUNDED = ["afwerx", "spacewerx"];   // portals that read a Get Funded page (portals/shared/funding_list.py)
const NO_CLOSE = "No close date on the Get Funded page (TBD, or submissions on a continuous basis).";
const UPCOMING_NOTE = "DOE lists this solicitation as upcoming: it is not open yet.";
const AWARD_NOTE = "Space Florida has posted a notice of intent to award.";
const APFIT_NOTE = "No deadline here: each participating organization sets its own.";
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function readExtra(extra: string | null | undefined): Record<string, unknown> {
  if (!extra) return {};
  try {
    const data: unknown = JSON.parse(extra);
    return data && typeof data === "object" && !Array.isArray(data) ? (data as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

function text(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

/** The issuing office. SAM.gov writes the agency path ("DEPT OF DEFENSE / DEPT OF THE ARMY / AMC");
 *  its sub-tier shows, with the whole path on hover. */
function office(department: string, portal: string): Detail | null {
  if (!department || department === portal) return null;
  const parts = department.split(" / ").map((p) => p.trim()).filter(Boolean);
  return parts.length > 1 ? { text: parts[1], title: department } : { text: department };
}

function firstContact(contacts: unknown): Detail | null {
  if (!Array.isArray(contacts)) return null;
  for (const entry of contacts) {
    if (!entry || typeof entry !== "object") continue;
    const person = entry as Record<string, unknown>;
    const name = text(person.name);
    if (!name) continue;
    const email = text(person.email);
    const item: Detail = { text: name };
    if (email) item.href = `mailto:${email}`;
    const title = [email, text(person.phone)].filter(Boolean).join(", ");
    if (title) item.title = title;
    return item;
  }
  return null;
}

/** The first non-empty text under a key ending in `suffix` ("_deadline_text" for NSTXL and DOE). */
function bySuffix(data: Record<string, unknown>, suffix: string): string {
  for (const [key, value] of Object.entries(data)) {
    if (key.endsWith(suffix) && text(value)) return text(value);
  }
  return "";
}

/** NASA's expected solicitation quarter (award quarter on hover) and estimated value. */
function forecastDetails(extra: Record<string, unknown>): Detail[] {
  const items: Detail[] = [];
  const expected = text(extra.nasa_solicitation_expected);
  if (expected) {
    const item: Detail = { text: `solicitation ${expected}` };
    const award = text(extra.nasa_award_expected);
    if (award) item.title = `Award expected ${award}`;
    items.push(item);
  }
  const value = text(extra.nasa_estimated_value);
  if (value) items.push({ text: value, title: "Estimated contract value" });
  return items;
}

/** Space Florida's documents, linked to the first (the RFP), every name on hover. */
function documentDetails(extra: Record<string, unknown>): Detail[] {
  const links = Array.isArray(extra.spacefl_document_links) ? extra.spacefl_document_links : [];
  const named = links.filter((d): d is Record<string, unknown> => !!d && typeof d === "object" && !!text((d as Record<string, unknown>).name));
  if (!named.length) return [];
  const item: Detail = { text: `${named.length} document${named.length === 1 ? "" : "s"}`,
                         title: named.map((d) => text(d.name)).join("; ") };
  const first = text(named[0].url);
  if (first) item.href = first;
  return [item];
}

function isoDay(value: unknown): string {
  const day = text(value);
  return /^\d{4}-\d{2}-\d{2}$/.test(day) ? day : "";
}

/** "28 Oct" for an ISO date, with the year when it is not `now`'s. */
function shortDate(iso: string, now: Date): string {
  const [year, month, day] = iso.split("-").map(Number);
  const shown = `${day} ${MONTHS[month - 1]}`;
  return year === now.getUTCFullYear() ? shown : `${shown} ${year}`;
}

/** AFWERX and SpaceWERX: a badge per service whose topics the cycle includes, and when it opens
 *  while that is still ahead, so a cycle in pre-release does not look open. */
function cycleDetails(extra: Record<string, unknown>, now: Date): Detail[] {
  const items: Detail[] = [];
  const today = now.toISOString().slice(0, 10);
  for (const prefix of GET_FUNDED) {
    const branches = extra[`${prefix}_branches`];
    for (const branch of Array.isArray(branches) ? branches : []) {
      const name = text(branch);
      if (name) items.push({ text: name, tone: "info", title: `Includes U.S. ${name} topics` });
    }
    const opens = isoDay(extra[`${prefix}_open`]);
    if (opens && opens > today) {
      const item: Detail = { text: `opens ${shortDate(opens, now)}`, tone: "warn" };
      const pre = isoDay(extra[`${prefix}_pre_release`]);
      if (pre) item.title = `Pre-release from ${shortDate(pre, now)}; submissions open ${shortDate(opens, now)}`;
      items.push(item);
    }
  }
  return items;
}

/** Type, office, set-aside and NAICS from the columns, then what each portal keeps in extra. */
export function callDetails(row: DetailRow, now: Date = new Date()): Detail[] {
  const items: Detail[] = [];
  const type = text(row.type);
  if (type) items.push({ text: type });
  const where = office(text(row.department), text(row.portal));
  if (where) items.push(where);
  if (text(row.set_aside)) items.push({ text: text(row.set_aside) });
  if (text(row.naics_code)) items.push({ text: `NAICS ${text(row.naics_code)}` });

  const extra = readExtra(row.extra);
  const number = text(extra.samgov_solicitation_number);
  if (number) items.push({ text: number });
  items.push(...forecastDetails(extra));
  const contact = firstContact(extra.samgov_contacts ?? extra.nasa_contacts);
  if (contact) items.push(contact);
  const files = Array.isArray(extra.samgov_attachments) ? extra.samgov_attachments.length : 0;
  if (files) items.push({ text: `${files} attachment${files === 1 ? "" : "s"}` });
  items.push(...documentDetails(extra));

  if (extra.nstxl_members_only === true) items.push({ text: "members only", tone: "warn", title: MEMBERS_NOTE });
  if (text(extra.doe_status) === "Upcoming") items.push({ text: "upcoming", tone: "warn", title: UPCOMING_NOTE });
  if (extra.spacefl_intent_to_award === true) items.push({ text: "intent to award", tone: "warn", title: AWARD_NOTE });

  const location = text(extra.sscfd_location);
  if (location) items.push({ text: location });
  const repost = text(extra.sscfd_sam_url);
  if (repost) items.push({ text: "also on SAM.gov", href: repost });
  return [...items, ...cycleDetails(extra, now)];
}

/** Hover text for the due date: where the deadline came from, when the portal says. */
export function deadlineNote(extra: string | null | undefined): string | null {
  const data = readExtra(extra);
  const sentence = bySuffix(data, "_deadline_text");
  if (sentence) return `From the page: ${sentence}`;
  if (data.nstxl_no_deadline === true) {
    return data.nstxl_members_only === true
      ? "Member-only page: sign in to NSTXL to see the deadline."
      : "No deadline in the page text; see its documents.";
  }
  if (GET_FUNDED.some((prefix) => data[`${prefix}_no_deadline`] === true)) return NO_CLOSE;
  if (data.nasa_no_deadline === true) {
    const expected = text(data.nasa_solicitation_expected);
    return expected ? `A forecast: NASA expects to release the solicitation in ${expected}.` : "A forecast: no solicitation yet.";
  }
  if (data.apfit_no_deadline === true) return APFIT_NOTE;
  const close = text(data.diu_close);
  return close ? `DIU: ${close}` : null;
}
