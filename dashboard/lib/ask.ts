// Ask Grok's panel (David, 7 Nov 2026): what it shows of a question and its answer. The answer is Grok's text, shown as
// paragraphs and "- " bullets, with links only to this dashboard's own pages or https sites, never as HTML. No imports,
// so `node --test` can load it directly.

export const MAX_QUESTION = 2000;
export const POLL_MS = 2000;
const OFFLINE_MS = 2 * 60 * 1000;   // the assistant beats every 30 seconds while idle

export type Part = { text: string; href?: string; strong?: boolean };
export type Block = { kind: "p"; lines: Part[][] } | { kind: "ul"; items: Part[][] };
export type SourceCall = { id: string; title: string; portal: string };
export type SourceRequest = { id: number; kind: string; summary: string };
export type Sources = { calls: SourceCall[]; facts: string[]; requests: SourceRequest[] };
export type AskMessage = {
  id: number;
  question: string;
  state: string;
  answer: string | null;
  sources: string | null;
  tools: string | null;
  model: string | null;
  cost_usd: number | null;
  asked_at: string;
  answered_at: string | null;
};

const LINK = /\[([^\]\n]+)\]\(([^)\s]+)\)/g;

function safeHref(href: string): string | null {
  if (href.startsWith("/") && !href.startsWith("//") && !href.includes("\\")) return href;
  if (/^https:\/\/[^\s/]+/i.test(href)) return href;
  return null;
}

const BOLD = /\*\*([^*\n]+)\*\*/g;

/** Plain text with its **bold** runs made bold parts. */
function plain(text: string): Part[] {
  const found: Part[] = [];
  let at = 0;
  for (const match of text.matchAll(BOLD)) {
    if (match.index > at) found.push({ text: text.slice(at, match.index) });
    found.push({ text: match[1], strong: true });
    at = match.index + match[0].length;
  }
  if (at < text.length) found.push({ text: text.slice(at) });
  return found;
}

/** One line of text, with its markdown links made parts that link where that is safe, and bold runs bold. */
function parts(line: string): Part[] {
  const found: Part[] = [];
  let at = 0;
  for (const match of line.matchAll(LINK)) {
    const href = safeHref(match[2]);
    if (!href) continue;
    if (match.index > at) found.push(...plain(line.slice(at, match.index)));
    found.push({ text: match[1], href });
    at = match.index + match[0].length;
  }
  if (at < line.length) found.push(...plain(line.slice(at)));
  return found;
}

/** Grok's answer as blocks: a paragraph per run of lines, a list per run of "- " bullets. */
export function parseAnswer(text: string | null | undefined): Block[] {
  const blocks: Block[] = [];
  for (const chunk of (text ?? "").replace(/\r\n/g, "\n").split(/\n\s*\n/)) {
    let list: Part[][] | null = null;
    let para: Part[][] | null = null;
    for (const raw of chunk.split("\n")) {
      const line = raw.trimEnd();
      if (!line.trim()) continue;
      const bullet = /^\s*[-*]\s+(.*)$/.exec(line);
      if (bullet) {
        para = null;
        if (!list) blocks.push({ kind: "ul", items: (list = []) });
        list.push(parts(bullet[1]));
      } else {
        list = null;
        if (!para) blocks.push({ kind: "p", lines: (para = []) });
        para.push(parts(line.trim()));
      }
    }
  }
  return blocks;
}

/** The calls and Company Reference ids an answer names, and the change requests Grok filed (version 2, David, 7 Nov
 *  2026), from the sources column; nothing for anything odd. */
export function parseSources(json: string | null | undefined): Sources {
  try {
    const value: unknown = JSON.parse(json ?? "");
    if (!value || typeof value !== "object") return { calls: [], facts: [], requests: [] };
    const v = value as { calls?: unknown; facts?: unknown; requests?: unknown };
    const calls = Array.isArray(v.calls)
      ? v.calls.flatMap((c) => {
          if (!c || typeof c !== "object") return [];
          const { id, title, portal } = c as Record<string, unknown>;
          return typeof id === "string" && typeof title === "string"
            ? [{ id, title, portal: typeof portal === "string" ? portal : "" }]
            : [];
        })
      : [];
    const facts = Array.isArray(v.facts) ? v.facts.filter((f): f is string => typeof f === "string") : [];
    const requests = Array.isArray(v.requests)
      ? v.requests.flatMap((r) => {
          if (!r || typeof r !== "object") return [];
          const { id, kind, summary } = r as Record<string, unknown>;
          return typeof id === "number" ? [{ id, kind: typeof kind === "string" ? kind : "", summary: typeof summary === "string" ? summary : "" }] : [];
        })
      : [];
    return { calls, facts, requests };
  } catch {
    return { calls: [], facts: [], requests: [] };
  }
}

/** A call an answer names opens on All calls, found by its title. */
export function callHref(call: SourceCall): string {
  return `/calls?q=${encodeURIComponent(call.title.slice(0, 120))}`;
}

/** "grok-4.7, 2 tools, about $0.04": who answered, the tools it called and what it cost. */
export function costLine(model: string | null, tools: string | null, cost: number | null): string {
  if (!model) return "";
  let n = 0;
  try {
    const list: unknown = JSON.parse(tools ?? "[]");
    n = Array.isArray(list) ? list.length : 0;
  } catch {
    n = 0;
  }
  const used = n === 0 ? "no tools" : n === 1 ? "1 tool" : `${n} tools`;
  if (cost === null || cost === undefined) return `${model}, ${used}`;
  return `${model}, ${used}, ${cost < 0.005 ? "under $0.01" : `about $${cost.toFixed(2)}`}`;
}

/** Whether the assistant has gone quiet: not seen for two minutes, or never. */
export function isOffline(seenAt: string | null, now: number = Date.now()): boolean {
  if (!seenAt) return true;
  const seen = Date.parse(seenAt);
  return Number.isNaN(seen) || now - seen > OFFLINE_MS;
}

/** What a waiting question says while the person waits. */
export function statusLine(state: string, seenAt: string | null, now: number = Date.now()): string {
  if (state !== "queued" && state !== "working") return "";
  return isOffline(seenAt, now) ? "Grok is offline, so the question waits until it is back" : "Grok is thinking";
}

/** A thread id the panel made: a UUID's letters, digits and hyphens. */
export function threadIdOk(id: string | null | undefined): id is string {
  return typeof id === "string" && /^[A-Za-z0-9-]{16,64}$/.test(id);
}
