"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { FIT_SORT_LABELS, FIT_SORTS, type FitSort } from "@/lib/fitratings";

const SETTLE_MS = 400;   // a search applies once the typing stops

/**
 * Find and sort on Fit ratings (Task 3, 18 Nov 2026): with 54 keywords a row was found by scrolling. The search finds
 * rows in every section by name, what they cover, their note or a NAICS code, and applies once the typing stops; the
 * sort orders every section. Both live in the address (`q`, `sort`), beside the open section, so a found list can be
 * shared like every other filter on the dashboard.
 */
export function FitFind({ query, sort }: { query: string; sort: FitSort }) {
  const router = useRouter();
  const [text, setText] = useState(query);
  const typed = useRef(false);

  const go = (next: { q?: string; sort?: FitSort }) => {
    const url = new URL(window.location.href);   // the open section is in the address (TopTabs keeps it there)
    for (const key of ["notice", "error", "row"]) url.searchParams.delete(key);
    const q = (next.q ?? text).trim();
    if (q) url.searchParams.set("q", q);
    else url.searchParams.delete("q");
    const s = next.sort ?? sort;
    if (s !== "list") url.searchParams.set("sort", s);
    else url.searchParams.delete("sort");
    url.hash = "";
    router.replace(`${url.pathname}${url.search}`, { scroll: false });
  };

  useEffect(() => {
    if (!typed.current) return undefined;
    const timer = window.setTimeout(() => go({ q: text }), SETTLE_MS);
    return () => window.clearTimeout(timer);
  }, [text]);

  return (
    <form
      className="fit-find"
      role="search"
      onSubmit={(event) => {
        event.preventDefault();
        go({ q: text });
      }}
    >
      <label className="field">
        <span className="field-label">Find</span>
        <input
          type="search"
          name="q"
          value={text}
          maxLength={100}
          placeholder="A tag, keyword, NAICS code or note"
          onChange={(event) => {
            typed.current = true;
            setText(event.target.value);
          }}
        />
      </label>
      <label className="field">
        <span className="field-label">Sort</span>
        <select name="sort" value={sort} onChange={(event) => go({ sort: event.target.value as FitSort })}>
          {FIT_SORTS.map((s) => (
            <option key={s} value={s}>
              {FIT_SORT_LABELS[s]}
            </option>
          ))}
        </select>
      </label>
      {query ? <span className="fit-find-count">Showing what matches &ldquo;{query}&rdquo; in each section.</span> : null}
    </form>
  );
}
