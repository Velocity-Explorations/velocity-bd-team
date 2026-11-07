// What kind of listing a call is (David, 7 Nov 2026; calls.listing, migration 015): a call to respond to now, an
// umbrella whose calls come under it, or an announcement with nothing to submit yet. Home's Top 10 holds calls; the
// umbrellas and announcements have a top 10 of their own on the next tab. No imports, so `node --test` can load it.

export const WATCH = ["Umbrella", "Announcement"];
export type TopTab = "calls" | "watch";

const MEANS: Record<string, string> = {
  Umbrella: "A standing CSO, BAA or cycle: its calls come under it, or it takes white papers at any time.",
  Announcement: "Nothing to submit yet: a forecast, a presolicitation or coming-soon notice, or an event.",
};

/** Whether a call belongs in the top 10 to watch rather than the Top 10. No kind yet counts as a call. */
export function isWatch(listing: string | null | undefined): boolean {
  return Boolean(listing && WATCH.includes(listing));
}

/** The badge a row wears for its kind, or null for a plain call. */
export function listingBadge(listing: string | null | undefined): { text: string; title: string } | null {
  if (!listing || !isWatch(listing)) return null;
  return { text: listing.toLowerCase(), title: MEANS[listing] };
}

/** Which of Home's two lists to open: the watch list only when the link asks for it (/?top=watch). */
export function topTab(param: string | string[] | undefined): TopTab {
  const value = Array.isArray(param) ? param[0] : param;
  return value === "watch" ? "watch" : "calls";
}
