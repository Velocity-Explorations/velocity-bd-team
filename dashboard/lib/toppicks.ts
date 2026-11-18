// Ratings of the Top 10's picks (Task 5 of the 9 Nov review, 18 Nov 2026): whether each pick in a week's Top 10 belongs
// there, in each person's view, kept apart from their decision on the call (migration 022, top10_ratings). Nothing ranks
// calls by them; Automation's Top 10 reviews shows where people agree. No imports, so `node --test` can load it directly.

export const PICK_RATINGS = ["good_pick", "not_a_fit", "unsure"] as const;
export type PickRating = (typeof PICK_RATINGS)[number];

export const PICK_LABELS: Record<PickRating, string> = { good_pick: "Good pick", not_a_fit: "Not a fit", unsure: "Unsure" };
export const PICK_TONES: Record<PickRating, string> = { good_pick: "good", not_a_fit: "bad", unsure: "warn" };

export const MAX_PICK_COMMENT = 300;

export type PickRow = { week_of: string; call_id: string; rated_by: string; rating: string; comment: string | null; rated_at: string };
export type PickRated = { rating: string; comment: string | null };
export type Agreement = "agree" | "split" | "one" | "none";

export function isPickRating(value: unknown): value is PickRating {
  return typeof value === "string" && (PICK_RATINGS as readonly string[]).includes(value);
}

/** Whether the people who rated a pick agree: two or more alike agree, any difference splits them. */
export function agreementOf(ratings: string[]): Agreement {
  if (ratings.length === 0) return "none";
  if (ratings.length === 1) return "one";
  return ratings.every((r) => r === ratings[0]) ? "agree" : "split";
}

export type ReviewWeek = {
  week: string;
  reviewers: string[];
  picks: { place: number; id: string; title: string; portal: string | null; by: Record<string, PickRated>; agreement: Agreement }[];
  summary: { picks: number; rated: number; agree: number; split: number };
};

/**
 * Each week's Top 10 with every reviewer's rating and comment of each pick, in the brief's order, and whether they agree.
 * `rated` counts the picks someone rated; a week keeps its own ratings, so a call picked in two weeks is rated in each.
 */
export function reviewWeeks(briefs: { week: string; picks: { id: string; title: string; portal: string | null }[] }[], rows: PickRow[]): ReviewWeek[] {
  return briefs.map(({ week, picks }) => {
    const own = rows.filter((r) => r.week_of === week);
    const reviewers = [...new Set(own.map((r) => r.rated_by))].sort((a, b) => a.localeCompare(b));
    const listed = picks.map((pick, i) => {
      const by: Record<string, PickRated> = {};
      for (const r of own.filter((x) => x.call_id === pick.id)) by[r.rated_by] = { rating: r.rating, comment: r.comment };
      return { place: i + 1, ...pick, by, agreement: agreementOf(Object.values(by).map((v) => v.rating)) };
    });
    return {
      week,
      reviewers,
      picks: listed,
      summary: {
        picks: listed.length,
        rated: listed.filter((p) => p.agreement !== "none").length,
        agree: listed.filter((p) => p.agreement === "agree").length,
        split: listed.filter((p) => p.agreement === "split").length,
      },
    };
  });
}

/** For Home: the viewer's own rating of each pick in a week, and everyone else's, by call. */
export function picksFor(rows: PickRow[], week: string, viewer: string | null): {
  mine: Map<string, PickRated>;
  others: Map<string, { person: string; rating: string; comment: string | null }[]>;
} {
  const mine = new Map<string, PickRated>();
  const others = new Map<string, { person: string; rating: string; comment: string | null }[]>();
  for (const r of rows.filter((x) => x.week_of === week)) {
    if (viewer && r.rated_by === viewer) {
      mine.set(r.call_id, { rating: r.rating, comment: r.comment });
    } else {
      others.set(r.call_id, [...(others.get(r.call_id) ?? []), { person: r.rated_by, rating: r.rating, comment: r.comment }]);
    }
  }
  return { mine, others };
}
