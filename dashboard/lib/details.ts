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

/** Type, office, set-aside and NAICS from the columns, then what each portal keeps in extra. */
export function callDetails(row: DetailRow): Detail[] {
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
  const contact = firstContact(extra.samgov_contacts);
  if (contact) items.push(contact);
  const files = Array.isArray(extra.samgov_attachments) ? extra.samgov_attachments.length : 0;
  if (files) items.push({ text: `${files} attachment${files === 1 ? "" : "s"}` });

  if (extra.nstxl_members_only === true) items.push({ text: "members only", tone: "warn", title: MEMBERS_NOTE });

  const location = text(extra.sscfd_location);
  if (location) items.push({ text: location });
  const repost = text(extra.sscfd_sam_url);
  if (repost) items.push({ text: "also on SAM.gov", href: repost });
  return items;
}

/** Hover text for the due date: where the deadline came from, when the portal says. */
export function deadlineNote(extra: string | null | undefined): string | null {
  const data = readExtra(extra);
  const sentence = text(data.nstxl_deadline_text);
  if (sentence) return `From the page: ${sentence}`;
  if (data.nstxl_no_deadline === true) {
    return data.nstxl_members_only === true
      ? "Member-only page: sign in to NSTXL to see the deadline."
      : "No deadline in the page text; see its documents.";
  }
  const close = text(data.diu_close);
  return close ? `DIU: ${close}` : null;
}
