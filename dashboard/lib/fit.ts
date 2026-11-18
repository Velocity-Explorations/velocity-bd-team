// The fit score on a call (PRO-487): review/fit.py scores it 0 to 100 from the team's ratings and says why. No imports, so
// `node --test` can load it directly.

export type FitColumns = { fit_score: number | null; fit_band: string | null; fit_why: string | null; listing?: string | null; matched_keywords?: string | null };

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

/**
 * Why a call scored what it did (Task 4, 18 Nov 2026), from what review/fit.py stored and nothing more: the score and its
 * band, each part the scoring rated (primary focus, type, notice, customer, access, NAICS, keywords, and any cap), and the
 * keywords the filter matched, which count only where the team rated them and they stand as whole words.
 */
export function whyThisScore(row: Partial<FitColumns> & { matched_keywords?: string | null }): { headline: string; parts: string[]; matched: string[] } {
  const { fit_score: score, fit_band: band } = row;
  const headline = score === null || score === undefined || !band
    ? "No fit score yet: no judge has named the call's primary focus"
    : band === "ruled out" ? "Ruled out" : `Fit ${score}, ${band}`;
  let matched: string[] = [];
  try {
    const parsed: unknown = JSON.parse(row.matched_keywords ?? "[]");
    matched = Array.isArray(parsed) ? [...new Set(parsed.map(String))] : [];
  } catch {
    matched = [];
  }
  return { headline, parts: fitReasons(row.fit_why), matched };
}

const SOON_DAYS = 60;   // RANKING in assistant/tools.py: inside each yes group, what closes within 60 days comes first

/**
 * How the Top 10 ranked a call, in words (Task 4, 18 Nov 2026), by its rule (RANKING in assistant/tools.py, David,
 * 6 Nov 2026): yes from both judges, then yes from one; inside each, what closes within 60 days; then the fit score.
 * `claude` is the call's own verdict, `grok` Grok's newest, `daysLeft` as the page counts them.
 */
export function rankReason(input: { claude: string | null; grok: string | null; daysLeft: number | null; score: number | null }): string {
  const yes = [input.claude === "yes" ? "Claude" : null, input.grok === "yes" ? "Grok" : null].filter(Boolean);
  const judges = yes.length === 2 ? "Yes from both judges" : yes.length === 1 ? `Yes from one judge (${yes[0]})` : "No yes from either judge";
  const days = input.daysLeft;
  const due = days === null
    ? `no deadline, so after the calls that close within ${SOON_DAYS} days`
    : days < 0
      ? `it closed ${-days} day${days === -1 ? "" : "s"} ago, after the brief ranked it`
      : days <= SOON_DAYS
        ? `${days === 0 ? "closes today" : `closes in ${days} day${days === 1 ? "" : "s"}`}, within the ${SOON_DAYS} days that rank first`
        : `closes in ${days} days, after the calls that close within ${SOON_DAYS}`;
  return `${judges}; ${due}; then its fit score, ${input.score ?? "none yet"}.`;
}
