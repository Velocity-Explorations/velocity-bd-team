// The fit score on a call (PRO-487): review/fit.py scores it 0 to 100 from the team's ratings and says why. No imports, so
// `node --test` can load it directly.

export type FitColumns = { fit_score: number | null; fit_band: string | null; fit_why: string | null; listing?: string | null };

const TONES: Record<string, string> = { strong: "good", possible: "warn", weak: "grey", "ruled out": "bad" };

/** The fit badge's words, tone and hover text; null for a call with no score yet. */
export function fitBadge(row: Partial<FitColumns>): { text: string; tone: string; why: string } | null {
  const { fit_score: score, fit_band: band } = row;
  if (score === null || score === undefined || !band) return null;
  return { text: band === "ruled out" ? band : `${score} ${band}`, tone: TONES[band] ?? "grey", why: fitReasons(row.fit_why).join("; ") };
}

/** The plain reasons behind a score; none when they cannot be read. */
export function fitReasons(raw: string | null | undefined): string[] {
  try {
    const parsed: unknown = JSON.parse(raw ?? "[]");
    return Array.isArray(parsed) ? parsed.map(String) : [];
  } catch {
    return [];
  }
}
