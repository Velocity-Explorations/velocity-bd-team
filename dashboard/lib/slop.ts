// The AI slop check's result (PW20 to PW23, phase 8b): the newest scan of a pursuit's drafts as the page shows
// it, read from slop_scans. The worker runs the scanner and the gate (drafting/scan.py, drafting/slop_gate.py);
// the page never does. Labels report writing patterns and their fixes only: none says or implies who or what
// wrote the text, and a label that names a model or a chatbot loses the name (PW23). No imports, so
// `node --test` can load it directly.

/** One scan, as slop_scans holds it (migration 008). */
export type ScanRow = {
  id: number;
  pursuit_id: number;
  step_id: number | null;
  draft_name: string | null;
  scanned_at: string;
  words: number | null;
  band: string | null;
  confidence: string | null;
  points: number | null;
  provisional: number;
  ready: number;
  verdict: string;
  fixed_count: number;
  result_json: string;
  text_lines: string | null;
};

/** The newest Check again for a pursuit (worker_jobs, kind `slop_scan`). */
export type ScanJob = {
  id: number;
  state: string;
  requested_by: string;
  requested_at: string;
  started_at: string | null;
  finished_at: string | null;
  result: string | null;
};

/** The tiers that count toward the band, in the order the page lists them, with the names the page uses. */
export const TIERS: [string, string][] = [
  ["discourse", "Discourse templates"],
  ["lexicon", "Dated word lists"],
  ["surface", "Surface habits"],
  ["residue", "Tool residue"],
  ["sourcing", "Tracking parameters"],
  ["house", "House rules"],
];
const FAULTS = "proposal";
const OPEN_FAMILY = "prop_open_item";   // drafting/slop_gate.py OPEN_FAMILY
const HOT_PARAGRAPHS = 5;

