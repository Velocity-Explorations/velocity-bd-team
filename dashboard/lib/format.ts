// Date and number formatting shared by every page. No imports, so `node --test` can load it directly.

export function isoNow(date: Date = new Date()): string {
  return date.toISOString().replace(/\.\d{3}Z$/, "Z");
}

function toDate(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

const formatters = new Map<string, Intl.DateTimeFormat>();

function formatterFor(timeZone: string): Intl.DateTimeFormat {
  const cached = formatters.get(timeZone);
  if (cached) return cached;
  const options: Intl.DateTimeFormatOptions = {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    timeZoneName: "short",
  };
  let fmt: Intl.DateTimeFormat;
  try {
    fmt = new Intl.DateTimeFormat("en-US", { ...options, timeZone });
  } catch {
    fmt = new Intl.DateTimeFormat("en-US", { ...options, timeZone: "UTC" }); // unknown zone in config
  }
  formatters.set(timeZone, fmt);
  return fmt;
}

/** "2026-10-16 05:35 MDT" for a ledger timestamp, in the given IANA zone. */
export function formatTime(iso: string | null | undefined, timeZone: string): string {
  const d = toDate(iso);
  if (!d) return "";
  const parts: Record<string, string> = {};
  for (const p of formatterFor(timeZone).formatToParts(d)) parts[p.type] = p.value;
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute} ${parts.timeZoneName}`;
}

/** "45s", "2m 49s", "1h 02m". Empty when either end is missing. */
export function formatDuration(startIso: string | null | undefined, endIso: string | null | undefined): string {
  const start = toDate(startIso);
  const end = toDate(endIso);
  if (!start || !end) return "";
  const total = Math.max(0, Math.round((end.getTime() - start.getTime()) / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}h ${String(m).padStart(2, "0")}m`;
  if (m > 0) return `${m}m ${String(s).padStart(2, "0")}s`;
  return `${s}s`;
}

export function formatAgo(iso: string | null | undefined, now: Date = new Date()): string {
  const d = toDate(iso);
  if (!d) return "";
  const secs = Math.round((now.getTime() - d.getTime()) / 1000);
  if (secs < 60) return "just now";
  if (secs < 3600) return `${Math.floor(secs / 60)} min ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)} h ago`;
  return `${Math.floor(secs / 86400)} d ago`;
}

/** runs.stage_counts JSON as ordered [key, count] pairs; anything unexpected is dropped. */
export function parseStageCounts(text: string | null | undefined): [string, number][] {
  if (!text) return [];
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    return [];
  }
  if (!data || typeof data !== "object" || Array.isArray(data)) return [];
  return Object.entries(data as Record<string, unknown>).filter(
    (entry): entry is [string, number] => typeof entry[1] === "number",
  );
}
