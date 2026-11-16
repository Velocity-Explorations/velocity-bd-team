// Small string helpers with no imports, so `node --test` can load them directly.

/** One human_notes line, in the format the pipeline's append_note() writes: "[at by] text". */
export function noteLine(at: string, by: string, text: string): string {
  const clean = text.replace(/\s+/g, " ").trim();
  return clean ? `[${at} ${by}] ${clean}` : "";
}

/** Escape LIKE wildcards; backslash is Postgres's default LIKE escape character. */
export function escapeLike(query: string): string {
  return query.replace(/[\\%_]/g, (c) => `\\${c}`);
}

/** A redirect target from a form field: same-site relative paths only. */
export function safeReturnTo(value: unknown, fallback = "/"): string {
  if (typeof value !== "string") return fallback;
  if (!value.startsWith("/") || value.startsWith("//") || value.includes("\\")) return fallback;
  if (/[\u0000-\u001f\u007f]/.test(value)) return fallback;
  return value;
}

/** Portal adapters flag a closed call in calls.extra with a key ending in "_closed". */
export function isClosed(extra: string | null | undefined): boolean {
  if (!extra) return false;
  try {
    const data: unknown = JSON.parse(extra);
    if (!data || typeof data !== "object" || Array.isArray(data)) return false;
    return Object.entries(data as Record<string, unknown>).some(([key, value]) => key.endsWith("_closed") && value === true);
  } catch {
    return false;
  }
}

/** First value of a search param, trimmed and capped. */
export function firstParam(raw: string | string[] | undefined, maxLength = 200): string {
  const value = Array.isArray(raw) ? raw[0] : raw;
  return (value ?? "").trim().slice(0, maxLength);
}

export type NoteParts = { at: string | null; by: string | null; text: string };

/** "[at by] text" back into its parts; lines in any other shape come back as plain text. */
export function parseNoteLine(line: string): NoteParts {
  const match = /^\[(\S+) ([^\]]+)\] ?(.*)$/.exec(line);
  return match ? { at: match[1], by: match[2], text: match[3] } : { at: null, by: null, text: line };
}

/** A note's stamp as the ledger writes it (isoNow, append_note): what a note box may send back to edit its line. */
export function isNoteStamp(value: unknown): value is string {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(value);
}

/**
 * A call's notes after a save from a note box (David, 16 Nov 2026). The box's first save adds `[now by] text` and
 * returns `now`; each later save sends that stamp back and edits its line in place, and an empty box takes the line
 * away. A stamp matches only `by`'s own line; if that line has gone (a decision took its place), the note starts again.
 * Every other line, a Slack reply's second line included, stays exactly as it was.
 */
export function writeNoteLine(notes: string | null, at: string | null, by: string, text: string, now: string): { notes: string | null; at: string | null } {
  const lines = notes ? notes.split("\n") : [];
  const index = at ? lines.findIndex((line) => line.startsWith(`[${at} ${by}] `)) : -1;
  const stamp = index >= 0 && at ? at : now;
  const line = noteLine(stamp, by, text);
  if (index >= 0) {
    if (line) lines[index] = line;
    else lines.splice(index, 1);
  } else if (line) {
    lines.push(line);
  } else {
    return { notes, at: null };
  }
  return { notes: lines.join("\n") || null, at: line ? stamp : null };
}

/**
 * A call's notes without `by`'s newest line when that line says `text`: the note box saved it as it was typed, and the
 * decision now carries the same note (behind a Not relevant reason, if one was chosen), so it is not kept twice.
 */
export function withoutTypedNote(notes: string | null, by: string, text: string): string | null {
  const clean = text.replace(/\s+/g, " ").trim();
  if (!notes || !clean) return notes;
  const lines = notes.split("\n");
  for (let i = lines.length - 1; i >= 0; i -= 1) {
    const parts = parseNoteLine(lines[i]);
    if (parts.by !== by) continue;
    if (parts.text !== clean) return notes;
    lines.splice(i, 1);
    return lines.join("\n") || null;
  }
  return notes;
}

export function buildHref(base: string, params: Record<string, string | null | undefined>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) query.set(key, value);
  }
  const text = query.toString();
  return text ? `${base}?${text}` : base;
}

/** The notice after a decision. A vote from the review queue takes the call out of the voter's
 *  queue, so the notice says so (PRO-554); `stays` names the call's decision when it is not yours. */
export function decidedNotice(plan: "decide" | "add" | "note", label: string, title: string, stays: string, fromQueue: boolean): string {
  if (plan === "note") return `Note added: ${title}`;
  const moved = fromQueue ? " It has left your queue." : "";
  if (plan === "decide") return fromQueue ? `${label}: ${title}.${moved}` : `${label}: ${title}`;
  return `Added your decision, ${label}: ${title}.${stays}${moved}`;
}

/** Whether a decision's return address is the queue (Needs review and its views, at /review since PRO-570). */
export function fromQueue(returnTo: string): boolean {
  return new URL(returnTo, "http://dashboard.local").pathname === "/review";
}

/** All calls, filtered to a call's title (the title filter reads 120 characters), where every
 *  person's vote on it shows. */
export function votedHref(title: string): string {
  return buildHref("/calls", { q: title.slice(0, 120) });
}