/** The placeholder kinds the gate counts (drafting/slop_gate.py PLACEHOLDER_KINDS), each with what it stands for. */
export const PLACEHOLDER_KINDS: [string, RegExp, string][] = [
  ["PERSON WRITES", /^\[PERSON\s+WRITES/i, "text a person must write"],
  ["NEEDS INPUT", /^\[NEEDS?\s+INPUT/i, "facts only you have"],
  ["NEEDS EVIDENCE", /^\[NEEDS?\s+EVIDENCE/i, "claims that need a source"],
];

export type Spot = { line: number; column: number; match: string };
export type FamilyView = { key: string; label: string; tier: string; hits: number; per1k: number; points: number; fix: string; spots: Spot[] };
export type Placeholder = { line: number; match: string; section: string };

export type SlopView = {
  verdict: string;
  ready: boolean;
  band: string | null;
  points: number | null;
  confidence: string;
  words: number;
  provisional: boolean;
  draft: string;
  scannedAt: string;
  fixed: number;
  placeholders: { kind: string; note: string; items: Placeholder[] }[];
  open: number;
  hot: { first: number; last: number; section: string; findings: number; families: string[] }[];
  families: FamilyView[];
  quiet: string[];
  faults: FamilyView[];
  exempt: number;
  lines: string[];
};

type Family = { label?: string; tier?: string; hits?: number; per_1k?: number; points?: number; fix?: string };
type Finding = { family?: string; tier?: string; line?: number; column?: number; match?: string; exempt?: string };
type Report = { families?: Record<string, Family>; findings?: Finding[]; hot_paragraphs?: { lines?: number[]; findings?: number; families?: string[] }[] };

const NAMED = /\b(chatbots?|AI|LLMs?|ChatGPT|GPT[-\w.]*|Claude|Gemini|Grok|Llama|Copilot|Mistral|DeepSeek|Qwen)\b/gi;

function tierName(tier: string): string {
  return TIERS.find(([key]) => key === tier)?.[1] ?? (tier === FAULTS ? "Proposal faults" : "Writing patterns");
}

function sentence(text: string): string {
  return text ? text[0].toUpperCase() + text.slice(1) : text;
}

/** A family's label as the page shows it: the dated word lists as Overused words, and no model or chatbot named. */
export function familyLabel(label: string, tier: string): string {
  if (tier === "lexicon") return "Overused words";
  const plain = label.replace(/\([^)]*\)/g, " ").replace(NAMED, " ").replace(/\s+/g, " ").trim();
  return plain ? sentence(plain) : tierName(tier);
}

export function placeholderKind(match: string): string {
  return PLACEHOLDER_KINDS.find(([, pattern]) => pattern.test(match))?.[0] ?? "other";
}

/** The nearest Markdown heading at or above a line (1-based), or "". */
export function sectionAt(lines: string[], line: number): string {
  for (let i = Math.min(line, lines.length) - 1; i >= 0; i--) {
    const heading = /^#{1,6}\s+(.*?)\s*#*\s*$/.exec(lines[i]);
    if (heading) return heading[1].replace(/\*\*/g, "").trim();
  }
  return "";
}

/** "draft_v2.md" reads "Draft v2"; the final version is the final version. */
export function draftLabel(name: string | null): string {
  if (!name) return "the draft";
  const version = /^draft_v(\d+)/.exec(name);
  if (version) return `Draft v${version[1]}`;
  return name.startsWith("draft_final") ? "Final version" : name.replace(/\.md$/, "");
}

export function bandTone(band: string | null): "good" | "warn" | "conflict" | "grey" {
  switch (band) {
    case "clean":
    case "light":
      return "good";
    case "revise":
      return "warn";
    case "heavy":
      return "conflict";
    default:
      return "grey";
  }
}

/** The scanner's confidence in words: full reads normal (300 words or more). */
export function confidenceWord(confidence: string | null): string {
  if (!confidence) return "not given";
  return confidence === "full" ? "normal" : confidence;
}

/** The notes under the verdict line (PW21). */
export function bandNotes(view: { words: number; confidence: string; provisional: boolean }): string[] {
  if (view.words < 150) return ["Under 150 words, so no band is given; only the placeholders and proposal faults are checked."];
  const notes = view.confidence === "low" ? ["Under 300 words, so the band has low confidence."] : [];
  if (view.provisional) {
    notes.push("The band lines are provisional until they are calibrated on 20 or more Velocity proposals written from 2019 " +
      "to 2022. Ready needs no open placeholder and a band of clean or light.");
  }
  return notes;
}

function num(value: unknown): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function round(n: number): number {
  return Math.round(n * 10) / 10;
}

function spotsOf(findings: Finding[], keys: string[]): Spot[] {
  return findings
    .filter((f) => keys.includes(String(f.family)))
    .map((f) => ({ line: num(f.line), column: num(f.column), match: String(f.match ?? "") }))
    .sort((a, b) => a.line - b.line || a.column - b.column);
}

function familyView(key: string, keys: string[], families: Record<string, Family>, findings: Finding[]): FamilyView {
  const first = families[keys.find((k) => num(families[k].hits) > 0) ?? keys[0]];
  const tier = String(first.tier ?? "");
  return {
    key,
    label: familyLabel(String(first.label ?? key), tier),
    tier: tierName(tier),
    hits: round(keys.reduce((sum, k) => sum + num(families[k].hits), 0)),
    per1k: round(keys.reduce((sum, k) => sum + num(families[k].per_1k), 0)),
    points: round(keys.reduce((sum, k) => sum + num(families[k].points), 0)),
    fix: String(first.fix ?? ""),
    spots: spotsOf(findings, keys),
  };
}

/** The result page's content (PW20), from the stored scan. A report that does not parse leaves only the verdict. */
export function slopView(scan: ScanRow): SlopView {
  let report: Report = {};
  try {
    const parsed = JSON.parse(scan.result_json);
    if (parsed && typeof parsed === "object") report = parsed as Report;
  } catch {
    report = {};
  }
  const lines = scan.text_lines ? scan.text_lines.split(/\r?\n/) : [];
  const families = report.families && typeof report.families === "object" ? report.families : {};
  const all = Array.isArray(report.findings) ? report.findings : [];
  const findings = all.filter((f) => !f.exempt);
  const confidence = confidenceWord(scan.confidence);
  const words = num(scan.words);

  const open = findings.filter((f) => f.family === OPEN_FAMILY);
  const kinds = [...PLACEHOLDER_KINDS.map(([kind, , note]) => [kind, note]), ["other", "other bracketed notes"]];
  const placeholders = kinds
    .map(([kind, note]) => ({
      kind,
      note,
      items: open.filter((f) => placeholderKind(String(f.match ?? "")) === kind)
        .map((f) => ({ line: num(f.line), match: String(f.match ?? ""), section: sectionAt(lines, num(f.line)) }))
        .sort((a, b) => a.line - b.line),
    }))
    .filter((group) => group.items.length);

  // The dated word lists read as one family; every other family that counts toward the band stands on its own.
  const banded = Object.keys(families).filter((k) => TIERS.some(([tier]) => tier === families[k].tier));
  const lexicon = banded.filter((k) => families[k].tier === "lexicon");
  const groups: [string, string[]][] = [
    ...banded.filter((k) => families[k].tier !== "lexicon").map((k): [string, string[]] => [k, [k]]),
    ...(lexicon.length ? [["lexicon", lexicon] as [string, string[]]] : []),
  ];
  const shown = groups
    .map(([key, keys]) => familyView(key, keys, families, findings))
    .filter((f) => f.hits > 0 || f.spots.length)
    .sort((a, b) => b.points - a.points || b.hits - a.hits || a.label.localeCompare(b.label));
  const quiet = TIERS.filter(([tier]) => !shown.some((f) => f.tier === tierName(tier))).map(([, name]) => name);
  const faults = Object.keys(families)
    .filter((k) => families[k].tier === FAULTS && k !== OPEN_FAMILY)
    .map((k) => familyView(k, [k], families, findings))
    .filter((f) => f.hits > 0 || f.spots.length)
    .sort((a, b) => b.hits - a.hits || a.label.localeCompare(b.label));

  const named = new Map(Object.values(families).map((f) => [String(f.label ?? ""), familyLabel(String(f.label ?? ""), String(f.tier ?? ""))]));
  const hot = (Array.isArray(report.hot_paragraphs) ? report.hot_paragraphs : []).slice(0, HOT_PARAGRAPHS).map((p) => {
    const span = Array.isArray(p.lines) && p.lines.length ? p.lines : [0];
    const first = num(span[0]);
    return {
      first,
      last: num(span[span.length - 1]),
      section: sectionAt(lines, first),
      findings: num(p.findings),
      families: [...new Set((p.families ?? []).map((label) => named.get(String(label)) ?? familyLabel(String(label), "")))],
    };
  });

  return {
    verdict: scan.verdict,
    ready: Boolean(scan.ready),
    band: scan.band,
    points: scan.points,
    confidence,
    words,
    provisional: Boolean(scan.provisional),
    draft: draftLabel(scan.draft_name),
    scannedAt: scan.scanned_at,
    fixed: num(scan.fixed_count),
    placeholders,
    open: open.length,
    hot,
    families: shown,
    quiet,
    faults,
    exempt: all.length - findings.length,
    lines,
  };
}

/** `?lines=88` or `?lines=86-94`, kept inside the text; anything else opens no text. */
export function parseLines(param: string | undefined, total: number): { first: number; last: number } | null {
  const found = /^(\d{1,6})(?:-(\d{1,6}))?$/.exec(param ?? "");
  if (!found) return null;
  const first = Number(found[1]);
  const last = Math.min(Number(found[2] ?? found[1]), total);
  return first >= 1 && first <= total && last >= first ? { first, last } : null;
}

/** The lines around a link, the linked ones marked. */
export function excerpt(lines: string[], first: number, last: number, pad = 3): { n: number; text: string; hit: boolean }[] {
  const out = [];
  for (let n = Math.max(1, first - pad); n <= Math.min(lines.length, last + pad); n++) {
    out.push({ n, text: lines[n - 1], hit: n >= first && n <= last });
  }
  return out;
}

/** What was found on each line, for the text beside the list: open placeholders, then families, then faults. */
export function lineNotes(view: SlopView): Map<number, string[]> {
  const notes = new Map<number, string[]>();
  const add = (line: number, note: string) => {
    const seen = notes.get(line) ?? [];
    if (!seen.includes(note)) notes.set(line, [...seen, note]);
  };
  for (const group of view.placeholders) for (const item of group.items) add(item.line, `${group.kind}, open`);
  for (const family of [...view.families, ...view.faults]) for (const spot of family.spots) add(spot.line, family.label);
  return notes;
}

/** Check again in words (PW22): queued or working, or failed when that is newer than the scan shown. */
export function jobState(job: ScanJob | null, scannedAt: string | null): "queued" | "working" | "failed" | null {
  if (!job) return null;
  if (job.state === "queued" || job.state === "working") return job.state;
  if (job.state === "failed" && job.finished_at && (!scannedAt || job.finished_at > scannedAt)) return "failed";
  return null;
}

/** The result page for a step, at a line or a range of lines, scrolled back to the item that linked there. */
export function slopHref(step: string, first?: number, last?: number, anchor?: string): string {
  const query = new URLSearchParams({ step, view: "slop" });
  if (first) query.set("lines", last && last !== first ? `${first}-${last}` : String(first));
  return `?${query.toString()}${anchor ? `#${anchor}` : ""}`;
}

// ------------------------------------------------------------------- Final checks (PW13, phase 9b)

const FINAL = "draft_final";

/** Why Final checks cannot be approved yet, or null (PW13, PW21): the newest scan must be of the final version and Ready. */
export function finalGate(scan: ScanRow | null): string | null {
  if (!scan || !(scan.draft_name ?? "").startsWith(FINAL)) return "No AI slop check of the final version is saved yet. Choose Check again.";
  if (scan.ready) return null;
  return `The AI slop check says ${scan.verdict}. Fill what is left in the final version, then choose Check again.`;
}

export type FinalCheck = { check: string; ok: boolean | null; result?: string; detail: string };

/** The step's seven checks, with the placeholder sweep and the slop check's final pass taken from a newer scan of the
 *  final version when Check again has run since the step was saved. */
export function finalChecks(checks: FinalCheck[], scan: ScanRow | null, finishedAt: string | null): FinalCheck[] {
  if (!scan || !(scan.draft_name ?? "").startsWith(FINAL) || (finishedAt && scan.scanned_at <= finishedAt)) return checks;
  const open = slopView(scan).open;
  return checks.map((c) => {
    if (c.check === "Placeholder sweep") {
      return open ? { ...c, ok: false, result: `${open} left`, detail: `${open} still open, checked again` }
        : { ...c, ok: true, result: "none left", detail: "none left, checked again" };
    }
    if (c.check === "AI slop check, final pass") {
      return { ...c, ok: Boolean(scan.ready), result: scan.ready ? "ready" : "not ready", detail: `${scan.verdict}, checked again` };
    }
    return c;
  });
}
